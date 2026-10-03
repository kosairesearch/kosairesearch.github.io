window.kosTocInit=function(){
  var nav=document.getElementById('nav'),mark=document.getElementById('chipsMark'),bar=document.getElementById('chipsBar'),mq=window.matchMedia('(max-width:820px)');
  if(!mark||!bar){window.kosOnScroll=null;window.__kosSpy=null;return}
  function pin(){var inNav=bar.parentNode===nav;
    if(!mq.matches){if(inNav){mark.after(bar);mark.style.height=''}return}
    var top=mark.getBoundingClientRect().top-(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--kos-bar-h'))||0);
    if(!inNav&&top<=60){mark.style.height=(bar.offsetHeight+12)+'px';nav.appendChild(bar);void bar.offsetHeight}
    else if(inNav&&top>60){mark.after(bar);mark.style.height='';void bar.offsetHeight}}
  window.kosOnScroll=pin;
  var links=[].slice.call(document.querySelectorAll('#toc a, #chips a')),secs=[].slice.call(document.querySelectorAll('section.sec'));
  var mvT=window.kosInd(document.getElementById('toc'),'y'),mvC=window.kosInd(document.getElementById('chips'),'x');
  // 목차 클릭 — 앵커 이동은 해시마다 방문 기록을 쌓아 뒤로가기가 이전 목차로 간다. 스크롤만 하고 주소는 replaceState 로 바꾼다.
  links.forEach(function(a){if(a.__tocBound)return;a.__tocBound=true;a.addEventListener('click',function(e){var id=(a.getAttribute('href')||'').slice(1),s=id&&document.getElementById(id);if(!s)return;e.preventDefault();
    var pad=parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)||0;var to=s.getBoundingClientRect().top+window.scrollY-pad;e.stopPropagation();if(window.KOSSmoothScroll)window.KOSSmoothScroll.scrollTo(to);else window.scrollTo({top:to,behavior:'smooth'});
    try{history.replaceState(null,'','#'+id)}catch(x){}})});
  function spy(){if(!secs.length)return;var y=window.scrollY+window.innerHeight*.3,cur=secs[0];secs.forEach(function(s){if(s.offsetTop<=y)cur=s});links.forEach(function(a){var on=a.getAttribute('href')==='#'+cur.id;if(on&&!a.classList.contains('on')&&a.parentNode.id==='chips'){a.parentNode.scrollTo({left:Math.max(0,a.offsetLeft-20),behavior:'smooth'})}a.classList.toggle('on',on)});mvT();mvC()}
  if(!window.__kosSpyBound){addEventListener('scroll',function(){if(window.__kosSpy)requestAnimationFrame(window.__kosSpy)},{passive:true});window.__kosSpyBound=true}
  window.__kosSpy=spy;spy();pin();
};
window.kosTocInit();
(function(){
  var nav=document.getElementById('nav'),tick=false;
  function upd(){tick=false;nav.classList.toggle('scrolled',window.scrollY>32);if(window.kosOnScroll)window.kosOnScroll()}
  addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(upd)}},{passive:true});upd();
  var sun='<path d="M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',moon='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();window.__kosPaintTheme=paint;
  document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{localStorage.setItem('kos-theme',t)}catch(e){}paint();});
  /* 휴대폰 메뉴 */
  var mb=document.getElementById('menuBtn'),mm=document.getElementById('mmenu');
  function setMenu(on){nav.classList.toggle('menu-open',on);mm.classList.toggle('open',on);mb.setAttribute('aria-expanded',on?'true':'false');document.documentElement.style.overflow=on?'hidden':'';if(window.KOSSmoothScroll){on?window.KOSSmoothScroll.stop():window.KOSSmoothScroll.start()}}  /* html 에 건다 — body 에 걸면 sticky 헤더가 사라진다(html 이 overflow-x:hidden 이라 body 가 스크롤 상자가 됨) */
  mb.addEventListener('click',function(){setMenu(!nav.classList.contains('menu-open'))});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&nav.classList.contains('menu-open'))setMenu(false)});
  window.matchMedia('(min-width:821px)').addEventListener('change',function(e){if(e.matches)setMenu(false)});
})();
(function(){
function box(e){ var r=e.getBoundingClientRect(); return {l:r.left,r:r.right,t:r.top,b:r.bottom}; }
function mv(b,dx){ return {l:b.l+dx,r:b.r+dx,t:b.t,b:b.b}; }
function fit(ch){
  var labs=[].slice.call(ch.querySelectorAll('.ch-val'));
  ch.style.marginTop=''; ch.style.marginBottom=''; labs.forEach(function(l){ l.style.marginTop=''; l.style.marginLeft=''; });
  var c0=box(ch); if(c0.r-c0.l<1) return;
  var rects=[].slice.call(ch.querySelectorAll('rect')).map(box), obst=rects.concat([].slice.call(ch.querySelectorAll('.ch-lab')).map(box)), lo=c0.t, hi=c0.b;
  function inside(b,dx){ if(b.r+dx>c0.r) dx=c0.r-b.r; if(b.l+dx<c0.l) dx=c0.l-b.l; return dx; }
  function lift(b,up){
    var dy=0, n, k, o, hit;
    for(n=0;n<24;n++){
      hit=null;
      for(k=0;k<obst.length;k++){ o=obst[k]; if(b.l<o.r-.5&&o.l<b.r-.5&&b.t+dy<o.b-.5&&o.t<b.b+dy-.5){ hit=o; break; } }
      if(!hit) break;
      dy=up?hit.t-2-b.b:hit.b+2-b.t;
    }
    return dy;
  }
  labs.map(function(l){ return {el:l, up:!l.classList.contains('dn'), b:box(l)}; })
    .sort(function(a,c){ return a.up!==c.up?(a.up?-1:1):(a.up?a.b.t-c.b.t:c.b.b-a.b.b); })
    .forEach(function(it){
      var b=it.b, dx=inside(b,0), dy=lift(mv(b,dx),it.up), bar, cx, cy;
      /* 막대 왼쪽 끝에서 쓰는 영업이익 라벨(.l)이 비켜야 하면 제 막대 가운데로 옮긴 자리와 견줘, 덜 움직이는 쪽(비슷하면 가운데)을 쓴다 —
         멀리 떠오른 라벨은 제 막대 바로 위에 있어야 어느 막대의 값인지 읽힌다 */
      if(dy&&it.el.classList.contains('l')){
        bar=rects.filter(function(r){ return Math.abs(r.l-b.l)<1.5; })[0];
        if(bar){ cx=inside(b,(bar.r-bar.l)/2-(b.r-b.l)/2); cy=lift(mv(b,cx),it.up); if(Math.abs(cy)<=Math.abs(dy)+4){ dx=cx; dy=cy; } }
      }
      if(dx) it.el.style.marginLeft=dx+'px';
      if(dy) it.el.style.marginTop=dy+'px';
      var f={l:b.l+dx,r:b.r+dx,t:b.t+dy,b:b.b+dy}; obst.push(f); lo=Math.min(lo,f.t); hi=Math.max(hi,f.b);
    });
  var cs=getComputedStyle(ch), mt=parseFloat(cs.marginTop)||0, up=c0.t-lo-mt+4, dn=hi-c0.b;
  if(up>0) ch.style.marginTop=(mt+up)+'px';
  if(dn>0) ch.style.marginBottom=((parseFloat(cs.marginBottom)||0)+dn)+'px';
}
var ro=window.ResizeObserver?new ResizeObserver(function(es){ es.forEach(function(e){ fit(e.target); }); }):null;
window.kosFitCharts=function(){
  if(ro) ro.disconnect();
  [].forEach.call(document.querySelectorAll('.ch'),function(ch){ fit(ch); if(ro) ro.observe(ch); });
};
if(document.fonts&&document.fonts.ready) document.fonts.ready.then(function(){ window.kosFitCharts(); });
window.kosFitCharts();
})();
/* ===== 종목 페이지 — 데이터로 그린다 (stock_page.render 와 같은 DOM) ===== */
(function(){
'use strict';
var DISC="본 콘텐츠는 AI가 시장 데이터와 웹 검색 결과를 분석한 정보 제공용이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 책임은 투자자 본인에게 있습니다. 데이터는 지연되거나 오류가 포함될 수 있습니다.", PRIMARY_SRC=[["한국거래소(KRX) — 시세 · 시가총액 · 거래량", "https://www.krx.co.kr"], ["금융감독원 전자공시(DART) — 재무제표 · 배당 공시", "https://dart.fss.or.kr"]], SECTIONS_V2=["리포트 개요", "사업 구조", "실적 추이", "실적 분석", "산업 분석", "전망", "밸류에이션", "강세 요인", "약세 요인", "리스크 요인", "다음 체크포인트", "종합 의견", "참고 출처"];
var LIVE=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[];
var DATA_DATE=String((window.KOS_LIVE_DATA&&KOS_LIVE_DATA.dataDate)||'');
var REPORTS=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
var VALS=(window.KOS_VALUATION&&KOS_VALUATION.stocks)||{};
/* 종목 페이지의 대표 주소 — 실사이트는 종목마다 미리 만든 페이지(stock/005930.html · scripts/build_stock_static.py)다.
   옛 주소(stock.html?ticker=)는 그리로 넘긴다. 없는 종목코드만 옛 주소 그대로 둔다. */
function stockUrl(t){ return 'https://kosai.kr/stock/'+encodeURIComponent(t)+'.html'; }
/* 미리 그린 글의 지문 — 노드로 미리 그린 글(scripts/prerender_stock.mjs)과 브라우저가 그린 글이 같은지 견준다(FNV-1a 32비트) */
window.kosHash=function(s){ var x=0x811c9dc5; for(var k=0;k<s.length;k++){ x^=s.charCodeAt(k); x=Math.imul(x,0x01000193); } return ('0000000'+(x>>>0).toString(16)).slice(-8); };
/* 영어 화면(staging/i18n.js) — 리포트 본문은 자료의 영어 쪽(pk), 라벨은 아래 T, 나머지 한국어 문구는 사전이 바꾼다. */
var I18=window.KOSi18n; function EN(){ return !!(I18&&I18.lang==='en'); }
var T_EN={ watch:'Add to Watchlist', watched:'In Watchlist', };
var T={ watch:'관심종목 추가', watched:'관심종목 추가됨', };
if(EN()) T=T_EN;
var LOCK_SVG='<svg class="lk" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
function qp(n){ return new URLSearchParams(location.search).get(n); }

/* 미리 만든 페이지는 종목코드(data-tk)와 미리 그린 글의 지문(data-pre)을 본문 자리에 달고 온다. 옛 껍데기(stock.html)는 ?ticker= 로 받는다. */
var PG=document.getElementById('page'), PRE=PG&&PG.getAttribute('data-pre');
var PRE_TIER=PG&&PG.getAttribute('data-pre-tier'), PRE_KNOWN=!!(PG&&PG.getAttribute('data-pre-known')==='1');   /* 미리 그릴 때의 리포트 형식 · 시세 유무 */
var TK=String((PG&&PG.getAttribute('data-tk'))||qp('ticker')||'').replace(/[^0-9A-Za-z]/g,'');
if(!TK){ var ks=Object.keys(REPORTS); TK=ks[0]||(LIVE[0]&&LIVE[0].ticker)||'005930'; }
var STOCK=null,i; for(i=0;i<LIVE.length;i++){ if(LIVE[i].ticker===TK){ STOCK=LIVE[i]; break; } }
var REP=null, TIER='none', KNOWN=!!STOCK, LOADED=false;

/* ── 글자·숫자 (stock_page.py 의 esc·fwon·fmcap·famt·fshares·pct·fdate·pk 와 같은 결과) ── */
function esc(x){ return String(x==null?'':x).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
/* 파이썬 '{:,.Nf}' 와 같은 글자. 정확히 반인 값(12.25)은 파이썬처럼 짝수로 붙인다 — toFixed 는 올려 버린다(12.3). */
function pyf(v,f,grp){
  v=+v; var a=Math.abs(v), s=a.toFixed(25), tail=s.slice(s.indexOf('.')+1+f), out;
  if(/^50*$/.test(tail)){ var p=Math.pow(10,f), lo=Math.floor(a*p); if(lo%2)lo+=1; out=(lo/p).toFixed(f); }
  else out=a.toFixed(f);
  if(grp){ var q=out.split('.'); q[0]=q[0].replace(/\B(?=(\d{3})+(?!\d))/g,','); out=q.join('.'); }
  return (v<0?'-':'')+out;
}
function pyround(x,n){ return Number(pyf(x,n)); }   /* 파이썬 round(x, n) */
/* 돈·주식 수 — 실사이트 stock.html 의 fwon·mcap·amt·shN(한국어 쪽) 그대로다. 빈 값만 '—'. 값마다 조·억·만을 붙인다:
   '조원' 하나로 고정했더니 작은 회사는 표·차트가 0.0, 시가총액이 0.4조원, 주식 수가 0.3억주로 나왔다(2026-09-26).
   반올림도 실사이트처럼 toFixed·Math.round(딱 반이면 올림)다. 셋이 같은지 staging/tests/same-units.test.mjs 가 본다. */
function fwon(v){ if(v==null)return '—'; v=+v; var sg=v<0?'-':''; var a=Math.abs(v);
  if(a>=1e12)return sg+(a/1e12).toFixed(1)+'조'; if(a>=1e8)return sg+Math.round(a/1e8).toLocaleString('en-US')+'억'; return sg+Math.round(a).toLocaleString('en-US')+'원'; }
function mcap(v){ if(v==null)return '—'; v=+v;
  if(v>=1){ var n=v.toLocaleString('en-US',{maximumFractionDigits:1}); return n+'조원'; }
  return Math.round(v*10000).toLocaleString('ko-KR')+'억원'; }
function amt(v){ if(v==null)return '—'; v=+v;
  if(v>=1e12)return (v/1e12).toFixed(1)+'조원'; if(v>=1e8)return Math.round(v/1e8).toLocaleString('en-US')+'억원'; return Math.round(v).toLocaleString('en-US')+'원'; }
function shN(v){ if(v==null)return '—'; v=+v;
  if(v>=1e8)return (v/1e8).toFixed(1)+'억주'; if(v>=1e4)return Math.round(v/1e4).toLocaleString('en-US')+'만주'; return v.toLocaleString('en-US')+'주'; }
function pct(v,signed){ if(v==null)return '—'; var s=(signed?(v<0?'':'+')+pyf(v,2):pyf(v,1))+'%'; return s.replace(/-/g,'−'); }
function fdate(d){ d=String(d==null?'':d); return /^\d{8}$/.test(d)?d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6):d; }
function pk(o){ if(o==null)return ''; if(typeof o==='object')return (EN()&&o.en)||o.ko||o.en||''; return o||''; }
function pad(x){ return x<10?'0'+x:''+x; }

/* ── 문단 — 실사이트 stock.html 의 것을 그대로(빌드할 때 떼어 온다). 손으로 고치지 말 것 ── */
function splitSentences(p){
    // 문장 끝('다.'/'요.' 등 또는 .!?) + 공백 뒤에 구분자 삽입 후 분리.
    // 소수점(13.5)은 뒤에 공백이 없어 분리되지 않음.
    var SEP='⁣';
    var m=String(p)
      .replace(/([다요죠음함됨임]\.)\s+/g, '$1'+SEP)
      .replace(/([.!?])\s+(?=[A-Z가-힣"'(])/g, '$1'+SEP);
    return m.split(SEP).map(function(s){return s.trim();}).filter(Boolean);
  }
var PARA_KO=170, PARA_EN=320;
function chunkPara(p){
    var s=splitSentences(p);
    if(s.length<2) return [p];
    var budget=/[가-힣]/.test(p)?PARA_KO:PARA_EN;
    var out=[],cur='',i,nx;
    for(i=0;i<s.length;i++){
      nx = cur ? cur+' '+s[i] : s[i];
      if(cur && nx.length>budget){ out.push(cur); cur=s[i]; }
      else cur=nx;
    }
    if(cur) out.push(cur);
    // 마지막 조각이 한 줄짜리 외톨이로 남으면 앞 문단에 붙인다.
    if(out.length>1 && out[out.length-1].length < budget*0.35){
      out[out.length-2] += ' '+out.pop();
    }
    return out;
  }
function ps(t){
    t=String(t==null?'':t);
    if(!t.trim()) return '';
    var out=[];
    t.split(/\n\n+/).forEach(function(x){ chunkPara(x.trim()).forEach(function(c){ if(c)out.push(c); }); });
    return out.map(function(c){ return '<p>'+esc(c)+'</p>'; }).join('');
  }
function prose(o){ var t=pk(o); var out=[]; String(t).split(/\n\n+/).forEach(function(p){ chunkPara(p.trim()).forEach(function(c){ if(c)out.push(c); }); }); return '<div class="prose">'+out.map(function(p){return '<p>'+esc(p)+'</p>';}).join('')+'</div>'; }
function factors(arr,cls){ return (arr||[]).map(function(f){return '<article class="fc '+cls+'"><h4><i class="dot"></i>'+esc(pk(f.title))+'</h4>'+ps(pk(f.body))+'</article>';}).join(''); }
function risksH(arr){ return '<div class="rks">'+(arr||[]).map(function(r){return '<div class="rk"><div class="rk-c">'+esc(pk(r.cat))+'</div><div class="rk-b">'+ps(pk(r.body))+'</div></div>';}).join('')+'</div>'; }
function cpsH(arr){ return '<ol class="cps">'+(arr||[]).map(function(c){return '<li><span class="when">'+esc(pk(c.when))+'</span><p>'+esc(pk(c.what))+'</p></li>';}).join('')+'</ol>'; }
function verdictH(){ return '<div class="prose verdict wrapup">'+ps(REP.verdict?pk(REP.verdict.body):'')+'</div>'; }
function kpH(){ return '<ol class="kp">'+(REP.keypoints||[]).map(function(k,i){return '<li><span class="n">'+(i+1)+'</span><p>'+esc(pk(k))+'</p></li>';}).join('')+'</ol>'; }
function abstractH(){ return '<div class="abstract"><h3 class="ab-title">'+esc(pk(REP.title))+'</h3><p class="ab-lead">'+esc(pk(REP.lead))+'</p>'+kpH()+'</div>'; }
function host(u){ return String(u).replace(/^https?:\/\//,'').split('/')[0].replace(/^www\./,''); }
function sourcesH(rep){
  var srcs=((rep&&rep.sources)||[]).filter(function(s){ return typeof s==='string'; });
  var li=PRIMARY_SRC.map(function(s){ return '<li><a href="'+esc(s[1])+'" target="_blank" rel="noopener">'+esc(s[0])+'</a></li>'; }).join('');
  if(!srcs.length) return '<ol class="srcs">'+li+'</ol>';
  var more=srcs.map(function(u){ return '<li><a href="'+esc(u)+'" target="_blank" rel="noopener nofollow">'+esc(host(u))+'</a></li>'; }).join('');
  return '<ol class="srcs">'+li+'</ol><details class="srcmore"><summary>기사·자료 '+srcs.length+'건 더 보기</summary><ol class="srcs">'+more+'</ol></details>';
}
/* 절 — 본문은 <section>(목차 따라가기가 본다), 흐린 미리보기 안은 <div>(같은 옷 · 따라가기는 건너뜀) */
function secH(i,title,inner,wide,quiet,tag){ tag=tag||'section'; var n=pad(i); return '<'+tag+' class="sec'+(wide?' wide':'')+'" id="s'+n+'"><div class="sec-h'+(quiet?' sec-h-quiet':'')+'"><span class="num">'+n+'</span><h2>'+esc(title)+'</h2></div>'+inner+'</'+tag+'>'; }

/* ── 차트 (stock_page.bar_chart 과 같은 좌표·표기) ── */
function barChart(groups){
  var w=520,h=220,padL=8,padR=8,top=28,bottom=28,n=groups.length; if(!n) return '';
  var vals=[]; groups.forEach(function(g){ [g[1],g[2]].forEach(function(v){ if(v!=null) vals.push(v); }); });
  var mx=Math.max.apply(null,[0].concat(vals)), mn=Math.min.apply(null,[0].concat(vals)); if(mx===mn) mx=1;
  var extra=mn<0?20:0, H=h+extra, plotH=h-top-bottom, rng=mx-mn, y0=top+plotH*mx/rng;
  var gw=(w-padL-padR)/n, bw=Math.min(22,gw*0.24), gap=6;
  var svg='<svg viewBox="0 0 '+w+' '+H+'" preserveAspectRatio="none" aria-hidden="true">'
    +'<line x1="'+padL+'" y1="'+pyf(y0,1)+'" x2="'+(w-padR)+'" y2="'+pyf(y0,1)+'" class="ch-base" vector-effect="non-scaling-stroke"/>';
  var labs='';
  groups.forEach(function(g,i){
    var cx=padL+gw*i+gw/2, marks=[];
    [[g[1],'ch-rev'],[g[2],'ch-op']].forEach(function(b,j){
      var val=b[0]; if(val==null) return;
      var x=(j===0)?cx-bw-gap/2:cx+gap/2, bh=plotH*Math.abs(val)/rng;
      if(val){ bh=Math.max(1.5,bh); var y=val>0?y0-bh:y0;
        svg+='<rect class="'+b[1]+'" x="'+pyf(x,1)+'" y="'+pyf(y,1)+'" width="'+pyf(bw,1)+'" height="'+pyf(bh,1)+'"/>'; }
      var up=val>=0, lft=(j===1&&up);   /* 영업이익 흑자 라벨은 막대 왼쪽 끝에서 오른쪽으로 — 옆 매출 막대를 덮지 않게 */
      marks.push([lft?x:x+bw/2, up?(y0-bh-5):(y0+bh+5), up, fwon(val), lft]);
    });
    if(marks.length===2 && marks[0][2]===marks[1][2] && Math.abs(marks[0][1]-marks[1][1])<14){
      var a=marks[0], c=marks[1];
      if(a[2]){ var hi=a[1]<=c[1]?a:c, lo=hi===a?c:a; hi[1]=lo[1]-14; }
      else { var deep=a[1]>=c[1]?a:c, sh=deep===a?c:a; deep[1]=sh[1]+14; }
    }
    marks.forEach(function(m){ labs+='<span class="ch-val'+(m[2]?'':' dn')+(m[4]?' l':'')+'" style="left:'+pyf(m[0]/w*100,2)+'%;top:'+pyf(m[1],1)+'px">'+m[3]+'</span>'; });
    labs+='<span class="ch-lab" style="left:'+pyf(cx/w*100,2)+'%;top:'+(H-20)+'px">'+esc(g[0])+'</span>';
  });
  return '<div class="ch" role="img" aria-label="매출·영업이익 막대그래프" style="height:'+H+'px">'+svg+'</svg>'+labs+'</div>';
}

/* ── 히어로 · 지표 (stock_page.render · _stats) ── */
function heroH(st){
  var name=st.name||TK, price=st.price, chg=st.change||0;
  var cls=chg>0?'up':(chg<0?'down':'flat'), arrow=chg>0?'▲':(chg<0?'▼':'');
  var ph=(price!=null)
    ?'<span class="p">'+pyf(price,0,true)+'원</span><span class="c '+cls+'">'+arrow+' '+pct(Math.abs(chg),true).replace(/^\+/,'')+'</span><span class="d">'+fdate(DATA_DATE)+' 장마감</span>'
    :'<span class="d">시세 없음</span>';
  return '<div><div class="eyebrow"><b>'+esc(st.market||'')+'</b><span>'+esc(st.sector||'')+'</span><span>'+TK+'</span></div><h1 class="name">'+esc(name)+'</h1><div class="price">'+ph+'</div>'
    +'<div class="actions"><button type="button" class="btn btn-ink ico" id="watchBtn" aria-pressed="false"><svg class="wb-add" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><svg class="wb-on" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg><span id="watchTxt">'+T.watch+'</span></button></div></div>';
}
function statsH(st){
  var price=st.price, per,pbr,eps,div,dps,win,note;
  if(TIER==='v2'){ var val=(REP.quant&&REP.quant.valuation)||{}; per=val.per; pbr=val.pbr; eps=val.eps; div=val.div; dps=val.dps; win=val.ttm_window; }
  else{
    var v=VALS[st.ticker]||{}, bps=v.bps; eps=v.eps; dps=v.dps;
    per=(eps&&eps>0&&price)?pyround(price/eps,1):null;
    pbr=(bps&&bps>0&&price)?pyround(price/bps,2):null;
    div=(dps!=null&&price)?pyround(dps/price*100,2):null; win=null;
  }
  function f(x,fn){ return x==null?'—':fn(x); }
  var rows=[
    ['시가총액', mcap(st.mcap)],
    ['거래대금', amt(st.trading_value)],
    ['거래량', shN(st.volume)],
    ['상장주식수', shN(st.shares)],
    ['PER', f(per,function(x){ return pyf(x,1)+'배'; })],
    ['PBR', f(pbr,function(x){ return pyf(x,1)+'배'; })],
    ['EPS', f(eps,function(x){ return pyf(x,0,true)+'원'; })],
    ['배당수익률', f(div,function(x){ return pyf(x,2)+'%'; })]];
  var html=rows.map(function(r){ return '<div class="st"><div class="st-k">'+esc(r[0])+'</div><div class="st-v">'+esc(r[1])+'</div></div>'; }).join('');
  if(TIER==='v2') note='PER·EPS·PBR·BPS는 최근 4개 분기('+esc(win)+') 기준 자체 산출'+(dps!=null?' · 배당수익률은 주당 '+pyf(dps,0,true)+'원 기준':'');
  else note='PER·PBR·배당수익률은 최근 확정 실적(EPS·BPS·주당배당금)과 현재 주가로 산출';
  return {html:html, note:note};
}

/* ── 본문 v2 — 13개 절. 앞 셋과 참고 출처는 무료, 04~12 는 구독 구간(scripts/report_split.py 의 PAID_KEYS) ── */
function v2Parts(){
  var q=REP.quant||{}, val=q.valuation||{};
  var annual=(q.annual||[]).slice().sort(function(a,b){ return a.year-b.year; }), quarterly=q.quarterly||[];
  var qChart=barChart(quarterly.map(function(x){ return [String(x.q).slice(2,4)+'Q'+String(x.q).slice(-1), x.rev, x.op]; }));
  var aChart=barChart(annual.map(function(a){ return [String(a.year), a.rev, a.op]; }));
  var annRows=annual.map(function(a){ return '<tr><th scope="row">'+a.year+'</th><td>'+fwon(a.rev)+'</td><td>'+fwon(a.op)+'</td><td>'+fwon(a.np_owner)+'</td><td>'+pct(a.opm)+'</td><td>'+pct(a.roe)+'</td><td>'+pct(a.debt_ratio)+'</td></tr>'; }).join('');
  var qtrRows=quarterly.map(function(x){ return '<tr><th scope="row">'+esc(x.q)+'</th><td>'+fwon(x.rev)+'</td><td>'+fwon(x.op)+'</td><td>'+((x.rev&&x.op!=null)?pct(x.op/x.rev*100):'—')+'</td></tr>'; }).join('');
  var lg='<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div>';
  var fin='<div class="tiles"><figure class="tile"><figcaption>분기 매출 · 영업이익</figcaption>'+qChart+lg+'</figure><figure class="tile"><figcaption>연간 매출 · 영업이익</figcaption>'+aChart+lg+'</figure></div>'
    +'<div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>분기 실적 · 최근 '+quarterly.length+'분기</span></div></caption><thead><tr><th>분기</th><th>매출액</th><th>영업이익</th><th>영업이익률</th></tr></thead><tbody>'+qtrRows+'</tbody></table></div>'
    +'<div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>연간 실적</span></div></caption><thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>지배주주 순이익</th><th>영업이익률</th><th>ROE</th><th>부채비율</th></tr></thead><tbody>'+annRows+'</tbody></table></div>'
    +'<p class="note">연결 기준(자회사 실적을 합친 재무제표) · DART 공시 확정치 · 순이익은 지배주주 기준 · 데이터 '+esc(q.asOf)+'</p>';
  function vv(key,fn){ var x=val[key]; return x==null?'—':fn(x); }
  var mul=function(x){ return pyf(x,1)+'배'; }, won=function(x){ return pyf(x,0,true)+'원'; };
  var vstrip='<div class="vstrip"><div class="st"><div class="st-k">PER</div><div class="st-v">'+vv('per',mul)+'</div></div><div class="st"><div class="st-k">PBR</div><div class="st-v">'+vv('pbr',mul)+'</div></div><div class="st"><div class="st-k">ROE</div><div class="st-v">'+vv('roe_ttm',function(x){ return pyf(x,1)+'%'; })+'</div></div><div class="st"><div class="st-k">EPS</div><div class="st-v">'+vv('eps',won)+'</div></div><div class="st"><div class="st-k">BPS</div><div class="st-v">'+vv('bps',won)+'</div></div><div class="st"><div class="st-k">주당배당금</div><div class="st-v">'+vv('dps',won)+'</div></div></div>';
  var vnote='<p class="note">'+esc(val.basis)+' · 기준 '+esc(q.asOf)+'</p>';
  return {
    free:[[1,'리포트 개요',abstractH(),false,true],[2,'사업 구조',prose(REP.business),false,false],[3,'실적 추이',fin,true,false]],
    paid:[[4,'실적 분석',prose(REP.earnings),false,false],[5,'산업 분석',prose(REP.industry),false,false],[6,'전망',prose(REP.outlook),false,false],
          [7,'밸류에이션',vstrip+prose(REP.valuation_comment)+vnote,true,false],[8,'강세 요인','<div class="fcs">'+factors(REP.bull,'bull')+'</div>',false,false],
          [9,'약세 요인','<div class="fcs">'+factors(REP.bear,'bear')+'</div>',false,false],[10,'리스크 요인',risksH(REP.risks),true,false],
          [11,'다음 체크포인트',cpsH(REP.checkpoints),false,false],[12,'종합 의견',verdictH(),false,false]],
    tail:[[13,'참고 출처',sourcesH(REP),false,false]],
    vstrip:vstrip, vnote:vnote
  };
}
function bodyV2(){
  var P=v2Parts(), locked=paywalled();
  var sec=function(s){ return secH(s[0],s[1],s[2],s[3],s[4]); };
  var html=P.free.map(sec).join('');
  if(locked) html+=lockBlock(teaserPane(P));
  else html+=P.paid.map(sec).join('');
  html+=P.tail.map(sec).join('');
  return {titles:SECTIONS_V2, html:html, locked:locked?P.paid.map(function(s){ return s[0]-1; }):[]};
}
/* 옛 형식(v1) — 재무 수치·체크포인트가 없다. 있는 절만 그린다(stock_page._body_v1). 잠그지 않는다. */
function bodyV1(){
  var items=[['리포트 개요',abstractH(),false,true],['사업 구조',prose(pk(REP.business)||pk(REP.desc)),false,false]];
  if(pk(REP.recent)) items.push(['최근 동향',prose(REP.recent),false,false]);
  items.push(['전망',prose(REP.outlook),false,false],['강세 요인','<div class="fcs">'+factors(REP.bull,'bull')+'</div>',false,false],
    ['약세 요인','<div class="fcs">'+factors(REP.bear,'bear')+'</div>',false,false],['리스크 요인',risksH(REP.risks),true,false],
    ['종합 의견',verdictH(),false,false],['참고 출처',sourcesH(REP),false,false]);
  return {titles:items.map(function(t){ return t[0]; }), html:items.map(function(it,i){ return secH(i+1,it[0],it[1],it[2],it[3]); }).join(''), locked:[]};
}

/* 실사이트 — 유료 구간이 없다(멤버십 전). 잠금 카드 · 흐린 미리보기 · paywall 모듈을 싣지 않고 모든 절을 그린다 */
var _lockOff=null; function paywalled(){ return false; }

/* ── 목차 · 페이지 ── */
function tocH(titles,locked){
  var lk={}; locked.forEach(function(i){ lk[i]=1; });
  var toc=titles.map(function(t,i){ var n=pad(i+1); return '<a href="#s'+n+'"'+(lk[i]?' data-lock="1"':'')+'><span class="n">'+n+'</span>'+esc(t)+(lk[i]?LOCK_SVG:'')+'</a>'; }).join('');
  var chips=titles.map(function(t,i){ var n=pad(i+1); return '<a href="#s'+n+'"'+(lk[i]?' data-lock="1"':'')+'>'+n+' '+esc(t)+(lk[i]?LOCK_SVG:'')+'</a>'; }).join('');
  return {toc:toc, chips:chips};
}
function pendingH(){
  var li=PRIMARY_SRC.map(function(s){ return '<li><a href="'+esc(s[1])+'" target="_blank" rel="noopener">'+esc(s[0])+'</a></li>'; }).join('');
  return '<div class="pending"><h2>이 종목의 리포트는 준비 중입니다</h2><p>새로 상장된 종목은 상장 직후 리포트를 작성합니다. 시세·시가총액·PER·PBR 같은 지표는 매 거래일 저녁에 갱신됩니다.</p><ol class="srcs">'+li+'</ol><p class="disc">'+DISC+'</p></div>';
}
function notFoundH(){   // 종목코드가 문장 안에 들어가 사전으로는 못 바꾼다 — 영어 화면은 여기서 바로
  if(EN()) return '<div class="pending"><h2>Stock not found</h2><p>No stock matches the ticker you requested ('+esc(TK)+'). Please look it up again in the <a href="/Reports.html">report list</a>.</p></div>';
  return '<div class="pending"><h2>종목을 찾을 수 없습니다</h2><p>요청하신 종목코드('+esc(TK)+')에 해당하는 종목이 없습니다. <a href="/Reports.html">리포트 목록</a>에서 종목을 다시 찾아 주시기 바랍니다.</p></div>';
}
var RANK={none:0,v1:1,v2:2};
function render(){
  /* 미리 만든 페이지 — 받은 자료가 미리 그린 때보다 모자라면(리포트 파일 · 시세를 못 받았으면 — 통신이 끊긴 휴대폰, 검색 로봇의 렌더링)
     미리 그린 글과 머리를 그대로 둔다. 그리면 다 있던 리포트가 '준비 중' · '찾을 수 없습니다'로 바뀐다(독립 검토 2026-10-03).
     새 리포트가 생긴 경우(준비 중 → 리포트)는 아래에서 새로 그린다. 영어 화면은 처음부터 다시 그리므로 해당 없다. */
  if(PRE&&LOADED&&!EN()&&((RANK[REP?TIER:'none']||0)<(RANK[PRE_TIER]||0)||(PRE_KNOWN&&!KNOWN))){
    var pm=document.getElementById('page'); PRE=null; pm.removeAttribute('data-pre'); pm.setAttribute('data-tier',PRE_TIER||'none');
    if(window.kosFitCharts) window.kosFitCharts(); if(window.kosTocInit) window.kosTocInit(); syncWatch(); return;
  }
  var st=STOCK||{ticker:TK, name:(REP&&REP.name)||TK, name_en:(REP&&REP.name_en)||'', market:(REP&&REP.market)||'', sector:(REP&&REP.sector)||'', price:null, change:0};
  var stats=statsH(st);
  var h='<header class="hero">'+heroH(st)+'</header><section class="stats" aria-label="핵심 지표">'+stats.html+'</section><p class="stats-note">'+stats.note+' · 시세 '+fdate(DATA_DATE)+' 장마감</p>';
  var locked=false;
  if(LOADED){
    if(REP){
      var b=(TIER==='v2')?bodyV2():bodyV1(), t=tocH(b.titles,b.locked);
      locked=b.locked.length>0;
      h+='<div class="body"><aside class="toc" id="toc">'+t.toc+'</aside><div class="content"><div class="chips-mark" id="chipsMark"></div><div class="chips-bar" id="chipsBar"><nav class="chips" id="chips">'+t.chips+'</nav></div>'
        +b.html+'<p class="rdate">리포트 작성 '+esc(REP.reportDate)+' · 데이터 기준 '+fdate(REP.dataDate)+'</p><p class="disc">'+DISC+'</p></div></div>';
    }
    else h+=KNOWN?pendingH():notFoundH();
  }
  var main=document.getElementById('page');
  /* 미리 만든 페이지 — 자료를 받아 그린 글이 미리 그린 글과 같으면(지문이 같으면) 그대로 둔다. 다시 넣으면 읽던 자리의
     펼친 출처 · 고른 글이 풀린다. 자료가 그사이 바뀌었거나 영어 화면이면 그린다. */
  var same=!!(PRE&&LOADED&&!EN()&&kosHash(h)===PRE);
  if(!same){
    /* 휴대폰 목차 띠가 헤더 안에 붙어 있으면(pin) 본문 밖에 있다 — 새로 그리기 전에 뗀다. 안 그러면 id 가 둘이 된다. */
    var old=document.getElementById('chipsBar'); if(old) old.parentNode.removeChild(old);
    main.innerHTML=h;
  }
  if(PRE){ PRE=null; main.removeAttribute('data-pre'); }   /* 한 번 견주면 끝 — 영어 화면의 가림(data-pre)도 여기서 걷힌다 */
  if(window.kosFitCharts) window.kosFitCharts();   /* 차트 값 라벨이 옆 막대·라벨에 닿으면 비켜 세운다(stock_page.CHART_FIT_JS) */
  if(LOADED) main.setAttribute('data-tier',REP?TIER:(KNOWN?'none':'unknown'));
  if(window.kosTocInit) window.kosTocInit();
  syncWatch();
  if(locked) wireLock();
  else if(_lockOff){ _lockOff(); _lockOff=null; }   /* 열렸으면 잠금 카드의 구독 리스너를 뗀다 — 사라진 단추를 붙들고 있지 않게 */
  if(LOADED) setSEO(locked);
}



/* 관심종목 단추 — KOSWatch(Firestore)가 켜고 끈다. 새로 그릴 때마다 단추가 바뀌므로 문서에 한 번만 건다. */
var watched=false;
function syncWatch(){
  watched=!!(window.KOSWatch&&window.KOSWatch.has(TK));
  var b=document.getElementById('watchBtn'), tx=document.getElementById('watchTxt');
  if(b){ b.classList.toggle('on',watched); b.setAttribute('aria-pressed',watched?'true':'false'); }
  if(tx) tx.textContent=watched?T.watched:T.watch;
}
window.addEventListener('koswatch:change',syncWatch);
document.addEventListener('click',function(e){
  var b=e.target.closest&&e.target.closest('#watchBtn'); if(!b||!window.KOSWatch) return;
  if(window.KOSWatch.has(TK)) window.KOSWatch.remove(TK); else window.KOSWatch.add(TK);
  syncWatch();
});

/* 제목 · 설명 · canonical · OG · JSON-LD — stock_page.render() 와 같은 내용을 종목이 정해진 뒤 채운다 */
function setSEO(locked){
  try{
    var url=(REP||KNOWN)?stockUrl(TK):'https://kosai.kr/stock.html?ticker='+encodeURIComponent(TK), name=(STOCK&&STOCK.name)||(REP&&REP.name)||TK, rt=REP?pk(REP.title):'', ttl, dsc;
    if(EN()){ var ne=STOCK&&I18?I18.nameEn(STOCK):name;
      if(REP){ ttl=ne+' ('+TK+') Report'+(rt?' — '+rt:'')+' | KOSAI'; dsc=String(pk(REP.lead)||pk(REP.desc)).replace(/\s+/g,' ').slice(0,158); }
      else if(KNOWN){ ttl=ne+' ('+TK+') — Report in preparation | KOSAI'; dsc=ne+' ('+TK+') price, market cap, P/E and P/B. Reports for newly listed stocks are written right after listing.'; }
      else{ ttl=TK+' — Stock not found | KOSAI'; dsc='No stock matches the requested code.'; }
    }
    else if(REP){ ttl=rt?name+'('+TK+') 리포트 — '+rt+' | KOSAI':name+'('+TK+') 리포트 | KOSAI'; dsc=String(pk(REP.lead)||pk(REP.desc)).replace(/\s+/g,' ').slice(0,158); }
    else if(KNOWN){ ttl=name+'('+TK+') 종목 — 리포트 준비 중 | KOSAI'; dsc=name+'('+TK+') 시세·시가총액·PER·PBR. AI 분석 리포트는 상장 직후 작성됩니다.'; }
    else{ ttl=TK+' — 종목을 찾을 수 없습니다 | KOSAI'; dsc='요청하신 종목코드에 해당하는 종목이 없습니다.'; }
    function setMeta(sel,attr,val){ var el=document.querySelector(sel); if(el) el.setAttribute(attr,val); }
    document.title=ttl;
    setMeta('link[rel=canonical]','href',url);
    setMeta('meta[name=description]','content',dsc);
    setMeta('meta[property="og:title"]','content',ttl);
    setMeta('meta[property="og:description"]','content',dsc);
    setMeta('meta[property="og:url"]','content',url);
    var ld={'@context':'https://schema.org','@type':'Article',
      'headline':(REP&&rt)?name+' ('+TK+') — '+rt:name+' ('+TK+')',
      'datePublished':(REP&&REP.reportDate)||fdate(DATA_DATE),'dateModified':fdate(DATA_DATE),
      'inLanguage':'ko','isAccessibleForFree':!locked,'mainEntityOfPage':url,
      'author':{'@type':'Organization','name':'KOSAI','url':'https://kosai.kr'},
      'about':{'@type':'Corporation','name':name,'legalName':(STOCK&&STOCK.name_en)||(REP&&REP.name_en)||name,'tickerSymbol':TK}};
    var s=document.getElementById('kos-jsonld');
    if(!s){ s=document.createElement('script'); s.type='application/ld+json'; s.id='kos-jsonld'; document.head.appendChild(s); }
    s.textContent=JSON.stringify(ld);
  }catch(e){}
}

/* ── 리포트 본문은 종목별 파일에서 그때 받는다(전체 리포트 v2 → 옛 형식 v1) ── */
function getJson(u){ return fetch(u,{cache:'no-cache'}).then(function(r){ return r.ok?r.json():null; }).catch(function(){ return null; }); }
/* 히어로·지표는 바로 — 본문은 받은 뒤. 미리 만든 페이지의 한국어 글은 그대로 두고 자료를 받은 뒤 한 번만 견준다(영어 화면은 바로 그린다) */
if(PRE&&!EN()) syncWatch(); else render();
getJson('/data/reports_v2/'+encodeURIComponent(TK)+'.json').then(function(r){
  if(r){ REP=r; TIER='v2'; return; }
  return getJson('/data/reports/'+encodeURIComponent(TK)+'.json').then(function(r1){ if(r1){ REP=r1; TIER='v1'; } });
}).then(function(){
  LOADED=true; render();
  if(window.KOSA) KOSA.track(REP?'report_view':'stock_view',{ticker:TK, name:(STOCK&&STOCK.name)||(REP&&REP.name)||TK});
  /* 최근 본 종목(검색창 드롭다운용) — 기기에만 둔다 */
  try{
    var RK='kos-recent', rc=JSON.parse(localStorage.getItem(RK)||'[]').filter(function(x){ return x&&x.t&&x.t!==TK; });
    if(STOCK||REP){ rc.unshift({t:TK, n:(STOCK&&STOCK.name)||(REP&&REP.name)||TK}); localStorage.setItem(RK, JSON.stringify(rc.slice(0,8))); }
  }catch(e){}
});
})();
