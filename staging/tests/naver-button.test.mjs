/* ============================================================
   네이버 로그인 버튼 — 네이버 개발자센터 '네이버 로그인 버튼 사용 가이드'의 규격을 실제 화면에서 잰다 (2026-10-04)

   왜 있나
     사장 "네이버 개발자센터 … 우리 웹사이트에 있는 네이버 로고 크기가 괜찮은지" → 점검 → "둘 다 진행해줘".
     잰 결과 로고가 약 11px(가이드는 완성형 16px 이상)로 글자(14px)보다 작았고, 녹색이 예전 색 #03C75A 였다(가이드는
     "반드시 지정된 녹색" #03A94D). 네이버 로그인 이용약관 특약 1.2 ⑨가 버튼 가이드를 지키라고 하고, 어기면 사전 검수 · 이용 제한
     사유가 된다. 옷은 comp_common.AUTH_CSS 의 .sbtn.naver, 로고는 build_auth_comp.N_SVG(공식 원본 .ai 의 좌표) 한 곳이다.

   보는 것 (실사이트 · 스테이징의 로그인 · 회원가입, 컴퓨터 1280 · 휴대폰 390)
     ① 배경이 지정 녹색 #03A94D, 글자 · 로고가 흰색
     ② N 로고 높이 16px 이상, 글자 크기는 로고 높이보다 작다
     ③ 로고와 글자 사이 8px 안팎(글자 옆 여백 때문에 화면에서는 8~10px), 로고 모양이 공식 원본과 같다
     ④ 다른 로그인 버튼(구글 · 카카오)보다 작지 않다 — 가이드가 '타사 버튼과 함께 쓸 때 크기를 줄이지 말 것'이라고 한다
     ⑤ 이 검사가 실제로 잡는지 — 고치기 전 옷(예전 녹색 · 18px 상자 안 11px 로고)을 덧씌우면 걸린다

   실행
     node staging/tests/naver-button.test.mjs
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
/* 공식 원본(NAVER_login_KR.ai · 20px 판)에서 꺼낸 N 의 꼭짓점 — 위 왼쪽이 (0,0), 아래로 갈수록 y 가 커진다 */
const OFFICIAL_N = "M13.561 10.706 6.146 0H0v20h6.439V9.298L13.854 20H20V0h-6.439z";
/* 고치기 전 옷 — ⑤ 에서 덧씌워 검사가 잡는지 본다 */
const OLD_CSS = `.sbtn.naver{background:#03C75A!important;border-color:#03C75A!important;gap:10px!important}
.sbtn.naver svg{width:18px!important;height:18px!important}`;
const OLD_SVG = '<svg viewBox="0 0 24 24"><path fill="#fff" d="M14.7 12.55 9.05 4.5H4.5v15h4.8v-8.05l5.65 8.05h4.55v-15h-4.8z"/></svg>';

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    if (rel.endsWith("/") || rel === "") rel += "index.html";
    const data = await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title>"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({ executablePath: CHROME });

function measure() {
  const b = document.getElementById("naverBtn");
  if (!b) return null;
  const svg = b.querySelector("svg"), path = svg && svg.querySelector("path");
  const pr = path.getBoundingClientRect(), br = b.getBoundingClientRect();
  const tn = [...b.childNodes].find((n) => n.nodeType === 3 && n.textContent.trim());
  const rg = document.createRange(); rg.selectNodeContents(tn); const tr = rg.getBoundingClientRect();
  const cs = getComputedStyle(b);
  const sizes = ["googleBtn", "kakaoBtn"].map((id) => { const e = document.getElementById(id); const q = e && e.getBoundingClientRect(); return q ? [q.width, q.height] : null; });
  return { bg: cs.backgroundColor, color: cs.color, fill: getComputedStyle(path).fill, font: parseFloat(cs.fontSize),
    logoH: pr.height, logoW: pr.width, gap: tr.left - pr.right, w: br.width, h: br.height, d: path.getAttribute("d"), others: sizes };
}
const GREEN = "rgb(3, 169, 77)", WHITE = "rgb(255, 255, 255)";
function judge(r) {
  const bad = [];
  if (!r) return ["네이버 버튼 없음"];
  if (r.bg !== GREEN) bad.push(`배경 ${r.bg}`);
  if (r.color !== WHITE || r.fill !== WHITE) bad.push(`글자 ${r.color} · 로고 ${r.fill}`);
  if (r.logoH < 15.9) bad.push(`로고 ${r.logoH.toFixed(1)}px(16px 미만)`);
  if (!(r.font < r.logoH)) bad.push(`글자 ${r.font}px 가 로고 ${r.logoH.toFixed(1)}px 보다 작지 않음`);
  if (r.gap < 7.5 || r.gap > 10.5) bad.push(`로고와 글자 사이 ${r.gap.toFixed(1)}px`);
  if (r.d !== OFFICIAL_N) bad.push("로고 모양이 공식 원본과 다름");
  for (const o of r.others) if (o && (r.w < o[0] - 0.5 || r.h < o[1] - 0.5)) bad.push(`다른 버튼(${o.map(Math.round).join("×")})보다 작음`);
  return bad;
}
async function open(path, w, extraCss, oldSvg) {
  const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, isMobile: w < 500, hasTouch: w < 500 });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (r) => r.abort());   // 바깥(파이어베이스 · 통계)은 부르지 않는다 — 버튼은 자료 없이 그려진다
  const page = await ctx.newPage();
  await page.goto(HOST + path, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  if (extraCss) await page.addStyleTag({ content: extraCss });
  if (oldSvg) await page.evaluate((s) => { const b = document.getElementById("naverBtn"); if (b) b.querySelector("svg").outerHTML = s; }, oldSvg);
  const r = await page.evaluate(measure);
  await ctx.close();
  return r;
}

for (const [site, base] of [["실사이트", ""], ["스테이징", "staging/"]]) {
  for (const p of ["Login.html", "Signup.html"]) for (const w of [1280, 390]) {
    const r = await open(base + p, w);
    const bad = judge(r);
    t(!bad.length, `${site} ${p} ${w}px — ${r ? `로고 ${r.logoH.toFixed(1)}px · 글자 ${r.font}px · 사이 ${r.gap.toFixed(1)}px · 배경 ${r.bg} · 버튼 ${Math.round(r.w)}×${Math.round(r.h)}` : "버튼 없음"}${bad.length ? " · 걸림: " + bad.join(" / ") : ""}`);
  }
}
/* ⑤ 고치기 전 옷을 덧씌우면 걸리는지 */
{
  const r = await open("Login.html", 1280, OLD_CSS, OLD_SVG);
  const bad = judge(r);
  t(bad.length >= 3, `⑤ 고치기 전 옷을 덧씌우면 걸린다 — ${bad.join(" / ") || "못 잡음"}`);
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
