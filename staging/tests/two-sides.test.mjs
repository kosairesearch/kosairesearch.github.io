/* ============================================================
   서버와 미리보기가 같은 답을 내는가 — 진짜 서버 함수와 시연을 나란히

   왜 있는가. 결제 규칙이 두 벌로 짜여 있다. 서버(functions/index.js)와
   미리보기(staging/demo-backend.js). 두 벌이면 갈라진다 — 실제로 갈라졌었고,
   그때 미리보기 주석에는 "서버와 같다" 고 적혀 있었다. 주석이 그 사실을 덮고
   있었다.

   예전에는 서버 계산을 이 파일에 옮겨 적고 그 사본과 견줬다. 원본이 바뀌어도
   사본은 그대로라, 2026-11-24 요금제 개편 때 이 시험은 서버의 옛 상수(DAILY_LIMIT)를
   읽다 멈췄다. 이제는 진짜 서버 함수를 돌린다 — functions/tests/lib/paid-harness.mjs
   (결제 스위치 KOSAI_PAYMENTS=on · 가짜 파이어스토어 · 가짜 토스 · 가짜 시계)가 함수
   파일을 그대로 부르고, 시연도 같은 가짜 시계로 돈다. 같은 순간 같은 구독에 두 쪽이
   낸 답을 1원 · 1밀리초까지 견준다.

   보는 것
     ① 환불 견적(refundPreview) — 기간 28~31일 × 날마다 × 열람(없음 · 결제 전 같은 날 ·
        결제 뒤 같은 날 · 다음 날) × 결제 시각(낮 · 자정 직전), 돌려주는 칸 전부
     ② 환불 실행(requestRefund) — 금액 · 사유 · 이용 종료 시각, 0원 거절, 다시 눌렀을 때 ·
        해지를 눌렀을 때의 문구
     ③ 명세 예시 — 3일째 13,410 / 10일째 8,444 / 27일째 0원 / 2일째 미열람 14,900 (두 쪽 모두)
     ④ 자동 수집 제한 — 같은 순서로 열면 같은 자리에서 거절하고(남은 시간 waitMs 까지),
        다시 연 종목은 받고, 60분 뒤 · 자정 뒤에 같이 다시 연다. 거절 문구(한국어 · 영어)
     ⑤ 값 — 요금 · 창 크기 · 문턱 · 7일 · 10% 가 두 쪽에서 같다, 서버에 옛 하루 한도 ·
        요금제 변경이 없다, 옛 요금제 이름(basic · pro)을 두 쪽 다 멤버십으로 읽는다

   실행
     npm install --no-save jsdom
     node staging/tests/two-sides.test.mjs
   ============================================================ */
import * as H from "../../functions/tests/lib/paid-harness.mjs";   // 먼저 — 시계 · 시간대(UTC)를 서버 시험과 같게 깐다
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work-two");

const require_ = createRequire(import.meta.url);
let JSDOM;
try {
  ({ JSDOM } = await import(require_.resolve("jsdom", { paths: [ROOT] })));
} catch (e) {
  console.error("jsdom 이 없습니다.  npm install --no-save jsdom  후 다시 실행하세요.");
  process.exit(2);
}

rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });
writeFileSync(TMP + "/payment-config.js", readFileSync(STAGING + "/payment-config.js"));
writeFileSync(TMP + "/demo.js", readFileSync(STAGING + "/demo-backend.js", "utf8")
  .replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"'));
writeFileSync(TMP + "/stub.js", `
export const app={}; export const isConfigured=true; export const SOCIAL={};
export const auth={currentUser:{uid:"u1",email:"a@b.c",displayName:"t"}};
export const onAuthStateChanged=(a,fn)=>{Promise.resolve().then(()=>fn(a.currentUser));return()=>{}};
export const signOut = async () => {};`);

const dom = new JSDOM("<!doctype html><body>", { url: "https://kosai.kr/staging/x.html" });
for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                 "location", "localStorage", "URL", "URLSearchParams"]) globalThis[k] = dom.window[k];
/* 토스 주소는 서버 시험 도구의 가짜 토스로, 리포트 파일은 시연이 받아 가는 정적 JSON 대역으로 */
const tossFetch = globalThis.fetch;
globalThis.fetch = async (url, init) => (/\/data\/reports_v2\//.test(String(url))
  ? { ok: true, json: async () => ({ ticker: "x", earnings: "실적 분석", verdict: "종합 의견" }) }
  : tossFetch(url, init));
