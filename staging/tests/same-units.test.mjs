/* ============================================================
   돈·주식 수 표기 — 스테이징이 실사이트와 같은가

   왜 있는가. 실사이트 stock.html 은 값마다 조·억·만을 붙인다
   ('302.2조' · '-747억' · '4,000억원' · '3,000만주'). 새 디자인은 한때 '조원' 하나로
   고정해 작은 회사의 실적 표·차트가 0.0 · -0.0 으로, 시가총액이 0.4조원으로, 주식 수가
   0.3억주로 나왔다(2026-09-26 · 리포트 2,551곳 중 2,261곳). 실사이트는 예전에 이미 고친
   버그였다. 같은 숫자를 세 곳이 따로 쓴다 — 실사이트 stock.html(JS) · 스테이징
   stock.html(JS · scripts/build_stock_staging.py) · 미리 만드는 종목 페이지(파이썬 ·
   scripts/stock_page.py). 한쪽만 바뀌면 여기서 걸린다.

   보는 것
     1. 포매터 — 진짜 값 전부(리포트의 매출·영업이익·순이익, 시세의 시가총액·거래대금·
        거래량·주식 수)와 경계값(딱 반 · 단위가 바뀌는 자리)을 넣으면 세 쪽이 글자 하나까지
        같다. 빈 값은 스테이징·파이썬 모두 '—'.
     2. 화면 — 진짜 브라우저로 실사이트와 스테이징의 같은 종목을 열면 실적 표의 돈 칸,
        차트 값 라벨, 지표 넷(시가총액·거래대금·거래량·상장주식수)이 같다. 스테이징 표·차트에
        '0.0' 이 없다. 종목은 작은 적자 회사(HLB) · 초대형(삼성전자) · 1억 미만 값(모나리자).

   실행
     node staging/tests/same-units.test.mjs
   ============================================================ */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { dirname, extname, join, normalize } from "node:path";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
let pass = 0, fail = 0;
const ok = (cond, name, extra) => { cond ? pass++ : fail++; console.log(`${cond ? "PASS" : "FAIL"}  ${name}${cond || !extra ? "" : "  ← " + extra}`); };
const n = (x) => x.toLocaleString("en-US");

/* ── 1. 포매터 ─────────────────────────────────────────────── */
console.log("── 포매터: 실사이트 · 스테이징 JS · 파이썬이 같은 글자를 낸다 ──\n");

function grab(html, file, name) {
  const key = "function " + name + "(";
  const i = html.indexOf(key);
  if (i < 0) throw new Error(`${file} 에 ${name} 이 없다`);
  if (html.indexOf(key, i + 1) >= 0) throw new Error(`${file} 에 ${name} 이 둘 이상이다`);
  let depth = 0;
  for (let k = html.indexOf("{", i); k < html.length; k++) {
    if (html[k] === "{") depth++;
    else if (html[k] === "}" && --depth === 0) return html.slice(i, k + 1);
  }
  throw new Error(`${file} 의 ${name} 이 닫히지 않는다`);
}
const liveHtml = readFileSync(join(ROOT, "stock.html"), "utf8");
const stageHtml = readFileSync(join(ROOT, "staging/stock.html"), "utf8");
/* 실사이트는 한·영 두 벌이다 — 한국어 쪽(L()==='ko')과 비교한다 */
const LIVE = new Function("function L(){ return 'ko'; }\n"
  + ["fwon", "mcap", "amt", "vol", "shN"].map((f) => grab(liveHtml, "stock.html", f)).join("\n")
  + "\nreturn { fwon, mcap, amt, vol, shN };")();
const STAGE = new Function(["fwon", "mcap", "amt", "shN"].map((f) => grab(stageHtml, "staging/stock.html", f)).join("\n")
  + "\nreturn { fwon, mcap, amt, shN };")();

/* 진짜 값 */
const WON = [];
const dir = join(ROOT, "data/reports_v2");
for (const f of readdirSync(dir)) {
  if (!f.endsWith(".json")) continue;
  let q; try { q = JSON.parse(readFileSync(join(dir, f), "utf8")).quant; } catch { continue; }
  if (!q || typeof q !== "object") continue;
  for (const r of [...(q.annual || []), ...(q.quarterly || [])])
    for (const k of ["rev", "op", "np_owner"]) if (r && typeof r[k] === "number") WON.push(r[k]);
}
const STOCKS = new Function("window", readFileSync(join(ROOT, "data/stocks.js"), "utf8") + "\nreturn window.KOS_LIVE_DATA;")({}).stocks;
const pick = (k) => STOCKS.map((s) => s[k]).filter((v) => typeof v === "number");

