/* ============================================================
   리포트 끝 '같은 업종의 다른 리포트' — 실사이트(stock/ · en/stock/) · 스테이징(stock.html)
   (2026-10-06 사장 "같은 업종의 다른 리포트 부분만 실사이트랑 스테이징에 적용해줘")

   왜 있나
     미리 만든 종목 페이지는 리포트 색인(reports-index.js)을 받지 않는다. 그래서 미리 그릴 때 고른 다섯 편(제목 · 날짜까지)을
     페이지에 싣고(window.KOS_PEERS) 화면 스크립트가 그것으로 그린다 — 빠지면 브라우저가 다시 그린 글이 미리 그린 글과 달라
     본문이 한 번 더 그려지고 칸의 제목이 빈다. 고르는 규칙(같은 대표 업종 · 시가총액이 가까운 순)이 어긋나거나, 영어 페이지의
     링크가 한국어 페이지로 가거나, 휴대폰에서 이름 · 날짜 · 제목이 겹쳐도 여기서 걸린다.

   보는 것
     ① 자료 — 미리 만든 페이지 전부(두 말)의 목록이 규칙대로다: 같은 대표 업종 · 자기 자신 아님 · 시가총액과 리포트가 있음 ·
        시가총액 차이가 작은 순 다섯. '기타'와 시세 없는 종목은 빈 목록이고 칸이 없다. 칸의 줄이 목록과 같고(종목 · 이름 · 제목 ·
        날짜), 링크는 한국어 페이지가 /stock/, 영어 페이지가 /en/stock/, 업종 링크는 사이트맵과 같은 글자다.
     ② 화면 — 실사이트 한국어 · 영어 페이지, 영어로 정한 사람이 보는 한국어 페이지, 스테이징에서 칸이 다섯 줄로 서고, 스테이징은
        리포트 색인으로 같은 다섯을 고른다. 컴퓨터(1280)와 휴대폰(390)에서 넘침 · 겹침이 없고, 휴대폰은 이름과 날짜가 한 줄,
        제목이 다음 줄이다. 영문명 · 영어 제목이 가장 긴 종목이 실린 영어 페이지로도 잰다.

   실행
     node staging/tests/peers.test.mjs                 # SITE_ROOT=다른 사본 으로 고치기 전 판을 대 볼 수 있다
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = process.env.SITE_ROOT || fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

let pass = 0, fail = 0;
const ok = (cond, name, extra = "") => {
  if (cond) { pass++; console.log(`  ✅ ${name}`); } else { fail++; console.log(`  ❌ ${name}${extra ? "  — " + extra : ""}`); }
};

/* ── 자료 ── */
const dctx = vm.createContext({});
dctx.window = dctx;
for (const f of ["data/stocks.js", "data/reports-index.js"]) vm.runInContext(readFileSync(join(ROOT, f), "utf8"), dctx);
const LIVE = dctx.KOS_LIVE_DATA.stocks, REPORTS = dctx.KOS_REPORTS.reports;
const BY = Object.fromEntries(LIVE.map((s) => [s.ticker, s]));
function expected(tk) {   // 화면 스크립트(build_stock_staging.PAGE_JS peerPick)와 따로 쓴 같은 규칙
  const st = BY[tk];
  if (!st || !st.sector || st.sector === "기타" || st.mcap == null) return [];
  const c = [];
  LIVE.forEach((s, k) => {
    const r = REPORTS[s.ticker];
    if (s.ticker === tk || s.sector !== st.sector || s.mcap == null || !r || !r.title) return;
    c.push({ d: Math.abs(s.mcap - st.mcap), k, s, r });
  });
  c.sort((a, b) => (a.d - b.d) || (a.k - b.k));
  return c.slice(0, 5).map((x) => [x.s.ticker, x.r.title.ko || "", x.r.title.en || "", x.r.reportDate || ""]);
}
const quote = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase()).replace(/%2F/g, "/");
const unesc = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&amp;/g, "&");
const ROW = /<a class="pr" href="([^"]+)"><div class="pr-n"><div class="pr-name">([\s\S]*?)<\/div><div class="pr-meta">([\s\S]*?)<\/div><\/div><span class="pr-title">([\s\S]*?)<\/span><span class="pr-date">([\s\S]*?)<\/span><\/a>/g;
const MARKET_EN = { "코스피": "KOSPI", "코스닥": "KOSDAQ", "코넥스": "KONEX" };

