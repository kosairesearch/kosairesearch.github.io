/* ============================================================
   요금제 하나 — member 월 14,900원 · 요금제 변경 없음 (2026-11-24)
   ------------------------------------------------------------
   실행:  node functions/tests/plan.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/plan.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가. 사장 "요금제는 1개 14900원." BASIC(9,900원) · PRO(14,900원)와 요금제
   변경(업그레이드 차액 결제 · 다운그레이드 예약 pendingPlan · changePlan)을 없앴다.

   돈이 새는 자리는 옛 값이다. 구독 문서나 옛 결제 화면에 basic · pro 가 남아 있을 때
   PRICE["basic"] 처럼 없는 칸을 읽으면 금액이 undefined 가 된다. 청구 쪽은 charge 의
   숫자 검사가 카드사 앞에서 막지만 결제가 통째로 실패하고, 환불 쪽은 받은 돈을 0원으로
   센다. 그래서 옛 id 는 member 로 읽고, 모르는 값은 돈을 움직이지 않는다.

   진짜 함수(confirmBilling · cancelSubscription · resumeSubscription · getUsage)를 결제
   스위치를 켜고 가짜 파이어스토어 · 가짜 토스로 돌린다(lib/paid-harness.mjs).
   갱신 · 재시도 배치의 옛 값은 renew.test 가 본다.
   ============================================================ */
import {
  clock, call, reset, seedSub, sub, charges, chargeTries, payments, fns, SRC, S,
  ok, eq, section, done, DAY, HOUR, UID, ts, addMonthMs,
} from "./lib/paid-harness.mjs";

const NOW0 = Date.parse("2026-11-10T03:00:00Z");     // 한국 시간 11월 10일 12시
/* 장면마다 새로 시작하되, 카드사에 보낸 결제 요청은 모아 둔다(⑥ 이 금액을 본다) */
const tries = [];
function fresh() { tries.push(...chargeTries()); reset(); clock.set(NOW0); }

/* ── ① 요금 표 ── */
section("① 요금 표");
{
  const line = (/^const PRICE = (\{[^}\n]*\});/m.exec(SRC) || [])[1] || "";
  eq("PRICE 는 한 줄 — { member: 14900 }", line, "{ member: 14900 }");
  ok("옛 요금제(basic · pro)의 가격이 표에 없다", !/\bbasic:\s*\d|\bpro:\s*\d/.test(SRC));
  ok("요금제 이름은 '멤버십'", /const PLAN_NAME = \{ member: "멤버십" \};/.test(SRC));
}

/* ── ② 요금제 변경이 없다 ── */
section("② 요금제 변경(changePlan)이 없다");
{
  ok("결제를 켠 함수 파일이 changePlan 을 내보내지 않는다", !("changePlan" in fns), Object.keys(fns).join(","));
  ok("함수 파일에 changePlan 내보내기가 없다", !/exports\.changePlan\b/.test(SRC));
  ok("업그레이드 차액 결제(멱등 이름 up_ · '업그레이드 차액')가 없다",
     !/`up_\$\{/.test(SRC) && !/업그레이드 차액`/.test(SRC));
  ok("결제 함수는 모두 그대로 있다",
     ["confirmBilling", "listPayments", "cancelSubscription", "resumeSubscription", "requestRefund",
      "refundPreview", "renewSubscriptions"].every((n) => typeof fns[n] === "function"));
}

/* ── ③ 새 결제 ── */
section("③ 새 결제 — 옛 결제 화면이 basic · pro 를 보내도 member 14,900원");
for (const [what, plan] of [["member", "member"], ["옛 id basic", "basic"], ["옛 id pro", "pro"],
                            ["요금제를 보내지 않음", undefined], ["대문자 MEMBER", "MEMBER"]]) {
  fresh();
  S.users.add(UID);
  const data = { authKey: "auth_1", customerKey: UID };
  if (plan !== undefined) data.plan = plan;
  const r = await call("confirmBilling", data);
  const s = sub() || {};
  eq(`${what} → 14,900원 한 번 결제 · 요금제 member`, [r.data && r.data.plan, charges(), s.plan], ["member", [14900], "member"]);
  if (plan === "basic") {
    const pay = payments()[0] || {};
    eq("  결제 내역 — 요금제 member · '멤버십 월 구독' · 종류 subscription",
       [pay.plan, pay.description, pay.kind, pay.amount], ["member", "멤버십 월 구독", "subscription", 14900]);
    eq("  이번 기간의 결제 건 · 기간(지금부터 한 달)",
       [s.periodPayments, s.currentPeriodStart.toMillis(), s.currentPeriodEnd.toMillis()],
       [[{ key: s.lastPaymentKey, amount: 14900, from: NOW0 }], NOW0, addMonthMs(NOW0)]);
    ok("  변경 예약 칸(pendingPlan)이 없다", !("pendingPlan" in s));
  }
}
{
  fresh();
  S.users.add(UID);
  const r = await call("confirmBilling", { plan: "enterprise", authKey: "auth_1", customerKey: UID });
  eq("모르는 요금제 값은 거절(invalid-argument)", r.error && r.error.code, "invalid-argument");
  eq("  카드 등록 · 결제 요청을 보내지 않는다", S.toss.length, 0);
}
{
  fresh();
  seedSub({ startMs: NOW0 - 3 * DAY });
  const r = await call("confirmBilling", { authKey: "auth_1", customerKey: UID });
  eq("이용 중인 구독 위에는 결제하지 않는다", [r.error && r.error.code, S.toss.length], ["already-exists", 0]);
}

