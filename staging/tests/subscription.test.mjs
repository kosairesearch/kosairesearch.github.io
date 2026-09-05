/* ============================================================
   스테이징 구독 관리 — 화면·계산 회귀 테스트
   ------------------------------------------------------------
   왜 있는가. 구독 관리를 설정 창으로 옮기면서 화면은 그럴듯한데 로직이
   빠진 판을 두 번 냈다. 눈으로 볼 수 없는 것들이라(브라우저가 없다) 눈
   대신 이걸로 본다.

   실행
     npm install --no-save jsdom
     node staging/tests/subscription.test.mjs

   무엇을 보는가
     · 모의 백엔드 계산 — 열람 차감, 한도, 환불 금액
     · 구독 칸의 네 가지 상태 — 없음 / 이용 중 / 결제 실패 / 이용 종료
     · 되돌리기 어려운 동작은 반드시 묻는가(해지·환불·플랜 변경)
     · 리포트를 열면 남은 열람이 창을 안 닫아도 줄어드는가

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
   골라 낸 뒤 한도를 차감한다 — 그 차감이 화면에 닿는지가 이 파일의 핵심이다. */
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "005930", earnings: "실적", outlook: "전망",
  bull: "강세", bear: "약세", risks: "리스크", verdict: "결론" }) });

await import(`file://${join(TMP, "demo.js")}`);
const P = await import(`file://${join(TMP, "panel.js")}`);

/* ── 도구 ──────────────────────────────────────────────────── */
let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; console.log("PASS  " + n); }
  else { fail++; console.log("FAIL  " + n + (x ? "  ← " + x : "")); }
};
const mount = () => document.getElementById("mount");
const txt = () => mount().textContent.replace(/\s+/g, " ").trim();
const btns = () => [...mount().querySelectorAll(".ks-btn")].map(b => b.textContent.trim());
const msg = () => mount().querySelector(".ks-msg").textContent;
const left = () => (txt().match(/오늘 남은 열람\s*(\d+)개 ?\/ ?(\d+)개/) || [])[1];
const sub = () => JSON.parse(localStorage.getItem("kos-demo-sub") || "null");
const settle = async () => { for (let i = 0; i < 25; i++) await new Promise(r => setTimeout(r, 1)); };
const openSubs = async () => { mount().textContent = ""; P.renderSettings(mount(), { tab: "subscription" }); await settle(); };
const click = async label => {
  mount().querySelectorAll(".ks-btn").forEach(b => { if (b.textContent.trim() === label) b.click(); });
  await settle();
};
const dlg = () => document.querySelector(".ks-dlg");
const dlgClick = async label => {
  [...dlg().querySelectorAll("button")].find(b => b.textContent.trim() === label).click();
  await settle();
};

console.log("── 모의 백엔드 계산 ──");

/* 결제 후 한 번도 안 열었으면 전액 환불이다. 예전에는 날짜를 안 가린 종목
   목록을 보고 있어서, 가입 전에 남은 기록 하나만 있어도 전액이 막혔다.
   결제 화면과 약관에 '7일 이내에 열람하지 않으셨다면 전액 환불' 이라고
   적어 두었으므로, 적은 것과 계산이 달라서는 안 된다. */
localStorage.clear();
localStorage.setItem("kos-demo-reads", JSON.stringify({ day: "2020-01-01", tickers: ["005930", "000660"] }));
w.KOSDemo.subscribe("basic");
ok("옛 기록이 있어도 결제 후 0개 열람이면 전액 환불",
   (await w.KOSDemo.call("requestRefund", {})).data.refunded === 9900);

localStorage.clear();
w.KOSDemo.subscribe("basic");
ok("가입 직후 오늘 열람 0", w.KOSDemo.readsToday() === 0);

console.log("\n── 구독 없음 ──");
localStorage.clear();
await openSubs();
ok("무료 안내를 보여 준다", txt().includes("무료로 이용 중입니다"));
ok("플랜 보기로 보낸다", btns().includes("플랜 보기"), btns().join("|"));
ok("해지·환불 버튼은 없다", !btns().includes("구독 해지") && !btns().includes("환불 신청"));

console.log("\n── 이용 중 ──");
w.KOSDemo.subscribe("basic");
await openSubs();
/* ready 는 한 번 resolve 되면 그때의 스냅샷을 영원히 들고 있다. 그걸로 그리면
   결제 전에 창을 한 번 열어 본 사람은 결제 후에도 '무료로 이용 중' 을 본다. */
