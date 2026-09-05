/* ============================================================
   KOSAI — 로그인 세션 표시 (전 페이지 공용)
   ------------------------------------------------------------
   각 페이지 헤더(#themeBtn 좌측)에 로그인 상태를 주입합니다.
   - 로그아웃 상태: "로그인" 링크 (현재 페이지로 되돌아오도록 ?next= 부여)
   - 로그인 상태: 아바타(이메일 첫 글자) + 드롭다운(이메일·로그아웃)
   firebase-config.js 설정 전(데모 모드)에는 로그인 링크만 표시합니다.
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js?v=7b8f27a5";
import { onAuthStateChanged, signOut, deleteUser }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, getDoc, deleteDoc }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
if(window.KOSi18n) window.KOSi18n.register({
  "로그인":"Sign in", "로그아웃":"Sign out", "회원 탈퇴":"Delete account", "구독 관리":"Subscription",
  "회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.":
    "Your account has been deleted. Thank you for using KOSAI.",
  "보안을 위해 다시 로그인하신 뒤 탈퇴를 진행하여 주시기 바랍니다.":
    "For security, please sign in again and then delete your account.",
  "탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.":
    "Something went wrong while deleting your account. Please try again later.",
  "정말 탈퇴하시겠습니까?":"Delete your account?",
  "이용 중인 구독이 있습니다":"You have an active subscription",
  "탈퇴하시면 구독이 즉시 해지되고, 환불 기준에 따라 산정된 금액이 자동으로 환불됩니다. 오늘 리포트를 열람하셨다면 오늘은 이용일로 차감되며, 계정이 삭제되므로 오늘 남은 열람은 사용하실 수 없습니다. 금액을 먼저 확인하시거나 오늘 남은 열람을 사용하신 뒤 나가시려면 구독 관리에서 환불을 신청하여 주시기 바랍니다.":
    "Deleting your account cancels the subscription right away and refunds the amount due under our refund terms. If you opened a report today, today counts as a used day, and because the account is deleted you cannot use the rest of today's limit. To see the amount first, or to use the rest of today before leaving, request the refund under Subscription instead.",
  "구독 관리로 이동":"Go to subscription",
  "환불을 처리하지 못하여 탈퇴를 진행하지 않았습니다. 구독 관리에서 환불을 먼저 신청하여 주시기 바랍니다.":
    "We could not process the refund, so your account was not deleted. Please request the refund on the subscription page first.",
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
   확정 시: 사유 기록(best-effort) → 서버 deleteAccount 호출.

   ⚠️ 삭제는 서버가 한다. 여기서 deleteUser() 만 부르면 계정은 사라지는데
      구독 문서는 살아 있어, 매일 도는 갱신 배치가 다음 달에도 카드를 긁는다.
      당사자는 로그인도 해지도 못 한다. 서버 함수가 구독을 먼저 닫는다. */
const WD_REASONS = ["원하는 종목·정보가 부족합니다", "정보가 정확하지 않습니다",
                    "자주 이용하지 않습니다", "이용 방법이 불편합니다", "기타"];

/* 지금 유료 구독 중인가. 탈퇴하면 남은 기간을 잃으므로 미리 알려야 한다.
   실패하면(규칙·네트워크) 경고만 못 붙일 뿐, 탈퇴 자체는 서버가 안전하게 처리한다. */
async function activeSub(uid){
  if (window.__KOSDEMO) {
    var st = window.KOSPaywall && window.KOSPaywall.state();
    return st && st.active ? st.sub : null;
  }
  try{
    const snap = await getDoc(doc(getFirestore(app), "subscriptions", uid));
    const s = snap.exists() ? snap.data() : null;
    if(!s || s.status !== "active") return null;
    const end = s.currentPeriodEnd;
    const ms = end && typeof end.toMillis === "function" ? end.toMillis()
             : typeof end === "number" ? end : Date.parse(end);
    return (Number.isFinite(ms) && ms > Date.now()) ? s : null;
  }catch(e){ return null; }
}

