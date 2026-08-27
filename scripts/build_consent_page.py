#!/usr/bin/env python3
"""Consent.html 을 만든다 — 껍데기는 Login.html 에서 그대로 떠 온다.

왜 스크립트인가. 이 사이트는 페이지마다 헤더·푸터·테마 토글·i18n 엔진을
통째로 복사해 갖고 있다(공용 파일이 아니다). 손으로 베끼면 한 군데가
어긋나고, 그러면 새 페이지만 폰트나 다크모드가 다르게 나온다.

Login.html 을 원본으로 삼아 '가운데'(main·페이지 사전·페이지 스크립트)만
갈아 끼운다. 껍데기가 바뀌면 이 스크립트를 다시 돌리면 된다.

  python3 scripts/build_consent_page.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Login.html"
OUT = ROOT / "Consent.html"

# ── 갈아 끼울 세 덩어리 ────────────────────────────────────────────

MAIN = '''<main>
  <div class="wrap">
    <div class="head">
      <div class="kick">ACCOUNT</div>
      <h1>약관 동의</h1>
      <p>가입을 마치려면 아래 항목에 동의해 주세요.</p>
    </div>

    <div class="auth-card card glass consent-card">
      <div class="auth-err" id="authErr"></div>
      <div id="consentMount"></div>

      <div class="consent-act">
        <button type="button" class="btn btn-primary" id="agreeBtn">동의하고 시작하기</button>
        <button type="button" class="consent-no" id="cancelBtn">동의하지 않고 취소</button>
      </div>

      <div class="consent-docs">
        <a class="doc-btn" href="Terms.html" target="_blank" rel="noopener">이용약관</a>
        <a class="doc-btn" href="Privacy.html" target="_blank" rel="noopener">개인정보처리방침</a>
      </div>
    </div>

    <p class="consent-note">동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.</p>
  </div>
</main>'''

# 모달용으로 만든 consent.js 의 치수는 이 페이지에 그대로 쓰면 작다. 모달은
# 좁은 카드 안에 욱여넣는 화면이고 여기는 페이지 하나를 다 쓴다. 글자와
# 간격을 키워 읽히게 한다.
CSS = '''<style id="consent-css">
.consent-card{max-width:520px;padding:28px 30px 26px}
.consent-card .kc{border:0;padding:0;margin:0}
.consent-card .kc-all{font-size:15.5px;padding-bottom:14px;margin-bottom:12px}
.consent-card .kc-all input,.consent-card .kc-row input{width:19px;height:19px}
.consent-card .kc-row{font-size:14.5px;line-height:1.6;padding:9px 0;gap:11px}
.consent-card .kc-row a{font-size:13px}
.consent-card .kc-detail{font-size:12.5px;line-height:1.7;margin-left:30px}
.consent-card .kc-err{font-size:13px;margin-top:10px}
.consent-act{display:flex;flex-direction:column;gap:10px;margin-top:22px}
.consent-act .btn-primary{width:100%;padding:15px 20px;font-size:15.5px}
.consent-no{background:none;border:0;font:500 13px var(--font-sans);color:var(--fg-3);
  cursor:pointer;padding:8px;text-decoration:underline;text-underline-offset:2px}
.consent-no:hover{color:var(--fg-2)}
/* 뤼튼처럼 카드 아래에 약관 두 개를 버튼으로 둔다. 항목 옆 [보기] 만 있으면
   동의를 누르기 전에 읽어 보라는 신호가 약하다. */
.consent-docs{display:flex;gap:8px;margin-top:20px;padding-top:18px;
  border-top:1px solid var(--hair)}
.doc-btn{flex:1;text-align:center;padding:11px 12px;border-radius:var(--radius-sm);
  border:1px solid var(--border-2);font:600 13px var(--font-sans);color:var(--fg-2);
  text-decoration:none;transition:border-color .15s,color .15s}
.doc-btn:hover{color:var(--fg-1);border-color:var(--fg-3)}
.consent-note{max-width:520px;margin:16px auto 0;text-align:center;
  font:400 12.5px/1.7 var(--font-sans);color:var(--fg-3)}
@media (max-width:640px){
  .consent-card{padding:24px 20px 22px}
  .consent-docs{flex-direction:column}
}
</style>'''

DICT = '''if(window.KOSi18n) KOSi18n.register({
  "약관 동의":"Agreements",
  "가입을 마치려면 아래 항목에 동의해 주세요.":"To finish signing up, please accept the items below.",
  "동의하고 시작하기":"Agree and continue",
  "동의하지 않고 취소":"Cancel",
  "이용약관":"Terms of Service",
  "개인정보처리방침":"Privacy Policy",
  "동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.":
    "If you do not agree, your sign-up is cancelled and no account is kept.",
  "동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.":
    "Could not save your agreement. Please try again in a moment.",
  "로그인이 필요합니다.":"Please sign in."
});'''

SCRIPT = '''<script type="module">
/* 가입 마지막 단계 — 약관 동의.
 *
 * 예전에는 구글 로그인이 끝난 자리에서 모달을 띄웠다. 페이지로 옮긴 이유는
 * 둘이다. 모달은 좁아서 글자를 키울 수 없었고, 무엇보다 '가입이 아직 안
 * 끝났다' 는 것이 화면에서 드러나지 않았다.
 *
 * 이 페이지는 로그인된 사용자를 전제로 한다. 계정은 이미 만들어져 있고,
 * 여기서 동의를 받아야 가입이 성립한다. 동의하지 않으면 계정을 지운다 —
 * 동의 기록 없는 계정을 남기지 않는 것이 consent.js 전체의 원칙이다.
 */
import { auth } from "./firebase-config.js";
import { onAuthStateChanged, deleteUser, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { renderConsent, saveConsent, consentState } from "./consent.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
const errBox = document.getElementById('authErr');
function showErr(msg){ errBox.textContent = msg; errBox.style.display = 'block'; }

/* 돌아갈 곳. 바깥 주소로 튕기지 않게 같은 사이트의 페이지 이름만 받는다 —
   ?next= 는 사용자가 고칠 수 있는 값이라 그대로 믿으면 안 된다. */
const raw = new URLSearchParams(location.search).get('next') || 'Home.html';
const NEXT = /^[A-Za-z0-9_.-]+\\.html(\\?[^#]*)?$/.test(raw) ? raw : 'Home.html';

let consent = null;

onAuthStateChanged(auth, async user => {
  if(!user){
    // 로그인 없이 이 주소로 들어온 경우. 가입 흐름 밖이므로 로그인으로 보낸다.
    location.replace('Login.html?next=' + encodeURIComponent(NEXT));
    return;
  }
  // 이미 동의한 계정이 뒤로가기 등으로 다시 들어오면 그냥 통과시킨다.
  // 조회에 실패하면(null) 막지 않고 화면을 띄운다 — 통신이 잠깐 끊겼다고
  // 가입을 세우지 않는다.
  if(await consentState(user.uid) === true){ location.replace(NEXT); return; }
  if(consent) return;                     // 인증 상태가 두 번 울려도 한 번만 그린다
  consent = renderConsent();
  document.getElementById('consentMount').appendChild(consent.el);
  if(window.KOSi18n) window.KOSi18n.apply();
});

document.getElementById('agreeBtn').addEventListener('click', async () => {
  const user = auth.currentUser;
  if(!user){ showErr(T('로그인이 필요합니다.')); return; }
  if(!consent || !consent.validate()) return;
  const btn = document.getElementById('agreeBtn');
  btn.disabled = true;
  try{
    const provider = String(user.uid).split(':')[0] === 'kakao' ? 'kakao'
      : String(user.uid).split(':')[0] === 'naver' ? 'naver'
      : ((user.providerData || [])[0] || {}).providerId === 'google.com' ? 'google'
      : 'email';
    await saveConsent(user.uid, consent.values(), provider, user.email || '');
    location.replace(NEXT);
  }catch(e){
    btn.disabled = false;
    showErr(T('동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.'));
  }
});

document.getElementById('cancelBtn').addEventListener('click', async () => {
  document.getElementById('cancelBtn').disabled = true;
  /* 거부하면 계정을 지운다. 로그아웃만 하면 동의하지 않은 계정이 그대로
     남는다. 지우기에 실패하면(재인증 요구 등) 로그아웃이라도 한다 — 남은
     계정은 다음 로그인 때 이 페이지를 다시 만난다. */
  try{ await deleteUser(auth.currentUser); }
  catch(e){ try{ await signOut(auth); }catch(_){} }
  location.replace('Home.html');
});
</script>'''


def build():
    src = SRC.read_text(encoding="utf-8")

    # ① main 교체
    out, n = re.subn(r"<main>.*?</main>", lambda _: MAIN, src, count=1, flags=re.S)
    if n != 1:
        return None, "<main> 을 찾지 못함"

    # ② 페이지 사전 교체 — 크롬 스크립트(메뉴·테마)는 그대로 두고 사전만 바꾼다.
    out, n = re.subn(r"if\(window\.KOSi18n\) KOSi18n\.register\(\{.*?\n\}\);",
                     lambda _: DICT, out, count=1, flags=re.S)
    if n != 1:
        return None, f"페이지 사전을 찾지 못함(매칭 {n})"

    # ③ 페이지 스크립트 교체.
    #    module 스크립트가 둘인데, 뒤엣것은 <script type="module" src="auth-state.js">
    #    로 속성이 붙어 있다. 여는 태그를 '>' 까지 정확히 맞추면 인라인 쪽만
    #    잡히므로 따로 걸러 낼 필요가 없다.
    #    (처음에 (?!.*?src=) 룩어헤드를 뒀다가 re.S 때문에 파일 끝까지 훑어
    #     매칭이 0이 됐다. 룩어헤드 자체가 필요 없는 자리였다.)
    out, n = re.subn(r'<script type="module">.*?</script>',
                     lambda _: SCRIPT, out, count=1, flags=re.S)
    if n != 1:
        return None, f"페이지 스크립트를 찾지 못함(매칭 {n})"

    # ④ 이 페이지만의 CSS 를 </head> 앞에 넣는다
    out = out.replace("</head>", CSS + "\n</head>", 1) if "</head>" in out else out
    if "consent-css" not in out:
        # Login.html 은 </head> 태그를 명시하지 않는다 — <body> 앞에 넣는다.
        out = out.replace("<body>", CSS + "\n<body>", 1)
    if "consent-css" not in out:
        return None, "CSS 를 넣을 자리를 찾지 못함"

    # ④-b 빵부스러기. <main> 바깥(내비 아래)에 있어 main 교체로는 안 바뀐다 —
    #      그대로 두면 '홈 / 로그인' 이 남는다.
    out, n = re.subn(r'(<div class="crumb"><a href="Home\.html">홈</a> / <b>)[^<]*(</b></div>)',
                     r"\g<1>약관 동의\g<2>", out, count=1)
    if n != 1:
        return None, f"빵부스러기를 찾지 못함(매칭 {n})"

    # ⑤ 제목·설명·정규 주소
    out = re.sub(r"<title>[^<]*</title>", "<title>약관 동의 — KOSAI</title>", out, count=1)
    out = re.sub(r'(<meta (?:name|property)="(?:description|og:description|twitter:description)" content=")[^"]*"',
                 r'\1KOSAI 가입 약관 동의."', out)
    out = re.sub(r'(<meta property="og:title" content=")[^"]*"', r'\1약관 동의 — KOSAI"', out)
    out = re.sub(r'(<meta name="twitter:title" content=")[^"]*"', r'\1약관 동의 — KOSAI"', out)
    out = out.replace("https://kosai.kr/Login.html", "https://kosai.kr/Consent.html")

    # 가입 중간 화면이므로 검색에 잡히면 안 된다.
    out = out.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow" />', 1)

    OUT.write_text(out, encoding="utf-8")
    return True, f"{OUT.name} 생성 ({len(out.splitlines())}줄)"


def main():
    ok, note = build()
    print(f"  {'✅' if ok else '❌'} {note}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
