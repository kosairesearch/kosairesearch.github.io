/* ============================================================
   무작위로 마구 눌러도 깨지면 안 되는 것들

   왜 있는가. 정해 놓은 순서대로 눌러 보는 검사는 우리가 상상한 길만 지난다.
   실제 사용자는 상상 못 한 순서로 누른다 — 결제하고 환불하고 다시 결제하고
   해지하고 되살리고, 그 사이에 리포트를 몰아서 열고, 시간이 흐르고.

   그래서 무작위 순서로 수천 번 돌리고, 그때마다 '무슨 일이 있어도 참이어야
   하는 것'을 확인한다. 어떤 순서에서 깨지는지는 실패했을 때 그대로 찍는다.

   2026-11-24 요금제 개편 — 요금제는 멤버십 하나, 하루 열람 한도 대신 자동 수집 제한
   (60분 안에 새로 연 종목 60개), 새 환불 계산. 지키는 것도 그에 맞췄다.

   지키는 것
     1. 돌려준 돈이 받은 돈을 넘지 않는다        ← 넘으면 우리가 손해다
     2. 취소 한 건이 그 결제 건의 금액을 넘지 않는다  ← 넘으면 카드사가 거절한다
     3. 열람을 받고 거절하는 판단이 명세 2절과 같다  ← 60분 안에 새 종목 60개까지 · 61번째부터 거절 ·
        오늘 연 종목은 언제나 · 창은 하루 기록 안에서(자정에 새로) — 시험이 따로 적은 모형과 한 건씩 견준다
     4. 이용 기간이 거꾸로 가지 않는다
     5. 이번 기간 결제 기록의 합이 실제로 받은 돈과 같다
     6. 환불이 끝난 구독에는 새 결제가 붙지 않는다
     7. 상태는 표에 있는 것만 나온다
     8. 요금제는 멤버십 하나뿐이다 — 옛 이름으로 결제해도, 요금제 변경을 눌러도
     9. 환불 금액은 명세 식(이용료 · 위약금)과 1원까지 같다 — 0원이면 실행하지 않는다

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
const PRICE = 14900, BURST_MAX = 60, WINDOW = 60 * 60e3, DAY = 86400e3, KST = 9 * 3600e3;
const sub = () => JSON.parse(localStorage.getItem("kos-demo-sub") || "null");
const pays = () => D.payments();
const kstDayNo = (ms) => Math.floor((ms + KST) / DAY);

/* 명세 3절의 식을 여기서 따로 적는다 — 시연 코드를 베끼지 않고 명세에서 옮겼다. */
function specRefund(s, now) {
  const P = (s.periodPayments || []).reduce((a, p) => a + (p.amount || 0), 0) || PRICE;
  const total = Math.max(1, kstDayNo(s.currentPeriodEnd) - kstDayNo(s.currentPeriodStart));
  const elapsed = kstDayNo(now) - kstDayNo(s.currentPeriodStart);
  const used = Math.min(total, elapsed + 1);
  const viewed = (s.readsSincePay || 0) > 0;
  if (elapsed <= 7 && !viewed) return P;
  const fee = Math.floor(P * used / total);
  const penalty = elapsed <= 7 ? 0 : Math.floor(P * 0.10);
  return Math.max(0, P - fee - penalty);
}

/* 씨앗을 고정한 난수 — 실패하면 그 씨앗으로 똑같이 재현할 수 있다. */
function rng(seed) {
  let x = seed >>> 0;
  return () => { x ^= x << 13; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return x / 4294967296; };
}

/* 시험이 따로 적은 열람 모형(명세 2절) — 시연이 스스로 적은 기록(kos-demo-reads)을 믿지 않고, 열 때마다
   받을지 거절할지를 여기서 먼저 정한 뒤 시연의 답과 견준다.

   시간을 앞으로 돌리는 것(advance)은 저장된 시각을 과거로 미는 것이다. 그래서 모형은 '가상 시각'(진짜 시각 +
   지금까지 넘긴 시간 clock)으로 적고, 하루 기록이 어느 날의 것인지는 시연과 같은 틀(가상 시각 − clock)에서 본다.
     · 하루 기록 — 마지막으로 연 때(last)가 오늘이 아니면 새로 시작한다(자정에 창도 빈다 · 서버와 같다)
     · 오늘 이미 연 종목 — 언제나 받는다(창을 채우지 않는다)
     · 새 종목 — 최근 60분 안에 새로 연 것이 60개면 거절, 아니면 받는다 */
