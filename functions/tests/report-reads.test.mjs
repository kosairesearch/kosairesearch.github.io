/* ============================================================
   리포트 열람 — 하루 한도 없음 · 자동 수집 제한 (2026-11-24 요금제 개편)
   ------------------------------------------------------------
   실행:  node functions/tests/report-reads.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/report-reads.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가. 사장 "요금제는 1개 14900원. 열람은 무제한." 하루 열람 한도(BASIC 5 ·
   PRO 15종목)를 없앴다. 대신 약관 제9조③ '짧은 시간에 비정상적으로 많은 열람이
   발생한 계정의 열람을 일시적으로 제한할 수 있다' 를 자동 수집 제한으로 건다.

     · 최근 60분 안에 새로 연 서로 다른 종목이 60개에 이르면 61번째 새 종목부터 거절
       (resource-exhausted · '짧은 시간에 리포트를 너무 많이 열어 열람이 잠시 제한되었습니다. …')
     · 오늘 이미 연 종목을 다시 여는 것은 언제나 허용
     · 60분이 지나 창에서 빠지면 다시 열 수 있다
     · 창은 하루 문서(한국 시간) 안에서 센다 — 자정에 새 문서가 시작되면 창도 빈다

   열람 기록(report_reads)은 한도가 없어져도 남긴다. 환불의 '이번 이용 기간에
   열었는가' 와 회원 탈퇴 정리가 그 기록을 본다(refund-rule.test ⑦ · ⑨).

   진짜 getReport · getUsage 를 가짜 파이어스토어로 돌린다(lib/paid-harness.mjs).
   ============================================================ */
import {
  clock, call, reset, seedSub, seedReports, readsDoc, tickers, store, indexNeeds,
  ok, eq, section, done, SRC, MIN, HOUR, DAY, UID, kstMidnightAfter,
} from "./lib/paid-harness.mjs";

const KO = "짧은 시간에 리포트를 너무 많이 열어 열람이 잠시 제한되었습니다. 잠시 후 다시 이용하여 주시기 바랍니다.";
const EN = "You opened too many reports in a short time, so viewing is paused for a while. Please try again shortly.";
/* 한국 시간 11월 2일 10시 — 하루 문서 안에서 몇 시간을 쓸 수 있게 오전에 시작한다 */
const T0 = Date.parse("2026-11-02T01:00:00Z");
const LIST = tickers(260);

function begin(over = {}) {
  reset();
  clock.set(T0);
  seedSub({ startMs: T0 - 3 * DAY, ...over });
  seedReports(LIST);
}
const open = (t, data = {}) => call("getReport", { ticker: t, ...data });

/* ── ① 상수 ── */
section("① 제한 값이 명세와 같다(시연과 같은 값이어야 한다)");
{
  const num = (name) => Number((new RegExp(`const ${name} = (\\d+);`).exec(SRC) || [])[1]);
  eq("BURST_WINDOW_MIN = 60", num("BURST_WINDOW_MIN"), 60);
  eq("BURST_MAX = 60", num("BURST_MAX"), 60);
  ok("하루 열람 한도(DAILY_LIMIT)가 없다", !/DAILY_LIMIT/.test(SRC));
}

/* ── ② 하루 한도가 없다 ── */
section("② 하루 한도가 없다");
{
  begin();
  const bad = [];
  for (let i = 0; i < 100; i++) {
    const r = await open(LIST[i]);
    if (!r.data) bad.push([i, r.error]);
    clock.add(2 * MIN);                                  // 2분에 한 종목 — 60분 창에 30개
  }
  ok("서로 다른 100종목을 2분 간격으로 모두 연다", bad.length === 0, JSON.stringify(bad.slice(0, 2)));
  eq("  오늘 연 종목 수 100", (readsDoc(T0) || {}).count, 100);
  const u = await call("getUsage");
  eq("  getUsage 는 {active, plan, used} — 한도 칸이 없다", u.data, { active: true, plan: "member", used: 100 });
}
{
  begin();
  const r = await open(LIST[0]);
  ok("응답에 한도(limit)가 없다", !!r.data && !("limit" in r.data), JSON.stringify(r.data && Object.keys(r.data)));
  eq("  요금제는 member · 오늘 연 종목 1", r.data && [r.data.plan, r.data.used], ["member", 1]);
}

