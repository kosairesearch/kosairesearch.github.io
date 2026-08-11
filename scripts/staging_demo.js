/* ============================================================
   KOSAI — 스테이징 모의 백엔드 (demo-backend.js 로 복사됨)
   ------------------------------------------------------------
   ⚠️ 스테이징 전용. 실제 사이트에는 절대 올라가지 않는다.

   결제 키와 서버가 아직 없어 가입 흐름을 눌러볼 수가 없었다. 그래서
   구독 상태를 브라우저(localStorage)에 두고 서버 흉내를 낸다.
     · 로그인은 진짜다(파이어베이스). 구독만 가짜다.
     · 돈은 오가지 않는다. 카드도 묻지 않는다.
     · 브라우저를 지우면 구독도 사라진다.

   서버(functions/index.js)와 같은 규칙을 지킨다 — 그래야 미리보기가
   출시 후와 같은 화면을 보여준다.
     · 하루 한도는 '열람 횟수'가 아니라 '오늘 본 서로 다른 종목' 수
     · 같은 종목 재열람은 차감하지 않는다
     · 한도는 한국 시간 자정에 초기화
     · 업그레이드는 즉시·차액, 다운그레이드는 다음 결제일
   ============================================================ */
import { auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { PLANS } from "./payment-config.js";

const SUB_KEY = "kos-demo-sub", READ_KEY = "kos-demo-reads", PAY_KEY = "kos-demo-pays",
      FB_KEY = "kos-demo-reasons";

/* 유료 구간 키 — scripts/report_split.py 의 PAID_KEYS 와 같아야 한다.
   여기서만 다르면 미리보기가 실제와 다른 걸 잠그게 된다. */
const PAID_KEYS = ["earnings", "industry", "outlook", "valuation_comment",
                   "bull", "bear", "risks", "checkpoints", "verdict", "recent", "desc"];

const read = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } };
const write = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
const kstDay = () => new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10);

function addMonth(from) {
  const d = new Date(from), day = d.getDate();
  d.setMonth(d.getMonth() + 1);
  if (d.getDate() !== day) d.setDate(0);
  return d.getTime();
}
function activeNow(s) {
  return !!(s && s.status === "active" && s.currentPeriodEnd > Date.now());
}
function pay(entry) {
  const list = read(PAY_KEY, []);
  list.unshift({ createdAt: Date.now(), paidAt: Date.now(), ...entry });
  write(PAY_KEY, list);
}

let user = null;
const listeners = new Set();
let resolveReady;
const ready = new Promise((r) => { resolveReady = r; });

function snapshot() {
  /* 로그인 없이는 구독도 없다. 서버에서 구독은 subscriptions/{uid} 라 로그인이
     전제인데, 여기서는 브라우저에 두다 보니 로그인 전에도 '구독 있음'으로 답했다.
     파이어베이스가 저장된 세션을 되살리는 몇백 밀리초 동안 화면은 '구독은 있는데
     로그인은 안 된 사람'을 보고, 리포트를 열려다 로그인 페이지로 튕긴다. */
  const sub = user ? read(SUB_KEY, null) : null;
  const plan = sub ? sub.plan : null;
  return { user, sub, active: activeNow(sub), plan,
           limit: (PLANS[plan] || {}).limit || null, plans: PLANS };
}
function emit() { const s = snapshot(); listeners.forEach((fn) => { try { fn(s); } catch (e) {} }); }

if (isConfigured) {
  onAuthStateChanged(auth, (u) => { user = u || null; emit(); resolveReady(snapshot()); });
} else {
  resolveReady(snapshot());
}

/* 하루 한도 차감. 서버 consumeDailyRead 와 같은 규칙. */
function consume(ticker, limit) {
  const day = kstDay();
  let r = read(READ_KEY, null);
  if (!r || r.day !== day) r = { day, tickers: [] };
  if (r.tickers.includes(ticker)) return true;    // 오늘 이미 본 종목
  if (r.tickers.length >= limit) return false;
  r.tickers.push(ticker);
  write(READ_KEY, r);
  return true;
}

