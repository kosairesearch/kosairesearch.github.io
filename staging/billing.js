/* ============================================================
   KOSAI — 구독 관리
   ------------------------------------------------------------
   화면에서 직접 할 수 있는 것: 플랜 변경 · 해지 · 해지 취소 · 환불 신청 ·
   결제 수단 변경 · 결제 내역 확인. 전화나 문의 접수 없이 끝나야 한다
   (요금제 페이지에 그렇게 고지했다).

   상태 판정과 금액 계산은 전부 서버가 한다. 이 파일은 보여주고 요청만 한다.
   ============================================================ */
import "./paywall.js";
import { call } from "./subscription-api.js";
import { app, isConfigured, SOCIAL } from "./firebase-config.js";
import { MIN_CHARGE, PLANS, TOSS, payReady, planOf, upgradeDiff, won, fmtDay } from "./payment-config.js";
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

const T = {
  ko: {
    cardOk: "결제 수단이 변경되었습니다. 다음 결제일부터 새 카드로 청구됩니다.",
    cur: "현재 플랜", on: "이용 중", willEnd: "해지 예정", off: "만료됨",
    perMonth: "월", limitRow: "하루 열람 한도", nextRow: "다음 결제일", endRow: "이용 종료일",
    startRow: "구독 시작일", amountRow: "결제 금액", cards: "개",
    pendRow: "예정된 변경", pendVal: "{d}부터 {p}",
    usedRow: "오늘 남은 열람", usedVal: "{r}개 / {l}개",
    undoPlan: "변경 취소",
    dlgUndoT: "플랜 변경을 취소하시겠습니까?",
    dlgUndoB: "{date} 이후에도 {p} 플랜이 그대로 유지됩니다.",
    alsoResume: " 예약해 두신 해지는 함께 취소됩니다.",
    alsoDropPlan: " 예약해 두신 {p} 플랜 변경은 함께 취소됩니다.",
    pay: "결제 수단", noCard: "등록된 카드가 없습니다.", changeCard: "카드 변경",
    upgrade: "PRO로 업그레이드", downgrade: "BASIC으로 변경",
    cancel: "구독 해지", resume: "해지 취소", refund: "환불 신청",
    hist: "결제 내역", histEmpty: "아직 결제 내역이 없습니다.",
    hDate: "일자", hDesc: "내용", hAmt: "금액", hSt: "상태",
    stPaid: "결제 완료", stRefund: "환불", stFail: "실패",
    pSub: "{p} 월 구독", pUp: "{p} 업그레이드 차액", pFail: "정기결제 실패",
    pRefund: "환불", pWhy: { withdraw: "청약철회", used: "이용분 차감", left: "잔여 기간" },
    freeName: "무료", freePill: "무료", freeLimit: "무료 구간까지",
    freeNote: '분석·전망·리스크 등 유료 구간은 <a href="pricing.html">멤버십</a>에서 보실 수 있습니다.',
    duePill: "결제 실패",
    dueD: "등록하신 카드로 결제가 승인되지 않았습니다. 한도 초과이거나 카드가 정지·만료된 경우일 수 있습니다. 카드를 다시 등록하시면 이용이 재개됩니다.",
    toPricing: "멤버십 보기",
    needT: "로그인이 필요합니다", needD: "구독 정보를 보려면 로그인해 주세요.", login: "로그인",
    note: '해지하시면 이미 결제하신 이용 기간이 끝날 때까지는 그대로 이용하실 수 있습니다. 환불 기준은 <a href="pricing.html#faq">멤버십 페이지</a>에서 확인하실 수 있습니다.',
    dlgCancelT: "구독을 해지하시겠습니까?",
    dlgCancelB: "{date}까지는 그대로 이용하실 수 있으며, 그 이후 결제되지 않습니다. 해지는 언제든지 취소하실 수 있습니다.",
    dlgUpT: "PRO로 업그레이드하시겠습니까?",
    dlgUpB: "즉시 PRO가 적용됩니다. 남은 기간에 해당하는 BASIC 금액을 차감한 차액 {a}이 등록하신 카드로 지금 결제되며, 결제일은 그대로 유지됩니다.",
    dlgUpB0: "즉시 PRO가 적용됩니다. 이번 결제 주기가 거의 끝나 지금 청구되는 금액은 없으며, 다음 결제일부터 PRO 요금으로 청구됩니다.",
    dlgDownT: "BASIC으로 변경하시겠습니까?",
    dlgDownB: "{date}부터 BASIC이 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.",
    dlgRefundT: "환불을 신청하시겠습니까?",
    dlgRefundB: "환불이 완료되면 유료 플랜 이용 권한이 즉시 종료됩니다. 환불 금액은 열람 여부와 이용 일수에 따라 산정됩니다.",
    yes: "확인", no: "취소",
    okCancel: "해지 예약이 완료되었습니다.", okResume: "해지가 취소되었습니다.",
    okUp: "{p} 플랜이 바로 적용되었습니다. 차액 {a}이 결제되었습니다.",
    okUp0: "{p} 플랜이 바로 적용되었습니다. 지금 청구된 금액은 없습니다.",
    okDown: "{d}부터 {p} 플랜으로 변경됩니다.",
    okUndo: "플랜 변경이 취소되었습니다.", okRefund: "환불 신청이 접수되었습니다.",
    fail: "처리에 실패했습니다. 잠시 후 다시 시도해 주세요.",
    surveyQ: "사유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)",
    surveyMore: "자세한 의견 (선택)",
    cancelWhy: ["가격이 부담됩니다", "원하는 종목·정보가 부족합니다",
                "리포트 내용이 기대와 다릅니다", "자주 이용하지 않습니다",
                "일시적으로 이용을 중단합니다", "기타"],
    refundWhy: ["실수로 결제했습니다", "서비스가 기대와 다릅니다",
                "오류·장애로 정상적으로 이용하지 못했습니다", "중복으로 결제되었습니다", "기타"],
  },
  en: {
    cardOk: "Your payment method has been updated. The new card will be charged from the next billing date.",
    cur: "Current plan", on: "Active", willEnd: "Ends soon", off: "Expired",
    perMonth: "mo", limitRow: "Daily limit", nextRow: "Next charge", endRow: "Access until",
    startRow: "Started", amountRow: "Amount", cards: "",
    pendRow: "Scheduled change", pendVal: "{p} from {d}",
    usedRow: "Left today", usedVal: "{r} of {l}",
    undoPlan: "Undo change",
    dlgUndoT: "Undo the scheduled change?",
    dlgUndoB: "You stay on {p} after {date}.",
    alsoResume: " Your scheduled cancellation will be undone.",
    alsoDropPlan: " Your scheduled change to {p} will be dropped.",
    pay: "Payment method", noCard: "No card registered.", changeCard: "Change card",
    upgrade: "Upgrade to PRO", downgrade: "Switch to BASIC",
    cancel: "Cancel subscription", resume: "Keep subscription", refund: "Request refund",
    hist: "Payment history", histEmpty: "No payments yet.",
    hDate: "Date", hDesc: "Description", hAmt: "Amount", hSt: "Status",
    stPaid: "Paid", stRefund: "Refunded", stFail: "Failed",
    pSub: "{p} monthly", pUp: "{p} upgrade difference", pFail: "Renewal failed",
    pRefund: "Refund", pWhy: { withdraw: "withdrawal", used: "usage deducted", left: "remaining days" },
    freeName: "Free", freePill: "Free", freeLimit: "Free sections only",
    freeNote: 'The analysis, outlook, and risk sections come with a <a href="pricing.html">plan</a>.',
    duePill: "Payment failed",
    dueD: "The card on file was declined — it may be over its limit, suspended, or expired. Register a card again to restore access.",
    toPricing: "See plans",
    needT: "Sign in required", needD: "Please sign in to see your subscription.", login: "Sign in",
    note: 'If you cancel, you keep access until the period you have paid for ends. Refund terms are on the <a href="pricing.html#faq">pricing page</a>.',
    dlgCancelT: "Cancel your subscription?",
    dlgCancelB: "You keep access until {date}, and you will not be charged after that. You can undo this anytime.",
    dlgUpT: "Upgrade to PRO?",
    dlgUpB: "PRO applies immediately. The unused part of BASIC is credited and the difference, {a}, is charged to your registered card now; your billing date stays the same.",
    dlgUpB0: "PRO applies immediately. This billing period is nearly over, so nothing is charged now — PRO pricing starts from your next billing date.",
    dlgDownT: "Switch to BASIC?",
    dlgDownB: "BASIC applies from {date}. You keep PRO until then.",
    dlgRefundT: "Request a refund?",
    dlgRefundB: "Your paid plan ends as soon as the refund is processed. The amount depends on whether you opened reports and how many days you used.",
    yes: "Confirm", no: "Cancel",
    okCancel: "Your subscription will end at the period end.", okResume: "Your subscription continues.",
    okUp: "You are on {p} as of now. {a} has been charged.",
    okUp0: "You are on {p} as of now. Nothing was charged.",
    okDown: "You move to {p} on {d}.",
    okUndo: "The scheduled change has been cancelled.", okRefund: "Your refund request has been received.",
    fail: "Something went wrong. Please try again shortly.",
    surveyQ: "Telling us why helps us improve (select all that apply)",
    surveyMore: "Tell us more (optional)",
    cancelWhy: ["Too expensive", "Missing stocks or information I want",
                "Reports were not what I expected", "I don't use it often",
                "Pausing for now", "Other"],
    refundWhy: ["I paid by mistake", "The service was not what I expected",
                "I could not use it because of a fault or outage", "I was charged twice", "Other"],
  },
};
const t = () => (EN() ? T.en : T.ko);

