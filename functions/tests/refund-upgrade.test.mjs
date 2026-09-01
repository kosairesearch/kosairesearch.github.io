/* ============================================================
   업그레이드한 뒤의 환불 — 결제가 둘인 주기를 어떻게 세는가

   왜 있는가. 한 주기에 결제가 둘일 수 있다(월 구독 + 업그레이드 차액).
   환불이 그걸 한 덩어리로 보고 있었고, 그래서 셋이 한꺼번에 틀렸다.

     ① 기준 금액이 정가였다
        price = PRICE[sub.plan] — BASIC 9,900원을 내고 PRO 로 올린 사람에게
        14,900원을 기준으로 환불액을 냈다. 받은 적 없는 돈이다.
        미리보기는 '실제로 받은 돈'을 쓰고 있어서, 두 쪽이 다른 답을 냈다.

     ② 취소가 결제 건 하나만 가리켰다
        toss(/payments/{lastPaymentKey}/cancel, {cancelAmount: 전액})
        lastPaymentKey 는 월 구독 건이라 차액은 안 들어 있다. 그 건의 금액보다
        큰 취소는 카드사가 거절한다 — 업그레이드한 사람은 환불이 아예 안 됐다.

     ③ 차액에서도 지나간 날을 뺐다
        차액은 '업그레이드한 날부터 주기 끝까지' 를 산 돈이다. 그 앞의 날들에는
        옛 플랜을 썼지 새 플랜을 쓴 적이 없다. 787원을 덜 돌려줬다.

   서버는 여기서 돌릴 수 없다(파이어베이스가 필요하다). 그래서 refundQuote 가
   쓰는 계산만 그대로 옮겨 놓고 본다 — 옮겨 적은 것이 원본과 어긋나면 그게
   화면과 실제가 갈라지는 자리다.

   실행
     node functions/tests/refund-upgrade.test.mjs
   ============================================================ */

const DAY = 86400000;
const PRICE = { basic: 9900, pro: 14900 };   // functions/index.js 와 같아야 한다
const REFUND_FEE_RATE = 0.10;
const FREE_WITHDRAW_DAYS = 7;
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600000) / DAY);

/* ── functions/index.js 에서 그대로 옮긴 것 ────────────────── */
const paidThisPeriod = (sub) =>
  ((sub && sub.periodPayments) || []).reduce((a, e) => a + (e.amount || 0), 0);

function refundSources(sub) {
  const list = ((sub && sub.periodPayments) || [])
    .filter((e) => e && e.key && e.amount > 0);
  if (list.length) return list.slice().reverse();
  return sub && sub.lastPaymentKey
    ? [{ key: sub.lastPaymentKey, amount: PRICE[sub.plan] || 0 }] : [];
}

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

/* refundQuote 의 금액 부분. 열람 여부는 인자로 받는다(DB 조회 자리). */
function quote(sub, nowMs, { opened, openedToday }) {
  const startMs = sub.currentPeriodStart, endMs = sub.currentPeriodEnd;
  const total = Math.max(1, Math.round((endMs - startMs) / DAY));
  const price = paidThisPeriod(sub) || PRICE[sub.plan] || 0;
  const elapsed = Math.max(0, kstDayNo(nowMs) - kstDayNo(startMs));
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));
  if (!opened && used <= FREE_WITHDRAW_DAYS) return { amount: price, why: "withdraw" };
  const unused = unusedOf(sub, startMs, endMs, kstDayNo(startMs) + used);
  return { amount: Math.floor(unused * (1 - REFUND_FEE_RATE)), why: opened ? "used" : "left" };
}

/* doRefund 가 카드사에 내보내는 취소들. 실제로 나가는 모양 그대로 만든다. */
function cancels(sub, amount) {
  const out = [];
  let rest = amount;
  for (const src of refundSources(sub)) {
    if (rest <= 0) break;
    const take = Math.min(rest, src.amount);
    if (take > 0) { out.push({ key: src.key, amount: take }); rest -= take; }
  }
  return { out, rest };
}

/* ── 도구 ──────────────────────────────────────────────────── */
let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};
const won = (n) => Math.round(n).toLocaleString("ko-KR") + "원";

