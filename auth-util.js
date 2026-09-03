/* ============================================================
   KOSAI — 로그인·회원가입 공용 유틸
   ------------------------------------------------------------
   로그인 화면이 세 개(Login·Signup·게이트 팝업)라 같은 판단이 세 군데에
   흩어져 있었다. 한 군데만 고치면 나머지가 남는다. 여기 모은다.

     safeNext()      로그인 뒤 어디로 보낼지 — 우리 사이트 안으로만
     goNext()        그 주소로 이동
     nextParam()     지금 페이지를 next 로 붙일 때 쓰는 값
     mapAuthError()  Firebase 오류 코드를 사람이 읽는 문장으로
   ============================================================ */

if (window.KOSi18n) window.KOSi18n.register({
  "이메일 또는 비밀번호가 올바르지 않습니다.": "Incorrect email or password.",
  "이메일 형식이 올바르지 않습니다.": "That email address doesn't look right.",
  "비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.":
    "Your password must be at least 8 characters and include letters and numbers.",
  "이미 가입된 이메일입니다.": "That email is already registered.",
  "요청이 많아 잠시 막혔습니다. 잠시 후 다시 시도하여 주시기 바랍니다.":
    "Too many attempts. Please try again in a moment.",
  "이 이메일은 다른 방법으로 가입되어 있습니다. 아래 버튼 중 처음 가입하실 때 쓰신 것으로 로그인하여 주시기 바랍니다.":
    "This email is registered with a different sign-in method. Please use the one you signed up with.",
  "네트워크 연결을 확인하여 주시기 바랍니다.": "Please check your network connection.",
  "이 계정은 사용이 중지되었습니다. hello@kosai.kr로 문의하여 주시기 바랍니다.":
    "This account has been disabled. Please contact hello@kosai.kr.",
  "보안을 위해 다시 로그인하신 뒤 진행하여 주시기 바랍니다.":
    "For security, please sign in again and then continue.",
  "로그인 창이 닫혔습니다. 다시 시도하여 주시기 바랍니다.":
    "The sign-in window was closed. Please try again.",
  "브라우저가 팝업을 막았습니다. 팝업을 허용하신 뒤 다시 시도하여 주시기 바랍니다.":
    "Your browser blocked the popup. Please allow popups and try again.",
  "Firebase 설정이 필요합니다. firebase-config.js를 확인하여 주시기 바랍니다.":
    "Firebase needs to be configured (see firebase-config.js).",
  "처리 중 오류가 발생했습니다.": "Something went wrong."
});

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

/* 우리 사이트 안의 페이지 이름만 허용한다. 하위 폴더는 한 단계까지
   (리포트가 r/005930.html 에 있다). */
