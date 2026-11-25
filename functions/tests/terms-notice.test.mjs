/* ============================================================
   약관 개정 개별 통지 — runTermsNotice · scripts/send_terms_notice.cjs · .github/workflows/terms_notice_mail.yml (2026-11-25)

   이용약관 제3조 — 불리하거나 중대한 변경은 적용일 30일 전부터 공지하고 전자우편으로 개별 통지한다. 2027년 1월 1일 유료
   시행안이 그 변경이라 2026년 12월 2일까지 이메일이 있는 회원 전원에게 보낸다. 사장 승인 뒤 사람이 돌리는 도구다.

     ① 대상 — 이메일이 있는 회원(계정의 주소 · 없으면 회원 문서의 주소) · 비활성 · 주소 없는 계정 제외 · 같은 주소는 한 통 ·
        결제 화면을 영어로 쓴 회원은 영어 · 쪽 넘김
     ② count 는 아무것도 쓰지 않는다 · sample 은 관리자 주소로 한 통([시험]) · 기록을 남기지 않는다
     ③ send — 글(제목 · 첫머리 · 시행일 · 주요 내용 ①~④ · 맺음 세 문단 · 단추 · 문의 · 사업자) · 발송 기록 · 동의 이력 · 속도
     ④ 같은 회원에게 두 번 가지 않는다 — 다시 돌림 · 나중에 생긴 같은 주소의 계정 · 한 번 상한 · 처리 중 · 그 사이 다른 실행
     ⑤ 실패 — 거절(새 요청 이름으로 다시) · 답을 못 받음(같은 요청 이름 — 메일 서비스가 막는다) · 같은 이름을 이미 받음 ·
        초당 한도 · 하루 한도 · 열쇠 · 잇단 실패
     ⑥ 스크립트 — 방식 · 확인 문구 · 상한 · 출력에 주소 · 회원 번호가 없음(오류 글도 가림)
     ⑦ 작업 파일 — 예약 없음 · 열쇠 · 확인 문구 · 메일 열쇠는 count 에 주지 않음 · 숫자는 잠가서만(단계를 가짜 숫자로 실제로
        돌려 공개 기록에 숫자 · 주소 · 회원 번호가 나오면 걸린다 — scripts/tests/marketing_seal_test.py 와 같은 방식)

   실행
     node functions/tests/terms-notice.test.mjs
     FN_INDEX=<고치기 전 functions/index.js> node functions/tests/terms-notice.test.mjs   # 고치기 전이면 걸리는지
     NOTICE_WF=<출력을 그대로 찍는 작업 파일> node functions/tests/terms-notice.test.mjs   # ⑦ 이 잡는지
   ============================================================ */
