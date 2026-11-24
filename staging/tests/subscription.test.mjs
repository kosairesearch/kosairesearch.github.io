/* ============================================================
   스테이징 구독 관리 — 화면·계산 회귀 테스트
   ------------------------------------------------------------
   왜 있는가. 구독 관리를 설정 창으로 옮기면서 화면은 그럴듯한데 로직이
   빠진 판을 두 번 냈다. 눈으로 볼 수 없는 것들이라(브라우저가 없다) 눈
   대신 이걸로 본다.

   2026-11-24 요금제 개편(사장 "요금제는 1개 14900원. 열람은 무제한. 7일 이내
   환불할 때는 이용일수만 차감하고 환불. 7일 이후 환불은 이용일수 차감하고
   결제가격의 10%만큼 떼고 환불.")에 맞춰 다시 짰다.

   실행
     npm install --no-save jsdom
     node staging/tests/subscription.test.mjs

   무엇을 보는가
     · 모의 백엔드 계산 — 하루 한도 없음, 자동 수집 제한(60분 60종목), 환불 금액(명세 예시)
     · 구독 칸의 네 가지 상태 — 없음 / 이용 중 / 결제 실패 / 이용 종료
     · 요금제 변경(업그레이드 · 다운그레이드 · 변경 예약)이 화면에도 서버에도 없는가
     · 되돌리기 어려운 동작(해지 · 환불)은 반드시 묻는가
     · 환불 확인 창 — 계산 내역 · 까닭 한 줄 · 환불 기준(7일 안 · 7일 뒤 · 0원)
     · 이용 종료 시점 — 청약철회(withdraw)는 지금, 나머지(early · late)는 오늘 자정
     · 옛 시연 기록(basic · pro · 옛 환불 사유)을 만나도 깨지지 않는가

   실제 파이어베이스에는 붙지 않는다. firebase-config·consent·
   subscription-api 를 대역으로 갈아 끼우고, 나머지는 저장소의 파일
   그대로 읽는다 — 테스트용으로 다시 쓴 사본이 아니다.
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work");

const require_ = createRequire(import.meta.url);
let JSDOM;
try {
  ({ JSDOM } = await import(require_.resolve("jsdom", { paths: [ROOT] })));
} catch (e) {
  console.error("jsdom 이 없습니다.  npm install --no-save jsdom  후 다시 실행하세요.");
  process.exit(2);
}

/* ── 대역을 깐다 ──────────────────────────────────────────────
   gstatic 의 파이어베이스 모듈은 받아올 수 없고 받아올 이유도 없다.
   import 문만 우리 대역으로 돌리고 본문은 손대지 않는다 — 본문을 고치면
   저장소의 파일이 아니라 테스트가 만든 다른 코드를 검사하게 된다. */
rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });

const swap = (name, out) => {
  let s = readFileSync(join(STAGING, name), "utf8");
  s = s.replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-fb.js"');
  s = s.replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub-fb.js"');
  s = s.replace(/from "\.\/consent\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-consent.js"');
  s = s.replace(/from "\.\/subscription-api\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-api.js"');
  writeFileSync(join(TMP, out), s);
};
writeFileSync(join(TMP, "payment-config.js"), readFileSync(join(STAGING, "payment-config.js")));
swap("demo-backend.js", "demo.js");
swap("settings-panel.js", "panel.js");
writeFileSync(join(TMP, "stub-fb.js"), `
export const app = {};
export const auth = { currentUser: { uid: "u1", email: "a@b.c", displayName: "테스터" } };
export const isConfigured = true;
export const SOCIAL = { functionsRegion: "asia-northeast3" };
/* 진짜 파이어베이스는 저장된 세션을 되살린 뒤 콜백을 부른다. 대역이 안 부르면
   paywall 의 ready 가 영원히 안 풀려 화면이 '불러오는 중…' 에서 멈춘다. */
export const onAuthStateChanged = (a, fn) => { Promise.resolve().then(() => fn(a.currentUser)); return () => {}; };
export const signOut = async () => {};
`);
writeFileSync(join(TMP, "stub-consent.js"), `
export const getMarketing = async () => true;
export const setMarketing = async () => {};
export const accountInfo = async u => ({ name: u.displayName, email: u.email });
`);
writeFileSync(join(TMP, "stub-api.js"), `
export const call = (n, d) => window.KOSDemo.call(n, d || {});
`);

/* ── 브라우저 자리를 만든다 ─────────────────────────────────── */
const dom = new JSDOM(
  `<!doctype html><html><head></head><body><button id="themeBtn"></button><div id="mount"></div></body></html>`,
  { url: "https://kosai.kr/staging/Home.html", pretendToBeVisual: true });
const w = dom.window;
for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                 "location", "localStorage", "history", "URL", "URLSearchParams"]) {
  globalThis[k] = w[k];
}
/* stock.html 이 리포트를 여는 길. 정적 JSON 을 받고 fetchPaid 가 유료 구간을
   골라 낸 뒤 열람을 남긴다 — 그 기록이 환불 계산에 닿는지가 이 파일의 핵심이다. */
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "005930", earnings: "실적", outlook: "전망",
  bull: "강세", bear: "약세", risks: "리스크", verdict: "결론" }) });

await import(`file://${join(TMP, "demo.js")}`);
const P = await import(`file://${join(TMP, "panel.js")}`);
const CFG = await import(`file://${join(TMP, "payment-config.js")}`);