async function openWithdrawModal(){
  const user = auth.currentUser;
  if(!user) return;
  if(document.getElementById('wdModal')) return;
  injectCss();
  const sub = await activeSub(user.uid);
  const email = user.email || user.displayName || '';
  const lang = (window.KOSi18n ? KOSi18n.lang : 'ko');
  const WORD = lang === 'en' ? 'DELETE' : '탈퇴';          // 언어별 확인 문구
  const typePlaceholder = lang === 'en'
    ? `Type ‘${WORD}’ to confirm` : `확인을 위해 ‘${WORD}’ 를 입력하십시오`;
  const ov = document.createElement('div');
  ov.id = 'wdModal'; ov.className = 'wd-ov';
  ov.innerHTML = `
    <div class="wd-card" role="dialog" aria-modal="true">
      <div class="wd-h">${T("정말 탈퇴하시겠습니까?")}</div>
      <div class="wd-em"></div>
      <p class="wd-warn">${T("계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.")}</p>
      ${sub ? `<div class="wd-sub">
        <b>${T("이용 중인 구독이 있습니다")}</b>
        <p>${T("탈퇴하시면 구독이 즉시 해지되고, 환불 기준에 따라 산정된 금액이 자동으로 환불됩니다. 오늘 리포트를 열람하셨다면 오늘은 이용일로 차감되며, 계정이 삭제되므로 오늘 남은 열람은 사용하실 수 없습니다. 금액을 먼저 확인하시거나 오늘 남은 열람을 사용하신 뒤 나가시려면 구독 관리에서 환불을 신청하여 주시기 바랍니다.")}</p>
        <button type="button" class="wd-tosubs">${T("구독 관리로 이동")}</button>
      </div>` : ""}
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
  ov.querySelector('.wd-em').textContent = email;
  document.body.appendChild(ov);
  const ack = ov.querySelector('#wdAck'), type = ov.querySelector('#wdType'), go = ov.querySelector('.wd-go');
  const sync = () => { go.disabled = !(ack.checked && type.value.trim() === WORD); };
  ack.addEventListener('change', sync); type.addEventListener('input', sync);
  /* 사유는 여러 개 고를 수 있다. 떠나는 이유가 하나뿐인 경우는 드물다 —
     하나만 받으면 나머지는 듣지 못하고 사라진다. */
  const close = () => ov.remove();
  ov.querySelector('.wd-cancel').addEventListener('click', close);
  ov.addEventListener('click', e => { if(e.target === ov) close(); });
  /* 페이지를 옮기지 않고 이 자리에서 구독 칸을 편다. 환불 금액을 보러
     갔다가 돌아오는 길이 없으면 대부분 그냥 나가 버린다. */
  const toSubs = ov.querySelector('.wd-tosubs');
  if(toSubs) toSubs.addEventListener('click', () => { close(); openSettings('subscription'); });
  go.addEventListener('click', async () => {
    go.disabled = true; go.textContent = '...';
    const reason = [...ov.querySelectorAll('input[name=wdReason]:checked')]
      .map((c) => c.value).join(', ');
    const detail = ov.querySelector('.wd-detail').value.trim();
    await finishWithdraw(user, email, reason, detail, ov, !!sub);
  });
}

async function recordReason(email, reason, detail){
  if(!reason && !detail) return;
  if (window.__KOSDEMO) {
    await window.KOSDemo.call("submitForm", { kind: "feedback", category: "회원 탈퇴",
      message: [reason && ("사유: " + reason), detail].filter(Boolean).join("\n"),
      email, page: "회원탈퇴" });
    return;
  }
  try{
    const fns = getFunctions(app, "asia-northeast3");
    const msg = [reason && ("사유: " + reason), detail].filter(Boolean).join("\n");
    await httpsCallable(fns, "submitForm")({
      kind: "feedback", category: "회원 탈퇴", message: msg || "(사유 미기재)",
      email, page: "회원탈퇴"
    });
  }catch(_){ /* 사유 기록 실패해도 탈퇴는 진행 */ }
}

async function finishWithdraw(user, email, reason, detail, ov, hadSub){
  try{
    await recordReason(email, reason, detail);
    try{
      const fns = getFunctions(app, "asia-northeast3");
      if (window.__KOSDEMO) await window.KOSDemo.call('deleteAccount');
      else await httpsCallable(fns, "deleteAccount")({});
      try{ await signOut(auth); }catch(_){}    // 계정은 서버가 지웠다 — 토큰만 정리
    }catch(e){
      /* 함수가 아직 배포되지 않은 환경에서는 예전 방식으로 돌아간다. 단 구독이
         있으면 절대 안 된다 — 계정만 지우면 카드가 계속 긁힌다. */
      if(hadSub || window.__KOSDEMO) throw e;
      try{ await deleteDoc(doc(getFirestore(app), "watchlists", user.uid)); }catch(_){}
      await deleteUser(user);
    }
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
      // 서버가 이유를 준 경우(예: 환불 실패로 탈퇴 중단) 그대로 보여 준다.
      const msg = (e && e.message && /환불|refund/i.test(e.message))
        ? e.message : T("탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.");
      alert(msg);
      ov.remove();
    }
  }
}

/* 탈퇴 화면은 이 파일 하나만 갖는다. 설정 창의 '회원 탈퇴' 도 여기로 온다 —
   저쪽에서 다시 만들면 확인 절차가 두 벌이 되고, 구독이 살아 있을 때 막는
   규칙을 한쪽에만 고치게 된다. */
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
  #navAuth .menu .mi{display:block;text-decoration:none;color:inherit}
  #navAuth .menu button,#navAuth .menu .mi{text-align:left;border:0;background:transparent;cursor:pointer;
    font:600 14px var(--font-sans);color:var(--fg-1);padding:10px;border-radius:8px}
  #navAuth .menu button:hover,#navAuth .menu .mi:hover{background:rgba(0,0,0,.06)}
  :root[data-theme="dark"] #navAuth .menu button:hover,:root[data-theme="dark"] #navAuth .menu .mi:hover{background:rgba(255,255,255,.08)}
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
.wd-sub{margin:12px 0 0;padding:12px 14px;border-radius:12px;text-align:left;
  background:rgba(220,120,20,.10);border:1px solid rgba(220,120,20,.28)}
.wd-sub b{display:block;font:700 13px var(--font-sans);color:var(--fg-1)}
.wd-sub p{margin:5px 0 0;font:400 12.5px/1.6 var(--font-sans);color:var(--fg-2);word-break:keep-all}
.wd-sub a,.wd-sub .wd-tosubs{display:inline-block;margin-top:8px;font:600 12.5px var(--font-sans);
  color:var(--fg-1);border:0;background:transparent;padding:0;cursor:pointer;
  text-decoration:underline;text-underline-offset:3px}
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
       <button class="acct-btn" type="button" aria-label="account"><span class="avatar"></span></button>
       <div class="menu" role="menu">
         <div class="em"></div>
         <button type="button" class="settings">설정</button>
         <button type="button" class="logout">로그아웃</button>
       </div>
     </div>`;
  /* 이 메뉴에 '구독 관리'와 '회원 탈퇴'가 같이 있었다. 둘 다 설정 창 안에
     들어갔으므로 같은 곳으로 가는 문이 둘이 된 셈이다. 문이 둘이면 어느 쪽이
     맞는지 고민하게 되고, 나중에 한쪽만 고치게 된다. 여기는 계정 메뉴이지
     설정 목차가 아니다 — 설정으로 보내고 끝낸다.
     탈퇴 화면 자체는 이 파일이 계속 갖는다(window.KOSAccount.withdraw). */
  wrap.querySelector('.avatar').textContent = initial;
  wrap.querySelector('.em').textContent = email;
  const acct = wrap.querySelector('.acct');
  wrap.querySelector('.acct-btn').addEventListener('click', e => { e.stopPropagation(); acct.classList.toggle('open'); });
  document.addEventListener('click', () => acct.classList.remove('open'));
  wrap.querySelector('.settings').addEventListener('click', () => { acct.classList.remove('open'); openSettings(); });
  wrap.querySelector('.logout').addEventListener('click', async () => {
    try{ await signOut(auth); }catch(e){}
    location.href = 'Home.html';
  });
  if(window.KOSi18n) window.KOSi18n.apply();
}

