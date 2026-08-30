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
import { MIN_CHARGE, PLANS } from "./payment-config.js";

const SUB_KEY = "kos-demo-sub", READ_KEY = "kos-demo-reads", PAY_KEY = "kos-demo-pays",
      FB_KEY = "kos-demo-reasons";

/* 유료 구간 키 — scripts/report_split.py 의 PAID_KEYS 와 같아야 한다.
   여기서만 다르면 미리보기가 실제와 다른 걸 잠그게 된다. */
const PAID_KEYS = ["earnings", "industry", "outlook", "valuation_comment",
                   "bull", "bear", "risks", "checkpoints", "verdict", "recent", "desc"];

/* 화면에 보여 줄 결제 내역 줄 수. 서버 PAYMENT_PAGE 와 같아야 한다 —
   다르면 미리보기에서 보이던 줄이 실제에서 안 보인다. */
const PAYMENT_PAGE = 24;

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

/* 이 구독이 시작되기 전에 오늘 이미 본 몫. 한도에서 빼 준다.
   서버 readsOffset 과 같은 규칙.

   한 번 걷어냈다가 되돌렸다. '하루 한도는 날짜에 붙는다' 로 정하면 같은 날
   환불하고 다시 결제한 사람이 한 달치를 내고 오늘 0건을 받는다 — 받은 돈에
   아무것도 딸려 오지 않는 날이 생긴다. 새 구독은 자기 시작 시점부터 자기
   한도를 준다.

   같은 날 시작한 구독에만 적용한다. 어제 시작했으면 오늘 본 건 전부 이
   구독으로 본 것이다. */
function readsOffset(sub) {
  return sub && sub.readsAtStartDay === kstDay() ? (sub.readsAtStart || 0) : 0;
}
function usedToday(sub) {
  const r = read(READ_KEY, null);
  const seen = (r && r.day === kstDay() && r.tickers) || [];
  return Math.max(0, seen.length - readsOffset(sub === undefined ? read(SUB_KEY, null) : sub));
}

/* 하루 한도 차감. 서버 consumeDailyRead 와 같은 규칙. */
function consume(ticker, limit) {
  const day = kstDay();
  const sub = read(SUB_KEY, null);
  const off = readsOffset(sub);
  let r = read(READ_KEY, null);
  if (!r || r.day !== day) r = { day, tickers: [] };
  if (r.tickers.includes(ticker)) return true;    // 오늘 이미 본 종목
  if (r.tickers.length - off >= limit) return false;
  r.tickers.push(ticker);
  write(READ_KEY, r);
  /* 이번 결제 주기에 몇 개를 열었는지 따로 센다. 하루 목록(READ_KEY)은 자정에
     비므로 '결제 후 한 번도 안 열었는가' 를 그것으로 답할 수 없다 — 환불 기준이
     바로 그 질문이라 별도로 쌓아 둔다. */
  if (sub) { sub.readsSincePay = (sub.readsSincePay || 0) + 1; write(SUB_KEY, sub); }
  /* 열람 사실을 화면에 알린다. 이게 없으면 열어 둔 구독 화면의 '오늘 열람' 이
     리포트를 봐도 계속 처음 숫자에 멈춰 있다. */
  emit();
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
    // 실제 서버는 카드사 이름을 모르면 비워 둔다(토스가 코드로만 준다).
    card: { company: "", issuerCode: "61", number: "0000-00**-****-0000" },
    // 새 구독이면 오늘이 시작일이다(서버 confirmBilling 과 같다).
    startedAt: now,
    // 이번 주기에 받은 돈. 환불이 이 합계를 기준으로 계산된다(서버 periodPayments).
    periodPayments: [{ key: "demo-" + now, amount: p.price }],
    // 결제 후 연 리포트 수. 환불이 '한 번도 안 열었는가' 를 이걸로 판단한다.
    readsSincePay: 0,
    /* 오늘 이미 본 몫은 이 구독의 한도에서 뺀다(서버 confirmBilling 과 같다).
       환불하고 같은 날 다시 시작한 사람에게 한도를 새로 주는 자리다. */
    readsAtStart: (function () {
      const r = read(READ_KEY, null);
      return (r && r.day === kstDay() && r.tickers ? r.tickers.length : 0);
    })(),
    readsAtStartDay: kstDay(),
  });
  pay({ amount: p.price, description: `${p.name} 월 구독 (모의)`, kind: "subscription", status: "paid", plan: p.id });
  emit();
}

/* 카드만 바꾸기. 결제는 하지 않는다(서버 confirmBilling updateMethod 와 같다).
   결제가 밀려 멈춘 구독이면 새 카드로 바로 받아 되살린다. */