/* ── 도구 ──────────────────────────────────────────────────── */
let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};
const DAY = 86400e3, KST = 9 * 3600e3;
const mount = () => document.getElementById("mount");
const txt = () => mount().textContent.replace(/\s+/g, " ").trim();
const btns = () => [...mount().querySelectorAll(".ks-btn")].map(b => b.textContent.trim());
const msg = () => mount().querySelector(".ks-msg").textContent;
const sub = () => JSON.parse(localStorage.getItem("kos-demo-sub") || "null");
const putSub = (s) => localStorage.setItem("kos-demo-sub", JSON.stringify(s));
const settle = async () => { for (let i = 0; i < 25; i++) await new Promise(r => setTimeout(r, 1)); };
const openSubs = async () => { mount().textContent = ""; P.renderSettings(mount(), { tab: "subscription" }); await settle(); };
const click = async label => {
  mount().querySelectorAll(".ks-btn").forEach(b => { if (b.textContent.trim() === label) b.click(); });
  await settle();
};
const dlgs = () => [...document.querySelectorAll(".ks-dlg")];
const dlg = () => dlgs()[dlgs().length - 1] || null;
const dlgText = () => (dlg() ? dlg().textContent.replace(/\s+/g, " ").trim() : "");
const dlgBtns = () => (dlg() ? [...dlg().querySelectorAll("button")].map(b => b.textContent.trim()) : []);
const dlgClick = async label => {
  const b = [...dlg().querySelectorAll("button")].find(x => x.textContent.trim() === label);
  if (!b) throw new Error(`창에 [${label}] 단추가 없다 — ${dlgBtns().join("|")}`);
  b.click();
  await settle();
};
const kstDayNo = (ms) => Math.floor((ms + KST) / DAY);
const endOfToday = () => (kstDayNo(Date.now()) + 1) * DAY - KST;
/* 결제일부터 한 달(서버 · 시연 addMonth 와 같은 식 — 31일이면 다음 달 말일) */
const addMonth = (from) => { const d = new Date(from), day = d.getDate(); d.setMonth(d.getMonth() + 1); if (d.getDate() !== day) d.setDate(0); return d.getTime(); };
const won = (n) => n.toLocaleString("en-US") + "원";

/* 결제한 지 elapsed 일 지난 구독(이용 기간 len 일)을 만든다. 결제 시점(from)도 같이 옮긴다 —
   월 구독은 이용 기간이 시작될 때 받으므로 실제 자료에서 둘은 언제나 같다. 날짜 경계가 어긋나지
   않게 시작 시각을 '한국 시간 정오'에 둔다(오늘 정오 − elapsed 일). */
function setup(elapsed, { len = 30, viewed = false, plan = "member" } = {}) {
  localStorage.clear();
  w.KOSDemo.subscribe(plan);
  const s0 = sub();
  const noonToday = Math.floor((Date.now() + KST) / DAY) * DAY - KST + 12 * 3600e3;
  s0.currentPeriodStart = noonToday - elapsed * DAY;
  s0.currentPeriodEnd = s0.currentPeriodStart + len * DAY;
  s0.periodPayments = s0.periodPayments.map(p => ({ ...p, from: s0.currentPeriodStart }));
  s0.readsSincePay = viewed ? 3 : 0;
  putSub(s0);
  return s0;
}

/* 하나뿐인 요금제 — 명세 1절 */
const PRICE = 14900;
ok("요금제는 멤버십 하나 · 월 14,900원",
   Object.keys(CFG.PLANS).join() === "member" && CFG.PLAN.price === PRICE && CFG.PLAN.name === "멤버십" && CFG.PLAN.nameEn === "Membership",
   JSON.stringify(CFG.PLANS));
ok("옛 요금제 이름(basic · pro)은 멤버십으로 읽는다",
   CFG.planOf("basic").id === "member" && CFG.planOf("PRO").id === "member" && CFG.planOf("zzz") === null);
ok("업그레이드 차액 · 최소 청구액 계산은 없다", !("upgradeDiff" in CFG) && !("MIN_CHARGE" in CFG));

console.log("── 모의 백엔드 계산 ──");

/* 결제 후 한 번도 안 열었으면 전액 환불이다. 예전에는 날짜를 안 가린 종목
   목록을 보고 있어서, 가입 전에 남은 기록 하나만 있어도 전액이 막혔다. */
localStorage.clear();
localStorage.setItem("kos-demo-reads", JSON.stringify({ day: "2020-01-01", tickers: ["005930", "000660"] }));
w.KOSDemo.subscribe("member");
ok("옛 기록이 있어도 결제 후 0개 열람이면 전액 환불",
   (await w.KOSDemo.call("requestRefund", {})).data.refunded === PRICE);

localStorage.clear();
w.KOSDemo.subscribe("member");
ok("가입 직후 오늘 열람 0", w.KOSDemo.readsToday() === 0);
ok("옛 주소로 결제해도(plan=basic) 멤버십이 된다",
   (() => { localStorage.clear(); w.KOSDemo.subscribe("basic"); return sub().plan === "member" && sub().periodPayments[0].amount === PRICE; })(),
   JSON.stringify(sub()));
{
  let bad = false;
  localStorage.clear();
  try { w.KOSDemo.subscribe("zzz"); } catch (e) { bad = true; }
  ok("모르는 요금제로는 결제하지 않는다", bad && !sub());
}

console.log("\n── 구독 없음 ──");
localStorage.clear();
await openSubs();
ok("무료 안내를 보여 준다", txt().includes("무료로 이용하고 계십니다"));
ok("멤버십 보기로 보낸다", btns().includes("멤버십 보기"), btns().join("|"));
ok("해지·환불 버튼은 없다", !btns().includes("해지하기") && !btns().includes("환불 신청하기"));

console.log("\n── 이용 중 ──");
w.KOSDemo.subscribe("member");
await openSubs();
/* ready 는 한 번 resolve 되면 그때의 스냅샷을 영원히 들고 있다. 그걸로 그리면
   결제 전에 창을 한 번 열어 본 사람은 결제 후에도 '무료로 이용하고 계십니다' 를 본다. */
ok("결제했으면 무료라고 하지 않는다", !txt().includes("무료로 이용하고 계십니다"), txt().slice(0, 160));
ok("이용 중인 플랜 멤버십", /이용 중인 플랜\s*멤버십/.test(txt()), txt().slice(0, 160));
ok("결제 금액 14,900원", txt().includes("결제 금액14,900원"), txt().slice(0, 200));
ok("하루 열람 한도 · 오늘 남은 열람을 적지 않는다(한도 없음)",
   !txt().includes("하루 열람 한도") && !txt().includes("남은 열람") && !/\d+개 \/ \d+개/.test(txt()), txt().slice(0, 300));
ok("다음 결제일을 보여 준다", txt().includes("다음 결제일"));
ok("버튼 셋 — 결제 수단 변경하기 · 해지하기 · 환불 신청하기",
   btns().join("|") === "결제 수단 변경하기|해지하기|환불 신청하기", btns().join("|"));
