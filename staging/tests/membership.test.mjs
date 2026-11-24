/* ============================================================
   멤버십 화면 — 요금제 하나 · 열람 무제한 · 새 환불 안내가 실제 화면에 그대로 나오는가 (2026-11-24)

   왜 있나
     사장 결정(2026-11-24): "요금제는 1개 14900원. 열람은 무제한. 7일 이내 환불할 때는 이용일수만 차감하고 환불.
     7일 이후 환불은 이용일수 차감하고 결제가격의 10%만큼 떼고 환불." 금융감독원에 낸 신고 서류(이용약관 · 사업계획서)와
     스테이징 화면이 같은 말을 해야 한다. 계산은 subscription · two-sides 시험이 보고, 여기서는 사람이 보는 화면을 본다 —
     요금제 화면 · 결제 화면 · 리포트의 잠금 카드 · 설정의 환불 확인 창.

   보는 것 (스테이징 · 크로미움 · 파이어베이스는 대역)
     ① 요금제 화면 — 두 단(무료 · 멤버십) · 월 14,900원 · 표의 열 둘 · 하루 열람 한도 줄 없음 · 요금제 변경 확인 창 없음 ·
        BASIC · PRO · '2,500여' · '전 종목' 없음
     ② 자주 묻는 질문 — 질문 목록(옛 셋을 빼고 '열람할 수 있는 리포트 수에 제한이 있나요?' 를 넣음) · 환불 답이 명세 4절의
        환불 안내와 한 글자까지 같다(영어 답은 결제 화면 · 설정과 같은 글) · 지금 말이 아닌 쪽은 숨는다
     ③ 구독 단추 — 로그아웃 · 구독 없음 · 이용 중 · 결제 실패마다 이름과 가는 곳(업그레이드 단추 없음)
     ④ 결제 화면 — 환불 안내가 결제 단추보다 위에 실제로 보인다(컴퓨터 · 휴대폰)
     ⑤ 리포트 잠금 카드 — '멤버십 월 14,900원'(요금은 payment-config 의 값) · 자동 수집 제한(61번째 새 종목)이면 명세 문구로
        바뀌고 '멤버십 보기' 는 숨고 '이어서 읽기' 는 남는다 · 오늘 이미 연 종목은 제한 중에도 열린다
     ⑥ 설정의 환불 확인 창 — 휴대폰에서 제목이 화면 안에 있고 계산 내역 · 환불 기준이 실린다
        (처음 판은 창을 열며 단추로 초점을 옮겨 창이 맨 아래까지 굴렀다 — 제목 · 환불 금액이 화면 위로 사라진 채 열렸다)

   고치기 전 스테이징(BASIC · PRO 판 — 커밋 830f40c9b)에 돌리면 39건 중 35건이 걸린다.

   실행
     node staging/tests/membership.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) for (const sub of ["chrome-linux64", "chrome-linux"]) { const p = `${base}/${d}/${sub}/chrome`; if (existsSync(p)) return p; }
  return null;
})();
if (!CHROME) { console.error("크로미움을 찾지 못했습니다(PLAYWRIGHT_BROWSERS_PATH 확인)."); process.exit(2); }

/* 명세 4절의 환불 안내 — 결제 화면 · 자주 묻는 질문 · 설정의 환불 확인 창이 같은 글을 쓴다. 명세에서 그대로 옮겼다. */
const NOTICE = [
  "환불 금액은 환불 신청일부터 3영업일 이내에 결제하신 수단으로 돌려드립니다.",
  "결제일(정기결제 갱신 결제일 포함)부터 7일 이내에 신청하시면, 결제금액에서 이용하신 날의 이용료를 뺀 금액을 환불합니다. 결제 후 리포트의 유료 영역을 열람하지 않으셨다면 전액 환불합니다.",
  "결제일부터 7일이 지난 뒤에 신청하시면, 결제금액에서 이용하신 날의 이용료와 결제금액의 10%(위약금)를 뺀 금액을 환불합니다. 계산한 금액이 0원 이하이면 환불 금액은 없으며, 추가로 청구하지 않습니다.",
  "이용하신 날의 이용료 = 결제금액 ÷ 해당 이용 기간의 일수 × 이용일수(이용 기간 시작일부터 환불 신청일까지). 1원 미만은 회원에게 유리하게 처리합니다.",
  "예) 이용 기간 30일 기준 — 3일째 신청 13,410원 환불 / 10일째 신청 8,444원 환불",
  "의무 사용 기간은 없으며, 설정의 구독 항목에서 언제든지 해지하실 수 있습니다. 해지하시면 다음 결제일부터 이용료가 청구되지 않고, 이미 결제하신 기간이 끝날 때까지 이용하실 수 있습니다.",
];
const BURST = ["짧은 시간에 리포트를 너무 많이 열어 열람이 잠시 제한되었습니다.", "잠시 후 다시 이용하여 주시기 바랍니다."];
/* 화면의 요금 · 영어 안내는 payment-config.js 의 값(JSON 표시 사이)을 쓴다 — 시험도 거기서 읽어 견준다 */
const CFG_SRC = readFileSync(join(ROOT, "staging/payment-config.js"), "utf8");
const block = (name) => { const m = CFG_SRC.match(new RegExp(`export const ${name} = /\\*@json\\*/([\\s\\S]*?)/\\*@/json\\*/`)); return m ? JSON.parse(m[1]) : null; };
const PLANS = block("PLANS") || {}, REFUND = block("REFUND_NOTICE") || { en: { lead: "", steps: [], notes: [] } };
const SPEC_PRICE = 14900;                                  /* 명세 1절 — 월 14,900원 */
const PRICE = (PLANS.member && PLANS.member.price) || SPEC_PRICE;

