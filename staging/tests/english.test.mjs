/* ============================================================
   영어 화면에 한국어가 남지 않는다 — 스테이징 · 실사이트 전 페이지 (2026-10-03)

   왜 있는가. 9월 26일 스테이징을 새 디자인으로 옮기면서 번역(KOSi18n)이
   통째로 빠졌고, 설정 화면의 '언어' 줄까지 사라졌는데 아무도 몰랐다.
   사장이 "왜 언어 설정이 없냐"고 물어서 알았다. 한국어로 보면 멀쩡하니
   눈으로는 안 걸린다 — 그래서 영어로 열어 본다.

   보는 것
     · 페이지마다 영어(localStorage kos-lang=en)로 열고, 로그인 전 · 후와
       자주 하는 동작(메뉴 · 검색 · 탭 · 질문 펼치기)을 거친 뒤
       body 의 모든 글 조각 · placeholder · aria-label · title · alt ·
       문서 제목에 한글이 남았는지.
     · 숨겨 둔 글(오류 문구 · 메뉴)도 본다 — 나타나는 순간 한국어면 안 된다.
     · 영문명이 없는 종목(자료에 name_en 이 빈 종목)의 이름은 예외.
     · 두 말로 미리 그려 둔 곳의 한국어 쪽(data-lang="ko")은 예외.
     · 언어를 고르는 줄의 '한국어' 는 예외(언어 이름은 그 말로 쓴다).
     · 두 사이트를 같은 장면으로 본다. 실사이트(루트)도 2026-10-03 부터 같은 생성기
       (scripts/build_live.py)가 만든 새 디자인이고 번역 엔진(i18n.js)과 사전도 같은
       방식으로 싣는다. 멤버십 장면(요금제 · 결제 · 설정의 구독 칸)은 실사이트에 없어
       실사이트에서만 뺀다.

   실행
     node staging/tests/english.test.mjs           # 실패하면 남은 한국어를 페이지별로 보여 준다
     LIST=파일 node staging/tests/english.test.mjs # 남은 문구를 JSON 으로(번역 작업용)
     ONLY=실사이트 node staging/tests/english.test.mjs   # 이름이 맞는 장면만(정규식)
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { readFileSync, existsSync, readdirSync, writeFileSync } from "node:fs";
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

const CONSENT_VERSION = readFileSync(join(ROOT, "staging/consent.js"), "utf8").match(/CONSENT_VERSION\s*=\s*"([^"]+)"/)[1];
const UID = "u-en-test";
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
    function tell(p){ (subs[p] || []).forEach((f) => setTimeout(() => f(snap(p)), 0)); }
    function write(p, v){ localStorage.setItem(K(p), JSON.stringify(v)); tell(p); }
    export function getFirestore(){ return {}; } export function initializeFirestore(){ return {}; }
    export function doc(db, ...parts){ return { path: parts.join("/") }; }
    export function collection(db, ...parts){ return { path: parts.join("/") }; }
    export function deleteField(){ return DEL; } export function serverTimestamp(){ return Date.now(); }
    export function onSnapshot(ref, next){ const f = (s) => next(s); (subs[ref.path] = subs[ref.path] || []).push(f); setTimeout(() => f(snap(ref.path)), 20); return () => {}; }
    export async function getDoc(ref){ return snap(ref.path); }
    export async function setDoc(ref, data){ write(ref.path, Object.assign(read(ref.path) || {}, data)); }
    export async function updateDoc(ref, data){ write(ref.path, Object.assign(read(ref.path) || {}, data)); }
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
const MISSING = new Set();   // 리포트 파일을 없는 척할 종목(준비 중 화면)
const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const m = rel.match(/data\/reports(?:_v2)?\/([0-9A-Z]{6})\.json$/);
    if (m && MISSING.has(m[1])) { res.writeHead(404); res.end("no"); return; }
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: CHROME });

/* 영문명이 없는 종목 — 이름은 한국어 그대로 둔다(번역할 근거가 없다) */
const LIVE = JSON.parse((s => s.slice(s.indexOf("{"), s.lastIndexOf("}") + 1))(readFileSync(join(ROOT, "data/stocks.js"), "utf8")));
const NO_EN = LIVE.stocks.filter((s) => !s.name_en).map((s) => s.name);
const PENDING = "0220W0";   // 준비 중 화면은 이 종목의 리포트 파일을 없는 척해서 본다

