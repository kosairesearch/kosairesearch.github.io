/* ============================================================
   KOSAI — 구독 관리
   ------------------------------------------------------------
   화면에서 직접 할 수 있는 것: 플랜 변경 · 해지 · 해지 취소 · 환불 신청 ·
   결제 수단 변경 · 결제 내역 확인. 전화나 문의 접수 없이 끝나야 한다
   (요금제 페이지에 그렇게 고지했다).

   상태 판정과 금액 계산은 전부 서버가 한다. 이 파일은 보여주고 요청만 한다.
   ============================================================ */
import "./paywall.js";
import { app, isConfigured, SOCIAL } from "./firebase-config.js";
import { PLANS, TOSS, payReady, planOf, won, fmtDay } from "./payment-config.js";
import { getFirestore, collection, query, orderBy, limit, getDocs }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const root = document.getElementById("blApp");
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
const fns = isConfigured ? getFunctions(app, SOCIAL.functionsRegion || "asia-northeast3") : null;
const call = (n, d) => httpsCallable(fns, n)(d || {});

const T = {
  ko: {
    welcome: "구독이 시작되었습니다. 이제 모든 리포트를 전문으로 보실 수 있습니다.",
    cardOk: "결제 수단이 변경되었습니다. 다음 결제부터 새 카드로 청구됩니다.",
    cur: "현재 플랜", on: "이용 중", willEnd: "해지 예정", off: "만료됨",
    perMonth: "월", limitRow: "하루 열람 한도", nextRow: "다음 결제일", endRow: "이용 종료일",
    startRow: "구독 시작일", amountRow: "결제 금액", cards: "개",
    pay: "결제 수단", noCard: "등록된 카드가 없습니다.", changeCard: "카드 변경",
    upgrade: "PRO로 업그레이드", downgrade: "BASIC으로 변경",
    cancel: "구독 해지", resume: "해지 취소", refund: "환불 신청",
    hist: "결제 내역", histEmpty: "아직 결제 내역이 없습니다.",
    hDate: "일자", hDesc: "내용", hAmt: "금액", hSt: "상태",
    stPaid: "결제 완료", stRefund: "환불", stFail: "실패",
    noneT: "이용 중인 구독이 없습니다", noneD: "요금제를 선택하시면 리포트 전문을 바로 보실 수 있습니다.",
    dueT: "정기결제가 처리되지 않았습니다",
    dueD: "등록하신 카드로 결제가 이루어지지 않았습니다. 한도 초과이거나 카드가 정지·만료된 경우일 수 있습니다. 카드를 다시 등록하시면 이용이 이어집니다.",
    endedT: "구독이 종료되었습니다", endedD: "다시 시작하시려면 요금제를 선택해 주세요.",
    toPricing: "요금제 보기",
    needT: "로그인이 필요합니다", needD: "구독 정보를 보려면 로그인해 주세요.", login: "로그인",
    note: '해지하시면 이미 결제하신 이용 기간이 끝날 때까지는 그대로 이용하실 수 있습니다. 환불 기준은 <a href="pricing.html#faq">요금제 페이지</a>에서 확인하실 수 있습니다.',
    dlgCancelT: "구독을 해지하시겠습니까?",
    dlgCancelB: "{date}까지는 그대로 이용하실 수 있으며, 그 이후 결제되지 않습니다. 해지는 언제든지 취소하실 수 있습니다.",
    dlgUpT: "PRO로 업그레이드하시겠습니까?",
    dlgUpB: "즉시 PRO가 적용됩니다. 남은 기간에 해당하는 BASIC 금액을 차감하고 차액만 결제되며, 결제일은 그대로 유지됩니다.",
    dlgDownT: "BASIC으로 변경하시겠습니까?",
    dlgDownB: "{date}부터 BASIC이 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.",
    dlgRefundT: "환불을 신청하시겠습니까?",
    dlgRefundB: "환불이 완료되면 유료 플랜 이용 권한이 즉시 종료됩니다. 환불 금액은 열람 여부와 이용 일수에 따라 산정됩니다.",
    yes: "확인", no: "취소",
    okCancel: "해지 예약이 완료되었습니다.", okResume: "해지가 취소되었습니다.",
    okPlan: "플랜이 변경되었습니다.", okRefund: "환불 신청이 접수되었습니다.",
    fail: "처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
  },
  en: {
    welcome: "Your subscription is active. Every report is now open in full.",
    cardOk: "Your payment method has been updated. The new card is charged from the next cycle.",
    cur: "Current plan", on: "Active", willEnd: "Ends soon", off: "Expired",
    perMonth: "mo", limitRow: "Daily limit", nextRow: "Next charge", endRow: "Access until",
    startRow: "Started", amountRow: "Amount", cards: "",
    pay: "Payment method", noCard: "No card registered.", changeCard: "Change card",
    upgrade: "Upgrade to PRO", downgrade: "Switch to BASIC",
    cancel: "Cancel subscription", resume: "Keep subscription", refund: "Request refund",
    hist: "Payment history", histEmpty: "No payments yet.",
    hDate: "Date", hDesc: "Description", hAmt: "Amount", hSt: "Status",
    stPaid: "Paid", stRefund: "Refunded", stFail: "Failed",
    noneT: "No active subscription", noneD: "Pick a plan and every report opens in full right away.",
    dueT: "We could not process your renewal",
    dueD: "The card on file was declined — it may be over its limit, suspended, or expired. Register a card again and your access continues.",
    endedT: "Your subscription has ended", endedD: "Pick a plan to start again.",
    toPricing: "See plans",
    needT: "Sign in required", needD: "Please sign in to see your subscription.", login: "Sign in",
    note: 'If you cancel, you keep access until the period you have paid for ends. Refund terms are on the <a href="pricing.html#faq">pricing page</a>.',
    dlgCancelT: "Cancel your subscription?",
    dlgCancelB: "You keep access until {date}, and you will not be charged after that. You can undo this anytime.",
    dlgUpT: "Upgrade to PRO?",
    dlgUpB: "PRO applies immediately. The unused part of BASIC is credited and you pay only the difference; your billing date stays the same.",
    dlgDownT: "Switch to BASIC?",
    dlgDownB: "BASIC applies from {date}. You keep PRO until then.",
    dlgRefundT: "Request a refund?",
    dlgRefundB: "Your paid plan ends as soon as the refund is processed. The amount depends on whether you opened reports and how many days you used.",
    yes: "Confirm", no: "Cancel",
    okCancel: "Your subscription will end at the period end.", okResume: "Your subscription continues.",
    okPlan: "Your plan has been changed.", okRefund: "Your refund request has been received.",
    fail: "Something went wrong. Please try again shortly.",
  },
};
const t = () => (EN() ? T.en : T.ko);