/* ── 파이어베이스 대역(english.test.mjs 와 같은 틀) ───────────────── */
const CONSENT_VERSION = readFileSync(join(ROOT, "staging/consent.js"), "utf8").match(/CONSENT_VERSION\s*=\s*"([^"]+)"/)[1];
const UID = "u-member-test";
const fakeAuth = (signedIn) => `
    const U = ${signedIn ? `{ uid: ${JSON.stringify(UID)}, email: "t@example.com", displayName: "Tester", emailVerified: true,
      providerData: [{ providerId: "google.com" }], metadata: { creationTime: "Thu, 01 Oct 2026 00:00:00 GMT" },
      getIdToken: async () => "t", reload: async () => {} }` : "null"};
    const A = { currentUser: U };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(U), 0); return () => {}; }
    export function onIdTokenChanged(a, cb){ setTimeout(() => cb(U), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    export class OAuthProvider { constructor(){} setCustomParameters(){} addScope(){} }
    export class EmailAuthProvider { static credential(){ return {}; } }
    const no = async () => ({});
    export const applyActionCode = no, confirmPasswordReset = no, createUserWithEmailAndPassword = no, checkActionCode = no,
      deleteUser = no, signInWithCustomToken = no, signInWithEmailAndPassword = no, signInWithPopup = no, signInWithRedirect = no,
      signOut = no, verifyPasswordResetCode = async () => "t@example.com", sendEmailVerification = no, sendPasswordResetEmail = no,
      updateProfile = no, updatePassword = no, reauthenticateWithCredential = no, reauthenticateWithPopup = no, linkWithPopup = no,
      setPersistence = no, getRedirectResult = async () => null, fetchSignInMethodsForEmail = async () => [];
    export const browserLocalPersistence = {}, browserSessionPersistence = {};
    export function getAdditionalUserInfo(){ return null; }`;
