/* ============================================================
   약관·개인정보처리방침이 실사이트와 스테이징에서 같은가

   왜 있는가. 6월에 갈라졌다. 스테이징에 유료화 조항을 미리 써 넣었고,
   그 뒤 9월에 실사이트만 개정했다. 스테이징은 6월 판 그대로 남았다.
   그래서 스테이징에는 이런 것들이 통째로 빠져 있었다.

     고의·중대한 과실 단서(책임 제한) · 유사투자자문업 신고 의무
     데이터 출처별 지식재산권 · 청약철회 제한 요건 · 가분적 콘텐츠 환불
     부칙(시행일·경과조치·개정 이력)

   스테이징 갈래에는 유료화 작업이 들어 있어서 언젠가 실사이트로 올라간다.
   그때 그대로 올렸으면 9월 개정이 조용히 지워졌을 것이다. 석 달 동안
   아무도 몰랐다 — 법률 문서라서 아무도 안 열어 봤기 때문이다.

   그래서 여기서 막는다. 두 쪽 본문이 글자 하나까지 같아야 한다.

   이 검사가 실패한다면
     한쪽만 고쳤다는 뜻이다. 양쪽을 같이 고쳐라.

     유료화 개정안을 스테이징에서만 미리 굴리지 마라. 갈라진 채 잊힌다.
     초안은 따로 갈래(branch)에 두고, 정한 시행일에 양쪽을 같이 바꿔라.
     그래야 화면에 걸린 약관과 실제로 효력 있는 약관이 늘 같다.

   실행
     node staging/tests/same-legal.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
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

/* 법률 본문만 떼어 글자만 남긴다. 껍데기(스테이징 띠·메뉴·글꼴 경로·목차)는 두 쪽이 달라야 정상이므로 비교 대상이 아니다.
   실사이트(옛 디자인)는 .legal 상자 하나에 공고일 줄·머리말·조문이 다 들어 있다. 스테이징(새 디자인, 2026-09-26)은
   같은 글을 제목 아래 .meta(공고일) · .intro(머리말) · section.sec(조문)으로 펼쳐 놓았다 — build_legal_comp.py 가
   만들 때 실사이트 .legal 과 글자가 같은지 스스로 확인하고, 여기서는 만들어진 파일끼리 다시 본다. */
import { JSDOM } from "jsdom";
const norm = (t) => t.replace(/\s+/g, " ").trim();
function body(file) {
  const doc = new JSDOM(readFileSync(file, "utf8").replace(/<br\s*\/?>/gi, " ")).window.document;   // 줄바꿈 태그는 띄어쓰기로 — 글자 비교라서
  const legal = doc.querySelector(".legal");
  if (legal) return norm(legal.textContent);
  const parts = [doc.querySelector(".page-hero .meta"), doc.querySelector(".page-hero .intro"),
                 ...[...doc.querySelectorAll("section.sec")].flatMap((s) => [s.querySelector("h2"), s.querySelector(".prose")])];
  if (parts.some((x) => !x) || parts.length < 4) return null;
  return norm(parts.map((x) => x.textContent).join(" "));
}

/* 어디서부터 달라지는지 한 줄로 짚어 준다. 5천 자를 통째로 찍으면
   무엇이 다른지 사람이 못 찾는다. */
function firstDiff(a, b) {
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  const at = Math.max(0, i - 40);
  return `${i}번째 글자부터 다르다\n        실사이트 …${a.slice(at, i + 60)}\n        스테이징 …${b.slice(at, i + 60)}`;
}

for (const name of ["Terms.html", "Privacy.html"]) {
  const live = body(join(ROOT, name));
  const stg = body(join(STAGING, name));
  if (!ok(live, `실사이트 ${name} 에 법률 본문(.legal)이 있다`)) continue;
  if (!ok(stg, `스테이징 ${name} 에 법률 본문(.legal 또는 .meta·.intro·section.sec)이 있다`)) continue;
  ok(live === stg, `${name} 본문이 양쪽에서 같다`,
     live === stg ? "" : firstDiff(live, stg));

  /* 시행일 줄은 따로 한 번 더 본다. 본문이 같으면 당연히 같지만, 여기가
     어긋나면 '언제부터 효력이 있는 약관인가' 가 갈리므로 이름을 붙여
     따로 실패시킨다 — 로그만 보고도 무슨 일인지 알 수 있게. */
  const when = t => (t.match(/(공고일|시행일)[^·]*(·[^·]*시행일[^·]*)?/) || [""])[0].trim();
  ok(when(live) === when(stg), `${name} 시행일 표기가 같다`,
     `실사이트 "${when(live)}" · 스테이징 "${when(stg)}"`);
}

/* 9월 개정에서 들어온 것들. 본문 비교로 이미 걸리지만, 이 이름들이 로그에
   찍혀야 무엇을 잃을 뻔했는지 다음 사람이 안다. */
const NINE = ["고의 또는 중대한 과실", "경과조치", "유사투자자문업",
              "데이터 출처", "시험 사용 상품", "가분적 콘텐츠"];
const stgTerms = readFileSync(join(STAGING, "Terms.html"), "utf8");
for (const k of NINE)
  ok(stgTerms.includes(k), `스테이징 약관에 "${k}" 가 남아 있다`,
     "9월 개정 내용이다. 6월 판으로 되돌아갔는지 확인하라");

console.log(`통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
