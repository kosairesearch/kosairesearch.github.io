/* 화면이 실제로 어떻게 그려지는가 — 진짜 브라우저로 재 본다.
   ───────────────────────────────────────────────────────────
   다른 검사들은 jsdom 으로 돈다. 그건 문서 구조와 자바스크립트는 보지만
   '무엇이 무엇을 가리는가' 는 못 본다 — 위치도 크기도 계산하지 않기 때문이다.

   그래서 실제로 이런 일이 났다. 모바일에서 햄버거 메뉴를 열면 첫 두 칸
   (홈·리포트)이 헤더에 덮여 보이지 않았다. 아래로 밀어야 나왔다.

   원인은 자리를 숫자로 적어 둔 것이었다.

     .nav          position:sticky; top:12px       화면 위에서 12px
     .mobile-menu  position:fixed;  top:70px       화면 위에서 70px

   실사이트에서는 맞는 값이다(헤더 12 + 높이 약 56 = 68, 메뉴는 그 바로 아래
   70). 그런데 스테이징에는 맨 위에 STAGING 띠가 붙어 있다. 띠가 화면 위쪽을
   차지하니 헤더는 그만큼 내려와 앉는데, 메뉴는 여전히 70px 자리를 잡는다 —
   헤더 밑으로 들어간다.

   숫자를 하나 더 크게 고쳐 놓고 끝내면 다음에 띠 문구가 한 줄 늘 때 또
   어긋난다. 띠 높이를 재서 둘 다 그만큼 내리도록 고쳤고, 이 검사는 그것이
   실제로 지켜지는지를 화면을 그려서 확인한다.

   2026-10-03 부터 실사이트(루트)도 스테이징과 같은 생성기(scripts/build_live.py)가
   만든 새 디자인이다 — 메뉴는 두 곳 모두 .mmenu, 제목 위 눈썹은 .crumb 한 낱말,
   지금 위치는 헤더의 활성 메뉴. 그래서 실사이트에도 스테이징과 같은 기대를 건다.
   다른 것은 STAGING 띠 하나뿐이다 — 실사이트에는 띠가 없어야 하고(.kos-staging-bar
   없음) 헤더는 화면 맨 위(0px)에 붙는다. 띠에만 걸린 확인(띠 아래 · 띠가 길어질 때 ·
   띠와 확인 창의 층)은 스테이징에서만 본다.
   ───────────────────────────────────────────────────────────
   돌리려면:

     npm install --no-save playwright-core

   브라우저는 이미 깔려 있는 것을 쓴다(PLAYWRIGHT_BROWSERS_PATH). 새로
   내려받지 않는다 — 받을 수도 없다. */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync, readdirSync } from "node:fs";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) {
  console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요.");
  process.exit(2);
}

const ROOT = fileURLToPath(new URL("../../", import.meta.url));

/* 이미 깔려 있는 크로미움을 찾는다. 판올림하면 폴더 이름의 숫자가 바뀌므로
   이름을 적어 두지 않고 고른다 — 적어 두면 다음 판올림에 조용히 죽는다. */
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  // 판마다 폴더 이름이 다르다(1194: chrome-linux · 1243: chrome-linux64). 최신 판부터 둘 다 본다.
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) for (const sub of ["chrome-linux64", "chrome-linux"]) {
    const p = `${base}/${d}/${sub}/chrome`;
    if (existsSync(p)) return p;
  }
  return null;
})();
if (!CHROME) {
  console.error("크로미움을 찾지 못했습니다(PLAYWRIGHT_BROWSERS_PATH 확인).");
  process.exit(2);
}

let pass = 0, fail = 0;
const ok = (name, cond, extra = "") => {
  if (cond) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + (extra ? "  ← " + extra : "")); }
};

/* ── 파일을 그대로 내주는 아주 작은 서버 ────────────────────
   file:// 로 열면 모듈 스크립트가 CORS 로 막힌다. 이 검사는 위치만 보므로
   모듈이 죽어도 상관없지만, 페이지가 반쯤 죽은 채로 재는 것보다 낫다.
   (바깥 CDN 은 어차피 막혀 있어 파이어베이스 쪽은 실패한다 — 헤더와 메뉴는
   모듈이 아닌 인라인 스크립트가 붙이므로 영향이 없다.) */
const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css",
               ".png": "image/png", ".svg": "image/svg+xml", ".json": "application/json",
               ".webmanifest": "application/manifest+json", ".ico": "image/x-icon" };

const server = createServer(async (req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: CHROME });

/* 세로로 긴 흔한 휴대폰 크기. 띠가 두세 줄로 접히는 폭이라 문제가 드러난다. */
const PHONE = { width: 390, height: 844 };

/* 한 페이지를 열어 메뉴를 펴고, 무엇이 무엇을 가리는지 잰다. */
/* 새 디자인의 메뉴는 .mmenu(헤더 아래를 다 덮는 한 장) — 스테이징은 2026-09-26, 실사이트는 2026-10-03 부터. 옛 실사이트는 .mobile-menu 였다. */
const MENU = ".mmenu";