console.log("① 자료 — 미리 만든 페이지 전부");
const longest = { name: ["", ""], title: ["", ""] };   // [종목코드, 글] — 영문명 · 영어 제목이 가장 긴 것
for (const s of LIVE) {
  const r = REPORTS[s.ticker];
  if (s.name_en && s.name_en.length > longest.name[1].length) longest.name = [s.ticker, s.name_en];
  if (r && r.title && r.title.en && r.title.en.length > longest.title[1].length) longest.title = [s.ticker, r.title.en];
}
const carrier = { name: null, title: null };   // 그 종목이 칸에 실린 영어 페이지
for (const lang of ["ko", "en"]) {
  const dir = join(ROOT, lang === "en" ? "en/stock" : "stock");
  const files = readdirSync(dir).filter((f) => /^[0-9A-Z]{6}\.html$/.test(f));
  let pages = 0, full = 0, empty = 0;
  const bad = { list: [], noScript: [], rows: [], href: [], more: [], emptyHasSec: [] };
  for (const f of files) {
    const tk = f.slice(0, 6), html = readFileSync(join(dir, f), "utf8");
    pages++;
    const m = /<script>window\.KOS_PEERS=(.*?);<\/script>/s.exec(html);
    if (!m) { bad.noScript.push(tk); continue; }
    const got = JSON.parse(m[1]), want = expected(tk);
    if (JSON.stringify(got) !== JSON.stringify(want)) bad.list.push(tk);
    const sec = /<section class="peers"[^>]*>([\s\S]*?)<\/section>/.exec(html);
    if (!want.length) { empty++; if (sec) bad.emptyHasSec.push(tk); continue; }
    if (want.length === 5) full++;
    if (!sec) { bad.rows.push(tk + "(칸 없음)"); continue; }
    const rows = [...sec[1].matchAll(ROW)];
    const st = BY[tk];
    const rowsOk = rows.length === want.length && rows.every((x, i) => {
      const [t, ko, en, d] = want[i], ps = BY[t];
      const href = lang === "en" ? `/en/stock/${t}.html` : `/stock/${t}.html`;
      if (x[1] !== href) { bad.href.push(`${tk}→${x[1]}`); return false; }
      const title = lang === "en" ? (en || ko) : (ko || en);
      const meta = `${t} · ${lang === "en" ? (MARKET_EN[ps.market] || ps.market) : ps.market}`;
      const name = unesc(x[2]);
      const nameOk = lang === "en" ? name.length > 0 : name === ps.name;
      return nameOk && unesc(x[3]) === meta && unesc(x[4]) === title && unesc(x[5]) === d;
    });
    if (!rowsOk) bad.rows.push(tk);
    const more = /<a class="pr-more" href="([^"]+)">/.exec(sec[1]);
    if (!more || more[1] !== `/industry.html?sector=${quote(st.sector)}`) bad.more.push(`${tk}:${more && more[1]}`);
    if (lang === "en") {
      if (!carrier.name && want.some((p) => p[0] === longest.name[0])) carrier.name = tk;
      if (!carrier.title && want.some((p) => p[0] === longest.title[0])) carrier.title = tk;
    }
  }
  const L = lang === "en" ? "영어" : "한국어";
  const show = (a) => a.slice(0, 5).join(", ");
  ok(pages > 2600, `${L} 페이지 ${pages}장을 훑었다`);
  ok(!bad.noScript.length, `${L} — 모든 페이지에 고른 목록(KOS_PEERS)이 실려 있다`, show(bad.noScript));
  ok(!bad.list.length, `${L} — 목록이 규칙대로다(같은 대표 업종 · 시가총액 가까운 순 다섯)`, `${bad.list.length}장: ${show(bad.list)}`);
  ok(!bad.rows.length, `${L} — 칸의 줄이 목록과 같다(이름 · 종목코드 · 시장 · 제목 · 날짜)`, `${bad.rows.length}장: ${show(bad.rows)}`);
  ok(!bad.href.length, `${L} — 종목 링크가 ${lang === "en" ? "영어 페이지(/en/stock/)" : "한국어 페이지(/stock/)"}`, show(bad.href));
  ok(!bad.more.length, `${L} — 업종 분석 링크가 사이트맵과 같은 글자`, show(bad.more));
  ok(!bad.emptyHasSec.length && empty > 0, `${L} — '기타' · 시세 없는 종목(${empty}장)은 칸이 없다`, show(bad.emptyHasSec));
  ok(full > 2500, `${L} — 다섯 편이 찬 페이지 ${full}장`);
}
ok(carrier.name && carrier.title, `가장 긴 영문명(${longest.name[0]}) · 영어 제목(${longest.title[0]})이 실린 페이지를 찾았다`, JSON.stringify(carrier));

