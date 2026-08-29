/* ============================================================
   환불 — 날짜 계산 회귀 테스트
   ------------------------------------------------------------
   실행:  node functions/tests/refund-days.test.mjs

   왜 있는가. 이건 돈이 오가는 계산인데 브라우저도 서버도 없는 데서 고친다.
   틀리면 회원 카드에 잘못된 금액이 꽂히고, 되돌리려면 사람이 붙어야 한다.

   무엇을 지키는가. functions/index.js 의 refundQuote 가 쓰는 규칙 그대로다.

     오늘 리포트 0건    오늘은 차감하지 않는다 → 이용은 지금 끝난다
     오늘 리포트 1건+   오늘을 차감한다        → 이용은 오늘 자정(KST)까지

   여태 경과 시간을 초 단위로 나눠 썼다(9.375일). 우리가 파는 단위는 하루인데
   (하루 5건, 한국 시간 자정 리셋) 쪼갤 수 없는 것을 소수로 차감하니 오전에
   한 건도 안 보고 환불하면 오늘 값을 내고 5건은 못 봤다.

   ⚠️ 아래 식은 functions/index.js 와 staging/demo-backend.js 에 같은 모양으로
      들어 있다. 셋 중 하나만 고치면 화면·미리보기·실제 청구가 갈라진다.
   ============================================================ */

/* functions/index.js 의 kstDayNo · kstEndOfToday 와 같은 식 */
const KST_OFFSET = 9 * 3600 * 1000;
const kstDayNo = (ms) => Math.floor((ms + KST_OFFSET) / 86400000);
const kstEndOfToday = (ms = Date.now()) =>
  new Date((kstDayNo(ms) + 1) * 86400000 - KST_OFFSET);

/* refundQuote 의 금액 부분 */
const REFUND_FEE_RATE = 0.10;
const FREE_WITHDRAW_DAYS = 7;
function quote({ elapsed, openedToday, openedThisPeriod, total = 30, price = 9900 }) {
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));
  if (!openedThisPeriod && used <= FREE_WITHDRAW_DAYS) return price;
  return Math.floor(price * Math.max(0, (total - used) / total) * (1 - REFUND_FEE_RATE));
}

let pass = 0, fail = 0;
const eq = (name, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log(`FAIL  ${name} → ${g}  (기대 ${w})`); }
};
const at = (s) => Date.parse(s);                 // KST 표기로 준다
const kst = (d) => new Date(d).toLocaleString("sv-SE", { timeZone: "Asia/Seoul" });
const gap = (a, b) => kstDayNo(at(b)) - kstDayNo(at(a));

console.log("── 오늘이 끝나는 순간 ──");
eq("09:00 → 다음 자정", kst(kstEndOfToday(at("2026-08-29T09:00:00+09:00"))), "2026-08-30 00:00:00");
eq("00:00 → 그날 자정", kst(kstEndOfToday(at("2026-08-29T00:00:00+09:00"))), "2026-08-30 00:00:00");
eq("23:59 → 1분 뒤",    kst(kstEndOfToday(at("2026-08-29T23:59:00+09:00"))), "2026-08-30 00:00:00");
/* KST 오전 0~9시는 UTC 로 전날이다. UTC 로 끊으면 여기서 하루가 밀린다. */
eq("08:00(UTC 로는 전날 23시)", kst(kstEndOfToday(at("2026-08-29T08:00:00+09:00"))), "2026-08-30 00:00:00");
eq("월 경계 8/31 → 9/1",  kst(kstEndOfToday(at("2026-08-31T20:00:00+09:00"))), "2026-09-01 00:00:00");
eq("연 경계 12/31 → 1/1", kst(kstEndOfToday(at("2026-12-31T20:00:00+09:00"))), "2027-01-01 00:00:00");
eq("윤년 2/28 → 2/29",    kst(kstEndOfToday(at("2028-02-28T20:00:00+09:00"))), "2028-02-29 00:00:00");

console.log("\n── 며칠이 지났는가(달력으로) ──");
eq("8/1 → 8/10 = 9일", gap("2026-08-01T09:00:00+09:00", "2026-08-10T09:00:00+09:00"), 9);
eq("결제 당일은 0일",   gap("2026-08-01T09:00:00+09:00", "2026-08-01T23:00:00+09:00"), 0);
/* 두 시간밖에 안 지났지만 날짜는 하루 넘었다. 시간이 아니라 날짜를 센다. */
eq("23시 결제 → 다음 날 01시는 1일", gap("2026-08-01T23:00:00+09:00", "2026-08-02T01:00:00+09:00"), 1);
/* 반대로 스물세 시간이 지나도 같은 날이면 0일이다. */
eq("00:30 결제 → 같은 날 23:30 은 0일", gap("2026-08-01T00:30:00+09:00", "2026-08-01T23:30:00+09:00"), 0);

console.log("\n── 환불 금액 (BASIC 9,900원 · 30일) ──");
const opened = { openedThisPeriod: true };
eq("9일 경과 · 오늘 0건 → 6,237원", quote({ elapsed: 9, openedToday: false, ...opened }), 6237);
eq("9일 경과 · 오늘 1건 → 5,940원", quote({ elapsed: 9, openedToday: true, ...opened }), 5940);
/* 오늘 안 본 사람이 본 사람보다 하루치만큼 더 받는다. 뒤집히면 안 된다. */
eq("오늘 0건이 항상 더 받는다",
   [0, 1, 5, 15, 29].every((d) =>
     quote({ elapsed: d, openedToday: false, ...opened }) >=
     quote({ elapsed: d, openedToday: true, ...opened })), true);

console.log("\n── 경계 ──");
/* 가입하자마자 5건 보고 환불 — 하루가 반드시 차감되므로 공짜가 되지 않는다.
   초 단위로 세던 때는 996원이었다. 새 규칙이 오히려 조금 더 받는다. */
eq("가입 당일 · 5건 열람 → 8,613원 (부담 1,287원)",
   quote({ elapsed: 0, openedToday: true, ...opened }), 8613);
eq("마지막 날 · 오늘 1건 → 0원", quote({ elapsed: 29, openedToday: true, ...opened }), 0);
eq("기간을 넘겨도 음수가 되지 않는다", quote({ elapsed: 40, openedToday: true, ...opened }), 0);

console.log("\n── 청약철회(7일 이내 · 미열람)는 전액 ──");
/* 한 건도 안 열었으면 오늘도 당연히 0건이라 오늘은 차감되지 않는다.
   그래서 예외를 따로 두지 않아도 같은 규칙에 그대로 들어맞는다. */
eq("가입 당일 · 미열람 → 전액",
   quote({ elapsed: 0, openedToday: false, openedThisPeriod: false }), 9900);
eq("7일째 · 미열람 → 전액",
   quote({ elapsed: 7, openedToday: false, openedThisPeriod: false }), 9900);
/* 6,534 가 아니라 6,533 이다. 9900 × (22/30) × 0.9 를 소수로 계산하면
   6533.999999999999 가 나오고 Math.floor 가 1원을 깎는다. 곱하는 순서를 바꾸면
   딱 떨어지지만 그 식이 functions·demo-backend 두 곳에 같은 모양으로 들어 있어
   한 곳만 고치면 화면과 실제 청구가 갈라진다. 1원이고, 고지한 문구도
   '수수료를 제외한 금액' 이라 그대로 둔다 — 다음 사람이 버그로 보고 고치지
   않도록 여기 적어 둔다. */
eq("8일째 · 미열람 → 전액 아님(잔여분 − 10%)",
   quote({ elapsed: 8, openedToday: false, openedThisPeriod: false }), 6533);

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
