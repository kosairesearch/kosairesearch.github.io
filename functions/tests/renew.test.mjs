/* ============================================================
   자동 갱신 — 매일 한 번 도는 배치(renewSubscriptions)

   왜 따로 있는가. 표의 열 하나(자동 갱신)만 미리보기에서 눌러 볼 수 없다.
   브라우저에는 크론이 없어서다. 여기서 그 자리를 메운다.

   무엇을 보는가
     · 요금제는 하나다 — 구독 문서에 옛 요금제 값(basic · pro)이나 다운그레이드
       예약(pendingPlan)이 남아 있어도 member 14,900원을 받는다(2026-11-24)
     · 모르는 요금제 값이면 카드사를 부르지 않는다 — 금액이 비어 NaN 이 나가지 않는다
     · 해지 예약이면 긁지 않고 닫는다
     · 새 주기라 지난 주기의 결제 기록 · 환불 기록을 끊는다
     · 카드가 거절되면 끊지 않고 '결제 실패' 로 두고 정해진 날에 다시 시도한다
     · 계정이 사라진 문서는 긁지 않는다
     · 사용자가 같은 순간에 결제하면 두 번 청구되지 않는다  ← 제일 중요하다
     · 목록을 만든 뒤 상태가 바뀌었으면 다시 긁지 않는다

   전에는 배치가 한 건을 처리하는 판단을 이 파일에 옮겨 적어 시험했다. 이제 진짜
   함수를 결제 스위치를 켜고 가짜 파이어스토어 · 가짜 토스로 돌린다
   (lib/paid-harness.mjs). 옮겨 적은 사본은 원본이 바뀌어도 통과한다.

   실행
     node functions/tests/renew.test.mjs
     FN_INDEX=<고치기 전 functions/index.js> node functions/tests/renew.test.mjs   # 고치기 전이면 걸리는지
   ============================================================ */
import {
  clock, runJob, reset, seedSub, sub, store, hooks, S, charges, chargeTries, payments, failToss,
  indexNeeds, SRC, ok, eq, section, done, DAY, HOUR, UID, ts, kstDayNo, kstDay, addMonthMs,
} from "./lib/paid-harness.mjs";

/* 배치가 도는 시각 — 02:00 UTC(한국 시간 11시) */
const NOW = Date.parse("2026-11-10T02:00:00Z");
const tries = [];
function fresh() { tries.push(...chargeTries()); reset(); clock.set(NOW); }
/* 기간이 막 끝난 이용 중 구독 */
function due(over = {}, uid = UID) {
  return seedSub({
    uid, startMs: NOW - 30 * DAY, endMs: NOW - 1000, payKey: "old",
    refundDone: [{ key: "old", amount: 100 }], ...over,
  });
}
/* 카드가 거절돼 재시도를 기다리는 구독 */
function stuck(over = {}, uid = UID) {
  return seedSub({
    uid, startMs: NOW - 60 * DAY, endMs: NOW - 30 * DAY, payKey: "old", status: "past_due",
    refundDone: [{ key: "old", amount: 100 }], failedAt: ts(NOW - 30 * DAY), ...over,
  });
}
const renew = () => runJob("renewSubscriptions");
const failRows = (uid = UID) => payments(uid).filter((p) => p.kind === "failed");
const alerts = () => S.mails.filter((m) => /정기결제/.test(m.subject || ""));

section("보통 갱신");
{
  fresh();
  due();
  const endMs = sub().currentPeriodEnd.toMillis();
  const r = await renew();
  const s = sub();
  ok("배치가 오류 없이 끝난다", !r.error, JSON.stringify(r.error));
  eq("member 정가 14,900원을 받는다", charges(), [14900]);
  ok("새 기간이 지금부터 한 달", s.currentPeriodStart.toMillis() === NOW && s.currentPeriodEnd.toMillis() === addMonthMs(NOW));
  eq("지난 주기 결제 기록을 끊는다", s.periodPayments, [{ key: s.lastPaymentKey, amount: 14900, from: NOW }]);
  ok("지난 환불 기록(refundDone)을 지운다 — 남으면 다음 환불이 이미 취소한 줄 알고 건너뛴다", !("refundDone" in s));
  eq("멱등 이름은 그 주기로 고정된다", (S.toss.find((c) => /^\/billing\/bk/.test(c.path)) || {}).idem, `renew_${UID}_${kstDayNo(endMs)}`);
  const pay = payments()[0] || {};
  eq("결제 내역 — 14,900원 · member · '멤버십 월 구독'", [pay.amount, pay.plan, pay.description, pay.kind],
     [14900, "member", "멤버십 월 구독", "subscription"]);
  eq("거절이 없는 날은 운영 알림을 보내지 않는다", alerts().length, 0);
}

