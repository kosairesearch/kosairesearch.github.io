/* ============================================================
   메일의 수신거부 링크가 여는 화면 — 계정 인증 화면(auth-action.html?mode=unsubscribe) (2026-10-29)

   왜 있나
     처리방침 15항이 '발송되는 모든 메일 하단의 수신거부 링크로도 즉시 해제할 수 있다'고 약속하는데, 링크도
     처리할 곳도 없었다(사장 "우리 웹사이트에서 보내는 모든 이메일에 수신거부링크가 들어있는지 확인해봐"). 이제 2년
     재확인 메일 꼬리에 링크가 실리고(서버는 functions/tests/unsubscribe.test.mjs 가 본다), 그 링크가 이 화면을 연다.

   보는 것 (실사이트 · 스테이징 — 파이어베이스는 가짜로 끼운다)
     ① 링크를 열면 확인 화면만 보인다 — 여는 것만으로는 서버를 부르지 않는다(메일 보안 검사기가 미리 열어도 철회되지 않게)
     ② '수신 거부하기'를 누르면 회원 번호 · 표를 그대로 서버(unsubscribeMarketing)에 넘기고 완료 화면 · '홈으로'
     ③ 이미 철회된 회원 → '이미 수신 거부된 상태입니다'
     ④ 서버가 거절(표가 틀림) → '링크가 올바르지 않습니다' · '설정 화면 열기'
     ⑤ 일시 오류 → 확인 화면에 그대로 머물고 안내 · 단추를 다시 누를 수 있다
     ⑥ 표가 빠진 링크 → 서버를 부르지 않고 '링크가 올바르지 않습니다'
     ⑦ 영어 메일의 링크(?lang=en) → 화면 전체가 영어(한국어가 남지 않는다)
     ⑧ 원래 일(이메일 인증)은 그대로 된다

   실행
     node staging/tests/unsubscribe-page.test.mjs
     SITE_ROOT=<고치기 전 사본> node staging/tests/unsubscribe-page.test.mjs   # 고치기 전이면 걸리는지
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = process.env.SITE_ROOT || fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

/* 가짜 파이어베이스 — unsubscribeMarketing 은 window.__reply 를 답한다("denied" · "internal" 은 그 코드로 던진다).
   부른 내용은 window.__calls 에 남긴다. */
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const A = { currentUser: null };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(null), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    const no = async () => ({});
    export const signInWithCustomToken = no, createUserWithEmailAndPassword = no, deleteUser = no, signInWithEmailAndPassword = no,
      signInWithPopup = no, signOut = no, applyActionCode = no, confirmPasswordReset = no;
    export async function verifyPasswordResetCode(){ return "me@kosai.kr"; }
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
        if (data && data.warm) return { data: { warm: true } };
        (window.__calls = window.__calls || []).push({ name, data });
        const r = window.__reply;
        if (r === "denied") { const e = new Error("링크가 올바르지 않습니다."); e.code = "functions/permission-denied"; throw e; }
        if (r === "internal") { const e = new Error("internal"); e.code = "functions/internal"; throw e; }
        return { data: r };
      };
    }`,
};

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    if (rel.endsWith("/") || rel === "") rel += "index.html";
    const data = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title>"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({ executablePath: CHROME });

const UID = "naver:1234567";
const TOK = "abcdefghijklmnopqrstuvwxyz012345";
const q = (o) => Object.entries(o).map(([k, v]) => `${k}=${encodeURIComponent(v)}`).join("&");

async function open(base, query, reply) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript((r) => { window.__reply = r; window.__calls = []; }, reply);
  const p = await ctx.newPage();
  p.errs = [];
  p.on("pageerror", (e) => p.errs.push(String(e)));
  await p.goto(`${HOST}${base}auth-action.html?${query}`, { waitUntil: "networkidle" });
  await p.waitForFunction(() => { const h = document.getElementById("acTitle"); return h && !/처리 중|Working/.test(h.textContent); }, null, { timeout: 15000 }).catch(() => {});
  await p.waitForTimeout(150);   // 번역 엔진(MutationObserver)이 새 글을 바꿀 틈
  p.ctx = ctx;
  return p;
}
const read = (p) => p.evaluate(() => {
  const $ = (s) => document.querySelector(s);
  const btn = $("#acBody .btn");
  const err = $("#acErr");
  return {
    crumb: $("#crumbLabel").textContent.trim(), title: $("#acTitle").textContent.trim(), desc: $("#acDesc").textContent.trim(),
    btn: btn ? btn.textContent.trim() : "", href: btn && btn.getAttribute("href"), disabled: !!(btn && btn.disabled),
    alert: err && err.classList.contains("show") ? err.textContent.trim() : "",
    calls: (window.__calls || []).map((c) => c.name + ":" + JSON.stringify(c.data)),
    main: ($("main") || document.body).innerText,
  };
});
async function press(p, reply) {
  await p.evaluate((r) => { window.__reply = r; }, reply);
  await p.click("#unsubBtn", { timeout: 3000 }).catch(() => {});   // 고치기 전 판에는 단추가 없다 — 아래 검사가 걸린다
  await p.waitForFunction(() => {
    const h = document.getElementById("acTitle"), e = document.getElementById("acErr");
    return (h && !/마케팅 정보 수신 거부|Unsubscribe from/.test(h.textContent)) || (e && e.classList.contains("show"));
  }, null, { timeout: 8000 }).catch(() => {});
  await p.waitForTimeout(150);
  return read(p);
}

for (const [site, base] of [["실사이트", ""], ["스테이징", "staging/"]]) {
  console.log(`\n── ${site} 수신거부 화면 ──`);
  let p = await open(base, q({ mode: "unsubscribe", u: UID, t: TOK }), { ok: true, already: false });
  let r = await read(p);
  t(r.crumb === "마케팅 정보 수신" && r.title === "마케팅 정보 수신 거부" && r.btn === "수신 거부하기",
    `① 확인 화면 — '${r.title}' · 단추 '${r.btn}'`);
  t(r.calls.length === 0, `① 여는 것만으로는 서버를 부르지 않는다 (${r.calls.length}번)`);
  r = await press(p, { ok: true, already: false });
  t(r.calls.length === 1 && r.calls[0] === `unsubscribeMarketing:${JSON.stringify({ u: UID, t: TOK })}`, `② 회원 번호 · 표를 그대로 넘긴다 (${r.calls.join(", ")})`);
  t(r.title === "수신 거부가 완료되었습니다" && r.btn === "홈으로" && r.href === "Home.html", `② 완료 화면 — '${r.title}' · '${r.btn}' → ${r.href}`);
  t(p.errs.length === 0, `② 화면 오류 없음 ${p.errs.join(" | ")}`);
  await p.ctx.close();

  p = await open(base, q({ mode: "unsubscribe", u: UID, t: TOK }), null);
  r = await press(p, { ok: true, already: true });
  t(r.title === "이미 수신 거부된 상태입니다", `③ 이미 철회된 회원 → '${r.title}'`);
  await p.ctx.close();

  p = await open(base, q({ mode: "unsubscribe", u: UID, t: TOK }), null);
  r = await press(p, "denied");
  t(r.title === "링크가 올바르지 않습니다" && r.btn === "설정 화면 열기" && r.href === "Settings.html?tab=notifications",
    `④ 서버가 거절 → '${r.title}' · '${r.btn}' → ${r.href}`);
  t(!/functions\//.test(r.main), "④ 오류 코드가 화면에 나오지 않는다");
  await p.ctx.close();

  p = await open(base, q({ mode: "unsubscribe", u: UID, t: TOK }), null);
  r = await press(p, "internal");
  t(r.title === "마케팅 정보 수신 거부" && r.alert === "처리하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다." && !r.disabled,
    `⑤ 일시 오류 → 확인 화면에 머물고 안내 '${r.alert}' · 단추 다시 누를 수 있음`);
  r = await press(p, { ok: true, already: false });
  t(r.title === "수신 거부가 완료되었습니다", "⑤ 다시 누르면 완료");
  await p.ctx.close();

  p = await open(base, q({ mode: "unsubscribe", u: UID }), { ok: true });
  r = await read(p);
  t(r.title === "링크가 올바르지 않습니다" && r.calls.length === 0, `⑥ 표가 빠진 링크 → '${r.title}' · 서버 호출 ${r.calls.length}번`);
  await p.ctx.close();

  p = await open(base, q({ mode: "unsubscribe", u: UID, t: TOK, lang: "en" }), null);
  r = await read(p);
  t(r.title === "Unsubscribe from marketing messages" && r.btn === "Unsubscribe" && !/[가-힣]/.test(r.main),
    `⑦ 영어 링크 → '${r.title}' · '${r.btn}'${/[가-힣]/.test(r.main) ? " · 남은 한국어: " + (r.main.match(/[가-힣][^\n]{0,30}/) || [""])[0] : ""}`);
  r = await press(p, { ok: true, already: false });
  t(r.title === "You have been unsubscribed" && /^(Go to home|Back to home)$/.test(r.btn) && !/[가-힣]/.test(r.main),
    `⑦ 영어 완료 화면 → '${r.title}' · '${r.btn}'`);
  await p.ctx.close();

  p = await open(base, q({ mode: "verifyEmail", oobCode: "CODE" }), null);
  r = await read(p);
  t(r.title === "이메일 인증이 완료되었습니다" && r.calls.length === 0, `⑧ 이메일 인증은 그대로 — '${r.title}'`);
  await p.ctx.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
