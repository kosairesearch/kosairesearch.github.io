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
     ⑦ 바깥(검색 결과 등)에서 옛 주소로 들어온 방문 — 넘어간 뒤에도 원래 출처가 방문 기록에 남는다(넘기는 페이지가 출처 자리를
        차지해 검색 유입이 '내부'로 잡히던 것 · 독립 검토 2026-10-03). r/ 은 유입 꼬리표(utm)도 실어 간다
     ⑧ 자료(리포트 파일 · 시세)를 못 받아도 미리 그린 글 · 제목 · 대표 주소가 그대로다('준비 중' · '찾을 수 없습니다'로 덮지 않는다)
     ⑨ 영어 페이지(/en/stock/ · 옛 r/ 의 영어 본문을 대신한다) — 자바스크립트 없이 머리 · 본문 · 꼬리가 영어, 한국어 페이지와
        서로를 hreflang 으로 가리킨다. 저장된 말과 관계없이 영어로 보이고 저장된 말은 바꾸지 않는다(한 번 열었다고 사이트 전체가
        영어로 굳지 않게 — 다른 페이지는 한국어 그대로). 자료를 기다리는 동안에도 가리지 않고, 본문을 다시 넣지 않는다. 화면이 새로
        그려도 미리 그린 글과 같고, 번역 엔진을 못 받아도 영어 글이 남는다. 한국어로 바꾸면 한국어 페이지로 간다

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
    if (req.url.startsWith("/__ext.html")) {   // 바깥 사이트 흉내 — localhost 로 열면 127.0.0.1 과 다른 출처다
      const to = new URL(req.url, "http://x").searchParams.get("to") || "/";
      res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
      res.end(`<!doctype html><title>ext</title><a id="go" href="http://127.0.0.1:${server.address().port}${to}">go</a>`);
      return;
    }
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
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => {
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
  const r = await page.evaluate(() => ({ lang: document.documentElement.lang, title: document.title, canon: document.querySelector("link[rel=canonical]").getAttribute("href"),
    han: (document.getElementById("page").innerText.match(/[가-힣]+/g) || []).slice(0, 6), pre: document.getElementById("page").getAttribute("data-pre"),
    vis: getComputedStyle(document.getElementById("page")).visibility }));
  ok(r.lang === "en", `${tk} — 영어 화면`);
  ok(r.canon === `https://kosai.kr/stock/${tk}.html`, `${tk} — 대표 주소는 한국어 페이지 그대로(이 주소의 말은 한국어)`, r.canon);
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
  await page.goto(`${BASE}/r/005930.html?utm_source=t#s03`);
  await page.waitForURL(/\/stock\/005930\.html/, { timeout: 10000 }).catch(() => {});
  ok(page.url() === `${BASE}/stock/005930.html?utm_source=t#s03`, "r/ 도 꼬리표 · #절 그대로", page.url());
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

console.log("\n⑦ 바깥에서 옛 주소로 들어온 방문 — 원래 출처가 남는다");
for (const [label, to] of [["stock.html?ticker=", "/stock.html?ticker=005930"], ["r/", "/r/005930.html"]]) {
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  await page.goto(`http://localhost:${server.address().port}/__ext.html?to=${encodeURIComponent(to)}`);
  await Promise.all([page.waitForURL(/\/stock\/005930\.html/, { timeout: 15000 }).catch(() => {}), page.click("#go")]);
  await loaded(page);
  const entry = await page.evaluate(() => { try { return JSON.parse(sessionStorage.getItem("kosai_entry")); } catch (e) { return null; } });
  ok(!!entry && entry.source === "localhost", `${label} 를 거쳐도 유입처가 바깥 사이트(내부 아님)`, JSON.stringify(entry));
  await ctx.close();
}

console.log("\n⑧ 자료를 못 받아도 미리 그린 글은 그대로");
for (const [label, pat] of [["리포트 파일을", /\/data\/reports(_v2)?\/005930\.json/], ["리포트 파일과 시세를", /\/data\/(reports(_v2)?\/005930\.json|stocks\.js)/]]) {
  const ctx = await ctxOf();
  await ctx.route(pat, (route) => route.abort());
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE}/stock/005930.html`);
  await loaded(page);
  const r = await page.evaluate(() => ({ secs: document.querySelectorAll("#page section.sec").length, pending: !!document.querySelector("#page .pending"),
    title: document.title, canon: document.querySelector("link[rel=canonical]").getAttribute("href"), price: !!document.querySelector("#page .price .p"),
    tier: document.getElementById("page").getAttribute("data-tier") }));
  ok(r.secs === 13 && !r.pending && r.price, `${label} 못 받아도 본문 13절 · 시세가 그대로`, JSON.stringify(r));
  ok(r.title.includes("삼성전자") && !/준비 중|찾을 수 없습니다/.test(r.title), `${label} — 제목 그대로`, r.title);
  ok(r.canon === "https://kosai.kr/stock/005930.html" && r.tier === "v2", `${label} — 대표 주소 그대로`, r.canon);
  ok(errors.length === 0, `${label} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
  await ctx.close();
}

