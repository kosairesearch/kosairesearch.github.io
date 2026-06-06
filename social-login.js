/* ============================================================
   KOSAI — 카카오 / 네이버 로그인 (프론트엔드)
   ------------------------------------------------------------
   OAuth 2.0 인가코드(authorization code) 방식:
   1) 버튼 클릭 → 카카오/네이버 동의 화면으로 리다이렉트
   2) 동의 후 ?code=...&state=... 로 이 페이지에 복귀
   3) code 를 Cloud Functions(socialLogin)로 전송
   4) 서버가 토큰 검증 후 Firebase 커스텀 토큰 발급 → signInWithCustomToken
   클라이언트는 공개 키(REST/Client ID)만 사용하고, 비밀키는 서버에만 있습니다.
   ============================================================ */
import { app, auth, SOCIAL } from "./firebase-config.js";
import { signInWithCustomToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFunctions, httpsCallable } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

if(window.KOSi18n) window.KOSi18n.register({
  "소셜 로그인에 실패했습니다.":"Social sign-in failed.",
  "로그인 요청이 만료되었어요. 다시 시도해 주세요.":"Your sign-in request expired. Please try again.",
  "카카오·네이버 로그인은 앱 키 설정이 필요합니다. (firebase-config.js 참고)":"Kakao/Naver sign-in needs app keys to be configured (see firebase-config.js)."
});
const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

const AUTHORIZE = {
  kakao: "https://kauth.kakao.com/oauth/authorize",
  naver: "https://nid.naver.com/oauth2.0/authorize"
};

function ready(provider){
  if(provider === "kakao") return !SOCIAL.kakaoRestKey.startsWith("[");
  if(provider === "naver") return !SOCIAL.naverClientId.startsWith("[");
  return false;
}

function redirectToProvider(provider, next){
  const redirectUri = location.origin + location.pathname; // 예: https://.../Login.html
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
  sessionStorage.setItem("kos_social", JSON.stringify({ provider, next, nonce, redirectUri }));
  const clientId = provider === "kakao" ? SOCIAL.kakaoRestKey : SOCIAL.naverClientId;
  const url = `${AUTHORIZE[provider]}?response_type=code&client_id=${encodeURIComponent(clientId)}`
    + `&redirect_uri=${encodeURIComponent(redirectUri)}&state=${nonce}`;
  location.href = url;
}

async function completeLogin(code, returnedState, saved, onError){
  try{
    const fns = getFunctions(app, SOCIAL.functionsRegion);
    const call = httpsCallable(fns, "socialLogin");
    const { data } = await call({
      provider: saved.provider,
      code,
      redirectUri: saved.redirectUri,
      state: returnedState
    });
    await signInWithCustomToken(auth, data.token);
    location.href = saved.next || "Home.html";
  }catch(err){
    history.replaceState({}, "", location.pathname);
    onError && onError(T("소셜 로그인에 실패했습니다.") + " (" + (err.code || err.message || "") + ")");
  }
}

/* 페이지의 #kakaoBtn / #naverBtn 에 동작을 연결하고, OAuth 복귀를 처리합니다.
   opts.onError(msg)     : 오류 메시지 표시
   opts.requireAgree()   : (회원가입용) 약관 동의 확인 — false 면 진행 중단 */
export function wireSocialButtons(opts = {}){
  const { onError, requireAgree } = opts;
  const params = new URLSearchParams(location.search);
  const code = params.get("code");
  const returnedState = params.get("state");

  // 1) OAuth 복귀 처리
  if(code){
    let saved = null;
    try{ saved = JSON.parse(sessionStorage.getItem("kos_social") || "null"); }catch(e){}
    sessionStorage.removeItem("kos_social");
    if(saved && saved.nonce === returnedState){
      completeLogin(code, returnedState, saved, onError);
    }else{
      history.replaceState({}, "", location.pathname);
      onError && onError(T("로그인 요청이 만료되었어요. 다시 시도해 주세요."));
    }
    return;
  }

  // 2) 버튼 연결
  for(const [id, provider] of [["kakaoBtn", "kakao"], ["naverBtn", "naver"]]){
    const b = document.getElementById(id);
    if(!b) continue;
    b.addEventListener("click", () => {
      if(requireAgree && !requireAgree()) return;
      if(!ready(provider)){
        onError && onError(T("카카오·네이버 로그인은 앱 키 설정이 필요합니다. (firebase-config.js 참고)"));
        return;
      }
      redirectToProvider(provider, params.get("next") || "");
    });
  }
}