ok("결제했으면 무료라고 하지 않는다", !txt().includes("무료로 이용 중입니다"), txt().slice(0, 160));
ok("이용 중인 플랜 BASIC", /이용 중인 플랜\s*BASIC/.test(txt()));
ok("하루 한도와 남은 열람을 보여 준다", txt().includes("하루 열람 한도") && left() === "5");
ok("다음 결제일을 보여 준다", txt().includes("다음 결제일"));
ok("버튼 네 개", btns().join("|") === "PRO로 업그레이드|결제 수단 변경|구독 해지|환불 신청", btns().join("|"));
ok("결제 내역을 보여 준다", txt().includes("BASIC 월 구독"));

console.log("\n── 결제 내역 ──");
/* 내역은 미리보기든 실제 서버든 listPayments 라는 같은 이름으로 받는다.
   화면이 어느 쪽에 붙어 있는지 따지지 않게 하려는 것이다. */
{
  const rows = (await w.KOSDemo.call("listPayments", {})).data.items;
  ok("listPayments 로 받아온다", Array.isArray(rows) && rows.length === 1, JSON.stringify(rows).slice(0, 120));
  ok("화면에 월 구독 줄이 있다", txt().includes("BASIC 월 구독"));

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
  ok("구독이 없어도 지난 내역은 보인다", txt().includes("BASIC 월 구독"), txt().slice(0, 200));
  localStorage.setItem("kos-demo-pays", keep);
  w.KOSDemo.subscribe("basic");
  await openSubs();
}

console.log("\n── 리포트를 열면 남은 열람이 준다 ──");
await w.KOSPaywall.fetchPaid("005930"); await settle();
ok("창을 안 닫아도 4로 준다", left() === "4", "남은=" + left());
await w.KOSPaywall.fetchPaid("000660"); await settle();
ok("두 개 열면 3", left() === "3", "남은=" + left());
await w.KOSPaywall.fetchPaid("005930"); await settle();
ok("같은 종목 재열람은 차감하지 않는다", left() === "3", "남은=" + left());
await openSubs();
ok("창을 다시 열어도 3", left() === "3", "남은=" + left());
await w.KOSPaywall.fetchPaid("A"); await w.KOSPaywall.fetchPaid("B"); await w.KOSPaywall.fetchPaid("C");
await settle();
ok("한도를 다 쓰면 0", left() === "0", "남은=" + left());
let blocked = false;
await w.KOSPaywall.fetchPaid("D").catch(e => { blocked = e.code === "resource-exhausted"; });
ok("한도를 넘으면 거절한다", blocked);

console.log("\n── 해지는 반드시 묻는다 ──");
localStorage.clear(); w.KOSDemo.subscribe("basic");
await openSubs();
await click("구독 해지");
ok("확인 대화상자가 뜬다", !!dlg());
ok("사유를 함께 묻는다", dlg().textContent.includes("가격이 부담됩니다"));
ok("아직 해지되지 않았다", sub().cancelAtPeriodEnd === false);
await dlgClick("취소");
ok("취소하면 창이 닫힌다", !dlg());
ok("취소하면 구독은 그대로", sub().cancelAtPeriodEnd === false);

await click("구독 해지");
dlg().querySelector("input[type=checkbox]").checked = true;
await dlgClick("확인");
ok("확인하면 해지 예약", sub().cancelAtPeriodEnd === true);
ok("배지가 '해지 예약됨'", txt().includes("해지 예약됨"));
ok("버튼이 '해지 취소'로 뒤집힌다", btns().includes("해지 취소") && !btns().includes("구독 해지"));
ok("'다음 결제일'이 '이용 종료일'로 바뀐다", txt().includes("이용 종료일") && !txt().includes("다음 결제일"));
ok("사유가 접수된다", w.KOSDemo.reasons().some(r => r.category === "구독 해지"));

/* 재개는 되돌리기 쉽다 — 묻지 않는다. 되돌리기 쉬운 것까지 물으면 확인
   대화상자가 흔해지고, 정작 물어야 할 때 그냥 누르게 된다. */
await click("해지 취소");
ok("해지 취소는 묻지 않고 바로 처리", sub().cancelAtPeriodEnd === false);

