#!/usr/bin/env python3
"""스테이징(kosai.kr/staging/) 새 디자인 계정 페이지의 인라인 모듈 넷 — Firebase 진짜 동작.

`build_auth_comp.py` 의 시안 JS(뒤가 없어 ?user= 로 흉내 낸 것) 대신, 실사이트(루트)
Login.html · Signup.html · Consent.html · auth-action.html 의 인라인 <script type="module">
을 새 마크업 위에 그대로 옮긴 것이다. 네 문자열은 각각 `<script type="module">` 의 **본문**
이다 — 태그 없이 그대로 끼운다.

    from auth_staging import LOGIN_JS, SIGNUP_JS, CONSENT_JS, ACTION_JS
    html = ... + '<script type="module">\\n' + LOGIN_JS + '\\n</script>' + ...

■ 가져오는 모듈 — 전부 스테이징 폴더 안의 것 · 맨 주소(?v= 없음)
    from "./firebase-config.js"   auth · isConfigured
    from "./auth-util.js"         goNext · safeNext · mapAuthError · isUserCancelled
    from "./social-login.js"      wireSocialButtons            (로그인 · 가입)
    from "./auth-emails.js"       sendVerifyEmail · sendResetEmail
    from "./consent.js"           saveConsent · consentStage · deleteMyAccount   (동의 · 정적)
    import("./consent.js")        consentState · finishGoogleSignup            (로그인 · 가입 · 동적)
    import("./auth-hint.js")      signinMethod · hintText — 선택. 실패하면 try/catch 로 넘어간다
    https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js
  `scripts/stamp_assets.py` 가 from "./x.js" · import("./x.js") 두 모양에 해시를 붙인다.
  staging/ 에는 auth-hint.js 가 없다 — staging/social-login.js 도 이미 같은 식으로(맨 주소 ·
  try/catch) 부르고 있어, 파일이 없으면 안내 한 줄만 빠지고 기본 문구로 간다.

■ 기대는 마크업 (build_auth_comp.py 의 LOGIN·SIGNUP·CONSENT·ACTION + 소셜 단추 id)
  로그인   form#emailForm · #email · #password · a#forgotLink · .alert#authErr · button#emailSubmit
           #googleBtn · #kakaoBtn · #naverBtn (카카오·네이버는 social-login.js 가 id 로 찾는다)
  회원가입 위와 같고 #password2 가 더 있다
  약관동의 #consentMount 안의 label.check[data-k=all|age14|terms|privacy|marketing][data-req]
           (class on = 체크) · #agreeBtn · #cancelBtn · #ttl · #lede · #foot · .alert#authErr · .acts · .auth
  계정인증 #crumbLabel · #acTitle · #acDesc · #acBody · .alert#acErr
           (재설정 폼은 JS 가 만든다 — form#rs · #np · #np2 · #rsSubmit, .fld/.msg 마크업)

■ 오류 UX
  칸에 매인 오류 → 그 칸의 .fld 에 err 를 붙이고 .msg 에 글자. 빈 칸은 한꺼번에 다 표시하고
  첫 칸에 초점. input 이 들어오면 지운다.
  서버·전역 오류 → #authErr(.alert) 에 show. 안내(재설정 메일 보냄 · 인증 안내 · 데모 모드)는
  info 도 붙인다. 사용자가 정한 글자(이메일 · 서버 문장)는 textContent/createElement 로만 넣는다
  — innerHTML 에 잇지 않는다(staging/tests/auth-table.test.mjs ⑥).

■ 이동
  성공 뒤 이동은 goNext()/safeNext() 만 쓴다(기본 Home.html). next · continueUrl 은 검사 없이
  쓰지 않는다. 화면 문구는 한국어 격식체뿐이다 — 새 페이지에는 KOSi18n 이 없다(check_seo.py).

■ 실사이트와 다른 자리
  · 데모 모드 안내(#cfgNote) 가 없어 #authErr(info) 에 띄운다 — 다음 동작에서 지워진다.
  · 로그인의 '인증 안 된 계정' 안내(#vrow) 도 #authErr(info) 안에 링크와 함께 둔다.
  · auth-hint 의 renderHint 는 style.display 를 만져 .alert.show 규칙과 어긋나므로 쓰지 않는다.
    hintText 로 문구만 받아 showErr 로 띄운다.
  · 동의 화면은 consent.js 의 renderConsent 를 붙이지 않고 마크업의 .check 줄을 읽는다.
    재동의(stale)면 마케팅 줄을 숨긴다(renderConsent 의 requiredOnly 와 같다).
    돌아갈 곳은 자체 정규식 대신 auth-util 의 safeNext 를 쓴다.
  · 인증 메일 보냄 화면은 .sent 상자(h2 · p · .acts) 로 그린다.
  · 계정 인증 성공 화면의 체크 배지(.ac-badge) 는 새 디자인에 없어 단추만 둔다.
"""

FIREBASE_AUTH = "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js"

