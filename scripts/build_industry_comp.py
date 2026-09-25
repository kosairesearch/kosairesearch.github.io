#!/usr/bin/env python3
"""업종 분석(industry.html) — 새 디자인 시안(comp). 리포트·홈 시안과 같은 부품(comp_common)을 쓴다.

    python3 scripts/build_industry_comp.py [출력 경로]    # 기본 preview/industry.html

industry.html 의 기능은 그대로: 목록(대표 업종 29개 · 테마 2개 · 시가총액순 · 시장 비중 · 종목 수 · 시가총액 가중 등락률 · 주요 종목),
상세(?sector=…: 지표 4개 · AI 업종 분석 다섯 절 · 리스크 · 작성일 · 업종 내 주요 종목 시가총액순 20). '기타' 는 분류 안내, 분석 없는
업종은 안내 한 줄. 데이터는 실사이트와 같은 /data/stocks.js · /data/sectors.js · /data/reports-index.js 를 그 자리에서 읽는다.
한/영 전환·로그인 상태·SEO 메타는 시안에서는 뺐다 — 옮길 때 붙인다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
/* 눈썹줄 · 제목 */
.hero{padding:44px 0 0}
.crumb{font:500 13px/20px var(--font);color:var(--ink-55);display:flex;gap:8px;align-items:center} .crumb a:hover{color:var(--ink)}
.crumb svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;color:var(--ink-30)}
.hero h1{margin:12px 0 0;font:700 44px/52px var(--font);letter-spacing:-.025em}
.hero .sub{margin:16px 0 0;font:400 17px/28px var(--font);color:var(--ink-72);max-width:640px}
.hero .lead{margin:18px 0 0;font:400 18px/30px var(--font);color:var(--ink-72);max-width:720px}
/* 지표 띠 — 리포트 페이지와 같은 문법 */
.stats{margin-top:36px;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:22px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.st-k{font:500 12px/16px var(--font);color:var(--ink-55)} .st-v{margin-top:6px;font:600 19px/24px var(--font);letter-spacing:-.01em;white-space:nowrap}
.stats-note{margin:10px 0 0;font:400 12px/16px var(--font);color:var(--ink-55)}
/* 업종 표(목록) */
.list{padding-top:48px} .list .sec-h{margin-bottom:14px}
.tbl.sectors th:first-child,.tbl.sectors td:first-child{min-width:150px}
.tbl.sectors td{padding-top:13px;padding-bottom:13px}
.s-name{font:600 15px/20px var(--font)}
.tbl.sectors td.w{text-align:left;white-space:nowrap;min-width:190px} .wb{display:inline-block;width:calc(var(--w) * 120px);min-width:2px;height:3px;background:var(--ink);vertical-align:middle;margin-right:10px}
.tbl.sectors td.keys,.tbl.sectors th.keys{text-align:left;white-space:normal;font-size:13px;color:var(--ink-55)}
.tbl.sectors tbody tr{cursor:pointer} .tbl.sectors tbody tr:hover .s-name{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}
.note{margin:14px 0 0;font:400 12px/18px var(--font);color:var(--ink-55)}
/* 본문 절 */
.prose p{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em} .prose p:last-child{margin-bottom:0}
.rks{border-top:1px solid var(--line)} .rk{padding:20px 0 18px;border-bottom:1px solid var(--hair)} .rk h4{margin:0 0 8px;font:600 16px/24px var(--font)} .rk p{margin:0;font:400 15px/24px var(--font);color:var(--ink-72)}
.stamp{margin:24px 0 0;font:400 12px/18px var(--font);color:var(--ink-55)}
.srcmore summary{margin-top:10px;font:500 13px/20px var(--font);color:var(--ink-55);cursor:pointer;list-style:none}
.srcs{margin:8px 0 0;padding:0 0 0 22px;display:grid;gap:8px} .srcs li{font:400 14px/20px var(--font);color:var(--ink-55)} .srcs a{color:var(--ink-72);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px} .srcs a:hover{color:var(--ink)}
.ainote{margin:0;font:400 15px/24px var(--font);color:var(--ink-55)}
/* 업종 내 주요 종목 표 */
.tbl.stocks th:first-child,.tbl.stocks td:first-child{white-space:normal;min-width:170px}
.tbl.stocks td{padding-top:12px;padding-bottom:12px}
.tbl.stocks tbody tr{cursor:pointer} .tbl.stocks tbody tr:hover .m-name{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}
.m-rank{display:inline-block;width:24px;font:500 12px/16px var(--font);color:var(--ink-30)}
.m-name{font:500 14px/20px var(--font)} .m-meta{margin:2px 0 0 24px;font:400 12px/16px var(--font);color:var(--ink-55)}
.tbl.stocks td.rt,.tbl.stocks th.rt{text-align:left;white-space:normal;color:var(--ink-72);max-width:320px}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .hero{padding:20px 0 0} .hero h1{font-size:32px;line-height:38px} .hero .sub,.hero .lead{font-size:15px;line-height:24px}
  .stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 12px;padding:18px 0;margin-top:24px} .st-v{font-size:17px}
  .list{padding-top:32px}
  .tbl.sectors td.w{min-width:120px} .wb{width:calc(var(--w) * 56px);margin-right:8px}
  .tbl.sectors .keys,.tbl.stocks .rt{display:none}
  .prose p{font-size:16px;line-height:27px}
}'''

JS = r'''(function(){
  var STOCKS=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[], SECTORS=(window.KOS_SECTORS&&KOS_SECTORS.sectors)||{}, RREP=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
  var dd=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.dataDate)||''; var dateF=dd?dd.slice(0,4)+'-'+dd.slice(4,6)+'-'+dd.slice(6,8):'';
  function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
  function won(n){return n==null?'—':Number(n).toLocaleString('ko-KR')+'원'}
  function chg(c){c=c||0;return (c>0?'▲ ':c<0?'▼ ':'')+Math.abs(c).toFixed(2)+'%'}
  function dir(c){return c>0?'up':c<0?'down':'flat'}
  function mcap(j){j=j||0;if(j>=1)return j.toLocaleString('en-US',{maximumFractionDigits:1})+'조';return Math.round(j*10000).toLocaleString('ko-KR')+'억'}
  function fmtDay(s){var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(s||'');return m?(+m[1])+'년 '+(+m[2])+'월 '+(+m[3])+'일':''}
  function host(u){return String(u).replace(/^https?:\/\//,'').replace(/^www\./,'').split('/')[0]}
  /* 문단 나누기 — industry.html 과 같은 규칙(빈 줄로만 나누고, 긴 덩어리는 문장 경계에서 280자 안팎으로) */
  function sents(t){var out=[],last=0,re=/[.!?](?=\s)/g,m;while((m=re.exec(t))){out.push(t.slice(last,m.index+1));last=m.index+1}if(last<t.length)out.push(t.slice(last));return out.map(function(s){return s.replace(/^\s+/,'')}).filter(Boolean)}
  function chunk(t){t=t.trim();if(t.length<=320)return[t];var ss=sents(t);if(ss.length<2)return[t];var n=Math.max(2,Math.round(t.length/280)),target=t.length/n,out=[],cur='';
    ss.forEach(function(s){if(cur&&cur.length+s.length>target*1.35){out.push(cur);cur=s}else cur=cur?cur+' '+s:s});if(cur)out.push(cur);
    for(var i=out.length-1;i>0;i--)if(out[i].length<100){out[i-1]+=' '+out[i];out.splice(i,1)}if(out.length>1&&out[0].length<100){out[1]=out[0]+' '+out[1];out.shift()}return out}
  function paras(o){var t=o&&(o.ko||o.en)||'';if(!t)return '';var out=[];String(t).split(/\n\n+/).forEach(function(b){out=out.concat(chunk(b.replace(/\s*\n\s*/g,' ')))});return '<div class="prose">'+out.map(function(x){return '<p>'+esc(x)+'</p>'}).join('')+'</div>'}
  /* 집계 — industry.html 과 같은 규칙: 대표 업종(sector) 하나로 나눠 비중 합이 100%, 테마(로봇·AI)는 categories 로 따로 */
  function scats(s){return (s.categories&&s.categories.length)?s.categories:[s.sector||'기타']}
  function mkRow(sec,lst,total){var mc=0,wc=0;lst.forEach(function(s){mc+=(s.mcap||0);wc+=(s.change||0)*(s.mcap||0)});lst=lst.slice().sort(function(a,b){return (b.mcap||0)-(a.mcap||0)});return {sec:sec,n:lst.length,mc:mc,w:total?mc/total*100:0,chg:mc?wc/mc:0,list:lst}}
  function agg(){var total=0,byRep={},byCat={};STOCKS.forEach(function(s){var m=s.mcap||0;total+=m;var rep=s.sector||'기타';(byRep[rep]=byRep[rep]||[]).push(s);scats(s).forEach(function(c){(byCat[c]=byCat[c]||[]).push(s)})});
    var rows=Object.keys(byRep).map(function(sec){return mkRow(sec,byRep[sec],total)}).sort(function(a,b){return b.mc-a.mc});
    var themeRows=Object.keys(byCat).filter(function(c){return byRep[c]==null}).map(function(sec){return mkRow(sec,byCat[sec],total)}).sort(function(a,b){return b.mc-a.mc});
    return {rows:rows,themeRows:themeRows,total:total,byCat:byCat}}
  var app=document.getElementById('app');
  function secLink(sec){return '/preview/industry.html?sector='+encodeURIComponent(sec)}
  function sectorTable(rows,withW){var maxW=0;rows.forEach(function(r){if(r.w>maxW)maxW=r.w});
    return '<div class="tbl-wrap"><table class="tbl sectors"><thead><tr><th>'+(withW?'업종':'테마')+'</th><th>시가총액</th>'+(withW?'<th style="text-align:left">시장 비중</th>':'')+'<th>종목 수</th><th>평균 등락률</th><th class="keys">주요 종목</th></tr></thead><tbody>'
      +rows.map(function(r){return '<tr data-sec="'+esc(r.sec)+'"><td><a class="s-name" href="'+secLink(r.sec)+'">'+esc(r.sec)+'</a></td><td>'+mcap(r.mc)+'</td>'
        +(withW?'<td class="w"><i class="wb" style="--w:'+(r.w/maxW).toFixed(3)+'"></i>'+r.w.toFixed(1)+'%</td>':'')
        +'<td>'+r.n+'</td><td class="'+dir(r.chg)+'">'+chg(r.chg)+'</td><td class="keys">'+r.list.slice(0,3).map(function(s){return esc(s.name)}).join(' · ')+'</td></tr>'}).join('')+'</tbody></table></div>'}
  function renderList(){var a=agg();document.title='업종 분석 — 디자인 시안 | KOSAI';
    app.innerHTML='<header class="hero"><p class="crumb">코스피 · 코스닥 '+STOCKS.length.toLocaleString('ko-KR')+'개 종목 · '+a.rows.length+'개 업종 · '+a.themeRows.length+'개 테마</p><h1>업종 분석</h1><p class="sub">한국 상장사를 업종으로 나눠 시가총액·등락률과 AI 업종 분석을 제공합니다.</p></header>'
      +'<section class="list"><div class="sec-h"><h2>업종</h2></div>'+sectorTable(a.rows,true)+'<p class="note">시가총액 순 · 시장 비중은 코스피·코스닥 전체 시가총액 대비 · 평균 등락률은 시가총액 가중'+(dateF?' · '+dateF+' 종가 기준':'')+'</p></section>'
      +(a.themeRows.length?'<section class="list"><div class="sec-h"><h2>테마</h2></div>'+sectorTable(a.themeRows,false)+'<p class="note">테마는 여러 업종에 걸친 묶음이라 시장 비중을 따로 두지 않습니다.</p></section>':'')}
  function renderDetail(sec){var a=agg(),row=null;a.rows.forEach(function(r){if(r.sec===sec)row=r});var isTheme=!row;if(!row&&a.byCat[sec])row=mkRow(sec,a.byCat[sec],a.total);if(!row){renderList();return}
    var an=SECTORS[sec]||null;document.title=sec+' 업종 분석 — 디자인 시안 | KOSAI';
    var stats='<section class="stats"><div><div class="st-k">시가총액 합계</div><div class="st-v">'+mcap(row.mc)+'</div></div>'+(isTheme?'':'<div><div class="st-k">시장 비중</div><div class="st-v">'+row.w.toFixed(1)+'%</div></div>')
      +'<div><div class="st-k">종목 수</div><div class="st-v">'+row.n+'개</div></div><div><div class="st-k">평균 등락률</div><div class="st-v '+dir(row.chg)+'">'+chg(row.chg)+'</div></div></section>'
      +'<p class="stats-note">평균 등락률은 시가총액 가중'+(isTheme?' · 테마는 여러 업종에 걸쳐 있어 시장 비중을 두지 않습니다':'')+(dateF?' · '+dateF+' 종가 기준':'')+'</p>';
    var secs=[]; // {title, html, wide}
    if(an){secs.push({t:'업종 개요',h:paras(an.overview)});secs.push({t:'산업 구조·가치사슬',h:paras(an.structure)});secs.push({t:'최근 동향',h:paras(an.trends)});secs.push({t:'향후 전망',h:paras(an.outlook)});
      var risks=(an.risks||[]).map(function(r){return '<div class="rk"><h4>'+esc(r.title&&r.title.ko)+'</h4><p>'+esc(r.body&&r.body.ko)+'</p></div>'}).join('');
      var d=fmtDay(an.generatedAt||(window.KOS_SECTORS&&KOS_SECTORS.lastUpdated)),src=an.sources||[];
      var tail=(d?'<p class="stamp">'+d+' 작성 · 업종 상장사 종합과 웹 검색 참고 · 본문 수치는 작성 시점 기준이며, 위 지표는 '+(dateF||'최근')+' 종가입니다.</p>':'')
        +(src.length?'<details class="srcmore"><summary>참고 자료 '+src.length+'건 더 보기</summary><ol class="srcs">'+src.map(function(u){return '<li><a href="'+esc(u)+'" target="_blank" rel="noopener">'+esc(host(u))+'</a></li>'}).join('')+'</ol></details>':'');
      if(risks)secs.push({t:'리스크 요인',h:'<div class="rks">'+risks+'</div>'+tail});else if(tail)secs[secs.length-1].h+=tail}
    else if(sec==='기타'){secs.push({t:'분류 안내',h:'<div class="prose"><p>여러 업종에 걸쳐 있거나 기존 분류에 속하지 않는 기업을 모은 구간입니다. 사업 내용이 서로 달라 하나의 업황으로 묶이지 않으므로 AI 업종 분석을 제공하지 않습니다.</p><p>각 기업의 사업 구조와 실적은 아래 종목의 개별 리포트에서 확인하실 수 있습니다.</p></div>'})}
    else{secs.push({t:'업종 분석',h:'<p class="ainote">AI 업종 분석은 분기별 갱신 시 반영됩니다.</p>'})}
    var rows=row.list.slice(0,20).map(function(s,i){var c=s.change||0,r=RREP[s.ticker];return '<tr data-tk="'+s.ticker+'"><td><span class="m-rank">'+(i+1)+'</span><a class="m-name" href="/stock.html?ticker='+s.ticker+'">'+esc(s.name)+'</a><div class="m-meta">'+s.ticker+' · '+esc(s.market)+'</div></td><td>'+won(s.price)+'</td><td class="'+dir(c)+'">'+chg(c)+'</td><td>'+mcap(s.mcap)+'</td><td class="rt">'+esc(r&&r.title&&r.title.ko||'')+'</td></tr>'}).join('');
    secs.push({t:'업종 내 주요 종목',wide:true,h:'<div class="tbl-wrap"><table class="tbl stocks"><thead><tr><th>종목</th><th>현재가</th><th>등락률</th><th>시가총액</th><th class="rt">리포트</th></tr></thead><tbody>'+rows+'</tbody></table></div><p class="note">시가총액 순 상위 '+Math.min(20,row.list.length)+'종목'+(row.list.length>20?' (전체 '+row.list.length+'종목)':'')+(dateF?' · '+dateF+' 종가 기준':'')+'</p>'});
    var toc=secs.map(function(s,i){var n=String(i+1).padStart(2,'0');return '<a href="#s'+n+'"><span class="n">'+n+'</span>'+esc(s.t)+'</a>'}).join('');
    var chips=secs.map(function(s,i){var n=String(i+1).padStart(2,'0');return '<a href="#s'+n+'">'+n+' '+esc(s.t)+'</a>'}).join('');
    var body=secs.map(function(s,i){var n=String(i+1).padStart(2,'0');return '<section class="sec'+(s.wide?' wide':'')+'" id="s'+n+'"><div class="sec-h"><span class="num">'+n+'</span><h2>'+esc(s.t)+'</h2></div>'+s.h+'</section>'}).join('');
    app.innerHTML='<header class="hero"><p class="crumb"><a href="/preview/industry.html">업종 분석</a><svg viewBox="0 0 24 24"><path d="M9 6l6 6-6 6"/></svg><span>'+esc(sec)+'</span></p><h1>'+esc(sec)+'</h1>'+(an&&an.lead?'<p class="lead">'+esc(an.lead.ko||an.lead.en)+'</p>':'')+'</header>'+stats
      +'<div class="body"><aside class="toc" id="toc">'+toc+'</aside><div class="content"><div class="chips-mark" id="chipsMark"></div><div class="chips-bar" id="chipsBar"><nav class="chips" id="chips">'+chips+'</nav></div>'+body+'</div></div>';
  }
  app.addEventListener('click',function(e){if(e.target.closest('a'))return;var tr=e.target.closest('tr[data-sec]');if(tr){location.href=secLink(tr.dataset.sec);return}var tk=e.target.closest('tr[data-tk]');if(tk)location.href='/stock.html?ticker='+tk.dataset.tk});
  var q=new URLSearchParams(location.search).get('sector');if(q)renderDetail(q);else renderList();
})();
'''


def build(out_path):
    html = (C.head('업종 분석 — 디자인 시안 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.TOC_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + C.TOC_MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('업종 분석') + '\n<main class="wrap" id="app"></main>\n' + C.FOOTER + '\n'
            + '<script src="/data/stocks.js"></script>\n<script src="/data/sectors.js"></script>\n<script src="/data/reports-index.js"></script>\n<script>\n' + JS + C.TOC_JS + '\n' + C.JS + '\n</script>\n</body>\n</html>')
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'✅ {out_path} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'preview/industry.html'))
