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
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
if(window.KOSi18n) window.KOSi18n.register({
  "로그인":"Sign in", "로그아웃":"Sign out", "회원 탈퇴":"Delete account",
  "회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.":
    "Your account has been deleted. Thank you for using KOSAI.",
  "보안을 위해 다시 로그인한 뒤 탈퇴를 진행해 주세요.":
    "For security, please sign in again and then delete your account.",
  "탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.":
    "Something went wrong while deleting your account. Please try again later.",
  "정말 탈퇴하시겠어요?":"Delete your account?",
  "계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.":
    "Your account and saved watchlist will be permanently deleted. This cannot be undone.",
  "떠나시는 이유를 알려주시면 개선에 큰 도움이 됩니다 (선택)":
    "Telling us why helps us improve (optional)",
  "원하는 종목·정보가 부족해요":"Missing stocks or information I want",
  "정보가 정확하지 않아요":"Information isn't accurate",
  "자주 사용하지 않아요":"I don't use it often",
  "사용법이 불편해요":"Hard to use",
  "기타":"Other",
  "자세한 의견 (선택)":"Tell us more (optional)",
  "위 내용을 이해했으며 되돌릴 수 없음에 동의합니다":
    "I understand this is permanent and cannot be undone",
  "확인을 위해 '탈퇴' 를 입력하세요":"Type ‘탈퇴’ to confirm",
  "탈퇴하기":"Delete account", "취소":"Cancel",
  "회원 탈퇴가 완료되었습니다":"Your account has been deleted",
  "그동안 이용해 주셔서 감사합니다.":"Thank you for using KOSAI.",
  "홈으로":"Go to home"
});

/* 회원 탈퇴 — 다단계 확인 모달:
   사유 설문(선택) → '되돌릴 수 없음' 동의 체크 → '탈퇴' 입력 시에만 버튼 활성화.
   확정 시: 사유를 이메일로 기록(best-effort) → 워치리스트 삭제 → 계정 삭제. */
const WD_REASONS = ["원하는 종목·정보가 부족해요", "정보가 정확하지 않아요",
                    "자주 사용하지 않아요", "사용법이 불편해요", "기타"];

function openWithdrawModal(){
  const user = auth.currentUser;
  if(!user) return;
  if(document.getElementById('wdModal')) return;
  injectCss();
  const email = user.email || user.displayName || '';
  const lang = (window.KOSi18n ? KOSi18n.lang : 'ko');
  const WORD = lang === 'en' ? 'DELETE' : '탈퇴';          // 언어별 확인 문구
  const typePlaceholder = lang === 'en'
    ? `Type ‘${WORD}’ to confirm` : `확인을 위해 ‘${WORD}’ 를 입력하세요`;
  const ov = document.createElement('div');
  ov.id = 'wdModal'; ov.className = 'wd-ov';
  ov.innerHTML = `
    <div class="wd-card" role="dialog" aria-modal="true">
      <div class="wd-h">${T("정말 탈퇴하시겠어요?")}</div>
      <div class="wd-em">${email}</div>
      <p class="wd-warn">${T("계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.")}</p>
      <div class="wd-q">${T("떠나시는 이유를 알려주시면 개선에 큰 도움이 됩니다 (선택)")}</div>
      <div class="wd-reasons">${WD_REASONS.map((r)=>
        `<label class="wd-r"><input type="radio" name="wdReason" value="${r}"><span>${T(r)}</span></label>`).join('')}</div>
      <textarea class="wd-detail" rows="2" placeholder="${T("자세한 의견 (선택)")}"></textarea>
      <label class="wd-ack"><input type="checkbox" id="wdAck"><span>${T("위 내용을 이해했으며 되돌릴 수 없음에 동의합니다")}</span></label>
      <input class="wd-type" id="wdType" type="text" autocomplete="off" placeholder="${typePlaceholder}">
      <div class="wd-actions">
        <button type="button" class="wd-cancel">${T("취소")}</button>
        <button type="button" class="wd-go" disabled>${T("탈퇴하기")}</button>
      </div>
    </div>`;
  document.body.appendChild(ov);
  const ack = ov.querySelector('#wdAck'), type = ov.querySelector('#wdType'), go = ov.querySelector('.wd-go');
  const sync = () => { go.disabled = !(ack.checked && type.value.trim() === WORD); };
  ack.addEventListener('change', sync); type.addEventListener('input', sync);
  const close = () => ov.remove();
  ov.querySelector('.wd-cancel').addEventListener('click', close);
  ov.addEventListener('click', e => { if(e.target === ov) close(); });
  go.addEventListener('click', async () => {
    go.disabled = true; go.textContent = '...';
    const reason = (ov.querySelector('input[name=wdReason]:checked') || {}).value || '';
    const detail = ov.querySelector('.wd-detail').value.trim();
    await finishWithdraw(user, email, reason, detail, ov);
  });
}

async function recordReason(email, reason, detail){
  if(!reason && !detail) return;
  try{
    const fns = getFunctions(app, "asia-northeast3");
    const msg = [reason && ("사유: " + reason), detail].filter(Boolean).join("\n");
    await httpsCallable(fns, "submitForm")({
      kind: "feedback", category: "회원 탈퇴", message: msg || "(사유 미기재)",
      email, page: "회원탈퇴"
    });
  }catch(_){ /* 사유 기록 실패해도 탈퇴는 진행 */ }
}