/* ── 화면 ── */
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

/* 파이어베이스 — 로그인하지 않은 사람(stock-static.test 와 같은 가짜) */
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
const browser = await chromium.launch({ executablePath: CHROME });
async function open(path, { width = 1280, height = 900, lang = null } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  if (lang) await ctx.addInitScript((v) => { try { localStorage.setItem("kos-lang", v); } catch (e) {} }, lang);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(BASE + path);
  await page.waitForFunction(() => { const m = document.getElementById("page"); return m && m.hasAttribute("data-tier"); }, null, { timeout: 20000 });
  await page.waitForTimeout(250);
  const r = await page.evaluate(() => {
    const sec = document.querySelector("#page section.peers");
    if (!sec) return { sec: false };
    const R = (e) => e.getBoundingClientRect();
    const hit = (p, q) => p.left < q.right - 0.5 && q.left < p.right - 0.5 && p.top < q.bottom - 0.5 && q.top < p.bottom - 0.5;
    const rows = [...sec.querySelectorAll("a.pr")].map((a) => {
      const n = R(a.querySelector(".pr-n")), t = R(a.querySelector(".pr-title")), d = R(a.querySelector(".pr-date"));
      const over = [".pr-name", ".pr-meta", ".pr-title", ".pr-date"].some((q) => { const e = a.querySelector(q); return e.scrollWidth > e.clientWidth + 1; });
      return { href: a.getAttribute("href"), tk: (a.querySelector(".pr-meta").textContent.match(/[0-9A-Z]{6}/) || [""])[0],
        overlap: hit(n, t) || hit(n, d) || hit(t, d), over,
        sameLine: d.top < n.bottom && n.top < d.bottom, titleBelow: t.top >= Math.max(n.bottom, d.bottom) - 1, titleBeside: t.left >= n.right - 1 && t.top < n.bottom };
    });
    const s = R(sec), more = sec.querySelector("a.pr-more");
    return { sec: true, rows, h2: sec.querySelector("h2").textContent.trim(), more: more && more.getAttribute("href"), moreText: more && more.textContent.trim(),
      han: (sec.innerText.match(/[가-힣]+/g) || []).slice(0, 6), out: s.right > innerWidth + 0.5 || s.left < -0.5,
      sw: document.documentElement.scrollWidth, vw: innerWidth, lang: document.documentElement.lang };
  });
  r.errors = errors;
  await ctx.close();
  return r;
}

