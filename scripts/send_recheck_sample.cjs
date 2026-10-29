/* 마케팅 수신 동의 2년 재확인 메일 시험 발송 — 관리자 주소(hello@kosai.kr)로 한 통 (2026-10-29)
   ------------------------------------------------------------
   Actions → 📧 수신거부 메일 시험 발송(mail_sample.yml)이 돌린다. 사장 "hello@kosai.kr 로 메일 보내봐. 수신거부링크
   누르면 되나 안되나 보게".

   함수 파일(functions/index.js)을 그대로 불러 관리자 함수 adminMarketingRecheck 의 시험 발송(sample)을 돌린다 — 메일 ·
   수신거부 링크 · 표를 실제 발송과 같은 코드로 만든다(sendRecheckSample). 받는 주소는 관리자 주소로 정해져 있다(입력을
   받지 않는다). 링크를 누르면 그 관리자 계정의 마케팅 수신 동의가 실제로 철회된다 — 설정 화면에서 다시 켤 수 있다.

   실행 기록은 공개라 링크 · 표 · 회원 번호를 찍지 않는다. 서비스 계정(GOOGLE_APPLICATION_CREDENTIALS)과
   RESEND_API_KEY 가 있어야 한다.
     node scripts/send_recheck_sample.cjs
   ============================================================ */
const path = require("path");

const FN = path.join(__dirname, "..", "functions");
const ADMIN = "hello@kosai.kr";

(async () => {
  // 함수 파일과 같은 관리자 SDK(functions/node_modules)를 쓴다 — 함수 파일이 불러질 때 initializeApp() 을 한다.
  const admin = require(require.resolve("firebase-admin", { paths: [FN] }));
  const fns = require(path.join(FN, "index.js"));
  const user = await admin.auth().getUserByEmail(ADMIN);
  const r = await fns.adminMarketingRecheck.run({
    auth: { uid: user.uid, token: { email: user.email, email_verified: user.emailVerified } },
    data: { sample: true },
    rawRequest: { headers: { "user-agent": "github-actions mail_sample.yml" } },
  });
  if (!r || r.sent !== true) {
    console.log(`보내지 못했다 — ${(r && r.reason) === "no-user-doc" ? "관리자 계정의 회원 문서가 없다" : JSON.stringify(r)}`);
    process.exit(1);
  }
  console.log(`시험 메일을 ${ADMIN} 로 보냈다(제목 앞 [시험]).`);
  console.log(r.marketing
    ? "이 계정은 마케팅 수신 동의가 켜져 있다 — 링크에서 '수신 거부하기'를 누르면 동의가 철회되고 '수신 거부가 완료되었습니다'가 나온다."
    : "이 계정은 마케팅 수신 동의가 꺼져 있다 — 링크에서 '수신 거부하기'를 누르면 '이미 수신 거부된 상태입니다'가 나온다.");
})().catch((e) => {
  console.error(`실패 — ${(e && e.code) || ""} ${(e && e.message) || e}`);
  process.exit(1);
});
