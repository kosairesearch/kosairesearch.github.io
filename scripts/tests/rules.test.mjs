/* ============================================================
   파이어스토어 접근 규칙 검사 — 남의 것을 볼 수 있는가

   왜 있는가. 규칙은 화면과 서버 사이에 있는 마지막 문이다. 여기가 열려
   있으면 앞의 검사를 아무리 통과해도 소용이 없다 — 브라우저 콘솔을 열
   수 있는 사람은 누구나 문서를 직접 읽고 쓸 수 있다.

   그런데 규칙은 눈으로 봐서는 맞는지 알기 어렵다. 예를 들어 delete 는
   allow write 에 들어가는데 그때 request.resource 가 null 이라, 쓰기에
   모양 검사를 붙이면 삭제가 같이 막힌다. 읽어서는 안 보이고 돌려 봐야
   보인다.

   구독 규칙이 통째로 빠져 있던 적이 있다. 화면은 조용히 실패했고
   (paywall 이 sub = null 로 삼켰다) 돈을 낸 사람이 '무료 이용 중' 으로
   보이는 자리였다. 규칙은 없으면 막히고, 막히면 화면이 조용해진다.

   실행
     npm install --no-save firebase-tools @firebase/rules-unit-testing
     node scripts/tests/rules.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { initializeTestEnvironment, assertFails, assertSucceeds }
  from "@firebase/rules-unit-testing";
import {
  doc, getDoc, setDoc, updateDoc, deleteDoc, collection, getDocs, deleteField,
} from "firebase/firestore";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

let pass = 0, fail = 0;
const ok = (c, m, d = "") => { c ? (pass++, console.log("  ✔", m, d)) : (fail++, console.log("  ✘", m, d)); };
async function can(p, m) { try { await assertSucceeds(p); ok(true, m); } catch (e) { ok(false, m, String(e).slice(0, 90)); } }
async function cannot(p, m) { try { await assertFails(p); ok(true, m); } catch (e) { ok(false, m, "막혔어야 하는데 통과했다"); } }

const env = await initializeTestEnvironment({
  projectId: "kosai-rules-test",
  firestore: { rules: readFileSync(join(ROOT, "firestore.rules"), "utf8"), host: "127.0.0.1", port: 8080 },
});

const me = env.authenticatedContext("me").firestore();
const other = env.authenticatedContext("other").firestore();
const anon = env.unauthenticatedContext().firestore();

/* 서버(Admin SDK)가 미리 넣어 둔 자료. 규칙을 지나간다. */
await env.withSecurityRulesDisabled(async (c) => {
  const db = c.firestore();
  await setDoc(doc(db, "users/me"), { email: "me@x.com", consents: { version: 1 } });
  await setDoc(doc(db, "users/other"), { email: "other@x.com" });
  await setDoc(doc(db, "subscriptions/me"), { plan: "basic", status: "active" });
  await setDoc(doc(db, "subscriptions/other"), { plan: "pro", status: "active" });
  await setDoc(doc(db, "watchlists/me"), { items: { "005930": 1 } });
  await setDoc(doc(db, "watchlists/other"), { items: { "000660": 1 } });
  await setDoc(doc(db, "consentEvents/e1"), { uid: "me" });
  await setDoc(doc(db, "payments/me/list/p1"), { amount: 9900, paymentKey: "secret" });
  await setDoc(doc(db, "report_reads/me_2026-09-04"), { uid: "me", n: 3 });
  await setDoc(doc(db, "reports_paid/005930"), { body: "유료 본문" });
  await setDoc(doc(db, "providerTokens/me"), { refreshToken: "비밀" });
  await setDoc(doc(db, "mailQuota/reset_abc"), { h: { n: 3, at: 1 } });
});