async function measure(path, { scrollTo = 0 } = {}) {
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  await page.goto(BASE + path, { waitUntil: "domcontentloaded" });
  // 띠 높이를 재는 스크립트와 글꼴이 자리를 잡을 틈을 준다.
  await page.waitForTimeout(400);
  if (scrollTo) { await page.evaluate((y) => scrollTo(0, y), scrollTo); await page.waitForTimeout(150); }
  await page.click("#menuBtn");
  await page.waitForTimeout(150);

  const got = await page.evaluate((MENU) => {
    const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, h: r.height }; };
    const items = [...document.querySelectorAll(MENU + " a")].map((a) => ({
      text: a.textContent.trim(), ...box(a),
    }));
    return {
      bar: box(document.querySelector(".kos-staging-bar")),
      nav: box(document.querySelector(".nav")),
      menu: box(document.querySelector(MENU)),
      open: !!document.querySelector(MENU) && document.querySelector(MENU).classList.contains("open"),   // 메뉴가 없으면 "메뉴가 열린다" 로 걸린다
      items,
      innerHeight,
    };
  }, MENU);
  await page.close();
  return got;
}

/* ── 스테이징: 메뉴 첫 칸이 헤더에 가리지 않는가 ──────────── */
console.log("── 모바일 메뉴가 헤더에 가리지 않는다 (스테이징) ──\n");

const PAGES = ["/staging/pricing.html", "/staging/Home.html", "/staging/Reports.html", "/staging/index.html",
               "/staging/stock.html", "/staging/Terms.html", "/staging/checkout.html"];