section("옛 요금제 값 · 다운그레이드 예약이 남은 구독 — 모두 14,900원");
{
  fresh();
  due({ plan: "basic" }, "a");
  due({ plan: "pro", pendingPlan: "basic" }, "b");
  due({ plan: "PRO" }, "c");
  due({ plan: "basic", pendingPlan: "pro" }, "d");
  due({}, "e");
  await renew();
  eq("다섯 구독 모두 14,900원(옛 9,900원 · 예약된 다운그레이드를 쓰지 않는다)", charges(), [14900, 14900, 14900, 14900, 14900]);
  ok("요금제는 모두 member 로 적힌다", ["a", "b", "c", "d", "e"].every((u) => sub(u).plan === "member"),
     ["a", "b", "c", "d", "e"].map((u) => sub(u).plan).join(","));
  ok("변경 예약 칸(pendingPlan)은 지운다", ["a", "b", "c", "d", "e"].every((u) => !("pendingPlan" in sub(u))));
  ok("결제 기록 금액도 14,900원", ["a", "b", "c", "d"].every((u) => sub(u).periodPayments[0].amount === 14900));
}

section("모르는 요금제 값 — 카드사를 부르지 않는다");
for (const plan of ["enterprise", null]) {
  fresh();
  due({ plan });
  await renew();
  eq(`요금제 ${JSON.stringify(plan)} → 결제 요청 0건`, chargeTries().length, 0);
  eq("  '결제 실패' 로 남는다(카드를 긁지 않았으니 이용도 열지 않는다)", sub().status, "past_due");
  eq("  실패 내역의 금액은 0원 — 실제와 다른 금액을 적지 않는다", failRows().map((p) => p.amount), [0]);
  ok("  운영 알림에 뜬다", alerts().length === 1);
}

section("해지 예약 · 환불이 끝난 구독");
{
  fresh();
  due({ cancelAtPeriodEnd: true });
  await renew();
  ok("해지 예약이면 긁지 않고 종료로 닫는다", sub().status === "expired" && chargeTries().length === 0);
}
{
  fresh();
  due({ cancelAtPeriodEnd: true, refundedAt: ts(NOW - 12 * HOUR) });
  await renew();
  ok("이용일수를 뺀 환불 뒤 자정이 지난 구독도 긁지 않고 닫는다", sub().status === "expired" && chargeTries().length === 0);
}

section("카드가 거절되면");
{
  fresh();
  due({ plan: "pro", pendingPlan: "basic" });
  failToss(/^\/billing\/bk/, { message: "한도 초과" });
  await renew();
  const s = sub();
  ok("끊지 않고 '결제 실패' 로 둔다", s.status === "past_due" && s.retryCount === 0 && s.failedAt.toMillis() === NOW,
     JSON.stringify([s.status, s.retryCount]));
  eq("실패 내역 — 청구하려던 14,900원 · member", failRows().map((p) => [p.amount, p.plan]), [[14900, "member"]]);
  eq("운영 알림 — 새로 거절 1건", alerts().map((m) => m.subject), ["[KOSAI] 정기결제 — 새로 거절 1건"]);
}

section("계정이 사라진 문서");
{
  fresh();
  due();
  S.users.delete(UID);
  await renew();
  ok("긁지 않고 닫는다 · 카드를 지운다", chargeTries().length === 0 && sub().status === "deleted" && !("billingKey" in sub()));
}

