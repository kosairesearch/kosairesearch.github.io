/* ============================================================
   로그인 화면 '비밀번호를 잊으셨나요?' — 서버 결과에 맞는 안내 (2026-10-04)

   왜 있나
     사장(실사이트): 가입되지 않은 이메일을 넣고 '비밀번호를 잊으셨나요?'를 누르면 빨간 글씨로
     '처리 중 오류가 발생했습니다. (functions/internal)' 가 떴다. 서버(sendResetEmail)가 이제 결과를 돌려주고
     ({sent:true} · {sent:false, reason:"unregistered"} · {sent:false, reason:"no-password", method} ·
     invalid-argument), 화면이 그것으로 문구를 고른다. 서버는 functions/tests/reset-email.test.mjs 가 본다.

   보는 것 (실사이트 · 스테이징 로그인 화면 — 파이어베이스는 가짜로 끼운다)
     ① 가입되지 않은 이메일 → '가입되지 않은 이메일입니다.'(사장이 넣은 'dlae@!kdjae.com' 그대로)
     ② 보냈다 → '비밀번호 재설정 메일을 보내 드렸습니다. …'(안내 색) · 배포 전 서버(sent 없음)도 같은 안내
     ③ 비밀번호 없이 카카오 · 네이버 · 구글로 가입 → 로그인 화면과 같은 '카카오 계정으로 가입된 이메일입니다.'
     ④ 형식이 틀린 주소(invalid-argument) → 이메일 칸 아래 '올바른 이메일 형식이 아닙니다.'
     ⑤ 빈 칸 → 서버를 부르지 않고 칸 아래 안내(전과 같음)
     ⑥ 영어 화면 → 같은 경우가 모두 영어(한국어가 남지 않는다)
     ⑦ 휴대폰(390×667)에서 안내가 화면 안에 보인다
     어느 경우에도 'functions/' 같은 오류 코드가 화면에 나오지 않는다.

   실행
     node staging/tests/forgot-password.test.mjs
     SITE_ROOT=<고치기 전 사본> node staging/tests/forgot-password.test.mjs   # 고치기 전이면 걸리는지
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

/* 가짜 파이어베이스 — sendResetEmail 은 window.__reply 를 답한다("invalid" · "internal" 은 그 코드로 던진다).
   부른 내용은 window.__calls 에 남긴다. 로그인 화면이 열릴 때 보내는 socialLogin 미리 깨우기({warm:true})는 바로 답한다. */
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const A = { currentUser: null };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(null), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    const no = async () => ({});
    export const signInWithCustomToken = no, createUserWithEmailAndPassword = no, deleteUser = no, signInWithEmailAndPassword = no,
      signInWithPopup = no, signOut = no, applyActionCode = no, confirmPasswordReset = no, verifyPasswordResetCode = no;
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
        if (r === "invalid") { const e = new Error("유효한 이메일이 필요합니다."); e.code = "functions/invalid-argument"; throw e; }
        if (r === "internal") { const e = new Error("요청 처리에 실패했습니다."); e.code = "functions/internal"; throw e; }
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

async function open(base, { lang = "ko", viewport = { width: 1280, height: 900 } } = {}) {
  const ctx = await browser.newContext({ viewport });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript((lg) => { try { localStorage.setItem("kos-lang", lg); } catch (e) {} }, lang);
  const p = await ctx.newPage();
  p.errs = [];
  p.on("pageerror", (e) => p.errs.push(String(e)));
  await p.goto(`${HOST}${base}Login.html`, { waitUntil: "networkidle" });
  await p.waitForFunction(() => document.getElementById("forgotLink") && document.getElementById("email"), null, { timeout: 15000 });
  p.ctx = ctx;
  return p;
}
/* 이메일을 넣고 '비밀번호를 잊으셨나요?'를 누른 뒤, 안내가 바뀌기를 기다려 화면에 보이는 것을 읽는다 */
async function forgot(p, email, reply) {
  await p.evaluate((r) => { window.__reply = r; window.__calls = []; }, reply);
  await p.fill("#email", email);
  await p.click("#forgotLink");
  await p.waitForFunction(() => {
    const e = document.getElementById("authErr"), f = document.getElementById("email").closest(".fld");
    return (e && e.classList.contains("show")) || (f && f.classList.contains("err"));
  }, null, { timeout: 8000 }).catch(() => {});
  await p.waitForTimeout(150);   // 번역 엔진(MutationObserver)이 새 글을 바꿀 틈
  return p.evaluate(() => {
    const e = document.getElementById("authErr"), f = document.getElementById("email").closest(".fld");
    const r = e.getBoundingClientRect();
    return {
      alert: e.classList.contains("show") ? e.textContent.trim() : "",
      info: e.classList.contains("info"),
      field: f.classList.contains("err") ? (f.querySelector(".msg") || {}).textContent : "",
      calls: (window.__calls || []).map((c) => c.name + ":" + (c.data && c.data.email) + ":" + (c.data && c.data.lang)),
      inView: r.height > 0 && r.top >= 0 && r.bottom <= innerHeight,
      focus: document.activeElement && document.activeElement.id,
    };
  });
}
const noCode = (s) => !/functions\/|\(.*\/.*\)/.test(s || "");

