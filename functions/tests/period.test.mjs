/* ============================================================
   새 구독의 이용 기간 — 겹치는 시간을 어디에 두는가

   왜 있는가. 환불한 날 다시 결제하면 이전 구독이 자정까지 살아 있을 수 있어서,
   오늘 하루 요금을 두 번 내는 모양이 된다. 그 시간을 앞에서 뺄지(새 구독을 내일
   시작) 뒤에 붙일지(기간을 늘림) 사이를 오갔고, 한 번은 화면에는 '내일부터' 라고
   적어 놓고 실제로는 오늘 열리는 판을 낸 적이 있다.

   지금 규칙은 뒤에 붙이는 쪽이다.

     start  지금
     end    addMonth(max(지금, 이전 구독이 끝나는 시점))

   2026-11-24 환불 규칙을 바꾼 뒤로 이전 구독이 언제 끝나는지는 환불의 종류가
   정한다 — 청약철회(7일 이내 · 열람 없음 · 전액)는 그 자리에서, 이용일수를 뺀 환불
   (7일 이내 열람 · 7일 경과)은 오늘 자정(한국 시간)에 끝난다. 하루 열람 기록으로
   '오늘 열었는가' 를 따지던 옛 규칙은 없어졌다.

   ①~⑥ 은 confirmBilling 의 기간 계산을 달력으로 본다(addMonth 는 함수 파일의 것과
   본문이 같은지 ⑦ 이 견준다). ⑧ 은 진짜 함수(confirmBilling · requestRefund ·
   getReport · refundPreview)를 결제 스위치를 켜고 가짜 파이어스토어 · 가짜 토스로
   돌려, 환불 뒤 같은 날 다시 결제한 사람의 기간과 다음 환불을 본다(lib/paid-harness.mjs).

   실행
     node functions/tests/period.test.mjs
   ============================================================ */
import {
  clock, call, reset, sub, charges, cancels, seedReports, S, SRC,
  ok, eq, section, done, DAY, HOUR, MIN, UID, kstMidnightAfter,
} from "./lib/paid-harness.mjs";

/* functions/index.js 의 addMonth 와 같아야 한다(⑦ 이 견준다). 2026-11-25 — 한국 날짜로 세고, 기간은 결제일 오전 9시에 끝난다. */
const KST_OFFSET = 9 * 3600 * 1000;
const PERIOD_END_HOUR = 9;
function addMonth(from, day = 0) {
  const k = new Date(new Date(from).getTime() + KST_OFFSET);          // 한국 시간의 벽시계를 UTC 칸에 담아 센다
  const y = k.getUTCFullYear(), m = k.getUTCMonth() + 1;              // 다음 달(12월의 다음은 Date.UTC 가 이듬해 1월로 넘긴다)
  const last = new Date(Date.UTC(y, m + 1, 0)).getUTCDate();          // 다음 달의 마지막 날
  return new Date(Date.UTC(y, m, Math.min(day || k.getUTCDate(), last), PERIOD_END_HOUR) - KST_OFFSET);
}

/* confirmBilling 의 새 구독 기간 계산. */
function period(nowMs, prevEndMs) {
  const start = new Date(nowMs);
  const end = addMonth(new Date(Math.max(nowMs, prevEndMs || 0)));
  return { start, end };
}

const iso = (d) => new Date(d).toISOString();