ok("요금제 변경 단추가 없다", !btns().some(b => /업그레이드|BASIC|PRO|변경 취소|요금제 변경/.test(b)), btns().join("|"));
ok("결제 수단 변경은 멤버십 주소로", mount().querySelector('a.ks-btn[href^="checkout.html"]').getAttribute("href") === "checkout.html?plan=member&method=1");
ok("결제 내역을 보여 준다", txt().includes("멤버십 월 구독"));

console.log("\n── 결제 내역 ──");
/* 내역은 미리보기든 실제 서버든 listPayments 라는 같은 이름으로 받는다.
   화면이 어느 쪽에 붙어 있는지 따지지 않게 하려는 것이다. */
{
  const rows = (await w.KOSDemo.call("listPayments", {})).data.items;
  ok("listPayments 로 받아온다", Array.isArray(rows) && rows.length === 1, JSON.stringify(rows).slice(0, 120));
  ok("화면에 월 구독 줄이 있다", txt().includes("멤버십 월 구독"));

  /* 못 받아 왔을 때와 아직 없을 때는 다른 말이어야 한다. 실패를 빈 배열로
     뭉개면 결제한 사람이 '아직 결제 내역이 없습니다' 를 보고 돈이 안 들어간
     줄 안다. */
  const realCall = w.KOSDemo.call;
  w.KOSDemo.call = (n, d) => (n === "listPayments"
    ? Promise.reject(new Error("망가진 척"))
    : realCall(n, d));
  await openSubs();
  ok("못 받아 오면 '결제 내역' 칸이 아예 없다", !txt().includes("결제 내역"), txt().slice(0, 200));
  w.KOSDemo.call = realCall;

  await openSubs();
  ok("다시 받아 오면 칸이 돌아온다", txt().includes("결제 내역"));

  /* 구독이 없어도 지난 내역은 보여야 한다 — 환불하고 나간 사람이 자기 결제를
     확인할 데가 여기뿐이다. */
  const keep = localStorage.getItem("kos-demo-pays");
  localStorage.removeItem("kos-demo-sub");
  await openSubs();
  ok("구독이 없어도 지난 내역은 보인다", txt().includes("멤버십 월 구독"), txt().slice(0, 200));
  localStorage.setItem("kos-demo-pays", keep);
}

/* ── 열람 — 하루 한도 없음 · 자동 수집 제한(명세 2절) ─────────────
   최근 60분 안에 새로 연 서로 다른 종목이 60개에 이르면 61번째 새 종목부터 거절한다.
   오늘 이미 연 종목을 다시 여는 것은 언제나 된다. 60분이 지나 창에서 빠지면 다시 열린다. */
console.log("\n── 열람: 하루 한도 없음 · 자동 수집 제한 ──");
{
  localStorage.clear();
  w.KOSDemo.subscribe("member");
  ok("창 크기 · 문턱은 서버와 같은 60분 · 60종목", CFG.BURST_WINDOW_MIN === 60 && CFG.BURST_MAX === 60);
  let opened = 0;
  for (let i = 1; i <= 60; i++) { try { await w.KOSPaywall.fetchPaid("T" + i); opened++; } catch (e) { break; } }
  ok("예전 하루 한도(5 · 15)를 넘어 60개까지 열린다", opened === 60, "열림=" + opened);
  ok("60번째 새 종목까지 허용", w.KOSDemo.opensInWindow() === 60, String(w.KOSDemo.opensInWindow()));
  let e61 = null;
  await w.KOSPaywall.fetchPaid("T61").catch(e => { e61 = e; });
  ok("61번째 새 종목은 거절한다(resource-exhausted)", e61 && e61.code === "resource-exhausted", e61 && e61.code);
  ok("거절 문구가 명세와 같다",
     e61 && e61.message === "짧은 시간에 리포트를 너무 많이 열어 열람이 잠시 제한되었습니다. 잠시 후 다시 이용하여 주시기 바랍니다.",
     e61 && e61.message);
  ok("거절된 종목은 기록에 남지 않는다", w.KOSDemo.readsToday() === 60, String(w.KOSDemo.readsToday()));
  ok("오늘 이미 연 종목을 다시 여는 것은 된다(새로고침 · 다른 기기)",
     await w.KOSPaywall.fetchPaid("T7").then(() => true).catch(() => false));
  ok("다시 연 것은 창을 더 채우지 않는다", w.KOSDemo.opensInWindow() === 60);

  w.KOSDemo.advance(30 / 1440);
  let e30 = null;
  await w.KOSPaywall.fetchPaid("T62").catch(e => { e30 = e; });
  ok("30분 뒤에도 창이 차 있으면 여전히 거절", e30 && e30.code === "resource-exhausted");

  w.KOSDemo.advance(31 / 1440);     // 처음 연 때부터 61분 — 60개가 모두 창에서 빠진다
  ok("60분이 지나면 창에서 빠진다", w.KOSDemo.opensInWindow() === 0, String(w.KOSDemo.opensInWindow()));
  let more = 0;
  for (let i = 100; i < 160; i++) { try { await w.KOSPaywall.fetchPaid("T" + i); more++; } catch (e) { break; } }
  ok("창이 비면 다시 60개가 열린다 — 하루 열람 종목 수에는 한도가 없다", more === 60 && w.KOSDemo.readsToday() >= 120,
     `더 열림=${more} · 오늘=${w.KOSDemo.readsToday()}`);
}

console.log("\n── 해지는 반드시 묻는다 ──");
localStorage.clear(); w.KOSDemo.subscribe("member");
await openSubs();
await click("해지하기");
ok("확인 대화상자가 뜬다", !!dlg());
ok("사유를 함께 묻는다", dlgText().includes("가격이 부담됩니다"));
ok("창의 단추는 '닫기' · '해지하기'", dlgBtns().join("|") === "닫기|해지하기", dlgBtns().join("|"));
ok("아직 해지되지 않았다", sub().cancelAtPeriodEnd === false);
await dlgClick("닫기");
ok("닫으면 창이 닫힌다", !dlg());
ok("닫으면 구독은 그대로", sub().cancelAtPeriodEnd === false);

