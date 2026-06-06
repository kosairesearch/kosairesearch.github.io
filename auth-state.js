/* ============================================================
   KOS ai — 로그인 세션 표시 (전 페이지 공용)
   ------------------------------------------------------------
   각 페이지 헤더(#themeBtn 좌측)에 로그인 상태를 주입합니다.
   - 로그아웃 상태: "로그인" 링크 (현재 페이지로 되돌아오도록 ?next= 부여)
   - 로그인 상태: 아바타(이메일 첫 글자) + 드롭다운(이메일·로그아웃)
   firebase-config.js 설정 전(데모 모드)에는 로그인 링크만 표시합니다.
   ============================================================ */
import { auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
if(window.KOSi18n) window.KOSi18n.register({ "로그인":"Sign in", "로그아웃":"Sign out" });

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
  :root[data-theme="dark"] #navAuth .menu button:hover{background:rgba(255,255,255,.08)}`;
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
       </div>
     </div>`;
  const acct = wrap.querySelector('.acct');
  wrap.querySelector('.acct-btn').addEventListener('click', e => { e.stopPropagation(); acct.classList.toggle('open'); });
  document.addEventListener('click', () => acct.classList.remove('open'));
  wrap.querySelector('.logout').addEventListener('click', async () => {
    try{ await signOut(auth); }catch(e){}
    location.href = 'Home.html';
  });
  if(window.KOSi18n) window.KOSi18n.apply();
}

function start(){
  const wrap = mount();
  if(!wrap) return;
  if(!isConfigured){ renderLoggedOut(wrap); return; }
  onAuthStateChanged(auth, user => user ? renderLoggedIn(wrap, user) : renderLoggedOut(wrap));
}

if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