/* 확인 대화상자 — 되돌리기 어려운 동작은 한 번 묻는다. */
function ask(title, body) {
  const k = t(), d = document.getElementById("dlg");
  document.getElementById("dlgT").textContent = title;
  document.getElementById("dlgB").innerHTML = `<p>${esc(body)}</p>`;
  document.getElementById("dlgYes").textContent = k.yes;
  document.getElementById("dlgNo").textContent = k.no;
  d.classList.add("open");
  return new Promise((res) => {
    const done = (v) => { d.classList.remove("open"); yes.onclick = null; no.onclick = null; res(v); };
    const yes = document.getElementById("dlgYes"), no = document.getElementById("dlgNo");
    yes.onclick = () => done(true);
    no.onclick = () => done(false);
    d.onclick = (e) => { if (e.target === d) done(false); };
  });
}

function empty(title, desc, actions) {
  root.innerHTML = `<div class="bl-empty glass"><h2>${esc(title)}</h2><p>${esc(desc)}</p>${actions || ""}</div>`;
}

function statusPill(sub, k) {
  if (sub.cancelAtPeriodEnd) return `<span class="pill warn">${esc(k.willEnd)}</span>`;
  return `<span class="pill on">${esc(k.on)}</span>`;
}

function view(st, payments) {
  const k = t(), sub = st.sub || {}, plan = planOf(sub.plan) || { name: String(sub.plan || "").toUpperCase(), price: 0, limit: 0 };
  const endDay = fmtDay(sub.currentPeriodEnd, EN());
  const card = sub.card || null;
  const other = sub.plan === "pro" ? PLANS.basic : PLANS.pro;

  const rows = [
    [k.amountRow, `${won(plan.price, EN())} / ${k.perMonth}`],
    [k.limitRow, `${plan.limit}${k.cards}`],
    [sub.cancelAtPeriodEnd ? k.endRow : k.nextRow, endDay],
    [k.startRow, fmtDay(sub.startedAt, EN())],
  ].filter((r) => r[1]);

  const hist = payments.length
    ? `<div class="hist-wrap"><table class="hist"><thead><tr>
         <th>${esc(k.hDate)}</th><th>${esc(k.hDesc)}</th><th>${esc(k.hAmt)}</th><th>${esc(k.hSt)}</th></tr></thead><tbody>`
      + payments.map((p) => {
          const s = p.status === "refunded" ? `<span class="st rf">${esc(k.stRefund)}</span>`
                  : p.status === "failed" ? `<span class="st rf">${esc(k.stFail)}</span>`
                  : `<span class="st ok">${esc(k.stPaid)}</span>`;
          const amt = (p.amount < 0 ? "-" : "") + won(Math.abs(p.amount || 0), EN());
          return `<tr><td>${esc(fmtDay(p.paidAt || p.createdAt, EN()))}</td><td>${esc(p.description || "")}</td><td>${esc(amt)}</td><td>${s}</td></tr>`;
        }).join("")
      + "</tbody></table></div>"
    : `<p class="bl-note">${esc(k.histEmpty)}</p>`;

  root.innerHTML = `
  <div class="bl">
    ${qp("welcome") || qp("card")
      ? `<div class="bl-card glass"><p style="margin:0;font:600 15px/1.6 var(--font-sans)">${esc(qp("card") ? k.cardOk : k.welcome)}</p></div>`
      : ""}

    <section class="bl-card glass">
      <div class="bl-top">
        <div class="bl-plan"><span class="nm">${esc(plan.name)}</span><span class="pr">${esc(won(plan.price, EN()))} / ${esc(k.perMonth)}</span></div>
        ${statusPill(sub, k)}
      </div>
      <ul class="bl-rows">${rows.map((r) => `<li><span>${esc(r[0])}</span><b>${esc(r[1])}</b></li>`).join("")}</ul>
      <div class="bl-acts">
        <button type="button" class="btn btn-soft" data-act="plan" data-to="${esc(other.id)}">
          ${esc(sub.plan === "pro" ? k.downgrade : k.upgrade)}</button>
        ${sub.cancelAtPeriodEnd
          ? `<button type="button" class="btn btn-primary" data-act="resume">${esc(k.resume)}</button>`
          : `<button type="button" class="btn btn-soft" data-act="cancel">${esc(k.cancel)}</button>`}
        <button type="button" class="btn btn-soft" data-act="refund">${esc(k.refund)}</button>
      </div>
      <p class="bl-msg" id="blMsg"></p>
      <p class="bl-note">${k.note}</p>
    </section>

    <section class="bl-card glass">
      <h2>${esc(k.pay)}</h2>
      <ul class="bl-rows" style="border-top:0;padding-top:0;margin-top:0">
        <li><span>${card ? esc(card.company || "") : esc(k.noCard)}</span>
            <b>${card && card.number ? esc(card.number) : ""}</b></li>
      </ul>
      <div class="bl-acts">
        <a class="btn btn-soft" href="checkout.html?plan=${esc(sub.plan || "basic")}&amp;method=1">${esc(k.changeCard)}</a>
      </div>
    </section>

    <section class="bl-card glass">
      <h2>${esc(k.hist)}</h2>
      ${hist}
    </section>
  </div>`;

  wire(st);
}

