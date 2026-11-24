/* ============================================================
   결제 내역 — 화면이 읽을 수 있는 모양으로 나가는가
   ------------------------------------------------------------
   실행:  node functions/tests/payments.test.mjs

   왜 있는가. payments/{uid}/items 는 규칙으로 아무에게도 열지 않았다(서버만
   쓴다). 그래서 본인이 자기 결제 내역을 보는 길이 listPayments 하나뿐인데,
   그 응답이 화면에서 안 읽히면 회원은 돈이 오간 기록을 볼 방법이 없다.

   가장 쉽게 나는 사고. Firestore 시각(Timestamp)을 그대로 실어 보내면
   브라우저에는 {_seconds: …} 라는 객체로 도착한다. 화면의 날짜 함수는 숫자·
   글자·Timestamp 만 읽으므로 그 객체는 NaN 이 되고, 내역 표의 '일자' 칸이
   통째로 빈다. 표는 그려지는데 날짜만 없어서 눈으로는 잘 안 보인다.

   맨 아래 '진짜 listPayments' 는 결제 스위치를 켠 진짜 함수를 가짜 파이어스토어로
   돌린다(lib/paid-harness.mjs). 요금제는 하나(member 월 14,900원)이고, 환불 사유는
   withdraw · early · late 다(2026-11-24). 그 전에 남은 내역의 사유(used · left)도
   그대로 내보낸다 — 화면이 이름표로 읽는다.
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { call, reset, store, Ts, UID } from "./lib/paid-harness.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

/* functions/index.js 의 isoOf 와 같은 식 */
const isoOf = (v) =>
  v == null ? null
  : typeof v.toDate === "function" ? v.toDate().toISOString()
  : typeof v === "number" ? new Date(v).toISOString()
  : String(v);

/* payment-config.js 의 fmtDay 가 시각을 읽는 방식 — 화면이 실제로 하는 일 */
const readableAt = (v) => {
  const ms = typeof v?.toMillis === "function" ? v.toMillis()
           : typeof v === "number" ? v : Date.parse(v);
  return Number.isFinite(ms);
};

/* Firestore Timestamp 흉내 */
const stamp = (iso) => ({
  toDate: () => new Date(iso),
  _seconds: Math.floor(Date.parse(iso) / 1000),
  _nanoseconds: 0,
});

/* listPayments 가 한 줄을 내보내는 모양 */
const rowOf = (p) => ({
  amount: p.amount || 0,
  kind: p.kind || null,
  why: p.why || null,
  status: p.status || "paid",
  plan: p.plan || null,
  paidAt: isoOf(p.paidAt),
  createdAt: isoOf(p.createdAt),
});

let pass = 0, fail = 0;
const eq = (name, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log(`FAIL  ${name} → ${g}  (기대 ${w})`); }
};

console.log("── 시각을 화면이 읽을 수 있게 바꾼다 ──");
eq("Timestamp → 글자", isoOf(stamp("2026-08-30T05:00:00.000Z")), "2026-08-30T05:00:00.000Z");
eq("밀리초 → 글자", isoOf(Date.parse("2026-08-30T05:00:00.000Z")), "2026-08-30T05:00:00.000Z");
eq("이미 글자면 그대로", isoOf("2026-08-30T05:00:00.000Z"), "2026-08-30T05:00:00.000Z");
eq("없으면 null", isoOf(null), null);
eq("결제 실패 줄은 paidAt 이 없다", isoOf(undefined), null);

console.log("\n── 화면이 실제로 읽어 낸다 ──");
eq("바꾼 값은 날짜로 읽힌다", readableAt(isoOf(stamp("2026-08-30T05:00:00.000Z"))), true);
/* 이게 막으려는 사고다. 안 바꾸고 그대로 실어 보내면 이렇게 된다. */
eq("안 바꾸고 보내면 못 읽는다(막으려는 사고)",
   readableAt({ _seconds: 1788000000, _nanoseconds: 0 }), false);

console.log("\n── 한 줄의 모양 ──");
const row = rowOf({
  amount: 14900, description: "멤버십 월 구독", kind: "subscription",
  status: "paid", plan: "member",
  paymentKey: "tviva20260830", orderId: "kosai_new_abc123_xyz",
  paidAt: "2026-08-30T05:00:00.000Z", createdAt: stamp("2026-08-30T05:00:01.000Z"),
});
eq("금액", row.amount, 14900);
eq("종류", row.kind, "subscription");
/* 토스 식별자는 나가면 안 된다. 화면이 쓸 일이 없고, 결제 건을 취소할 수
   있는 열쇠라 브라우저에 둘 이유가 없다. */
