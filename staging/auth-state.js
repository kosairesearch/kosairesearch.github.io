/* ============================================================
   KOSAI — 로그인 세션 표시 (전 페이지 공용 · 새 헤더용)
   ------------------------------------------------------------
   헤더 오른쪽(#navRight)에는 정적 '로그인' 링크(a.login)와 빈 계정 칸(#acct)이
   있고, 휴대폰 메뉴(#mmenu)에는 #mauth 가 있다(scripts/comp_common.py · nav()).
   이 파일은 그 세 자리를 로그인 상태에 맞게 채운다.

   - 로그아웃: a.login 은 그대로 두고 href 에 ?next=(지금 페이지) 만 붙인다.
               #mauth 에는 '로그인' · '회원가입'.
   - 로그인:   #navRight 에 user, #acct 에 show 를 붙이고 아바타(머리글자) +
               드롭다운(이메일 · 설정 · 로그아웃)을 넣는다. #mauth 에는 '설정' · '로그아웃'.

   옷(CSS)은 페이지가 갖고 있다(.acct · .avatar · .acct-menu · .mm-auth ·
   .right.user .login). 이 파일이 넣는 CSS 는 회원 탈퇴 창 하나뿐이다.
   설정은 창이 아니라 페이지(Settings.html?tab=…)다.
   firebase-config.js 설정 전(데모 모드)에는 로그아웃 상태만 그린다.
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js?v=7b8f27a5";
import { onAuthStateChanged, signOut, deleteUser }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, getDoc, deleteDoc }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

/* 새 페이지에는 KOSi18n 이 없을 수 있다. 있을 때만 쓴다. */
const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
function applyI18n(){ if(window.KOSi18n && typeof window.KOSi18n.apply === 'function') window.KOSi18n.apply(); }
if(window.KOSi18n) window.KOSi18n.register({
  "로그인":"Sign in", "로그아웃":"Sign out", "회원가입":"Sign up", "설정":"Settings",
  "회원 탈퇴":"Delete account", "구독 관리":"Subscription",
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

/* ────────────────── 주소 도우미 ────────────────── */
function here(){ return location.pathname.split('/').pop() || 'Home.html'; }
function isAuthPage(){ return /^(Login|Signup)\.html$/i.test(here()); }
/* 로그인 뒤 돌아올 곳 — 지금 페이지 이름에 쿼리까지(stock.html?ticker=… 로 되돌아와야 한다).
   값을 실어 보낼 뿐이다. 받는 쪽(Login.html 의 safeNext)이 우리 사이트 안의 .html 하나만 통과시킨다. */
function nextHere(){ return encodeURIComponent(here() + (location.search || '')); }
function loginHref(){ return 'Login.html?next=' + nextHere(); }

/* 설정은 페이지다. 칸 이름은 아는 넷만 주소에 싣는다 — 모르는 값은 버리고 설정 첫 칸으로. */
const SETTINGS_TABS = /^(general|notifications|subscription|account)$/;
function settingsHref(tab, card){
  const t = SETTINGS_TABS.test(tab || '') ? tab : '';
  return 'Settings.html' + (t ? '?tab=' + t : '') + (card ? (t ? '&' : '?') + 'card=1' : '');
}
function openSettings(tab){ location.href = settingsHref(tab, false); }

/* ────────────────── 회원 탈퇴 ──────────────────
   다단계 확인 창: 사유 설문(선택) → '되돌릴 수 없음' 동의 체크 → '탈퇴' 입력 시에만 버튼 활성화.
   확정 시: 사유 기록(best-effort) → 서버 deleteAccount 호출.

   ⚠️ 삭제는 서버가 한다. 여기서 deleteUser() 만 부르면 계정은 사라지는데
      구독 문서는 살아 있어, 매일 도는 갱신 배치가 다음 달에도 카드를 긁는다.
      당사자는 로그인도 해지도 못 한다. 서버 함수가 구독을 먼저 닫는다. */
const WD_REASONS = ["원하는 종목·정보가 부족합니다", "정보가 정확하지 않습니다",
                    "자주 이용하지 않습니다", "이용 방법이 불편합니다", "기타"];
const WD_CHECK = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12l5 5 9-10"/></svg>';

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
  /* 아래 틀에는 우리 문구와 상수만 들어간다. 이메일(카카오는 닉네임이 올 수 있다 —
     사용자가 제공자 쪽에서 마음대로 정한 글자)은 뒤에서 글자로만 넣는다. */
  ov.innerHTML = `
    <div class="wd-card" role="dialog" aria-modal="true">
      <h2 class="wd-h">${T("정말 탈퇴하시겠습니까?")}</h2>
      <p class="wd-em"></p>
      <p class="wd-warn">${T("계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.")}</p>
      ${sub ? `<div class="wd-sub">
        <b>${T("이용 중인 구독이 있습니다")}</b>
        <p>${T("탈퇴하시면 구독이 즉시 해지되고, 환불 기준에 따라 산정된 금액이 자동으로 환불됩니다. 오늘 리포트를 열람하셨다면 오늘은 이용일로 차감되며, 계정이 삭제되므로 오늘 남은 열람은 사용하실 수 없습니다. 금액을 먼저 확인하시거나 오늘 남은 열람을 사용하신 뒤 나가시려면 구독 관리에서 환불을 신청하여 주시기 바랍니다.")}</p>
        <button type="button" class="wd-tosubs">${T("구독 관리로 이동")}</button>
      </div>` : ""}
      <p class="wd-q">${T("떠나시는 이유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)")}</p>
      <div class="wd-reasons">${WD_REASONS.map((r)=>
        `<label class="wd-r"><input type="checkbox" name="wdReason" value="${r}"><span class="wd-box">${WD_CHECK}</span><span>${T(r)}</span></label>`).join('')}</div>
      <textarea class="wd-detail" rows="2" placeholder="${T("자세한 의견 (선택)")}"></textarea>
      <label class="wd-ack"><input type="checkbox" id="wdAck"><span class="wd-box">${WD_CHECK}</span><span>${T("위 내용을 이해했으며 되돌릴 수 없음에 동의합니다")}</span></label>
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
  /* 환불 금액을 보러 설정 페이지의 구독 칸으로 간다. 설정은 이제 창이 아니라 페이지라
     자리를 옮기지만, 탈퇴 창은 설정 페이지에서도 다시 열 수 있다. */
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
        <h2 class="wd-done-h">${T("회원 탈퇴가 완료되었습니다")}</h2>
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
      location.href = loginHref();
    }else{
      // 서버가 이유를 준 경우(예: 환불 실패로 탈퇴 중단) 그대로 보여 준다.
      const msg = (e && e.message && /환불|refund/i.test(e.message))
        ? e.message : T("탈퇴 처리 중 오류가 발생했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.");
      alert(msg);
      ov.remove();
    }
  }
}

/* 탈퇴 화면은 이 파일 하나만 갖는다. 설정 페이지의 '회원 탈퇴' 도 여기로 온다 —
   저쪽에서 다시 만들면 확인 절차가 두 벌이 되고, 구독이 살아 있을 때 막는
   규칙을 한쪽에만 고치게 된다. */
window.KOSAccount = { withdraw: openWithdrawModal };

/* 탈퇴 창의 옷. 헤더 CSS 는 페이지가 갖고 있어 여기 없다.
   모양은 설정 시안의 확인 창(scripts/build_auth_comp.py · .ov/.dlg)과 같다 —
   토큰(--surface · --hair · --line · --ink · --up)만 쓰므로 다크 모드는 저절로 따라온다.
   z-index 80: 스테이징 띠(60)·헤더(50)·계정 메뉴(60) 위. */
function injectCss(){
  if(document.getElementById('wdModalCss')) return;
  const st = document.createElement('style'); st.id = 'wdModalCss';
  st.textContent = `
  .wd-ov{position:fixed;inset:0;z-index:80;display:flex;align-items:center;justify-content:center;
    padding:24px;background:rgba(20,20,20,.32)}
  .wd-card{width:100%;max-width:480px;max-height:90vh;overflow:auto;box-sizing:border-box;padding:28px 28px 24px;
    background:var(--surface);border:1px solid var(--hair);border-radius:16px;box-shadow:0 24px 60px rgba(20,20,20,.18);
    color:var(--ink);font-family:var(--font)}
  .wd-h{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em;color:var(--ink)}
  .wd-em{margin:6px 0 0;font:400 13px/20px var(--font);color:var(--ink-62);word-break:break-all}
  .wd-warn{margin:16px 0 0;font:400 14px/22px var(--font);color:var(--up)}
  .wd-sub{margin:18px 0 0;padding:14px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair)}
  .wd-sub b{display:block;font:600 13px/20px var(--font);color:var(--ink)}
  .wd-sub p{margin:4px 0 0;font:400 13px/20px var(--font);color:var(--ink-72);word-break:keep-all}
  .wd-tosubs{display:inline-block;margin-top:8px;border:0;background:none;padding:0;font:500 13px/20px var(--font);
    color:var(--ink);cursor:pointer;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
  .wd-tosubs:hover{text-decoration-color:var(--ink)}
  .wd-q{margin:26px 0 4px;font:500 13px/20px var(--font);color:var(--ink-72)}
  .wd-reasons{display:flex;flex-direction:column}
  /* 체크 줄 — 진짜 checkbox 는 보이지 않게 두고(논리·키보드·읽기 도구는 그대로) 상자(.wd-box)를 그린다 */
  .wd-r,.wd-ack{position:relative;display:flex;align-items:center;gap:12px;padding:10px 0;
    font:400 14px/20px var(--font);color:var(--ink);cursor:pointer;user-select:none;border-bottom:1px solid var(--hair)}
  .wd-r:last-child{border-bottom:0}
  .wd-r input,.wd-ack input{position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;
    clip:rect(0 0 0 0);white-space:nowrap}
  .wd-box{width:18px;height:18px;box-sizing:border-box;border:1px solid var(--line);border-radius:5px;flex:none;
    display:inline-flex;align-items:center;justify-content:center;color:var(--bg);transition:background-color .12s,border-color .12s}
  .wd-box svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;opacity:0}
  .wd-r input:checked+.wd-box,.wd-ack input:checked+.wd-box{background:var(--ink);border-color:var(--ink)}
  .wd-r input:checked+.wd-box svg,.wd-ack input:checked+.wd-box svg{opacity:1}
  .wd-r input:focus-visible+.wd-box,.wd-ack input:focus-visible+.wd-box{outline:2px solid var(--ink);outline-offset:2px}
  .wd-detail{display:block;width:100%;box-sizing:border-box;margin-top:8px;min-height:56px;resize:vertical;
    border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent;padding:8px 0;
    font:400 15px/24px var(--font);color:var(--ink);outline:0;transition:border-color .15s}
  .wd-detail:focus{border-bottom-color:var(--ink)}
  .wd-detail::placeholder,.wd-type::placeholder{color:var(--ink-62)}
  .wd-ack{margin-top:22px;border-bottom:0;font-size:13px;align-items:flex-start;color:var(--ink-72)}
  .wd-ack .wd-box{margin-top:1px}
  .wd-type{display:block;width:100%;box-sizing:border-box;margin-top:10px;border:0;border-bottom:1px solid var(--line);
    border-radius:0;background:transparent;padding:8px 0;font:500 15px/24px var(--font);color:var(--ink);outline:0;
    -webkit-appearance:none;appearance:none;transition:border-color .15s}
  .wd-type:focus{border-bottom-color:var(--ink)}
  .wd-actions{display:flex;justify-content:flex-end;align-items:center;gap:20px;margin-top:26px}
  .wd-cancel{border:0;background:none;padding:0;font:500 13px/1 var(--font);color:var(--ink-72);cursor:pointer;transition:color .12s}
  .wd-cancel:hover{color:var(--ink)}
  .wd-go{display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 18px;border:0;border-radius:999px;
    background:var(--up);color:#fff;font:600 14px/1 var(--font);cursor:pointer;transition:opacity .12s}
  .wd-go:hover{opacity:.9}
  .wd-go:disabled{opacity:.35;cursor:default}
  /* 탈퇴 완료 화면 */
  .wd-done{display:flex;flex-direction:column;align-items:center;text-align:center;padding:8px 0}
  .wd-check{width:56px;height:56px;border-radius:50%;display:flex;align-items:center;justify-content:center;
    background:var(--surface-2);color:var(--ink);margin-bottom:18px}
  .wd-check svg{width:26px;height:26px}
  .wd-done-h{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em;color:var(--ink)}
  .wd-done-sub{margin:10px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}
  .wd-home{display:inline-flex;align-items:center;justify-content:center;height:40px;padding:0 18px;border:0;border-radius:999px;
    background:var(--ink);color:var(--bg);font:600 14px/1 var(--font);cursor:pointer;transition:opacity .12s}
  .wd-home:hover{opacity:.9}`;
  document.head.appendChild(st);
}

/* ────────────────── 헤더 · 휴대폰 메뉴 ────────────────── */

/* 글자는 글자로만 넣는다 — 마크업에 이어 붙이지 않는다.
   카카오는 이메일을 안 주는 경우가 있어 닉네임이 대신 들어오는데, 닉네임은
   사용자가 제공자 쪽에서 마음대로 정한 글자다. '<' 하나만 들어 있어도 메뉴가
   깨지고, 나쁘게 쓰면 우리 페이지 위에서 코드가 돈다. 그래서 헤더는 innerHTML 없이
   createElement · textContent 로만 짓는다. */
function el(tag, attrs, text){
  const n = document.createElement(tag);
  if(attrs) for(const k in attrs) n.setAttribute(k, attrs[k]);
  if(text != null) n.textContent = text;
  return n;
}
function clear(node){ while(node.firstChild) node.removeChild(node.firstChild); }

/* 자리 셋. #acct 가 없으면 이 헤더가 아니다 — 아무것도 하지 않는다. */
function mount(){
  const acct = document.getElementById('acct');
  if(!acct) return null;
  const right = document.getElementById('navRight') || acct.parentElement;
  return { acct, right,
           login: right ? right.querySelector('a.login') : null,
           mauth: document.getElementById('mauth') };
}

function setMenu(acct, on){
  acct.classList.toggle('open', on);
  const btn = acct.querySelector('#acctBtn');
  if(btn) btn.setAttribute('aria-expanded', on ? 'true' : 'false');
}
function closeMenu(){
  const acct = document.getElementById('acct');
  if(acct && acct.classList.contains('open')) setMenu(acct, false);
}
/* 바깥 클릭 · Esc 로 닫는다. 그릴 때마다가 아니라 한 번만 건다 — 상태가 바뀔 때마다
   다시 그리는데, 그때마다 문서에 손잡이를 하나씩 더 달면 안 된다. */
let menuBound = false;
function bindMenuOnce(){
  if(menuBound) return; menuBound = true;
  document.addEventListener('click', e => {
    const acct = document.getElementById('acct');
    if(acct && acct.classList.contains('open') && !acct.contains(e.target)) setMenu(acct, false);
  });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') closeMenu(); });
}

async function logout(){
  try{ await signOut(auth); }catch(e){}
  location.href = 'Home.html';
}

/* 로그아웃 상태 — 정적 '로그인' 링크를 그대로 쓰되 돌아올 곳만 붙인다.
   로그인·가입 화면에서는 헤더를 건드리지 않는다(예전에도 그 자리에 아무것도 안 그렸다). */
function renderLoggedOut(S){
  if(isAuthPage()) return;
  if(S.right) S.right.classList.remove('user');
  S.acct.classList.remove('show', 'open');
  clear(S.acct);
  if(S.login) S.login.setAttribute('href', loginHref());
  if(S.mauth){
    clear(S.mauth);
    S.mauth.appendChild(el('a', { href: loginHref() }, '로그인'));
    S.mauth.appendChild(el('a', { href: 'Signup.html' }, '회원가입'));
  }
  applyI18n();
}

/* 로그인 상태 — 아바타(머리글자) + 드롭다운(이메일 · 설정 · 로그아웃).
   이 메뉴는 계정 메뉴이지 설정 목차가 아니다. '구독 관리'·'회원 탈퇴'는 설정 페이지 안에
   있으므로 여기서는 설정으로 보내고 끝낸다 — 같은 곳으로 가는 문이 둘이면 한쪽만 고치게 된다.
   탈퇴 화면 자체는 이 파일이 계속 갖는다(window.KOSAccount.withdraw).
   휴대폰 메뉴도 같은 구성이다 — 한쪽에만 항목이 더 있으면 안내가 갈린다.
   (이메일 줄은 휴대폰에 없다 — 헤더의 동그라미가 이미 로그인 상태를 말한다. 9/26 사장) */
function renderLoggedIn(S, user){
  if(isAuthPage()) return;
  const email = user.email || (user.displayName || '');
  const initial = (email.trim()[0] || 'U').toUpperCase();
  if(S.right) S.right.classList.add('user');
  if(S.login) S.login.setAttribute('href', loginHref());
  clear(S.acct);
  const btn = el('button', { type: 'button', 'class': 'avatar', id: 'acctBtn',
    'aria-haspopup': 'true', 'aria-expanded': 'false', 'aria-label': '계정 메뉴' }, initial);
  const menu = el('div', { 'class': 'acct-menu', role: 'menu' });
  menu.appendChild(el('div', { 'class': 'em' }, email));
  menu.appendChild(el('a', { href: 'Settings.html' }, '설정'));
  const out = el('button', { type: 'button', 'class': 'logout' }, '로그아웃');
  out.addEventListener('click', logout);
  menu.appendChild(out);
  S.acct.appendChild(btn); S.acct.appendChild(menu);
  S.acct.classList.remove('open');
  S.acct.classList.add('show');
  btn.addEventListener('click', () => setMenu(S.acct, !S.acct.classList.contains('open')));
  if(S.mauth){
    clear(S.mauth);
    S.mauth.appendChild(el('a', { href: 'Settings.html' }, '설정'));
    const mout = el('button', { type: 'button', 'class': 'logout' }, '로그아웃');
    mout.addEventListener('click', logout);
    S.mauth.appendChild(mout);
  }
  applyI18n();
}

/* ────────────────── ?settings= 깊은 링크 ──────────────────
   billing.html 이 여기로 보낸다(Home.html?settings=subscription). 결제를 마치고 돌아오는
   길도 같다 — 그때는 ?card=1 이 함께 오고, 설정 페이지가 '카드가 바뀌었습니다' 를 띄운다.
   설정이 창이던 때는 이 자리에서 창을 열었다. 지금은 페이지라 그리로 보낸다 —
   Settings.html?tab=<칸>(&card=1). replace 라 뒤로 가기에 ?settings= 주소가 남지 않아
   다시 돌아와 또 보내는 일이 없다. 로그인이 확인된 뒤에 한 번만 간다. 로그아웃
   상태면 '로그인' 링크의 next 에 이 쿼리가 그대로 실려, 로그인하고 돌아오면 그때 간다. */
let settingsFollowed = false;
function followSettingsLink(user){
  if(settingsFollowed || !user) return;
  let q;
  try{ q = new URLSearchParams(location.search); }catch(e){ return; }
  const tab = q.get('settings');
  if(!tab) return;
  settingsFollowed = true;
  location.replace(settingsHref(tab, !!q.get('card')));
}

/* ────────────────── 동의 기록 그물 ──────────────────
   구글 가입은 팝업이 닫히는 순간 파이어베이스가 계정을 먼저 만들고, 동의는 그 뒤
   Consent.html 에서 받는다. 그 사이에 탭을 닫으면 동의 기록 없는 계정이 남고, 다시
   물어보는 자리가 없었다. 그래서 이 파일에 그물을 친다 — 모든 페이지에서 돌기 때문이다.
   기록이 없으면 동의 페이지로 보낸다. 가입을 마치지 못한 사람에게만, 이미 가는 길이던
   화면을 next 로 들고 간다.

   부르는 조건을 좁게 잡는다. 잘못 걸면 사이트를 못 쓰게 만드는 자리다.
     · 동의·로그인·가입 페이지에서는 하지 않는다 — 무한 이동이 된다.
     · Terms·Privacy 도 뺀다. 동의 화면이 그 둘을 새 탭으로 열어 주는데, 목록에서
       빠뜨리면 열린 탭이 곧바로 동의 화면으로 되튕긴다 — 동의하라고 보여 주는
       문서를 정작 못 읽게 막는다.
     · 조회에 실패하면(null) 아무것도 하지 않는다. 통신이 끊겼다고 사람을
       가입 화면으로 몰아내면 안 된다. 확실히 '없다'(false)일 때만 보낸다.
     · 한 번만 시도한다. onAuthStateChanged 는 여러 번 울린다. */
const CONSENT_SKIP = /^(Consent|Login|Signup|auth-action|Terms|Privacy)\.html$/i;
let consentChecked = false;

/* 같은 탭에서 동의 화면으로 몇 번이나 보냈는지.

   ⚠️ 이 자리에서 무한 루프가 났다. 동의를 눌러 기록이 저장돼도 다른 곳에서 그 기록이
      다시 반쪽이 되면, 여기가 또 동의 화면으로 보낸다. 사용자는 동의 → 화면 → 동의 →
      화면 을 끝없이 반복하게 되고 사이트를 아예 쓸 수 없다. 원인은 따로 고쳤지만,
      다음에 또 어딘가가 기록을 흐트러뜨렸을 때 같은 덫이 된다. 못 나가는 것보다는
      못 물어보는 편이 낫다 — 동의는 다음 접속에 다시 물어볼 수 있지만, 갇힌 사람은
      아무것도 할 수 없다.

   한 탭에서 한 번만 보낸다. 두 번째부터는 보내지 않고 콘솔에만 남긴다. */
const CONSENT_BOUNCE = "kos_consent_bounce";

async function guardConsent(user){
  if(consentChecked || !user || CONSENT_SKIP.test(here())) return;
  consentChecked = true;
  try{
    const { consentState } = await import("./consent.js?v=206cdd28");
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

    /* 돌아갈 곳에 쿼리를 붙이지 않는다. 소셜 로그인 직후처럼 주소에 ?code=… 가
       남아 있을 때 그 인가코드까지 next 에 실려 가면, 동의를 마친 뒤 그 주소로
       되돌아가 이미 써 버린 코드로 로그인을 한 번 더 시도하게 된다. 페이지면 충분하다. */
    location.replace('Consent.html?next=' + encodeURIComponent(here()));
  }catch(e){ /* 표시·이동용 — 실패하면 그냥 둔다 */ }
}

/* ────────────────── 첫 그림 · 시작 ──────────────────
   지난번 계정 표시를 기억해 두고(kos-signed=1 · kos-signed-user=이메일), 파이어베이스가
   세션을 되살리기 전에 그것으로 먼저 그린다. 헤더 오른쪽 아바타가 페이지마다 몇백 밀리초 뒤에
   '툭' 나타나던 것을 없앤다(2026-09-24 사장: "홈 버튼 누를 때도 가끔 깜빡"). 기억이 없으면
   '로그인' 링크를 바로 그린다. 확인이 끝나면 진짜 상태로 다시 그린다 — 기억이 틀렸을 때
   (세션 만료)만 눈에 띈다. kos-signed 는 워치리스트 가림막·관심종목 목록·모의 구독도 읽는다. */
function remembered(){
  try{
    if(localStorage.getItem('kos-signed') !== '1') return null;
    const email = localStorage.getItem('kos-signed-user');
    return email ? { email, provisional: true } : null;
  }catch(e){ return null; }
}
function rememberUser(user){
  try{
    if(user){ localStorage.setItem('kos-signed','1'); localStorage.setItem('kos-signed-user', user.email || user.displayName || ''); }
    else { localStorage.removeItem('kos-signed'); localStorage.removeItem('kos-signed-user'); }
  }catch(e){}
}

function start(){
  const S = mount();
  if(!S) return;
  bindMenuOnce();
  if(!isConfigured){ renderLoggedOut(S); return; }
  const guess = remembered();
  if(guess) renderLoggedIn(S, guess); else renderLoggedOut(S);
  onAuthStateChanged(auth, user => {
    rememberUser(user);
    if(user) renderLoggedIn(S, user); else renderLoggedOut(S);
    followSettingsLink(user);
    guardConsent(user);
  });
}

if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
else start();
