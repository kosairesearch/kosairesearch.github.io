/* ============================================================
   종목 페이지 — 글자끼리 겹치는 자리 · 가로로 넘치는 페이지가 없는지 (2026-10-03)

   왜 있나
     사장이 실사이트 플리토 리포트의 '다음 체크포인트'에서 시점 글('2026년 11월 중(3분기보고서 공시 예상 시점)')이 옆 글과
     겹쳐 찍힌 것을 먼저 봤다. 시점 칸이 120px 인데 줄바꿈을 막아 두어(white-space:nowrap) 긴 시점이 옆 칸으로 넘쳤다 —
     시점 글 22,180개 중 10,633개(한국어 1,779편 · 영어 2,541편)가 컴퓨터 · 태블릿 화면에서 겹쳤다. 표본 몇 장만 보던
     화면 검사는 짧은 시점만 있는 종목을 봐서 몰랐다. 그래서 '가장 긴 글을 가진 종목'을 골라 화면 폭 셋에서 잰다.

   보는 것
     자료에서 칸마다 가장 긴 글을 가진 종목(체크포인트 시점 · 위험 요인 분류 · 영문 이름 — 한국어 · 영어 각각)과 고정 표본을
     열어, 작은 컴퓨터(1101px) · 태블릿(821px) · 작은 휴대폰(360px) 화면에서
       ① 보이는 글자 조각(줄 단위 상자)끼리 겹치지 않는다
       ② 페이지가 화면보다 넓지 않다(가로 스크롤 없음)
     그리고 고치기 전의 옷(시점 칸 120px · 줄바꿈 금지)을 덧씌우면 ① 이 걸리는지 — 이 검사가 실제로 잡는지 — 도 본다.

   실행
     node staging/tests/stock-overlap.test.mjs
   ============================================================ */