console.log("\n── 플랜 변경 ──");
await click("PRO로 업그레이드");
ok("업그레이드도 묻는다", !!dlg());
ok("얼마가 청구되는지 보여 준다", /차액/.test(dlg().textContent) && /원/.test(dlg().textContent),
   dlg().textContent.slice(0, 200));
await dlgClick("확인");
ok("확인하면 PRO", sub().plan === "pro");
ok("결과를 알려 준다", /PRO/.test(msg()), msg());
await openSubs();
ok("PRO 는 BASIC 으로 내려가는 길을 준다", btns().includes("BASIC으로 변경"), btns().join("|"));
ok("PRO 한도 15개", left() === "15", "남은=" + left());
await click("BASIC으로 변경");
await dlgClick("확인");
ok("다운그레이드는 다음 결제일부터(지금은 그대로 PRO)", sub().plan === "pro" && sub().pendingPlan === "basic");
ok("예정된 변경을 화면에 적어 둔다", txt().includes("예정된 변경"), txt().slice(0, 300));
await click("변경 취소");
await dlgClick("확인");
ok("예약을 취소할 수 있다", sub().pendingPlan === null);

console.log("\n── 환불: 신청한 날을 셀지 말지 ──");
/* 우리가 파는 단위는 하루다(하루 5건, KST 자정 리셋). 여태 경과 시간을 초 단위로
   나눠 차감해서, 오전에 한 건도 안 보고 환불하면 오늘 값을 내고 5건은 못 봤다.
   이제 오늘 열었으면 오늘을 받고 자정까지 열어 주고, 안 열었으면 안 받고 지금
   끝낸다. 요금제 페이지와 약관에 적어 둔 그대로다. */
{
  const DAY = 86400e3, KST = 9 * 3600e3;
  const setup = (daysAgo) => {
    localStorage.clear();
    w.KOSDemo.subscribe("basic");
    const s0 = sub();
    s0.currentPeriodStart = Date.now() - daysAgo * DAY;
    s0.currentPeriodEnd = s0.currentPeriodStart + 30 * DAY;
    /* 결제 시점도 같이 되돌린다. 월 구독은 주기가 시작될 때 받으므로 실제
       자료에서 이 둘은 언제나 같다 — 주기만 옮기면 '오늘 결제하고 9일 전부터
       쓴 구독' 이라는, 있을 수 없는 자료로 환불을 계산하게 된다. */
    s0.periodPayments = (s0.periodPayments || [])
      .map((p) => ({ ...p, from: s0.currentPeriodStart }));
    localStorage.setItem("kos-demo-sub", JSON.stringify(s0));
    return s0;
  };
  const endOfToday = () => (Math.floor((Date.now() + KST) / DAY) + 1) * DAY - KST;

  // ① 오늘 한 건도 안 봤으면 오늘은 차감하지 않는다
  setup(9);
  let s1 = sub(); s1.readsSincePay = 3;      // 지난 날에는 봤다(전액 환불 대상 아님)
  localStorage.setItem("kos-demo-sub", JSON.stringify(s1));
  let r = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("오늘 0건 → 9일만 차감", r.refunded === Math.floor(9900 * (21 / 30) * 0.9), String(r.refunded));
  ok("오늘 0건 → 이용은 지금 끝난다", r.endsAt <= Date.now() + 1000, String(r.endsAt - Date.now()));
  ok("오늘 0건 → 곧바로 비활성", w.KOSPaywall.state().active === false);

  // ② 오늘 한 건이라도 봤으면 오늘까지 차감하고 오늘까지 열어 준다
  setup(9);
  await w.KOSPaywall.fetchPaid("005930");    // 오늘 1건
  r = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("오늘 1건 → 10일 차감", r.refunded === Math.floor(9900 * (20 / 30) * 0.9), String(r.refunded));
  ok("오늘 1건 → 오늘 자정까지", r.endsAt === endOfToday(), String(new Date(r.endsAt)));
  ok("오늘 1건 → 자정까지는 살아 있다", w.KOSPaywall.state().active === true);
  ok("오늘 1건 → 남은 4건 계속 열 수 있다",
     await w.KOSPaywall.fetchPaid("000660").then(() => true).catch(() => false));

  // ③ 오늘 0건이 오늘 1건보다 많이 돌려받는다 — 하루치만큼
  ok("오늘 0건이 오늘 1건보다 하루치만큼 더 받는다",
     Math.floor(9900 * (21 / 30) * 0.9) - Math.floor(9900 * (20 / 30) * 0.9) > 0);

  // ④ 자정 직전에 0건이어도 오늘 값을 받지 않는다(가장 이상하던 경우)
  setup(9);
  let s4 = sub(); s4.readsSincePay = 3;
  localStorage.setItem("kos-demo-sub", JSON.stringify(s4));
  r = (await w.KOSDemo.call("requestRefund", {})).data;
  ok("시각과 무관하게 오늘 0건이면 안 받는다", r.refunded === Math.floor(9900 * (21 / 30) * 0.9));

  // ⑤ 끝난 구독에는 아무것도 하지 않는다
  setup(9);
  await w.KOSPaywall.fetchPaid("005930");
  await w.KOSDemo.call("requestRefund", {});
  for (const fn of ["requestRefund", "cancelSubscription", "changePlan"]) {
    let blocked = false;
    await w.KOSDemo.call(fn, { plan: "pro" }).catch(() => { blocked = true; });
    ok(`환불 뒤 ${fn} 거절`, blocked);
  }
  await openSubs();
  ok("환불 뒤 화면은 '환불 완료'", txt().includes("환불 완료"), txt().slice(0, 200));
  ok("환불 뒤 해지·플랜 버튼 없음",
     !btns().includes("구독 해지") && !btns().includes("PRO로 업그레이드"), btns().join("|"));
  ok("환불 뒤 언제까지인지 말해 준다", txt().includes("오늘 자정까지"), txt().slice(0, 260));
}