import { readFileSync, writeFileSync, mkdtempSync, mkdirSync, copyFileSync, rmSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";
import { spawnSync } from "node:child_process";
import {
  clock, reset, store, hooks, S, fns, ok, eq, section, done, MIN, ts,
} from "./lib/paid-harness.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);
const TN = (fns.kosTools && fns.kosTools.termsNotice) || {};
const VER = "2027-01-01";
const NOW = Date.parse("2026-11-26T01:00:00Z");
const SUBJ_KO = "[KOSAI] 이용약관 및 개인정보 처리방침 개정 안내(2027년 1월 1일 시행)";
const SUBJ_EN = "[KOSAI] Changes to our Terms of Service and Privacy Policy (effective January 1, 2027)";

const unesc = (s) => String(s).replace(/&quot;/g, '"').replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&");
const texts = (html) => [...String(html || "").matchAll(/<(p|li|h1|h2)\b[^>]*>([\s\S]*?)<\/\1>/g)]
  .map((m) => unesc(m[2].replace(/<br>/g, "\n").replace(/<[^>]+>/g, "")));
const hasP = (html, t) => texts(html).some((x) => x === t || x.includes(t));
const rows = (html) => [...String(html || "").matchAll(/<tr><td[^>]*>([^<]*)<\/td><td[^>]*>([^<]*)<\/td><\/tr>/g)]
  .map((m) => [unesc(m[1]), unesc(m[2])]);
const notice = (uid) => store.get(`termsNotices/${VER}_${uid}`);
const events = () => [...store.entries()].filter(([p, v]) => p.startsWith("consentEvents/") && v.kind === "terms_notice").map(([, v]) => v);
const mailsTo = (to) => S.mails.filter((m) => m.to === to);
const HANGUL = /[가-힣]/;

let slept = [];
const sleep = async (ms) => { slept.push(ms); };
async function run(opt = {}) {
  slept = [];
  if (typeof TN.run !== "function") return { error: "runTermsNotice 없음" };
  try { return await TN.run({ sleep, ...opt }); } catch (e) { return { error: e.message }; }
}
function member(uid, email, meta = {}) {
  S.users.add(uid);
  if (email) S.emails.set(uid, email);
  S.userMeta.set(uid, meta);
}
function seedMembers() {
  reset();
  clock.set(NOW);
  member("a1", "Alpha@Example.com", { emailVerified: true });
  member("a2", "beta@example.com", { emailVerified: false });
  member("a3", "gamma@example.com", { emailVerified: true });            // 결제 화면을 영어로 쓴 회원
  member("a4", "delta@example.com", { emailVerified: true, disabled: true });   // 비활성 — 뺀다
  member("a5", null);                                                      // 계정에 주소가 없는 옛 카카오 회원
  store.set("users/a5", { email: "BETA@example.com" });                   //   회원 문서의 주소가 a2 와 같다 → 한 통
  member("a6", null);                                                      // 주소가 어디에도 없다 — 뺀다
  member("a7", "not-an-email");                                            // 형식이 틀린 주소 — 뺀다
  store.set("subscriptions/a3", { status: "active", mailLang: "en" });
}
const noPII = (x) => !/@|"a[1-9]"|"[b-e][1-9]"|uid_/.test(JSON.stringify(x));

/* ── ① ② ── */
section("① 대상 · ② count — 아무것도 쓰지 않는다");
{
  seedMembers();
  const r = await run({ mode: "count" });
  eq("대상 수 — 주소 3곳(계정 4개) · 인증 2 · 미인증 1 · 영어 1 · 한국어 2 · 비활성 1 · 주소 없음 2",
     [r.addresses, r.members, r.verified, r.unverified, r.en, r.ko, r.disabled, r.noEmail],
     [3, 4, 2, 1, 1, 2, 1, 2]);
  eq("판 · 통지를 시작해야 하는 날(시행일 30일 전)", [r.version, r.deadline], [VER, "2026-12-02"]);
  eq("  이미 보냄 0 · 남음 3", [r.alreadySent, r.remaining], [0, 3]);
  eq("  메일 · 발송 기록 · 동의 이력 모두 없음", [S.mails.length, [...store.keys()].filter((k) => k.startsWith("termsNotices/")).length,
     events().length], [0, 0, 0]);
  ok("  돌려주는 값에 주소 · 회원 번호가 없다", noPII(r), JSON.stringify(r));
  S.pageSize = 2;
  const r2 = await run({ mode: "count" });
  eq("계정 목록을 여러 쪽으로 받아도 같다", [r2.addresses, r2.members, r2.disabled, r2.noEmail], [3, 4, 1, 2]);
  if (typeof TN.deadline === "function") eq("통지 기한 함수", TN.deadline(), "2026-12-02");
}

section("② sample — 관리자 주소로 한 통 · 기록 없음");
{
  seedMembers();
  const r = await run({ mode: "sample" });
  eq("보냄 1", [r.sent, r.error], [1, null]);
  eq("받는 사람은 관리자 주소뿐", S.mails.map((m) => m.to), ["hello@kosai.kr"]);
  eq("제목 앞 [시험]", (S.mails[0] || {}).subject, "[시험] " + SUBJ_KO);
  ok("요청 이름을 붙이지 않는다(시험은 몇 번이고 보낸다)", !("idem" in (S.mails[0] || {})));
  eq("발송 기록 · 동의 이력을 남기지 않는다", [[...store.keys()].filter((k) => k.startsWith("termsNotices/")).length, events().length], [0, 0]);
  await run({ mode: "sample", lang: "en" });
  eq("영어 시험 메일", (S.mails[1] || {}).subject, "[시험] " + SUBJ_EN);
  ok("돌려주는 값에 주소가 없다", noPII(r), JSON.stringify(r));
}

/* ── ③ ── */
section("③ send — 글 · 발송 기록 · 동의 이력 · 속도");
{
  seedMembers();
  const r = await run({ mode: "send" });
  eq("보냄 3 · 실패 0 · 남음 0 · 끝까지", [r.sent, r.failed, r.remaining, r.stoppedBy], [3, 0, 0, null]);
  eq("주소마다 한 통(소문자로 맞춘 주소)", S.mails.map((m) => m.to).sort(), ["alpha@example.com", "beta@example.com", "gamma@example.com"]);
  eq("영어로 받는 회원은 영어", [(mailsTo("gamma@example.com")[0] || {}).subject, (mailsTo("alpha@example.com")[0] || {}).subject],
     [SUBJ_EN, SUBJ_KO]);
  eq("보내는 주소", (S.mails[0] || {}).from, "KOSAI <hello@kosai.kr>");
  const ko = (mailsTo("alpha@example.com")[0] || {}).html || "";
  ok("첫머리", hasP(ko, "KOSAI를 이용해 주셔서 감사합니다. 2027년 1월 1일부터 유료 서비스(멤버십)를 도입함에 따라 이용약관과 개인정보 처리방침을 개정하여 안내드립니다."));
  eq("시행일", rows(ko), [["시행일", "2027년 1월 1일"]]);
  ok("주요 내용 제목", hasP(ko, "주요 내용"));
  for (const t of [
    "① 리포트의 실적 분석, 산업 분석, 전망, 밸류에이션 해설, 강세·약세 요인, 리스크 요인, 다음 체크포인트, 종합 의견은 멤버십(월 14,900원, 부가가치세 포함) 회원에게 제공합니다. 리포트의 개요, 사업 구조, 실적 추이, 참고 출처와 업종 분석, 모닝브리핑은 계속 무료로 제공합니다.",
    "② 멤버십은 신용·체크카드 월 정기결제이며 언제든지 해지할 수 있습니다. 결제일부터 7일 이내에는 이용한 날의 이용료만 빼고 환불하며(유료 영역을 열람하지 않으셨다면 전액), 7일이 지난 뒤에는 이용한 날의 이용료와 결제금액의 10%를 빼고 환불합니다.",
    "③ 유료 서비스는 유사투자자문업 신고가 수리된 뒤에 시작합니다. 개정 약관 제16조에는 KOSAI가 금융투자업자가 아닌 유사투자자문업자로서 "
      + "개별적인 투자상담과 자금운용을 하지 않는다는 사항과, 투자에는 원금 손실이 발생할 수 있으며 그 손실은 투자자에게 귀속된다는 사항을 둡니다.",
    "④ 개인정보 처리방침에 구독 결제와 환불에 필요한 결제 정보, 유료 영역 열람 기록의 처리와 결제 처리 위탁(토스페이먼츠)을 추가합니다.",
    "기존 회원께서 시행일에 자동으로 결제되는 금액은 없습니다. 멤버십은 직접 구독을 신청하시는 경우에만 이용료가 청구됩니다.",
    "개정 약관에 동의하지 않으시면 시행일 전까지 설정 화면에서 회원 탈퇴를 하실 수 있습니다. 시행일까지 거부 의사를 표시하지 않으시면 개정 약관에 동의하신 것으로 봅니다(현행 이용약관 제3조).",
    "유사투자자문업 신고 수리 등 준비 사정으로 시행일이 늦어지는 경우 다시 안내드립니다.",
  ]) ok(`본문 — ${t.slice(0, 18)}…`, hasP(ko, t));
  ok("단추 '개정 내용 자세히 보기' → 공지 페이지", ko.includes('href="https://kosai.kr/Notice.html"') && ko.includes(">개정 내용 자세히 보기</a>"));
  ok("꼬리 — 문의 · 사업자 표시", hasP(ko, "문의: hello@kosai.kr") &&
     ko.includes("상호 코사이 · 대표 임범준 · 사업자등록번호 380-25-02019 · 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호 · hello@kosai.kr"));
  ok("광고가 아니라 수신거부 줄이 없다", !/수신거부|unsubscribe/i.test(ko));
  const en = (mailsTo("gamma@example.com")[0] || {}).html || "";
  ok("영어 — 한글 없음 · 공지 링크 · 단추", en && !HANGUL.test(en) && en.includes('href="https://kosai.kr/Notice.html"') &&
     en.includes(">Read the full changes</a>"), (en.match(/.{20}[가-힣].{20}/) || [""])[0]);
  ok("영어 — 신고 수리 뒤 시작 · 개정 약관 제16조의 고지", hasP(en, "The paid service will start after our report as a quasi-investment advisory business is accepted.") &&
     hasP(en, "Article 16 of the revised Terms states that KOSAI is a quasi-investment advisory business"));
  ok("영어 — 시행일 · 금액 · 7일 · 10% 가 같은 값", hasP(en, "January 1, 2027") && hasP(en, "KRW 14,900") &&
     hasP(en, "Within 7 days of the billing date") && hasP(en, "10% of the amount paid"));

  eq("발송 기록 — 계정마다 '보냄'(같은 주소의 둘째 계정은 sharedAddress)", ["a1", "a2", "a3", "a5"].map((u) =>
     [(notice(u) || {}).status, !!(notice(u) || {}).sharedAddress, (notice(u) || {}).lang]),
     [["sent", false, "ko"], ["sent", false, "ko"], ["sent", false, "en"], ["sent", true, "ko"]]);
  ok("  발송 기록에는 주소를 적지 않는다", ["a1", "a2", "a3", "a5"].every((u) => !JSON.stringify(notice(u) || {}).includes("@")));
  eq("동의 이력(terms_notice) — 계정마다 · 주소 · 판 · 말", events().map((e) => [e.uid, e.email, e.version, e.lang]).sort(),
     [["a1", "alpha@example.com", VER, "ko"], ["a2", "beta@example.com", VER, "ko"], ["a3", "gamma@example.com", VER, "en"],
      ["a5", "beta@example.com", VER, "ko"]]);
  const keys = S.mails.map((m) => m.idem || "");
  ok("요청 이름 — 주소마다 다르고 '판/주소 지문/확정 실패 횟수' 꼴", new Set(keys).size === 3 &&
     keys.every((k) => /^terms-notice\/2027-01-01\/[0-9a-f]{32}\/0$/.test(k)), keys.join(" "));
  ok("  요청 이름에 주소 · 회원 번호가 들어가지 않는다(주소의 지문만)", keys.every((k) => !/@|example|\/a[1-9]\//.test(k)));
  eq("한 통마다 쉰다(600ms · 세 통이면 두 번)", slept, [600, 600]);
  ok("돌려주는 값에 주소 · 회원 번호가 없다", noPII(r), JSON.stringify(r));
}

/* ── ④ ── */
section("④ 같은 회원에게 두 번 가지 않는다");
{
  seedMembers();
  await run({ mode: "send" });
  const before = S.mails.length;
  const r = await run({ mode: "send" });
  eq("다시 돌리면 아무에게도 가지 않는다", [S.mails.length - before, r.sent, r.remaining, r.alreadySent], [0, 0, 0, 3]);
  member("a8", "Beta@Example.com", { emailVerified: true });
  const r2 = await run({ mode: "send" });
  eq("나중에 생긴 같은 주소의 계정 — 보내지 않고 기록만", [S.mails.length - before, r2.shared, (notice("a8") || {}).status,
     !!(notice("a8") || {}).sharedAddress], [0, 1, "sent", true]);
  ok("  그 계정에도 동의 이력을 남긴다", events().some((e) => e.uid === "a8" && e.email === "beta@example.com"));
}
{
  reset(); clock.set(NOW);
  for (let i = 1; i <= 5; i++) member("b" + i, `b${i}@example.com`, { emailVerified: true });
  const r1 = await run({ mode: "send", limit: 2 });
  eq("한 번 상한 2 — 두 통 보내고 멈춘다", [r1.sent, r1.stoppedBy, r1.remaining, r1.limit], [2, "limit", 3, 2]);
  const r2 = await run({ mode: "send", limit: 2 });
  const r3 = await run({ mode: "send", limit: 2 });
  eq("  다시 돌리면 이어서 — 2 · 1 · 끝", [r2.sent, r3.sent, r3.stoppedBy, r3.remaining], [2, 1, null, 0]);
  eq("  모두 한 통씩", S.mails.map((m) => m.to).sort(), ["b1@example.com", "b2@example.com", "b3@example.com", "b4@example.com", "b5@example.com"]);
}
{
  reset(); clock.set(NOW);
  member("d1", "d1@example.com"); member("d2", "d2@example.com");
  store.set(`termsNotices/${VER}_d1`, { uid: "d1", status: "sending", claimedAt: ts(NOW - MIN) });
  const r = await run({ mode: "send" });
  eq("다른 실행이 1분 전에 잡은 회원은 건너뛴다", [r.busy, r.sent, mailsTo("d1@example.com").length], [1, 1, 0]);
  store.set(`termsNotices/${VER}_d1`, { uid: "d1", status: "sending", claimedAt: ts(NOW - 20 * MIN) });
  const r2 = await run({ mode: "send" });
  eq("  15분이 지난 잡음은 죽은 실행의 것 — 이어서 보낸다", [r2.sent, mailsTo("d1@example.com").length], [1, 1]);
}
{
  reset(); clock.set(NOW);
  member("e1", "e1@example.com");
  hooks.beforeTx = async () => { store.set(`termsNotices/${VER}_e1`, { uid: "e1", status: "sent" }); };
  const r = await run({ mode: "send" });
  eq("목록을 만든 뒤 다른 실행이 보냈으면 보내지 않는다", [r.raced, r.sent, S.mails.length, r.remaining], [1, 0, 0, 0]);
}

/* ── ⑤ ── */
section("⑤ 실패 · 다시 보내기");
{
  reset(); clock.set(NOW);
  member("c1", "c1@example.com"); member("c2", "c2@example.com"); member("c3", "c3@example.com");
  S.mailFail = async (m) => (m.to === "c2@example.com" ? { data: null, error: { name: "validation_error" } } : undefined);
  const r = await run({ mode: "send" });
  eq("거절된 한 통 — 나머지는 보낸다", [r.sent, r.failed, r.unsure, r.stoppedBy], [2, 1, 0, null]);
  eq("  '실패'와 확정 실패 횟수를 적는다", [(notice("c2") || {}).status, (notice("c2") || {}).failures, (notice("c2") || {}).error],
     ["failed", 1, "validation_error"]);
  S.mailFail = null;
  const r2 = await run({ mode: "send" });
  eq("  다시 돌리면 그 회원에게만 — 새 요청 이름(/1)", [r2.sent, mailsTo("c2@example.com").map((m) => m.idem.split("/").pop())], [1, ["1"]]);
  eq("  이제 '보냄'", (notice("c2") || {}).status, "sent");
}
{
  reset(); clock.set(NOW);
  member("f1", "f1@example.com");
  const accepted = new Set();
  /* 메일 서비스는 받았는데 답이 끊겼다 — 실제로는 나갔다 */
  S.mailFail = async (m, idem) => { accepted.add(idem); S.mails.push({ ...m, idem }); throw Object.assign(new Error("socket hang up f1@example.com"), { name: "FetchError" }); };
  const r = await run({ mode: "send" });
  eq("답을 못 받음 — 실패로 세되 확정 실패 횟수는 올리지 않는다", [r.failed, r.unsure, (notice("f1") || {}).failures, (notice("f1") || {}).unsure],
     [1, 1, undefined, true]);
  /* 다음 실행 — 같은 요청 이름이면 메일 서비스가 다시 보내지 않고 처음 답을 돌려준다 */
  S.mailFail = async (m, idem) => (accepted.has(idem) ? { data: { id: "first" }, error: null } : undefined);
  const r2 = await run({ mode: "send" });
  eq("  다시 돌리면 같은 요청 이름 — 한 번만 받는다", [r2.sent, mailsTo("f1@example.com").length, (notice("f1") || {}).status], [1, 1, "sent"]);
}
{
  reset(); clock.set(NOW);
  member("g1", "g1@example.com");
  S.mailFail = async () => ({ data: null, error: { name: "invalid_idempotent_request" } });
  const r = await run({ mode: "send" });
  eq("같은 요청 이름을 이미 받았다는 답 — 앞선 실행이 보낸 것으로 친다", [r.sent, r.failed, (notice("g1") || {}).status, (notice("g1") || {}).dedup],
     [1, 0, "sent", "invalid_idempotent_request"]);
}
{
  reset(); clock.set(NOW);
  member("h1", "h1@example.com");
  let first = true;
  S.mailFail = async () => { if (first) { first = false; return { data: null, error: { name: "rate_limit_exceeded" } }; } return undefined; };
  const r = await run({ mode: "send" });
  eq("초당 한도 — 2초 쉬고 한 번 더 보낸다", [r.sent, slept, mailsTo("h1@example.com").length], [1, [2000], 1]);
}
for (const [label, name, want, tries] of [
  ["하루 한도", "daily_quota_exceeded", "quota", 1],
  ["열쇠가 틀림", "invalid_api_Key", "auth", 1],
  ["잇단 실패 다섯 번", "validation_error", "errors", 5],
]) {
  reset(); clock.set(NOW);
  for (let i = 1; i <= 7; i++) member("k" + i, `k${i}@example.com`);
  let calls = 0;
  S.mailFail = async () => { calls++; return { data: null, error: { name } }; };
  const r = await run({ mode: "send" });
  eq(`${label} — 그 자리에서 멈춘다`, [r.stoppedBy, calls, r.failed, r.remaining], [want, tries, tries, 7]);
}

/* ── ⑥ ── */
section("⑥ 스크립트(scripts/send_terms_notice.cjs)");
let SCRIPT = null;
try { SCRIPT = require(join(ROOT, "scripts/send_terms_notice.cjs")); } catch (e) { ok("스크립트를 불러온다", false, e.message); }
async function script(env, opt = {}) {
  const lines = [];
  if (!SCRIPT) return { code: -1, lines };
  const code = await SCRIPT.main({ env: { NOTICE_GAP_MS: "0", ...env }, out: (s) => lines.push(String(s)), ...opt });
  return { code, lines, text: lines.join("\n") };
}
const clean = (t) => !/@|\ba[1-9]\b|uid_secret|termsNotices\/2027-01-01_/.test(t);
{
  seedMembers();
  const c = await script({ MODE: "count" });
  eq("count — 끝 코드 0", c.code, 0);
  ok("  숫자를 찍는다(작업 파일이 잠근다)", /보낼 주소 3곳/.test(c.text) && /남음 3곳/.test(c.text) && /2026-12-02/.test(c.text), c.text);
  ok("  주소 · 회원 번호가 없다", clean(c.text), c.text);
  const n = await script({ MODE: "send" });
  eq("send — 확인 문구가 없으면 2 · 아무에게도 보내지 않는다", [n.code, S.mails.length], [2, 0]);
  const w = await script({ MODE: "send", CONFIRM: "보낼래" });
  eq("  틀린 확인 문구도 2", [w.code, S.mails.length], [2, 0]);
  const bad = await script({ MODE: "send", CONFIRM: "보내기", LIMIT: "abc" });
  eq("  상한이 수가 아니면 2", [bad.code, S.mails.length], [2, 0]);
  const s = await script({ MODE: "send", CONFIRM: "보내기", LIMIT: "1" });
  eq("send — 상한 1 · 끝 코드 0(상한에 닿은 것은 실패가 아니다)", [s.code, S.mails.length], [0, 1]);
  ok("  보낸 수 · 남은 수 · 멈춘 까닭을 찍는다", /보냄 1통/.test(s.text) && /남음 2곳/.test(s.text) && /한 번 상한에 닿았다/.test(s.text), s.text);
  ok("  주소 · 회원 번호가 없다", clean(s.text), s.text);
  const x = await script({ MODE: "bogus" });
  eq("모르는 방식은 2", x.code, 2);
}
{
  seedMembers();
  const s = await script({ MODE: "sample", NOTICE_LANG: "en" });
  eq("sample — 끝 코드 0 · 관리자 주소로 영어 한 통", [s.code, S.mails.map((m) => [m.to, m.subject])], [0, [["hello@kosai.kr", "[시험] " + SUBJ_EN]]]);
  eq("  한 줄만 찍고 주소를 적지 않는다", [s.lines.length, clean(s.text)], [1, true]);
  S.mailFail = async () => ({ data: null, error: { name: "validation_error" } });
  const f = await script({ MODE: "sample" });
  eq("  못 보내면 1 · 오류 이름", [f.code, /validation_error/.test(f.text)], [1, true]);
}
{
  seedMembers();
  S.mailFail = async () => ({ data: null, error: { name: "daily_quota_exceeded" } });
  const q = await script({ MODE: "send", CONFIRM: "보내기" });
  eq("한도에 걸려 멈추면 1 · 사정을 찍는다", [q.code, /발송 한도/.test(q.text)], [1, true]);
}
{
  const boom = { kosTools: { termsNotice: { run: async () => {
    throw Object.assign(new Error("write termsNotices/2027-01-01_uid_secret_9 failed for someone@example.com"), { code: "aborted" });
  } } } };
  const e = await script({ MODE: "count" }, { fns: boom });
  eq("오류 — 끝 코드 1", e.code, 1);
  ok("  오류 글의 주소 · 문서 경로(회원 번호)를 가린다", clean(e.text) && /\(주소\)/.test(e.text) && /termsNotices\/\(번호\)/.test(e.text), e.text);
  const none = await script({ MODE: "count" }, { fns: {} });
  eq("함수 파일에 도구가 없으면 1", none.code, 1);
}

/* ── ⑦ ── */
section("⑦ 작업 파일 — 예약 없음 · 열쇠 · 숫자는 잠가서만");
/* NOTICE_WF=<다른 작업 파일> — 출력을 그대로 찍는 판으로 돌려 이 검사가 걸리는지 본다 */
const WF_PATH = process.env.NOTICE_WF || join(ROOT, ".github/workflows/terms_notice_mail.yml");
const WF = existsSync(WF_PATH) ? readFileSync(WF_PATH, "utf8") : "";
const code = WF.split("\n").filter((x) => !x.trim().startsWith("#")).join("\n");
ok("작업 파일이 있다", !!WF);
ok("손으로만 돈다(workflow_dispatch · 예약 없음)", /workflow_dispatch:/.test(code) && !/^\s*schedule:/m.test(code));
ok("같은 묶음으로 겹쳐 돌지 않는다(concurrency)", /concurrency:\s*\n\s+group: terms-notice-mail/.test(code));
ok("입력 — mode · lang · limit · confirm · key", ["mode:", "lang:", "limit:", "confirm:", "key:"].every((k) => code.includes(`      ${k}`)));
ok("메일 열쇠는 count 에 주지 않는다", code.includes("RESEND_API_KEY: ${{ inputs.mode != 'count' && secrets.RESEND_API_KEY || '' }}"));
ok("저장소 읽기 권한만", /permissions:\s*\n\s+contents: read/.test(code));
ok("열쇠 확인이 스크립트보다 먼저", code.indexOf("marketing_seal.py check") >= 0 &&
   code.indexOf("marketing_seal.py check") < code.indexOf("node scripts/send_terms_notice.cjs"));
ok("출력을 기록에 흘리지 않는다(tee · cat 없음 · 요약 칸에 파일을 붙이지 않음)",
   !/\btee\b/.test(code) && !/\bcat\b/.test(code) && !/GITHUB_STEP_SUMMARY.*\$\(/.test(code));
ok("잠긴 줄 표시(KOSAI-SEALED)를 작업 파일에 쓰지 않는다", !code.includes("KOSAI-SEALED"));
ok("스크립트는 파일로만 쓴다", /node scripts\/send_terms_notice\.cjs > \/tmp\/notice\.txt 2>&1/.test(code));

/* 단계 본문(run: |)을 꺼낸다 — 단계 이름이 아니라 그 단계가 돌리는 명령으로 찾는다 */
function stepRun(needle) {
  const rows = WF.split("\n");
  const hit = rows.findIndex((x) => x.includes(needle) && !x.trim().startsWith("#"));
  if (hit < 0) return null;
  let j = hit;
  while (j >= 0 && !rows[j].trim().startsWith("run:")) j--;
  if (j < 0) return null;
  const first = rows[j].trim().slice(4).trim();
  if (first && first !== "|") return first + "\n";
  const ind = rows[j].length - rows[j].trimStart().length;
  const body = [];
  for (const x of rows.slice(j + 1)) { if (x.trim() && x.length - x.trimStart().length <= ind) break; body.push(x); }
  const pad = Math.min(...body.filter((x) => x.trim()).map((x) => x.length - x.trimStart().length));
  return body.map((x) => x.slice(pad)).join("\n") + "\n";
}
const have = (cmd) => spawnSync(cmd, ["--version"], { encoding: "utf8" }).status === 0;
if (!have("python3") || !spawnSync("openssl", ["version"], { encoding: "utf8" }).stdout) {
  ok("python3 · openssl 이 있어야 잠금 단계를 돌려 본다", false);
} else {
  const TMP = mkdtempSync(join(tmpdir(), "notice-wf-"));
  const SEAL = join(ROOT, "scripts/marketing_seal.py");
  const KEYF = join(TMP, "key", "key.pem");
  const sealEnv = { ...process.env, KOSAI_MARKETING_KEY: KEYF, PYTHONIOENCODING: "utf-8" };
  const KEY = spawnSync("python3", [SEAL, "newkey"], { env: sealEnv, encoding: "utf8" }).stdout.trim();
  ok("시험용 열쇠를 만든다(진짜 열쇠는 건드리지 않는다)", KEY.length > 300 && !KEY.includes("\n"));
  /* 기록에 나오면 안 되는 글 — 회원 수 · 주소 · 회원 번호(가짜). 쉼표는 잠근 글(base64)에 없다. */
  const SECRET = ["보낼 주소 1,234곳", "someone@example.com", "uid_secret_77", "남음 5,678곳"];
  const fake = (rc) => [
    "const fs = require('fs');",
    "fs.writeFileSync('ran.txt', 'ran');",
    `console.log(${JSON.stringify(SECRET[0] + " · " + SECRET[3])});`,
    `console.error(${JSON.stringify("경고 " + SECRET[1] + " " + SECRET[2])});`,
    `process.exit(${rc});`,
  ].join("\n");
  function workspace(rc) {
    const w = mkdtempSync(join(TMP, "w-"));
    mkdirSync(join(w, "scripts"));
    copyFileSync(SEAL, join(w, "scripts", "marketing_seal.py"));
    writeFileSync(join(w, "scripts", "send_terms_notice.cjs"), fake(rc));
    return w;
  }
  function step(w, body, env) {
    if (body == null) return { rc: null, out: "", summ: "" };
    const f = join(w, "step.sh");
    writeFileSync(f, body.replaceAll("/tmp/notice.txt", join(w, "notice.txt")));
    const summ = join(w, "summary.md");
    writeFileSync(summ, "");
    const r = spawnSync("bash", ["-eo", "pipefail", f], {
      cwd: w, encoding: "utf8",
      env: { ...process.env, PYTHONIOENCODING: "utf-8", GITHUB_STEP_SUMMARY: summ, MODE: "", KEY: "", CONFIRM: "", ...env },
    });
    return { rc: r.status, out: (r.stdout || "") + (r.stderr || ""), summ: readFileSync(summ, "utf8") };
  }
  const opened = (out) => {
    const lf = join(TMP, "job.log");
    writeFileSync(lf, out.split("\n").map((x) => "2026-11-25T01:02:03.4567890Z " + x).join("\n"));
    const r = spawnSync("python3", [SEAL, "open", "--file", lf], { env: sealEnv, encoding: "utf8" });
    return r.status === 0 ? r.stdout : "";
  };
  const leaked = (s) => SECRET.filter((x) => s.includes(x)).concat(["1,234", "5,678", "@"].filter((x) => s.includes(x)));

  const keyStep = stepRun("marketing_seal.py check");
  const sendStep = stepRun("node scripts/send_terms_notice.cjs");
  ok("열쇠 확인 단계 · 통지 단계를 찾는다", !!keyStep && !!sendStep);
  const w0 = workspace(0);
  let r = step(w0, keyStep, { MODE: "count", KEY: "" });
  ok("열쇠 확인 — count 에 열쇠가 없으면 실패(::error)", r.rc === 1 && r.out.includes("::error"), `rc=${r.rc} ${r.out.slice(-200)}`);
  r = step(w0, keyStep, { MODE: "send", CONFIRM: "보내기", KEY: "" });
  ok("  send 에 열쇠가 없으면 실패", r.rc === 1 && r.out.includes("::error"), `rc=${r.rc}`);
  r = step(w0, keyStep, { MODE: "send", CONFIRM: "", KEY });
  ok("  send 에 확인 문구가 없으면 실패", r.rc === 1 && r.out.includes("확인 문구"), `rc=${r.rc} ${r.out.slice(-200)}`);
  r = step(w0, keyStep, { MODE: "count", KEY: "잘못된열쇠" });
  ok("  열쇠가 공개 열쇠가 아니면 실패", r.rc === 2, `rc=${r.rc} ${r.out.slice(-200)}`);
  r = step(w0, keyStep, { MODE: "sample", KEY: "" });
  ok("  sample 은 열쇠 없이도 지난다", r.rc === 0, `rc=${r.rc} ${r.out.slice(-200)}`);
  r = step(w0, keyStep, { MODE: "count", KEY });
  ok("  맞는 열쇠면 지난다", r.rc === 0, `rc=${r.rc} ${r.out.slice(-200)}`);

  for (const [mode, rc] of [["count", 0], ["send", 1]]) {
    const w = workspace(rc);
    const s = step(w, sendStep, { MODE: mode, KEY, CONFIRM: mode === "send" ? "보내기" : "" });
    ok(`통지 단계(${mode}) — 스크립트의 끝 코드 ${rc} 를 그대로 낸다`, s.rc === rc, `rc=${s.rc} ${s.out.slice(-300)}`);
    eq(`  공개 기록 · 요약 칸에 회원 수 · 주소 · 회원 번호가 없다(${mode})`, leaked(s.out + s.summ), []);
    const o = opened(s.out);
    ok(`  잠긴 글에는 다 있다(${mode})`, SECRET.every((x) => o.includes(x)), o.slice(0, 200));
    ok(`  요약 칸은 '잠겨 있습니다' 한 줄(${mode})`, s.summ.trim().split("\n").length === 1 && s.summ.includes("잠겨 있습니다"), s.summ);
  }
  {
    const w = workspace(0);
    const s = step(w, sendStep, { MODE: "count", KEY: "" });
    ok("통지 단계만 따로 돌려도 열쇠가 없으면 스크립트를 돌리지 않는다", s.rc === 1 && !existsSync(join(w, "ran.txt")), `rc=${s.rc}`);
    eq("  그때도 기록에 숫자가 없다", leaked(s.out + s.summ), []);
  }
  for (const rc of [0, 1]) {
    const w = workspace(rc);
    const s = step(w, sendStep, { MODE: "sample", KEY: "" });
    ok(`sample(열쇠 없음 · 끝 코드 ${rc}) — 성공 여부 한 줄만`, s.rc === rc &&
       s.out.trim() === (rc === 0 ? "시험 메일을 관리자 주소로 보냈다(제목 앞 [시험])." : "시험 메일을 보내지 못했다(끝 코드 1)."), s.out);
    eq(`  기록에 스크립트 출력이 없다(끝 코드 ${rc})`, leaked(s.out + s.summ), []);
  }
  {
    const w = workspace(0);
    const s = step(w, sendStep, { MODE: "sample", KEY });
    ok("sample 에 열쇠를 주면 출력도 잠가서 남긴다", s.rc === 0 && opened(s.out).includes(SECRET[1]) && leaked(s.out + s.summ).length === 0,
       s.out.slice(-200));
  }
  rmSync(TMP, { recursive: true, force: true });
}

done();
