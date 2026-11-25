/* ============================================================
   결제 · 환불 안내 메일 · 결제 화면 동의 기록 · 결제 수단 정보 삭제 · 열람 기록 1년 파기 (2026-11-25)

   유료 시행안 약관(2027-01-01 시행 · 금융감독원에 낸 신고 서류의 이용약관) 제9조 · 제11조와 개인정보 처리방침
   유료판이 약속한 것이 서버에 있는지 진짜 함수(lib/paid-harness.mjs)로 본다.

     ① 환불 안내 글 — 서버 사본(REFUND_NOTICE)이 결제 화면의 원본(staging/payment-config.js)과 글자 하나까지 같다
     ② 메일 글 — 여섯 가지(구독 시작 · 정기결제 · 재시도 성공 · 환불 · 승인 실패 · 종료) × 한국어 · 영어의 제목 · 첫머리 ·
        표 · 해지 · 청약철회와 환불 · 약관 링크 · 단추 · 사업자 · 법정 표시. 광고가 아니라 수신거부 줄이 없다
     ③ 첫 결제(confirmBilling) — 계약 내용 안내 메일 · 동의 기록(구독 문서와 첫 결제 기록) · 말 기록
     ④ 메일이 실패해도 결제는 끝난다 — 거절 · 통신 오류 · 시간 초과. 기록(로그)에 주소 · 회원 번호 · 카드번호가 없다
     ⑤ 카드 변경 — 이용 중이면 메일 · 동의 기록 없음, 결제가 밀린 구독이면 재시도 성공 안내
     ⑥ 갱신 배치 — 정기결제 완료 · 첫 거절 · 재시도 성공 · 네 번 실패 뒤 종료, 해지 예약 · 계정 없음
     ⑦ 환불 · 해지 · 탈퇴 — 환불 안내(즉시 / 자정까지 / 위약금 / 탈퇴), 결제 수단 정보를 지우는 때와 지우지 않는 때
     ⑧ 열람 기록 1년 파기 — 기준일 · 상한 · 묶음 크기 · 매일 도는 예약 함수에 들어 있음 · 실패해도 던지지 않음

   실행
     node functions/tests/billing-mail.test.mjs
     FN_INDEX=<고치기 전 functions/index.js> node functions/tests/billing-mail.test.mjs   # 고치기 전이면 걸리는지
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

/* 메일 서비스가 답하지 않는 경우를 짧게 본다 — 함수 파일이 불러질 때 읽으므로 시험 도구를 부르기 전에 둔다. */
process.env.KOSAI_MAIL_TIMEOUT_MS = "80";
const H = await import("./lib/paid-harness.mjs");
const {
  clock, call, runJob, reset, seedSub, seedReads, seedReports, sub, store, S, payments, failToss, fns, SRC,
  indexNeeds, ok, eq, section, done, DAY, HOUR, MIN, UID, ts, kstDay,
} = H;

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const T = fns.kosTools || {};
/* 함수 파일이 쓰는 가짜 파이어스토어 — 시험 도구가 관리자 SDK 자리에 끼운 그것을 받는다 */
const DB = createRequire(import.meta.url)("firebase-admin").firestore();
const MAIL = "member@example.com";

const unesc = (s) => String(s).replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
const rows = (html) => [...String(html).matchAll(/<tr><td[^>]*>([^<]*)<\/td><td[^>]*>([^<]*)<\/td><\/tr>/g)]
  .map((m) => [unesc(m[1]), unesc(m[2])]);