console.log("\n── 환불(화면에서) ──");
/* 앞 블록이 환불까지 끝내 놨다 — 버튼이 없는 상태다. 새 구독으로 다시 깐다. */
localStorage.clear(); w.KOSDemo.subscribe("basic");
await openSubs();
await click("환불 신청");
ok("환불도 묻는다", !!dlg());
ok("환불 사유를 묻는다", dlg().textContent.includes("실수로 결제했습니다"));
/* 누르기 전에 얼마인지 보여 줘야 한다. 여태 "이용하신 일수를 차감해
   산정됩니다" 만 적고 금액은 누른 뒤에야 알려 줬다 — 그 사이에 리포트를 한 건
   열면 확인할 때와 다른 금액이 나갔다. */
ok("확인 창에 환불 금액이 나온다", /9,900원이 환불됩니다/.test(dlg().textContent),
   dlg().textContent.slice(0, 160));
ok("확인 창에 언제 끝나는지도 나온다", /즉시 종료됩니다/.test(dlg().textContent));
ok("플랜 변경이 더 싸다는 것도 알려 준다", /플랜 변경/.test(dlg().textContent));
await dlgClick("확인");
/* 가입 당일·미열람이라 청약철회 전액이고, 오늘 값을 안 받았으니 지금 끝난다.
   금액과 '언제까지'를 한 문장에 같이 말해야 한다 — 금액만 알려 주면 오늘
   남은 열람을 쓸 수 있는지 없는지를 눌러 봐야 안다. */
ok("환불 금액을 알려 준다", /9,900원/.test(msg()), msg());
ok("언제 끝나는지도 알려 준다", /지금 종료/.test(msg()), msg());
ok("환불하면 화면이 '환불 완료'", txt().includes("환불 완료"), txt().slice(0, 200));

/* ── 보여준 금액과 다르면 실행하지 않는다 ──────────────────────
   확인 창을 띄운 뒤 리포트를 한 건 열면 오늘이 이용일로 잡혀 금액이 달라진다.
   그대로 진행하면 사용자는 본 적 없는 금액을 받는다. 새 금액을 알려 주고 다시
   묻게 해야 한다.
   ─────────────────────────────────────────────────────────── */
