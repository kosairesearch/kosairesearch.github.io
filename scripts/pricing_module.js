/* 결제 진입점. 이미 이용 중인 사람에게 'PRO 시작하기'를 보여 주면 안 된다 —
   이미 낸 돈을 다시 팔고 있는 셈이고, 눌러 봐야 '이미 이용 중입니다'로 끝난다.
   구독 상태에 맞게 버튼과 배지를 바꾼다. */
import "./paywall.js";
import { call } from "./subscription-api.js";
import { MIN_CHARGE, upgradeDiff, won } from "./payment-config.js";

const P = window.KOSPaywall;
const btns = [...document.querySelectorAll('.plan [data-plan]')];
const EN = () => {
  try { const v = localStorage.getItem('kos-lang'); if (v) return v === 'en'; } catch (e) {}
  return !!(window.KOSi18n && window.KOSi18n.lang === 'en');
};
const T = {
  ko: { start: '업그레이드', current: '이용 중', manage: '구독 관리',
        up: 'PRO로 업그레이드', down: 'BASIC으로 변경', badge: '이용 중',
        pend: '{d}부터 적용', pendBadge: '변경 예정',
        undo: '변경 취소', fixCard: '결제 수단 변경',
        yes: '확인', no: '취소',
        dlgUpT: 'PRO로 업그레이드하시겠습니까?',
        dlgUpB: '즉시 PRO가 적용됩니다. 남은 기간에 해당하는 BASIC 금액을 차감한 차액 {a}이 등록하신 카드로 지금 결제되며, 결제일은 그대로 유지됩니다.',
        dlgUpB0: '즉시 PRO가 적용됩니다. 이번 결제 주기가 거의 끝나 지금 청구되는 금액은 없으며, 다음 결제일부터 PRO 요금으로 청구됩니다.',
        dlgDownT: 'BASIC으로 변경하시겠습니까?',
        dlgDownB: '{d}부터 BASIC이 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.',
        dlgUndoT: '플랜 변경을 취소하시겠습니까?',
        dlgUndoB: '{d} 이후에도 {p} 플랜이 그대로 유지됩니다.',
        alsoResume: ' 예약해 두신 해지는 함께 취소됩니다.',
        okUp: 'PRO 플랜이 바로 적용되었습니다. 차액 {a}이 결제되었습니다.',
        okUp0: 'PRO 플랜이 바로 적용되었습니다. 지금 청구된 금액은 없습니다.',
        okDown: '{d}부터 BASIC 플랜으로 변경됩니다.',
        okUndo: '플랜 변경이 취소되었습니다.',
        fail: '처리에 실패했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.' },
  en: { start: 'Upgrade', current: 'Current plan', manage: 'Manage subscription',
        up: 'Upgrade to PRO', down: 'Switch to BASIC', badge: 'Current',
        pend: 'From {d}', pendBadge: 'Scheduled',
        undo: 'Undo change', fixCard: 'Change card',
        yes: 'Confirm', no: 'Cancel',
        dlgUpT: 'Upgrade to PRO?',
        dlgUpB: 'PRO applies immediately. The unused part of BASIC is credited and the difference, {a}, is charged to your registered card now; your billing date stays the same.',
        dlgUpB0: 'PRO applies immediately. This billing period is nearly over, so nothing is charged now — PRO pricing starts from your next billing date.',
        dlgDownT: 'Switch to BASIC?',
        dlgDownB: 'BASIC applies from {d}. You keep PRO until then.',
        dlgUndoT: 'Undo the scheduled change?',
        dlgUndoB: 'You stay on {p} after {d}.',
        alsoResume: ' Your scheduled cancellation will be undone.',
        okUp: 'You are on PRO as of now. {a} has been charged.',
        okUp0: 'You are on PRO as of now. Nothing was charged.',
        okDown: 'You move to BASIC on {d}.',
        okUndo: 'The scheduled change has been cancelled.',
        fail: 'Something went wrong. Please try again shortly.' },
};
const t = () => (EN() ? T.en : T.ko);
const day = (v) => {
  if (!v) return '';
  const ms = typeof v?.toMillis === 'function' ? v.toMillis()
           : typeof v === 'number' ? v : Date.parse(v);
  if (!Number.isFinite(ms)) return '';
  const d = new Date(ms), M = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return EN() ? `${M[d.getMonth()]} ${d.getDate()}` : `${d.getMonth() + 1}월 ${d.getDate()}일`;
};

