/* ============================================================
   KOSAI — 설정 패널 (스테이징)
   ------------------------------------------------------------
   실사이트의 settings-panel.js 를 가져와 항목을 왼쪽 목록으로 나누고
   '구독' 을 더한 판이다.

   왜 페이지가 아니라 창인가. 구독 관리는 리포트를 보다가 잠깐 들르는
   곳이지 찾아가는 곳이 아니다. billing.html 로 페이지를 옮기면 보던
   화면을 잃고, 돌아오려면 뒤로가기를 눌러야 한다. 테마·언어·마케팅
   수신과 같은 성격의 설정인데 그것만 페이지로 떨어져 있을 이유도 없다.

   왜 왼쪽 목록인가. 실사이트 창은 한 줄로 죽 이어진 형태다. 거기에
   구독을 더하면 스크롤이 길어지고, 테마를 바꾸러 온 사람이 결제 정보를
   지나쳐야 한다. 성격이 다른 것은 갈라 놓는 편이 낫다.

     일반    테마 · 언어
     알림    마케팅 정보 수신
     구독    상태 · 결제 · 사용량 · 플랜 변경 · 해지/재개/환불 · 결제 내역
     계정    닉네임 · 이메일 · 로그아웃 · 회원 탈퇴

   구독 자료는 window.KOSPaywall(paywall.js)에서 받고, 바꾸는 일은
   subscription-api.js 의 call() 로 보낸다. 스테이징에서는 그 call 이
   모의 백엔드로 돌아가므로 실제로 돈이 오가지 않는다.

     openSettings(tab)   지금 화면 위에 창으로 띄운다
     window.KOSSettings.open("subscription")   구독 칸을 펴서 연다

   화면이 좁아졌다고 판단을 줄이지 않는다. 처음에 구독 칸을 상태만 적고
   버튼은 이름만 달아 내보냈는데, 그건 화면이지 기능이 아니었다. 옛 구독 관리
   페이지(billing.js)가 하던 확인 절차·사유 접수·금액 고지를 전부 옮겨 온 뒤
   그 파일은 지웠다 — 아무도 부르지 않는데 옛 환불 문구를 들고 있어서, 나중에
   읽는 사람이 어느 쪽이 맞는지 헷갈릴 자리였다.

   이 파일은 눈으로 확인할 수 없는 것이 많다(브라우저가 없는 데서 고친다).
   staging/tests/subscription.test.mjs 가 대신 본다 — 고치면 돌릴 것.
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getMarketing, setMarketing, accountInfo } from "./consent.js";
import { call } from "./subscription-api.js";
import { PLANS, planOf, won, fmtDay, payReady, upgradeDiff, MIN_CHARGE }
  from "./payment-config.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
const EN = () => (window.KOSi18n ? window.KOSi18n.lang : "ko") === "en";

if (window.KOSi18n) window.KOSi18n.register({
  "설정": "Settings",
  "일반": "General",
  "알림": "Notifications",
  "구독": "Subscription",
  "계정": "Account",
  "닉네임": "Nickname",
  "이메일": "Email",
  "등록된 주소 없음": "No address on file",
  "테마": "Theme",
  "라이트": "Light",
  "다크": "Dark",
  "언어": "Language",
  "한국어": "Korean",
  "English": "English",
  "마케팅 정보 수신": "Marketing messages",
  "새 리포트와 서비스 소식을 이메일로 받습니다. 받지 않아도 서비스 이용에는 아무 영향이 없습니다.":
    "Get news about new reports and the service by email. Turning this off does not affect your use of the service.",
  "로그아웃": "Sign out",
  "회원 탈퇴": "Delete account",
  "저장하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.": "Could not save. Please try again in a moment.",
  "불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.": "Could not load. Please try again in a moment.",
  "계정 설정을 보려면 로그인이 필요합니다.": "Sign in to view your account settings.",
  "로그인": "Sign in",
  "닫기": "Close",
  "약관과 개인정보 처리에 관한 내용은": "You can review our",
  "이용약관": "Terms of Service",
  "개인정보처리방침": "Privacy Policy",
  "에서 확인할 수 있습니다.": ".",
  /* 구독 — 문구는 옛 구독 관리 페이지가 쓰던 것을 그대로 옮겼다. 화면만
     바뀌었을 뿐 사용자가 읽는 말이 달라질 이유가 없다. */
  "불러오는 중…": "Loading…",
  "이용 중인 플랜": "Current plan",
  "무료": "Free",
  "무료로 이용 중입니다. 분석·전망·리스크 등 유료 구간은 멤버십에서 보실 수 있습니다.":
    "You are on the free plan. The analysis, outlook, and risk sections come with a plan.",
  "플랜 보기": "See plans",
  "멤버십 보기": "See plans",
  "상태": "Status",
  "이용 중": "Active",
  "해지 예약됨": "Ends soon",
  "결제 실패": "Payment failed",
  "이용 종료됨": "Ended",
  "다음 결제일": "Next billing date",
  "이용 종료일": "Access until",
  "구독 시작일": "Started",
  "결제 금액": "Amount",
  "하루 열람 한도": "Daily limit",
  "오늘 남은 열람": "Left today",
  "예정된 변경": "Scheduled change",
  "결제 수단": "Payment method",
  "등록된 카드가 없습니다.": "No card registered.",
  "등록하신 카드": "Card on file",
  "결제 내역": "Payment history",
  "아직 결제 내역이 없습니다.": "No payments yet.",
  "일자": "Date", "내용": "Description", "금액": "Amount",
  "결제 완료": "Paid", "환불": "Refunded", "실패": "Failed",
  "{p} 월 구독": "{p} monthly", "{p} 업그레이드 차액": "{p} upgrade difference",
  "정기결제 실패": "Renewal failed",
  "청약철회": "withdrawal", "이용분 차감": "usage deducted", "잔여 기간": "remaining days",
  "환불 완료": "Refunded",
  "환불이 완료되었습니다. 오늘 자정까지 이용하실 수 있으며, 언제든 다시 시작하실 수 있습니다.":
    "Refunded. You keep access until midnight tonight, and you can start again whenever you like.",
  "환불이 완료되어 이용이 종료되었습니다. 언제든 다시 시작하실 수 있습니다.":
    "Refunded. Your access has ended. You can start again whenever you like.",
  "다시 시작하기": "Start again",
  "{r}개 / {l}개": "{r} of {l}", "{d}부터 {p}": "{p} from {d}",
  "PRO로 업그레이드": "Upgrade to PRO", "BASIC으로 변경": "Switch to BASIC",
  "변경 취소": "Undo change",
  "결제 수단 변경": "Change card",
  "구독 해지": "Cancel subscription",
  "해지 취소": "Keep subscription",
  "환불 신청": "Request a refund",
  "확인": "Confirm", "취소": "Cancel",
  "구독을 해지하시겠습니까?": "Cancel your subscription?",
  "{date}까지는 그대로 이용하실 수 있으며, 그 이후 결제되지 않습니다. 해지는 언제든지 취소하실 수 있습니다.":
    "You keep access until {date}, and you will not be charged after that. You can undo this anytime.",
  "환불을 신청하시겠습니까?": "Request a refund?",
  "환불 금액은 이용하신 일수를 차감해 산정됩니다.":
    "The refund deducts the days you have used.",
  "{a}이 환불됩니다.": "{a} will be refunded.",
  "오늘 자정까지 이용하실 수 있습니다.": "You keep access until midnight today.",
  "이용은 신청 즉시 종료됩니다.": "Your access ends as soon as you confirm.",
  "오늘 리포트를 보셨다면 오늘까지 이용하실 수 있고, 오늘 한 건도 보지 않으셨다면 오늘은 차감하지 않고 이용이 바로 종료됩니다.":
    "If you opened a report today, you keep access until midnight; if you opened none today, today is not charged and your access ends right away.",
  "플랜 변경만 원하시는 경우에는 환불 대신 위의 ‘플랜 변경’을 이용하여 주시기 바랍니다. 남은 기간에 대한 차액만 결제되며 즉시 적용됩니다.":
    "If you only want to switch plans, use “Change plan” above instead of a refund — you are charged only the difference for the remaining period, and it applies immediately.",
  "PRO로 업그레이드하시겠습니까?": "Upgrade to PRO?",
  "즉시 PRO가 적용됩니다. 남은 기간에 해당하는 BASIC 금액을 차감한 차액 {a}이 등록하신 카드로 지금 결제되며, 결제일은 그대로 유지됩니다.":
    "PRO applies immediately. The unused part of BASIC is credited and the difference, {a}, is charged to your card now; your billing date stays the same.",
  "즉시 PRO가 적용됩니다. 이번 결제 주기가 거의 끝나 지금 청구되는 금액은 없으며, 다음 결제일부터 PRO 요금으로 청구됩니다.":
    "PRO applies immediately. This billing period is nearly over, so nothing is charged now — PRO pricing starts from your next billing date.",
  "BASIC으로 변경하시겠습니까?": "Switch to BASIC?",
  "{date}부터 BASIC이 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.":
    "BASIC applies from {date}. You keep PRO until then.",
  "플랜 변경을 취소하시겠습니까?": "Undo the scheduled change?",
  "{date} 이후에도 {p} 플랜이 그대로 유지됩니다.": "You stay on {p} after {date}.",
  " 예약해 두신 해지는 함께 취소됩니다.": " Your scheduled cancellation will be undone.",
  " 예약해 두신 {p} 플랜 변경은 함께 취소됩니다.": " Your scheduled change to {p} will be dropped.",
  "사유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)":
    "Telling us why helps us improve (select all that apply)",
  "자세한 의견 (선택)": "Tell us more (optional)",
  "해지 예약이 완료되었습니다.": "Your subscription will end at the period end.",
  "해지가 취소되었습니다.": "Your subscription continues.",
  "환불 신청이 접수되었습니다. {a}이 환불되며, 오늘 자정까지 이용하실 수 있습니다.":
    "Refund requested. {a} will be returned, and you keep access until midnight tonight.",
  "환불 신청이 접수되었습니다. {a}이 환불되며, 이용은 지금 종료됩니다.":
    "Refund requested. {a} will be returned, and your access ends now.",
  "환불 신청이 접수되었습니다.": "Your refund request has been received.",
  "{p} 플랜이 바로 적용되었습니다. 차액 {a}이 결제되었습니다.":
    "You are on {p} as of now. {a} has been charged.",
  "{p} 플랜이 바로 적용되었습니다. 지금 청구된 금액은 없습니다.":
    "You are on {p} as of now. Nothing was charged.",
  "{d}부터 {p} 플랜으로 변경됩니다.": "You move to {p} on {d}.",
  "플랜 변경이 취소되었습니다.": "The scheduled change has been cancelled.",
  "처리하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.": "Could not complete. Please try again in a moment.",
  "등록하신 카드로 결제가 승인되지 않았습니다. 결제일로부터 1일·3일·5일·7일째에 자동으로 다시 시도하며, 결제가 완료되면 그 시점부터 새로운 이용 기간이 시작됩니다. 카드를 다시 등록하시면 즉시 재개하실 수 있습니다.":
    "The card on file was declined. We retry automatically on days 1, 3, 5 and 7 after the billing date; once a payment succeeds, a new billing period starts from that moment. Registering a card again restores access immediately.",
  "결제 재시도가 중지되며 구독이 즉시 종료됩니다. 이미 결제된 금액은 없으므로 추가로 청구되는 금액도 없습니다.":
    "Retries stop and your subscription ends immediately. Nothing was charged for this period, so there is nothing further to bill.",
  "구독이 해지되었으며, 결제 재시도도 중지되었습니다.":
    "Your subscription has been cancelled and payment retries have stopped.",
  "해지하시면 이미 결제하신 이용 기간이 끝날 때까지는 그대로 이용하실 수 있습니다.":
    "If you cancel, you keep access until the period you have paid for ends.",
  "결제 수단이 변경되었습니다. 다음 결제일부터 새 카드로 청구됩니다.":
    "Your payment method has been updated. The new card will be charged from your next billing date.",
  "미리보기입니다. 실제로 돈이 오가지 않습니다.": "Preview only — no real payment is made.",
});

