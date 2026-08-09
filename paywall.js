/* ============================================================
   KOSAI — 유료 구간 접근 (전 페이지 공용)
   ------------------------------------------------------------
   무료 구간은 정적 파일로 공개되고, 유료 구간은 Firestore 에만 있다.
   이 모듈이 로그인·구독 상태를 확인하고 getReport 를 호출해 받아온다.

   전역 API: window.KOSPaywall
     .ready                  → Promise (첫 인증 확인이 끝나면 resolve)
     .state()                → { user, sub, active, plan }
     .onChange(fn)           → 로그인/구독이 바뀔 때마다 호출(즉시 1회 포함)
     .fetchPaid(ticker)      → Promise<{ paid, plan, limit }>
                               실패하면 code 를 가진 Error 를 던진다:
                               unauthenticated / permission-denied /
                               resource-exhausted / not-found / internal

   구독 문서는 subscriptions/{uid}. 서버(Functions)만 쓰고 클라이언트는 읽기만
   한다 — 사용자가 자기 문서의 plan 을 pro 로 고쳐 쓸 수 있으면 안 된다.
   ============================================================ */
import { app, auth, isConfigured, SOCIAL } from "./firebase-config.js";
import { PLANS } from "./payment-config.js";
import { onAuthStateChanged }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, onSnapshot }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const db = isConfigured ? getFirestore(app) : null;
const fns = isConfigured ? getFunctions(app, SOCIAL.functionsRegion || "asia-northeast3") : null;

let user = null;
let sub = null;            // { status, plan, currentPeriodEnd, cancelAtPeriodEnd }
let unsubDoc = null;
const listeners = new Set();

/** 구독이 지금 유효한가. 서버 판단과 같은 기준을 쓴다(functions/index.js subActive). */
function activeNow(s) {
  if (!s || s.status !== "active") return false;
  const end = s.currentPeriodEnd;
  if (!end) return false;
  const ms = typeof end?.toMillis === "function" ? end.toMillis()
            : typeof end === "number" ? end : Date.parse(end);
  return Number.isFinite(ms) && ms > Date.now();
}

function snapshot() {
  const plan = (sub && sub.plan) || null;
  // 한도 숫자는 payment-config 한 곳에서 온다. 화면마다 5·15를 적어 두면
  // 값을 바꿀 때 한 군데를 빼먹는다.
  return { user, sub, active: activeNow(sub), plan,
           limit: (PLANS[plan] || {}).limit || null, plans: PLANS };
}

function emit() {
  const s = snapshot();
  listeners.forEach((fn) => { try { fn(s); } catch (e) { console.error("[paywall]", e); } });
}

let resolveReady;
const ready = new Promise((r) => { resolveReady = r; });

if (isConfigured) {
  onAuthStateChanged(auth, (u) => {
    user = u || null;
    if (unsubDoc) { unsubDoc(); unsubDoc = null; }
    sub = null;
    if (u) {
      // 실시간 구독 — 결제가 끝나면 서버가 문서를 쓰고, 화면이 저절로 열린다.
      unsubDoc = onSnapshot(doc(db, "subscriptions", u.uid),
        (d) => { sub = d.exists() ? d.data() : null; emit(); resolveReady(snapshot()); },
        (e) => { console.warn("[paywall] 구독 조회 실패", e); sub = null; emit(); resolveReady(snapshot()); });
    } else {
      emit();
      resolveReady(snapshot());
    }
  });
} else {
  resolveReady(snapshot());
}

async function fetchPaid(ticker) {
  if (!isConfigured) { const e = new Error("설정 전"); e.code = "unavailable"; throw e; }
  if (!user) { const e = new Error("로그인이 필요합니다."); e.code = "unauthenticated"; throw e; }
  try {
    const call = httpsCallable(fns, "getReport");
    const res = await call({ ticker });
    return res.data;
  } catch (err) {
    // Functions 는 'functions/permission-denied' 형태로 준다 — 접두사를 떼고 넘긴다.
    const e = new Error(err.message || "요청에 실패했습니다.");
    e.code = String(err.code || "internal").replace(/^functions\//, "");
    throw e;
  }
}

window.KOSPaywall = {
  ready,
  isConfigured,
  state: snapshot,
  onChange(fn) { listeners.add(fn); fn(snapshot()); return () => listeners.delete(fn); },
  fetchPaid,
};

/* 이 모듈은 본문보다 늦게 뜬다. 리포트 본문은 같은 도메인의 JSON 하나만 받으면
   그려지는데, 여기는 구글에서 파이어베이스 묶음까지 받아야 하니 거의 항상 진다.
   먼저 그려진 화면이 window.KOSPaywall 을 못 찾고 그냥 지나가 버리지 않도록,
   자리를 잡았다고 알린다. */
document.dispatchEvent(new Event("kos-paywall-ready"));