const FAKE_FS = `
    const K = (p) => "__fakefs:" + p, subs = {}, DEL = { del: 1 };
    function read(p){ try { return JSON.parse(localStorage.getItem(K(p)) || "null"); } catch (e) { return null; } }
    function snap(p){ const d = read(p); return { exists: () => d != null, data: () => d, metadata: { fromCache: false, hasPendingWrites: false } }; }
    export function getFirestore(){ return {}; } export function initializeFirestore(){ return {}; }
    export function doc(db, ...parts){ return { path: parts.join("/") }; }
    export function collection(db, ...parts){ return { path: parts.join("/") }; }
    export function deleteField(){ return DEL; } export function serverTimestamp(){ return Date.now(); }
    export function onSnapshot(ref, next){ setTimeout(() => next(snap(ref.path)), 20); return () => {}; }
    export async function getDoc(ref){ return snap(ref.path); }
    export async function setDoc(ref, data){ localStorage.setItem(K(ref.path), JSON.stringify(Object.assign(read(ref.path) || {}, data))); }
    export async function updateDoc(ref, data){ localStorage.setItem(K(ref.path), JSON.stringify(Object.assign(read(ref.path) || {}, data))); }
    export async function addDoc(){ return { id: "x" }; } export async function deleteDoc(ref){ localStorage.removeItem(K(ref.path)); }
    export const persistentLocalCache = () => ({}), persistentMultipleTabManager = () => ({});`;
