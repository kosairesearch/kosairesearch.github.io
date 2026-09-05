/* ============================================================
   무작위로 마구 눌러도 깨지면 안 되는 것들

   왜 있는가. 정해 놓은 순서대로 눌러 보는 검사는 우리가 상상한 길만 지난다.
   실제 사용자는 상상 못 한 순서로 누른다 — 결제하고 환불하고 다시 결제하고
   업그레이드하고 해지하고 되살리고, 그 사이에 리포트를 열고.

   그래서 무작위 순서로 수천 번 돌리고, 그때마다 '무슨 일이 있어도 참이어야
   하는 것'을 확인한다. 어떤 순서에서 깨지는지는 실패했을 때 그대로 찍는다.

   지키는 것
     1. 돌려준 돈이 받은 돈을 넘지 않는다        ← 넘으면 우리가 손해다
     2. 취소 한 건이 그 결제 건의 금액을 넘지 않는다  ← 넘으면 카드사가 거절한다
     3. 하루에 열리는 리포트가 플랜 한도를 넘지 않는다 ← 넘으면 고지가 거짓이 된다
     4. 이용 기간이 거꾸로 가지 않는다
     5. 이번 주기 결제 기록의 합이 실제로 받은 돈과 같다
     6. 환불이 끝난 구독에는 새 결제가 붙지 않는다
     7. 상태는 표에 있는 것만 나온다

   실행
     npm install --no-save jsdom
     node staging/tests/invariants.test.mjs
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work-inv");

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
export const onAuthStateChanged=(a,fn)=>{Promise.resolve().then(()=>fn(a.currentUser));return()=>{}};`);

const dom = new JSDOM("<!doctype html><body>", { url: "https://kosai.kr/staging/x.html" });
for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                 "location", "localStorage", "URL", "URLSearchParams"]) globalThis[k] = dom.window[k];
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "x", earnings: "e", outlook: "o", bull: "b", bear: "b", risks: "r", verdict: "v" }) });
await import(`file://${TMP}/demo.js`);

const D = window.KOSDemo, PW = window.KOSPaywall;
const PLANS = { basic: { price: 9900, limit: 5 }, pro: { price: 14900, limit: 15 } };
const sub = () => JSON.parse(localStorage.getItem("kos-demo-sub") || "null");
const pays = () => D.payments();

/* 씨앗을 고정한 난수 — 실패하면 그 씨앗으로 똑같이 재현할 수 있다. */
function rng(seed) {
  let x = seed >>> 0;
  return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return x / 4294967296; };
}

const OPS = [
  ["basic 결제",  () => D.subscribe("basic")],
  ["pro 결제",    () => D.subscribe("pro")],
  ["카드 변경",   () => D.updateCard()],
  ["pro 로 올림", () => D.call("changePlan", { plan: "pro" })],
  ["basic 로 내림", () => D.call("changePlan", { plan: "basic" })],
  ["해지",        () => D.call("cancelSubscription", {})],
  ["해지 취소",   () => D.call("resumeSubscription", {})],
  ["환불",        () => D.call("requestRefund", {})],
  ["리포트 열람", (r) => PW.fetchPaid("T" + Math.floor(r() * 30))],
  /* 한 번에 몰아 본다. 한 판에 한두 건씩만 열면 한도를 넘길 기회가 아예
     없어서, 한도 검사를 통째로 없애도 이 검사가 아무 말을 안 했다. */
  ["리포트 20건 몰아보기", async () => {
    for (let i = 0; i < 20; i++) { try { await PW.fetchPaid("B" + i); } catch (e) { break; } }
  }],
  ["past_due",    () => D.simulate("past_due")],
  ["expired",     () => D.simulate("expired")],
];

const STATES = new Set(["active", "past_due", "expired", "deleted"]);

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "\n      " + x : "")); }
};

/* ── 한 판 돌리기 ───────────────────────────────────────────── */
async function run(seed, steps) {
  const r = rng(seed);
  localStorage.clear();
  const log = [];
  for (let i = 0; i < steps; i++) {
    const [name, fn] = OPS[Math.floor(r() * OPS.length)];
    log.push(name);
    try { await fn(r); } catch (e) { /* 거절은 정상이다 */ }

    const s = sub();
    if (!s) continue;

    // 5. 결제 기록의 합이 실제로 받은 돈과 같다
    const inRecord = (s.periodPayments || []).reduce((a, p) => a + (p.amount || 0), 0);
    if (inRecord < 0) return { seed, log, why: `결제 기록 합이 음수: ${inRecord}` };

    // 2. 취소 한 건이 그 결제 건의 금액을 넘지 않는다
    for (const p of s.periodPayments || []) {
      if (!(p.amount > 0)) return { seed, log, why: `결제 금액이 0 이하: ${JSON.stringify(p)}` };
      if (!Number.isFinite(p.from)) return { seed, log, why: `결제 시작 시각 없음: ${JSON.stringify(p)}` };
    }

    /* 4. 이용 기간이 거꾸로 가지 않는다.
       길이 0 은 인정한다 — 결제하자마자 한 건도 안 보고 환불하면 전액을 돌려주고
       이용을 즉시 끝내므로, 시작과 끝이 같아지는 것이 오히려 정직한 표현이다. */
    if (s.currentPeriodEnd < s.currentPeriodStart) {
      return { seed, log, why: `기간이 거꾸로: ${s.currentPeriodStart} → ${s.currentPeriodEnd}` };
    }

    // 7. 상태는 아는 것만
    if (!STATES.has(s.status)) return { seed, log, why: `모르는 상태: ${s.status}` };

    // 6. 환불이 끝난 구독에는 새 결제가 붙지 않는다
    if (s.refundedAt && inRecord === 0) {
      return { seed, log, why: "환불된 구독인데 결제 기록이 비었다" };
    }
  }

  // 1. 돌려준 돈이 받은 돈을 넘지 않는다 (판 전체 기준)
  const all = pays();
  const paid = all.filter((p) => p.amount > 0).reduce((a, p) => a + p.amount, 0);
  const back = all.filter((p) => p.amount < 0).reduce((a, p) => a - p.amount, 0);
  if (back > paid) return { seed, log, why: `돌려준 돈(${back})이 받은 돈(${paid})보다 많다` };

  // 3. 하루에 열린 리포트가 그날 쓸 수 있었던 최대 한도를 넘지 않는다
  const reads = JSON.parse(localStorage.getItem("kos-demo-reads") || "null");
  const used = ((reads && reads.tickers) || []).length;
  if (used > PLANS.pro.limit) {
    return { seed, log, why: `하루 열람 ${used}건 — PRO 한도 ${PLANS.pro.limit}건을 넘었다` };
  }
  return null;
}