/* 확인 대화상자 — 되돌리기 어려운 동작은 한 번 묻는다.
   why 를 주면 사유를 함께 묻는다(해지·환불). 답하지 않아도 진행된다 —
   환불은 법으로 보장된 권리이므로 설문으로 막아서는 안 된다.
   돌려주는 값: 취소면 false, 확인이면 { reason, detail }. */
function ask(title, body, why) {
  const k = t(), d = document.getElementById("dlg");
  document.getElementById("dlgT").textContent = title;
  document.getElementById("dlgB").innerHTML = `<p>${esc(body)}</p>` + (why
    ? `<div class="dlg-q">${esc(k.surveyQ)}</div>
       <div class="dlg-reasons">${k[why].map((r, i) =>
         `<label class="dlg-r"><input type="checkbox" name="dlgWhy" value="${i}"><span>${esc(r)}</span></label>`).join("")}</div>
       <textarea class="dlg-detail" rows="2" placeholder="${esc(k.surveyMore)}"></textarea>`
    : "");
  document.getElementById("dlgYes").textContent = k.yes;
  document.getElementById("dlgNo").textContent = k.no;
  d.classList.add("open");
  return new Promise((res) => {
    const pick = () => {
      if (!why) return {};
      /* 사유는 늘 한국어로 보낸다. 화면이 영어여도 접수함은 하나라, 언어별로
         다른 문구가 섞이면 모아서 세어 볼 수가 없다. */
      const reason = [...d.querySelectorAll("input[name=dlgWhy]:checked")]
        .map((c) => T.ko[why][+c.value]).filter(Boolean).join(", ");
      const el = d.querySelector(".dlg-detail");
      return { reason, detail: el ? el.value.trim() : "" };
    };
    const yes = document.getElementById("dlgYes"), no = document.getElementById("dlgNo");
    const done = (v) => { d.classList.remove("open"); yes.onclick = null; no.onclick = null; res(v); };
    yes.onclick = () => done(pick());
    no.onclick = () => done(false);
    d.onclick = (e) => { if (e.target === d) done(false); };
  });
}

