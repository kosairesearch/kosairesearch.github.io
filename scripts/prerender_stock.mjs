/* ============================================================
   실사이트 종목 페이지를 미리 그린다 — scripts/build_stock_static.py 가 부른다(한국어 · 영어 두 번).

   리포트 상세 화면의 스크립트(build_stock_staging.PAGE_JS 의 실사이트 판 — 브라우저에서는 stock/assets/stock.js 의 끝 덩어리)를
   노드의 vm 에서 가짜 문서로 돌려, 브라우저가 그릴 글(본문 자리의 innerHTML)과 머리 값(제목 · 설명 · canonical · 공유 ·
   구조화 데이터)을 그대로 받는다. 같은 코드가 같은 자료로 그리므로 미리 그린 글과 브라우저가 그리는 글이 글자 하나까지 같다 —
   문단 자르기(170자 예산) · 돈 표기(조 · 억) · 차트 좌표가 한 벌이다. 파이썬으로 다시 쓰지 않는 이유가 이것이다.

   번역 엔진(i18n.js)도 브라우저처럼 먼저 띄운다(페이지 머리에 있는 그대로). 한국어는 엔진이 한국어로 서 있을 뿐이고,
   영어(/en/stock/{종목코드}.html · 2026-10-03)는 엔진이 영어로 서서 스크립트가 영어 화면을 그리고, 그 글에 남은 한국어
   라벨을 엔진의 walk 가 사전으로 바꾼다 — 브라우저의 엔진이 하는 일을 작은 HTML 나무(scripts/mini_dom.mjs) 위에서 그대로.
   지문(hash)은 번역 전의 글로 잰다 — 브라우저의 페이지 스크립트가 영어 화면에서 그린 글과 견주기 때문이다.

   입력(표준 입력 · JSON)   {"root": 저장소, "js": 페이지 스크립트 파일, "tickers": […], "lang": "ko"|"en",
                             "engine": i18n.js, "dict": 영어 사전(stock/assets/i18n-dict.js 와 같은 것), "shell": [머리 · 꼬리 HTML]}
   출력(표준 출력)          영어면 맨 앞에 {"shell": [번역한 머리 · 꼬리]} 한 줄. 그다음 종목마다 JSON 한 줄
                            {tk, h, hash, tier, title, desc, canonical, ogTitle, ogDesc, ogUrl, ld, han}
                            (h 는 영어면 번역까지 마친 글, han 은 그 글에 남은 한글 글자 수 · 표본)
   실패                     종목 하나가 그리다 멈추면(깨진 리포트 파일 등) 그 종목만 {tk, error} 로 알리고 다음 종목을 그린다 —
                            한 종목 때문에 뒤의 종목이 모두 옛 페이지로 남지 않게(독립 검토 2026-10-03). 파이썬 쪽이 그 종목의
                            옛 페이지를 그대로 두고 끝에 실패로 알린다.

   자료(data/stocks.js · valuation.js · reports-index.js)는 한 번 읽고, 리포트(data/reports_v2 · data/reports)는 스크립트가
   fetch 로 부르는 주소를 디스크에서 읽어 준다. 브라우저에서 r.json() 이 실패하면 null 이 되는 것과 같게, 깨진 JSON 은 거절한다.
   ============================================================ */
import vm from "node:vm";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { parse, serialize } from "./mini_dom.mjs";

const spec = JSON.parse(readFileSync(0, "utf8"));
const ROOT = spec.root;
const LANG = spec.lang === "en" ? "en" : "ko";

const ctx = vm.createContext({ console, URLSearchParams });
ctx.window = ctx;
for (const f of ["data/stocks.js", "data/valuation.js", "data/reports-index.js"]) {
  vm.runInContext(readFileSync(join(ROOT, f), "utf8"), ctx, { filename: f });
}
const cJSON = vm.runInContext("JSON", ctx), cPromise = vm.runInContext("Promise", ctx);
const page = new vm.Script(readFileSync(spec.js, "utf8"), { filename: "stock-page.js" });

function el() {
  const a = {};
  return { attrs: a, getAttribute: (k) => (k in a ? a[k] : null), setAttribute: (k, v) => { a[k] = String(v); }, removeAttribute: (k) => { delete a[k]; },
           classList: { add() {}, remove() {}, contains: () => false, toggle() {} } };
}

/* ── 번역 엔진 — 페이지 머리의 i18n.js 와 같은 파일. 브라우저 순서 그대로: 엔진(머리) → 자료 → 사전 등록(i18n-dict.js, 영어일 때만)
   → 문서가 다 읽힌 뒤 엔진 시작(종목 영문명을 자료에서 사전에 더한다). 영어 페이지는 머리에서 KOS_PAGE_LANG='en' 을 단다. ── */
const eStore = {};
let domReady = null;
const eRoot = el();
const eDoc = {
  documentElement: eRoot, head: { appendChild: (e) => e }, body: null, title: "", readyState: "loading",
  addEventListener: (t, f) => { if (t === "DOMContentLoaded") domReady = f; },
  createElement: (tag) => ({ tagName: String(tag).toUpperCase(), textContent: "" }),
  querySelectorAll: () => [], querySelector: () => null,
};
Object.assign(ctx, {
  document: eDoc,
  location: { pathname: LANG === "en" ? "/en/stock/" : "/stock/", search: "", hash: "", href: "https://kosai.kr/" },
  localStorage: { getItem: (k) => (k in eStore ? eStore[k] : null), setItem: (k, v) => { eStore[k] = String(v); }, removeItem: (k) => { delete eStore[k]; } },
  addEventListener: () => {}, removeEventListener: () => {},
});
if (LANG === "en") ctx.KOS_PAGE_LANG = "en";
vm.runInContext(readFileSync(spec.engine, "utf8"), ctx, { filename: "i18n.js" });
const I18 = ctx.KOSi18n;
if (!I18 || I18.lang !== LANG) throw new Error(`번역 엔진이 ${LANG} 로 서지 않았다(${I18 && I18.lang})`);
if (LANG === "en") I18.register(spec.dict || {});
if (domReady) domReady();

