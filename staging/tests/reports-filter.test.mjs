/* 리포트 페이지의 숫자 조건 — 진짜 브라우저로 눌러 본다.
   ───────────────────────────────────────────────────────────
   스크리너에 있던 필터를 리포트 페이지로 가져왔다. 두 페이지가 같은 2,658개
   종목을 두 가지 방식으로 보여 주고 있었고, "PER 10배 이하인 종목의 리포트를
   읽자" 는 가장 자연스러운 요구가 어느 쪽에서도 되지 않았기 때문이다.

   여기서 확인하는 것은 크게 셋이다.

     ① 조건이 실제로 맞게 걸리는가
        화면이 말하는 개수를 믿지 않는다. 원자료에서 같은 조건을 직접 세어
        견준다 — 화면 코드가 틀리면 개수도 같이 틀리므로, 화면끼리 비교하면
        아무것도 못 잡는다.

     ② 안 쓰는 사람에게 짐을 지우지 않는가
        PER·PBR 값은 valuation.js(279KB)에 있다. 이 페이지는 이미 1.7MB 를
        받는데 필터를 한 번도 안 쓰는 사람이 대부분이다. 그래서 처음에는 받지
        않고 필터를 처음 건드릴 때 받는다. 그게 지켜지는지 본다.

     ③ 값을 못 받았을 때 조용히 망가지지 않는가
        받는 데 실패하면 PER 조건은 아무도 못 걸러낸다. 그때 '조건에 맞는
        종목 0개' 로 보이면, 사용자는 자기가 고른 조건이 너무 빡빡한 줄 안다.
        목록은 그대로 두는 것이 맞다.
   ───────────────────────────────────────────────────────────
   돌리려면:

     npm install --no-save playwright-core
*/
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, readdirSync } from "node:fs";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) {
  console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요.");
  process.exit(2);
}

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  const dir = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort().pop();
  const p = dir && `${base}/${dir}/chrome-linux/chrome`;
  return p && existsSync(p) ? p : null;
})();
if (!CHROME) { console.error("크로미움을 찾지 못했습니다."); process.exit(2); }

let pass = 0, fail = 0;
const ok = (name, cond, extra = "") => {
  if (cond) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + (extra ? "  ← " + extra : "")); }
};

const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
               ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json",
               ".ico": "image/x-icon", ".webmanifest": "application/manifest+json" };