section("사용자가 같은 순간에 결제 · 환불하는 중이면");
{
  /* 갱신 대상은 기간이 끝난 문서라 subActive 가 false 다. 해지 · 환불은 저절로
     막히지만 '새 결제' 는 막히지 않는다. 배치가 자물쇠를 안 잡으면 두 번 청구된다. */
  fresh();
  due({ busy: { op: "billing", at: ts(NOW - 10 * 1000) } });
  await renew();
  ok("건너뛴다 — 두 번 청구하지 않는다", chargeTries().length === 0);
  ok("'결제 실패' 로 적지 않는다", sub().status === "active" && failRows().length === 0);
}

section("목록을 만든 뒤 상태가 바뀌었으면");
{
  fresh();
  due();
  hooks.beforeTx = () => { store.get(`subscriptions/${UID}`).currentPeriodEnd = ts(NOW + 30 * DAY); };
  await renew();
  ok("그 사이 새 기간이 시작됐으면 다시 긁지 않는다", chargeTries().length === 0);
}
{
  fresh();
  due();
  hooks.beforeTx = () => { store.get(`subscriptions/${UID}`).status = "deleted"; };
  await renew();
  ok("그 사이 active 가 아니게 됐으면 건드리지 않는다", chargeTries().length === 0 && sub().status === "deleted");
}

/* ── 카드가 거절된 뒤의 재시도 ─────────────────────────────
   한 번 거절됐다고 바로 끊지 않는다. 정해진 날(1 · 3 · 5 · 7일째)에 다시
   시도하고, 성공하면 그 순간부터 새 한 달이 시작된다. 네 번 다 실패하면 종료한다.
   ─────────────────────────────────────────────────────────── */
section("재시도: 정해진 날에만");
for (const [tried, dayN, want] of [
  [0, 0, "기다림"], [0, 1, "되살림"], [1, 2, "기다림"], [1, 3, "되살림"],
  [2, 4, "기다림"], [2, 5, "되살림"], [3, 6, "기다림"], [3, 7, "되살림"], [4, 30, "종료"],
]) {
  fresh();
  stuck({ retryCount: tried, failedAt: ts(NOW - dayN * DAY) });
  await renew();
  const got = sub().status === "active" ? "되살림" : sub().status === "expired" ? "종료" : "기다림";
  const paid = charges().length;
  ok(`${tried}번 시도함 · ${dayN}일째 → ${want}`, got === want && paid === (want === "되살림" ? 1 : 0), `${got} · 결제 ${paid}건`);
}

section("재시도 성공 — 그 순간부터 새 한 달 · 옛 요금제 값이어도 14,900원");
{
  fresh();
  stuck({ plan: "pro", pendingPlan: "basic" });
  await renew();
  const s = sub();
  eq("14,900원을 받는다", charges(), [14900]);
  ok("되살아나 지금부터 한 달", s.status === "active" && s.currentPeriodStart.toMillis() === NOW &&
     s.currentPeriodEnd.toMillis() === addMonthMs(NOW));
  ok("요금제 member · 변경 예약 칸 · 밀린 흔적 · 환불 기록을 지운다",
     s.plan === "member" && !("pendingPlan" in s) && !("failedAt" in s) && !("retryCount" in s) && !("refundDone" in s));
  eq("지난 주기 결제 기록을 끊는다", s.periodPayments, [{ key: s.lastPaymentKey, amount: 14900, from: NOW }]);
  eq("멱등 이름이 그날로 고정된다", (S.toss.find((c) => /^\/billing\/bk/.test(c.path)) || {}).idem, `dun_${UID}_${kstDay(NOW)}`);
  eq("운영 알림 — 재시도 성공 1건", alerts().map((m) => m.subject), ["[KOSAI] 정기결제 — 재시도 성공 1건"]);
}

