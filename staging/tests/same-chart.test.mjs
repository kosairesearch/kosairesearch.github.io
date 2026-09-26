/* ============================================================
   리포트 실적 차트 — 스테이징(JS)과 정적 종목 페이지(파이썬)가 같은 그림을 그리는가

   왜 있는가. 같은 막대그래프를 두 곳이 따로 그린다. 스테이징 stock.html 은 JS
   (scripts/build_stock_staging.py 의 barChart), 미리 만드는 종목 페이지는 파이썬
   (scripts/stock_page.py 의 bar_chart). 2026-09-26 에 두 곳 모두에서 같은 버그 둘을
   고쳤다 — 적자가 0선 위 2px 막대로 그려지던 것, 라벨이 SVG 안에 있어 휴대폰에서
   13px 이 8.8px 로 줄던 것. 한쪽만 고치면 되살아나므로 여기서 막는다.

   보는 것
     1. 같은 숫자를 넣으면 두 쪽이 글자 하나까지 같은 마크업을 낸다(만든 예 + 진짜 리포트)
     2. 음수 막대는 0선 아래에 있다
     3. 값·연도 라벨은 SVG 밖 HTML 이다(<text> 가 없다)

   실행
     node staging/tests/same-chart.test.mjs
   ============================================================ */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { spawnSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
let pass = 0, fail = 0;
const ok = (cond, name, extra) => { cond ? pass++ : fail++; console.log(`${cond ? "PASS" : "FAIL"}  ${name}${cond || !extra ? "" : "  ← " + extra}`); };

/* 스테이징 페이지에서 함수 넷을 떼어 온다 */
const html = readFileSync(join(ROOT, "staging/stock.html"), "utf8");
function grab(name) {
  const i = html.indexOf("function " + name + "(");
  if (i < 0) throw new Error("staging/stock.html 에 " + name + " 이 없다");
  let depth = 0;
  for (let k = html.indexOf("{", i); k < html.length; k++) {
    if (html[k] === "{") depth++;
    else if (html[k] === "}" && --depth === 0) return html.slice(i, k + 1);
  }
}
const barChart = new Function(["esc", "pyf", "fjo", "barChart"].map(grab).join("\n") + "\nreturn barChart;")();

/* 만든 예 — 적자만 · 흑자만 · 섞임 · 0 · 비어 있음 · 두 막대 높이가 비슷함 */
const cases = [
  [["22", 1.0e12, -0.2e12], ["23", 1.2e12, 0.1e12], ["24", 0.9e12, null]],
  [["21Q1", 3.1e10, -4.2e10], ["21Q2", 2.0e10, -5.5e10], ["21Q3", 0, -6e10], ["21Q4", 1.5e10, -1e9], ["22Q1", 2.2e10, 2.1e10]],
  [["2021", 279.6e12, 51.6e12], ["2022", 302.2e12, 43.4e12], ["2023", 258.9e12, 6.6e12], ["2024", 300.9e12, 32.7e12]],
  [["a", 0, 0], ["b", null, null]],
  [["x", 5e11, 4.9e11], ["y", -1e11, -1.05e11]],
];
/* 진짜 리포트 — 적자가 있는 종목 몇과 흑자 종목 몇 */
const dir = join(ROOT, "data/reports_v2");
const real = [];
for (const tk of ["028300", "085660", "011810", "005930", "000660"]) {
  const f = join(dir, tk + ".json");
  if (!existsSync(f)) continue;
  const q = (JSON.parse(readFileSync(f, "utf8")).quant) || {};
  const annual = (q.annual || []).slice().sort((a, b) => a.year - b.year);
  real.push(annual.map((a) => [String(a.year), a.rev ?? null, a.op ?? null]));
  real.push((q.quarterly || []).map((x) => [String(x.q).slice(2, 4) + "Q" + String(x.q).slice(-1), x.rev ?? null, x.op ?? null]));
}
const all = cases.concat(real.filter((g) => g.length));

const py = spawnSync("python3", ["-c",
  "import json,sys; sys.path.insert(0,'scripts'); import stock_page as S; " +
  "C=json.load(sys.stdin); print(json.dumps([S.bar_chart([tuple(g) for g in c]) for c in C]))"],
  { cwd: ROOT, input: JSON.stringify(all), encoding: "utf8" });
if (py.status !== 0) { console.error(py.stderr); process.exit(2); }
const pyOut = JSON.parse(py.stdout);

all.forEach((g, i) => {
  const js = barChart(g), p = pyOut[i];
  const label = i < cases.length ? `만든 예 ${i + 1}` : `진짜 리포트 ${i - cases.length + 1}`;
  let at = -1; if (js !== p) { for (let k = 0; k < Math.max(js.length, p.length); k++) if (js[k] !== p[k]) { at = k; break; } }
  ok(js === p, `${label} — 파이썬과 JS 가 같다`, at >= 0 ? `JS ${js.slice(at - 40, at + 40)} | PY ${p.slice(at - 40, at + 40)}` : "");

  if (!js) return;
  ok(!/<text\b/.test(js), `${label} — 라벨이 SVG 밖 HTML 이다`);
  const y0 = +(/class="ch-base"/.test(js) && js.match(/<line[^>]*y1="([\d.]+)"/)[1]);
  const rects = [...js.matchAll(/<rect class="(ch-rev|ch-op)" x="[\d.]+" y="([\d.]+)" width="[\d.]+" height="([\d.]+)"\/>/g)];
  const vals = g.flatMap((r) => [r[1], r[2]]).filter((v) => v != null && v !== 0);
  let wrong = 0;
  rects.forEach((m, k) => { const v = vals[k], y = +m[2]; if (v < 0 && y + 0.05 < y0) wrong++; if (v > 0 && y > y0 + 0.05) wrong++; });
  ok(rects.length === vals.length && wrong === 0, `${label} — 흑자는 0선 위, 적자는 0선 아래`, `막대 ${rects.length}/${vals.length} · 잘못 ${wrong}`);
});

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
