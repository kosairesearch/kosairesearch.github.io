/* ============================================================
   서버와 미리보기가 같은 금액을 내는가 — 날짜를 전부 돌려서

   왜 있는가. 환불 계산이 두 벌로 짜여 있다. 서버(functions/index.js)와
   미리보기(staging/demo-backend.js). 두 벌이면 갈라진다 — 실제로 갈라졌었고,
   그때 미리보기 주석에는 "서버와 같다" 고 적혀 있었다. 주석이 그 사실을 덮고
   있었다.

   눈으로 견주는 것으로는 부족하다. 한 해치 날짜와 여러 상황을 전부 돌려
   금액을 1원 단위로 맞춰 본다.

   미리보기 코드를 진짜로 불러다 쓰고, 서버 쪽은 index.js 에서 그대로 옮겨
   적는다. 옮겨 적은 것이 원본과 같은지는 functions/tests 가 따로 본다.

   실행
     npm install --no-save jsdom
     node staging/tests/two-sides.test.mjs
   ============================================================ */
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
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "x", earnings: "e", outlook: "o", bull: "b", bear: "b", risks: "r", verdict: "v" }) });
await import(`file://${TMP}/demo.js`);
const D = window.KOSDemo, PW = window.KOSPaywall;

const DAY = 86400000;
const PRICE = { basic: 9900, pro: 14900 };
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600000) / DAY);

/* ── functions/index.js 에서 그대로 옮긴 것 ────────────────── */
function unusedOf(sub, startMs, endMs, usedUntilDay) {
  const endDay = kstDayNo(endMs);
  const list = ((sub && sub.periodPayments) || []).length
    ? sub.periodPayments
    : [{ amount: PRICE[sub.plan] || 0, from: startMs }];
  return list.reduce((sum, p) => {
    const fromDay = kstDayNo(p.from || startMs);
    const win = Math.max(1, endDay - fromDay);
    const left = Math.max(0, endDay - Math.max(fromDay, usedUntilDay));
    return sum + (p.amount || 0) * Math.min(1, left / win);
  }, 0);
}
const paidThisPeriod = (sub) =>
  ((sub && sub.periodPayments) || []).reduce((a, e) => a + (e.amount || 0), 0);

/* 서버 refundQuote 의 금액 부분. */
function serverQuote(sub, nowMs, { opened, openedToday }) {
  const startMs = sub.currentPeriodStart, endMs = sub.currentPeriodEnd;
  const total = Math.max(1, Math.round((endMs - startMs) / DAY));
  const price = paidThisPeriod(sub) || PRICE[sub.plan] || 0;
  const elapsed = Math.max(0, kstDayNo(nowMs) - kstDayNo(startMs));
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));
  if (!opened && used <= 7) return { amount: price, why: "withdraw" };
  const unused = unusedOf(sub, startMs, endMs, kstDayNo(startMs) + used);
  return { amount: Math.floor(unused * 0.9), why: opened ? "used" : "left" };
}

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};

/* 미리보기의 refundAmount 를 실제로 부른다 — 구독을 심어 두고 환불 견적을 받는다. */
function demoQuote(sub) {
  localStorage.clear();
  localStorage.setItem("kos-demo-sub", JSON.stringify(sub));
  if (sub._readsToday) {
    localStorage.setItem("kos-demo-reads", JSON.stringify({
      day: new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10),
      tickers: Array.from({ length: sub._readsToday }, (_, i) => "T" + i),
    }));
  }
  return D.call("refundPreview", {}).then((r) => r.data.amount);
}

console.log("── 한 해치 날짜를 전부 돌려 두 쪽을 맞춘다 ──\n");

/* 하루 단위로 오늘을 옮길 수는 없으므로(Date.now 를 못 바꾼다) 반대로 한다 —
   결제 시점을 과거로 옮겨 '며칠째' 를 만든다. */
const NOW = Date.now();
let mismatch = null, cases = 0;

for (const plan of ["basic", "pro"]) {
  for (let monthLen of [28, 29, 30, 31]) {
      // 마지막 날은 기간이 이미 끝나 견적을 낼 수 없다(활성이 아니다)
    for (let dayNo = 0; dayNo < monthLen && !mismatch; dayNo++) {
      for (const reads of [0, 3]) {
        for (const everOpened of [false, true]) {
          const start = NOW - dayNo * DAY;
          const end = start + monthLen * DAY;
          const sub = {
            status: "active", plan,
            currentPeriodStart: start, currentPeriodEnd: end,
            cancelAtPeriodEnd: false, pendingPlan: null,
            periodPayments: [{ key: "p1", amount: PRICE[plan], from: start }],
            readsSincePay: everOpened ? 5 : 0,
            _readsToday: reads,
          };
          const mine = serverQuote(sub, NOW,
            { opened: everOpened, openedToday: reads > 0 });
          const theirs = await demoQuote(sub);
          cases++;
          if (mine.amount !== theirs) {
            mismatch = { plan, monthLen, dayNo, reads, everOpened,
                         server: mine.amount, demo: theirs };
            break;
          }
        }
        if (mismatch) break;
      }
    }
  }
}
if (mismatch) console.log("  " + JSON.stringify(mismatch));
ok(`월 구독만 있을 때 — ${cases}가지 전부 1원까지 같다`, !mismatch);

