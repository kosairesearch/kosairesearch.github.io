/* ============================================================
   환불 — 금액 · 실행 · 이용 종료 (2026-11-24 요금제 개편)
   ------------------------------------------------------------
   실행:  node functions/tests/refund-rule.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/refund-rule.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가. 사장 "7일 이내 환불할 때는 이용일수만 차감하고 환불. 7일 이후 환불은
   이용일수 차감하고 결제가격의 10%만큼 떼고 환불." 결제 화면 · 자주 묻는 질문 · 약관
   · 금융감독원에 낸 신고 서류가 같은 기준을 적는다. 적어 둔 것과 실제로 돌려주는
   돈이 다르면 그건 거짓말이 된다.

     P = 이번 이용 기간에 받은 금액 · usedDays = 결제일부터 신청일까지(둘 다 넣는다)
     fee = floor(P × usedDays ÷ 기간 일수) · penalty = floor(P × 10%)
       7일 이내 · 열람 없음   P             withdraw   이용은 지금 끝
       7일 이내 · 열람 있음   P − fee       early      이용은 오늘 자정까지
       7일 지남               P − fee − penalty(0원 밑이면 0)   late   오늘 자정까지
     0원이면 환불 신청을 실행하지 않는다(failed-precondition '환불 가능한 금액이 없습니다.')

   진짜 functions/index.js 를 결제 스위치를 켜고 가짜 파이어스토어 · 가짜 토스로 돌린다
   (lib/paid-harness.mjs). 계산을 여기에 옮겨 적어 시험하면 원본이 바뀌어도 통과한다.
   기대 금액은 명세의 식을 이 파일에서 따로 세운 것(expectQuote)과 명세의 예시 금액이다.

   업그레이드한 기간의 환불(refund-upgrade.test.mjs)은 요금제 변경을 없애며 지웠다.
   그 시험이 지키던 것 가운데 남는 것 — 기준은 정가가 아니라 받은 돈 · 취소는 결제
   건마다 그 건의 금액 안에서 · 결제 건 기록이 없는 옛 구독 — 은 ⑧ 이 본다.
   ============================================================ */
import {
  clock, call, reset, seedSub, seedReports, seedReads, sub, cancels, payments, store,
  indexNeeds, ok, eq, section, done, won, DAY, HOUR, MIN, UID, ts, kstMidnightAfter, S,
} from "./lib/paid-harness.mjs";

const P = 14900;
/* 한국 시간 2026년 11월 2일 14시 결제 → 12월 2일 14시까지(30일 기간) */
const START = Date.parse("2026-11-02T05:00:00Z");
const TICKER = "005930";

/* 명세의 식 — 서버 코드를 옮긴 것이 아니라 명세를 따로 세운 것 */
function expectQuote({ price = P, usedDays, total, elapsed, viewed }) {
  const within = elapsed <= 7;
  if (within && !viewed) return { amount: price, why: "withdraw", fee: 0, penalty: 0 };
  const fee = Math.floor(price * usedDays / total);
  if (within) return { amount: price - fee, why: "early", fee, penalty: 0 };
  const penalty = Math.floor(price * 10 / 100);
  return { amount: Math.max(0, price - fee - penalty), why: "late", fee, penalty };
}

/* 결제한 상태에서 시작한다. viewed 면 결제 한 시간 뒤 리포트를 하나 연 기록을 둔다
   (getReport 가 남기는 모양 그대로 — 진짜 getReport 를 거치는 길은 ⑦ 이 본다). */
async function begin({ startMs = START, endMs, viewed = false, ...rest } = {}) {
  reset();
  clock.set(startMs);
  seedSub({ startMs, endMs, ...rest });
  seedReports([TICKER, "000660", "035420"]);
  if (viewed) seedReads(startMs + HOUR, [TICKER]);
}
/* n일째(결제한 날 = 1일째)의 같은 시각 */
const day = (n, startMs = START) => startMs + (n - 1) * DAY;
const endOf = () => sub().currentPeriodEnd.toMillis();

