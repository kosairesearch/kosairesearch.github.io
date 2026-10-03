/* ============================================================
   모닝브리핑 지난 호(스테이징 · 실사이트) — 발행한 호마다 페이지가 있고 호수 · 이전 호 · 다음 호 · 목록 · 대표 주소가 맞는지 (2026-10-04)

   왜 있나
     사장 "모닝브리핑 지난 호 스테이징에 만들어봐" → "그냥 최대한 좋은 쪽으로 해줘". 랜딩 브리핑 띠가 '제31호 읽기' 처럼 호수를
     내세우는데 지난 호를 볼 길이 없었다. scripts/build_brief_comp.py 의 build_archive() 가 발행한 브리핑(meta.publishedAt)마다
     brief-YYYY-MM-DD.html 과 목록 brief-archive.html 을 만든다 — 스테이징(staging/)과 실사이트(루트). 실사이트는 아침 작업의
     render_brief.py 가 발행 직후에 만든다. 호수는 발행할 때 브리핑에 적어 둔 meta.issueNo 다(없으면 발행한 순서) — 랜딩의 호수
     (stamp_counts.brief_no)와 같은 수. 발행하지 않은 원고(9월 13일 시험 원고)는 호수에도 목록에도 들지 않는다.

   보는 것 (두 사이트 모두)
     ① 발행한 브리핑마다 페이지가 하나씩 — 빠진 호도, 발행하지 않은 원고의 페이지도, 발행 목록에 없는 페이지도 없다
     ② 호수 — 그 호의 날짜 줄이 브리핑에 적힌 호수(meta.issueNo · 없으면 발행한 순서)와 같고, 호수가 날짜 순으로 커진다
     ③ 이전 호 · 다음 호 — 바로 앞뒤 호를 가리키고, 적힌 제목 · 호수가 그 호 페이지의 제목 · 호수와 같다.
        첫 호는 이전 호가 없고 최신 호는 다음 호가 없다. 모든 호에 '지난 호 전체 보기'
     ④ 지난 호 알림 — 최신 호가 아니면 '지난 호입니다 · 최신 호 보기', 최신 호에는 없다. brief.html 은 최신 호 페이지와 본문이 같다
     ⑤ 목록 — 모든 호가 최신 호부터 한 번씩, 주소 · 호수 · 날짜 · 제목이 그 호 페이지와 같다. 머리 문장의 편수가 발행 수와 같다
     ⑥ 검색 노출 — 스테이징은 모두 noindex. 실사이트는 색인 대상이고, 대표 주소(canonical)는 brief.html · 목록 · 지난 호가 자기 주소,
        가장 최근 호의 고정 페이지만 brief.html(같은 글). 호마다 '날짜 모닝브리핑 제N호.' 로 시작하는 검색 설명
     ⑦ 화면 — 목록 · 최신 호 · 가운데 호 · 첫 호(실사이트는 목록 · 가운데 호)를 컴퓨터 1280 · 휴대폰 390 에서 열어 가로 넘침이 없고,
        영어로 열면 한글이 남지 않는다(글 · 속성 · 문서 제목 · 날짜 줄 앞의 호수 'Morning Brief No. N').
        이전 호 · 다음 호는 위아래로 쌓여 모두 왼쪽 정렬이고, 첫 칸 위에 선이 겹치지 않는다(2026-10-04 사장 "정렬이 어색한데" —
        두 칸으로 나눠 다음 호를 오른쪽 정렬했을 때 두 줄 제목의 왼쪽 끝이 들쭉날쭉했고, 다음 호만 있는 첫 호는 휴대폰에서 선이 두 줄이었다).
        그 옛 배치를 덧씌우면 이 확인이 걸리는 것도 본다
     ⑧ 눌러서 옮겨 가기 — 목록에서 호를 누르면 그 호로, '다음 호' · '지난 호 전체 보기' · '최신 호 보기' 를 누르면 그곳으로 간다
     ⑨ 이 검사가 실제로 잡는지 — 목록에서 한 호를 빼거나, 호수를 하나 밀거나, 시험 원고의 페이지를 두거나, 다음 호 주소를
        엉뚱한 호로 바꾸거나, 지난 호의 대표 주소를 brief.html 로 바꾸면 ①~⑥ 이 걸린다

   실행
     node staging/tests/brief-archive.test.mjs
     DIR=다른/스테이징/폴더 node staging/tests/brief-archive.test.mjs   # 스테이징 쪽을 다른 폴더의 페이지로 본다
   ============================================================ */
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { readFileSync, readdirSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch (e) { console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요."); process.exit(2); }

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SDIR = process.env.DIR ? resolve(process.env.DIR) : join(ROOT, "staging");
const SITE = "https://kosai.kr";
const CHROME = process.env.CHROME || "/opt/pw-browsers/chromium";
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };

let pass = 0, fail = 0;
const t = (ok, msg) => { if (ok) { pass++; console.log("  ✔ " + msg); } else { fail++; console.log("  ✘ " + msg); } };

/* ── 발행한 브리핑 — 생성기(published · number_of)와 같은 규칙: 날짜 이름의 자료 가운데 meta.publishedAt 이 있는 것, 날짜순.
      호수는 meta.issueNo(정수) — 없으면 발행한 순서 ── */
const BRIEFS = join(ROOT, "data/briefs");
const all = readdirSync(BRIEFS).filter((f) => /^\d{4}-\d\d-\d\d\.json$/.test(f)).sort();
const items = [], NO = {};
for (const f of all) {
  let doc;
  try { doc = JSON.parse(readFileSync(join(BRIEFS, f), "utf8")); } catch (e) { continue; }
  const m = doc.meta || {};
  if (!m.publishedAt) continue;
  items.push(f.slice(0, 10));
  NO[f.slice(0, 10)] = Number.isInteger(m.issueNo) && m.issueNo > 0 ? m.issueNo : items.length;
}
const drafts = all.map((f) => f.slice(0, 10)).filter((d) => !items.includes(d));
const N = items.length;

/* ── 페이지 글에서 읽기 ── */
const dec = (s) => s.replace(/<[^>]+>/g, "").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&").trim();
function readIssue(html) {
  const d = html.match(/<div class="mb-date" data-no="제(\d+)호" data-n="(\d+)">/);
  const h1 = html.match(/<article class="mb">[\s\S]*?<h1[^>]*>([\s\S]*?)<\/h1>/);
  const nav = {};
  for (const m of html.matchAll(/<a class="mb-nv mb-nv--(prev|next)" href="([^"]+)"><span class="mb-nv-k">[^<]*<\/span><span class="mb-nv-t">([^<]*)<\/span><span class="mb-nv-d"><span>제(\d+)호<\/span><span>([^<]*)<\/span><\/span><\/a>/g))
    nav[m[1]] = { href: m[2], title: dec(m[3]), no: +m[4], date: m[5] };
  const canon = html.match(/<link rel="canonical" href="([^"]+)"/), desc = html.match(/<meta name="description" content="([^"]*)"/);
  return { no: d ? +d[1] : null, n: d ? +d[2] : null, title: h1 ? dec(h1[1]) : null, old: html.includes('<p class="mb-old">'),
           oldLink: /<p class="mb-old">[^<]*<a href="brief\.html">/.test(html), all: html.includes('<p class="mb-all"><a href="brief-archive.html">'), nav,
           canon: canon ? canon[1] : null, desc: desc ? dec(desc[1]) : null, noindex: /<meta name="robots" content="[^"]*noindex/.test(html) };
}
function readArchive(html) {
  const rows = [...html.matchAll(/<li><a href="([^"]+)"><span class="ba-no">제(\d+)호<\/span><span class="ba-d">([^<]*)<\/span><span class="ba-t">([^<]*)<\/span><\/a><\/li>/g)]
    .map((m) => ({ href: m[1], no: +m[2], date: m[3], title: dec(m[4]) }));
  const sub = html.match(/지금까지 발행한 모닝브리핑 (\d+)편을/);
  return { rows, count: sub ? +sub[1] : null };
}
// 본문 — 페이지 끝 공통 사전(finish 가 그 페이지 글에서 골라 싣는 덩어리)은 뺀다. brief.html 은 머리의 고정 설명문과 겹치는 항목
// 서너 개가 더 실려 있을 뿐이고(화면에 안 보임), 화면 글과 그 호의 사전(첫 덩어리)은 같아야 한다.
const body = (html) => {
  const b = (html.match(/<body>[\s\S]*<\/body>/) || [""])[0];
  let k = 0;
  return b.replace(/<script type="application\/json" data-kos-i18n>[\s\S]*?<\/script>/g, (m) => (k++ ? "" : m));
};
const WEEK = ["일", "월", "화", "수", "목", "금", "토"];
const md = (d) => { const x = new Date(d + "T00:00:00Z"); return `${x.getUTCMonth() + 1}월 ${x.getUTCDate()}일 (${WEEK[x.getUTCDay()]})`; };
const ymd = (d) => `${d.slice(0, 4)}년 ` + md(d);