console.log("\n⑨ 영어 페이지(/en/stock/)");
const KO_NAME = { "005930": "삼성전자", "0220W0": "한화머시너리앤서비스홀딩스", "006380": "카프로" };
const EN_NAME = { "005930": "Samsung Electronics", "0220W0": "Hanwha Machinery & Service Holdings", "006380": "Capro" };
const alts = () => { const o = {}; document.querySelectorAll("link[rel=alternate][hreflang]").forEach((l) => { o[l.getAttribute("hreflang")] = l.getAttribute("href"); }); return o; };
{
  const ctx = await ctxOf({ javaScriptEnabled: false });
  const page = await ctx.newPage();
  for (const [tk, tier, onMarket] of CASES) {
    const r = await page.goto(`${BASE}/en/stock/${tk}.html`);
    const h = await page.evaluate((altsSrc) => {
      const alts = new Function("return (" + altsSrc + ")")();
      const a = (q, k) => (document.querySelector(q) || {}).getAttribute?.(k) ?? null;
      let ld = null; try { ld = JSON.parse(document.getElementById("kos-jsonld").textContent); } catch (e) {}
      const body = document.body.cloneNode(true); body.querySelectorAll("script,style").forEach((x) => x.remove());
      const attrs = [...body.querySelectorAll("[aria-label],[title],[alt],[placeholder]")].flatMap((e) => ["aria-label", "title", "alt", "placeholder"].map((k) => e.getAttribute(k) || ""));
      return { lang: document.documentElement.lang, title: document.title, canon: a("link[rel=canonical]", "href"), ogurl: a('meta[property="og:url"]', "content"),
        locale: a('meta[property="og:locale"]', "content"), robots: a("meta[name=robots]", "content"), desc: a("meta[name=description]", "content"), ld, alt: alts(),
        han: (body.textContent + " " + attrs.join(" ")).match(/[가-힣]+/g) || [], name: (document.querySelector("#page h1.name") || {}).textContent || "",
        secs: document.querySelectorAll("#page section.sec").length, preLang: document.getElementById("page").getAttribute("data-pre-lang"),
        pageLang: /KOS_PAGE_LANG='en'/.test(document.head.innerHTML.split("i18n.js")[0]) };
    }, alts.toString());
    const url = `https://kosai.kr/en/stock/${tk}.html`, ko = `https://kosai.kr/stock/${tk}.html`;
    ok(r.status() === 200 && h.lang === "en" && h.preLang === "en", `${tk} — 영어 페이지(html lang=en · data-pre-lang=en)`);
    ok(h.pageLang, `${tk} — 번역 엔진보다 먼저 이 페이지의 말(KOS_PAGE_LANG)을 단다`);
    ok(h.canon === url && h.ogurl === url && h.locale === "en_US", `${tk} — canonical · og:url 이 영어 주소 · og:locale en_US`, h.canon);
    ok(h.alt.ko === ko && h.alt.en === url && h.alt["x-default"] === ko, `${tk} — hreflang(한국어 · 영어 · 기본은 한국어)`, JSON.stringify(h.alt));
    ok(!/[가-힣]/.test(h.title + h.desc) && h.title.includes(tk) && h.name === EN_NAME[tk], `${tk} — 제목 · 설명 · 회사 이름이 영어`, `${h.title} · ${h.name}`);
    ok(h.ld && h.ld.inLanguage === "en" && h.ld.mainEntityOfPage === url && h.ld.about.name === EN_NAME[tk] && h.ld.about.alternateName === KO_NAME[tk],
       `${tk} — 구조화 데이터(영어 · 한국어 이름은 alternateName)`, JSON.stringify(h.ld && h.ld.about));
    ok(h.han.length === 0, `${tk} — 머리 · 본문 · 꼬리 글과 속성에 한글이 없다`, h.han.slice(0, 6).join(" "));
    ok(h.secs >= (tier === "v2" ? 13 : 6), `${tk} — 본문 절이 다 들어 있다(${h.secs}개)`);
    ok(onMarket ? !h.robots : /noindex/.test(h.robots || ""), `${tk} — ${onMarket ? "색인 허용" : "상장 폐지라 noindex"}`, h.robots || "");
    await page.goto(`${BASE}/stock/${tk}.html`);
    const k = await page.evaluate((altsSrc) => { const alts = new Function("return (" + altsSrc + ")")(); let ld = null; try { ld = JSON.parse(document.getElementById("kos-jsonld").textContent); } catch (e) {} return { alt: alts(), ld }; }, alts.toString());
    ok(k.alt.ko === ko && k.alt.en === url && k.alt["x-default"] === ko, `${tk} — 한국어 페이지의 hreflang 이 영어 페이지를 가리킨다`);
    ok(k.ld && k.ld.about.name === KO_NAME[tk] && k.ld.about.alternateName === EN_NAME[tk], `${tk} — 한국어 페이지 구조화 데이터의 영문명(alternateName)`, JSON.stringify(k.ld && k.ld.about));
  }
  await ctx.close();
}
const swapHook = () => {
  window.__swaps = 0;
  const d = Object.getOwnPropertyDescriptor(Element.prototype, "innerHTML");
  Object.defineProperty(Element.prototype, "innerHTML", { configurable: true, get() { return d.get.call(this); },
    set(v) { if (this.id === "page") window.__swaps++; d.set.call(this, v); } });
};
const enState = (page) => page.evaluate(() => ({ swaps: window.__swaps, lang: document.documentElement.lang, title: document.title,
  canon: document.querySelector("link[rel=canonical]").getAttribute("href"), pre: document.getElementById("page").getAttribute("data-pre"),
  vis: getComputedStyle(document.getElementById("page")).visibility + "/" + getComputedStyle(document.body).visibility,
  han: (document.body.innerText.match(/[가-힣]+/g) || []).slice(0, 6), stored: localStorage.getItem("kos-lang"),
  watch: (document.getElementById("watchTxt") || {}).textContent || "" }));