/* ── ① 명세의 예시 금액 ── */
section("① 명세의 예시 금액 (30일 기간 · 14,900원)");
{
  await begin();
  clock.set(day(2));
  const q = (await call("refundPreview")).data || {};
  eq("2일째 · 열람 없음 → 14,900원 전액(청약철회)", [q.amount, q.why], [14900, "withdraw"]);
  eq("  청약철회는 이용일 · 위약금을 빼지 않는다", [q.fee, q.penalty, q.chargedToday], [0, 0, false]);
  eq("  기간 일수 30 · 이용일수 2 · 받은 금액 14,900", [q.totalDays, q.usedDays, q.price], [30, 2, 14900]);
}
{
  await begin({ viewed: true });
  clock.set(day(3));
  const q = (await call("refundPreview")).data || {};
  eq("3일째 · 열람 있음 → 14,900 − 1,490 = 13,410원", [q.amount, q.why, q.fee, q.penalty], [13410, "early", 1490, 0]);
  eq("  이용일수 3 · 오늘 값을 받는다", [q.usedDays, q.chargedToday], [3, true]);
}
{
  await begin({ viewed: true });
  clock.set(day(10));
  const q = (await call("refundPreview")).data || {};
  eq("10일째 → 14,900 − 4,966 − 1,490 = 8,444원", [q.amount, q.why, q.fee, q.penalty], [8444, "late", 4966, 1490]);
}
{
  await begin({ viewed: true });
  clock.set(day(27));
  const q = (await call("refundPreview")).data || {};
  eq("27일째 → 0원(환불 없음)", [q.amount, q.why], [0, "late"]);
  eq("  미리 보기는 0원을 오류 없이 준다(화면이 해지를 안내한다)", [q.fee, q.penalty, q.usedDays], [13410, 1490, 27]);
}
{
  /* 7일이 지나면 열람 여부와 관계없이 이용일수와 위약금을 뺀다 */
  await begin();
  clock.set(day(10));
  eq("10일째 · 열람 없음도 8,444원", ((await call("refundPreview")).data || {}).amount, 8444);
}

/* ── ② 7일 경계 ── */
section("② 7일 경계 — 결제일부터 7일 이내(결제한 날은 세지 않는다)");
{
  await begin();
  clock.set(day(8));
  const q = (await call("refundPreview")).data || {};
  eq("8일째(결제 뒤 7일) · 열람 없음 → 아직 전액", [q.amount, q.why], [14900, "withdraw"]);
}
{
  await begin({ viewed: true });
  clock.set(day(8));
  const q = (await call("refundPreview")).data || {};
  eq("8일째 · 열람 있음 → 이용일수만 뺀다(14,900 − 3,973 = 10,927원)",
     [q.amount, q.why, q.penalty], [10927, "early", 0]);
}
{
  await begin();
  clock.set(day(9));
  const q = (await call("refundPreview")).data || {};
  eq("9일째(결제 뒤 8일) · 열람 없음 → 위약금까지 뺀다(14,900 − 4,470 − 1,490 = 8,940원)",
     [q.amount, q.why, q.fee, q.penalty], [8940, "late", 4470, 1490]);
}

/* ── ③ 31일 · 28일 기간 ── */
section("③ 31일 · 28일 기간");
{
  const s31 = Date.parse("2026-12-02T05:00:00Z");      // 12월 2일 → 1월 2일
  await begin({ startMs: s31, viewed: true });
  clock.set(day(3, s31));
  const a = (await call("refundPreview")).data || {};
  eq("31일 기간 · 3일째 → 14,900 − floor(14,900×3÷31)=1,441 → 13,459원",
     [a.totalDays, a.amount, a.fee], [31, 13459, 1441]);
  clock.set(day(10, s31));
  const b = (await call("refundPreview")).data || {};
  eq("31일 기간 · 10일째 → 14,900 − 4,806 − 1,490 = 8,604원", [b.amount, b.fee, b.penalty], [8604, 4806, 1490]);
}
{
  const s28 = Date.parse("2027-02-02T05:00:00Z");      // 2월 2일 → 3월 2일
  await begin({ startMs: s28, viewed: true });
  clock.set(day(3, s28));
  const a = (await call("refundPreview")).data || {};
  eq("28일 기간 · 3일째 → 14,900 − 1,596 = 13,304원", [a.totalDays, a.amount, a.fee], [28, 13304, 1596]);
  clock.set(day(10, s28));
  const b = (await call("refundPreview")).data || {};
  eq("28일 기간 · 10일째 → 14,900 − 5,321 − 1,490 = 8,089원", [b.amount, b.fee, b.penalty], [8089, 5321, 1490]);
  clock.set(day(28, s28));
  const c = (await call("refundPreview")).data || {};
  eq("28일 기간 · 마지막 날 → 이용일수가 기간 일수에서 멈추고 0원", [c.usedDays, c.amount], [28, 0]);
}