# ── 로그인·가입 공용 — 칸 오류(.fld .msg) · 전역 오류(#authErr) ──────────────────
_COMMON = r'''
const $ = s => document.querySelector(s);
const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const errBox = $('#authErr');
/* 오류는 그 칸 밑에(.fld .msg) — 빈 칸은 한꺼번에 다 표시하고 첫 칸에 초점. 단추 위의
   .alert(#authErr) 에는 칸 하나에 매이지 않는 것만: 서버 응답(비밀번호 틀림 · 시도 초과 ·
   인증 안 된 계정)과 안내(info). */
function showErr(msg, info){ errBox.textContent = msg; errBox.classList.toggle('info', !!info); errBox.classList.add('show'); }
function hideErr(){ errBox.classList.remove('show', 'info'); errBox.textContent = ''; }
function link(text, href){
  const a = document.createElement('a');
  a.href = href || '#'; a.textContent = text;
  a.style.cssText = 'color:inherit;font-weight:600;text-decoration:underline;text-underline-offset:3px';
  return a;
}
function fldMsg(id, msg){ const f = $('#' + id).closest('.fld'); f.querySelector('.msg').textContent = msg; f.classList.add('err'); }
function clearAll(){ hideErr(); document.querySelectorAll('.fld.err').forEach(f => f.classList.remove('err')); }
function focusBad(ids){
  const id = ids.find(i => $('#' + i).closest('.fld').classList.contains('err'));
  if(id) $('#' + id).focus();
  return !!id;
}
document.querySelectorAll('.fld input').forEach(i => i.addEventListener('input', () => i.closest('.fld').classList.remove('err')));
'''

# ── 구글 팝업 — 로그인·가입이 같은 코드를 쓴다 ─────────────────────────────────
_GOOGLE = r'''
/* 구글은 팝업이 닫히는 순간 파이어베이스가 계정을 만든다. 새 계정이면 consent.js 가 동의 화면으로
   보내며 false 를 돌려주고(저장·삭제도 저쪽 일), 기존 계정이면 true 다. 로직은 consent.js 한 곳에
   있어 로그인 화면과 가입 화면이 어긋날 수 없다. */
$('#googleBtn').addEventListener('click', async () => {
  clearAll();
  const gb = $('#googleBtn');
  if(gb.dataset.busy) return;          /* 팝업이 두 번 열리지 않게 */
  gb.dataset.busy = '1';
  try{
    const cred = await signInWithPopup(auth, new GoogleAuthProvider());
    const isNew = !!(getAdditionalUserInfo(cred) || {}).isNewUser;
    const { finishGoogleSignup } = await import("./consent.js");
    if(!(await finishGoogleSignup(cred, isNew))) return;   /* 동의 화면으로 넘어갔다 */
    goNext();
  }
  catch(err){ if(isUserCancelled(err)) return; showErr(mapAuthError(err)); }
  finally{ delete gb.dataset.busy; }
});
'''

