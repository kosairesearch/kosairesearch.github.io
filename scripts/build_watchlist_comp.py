#!/usr/bin/env python3
"""관심종목(Watchlist.html) — 새 디자인 시안(comp). 리포트·홈·업종 시안과 같은 부품(comp_common)을 쓴다.

    python3 scripts/build_watchlist_comp.py [출력 경로]    # 기본 preview/watchlist.html

Watchlist.html 의 기능은 그대로: 종목 수 · 정렬 여섯 가지 · 편집(줄마다 빼기 · 전체 삭제) · 10개씩 쪽 넘기기 · 빈 목록 안내.
실사이트는 로그인한 계정의 목록(Firestore)을 쓰지만 시안은 로그인이 없으므로 예시 6종목으로 그린다.
  ?demo=25  거래대금 상위 25종목으로 쪽 넘기기까지 본다      ?empty=1  빈 목록 화면
빼기·전체 삭제는 화면 안에서만 동작한다(새로고침하면 돌아온다). 한/영 전환·로그인 게이트는 옮길 때 붙인다.
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
/* 정렬 · 편집 줄 */
.bar{margin-top:36px;display:flex;align-items:center;gap:24px;border-bottom:1px solid var(--hair)}
.sorts{position:relative;display:flex;gap:20px;align-items:center;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0} .sorts::-webkit-scrollbar{display:none}
.sorts .lbl{font:500 12px/44px var(--font);color:var(--ink-30);flex:none;margin-right:2px}
.sorts button{flex:none;position:relative;border:0;background:none;padding:0;font:500 13px/44px var(--font);color:var(--ink-55);cursor:pointer;white-space:nowrap;transition:color .12s}
.sorts button:hover{color:var(--ink)} .sorts button.on{color:var(--ink);font-weight:600}
.sortsel{display:none}
.acts{display:flex;gap:18px;flex:none}
.tbtn{border:0;background:none;padding:0;font:500 13px/44px var(--font);color:var(--ink-72);cursor:pointer;transition:color .12s} .tbtn:hover{color:var(--ink)} .tbtn.on{color:var(--ink);font-weight:600} .tbtn.danger{color:var(--up)}
/* 줄 목록 — 홈 최신 리포트와 같은 줄 */
.row{display:grid;grid-template-columns:36px 200px minmax(0,1fr) 170px 96px;gap:0 20px;align-items:center;padding:16px 0;border-bottom:1px solid var(--hair)}
.rows.edit .row{grid-template-columns:28px 36px 200px minmax(0,1fr) 170px 96px}
.rm{width:24px;height:24px;border-radius:50%;border:1px solid var(--line);background:transparent;color:var(--ink-72);display:none;align-items:center;justify-content:center;cursor:pointer;padding:0} .rows.edit .rm{display:inline-flex} .rm:hover{border-color:var(--up);color:var(--up)}
.rm svg{width:12px;height:12px;stroke:currentColor;stroke-width:2.2;fill:none;stroke-linecap:round}
.rk{font:500 12px/16px var(--font);color:var(--ink-30)}
.r-name{font:600 16px/22px var(--font)} .r-meta{margin-top:3px;font:400 12px/16px var(--font);color:var(--ink-55)} .r-meta .md{display:none}
.r-title{font:400 16px/24px var(--font)} .r-title.none{color:var(--ink-30)}
.row:hover .r-title{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.r-price{text-align:right;font:500 16px/22px var(--font);white-space:nowrap} .r-price .c{margin-left:8px;font:600 13px/18px var(--font)}
.r-date{text-align:right;font:400 13px/18px var(--font);color:var(--ink-55)}
/* 쪽 넘기기 */
.pager{display:flex;justify-content:space-between;align-items:center;margin-top:18px;font:400 13px/20px var(--font);color:var(--ink-55)}
.pctl{position:relative;display:flex;gap:2px} .pctl>.ind{margin-top:4px} .pctl button{border:0;background:none;min-width:32px;height:32px;padding:0 6px;font:500 13px var(--font);color:var(--ink-55);cursor:pointer}
.pctl button:hover{color:var(--ink)} .pctl button.on{color:var(--ink);font-weight:600} .pctl button:disabled{color:var(--ink-30);cursor:default}
/* 빈 목록 */
.empty{padding:56px 0 24px;max-width:520px} .empty h2{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em} .empty p{margin:12px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .hero{padding:20px 0 0} .hero h1{font-size:32px;line-height:38px} .hero .sub{font-size:15px;line-height:24px}
  .bar{margin-top:24px;gap:12px} .sorts{display:none}
  .sortsel{display:block;flex:1;min-width:0;height:44px;border:0;background:transparent;font:500 14px var(--font);color:var(--ink);padding:0;outline:0}
  .row{grid-template-columns:24px minmax(0,1fr) auto;grid-template-areas:"rk name price" "rk title title";gap:8px 12px;padding:14px 0;align-items:start}
  .rows.edit .row{grid-template-columns:28px 24px minmax(0,1fr) auto;grid-template-areas:"rm rk name price" "rm rk title title"}
  .rm{grid-area:rm;align-self:center} .rk{grid-area:rk;line-height:22px} .row>div:nth-of-type(1){grid-area:name} .r-title{grid-area:title;font-size:15px;line-height:22px;color:var(--ink-72)} .r-price{grid-area:price}
  .r-date{display:none} .r-meta .md{display:inline} .r-meta .md b{font-weight:400;white-space:nowrap}
  .r-price{font-size:15px;line-height:22px} .r-price .c{display:block;margin:2px 0 0}
}'''

BODY = '''<main class="wrap">
  <header class="hero">
    <p class="crumb" id="count">관심종목</p>
    <h1>관심 종목</h1>
    <p class="sub">종목 페이지에서 추가한 종목을 한 줄씩 모아 봅니다. 시안이라 로그인 없이 예시 종목으로 그렸습니다.</p>
  </header>
  <div class="bar">
    <div class="sorts" id="sorts"><span class="lbl">정렬</span>
      <button type="button" data-sort="mcap_desc" class="on">시가총액 높은 순</button><button type="button" data-sort="mcap_asc">시가총액 낮은 순</button><button type="button" data-sort="change_desc">등락률 높은 순</button><button type="button" data-sort="change_asc">등락률 낮은 순</button><button type="button" data-sort="added">추가 순서</button><button type="button" data-sort="name">종목명순</button>
    </div>
    <select class="sortsel" id="sortSelect" aria-label="정렬"><option value="mcap_desc">시가총액 높은 순</option><option value="mcap_asc">시가총액 낮은 순</option><option value="change_desc">등락률 높은 순</option><option value="change_asc">등락률 낮은 순</option><option value="added">추가 순서</option><option value="name">종목명순</option></select>
    <div class="acts"><button type="button" class="tbtn danger" id="clearAll" hidden>전체 삭제</button><button type="button" class="tbtn" id="editBtn">편집</button></div>
  </div>
  <div class="rows" id="rows"></div>
  <div class="pager" id="pager" hidden><span id="pinfo"></span><div class="pctl" id="pctl"></div></div>
  <div class="empty" id="empty" hidden>
    <h2>관심 종목이 비어 있습니다</h2>
    <p>리포트 페이지에서 업종·시가총액·PER 등 조건으로 종목을 찾으시거나, 종목 상세 페이지에서 관심종목에 추가하실 수 있습니다.</p>
    <a class="btn btn-ink" href="/Reports.html">리포트 둘러보기</a>
  </div>
</main>'''

JS = r'''(function(){
  var live=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[], RREP=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function won(n){return n==null?'—':Number(n).toLocaleString('ko-KR')+'원'} function chg(c){c=c||0;return (c>0?'▲ ':c<0?'▼ ':'')+Math.abs(c).toFixed(2)+'%'} function dir(c){return c>0?'up':c<0?'down':'flat'}
  /* 예시 목록 — 실사이트에서는 KOSWatch(Firestore 계정별 목록)가 이 자리를 채운다 */
  var q=new URLSearchParams(location.search),byTk={};live.forEach(function(s){byTk[s.ticker]=s});
  var DEFAULT=['005930','000660','035420','035720','005380','068270'],LIST;
  if(q.get('empty'))LIST=[];
  else if(q.get('demo'))LIST=live.slice().sort(function(a,b){return (b.trading_value||0)-(a.trading_value||0)}).slice(0,Math.max(1,+q.get('demo')||25)).map(function(s,i){return Object.assign({},s,{added:1000-i})});
  else LIST=DEFAULT.map(function(t){return byTk[t]}).filter(Boolean).map(function(s,i){return Object.assign({},s,{added:i})});
  var sortKey='mcap_desc',page=1,PAGE=10,edit=false;
  var rowsEl=document.getElementById('rows'),emptyEl=document.getElementById('empty'),pagerEl=document.getElementById('pager');
  function sorted(){var l=LIST.slice();
    if(sortKey==='change_desc')l.sort(function(a,b){return (b.change||0)-(a.change||0)});else if(sortKey==='change_asc')l.sort(function(a,b){return (a.change||0)-(b.change||0)});
    else if(sortKey==='mcap_desc')l.sort(function(a,b){return (b.mcap||0)-(a.mcap||0)});else if(sortKey==='mcap_asc')l.sort(function(a,b){return (a.mcap||0)-(b.mcap||0)});
    else if(sortKey==='added')l.sort(function(a,b){return b.added-a.added});else if(sortKey==='name')l.sort(function(a,b){return a.name.localeCompare(b.name,'ko')});return l}
  function row(s,i){var r=RREP[s.ticker],t=r&&r.title&&r.title.ko,c=s.change||0;
    return '<a class="row" href="/stock.html?ticker='+s.ticker+'" data-tk="'+s.ticker+'"><button type="button" class="rm" data-rm="'+s.ticker+'" aria-label="제거"><svg viewBox="0 0 24 24"><path d="M5 12h14"/></svg></button><span class="rk">'+(i+1)+'</span>'
      +'<div><div class="r-name">'+esc(s.name)+'</div><div class="r-meta">'+s.ticker+' · '+esc(s.market)+' · '+esc(s.sector)+(r&&r.reportDate?'<span class="md"> · <b>'+esc(r.reportDate)+'</b></span>':'')+'</div></div>'
      +'<div class="r-title'+(t?'':' none')+'">'+(t?esc(t):'리포트 준비 중')+'</div><div class="r-price">'+won(s.price)+'<span class="c '+dir(c)+'">'+chg(c)+'</span></div><div class="r-date">'+esc(r&&r.reportDate||'—')+'</div></a>'}
  function render(){document.getElementById('count').textContent='관심종목 · '+LIST.length+'개 종목';
    if(!LIST.length){rowsEl.innerHTML='';emptyEl.hidden=false;pagerEl.hidden=true;document.querySelector('.bar').hidden=true;return}
    emptyEl.hidden=true;document.querySelector('.bar').hidden=false;
    var list=sorted(),total=list.length,pages=Math.max(1,Math.ceil(total/PAGE));if(page>pages)page=pages;if(page<1)page=1;var start=(page-1)*PAGE;
    rowsEl.innerHTML=list.slice(start,start+PAGE).map(function(s,i){return row(s,start+i)}).join('');rowsEl.classList.toggle('edit',edit);
    if(pages<=1){pagerEl.hidden=true;return}pagerEl.hidden=false;
    document.getElementById('pinfo').textContent=(start+1)+'–'+Math.min(start+PAGE,total)+' / 총 '+total+'개';
    var BLK=matchMedia('(max-width:640px)').matches?5:10,blk=Math.floor((page-1)/BLK),bs=blk*BLK+1,be=Math.min(bs+BLK-1,pages),b='<button type="button" '+(page<=1?'disabled':'')+' data-pg="prev">‹</button>';
    for(var i=bs;i<=be;i++)b+='<button type="button" class="'+(i===page?'on':'')+'" data-pg="'+i+'"><span>'+i+'</span></button>';b+='<button type="button" '+(page>=pages?'disabled':'')+' data-pg="next">›</button>';var pc=document.getElementById('pctl');pc.querySelectorAll('button').forEach(function(x){x.remove()});pc.insertAdjacentHTML('afterbegin',b);window.kosInd(pc,'x','.on>span')(true)}
  function applySort(k){sortKey=k;page=1;document.querySelectorAll('#sorts button').forEach(function(b){b.classList.toggle('on',b.dataset.sort===k)});window.kosInd(document.getElementById('sorts'),'x')();document.getElementById('sortSelect').value=k;render()}
  document.getElementById('sorts').addEventListener('click',function(e){var b=e.target.closest('button');if(b)applySort(b.dataset.sort)});
  window.kosInd(document.getElementById('sorts'),'x');
  document.getElementById('sortSelect').addEventListener('change',function(e){applySort(e.target.value)});
  var editBtn=document.getElementById('editBtn'),clearBtn=document.getElementById('clearAll');
  function setEdit(on){edit=on;editBtn.textContent=on?'완료':'편집';editBtn.classList.toggle('on',on);clearBtn.hidden=!on;rowsEl.classList.toggle('edit',on)}
  editBtn.addEventListener('click',function(){setEdit(!edit)});
  clearBtn.addEventListener('click',function(){if(!confirm('관심 종목을 전체 삭제하시겠습니까?'))return;LIST=[];setEdit(false);page=1;render()});
  rowsEl.addEventListener('click',function(e){var rm=e.target.closest('[data-rm]');if(rm){e.preventDefault();LIST=LIST.filter(function(s){return s.ticker!==rm.dataset.rm});render()}});
  document.getElementById('pctl').addEventListener('click',function(e){var b=e.target.closest('button[data-pg]');if(!b)return;var pg=b.dataset.pg;if(pg==='prev')page=Math.max(1,page-1);else if(pg==='next')page++;else page=+pg;render();window.scrollTo({top:0,behavior:'smooth'})});
  render();
})();
'''


def build(out_path):
    html = (C.head('관심 종목 — 디자인 시안 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('관심종목') + '\n' + BODY + '\n' + C.FOOTER + '\n'
            + '<script src="/data/stocks.js"></script>\n<script src="/data/reports-index.js"></script>\n<script>\n' + JS + C.JS + '\n</script>\n</body>\n</html>')
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'✅ {out_path} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'preview/watchlist.html'))