/* 로그인 전 화면. 구독 상태와 무관하게 여기서 끝난다. */
function empty(title, desc, actions) {
  root.innerHTML = `<div class="bl"><div class="bl-empty glass"><h2>${esc(title)}</h2><p>${esc(desc)}</p>${actions || ""}</div></div>`;
}

/* 화면은 하나다. 구독이 있든 없든 같은 카드 세 장 — 플랜 · 결제 수단 · 결제 내역.
   상태마다 다른 화면을 그리면 '구독을 안 하면 볼 게 없는 페이지'가 된다. */
/* 결제 내역. 구독이 끝났어도 본인 결제 기록은 볼 수 있어야 한다 —
   전자상거래법상 우리가 5년간 보관하는 기록이기도 하다. */
/* 오늘 몇 개 남았는지. 서버만 아는 값이라(report_reads 는 클라이언트 읽기 차단)
   getUsage 로 받아 둔다. 한도에 부딪히기 전에는 알 길이 없었다. */
let usage = null;

/* 결제 한 줄의 설명. 저장된 건 종류(kind)뿐이고 문구는 여기서 만든다 —
   한국어 문장으로 굳혀 저장하면 영어 화면에서 번역할 방법이 없다.
   kind 가 없는 옛 기록은 저장돼 있던 description 을 그대로 쓴다. */