for (const [label, stored, want] of [["말을 정하지 않은 방문자", null, null], ["한국어를 고른 방문자", "ko", "ko"], ["영어를 고른 방문자", "en", "en"]]) {
  for (const tk of ["005930", "0220W0"]) {
    const ctx = await ctxOf();
    if (stored) await ctx.addInitScript((v) => { try { localStorage.setItem("kos-lang", v); } catch (e) {} }, stored);
    await ctx.addInitScript(swapHook);
    const page = await ctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(`${BASE}/en/stock/${tk}.html`);
    await loaded(page);
    await page.waitForTimeout(400);
    const r = await enState(page);
    ok(r.lang === "en" && r.han.length === 0 && !/[가-힣]/.test(r.title), `${label} · ${tk} — 영어로 보인다`, `${r.lang} · ${r.han.join(" ")} · ${r.title}`);
    ok(r.swaps === 0 && r.pre === null, `${label} · ${tk} — 본문을 다시 넣지 않았다(미리 번역한 글 그대로)`, `${r.swaps}번`);
    ok(r.canon === `https://kosai.kr/en/stock/${tk}.html`, `${label} · ${tk} — 자료를 받은 뒤에도 대표 주소가 영어 주소`, r.canon);
    ok(r.vis === "visible/visible" && r.watch === "Add to Watchlist", `${label} · ${tk} — 가리지 않고 · 단추도 영어`, `${r.vis} · ${r.watch}`);
    ok(r.stored === want, `${label} · ${tk} — 저장된 말을 바꾸지 않는다(${want})`, String(r.stored));
    ok(errors.length === 0, `${label} · ${tk} — 페이지 오류 없음`, errors.slice(0, 2).join(" | "));
    if (stored !== "en" && tk === "005930") {   // 영어 페이지를 연 뒤 다른 페이지 — 그 사람이 고른 말(정하지 않았으면 한국어) 그대로
      await page.goto(`${BASE}/Reports.html`);
      await page.waitForTimeout(500);
      const after = await page.evaluate(() => [document.documentElement.lang, localStorage.getItem("kos-lang")]);
      ok(after[0] === "ko" && after[1] === stored, `${label} — 영어 페이지를 연 뒤 다른 페이지는 한국어 그대로`, after.join(" · "));
    }
    await ctx.close();
  }
}
{
  // 자료(리포트 파일)를 기다리는 동안에도 미리 번역한 본문이 보인다 — 한국어 페이지를 영어로 볼 때의 가림이 영어 페이지에 걸리면 안 된다
  const ctx = await ctxOf();
  let release;
  const hold = new Promise((r) => { release = r; });
  await ctx.route(/\/data\/reports(_v2)?\/005930\.json/, async (route) => { await hold; route.continue(); });
  const page = await ctx.newPage();
  await page.goto(`${BASE}/en/stock/005930.html`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(800);
  const v = await page.evaluate(() => [getComputedStyle(document.getElementById("page")).visibility, getComputedStyle(document.body).visibility,
    document.getElementById("page").hasAttribute("data-pre"), document.querySelectorAll("#page section.sec").length]);
  ok(v[0] === "visible" && v[1] === "visible" && v[2] === true && v[3] === 13, "자료를 기다리는 동안에도 영어 본문이 보인다(가리지 않는다)", v.join(" · "));
  release();
  await loaded(page);
  await ctx.close();
}
/* 미리 번역한 글과 화면이 새로 그린 글이 같은가 — 지문을 틀리게 바꿔 페이지 스크립트가 영어로 새로 그리고 번역 엔진이 라벨을 바꾸게 한 뒤 견준다.
   다르면 자료가 바뀐 날(새로 그리는 날) 화면의 글이 한 번 바뀐다 */
const firstDiff = (a, b) => { let i = 0; while (i < a.length && a[i] === b[i]) i++; return i >= a.length && i >= b.length ? "" : `@${i}: "${a.slice(i, i + 40)}" ≠ "${b.slice(i, i + 40)}"`; };
for (const tk of ["005930", "0220W0", "006380"]) {
  const ca = await ctxOf();
  const pa = await ca.newPage();
  await pa.goto(`${BASE}/en/stock/${tk}.html`);
  await loaded(pa);
  await pa.waitForTimeout(300);
  const A = await pa.evaluate(() => document.getElementById("page").innerText);
  await ca.close();
  const cb = await ctxOf();
  await cb.route(new RegExp(`/en/stock/${tk}\\.html$`), async (route) => {
    const resp = await route.fetch();
    route.fulfill({ response: resp, body: (await resp.text()).replace(/data-pre="[0-9a-f]{8}"/, 'data-pre="00000000"') });
  });
  await cb.addInitScript(swapHook);
  const pb = await cb.newPage();
  await pb.goto(`${BASE}/en/stock/${tk}.html`);
  await loaded(pb);
  await pb.waitForTimeout(600);
  const B = await pb.evaluate(() => ({ t: document.getElementById("page").innerText, swaps: window.__swaps }));
  ok(B.swaps >= 1 && B.t === A, `${tk} — 화면이 새로 그린 영어 글 = 미리 번역한 영어 글`, `새로 그림 ${B.swaps}번 ${firstDiff(A, B.t)}`);
  await cb.close();
}
{
  const ctx = await ctxOf();
  await ctx.route(/\/i18n\.js(\?|$)/, (route) => route.abort());   // 검색 로봇이 렌더링하다 파일 하나를 건너뛴 경우
  await ctx.addInitScript(swapHook);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/en/stock/005930.html`);
  await loaded(page);
  await page.waitForTimeout(400);
  const r = await enState(page);
  ok(r.swaps === 0 && r.han.length === 0 && r.canon === "https://kosai.kr/en/stock/005930.html" && r.watch === "Add to Watchlist",
     "번역 엔진을 못 받아도 미리 그린 영어 글 · 대표 주소가 그대로", JSON.stringify(r));
  await ctx.close();
}
{
  const ctx = await ctxOf();
  await ctx.route(/\/data\/reports(_v2)?\/005930\.json/, (route) => route.abort());
  const page = await ctx.newPage();
  await page.goto(`${BASE}/en/stock/005930.html`);
  await loaded(page);
  const r = await page.evaluate(() => ({ secs: document.querySelectorAll("#page section.sec").length, title: document.title,
    canon: document.querySelector("link[rel=canonical]").getAttribute("href"), han: (document.body.innerText.match(/[가-힣]+/g) || []).length }));
  ok(r.secs === 13 && /Samsung Electronics/.test(r.title) && r.canon === "https://kosai.kr/en/stock/005930.html" && r.han === 0,
     "리포트 파일을 못 받아도 영어 본문 13절 · 제목 · 대표 주소가 그대로", JSON.stringify(r));
  await ctx.close();
}
{
  const ctx = await ctxOf();
  const page = await ctx.newPage();
  await page.goto(`${BASE}/en/stock/005930.html`);
  await loaded(page);
  const want = "/Login.html?next=" + encodeURIComponent("en/stock/005930.html");
  await page.waitForFunction((w) => { const a = document.querySelector("#navRight a.login"); return a && a.getAttribute("href") === w; }, want, { timeout: 10000 }).catch(() => {});
  const login = await page.evaluate(() => [(document.querySelector("#navRight a.login") || {}).getAttribute?.("href"), (document.querySelector("#navRight a.login") || {}).textContent]);
  ok(login[0] === want && login[1] === "Sign in", "영어 페이지 — 머리의 로그인 링크(돌아올 곳 en/stock/005930.html)", login.join(" · "));
  await page.click("#watchBtn");
  await page.waitForSelector("#kosPopup", { timeout: 10000 }).catch(() => {});
  const pop = await page.evaluate(() => [...document.querySelectorAll("#kosPopup a")].map((a) => a.getAttribute("href")));
  ok(pop.includes(want), "영어 페이지 — 안내창의 로그인 링크", pop.join(" , "));
  await Promise.all([page.waitForURL(/\/stock\/005930\.html$/, { timeout: 10000 }).catch(() => {}), page.evaluate(() => window.KOSi18n.setLang("ko"))]);
  await loaded(page);
  const back = await page.evaluate(() => [location.pathname, document.documentElement.lang, localStorage.getItem("kos-lang")]);
  ok(back[0] === "/stock/005930.html" && back[1] === "ko" && back[2] === "ko", "영어 페이지에서 한국어로 바꾸면 한국어 페이지로 간다", back.join(" · "));
  await ctx.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