/* ①~⑥ — files: { 파일 이름: 글 } 에서 어긋난 곳을 모두 적어 돌려준다(⑨ 에서 일부러 틀린 판에도 돌린다). live — 실사이트 규칙(⑥) */
function staticProblems(files, live) {
  const bad = { 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] };
  const pages = Object.keys(files).filter((f) => /^brief-\d{4}-\d\d-\d\d\.html$/.test(f));
  for (const d of items) if (!files[`brief-${d}.html`]) bad[1].push(`brief-${d}.html 없음`);
  for (const f of pages) if (!items.includes(f.slice(6, 16))) bad[1].push(`${f} — 발행 목록에 없는 페이지${drafts.includes(f.slice(6, 16)) ? "(발행하지 않은 원고)" : ""}`);
  const info = {};
  items.forEach((d) => { const h = files[`brief-${d}.html`]; if (h) info[d] = readIssue(h); });
  items.forEach((d, i) => {
    const p = info[d]; if (!p) return;
    if (p.no !== NO[d] || p.n !== NO[d]) bad[2].push(`${d} — 제${p.no}호(data-n ${p.n}), 기대 제${NO[d]}호`);
    if (i && NO[d] <= NO[items[i - 1]]) bad[2].push(`${d} — 제${NO[d]}호가 앞 호(제${NO[items[i - 1]]}호)보다 크지 않다`);
    for (const [side, j] of [["prev", i - 1], ["next", i + 1]]) {
      const c = p.nav[side], want = items[j];
      if (!want) { if (c) bad[3].push(`${d} — ${side === "prev" ? "첫 호인데 이전 호" : "최신 호인데 다음 호"}가 있다`); continue; }
      if (!c) { bad[3].push(`${d} — ${side === "prev" ? "이전 호" : "다음 호"}가 없다`); continue; }
      const q = info[want];
      if (c.href !== `brief-${want}.html` || c.no !== NO[want] || c.date !== ymd(want) || !q || c.title !== q.title)
        bad[3].push(`${d} — ${side} 칸 ${c.href} · 제${c.no}호 · ${c.date} · '${c.title}' (기대 brief-${want}.html · 제${NO[want]}호 · ${ymd(want)} · '${q && q.title}')`);
    }
    if (!p.all) bad[3].push(`${d} — '지난 호 전체 보기' 없음`);
    const latest = i === N - 1;
    if (latest ? p.old : !(p.old && p.oldLink)) bad[4].push(`${d} — 지난 호 알림 ${p.old ? "있음" : "없음"}(최신 호 ${latest})`);
    if (live) {   // ⑥ 실사이트 — 색인 · 대표 주소 · 검색 설명
      const want = latest ? `${SITE}/brief.html` : `${SITE}/brief-${d}.html`;
      if (p.noindex) bad[6].push(`${d} — noindex`);
      if (p.canon !== want) bad[6].push(`${d} — 대표 주소 ${p.canon} (기대 ${want})`);
      if (!p.desc || !p.desc.startsWith(`${ymd(d)} 모닝브리핑 제${NO[d]}호.`) || p.desc.length < 40) bad[6].push(`${d} — 검색 설명 '${(p.desc || "").slice(0, 30)}'`);
    } else if (!p.noindex) bad[6].push(`${d} — 스테이징인데 noindex 가 아니다`);
  });
  const latestPage = N && files[`brief-${items[N - 1]}.html`];
  if (N && (!files["brief.html"] || !latestPage || body(files["brief.html"]) !== body(latestPage))) bad[4].push("brief.html 의 본문이 최신 호 페이지와 다르다");
  if (live && files["brief.html"] && readIssue(files["brief.html"]).canon !== `${SITE}/brief.html`) bad[6].push("brief.html 의 대표 주소가 자기 주소가 아니다");
  const a = files["brief-archive.html"] ? readArchive(files["brief-archive.html"]) : { rows: [], count: null };
  if (a.count !== N) bad[5].push(`머리 문장 ${a.count}편, 발행 ${N}편`);
  if (a.rows.length !== N) bad[5].push(`목록 ${a.rows.length}줄, 발행 ${N}편`);
  a.rows.forEach((r, k) => {
    const i = N - 1 - k, d = items[i], p = d && info[d];
    if (!d || r.href !== `brief-${d}.html` || r.no !== NO[d] || r.date !== md(d) || !p || r.title !== p.title)
      bad[5].push(`${k + 1}째 줄 ${r.href} · 제${r.no}호 · ${r.date} · '${r.title}' (기대 brief-${d}.html · 제${d && NO[d]}호 · ${d && md(d)} · '${p && p.title}')`);
  });
  if (live && files["brief-archive.html"] && readIssue(files["brief-archive.html"]).canon !== `${SITE}/brief-archive.html`) bad[6].push("목록의 대표 주소가 자기 주소가 아니다");
  return bad;
}