async function scan(path, { signedIn = false, act = null, width = 1280 } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 } });
  const fake = FAKE(signedIn);
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && fake[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: fake[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript(([uid, v]) => {
    try {
      localStorage.setItem("kos-lang", "en");
      localStorage.setItem("__fakefs:users/" + uid, JSON.stringify({ consents: { age14: true, terms: true, privacy: true, version: v } }));
    } catch (e) {}
  }, [UID, CONSENT_VERSION]);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e.message || e)));
  await page.goto(BASE + path, { waitUntil: "load" });
  await page.waitForTimeout(1200);
  if (act) { try { await act(page); } catch (e) { errors.push("동작 실패: " + e.message); } await page.waitForTimeout(500); }
  const left = await page.evaluate((NO_EN) => {
    const HAN = /[가-힣]/;
    const strip = (s) => { for (const n of NO_EN) s = s.split(n).join(""); return s; };
    const out = new Map();
    const note = (text, where) => { const t = text.replace(/\s+/g, " ").trim(); if (!t || !HAN.test(strip(t))) return; if (!out.has(t)) out.set(t, where); };
    const where = (el) => { const p = []; for (let e = el; e && e.nodeType === 1 && p.length < 3; e = e.parentElement) p.unshift(e.tagName.toLowerCase() + (e.id ? "#" + e.id : "") + (e.classList[0] ? "." + e.classList[0] : "")); return p.join(">"); };
    const skip = (el) => el.closest('script,style,noscript,template,[data-lang="ko"]');
    const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      const el = n.parentElement; if (!el || skip(el)) continue;
      if (el.closest(".ks-seg") && n.nodeValue.trim() === "한국어") continue;   // 언어 고르는 줄
      note(n.nodeValue, where(el));
    }
    for (const el of document.body.querySelectorAll("[placeholder],[aria-label],[title],[alt]")) {
      if (skip(el)) continue;
      for (const a of ["placeholder", "aria-label", "title", "alt"]) { const v = el.getAttribute(a); if (v) note(v, where(el) + "@" + a); }
    }
    note(document.title, "title");
    return [...out.entries()];
  }, NO_EN);
  const lang = await page.evaluate(() => [document.documentElement.lang, !!window.KOSi18n, window.KOSi18n && window.KOSi18n.lang]);
  await ctx.close();
  return { left, errors, lang };
}

const clickAll = (sel) => async (page) => { for (const h of await page.$$(sel)) { try { await h.click({ timeout: 800 }); } catch (e) {} } };
const typeIn = (sel, text) => async (page) => { await page.click(sel); await page.keyboard.type(text, { delay: 20 }); await page.waitForTimeout(500); };
const seq = (...fs) => async (page) => { for (const f of fs) await f(page); };
const openMenu = async (page) => { await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(200); const b = await page.$("#menuBtn"); if (b && await b.isVisible()) await b.click(); };
const openDetails = async (page) => page.evaluate(() => document.querySelectorAll("details").forEach((d) => (d.open = true)));
const scrollAll = async (page) => { for (let y = 0; y < 12000; y += 700) { await page.evaluate((y) => scrollTo(0, y), y); await page.waitForTimeout(120); } };

/* 장면 — [이름, 사이트 안 주소, { signedIn 로그인 · act 동작 · pending 준비 중 · paid 멤버십 장면 }].
   paid 장면(요금제 · 결제 · 설정의 구독 칸)은 실사이트에 없어 스테이징에서만 돈다. */