/* 서버는 valuation.js 를 일부러 막을 수 있어야 한다 — ③을 보려면 필요하다. */
let blockVal = false;
const server = createServer(async (req, res) => {
  const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
  if (blockVal && rel.endsWith("valuation.js")) { res.writeHead(503); res.end("nope"); return; }
  try {
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: CHROME });

const DESK = { width: 1280, height: 960 };
const PHONE = { width: 390, height: 844 };

async function open(viewport = DESK) {
  const page = await browser.newPage({ viewport });
  await page.goto(BASE + "/staging/Reports.html", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(500);
  return page;
}
const shown = (p) => p.evaluate(() => +document.getElementById("countN").textContent);
const chips = (p) => p.evaluate(() => [...document.querySelectorAll(".fchip .lab")].map((e) => e.textContent));

/* 원자료에서 직접 센다. 화면과 같은 코드를 쓰지 않는 것이 요점이다. */
function countBy(page, fn) {
  return page.evaluate(`(${fn})(window.KOS_LIVE_DATA.stocks, window.KOS_VALUATION && KOS_VALUATION.stocks)`);
}

/* ── ② 안 쓰면 안 받는다 ────────────────────────────────── */
console.log("── 필터를 안 쓰면 밸류에이션 자료를 받지 않는다 ──\n");
{
  const p = await open();
  const st = await p.evaluate(() => ({
    n: +document.getElementById("countN").textContent,
    val: !!window.KOS_VALUATION,
    rows: document.querySelectorAll(".rl-row").length,
    /* 조건을 고르는 자리는 '필터 추가' 하나뿐이어야 한다. 업종 칩을 따로 두면
       같은 일을 하는 조작이 둘이 되어 어느 쪽이 이기는지 설명할 수 없다. */
    chips: document.querySelectorAll(".chip").length,
    presets: document.querySelectorAll(".preset-pill").length,
    fchips: document.getElementById("fchips").textContent.trim(),
  }));
  ok("처음에는 279KB 를 받지 않는다", st.val === false, "이미 받았다");
  ok("목록은 전과 같이 전부 나온다", st.n === 2686 || st.n > 2000, String(st.n));
  ok("한 화면에 20줄", st.rows === 20, String(st.rows));
  ok("업종 칩 줄이 없다", st.chips === 0, String(st.chips));
  ok("테마 줄이 없다", st.presets === 0, String(st.presets));
  ok("걸린 조건은 없다", st.fchips === "", st.fchips);

  await p.click("#addFilterBtn");
  await p.waitForTimeout(250);
  const list = await p.evaluate(() => [...document.querySelectorAll(".pop-field .fi")].map((e) => e.textContent));
  ok("업종이 조건 목록 맨 위에 있다", list[0] === "업종", JSON.stringify(list));
  ok("조건 일곱 가지를 준다",
     JSON.stringify(list) === JSON.stringify(["업종","시장","시가총액","PER","PBR","배당수익률","매출 성장률"]),
     JSON.stringify(list));
  ok("업종을 여는 데 279KB 가 필요하지 않다",
     await p.evaluate(() => document.querySelector('[data-field="sector"]') !== null));
  await p.close();
}

/* ── ① 조건이 맞게 걸리는가 ────────────────────────────── */
console.log("\n── 업종은 여러 개를 함께 고를 수 있다 ──\n");
{
  /* 칩으로 두었을 때는 하나밖에 못 골랐다. '반도체와 2차전지를 같이 보자' 가
     안 됐다는 뜻이다. */
  const p = await open();
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="sector"]'); await p.waitForTimeout(250);

  const heads = await p.evaluate(() => [...document.querySelectorAll(".check")].slice(0, 3)
    .map((c) => ({ name: c.dataset.v, n: +c.querySelector(".count").textContent })));
  ok("업종마다 종목 수를 같이 보여 준다", heads.every((h) => h.n > 0), JSON.stringify(heads));
  ok("많은 업종부터 나온다", heads[0].n >= heads[1].n && heads[1].n >= heads[2].n, JSON.stringify(heads));

  await p.evaluate(() => { for (const c of document.querySelectorAll(".check"))
    if (["반도체", "2차전지"].includes(c.dataset.v)) c.click(); });
  await p.click("#popApply"); await p.waitForTimeout(500);

  const got = await shown(p);
  const want = await countBy(p, `(S)=>S.filter(s=>{
    const c=(s.categories&&s.categories.length)?s.categories:[s.sector];
    return c.includes('반도체')||c.includes('2차전지');
  }).length`);
  ok("둘 다 걸린다(하나라도 맞으면 나온다)", got === want, `화면 ${got} · 직접 ${want}`);
  ok("칩이 몇 개인지 알려 준다", (await chips(p))[0] === "업종 · 반도체 외 1", JSON.stringify(await chips(p)));
  ok("업종만으로는 279KB 를 받지 않는다", (await p.evaluate(() => !!window.KOS_VALUATION)) === false);

  /* 화면에 뜬 줄이 실제로 그 업종인가 — 개수만 맞고 목록이 틀릴 수 있다. */
  const bad = await p.evaluate(() => [...document.querySelectorAll(".rl-row")].map((a) => a.dataset.tk)
    .filter((tk) => {
      const s = KOS_LIVE_DATA.stocks.find((x) => x.ticker === tk);
      const c = (s.categories && s.categories.length) ? s.categories : [s.sector];
      return !(c.includes("반도체") || c.includes("2차전지"));
    }));
  ok("보여 준 줄이 전부 그 업종이다", bad.length === 0, bad.join(","));
  await p.close();
}

console.log("\n── 조건을 직접 넣어도 같다 ──\n");
{
  const p = await open();
  await p.click("#addFilterBtn");
  await p.waitForTimeout(200);
  await p.click('[data-field="div"]');
  await p.waitForTimeout(150);
  await p.fill("#rMin", "4");
  await p.click("#popApply");
  await p.waitForTimeout(1200);

  const got = await shown(p);
  const want = await countBy(p, `(S,V)=>S.filter(s=>{
    const v=V&&V[s.ticker]; if(!v||v.dps==null||!s.price) return false;
    return +(v.dps/s.price*100).toFixed(2) >= 4;
  }).length`);
  ok("배당수익률 4% 이상 — 직접 센 것과 같다", got === want, `화면 ${got} · 직접 ${want}`);
  ok("칩에 조건이 적힌다", (await chips(p))[0] === "배당수익률 4% 이상", JSON.stringify(await chips(p)));

  /* 값을 줄에 같이 보여 준다 — 왜 걸렸는지 보이지 않으면 결과를 믿기 어렵다. */
  const badge = await p.evaluate(() => {
    const m = document.querySelector(".rl-row .mval");
    return m ? m.textContent : null;
  });
  ok("걸어 둔 값이 줄에 보인다", badge && badge.startsWith("배당수익률"), String(badge));
  await p.close();
}

console.log("\n── 업종·숫자·검색이 함께 걸린다(전부 만족) ──\n");
{
  const p = await open();
  // 업종 = 금융
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="sector"]'); await p.waitForTimeout(250);
  await p.evaluate(() => { const c = [...document.querySelectorAll(".check")]
    .find((x) => x.dataset.v === "금융"); if (c) c.click(); });
  await p.click("#popApply"); await p.waitForTimeout(400);
  // PER 10배 이하
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="per"]'); await p.waitForTimeout(200);
  await p.fill("#rMax", "10");
  await p.click("#popApply"); await p.waitForTimeout(1400);

  const got = await shown(p);
  const want = await countBy(p, `(S,V)=>S.filter(s=>{
    const cats=(s.categories&&s.categories.length)?s.categories:[s.sector];
    if(!cats.includes('금융')) return false;
    const v=V&&V[s.ticker]; if(!v) return false;
    const per=(v.eps&&v.eps>0&&s.price)?+(s.price/v.eps).toFixed(1):null;
    return per!=null && per<=10;
  }).length`);
  ok("업종과 숫자 조건이 함께 걸린다", got === want, `화면 ${got} · 직접 ${want}`);
  ok("조건 둘이 칩으로 보인다", (await chips(p)).length === 2, JSON.stringify(await chips(p)));

  await p.fill("#searchInput", "은행");
  await p.waitForTimeout(300);
  const got2 = await shown(p);
  ok("검색까지 더해도 좁아지기만 한다", got2 <= got, `${got2} vs ${got}`);
  await p.close();
}

