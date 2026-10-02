/* 랜딩 공시 시계 — '오늘'은 시계 바깥, 글자는 서로 · 점 · 선과 닿지 않고 화면 밖으로 나가지 않는다 (2026-10-03 사장)

   사장: "'오늘'이 시계 안쪽에 위치하는 게 나아, 아니면 영어모드처럼 밖에 위치하는 게 나아? 더 나은 쪽으로 니가 판단해서 실행해줘."
   → 바깥. 오늘은 바깥 원(한 해의 길) 위의 점이라, 같은 원의 표지인 달 이름처럼 바깥에 둬야 '바깥은 날짜, 안쪽은 제출 기간'으로
   읽힌다. 안쪽에 두었을 때는 제출 기간 선의 머리에 붙어 그 선의 이름처럼 읽혔고, 한국어도 컴퓨터는 안쪽 · 휴대폰은 바깥으로 오갔다.

   스테이징 랜딩(staging/index.html)에 실린 시계 스크립트를 그대로 꺼내 날짜를 바꿔 가며 다시 그린다. 고른 날은 '오늘'이 달 이름과
   부딪치는 분기 첫날 앞뒤와 제출 기한 날, 폭은 휴대폰 넷(320 · 390 · 414 · 430px)과 컴퓨터 하나, 말은 한국어 · 영어다.
   두 해 모든 날 × 폭 12가지 전수 측정(겹침 0 · 화면 밖 0 · 모든 날 바깥)은 CLAUDE.md 의 공시 시계 항목에 적었다 — 여기서는
   그 결과가 되돌아가지 않게만 본다.

     node staging/tests/filing-clock.test.mjs
*/
import { readdirSync, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
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

const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({ executablePath: CHROME });

let pass = 0, fail = 0;
function ok(cond, msg, extra) {
  if (cond) { pass++; console.log("  ✅ " + msg); }
  else { fail++; console.log("  ❌ " + msg + (extra ? " — " + extra : "")); }
}

/* 분기 첫날 앞뒤(달 이름과 부딪치는 날) · 제출 기한 날 · 해의 끝. 2027 은 다음 해로 넘어가도 같은지 */
const DAYS = ["2026-01-01", "2026-01-02", "2026-03-31", "2026-04-01", "2026-04-02", "2026-05-15", "2026-06-30", "2026-07-01",
  "2026-07-02", "2026-08-14", "2026-09-30", "2026-10-01", "2026-10-02", "2026-10-03", "2026-11-16", "2026-12-31",
  "2027-04-02", "2027-10-01"];
const WIDTHS = [320, 390, 414, 430, 1440];

try {
  for (const lang of ["ko", "en"]) {
    console.log(`\n${lang === "ko" ? "한국어" : "영어"}`);
    for (const w of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width: w, height: 900 } });
      await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (r) => r.abort());
      await ctx.addInitScript((l) => { try { localStorage.setItem("kos-lang", l); } catch (e) {} }, lang);
      const page = await ctx.newPage();
      await page.goto(`${BASE}/staging/`, { waitUntil: "load" });
      await page.evaluate(() => document.fonts.ready.then(() => 1));
      const bad = await page.evaluate((days) => {
        const code = [...document.scripts].map((s) => s.textContent).find((t) => t.includes("cycData") && t.includes("function fit("));
        if (!code) return ["시계 스크립트를 찾지 못함"];
        const real = Date.now, out = [];
        const hit = (a, b) => a[0] < b[2] && b[0] < a[2] && a[1] < b[3] && b[1] < a[3];
        for (const day of days) {
          const [y, m, d] = day.split("-").map(Number), T = Date.UTC(y, m - 1, d) - 324e5 + 12 * 36e5;   // 그날 한국 시각 정오
          Date.now = () => T;
          (0, eval)(code);
          const sv = document.querySelector("#cycBox svg");
          if (!sv) { out.push(day + " 그림 없음"); continue; }
          const S = +sv.getAttribute("viewBox").split(" ")[2], R = S / 2 - (S < 420 ? 22 : 28);
          const sr = sv.getBoundingClientRect(), vw = document.documentElement.clientWidth;
          const texts = [...sv.querySelectorAll("text")].map((t) => { const b = t.getBBox();
            return { el: t, c: t.getAttribute("class") || "", s: t.textContent, b: [b.x, b.y, b.x + b.width, b.y + b.height] }; });
          const ob = [];
          sv.querySelectorAll("circle").forEach((c) => { const r = +c.getAttribute("r"), x = +c.getAttribute("cx"), yy = +c.getAttribute("cy"); ob.push([x - r, yy - r, x + r, yy + r]); });
          sv.querySelectorAll("path").forEach((p) => { const n = p.getTotalLength(), hw = +p.getAttribute("stroke-width") / 2;
            for (let l = 0; l <= n; l += 2) { const q = p.getPointAtLength(l); ob.push([q.x - hw, q.y - hw, q.x + hw, q.y + hw]); } });
          const td = texts.find((t) => t.c === "td");
          if (!td) { out.push(day + " '오늘' 글자 없음"); continue; }
          if (Math.hypot(+td.el.getAttribute("x") - S / 2, +td.el.getAttribute("y") - S / 2) <= R) out.push(day + " '오늘'이 시계 안쪽");
          texts.forEach((t) => { if (t.b[0] + sr.left < 0 || t.b[2] + sr.left > vw) out.push(day + " 화면 밖: " + t.s); });
          texts.filter((t) => ["n1", "n2", "td"].includes(t.c)).forEach((t) => {
            texts.forEach((u) => { if (u !== t && !(t.c[0] === "n" && u.c[0] === "n") && hit(t.b, u.b)) out.push(day + " 글자 겹침: " + t.s + " | " + u.s); });
            if (ob.some((o) => hit(t.b, o))) out.push(day + " 점 · 선과 겹침: " + t.s);
          });
          /* 옆 글자와 가로로 붙으면 '1월 오늘' 처럼 한 덩이로 읽힌다 */
          texts.forEach((u) => { if (u === td) return;
            if (Math.min(td.b[3], u.b[3]) - Math.max(td.b[1], u.b[1]) > 0) { const gap = Math.max(u.b[0] - td.b[2], td.b[0] - u.b[2]); if (gap >= 0 && gap < 8) out.push(day + " 옆 글자와 붙음: " + td.s + " · " + u.s); } });
        }
        Date.now = real;
        return out;
      }, DAYS);
      ok(bad.length === 0, `${w}px · ${DAYS.length}일 — '오늘'은 바깥, 겹침 · 화면 밖 · 붙은 글자 없음`, bad.slice(0, 4).join(" / "));
      await ctx.close();
    }
  }
} finally {
  await browser.close();
  server.close();
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
