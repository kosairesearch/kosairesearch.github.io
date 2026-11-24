/* ============================================================
   결제 규칙 명세표가 실제와 맞는가 — 상태 7 × 동작 8

   왜 있는가. 표를 만들어 놓고 코드가 그대로 도는지는 눈으로만 확인했다.
   표와 코드가 갈라지면 표가 거짓말이 되고, 우리는 거짓말을 보고 판단하게 된다.

   그래서 표를 그대로 코드로 옮겨 놓고, 상태마다 동작을 실제로 눌러 본다.
   기대와 다르면 실패한다 — 표가 틀렸거나 코드가 틀렸거나 둘 중 하나다.

   '자동 갱신'은 여기서 다루지 않는다. 미리보기에는 갱신 배치가 없다(브라우저에
   크론이 없다). 그쪽은 functions/tests/renew.test.mjs 가 본다.

   2026-11-24 요금제 개편 — 요금제는 멤버십 하나다. 플랜 올리기 · 내리기 · 변경 예약(상태 D)은
   없앴고, '요금제 변경'(changePlan)은 어느 상태에서도 거절되는지 본다. 대신 '환불 금액 0원'(H —
   27일째)을 더했다 — 환불은 실행하지 않고 해지는 된다.

   실행
     npm install --no-save jsdom
     node staging/tests/spec-table.test.mjs
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const STAGING = join(HERE, "..");
const ROOT = join(STAGING, "..");
const TMP = join(HERE, ".work-spec");

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
writeFileSync(TMP + "/payment-config.js", readFileSync(STAGING + "/payment-config.js"));
writeFileSync(TMP + "/demo.js", readFileSync(STAGING + "/demo-backend.js", "utf8")
  .replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"'));
writeFileSync(TMP + "/panel.js", readFileSync(STAGING + "/settings-panel.js", "utf8")
  .replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"')
  .replace(/from "\.\/consent\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-consent.js"')
  .replace(/from "\.\/subscription-api\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-api.js"'));
writeFileSync(TMP + "/stub-consent.js", `
export const getMarketing = async () => true;
export const setMarketing = async () => {};
export const accountInfo = async u => ({ name: u.displayName, email: u.email });
`);
writeFileSync(TMP + "/stub-api.js", `
export const call = (n, d) => window.KOSDemo.call(n, d || {});
`);
writeFileSync(TMP + "/stub.js", `
export const app={}; export const isConfigured=true; export const SOCIAL={};
export const auth={currentUser:{uid:"u1",email:"a@b.c",displayName:"t"}};
export const onAuthStateChanged=(a,fn)=>{Promise.resolve().then(()=>fn(a.currentUser));return()=>{}};
export const signOut = async () => {};`);

const dom = new JSDOM(
  `<!doctype html><body><button id="themeBtn"></button><div id="mount"></div></body>`,
  { url: "https://kosai.kr/staging/x.html", pretendToBeVisual: true });
for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                 "location", "localStorage", "URL", "URLSearchParams"]) globalThis[k] = dom.window[k];
globalThis.fetch = async () => ({ ok: true, json: async () => ({
  ticker: "x", earnings: "e", outlook: "o", bull: "b", bear: "b", risks: "r", verdict: "v" }) });
await import(`file://${TMP}/demo.js`);
const P = await import(`file://${TMP}/panel.js`);

const D = window.KOSDemo, PW = window.KOSPaywall;
const SUB = "kos-demo-sub";
const sub = () => JSON.parse(localStorage.getItem(SUB) || "null");
const put = (s) => localStorage.setItem(SUB, JSON.stringify(s));

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) { pass++; }
  else { fail++; console.log("  FAIL " + n + (x ? "\n         " + x : "")); }
};

/* ── 상태 만들기 ──────────────────────────────────────────── */
async function setup(state) {
  localStorage.clear();
  if (state === "A") return;                       // 무료 — 구독 없음
  D.subscribe("member");
  if (state === "B") return;                       // 이용 중
  if (state === "C") { await D.call("cancelSubscription", {}); return; }
  if (state === "H") {                             // 환불 금액 0원 — 30일 기간의 27일째, 열람 있음
    const s = sub(), DAY = 86400e3, noon = Math.floor((Date.now() + 9 * 3600e3) / DAY) * DAY - 9 * 3600e3 + 12 * 3600e3;
    s.currentPeriodStart = noon - 26 * DAY; s.currentPeriodEnd = s.currentPeriodStart + 30 * DAY;
    s.periodPayments = s.periodPayments.map((p) => ({ ...p, from: s.currentPeriodStart }));
    s.readsSincePay = 5; put(s);
    return;
  }
  if (state === "E") { D.simulate("past_due"); return; }
  if (state === "F") {                             // 환불 완료 — 오늘 1건 봐서 자정까지 살아 있음
    await PW.fetchPaid("005930");
    await D.call("requestRefund", {});
    return;
  }
  if (state === "G") { D.simulate("expired"); return; }
  throw new Error("모르는 상태 " + state);
}

