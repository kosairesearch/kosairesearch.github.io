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
  var GA4_ID = "G-8ZHG2KXW6Z";    // GA4 측정 ID
  var NAVER_ID = "1aa82ad75b71490";  // 네이버 애널리틱스 ID

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

  // ── 공용 이벤트 헬퍼 — 코드 어디서든 KOSA.track() 호출 ──
  window.KOSA = {
    on: function () { return !!(GA4_ID || NAVER_ID); },
    track: function (name, params) {
      try { if (window.gtag) gtag("event", name, params || {}); } catch (e) {}
    }
  };
})();