let st = { user: null, active: false, plan: null, sub: null };
/* 처리 결과 문구. 구독이 바뀌면 paint() 가 다시 돌면서 화면을 새로 그리므로
   화면 밖에 들고 있어야 다시 그린 뒤에도 남는다. */
let flash = null;

/* 확인 대화상자. 되돌리기 어렵거나 돈이 오가는 동작은 한 번 묻는다. */
function ask(title, body) {
  const k = t(), d = document.getElementById('dlg');
  document.getElementById('dlgT').textContent = title;
  document.getElementById('dlgB').innerHTML = '<p></p>';
  document.querySelector('#dlgB p').textContent = body;
  document.getElementById('dlgYes').textContent = k.yes;
  document.getElementById('dlgNo').textContent = k.no;
  d.classList.add('open');
  return new Promise((res) => {
    const yes = document.getElementById('dlgYes'), no = document.getElementById('dlgNo');
    const done = (v) => { d.classList.remove('open'); yes.onclick = null; no.onclick = null; res(v); };
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
    d.onclick = (e) => { if (e.target === d) done(false); };
  });
}

/* 지금 이 사람에게 플랜을 파는 자리인가.

   환불한 구독은 오늘 리포트를 본 경우 자정까지 살아 있다(값을 받았으니 쓰게
   둔다). 그런데 그걸 '이용 중' 으로 보면 카드 버튼이 '구독 관리' 가 되고,
   눌러도 설정 창의 '환불 완료' 화면으로 갔다가 다시 여기로 돌아온다 —
   환불한 날 다시 시작하려는 사람이 나갈 데가 없는 고리에 갇혔다.

   이용은 이용대로 자정까지 두고, 파는 쪽에서는 지난 손님으로 본다. */
function selling() {
  const sub = st.sub || {};
  return st.active && !sub.refundedAt;
}

function paint() {
  const k = t();
  const sub = st.sub || {};
  const live = selling();
  const due = !st.active && sub.status === 'past_due';
  const pend = live && sub.pendingPlan && sub.pendingPlan !== st.plan ? sub.pendingPlan : null;

  btns.forEach((btn) => {
    const id = btn.dataset.plan;
    const card = btn.closest('.plan');
    const msg = card.querySelector('.plan-msg');
    card.querySelectorAll('.plan-badge.js').forEach((e) => e.remove());
    btn.classList.remove('is-current');
    btn.disabled = false;

    msg.className = 'plan-msg';
    msg.textContent = '';
    if (flash && flash.plan === id) {
      msg.textContent = flash.text;
      msg.className = 'plan-msg show' + (flash.err ? ' err' : '');
    }

    let label = k.start, badge = null;
    if (due) {
      // 결제가 밀려 멈춘 구독이다. 플랜을 바꿀 게 아니라 카드를 먼저 고쳐야 한다.
      label = k.fixCard;
    } else if (live && id === st.plan) {
      // 지금 쓰는 플랜 — 팔 게 아니라 관리로 보낸다.
      label = k.manage; badge = k.badge;
      btn.classList.add('is-current');
    } else if (live && id === pend) {
      label = k.undo; badge = k.pendBadge;
    } else if (live) {
      label = id === 'pro' ? k.up : k.down;
    }
    btn.textContent = label;
    if (badge) {
      const b = document.createElement('div');
      b.className = 'plan-badge js';
      b.textContent = badge + (id === pend ? ' · ' + k.pend.replace('{d}', day(sub.currentPeriodEnd)) : '');
      card.appendChild(b);
    }
  });
}

/* 플랜 변경은 이 페이지에서 끝낸다. 업그레이드를 누른 사람을 구독 관리
   페이지로 보내면, 방금 무엇을 눌렀는지와 상관없는 화면이 뜬다. */