/* BASIC 을 31일짜리로 사고, 7일 뒤 PRO 로 올린 사람 */
const NOW = Date.parse("2026-09-02T05:00:00Z");
const START = NOW - 7 * DAY;
const END = START + 31 * DAY;
const DIFF = Math.floor((PRICE.pro - PRICE.basic) * (24 / 31));   // 업그레이드 차액

const upgraded = {
  plan: "pro", currentPeriodStart: START, currentPeriodEnd: END,
  lastPaymentKey: "pay_base",
  periodPayments: [
    { key: "pay_base", amount: PRICE.basic, from: START },
    { key: "pay_up", amount: DIFF, from: NOW },
  ],
};

console.log("── 기준 금액 ──");
{
  ok("정가가 아니라 실제로 받은 돈을 쓴다",
     paidThisPeriod(upgraded) === PRICE.basic + DIFF,
     won(paidThisPeriod(upgraded)));
  ok("그 금액은 PRO 정가와 다르다", paidThisPeriod(upgraded) !== PRICE.pro,
     `${won(paidThisPeriod(upgraded))} ≠ ${won(PRICE.pro)}`);
}

console.log("\n── 남은 돈을 건마다 제 기간으로 센다 ──");
{
  const q = quote(upgraded, NOW, { opened: true, openedToday: false });
  //  월 구독 9,900원 — 31일을 샀고 7일 썼다      → 24/31
  //  차액   DIFF     — 오늘부터 24일을 샀고 안 썼다 → 24/24 (전액)
  const want = Math.floor((PRICE.basic * 24 / 31 + DIFF) * 0.9);
  ok("건마다 세어 돌려준다", q.amount === want, `${won(q.amount)} (기대 ${won(want)})`);

  const lumped = Math.floor((PRICE.basic + DIFF) * 24 / 31 * 0.9);
  ok("한 덩어리로 세던 옛 금액이 아니다", q.amount !== lumped,
     `옛 계산 ${won(lumped)} · 덜 주던 금액 ${won(q.amount - lumped)}`);
  ok("옛 계산은 사용자에게 불리했다", q.amount > lumped);
  ok("낸 돈을 넘지 않는다", q.amount <= paidThisPeriod(upgraded));
}

console.log("\n── 취소는 결제 건마다 나눠 나간다 ──");
{
  const q = quote(upgraded, NOW, { opened: true, openedToday: false });
  const { out, rest } = cancels(upgraded, q.amount);
  ok("남는 금액 없이 전부 나간다", rest === 0, "남음 " + rest);
  ok("합계가 환불 금액과 같다", out.reduce((a, b) => a + b.amount, 0) === q.amount);
  const cap = Object.fromEntries(upgraded.periodPayments.map((p) => [p.key, p.amount]));
  ok("각 취소가 그 결제 건의 금액을 넘지 않는다",
     out.every((c) => c.amount <= cap[c.key]),
     JSON.stringify(out));
  ok("최근 결제부터 되돌린다", out[0].key === "pay_up", JSON.stringify(out.map((c) => c.key)));

  /* 고치기 전에는 한 건(lastPaymentKey)에 전액을 몰아 냈다. 그 건은 9,900원인데
     환불액은 그보다 크다 — 카드사가 거절해서 환불이 통째로 실패했다. */
  ok("옛 방식이었다면 카드사가 거절했을 금액이다",
     q.amount > cap["pay_base"], `${won(q.amount)} > ${won(cap["pay_base"])}`);
}

console.log("\n── 업그레이드하지 않은 보통 구독 ──");
{
  const plain = {
    plan: "basic", currentPeriodStart: START, currentPeriodEnd: END,
    lastPaymentKey: "pay_base",
    periodPayments: [{ key: "pay_base", amount: PRICE.basic, from: START }],
  };
  const q = quote(plain, NOW, { opened: true, openedToday: false });
  ok("전과 같은 금액이다", q.amount === Math.floor(PRICE.basic * 24 / 31 * 0.9), won(q.amount));
  const { out, rest } = cancels(plain, q.amount);
  ok("취소는 한 건이면 된다", out.length === 1 && rest === 0);
}

console.log("\n── periodPayments 가 없던 옛 구독 ──");
{
  const old = {
    plan: "basic", currentPeriodStart: START, currentPeriodEnd: END,
    lastPaymentKey: "pay_old",
  };
  const q = quote(old, NOW, { opened: true, openedToday: false });
  ok("정가로 되돌아가 계산한다", q.amount === Math.floor(PRICE.basic * 24 / 31 * 0.9), won(q.amount));
  const { out, rest } = cancels(old, q.amount);
  ok("lastPaymentKey 로 취소한다", out.length === 1 && out[0].key === "pay_old" && rest === 0,
     JSON.stringify(out));
}

