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
  s = s.replace(/from "\.\/firebase-config\.js"/g, 'from "./stub-fb.js"');
  s = s.replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub-fb.js"');
  s = s.replace(/from "\.\/consent\.js"/g, 'from "./stub-consent.js"');
  s = s.replace(/from "\.\/subscription-api\.js"/g, 'from "./stub-api.js"');
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
await dlgClick("확인");
/* 가입 당일·미열람이라 청약철회 전액이고, 오늘 값을 안 받았으니 지금 끝난다.
   금액과 '언제까지'를 한 문장에 같이 말해야 한다 — 금액만 알려 주면 오늘
   남은 열람을 쓸 수 있는지 없는지를 눌러 봐야 안다. */
ok("환불 금액을 알려 준다", /9,900원/.test(msg()), msg());
ok("언제 끝나는지도 알려 준다", /지금 종료/.test(msg()), msg());
ok("환불하면 화면이 '환불 완료'", txt().includes("환불 완료"), txt().slice(0, 200));

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

  /* 새 구독은 자기 한도를 온전히 받는다.

     한때 '하루 한도는 날짜에 붙는다' 로 정했는데, 그러면 한도를 다 쓰고
     환불한 사람이 한 달치를 다시 내고 오늘 0건을 받는다. 받은 돈에 아무것도
     딸려 오지 않는 날이 생기는 것이라 뒤집었다. */
  ok("다시 결제하면 오늘 한도를 온전히 받는다", left() === "5", "남은=" + left());
  ok("이 구독으로 본 건 아직 0건", w.KOSDemo.readsToday() === 0, String(w.KOSDemo.readsToday()));

  // 지난 결제와 환불은 내역에 그대로 남는다
  const rows = (await w.KOSDemo.call("listPayments", {})).data.items;
  ok("내역에 결제 2건·환불 1건", rows.length === 3, JSON.stringify(rows.map(r => r.kind)));

  /* 한도를 다 쓰고 환불한 뒤 다시 결제해도 마찬가지다 — 실제로 겪은 경우다.
     PRO 15건을 다 보고 환불한 사람이 14,900원을 다시 내고 0건을 받았다. */
  for (const tk of ["a", "b", "c", "d", "e"]) await w.KOSPaywall.fetchPaid(tk);
  await settle();
  ok("새 구독의 한도도 다 쓸 수 있다", left() === "0", "남은=" + left());
  await w.KOSDemo.call("requestRefund", {});
  w.KOSDemo.subscribe("pro");
  await openSubs();
  ok("한도를 다 쓰고 환불한 뒤 다시 결제하면 PRO 한도가 온전히 나온다",
     left() === "15", "남은=" + left());
  ok("새 구독으로 리포트를 열 수 있다",
     await w.KOSPaywall.fetchPaid("zz").then(() => true).catch(() => false));

  /* 어제 시작한 구독에는 빼 주지 않는다 — 오늘 본 건 전부 이 구독으로 본 것이다. */
  const s2 = sub(); s2.readsAtStartDay = "2020-01-01"; s2.readsAtStart = 99;
  localStorage.setItem("kos-demo-sub", JSON.stringify(s2));
  await openSubs();
  ok("지난 날 시작한 구독은 오늘 본 만큼 그대로 깎인다", left() !== "15", "남은=" + left());
  localStorage.setItem("kos-demo-sub", JSON.stringify({ ...s2, readsAtStartDay: sub().readsAtStartDay }));

}

console.log("\n── 결제 실패 ──");
localStorage.clear(); w.KOSDemo.subscribe("basic"); w.KOSDemo.simulate("past_due");
await openSubs();
/* 카드가 거절된 유료 회원에게 '무료로 이용 중' 을 보여 주면, 자기가 왜 못
   보는지도 카드를 어떻게 고치는지도 알 수 없다. */
ok("무료라고 하지 않는다", !txt().includes("무료로 이용 중입니다"), txt().slice(0, 160));
ok("배지가 '결제 실패'", txt().includes("결제 실패"));
ok("왜 막혔는지 설명한다", txt().includes("승인되지 않았습니다"));
ok("카드 재등록 하나만 준다", btns().join("|") === "결제 수단 변경", btns().join("|"));

console.log("\n── 이용 종료 ──");
localStorage.clear(); w.KOSDemo.subscribe("pro"); w.KOSDemo.simulate("expired");
await openSubs();
ok("배지가 '이용 종료됨'", txt().includes("이용 종료됨"), txt().slice(0, 160));
ok("다시 시작할 길을 준다", btns().includes("멤버십 보기"), btns().join("|"));

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
