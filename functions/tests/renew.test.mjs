/* ============================================================
   자동 갱신 — 매일 한 번 도는 배치

   왜 따로 있는가. 표의 열 하나(자동 갱신)만 미리보기에서 눌러 볼 수 없다.
   브라우저에는 크론이 없어서다. 여기서 그 자리를 메운다.

   무엇을 보는가
     · 해지 예약이면 긁지 않고 닫는다
     · 예약된 다운그레이드를 그때 적용한다
     · 새 주기라 지난 주기의 결제 기록을 끊는다
     · 카드가 거절되면 끊지 않고 '결제 실패' 로 두고 기다린다
     · 계정이 사라진 문서는 긁지 않는다
     · 사용자가 같은 순간에 결제하면 두 번 청구되지 않는다  ← 제일 중요하다
     · 목록을 만든 뒤 상태가 바뀌었으면 다시 긁지 않는다

   서버는 여기서 돌릴 수 없다(파이어베이스가 필요하다). 그래서 배치가 한 건을
   처리할 때 하는 판단만 그대로 옮겨 놓고, 파이어스토어와 토스를 아주 작은
   대역으로 흉내 낸다. 옮겨 적은 것이 원본과 어긋나지 않는지는 맨 아래에서
   따로 본다.

   실행
     node functions/tests/renew.test.mjs
   ============================================================ */

const PRICE = { basic: 9900, pro: 14900 };
const DAY = 86400000;
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600000) / DAY);
const DELETE = Symbol("delete");

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};

class Err extends Error { constructor(m, locked) { super(m); if (locked) this.kosLocked = true; } }

/* ── 대역 ──────────────────────────────────────────────────── */
function makeRef(doc) {
  return {
    _doc: doc,
    async get() { return { data: () => ({ ...doc }) }; },
    async set(patch) {
      for (const [k, v] of Object.entries(patch)) {
        if (v === DELETE) delete doc[k]; else doc[k] = v;
      }
    },
  };
}

/* renewSubscriptions 가 한 건을 처리할 때 하는 일. index.js 의 루프 본문과 같다. */
async function renewOne(ref, now, deps) {
  const { authExists, withLock, charge, writePayment } = deps;
  const d0 = (await ref.get()).data();
  const uid = "u1";
  let sub = d0;
  let plan = sub.pendingPlan || sub.plan;
  try {
    if (!authExists()) {
      await ref.set({ status: "deleted", billingKey: DELETE });
      return "deleted";
    }
    let out = "renewed";
    await withLock(async () => {
      const fresh = (await ref.get()).data();
      if (!fresh || fresh.status !== "active") { out = "skip"; return; }
      const endMs = fresh.currentPeriodEnd || 0;
      if (endMs > now) { out = "skip"; return; }
      sub = fresh;
      plan = sub.pendingPlan || sub.plan;

      if (sub.cancelAtPeriodEnd) {
        await ref.set({ status: "expired" });
        out = "expired";
        return;
      }
      const pay = await charge(PRICE[plan], `renew_${uid}_${kstDayNo(endMs)}`);
      await ref.set({
        plan, pendingPlan: null, status: "active",
        currentPeriodStart: now,
        currentPeriodEnd: now + 30 * DAY,
        lastPaymentKey: pay ? pay.paymentKey : sub.lastPaymentKey,
        periodPayments: pay ? [{ key: pay.paymentKey, amount: PRICE[plan], from: now }] : [],
        refundDone: DELETE,
        failedAt: null,
      });
    });
    return out;
  } catch (e) {
    if (e && e.kosLocked) return "locked";
    await ref.set({ status: "past_due", failedAt: now });
    await writePayment({ amount: PRICE[plan] || 0, kind: "failed", status: "failed", plan });
    return "past_due";
  }
}

const noLock = (fn) => fn();
const okCharge = (n = 0) => async () => ({ paymentKey: "pay_" + (++n) });
const NOW = Date.parse("2026-09-02T02:00:00Z");
const base = () => ({
  status: "active", plan: "basic", lastPaymentKey: "old",
  currentPeriodStart: NOW - 30 * DAY, currentPeriodEnd: NOW - 1000,
  periodPayments: [{ key: "old", amount: 9900, from: NOW - 30 * DAY }],
  refundDone: [{ key: "old", amount: 100 }],
});