await import(`file://${TMP}/demo.js`);
const CFG = await import(`file://${TMP}/payment-config.js`);
const D = window.KOSDemo, PW = window.KOSPaywall;
await PW.ready;

const { DAY, HOUR, MIN, clock } = H;
const P = 14900;

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};

/* 두 쪽에 같은 구독을 심는다. view — 열람 기록
     null      결제 뒤 열람 없음
     "before"  결제 한 시간 전 같은 날 연 기록(이전 구독 · 결제 전) — 이번 기간 열람이 아니다
     "after"   결제 한 시간 뒤 연 기록
     "next"    결제 다음 날 연 기록(그날이 왔을 때만 심는다) */
function seedBoth({ startMs, endMs, view = null, plan = "member", amount = P }) {
  H.reset();
  H.seedSub({ startMs, endMs, plan, amount });
  H.seedReports(["005930", "000660"]);
  if (view === "before") H.seedReads(startMs - HOUR, ["005930"]);
  if (view === "after") H.seedReads(startMs + HOUR, ["005930"]);
  if (view === "next") H.seedReads(startMs + DAY, ["005930"]);
  localStorage.clear();
  localStorage.setItem("kos-demo-sub", JSON.stringify({
    status: "active", plan, currentPeriodStart: startMs, currentPeriodEnd: endMs, cancelAtPeriodEnd: false,
    startedAt: startMs, periodPayments: [{ key: "pay_seed", amount, from: startMs }],
    readsSincePay: view === "after" || view === "next" ? 1 : 0,
  }));
}
const demoCall = (name, data = {}) => D.call(name, data).then((r) => ({ data: r.data }), (e) => ({ error: { code: e.code, message: e.message } }));
const msOf = (v) => (typeof v === "number" ? v : Date.parse(v));
const FIELDS = ["amount", "why", "reason", "chargedToday", "price", "usedDays", "totalDays", "fee", "penalty"];

/* 견적 · 실행 한 쌍을 견준다 — 같은 칸 · 같은 값, 이용 종료 시각은 1밀리초까지, 거절이면 같은 문구 */
function differ(srv, demo, fields) {
  if (srv.error || demo.error) {
    const a = srv.error ? srv.error.message : "(거절 없음)", b = demo.error ? demo.error.message : "(거절 없음)";
    return a === b ? null : `거절 문구 — 서버 "${a}" · 시연 "${b}"`;
  }
  for (const f of fields) {
    if (srv.data[f] !== demo.data[f]) return `${f} — 서버 ${JSON.stringify(srv.data[f])} · 시연 ${JSON.stringify(demo.data[f])}`;
  }
  if (msOf(srv.data.endsAt) !== msOf(demo.data.endsAt)) {
    return `endsAt — 서버 ${srv.data.endsAt} · 시연 ${new Date(msOf(demo.data.endsAt)).toISOString()}`;
  }
  return null;
}

/* ── ① 환불 견적 ─────────────────────────────────────────────── */
console.log("── ① 환불 견적 — 날마다 · 열람마다 · 기간 길이마다 ──\n");
{
  /* 결제 시각 두 가지 — 한국 시간 낮(14:00)과 자정 직전(23:30). 자정 직전에 결제하면 '결제 한 시간 뒤'의 열람이
     다음 날 기록에 들어가고, 오늘을 세는 시각도 날을 넘는다. */
  const STARTS = [Date.parse("2026-11-02T05:00:00Z"), Date.parse("2026-11-02T14:30:00Z")];
  let cases = 0, mismatch = null, refused = 0;
  const seen = new Set();
  for (const startMs of STARTS) {
    for (const len of [28, 29, 30, 31]) {
      const endMs = startMs + len * DAY;
      for (let dayNo = 0; dayNo <= len && !mismatch; dayNo++) {       // 마지막(len)은 기간이 끝난 뒤 — 두 쪽 모두 거절해야 한다
        for (const view of [null, "before", "after", "next"]) {
          if (view === "next" && dayNo < 1) continue;          // 아직 오지 않은 날의 기록은 없다
          const now = startMs + dayNo * DAY + 3 * HOUR;
          clock.set(now);
          seedBoth({ startMs, endMs, view });
          const srv = await H.call("refundPreview");
          const demo = await demoCall("refundPreview");
          cases++;
          if (srv.error) refused++; else seen.add(srv.data.why);
          const d = differ(srv, demo, FIELDS);
          if (d) { mismatch = { start: new Date(startMs).toISOString(), len, dayNo, view, d }; break; }
        }
      }
    }
  }
  if (mismatch) console.log("  " + JSON.stringify(mismatch));
  ok(`견적 ${cases}가지 — 금액 · 사유 · 계산 내역 · 이용 종료 시각이 1원 · 1밀리초까지 같다`, !mismatch);
  ok(`세 갈래(withdraw · early · late)와 기간이 끝난 경우(거절 ${refused}건)를 모두 지났다`,
     ["withdraw", "early", "late"].every((w) => seen.has(w)) && refused > 0, [...seen].join(","));
}