async function finishWithdraw(user, email, reason, detail, ov){
  try{
    await recordReason(email, reason, detail);
    try{ await deleteDoc(doc(getFirestore(app), "watchlists", user.uid)); }catch(e){}
    await deleteUser(user);
    // 완료 화면 — 자동으로 사라지지 않고, 사용자가 '홈으로'를 눌러야 닫힘
    ov.querySelector('.wd-card').innerHTML = `
      <div class="wd-done">
        <div class="wd-check"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg></div>
        <div class="wd-done-h">${T("회원 탈퇴가 완료되었습니다")}</div>
        <p class="wd-done-sub">${T("그동안 이용해 주셔서 감사합니다.")}</p>
        <button type="button" class="wd-home">${T("홈으로")}</button>
      </div>`;
    const home = () => { location.href = "Home.html"; };
    ov.querySelector('.wd-home').addEventListener('click', home);
    ov.onclick = e => { if(e.target === ov) home(); };
  }catch(e){
    if(e && e.code === "auth/requires-recent-login"){
      alert(T("보안을 위해 다시 로그인한 뒤 탈퇴를 진행해 주세요."));
      try{ await signOut(auth); }catch(_){}
      location.href = "Login.html?next=" + encodeURIComponent(here());
    }else{
      alert(T("탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."));
      ov.remove();
    }
  }
}

const deleteAccount = openWithdrawModal;

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
  :root[data-theme="dark"] #mobileMenu #mAuth button.m-withdraw{color:#ff8a8c}
  /* 회원 탈퇴 모달 */
  .wd-ov{position:fixed;inset:0;z-index:9999;display:flex;align-items:center;justify-content:center;
    background:rgba(10,12,20,.55);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px);padding:24px}
  .wd-card{width:100%;max-width:540px;max-height:90vh;overflow-y:auto;background:var(--bg-1,#fff);
    border:1px solid var(--border-2);border-radius:20px;box-shadow:0 28px 70px rgba(0,0,0,.4);padding:36px 34px}
  :root[data-theme="dark"] .wd-card{background:#1c1e2a}
  .wd-h{font:700 22px var(--font-sans);color:var(--fg-1);letter-spacing:-.02em}
  .wd-em{margin-top:6px;font:500 13px var(--font-sans);color:var(--fg-3);word-break:break-all}
  .wd-warn{margin:16px 0 0;font:400 14.5px/1.65 var(--font-sans);color:#c0282b}
  :root[data-theme="dark"] .wd-warn{color:#ff8a8c}
  .wd-q{margin:28px 0 10px;font:600 13.5px var(--font-sans);color:var(--fg-2)}
  .wd-reasons{display:flex;flex-direction:column;gap:3px}
  .wd-r{display:flex;align-items:center;gap:11px;padding:11px 10px;border-radius:10px;cursor:pointer;
    font:400 14.5px var(--font-sans);color:var(--fg-1)}
  .wd-r:hover{background:rgba(0,0,0,.04)}
  :root[data-theme="dark"] .wd-r:hover{background:rgba(255,255,255,.05)}
  .wd-r input{accent-color:var(--brand-blue);width:17px;height:17px;flex:0 0 auto}
  .wd-detail{width:100%;margin-top:12px;box-sizing:border-box;resize:vertical;border:1px solid var(--border-2);
    border-radius:12px;padding:12px 14px;font:400 14px var(--font-sans);color:var(--fg-1);background:transparent}
  .wd-ack{display:flex;align-items:flex-start;gap:11px;margin-top:26px;cursor:pointer;
    font:400 13.5px/1.55 var(--font-sans);color:var(--fg-2)}
  .wd-ack input{accent-color:#c0282b;width:18px;height:18px;flex:0 0 auto;margin-top:1px}
  .wd-type{width:100%;margin-top:14px;box-sizing:border-box;border:1px solid var(--border-2);border-radius:12px;
    padding:14px 15px;font:500 15px var(--font-sans);color:var(--fg-1);background:transparent}
  .wd-type:focus{outline:none;border-color:var(--brand-blue)}
  .wd-actions{display:flex;gap:10px;margin-top:26px}
  .wd-actions button{flex:1;border:0;border-radius:12px;padding:15px;cursor:pointer;font:600 15px var(--font-sans)}
  .wd-cancel{background:rgba(0,0,0,.06);color:var(--fg-1)}
  :root[data-theme="dark"] .wd-cancel{background:rgba(255,255,255,.1)}
  .wd-go{background:#c0282b;color:#fff}
  .wd-go:disabled{opacity:.4;cursor:not-allowed}
  /* 탈퇴 완료 화면 */
  .wd-done{display:flex;flex-direction:column;align-items:center;text-align:center;padding:18px 6px 6px}
  .wd-check{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    background:rgba(31,157,87,.12);color:#1f9d57;margin-bottom:20px}
  .wd-check svg{width:32px;height:32px}
  :root[data-theme="dark"] .wd-check{background:rgba(61,220,132,.15);color:#3ddc84}
  .wd-done-h{font:700 21px var(--font-sans);color:var(--fg-1);letter-spacing:-.02em}
  .wd-done-sub{margin:10px 0 0;font:400 14.5px/1.6 var(--font-sans);color:var(--fg-3)}
  .wd-home{margin-top:28px;width:100%;border:0;border-radius:12px;padding:15px;cursor:pointer;
    font:600 15px var(--font-sans);background:var(--brand-blue,#0d69d4);color:#fff}
  .wd-home:hover{filter:brightness(1.05)}`;
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
