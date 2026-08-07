/* ============================================================
   KOSAI — 인증/비밀번호 메일 발송 호출 (Cloud Functions)
   ------------------------------------------------------------
   Firebase 기본 메일(본문 수정 불가) 대신, 백엔드 함수가
   링크를 생성해 Resend 로 우리 디자인의 메일을 발송합니다.
   서버: functions/index.js → sendVerifyEmail / sendResetEmail
   ============================================================ */
import { app, SOCIAL } from "./firebase-config.js";
import { getFunctions, httpsCallable } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const fns = getFunctions(app, SOCIAL.functionsRegion);

// 현재 사이트 언어(localStorage 'kos-lang') → 메일 언어로 전달
function curLang(){
  try{ return localStorage.getItem("kos-lang") === "en" ? "en" : "ko"; }
  catch(e){ return "ko"; }
}

export async function sendVerifyEmail(email){
  await httpsCallable(fns, "sendVerifyEmail")({ email: email || "", lang: curLang() });
}

export async function sendResetEmail(email){
  await httpsCallable(fns, "sendResetEmail")({ email: email || "", lang: curLang() });
}