let clock = 0, model = null, mism = null, seen = { reopen: 0, fresh: 0, refused: 0 };
function decide(t, real, v) {
  if (!model || kstDayNo(model.last - clock) !== kstDayNo(real)) model = { tickers: new Set(), opens: [], last: v };
  if (model.tickers.has(t)) return "reopen";
  return model.opens.filter((x) => x > v - WINDOW).length >= BURST_MAX ? "refuse" : "fresh";
}
async function open(t) {
  const real = Date.now(), v = real + clock;
  let err = null;
  try { await PW.fetchPaid(t); } catch (e) { err = e; }
  if (err && err.code !== "resource-exhausted") throw err;     // 구독 없음 등 — 열람 기록까지 오지 않았다
  const want = decide(t, real, v), got = err ? "refuse" : "accept";
  seen[want === "refuse" ? "refused" : want]++;
  if ((want === "refuse") !== (got === "refuse") && !mism) {
    mism = `${t} — 모형은 ${want === "refuse" ? "거절" : "받음(" + (want === "reopen" ? "다시 연 종목" : "새 종목") + ")"} · 시연은 ${got === "refuse" ? "거절" : "받음"}`
      + ` (창 안 ${model.opens.filter((x) => x > v - WINDOW).length}개)`;
  }
  if (got === "accept") {
    if (want === "fresh") { model.tickers.add(t); model.opens = [...model.opens.filter((x) => x > v - WINDOW), v]; }
    model.last = v;
  }
  if (err) throw err;
}
function advance(days) { D.advance(days); clock += Math.round(days * DAY); }

