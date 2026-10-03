/* ============================================================
   실사이트 종목 페이지를 미리 그린다 — scripts/build_stock_static.py 가 부른다.

   리포트 상세 화면의 스크립트(build_stock_staging.PAGE_JS 의 실사이트 판 — 브라우저에서는 stock/assets/stock.js 의 끝 덩어리)를
   노드의 vm 에서 가짜 문서로 돌려, 브라우저가 그릴 글(본문 자리의 innerHTML)과 머리 값(제목 · 설명 · canonical · 공유 ·
   구조화 데이터)을 그대로 받는다. 같은 코드가 같은 자료로 그리므로 미리 그린 글과 브라우저가 그리는 글이 글자 하나까지 같다 —
   문단 자르기(170자 예산) · 돈 표기(조 · 억) · 차트 좌표가 한 벌이다. 파이썬으로 다시 쓰지 않는 이유가 이것이다.

   입력(표준 입력 · JSON)   {"root": 저장소, "js": 페이지 스크립트 파일, "tickers": ["005930", …]}
   출력(표준 출력)          종목마다 JSON 한 줄 {tk, h, hash, tier, title, desc, canonical, ogTitle, ogDesc, ogUrl, ld}
   실패                     종목 하나가 그리다 멈추면(깨진 리포트 파일 등) 그 종목만 {tk, error} 로 알리고 다음 종목을 그린다 —
                            한 종목 때문에 뒤의 종목이 모두 옛 페이지로 남지 않게(독립 검토 2026-10-03). 파이썬 쪽이 그 종목의
                            옛 페이지를 그대로 두고 끝에 실패로 알린다.

   자료(data/stocks.js · valuation.js · reports-index.js)는 한 번 읽고, 리포트(data/reports_v2 · data/reports)는 스크립트가
   fetch 로 부르는 주소를 디스크에서 읽어 준다. 브라우저에서 r.json() 이 실패하면 null 이 되는 것과 같게, 깨진 JSON 은 거절한다.
   ============================================================ */
import vm from "node:vm";
import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const spec = JSON.parse(readFileSync(0, "utf8"));
const ROOT = spec.root;

const ctx = vm.createContext({ console, URLSearchParams });
ctx.window = ctx;
for (const f of ["data/stocks.js", "data/valuation.js", "data/reports-index.js"]) {
  vm.runInContext(readFileSync(join(ROOT, f), "utf8"), ctx, { filename: f });
}
const cJSON = vm.runInContext("JSON", ctx), cPromise = vm.runInContext("Promise", ctx);
const page = new vm.Script(readFileSync(spec.js, "utf8"), { filename: "stock-page.js" });

function el() {
  const a = {};
  return { attrs: a, getAttribute: (k) => (k in a ? a[k] : null), setAttribute: (k, v) => { a[k] = String(v); }, removeAttribute: (k) => { delete a[k]; } };
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
for (const tk of spec.tickers) {
  pageErr = null;
  const main = el();
  main.attrs["data-tk"] = tk;
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
    location: { search: "", hash: "", pathname: `/stock/${tk}.html`, href: `https://kosai.kr/stock/${tk}.html` },
    localStorage: { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: (k) => { delete store[k]; } },
    fetch: fetchFor,
    addEventListener: () => {}, removeEventListener: () => {},
    history: { replaceState: () => {} },
    KOSi18n: undefined, KOSA: undefined, KOSWatch: undefined, KOSPaywall: undefined, kosFitCharts: undefined, kosTocInit: undefined,
  });
  try { page.runInContext(ctx); } catch (e) { pageErr = e; }
  for (let i = 0; i < 200 && !("data-tier" in main.attrs) && !pageErr; i++) await tick();   // 자료를 받은 뒤의 그리기(LOADED)가 data-tier 를 단다
  if (pageErr || !("data-tier" in main.attrs) || !html) {
    emit({ tk, error: String((pageErr && (pageErr.stack || pageErr.message)) || pageErr || "그리기가 끝나지 않았다").split("\n").slice(0, 3).join(" | ") });
    continue;
  }
  const ld = kids.find((e) => e.id === "kos-jsonld");
  const meta = (sel, k) => (metas[sel] ? metas[sel].attrs[k] : null);
  emit({
    tk, h: html, hash: ctx.kosHash(html), tier: main.attrs["data-tier"], title: doc.title,
    desc: meta("meta[name=description]", "content"), canonical: meta("link[rel=canonical]", "href"),
    ogTitle: meta('meta[property="og:title"]', "content"), ogDesc: meta('meta[property="og:description"]', "content"),
    ogUrl: meta('meta[property="og:url"]', "content"), ld: ld ? ld.textContent : null,
  });
}