/* ── ③ 자동 수집 제한 ── */
section("③ 최근 60분 안에 새로 연 종목 60개 — 61번째 새 종목부터 거절");
{
  begin();
  const bad = [];
  for (let i = 0; i < 60; i++) {
    const r = await open(LIST[i]);
    if (!r.data) bad.push([i, r.error]);
    clock.add(10 * 1000);                                // 10초에 한 종목 — 10분 동안 60종목
  }
  ok("60번째까지는 연다", bad.length === 0, JSON.stringify(bad.slice(0, 2)));
  const r61 = await open(LIST[60]);
  eq("61번째 새 종목은 거절(resource-exhausted)", r61.error && r61.error.code, "resource-exhausted");
  eq("  안내 문구(한국어)", r61.error && r61.error.message, KO);
  const en = await open(LIST[61], { lang: "en" });
  eq("  안내 문구(영어 화면)", en.error && en.error.message, EN);
  const waitMs = r61.error && r61.error.details && r61.error.details.waitMs;
  eq("  다시 열리는 때까지(첫 종목이 창에서 빠질 때 — 50분)", waitMs, 50 * MIN);
  const d0 = readsDoc(T0) || {};
  ok("  거절한 종목은 기록하지 않는다", !(d0.tickers || []).includes(LIST[60]) && d0.count === 60);

  const again = await open(LIST[5]);
  ok("이미 연 종목을 다시 여는 것은 언제나 허용", !!again.data, JSON.stringify(again.error));
  eq("  다시 연 것은 창에 세지 않는다(오늘 연 종목 수 그대로)", again.data && again.data.used, 60);
  eq("  다시 연 시각을 남긴다(환불의 '열람 여부'가 본다)", (readsDoc(T0) || {}).lastAt, clock.now());

  clock.set(T0 + 60 * MIN - 1);
  eq("첫 종목을 연 지 60분이 되기 직전에는 아직 거절", ((await open(LIST[60])).error || {}).code, "resource-exhausted");
  clock.set(T0 + 60 * MIN);
  ok("60분이 지나 첫 종목이 창에서 빠지면 새 종목을 연다", !!(await open(LIST[60])).data);
  eq("  한 칸만 비었다 — 바로 다음 새 종목은 다시 거절", ((await open(LIST[61])).error || {}).code, "resource-exhausted");
  clock.set(T0 + 60 * MIN + 10 * 1000);
  ok("  둘째 종목이 빠지면 또 하나 연다", !!(await open(LIST[61])).data);
}
{
  /* 한 시간에 60종목을 꾸준히 열면 하루 종일 막히지 않는다 — 사람이 읽는 속도로는 닿지 않는 선 */
  begin();
  const bad = [];
  for (let i = 0; i < 180; i++) {
    const r = await open(LIST[i]);
    if (!r.data) bad.push(i);
    clock.add(60 * 1000);                                // 1분에 한 종목 · 세 시간
  }
  ok("1분에 한 종목씩 세 시간(180종목) — 한 번도 막히지 않는다", bad.length === 0, bad.slice(0, 5).join(","));
}
{
  /* 창은 하루 문서 안에서 센다 — 한국 시간 자정에 새로 시작한다(명세가 허용한 단순한 방식) */
  begin();
  const lateNight = kstMidnightAfter(T0) - 30 * MIN;    // 23시 30분
  clock.set(lateNight);
  for (let i = 0; i < 60; i++) { await open(LIST[i]); clock.add(1000); }
  eq("23시 30분부터 60종목 — 61번째는 거절", ((await open(LIST[60])).error || {}).code, "resource-exhausted");
  clock.set(kstMidnightAfter(T0) + MIN);
  ok("자정이 지나 새 하루 문서가 시작되면 다시 연다", !!(await open(LIST[60])).data);
}

/* ── ④ 그 밖의 길 ── */
section("④ 리포트 없음 · 구독 없음 · 옛 요금제 값");
{
  begin();
  const r = await open("999999");
  eq("없는 리포트는 not-found", r.error && r.error.code, "not-found");
  ok("  기록을 남기지 않는다(제한의 한 칸을 쓰지 않는다)", readsDoc(T0) === undefined);
}
{
  reset();
  clock.set(T0);
  seedReports(LIST);
  eq("구독이 없으면 permission-denied", ((await open(LIST[0])).error || {}).code, "permission-denied");
  eq("  getUsage — {active:false, plan:null, used:0}", (await call("getUsage")).data, { active: false, plan: null, used: 0 });
}
{
  begin({ endMs: T0 - MIN });
  eq("기간이 끝난 구독은 permission-denied", ((await open(LIST[0])).error || {}).code, "permission-denied");
}
for (const plan of ["basic", "pro", "PRO", "member"]) {
  begin({ plan });
  const r = await open(LIST[0]);
  eq(`옛 요금제 값 '${plan}' 인 구독도 연다 · member 로 읽는다`, r.data && r.data.plan, "member");
}
{
  /* 구독 문서는 서버만 쓰므로 모르는 값이 생길 일은 없다. 생겨도 이용 중인 구독이면 막지 않는다. */
  begin({ plan: "enterprise" });
  eq("모르는 요금제 값이어도 이용 중인 구독이면 연다", ((await open(LIST[0])).data || {}).plan, "member");
}
{
  begin();
  eq("종목코드가 틀리면 invalid-argument", ((await open("12")).error || {}).code, "invalid-argument");
  eq("로그인하지 않으면 unauthenticated", ((await call("getReport", { ticker: LIST[0] }, { uid: null })).error || {}).code,
     "unauthenticated");
}
{
  begin();
  await open(LIST[0]);
  const d = readsDoc(T0) || {};
  ok("열람 기록에 uid · 날짜 · 종목 · 처음 연 시각 · 마지막 연 시각이 있다",
     d.uid === UID && d.day === "2026-11-02" && JSON.stringify(d.tickers) === JSON.stringify([LIST[0]]) &&
     JSON.stringify(d.openedAt) === JSON.stringify([T0]) && d.lastAt === T0, JSON.stringify(d));
  ok("열람이 복합 색인이 필요한 질의를 쓰지 않는다", indexNeeds.length === 0, indexNeeds.join(" / "));
}

done();
