#!/usr/bin/env python3
"""리포트 목록(Reports.html) — 새 디자인 시안(comp). 다른 시안과 같은 부품(comp_common)을 쓴다.

    python3 scripts/build_reports_comp.py [출력 경로]    # 기본 preview/reports.html

Reports.html 의 기능은 그대로 옮겼다:
  · 검색(티커·종목명·업종) · '필터 추가' 창(업종 다중선택 · 시장 · 시가총액/PER/PBR/배당수익률/매출 성장률 범위 + 빠른 조건)
  · 걸린 조건 칩(누르면 다시 편집 · ✕ · 모두 지우기) · 정렬 9종 · 20개씩 쪽 넘기기 · 북마크 · 빈 상태 두 가지
  · PER·PBR·배당·성장률 값은 /data/valuation.js 에 있어 그 조건을 처음 펼칠 때(또는 그 정렬을 고를 때) 받는다.
    못 받으면 그 조건은 아무도 못 걸러낸다(목록이 통째로 비지 않게) — 실사이트와 같다.
북마크는 실사이트에서 KOSWatch(Firestore)가 맡는다. 시안은 로그인이 없어 화면 안에서만 켜고 끈다.
한/영 전환·로그인 상태는 옮길 때 붙인다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
.hero{padding:44px 0 0}
.crumb{font:500 13px/20px var(--font);color:var(--ink-55)}
.hero h1{margin:12px 0 0;font:700 44px/52px var(--font);letter-spacing:-.025em}
.hero .sub{margin:16px 0 0;font:400 17px/28px var(--font);color:var(--ink-72);max-width:640px}
/* 도구 줄 — 검색 · 필터 추가 · 정렬. 검색은 밑줄 입력(홈과 같다), 나머지는 글자 단추 */
.tools{margin-top:36px;display:flex;align-items:stretch;gap:32px}
.search{flex:1;min-width:0;display:flex;align-items:center;gap:12px;height:52px;border-bottom:1px solid var(--line);transition:border-color .15s} .search:focus-within{border-bottom-color:var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-55);flex:none}
.search input{flex:1;min-width:0;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0} .search input::placeholder{color:var(--ink-30)}
.tool{display:inline-flex;align-items:center;gap:6px;height:52px;border:0;background:none;padding:0;font:500 14px/1 var(--font);color:var(--ink-72);cursor:pointer;white-space:nowrap;transition:color .12s} .tool:hover{color:var(--ink)}
.tool svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none} .tool .caret{width:14px;height:14px;margin-left:-2px;color:var(--ink-55)}
/* 정렬 메뉴 — 떠 있는 면(홈 검색 제안과 같은 규칙) */
.sortwrap{position:relative;display:flex}
.smenu{display:none;position:absolute;right:0;top:calc(100% - 6px);z-index:30;min-width:210px;background:var(--surface);border:1px solid var(--hair);border-radius:12px;padding:6px 0;box-shadow:0 8px 24px rgba(20,20,20,.08)}
.sortwrap.open .smenu{display:block}
.smenu button{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;border:0;background:none;padding:9px 16px;font:400 14px/20px var(--font);color:var(--ink-72);cursor:pointer;text-align:left;white-space:nowrap}
.smenu button:hover{background:var(--surface-2);color:var(--ink)} .smenu button.on{color:var(--ink);font-weight:600}
.smenu .ck{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2.4;stroke-linecap:round;stroke-linejoin:round;opacity:0;flex:none} .smenu button.on .ck{opacity:1}
/* 걸린 조건 칩 — 누르면 다시 편집, ✕ 로 뺀다 */
.fchips{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin-top:16px} .fchips:empty{display:none}
.fchips .lbl{font:500 12px/20px var(--font);color:var(--ink-30);margin-right:2px}
.fchip{display:inline-flex;align-items:center;gap:8px;height:30px;padding:0 10px 0 12px;border:1px solid var(--line);border-radius:999px;font:500 13px/1 var(--font);color:var(--ink);cursor:pointer;transition:border-color .12s} .fchip:hover{border-color:var(--ink)}
.fchip .x{font:400 13px/1 var(--font);color:var(--ink-55);padding:4px 0} .fchip .x:hover{color:var(--ink)}
.clear-all{border:0;background:none;padding:0 2px;font:500 13px/1 var(--font);color:var(--ink-55);cursor:pointer;text-decoration:underline;text-underline-offset:4px;text-decoration-color:var(--line)} .clear-all:hover{color:var(--ink)}
/* 개수 */
.count{margin-top:28px;font:400 13px/20px var(--font);color:var(--ink-55)} .count b{font-weight:600;color:var(--ink)}
/* 목록 — 관심종목·홈 최신 리포트와 같은 줄 + 순위·북마크 */
.rl{margin-top:8px}
.rl-head,.rl-row{display:grid;grid-template-columns:36px 200px minmax(0,1fr) 170px 96px 36px;gap:0 20px}
.rl-head{padding:10px 0;border-bottom:1px solid var(--line);font:500 12px/16px var(--font);color:var(--ink-55)}
.rl-head span:nth-child(4),.rl-head span:nth-child(5){text-align:right} .rl-head span:last-child{text-align:center}
.rl-row{align-items:center;padding:16px 0;border-bottom:1px solid var(--hair);color:inherit;text-decoration:none}
.rk{font:500 12px/16px var(--font);color:var(--ink-30)}
.r-name{font:600 16px/22px var(--font)} .r-meta{margin-top:3px;font:400 12px/16px var(--font);color:var(--ink-55)} .r-meta .md{display:none} .r-meta .mval{color:var(--ink-72)}
.r-title{font:400 16px/24px var(--font)} .r-title.none{color:var(--ink-30)}
.rl-row:hover .r-title{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.r-price{text-align:right;font:500 16px/22px var(--font);white-space:nowrap} .r-price .c{margin-left:8px;font:600 13px/18px var(--font)}
.r-date{text-align:right;font:400 13px/18px var(--font);color:var(--ink-55)}
.wl{width:36px;height:36px;border:0;background:none;display:inline-flex;align-items:center;justify-content:center;color:var(--ink-30);cursor:pointer;border-radius:8px;padding:0;justify-self:center;transition:color .12s} .wl:hover{color:var(--ink)}
.wl svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round} .wl .ck{display:none} .wl.on{color:var(--ink)} .wl.on .pl{display:none} .wl.on .ck{display:block;stroke-width:2.4}
/* 쪽 넘기기 */
.pager{display:flex;justify-content:space-between;align-items:center;margin-top:18px;font:400 13px/20px var(--font);color:var(--ink-55)}
.pctl{position:relative;display:flex;gap:2px} .pctl>.ind{margin-top:4px} .pctl button{border:0;background:none;min-width:32px;height:32px;padding:0 6px;font:500 13px var(--font);color:var(--ink-55);cursor:pointer}
.pctl button:hover{color:var(--ink)} .pctl button.on{color:var(--ink);font-weight:600} .pctl button:disabled{color:var(--ink-30);cursor:default}
/* 빈 상태 */
.empty{padding:56px 0 24px;max-width:520px} .empty h2{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em} .empty p{margin:12px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}
/* 조건을 고르는 창 — 데스크톱은 '필터 추가' 아래 떠 있는 면, 좁은 화면은 아래에서 올라오는 시트 */
.pop-backdrop{display:none;position:fixed;inset:0;z-index:40;background:rgba(20,20,20,.16)} .pop-backdrop.open{display:block}
.popover{display:none;position:fixed;z-index:41;width:340px;max-height:min(72vh,600px);background:var(--surface);border:1px solid var(--hair);border-radius:14px;box-shadow:0 12px 32px rgba(20,20,20,.12);flex-direction:column;overflow:hidden} .popover.open{display:flex}
.pop-head{display:flex;align-items:center;gap:4px;padding:10px 10px 10px 18px;border-bottom:1px solid var(--hair);flex:none}
.pop-title{flex:1;font:600 14px/20px var(--font)}
.pop-back,.pop-close{border:0;background:none;width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;color:var(--ink-55);cursor:pointer;padding:0;border-radius:8px} .pop-back:hover,.pop-close:hover{color:var(--ink)}
.pop-back{margin-left:-10px;margin-right:2px} .pop-back svg,.pop-close svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.pop-body{overflow:auto;padding:6px 0;min-height:0}
.pop-field{display:flex;align-items:center;gap:10px;width:100%;border:0;background:none;padding:11px 18px;font:400 14px/20px var(--font);color:var(--ink);cursor:pointer;text-align:left} .pop-field:hover{background:var(--surface-2)}
.pop-field .dot{width:6px;height:6px;border-radius:50%;background:var(--ink);flex:none;margin:0 2px 0 -12px} .pop-field .fi{flex:none} .pop-field .cur{flex:1;min-width:0;font:400 13px/18px var(--font);color:var(--ink-55);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;text-align:right} .pop-field .arr{color:var(--ink-30);flex:none;margin-left:auto} .pop-field .cur+.arr{margin-left:0}
.pop-editor{padding:4px 18px 12px}
.checks{display:flex;flex-direction:column}
.range-inputs{display:flex;align-items:center;gap:12px;margin-top:6px}
.range-inputs input{flex:1;min-width:0;width:100%;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent;font:400 16px/24px var(--font);color:var(--ink);padding:8px 0;outline:0;-moz-appearance:textfield;transition:border-color .15s} .range-inputs input:focus{border-bottom-color:var(--ink)}
.range-inputs input::-webkit-outer-spin-button,.range-inputs input::-webkit-inner-spin-button{-webkit-appearance:none;margin:0} .range-inputs input::placeholder{color:var(--ink-30)} .range-inputs .tilde{color:var(--ink-30);flex:none}
.unit-note{margin-top:10px;font:400 12px/16px var(--font);color:var(--ink-55)}
.range-quick{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px} .range-quick button{border:1px solid var(--line);background:none;border-radius:999px;padding:0 11px;height:28px;font:500 12px/1 var(--font);color:var(--ink-72);cursor:pointer;transition:border-color .12s,color .12s} .range-quick button:hover{border-color:var(--ink);color:var(--ink)}
.pop-foot{display:flex;justify-content:flex-end;align-items:center;gap:18px;padding:12px 18px;border-top:1px solid var(--hair);flex:none} .pop-foot .btn{height:36px;padding:0 16px;font-size:13px}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .hero{padding:20px 0 0} .hero h1{font-size:32px;line-height:38px} .hero .sub{font-size:15px;line-height:24px}
  .tools{margin-top:24px;flex-wrap:wrap;gap:0 24px} .search{flex-basis:100%;height:48px} .search input{font-size:16px}
  .tool{height:44px} .sortwrap{margin-left:auto}
  .rl-head{display:none} .rl{margin-top:4px;border-top:1px solid var(--line)}
  .rl-row{grid-template-columns:24px minmax(0,1fr) auto;grid-template-areas:"rk name price" "rk title wl";gap:8px 12px;padding:14px 0;align-items:start}
  .rk{grid-area:rk;line-height:22px} .rl-row>div:nth-of-type(1){grid-area:name} .r-title{grid-area:title;font-size:15px;line-height:22px;color:var(--ink-72)} .r-price{grid-area:price}
  .wl{grid-area:wl;width:24px;height:22px;justify-self:end;align-self:center} .r-date{display:none} .r-meta .md{display:inline} .r-meta .md b{font-weight:400;white-space:nowrap}
  .r-price{font-size:15px;line-height:22px} .r-price .c{display:block;margin:2px 0 0}
  .popover.sheet{left:0!important;right:0;top:auto!important;bottom:0;width:auto;max-height:82vh;border-radius:16px 16px 0 0;border-bottom:0}
  .popover.sheet .pop-foot{padding-bottom:max(12px,env(safe-area-inset-bottom))}
}'''

BODY = '''<main class="wrap">
  <header class="hero">
    <p class="crumb" id="eyebrow">코스피 · 코스닥 상장사 리서치</p>
    <h1>종목 리포트</h1>
    <p class="sub">한국 상장사의 분석 리포트를 종목별로 확인하실 수 있습니다. 종목을 선택하시면 상세 리포트로 이동합니다.</p>
  </header>
  <div class="tools">
    <label class="search"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg><input id="searchInput" placeholder="티커 · 종목명 · 업종 검색" autocomplete="off"></label>
    <button type="button" class="tool" id="addFilterBtn"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>필터 추가</button>
    <div class="sortwrap" id="sortWrap">
      <button type="button" class="tool" id="sortBtn"><span id="sortLabel">시가총액 높은 순</span><svg class="caret" viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>
      <div class="smenu" id="sortMenu"></div>
    </div>
  </div>
  <div class="fchips" id="fchips"></div>
  <p class="count"><b id="countN">0</b>개 종목</p>
  <div class="rl" id="rl">
    <div class="rl-head"><span>NO.</span><span>종목</span><span>리포트 제목</span><span>현재가</span><span>작성일</span><span>관심</span></div>
    <div id="rows"></div>
  </div>
  <div class="pager" id="pager" hidden><span id="pinfo"></span><div class="pctl" id="pctl"></div></div>
  <div class="empty" id="empty" hidden>
    <h2 id="emptyH">검색 결과가 없습니다</h2>
    <p id="emptyMsg">다른 종목명·티커·업종으로 검색해 보시기 바랍니다.</p>
    <div id="emptyActs" hidden><button type="button" class="btn btn-ink" id="emptyReset">필터 초기화</button></div>
  </div>
</main>
<div class="pop-backdrop" id="popBackdrop"></div>
<div class="popover" id="popover" role="dialog" aria-label="필터 설정">
  <div class="pop-head">
    <button type="button" class="pop-back" id="popBack" aria-label="뒤로" hidden><svg viewBox="0 0 24 24"><path d="M15 18l-6-6 6-6"/></svg></button>
    <span class="pop-title" id="popTitle">필터 추가</span>
    <button type="button" class="pop-close" id="popClose" aria-label="닫기"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
  </div>
  <div class="pop-body" id="popBody"></div>
  <div class="pop-foot" id="popFoot" hidden><button type="button" class="tbtn danger" id="popRemove" hidden>제거</button><button type="button" class="btn btn-ink" id="popApply">적용</button></div>
</div>'''

JS = r'''(function(){
  var REPORTS=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[], RREP=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function won(n){return n==null?'—':Number(n).toLocaleString('ko-KR')+'원'} function chg(c){c=c||0;return (c>0?'▲ ':c<0?'▼ ':'')+Math.abs(c).toFixed(2)+'%'} function dir(c){return c>0?'up':c<0?'down':'flat'}
  /* 시가총액 단위는 조. 1조 미만은 억으로 읽는다 — 0.3조 보다 3,000억 이 읽기 쉽다. */
  function mcapF(jo){return !jo?'—':(jo>=1?(+jo).toLocaleString('en-US',{maximumFractionDigits:1})+'조':Math.round(jo*10000).toLocaleString('ko-KR')+'억')}
  var rcats=function(r){return (r.categories&&r.categories.length?r.categories:[r.sector])};
  /* 업종마다 몇 종목인지 같이 센다. 고르기 전에 규모를 알 수 있어야 헛걸음을 안 한다. */
  var SECTORS=[];(function(){var m={};REPORTS.forEach(function(r){rcats(r).forEach(function(c){m[c]=(m[c]||0)+1})});SECTORS=Object.keys(m).map(function(n){return{name:n,count:m[n]}}).sort(function(a,b){return b.count-a.count})})();
  var state={q:'',sort:'mcap_desc',page:1,pageSize:20,filters:{}};
  var SORT_LABEL={mcap_desc:'시가총액 높은 순',mcap_asc:'시가총액 낮은 순',change_desc:'등락률 높은 순',change_asc:'등락률 낮은 순',date:'최신 리포트순',name:'종목명순',per_asc:'PER 낮은 순',pbr_asc:'PBR 낮은 순',div_desc:'배당수익률 높은 순'};
  var rowsEl=document.getElementById('rows'),rlEl=document.getElementById('rl'),emptyEl=document.getElementById('empty'),pagerEl=document.getElementById('pager');
  var nBoth=REPORTS.filter(function(s){return RREP[s.ticker]}).length;
  document.getElementById('eyebrow').textContent='코스피 · 코스닥 상장사 '+nBoth.toLocaleString('ko-KR')+'종목 리포트';
  /* 값이 없는 종목은 방향과 상관없이 뒤로 보낸다. 앞에 두면 'PER 낮은 순'의 첫 화면이 전부 '—' 가 된다. */
  function byNum(k,d){return function(a,b){var x=a[k],y=b[k],xb=(x==null||isNaN(x)),yb=(y==null||isNaN(y));if(xb&&yb)return (b.mcap||0)-(a.mcap||0);if(xb)return 1;if(yb)return -1;return (x-y)*d}}
  function repTitle(tk){var R=RREP[tk];return R&&R.title?(R.title.ko||R.title.en||''):''} function repDate(tk){var R=RREP[tk];return R&&R.reportDate?R.reportDate:''} function repTs(tk){var R=RREP[tk];return R?(R.reportTs||R.reportDate||''):''}
  function getList(){var t=state.q.trim().toLowerCase();
    var l=REPORTS.filter(function(r){if(!passesFilters(r))return false;if(t&&!(r.name.toLowerCase().indexOf(t)>=0||r.ticker.indexOf(t)>=0||(r.sector||'').toLowerCase().indexOf(t)>=0))return false;return true});
    var s=state.sort;
    if(s==='mcap_desc')l.sort(function(a,b){return (b.mcap||0)-(a.mcap||0)});else if(s==='mcap_asc')l.sort(function(a,b){return (a.mcap||0)-(b.mcap||0)});
    else if(s==='change_desc')l.sort(function(a,b){return (b.change||0)-(a.change||0)});else if(s==='change_asc')l.sort(function(a,b){return (a.change||0)-(b.change||0)});
    else if(s==='date')l.sort(function(a,b){return String(repTs(b.ticker)).localeCompare(String(repTs(a.ticker)))||(b.mcap||0)-(a.mcap||0)});
    else if(s==='name')l.sort(function(a,b){return a.name.localeCompare(b.name,'ko')});
    else if(s==='per_asc')l.sort(byNum('per',1));else if(s==='pbr_asc')l.sort(byNum('pbr',1));else if(s==='div_desc')l.sort(byNum('div',-1));
    return l}
  /* 북마크 — 스테이징·실사이트에서는 KOSWatch(Firestore, watchlist.js)가 맡는다. 시안(KOSWatch 없음)은 화면 안에서만. */
  var WL={};function isW(tk){return window.KOSWatch?KOSWatch.has(tk):!!WL[tk]}
  function syncWl(){rowsEl.querySelectorAll('.wl').forEach(function(b){var on=isW(b.dataset.wl);b.classList.toggle('on',on);b.title=on?'관심종목에서 빼기':'관심종목 추가';b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',on?'true':'false')})}
  addEventListener('koswatch:change',syncWl);
  /* 관심종목 단추 — 더하기(추가) → 체크(추가됨). 상세 페이지의 '＋ 관심종목 추가' 와 같은 기호 */
  var bmSvg='<svg class="pl" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><svg class="ck" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>';
  function rowHtml(r,i){var c=r.change||0,t=repTitle(r.ticker),d=repDate(r.ticker);
    return '<a class="rl-row" href="/stock.html?ticker='+r.ticker+'" data-tk="'+r.ticker+'"><span class="rk">'+(i+1)+'</span>'
      +'<div><div class="r-name">'+esc(r.name)+'</div><div class="r-meta">'+r.ticker+' · '+esc(r.market)+' · '+esc(r.sector)+metricBits(r).map(function(m){return ' · '+m}).join('')+(d?'<span class="md"> · <b>'+esc(d)+'</b></span>':'')+'</div></div>'
      +'<div class="r-title'+(t?'':' none')+'">'+(t?esc(t):'리포트 준비 중')+'</div><div class="r-price">'+won(r.price)+'<span class="c '+dir(c)+'">'+chg(c)+'</span></div><div class="r-date">'+esc(d||'—')+'</div>'
      +'<button type="button" class="wl'+(isW(r.ticker)?' on':'')+'" data-wl="'+r.ticker+'" title="'+(isW(r.ticker)?'관심종목에서 빼기':'관심종목 추가')+'" aria-label="'+(isW(r.ticker)?'관심종목에서 빼기':'관심종목 추가')+'" aria-pressed="'+(isW(r.ticker)?'true':'false')+'">'+bmSvg+'</button></a>'}
  /* ── 숫자 조건 ── PER·PBR·배당·성장률은 /data/valuation.js 에 있다. 필터를 처음 건드릴 때 받는다. */
  var valState='none',valPromise=null;
  function attachVal(){var VAL=(window.KOS_VALUATION&&KOS_VALUATION.stocks)||{};REPORTS.forEach(function(s){var v=VAL[s.ticker];if(!v)return;
    if(v.eps&&v.eps>0&&s.price)s.per=+(s.price/v.eps).toFixed(1);if(v.bps&&v.bps>0&&s.price)s.pbr=+(s.price/v.bps).toFixed(2);if(v.dps!=null&&s.price)s.div=+(v.dps/s.price*100).toFixed(2);if(v.roe!=null)s.roe=v.roe;if(v.rev_g!=null)s.rev=v.rev_g})}
  function needVal(){if(valState==='ready')return Promise.resolve(true);if(valPromise)return valPromise;valState='loading';
    valPromise=new Promise(function(res){var el=document.createElement('script');el.src='/data/valuation.js';el.onload=function(){attachVal();valState='ready';res(true)};el.onerror=function(){valState='failed';res(false)};document.head.appendChild(el)});return valPromise}
  window.__valState=function(){return valState};
  var FIELDS={
    sector:{label:'업종',type:'multi',options:SECTORS},
    market:{label:'시장',type:'segment',options:['전체','코스피','코스닥']},
    mcap:{label:'시가총액',type:'range',unit:'조',quick:[{l:'1조원 이하',max:1},{l:'1조원 이상 ~ 10조원 이하',min:1,max:10},{l:'10조원 이상',min:10}]},
    per:{label:'PER',type:'range',unit:'배',quick:[{l:'10배 이하',max:10},{l:'20배 이하',max:20}]},
    pbr:{label:'PBR',type:'range',unit:'배',quick:[{l:'1배 이하',max:1},{l:'2배 이하',max:2}]},
    div:{label:'배당수익률',type:'range',unit:'%',quick:[{l:'2% 이상',min:2},{l:'4% 이상',min:4}]},
    rev:{label:'매출 성장률',type:'range',unit:'%',quick:[{l:'10% 이상',min:10},{l:'20% 이상',min:20},{l:'25% 이상',min:25}]}};
  var FIELD_ORDER=['sector','market','mcap','per','pbr','div','rev'],NEEDS_VAL={per:1,pbr:1,div:1,rev:1},SORT_NEEDS_VAL={per_asc:1,pbr_asc:1,div_desc:1};
  function passesFilters(r){for(var k in state.filters){var f=FIELDS[k],v=state.filters[k];
      if(f.type==='segment'){if(v!=='전체'&&r.market!==v)return false}
      else if(f.type==='multi'){if(v.length&&!rcats(r).some(function(c){return v.indexOf(c)>=0}))return false}
      else{ /* 값을 아직 못 받았으면 아무도 못 걸러낸다 — 목록이 통째로 비지 않게 */
        if(NEEDS_VAL[k]&&valState!=='ready')continue;var val=r[k];if(val==null||isNaN(val))return false;if(v.min!=null&&val<v.min)return false;if(v.max!=null&&val>v.max)return false}}
    return true}
  function anyFilter(){return Object.keys(state.filters).length>0}
  /* 걸어 둔 조건의 실제 값 — 종목명 아랫줄에 붙인다 */
  function metricBits(r){var out=[];FIELD_ORDER.forEach(function(k){if(state.filters[k]==null||FIELDS[k].type!=='range')return;var v=r[k];if(v==null||isNaN(v))return;
      if(k==='mcap'){out.push('<span class="mval">시가총액 '+mcapF(v)+'</span>');return}out.push('<span class="mval">'+FIELDS[k].label+' '+(k==='pbr'?v.toFixed(2):v.toFixed(1))+FIELDS[k].unit+'</span>')});return out}
  function chipLabel(k){var f=FIELDS[k],v=state.filters[k],L=f.label;
    if(f.type==='segment')return L+' · '+v;if(f.type==='multi')return v.length===1?L+' · '+v[0]:L+' · '+v[0]+' 외 '+(v.length-1);
    var u=f.unit;if(v.min!=null&&v.max!=null)return L+' '+v.min+'–'+v.max+u;if(v.min!=null)return L+' '+v.min+u+' 이상';return L+' '+v.max+u+' 이하'}
  function renderFchips(){var el=document.getElementById('fchips'),keys=FIELD_ORDER.filter(function(k){return state.filters[k]!=null});if(!keys.length){el.innerHTML='';return}
    el.innerHTML='<span class="lbl">필터</span>'+keys.map(function(k){return '<span class="fchip" data-field="'+k+'"><span class="lab">'+esc(chipLabel(k))+'</span><span class="x" data-remove="'+k+'" aria-label="빼기">✕</span></span>'}).join('')+'<button type="button" class="clear-all" id="clearAll">모두 지우기</button>'}
  /* ── 조건을 고르는 창 ── */
  var backdrop=document.getElementById('popBackdrop'),popover=document.getElementById('popover'),popTitle=document.getElementById('popTitle'),popBody=document.getElementById('popBody'),popFoot=document.getElementById('popFoot'),popBack=document.getElementById('popBack'),popApply=document.getElementById('popApply'),popRemove=document.getElementById('popRemove');
  var curField=null,checkSvg='<svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>';
  function place(anchor){var sheet=window.innerWidth<768;popover.classList.toggle('sheet',sheet);if(sheet){popover.style.left=popover.style.top=popover.style.maxHeight='';return}
    var r=anchor.getBoundingClientRect(),pw=340,gap=8,left=r.left;if(left+pw>window.innerWidth-12)left=window.innerWidth-12-pw;if(left<12)left=12;var top=r.bottom+gap;popover.style.left=left+'px';popover.style.top=top+'px';popover.style.maxHeight=Math.max(240,Math.min(600,window.innerHeight-top-16))+'px'}
  function openPop(anchor,view,field){place(anchor);backdrop.classList.add('open');popover.classList.add('open');if(view==='list')showList();else showEditor(field)}
  function closePop(){backdrop.classList.remove('open');popover.classList.remove('open');curField=null}
  function showList(){curField=null;popTitle.textContent='필터 추가';popBack.hidden=true;popFoot.hidden=true;
    popBody.innerHTML=FIELD_ORDER.map(function(k){var f=FIELDS[k],active=state.filters[k]!=null,L=f.label,cur=active?'<span class="cur">'+esc(chipLabel(k).replace(L+' · ','').replace(L+' ',''))+'</span>':'';
      return '<button type="button" class="pop-field" data-field="'+k+'">'+(active?'<span class="dot"></span>':'')+'<span class="fi">'+L+'</span>'+cur+'<span class="arr">›</span></button>'}).join('')}
  function showEditor(k){curField=k;var f=FIELDS[k],cur=state.filters[k];
    /* 값이 필요한 조건을 펼치는 순간 받기 시작한다 — 업종만 고르는 사람에게 247KB 를 지우지 않으려고 창을 열 때가 아니라 여기서 */
    if(NEEDS_VAL[k])needVal().then(function(v){if(v&&anyFilter())render()});
    popTitle.textContent=f.label;popBack.hidden=false;popFoot.hidden=false;popRemove.hidden=cur==null;
    var html='<div class="pop-editor">';
    if(f.type==='segment')html+='<div class="seg" data-ctl="segment">'+f.options.map(function(o){return '<button type="button" class="'+((cur||'전체')===o?'on':'')+'" data-v="'+o+'">'+o+'</button>'}).join('')+'</div>';
    else if(f.type==='multi'){var sel={};(cur||[]).forEach(function(c){sel[c]=1});html+='<div class="checks" data-ctl="multi">'+f.options.map(function(o){return '<label class="check'+(sel[o.name]?' on':'')+'" data-v="'+esc(o.name)+'"><span class="box">'+checkSvg+'</span>'+esc(o.name)+'<span class="count">'+o.count+'</span></label>'}).join('')+'</div>'}
    else{var mn=cur&&cur.min!=null?cur.min:'',mx=cur&&cur.max!=null?cur.max:'';
      html+='<div class="range-edit" data-ctl="range"><div class="range-inputs"><input id="rMin" type="number" inputmode="decimal" placeholder="최소" value="'+mn+'"><span class="tilde">~</span><input id="rMax" type="number" inputmode="decimal" placeholder="최대" value="'+mx+'"></div><div class="unit-note">단위 · '+f.unit+'</div>'
        +(f.quick?'<div class="range-quick">'+f.quick.map(function(q,i){return '<button type="button" data-qi="'+i+'">'+q.l+'</button>'}).join('')+'</div>':'')+'</div>'}
    popBody.innerHTML=html+'</div>';popBody.scrollTop=0;
    var seg=popBody.querySelector('.seg');if(seg)window.kosInd(seg,'x');
    var fi=popBody.querySelector('#rMin');if(fi&&window.innerWidth>=768)fi.focus()}
  function readEditor(){var f=FIELDS[curField];if(f.type==='segment'){var a=popBody.querySelector('.seg .on');return a?a.dataset.v:'전체'}
    if(f.type==='multi')return [].slice.call(popBody.querySelectorAll('.check.on')).map(function(c){return c.dataset.v});
    var mn=popBody.querySelector('#rMin').value,mx=popBody.querySelector('#rMax').value;return{min:mn===''?null:+mn,max:mx===''?null:+mx}}
  function isEmptyVal(v){var f=FIELDS[curField];if(f.type==='segment')return v==='전체';if(f.type==='multi')return v.length===0;return v.min==null&&v.max==null}
  document.getElementById('addFilterBtn').addEventListener('click',function(e){openPop(e.currentTarget,'list')});
  backdrop.addEventListener('click',closePop);document.getElementById('popClose').addEventListener('click',closePop);
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&popover.classList.contains('open'))closePop()});
  popBack.addEventListener('click',function(){place(document.getElementById('addFilterBtn'));showList()});
  popBody.addEventListener('click',function(e){var fb=e.target.closest('.pop-field');if(fb){showEditor(fb.dataset.field);return}
    var seg=e.target.closest('.seg button');if(seg){[].slice.call(seg.parentElement.children).forEach(function(b){b.classList.toggle('on',b===seg)});window.kosInd(seg.parentElement,'x')();return}
    var chk=e.target.closest('.check');if(chk){chk.classList.toggle('on');return}
    var q=e.target.closest('.range-quick button');if(q){var qd=FIELDS[curField].quick[+q.dataset.qi];popBody.querySelector('#rMin').value=qd.min!=null?qd.min:'';popBody.querySelector('#rMax').value=qd.max!=null?qd.max:''}});
  popBody.addEventListener('keydown',function(e){if(e.key==='Enter'&&e.target.tagName==='INPUT')popApply.click()});
  popApply.addEventListener('click',function(){var v=readEditor(),k=curField;if(isEmptyVal(v))delete state.filters[k];else state.filters[k]=v;state.page=1;closePop();render();
    if(state.filters[k]&&NEEDS_VAL[k])needVal().then(function(){render()})});
  popRemove.addEventListener('click',function(){delete state.filters[curField];state.page=1;closePop();render()});
  document.getElementById('fchips').addEventListener('click',function(e){if(e.target.closest('#clearAll')){state.filters={};state.page=1;render();return}
    var rm=e.target.closest('[data-remove]');if(rm){delete state.filters[rm.dataset.remove];state.page=1;render();return}
    var chip=e.target.closest('.fchip');if(chip)openPop(chip,'editor',chip.dataset.field)});
  /* ── 정렬 메뉴 ── */
  var sortWrap=document.getElementById('sortWrap'),sortMenu=document.getElementById('sortMenu');
  sortMenu.innerHTML=Object.keys(SORT_LABEL).map(function(k){return '<button type="button" data-v="'+k+'" class="'+(k===state.sort?'on':'')+'">'+SORT_LABEL[k]+'<svg class="ck" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg></button>'}).join('');
  function repaintSort(){document.getElementById('sortLabel').textContent=SORT_LABEL[state.sort];[].slice.call(sortMenu.children).forEach(function(b){b.classList.toggle('on',b.dataset.v===state.sort)})}
  document.getElementById('sortBtn').addEventListener('click',function(e){e.stopPropagation();sortWrap.classList.toggle('open')});
  sortMenu.addEventListener('click',function(e){var b=e.target.closest('button[data-v]');if(!b)return;state.sort=b.dataset.v;state.page=1;sortWrap.classList.remove('open');render();if(SORT_NEEDS_VAL[state.sort])needVal().then(function(){render()})});
  document.addEventListener('click',function(e){if(!sortWrap.contains(e.target))sortWrap.classList.remove('open')});
  /* ── 그리기 ── */
  function render(){repaintSort();renderFchips();var l=getList();document.getElementById('countN').textContent=l.length.toLocaleString('ko-KR');
    if(!l.length){rlEl.hidden=true;pagerEl.hidden=true;emptyEl.hidden=false;var on=anyFilter();
      /* 조건 때문에 빈 것과 검색어 때문에 빈 것은 다음 할 일이 다르다 */
      document.getElementById('emptyH').textContent=on?'조건에 맞는 종목이 없습니다':'검색 결과가 없습니다';
      document.getElementById('emptyMsg').textContent=on?'조건을 넓히거나 지워 보시기 바랍니다.':'다른 종목명·티커·업종으로 검색해 보시기 바랍니다.';document.getElementById('emptyActs').hidden=!on;return}
    rlEl.hidden=false;emptyEl.hidden=true;
    var total=l.length,size=state.pageSize,pages=Math.max(1,Math.ceil(total/size));if(state.page>pages)state.page=pages;if(state.page<1)state.page=1;var start=(state.page-1)*size;
    rowsEl.innerHTML=l.slice(start,start+size).map(function(r,i){return rowHtml(r,start+i)}).join('');
    if(pages<=1){pagerEl.hidden=true;return}pagerEl.hidden=false;
    document.getElementById('pinfo').textContent=(start+1)+'–'+Math.min(start+size,total)+' / 총 '+total.toLocaleString('ko-KR')+'개';
    var BLK=matchMedia('(max-width:640px)').matches?5:10,blk=Math.floor((state.page-1)/BLK),bs=blk*BLK+1,be=Math.min(bs+BLK-1,pages),b='<button type="button" '+(state.page<=1?'disabled':'')+' data-pg="prev">‹</button>';
    for(var i=bs;i<=be;i++)b+='<button type="button" class="'+(i===state.page?'on':'')+'" data-pg="'+i+'"><span>'+i+'</span></button>';b+='<button type="button" '+(state.page>=pages?'disabled':'')+' data-pg="next">›</button>';
    var pc=document.getElementById('pctl');pc.querySelectorAll('button').forEach(function(x){x.remove()});pc.insertAdjacentHTML('afterbegin',b);window.kosInd(pc,'x','.on>span')(true)}
  document.getElementById('searchInput').addEventListener('input',function(e){state.q=e.target.value;state.page=1;render()});
  rowsEl.addEventListener('click',function(e){var b=e.target.closest('.wl');if(!b)return;e.preventDefault();e.stopPropagation();var tk=b.dataset.wl;if(window.KOSWatch){if(KOSWatch.has(tk))KOSWatch.remove(tk);else if(!KOSWatch.add(tk))return;}else if(isW(tk))delete WL[tk];else WL[tk]=1;var on=isW(tk);b.classList.toggle('on',on);b.title=on?'관심종목에서 빼기':'관심종목 추가';b.setAttribute('aria-label',b.title);b.setAttribute('aria-pressed',on?'true':'false')});
  document.getElementById('pctl').addEventListener('click',function(e){var b=e.target.closest('button[data-pg]');if(!b)return;var pg=b.dataset.pg;if(pg==='prev')state.page=Math.max(1,state.page-1);else if(pg==='next')state.page++;else state.page=+pg;render();
    var pad=parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)||0;window.scrollTo({top:rlEl.getBoundingClientRect().top+window.scrollY-pad,behavior:'smooth'})});
  document.getElementById('emptyReset').addEventListener('click',function(){state.filters={};state.page=1;render()});
  addEventListener('resize',function(){if(popover.classList.contains('open'))place(curField?(document.querySelector('.fchip[data-field="'+curField+'"]')||document.getElementById('addFilterBtn')):document.getElementById('addFilterBtn'))});
  window.__kosReports={state:state,getList:getList,FIELDS:FIELDS,render:render,openPop:openPop,showEditor:showEditor};
  render();
})();
'''


def build(out_path):
    html = (C.head('종목 리포트 — 디자인 시안 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('리포트') + '\n' + BODY + '\n' + C.FOOTER + '\n'
            + '<script src="/data/stocks.js"></script>\n<script src="/data/reports-index.js"></script>\n<script>\n' + JS + C.JS + '\n</script>\n</body>\n</html>')
    C.emit(out_path, html)
    print(f'✅ {out_path} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'preview/reports.html'))