console.log("\n── 확인한 금액으로만 환불한다 ──");
{
  const DAY = 86400e3;
  localStorage.clear();
  w.KOSDemo.subscribe("basic");
  // 열람 이력이 있는 주기로 만든다(청약철회 전액이 아니라 일수 차감이 되게)
  const s0 = sub();
  s0.currentPeriodStart = Date.now() - 9 * DAY;
  s0.currentPeriodEnd = s0.currentPeriodStart + 30 * DAY;
  s0.readsSincePay = 3;
  s0.periodPayments = s0.periodPayments.map(p => ({ ...p, from: s0.currentPeriodStart }));
  localStorage.setItem("kos-demo-sub", JSON.stringify(s0));

  const q = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("견적은 돈을 건드리지 않는다",
     w.KOSDemo.payments().filter(p => p.kind === "refund").length === 0);
  ok("견적 금액이 오늘 0건 기준", q.amount === Math.floor(9900 * (21 / 30) * 0.9),
     String(q.amount));

  // 확인 창을 본 뒤 리포트를 한 건 열었다 → 오늘이 이용일로 잡힌다
  await w.KOSPaywall.fetchPaid("005930");

  let blocked = "";
  await w.KOSDemo.call("requestRefund", { expectAmount: q.amount })
    .catch(e => { blocked = e.message; });
  ok("금액이 달라지면 실행하지 않는다", /변경되었습니다/.test(blocked), blocked || "그냥 진행됨");
  ok("돈은 나가지 않았다",
     w.KOSDemo.payments().filter(p => p.kind === "refund").length === 0);
  ok("구독도 그대로다", !sub().refundedAt);

  // 새 금액으로 다시 확인하면 진행된다
  const q2 = (await w.KOSDemo.call("refundPreview", {})).data;
  ok("새 금액은 하루치만큼 적다", q2.amount < q.amount, `${q.amount} → ${q2.amount}`);
  const r = (await w.KOSDemo.call("requestRefund", { expectAmount: q2.amount })).data;
  ok("새 금액으로는 환불된다", r.refunded === q2.amount, String(r.refunded));
  ok("서버와 같은 이름(amount)으로도 준다", r.amount === q2.amount);
}