function updateCard() {
  const sub = read(SUB_KEY, null);
  if (!sub) throw new Error("이용 중인 구독이 없습니다.");
  /* 환불이 끝난 구독에는 카드도 새로 걸지 않는다. 오늘 값을 받은 환불은
     자정까지 살아 있어서 그 사이에 여기까지 올 수 있는데, 곧 끝날 구독에
     카드를 등록시키면 다음 달에 긁힐 것처럼 읽힌다. */
  if (sub.refundedAt) throw new Error("환불이 완료된 구독입니다.");
  const n = String(1000 + Math.floor(Math.random() * 9000));
  sub.card = { company: "", issuerCode: "61", number: `0000-00**-****-${n}` };
  if (sub.status === "past_due") {
    const now = Date.now();
    sub.status = "active";
    sub.currentPeriodStart = now;
    sub.currentPeriodEnd = addMonth(now);
    const p = PLANS[sub.plan];
    if (p) {
      pay({ amount: p.price, description: `${p.name} 월 구독 (모의)`, kind: "subscription", status: "paid", plan: p.id });
      // 새 주기다 — 받은 돈도 연 리포트 수도 여기서 다시 센다. 안 비우면
      // 지난 주기 몫이 이번 환불 계산에 그대로 실린다.
      sub.periodPayments = [{ key: "demo-" + now, amount: p.price }];
      sub.readsSincePay = 0;
    }
  }
  write(SUB_KEY, sub);
  emit();
}

/* 환불 금액 — 서버 refundQuote 와 같은 기준.
   미열람 + 7일 이내면 전액, 아니면 잔여 기간분에서 수수료 10%. */
const paidThisPeriod = (sub) =>
  ((sub && sub.periodPayments) || []).reduce((a, e) => a + (e.amount || 0), 0);

/* 한국 시간 기준으로 며칠째인가(1970-01-01 = 0). 날짜끼리 빼면 날 수가 된다.
   서버 kstDayNo 와 같은 식이어야 한다. */
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600e3) / 86400e3);
/* 오늘이 끝나는 순간 = 내일 0시(KST). */
const kstEndOfToday = (ms = Date.now()) =>
  (kstDayNo(ms) + 1) * 86400e3 - 9 * 3600e3;

/* 환불 금액 — 서버 refundQuote 와 같은 기준.

   오늘 하루를 셀지 말지는 '오늘 리포트를 열었는가' 가 정한다.

     오늘 0건    오늘 값을 받지 않는다 → 이용은 지금 끝난다
     오늘 1건+   오늘 값을 받는다     → 이용은 오늘 자정까지

   경과 시간을 초 단위로 나눠 쓰고 있었다(9.375일). 우리가 파는 단위는 하루라
   쪼갤 수가 없는데 소수로 차감하니 양쪽 다 어긋났다 — 오전에 한 건도 안 보고
   환불하면 오늘 값을 내고 5건은 못 봤고, 5건 다 보고 환불하면 하루치를 다
   쓰고 0.375일만 냈다. */
function refundAmount(sub, at = Date.now()) {
  const total = Math.max(1, Math.round((sub.currentPeriodEnd - sub.currentPeriodStart) / 86400e3));
  /* '열었는가' 는 결제 후에 열었는가를 묻는 것이다.
     READ_KEY 를 보고 있었는데 그건 날짜를 안 가린 오늘·과거의 종목 목록이라,
     가입 전에 남은 기록 하나만 있어도 전액 환불이 막혔다. 결제 시점에 0으로
     두고 consume 이 올리는 readsSincePay 로 센다.

       고치기 전   옛 기록 2개 + 오늘 0개 열람 → 8,910원
       고친 뒤     같은 상황                   → 9,900원 (전액)

     결제 화면과 약관에 '7일 이내에 열람하지 않으셨다면 전액 환불' 이라고
     적어 두었다. 적어 둔 것과 계산이 달라서는 안 된다. */
  const opened = (sub.readsSincePay || 0) > 0;
  // 오늘 한 건이라도 열었는가. 화면의 '오늘 남은 열람' 과 같은 자료를 본다.
  const openedToday = usedToday(sub) > 0;
  // 지난 날은 전부 차감하고, 오늘은 열었을 때만 더한다.
  const elapsed = Math.max(0, kstDayNo(at) - kstDayNo(sub.currentPeriodStart));
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));
  // 업그레이드 차액까지 포함한 '실제로 받은 돈'이 기준이다(서버와 같다).
  const price = paidThisPeriod(sub) || (PLANS[sub.plan] || {}).price || 0;
  if (!opened && used <= 7) {
    return { amount: price, why: "withdraw", chargedToday: openedToday };
  }
  return {
    amount: Math.floor(price * Math.max(0, (total - used) / total) * 0.9),
    why: opened ? "used" : "left",
    chargedToday: openedToday,
  };
}