# ══════════════════════════════════════════════════════════════════════════════
LOGIN_JS = r'''import { auth, isConfigured } from "./firebase-config.js";
import { signInWithEmailAndPassword, GoogleAuthProvider, signInWithPopup, signOut, getAdditionalUserInfo }
  from "''' + FIREBASE_AUTH + r'''";
import { wireSocialButtons } from "./social-login.js";
import { goNext, mapAuthError, isUserCancelled } from "./auth-util.js";
import { sendVerifyEmail, sendResetEmail } from "./auth-emails.js";
''' + _COMMON + r'''
if(!isConfigured) showErr('데모 모드입니다 — 실제 로그인을 사용하시려면 firebase-config.js에 Firebase 설정값을 입력하여 주시기 바랍니다.', true);

/* 인증을 안 끝낸 이메일 계정 — 로그아웃시키고, 인증 메일을 다시 받을 길을 같은 자리에 준다. */
let unverifiedUser = null;
function offerResend(){
  hideErr();
  errBox.classList.add('info');
  errBox.appendChild(document.createTextNode('이메일 인증이 필요합니다. 메일의 링크를 누르신 뒤 다시 로그인하여 주시기 바랍니다. '));
  const a = link('인증 메일 다시 보내기');
  a.addEventListener('click', async ev => {
    ev.preventDefault();
    try{
      if(unverifiedUser) await sendVerifyEmail(unverifiedUser.email);
      showErr('인증 메일을 다시 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.', true);
    }
    catch(err){ showErr(mapAuthError(err)); }
  });
  errBox.appendChild(a);
  errBox.classList.add('show');
}

$('#emailForm').addEventListener('submit', async e => {
  e.preventDefault(); clearAll();
  const email = $('#email').value.trim(), pw = $('#password').value;
  if(!email) fldMsg('email', '이메일을 입력하여 주시기 바랍니다.');
  else if(!EMAIL.test(email)) fldMsg('email', '올바른 이메일 형식이 아닙니다.');
  if(!pw) fldMsg('password', '비밀번호를 입력하여 주시기 바랍니다.');
  if(focusBad(['email', 'password'])) return;
  const btn = $('#emailSubmit'); btn.disabled = true;
  try{
    const cred = await signInWithEmailAndPassword(auth, email, pw);

    /* 동의를 인증보다 먼저 본다. 가입 순서가 '계정 → 동의 → 메일 인증' 이므로 로그인도 같은 순서다.
       인증 게이트가 먼저 걸리면 동의 화면에서 나가 버린 계정은 '메일을 인증하라' 만 듣고 로그아웃돼
       동의 화면으로 갈 길이 영영 없다. 조회에 실패하면(null) 막지 않고 아래로 넘긴다. */
    try{
      const { consentState } = await import("./consent.js");
      if(await consentState(cred.user.uid) === false){
        const nx = new URLSearchParams(location.search).get('next') || 'Home.html';
        location.replace('Consent.html?next=' + encodeURIComponent(nx));
        return;
      }
    }catch(_){ /* 조회 실패는 로그인을 막을 사유가 아니다 */ }

    const pwOnly = cred.user.providerData.length && cred.user.providerData.every(p => p.providerId === 'password');
    if(pwOnly && !cred.user.emailVerified){
      unverifiedUser = cred.user;
      await signOut(auth);
      offerResend();
      return;
    }
    goNext();
  }catch(err){
    /* 비밀번호가 틀린 것과, 애초에 비밀번호로 가입한 적이 없는 것(네이버로 가입)은 다른 일이다.
       서버가 알면 '네이버 계정으로 가입된 이메일입니다' 한 줄을 대신 띄운다. 안내는 부가 기능이라
       실패해도 기본 문구로 간다. */
    const code = String((err && err.code) || '');
    if(/invalid-credential|wrong-password|user-not-found|invalid-login/.test(code)){
      try{
        const { signinMethod, hintText } = await import("./auth-hint.js");
        const m = await signinMethod(email);
        const hint = m && m !== 'email' ? hintText(m) : '';
        if(hint){ showErr(hint); return; }
      }catch(_){}
    }
    showErr(mapAuthError(err));
  }
  finally{ btn.disabled = false; }
});
''' + _GOOGLE + r'''
$('#forgotLink').addEventListener('click', async e => {
  e.preventDefault(); clearAll();
  const email = $('#email').value.trim();
  if(!email) fldMsg('email', '이메일을 먼저 입력하여 주시기 바랍니다.');
  else if(!EMAIL.test(email)) fldMsg('email', '올바른 이메일 형식이 아닙니다.');
  if(focusBad(['email'])) return;
  try{ await sendResetEmail(email); showErr('비밀번호 재설정 메일을 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.', true); }
  catch(err){ showErr(mapAuthError(err)); }
});

/* 카카오 · 네이버 — OAuth 리다이렉트 + Cloud Functions 커스텀 토큰. #kakaoBtn · #naverBtn 을 id 로 찾고
   ?code= 복귀도 여기서 처리한다. 돌아갈 곳은 social-login.js 안에서 safeNext 를 거친다. */
wireSocialButtons({ onError: showErr });
'''

