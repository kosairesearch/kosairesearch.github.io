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
      <h1 id="ttl">약관 동의</h1>
      <p id="lede">가입을 마치려면 아래 항목에 동의해 주세요.</p>
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

    <p class="consent-note" id="foot">동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.</p>
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
.verify-sent{text-align:center;padding:6px 0 2px}
.verify-sent b{display:block;font:700 17px/1.4 var(--font-sans);color:var(--fg-1);margin-bottom:8px}
.verify-sent p{margin:0;font:400 14px/1.7 var(--font-sans);color:var(--fg-2);word-break:break-all}
.verify-sent a{display:inline-block;margin-top:16px;font:600 14px var(--font-sans);
  color:var(--brand-blue);text-decoration:none}
.verify-sent a:hover{text-decoration:underline}
:root[data-theme="dark"] .verify-sent a{color:var(--brand-cyan)}
.verify-again{display:block;margin:14px auto 0;background:none;border:0;cursor:pointer;
  font:500 12.5px var(--font-sans);color:var(--fg-3);text-decoration:underline;
  text-underline-offset:2px;padding:6px}
.verify-again:hover:not(:disabled){color:var(--fg-2)}
.verify-again:disabled{cursor:default;text-decoration:none;color:var(--fg-3)}
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
  "개정된 약관 동의":"Updated terms",
  "이용약관이 개정되었습니다. 계속 이용하시려면 동의해 주세요.":
    "Our Terms of Service have been updated. Please accept them to continue.",
  "동의하고 계속하기":"Agree and continue",
  "나중에 하기":"Not now",
  "동의하지 않으면 로그아웃됩니다. 계정과 자료는 그대로 남습니다.":
    "If you do not agree you will be signed out. Your account and data stay as they are.",
  "동의하고 시작하기":"Agree and continue",
  "동의하지 않고 취소":"Cancel",
  "이용약관":"Terms of Service",
  "개인정보처리방침":"Privacy Policy",
  "동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.":
    "If you do not agree, your sign-up is cancelled and no account is kept.",
  "동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.":
    "Could not save your agreement. Please try again in a moment.",
  "로그인이 필요합니다.":"Please sign in.",
  "가입이 만료되어 계정이 삭제되었어요. 처음부터 다시 가입해 주세요.":
    "This sign-up expired and the account was removed. Please sign up again.",
  "다시 가입하기":"Sign up again",
  "인증 메일을 보냈어요":"Verification email sent",
  "주소로 인증 링크를 보냈습니다. 메일의 링크를 눌러 인증한 뒤 로그인해 주세요. (스팸함도 확인해 주세요)":
    "— we sent a verification link. Click it to verify, then sign in. (Check your spam folder too.)",
  "로그인하러 가기":"Go to sign in",
  "가입 완료":"Almost done",
  "메일 인증만 남았어요.":"Just one more step — verify your email.",
  "인증 메일을 보내지 못했어요":"Could not send the verification email",
  "주소로 인증 링크를 보내지 못했습니다. 아래에서 다시 보내 주세요.":
    "— we could not send the verification link. Please resend below.",
  "인증 메일 다시 보내기":"Resend verification email",
  "다시 보냈습니다. 메일함을 확인해 주세요.":"Sent again — please check your inbox.",
  "보내지 못했어요. 잠시 후 다시 시도해 주세요.":"Could not send. Please try again in a moment.",
  "이미 다른 방법으로 가입된 이메일입니다.":"This email is already registered with another sign-in method.",
  "이 주소는 이미 다음 방법으로 등록되어 있습니다:":"This address is already registered with:",
  "이메일 가입":"Email sign-up",
  "구글 로그인":"Google sign-in",
  "카카오 로그인":"Kakao sign-in",
  "네이버 로그인":"Naver sign-in",
  "로그인하러 가기":"Go to sign in"
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
import { renderConsent, saveConsent, consentStage } from "./consent.js";
import { sendVerifyEmail } from "./auth-emails.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
const errBox = document.getElementById('authErr');
function showErr(msg){ errBox.textContent = msg; errBox.style.display = 'block'; }