/* 구독 관리 버튼들. 서버 함수와 같은 이름·같은 규칙. */
async function call(name, arg) {
  if (name === "getUsage") {
    const st = snapshot();
    if (!st.active) return { data: { active: false, used: 0, limit: 0 } };
    return { data: { active: true, plan: st.plan, limit: st.limit,
                     used: usedToday(st.sub) } };
  }
  /* 결제 내역. 서버와 같은 이름·같은 모양으로 답한다 — 화면이 미리보기인지
     실제인지 따지지 않게 하려는 것이다.

     구독이 없어도 답한다. 아래 '구독 없으면 거절' 블록보다 위에 있어야 한다 —
     환불하고 나간 사람도 지난 내역은 볼 수 있어야 한다. */
  if (name === "listPayments") {
    return { data: { items: read(PAY_KEY, []).slice(0, PAYMENT_PAGE) } };
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
    if (s0 && activeNow(s0)) refunded = refundAmount(s0).amount;
    [SUB_KEY, READ_KEY, PAY_KEY].forEach((k) => localStorage.removeItem(k));
    emit();
    return { data: { ok: true, demo: true, refunded } };
  }
  const sub = read(SUB_KEY, null);
  if (!sub) throw new Error("이용 중인 구독이 없습니다.");
  /* 환불이 끝난 구독에는 아무것도 하지 않는다. 오늘 값을 받은 환불은 자정까지
     살아 있어서, 그 사이에 해지·플랜 변경·재환불을 또 누를 수 있다. 서버
     refundedAlready 와 같은 규칙이다. */
  if (sub.refundedAt) throw new Error("환불이 완료된 구독입니다.");
  let charged = 0;                    // 업그레이드 차액 — 서버와 같이 돌려준다
  let refunded = 0;                   // 환불액 — 화면이 얼마가 돌아가는지 말해야 한다
  let endsAt = 0;                     // 언제까지 볼 수 있는지 — 화면이 그대로 말한다
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
      // 토스는 카드로 100원 미만을 결제할 수 없다. 서버 charge() 와 같이
      // 그 아래면 청구를 건너뛰고 플랜만 올린다.
      charged = diff >= MIN_CHARGE ? diff : 0;
      if (charged) sub.periodPayments = [...(sub.periodPayments || []),
                                         { key: "demo-up-" + Date.now(), amount: charged }];
      if (charged) pay({ amount: diff, description: `${next.name} 업그레이드 차액 (모의)`, kind: "upgrade", status: "paid", plan: next.id });
    } else {
      // 다운그레이드는 다음 결제일부터. 지금 쓰는 플랜을 다시 고르면 예약 취소.
      sub.pendingPlan = next.id === sub.plan ? null : next.id;
    }
  } else if (name === "requestRefund") {
    const q = refundAmount(sub);
    refunded = q.amount;
    // 내역에 적는 사유도 계산이 쓴 신호를 그대로 쓴다. 표시만 따로 세면
    // '청약철회'로 적힌 건에 이용분이 차감돼 있는, 설명할 수 없는 내역이 남는다.
    pay({ amount: -refunded, description: "환불 (모의)", kind: "refund",
         why: q.why, status: "refunded", plan: sub.plan });
    /* 오늘 값을 받았으면 오늘은 끝까지 쓰게 둔다. 안 받았으면 지금 끝낸다.
       status 를 "refunded" 로 적지 않는 이유는 서버와 같다 — activeNow 가
       status === "active" 를 요구해서, 그렇게 적으면 자정까지 열어 두려던
       것이 그 자리에서 끊긴다. 끝났다는 사실은 refundedAt 이 말한다. */
    sub.status = "active";
    sub.cancelAtPeriodEnd = true;
    sub.pendingPlan = null;
    sub.currentPeriodEnd = q.chargedToday ? kstEndOfToday() : Date.now();
    sub.refundedAt = Date.now();
    endsAt = sub.currentPeriodEnd;
  }
  write(SUB_KEY, sub);
  emit();
  return { data: { ok: true, charged, refunded, endsAt } };
}

window.__KOSDEMO = true;
window.KOSDemo = {
  subscribe, updateCard, call,
  payments: () => read(PAY_KEY, []),
  reasons: () => read(FB_KEY, []),
  reset() { [SUB_KEY, READ_KEY, PAY_KEY, FB_KEY].forEach((k) => localStorage.removeItem(k)); emit(); },
  readsToday: () => usedToday(read(SUB_KEY, null)),
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