const SCENES = [
  ["첫 화면(랜딩)", "/", { act: seq(scrollAll, typeIn("#q, input[type=search], .search input", "sam")) }],
  ["첫 화면 — 휴대폰 메뉴", "/", { act: openMenu }],
  ["홈", "/Home.html", { act: typeIn("input[type=search], .search input, #q", "sam") }],
  /* 계정 메뉴를 연 화면 — 메뉴를 여는 단추(#acctBtn)만 누른다. 메뉴 안의 단추를 다 누르면 '로그아웃'까지 눌려 페이지가 새로
     열리고, 컴퓨터가 바쁠 때는 덜 그려진 새 페이지를 검사해 걸렸다(2026-10-03). 메뉴를 연 채로 보는 것이 이 장면의 뜻이다. */
  ["홈 — 로그인", "/Home.html", { signedIn: true, act: clickAll("#acctBtn, .acct-btn") }],
  ["리포트 목록", "/Reports.html", { act: clickAll(".flt button, .filters button, [data-sort], .sort button") }],
  ["리포트 목록 — 검색 결과 없음", "/Reports.html", { act: typeIn("input[type=search], .search input, #q", "zzzzzz") }],
  ["업종 분석", "/industry.html", {}],
  ["업종 분석 — 업종 하나", "/industry.html?sector=%EB%B0%98%EB%8F%84%EC%B2%B4", {}],
  ["관심종목 — 로그아웃", "/Watchlist.html", {}],
  ["관심종목 — 로그인(비어 있음)", "/Watchlist.html", { signedIn: true }],
  ["모닝브리핑", "/brief.html", {}],
  ["회사 소개", "/About.html", {}],
  ["문의하기", "/Contact.html", { act: clickAll("button[type=submit]") }],
  ["피드백", "/Feedback.html", { act: clickAll("button[type=submit]") }],
  ["이용약관", "/Terms.html", {}],
  ["개인정보 처리방침", "/Privacy.html", {}],
  ["로그인", "/Login.html", { act: clickAll("button[type=submit]") }],
  ["회원가입", "/Signup.html", { act: clickAll("button[type=submit]") }],
  ["약관 동의", "/Consent.html", { signedIn: true }],
  ["계정 인증 — 비밀번호 재설정", "/auth-action.html?mode=resetPassword&oobCode=x", {}],
  ["계정 인증 — 이메일 확인", "/auth-action.html?mode=verifyEmail&oobCode=x", {}],
  ["멤버십 — 로그아웃", "/pricing.html", { act: openDetails, paid: true }],
  ["멤버십 — 로그인", "/pricing.html", { signedIn: true, act: openDetails, paid: true }],
  ["결제", "/checkout.html?plan=basic", { signedIn: true, paid: true }],
  ["설정 — 로그아웃", "/Settings.html", {}],
  ["설정 — 일반", "/Settings.html?tab=general", { signedIn: true }],
  ["설정 — 알림", "/Settings.html?tab=notifications", { signedIn: true }],
  ["설정 — 구독", "/Settings.html?tab=subscription", { signedIn: true, paid: true }],
  ["설정 — 계정", "/Settings.html?tab=account", { signedIn: true }],
  ["리포트 상세 — 새 형식", "/stock.html?ticker=005930", { act: openDetails }],
  ["리포트 상세 — 새 형식(로그인)", "/stock.html?ticker=005930", { signedIn: true, act: openDetails }],
  ["리포트 상세 — 옛 형식", "/stock.html?ticker=0001A0", { act: openDetails }],
  ["리포트 상세 — 준비 중", `/stock.html?ticker=${PENDING}`, { pending: true }],
  ["리포트 상세 — 없는 종목", "/stock.html?ticker=999999", {}],
];
const SITES = [["스테이징", "/staging"], ["실사이트", ""]];
const CASES = SITES.flatMap(([site, pre]) => SCENES.filter(([, , opt]) => !(opt.paid && !pre))
  .map(([name, path, opt]) => [`${site} · ${name}`, pre + path, opt]));

