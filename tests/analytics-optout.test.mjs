/* ============================================================
   analytics.js — 우리 발자국은 아예 보내지 않는다

   왜 있는가. 8월 24일 주에 기록된 조회의 28%가 우리 것이었다.
   로그인 240·동의 68·가입 33·관리자 49 가 다음 주에 한꺼번에 23 으로
   떨어졌는데, 첫 주간 보고서는 그걸 "이용자가 빠졌다"로 읽고 "링크가
   끊겼을 수 있다"는 틀린 결론을 냈다. 사장이 그 주에 시험을 멈춘
   것뿐이었다.

   받아 놓고 거르는 것으로는 부족하다. 실사이트에서 종목 리포트를 직접
   열어 보면 페이지 이름만으로는 손님과 구분할 수 없다. 그래서 보내는
   쪽에서 막고, 그게 진짜로 막히는지 여기서 본다.

   보는 것
     · /staging/ 아래에서는 아무것도 싣지 않는가
     · /Admin.html 에서도 싣지 않는가
     · ?noga=1 을 열면 그 뒤로 영영 안 싣는가, ?noga=0 으로 되돌아오는가
     · noga 를 주소에서 지우는가 (남에게 퍼지면 그 사람도 빠진다)
     · 막은 경우에도 KOSA.track 이 있는가 (없으면 부르는 쪽이 멈춘다)
     · 평소(실사이트 일반 페이지)에는 멀쩡히 싣는가
     · 스테이징 판정이 '파일'이 아니라 '주소' 기준인가
       (파일에 박아 두면 staging 을 실사이트로 올릴 때 집계가 죽는다)

   실행
     npm install --no-save jsdom
     node tests/analytics-optout.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { JSDOM } from "jsdom";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const SRC = readFileSync(join(ROOT, "analytics.js"), "utf8");

let pass = 0, fail = 0;
const ok = (name, cond, extra = "") => {
  if (cond) { pass++; console.log(`  ✅ ${name}`); }
  else { fail++; console.log(`  ❌ ${name}  ${extra}`); }
};

/** 한 페이지를 열어 analytics.js 를 돌린 결과를 본다. */
function run(url, { store = {} } = {}) {
  const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>",
    { url, runScripts: "outside-only", pretendToBeVisual: true });
  const w = dom.window;
  // localStorage 를 우리가 들여다볼 수 있는 것으로 바꿔 끼운다
  Object.defineProperty(w, "localStorage", {
    configurable: true,
    value: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => { store[k] = String(v); },
      removeItem: (k) => { delete store[k]; },
    },
  });
  w.eval(SRC);
  const srcs = [...w.document.querySelectorAll("script")].map((s) => s.src);
  return {
    store,
    ga: srcs.some((s) => s.includes("googletagmanager")),
    naver: srcs.some((s) => s.includes("wcslog")),
    on: w.KOSA && w.KOSA.on(),
    hasTrack: !!(w.KOSA && typeof w.KOSA.track === "function"),
    href: w.location.href,
    body: w.document.body.textContent,
    win: w,
  };
}

console.log("① 평소 — 실사이트 일반 페이지");
let r = run("https://kosai.kr/stock.html?ticker=005930");
ok("GA4 를 싣는다", r.ga);
ok("네이버도 싣는다", r.naver);
ok("KOSA.on() 이 참", r.on === true);
ok("종목 주소는 건드리지 않는다", r.href.includes("ticker=005930"), r.href);

console.log("\n② 스테이징 — 아무것도 싣지 않는다");
r = run("https://kosai.kr/staging/Reports.html");
ok("GA4 를 싣지 않는다", !r.ga);
ok("네이버도 싣지 않는다", !r.naver);
ok("KOSA.on() 이 거짓", r.on === false);
ok("그래도 KOSA.track 은 있다", r.hasTrack);
ok("track 을 불러도 터지지 않는다",
  (() => { try { r.win.KOSA.track("sign_up", { a: 1 }); return true; } catch (e) { return false; } })());

console.log("\n③ 관리자 화면 — 싣지 않는다");
r = run("https://kosai.kr/Admin.html");
ok("GA4 를 싣지 않는다", !r.ga);
ok("KOSA.track 은 있다", r.hasTrack);

console.log("\n④ 끄기 스위치");
const box = {};
r = run("https://kosai.kr/?noga=1", { store: box });
ok("그 방문부터 바로 싣지 않는다", !r.ga);
ok("브라우저에 기억해 둔다", box.kosai_no_analytics === "1", JSON.stringify(box));
ok("무슨 일이 일어났는지 화면에 알린다", r.body.includes("통계에 잡히지 않습니다"), r.body);
ok("주소에서 noga 를 지운다", !r.href.includes("noga"), r.href);

r = run("https://kosai.kr/stock.html", { store: box });
ok("다음 페이지에서도 계속 빠져 있다", !r.ga);
ok("네이버도 빠져 있다", !r.naver);

r = run("https://kosai.kr/?noga=0", { store: box });
ok("?noga=0 이면 기억을 지운다", !("kosai_no_analytics" in box), JSON.stringify(box));
ok("되돌렸다고 알린다", r.body.includes("다시 방문 통계에"), r.body);

r = run("https://kosai.kr/stock.html", { store: box });
ok("되돌린 뒤에는 다시 싣는다", r.ga);

console.log("\n⑤ 스테이징 판정은 주소 기준이어야 한다");
// 같은 파일이 실사이트 뿌리에 올라가면(유료화 이관) 집계가 켜져야 한다.
const staged = readFileSync(join(ROOT, "staging", "analytics.js"), "utf8");
ok("staging/analytics.js 가 실사이트 것과 같다", staged === SRC);
ok("파일 안에 '끔' 이 박혀 있지 않다",
  !/GA4_ID\s*=\s*""/.test(SRC) && SRC.includes('indexOf("/staging/")'));
// 실제로: staging 파일 내용을 뿌리 주소에서 돌리면 켜져야 한다
{
  const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>",
    { url: "https://kosai.kr/Reports.html", runScripts: "outside-only" });
  dom.window.eval(staged);
  const on = [...dom.window.document.querySelectorAll("script")]
    .some((s) => s.src.includes("googletagmanager"));
  ok("staging 파일을 뿌리로 올리면 집계가 살아난다", on);
}

console.log("\n⑥ localStorage 가 막혀 있어도 화면이 멈추지 않는다");
{
  const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>",
    { url: "https://kosai.kr/", runScripts: "outside-only" });
  Object.defineProperty(dom.window, "localStorage", {
    configurable: true,
    get() { throw new Error("차단됨"); },
  });
  let threw = false;
  try { dom.window.eval(SRC); } catch (e) { threw = true; }
  ok("예외가 새어 나오지 않는다", !threw);
  ok("그래도 GA4 는 실린다",
    [...dom.window.document.querySelectorAll("script")]
      .some((s) => s.src.includes("googletagmanager")));
}

console.log("\n" + "=".repeat(52));
console.log(`PASS ${pass}  FAIL ${fail}`);
process.exit(fail ? 1 : 0);