# ══════════════════════════════════════════════════════════════════════════════
SIGNUP_JS = r'''import { auth, isConfigured } from "./firebase-config.js";
import { createUserWithEmailAndPassword, GoogleAuthProvider, signInWithPopup, getAdditionalUserInfo }
  from "''' + FIREBASE_AUTH + r'''";
import { wireSocialButtons } from "./social-login.js";
import { goNext, mapAuthError, isUserCancelled } from "./auth-util.js";
import { sendVerifyEmail } from "./auth-emails.js";
''' + _COMMON + r'''
if(!isConfigured) showErr('데모 모드입니다 — 실제 가입을 사용하시려면 firebase-config.js에 Firebase 설정값을 입력하여 주시기 바랍니다.', true);

/* 이미 가입된 이메일 — 그냥 막고 끝내면 안 된다. 세 가지가 숨어 있다.
     ① 소셜로 가입한 주소 — 서버가 알면 그 한 줄만 띄운다
     ② 이메일로 가입하고 인증까지 끝낸 사람 — 로그인하면 된다
     ③ 이메일로 가입했는데 인증을 못 끝낸 사람 — 재가입도 로그인도 막혀 갇힌다. 인증 메일을 다시 받아야 풀린다
   ②와 ③은 로그인 전에 구분할 수 없어 둘 다 놓는다. */
async function showAlreadyRegistered(email){
  hideErr();
  try{
    const { signinMethod, hintText } = await import("./auth-hint.js");
    const m = await signinMethod(email);
    const hint = m && m !== 'email' ? hintText(m) : '';
    if(hint){ showErr(hint); return; }
  }catch(_){ /* 안내는 부가 기능 */ }

  const nx = new URLSearchParams(location.search).get('next') || 'Home.html';
  const line1 = document.createElement('div');
  line1.style.fontWeight = '600';
  line1.appendChild(document.createTextNode('이미 가입된 이메일입니다. '));
  line1.appendChild(link('로그인하러 가기', 'Login.html?next=' + encodeURIComponent(nx)));

  const line2 = document.createElement('div');
  line2.style.cssText = 'margin-top:6px;font-weight:400;opacity:.85';
  line2.appendChild(document.createTextNode('메일 인증을 아직 못 하셨나요? '));
  const again = link('인증 메일 다시 보내기');
  again.addEventListener('click', async ev => {
    ev.preventDefault();
    again.textContent = '보내는 중…';
    try{ await sendVerifyEmail(email); showErr('인증 메일을 다시 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.', true); }
    catch(err){ showErr(mapAuthError(err)); }
  });
  line2.appendChild(again);

  errBox.appendChild(line1);
  errBox.appendChild(line2);
  errBox.classList.add('show');
}

$('#emailForm').addEventListener('submit', async e => {
  e.preventDefault(); clearAll();
  const email = $('#email').value.trim(), pw = $('#password').value, pw2 = $('#password2').value;
  if(!email) fldMsg('email', '이메일을 입력하여 주시기 바랍니다.');
  else if(!EMAIL.test(email)) fldMsg('email', '올바른 이메일 형식이 아닙니다.');
  if(!pw) fldMsg('password', '비밀번호를 입력하여 주시기 바랍니다.');
  else if(pw.length < 8 || !/[A-Za-z]/.test(pw) || !/[0-9]/.test(pw)) fldMsg('password', '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.');
  if(!pw2) fldMsg('password2', '비밀번호를 다시 입력하여 주시기 바랍니다.');
  else if(pw !== pw2) fldMsg('password2', '비밀번호가 일치하지 않습니다.');
  if(focusBad(['email', 'password', 'password2'])) return;
  const btn = $('#emailSubmit'); btn.disabled = true;

  /* 계정을 만들기 전에 막는다. 이메일을 심기 전에 만들어진 소셜 계정은 Auth 에 이메일이 없어
     파이어베이스가 거절하지 않는다 — 여기서 먼저 물어보면 계정이 만들어지지 않는다.
     서버가 모르면(null) 그냥 진행한다. */
  try{
    const { signinMethod, hintText } = await import("./auth-hint.js");
    const m = await signinMethod(email);
    const hint = m && m !== 'email' ? hintText(m) : '';
    if(hint){ showErr(hint); btn.disabled = false; return; }
  }catch(_){ /* 안내는 부가 기능 */ }

  try{
    /* 계정을 먼저 만들고 동의를 그 다음에 받는다 — 비밀번호를 다음 화면까지 들고 갈 수는 없다.
       동의를 마치지 못한 계정은 guardConsent 가 동의 페이지로 되돌리고 24시간 뒤 purgeUnconsented
       가 지운다. 인증 메일 발송과 로그아웃은 Consent.html 이 맡는다. */
    await createUserWithEmailAndPassword(auth, email, pw);
    const nx = new URLSearchParams(location.search).get('next') || 'Home.html';
    /* replace — 계정은 이미 만들어졌으므로 뒤로가기로 가입 폼에 돌아가 다시 누르면 '이미 가입된 이메일' 만 본다. */
    location.replace('Consent.html?next=' + encodeURIComponent(nx));
  }
  catch(err){
    if(String((err && err.code) || '').includes('email-already-in-use')) showAlreadyRegistered(email);
    else showErr(mapAuthError(err));
    btn.disabled = false;
  }
});
''' + _GOOGLE + r'''
/* 카카오 · 네이버 — 서버가 계정을 만들면서 같은 호출 안에 동의를 남긴다. 여기서 담아 보낼 것이 없다. */
wireSocialButtons({ onError: showErr });
'''

