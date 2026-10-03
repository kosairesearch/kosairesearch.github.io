/* ============================================================
   KOSAI — 한국어 ⇄ 영어 (KOSi18n)
   실사이트(루트 i18n.js)와 스테이징(staging/i18n.js)이 같은 파일이다 — scripts/build_live.py 가 루트로 복사하고 --check 가 같은지 본다.

   실사이트 페이지마다 들어 있는 KOSi18n 과 쓰는 법이 같다.
     KOSi18n.register(사전, 바뀔 때 부를 함수) · KOSi18n.t('한국어') ·
     KOSi18n.setLang('en' | 'ko') · KOSi18n.lang
   설정 화면(settings-panel.js)의 '언어' 줄과 모듈들(auth-state · checkout ·
   consent …)이 이것을 찾는다. 이것이 없으면 언어 줄이 아예 안 보인다 —
   9월 26일 새 디자인으로 옮기며 빠졌던 것이 그 자리다(2026-10-03 복구).

   실사이트 것에 더한 것
     · 사전은 페이지 맨 끝의 <script type="application/json" data-kos-i18n>.
       생성기(comp_common.finish)가 그 페이지에 나오는 문구만 골라 넣는다.
       한국어로 보는 사람은 읽지 않는다.
     · 나중에 그려지는 글(검색 후보 · 목록 · 알림)도 바꾼다(MutationObserver).
     · placeholder · aria-label · title · alt 와 문서 제목.
     · 숫자가 바뀌는 문장 — 사전 키의 '#' 자리에 아무 숫자나 온다.
       "국내 상장 #개 종목" : "# listed Korean stocks"
     · 종목명은 자료의 영문명(name_en)으로. 없으면 한국어 이름 그대로.
     · 영어로 정한 사람에게 한국어가 먼저 비치지 않게 번역이 끝날 때까지
       본문을 가린다. 스크립트가 죽어도 1.5초 뒤에는 CSS 가 스스로 연다.
     · 말을 바꾸면(setLang) 페이지를 다시 연다 — 스크립트가 그린 글까지
       처음부터 그 말로 그리게. 실사이트는 그 자리에서 바꾼다.
   ============================================================ */