/* settings-panel.js 는 여기서 정적으로 import 하지 않는다. 이 파일은 모든
   페이지에 실리므로, 설정을 한 번도 안 여는 사람에게까지 받게 할 이유가 없다. */
async function openSettings(tab){
  try{
    const m = await import("./settings-panel.js?v=612ebfbf");
    m.openSettings(tab);
  }catch(e){ console.warn("[settings] 열지 못했습니다", e && e.message); }
}

function renderMobileAuth(user){
  const mm = document.getElementById('mobileMenu'); if(!mm || isAuthPage()) return;
  let el = document.getElementById('mAuth');
  if(!el){ el = document.createElement('div'); el.id = 'mAuth'; mm.appendChild(el); }
  if(user){
    const email = user.email || (user.displayName || '');
    // 데스크톱 메뉴와 같은 구성이다 — 한쪽에만 항목이 더 있으면 안내가 갈린다.
    el.innerHTML = `<div class="m-em"></div><button type="button" class="m-settings">설정</button><button type="button" class="m-logout">로그아웃</button>`;
    el.querySelector('.m-em').textContent = email;
    el.querySelector('.m-settings').addEventListener('click', () => { mm.classList.remove('open'); openSettings(); });
    el.querySelector('.m-logout').addEventListener('click', async () => { try{ await signOut(auth); }catch(e){} location.href = 'Home.html'; });
  } else {
    el.innerHTML = `<a href="Login.html?next=${encodeURIComponent(here())}">로그인</a>`;
  }
  if(window.KOSi18n) window.KOSi18n.apply();
}

