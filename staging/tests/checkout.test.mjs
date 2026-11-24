/* ============================================================
   스테이징 결제 화면 — 실제로 그려지는가

   왜 있는가. 결제 화면이 '불러오는 중…' 에서 멈춘 적이 있다. 화면을 그리는
   중에 잘못된 이름을 하나 읽었을 뿐인데, 그러면 아무 말 없이 회전자만 돌고
   사용자는 결제도 못 하고 이유도 모른다. 눈으로 볼 수 없으니 이걸로 본다.

   실행
     npm install --no-save jsdom
     node staging/tests/checkout.test.mjs

   무엇을 보는가
     · 요금제는 멤버십 하나 — 주소에 요금제가 없거나 옛 이름(basic · pro)이어도 멤버십 결제 화면
     · 환불 기준(명세 4절 환불 안내)이 결제 단추보다 앞에 펼쳐져 있는가 — 전자상거래법 제17조⑥
     · 구독이 없는 사람에게 결제 화면이 그려지는가
     · 환불한 날 다시 시작하려는 사람에게도 그려지는가
     · 오늘 리포트를 봐서 자정까지 살아 있는 구독이라면
       겹친 하루를 뒤에 붙인다고 알려 주고 다음 결제일이 밀리는가
     · 이용 중인 사람은 결제 화면 대신 '이미 이용 중' 으로 막히는가

   저장소의 checkout.js 를 그대로 읽는다. import 문만 대역으로 돌린다.
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work-co");

const require_ = createRequire(import.meta.url);
let JSDOM;
try {
  ({ JSDOM } = await import(require_.resolve("jsdom", { paths: [ROOT] })));
} catch (e) {
  console.error("jsdom 이 없습니다.  npm install --no-save jsdom  후 다시 실행하세요.");
  process.exit(2);
}

rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });

const swap = (name, out) => {
  let s = readFileSync(join(STAGING, name), "utf8");
  // 대역이 이미 깔았다. 주소에 캐시 판본이 붙어 있어도 지운다.
  s = s.replace(/import "\.\/paywall\.js(?:\?v=[0-9a-f]+)?";/g, "");
  s = s.replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-fb.js"');
  s = s.replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub-fb.js"');
  writeFileSync(join(TMP, out), s);
};
writeFileSync(join(TMP, "payment-config.js"), readFileSync(join(STAGING, "payment-config.js")));
swap("demo-backend.js", "demo.js");
swap("checkout.js", "checkout.js");
writeFileSync(join(TMP, "stub-fb.js"), `
export const app = {};
export const auth = { currentUser: { uid: "u1", email: "a@b.c", displayName: "테스터" } };
export const isConfigured = true;
export const SOCIAL = { functionsRegion: "asia-northeast3" };
export const onAuthStateChanged = (a, fn) => { Promise.resolve().then(() => fn(a.currentUser)); return () => {}; };
export const getFunctions = () => ({});
export const httpsCallable = () => async () => ({ data: {} });
`);

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};

const DAY = 86400000;
const kstDayNo = (ms) => Math.floor((ms + 9 * 3600000) / DAY);
const kstEndOfToday = () => (kstDayNo(Date.now()) + 1) * DAY - 9 * 3600000;

/* 결제 화면은 주소(?plan=…)를 읽고 한 번만 그린다 — 상황마다 창을 새로 연다. */
async function open(query, setup, lang) {
  const dom = new JSDOM(
    `<!doctype html><html><body><h1 id="coH1"></h1><p id="coH2"></p><div id="coApp"></div></body></html>`,
    { url: "https://kosai.kr/staging/checkout.html" + query, pretendToBeVisual: true });
  const w = dom.window;
  for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                   "location", "localStorage", "history", "URL", "URLSearchParams"]) {
    globalThis[k] = w[k];
  }
  /* 구독은 모의 백엔드가 뜨기 전에 깔아 둔다 — 뜨는 순간의 상태를 읽어
     결제 화면에 넘기므로, 나중에 넣으면 못 본다. */
  if (lang) localStorage.setItem("kos-lang", lang);
  if (setup) setup();
  const bust = "?" + Math.random();                 // 창마다 새 모듈로 읽는다
  await import(`file://${join(TMP, "demo.js")}${bust}`);
  await import(`file://${join(TMP, "checkout.js")}${bust}`);
  for (let i = 0; i < 40; i++) await new Promise((r) => setTimeout(r, 1));
  return () => document.getElementById("coApp").textContent.replace(/\s+/g, " ").trim();
}

