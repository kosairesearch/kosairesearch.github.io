/* ============================================================
   약관·개인정보처리방침이 정해진 원문 그대로인가 — 실사이트 · 스테이징

   왜 있는가. 6월에 갈라졌다. 스테이징에 유료화 조항을 미리 써 넣었고,
   그 뒤 9월에 실사이트만 개정했다. 스테이징은 6월 판 그대로 남았다.
   그래서 스테이징에는 이런 것들이 통째로 빠져 있었다.

     고의·중대한 과실 단서(책임 제한) · 유사투자자문업 신고 의무
     데이터 출처별 지식재산권 · 청약철회 제한 요건 · 가분적 콘텐츠 환불
     부칙(시행일·경과조치·개정 이력)

   석 달 동안 아무도 몰랐다 — 법률 문서라서 아무도 안 열어 봤기 때문이다.

   2026-11-25 사장이 유료화 날짜를 2027년 1월 1일로 정하고 스테이징 약관을
   유료판으로 바꾸라고 했다. 그래서 약관 · 방침은 이제 두 판이다.

     현행판  scripts/content/terms.src.html · privacy.src.html
             실사이트 Terms.html · Privacy.html (시행일 전까지)
     유료판  scripts/content/terms.paid.src.html · privacy.paid.src.html
             스테이징 Terms.html · Privacy.html (늘)
             실사이트 Terms-2027.html · Privacy-2027.html (공지 기간 — comp_common.NOTICE_LIVE)
             실사이트 Terms.html · Privacy.html (시행일부터 — comp_common.PAID_LIVE)

   6월의 일이 다시 나지 않게 여기서 막는다.

   ① 화면에 걸린 글 = 정해진 원문. 페이지마다 어느 원문을 써야 하는지 위
      표대로 정해 두고, 본문이 그 원문과 글자 하나까지 같은지 본다.
   ② 유료판은 현행판의 어느 판을 바탕으로 했는지 적어 둔다(머리 주석의
      'sha256 앞 16자리'). 현행판을 고치면 그 값이 어긋나 여기서 걸린다 —
      유료판에도 같은 개정을 넣었는지 보고, 넣었으면 그 값을 새로 적어라.
      그래야 시행일에 유료판으로 바꿀 때 그 사이의 개정이 조용히 지워지지 않는다.

   실행
     node staging/tests/same-legal.test.mjs
   ============================================================ */
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const CONTENT = join(ROOT, "scripts/content");

let pass = 0, fail = 0;
const ok = (cond, name, extra) => {
  if (cond) { pass++; return true; }
  fail++; console.error(`  FAIL ${name}${extra ? "\n        " + extra : ""}`);
  return false;
};

/* 스위치 — comp_common.py 의 NOTICE_LIVE · PAID_LIVE 를 그대로 읽는다. */
const CC = readFileSync(join(ROOT, "scripts/comp_common.py"), "utf8");
const flag = (n) => new RegExp(`^${n} = True`, "m").test(CC);
const NOTICE_LIVE = flag("NOTICE_LIVE"), PAID_LIVE = flag("PAID_LIVE");

const norm = (t) => t.replace(/\s+/g, " ").trim();

/* 원문의 본문 글 — .legal 상자(공고일 줄 · 머리말 · 조문) 그대로. 생성기(build_legal_comp.py)가 이 글을
   제목 아래 .meta(공고일) · .intro(머리말) · section.sec(조문)으로 펼친다. */
function srcBody(file) {
  const doc = new JSDOM(readFileSync(file, "utf8").replace(/<br\s*\/?>/gi, " ")).window.document;
  const legal = doc.querySelector(".legal");
  return legal ? norm(legal.textContent) : null;
}

/* 만들어진 페이지의 본문 글. 껍데기(띠 · 메뉴 · 목차 · 개정 안내 상자)는 보지 않는다. */
function pageBody(file) {
  const doc = new JSDOM(readFileSync(file, "utf8").replace(/<br\s*\/?>/gi, " ")).window.document;
  const legal = doc.querySelector(".legal");
  if (legal) return norm(legal.textContent);
  const parts = [doc.querySelector(".page-hero .meta"), doc.querySelector(".page-hero .intro"),
                 ...[...doc.querySelectorAll("section.sec")].flatMap((s) => [s.querySelector("h2"), s.querySelector(".prose")])];
  if (parts.some((x) => !x) || parts.length < 4) return null;
  return norm(parts.map((x) => x.textContent).join(" "));
}

/* 어디서부터 달라지는지 한 줄로 짚어 준다. 5천 자를 통째로 찍으면
   무엇이 다른지 사람이 못 찾는다. */
function firstDiff(want, got) {
  let i = 0;
  while (i < want.length && i < got.length && want[i] === got[i]) i++;
  const at = Math.max(0, i - 40);
  return `${i}번째 글자부터 다르다\n        원문   …${want.slice(at, i + 60)}\n        화면   …${got.slice(at, i + 60)}`;
}
const when = (t) => (t.match(/(공고일|시행일)[^·]*(·[^·]*시행일[^·]*)?/) || [""])[0].trim();

const DOCS = [
  { name: "이용약관", page: "Terms.html", next: "Terms-2027.html", cur: "terms.src.html", paid: "terms.paid.src.html" },
  { name: "개인정보 처리방침", page: "Privacy.html", next: "Privacy-2027.html", cur: "privacy.src.html", paid: "privacy.paid.src.html" },
];

