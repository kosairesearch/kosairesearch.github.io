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

/* 오늘 본 종목 수. 서버 usageOf 와 같다.

   구독별로 따로 세지 않는다. 구독 기간이 겹치지 않게 만들어 두었기 때문에
   (subscribe 가 이전 구독이 끝나는 시점부터 시작한다) 어느 하루의 열람은
   언제나 한 구독에만 속한다. */
function usedToday() {
  const r = read(READ_KEY, null);
  return ((r && r.day === kstDay() && r.tickers) || []).length;
}

/* 하루 한도 차감. 서버 consumeDailyRead 와 같은 규칙. */
function consume(ticker, limit) {
  const day = kstDay();
  const sub = read(SUB_KEY, null);
  let r = read(READ_KEY, null);
  if (!r || r.day !== day) r = { day, tickers: [] };
  if (r.tickers.includes(ticker)) return true;    // 오늘 이미 본 종목
  if (r.tickers.length >= limit) return false;
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
  /* 이미 이용 중이면 새로 만들지 않는다(서버 confirmBilling 과 같다). 돈을 두
     번 받는 자리다. 해지 예약(cancelAtPeriodEnd)이나 환불 완료(refundedAt)는
     예외다 — 그 둘은 '다시 시작하기' 로 여기에 오는 길이다. */
  const cur = read(SUB_KEY, null);
  if (activeNow(cur) && !cur.cancelAtPeriodEnd && !cur.refundedAt) {
    throw new Error("이미 이용 중인 구독이 있습니다.");
  }
  const now = Date.now();
  /* 이용은 지금부터. 이전 구독과 겹치는 하루는 기간 끝에 붙인다
     (서버 confirmBilling 과 같다 — 그쪽 주석에 이유를 적어 두었다).

     환불한 날 다시 시작하는 사람이 여기로 온다. 오늘 리포트를 봤다면 오늘
     요금은 이미 환불에서 차감했고 그 구독은 자정까지 살아 있다. 거기에 새
     구독까지 오늘부터 시작하니 같은 하루를 두 번 내는 셈인데, 그 하루를
     앞에서 빼지 않고 뒤에 붙여 돌려준다.

     이전 구독이 이미 끝났으면(오늘 한 건도 안 봐서 환불과 동시에 닫힌 경우,
     또는 처음 가입) 겹치는 하루가 없으므로 그냥 한 달이다. */
  const prev = read(SUB_KEY, null);
  const start = now;
  const end = addMonth(Math.max(now, (prev && prev.currentPeriodEnd) || 0));
  write(SUB_KEY, {
    status: "active", plan: p.id,
    currentPeriodStart: start, currentPeriodEnd: end,
    cancelAtPeriodEnd: false, pendingPlan: null,
    // 실제 서버는 카드사 이름을 모르면 비워 둔다(토스가 코드로만 준다).
    card: { company: "", issuerCode: "61", number: "0000-00**-****-0000" },
    startedAt: start,
    /* 이번 주기에 받은 돈. 환불이 이 목록을 보고 계산한다(서버 periodPayments).
       from 은 그 돈이 사는 기간의 시작이다 —
       월 구독은 주기 전체를 산다(서버 confirmBilling 과 같다). */
    periodPayments: [{ key: "demo-" + now, amount: p.price, from: start }],
    // 결제 후 연 리포트 수. 환불이 '한 번도 안 열었는가' 를 이걸로 판단한다.
    readsSincePay: 0,
  });
  pay({ amount: p.price, description: `${p.name} 월 구독 (모의)`, kind: "subscription", status: "paid", plan: p.id });
  emit();
}

/* 카드만 바꾸기. 결제는 하지 않는다(서버 confirmBilling updateMethod 와 같다).
   결제가 밀려 멈춘 구독이면 새 카드로 바로 받아 되살린다. */