function payLabel(p) {
  const k = t();
  const name = (planOf(p.plan) || {}).name || String(p.plan || "").toUpperCase();
  if (p.kind === "subscription") return k.pSub.replace("{p}", name);
  if (p.kind === "upgrade") return k.pUp.replace("{p}", name);
  if (p.kind === "failed") return k.pFail;
  if (p.kind === "refund") {
    const why = k.pWhy[p.why];
    return why ? `${k.pRefund} · ${why}` : k.pRefund;
  }
  return p.description || "";
}

function histSection(payments) {
  const k = t();
  const body = payments.length
    ? `<div class="hist-wrap"><table class="hist"><thead><tr>
         <th>${esc(k.hDate)}</th><th>${esc(k.hDesc)}</th><th>${esc(k.hAmt)}</th><th>${esc(k.hSt)}</th></tr></thead><tbody>`
      + payments.map((p) => {
          const s = p.status === "refunded" ? `<span class="st rf">${esc(k.stRefund)}</span>`
                  : p.status === "failed" ? `<span class="st rf">${esc(k.stFail)}</span>`
                  : `<span class="st ok">${esc(k.stPaid)}</span>`;
          const amt = (p.amount < 0 ? "-" : "") + won(Math.abs(p.amount || 0), EN());
          return `<tr><td>${esc(fmtDay(p.paidAt || p.createdAt, EN()))}</td><td>${esc(payLabel(p))}</td><td>${esc(amt)}</td><td>${s}</td></tr>`;
        }).join("")
      + "</tbody></table></div>"
    : `<p class="bl-note">${esc(k.histEmpty)}</p>`;
  return `<section class="bl-card glass"><h2>${esc(k.hist)}</h2>${body}</section>`;
}

/* 주소에 붙은 표시(?card=1)로 한 번만 띄우는 안내. 읽자마자 주소에서 지운다 —
   안 지우면 새로고침할 때마다, 심지어 구독이 끝난 뒤에도 계속 뜬다.
   '구독이 시작되었습니다'가 무료 플랜 화면에 떠 있던 게 그 때문이었다. */
let flagOnce = null;
(function readFlag() {
  if (qp("card")) flagOnce = "card";
  // welcome 은 더 이상 쓰지 않는다. 예전 주소가 남아 있으면 지워만 둔다.
  if (flagOnce || qp("welcome")) {
    try {
      const u = new URL(location.href);
      u.searchParams.delete("card");
      u.searchParams.delete("welcome");
      history.replaceState(null, "", u.pathname + (u.search || "") + u.hash);
    } catch (e) {}
  }
})();