await click("해지하기");
dlg().querySelector("input[type=checkbox]").checked = true;
await dlgClick("해지하기");
ok("확인하면 해지 예약", sub().cancelAtPeriodEnd === true);
ok("배지가 '해지 예약됨'", txt().includes("해지 예약됨"));
ok("버튼이 '해지 취소하기'로 뒤집힌다", btns().includes("해지 취소하기") && !btns().includes("해지하기"), btns().join("|"));
ok("'다음 결제일'이 '이용 종료일'로 바뀐다", txt().includes("이용 종료일") && !txt().includes("다음 결제일"));
ok("사유가 접수된다", w.KOSDemo.reasons().some(r => r.category === "구독 해지"));

/* 재개는 되돌리기 쉽다 — 묻지 않는다. 되돌리기 쉬운 것까지 물으면 확인
   대화상자가 흔해지고, 정작 물어야 할 때 그냥 누르게 된다. */
await click("해지 취소하기");
ok("해지 취소는 묻지 않고 바로 처리", sub().cancelAtPeriodEnd === false);

console.log("\n── 요금제 변경은 없다 ──");
{
  let code = "";
  await w.KOSDemo.call("changePlan", { plan: "pro" }).catch(e => { code = e.code; });
  ok("changePlan 은 모르는 요청으로 거절한다", code === "not-found", code || "그냥 진행됨");
  ok("구독은 그대로 멤버십", sub().plan === "member" && !("pendingPlan" in sub()), JSON.stringify(sub()));
  /* 오늘 연 리포트 수는 서버처럼 {active, plan, used} 로만 준다 — 한도(limit) 칸이 없다 */
  const u = (await w.KOSDemo.call("getUsage", {})).data;
  ok("오늘 열람 수(getUsage)에 한도 칸이 없다", u.active === true && u.plan === "member" && typeof u.used === "number" && !("limit" in u),
     JSON.stringify(u));
}

/* ── 환불 금액 — 명세 3절의 예시 ─────────────────────────────
   P = 14,900 · 이용 기간 30일. fee = floor(P × 이용일수 ÷ 30) · 위약금 = floor(P × 10%) = 1,490.
     3일째 · 열람 있음   14,900 − 1,490            = 13,410  early
     10일째               14,900 − 4,966 − 1,490    =  8,444  late
     27일째               14,900 − 13,410 − 1,490   =      0  실행 거절
     2일째 · 열람 없음    14,900                    전액    withdraw */
console.log("\n── 환불 금액: 명세 예시 ──");
{
  setup(2, { viewed: true });
  let q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("3일째 · 열람 있음 → 13,410원 (early)", q.amount === 13410 && q.why === "early", JSON.stringify(q));
  ok("계산 내역을 함께 준다 — 결제금액 · 이용일수/기간 · 이용료 · 위약금",
     q.price === PRICE && q.usedDays === 3 && q.totalDays === 30 && q.fee === 1490 && q.penalty === 0,
     JSON.stringify(q));
  ok("사유 글(reason)은 서버가 카드 취소에 적는 글과 같다", q.reason === "7일 이내 환불(이용일수 차감)", q.reason);
  let r = (await w.KOSDemo.call("requestRefund", { expectAmount: q.amount })).data;
  ok("실행해도 같은 금액", r.refunded === 13410 && r.amount === 13410, JSON.stringify(r));
  ok("early → 오늘 자정까지 이용", r.endsAt === endOfToday() && w.KOSPaywall.state().active === true,
     String(new Date(r.endsAt)));
  ok("자정 전까지는 리포트를 더 열 수 있다",
     await w.KOSPaywall.fetchPaid("000660").then(() => true).catch(() => false));

  setup(9, { viewed: true });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("10일째 → 8,444원 (late)", q.amount === 8444 && q.why === "late", JSON.stringify(q));
  ok("10일째 계산 내역 — 이용료 4,966 · 위약금 1,490",
     q.usedDays === 10 && q.totalDays === 30 && q.fee === 4966 && q.penalty === 1490, JSON.stringify(q));
  r = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("late 실행 → 8,444원 · 오늘 자정까지", r.refunded === 8444 && r.endsAt === endOfToday(), JSON.stringify(r));

  setup(9, { viewed: false });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("7일이 지나면 열람이 없어도 위약금을 뺀다 (10일째 · 열람 없음 → 8,444원)",
     q.amount === 8444 && q.why === "late", JSON.stringify(q));

  setup(26, { viewed: true });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("27일째 → 0원 (미리 보기는 0원을 그대로 알려 준다)", q.amount === 0 && q.fee === 13410 && q.penalty === 1490, JSON.stringify(q));
  let e0 = null;
  await w.KOSDemo.call("requestRefund", {}).catch(e => { e0 = e; });
  ok("0원이면 환불 신청을 실행하지 않는다", e0 && e0.code === "failed-precondition" && e0.message === "환불 가능한 금액이 없습니다.",
     e0 ? `${e0.code} · ${e0.message}` : "그냥 진행됨");
  ok("0원 — 돈도 구독도 그대로", w.KOSDemo.payments().every(p => p.kind !== "refund") && !sub().refundedAt && sub().cancelAtPeriodEnd === false);

  setup(1, { viewed: false });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("2일째 · 열람 없음 → 14,900원 전액 (withdraw)", q.amount === PRICE && q.why === "withdraw" && q.fee === 0 && q.penalty === 0,
     JSON.stringify(q));
  ok("withdraw 는 오늘 몫을 받지 않는다", q.chargedToday === false);
  r = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("withdraw → 이용은 지금 끝난다", r.refunded === PRICE && r.endsAt <= Date.now() + 1000 && w.KOSPaywall.state().active === false,
     JSON.stringify(r));

  /* 7일 경계 — 결제일부터 7일 이내(초일불산입). 8일째(경과 7일)까지는 위약금이 없다. */
  setup(7, { viewed: true });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("8일째(경과 7일)는 아직 7일 이내 — 위약금 없음", q.why === "early" && q.penalty === 0 && q.amount === PRICE - Math.floor(PRICE * 8 / 30),
     JSON.stringify(q));
  setup(8, { viewed: true });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("9일째(경과 8일)부터 위약금", q.why === "late" && q.penalty === 1490 && q.amount === PRICE - Math.floor(PRICE * 9 / 30) - 1490,
     JSON.stringify(q));
  setup(7, { viewed: false });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("8일째 · 열람 없음은 전액(청약철회)", q.why === "withdraw" && q.amount === PRICE, JSON.stringify(q));

  /* 다른 길이의 이용 기간 — 이용 기간의 일수로 나눈다(28~31일) */
  setup(2, { viewed: true, len: 31 });
  q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("31일 기간 3일째 → 이용료 floor(14,900×3÷31)", q.totalDays === 31 && q.fee === Math.floor(PRICE * 3 / 31) && q.amount === PRICE - q.fee,
     JSON.stringify(q));

  /* 환불 안내의 예시 금액이 실제 계산과 같은가 — 안내만 남고 계산이 바뀌면 고지가 거짓이 된다 */
  const ex = CFG.REFUND_NOTICE.ko.notes.find(n => n.startsWith("예)")) || "";
  ok("환불 안내의 예시 금액(13,410 · 8,444)이 계산과 같다",
     ex.includes(won(13410)) && ex.includes(won(8444)), ex);
}