function start(){
  const wrap = mount();
  if(!wrap) return;
  if(!isConfigured){ renderLoggedOut(wrap); renderMobileAuth(null); return; }
  onAuthStateChanged(auth, user => {
    /* 이 브라우저가 로그인 상태였는지 표시해 둔다. 워치리스트는 인증이 끝날
       때까지 화면을 감추는데, 이 값이 있으면 감추지 않고 바로 그린다 — 그래야
       그 페이지만 깜빡이지 않는다. */
    try{ user ? localStorage.setItem('kos-signed','1') : localStorage.removeItem('kos-signed'); }catch(e){}
    user ? renderLoggedIn(wrap, user) : renderLoggedOut(wrap); renderMobileAuth(user);
    autoOpenSettings(user);
  });
}

/* 주소에 ?settings=구독 이 붙어 오면 그 칸을 펴서 창을 연다.

   billing.html 이 여기로 보낸다. 결제를 마치고 돌아오는 길도 같다 —
   그때는 ?card=1 이 함께 오고, 설정 창이 '카드가 바뀌었습니다' 를 띄운다.

   한 번만 연다. 창을 닫고 새로고침했는데 또 열리면 닫을 수가 없다.
   그래서 주소에서 표시를 지운다. */
let settingsOpened = false;
function autoOpenSettings(user){
  if(settingsOpened || !user) return;
  const q = new URLSearchParams(location.search);
  const tab = q.get('settings');
  if(!tab) return;
  settingsOpened = true;
  /* 주소에서 지우기 전에 넘겨 둔다. 지운 뒤에 읽으면 안내가 안 뜬다. */
  if(q.get('card')) window.__KOS_CARD_NOTICE = true;
  try{
    const u = new URL(location.href);
    u.searchParams.delete('settings');
    u.searchParams.delete('card');
    history.replaceState(null, '', u.pathname + (u.search || '') + u.hash);
  }catch(e){}
  openSettings(tab);
}

if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