/* 해지·환불 사유. 화면이 영어여도 접수함으로는 늘 한국어로 보낸다 — 접수함이
   하나인데 언어별로 다른 문구가 섞이면 모아서 세어 볼 수가 없다. */
const WHY = {
  cancel: ["가격이 부담됩니다", "원하는 종목·정보가 부족합니다",
           "리포트 내용이 기대와 다릅니다", "자주 이용하지 않습니다",
           "일시적으로 이용을 중단합니다", "기타"],
  refund: ["실수로 결제했습니다", "서비스가 기대와 다릅니다",
           "오류·장애로 정상적으로 이용하지 못했습니다", "중복으로 결제되었습니다", "기타"],
};
if (window.KOSi18n) window.KOSi18n.register({
  "가격이 부담됩니다": "Too expensive",
  "원하는 종목·정보가 부족합니다": "Missing stocks or information I want",
  "리포트 내용이 기대와 다릅니다": "Reports were not what I expected",
  "자주 이용하지 않습니다": "I don't use it often",
  "일시적으로 이용을 중단합니다": "Pausing for now",
  "기타": "Other",
  "실수로 결제했습니다": "I paid by mistake",
  "서비스가 기대와 다릅니다": "The service was not what I expected",
  "오류·장애로 정상적으로 이용하지 못했습니다": "I could not use it because of a fault or outage",
  "중복으로 결제되었습니다": "I was charged twice",
});

/* ────────────────────────────── 모양 ────────────────────────────── */