/* ── ④ 0원이면 실행하지 않는다 ── */
section("④ 0원이면 환불 신청을 실행하지 않는다");
{
  await begin({ viewed: true });
  clock.set(day(27));
  const before = JSON.stringify(sub());
  const r = await call("requestRefund", { expectAmount: 0 });
  eq("거절한다(failed-precondition)", r.error && r.error.code, "failed-precondition");
  eq("문구 '환불 가능한 금액이 없습니다.'", r.error && r.error.message, "환불 가능한 금액이 없습니다.");
  eq("카드사에 취소를 보내지 않는다", cancels().length, 0);
  ok("구독을 건드리지 않는다(환불 완료 · 이용 종료를 적지 않는다)",
     JSON.stringify(sub()) === before && !sub().refundedAt && sub().cancelAtPeriodEnd === false);
  eq("회원에게 더 청구하지 않는다(결제 요청 0건)", S.toss.length, 0);
  const r2 = await call("requestRefund", {});
  eq("보여 준 금액 없이 불러도 거절한다", r2.error && r2.error.code, "failed-precondition");
}

/* ── ⑤ 미리 보기와 실행이 같다 ── */
section("⑤ 미리 보기와 실행이 같은 금액 · 같은 종료 시각 (30일 기간 · 날마다 · 열람 있음/없음)");
{
  const bad = [];
  let n0 = 0, cases = 0;
  for (let n = 1; n <= 30; n++) {
    for (const viewed of [false, true]) {
      await begin({ viewed });
      clock.set(day(n));
      const q = (await call("refundPreview")).data;
      const want = expectQuote({ usedDays: n, total: 30, elapsed: n - 1, viewed });
      cases++;
      if (!q || q.amount !== want.amount || q.why !== want.why || q.fee !== want.fee || q.penalty !== want.penalty) {
        bad.push({ n, viewed, got: q && [q.amount, q.why, q.fee, q.penalty], want }); continue;
      }
      const r = await call("requestRefund", { expectAmount: q.amount });
      if (q.amount <= 0) {
        n0++;
        if (!r.error || r.error.message !== "환불 가능한 금액이 없습니다." || cancels().length) bad.push({ n, viewed, zero: r });
        continue;
      }
      const back = cancels().reduce((a, c) => a + c.amount, 0);
      if (!r.data || r.data.amount !== q.amount || r.data.endsAt !== q.endsAt || back !== q.amount ||
          endOf() !== Date.parse(q.endsAt)) {
        bad.push({ n, viewed, preview: [q.amount, q.endsAt], run: r.data || r.error, back, end: endOf() });
      }
    }
  }
  ok(`${cases}가지 — 미리 보기가 명세의 식과 1원까지 같고, 실행이 같은 금액을 돌려주고 같은 시각에 끝낸다`,
     bad.length === 0, JSON.stringify(bad.slice(0, 3)));
  ok(`그중 0원인 ${n0}가지는 실행하지 않았다`, n0 > 0);
}

/* ── ⑥ 이용 종료 시각 ── */
section("⑥ 이용 종료 — 청약철회는 지금, 나머지는 오늘 자정(한국 시간)");
{
  await begin();
  clock.set(day(3) + 3 * HOUR);
  const q = (await call("refundPreview")).data;
  const r = await call("requestRefund", { expectAmount: q.amount });
  eq("청약철회 — 지금 끝난다", endOf(), clock.now());
  eq("  응답의 종료 시각도 지금", r.data && Date.parse(r.data.endsAt), clock.now());
  const g = await call("getReport", { ticker: TICKER });
  eq("  환불 직후 리포트가 잠긴다", g.error && g.error.code, "permission-denied");
}
for (const [what, n, viewed] of [["7일 이내 · 열람 있음(early)", 3, true], ["7일 지남(late)", 12, false]]) {
  await begin({ viewed });
  clock.set(day(n) + 2 * HOUR);                        // 한국 시간 16시
  const q = (await call("refundPreview")).data;
  const r = await call("requestRefund", { expectAmount: q.amount });
  const midnight = kstMidnightAfter(clock.now());
  eq(`${what} — 오늘 자정까지`, endOf(), midnight);
  eq(`  응답의 종료 시각도 자정`, r.data && Date.parse(r.data.endsAt), midnight);
  ok("  구독은 살아 있되 다음 결제를 하지 않게 표시한다",
     sub().status === "active" && sub().cancelAtPeriodEnd === true && !!sub().refundedAt);
  clock.set(midnight - MIN);
  ok("  자정 1분 전까지 리포트를 열 수 있다", !!(await call("getReport", { ticker: "000660" })).data);
  clock.set(midnight);
  eq("  자정이 되면 잠긴다", ((await call("getReport", { ticker: "000660" })).error || {}).code, "permission-denied");
}
{
  await begin({ viewed: true });
  clock.set(day(3));
  const q = (await call("refundPreview")).data;
  await call("requestRefund", { expectAmount: q.amount });
  const again = await call("requestRefund", { expectAmount: q.amount });
  eq("환불을 두 번 누르면 두 번째는 막는다", again.error && again.error.message, "이미 환불이 완료되었습니다.");
  eq("  취소는 한 번만 나갔다", cancels().length, 1);
  eq("  환불 견적도 막는다", ((await call("refundPreview")).error || {}).message, "이미 환불이 완료되었습니다.");
}

