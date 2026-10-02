/* 휠 감속은 한 칸씩 끊기는 마우스 휠에만 — 맥과 터치패드는 원래 스크롤 (2026-10-02 사장)

   사장이 맥북 트랙패드로 랜딩을 스크롤해 보고 "좀 이상하더라" 고 했다. 트랙패드는 운영체제가 이미 관성을
   주는데 lenis 가 그 위에 감속을 한 번 더 걸어서였다 — 화면이 손가락보다 늦게 따라오고, 손을 뗀 뒤에도 한 번
   더 미끄러진다. 이제 smooth-scroll.js 가 맥이면 켜지 않고, 다른 곳에서도 wheelDeltaY 가 120 의 배수인
   이벤트(휠 한 칸)만 감속한다. 실사이트 · 스테이징 사본을 둘 다 본다.

   마우스 휠은 진짜 입력(CDP)으로 본다 — 크로미움은 한 칸을 120 으로 적는다. 터치패드는 진짜로 만들 수 없어
   (CDP 가 만드는 휠은 늘 120 이다) wheelDeltaY 를 넣은 가짜 휠 이벤트로 본다. 가짜 이벤트에는 브라우저가
   화면을 옮기지 않으므로, 막히지 않았으면(defaultPrevented 거짓) 시험이 그만큼 직접 옮긴다 — 브라우저가 할 일이다.

     node staging/tests/smooth-wheel.test.mjs
*/
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { dirname, extname, join, normalize } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch {
  console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요.");
  process.exit(2);
}
/* 깔려 있는 크로미움 — same-units.test.mjs 와 같은 방법 */
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) for (const sub of ["chrome-linux64", "chrome-linux"]) {
    const p = `${base}/${d}/${sub}/chrome`;
    if (existsSync(p)) return p;
  }
  return null;
})();
if (!CHROME) { console.error("크로미움을 찾지 못했습니다(PLAYWRIGHT_BROWSERS_PATH 확인)."); process.exit(2); }

let pass = 0, fail = 0;
function ok(cond, msg, extra) {
  if (cond) { pass++; console.log("  ✅ " + msg); }
  else { fail++; console.log("  ❌ " + msg + (extra ? " — " + extra : "")); }
}

/* ① 두 사본은 정해 둔 자리(스테이징 머리말 · duration · defaultPrevented 한 줄) 말고는 같아야 한다 —
   한쪽만 고치면 다른 쪽에 옛 동작이 남는다 */
{
  const strip = (s) => s
    .replace(/^\/\* 스테이징 사본 —[\s\S]*?\*\/\n/, "")
    .replace(/^ *duration: 0\.[0-9].*\n/m, "")
    .replace(/^ *if \(e\.defaultPrevented\) return;.*\n/m, "");
  const live = readFileSync(join(ROOT, "smooth-scroll.js"), "utf8");
  const stg = readFileSync(join(ROOT, "staging/smooth-scroll.js"), "utf8");
  console.log("\n두 사본");
  ok(strip(live) === strip(stg), "실사이트 · 스테이징 smooth-scroll.js 가 정해 둔 세 자리 말고는 같다",
     "한쪽만 고쳤다 — 다른 쪽에도 같이 넣을 것");
}

/* 시험 페이지 — 길쭉한 본문에 lenis.js · smooth-scroll.js 만. 뒤에 붙인 듣개가 lenis 다음에 돌아 막혔는지 본다 */
const PAGE = `<!doctype html><meta charset="utf-8"><title>휠</title>
<style>html,body{margin:0}</style><div style="height:20000px"></div>
<script src="lenis.js"></script><script src="smooth-scroll.js"></script>
<script>
  addEventListener("wheel", function (e) { window.__last = { prevented: e.defaultPrevented, trusted: e.isTrusted }; });
  /* 가짜 휠 — 막히지 않았으면 브라우저 대신 옮긴다 */
  window.__wheel = function (o) {
    var ev = new WheelEvent("wheel", Object.assign({ bubbles: true, cancelable: true, deltaMode: 0, clientX: 300, clientY: 300 }, o));
    document.body.dispatchEvent(ev);
    if (!ev.defaultPrevented && !o.ctrlKey) window.scrollBy(0, o.deltaY || 0);
    var L = window.KOSSmoothScroll;
    return { prevented: ev.defaultPrevented, state: L ? L.isScrolling : null };
  };
</script>`;