/* 돌아갈 곳. 바깥 주소로 튕기지 않게 같은 사이트의 페이지 이름만 받는다 —
   ?next= 는 사용자가 고칠 수 있는 값이라 그대로 믿으면 안 된다. */
const raw = new URLSearchParams(location.search).get('next') || 'Home.html';
const NEXT = /^[A-Za-z0-9_.-]+\\.html(\\?[^#]*)?$/.test(raw) ? raw : 'Home.html';

let consent = null;

/* 이 사람이 여기 온 이유. 'none' 이면 가입을 마치지 못한 계정이고,
   'stale' 이면 약관이 개정돼 다시 받는 것이다. 화면에 쓸 말이 다르다 —
   3년 쓴 회원에게 "가입을 마치려면" 이라고 하면 무슨 소린지 알 수 없고,
   "동의하지 않으면 계정이 남지 않습니다" 는 사실도 아니다. */
let stage = 'none';

/* 위 판단이 실제 기록을 보고 내려진 것인가. 조회가 실패하면(null) false 다.
   취소 버튼이 계정을 지울지 말지를 이걸로 가른다 — 아래 참고. */
let stageKnown = false;

/* 재동의 화면의 문구. 지우는 것이 아니라 갈아 끼운다 — 같은 페이지가
   두 가지 일을 한다. */
const RECONSENT = {
  ttl:  '개정된 약관 동의',
  lede: '이용약관이 개정되었습니다. 계속 이용하시려면 동의해 주세요.',
  btn:  '동의하고 계속하기',
  no:   '나중에 하기',
  foot: '동의하지 않으면 로그아웃됩니다. 계정과 자료는 그대로 남습니다.'
};

function paintReconsent(){
  document.getElementById('ttl').textContent  = T(RECONSENT.ttl);
  document.getElementById('lede').textContent = T(RECONSENT.lede);
  document.getElementById('agreeBtn').textContent = T(RECONSENT.btn);
  document.getElementById('cancelBtn').textContent = T(RECONSENT.no);
  document.getElementById('foot').textContent = T(RECONSENT.foot);
}

/* 우리가 일부러 로그아웃하거나 계정을 지우는 동안 아래 리스너가 끼어들지
   못하게 막는 빗장이다.

   signOut·deleteUser 를 부르면 onAuthStateChanged 가 user=null 로 울린다.
   그 리스너 첫 줄이 로그인 페이지로 보내 버리므로, 이메일 가입을 마치고
   '인증 메일을 보냈어요' 를 띄우려던 순간 화면이 로그인으로 넘어갔다.
   취소 버튼도 같은 이유로 홈이 아니라 로그인으로 갔다. */
let finishing = false;

onAuthStateChanged(auth, async user => {
  if(finishing) return;
  if(!user){
    // 로그인 없이 이 주소로 들어온 경우. 가입 흐름 밖이므로 로그인으로 보낸다.
    location.replace('Login.html?next=' + encodeURIComponent(NEXT));
    return;
  }
  // 이미 동의한 계정이 뒤로가기 등으로 다시 들어오면 그냥 통과시킨다.
  // 조회에 실패하면(null) 막지 않고 화면을 띄운다 — 통신이 잠깐 끊겼다고
  // 가입을 세우지 않는다.
  const st = await consentStage(user.uid);
  if(st === 'ok'){ location.replace(NEXT); return; }
  if(consent) return;                     // 인증 상태가 두 번 울려도 한 번만 그린다
  /* 못 읽었으면(null) 막지 않고 가입 화면으로 띄운다 — 통신이 잠깐
     끊겼다고 가입을 세우지 않는다. */
  stage = st === 'stale' ? 'stale' : 'none';
  stageKnown = (st === 'stale' || st === 'none');
  if(stage === 'stale') paintReconsent();
  /* 재동의는 필수 항목만 묻는다. 마케팅은 선택 항목이라 설정 화면이
     관리하는데, 여기서 빈 칸으로 다시 내밀면 켜 둔 사람이 그대로 두는
     순간 꺼진 것처럼 보인다. 서버도 재동의 때는 마케팅을 건드리지 않는다. */
  consent = renderConsent({ requiredOnly: stage === 'stale' });
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
    const r = await saveConsent(user.uid, consent.values(), provider, user.email || '');

    /* 개정 때문에 다시 받은 것이면 여기서 끝이다. 가입이 아니므로
       가입 집계를 올리지 않고, 인증 메일도 보내지 않고, 로그아웃도 하지
       않는다 — 이미 쓰고 있던 사람을 붙잡아 세운 것뿐이다.

       판단은 서버 대답을 따른다. 기존 기록이 있었는지는 서버만 안다.
       대답이 안 오는 옛 브라우저를 대비해 화면이 고른 stage 로 물러선다. */
    const reconsent = r && typeof r.reconsent === 'boolean' ? r.reconsent : (stage === 'stale');
    if(reconsent){ location.replace(NEXT); return; }

    if(window.KOSA) KOSA.track('sign_up', { method: provider });

    /* 이메일 가입은 여기서 끝나지 않는다. 메일 인증이 남아 있어서
       바로 들여보내면 안 된다 — 인증 전에는 로그인 상태로 두지 않는다는
       것이 이 사이트의 규칙이다(Signup.html 이 하던 일을 그대로 가져왔다).
       소셜 가입은 인증이 이미 끝나 있으므로 곧장 보낸다. */
    if(provider === 'email'){
      const mail = user.email || '';
      /* 발송 실패를 삼키지 않는다. 실패해도 '보냈어요' 라고 하면 오지 않는
         메일을 기다리게 된다. 아래 화면이 문구를 갈라 준다. */
      let sent = true;
      try{ await sendVerifyEmail(mail); }catch(_){ sent = false; }
      finishing = true;                 // 아래 signOut 이 리스너를 깨우지 못하게
      /* signOut 은 이 파일 맨 위에서 이미 가져왔다. 여기서 다시 동적으로
         import 하면 그때 네트워크를 한 번 더 타고, 그게 실패하면 동의는
         저장됐는데 화면에는 '저장에 실패했어요' 가 뜬 채 흐름이 멈춘다.
         실제로 그렇게 걸렸다. */
      try{ await signOut(auth); }catch(_){}
      showVerifySent(mail, sent);
      return;
    }
    location.replace(NEXT);
  }catch(e){
    btn.disabled = false;
    /* 동의를 마치지 않은 계정은 24시간 뒤 purgeUnconsented 가 지운다.
       이 화면을 하룻밤 켜 둔 채 돌아와 누르면 계정이 이미 없을 수 있다.
       그때 '저장에 실패했어요' 만 뜨면 무슨 일인지 알 수가 없다. */
    const code = (e && (e.code || '')) + '';

    /* 같은 이메일을 쓰는 계정이 이미 있다. 서버가 동의 기록을 거부했다.
       방금 만들어진 이 계정은 남길 이유가 없으므로 지우고, 원래 가입한
       방법으로 안내한다. 계정 둘을 남겨 두면 관심 종목이 갈리고 같은
       주소로 메일이 두 번 간다. */
    if(/already-exists/.test(code)){
      finishing = true;
      try{ await deleteUser(auth.currentUser); }
      catch(_){ try{ await signOut(auth); }catch(__){} }
      /* 서버 문장은 길고 한국어뿐이다. 서버가 details.method 로 어느
         방법인지 알려 주므로 문구는 여기서 만든다 — 로그인·가입 화면과
         같은 한 줄을 쓴다. */
      let msg = '';
      try{
        const { hintText } = await import('./auth-hint.js');
        msg = hintText((e && e.details && e.details.method) || '');
      }catch(_){}
      errBox.textContent = (msg || (e && e.message) || T('이미 다른 방법으로 가입된 이메일입니다.')) + ' ';
      const a = document.createElement('a');
      a.href = 'Login.html'; a.textContent = T('로그인하러 가기');
      a.style.cssText = 'color:var(--brand-blue);font-weight:600;text-decoration:underline';
      errBox.appendChild(a);
      errBox.style.display = 'block';
      document.querySelector('.consent-act').style.display = 'none';
      return;
    }

    if(/not-found|user-not-found|unauthenticated|permission-denied/.test(code)){
      errBox.textContent = T('가입이 만료되어 계정이 삭제되었어요. 처음부터 다시 가입해 주세요.') + ' ';
      const a = document.createElement('a');
      a.href = 'Signup.html'; a.textContent = T('다시 가입하기');
      a.style.cssText = 'color:var(--brand-blue);font-weight:600;text-decoration:underline';
      errBox.appendChild(a);
      errBox.style.display = 'block';
      btn.disabled = true;
      return;
    }
    showErr(T('동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.'));
  }
});

/* 이메일 가입 마무리 — 카드를 안내문으로 갈아 끼운다. 페이지를 또 옮기면
   뒤로가기로 동의 화면에 되돌아오는데, 그때는 이미 로그아웃돼 있어
   로그인 페이지로 튕긴다. 같은 자리에서 끝내는 편이 덜 헷갈린다. */
function showVerifySent(mail, sent){
  /* 머리글도 같이 바꾼다. 본문이 '메일 보냈어요' 인데 위에서는 여전히
     '아래 항목에 동의해 주세요' 라고 하면 화면이 두 말을 하게 된다. */
  const h1 = document.querySelector('.head h1');
  const sub = document.querySelector('.head p');
  if(h1){ h1.textContent = T('가입 완료'); }
  if(sub){ sub.textContent = T('메일 인증만 남았어요.'); }
  document.getElementById('consentMount').innerHTML = '';
  document.querySelector('.consent-act').style.display = 'none';
  document.querySelector('.consent-docs').style.display = 'none';
  document.querySelector('.consent-note').style.display = 'none';
  errBox.style.display = 'none';
  const box = document.createElement('div');
  box.className = 'verify-sent';
  const b = document.createElement('b');
  b.textContent = T('인증 메일을 보냈어요');
  if(!sent){ b.textContent = T('인증 메일을 보내지 못했어요'); }
  const p = document.createElement('p');
  p.textContent = sent
    ? mail + ' ' + T('주소로 인증 링크를 보냈습니다. 메일의 링크를 눌러 인증한 뒤 로그인해 주세요. (스팸함도 확인해 주세요)')
    : mail + ' ' + T('주소로 인증 링크를 보내지 못했습니다. 아래에서 다시 보내 주세요.');
  const a = document.createElement('a');
  a.href = 'Login.html'; a.textContent = T('로그인하러 가기');
  box.appendChild(b); box.appendChild(p); box.appendChild(a);

  /* 다시 보내기. 성공했을 때도 둔다 — 스팸함으로 갔거나 지웠을 수 있다.
     sendVerifyEmail 은 이메일을 본문에 실어 보내므로 로그아웃 뒤에도 된다. */
  const again = document.createElement('button');
  again.type = 'button'; again.className = 'verify-again';
  again.textContent = T('인증 메일 다시 보내기');
  again.addEventListener('click', async () => {
    again.disabled = true;
    try{
      await sendVerifyEmail(mail);
      again.textContent = T('다시 보냈습니다. 메일함을 확인해 주세요.');
    }catch(_){
      again.disabled = false;
      again.textContent = T('보내지 못했어요. 잠시 후 다시 시도해 주세요.');
    }
  });
  box.appendChild(again);
  document.querySelector('.consent-card').appendChild(box);
  if(window.KOSi18n) window.KOSi18n.apply();
}

document.getElementById('cancelBtn').addEventListener('click', async () => {
  document.getElementById('cancelBtn').disabled = true;
  finishing = true;                     // deleteUser 가 리스너를 깨우지 못하게

  /* 개정 재동의를 미룬 경우에는 로그아웃만 한다. 절대 지우지 않는다.

     이미 쓰고 있던 회원이다. 약관 개정에 아직 동의하지 않았다는 것과
     계정을 없애 달라는 것은 전혀 다른 말이다. 여기서 지우면 워치리스트도
     구독도 같이 사라진다 — 되돌릴 수 없다.

     약관 제3조가 시행일까지 거부 의사를 밝히지 않으면 동의한 것으로
     본다고 정하고 있고, 동의하지 않는 회원은 탈퇴할 수 있다. 탈퇴는
     설정 화면에서 본인이 하는 것이지 이 버튼이 대신할 일이 아니다. */
  /* 조회에 실패해 여기 온 이유를 모르는 경우도 지우지 않는다.

     통신이 잠깐 끊기면 stage 가 'none' 으로 떨어진다. 그 상태에서 기존
     회원이 새로고침하고 취소를 누르면 멀쩡한 계정이 사라진다 — 워치리스트도
     구독도 같이. 지우는 것은 되돌릴 수 없고, 안 지워서 생기는 일은
     '동의 없는 계정이 하루 더 남는 것' 뿐이며 그건 purgeUnconsented 가
     내일 치운다. 애매하면 지우지 않는 쪽으로 기운다. */
  if(stage === 'stale' || !stageKnown){
    try{ await signOut(auth); }catch(_){}
    location.replace('Home.html');
    return;
  }

  /* 가입을 마치지 않은 계정은 지운다. 로그아웃만 하면 동의하지 않은
     계정이 그대로 남는다. 지우기에 실패하면(재인증 요구 등) 로그아웃이라도
     한다 — 남은 계정은 다음 로그인 때 이 페이지를 다시 만난다. */
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


def check_guard_skips():
    """동의 화면이 여는 문서가 guardConsent 의 제외 목록에 있는지 본다.

    빠뜨리면 그 문서를 새 탭으로 열자마자 동의 화면으로 되튕긴다. 사용자
    눈에는 '약관 보기 링크가 안 눌린다' 로 보인다 — 동의하라고 보여 주는
    문서를 정작 못 읽게 막는 셈이라, 실제로 한 번 그렇게 나갔다.

    조용히 돌아올 수 있는 종류라 여기서 막는다. 이 생성기는 동의 화면을
    고칠 때마다 도니, 링크를 새로 추가하면 그 자리에서 걸린다.
    """
    guard = (ROOT / "auth-state.js").read_text(encoding="utf-8")
    m = re.search(r"const CONSENT_SKIP = /\^\((.*?)\)\\\.html", guard)
    if not m:
        return ["auth-state.js 에서 CONSENT_SKIP 을 찾지 못함"]
    skip = set(m.group(1).split("|"))
    page = OUT.read_text(encoding="utf-8")
    # 동의 카드 안에서 여는 링크만 본다(헤더·푸터의 일반 링크는 대상이 아니다).
    card = page[page.find('class="auth-card'):page.find("</main>")]
    linked = set(re.findall(r'href="([A-Za-z0-9_-]+)\.html"', card))
    return [f"{x}.html 이 CONSENT_SKIP 에 없다 — 새 탭이 동의 화면으로 되튕긴다"
            for x in sorted(linked) if x not in skip]


def main():
    ok, note = build()
    print(f"  {'✅' if ok else '❌'} {note}")
    if not ok:
        return 1
    problems = check_guard_skips()
    for x in problems:
        print(f"  ❌ {x}")
    if not problems:
        print("  ✅ 동의 화면이 여는 문서가 모두 guardConsent 제외 목록에 있다")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