/* ── ⑦ 열람 여부 ── */
section("⑦ '이번 이용 기간에 열었는가'");
{
  /* 같은 날 앞선 구독(환불 · 자정까지)에서 연 것은 이번 기간이 아니다 */
  await begin();
  seedReads(START - 3 * HOUR, [TICKER]);              // 결제 세 시간 전
  clock.set(day(2));
  eq("결제한 날, 결제 전의 열람은 세지 않는다 → 전액", ((await call("refundPreview")).data || {}).why, "withdraw");
}
{
  await begin();
  seedReads(START - 3 * HOUR, [TICKER]);
  clock.set(START + HOUR);
  await call("getReport", { ticker: TICKER });          // 결제 전에 연 종목을 다시 연다
  clock.set(day(2));
  eq("결제 뒤에 같은 종목을 다시 연 것은 센다 → 이용일수 차감", ((await call("refundPreview")).data || {}).why, "early");
}
{
  await begin();
  clock.set(START + 30 * MIN);
  const g = await call("getReport", { ticker: "035420" });  // 진짜 getReport 로 연다
  clock.set(day(2));
  eq("getReport 로 연 기록을 환불이 읽는다 → 이용일수 차감",
     [!!g.data, ((await call("refundPreview")).data || {}).why], [true, "early"]);
}
{
  await begin();
  seedReads(day(4), [TICKER]);
  clock.set(day(5));
  eq("결제 다음 날부터의 열람은 센다", ((await call("refundPreview")).data || {}).why, "early");
}
{
  await begin();
  seedReads(START - 2 * DAY, [TICKER]);               // 지난 기간
  clock.set(day(3));
  eq("지난 기간의 열람은 세지 않는다", ((await call("refundPreview")).data || {}).why, "withdraw");
}
{
  /* 열람 시각(lastAt)을 남기기 전의 기록 — updatedAt 으로 본다 */
  await begin();
  store.set(`report_reads/${UID}_2026-11-02`, { uid: UID, day: "2026-11-02", tickers: [TICKER], updatedAt: ts(START + HOUR) });
  clock.set(day(2));
  eq("옛 기록 · 결제 뒤 updatedAt → 센다", ((await call("refundPreview")).data || {}).why, "early");
  store.set(`report_reads/${UID}_2026-11-02`, { uid: UID, day: "2026-11-02", tickers: [TICKER], updatedAt: ts(START - HOUR) });
  eq("옛 기록 · 결제 전 updatedAt → 세지 않는다", ((await call("refundPreview")).data || {}).why, "withdraw");
}
{
  /* 저장소에는 파이어스토어 복합 색인 설정이 없다. 환불 계산이 '같다 + 범위' 질의를
     쓰면 결제를 켜는 날 환불 · 탈퇴가 '색인이 필요하다' 로 멈춘다. */
  indexNeeds.length = 0;
  await begin({ viewed: true });
  clock.set(day(3));
  await call("refundPreview");
  await call("requestRefund", {});
  ok("환불 견적 · 환불이 복합 색인이 필요한 질의를 쓰지 않는다", indexNeeds.length === 0, indexNeeds.join(" / "));
}

