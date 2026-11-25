/* ============================================================
   상장 전 리포트가 검색 · 목록에 나오는가 — 첫 화면 검색 · 홈 · 리포트 목록
   ============================================================
   2026-11-24 사장 "상장 종목은 상장 전에 리포트 나온대매. 엠비디 리포트 왜 없냐" — 엠비디(498150 · 11/24 상장) 리포트는 11/21 에
   게시돼 종목 페이지(/stock/498150.html)에는 있었으나, 첫 화면 검색 · 홈(검색 · 최신 리포트) · 리포트 목록이 종목을 시세 자료
   (stocks.js)에서만 읽어 보이지 않았다. 시세 자료에는 상장일 장 마감 뒤에야 종목이 오른다. 이제 리포트 색인(reports-index.js)의
   ipo 칸(scripts/ipo_listings.index_entries · 이름 · 시장 · 업종 · 상장일 · 공모가)으로 그 종목을 그린다(comp_common.IPO_JS ·
   landing.SEARCH_JS).

   진짜 자료(stocks.js · reports-index.js)에 시험 장면을 끼운다 — 엠비디를 시세 자료에서 빼고 색인에 ipo 칸과 가장 최근 리포트를 둔다.
   두 사이트(실사이트 · 스테이징)를 본다. 비슷한 이름의 상장사(아이엠비디엑스 461030)가 있어, 색인을 늦게 받을 때 '엠비디'로
   '리포트 찾기'를 누른 사람이 그쪽으로 가지 않는지도 본다. 상장일 장 마감 뒤(시세 자료에 오른 뒤)에는 한 줄만 · 평소 줄인지 본다.

   실행
     node staging/tests/ipo-listing.test.mjs
     SITE_ROOT=<고치기 전 사본> node staging/tests/ipo-listing.test.mjs   # 고치기 전이면 걸리는지
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
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "") || "index.html";
    const data = await readFile(join(ROOT, rel));
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

/* ── 시험 장면 ── 진짜 자료에 엠비디를 끼운다 */
const body = (src) => JSON.parse(src.slice(src.indexOf("=") + 1).trim().replace(/;\s*$/, ""));
const STOCKS = body(await readFile(join(ROOT, "data/stocks.js"), "utf8"));
const INDEX = body(await readFile(join(ROOT, "data/reports-index.js"), "utf8"));
const TK = "498150", NAME = "엠비디", NEAR = "461030";   // 아이엠비디엑스 — '엠비디'가 이름 안에 든 상장사
const IPO = { name: NAME, name_en: "MBD Co., Ltd.", market: "코스닥", sector: "전자·부품", categories: ["전자·부품"],
  list_date: "2026-11-24", offer_price: 7000, shares: 14342238 };
const REP = { title: { ko: "자본잠식 해소, 영업적자는 남았다", en: "Recapitalized, but operating losses persist" },
  reportDate: "2026-11-21", reportTs: "9999-12-31 23:59" };          // 가장 최근 리포트 — 홈 '최신 리포트' 맨 위
const near = STOCKS.stocks.find((s) => s.ticker === NEAR);
ok("시험 전제 — 비슷한 이름의 상장사가 시세 자료에 있다", !!near && near.name.includes(NAME), near && near.name);

function scene(kind) {
  const st = JSON.parse(JSON.stringify(STOCKS)), ix = JSON.parse(JSON.stringify(INDEX));
  st.stocks = st.stocks.filter((s) => s.ticker !== TK);
  ix.reports[TK] = REP;
  if (kind === "pre") ix.ipo = { [TK]: IPO };
  if (kind === "listed") {             // 상장일 장 마감 뒤 — 시세 자료에 올랐다. 색인의 ipo 칸은 다음 동기화 전까지 남아 있을 수 있다
    st.stocks.push(Object.assign({}, near, { ticker: TK, name: NAME, name_en: IPO.name_en, market: "코스닥", sector: "전자·부품",
      categories: ["전자·부품"], price: 9000, change: 28.57, mcap: 0.13, trading_value: 5e10 }));
    ix.ipo = { [TK]: IPO };
  }
  const live = st.stocks.filter((s) => ix.reports[s.ticker]).length;   // 머리 줄 종목 수 — 시세 자료 기준
  return { stocks: "window.KOS_LIVE_DATA = " + JSON.stringify(st) + ";\n", index: "window.KOS_REPORTS = " + JSON.stringify(ix) + ";\n",
           live, total: st.stocks.length };
}

