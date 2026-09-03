/* ============================================================
   KOSAI — 로그인 세션 표시 (전 페이지 공용)
   ------------------------------------------------------------
   각 페이지 헤더(#themeBtn 좌측)에 로그인 상태를 주입합니다.
   - 로그아웃 상태: "로그인" 링크 (현재 페이지로 되돌아오도록 ?next= 부여)
   - 로그인 상태: 아바타(이메일 첫 글자) + 드롭다운(이메일·로그아웃)
   firebase-config.js 설정 전(데모 모드)에는 로그인 링크만 표시합니다.
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
if(window.KOSi18n) window.KOSi18n.register({
  "로그인":"Sign in", "로그아웃":"Sign out", "회원 탈퇴":"Delete account",
  "설정":"Settings",
  "회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.":
    "Your account has been deleted. Thank you for using KOSAI.",
  "보안을 위해 다시 로그인하신 뒤 탈퇴를 진행하여 주시기 바랍니다.":
    "For security, please sign in again and then delete your account.",
  "탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.":
    "Something went wrong while deleting your account. Please try again later.",
  "정말 탈퇴하시겠어요?":"Delete your account?",
  "계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.":
    "Your account and saved watchlist will be permanently deleted. This cannot be undone.",
  "떠나시는 이유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)":
    "Telling us why helps us improve (select all that apply)",
  "원하는 종목·정보가 부족합니다":"Missing stocks or information I want",
  "정보가 정확하지 않습니다":"Information isn't accurate",
  "자주 이용하지 않습니다":"I don't use it often",
  "이용 방법이 불편합니다":"Hard to use",
  "기타":"Other",
  "자세한 의견 (선택)":"Tell us more (optional)",
  "위 내용을 이해했으며 되돌릴 수 없음에 동의합니다":
    "I understand this is permanent and cannot be undone",
  "확인을 위해 '탈퇴' 를 입력하여 주십시오":"Type ‘탈퇴’ to confirm",
  "탈퇴하기":"Delete account", "취소":"Cancel",
  "회원 탈퇴가 완료되었습니다":"Your account has been deleted",
  "그동안 이용해 주셔서 감사합니다.":"Thank you for using KOSAI.",
  "홈으로":"Go to home"
});

/* 회원 탈퇴 — 다단계 확인 모달:
   사유 설문(선택) → '되돌릴 수 없음' 동의 체크 → '탈퇴' 입력 시에만 버튼 활성화.
   확정 시: 사유를 이메일로 기록(best-effort) → 워치리스트 삭제 → 계정 삭제. */
const WD_REASONS = ["원하는 종목·정보가 부족합니다", "정보가 정확하지 않습니다",
                    "자주 이용하지 않습니다", "이용 방법이 불편합니다", "기타"];

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
      <div class="wd-q">${T("떠나시는 이유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)")}</div>
      <div class="wd-reasons">${WD_REASONS.map((r)=>
        `<label class="wd-r"><input type="checkbox" name="wdReason" value="${r}"><span>${T(r)}</span></label>`).join('')}</div>
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
  /* 사유는 여러 개 고를 수 있다. 떠나는 이유가 하나뿐인 경우는 드물다 —
     하나만 받으면 나머지는 듣지 못하고 사라진다. */
  const close = () => ov.remove();
  ov.querySelector('.wd-cancel').addEventListener('click', close);
  ov.addEventListener('click', e => { if(e.target === ov) close(); });
  go.addEventListener('click', async () => {
    go.disabled = true; go.textContent = '...';
    const reason = [...ov.querySelectorAll('input[name=wdReason]:checked')]
      .map((c) => c.value).join(', ');
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
    /* 탈퇴는 서버가 한다.

       전에는 여기서 클라이언트가 워치리스트·동의 기록·계정을 직접 지웠다.
       그런데 지워야 할 것이 그 셋만이 아니다 — 구독(subscriptions), 열람
       기록(report_reads), 그리고 결제가 남아 있으면 환불까지 서버에서
       처리해야 한다. 클라이언트가 지울 수 있는 것만 지우면 나머지가 유령으로
       남고, 창을 닫아 버리면 그마저도 중간에 멈춘다.

       deleteAccount 함수가 그 순서를 전부 갖고 있는데 아무도 부르지 않고
       있었다. 부른다. 환불이 실패하면 서버가 탈퇴를 진행하지 않고 오류를
       돌려준다 — 계정을 지운 뒤 환불이 실패하면 당사자는 로그인도 못 하는데
       돈은 우리가 들고 있는 상태가 되고, 되돌릴 방법이 없다. */
    const fns = getFunctions(app, "asia-northeast3");
    await httpsCallable(fns, "deleteAccount")({});
    try{ await signOut(auth); }catch(_){}
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
      alert(T("보안을 위해 다시 로그인하신 뒤 탈퇴를 진행하여 주시기 바랍니다."));
      try{ await signOut(auth); }catch(_){}
      location.href = "Login.html?next=" + encodeURIComponent(here());
    }else{
      alert(T("탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하여 주시기 바랍니다."));
      ov.remove();
    }
  }
}

