/* ============================================================
   종목마다 미리 만든 페이지 — 실사이트 stock/{종목코드}.html (2026-10-03 사장 '1안')

   왜 있나
     종목 화면이 빈 틀 하나(stock.html?ticker=)였을 때는 로봇이 본문을 못 읽어 로봇용 사본(r/)을 따로 두었고, 검색으로
     들어온 사람이 머리도 꼬리도 없는 그 사본에 떨어졌다. 이제 종목마다 완성된 페이지를 미리 만든다(scripts/build_stock_static.py).
     미리 그린 글은 리포트 상세 화면의 스크립트를 노드로 돌린 결과라, 브라우저가 그리는 글과 글자 하나까지 같아야 한다 —
     다르면 화면이 열리자마자 한 번 더 그려진다(출렁임). 그리고 폴더가 한 단 내려가서(/stock/) 상대 주소가 깨지기 쉽다.

   보는 것
     ① 자바스크립트 없이 — 제목 · 설명 · canonical · 공유 · 구조화 데이터가 종목마다 있고 본문(히어로 · 절)이 다 들어 있다.
        상장 폐지로 리포트만 남은 종목은 noindex
     ② 자바스크립트로 — 자료를 받은 뒤 본문을 다시 넣지 않는다(지문이 같다) · 오류 없음 · 미리 그린 표시(data-pre)가 걷힌다
     ③ 로그인 링크 · 관심종목 안내창의 로그인 · 가입 링크가 맨 위 주소(/Login.html)이고 돌아올 곳이 stock/005930.html
     ④ 영어로 정한 사람 — 본문 · 문서 제목에 한글이 없다(미리 그린 한국어가 남지 않는다)
     ⑤ 옛 주소 — stock.html?ticker= 는 새 주소로 넘어간다(꼬리표 · #절 그대로, 소문자 종목코드도). 종목코드 모양이 아니면
        넘기지 않고 '종목을 찾을 수 없습니다'(리포트 목록 링크는 /Reports.html). r/{종목코드}.html 도 새 주소로 넘어간다
     ⑥ 사이트 안 링크 — 리포트 목록의 종목 줄이 새 주소를 가리킨다

   실행
     node staging/tests/stock-static.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

if (!existsSync(join(ROOT, "stock/005930.html"))) { console.error("stock/ 가 없습니다 — python3 scripts/build_stock_static.py"); process.exit(1); }

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title><p>없는 페이지"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

/* 파이어베이스 — 로그인하지 않은 사람 */
const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const A = { currentUser: null };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(null), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    const no = async () => ({});
    export const applyActionCode = no, confirmPasswordReset = no, createUserWithEmailAndPassword = no, deleteUser = no,
      signInWithCustomToken = no, signInWithEmailAndPassword = no, signInWithPopup = no, signOut = no, verifyPasswordResetCode = no,
      sendEmailVerification = no, sendPasswordResetEmail = no;
    export function getAdditionalUserInfo(){ return null; }`,
  "firebase-firestore": `
    export function getFirestore(){ return {}; } export function doc(){ return {}; } export function deleteField(){ return {}; }
    export function onSnapshot(r, next){ return () => {}; } export async function getDoc(){ return { exists: () => false, data: () => null }; }
    export async function setDoc(){} export async function updateDoc(){} export async function deleteDoc(){}`,
  "firebase-functions": `export function getFunctions(){ return {}; } export function httpsCallable(){ return async () => ({ data: {} }); }`,
};

let pass = 0, fail = 0;
const ok = (cond, name, extra = "") => {
  if (cond) { pass++; console.log(`  ✅ ${name}`); } else { fail++; console.log(`  ❌ ${name}${extra ? "  — " + extra : ""}`); }
};

const browser = await chromium.launch({ executablePath: CHROME });
async function ctxOf(opts = {}) {
  const ctx = await browser.newContext(Object.assign({ viewport: { width: 1280, height: 900 } }, opts));
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  return ctx;
}
const loaded = (page) => page.waitForFunction(() => { const m = document.getElementById("page"); return m && m.hasAttribute("data-tier"); }, null, { timeout: 20000 });

const CASES = [["005930", "v2", true], ["0220W0", "v1", true], ["006380", "v2", false]];   // 종목 · 리포트 형식 · 상장 여부

console.log("① 자바스크립트 없이");
{
  const ctx = await ctxOf({ javaScriptEnabled: false });
  const page = await ctx.newPage();
  for (const [tk, tier, onMarket] of CASES) {
    const r = await page.goto(`${BASE}/stock/${tk}.html`);
    const h = await page.evaluate(() => {
      const a = (q, k) => (document.querySelector(q) || {}).getAttribute?.(k) ?? null;
      let ld = null; try { ld = JSON.parse(document.getElementById("kos-jsonld").textContent); } catch (e) {}
      return { title: document.title, canon: a("link[rel=canonical]", "href"), ogurl: a('meta[property="og:url"]', "content"),
        desc: a("meta[name=description]", "content"), ogt: a('meta[property="og:title"]', "content"), robots: a("meta[name=robots]", "content"),
        ld, name: (document.querySelector("#page h1.name") || {}).textContent || "", secs: document.querySelectorAll("#page section.sec").length,
        tier: document.getElementById("page").getAttribute("data-tier"), pre: document.getElementById("page").getAttribute("data-pre") };
    });
    const url = `https://kosai.kr/stock/${tk}.html`;
    ok(r.status() === 200, `${tk} — 페이지가 있다`);
    ok(h.canon === url && h.ogurl === url, `${tk} — canonical · og:url 이 자기 주소`, h.canon);
    ok(h.name && h.title.includes(h.name) && h.title.includes(tk) && h.ogt === h.title, `${tk} — 제목에 종목 이름 · 코드`, h.title);
    ok(h.desc && h.desc.length > 20, `${tk} — 설명이 리포트 요약`, (h.desc || "").slice(0, 40));
    ok(h.ld && h.ld.mainEntityOfPage === url && h.ld.about && h.ld.about.tickerSymbol === tk, `${tk} — 구조화 데이터`);
    ok(h.secs >= (tier === "v2" ? 13 : 6), `${tk} — 본문 절이 다 들어 있다(${h.secs}개)`);
    ok(onMarket ? !h.robots : /noindex/.test(h.robots || ""), `${tk} — ${onMarket ? "색인 허용" : "상장 폐지라 noindex"}`, h.robots || "");
    ok(/^[0-9a-f]{8}$/.test(h.pre || "") && h.tier === null, `${tk} — 미리 그린 표시(data-pre)만 있고 data-tier 는 아직 없다`);
  }
  await ctx.close();
}