const read = (dir) => {
  const files = {};
  for (const f of readdirSync(dir)) if (/^brief(-\d{4}-\d\d-\d\d|-archive)?\.html$/.test(f)) files[f] = readFileSync(join(dir, f), "utf8");
  return files;
};
const SITES = [{ name: "스테이징", files: read(SDIR), live: false, base: "staging/" }, { name: "실사이트", files: read(ROOT), live: true, base: "" }];

console.log(`── 발행한 브리핑 ${N}편(${items[0]} 제${NO[items[0]]}호 ~ ${items[N - 1]} 제${NO[items[N - 1]]}호) · 발행하지 않은 원고 ${drafts.length}편(${drafts.join(", ") || "없음"})`);
for (const s of SITES) {
  const P = staticProblems(s.files, s.live);
  const show = (k) => P[k].slice(0, 4).join(" / ") + (P[k].length > 4 ? ` 외 ${P[k].length - 4}건` : "");
  t(N > 0 && !P[1].length, `${s.name} ① 발행한 ${N}편마다 페이지가 하나씩 — 빠진 호 · 원고 페이지 · 남은 페이지 없음 ${show(1)}`);
  t(!P[2].length, `${s.name} ② 호수가 브리핑에 적힌 호수와 같고 날짜 순으로 커진다 ${show(2)}`);
  t(!P[3].length, `${s.name} ③ 이전 호 · 다음 호가 바로 앞뒤 호를 가리키고 제목 · 호수 · 날짜가 그 호와 같다 ${show(3)}`);
  t(!P[4].length, `${s.name} ④ 지난 호 알림은 최신 호가 아닐 때만 · brief.html 본문 = 최신 호 페이지 본문 ${show(4)}`);
  t(!P[5].length, `${s.name} ⑤ 목록에 ${N}편이 최신 호부터 · 주소 · 호수 · 날짜 · 제목이 그 호와 같다 ${show(5)}`);
  t(!P[6].length, `${s.name} ⑥ ${s.live ? "색인 대상 · 대표 주소(최신 호만 brief.html) · 호마다 검색 설명" : "모두 noindex"} ${show(6)}`);
}