console.log("\n── 환불 뒤에는 아무것도 하지 않는다 ──");
{
  setup(2, { viewed: true });
  await w.KOSDemo.call("requestRefund", {});
  for (const fn of ["requestRefund", "cancelSubscription", "refundPreview"]) {
    let blocked = false;
    await w.KOSDemo.call(fn, {}).catch(() => { blocked = true; });
    ok(`환불 뒤 ${fn} 거절`, blocked);
  }
  await openSubs();
  ok("환불 뒤 화면은 '환불 완료'", txt().includes("환불 완료"), txt().slice(0, 200));
  ok("환불 뒤 해지·환불 버튼 없음",
     !btns().includes("해지하기") && !btns().includes("환불 신청하기"), btns().join("|"));
  ok("환불 뒤 언제까지인지 말해 준다", txt().includes("오늘 자정까지"), txt().slice(0, 260));
  ok("내역의 환불 줄은 '환불 · 이용분 차감'", txt().includes("환불 · 이용분 차감"), txt().slice(0, 400));
}

/* ── 환불 확인 창 ─────────────────────────────────────────────
   누르기 전에 얼마가 왜 돌아가는지 보여 준다 — 계산 내역(결제금액 · 이용일수 · 이용료 ·
   위약금 · 환불 금액), 그 까닭 한 줄, 결제 화면 · 자주 묻는 질문과 같은 환불 기준. */
console.log("\n── 환불 확인 창 ──");
const NOTICE = CFG.REFUND_NOTICE.ko;
const hasNotice = () => [NOTICE.lead, ...NOTICE.steps, ...NOTICE.notes].every(x => dlgText().includes(x));
const kv = () => {   // 계산 내역 — dt → dd
  const out = {};
  const dl = dlg() && dlg().querySelector(".ks-dlg-kv");
  if (!dl) return out;
  const dts = [...dl.querySelectorAll("dt")], dds = [...dl.querySelectorAll("dd")];
  dts.forEach((d, i) => { out[d.textContent.trim()] = (dds[i] || {}).textContent; });
  return out;
};
{
  /* 7일 안 · 열람 없음 — 가입 당일 */
  localStorage.clear(); w.KOSDemo.subscribe("member");
  await openSubs();
  await click("환불 신청하기");
  ok("환불도 묻는다", !!dlg());
  ok("창의 제목", dlg().querySelector(".ks-dlg-t").textContent === "환불을 신청하시겠습니까?");
  ok("환불 사유를 묻는다", dlgText().includes("실수로 결제했습니다"));
  ok("확인 창에 환불 금액이 나온다", dlgText().includes("14,900원이 환불됩니다"), dlgText().slice(0, 160));
  ok("청약철회는 즉시 종료된다고 적는다", dlgText().includes("이용은 신청 즉시 종료됩니다"));
  ok("왜 전액인지 한 줄", dlgText().includes("결제 후 리포트의 유료 영역을 열람하지 않으셔서 전액 환불합니다"));
  const k1 = kv();
  ok("계산 내역 — 결제금액 · 이용일수 · 이용료 · 위약금 · 환불 금액",
     Object.keys(k1).join("|") === "결제금액|이용일수|이용료|위약금|환불 금액", Object.keys(k1).join("|"));
  ok("계산 내역 값(전액)", k1["결제금액"] === "14,900원" && /^1일 \/ (28|29|30|31)일$/.test(k1["이용일수"])
     && k1["이용료"] === "0원" && k1["위약금"] === "0원" && k1["환불 금액"] === "14,900원", JSON.stringify(k1));
  ok("환불 기준(명세 4절 안내)을 함께 보여 준다", hasNotice(), dlgText().slice(-300));
  ok("플랜 변경 안내는 없다", !/플랜 변경|업그레이드/.test(dlgText()));
  ok("창의 단추는 '닫기' · '환불 신청하기'", dlgBtns().join("|") === "닫기|환불 신청하기", dlgBtns().join("|"));
  await dlgClick("환불 신청하기");
  ok("환불 금액을 알려 준다", /14,900원/.test(msg()), msg());
  ok("언제 끝나는지도 알려 준다", /지금 종료/.test(msg()), msg());
  ok("환불하면 화면이 '환불 완료'", txt().includes("환불 완료"), txt().slice(0, 200));
  ok("내역의 환불 줄은 '환불 · 청약철회'", txt().includes("환불 · 청약철회"));

  /* 7일 안 · 열람 있음 — 3일째 */
  setup(2, { viewed: true });
  await openSubs();
  await click("환불 신청하기");
  const k2 = kv();
  ok("7일 안 — 13,410원이 환불된다고 적는다", dlgText().includes("13,410원이 환불됩니다"), dlgText().slice(0, 160));
  ok("7일 안 — 오늘 자정까지 이용", dlgText().includes("오늘 자정까지 이용하실 수 있습니다"));
  ok("7일 안 — 까닭 한 줄", dlgText().includes("결제일부터 7일 이내에 신청하셔서 결제금액에서 이용하신 날의 이용료를 뺀 금액을 환불합니다"));
  ok("7일 안 — 계산 내역", k2["이용일수"] === "3일 / 30일" && k2["이용료"] === "-1,490원" && k2["위약금"] === "0원" && k2["환불 금액"] === "13,410원",
     JSON.stringify(k2));
  await dlgClick("닫기");
  ok("닫으면 환불하지 않는다", !sub().refundedAt);

  /* 7일 뒤 — 10일째 */
  setup(9, { viewed: true });
  await openSubs();
  await click("환불 신청하기");
  const k3 = kv();
  ok("7일 뒤 — 8,444원", dlgText().includes("8,444원이 환불됩니다"), dlgText().slice(0, 160));
  ok("7일 뒤 — 까닭 한 줄(위약금)", dlgText().includes("결제일부터 7일이 지나 결제금액에서 이용하신 날의 이용료와 결제금액의 10%(위약금)를 뺀 금액을 환불합니다"));
  ok("7일 뒤 — 계산 내역", k3["이용일수"] === "10일 / 30일" && k3["이용료"] === "-4,966원" && k3["위약금"] === "-1,490원" && k3["환불 금액"] === "8,444원",
     JSON.stringify(k3));
  await dlgClick("환불 신청하기");
  ok("7일 뒤 — 실행 금액도 8,444원 · 자정까지", /8,444원/.test(msg()) && /오늘 자정까지/.test(msg()), msg());
  ok("내역의 환불 줄은 '환불 · 이용분 · 위약금 차감'", txt().includes("환불 · 이용분 · 위약금 차감"), txt().slice(0, 500));

  /* 0원 — 27일째. 환불 단추 대신 해지를 안내한다 */
  setup(26, { viewed: true });
  await openSubs();
  await click("환불 신청하기");
  ok("0원 — 창이 뜬다", !!dlg());
  ok("0원 — 명세 문구", dlgText().includes("환불 가능한 금액이 없습니다. 해지하시면 다음 결제일부터 이용료가 청구되지 않습니다."),
     dlgText().slice(0, 200));
  ok("0원 — 환불 단추 대신 해지를 안내한다", dlgBtns().join("|") === "닫기|해지하기", dlgBtns().join("|"));
  ok("0원 — 계산 내역은 보여 준다", kv()["환불 금액"] === "0원" && kv()["위약금"] === "-1,490원", JSON.stringify(kv()));
  ok("0원 — 환불 기준도 보여 준다", hasNotice());
  await dlgClick("해지하기");
  ok("0원 → 해지하기 — 해지 확인 창으로 이어진다", !!dlg() && dlgText().includes("구독을 해지하시겠습니까?"), dlgText().slice(0, 120));
  await dlgClick("해지하기");
  ok("0원 → 해지 예약 · 환불은 없다", sub().cancelAtPeriodEnd === true && !sub().refundedAt
     && w.KOSDemo.payments().every(p => p.kind !== "refund"), JSON.stringify(sub()));

  /* 0원 · 해지가 이미 예약된 구독 — 할 일이 없으니 닫기만 */
  await openSubs();
  await click("환불 신청하기");
  ok("0원 · 해지 예약 — 예약돼 있다고 적는다",
     dlgText().includes("환불 가능한 금액이 없습니다. 해지가 예약되어 있어 다음 결제일부터 이용료가 청구되지 않습니다."), dlgText().slice(0, 200));
  ok("0원 · 해지 예약 — 단추는 닫기 하나", dlgBtns().join("|") === "닫기", dlgBtns().join("|"));
  await dlgClick("닫기");

  /* 견적을 못 받아도 신청은 막지 않는다 — 금액만 못 적는다 */
  setup(2, { viewed: true });
  await openSubs();
  const realCall = w.KOSDemo.call;
  w.KOSDemo.call = (n, d) => (n === "refundPreview" ? Promise.reject(new Error("망가진 척")) : realCall(n, d));
  await click("환불 신청하기");
  ok("견적이 없으면 기준을 적고 묻는다", !!dlg() && dlgText().includes("환불 금액은 아래 환불 기준에 따라 산정됩니다") && hasNotice());
  await dlgClick("환불 신청하기");
  w.KOSDemo.call = realCall;
  ok("견적이 없어도 서버가 센 금액으로 환불된다", /13,410원/.test(msg()), msg());
}