/* ── ② 환불 실행 ─────────────────────────────────────────────── */
console.log("\n── ② 환불 실행 — 금액 · 사유 · 이용 종료, 0원 거절, 다시 누를 때 ──\n");
{
  const startMs = Date.parse("2026-11-02T05:00:00Z"), endMs = startMs + 30 * DAY;
  let cases = 0, mismatch = null, zeros = 0;
  for (let dayNo = 0; dayNo < 30 && !mismatch; dayNo++) {
    for (const view of [null, "after"]) {
      const now = startMs + dayNo * DAY + 3 * HOUR;
      clock.set(now); seedBoth({ startMs, endMs, view });
      const q = (await H.call("refundPreview")).data;
      const srv = await H.call("requestRefund", { expectAmount: q.amount });
      const demo = await demoCall("requestRefund", { expectAmount: q.amount });
      cases++;
      if (srv.error && srv.error.message === "환불 가능한 금액이 없습니다.") zeros++;
      let d = differ(srv, demo, ["amount", "why"]);
      if (!d && !srv.error) {
        /* 환불이 끝난 구독 — 다시 환불을 누르거나 해지를 누르면 두 쪽이 같은 말로 거절한다 */
        for (const [fn, data] of [["requestRefund", {}], ["cancelSubscription", {}], ["refundPreview", {}]]) {
          const a = await H.call(fn, data), b = await demoCall(fn, data);
          d = differ(a, b, []);
          if (!d && !(a.error && b.error)) d = `${fn} — 환불 뒤에도 거절하지 않았다`;
          if (d) { d = `${fn}: ${d}`; break; }
        }
      }
      if (d) { mismatch = { dayNo, view, d }; break; }
    }
  }
  if (mismatch) console.log("  " + JSON.stringify(mismatch));
  ok(`실행 ${cases}가지 — 돌려준 금액 · 사유 · 이용 종료 시각이 같다 · 환불 뒤 거절 문구가 같다`, !mismatch);
  ok(`0원(실행 거절)도 지났다 (${zeros}건)`, zeros > 0);

  /* 보여 준 금액과 다르면 두 쪽 모두 실행하지 않는다 */
  clock.set(startMs + 2 * DAY + 3 * HOUR); seedBoth({ startMs, endMs, view: "after" });
  const a = await H.call("requestRefund", { expectAmount: P }), b = await demoCall("requestRefund", { expectAmount: P });
  ok("보여 준 금액과 다르면 실행하지 않는다 — 같은 문구", !!(a.error && b.error) && a.error.message === b.error.message,
     `${a.error && a.error.message} · ${b.error && b.error.message}`);
}