console.log("\n── ① 워치리스트 — 본인 것만 ──");
await can(getDoc(doc(me, "watchlists/me")), "본인 것을 읽는다");
await can(setDoc(doc(me, "watchlists/me"), { items: { "005930": 1 } }), "본인 것을 쓴다");
await can(updateDoc(doc(me, "watchlists/me"), { "items.005930": deleteField() }), "한 종목만 지운다");
await can(deleteDoc(doc(me, "watchlists/me")), "문서째 지운다(탈퇴 때 쓴다)");
await cannot(getDoc(doc(me, "watchlists/other")), "남의 것은 못 읽는다");
await cannot(setDoc(doc(me, "watchlists/other"), { items: {} }), "남의 것에 못 쓴다");
await cannot(getDoc(doc(anon, "watchlists/me")), "로그인 안 하면 못 읽는다");
await cannot(getDocs(collection(me, "watchlists")), "목록째 훑지 못한다");

console.log("\n── ② 회원 문서 — 본인 읽기만, 쓰기는 아무도 ──");
await can(getDoc(doc(me, "users/me")), "본인 것을 읽는다(설정 화면이 쓴다)");
await cannot(getDoc(doc(me, "users/other")), "남의 동의 기록은 못 읽는다");
await cannot(getDoc(doc(anon, "users/me")), "로그인 안 하면 못 읽는다");
await cannot(setDoc(doc(me, "users/me"), { consents: { age14: true } }), "본인도 못 쓴다(동의 기록 위조 방지)");
await cannot(updateDoc(doc(me, "users/me"), { "consents.marketing": true }), "마케팅 동의를 직접 못 켠다");
await cannot(deleteDoc(doc(me, "users/me")), "본인도 못 지운다");
await cannot(getDocs(collection(me, "users")), "회원 목록을 훑지 못한다");

console.log("\n── ③ 구독 — 본인 읽기만 ──");
await can(getDoc(doc(me, "subscriptions/me")), "본인 것을 읽는다(화면이 실시간으로 본다)");
await cannot(getDoc(doc(me, "subscriptions/other")), "남의 구독은 못 읽는다");
await cannot(setDoc(doc(me, "subscriptions/me"), { plan: "pro", status: "active" }),
             "PRO 로 고쳐 쓰지 못한다(돈 안 내고 여는 길)");
await cannot(updateDoc(doc(me, "subscriptions/me"), { status: "active" }), "상태를 직접 못 바꾼다");

console.log("\n── ④ 아무에게도 열지 않은 자리 ──");
await cannot(getDoc(doc(me, "consentEvents/e1")), "동의 이력을 못 읽는다");
await cannot(setDoc(doc(me, "consentEvents/e2"), { uid: "me" }), "동의 이력을 못 만든다");
await cannot(getDoc(doc(me, "payments/me/list/p1")), "결제 내역을 못 읽는다(토스 식별자가 들어 있다)");
await cannot(getDoc(doc(me, "report_reads/me_2026-09-04")), "열람 기록을 못 읽는다");
await cannot(setDoc(doc(me, "report_reads/me_2026-09-04"), { n: 0 }), "열람 한도를 못 지운다");
await cannot(getDoc(doc(me, "reports_paid/005930")), "유료 리포트 본문을 못 읽는다");
await cannot(getDoc(doc(me, "providerTokens/me")), "제공자 토큰을 못 읽는다(본인도)");
await cannot(setDoc(doc(me, "providerTokens/me"), { refreshToken: "x" }), "제공자 토큰을 못 쓴다");
await cannot(getDoc(doc(me, "mailQuota/reset_abc")), "메일 발송 셈을 못 읽는다");
await cannot(setDoc(doc(me, "mailQuota/reset_abc"), { h: { n: 0, at: 0 } }),
             "메일 발송 셈을 못 지운다(지울 수 있으면 제한이 없는 것과 같다)");
await cannot(deleteDoc(doc(me, "mailQuota/reset_abc")), "메일 발송 셈 문서를 못 지운다");

console.log("\n── ⑤ 규칙에 없는 자리는 막힌다 ──");
await cannot(getDoc(doc(me, "무엇이든/x")), "규칙이 없는 컬렉션은 읽기가 막힌다");
await cannot(setDoc(doc(me, "무엇이든/x"), { a: 1 }), "규칙이 없는 컬렉션은 쓰기가 막힌다");
await cannot(getDoc(doc(me, "users/me/비밀/x")), "회원 문서 아래 하위 자리도 막힌다");

await env.cleanup();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