/* ── ④ 해지 · 해지 취소 ── */
section("④ 해지 — 취소된 변경 예약(droppedPlan)을 더는 말하지 않는다");
{
  fresh();
  seedSub({ startMs: NOW0 - 3 * DAY, plan: "pro", pendingPlan: "basic" });
  const r = await call("cancelSubscription");
  eq("해지 예약 — 응답은 {ok:true}", r.data, { ok: true });
  ok("  해지 예약이 걸리고 옛 변경 예약 칸은 지워진다", sub().cancelAtPeriodEnd === true && !("pendingPlan" in sub()));
  const back = await call("resumeSubscription");
  ok("해지 취소", !!back.data && sub().cancelAtPeriodEnd === false, JSON.stringify(back));
}
{
  fresh();
  seedSub({ startMs: NOW0 - 40 * DAY, endMs: NOW0 - 10 * DAY, status: "past_due", pendingPlan: "basic",
            failedAt: ts(NOW0 - 10 * DAY), retryCount: 2 });
  const r = await call("cancelSubscription");
  eq("결제가 밀린 구독의 해지 — 즉시 종료 · {ok, stopped}", r.data, { ok: true, stopped: true });
  ok("  종료 · 재시도 일정과 변경 예약 칸을 지운다",
     sub().status === "expired" && !("failedAt" in sub()) && !("retryCount" in sub()) && !("pendingPlan" in sub()));
}

/* ── ⑤ 카드 재등록으로 되살리기 ── */
section("⑤ 결제가 밀린 구독을 카드 재등록으로 되살린다 — 옛 값이어도 14,900원");
for (const [what, over] of [
  ["옛 요금제 pro + 다운그레이드 예약 basic", { plan: "pro", pendingPlan: "basic" }],
  ["옛 요금제 basic", { plan: "basic" }],
]) {
  fresh();
  seedSub({ startMs: NOW0 - 40 * DAY, endMs: NOW0 - 10 * DAY, status: "past_due",
            failedAt: ts(NOW0 - 10 * DAY), retryCount: 1, ...over });
  const r = await call("confirmBilling", { updateMethod: true, authKey: "auth_2", customerKey: UID });
  const s = sub();
  eq(`${what} → 14,900원 · member`, [charges(), s.plan, r.data && r.data.plan], [[14900], "member", "member"]);
  ok("  되살아나 지금부터 한 달 · 예약 칸과 밀린 흔적을 지운다",
     s.status === "active" && s.currentPeriodStart.toMillis() === NOW0 && s.currentPeriodEnd.toMillis() === addMonthMs(NOW0) &&
     !("pendingPlan" in s) && !("failedAt" in s) && !("retryCount" in s), JSON.stringify(s));
}
{
  fresh();
  seedSub({ startMs: NOW0 - 40 * DAY, endMs: NOW0 - 10 * DAY, status: "past_due", plan: "enterprise",
            failedAt: ts(NOW0 - 10 * DAY), retryCount: 1 });
  const r = await call("confirmBilling", { updateMethod: true, authKey: "auth_2", customerKey: UID });
  ok("모르는 요금제 값이면 카드사에 결제를 보내지 않는다(금액이 비어 멈춘다)",
     !!r.error && chargeTries().length === 0, JSON.stringify(r));
  eq("  구독은 그대로 밀린 상태", sub().status, "past_due");
}
{
  fresh();
  seedSub({ startMs: NOW0 - 3 * DAY, plan: "basic" });
  const r = await call("confirmBilling", { updateMethod: true, authKey: "auth_2", customerKey: UID });
  ok("이용 중인 구독의 카드만 바꾸면 결제하지 않는다", !!r.data && charges().length === 0, JSON.stringify(r));
}

/* ── ⑥ 카드로 보낸 금액은 언제나 숫자 ── */
section("⑥ 카드사에 보낸 결제 금액");
tries.push(...chargeTries());
ok(`위의 결제 요청 ${tries.length}건의 금액이 모두 숫자였다(NaN · undefined 없음)`,
   tries.length > 0 && tries.every((c) => Number.isFinite(c.body.amount)),
   JSON.stringify(tries.filter((c) => !Number.isFinite(c.body.amount)).slice(0, 2)));

done();