/* ── ③ 명세 예시 ─────────────────────────────────────────────── */
console.log("\n── ③ 명세 예시(30일 기간) ──\n");
{
  const startMs = Date.parse("2026-11-02T05:00:00Z"), endMs = startMs + 30 * DAY;
  for (const [n, view, want, why] of [[3, "after", 13410, "early"], [10, "after", 8444, "late"],
                                       [27, "after", 0, "late"], [2, null, 14900, "withdraw"]]) {
    clock.set(startMs + (n - 1) * DAY + 3 * HOUR); seedBoth({ startMs, endMs, view });
    const s = (await H.call("refundPreview")).data, d = (await demoCall("refundPreview")).data;
    ok(`${n}일째${view ? " · 열람 있음" : " · 열람 없음"} → ${want.toLocaleString("ko-KR")}원 (서버 ${s.amount} · 시연 ${d.amount})`,
       s.amount === want && d.amount === want && s.why === why && d.why === why);
  }
  ok("환불 안내의 예시(13,410원 · 8,444원)가 두 쪽 계산과 같다",
     CFG.REFUND_NOTICE.ko.notes.some((x) => x.includes("13,410원") && x.includes("8,444원")));
}

/* ── ④ 자동 수집 제한 ───────────────────────────────────────── */
console.log("\n── ④ 자동 수집 제한 — 같은 순서로 열면 같은 자리에서 거절한다 ──\n");
{
  const T = H.tickers(200);
  const startMs = Date.parse("2026-11-02T01:00:00Z");      // 한국 시간 10:00
  clock.set(startMs + 30 * MIN);
  seedBoth({ startMs, endMs: startMs + 30 * DAY });
  H.seedReports(T);
  const open = async (t, lang) => {
    const s = await H.call("getReport", lang ? { ticker: t, lang } : { ticker: t });
    let d;
    try { const r = await PW.fetchPaid(t, lang ? { lang } : undefined); d = { data: r }; }
    catch (e) { d = { error: { code: e.code, message: e.message, details: e.details } }; }
    return { s, d };
  };
  const same = (r) => (!!r.s.error === !!r.d.error) && (!r.s.error || (r.s.error.code === r.d.error.code && r.s.error.message === r.d.error.message
    && JSON.stringify(r.s.error.details) === JSON.stringify(r.d.error.details)))
    && (!!r.s.error || (r.s.data.used === r.d.data.used && r.s.data.plan === r.d.data.plan));

  let bad = null, accepted = 0, refusedAt = -1;
  for (let i = 0; i < 70 && !bad; i++) {
    clock.add(10 * 1000);                                 // 10초마다 하나씩 — 사람이 아니라 프로그램의 속도
    const r = await open(T[i]);
    if (!same(r)) bad = `${i + 1}번째(${T[i]}) — 서버 ${JSON.stringify(r.s.error || r.s.data.used)} · 시연 ${JSON.stringify(r.d.error || r.d.data.used)}`;
    else if (!r.s.error) accepted++;
    else if (refusedAt < 0) refusedAt = i + 1;
  }
  ok("70개를 잇달아 열면 두 쪽 모두 60개를 받고 61번째부터 거절한다(남은 시간 waitMs · 오늘 연 수 used 까지 같다)",
     !bad && accepted === 60 && refusedAt === 61, bad || `받음 ${accepted} · 첫 거절 ${refusedAt}번째`);

  const re = await open(T[5]);
  ok("오늘 이미 연 종목은 두 쪽 모두 받는다", same(re) && !re.s.error, JSON.stringify(re.s.error || re.d.error || ""));

  const ko = await open(T[80]), en = await open(T[81], "en");
  ok("거절 문구(한국어)가 같다 — 명세 문구",
     same(ko) && ko.s.error && ko.s.error.message === "짧은 시간에 리포트를 너무 많이 열어 열람이 잠시 제한되었습니다. 잠시 후 다시 이용하여 주시기 바랍니다.",
     JSON.stringify([ko.s.error, ko.d.error]));
  ok("거절 문구(영어 · lang:en)가 같다 — 명세 문구",
     same(en) && en.s.error && en.s.error.message === "You opened too many reports in a short time, so viewing is paused for a while. Please try again shortly.",
     JSON.stringify([en.s.error, en.d.error]));

  /* 첫 열람에서 60분이 지나면 맨 앞 것부터 창에서 빠진다 */
  clock.set(startMs + 30 * MIN + 10 * 1000 + 60 * MIN + 1);
  const back = await open(T[90]);
  ok("60분이 지나 창에서 빠지면 두 쪽 모두 다시 받는다", same(back) && !back.s.error, JSON.stringify(back.s.error || back.d.error || ""));

  /* 자정 — 하루 기록이 새로 시작되어 창도 빈다(두 쪽 모두 같은 단순화) */
  seedBoth({ startMs, endMs: startMs + 30 * DAY });
  H.seedReports(T);
  clock.set(Date.parse("2026-11-03T14:40:00Z"));          // 한국 시간 23:40
  let n = 0, b2 = null;
  for (let i = 0; i < 60 && !b2; i++) { clock.add(5 * 1000); const r = await open(T[100 + i]); if (!same(r) || r.s.error) b2 = JSON.stringify(r.s.error || r.d.error); else n++; }
  const full = await open(T[170]);
  clock.set(Date.parse("2026-11-03T15:01:00Z"));          // 한국 시간 다음 날 00:01 — 23:40 의 열람은 아직 60분 안이다
  const after = await open(T[171]);
  ok("자정 전 60개 · 자정 뒤 새 종목 — 두 쪽 모두 하루 기록을 새로 시작한다", !b2 && n === 60 && same(full) && !!full.s.error && same(after) && !after.s.error,
     b2 || JSON.stringify([full.s.error, after.s.error, after.d.error]));
}