function css() {
  if (document.getElementById("kos-settings-css")) return;
  const s = document.createElement("style");
  s.id = "kos-settings-css";
  s.textContent = `
.ks-ov{position:fixed;inset:0;z-index:1100;background:rgba(10,11,19,.5);
  display:flex;align-items:center;justify-content:center;padding:20px;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
/* 실사이트 창(420px)보다 넓다. 왼쪽에 목록이 서고 오른쪽에 내용이 오므로
   좁으면 둘 다 답답해진다. 높이를 고정해 칸을 옮겨도 창이 들썩이지 않게 한다. */
.ks-card{width:100%;max-width:860px;height:min(600px,86vh);display:flex;flex-direction:column;
  background:var(--bg-1);border-radius:var(--radius-lg,16px);overflow:hidden;
  box-shadow:var(--shadow-2,0 24px 64px rgba(15,23,42,.24));
  border:1px solid var(--border-2,rgba(0,0,0,.07))}
:root[data-theme="dark"] .ks-card{background:#1a1b26;border-color:rgba(255,255,255,.08)}
.ks-top{display:flex;align-items:center;justify-content:space-between;flex:none;
  padding:15px 18px;border-bottom:1px solid var(--hair,rgba(0,0,0,.07))}
.ks-title{font:700 16px/1.3 var(--font-sans,system-ui);color:var(--fg-1)}
.ks-x{border:0;background:transparent;cursor:pointer;font-size:19px;line-height:1;
  color:var(--fg-3);padding:4px 6px;border-radius:8px}
.ks-x:hover{background:rgba(0,0,0,.06)}
:root[data-theme="dark"] .ks-x:hover{background:rgba(255,255,255,.08)}
.ks-main{flex:1;display:flex;min-height:0}
.ks-nav{flex:none;width:196px;padding:12px 10px;overflow:auto;
  border-right:1px solid var(--hair,rgba(0,0,0,.07))}
.ks-nav button{display:block;width:100%;text-align:left;border:0;background:transparent;
  cursor:pointer;padding:9px 12px;border-radius:9px;color:var(--fg-2);
  font:600 13.5px var(--font-sans,system-ui)}
.ks-nav button:hover{background:rgba(0,0,0,.05)}
:root[data-theme="dark"] .ks-nav button:hover{background:rgba(255,255,255,.06)}
.ks-nav button[aria-selected="true"]{background:rgba(47,109,246,.1);color:var(--brand-blue,#2f6df6)}
.ks-panel{flex:1;min-width:0;overflow:auto;padding:18px 22px 22px}
.ks-sec{padding:0 0 16px}
/* 앞 칸과 성격이 다른 칸. 구독 상태·버튼 바로 아래에 '결제 내역' 머리가
   붙어 버려 안내 문구와 표 제목이 한 덩어리로 읽혔다. 줄 하나로 끊는다. */
.ks-sec.sep{margin-top:26px;padding-top:20px;border-top:1px solid var(--hair,rgba(0,0,0,.07))}
.ks-h{margin:0 0 10px;font:700 12px/1.3 var(--font-sans,system-ui);color:var(--fg-3);
  letter-spacing:.04em;text-transform:uppercase}
.ks-kv{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;
  font:400 13.5px/1.6 var(--font-sans,system-ui);margin:0}
.ks-kv dt{color:var(--fg-3);white-space:nowrap}
.ks-kv dd{margin:0;color:var(--fg-1);word-break:break-all}
.ks-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:7px 0}
.ks-row .ks-lab{font:600 13.5px/1.45 var(--font-sans,system-ui);color:var(--fg-1)}
.ks-row .ks-sub{display:block;margin-top:3px;font:400 11.5px/1.55 var(--font-sans,system-ui);color:var(--fg-3)}
.ks-seg{display:inline-flex;flex:none;width:184px;border:1px solid var(--border-2,rgba(0,0,0,.1));
  border-radius:9999px;overflow:hidden}
.ks-seg button{flex:1 1 50%;border:0;background:transparent;cursor:pointer;padding:7px 0;
  font:600 12.5px var(--font-sans,system-ui);color:var(--fg-3);white-space:nowrap}
.ks-seg button[aria-pressed="true"]{background:var(--brand-blue,#2f6df6);color:#fff}
.ks-sw{position:relative;flex:none;width:44px;height:25px;border-radius:9999px;border:0;cursor:pointer;
  background:var(--border-2,rgba(0,0,0,.16));transition:background .16s}
.ks-sw[aria-checked="true"]{background:var(--brand-blue,#2f6df6)}
.ks-sw::after{content:"";position:absolute;top:3px;left:3px;width:19px;height:19px;border-radius:50%;
  background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.28);transition:transform .16s}
.ks-sw[aria-checked="true"]::after{transform:translateX(19px)}
.ks-sw:disabled{opacity:.5;cursor:default}
.ks-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.ks-btn{display:inline-block;padding:10px 14px;border-radius:10px;cursor:pointer;
  font:600 13px var(--font-sans,system-ui);text-align:center;text-decoration:none;
  border:1px solid var(--border-2,rgba(0,0,0,.1));background:transparent;color:var(--fg-1)}
.ks-btn:hover{background:rgba(0,0,0,.04)}
:root[data-theme="dark"] .ks-btn:hover{background:rgba(255,255,255,.06)}
.ks-btn.primary{background:var(--brand-blue,#2f6df6);border-color:transparent;color:#fff}
.ks-btn.primary:hover{filter:brightness(1.05)}
.ks-btn.danger{color:#c0282b;border-color:rgba(192,40,43,.3)}
:root[data-theme="dark"] .ks-btn.danger{color:#ff8a8c;border-color:rgba(255,138,140,.28)}
.ks-btn:disabled{opacity:.55;cursor:default}
.ks-badge{display:inline-block;padding:3px 9px;border-radius:9999px;
  font:700 11.5px var(--font-sans,system-ui)}
.ks-badge.on{background:rgba(10,125,50,.12);color:#0a7d32}
.ks-badge.warn{background:rgba(192,40,43,.12);color:#c0282b}
:root[data-theme="dark"] .ks-badge.on{background:rgba(61,220,132,.14);color:#3ddc84}
:root[data-theme="dark"] .ks-badge.warn{background:rgba(255,138,140,.14);color:#ff8a8c}
.ks-msg{display:none;margin:10px 0 0;font:600 12px/1.5 var(--font-sans,system-ui)}
.ks-msg.on{display:block}
.ks-msg.ok{color:var(--brand-blue,#2f6df6)}
.ks-msg.err{color:#c0282b}
:root[data-theme="dark"] .ks-msg.err{color:#ff8a8c}
.ks-note{margin:14px 0 0;font:400 11.5px/1.6 var(--font-sans,system-ui);color:var(--fg-3)}
.ks-note a{color:var(--fg-2);text-decoration:underline;text-underline-offset:2px}
/* 결제 내역 — 좁은 칸에서도 가로로 넘치지 않게 자기 안에서만 스크롤한다 */
.ks-hist{width:100%;overflow-x:auto;margin-top:8px}
.ks-hist table{width:100%;border-collapse:collapse;font:400 12.5px/1.5 var(--font-sans,system-ui)}
.ks-hist th{text-align:left;padding:6px 10px 6px 0;color:var(--fg-3);font-weight:600;white-space:nowrap;
  border-bottom:1px solid var(--hair,rgba(0,0,0,.07))}
.ks-hist td{padding:8px 10px 8px 0;color:var(--fg-1);white-space:nowrap;
  border-bottom:1px solid var(--hair,rgba(0,0,0,.05))}
/* 확인 대화상자 — 설정 창(1100) 위에 선다 */
.ks-dlg{position:fixed;inset:0;z-index:1200;display:flex;align-items:center;justify-content:center;
  padding:20px;background:rgba(10,11,19,.55);-webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
.ks-dlg-card{width:100%;max-width:440px;max-height:86vh;overflow:auto;padding:22px 22px 18px;
  background:var(--bg-1);border-radius:16px;border:1px solid var(--border-2,rgba(0,0,0,.08));
  box-shadow:0 24px 64px rgba(15,23,42,.3)}
:root[data-theme="dark"] .ks-dlg-card{background:#1a1b26;border-color:rgba(255,255,255,.08)}
.ks-dlg-t{margin:0 0 8px;font:700 15.5px/1.4 var(--font-sans,system-ui);color:var(--fg-1)}
.ks-dlg-b{margin:0;font:400 13px/1.65 var(--font-sans,system-ui);color:var(--fg-2);word-break:keep-all}
.ks-dlg-q{margin:16px 0 8px;font:600 12px var(--font-sans,system-ui);color:var(--fg-3)}
.ks-dlg-r{display:flex;align-items:flex-start;gap:8px;padding:5px 0;
  font:400 12.5px/1.45 var(--font-sans,system-ui);color:var(--fg-2);cursor:pointer}
.ks-dlg-r input{margin-top:2px;flex:none}
.ks-dlg-d{width:100%;margin-top:8px;padding:8px 10px;border-radius:9px;resize:vertical;
  border:1px solid var(--border-2,rgba(0,0,0,.12));background:transparent;color:var(--fg-1);
  font:400 12.5px/1.5 var(--font-sans,system-ui)}
/* 좁은 화면 — 왼쪽 목록을 위쪽 가로줄로 눕힌다. 196px 를 떼어 주면
   내용이 들어갈 자리가 남지 않는다. */
@media (max-width:640px){
  .ks-ov{padding:0}
  .ks-card{max-width:none;height:100%;border-radius:0}
  .ks-main{flex-direction:column}
  .ks-nav{width:auto;display:flex;gap:6px;overflow-x:auto;padding:10px 12px;
    border-right:0;border-bottom:1px solid var(--hair,rgba(0,0,0,.07))}
  .ks-nav button{width:auto;white-space:nowrap;padding:8px 12px}
  .ks-panel{padding:16px}
}`;
  document.head.appendChild(s);
}