const SUB_KEY = "kos-demo-sub";
const putSub = (s) => localStorage.setItem(SUB_KEY, JSON.stringify(s));

/* 명세 4절의 환불 안내 — 결제 화면 · 자주 묻는 질문 · 설정의 환불 확인 창이 같은 글을 쓴다. 명세에서 그대로 옮겼다. */
const NOTICE = [
  "환불 금액은 환불 신청일부터 3영업일 이내에 결제하신 수단으로 돌려드립니다.",
  "결제일(정기결제 갱신 결제일 포함)부터 7일 이내에 신청하시면, 결제금액에서 이용하신 날의 이용료를 뺀 금액을 환불합니다. 결제 후 리포트의 유료 영역을 열람하지 않으셨다면 전액 환불합니다.",
  "결제일부터 7일이 지난 뒤에 신청하시면, 결제금액에서 이용하신 날의 이용료와 결제금액의 10%(위약금)를 뺀 금액을 환불합니다. 계산한 금액이 0원 이하이면 환불 금액은 없으며, 추가로 청구하지 않습니다.",
  "이용하신 날의 이용료 = 결제금액 ÷ 해당 이용 기간의 일수 × 이용일수(이용 기간 시작일부터 환불 신청일까지). 1원 미만은 회원에게 유리하게 처리합니다.",
  "예) 이용 기간 30일 기준 — 3일째 신청 13,410원 환불 / 10일째 신청 8,444원 환불",
  "의무 사용 기간은 없으며, 설정의 구독 항목에서 언제든지 해지하실 수 있습니다. 해지하시면 다음 결제일부터 이용료가 청구되지 않고, 이미 결제하신 기간이 끝날 때까지 이용하실 수 있습니다.",
];

console.log("── 구독이 없는 사람 ──");
{
  const txt = await open("?plan=member");
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  ok("회전자에서 멈추지 않는다", !/불러오는 중/.test(txt()), txt().slice(0, 60));
  ok("이용 시작일은 오늘", /이용 시작일오늘/.test(txt()), txt());
  ok("요금제는 멤버십 · 월 14,900원", /플랜멤버십/.test(txt()) && /월 14,900원/.test(txt()) && /결제 금액14,900원/.test(txt()), txt().slice(-200));
  ok("BASIC · PRO 는 없다", !/BASIC|PRO/.test(txt()));

  /* 환불 기준 — 결제 전에 보이게. 단계 제목 · 글 전부 · 결제 단추보다 앞 · 접혀 있지 않다 */
  const ref = document.getElementById("coRefund"), btn = document.getElementById("payBtn");
  ok("환불 기준 단계가 있다", [...document.querySelectorAll(".co-step h3")].map((h) => h.textContent).join("|") === "결제 수단|환불 기준|약관 동의",
     [...document.querySelectorAll(".co-step h3")].map((h) => h.textContent).join("|"));
  const lines = ref ? [...ref.querySelectorAll("p, li")].map((x) => x.textContent) : [];
  ok("환불 안내가 명세 글과 한 글자까지 같다", JSON.stringify(lines) === JSON.stringify(NOTICE), JSON.stringify(lines).slice(0, 300));
  ok("환불 안내는 결제 단추보다 앞에 있다", !!(ref && btn && (ref.compareDocumentPosition(btn) & 4)));
  ok("환불 안내는 접혀 있지 않다(details · hidden 아님)", !!ref && !ref.closest("details") && !ref.hidden && !ref.closest("[hidden]"));
  ok("동의 항목이 위 환불 기준을 가리킨다", [...document.querySelectorAll(".agree label")].some((l) => /위 환불 기준을 확인했으며/.test(l.textContent)));
  ok("옛 하루 열람 한도 이야기는 없다", !/열람 한도/.test(txt()));
}

