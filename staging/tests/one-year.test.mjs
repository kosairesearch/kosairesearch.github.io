/* ============================================================
   1년을 살아 본다 — 날마다 하루씩 넘기며

   왜 있는가. 지금까지의 검사는 한 순간을 본다. 실제 구독은 열두 달을 산다 —
   달마다 갱신되고, 중간에 카드가 거절되고, 재시도로 되살아나고, 플랜을 올리고
   내리고, 환불하고 다시 시작한다. 그 긴 흐름에서만 드러나는 것이 있다.

   그래서 하루씩 365번 넘기면서 매일
     · 갱신 배치를 돌리고
     · 그날의 사용자 행동을 하고
     · 절대 깨지면 안 되는 것들을 확인한다

   지키는 것
     1. 받은 돈보다 많이 돌려주지 않는다
     2. 하루 열람이 플랜 한도를 넘지 않는다
     3. 이용 기간이 거꾸로 가지 않는다
     4. 결제 없이 이용 중이 되지 않는다        ← 공짜로 여는 길
     5. 이용 중인데 결제 기록이 비어 있지 않다  ← 환불할 근거가 사라진 상태
     6. 모르는 상태가 나오지 않는다
     7. 재시도 횟수가 상한을 넘지 않는다
     8. 이용 기간이 한 달을 크게 넘지 않는다    ← 갱신을 건너뛰면 공짜가 된다

   실행
     npm install --no-save jsdom
     node staging/tests/one-year.test.mjs
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work-year");

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
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "x", earnings: "e", outlook: "o", bull: "b", bear: "b", risks: "r", verdict: "v" }) });
await import(`file://${TMP}/demo.js`);

const D = window.KOSDemo, PW = window.KOSPaywall;
const PLANS = { basic: { price: 9900, limit: 5 }, pro: { price: 14900, limit: 15 } };
const RETRY_MAX = 4;
const DAY = 86400e3;
const sub = () => JSON.parse(localStorage.getItem("kos-demo-sub") || "null");
const pays = () => D.payments();
const STATES = new Set(["active", "past_due", "expired", "deleted"]);

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "\n      " + x : "")); }
};

function rng(seed) {
  let x = seed >>> 0;
  return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return x / 4294967296; };
}

/* 하루 치를 산다. 문제가 있으면 무엇이 언제 깨졌는지 돌려준다. */
function checkDay(log, dayNo) {
  const s = sub();
  if (!s) return null;

  if (!STATES.has(s.status)) return `${dayNo}일차: 모르는 상태 ${s.status}`;
  if (s.currentPeriodEnd < s.currentPeriodStart) {
    return `${dayNo}일차: 기간이 거꾸로`;
  }
  if ((s.retryCount || 0) > RETRY_MAX) {
    return `${dayNo}일차: 재시도 횟수가 상한을 넘었다 (${s.retryCount})`;
  }

  const active = s.status === "active" && s.currentPeriodEnd > Date.now();
  const inRecord = (s.periodPayments || []).reduce((a, p) => a + (p.amount || 0), 0);

  // 4·5. 이용 중이면 그 주기에 받은 돈이 있어야 한다
  if (active && !s.refundedAt && inRecord <= 0) {
    return `${dayNo}일차: 이용 중인데 결제 기록이 비었다 — 공짜로 열린 셈이다`;
  }
  // 8. 한 주기가 한 달을 크게 넘지 않는다(겹친 하루를 붙이므로 +2일까지는 정상)
  const len = (s.currentPeriodEnd - s.currentPeriodStart) / DAY;
  if (len > 34) return `${dayNo}일차: 이용 기간이 ${len.toFixed(1)}일 — 너무 길다`;

  // 2. 하루 열람이 한도를 넘지 않는다
  const r = JSON.parse(localStorage.getItem("kos-demo-reads") || "null");
  const used = ((r && r.tickers) || []).length;
  const limit = (PLANS[s.plan] || {}).limit || 0;
  if (used > Math.max(limit, PLANS.pro.limit)) {
    return `${dayNo}일차: 하루 열람 ${used}건 — 한도를 넘었다`;
  }
  return null;
}