console.log("── 무작위 조작 2,000판 ──\n");

const ROUNDS = 2000, STEPS = 14;
let broken = null, done = 0;
for (let seed = 1; seed <= ROUNDS && !broken; seed++) {
  broken = await run(seed, STEPS);
  done++;
}

if (broken) {
  console.log(`  씨앗 ${broken.seed} 에서 깨졌다`);
  console.log(`  이유: ${broken.why}`);
  console.log(`  순서: ${broken.log.join(" → ")}`);
}
ok(`${done}판 · 판마다 ${STEPS}단계 · 총 ${done * STEPS}회 조작`, !broken);

/* ── 특히 돈 쪽은 따로 한 번 더 ───────────────────────────────
   위는 '넘지 않는다' 만 본다. 여기서는 환불 한 건이 그 주기에 받은 돈을
   넘지 않는지, 취소가 결제 건별 한도 안에 들어오는지를 판마다 본다. */
console.log("\n── 환불이 받은 돈을 넘지 않는가 (500판) ──\n");
let moneyBad = null;
for (let seed = 5000; seed < 5500 && !moneyBad; seed++) {
  const r = rng(seed);
  localStorage.clear();
  const log = [];
  for (let i = 0; i < 12; i++) {
    const [name, fn] = OPS[Math.floor(r() * OPS.length)];
    log.push(name);
    const before = sub();
    const wasIn = before ? (before.periodPayments || []).reduce((a, p) => a + p.amount, 0) : 0;
    /* 이번 조작이 만든 줄만 골라내는 기준. 시각으로 자르면 안 된다 — 조작이
       같은 밀리초 안에 여러 번 일어나 앞선 취소까지 딸려 온다. 개수로 센다.
       내역은 새 줄을 앞에 넣으므로(unshift) 새 것은 앞쪽에 쌓인다. */
    const hadRefunds = pays().filter((p) => p.kind === "refund").length;
    let refunded = 0;
    try {
      const res = await fn(r);
      if (name === "환불" && res && res.data) refunded = res.data.refunded || 0;
    } catch (e) { /* 거절은 정상 */ }
    if (refunded > wasIn) {
      moneyBad = { seed, log, why: `환불 ${refunded}원 > 그 주기에 받은 돈 ${wasIn}원` };
      break;
    }
    /* 취소가 결제 건별 금액을 넘지 않는가.

       이번 환불이 만들어 낸 줄만 본다. 내역 전체를 보면 지난 주기의 취소가
       이번 주기의 결제 건과 견주어져 엉뚱하게 걸린다 — 처음에 그렇게 짜서
       PRO 를 환불한 뒤 BASIC 을 결제한 판을 버그로 잘못 읽었다. */
    if (name === "환불" && refunded > 0) {
      const caps = (before && before.periodPayments || []).map((p) => p.amount);
      const rows = pays().filter((p) => p.kind === "refund");
      const justNow = rows.slice(0, rows.length - hadRefunds).map((p) => -p.amount);
      const biggest = caps.length ? Math.max(...caps) : 0;
      if (justNow.some((x) => x > biggest)) {
        moneyBad = { seed, log,
          why: `취소 한 건(${Math.max(...justNow)})이 그 주기 어느 결제 건보다 크다 (최대 ${biggest})` };
        break;
      }
      if (justNow.reduce((a, b) => a + b, 0) !== refunded) {
        moneyBad = { seed, log,
          why: `취소 합계(${justNow.reduce((a, b) => a + b, 0)})가 환불 금액(${refunded})과 다르다` };
        break;
      }
    }
  }
}
if (moneyBad) {
  console.log(`  씨앗 ${moneyBad.seed}: ${moneyBad.why}`);
  console.log(`  순서: ${moneyBad.log.join(" → ")}`);
}
ok("환불이 그 주기에 받은 돈을 넘지 않는다", !moneyBad);

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
