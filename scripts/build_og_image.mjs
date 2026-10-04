/* ============================================================
   공유 사진(og:image) — 카카오톡 · 문자 · 소셜 미디어에 링크를 보냈을 때 뜨는 사진을 만든다(assets/og-image.png · 1200×630).
   2026-10-04 사장 1안: 첫 화면(index.html)의 점 행성과 로고. 글은 로고뿐이다 — 제목과 설명은 메신저가 사진 아래에 따로
   보여 주므로 사진에 같은 말을 넣지 않고, 바뀌는 숫자(종목 수 · 주가)는 메신저가 사진을 보관해 옛 값이 남으므로 넣지 않는다.

   그리는 법: 첫 화면을 1200×630 창에 띄워(움직임 줄임 — 행성이 다 떠오른 모습) 머리 · 제목 · 검색창을 걷어 내고, 행성 위
   빈자리 한가운데에 흰 로고를 둔다. 행성은 ORB_JS 그대로 그리되, 메신저에서 사진이 크게 줄어도 점이 보이도록 점을 첫 화면보다
   굵고 성기게 한다(SZ 1.2 → 2.4 · PD 47 → 60). 첫 화면 자체는 바꾸지 않는다.

   그림을 바꾸면 scripts/comp_common.py 의 OG_IMAGE 끝 ?v= 를 올리고 build_live.py 를 돌린다 — 카카오톡은 사진 주소로
   휴대폰에 보관하므로 주소가 같으면 옛 사진이 남는다. 카카오는 JPG · PNG 만 받고, 가로 2 : 세로 1 로 잘라 보여 준다(위아래
   15px 씩 잘린다 — 로고와 행성은 그 안쪽이다). 반짝이는 점은 시각에 따라 밝기가 달라 찍을 때마다 조금씩 다르다.

   실행
     node scripts/build_og_image.mjs                 # assets/og-image.png 를 새로 쓴다
     node scripts/build_og_image.mjs <저장할 파일>     # 다른 곳에 써서 견줘 본다
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { extname, join, normalize } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const OUT = process.argv[2] || join(ROOT, "assets/og-image.png");
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

const W = 1200, H = 630;          // 공유 사진 규격(메신저 · 검색 공통)
const ORB_V = 390;                // 행성 칸 높이 — 1200×630 창에서 첫 화면이 쓰는 값(62vh)과 같다. 행성 꼭대기가 위에서 340px
const WM = 480;                   // 로고 폭(원본 2136×348)

const server = createServer(async (req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    let data = await readFile(join(ROOT, rel || "index.html"));
    if (rel === "index.html") {   // 점만 굵고 성기게 — ORB_JS 의 PC 값 한 군데
      const s = data.toString("utf8");
      if (!s.includes("SZ=1.2;PD=47")) throw new Error("ORB_JS 의 점 크기 · 간격(SZ=1.2;PD=47)을 찾지 못했습니다");
      data = Buffer.from(s.replace("SZ=1.2;PD=47", "SZ=2.4;PD=60"));
    }
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404); res.end(String(e.message || e)); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: CHROME });
try {
  const ctx = await browser.newContext({ viewport: { width: W, height: H }, deviceScaleFactor: 1, reducedMotion: "reduce" });
  await ctx.route((u) => !u.href.startsWith(HOST), (r) => r.abort());   // 통계 · 로그인 같은 바깥 요청은 보내지 않는다
  const p = await ctx.newPage();
  const res = await p.goto(HOST + "/index.html", { waitUntil: "load" });
  if (!res || !res.ok()) throw new Error("첫 화면을 열지 못했습니다: " + (res && (await res.text())));
  await p.evaluate(() => document.fonts.ready);
  const ok = await p.evaluate(({ W, H, ORB_V, WM }) => {
    const hero = document.getElementById("hero"), orb = document.getElementById("orb"), inn = hero && hero.querySelector(".hero-in");
    if (!hero || !orb || !inn) return false;
    document.querySelectorAll("#nav,#kosEdgeTop,#kosEdgeBot,.stg,.mmenu").forEach((e) => (e.style.display = "none"));
    hero.style.setProperty("--orb-v", ORB_V + "px");
    Object.assign(hero.style, { marginTop: "0", minHeight: H + "px", height: H + "px" });
    inn.innerHTML = "";
    const img = new Image(); img.id = "ogMark"; img.src = "/assets/kosai-wordmark-white.png"; img.alt = "";
    const top = (H - ORB_V + 100) / 2 - (WM * 348 / 2136) / 2;   // 행성 꼭대기 위 빈자리의 한가운데
    Object.assign(img.style, { position: "absolute", left: (W - WM) / 2 + "px", top: top + "px", width: WM + "px", display: "block" });
    hero.appendChild(img);
    window.scrollTo(0, 0); dispatchEvent(new Event("resize"));
    return true;
  }, { W, H, ORB_V, WM });
  if (!ok) throw new Error("첫 화면의 행성(#hero · #orb)을 찾지 못했습니다 — landing.py 구조가 바뀌었는지 보십시오");
  await p.waitForFunction(() => { const i = document.getElementById("ogMark"); return i.complete && i.naturalWidth > 0; });
  await p.waitForTimeout(900);    // 크기를 바꾼 뒤 행성을 다시 그리는 시간(requestAnimationFrame)
  const grid = await p.evaluate(() => document.getElementById("orb").getAttribute("data-grid"));
  await p.screenshot({ path: OUT, clip: { x: 0, y: 0, width: W, height: H } });
  console.log(`공유 사진 → ${OUT}  (${W}×${H}, 점 격자 ${grid})`);
} finally {
  await browser.close();
  server.close();
}