/* ── 동작 ───────────────────────────────────────────────── */
const ACTIONS = {
  "구독 시작":   () => D.subscribe("member"),
  "카드 변경":   () => D.updateCard(),
  "해지":        () => D.call("cancelSubscription", {}),
  "해지 취소":   () => D.call("resumeSubscription", {}),
  "환불 신청":   () => D.call("requestRefund", {}),
  "회원 탈퇴":   () => D.call("deleteAccount", {}),
  "리포트 열람": () => PW.fetchPaid("000660"),
  /* 요금제가 하나라 바꿀 데가 없다 — 서버에도 changePlan 이 없다. 어느 상태에서든 거절한다. */
  "요금제 변경": () => D.call("changePlan", { plan: "member" }),
};

/* ── 표 그대로 ──────────────────────────────────────────────
   O 된다 · X 거절한다 · - 그 상태에선 없는 동작(안 본다) */
const TABLE = {
  //                시작 카드 해지 해지취소 환불 탈퇴 열람 요금제변경
  "A 무료":        ["O", "X", "X", "X", "X", "O", "X", "X"],
  "B 이용 중":     ["X", "O", "O", "-", "O", "O", "O", "X"],
  /* C 의 '구독 시작' 은 거절한다. 남은 기간이 그대로 있는 구독 위에 새 결제를
     얹으면 이용 기간이 두 달 가까이 늘어나면서, 받은 돈 기록은 새 한 건으로
     갈아엎어져 첫 달 결제가 환불 대상에서 사라진다. 되돌리는 길은 '해지 취소'
     이며 공짜다. */
  "C 해지 예약":   ["X", "O", "-", "O", "O", "O", "O", "X"],
  /* E 의 '해지' 는 된다. 카드가 거절되면 1·3·5·7일째에 다시 결제를 시도하므로,
     그만두려는 사람에게 멈출 방법이 있어야 한다. 예약이 아니라 즉시 종료다 —
     이미 낸 달은 다 썼고 다음 달 값은 받지 못해, 남겨서 지킬 기간이 없다. */
  "E 결제 실패":   ["O", "O", "O", "X", "X", "O", "X", "X"],
  /* F 의 '리포트 열람' 은 된다 — 열람한 뒤 환불하면 오늘 몫을 받아 오늘 자정까지 열어 둔다. */
  "F 환불 완료":   ["O", "X", "X", "X", "X", "O", "O", "X"],
  "G 이용 종료":   ["O", "X", "X", "X", "X", "O", "X", "X"],
  /* H 는 계산한 환불 금액이 0원이다(27일째) — 환불은 실행하지 않고(더 청구하지도 않는다), 해지는 된다. */
  "H 환불 0원":    ["X", "O", "O", "-", "X", "O", "O", "X"],
};
const NAMES = Object.keys(ACTIONS);

console.log("── 표 56칸을 실제로 눌러 본다 ──\n");

const grid = [];
for (const [stateName, want] of Object.entries(TABLE)) {
  const code = stateName[0];
  const row = [];
  for (let i = 0; i < NAMES.length; i++) {
    const act = NAMES[i], expect = want[i];
    if (expect === "-") { row.push("-"); continue; }

    await setup(code);
    let got = "O", err = "";
    try { await ACTIONS[act](); }
    catch (e) { got = "X"; err = (e && e.message) || String(e); }

    row.push(got === expect ? got : `${got}!`);
    ok(`${stateName} · ${act}`, got === expect,
       `표에는 ${expect === "O" ? "된다" : "거절한다"} 인데 실제로는 ` +
       (got === "O" ? "됐다" : `거절했다 — "${err}"`));
  }
  grid.push([stateName, row]);
}

/* 결과를 표로 다시 그려 준다 — 어긋난 칸에 ! 가 붙는다 */
const w = Math.max(...NAMES.map((n) => n.length), 12);
console.log("  " + "상태".padEnd(14) + NAMES.map((n) => n.padEnd(13)).join(""));
console.log("  " + "─".repeat(14 + NAMES.length * 13));
for (const [name, row] of grid) {
  console.log("  " + name.padEnd(14) + row.map((c) => c.padEnd(13)).join(""));
}

/* ── 거절할 때 무슨 말을 하는가 ──────────────────────────────
   메시지가 바뀌면 화면이 다른 안내를 하게 된다. 표에 적어 둔 문구와 맞는지 본다. */
