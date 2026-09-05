/* ============================================================
   실사이트 설정 창 — settings-panel.js

   왜 있는가. 이 파일은 브라우저 없이 고친다. 스테이징 창(구독 포함)과
   실사이트 창(구독 없음)이 같은 뼈대를 쓰는데, 한쪽을 고치다 다른 쪽에
   구독 칸을 딸려 보내거나 로그인 게이트를 흘리면 눈으로는 안 보인다.

   보는 것
     · 목록이 일반·알림·계정 셋인가, 구독은 없는가
     · 칸을 옮기면 내용이 실제로 바뀌는가
     · 마케팅 스위치가 누르는 순간 저장되고, 실패하면 되돌아가는가
     · 테마를 바꾸면 문서와 헤더 아이콘이 함께 따라가는가
     · 비회원에게는 '일반' 하나와 로그인 길만 보이는가
     · 목록과 내용을 가르는 선이 두 테마 모두에서 색을 갖는가
       (Settings.html 은 창이 아니라 본문에 펴므로 .ks-card 가 없다.
        --ks-line 을 .ks-main 에도 걸어 두지 않으면 선이 글자색이 된다)

   실행
     npm install --no-save jsdom
     node tests/settings-panel.test.mjs
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createRequire } from "node:module";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const TMP = join(HERE, ".work-settings");

const require_ = createRequire(import.meta.url);
let JSDOM;
try {
  ({ JSDOM } = await import(require_.resolve("jsdom", { paths: [ROOT] })));
} catch (e) {
  console.error("jsdom 이 없습니다.  npm install --no-save jsdom  후 다시 실행하세요.");
  process.exit(2);
}

/* 파이어베이스와 동의 모듈은 갈아 끼운다. 여기서 보려는 것은 창의 짜임새이지
   로그인이 아니다. */