console.log("\n── 조건을 빼는 길 ──\n");
{
  const p = await open();
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="mcap"]'); await p.waitForTimeout(200);
  await p.fill("#rMin", "0.5"); await p.click("#popApply"); await p.waitForTimeout(400);
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="div"]'); await p.waitForTimeout(200);
  await p.fill("#rMin", "4"); await p.click("#popApply"); await p.waitForTimeout(1400);
  const two = await shown(p);

  await p.click('.fchip [data-remove="div"]');
  await p.waitForTimeout(300);
  ok("✕ 를 누르면 그 조건만 빠진다",
     JSON.stringify(await chips(p)) === JSON.stringify(["시가총액 0.5조 이상"]),
     JSON.stringify(await chips(p)));
  ok("남는 종목이 늘어난다", (await shown(p)) > two, `${await shown(p)} vs ${two}`);

  await p.click("#clearAll");
  await p.waitForTimeout(300);
  ok("모두 지우면 처음으로 돌아온다", (await shown(p)) === 2686 || (await shown(p)) > 2000,
     String(await shown(p)));
  ok("칩도 사라진다", (await chips(p)).length === 0);
  await p.close();
}

console.log("\n── 업종 체크를 다 풀면 조건이 빠진다 ──\n");
{
  /* 체크를 하나도 안 남기고 '적용'을 누르면 '아무 업종도 아닌 것' 이 아니라
     '업종을 안 따짐' 이어야 한다. 반대로 두면 목록이 통째로 빈다. */
  const p = await open();
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="sector"]'); await p.waitForTimeout(250);
  await p.evaluate(() => { const c = [...document.querySelectorAll(".check")]
    .find((x) => x.dataset.v === "반도체"); if (c) c.click(); });
  await p.click("#popApply"); await p.waitForTimeout(400);
  const some = await shown(p);
  ok("업종 하나를 고르면 좁아진다", some > 0 && some < 2000, String(some));

  await p.click(".fchip"); await p.waitForTimeout(300);      // 칩을 눌러 다시 연다
  await p.evaluate(() => { const c = [...document.querySelectorAll(".check.on")][0]; if (c) c.click(); });
  await p.click("#popApply"); await p.waitForTimeout(400);
  ok("다 풀면 전체로 돌아온다", (await shown(p)) > 2000, String(await shown(p)));
  ok("칩도 사라진다", (await chips(p)).length === 0, JSON.stringify(await chips(p)));
  await p.close();
}