section("재시도 실패 · 마지막 실패");
{
  fresh();
  stuck({ retryCount: 1, failedAt: ts(NOW - 3 * DAY) });
  failToss(/^\/billing\/bk/);
  await renew();
  ok("아직 끊지 않고 횟수만 올린다", sub().status === "past_due" && sub().retryCount === 2);
  eq("실패 내역 — '정기결제 재시도 실패(2회)' · 14,900원", failRows().map((p) => [p.description, p.amount]),
     [["정기결제 재시도 실패(2회)", 14900]]);
}
{
  fresh();
  stuck({ retryCount: 3, failedAt: ts(NOW - 7 * DAY) });
  failToss(/^\/billing\/bk/);
  await renew();
  ok("네 번째도 실패하면 이용을 종료한다", sub().status === "expired" && sub().retryCount === 4);
  eq("  최종 실패로 적는다", failRows().map((p) => p.description), ["정기결제 실패(최종)"]);
  eq("  운영 알림 — 최종 실패 1건", alerts().map((m) => m.subject), ["[KOSAI] 정기결제 — 최종 실패 1건"]);
}
{
  fresh();
  stuck({ plan: "enterprise", retryCount: 0, failedAt: ts(NOW - DAY) });
  await renew();
  ok("재시도도 모르는 요금제 값이면 카드사를 부르지 않는다", chargeTries().length === 0 && sub().retryCount === 1,
     JSON.stringify([chargeTries().length, sub().retryCount]));
}
{
  fresh();
  stuck({ failedAt: undefined });
  await renew();
  ok("언제 실패했는지 모르면 오늘을 기준일로 다시 잡는다(긁지 않는다)",
     sub().failedAt && sub().failedAt.toMillis() === NOW && sub().retryCount === 0 && chargeTries().length === 0);
}
{
  fresh();
  stuck({ retryCount: 0, failedAt: ts(NOW - DAY) });
  S.users.delete(UID);
  await renew();
  ok("재시도도 긁기 전에 계정을 확인한다", chargeTries().length === 0 && sub().status === "deleted");
}

section("재시도가 사용자 조작과 겹치면");
{
  fresh();
  stuck({ retryCount: 0, failedAt: ts(NOW - DAY) });
  hooks.beforeTx = () => { store.get(`subscriptions/${UID}`).status = "active"; };
  await renew();
  ok("그 사이 카드를 바꿔 되살아났으면 건드리지 않는다", chargeTries().length === 0);
}
{
  fresh();
  stuck({ retryCount: 0, failedAt: ts(NOW - DAY), busy: { op: "billing", at: ts(NOW - 5000) } });
  await renew();
  ok("처리 중이면 건너뛰고 상태를 바꾸지 않는다",
     chargeTries().length === 0 && sub().status === "past_due" && (sub().retryCount || 0) === 0);
}

