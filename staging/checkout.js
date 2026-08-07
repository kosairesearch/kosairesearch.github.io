/* ============================================================
   KOSAI — 결제(구독 시작)
   ------------------------------------------------------------
   흐름
     1) ?plan=basic|pro 확인 → 로그인 확인
     2) 카드 등록(토스페이먼츠 빌링 인증) → 결제창으로 이동
     3) 돌아오면 ?authKey&customerKey 를 서버로 넘겨 confirmBilling 호출
        서버가 빌링키를 발급하고 첫 결제를 승인한 뒤 subscriptions/{uid} 를 쓴다
     4) 구독 관리 페이지로 이동

   금액은 여기서 정하지 않는다. 클라이언트가 보낸 금액을 믿으면 9,900원짜리를
   100원에 파는 요청을 만들 수 있다. 서버가 plan 만 받아 자기 표에서 금액을 읽는다.
   ============================================================ */
import "./paywall.js";
import { app, auth, isConfigured, SOCIAL } from "./firebase-config.js";
import { PLANS, TOSS, payReady, planOf, won } from "./payment-config.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const app_ = document.getElementById("coApp");
/* i18n 엔진은 DOMContentLoaded 에서야 언어를 정하는데, 모듈 스크립트는 그보다
   먼저 실행된다. KOSi18n.lang 만 보면 항상 'ko' 로 읽혀 영어 모드에서 한국어가
   나온다 — 저장소를 먼저 본다. */
const EN = () => {
  try { const v = localStorage.getItem("kos-lang"); if (v) return v === "en"; } catch (e) {}
  return !!(window.KOSi18n && window.KOSi18n.lang === "en");
};
const qp = (k) => new URLSearchParams(location.search).get(k);
const esc = (x) => String(x == null ? "" : x)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const T = {
  ko: {
    step1: "주문 확인", step2: "결제 수단", step3: "약관 동의",
    card: "신용·체크카드", cardD: "국내에서 발급된 카드로 매달 자동 결제됩니다.",
    sumPlan: "플랜", sumCycle: "결제 주기", sumFirst: "첫 결제일", sumNext: "다음 결제일",
    monthly: "매월", today: "오늘", total: "결제 금액", vat: "부가가치세 포함",
    agreeAll: "아래 내용에 모두 동의합니다",
    agree1: '<a href="Terms.html" target="_blank" rel="noopener">이용약관</a>과 <a href="Privacy.html" target="_blank" rel="noopener">개인정보 처리방침</a>에 동의합니다. (필수)',
    agree2: "매월 같은 날짜에 등록하신 카드로 자동 결제되는 정기결제에 동의합니다. (필수)",
    agree3: "디지털 콘텐츠 특성상 리포트를 열람하시면 청약철회가 제한될 수 있음을 확인했습니다. (필수)",
    pay: "결제하고 시작하기",
    fine: '결제 후 7일 이내에 리포트를 열람하지 않으셨다면 전액 환불됩니다. 자세한 기준은 <a href="pricing.html#faq">환불 기준</a>을 확인해 주세요. 구독은 <a href="billing.html">구독 관리</a>에서 언제든지 해지하실 수 있습니다.',
    loading: "불러오는 중…", paying: "결제창을 여는 중…", confirming: "결제를 확인하는 중…",
    needLogin: "로그인이 필요합니다", needLoginD: "구독은 계정에 연결됩니다. 로그인 후 계속 진행해 주세요.",
    login: "로그인", toPricing: "요금제 보기",
    already: "이미 이용 중입니다", alreadyD: "현재 {plan} 플랜을 이용하고 계십니다. 플랜 변경과 해지는 구독 관리에서 하실 수 있습니다.",
    toBilling: "구독 관리로 이동",
    notReady: "결제 준비 중입니다", notReadyD: "결제 연동 설정이 아직 완료되지 않았습니다. 잠시 후 다시 시도해 주세요.",
    badPlan: "요금제를 찾을 수 없습니다", badPlanD: "요금제 페이지에서 다시 선택해 주세요.",
    failTitle: "결제가 완료되지 않았습니다",
    errAgree: "필수 항목에 모두 동의해 주세요.",
    errOpen: "결제창을 열지 못했습니다. 잠시 후 다시 시도해 주세요.",
    errConfirm: "결제 확인에 실패했습니다. 카드사 승인 내역을 확인하신 뒤 다시 시도해 주세요.",
    done: "구독이 시작되었습니다",
  },
  en: {
    step1: "Order", step2: "Payment method", step3: "Agreements",
    card: "Credit or debit card", cardD: "Billed automatically each month to the card you register.",
    sumPlan: "Plan", sumCycle: "Billing cycle", sumFirst: "First charge", sumNext: "Next charge",
    monthly: "Monthly", today: "Today", total: "Amount due", vat: "VAT included",
    agreeAll: "I agree to everything below",
    agree1: 'I agree to the <a href="Terms.html" target="_blank" rel="noopener">Terms of Service</a> and <a href="Privacy.html" target="_blank" rel="noopener">Privacy Policy</a>. (required)',
    agree2: "I agree to recurring monthly charges to the card I register. (required)",
    agree3: "I understand that opening a report may limit my right to withdraw, as this is digital content. (required)",
    pay: "Pay and start",
    fine: 'If you have not opened a report within 7 days of payment, you get a full refund. See <a href="pricing.html#faq">refund terms</a> for details. You can cancel anytime on the <a href="billing.html">subscription page</a>.',
    loading: "Loading…", paying: "Opening the payment window…", confirming: "Confirming your payment…",
    needLogin: "Sign in required", needLoginD: "Subscriptions are tied to your account. Please sign in to continue.",
    login: "Sign in", toPricing: "See plans",
    already: "You are already subscribed", alreadyD: "You are on the {plan} plan. You can change or cancel it on the subscription page.",
    toBilling: "Go to subscription",
    notReady: "Payments are not live yet", notReadyD: "Payment integration is not finished. Please try again shortly.",
    badPlan: "Plan not found", badPlanD: "Please pick a plan again from the pricing page.",
    failTitle: "Payment was not completed",
    errAgree: "Please agree to all required items.",
    errOpen: "Could not open the payment window. Please try again shortly.",
    errConfirm: "We could not confirm the payment. Check your card statement and try again.",
    done: "Your subscription has started",
  },
};
const t = () => (EN() ? T.en : T.ko);

