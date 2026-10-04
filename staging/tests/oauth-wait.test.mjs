/* ============================================================
   카카오 · 네이버에서 돌아온 직후의 진행 표시 — 로그인 · 회원가입 (2026-10-04)

   왜 있나
     사장 "네이버로 로그인하면 그냥 이 화면이 떠. 그러고나서 한참 기다려야 로그인된 걸로 뜨는데".
     제공자에서 돌아온 페이지(?code=&state=)가 로그인 폼을 그대로 보여 주고, 뒤에서 서버 확인 · 로그인 · 이동을
     몇 초 동안 기다렸다 — 아무 일도 일어나지 않은 것처럼 보였다. 이제 페이지 맨 앞 스크립트(build_auth_comp.OAUTH_WAIT)가
     그리기 전에 data-oauth 를 달아 폼 대신 '네이버 계정을 확인하고 있습니다'를 보여 준다.

   보는 것 (실사이트 · 스테이징의 Login.html · Signup.html — 파이어베이스는 가짜로 끼운다)
     ① 돌아온 직후(모듈이 돌기 전)부터 진행 표시가 보이고 폼 · 버튼은 감춰진다. 뒤에서는 서버 호출이 그대로 나간다
     ② 서버가 실패하면 표시를 거두고 오류 안내와 폼을 다시 보여 준다
     ③ 카카오에서 돌아오면 카카오 문구
     ④ 저장해 둔 요청과 state 가 다르면 표시하지 않는다(곧바로 '만료' 안내가 뜬다)
     ⑤ 40초가 지나도 끝나지 않으면 스스로 거두고 지연 안내를 띄운다(모듈을 못 받은 경우의 안전장치)
     ⑥ 뒤로 가기로 되살아난 페이지(pageshow persisted)에서는 거둔다
     ⑦ 성공하면 다음 페이지(Home.html)로 넘어간다
     ⑨ 그냥 연 화면은 서버 함수를 미리 깨운다(warm 한 번), 돌아온 길에서는 깨우지 않고 진짜 요청만 보낸다
     ⑧ 이 검사가 실제로 잡는지 — 맨 앞 스크립트를 뺀 판을 덧씌우면 ① 이 걸린다

   실행
     node staging/tests/oauth-wait.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

/* 가짜 파이어베이스 — 로그인은 안 된 상태로 시작하고, 서버 호출(socialLogin)은 window.__fnMode 대로 답한다 */
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const A = { currentUser: null };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(null), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    const no = async () => ({});
    export const createUserWithEmailAndPassword = no, deleteUser = no, signInWithCustomToken = no,
      signInWithEmailAndPassword = no, signInWithPopup = no, signOut = no;
    export function getAdditionalUserInfo(){ return null; }`,
  "firebase-firestore": `
    export function getFirestore(){ return {}; } export function doc(){ return {}; } export function deleteField(){ return {}; }
    export async function getDoc(){ return { exists: () => false, data: () => null }; }
    export async function setDoc(){} export async function updateDoc(){} export async function deleteDoc(){}
    export function onSnapshot(){ return () => {}; }`,
  "firebase-functions": `
    export function getFunctions(){ return {}; }
    export function httpsCallable(f, name){
      return async (data) => {
        window.__calls = (window.__calls || []).concat([name + (data && data.warm ? ":warm" : "")]);
        if (data && data.warm) return { data: { warm: true } };
        const m = window.__fnMode || "fail";
        if (m === "hang") return new Promise(() => {});
        if (m === "ok") return { data: { token: "tok" } };
        const e = new Error("internal"); e.code = "functions/internal"; throw e;
      };
    }`,
};
/* ⑧ — 맨 앞 스크립트를 뺀 판(고치기 전과 같은 동작) */
const STRIP = /<script>\(function\(\)\{var d=document\.documentElement,q=new URLSearchParams\(location\.search\)[\s\S]*?<\/script>/;

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    if (rel === "__blank") { res.writeHead(200, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>.</title>"); return; }
    if (rel.endsWith("/") || rel === "") rel += "index.html";
    const data = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title>"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({ executablePath: CHROME });

/* 화면 상태 — 진행 표시 · 폼 · 버튼이 실제로 보이는지(display) */
function state() {
  const vis = (sel) => { const e = document.querySelector(sel); return !!e && getComputedStyle(e).display !== "none" && e.getClientRects().length > 0; };
  const span = [...document.querySelectorAll(".ow-t span")].find((s) => getComputedStyle(s).display !== "none");
  const err = document.getElementById("authErr");
  return { oauth: document.documentElement.getAttribute("data-oauth"), wait: vis(".ow"), form: vis("#emailForm"), social: vis(".social"),
    msg: span ? span.textContent : "", err: err && err.classList.contains("show") ? err.textContent : "", calls: (window.__calls || []).slice() };
}

async function open(base, page, { provider = "naver", state: st = "n1", mode = "fail", clock = false, strip = false } = {}) {
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  if (strip) await ctx.route(new RegExp(`/${base}${page}\\?`), async (route) => {
    const body = (await readFile(join(ROOT, base + page), "utf8")).replace(STRIP, "");
    route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body });
  });
  await ctx.addInitScript((m) => { window.__fnMode = m; }, mode);
  const p = await ctx.newPage();
  if (clock) await p.clock.install();
  await p.goto(HOST + "__blank");
  await p.evaluate(([prov, b, pg]) => sessionStorage.setItem("kos_social",
    JSON.stringify({ provider: prov, next: "", nonce: "n1", redirectUri: location.origin + "/" + b + pg })), [provider, base, page]);
  await p.goto(`${HOST}${base}${page}?code=c1&state=${st}`, { waitUntil: "domcontentloaded" });
  return { ctx, p };
}

for (const [site, base] of [["실사이트", ""], ["스테이징", "staging/"]]) {
  for (const page of ["Login.html", "Signup.html"]) {
    console.log(`\n${site} ${page}`);
    /* ① 돌아온 직후 — 모듈이 돌기 전(문서를 다 읽은 순간)부터 */
    {
      const { ctx, p } = await open(base, page, { mode: "hang" });
      const first = await p.evaluate(state);
      await p.waitForFunction(() => (window.__calls || []).includes("socialLogin"), null, { timeout: 15000 }).catch(() => {});
      const later = await p.evaluate(state);
      t(first.oauth === "naver" && first.wait && !first.form && !first.social && first.msg === "네이버 계정을 확인하고 있습니다.",
        `① 돌아온 직후 진행 표시 — ${JSON.stringify({ oauth: first.oauth, 표시: first.wait, 폼: first.form, 버튼: first.social, 문구: first.msg })}`);
      t(later.calls.includes("socialLogin") && later.wait && !later.form, `① 표시 뒤에서 서버 호출이 나간다 — 호출 ${JSON.stringify(later.calls)}`);
      t(!later.calls.includes("socialLogin:warm"), `⑨ 돌아온 길에서는 미리 깨우지 않는다 — 호출 ${JSON.stringify(later.calls)}`);
      await ctx.close();
    }
    /* ② 서버 실패 */
    {
      const { ctx, p } = await open(base, page, { mode: "fail" });
      await p.waitForSelector("#authErr.show", { timeout: 15000 }).catch(() => {});
      const s = await p.evaluate(state);
      t(!s.oauth && !s.wait && s.form && s.social && /소셜 로그인에 실패했습니다/.test(s.err), `② 실패하면 표시를 거두고 안내 — ${JSON.stringify({ oauth: s.oauth, 폼: s.form, 안내: s.err })}`);
      await ctx.close();
    }
    /* ⑨ 그냥 연 화면 — 서버 함수를 미리 깨운다 */
    {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
      await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
        const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
        if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
        return route.abort();
      });
      const p = await ctx.newPage();
      await p.goto(`${HOST}${base}${page}`, { waitUntil: "domcontentloaded" });
      await p.waitForFunction(() => (window.__calls || []).length > 0, null, { timeout: 15000 }).catch(() => {});
      await p.waitForTimeout(300);
      const s = await p.evaluate(state);
      t(JSON.stringify(s.calls) === JSON.stringify(["socialLogin:warm"]) && !s.oauth && s.form && s.social,
        `⑨ 그냥 연 화면은 미리 깨우기 한 번 — 호출 ${JSON.stringify(s.calls)} · 폼 ${s.form}`);
      await ctx.close();
    }
    if (page !== "Login.html") continue;   // 나머지는 같은 스크립트 — 로그인 화면에서만 본다
    /* ③ 카카오 */
    {
      const { ctx, p } = await open(base, page, { provider: "kakao", mode: "hang" });
      const s = await p.evaluate(state);
      t(s.oauth === "kakao" && s.msg === "카카오 계정을 확인하고 있습니다.", `③ 카카오 문구 — ${s.msg}`);
      await ctx.close();
    }
    /* ④ state 불일치 */
    {
      const { ctx, p } = await open(base, page, { state: "other", mode: "hang" });
      const first = await p.evaluate(state);
      await p.waitForSelector("#authErr.show", { timeout: 15000 }).catch(() => {});
      const s = await p.evaluate(state);
      t(!first.oauth && !first.wait && first.form && /만료/.test(s.err) && !s.calls.length, `④ 요청이 맞지 않으면 표시하지 않음 — ${s.err}`);
      await ctx.close();
    }
    /* ⑤ 40초 안전장치 */
    {
      const { ctx, p } = await open(base, page, { mode: "hang", clock: true });
      await p.waitForFunction(() => (window.__calls || []).includes("socialLogin"), null, { timeout: 15000 }).catch(() => {});
      await p.clock.fastForward(39000);
      const before = await p.evaluate(state);
      await p.clock.fastForward(2000);
      const s = await p.evaluate(state);
      t(before.oauth === "naver" && !s.oauth && s.form && /지연/.test(s.err), `⑤ 40초 뒤 스스로 거둠 — 39초 ${before.oauth} · 41초 ${s.oauth} · ${s.err}`);
      await ctx.close();
    }
    /* ⑥ 뒤로 가기로 되살아난 페이지 */
    {
      const { ctx, p } = await open(base, page, { mode: "hang" });
      await p.evaluate(() => dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true })));
      const s = await p.evaluate(state);
      t(!s.oauth && s.form, `⑥ pageshow(persisted) 에서 거둠 — ${s.oauth}`);
      await ctx.close();
    }
    /* ⑦ 성공 */
    {
      const { ctx, p } = await open(base, page, { mode: "ok" });
      const ok = await p.waitForURL(/Home\.html$/, { timeout: 15000 }).then(() => true).catch(() => false);
      t(ok, `⑦ 성공하면 다음 페이지로 — ${p.url().replace(HOST, "/")}`);
      await ctx.close();
    }
    /* ⑧ 맨 앞 스크립트를 뺀 판이면 ① 이 걸린다 */
    {
      const { ctx, p } = await open(base, page, { mode: "hang", strip: true });
      const s = await p.evaluate(state);
      t(!s.oauth && s.form, `⑧ 맨 앞 스크립트가 없으면 폼이 그대로 보인다(검사가 잡는다) — ${JSON.stringify({ oauth: s.oauth, 폼: s.form })}`);
      await ctx.close();
    }
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
