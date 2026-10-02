/* ============================================================
   돈·주식 수 표기 — 실사이트 · 스테이징 · 파이썬이 같은 글자를 내는가

   왜 있는가. 실사이트 stock.html 은 값마다 조·억·만을 붙인다
   ('302.2조' · '-747억' · '4,000억원' · '3,000만주'). 새 디자인은 한때 '조원' 하나로
   고정해 작은 회사의 실적 표·차트가 0.0 · -0.0 으로, 시가총액이 0.4조원으로, 주식 수가
   0.3억주로 나왔다(2026-09-26 · 리포트 2,551곳 중 2,261곳). 실사이트는 예전에 이미 고친
   버그였다. 같은 숫자를 세 곳이 따로 쓴다 — 실사이트 stock.html(JS) · 스테이징
   stock.html(JS) · 미리 만드는 종목 페이지(파이썬 · scripts/stock_page.py). 한쪽만 바뀌면
   여기서 걸린다.

   2026-10-03 부터 실사이트 stock.html 도 스테이징과 같은 생성기(scripts/build_stock_staging.py
   의 live 판)가 만든다. 손으로 쓴 옛 실사이트 포매터(fwon · mcap · amt · vol · shN)는 그때
   없어졌다. 그 코드가 '실사이트 방식'(CLAUDE.md)의 기준이었으므로, 그것이 경계값에 내던 글자를
   아래 EDGE 에 그대로 박아 두었다 — 세 쪽이 함께 바뀌어도 여기서 걸린다.

   보는 것
     1. 포매터 — 진짜 값 전부(리포트의 매출·영업이익·순이익, 시세의 시가총액·거래대금·
        거래량·주식 수)와 경계값(딱 반 · 단위가 바뀌는 자리)을 넣으면 세 쪽이 글자 하나까지
        같다. 경계값은 옛 실사이트가 내던 글자와도 같다. 빈 값은 세 쪽 모두 '—'.
     2. 화면 — 진짜 브라우저로 실사이트와 스테이징에서 같은 종목을 열면 실적 표의 돈 칸,
        차트 값 라벨, 지표 넷(시가총액·거래대금·거래량·상장주식수)이 같은 자료(data/reports_v2 ·
        data/stocks.js)를 파이썬 stock_page 로 바꾼 글자와 같다 — 그래서 두 사이트끼리도 같다.
        표·차트에 '0.0' 이 없다. 종목은 작은 적자 회사(HLB) · 초대형(삼성전자) · 1억 미만 값(모나리자).

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
console.log("── 포매터: 실사이트 JS · 스테이징 JS · 파이썬이 같은 글자를 낸다 ──\n");

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
/* 두 사이트 모두 같은 넷을 쓴다 — 실적 fwon · 시가총액 mcap · 거래대금 amt · 거래량과 상장주식수 shN */
const FNS = ["fwon", "mcap", "amt", "shN"];
const load = (file) => new Function(FNS.map((f) => grab(readFileSync(join(ROOT, file), "utf8"), file, f)).join("\n")
  + `\nreturn { ${FNS.join(", ")} };`)();
const LIVE = load("stock.html");
const STAGE = load("staging/stock.html");
const FN_OF = { won: "fwon", jo: "mcap", amt: "amt", shares: "shN" };

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
   이진수로는 반 아래인 값(1.15 · 8.45 — toFixed 는 내리고 toLocaleString 은 올린다).
   [넣는 값, 옛 실사이트가 내던 글자] — 2026-10-02 까지의 손으로 쓴 stock.html(한국어 쪽)에서 뽑았다.
   주식 수는 옛 실사이트의 vol(거래량) · shN(상장주식수) 둘이 같은 글자를 냈다. */
const EDGE = {
  won: [[0, "0원"], [0.5, "1원"], [1, "1원"], [2.5, "3원"], [-2.5, "-3원"], [99999999, "99,999,999원"],
        [99999999.5, "100,000,000원"], [1e8, "1억"], [-1e8, "-1억"], [12250000000, "123억"], [-12250000000, "-123억"],
        [12350000000, "124억"], [999949999999, "9,999억"], [999950000000, "10,000억"], [999999999999, "10,000억"],
        [1e12, "1.0조"], [1.25e12, "1.3조"], [-1.25e12, "-1.3조"], [1.35e12, "1.4조"], [302.2e12, "302.2조"],
        [1234.56e12, "1234.6조"]],
  jo: [[0, "0억원"], [0.00004, "0억원"], [0.00005, "1억원"], [0.5, "5,000억원"], [0.99994, "9,999억원"],
       [0.99995, "10,000억원"], [0.99999, "10,000억원"], [1, "1조원"], [1.04, "1조원"], [1.05, "1.1조원"],
       [1.15, "1.2조원"], [1.25, "1.3조원"], [2.95, "3조원"], [3, "3조원"], [3.05, "3.1조원"], [8.45, "8.5조원"],
       [10, "10조원"], [999.95, "1,000조원"], [1669.1125, "1,669.1조원"], [12345.65, "12,345.7조원"]],
  amt: [[0, "0원"], [1, "1원"], [0.5, "1원"], [99999999, "99,999,999원"], [99999999.5, "100,000,000원"],
        [1e8, "1억원"], [1.5e8, "2억원"], [12250000000, "123억원"], [999950000000, "10,000억원"],
        [999999999999, "10,000억원"], [1e12, "1.0조원"], [1.25e12, "1.3조원"], [5926486634990, "5.9조원"]],
  shares: [[0, "0주"], [1, "1주"], [9999, "9,999주"], [10000, "1만주"], [15000, "2만주"], [25000, "3만주"],
           [35000, "4만주"], [99994999, "9,999만주"], [99995000, "10,000만주"], [99999999, "10,000만주"],
           [1e8, "1.0억주"], [125000000, "1.3억주"], [5846278608, "58.5억주"], [1234.5678, "1,234.568주"], [1.0005, "1.001주"]],
};
const REAL = {
  won: WON,
  jo: pick("mcap"),
  amt: pick("trading_value"),
  shares: pick("volume").concat(pick("shares")),
};
const IN = Object.fromEntries(Object.keys(EDGE).map((k) => [k, REAL[k].concat(EDGE[k].map((p) => p[0]))]));

