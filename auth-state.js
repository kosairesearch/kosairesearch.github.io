/* ============================================================
   KOSAI — 로그인 세션 표시 (전 페이지 공용)
   ------------------------------------------------------------
   각 페이지 헤더(#themeBtn 좌측)에 로그인 상태를 주입합니다.
   - 로그아웃 상태: "로그인" 링크 (현재 페이지로 되돌아오도록 ?next= 부여)
   - 로그인 상태: 아바타(이메일 첫 글자) + 드롭다운(이메일·로그아웃)
   firebase-config.js 설정 전(데모 모드)에는 로그인 링크만 표시합니다.
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut, deleteUser }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, deleteDoc }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
if(window.KOSi18n) window.KOSi18n.register({
  "로그인":"Sign in", "로그아웃":"Sign out", "회원 탈퇴":"Delete account",
  "정말 회원 탈퇴하시겠어요?\n계정과 저장된 관심종목이 모두 삭제되며 되돌릴 수 없습니다.":
    "Delete your account?\nYour account and saved watchlist will be permanently removed. This cannot be undone.",
  "회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.":
    "Your account has been deleted. Thank you for using KOSAI.",
  "보안을 위해 다시 로그인한 뒤 탈퇴를 진행해 주세요.":
    "For security, please sign in again and then delete your account.",
  "탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.":
    "Something went wrong while deleting your account. Please try again later."
});

/* 회원 탈퇴: 워치리스트(Firestore) 삭제 → 계정 삭제 → 홈으로.
   Firebase 보안상 최근 로그인이 필요하면(requires-recent-login) 재로그인 안내. */
async function deleteAccount(){
  const user = auth.currentUser;
  if(!user) return;
  if(!confirm(T("정말 회원 탈퇴하시겠어요?\n계정과 저장된 관심종목이 모두 삭제되며 되돌릴 수 없습니다."))) return;
  try{
    try{ await deleteDoc(doc(getFirestore(app), "watchlists", user.uid)); }catch(e){}
    await deleteUser(user);
    alert(T("회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다."));
    location.href = "Home.html";
  }catch(e){
    if(e && e.code === "auth/requires-recent-login"){
      alert(T("보안을 위해 다시 로그인한 뒤 탈퇴를 진행해 주세요."));
      try{ await signOut(auth); }catch(_){}
      location.href = "Login.html?next=" + encodeURIComponent(here());
    }else{
      alert(T("탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."));
    }
  }
}

function injectCss(){
  if(document.getElementById('navAuthCss')) return;
  const st = document.createElement('style'); st.id = 'navAuthCss';
  st.textContent = `
  #navAuth{display:inline-flex;align-items:center;margin-right:2px}
  #navAuth .login-link{font:600 13px var(--font-sans);color:var(--fg-2);text-decoration:none;
    padding:8px 14px;border-radius:9999px;background:rgba(0,0,0,.05);transition:.15s;white-space:nowrap}
  #navAuth .login-link:hover{color:var(--fg-1)}
  :root[data-theme="dark"] #navAuth .login-link{background:rgba(255,255,255,.08)}
  #navAuth .acct{position:relative}
  #navAuth .acct-btn{display:inline-flex;align-items:center;border:0;background:transparent;cursor:pointer;
    padding:3px;border-radius:9999px;transition:.15s}
  #navAuth .acct-btn:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #navAuth .acct-btn:hover{background:rgba(255,255,255,.08)}
  #navAuth .avatar{width:30px;height:30px;border-radius:50%;color:#fff;
    background:linear-gradient(135deg,var(--brand-blue),var(--brand-cyan));
    font:700 13px var(--font-sans);display:flex;align-items:center;justify-content:center}
  #navAuth .menu{position:absolute;right:0;top:44px;min-width:210px;padding:8px;border-radius:14px;
    display:none;flex-direction:column;gap:2px;background:rgba(255,255,255,.92);
    border:1px solid var(--border-2);box-shadow:var(--shadow-2);
    -webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px)}
  :root[data-theme="dark"] #navAuth .menu{background:rgba(28,30,42,.92)}
  #navAuth .acct.open .menu{display:flex}
  #navAuth .menu .em{padding:9px 10px 10px;font:500 12px var(--font-sans);color:var(--fg-3);
    word-break:break-all;border-bottom:1px solid var(--hair);margin-bottom:4px}
  #navAuth .menu button{text-align:left;border:0;background:transparent;cursor:pointer;
    font:600 14px var(--font-sans);color:var(--fg-1);padding:10px;border-radius:8px}
  #navAuth .menu button:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #navAuth .menu button:hover{background:rgba(255,255,255,.08)}
  #navAuth .menu button.withdraw{color:#c0282b;font-weight:500;font-size:12.5px;margin-top:2px;border-top:1px solid var(--hair);border-radius:0 0 8px 8px}
  :root[data-theme="dark"] #navAuth .menu button.withdraw{color:#ff8a8c}
  /* 모바일: 헤더 로그인/계정 숨기고 햄버거 메뉴 안으로 */
  @media(max-width:767px){#navAuth{display:none}}
  #mobileMenu #mAuth{border-top:1px solid var(--hair);margin-top:6px;padding-top:6px}
  #mobileMenu #mAuth .m-em{font:500 12px var(--font-sans);color:var(--fg-3);padding:8px 14px 2px;word-break:break-all}
  #mobileMenu #mAuth a,#mobileMenu #mAuth button{display:block;width:100%;text-align:left;border:0;background:transparent;
    cursor:pointer;font:600 16px var(--font-sans);color:var(--fg-1);text-decoration:none;padding:13px 14px;border-radius:var(--radius-sm)}
  #mobileMenu #mAuth a:hover,#mobileMenu #mAuth button:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #mobileMenu #mAuth a:hover,:root[data-theme="dark"] #mobileMenu #mAuth button:hover{background:rgba(255,255,255,.08)}
  #mobileMenu #mAuth button.m-withdraw{color:#c0282b;font-size:14px}
  :root[data-theme="dark"] #mobileMenu #mAuth button.m-withdraw{color:#ff8a8c}`;
  document.head.appendChild(st);
}