console.log("\n── 값이 없는 종목은 정렬에서 뒤로 ──\n");
{
  const p = await open();
  await p.click("#sortBtn"); await p.waitForTimeout(150);
  await p.click('#sortMenu button[data-v="per_asc"]');
  await p.waitForTimeout(1500);
  const first = await p.evaluate(() => {
    const tks = [...document.querySelectorAll(".rl-row")].map((a) => a.dataset.tk);
    const V = (window.KOS_VALUATION && KOS_VALUATION.stocks) || {};
    return tks.map((tk) => {
      const s = KOS_LIVE_DATA.stocks.find((x) => x.ticker === tk), v = V[tk];
      return (v && v.eps > 0 && s) ? +(s.price / v.eps).toFixed(1) : null;
    });
  });
  ok("PER 낮은 순을 고르면 자료를 받는다", await p.evaluate(() => !!window.KOS_VALUATION));
  ok("첫 화면이 '—' 로 차지 않는다", first.filter((x) => x == null).length === 0,
     JSON.stringify(first.slice(0, 5)));
  ok("작은 값부터 나온다", first.every((v, i) => i === 0 || first[i - 1] <= v),
     JSON.stringify(first.slice(0, 5)));
  await p.close();
}

console.log("\n── 조건 때문에 비면 다른 말을 한다 ──\n");
{
  const p = await open();
  await p.click("#addFilterBtn"); await p.waitForTimeout(200);
  await p.click('[data-field="per"]'); await p.waitForTimeout(150);
  await p.fill("#rMin", "9999"); await p.fill("#rMax", "10000");
  await p.click("#popApply");
  await p.waitForTimeout(1400);
  const st = await p.evaluate(() => ({
    n: +document.getElementById("countN").textContent,
    msg: document.getElementById("emptyMsg").textContent,
    reset: getComputedStyle(document.getElementById("emptyActs")).display !== "none",
  }));
  ok("아무것도 안 남는다", st.n === 0, String(st.n));
  ok("검색어 탓이 아니라고 말해 준다", st.msg.includes("조건"), st.msg);
  ok("초기화 버튼을 준다", st.reset);
  await p.click("#emptyReset"); await p.waitForTimeout(300);
  ok("초기화하면 돌아온다", (await shown(p)) > 2000, String(await shown(p)));
  await p.close();
}