/* ── 보여준 금액과 다르면 실행하지 않는다 ──────────────────────
   확인 창을 띄운 뒤 결제 후 처음으로 리포트를 열면 청약철회(전액)가 이용분 차감으로
   바뀐다. 그대로 진행하면 사용자는 본 적 없는 금액을 받는다. 새 금액을 알려 주고 다시
   묻게 해야 한다. */
console.log("\n── 확인한 금액으로만 환불한다 ──");
{
  setup(2, { viewed: false });
  const q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("견적은 돈을 건드리지 않는다",
     w.KOSDemo.payments().filter(p => p.kind === "refund").length === 0);
  ok("열람 전 견적은 전액", q.amount === PRICE && q.why === "withdraw", JSON.stringify(q));

  await w.KOSPaywall.fetchPaid("005930");     // 확인 창을 본 뒤 리포트를 처음 열었다

  let blocked = "";
  await w.KOSDemo.call("requestRefund", { expectAmount: q.amount })
    .catch(e => { blocked = e.message; });
  ok("금액이 달라지면 실행하지 않는다", /변경되었습니다/.test(blocked), blocked || "그냥 진행됨");
  ok("돈은 나가지 않았다",
     w.KOSDemo.payments().filter(p => p.kind === "refund").length === 0);
  ok("구독도 그대로다", !sub().refundedAt);

  const q2 = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("새 금액은 이용분을 뺀 13,410원", q2.amount === 13410 && q2.why === "early", JSON.stringify(q2));
  const r = (await w.KOSDemo.call("requestRefund", { expectAmount: q2.amount })).data;
  ok("새 금액으로는 환불된다", r.refunded === q2.amount, String(r.refunded));
  ok("서버와 같은 이름(amount)으로도 준다", r.amount === q2.amount);
}