console.log("\n── 오늘 리포트를 열었으면 오늘도 차감한다 ──");
{
  const a = quote(upgraded, NOW, { opened: true, openedToday: false }).amount;
  const b = quote(upgraded, NOW, { opened: true, openedToday: true }).amount;
  ok("오늘 1건이면 덜 받는다", b < a, `${won(a)} → ${won(b)}`);
  ok("차이는 하루치 언저리다", a - b > 0 && a - b < paidThisPeriod(upgraded) / 20,
     won(a - b));
}

console.log("\n── 업그레이드한 날 바로 환불 ──");
{
  // 차액을 낸 그날 환불하면 차액은 하루도 안 썼다 — 거의 전부 돌아와야 한다.
  const q = quote(upgraded, NOW, { opened: true, openedToday: false });
  const backOfDiff = q.amount - Math.floor(PRICE.basic * 24 / 31 * 0.9);
  ok("차액은 수수료만 떼고 거의 그대로 돌아온다",
     backOfDiff >= Math.floor(DIFF * 0.9) - 1, `${won(backOfDiff)} vs ${won(DIFF * 0.9)}`);
}

console.log("\n── 7일 이내 미열람이면 낸 돈 전부 ──");
{
  const q = quote(upgraded, NOW, { opened: false, openedToday: false });
  ok("전액은 '정가'가 아니라 '낸 돈' 이다",
     q.amount === PRICE.basic + DIFF && q.why === "withdraw", won(q.amount));
  const { out, rest } = cancels(upgraded, q.amount);
  ok("두 건을 모두 취소해야 전액이 된다", out.length === 2 && rest === 0,
     JSON.stringify(out.map((c) => c.amount)));
}

console.log("\n── 주기가 끝날 무렵 업그레이드 ──");
{
  const nowLate = START + 29 * DAY;
  const diffLate = Math.floor((PRICE.pro - PRICE.basic) * (2 / 31));
  const late = {
    plan: "pro", currentPeriodStart: START, currentPeriodEnd: END,
    lastPaymentKey: "pay_base",
    periodPayments: [
      { key: "pay_base", amount: PRICE.basic, from: START },
      { key: "pay_up", amount: diffLate, from: nowLate },
    ],
  };
  const q = quote(late, nowLate, { opened: true, openedToday: false });
  ok("낸 돈을 넘지 않는다", q.amount <= PRICE.basic + diffLate,
     `${won(q.amount)} vs ${won(PRICE.basic + diffLate)}`);
  const { rest } = cancels(late, q.amount);
  ok("취소가 모자라지 않는다", rest === 0, "남음 " + rest);
}

/* ── 옮겨 적은 것이 원본과 같은가 ─────────────────────────────
   이 파일은 functions/index.js 의 함수를 손으로 옮겨 적어 검사한다. 원본만
   고치고 여기를 안 고치면, 통과하는 테스트가 실제로는 아무것도 안 지킨다.
   본문을 견줘 본다(공백·주석은 뺀다).
   ─────────────────────────────────────────────────────────── */
console.log("\n── 옮겨 적은 것이 원본과 같은가 ──");
{
  const { readFileSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const { dirname, join } = await import("node:path");
  const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "index.js"), "utf8");
  const mine = readFileSync(fileURLToPath(import.meta.url), "utf8");
  const body = (text, name) => {
    const i = text.indexOf(`function ${name}(`);
    if (i < 0) return null;
    let d = 0, j = text.indexOf("{", i);
    for (let k = j; k < text.length; k++) {
      if (text[k] === "{") d++;
      else if (text[k] === "}" && --d === 0) {
        return text.slice(j, k + 1).replace(/\/\*[\s\S]*?\*\/|\/\/[^\n]*|\s+/g, "");
      }
    }
    return null;
  };
  for (const name of ["refundSources", "unusedOf"]) {
    const a = body(src, name), b = body(mine, name);
    ok(`${name} 이 index.js 와 같다`, a !== null && a === b,
       a === null ? "index.js 에서 못 찾음" : "본문이 다르다");
  }
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