/* ── 2 에서 쓸 화면 기대값도 같은 파이썬에서 받는다 — 같은 자료를 stock_page 로 바꾼 글자 ── */
const STAT_KEYS = ["시가총액", "거래대금", "거래량", "상장주식수"];
const TICKERS = [["028300", "HLB · 작은 적자 회사"], ["005930", "삼성전자 · 초대형"], ["012690", "모나리자 · 1억 미만 값"]];
const RAW = {};
for (const [tk] of TICKERS) {
  const q = JSON.parse(readFileSync(join(ROOT, `data/reports_v2/${tk}.json`), "utf8")).quant || {};
  const st = STOCKS.find((s) => s.ticker === tk) || {};
  RAW[tk] = {   // JSON 으로 넘기면 빠진 값(undefined)은 null — 파이썬에서 None, 화면에서 '—'
    annual: (q.annual || []).map((a) => [String(a.year), a.rev ?? null, a.op ?? null, a.np_owner ?? null]),
    quarterly: (q.quarterly || []).map((x) => [String(x.q), x.rev ?? null, x.op ?? null]),
    stats: [st.mcap ?? null, st.trading_value ?? null, st.volume ?? null, st.shares ?? null],
  };
}

const py = spawnSync("python3", ["-c", `
import json, sys
sys.path.insert(0, 'scripts')
import stock_page as S
I = json.load(sys.stdin)
F = S.fwon
screen = {}
for tk, r in I['screen'].items():
    screen[tk] = {
        'annual': {a[0]: [F(a[1]), F(a[2]), F(a[3])] for a in r['annual']},
        'quarterly': {x[0]: [F(x[1]), F(x[2])] for x in r['quarterly']},
        # 차트 — 분기 · 연간 막대마다 매출 · 영업이익(빈 값은 라벨이 없다)
        'labels': [F(v) for g in r['quarterly'] + r['annual'] for v in g[1:3] if v is not None],
        'stats': [S.fmcap(r['stats'][0]), S.famt(r['stats'][1]), S.fshares(r['stats'][2]), S.fshares(r['stats'][3])],
    }
print(json.dumps({'won': [S.fwon(v) for v in I['won']], 'jo': [S.fmcap(v) for v in I['jo']],
                  'amt': [S.famt(v) for v in I['amt']], 'shares': [S.fshares(v) for v in I['shares']],
                  'none': [S.fwon(None), S.fmcap(None), S.famt(None), S.fshares(None)], 'screen': screen}, ensure_ascii=False))
`], { cwd: ROOT, input: JSON.stringify({ ...IN, screen: RAW }), encoding: "utf8", maxBuffer: 64 << 20 });
if (py.status !== 0) { console.error(py.stderr); process.exit(2); }
const PY = JSON.parse(py.stdout);

function same(name, key) {
  const f = FN_OF[key], bad = [], old = [], base = REAL[key].length;
  IN[key].forEach((v, i) => {
    const a = LIVE[f](v), b = STAGE[f](v), c = PY[key][i];
    if (a !== b || b !== c) bad.push(`${v}: 실사이트 ${a} · 스테이징 ${b} · 파이썬 ${c}`);
    if (i >= base && b !== EDGE[key][i - base][1]) old.push(`${v}: 지금 ${b} · 옛 실사이트 ${EDGE[key][i - base][1]}`);
  });
  ok(!bad.length, `${name} — 값 ${n(IN[key].length)}개(경계 ${EDGE[key].length}개 포함)가 세 쪽에서 같다`, bad.slice(0, 4).join(" | "));
  ok(!old.length, `${name} — 경계값 ${EDGE[key].length}개가 옛 실사이트 글자와 같다`, old.slice(0, 4).join(" | "));
}
same("실적 fwon(매출·영업이익·순이익)", "won");
same("시가총액 mcap", "jo");
same("거래대금 amt", "amt");
same("거래량·상장주식수 shN", "shares");

