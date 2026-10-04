/* ============================================================
   카카오 · 네이버에서 돌아온 뒤 — 동의 화면 · 취소 · 안내 · 키보드 (2026-10-04)

   왜 있나
     사장 "네이버랑 카카오는 이용약관, 개인정보처리방침, 14세 이상, 마케팅 동의 화면이 안 떠".
     제공자의 동의 화면은 처음 연결할 때만 뜬다. 연결이 남은 채 계정만 없어진 사람이 다시 가입하면 동의
     화면 없이 계정이 만들어졌다. 이제 서버(socialLogin)가 그 사람의 연결을 끊고 reauth 로 알려 주면
     화면이 제공자로 한 번 더 보내 동의 화면을 띄우고, 받지 못하면 needConsent 로 우리 동의 화면에 보낸다.
     functions/tests/social-consent.test.mjs 가 서버를, 이 검사가 화면을 본다.

   보는 것 (실사이트 · 스테이징 — 파이어베이스와 제공자는 가짜로 끼운다)
     ① reauth → 제공자로 한 번 더(새 요청 · reauth 표시), 돌아오면 reauth:true 로 다시 묻고 가입을 마친다
     ② 서버가 reauth 를 또 주면 다시 보내지 않고 안내한다(제공자와 끝없이 오가지 않는다)
     ③ needConsent → 우리 동의 화면(Consent.html?next=…)으로 곧바로
     ④ 제공자 화면에서 취소(?error=access_denied) → '로그인이 취소되었습니다.' · 남의 요청이면 아무것도 안 함
     ⑤ 휴대폰(390×667)에서 실패 안내가 화면 안에 보인다
     ⑥ 약관 동의 — 체크 칸이 이름 있는 체크박스이고 스페이스 · 엔터로 체크된다(전체 동의 포함)
     ⑦ 메일 인증을 마친 뒤 '로그인하러 가기' 가 로그인 화면으로 간다(전에는 홈)

   실행
     node staging/tests/social-return.test.mjs
     SITE_ROOT=<고치기 전 사본> node staging/tests/social-return.test.mjs   # 고치기 전이면 걸리는지
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

/* 가짜 파이어베이스. 서버 호출은 sessionStorage 의 __replies 를 차례로 답하고, 부른 내용은 __log 에 남긴다
   (제공자를 다녀오는 동안 페이지가 바뀌어도 같은 탭이면 남는다). 로그인하면 __user 에 남겨 다음 페이지도 로그인 상태다. */
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const ss = sessionStorage;
    const A = { currentUser: JSON.parse(ss.getItem("__user") || "null") };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(A.currentUser), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    export async function signInWithCustomToken(a, t){ A.currentUser = { uid: "naver:2", email: "", providerData: [] }; ss.setItem("__user", JSON.stringify(A.currentUser)); return { user: A.currentUser }; }
    const no = async () => ({});
    export const createUserWithEmailAndPassword = no, deleteUser = no, signInWithEmailAndPassword = no, signInWithPopup = no,
      signOut = async () => { A.currentUser = null; ss.removeItem("__user"); }, applyActionCode = no, confirmPasswordReset = no;
    export async function verifyPasswordResetCode(){ return "you@example.com"; }
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
        const ss = sessionStorage;
        ss.setItem("__log", JSON.stringify(JSON.parse(ss.getItem("__log") || "[]").concat([{ name, data }])));
        const replies = JSON.parse(ss.getItem("__replies") || "[]");
        const r = replies.shift(); ss.setItem("__replies", JSON.stringify(replies));
        if (r === undefined || r === "hang") return new Promise(() => {});
        if (r === "fail") { const e = new Error("internal"); e.code = "functions/internal"; throw e; }
        return { data: r };
      };
    }`,
};

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

/* 제공자 흉내 — 인가 주소로 오면 같은 state 로 우리 페이지에 code 를 붙여 돌려보낸다(동의 화면을 거친 셈) */
async function context(viewport = { width: 390, height: 844 }) {
  const ctx = await browser.newContext({ viewport });
  ctx.authorizeHits = [];
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const url = route.request().url();
    const m = url.match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    if (/kauth\.kakao\.com\/oauth\/authorize|nid\.naver\.com\/oauth2\.0\/authorize/.test(url)) {
      ctx.authorizeHits.push(url);
      const u = new URL(url);
      return route.fulfill({ status: 302, headers: { location: `${u.searchParams.get("redirect_uri")}?code=c2&state=${u.searchParams.get("state")}` } });
    }
    return route.abort();
  });
  return ctx;
}
async function prime(p, base, page, { provider = "naver", next = "Watchlist.html", replies = [], reauth = false } = {}) {
  await p.goto(HOST + "__blank");
  await p.evaluate(([prov, b, pg, nx, rp, ra]) => {
    sessionStorage.setItem("kos_social", JSON.stringify({ provider: prov, next: nx, nonce: "n1", redirectUri: location.origin + "/" + b + pg, reauth: ra }));
    sessionStorage.setItem("__replies", JSON.stringify(rp));
  }, [provider, base, page, next, replies, reauth]);
}
const log = (p) => p.evaluate(() => JSON.parse(sessionStorage.getItem("__log") || "[]")).catch(() => []);
const errText = (p) => p.evaluate(() => { const e = document.getElementById("authErr"); return e && e.classList.contains("show") ? e.textContent : ""; });

for (const [site, base] of [["실사이트", ""], ["스테이징", "staging/"]]) {
  for (const page of ["Login.html", "Signup.html"]) {
    console.log(`\n${site} ${page}`);
    /* ① reauth → 제공자 한 번 더 → 가입 */
    {
      const ctx = await context(); const p = await ctx.newPage();
      await prime(p, base, page, { replies: [{ reauth: true }, { token: "tok", needConsent: false }] });
      await p.goto(`${HOST}${base}${page}?code=c1&state=n1`);
      const done = await p.waitForURL(/Watchlist\.html$/, { timeout: 15000 }).then(() => true).catch(() => false);
      const L = await log(p);
      const hit = ctx.authorizeHits[0] ? new URL(ctx.authorizeHits[0]) : null;
      t(ctx.authorizeHits.length === 1 && hit && hit.searchParams.get("state") !== "n1" && hit.searchParams.get("redirect_uri") === `${HOST}${base}${page}`,
        `① 제공자로 한 번 더 보낸다(새 요청) — ${ctx.authorizeHits.length}번 · state ${hit && hit.searchParams.get("state")}`);
      t(L.length === 2 && L[0].data.flow === 2 && !L[0].data.reauth && L[1].data.reauth === true && L[1].data.code === "c2",
        `① 처음엔 flow 2, 돌아온 길엔 reauth 표시 — ${JSON.stringify(L.map((x) => ({ code: x.data.code, flow: x.data.flow, reauth: x.data.reauth })))}`);
      t(done, `① 돌아와 가입을 마치고 원래 가려던 곳으로 — ${p.url().replace(HOST, "/")}`);
      await ctx.close();
    }
    if (page !== "Login.html") continue;   // 나머지는 같은 모듈 — 로그인 화면에서만 본다
    /* ② 서버가 reauth 를 또 줌 → 멈추고 안내 */
    {
      const ctx = await context(); const p = await ctx.newPage();
      await prime(p, base, page, { replies: [{ reauth: true }, { reauth: true }] });
      await p.goto(`${HOST}${base}${page}?code=c1&state=n1`);
      await p.waitForSelector("#authErr.show", { timeout: 15000 }).catch(() => {});
      const e = await errText(p);
      t(ctx.authorizeHits.length === 1 && /동의 절차를 마치지 못했습니다/.test(e) && /Login\.html$/.test(p.url()),
        `② 두 번째 reauth 에서 멈춤 — 제공자 ${ctx.authorizeHits.length}번 · ${e}`);
      await ctx.close();
    }
    /* ③ needConsent → 우리 동의 화면 */
    {
      const ctx = await context(); const p = await ctx.newPage();
      await prime(p, base, page, { replies: [{ token: "tok", needConsent: true }] });
      await p.goto(`${HOST}${base}${page}?code=c1&state=n1`);
      const ok = await p.waitForURL(/Consent\.html\?next=Watchlist\.html$/, { timeout: 15000 }).then(() => true).catch(() => false);
      t(ok, `③ needConsent → 동의 화면으로 — ${p.url().replace(HOST, "/")}`);
      await ctx.close();
    }
    /* ④ 제공자 화면에서 취소 */
    {
      const ctx = await context(); const p = await ctx.newPage();
      await prime(p, base, page, {});
      await p.goto(`${HOST}${base}${page}?error=access_denied&error_description=Canceled+By+User&state=n1`);
      await p.waitForSelector("#authErr.show", { timeout: 15000 }).catch(() => {});
      const e = await errText(p);
      const ss = await p.evaluate(() => sessionStorage.getItem("kos_social"));
      t(e === "로그인이 취소되었습니다." && !ss && !/[?]/.test(p.url()), `④ 취소 안내 · 요청 정리 · 주소 정리 — ${e} · ${p.url().replace(HOST, "/")}`);
      await ctx.close();
    }
    {
      const ctx = await context(); const p = await ctx.newPage();
      await prime(p, base, page, {});
      await p.goto(`${HOST}${base}${page}?error=access_denied&state=someone-else`);
      await p.waitForLoadState("networkidle").catch(() => {});
      await p.waitForTimeout(300);
      t(!(await errText(p)), `④ 남의 요청(state 다름)이면 아무 말도 하지 않음`);
      await ctx.close();
    }
    /* ⑤ 휴대폰에서 실패 안내가 보이는 자리에 */
    {
      const ctx = await context({ width: 390, height: 667 }); const p = await ctx.newPage();
      await prime(p, base, page, { replies: ["fail"] });
      await p.goto(`${HOST}${base}${page}?code=c1&state=n1`);
      await p.waitForSelector("#authErr.show", { timeout: 15000 }).catch(() => {});
      await p.waitForTimeout(400);
      const r = await p.evaluate(() => { const b = document.getElementById("authErr").getBoundingClientRect(); return { top: Math.round(b.top), bottom: Math.round(b.bottom), h: innerHeight }; });
      t(r.top >= 0 && r.bottom <= r.h, `⑤ 실패 안내가 화면 안에 — ${JSON.stringify(r)}`);
      await ctx.close();
    }
  }

  /* ⑥ 약관 동의 — 키보드 · 화면 낭독기 */
  console.log(`\n${site} Consent.html`);
  {
    const ctx = await context({ width: 1280, height: 900 }); const p = await ctx.newPage();
    await p.goto(HOST + "__blank");
    await p.evaluate(() => sessionStorage.setItem("__user", JSON.stringify({ uid: "naver:2", email: "", providerData: [] })));
    await p.goto(`${HOST}${base}Consent.html?next=Watchlist.html`);
    await p.waitForLoadState("networkidle").catch(() => {});   // 동의 화면 스크립트가 손잡이를 단 뒤에 누른다
    await p.waitForTimeout(300);
    const names = ["전체 동의", "[필수] 만 14세 이상입니다", "[필수] 이용약관 동의", "[필수] 개인정보 수집·이용 동의", "[선택] 마케팅 정보 수신 동의"];
    const found = [];
    for (const n of names) found.push(await p.getByRole("checkbox", { name: n, exact: true }).count());
    t(found.every((c) => c === 1), `⑥ 이름 있는 체크박스 다섯 — ${JSON.stringify(found)}`);
    const aria = (k) => p.evaluate((k) => { const r = document.querySelector(`#consentMount .check[data-k="${k}"]`); return [r.classList.contains("on"), r.querySelector(".box").getAttribute("aria-checked")]; }, k);
    await p.getByRole("checkbox", { name: "[필수] 만 14세 이상입니다", exact: true }).focus({ timeout: 3000 }).catch(() => {});
    await p.keyboard.press("Space");
    const a1 = await aria("age14");
    await p.keyboard.press("Tab");        // 다음 칸(이용약관)으로
    const focused = await p.evaluate(() => { const b = document.activeElement; return b && b.closest(".check") ? b.closest(".check").dataset.k : (b && b.tagName); });
    await p.keyboard.press("Enter");
    const a2 = await aria("terms");
    t(JSON.stringify(a1) === '[true,"true"]' && focused === "terms" && JSON.stringify(a2) === '[true,"true"]',
      `⑥ 스페이스 · 탭 · 엔터로 체크 — 만14세 ${JSON.stringify(a1)} · 다음 칸 ${focused} · 이용약관 ${JSON.stringify(a2)}`);
    await p.getByRole("checkbox", { name: "전체 동의", exact: true }).focus({ timeout: 3000 }).catch(() => {});
    await p.keyboard.press("Space");
    const all = await p.evaluate(() => [...document.querySelectorAll("#consentMount .check .box")].map((b) => b.getAttribute("aria-checked")));
    t(all.every((v) => v === "true"), `⑥ 전체 동의를 키보드로 — ${JSON.stringify(all)}`);
    await ctx.close();
  }

  /* ⑦ 메일 인증 뒤 '로그인하러 가기' */
  console.log(`\n${site} auth-action.html`);
  {
    const ctx = await context(); const p = await ctx.newPage();
    await p.goto(`${HOST}${base}auth-action.html?mode=verifyEmail&oobCode=x&continueUrl=${encodeURIComponent("https://kosai.kr/Login.html")}&lang=ko`);
    await p.waitForSelector("a:has-text('로그인하러 가기')", { timeout: 15000 }).catch(() => {});
    const href = await p.evaluate(() => { const a = [...document.querySelectorAll("a")].find((x) => /로그인하러 가기/.test(x.textContent)); return a ? a.href : ""; });
    t(href === `${HOST}${base}Login.html`, `⑦ 인증 완료 → 로그인 화면 — ${href.replace(HOST, "/")}`);
    await ctx.close();
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
