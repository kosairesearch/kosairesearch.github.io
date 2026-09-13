/* ============================================================
   KOSAI Analytics — GA4 + Naver Analytics (config-driven)
   ------------------------------------------------------------
   ▸ 측정 ID를 아래 두 변수에 넣으면 자동 활성화됩니다.
     - GA4_ID   : Google 애널리틱스 4 측정 ID ("G-XXXXXXXXXX")
     - NAVER_ID : 네이버 애널리틱스 ID (숫자/영문 코드)
   ▸ 비워두면 아무 것도 로드하지 않습니다(안전한 no-op).
   ▸ 전역 헬퍼: KOSA.track('event_name', { ...params })

   우리 발자국은 아예 보내지 않습니다 (2026-09-13 추가)
   ------------------------------------------------------------
   8월 24일 주에 기록된 조회의 28%가 우리 것이었습니다. 로그인 240회·
   동의 68회·가입 33회·관리자 49회가 다음 주에 한꺼번에 23회로 떨어졌고,
   첫 주간 보고서는 그걸 "이용자가 빠졌다 · 링크가 끊겼을 수 있다"는
   틀린 결론으로 읽었습니다. 사장이 그 주에 사이트 시험을 멈춘 것뿐이었죠.

   받아 놓고 나중에 걸러내는 것으로는 부족합니다. 실사이트에서 종목
   리포트를 직접 열어 보면 그건 페이지 이름만으로 손님과 구분할 수
   없으니까요. 그래서 보내는 쪽에서 막습니다.

   막는 경우 세 가지
     1. /staging/ 아래 — 브랜치 미리보기. 손님이 오는 곳이 아닙니다.
     2. /Admin.html  — 관리자 화면. 우리만 봅니다.
     3. 끄기 스위치를 켠 브라우저 — 아래 설명 참고.

   내 브라우저를 통계에서 빼는 법
     https://kosai.kr/?noga=1  ← 한 번 열면 그 브라우저는 영영 빠집니다
     https://kosai.kr/?noga=0  ← 다시 넣습니다
   브라우저·기기마다 따로 해야 합니다(저장 위치가 브라우저 안이라서).
   ============================================================ */