const noneOf = (S) => [S.fwon(null), S.mcap(null), S.amt(null), S.shN(null)];
ok([...noneOf(LIVE), ...noneOf(STAGE), ...PY.none].every((s) => s === "—"), "빈 값은 실사이트·스테이징·파이썬 모두 '—'",
   `실사이트 ${noneOf(LIVE)} · 스테이징 ${noneOf(STAGE)} · 파이썬 ${PY.none}`);

/* ── 2. 화면 ────────────────────────────────────────────────── */
console.log("\n── 화면: 실사이트와 스테이징이 같은 종목에서 파이썬과 같은 숫자를 보인다 ──\n");

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

/* 표 한 장 → { 연도·분기: [칸…] } — 두 사이트가 같은 마크업이다(table.tbl · .ch .ch-val · .st) */
const READ = () => {
  const rows = (t) => Object.fromEntries(t ? [...t.querySelectorAll("tbody tr")].map((tr) => {
    const c = [...tr.children].map((x) => x.textContent.trim());
    return [c[0], c.slice(1)];
  }) : []);
  const tbl = (w) => [...document.querySelectorAll("table.tbl")].find((t) => (t.querySelector("caption")?.textContent || "").includes(w));
  return {
    annual: rows(tbl("연간 실적")), quarterly: rows(tbl("분기 실적")),
    labels: [...document.querySelectorAll(".ch .ch-val")].map((s) => s.textContent.trim()),
    stats: Object.fromEntries([...document.querySelectorAll(".st")].map((s) => [s.querySelector(".st-k").textContent.trim(), s.querySelector(".st-v").textContent.trim()])),
  };
};
const SITES = [["실사이트", (tk) => `${BASE}/stock.html?ticker=${tk}`],
               ["스테이징", (tk) => `${BASE}/staging/stock.html?ticker=${tk}&paywall=0`]];
async function view(url) {
  const page = await browser.newPage();
  page.on("pageerror", () => {});
  await page.route("**gstatic.com/**", (r) => r.abort());   // 파이어베이스는 이 검사와 무관하다
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("table.tbl tbody tr", { timeout: 20000 });
  await page.waitForTimeout(200);
  const got = await page.evaluate(READ);
  await page.close();
  return got;
}

for (const [tk, what] of TICKERS) {
  const E = PY.screen[tk];
  for (const [site, url] of SITES) {
    const S = await view(url(tk));
    /* 돈 칸만 본다 — 연간: 매출·영업이익·순이익, 분기: 매출·영업이익(비율 칸의 빼기표 글리프는 따로 정할 일이다) */
    const diff = [];
    const cmp = (kind, got, want, cols) => {
      const gk = Object.keys(got).sort().join(","), wk = Object.keys(want).sort().join(",");
      if (!Object.keys(want).length) diff.push(`${kind} 자료가 비었다`);
      if (gk !== wk) diff.push(`${kind} 줄: 화면 ${gk || "없음"} · 자료 ${wk}`);
      for (const k of Object.keys(want)) for (const c of cols)
        if (got[k]?.[c] !== want[k][c]) diff.push(`${kind} ${k} ${c + 1}칸: 화면 ${got[k]?.[c]} · 파이썬 ${want[k][c]}`);
    };
    cmp("연간", S.annual, E.annual, [0, 1, 2]);
    cmp("분기", S.quarterly, E.quarterly, [0, 1]);
    ok(!diff.length, `${site} ${tk} ${what} — 실적 표의 돈 칸이 파이썬과 같다 (연간 ${Object.keys(S.annual).length} · 분기 ${Object.keys(S.quarterly).length}줄)`, diff.slice(0, 4).join(" | "));

    const la = [...S.labels].sort().join(" "), lb = [...E.labels].sort().join(" ");
    ok(S.labels.length > 0 && la === lb, `${site} ${tk} ${what} — 차트 값 라벨 ${S.labels.length}개가 파이썬과 같다`, `화면 ${la} | 파이썬 ${lb}`);

    const sd = STAT_KEYS.map((k, i) => [k, S.stats[k], E.stats[i]]).filter(([, a, b]) => a !== b).map(([k, a, b]) => `${k} 화면 ${a} · 파이썬 ${b}`);
    ok(!sd.length, `${site} ${tk} ${what} — 지표 넷이 파이썬과 같다 (${STAT_KEYS.map((k) => S.stats[k]).join(" · ")})`, sd.join(" | "));

    const cells = [...Object.values(S.annual).flatMap((c) => c.slice(0, 3)), ...Object.values(S.quarterly).flatMap((c) => c.slice(0, 2)), ...S.labels];
    const zero = cells.filter((s) => /^-?0\.0$/.test(s));
    ok(cells.length > 0 && !zero.length, `${site} ${tk} ${what} — 표·차트에 0.0 이 없다`, zero.join(" ") || "칸이 없다");
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
