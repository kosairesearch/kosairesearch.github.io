/* ============================================================
   환불 — 날짜를 세는 법 (한국 시간 날짜 · 이용일수 · 기간 일수 · 7일 경계 · 자정)
   ------------------------------------------------------------
   실행:  node functions/tests/refund-days.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/refund-days.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가. 이건 돈이 오가는 계산인데 브라우저도 서버도 없는 데서 고친다.
   틀리면 회원 카드에 잘못된 금액이 꽂히고, 되돌리려면 사람이 붙어야 한다.

   날짜는 한국 시간으로 센다(kstDayNo). 한국 시간 오전 0~9시는 UTC 로 전날이라,
   UTC 로 끊으면 그 아홉 시간 동안 하루가 어긋난다.

     기간 일수 total   = 끝나는 날 − 시작한 날 (28~31일 · 결제 화면에 적은 '해당 이용 기간의 일수')
     이용일수 usedDays = 시작한 날부터 신청한 날까지(둘 다 넣는다) — 시각이 아니라 날짜로
     7일 이내          = 신청한 날 − 시작한 날 ≤ 7 (결제한 날은 세지 않는다)
     이용 종료         = 청약철회는 지금 · 그 밖은 오늘 자정(한국 시간)

   진짜 refundPreview 가 돌려주는 usedDays · totalDays · endsAt 을 본다
   (lib/paid-harness.mjs). 기간은 진짜 confirmBilling 이 잡은 것을 쓴다(③).
   금액 규칙은 refund-rule.test 가 본다.
   ============================================================ */
import {
  clock, call, reset, seedSub, seedReads, sub, S, ok, eq, section, done, DAY, MIN, UID,
} from "./lib/paid-harness.mjs";

const at = (s) => Date.parse(s);                       // '+09:00' 을 붙여 한국 시간으로 준다
const kst = (ms) => new Date(ms).toLocaleString("sv-SE", { timeZone: "Asia/Seoul" });

/* startMs 에 결제한 구독으로 nowMs 에 환불 견적을 낸다. viewed 면 결제 1분 뒤 연 기록을 둔다. */
async function quoteAt(startMs, nowMs, { viewed = true, endMs } = {}) {
  reset();
  clock.set(startMs);
  seedSub({ startMs, endMs });
  if (viewed) seedReads(startMs + MIN, ["005930"]);
  clock.set(nowMs);
  return (await call("refundPreview")).data || {};
}

section("① 오늘이 끝나는 순간 — 이용일수를 뺀 환불은 오늘 자정(한국 시간)까지");
for (const [now, want] of [
  ["2026-08-29T09:00:00+09:00", "2026-08-30 00:00:00"],
  ["2026-08-29T00:00:00+09:00", "2026-08-30 00:00:00"],
  ["2026-08-29T23:59:00+09:00", "2026-08-30 00:00:00"],
  ["2026-08-29T08:00:00+09:00", "2026-08-30 00:00:00"],   // UTC 로는 전날 23시
  ["2026-08-31T20:00:00+09:00", "2026-09-01 00:00:00"],   // 달 경계
  ["2026-12-31T20:00:00+09:00", "2027-01-01 00:00:00"],   // 해 경계
  ["2028-02-28T20:00:00+09:00", "2028-02-29 00:00:00"],   // 윤년
]) {
  const q = await quoteAt(at(now) - 2 * DAY, at(now));
  eq(`${now.slice(0, 16).replace("T", " ")} → ${want}`, [q.why, q.endsAt && kst(Date.parse(q.endsAt))], ["early", want]);
}
{
  const now = at("2026-08-29T15:00:00+09:00");
  const q = await quoteAt(now - 2 * DAY, now, { viewed: false });
  eq("청약철회(열람 없음)는 지금 끝난다", [q.why, q.chargedToday, Date.parse(q.endsAt)], ["withdraw", false, now]);
}