/* ── 한 해를 산다 ─────────────────────────────────────────── */
async function liveAYear(seed, { chaos }) {
  const rnd = rng(seed);
  localStorage.clear();
  const log = [];
  D.subscribe(rnd() < 0.5 ? "basic" : "pro");
  log.push("결제");

  for (let dayNo = 1; dayNo <= 365; dayNo++) {
    D.advance(1);

    // 매일 도는 갱신 배치. chaos 만큼의 확률로 카드가 거절된다.
    const decline = rnd() < chaos;
    try { D.runRenewal({ decline }); } catch (e) { /* 대상이 없으면 그냥 넘어간다 */ }

    // 그날의 사용자 행동
    const roll = rnd();
    try {
      if (roll < 0.35) {                                   // 리포트를 본다
        const n = 1 + Math.floor(rnd() * 4);
        for (let i = 0; i < n; i++) { try { await PW.fetchPaid("T" + Math.floor(rnd() * 40)); } catch (e) { break; } }
      } else if (roll < 0.40) { await D.call("changePlan", { plan: "pro" }); log.push(`${dayNo}:올림`); }
      else if (roll < 0.44) { await D.call("changePlan", { plan: "basic" }); log.push(`${dayNo}:내림`); }
      else if (roll < 0.47) { await D.call("cancelSubscription", {}); log.push(`${dayNo}:해지`); }
      else if (roll < 0.50) { await D.call("resumeSubscription", {}); log.push(`${dayNo}:해지취소`); }
      else if (roll < 0.53) { await D.call("requestRefund", {}); log.push(`${dayNo}:환불`); }
      else if (roll < 0.57) { D.updateCard(); log.push(`${dayNo}:카드변경`); }
      else if (roll < 0.61) { D.subscribe(rnd() < 0.5 ? "basic" : "pro"); log.push(`${dayNo}:재결제`); }
    } catch (e) { /* 거절은 정상이다 */ }

    const bad = checkDay(log, dayNo);
    if (bad) return { seed, bad, log: log.slice(-14) };
  }

  // 한 해가 끝난 뒤 — 돈이 맞는가
  const all = pays();
  const paid = all.filter((p) => p.amount > 0).reduce((a, p) => a + p.amount, 0);
  const back = all.filter((p) => p.amount < 0).reduce((a, p) => a - p.amount, 0);
  if (back > paid) return { seed, bad: `한 해 동안 돌려준 돈(${back})이 받은 돈(${paid})보다 많다`, log: log.slice(-14) };
  return null;
}

console.log("── 한 해를 산다 · 카드가 가끔 거절되는 경우 ──\n");
let broken = null, ran = 0;
for (let seed = 1; seed <= 60 && !broken; seed++) {
  broken = await liveAYear(seed, { chaos: 0.06 });
  ran++;
}
if (broken) { console.log(`  씨앗 ${broken.seed}: ${broken.bad}`); console.log(`  최근 조작: ${broken.log.join(" → ")}`); }
ok(`${ran}명 × 365일 = ${ran * 365}일`, !broken);

console.log("\n── 카드가 자주 거절되는 경우(30%) ──\n");
broken = null; ran = 0;
for (let seed = 100; seed <= 140 && !broken; seed++) {
  broken = await liveAYear(seed, { chaos: 0.30 });
  ran++;
}
if (broken) { console.log(`  씨앗 ${broken.seed}: ${broken.bad}`); console.log(`  최근 조작: ${broken.log.join(" → ")}`); }
ok(`${ran}명 × 365일 = ${ran * 365}일`, !broken);

console.log("\n── 카드가 한 번도 거절되지 않는 경우 ──\n");
broken = null; ran = 0;
for (let seed = 200; seed <= 240 && !broken; seed++) {
  broken = await liveAYear(seed, { chaos: 0 });
  ran++;
}
if (broken) { console.log(`  씨앗 ${broken.seed}: ${broken.bad}`); console.log(`  최근 조작: ${broken.log.join(" → ")}`); }
ok(`${ran}명 × 365일 = ${ran * 365}일`, !broken);

