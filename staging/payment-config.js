/* ============================================================
   KOSAI — 요금제·결제 설정 (프런트 공용)
   ------------------------------------------------------------
   요금과 한도가 여러 파일에 흩어지면 어느 하나만 고쳐 놓고 지나가게 된다.
   화면에 쓰이는 값은 전부 여기서 가져다 쓴다.
   ⚠️ 실제 청구 금액과 열람 한도는 서버(functions/index.js)가 다시 판단한다.
      여기 값은 표시용이다 — 클라이언트가 보낸 금액을 믿으면 안 된다.

   ▶ 설정 방법(토스페이먼츠)
   1) https://developers.tosspayments.com 에서 상점 등록
   2) 결제 → API 키에서 '클라이언트 키'를 복사해 아래 [PLACEHOLDER] 교체
      (시크릿 키는 절대 여기에 두지 말 것 — Functions 환경변수 TOSS_SECRET_KEY)
   3) 정기결제(빌링)를 사용 설정
   ============================================================ */

export const PLANS = {
  basic: { id: "basic", name: "BASIC", price: 9900,  limit: 5  },
  pro:   { id: "pro",   name: "PRO",   price: 14900, limit: 15 },
};

export const TOSS = {
  clientKey: "[TOSS_CLIENT_KEY]",
  // 결제창에서 돌아올 주소. 경로만 두고 origin 은 실행 시점에 붙인다.
  successPath: "checkout.html",
  failPath: "checkout.html",
};

export const payReady = !TOSS.clientKey.startsWith("[");

export function planOf(id) {
  return PLANS[String(id || "").toLowerCase()] || null;
}

/** 카드로 청구할 수 있는 최소 금액. 토스페이먼츠 정책상 신용·체크카드는
    100원 미만을 결제할 수 없다. 업그레이드 차액은 남은 기간에 비례하므로
    결제 주기 끝자락에는 이 아래로 떨어진다 — 그대로 청구를 시도하면
    카드사가 거절하고 업그레이드 자체가 실패한다. */
export const MIN_CHARGE = 100;

/** 업그레이드를 지금 누르면 카드에서 빠져나갈 차액.
    서버 changePlan 과 같은 식이다. 표시용이며, 실제 청구액은 서버가 다시 계산한다.
    남은 기간이 얼마 없으면 0원이 나올 수 있다(그때는 아무것도 청구되지 않는다). */
export function upgradeDiff(sub, toId) {
  const to = planOf(toId), cur = planOf(sub && sub.plan);
  if (!to || !cur || to.price <= cur.price) return 0;
  const ms = (v) => (v && typeof v.toMillis === "function") ? v.toMillis()
                  : typeof v === "number" ? v : Date.parse(v);
  const end = ms(sub.currentPeriodEnd);
  const start = sub.currentPeriodStart ? ms(sub.currentPeriodStart) : end - 30 * 86400000;
  if (!Number.isFinite(end) || !Number.isFinite(start)) return 0;
  const total = Math.max(1, (end - start) / 86400000);
  const left = Math.max(0, (end - Date.now()) / 86400000);
  return Math.floor((to.price - cur.price) * (left / total));
}

/** 9900 → "9,900원" / en: "KRW 9,900" */
export function won(v, en) {
  const n = Number(v || 0).toLocaleString("en-US");
  return en ? `KRW ${n}` : `${n}원`;
}

/** Firestore Timestamp | ISO 문자열 → "2026년 9월 6일" / "Sep 6, 2026" */
export function fmtDay(v, en) {
  if (!v) return "";
  const ms = typeof v?.toMillis === "function" ? v.toMillis()
           : typeof v === "number" ? v : Date.parse(v);
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms);
  const M = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  return en
    ? `${M[d.getMonth()]} ${d.getDate()}, ${d.getFullYear()}`
    : `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
}
