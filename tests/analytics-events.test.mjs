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

console.log("\n" + "=".repeat(52));
console.log(`PASS ${pass}  FAIL ${fail}`);
process.exit(fail ? 1 : 0);