section("② 이용일수는 시각이 아니라 날짜로 센다");
for (const [start, now, want, why] of [
  ["2026-08-01T09:00:00+09:00", "2026-08-10T09:00:00+09:00", 10, "8/1 → 8/10 = 10일째"],
  ["2026-08-01T09:00:00+09:00", "2026-08-01T23:00:00+09:00", 1, "결제한 날은 1일째"],
  /* 두 시간밖에 안 지났지만 날짜는 하루 넘었다 */
  ["2026-08-01T23:00:00+09:00", "2026-08-02T01:00:00+09:00", 2, "23시 결제 → 다음 날 01시는 2일째"],
  /* 반대로 스물세 시간이 지나도 같은 날이면 1일째다 */
  ["2026-08-01T00:30:00+09:00", "2026-08-01T23:30:00+09:00", 1, "00:30 결제 → 같은 날 23:30 은 1일째"],
  /* 한국 시간 08시 결제(UTC 로는 전날) → 다음 날 08시 30분 */
  ["2026-08-01T08:00:00+09:00", "2026-08-02T08:30:00+09:00", 2, "08시 결제(UTC 로는 전날) → 다음 날 = 2일째"],
]) {
  eq(why, (await quoteAt(at(start), at(now))).usedDays, want);
}
{
  /* 기간 마지막 날(끝나는 시각 전) — 이용일수가 기간 일수를 넘지 않는다 */
  const start = at("2026-11-02T14:00:00+09:00");
  const q = await quoteAt(start, at("2026-12-02T10:00:00+09:00"));
  eq("기간 마지막 날 — 이용일수는 기간 일수(30)에서 멈춘다", [q.usedDays, q.totalDays, q.amount], [30, 30, 0]);
}

section("③ 기간 일수 — confirmBilling 이 실제로 잡은 기간으로");
for (const [start, want, why] of [
  ["2026-11-02T14:00:00+09:00", 30, "11월 2일 → 12월 2일 = 30일"],
  ["2026-12-02T14:00:00+09:00", 31, "12월 2일 → 1월 2일 = 31일"],
  ["2027-02-02T14:00:00+09:00", 28, "2027년 2월 2일 → 3월 2일 = 28일"],
  ["2028-02-02T14:00:00+09:00", 29, "2028년(윤년) 2월 2일 → 3월 2일 = 29일"],
  ["2027-01-31T14:00:00+09:00", 28, "1월 31일 → 2월 28일(다음 달에 31일이 없다) = 28일"],
  ["2027-01-30T14:00:00+09:00", 29, "1월 30일 → 2월 28일 = 29일"],
  ["2027-03-31T14:00:00+09:00", 30, "3월 31일 → 4월 30일 = 30일"],
]) {
  reset();
  clock.set(at(start));
  S.users.add(UID);
  const r = await call("confirmBilling", { authKey: "auth", customerKey: UID });
  clock.set(at(start) + DAY);
  const q = (await call("refundPreview")).data || {};
  eq(why, [!!r.data, q.totalDays], [true, want]);
}
{
  /* 한국 시간 08시에 결제하면 UTC 로는 전날이다. 한국 날짜로 세야 30일이다. */
  const start = at("2026-11-02T08:00:00+09:00");
  reset();
  clock.set(start);
  S.users.add(UID);
  await call("confirmBilling", { authKey: "auth", customerKey: UID });
  const s0 = sub();
  const endKst = s0 && s0.currentPeriodEnd ? kst(s0.currentPeriodEnd.toMillis()) : null;
  clock.set(start + DAY);
  eq("한국 시간 08시 결제 — 기간은 한국 날짜로 30일(12월 2일 08시까지)",
     [((await call("refundPreview")).data || {}).totalDays, endKst], [30, "2026-12-02 08:00:00"]);
}

section("④ 7일 경계 — 신청한 날 − 결제한 날 ≤ 7 (한국 시간 날짜)");
{
  const start = at("2026-11-02T23:50:00+09:00");
  const a = await quoteAt(start, at("2026-11-09T23:59:00+09:00"), { viewed: false });
  eq("23시 50분 결제 → 7일 뒤 23시 59분은 아직 7일 이내(전액)", [a.usedDays, a.why], [8, "withdraw"]);
  const b = await quoteAt(start, at("2026-11-10T00:00:00+09:00"), { viewed: false });
  eq("  그다음 자정이 되면 7일이 지났다(위약금)", [b.usedDays, b.why], [9, "late"]);
}
{
  /* UTC 로 세면 하루 일찍 7일이 지난 것으로 본다 */
  const q = await quoteAt(at("2026-11-02T08:00:00+09:00"), at("2026-11-09T10:00:00+09:00"), { viewed: false });
  eq("한국 시간 08시 결제(UTC 로는 전날) → 7일 뒤 10시는 7일 이내", q.why, "withdraw");
}

done();