section("① 처음 가입 (겹치는 것이 없다)");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  const { start, end } = period(now, 0);
  ok("이용은 지금부터", start.getTime() === now, iso(start));
  ok("기간은 그냥 한 달", end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

section("② 청약철회(전액 환불) 뒤 재결제 — 이전 구독이 그 자리에서 닫혔다");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  // 청약철회는 이용을 지금 끝내므로 이전 구독의 끝은 '지금' 이다
  const { start, end } = period(now, now);
  ok("이용은 지금부터", start.getTime() === now);
  ok("겹치는 시간이 없으니 기간도 안 늘어난다",
     end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

section("③ 이용일수를 뺀 환불 뒤 재결제 — 자정까지 겹친다");
{
  const now = Date.parse("2026-09-01T05:00:00Z");     // KST 9/1 14:00
  const prevEnd = kstMidnightAfter(now);               // KST 9/2 00:00
  const { start, end } = period(now, prevEnd);
  ok("이용은 그래도 지금부터 — 오늘 바로 열린다", start.getTime() === now, iso(start));
  ok("기간 끝은 자정 기준으로 한 달", end.getTime() === addMonth(new Date(prevEnd)).getTime(), iso(end));
  ok("겹친 만큼 보통 한 달보다 길다",
     end.getTime() > addMonth(new Date(now)).getTime(), iso(end));
  const extra = (end.getTime() - addMonth(new Date(now)).getTime()) / 3600000;
  ok("늘어나는 건 하루 이내다 (여기서는 10시간)", extra > 0 && extra <= 24, extra + "시간");
}

section("④ 자정 언저리 (한국 0~9시는 UTC 로 전날이다)");
{
  // KST 9/1 01:00 = UTC 8/31 16:00. UTC 로 끊으면 하루가 어긋난다.
  const now = Date.parse("2026-08-31T16:00:00Z");
  const prevEnd = kstMidnightAfter(now);
  ok("이전 구독의 끝은 KST 9월 2일 0시",
     new Date(prevEnd).toISOString() === "2026-09-01T15:00:00.000Z", iso(prevEnd));
  const { end } = period(now, prevEnd);
  ok("기간 끝도 그 기준으로 밀린다",
     end.getTime() === addMonth(new Date(prevEnd)).getTime(), iso(end));
}

section("⑤ 달 길이가 다를 때");
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

section("⑥ 지난 구독이 오래전에 끝났을 때");
{
  const now = Date.parse("2026-09-01T05:00:00Z");
  const prevEnd = Date.parse("2026-06-01T00:00:00Z");   // 석 달 전
  const { start, end } = period(now, prevEnd);
  ok("옛 날짜를 끌어오지 않는다", start.getTime() === now);
  ok("그냥 오늘부터 한 달", end.getTime() === addMonth(new Date(now)).getTime(), iso(end));
}

section("⑦ 옮겨 적은 것이 원본과 같은가");
{
  const body = (text, name) => {
    const i = text.indexOf(`function ${name}(`);
    if (i < 0) return null;
    let d = 0;
    const j = text.indexOf("{", i);
    for (let k = j; k < text.length; k++) {
      if (text[k] === "{") d++;
      else if (text[k] === "}" && --d === 0) return text.slice(j, k + 1).replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|\s+/g, "");
    }
    return null;
  };
  const mine = body(addMonth.toString(), "addMonth");
  const real = body(SRC, "addMonth");
  ok("addMonth 가 functions/index.js 와 같다", real !== null && mine === real,
     real === null ? "index.js 에서 못 찾음" : "본문이 다르다");
  ok("confirmBilling 이 max(지금, 이전 구독의 끝) 으로 기간을 잡는다",
     /addMonth\(new Date\(Math\.max\(now\.getTime\(\), prevEnd\)\)\)/.test(SRC));
}

/* ── 진짜 함수로 — 환불한 날 다시 결제한다 ─────────────────── */
const T = Date.parse("2026-11-02T05:00:00Z");         // 한국 시간 11월 2일 14시
const pay = () => call("confirmBilling", { authKey: "auth", customerKey: UID });
async function refundNow() {
  const q = (await call("refundPreview")).data || {};
  const r = await call("requestRefund", { expectAmount: q.amount });
  return { q, r };
}
function begin(at = T) { reset(); clock.set(at); S.users.add(UID); seedReports(["005930", "000660"]); }

section("⑧-1 청약철회 뒤 같은 날 다시 결제 — 겹치는 시간이 없다");
{
  begin();
  await pay();
  clock.set(T + HOUR);
  const { q, r } = await refundNow();
  eq("결제 한 시간 뒤 · 열람 없음 → 전액 · 지금 끝난다",
     [q.why, r.data && r.data.amount, sub()?.currentPeriodEnd?.toMillis()], ["withdraw", 14900, T + HOUR]);
  clock.set(T + 2 * HOUR);
  const again = await pay();
  const s = sub() || {};
  ok("다시 결제할 수 있다", !!again.data, JSON.stringify(again.error));
  ok("새 기간은 지금부터 그냥 한 달", s.currentPeriodStart?.toMillis() === T + 2 * HOUR &&
     s.currentPeriodEnd?.toMillis() === addMonth(new Date(T + 2 * HOUR)).getTime());
  eq("결제 두 번 · 취소 한 번", [charges(), cancels().map((c) => c.amount)], [[14900, 14900], [14900]]);
  ok("지난 구독의 '환불 완료' 와 취소 기록을 지운다", !("refundedAt" in s) && !("refundDone" in s));
  eq("이번 기간의 결제 건은 새 결제 하나", (s.periodPayments || []).length, 1);
}

section("⑧-2 이용일수를 뺀 환불 뒤 같은 날 다시 결제 — 자정까지 겹친 시간을 뒤에 붙인다");
{
  begin();
  await pay();
  clock.set(T + 10 * MIN);
  await call("getReport", { ticker: "005930" });
  clock.set(T + 30 * MIN);
  const { q, r } = await refundNow();
  const midnight = kstMidnightAfter(T);
  eq("열람한 뒤 환불 → 이용일수 차감 · 오늘 자정까지",
     [q.why, r.data && r.data.amount, sub()?.currentPeriodEnd?.toMillis()], ["early", 14900 - Math.floor(14900 / 30), midnight]);
  clock.set(T + HOUR);
  const again = await pay();
  const s = sub() || {};
  ok("다시 결제할 수 있다(환불이 끝난 구독은 '이용 중' 으로 막지 않는다)", !!again.data, JSON.stringify(again.error));
  eq("새 기간 — 지금부터 · 끝은 자정 기준으로 한 달",
     [s.currentPeriodStart?.toMillis(), s.currentPeriodEnd?.toMillis()], [T + HOUR, addMonth(new Date(midnight)).getTime()]);
  ok("  보통 한 달보다 길다(겹친 시간만큼)", s.currentPeriodEnd?.toMillis() > addMonth(new Date(T + HOUR)).getTime());
  ok("바로 리포트를 연다", !!(await call("getReport", { ticker: "000660" })).data);

  /* 새 기간의 환불 — 결제 전(같은 날 앞선 구독)에 연 것은 세지 않는다 */
  begin();
  await pay();
  clock.set(T + 10 * MIN);
  await call("getReport", { ticker: "005930" });
  clock.set(T + 30 * MIN);
  await refundNow();
  clock.set(T + HOUR);
  await pay();
  clock.set(T + 2 * HOUR);
  const n1 = (await call("refundPreview")).data || {};
  eq("새 기간에는 아직 안 열었다 → 전액 · 기간 일수는 겹친 하루를 넣어 31일", [n1.why, n1.amount, n1.totalDays],
     ["withdraw", 14900, 31]);
  await call("getReport", { ticker: "005930" });       // 아침에 본 종목을 다시 연다
  const n2 = (await call("refundPreview")).data || {};
  eq("  아침에 본 종목을 새 기간에 다시 열면 연 것이다 → 이용일수 차감", n2.why, "early");
}
{
  /* 겹친 시간을 붙인 기간이 달 끝에 걸린다 — 기준(3월 31일 0시)의 한 달 뒤는 4월 말일이다(31일 → 짧은 달 말일).
     2026-11-25 전에는 한 달 더하기를 세계 표준시로 세어 3월 31일 0시(UTC 로는 30일)가 5월 1일이 되고 32일 기간이었다. */
  const T3 = Date.parse("2027-03-30T05:00:00Z");      // 한국 시간 3월 30일 14시
  begin(T3);
  await pay();
  clock.set(T3 + 10 * MIN);
  await call("getReport", { ticker: "005930" });
  clock.set(T3 + 30 * MIN);
  await refundNow();
  clock.set(T3 + HOUR);
  await pay();
  clock.set(T3 + 2 * DAY);
  const q = (await call("refundPreview")).data || {};
  eq("3월 30일 환불 뒤 재결제 → 결제일 4월 30일 9시까지 · 31일 기간", [q.totalDays, q.usedDays], [31, 3]);
  eq("  결제일은 31일로 남는다 — 4월 30일 다음 결제일은 5월 31일", sub()?.billingDay, 31);
}

done();
