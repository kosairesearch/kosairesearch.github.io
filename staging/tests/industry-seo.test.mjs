/* ============================================================
   업종 상세의 검색 노출 머리 — 실사이트 industry.html?sector=…

   왜 있나
     사이트맵(scripts/generate_sitemap.py)은 업종 상세 주소 30개를 따로 올린다. 그런데 2026-10-03 새 디자인을
     실사이트로 옮긴 판은 canonical 이 목록 주소(industry.html)로 고정돼 있어, 업종 상세 30개가 스스로를 목록의
     중복이라고 답했다(독립 검토가 잡았다). 옛 실사이트는 머리의 즉시 보정과 setSEO() 로 업종마다 고쳤다.
     지금은 build_industry_comp.SEO_HEAD · SEO_FN 이 같은 일을 한다(실사이트만).

   보는 것
     · 사이트맵의 업종 주소마다 — canonical · og:url 이 사이트맵 주소와 글자 하나까지 같다
       (괄호가 든 '인공지능(AI)' 는 %28AI%29 — 사이트맵의 urllib.parse.quote 와 같은 글자)
     · 제목 · 설명 · 공유 제목 · 공유 설명에 업종 이름이 든다(분석 글이 있는 업종)
     · 같은 업종을 다른 글자로 불러도(괄호 그대로 · 소문자 %) canonical 은 사이트맵 주소 하나
     · 목록과 모르는 업종은 목록 주소 그대로

   실행
     node staging/tests/industry-seo.test.mjs
     PAGE=다른/industry.html node staging/tests/industry-seo.test.mjs   # 다른 판으로(고치기 전 판은 실패해야 한다)
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const PAGE = process.env.PAGE || join(ROOT, "industry.html");
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel.endsWith("/")) rel += "index.html";
    const file = rel.replace(/^[/\\]+/, "") === "industry.html" ? PAGE : join(ROOT, rel);
    const body = await readFile(file);
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

let pass = 0, fail = 0;
const ok = (cond, name, extra = "") => {
  if (cond) { pass++; } else { fail++; console.log(`FAIL  ${name}${extra ? "  — " + extra : ""}`); }
};

/* 사이트맵의 업종 주소 · 분석 글이 있는 업종 */
const sitemap = readFileSync(join(ROOT, "sitemap.xml"), "utf8");
const URLS = [...sitemap.matchAll(/<loc>(https:\/\/kosai\.kr\/industry\.html\?sector=[^<]+)<\/loc>/g)].map((m) => m[1].replace(/&amp;/g, "&"));
const secRaw = readFileSync(join(ROOT, "data/sectors.js"), "utf8");
const SECTORS = JSON.parse(secRaw.slice(secRaw.indexOf("{")).trim().replace(/;$/, "")).sectors || {};

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext();
await ctx.route("**/*", (route) => (route.request().url().startsWith(BASE) ? route.continue() : route.abort()));
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

async function head(path) {
  await page.goto(BASE + path, { waitUntil: "load" });
  await page.waitForFunction(() => document.querySelector("#app") && document.querySelector("#app").children.length > 0, null, { timeout: 15000 });
  return page.evaluate(() => {
    const a = (q, k) => (document.querySelector(q) || {}).getAttribute?.(k) ?? null;
    return { title: document.title, canon: a("link[rel=canonical]", "href"), ogurl: a('meta[property="og:url"]', "content"),
      desc: a("meta[name=description]", "content"), ogt: a('meta[property="og:title"]', "content"), ogd: a('meta[property="og:description"]', "content"),
      twt: a('meta[name="twitter:title"]', "content"), twd: a('meta[name="twitter:description"]', "content"), h1: (document.querySelector("h1") || {}).textContent || "" };
  });
}

ok(URLS.length >= 20, "사이트맵에 업종 상세 주소가 있다", `${URLS.length}개`);
for (const url of URLS) {
  const enc = url.split("?sector=")[1];
  const sec = decodeURIComponent(enc);
  const h = await head("/industry.html?sector=" + enc);
  ok(h.h1 === sec, `${sec} — 상세 화면이 그려진다`, h.h1);
  ok(h.canon === url, `${sec} — canonical = 사이트맵 주소`, h.canon);
  ok(h.ogurl === url, `${sec} — og:url = 사이트맵 주소`, h.ogurl);
  ok(h.title.includes(sec) && h.ogt === h.title && h.twt === h.title, `${sec} — 제목 · 공유 제목에 업종 이름`, `${h.title} / ${h.ogt}`);
  if (SECTORS[sec]) {
    ok(h.desc.includes(sec) && h.ogd === h.desc && h.twd === h.desc, `${sec} — 설명 · 공유 설명에 업종 이름`, h.desc);
  }
}

/* 같은 업종을 다른 글자로 불러도 canonical 은 사이트맵 주소 하나 */
const ai = URLS.find((u) => u.includes("%28AI%29"));
if (ai) {
  const h1 = await head("/industry.html?sector=" + encodeURIComponent("인공지능(AI)"));
  ok(h1.canon === ai, "괄호를 그대로 둔 주소도 canonical 은 %28AI%29", h1.canon);
}
const semi = URLS.find((u) => decodeURIComponent(u.split("?sector=")[1]) === "반도체");
if (semi) {
  const lower = "/industry.html?sector=" + semi.split("?sector=")[1].toLowerCase();
  const h2 = await head(lower);
  ok(h2.canon === semi, "소문자 % 로 불러도 canonical 은 사이트맵 주소", h2.canon);
}

/* 목록 · 모르는 업종 — 목록 주소 그대로 */
const LIST = "https://kosai.kr/industry.html";
const h3 = await head("/industry.html");
ok(h3.canon === LIST && h3.ogurl === LIST, "목록 — canonical · og:url 이 목록 주소", h3.canon);
const h4 = await head("/industry.html?sector=" + encodeURIComponent("없는업종"));
ok(h4.canon === LIST && h4.ogurl === LIST, "모르는 업종 — 목록으로 그리고 목록 주소", h4.canon);
ok(h4.desc === h3.desc, "모르는 업종 — 설명도 목록 그대로", h4.desc);

ok(errors.length === 0, "페이지 오류 없음", errors.slice(0, 3).join(" | "));

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