async function fetchPaid(ticker) {
  const st = snapshot();
  const err = (code, msg) => { const e = new Error(msg); e.code = code; return e; };
  if (!st.user) throw err("unauthenticated", "로그인이 필요합니다.");
  if (!st.active) throw err("permission-denied", "멤버십이 필요합니다.");
  if (!st.limit) throw err("failed-precondition", "요금제 정보를 확인할 수 없습니다.");

  // 실제로는 Firestore 에 있다. 미리보기에서는 아직 정적 파일에 남아 있는
  // 전문에서 유료 구간만 골라 온다.
  const res = await fetch(`../data/reports_v2/${encodeURIComponent(ticker)}.json`, { cache: "no-cache" });
  if (!res.ok) throw err("not-found", "리포트를 찾을 수 없습니다.");
  const rep = await res.json();
  const paid = {};
  PAID_KEYS.forEach((k) => { if (rep[k] != null) paid[k] = rep[k]; });
  if (!Object.keys(paid).length) throw err("not-found", "유료 구간이 없습니다.");

  // 리포트가 있는 걸 확인한 뒤에 차감한다(없는 종목으로 한도를 잃으면 안 된다)
  if (!consume(ticker, st.limit)) throw err("resource-exhausted", "오늘 열람 한도를 모두 사용했습니다.");
  return { ticker, paid, plan: st.plan, limit: st.limit };
}

/* 결제 — 카드도 안 묻고 바로 구독을 만든다. */
function subscribe(planId) {
  const p = PLANS[planId];
  if (!p) throw new Error("plan");
  const now = Date.now();
  write(SUB_KEY, {
    status: "active", plan: p.id,
    currentPeriodStart: now, currentPeriodEnd: addMonth(now),
    cancelAtPeriodEnd: false, pendingPlan: null,
    card: { company: "모의 카드", number: "0000-00**-****-0000" },
    // 새 구독이면 오늘이 시작일이다(서버 confirmBilling 과 같다).
    startedAt: now,
  });
  pay({ amount: p.price, description: `${p.name} 월 구독 (모의)`, kind: "subscription", status: "paid", plan: p.id });
  emit();
}

/* 카드만 바꾸기. 결제는 하지 않는다(서버 confirmBilling updateMethod 와 같다).
   결제가 밀려 멈춘 구독이면 새 카드로 바로 받아 되살린다. */
function updateCard() {
  const sub = read(SUB_KEY, null);
  if (!sub) throw new Error("이용 중인 구독이 없습니다.");
  const n = String(1000 + Math.floor(Math.random() * 9000));
  sub.card = { company: "모의 카드", number: `0000-00**-****-${n}` };
  if (sub.status === "past_due") {
    const now = Date.now();
    sub.status = "active";
    sub.currentPeriodStart = now;
    sub.currentPeriodEnd = addMonth(now);
    const p = PLANS[sub.plan];
    if (p) pay({ amount: p.price, description: `${p.name} 월 구독 (모의)`, kind: "subscription", status: "paid", plan: p.id });
  }
  write(SUB_KEY, sub);
  emit();
}

/* 환불 금액 — 서버 refundQuote 와 같은 기준.
   미열람 + 7일 이내면 전액, 아니면 잔여 기간분에서 수수료 10%. */
function refundAmount(sub) {
  const total = Math.max(1, (sub.currentPeriodEnd - sub.currentPeriodStart) / 86400e3);
  const used = Math.min(total, Math.max(0, (Date.now() - sub.currentPeriodStart) / 86400e3));
  const opened = (read(READ_KEY, { tickers: [] }).tickers || []).length > 0;
  const price = (PLANS[sub.plan] || {}).price || 0;
  return (!opened && used <= 7) ? price
       : Math.floor(price * Math.max(0, (total - used) / total) * 0.9);
}

