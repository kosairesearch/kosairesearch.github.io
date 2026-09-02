/* ============================================================
   돈이 두 번 나가지 않게 하는 장치들

   왜 있는가. 환불 금액이 몇백 원 틀리는 것과, 돈이 두 번 나가는 것은 다른
   종류의 사고다. 뒤쪽은 환불하면 되는 게 아니라 신뢰가 깨진다. 그런데 그쪽은
   여태 아무 장치가 없었다.

     ① "이미 환불했나?" 를 확인하고 → 환불했다. 그 사이에 두 번째 요청이
        들어오면 둘 다 확인을 통과한다. 느린 화면에서 두 번 누르면 일어난다.
     ② 취소가 여러 건으로 나가는데 중간에 실패하면, 다시 눌렀을 때 이미
        취소한 건을 또 취소하려 든다.

   서버는 여기서 돌릴 수 없다(파이어베이스가 필요하다). 그래서 장치의 알맹이만
   그대로 옮겨 놓고, 파이어스토어 트랜잭션과 토스를 아주 작은 대역으로 흉내
   내어 실제로 두 번 나가는지 본다.

   실행
     node functions/tests/safety.test.mjs
   ============================================================ */

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};

class Err extends Error { constructor(code, msg) { super(msg); this.code = code; } }

/* ── 파이어스토어 대역 ──────────────────────────────────────
   문서 하나와 트랜잭션만 흉내 낸다. 트랜잭션은 '읽고 쓰는 동안 아무도 못
   끼어든다' 가 핵심이므로, 그 구간을 한 줄로 이어 실행한다. */
function makeDb() {
  let doc = {};
  let chain = Promise.resolve();          // 트랜잭션끼리는 줄을 선다
  const ref = {
    path: "subscriptions/u1",
    async get() { return { exists: !!Object.keys(doc).length, data: () => ({ ...doc }) }; },
    async set(patch, opt) {
      for (const [k, v] of Object.entries(patch)) {
        if (v === DELETE) delete doc[k]; else doc[k] = v;
      }
      if (!opt || !opt.merge) doc = { ...patch };
    },
  };
  const db = {
    runTransaction(fn) {
      const run = chain.then(() => fn({
        get: async () => ({ exists: !!Object.keys(doc).length, data: () => ({ ...doc }) }),
        set: (r, patch) => { Object.assign(doc, patch); },
      }));
      chain = run.catch(() => {});        // 실패해도 줄은 이어진다
      return run;
    },
  };
  return { db, ref, peek: () => ({ ...doc }) };
}
const DELETE = Symbol("delete");

/* ── functions/index.js 에서 그대로 옮긴 것 ────────────────── */
const BUSY_TTL = 2 * 60 * 1000;

async function withLock(db, ref, op, fn) {
  await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const busy = snap.exists && snap.data().busy;
    const at = busy && busy.at && typeof busy.at.toMillis === "function" ? busy.at.toMillis() : 0;
    if (busy && Date.now() - at < BUSY_TTL) {
      throw new Err("aborted",
        "앞서 요청하신 건을 처리하는 중입니다. 잠시 후 다시 시도하여 주시기 바랍니다.");
    }
    tx.set(ref, { busy: { op, at: { toMillis: () => Date.now() } } });
  });
  try {
    return await fn();
  } finally {
    try { await ref.set({ busy: DELETE }, { merge: true }); } catch (e) {}
  }
}

console.log("── 자물쇠: 두 번 눌러도 한 번만 ──");
{
  const { db, ref } = makeDb();
  let ran = 0;
  const work = () => withLock(db, ref, "refund", async () => {
    ran++;
    await new Promise((r) => setTimeout(r, 20));   // 카드사를 부르는 동안
    return "done";
  });
  const [a, b] = await Promise.allSettled([work(), work()]);
  ok("본 작업은 한 번만 돈다", ran === 1, "돈 횟수 " + ran);
  ok("하나는 성공한다", [a, b].filter((r) => r.status === "fulfilled").length === 1);
  const no = [a, b].find((r) => r.status === "rejected");
  ok("다른 하나는 거절된다", !!no && /처리하는 중입니다/.test(no.reason.message),
     no ? no.reason.message : "거절 없음");
}

