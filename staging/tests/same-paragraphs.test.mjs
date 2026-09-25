/* ============================================================
   리포트 본문을 문단으로 자르는 규칙이 실사이트와 스테이징에서 같은가

   왜 있는가. 예전에는 세 문장마다 잘랐다. 문장 길이가 제각각이라 한 문단이
   휴대폰에서 10~14줄이 되고, 사장이 "글이 너무 빽빽해서 읽기 힘들다" 고 했다.
   그래서 실사이트를 '글자 수(한글 170자) 예산' 방식으로 바꿨는데, 스테이징은
   옛 방식 그대로 남았다. 두 갈래가 갈라진 채 오래 갔고, 그걸 아무도 못 봤다.
   CLAUDE.md 에 "올리기 전에 꼭 맞춰라" 고 손으로 적어 둔 것이 유일한 방어였다.

   사람의 기억 말고 여기서 막는다. 진짜 리포트 본문을 양쪽 규칙에 똑같이
   넣어 보고, 나온 문단이 글자 하나까지 같은지 본다. 다르면 실패한다.

   보는 것
     1. splitSentences · chunkPara · ps 의 코드가 양쪽에서 같다
     2. 진짜 리포트로 돌려도 나온 문단이 같다 (prose·bull·bear·risk·verdict)
     3. 실사이트가 '글자 수' 방식이다 (세 문장 방식으로 되돌아가지 않았나)

   실행
     node staging/tests/same-paragraphs.test.mjs
   ============================================================ */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");

let pass = 0, fail = 0;
const ok = (cond, name, extra) => {
  if (cond) { pass++; return true; }
  fail++; console.error(`  FAIL ${name}${extra ? "\n        " + extra : ""}`);
  return false;
};

/* 페이지에서 함수 한 덩어리를 이름으로 떼어 온다. 여는 중괄호부터 짝이 맞는
   닫는 중괄호까지 센다 — 줄 수나 들여쓰기에 기대지 않는다. */
function grab(src, head) {
  const i = src.indexOf(head);
  if (i < 0) return null;
  let j = src.indexOf("{", i), depth = 0;
  for (let k = j; k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}" && --depth === 0) return src.slice(i, k + 1);
  }
  return null;
}

const live = readFileSync(join(ROOT, "stock.html"), "utf8");
const stg  = readFileSync(join(STAGING, "stock.html"), "utf8");

/* ── 1. 코드가 같은가 ───────────────────────────────────────── */
const HEADS = ["function splitSentences(", "function chunkPara(", "function ps("];
for (const h of HEADS) {
  const a = grab(live, h), b = grab(stg, h);
  if (!ok(a, `실사이트에 ${h} 가 있다`)) continue;
  if (!ok(b, `스테이징에 ${h} 가 있다`,
          "스테이징이 옛 방식(세 문장)으로 되돌아갔을 수 있다")) continue;
  ok(a === b, `${h} 코드가 양쪽에서 같다`,
     "scripts 로 옮기지 말고 stock.html 의 것을 그대로 맞춰라");
}

/* 예산 값도 같아야 한다 */
const budget = s => (s.match(/var PARA_KO=(\d+),\s*PARA_EN=(\d+)/) || []).slice(1).join("/");
ok(budget(live) !== "", "실사이트에 PARA_KO·PARA_EN 이 있다",
   "세 문장 방식으로 되돌아갔는지 확인하라");
ok(budget(live) === budget(stg), "문단 예산(PARA_KO·PARA_EN)이 양쪽에서 같다",
   `실사이트 ${budget(live) || "(없음)"} · 스테이징 ${budget(stg) || "(없음)"}`);

/* 본문을 쓰는 자리도 같은 함수를 거쳐야 한다. 규칙만 같고 bull·bear·risk·
   종합 의견이 통째로 한 문단이면 읽는 사람에게는 안 고친 것과 같다. */
const uses = [
  [/function factors\([^\n]*ps\(pk\(f\.body\)\)/, "bull·bear 본문이 ps() 를 거친다"],
  [/function risksH\([^\n]*ps\(pk\(r\.body\)\)/, "risk 본문이 ps() 를 거친다"],
  [/wrapup[^"]*">'\+ps\(REP\.verdict/,        "종합 의견이 ps() 를 거친다"],
  [/chunkPara\(p\.trim\(\)\)/,                    "prose() 가 글자 수 방식으로 자른다"],
];
for (const [re, name] of uses) {
  ok(re.test(live), `실사이트 — ${name}`);
  ok(re.test(stg),  `스테이징 — ${name}`);
}

/* ── 2. 진짜 리포트로 돌려도 결과가 같은가 ──────────────────── */
function build(src) {
  const parts = HEADS.map(h => grab(src, h)).filter(Boolean);
  const bud = src.match(/var PARA_KO=\d+,\s*PARA_EN=\d+;/);
  const esc = "function esc(s){return String(s);}";
  return new Function(`${esc}\n${bud ? bud[0] : ""}\n${parts.join("\n")}
    return {chunkPara:chunkPara, ps:ps};`)();
}
const A = build(live), B = build(stg);

const DIR = join(ROOT, "data", "reports_v2");
let files = [];
try {
  files = readdirSync(DIR).filter(f => f.endsWith(".json")).sort().slice(0, 120);
} catch (e) { /* 리포트가 없는 환경이면 코드 비교만으로 끝낸다 */ }

const ko = o => (o && typeof o === "object") ? (o.ko || o.KO || "") : (o || "");
let bodies = 0, diffs = 0, firstDiff = "";
for (const f of files) {
  let d;
  try { d = JSON.parse(readFileSync(join(DIR, f), "utf8")); } catch (e) { continue; }
  const texts = [];
  for (const k of ["earnings", "industry", "outlook", "valuation_comment", "business", "recent"]) {
    const t = ko(d[k]); if (t) texts.push(t);
  }
  for (const k of ["bull", "bear", "risks"])
    for (const it of (d[k] || [])) { const t = ko(it.body); if (t) texts.push(t); }
  if (d.verdict) { const t = ko(d.verdict.body); if (t) texts.push(t); }

  for (const t of texts) {
    bodies++;
    const a = A.ps(t), b = B.ps(t);
    if (a !== b && diffs++ === 0)
      firstDiff = `${f}\n        실: ${a.slice(0, 90)}\n        스: ${b.slice(0, 90)}`;
  }
}
if (bodies)
  ok(diffs === 0, `진짜 리포트 ${bodies}덩어리를 돌려도 문단이 같다`,
     diffs ? `${diffs}덩어리가 다르다. 첫 번째: ${firstDiff}` : "");

/* ── 3. 실사이트가 '세 문장' 으로 되돌아가지 않았나 ─────────── */
ok(!/chunkPara\([^)]*,\s*\d+\s*\)/.test(live), "실사이트가 세 문장 방식이 아니다");
ok(!/chunkPara\([^)]*,\s*\d+\s*\)/.test(stg),  "스테이징이 세 문장 방식이 아니다",
   "chunkPara(p,3) 이 남아 있다 — 옛 방식이다");

console.log(`통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
