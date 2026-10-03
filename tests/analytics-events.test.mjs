/* ============================================================
   analytics.js — 행동 기록

   왜 있는가. 마케팅 보고가 "방문자 몇 명" 에서 멈춘 이유는 사이트가
   행동을 거의 기록하지 않아서다. sign_up 에 출처 페이지가 없어서
   "어느 페이지에서 가입하는지" 를 물어도 답이 없었고, 유입처가 없어서
   "네이버에서 온 사람이 가입까지 갔나" 도 셀 수 없었다.

   맥락을 부르는 곳마다 적으면 하나는 반드시 빠진다. 그래서 KOSA.track
   안에서 붙인다. 그게 실제로 붙는지, 그리고 저절로 기록되는 것들이
   제대로 도는지를 여기서 본다.

   보는 것
     · 모든 이벤트에 from_page·entry_page·entry_source 가 붙는가
     · 부르는 쪽이 준 값이 덮이지 않는가
     · 유입처를 referrer 에서 알아보는가 (네이버·구글·X·인스타…)
     · utm_source 가 있으면 그쪽이 이기는가
     · 방문 중에 유입처가 첫 페이지 것으로 유지되는가
     · 종목 링크를 누르면 stock_click 이 뜨는가
     · 스크롤 단계가 한 번씩만 뜨는가
     · 페이지를 떠날 때 머문 시간과 읽은 깊이가 남는가, 두 번 안 뜨는가
     · 집계를 끈 경우엔 아무것도 안 뜨는가

   실행
     node tests/analytics-events.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(HERE, "..", "analytics.js"), "utf8");

let pass = 0, fail = 0;
const ok = (n, c, e = "") => { c ? (pass++, console.log(`  ✅ ${n}`))
                                 : (fail++, console.log(`  ❌ ${n}  ${e}`)); };
const eq = (n, g, w) => ok(n, JSON.stringify(g) === JSON.stringify(w),
                           `받음=${JSON.stringify(g)} 기대=${JSON.stringify(w)}`);

/** 페이지를 열고, gtag 로 나간 이벤트를 전부 모은다. */
function open(url, { referrer = "", session = {}, store = {}, html } = {}) {
  const dom = new JSDOM(html || `<!doctype html><html><head></head><body>
      <a id="lnk" href="stock.html?ticker=005930">삼성전자</a>
      <a id="other" href="Reports.html">목록</a>
      <div style="height:3000px"></div></body></html>`,
    Object.assign({ url, runScripts: "outside-only", pretendToBeVisual: true },
                  referrer ? { referrer } : {}));
  const w = dom.window;
  for (const [key, box] of [["localStorage", store], ["sessionStorage", session]]) {
    Object.defineProperty(w, key, { configurable: true, value: {
      getItem: (k) => (k in box ? box[k] : null),
      setItem: (k, v) => { box[k] = String(v); },
      removeItem: (k) => { delete box[k]; } } });
  }
  const events = [];
  w.dataLayer = [];
  w.gtag = function (kind, name, params) {
    if (kind === "event") events.push({ name, params });
  };
  w.eval(SRC);
  /* analytics.js 를 읽는 도중에 뜬 이벤트(리포트를 여는 순간의
     report_view 같은 것)는 gtag.js 가 아직 안 붙었으므로 dataLayer 에
     쌓인다. 진짜 브라우저에서는 gtag.js 가 나중에 와서 그걸 꺼내 보낸다.
     여기서도 꺼내 와야 실제와 같아진다. */
  for (const a of (w.dataLayer || [])) {
    if (a && a[0] === "event") events.push({ name: a[1], params: a[2] });
  }
  // analytics.js 가 gtag 를 자기 것으로 덮으므로 다시 우리 것으로
  w.gtag = function (kind, name, params) {
    if (kind === "event") events.push({ name, params });
  };
  return { w, events, session, doc: w.document };
}

console.log("① 모든 이벤트에 맥락이 붙는다");
{
  const { w, events } = open("https://kosai.kr/stock.html?ticker=005930",
    { referrer: "https://search.naver.com/search?q=%EC%82%BC%EC%84%B1" });
  w.KOSA.track("sign_up", { method: "google" });
  const p = events.find((e) => e.name === "sign_up").params;
  eq("어느 페이지에서", p.from_page, "/stock.html");
  eq("어디서 들어왔나", p.entry_source, "naver");
  eq("처음 연 페이지", p.entry_page, "/stock.html");
  eq("부르는 쪽 값이 살아 있다", p.method, "google");
}
{
  const { w, events } = open("https://kosai.kr/Reports.html");
  w.KOSA.track("x", { from_page: "내가 정한 값" });
  eq("부르는 쪽이 준 값이 이긴다",
     events.find((e) => e.name === "x").params.from_page, "내가 정한 값");
}

