#!/usr/bin/env python3
"""홈(Home.html) — 새 디자인 시안(comp). 리포트 시안(build_stock_comp.py)과 같은 부품(comp_common)을 쓴다.

    python3 scripts/build_home_comp.py [출력 경로]    # 기본 preview/home.html

Home.html 의 기능은 그대로: 검색(자동완성·최근 본 종목·화살표·엔터), 최신 리포트 6편(검색어로 거름),
업종 탭(정해진 순서 · 데스크톱은 전부 두 줄 · 휴대폰은 한 줄 스크롤 + 끝의 '전체 업종' 시트) 아래 거래대금 순 종목 표. 데이터는 실사이트와 같은
/data/stocks.js · /data/reports-index.js 를 그 자리에서 읽는다. 한/영 전환·로그인 상태·마키(컨베이어)는 시안에서는 뺐다 —
시안이 통과하면 Home.html 에 옮길 때 붙인다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
/* 히어로 — 왼쪽 정렬 · 구호 · 한 줄 검색 */
.hero{padding:56px 0 8px;max-width:680px}
.eyebrow{margin:0;font:500 13px/20px var(--font);color:var(--ink-55)}
.hero h1{margin:14px 0 0;font:700 44px/54px var(--font);letter-spacing:-.025em}
.sub{margin:18px 0 0;font:400 17px/28px var(--font);color:var(--ink-72);max-width:560px}
.search-wrap{position:relative;margin-top:36px}
.search{display:flex;align-items:center;gap:12px;height:56px;border-bottom:1px solid var(--line);transition:border-color .15s}
.search:focus-within{border-bottom-color:var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-55);flex:none}
.search input{flex:1;min-width:0;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0}
.search input::placeholder{color:var(--ink-30)}
.search .btn{height:36px;padding:0 16px;flex:none}
/* 자동완성 — 본문 위에 뜨는 판이라 여기만 면·그림자를 쓴다 */
.ac{display:none;position:absolute;left:0;right:0;top:calc(100% + 8px);z-index:20;background:var(--surface);border:1px solid var(--hair);border-radius:12px;padding:6px 0;box-shadow:0 8px 24px rgba(20,20,20,.08)}
.ac.show{display:block}
.ac-head{display:flex;justify-content:space-between;align-items:center;padding:8px 16px 6px;font:500 12px/16px var(--font);color:var(--ink-55)}
.ac-head button{border:0;background:none;font:500 12px/16px var(--font);color:var(--ink-55);cursor:pointer;padding:0} .ac-head button:hover{color:var(--ink)}
.ac-item{display:flex;align-items:center;gap:14px;padding:10px 16px;font:400 15px/20px var(--font);color:var(--ink);cursor:pointer}
.ac-item:hover,.ac-item.active{background:var(--surface-2)}
.ac-tk{font:500 12px/16px var(--font);color:var(--ink-55);width:56px;flex:none} .ac-nm{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis} .ac-nm mark{background:none;color:inherit;font-weight:600} .ac-sec{font:400 12px/16px var(--font);color:var(--ink-55)}
.ac-x{border:0;background:none;color:var(--ink-30);font:400 18px/1 var(--font);cursor:pointer;padding:0 2px} .ac-x:hover{color:var(--ink)}
.ac-empty{padding:12px 16px;font:400 14px/20px var(--font);color:var(--ink-55)}
/* 절 */
.sec{padding-top:72px}
/* 최신 리포트 — 줄 목록 */
.rows{border-top:1px solid var(--line)}
.row{display:grid;grid-template-columns:200px minmax(0,1fr) 170px 96px;gap:24px;align-items:center;padding:18px 0;border-bottom:1px solid var(--hair)}
.row:hover .r-title{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.r-name{font:600 16px/22px var(--font)} .r-meta{margin-top:3px;font:400 12px/16px var(--font);color:var(--ink-55)} .r-meta .md{display:none}
.r-title{font:400 16px/24px var(--font);color:var(--ink)}
.r-price{text-align:right;font:500 16px/22px var(--font);white-space:nowrap} .r-price .c{margin-left:8px;font:600 13px/18px var(--font)}
.r-date{text-align:right;font:400 13px/18px var(--font);color:var(--ink-55)}
.empty{margin:0;padding:28px 0;font:400 14px/20px var(--font);color:var(--ink-55)}
/* 업종 탭 — 데스크톱: 정해진 순서로 전부 두 줄(더보기 없음). 줄 사이 23px 로 가로 간격(22px)과 맞춘다 — 한 줄용 44px 칸을
   그대로 쌓으면 줄 사이가 51px 로 벌어져 두 덩어리로 보인다(9/26 사장). 간격은 어디나 22px 로 같다 — 묶음 사이만
   1.5배 띄워 봤더니 묶음이 아니라 '간격이 제각각'으로 읽혔다(9/26 사장). 묶음은 순서로만 보이고, 휴대폰 시트에는 이름표가 있다. */
.tabs{position:relative;display:flex;flex-wrap:wrap;gap:8px 22px;padding-bottom:8px;border-bottom:1px solid var(--hair);margin-bottom:10px}
.tab{flex:none;position:relative;border:0;background:none;padding:0;font:500 13px/30px var(--font);color:var(--ink-55);cursor:pointer;white-space:nowrap;transition:color .12s} .tab:hover{color:var(--ink)} .tab.on{color:var(--ink);font-weight:600}
.tab.more{display:none}
/* 업종 고르기 시트 — 휴대폰에서 '전체 업종'을 누르면 아래에서 올라온다. 리포트 목록의 필터 시트와 같은 옷 */
.pop-backdrop{display:none;position:fixed;inset:0;z-index:40;background:rgba(20,20,20,.16)} .pop-backdrop.open{display:block}
.sheet{display:none;position:fixed;z-index:41;left:0;right:0;bottom:0;max-height:82vh;background:var(--surface);border:1px solid var(--hair);border-bottom:0;border-radius:16px 16px 0 0;box-shadow:0 12px 32px rgba(20,20,20,.12);flex-direction:column;overflow:hidden} .sheet.open{display:flex}
.pop-head{display:flex;align-items:center;gap:4px;padding:10px 10px 10px 18px;border-bottom:1px solid var(--hair);flex:none} .pop-title{flex:1;font:600 14px/20px var(--font)}
.pop-close{border:0;background:none;width:30px;height:30px;display:inline-flex;align-items:center;justify-content:center;color:var(--ink-55);cursor:pointer;padding:0;border-radius:8px} .pop-close:hover{color:var(--ink)} .pop-close svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round}
.pop-body{overflow:auto;overscroll-behavior:contain;padding:8px 18px max(20px,env(safe-area-inset-bottom));min-height:0}
.sg{margin:12px 0 0} .sg:first-child{margin-top:4px} .sg h4{margin:0 0 2px;font:500 12px/20px var(--font);color:var(--ink-55)}
.sw{display:flex;flex-wrap:wrap;gap:0 22px} .sw button{position:relative;border:0;background:none;padding:0;font:500 15px/40px var(--font);color:var(--ink-72);cursor:pointer;white-space:nowrap} .sw button.on{color:var(--ink);font-weight:600} .sw button.on::after{content:"";position:absolute;left:0;right:0;bottom:6px;height:2px;background:var(--ink)}
.sg.top .sw button{font-weight:600}
/* 종목 표 */
.tbl.movers th:first-child,.tbl.movers td:first-child{white-space:normal;min-width:200px}
.tbl.movers tbody tr{cursor:pointer} .tbl.movers tbody tr:hover .m-name{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}
.tbl.movers td{padding-top:13px;padding-bottom:13px}
.m-rank{display:inline-block;width:24px;font:500 12px/16px var(--font);color:var(--ink-30)}
.m-name{font:500 14px/20px var(--font)} .m-meta{margin:2px 0 0 24px;font:400 12px/16px var(--font);color:var(--ink-55)}
.empty-td{text-align:left;color:var(--ink-55);padding:28px 0}
.note{margin:16px 0 0;font:400 12px/18px var(--font);color:var(--ink-55)}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .hero{padding:24px 0 4px} .hero h1{font-size:32px;line-height:40px} .sub{font-size:15px;line-height:24px;margin-top:12px}
  .search-wrap{margin-top:24px} .search{height:50px} .search input{font-size:16px} .search .btn{height:32px;padding:0 12px;font-size:13px}
  .sec{padding-top:48px}
  .row{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"name price" "title title";gap:8px 12px;padding:14px 0;align-items:start}
  .row>div:first-child{grid-area:name} .r-title{grid-area:title;font-size:15px;line-height:22px;color:var(--ink-72)} .r-price{grid-area:price}
  .r-date{display:none} .r-meta .md{display:inline}
  .r-price{font-size:15px;line-height:22px} .r-price .c{display:block;margin:2px 0 0}
  .tbl.movers th:first-child,.tbl.movers td:first-child{min-width:150px}
  /* 업종 탭 — 한 줄 스크롤. '전체 업종'은 줄 맨 끝이라 끝까지 밀어야 보인다(9/26 사장: 처음부터 보이면 지저분하다) */
  .tabs{flex-wrap:nowrap;gap:22px;height:44px;padding-bottom:0;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;touch-action:pan-x;overscroll-behavior-x:contain} .tabs::-webkit-scrollbar{display:none}
  .tab{line-height:44px}
  .tab.more{display:inline-flex;align-items:center;gap:3px;color:var(--ink);padding-right:2px} .tab.more svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
}'''

BODY = '''<main class="wrap">
  <header class="hero">
    <p class="eyebrow" id="eyebrow">코스피 · 코스닥 상장사 리서치</p>
    <h1>한국 상장사,<br>AI 리서치로 한눈에.</h1>
    <p class="sub">재무·실적·밸류에이션을 한 페이지에. 핵심만 정리한 종목 분석으로 시장을 빠르게 파악하실 수 있습니다.</p>
    <div class="search-wrap">
      <form class="search" id="searchForm" role="search" autocomplete="off" onsubmit="return false">
        <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>
        <input id="searchInput" placeholder="티커 · 종목명 · 업종 검색" autocomplete="off" role="combobox" aria-expanded="false" aria-controls="acList">
        <button class="btn btn-ink" type="button" id="searchBtn">검색</button>
      </form>
      <div class="ac" id="acList" role="listbox"></div>
    </div>
  </header>
  <section class="sec" id="reports">
    <div class="sec-h"><h2>최신 리포트</h2><a class="more" href="/Reports.html">전체 리포트 보기 <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a></div>
    <div class="rows" id="reportRows"></div>
    <p class="empty" id="reportEmpty" hidden>검색 결과가 없습니다.</p>
  </section>
  <section class="sec" id="movers">
    <div class="sec-h"><h2>업종별 주목 종목</h2><a class="more" href="/industry.html">업종 분석 페이지로 <svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a></div>
    <div class="tabs" id="tabs"></div>
    <div class="tbl-wrap"><table class="tbl movers"><thead><tr><th>종목</th><th>현재가</th><th>등락률</th><th>거래대금</th><th>시가총액</th></tr></thead><tbody id="moverBody"></tbody></table></div>
    <p class="note" id="moverNote"></p>
  </section>
</main>
<div class="pop-backdrop" id="sectorBack"></div>
<div class="sheet" id="sectorSheet" role="dialog" aria-modal="true" aria-label="업종 고르기"><div class="pop-head"><div class="pop-title">업종</div><button type="button" class="pop-close" id="sectorClose" aria-label="닫기"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div><div class="pop-body" id="sectorBody"></div></div>'''

JS = r'''(function(){
  var live=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[], RREP=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
  var dd=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.dataDate)||''; var dateF=dd?dd.slice(0,4)+'-'+dd.slice(4,6)+'-'+dd.slice(6,8):'';
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  var fmt={won:function(n){return n==null?'—':n.toLocaleString('ko-KR')+'원'},
    chg:function(c){c=c||0;return (c>0?'▲ ':c<0?'▼ ':'')+Math.abs(c).toFixed(2)+'%'},
    dir:function(c){return c>0?'up':c<0?'down':'flat'},
    mcap:function(n){return !n?'—':(n>=1?(+n).toLocaleString('en-US',{maximumFractionDigits:1})+'조':Math.round(n*10000).toLocaleString('ko-KR')+'억')},
    amt:function(n){return !n?'—':(n>=1e12?(n/1e12).toFixed(1)+'조':Math.round(n/1e8).toLocaleString('ko-KR')+'억')}};
  // 리포트가 있는 종목 수 하나만 — 종목 수와 리포트 수를 나란히 두면 새로 상장돼 아직 리포트가 없는 종목만큼 어긋나 보인다
  var nBoth=live.filter(function(s){return RREP[s.ticker]}).length;
  document.getElementById('eyebrow').textContent='코스피 · 코스닥 상장사 '+nBoth.toLocaleString('ko-KR')+'종목 리포트';

  /* ---- 최신 리포트 6편 (Home.html 과 같은 규칙) ---- */
  var REPORTS=live.filter(function(s){return RREP[s.ticker]}).map(function(s){var r=RREP[s.ticker];return Object.assign({},s,{reportDate:r.reportDate,reportTs:r.reportTs||r.reportDate,title:(r.title&&r.title.ko)||''})});
  REPORTS.sort(function(a,b){return String(b.reportTs||'').localeCompare(String(a.reportTs||''))||(b.mcap||0)-(a.mcap||0)}); REPORTS=REPORTS.slice(0,6);
  var rowsEl=document.getElementById('reportRows'),emptyEl=document.getElementById('reportEmpty');
  function renderReports(q){
    var t=(q||'').trim().toLowerCase();
    var list=REPORTS.filter(function(d){return !t||d.name.toLowerCase().indexOf(t)>=0||d.ticker.indexOf(t)>=0||(d.sector||'').toLowerCase().indexOf(t)>=0});
    rowsEl.innerHTML=list.map(function(d){var c=d.change||0;
      return '<a class="row" href="/stock.html?ticker='+d.ticker+'"><div><div class="r-name">'+esc(d.name)+'</div><div class="r-meta">'+d.ticker+' · '+esc(d.market)+' · '+esc(d.sector)+'<span class="md"> · '+esc(d.reportDate)+'</span></div></div>'
        +'<div class="r-title">'+esc(d.title)+'</div><div class="r-price">'+fmt.won(d.price)+'<span class="c '+fmt.dir(c)+'">'+fmt.chg(c)+'</span></div><div class="r-date">'+esc(d.reportDate)+'</div></a>'}).join('');
    emptyEl.hidden=!!list.length;
  }

  /* ---- 업종 탭 + 거래대금 순 종목 표 ---- */
  var MOVERS=live.slice().sort(function(a,b){return (b.trading_value||0)-(a.trading_value||0)});
  function mcats(m){return (m.categories&&m.categories.length)?m.categories:[m.sector]}
  /* 업종 순서는 정해 둔다(묶음별). 그날 거래대금 순으로 늘어놓으면 매일 자리가 바뀌어 찾기 어렵다(9/26 사장).
     자료에 묶음에 없는 업종이 생기면 마지막 묶음 끝에 붙는다 — 사라지지 않는다. */
  var GROUPS=[['테마',['인공지능(AI)','로봇']],['기술·미디어',['반도체','전자·부품','IT·소프트웨어','게임','통신','미디어·엔터']],['산업',['기계·장비','전기장비','조선','자동차','항공·방산','건설·건자재','철강·금속','운송·물류']],['에너지·소재',['화학','정유','에너지·전력','2차전지']],['소비',['유통·소비재','식음료','화장품','섬유·패션·생활','호텔·레저']],['금융',['금융','보험','지주','부동산·리츠']],['헬스케어 · 기타',['바이오·제약','기타']]];
  var HOT=[]; MOVERS.forEach(function(m){mcats(m).forEach(function(c){if(c&&HOT.indexOf(c)<0)HOT.push(c)})});   // 오늘 거래가 몰린 순 — 휴대폰 한 줄에 쓴다
  var have={}; HOT.forEach(function(c){have[c]=1});
  var ORDER=[]; GROUPS.forEach(function(g){g[1].forEach(function(s){if(have[s])ORDER.push({s:s,g:g[0]})})});
  HOT.forEach(function(c){if(!ORDER.some(function(o){return o.s===c}))ORDER.push({s:c,g:GROUPS[GROUPS.length-1][0]})});
  var LIMIT=10,active='전체',mq=window.matchMedia('(max-width:820px)');
  var tabsEl=document.getElementById('tabs'),body=document.getElementById('moverBody');
  function tabBtn(s,cls){return '<button type="button" class="tab'+(s===active?' on':'')+(cls||'')+'" data-s="'+esc(s)+'">'+esc(s)+'</button>'}
  function renderTabs(){
    var h;
    if(mq.matches){ /* 휴대폰: 전체 · (고른 업종) · 오늘 거래가 몰린 업종 아홉 · 맨 끝에 '전체 업종'(시트) */
      var shown=HOT.slice(0,LIMIT-1); if(active!=='전체'&&shown.indexOf(active)<0)shown.unshift(active);
      h=tabBtn('전체')+shown.map(function(s){return tabBtn(s)}).join('')+'<button type="button" class="tab more" data-more="1">전체 업종 <svg viewBox="0 0 24 24"><path d="M6 9l6 6 6-6"/></svg></button>';
    }else{ /* 데스크톱: 정해진 순서로 전부 */
      h=tabBtn('전체')+ORDER.map(function(o){return tabBtn(o.s)}).join('');
    }
    tabsEl.querySelectorAll('.tab').forEach(function(b){b.remove()});tabsEl.insertAdjacentHTML('afterbegin',h); window.kosInd(tabsEl,'x')(true);
  }
  /* 업종 고르기 시트 — 하나를 누르면 바로 닫힌다(적용 단추 없음) */
  var sheet=document.getElementById('sectorSheet'),back=document.getElementById('sectorBack'),sbody=document.getElementById('sectorBody');
  function sBtn(s){return '<button type="button"'+(s===active?' class="on"':'')+' data-s="'+esc(s)+'">'+esc(s)+'</button>'}
  function renderSheet(){var by={};ORDER.forEach(function(o){(by[o.g]=by[o.g]||[]).push(o.s)});
    sbody.innerHTML='<div class="sg top"><div class="sw">'+sBtn('전체')+'</div></div>'+GROUPS.map(function(g){var ws=by[g[0]]||[];return ws.length?'<div class="sg"><h4>'+esc(g[0])+'</h4><div class="sw">'+ws.map(sBtn).join('')+'</div></div>':''}).join('')}
  function openSheet(){renderSheet();sheet.classList.add('open');back.classList.add('open');document.documentElement.style.overflow='hidden'}  /* html 에 — body 에 걸면 sticky 헤더가 사라진다 */
  function closeSheet(){sheet.classList.remove('open');back.classList.remove('open');document.documentElement.style.overflow=''}
  document.getElementById('sectorClose').addEventListener('click',closeSheet);back.addEventListener('click',closeSheet);
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&sheet.classList.contains('open'))closeSheet()});
  sbody.addEventListener('click',function(e){var b=e.target.closest('button[data-s]');if(!b)return;active=b.dataset.s;closeSheet();renderTabs();renderMovers();tabsEl.scrollLeft=0});
  (mq.addEventListener?mq.addEventListener('change',renderTabs):mq.addListener(renderTabs));
  function renderMovers(){
    var list=(active==='전체'?MOVERS:MOVERS.filter(function(m){return mcats(m).indexOf(active)>=0})).slice(0,12);
    body.innerHTML=list.length?list.map(function(m,i){var c=m.change||0;
      return '<tr data-tk="'+m.ticker+'"><td><span class="m-rank">'+(i+1)+'</span><a class="m-name" href="/stock.html?ticker='+m.ticker+'">'+esc(m.name)+'</a><div class="m-meta">'+m.ticker+' · '+esc(m.sector)+'</div></td>'
        +'<td>'+fmt.won(m.price)+'</td><td class="'+fmt.dir(c)+'">'+fmt.chg(c)+'</td><td>'+fmt.amt(m.trading_value)+'</td><td>'+fmt.mcap(m.mcap)+'</td></tr>'}).join('')
      :'<tr><td colspan="5" class="empty-td">해당 업종 종목이 없습니다.</td></tr>';
    document.getElementById('moverNote').textContent=(active==='전체'?'전체':active)+' · 거래대금 순 상위 '+list.length+'종목'+(dateF?' · '+dateF+' 종가 기준':'');
  }
  tabsEl.addEventListener('click',function(e){var b=e.target.closest('.tab');if(!b)return;if(b.dataset.more){openSheet();return}active=b.dataset.s;renderTabs();renderMovers()});
  body.addEventListener('click',function(e){var tr=e.target.closest('tr[data-tk]');if(!tr||e.target.closest('a'))return;location.href='/stock.html?ticker='+tr.dataset.tk});

  /* ---- 검색 · 자동완성 · 최근 본 종목 (Home.html 의 규칙 그대로) ---- */
  var INDEX=[],seen={}; live.forEach(function(s){if(seen[s.ticker])return;seen[s.ticker]=1;INDEX.push({ticker:s.ticker,name:s.name,sector:s.sector||''})});
  function search(q){var t=q.trim().toLowerCase();if(!t)return[];
    return INDEX.map(function(s){var nm=s.name.toLowerCase(),sc=-1;
      if(nm.indexOf(t)===0)sc=0;else if(s.ticker.indexOf(t)===0)sc=1;else if(nm.indexOf(t)>=0)sc=2;else if(s.ticker.indexOf(t)>=0)sc=3;else if(s.sector.toLowerCase().indexOf(t)>=0)sc=4;
      return {s:s,sc:sc}}).filter(function(x){return x.sc>=0}).sort(function(a,b){return a.sc-b.sc||a.s.name.localeCompare(b.s.name,'ko')}).slice(0,8).map(function(x){return x.s})}
  function hl(name,q){var t=q.trim();if(!t)return esc(name);var i=name.toLowerCase().indexOf(t.toLowerCase());if(i<0)return esc(name);return esc(name.slice(0,i))+'<mark>'+esc(name.slice(i,i+t.length))+'</mark>'+esc(name.slice(i+t.length))}
  var input=document.getElementById('searchInput'),ac=document.getElementById('acList'),items=[],act=-1,RKEY='kos-recent';
  function getRecent(){try{return JSON.parse(localStorage.getItem(RKEY)||'[]').filter(function(x){return x&&x.t})}catch(e){return[]}}
  function setRecent(a){try{localStorage.setItem(RKEY,JSON.stringify(a))}catch(e){}}
  function open(){ac.classList.add('show');input.setAttribute('aria-expanded','true')}
  function closeAC(){ac.classList.remove('show');input.setAttribute('aria-expanded','false');act=-1}
  function renderRecent(){var rec=getRecent();if(!rec.length){closeAC();return}items=rec.map(function(x){return{ticker:x.t,name:x.n}});act=-1;
    ac.innerHTML='<div class="ac-head"><span>최근 본 종목</span><button type="button" id="acClear">전체 삭제</button></div>'+rec.map(function(x,i){return '<div class="ac-item ac-recent" data-i="'+i+'" data-tk="'+esc(x.t)+'" role="option"><span class="ac-tk">'+esc(x.t)+'</span><span class="ac-nm">'+esc(x.n)+'</span><button type="button" class="ac-x" data-tk="'+esc(x.t)+'" aria-label="삭제">×</button></div>'}).join('');open()}
  function renderAC(){var q=input.value;if(!q.trim()){renderRecent();return}items=search(q);act=-1;
    ac.innerHTML=items.length?items.map(function(s,i){return '<a class="ac-item" href="/stock.html?ticker='+s.ticker+'" data-i="'+i+'" role="option"><span class="ac-tk">'+s.ticker+'</span><span class="ac-nm">'+hl(s.name,q)+'</span><span class="ac-sec">'+esc(s.sector)+'</span></a>'}).join('')
      :'<div class="ac-empty">“'+esc(q.trim())+'” 검색 결과가 없습니다</div>';open()}
  function goStock(tk){try{input.blur()}catch(e){}location.href='/stock.html?ticker='+tk}
  function setActive(n){var els=ac.querySelectorAll('.ac-item');if(!els.length)return;act=(n+els.length)%els.length;els.forEach(function(el,i){el.classList.toggle('active',i===act)});els[act].scrollIntoView({block:'nearest'})}
  input.addEventListener('input',function(){renderReports(input.value);renderAC()});
  input.addEventListener('focus',function(){input.value.trim()?renderAC():renderRecent()});
  ac.addEventListener('click',function(e){var x=e.target.closest('.ac-x');if(x){e.preventDefault();e.stopPropagation();setRecent(getRecent().filter(function(r){return r.t!==x.dataset.tk}));renderRecent();return}
    if(e.target.closest('#acClear')){e.preventDefault();setRecent([]);closeAC();return}var row=e.target.closest('.ac-recent');if(row)goStock(row.dataset.tk)});
  input.addEventListener('keydown',function(e){var composing=e.isComposing||e.keyCode===229;
    if(e.key==='Enter'){if(!composing)e.preventDefault();var pick=(act>=0&&items[act])?items[act]:search(input.value)[0];if(pick)goStock(pick.ticker);else if(input.value.trim())document.getElementById('searchBtn').click();return}
    if(composing&&e.key!=='Escape')return;if(!ac.classList.contains('show'))return;
    if(e.key==='ArrowDown'){e.preventDefault();setActive(act+1)}else if(e.key==='ArrowUp'){e.preventDefault();setActive(act-1)}else if(e.key==='Escape')closeAC()});
  document.addEventListener('click',function(e){if(!e.target.closest('.search-wrap'))closeAC()});
  window.addEventListener('pageshow',function(e){if(e.persisted){try{input.blur()}catch(_){}closeAC()}});
  document.getElementById('searchBtn').addEventListener('click',function(){renderReports(input.value);closeAC();document.getElementById('reports').scrollIntoView({behavior:'smooth',block:'start'})});

  renderReports('');renderTabs();renderMovers();
})();
'''


def build(out_path):
    html = (C.head('홈 — 디자인 시안 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('홈') + '\n' + BODY + '\n' + C.FOOTER + '\n'
            + '<script src="/data/stocks.js"></script>\n<script src="/data/reports-index.js"></script>\n<script>\n' + JS + C.JS + '\n</script>\n</body>\n</html>')
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'✅ {out_path} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'preview/home.html'))