/* ── ⑤ 값 ───────────────────────────────────────────────────── */
console.log("\n── ⑤ 요금 · 창 · 문턱 · 7일 · 10% 가 두 쪽에서 같은가 ──\n");
{
  const SRC = H.SRC;
  const num = (re) => { const m = SRC.match(re); return m ? Number(m[1]) : NaN; };
  const price = num(/const PRICE = \{\s*member:\s*(\d+)\s*\}/);
  ok(`요금 — 서버 ${price}원 · 화면 ${CFG.PLAN.price}원 · 명세 14,900원`, price === CFG.PLAN.price && price === 14900);
  ok(`요금제는 하나(member) — 화면 ${Object.keys(CFG.PLANS).join(",")}`, Object.keys(CFG.PLANS).join() === "member");
  const win = num(/const BURST_WINDOW_MIN = (\d+)/), max = num(/const BURST_MAX = (\d+)/);
  ok(`자동 수집 제한 — 서버 ${win}분 ${max}종목 · 화면 ${CFG.BURST_WINDOW_MIN}분 ${CFG.BURST_MAX}종목`,
     win === CFG.BURST_WINDOW_MIN && max === CFG.BURST_MAX && win === 60 && max === 60);
  ok("환불 기준 — 서버 7일 · 위약금 10%", num(/const REFUND_WINDOW_DAYS = (\d+)/) === 7 && num(/const REFUND_PENALTY_PCT = (\d+)/) === 10);
  ok("서버에 하루 열람 한도(DAILY_LIMIT · consumeDailyRead)가 없다", !/const DAILY_LIMIT\b|function consumeDailyRead\b/.test(SRC));
  ok("두 쪽 모두 요금제 변경(changePlan)이 없다",
     typeof H.fns.changePlan !== "function" && (await demoCall("changePlan", { plan: "pro" })).error?.code === "not-found");

  /* 옛 요금제 이름 — 두 쪽 모두 멤버십으로 읽는다 */
  for (const plan of ["basic", "pro"]) {
    const startMs = Date.parse("2026-11-02T05:00:00Z");
    clock.set(startMs + 2 * HOUR); seedBoth({ startMs, endMs: startMs + 30 * DAY, plan, amount: plan === "basic" ? 9900 : 14900 });
    const a = await H.call("getUsage"), b = await demoCall("getUsage");
    ok(`옛 요금제 '${plan}' — 두 쪽 모두 member · 한도 칸 없음 (서버 ${JSON.stringify(a.data)} · 시연 ${JSON.stringify(b.data)})`,
       a.data && b.data && a.data.plan === "member" && b.data.plan === "member" && JSON.stringify(Object.keys(a.data).sort()) === JSON.stringify(Object.keys(b.data).sort())
       && !("limit" in a.data) && !("limit" in b.data));
    const qa = (await H.call("refundPreview")).data, qb = (await demoCall("refundPreview")).data;
    ok(`옛 요금제 '${plan}' — 환불 기준은 이번 기간에 받은 돈(${qa.price}원)으로 같다`, qa.price === qb.price && qa.amount === qb.amount && qa.price === (plan === "basic" ? 9900 : 14900),
       `${qa.price}/${qa.amount} · ${qb.price}/${qb.amount}`);
  }
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