console.log("\n── 환불한 날 다시 시작하기 ──");
/* 리포트를 연 뒤 환불하면 오늘 몫을 받아 자정까지 살아 있다. 그걸 '이용 중' 으로 보면
   요금제 화면이 '구독 관리' 로 보내고, 그 화면은 다시 요금제로 보낸다 —
   마음이 바뀐 사람이 나갈 데가 없는 고리에 갇힌다. */
{
  localStorage.clear();
  w.KOSDemo.subscribe("member");
  await w.KOSPaywall.fetchPaid("005930");        // 결제 후 열람 — 환불은 이용분 차감(early)
  const s1 = sub(), tot = kstDayNo(s1.currentPeriodEnd) - kstDayNo(s1.currentPeriodStart);
  const r0 = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("열람 뒤 당일 환불은 하루치 이용료를 뺀다", r0.refunded === PRICE - Math.floor(PRICE / tot), `${r0.refunded}원 · 이용 기간 ${tot}일`);
  await openSubs();
  ok("환불 뒤 화면이 다시 시작할 길을 준다", btns().includes("다시 시작하기"), btns().join("|"));
  ok("환불 뒤에도 자정까지는 이용 중", w.KOSPaywall.state().active === true);

  // 같은 날 다시 결제
  w.KOSDemo.subscribe("member");
  await openSubs();
  ok("다시 결제하면 '이용 중'", txt().includes("이용 중") && !txt().includes("환불 완료"), txt().slice(0, 200));
  ok("환불 표시가 지워진다", sub().refundedAt === undefined, JSON.stringify(sub().refundedAt));
  ok("버튼이 다시 셋", btns().join("|") === "결제 수단 변경하기|해지하기|환불 신청하기", btns().join("|"));

  /* 새 구독이니 해지가 다시 되어야 한다. 환불 표시가 남아 있으면 서버가 전부
     거절해서, 방금 돈을 낸 사람이 아무것도 못 한다. */
  let blocked = false;
  await w.KOSDemo.call("cancelSubscription", {}).catch(() => { blocked = true; });
  ok("다시 결제한 구독은 해지가 된다", blocked === false);
  await w.KOSDemo.call("resumeSubscription", {});

  /* 새 구독은 오늘부터 시작한다. 겹치는 하루는 기간 끝에 붙여 돌려준다. */
  ok("새 구독은 오늘부터",
     sub().currentPeriodStart <= Date.now() + 60000,
     new Date(sub().currentPeriodStart).toISOString());
  ok("겹친 하루만큼 기간 끝이 뒤로 밀린다(오늘 자정부터 한 달)",
     Math.abs(sub().currentPeriodEnd - addMonth(endOfToday())) < 60000 && sub().currentPeriodEnd > addMonth(Date.now()),
     new Date(sub().currentPeriodEnd).toISOString());

  /* 새 이용 기간에 같은 종목을 다시 연 것도 '결제 후 열람' 이다 — 아니면 그 종목을 읽고도
     청약철회 전액을 받는다. */
  ok("새 기간은 열람 0에서 시작", (sub().readsSincePay || 0) === 0);
  await w.KOSPaywall.fetchPaid("005930");        // 오늘 이미 연 종목 — 막지 않고, 열람으로 센다
  ok("오늘 이미 연 종목을 다시 열어도 새 기간의 열람으로 센다", (sub().readsSincePay || 0) > 0);
  const q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("그래서 전액(청약철회)이 아니라 이용분 차감", q.why === "early", JSON.stringify(q));

  // 지난 결제와 환불은 내역에 그대로 남는다
  const rows = (await w.KOSDemo.call("listPayments", {})).data.items;
  ok("내역에 결제 2건·환불 1건", rows.length === 3, JSON.stringify(rows.map(r => r.kind)));

  /* 열람 없이 환불하면(청약철회) 이전 구독은 그 자리에서 끝난다.
     겹치는 하루가 없으므로 기간도 늘어나지 않는다 — 그냥 한 달이다. */
  localStorage.clear();
  w.KOSDemo.subscribe("member");
  const plainEnd = sub().currentPeriodEnd;         // 겹침 없는 보통 한 달
  await w.KOSDemo.call("requestRefund", {});      // 열람 없음 → 즉시 종료
  w.KOSDemo.subscribe("member");
  ok("청약철회로 환불했으면 새 구독은 지금부터",
     sub().currentPeriodStart <= Date.now() + 60000,
     new Date(sub().currentPeriodStart).toISOString());
  ok("겹치는 하루가 없으니 기간도 안 늘어난다",
     Math.abs(sub().currentPeriodEnd - plainEnd) < 60000,
     `${new Date(plainEnd).toISOString()} → ${new Date(sub().currentPeriodEnd).toISOString()}`);
}

console.log("\n── 결제 실패 ──");
localStorage.clear(); w.KOSDemo.subscribe("member"); w.KOSDemo.simulate("past_due");
await openSubs();
/* 카드가 거절된 유료 회원에게 '무료로 이용하고 계십니다' 를 보여 주면, 자기가 왜 못
   보는지도 카드를 어떻게 고치는지도 알 수 없다. */
ok("무료라고 하지 않는다", !txt().includes("무료로 이용하고 계십니다"), txt().slice(0, 160));
ok("배지가 '결제 실패'", txt().includes("결제 실패"));
ok("왜 막혔는지 설명한다", txt().includes("승인되지 않았습니다"));
/* 카드 재등록과 해지, 둘뿐이다. 해지를 빼면 재시도를 멈출 방법이 없어진다. */
ok("카드 재등록과 해지, 둘만 준다", btns().join("|") === "결제 수단 변경하기|해지하기", btns().join("|"));
ok("언제 다시 시도하는지 알려 준다", txt().includes("1일·3일·5일·7일째"), txt().slice(0, 400));
{
  /* 해지하면 재시도가 멈추고 그 자리에서 끝난다 — 예약이 아니다. */
  const r = await w.KOSDemo.call("cancelSubscription", {});
  const s = sub();
  ok("해지하면 재시도가 멈춘다", r.data.stopped === true && s.status === "expired",
     JSON.stringify({ stopped: r.data.stopped, status: s.status }));
  ok("재시도 일정이 지워진다", s.retryCount === undefined && s.failedAt === undefined,
     JSON.stringify({ retryCount: s.retryCount, failedAt: s.failedAt }));
}

console.log("\n── 이용 종료 ──");
localStorage.clear(); w.KOSDemo.subscribe("member"); w.KOSDemo.simulate("expired");
await openSubs();
ok("배지가 '이용 종료됨'", txt().includes("이용 종료됨"), txt().slice(0, 160));
ok("다시 시작할 길을 준다", btns().includes("멤버십 보기"), btns().join("|"));

/* ── 옛 시연 기록 ─────────────────────────────────────────────
   개편 전에 스테이징을 눌러 본 브라우저에는 basic · pro 구독, 변경 예약(pendingPlan),
   업그레이드 차액 결제, 옛 환불 사유(used · left)가 남아 있다. 깨지지 않고 멤버십으로 읽혀야 한다. */