# ══════════════════════════════════════════════════════════════════════════════
CONSENT_JS = r'''/* 가입 마지막 단계 — 약관 동의. 로그인된 사용자를 전제로 한다. 계정은 이미 만들어져 있고 여기서
   동의를 받아야 가입이 성립한다. 동의하지 않으면 계정을 지운다 — 동의 기록 없는 계정을 남기지 않는다. */
import { auth } from "./firebase-config.js";
import { onAuthStateChanged, deleteUser, signOut }
  from "''' + FIREBASE_AUTH + r'''";
import { saveConsent, consentStage, deleteMyAccount } from "./consent.js";
import { sendVerifyEmail } from "./auth-emails.js";
import { safeNext } from "./auth-util.js";

const $ = s => document.querySelector(s);
const errBox = $('#authErr');
function showErr(msg, info){ errBox.textContent = msg; errBox.classList.toggle('info', !!info); errBox.classList.add('show'); }
function hideErr(){ errBox.classList.remove('show', 'info'); errBox.textContent = ''; }
function link(text, href){
  const a = document.createElement('a');
  a.href = href || '#'; a.textContent = text;
  a.style.cssText = 'color:inherit;font-weight:600;text-decoration:underline;text-underline-offset:3px';
  return a;
}

/* 돌아갈 곳. ?next= 는 사용자가 고칠 수 있는 값이라 auth-util 의 자물쇠를 거친다 — 우리 사이트 안의
   .html 하나만, 아니면 Home.html. */
const NEXT = safeNext();

/* 동의 줄은 마크업에 있다(consent.js 의 renderConsent 를 붙이지 않는다). class on = 체크. */
const allRow = $('#consentMount .check[data-k="all"]');
let items = [...document.querySelectorAll('#consentMount .check')].filter(r => r !== allRow);
function isOn(r){ return r.classList.contains('on'); }
function syncAll(){ allRow.classList.toggle('on', items.every(isOn)); }
allRow.addEventListener('click', () => { const on = !isOn(allRow); items.forEach(r => r.classList.toggle('on', on)); syncAll(); hideErr(); });
items.forEach(r => r.addEventListener('click', e => {
  if(e.target.closest('a')) return;      /* 약관을 보려던 것뿐이다 — 체크를 건드리지 않는다 */
  r.classList.toggle('on'); syncAll(); hideErr();
}));
function values(){ const v = {}; items.forEach(r => { v[r.dataset.k] = isOn(r); }); return v; }
function validate(){
  const bad = items.filter(r => r.dataset.req && !isOn(r));
  if(!bad.length) return true;
  showErr('필수 항목에 모두 동의하셔야 가입하실 수 있습니다.');
  try{ bad[0].scrollIntoView({ block: 'center', behavior: 'smooth' }); }catch(_){}
  return false;
}

/* 이 사람이 여기 온 이유. 'none' 이면 가입을 마치지 못한 계정, 'stale' 이면 약관이 개정돼 다시 받는
   것이다. stageKnown 은 그 판단이 실제 기록을 보고 내려졌는가 — 취소 단추가 계정을 지울지 이걸로 가른다. */
let painted = false, stage = 'none', stageKnown = false;

/* 우리가 일부러 로그아웃하거나 계정을 지우는 동안 아래 리스너가 로그인 페이지로 보내 버리지 못하게 막는 빗장. */
let finishing = false;

const RECONSENT = {
  ttl:  '개정된 약관 동의',
  lede: '이용약관이 개정되었습니다. 계속 이용하시려면 동의하여 주시기 바랍니다.',
  btn:  '동의하고 계속하기',
  no:   '나중에 하기',
  foot: '동의하지 않으면 로그아웃됩니다. 계정과 자료는 그대로 남습니다.'
};
function paintReconsent(){
  $('#ttl').textContent = RECONSENT.ttl;
  $('#lede').textContent = RECONSENT.lede;
  $('#agreeBtn').textContent = RECONSENT.btn;
  $('#cancelBtn').textContent = RECONSENT.no;
  $('#foot').textContent = RECONSENT.foot;
  /* 재동의는 필수 항목만 묻는다. 마케팅은 설정 화면이 관리한다 — 서버도 재동의 때는 건드리지 않는다. */
  items.filter(r => !r.dataset.req).forEach(r => { r.classList.remove('on'); r.style.display = 'none'; });
  items = items.filter(r => r.dataset.req);
  syncAll();
}

onAuthStateChanged(auth, async user => {
  if(finishing) return;
  if(!user){
    /* 로그인 없이 이 주소로 들어온 경우 — 가입 흐름 밖이므로 로그인으로 보낸다. */
    location.replace('Login.html?next=' + encodeURIComponent(NEXT));
    return;
  }
  /* 이미 동의한 계정이 뒤로가기 등으로 다시 들어오면 그냥 통과. 조회에 실패하면(null) 막지 않고
     가입 화면으로 띄운다 — 통신이 잠깐 끊겼다고 가입을 세우지 않는다. */
  const st = await consentStage(user.uid);
  if(st === 'ok'){ location.replace(NEXT); return; }
  if(painted) return;                    /* 인증 상태가 두 번 울려도 한 번만 */
  painted = true;
  stage = st === 'stale' ? 'stale' : 'none';
  stageKnown = (st === 'stale' || st === 'none');
  if(stage === 'stale') paintReconsent();
});

function providerOf(user){
  const head = String(user.uid).split(':')[0];
  if(head === 'kakao' || head === 'naver') return head;
  return ((user.providerData || [])[0] || {}).providerId === 'google.com' ? 'google' : 'email';
}

$('#agreeBtn').addEventListener('click', async () => {
  const user = auth.currentUser;
  if(!user){ showErr('로그인이 필요합니다.'); return; }
  if(!painted || !validate()) return;
  const btn = $('#agreeBtn');
  btn.disabled = true;
  try{
    const provider = providerOf(user);
    const r = await saveConsent(user.uid, values(), provider, user.email || '');

    /* 개정 때문에 다시 받은 것이면 여기서 끝 — 가입이 아니므로 집계도 인증 메일도 로그아웃도 없다.
       판단은 서버 대답을 따르고, 대답이 없으면 화면이 고른 stage 로 물러선다. */
    const reconsent = r && typeof r.reconsent === 'boolean' ? r.reconsent : (stage === 'stale');
    if(reconsent){ location.replace(NEXT); return; }

    if(window.KOSA) window.KOSA.track('sign_up', { method: provider });

    /* 이메일 가입은 메일 인증이 남아 있어 바로 들여보내지 않는다. 인증이 남은 사람만 — 동의 절차가
       생기기 전에 가입해 이미 인증을 마친 회원은 붙잡지 않는다(그 메일은 오지 않는다). */
    if(provider === 'email' && !user.emailVerified){
      const mail = user.email || '';
      let sent = true;                    /* 발송 실패를 삼키지 않는다 — 화면이 문구를 갈라 준다 */
      try{ await sendVerifyEmail(mail); }catch(_){ sent = false; }
      finishing = true;                   /* 아래 signOut 이 리스너를 깨우지 못하게 */
      try{ await signOut(auth); }catch(_){}
      showVerifySent(mail, sent);
      return;
    }
    location.replace(NEXT);
  }catch(e){
    btn.disabled = false;
    const code = (e && (e.code || '')) + '';

    /* 같은 이메일을 쓰는 계정이 이미 있어 서버가 거부했다. 방금 만든 이 계정은 지우고 원래 방법으로
       안내한다 — 계정 둘을 남기면 관심 종목이 갈리고 같은 주소로 메일이 두 번 간다. */
    if(/already-exists/.test(code)){
      finishing = true;
      try{ await deleteUser(auth.currentUser); }
      catch(_){ try{ await signOut(auth); }catch(__){} }
      let msg = '';
      try{
        const { hintText } = await import("./auth-hint.js");
        msg = hintText((e && e.details && e.details.method) || '');
      }catch(_){}
      hideErr();
      errBox.appendChild(document.createTextNode((msg || (e && e.message) || '이미 다른 방법으로 가입된 이메일입니다.') + ' '));
      errBox.appendChild(link('로그인하러 가기', 'Login.html'));
      errBox.classList.add('show');
      $('.acts').style.display = 'none';
      return;
    }

    /* 동의를 마치지 않은 계정은 24시간 뒤 purgeUnconsented 가 지운다 — 하룻밤 켜 둔 화면에서 누르면
       계정이 이미 없을 수 있다. */
    if(/not-found|user-not-found|unauthenticated|permission-denied/.test(code)){
      hideErr();
      errBox.appendChild(document.createTextNode('가입이 만료되어 계정이 삭제되었습니다. 처음부터 다시 가입하여 주시기 바랍니다. '));
      errBox.appendChild(link('다시 가입하기', 'Signup.html'));
      errBox.classList.add('show');
      btn.disabled = true;
      return;
    }
    showErr('동의를 저장하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.');
  }
});

/* 이메일 가입 마무리 — 같은 자리에서 안내문으로 갈아 끼운다. 페이지를 또 옮기면 뒤로가기로 여기 되돌아
   오는데 그때는 이미 로그아웃돼 있어 로그인 페이지로 튕긴다. 머리글도 같이 바꾼다 — 본문은 메일을
   보냈다는데 위에서는 '아래 항목에 동의하여 주시기 바랍니다' 면 화면이 두 말을 한다. */
function showVerifySent(mail, sent){
  $('#ttl').textContent = '가입 완료';
  $('#lede').textContent = '메일 인증만 남았습니다.';
  $('#consentMount').style.display = 'none';
  $('.acts').style.display = 'none';
  $('#foot').style.display = 'none';
  hideErr();

  const box = document.createElement('div');
  box.className = 'sent';
  const h = document.createElement('h2');
  h.textContent = sent ? '인증 메일을 보내 드렸습니다' : '인증 메일을 보내 드리지 못했습니다';
  const p = document.createElement('p');
  p.textContent = mail + ' ' + (sent
    ? '주소로 인증 링크를 보내 드렸습니다. 메일의 링크를 눌러 인증하신 뒤 로그인하여 주시기 바랍니다. (스팸함도 함께 확인해 주십시오)'
    : '주소로 인증 링크를 보내지 못했습니다. 아래에서 다시 요청하여 주시기 바랍니다.');
  const go = document.createElement('a');
  go.className = 'btn btn-ink'; go.href = 'Login.html'; go.textContent = '로그인하러 가기';

  /* 다시 보내기. 성공했을 때도 둔다 — 스팸함으로 갔거나 지웠을 수 있다. sendVerifyEmail 은 이메일을
     본문에 실어 보내므로 로그아웃 뒤에도 된다. */
  const again = document.createElement('button');
  again.type = 'button'; again.className = 'tbtn'; again.textContent = '인증 메일 다시 보내기';
  again.addEventListener('click', async () => {
    again.disabled = true;
    try{ await sendVerifyEmail(mail); again.textContent = '다시 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.'; }
    catch(_){ again.disabled = false; again.textContent = '보내지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.'; }
  });

  const acts = document.createElement('div');
  acts.className = 'acts';
  acts.appendChild(go); acts.appendChild(again);
  box.appendChild(h); box.appendChild(p); box.appendChild(acts);
  $('.auth').appendChild(box);
}

$('#cancelBtn').addEventListener('click', async () => {
  $('#cancelBtn').disabled = true;
  finishing = true;                       /* deleteUser 가 리스너를 깨우지 못하게 */

  /* 개정 재동의를 미룬 경우, 그리고 조회에 실패해 여기 온 이유를 모르는 경우에는 로그아웃만 한다.
     절대 지우지 않는다 — 이미 쓰고 있던 회원의 워치리스트·구독이 같이 사라지고 되돌릴 수 없다.
     안 지워서 생기는 일은 '동의 없는 계정이 하루 더 남는 것' 뿐이고 그건 purgeUnconsented 가 치운다. */
  if(stage === 'stale' || !stageKnown){
    try{ await signOut(auth); }catch(_){}
    location.replace('Home.html');
    return;
  }

  /* 가입을 마치지 않은 계정은 지운다. 서버(deleteAccount)에 맡긴다 — deleteUser 만 부르면 Auth 사용자만
     사라지고 users 문서가 남아 다음 가입의 중복 검사에 걸린다. 서버가 실패하면 그때는 브라우저에서라도
     Auth 사용자를 지운다. 남은 문서는 purgeUnconsented 가 다음 날 치운다. */
  try{
    await deleteMyAccount();
  }catch(e){
    console.warn('[consent] 서버 탈퇴 실패, 계정만 지운다:', e && e.message);
    try{ await deleteUser(auth.currentUser); }
    catch(_){ try{ await signOut(auth); }catch(__){} }
  }
  location.replace('Home.html');
});
'''