const FAKE = (signedIn) => ({
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; } export function getApp(){ return {}; } export function getApps(){ return []; }`,
  "firebase-auth": fakeAuth(signedIn),
  "firebase-firestore": FAKE_FS,
  "firebase-functions": `export function getFunctions(){ return {}; } export function httpsCallable(){ return async () => ({ data: {} }); }`,
  "firebase-app-check": `export function initializeAppCheck(){ return {}; } export class ReCaptchaV3Provider { constructor(){} } export class ReCaptchaEnterpriseProvider { constructor(){} }`,
  "firebase-analytics": `export function getAnalytics(){ return {}; } export function logEvent(){} export function isSupported(){ return Promise.resolve(false); }`,
});

const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
  ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: CHROME });

/* 모의 결제의 기록 — 결제한 지 elapsed 일 지난 멤버십(한국 시간 정오 결제) */
const DAY = 86400e3, KST = 9 * 3600e3;
const demoSub = (elapsed, { viewed = true, status = "active" } = {}) => {
  const noon = Math.floor((Date.now() + KST) / DAY) * DAY - KST + 12 * 3600e3, start = noon - elapsed * DAY;
  return { status, plan: "member", currentPeriodStart: start, currentPeriodEnd: start + 30 * DAY, cancelAtPeriodEnd: false,
           startedAt: start, card: { company: "", issuerCode: "61", number: "0000-00**-****-0000" },
           periodPayments: [{ key: "demo", amount: PRICE, from: start }], readsSincePay: viewed ? 3 : 0 };
};
/* 최근 30분 안에 새 종목 60개 — 자동 수집 제한의 문턱. withTicker 를 주면 그 종목도 오늘 연 것으로 넣는다 */
const burstReads = (withTicker) => {
  const now = Date.now(), t = Array.from({ length: 60 }, (_, i) => withTicker && i === 0 ? withTicker : "B" + String(i).padStart(5, "0"));
  return { day: new Date(now + KST).toISOString().slice(0, 10), tickers: t, opens: t.map((x, i) => ({ t: x, at: now - 30 * 60e3 + i * 1000 })), last: now - 60e3 };
};

async function open(path, { signedIn = false, init = {}, lang = "ko", width = 1280 } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: width < 500 ? 844 : 900 }, isMobile: width < 500, hasTouch: width < 500 });
  const fake = FAKE(signedIn);
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && fake[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: fake[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript(([uid, v, lg, pairs]) => {
    try {
      if (lg === "en") localStorage.setItem("kos-lang", "en");
      localStorage.setItem("__fakefs:users/" + uid, JSON.stringify({ consents: { age14: true, terms: true, privacy: true, version: v } }));
      if (!sessionStorage.getItem("__seeded")) { for (const [k, val] of pairs) localStorage.setItem(k, val); sessionStorage.setItem("__seeded", "1"); }
    } catch (e) {}
  }, [UID, CONSENT_VERSION, lang, Object.entries(init).map(([k, v]) => [k, JSON.stringify(v)])]);
  const page = await ctx.newPage();
  await page.goto(BASE + "/staging/" + path, { waitUntil: "load" });
  await page.waitForTimeout(900);
  return { page, close: () => ctx.close() };
}

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};
const norm = (s) => String(s || "").replace(/\s+/g, " ").trim();

/* ── ① 요금제 화면 ───────────────────────────────────────────── */
console.log("── ① 요금제 화면 ──");
ok("요금 설정(payment-config)은 멤버십 하나 · 월 14,900원", Object.keys(PLANS).join() === "member" && PRICE === SPEC_PRICE, Object.keys(PLANS).join());
ok("요금 설정에 환불 안내(REFUND_NOTICE)가 있다", !!block("REFUND_NOTICE"));
{
  const { page, close } = await open("pricing.html");
  const r = await page.evaluate(() => ({
    plans: [...document.querySelectorAll(".plan")].map((p) => ({ name: p.querySelector(".plan-name").textContent.trim(),
      price: p.querySelector(".plan-price").textContent.replace(/\s+/g, ""), feats: [...p.querySelectorAll(".plan-feats li")].map((l) => l.textContent),
      btns: [...p.querySelectorAll("[data-plan]")].map((b) => b.dataset.plan + ":" + b.textContent.trim()) })),
    heads: [...document.querySelectorAll(".cmp-t thead th")].map((t) => t.textContent.trim()),
    rows: [...document.querySelectorAll(".cmp-t tbody tr")].map((t) => t.querySelector("td").firstChild.textContent.trim()),
    cols: [...document.querySelectorAll(".cmp-t tbody tr")].map((t) => t.querySelectorAll("td").length),
    dlg: !!document.querySelector("#dlg, .dlg"),
    main: document.querySelector("main").innerText,
  }));
  ok("요금제는 두 단 — 무료 · 멤버십", r.plans.map((p) => p.name).join("|") === "무료|멤버십", r.plans.map((p) => p.name).join("|"));
  ok(`멤버십 가격은 '월 ${PRICE.toLocaleString("en-US")}원'`, r.plans[1] && r.plans[1].price === `월${PRICE.toLocaleString("en-US")}원`, r.plans[1] && r.plans[1].price);
  ok("구독 단추는 하나(member · '구독하기')", r.plans.flatMap((p) => p.btns).join("|") === "member:구독하기", r.plans.flatMap((p) => p.btns).join("|"));
  ok("멤버십 항목에 '열람 종목 수 제한 없음'", r.plans[1] && r.plans[1].feats.includes("열람 종목 수 제한 없음"), JSON.stringify(r.plans[1] && r.plans[1].feats));
  ok("표의 열은 무료 · 멤버십 둘", r.heads.join("|") === "리포트 섹션|무료|멤버십" && r.cols.every((n) => n === 3), r.heads.join("|"));
  ok("표에 하루 열람 한도 줄이 없다", !r.rows.some((x) => /열람 한도/.test(x)) && r.rows.length === 13, r.rows.join("|"));
  ok("요금제 변경 확인 창이 없다", !r.dlg);
  ok("BASIC · PRO · 하루 한도 · '2,500여' · '전 종목' 이 없다", !/BASIC|PRO|하루 열람 한도|하루 \d+개|2,500여|2,700여|전 종목|업그레이드/.test(r.main),
     (r.main.match(/.{0,20}(BASIC|PRO|하루 열람 한도|2,500여|전 종목|업그레이드).{0,20}/) || [""])[0]);

  /* ② 자주 묻는 질문 */
  console.log("\n── ② 자주 묻는 질문 ──");
  await page.evaluate(() => document.querySelectorAll("details.qa").forEach((d) => (d.open = true)));
  const q = await page.evaluate(() => {
    const qa = [...document.querySelectorAll("details.qa")];
    const find = (t) => qa.find((d) => d.querySelector("summary").textContent.trim() === t);
    const refund = find("환불 기준은 어떻게 되나요?"), lim = find("열람할 수 있는 리포트 수에 제한이 있나요?");
    const lines = (el) => (el ? [...el.querySelectorAll("p, li")].map((x) => x.textContent) : []);
    const ko = refund && refund.querySelector('[data-lang="ko"]'), en = refund && refund.querySelector('[data-lang="en"]');
    return { qs: qa.map((d) => d.querySelector("summary").textContent.trim()), ko: lines(ko), en: lines(en),
             koShown: !!ko && getComputedStyle(ko).display !== "none", enShown: !!en && getComputedStyle(en).display !== "none",
             lim: lim ? lim.querySelector(".a").textContent : "", tail: refund ? refund.querySelector(".a > p:last-child").textContent : "" };
  });
  ok("질문 목록 — 옛 셋(BASIC과 PRO · 플랜 변경 · 하루 열람 한도)을 빼고 열람 제한 질문을 넣었다",
     JSON.stringify(q.qs) === JSON.stringify(["열람할 수 있는 리포트 수에 제한이 있나요?", "구독은 언제든지 해지할 수 있나요?", "결제가 승인되지 않으면 어떻게 되나요?",
       "환불 기준은 어떻게 되나요?", "리포트는 어떤 주기로 갱신되나요?", "이용 가능한 결제 수단은 무엇인가요?", "구독하면 종목 추천을 받을 수 있나요?"]), JSON.stringify(q.qs));
  ok("열람 제한 답 — 제한 없음 · 자동 수집 제한 · 같은 종목 다시 열기",
     /종목 수에 제한이 없습니다/.test(q.lim) && /자동 수집/.test(q.lim) && /일시적으로 제한/.test(q.lim) && /다시 열람하시는 경우에도 제한 없이/.test(q.lim), q.lim);
  ok("환불 답이 명세의 환불 안내와 한 글자까지 같다", JSON.stringify(q.ko) === JSON.stringify(NOTICE), JSON.stringify(q.ko).slice(0, 300));
  ok("환불 답의 영어는 결제 화면 · 설정과 같은 글(payment-config)", JSON.stringify(q.en) === JSON.stringify([REFUND.en.lead, ...REFUND.en.steps, ...REFUND.en.notes]));
  ok("한국어 화면에서는 한국어 답만 보인다", q.koShown && !q.enShown, JSON.stringify([q.koShown, q.enShown]));
  ok("신청하는 곳을 함께 적는다", /설정의 구독 항목에서 직접/.test(q.tail), q.tail);
  await close();

  const e = await open("pricing.html", { lang: "en" });
  await e.page.evaluate(() => document.querySelectorAll("details.qa").forEach((d) => (d.open = true)));
  const shown = await e.page.evaluate(() => {
    const ko = document.querySelector('.refund-notice[data-lang="ko"]'), en = document.querySelector('.refund-notice[data-lang="en"]');
    const shown = (el) => !!el && getComputedStyle(el).display !== "none";
    return [shown(ko), shown(en)];
  });
  ok("영어 화면에서는 영어 답만 보인다", !shown[0] && shown[1], JSON.stringify(shown));
  await e.close();
}

/* ── ③ 구독 단추 ─────────────────────────────────────────────── */
console.log("\n── ③ 구독 단추 — 상태마다 이름과 가는 곳 ──");
for (const [label, opt, want, goes] of [
  ["로그아웃", {}, "구독하기", /Login\.html\?next=pricing\.html/],
  ["로그인 · 구독 없음", { signedIn: true }, "구독하기", /checkout\.html\?plan=member$/],
  ["이용 중", { signedIn: true, init: { "kos-demo-sub": demoSub(2) } }, "구독 관리하기", /billing\.html|Settings\.html/],
  ["결제 실패", { signedIn: true, init: { "kos-demo-sub": { ...demoSub(31), status: "past_due" } } }, "결제 수단 변경하기", /checkout\.html\?plan=member&method=1/],
]) {
  const { page, close } = await open("pricing.html", opt);
  const s = await page.evaluate(() => ({ btn: document.querySelector("[data-plan]").textContent.trim(),
    badge: (document.querySelector(".plan-badge.js") || {}).textContent || "", all: [...document.querySelectorAll("button, a")].map((b) => b.textContent.trim()) }));
  ok(`${label} — 단추 '${want}'`, s.btn === want, s.btn);
  if (label === "이용 중") ok("이용 중 — 배지 '이용 중'", s.badge === "이용 중", s.badge);
  ok(`${label} — 업그레이드 · 요금제 변경 단추가 없다`, !s.all.some((t) => /업그레이드|BASIC|PRO|변경 취소/.test(t)));
  await Promise.all([page.waitForURL(goes, { timeout: 5000 }).catch(() => {}), page.click("[data-plan]")]);
  ok(`${label} — 누르면 ${goes}`, goes.test(page.url()), page.url());
  await close();
}

/* ── ④ 결제 화면 ─────────────────────────────────────────────── */
console.log("\n── ④ 결제 화면 — 환불 안내가 결제 단추보다 위에 보인다 ──");
for (const width of [1280, 390]) {
  const { page, close } = await open("checkout.html?plan=member", { signedIn: true, width });
  const r = await page.evaluate(() => {
    const ref = document.getElementById("coRefund"), btn = document.getElementById("payBtn");
    if (!ref || !btn) return null;
    const a = ref.getBoundingClientRect(), b = btn.getBoundingClientRect(), cs = getComputedStyle(ref);
    return { lines: [...ref.querySelectorAll("p, li")].map((x) => x.textContent), h: a.height, refBottom: a.bottom + scrollY, btnTop: b.top + scrollY,
             visible: cs.display !== "none" && cs.visibility !== "hidden" && parseFloat(cs.opacity) > 0.5, font: parseFloat(cs.fontSize) };
  });
  ok(`${width}px — 환불 안내가 있다`, !!r, "coRefund 없음");
  if (!r) { await close(); continue; }
  ok(`${width}px — 글이 명세와 같다`, JSON.stringify(r.lines) === JSON.stringify(NOTICE));
  ok(`${width}px — 실제로 보인다(높이 ${Math.round(r.h)}px · 글자 ${r.font}px)`, r.visible && r.h > 100 && r.font >= 12);
  ok(`${width}px — 결제 단추보다 위`, r.refBottom <= r.btnTop, `${Math.round(r.refBottom)} · ${Math.round(r.btnTop)}`);
  await close();
}

/* ── ⑤ 리포트 잠금 카드 ─────────────────────────────────────── */
console.log("\n── ⑤ 리포트 잠금 카드 — 요금 · 자동 수집 제한 ──");
{
  const { page, close } = await open("stock.html?ticker=005930");
  await page.waitForSelector("#lockCard", { timeout: 15000 }).catch(() => {});
  const sub = await page.evaluate(() => (document.querySelector("#lockCard .lock-sub") || {}).textContent || "");
  ok(`잠금 카드의 요금 — '멤버십 월 ${PRICE.toLocaleString("en-US")}원'`, sub.endsWith(`멤버십 월 ${PRICE.toLocaleString("en-US")}원`) && !/BASIC|부터/.test(sub), sub);
  await close();
}
for (const lang of ["ko", "en"]) {
  const { page, close } = await open("stock.html?ticker=005930", { signedIn: true, lang, init: { "kos-demo-sub": demoSub(2), "kos-demo-reads": burstReads() } });
  await page.waitForFunction(() => { const h = document.querySelector("#lockCard h3"); return h && !/구독 회원|available to members/.test(h.textContent); }, null, { timeout: 15000 }).catch(() => {});
  const r = await page.evaluate(() => {
    const card = document.getElementById("lockCard");
    if (!card) return null;
    const vis = (el) => !!el && getComputedStyle(el).display !== "none" && el.getBoundingClientRect().width > 0;
    return { h3: card.querySelector("h3").textContent, sub: card.querySelector(".lock-sub").textContent,
             buy: vis(card.querySelector(".lock-cta .btn-ink")), btn: vis(document.getElementById("lockBtn")), btnText: document.getElementById("lockBtn").textContent };
  });
  const want = lang === "en" ? ["You opened too many reports in a short time, so viewing is paused for a while.", "Please try again shortly."] : BURST;
  ok(`${lang} — 61번째 새 종목이면 명세 문구로 바뀐다`, r && r.h3 === want[0] && r.sub === want[1], JSON.stringify(r));
  ok(`${lang} — '멤버십 보기' 는 숨고 '이어서 읽기' 는 남는다`, r && !r.buy && r.btn && r.btnText === (lang === "en" ? "Continue reading" : "이어서 읽기"), JSON.stringify(r));
  await close();
}
{
  /* 제한에 걸린 상태라도 오늘 이미 연 종목은 열린다(새로고침 · 다른 기기) */
  const { page, close } = await open("stock.html?ticker=005930", { signedIn: true, init: { "kos-demo-sub": demoSub(2), "kos-demo-reads": burstReads("005930") } });
  await page.waitForFunction(() => !document.getElementById("tz") && document.querySelector("#s04 .prose p"), null, { timeout: 15000 }).catch(() => {});
  const opened = await page.evaluate(() => !document.getElementById("tz") && !!document.querySelector("#s04 .prose p"));
  ok("오늘 이미 연 종목은 제한 중에도 열린다", opened);
  await close();
}

/* ── ⑥ 설정의 환불 확인 창 — 휴대폰 ──────────────────────────── */
console.log("\n── ⑥ 설정의 환불 확인 창(휴대폰 390px) ──");
{
  const { page, close } = await open("Settings.html?tab=subscription", { signedIn: true, width: 390, init: { "kos-demo-sub": demoSub(9) } });
  await page.click('.ks-btn:has-text("환불 신청하기")', { timeout: 5000 }).catch(() => {});
  await page.waitForSelector(".ks-dlg-card", { timeout: 5000 }).catch(() => {});
  const r = await page.evaluate(() => {
    const c = document.querySelector(".ks-dlg-card");
    if (!c) return null;
    const t = c.querySelector(".ks-dlg-t").getBoundingClientRect(), box = c.getBoundingClientRect();
    return { titleTop: t.top, titleBottom: t.bottom, inner: innerHeight, boxW: box.width, vw: innerWidth, scroll: getComputedStyle(c).overflowY,
             kv: [...c.querySelectorAll(".ks-dlg-kv dt")].map((d) => d.textContent), notice: !!c.querySelector(".ks-dlg-n ol li"),
             btns: [...c.querySelectorAll("button")].map((b) => b.textContent.trim()) };
  });
  ok("확인 창이 열린다", !!r);
  if (r) {
    ok("제목이 화면 안에 있다", r.titleTop >= 0 && r.titleBottom <= r.inner, JSON.stringify(r));
    ok("창이 화면 폭을 넘지 않는다", r.boxW <= r.vw, `${r.boxW} · ${r.vw}`);
    ok("긴 내용은 창 안에서 스크롤된다", r.scroll === "auto" || r.scroll === "scroll", r.scroll);
    ok("계산 내역 다섯 줄", r.kv.join("|") === "결제금액|이용일수|이용료|위약금|환불 금액", r.kv.join("|"));
    ok("환불 기준이 실린다", r.notice);
    ok("단추는 '닫기' · '환불 신청하기'", r.btns.join("|") === "닫기|환불 신청하기", r.btns.join("|"));
  }
  await close();
}

await browser.close(); server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