console.log("\n── 요금제를 적지 않았거나 옛 이름으로 왔을 때 ──");
for (const q of ["", "?plan=basic", "?plan=PRO"]) {
  const txt = await open(q);
  ok(`'${q || "(없음)"}' — 멤버십 결제 화면`, /결제하고 시작하기/.test(txt()) && /플랜멤버십/.test(txt()), txt().slice(0, 80));
}

console.log("\n── 영어 화면 ──");
{
  const txt = await open("?plan=member", null, "en");
  const ref = document.getElementById("coRefund");
  ok("영어 환불 안내 — 3영업일 · 7일 · 10% · 예시 금액", !!ref && /within 3 business days/.test(ref.textContent)
     && /10% of the amount paid/.test(ref.textContent) && /KRW 13,410/.test(ref.textContent) && /KRW 8,444/.test(ref.textContent), ref && ref.textContent.slice(0, 200));
  ok("영어 화면에 한글이 없다", !/[가-힣]/.test(txt()), (txt().match(/[^ ]*[가-힣][^ ]*/g) || []).slice(0, 5).join(" "));
  ok("요금제 이름은 Membership", /PlanMembership/.test(txt()), txt().slice(-200));
}

console.log("\n── 청약철회로 환불했다(이용이 이미 끝났다) ──");
{
  const txt = await open("?plan=member", () => putSub({
    status: "active", plan: "member", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: Date.now() - 1000, cancelAtPeriodEnd: true,
    refundedAt: Date.now() - 1000, readsSincePay: 0,
  }));
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  ok("이용 시작일은 오늘", /이용 시작일오늘/.test(txt()), txt());
  ok("나중에 시작한다는 안내는 없다", !/새 구독은/.test(txt()));
}

console.log("\n── 이용분을 빼고 환불했다(오늘 자정까지 살아 있다) ──");
{
  const end = kstEndOfToday();
  const txt = await open("?plan=member", () => putSub({
    status: "active", plan: "member", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: end, cancelAtPeriodEnd: true,
    refundedAt: Date.now() - 1000, readsSincePay: 3,
  }));
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  ok("이용 시작일은 오늘", /이용 시작일오늘/.test(txt()), txt());
  ok("첫 결제일도 오늘", /첫 결제일오늘/.test(txt()), txt());
  ok("겹치는 하루를 뒤에 붙인다고 미리 알려 준다",
     /이용 기간 끝에 더해 드립니다/.test(txt()), txt());
  ok("그 안내에 하루 열람 한도 이야기가 없다", !/열람 한도/.test(txt()));
  /* 다음 결제일이 '오늘부터 한 달' 이 아니라 '자정부터 한 달' 이어야 한다.
     이걸 안 보면 안내 문구만 붙고 날짜는 안 밀리는 판을 못 잡는다. */
  const nx = new Date(end); nx.setMonth(nx.getMonth() + 1);
  const day = `${nx.getFullYear()}년 ${nx.getMonth() + 1}월 ${nx.getDate()}일`;
  ok("다음 결제일이 그만큼 뒤로 밀린다", txt().includes("다음 결제일" + day), txt());
}

console.log("\n── 그냥 이용 중인 사람 ──");
{
  const txt = await open("?plan=member", () => putSub({
    status: "active", plan: "basic", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: Date.now() + 20 * DAY, cancelAtPeriodEnd: false, readsSincePay: 1,
  }));
  ok("결제 화면 대신 '이미 이용 중' 으로 막힌다", /이미 이용 중/.test(txt()), txt().slice(0, 60));
  ok("결제 단추는 없다", !/결제하고 시작하기/.test(txt()));
  ok("요금제 변경 안내가 없다 — 해지와 환불만", /해지와 환불은 구독 관리에서/.test(txt()) && !/플랜 변경/.test(txt()), txt().slice(0, 120));
}

console.log("\n── 요금제를 잘못 짚었을 때 ──");
{
  const txt = await open("?plan=zzz");
  ok("안내 화면이 나온다", /요금제를 찾을 수 없습니다/.test(txt()), txt().slice(0, 60));
  ok("회전자에서 멈추지 않는다", !/불러오는 중/.test(txt()));
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n${pass} PASS  ${fail} FAIL`);
process.exit(fail ? 1 : 0);