section("결제일 — 매월 같은 날 · 끝나기 전에 결제한다(2026-11-25 · 약관 제9조②)");
{
  /* 배치는 한국 시간 8시 30분에 돈다. 기간은 결제일 9시에 끝난다(addMonth). 전에는 11시에 돌며 이미 끝난 기간만 결제해,
     오후에 끝나는 구독은 다음 날로 밀리고 그사이 잠겼다. */
  const B = Date.parse("2026-12-02T08:30:00+09:00");
  const later = Date.parse("2026-12-02T15:00:00+09:00");       // 오늘 오후에 끝나는 옛 기간(결제한 시각 그대로 끝나던 문서)
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2026-11-02T15:00:00+09:00"), endMs: later, payKey: "old" });
  await renew();
  const s = sub();
  eq("오늘 오후에 끝나는 기간도 오늘 아침에 결제한다", charges(), [14900]);
  eq("  다음 결제일은 다음 달 같은 날 9시(한국 시간)", new Date(s.currentPeriodEnd.toMillis()).toISOString(), "2027-01-02T00:00:00.000Z");
  eq("  결제일(billingDay)을 적는다", s.billingDay, 2);
  eq("  같은 날 두 번 돌아도 다시 결제하지 않는다", (await renew(), charges()), [14900]);
}
{
  const B = Date.parse("2026-12-02T08:30:00+09:00");
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2026-11-03T09:00:00+09:00"), endMs: Date.parse("2026-12-03T09:00:00+09:00"), payKey: "old" });
  await renew();
  eq("내일 끝나는 기간은 오늘 결제하지 않는다", chargeTries().length, 0);
}
{
  /* 다음 달 배치가 몇 초 일찍 돌아도 밀리지 않는다 — 끝나는 날이 오늘이면 결제한다 */
  const B = Date.parse("2027-01-02T08:29:58+09:00");
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2026-12-02T08:30:00+09:00"), endMs: Date.parse("2027-01-02T09:00:00+09:00"), payKey: "old", billingDay: 2 });
  await renew();
  eq("결제일 9시 전에 돌면 그날 결제한다", charges(), [14900]);
  eq("  다음 결제일 2월 2일 9시", new Date(sub().currentPeriodEnd.toMillis()).toISOString(), "2027-02-02T00:00:00.000Z");
}
{
  /* 31일 결제 — 짧은 달에는 말일, 그다음 달에는 다시 31일 */
  const B = Date.parse("2027-02-28T08:30:00+09:00");
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2027-01-31T14:00:00+09:00"), endMs: Date.parse("2027-02-28T09:00:00+09:00"), payKey: "old", billingDay: 31 });
  await renew();
  eq("2월 28일에 결제하고 다음 결제일은 3월 31일 9시", [charges(), new Date(sub().currentPeriodEnd.toMillis()).toISOString(), sub().billingDay],
     [[14900], "2027-03-31T00:00:00.000Z", 31]);
}
{
  /* 해지 예약 · 이용일수를 뺀 환불은 기간이 실제로 끝난 뒤에 닫는다 — 아침에 닫으면 남은 시간을 빼앗는다 */
  const B = Date.parse("2026-12-02T08:30:00+09:00");
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2026-11-02T15:00:00+09:00"), endMs: Date.parse("2026-12-02T15:00:00+09:00"), payKey: "old", cancelAtPeriodEnd: true });
  await renew();
  eq("오늘 오후에 끝나는 해지 예약은 아침에 닫지 않는다(결제도 없다)", [sub().status, chargeTries().length, !!sub().billingKey], ["active", 0, true]);
  clock.set(Date.parse("2026-12-03T08:30:00+09:00"));
  await renew();
  eq("  다음 날 배치가 닫고 결제 수단 정보를 지운다", [sub().status, chargeTries().length, "billingKey" in sub()], ["expired", 0, false]);
}
{
  /* 배치가 멈춰 결제일을 넘긴 경우(우리 쪽 사정) — 늦은 날부터 한 달을 준다. 결제일에 맞추면 짧은 기간에 한 달 값을 받는다 */
  const B = Date.parse("2026-12-05T08:30:00+09:00");
  reset(); clock.set(B);
  seedSub({ startMs: Date.parse("2026-11-02T09:00:00+09:00"), endMs: Date.parse("2026-12-02T09:00:00+09:00"), payKey: "old", billingDay: 2 });
  await renew();
  eq("결제일을 넘겨 결제하면 그날부터 한 달 · 결제일도 그날", [charges(), new Date(sub().currentPeriodEnd.toMillis()).toISOString(), sub().billingDay],
     [[14900], "2027-01-05T00:00:00.000Z", 5]);
}
{
  const i = SRC.indexOf("exports.renewSubscriptions");
  ok("배치는 한국 시간 8시 30분에 돈다", /schedule: "30 8 \* \* \*", timeZone: "Asia\/Seoul"/.test(SRC.slice(i, i + 400)));
}

section("카드사에 보낸 결제 금액");
tries.push(...chargeTries());
ok(`위의 결제 요청 ${tries.length}건의 금액이 모두 숫자였다(NaN · undefined 없음)`,
   tries.length > 0 && tries.every((c) => Number.isFinite(c.body.amount)));

section("원본에 남아 있어야 할 장치");
{
  const i = SRC.indexOf("exports.renewSubscriptions");
  const body = SRC.slice(i, SRC.indexOf("\n);\n", i));
  ok("상한(400)까지 찼으면 알린다(갱신 · 재시도 모두)",
     /대상이 상한\(400\)까지 찼다/.test(body) && /재시도 대상이 상한\(400\)까지 찼다/.test(body));
  ok("예약해 둔 변경(pendingPlan)으로 청구할 요금제를 고르지 않는다", !/pendingPlan \|\|/.test(body));
}
/* 갱신 대상을 고르는 질의(status 같다 + currentPeriodEnd 범위)는 파이어스토어 복합 색인이
   있어야 돈다. 저장소에는 색인 설정이 없다 — 결제를 켜기 전에 색인을 만들어야 한다. */
if (indexNeeds.length) console.log("\n참고  복합 색인이 필요한 질의: " + [...new Set(indexNeeds)].join(" / "));

done();
