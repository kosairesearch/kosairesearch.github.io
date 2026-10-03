/* ============================================================
   리포트 상세 잠금 구간 — 미리보기가 '네모난 모자이크'로 돌아가지 않는지 (2026-10-03)

   왜 있나
     사장이 스테이징 리포트의 페이월을 보고 "모자이크 부분이 어색하다"고 했다. 처음에는 잠긴 절을 통째로
     filter:blur(6px) 로 흐려, 제목까지 얼룩처럼 번지고 상자 가장자리가 네모로 비쳤다. 같은 날 글자마다 그림자만
     남기는 채움 글자(color:transparent + text-shadow)로 바꿨더니 "모자이크가 딱 네모낳게 저렇게 티가 난다는 게
     어색하다" — 흐린 글자는 줄마다 회색 막대가 되어 여전히 네모로 보였다.
     지금은 흐림이 없다. 잠긴 첫 절의 제목과 앞 문단들을 실제 글 그대로 보여 주고, 두 줄 아래부터 바탕으로
     옅어진 뒤 잠금 카드가 온다(해외 경제지의 유료 기사 방식). 처음에는 네 줄에서 끊었더니 "분량이 없는 것 같잖아.
     리포트가 그냥 끝난 것 같기도 하고" — 그래서 창을 열두 줄로 넓히고 열 줄에 걸쳐 천천히 옅어지게 했다.

   보는 것 (컴퓨터 1280 · 휴대폰 390 · 라이트 · 다크 · 영어)
     ① 잠긴 첫 절의 제목은 또렷하다 — 글자색이 보이고, 제목과 그 위 어디에도 filter 가 없다
     ② 잠금 구간 안에 흐림이 하나도 없다 — filter:blur 도, 글자 그림자도, 투명한 글자색도
     ③ 미리보기 글은 실제 리포트 글이다 — 잠금을 풀었을 때(?paywall=0) 그 절의 첫 문단과 글자 하나까지 같다
     ④ 미리보기는 옅어지며 끝난다 — 창은 열 줄 넘게 열두 줄 이하, 위 한 줄 이상은 또렷하고 끝은 투명,
        글은 창 아래로 이어진다(리포트가 끝난 것처럼 보이지 않게), 제목에서 잠금 카드까지 420px 이하
     ⑤ 첫 문단이 한 줄뿐인 리포트(010140 '연간 흐름은 뚜렷하다.')도 다음 문단들까지 담아 창을 채운다
     ⑥ 실적 분석이 짧은 리포트(003780 · 631자)도 절의 마지막 문단은 미리보기에 싣지 않는다 — 절이 통째로 보이지 않게
     ⑦ 산문 절의 글이 없으면 제목만 — 채움 글자로 메우지 않는다
     ⑧ 이 검사가 실제로 잡는지 — 옛 옷 둘(통째 blur · 그림자 채움 글자)을 덧씌우면 ①② 가, 네 줄 창을 덧씌우면 ④ 가 걸린다

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
  const alpha = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return /^color\(/.test(c) ? 1 : 0; const p = m[1].split(/[\s,/]+/).filter(Boolean).map(Number); return p.length > 3 ? p[3] : 1; };
  // 흐림 — filter:blur · 글자 그림자 · 투명한 글자색(그림자만 남기는 채움 글자). 글자가 있는 요소만 본다.
  let blurred = 0, shadowed = 0, clear = 0;
  for (const e of tz.querySelectorAll("*")) {
    const cs = getComputedStyle(e);
    if (/blur/.test(cs.filter)) blurred++;
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.nodeValue.trim());
    if (!own) continue;
    if (cs.textShadow && cs.textShadow !== "none") shadowed++;
    if (alpha(cs.color) < 0.5) clear++;
  }
  const ps = fade ? [...fade.querySelectorAll("p")] : [];
  const p0 = ps[0] && getComputedStyle(ps[0]);
  const fs = fade && getComputedStyle(fade);
  const mask = fs ? (fs.maskImage && fs.maskImage !== "none" ? fs.maskImage : fs.webkitMaskImage) : null;
  const hr = h2 && h2.getBoundingClientRect(), fr = fade && fade.getBoundingClientRect(), cr = card && card.getBoundingClientRect();
  return {
    title: h2 && h2.textContent.trim(), titleAlpha: h2 ? alpha(getComputedStyle(h2).color) : 0, filtered, blurred, shadowed, clear,
    texts: ps.map((p) => p.textContent), lineH: p0 ? parseFloat(p0.lineHeight) : null, textAlpha: p0 ? alpha(p0.color) : null,
    mask: mask || "none", fadeH: fr ? Math.round(fr.height) : null, toCard: hr && cr ? Math.round(cr.top - hr.bottom) : null,
    more: fade ? fade.scrollHeight - fade.clientHeight : null,
    peekText: (tz.querySelector(".tz-peek") || { textContent: "" }).textContent.replace(/\s+/g, " ").trim(), card: !!card,
  };
}

const browser = await chromium.launch({ executablePath: CHROME });
async function open({ w, theme = "light", lang = "ko", css = [], tk = "005930", unlocked = false, strip = false }) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, colorScheme: theme, isMobile: w < 500, hasTouch: w < 500 });
  await ctx.addInitScript(([th, lg]) => { try { localStorage.setItem("kos-theme", th); localStorage.setItem("theme", th); if (lg === "en") localStorage.setItem("kos-lang", "en"); } catch (e) {} }, [theme, lang]);
  const page = await ctx.newPage();
  await page.route(new RegExp("^(?!" + BASE.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&") + ")"), (r) => r.abort());
  if (strip) await page.route(new RegExp(`/data/reports_v2/${tk}\\.json`), async (r) => {   // 산문 절 넷의 글을 뺀 리포트
    const res = await r.fetch(), j = await res.json();
    for (const k of ["earnings", "industry", "outlook", "valuation_comment"]) delete j[k];
    await r.fulfill({ response: res, body: JSON.stringify(j) });
  });
  await page.goto(`${BASE}/staging/stock.html?ticker=${tk}${unlocked ? "&paywall=0" : ""}`, { waitUntil: "load" });
  if (unlocked) {
    await page.waitForFunction(() => document.querySelector("#s04 .prose p"), null, { timeout: 15000 }).catch(() => {});
    const r = await page.evaluate(() => ({ locked: !!document.getElementById("tz"), texts: [...document.querySelectorAll("#s04 .prose p")].map((p) => p.textContent) }));
    await ctx.close();
    return r;
  }
  await page.waitForFunction(() => document.getElementById("tz"), null, { timeout: 15000 }).catch(() => {});
  await page.evaluate(() => document.fonts.ready);
  for (const c of css) await page.addStyleTag({ content: c });
  await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
  const r = await page.evaluate(measure);
  await ctx.close();
  return r;
}

// 마스크 — 'linear-gradient(rgb(0, 0, 0) 0px, rgb(0, 0, 0) 56px, rgba(0, 0, 0, 0) 112px)' 에서 또렷한 끝과 투명한 끝을 읽는다
function maskStops(m) {
  const alpha = (c) => { if (c === "transparent") return 0; const p = c.replace(/^rgba?\(|\)$/g, "").split(/[\s,/]+/).filter(Boolean).map(Number); return p.length > 3 ? p[3] : 1; };
  const stops = [...String(m).matchAll(/(rgba?\([^)]*\)|transparent)\s+(-?[\d.]+)px/g)].map((x) => ({ a: alpha(x[1]), px: +x[2] }));
  const solid = stops.filter((s) => s.a >= 0.99).reduce((v, s) => Math.max(v, s.px), -1);
  const last = stops[stops.length - 1];
  return { solid, end: last && last.a === 0 ? last.px : null };
}

const firstSec = {};
for (const [lang, tk] of [["ko", "005930"], ["en", "005930"], ["ko", "010140"], ["en", "010140"], ["ko", "003780"]]) {
  const u = await open({ w: 1280, lang, tk, unlocked: true });
  if (u.locked || !u.texts.length) { t(false, `${tk} (${lang}) — ?paywall=0 으로 열었는데 04 절 본문이 없다 (잠금 ${u.locked})`); continue; }
  firstSec[lang + tk] = u.texts;
}

console.log("── 잠긴 첫 절 — 제목은 또렷하게, 본문은 실제 글로 옅어지며 아래로 이어지게 ──");
for (const [w, theme, lang] of [[1280, "light", "ko"], [1280, "dark", "ko"], [390, "light", "ko"], [390, "dark", "ko"], [1280, "light", "en"]]) {
  const r = await open({ w, theme, lang });
  const tag = `${w}px · ${theme} · ${lang}`;
  if (r.none) { t(false, `${tag} — 잠금 구간(#tz)이 없다`); continue; }
  const want = lang === "en" ? "Earnings analysis" : "실적 분석";
  t(r.title === want && r.titleAlpha > 0.9 && r.filtered.length === 0, `① ${tag} 제목 '${r.title}' 또렷 (글자 불투명도 ${r.titleAlpha} · 위로 filter ${r.filtered.length}개)`);
  t(r.blurred === 0 && r.shadowed === 0 && r.clear === 0, `② ${tag} 흐림 없음 (filter:blur ${r.blurred} · 글자 그림자 ${r.shadowed} · 투명 글자 ${r.clear})`);
  const open1 = firstSec[lang + "005930"] || [];
  const same = r.texts.length > 0 && r.texts.every((x, i) => x === open1[i]);
  t(same && r.textAlpha > 0.9, `③ ${tag} 실제 글 — 잠금을 풀었을 때의 04 절 첫 문단과 같다 (${r.texts.length}문단 · '${(r.texts[0] || "").slice(0, 24)}…' · 글자 불투명도 ${r.textAlpha})`);
  const m = maskStops(r.mask);
  const lines = r.lineH ? r.fadeH / r.lineH : 99;
  t(lines > 10 && lines <= 12.05 && m.solid >= r.lineH && m.end != null && m.end <= r.fadeH + 1 && r.more > 0 && r.toCard <= 420,
    `④ ${tag} 창 ${r.fadeH}px(${lines.toFixed(1)}줄) · 또렷 ${m.solid}px → 투명 ${m.end}px · 창 아래로 이어지는 글 ${r.more}px · 제목에서 잠금 카드까지 ${r.toCard}px`);
}

console.log("── 첫 문단이 한 줄뿐인 리포트 ──");
for (const lang of ["ko", "en"]) {
  const r = await open({ w: 1280, lang, tk: "010140" });
  const open1 = firstSec[lang + "010140"] || [];
  const same = r.texts.length > 0 && r.texts.every((x, i) => x === open1[i]);
  const short = (open1[0] || "").length < 60;
  t(same && (!short || r.texts.length >= 2) && r.more > 0, `⑤ 010140 (${lang}) ${r.texts.length}문단 — 첫 문단 '${(open1[0] || "").slice(0, 24)}' ${open1[0] ? open1[0].length : 0}자${short ? " · 다음 문단까지 담음" : ""} · 창 아래로 이어지는 글 ${r.more}px`);
}

console.log("── 실적 분석이 짧은 리포트 ──");
{
  const r = await open({ w: 1280, tk: "003780" });
  const open1 = firstSec["ko003780"] || [];
  const same = r.texts.length > 0 && r.texts.every((x, i) => x === open1[i]);
  t(same && r.texts.length < open1.length, `⑥ 003780 미리보기 ${r.texts.length}문단 < 절 전체 ${open1.length}문단 — 마지막 문단은 싣지 않는다`);
}

console.log("── 산문 절의 글이 없을 때 ──");
{
  const r = await open({ w: 1280, strip: true });
  t(!r.none && r.texts.length === 0 && r.mask === "none" && r.title === "실적 분석" && r.peekText.replace(/\s+/g, "") === "04실적분석" && r.card,
    `⑦ 제목만 남는다 (미리보기 글 '${r.peekText}' · 잠금 카드 ${r.card})`);
}

console.log("── 옛 옷이면 걸리는가 ──");
{
  const r = await open({ w: 1280, css: [".tz-peek{filter:blur(6px)!important}"] });
  t(r.filtered.length > 0 && r.blurred > 0, `⑧ 통째 blur 를 덧씌우면 ①② 가 잡는다 (제목 위 filter ${r.filtered.length}개 · blur ${r.blurred}개)`);
  const s = await open({ w: 1280, css: [".tz-fade *{color:transparent!important;text-shadow:0 0 8px rgba(128,128,128,.55)!important}"] });
  t(s.shadowed > 0 && s.clear > 0, `⑧ 그림자 채움 글자를 덧씌우면 ② 가 잡는다 (글자 그림자 ${s.shadowed} · 투명 글자 ${s.clear})`);
  const q = await open({ w: 1280, css: [".tz-fade{max-height:112px!important}"] });
  const ql = q.lineH ? q.fadeH / q.lineH : 99;
  t(!(ql > 10), `⑧ 네 줄 창을 덧씌우면 ④ 가 잡는다 (창 ${q.fadeH}px · ${ql.toFixed(1)}줄)`);
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