(function () {
  var KEY = 'kos-lang';
  var dict = {};                 // 정규화한 한국어 → 영어
  var tdict = {};                // 숫자 자리를 # 로 바꾼 한국어 → 영어
  var listeners = [];
  var txtOrig = new WeakMap();   // 글 조각 → 원래 한국어
  var attrOrig = new WeakMap();  // 요소 → {속성: 원래 한국어}
  var blockOrig = new WeakMap(); // 요소 → {html, key}
  var titleOrig = null;
  var ATTRS = ['placeholder', 'aria-label', 'title', 'alt'];
  var HAN = /[가-힣]/;
  /* 메일 링크의 ?lang= — 서버(functions/index.js customActionLink)가 회원 메일의 링크에 붙인다.
     auth-action.html 에서만 받는다(옛 실사이트 auth-action.html 머리에 있던 한 줄과 같은 일).
     이 파일의 글도 번역 사전을 고르는 데 쓰이므로(comp_common._i18n_corpus) 주석에 화면 문구를 그대로 적지 않는다. */
  try {
    if (/(^|\/)auth-action\.html$/i.test(location.pathname)) {
      var qlang = new URLSearchParams(location.search).get('lang');
      if (qlang === 'en' || qlang === 'ko') localStorage.setItem(KEY, qlang);
    }
  } catch (e) {}
  /* 말이 정해진 페이지 — 영어 종목 페이지(/en/stock/{종목코드}.html · scripts/build_stock_static.py)는 이 파일보다 먼저
     window.KOS_PAGE_LANG='en' 을 단다. 그 페이지는 저장된 말과 관계없이 그 말로 보인다 — 글이 이미 그 말로 미리 그려져 있고,
     검색 · 인공지능 수집 로봇이 읽는 것도 그 글이다. 저장된 말이 없으면 그 말을 저장한다(영어 검색 결과로 들어온 사람이 다른
     페이지로 옮겨도 영어로 보이게). 한국어를 이미 고른 사람의 설정은 바꾸지 않는다 — 그 페이지만 영어다. */
  var PAGE_LANG = window.KOS_PAGE_LANG === 'en' || window.KOS_PAGE_LANG === 'ko' ? window.KOS_PAGE_LANG : null;
  if (PAGE_LANG) { try { if (localStorage.getItem(KEY) == null) localStorage.setItem(KEY, PAGE_LANG); } catch (e) {} }
  var lang = PAGE_LANG || getLang();
  var mo = null, started = false;

  function getLang() { try { return localStorage.getItem(KEY) === 'en' ? 'en' : 'ko'; } catch (e) { return 'ko'; } }
  function norm(s) { return (s == null ? '' : String(s)).replace(/\s+/g, ' ').trim(); }

  /* 영어로 정한 사람에게는 번역이 끝날 때까지 본문을 가린다(머리에서 바로). 말이 정해진 페이지는 글이 이미 그 말이라 가리지 않는다. */
  var root = document.documentElement;
  root.setAttribute('lang', lang);
  if (lang === 'en' && !PAGE_LANG) root.classList.add('kos-i18n-wait');
  (function css() {
    var st = document.createElement('style');
    st.textContent = 'html.kos-i18n-wait body{visibility:hidden;animation:kosI18nShow 0s 1.5s forwards}' +
      '@keyframes kosI18nShow{to{visibility:visible}}' +
      /* 두 말로 미리 그려 둔 곳(브리핑 본문 등) — 지금 말이 아닌 쪽을 숨긴다 */
      'html[lang="en"] [data-lang="ko"],html:not([lang="en"]) [data-lang="en"]{display:none!important}';
    (document.head || root).appendChild(st);
  })();

  /* ── 사전 찾기 ─────────────────────────────────────────────
     ① 그대로 ② 날짜를 '@' 로(영어 날짜로 채움) ③ 숫자를 '#' 로 ④ 금액·주식 수(조·억·만·원·주)
     ⑤ 앞 번호('01 목차') ⑥ ' · ' · ' | ' · ' — ' 로 나뉜 조각마다.
     뒤를 보는 정규식(lookbehind)은 iOS 16.3 이하 사파리가 읽지 못해 쓰지 않는다 — 스크립트 전체가 죽는다. */
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var WD = { '일': 'Sun', '월': 'Mon', '화': 'Tue', '수': 'Wed', '목': 'Thu', '금': 'Fri', '토': 'Sat' };
  var DATE = /(\d{4})년 ?(\d{1,2})월 ?(\d{1,2})일(?: ?\(([일월화수목금토])\))?|(\d{1,2})월 ?(\d{1,2})일(?: ?\(([일월화수목금토])\))?|(\d{4})년 ?(\d{1,2})월(?! ?\d)/g;
  function dateTpl(s) {
    var ds = [];
    var key = s.replace(DATE, function (m, y, mo, d, w, mo2, d2, w2, y3, mo3) {
      if (y) ds.push(MON[mo - 1] + ' ' + (+d) + ', ' + y + (w ? ' (' + WD[w] + ')' : ''));
      else if (mo2) ds.push(MON[mo2 - 1] + ' ' + (+d2) + (w2 ? ' (' + WD[w2] + ')' : ''));
      else ds.push(MON[mo3 - 1] + ' ' + y3);
      return '@';
    });
    return { key: key, ds: ds };
  }
  function numTpl(s) {   // 날짜 · 종목코드 안의 '-' 는 부호가 아니다
    var nums = [];
    var key = s.replace(/[+\-−]?\d[\d,]*(?:\.\d+)?/g, function (m, off) {
      if (/^[+\-−]/.test(m) && off > 0 && /[\dA-Za-z]/.test(s.charAt(off - 1))) { nums.push(m.slice(1)); return m.charAt(0) + '#'; }
      nums.push(m); return '#';
    });
    return { key: key, nums: nums };
  }
  function fill(t, ch, vals) { var i = 0; return t.split(ch).reduce(function (a, b) { return a + (vals[i] != null ? vals[i++] : ch) + b; }); }
  function viaNum(s) {
    var n = numTpl(s);
    if (!n.nums.length) return null;
    var t = tdict[n.key];
    return t == null ? null : fill(t, '#', n.nums);
  }
  function fmt(v, dp) { return v.toLocaleString('en-US', { maximumFractionDigits: dp == null ? 1 : dp }); }
  /* 표 · 지표 칸의 금액과 주식 수. 실사이트 영어 화면과 같은 꼴(₩1.42T · ₩769.7B · ₩78,400 · 30M). */
  function money(s) {
    var m = s.match(/^([+\-−]?)([\d,]+(?:\.\d+)?) ?(조|억|만)? ?(원|주)?$/);
    if (!m || (!m[3] && !m[4])) return null;
    var sg = m[1] ? (m[1] === '+' ? '+' : '-') : '', v = parseFloat(m[2].replace(/,/g, '')), u = m[3] || '', k = m[4] || '';
    if (k === '주') {
      var n = u === '억' ? v * 1e8 : u === '만' ? v * 1e4 : v;
      if (n >= 1e9) return sg + fmt(n / 1e9, 2) + 'B';
      if (n >= 1e6) return sg + fmt(n / 1e6, 1) + 'M';
      return sg + fmt(n, 0) + ' shares';
    }
    var w = u === '조' ? v * 1e12 : u === '억' ? v * 1e8 : u === '만' ? v * 1e4 : v;
    if (u === '조' || w >= 1e12) return sg + '₩' + fmt(w / 1e12) + 'T';
    if (w >= 1e9) return sg + '₩' + fmt(w / 1e9) + 'B';
    if (w >= 1e6 && u) return sg + '₩' + fmt(w / 1e6) + 'M';
    return sg + '₩' + fmt(w, 0);
  }
  function look1(core) {
    var en = dict[core];
    if (en != null) return en;
    if (!/\d/.test(core)) return null;
    var d = dateTpl(core);
    if (d.ds.length) {
      var e2 = dict[d.key];
      if (e2 == null) e2 = viaNum(d.key);
      if (e2 != null) return fill(e2, '@', d.ds);
    }
    var e3 = viaNum(core);
    if (e3 != null) return e3;
    var mo = money(core);
    if (mo != null) return mo;
    var p = core.match(/^(\d{1,2}\.?) (.+)$/);
    if (p && HAN.test(p[2])) { var r = look1(p[2]); if (r == null) r = segs(p[2]); if (r != null) return p[1] + ' ' + r; }
    return null;
  }
  var SEPS = [' · ', ' | ', ' — ', ' / '];
  function segs(core) {
    for (var s = 0; s < SEPS.length; s++) {
      if (core.indexOf(SEPS[s]) < 0) continue;
      var parts = core.split(SEPS[s]), changed = false;
      for (var i = 0; i < parts.length; i++) {
        if (!HAN.test(parts[i])) continue;
        var r = look1(parts[i]);
        if (r == null) r = segs(parts[i]);
        if (r != null) { parts[i] = r; changed = true; }
      }
      if (changed) return parts.join(SEPS[s]);
    }
    return null;
  }
  function lookup(core) {
    var r = look1(core);
    return r != null ? r : segs(core);
  }
  function translateText(orig) {
    var m = String(orig).match(/^(\s*)([\s\S]*?)(\s*)$/);
    var core = norm(m[2]);
    if (!core || !HAN.test(core)) return orig;
    var en = lookup(core);
    if (en != null && en.indexOf('<') >= 0) en = en.replace(/<br\b[^>]*>/gi, ' ').replace(/<[^>]*>/g, '').replace(/\s+/g, ' ');   // 덩어리용 값(<br> · <span>)이 글 조각이나 속성에 오면 글만
    return en != null ? m[1] + en + m[3] : orig;
  }
  function t(ko) {
    if (ko == null) return '';
    if (lang !== 'en') return ko;
    var en = lookup(norm(ko));
    return en != null ? en : ko;
  }

  function doAttrs(el) {
    for (var i = 0; i < ATTRS.length; i++) {
      var a = ATTRS[i];
      if (!el.hasAttribute(a)) continue;
      var rec = attrOrig.get(el);
      var cur = el.getAttribute(a);
      if (!rec) { rec = {}; attrOrig.set(el, rec); }
      if (!(a in rec)) { if (!HAN.test(cur)) continue; rec[a] = cur; }
      var want = lang === 'en' ? translateText(rec[a]) : rec[a];
      if (cur !== want) el.setAttribute(a, want);
    }
  }
  function blockText(el) {   // <br> 은 띄어쓰기로 — '증권사가 다루지 않는<br>종목까지' → '증권사가 다루지 않는 종목까지'
    var out = '';
    (function rec(n) {
      for (var c = n.firstChild; c; c = c.nextSibling) {
        if (c.nodeType === 3) out += c.nodeValue;
        else if (c.nodeType === 1) { if (c.tagName === 'BR') out += ' '; else rec(c); }
      }
    })(el);
    return norm(out);
  }
  function doBlock(el) {
    if (!blockOrig.has(el)) blockOrig.set(el, { html: el.innerHTML, key: blockText(el) });
    var rec = blockOrig.get(el);
    if (lang === 'en') {
      var en = lookup(rec.key);
      if (en != null) { if (/<[a-z][\s\S]*>/i.test(en)) el.innerHTML = en; else el.textContent = en; return; }
    }
    if (el.innerHTML !== rec.html) el.innerHTML = rec.html;
  }
  /* 줄을 나눈 제목처럼 글이 <br> · <span> · <b> 로 쪼개진 덩어리 — 통째로 사전에 있으면 통째로 바꾼다.
     영어 값에 <br> 을 넣으면 영어도 그 자리에서 줄을 바꾼다. 안에 id 가 붙은 요소(스크립트가 고치는 칸)나
     입력칸 · 그림이 있으면 건드리지 않는다 — 통째로 바꾸면 그 요소가 사라진다. */
  var BLOCKISH = { P: 1, LI: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, TD: 1, TH: 1, DT: 1, DD: 1, SUMMARY: 1, FIGCAPTION: 1, LABEL: 1, SPAN: 1, BLOCKQUOTE: 1, CAPTION: 1 };
  var INLINE = { B: 1, STRONG: 1, EM: 1, I: 1, SPAN: 1, BR: 1, SMALL: 1, SUP: 1, SUB: 1, MARK: 1, WBR: 1, A: 1, CODE: 1, U: 1 };
  function autoBlock(el) {
    if (!BLOCKISH[el.tagName] || !el.firstElementChild || blockOrig.has(el)) return blockOrig.has(el);
    var all = el.getElementsByTagName('*');
    if (all.length > 40) return false;
    for (var i = 0; i < all.length; i++) {
      if (!INLINE[all[i].tagName] || all[i].id || all[i].hasAttribute('data-i18n-skip')) return false;
    }
    var key = blockText(el);
    if (!key || key.length > 600 || !HAN.test(key)) return false;
    if (lang !== 'en') return false;
    /* 덩어리째 바꾸는 것은 덩어리 전체가 번역될 때만. 조각 번역(' · ' 로 나눈 일부만 찾은 것)으로 바꾸면 안쪽 요소가 사라지고
       못 찾은 한국어가 그대로 붙어 남는다 — 그때는 안쪽 글을 하나씩 바꾼다 */
    var en = lookup(key);
    return en != null && !HAN.test(en.replace(/<[^>]*>/g, ''));
  }
  function walk(node) {
    if (node.nodeType === 1) {
      var tag = node.tagName;
      if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEMPLATE') return;
      if (node.hasAttribute('data-i18n-skip')) return;
      doAttrs(node);
      if (node.hasAttribute('data-i18n-block') || autoBlock(node)) { doBlock(node); return; }
      for (var c = node.firstChild; c; c = c.nextSibling) walk(c);
    } else if (node.nodeType === 3) {
      var v = node.nodeValue;
      if (!v || !v.trim()) return;
      if (!txtOrig.has(node)) { if (!HAN.test(v)) return; txtOrig.set(node, v); }
      var o = txtOrig.get(node);
      var want = lang === 'en' ? translateText(o) : o;
      if (node.nodeValue !== want) node.nodeValue = want;
    }
  }
  function inSkip(n) {
    for (var e = n.nodeType === 1 ? n : n.parentNode; e && e.nodeType === 1; e = e.parentNode) {
      if (e.hasAttribute('data-i18n-skip') || e.hasAttribute('data-i18n-block')) return true;
    }
    return false;
  }
  function doTitle() {
    if (titleOrig == null) titleOrig = document.title;
    var want = lang === 'en' ? translateText(titleOrig) : titleOrig;
    if (document.title !== want) document.title = want;
  }

  function apply() {
    root.setAttribute('lang', lang);
    if (document.body) walk(document.body);
    doTitle();
    if (mo) mo.takeRecords();   // 방금 바꾼 것은 다시 보지 않는다
  }

  /* 나중에 그려지는 글. 페이지가 바꾼 한국어는 새 원문으로 삼는다. */
  function watch() {
    if (!window.MutationObserver || mo) return;
    mo = new MutationObserver(function (recs) {
      for (var i = 0; i < recs.length; i++) {
        var r = recs[i];
        if (r.type === 'childList') {
          for (var j = 0; j < r.addedNodes.length; j++) {
            var n = r.addedNodes[j];
            if (n.nodeType === 3) txtOrig.delete(n);
            if (!inSkip(n)) walk(n);
          }
        } else if (r.type === 'characterData') {
          var tn = r.target;
          if (HAN.test(tn.nodeValue || '')) txtOrig.set(tn, tn.nodeValue); else txtOrig.delete(tn);
          if (!inSkip(tn)) walk(tn);
        } else if (r.type === 'attributes') {
          var el = r.target, rec = attrOrig.get(el), cur = el.getAttribute(r.attributeName);
          if (rec) { if (cur != null && HAN.test(cur)) rec[r.attributeName] = cur; else delete rec[r.attributeName]; }
          if (!inSkip(el)) doAttrs(el);
        }
      }
      mo.takeRecords();
    });
    mo.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
    var tEl = document.querySelector('title');
    if (tEl) new MutationObserver(function () { if (document.title !== translateText(titleOrig || '')) { titleOrig = null; doTitle(); } })
      .observe(tEl, { childList: true, characterData: true, subtree: true });
  }

  function add(d) {
    if (!d) return;
    for (var k in d) {
      if (!Object.prototype.hasOwnProperty.call(d, k)) continue;
      var nk = norm(k);
      if (nk.indexOf('#') >= 0) tdict[nk] = d[k]; else dict[nk] = d[k];
    }
  }
  function register(d, onChange) {
    add(d);
    if (onChange) { listeners.push(onChange); try { onChange(lang); } catch (e) {} }
    if (started) apply();
  }
  function setLang(l) {
    l = l === 'en' ? 'en' : 'ko';
    if (l === lang) return;
    var saved = false;
    try { localStorage.setItem(KEY, l); saved = localStorage.getItem(KEY) === l; } catch (e) {}
    /* 말이 정해진 페이지는 고른 말의 주소(<link rel="alternate" hreflang>)로 간다 — 같은 주소를 다시 열면 또 그 말이다.
       주소의 경로만 쓴다(같은 사이트 안에서 · 꼬리표와 #절 그대로) — hreflang 은 kosai.kr 로 적혀 있어 미러 · 시험 서버에서 밖으로 나가지 않게 */
    if (PAGE_LANG && l !== PAGE_LANG) {
      var alt = document.querySelector('link[rel="alternate"][hreflang="' + l + '"]');
      var path = alt && (alt.getAttribute('href') || '').replace(/^https?:\/\/[^\/]+/, '');
      if (path && path.charAt(0) === '/') { location.href = path + location.search + location.hash; return; }
    }
    /* 페이지를 다시 연다 — 모듈과 페이지 스크립트가 그린 글(목록 · 리포트 본문 · 설정 칸)까지 처음부터 그 말로 그리게.
       그 자리에서 바꾸면 영어로 그려진 글은 한국어 원문을 몰라 되돌리지 못한다(설정 칸이 영어로 남았다).
       저장소를 못 쓰는 창(사생활 보호 등)은 다시 열어도 말이 그대로라 그 자리에서만 바꾼다 */
    if (saved) { location.reload(); return; }
    lang = l;
    load();
    for (var i = 0; i < listeners.length; i++) { try { listeners[i](lang); } catch (e) {} }   // 다시 그릴 곳이 먼저
    apply();
  }

  /* 종목명 — 자료의 영문명은 'SAMSUNG ELECTRONICS CO,.LTD' 꼴이라 다듬는다(실사이트 cleanEn 과 같다). */
  function cleanEn(s) {
    s = (s || '').trim();
    var prev;
    do { prev = s; s = s.replace(/[\s,\.]*\b(CO|LTD|INC|CORP|CORPORATION|LIMITED|PLC|LLC)\b\.?\s*,?\s*\.?$/i, '').trim(); } while (s !== prev && s);
    s = s.replace(/[,.\s]+$/, '').trim();
    var letters = s.replace(/[^A-Za-z]/g, ''), upper = s.replace(/[^A-Z]/g, '');
    if (letters && upper.length / letters.length > 0.8) {
      var ACR = { LG: 1, SK: 1, KB: 1, KT: 1, HD: 1, CJ: 1, GS: 1, LS: 1, DB: 1, NH: 1, SC: 1, POSCO: 1, NAVER: 1, HMM: 1, OCI: 1, DL: 1, BGF: 1, JYP: 1, YG: 1, SM: 1, HLB: 1, KCC: 1, DGB: 1, BNK: 1, JB: 1, NHN: 1, SDI: 1, BM: 1, IPS: 1, NC: 1, LX: 1, KG: 1, DN: 1 };
      s = s.split(/\s+/).map(function (w) {
        var wu = w.toUpperCase().replace(/[.,]/g, '');
        if (ACR[wu]) return wu;
        if (/[&]/.test(w) && w === w.toUpperCase()) return w;
        return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
      }).join(' ');
    }
    return s;
  }
  var namesDone = null;
  function names(list) {
    var d = {};
    (list || []).forEach(function (s) { if (s && s.name && s.name_en && !(s.name in dict)) d[s.name] = cleanEn(s.name_en); });
    add(d);
  }
  function nameEn(s) { return s && s.name_en ? cleanEn(s.name_en) : (s && s.name) || ''; }
  /* 화면이 자료를 그릴 때 — 지금 말에 맞는 쪽. {ko, en} 이면 고르고, 종목이면 이름을 고른다. */
  function pick(o) { if (o == null) return ''; if (typeof o !== 'object') return String(o); return (lang === 'en' && o.en) || o.ko || o.en || ''; }
  function name(s) { return lang === 'en' ? nameEn(s) : (s && s.name) || ''; }

  /* 페이지 끝의 사전. 영어일 때만 읽는다 — 페이지 끝의 한 줄(KOSi18n.load())이 부르므로 뒤에 도는 모듈보다 먼저다. */
  var loaded = false;
  function load(force) {
    if (!force && lang !== 'en') return;
    if (!loaded) {
      var bl = document.querySelectorAll('script[type="application/json"][data-kos-i18n]');
      if (bl.length) loaded = true;
      for (var i = 0; i < bl.length; i++) { try { add(JSON.parse(bl[i].textContent)); } catch (e) {} }
    }
    var live = window.KOS_LIVE_DATA && window.KOS_LIVE_DATA.stocks;
    if (live && namesDone !== live) { namesDone = live; names(live); }
  }

  function init() {
    load();
    started = true;
    for (var i = 0; i < listeners.length; i++) { try { listeners[i](lang); } catch (e) {} }
    apply();
    watch();
    root.classList.remove('kos-i18n-wait');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();

  window.KOSi18n = {
    register: register, t: t, setLang: setLang, apply: apply, load: load, names: names, nameEn: nameEn, cleanEn: cleanEn, pick: pick, name: name,
    get lang() { return lang; }
  };
})();