function mount(){
  const theme = document.getElementById('themeBtn');
  if(!theme) return null;
  let wrap = document.getElementById('navAuth');
  if(wrap) return wrap;
  injectCss();
  wrap = document.createElement('div'); wrap.id = 'navAuth';
  const anchor = document.getElementById('langToggle') || theme;
  anchor.parentNode.insertBefore(wrap, anchor);
  return wrap;
}

function here(){ return location.pathname.split('/').pop() || 'Home.html'; }
function isAuthPage(){ return /^(Login|Signup)\.html$/i.test(here()); }

function renderLoggedOut(wrap){
  wrap.innerHTML = isAuthPage()
    ? ''
    : `<a class="login-link" href="Login.html?next=${encodeURIComponent(here())}">로그인</a>`;
  if(window.KOSi18n) window.KOSi18n.apply();
}

function renderLoggedIn(wrap, user){
  const email = user.email || (user.displayName || '');
  const initial = (email.trim()[0] || 'U').toUpperCase();
  wrap.innerHTML =
    `<div class="acct">
       <button class="acct-btn" type="button" aria-label="account"><span class="avatar">${initial}</span></button>
       <div class="menu" role="menu">
         <div class="em">${email}</div>
         <button type="button" class="logout">로그아웃</button>
         <button type="button" class="withdraw">회원 탈퇴</button>
       </div>
     </div>`;
  const acct = wrap.querySelector('.acct');
  wrap.querySelector('.acct-btn').addEventListener('click', e => { e.stopPropagation(); acct.classList.toggle('open'); });
  document.addEventListener('click', () => acct.classList.remove('open'));
  wrap.querySelector('.logout').addEventListener('click', async () => {
    try{ await signOut(auth); }catch(e){}
    location.href = 'Home.html';
  });
  wrap.querySelector('.withdraw').addEventListener('click', deleteAccount);
  if(window.KOSi18n) window.KOSi18n.apply();
}

function renderMobileAuth(user){
  const mm = document.getElementById('mobileMenu'); if(!mm || isAuthPage()) return;
  let el = document.getElementById('mAuth');
  if(!el){ el = document.createElement('div'); el.id = 'mAuth'; mm.appendChild(el); }
  if(user){
    const email = user.email || (user.displayName || '');
    el.innerHTML = `<div class="m-em">${email}</div><button type="button" class="m-logout">로그아웃</button><button type="button" class="m-withdraw">회원 탈퇴</button>`;
    el.querySelector('.m-logout').addEventListener('click', async () => { try{ await signOut(auth); }catch(e){} location.href = 'Home.html'; });
    el.querySelector('.m-withdraw').addEventListener('click', deleteAccount);
  } else {
    el.innerHTML = `<a href="Login.html?next=${encodeURIComponent(here())}">로그인</a>`;
  }
  if(window.KOSi18n) window.KOSi18n.apply();
}

function start(){
  const wrap = mount();
  if(!wrap) return;
  if(!isConfigured){ renderLoggedOut(wrap); renderMobileAuth(null); return; }
  onAuthStateChanged(auth, user => { user ? renderLoggedIn(wrap, user) : renderLoggedOut(wrap); renderMobileAuth(user); });
}

if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