/* 엔진의 walk 로 HTML 조각을 번역한다 — 문서 자리에 작은 나무를 잠깐 끼운다(제목은 건드리지 않게 빈 값으로). */
function translate(html) {
  const tree = parse(html);
  const saved = ctx.document;
  ctx.document = { body: tree.body, documentElement: eRoot, get title() { return ""; }, set title(v) {} };
  try { I18.apply(); } finally { ctx.document = saved; }
  return serialize(tree);
}
const HAN = /[가-힣]/g;
function hangulLeft(html) {   // 번역한 글에 남은 한글 — 태그 · 속성 밖의 글만 센다(영문명이 없는 종목명 · 영어판이 없는 리포트 칸)
  const txt = html.replace(/<[^>]*>/g, " ");
  const m = txt.match(HAN);
  if (!m) return null;
  const at = txt.search(/[가-힣]/);
  return { n: m.length, sample: txt.slice(Math.max(0, at - 10), at + 30).replace(/\s+/g, " ").trim() };
}

function fetchFor(u) {
  const m = /^\/data\/(reports_v2|reports)\/([^/?#]+)\.json$/.exec(String(u));
  const no = () => cPromise.resolve({ ok: false, json: () => cPromise.resolve(null) });
  if (!m) return no();
  const f = join(ROOT, "data", m[1], decodeURIComponent(m[2]) + ".json");
  if (!existsSync(f)) return no();
  const txt = readFileSync(f, "utf8");
  return cPromise.resolve({ ok: true, json: () => { try { return cPromise.resolve(cJSON.parse(txt)); } catch (e) { return cPromise.reject(e); } } });
}

const tick = () => new Promise((r) => setImmediate(r));
/* 페이지 스크립트의 약속 사슬에는 catch 가 없다 — 그리다 던진 오류는 '처리되지 않은 거절'로 온다. 노드가 그것으로 멈추지 않게
   붙잡아 지금 종목의 실패로 적는다. 종목마다 자료를 받은 뒤의 그리기가 끝날 때까지 기다리므로 앞 종목의 오류가 섞이지 않는다. */
let pageErr = null;
process.on("unhandledRejection", (e) => { pageErr = e || new Error("거절"); });
const emit = (o) => process.stdout.write(JSON.stringify(o) + "\n");
if (LANG === "en") emit({ shell: (spec.shell || []).map(translate) });
for (const tk of spec.tickers) {
  pageErr = null;
  const main = el();
  main.attrs["data-tk"] = tk;
  if (LANG === "en") main.attrs["data-pre-lang"] = "en";   // 영어 페이지 — 대표 주소를 영어 주소로 단다(setSEO)
  let html = null;
  Object.defineProperty(main, "innerHTML", { get: () => html, set: (v) => { html = String(v); } });
  const metas = {}, kids = [];
  const doc = {
    title: "",
    head: { appendChild: (e) => { kids.push(e); return e; } },
    documentElement: el(),
    getElementById: (id) => (id === "page" ? main : id === "kos-jsonld" ? kids.find((e) => e.id === "kos-jsonld") || null : null),
    querySelector: (sel) => metas[sel] || (metas[sel] = el()),
    querySelectorAll: () => [],
    createElement: (tag) => Object.assign(el(), { tagName: String(tag).toUpperCase(), id: "", type: "", textContent: "" }),
    addEventListener: () => {},
  };
  const store = {};
  Object.assign(ctx, {
    document: doc,
    location: { search: "", hash: "", pathname: `${LANG === "en" ? "/en" : ""}/stock/${tk}.html`, href: `https://kosai.kr${LANG === "en" ? "/en" : ""}/stock/${tk}.html` },
    localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } },
    fetch: fetchFor,
    addEventListener: () => {}, removeEventListener: () => {},
    history: { replaceState: () => {} },
    KOSi18n: I18, KOSA: undefined, KOSWatch: undefined, KOSPaywall: undefined, kosFitCharts: undefined, kosTocInit: undefined,
  });
  try { page.runInContext(ctx); } catch (e) { pageErr = e; }
  for (let i = 0; i < 200 && !("data-tier" in main.attrs) && !pageErr; i++) await tick();   // 자료를 받은 뒤의 그리기(LOADED)가 data-tier 를 단다
  let out = html;
  if (!pageErr && "data-tier" in main.attrs && html && LANG === "en") {
    try { out = translate(html); } catch (e) { pageErr = e; }
  }
  if (pageErr || !("data-tier" in main.attrs) || !html) {
    emit({ tk, error: String((pageErr && (pageErr.stack || pageErr.message)) || pageErr || "그리기가 끝나지 않았다").split("\n").slice(0, 3).join(" | ") });
    continue;
  }
  const ld = kids.find((e) => e.id === "kos-jsonld");
  const meta = (sel, k) => (metas[sel] ? metas[sel].attrs[k] : null);
  emit({
    tk, h: out, hash: ctx.kosHash(html), tier: main.attrs["data-tier"], title: doc.title,
    desc: meta("meta[name=description]", "content"), canonical: meta("link[rel=canonical]", "href"),
    ogTitle: meta('meta[property="og:title"]', "content"), ogDesc: meta('meta[property="og:description"]', "content"),
    ogUrl: meta('meta[property="og:url"]', "content"), ld: ld ? ld.textContent : null,
    han: LANG === "en" ? hangulLeft(out) : null,
  });
}