/* ⑨ 일부러 틀린 판 — 검사가 정말 잡는지(실사이트 판으로) */
{
  const files = SITES[1].files, last = items[N - 1], mid = items[Math.floor(N / 2)];
  const drop = { ...files, "brief-archive.html": files["brief-archive.html"].replace(/<li><a href="brief-[^"]+">[\s\S]*?<\/li>/, "") };
  const shift = { ...files, [`brief-${mid}.html`]: files[`brief-${mid}.html`].replace(/data-no="제(\d+)호" data-n="(\d+)"/, (m, a, b) => `data-no="제${+a + 1}호" data-n="${+b + 1}"`) };
  const draft = { ...files, ...(drafts[0] ? { [`brief-${drafts[0]}.html`]: files[`brief-${mid}.html`] } : { "brief-2000-01-01.html": files[`brief-${mid}.html`] }) };
  const wrong = { ...files, [`brief-${mid}.html`]: files[`brief-${mid}.html`].replace(/(mb-nv--next" href=")brief-[^"]+(")/, `$1brief-${last}.html$2`) };
  const canon = { ...files, [`brief-${mid}.html`]: files[`brief-${mid}.html`].replace(/(<link rel="canonical" href=")[^"]+(")/, `$1${SITE}/brief.html$2`) };
  const n = (b) => Object.values(b).reduce((s, x) => s + x.length, 0);
  const r = [drop, shift, draft, wrong, canon].map((f) => staticProblems(f, true));
  t(r[0][5].length > 0 && r[1][2].length > 0 && r[2][1].length > 0 && r[3][3].length > 0 && r[4][6].length > 0,
    `⑨ 틀린 판 다섯을 잡는다 — 목록에서 한 호 빼기 ⑤ ${r[0][5].length}건 · 호수 밀기 ② 외 ${n(r[1])}건 · 원고 페이지 ① ${r[2][1].length}건 · ` +
    `다음 호를 엉뚱한 호로 ③ ${r[3][3].length}건 · 지난 호의 대표 주소를 brief.html 로 ⑥ ${r[4][6].length}건`);
}

/* ── 화면 ⑦⑧ ── */
const server = createServer(async (req, res) => {
  try {
    let rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "").replace(/^[/\\]+/, "");
    if (rel.endsWith("/") || rel === "") rel += "index.html";
    const file = rel.startsWith("staging/") ? join(SDIR, rel.slice(8)) : join(ROOT, rel);
    const data = await readFile(file);
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(data);
  } catch (e) { res.writeHead(404, { "content-type": "text/html; charset=utf-8" }); res.end("<!doctype html><title>404</title>"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const HOST = `http://127.0.0.1:${server.address().port}/`;
const browser = await chromium.launch({ executablePath: CHROME });

async function open(lang, w, url) {
  const ctx = await browser.newContext({ viewport: { width: w, height: w < 500 ? 844 : 900 }, isMobile: w < 500, hasTouch: w < 500 });
  await ctx.addInitScript((lg) => { try { if (lg === "en") localStorage.setItem("kos-lang", "en"); } catch (e) {} }, lang);
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (r) => r.abort());   // 바깥(파이어베이스 · 통계)은 부르지 않는다 — 이 화면은 자료 없이 그려진다
  const page = await ctx.newPage();
  await page.goto(url, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
  return { ctx, page };
}
function look() {
  const HAN = /[가-힣]/, left = [];
  const note = (s, w) => { const x = (s || "").replace(/\s+/g, " ").trim(); if (x && HAN.test(x) && left.length < 6) left.push(`${w}: ${x.slice(0, 40)}`); };
  const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = tw.nextNode(); n; n = tw.nextNode()) {
    const el = n.parentElement;
    if (!el || el.closest('script,style,noscript,template,[data-lang="ko"]')) continue;
    if (el.closest(".ks-seg") && n.nodeValue.trim() === "한국어") continue;
    note(n.nodeValue, el.tagName.toLowerCase() + (el.className ? "." + String(el.className).split(" ")[0] : ""));
  }
  for (const el of document.body.querySelectorAll("[placeholder],[aria-label],[title],[alt]"))
    for (const a of ["placeholder", "aria-label", "title", "alt"]) note(el.getAttribute(a), el.tagName.toLowerCase() + "@" + a);
  note(document.title, "title");
  const md = document.querySelector(".mb-date");
  const before = md ? getComputedStyle(md, "::before").content : "";
  note(before, ".mb-date::before");
  // 이전 호 · 다음 호 — 칸마다 왼쪽 끝이 칸 묶음의 왼쪽 끝과 같고(왼쪽 정렬), 위아래로 쌓이고, 첫 칸 위에 선이 없다(묶음의 위 선과 겹치지 않게)
  const nav = document.querySelector(".mb-nav");
  let navOk = null, navNote = "";
  if (nav) {
    const L = nav.getBoundingClientRect().left, cards = [...nav.querySelectorAll(".mb-nv")];
    const flush = cards.every((c) => Math.abs(c.getBoundingClientRect().left - L) < 1
      && [c, c.querySelector(".mb-nv-t")].every((e) => e && /^(start|left)$/.test(getComputedStyle(e).textAlign)));
    const stacked = cards.every((c, i) => !i || c.getBoundingClientRect().top >= cards[i - 1].getBoundingClientRect().bottom - 0.5);
    const firstRule = cards.length ? parseFloat(getComputedStyle(cards[0]).borderTopWidth) : 0;
    navOk = cards.length > 0 && flush && stacked && !firstRule;
    navNote = `칸 ${cards.length} · ${flush ? "왼쪽 정렬" : "정렬 어긋남"} · ${stacked ? "위아래" : "나란히"}${firstRule ? " · 첫 칸 위 선 겹침" : ""}`;
  }
  return { left, before, navOk, navNote, wide: document.documentElement.scrollWidth - document.documentElement.clientWidth, lang: document.documentElement.lang };
}
// 고치기 전 배치(2026-10-04 까지) — 두 칸으로 나눠 다음 호를 오른쪽 정렬, 휴대폰에서는 다음 호 위에 늘 선
const OLD_NAV_CSS = `.mb-nav{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 40px}
.mb-nv+.mb-nv{margin-top:0;border-top:0} .mb-nv--next{grid-column:2;text-align:right}
@media (max-width:820px){.mb-nav{grid-template-columns:minmax(0,1fr)} .mb-nv--next{grid-column:1;text-align:left;margin-top:20px;border-top:1px solid var(--hair)}}`;

if (N) {
  const mid = Math.floor(N / 2);
  for (const s of SITES) {
    const shots = [["목록", "brief-archive.html"], ["가운데 호", `brief-${items[mid]}.html`]]
      .concat(s.live ? [] : [["최신 호", "brief.html"], ["첫 호", `brief-${items[0]}.html`]]);
    for (const lang of ["ko", "en"]) for (const w of [1280, 390]) {
      const rows = [];
      let ok = true;
      for (const [name, path] of shots) {
        const { ctx, page } = await open(lang, w, HOST + s.base + path);
        const r = await page.evaluate(look);
        await ctx.close();
        const fine = r.wide <= 1 && (path === "brief-archive.html" || r.navOk)
          && (lang === "ko" ? (path === "brief-archive.html" || /모닝브리핑/.test(r.before)) : (r.lang === "en" && !r.left.length && (path === "brief-archive.html" || /Morning Brief No\. \d+/.test(r.before))));
        if (!fine) ok = false;
        rows.push(`${name} 넘침 ${r.wide}${lang === "en" ? ` · 한글 ${r.left.length}${r.left.length ? " (" + r.left.join(" / ") + ")" : ""}` : ""}${path === "brief-archive.html" ? "" : ` · 호수 ${r.before} · ${r.navNote}`}`);
      }
      t(ok, `${s.name} ⑦ ${lang === "ko" ? "한국어" : "영어"} · ${w}px — ${rows.join(" | ")}`);
    }
    if (s === SITES[0]) {   // 옛 배치를 덧씌우면 걸리는지 — 컴퓨터는 가운데 호(두 칸 · 오른쪽 정렬), 휴대폰은 첫 호(다음 호 위 선 겹침)
      const caught = [];
      for (const [w, path] of [[1280, `brief-${items[mid]}.html`], [390, `brief-${items[0]}.html`]]) {
        const { ctx, page } = await open("ko", w, HOST + s.base + path);
        await page.addStyleTag({ content: OLD_NAV_CSS });
        const r = await page.evaluate(look);
        await ctx.close();
        caught.push([r.navOk === false, `${w}px ${path} ${r.navNote}`]);
      }
      t(caught.every(([c]) => c), `${s.name} ⑦ 옛 배치를 덧씌우면 걸린다 — ${caught.map(([c, m]) => `${c ? "걸림" : "못 잡음"} ${m}`).join(" | ")}`);
    }

    /* ⑧ 눌러서 옮겨 가기 — 목록 → 가운데 호 → 다음 호 → 지난 호 전체 보기 → 첫 호 → (지난 호의) 최신 호 보기 */
    const d = items[mid];
    const { ctx, page } = await open("ko", 1280, HOST + s.base + "brief-archive.html");
    const steps = [];
    const go = async (sel, want) => {
      await Promise.all([page.waitForURL((u) => u.pathname.endsWith("/" + want), { timeout: 8000 }).catch(() => {}), page.click(sel)]);
      await page.waitForLoadState("load");
      const p = new URL(page.url()).pathname.split("/").pop();
      steps.push(`${p}${p === want ? "" : `(기대 ${want})`}`);
      return p === want;
    };
    let ok = await go(`.ba-list a[href="brief-${d}.html"]`, `brief-${d}.html`);
    const no = await page.evaluate(() => (document.querySelector(".mb-date") || {}).dataset?.no);
    ok = ok && no === `제${NO[d]}호`;
    if (items[mid + 1]) ok = (await go(".mb-nv--next", `brief-${items[mid + 1]}.html`)) && ok;
    ok = (await go(".mb-all a", "brief-archive.html")) && ok;
    ok = (await go(`.ba-list a[href="brief-${items[0]}.html"]`, `brief-${items[0]}.html`)) && ok;
    ok = (await go(".mb-old a", "brief.html")) && ok;
    await ctx.close();
    t(ok, `${s.name} ⑧ 눌러서 옮겨 간다 — 목록 → ${steps.join(" → ")} (가운데 호 ${no})`);
  }
}

await browser.close();
server.close();
console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
