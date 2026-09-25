#!/usr/bin/env python3
"""홈(Home.html) — 새 디자인 시안(comp). 리포트 시안(build_stock_comp.py)과 같은 부품(comp_common)을 쓴다.

    python3 scripts/build_home_comp.py [출력 경로]    # 기본 preview/home.html

Home.html 의 기능은 그대로: 검색(자동완성·최근 본 종목·화살표·엔터), 최신 리포트 6편(검색어로 거름),
업종 탭(대표+테마 · 10개 넘으면 더보기) 아래 거래대금 순 종목 표. 데이터는 실사이트와 같은
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
/* 업종 탭 — 밑줄 탭 */
.tabs{display:flex;gap:22px;height:44px;overflow-x:auto;overflow-y:hidden;scrollbar-width:none;border-bottom:1px solid var(--hair);margin-bottom:10px;touch-action:pan-x;overscroll-behavior-x:contain} .tabs::-webkit-scrollbar{display:none}
.tabs.all{flex-wrap:wrap;height:auto}
.tab{flex:none;position:relative;border:0;background:none;padding:0;font:500 13px/44px var(--font);color:var(--ink-55);cursor:pointer;white-space:nowrap;transition:color .12s} .tab:hover{color:var(--ink)} .tab.on{color:var(--ink);font-weight:600}
.tab.on::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--ink)}
.tab.more{color:var(--ink-30)}
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
  .eb-date{display:none}
  .row{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"name price" "title title";gap:8px 12px;padding:14px 0;align-items:start}
  .row>div:first-child{grid-area:name} .r-title{grid-area:title;font-size:15px;line-height:22px;color:var(--ink-72)} .r-price{grid-area:price}
  .r-date{display:none} .r-meta .md{display:inline}
  .r-price{font-size:15px;line-height:22px} .r-price .c{display:block;margin:2px 0 0}
  .tbl.movers th:first-child,.tbl.movers td:first-child{min-width:150px}
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
</main>'''

JS = r'''(function(){
  var live=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[], RREP=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
  var dd=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.dataDate)||''; var dateF=dd?dd.slice(0,4)+'-'+dd.slice(4,6)+'-'+dd.slice(6,8):'';
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  var fmt={won:function(n){return n==null?'—':n.toLocaleString('ko-KR')+'원'},
    chg:function(c){c=c||0;return (c>0?'▲ ':c<0?'▼ ':'')+Math.abs(c).toFixed(2)+'%'},
    dir:function(c){return c>0?'up':c<0?'down':'flat'},
    mcap:function(n){return !n?'—':(n>=1?(+n).toLocaleString('en-US',{maximumFractionDigits:1})+'조':Math.round(n*10000).toLocaleString('ko-KR')+'억')},
    amt:function(n){return !n?'—':(n>=1e12?(n/1e12).toFixed(1)+'조':Math.round(n/1e8).toLocaleString('ko-KR')+'억')}};
  var nRep=Object.keys(RREP).length;
  document.getElementById('eyebrow').innerHTML='코스피 · 코스닥 '+live.length.toLocaleString('ko-KR')+'개 종목 · 리포트 '+nRep.toLocaleString('ko-KR')+'편'+(dateF?'<span class="eb-date"> · 시세 '+dateF+' 장마감</span>':'');

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
  var TABS=['전체']; MOVERS.forEach(function(m){mcats(m).forEach(function(c){if(c&&TABS.indexOf(c)<0)TABS.push(c)})});
  var LIMIT=10,expanded=false,active='전체';
  var tabsEl=document.getElementById('tabs'),body=document.getElementById('moverBody');
  function renderTabs(){
    var shown=expanded?TABS:TABS.slice(0,LIMIT);
    var h=shown.map(function(s){return '<button type="button" class="tab'+(s===active?' on':'')+'" data-s="'+esc(s)+'">'+esc(s)+'</button>'}).join('');
    if(TABS.length>LIMIT)h+='<button type="button" class="tab more" data-more="1">'+(expanded?'접기':'+'+(TABS.length-LIMIT)+' 더보기')+'</button>';
    tabsEl.innerHTML=h; tabsEl.classList.toggle('all',expanded);
  }
  function renderMovers(){
    var list=(active==='전체'?MOVERS:MOVERS.filter(function(m){return mcats(m).indexOf(active)>=0})).slice(0,12);
    body.innerHTML=list.length?list.map(function(m,i){var c=m.change||0;
      return '<tr data-tk="'+m.ticker+'"><td><span class="m-rank">'+(i+1)+'</span><a class="m-name" href="/stock.html?ticker='+m.ticker+'">'+esc(m.name)+'</a><div class="m-meta">'+m.ticker+' · '+esc(m.sector)+'</div></td>'
        +'<td>'+fmt.won(m.price)+'</td><td class="'+fmt.dir(c)+'">'+fmt.chg(c)+'</td><td>'+fmt.amt(m.trading_value)+'</td><td>'+fmt.mcap(m.mcap)+'</td></tr>'}).join('')
      :'<tr><td colspan="5" class="empty-td">해당 업종 종목이 없습니다.</td></tr>';
    document.getElementById('moverNote').textContent=(active==='전체'?'전체':active)+' · 거래대금 순 상위 '+list.length+'종목'+(dateF?' · 시세 '+dateF+' 장마감':'');
  }
  tabsEl.addEventListener('click',function(e){var b=e.target.closest('.tab');if(!b)return;if(b.dataset.more){expanded=!expanded;renderTabs();return}active=b.dataset.s;renderTabs();renderMovers()});
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