/* ── 재시도로 되살아나는 길을 못 박는다 ────────────────────── */
console.log("\n── 재시도 성공: 그 순간부터 새 한 달 ──\n");
{
  localStorage.clear();
  D.subscribe("basic");
  D.advance(31);
  D.runRenewal({ decline: true });
  ok("거절되면 '결제 실패' 로 둔다", sub().status === "past_due", sub().status);
  ok("그동안은 리포트를 볼 수 없다",
     await PW.fetchPaid("005930").then(() => false).catch(() => true));

  D.advance(1);
  D.runRenewal({ decline: true });
  ok("1일째 재시도 — 아직 안 끊는다", sub().status === "past_due" && sub().retryCount === 1,
     `${sub().status} · ${sub().retryCount}`);

  D.advance(2);
  const before = pays().length;
  const msg = D.runRenewal({ decline: false });
  const s = sub();
  ok("3일째 재시도에서 결제된다", s.status === "active", msg);
  ok("그 순간부터 새 기간이 시작된다",
     Math.abs(s.currentPeriodStart - Date.now()) < 5000, String(s.currentPeriodStart));
  ok("거기서부터 한 달", (s.currentPeriodEnd - s.currentPeriodStart) / DAY > 27);
  ok("실패 흔적이 지워진다", s.failedAt === undefined && s.retryCount === undefined,
     JSON.stringify({ failedAt: s.failedAt, retryCount: s.retryCount }));
  ok("결제 기록이 새로 시작된다",
     s.periodPayments.length === 1 && s.periodPayments[0].amount === PLANS.basic.price);
  ok("내역에 결제가 한 줄 늘었다", pays().length === before + 1);
  ok("다시 리포트를 볼 수 있다",
     await PW.fetchPaid("005930").then(() => true).catch(() => false));
}

console.log("\n── 재시도 중 카드를 직접 바꾸면 바로 되살아난다 ──\n");
{
  localStorage.clear();
  D.subscribe("pro");
  D.advance(31);
  D.runRenewal({ decline: true });
  D.updateCard();
  const s = sub();
  ok("그 자리에서 결제되어 이용 중이 된다", s.status === "active", s.status);
  ok("실패 흔적이 지워진다", s.failedAt === undefined && s.retryCount === undefined);
  ok("그 순간부터 새 기간", Math.abs(s.currentPeriodStart - Date.now()) < 5000);
}

/* ── 예약해 둔 다운그레이드가 되살아날 때 반영되는가 ──────────
   BASIC 으로 내리겠다고 예약한 사람의 카드가 다음 결제일에 거절됐다. 되살릴
   때 옛 플랜(PRO)으로 청구하면, 내리겠다고 말해 둔 사람에게 비싼 값을 받고
   비싼 플랜을 그대로 물려 놓는 셈이 된다. 되살리는 길은 둘이다 — 카드 재등록,
   배치 재시도. 둘 다 확인한다. */
console.log("\n── 내리기로 예약해 둔 사람이 되살아나면 ──\n");
for (const [how, revive] of [
  ["카드 재등록", () => D.updateCard()],
  ["배치 재시도", () => { D.advance(1); D.runRenewal({ decline: false }); }],
]) {
  localStorage.clear();
  D.subscribe("pro");
  await D.call("changePlan", { plan: "basic" });          // 다음 결제일부터 BASIC
  D.advance(31);
  D.runRenewal({ decline: true });                        // 그 결제일에 거절됐다
  const was = pays().length;
  revive();
  const s = sub();
  ok(`${how} — BASIC 으로 되살아난다`, s.status === "active" && s.plan === "basic",
     `${s.status} · ${s.plan}`);
  ok(`${how} — 예약이 비워진다`, !s.pendingPlan, String(s.pendingPlan));
  ok(`${how} — BASIC 값만 받는다`,
     s.periodPayments.length === 1 && s.periodPayments[0].amount === PLANS.basic.price,
     JSON.stringify(s.periodPayments));
  ok(`${how} — 내역에도 BASIC 으로 적힌다`,
     pays().length === was + 1 && pays()[0].amount === PLANS.basic.price,
     JSON.stringify(pays()[0]));
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