function view(st, payments) {
  const k = t();
  // 결제 수단 변경 안내는 구독이 살아 있을 때만 뜻이 있다.
  const banner = flagOnce === "card" && (st.active || (st.sub && st.sub.status === "past_due"))
    ? k.cardOk : null;
  const sub = st.sub || {};
  const active = !!st.active;
  const due = !active && sub.status === "past_due";
  const endDay = fmtDay(sub.currentPeriodEnd, EN());

  const paid = planOf(sub.plan);
  const plan = active || due
    ? (paid || { name: String(sub.plan || "").toUpperCase(), price: 0, limit: 0 })
    : { name: k.freeName, price: 0, limit: 0 };
  const other = sub.plan === "pro" ? PLANS.basic : PLANS.pro;

  /* 다운그레이드는 다음 결제일부터라 지금 화면에는 아무것도 안 바뀐다.
     예약된 걸 어디에도 안 적어 두면, 확인을 눌러도 아무 일도 안 일어난 것처럼 보인다. */
  const pend = active && sub.pendingPlan && sub.pendingPlan !== sub.plan ? planOf(sub.pendingPlan) : null;
  const left = active && usage && usage.limit ? Math.max(0, usage.limit - (usage.used || 0)) : null;

  const pill = due ? `<span class="pill warn">${esc(k.duePill)}</span>`
    : !active ? `<span class="pill">${esc(k.freePill)}</span>`
    : sub.cancelAtPeriodEnd ? `<span class="pill warn">${esc(k.willEnd)}</span>`
    : `<span class="pill on">${esc(k.on)}</span>`;

  let rows;
  if (active) {
    rows = [
      [k.amountRow, `${won(plan.price, EN())} / ${k.perMonth}`],
      [k.limitRow, `${plan.limit}${k.cards}`],
      left == null ? null : [k.usedRow, k.usedVal.replace("{r}", left).replace("{l}", usage.limit)],
      [sub.cancelAtPeriodEnd ? k.endRow : k.nextRow, endDay],
      pend ? [k.pendRow, k.pendVal.replace("{d}", endDay).replace("{p}", pend.name)] : null,
      [k.startRow, fmtDay(sub.startedAt, EN())],
    ];
  } else if (due) {
    rows = [
      [k.amountRow, `${won(plan.price, EN())} / ${k.perMonth}`],
      [k.limitRow, `${plan.limit}${k.cards}`],
      [k.endRow, endDay],
      [k.startRow, fmtDay(sub.startedAt, EN())],
    ];
  } else {
    /* 무료 — 끝나는 날이 없다. 예전 구독이 끝난 날짜를 여기에 '이용 종료일'로
       적어 두니, 머리에는 '무료'라고 쓰여 있는데 바로 아래에 종료일이 붙어
       무료 이용이 그날 끊기는 것처럼 읽혔다. 지난 구독이 언제 끝났는지는
       아래 결제 내역이 이미 보여 준다. */
    rows = [
      [k.amountRow, won(0, EN())],
      [k.limitRow, k.freeLimit],
    ];
  }
  rows = rows.filter((r) => r && r[1]);

  let acts, note;
  if (active) {
    acts = `<button type="button" class="btn btn-soft" data-act="plan" data-to="${esc(pend ? sub.plan : other.id)}">
          ${esc(pend ? k.undoPlan : sub.plan === "pro" ? k.downgrade : k.upgrade)}</button>
        ${sub.cancelAtPeriodEnd
          ? `<button type="button" class="btn btn-primary" data-act="resume">${esc(k.resume)}</button>`
          : `<button type="button" class="btn btn-soft" data-act="cancel">${esc(k.cancel)}</button>`}
        <button type="button" class="btn btn-soft" data-act="refund">${esc(k.refund)}</button>`;
    note = k.note;
  } else if (due) {
    acts = `<a class="btn btn-primary" href="checkout.html?plan=${esc(sub.plan || "basic")}&amp;method=1">${esc(k.changeCard)}</a>`;
    note = k.dueD;
  } else {
    acts = `<a class="btn btn-primary" href="pricing.html">${esc(k.toPricing)}</a>`;
    note = k.freeNote;
  }

  const card = sub.card || null;
  const showCard = active || due;

  root.innerHTML = `
  <div class="bl">
    ${banner ? `<div class="bl-card glass"><p style="margin:0;font:600 15px/1.6 var(--font-sans)">${esc(banner)}</p></div>` : ""}

    <section class="bl-card glass">
      <div class="bl-top">
        <!-- 금액은 아래 '결제 금액' 줄에 있다. 같은 값을 두 번 쓰지 않는다. -->
        <div class="bl-plan"><span class="nm">${esc(plan.name)}</span></div>
        ${pill}
      </div>
      <ul class="bl-rows">${rows.map((r) => `<li><span>${esc(r[0])}</span><b>${esc(r[1])}</b></li>`).join("")}</ul>
      <div class="bl-acts">${acts}</div>
      <p class="bl-msg" id="blMsg"></p>
      <p class="bl-note">${note}</p>
    </section>

    <section class="bl-card glass">
      <h2>${esc(k.pay)}</h2>
      <ul class="bl-rows" style="border-top:0;padding-top:0;margin-top:0">
        <li><span>${showCard && card ? esc(card.company || "") : esc(k.noCard)}</span>
            <b>${showCard && card && card.number ? esc(card.number) : ""}</b></li>
      </ul>
      ${showCard ? `<div class="bl-acts">
        <a class="btn btn-soft" href="checkout.html?plan=${esc(sub.plan || "basic")}&amp;method=1">${esc(k.changeCard)}</a>
      </div>` : ""}
    </section>

    ${histSection(payments)}
  </div>`;

  wire(st);
}