const deleteAccount = openWithdrawModal;

/* 설정 패널의 '회원 탈퇴' 가 이걸 부른다. 확인 절차를 두 벌 만들지
   않으려고 화면은 여기 하나만 둔다. */
window.KOSAccount = { withdraw: openWithdrawModal };

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
  #navAuth .menu button,#navAuth .menu a{text-align:left;border:0;background:transparent;cursor:pointer;
    text-decoration:none;display:block;
    font:600 14px var(--font-sans);color:var(--fg-1);padding:10px;border-radius:8px}
  #navAuth .menu button:hover,#navAuth .menu a:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #navAuth .menu button:hover,
  :root[data-theme="dark"] #navAuth .menu a:hover{background:rgba(255,255,255,.08)}
  /* 모바일: 헤더 로그인/계정 숨기고 햄버거 메뉴 안으로 */
  @media(max-width:767px){#navAuth{display:none}}
  #mobileMenu #mAuth{border-top:1px solid var(--hair);margin-top:6px;padding-top:6px}
  #mobileMenu #mAuth .m-em{font:500 12px var(--font-sans);color:var(--fg-3);padding:8px 14px 2px;word-break:break-all}
  #mobileMenu #mAuth a,#mobileMenu #mAuth button{display:block;width:100%;text-align:left;border:0;background:transparent;
    cursor:pointer;font:600 16px var(--font-sans);color:var(--fg-1);text-decoration:none;padding:13px 14px;border-radius:var(--radius-sm)}
  #mobileMenu #mAuth a:hover,#mobileMenu #mAuth button:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #mobileMenu #mAuth a:hover,:root[data-theme="dark"] #mobileMenu #mAuth button:hover{background:rgba(255,255,255,.08)}
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
  .wd-r input{accent-color:#c0282b;width:18px;height:18px;flex:0 0 auto}
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
         <button type="button" class="settings">설정</button>
         <button type="button" class="logout">로그아웃</button>
       </div>
     </div>`;
  /* 이 메뉴에 '회원 탈퇴'가 같이 있었다. 설정 창 안에 이미 있으므로 같은 곳으로
     가는 문이 둘이 된 셈이다. 문이 둘이면 어느 쪽이 맞는지 고민하게 되고,
     나중에 한쪽만 고치게 된다. 여기는 계정 메뉴이지 설정 목차가 아니다 —
     설정으로 보내고 끝낸다.
     탈퇴 화면 자체는 이 파일이 계속 갖는다(window.KOSAccount.withdraw). */
  const acct = wrap.querySelector('.acct');
  wrap.querySelector('.acct-btn').addEventListener('click', e => { e.stopPropagation(); acct.classList.toggle('open'); });
  document.addEventListener('click', () => acct.classList.remove('open'));
  wrap.querySelector('.logout').addEventListener('click', async () => {
    try{ await signOut(auth); }catch(e){}
    location.href = 'Home.html';
  });
  wrap.querySelector('.settings').addEventListener('click', () => { acct.classList.remove('open'); openSettings(); });
  if(window.KOSi18n) window.KOSi18n.apply();
}

/* 설정은 지금 보던 화면 위에 창으로 띄운다. 리포트를 보다가 테마 한 번
   바꾸려고 페이지를 떠날 이유가 없다.

   settings-panel.js 는 여기서 정적으로 import 하지 않는다. 이 파일은 모든
   페이지에 실리는데, 설정 창은 눌러야 열린다. 누르는 순간 받아 온다. */
async function openSettings(){
  try{
    const m = await import("./settings-panel.js");
    m.openSettings();
  }catch(e){
    console.warn("[settings] 불러오지 못했습니다:", e && e.message);
    location.href = "Settings.html";   // 그래도 갈 곳은 남긴다
  }
}

function renderMobileAuth(user){
  const mm = document.getElementById('mobileMenu'); if(!mm || isAuthPage()) return;
  let el = document.getElementById('mAuth');
  if(!el){ el = document.createElement('div'); el.id = 'mAuth'; mm.appendChild(el); }
  if(user){
    const email = user.email || (user.displayName || '');
    // 데스크톱 메뉴와 같은 구성이다 — 한쪽에만 항목이 더 있으면 안내가 갈린다.
    el.innerHTML = `<div class="m-em">${email}</div><button type="button" class="m-settings">설정</button><button type="button" class="m-logout">로그아웃</button>`;
    el.querySelector('.m-settings').addEventListener('click', () => { mm.classList.remove('open'); openSettings(); });
    el.querySelector('.m-logout').addEventListener('click', async () => { try{ await signOut(auth); }catch(e){} location.href = 'Home.html'; });
  } else {
    el.innerHTML = `<a href="Login.html?next=${encodeURIComponent(here())}">로그인</a>`;
  }
  if(window.KOSi18n) window.KOSi18n.apply();
}

/* 동의를 가로막는 화면은 더 이상 없다.
   전에는 여기서 동의 기록이 없는 계정을 붙잡아 화면을 띄웠다. 로그인
   페이지로 들어오면 아무 동의 없이 계정이 만들어지던 구멍을 막으려던
   것이었다.

   그 구멍은 다른 방식으로 막았다. 구글·카카오·네이버는 각자 자기 동의
   화면을 보여 주고(카카오 '연결된 서비스', 네이버 '외부 사이트 연결',
   구글 myaccount.google.com/connections 에서 확인된다), 우리는 버튼 아래
   고지 문구로 받아 계정을 만드는 그 자리에서 기록한다. 이메일 가입은
   가입 페이지의 체크박스로 받는다.

   즉 계정이 만들어지는 네 길 모두 그 자리에서 동의가 남는다. 지나간 뒤에
   붙잡을 일이 없어졌다.

   ※ 나중에 CONSENT_VERSION 을 올려 기존 회원에게 새 동의를 받아야 할 때는
     여기 다시 넣는 것이 아니라 별도 안내 화면을 만드는 편이 낫다. 로그인
     하자마자 모달이 뜨는 건 그때도 좋은 방법이 아니다. */

/* 위 주석의 전제가 하나 깨졌다. 구글 가입은 팝업이 닫히는 순간 파이어베이스가
   계정을 먼저 만들고, 동의는 그 뒤 Consent.html 에서 받는다. 그 사이에 탭을
   닫으면 동의 기록 없는 계정이 남고, 다시 물어보는 자리가 없었다.
   (ensureConsent 가 consent.js 에 있었지만 아무도 부르지 않았다.)

   그래서 이 파일에 그물을 친다. 이 파일은 모든 페이지에서 돌기 때문이다.
   기록이 없으면 동의 페이지로 보낸다. 로그인 직후 모달을 띄우는 것과 다르다 —
   가입을 마치지 못한 사람에게만, 이미 가는 길이던 화면을 next 로 들고 간다.

   부르는 조건을 좁게 잡는다. 잘못 걸면 사이트를 못 쓰게 만드는 자리다.
     · 동의·로그인·가입 페이지에서는 하지 않는다 — 무한 이동이 된다.
     · 조회에 실패하면(null) 아무것도 하지 않는다. 통신이 끊겼다고 사람을
       가입 화면으로 몰아내면 안 된다. 확실히 '없다'(false)일 때만 보낸다.
     · 한 번만 시도한다. onAuthStateChanged 는 여러 번 울린다. */
/* Terms·Privacy 가 여기 꼭 있어야 한다. 동의 화면이 그 둘을 새 탭으로
   열어 주는데, 목록에서 빠뜨리면 열린 탭이 곧바로 동의 화면으로 되튕긴다.
   사용자 눈에는 '약관 보기 링크가 안 눌린다' 로 보였다 — 동의하라고
   보여 주는 문서를 정작 못 읽게 막고 있었던 것이다. */
const CONSENT_SKIP = /^(Consent|Login|Signup|auth-action|Terms|Privacy)\.html$/i;
let consentChecked = false;

/* 같은 탭에서 동의 화면으로 몇 번이나 보냈는지.

   ⚠️ 이 자리에서 무한 루프가 났다. 동의를 눌러 기록이 저장돼도 다른
      곳에서 그 기록이 다시 반쪽이 되면, 여기가 또 동의 화면으로 보낸다.
      사용자는 동의 → 화면 → 동의 → 화면 을 끝없이 반복하게 되고 사이트를
      아예 쓸 수 없다.

      그 원인(제공자 약관 맞추기가 반쪽 기록을 쓰던 것)은 따로 고쳤다.
      다만 원인을 하나 고쳤다고 이 자리를 그대로 두면, 다음에 또 어딘가가
      기록을 흐트러뜨렸을 때 같은 덫이 된다. 못 나가는 것보다는 못 물어보는
      편이 낫다 — 동의는 다음 접속에 다시 물어볼 수 있지만, 갇힌 사람은
      아무것도 할 수 없다.

   한 탭에서 한 번만 보낸다. 두 번째부터는 보내지 않고 콘솔에만 남긴다. */
const CONSENT_BOUNCE = "kos_consent_bounce";

async function guardConsent(user){
  if(consentChecked || !user || CONSENT_SKIP.test(here())) return;
  consentChecked = true;
  try{
    const { consentState } = await import("./consent.js");
    const state = await consentState(user.uid);
    if(state === true){
      /* 기록이 제자리를 찾았다. 다음에 정말로 필요해지면(약관 개정 등)
         다시 보낼 수 있도록 셈을 지운다. */
      try{ sessionStorage.removeItem(CONSENT_BOUNCE); }catch(e){}
      return;
    }
    if(state !== false) return;            // null — 못 읽었다. 건드리지 않는다

    let bounced = 0;
    try{ bounced = parseInt(sessionStorage.getItem(CONSENT_BOUNCE) || "0", 10) || 0; }catch(e){}
    if(bounced >= 1){
      console.warn("[consent] 동의 기록이 아직 없지만 이미 한 번 보냈다 —",
        "또 보내면 갇힌다. 이번엔 그냥 둔다.", user.uid);
      return;
    }
    try{ sessionStorage.setItem(CONSENT_BOUNCE, String(bounced + 1)); }catch(e){}

    /* 돌아갈 곳에 쿼리를 붙이지 않는다.

       전에는 here() + location.search 를 그대로 넣었다. 그러면 소셜 로그인
       직후처럼 주소에 ?code=… 가 남아 있을 때 그 인가코드까지 next 에
       실려 가고, 동의를 마친 뒤 그 주소로 되돌아가면 이미 써 버린 코드로
       로그인을 한 번 더 시도하게 된다. 돌아갈 곳은 페이지면 충분하다. */
    location.replace('Consent.html?next=' + encodeURIComponent(here()));
  }catch(e){ /* 표시·이동용 — 실패하면 그냥 둔다 */ }
}

function start(){
  const wrap = mount();
  if(!wrap) return;
  if(!isConfigured){ renderLoggedOut(wrap); renderMobileAuth(null); return; }
  onAuthStateChanged(auth, user => {
    user ? renderLoggedIn(wrap, user) : renderLoggedOut(wrap);
    renderMobileAuth(user);
    guardConsent(user);
  });
}

if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