import { createServer } from "node:http";
import { readFile, readdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
const WIDTHS = [1101, 821, 360];

if (!existsSync(join(ROOT, "stock/005930.html"))) { console.error("stock/ 가 없습니다 — python3 scripts/build_stock_static.py"); process.exit(1); }

// ── 칸마다 가장 긴 글을 가진 종목 ─────────────────────────────────────────
const pages = new Set(["/stock/005930.html", "/en/stock/005930.html", "/stock/300080.html", "/en/stock/300080.html", "/stock/0220W0.html"]);
const longest = [];   // [길이, 종목, 말, 칸]
for (const f of await readdir(join(ROOT, "data/reports_v2"))) {
  if (!/^[0-9A-Z]{6}\.json$/.test(f)) continue;
  const tk = f.slice(0, 6);
  if (!existsSync(join(ROOT, "stock", tk + ".html"))) continue;
  let r;
  try { r = JSON.parse(await readFile(join(ROOT, "data/reports_v2", f), "utf8")); } catch (e) { continue; }
  for (const lang of ["ko", "en"]) {
    const w = Math.max(0, ...(r.checkpoints || []).map((c) => String((c && c.when && c.when[lang]) || "").length));
    const k = Math.max(0, ...(r.risks || []).map((c) => String((c && c.cat && c.cat[lang]) || "").length));
    longest.push([w, tk, lang, "시점"], [k, tk, lang, "위험 분류"]);
  }
  longest.push([String(r.name_en || "").length, tk, "en", "영문 이름"]);
}
for (const kind of ["시점", "위험 분류", "영문 이름"]) for (const lang of ["ko", "en"]) {
  longest.filter((x) => x[3] === kind && x[2] === lang).sort((a, b) => b[0] - a[0]).slice(0, 3)
    .forEach((x) => pages.add((lang === "en" ? "/en/stock/" : "/stock/") + x[1] + ".html"));
}

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const body = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title><p>없는 페이지"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

// 페이지 안에서 잰다 — 보이는 글자 조각끼리 겹치는 자리 · 화면보다 넓은 페이지
function detect() {
  const vis = (el) => {
    const d = el.closest("details:not([open])");             // 접힌 '출처 더 보기' 안은 화면에 없다(크로미움은 펼친 자리를 돌려준다)
    if (d && !el.closest("summary")) return false;
    if (el.checkVisibility && !el.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })) return false;
    return true;
  };
  const name = (el) => {
    const sec = el.closest("section[id]");
    const one = (e) => e.tagName.toLowerCase() + (typeof e.className === "string" && e.className.trim() ? "." + e.className.trim().split(/\s+/).join(".") : "");
    return (sec ? "#" + sec.id + " " : "") + (el.parentElement ? one(el.parentElement) + " > " : "") + one(el);
  };
  const blockOf = (el) => { for (let e = el; e; e = e.parentElement) { if (getComputedStyle(e).display !== "inline") return e; } return null; };
  const boxes = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.nodeValue.trim() ? 1 : 2) });
  const seenEl = new Map();
  let n;
  while ((n = walker.nextNode())) {
    const el = n.parentElement;
    if (!el || el.closest("script,style,noscript,template")) continue;
    if (!seenEl.has(el)) seenEl.set(el, vis(el));
    if (!seenEl.get(el)) continue;
    const r = document.createRange();
    r.selectNodeContents(n);
    for (const rc of r.getClientRects()) if (rc.width >= 2 && rc.height >= 4) boxes.push({ n, el, blk: blockOf(el), x: rc.left, y: rc.top + scrollY, w: rc.width, h: rc.height });
  }
  boxes.sort((a, b) => a.y - b.y);
  const hits = [];
  for (let i = 0; i < boxes.length && hits.length < 5; i++) {
    const a = boxes[i];
    for (let j = i + 1; j < boxes.length; j++) {
      const b = boxes[j];
      if (b.y >= a.y + a.h) break;
      if (a.n === b.n) continue;
      if (a.blk === b.blk && Math.abs((a.y + a.h / 2) - (b.y + b.h / 2)) > Math.min(a.h, b.h) / 2) continue;   // 같은 덩어리의 다른 줄
      const ox = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), oy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
      if (ox > 2 && oy > 3) { hits.push(`${name(a.el)} '${a.n.nodeValue.trim().slice(0, 16)}' ⟷ ${name(b.el)} '${b.n.nodeValue.trim().slice(0, 16)}'`); break; }
    }
  }
  return { hits, wide: document.documentElement.scrollWidth - document.documentElement.clientWidth };
}

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({ viewport: { width: WIDTHS[0], height: 900 } });
const page = await ctx.newPage();
await page.route(new RegExp("^(?!" + BASE.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&") + ")"), (r) => r.abort());
const settle = () => page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 30)))));
async function open(p) {
  await page.setViewportSize({ width: WIDTHS[0], height: 900 });
  await page.goto(BASE + p, { waitUntil: "load" });
  await page.waitForFunction(() => { const g = document.getElementById("page"); return !g || g.hasAttribute("data-tier"); }, null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
}

console.log(`── 칸마다 가장 긴 글을 가진 종목 ${pages.size}장 × 화면 폭 ${WIDTHS.join(" · ")} ──`);
for (const p of pages) {
  await open(p);
  const bad = [];
  for (const w of WIDTHS) {
    if (w !== WIDTHS[0]) await page.setViewportSize({ width: w, height: 900 });
    await settle();
    const r = await page.evaluate(detect);
    if (r.hits.length) bad.push(`${w}px 겹침 ${r.hits[0]}`);
    if (r.wide > 1) bad.push(`${w}px 가로 넘침 ${r.wide}px`);
  }
  t(bad.length === 0, `${p}${bad.length ? " — " + bad.join(" · ") : ""}`);
}

console.log("── 고치기 전의 옷이면 걸리는가(이 검사가 실제로 잡는지) ──");
const top = longest.filter((x) => x[3] === "시점" && x[2] === "ko").sort((a, b) => b[0] - a[0])[0];
await open("/stock/" + top[1] + ".html");
await page.addStyleTag({ content: ".cps li{grid-template-columns:120px minmax(0,1fr)!important;gap:16px!important} .cps .when{white-space:nowrap!important}" });
await settle();
const old = await page.evaluate(detect);
t(old.hits.some((h) => h.includes("when")), `시점 칸 120px · 줄바꿈 금지 → 겹침을 잡는다 (${top[1]} · ${old.hits[0] || "없음"})`);

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
