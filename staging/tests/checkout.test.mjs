/* ============================================================
   스테이징 결제 화면 — 실제로 그려지는가

   왜 있는가. 결제 화면이 '불러오는 중…' 에서 멈춘 적이 있다. 화면을 그리는
   중에 잘못된 이름을 하나 읽었을 뿐인데, 그러면 아무 말 없이 회전자만 돌고
   사용자는 결제도 못 하고 이유도 모른다. 눈으로 볼 수 없으니 이걸로 본다.

   실행
     npm install --no-save jsdom
     node staging/tests/checkout.test.mjs

   무엇을 보는가
     · 구독이 없는 사람에게 결제 화면이 그려지는가
     · 환불한 날 다시 시작하려는 사람에게도 그려지는가
     · 오늘 리포트를 봐서 자정까지 살아 있는 구독이라면
       '이용 시작일'이 내일로 나오고 안내 문구가 붙는가
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
  s = s.replace(/import "\.\/paywall\.js";/g, "");           // 대역이 이미 깔았다
  s = s.replace(/from "\.\/firebase-config\.js"/g, 'from "./stub-fb.js"');
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
async function open(query, setup) {
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
  if (setup) setup();
  const bust = "?" + Math.random();                 // 창마다 새 모듈로 읽는다
  await import(`file://${join(TMP, "demo.js")}${bust}`);
  await import(`file://${join(TMP, "checkout.js")}${bust}`);
  for (let i = 0; i < 40; i++) await new Promise((r) => setTimeout(r, 1));
  return () => document.getElementById("coApp").textContent.replace(/\s+/g, " ").trim();
}

const SUB_KEY = "kos-demo-sub";
const putSub = (s) => localStorage.setItem(SUB_KEY, JSON.stringify(s));

console.log("── 구독이 없는 사람 ──");
{
  const txt = await open("?plan=pro");
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  ok("회전자에서 멈추지 않는다", !/불러오는 중/.test(txt()), txt().slice(0, 60));
  ok("이용 시작일은 오늘", /이용 시작일오늘/.test(txt()), txt());
}

console.log("\n── 환불했고 오늘은 안 봤다(이용이 이미 끝났다) ──");
{
  const txt = await open("?plan=pro", () => putSub({
    status: "active", plan: "pro", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: Date.now() - 1000, cancelAtPeriodEnd: true,
    refundedAt: Date.now() - 1000, readsSincePay: 0,
  }));
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  ok("이용 시작일은 오늘", /이용 시작일오늘/.test(txt()), txt());
  ok("나중에 시작한다는 안내는 없다", !/새 구독은/.test(txt()));
}

console.log("\n── 환불했지만 오늘 리포트를 봤다(자정까지 살아 있다) ──");
{
  const end = kstEndOfToday();
  const txt = await open("?plan=pro", () => putSub({
    status: "active", plan: "pro", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: end, cancelAtPeriodEnd: true,
    refundedAt: Date.now() - 1000, readsSincePay: 3,
  }));
  ok("결제 화면이 그려진다", /결제하고 시작하기/.test(txt()), txt().slice(0, 60));
  const d = new Date(end);
  const day = `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일`;
  ok("이용 시작일이 이전 구독이 끝난 뒤로 나온다", txt().includes("이용 시작일" + day), txt());
  ok("나중에 시작한다고 미리 알려 준다", /오늘 끝나므로/.test(txt()), txt());
  ok("첫 결제일은 오늘이라고 그대로 말한다", /첫 결제일오늘/.test(txt()), txt());
}

console.log("\n── 그냥 이용 중인 사람 ──");
{
  const txt = await open("?plan=pro", () => putSub({
    status: "active", plan: "basic", currentPeriodStart: Date.now() - 5 * DAY,
    currentPeriodEnd: Date.now() + 20 * DAY, cancelAtPeriodEnd: false, readsSincePay: 1,
  }));
  ok("결제 화면 대신 '이미 이용 중' 으로 막힌다", /이미 이용 중/.test(txt()), txt().slice(0, 60));
  ok("결제 단추는 없다", !/결제하고 시작하기/.test(txt()));
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