/* ────────────────────────────── 조각 ────────────────────────────── */

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function segRow(label, options, current, onPick) {
  const row = el("div", "ks-row");
  row.appendChild(el("div", "ks-lab", T(label)));
  const seg = el("div", "ks-seg");
  const btns = options.map(o => {
    const b = el("button", null, T(o.label));
    b.type = "button";
    b.setAttribute("aria-pressed", String(o.value === current));
    b.addEventListener("click", () => {
      btns.forEach(x => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      onPick(o.value);
    });
    seg.appendChild(b);
    return b;
  });
  row.appendChild(seg);
  return row;
}

const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';

function currentTheme() {
  const a = document.documentElement.getAttribute("data-theme");
  if (a) return a;
  try { return localStorage.getItem("kos-theme") || "dark"; } catch (_) { return "dark"; }
}
function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("kos-theme", t); } catch (_) {}
  const i = document.getElementById("themeIcon");
  if (i) i.innerHTML = t === "dark" ? SUN : MOON;
}
function currentLang() { return (window.KOSi18n ? window.KOSi18n.lang : "ko") || "ko"; }

/* ────────────────────────── 칸별로 그리기 ────────────────────────── */

function paneGeneral() {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("일반")));
  s.appendChild(segRow("테마",
    [{ label: "라이트", value: "light" }, { label: "다크", value: "dark" }],
    currentTheme(), applyTheme));
  if (window.KOSi18n) {
    s.appendChild(segRow("언어",
      [{ label: "한국어", value: "ko" }, { label: "English", value: "en" }],
      currentLang(), v => { try { window.KOSi18n.setLang(v); } catch (_) {} }));
  }
  box.appendChild(s);
  return box;
}

function paneNotifications(user) {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("알림")));

  const row = el("div", "ks-row");
  const lab = el("div", "ks-lab", T("마케팅 정보 수신"));
  lab.appendChild(el("span", "ks-sub",
    T("새 리포트와 서비스 소식을 이메일로 받습니다. 받지 않아도 서비스 이용에는 아무 영향이 없습니다.")));
  const sw = el("button", "ks-sw");
  sw.type = "button";
  sw.setAttribute("role", "switch");
  sw.setAttribute("aria-checked", "false");
  sw.disabled = true;
  row.appendChild(lab); row.appendChild(sw);
  s.appendChild(row);

  const msg = el("p", "ks-msg");
  s.appendChild(msg);
  box.appendChild(s);

  const say = (t, k) => { msg.textContent = T(t); msg.className = "ks-msg on " + k; };

  getMarketing(user.uid)
    .then(on => { sw.setAttribute("aria-checked", String(!!on)); sw.disabled = false; })
    .catch(() => say("불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.", "err"));

  /* 누르는 순간 저장한다. '저장' 버튼을 따로 두면 눌렀다고 생각하고 나가는
     사람이 반드시 생긴다. 실패하면 스위치를 되돌리고 이유를 말한다. */
  sw.addEventListener("click", async () => {
    const was = sw.getAttribute("aria-checked") === "true";
    sw.setAttribute("aria-checked", String(!was));
    sw.disabled = true;
    msg.className = "ks-msg";
    try { await setMarketing(user.uid, !was); }
    catch (_) {
      sw.setAttribute("aria-checked", String(was));
      say("저장하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.", "err");
    }
    sw.disabled = false;
  });
  return box;
}

/* ── 구독 ────────────────────────────────────────────────────────
   billing.html 이 하던 일을 이 칸으로 옮긴다. 처음에는 '지금 어떤 상태인가'
   만 옮기고 버튼은 이름만 달아 두었는데, 그건 화면이지 기능이 아니었다.
   페이지가 실제로 하던 것을 그대로 가져온다.

     · 되돌리기 어려운 것(해지·환불·플랜 변경)은 반드시 한 번 묻는다
     · 업그레이드는 얼마가 청구되는지 보여 주고 묻는다
     · 해지·환불은 사유를 함께 받는다(답하지 않아도 진행된다)
     · 결제 실패·이용 종료도 각각 제 화면을 갖는다
     · 결제 내역을 보여 준다

   화면이 좁아졌다고 판단을 줄이면, 사용자는 무슨 일이 일어났는지 모르는
   채로 구독을 잃는다. */

/* 확인 대화상자. why 를 주면 사유를 함께 묻는다.
   돌려주는 값: 취소면 false, 확인이면 { reason, detail }.
   답하지 않아도 진행된다 — 환불은 권리이지 설문의 대가가 아니다. */
function ask(title, body, why) {
  css();
  const ov = el("div", "ks-dlg");
  const card = el("div", "ks-dlg-card");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");
  card.appendChild(el("p", "ks-dlg-t", title));
  /* 본문이 여러 문단일 수 있다. 빈 줄로 끊어 문단마다 <p> 를 만든다 —
     줄바꿈 문자를 그대로 넣으면 HTML 이 공백 하나로 뭉개 한 덩어리가 된다. */
  String(body).split("\n\n").forEach(p => card.appendChild(el("p", "ks-dlg-b", p)));

  let boxes = [], detail = null;
  if (why) {
    card.appendChild(el("div", "ks-dlg-q", T("사유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)")));
    WHY[why].forEach(r => {
      const lab = el("label", "ks-dlg-r");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.value = r;                       // 값은 늘 한국어다(접수함이 하나다)
      lab.appendChild(cb);
      lab.appendChild(el("span", null, T(r)));
      card.appendChild(lab);
      boxes.push(cb);
    });
    detail = document.createElement("textarea");
    detail.className = "ks-dlg-d";
    detail.rows = 2;
    detail.placeholder = T("자세한 의견 (선택)");
    card.appendChild(detail);
  }

  const btns = el("div", "ks-btns");
  const no = el("button", "ks-btn", T("취소"));
  const yes = el("button", "ks-btn primary", T("확인"));
  no.type = yes.type = "button";
  btns.appendChild(no); btns.appendChild(yes);
  card.appendChild(btns);
  ov.appendChild(card);
  document.body.appendChild(ov);
  yes.focus();

  return new Promise(res => {
    const done = v => {
      ov.remove();
      document.removeEventListener("keydown", onKey);
      res(v);
    };
    function onKey(e) { if (e.key === "Escape") done(false); }
    document.addEventListener("keydown", onKey);
    yes.addEventListener("click", () => done(why
      ? { reason: boxes.filter(b => b.checked).map(b => b.value).join(", "),
          detail: detail.value.trim() }
      : {}));
    no.addEventListener("click", () => done(false));
    ov.addEventListener("click", e => { if (e.target === ov) done(false); });
  });
}

/* 사유를 접수함으로 보낸다(회원 탈퇴와 같은 경로).
   최선 노력이다 — 실패해도 해지·환불은 이미 끝났고, 사용자에게 '사유 전송
   실패'를 알릴 이유가 없다. 기다리지도 않는다. */
function sendReason(category, ans) {
  const message = [ans.reason && "사유: " + ans.reason, ans.detail].filter(Boolean).join("\n");
  if (!message) return;
  const u = auth.currentUser;
  call("submitForm", { kind: "feedback", category, message,
                       email: (u && u.email) || "", page: "구독 관리" })
    .catch(e => console.warn("[settings] 사유 전송 실패", e && e.message));
}

function payLabel(p) {
  const name = (planOf(p.plan) || {}).name || String(p.plan || "").toUpperCase();
  if (p.kind === "subscription") return T("{p} 월 구독").replace("{p}", name);
  if (p.kind === "upgrade") return T("{p} 업그레이드 차액").replace("{p}", name);
  if (p.kind === "failed") return T("정기결제 실패");
  if (p.kind === "refund") {
    const why = p.why === "used" ? T("이용분 차감")
              : p.why === "withdraw" ? T("청약철회")
              : p.why === "left" ? T("잔여 기간") : "";
    return why ? `${T("환불")} · ${why}` : T("환불");
  }
  return p.description || "";
}