const SRC = readFileSync(join(ROOT, "settings-panel.js"), "utf8");
rmSync(TMP, { recursive: true, force: true });
mkdirSync(TMP, { recursive: true });
writeFileSync(join(TMP, "panel.js"), SRC
  .replace(/from "\.\/firebase-config\.js"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"')
  .replace(/from "\.\/consent\.js"/g, 'from "./stub-consent.js"'));
writeFileSync(join(TMP, "stub-consent.js"), `
let fail = false;
export const _failNext = () => { fail = true; };
export const getMarketing = async () => true;
export const setMarketing = async () => { if (fail) { fail = false; throw new Error("nope"); } };
export const accountInfo = async u => ({ name: u.displayName, email: u.email });`);
writeFileSync(join(TMP, "stub.js"), `
export const app = {}; export const isConfigured = true;
export const auth = { currentUser: { uid: "u1", email: "a@b.c", displayName: "홍길동" } };
export const onAuthStateChanged = (a, fn) => { Promise.resolve().then(() => fn(a.currentUser)); return () => {}; };
export const signOut = async () => {};`);

const dom = new JSDOM(
  `<!doctype html><body><button id="themeBtn"><svg id="themeIcon"></svg></button></body>`,
  { url: "https://kosai.kr/Home.html", pretendToBeVisual: true });
for (const k of ["window", "document", "Event", "Node", "HTMLElement",
                 "location", "localStorage", "URL", "URLSearchParams"]) globalThis[k] = dom.window[k];

/* 언어 줄은 KOSi18n 이 있을 때만 그려진다. 없는 채로 재면 '테마만 있네' 하고
   지나가게 되므로, 실제 페이지처럼 사전을 먼저 심는다. */
const DICT = {};
window.KOSi18n = {
  lang: "ko",
  register: d => Object.assign(DICT, d),
  t: m => (window.KOSi18n.lang === "en" && DICT[m]) || m,
  setLang(v) { this.lang = v; },
  apply() {},
};

const P = await import(`file://${join(TMP, "panel.js")}`);
const stub = await import(`file://${join(TMP, "stub.js")}`);
const consent = await import(`file://${join(TMP, "stub-consent.js")}`);

let pass = 0, fail = 0;
const ok = (n, c, x = "") => {
  if (c) pass++;
  else { fail++; console.log("  FAIL " + n + (x ? "  — " + x : "")); }
};
const tick = () => new Promise(r => setTimeout(r, 20));

/* ── ① 로그인 상태: 목록 세 칸, 구독은 없다 ───────────────────────── */
P.openSettings();
await tick();
const nav = document.querySelector(".ks-nav");
const panel = document.querySelector(".ks-panel");
ok("창이 뜬다", !!document.querySelector(".ks-card"));
ok("두 칸 구조 — .ks-main 안에 목록과 내용",
   nav && panel && nav.parentElement === panel.parentElement
   && nav.parentElement.className === "ks-main");
const labels = [...nav.querySelectorAll("button")].map(b => b.textContent);
ok("목록은 일반·알림·계정 셋", labels.join("/") === "일반/알림/계정", labels.join("/"));
ok("구독 칸 없음", !labels.includes("구독"));
ok("구독 문구를 사전에 올리지 않는다", !("구독" in DICT));
ok("구독 모듈을 들이지 않는다", !/subscription-api|payment-config|plans\.js/.test(SRC));
ok("처음엔 일반이 선택돼 있다",
   nav.querySelectorAll('button[aria-selected="true"]').length === 1
   && nav.querySelector('button[aria-selected="true"]').textContent === "일반");
ok("일반 칸에 테마·언어 두 줄", panel.querySelectorAll(".ks-seg").length === 2);
ok("일반 칸에 스위치는 없다", panel.querySelectorAll(".ks-sw").length === 0);

/* ── ② 칸을 옮기면 내용이 바뀐다 ─────────────────────────────────── */
const tab = t => [...nav.querySelectorAll("button")].find(b => b.textContent === t);
tab("알림").click(); await tick();
ok("알림 — 스위치 하나", panel.querySelectorAll(".ks-sw").length === 1);
ok("알림 — 앞 칸 내용은 사라진다", panel.querySelectorAll(".ks-seg").length === 0);
ok("고른 칸만 선택 표시", tab("알림").getAttribute("aria-selected") === "true"
   && tab("일반").getAttribute("aria-selected") === "false");

tab("계정").click(); await tick();
const dd = [...panel.querySelectorAll(".ks-kv dd")].map(d => d.textContent);
ok("계정 — 닉네임·이메일", dd.join("/") === "홍길동/a@b.c", dd.join("/"));
const btns = [...panel.querySelectorAll(".ks-btns .ks-btn")].map(b => b.textContent);
ok("계정 — 로그아웃·회원 탈퇴", btns.join("/") === "로그아웃/회원 탈퇴", btns.join("/"));
ok("탈퇴는 위험 표시", !!panel.querySelector(".ks-btn.danger"));
ok("약관·개인정보 링크",
   [...panel.querySelectorAll(".ks-note a")].map(a => a.getAttribute("href")).join(",")
   === "Terms.html,Privacy.html");

/* ── ③ 마케팅 스위치는 누르는 순간 저장한다 ─────────────────────── */
tab("알림").click(); await tick();
const sw = panel.querySelector(".ks-sw");
ok("불러온 값이 켜짐으로 반영되고 잠금이 풀린다",
   sw.getAttribute("aria-checked") === "true" && !sw.disabled);
sw.click(); await tick();
ok("누르면 꺼짐으로 바뀐다", sw.getAttribute("aria-checked") === "false");
ok("잘 됐다는 말은 하지 않는다 — 스위치가 옮겨 간 것이 곧 확인이다",
   !panel.querySelector(".ks-msg").classList.contains("on"));
consent._failNext();
sw.click(); await tick();
ok("저장이 실패하면 스위치가 되돌아간다", sw.getAttribute("aria-checked") === "false");
ok("실패했을 때만 이유를 말한다",
   panel.querySelector(".ks-msg.on.err")
   && panel.querySelector(".ks-msg").textContent.includes("저장하지 못했습니다"));

/* ── ④ 테마 ─────────────────────────────────────────────────────── */
tab("일반").click(); await tick();
const seg = panel.querySelectorAll(".ks-seg")[0].querySelectorAll("button");
seg[0].click();
ok("테마가 라이트로", document.documentElement.getAttribute("data-theme") === "light");
ok("헤더 아이콘도 함께 바뀐다", document.getElementById("themeIcon").innerHTML.includes("21 12.8"));
seg[1].click();
ok("테마가 다크로", document.documentElement.getAttribute("data-theme") === "dark");

/* ── ⑤ Escape 로 닫힌다 ────────────────────────────────────────── */
document.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape" }));
ok("Escape 로 닫힌다", !document.getElementById("ksModal"));

/* ── ⑥ 비회원 — Settings.html 이 본문에 펴는 길 ────────────────── */
stub.auth.currentUser = null;
const box = document.createElement("div");
document.body.appendChild(box);
P.renderSettings(box);
await tick();
const nav2 = box.querySelector(".ks-nav"), panel2 = box.querySelector(".ks-panel");
ok("비회원도 두 칸 구조", !!nav2 && !!panel2);
ok("비회원 목록은 일반 하나",
   [...nav2.querySelectorAll("button")].map(b => b.textContent).join("/") === "일반");
ok("비회원도 테마·언어는 쓴다 — 그 기기의 취향이지 계정이 아니다",
   panel2.querySelectorAll(".ks-seg").length === 2);
ok("로그인 길이 보인다",
   panel2.querySelector("a.ks-btn.primary")
   && panel2.querySelector("a.ks-btn.primary").getAttribute("href").startsWith("Login.html?next="));
ok("비회원에게 스위치·탈퇴는 없다",
   !panel2.querySelector(".ks-sw") && !panel2.querySelector(".ks-btn.danger"));

/* ── ⑦ 가르는 선 ───────────────────────────────────────────────── */
const style = document.getElementById("kos-settings-css").textContent;
ok("목록 오른쪽에 선", /\.ks-nav\{[^}]*border-right:1px solid var\(--ks-line\)/.test(style));
ok("--ks-line 을 .ks-card 와 .ks-main 둘 다에 건다",
   /\.ks-card,\.ks-main\{--ks-line:rgba\(0,0,0,\.12\)\}/.test(style));
ok("다크에서도 .ks-main 에 정의된다",
   /\[data-theme="dark"\] \.ks-main\{--ks-line:rgba\(255,255,255,\.13\)\}/.test(style));
ok("좁은 화면에서는 아래쪽 선으로 눕는다",
   /border-right:0;border-bottom:1px solid var\(--ks-line\)/.test(style));

/* ── ⑧ Settings.html 이 창과 같은 폭을 갖고 있는가 ───────────────── */
const setHtml = readFileSync(join(ROOT, "Settings.html"), "utf8");
ok("Settings.html 의 카드가 두 칸을 담을 만큼 넓다",
   /\.set-card\{max-width:860px/.test(setHtml));

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