console.log("\n── 거절 문구 ──\n");
const MSG = [
  ["A", "카드 변경",   () => D.updateCard(),                          "이용 중인 구독이 없습니다."],
  ["A", "해지",        () => D.call("cancelSubscription", {}),         "이용 중인 구독이 없습니다."],
  ["B", "구독 시작",   () => D.subscribe("member"),                    "이미 이용 중인 구독이 있습니다."],
  ["C", "구독 시작",   () => D.subscribe("member"),                    "해지가 예약된 구독이 있습니다. 구독 관리에서 해지를 취소해 주시기 바랍니다."],
  ["E", "환불 신청",   () => D.call("requestRefund", {}),              "이용 중인 구독이 없습니다."],
  /* 환불을 다시 누르면 서버와 같이 '이미 환불이 완료되었습니다.' — 해지 · 해지 취소는 '환불이 완료된 구독입니다.' */
  ["F", "환불 신청",   () => D.call("requestRefund", {}),              "이미 환불이 완료되었습니다."],
  ["F", "해지",        () => D.call("cancelSubscription", {}),         "환불이 완료된 구독입니다."],
  ["G", "해지",        () => D.call("cancelSubscription", {}),         "이용 중인 구독이 없습니다."],
  ["H", "환불 신청",   () => D.call("requestRefund", {}),              "환불 가능한 금액이 없습니다."],
];
for (const [st, act, run, want] of MSG) {
  await setup(st);
  let msg = "(거절하지 않았다)";
  try { await run(); } catch (e) { msg = (e && e.message) || String(e); }
  const good = msg === want;
  ok(`${st} · ${act} 문구`, good, `기대 "${want}" · 실제 "${msg}"`);
  console.log(`  ${good ? "PASS" : "FAIL"}  ${st} · ${act.padEnd(10)} "${msg}"`);
}

/* ── 화면이 그 상태를 뭐라고 보여 주는가 ─────────────────────
   계산이 맞아도 화면이 다른 말을 하면 소용없다. 상태마다 설정 창을 실제로
   그려서 상태 배지와 버튼을 본다.

   특히 '환불 완료' 는 status 가 그대로 "active" 라(오늘 값을 받은 환불은
   자정까지 살아 있다) 그것만 보면 '이용 중' 과 해지·플랜 변경 버튼을 그대로
   보여 주게 된다. 실제로 그랬던 적이 있다.
   ─────────────────────────────────────────────────────────── */
console.log("\n── 상태마다 화면이 뭐라고 하는가 ──\n");
const mount = () => document.getElementById("mount");
const settle = async () => { for (let i = 0; i < 30; i++) await new Promise((r) => setTimeout(r, 1)); };
const draw = async () => {
  mount().textContent = "";
  P.renderSettings(mount(), { tab: "subscription" });
  await settle();
};
const txt = () => mount().textContent.replace(/\s+/g, " ").trim();
const btns = () => [...mount().querySelectorAll(".ks-btn")].map((b) => b.textContent.trim());

const SCREEN = [
  ["A", "무료로 이용하고 계십니다", ["멤버십 보기"],                         ["해지하기", "환불 신청하기"]],   /* 요금제 화면으로 가는 단추는 G 와 같은 이름(2026-10-03) */
  ["B", "이용 중",         ["결제 수단 변경하기", "해지하기", "환불 신청하기"], ["다시 시작하기", "해지 취소하기"]],
  ["C", "해지 예약됨",     ["해지 취소하기", "환불 신청하기"],                ["해지하기"]],
  ["E", "결제 실패",       ["결제 수단 변경하기", "해지하기"],               ["환불 신청하기"]],
  ["F", "환불 완료",       ["다시 시작하기"],                                ["해지하기", "환불 신청하기"]],
  /* 끝난 구독은 '멤버십 보기' 다. 환불 직후(F)만 '다시 시작하기' 로 다르게
     적는다 — 마음이 바뀐 사람에게 필요한 건 요금표 구경이 아니라 결제로 가는
     길이라서다. 둘 다 요금제 화면으로 간다. */
  ["G", "이용 종료됨",     ["멤버십 보기"],                                  ["해지하기", "환불 신청하기"]],
  /* 환불 금액이 0원이어도 '환불 신청하기' 는 남긴다 — 누르면 계산 내역과 함께 '환불 가능한 금액이 없습니다' 와 해지를 안내한다 */
  ["H", "이용 중",         ["해지하기", "환불 신청하기"],                    ["다시 시작하기"]],
];
for (const [code, badge, must, mustNot] of SCREEN) {
  await setup(code);
  await draw();
  const t = txt(), b = btns();
  ok(`${code} 화면이 "${badge}" 로 적는다`, t.includes(badge), t.slice(0, 140));
  for (const x of must) ok(`${code} 화면에 [${x}] 가 있다`, b.some((y) => y === x), b.join(" | "));
  for (const x of mustNot) ok(`${code} 화면에 [${x}] 가 없다`, !b.some((y) => y === x), b.join(" | "));
  /* 요금제 변경 단추(업그레이드 · 다운그레이드 · 변경 취소)는 어느 상태에도 없다 */
  ok(`${code} 화면에 요금제 변경 단추가 없다`, !b.some((y) => /업그레이드|BASIC|PRO|변경 취소|요금제 변경|플랜 변경/.test(y)), b.join(" | "));
  /* 하루 열람 한도는 없다 — 어느 상태에서도 한도 · 남은 열람을 적지 않는다 */
  ok(`${code} 화면에 하루 한도가 없다`, !/하루 열람 한도|남은 열람/.test(t), t.slice(0, 200));
  console.log(`  ${code}  ${badge.padEnd(12)} ${b.join(" · ")}`);
}

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
