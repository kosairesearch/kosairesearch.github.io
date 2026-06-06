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
   카카오·네이버는 Firebase 기본 공급자가 아니므로, Cloud Functions 백엔드가
   카카오/네이버 인증을 검증하고 Firebase 커스텀 토큰을 발급합니다(functions/ 참고).
   클라이언트에는 "공개 키"만 두고(아래 SOCIAL), 비밀키는 서버(Functions)에만 둡니다.
   배포·키 발급 절차는 저장소 루트의 SETUP.md 를 참고하세요.
   ============================================================ */
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAuth } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = {
  apiKey: "[FIREBASE_API_KEY]",
  authDomain: "[FIREBASE_AUTH_DOMAIN]",        // 예: kos-ai.firebaseapp.com
  projectId: "[FIREBASE_PROJECT_ID]",
  appId: "[FIREBASE_APP_ID]"
};

// 카카오/네이버 공개 키 (authorize 요청용 — 비밀키는 Functions 서버에만 둡니다)
export const SOCIAL = {
  kakaoRestKey: "[KAKAO_REST_API_KEY]",   // 카카오 REST API 키 (공개)
  naverClientId: "[NAVER_CLIENT_ID]",      // 네이버 Client ID (공개)
  functionsRegion: "asia-northeast3"        // Cloud Functions 배포 리전 (서울)
};

// 소셜(카카오/네이버) 설정 완료 여부
export const socialReady =
  !SOCIAL.kakaoRestKey.startsWith("[") || !SOCIAL.naverClientId.startsWith("[");

// 설정이 아직 안 된 상태인지 확인 (UI에서 안내용으로 사용)
export const isConfigured = !firebaseConfig.apiKey.startsWith("[");

export const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
auth.languageCode = "ko";