const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;
const report = {};
let fail = 0, pass = 0;
for (const [name, path, opt] of CASES) {
  if (only && !only.test(name)) continue;
  if (opt.pending) MISSING.add(PENDING); else MISSING.clear();
  const r = await scan(path, opt);
  const bad = r.left.length || !r.lang[1] || r.lang[0] !== "en";
  if (bad) { fail++; report[name] = r.left; console.log(`FAIL  ${name} — 남은 한국어 ${r.left.length}개` + (!r.lang[1] ? " · 번역 엔진 없음" : "") + (r.lang[0] !== "en" ? ` · html lang=${r.lang[0]}` : "")); if (!process.env.LIST) r.left.slice(0, 12).forEach(([t, w]) => console.log(`        ${t.slice(0, 90)}   ← ${w}`)); }
  else { pass++; console.log(`PASS  ${name}`); }
  if (r.errors.length && process.env.VERBOSE) console.log("        스크립트 오류: " + r.errors.slice(0, 3).join(" | "));
}
/* 설정에서 말을 바꿨다가 되돌린다 — 한국어로 연 화면 → 'English' → 'Korean'. 영어 화면에 한글이 없고(언어 줄의 '한국어' 빼고),
   되돌린 화면이 처음 한국어 화면과 글자 하나까지 같아야 한다. 스크립트가 그린 설정 칸이 영어로 남던 자리다 */
async function roundTrip(pre) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const fake = FAKE(true);
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && fake[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: fake[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript(([uid, v]) => {
    try { localStorage.setItem("__fakefs:users/" + uid, JSON.stringify({ consents: { age14: true, terms: true, privacy: true, version: v } })); } catch (e) {}
  }, [UID, CONSENT_VERSION]);
  const page = await ctx.newPage();
  const text = () => page.evaluate(() => document.body.innerText + "\n" + document.title);
  const pick = async (label) => {   // 말을 바꾸면 페이지를 다시 연다 — 표시가 사라지고 다 열릴 때까지 기다린다
    await page.evaluate(() => { window.__mark = 1; });
    await page.click(`.ks-seg button:has-text("${label}")`);
    let ok = false;
    for (let i = 0; i < 50 && !ok; i++) {
      await page.waitForTimeout(200);
      try { ok = await page.evaluate(() => !window.__mark && document.readyState === "complete"); } catch (e) {}
    }
    if (!ok) throw new Error(`'${label}' 을 눌러도 페이지가 다시 열리지 않았습니다`);
    await page.waitForTimeout(1200);
  };
  const out = [];
  try {
    await page.goto(BASE + pre + "/Settings.html?tab=general", { waitUntil: "load" });
    await page.waitForTimeout(1200);
    const ko0 = await text();
    if (!(await page.$('.ks-seg button:has-text("English")'))) out.push("설정에 언어 줄이 없습니다");
    else {
      await pick("English");
      const en = await page.evaluate(() => [document.documentElement.lang, localStorage.getItem("kos-lang"), document.body.innerText.replace(/한국어/g, "")]);
      if (en[0] !== "en" || en[1] !== "en") out.push(`영어로 바뀌지 않았습니다(lang=${en[0]}, 저장=${en[1]})`);
      const han = (en[2].match(/[^\n]*[가-힣][^\n]*/g) || []).slice(0, 5);
      if (han.length) out.push("영어 화면에 남은 한국어: " + han.join(" | "));
      await pick("Korean");   // 영어 화면에서는 언어 이름도 영어다(실사이트와 같다)
      const ko1 = await text();
      if (ko1 !== ko0) out.push("되돌린 한국어 화면이 처음과 다릅니다");
    }
  } catch (e) { out.push("동작 실패: " + e.message); }
  await ctx.close();
  return out;
}
for (const [site, pre] of SITES) {
  const name = `${site} · 설정 — 언어 바꾸고 되돌리기`;
  if (only && !only.test(name)) continue;
  const rt = await roundTrip(pre);
  if (rt.length) { fail++; console.log("FAIL  " + name); rt.forEach((m) => console.log("        " + m.slice(0, 200))); }
  else { pass++; console.log("PASS  " + name); }
}
if (process.env.LIST) writeFileSync(process.env.LIST, JSON.stringify(report, null, 1));
await browser.close(); server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
