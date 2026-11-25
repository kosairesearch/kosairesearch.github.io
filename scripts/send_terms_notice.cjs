/* 약관 개정 개별 통지 메일 — 2027년 1월 1일 시행 유료 시행안 (2026-11-25)
   ------------------------------------------------------------
   이용약관 제3조 — 회원에게 불리하거나 중대한 변경은 적용일 30일 전부터 공지하고 전자우편으로 개별 통지한다. 유료 전환은 그
   변경이라, 시행일 30일 전(2026년 12월 2일)까지 이메일이 있는 회원 전원에게 보낸다. 사장 승인 뒤 사람이 돌린다.

   Actions → 📮 약관 개정 통지 메일(terms_notice_mail.yml)이 돌린다. 예약을 걸지 말 것.
   함수 파일(functions/index.js)을 그대로 불러 그 안의 통지 도구(kosTools.termsNotice — runTermsNotice)를 부른다 — 대상 ·
   글 · 같은 회원에게 두 번 보내지 않는 장치가 서버 코드 하나에 있다.

     MODE=count    보낼 대상 수만 센다(아무것도 쓰지 않는다)
     MODE=sample   관리자 주소(hello@kosai.kr)로 한 통 — 제목 앞 [시험] · NOTICE_LANG=ko|en
     MODE=send     전원. CONFIRM=보내기 가 있어야 보낸다. 한 번에 LIMIT 통까지(기본 100) — 나머지는 다시 돌리면 이어서 보낸다
                   NOTICE_GAP_MS 로 한 통마다 쉬는 시간을 바꿀 수 있다(기본 600ms)

   찍는 것 — 숫자와 사정뿐이다(메일 주소 · 회원 번호 · 카드번호 없음). 오류 글에 주소나 문서 경로가 섞여 오면 가리고 찍는다.
   그 숫자(회원 수 · 보낸 수)도 마케팅 숫자라, 작업 파일은 이 출력을 파일로 받아 공개 열쇠로 잠가서만 찍는다(scripts/marketing_seal.py ·
   CLAUDE.md '마케팅 숫자 — 공개 실행 기록에 찍지 않는다'). 이 스크립트를 공개 기록에 그대로 찍는 단계로 돌리지 말 것.

   서비스 계정(GOOGLE_APPLICATION_CREDENTIALS)이 있어야 하고, sample · send 는 RESEND_API_KEY 가 있어야 한다.
     MODE=count node scripts/send_terms_notice.cjs
   끝 코드 — 0 정상 · 1 실패(보내지 못한 메일이 있거나 한도 · 열쇠 문제로 멈춤) · 2 입력이 틀려 아무것도 하지 않음
   ============================================================ */
const path = require("path");

const FN = path.join(__dirname, "..", "functions");
const MODES = ["count", "sample", "send"];
const CONFIRM_WORD = "보내기";