console.log("\n── 업그레이드 차액까지 낀 경우 ──\n");
mismatch = null; cases = 0;
for (let monthLen of [28, 30, 31]) {
  for (let dayNo = 1; dayNo < monthLen && !mismatch; dayNo++) {
    for (let upAt = 0; upAt <= dayNo; upAt++) {
      for (const reads of [0, 2]) {
        const start = NOW - dayNo * DAY;
        const end = start + monthLen * DAY;
        const upFrom = NOW - (dayNo - upAt) * DAY;
        const leftAtUp = Math.max(0, (end - upFrom) / DAY);
        const diff = Math.floor((PRICE.pro - PRICE.basic) * (leftAtUp / monthLen));
        if (diff <= 0) continue;
        const sub = {
          status: "active", plan: "pro",
          currentPeriodStart: start, currentPeriodEnd: end,
          cancelAtPeriodEnd: false, pendingPlan: null,
          periodPayments: [
            { key: "p1", amount: PRICE.basic, from: start },
            { key: "p2", amount: diff, from: upFrom },
          ],
          readsSincePay: 4,
          _readsToday: reads,
        };
        const mine = serverQuote(sub, NOW, { opened: true, openedToday: reads > 0 });
        const theirs = await demoQuote(sub);
        cases++;
        if (mine.amount !== theirs) {
          mismatch = { monthLen, dayNo, upAt, reads, server: mine.amount, demo: theirs };
          break;
        }
      }
      if (mismatch) break;
    }
  }
}
if (mismatch) console.log("  " + JSON.stringify(mismatch));
ok(`결제가 둘일 때 — ${cases}가지 전부 1원까지 같다`, !mismatch);

console.log("\n── 업그레이드 차액도 두 쪽이 같은가 ──\n");
mismatch = null; cases = 0;
for (let monthLen of [28, 30, 31]) {
  for (let dayNo = 0; dayNo < monthLen && !mismatch; dayNo++) {
    localStorage.clear();
    const start = NOW - dayNo * DAY, end = start + monthLen * DAY;
    localStorage.setItem("kos-demo-sub", JSON.stringify({
      status: "active", plan: "basic",
      currentPeriodStart: start, currentPeriodEnd: end,
      cancelAtPeriodEnd: false, pendingPlan: null,
      periodPayments: [{ key: "p1", amount: PRICE.basic, from: start }],
      readsSincePay: 0,
    }));
    // 서버 changePlan 의 차액 계산
    const total = Math.max(1, (end - start) / DAY);
    const left = Math.max(0, (end - Date.now()) / DAY);
    let mine = Math.floor((PRICE.pro - PRICE.basic) * (left / total));
    if (mine < 100) mine = 0;                        // MIN_CHARGE
    const theirs = (await D.call("changePlan", { plan: "pro" })).data.charged;
    cases++;
    if (mine !== theirs) mismatch = { monthLen, dayNo, server: mine, demo: theirs };
  }
}
if (mismatch) console.log("  " + JSON.stringify(mismatch));
ok(`업그레이드 차액 — ${cases}가지 전부 1원까지 같다`, !mismatch);

console.log("\n── 하루 한도와 플랜 값이 두 쪽에서 같은가 ──\n");
{
  const cfg = JSON.parse(readFileSync(STAGING + "/payment-config.js", "utf8")
    .match(/PLANS = (\{[\s\S]*?\n\});/)[1]
    .replace(/(\w+):/g, '"$1":').replace(/,(\s*[}\]])/g, "$1"));
  const srv = readFileSync(join(ROOT, "functions", "index.js"), "utf8");
  const price = JSON.parse((srv.match(/const PRICE = (\{[^}]+\})/) || [])[1]
    .replace(/(\w+):/g, '"$1":'));
  const limit = JSON.parse((srv.match(/const DAILY_LIMIT = (\{[^}]+\})/) || [])[1]
    .replace(/(\w+):/g, '"$1":'));
  for (const p of ["basic", "pro"]) {
    ok(`${p.toUpperCase()} 요금이 같다 (${cfg[p].price}원)`, cfg[p].price === price[p],
       `화면 ${cfg[p].price} · 서버 ${price[p]}`);
    ok(`${p.toUpperCase()} 하루 한도가 같다 (${cfg[p].limit}건)`, cfg[p].limit === limit[p],
       `화면 ${cfg[p].limit} · 서버 ${limit[p]}`);
  }
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