function state(title, desc, actions) {
  app_.innerHTML = `<div class="co-state glass"><h2>${esc(title)}</h2><p>${esc(desc)}</p>${actions || ""}</div>`;
}
function busy(msg) {
  app_.innerHTML = `<div class="co-state glass"><p><span class="spin"></span>${esc(msg)}</p></div>`;
}
function nextMonth() {
  const d = new Date();
  const day = d.getDate();
  d.setMonth(d.getMonth() + 1);
  if (d.getDate() !== day) d.setDate(0);   // 31일 → 다음 달 말일
  return d;
}
function dayText(d) {
  const M = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return EN() ? `${M[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
              : `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}

function form(plan) {
  const k = t();
  const nx = nextMonth();
  return `
  <div class="co">
    <section class="co-card glass">
      <div class="co-step"><span class="n">1</span><h3>${esc(k.step2)}</h3></div>
      <div class="pm">
        <label>
          <input type="radio" name="pm" value="card" checked />
          <span class="card"><span><span class="t">${esc(k.card)}</span><span class="d">${esc(k.cardD)}</span></span></span>
        </label>
      </div>

      <div class="co-step"><span class="n">2</span><h3>${esc(k.step3)}</h3></div>
      <div class="agree">
        <label class="all"><input type="checkbox" id="agAll" /><span>${esc(k.agreeAll)}</span></label>
        <label><input type="checkbox" class="ag" /><span>${k.agree1}</span></label>
        <label><input type="checkbox" class="ag" /><span>${esc(k.agree2)}</span></label>
        <label><input type="checkbox" class="ag" /><span>${esc(k.agree3)}</span></label>
      </div>

      <button type="button" class="btn btn-primary co-btn" id="payBtn">${esc(k.pay)}</button>
      <p class="co-msg" id="coMsg"></p>
      <p class="co-fine">${k.fine}</p>
    </section>

    <aside class="sum glass">
      <span class="plan-badge">${esc(plan.name)}</span>
      <div class="amt">${esc(won(plan.price, EN()))}<small> / ${EN() ? "mo" : "월"}</small></div>
      <div class="cyc">${esc(k.vat)}</div>
      <ul>
        <li><span>${esc(k.sumPlan)}</span><b>${esc(plan.name)}</b></li>
        <li><span>${esc(k.sumCycle)}</span><b>${esc(k.monthly)}</b></li>
        <li><span>${esc(k.sumFirst)}</span><b>${esc(k.today)}</b></li>
        <li><span>${esc(k.sumNext)}</span><b>${esc(dayText(nx))}</b></li>
      </ul>
      <div class="total"><span class="k">${esc(k.total)}</span><span class="v">${esc(won(plan.price, EN()))}</span></div>
    </aside>
  </div>`;
}