# ══════════════════════════════════════════════════════════════════════════════
ACTION_JS = r'''import { auth } from "./firebase-config.js";
import { safeNext } from "./auth-util.js";
import { applyActionCode, verifyPasswordResetCode, confirmPasswordReset }
  from "''' + FIREBASE_AUTH + r'''";

const $ = s => document.querySelector(s);
const params = new URLSearchParams(location.search);
const mode = params.get('mode');
const oobCode = params.get('oobCode');

/* 메일의 링크를 누르고 온 사람이 다음에 갈 곳. 주소에 그대로 실려 오는 값이라 믿으면 안 된다 —
   safeNext 가 우리 사이트 안의 .html 하나만 통과시킨다(로그인·가입 화면과 같은 자물쇠). 화면은
   createElement 로만 그리므로 문자열이 마크업으로 읽힐 자리도 없다. */
const continueUrl = safeNext(params.get('continueUrl'));

const crumbEl = $('#crumbLabel'), titleEl = $('#acTitle'), descEl = $('#acDesc'), bodyEl = $('#acBody'), errEl = $('#acErr');
function showErrMsg(msg){ errEl.textContent = msg; errEl.classList.add('show'); }
function clearErr(){ errEl.classList.remove('show'); errEl.textContent = ''; }
function el(tag, cls, text){
  const n = document.createElement(tag);
  if(cls) n.className = cls;
  if(text != null) n.textContent = text;
  return n;
}
function goBtn(label, href){ const a = el('a', 'btn btn-ink', label); a.href = href; return a; }
function fld(id, label, placeholder){
  const f = el('div', 'fld');
  const l = el('label', null, label); l.htmlFor = id;
  const i = el('input'); i.id = id; i.type = 'password'; i.autocomplete = 'new-password'; i.placeholder = placeholder; i.required = true;
  f.appendChild(l); f.appendChild(i); f.appendChild(el('div', 'msg'));
  return f;
}
function fm(input, msg){ const f = input.closest('.fld'); f.querySelector('.msg').textContent = msg; f.classList.add('err'); }
function paint(crumb, title, desc){
  crumbEl.textContent = crumb; titleEl.textContent = title; descEl.textContent = desc;
  bodyEl.textContent = '';
}

/* 현재 화면 상태 — 상태를 바꾸고 render() 로 다시 그린다. */
let state = { kind: 'loading' };

function render(){
  const s = state;
  if(s.kind === 'loading'){
    paint('계정 인증', '처리 중…', '잠시만 기다려 주시기 바랍니다.');
    const spin = el('div', 'spin'); spin.setAttribute('aria-label', '로딩');
    bodyEl.appendChild(spin);
  } else if(s.kind === 'ok'){
    paint(s.crumb, s.title, s.desc);
    bodyEl.appendChild(goBtn('로그인하러 가기', s.href));
  } else if(s.kind === 'error'){
    paint(s.crumb || '계정 인증', s.title, s.desc);
    bodyEl.appendChild(goBtn('로그인 페이지로', 'Login.html'));
  } else if(s.kind === 'reset'){
    paint('비밀번호 재설정', '새 비밀번호 설정', s.email + ' 계정의 새 비밀번호를 입력하여 주시기 바랍니다.');
    const form = el('form'); form.id = 'rs'; form.noValidate = true;
    form.appendChild(fld('np', '새 비밀번호', '영문·숫자 포함 8자 이상'));
    form.appendChild(fld('np2', '새 비밀번호 확인', '비밀번호를 다시 입력하십시오'));
    const btn = el('button', 'btn btn-ink', '비밀번호 변경'); btn.type = 'submit'; btn.id = 'rsSubmit';
    form.appendChild(btn);
    bodyEl.appendChild(form);
    form.querySelectorAll('input').forEach(i => i.addEventListener('input', () => i.closest('.fld').classList.remove('err')));
    form.addEventListener('submit', onResetSubmit);
  }
}

async function onResetSubmit(ev){
  ev.preventDefault(); clearErr();
  const np = $('#np'), np2 = $('#np2');
  [np, np2].forEach(i => i.closest('.fld').classList.remove('err'));
  const pw = np.value, pw2 = np2.value;
  if(!pw) fm(np, '비밀번호를 입력하여 주시기 바랍니다.');
  else if(pw.length < 8 || !/[A-Za-z]/.test(pw) || !/[0-9]/.test(pw)) fm(np, '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.');
  if(!pw2) fm(np2, '비밀번호를 다시 입력하여 주시기 바랍니다.');
  else if(pw !== pw2) fm(np2, '비밀번호가 일치하지 않습니다.');
  const bad = [np, np2].find(i => i.closest('.fld').classList.contains('err'));
  if(bad){ bad.focus(); return; }
  const btn = $('#rsSubmit'); btn.disabled = true;
  try{
    await confirmPasswordReset(auth, oobCode, pw);
    state = { kind: 'ok', crumb: '비밀번호 재설정', title: '비밀번호가 변경되었습니다', desc: '새 비밀번호로 로그인하여 주시기 바랍니다.', href: 'Login.html' };
    render();
  }catch(e){
    btn.disabled = false;
    const c = (e && e.code) || '';
    if(c.includes('expired') || c.includes('invalid-action-code')) showErrMsg('링크가 만료되었거나 이미 사용되었습니다. 메일을 다시 요청하여 주시기 바랍니다.');
    else showErrMsg('비밀번호 변경에 실패했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.');
  }
}

async function run(){
  if(!mode || !oobCode){
    state = { kind: 'error', title: '잘못된 접근입니다', desc: '유효하지 않은 링크입니다. 메일의 버튼을 다시 눌러 주시기 바랍니다.' };
    render(); return;
  }
  try{
    if(mode === 'verifyEmail'){
      await applyActionCode(auth, oobCode);
      state = { kind: 'ok', crumb: '이메일 인증', title: '이메일 인증이 완료되었습니다', desc: 'KOSAI의 모든 기능을 이용하실 수 있습니다. 로그인하여 주시기 바랍니다.', href: continueUrl };
    } else if(mode === 'resetPassword'){
      const email = await verifyPasswordResetCode(auth, oobCode);
      state = { kind: 'reset', email };
    } else if(mode === 'recoverEmail' || mode === 'verifyAndChangeEmail'){
      await applyActionCode(auth, oobCode);
      state = { kind: 'ok', crumb: '이메일 변경', title: '이메일 주소가 변경되었습니다', desc: '변경된 이메일로 다시 로그인하여 주시기 바랍니다.', href: continueUrl };
    } else {
      state = { kind: 'error', title: '지원하지 않는 요청', desc: '유효하지 않은 링크입니다.' };
    }
  }catch(e){
    const c = (e && e.code) || '';
    if(c.includes('expired')) state = { kind: 'error', title: '링크가 만료되었습니다', desc: '보안을 위해 인증 링크는 일정 시간이 지나면 만료됩니다. 메일을 다시 요청하여 주시기 바랍니다.' };
    else if(c.includes('invalid-action-code')) state = { kind: 'error', title: '이미 사용된 링크입니다', desc: '이미 처리되었거나 유효하지 않은 링크입니다. 새로 요청하여 주시기 바랍니다.' };
    else state = { kind: 'error', title: '처리 중 문제가 발생했습니다', desc: '잠시 후 다시 시도하시거나, 메일을 다시 요청하여 주시기 바랍니다.' };
  }
  render();
}

render();
run();
'''

__all__ = ["LOGIN_JS", "SIGNUP_JS", "CONSENT_JS", "ACTION_JS", "FIREBASE_AUTH"]


if __name__ == "__main__":
    for name in ("LOGIN_JS", "SIGNUP_JS", "CONSENT_JS", "ACTION_JS"):
        print(f"{name}: {len(globals()[name]):,}자")