/* 경계값 — 딱 반(자바스크립트는 올리고 파이썬 format 은 짝수로 붙인다) · 단위가 바뀌는 자리 ·
   이진수로는 반 아래인 값(1.15 · 8.45 — toFixed 는 내리고 toLocaleString 은 올린다) */
const EDGE = {
  won: [0, 0.5, 1, 2.5, -2.5, 99999999, 99999999.5, 1e8, -1e8, 12250000000, -12250000000, 12350000000,
        999949999999, 999950000000, 999999999999, 1e12, 1.25e12, -1.25e12, 1.35e12, 302.2e12, 1234.56e12],
  jo: [0, 0.00004, 0.00005, 0.5, 0.99994, 0.99995, 0.99999, 1, 1.04, 1.05, 1.15, 1.25, 2.95, 3, 3.05, 8.45, 10, 999.95, 1669.1125, 12345.65],
  amt: [0, 1, 0.5, 99999999, 99999999.5, 1e8, 1.5e8, 12250000000, 999950000000, 999999999999, 1e12, 1.25e12, 5926486634990],
  shares: [0, 1, 9999, 10000, 15000, 25000, 35000, 99994999, 99995000, 99999999, 1e8, 125000000, 5846278608, 1234.5678, 1.0005],
};
const IN = {
  won: WON.concat(EDGE.won),
  jo: pick("mcap").concat(EDGE.jo),
  amt: pick("trading_value").concat(EDGE.amt),
  shares: pick("volume").concat(pick("shares"), EDGE.shares),
};

const py = spawnSync("python3", ["-c",
  "import json,sys; sys.path.insert(0,'scripts'); import stock_page as S; I=json.load(sys.stdin); "
  + "print(json.dumps({'won':[S.fwon(v) for v in I['won']],'jo':[S.fmcap(v) for v in I['jo']],"
  + "'amt':[S.famt(v) for v in I['amt']],'shares':[S.fshares(v) for v in I['shares']],"
  + "'none':[S.fwon(None),S.fmcap(None),S.famt(None),S.fshares(None)]}, ensure_ascii=False))"],
  { cwd: ROOT, input: JSON.stringify(IN), encoding: "utf8", maxBuffer: 64 << 20 });
if (py.status !== 0) { console.error(py.stderr); process.exit(2); }
const PY = JSON.parse(py.stdout);

function same(name, key, liveFns, stageFn) {
  const bad = [];
  IN[key].forEach((v, i) => {
    const a = liveFns.map((f) => f(v)), b = stageFn(v), c = PY[key][i];
    if (a.some((x) => x !== b) || b !== c) bad.push(`${v}: 실사이트 ${a[0]} · 스테이징 ${b} · 파이썬 ${c}`);
  });
  ok(!bad.length, `${name} — 값 ${n(IN[key].length)}개(경계 ${EDGE[key].length}개 포함)가 세 쪽에서 같다`, bad.slice(0, 4).join(" | "));
}
same("실적 fwon(매출·영업이익·순이익)", "won", [LIVE.fwon], STAGE.fwon);
same("시가총액 mcap", "jo", [LIVE.mcap], STAGE.mcap);
same("거래대금 amt", "amt", [LIVE.amt], STAGE.amt);
same("거래량·상장주식수 vol·shN", "shares", [LIVE.vol, LIVE.shN], STAGE.shN);

const stageNone = [STAGE.fwon(null), STAGE.mcap(null), STAGE.amt(null), STAGE.shN(null)];
ok(stageNone.every((s) => s === "—") && PY.none.every((s) => s === "—"), "빈 값은 스테이징·파이썬 모두 '—'", `JS ${stageNone} · PY ${PY.none}`);

/* ── 2. 화면 ────────────────────────────────────────────────── */
console.log("\n── 화면: 실사이트와 스테이징의 같은 종목이 같은 숫자를 보인다 ──\n");

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) {
  console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요.");
  process.exit(2);
}
/* 깔려 있는 크로미움 — 판마다 폴더 이름이 다르다(chrome-linux · chrome-linux64). layout.test.mjs 와 같은 방법 */
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) for (const sub of ["chrome-linux64", "chrome-linux"]) {
    const p = `${base}/${d}/${sub}/chrome`;
    if (existsSync(p)) return p;
  }
  return null;
})();
if (!CHROME) { console.error("크로미움을 찾지 못했습니다(PLAYWRIGHT_BROWSERS_PATH 확인)."); process.exit(2); }

const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2" };
const server = createServer(async (req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: CHROME });

