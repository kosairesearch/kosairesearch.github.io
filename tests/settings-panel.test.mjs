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
       (창이 아닌 자리에 펴면 .ks-card 가 없다. --ks-line 을 .ks-main 에도
        걸어 두지 않으면 선이 글자색이 된다)
     · Settings.html 이 이 모듈을 본문(#mount)에 그리는가 — 2026-10-03 부터
       실사이트 설정 페이지도 새 디자인이다(scripts/build_settings_staging.py 의
       live 판). 목록은 위 탭 줄, 구독 칸은 주소(?tab=subscription)로도 안 열린다.
       페이지의 모듈을 그대로 돌려 본다(파이어베이스만 갈아 끼운다)
     · 이 파일을 부르는 곳(설정 페이지 · 관리자 화면의 auth-state-legacy.js)마다
       캐시 판본이 붙어 있고 서로 같고 지금 내용과 맞는가

   실행
     npm install --no-save jsdom
     node tests/settings-panel.test.mjs
   ============================================================ */
import { readFileSync, writeFileSync, mkdirSync, rmSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
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
/* 주소에는 캐시용 판본(?v=1a2b3c4d)이 붙어 있다 — stamp_assets.py 가 붙인다.
   그 부분까지 같이 받아 줘야 도장을 다시 찍을 때마다 이 검사가 깨지지 않는다. */
writeFileSync(join(TMP, "panel.js"), SRC
  .replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"')
  .replace(/from "\.\/consent\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub-consent.js"'));
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

/* 스크롤바. 내용이 창보다 길면 오른쪽에 띠가 서는데, 기본 스크롤바는 바탕이
   밝아 어두운 창을 세로로 가르는 밝은 줄이 하나 더 생긴다. 바탕을 지우고
   손잡이만 남긴다.

   눈으로는 대신 못 본다 — 고치는 자리(헤드리스 크로미움)는 겹치는 스크롤바를
   써서 화면에도 스크린샷에도 아예 안 나온다. 규칙이 제자리에 있는지를 본다. */
ok("바탕이 없다 — 손잡이 색과 '투명'을 함께 준다",
   /scrollbar-color:var\(--ks-thumb\) transparent/.test(style));
ok("손잡이 색이 두 테마 모두 있다",
   /--ks-thumb:rgba\(0,0,0,\.28\)/.test(style) && /--ks-thumb:rgba\(255,255,255,\.26\)/.test(style));
ok("넘치는 칸마다 굵기를 준다(scrollbar-width 는 물려받지 않는다)",
   /\.ks-nav,\.ks-panel\{scrollbar-width:thin\}/.test(style));
ok("scrollbar-color 를 모르는 곳(사파리)에도 바탕이 없다",
   /::-webkit-scrollbar-track\{background:transparent\}/.test(style));
ok("실사이트에는 확인 대화상자가 없으므로 그 규칙도 없다", !/ks-dlg/.test(style));

/* ── ⑧ Settings.html — 이 창을 본문(#mount)에 그리는 페이지 ──────────
   옛 실사이트 Settings.html 은 .set-card(최대 860px) 안에 창과 같은 두 칸(왼쪽 목록 ·
   오른쪽 내용)을 폈다. 그래서 카드가 두 칸을 담을 만큼 넓은지를 봤다.
   2026-10-03 부터는 새 디자인이다 — 로그인 칸(.auth)보다 넓은 글 칸(.auth.wide)에서 목록을
   위 탭 줄로 눕히고 내용을 그 아래에 쌓는다(#mount .ks-main{display:block}). 두 칸 폭은 더
   필요 없으니, 그 대신 이 페이지가 정말 이 모듈을 불러 #mount 에 그리는지를 페이지의 모듈
   그대로 돌려 본다 — 주소의 ?tab= 과 로그인 상태에 따라 무엇이 열리는가. */
const setHtml = readFileSync(join(ROOT, "Settings.html"), "utf8");
const pageMod = (setHtml.match(/<script type="module">([\s\S]*?)<\/script>/) || [])[1] || "";
ok("Settings.html 이 ./settings-panel.js 의 renderSettings 를 부른다",
   /import \{ renderSettings \} from "\.\/settings-panel\.js(\?v=[0-9a-f]{8})?";/.test(pageMod));
ok("실사이트 설정 페이지가 여는 칸에 구독이 없다",
   /const TABS = \["general", "notifications", "account"\];/.test(pageMod) && !/subscription|__KOS_CARD_NOTICE/.test(pageMod));
const wide = +((setHtml.match(/\.auth\.wide\{max-width:(\d+)px\}/) || [])[1] || 0);
const narrow = +((setHtml.match(/\.auth\{max-width:(\d+)px/) || [])[1] || 0);
ok("설정은 로그인 칸(.auth)보다 넓은 칸(.auth.wide)에 편다",
   /<div class="auth wide">[\s\S]*?<div id="mount"/.test(setHtml) && narrow > 0 && wide > narrow, `${wide}px vs ${narrow}px`);
ok("목록은 위 탭 줄로 눕고 내용은 그 아래에 쌓인다",
   /#mount \.ks-main\{display:block\}/.test(setHtml) && /#mount \.ks-nav\{[^}]*display:flex/.test(setHtml));
ok("탭 줄 아래 선은 페이지 토큰(--hair)이고 두 테마 모두 정의돼 있다",
   /#mount \.ks-nav\{[^}]*border-bottom:1px solid var\(--hair\)/.test(setHtml)
   && /:root\{[^}]*--hair:rgba\(/.test(setHtml) && /:root\[data-theme="dark"\]\{[^}]*--hair:rgba\(/.test(setHtml));

writeFileSync(join(TMP, "page.js"), pageMod
  .replace(/from "\.\/firebase-config\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./stub.js"')
  .replace(/from "https:\/\/www\.gstatic\.com\/firebasejs\/[^"]+"/g, 'from "./stub.js"')
  .replace(/from "\.\/settings-panel\.js(?:\?v=[0-9a-f]+)?"/g, 'from "./panel.js"'));   // 위에서 들인 그 모듈(P) 그대로
const GLOBALS = ["window", "document", "Event", "Node", "HTMLElement", "location", "localStorage",
                 "URL", "URLSearchParams", "MutationObserver"];
let runs = 0;
async function settingsPage(query, user) {
  const d = new JSDOM(setHtml.replace(/<script\b[\s\S]*?<\/script>/g, ""),   // 마크업만 — 모듈은 아래에서 돌린다
    { url: "https://kosai.kr/Settings.html" + query, pretendToBeVisual: true });
  d.window.KOSi18n = window.KOSi18n;
  const saved = Object.fromEntries(GLOBALS.map(k => [k, globalThis[k]]));
  for (const k of GLOBALS) globalThis[k] = d.window[k];
  stub.auth.currentUser = user;
  try {
    await import(`file://${join(TMP, "page.js")}?run=${++runs}`);
    await tick();
    const m = d.window.document.getElementById("mount");
    if (!m) return { mount: false, nav: [], sel: [], seg: 0, dd: [], login: null };   // 자리째 지워졌다 — 아래 확인이 실패로 알린다
    return { mount: true, nav: [...m.querySelectorAll(".ks-nav button")].map(b => b.textContent),
             sel: [...m.querySelectorAll('.ks-nav button[aria-selected="true"]')].map(b => b.textContent),
             seg: m.querySelectorAll(".ks-seg").length,
             dd: [...m.querySelectorAll(".ks-kv dd")].map(x => x.textContent),
             login: m.querySelector("a.ks-btn.primary") ? m.querySelector("a.ks-btn.primary").getAttribute("href") : null };
  } finally { for (const k of GLOBALS) globalThis[k] = saved[k]; }
}
const USER = { uid: "u1", email: "a@b.c", displayName: "홍길동" };
{
  const g = await settingsPage("", USER);
  ok("Settings.html — #mount 에 일반·알림·계정을 그리고 일반을 연다",
     g.nav.join("/") === "일반/알림/계정" && g.sel.join() === "일반" && g.seg === 2, JSON.stringify(g));
  const a = await settingsPage("?tab=account", USER);
  ok("Settings.html?tab=account — 계정 칸을 연다",
     a.sel.join() === "계정" && a.dd.join("/") === "홍길동/a@b.c", JSON.stringify(a));
  const s = await settingsPage("?tab=subscription", USER);
  ok("Settings.html?tab=subscription — 없는 칸이라 일반을 연다(구독 칸 없음)",
     s.sel.join() === "일반" && !s.nav.includes("구독"), JSON.stringify(s));
  const o = await settingsPage("?tab=account", null);
  ok("Settings.html — 비회원은 일반 하나와 이 페이지로 돌아오는 로그인 길",
     o.nav.join("/") === "일반" && o.login === "Login.html?next=" + encodeURIComponent("Settings.html?tab=account"), JSON.stringify(o));
}

/* ── ⑨ 캐시 주소 ─────────────────────────────────────────────────
   창을 두 칸으로 새로 짜고 배포했는데 화면은 옛 창이었다. 이 파일만
   저장소 어디에서도 판본이 안 붙어 있어서, 브라우저가 받아 둔 옛 파일을
   계속 쓰고 있었다. stamp_assets.py 가 그 뒤로 세 모양을 모두 보지만,
   못 보는 모양이 또 생기면 --check 는 아무 말도 하지 않는다(맨 주소는
   '최신이 아닌 해시' 가 아니라 '해시 없음' 이라 눈에 안 띈다).
   그래서 여기서 직접 본다.

   2026-10-03 부터 이 파일을 부르는 곳은 설정 페이지(Settings.html)와 관리자 화면이 쓰는
   옛 모듈(auth-state-legacy.js 의 import())이다. 새 auth-state.js 는 설정을 창으로 띄우지
   않고 페이지로 보내 이 파일을 부르지 않는다. 그래서 이름을 정해 두지 않고 루트 파일을 다
   훑어 부르는 자리를 모은 뒤, 자리마다 판본이 붙었는지 · 서로 같은지 · 지금 내용의 해시와
   맞는지 본다 — 새로 부르는 곳이 생겨도 같이 걸린다. */
const refs = [];
for (const f of readdirSync(ROOT).filter(f => /\.(html|js)$/.test(f)).sort()) {
  const t = readFileSync(join(ROOT, f), "utf8");
  for (const m of t.matchAll(/settings-panel\.js(\?v=([0-9a-f]+))?["'`]/g)) refs.push({ f, v: m[2] || null });
}
const users = [...new Set(refs.map(r => r.f))];
ok("부르는 곳에 설정 페이지와 관리자 화면의 모듈이 있다",
   users.includes("Settings.html") && users.includes("auth-state-legacy.js"), users.join(", ") || "없음");
ok("부르는 자리마다 판본이 붙어 있다", refs.length > 0 && refs.every(r => r.v),
   refs.filter(r => !r.v).map(r => r.f).join(", "));
const vs = [...new Set(refs.map(r => r.v))];
ok("판본이 모두 같다 — 갈리면 한쪽은 옛 창을 쓴다", vs.length === 1,
   refs.map(r => `${r.f} ${r.v}`).join(" · "));
const want = createHash("sha1").update(SRC, "utf8").digest("hex").slice(0, 8);
ok("판본이 지금 파일 내용과 맞다(stamp_assets.py 와 같은 해시)", vs.length === 1 && vs[0] === want,
   `${vs.join(",")} vs ${want}`);

rmSync(TMP, { recursive: true, force: true });
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