console.log("\n── 환불한 날 다시 시작하기 ──");
/* 환불하면 오늘 값을 받은 경우 자정까지 살아 있다. 그걸 '이용 중' 으로 보면
   요금제 화면이 '구독 관리' 로 보내고, 그 화면은 다시 요금제로 보낸다 —
   마음이 바뀐 사람이 나갈 데가 없는 고리에 갇힌다. */
{
  localStorage.clear();
  w.KOSDemo.subscribe("basic");
  await w.KOSPaywall.fetchPaid("005930");        // 오늘 1건 — 오늘 값을 받는다
  await w.KOSPaywall.fetchPaid("000660");        // 오늘 2건
  await w.KOSDemo.call("requestRefund", {});
  await openSubs();
  ok("환불 뒤 화면이 다시 시작할 길을 준다", btns().includes("다시 시작하기"), btns().join("|"));
  ok("환불 뒤에도 자정까지는 이용 중", w.KOSPaywall.state().active === true);

  // 같은 날 다시 결제
  w.KOSDemo.subscribe("basic");
  await openSubs();
  ok("다시 결제하면 '이용 중'", txt().includes("이용 중") && !txt().includes("환불 완료"), txt().slice(0, 200));
  ok("환불 표시가 지워진다", sub().refundedAt === undefined, JSON.stringify(sub().refundedAt));
  ok("버튼이 다시 네 개", btns().join("|") === "PRO로 업그레이드|결제 수단 변경|구독 해지|환불 신청", btns().join("|"));

  /* 새 구독이니 해지·플랜 변경이 다시 되어야 한다. 환불 표시가 남아 있으면
     서버가 전부 거절해서, 방금 돈을 낸 사람이 아무것도 못 한다. */
  let blocked = false;
  await w.KOSDemo.call("cancelSubscription", {}).catch(() => { blocked = true; });
  ok("다시 결제한 구독은 해지가 된다", blocked === false);
  await w.KOSDemo.call("resumeSubscription", {});

  /* 새 구독은 오늘부터 시작한다. 겹치는 하루는 기간 끝에 붙여 돌려준다.

     오늘 리포트를 봤으면 오늘 요금은 이미 환불에서 차감했고 그 구독이 자정까지
     살아 있다. 거기에 새 구독까지 오늘부터 시작하니 같은 하루를 두 번 내는
     셈인데, 그 하루를 앞에서 빼지 않고 뒤에 붙인다.

     하루 한도는 날짜에 붙으므로 오늘 남은 열람은 '리셋' 이 아니다. 같은 플랜을
     다시 샀으면 2건 봤으니 3건이 남는다 — 재결제로 하루 한도를 늘릴 수 없다. */
  ok("오늘 남은 열람은 리셋되지 않는다", left() === "3", "남은=" + left());
  ok("새 구독은 오늘부터",
     sub().currentPeriodStart <= Date.now() + 60000,
     new Date(sub().currentPeriodStart).toISOString());
  ok("겹친 하루만큼 기간 끝이 뒤로 밀린다",
     sub().currentPeriodEnd > Date.now() + 30 * 86400e3,
     new Date(sub().currentPeriodEnd).toISOString());

  // 지난 결제와 환불은 내역에 그대로 남는다
  const rows = (await w.KOSDemo.call("listPayments", {})).data.items;
  ok("내역에 결제 2건·환불 1건", rows.length === 3, JSON.stringify(rows.map(r => r.kind)));

  /* 오늘 하루 총 열람이 플랜 한도를 넘지 않는다 — 이게 이 규칙의 핵심이다.
     환불·재결제를 반복해도 오늘 열 수 있는 건수는 늘지 않는다. */
  let more = 0;
  for (let i = 0; i < 20; i++) {
    try { await w.KOSPaywall.fetchPaid("z" + i); more++; } catch (e) { break; }
  }
  await settle();
  ok("재결제 뒤에도 오늘 총 열람은 BASIC 한도 5건", 2 + more === 5, `2 + ${more}`);

  /* 한도를 다 쓰고 환불한 뒤 같은 플랜으로 다시 결제하는 경우. 오늘은 0건이다.
     대신 기간이 하루 길어져, 실제로 쓸 수 있는 날 수는 여느 한 달과 같다.
     '한 달치를 내고 아무것도 못 받는' 것이 아니라는 것을 여기서 못 박는다. */
  await w.KOSDemo.call("requestRefund", {});
  const endBefore = sub().currentPeriodEnd;
  w.KOSDemo.subscribe("basic");
  await openSubs();
  ok("한도를 다 쓴 날 같은 플랜으로 재결제하면 오늘은 0건", left() === "0", "남은=" + left());
  ok("대신 못 쓴 오늘만큼 기간이 길어진다",
     sub().currentPeriodEnd > endBefore + 29 * 86400e3,
     `${new Date(endBefore).toISOString()} → ${new Date(sub().currentPeriodEnd).toISOString()}`);

  /* 더 큰 플랜으로 올려 재결제하면 오늘 한도도 그 플랜 것이 된다.
     BASIC 5건을 다 쓰고 PRO 로 가면 오늘 10건이 더 열린다 — 이건 구멍이
     아니다. 오늘 총 열람이 15건으로 PRO 한도를 넘지 않고, 값도 제대로
     치렀다(플랜 변경 업그레이드가 차액만 받는 것보다 오히려 비싸다). */
  await w.KOSDemo.call("requestRefund", {});
  w.KOSDemo.subscribe("pro");
  await openSubs();
  ok("PRO 로 올려 재결제하면 오늘 남은 10건", left() === "10", "남은=" + left());
  let extra = 0;
  for (let i = 0; i < 20; i++) {
    try { await w.KOSPaywall.fetchPaid("p" + i); extra++; } catch (e) { break; }
  }
  ok("오늘 총 열람은 PRO 한도 15건을 넘지 않는다", 5 + extra === 15, `5 + ${extra}`);

  /* 오늘 한 건도 안 보고 환불하면 이전 구독은 그 자리에서 끝난다.
     겹치는 하루가 없으므로 기간도 늘어나지 않는다 — 그냥 한 달이다. */
  localStorage.clear();
  w.KOSDemo.subscribe("basic");
  const plainEnd = sub().currentPeriodEnd;         // 겹침 없는 보통 한 달
  await w.KOSDemo.call("requestRefund", {});      // 오늘 0건 → 즉시 종료
  w.KOSDemo.subscribe("basic");
  await openSubs();
  ok("오늘 0건으로 환불했으면 새 구독은 지금부터",
     sub().currentPeriodStart <= Date.now() + 60000,
     new Date(sub().currentPeriodStart).toISOString());
  ok("그 경우 오늘 한도는 온전히 5건", left() === "5", "남은=" + left());
  ok("겹치는 하루가 없으니 기간도 안 늘어난다",
     Math.abs(sub().currentPeriodEnd - plainEnd) < 60000,
     `${new Date(plainEnd).toISOString()} → ${new Date(sub().currentPeriodEnd).toISOString()}`);
}