console.log("\n② 유입처를 알아본다");
const cases = [
  ["", "direct"],
  ["https://www.google.com/search?q=kosai", "google"],
  ["https://m.search.naver.com/search.naver", "naver"],
  ["https://t.co/abc", "x"],
  ["https://www.instagram.com/", "instagram"],
  ["https://search.daum.net/", "daum"],
  ["https://kosai.kr/Reports.html", "internal"],
  ["https://blog.example.com/post", "blog.example.com"],
];
for (const [ref, want] of cases) {
  const { w, events } = open("https://kosai.kr/", { referrer: ref });
  w.KOSA.track("t");
  eq(`${ref || "(직접)"} → ${want}`,
     events.find((e) => e.name === "t").params.entry_source, want);
}
{
  const { w, events } = open("https://kosai.kr/?utm_source=newsletter",
    { referrer: "https://www.google.com/" });
  w.KOSA.track("t");
  eq("utm_source 가 referrer 를 이긴다",
     events.find((e) => e.name === "t").params.entry_source, "newsletter");
}

console.log("\n③ 방문 내내 첫 유입처를 유지한다");
{
  const box = {};
  open("https://kosai.kr/", { referrer: "https://m.search.naver.com/", session: box });
  // 두 번째 페이지 — referrer 는 우리 사이트지만 유입처는 네이버여야 한다
  const { w, events } = open("https://kosai.kr/stock.html",
    { referrer: "https://kosai.kr/", session: box });
  w.KOSA.track("sign_up", {});
  const p = events.find((e) => e.name === "sign_up").params;
  eq("유입처가 네이버로 남는다", p.entry_source, "naver");
  eq("처음 연 페이지도 남는다", p.entry_page, "/");
  eq("지금 페이지는 새것", p.from_page, "/stock.html");
}

console.log("\n④ 종목 링크 누름");
{
  const { w, events, doc } = open("https://kosai.kr/Reports.html");
  doc.getElementById("lnk").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  const e = events.find((x) => x.name === "stock_click");
  ok("stock_click 이 뜬다", !!e, JSON.stringify(events));
  eq("종목 코드가 실린다", e && e.params.ticker, "005930");
  eq("어느 페이지에서 눌렀는지", e && e.params.from_page, "/Reports.html");
  doc.getElementById("other").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  eq("종목이 아닌 링크는 안 센다",
     events.filter((x) => x.name === "stock_click").length, 1);
}

console.log("\n⑤ 얼마나 내려 읽었나");
{
  const { w, events } = open("https://kosai.kr/stock.html");
  Object.defineProperty(w.document.documentElement, "scrollHeight",
    { configurable: true, value: 3000 });
  Object.defineProperty(w, "innerHeight", { configurable: true, value: 1000 });
  const scrollTo = (y) => {
    Object.defineProperty(w, "pageYOffset", { configurable: true, value: y });
    w.dispatchEvent(new w.Event("scroll"));
  };
  scrollTo(500);   // 25%
  scrollTo(1000);  // 50%
  scrollTo(1000);  // 또 50% — 다시 세면 안 된다
  scrollTo(2000);  // 100%
  const steps = events.filter((e) => e.name === "scroll_depth").map((e) => e.params.percent);
  eq("단계가 한 번씩만", steps, [25, 50, 75, 100]);
}

console.log("\n⑥ 떠날 때");
{
  const { w, events } = open("https://kosai.kr/brief.html");
  w.dispatchEvent(new w.Event("pagehide"));
  const e = events.find((x) => x.name === "page_leave");
  ok("page_leave 가 뜬다", !!e);
  ok("머문 시간이 숫자", typeof (e && e.params.seconds) === "number");
  ok("읽은 깊이가 실린다", typeof (e && e.params.max_scroll) === "number");
  eq("어느 페이지에서 떠났는지", e && e.params.from_page, "/brief.html");
  w.dispatchEvent(new w.Event("pagehide"));
  eq("두 번 안 뜬다", events.filter((x) => x.name === "page_leave").length, 1);
}

console.log("\n⑦ 집계를 끈 경우엔 아무것도 안 뜬다");
{
  const { w, events, doc } = open("https://kosai.kr/Reports.html",
    { store: { kosai_no_analytics: "1" } });
  w.KOSA.track("sign_up", { method: "email" });
  doc.getElementById("lnk").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  w.dispatchEvent(new w.Event("pagehide"));
  eq("이벤트가 하나도 없다", events.length, 0);
}
{
  const { w, events } = open("https://kosai.kr/staging/Reports.html");
  w.KOSA.track("sign_up", {});
  eq("스테이징도 없다", events.length, 0);
}

