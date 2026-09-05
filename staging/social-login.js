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
import { app, auth, SOCIAL } from "./firebase-config.js?v=7b8f27a5";
import { safeNext } from "./auth-util.js?v=0ad15dc5";
import { signInWithCustomToken } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFunctions, httpsCallable } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

if(window.KOSi18n) window.KOSi18n.register({
  "소셜 로그인에 실패했습니다.":"Social sign-in failed.",
  "이미 다른 방법으로 가입된 이메일입니다.":"This email is already registered with a different sign-in method.",
  "로그인 요청이 만료되었습니다. 다시 시도하여 주시기 바랍니다.":"Your sign-in request expired. Please try again.",
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

/* 제공자로 보낸다. 카카오도 네이버도 한 번만 거친다.

   ■ 없어진 것 — 네이버 auth_type=reprompt 왕복

   한동안 네이버에는 왕복이 하나 있었다. 처음에는 그냥 보내고, 서버가
   '계정을 만들어야 하는데 동의를 못 받았다'(needsConsent) 고 하면
   auth_type=reprompt 를 붙여 한 번 더 보냈다. 그래야 동의 화면이 떴다.

   왜 그랬나. 탈퇴해도 네이버 쪽 연결이 남아서, 다시 가입할 때 네이버가
   동의를 묻지 않고 곧장 통과시켰기 때문이다. 무엇에 동의하는지 못 본 채
   계정이 만들어지는 것을 막으려고 억지로 화면을 띄웠다.

   왜 없앴나. 뿌리를 고쳤다. 이제 탈퇴할 때 서버가 네이버 연결을 끊는다
   (naverUnlink). 연결이 없으면 다음 로그인은 첫 연결이므로 네이버가 알아서
   동의 화면을 띄운다 — 카카오와 똑같아졌다.

   왕복을 남겨 두면 그 화면을 두 번 보게 된다. 실제로 그랬다. 끊긴 연결이라
   1차에서 이미 동의 화면이 뜨는데, 서버가 '아직 동의 기록이 없다' 며
   needsConsent 를 돌려주니 2차에서 또 띄웠다. 뿌리를 고치고도 땜질을
   남겨 두면 그 땜질이 새 증상이 된다.

   연결 끊기가 실패한 계정은 동의 화면이 안 뜰 수 있다. 그때는 서버가
   제공자 동의 시각을 탈퇴 시각과 견주어 걸러 내고(staleConsent) 우리 동의
   화면으로 보낸다. 막다른 길이 아니라 물러설 자리가 있다. */
function redirectToProvider(provider, next){
  const redirectUri = location.origin + location.pathname; // 예: https://.../Login.html
  const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
  sessionStorage.setItem("kos_social",
    JSON.stringify({ provider, next, nonce, redirectUri }));
  const clientId = provider === "kakao" ? SOCIAL.kakaoRestKey : SOCIAL.naverClientId;
  const url = `${AUTHORIZE[provider]}?response_type=code&client_id=${encodeURIComponent(clientId)}`
    + `&redirect_uri=${encodeURIComponent(redirectUri)}&state=${nonce}`;
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
    /* 돌아갈 곳은 반드시 safeNext 를 거친다.

       여기만 그냥 쓰고 있었다. next 는 주소에 실려 오는 값이라
       Login.html?next=https://남의사이트 로 링크를 만들면, 카카오·네이버로
       로그인한 사람이 우리 주소에서 시작해 남의 사이트로 넘어간다. 이메일·
       구글 경로는 goNext() 를 거쳐 막혀 있었는데 이 길만 열려 있었다. */
    location.href = safeNext(saved.next);
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

  /* 1) 버튼부터 연결한다.

     전에는 OAuth 복귀 처리를 먼저 하고 return 으로 끝냈다. 그래서 제공자
     화면에서 돌아와 실패한 순간 세 버튼이 전부 죽었다 — 오류 문구는
     떠 있는데 아무 버튼도 안 눌리고, 새로고침해야만 살아났다.

     실패했을 때야말로 다른 방법을 눌러 봐야 하는 순간이다. 그 자리에서
     버튼을 죽이면 사용자는 화면이 고장 난 줄 안다. 연결을 먼저 한다. */
  for(const [id, provider] of [["kakaoBtn", "kakao"], ["naverBtn", "naver"]]){
    const b = document.getElementById(id);
    if(!b) continue;
    b.addEventListener("click", () => {
      if(requireAgree && !requireAgree()) return;
      if(!ready(provider)){
        onError && onError(T("카카오·네이버 로그인은 앱 키 설정이 필요합니다. (firebase-config.js 참고)"));
        return;
      }
      /* 처음에는 동의 화면 없이 보낸다. 필요하면 서버가 알려 준다. */
      redirectToProvider(provider, params.get("next") || "", false);
    });
  }

  // 2) OAuth 복귀 처리
  if(code){
    let saved = null;
    try{ saved = JSON.parse(sessionStorage.getItem("kos_social") || "null"); }catch(e){}
    sessionStorage.removeItem("kos_social");
    /* 주소에서 code 를 지운다. 남겨 두면 새로고침할 때 같은 코드로 다시
       시도하게 되는데, 인가 코드는 한 번만 쓸 수 있어 늘 실패한다. */
    history.replaceState({}, "", location.pathname);
    if(saved && saved.nonce === returnedState){
      completeLogin(code, returnedState, saved, onError);
    }else{
      onError && onError(T("로그인 요청이 만료되었습니다. 다시 시도하여 주시기 바랍니다."));
    }
  }
}