console.log("\n② 자바스크립트로 — 자료를 받은 뒤 다시 그리지 않는다");
for (const [tk] of CASES) {
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  /* 본문 자리에 글을 넣는 순간을 센다 — 자료가 DOMContentLoaded 전에 올 수도 있어 관찰자보다 innerHTML 을 붙잡는 편이 확실하다 */
  await page.addInitScript(() => {
    window.__swaps = 0;
    const d = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
    Object.defineProperty(Element.prototype, "innerHTML", { configurable: true, get() { return d.get.call(this); },
      set(v) { if (this.id === "page") window.__swaps++; d.set.call(this, v); } });
  });
  await page.goto(`${BASE}/stock/${tk}.html`);
  await loaded(page);
  await page.waitForTimeout(300);
  const r = await page.evaluate(() => ({ swaps: window.__swaps, pre: document.getElementById("page").getAttribute("data-pre"),
    canon: document.querySelector("link[rel=canonical]").getAttribute("href"), wb: !!document.getElementById("watchBtn") }));
  ok(r.swaps === 0, `${tk} — 본문을 다시 넣지 않았다(미리 그린 글 = 화면 스크립트의 글)`, `${r.swaps}번`);
  ok(r.pre === null, `${tk} — 미리 그린 표시가 걷혔다`);
  ok(r.canon === `https://kosai.kr/stock/${tk}.html`, `${tk} — canonical 이 그대로`, r.canon);
  ok(errors.length === 0, `${tk} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
  await ctx.close();
}

console.log("\n③ 로그인 링크 · 관심종목 안내창 — 맨 위 주소, 돌아올 곳은 이 페이지");
{
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/stock/005930.html`);
  await loaded(page);
  const want = "/Login.html?next=" + encodeURIComponent("stock/005930.html");
  await page.waitForFunction((w) => { const a = document.querySelector("#navRight a.login"); return a && a.getAttribute("href") === w; }, want, { timeout: 10000 }).catch(() => {});
  const login = await page.evaluate(() => (document.querySelector("#navRight a.login") || {}).getAttribute?.("href"));
  ok(login === want, "머리의 로그인 링크", login);
  await page.click("#watchBtn");
  await page.waitForSelector("#kosPopup", { timeout: 10000 }).catch(() => {});
  const pop = await page.evaluate(() => [...document.querySelectorAll("#kosPopup a")].map((a) => a.getAttribute("href")));
  ok(pop.includes(want), "안내창의 로그인 링크", pop.join(" , "));
  ok(pop.includes("/Signup.html?next=" + encodeURIComponent("stock/005930.html")), "안내창의 가입 링크", pop.join(" , "));
  const r = await (await ctx.request.get(BASE + want.split("?")[0])).status();
  ok(r === 200, "로그인 링크가 있는 페이지로 간다");
  await ctx.close();
}