function wireForm(plan, user) {
  const k = t();
  const all = document.getElementById("agAll");
  const boxes = [...document.querySelectorAll(".agree .ag")];
  const btn = document.getElementById("payBtn");
  const msg = document.getElementById("coMsg");
  const sync = () => { all.checked = boxes.every((b) => b.checked); };
  all.addEventListener("change", () => { boxes.forEach((b) => { b.checked = all.checked; }); });
  boxes.forEach((b) => b.addEventListener("change", sync));

  btn.addEventListener("click", async () => {
    msg.className = "co-msg";
    if (!boxes.every((b) => b.checked)) { msg.className = "co-msg err"; msg.textContent = k.errAgree; return; }
    btn.disabled = true;
    msg.innerHTML = `<span class="spin"></span>${esc(k.paying)}`;
    try {
      const { loadTossPayments } = await import("https://js.tosspayments.com/v2/standard");
      const toss = await loadTossPayments(TOSS.clientKey);
      const payment = toss.payment({ customerKey: user.uid });
      const back = new URL(TOSS.successPath, location.href);
      back.searchParams.set("plan", plan.id);
      const fail = new URL(TOSS.failPath, location.href);
      fail.searchParams.set("plan", plan.id);
      await payment.requestBillingAuth({
        method: "CARD",
        successUrl: back.toString(),
        failUrl: fail.toString(),
        customerEmail: user.email || undefined,
        customerName: user.displayName || undefined,
      });
    } catch (e) {
      console.error("[checkout]", e);
      btn.disabled = false;
      msg.className = "co-msg err";
      msg.textContent = k.errOpen;
    }
  });
}

/* 결제창에서 돌아왔을 때 — 빌링키 발급과 첫 결제는 서버가 한다. */
async function confirm(authKey, customerKey, planId) {
  const k = t();
  busy(k.confirming);
  try {
    const fns = getFunctions(app, SOCIAL.functionsRegion || "asia-northeast3");
    await httpsCallable(fns, "confirmBilling")({ authKey, customerKey, plan: planId });
    location.replace("billing.html?welcome=1");
  } catch (e) {
    console.error("[checkout] confirmBilling", e);
    state(k.failTitle, e.message || k.errConfirm,
      `<a class="btn btn-primary" href="checkout.html?plan=${encodeURIComponent(planId)}">${esc(k.pay)}</a>`);
  }
}

/* KO ⇄ EN 토글 시 다시 그린다. 이 영역은 data-i18n-skip 이라 엔진이 손대지 않는다. */
let repaint = null;
if (window.KOSi18n) window.KOSi18n.register(null, () => { if (repaint) repaint(); });

(async function main() {
  const k = t();
  const planId = String(qp("plan") || "").toLowerCase();
  const plan = planOf(planId);
  if (!plan) { state(k.badPlan, k.badPlanD, `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`); return; }

  // 결제창 실패로 돌아온 경우
  const failCode = qp("code");
  if (failCode) {
    state(k.failTitle, qp("message") || k.errOpen,
      `<a class="btn btn-primary" href="checkout.html?plan=${encodeURIComponent(plan.id)}">${esc(k.pay)}</a>`);
    return;
  }

  busy(k.loading);
  const st = await window.KOSPaywall.ready;

  const authKey = qp("authKey"), customerKey = qp("customerKey");
  if (authKey && customerKey) { await confirm(authKey, customerKey, plan.id); return; }

  if (!isConfigured) { state(k.notReady, k.notReadyD, `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`); return; }
  if (!st.user) {
    state(k.needLogin, k.needLoginD,
      `<a class="btn btn-primary" href="Login.html?next=${encodeURIComponent("checkout.html?plan=" + plan.id)}">${esc(k.login)}</a>`);
    return;
  }
  if (st.active) {
    const cur = PLANS[st.plan] ? PLANS[st.plan].name : String(st.plan || "").toUpperCase();
    state(k.already, k.alreadyD.replace("{plan}", cur),
      `<a class="btn btn-primary" href="billing.html">${esc(k.toBilling)}</a>`);
    return;
  }
  if (!payReady) { state(k.notReady, k.notReadyD, `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`); return; }

  repaint = () => { app_.innerHTML = form(plan); wireForm(plan, st.user); };
  repaint();
})();
