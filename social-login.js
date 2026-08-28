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
  let url = `${AUTHORIZE[provider]}?response_type=code&client_id=${encodeURIComponent(clientId)}`
    + `&redirect_uri=${encodeURIComponent(redirectUri)}&state=${nonce}`;

  /* 가입 화면에서 누른 네이버는 동의 화면을 다시 띄운다.

     한 번 연결하면 네이버는 그 뒤로 동의 화면을 건너뛴다. 탈퇴하고 다시
     가입해도 마찬가지라, 무엇에 동의하는지 못 본 채 계정이 만들어진다.
     카카오는 탈퇴할 때 서버가 연결을 끊어 해결했는데(어드민 키), 네이버에는
     그런 창구가 없다 — 대신 authorize 에 auth_type=reprompt 를 붙이면
     그 자리에서 동의 화면이 다시 뜬다.

     로그인 화면에서는 붙이지 않는다. 매번 동의를 다시 묻는 꼴이 된다.
     가입은 처음 한 번이니 거기서만 묻는다. */
  if(provider === "naver" && /Signup\.html$/i.test(location.pathname)){
    url += "&auth_type=reprompt";
  }
  location.href = url;
}

async function completeLogin(code, returnedState, saved, onError){
  try{
    const fns = getFunctions(app, SOCIAL.functionsRegion);
    const call = httpsCallable(fns, "socialLogin");
    const payload = {
      provider: saved.provider,
      code,
      redirectUri: saved.redirectUri,
      state: returnedState
    };

    /* 우리 동의 화면을 띄우지 않는다.
       카카오·네이버는 자기 동의 화면을 이미 보여 준다(카카오 '연결된 서비스',
       네이버 '외부 사이트 연결' 에서 확인된다). 거기에 우리 화면을 한 번 더
       얹으면 같은 걸 두 번 묻는 셈이다.

       대신 버튼 아래 고지 문구로 받고, 서버가 계정을 만들면서 같은 호출 안에
       동의를 기록한다(method: "signup-notice"). 기록에 실패하면 계정도
       만들지 않는다. */
    const { data } = await call(payload);
    if(!data || !data.token) throw new Error("가입을 마치지 못했습니다.");

    await signInWithCustomToken(auth, data.token);
    location.href = saved.next || "Home.html";
  }catch(err){
    history.replaceState({}, "", location.pathname);
    /* 같은 이메일을 쓰는 계정이 이미 있어 서버가 만들지 않은 경우.
       코드만 붙여 내보내면 무슨 일인지 알 수 없다 — 서버가 보낸 문장을
       그대로 보여 준다("이미 이메일로 가입된 이메일입니다." 같은 형태다). */
    /* 같은 이메일을 쓰는 계정이 이미 있어 서버가 만들지 않은 경우.
       서버 문장을 그대로 내보내면 길고 한국어뿐이라 화면과 어긋난다.
       서버가 details.method 로 어느 방법인지 알려 주므로 문구는 여기서
       만든다 — 로그인·가입 화면과 같은 한 줄을 쓴다. */
    const code = String((err && err.code) || "");
    if(code.indexOf("already-exists") >= 0){
      let msg = "";
      try{
        const { hintText } = await import("./auth-hint.js");
        msg = hintText((err && err.details && err.details.method) || "");
      }catch(_){}
      onError && onError(msg || err.message || T("이미 다른 방법으로 가입된 이메일입니다."));
      return;
    }
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