/* ── ⑧ 결제 건 · 보여 준 금액 ── */
section("⑧ 받은 돈이 기준 · 결제 건마다 취소 · 보여 준 금액과 다르면 멈춘다");
{
  /* 결제 건 기록(periodPayments)이 붙기 전의 옛 구독 — 옛 요금제 값(basic)이어도 정가 14,900원 */
  await begin({ plan: "basic", payKey: "pay_old", periodPayments: undefined });
  clock.set(day(2));
  const q = (await call("refundPreview")).data || {};
  eq("결제 건 기록이 없는 옛 구독 → 정가 14,900원 기준", [q.price, q.amount], [14900, 14900]);
  const r = await call("requestRefund", { expectAmount: q.amount });
  eq("  lastPaymentKey 한 건에서 그 금액을 취소한다", cancels(), [{ key: "pay_old", amount: 14900 }]);
  ok("  실행됐다", !!r.data, JSON.stringify(r.error));
}
{
  /* 요금제를 하나로 합치기 전에 업그레이드 차액을 낸 기간 — 결제가 두 건이다 */
  await begin({
    plan: "pro", payKey: "pay_base", viewed: true,
    periodPayments: [{ key: "pay_base", amount: 9900, from: START }, { key: "pay_up", amount: 3833, from: START + DAY }],
  });
  clock.set(day(3));
  const q = (await call("refundPreview")).data || {};
  eq("기준은 정가가 아니라 받은 돈(9,900 + 3,833 = 13,733원)", q.price, 13733);
  eq("  13,733 − floor(13,733×3÷30)=1,373 → 12,360원", q.amount, 12360);
  await call("requestRefund", { expectAmount: q.amount });
  const c = cancels();
  eq("  최근 결제부터, 각 건의 금액 안에서 나눠 취소한다", c, [{ key: "pay_up", amount: 3833 }, { key: "pay_base", amount: 8527 }]);
  eq("  환불 내역도 건마다 남는다(why early)",
     payments().filter((p) => p.kind === "refund").map((p) => [p.amount, p.why]), [[-3833, "early"], [-8527, "early"]]);
}
{
  await begin({ viewed: true });
  clock.set(day(8) + 9 * HOUR + 50 * MIN);              // 8일째 23시 50분 — 아직 7일 이내
  const q = (await call("refundPreview")).data || {};
  clock.add(20 * MIN);                                  // 확인 창을 연 채 자정을 넘겼다
  const r = await call("requestRefund", { expectAmount: q.amount });
  eq("자정을 넘겨 7일이 지나면 금액이 바뀌어 실행하지 않는다", r.error && r.error.code, "failed-precondition");
  eq("  새 금액을 알려 준다(10,927 → 8,940원)", [q.amount, r.error && r.error.details && r.error.details.amount], [10927, 8940]);
  ok("  문구에 새 금액이 있다", /8,940원으로 변경되었습니다/.test((r.error && r.error.message) || ""), r.error && r.error.message);
  eq("  취소를 보내지 않았다", cancels().length, 0);
}
{
  await begin();
  clock.set(day(3));
  const q = (await call("refundPreview")).data || {};
  await call("getReport", { ticker: TICKER });          // 확인 창을 띄운 뒤 리포트를 열었다
  const r = await call("requestRefund", { expectAmount: q.amount });
  eq("확인 창 뒤에 리포트를 열면 전액이 아니게 되어 멈춘다(14,900 → 13,410원)",
     [q.amount, r.error && r.error.details && r.error.details.amount], [14900, 13410]);
}

/* ── ⑨ 회원 탈퇴 ── */
section("⑨ 회원 탈퇴도 같은 계산으로 먼저 돌려준다");
{
  await begin();
  clock.set(day(3));
  const r = await call("deleteAccount");
  eq("7일 이내 · 열람 없음 → 14,900원을 돌려주고 탈퇴", r.data && r.data.refunded, 14900);
  eq("  계정을 지웠다", S.deletedUsers, [UID]);
  ok("  구독을 닫고 카드 정보를 지웠다", sub().status === "deleted" && !("billingKey" in sub()) && !("card" in sub()));
}
{
  await begin({ viewed: true, pendingPlan: "basic" });
  clock.set(day(10));
  const r = await call("deleteAccount");
  eq("10일째 → 8,444원", r.data && r.data.refunded, 8444);
  ok("  옛 요금제 변경 예약(pendingPlan)도 지운다", !("pendingPlan" in sub()));
}
{
  await begin({ viewed: true });
  clock.set(day(27));
  const r = await call("deleteAccount");
  eq("27일째 → 돌려줄 금액 0원 · 취소 없이 탈퇴만", [r.data && r.data.refunded, cancels().length, S.deletedUsers.length], [0, 0, 1]);
}
{
  /* 하루 한도가 없어져도 연 날마다 기록이 쌓인다. 200개씩 한 번만 지우면 나머지가 남는다. */
  await begin();
  for (let i = 0; i < 450; i++) store.set(`report_reads/${UID}_d${i}`, { uid: UID, tickers: [TICKER] });
  for (let i = 0; i < 3; i++) store.set(`report_reads/other_d${i}`, { uid: "other", tickers: [TICKER] });
  clock.set(day(2));
  await call("deleteAccount");
  const left = [...store.keys()].filter((k) => k.startsWith("report_reads/"));
  eq("열람 기록 450개를 모두 지운다(다른 회원 것은 그대로)", left.length, 3);
  ok("  탈퇴가 복합 색인이 필요한 질의를 쓰지 않는다", indexNeeds.length === 0, indexNeeds.join(" / "));
}

done();
