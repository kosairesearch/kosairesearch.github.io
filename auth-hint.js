/* ============================================================
   KOSAI — "왜 로그인이 안 되는지" 안내
   ------------------------------------------------------------
   같은 이메일 주소라도 가입한 방법이 다르면 로그인 방법도 다르다.
   네이버로 가입한 사람이 이메일·비밀번호 칸에 입력하면 비밀번호가 틀린 게
   아니라 애초에 비밀번호가 없는 계정이다. 그런데 화면은 '이메일 또는
   비밀번호가 올바르지 않습니다' 만 보여 줬다 — 몇 번을 다시 쳐도 안 된다.

   문구를 한 곳에 둔다. 로그인 화면과 가입 화면이 같은 상황을 다른 말로
   설명하면 그것대로 혼란스럽다.

   문구를 고를 때 지킨 것
     · 무엇이 문제인지 한 문장, 무엇을 하면 되는지 한 문장.
     · 화면에 실제로 있는 버튼 이름을 그대로 부른다("네이버로 계속하기").
       '소셜 로그인을 이용해 주세요' 같은 말은 어느 것을 누르라는 건지
       알려 주지 않는다.
     · 사과하거나 변명하지 않는다. 사용자가 잘못한 일이 아니다.
   ============================================================ */
import { app, SOCIAL } from "./firebase-config.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

if (window.KOSi18n) window.KOSi18n.register({
  "Google 계정으로 가입된 이메일입니다.": "This email is registered with Google.",
  "카카오 계정으로 가입된 이메일입니다.": "This email is registered with Kakao.",
  "네이버 계정으로 가입된 이메일입니다.": "This email is registered with Naver.",
  "이미 가입된 이메일입니다.": "This email is already registered.",
  "위의 Google로 계속하기를 눌러 로그인해 주세요.":
    "Use “Continue with Google” above to sign in.",
  "위의 카카오로 계속하기를 눌러 로그인해 주세요.":
    "Use “Continue with Kakao” above to sign in.",
  "위의 네이버로 계속하기를 눌러 로그인해 주세요.":
    "Use “Continue with Naver” above to sign in.",
  "위의 Google로 계속하기를 눌러 주세요.": "Use “Continue with Google” above.",
  "위의 카카오로 계속하기를 눌러 주세요.": "Use “Continue with Kakao” above.",
  "위의 네이버로 계속하기를 눌러 주세요.": "Use “Continue with Naver” above.",
  "로그인하러 가기": "Go to sign in"
});

/* 가입 방법별 문구. login/signup 두 상황에서 뒷문장만 다르다. */
const HINT = {
  google: { head: "Google 계정으로 가입된 이메일입니다.",
            login: "위의 Google로 계속하기를 눌러 로그인해 주세요.",
            signup: "위의 Google로 계속하기를 눌러 주세요." },
  kakao:  { head: "카카오 계정으로 가입된 이메일입니다.",
            login: "위의 카카오로 계속하기를 눌러 로그인해 주세요.",
            signup: "위의 카카오로 계속하기를 눌러 주세요." },
  naver:  { head: "네이버 계정으로 가입된 이메일입니다.",
            login: "위의 네이버로 계속하기를 눌러 로그인해 주세요.",
            signup: "위의 네이버로 계속하기를 눌러 주세요." },
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

/* 안내 문구를 box 에 그린다. 그릴 것이 있으면 true.
   mode: "login"  — 로그인 화면에서 비밀번호가 안 맞을 때
         "signup" — 가입 화면에서 이미 있는 주소일 때 */
export function renderHint(box, method, mode) {
  const h = HINT[method];
  if (!h) return false;
  box.textContent = "";
  const b = document.createElement("div");
  b.style.fontWeight = "600";
  b.textContent = T(h.head);
  const p = document.createElement("div");
  p.style.cssText = "margin-top:4px;font-weight:400;opacity:.9";
  p.textContent = T(h[mode] || h.login);
  box.appendChild(b);
  box.appendChild(p);
  box.style.display = "block";
  return true;
}