console.log("\n── 자물쇠: 끝나면 풀린다 ──");
{
  const { db, ref, peek } = makeDb();
  await withLock(db, ref, "refund", async () => "ok");
  ok("자물쇠가 남지 않는다", peek().busy === undefined, JSON.stringify(peek()));
  let second = false;
  await withLock(db, ref, "refund", async () => { second = true; });
  ok("그래서 다시 할 수 있다", second);
}

console.log("\n── 자물쇠: 중간에 터져도 풀린다 ──");
{
  const { db, ref, peek } = makeDb();
  let msg = "";
  await withLock(db, ref, "refund", async () => { throw new Err("internal", "카드사 오류"); })
    .catch((e) => { msg = e.message; });
  ok("오류는 그대로 올라온다", msg === "카드사 오류", msg);
  ok("자물쇠는 풀려 있다", peek().busy === undefined,
     "안 풀리면 그 사람은 영영 환불도 결제도 못 한다");
}

console.log("\n── 자물쇠: 오래된 것은 없는 셈 친다 ──");
{
  const { db, ref } = makeDb();
  // 함수가 중간에 죽어 3분 전 자물쇠가 남아 있는 상황
  await ref.set({ busy: { op: "refund", at: { toMillis: () => Date.now() - 3 * 60 * 1000 } } }, { merge: true });
  let ran = false;
  await withLock(db, ref, "refund", async () => { ran = true; });
  ok("TTL 지난 자물쇠는 막지 않는다", ran);
}

/* ── 환불: 중간에 실패해도 두 번 취소하지 않는다 ───────────── */
const PRICE = { basic: 9900, pro: 14900 };
function refundSources(sub) {
  const list = ((sub && sub.periodPayments) || []).filter((e) => e && e.key && e.amount > 0);
  if (list.length) return list.slice().reverse();
  return sub && sub.lastPaymentKey
    ? [{ key: sub.lastPaymentKey, amount: PRICE[sub.plan] || 0 }] : [];
}

/* doRefund 의 알맹이. toss 와 writePayment 만 대역으로 받는다. */
async function doRefund(ref, sub, q, toss, writePayment) {
  const done = ((sub && sub.refundDone) || []).slice();
  const takenOf = (key) => done.reduce((a, d) => a + (d.key === key ? d.amount : 0), 0);
  let rest = q.amount - done.reduce((a, d) => a + d.amount, 0);
  for (const src of refundSources(sub)) {
    if (rest <= 0) break;
    const room = src.amount - takenOf(src.key);
    const take = Math.min(rest, room);
    if (take <= 0) continue;
    await toss(`/payments/${src.key}/cancel`, { cancelAmount: take }, `refund_u1_${src.key}_${take}`);
    done.push({ key: src.key, amount: take });
    await ref.set({ refundDone: done }, { merge: true });
    await writePayment({ amount: -take, paymentKey: src.key });
    rest -= take;
  }
  if (rest > 0) throw new Err("internal", "환불을 끝까지 처리하지 못했습니다.");
}

console.log("\n── 환불: 중간에 실패하고 다시 눌렀을 때 ──");
{
  const { ref, peek } = makeDb();
  const sub = {
    plan: "pro", lastPaymentKey: "pay_base",
    periodPayments: [
      { key: "pay_base", amount: 9900, from: 0 },
      { key: "pay_up", amount: 3833, from: 0 },
    ],
  };
  const q = { amount: 10280 };

  const sent = [];
  let failNext = true;
  const toss = async (path, body, idem) => {
    sent.push({ path, amount: body.cancelAmount, idem });
    // 두 번째 취소(월 구독 건)에서 한 번 끊긴다
    if (failNext && path.includes("pay_base")) { failNext = false; throw new Err("internal", "네트워크 오류"); }
  };
  const rows = [];
  const writePayment = async (r) => { rows.push(r); };

  let msg = "";
  await doRefund(ref, sub, q, toss, writePayment).catch((e) => { msg = e.message; });
  ok("첫 번째 취소는 나갔다", sent.filter((s) => s.path.includes("pay_up")).length === 1);
  ok("두 번째에서 끊겼다", msg === "네트워크 오류", msg);
  ok("나간 만큼만 기록됐다", (peek().refundDone || []).length === 1,
     JSON.stringify(peek().refundDone));

  // 사용자가 다시 누른다 — 기록을 들고 이어서 한다
  const again = { ...sub, refundDone: peek().refundDone };
  sent.length = 0;
  await doRefund(ref, again, q, toss, writePayment);
  ok("다시 눌러도 첫 건은 또 취소하지 않는다",
     sent.every((s) => !s.path.includes("pay_up")), JSON.stringify(sent));
  ok("남은 것만 취소한다", sent.length === 1 && sent[0].path.includes("pay_base"),
     JSON.stringify(sent));

  const total = (peek().refundDone || []).reduce((a, d) => a + d.amount, 0);
  ok("합계가 환불 금액과 정확히 같다", total === q.amount, `${total} vs ${q.amount}`);
  ok("어느 건도 자기 금액을 넘지 않는다",
     (peek().refundDone || []).every((d) =>
       d.amount <= sub.periodPayments.find((p) => p.key === d.key).amount));
}

