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
  const dir = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d)).sort().pop();
  const p = dir && `${base}/${dir}/chrome-linux/chrome`;
  return p && existsSync(p) ? p : null;
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
async function measure(path, { scrollTo = 0 } = {}) {
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  await page.goto(BASE + path, { waitUntil: "domcontentloaded" });
  // 띠 높이를 재는 스크립트와 글꼴이 자리를 잡을 틈을 준다.
  await page.waitForTimeout(400);
  if (scrollTo) { await page.evaluate((y) => scrollTo(0, y), scrollTo); await page.waitForTimeout(150); }
  await page.click("#menuBtn");
  await page.waitForTimeout(150);

  const got = await page.evaluate(() => {
    const box = (el) => { if (!el) return null; const r = el.getBoundingClientRect();
      return { top: r.top, bottom: r.bottom, left: r.left, right: r.right, h: r.height }; };
    const items = [...document.querySelectorAll(".mobile-menu a")].map((a) => ({
      text: a.textContent.trim(), ...box(a),
    }));
    return {
      bar: box(document.querySelector(".kos-staging-bar")),
      nav: box(document.querySelector(".nav")),
      menu: box(document.querySelector(".mobile-menu")),
      open: document.querySelector(".mobile-menu").classList.contains("open"),
      items,
      innerHeight,
    };
  });
  await page.close();
  return got;
}

/* ── 스테이징: 메뉴 첫 칸이 헤더에 가리지 않는가 ──────────── */
console.log("── 모바일 메뉴가 헤더에 가리지 않는다 (스테이징) ──\n");

const PAGES = ["/staging/pricing.html", "/staging/Home.html", "/staging/Reports.html",
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
             first: box(".mobile-menu a") };
  });
  await page.close();
  ok("띠가 실제로 길어졌다", m.bar.h > before + 10, `${before.toFixed(1)} → ${m.bar.h.toFixed(1)}`);
  ok("헤더가 늘어난 띠 아래로 내려간다", m.nav.top >= m.bar.bottom - 0.5,
     `헤더 top ${m.nav.top.toFixed(1)} · 띠 bottom ${m.bar.bottom.toFixed(1)}`);
  ok("메뉴 첫 칸도 함께 내려간다", m.first.top >= m.nav.bottom - 0.5,
     `첫 칸 top ${m.first.top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
}

/* ── 확인 창이 띠에 가리지 않는가 ──────────────────────────
   .dlg-box 는 최대 88vh 를 가운데 정렬한다. 띠가 확인 창보다 위에 그려지면
   내용이 긴 창은 제목이 있는 윗부분이 띠 밑으로 들어가 읽을 수가 없다. */
console.log("\n── 확인 창이 띠에 가리지 않는다 ──\n");
{
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  await page.goto(BASE + "/staging/pricing.html", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(400);
  const z = await page.evaluate(() => {
    const num = (s) => parseInt(getComputedStyle(document.querySelector(s)).zIndex, 10);
    return { bar: num(".kos-staging-bar"), nav: num(".nav"),
             menu: num(".mobile-menu"), dlg: num(".dlg") };
  });
  await page.close();
  ok("띠가 헤더·메뉴보다 위에 그려진다", z.bar > z.nav && z.bar > z.menu, JSON.stringify(z));
  ok("띠가 확인 창보다는 아래에 그려진다", z.bar < z.dlg, JSON.stringify(z));
}

/* ── 실사이트는 그대로여야 한다 ────────────────────────────
   띠가 없으므로 --kos-bar-h 는 0 이고, 자리는 전과 같아야 한다. */
console.log("\n── 실사이트는 달라지지 않는다 ──\n");
for (const p of ["/Home.html", "/Reports.html", "/index.html"]) {
  const page = await browser.newPage({ viewport: PHONE, deviceScaleFactor: 2 });
  await page.goto(BASE + p, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(400);
  await page.click("#menuBtn");
  await page.waitForTimeout(150);
  const m = await page.evaluate(() => {
    const box = (s) => { const el = document.querySelector(s); if (!el) return null;
      const r = el.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; };
    return { bar: box(".kos-staging-bar"), nav: box(".nav"), first: box(".mobile-menu a"),
             items: document.querySelectorAll(".mobile-menu a").length };
  });
  await page.close();
  const name = p.slice(1);
  ok(`${name} — STAGING 띠가 없다`, m.bar === null);
  ok(`${name} — 헤더가 12px 자리 그대로다`, Math.abs(m.nav.top - 12) < 1.5, `top ${m.nav.top.toFixed(1)}`);
  ok(`${name} — 첫 칸이 헤더 아래에 있다`, m.items > 0 && m.first.top >= m.nav.bottom - 0.5,
     `첫 칸 top ${m.first && m.first.top.toFixed(1)} · 헤더 bottom ${m.nav.bottom.toFixed(1)}`);
}

/* ── 빵부스러기('홈 / 리포트')가 페이지마다 같은가 ────────
   눈으로는 "뭔가 좀 다른데" 까지만 보이고 무엇이 다른지는 안 보인다. 실제로
   업종별 페이지만 다른 클래스(.ind-bc)를 쓰고 있었다 — 글씨 12px·굵기 600·
   자간 0.36px 에 '홈' 은 링크도 아니고 현재 위치 강조도 없었다. 나머지 아홉
   페이지는 13px·500·링크·강조였다. 여백도 세 가지로 갈려 있었다.

   그래서 사람 눈이 아니라 브라우저가 잰 값으로 못 박는다. */
console.log("\n── 빵부스러기가 페이지마다 같다 ──\n");
for (const [label, pre] of [["실사이트", ""], ["스테이징", "/staging"]]) {
  const PAGES = ["/Reports.html", "/industry.html", "/Watchlist.html",
                 "/brief.html", "/About.html", "/stock.html"];
  const seen = [];
  for (const path of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    await page.goto(BASE + pre + path, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1400);
    const got = await page.evaluate(() => {
      const c = document.querySelector(".crumb");
      if (!c) return null;
      const cs = getComputedStyle(c), r = c.getBoundingClientRect();
      return { size: cs.fontSize, weight: cs.fontWeight, color: cs.color,
               letter: cs.letterSpacing, top: Math.round(r.top),
               link: !!c.querySelector("a"), bold: !!c.querySelector("b") };
    });
    await page.close();
    ok(`${label}${path} — 빵부스러기가 있다`, got !== null);
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
    /* '홈' 은 눌러서 갈 수 있어야 하고, 지금 위치는 굵게 보여야 한다.
       업종별 페이지는 둘 다 없어서 빵부스러기 노릇을 못 하고 있었다. */
    for (const [path, g] of seen) {
      ok(`${label}${path} — 앞 단계가 링크다`, g.link, "누를 수 없으면 빵부스러기가 아니다");
      ok(`${label}${path} — 지금 위치가 강조된다`, g.bold);
    }
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