const NEXT_OK = /^[A-Za-z0-9 _.\-]+(\/[A-Za-z0-9 _.\-]+)?\.html(\?[^#]*)?(#[^#]*)?$/;

/* 로그인 뒤 돌아갈 주소.

   전에는 ?next= 를 그대로 location.href 에 넣었다. Login.html?next=https://…
   로 링크를 만들면 우리 로그인 화면을 거쳐 남의 사이트로 보낼 수 있다는
   뜻이다. 피싱에 그대로 쓰인다 — 주소창에 kosai.kr 이 찍힌 채로 로그인을
   시키고 다른 데로 넘긴다.

   그래서 우리 사이트 안의 .html 하나만 통과시킨다. 프로토콜이 붙은 것,
   //로 시작하는 것, 상위 폴더로 올라가는 것은 전부 홈으로 보낸다. */
export function safeNext(raw) {
  let v = raw;
  if (v == null) {
    try { v = new URLSearchParams(location.search).get("next"); } catch (_) { v = null; }
  }
  if (!v) return "Home.html";
  let s = String(v);
  try { s = decodeURIComponent(s); } catch (_) { /* 잘못 인코딩된 값 — 원문으로 본다 */ }
  s = s.trim();
  if (!s) return "Home.html";
  if (/^[a-z][a-z0-9+.\-]*:/i.test(s)) return "Home.html";   // http: javascript: data: …
  if (s.startsWith("//") || s.startsWith("\\")) return "Home.html";
  if (s.startsWith("/")) s = s.slice(1);
  if (s.includes("\\") || s.includes("..")) return "Home.html";
  return NEXT_OK.test(s) ? s : "Home.html";
}

export function goNext(raw) { location.href = safeNext(raw); }

/* 지금 페이지를 ?next= 로 넘길 때 쓰는 값. 로그인 화면 자신은 넘기지
   않는다 — 로그인하면 다시 로그인 화면으로 돌아오는 고리가 된다. */
export function nextParam() {
  let page = "Home.html";
  try { page = decodeURIComponent(location.pathname.split("/").pop() || "Home.html"); }
  catch (_) { page = location.pathname.split("/").pop() || "Home.html"; }
  if (/^(login|signup)\.html$/i.test(page)) return "";
  return encodeURIComponent(page + (location.search || ""));
}

/* Firebase 오류를 사람이 읽는 문장으로.

   전에는 화면마다 따로 매핑했고, 그래서 화면마다 아는 코드가 달랐다.
   가장 큰 구멍이 account-exists-with-different-credential 이었다 —
   이메일로 가입한 사람이 구글 버튼을 누르면 이 코드가 오는데 아무 화면도
   이걸 몰라서 "오류가 발생했습니다 (알 수 없는 코드)" 만 뜨고 끝났다.
   사용자는 뭘 해야 할지 알 수 없어 그대로 막힌다. */
export function mapAuthError(err) {
  const c = String((err && (err.code || err.message)) || "");
  const has = s => c.includes(s);

  if (has("api-key") || has("configuration-not-found") || has("operation-not-allowed"))
    return T("Firebase 설정이 필요합니다. firebase-config.js를 확인하여 주시기 바랍니다.");
  if (has("account-exists-with-different-credential") || has("email-already-in-use") && has("credential"))
    return T("이 이메일은 다른 방법으로 가입되어 있습니다. 아래 버튼 중 처음 가입하실 때 쓰신 것으로 로그인하여 주시기 바랍니다.");
  if (has("email-already-in-use")) return T("이미 가입된 이메일입니다.");
  if (has("invalid-credential") || has("wrong-password") || has("user-not-found"))
    return T("이메일 또는 비밀번호가 올바르지 않습니다.");
  if (has("invalid-email")) return T("이메일 형식이 올바르지 않습니다.");
  if (has("weak-password")) return T("비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.");
  if (has("too-many-requests")) return T("요청이 많아 잠시 막혔습니다. 잠시 후 다시 시도하여 주시기 바랍니다.");
  if (has("network-request-failed")) return T("네트워크 연결을 확인하여 주시기 바랍니다.");
  if (has("user-disabled")) return T("이 계정은 사용이 중지되었습니다. hello@kosai.kr로 문의하여 주시기 바랍니다.");
  if (has("requires-recent-login")) return T("보안을 위해 다시 로그인하신 뒤 진행하여 주시기 바랍니다.");
  if (has("popup-blocked")) return T("브라우저가 팝업을 막았습니다. 팝업을 허용하신 뒤 다시 시도하여 주시기 바랍니다.");
  if (has("popup-closed") || has("cancelled-popup")) return T("로그인 창이 닫혔습니다. 다시 시도하여 주시기 바랍니다.");
  return T("처리 중 오류가 발생했습니다.") + (err && err.code ? " (" + err.code + ")" : "");
}

/* 사용자가 취소한 것이라 화면에 빨간 오류를 띄울 일이 아닌 경우. */
export function isUserCancelled(err) {
  const c = String((err && err.code) || "");
  return c.includes("popup-closed") || c.includes("cancelled-popup") || c.includes("user-cancelled");
}