console.log("\n── 환불: 같은 이름으로 보내는가 ──");
{
  const { ref } = makeDb();
  const sub = { plan: "basic", lastPaymentKey: "pay_a",
                periodPayments: [{ key: "pay_a", amount: 9900, from: 0 }] };
  const seen = [];
  const toss = async (p, b, idem) => { seen.push(idem); };
  await doRefund(ref, sub, { amount: 6237 }, toss, async () => {});
  const { ref: ref2 } = makeDb();
  await doRefund(ref2, sub, { amount: 6237 }, toss, async () => {});
  ok("같은 환불은 같은 이름으로 나간다", seen[0] === seen[1], JSON.stringify(seen));
  ok("이름에 시각이 안 들어간다", !/\d{10,}/.test(seen[0]), seen[0]);
}

/* ── 옮겨 적은 것이 원본과 같은가 ──────────────────────────── */
console.log("\n── 옮겨 적은 것이 원본과 같은가 ──");
{
  const { readFileSync } = await import("node:fs");
  const { fileURLToPath } = await import("node:url");
  const { dirname, join } = await import("node:path");
  const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "index.js"), "utf8");
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
  const real = body(src, "withLock");
  ok("index.js 에 withLock 이 있다", real !== null);
  /* 대역을 쓰느라 본문이 똑같지는 않다. 대신 반드시 있어야 할 것들을 확인한다 —
     하나라도 빠지면 자물쇠가 자물쇠 노릇을 못 한다. */
  ok("트랜잭션 안에서 확인하고 잠근다", /runTransaction/.test(real || ""));
  ok("TTL 로 오래된 자물쇠를 풀어 준다", /BUSY_TTL/.test(real || ""));
  ok("finally 에서 반드시 푼다", /finally/.test(real || ""));
  ok("돈 나가는 함수 셋에 다 걸려 있다",
     (src.match(/withLock\(db, ref, "/g) || []).length === 3,
     String((src.match(/withLock\(db, ref, "/g) || []).length));
  ok("결제·취소가 멱등 이름을 들고 나간다",
     /Idempotency-Key/.test(src) && /refund_\$\{uid\}_\$\{src\.key\}/.test(src));
  /* doRefund 에 인자를 하나 더 받게 고치면서 호출부 한 곳을 빠뜨린 적이 있다
     (deleteAccount). 그러면 유료 회원은 탈퇴 자체가 안 됐다 — 환불에서 터지고,
     "환불 처리에 실패해 탈퇴를 진행하지 않았습니다" 로 막힌다. 문법 검사로는
     안 걸리고, 그 길을 실제로 지나가야만 드러난다. 인자 수를 세어 둔다. */
  const decl = (src.match(/async function doRefund\(([^)]*)\)/) || [])[1] || "";
  const wantArgs = decl.split(",").length;
  const calls = [...src.matchAll(/await doRefund\(([^)]*)\)/g)].map((m) => m[1].split(",").length);
  ok("doRefund 를 부르는 곳이 둘이다", calls.length === 2, JSON.stringify(calls));
  ok("모든 호출이 선언과 인자 수가 같다",
     calls.length > 0 && calls.every((n) => n === wantArgs),
     `선언 ${wantArgs}개 · 호출 ${JSON.stringify(calls)}`);

  ok("새 주기마다 refundDone 을 지운다",
     (src.match(/refundDone: admin\.firestore\.FieldValue\.delete\(\)|patch\.refundDone = admin\.firestore\.FieldValue\.delete\(\)/g) || []).length === 3,
     String((src.match(/refundDone: admin\.firestore\.FieldValue\.delete\(\)|patch\.refundDone = admin\.firestore\.FieldValue\.delete\(\)/g) || []).length));
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
