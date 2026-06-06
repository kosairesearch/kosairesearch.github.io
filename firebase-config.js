/* ============================================================
   KOS ai — Firebase 초기화 (로그인/회원가입 공용 모듈)
   ------------------------------------------------------------
   ▶ 설정 방법
   1) Firebase 콘솔(https://console.firebase.google.com)에서 프로젝트 생성
   2) 빌드 → Authentication → 시작하기 → 로그인 방법에서
      "이메일/비밀번호"와 "Google" 사용 설정
   3) Authentication → 설정 → 승인된 도메인에
      kosairesearch.github.io 추가 (로컬 테스트 시 localhost 도 추가)
   4) 프로젝트 설정 → 일반 → 내 앱(웹) → SDK 설정/구성에서
      아래 firebaseConfig 값을 복사해 [PLACEHOLDER] 자리를 교체

   ▶ Kakao / Naver
   카카오·네이버는 Firebase 기본 공급자가 아니므로, Firebase 계정과
   통합하려면 Identity Platform(OIDC) 또는 커스텀 토큰 발급용 백엔드
   (Cloud Functions)가 추가로 필요합니다. 키는 아래 SOCIAL 에 둡니다.
   ============================================================ */
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = {
  apiKey: "[FIREBASE_API_KEY]",
  authDomain: "[FIREBASE_AUTH_DOMAIN]",        // 예: kos-ai.firebaseapp.com
  projectId: "[FIREBASE_PROJECT_ID]",
  appId: "[FIREBASE_APP_ID]"
};

// 카카오/네이버 클라이언트 키 (설정 후 사용)
export const SOCIAL = {
  kakaoJsKey: "[KAKAO_JAVASCRIPT_KEY]",
  naverClientId: "[NAVER_CLIENT_ID]",
  naverCallbackUrl: "[NAVER_CALLBACK_URL]"      // 예: https://kosairesearch.github.io/Login.html
};

// 설정이 아직 안 된 상태인지 확인 (UI에서 안내용으로 사용)
export const isConfigured = !firebaseConfig.apiKey.startsWith("[");

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
auth.languageCode = "ko";
