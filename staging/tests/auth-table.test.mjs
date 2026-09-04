/* ============================================================
   로그인·회원가입 명세표가 실제와 맞는가 — 상태 10 × 동작 8

   왜 있는가. 로그인은 화면 넷(Login·Signup·Consent·auth-action)과 모듈
   다섯(auth-util·auth-state·auth-guard·social-login·consent)에 걸쳐 있다.
   한 화면만 보고 고치면 나머지가 남고, 남은 쪽은 사람이 그 경로를 밟기
   전까지 아무도 모른다. 실제로 그렇게 다섯 가지가 새어 있었다.

     ① auth-action.html 이 continueUrl 을 검사 없이 버튼 주소에 이어 붙였다
        — 남의 사이트로 보내지고, 따옴표를 닫으면 코드까지 돌았다
     ② social-login.js 만 safeNext 를 안 거쳤다 — 같은 열린 문이 하나 더
     ③ 비밀번호가 틀렸을 때 나오는 코드 하나를 문구 표가 몰랐다
        — 가장 흔한 실패에 'auth/invalid-login-credentials' 가 그대로 떴다
     ④ 계정 메뉴가 닉네임을 마크업으로 이어 붙였다
     ⑤ 이미 인증된 옛 회원이 동의를 마치면 로그아웃되고, 오지 않는
        인증 메일을 기다리게 됐다

   표를 코드로 옮겨 놓고 눌러 본다. 기대와 다르면 표가 틀렸거나 코드가
   틀렸거나 둘 중 하나다.

   실행
     node staging/tests/auth-table.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const read = f => readFileSync(join(ROOT, f), "utf8");

let pass = 0, fail = 0;
const ok = (cond, name, detail = "") => {
  if (cond) { pass++; console.log("  ✔", name, detail); }
  else { fail++; console.log("  ✘", name, detail); }
};
const eq = (got, want, name) =>
  ok(got === want, name, got === want ? "" : `← ${JSON.stringify(got)} (기대 ${JSON.stringify(want)})`);

/* ── auth-util.js 를 그대로 들여온다 ─────────────────────────
   브라우저 전역(window)만 채워 주면 그대로 돈다. 복사해 오지 않는다 —
   복사본은 진짜 파일이 바뀌어도 통과한다. */
globalThis.window = { KOSi18n: null };
const util = await import("file://" + join(ROOT, "auth-util.js"));
const { safeNext, mapAuthError, isUserCancelled, nextParam } = util;

/* ══════════════════════════════════════════════════════════
   1) 돌아갈 주소 — 우리 사이트 밖으로 나가지 않는가
   ══════════════════════════════════════════════════════════ */
console.log("\n── ① 돌아갈 주소(next·continueUrl) ──");

const NEXT_CASES = [
  // [이름, 넣는 값, 기대]
  ["평범한 페이지",            "Home.html",                    "Home.html"],
  ["쿼리가 붙은 페이지",       "stock.html?ticker=005930",     "stock.html?ticker=005930"],
  ["한 단계 하위 폴더",        "r/005930.html",                "r/005930.html"],
  ["앞의 슬래시는 떼고 통과",  "/Watchlist.html",              "Watchlist.html"],
  ["빈 값",                    "",                             "Home.html"],
  ["없음",                     null,                           "Home.html"],
  ["남의 사이트",              "https://evil.example.com",     "Home.html"],
  ["프로토콜 생략",            "//evil.example.com",           "Home.html"],
  ["javascript:",              "javascript:alert(1)",          "Home.html"],
  ["data:",                    "data:text/html,<b>x",          "Home.html"],
  ["대문자 프로토콜",          "JaVaScRiPt:alert(1)",          "Home.html"],
  ["인코딩된 프로토콜",        "%6a%61%76%61script:alert(1)",  "Home.html"],
  ["상위 폴더",                "../secret.html",               "Home.html"],
  ["중간에 상위 폴더",         "a/../../x.html",               "Home.html"],
  ["역슬래시",                 "\\\\evil.example.com",         "Home.html"],
  ["따옴표로 속성 탈출",       '" onfocus="alert(1)" autofocus x="', "Home.html"],
  ["태그 삽입",                '"><img src=x onerror=alert(1)>', "Home.html"],
  [".html 이 아님",            "Home.php",                     "Home.html"],
  ["앞뒤 공백",                "  Home.html  ",                "Home.html"],
];
for (const [name, input, want] of NEXT_CASES) eq(safeNext(input), want, `safeNext — ${name}`);