(function () {
  var GA4_ID = "G-8ZHG2KXW6Z";    // GA4 측정 ID
  var NAVER_ID = "1aa82ad75b71490";  // 네이버 애널리틱스 ID
  var OPTOUT_KEY = "kosai_no_analytics";

  var path = (location.pathname || "");

  /* 스테이징은 '파일'이 아니라 '주소'로 판단합니다.
     staging/analytics.js 안에 꺼 두면, 나중에 이 폴더를 실사이트로 올릴 때
     (유료화 작업이 거기 있습니다) 실사이트 집계가 통째로 조용히 죽습니다.
     주소로 보면 올라가는 순간 /staging/ 이 사라지므로 저절로 켜집니다. */
  var isStaging = path.indexOf("/staging/") === 0;
  var isAdmin = /\/Admin\.html$/i.test(path);

  /* 끄기 스위치. 주소에 ?noga=1 이 있으면 이 브라우저에 기억해 둡니다. */
  function notice(msg) {
    try {
      var d = document.createElement("div");
      d.textContent = msg;
      d.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);" +
        "background:#111;color:#fff;padding:12px 18px;border-radius:8px;z-index:99999;" +
        "font:14px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;" +
        "box-shadow:0 4px 16px rgba(0,0,0,.3);max-width:90vw;text-align:center";
      var put = function () {
        document.body.appendChild(d);
        setTimeout(function () { d.remove(); }, 6000);
      };
      if (document.body) put(); else addEventListener("DOMContentLoaded", put);
    } catch (e) {}
  }

  try {
    var q = new URLSearchParams(location.search).get("noga");
    if (q === "1") {
      localStorage.setItem(OPTOUT_KEY, "1");
      notice("이 브라우저는 이제 방문 통계에 잡히지 않습니다.");
    } else if (q === "0") {
      localStorage.removeItem(OPTOUT_KEY);
      notice("이 브라우저를 다시 방문 통계에 넣었습니다.");
    }
    if (q !== null && history.replaceState) {
      /* 주소에서 지웁니다. 이게 붙은 링크가 남으로 퍼지면 그 사람도
         영영 통계에서 빠집니다. */
      var u = new URL(location.href);
      u.searchParams.delete("noga");
      history.replaceState(null, "", u.pathname + u.search + u.hash);
    }
  } catch (e) {}

  var optedOut = false;
  try { optedOut = localStorage.getItem(OPTOUT_KEY) === "1"; } catch (e) {}

  var skip = isStaging || isAdmin || optedOut;
  if (skip) {
    /* 아무것도 싣지 않습니다. 다만 KOSA.track 은 있어야 합니다 —
       부르는 쪽이 없는 함수를 부르면 그 자리에서 화면이 멈춥니다. */
    window.KOSA = { on: function () { return false; }, track: function () {} };
    return;
  }

  // ── Google Analytics 4 ──
  if (GA4_ID && GA4_ID.indexOf("G-") === 0) {
    var g = document.createElement("script");
    g.async = true;
    g.src = "https://www.googletagmanager.com/gtag/js?id=" + GA4_ID;
    document.head.appendChild(g);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag("js", new Date());
    /* 광고 목적 수집을 코드에서 끈다.
       anonymize_ip 는 유니버설 애널리틱스 파라미터라 GA4 가 무시한다 — 넣어도
       아무 일도 하지 않으므로 뺐다(GA4 는 IP 를 기록·저장하지 않는 것이 기본이다).
       대신 실제로 의미가 있는 두 가지를 끈다. 둘 다 기본값이 true 라서, 적어 주지
       않으면 켜진 채로 돈다. 개인정보처리방침 9번이 '광고를 목적으로 한 행태정보를
       수집하지 않는다' 고 적고 있으므로, 관리자 콘솔 설정과 무관하게 코드에서
       보장해야 그 문장이 참이 된다. */
    gtag("config", GA4_ID, {
      allow_google_signals: false,
      allow_ad_personalization_signals: false
    });
  }

  // ── Naver Analytics (한국 검색 유입 분석) ──
  if (NAVER_ID) {
    var n = document.createElement("script");
    n.async = true;
    n.src = "//wcs.naver.net/wcslog.js";
    n.onload = function () {
      try {
        if (!window.wcs_add) window.wcs_add = {};
        window.wcs_add.wa = NAVER_ID;
        if (!window._nasa) window._nasa = {};
        if (window.wcs && wcs.inflow) wcs.inflow();
        if (window.wcs_do) wcs_do(window._nasa);
      } catch (e) {}
    };
    document.head.appendChild(n);
  }

  /* ── 행동 기록 ─────────────────────────────────────────────────
     모든 이벤트에 '어느 페이지에서' 와 '어디서 들어온 사람인지' 를
     자동으로 붙인다.

     왜 여기서 붙이나. 부르는 곳이 스무 군데인데 거기마다 적으면 하나는
     반드시 빠진다. 실제로 sign_up 에 출처 페이지가 없어서 "어느 페이지에서
     가입하는지" 를 못 봤다. 여기서 붙이면 앞으로 만들 이벤트도 공짜로
     따라온다.

     from_page     이 이벤트가 일어난 페이지
     entry_page    이번 방문에서 처음 열었던 페이지
     entry_source  이번 방문의 유입처 (naver·google·direct…)
     ──────────────────────────────────────────────────────────── */
  var SS_ENTRY = "kosai_entry";

  function pageKey() {
    /* 종목 리포트는 주소가 stock.html?ticker=005930 인데, 페이지 이름으로는
       전부 /stock.html 한 덩어리다. 그래서 종목은 ticker 로 따로 싣는다. */
    return (location.pathname || "/").replace(/\/index\.html$/i, "/");
  }

  function entry() {
    /* 이번 방문의 시작점. 첫 페이지에서 한 번 정해 두고 방문이 끝날 때까지
       쓴다(sessionStorage 라 탭을 닫으면 사라진다). 이게 있어야 "네이버에서
       온 사람이 가입까지 갔나" 를 셀 수 있다. */
    try {
      var v = sessionStorage.getItem(SS_ENTRY);
      if (v) return JSON.parse(v);
    } catch (e) {}
    var ref = document.referrer || "";
    var src = "direct";
    try {
      if (ref) {
        var h = new URL(ref).hostname.replace(/^www\./, "");
        if (h === location.hostname) src = "internal";
        else if (/naver\./.test(h)) src = "naver";
        else if (/google\./.test(h)) src = "google";
        else if (/daum\.|kakao\./.test(h)) src = "daum";
        else if (/bing\./.test(h)) src = "bing";
        else if (/t\.co$|twitter\.|x\.com$/.test(h)) src = "x";
        else if (/instagram\./.test(h)) src = "instagram";
        else if (/facebook\./.test(h)) src = "facebook";
        else src = h;
      }
      var q = new URLSearchParams(location.search);
      if (q.get("utm_source")) src = q.get("utm_source");
    } catch (e) {}
    var box = { page: pageKey(), source: src };
    try { sessionStorage.setItem(SS_ENTRY, JSON.stringify(box)); } catch (e) {}
    return box;
  }

  function withContext(params) {
    var e = entry();
    var out = { from_page: pageKey(), entry_page: e.page, entry_source: e.source };
    for (var k in (params || {})) {
      if (Object.prototype.hasOwnProperty.call(params, k)) out[k] = params[k];
    }
    return out;
  }

  // ── 공용 이벤트 헬퍼 — 코드 어디서든 KOSA.track() 호출 ──
  window.KOSA = {
    on: function () { return !!(GA4_ID || NAVER_ID); },
    track: function (name, params) {
      try { if (window.gtag) gtag("event", name, withContext(params)); } catch (e) {}
    }
  };

  /* ── 저절로 기록되는 것들 ─────────────────────────────────────── */
  try {
    entry();   // 첫 페이지에서 유입처를 잡아 둔다

    /* ① 종목 링크 누름. 어느 종목이 실제로 눌리는지 본다.
       링크마다 코드를 넣지 않고 문서 전체에서 한 번만 듣는다 — 나중에
       목록을 새로 만들어도 저절로 따라온다. */
    document.addEventListener("click", function (ev) {
      try {
        var a = ev.target && ev.target.closest && ev.target.closest("a[href]");
        if (!a) return;
        var m = /stock\.html\?(?:[^#]*&)?ticker=(\d{6})/.exec(a.getAttribute("href") || "");
        if (m) KOSA.track("stock_click", { ticker: m[1] });
      } catch (e) {}
    }, true);

    /* ② 얼마나 내려 읽었나. 리포트를 끝까지 보는지가 여기서 보인다.
       25·50·75·100% 를 한 번씩만 보낸다. */
    var hit = {}, maxPct = 0;
    function depth() {
      var h = document.documentElement;
      var total = Math.max(h.scrollHeight, document.body ? document.body.scrollHeight : 0)
        - window.innerHeight;
      if (total <= 0) return 100;
      return Math.min(100, Math.round((window.pageYOffset / total) * 100));
    }
    addEventListener("scroll", function () {
      try {
        var p = depth();
        if (p > maxPct) maxPct = p;
        [25, 50, 75, 100].forEach(function (step) {
          if (p >= step && !hit[step]) {
            hit[step] = 1;
            KOSA.track("scroll_depth", { percent: step });
          }
        });
      } catch (e) {}
    }, { passive: true });

    /* ③ 이 페이지를 언제 떠났나. 어디서 사람이 빠져나가는지 본다.
       pagehide 는 탭을 닫아도 뜬다(unload 는 요즘 브라우저에서 안 뜬다). */
    var t0 = Date.now(), left = false;
    function leaving() {
      if (left) return;
      left = true;
      try {
        KOSA.track("page_leave", {
          seconds: Math.round((Date.now() - t0) / 1000),
          max_scroll: maxPct
        });
      } catch (e) {}
    }
    addEventListener("pagehide", leaving);
    addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") leaving();
    });
  } catch (e) {}
})();