function paneSubscription() {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("구독")));
  const body = el("div");
  s.appendChild(body);
  const msg = el("p", "ks-msg");
  s.appendChild(msg);
  box.appendChild(s);

  const say = (t, k) => { msg.textContent = t; msg.className = "ks-msg on " + k; };

  /* 결제 수단을 바꾸고 돌아온 길이면 한 번만 알린다. auth-state 가 주소에서
     ?card=1 을 지우기 전에 여기로 넘겨 준다. 읽고 나면 지운다 — 칸을 옮겼다
     돌아올 때마다 같은 안내가 뜨면 무슨 일이 또 일어난 줄 안다. */
  if (window.__KOS_CARD_NOTICE) {
    delete window.__KOS_CARD_NOTICE;
    say(T("결제 수단이 변경되었습니다. 다음 결제일부터 새 카드로 청구됩니다."), "ok");
  }

  /* 결과 문구(msg)는 다시 그려지는 body 바깥에 둔다. 옛 페이지는 이걸 안쪽에
     두는 바람에 확인을 눌러도 아무 말도 안 뜨는 것처럼 보였고, 그걸 메우려고
     따로 장치를 만들어야 했다. 자리를 옮기면 그 장치가 필요 없다. */

  body.appendChild(el("p", "ks-note", T("불러오는 중…")));

  const kv = (dl, k, v) => {
    if (v == null || v === "") return;
    dl.appendChild(el("dt", null, T(k)));
    const dd = el("dd");
    if (v instanceof Node) dd.appendChild(v); else dd.textContent = v;
    dl.appendChild(dd);
  };

  const cardHref = sub =>
    "checkout.html?plan=" + encodeURIComponent((sub && sub.plan) || "basic") + "&method=1";

  /* 결제창 키가 아직 안 꽂혔으면 카드 관련 버튼은 눌러야 빈 화면이다. 다만
     미리보기(__KOSDEMO)는 토스 없이 checkout.js 안에서 흉내내므로 키가 없어도
     된다 — 스테이징이 그쪽이라 payReady 만 보면 확인할 것을 못 본다. */
  const canCard = () => payReady || !!window.__KOSDEMO;

  /* 되돌리기 어려운 동작 한 벌. 확인 → 호출 → 결과 문구 → 사유 전송 순서다.
     사유는 처리에 성공한 뒤에 보낸다. 먼저 보내면 해지가 실패했는데 '해지 사유'
     만 접수되어, 있지도 않은 해지가 집계에 잡힌다. */
  async function act(btn, { confirm, fn, arg, done, survey }) {
    const ans = confirm ? await confirm() : {};
    if (!ans) return;
    const all = [...body.querySelectorAll("button")];
    all.forEach(b => { b.disabled = true; });
    msg.className = "ks-msg";
    try {
      /* arg 를 함수로도 받는다. 확인 창에서 알아낸 값(예: 사용자가 본 환불
         금액)을 넘기려면 버튼을 만들 때가 아니라 이때 정해져야 한다. */
      const res = await call(fn, (typeof arg === "function" ? arg() : arg) || {});
      if (survey) sendReason(survey, ans);
      say(done(res && res.data), "ok");
      /* 데모·서버 모두 상태가 바뀌면 onChange 로 다시 그린다. 그래도 여기서
         한 번 더 그린다 — 알림이 안 오는 구현에서도 화면이 멈추지 않게. */
      refresh();
    } catch (e) {
      console.error("[settings] " + fn, e);
      say(e && e.message ? e.message : T("처리하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다."), "err");
      all.forEach(b => { b.disabled = false; });
    }
  }

  function button(label, cls, onClick) {
    const b = el("button", "ks-btn" + (cls ? " " + cls : ""), T(label));
    b.type = "button";
    b.addEventListener("click", () => onClick(b));
    return b;
  }

  /* payments 가 null 이면 아예 안 그린다(배열이면 비어 있어도 그린다).
     '내역을 못 받았다' 와 '내역이 없다' 는 다른 말이다. 둘을 같이 취급하면
     결제한 사람에게 '아직 결제 내역이 없습니다' 가 뜬다. */
  function histSection(payments) {
    if (!payments) return null;
    const wrap = el("div", "ks-sec sep");
    wrap.appendChild(el("div", "ks-h", T("결제 내역")));
    if (!payments.length) {
      wrap.appendChild(el("p", "ks-note", T("아직 결제 내역이 없습니다.")));
      return wrap;
    }
    const en = EN();
    const scroll = el("div", "ks-hist");
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const hr = document.createElement("tr");
    ["일자", "내용", "금액", "상태"].forEach(h => {
      const th = document.createElement("th");
      th.textContent = T(h);
      hr.appendChild(th);
    });
    thead.appendChild(hr);
    table.appendChild(thead);
    const tb = document.createElement("tbody");
    payments.forEach(p => {
      const tr = document.createElement("tr");
      const amt = (p.amount < 0 ? "-" : "") + won(Math.abs(p.amount || 0), en);
      const stat = p.status === "refunded" ? T("환불")
                 : p.status === "failed" ? T("실패") : T("결제 완료");
      [fmtDay(p.paidAt || p.createdAt, en), payLabel(p), amt, stat].forEach(v => {
        const td = document.createElement("td");
        td.textContent = v;
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    scroll.appendChild(table);
    wrap.appendChild(scroll);
    return wrap;
  }

  /* 화면은 네 갈래다. 처음에는 active 만 그리고 나머지를 전부 '무료'로
     떨어뜨렸는데, 그러면 카드 결제가 밀린 유료 회원이 '무료로 이용 중' 을
     보고 카드를 고칠 길도 없이 끝난다. 상태마다 할 말과 할 일이 다르다.

       구독 없음   요금제로 보낸다
       이용 중     전부 보여 주고 전부 할 수 있다
       결제 실패   왜 막혔는지 말하고 카드 재등록으로 보낸다
       이용 종료   끝난 사실을 말하고 다시 시작할 길을 준다 */
  function draw(st, usage, payments) {
    body.textContent = "";
    const en = EN();
    const sub = (st && st.sub) || null;
    const active = !!(st && st.active);
    /* 환불이 끝났는가. 오늘 값을 받은 환불은 자정까지 살아 있어서 status 가
       그대로 "active" 다 — 그것만 보면 방금 환불한 사람에게 '이용 중' 과 해지·
       플랜 변경 버튼을 그대로 보여 주게 된다. 환불 여부는 refundedAt 이 말한다. */
    const refunded = !!(sub && sub.refundedAt);
    const due = !active && !refunded && sub && sub.status === "past_due";
    /* 이용 중도, 결제 실패도, 환불도 아닌데 기간이 있으면 끝난 구독이다.

       전에는 sub.status === "refunded" 도 같이 봤는데 그런 상태는 없다 —
       환불은 status 를 "active" 로 두고 refundedAt 으로 표시한다(그래야 오늘
       값을 받은 환불이 자정까지 살아 있다). 구독 문서에 들어가는 status 는
       active · past_due · expired · deleted 넷뿐이다. 죽은 조건을 남겨 두면
       다음에 읽는 사람이 없는 상태를 있는 줄로 안다.

       currentPeriodEnd 가 없는 문서(자물쇠만 걸린 껍데기)는 여기서 걸리지 않고
       아래 '무료' 로 떨어진다 — 그게 맞다. */
    const ended = !active && !due && sub && sub.currentPeriodEnd;
    const plan = planOf(sub && sub.plan);
    const endDay = sub ? fmtDay(sub.currentPeriodEnd, en) : "";

    if (!sub || (!active && !due && !ended)) {
      body.appendChild(el("p", "ks-note",
        T("무료로 이용 중입니다. 분석·전망·리스크 등 유료 구간은 멤버십에서 보실 수 있습니다.")));
      const btns = el("div", "ks-btns");
      const a = el("a", "ks-btn primary", T("플랜 보기"));
      a.href = "pricing.html";
      btns.appendChild(a);
      body.appendChild(btns);
      const h = histSection(payments); if (h) body.appendChild(h);
      return;
    }

    const dl = el("dl", "ks-kv");
    kv(dl, "이용 중인 플랜", (plan && plan.name) || String(sub.plan || "").toUpperCase());

    const badge = el("span", "ks-badge " + (active && !refunded && !sub.cancelAtPeriodEnd ? "on" : "warn"),
      T(refunded ? "환불 완료"
        : due ? "결제 실패"
        : ended ? "이용 종료됨"
        : sub.cancelAtPeriodEnd ? "해지 예약됨" : "이용 중"));
    kv(dl, "상태", badge);

    if ((active || due) && !refunded) {
      kv(dl, "결제 금액", won((plan && plan.price) || 0, en));
      if (plan && plan.limit) kv(dl, "하루 열람 한도", `${plan.limit}${en ? "" : "개"}`);
    }

    /* 남은 열람으로 적는다. '오늘 열람 2건' 은 많이 본 건지 적게 본 건지를
       한도와 견줘 봐야 알 수 있다 — 사용자가 궁금한 건 몇 개가 남았는가다.
       usage.limit 이 0 일 수 있어 ?? 가 아니라 || 로 받는다(0 ?? x 는 0). */
    if (active && usage && typeof usage.used === "number") {
      const lim = usage.limit || (plan && plan.limit) || 0;
      if (lim) kv(dl, "오늘 남은 열람",
        T("{r}개 / {l}개").replace("{r}", Math.max(0, lim - usage.used)).replace("{l}", lim));
    }

    if (endDay) kv(dl, active && !sub.cancelAtPeriodEnd ? "다음 결제일" : "이용 종료일", endDay);

    /* 다운그레이드는 다음 결제일부터라 지금 화면에는 아무것도 안 바뀐다.
       예약된 걸 어디에도 안 적어 두면, 확인을 눌러도 아무 일도 안 일어난 것처럼
       보이고 다음 달에 왜 금액이 바뀌었는지 알 수 없다. */
    const pend = active && sub.pendingPlan && sub.pendingPlan !== sub.plan
      ? planOf(sub.pendingPlan) : null;
    if (pend) kv(dl, "예정된 변경",
      T("{d}부터 {p}").replace("{d}", endDay).replace("{p}", pend.name));

    if (sub.startedAt) kv(dl, "구독 시작일", fmtDay(sub.startedAt, en));

    const card = sub.card;
    if ((active || due) && !refunded) kv(dl, "결제 수단", card && (card.company || card.number)
      ? ((card.company || T("등록하신 카드")) + " " + (card.number || "")).trim()
      : T("등록된 카드가 없습니다."));

    body.appendChild(dl);

    const btns = el("div", "ks-btns");

    /* 환불이 끝났으면 더 할 일이 없다. 해지·플랜 변경 버튼을 남겨 두면 이미
       끝난 구독을 다시 만지려 들고, 서버는 거절한다 — 눌리는 버튼이 거절만
       하는 것보다 없는 편이 낫다. 남은 건 언제까지 볼 수 있는지 뿐이다. */
    if (refunded) {
      body.appendChild(el("p", "ks-note",
        T(active ? "환불이 완료되었습니다. 오늘 자정까지 이용하실 수 있으며, 언제든 다시 시작하실 수 있습니다."
                 : "환불이 완료되어 이용이 종료되었습니다. 언제든 다시 시작하실 수 있습니다.")));
      /* '멤버십 보기' 가 아니라 '다시 시작하기' 다. 환불하고 마음이 바뀐
         사람에게 필요한 건 요금표 구경이 아니라 결제로 가는 길이다. */
      const a = el("a", "ks-btn primary", T("다시 시작하기"));
      a.href = "pricing.html";
      btns.appendChild(a);
      body.appendChild(btns);
      const h = histSection(payments); if (h) body.appendChild(h);
      return;
    }

    if (due) {
      /* 결제가 막힌 사람에게 필요한 건 설명과 카드 한 장이다. 플랜 변경까지
         같이 두면 무엇부터 눌러야 할지가 흐려지므로 두 가지만 둔다.

         해지는 빼지 않는다. 카드가 거절되면 정해진 날에 다시 결제를 시도하므로,
         그만두시려는 분께 멈출 방법이 없으면 원치 않는 요금이 청구될 수 있다. */
      const a = el("a", "ks-btn primary", T("결제 수단 변경"));
      a.href = cardHref(sub);
      btns.appendChild(a);
      btns.appendChild(button("구독 해지", "danger", b => act(b, {
        confirm: () => ask(T("구독을 해지하시겠습니까?"),
          T("결제 재시도가 중지되며 구독이 즉시 종료됩니다. 이미 결제된 금액은 없으므로 추가로 청구되는 금액도 없습니다."),
          "cancel"),
        fn: "cancelSubscription",
        done: () => T("구독이 해지되었으며, 결제 재시도도 중지되었습니다."),
        survey: "구독 해지",
      })));
      body.appendChild(btns);
      body.appendChild(el("p", "ks-note",
        T("등록하신 카드로 결제가 승인되지 않았습니다. 결제일로부터 1일·3일·5일·7일째에 자동으로 다시 시도하며, 결제가 완료되면 그 시점부터 새로운 이용 기간이 시작됩니다. 카드를 다시 등록하시면 즉시 재개하실 수 있습니다.")));
      const h = histSection(payments); if (h) body.appendChild(h);
      return;
    }

    if (ended) {
      const a = el("a", "ks-btn primary", T("멤버십 보기"));
      a.href = "pricing.html";
      btns.appendChild(a);
      body.appendChild(btns);
      const h = histSection(payments); if (h) body.appendChild(h);
      return;
    }

    /* ── 이용 중 ─────────────────────────────────────────────── */

    const other = sub.plan === "pro" ? PLANS.basic : PLANS.pro;
    const up = !pend && (other.price || 0) > ((plan && plan.price) || 0);
    /* 해지 예약과 플랜 변경 예약은 함께 둘 수 없다 — 서버가 갱신할 때 해지를
       먼저 보고 끝내므로, 둘 다 걸어 두면 변경은 조용히 사라진다. 한쪽을
       고르면 다른 쪽이 풀린다는 걸 누르기 전에 말해 준다. */
    const alsoResume = sub.cancelAtPeriodEnd ? T(" 예약해 두신 해지는 함께 취소됩니다.") : "";

    btns.appendChild(button(
      pend ? "변경 취소" : sub.plan === "pro" ? "BASIC으로 변경" : "PRO로 업그레이드",
      null,
      b => act(b, {
        confirm: () => {
          if (pend) return ask(T("플랜 변경을 취소하시겠습니까?"),
            T("{date} 이후에도 {p} 플랜이 그대로 유지됩니다.")
              .replace("{date}", endDay).replace("{p}", (plan && plan.name) || "") + alsoResume);
          if (up) {
            /* 얼마가 청구되는지 보여 주고 묻는다. 금액 없이 확인을 받으면
               카드에서 얼마가 빠져나갈지 모르는 채로 누르게 된다. */
            const diff = upgradeDiff(sub, other.id);
            return ask(T("PRO로 업그레이드하시겠습니까?"),
              (diff >= MIN_CHARGE
                ? T("즉시 PRO가 적용됩니다. 남은 기간에 해당하는 BASIC 금액을 차감한 차액 {a}이 등록하신 카드로 지금 결제되며, 결제일은 그대로 유지됩니다.")
                    .replace("{a}", won(diff, en))
                : T("즉시 PRO가 적용됩니다. 이번 결제 주기가 거의 끝나 지금 청구되는 금액은 없으며, 다음 결제일부터 PRO 요금으로 청구됩니다."))
              + alsoResume);
          }
          return ask(T("BASIC으로 변경하시겠습니까?"),
            T("{date}부터 BASIC이 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.")
              .replace("{date}", endDay) + alsoResume);
        },
        fn: "changePlan",
        arg: { plan: pend ? sub.plan : other.id },
        /* 업그레이드 결과 문구는 미리 보여 준 금액이 아니라 실제 청구액으로
           쓴다 — 둘이 다를 수 있고(서버가 다시 계산한다), 다르면 카드 명세와
           화면이 어긋난다. */
        done: d => pend ? T("플랜 변경이 취소되었습니다.")
          : up ? ((d && d.charged > 0)
              ? T("{p} 플랜이 바로 적용되었습니다. 차액 {a}이 결제되었습니다.")
                  .replace("{p}", other.name).replace("{a}", won(d.charged, en))
              : T("{p} 플랜이 바로 적용되었습니다. 지금 청구된 금액은 없습니다.")
                  .replace("{p}", other.name))
          : T("{d}부터 {p} 플랜으로 변경됩니다.")
              .replace("{d}", endDay).replace("{p}", other.name),
      })));

    if (canCard()) {
      /* 주소 모양은 pricing.html 과 같아야 한다(plan + method=1).
         method 를 빼면 결제창이 '카드 변경' 이 아니라 새 결제로 뜬다. */
      const a = el("a", "ks-btn", T("결제 수단 변경"));
      a.href = cardHref(sub);
      btns.appendChild(a);
    }

    /* 해지와 재개는 한 자리에서 뒤집힌다. 버튼을 둘 다 두면 지금 어느 상태인지가
       흐려진다. 재개는 되돌리기 쉬우므로 묻지 않는다. */
    if (sub.cancelAtPeriodEnd) {
      btns.appendChild(button("해지 취소", "primary", b => act(b, {
        fn: "resumeSubscription",
        done: () => T("해지가 취소되었습니다."),
      })));
    } else {
      btns.appendChild(button("구독 해지", "danger", b => act(b, {
        confirm: () => ask(T("구독을 해지하시겠습니까?"),
          T("{date}까지는 그대로 이용하실 수 있으며, 그 이후 결제되지 않습니다. 해지는 언제든지 취소하실 수 있습니다.")
            .replace("{date}", endDay)
          + (pend ? T(" 예약해 두신 {p} 플랜 변경은 함께 취소됩니다.").replace("{p}", pend.name) : ""),
          "cancel"),
        fn: "cancelSubscription",
        done: () => T("해지 예약이 완료되었습니다."),
        survey: "구독 해지",
      })));
    }

    /* 확인 창에서 사용자가 본 금액. 그 값 그대로 서버에 되돌려주고, 서버는
       다시 계산해 다르면 실행하지 않는다. 창을 띄운 뒤 리포트를 한 건 열면
       오늘이 이용일로 잡혀 금액이 달라지는데, 그대로 진행하면 사용자는 본 적
       없는 금액을 받게 된다. */
    let quoted = null;
    btns.appendChild(button("환불 신청", "danger", b => act(b, {
      /* 금액을 먼저 물어보고 창에 적는다. 여태 "이용하신 일수를 차감해
         산정됩니다" 만 적고 얼마인지는 누른 뒤에야 알려 줬다.

         그리고 플랜을 바꾸려고 환불을 누르는 사람이 있다. 환불했다 다시 사면
         한 달치를 새로 내지만, 플랜 변경은 남은 기간의 차액만 받고 바로
         적용된다. 누르기 전에 말해 주지 않으면 훨씬 비싼 길로 돌아가게 된다. */
      confirm: async () => {
        quoted = null;
        let head = T("환불 금액은 이용하신 일수를 차감해 산정됩니다.");
        try {
          const q = (await call("refundPreview", {})).data;
          if (q && Number.isFinite(q.amount)) {
            quoted = q.amount;
            const endMs = typeof q.endsAt === "number" ? q.endsAt : Date.parse(q.endsAt);
            head = T("{a}이 환불됩니다.").replace("{a}", won(q.amount, en)) + " "
              + (Number.isFinite(endMs) && endMs > Date.now()
                 ? T("오늘 자정까지 이용하실 수 있습니다.")
                 : T("이용은 신청 즉시 종료됩니다."));
          }
        } catch (e) {
          // 견적을 못 받아도 신청 자체는 막지 않는다. 금액만 못 적을 뿐이다.
          console.error("[settings] refundPreview", e);
        }
        return ask(T("환불을 신청하시겠습니까?"),
          head + "\n\n"
          + T("오늘 리포트를 보셨다면 오늘까지 이용하실 수 있고, 오늘 한 건도 보지 않으셨다면 오늘은 차감하지 않고 이용이 바로 종료됩니다.")
          + "\n\n" + T("플랜 변경만 원하시는 경우에는 환불 대신 위의 ‘플랜 변경’을 이용하여 주시기 바랍니다. 남은 기간에 대한 차액만 결제되며 즉시 적용됩니다."),
          "refund");
      },
      fn: "requestRefund",
      arg: () => (quoted == null ? {} : { expectAmount: quoted }),
      /* 언제까지 볼 수 있는지를 결과에 같이 적는다. 금액만 알려 주면 오늘
         남은 열람을 쓸 수 있는지 없는지를 눌러 봐야 안다.
         endsAt 은 미리보기가 밀리초, 서버가 ISO 문자열로 준다 — 문자열을
         숫자와 그냥 비교하면 늘 거짓이 되어 항상 '지금 종료' 로 적힌다.
         금액 이름도 둘이 다르다(서버 amount · 미리보기 refunded). */
      done: d => {
        const got = d && (Number.isFinite(d.amount) ? d.amount : d.refunded);
        if (!(got > 0)) return T("환불 신청이 접수되었습니다.");
        const endMs = typeof d.endsAt === "number" ? d.endsAt : Date.parse(d.endsAt);
        return (Number.isFinite(endMs) && endMs > Date.now()
          ? T("환불 신청이 접수되었습니다. {a}이 환불되며, 오늘 자정까지 이용하실 수 있습니다.")
          : T("환불 신청이 접수되었습니다. {a}이 환불되며, 이용은 지금 종료됩니다."))
          .replace("{a}", won(got, en));
      },
      survey: "환불 신청",
    })));

    body.appendChild(btns);
    body.appendChild(el("p", "ks-note",
      T("해지하시면 이미 결제하신 이용 기간이 끝날 때까지는 그대로 이용하실 수 있습니다.")));
    const hist = histSection(payments); if (hist) body.appendChild(hist);
    body.appendChild(el("p", "ks-note", T("미리보기입니다. 실제로 돈이 오가지 않습니다.")));
    if (window.KOSi18n) window.KOSi18n.apply();
  }

  /* paywall 이 아직 안 실렸을 수도 있다(스크립트 순서). 없으면 구독을 '없음'
     으로 그리는 대신 그렇게 말한다 — 유료 회원에게 무료라고 보여 주는 쪽이
     훨씬 나쁘다. */
  const pw = window.KOSPaywall;
  if (!pw) {
    body.textContent = "";
    body.appendChild(el("p", "ks-note", T("불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.")));
    return box;
  }

  const load = async (st) => {
    const [usage, payments] = await Promise.all([
      call("getUsage", {}).then(r => (r && r.data) || null).catch(() => null),
      /* 결제 내역. 미리보기든 실제든 같은 이름을 부른다 — 화면이 어느 쪽에
         붙어 있는지 따질 이유가 없다.

         받아 왔으면 배열이고(비어 있어도 배열이다), 못 받아 왔으면 null 이다.
         그 둘을 구별해야 한다. 실패를 빈 배열로 뭉개면 결제한 사람에게
         '아직 결제 내역이 없습니다' 가 뜬다 — 돈이 안 들어온 줄 안다. */
      call("listPayments", {})
        .then(r => ((r && r.data && r.data.items) || []))
        .catch(() => null),
    ]);
    draw(st, usage, payments);
  };
  const refresh = () => load(pw.state());

  /* ready 는 '인증이 한 번 확인됐다' 는 신호일 뿐 최신 상태가 아니다.
     한 번 resolve 되면 그때의 스냅샷을 영원히 들고 있다.

       ready.then(load)  ← 결제 전에 한 번 열어 봤다면 그때의 '구독 없음' 이
                            그대로 다시 그려진다. 결제하고 창을 열면 '무료로
                            이용 중' 이 뜬다.

     그래서 ready 는 기다리는 데만 쓰고, 값은 onChange 에서 받는다. onChange 는
     붙는 즉시 지금 스냅샷으로 한 번 부르고, 그 뒤 바뀔 때마다 부른다 — 첫 그림과
     이후 갱신이 같은 길로 들어와 어긋날 자리가 없다.

     ready 를 먼저 기다리는 건 여전히 필요하다. 바로 붙으면 인증이 끝나기 전의
     빈 스냅샷(user:null)이 먼저 와서 유료 회원에게 '무료' 가 한 번 스친다. */
  let off = null;
  pw.ready.then(() => {
    if (pw.onChange) off = pw.onChange(load);
    else load(pw.state());
  }).catch(() => {
    body.textContent = "";
    body.appendChild(el("p", "ks-note", T("불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.")));
  });

  /* 칸을 옮기거나 창을 닫으면 이 자리는 사라진다. 듣던 것을 놓지 않으면
     없어진 자리에 계속 그리려 든다. renderSettings 가 이걸 부른다. */
  box._kosOff = () => { if (off) { off(); off = null; } };

  return box;
}

function paneAccount(user, opts) {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("계정")));

  const dl = el("dl", "ks-kv");
  const nameDd = el("dd", null, user.displayName || "—");
  const mailDd = el("dd", null, user.email || "—");
  dl.appendChild(el("dt", null, T("닉네임"))); dl.appendChild(nameDd);
  dl.appendChild(el("dt", null, T("이메일"))); dl.appendChild(mailDd);
  s.appendChild(dl);

  accountInfo(user).then(info => {
    nameDd.textContent = info.name || "—";
    mailDd.textContent = info.email || T("등록된 주소 없음");
  }).catch(() => {});

  const btns = el("div", "ks-btns");
  const out = el("button", "ks-btn", T("로그아웃"));
  out.type = "button";
  out.addEventListener("click", async () => {
    try { await signOut(auth); } catch (_) {}
    location.href = "Home.html";
  });
  const del = el("button", "ks-btn danger", T("회원 탈퇴"));
  del.type = "button";
  del.addEventListener("click", () => {
    if (opts.onClose) opts.onClose();
    /* 탈퇴 화면은 auth-state.js 가 갖고 있다. 여기서 다시 만들면 확인
       절차가 두 벌이 되고, 한쪽만 고치게 된다. */
    if (window.KOSAccount && window.KOSAccount.withdraw) window.KOSAccount.withdraw();
  });
  btns.appendChild(out); btns.appendChild(del);
  s.appendChild(btns);

  const note = el("p", "ks-note");
  note.appendChild(document.createTextNode(T("약관과 개인정보 처리에 관한 내용은") + " "));
  const t1 = el("a", null, T("이용약관")); t1.href = "Terms.html"; note.appendChild(t1);
  note.appendChild(document.createTextNode(" · "));
  const t2 = el("a", null, T("개인정보처리방침")); t2.href = "Privacy.html"; note.appendChild(t2);
  note.appendChild(document.createTextNode(T("에서 확인할 수 있습니다.")));
  s.appendChild(note);

  box.appendChild(s);
  return box;
}

/* ────────────────────────────── 본체 ────────────────────────────── */

/* 주어진 자리에 설정을 그린다. tab 으로 처음 펼 칸을 정한다. */
export function renderSettings(box, opts = {}) {
  css();
  box.textContent = "";

  const user = auth.currentUser;
  const signedIn = !!(isConfigured && user);

  /* 화면(테마·언어)은 로그인과 상관없다. 그 기기의 취향이고 계정에
     저장되지 않는다. 그래서 비회원에게도 '일반' 은 보인다. */
  const tabs = [{ id: "general", label: "일반", make: () => paneGeneral() }];
  if (signedIn) {
    tabs.push({ id: "notifications", label: "알림", make: () => paneNotifications(user) });
    tabs.push({ id: "subscription", label: "구독", make: () => paneSubscription() });
    tabs.push({ id: "account", label: "계정", make: () => paneAccount(user, opts) });
  }

  const main = el("div", "ks-main");
  const nav = el("div", "ks-nav");
  nav.setAttribute("role", "tablist");
  const panel = el("div", "ks-panel");
  main.appendChild(nav); main.appendChild(panel);
  box.appendChild(main);

  const btns = [];
  function drop() {
    const cur = panel.firstChild;
    if (cur && typeof cur._kosOff === "function") { try { cur._kosOff(); } catch (_) {} }
  }
  function show(id) {
    const t = tabs.find(x => x.id === id) || tabs[0];
    btns.forEach(b => b.setAttribute("aria-selected", String(b.dataset.id === t.id)));
    drop();
    panel.textContent = "";
    panel.appendChild(t.make());
    panel.scrollTop = 0;
    if (window.KOSi18n) window.KOSi18n.apply();
  }
  box._kosOff = drop;

  tabs.forEach(t => {
    const b = el("button", null, T(t.label));
    b.type = "button";
    b.dataset.id = t.id;
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(t.id));
    nav.appendChild(b);
    btns.push(b);
  });

  if (!signedIn) {
    const s = el("div", "ks-sec");
    s.appendChild(el("p", "ks-note", T("계정 설정을 보려면 로그인이 필요합니다.")));
    const a = el("a", "ks-btn primary", T("로그인"));
    a.href = "Login.html?next=" + encodeURIComponent(
      (location.pathname.split("/").pop() || "Home.html") + (location.search || ""));
    s.appendChild(a);
    panel.appendChild(paneGeneral());
    panel.appendChild(s);
    btns[0].setAttribute("aria-selected", "true");
    if (window.KOSi18n) window.KOSi18n.apply();
    return;
  }

  show(opts.tab && tabs.some(t => t.id === opts.tab) ? opts.tab : "general");
}