console.log("\n⑧ 어느 리포트를 열었나 (report_view)");
{
  const { events } = open("https://kosai.kr/stock.html?ticker=005930");
  const rv = events.filter((e) => e.name === "report_view");
  eq("리포트를 열면 한 번 뜬다", rv.length, 1);
  eq("어느 종목인지 실린다", rv[0].params.ticker, "005930");
}
{
  const { events } = open("https://kosai.kr/stock.html?lang=en&ticker=000660");
  eq("앞에 다른 값이 있어도 찾는다",
     events.find((e) => e.name === "report_view").params.ticker, "000660");
}
{
  const { events } = open("https://kosai.kr/Reports.html?ticker=005930");
  eq("리포트 페이지가 아니면 안 뜬다",
     events.filter((e) => e.name === "report_view").length, 0);
}
{
  const { events } = open("https://kosai.kr/stock.html");
  eq("종목 번호가 없으면 안 뜬다",
     events.filter((e) => e.name === "report_view").length, 0);
}
{
  const { events } = open("https://kosai.kr/stock.html?ticker=12345");
  eq("여섯 자리가 아니면 안 뜬다",
     events.filter((e) => e.name === "report_view").length, 0);
}
{
  const { events } = open("https://kosai.kr/staging/stock.html?ticker=005930");
  eq("스테이징에서는 안 뜬다", events.length, 0);
}

console.log("\n⑨ 여태 리포트를 몇 개 봤나 (reports_seen)");
{
  const store = {};
  const a = open("https://kosai.kr/stock.html?ticker=005930", { store });
  eq("처음 연 리포트에는 0 이 실린다",
     a.events.find((e) => e.name === "report_view").params.reports_seen, "0");
  eq("열고 나면 하나로 센다", store.kosai_reports_seen, "1");

  const b = open("https://kosai.kr/stock.html?ticker=000660", { store });
  eq("두 번째에는 1 이 실린다",
     b.events.find((e) => e.name === "report_view").params.reports_seen, "1");
  eq("둘로 센다", store.kosai_reports_seen, "2");
}
{
  // 가입하는 순간 '여태 몇 개 봤는지' 가 같이 실려야 한다.
  const { w, events } = open("https://kosai.kr/Signup.html",
                             { store: { kosai_reports_seen: "7" } });
  w.KOSA.track("sign_up", { method: "google" });
  eq("가입에도 실린다",
     events.find((e) => e.name === "sign_up").params.reports_seen, "6~10");
}
{
  const cases = [["0", "0"], ["1", "1"], ["2", "2"], ["3", "3~5"], ["5", "3~5"],
                 ["6", "6~10"], ["10", "6~10"], ["11", "11+"], ["999", "11+"]];
  let good = true;
  for (const [have, want] of cases) {
    const { w, events } = open("https://kosai.kr/Reports.html",
                               { store: { kosai_reports_seen: have } });
    w.KOSA.track("ping", {});
    good = good && events.find((e) => e.name === "ping").params.reports_seen === want;
  }
  ok("묶음이 제대로 나뉜다 (0·1·2·3~5·6~10·11+)", good);
}
{
  const { w, events } = open("https://kosai.kr/Reports.html",
                             { store: { kosai_reports_seen: "이상한값" } });
  w.KOSA.track("ping", {});
  eq("망가진 값은 0 으로 본다",
     events.find((e) => e.name === "ping").params.reports_seen, "0");
}

console.log("\n⑩ 종목마다 미리 만든 페이지(/stock/005930.html · 2026-10-03)");
/* 통계에는 옛 주소 모양(/stock.html?ticker=)으로 싣는다 — 주간 보고서 · 마케팅 도구가 '/stock.html' 한 덩어리로
   리포트를 연 사람을 센다. 주소가 바뀌었다고 그 숫자가 끊기면 안 된다. */