/* 오류 글에서 주소 · 문서 경로(회원 번호가 든다)를 가린다 — 잠가서 찍더라도 사정 설명에 개인정보를 싣지 않는다. */
function clean(s) {
  return String(s == null ? "" : s)
    .replace(/[^\s@<>"'`()[\]{},;:]+@[^\s@<>"'`()[\]{},;:]+/g, "(주소)")
    .replace(/\b(users|subscriptions|termsNotices|consentEvents|payments|report_reads|billingMails|watchlists)\/[^\s"'`)\]},;]+/g, "$1/(번호)")
    .replace(/\s+/g, " ")
    .slice(0, 300);
}

const n = (x) => Number(x || 0).toLocaleString("ko-KR");

const STOPPED = {
  limit: "한 번 상한에 닿았다 — 다시 돌리면 남은 회원에게 이어서 보낸다",
  quota: "메일 서비스의 발송 한도(하루 · 월)에 걸렸다 — 한도가 풀린 뒤 다시 돌린다",
  auth: "메일 서비스가 열쇠 · 보내는 주소를 받지 않았다 — RESEND_API_KEY 와 보내는 도메인 인증을 확인한다",
  errors: "잇달아 다섯 번 실패했다 — 메일 서비스 상태를 확인한 뒤 다시 돌린다",
};

async function main({ env = process.env, out = (s) => console.log(s), fns = null } = {}) {
  const mode = String(env.MODE || "count").trim();
  if (!MODES.includes(mode)) {
    out(`모르는 방식이다 — count · sample · send 중 하나. 아무것도 하지 않았다.`);
    return 2;
  }
  if (mode === "send" && String(env.CONFIRM || "").trim() !== CONFIRM_WORD) {
    out(`send 는 확인 문구(CONFIRM=${CONFIRM_WORD})가 있어야 보낸다. 아무것도 보내지 않았다.`);
    return 2;
  }
  const rawLimit = String(env.LIMIT || "").trim();
  const limit = rawLimit ? Number(rawLimit) : undefined;
  if (rawLimit && !(Number.isInteger(limit) && limit > 0 && limit <= 5000)) {
    out("LIMIT 은 1 ~ 5,000 사이의 정수여야 한다. 아무것도 하지 않았다.");
    return 2;
  }
  const rawGap = String(env.NOTICE_GAP_MS || "").trim();
  const gapMs = rawGap ? Number(rawGap) : undefined;
  if (rawGap && !(Number.isFinite(gapMs) && gapMs >= 0)) {
    out("NOTICE_GAP_MS 는 0 이상의 수여야 한다. 아무것도 하지 않았다.");
    return 2;
  }
  const lang = env.NOTICE_LANG === "en" ? "en" : "ko";

  let tools;
  try {
    // 함수 파일과 같은 관리자 SDK(functions/node_modules)를 쓴다 — 함수 파일이 불러질 때 initializeApp() 을 한다.
    const mod = fns || require(path.join(FN, "index.js"));
    tools = mod && mod.kosTools && mod.kosTools.termsNotice;
  } catch (e) {
    out(`함수 파일을 불러오지 못했다 — ${clean((e && (e.code || e.name)) || "error")} ${clean(e && e.message)}`);
    return 1;
  }
  if (!tools || typeof tools.run !== "function") {
    out("함수 파일에 통지 도구(kosTools.termsNotice)가 없다.");
    return 1;
  }

  let r;
  try {
    r = await tools.run({ mode, lang, ...(limit ? { limit } : {}), ...(gapMs !== undefined ? { gapMs } : {}) });
  } catch (e) {
    out(`실패 — ${clean((e && (e.code || e.name)) || "error")} ${clean(e && e.message)}`);
    return 1;
  }

  if (mode === "sample") {
    if (r && r.sent === 1) {
      out(`시험 메일을 관리자 주소로 보냈다(${lang === "en" ? "영어" : "한국어"} · 제목 앞 [시험]).`);
      return 0;
    }
    out(`시험 메일을 보내지 못했다 — ${clean((r && r.error) || "알 수 없음")}`);
    return 1;
  }

  out(`약관 개정 개별 통지 — ${mode === "count" ? "대상 확인" : "발송"}`);
  out(`약관 판 ${r.version} · 통지를 시작해야 하는 날 ${r.deadline}(시행일 30일 전)`);
  out(`보낼 주소 ${n(r.addresses)}곳(이메일이 있는 회원 계정 ${n(r.members)}개 — 같은 주소를 쓰는 계정에는 한 통)`);
  out(`  이메일 인증됨 ${n(r.verified)}곳 · 미인증 ${n(r.unverified)}곳`);
  out(`  영어로 받음 ${n(r.en)}곳 · 한국어로 받음 ${n(r.ko)}곳`);
  out(`제외 — 비활성 계정 ${n(r.disabled)}개 · 주소가 없는 계정 ${n(r.noEmail)}개`);
  if (mode === "count") {
    out(`이미 보냄 ${n(r.alreadySent)}곳 · 남음 ${n(r.remaining)}곳`);
    return 0;
  }
  out(`이번 실행 — 보냄 ${n(r.sent)}통 · 실패 ${n(r.failed)}통(그중 답을 받지 못한 것 ${n(r.unsure)}통)`);
  out(`  다른 실행이 처리 중이라 건너뜀 ${n(r.busy)}곳 · 그 사이 다른 실행이 보냄 ${n(r.raced)}곳 · 같은 주소로 이미 보내 기록만 남김 ${n(r.shared)}곳`);
  if (r.logMiss) out(`  동의 이력(consentEvents)을 남기지 못한 계정 ${n(r.logMiss)}개 — 발송 기록(termsNotices)에는 남았다`);
  out(`남음 ${n(r.remaining)}곳 · 한 번 상한 ${n(r.limit)}통`);
  out(r.stoppedBy ? `멈춘 까닭 — ${STOPPED[r.stoppedBy] || clean(r.stoppedBy)}` : "대상 끝까지 돌았다.");
  return r.failed === 0 && (!r.stoppedBy || r.stoppedBy === "limit") ? 0 : 1;
}

module.exports = { main, clean, CONFIRM_WORD };

if (require.main === module) {
  main().then((code) => process.exit(code), (e) => {
    console.log(`실패 — ${clean((e && (e.code || e.name)) || "error")}`);
    process.exit(1);
  });
}