function wire(st) {
  const k = t(), msg = document.getElementById("blMsg");
  const sub = st.sub || {};
  const endDay = fmtDay(sub.currentPeriodEnd, EN());
  const show = (text, err) => { msg.className = "bl-msg" + (err ? " err" : ""); msg.textContent = text; };

  root.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const act = btn.dataset.act;
      let ok = false, fn = null, arg = null, done = "";
      if (act === "cancel") {
        ok = await ask(k.dlgCancelT, k.dlgCancelB.replace("{date}", endDay));
        fn = "cancelSubscription"; done = k.okCancel;
      } else if (act === "resume") {
        ok = true; fn = "resumeSubscription"; done = k.okResume;
      } else if (act === "refund") {
        ok = await ask(k.dlgRefundT, k.dlgRefundB);
        fn = "requestRefund"; done = k.okRefund;
      } else if (act === "plan") {
        const up = btn.dataset.to === "pro";
        ok = await ask(up ? k.dlgUpT : k.dlgDownT,
          up ? k.dlgUpB : k.dlgDownB.replace("{date}", endDay));
        fn = "changePlan"; arg = { plan: btn.dataset.to }; done = k.okPlan;
      }
      if (!ok) return;
      root.querySelectorAll("[data-act]").forEach((b) => { b.disabled = true; });
      show("");
      try {
        await call(fn, arg);
        show(done, false);
        // subscriptions 문서를 실시간으로 보고 있으므로 곧 화면이 새로 그려진다.
      } catch (e) {
        console.error("[billing]", fn, e);
        show(e.message || k.fail, true);
        root.querySelectorAll("[data-act]").forEach((b) => { b.disabled = false; });
      }
    });
  });
}