console.log("\n── 옛 시연 기록 ──");
{
  localStorage.clear();
  const start = Date.now() - 3 * DAY;
  putSub({ status: "active", plan: "pro", pendingPlan: "basic", currentPeriodStart: start, currentPeriodEnd: start + 30 * DAY,
           cancelAtPeriodEnd: false, startedAt: start, readsSincePay: 4,
           card: { company: "", number: "0000-00**-****-0000" },
           periodPayments: [{ key: "a", amount: 9900, from: start }, { key: "b", amount: 3870, from: start + DAY }] });
  localStorage.setItem("kos-demo-pays", JSON.stringify([
    { createdAt: start - 40 * DAY, paidAt: start - 40 * DAY, amount: -5000, kind: "refund", why: "used", status: "refunded", plan: "basic" },
    { createdAt: start - 39 * DAY, paidAt: start - 39 * DAY, amount: -3000, kind: "refund", why: "left", status: "refunded", plan: "pro" },
    { createdAt: start + DAY, paidAt: start + DAY, amount: 3870, kind: "upgrade", description: "PRO 업그레이드 차액 (모의)", status: "paid", plan: "pro" },
    { createdAt: start, paidAt: start, amount: 9900, kind: "subscription", status: "paid", plan: "basic" },
  ]));
  ok("옛 구독도 멤버십으로 읽는다", w.KOSPaywall.state().plan === "member", String(w.KOSPaywall.state().plan));
  await openSubs();
  ok("화면의 요금제는 멤버십", /이용 중인 플랜\s*멤버십/.test(txt()), txt().slice(0, 160));
  ok("변경 예약은 적지 않는다", !txt().includes("예정된 변경") && !/BASIC|PRO/.test(txt()), txt().slice(0, 300));
  ok("옛 환불 사유 이름표가 남아 있다", txt().includes("환불 · 이용분 차감") && txt().includes("환불 · 잔여 기간"), txt().slice(-400));
  ok("옛 차액 결제 줄은 '요금제 변경 차액'", txt().includes("요금제 변경 차액"), txt().slice(-400));
  ok("옛 결제 줄도 '멤버십 월 구독'", txt().includes("멤버십 월 구독"));

  /* 환불은 실제로 받은 돈(9,900 + 3,870)을 P 로 쓰고, 취소는 결제 건마다 그 건의 금액 안에서 나눠 낸다 */
  const q = (await w.KOSDemo.call("refundPreview", {})).data;
  const P0 = 9900 + 3870, want = P0 - Math.floor(P0 * 4 / 30);
  ok("P 는 이번 기간에 실제로 받은 돈", q.price === P0 && q.amount === want && q.why === "early", JSON.stringify(q));
  const before = w.KOSDemo.payments().filter(p => p.kind === "refund").length;
  const r = (await w.KOSDemo.call("requestRefund", { expectAmount: q.amount })).data;
  const rows = w.KOSDemo.payments().filter(p => p.kind === "refund").slice(0, w.KOSDemo.payments().filter(p => p.kind === "refund").length - before);
  ok("취소가 결제 건마다 따로 나간다", rows.length === 2, JSON.stringify(rows.map(p => p.amount)));
  /* 최근 건(3,870원)부터 취소한다 — 그 건은 통째로, 나머지는 첫 건(9,900원)에서 */
  const amts = rows.map(p => -p.amount).sort((a, b) => a - b);
  ok("각 취소는 그 결제 건의 금액을 넘지 않는다", amts[0] <= 3870 && amts[1] <= 9900 && amts.includes(3870), JSON.stringify(rows.map(p => p.amount)));
  ok("취소 합계 = 환불 금액", rows.reduce((a, b) => a - b.amount, 0) === r.refunded, `${rows.reduce((a, b) => a - b.amount, 0)} vs ${r.refunded}`);

  // 옛 구독이 갱신되면 멤버십 값으로
  localStorage.clear();
  putSub({ status: "active", plan: "basic", pendingPlan: "pro", currentPeriodStart: Date.now() - 31 * DAY, currentPeriodEnd: Date.now() - 1000,
           cancelAtPeriodEnd: false, readsSincePay: 0, periodPayments: [{ key: "a", amount: 9900, from: Date.now() - 31 * DAY }] });
  w.KOSDemo.runRenewal();
  ok("옛 구독의 갱신은 멤버십 14,900원", sub().plan === "member" && !("pendingPlan" in sub()) && sub().periodPayments[0].amount === PRICE,
     JSON.stringify(sub()));
}

console.log("\n── 스크롤바 ──");
{
  /* 구독 칸은 결제 내역이 붙어 창보다 길어진다. 기본 스크롤바는 바탕이 밝아
     어두운 창을 세로로 가르는 밝은 줄이 하나 더 생겼다. 바탕을 지우고 손잡이만
     남긴다.

     이 검사는 눈으로 대신 못 한다 — 고치는 자리(헤드리스 크로미움)는 겹치는
     스크롤바를 써서 화면에도 스크린샷에도 아예 안 나온다. 그래서 규칙이
     제자리에 있는지를 글자로 본다. */
  const css = document.getElementById("kos-settings-css").textContent;
  ok("바탕이 없다 — 손잡이 색과 '투명'을 함께 준다",
     /scrollbar-color:var\(--ks-thumb\) transparent/.test(css));
  ok("손잡이 색이 두 테마 모두 있다",
     /--ks-thumb:rgba\(0,0,0,\.28\)/.test(css) && /--ks-thumb:rgba\(255,255,255,\.26\)/.test(css));
  ok("넘치는 칸마다 굵기를 준다(scrollbar-width 는 물려받지 않는다)",
     /\.ks-nav,\.ks-panel,\.ks-hist,\.ks-dlg-card\{scrollbar-width:thin\}/.test(css));
  ok("scrollbar-color 를 모르는 곳(사파리)에도 바탕이 없다",
     /::-webkit-scrollbar-track[^{]*\{background:transparent\}/.test(css));
  ok("그 길에서도 손잡이는 같은 색",
     /::-webkit-scrollbar-thumb[^{]*\{[\s\S]{0,80}background:var\(--ks-thumb\)/.test(css));
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