for (const d of DOCS) {
  const cur = srcBody(join(CONTENT, d.cur));
  const paid = srcBody(join(CONTENT, d.paid));
  if (!ok(cur && paid, `${d.name} 원문 두 판(${d.cur} · ${d.paid})에 본문(.legal)이 있다`)) continue;

  /* ① 화면 = 정해진 원문 */
  const want = [
    [join(ROOT, d.page), PAID_LIVE ? paid : cur, `실사이트 ${d.page}`, PAID_LIVE ? d.paid : d.cur],
    [join(STAGING, d.page), paid, `스테이징 ${d.page}`, d.paid],
  ];
  if (NOTICE_LIVE && !PAID_LIVE) want.push([join(ROOT, d.next), paid, `실사이트 ${d.next}(개정 전문)`, d.paid]);
  for (const [file, src, label, srcName] of want) {
    if (!ok(existsSync(file), `${label} 이 있다`)) continue;
    const got = pageBody(file);
    if (!ok(got, `${label} 에 법률 본문(.meta · .intro · section.sec)이 있다`)) continue;
    ok(got === src, `${label} 본문이 원문(${srcName})과 같다`, got === src ? "" : firstDiff(src, got));
    /* 시행일 줄은 따로 한 번 더 — 어긋나면 '언제부터 효력이 있는 약관인가' 가 갈리므로 이름을 붙여 따로 실패시킨다. */
    ok(when(got) === when(src), `${label} 공고일 · 시행일 줄이 원문과 같다`, `원문 "${when(src)}" · 화면 "${when(got)}"`);
  }
  if (!NOTICE_LIVE) ok(!existsSync(join(ROOT, d.next)), `공지 전에는 실사이트에 ${d.next} 가 없다`,
                       "comp_common.NOTICE_LIVE 가 꺼져 있다 — 사장 승인 전에 개정 전문을 싣지 않는다");

  /* ② 유료판이 현행판의 지금 판을 바탕으로 했는가 */
  const paidRaw = readFileSync(join(CONTENT, d.paid), "utf8");
  const base = (paidRaw.match(/sha256 앞 16자리 ([0-9a-f]{16})/) || [])[1];
  const now = createHash("sha256").update(readFileSync(join(CONTENT, d.cur))).digest("hex").slice(0, 16);
  ok(base === now, `${d.paid} 가 현행판(${d.cur})의 지금 판을 바탕으로 한다`,
     `현행판이 바뀌었다(적어 둔 값 ${base} · 지금 ${now}). 그 개정을 유료판에도 넣었는지 확인하고, 넣었으면 유료판 머리 주석의 값을 ${now} 로 고쳐라.`);
}

/* 공지 — 실사이트에 실으면 스테이징과 본문이 같아야 한다(링크만 다르다 — 스테이징은 Terms.html, 실사이트는 Terms-2027.html). */
const noticeSrc = srcBody(join(CONTENT, "notice.src.html"));
const stgNotice = existsSync(join(STAGING, "Notice.html")) ? pageBody(join(STAGING, "Notice.html")) : null;
ok(stgNotice && stgNotice === noticeSrc, "스테이징 Notice.html 본문이 원문(notice.src.html)과 같다",
   stgNotice ? firstDiff(noticeSrc, stgNotice) : "스테이징 Notice.html 이 없다");
if (NOTICE_LIVE) {
  const liveNotice = existsSync(join(ROOT, "Notice.html")) ? pageBody(join(ROOT, "Notice.html")) : null;
  ok(liveNotice && liveNotice === noticeSrc, "실사이트 Notice.html 본문이 원문과 같다",
     liveNotice ? firstDiff(noticeSrc, liveNotice) : "실사이트 Notice.html 이 없다");
} else {
  ok(!existsSync(join(ROOT, "Notice.html")), "공지 전에는 실사이트에 Notice.html 이 없다");
}

/* 9월 개정에서 들어온 것들. 본문 비교로 이미 걸리지만, 이 이름들이 로그에
   찍혀야 무엇을 잃을 뻔했는지 다음 사람이 안다. 유료판은 같은 뜻을 더 구체적인 말로
   담았다(청약철회 제한 요건 → 전자상거래법 제17조제2항제5호 · 가분적 콘텐츠 → 이용 기간에 따라 나눌 수 있는 디지털콘텐츠). */
const NINE = ["고의 또는 중대한 과실", "경과조치", "유사투자자문업", "데이터 출처", "시험 사용 상품", "가분적 콘텐츠"];
const NINE_PAID = ["고의 또는 중대한 과실", "경과조치", "유사투자자문업", "데이터 출처", "제17조제2항제5호", "나눌 수 있는 디지털콘텐츠"];
const liveTerms = readFileSync(join(ROOT, "Terms.html"), "utf8");
const stgTerms = readFileSync(join(STAGING, "Terms.html"), "utf8");
for (const k of PAID_LIVE ? NINE_PAID : NINE)
  ok(liveTerms.includes(k), `실사이트 약관에 "${k}" 가 남아 있다`, "9월 개정 내용이다. 옛 판으로 되돌아갔는지 확인하라");
for (const k of NINE_PAID)
  ok(stgTerms.includes(k), `스테이징 약관에 "${k}" 가 남아 있다`, "9월 개정 내용이다. 유료판에서 빠졌는지 확인하라");

console.log(`통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