const row = (html, k) => (rows(html).find(([a]) => a === k) || [])[1];
const texts = (html) => [...String(html).matchAll(/<(p|li|h1|h2)\b[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => unesc(m[2].replace(/<br>/g, "\n").replace(/<[^>]+>/g, "")));
const hasText = (html, t) => texts(html).some((x) => x.includes(t));
const memberMails = (to = MAIL) => S.mails.filter((m) => m.to === to);
const lastMail = (to = MAIL) => memberMails(to).slice(-1)[0] || { subject: "", html: "" };
const mailRecs = () => [...store.entries()].filter(([p]) => p.startsWith("billingMails/")).map(([, v]) => v);
const mail = (kind, lang, d) => {
  try { return T.billingMail(kind, lang, d); } catch (e) { return { subject: "", html: "", error: e.message }; }
};
const HANGUL = /[가-힣]/;

/* 로그를 받아 둔다 — 시험 도구의 call 은 기록을 버리므로, 기록에 무엇이 찍히는지 볼 때 쓴다. */
async function loud(fn) {
  const lines = [];
  const keep = { log: console.log, warn: console.warn, error: console.error };
  console.log = console.warn = console.error = (...a) => lines.push(a.map(String).join(" "));
  try { return { r: await fn(), lines }; } finally { Object.assign(console, keep); }
}
async function callLoud(name, data = {}) {
  return loud(async () => {
    try { return { data: await fns[name]({ data, auth: { uid: UID, token: {} }, rawRequest: { headers: {} } }) }; }
    catch (e) { return { error: { code: e.code, message: e.message } }; }
  });
}
const leaks = (lines) => lines.filter((l) => l.includes(MAIL) || l.includes(UID + " ") || l.endsWith(UID) ||
  l.includes("uid=" + UID) || l.includes("4330****1234"));

/* 한국 시간 2026년 11월 2일 14시 */
const START = Date.parse("2026-11-02T05:00:00Z");
const day = (n, startMs = START) => startMs + (n - 1) * DAY;
function begin({ startMs = START, email = MAIL, viewed = false, ...rest } = {}) {
  reset();
  clock.set(startMs);
  seedSub({ startMs, ...rest });
  if (email) S.emails.set(UID, email);
  seedReports(["005930"]);
  if (viewed) seedReads(startMs + HOUR, ["005930"]);
}

/* ── ① ── */
section("① 환불 안내 글 — 서버 사본 = 결제 화면의 원본(staging/payment-config.js)");
{
  const cfg = readFileSync(join(ROOT, "staging/payment-config.js"), "utf8");
  const pick = (src, re) => { const m = re.exec(src); try { return m && JSON.parse(m[1]); } catch (e) { return null; } };
  const web = pick(cfg, /export const REFUND_NOTICE = \/\*@json\*\/([\s\S]*?)\/\*@\/json\*\//);
  const srv = pick(SRC, /const REFUND_NOTICE = \/\*@json\*\/([\s\S]*?)\/\*@\/json\*\//);
  ok("두 파일에서 환불 안내 글을 읽는다", !!web && !!srv);
  eq("한국어 · 영어 모두 글자 하나까지 같다", srv, web);
  eq("메일이 쓰는 값도 같다(kosTools.refundNotice)", T.refundNotice, web);
}

/* ── ② ── */
section("② 메일 글 — 구독 시작(계약 내용 안내)");
const PAID = { amount: 14900, paidAt: START, start: START, end: Date.parse("2026-12-02T05:00:00Z"),
               card: { company: "11", number: "4330****1234" } };
{
  const m = mail("new", "ko", PAID);
  eq("제목", m.subject, "[KOSAI] 멤버십 결제 완료 및 계약 내용 안내");
  ok("첫머리 — 감사 · 결제 내용과 계약 내용 · 전자상거래법 · 보관", hasText(m.html,
    "KOSAI 멤버십을 구독해 주셔서 감사합니다. 결제 내용과 계약 내용을 안내드립니다. 이 메일은 「전자상거래 등에서의 소비자보호에 관한 법률」에 따른 계약 내용 안내이므로 보관하여 주시기 바랍니다."));
  eq("표 — 상품 · 결제 금액 · 결제 일시 · 이용 기간 · 다음 결제일 · 결제 수단", rows(m.html), [
    ["상품", "KOSAI 멤버십 월 구독"],
    ["결제 금액", "14,900원(부가가치세 포함)"],
    ["결제 일시", "2026년 11월 2일 14:00"],
    ["이용 기간", "2026년 11월 2일 14:00 ~ 2026년 12월 2일 14:00"],
    ["다음 결제일", "2026년 12월 2일(해지 전까지 매월 같은 날 자동 결제)"],
    ["결제 수단", "KB국민카드 4330****1234"],
  ]);
  ok("해지 — 설정의 구독 항목 · 다음 결제일부터 청구 안 됨 · 기간 끝까지 이용",
     hasText(m.html, "해지는 설정 화면의 구독 항목에서 언제든지 하실 수 있습니다. 해지하시면 다음 결제일부터 이용료가 청구되지 않으며, 이미 결제하신 이용 기간이 끝날 때까지 이용하실 수 있습니다."));
  const N = T.refundNotice ? T.refundNotice.ko : { lead: "?", steps: ["?"], notes: ["?"] };
  ok("청약철회와 환불 — 제목", hasText(m.html, "청약철회와 환불"));
  ok("  안내 첫 줄(lead) 그대로", hasText(m.html, N.lead));
  ok("  계산 단계(steps) 그대로", N.steps.every((s) => hasText(m.html, s)));
  ok("  참고(notes) 그대로", N.notes.every((s) => hasText(m.html, s)));
  ok("이용약관 링크", m.html.includes('href="https://kosai.kr/Terms.html"'));
  ok("단추 '구독 관리' → 설정의 구독 항목",
     m.html.includes('href="https://kosai.kr/Settings.html?tab=subscription"') && m.html.includes(">구독 관리</a>"));
  ok("사업자 표시", m.html.includes("상호 코사이 · 대표 임범준 · 사업자등록번호 380-25-02019 · 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호 · hello@kosai.kr"));
  ok("법정 표시 두 문장(자본시장법 제101조의3)",
     m.html.includes("KOSAI는 금융투자업자가 아닌 유사투자자문업자로, 개별적인 투자상담과 자금운용을 하지 않습니다.") &&
     m.html.includes("투자에는 원금 손실이 발생할 수 있으며, 그 손실은 투자자에게 귀속됩니다."));
  ok("거래 안내라 수신거부 줄이 없고 광고가 아니라고 밝힌다",
     !/수신거부|unsubscribe/i.test(m.html) && hasText(m.html, "광고성 정보가 아니며"));
  const empty = ["MAIL_ORDER_NO", "ADVISORY_NO", "BIZ_PHONE"].every((k) => new RegExp(`^const ${k} = "";`, "m").test(SRC));
  if (empty) ok("아직 없는 신고번호 · 대표전화 줄은 싣지 않는다", !/통신판매업 신고|유사투자자문업 신고 |대표전화/.test(m.html));
}
{
  const m = mail("new", "en", PAID);
  eq("영어 제목", m.subject, "[KOSAI] Membership payment confirmed: your contract details");
  eq("영어 표", rows(m.html), [
    ["Product", "KOSAI Membership (monthly subscription)"],
    ["Amount paid", "KRW 14,900 (VAT included)"],
    ["Paid at", "Nov 2, 2026 14:00 KST"],
    ["Billing period", "Nov 2, 2026 14:00 KST to Dec 2, 2026 14:00 KST"],
    ["Next billing date", "Dec 2, 2026 (charged automatically on the same day each month until you cancel)"],
    ["Payment method", "KB Kookmin Card 4330****1234"],
  ]);
  const N = T.refundNotice ? T.refundNotice.en : { lead: "?", steps: ["?"], notes: ["?"] };
  ok("영어 환불 안내 그대로", hasText(m.html, N.lead) && N.steps.every((s) => hasText(m.html, s)) && N.notes.every((s) => hasText(m.html, s)));
  ok("영어 단추 · 약관 · 사업자 · 법정 표시", m.html.includes(">Manage subscription</a>") &&
     m.html.includes("Terms of Service: ") && m.html.includes("Company KOSAI · CEO Beomjun Lim") &&
     m.html.includes("is borne by the investor"));
  ok("영어 메일에는 한글이 없다", !HANGUL.test(m.html), (m.html.match(/.{20}[가-힣].{20}/) || [""])[0]);
  ok("영어 메일은 lang=en", m.html.includes('<html lang="en">'));
}

section("② 메일 글 — 정기결제 · 재시도 성공");
{
  const r = mail("renew", "ko", PAID);
  eq("정기결제 제목", r.subject, "[KOSAI] 멤버십 정기결제 완료 안내");
  ok("정기결제 첫머리", hasText(r.html, "KOSAI 멤버십 이용료가 정기결제로 결제되었습니다."));
  eq("같은 표", rows(r.html).map(([k]) => k), ["상품", "결제 금액", "결제 일시", "이용 기간", "다음 결제일", "결제 수단"]);
  ok("7일 환불 한 줄", hasText(r.html, "결제일부터 7일 이내에 환불을 신청하시면 이용하신 날의 이용료만 빼고 환불합니다(유료 영역을 열람하지 않으셨다면 전액)."));
  ok("해지 · 약관 링크 · 사업자 표시", hasText(r.html, "해지") && r.html.includes("https://kosai.kr/Terms.html") && r.html.includes("380-25-02019"));
  const v = mail("revive", "ko", PAID);
  eq("재시도 성공 제목은 정기결제와 같다", v.subject, "[KOSAI] 멤버십 정기결제 완료 안내");
  ok("재시도 성공 첫머리", hasText(v.html, "승인되지 않았던 이용료가 결제되어 이용이 다시 시작되었습니다. 이용 기간은 이번 결제일부터 다시 계산합니다."));
  ok("재시도 성공에도 7일 환불 한 줄", hasText(v.html, "결제일부터 7일 이내에 환불을 신청하시면"));
  const ve = mail("revive", "en", PAID);
  ok("영어 재시도 성공 — 한글 없음 · 첫머리", !HANGUL.test(ve.html) && hasText(ve.html, "has now been paid, and your access has resumed"));
}

section("② 메일 글 — 환불");
const Q = (o) => ({ amount: 13410, price: 14900, fee: 1490, penalty: 0, usedDays: 3, totalDays: 30, why: "early",
                    chargedToday: true, requestedAt: day(3), endsAt: Date.parse("2026-11-04T15:00:00Z"),
                    card: { company: "11", number: "4330****1234" }, withdrawal: false, ...o });
{
  const m = mail("refund", "ko", Q());
  eq("제목", m.subject, "[KOSAI] 환불 처리 안내");
  eq("표 — 7일 이내 · 열람 있음(이용일수를 뺀 환불)", rows(m.html), [
    ["환불 금액", "13,410원"],
    ["결제 금액", "14,900원"],
    ["이용한 날의 이용료", "1,490원(이용일수 3일 / 기간 30일)"],
    ["신청일", "2026년 11월 4일"],
    ["환불 수단", "결제하신 카드(KB국민카드 4330****1234)의 결제를 취소하였습니다. 카드사에 따라 취소 내역이 반영되기까지 며칠이 걸릴 수 있습니다."],
    ["이용 종료", "2026년 11월 4일 24:00(자정)까지 이용하실 수 있습니다"],
  ]);
  ok("단추 '구독 관리'가 있다", m.html.includes(">구독 관리</a>"));
  const late = mail("refund", "ko", Q({ amount: 6965, fee: 6445, penalty: 1490, usedDays: 13, why: "late", requestedAt: day(13) }));
  eq("7일이 지난 환불 — 위약금 줄", row(late.html, "위약금"), "1,490원(결제금액의 10%)");
  ok("위약금이 없으면 그 줄이 없다", row(m.html, "위약금") === undefined);
  const wd = mail("refund", "ko", Q({ amount: 14900, fee: 0, why: "withdraw", chargedToday: false, requestedAt: day(2), endsAt: day(2) }));
  eq("청약철회(전액) — 이용료 0원 · 즉시 종료", [row(wd.html, "이용한 날의 이용료"), row(wd.html, "이용 종료")],
     ["0원(결제 후 유료 영역을 열람하지 않으셔서 전액 환불)", "즉시 종료되었습니다(2026년 11월 3일 14:00)"]);
  const quit = mail("refund", "ko", Q({ amount: 14900, fee: 0, why: "withdraw", chargedToday: false, withdrawal: true }));
  ok("회원 탈퇴 환불 — 탈퇴 안내 · 누를 단추 없음 · 이용 종료",
     hasText(quit.html, "회원 탈퇴 신청에 따라 멤버십 이용료를 환불하였습니다.") && !quit.html.includes("Settings.html") &&
     row(quit.html, "이용 종료") === "회원 탈퇴와 함께 즉시 종료되었습니다");
  const en = mail("refund", "en", Q());
  ok("영어 환불 — 한글 없음 · 자정까지", !HANGUL.test(en.html) && row(en.html, "Access ends") === "You keep access until 24:00 (midnight) KST on Nov 4, 2026");
}

section("② 메일 글 — 승인 실패 · 종료");
{
  const failedAt = Date.parse("2026-11-10T02:00:00Z");   // 한국 시간 11월 10일 11시(갱신 배치)
  const f = mail("fail", "ko", { amount: 14900, failedAt, card: { company: "41", number: "5310****9999" } });
  eq("승인 실패 제목", f.subject, "[KOSAI] 정기결제 승인 실패 안내");
  ok("첫머리", hasText(f.html, "등록하신 카드로 멤버십 이용료가 승인되지 않아 유료 영역 이용이 일시 중지되었습니다."));
  eq("다시 시도하는 날 — 최초 거절일부터 1 · 3 · 5 · 7일이 되는 날(약관 제9조 · 재시도 배치와 같은 날)", row(f.html, "다시 시도하는 날"),
     "2026년 11월 11일, 2026년 11월 13일, 2026년 11월 15일, 2026년 11월 17일(최초 승인 거절일부터 1일, 3일, 5일, 7일이 되는 날 — 이용약관 제9조)");
  eq("결제 수단(신한카드)", row(f.html, "결제 수단"), "신한카드 5310****9999");
  ok("결제 수단 변경 방법 — 구독 관리에서 카드 변경 · 바로 결제되어 이용 재개",
     hasText(f.html, "'구독 관리'에서 카드를 변경하여 주시기 바랍니다. 새로 등록하신 카드로 바로 결제되어 이용이 다시 시작되며"));
  ok("별도 청구 없음", hasText(f.html, "네 번 모두 승인되지 않으면 구독이 종료되며, 별도로 청구되는 금액은 없습니다."));
  const e = mail("end", "ko", { endedAt: failedAt + 7 * DAY });
  eq("종료 제목", e.subject, "[KOSAI] 멤버십 종료 안내");
  ok("종료 첫머리", hasText(e.html, "네 번의 재시도가 모두 승인되지 않아 구독이 종료되었습니다. 추가로 청구되는 금액은 없습니다. 다시 이용하시려면 구독을 새로 신청하여 주시기 바랍니다."));
  ok("종료 — 결제 수단 정보 삭제를 알린다", hasText(e.html, "빌링키와 카드 정보"));
  const fe = mail("fail", "en", { amount: 14900, failedAt, card: { company: "41", number: "5310****9999" } });
  ok("영어 승인 실패 — 한글 없음 · 재시도 날짜", !HANGUL.test(fe.html) &&
     row(fe.html, "Retry dates") === "Nov 11, 2026; Nov 13, 2026; Nov 15, 2026; Nov 17, 2026 (1, 3, 5 and 7 days after the first decline)");
  ok("영어 종료 — 한글 없음", !HANGUL.test(mail("end", "en", { endedAt: failedAt }).html));
}

section("② 메일 글 — 카드 표시 · 글자 가리기");
{
  const unknown = mail("new", "ko", { ...PAID, card: { company: "Z9", number: "1111****2222" } });
  eq("모르는 카드사 코드는 '카드'", row(unknown.html, "결제 수단"), "카드 1111****2222");
  const named = mail("new", "en", { ...PAID, card: { company: "현대카드", number: "" } });
  eq("코드가 아닌 이름은 그대로(영어 메일에도 — 카드사가 준 이름)", row(named.html, "Payment method"), "현대카드");
  const none = mail("new", "ko", { ...PAID, card: null });
  ok("카드 정보가 없으면 결제 수단 줄이 없다", row(none.html, "결제 수단") === undefined);
  const evil = mail("new", "ko", { ...PAID, card: { company: "11", number: '<img src=x onerror="a">' } });
  ok("카드 번호의 꺾쇠는 글자로 바뀐다", !evil.html.includes("<img src=x") && evil.html.includes("&lt;img"));
  let threw = false;
  try { T.billingMail("bogus", "ko", {}); } catch (e) { threw = true; }
  ok("모르는 종류는 만들지 않는다", threw);
}

/* ── ③ ── */
section("③ 첫 결제 — 계약 내용 안내 · 동의 기록 · 말");
const ALL = ["terms", "privacy", "recurring", "refund", "age"];
async function firstPay(data = {}, { email = MAIL } = {}) {
  reset();
  clock.set(START);
  S.users.add(UID);
  if (email) S.emails.set(UID, email);
  return call("confirmBilling", { authKey: "auth_1", customerKey: UID, plan: "member", ...data });
}
{
  const r = await firstPay({ agreed: [...ALL, "bogus"], adultConfirmed: true, lang: "ko" });
  ok("결제가 끝난다", r.data && r.data.ok, JSON.stringify(r.error));
  eq("회원 주소로 한 통", memberMails().map((m) => m.subject), ["[KOSAI] 멤버십 결제 완료 및 계약 내용 안내"]);
  const m = lastMail();
  eq("보내는 주소", m.from, "KOSAI <hello@kosai.kr>");
  eq("메일의 결제 일시 · 이용 기간 · 다음 결제일은 실제 구독과 같다",
     [row(m.html, "결제 일시"), row(m.html, "이용 기간"), row(m.html, "다음 결제일"), row(m.html, "결제 수단")],
     ["2026년 11월 2일 14:00", "2026년 11월 2일 14:00 ~ 2026년 12월 2일 14:00",
      "2026년 12월 2일(해지 전까지 매월 같은 날 자동 결제)", "KB국민카드 4330****1234"]);
  const s = sub() || {};
  const c = s.consent || {};
  eq("구독 문서의 동의 기록 — 판 · 항목(모르는 항목은 버림) · 연령 확인", [c.version, c.items, c.adultConfirmed],
     ["2027-01-01", ALL, true]);
  ok("  동의 시각은 서버 시각", c.at && c.at.toMillis && c.at.toMillis() === START);
  const p = payments()[0] || {};
  eq("첫 결제 기록(5년 보관)에도 같은 동의 기록", [p.consent && p.consent.version, p.consent && p.consent.items,
     p.consent && p.consent.adultConfirmed], ["2027-01-01", ALL, true]);
  eq("회원의 메일 말을 구독 문서에 적는다", s.mailLang, "ko");
  const rec = mailRecs();
  eq("보낸 기록(billingMails) — 종류 · 성공", rec.map((x) => [x.uid, x.kind, x.ok, x.error]), [[UID, "new", true, null]]);
  ok("  보낸 기록에 주소가 없다", rec.every((x) => !JSON.stringify(x).includes("@")));
}
{
  await firstPay({ agreed: ALL, adultConfirmed: true, lang: "en" });
  eq("영어 결제 화면 → 영어 계약 내용 안내", lastMail().subject, "[KOSAI] Membership payment confirmed: your contract details");
  eq("  구독 문서의 말 en", (sub() || {}).mailLang, "en");
}
{
  await firstPay({});
  const c = (sub() || {}).consent || {};
  eq("항목을 보내지 않은 옛 화면 — 받지 않은 동의를 적지 않는다", [c.version, c.items, c.adultConfirmed], ["2027-01-01", [], false]);
  eq("  말을 모르면 한국어", (sub() || {}).mailLang, "ko");
  eq("  안내 메일은 보낸다", memberMails().length, 1);
}
{
  reset(); clock.set(START); S.users.add(UID);
  store.set(`users/${UID}`, { email: "Old.Member@Example.com" });
  await call("confirmBilling", { authKey: "auth_1", customerKey: UID, plan: "member" });
  eq("계정에 주소가 없는 옛 회원 — 회원 문서의 주소로", S.mails.map((m) => m.to), ["old.member@example.com"]);
}
{
  const r = await firstPay({}, { email: null });
  ok("주소가 없으면 메일 없이 결제만 끝난다", r.data && r.data.ok && S.mails.length === 0);
  eq("  기록에 '주소 없음'", mailRecs().map((x) => [x.kind, x.ok, x.error]), [["new", false, "no-email"]]);
}

/* ── ④ ── */
section("④ 메일이 실패해도 결제는 끝난다 — 기록에 주소 · 회원 번호 · 카드번호 없음");
for (const [name, fail, want] of [
  ["메일 서비스가 거절", async () => ({ data: null, error: { name: "validation_error", message: `잘못된 주소 ${MAIL}` } }), "validation_error"],
  ["통신 오류(던짐)", async () => { throw Object.assign(new Error(`connect ECONNRESET ${MAIL}`), { name: "FetchError" }); }, "FetchError"],
  ["답이 없음(시간 초과)", () => new Promise(() => {}), "timeout"],
]) {
  reset(); clock.set(START); S.users.add(UID); S.emails.set(UID, MAIL);
  S.mailFail = fail;
  const t0 = Date.now();
  const { r, lines } = await callLoud("confirmBilling", { authKey: "auth_1", customerKey: UID, plan: "member" });
  ok(`${name} — 결제 성공으로 돌려준다`, r.data && r.data.ok && (sub() || {}).status === "active", JSON.stringify(r.error));
  eq(`  보낸 기록의 오류 이름`, mailRecs().map((x) => [x.ok, x.error]), [[false, want]]);
  ok(`  기록(로그)에 주소 · 회원 번호 · 카드번호가 없다`, leaks(lines).length === 0, leaks(lines).join(" / "));
  if (want === "timeout") ok("  기다림에 상한이 있다(KOSAI_MAIL_TIMEOUT_MS)", Date.now() - t0 < 5000, `${Date.now() - t0}ms`);
}

/* ── ⑤ ── */
section("⑤ 카드 변경 — 이용 중이면 안내 없음 · 결제가 밀린 구독은 재시도 성공 안내");
{
  begin();
  const before = payments().length;
  const r = await call("confirmBilling", { updateMethod: true, authKey: "auth_2", customerKey: UID, lang: "en" });
  ok("카드만 바꾼다", r.data && r.data.updated, JSON.stringify(r.error));
  eq("  결제 · 메일 없음", [payments().length - before, memberMails().length], [0, 0]);
  ok("  동의 기록을 남기지 않는다(카드 변경은 계약이 아니다)", !("consent" in (sub() || {})));
  eq("  그 화면의 말을 적는다(다음 안내 메일의 말)", (sub() || {}).mailLang, "en");
}
{
  begin({ status: "past_due", failedAt: ts(START - 2 * DAY), retryCount: 1, endMs: START - 3 * DAY });
  const r = await call("confirmBilling", { updateMethod: true, authKey: "auth_2", customerKey: UID });
  ok("밀린 구독을 새 카드로 되살린다", r.data && (sub() || {}).status === "active", JSON.stringify(r.error));
  eq("  재시도 성공 안내", memberMails().map((m) => m.subject), ["[KOSAI] 멤버십 정기결제 완료 안내"]);
  ok("  첫머리 — 이용이 다시 시작 · 이용 기간을 다시 계산", hasText(lastMail().html, "승인되지 않았던 이용료가 결제되어 이용이 다시 시작되었습니다."));
  eq("  메일의 이용 기간 = 새 구독 기간", row(lastMail().html, "이용 기간"), "2026년 11월 2일 14:00 ~ 2026년 12월 2일 14:00");
  ok("  결제 기록에 동의 칸을 만들지 않는다", payments().every((p) => !("consent" in p)));
}

/* ── ⑥ ── */
section("⑥ 갱신 배치 — 정기결제 · 첫 거절 · 재시도 성공 · 종료");
const BATCH = Date.parse("2026-11-10T02:00:00Z");
function due(over = {}) { begin({ startMs: BATCH - 30 * DAY, endMs: BATCH - 1000, ...over }); clock.set(BATCH); }
{
  due({ mailLang: "en" });
  const r = await runJob("renewSubscriptions");
  ok("배치가 끝난다", !r.error, JSON.stringify(r.error));
  eq("정기결제 완료 — 회원이 고른 말(영어)로", memberMails().map((m) => m.subject), ["[KOSAI] Membership renewal payment confirmed"]);
  eq("  표의 금액 · 이용 기간", [row(lastMail().html, "Amount paid"), row(lastMail().html, "Billing period")],
     ["KRW 14,900 (VAT included)", "Nov 10, 2026 11:00 KST to Dec 10, 2026 11:00 KST"]);
}
{
  due();
  failToss(/^\/billing\/bk/);
  await runJob("renewSubscriptions");
  const s = sub() || {};
  eq("첫 거절 — 결제가 밀린 상태 · 결제 수단은 남긴다(되살릴 수 있다)", [s.status, !!s.billingKey, !!s.card], ["past_due", true, true]);
  eq("  승인 실패 안내 한 통", memberMails().map((m) => m.subject), ["[KOSAI] 정기결제 승인 실패 안내"]);
  eq("  다시 시도하는 날", row(lastMail().html, "다시 시도하는 날"),
     "2026년 11월 11일, 2026년 11월 13일, 2026년 11월 15일, 2026년 11월 17일(최초 승인 거절일부터 1일, 3일, 5일, 7일이 되는 날 — 이용약관 제9조)");
  /* 재시도도 실패 — 안내를 다시 보내지 않는다 */
  clock.set(BATCH + DAY);
  await runJob("renewSubscriptions");
  eq("  첫 재시도 실패에는 메일을 보내지 않는다", memberMails().length, 1);
}
{
  begin({ status: "past_due", failedAt: ts(BATCH - 7 * DAY), retryCount: 3, endMs: BATCH - 8 * DAY, startMs: BATCH - 38 * DAY });
  clock.set(BATCH);
  failToss(/^\/billing\/bk/);
  await runJob("renewSubscriptions");
  const s = sub() || {};
  eq("네 번째 재시도도 실패 — 종료 · 결제 수단 정보 삭제", [s.status, "billingKey" in s, "customerKey" in s, "card" in s],
     ["expired", false, false, false]);
  ok("  지운 시각을 남긴다(billingErasedAt)", s.billingErasedAt && s.billingErasedAt.toMillis() === BATCH);
  eq("  종료 안내", memberMails().map((m) => m.subject), ["[KOSAI] 멤버십 종료 안내"]);
}
{
  begin({ status: "past_due", failedAt: ts(BATCH - DAY), retryCount: 0, endMs: BATCH - 2 * DAY, startMs: BATCH - 32 * DAY });
  clock.set(BATCH);
  await runJob("renewSubscriptions");
  eq("재시도 성공 — 다시 이용 중 · 재시도 성공 안내", [(sub() || {}).status, memberMails().map((m) => m.subject)],
     ["active", ["[KOSAI] 멤버십 정기결제 완료 안내"]]);
  ok("  첫머리가 재시도 성공", hasText(lastMail().html, "승인되지 않았던 이용료가 결제되어"));
}
{
  due({ cancelAtPeriodEnd: true });
  await runJob("renewSubscriptions");
  const s = sub() || {};
  eq("해지 예약이 기간 끝에 닫히면 결제 수단 정보를 지운다", [s.status, "billingKey" in s, "card" in s], ["expired", false, false]);
  eq("  닫히는 날에는 메일이 없다(해지할 때 안내했다)", memberMails().length, 0);
}
{
  due();
  S.users.delete(UID);
  await runJob("renewSubscriptions");
  const s = sub() || {};
  eq("계정이 없어진 구독 — 긁지 않고 닫으며 결제 수단 정보를 지운다", [s.status, "billingKey" in s], ["deleted", false]);
}

/* ── ⑦ ── */
section("⑦ 환불 · 해지 · 탈퇴 — 환불 안내와 결제 수단 정보");
{
  begin();
  clock.set(day(2));
  const q = (await call("refundPreview")).data || {};
  const r = await call("requestRefund", { expectAmount: q.amount, lang: "ko" });
  ok("청약철회(전액) 환불", r.data && r.data.amount === 14900, JSON.stringify(r.error));
  const s = sub() || {};
  eq("  그 자리에서 끝나므로 결제 수단 정보를 지운다", ["billingKey" in s, "customerKey" in s, "card" in s, !!s.billingErasedAt],
     [false, false, false, true]);
  eq("  환불 안내", memberMails().map((m) => m.subject), ["[KOSAI] 환불 처리 안내"]);
  eq("  환불 금액 · 이용 종료(즉시 — refundEndsAt 과 같은 시각)", [row(lastMail().html, "환불 금액"), row(lastMail().html, "이용 종료")],
     ["14,900원", "즉시 종료되었습니다(2026년 11월 3일 14:00)"]);
  ok("  환불 수단에 지우기 전의 카드를 적는다", String(row(lastMail().html, "환불 수단") || "").includes("KB국민카드 4330****1234"));
}
{
  begin({ viewed: true });
  clock.set(day(3));
  const q = (await call("refundPreview")).data || {};
  await call("requestRefund", { expectAmount: q.amount });
  const s = sub() || {};
  eq("이용일수를 뺀 환불 — 오늘 자정까지 이용하므로 결제 수단 정보는 아직 남긴다", [!!s.billingKey, !!s.card], [true, true]);
  eq("  안내의 금액 · 이용료 · 이용 종료", [row(lastMail().html, "환불 금액"), row(lastMail().html, "이용한 날의 이용료"),
     row(lastMail().html, "이용 종료")], ["13,410원", "1,490원(이용일수 3일 / 기간 30일)", "2026년 11월 4일 24:00(자정)까지 이용하실 수 있습니다"]);
  eq("  메일의 자정 = 구독이 끝나는 시각", sub().currentPeriodEnd.toMillis(), Date.parse("2026-11-04T15:00:00Z"));
  clock.set(Date.parse("2026-11-05T02:00:00Z"));
  await runJob("renewSubscriptions");
  const t = sub() || {};
  eq("  다음 날 갱신 배치가 닫으며 지운다(카드는 긁지 않는다)", [t.status, "billingKey" in t, "card" in t, S.toss.filter((c) => /^\/billing\/bk/.test(c.path)).length],
     ["expired", false, false, 0]);
}
{
  begin({ viewed: true });
  clock.set(day(10));
  const q = (await call("refundPreview")).data || {};
  await call("requestRefund", { expectAmount: q.amount });
  eq("7일이 지난 환불 — 위약금 줄", row(lastMail().html, "위약금"), "1,490원(결제금액의 10%)");
}
{
  begin({ mailLang: "en" });
  clock.set(day(2));
  const q = (await call("refundPreview")).data || {};
  await call("requestRefund", { expectAmount: q.amount });
  eq("화면이 말을 보내지 않으면 구독 문서의 말(영어)로", lastMail().subject, "[KOSAI] Your refund has been processed");
}
{
  begin({ status: "past_due", failedAt: ts(START - DAY), retryCount: 1 });
  await call("cancelSubscription");
  const s = sub() || {};
  eq("결제가 밀린 구독의 해지 — 그 자리에서 끝나므로 지운다", [s.status, "billingKey" in s, "card" in s], ["expired", false, false]);
}
{
  begin();
  await call("cancelSubscription");
  const s = sub() || {};
  eq("이용 중 해지 예약 — 기간 끝까지 쓰고 해지 취소도 되므로 남긴다", [s.cancelAtPeriodEnd, !!s.billingKey, !!s.card], [true, true, true]);
}
{
  begin();
  store.set(`termsNotices/2027-01-01_${UID}`, { uid: UID, status: "sent" });
  clock.set(day(3));
  const r = await call("deleteAccount", { lang: "ko" });
  eq("회원 탈퇴 — 14,900원을 돌려주고 탈퇴", r.data && r.data.refunded, 14900);
  eq("  주소를 지우기 전에 환불 안내를 보낸다", memberMails().map((m) => m.subject), ["[KOSAI] 환불 처리 안내"]);
  ok("  탈퇴 안내 · 누를 단추 없음", hasText(lastMail().html, "회원 탈퇴 신청에 따라") && !lastMail().html.includes("Settings.html"));
  ok("  계정은 지워졌다", S.deletedUsers.includes(UID));
  ok("  약관 개정 통지의 발송 기록도 지운다", !store.has(`termsNotices/2027-01-01_${UID}`));
  ok("  메일 보낸 기록(billingMails)은 남긴다 — 계약 안내를 보냈다는 기록", mailRecs().some((x) => x.kind === "refund" && x.ok));
}
{
  begin({ viewed: true });
  clock.set(day(27));
  const r = await call("deleteAccount");
  eq("돌려줄 금액이 없는 탈퇴 — 환불 안내를 보내지 않는다", [r.data && r.data.refunded, memberMails().length], [0, 0]);
}

/* ── ⑧ ── */
section("⑧ 열람 기록 1년 파기 — 매일 도는 purgeUnconsented 안에서");
{
  const cut = T.readsCutoffDay || (() => "");
  eq("한국 시간 2027년 11월 25일 0시 → 2026년 11월 25일 앞을 지운다", cut(Date.parse("2027-11-24T15:00:00Z")), "2026-11-25");
  eq("  그 1분 전(한국 시간 11월 24일 23:59)", cut(Date.parse("2027-11-24T14:59:00Z")), "2026-11-24");
  eq("2월 29일 → 전해 2월 28일", cut(Date.parse("2028-02-29T03:00:00Z")), "2027-02-28");
  const NOWP = Date.parse("2027-11-25T03:30:00Z");
  reset(); clock.set(NOWP);
  const days = ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2027-11-25"];
  days.forEach((d, i) => store.set(`report_reads/u${i}_${d}`, { uid: "u" + i, day: d, tickers: ["005930"] }));
  const r = typeof T.purgeOldReads === "function" ? await loud(() => T.purgeOldReads(DB, NOWP)) : { r: {}, lines: [] };
  const left = [...store.keys()].filter((k) => k.startsWith("report_reads/")).map((k) => k.split("_").pop()).sort();
  eq("열람한 날부터 1년이 지난 기록만 지운다", left, ["2026-11-25", "2026-11-26", "2027-11-25"]);
  eq("  지운 수 · 기준일", [r.r.deleted, r.r.cutoff], [2, "2026-11-25"]);
  ok("  기록(로그)에는 건수와 기준일만", r.lines.length === 1 && !/u\d_/.test(r.lines[0]), r.lines.join(" / "));
  ok("  복합 색인이 필요한 질의를 쓰지 않는다", indexNeeds.length === 0, indexNeeds.join(" / "));
}
{
  /* 매일 도는 예약 함수(purgeUnconsented)를 통째로 돌린다 */
  const NOWP = Date.parse("2027-11-25T03:30:00Z");
  reset(); clock.set(NOWP);
  for (let i = 0; i < 2100; i++) store.set(`report_reads/m${i}_2025-0${1 + (i % 9)}-1${i % 10}`, { uid: "m" + i, day: `2025-0${1 + (i % 9)}-1${i % 10}` });
  for (let i = 0; i < 5; i++) store.set(`report_reads/k${i}_2027-11-2${i}`, { uid: "k" + i, day: `2027-11-2${i}` });
  const r1 = await runJob("purgeUnconsented");
  const left1 = [...store.keys()].filter((k) => k.startsWith("report_reads/")).length;
  ok("예약 함수가 오류 없이 끝난다", !r1.error, JSON.stringify(r1.error));
  eq("한 번에 2,000건까지만 지운다(되돌릴 수 없는 삭제의 상한)", left1, 105);
  ok("  묶음 하나가 400건을 넘지 않는다(파이어스토어 한도 500)", S.batches.length > 0 && S.batches.every((n) => n <= 400), S.batches.join(","));
  await runJob("purgeUnconsented");
  const left2 = [...store.keys()].filter((k) => k.startsWith("report_reads/")).map((k) => k.split("/")[1][0]);
  eq("  남은 것은 다음 날 이어서 지운다 — 1년이 안 된 기록만 남는다", [left2.length, left2.every((c) => c === "k")], [5, true]);
}
{
  const bad = { collection() { throw new Error("파이어스토어가 막혔다"); } };
  let threw = false, out = null;
  try { out = (await loud(() => T.purgeOldReads(bad, Date.now()))).r; } catch (e) { threw = true; }
  /* (고치기 전 파일에는 purgeOldReads 가 없다 — 그때는 던져서 실패로 센다) */
  ok("조회가 실패해도 던지지 않는다 — 같은 예약 함수의 계정 정리를 막지 않는다", !threw && out && out.deleted === 0);
}

done();