/* 처리 결과 문구. 화면 밖에 들고 있어야 한다 — 구독 문서가 바뀌면 화면이 통째로
   다시 그려지는데, 그리기 전에 써 둔 글자는 떨어져 나간 옛 DOM 에 남는다.
   그래서 확인을 눌러도 아무 말도 안 뜨는 것처럼 보였다. */
let flash = null;

/* 해지·환불 사유를 접수함으로 보낸다(회원 탈퇴와 같은 경로).
   최선 노력이다 — 전송이 실패해도 해지·환불은 이미 끝났고, 사용자에게
   '사유 전송 실패'를 알릴 이유가 없다. 기다리지도 않는다. */
function sendReason(category, ans, user) {
  const message = [ans.reason && "사유: " + ans.reason, ans.detail].filter(Boolean).join("\n");
  if (!message) return;                                   // 아무것도 안 적었으면 보내지 않는다
  call("submitForm", { kind: "feedback", category, message,
                       email: (user && user.email) || "", page: "구독 관리" })
    .catch((e) => console.warn("[billing] 사유 전송 실패", e));
}

function wire(st) {
  const k = t(), msg = document.getElementById("blMsg");
  const sub = st.sub || {};
  const endDay = fmtDay(sub.currentPeriodEnd, EN());
  const show = (text, err) => { msg.className = "bl-msg" + (err ? " err" : ""); msg.textContent = text; };
  if (flash) show(flash.text, flash.err);

  root.querySelectorAll("[data-act]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const act = btn.dataset.act;
      flash = null;
      let ok = false, fn = null, arg = null, done = "", upTo = null;
      /* 해지 예약과 플랜 변경 예약은 함께 둘 수 없다 — 서버가 갱신할 때 해지를
         먼저 보고 끝내므로, 둘 다 걸어 두면 변경은 조용히 사라진다. 한쪽을
         고르면 다른 쪽이 풀린다는 걸 누르기 전에 말해 준다. */
      const pending = sub.pendingPlan && sub.pendingPlan !== sub.plan ? planOf(sub.pendingPlan) : null;
      let survey = null;
      if (act === "cancel") {
        ok = await ask(k.dlgCancelT, k.dlgCancelB.replace("{date}", endDay)
          + (pending ? k.alsoDropPlan.replace("{p}", pending.name) : ""), "cancelWhy");
        fn = "cancelSubscription"; done = k.okCancel; survey = "구독 해지";
      } else if (act === "resume") {
        ok = true; fn = "resumeSubscription"; done = k.okResume;
      } else if (act === "refund") {
        ok = await ask(k.dlgRefundT, k.dlgRefundB, "refundWhy");
        fn = "requestRefund"; done = k.okRefund; survey = "환불 신청";
      } else if (act === "plan") {
        const to = planOf(btn.dataset.to) || {};
        const undo = btn.dataset.to === sub.plan;
        const up = !undo && (to.price || 0) > (planOf(sub.plan) || {}).price;
        const more = sub.cancelAtPeriodEnd ? k.alsoResume : "";
        if (undo) {
          ok = await ask(k.dlgUndoT, k.dlgUndoB.replace("{date}", endDay).replace("{p}", to.name || "") + more);
          done = k.okUndo;
        } else if (up) {
          /* 얼마가 청구되는지 보여 주고 묻는다. 금액 없이 확인을 받으면
             카드에 얼마가 빠져나갈지 모르는 채로 누르게 된다. */
          const diff = upgradeDiff(sub, btn.dataset.to);
          ok = await ask(k.dlgUpT,
            (diff >= MIN_CHARGE ? k.dlgUpB.replace("{a}", won(diff, EN())) : k.dlgUpB0) + more);
          done = null;                    // 실제 청구액은 서버가 알려 준다
          upTo = to.name || "";
        } else {
          ok = await ask(k.dlgDownT, k.dlgDownB.replace("{date}", endDay) + more);
          done = k.okDown.replace("{d}", endDay).replace("{p}", to.name || "");
        }
        fn = "changePlan"; arg = { plan: btn.dataset.to };
      }
      if (!ok) return;
      root.querySelectorAll("[data-act]").forEach((b) => { b.disabled = true; });
      show("");
      try {
        const res = await call(fn, arg);
        if (done == null) {
          // 업그레이드 — 미리 보여 준 금액이 아니라 실제 청구액을 알린다.
          const charged = (res && res.data && res.data.charged) || 0;
          done = (charged > 0 ? k.okUp.replace("{a}", won(charged, EN())) : k.okUp0)
            .replace("{p}", upTo || "");
        }
        // 사유는 처리에 성공한 뒤에 보낸다. 먼저 보내면 해지가 실패했는데
        // '해지 사유'만 접수되어, 있지도 않은 해지가 집계에 잡힌다.
        if (survey) sendReason(survey, ok, st.user);
        // 화면은 구독 문서가 바뀌면 저절로 다시 그려진다. 결과 문구는 flash 에
        // 담아 두고 한 번 더 그려, 그 사이에 지워지지 않게 한다.
        flash = { text: done, err: false };
        if (repaint) repaint(); else show(done, false);
      } catch (e) {
        console.error("[billing]", fn, e);
        show(e.message || k.fail, true);
        root.querySelectorAll("[data-act]").forEach((b) => { b.disabled = false; });
      }
    });
  });
}

