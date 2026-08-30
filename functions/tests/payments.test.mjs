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
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

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
  amount: 9900, description: "BASIC 월 구독", kind: "subscription",
  status: "paid", plan: "basic",
  paymentKey: "tviva20260830", orderId: "kosai_new_abc123_xyz",
  paidAt: "2026-08-30T05:00:00.000Z", createdAt: stamp("2026-08-30T05:00:01.000Z"),
});
eq("금액", row.amount, 9900);
eq("종류", row.kind, "subscription");
/* 토스 식별자는 나가면 안 된다. 화면이 쓸 일이 없고, 결제 건을 취소할 수
   있는 열쇠라 브라우저에 둘 이유가 없다. */
eq("결제 식별자는 안 나간다", "paymentKey" in row || "orderId" in row, false);
/* 설명 문장은 한국어로 굳어 있어 영어 화면에서 번역할 수가 없다. 화면은
   kind 로 문구를 만든다. */
eq("한국어 설명 문장도 안 나간다", "description" in row, false);

const refund = rowOf({ amount: -6237, kind: "refund", why: "used",
                       status: "refunded", plan: "basic", paidAt: null,
                       createdAt: stamp("2026-08-30T05:00:00.000Z") });
eq("환불은 음수", refund.amount, -6237);
eq("환불 사유가 실린다", refund.why, "used");
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

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