for (const p of PAGES) {
  const m = await measure(p);
  const name = p.split("/").pop();
  if (!m.open || !m.items.length) { ok(`${name} — 메뉴가 열린다`, false, JSON.stringify({ open: m.open, n: m.items.length })); continue; }

  const first = m.items[0];
  ok(`${name} — 첫 칸(${first.text})이 헤더 아래에 있다`,
     first.top >= m.nav.bottom - 0.5,
     `첫 칸 top ${first.top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
  ok(`${name} — 첫 칸이 STAGING 띠 아래에 있다`,
     first.top >= m.bar.bottom - 0.5,
     `첫 칸 top ${first.top.toFixed(1)} · 띠 bottom ${m.bar.bottom.toFixed(1)}`);
  ok(`${name} — 헤더가 띠에 가리지 않는다`,
     m.nav.top >= m.bar.bottom - 0.5,
     `헤더 top ${m.nav.top.toFixed(1)} · 띠 bottom ${m.bar.bottom.toFixed(1)}`);
  ok(`${name} — 메뉴가 화면 안에 다 들어온다`,
     m.items[m.items.length - 1].bottom <= m.innerHeight + 0.5,
     `마지막 칸 bottom ${m.items[m.items.length - 1].bottom.toFixed(1)} · 화면 ${m.innerHeight}`);
}

/* ── 스크롤한 뒤에도 같아야 한다 ────────────────────────────
   띠도 헤더도 화면에 붙어 있으므로(sticky) 스크롤과 상관없이 자리가 같다.
   한쪽만 붙어 있으면 스크롤한 순간 다시 겹친다. */
console.log("\n── 스크롤한 뒤에도 가리지 않는다 ──\n");
{
  const m = await measure("/staging/pricing.html", { scrollTo: 900 });
  ok("스크롤 후 — 헤더가 띠 아래에 그대로 있다",
     m.nav.top >= m.bar.bottom - 0.5,
     `헤더 top ${m.nav.top.toFixed(1)} · 띠 bottom ${m.bar.bottom.toFixed(1)}`);
  ok("스크롤 후 — 첫 칸이 헤더 아래에 그대로 있다",
     m.items[0].top >= m.nav.bottom - 0.5,
     `첫 칸 top ${m.items[0].top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
}

/* ── 띠가 길어져도 따라간다 ────────────────────────────────
   숫자를 하나 고쳐 놓고 끝냈다면 여기서 걸린다. */
console.log("\n── 띠 문구가 길어져도 따라간다 ──\n");
{
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  await page.goto(BASE + "/staging/pricing.html", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(400);
  const before = await page.evaluate(() => document.querySelector(".kos-staging-bar").getBoundingClientRect().height);
  await page.evaluate(() => {
    document.querySelector(".kos-staging-bar span").textContent =
      "미리보기입니다. ".repeat(12);          // 줄 수를 억지로 늘린다
  });
  await page.waitForTimeout(300);             // ResizeObserver 가 다시 잴 틈
  await page.click("#menuBtn");
  await page.waitForTimeout(150);
  const m = await page.evaluate(() => {
    const box = (s) => { const r = document.querySelector(s).getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, h: r.height }; };
    return { bar: box(".kos-staging-bar"), nav: box(".nav"),
             first: box(".mmenu a") };
  });
  await page.close();
  ok("띠가 실제로 길어졌다", m.bar.h > before + 10, `${before.toFixed(1)} → ${m.bar.h.toFixed(1)}`);
  ok("헤더가 늘어난 띠 아래로 내려간다", m.nav.top >= m.bar.bottom - 0.5,
     `헤더 top ${m.nav.top.toFixed(1)} · 띠 bottom ${m.bar.bottom.toFixed(1)}`);
  ok("메뉴 첫 칸도 함께 내려간다", m.first.top >= m.nav.bottom - 0.5,
     `첫 칸 top ${m.first.top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
}

/* ── 확인 창이 띠에 가리지 않는가 ──────────────────────────
   확인 창은 최대 86vh 를 가운데 정렬한다. 띠가 확인 창보다 위에 그려지면
   내용이 긴 창은 제목이 있는 윗부분이 띠 밑으로 들어가 읽을 수가 없다.
   요금제 화면의 확인 창(.dlg — 요금제 변경)은 요금제를 하나로 합치며 없앴다(2026-11-24). 남은 확인 창은
   설정의 해지 · 환불 확인 창(.ks-dlg — 환불 창은 계산 내역 · 환불 기준까지 실려 가장 길다)과 회원 탈퇴 창(.wd-ov)이다. */
console.log("\n── 확인 창이 띠에 가리지 않는다 ──\n");
{
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  /* 설정 화면은 파이어베이스 묶음을 받아야 그려진다 — 시험에서는 로그아웃 상태의 대역으로 바꿔 끼운다 */
  const FAKE_FB = {
    "firebase-app": "export function initializeApp(c){ return { options: c || {} }; } export function getApp(){ return {}; } export function getApps(){ return []; }",
    "firebase-auth": "const A = { currentUser: null }; export function getAuth(){ return A; } export function onAuthStateChanged(a, cb){ setTimeout(() => cb(null), 0); return () => {}; }"
      + " const no = async () => ({}); export const signOut = no, deleteUser = no, signInWithCustomToken = no, signInWithEmailAndPassword = no;",
    "firebase-firestore": "export function getFirestore(){ return {}; } export function doc(){ return {}; } export async function getDoc(){ return { exists: () => false, data: () => null }; }"
      + " export async function setDoc(){} export async function deleteDoc(){} export function onSnapshot(){ return () => {}; } export function serverTimestamp(){ return 0; }",
    "firebase-functions": "export function getFunctions(){ return {}; } export function httpsCallable(){ return async () => ({ data: {} }); }",
  };
  await page.route(/gstatic\.com\/firebasejs\/[\d.]+\/firebase-[a-z-]+\.js/, (route) => {
    const m = route.request().url().match(/(firebase-[a-z-]+)\.js/);
    return FAKE_FB[m[1]] != null ? route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE_FB[m[1]] }) : route.abort();
  });
  await page.goto(BASE + "/staging/Settings.html", { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => document.getElementById("kos-settings-css"), null, { timeout: 10000 }).catch(() => {});
  const z = await page.evaluate(() => {
    const num = (s) => { const e = document.querySelector(s); return e ? parseInt(getComputedStyle(e).zIndex, 10) : NaN; };
    /* 확인 창은 누를 때 만들어진다 — 같은 이름의 빈 창을 잠깐 붙여 옷(z-index)만 잰다 */
    const probe = document.createElement("div"); probe.className = "ks-dlg"; document.body.appendChild(probe);
    const out = { bar: num(".kos-staging-bar"), nav: num(".nav"), menu: num(".mmenu"), dlg: num(".ks-dlg") };
    probe.remove();
    return out;
  });
  await page.close();
  ok("띠가 헤더·메뉴보다 위에 그려진다", z.bar > z.nav && z.bar > z.menu, JSON.stringify(z));
  ok("띠가 확인 창(설정의 해지 · 환불)보다는 아래에 그려진다", z.bar < z.dlg, JSON.stringify(z));
}

/* ── 실사이트 — 띠가 없을 뿐 메뉴는 스테이징과 같다 ───────────
   띠가 없으므로 --kos-bar-h 는 0 이고, 헤더는 화면 맨 위(0px)에 붙는다. 메뉴 첫 칸이 헤더
   아래에 있고 마지막 칸까지 화면 안에 들어오는 것은 스테이징과 같은 기대다. 멤버십 화면
   (pricing · checkout)은 실사이트에 없어 빼고, 첫 화면(index)을 더 본다. */
console.log("\n── 실사이트: 띠 없이 같은 메뉴 ──\n");
for (const p of ["/Home.html", "/Reports.html", "/index.html", "/stock.html", "/Terms.html"]) {
  const m = await measure(p);
  const name = p.slice(1);
  ok(`${name} — STAGING 띠가 없다`, m.bar === null);
  ok(`${name} — 헤더가 화면 맨 위(0px)에 붙어 있다`, !!m.nav && Math.abs(m.nav.top) < 1.5, `top ${m.nav && m.nav.top.toFixed(1)}`);
  if (!m.open || !m.items.length) { ok(`${name} — 메뉴가 열린다`, false, JSON.stringify({ open: m.open, n: m.items.length })); continue; }
  const first = m.items[0];
  ok(`${name} — 첫 칸(${first.text})이 헤더 아래에 있다`,
     first.top >= m.nav.bottom - 0.5,
     `첫 칸 top ${first.top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
  ok(`${name} — 메뉴가 화면 안에 다 들어온다`,
     m.items[m.items.length - 1].bottom <= m.innerHeight + 0.5,
     `마지막 칸 bottom ${m.items[m.items.length - 1].bottom.toFixed(1)} · 화면 ${m.innerHeight}`);
}
{
  const m = await measure("/Terms.html", { scrollTo: 900 });
  ok("실사이트 스크롤 후 — 헤더가 화면 맨 위에 그대로 있다",
     !!m.nav && Math.abs(m.nav.top) < 1.5, `헤더 top ${m.nav && m.nav.top.toFixed(1)}`);
  ok("실사이트 스크롤 후 — 첫 칸이 헤더 아래에 그대로 있다",
     m.items.length > 0 && m.items[0].top >= m.nav.bottom - 0.5,
     `첫 칸 top ${m.items[0] && m.items[0].top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
}

/* ── 빵부스러기('홈 / 리포트')가 페이지마다 같은가 ────────
   눈으로는 "뭔가 좀 다른데" 까지만 보이고 무엇이 다른지는 안 보인다. 실제로
   업종별 페이지만 다른 클래스(.ind-bc)를 쓰고 있었다 — 글씨 12px·굵기 600·
   자간 0.36px 에 '홈' 은 링크도 아니고 현재 위치 강조도 없었다. 나머지 아홉
   페이지는 13px·500·링크·강조였다. 여백도 세 가지로 갈려 있었다.

   그래서 사람 눈이 아니라 브라우저가 잰 값으로 못 박는다.

   새 디자인(스테이징 2026-09-26 · 실사이트 2026-10-03)에는 빵부스러기가 없다. 그 자리에
   제목 위 눈썹(.crumb — '리포트' · '업종 분석' 같은 한 낱말)이 있다. 그래서 눈썹이 있는
   페이지끼리 글씨·색·자간·높이가 같은지, 두 사이트의 눈썹이 같은 옷인지 본다. 모닝브리핑 ·
   종목 상세에는 눈썹이 없다(두 사이트 같음). 빵부스러기가 하던 나머지 두 일은 아래에서 본다 —
   '지금 위치가 강조된다' 는 헤더의 활성 메뉴가, '앞 단계가 링크다' 는 그 활성 메뉴 자체와
   업종 하나를 연 화면의 눈썹(업종 목록으로 가는 링크)이 맡는다. */
console.log("\n── 눈썹이 페이지마다 같다 ──\n");
const CRUMB_PAGES = ["/Reports.html", "/industry.html", "/Watchlist.html", "/About.html", "/Terms.html"];
const crumbOf = {};
for (const [label, pre] of [["실사이트", ""], ["스테이징", "/staging"]]) {
  const seen = [];
  for (const path of CRUMB_PAGES) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(BASE + pre + path, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1400);
    const got = await page.evaluate(() => {
      const c = document.querySelector(".crumb");
      if (!c) return null;
      const cs = getComputedStyle(c), r = c.getBoundingClientRect();
      return { size: cs.fontSize, weight: cs.fontWeight, color: cs.color,
               letter: cs.letterSpacing, top: Math.round(r.top) };
    });
    await page.close();
    ok(`${label}${path} — 눈썹이 있다`, got !== null);
    if (got) seen.push([path, got]);
  }
  if (seen.length > 1) {
    const [, first] = seen[0];
    for (const [path, g] of seen.slice(1)) {
      ok(`${label}${path} — 글씨·색·자간이 같다`,
         g.size === first.size && g.weight === first.weight
           && g.color === first.color && g.letter === first.letter,
         JSON.stringify({ 기준: first, 이페이지: g }));
      ok(`${label}${path} — 헤더에서 같은 높이에 앉는다`,
         Math.abs(g.top - first.top) <= 1, `${g.top} vs ${first.top}`);
    }
  }
  crumbOf[label] = seen.length ? seen[0][1] : null;
}
{
  const a = crumbOf["실사이트"], b = crumbOf["스테이징"];
  ok("두 사이트의 눈썹이 같은 옷이다(글씨·굵기·색·자간)",
     !!a && !!b && a.size === b.size && a.weight === b.weight && a.color === b.color && a.letter === b.letter,
     JSON.stringify({ 실사이트: a, 스테이징: b }));
}

/* ── 지금 위치 — 헤더의 활성 메뉴 ───────────────────────────
   옛 빵부스러기의 '지금 위치는 굵게 · 앞 단계는 링크' 를 새 디자인에서는 헤더가 한다. 지금 페이지가
   속한 메뉴 하나만 활성(.on)이고, 다른 메뉴보다 굵고 진하게 보이며, 그 메뉴는 그 칸의 첫 페이지로 가는
   링크다 — 종목 상세에서는 '리포트'(목록으로 돌아가는 앞 단계). 메뉴가 줄지어 보이는 넓은 화면에서 잰다. */
console.log("\n── 지금 위치가 헤더에 표시된다 ──\n");
const SECTIONS = [["/Reports.html", "리포트", "/Reports.html"], ["/industry.html", "업종 분석", "/industry.html"],
                  ["/Watchlist.html", "관심종목", "/Watchlist.html"], ["/brief.html", "모닝브리핑", "/brief.html"],
                  ["/stock.html?ticker=005930", "리포트", "/Reports.html"]];
for (const [label, pre] of [["실사이트", ""], ["스테이징", "/staging"]]) {
  for (const [path, want, target] of SECTIONS) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.route("**gstatic.com/**", (r) => r.abort());
    await page.goto(BASE + pre + path, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(600);
    const g = await page.evaluate(() => {
      const links = [...document.querySelectorAll(".nav .links a")];
      const on = links.filter((a) => a.classList.contains("on")), off = links.filter((a) => !a.classList.contains("on"));
      const st = (a) => { const cs = getComputedStyle(a); return { w: Number(cs.fontWeight), c: cs.color }; };
      return { n: on.length, links: links.length, text: on[0] && on[0].textContent.trim(),
               path: on[0] && new URL(on[0].href).pathname, on: on[0] && st(on[0]), off: off.map(st) };
    });
    await page.close();
    const name = `${label}${path.split("?")[0]}`;
    ok(`${name} — 헤더에 지금 위치 하나가 표시된다(${want})`,
       g.n === 1 && g.text === want, JSON.stringify({ 활성: g.n, 글: g.text }));
    ok(`${name} — 그 메뉴가 ${want} 페이지로 가는 링크다`, g.path === pre + target, `${g.path}`);
    ok(`${name} — 지금 위치가 다른 메뉴보다 굵고 진하게 보인다`,
       !!g.on && g.off.length > 0 && g.off.every((o) => g.on.w > o.w && g.on.c !== o.c), JSON.stringify({ 활성: g.on, 나머지: g.off }));
  }
  /* 업종 하나를 연 화면 — 눈썹이 업종 목록으로 가는 링크다(앞 단계) */
  {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.route("**gstatic.com/**", (r) => r.abort());
    await page.goto(`${BASE}${pre}/industry.html?sector=${encodeURIComponent("반도체")}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    const g = await page.evaluate(() => {
      const a = document.querySelector(".crumb a");
      return a ? { text: a.textContent.trim(), path: new URL(a.href).pathname } : null;
    });
    await page.close();
    ok(`${label}/industry.html?sector=반도체 — 눈썹이 업종 목록으로 가는 링크다`,
       !!g && g.text === "업종 분석" && g.path === pre + "/industry.html", JSON.stringify(g));
  }
}

/* ── 바깥 서버가 죽어도 화면이 빈 채로 남지 않는가 ────────
   워치리스트는 로그인 확인이 끝날 때까지 화면을 가려 둔다
   (html.kos-locked → body{visibility:hidden}). 풀어 주는 것은 auth-guard.js
   인데, 그 파일은 파이어베이스를 구글 서버에서 받아 온다.

   그 한 줄이 실패하면 모듈이 통째로 실행되지 않고, 풀어 주는 코드도 같이
   죽는다. 회사망·광고차단기·구글 장애 어느 하나로도 일어날 수 있고, 그때
   사용자가 보는 것은 느린 화면이 아니라 아무것도 없는 화면이다.

   그래서 가림막에 시한을 뒀다. 여기서는 구글 서버를 실제로 끊어 놓고
   그 시한이 정말 도는지 본다 — 이 검사가 없으면 시한이 지워져도 아무도
   모른다(평소에는 파이어베이스가 잘 오므로 티가 안 난다).

   업종·종목은 공개 페이지라 가림막을 쓰지 않는다(2026-09-24, 스테이징에서
   먼저 빼고 실사이트로 옮겼다). auth-guard.js 가 확인 없이 바로 풀어 주는데도
   가려 두었더니, 그 모듈이 파이어베이스를 다 받아 올 때까지 빈 화면이 잠깐
   보였다("업종분석 누를 때 아주 살짝 깜빡", 사장). 워치리스트는 이 브라우저가
   로그인 상태였다고 기억하면(kos-signed=1) 가리지 않는다 — 그것도 여기서 본다. */
console.log("\n── 구글 서버가 막혀도 화면이 나온다 ──\n");
const GATE_SRC = "classList.add('kos-locked')";
for (const [label, pre] of [["실사이트", ""], ["스테이징", "/staging"]]) {
  for (const path of ["/industry.html", "/stock.html", "/Watchlist.html"]) {
    const src = await readFile(join(ROOT, pre, path), "utf8");
    const gated = src.includes(GATE_SRC);
    ok(`${label}${path} — ${path === "/Watchlist.html" ? "가림막이 있다" : "공개 페이지라 가림막이 없다"}`,
       gated === (path === "/Watchlist.html"),
       "공개 페이지를 가리면 페이지를 옮길 때마다 빈 화면이 잠깐 보인다");
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    await page.route("**gstatic.com/**", (r) => r.abort());   // 파이어베이스를 끊는다
    await page.goto(BASE + pre + path, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(700);
    const early = await page.evaluate(() =>
      document.documentElement.classList.contains("kos-locked"));
    await page.waitForTimeout(2600);                          // 시한(2.5초)이 지날 만큼
    const got = await page.evaluate(() => ({
      locked: document.documentElement.classList.contains("kos-locked"),
      vis: getComputedStyle(document.body).visibility,
      chars: document.body.innerText.trim().length,
    }));
    await page.close();
    if (gated) {
      ok(`${label}${path} — 확인 전에는 가려 둔다`, early,
         "가리지 않으면 로그인 확인 전 내용이 번쩍 보인다");
    } else {
      ok(`${label}${path} — 처음부터 보인다`, !early, "공개 페이지는 가릴 이유가 없다");
    }
    ok(`${label}${path} — 파이어베이스가 안 와도 결국 보인다`,
       !got.locked && got.vis === "visible", JSON.stringify(got));
    ok(`${label}${path} — 글자가 실제로 그려진다`, got.chars > 50, `본문 ${got.chars}자`);
  }
  /* 워치리스트 — 로그인 상태였다고 기억하면 가리지 않는다 */
  {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
    await ctx.addInitScript(() => { try { localStorage.setItem("kos-signed", "1"); } catch (e) {} });
    const page = await ctx.newPage();
    await page.route("**gstatic.com/**", (r) => r.abort());
    await page.goto(BASE + pre + "/Watchlist.html", { waitUntil: "domcontentloaded" });
    const early = await page.evaluate(() => getComputedStyle(document.body).visibility);
    await ctx.close();
    ok(`${label}/Watchlist.html — 로그인 상태였다고 기억하면 처음부터 보인다`, early === "visible",
       "kos-signed=1 인데도 가리면 로그인한 사람에게 매번 빈 화면이 잠깐 보인다");
  }
}

/* ── 리포트 차트 값 라벨이 막대·다른 라벨에 닿지 않는다 (두 사이트) ──────
   값마다 억·조를 붙이자(2026-09-26 · 실사이트와 같게) 라벨이 45px 안팎으로 길어졌다
   ('-1,042억' · 1억 미만은 '11,633,176원' 77px). 칸이 좁은 폭(휴대폰 · 두 칸으로 놓인
   데스크톱)에서는 옆 막대·라벨에 닿는다. stock_page.CHART_FIT_JS 가 그린 뒤 실제 폭에서 재어
   닿는 라벨만 비켜 세운다 — 그게 도는지 본다. 종목은 은행(영업이익이 매출보다 큼) · 1억 미만
   값 · 칸이 빽빽함 · 적자 회사 · 초대형. 실사이트 stock.html 도 같은 생성기(live 판)라 같은 기대를 건다. */
console.log("\n── 리포트 차트 값 라벨이 막대·다른 라벨에 닿지 않는다 (두 사이트) ──\n");
for (const [label, url] of [["스테이징", (tk) => `${BASE}/staging/stock.html?ticker=${tk}&paywall=0`],
                            ["실사이트", (tk) => `${BASE}/stock.html?ticker=${tk}`]])
for (const width of [320, 390, 1440]) {
  for (const tk of ["055550", "012690", "207940", "028300", "005930"]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.route("**gstatic.com/**", (r) => r.abort());
    await page.goto(url(tk), { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".ch .ch-val", { timeout: 20000 });
    await page.waitForTimeout(400);
    const got = await page.evaluate(() => {
      const out = []; let n = 0;
      const B = (e) => e.getBoundingClientRect();
      const hit = (a, b) => a.left < b.right - 0.5 && b.left < a.right - 0.5 && a.top < b.bottom - 0.5 && b.top < a.bottom - 0.5;
      document.querySelectorAll(".ch").forEach((c) => {
        const vals = [...c.querySelectorAll(".ch-val")].map((e) => ({ t: e.textContent, r: B(e) }));
        const others = [...c.querySelectorAll("rect")].map((e) => ({ t: "막대", r: B(e) }))
          .concat([...c.querySelectorAll(".ch-lab")].map((e) => ({ t: "축 " + e.textContent, r: B(e) })));
        const cr = B(c), fig = c.closest("figure");
        const cap = fig && fig.querySelector("figcaption"), lg = fig && fig.querySelector(".lg");
        vals.forEach((a, i) => {
          n++;
          others.forEach((o) => { if (hit(a.r, o.r)) out.push(`${a.t}~${o.t}`); });
          vals.forEach((b, j) => { if (j > i && hit(a.r, b.r)) out.push(`${a.t}~${b.t}`); });
          /* 차트 옆 여백 16px 까지는 나가도 된다 — 차트 끝 라벨을 안으로 밀어 넣다 옆 막대에 닿으면 멀리 떠오르므로(2026-11-26 · 아래 블록) */
          if (a.r.left < Math.max(cr.left - 16.5, 3.5) || a.r.right > Math.min(cr.right + 16.5, document.documentElement.clientWidth - 3.5)) out.push(`${a.t} 차트 밖`);
          if (cap && a.r.top < B(cap).bottom + 1) out.push(`${a.t}~제목`);
          if (lg && a.r.bottom > B(lg).top - 1) out.push(`${a.t}~범례`);
        });
      });
      return { out, n };
    });
    await page.close();
    ok(`${label} ${width}px ${tk} — 값 라벨 ${got.n}개가 막대·라벨·축·제목·범례에 닿지 않고 차트 안(옆 여백 16px 까지)에 있다`,
       got.n > 0 && !got.out.length, got.out.slice(0, 4).join(" | "));
  }
}

/* ── 차트 끝 값 라벨은 제 막대 바로 위에 둔다 (두 사이트) ──────
   2026-11-26 사장이 보낸 에이피알 리포트 화면(휴대폰) — 마지막 분기(26Q3) 영업이익 라벨 '1,606억'이 매출 라벨 '7,731억' 위로 떠 있었다.
   그 라벨은 막대 왼쪽 끝에서 오른쪽으로 쓰는데 차트 오른쪽 끝을 넘었고, 차트 안으로 밀어 넣으면 옆 매출 막대에 1px 겹쳐 비켜 세우기
   (stock_page.CHART_FIT_JS)가 144px 띄웠다. 이제 차트 옆 여백(16px · 화면 끝 4px 안)까지 내보낸 자리를 먼저 본다. 그날 차트를 그대로
   끼워 넣고 잰다 — 리포트가 다시 쓰여도 장면은 같다. 고치기 전 판이면 라벨이 막대에서 150px 가까이 떨어져 걸린다. */
const APR_Q = '<div class="ch" role="img" aria-label="매출·영업이익 막대그래프" style="height:220px"><svg viewBox="0 0 520 220" preserveAspectRatio="none" aria-hidden="true"><line x1="8" y1="192.0" x2="512" y2="192.0" class="ch-base" vector-effect="non-scaling-stroke"/><rect class="ch-rev" x="33.4" y="110.1" width="22.0" height="81.9"/><rect class="ch-op" x="61.4" y="171.6" width="22.0" height="20.4"/><rect class="ch-rev" x="134.2" y="75.8" width="22.0" height="116.2"/><rect class="ch-op" x="162.2" y="164.4" width="22.0" height="27.6"/><rect class="ch-rev" x="235.0" y="66.1" width="22.0" height="125.9"/><rect class="ch-op" x="263.0" y="159.7" width="22.0" height="32.3"/><rect class="ch-rev" x="335.8" y="29.2" width="22.0" height="162.8"/><rect class="ch-op" x="363.8" y="151.6" width="22.0" height="40.4"/><rect class="ch-rev" x="436.6" y="28.0" width="22.0" height="164.0"/><rect class="ch-op" x="464.6" y="157.9" width="22.0" height="34.1"/></svg><span class="ch-val" style="left:8.54%;top:105.1px">3,859억</span><span class="ch-val l" style="left:11.81%;top:166.6px">961억</span><span class="ch-lab" style="left:11.23%;top:200px">25Q3</span><span class="ch-val" style="left:27.92%;top:70.8px">5,476억</span><span class="ch-val l" style="left:31.19%;top:159.4px">1,303억</span><span class="ch-lab" style="left:30.62%;top:200px">25Q4</span><span class="ch-val" style="left:47.31%;top:61.1px">5,934억</span><span class="ch-val l" style="left:50.58%;top:154.7px">1,523억</span><span class="ch-lab" style="left:50.00%;top:200px">26Q1</span><span class="ch-val" style="left:66.69%;top:24.2px">7,675억</span><span class="ch-val l" style="left:69.96%;top:146.6px">1,906억</span><span class="ch-lab" style="left:69.38%;top:200px">26Q2</span><span class="ch-val" style="left:86.08%;top:23.0px">7,731억</span><span class="ch-val l" style="left:89.35%;top:152.9px">1,606억</span><span class="ch-lab" style="left:88.77%;top:200px">26Q3</span></div>';
console.log("\n── 차트 끝 값 라벨은 제 막대 바로 위에 둔다 (두 사이트) ──\n");
for (const [label, url] of [["스테이징", (tk) => `${BASE}/staging/stock.html?ticker=${tk}&paywall=0`],
                            ["실사이트", (tk) => `${BASE}/stock.html?ticker=${tk}`]])
for (const width of [360, 390, 402]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.route("**gstatic.com/**", (r) => r.abort());
  await page.goto(url("278470"), { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".ch .ch-val", { timeout: 20000 });
  await page.waitForTimeout(400);
  const got = await page.evaluate((html) => {
    document.querySelector(".ch").outerHTML = html;
    window.kosFitCharts();
    const c = document.querySelector(".ch"), rs = [...c.querySelectorAll("rect")], vs = [...c.querySelectorAll(".ch-val")];
    const op = rs[rs.length - 1].getBoundingClientRect(), rev = rs[rs.length - 2].getBoundingClientRect(), lab = vs[vs.length - 1].getBoundingClientRect();
    return { t: vs[vs.length - 1].textContent, gap: +(op.top - lab.bottom).toFixed(1), dl: +(lab.left - op.left).toFixed(1), revR: +rev.right.toFixed(1),
             labL: +lab.left.toFixed(1), labR: +lab.right.toFixed(1), chR: +c.getBoundingClientRect().right.toFixed(1), vw: document.documentElement.clientWidth };
  }, APR_Q);
  await page.close();
  ok(`${label} ${width}px — 마지막 분기 영업이익 라벨이 제 막대 바로 위(막대 왼쪽 끝부터)에 있고 옆 매출 막대에 닿지 않는다`,
     got.t === "1,606억" && got.gap >= 2 && got.gap <= 12 && Math.abs(got.dl) <= 1.5 && got.labL >= got.revR, JSON.stringify(got));
  ok(`${label} ${width}px — 그 라벨은 차트 옆 여백 16px · 화면 끝 4px 안에 있다`, got.labR <= Math.min(got.chR + 16.5, got.vw - 3.5), JSON.stringify(got));
}

/* ── 작은 막대 옆에 큰 막대가 붙은 차트 — 라벨은 옆으로 조금 비켜 제 막대 위에 둔다 (두 사이트) ──────
   은행 · 금융지주의 분기 차트는 매출 칸(영업수익 일부)이 영업이익보다 훨씬 작아, 작은 매출 막대 바로 오른쪽에 큰 영업이익 막대가 붙는다.
   가운데에 쓴 매출 라벨이 큰 막대에 몇 px 겹쳐 비켜 세우기가 큰 막대 위까지 띄웠다(2026-11-26 기업은행 '315억' 164px · 신한지주 등 7장).
   이제 옆으로 16px 안에서 옮긴 자리(제 막대 가운데는 덮은 채 · 다른 막대와 2px 띄움)를 함께 본다. 그날 기업은행 분기 차트를 끼워 넣고 잰다
   — 고치기 전 판이면 라벨이 막대에서 120px 넘게 떨어져 걸린다. */
const IBK_Q = '<div class="ch" role="img" aria-label="매출·영업이익 막대그래프" style="height:220px"><svg viewBox="0 0 520 220" preserveAspectRatio="none" aria-hidden="true"><line x1="8" y1="192.0" x2="512" y2="192.0" class="ch-base" vector-effect="non-scaling-stroke"/><rect class="ch-rev" x="33.4" y="187.0" width="22.0" height="5.0"/><rect class="ch-op" x="61.4" y="36.7" width="22.0" height="155.3"/><rect class="ch-rev" x="134.2" y="187.2" width="22.0" height="4.8"/><rect class="ch-op" x="162.2" y="76.3" width="22.0" height="115.7"/><rect class="ch-rev" x="235.0" y="186.8" width="22.0" height="5.2"/><rect class="ch-op" x="263.0" y="43.7" width="22.0" height="148.3"/><rect class="ch-rev" x="335.8" y="185.9" width="22.0" height="6.1"/><rect class="ch-op" x="363.8" y="46.5" width="22.0" height="145.5"/><rect class="ch-rev" x="436.6" y="186.4" width="22.0" height="5.6"/><rect class="ch-op" x="464.6" y="28.0" width="22.0" height="164.0"/></svg><span class="ch-val" style="left:8.54%;top:182.0px">315억</span><span class="ch-val l" style="left:11.81%;top:31.7px">9,767억</span><span class="ch-lab" style="left:11.23%;top:200px">25Q3</span><span class="ch-val" style="left:27.92%;top:182.2px">303억</span><span class="ch-val l" style="left:31.19%;top:71.3px">7,274억</span><span class="ch-lab" style="left:30.62%;top:200px">25Q4</span><span class="ch-val" style="left:47.31%;top:181.8px">328억</span><span class="ch-val l" style="left:50.58%;top:38.7px">9,325억</span><span class="ch-lab" style="left:50.00%;top:200px">26Q1</span><span class="ch-val" style="left:66.69%;top:180.9px">381억</span><span class="ch-val l" style="left:69.96%;top:41.5px">9,151억</span><span class="ch-lab" style="left:69.38%;top:200px">26Q2</span><span class="ch-val" style="left:86.08%;top:181.4px">352억</span><span class="ch-val l" style="left:89.35%;top:23.0px">1.0조</span><span class="ch-lab" style="left:88.77%;top:200px">26Q3</span></div>';
console.log("\n── 작은 막대 옆에 큰 막대가 붙은 차트 — 라벨은 옆으로 조금 비켜 제 막대 위에 둔다 (두 사이트) ──\n");
for (const [label, url] of [["스테이징", (tk) => `${BASE}/staging/stock.html?ticker=${tk}&paywall=0`],
                            ["실사이트", (tk) => `${BASE}/stock.html?ticker=${tk}`]])
for (const width of [360, 390, 402]) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.route("**gstatic.com/**", (r) => r.abort());
  await page.goto(url("024110"), { waitUntil: "domcontentloaded" });
  await page.waitForSelector(".ch .ch-val", { timeout: 20000 });
  await page.waitForTimeout(400);
  const got = await page.evaluate((html) => {
    document.querySelector(".ch").outerHTML = html;
    window.kosFitCharts();
    const c = document.querySelector(".ch"), rev = [...c.querySelectorAll("rect.ch-rev")], op = [...c.querySelectorAll("rect.ch-op")];
    const vs = [...c.querySelectorAll(".ch-val:not(.l)")];
    return vs.map((v, i) => { const l = v.getBoundingClientRect(), b = rev[i].getBoundingClientRect(), o = op[i].getBoundingClientRect();
      return { t: v.textContent, gap: +(b.top - l.bottom).toFixed(1), cover: l.left <= (b.left + b.right) / 2 && (b.left + b.right) / 2 <= l.right,
               room: +(o.left - l.right).toFixed(1) }; });
  }, IBK_Q);
  await page.close();
  const bad = got.filter((g) => !(g.gap >= 2 && g.gap <= 12 && g.cover && g.room >= 1.5));
  ok(`${label} ${width}px — 매출 라벨 다섯이 모두 제 막대 바로 위(가운데를 덮은 채)에 있고 옆 큰 막대에 닿지 않는다`,
     got.length === 5 && !bad.length, JSON.stringify(bad.length ? bad : got));
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
