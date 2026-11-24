/* ============================================================
   KOSAI — 요금제·결제 설정 (프런트 공용)
   ------------------------------------------------------------
   요금과 환불 안내가 여러 파일에 흩어지면 어느 하나만 고쳐 놓고 지나가게 된다.
   화면에 쓰이는 값은 전부 여기서 가져다 쓴다.
   ⚠️ 실제 청구 금액과 환불 금액은 서버(functions/index.js)가 다시 판단한다.
      여기 값은 표시용이다 — 클라이언트가 보낸 금액을 믿으면 안 된다.

   요금제는 하나다(2026-11-24 사장 "요금제는 1개 14900원. 열람은 무제한") —
   멤버십(member) · 월 14,900원 · 하루 한도 없음 · 요금제 변경 없음.
   예전의 basic · pro 는 없앴다. 시연 브라우저에 남은 옛 값(구독 · 결제 내역의
   plan)이나 옛 주소(checkout.html?plan=basic)는 planOf 가 member 로 읽는다.

   PLANS 와 REFUND_NOTICE 는 '@json' 표시 사이에 JSON 문법으로만 적는다 —
   요금제 화면 생성기(scripts/build_pricing.py)와 리포트 화면 생성기가 그 글을 그대로
   읽어 가격과 자주 묻는 질문의 환불 답을 그린다. 한 곳만 고치면 세 화면이 같이 바뀐다.

   ▶ 설정 방법(토스페이먼츠)
   1) https://developers.tosspayments.com 에서 상점 등록
   2) 결제 → API 키에서 '클라이언트 키'를 복사해 아래 [PLACEHOLDER] 교체
      (시크릿 키는 절대 여기에 두지 말 것 — Functions 환경변수 TOSS_SECRET_KEY)
   3) 정기결제(빌링)를 사용 설정
   ============================================================ */

export const PLANS = /*@json*/{
  "member": { "id": "member", "name": "멤버십", "nameEn": "Membership", "price": 14900 }
}/*@/json*/;

/** 하나뿐인 요금제 */
export const PLAN = PLANS.member;

/* 없앤 요금제 — 시연 기록 · 옛 주소에 남아 있으면 멤버십으로 읽는다. */
const LEGACY = { basic: "member", pro: "member" };

export function planOf(id) {
  const k = String(id || "").toLowerCase();
  return PLANS[k] || PLANS[LEGACY[k]] || null;
}

/** 화면에 적는 요금제 이름 — "멤버십" / en: "Membership" */
export function planName(p, en) {
  return p ? (en ? p.nameEn : p.name) : "";
}

/* 자동 수집 제한(약관 제9조③ — 무제한 열람의 단서). 최근 60분 안에 새로 연 서로 다른
   종목이 60개에 이르면 61번째 새 종목부터 거절한다. 오늘 이미 연 종목을 다시 여는 것은
   언제나 된다. 서버(functions/index.js)와 같은 값이어야 한다 — staging/tests/two-sides.test.mjs 가 본다. */
export const BURST_WINDOW_MIN = 60;
export const BURST_MAX = 60;

export const TOSS = {
  clientKey: "[TOSS_CLIENT_KEY]",
  // 결제창에서 돌아올 주소. 경로만 두고 origin 은 실행 시점에 붙인다.
  successPath: "checkout.html",
  failPath: "checkout.html",
};

export const payReady = !TOSS.clientKey.startsWith("[");

/** 14900 → "14,900원" / en: "KRW 14,900" */
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

/* 환불 안내 — 결제 화면 · 자주 묻는 질문 · 설정의 환불 확인 창이 이 글 하나를 쓴다(2026-11-24 명세 4절).
   결제 화면에는 반드시 보이게 둔다 — 전자상거래법 제17조⑥: 7일 안에도 이용한 날을 빼는 제한은 결제 전에
   알려야 효력이 있다. 계산은 시연 서버(demo-backend.js refundQuote)와 서버 refundQuote 가 같은 식으로 한다.
     lead   첫 문단
     steps  번호를 단 두 항목(7일 이내 · 7일 뒤)
     notes  그 아래 점 항목(이용료 식 · 예시 · 해지)
   예시 금액(13,410원 · 8,444원)은 이용 기간 30일 · 14,900원 기준이다. 가격을 바꾸면 같이 고친다 —
   staging/tests/subscription.test.mjs 가 시연 계산과 견준다. */
export const REFUND_NOTICE = /*@json*/{
  "ko": {
    "lead": "환불 금액은 환불 신청일부터 3영업일 이내에 결제하신 수단으로 돌려드립니다.",
    "steps": [
      "결제일(정기결제 갱신 결제일 포함)부터 7일 이내에 신청하시면, 결제금액에서 이용하신 날의 이용료를 뺀 금액을 환불합니다. 결제 후 리포트의 유료 영역을 열람하지 않으셨다면 전액 환불합니다.",
      "결제일부터 7일이 지난 뒤에 신청하시면, 결제금액에서 이용하신 날의 이용료와 결제금액의 10%(위약금)를 뺀 금액을 환불합니다. 계산한 금액이 0원 이하이면 환불 금액은 없으며, 추가로 청구하지 않습니다."
    ],
    "notes": [
      "이용하신 날의 이용료 = 결제금액 ÷ 해당 이용 기간의 일수 × 이용일수(이용 기간 시작일부터 환불 신청일까지). 1원 미만은 회원에게 유리하게 처리합니다.",
      "예) 이용 기간 30일 기준 — 3일째 신청 13,410원 환불 / 10일째 신청 8,444원 환불",
      "의무 사용 기간은 없으며, 설정의 구독 항목에서 언제든지 해지하실 수 있습니다. 해지하시면 다음 결제일부터 이용료가 청구되지 않고, 이미 결제하신 기간이 끝날 때까지 이용하실 수 있습니다."
    ]
  },
  "en": {
    "lead": "Refunds are returned to your original payment method within 3 business days of your refund request.",
    "steps": [
      "If you request a refund within 7 days of the billing date (including renewal billing dates), we refund the amount paid minus the usage charge for the days you have used. If you have not opened the paid sections of any report since payment, we refund the full amount.",
      "If you request a refund more than 7 days after the billing date, we refund the amount paid minus the usage charge for the days you have used and 10% of the amount paid (a cancellation fee). If the result is zero or less, no refund is due and nothing further is charged."
    ],
    "notes": [
      "Usage charge = amount paid ÷ number of days in the billing period × days used (from the start of the billing period to the day of your refund request). Amounts below KRW 1 are rounded in your favor.",
      "Example (30-day billing period): a request on day 3 is refunded KRW 13,410; a request on day 10 is refunded KRW 8,444.",
      "There is no minimum term. You can cancel at any time under Subscription in Settings. Once you cancel, you will not be charged from the next billing date, and you keep access until the end of the period you have already paid for."
    ]
  }
}/*@/json*/;