for (const [site, base] of [["실사이트", ""], ["스테이징", "staging/"]]) {
  console.log(`\n── ${site} 로그인 화면 ──`);
  const p = await open(base);

  let r = await forgot(p, "dlae@!kdjae.com", { ok: true, sent: false, reason: "unregistered" });
  t(r.alert === "가입되지 않은 이메일입니다." && !r.info, `① 가입되지 않은 이메일 → '${r.alert}'(빨간 안내)`);
  t(r.calls.length === 1 && r.calls[0] === "sendResetEmail:dlae@!kdjae.com:ko", `① 서버에 그 주소 그대로 묻는다 (${r.calls.join(", ")})`);

  r = await forgot(p, "me@kosai.kr", { ok: true, sent: true });
  t(r.alert === "비밀번호 재설정 메일을 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다." && r.info, `② 보냈다 → 안내 색 '${r.alert}'`);
  r = await forgot(p, "me@kosai.kr", { ok: true });
  t(r.alert.startsWith("비밀번호 재설정 메일을 보내 드렸습니다.") && r.info, "② 배포 전 서버(sent 없음) → 전처럼 '보내 드렸습니다'");

  for (const [m, want] of [["kakao", "카카오 계정으로 가입된 이메일입니다."], ["naver", "네이버 계정으로 가입된 이메일입니다."], ["google", "Google 계정으로 가입된 이메일입니다."]]) {
    r = await forgot(p, `x@${m}.com`, { ok: true, sent: false, reason: "no-password", method: m });
    t(r.alert === want && !r.info, `③ 비밀번호 없는 ${m} 가입 → '${r.alert}'`);
  }

  r = await forgot(p, "a@b.c", "invalid");
  t(r.field === "올바른 이메일 형식이 아닙니다." && !r.alert && r.focus === "email", `④ 형식이 틀린 주소 → 칸 아래 '${r.field}' · 칸에 초점`);

  await p.evaluate(() => { window.__calls = []; });
  await p.fill("#email", "");
  await p.click("#forgotLink");
  await p.waitForTimeout(200);
  const empty = await p.evaluate(() => ({ field: (document.getElementById("email").closest(".fld").querySelector(".msg") || {}).textContent, calls: (window.__calls || []).length }));
  t(empty.field === "이메일을 먼저 입력하여 주시기 바랍니다." && empty.calls === 0, `⑤ 빈 칸 → 서버를 부르지 않고 '${empty.field}'`);

  r = await forgot(p, "me@kosai.kr", "internal");
  t(r.alert.startsWith("처리 중 오류가 발생했습니다.") && !r.info, "  (서버가 실제로 실패한 때의 일반 안내는 그대로)");
  t(p.errs.length === 0, `페이지 오류 없음${p.errs.length ? " — " + p.errs.join(" | ").slice(0, 200) : ""}`);
  await p.ctx.close();

  console.log(`── ${site} 영어 화면 ──`);
  const e = await open(base, { lang: "en" });
  const cases = [
    [{ ok: true, sent: false, reason: "unregistered" }, "This email is not registered.", "alert"],
    [{ ok: true, sent: true }, "A password reset email has been sent. Please check your inbox.", "alert"],
    [{ ok: true, sent: false, reason: "no-password", method: "kakao" }, "This email is registered with Kakao.", "alert"],
    ["invalid", "That doesn't look like a valid email.", "field"],
  ];
  for (const [reply, want, where] of cases) {
    r = await forgot(e, "dlae@!kdjae.com", reply);
    const got = r[where];
    t(got === want && !/[가-힣]/.test(r.alert + r.field) && noCode(r.alert), `⑥ ${JSON.stringify(reply).slice(0, 48)} → '${got}'`);
  }
  t(r.calls[0] && r.calls[0].endsWith(":en"), "⑥ 영어 화면은 서버에 lang=en 으로 묻는다(메일도 영어)");
  await e.ctx.close();

  console.log(`── ${site} 휴대폰 ──`);
  const m = await open(base, { viewport: { width: 390, height: 667 } });
  r = await forgot(m, "dlae@!kdjae.com", { ok: true, sent: false, reason: "unregistered" });
  t(r.alert === "가입되지 않은 이메일입니다." && r.inView, `⑦ 390×667 에서 안내가 화면 안에 보인다(${r.inView})`);
  await m.ctx.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