function updateCard() {
  const sub = read(SUB_KEY, null);
  /* 환불이 끝난 구독에는 카드도 새로 걸지 않는다. 오늘 값을 받은 환불은
     자정까지 살아 있어서 그 사이에 여기까지 올 수 있는데, 곧 끝날 구독에
     카드를 등록시키면 다음 달에 긁힐 것처럼 읽힌다. */
  if (sub && sub.refundedAt) throw new Error("환불이 완료된 구독입니다.");
  /* 카드를 바꿀 수 있는 상태는 둘뿐이다 — 이용 중이거나, 결제가 밀려 멈춰
     있거나(서버 confirmBilling updateMethod 와 같다). 이미 끝난 구독은 카드를
     새로 걸어도 다시 결제되지 않으므로, 되는 것처럼 보여 주면 안 된다. */
  if (!activeNow(sub) && !(sub && sub.status === "past_due")) {
    throw new Error("이용 중인 구독이 없습니다.");
  }
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
      sub.periodPayments = [{ key: "demo-" + now, amount: p.price, from: now }];
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

/* 아직 안 쓴 돈. 결제 건마다 그 돈이 사는 기간이 다르므로 따로 센다
   (서버 unusedOf 와 같은 식 — 그쪽 주석에 이유를 적어 두었다).

   월 구독은 주기 전체를 사고, 업그레이드 차액은 '그날부터 주기 끝까지' 만
   산다. 한 덩어리로 세면 차액에서도 지나간 날을 빼는데, 그 날들에는 옛 플랜을
   썼지 새 플랜을 쓴 적이 없다. */
function unusedMoney(sub, usedUntilDay) {
  const endDay = kstDayNo(sub.currentPeriodEnd);
  const list = (sub.periodPayments || []).length
    ? sub.periodPayments
    : [{ amount: (PLANS[sub.plan] || {}).price || 0, from: sub.currentPeriodStart }];
  return list.reduce((sum, p) => {
    const fromDay = kstDayNo(p.from || sub.currentPeriodStart);
    const win = Math.max(1, endDay - fromDay);
    const left = Math.max(0, endDay - Math.max(fromDay, usedUntilDay));
    return sum + (p.amount || 0) * Math.min(1, left / win);
  }, 0);
}

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
  const openedToday = usedToday() > 0;
  // 지난 날은 전부 차감하고, 오늘은 열었을 때만 더한다.
  const elapsed = Math.max(0, kstDayNo(at) - kstDayNo(sub.currentPeriodStart));
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));
  // 업그레이드 차액까지 포함한 '실제로 받은 돈'이 기준이다(서버와 같다).
  const price = paidThisPeriod(sub) || (PLANS[sub.plan] || {}).price || 0;
  if (!opened && used <= 7) {
    return { amount: price, why: "withdraw", chargedToday: openedToday };
  }
  // 이 날짜까지는 쓴 것으로 본다. 그 뒤에 남은 돈만 돌려준다.
  const unused = unusedMoney(sub, kstDayNo(sub.currentPeriodStart) + used);
  return {
    amount: Math.floor(unused * 0.9),
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
                     used: usedToday() } };
  }
  /* 결제 내역. 서버와 같은 이름·같은 모양으로 답한다 — 화면이 미리보기인지
     실제인지 따지지 않게 하려는 것이다.

     구독이 없어도 답한다. 아래 '구독 없으면 거절' 블록보다 위에 있어야 한다 —
     환불하고 나간 사람도 지난 내역은 볼 수 있어야 한다. */
  /* 환불 견적. 돈을 건드리지 않고 계산만 한다(서버 refundPreview 와 같다).
     확인 창에 금액을 적어 주려고 있다 — 여태 금액 없이 물어보고 누른 뒤에야
     얼마인지 알려 줬다. */
  if (name === "refundPreview") {
    const s0 = read(SUB_KEY, null);
    if (!s0 || !activeNow(s0)) throw new Error("이용 중인 구독이 없습니다.");
    if (s0.refundedAt) throw new Error("이미 환불이 완료되었습니다.");
    const q = refundAmount(s0);
    return { data: { amount: q.amount, why: q.why, chargedToday: q.chargedToday,
                     endsAt: q.chargedToday ? kstEndOfToday() : Date.now() } };
  }
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
  /* 서버는 '문서가 있는가' 가 아니라 '지금 이용 중인가' 로 막는다(subActive).
     결제가 밀려 멈춘 구독이나 이미 끝난 구독에도 해지·플랜 변경·환불이 되면,
     미리보기에서는 되는데 실제로는 거절당한다. 순서도 서버와 같게 둔다 —
     이용 중이 아닌 것을 먼저 보고, 그다음에 환불이 끝났는지 본다. */
  if (!activeNow(sub)) throw new Error("이용 중인 구독이 없습니다.");
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
    const next = PLANS[(arg || {}).plan];
    if (!next) throw new Error("요금제를 확인할 수 없습니다.");
    /* 쓰고 있는 플랜을 다시 고르는 건 '예약 취소' 다. 그런데 취소할 예약이
       없으면 할 일이 없다 — 서버는 여기서 거절한다(changePlan).

       이 관문이 없으면 그냥 통과하는 데서 끝나지 않는다. 바로 아래에서
       cancelAtPeriodEnd 를 내리므로, 해지를 예약해 둔 사람이 같은 플랜을 다시
       고르면 해지가 조용히 풀린다. 서버에서는 거절당하는 동작이다. */
    if (next.id === sub.plan && !sub.pendingPlan) {
      throw new Error("이미 해당 플랜을 이용 중입니다.");
    }
    sub.cancelAtPeriodEnd = false;
    if (next.price > PLANS[sub.plan].price) {
      const total = Math.max(1, (sub.currentPeriodEnd - sub.currentPeriodStart) / 86400e3);
      const left = Math.max(0, (sub.currentPeriodEnd - Date.now()) / 86400e3);
      const diff = Math.floor((next.price - PLANS[sub.plan].price) * (left / total));
      sub.plan = next.id; sub.pendingPlan = null;
      // 토스는 카드로 100원 미만을 결제할 수 없다. 서버 charge() 와 같이
      // 그 아래면 청구를 건너뛰고 플랜만 올린다.
      charged = diff >= MIN_CHARGE ? diff : 0;
      // 차액은 '지금부터 주기 끝까지' 를 산다. 그 값으로 청구했으니
      // 환불도 그 기간으로 나눠야 한다(서버 changePlan 과 같다).
      if (charged) sub.periodPayments = [...(sub.periodPayments || []),
        { key: "demo-up-" + Date.now(), amount: charged, from: Date.now() }];
      if (charged) pay({ amount: diff, description: `${next.name} 업그레이드 차액 (모의)`, kind: "upgrade", status: "paid", plan: next.id });
    } else {
      // 다운그레이드는 다음 결제일부터. 지금 쓰는 플랜을 다시 고르면 예약 취소.
      sub.pendingPlan = next.id === sub.plan ? null : next.id;
    }
  } else if (name === "requestRefund") {
    const q = refundAmount(sub);
    /* 확인 창에서 본 금액과 다르면 실행하지 않는다(서버와 같다). 창을 띄운 뒤
       리포트를 한 건 열면 오늘이 이용일로 잡혀 금액이 달라진다. */
    const expect = Number((arg || {}).expectAmount ?? NaN);
    if (Number.isFinite(expect) && expect !== q.amount) {
      throw new Error(`환불 금액이 ${q.amount.toLocaleString("ko-KR")}원으로 변경되었습니다. 다시 확인해 주시기 바랍니다.`);
    }
    refunded = q.amount;
    /* 한 주기에 결제가 여러 건일 수 있다(월 구독 + 업그레이드 차액). 카드사는
       결제 건 하나를 그 건의 금액 안에서만 취소해 주므로, 최근 건부터 차례로
       각 건의 금액만큼 취소한다. 서버 doRefund 와 같은 규칙이다.

       내역도 건마다 남긴다 — 취소가 둘로 나가면 카드 명세서에도 둘로 찍힌다.

       내역에 적는 사유는 계산이 쓴 신호를 그대로 쓴다. 표시만 따로 세면
       '청약철회'로 적힌 건에 이용분이 차감돼 있는, 설명할 수 없는 내역이 남는다. */
    let rest = refunded;
    for (const src of (sub.periodPayments || []).slice().reverse()) {
      if (rest <= 0) break;
      const take = Math.min(rest, src.amount || 0);
      if (take <= 0) continue;
      pay({ amount: -take, description: "환불 (모의)", kind: "refund",
            why: q.why, status: "refunded", plan: sub.plan });
      rest -= take;
    }
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
  /* amount 는 서버 requestRefund 가 쓰는 이름이다. 미리보기만 refunded 로
     주면 화면이 실제 서버에서는 금액을 못 읽는다 — 둘 다 담아 보낸다. */
  return { data: { ok: true, charged, refunded, amount: refunded, endsAt } };
}

window.__KOSDEMO = true;
window.KOSDemo = {
  subscribe, updateCard, call,
  payments: () => read(PAY_KEY, []),
  reasons: () => read(FB_KEY, []),
  reset() { [SUB_KEY, READ_KEY, PAY_KEY, FB_KEY].forEach((k) => localStorage.removeItem(k)); emit(); },
  readsToday: () => usedToday(),
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
