/* ============================================================
   KOSAI Analytics — GA4 + Naver Analytics (config-driven)
   ------------------------------------------------------------
   ▸ 측정 ID를 아래 두 변수에 넣으면 자동 활성화됩니다.
     - GA4_ID   : Google 애널리틱스 4 측정 ID ("G-XXXXXXXXXX")
     - NAVER_ID : 네이버 애널리틱스 ID (숫자/영문 코드)
   ▸ 비워두면 아무 것도 로드하지 않습니다(안전한 no-op).
   ▸ 전역 헬퍼: KOSA.track('event_name', { ...params })
   ============================================================ */
(function () {
  var GA4_ID = "G-XRYHGM36GS";    // GA4 측정 ID
  var NAVER_ID = "";  // 예: "a1b2c3d4e5"   ← 여기에 네이버 애널리틱스 ID

  // ── Google Analytics 4 ──
  if (GA4_ID && GA4_ID.indexOf("G-") === 0) {
    var g = document.createElement("script");
    g.async = true;
    g.src = "https://www.googletagmanager.com/gtag/js?id=" + GA4_ID;
    document.head.appendChild(g);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { dataLayer.push(arguments); };
    gtag("js", new Date());
    // IP 익명화 — 개인정보 최소수집
    gtag("config", GA4_ID, { anonymize_ip: true });
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

  // ── 공용 이벤트 헬퍼 — 코드 어디서든 KOSA.track() 호출 ──
  window.KOSA = {
    on: function () { return !!(GA4_ID || NAVER_ID); },
    track: function (name, params) {
      try { if (window.gtag) gtag("event", name, params || {}); } catch (e) {}
    }
  };
})();
