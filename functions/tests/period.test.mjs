/* ============================================================
   새 구독의 이용 기간 — 겹치는 하루를 어디에 두는가

   왜 있는가. 환불한 날 다시 결제하면 이전 구독이 자정까지 살아 있어서, 오늘
   하루 요금을 두 번 내는 모양이 된다. 그 하루를 앞에서 뺄지(새 구독을 내일
   시작) 뒤에 붙일지(기간을 하루 늘림) 사이를 오갔고, 한 번은 화면에는 '내일
   부터' 라고 적어 놓고 실제로는 오늘 열리는 판을 낸 적이 있다.

   지금 규칙은 뒤에 붙이는 쪽이다.

     start  지금
     end    addMonth(max(지금, 이전 구독이 끝나는 시점))

   서버는 여기서 돌릴 수 없다(파이어베이스가 필요하다). 그래서 confirmBilling
   이 쓰는 계산만 그대로 옮겨 놓고 본다 — 옮겨 적은 것이 원본과 어긋나면
   그게 바로 화면과 실제가 갈라지는 자리다.

   실행
     node functions/tests/period.test.mjs
   ============================================================ */

const DAY = 86400000;

/* functions/index.js 의 addMonth 와 같아야 한다. */
function addMonth(from) {
  const d = new Date(from);
  const day = d.getDate();
  d.setMonth(d.getMonth() + 1);
  if (d.getDate() !== day) d.setDate(0);   // 31일 → 다음 달 말일
  return d;
}

/* confirmBilling 의 새 구독 기간 계산. */
function period(nowMs, prevEndMs) {
  const start = new Date(nowMs);
  const end = addMonth(new Date(Math.max(nowMs, prevEndMs || 0)));
  return { start, end };
}

/* 한국 시간 자정 — 오늘 리포트를 본 뒤 환불하면 이전 구독이 여기까지 산다. */
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600000) / DAY);
const kstEndOfToday = (ms) => (kstDayNo(ms) + 1) * DAY - 9 * 3600000;

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};
const iso = (d) => new Date(d).toISOString();

console.log("── 처음 가입 (겹치는 것이 없다) ──");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  const { start, end } = period(now, 0);
  ok("이용은 지금부터", start.getTime() === now, iso(start));
  ok("기간은 그냥 한 달", end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

console.log("\n── 오늘 0건으로 환불하고 재결제 (이전 구독이 그 자리에서 닫혔다) ──");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  // 환불이 즉시 종료시키므로 이전 구독의 끝은 '지금' 이다
  const { start, end } = period(now, now);
  ok("이용은 지금부터", start.getTime() === now);
  ok("겹치는 하루가 없으니 기간도 안 늘어난다",
     end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

console.log("\n── 오늘 리포트를 보고 환불하고 재결제 (자정까지 겹친다) ──");
{
  const now = Date.parse("2026-09-01T05:00:00Z");     // KST 9/1 14:00
  const prevEnd = kstEndOfToday(now);                  // KST 9/2 00:00
  const { start, end } = period(now, prevEnd);
  ok("이용은 그래도 지금부터 — 오늘 바로 열린다", start.getTime() === now, iso(start));
  ok("기간 끝은 자정 기준으로 한 달", end.getTime() === addMonth(new Date(prevEnd)).getTime(), iso(end));
  ok("겹친 만큼 보통 한 달보다 길다",
     end.getTime() > addMonth(new Date(now)).getTime(), iso(end));
  const extra = (end.getTime() - addMonth(new Date(now)).getTime()) / 3600000;
  ok("늘어나는 건 하루 이내다 (여기서는 10시간)", extra > 0 && extra <= 24, extra + "시간");
}

console.log("\n── 자정 언저리 (한국 0~9시는 UTC 로 전날이다) ──");
{
  // KST 9/1 01:00 = UTC 8/31 16:00. UTC 로 끊으면 하루가 어긋난다.
  const now = Date.parse("2026-08-31T16:00:00Z");
  const prevEnd = kstEndOfToday(now);
  ok("이전 구독의 끝은 KST 9월 2일 0시",
     new Date(prevEnd).toISOString() === "2026-09-01T15:00:00.000Z", iso(prevEnd));
  const { end } = period(now, prevEnd);
  ok("기간 끝도 그 기준으로 밀린다",
     end.getTime() === addMonth(new Date(prevEnd)).getTime(), iso(end));
}

console.log("\n── 달 길이가 다를 때 ──");
{
  // KST 1/31. 다음 달에 31일이 없다 — 말일로 당겨야 한다.
  const now = Date.parse("2026-01-31T05:00:00Z");
  const { end } = period(now, 0);
  ok("1월 31일 → 2월 28일 (3월 3일로 넘어가지 않는다)",
     end.getMonth() === 1 && end.getDate() === 28, iso(end));
}
{
  // 윤년 2월 29일
  const now = Date.parse("2028-01-31T05:00:00Z");
  const { end } = period(now, 0);
  ok("윤년이면 1월 31일 → 2월 29일",
     end.getMonth() === 1 && end.getDate() === 29, iso(end));
}

console.log("\n── 지난 구독이 오래전에 끝났을 때 ──");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  const prevEnd = Date.parse("2026-06-01T00:00:00Z");   // 석 달 전
  const { start, end } = period(now, prevEnd);
  ok("옛 날짜를 끌어오지 않는다", start.getTime() === now);
  ok("그냥 오늘부터 한 달", end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