console.log("── 보통 갱신 ──");
{
  const doc = base(); const ref = makeRef(doc);
  const charged = [];
  const r = await renewOne(ref, NOW, {
    authExists: () => true, withLock: noLock,
    charge: async (amt, idem) => { charged.push({ amt, idem }); return { paymentKey: "pay_new" }; },
    writePayment: async () => {},
  });
  ok("갱신됐다", r === "renewed");
  ok("플랜 정가를 받는다", charged[0].amt === 9900, String(charged[0].amt));
  ok("새 기간이 시작된다", doc.currentPeriodStart === NOW && doc.currentPeriodEnd > NOW);
  ok("지난 주기 결제 기록을 끊는다",
     doc.periodPayments.length === 1 && doc.periodPayments[0].key === "pay_new",
     JSON.stringify(doc.periodPayments));
  ok("지난 환불 기록(refundDone)을 지운다", doc.refundDone === undefined,
     "남으면 다음 환불이 이미 취소한 줄 알고 건너뛴다");
  ok("멱등 이름은 그 주기로 고정된다",
     charged[0].idem === `renew_u1_${kstDayNo(NOW - 1000)}`, charged[0].idem);
}

console.log("\n── 해지 예약이면 긁지 않는다 ──");
{
  const doc = { ...base(), cancelAtPeriodEnd: true }; const ref = makeRef(doc);
  let charged = 0;
  const r = await renewOne(ref, NOW, {
    authExists: () => true, withLock: noLock,
    charge: async () => { charged++; return { paymentKey: "x" }; }, writePayment: async () => {},
  });
  ok("종료로 닫는다", r === "expired" && doc.status === "expired", doc.status);
  ok("카드를 긁지 않는다", charged === 0, String(charged));
}

console.log("\n── 예약된 다운그레이드를 적용한다 ──");
{
  const doc = { ...base(), plan: "pro", pendingPlan: "basic" }; const ref = makeRef(doc);
  const charged = [];
  await renewOne(ref, NOW, {
    authExists: () => true, withLock: noLock,
    charge: async (amt) => { charged.push(amt); return { paymentKey: "p" }; }, writePayment: async () => {},
  });
  ok("내린 플랜 금액을 받는다", charged[0] === PRICE.basic, String(charged[0]));
  ok("플랜이 바뀐다", doc.plan === "basic", doc.plan);
  ok("예약이 지워진다", doc.pendingPlan === null);
  ok("결제 기록도 내린 플랜 금액", doc.periodPayments[0].amount === PRICE.basic);
}

console.log("\n── 카드가 거절되면 ──");
{
  const doc = { ...base(), plan: "pro", pendingPlan: "basic" }; const ref = makeRef(doc);
  const rows = [];
  const r = await renewOne(ref, NOW, {
    authExists: () => true, withLock: noLock,
    charge: async () => { throw new Err("한도 초과"); },
    writePayment: async (x) => rows.push(x),
  });
  ok("끊지 않고 '결제 실패' 로 둔다", r === "past_due" && doc.status === "past_due", doc.status);
  ok("실패 기록이 남는다", rows.length === 1 && rows[0].kind === "failed");
  /* 다운그레이드가 예약돼 있었으면 청구하려던 건 BASIC 이다. 옛 플랜(PRO)으로
     적으면 내역에 실제와 다른 금액이 남는다. */
  ok("청구하려던 플랜으로 적는다", rows[0].plan === "basic" && rows[0].amount === PRICE.basic,
     JSON.stringify(rows[0]));
}

console.log("\n── 계정이 사라진 문서 ──");
{
  const doc = base(); const ref = makeRef(doc);
  let charged = 0;
  const r = await renewOne(ref, NOW, {
    authExists: () => false, withLock: noLock,
    charge: async () => { charged++; return {}; }, writePayment: async () => {},
  });
  ok("긁지 않는다", charged === 0 && r === "deleted");
  ok("카드를 지운다", doc.billingKey === undefined && doc.status === "deleted");
}

console.log("\n── 사용자가 같은 순간에 결제하면 ──");
{
  /* 갱신 대상은 기간이 끝난 문서라 subActive 가 false 다. 그래서 해지·환불은
     저절로 막히지만 '새 결제' 만은 막히지 않는다. 배치가 자물쇠를 안 잡으면
     같은 사람에게 두 번 청구된다. */
  const doc = base(); const ref = makeRef(doc);
  let charged = 0;
  const rows = [];
  const r = await renewOne(ref, NOW, {
    authExists: () => true,
    withLock: async () => { throw new Err("처리하는 중입니다", true); },
    charge: async () => { charged++; return {}; },
    writePayment: async (x) => rows.push(x),
  });
  ok("건너뛴다", r === "locked", r);
  ok("두 번 청구하지 않는다", charged === 0, String(charged));
  ok("'결제 실패' 로 적지 않는다", doc.status === "active" && rows.length === 0,
     "방금 결제한 사람에게 실패가 뜨면 안 된다");
}