console.log("\n② 화면");
const TK = "092730";   // 네오팜 — 화장품 · 사장에게 보낸 시안과 같은 종목
const want = expected(TK).map((p) => p[0]);
{
  const r = await open(`/stock/${TK}.html`);
  ok(r.sec && r.rows.length === 5, "실사이트 한국어 — 칸이 다섯 줄", JSON.stringify(r).slice(0, 200));
  if (r.sec) {
    ok(r.h2 === "같은 업종의 다른 리포트" && r.moreText === "업종 분석 보기", "제목 · 업종 링크 문구", `${r.h2} / ${r.moreText}`);
    ok(r.rows.map((x) => x.tk).join() === want.join() && r.rows.every((x) => x.href === `/stock/${x.tk}.html`), "실린 종목 · 링크(/stock/)", r.rows.map((x) => x.href).join(" "));
    ok(r.rows.every((x) => !x.overlap && !x.over && x.titleBeside), "컴퓨터 — 이름 | 제목 | 날짜가 한 줄에 겹치지 않는다");
    ok(!r.out && r.sw <= r.vw, "컴퓨터 — 화면 밖으로 넘치지 않는다", `${r.sw}/${r.vw}`);
    ok(!r.errors.length, "스크립트 오류 없음", r.errors.join(" | "));
  }
}
{
  const r = await open(`/stock/${TK}.html`, { width: 390, height: 844 });
  ok(r.sec && r.rows.every((x) => !x.overlap && !x.over && x.sameLine && x.titleBelow), "휴대폰 — 이름 · 날짜 한 줄, 제목 다음 줄, 겹침 없음",
     JSON.stringify(r.rows || []).slice(0, 200));
  ok(r.sec && !r.out && r.sw <= r.vw, "휴대폰 — 화면 밖으로 넘치지 않는다", `${r.sw}/${r.vw}`);
}
{
  const r = await open(`/en/stock/${TK}.html`);
  ok(r.sec && r.rows.length === 5 && r.h2 === "Other reports in this industry" && r.moreText === "View industry analysis", "영어 페이지 — 제목 · 링크 문구가 영어", `${r.h2} / ${r.moreText}`);
  ok(r.sec && !r.han.length, "영어 페이지 — 칸에 한글이 없다", (r.han || []).join(" "));
  ok(r.sec && r.rows.every((x) => x.href === `/en/stock/${x.tk}.html`), "영어 페이지 — 종목 링크가 영어 페이지(/en/stock/)");
}
{
  const r = await open(`/stock/${TK}.html`, { lang: "en" });
  ok(r.sec && r.lang === "en" && r.h2 === "Other reports in this industry" && !r.han.length, "영어로 정한 사람이 보는 한국어 페이지 — 칸이 영어", `${r.h2} ${(r.han || []).join(" ")}`);
  ok(r.sec && r.rows.map((x) => x.tk).join() === want.join(), "  같은 다섯 편");
}
{
  const r = await open(`/staging/stock.html?ticker=${TK}`);
  ok(r.sec && r.rows.map((x) => x.tk).join() === want.join(), "스테이징 — 리포트 색인으로 같은 다섯 편을 고른다", r.sec ? r.rows.map((x) => x.tk).join() : "칸 없음");
  ok(r.sec && r.rows.every((x) => x.href === `stock.html?ticker=${x.tk}`) && r.more === `industry.html?sector=${quote(BY[TK].sector)}`,
     "스테이징 — 링크가 스테이징 안(상대 주소)", r.sec ? `${r.rows[0].href} · ${r.more}` : "");
  ok(r.sec && !r.errors.length, "스테이징 — 스크립트 오류 없음", (r.errors || []).join(" | "));
}
{
  const r = await open("/stock/078130.html");   // 국일제지 — '기타'
  ok(!r.sec, "'기타' 업종 종목은 칸이 없다");
}
for (const [what, tk] of [["가장 긴 영문명", carrier.name], ["가장 긴 영어 제목", carrier.title]]) {
  if (!tk) continue;
  for (const w of [1280, 821, 390]) {
    const r = await open(`/en/stock/${tk}.html`, { width: w, height: 900 });
    ok(r.sec && r.rows.every((x) => !x.overlap && !x.over) && !r.out && r.sw <= r.vw, `${what}이 실린 영어 페이지(${tk}) — 폭 ${w} 넘침 · 겹침 없음`,
       r.sec ? `${r.sw}/${r.vw} ${JSON.stringify(r.rows.filter((x) => x.overlap || x.over))}` : "칸 없음");
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