/* ── 환불하지 말고 그냥 플랜을 올리는 길 ────────────────────────
   플랜만 바꾸려는 사람이 환불부터 누르면 한 달치를 새로 낸다. 업그레이드는
   남은 기간의 차액만 받고 바로 적용된다 — 어느 쪽이 나은지 숫자로 못 박는다.
   ─────────────────────────────────────────────────────────── */
console.log("\n── 환불 없이 업그레이드 ──");
{
  localStorage.clear();
  w.KOSDemo.subscribe("basic");
  await w.KOSPaywall.fetchPaid("a1");
  await w.KOSPaywall.fetchPaid("a2");
  await openSubs();
  ok("BASIC 2건 열람 — 오늘 남은 3건", left() === "3", "남은=" + left());

  const endBefore = sub().currentPeriodEnd;
  const r = await w.KOSDemo.call("changePlan", { plan: "pro" });
  await openSubs();

  ok("PRO 정가가 아니라 차액만 청구한다",
     r.data.charged > 0 && r.data.charged < 14900, "청구=" + r.data.charged);
  ok("업그레이드는 바로 적용된다", sub().plan === "pro");
  ok("오늘 남은 열람이 PRO 한도로 늘어난다 (15 − 2 = 13)", left() === "13", "남은=" + left());
  ok("이용 기간은 그대로다 — 새로 한 달을 사는 게 아니다",
     Math.abs(sub().currentPeriodEnd - endBefore) < 60000);

  let more = 0;
  for (let i = 0; i < 20; i++) {
    try { await w.KOSPaywall.fetchPaid("u" + i); more++; } catch (e) { break; }
  }
  ok("실제로 13건이 더 열린다", more === 13, "더 열림=" + more);
  ok("오늘 총 열람은 PRO 한도 15건", 2 + more === 15, `2 + ${more}`);
}

/* ── 업그레이드하고 나서 환불하면 ─────────────────────────────
   여기가 오래 틀려 있었다. 한 주기에 결제가 둘인데(월 구독 + 차액) 환불이
   그걸 한 덩어리로 봤다.

     ① 서버는 정가(14,900원)를 기준으로 삼았다 — 받은 적 없는 돈이다.
        미리보기는 실제로 받은 돈을 썼다. 두 쪽이 다른 답을 냈다.
     ② 취소는 결제 건 하나만 가리켰다. 그 건보다 큰 금액을 취소하려 드니
        카드사가 통째로 거절한다 — 업그레이드한 사람은 환불이 아예 안 됐다.
     ③ 차액에서도 지나간 날을 뺐다. 그 날들에는 옛 플랜을 썼지 새 플랜을
        쓴 적이 없다. 787원을 덜 돌려줬다.
   ─────────────────────────────────────────────────────────── */