console.log("\n── 목록을 만든 뒤 상태가 바뀌었으면 ──");
{
  // 자물쇠를 잡는 사이에 사용자가 새로 결제해 기간이 미래로 옮겨졌다
  const doc = base(); const ref = makeRef(doc);
  let charged = 0;
  const r = await renewOne(ref, NOW, {
    authExists: () => true,
    withLock: async (fn) => { doc.currentPeriodEnd = NOW + 30 * DAY; return fn(); },
    charge: async () => { charged++; return {}; }, writePayment: async () => {},
  });
  ok("다시 긁지 않는다", charged === 0 && r === "skip", `${r} · ${charged}회`);
}
{
  // 그 사이 해지·탈퇴로 active 가 아니게 됐다
  const doc = base(); const ref = makeRef(doc);
  let charged = 0;
  const r = await renewOne(ref, NOW, {
    authExists: () => true,
    withLock: async (fn) => { doc.status = "deleted"; return fn(); },
    charge: async () => { charged++; return {}; }, writePayment: async () => {},
  });
  ok("active 가 아니면 건드리지 않는다", charged === 0 && r === "skip", `${r} · ${charged}회`);
}

/* ── 옮겨 적은 것이 원본과 같은가 ─────────────────────────────
   본문을 그대로 베낄 수는 없다(파이어스토어 호출이 섞여 있다). 대신 반드시
   있어야 할 것들이 index.js 에 남아 있는지 본다. 하나라도 빠지면 위 검사는
   전부 통과하면서 실제로는 두 번 청구된다.
   ─────────────────────────────────────────────────────────── */
console.log("\n── 원본에 그 장치들이 있는가 ──");
{
  const { readFileSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const { dirname, join } = await import("node:path");
  const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "index.js"), "utf8");
  /* 본문 끝을 글자 수로 어림잡지 않는다. 코드가 조금 길어지면 뒤쪽 검사가
     조용히 아무것도 안 보게 된다 — 실제로 그렇게 통과할 뻔했다. 괄호로 끊는다. */
  const i = src.indexOf("exports.renewSubscriptions");
  const open = src.indexOf("(", src.indexOf("onSchedule", i));
  let depth = 0, end = open;
  for (; end < src.length; end++) {
    if (src[end] === "(") depth++;
    else if (src[end] === ")" && --depth === 0) break;
  }
  const body = src.slice(i, end + 1);

  ok("갱신도 같은 자물쇠를 잡는다", /withLock\(db, d\.ref, "renew"/.test(body));
  ok("자물쇠를 잡은 뒤 다시 읽는다", /const fresh = \(await d\.ref\.get\(\)\)\.data\(\)/.test(body));
  ok("그 사이 새 기간이 시작됐으면 건너뛴다", /endMs > now\.getTime\(\)/.test(body));
  ok("active 가 아니면 건너뛴다", /fresh\.status !== "active"/.test(body));
  ok("자물쇠 실패는 실패로 적지 않는다", /e\.kosLocked/.test(body));
  ok("실패 기록에 청구하려던 플랜을 쓴다",
     /amount: PRICE\[plan\] \|\| 0[\s\S]{0,80}plan,/.test(body));
  ok("새 주기에 refundDone 을 지운다", /refundDone: admin\.firestore\.FieldValue\.delete\(\)/.test(body));
  ok("상한까지 찼으면 알린다", /상한\(400\)까지 찼다/.test(body));
  /* 카드가 거절돼도 여태 아무 데도 안 알렸다. 사용자는 설정 창을 열기 전에는
     모르고, 우리는 몇 명이 멈춰 있는지 알 방법이 없었다. */
  ok("카드 거절을 운영자에게 알린다", /alertOps\(`정기결제 실패/.test(body));
  ok("거절이 없는 날은 알리지 않는다", /if \(failed\.length\) \{/.test(body));
  ok("withLock 이 우리 표시를 붙인다", /e\.kosLocked = true/.test(src));
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
