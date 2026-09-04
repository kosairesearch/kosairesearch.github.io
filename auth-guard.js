/* ============================================================
   KOSAI — 로그인 게이트 (비로그인 차단)
   ------------------------------------------------------------
   1) 보호 페이지(워치리스트)는 로그인해야 이용할 수 있습니다.
      (종목 상세·업종 분석은 SEO를 위해 공개 — 게이트 없음)
      <head> 의 인라인 스크립트가 먼저 body 를 숨기고(html.kos-locked),
      이 모듈이 로그인 상태를 확인해 통과(unlock) 또는 게이트(lockPage) 처리합니다.
   2) window.KOSGate.showLoginPopup(msg) — 워치리스트 추가 등 액션 차단용 팝업.
   ============================================================ */
import { auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { sendVerifyEmail } from "./auth-emails.js";

if(window.KOSi18n) window.KOSi18n.register({
  "로그인이 필요합니다":"Sign-in required",
  "이 리포트는 로그인 후 열람하실 수 있습니다.":"Please sign in to view this report.",
  "이 기능은 로그인 후 이용하실 수 있습니다.":"Please sign in to use this feature.",
  "워치리스트에 추가하시려면 로그인이 필요합니다.":"Please sign in to add to your watchlist.",
  "이메일 인증 후 워치리스트를 이용하실 수 있습니다.":"Verify your email to use the watchlist.",
  "로그인":"Sign in", "회원가입":"Sign up", "홈으로":"Back to home",
  "이메일 인증이 필요합니다":"Email verification required",
  "받으신 메일의 링크를 눌러 이메일 인증을 완료하여 주시기 바랍니다.":"Please click the link in the email we sent to verify your address.",
  "인증 메일 다시 보내기":"Resend verification email",
  "인증을 완료했습니다":"I've verified — refresh",
  "인증 메일을 다시 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.":"Verification email resent. Please check your inbox.",
  "보내지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.":"Couldn't send. Please try again in a moment.",
  "로그아웃":"Sign out"
});

function pwOnly(u){ return !!(u && u.providerData && u.providerData.length && u.providerData.every(function(p){ return p.providerId === 'password'; })); }
function verified(u){ return !pwOnly(u) || u.emailVerified; }

function here(){ return location.pathname.split('/').pop() || 'Home.html'; }
function nextParam(){ try{ return encodeURIComponent(decodeURIComponent(here())); }catch(e){ return encodeURIComponent(here()); } }

function injectCss(){
  if(document.getElementById('kosGateCss')) return;
  var st = document.createElement('style'); st.id = 'kosGateCss';
  st.textContent = `
  .kg-overlay{position:fixed;inset:0;z-index:99999;display:flex;align-items:center;justify-content:center;padding:24px;
    visibility:visible;background:rgba(247,248,252,.94);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
  :root[data-theme="dark"] .kg-overlay{background:rgba(13,15,23,.94)}
  .kg-overlay.kg-dismiss{background:rgba(15,17,25,.5)}
  .kg-card{width:min(92vw,384px);padding:36px 28px 28px;border-radius:22px;text-align:center;position:relative;
    background:rgba(255,255,255,.9);border:1px solid rgba(0,0,0,.06);box-shadow:0 24px 64px rgba(15,23,42,.22);
    -webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)}
  :root[data-theme="dark"] .kg-card{background:rgba(28,30,42,.94);border-color:rgba(255,255,255,.08)}
  .kg-ico{width:60px;height:60px;margin:0 auto 16px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    background:linear-gradient(135deg,var(--brand-blue,#2f6df6),var(--brand-cyan,#22b8cf))}
  .kg-ico svg{width:28px;height:28px;stroke:#fff;fill:none;stroke-width:2}
  .kg-title{font:800 21px/1.3 var(--font-sans,system-ui),sans-serif;margin:0 0 8px;color:var(--fg-1,#0c0d10)}
  .kg-sub{font:500 14px/1.6 var(--font-sans,system-ui),sans-serif;color:var(--fg-3,#6b7280);margin:0 0 22px}
  .kg-btns{display:flex;flex-direction:column;gap:10px}
  .kg-btn{display:block;padding:13px;border-radius:12px;font:700 15px var(--font-sans,system-ui),sans-serif;
    text-decoration:none;cursor:pointer;border:1px solid rgba(0,0,0,.1);color:var(--fg-1,#0c0d10);background:rgba(0,0,0,.03)}
  .kg-btn:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] .kg-btn{border-color:rgba(255,255,255,.14);color:#fff;background:rgba(255,255,255,.06)}
  :root[data-theme="dark"] .kg-btn:hover{background:rgba(255,255,255,.1)}
  .kg-primary,.kg-primary:hover{background:linear-gradient(135deg,var(--brand-blue,#2f6df6),var(--brand-cyan,#22b8cf));border:0;color:#fff}
  .kg-home{display:inline-block;margin-top:16px;font:600 13px var(--font-sans,system-ui),sans-serif;color:var(--fg-3,#6b7280);text-decoration:none}
  .kg-home:hover{color:var(--fg-1,#0c0d10)}
  .kg-x{position:absolute;top:12px;right:14px;border:0;background:transparent;font-size:20px;line-height:1;cursor:pointer;color:var(--fg-3,#6b7280)}`;
  document.head.appendChild(st);
}

var LOCK_SVG = '<svg viewBox="0 0 24 24"><rect x="4.5" y="10.5" width="15" height="10" rx="2.2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/></svg>';
var MAIL_SVG = '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2.2"/><path d="m4 7 8 6 8-6"/></svg>';

function buildCard(opts){
  injectCss();
  var n = nextParam();
  var card = document.createElement('div');
  card.className = 'kg-card';
  card.innerHTML =
    (opts.dismissable ? '<button class="kg-x" type="button" aria-label="' + tt('홈으로') + '">✕</button>' : '') +
    '<div class="kg-ico">' + LOCK_SVG + '</div>' +
    '<h2 class="kg-title">' + tt('로그인이 필요합니다') + '</h2>' +
    '<p class="kg-sub">' + tt(opts.msg) + '</p>' +
    '<div class="kg-btns">' +
      '<a class="kg-btn kg-primary" href="Login.html?next=' + n + '">' + tt('로그인') + '</a>' +
      '<a class="kg-btn" href="Signup.html?next=' + n + '">' + tt('회원가입') + '</a>' +
    '</div>' +
    (opts.dismissable ? '' : '<a class="kg-home" href="Home.html">' + tt('홈으로') + '</a>');
  return card;
}
function tt(m){ return (window.KOSi18n ? window.KOSi18n.t(m) : m); }

function clearGate(){ var g=document.getElementById('kosGate'); if(g) g.remove(); }

function lockPage(msg){
  clearGate();
  var ov = document.createElement('div');
  ov.id = 'kosGate'; ov.className = 'kg-overlay';
  ov.appendChild(buildCard({ dismissable:false, msg: msg || '이 리포트는 로그인 후 열람하실 수 있습니다.' }));
  document.body.appendChild(ov);
  if(window.KOSi18n) window.KOSi18n.apply();
}

function lockVerify(user){
  clearGate();
  injectCss();
  var ov = document.createElement('div'); ov.id='kosGate'; ov.className='kg-overlay';
  var card = document.createElement('div'); card.className='kg-card';
  card.innerHTML =
    '<div class="kg-ico">' + MAIL_SVG + '</div>' +
    '<h2 class="kg-title">' + tt('이메일 인증이 필요합니다') + '</h2>' +
    '<p class="kg-sub">' + tt('받으신 메일의 링크를 눌러 이메일 인증을 완료하여 주시기 바랍니다.') + '</p>' +
    '<div class="kg-btns">' +
      '<button class="kg-btn kg-primary" id="kgResend" type="button">' + tt('인증 메일 다시 보내기') + '</button>' +
      '<button class="kg-btn" id="kgRefresh" type="button">' + tt('인증을 완료했습니다') + '</button>' +
    '</div>' +
    '<a class="kg-home" href="#" id="kgLogout">' + tt('로그아웃') + '</a>';
  ov.appendChild(card); document.body.appendChild(ov);
  if(window.KOSi18n) window.KOSi18n.apply();
  card.querySelector('#kgResend').addEventListener('click', async function(){
    /* 실패를 삼키지 않는다. catch(e){} 였을 때는 눌러도 아무 일이 안
       일어나고 이유도 안 보였다 — 사람은 고장 난 줄 알고 계속 누른다.
       메일 횟수 제한이 걸리면 서버가 '약 N분 뒤에' 를 문장으로 보내 주므로
       그것을 그대로 보여 준다. */
    const btn = this;
    btn.disabled = true;
    try{
      await sendVerifyEmail(user.email);
      btn.textContent = tt('인증 메일을 다시 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.');
    }catch(e){
      btn.disabled = false;
      btn.textContent = (e && e.code === 'functions/resource-exhausted' && e.message)
        ? e.message
        : tt('보내지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.');
    }
  });
  card.querySelector('#kgRefresh').addEventListener('click', async function(){
    try{ await user.reload(); }catch(e){}
    if(user.emailVerified) location.reload();
  });
  card.querySelector('#kgLogout').addEventListener('click', async function(e){
    e.preventDefault(); try{ await signOut(auth); }catch(e2){} location.href = 'Login.html';
  });
}

function showLoginPopup(msg){
  var ex = document.getElementById('kosPopup'); if(ex) ex.remove();
  var ov = document.createElement('div');
  ov.id = 'kosPopup'; ov.className = 'kg-overlay kg-dismiss';
  ov.appendChild(buildCard({ dismissable:true, msg: msg || '워치리스트에 추가하시려면 로그인이 필요합니다.' }));
  document.body.appendChild(ov);
  function close(){ ov.remove(); }
  ov.addEventListener('click', function(e){ if(e.target === ov) close(); });
  var x = ov.querySelector('.kg-x'); if(x) x.addEventListener('click', close);
  if(window.KOSi18n) window.KOSi18n.apply();
}

function unlock(){ clearGate(); document.documentElement.classList.remove('kos-locked'); }

window.KOSGate = { showLoginPopup: showLoginPopup, lockPage: lockPage };

/* ---- 페이지 보호 ---- */
var GATED = /^(watchlist)\.html$/i;
var page;
try{ page = decodeURIComponent(here()); }catch(e){ page = here(); }

if(GATED.test(page)){
  if(!isConfigured){ unlock(); }
  else onAuthStateChanged(auth, function(u){
    if(!u){ lockPage('이 기능은 로그인 후 이용하실 수 있습니다.'); }
    else if(verified(u)){ unlock(); }
    else { lockVerify(u); }
  });
} else {
  // 공개 페이지(종목·업종 포함): 콘텐츠 게이트 없이 즉시 잠금 해제
  unlock();
}
