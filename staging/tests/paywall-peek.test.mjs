/* ============================================================
   리포트 상세 잠금 구간 — 흐린 미리보기가 '검열 모자이크'로 돌아가지 않는지 (2026-10-03)

   왜 있나
     사장이 스테이징 리포트의 페이월을 보고 "모자이크 부분이 어색하다"고 했다. 그때는 잠긴 절을 통째로
     filter:blur(6px) 로 흐려, 제목까지 얼룩처럼 번지고 상자 가장자리가 네모로 비쳤으며, 채움 글자가
     진한 회색 막대로 뭉쳐 520px 동안 이어진 뒤에야 안내가 나왔다.
     지금은 잠긴 첫 절의 제목은 그대로 두고, 본문 첫머리만 글자 모양(color:transparent + text-shadow)으로
     옅게 비치다 사라진 뒤 잠금 카드가 온다.

   보는 것 (컴퓨터 1280 · 휴대폰 390 · 라이트 · 다크 · 영어)
     ① 잠긴 첫 절의 제목은 또렷하다 — 글자색이 보이고, 제목과 그 위 어디에도 filter 가 없다
     ② 잠금 구간 안에 filter:blur 가 하나도 없다(상자째 흐리면 네모 자국이 남는다)
     ③ 미리보기 본문은 글자 모양만 — 글자색 투명 · 그림자 흐림
     ④ 미리보기는 짧다 — 본문 높이 200px 이하, 제목에서 잠금 카드까지 360px 이하
     ⑤ 고대비 모드(forced-colors)에서는 미리보기 본문을 숨긴다 — 글자색이 되돌아와 채움 글자가 읽힌다
     ⑥ 이 검사가 실제로 잡는지 — 옛 옷(통째 blur)을 덧씌우면 ①② 가 걸린다

   실행
     node staging/tests/paywall-peek.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title>"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

// 페이지 안에서 잰다
function measure() {
  const tz = document.getElementById("tz");
  if (!tz) return { none: true };
  const h2 = tz.querySelector(".tz-peek .sec-h h2"), fade = tz.querySelector(".tz-fade"), card = document.getElementById("lockCard");
  const filtered = [];
  for (let e = h2; e && e !== document.body; e = e.parentElement) {
    const f = getComputedStyle(e).filter;
    if (f && f !== "none") filtered.push(e.className || e.tagName);
  }
  const blurred = [...tz.querySelectorAll("*")].filter((e) => /blur/.test(getComputedStyle(e).filter)).length;
  const alpha = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return /^color\(/.test(c) ? 1 : 0; const p = m[1].split(",").map(Number); return p.length > 3 ? p[3] : 1; };
  const p = fade && (fade.querySelector("p") || fade);
  const ps = p && getComputedStyle(p);
  const hr = h2 && h2.getBoundingClientRect(), fr = fade && fade.getBoundingClientRect(), cr = card && card.getBoundingClientRect();
  return {
    title: h2 && h2.textContent.trim(), titleAlpha: h2 ? alpha(getComputedStyle(h2).color) : 0, filtered, blurred,
    fadeColorAlpha: ps ? alpha(ps.color) : null, fadeShadow: ps ? ps.textShadow : null,
    fadeDisplay: fade ? getComputedStyle(fade).display : null,
    fadeH: fr ? Math.round(fr.height) : null, toCard: hr && cr ? Math.round(cr.top - hr.bottom) : null,
  };
}

const browser = await chromium.launch({ executablePath: CHROME });
async function open({ w, theme = "light", lang = "ko", forced = false, css = "" }) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: theme, isMobile: w < 500, hasTouch: w < 500 });
  await ctx.addInitScript(([th, lg]) => { try { localStorage.setItem("kos-theme", th); localStorage.setItem("theme", th); if (lg === "en") localStorage.setItem("kos-lang", "en"); } catch (e) {} }, [theme, lang]);
  const page = await ctx.newPage();
  await page.route(new RegExp("^(?!" + BASE.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&") + ")"), (r) => r.abort());
  if (forced) await page.emulateMedia({ forcedColors: "active" });
  await page.goto(BASE + "/staging/stock.html?ticker=005930", { waitUntil: "load" });
  await page.waitForFunction(() => document.getElementById("tz"), null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  if (css) await page.addStyleTag({ content: css });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const r = await page.evaluate(measure);
  await ctx.close();
  return r;
}

console.log("── 잠긴 첫 절 — 제목은 또렷하게, 본문은 글자 모양만 짧게 ──");
for (const [w, theme, lang] of [[1280, "light", "ko"], [1280, "dark", "ko"], [390, "light", "ko"], [390, "dark", "ko"], [1280, "light", "en"]]) {
  const r = await open({ w, theme, lang });
  const tag = `${w}px · ${theme} · ${lang}`;
  if (r.none) { t(false, `${tag} — 잠금 구간(#tz)이 없다`); continue; }
  const want = lang === "en" ? "Earnings analysis" : "실적 분석";
  t(r.title === want && r.titleAlpha > 0.9 && r.filtered.length === 0, `① ${tag} 제목 '${r.title}' 또렷 (글자 불투명도 ${r.titleAlpha} · 위로 filter ${r.filtered.length}개)`);
  t(r.blurred === 0, `② ${tag} 잠금 구간 안 filter:blur ${r.blurred}개`);
  t(r.fadeColorAlpha === 0 && /\d+px/.test(r.fadeShadow || "") && !/ 0px$/.test(r.fadeShadow || ""), `③ ${tag} 본문은 글자 모양만 (글자색 불투명도 ${r.fadeColorAlpha} · 그림자 ${r.fadeShadow})`);
  t(r.fadeH > 0 && r.fadeH <= 200 && r.toCard <= 360, `④ ${tag} 미리보기 높이 ${r.fadeH}px · 제목에서 잠금 카드까지 ${r.toCard}px`);
}

console.log("── 고대비 모드 ──");
{
  const r = await open({ w: 1280, forced: true });
  t(r.fadeDisplay === "none", `⑤ forced-colors 에서 미리보기 본문 숨김 (display ${r.fadeDisplay})`);
}

console.log("── 옛 옷(통째 blur)이면 걸리는가 ──");
{
  const r = await open({ w: 1280, css: ".tz-peek{filter:blur(6px)!important}" });
  t(r.filtered.length > 0 && r.blurred > 0, `⑥ 통째 blur 를 덧씌우면 ①② 가 잡는다 (제목 위 filter ${r.filtered.length}개 · blur ${r.blurred}개)`);
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