/* 표 한 장 → { 연도·분기: [칸…] } */
const READ = (side) => {
  const rows = (t) => Object.fromEntries(t ? [...t.querySelectorAll("tbody tr")].map((tr) => {
    const c = [...tr.children].map((x) => x.textContent.trim());
    return [c[0], c.slice(1)];
  }) : []);
  if (side === "live") {
    const tbl = (w) => [...document.querySelectorAll(".tbl-card")].find((c) => (c.querySelector(".tbl-cap")?.textContent || "").includes(w))?.querySelector("table");
    return {
      annual: rows(tbl("연간")), quarterly: rows(tbl("분기")),
      labels: [...document.querySelectorAll("svg.kchart text.blabel")].map((t) => t.textContent.trim()).filter((s) => !s.endsWith("%")),
      stats: Object.fromEntries([...document.querySelectorAll("#mgrid .m")].map((m) => [m.querySelector(".k").textContent.trim(), m.querySelector(".val").textContent.trim()])),
    };
  }
  const tbl = (w) => [...document.querySelectorAll("table.tbl")].find((t) => (t.querySelector("caption")?.textContent || "").includes(w));
  return {
    annual: rows(tbl("연간 실적")), quarterly: rows(tbl("분기 실적")),
    labels: [...document.querySelectorAll(".ch .ch-val")].map((s) => s.textContent.trim()),
    stats: Object.fromEntries([...document.querySelectorAll(".st")].map((s) => [s.querySelector(".st-k").textContent.trim(), s.querySelector(".st-v").textContent.trim()])),
  };
};
async function view(side, tk) {
  const page = await browser.newPage();
  page.on("pageerror", () => {});
  const url = side === "live" ? `${BASE}/stock.html?ticker=${tk}` : `${BASE}/staging/stock.html?ticker=${tk}&paywall=0`;
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(side === "live" ? ".tbl-card table tbody tr" : "table.tbl tbody tr", { timeout: 20000 });
  await page.waitForTimeout(200);
  const got = await page.evaluate(READ, side);
  await page.close();
  return got;
}

const STAT_KEYS = ["시가총액", "거래대금", "거래량", "상장주식수"];
const TICKERS = [["028300", "HLB · 작은 적자 회사"], ["005930", "삼성전자 · 초대형"], ["012690", "모나리자 · 1억 미만 값"]];
for (const [tk, what] of TICKERS) {
  const L = await view("live", tk), S = await view("staging", tk);
  /* 돈 칸만 본다 — 연간: 매출·영업이익·순이익, 분기: 매출·영업이익(비율 칸의 빼기표 글리프는 따로 정할 일이다) */
  const diff = [];
  const cmp = (kind, a, b, cols) => {
    const keys = Object.keys(b);
    if (!keys.length) diff.push(`${kind} 표가 비었다`);
    for (const k of keys) for (const c of cols) if (a[k]?.[c] !== b[k][c]) diff.push(`${kind} ${k} ${c + 1}칸: 실사이트 ${a[k]?.[c]} · 스테이징 ${b[k][c]}`);
  };
  cmp("연간", L.annual, S.annual, [0, 1, 2]);
  cmp("분기", L.quarterly, S.quarterly, [0, 1]);
  ok(!diff.length, `${tk} ${what} — 실적 표의 돈 칸이 실사이트와 같다 (연간 ${Object.keys(S.annual).length} · 분기 ${Object.keys(S.quarterly).length}줄)`, diff.slice(0, 4).join(" | "));

  const la = [...L.labels].sort().join(" "), lb = [...S.labels].sort().join(" ");
  ok(S.labels.length > 0 && la === lb, `${tk} ${what} — 차트 값 라벨 ${S.labels.length}개가 실사이트와 같다`, `실사이트 ${la} | 스테이징 ${lb}`);

  const sd = STAT_KEYS.filter((k) => L.stats[k] !== S.stats[k]).map((k) => `${k} 실사이트 ${L.stats[k]} · 스테이징 ${S.stats[k]}`);
  ok(!sd.length, `${tk} ${what} — 지표 넷이 실사이트와 같다 (${STAT_KEYS.map((k) => S.stats[k]).join(" · ")})`, sd.join(" | "));

  const cells = [...Object.values(S.annual).flatMap((c) => c.slice(0, 3)), ...Object.values(S.quarterly).flatMap((c) => c.slice(0, 2)), ...S.labels];
  const zero = cells.filter((s) => /^-?0\.0$/.test(s));
  ok(!zero.length, `${tk} ${what} — 스테이징 표·차트에 0.0 이 없다`, zero.join(" "));
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
