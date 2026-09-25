/* ============================================================
   KOSAI — "왜 로그인이 안 되는지" 안내
   ------------------------------------------------------------
   같은 이메일 주소라도 가입한 방법이 다르면 로그인 방법도 다르다.
   네이버로 가입한 사람이 이메일·비밀번호 칸에 입력하면 비밀번호가 틀린 게
   아니라 애초에 비밀번호가 없는 계정이다. 그런데 화면은 '이메일 또는
   비밀번호가 올바르지 않습니다' 만 보여 줬다 — 몇 번을 다시 쳐도 안 된다.

   문구를 한 곳에 둔다. 로그인 화면과 가입 화면이 같은 상황을 다른 말로
   설명하면 그것대로 혼란스럽다.

   한 줄이면 된다.

     네이버 계정으로 가입된 이메일입니다.

   처음에는 '위의 네이버로 계속하기를 눌러 로그인하여 주시기 바랍니다.' 를 덧붙였다.
   빼는 편이 낫다 — 소셜 버튼 셋이 바로 위에 보이는 화면이라, 어느 것을
   누를지는 이 한 줄로 이미 분명하다. 시키는 말을 더 얹으면 문장만 길어진다.
   ============================================================ */
import { app, SOCIAL } from "./firebase-config.js?v=7b8f27a5";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

if (window.KOSi18n) window.KOSi18n.register({
  "Google 계정으로 가입된 이메일입니다.": "This email is registered with Google.",
  "카카오 계정으로 가입된 이메일입니다.": "This email is registered with Kakao.",
  "네이버 계정으로 가입된 이메일입니다.": "This email is registered with Naver."
});

const HINT = {
  google: "Google 계정으로 가입된 이메일입니다.",
  kakao: "카카오 계정으로 가입된 이메일입니다.",
  naver: "네이버 계정으로 가입된 이메일입니다.",
};

/* 이 주소가 어느 방법으로 가입됐는지 묻는다. 모르면 null.
   실패해도 던지지 않는다 — 안내는 부가 기능이라, 이것 때문에 로그인 화면이
   멈추면 안 된다. */
export async function signinMethod(email) {
  try {
    const fns = getFunctions(app, (SOCIAL && SOCIAL.functionsRegion) || "asia-northeast3");
    const { data } = await httpsCallable(fns, "signinHint")({ email: email || "" });
    return (data && data.method) || null;
  } catch (e) { return null; }
}

/* 문구만 돌려준다. 오류 메시지처럼 문자열 한 개만 받는 자리에서 쓴다
   (소셜 로그인은 서버가 보낸 문장을 그대로 내보내고 있었다 — 서버 문장은
   길고 한국어뿐이라 화면과 어긋났다). 모르면 빈 문자열. */
export function hintText(method) {
  return HINT[method] ? T(HINT[method]) : "";
}

/* 안내 문구를 box 에 그린다. 그릴 것이 있으면 true. */
export function renderHint(box, method) {
  const line = HINT[method];
  if (!line) return false;
  box.textContent = T(line);
  box.style.display = "block";
  return true;
}