eq("결제 식별자는 안 나간다", "paymentKey" in row || "orderId" in row, false);
/* 설명 문장은 한국어로 굳어 있어 영어 화면에서 번역할 수가 없다. 화면은
   kind 로 문구를 만든다. */
eq("한국어 설명 문장도 안 나간다", "description" in row, false);

const refund = rowOf({ amount: -13410, kind: "refund", why: "early",
                       status: "refunded", plan: "member", paidAt: null,
                       createdAt: stamp("2026-08-30T05:00:00.000Z") });
eq("환불은 음수", refund.amount, -13410);
eq("환불 사유가 실린다", refund.why, "early");
eq("환불 줄도 날짜가 읽힌다", readableAt(refund.createdAt), true);

console.log("\n── 서버와 미리보기의 줄 수가 같은가 ──");
/* 다르면 미리보기에서 보이던 줄이 실제에서 안 보인다. 주석으로 '같아야 한다'
   고 적어 두는 것만으로는 다음에 한쪽만 고치는 걸 못 막는다. */
const pick = (path) => {
  const line = readFileSync(join(ROOT, path), "utf8")
    .split("\n").find((l) => l.startsWith("const PAYMENT_PAGE = "));
  if (!line) return null;
  const n = parseInt(line.replace("const PAYMENT_PAGE = ", ""), 10);
  return Number.isFinite(n) ? n : null;
};
const server = pick("functions/index.js");
const demo = pick("staging/demo-backend.js");
eq("서버에 값이 있다", server, 24);
eq("미리보기에 값이 있다", demo, 24);
/* null === null 로 통과해 버리면 안 된다. 값이 있고, 그 값이 같아야 한다. */
eq("두 값이 같다", server !== null && server === demo, true);

console.log("\n── 진짜 listPayments ──");
{
  reset();
  const at = (iso) => new Ts(Date.parse(iso));
  const put = (id, v) => store.set(`payments/${UID}/items/${id}`, v);
  put("a", { amount: 14900, description: "멤버십 월 구독", kind: "subscription", status: "paid", plan: "member",
             paymentKey: "pay_1", orderId: "kosai_new_x", paidAt: "2026-11-02T05:00:00.000Z", createdAt: at("2026-11-02T05:00:01Z") });
  put("b", { amount: -13410, description: "환불 · 7일 이내 환불(이용일수 차감)", kind: "refund", why: "early",
             status: "refunded", plan: "member", paymentKey: "pay_1", paidAt: "2026-11-04T05:00:00.000Z",
             createdAt: at("2026-11-04T05:00:01Z") });
  put("c", { amount: -5940, description: "환불 · 이용분 차감 환불", kind: "refund", why: "used",
             status: "refunded", plan: "basic", paymentKey: "pay_0", paidAt: "2026-08-30T05:00:00.000Z",
             createdAt: at("2026-08-30T05:00:01Z") });
  for (let i = 0; i < 30; i++) {
    put("old" + i, { amount: 9900, kind: "subscription", status: "paid", plan: "basic",
                     paymentKey: "p" + i, paidAt: null, createdAt: at(`2024-0${1 + (i % 9)}-0${1 + (i % 9)}T00:00:0${i % 10}Z`) });
  }
  const r = await call("listPayments", {});
  const items = (r.data && r.data.items) || [];
  eq("한 번에 24줄까지", items.length, 24);
  eq("최근 것부터 — 환불(early) · 결제 · 옛 환불(used)", items.slice(0, 3).map((x) => [x.kind, x.why, x.amount]),
     [["refund", "early", -13410], ["subscription", null, 14900], ["refund", "used", -5940]]);
  eq("요금제 칸은 적힌 그대로(옛 내역은 basic)", items.slice(0, 3).map((x) => x.plan), ["member", "member", "basic"]);
  eq("시각은 화면이 읽는 글자", [items[0].createdAt, readableAt(items[0].createdAt)], ["2026-11-04T05:00:01.000Z", true]);
  eq("결제 식별자 · 한국어 설명 문장이 나가지 않는다",
     items.every((x) => !("paymentKey" in x) && !("orderId" in x) && !("description" in x)), true);
  const none = await call("listPayments", {}, { uid: null });
  eq("로그인하지 않으면 unauthenticated", none.error && none.error.code, "unauthenticated");
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
