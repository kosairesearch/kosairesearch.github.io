/* ============================================================
   홈 검색 단추 — '리포트 찾기'를 누르면 그 종목의 리포트로 가는가
   ============================================================
   2026-10-05 사장이 받은 화면: 실사이트 홈에서 '삼성전자'를 입력하고 '리포트 찾기'를 누르면 아래 '최신 리포트' 칸에
   '검색 결과가 없습니다.'가 떴다. 단추가 리포트 2,685편이 아니라 최신 리포트 6편 안에서만 찾았기 때문이다(엔터 · 후보 고르기는
   정상이었다). 이제 첫 화면(landing SEARCH_JS)과 같은 규칙이다 — 고른 후보, 이름이나 종목코드가 꼭 맞는 종목, 결과가 하나뿐인
   종목이면 그 리포트로 가고, 여럿이면 후보를 펼치고, 없으면 후보 자리에 '검색 결과가 없습니다'가 뜬다. 검색어로 '최신 리포트'
   목록을 거르지 않는다.

   두 사이트(실사이트 /Home.html · 스테이징 /staging/Home.html)를 컴퓨터 폭으로, 실사이트는 휴대폰 폭과 영어 화면도 본다.

   실행
     node staging/tests/home-search.test.mjs
     SITE_ROOT=<고치기 전 사본> node staging/tests/home-search.test.mjs   # 고치기 전이면 걸리는지
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

const server = createServer(async (req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    const data = await readFile(join(ROOT, rel || "index.html"));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404); res.end("not found"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}`;

let pass = 0, fail = 0;
const ok = (name, cond, extra = "") => {
  if (cond) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + (extra ? "  ← " + extra : "")); }
};

const browser = await chromium.launch({ executablePath: CHROME });
async function open(path, { lang = "ko", viewport = { width: 1280, height: 900 } } = {}) {
  const ctx = await browser.newContext({ viewport });
  await ctx.route((u) => !u.href.startsWith(HOST), (r) => r.abort());   // 통계 · 로그인 같은 바깥 요청은 보내지 않는다
  await ctx.addInitScript((l) => { try { localStorage.setItem("kos-noga", "1"); if (l === "en") localStorage.setItem("kos-lang", "en"); } catch (e) {} }, lang);
  const p = await ctx.newPage();
  await p.goto(HOST + path, { waitUntil: "load" });
  await p.waitForFunction(() => document.querySelectorAll("#reportRows .row").length > 0, null, { timeout: 15000 });
  return { ctx, p };
}
const rows = (p) => p.evaluate(() => document.querySelectorAll("#reportRows .row").length);
const acText = (p) => p.evaluate(() => { const a = document.getElementById("acList"); return a && a.classList.contains("show") ? a.innerText : ""; });
const acCount = (p) => p.evaluate(() => document.querySelectorAll("#acList.show .ac-item").length);

async function press(p, q) {
  await p.fill("#searchInput", q);
  await p.waitForTimeout(150);
  await p.click("#searchBtn");
  await p.waitForTimeout(600);
}

for (const [site, path, stockRe] of [["실사이트", "/Home.html", /\/stock\/005930\.html$/], ["스테이징", "/staging/Home.html", /stock\.html\?ticker=005930$/]]) {
  // ① 이름이 꼭 맞으면 그 리포트로 간다 — 고치기 전에는 '검색 결과가 없습니다'에 머물렀다
  {
    const { ctx, p } = await open(path);
    const before = await rows(p);
    await press(p, "삼성전자");
    const url = p.url();
    ok(`${site} — '삼성전자' 입력 뒤 '리포트 찾기'가 삼성전자 리포트로 간다`, stockRe.test(url), url);
    await ctx.close();
    ok(`${site} — 최신 리포트 6편이 그려진다`, before === 6, String(before));
  }
  // ② 종목코드가 꼭 맞아도 간다
  {
    const { ctx, p } = await open(path);
    await press(p, "005930");
    ok(`${site} — '005930' 입력 뒤 '리포트 찾기'가 그 리포트로 간다`, stockRe.test(p.url()), p.url());
    await ctx.close();
  }
  // ③ 여럿이면 머물러 후보를 펼친다 · 입력해도 최신 리포트 목록은 그대로다
  {
    const { ctx, p } = await open(path);
    await p.fill("#searchInput", "삼성");
    await p.waitForTimeout(200);
    const r = await rows(p);
    await p.click("#searchBtn");
    await p.waitForTimeout(500);
    const n = await acCount(p), t = await acText(p);
    ok(`${site} — '삼성'은 홈에 머물러 후보를 펼친다(여럿)`, p.url().endsWith(path) && n >= 2 && t.includes("삼성전자"), `${p.url()} · 후보 ${n}`);
    ok(`${site} — 입력해도 최신 리포트 목록을 거르지 않는다`, r === 6, String(r));
    const empty = await p.evaluate(() => [...document.querySelectorAll("#reports *")].some((e) => e.children.length === 0 && /검색 결과가 없습니다/.test(e.textContent || "") && e.offsetParent !== null));
    ok(`${site} — 최신 리포트 칸에 '검색 결과가 없습니다'가 뜨지 않는다`, !empty);
    await ctx.close();
  }
  // ④ 없는 이름은 후보 자리에 '검색 결과가 없습니다'
  {
    const { ctx, p } = await open(path);
    await press(p, "없는회사이름가나다");
    const t = await acText(p);
    ok(`${site} — 없는 이름은 후보 자리에 '검색 결과가 없습니다'`, p.url().endsWith(path) && /검색 결과가 없습니다/.test(t), t.slice(0, 60));
    await ctx.close();
  }
  // ⑤ 빈 칸에서 누르면 검색창으로(이동하지 않는다)
  {
    const { ctx, p } = await open(path);
    await p.click("#searchBtn");
    await p.waitForTimeout(300);
    const focused = await p.evaluate(() => document.activeElement && document.activeElement.id);
    ok(`${site} — 빈 칸에서 누르면 검색창에 머문다`, p.url().endsWith(path) && focused === "searchInput", `${p.url()} · ${focused}`);
    await ctx.close();
  }
  // ⑥ 엔터는 전처럼 첫 후보로 간다
  {
    const { ctx, p } = await open(path);
    await p.fill("#searchInput", "삼성전자");
    await p.waitForTimeout(150);
    await p.press("#searchInput", "Enter");
    await p.waitForTimeout(600);
    ok(`${site} — 엔터는 첫 후보(삼성전자)로 간다`, stockRe.test(p.url()), p.url());
    await ctx.close();
  }
}

// ⑦ 휴대폰 폭 · 영어 화면(실사이트)
{
  const { ctx, p } = await open("/Home.html", { viewport: { width: 390, height: 844 } });
  await press(p, "삼성전자");
  ok("실사이트 휴대폰 — '리포트 찾기'가 삼성전자 리포트로 간다", /\/stock\/005930\.html$/.test(p.url()), p.url());
  await ctx.close();
}
{
  const { ctx, p } = await open("/Home.html", { lang: "en" });
  await press(p, "zzzzqq");
  const t = await acText(p);
  ok("실사이트 영어 — 없는 이름은 'No results for …'", p.url().endsWith("/Home.html") && /No results for/.test(t), t.slice(0, 60));
  await ctx.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