btns.forEach((btn) => {
  btn.addEventListener('click', async () => {
    const k = t(), id = btn.dataset.plan, sub = st.sub || {};
    if (!st.user) { location.href = 'Login.html?next=pricing.html'; return; }
    /* 환불한 사람도 여기로 온다 — 새 구독을 시작하는 길이다. 환불이 끝난
       구독은 오늘 자정까지 살아 있지만 돈은 이미 돌려줬으므로, 서버도 그
       구독 위에 새로 만드는 것을 허용한다(confirmBilling).

       해지만 예약해 둔 사람은 여기로 오지 않는다 — selling() 이 참이라 아래
       플랜 변경 쪽으로 가고, 해지를 되돌리는 것은 구독 관리의 '해지 취소'
       이다. 남은 기간이 그대로인 구독 위에 새 결제를 얹으면 첫 달 결제가
       환불 대상에서 사라지므로, 서버도 그 길은 막아 두었다. */
    if (!selling()) {
      // 결제가 밀린 구독은 카드부터. 그 외에는 결제 화면으로.
      if (!st.active && sub.status === 'past_due') {
        location.href = 'checkout.html?plan=' + encodeURIComponent(sub.plan || 'basic') + '&method=1';
      } else {
        location.href = 'checkout.html?plan=' + encodeURIComponent(id);
      }
      return;
    }
    if (id === st.plan) { location.href = 'billing.html'; return; }   // 이용 중인 플랜 → 관리

    const endDay = day(sub.currentPeriodEnd);
    const pend = sub.pendingPlan && sub.pendingPlan !== st.plan ? sub.pendingPlan : null;
    /* 해지를 예약해 둔 사람이 플랜을 바꾸면 그 해지는 풀린다(서버 changePlan).
       누르기 전에 말해 주지 않으면 해지한 줄 알고 있다가 다음 달에 결제된다. */
    const more = sub.cancelAtPeriodEnd ? k.alsoResume : '';
    let ok, done;
    if (id === pend) {
      ok = await ask(k.dlgUndoT,
        k.dlgUndoB.replace('{d}', endDay).replace('{p}', String(st.plan || '').toUpperCase()) + more);
      done = k.okUndo;
    } else if (id === 'pro') {
      /* 얼마가 빠져나가는지 보여 주고 묻는다. 금액 없이 '차액만 결제됩니다'로
         확인을 받으면, 카드에 얼마가 청구될지 모르는 채로 누르게 된다. */
      const diff = upgradeDiff(sub, id);
      ok = await ask(k.dlgUpT,
        (diff >= MIN_CHARGE ? k.dlgUpB.replace('{a}', won(diff, EN())) : k.dlgUpB0) + more);
      done = null;                       // 실제 청구액은 서버가 알려 준다
    } else {
      ok = await ask(k.dlgDownT, k.dlgDownB.replace('{d}', endDay) + more);
      done = k.okDown.replace('{d}', endDay);
    }
    if (!ok) return;

    flash = null;
    btns.forEach((b) => { b.disabled = true; });
    try {
      // 예약을 되돌리는 것도 같은 함수다 — 지금 쓰는 플랜을 다시 고르면 예약이 풀린다.
      const res = await call('changePlan', { plan: id === pend ? st.plan : id });
      if (done == null) {
        // 업그레이드 — 미리 보여 준 금액이 아니라 실제로 청구된 금액을 알린다.
        const charged = (res && res.data && res.data.charged) || 0;
        done = charged > 0 ? k.okUp.replace('{a}', won(charged, EN())) : k.okUp0;
      }
      flash = { plan: id, text: done, err: false };
      paint();          // 구독 문서가 바뀌면 onChange 도 돌지만, 늦을 수 있다
    } catch (e) {
      console.error('[pricing] changePlan', e);
      flash = { plan: id, text: e.message || k.fail, err: true };
      paint();
    }
  });
});

if (P) {
  /* 첫 그림 — 인증 확인이 끝나기 전에는 미리보기(P.peek — 모의 결제에만 있다)로 그린다. 없으면
     지금처럼 확인 전 상태로 그린다. 확인이 끝나면 진짜 상태로 한 번 더 그린다(기억이 틀렸을 때). */
  let settled = false;
  P.onChange((s) => { st = (!settled && P.peek) ? P.peek() : s; paint(); });
  if (P.ready && P.ready.then) P.ready.then(() => { settled = true; st = P.state(); paint(); });
} else {
  paint();
}
/* 이 버튼 글자는 스크립트가 쓰므로 번역 엔진이 손대지 않는다 — 직접 다시 그린다. */
if (window.KOSi18n) window.KOSi18n.register(null, paint);