async function loadPayments(uid) {
  if (!isConfigured) return [];
  try {
    const db = getFirestore(app);
    const q = query(collection(db, "payments", uid, "items"), orderBy("createdAt", "desc"), limit(12));
    const snap = await getDocs(q);
    return snap.docs.map((d) => d.data());
  } catch (e) {
    console.warn("[billing] 결제 내역 조회 실패", e);
    return [];
  }
}

let repaint = null;
if (window.KOSi18n) window.KOSi18n.register(null, () => { if (repaint) repaint(); });

(async function main() {
  await window.KOSPaywall.ready;
  let payments = [];
  window.KOSPaywall.onChange(async (st) => {
    const k = t();
    repaint = null;
    if (!st.user) {
      empty(k.needT, k.needD,
        `<a class="btn btn-primary" href="Login.html?next=billing.html">${esc(k.login)}</a>`);
      return;
    }
    if (!st.sub) {
      empty(k.noneT, k.noneD, `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`);
      return;
    }
    // 구독 기록은 있는데 지금 유효하지 않은 경우. 그냥 '구독 없음'으로 보내면
    // 갱신 결제가 실패한 사람이 이유도 모르고 카드를 바꿀 길도 없어진다.
    if (!st.active) {
      const plan = st.sub.plan || "basic";
      if (st.sub.status === "past_due") {
        empty(k.dueT, k.dueD,
          `<a class="btn btn-primary" href="checkout.html?plan=${esc(plan)}&amp;method=1">${esc(k.changeCard)}</a>`);
      } else {
        empty(k.endedT, k.endedD, `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`);
      }
      return;
    }
    if (!payments.length) payments = await loadPayments(st.user.uid);
    repaint = () => view(st, payments);
    repaint();
  });
})();
