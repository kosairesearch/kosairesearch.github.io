/* ============================================================
   리포트 열람 방법 변경 — 실적 분석 ~ 종합 의견은 로그인한 회원에게(무료 · 2026-11-26 공고 · 2026-12-03 0시 시행)

   왜 있나
     사장 "회원가입 후 리포트 열람할 수 있도록 하는 거는 최대한 빨리 … 7일 뒤에 바로 시행할 수 있게"(2026-11-26).
     잠금은 시행 시각(comp_common.ACCESS_GATE_AT)이 지나면 브라우저와 미리 그리기(노드)가 같은 시계로 스스로 켠다 — 시행일에
     사람 손이 닿지 않아도 0시에 시행된다. 잠근 절의 글은 페이지에 넣지 않는다 — 앞 문단 미리보기와 로그인 카드만 둔다
     (글을 넣고 화면에서만 가리면 검색 엔진이 숨긴 글로 볼 소지가 있다). 로그인 여부는 auth-state.js 가 알린다
     (window.KOS_SIGNED · kos-auth 이벤트) — 알리기 전에는 기억 값(kos-signed)으로 먼저 그린다.

   보는 것
     ① 잠금을 켠 판(임시 폴더에 다시 만든다 · ACCESS_GATE) — 자바스크립트 없이: 무료 구간(개요 · 사업 구조 · 실적 추이 · 참고 출처)이
        있고, 잠근 절의 글(산업 분석 · 전망 · 밸류에이션 · 강세 요인 · 리스크 · 체크포인트 · 종합 의견)이 페이지 소스에 없다. 미리보기
        (실적 분석 앞 문단)와 로그인 카드, 가입 · 로그인 링크가 맨 위 주소이고 돌아올 곳이 이 페이지, 목차의 04~12 에 자물쇠, 구조화
        데이터 isAccessibleForFree false, 시행 전 안내 한 줄 없음. 영어 페이지도 같다. 공용 파일에 실사이트 금지 낱말이 없다
     ② 로그인하지 않은 사람 — 본문을 다시 넣지 않는다(지문이 같다) · 카드가 보이고 옷(단추 줄 · 옅어지는 미리보기)이 입혀져 있다
     ③ 로그인한 사람 — 잠근 절이 모두 그려지고 카드가 없다 · 구조화 데이터 true · 로그인 알림 뒤에 한 번 더 그리지 않는다.
        기억 값이 없는 기기에서도 로그인 알림이 오면 열린다
     ④ 기억 값만 남고 실제로는 로그아웃된 사람(세션 만료) — 로그아웃 알림에 잠그고 기억 값을 지운다
     ⑤ 같은 페이지에서 로그인 · 로그아웃 — 새로 고치지 않아도 열리고 다시 잠긴다. 같은 상태 알림에는 다시 그리지 않는다
     ⑥ 옛 형식 리포트(공시 재무가 없는 기본 형식)는 잠그지 않는다
     ⑦ 영어 — 영어 페이지 · 한국어 페이지를 영어로 정한 사람 모두 카드가 영어이고 화면에 한글이 없다
     ⑧ 목차 · 휴대폰 목차 띠의 잠긴 항목을 누르면 카드 자리로 간다
     ⑨ 휴대폰(390) · 컴퓨터(1280) — 가로로 넘치지 않고, 카드 단추가 화면 안에서 서로 겹치지 않는다
     ⑩ 지금 저장소의 페이지 — 시계를 시행 시각 앞으로 돌리면 잠그지 않고 안내 한 줄이 실적 분석 앞에 있다. 시행 시각 뒤로 돌리면
        (시행 뒤 첫 종목 페이지 생성 전의 몇 시간) 로그인하지 않은 사람은 잠기고 안내 한 줄이 걷히며 카드에 옷이 입혀져 있고,
        로그인한 사람은 열린다. 시행일 정리(ACCESS_GATE 켬) 뒤에는 시계와 관계없이 잠근다

   실행
     node staging/tests/access-gate.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
const V2 = "005930", V1 = "417030";   // 새 형식(실적 표가 있는) 리포트 · 옛 형식(기본 형식)만 있는 종목
const FORBIDDEN = ["lockCard", "KOSPaywall", "paywall=", "pricing.html", "checkout.js", "demo-backend"];   // build_live.FORBIDDEN 가운데 잠금과 닿는 것

if (!existsSync(join(ROOT, `stock/${V2}.html`)) || !existsSync(join(ROOT, `stock/${V1}.html`))) {
  console.error("stock/ 가 없습니다 — python3 scripts/build_stock_static.py"); process.exit(1);
}

// ── 잠금을 켠 판을 임시 폴더에 만든다(저장소는 건드리지 않는다) ──────────────────────
const TMP = mkdtempSync(join(tmpdir(), "kos-gate-"));
const PY = `
import sys
from pathlib import Path
sys.path.insert(0, 'scripts')
import comp_common as C
C.ACCESS_GATE = True
import build_stock_static as BS
out = Path(sys.argv[1])
BS.OUT = out / 'stock'
BS.OUT_EN = out / 'en' / 'stock'
BS.build(sys.argv[2:])
`;
try { execFileSync("python3", ["-c", PY, TMP, V2, V1], { cwd: ROOT, stdio: "pipe" }); }
catch (e) { console.error("잠근 판을 만들지 못했다:", String(e.stderr || e).slice(0, 800)); rmSync(TMP, { recursive: true, force: true }); process.exit(1); }

let SERVE = "gated";   // gated — /stock/ · /en/stock/ 를 임시 폴더에서, repo — 저장소 그대로
const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    let file = join(ROOT, rel);
    if (SERVE === "gated" && /^\/(en\/)?stock\//.test(rel) && existsSync(join(TMP, rel))) file = join(TMP, rel);
    const body = await readFile(file);
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title><p>없는 페이지"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

// ── 파이어베이스 — 로그인하지 않은 사람 · 로그인한 사람 ──────────────────────────
const UID = "gate-test-uid";
const CONSENT_VERSION = readFileSync(join(ROOT, "staging/consent.js"), "utf8").match(/CONSENT_VERSION\s*=\s*"([^"]+)"/)[1];
const authModule = (signed) => `
  const U = ${signed ? `{ uid: ${JSON.stringify(UID)}, email: "t@example.com", displayName: "시험", emailVerified: true,
    providerData: [{ providerId: "google.com" }], getIdToken: async () => "t", reload: async () => {} }` : "null"};
  const A = { currentUser: U };
  export function getAuth(){ return A; }
  export function onAuthStateChanged(a, cb){ setTimeout(() => cb(U), 0); return () => {}; }
  export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
  const no = async () => ({});
  export const applyActionCode = no, confirmPasswordReset = no, createUserWithEmailAndPassword = no, deleteUser = no,
    signInWithCustomToken = no, signInWithEmailAndPassword = no, signInWithPopup = no, signOut = no, verifyPasswordResetCode = no,
    sendEmailVerification = no, sendPasswordResetEmail = no;
  export function getAdditionalUserInfo(){ return null; }`;
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-firestore": `
    const K = (p) => "__fakefs:" + p, DEL = { del: 1 };
    function read(p){ try { return JSON.parse(localStorage.getItem(K(p)) || "null"); } catch (e) { return null; } }
    function snap(p){ const d = read(p); return { exists: () => d != null, data: () => d, metadata: { fromCache: false, hasPendingWrites: false } }; }
    export function getFirestore(){ return {}; }
    export function doc(db, ...parts){ return { path: parts.join("/") }; }
    export function deleteField(){ return DEL; }
    export function onSnapshot(ref, next){ const t = setTimeout(() => next(snap(ref.path)), 20); return () => clearTimeout(t); }
    export async function getDoc(ref){ return snap(ref.path); }
    export async function setDoc(ref, data){ localStorage.setItem(K(ref.path), JSON.stringify(Object.assign(read(ref.path) || {}, data))); }
    export async function updateDoc(ref, data){ localStorage.setItem(K(ref.path), JSON.stringify(Object.assign(read(ref.path) || {}, data))); }
    export async function deleteDoc(ref){ localStorage.removeItem(K(ref.path)); }`,
  "firebase-functions": `export function getFunctions(){ return {}; } export function httpsCallable(){ return async () => ({ data: {} }); }`,
};

let pass = 0, fail = 0;
const ok = (cond, name, extra = "") => {
  if (cond) { pass++; console.log(`  ✅ ${name}`); } else { fail++; console.log(`  ❌ ${name}${extra ? "  — " + extra : ""}`); }
};

const browser = await chromium.launch({ executablePath: CHROME });
/* signed — 파이어베이스가 사용자를 알려 준다 · remember — 기억 값(kos-signed) · lang — 저장된 말 · at — 시계(밀리초) */
async function ctxOf({ signed = false, remember = false, lang = null, at = null, width = 1280, js = true } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, javaScriptEnabled: js });
  const fake = Object.assign({ "firebase-auth": authModule(signed) }, FAKE);
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && fake[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: fake[m[1]] });
    return route.abort();
  });
  if (js) {
    await ctx.addInitScript(({ uid, ver, remember, signed, lang, at }) => {
      try {
        if (!window.__kosSeeded) {
          window.__kosSeeded = 1;
          if (remember && sessionStorage.getItem("__seeded") !== "1") { localStorage.setItem("kos-signed", "1"); localStorage.setItem("kos-signed-user", "t@example.com"); }
          sessionStorage.setItem("__seeded", "1");
          if (signed) localStorage.setItem("__fakefs:users/" + uid, JSON.stringify({ consents: { age14: true, terms: true, privacy: true, version: ver } }));
          if (lang) localStorage.setItem("kos-lang", lang);
        }
      } catch (e) {}
      if (at != null) { const real = Date.now.bind(Date), off = at - real(); Date.now = () => real() + off; }
      /* 본문 자리에 글을 넣는 순간을 센다 — 지문이 같으면 다시 넣지 않아야 한다 */
      window.__swaps = 0;
      const d = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
      Object.defineProperty(Element.prototype, "innerHTML", { configurable: true, get() { return d.get.call(this); },
        set(v) { if (this.id === "page") window.__swaps++; d.set.call(this, v); } });
    }, { uid: UID, ver: CONSENT_VERSION, remember, signed, lang, at });
  }
  return ctx;
}
async function open(ctx, path) {
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(BASE + path);
  await page.waitForFunction(() => { const m = document.getElementById("page"); return m && m.hasAttribute("data-tier"); }, null, { timeout: 20000 });
  await page.waitForFunction(() => typeof window.KOS_SIGNED === "boolean", null, { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(300);
  return { page, errors };
}
/* 화면 요약 — 절 · 카드 · 링크 · 안내 한 줄 · 자물쇠 · 구조화 데이터 · 로그인 상태 · 옷 */
const state = (page) => page.evaluate(() => {
  const pg = document.getElementById("page");
  const card = document.getElementById("gateCard");
  let ld = null; try { ld = JSON.parse(document.getElementById("kos-jsonld").textContent); } catch (e) {}
  const fade = document.querySelector(".tz-fade"), cs = fade ? getComputedStyle(fade) : null;
  const note = document.querySelector(".access-note"), s04 = document.getElementById("s04");
  return {
    secs: [...pg.querySelectorAll("section.sec")].map((e) => e.id).join(","),
    card: !!card, cardH: card ? card.getBoundingClientRect().height : 0,
    h3: card ? card.querySelector("h3").textContent : "",
    cta: card ? [...card.querySelectorAll(".lock-cta a")].map((a) => a.getAttribute("href")) : [],
    ctaFlex: card ? getComputedStyle(card.querySelector(".lock-cta")).display : "",
    mask: cs ? String(cs.maskImage || cs.webkitMaskImage || "") : "",
    note: !!note, noteFirst: !!(note && s04 && (note.compareDocumentPosition(s04) & Node.DOCUMENT_POSITION_FOLLOWING)),
    locks: document.querySelectorAll("#toc a[data-lock]").length,
    free: ld ? ld.isAccessibleForFree : null,
    signed: window.KOS_SIGNED, remembered: localStorage.getItem("kos-signed"),
    swaps: window.__swaps, pre: pg.getAttribute("data-pre"),
    text: pg.innerText,
  };
});

// ── 잠근 절의 글(리포트 자료에서) — 이것이 잠근 판의 소스 · 화면에 있으면 안 된다 ──────────
const rep = JSON.parse(readFileSync(join(ROOT, `data/reports_v2/${V2}.json`), "utf8"));
const pick = (v, l) => (v && typeof v === "object" ? v[l] : (l === "ko" ? v : "")) || "";
const head = (s, n = 24) => String(s).replace(/\s+/g, " ").trim().slice(0, n);
const lockedText = (l) => [
  ["산업 분석", head(pick(rep.industry, l))], ["전망", head(pick(rep.outlook, l))], ["밸류에이션", head(pick(rep.valuation_comment, l))],
  ["강세 요인 제목", head(pick(rep.bull[0].title, l), 16)], ["약세 요인 제목", head(pick(rep.bear[0].title, l), 16)],
  ["리스크 본문", head(pick(rep.risks[0].body, l))], ["체크포인트", head(pick(rep.checkpoints[0].what, l), 18)],
  ["종합 의견", head(pick(rep.verdict && rep.verdict.body, l))],
].filter(([, t]) => t.length >= 10);
const leadText = (l) => head(pick(rep.earnings, l), 18);
const unesc = (h) => h.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&").replace(/\s+/g, " ");
const SIGNUP = (p) => "/Signup.html?next=" + encodeURIComponent(p), LOGIN = (p) => "/Login.html?next=" + encodeURIComponent(p);
const FREE_SECS = "s01,s02,s03,s13", ALL_SECS = Array.from({ length: 13 }, (_, i) => "s" + String(i + 1).padStart(2, "0")).join(",");

try {
  console.log("① 잠금을 켠 판 — 자바스크립트 없이(페이지 소스)");
  {
    const ctx = await ctxOf({ js: false });
    for (const [path, l, self] of [[`/stock/${V2}.html`, "ko", `stock/${V2}.html`], [`/en/stock/${V2}.html`, "en", `en/stock/${V2}.html`]]) {
      const src = unesc(await (await ctx.request.get(BASE + path)).text());
      const page = await ctx.newPage();
      await page.goto(BASE + path);
      const s = await state(page);
      ok(s.secs === FREE_SECS, `${path} — 무료 구간(개요 · 사업 구조 · 실적 추이 · 참고 출처)만 절로 있다`, s.secs);
      const leaked = lockedText(l).filter(([, t]) => src.includes(t)).map(([k]) => k);
      ok(leaked.length === 0, `${path} — 잠근 절의 글이 페이지 소스에 없다`, leaked.join(" · "));
      ok(src.includes(leadText(l)), `${path} — 미리보기(실적 분석 앞 문단)는 있다`);
      ok(s.card && s.cta[0] === SIGNUP(self) && s.cta[1] === LOGIN(self), `${path} — 로그인 카드 · 가입과 로그인 링크(돌아올 곳 ${self})`, s.cta.join(" , "));
      ok(s.locks === 9, `${path} — 목차의 04~12 에 자물쇠`, String(s.locks));
      ok(s.free === false, `${path} — 구조화 데이터 isAccessibleForFree false`, String(s.free));
      ok(!s.note, `${path} — 시행 전 안내 한 줄이 없다`);
      ok(/^[0-9a-f]{8}$/.test(s.pre || ""), `${path} — 미리 그린 표시(data-pre)가 있다`);
      if (l === "en") {
        ok(s.h3 === "The full report is available to signed-in members", "영어 페이지 — 카드가 영어", s.h3);
        ok(!/[가-힣]/.test(s.text), "영어 페이지 — 본문에 한글이 없다", (s.text.match(/[가-힣]+/g) || []).slice(0, 5).join(" "));
      }
      await page.close();
    }
    const js = readFileSync(join(TMP, "stock/assets/stock.js"), "utf8");
    ok(/var GATE=true, GATE_AT=null;/.test(js), "공용 스크립트 — 잠금이 켜져 있다(GATE=true)");
    ok(FORBIDDEN.every((w) => !js.includes(w)), "공용 스크립트 — 실사이트 금지 낱말이 없다", FORBIDDEN.filter((w) => js.includes(w)).join(" · "));
    const css = readFileSync(join(TMP, "stock/assets/stock.css"), "utf8");
    ok(css.includes(".tz-fade{") && css.includes(".lock-cta{"), "공용 옷 — 미리보기 · 잠금 카드의 옷이 있다");
    await ctx.close();
  }

  console.log("\n② 로그인하지 않은 사람");
  {
    const ctx = await ctxOf();
    const { page, errors } = await open(ctx, `/stock/${V2}.html`);
    const s = await state(page);
    ok(s.signed === false, "로그인 상태 알림(KOS_SIGNED false)", String(s.signed));
    ok(s.swaps === 0 && s.pre === null, "본문을 다시 넣지 않았다(미리 그린 글 = 화면 스크립트의 글)", `${s.swaps}번`);
    ok(s.card && s.cardH > 100, "카드가 보인다", String(s.cardH));
    ok(s.ctaFlex === "flex" && /gradient/.test(s.mask), "카드 · 미리보기에 옷이 입혀져 있다(단추 줄 · 옅어지는 미리보기)", `${s.ctaFlex} · ${s.mask.slice(0, 30)}`);
    const leaked = lockedText("ko").filter(([, t]) => s.text.includes(t)).map(([k]) => k);
    ok(leaked.length === 0, "잠근 절의 글이 화면에 없다", leaked.join(" · "));
    ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n③ 로그인한 사람");
  for (const remember of [true, false]) {
    const ctx = await ctxOf({ signed: true, remember });
    const { page, errors } = await open(ctx, `/stock/${V2}.html`);
    const s = await state(page);
    const tag = remember ? "기억 값이 있는 기기" : "기억 값이 없는 기기(로그인 알림으로 연다)";
    ok(s.signed === true, `${tag} — 로그인 상태 알림(KOS_SIGNED true)`, String(s.signed));
    ok(s.secs === ALL_SECS && !s.card && s.locks === 0, `${tag} — 잠근 절이 모두 그려지고 카드 · 자물쇠가 없다`, s.secs);
    ok(lockedText("ko").every(([, t]) => s.text.includes(t)), `${tag} — 잠근 절의 글이 화면에 있다`);
    ok(s.free === true, `${tag} — 구조화 데이터 isAccessibleForFree true`, String(s.free));
    if (remember) ok(s.swaps === 1, "기억 값이 있는 기기 — 한 번만 그렸다(로그인 알림 뒤에 다시 그리지 않는다)", `${s.swaps}번`);
    ok(errors.length === 0, `${tag} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n④ 기억 값만 남고 로그아웃된 사람(세션 만료)");
  {
    const ctx = await ctxOf({ remember: true });
    const { page, errors } = await open(ctx, `/stock/${V2}.html`);
    const s = await state(page);
    ok(s.signed === false && s.card && s.secs === FREE_SECS, "로그아웃 알림에 잠근다", s.secs);
    ok(s.remembered === null, "기억 값(kos-signed)을 지웠다", String(s.remembered));
    ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n⑤ 같은 페이지에서 로그인 · 로그아웃");
  {
    const ctx = await ctxOf();
    const { page, errors } = await open(ctx, `/stock/${V2}.html`);
    const tell = (v) => page.evaluate((v) => { window.KOS_SIGNED = v; window.dispatchEvent(new CustomEvent("kos-auth", { detail: { signedIn: v } })); }, v);
    await tell(true); await page.waitForTimeout(200);
    let s = await state(page);
    ok(s.secs === ALL_SECS && !s.card, "로그인하면 새로 고치지 않아도 열린다", s.secs);
    const n = s.swaps;
    await tell(true); await page.waitForTimeout(200);
    s = await state(page);
    ok(s.swaps === n, "같은 상태 알림에는 다시 그리지 않는다", `${n} → ${s.swaps}`);
    await tell(false); await page.waitForTimeout(200);
    s = await state(page);
    ok(s.secs === FREE_SECS && s.card, "로그아웃하면 다시 잠긴다", s.secs);
    ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n⑥ 옛 형식 리포트(기본 형식)");
  {
    const ctx = await ctxOf();
    const { page, errors } = await open(ctx, `/stock/${V1}.html`);
    const s = await state(page);
    ok(!s.card && s.locks === 0 && s.secs.split(",").length >= 6, "잠그지 않는다 — 모든 절이 있다", s.secs);
    ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n⑦ 영어");
  for (const [path, lang, self] of [[`/en/stock/${V2}.html`, null, `en/stock/${V2}.html`], [`/stock/${V2}.html`, "en", `stock/${V2}.html`]]) {
    const ctx = await ctxOf({ lang });
    const { page, errors } = await open(ctx, path);
    await page.waitForTimeout(300);
    const s = await state(page);
    const tag = lang ? "한국어 페이지를 영어로 정한 사람" : "영어 페이지";
    ok(s.h3 === "The full report is available to signed-in members" && /Free to sign up/.test(s.text), `${tag} — 카드가 영어`, s.h3);
    ok(!/[가-힣]/.test(s.text), `${tag} — 화면에 한글이 없다`, (s.text.match(/[가-힣]+/g) || []).slice(0, 5).join(" "));
    ok(s.cta[0] === SIGNUP(self) && s.cta[1] === LOGIN(self), `${tag} — 돌아올 곳 ${self}`, s.cta.join(" , "));
    ok(errors.length === 0, `${tag} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
    await ctx.close();
  }

  console.log("\n⑧ 목차의 잠긴 항목 — 카드 자리로 간다");
  for (const [width, sel, tag] of [[1280, "#toc a[data-lock]", "컴퓨터 목차"], [390, "#chips a[data-lock]", "휴대폰 목차 띠"]]) {
    const ctx = await ctxOf({ width });
    const { page } = await open(ctx, `/stock/${V2}.html`);
    await page.locator(sel).nth(3).click();
    await page.waitForTimeout(1500);
    const r = await page.evaluate(() => {
      const pad = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop) || 0;
      return { top: document.getElementById("tz").getBoundingClientRect().top, pad, y: window.scrollY, hash: location.hash };
    });
    ok(r.y > 0 && Math.abs(r.top - r.pad) < 48, `${tag} — 카드 자리(미리보기 시작)로 간다`, `top ${Math.round(r.top)} · 여백 ${r.pad}`);
    ok(r.hash === "#s07", `${tag} — 주소의 절 표시는 누른 항목`, r.hash);
    await ctx.close();
  }

  console.log("\n⑨ 화면 폭 — 넘침 · 겹침");
  /* 보이는 글자 조각끼리 겹치는 자리(stock-overlap.test 와 같은 방식) — 다만 잘려 보이지 않는 부분은 뺀다: 미리보기는 열두 줄 창
     (.tz-fade · overflow hidden)에서 잘리는데, 잘린 줄의 글자 상자는 화면에 없어도 남아 카드 제목과 겹친 것으로 잡힌다 */
  const textHits = () => {
    const clipOf = (el) => { let c = null;
      for (let e = el; e && e !== document.documentElement; e = e.parentElement) {
        const s = getComputedStyle(e);
        if (s.overflowX !== "visible" || s.overflowY !== "visible") { const b = e.getBoundingClientRect();
          c = c ? { l: Math.max(c.l, b.left), t: Math.max(c.t, b.top), r: Math.min(c.r, b.right), b: Math.min(c.b, b.bottom) } : { l: b.left, t: b.top, r: b.right, b: b.bottom }; }
      }
      return c; };
    const blockOf = (el) => { for (let e = el; e; e = e.parentElement) { if (getComputedStyle(e).display !== "inline") return e; } return null; };
    const boxes = [], memo = new Map();
    const w = document.createTreeWalker(document.getElementById("page"), NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.nodeValue.trim() ? 1 : 2) });
    let n;
    while ((n = w.nextNode())) {
      const el = n.parentElement;
      if (!el || (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))) continue;
      if (!memo.has(el)) memo.set(el, [clipOf(el), blockOf(el)]);
      const [c, blk] = memo.get(el), rg = document.createRange();
      rg.selectNodeContents(n);
      for (const q of rg.getClientRects()) {
        let l = q.left, t = q.top, r = q.right, b = q.bottom;
        if (c) { l = Math.max(l, c.l); t = Math.max(t, c.t); r = Math.min(r, c.r); b = Math.min(b, c.b); }
        if (r - l >= 2 && b - t >= 4) boxes.push({ n, el, blk, l, t, r, b });
      }
    }
    boxes.sort((a, b) => a.t - b.t);
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length && boxes[j].t < boxes[i].b; j++) {
      const a = boxes[i], b = boxes[j];
      if (a.n === b.n) continue;
      if (a.blk === b.blk && Math.abs((a.t + a.b) / 2 - (b.t + b.b) / 2) > Math.min(a.b - a.t, b.b - b.t) / 2) continue;   // 같은 덩어리의 다른 줄
      const ox = Math.min(a.r, b.r) - Math.max(a.l, b.l), oy = Math.min(a.b, b.b) - Math.max(a.t, b.t);
      if (ox > 2 && oy > 3) return `'${a.n.nodeValue.trim().slice(0, 14)}' ⟷ '${b.n.nodeValue.trim().slice(0, 14)}'`;
    }
    return "";
  };
  for (const width of [360, 390, 821, 1101, 1280]) {
    for (const path of [`/stock/${V2}.html`, `/en/stock/${V2}.html`]) {
      const ctx = await ctxOf({ width });
      const { page } = await open(ctx, path);
      await page.evaluate(() => document.fonts.ready);
      const r = await page.evaluate(() => {
        const bs = [...document.querySelectorAll("#gateCard .lock-cta a")].map((a) => a.getBoundingClientRect());
        const over = bs.length === 2 && !(bs[0].right <= bs[1].left || bs[1].right <= bs[0].left || bs[0].bottom <= bs[1].top || bs[1].bottom <= bs[0].top);
        return { sw: document.documentElement.scrollWidth, iw: window.innerWidth, n: bs.length, over,
          inside: bs.every((b) => b.left >= 0 && b.right <= window.innerWidth + 0.5) };
      });
      const hit = await page.evaluate(textHits);
      ok(r.sw <= r.iw + 1, `${width}px ${path} — 가로로 넘치지 않는다`, `${r.sw} > ${r.iw}`);
      ok(r.n === 2 && r.inside && !r.over, `${width}px ${path} — 카드 단추 둘이 화면 안에서 겹치지 않는다`, JSON.stringify(r));
      ok(!hit, `${width}px ${path} — 글자끼리 겹치는 자리가 없다(잘려 보이지 않는 미리보기 줄은 뺀다)`, hit);
      await ctx.close();
    }
  }

  console.log("\n⑩ 지금 저장소의 페이지 — 시행 시각 앞 · 뒤");
  SERVE = "repo";
  {
    const js = readFileSync(join(ROOT, "stock/assets/stock.js"), "utf8");
    const m = js.match(/var GATE=(true|false), GATE_AT=(null|\d+);/);
    ok(!!m, "공용 스크립트에 잠금 스위치가 있다");
    ok(FORBIDDEN.every((w) => !js.includes(w)), "공용 스크립트 — 실사이트 금지 낱말이 없다", FORBIDDEN.filter((w) => js.includes(w)).join(" · "));
    const cc = readFileSync(join(ROOT, "scripts/comp_common.py"), "utf8");
    const want = Date.parse((cc.match(/^ACCESS_GATE_AT = '([^']+)'/m) || [])[1] || "");
    /* 미리 그린 페이지가 지금 시각에 맞는가 — 시행 시각 전에는 잠기지 않고(안내 한 줄), 시행 시각 뒤에는 잠긴 채로 다시 만들어져 있어야 한다.
       시행 뒤 첫 종목 페이지 생성(데이터 갱신 · 리포트 워치독 · 신규 상장) 전에는 여기서 걸린다 — python3 scripts/build_live.py 로 다시 만든다 */
    if (m) {
      const html = readFileSync(join(ROOT, `stock/${V2}.html`), "utf8");
      const due = m[1] === "true" || Date.now() >= Number(m[2]);
      ok(html.includes('id="gateCard"') === due && html.includes('class="access-note"') === !due,
        due ? "시행 시각이 지났다 — 미리 그린 페이지가 잠긴 채로 다시 만들어져 있다" : "시행 전 — 미리 그린 페이지는 잠기지 않았고 안내 한 줄이 있다",
        due ? "잠기지 않은 옛 페이지다 — python3 scripts/build_live.py" : "시행 전인데 잠겼다");
    }
    if (m && m[1] === "false") {
      const at = Number(m[2]);
      ok(at === want, "잠그는 시각 = comp_common.ACCESS_GATE_AT(한국 시간 0시)", `${new Date(at).toISOString()} · ${new Date(want).toISOString()}`);
      {
        const ctx = await ctxOf({ at: at - 86400000 });
        const { page, errors } = await open(ctx, `/stock/${V2}.html`);
        const s = await state(page);
        ok(!s.card && s.secs === ALL_SECS, "시행 전 — 잠그지 않는다", s.secs);
        ok(s.note && s.noteFirst, "시행 전 — 안내 한 줄이 실적 분석 앞에 있다");
        ok(errors.length === 0, "시행 전 — 페이지 오류 없음", errors.slice(0, 2).join(" | "));
        await ctx.close();
      }
      for (const [signed, path] of [[false, `/stock/${V2}.html`], [true, `/stock/${V2}.html`], [false, `/en/stock/${V2}.html`]]) {
        const ctx = await ctxOf({ at: at + 3600000, signed, remember: signed });
        const { page, errors } = await open(ctx, path);
        const s = await state(page);
        const tag = `시행 뒤 · ${signed ? "로그인한 사람" : "로그인하지 않은 사람"} · ${path}`;
        if (signed) ok(!s.card && s.secs === ALL_SECS && !s.note, `${tag} — 열리고 안내 한 줄이 없다`, s.secs);
        else {
          ok(s.card && s.secs === FREE_SECS && !s.note, `${tag} — 잠기고 안내 한 줄이 걷혔다`, s.secs);
          ok(s.ctaFlex === "flex" && /gradient/.test(s.mask), `${tag} — 카드 · 미리보기에 옷이 입혀져 있다(생성 전 페이지도)`, `${s.ctaFlex} · ${s.mask.slice(0, 30)}`);
          ok(s.free === false, `${tag} — 구조화 데이터 isAccessibleForFree false`, String(s.free));
          if (path.startsWith("/en/")) ok(!/[가-힣]/.test(s.text), `${tag} — 화면에 한글이 없다`, (s.text.match(/[가-힣]+/g) || []).slice(0, 5).join(" "));
        }
        ok(errors.length === 0, `${tag} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
        await ctx.close();
      }
    } else if (m) {   // 시행일 정리 뒤 — 시계와 관계없이 잠근다
      for (const signed of [false, true]) {
        const ctx = await ctxOf({ signed, remember: signed });
        const { page, errors } = await open(ctx, `/stock/${V2}.html`);
        const s = await state(page);
        ok(signed ? (!s.card && s.secs === ALL_SECS) : (s.card && s.secs === FREE_SECS), `시행 뒤(정리됨) · ${signed ? "로그인한 사람 — 열린다" : "로그인하지 않은 사람 — 잠긴다"}`, s.secs);
        ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 2).join(" | "));
        await ctx.close();
      }
    }
  }
} finally {
  await browser.close();
  server.close();
  rmSync(TMP, { recursive: true, force: true });
}
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