const cfgOf = (w) => { const c = (w.dataLayer || []).find((a) => a && a[0] === "config"); return c ? c[2] : null; };
{
  const store = {};
  const { w, events } = open("https://kosai.kr/stock/005930.html", { store });
  const rv = events.filter((e) => e.name === "report_view");
  eq("리포트를 열면 한 번 뜬다", rv.length, 1);
  eq("어느 종목인지 실린다", rv[0] && rv[0].params.ticker, "005930");
  eq("페이지 이름은 옛 덩어리 그대로", rv[0] && rv[0].params.from_page, "/stock.html");
  eq("통계에 싣는 주소는 옛 주소 모양", cfgOf(w) && cfgOf(w).page_location, "https://kosai.kr/stock.html?ticker=005930");
  eq("광고 끄기 설정은 그대로", cfgOf(w) && cfgOf(w).allow_google_signals, false);
  eq("본 리포트 수도 센다", store.kosai_reports_seen, "1");
}
{
  const { w } = open("https://kosai.kr/stock/0220W0.html?utm_source=naver");
  eq("영문이 섞인 종목코드 · 유입 꼬리표도 실린다", cfgOf(w) && cfgOf(w).page_location,
     "https://kosai.kr/stock.html?ticker=0220W0&utm_source=naver");
}
{
  const { w } = open("https://kosai.kr/Reports.html");
  eq("다른 페이지는 주소를 바꾸지 않는다", cfgOf(w) && "page_location" in cfgOf(w), false);
}
{
  const { w, events, doc } = open("https://kosai.kr/Reports.html", { html: `<!doctype html><html><head></head><body>
      <a id="lnk" href="/stock/000660.html">SK하이닉스</a></body></html>` });
  doc.getElementById("lnk").dispatchEvent(new w.MouseEvent("click", { bubbles: true }));
  eq("새 주소 링크를 눌러도 stock_click", (events.find((x) => x.name === "stock_click") || {}).params?.ticker, "000660");
}
/* 옛 주소(stock.html?ticker= · r/)를 거쳐 온 방문 — 넘기는 페이지가 출처 자리를 차지한다. 넘기기 전에 남긴 원래 출처(kos-fwd-ref)를
   써야 검색 유입이 '내부 · 직접'으로 잡히지 않는다(독립 검토 2026-10-03). */
for (const via of ["https://kosai.kr/stock.html?ticker=005930", "https://kosai.kr/r/005930.html"]) {
  const NAVER = "https://m.search.naver.com/search.naver?query=%EC%82%BC%EC%84%B1";
  const session = { "kos-fwd-ref": NAVER };
  const { w, events } = open("https://kosai.kr/stock/005930.html", { referrer: via, session });
  w.KOSA.track("t");
  const short = via.replace("https://kosai.kr", "");
  eq(`${short} 를 거쳐 와도 유입처는 네이버`, events.find((e) => e.name === "t").params.entry_source, "naver");
  eq(`${short} — GA4 의 출처도 네이버`, cfgOf(w) && cfgOf(w).page_referrer, NAVER);
  eq(`${short} — 남긴 출처는 한 번 쓰고 지운다`, "kos-fwd-ref" in session, false);
}
{
  const session = { "kos-fwd-ref": "" };   // 주소 직접 입력 · 즐겨찾기로 옛 주소에 온 사람
  const { w, events } = open("https://kosai.kr/stock/005930.html", { referrer: "https://kosai.kr/stock.html?ticker=005930", session });
  w.KOSA.track("t");
  eq("원래 출처가 없던 방문은 직접", events.find((e) => e.name === "t").params.entry_source, "direct");
  eq("GA4 의 출처도 비운다", cfgOf(w) && cfgOf(w).page_referrer, "");
}
{
  // 사이트 안의 다른 페이지에서 왔으면 남은 값이 있어도 쓰지 않는다(옛 주소를 거친 것이 아니다)
  const session = { "kos-fwd-ref": "https://www.google.com/" };
  const { w, events } = open("https://kosai.kr/stock/005930.html", { referrer: "https://kosai.kr/Reports.html", session });
  w.KOSA.track("t");
  eq("옛 주소를 거치지 않은 방문은 그대로", events.find((e) => e.name === "t").params.entry_source, "internal");
  eq("GA4 출처도 그대로(덮지 않는다)", cfgOf(w) && "page_referrer" in cfgOf(w), false);
}
{
  // 옛 주소 껍데기는 새 주소로 넘기는 중이다(KOS_LEAVING) — 거기서 세면 같은 방문이 두 번 잡힌다
  const dom = new JSDOM(`<!doctype html><html><head></head><body></body></html>`,
    { url: "https://kosai.kr/stock.html?ticker=005930", runScripts: "outside-only" });
  const w = dom.window;
  Object.defineProperty(w, "localStorage", { configurable: true, value: { getItem: () => null, setItem() {}, removeItem() {} } });
  Object.defineProperty(w, "sessionStorage", { configurable: true, value: { getItem: () => null, setItem() {}, removeItem() {} } });
  w.KOS_LEAVING = 1;
  w.dataLayer = [];
  w.eval(SRC);
  eq("넘기는 중에는 아무것도 싣지 않는다", (w.dataLayer || []).length, 0);
  ok("KOSA.track 은 있다(부르는 쪽이 멈추지 않게)", typeof w.KOSA.track === "function");
}

console.log("\n" + "=".repeat(52));
console.log(`PASS ${pass}  FAIL ${fail}`);
process.exit(fail ? 1 : 0);