console.log("\n④ 영어로 정한 사람");
for (const tk of ["005930", "0220W0"]) {
  const ctx = await ctxOf();
  await ctx.addInitScript(() => { try { localStorage.setItem("kos-lang", "en"); } catch (e) {} });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE}/stock/${tk}.html`);
  await loaded(page);
  await page.waitForTimeout(400);
  const r = await page.evaluate(() => ({ lang: document.documentElement.lang, title: document.title,
    han: (document.getElementById("page").innerText.match(/[가-힣]+/g) || []).slice(0, 6), pre: document.getElementById("page").getAttribute("data-pre"),
    vis: getComputedStyle(document.getElementById("page")).visibility }));
  ok(r.lang === "en", `${tk} — 영어 화면`);
  ok(r.han.length === 0, `${tk} — 본문에 한글이 없다`, r.han.join(" "));
  ok(!/[가-힣]/.test(r.title), `${tk} — 문서 제목이 영어`, r.title);
  ok(r.pre === null && r.vis === "visible", `${tk} — 가림이 걷혔다`);
  ok(errors.length === 0, `${tk} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
  await ctx.close();
}

console.log("\n⑤ 옛 주소");
{
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/stock.html?ticker=005930&utm_source=t#s07`);
  await page.waitForURL(/\/stock\/005930\.html/, { timeout: 10000 }).catch(() => {});
  ok(page.url() === `${BASE}/stock/005930.html?utm_source=t#s07`, "stock.html?ticker= → 새 주소(꼬리표 · #절 그대로)", page.url());
  await page.goto(`${BASE}/stock.html?ticker=0220w0`);
  await page.waitForURL(/\/stock\/0220W0\.html/, { timeout: 10000 }).catch(() => {});
  ok(page.url() === `${BASE}/stock/0220W0.html`, "소문자 종목코드도", page.url());
  for (const [q, why] of [["12", "종목코드 모양이 아니면"], ["999999", "페이지가 없는 종목코드면"]]) {
    await page.goto(`${BASE}/stock.html?ticker=${q}`);
    await loaded(page);
    const nf = await page.evaluate(() => ({ url: location.pathname, h2: (document.querySelector("#page .pending h2") || {}).textContent || "",
      link: (document.querySelector("#page .pending a") || {}).getAttribute?.("href") }));
    ok(nf.url === "/stock.html" && /찾을 수 없습니다/.test(nf.h2), `${why} 넘기지 않고 옛 화면처럼 안내`, `${nf.url} ${nf.h2}`);
    ok(nf.link === "/Reports.html", `${why} — 안내의 리포트 목록 링크`, nf.link);
  }
  await page.goto(`${BASE}/r/005930.html`);
  await page.waitForURL(/\/stock\/005930\.html/, { timeout: 10000 }).catch(() => {});
  ok(page.url() === `${BASE}/stock/005930.html`, "r/005930.html → 새 주소", page.url());
  await page.goto(`${BASE}/r/`);
  await page.waitForURL(/\/Reports\.html/, { timeout: 10000 }).catch(() => {});
  ok(/\/Reports\.html$/.test(page.url()), "r/ 목록 → 리포트 목록", page.url());
  await ctx.close();
}

console.log("\n⑥ 사이트 안 링크");
{
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/Reports.html`);
  await page.waitForSelector("a.rl-row", { timeout: 20000 }).catch(() => {});
  const hrefs = await page.evaluate(() => [...document.querySelectorAll("a.rl-row")].slice(0, 30).map((a) => a.getAttribute("href")));
  ok(hrefs.length > 0 && hrefs.every((h) => /^\/stock\/[0-9A-Z]{6}\.html$/.test(h)), "리포트 목록의 종목 줄", hrefs.slice(0, 2).join(" , "));
  const st = await (await ctx.request.get(BASE + hrefs[0])).status();
  ok(st === 200, "그 주소의 페이지가 있다");
  await ctx.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