/* 로그인 화면 자신을 next 로 넘기면 고리가 된다 */
globalThis.location = { pathname: "/Login.html", search: "" };
eq(nextParam(), "", "nextParam — 로그인 화면은 자기를 넘기지 않는다");
globalThis.location = { pathname: "/Watchlist.html", search: "" };
eq(nextParam(), "Watchlist.html", "nextParam — 보통 페이지는 자기를 넘긴다");

/* ── 이동을 만드는 모든 자리가 safeNext 를 거치는가 ──
   값 하나만 새도 문 하나가 열린다. 파일을 훑어 확인한다. */
console.log("\n── ② 이동하는 자리가 전부 자물쇠를 거치는가 ──");
{
  const sl = read("social-login.js");
  ok(/location\.href\s*=\s*safeNext\(saved\.next\)/.test(sl),
     "social-login.js — 소셜 로그인 뒤 이동이 safeNext 를 거친다");
  ok(!/location\.href\s*=\s*saved\.next/.test(sl),
     "social-login.js — 검사 없이 넘기던 옛 줄이 남지 않았다");

  const aa = read("auth-action.html");
  ok(/const continueUrl = safeNext\(/.test(aa),
     "auth-action.html — continueUrl 이 safeNext 를 거친다");
  ok(!/const continueUrl = params\.get\('continueUrl'\)\s*\|\|/.test(aa),
     "auth-action.html — 검사 없이 받던 옛 줄이 남지 않았다");
  ok(/href="\$\{esc\(href\)\}"/.test(aa),
     "auth-action.html — 버튼 주소를 마크업에 넣기 전에 한 번 더 막는다");

  /* Consent.html 은 자기 자물쇠를 쓴다. 규칙이 다르더라도 바깥으로는
     못 나가야 한다 — 그 정규식을 그대로 꺼내 시험한다. */
  const cm = read("Consent.html").match(/const NEXT = (\/[^;]+\/)\.test\(raw\)/);
  ok(!!cm, "Consent.html — 돌아갈 주소를 거르는 자물쇠가 있다");
  if (cm) {
    const re = new RegExp(cm[1].slice(1, -1));
    for (const bad of ["https://evil.example.com", "//evil.example.com",
                       "javascript:alert(1)", "../x.html",
                       '"><img src=x onerror=alert(1)>'])
      ok(!re.test(bad), `Consent.html — 막는다: ${bad.slice(0, 28)}`);
    ok(re.test("Home.html"), "Consent.html — 평범한 페이지는 통과한다");
  }
}

/* ══════════════════════════════════════════════════════════
   3) 오류 문구 — 파이어베이스가 주는 코드를 다 아는가
   ══════════════════════════════════════════════════════════ */
console.log("\n── ③ 로그인이 안 될 때 무슨 말이 나오는가 ──");

const GENERIC = "처리 중 오류가 발생했습니다.";
const ERR_CASES = [
  ["비밀번호가 틀림(옛 코드)",        "auth/wrong-password",            "이메일 또는 비밀번호가 올바르지 않습니다."],
  ["비밀번호가 틀림(지금 코드)",      "auth/invalid-credential",        "이메일 또는 비밀번호가 올바르지 않습니다."],
  ["비밀번호가 틀림(열거 방지 켠 때)", "auth/invalid-login-credentials", "이메일 또는 비밀번호가 올바르지 않습니다."],
  ["없는 계정",                       "auth/user-not-found",            "이메일 또는 비밀번호가 올바르지 않습니다."],
  ["비밀번호를 안 보냄",              "auth/missing-password",          "이메일 또는 비밀번호가 올바르지 않습니다."],
  ["이메일 모양이 틀림",              "auth/invalid-email",             "이메일 형식이 올바르지 않습니다."],
  ["약한 비밀번호",                   "auth/weak-password",             "비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다."],
  ["이미 가입된 이메일",              "auth/email-already-in-use",      "이미 가입된 이메일입니다."],
  ["다른 방법으로 가입한 이메일",     "auth/account-exists-with-different-credential",
                                      "이 이메일은 다른 방법으로 가입되어 있습니다. 아래 버튼 중 처음 가입하실 때 쓰신 것으로 로그인하여 주시기 바랍니다."],
  ["너무 자주 시도",                  "auth/too-many-requests",         "요청이 많아 잠시 막혔습니다. 잠시 후 다시 시도하여 주시기 바랍니다."],
  ["네트워크 끊김",                   "auth/network-request-failed",    "네트워크 연결을 확인하여 주시기 바랍니다."],
  ["정지된 계정",                     "auth/user-disabled",             "이 계정은 사용이 중지되었습니다. hello@kosai.kr로 문의하여 주시기 바랍니다."],
  ["다시 로그인 필요",                "auth/requires-recent-login",     "보안을 위해 다시 로그인하신 뒤 진행하여 주시기 바랍니다."],
  ["팝업이 막힘",                     "auth/popup-blocked",             "브라우저가 팝업을 막았습니다. 팝업을 허용하신 뒤 다시 시도하여 주시기 바랍니다."],
  ["팝업을 닫음",                     "auth/popup-closed-by-user",      "로그인 창이 닫혔습니다. 다시 시도하여 주시기 바랍니다."],
  ["설정이 안 됨",                    "auth/operation-not-allowed",     "Firebase 설정이 필요합니다. firebase-config.js를 확인하여 주시기 바랍니다."],
];
for (const [name, code, want] of ERR_CASES)
  eq(mapAuthError({ code }), want, `문구 — ${name}`);

/* 모르는 코드는 일반 문구 + 코드로 떨어져야 한다(숨기면 우리가 못 고친다) */
ok(mapAuthError({ code: "auth/some-new-code" }).startsWith(GENERIC),
   "문구 — 모르는 코드는 일반 문구로 떨어진다");

/* 사용자가 스스로 닫은 것은 빨간 오류를 띄울 일이 아니다 */
ok(isUserCancelled({ code: "auth/popup-closed-by-user" }), "취소 — 팝업을 닫은 것은 오류가 아니다");
ok(!isUserCancelled({ code: "auth/wrong-password" }), "취소 — 비밀번호 오류는 오류가 맞다");

/* Login.html 이 아는 코드와 문구 표가 아는 코드가 어긋나지 않는가.
   실제로 여기가 갈려 있었다 — 화면은 알고 표는 몰랐다. */
{
  const m = read("Login.html").match(/if\(\/([^/]+)\/\.test\(code\)\)/);
  ok(!!m, "Login.html — 안내를 띄울 코드 목록이 있다");
  if (m) for (const part of m[1].split("|"))
    ok(mapAuthError({ code: "auth/" + part }) !== undefined
       && !mapAuthError({ code: "auth/" + part }).startsWith(GENERIC),
       `문구 표도 아는 코드: ${part}`);
}

/* ══════════════════════════════════════════════════════════
   4) 상태 × 동작 표
   ══════════════════════════════════════════════════════════ */
console.log("\n── ④ 상태 × 동작 — 코드가 표대로 갈라지는가 ──");

const login = read("Login.html"), signup = read("Signup.html");
const consentPage = read("Consent.html"), state = read("auth-state.js");
const guard = read("auth-guard.js"), consentJs = read("consent.js");

const SPEC = [
  ["가입 중단(동의 없음) → 이메일 로그인", "동의 화면으로",
   () => /consentState\(cred\.user\.uid\) === false/.test(login)
      && /Consent\.html\?next=/.test(login)],

  ["동의를 인증보다 먼저 본다", "순서가 가입과 같다",
   () => login.indexOf("consentState(cred.user.uid)") < login.indexOf("!cred.user.emailVerified")],

  ["인증 안 한 이메일 계정 → 로그인", "로그아웃 + 인증 메일 다시 보내기",
   () => /pwOnly && !cred\.user\.emailVerified/.test(login) && /offerResend\(\)/.test(login)],

  ["약관 개정(stale) → 로그인", "동의 화면으로(같은 길)",
   () => /=== "ok"/.test(consentJs) && /s === null \? null : s === "ok"/.test(consentJs)],

  ["동의 마친 새 이메일 계정", "인증 메일 + 로그아웃",
   () => /provider === 'email' && !user\.emailVerified/.test(consentPage)],

  ["이미 인증된 옛 회원이 동의 마침", "그냥 통과 — 붙잡지 않는다",
   () => /provider === 'email' && !user\.emailVerified/.test(consentPage)
      && !/if\(provider === 'email'\)\{/.test(consentPage)],

  ["구글 신규 가입", "동의 화면으로(계정 만든 직후)",
   () => /finishGoogleSignup/.test(login) && /if \(!isNewUser\) return Promise\.resolve\(true\)/.test(consentJs)],

  ["구글 기존 사용자", "다시 묻지 않는다",
   () => /if \(!isNewUser\) return Promise\.resolve\(true\)/.test(consentJs)],

  ["소셜 가입인데 같은 이메일이 이미 있음", "계정을 만들지 않고 안내",
   () => /already-exists/.test(read("social-login.js"))],

  /* 부르는 자리끼리 견준다. 맨 위 import 줄까지 세면 순서가 뒤집혀 보인다
     — 실제로 그렇게 헛경보가 났다. */
  ["가입 폼 — 소셜로 가입한 주소", "계정을 만들기 전에 막는다",
   () => signup.lastIndexOf("await signinMethod(email)")
       < signup.indexOf("await createUserWithEmailAndPassword(")],

  ["가입 폼 — 이미 가입된 주소", "로그인 길과 인증 메일 길을 같이 준다",
   () => /showAlreadyRegistered/.test(signup) && /인증 메일 다시 보내기/.test(signup)],

  ["동의 화면에서 취소(가입 중단 계정)", "계정을 지운다",
   () => /deleteMyAccount\(\)/.test(consentPage)],

  ["동의 화면에서 취소(개정 재동의)", "지우지 않고 로그아웃만",
   () => /stage === 'stale' \|\| !stageKnown/.test(consentPage)],

  ["동의 조회 실패(통신 끊김)", "막지도 지우지도 않는다",
   () => /!stageKnown/.test(consentPage) && /state !== false\) return/.test(state)],

  ["보호 페이지에 비로그인 접근", "로그인 창을 덮는다",
   () => /GATED\.test\(page\)/.test(guard) && /lockPage\(/.test(guard)],

  ["보호 페이지에 인증 안 한 계정", "인증 안내를 덮는다",
   () => /lockVerify\(u\)/.test(guard)],

  ["동의 없이 다른 페이지로 들어옴", "동의 화면으로 되돌린다",
   () => /guardConsent/.test(state) && /Consent\.html\?next=/.test(state)],

  ["동의 화면으로 두 번 튕김", "가두지 않고 통과시킨다",
   () => /bounced >= 1/.test(state)],

  ["로그인·가입 화면에서는 되돌리지 않는다", "고리를 만들지 않는다",
   () => /CONSENT_SKIP = \/\^\(Consent\|Login\|Signup/.test(state)],

  ["계정 메뉴의 이름·이메일", "글자로 넣는다(마크업으로 잇지 않는다)",
   () => /\.em'\)\.textContent = email/.test(state) && /m-em'\)\.textContent = email/.test(state)],
];
for (const [when, then, check] of SPEC) ok(check(), `${when} → ${then}`);

/* ══════════════════════════════════════════════════════════
   5) 구조 — 같은 실수가 다시 들어오지 못하게
   ══════════════════════════════════════════════════════════ */
console.log("\n── ⑤ 같은 실수가 다시 들어올 자리 ──");
{
  const files = ["Login.html", "Signup.html", "Consent.html", "auth-action.html",
                 "auth-state.js", "auth-guard.js", "social-login.js", "consent.js"];
  /* 주소 표시줄에서 온 값이 검사 없이 이동에 쓰이면 안 된다 */
  const leaks = [];
  for (const f of files) {
    const t = read(f);
    const re = /location\.(?:href|replace)\s*\(?\s*=?\s*([^;\n]+)/g;
    let m;
    while ((m = re.exec(t))) {
      const arg = m[1];
      if (/^['"`]/.test(arg.trim())) continue;              // 글자 그대로 — 안전
      if (/safeNext|goNext|NEXT\b|encodeURIComponent|url\b/.test(arg)) continue;
      leaks.push(`${f}: ${arg.trim().slice(0, 48)}`);
    }
  }
  ok(leaks.length === 0, "이동에 쓰이는 값이 전부 글자이거나 자물쇠를 거친다",
     leaks.slice(0, 3).join(" · "));

  /* 사용자가 정한 글자를 마크업으로 이어 붙이지 않는다 */
  const inj = [];
  for (const f of files) {
    for (const [i, l] of read(f).split("\n").entries()) {
      if (!/innerHTML\s*=/.test(l)) continue;
      if (/\$\{\s*(email|name|displayName|nick|user\.|msg|continueUrl|href)/.test(l))
        inj.push(`${f}:${i + 1}`);
    }
  }
  ok(inj.length === 0, "사용자가 정한 글자를 마크업에 이어 붙이지 않는다", inj.join(" · "));
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