const browser = await chromium.launch({ executablePath: CHROME });
async function open(path, sc, { lang = "ko", viewport = { width: 1280, height: 900 }, slowIndex = 0, watch = null } = {}) {
  const ctx = await browser.newContext({ viewport });
  await ctx.route((u) => !u.href.startsWith(HOST), (r) => r.abort());   // 통계 · 로그인 같은 바깥 요청은 보내지 않는다
  if (watch) {   // 관심종목 — 계정 목록(watchlist.js · Firestore) 대신 담아 둔 목록을 끼운다. 로그인 관문(auth-guard)은 건너뛴다
    await ctx.route((u) => /\/(watchlist|auth-guard)\.js$/.test(new URL(u).pathname), (r) => r.abort());
    await ctx.addInitScript((tks) => { try { localStorage.setItem("kos-signed", "1"); } catch (e) {}
      /* 진짜 모듈처럼 페이지 스크립트 뒤에 나타난다(페이지는 나타날 때까지 기다린다) */
      document.addEventListener("DOMContentLoaded", () => { window.KOSWatch = { ready: true, tickers: () => tks.slice(), addedAt: () => 0,
        has: (t) => tks.includes(t), add: () => true, remove: () => {}, clear: () => {} }; }); }, watch);
  }
  await ctx.route((u) => new URL(u).pathname === "/data/stocks.js",
    (r) => r.fulfill({ status: 200, contentType: "text/javascript; charset=utf-8", body: sc.stocks }));
  await ctx.route((u) => new URL(u).pathname === "/data/reports-index.js", async (r) => {
    if (slowIndex) await new Promise((res) => setTimeout(res, slowIndex));
    await r.fulfill({ status: 200, contentType: "text/javascript; charset=utf-8", body: sc.index });
  });
  await ctx.addInitScript((l) => { try { localStorage.setItem("kos-noga", "1"); if (l === "en") localStorage.setItem("kos-lang", "en"); } catch (e) {} }, lang);
  const p = await ctx.newPage();
  const errs = [];
  p.on("pageerror", (e) => errs.push(String(e && e.message || e)));
  await p.goto(HOST + path, { waitUntil: "load" });
  return { ctx, p, errs };
}
const navTo = (p) => p.waitForURL((u) => /ticker=|\/stock\//.test(String(u)), { timeout: 8000 }).then(() => p.url()).catch(() => p.url());

const PRE = scene("pre"), LISTED = scene("listed");
const SITES = [["실사이트", ""], ["스테이징", "/staging"]];

/* ── ① 첫 화면 검색 ── */
for (const [site, base] of SITES) {
  console.log(`\n── ${site} 첫 화면 검색 ──`);
  const landing = base ? base + "/index.html" : "/";
  {
    const { ctx, p, errs } = await open(landing, PRE);
    const inp = p.locator("form.search input").first();
    await inp.click(); await inp.fill(NAME);
    await p.waitForFunction(() => document.querySelector("form.search .ac.show"), null, { timeout: 8000 }).catch(() => {});
    await p.waitForTimeout(300);
    const items = await p.evaluate(() => [...document.querySelectorAll("form.search .ac.show .ac-item")]
      .map((a) => [a.querySelector(".ac-tk").textContent, a.querySelector(".ac-nm").textContent]));
    ok(`${site} 첫 화면 — '엠비디'를 치면 후보에 엠비디(${TK})가 있다`, items.some(([t, n]) => t === TK && n === NAME), JSON.stringify(items));
    ok(`${site} 첫 화면 — 비슷한 이름의 상장사도 그대로 있다`, items.some(([t]) => t === NEAR), JSON.stringify(items));
    await p.locator("form.search button").first().click();
    const u = await navTo(p);
    ok(`${site} 첫 화면 — '리포트 찾기'는 이름이 꼭 맞는 엠비디로 간다`, u.includes(TK), u);
    ok(`${site} 첫 화면 — 스크립트 오류가 없다`, errs.length === 0, errs.slice(0, 2).join(" / "));
    await ctx.close();
  }
  {   // 색인이 시세 자료보다 늦게 와도 — 시세 자료만으로 찾으면 '엠비디'가 아이엠비디엑스 하나로 정해져 그쪽으로 갔다
    const { ctx, p } = await open(landing, PRE, { slowIndex: 1500 });
    const inp = p.locator("form.search input").first();
    await inp.click(); await inp.fill(NAME);
    await p.locator("form.search button").first().click();
    const u = await navTo(p);
    ok(`${site} 첫 화면 — 색인이 늦게 와도 '리포트 찾기'가 아이엠비디엑스로 가지 않는다`, u.includes(TK) && !u.includes(NEAR), u);
    await ctx.close();
  }
  {
    const { ctx, p } = await open(landing, PRE, { lang: "en" });
    const inp = p.locator("form.search input").first();
    await inp.click(); await inp.fill("MBD");
    await p.waitForFunction(() => document.querySelector("form.search .ac.show"), null, { timeout: 8000 }).catch(() => {});
    await p.waitForTimeout(300);
    const items = await p.evaluate(() => [...document.querySelectorAll("form.search .ac.show .ac-item")]
      .map((a) => [a.querySelector(".ac-tk").textContent, a.querySelector(".ac-nm").textContent]));
    ok(`${site} 첫 화면(영어) — 영문명 'MBD'로도 찾는다`, items.some(([t, n]) => t === TK && n === "MBD"), JSON.stringify(items));
    await ctx.close();
  }
}

/* ── ② 홈 — 최신 리포트 · 검색 ── */
for (const [site, base] of SITES) {
  console.log(`\n── ${site} 홈 ──`);
  {
    const { ctx, p, errs } = await open(base + "/Home.html", PRE);
    await p.waitForFunction(() => document.querySelectorAll("#reportRows .row").length > 0, null, { timeout: 15000 }).catch(() => {});
    const first = await p.evaluate(() => { const a = document.querySelector("#reportRows .row"); return a ? [a.getAttribute("href"), a.innerText] : ["", ""]; });
    ok(`${site} 홈 — 최신 리포트 맨 위가 엠비디`, first[0].includes(TK) && first[1].includes(NAME), JSON.stringify(first));
    ok(`${site} 홈 — 가격 칸은 공모가(시세가 아니다)`, /7,000원/.test(first[1]) && first[1].includes("공모가"), first[1].replace(/\s+/g, " "));
    const eb = await p.evaluate(() => document.getElementById("eyebrow").textContent);
    ok(`${site} 홈 — 머리 줄 종목 수는 시세 자료 그대로(상장 전 종목을 세지 않는다)`, eb === `국내 상장 ${PRE.live.toLocaleString("ko-KR")}개 종목`, eb);
    await p.fill("#searchInput", NAME); await p.waitForTimeout(300);
    const ac = await p.evaluate(() => [...document.querySelectorAll("#acList.show .ac-item")].map((a) => a.querySelector(".ac-tk").textContent));
    ok(`${site} 홈 — 검색 후보에 엠비디가 있다`, ac.includes(TK) && ac.includes(NEAR), JSON.stringify(ac));
    await p.click("#searchBtn");
    const u = await navTo(p);
    ok(`${site} 홈 — '리포트 찾기'가 엠비디로 간다`, u.includes(TK), u);
    ok(`${site} 홈 — 스크립트 오류가 없다`, errs.length === 0, errs.slice(0, 2).join(" / "));
    await ctx.close();
  }
  {
    const { ctx, p } = await open(base + "/Home.html", PRE, { lang: "en" });
    await p.waitForFunction(() => document.querySelectorAll("#reportRows .row").length > 0, null, { timeout: 15000 }).catch(() => {});
    await p.waitForTimeout(400);
    const t = await p.evaluate(() => { const a = document.querySelector("#reportRows .row"); return a ? a.innerText : ""; });
    ok(`${site} 홈(영어) — 'Offer price' · '₩7,000' · 영어 제목`, t.includes("Offer price") && t.includes("₩7,000") && t.includes(REP.title.en) && !/[가-힣]/.test(t),
       t.replace(/\s+/g, " "));
    await ctx.close();
  }
}

/* ── ③ 리포트 목록 ── */
for (const [site, base] of SITES) {
  console.log(`\n── ${site} 리포트 목록 ──`);
  const { ctx, p, errs } = await open(base + "/Reports.html", PRE);
  await p.waitForFunction(() => document.querySelectorAll(".rl-row").length > 0, null, { timeout: 15000 }).catch(() => {});
  const eb = await p.evaluate(() => document.getElementById("eyebrow").textContent);
  ok(`${site} 목록 — 머리 줄 종목 수는 시세 자료 그대로`, eb === `국내 상장 ${PRE.live.toLocaleString("ko-KR")}개 종목 리포트`, eb);
  const n0 = await p.evaluate(() => +document.getElementById("countN").textContent.replace(/,/g, ""));
  ok(`${site} 목록 — 상장 전 종목 한 줄이 더해진다`, n0 === PRE.total + 1, `${n0} · 시세 자료 ${PRE.total}`);
  await p.fill("#searchInput", NAME); await p.waitForTimeout(300);
  const rows = await p.evaluate(() => [...document.querySelectorAll(".rl-row")].map((a) => [a.dataset.tk, a.innerText]));
  const me = rows.find(([t]) => t === TK);
  ok(`${site} 목록 — '엠비디' 검색에 엠비디가 나온다`, !!me && me[1].includes(NAME) && me[1].includes(REP.title.ko), JSON.stringify(rows.map(([t]) => t)));
  ok(`${site} 목록 — 가격 칸은 공모가`, !!me && /7,000원/.test(me[1]) && me[1].includes("공모가"), me && me[1].replace(/\s+/g, " "));
  await p.fill("#searchInput", "");
  await p.evaluate(() => { const R = window.__kosReports; R.state.sort = "date"; R.state.page = 1; R.render(); });
  const top = await p.evaluate(() => { const a = document.querySelector(".rl-row"); return a ? a.dataset.tk : ""; });
  ok(`${site} 목록 — 최신 리포트순 맨 위`, top === TK, top);
  ok(`${site} 목록 — 스크립트 오류가 없다`, errs.length === 0, errs.slice(0, 2).join(" / "));
  await ctx.close();
}

/* ── ④ 관심종목 — 종목 페이지에서 담은 상장 전 종목도 목록에 나온다 ── */
for (const [site, base] of SITES) {
  console.log(`\n── ${site} 관심종목 ──`);
  const { ctx, p, errs } = await open(base + "/Watchlist.html", PRE, { watch: [TK, "005930"] });
  await p.waitForFunction(() => document.querySelectorAll("#rows .row").length > 0, null, { timeout: 15000 }).catch(() => {});
  const rows = await p.evaluate(() => [...document.querySelectorAll("#rows .row")].map((a) => [a.dataset.tk, a.textContent]));
  const me = rows.find(([t]) => t === TK);
  ok(`${site} 관심종목 — 담아 둔 상장 전 종목이 나온다(공모가로)`, !!me && me[1].includes(NAME) && me[1].includes("공모가 7,000원"), JSON.stringify(rows.map(([t]) => t)));
  ok(`${site} 관심종목 — 상장 종목도 그대로`, rows.some(([t]) => t === "005930"), JSON.stringify(rows.map(([t]) => t)));
  ok(`${site} 관심종목 — 스크립트 오류가 없다`, errs.length === 0, errs.slice(0, 2).join(" / "));
  await ctx.close();
}

/* ── ⑤ 상장일 장 마감 뒤 — 시세 자료에 오르면 평소 줄 한 줄 ── */
for (const [site, base] of SITES) {
  console.log(`\n── ${site} 시세 자료에 오른 뒤 ──`);
  {
    const { ctx, p } = await open(base + "/Home.html", LISTED);
    await p.waitForFunction(() => document.querySelectorAll("#reportRows .row").length > 0, null, { timeout: 15000 }).catch(() => {});
    const mine = await p.evaluate((tk) => [...document.querySelectorAll("#reportRows .row")].filter((a) => a.getAttribute("href").includes(tk)).map((a) => a.innerText), TK);
    ok(`${site} 홈 — 한 줄이고 시세로 그린다(공모가 아님)`, mine.length === 1 && mine[0].includes("9,000원") && !mine[0].includes("공모가"), JSON.stringify(mine));
    const eb = await p.evaluate(() => document.getElementById("eyebrow").textContent);
    ok(`${site} 홈 — 머리 줄 종목 수에 들어간다`, eb === `국내 상장 ${LISTED.live.toLocaleString("ko-KR")}개 종목`, eb);
    await ctx.close();
  }
  {
    const { ctx, p } = await open(base + "/Reports.html", LISTED);
    await p.waitForFunction(() => document.querySelectorAll(".rl-row").length > 0, null, { timeout: 15000 }).catch(() => {});
    const n0 = await p.evaluate(() => +document.getElementById("countN").textContent.replace(/,/g, ""));
    ok(`${site} 목록 — 같은 종목을 두 번 세지 않는다`, n0 === LISTED.total, `${n0} · 시세 자료 ${LISTED.total}`);
    await p.fill("#searchInput", NAME); await p.waitForTimeout(300);
    const mine = await p.evaluate((tk) => [...document.querySelectorAll(".rl-row")].filter((a) => a.dataset.tk === tk).map((a) => a.innerText), TK);
    ok(`${site} 목록 — 한 줄이고 시세로 그린다`, mine.length === 1 && mine[0].includes("9,000원") && !mine[0].includes("공모가"), JSON.stringify(mine));
    await ctx.close();
  }
  {
    const landing = base ? base + "/index.html" : "/";
    const { ctx, p } = await open(landing, LISTED);
    const inp = p.locator("form.search input").first();
    await inp.click(); await inp.fill(NAME);
    await p.waitForFunction(() => document.querySelector("form.search .ac.show"), null, { timeout: 8000 }).catch(() => {});
    await p.waitForTimeout(300);
    const tks = await p.evaluate(() => [...document.querySelectorAll("form.search .ac.show .ac-item .ac-tk")].map((e) => e.textContent));
    ok(`${site} 첫 화면 — 후보에 한 번만`, tks.filter((t) => t === TK).length === 1, JSON.stringify(tks));
    await ctx.close();
  }
}

/* ── ⑥ 공모가가 없는 종목 — 공모 없이 상장하는 코넥스 종목(에이치스틸 · 2026-11-27) ──
   가격 칸은 종목 페이지(ipoLine)처럼 '상장일 YYYY-MM-DD'. 예전에는 '공모가 —'로 그려 공모가를 모르는 것처럼 읽혔고, 영어 사전에 없어
   영어 화면에도 한국어로 남았다(english.test 의 '약관 동의' 장면이 리포트 목록에서 잡았다 · 2026-11-25). */
{
  const NOOFF = scene("pre");
  const ix = JSON.parse(NOOFF.index.slice(NOOFF.index.indexOf("=") + 1).trim().replace(/;\s*$/, ""));
  const e = Object.assign({}, IPO, { market: "코넥스" }); delete e.offer_price;
  ix.ipo = { [TK]: e };
  NOOFF.index = "window.KOS_REPORTS = " + JSON.stringify(ix) + ";\n";
  for (const [site, base] of SITES) {
    console.log(`\n── ${site} 공모가가 없는 종목 ──`);
    for (const lang of ["ko", "en"]) {
      const { ctx, p, errs } = await open(base + "/Reports.html", NOOFF, { lang });
      await p.waitForFunction(() => document.querySelectorAll(".rl-row").length > 0, null, { timeout: 15000 }).catch(() => {});
      await p.evaluate(() => { const R = window.__kosReports; R.state.sort = "date"; R.state.page = 1; R.render(); });
      await p.waitForTimeout(lang === "en" ? 600 : 200);
      const cell = await p.evaluate((tk) => { const a = [...document.querySelectorAll(".rl-row")].find((r) => r.dataset.tk === tk);
        const c = a && a.querySelector(".r-price"); return c ? c.textContent.replace(/\s+/g, " ").trim() : null; }, TK);
      if (lang === "ko") ok(`${site} 목록 — 가격 칸은 '상장일 2026-11-24'('공모가 —' 아님)`, cell === "상장일 2026-11-24", cell);
      else ok(`${site} 목록(영어) — 'Listing date 2026-11-24' · 한국어 없음`, cell === "Listing date 2026-11-24", cell);
      ok(`${site} 목록(${lang}) — 스크립트 오류가 없다`, errs.length === 0, errs.slice(0, 2).join(" / "));
      await ctx.close();
    }
    {
      const { ctx, p } = await open(base + "/Watchlist.html", NOOFF, { watch: [TK] });
      await p.waitForFunction(() => document.querySelectorAll("#rows .row").length > 0, null, { timeout: 15000 }).catch(() => {});
      const t = await p.evaluate((tk) => { const a = [...document.querySelectorAll("#rows .row")].find((r) => r.dataset.tk === tk);
        const c = a && a.querySelector(".r-price"); return c ? c.textContent.replace(/\s+/g, " ").trim() : null; }, TK);
      ok(`${site} 관심종목 — 가격 칸은 '상장일 2026-11-24'`, t === "상장일 2026-11-24", t);
      await ctx.close();
    }
  }
}

await browser.close();
server.close();
console.log(`\n${pass} 통과 · ${fail} 실패`);
process.exit(fail ? 1 : 0);
