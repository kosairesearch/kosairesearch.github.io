/* 결제 진입점. 요금제는 멤버십 하나다(2026-11-24 — 요금제 변경 · 업그레이드 · 변경 예약 없음).
   이미 이용 중인 사람에게 '구독하기'를 보여 주면 안 된다 — 이미 낸 돈을 다시 팔고 있는
   셈이고, 눌러 봐야 '이미 이용 중입니다'로 끝난다. 구독 상태에 맞게 단추와 배지를 바꾼다.

     구독 전 · 이용 종료 · 환불 완료   구독하기 → 결제 화면(checkout.html?plan=member)
     이용 중(해지 예약 포함)           구독 관리하기 + '이용 중' 배지 → 설정의 구독 칸
     결제 실패(재시도 중)              결제 수단 변경하기 → 카드 변경(checkout.html?plan=member&method=1) */
import "./paywall.js";

const P = window.KOSPaywall;
const btns = [...document.querySelectorAll('.plan [data-plan]')];
const EN = () => {
  try { const v = localStorage.getItem('kos-lang'); if (v) return v === 'en'; } catch (e) {}
  return !!(window.KOSi18n && window.KOSi18n.lang === 'en');
};
const T = {
  ko: { start: '구독하기', manage: '구독 관리하기', badge: '이용 중', fixCard: '결제 수단 변경하기' },
  en: { start: 'Subscribe', manage: 'Manage subscription', badge: 'Current plan', fixCard: 'Change card' },
};
const t = () => (EN() ? T.en : T.ko);

let st = { user: null, active: false, plan: null, sub: null };

/* 지금 이 사람에게 멤버십을 파는 자리인가.

   환불한 구독은 리포트를 연 경우 자정까지 살아 있다(오늘 몫을 받았으니 쓰게
   둔다). 그런데 그걸 '이용 중' 으로 보면 단추가 '구독 관리하기' 가 되고,
   눌러도 설정 창의 '환불 완료' 화면으로 갔다가 다시 여기로 돌아온다 —
   환불한 날 다시 시작하려는 사람이 나갈 데가 없는 고리에 갇혔다.

   이용은 이용대로 자정까지 두고, 파는 쪽에서는 지난 손님으로 본다. */
function selling() {
  const sub = st.sub || {};
  return st.active && !sub.refundedAt;
}
// 결제가 밀려 멈춘 구독 — 결제 화면이 아니라 카드부터 고친다
const pastDue = () => !st.active && (st.sub || {}).status === 'past_due';

function paint() {
  const k = t();
  const live = selling(), due = pastDue();
  btns.forEach((btn) => {
    const card = btn.closest('.plan');
    card.querySelectorAll('.plan-badge.js').forEach((e) => e.remove());
    btn.classList.remove('is-current');
    btn.disabled = false;
    btn.textContent = due ? k.fixCard : live ? k.manage : k.start;
    if (live && !due) {
      btn.classList.add('is-current');
      const b = document.createElement('div');
      b.className = 'plan-badge js';
      b.textContent = k.badge;
      card.appendChild(b);
    }
  });
}

btns.forEach((btn) => {
  btn.addEventListener('click', () => {
    if (!st.user) { location.href = 'Login.html?next=pricing.html'; return; }
    /* 환불한 사람도 여기로 온다 — 새 구독을 시작하는 길이다. 환불이 끝난
       구독은 오늘 자정까지 살아 있을 수 있지만 돈은 이미 돌려줬으므로, 서버도
       그 구독 위에 새로 만드는 것을 허용한다(confirmBilling).

       해지만 예약해 둔 사람은 결제 화면으로 보내지 않는다 — selling() 이 참이라
       구독 관리로 가고, 해지를 되돌리는 것은 거기의 '해지 취소하기' 다. 남은 기간이
       그대로인 구독 위에 새 결제를 얹으면 첫 달 결제가 환불 대상에서 사라지므로,
       서버도 그 길은 막아 두었다. */
    if (pastDue()) { location.href = 'checkout.html?plan=member&method=1'; return; }
    if (selling()) { location.href = 'billing.html'; return; }
    location.href = 'checkout.html?plan=member';
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