/* 구독 관리 버튼들. 서버 함수와 같은 이름·같은 규칙. */
async function call(name, arg) {
  if (name === "getUsage") {
    const st = snapshot();
    if (!st.active) return { data: { active: false, used: 0, limit: 0 } };
    return { data: { active: true, plan: st.plan, limit: st.limit,
                     used: (read(READ_KEY, { tickers: [] }).tickers || []).length } };
  }
  /* 해지·환불 사유. 미리보기에서는 메일을 보내지 않고 남겨만 둔다 —
     KOSDemo.reasons() 로 무엇이 접수됐는지 확인할 수 있다. */
  if (name === "submitForm") {
    const list = read(FB_KEY, []);
    list.unshift({ at: Date.now(), ...(arg || {}) });
    write(FB_KEY, list);
    console.log("[demo] 사유 접수", arg);
    return { data: { ok: true, demo: true } };
  }
  /* 탈퇴 — 미리보기에서는 실제 계정을 지우지 않는다. 스테이징은 진짜 파이어베이스
     계정으로 로그인하므로, 여기서 지우면 실제 계정이 사라진다.
     환불은 서버와 같은 기준으로 먼저 계산해 돌려준다(고지한 기준 그대로). */
  if (name === "deleteAccount") {
    const s0 = read(SUB_KEY, null);
    let refunded = 0;
    if (s0 && activeNow(s0)) refunded = refundAmount(s0);
    [SUB_KEY, READ_KEY, PAY_KEY].forEach((k) => localStorage.removeItem(k));
    emit();
    return { data: { ok: true, demo: true, refunded } };
  }
  const sub = read(SUB_KEY, null);
  if (!sub) throw new Error("이용 중인 구독이 없습니다.");
  let charged = 0;                    // 업그레이드 차액 — 서버와 같이 돌려준다
  // 해지 예약과 플랜 변경 예약은 함께 둘 수 없다(서버 changePlan 설명 참고).
  if (name === "cancelSubscription") { sub.cancelAtPeriodEnd = true; sub.pendingPlan = null; }
  else if (name === "resumeSubscription") sub.cancelAtPeriodEnd = false;
  else if (name === "changePlan") {
    sub.cancelAtPeriodEnd = false;
    const next = PLANS[(arg || {}).plan];
    if (!next) throw new Error("요금제를 확인할 수 없습니다.");
    if (next.price > PLANS[sub.plan].price) {
      const total = Math.max(1, (sub.currentPeriodEnd - sub.currentPeriodStart) / 86400e3);
      const left = Math.max(0, (sub.currentPeriodEnd - Date.now()) / 86400e3);
      const diff = Math.floor((next.price - PLANS[sub.plan].price) * (left / total));
      sub.plan = next.id; sub.pendingPlan = null;
      charged = diff;
      // 남은 기간이 없으면 0원 — 서버 charge() 도 0 이하면 청구하지 않는다.
      if (diff > 0) pay({ amount: diff, description: `${next.name} 업그레이드 차액 (모의)`, kind: "upgrade", status: "paid", plan: next.id });
    } else {
      // 다운그레이드는 다음 결제일부터. 지금 쓰는 플랜을 다시 고르면 예약 취소.
      sub.pendingPlan = next.id === sub.plan ? null : next.id;
    }
  } else if (name === "requestRefund") {
    const amount = refundAmount(sub);
    pay({ amount: -amount, description: "환불 (모의)", kind: "refund",
         why: (read(READ_KEY, { tickers: [] }).tickers || []).length ? "used" : "withdraw",
         status: "refunded", plan: sub.plan });
    sub.status = "refunded"; sub.currentPeriodEnd = Date.now();
  }
  write(SUB_KEY, sub);
  emit();
  return { data: { ok: true, charged } };
}

window.__KOSDEMO = true;
window.KOSDemo = {
  subscribe, updateCard, call,
  payments: () => read(PAY_KEY, []),
  reasons: () => read(FB_KEY, []),
  reset() { [SUB_KEY, READ_KEY, PAY_KEY, FB_KEY].forEach((k) => localStorage.removeItem(k)); emit(); },
  readsToday: () => (read(READ_KEY, { tickers: [] }).tickers || []).length,
  /* 눌러 볼 수 없는 상태들 — 콘솔에서 만들어 화면을 확인한다.
     KOSDemo.simulate('past_due') / 'expired' */
  simulate(what) {
    const sub = read(SUB_KEY, null);
    if (!sub) throw new Error("구독 없음");
    if (what === "past_due") { sub.status = "past_due"; }
    else if (what === "expired") { sub.status = "active"; sub.currentPeriodEnd = Date.now() - 1000; }
    else throw new Error("past_due | expired");
    write(SUB_KEY, sub); emit();
  },
};
window.KOSPaywall = {
  ready, isConfigured: true, state: snapshot,
  onChange(fn) { listeners.add(fn); fn(snapshot()); return () => listeners.delete(fn); },
  fetchPaid,
};

// 본문이 먼저 그려졌을 수 있다 — 자리를 잡았다고 알린다(paywall.js 와 같은 신호).
document.dispatchEvent(new Event("kos-paywall-ready"));