async function loadUsage() {
  if (!isConfigured) return null;
  try {
    const res = await call("getUsage");
    return res.data && res.data.active ? res.data : null;
  } catch (e) {
    // 아직 배포 안 됐거나 실패 — 이 줄만 빠지고 나머지는 그대로 보인다.
    console.warn("[billing] 열람 현황 조회 실패", e);
    return null;
  }
}

async function loadPayments(uid) {
  if (window.__KOSDEMO) return window.KOSDemo.payments();
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

/* 어떤 화면이든 repaint 에 담아 두고 그린다.
   #blApp 은 data-i18n-skip 이라 번역 엔진이 손대지 않는다. 그래서 여기서 다시
   그리지 않으면 언어를 바꿔도 그 화면만 옛 언어로 남는다 — 안내 화면들은
   repaint 를 비워 둔 채였고, KO 로 바꿔도 영어가 그대로 있었다. */
function screen(fn) { repaint = fn; fn(); }

(async function main() {
  await window.KOSPaywall.ready;
  let payments = [];
  window.KOSPaywall.onChange(async (st) => {
    if (!st.user) {
      screen(() => { const k = t();
        empty(k.needT, k.needD,
          `<a class="btn btn-primary" href="Login.html?next=billing.html">${esc(k.login)}</a>`); });
      return;
    }
    /* 결제 내역은 구독 상태와 무관하게 불러온다. 구독이 없다고 지난 결제까지
       감추면, 돈을 낸 적 있는 사람이 그 기록을 확인할 데가 없어진다. */
    if (!payments.length) payments = await loadPayments(st.user.uid);
    usage = st.active ? await loadUsage() : null;
    screen(() => view(st, payments));
  });
})();