console.log("\n── 업그레이드하고 나서 환불 ──");
{
  const DAY = 86400e3;
  localStorage.clear();
  w.KOSDemo.subscribe("basic");

  // 7일 전에 결제한 것으로 돌린다(결제 시점도 같이 — 실제 자료에서 둘은 같다)
  const s0 = sub();
  const paidAt = Date.now() - 7 * DAY;
  s0.currentPeriodStart = paidAt;
  s0.currentPeriodEnd = paidAt + 31 * DAY;
  s0.readsSincePay = 12;                       // 일주일 동안 봤다
  s0.periodPayments = s0.periodPayments.map(p => ({ ...p, from: paidAt }));
  localStorage.setItem("kos-demo-sub", JSON.stringify(s0));

  const up = (await w.KOSDemo.call("changePlan", { plan: "pro" })).data.charged;
  ok("차액만 청구한다", up === Math.floor(5000 * 24 / 31), "청구=" + up);

  const pp = sub().periodPayments;
  ok("차액도 이번 주기 결제로 남는다", pp.length === 2 && pp[1].amount === up,
     JSON.stringify(pp));
  ok("차액은 '오늘부터' 를 산다고 적어 둔다",
     Math.abs(pp[1].from - Date.now()) < 60000 && pp[0].from === paidAt);

  const r = (await w.KOSDemo.call("requestRefund", {})).data;
  /* 건마다 자기 기간으로 나눠 센다.
       월 구독 9,900원 — 31일을 샀고 7일 썼다     → 9,900 × 24/31
       차액   3,870원 — 오늘부터 24일을 샀고 안 썼다 → 3,870 × 24/24 (전액) */
  const want = Math.floor((9900 * 24 / 31 + up * 24 / 24) * 0.9);
  ok("남은 돈을 건마다 제 기간으로 세어 돌려준다", r.refunded === want,
     `${r.refunded} (기대 ${want})`);

  /* 한 덩어리로 세면 차액에서도 7일을 빼 이만큼 덜 준다. 그 금액이 나오면
     예전 계산으로 돌아간 것이다. */
  const lumped = Math.floor((9900 + up) * 24 / 31 * 0.9);
  ok("한 덩어리로 세던 옛 금액이 아니다", r.refunded !== lumped,
     `옛 계산 ${lumped} · 차이 ${r.refunded - lumped}원`);

  ok("낸 돈보다 많이 돌려주지는 않는다", r.refunded <= 9900 + up,
     `${r.refunded} vs ${9900 + up}`);

  /* 취소를 건마다 나눠 내보내는지. 카드사는 결제 건 하나를 그 건의 금액
     안에서만 취소해 주므로, 한 건에 몰아 내면 거절당한다. */
  const refunds = w.KOSDemo.payments().filter(p => p.kind === "refund");
  ok("취소가 결제 건마다 따로 나간다", refunds.length === 2,
     JSON.stringify(refunds.map(p => p.amount)));
  ok("각 취소는 그 결제 건의 금액을 넘지 않는다",
     refunds.every(rr => {
       const src = pp.find(x => -rr.amount <= x.amount);
       return !!src;
     }) && refunds.every(rr => -rr.amount <= Math.max(...pp.map(x => x.amount))),
     JSON.stringify(refunds.map(p => p.amount)) + " vs " + JSON.stringify(pp.map(x => x.amount)));
  ok("취소 합계가 환불 금액과 같다",
     refunds.reduce((a, b) => a - b.amount, 0) === r.refunded,
     refunds.reduce((a, b) => a - b.amount, 0) + " vs " + r.refunded);
}

console.log("\n── 결제 실패 ──");
localStorage.clear(); w.KOSDemo.subscribe("basic"); w.KOSDemo.simulate("past_due");
await openSubs();
/* 카드가 거절된 유료 회원에게 '무료로 이용 중' 을 보여 주면, 자기가 왜 못
   보는지도 카드를 어떻게 고치는지도 알 수 없다. */
ok("무료라고 하지 않는다", !txt().includes("무료로 이용 중입니다"), txt().slice(0, 160));
ok("배지가 '결제 실패'", txt().includes("결제 실패"));
ok("왜 막혔는지 설명한다", txt().includes("승인되지 않았습니다"));
/* 카드 재등록과 해지, 둘뿐이다. 플랜 변경까지 두면 무엇부터 눌러야 할지가
   흐려지고, 해지를 빼면 재시도를 멈출 방법이 없어진다. */
ok("카드 재등록과 해지, 둘만 준다", btns().join("|") === "결제 수단 변경|구독 해지", btns().join("|"));
ok("언제 다시 시도하는지 알려 준다", txt().includes("1일·3일·5일·7일째"), txt().slice(0, 400));
{
  /* 해지하면 재시도가 멈추고 그 자리에서 끝난다 — 예약이 아니다. */
  const r = await w.KOSDemo.call("cancelSubscription", {});
  const s = JSON.parse(localStorage.getItem("kos-demo-sub"));
  ok("해지하면 재시도가 멈춘다", r.data.stopped === true && s.status === "expired",
     JSON.stringify({ stopped: r.data.stopped, status: s.status }));
  ok("재시도 일정이 지워진다", s.retryCount === undefined && s.failedAt === undefined,
     JSON.stringify({ retryCount: s.retryCount, failedAt: s.failedAt }));
}

console.log("\n── 이용 종료 ──");
localStorage.clear(); w.KOSDemo.subscribe("pro"); w.KOSDemo.simulate("expired");
await openSubs();
ok("배지가 '이용 종료됨'", txt().includes("이용 종료됨"), txt().slice(0, 160));
ok("다시 시작할 길을 준다", btns().includes("멤버십 보기"), btns().join("|"));

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