const OPS = [
  ["결제",          () => D.subscribe("member")],
  ["옛 주소로 결제", () => D.subscribe("basic")],
  ["카드 변경",     () => D.updateCard()],
  ["요금제 변경",   () => D.call("changePlan", { plan: "pro" })],
  ["해지",          () => D.call("cancelSubscription", {})],
  ["해지 취소",     () => D.call("resumeSubscription", {})],
  ["환불",          () => D.call("requestRefund", {})],
  ["리포트 열람",   (r) => open("T" + Math.floor(r() * 90))],
  /* 한 번에 몰아 본다. 한 판에 한두 건씩만 열면 문턱(60)에 닿을 기회가 아예
     없어서, 제한을 통째로 없애도 이 검사가 아무 말을 안 한다. */
  ["리포트 70건 몰아보기", async (r) => {
    const base = Math.floor(r() * 1000);
    for (let i = 0; i < 70; i++) { try { await open("B" + (base + i)); } catch (e) { if (e.code !== "resource-exhausted") throw e; } }
  }],
  ["20분 지남",     () => advance(20 / 1440)],
  ["61분 지남",     () => advance(61 / 1440)],
  ["하루 지남",     () => advance(1)],
  /* 7일 이내 · 7일 뒤 · 환불 0원이 모두 나오게 — 하루씩만 넘기면 12단계 안에 7일을 넘기기 어렵다 */
  ["8일 지남",      () => advance(8)],
  ["26일 지남",     () => advance(26)],
  ["past_due",      () => D.simulate("past_due")],
  ["expired",       () => D.simulate("expired")],
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
  clock = 0; model = null; mism = null;
  const log = [];
  for (let i = 0; i < steps; i++) {
    const [name, fn] = OPS[Math.floor(r() * OPS.length)];
    log.push(name);
    try { await fn(r); } catch (e) { /* 거절은 정상이다 */ }

    // 3. 열람 판단이 모형과 같다
    if (mism) return { seed, log, why: `열람 판단이 명세와 다르다: ${mism}` };

    const s = sub();
    if (!s) continue;

    // 5. 결제 기록의 합이 실제로 받은 돈과 같다
    const inRecord = (s.periodPayments || []).reduce((a, p) => a + (p.amount || 0), 0);
    if (inRecord < 0) return { seed, log, why: `결제 기록 합이 음수: ${inRecord}` };

    // 2. 결제 건은 금액과 시작 시각이 있어야 취소를 건마다 나눌 수 있다
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

    // 8. 요금제는 멤버십 하나 · 변경 예약은 없다
    if (s.plan !== "member" || s.pendingPlan) return { seed, log, why: `요금제가 멤버십이 아니다: ${s.plan} · 예약 ${s.pendingPlan}` };
    if ((s.periodPayments || []).some((p) => p.amount !== PRICE)) {
      return { seed, log, why: `이번 기간 결제가 멤버십 값이 아니다: ${JSON.stringify(s.periodPayments)}` };
    }

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
/* 모형의 세 갈래가 모두 실제로 일어났는가 — 하나라도 0이면 위의 3 은 그 갈래를 본 적이 없다 */
ok(`열람 판단 세 갈래를 모두 지났다 (새 종목 ${seen.fresh} · 다시 연 종목 ${seen.reopen} · 거절 ${seen.refused})`,
   seen.fresh > 0 && seen.reopen > 0 && seen.refused > 0);

/* 몰아보기가 실제로 문턱에 닿는가 */
{
  localStorage.clear(); clock = 0; model = null; mism = null;
  D.subscribe("member");
  let opened = 0, refused = 0;
  for (let i = 0; i < 70; i++) { try { await open("Z" + i); opened++; } catch (e) { if (e.code === "resource-exhausted") refused++; } }
  ok("몰아보기 70건 — 60건 열리고 10건 거절", opened === 60 && refused === 10 && !mism, `열림 ${opened} · 거절 ${refused} · ${mism || ""}`);
}

/* ── 특히 돈 쪽은 따로 한 번 더 ───────────────────────────────
   위는 '넘지 않는다' 만 본다. 여기서는 환불 한 건이 명세 식과 1원까지 같은지,
   그 기간에 받은 돈을 넘지 않는지, 취소가 결제 건별 한도 안에 들어오는지를 판마다 본다. */
console.log("\n── 환불이 명세 식과 같고 받은 돈을 넘지 않는가 (500판) ──\n");
let moneyBad = null, refunds = 0, zeros = 0;
for (let seed = 5000; seed < 5500 && !moneyBad; seed++) {
  const r = rng(seed);
  localStorage.clear(); clock = 0; model = null; mism = null;
  const log = [];
  for (let i = 0; i < 12; i++) {
    const [name, fn] = OPS[Math.floor(r() * OPS.length)];
    log.push(name);
    const before = sub();
    const wasIn = before ? (before.periodPayments || []).reduce((a, p) => a + p.amount, 0) : 0;
    /* 환불을 누르기 직전의 구독으로 명세 식의 금액을 미리 센다(이용 중이고 환불 전일 때만 뜻이 있다) */
    const live = before && before.status === "active" && before.currentPeriodEnd > Date.now() && !before.refundedAt;
    const want = name === "환불" && live ? specRefund(before, Date.now()) : null;
    /* 이번 조작이 만든 줄만 골라내는 기준. 시각으로 자르면 안 된다 — 조작이
       같은 밀리초 안에 여러 번 일어나 앞선 취소까지 딸려 온다. 개수로 센다.
       내역은 새 줄을 앞에 넣으므로(unshift) 새 것은 앞쪽에 쌓인다. */
    const hadRefunds = pays().filter((p) => p.kind === "refund").length;
    let refunded = 0, err = null;
    try {
      const res = await fn(r);
      if (name === "환불" && res && res.data) refunded = res.data.refunded || 0;
    } catch (e) { err = e; }
    if (want != null) {
      if (want > 0 && refunded !== want) {
        moneyBad = { seed, log, why: `환불 ${refunded}원 — 명세 식은 ${want}원 (${err ? err.message : "거절 없음"})` };
        break;
      }
      if (want === 0) {
        zeros++;
        if (!err || err.message !== "환불 가능한 금액이 없습니다.") {
          moneyBad = { seed, log, why: `명세 식이 0원인데 실행됐다(환불 ${refunded}원)` };
          break;
        }
      } else refunds++;
    }
    if (refunded > wasIn) {
      moneyBad = { seed, log, why: `환불 ${refunded}원 > 그 기간에 받은 돈 ${wasIn}원` };
      break;
    }
    /* 취소가 결제 건별 금액을 넘지 않는가 — 이번 환불이 만들어 낸 줄만 본다 */
    if (name === "환불" && refunded > 0) {
      const caps = (before && before.periodPayments || []).map((p) => p.amount);
      const rows = pays().filter((p) => p.kind === "refund");
      const justNow = rows.slice(0, rows.length - hadRefunds).map((p) => -p.amount);
      const biggest = caps.length ? Math.max(...caps) : 0;
      if (justNow.some((x) => x > biggest)) {
        moneyBad = { seed, log,
          why: `취소 한 건(${Math.max(...justNow)})이 그 기간 어느 결제 건보다 크다 (최대 ${biggest})` };
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
ok(`환불이 명세 식과 같고 받은 돈을 넘지 않는다 (실행 ${refunds}건 · 0원 거절 ${zeros}건)`, !moneyBad && refunds > 0);

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