const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript" };
const server = createServer((req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (/(^|\/)__wheel\.html$/.test(rel)) { res.writeHead(200, { "content-type": MIME[".html"] }); res.end(PAGE); return; }
    const body = readFileSync(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: CHROME });

const MAC_CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36";
const MAC_SAFARI = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.0 Safari/605.1.15";

async function open(dir, opts = {}, init) {
  const ctx = await browser.newContext({ viewport: { width: 1200, height: 800 }, ...opts });
  if (init) await ctx.addInitScript(init);
  const page = await ctx.newPage();
  await page.goto(`${BASE}/${dir}__wheel.html`);
  await page.waitForFunction(() => document.readyState === "complete");
  await page.mouse.move(600, 400);
  return { ctx, page };
}
const y = (page) => page.evaluate(() => window.scrollY);
/* 막지 않는(passive) 듣개만 있으면 크로미움이 휠을 기다리지 않고 보낸다 — 듣개가 돈 뒤에 읽는다 */
const lastWheel = (page) => page.waitForFunction(() => window.__last, null, { timeout: 3000 })
  .then((h) => h.jsonValue()).catch(() => null);
const top = (page) => page.evaluate(() => { const L = window.KOSSmoothScroll; if (L) L.scrollTo(0, { immediate: true }); window.scrollTo(0, 0); });

async function site(label, dir) {
  console.log(`\n${label}`);

  /* ② 맥이 아닌 컴퓨터 — 마우스 휠 한 칸은 미끄러지듯 */
  {
    const { ctx, page } = await open(dir);
    ok(await page.evaluate(() => !!window.KOSSmoothScroll), "맥이 아니면 켜진다");
    await page.mouse.wheel(0, 100);
    const last = await lastWheel(page);
    ok(last && last.trusted && last.prevented, "마우스 휠 한 칸(wheelDeltaY 120)은 lenis 가 받는다", JSON.stringify(last));
    await page.waitForTimeout(50);
    const mid = await y(page);
    ok(mid > 0 && mid < 100, `휠 한 칸이 미끄러지듯 옮겨진다(0.05초 뒤 ${mid.toFixed(1)}px / 100px)`);
    await page.waitForTimeout(1000);
    ok(Math.abs((await y(page)) - 100) < 1, "다 멎으면 휠 한 칸 거리(100px)에 선다", String(await y(page)));

    /* ③ 터치패드 — 잘게 오는 휠과 관성(0)은 브라우저가 그대로 옮긴다 */
    await page.waitForTimeout(500); await top(page);
    const pad = await page.evaluate(async () => {
      const out = [];
      const seq = [2, 5, 9, 14, 20, 24, 20, 14, 9, 4];
      for (const d of seq) { out.push(window.__wheel({ deltaY: d, wheelDeltaY: -d })); await new Promise((r) => setTimeout(r, 16)); }
      out.push(window.__wheel({ deltaY: 40, wheelDeltaY: -120 }));      // 터치패드가 우연히 120 을 냈다
      await new Promise((r) => setTimeout(r, 16));
      for (const d of [3, 2, 1]) { out.push(window.__wheel({ deltaY: d, wheelDeltaY: 0 })); await new Promise((r) => setTimeout(r, 16)); }   // 관성 구간
      return { out, y: window.scrollY };
    });
    ok(pad.out.slice(0, 10).every((r) => !r.prevented && r.state !== "smooth"), "터치패드의 잘게 오는 휠은 막지 않는다(감속 없음)",
       JSON.stringify(pad.out.slice(0, 10)));
    ok(!pad.out[10].prevented, "같은 동작 중에 우연히 120 이 와도 원래 스크롤 그대로", JSON.stringify(pad.out[10]));
    ok(pad.out.slice(11).every((r) => !r.prevented), "관성 구간(wheelDeltaY 0)도 원래 스크롤");
    ok(Math.abs(pad.y - 167) < 1, `손가락이 움직인 만큼만 바로 옮겨진다(${pad.y}px / 167px)`);

    /* ④ 0.4초 넘게 쉬면 새 동작 — 다시 마우스 휠은 감속 */
    await page.waitForTimeout(450);
    const again = await page.evaluate(() => window.__wheel({ deltaY: 100, wheelDeltaY: -120 }));
    ok(again.prevented && again.state === "smooth", "쉬었다가 굴린 마우스 휠은 다시 감속한다", JSON.stringify(again));

    /* ⑤ 감속 중에 잘게 오는 휠이 끼면 감속을 멈추고 원래 스크롤로 넘긴다 */
    const handoff = await page.evaluate(() => window.__wheel({ deltaY: 6, wheelDeltaY: -6 }));
    ok(!handoff.prevented && handoff.state !== "smooth", "감속 중 터치패드 입력이 오면 감속을 멈추고 넘긴다", JSON.stringify(handoff));

    /* ⑥ 가로 휠 · 확대(ctrl)는 판정을 바꾸지 않는다, 두 칸 묶음(240)은 한 칸과 같다 */
    await page.waitForTimeout(450);
    const mix = await page.evaluate(async () => {
      const a = window.__wheel({ deltaY: 100, wheelDeltaY: -120 });
      await new Promise((r) => setTimeout(r, 30));
      window.__wheel({ deltaX: 30, deltaY: 0, wheelDeltaX: -36, wheelDeltaY: 0 });
      window.__wheel({ deltaY: 3, wheelDeltaY: -9, ctrlKey: true });
      await new Promise((r) => setTimeout(r, 30));
      const b = window.__wheel({ deltaY: 200, wheelDeltaY: -240 });
      return [a, b];
    });
    ok(mix.every((r) => r.prevented), "가로 휠 · 확대(ctrl)가 끼어도 마우스 휠 감속은 그대로, 두 칸 묶음(240)도 감속", JSON.stringify(mix));

    /* ⑦ 고해상도 휠(한 칸을 잘게 — 15) · 맥 마우스식 값(12)은 원래 스크롤 */
    await page.waitForTimeout(450);
    const fine = await page.evaluate(async () => {
      const a = window.__wheel({ deltaY: 12.5, wheelDeltaY: -15 });
      await new Promise((r) => setTimeout(r, 450));
      const b = window.__wheel({ deltaY: 4.000244140625, wheelDeltaY: -12 });
      return [a, b];
    });
    ok(fine.every((r) => !r.prevented), "고해상도 휠처럼 잘게 오는 값은 원래 스크롤", JSON.stringify(fine));
    await ctx.close();
  }

  /* ⑧ 맥 — 크롬(userAgentData · platform) · 사파리(platform 만)식 모두 켜지지 않는다 */
  const macs = [
    ["맥 크롬", { userAgent: MAC_CHROME }, () => {
      Object.defineProperty(Navigator.prototype, "platform", { get: () => "MacIntel" });
      Object.defineProperty(Navigator.prototype, "userAgentData", { get: () => ({ platform: "macOS", mobile: false, brands: [] }) });
    }],
    ["맥 사파리", { userAgent: MAC_SAFARI }, () => {
      Object.defineProperty(Navigator.prototype, "platform", { get: () => "MacIntel" });
      Object.defineProperty(Navigator.prototype, "userAgentData", { get: () => undefined });
    }],
  ];
  for (const [name, opts, init] of macs) {
    const { ctx, page } = await open(dir, opts, init);
    ok(await page.evaluate(() => !window.KOSSmoothScroll && !document.documentElement.classList.contains("lenis")),
       `${name}에서는 켜지지 않는다`);
    await page.mouse.wheel(0, 100);
    const last = await lastWheel(page);
    ok(last && last.trusted && !last.prevented, `${name}의 휠은 브라우저가 그대로 옮긴다`, JSON.stringify(last));
    await page.waitForTimeout(600);
    ok(Math.abs((await y(page)) - 100) < 1, `${name}에서도 휠 거리는 같다(100px)`, String(await y(page)));
    await ctx.close();
  }

  /* ⑨ 움직임 줄임 — 전과 같이 켜지지 않는다 */
  {
    const { ctx, page } = await open(dir, { reducedMotion: "reduce" });
    ok(await page.evaluate(() => !window.KOSSmoothScroll), "움직임 줄임 설정이면 켜지지 않는다");
    await ctx.close();
  }
}

try {
  await site("실사이트", "");
  await site("스테이징", "staging/");
} finally {
  await browser.close();
  server.close();
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