/* 지금 보던 화면 위에 창으로 띄운다. tab 을 주면 그 칸을 펴서 연다 —
   '구독 관리' 를 누른 사람에게 일반 설정부터 보여 줄 이유가 없다. */
export function openSettings(tab) {
  css();
  const old = document.getElementById("ksModal");
  if (old) old.remove();

  const ov = el("div", "ks-ov");
  ov.id = "ksModal";
  const card = el("div", "ks-card");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");

  const top = el("div", "ks-top");
  top.appendChild(el("div", "ks-title", T("설정")));
  const x = el("button", "ks-x", "✕");
  x.type = "button";
  x.setAttribute("aria-label", T("닫기"));
  top.appendChild(x);

  const body = el("div");
  body.style.cssText = "flex:1;display:flex;min-height:0";
  card.appendChild(top); card.appendChild(body);
  ov.appendChild(card);
  document.body.appendChild(ov);

  const close = () => {
    if (typeof body._kosOff === "function") { try { body._kosOff(); } catch (_) {} }
    ov.remove();
    document.removeEventListener("keydown", onKey);
  };
  function onKey(e) { if (e.key === "Escape") close(); }
  x.addEventListener("click", close);
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  document.addEventListener("keydown", onKey);

  renderSettings(body, { onClose: close, tab });

  const stop = onAuthStateChanged(auth, u => { if (!u) { close(); stop(); } });
  return close;
}

window.KOSSettings = { open: openSettings, render: renderSettings };