/* ── ③ 자료를 못 받았을 때 ─────────────────────────────── */
console.log("\n── 밸류에이션 자료를 못 받아도 목록이 비지 않는다 ──\n");
{
  blockVal = true;
  const p = await open();
  const before = await shown(p);
  // 값이 필요한 조건(PER)과 필요 없는 조건(시가총액)을 함께 건다.
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="mcap"]'); await p.waitForTimeout(200);
  await p.fill("#rMin", "0.5"); await p.click("#popApply"); await p.waitForTimeout(400);
  await p.click("#addFilterBtn"); await p.waitForTimeout(250);
  await p.click('[data-field="per"]'); await p.waitForTimeout(300);
  await p.fill("#rMax", "10"); await p.click("#popApply"); await p.waitForTimeout(1800);
  const after = await shown(p);
  ok("자료를 정말 못 받았다", (await p.evaluate(() => !!window.KOS_VALUATION)) === false);
  ok("목록이 0 으로 떨어지지 않는다", after > 0, String(after));
  ok("시가총액 조건은 그대로 걸린다", after < before, `${after} vs ${before}`);
  ok("걸어 둔 조건은 칩에 그대로 남는다", (await chips(p)).length === 2, JSON.stringify(await chips(p)));
  blockVal = false;
  await p.close();
}

/* ── 휴대폰 ──────────────────────────────────────────── */
console.log("\n── 휴대폰에서 시트로 열린다 ──\n");
{
  const p = await open(PHONE);
  await p.click("#addFilterBtn");
  await p.waitForTimeout(400);
  const st = await p.evaluate(() => {
    const pop = document.querySelector(".popover"), r = pop.getBoundingClientRect();
    const bar = document.querySelector(".kos-staging-bar").getBoundingClientRect();
    return { sheet: pop.classList.contains("sheet"), open: pop.classList.contains("open"),
             bottom: Math.round(r.bottom), h: innerHeight, left: Math.round(r.left),
             /* 시트 폭은 innerWidth 가 아니라 '배치에 쓰이는 폭'과 견준다.
                여기(데스크톱 크로미움)는 세로 스크롤바가 자리를 15px 차지해
                innerWidth 390 · 배치 폭 375 로 갈린다. 진짜 휴대폰의 스크롤바는
                내용 위에 겹쳐 그려져 자리를 안 먹으므로 둘이 같다. innerWidth 로
                재면 실제로는 꽉 찬 시트를 두고 매번 실패한다. */
             w: Math.round(r.width), vw: Math.round(document.body.getBoundingClientRect().width),
             zPop: +getComputedStyle(pop).zIndex, zBar: +getComputedStyle(document.querySelector(".kos-staging-bar")).zIndex,
             barBottom: Math.round(bar.bottom), top: Math.round(r.top) };
  });
  ok("아래에서 올라오는 시트가 된다", st.sheet && st.open, JSON.stringify(st));
  ok("화면 아래에 붙는다", Math.abs(st.bottom - st.h) < 2, `${st.bottom} vs ${st.h}`);
  ok("가로를 꽉 채운다", st.left === 0 && Math.abs(st.w - st.vw) < 2, JSON.stringify(st));
  ok("STAGING 띠에 가리지 않는다", st.zPop > st.zBar || st.top >= st.barBottom,
     `팝오버 z${st.zPop} top${st.top} · 띠 z${st.zBar} bottom${st.barBottom}`);

  await p.click('[data-field="mcap"]'); await p.waitForTimeout(200);
  await p.click('.range-quick button[data-qi="2"]');   // 10조원 이상
  await p.click("#popApply"); await p.waitForTimeout(600);
  const got = await shown(p);
  const want = await countBy(p, `(S)=>S.filter(s=>s.mcap>=10).length`);
  ok("휴대폰에서도 조건이 걸린다", got === want, `화면 ${got} · 직접 ${want}`);

  /* 조건을 걸어도 가로로 밀리면 안 된다 — 줄에 값이 붙기 때문이다. */
  const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  ok("가로 스크롤이 생기지 않는다", over <= 1, `${over}px 넘침`);
  await p.close();
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
