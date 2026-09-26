#!/usr/bin/env python3
"""스테이징 종목 페이지(staging/stock.html) — 새 디자인 · 브라우저가 그리는 껍데기 한 장 · 유료 구간 잠금.

    python3 scripts/build_stock_staging.py                # staging/stock.html 을 다시 만든다
    python3 scripts/build_stock_staging.py --out /tmp/x   # 다른 폴더에 내 본다(검사·비교용 · 파일 이름은 stock.html)
    python3 scripts/build_stock_staging.py --check        # 만든 결과가 저장소와 같은지만 본다

무엇인가
  · 실사이트 stock.html 처럼 2,682 종목이 같이 쓰는 껍데기다. ?ticker= 로 종목을 받아 data/reports_v2/{tk}.json 을
    받고, 없으면 data/reports/{tk}.json(옛 형식 v1), 그것도 없으면 '리포트 준비 중' 안내를 그린다. 시세·지표는
    data/stocks.js · valuation.js 에서 온다.
  · 옷은 scripts/stock_page.py 의 PAGE_CSS 그대로다. 그 모듈이 파이썬으로 그리는 DOM(히어로 · 지표 · 목차 · 절 · 표 · 차트)을
    여기 자바스크립트가 같은 클래스·id 로 만든다 — 그래서 미리 만든 종목 페이지(preview/stock/)와 이 페이지가 같아 보인다.
    옷을 고칠 때는 stock_page.PAGE_CSS 한 곳만 고친다. 여기서는 잠금 카드·흐린 미리보기 옷(LOCK_CSS)만 보탠다.
  · 문단 자르기는 실사이트 stock.html 의 splitSentences · chunkPara · ps 를 빌드할 때 그 파일에서 떼어 와 그대로 넣는다.
    staging/tests/same-paragraphs.test.mjs 가 글자 하나까지 같은지 본다(CLAUDE.md 2026-09-14). 파이썬 chunk() 는 쓰지 않는다 —
    그래서 이 페이지의 문단은 실사이트와 같고, stock_page.render() 와는 문장 경계 규칙만큼 다르다.
  · 유료 구간(실적 분석 ~ 종합 의견)은 흐린 미리보기 + 잠금 카드. 열고 닫는 것은 paywall.js(실제) · demo-backend.js(모의)의
    window.KOSPaywall 이다. ?paywall=0 이면 잠그지 않는다. 옛 형식(v1)은 잠그지 않는다.
  · 스테이징 경로(../data · 모듈 꼬리 스크립트 · STAGING 띠)는 comp_common.set_mode('staging') + emit() 이 맡는다.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402
import stock_page as S  # noqa: E402

C.set_mode('staging')

TITLE = '종목 리포트 | KOSAI'
DESC = '종목별 AI 분석 리포트 — 핵심 지표, 실적 추이, 밸류에이션, 강세·약세 요인과 리스크.'
LIVE_FUNCS = ('function splitSentences(', 'function chunkPara(', 'function ps(')


# ── 실사이트의 문단 규칙을 그대로 떼어 온다 ──────────────────────────────────
def grab(src, head):
    """여는 중괄호부터 짝이 맞는 닫는 중괄호까지 — same-paragraphs.test.mjs 의 grab 과 같은 규칙."""
    i = src.find(head)
    if i < 0:
        return None
    j = src.find('{', i)
    depth = 0
    for k in range(j, len(src)):
        c = src[k]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
    return None


def live_paragraph_code():
    live = (ROOT / 'stock.html').read_text(encoding='utf-8')
    parts = []
    for head in LIVE_FUNCS:
        code = grab(live, head)
        if not code:
            raise SystemExit(f'stock.html 에서 {head} 를 찾지 못했다 — 실사이트 문단 규칙이 바뀌었는지 확인할 것')
        parts.append(code)
    m = re.search(r'var PARA_KO=\d+,\s*PARA_EN=\d+;', live)
    if not m:
        raise SystemExit('stock.html 에 PARA_KO·PARA_EN 이 없다')
    return '\n'.join([parts[0], m.group(0), parts[1], parts[2]])


# ── 잠금 카드 · 흐린 미리보기 · 목차 자물쇠 (이 페이지만의 옷) ─────────────────
LOCK_CSS = '''/* 유료 구간 — 흐린 미리보기 뒤에 잠금 카드. 상자·유리 없이 가는 선 하나로 나눈다(인쇄된 리서치 리포트) */
.tz{max-width:880px;padding:0 0 88px}
.tz-body{filter:blur(6px);-webkit-filter:blur(6px);pointer-events:none;user-select:none;-webkit-user-select:none;max-height:520px;overflow:hidden;-webkit-mask-image:linear-gradient(to bottom,#000 40%,transparent);mask-image:linear-gradient(to bottom,#000 40%,transparent)}
.tz-body .sec{padding-bottom:64px}
.lockwrap{max-width:720px}
.lockwrap.pending{visibility:hidden}
.lock{border-top:1px solid var(--line);padding:32px 0;margin:0}
.lock h3{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em}
.lock-sub{margin:8px 0 0;font:400 14px/22px var(--font);color:var(--ink-72)}
.lock-list{margin:14px 0 0;font:400 13px/20px var(--font);color:var(--ink-62)} .lock-list span+span::before{content:" · "}
.lock-cta{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.lock-note{margin:14px 0 0;font:400 12px/18px var(--font);color:var(--ink-62)}
.lock-err{display:none;margin:12px 0 0;font:400 13px/20px var(--font);color:var(--up)} .lock-err.show{display:block}
/* 목차의 자물쇠 — 잠긴 절 */
.toc a .lk{width:11px;height:11px;flex:none;margin-left:auto;align-self:center;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;opacity:.55}
.chips a .lk{display:inline-block;width:11px;height:11px;vertical-align:-1px;margin-left:5px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;opacity:.55}
.pending p a{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .pending p a:hover{text-decoration-color:var(--ink)}
@media (max-width:820px){.tz{padding-bottom:64px} .tz-body{max-height:440px}}'''

# 종목별 canonical 을 받자마자 맞춘다 — 뒤의 setSEO() 가 제목·설명·JSON-LD 를 마저 채운다.
CANON_JS = '''<script>(function(){try{var m=location.search.match(/[?&]ticker=([^&]+)/);if(!m)return;var t=decodeURIComponent(m[1]).replace(/[^0-9A-Za-z]/g,'');if(!t)return;
var u='https://kosai.kr/stock.html?ticker='+t;function set(sel,attr,val){var e=document.querySelector(sel);if(e)e.setAttribute(attr,val)}set('link[rel=canonical]','href',u);set('meta[property="og:url"]','content',u)}catch(e){}})();</script>'''

# ── 페이지 스크립트 ─────────────────────────────────────────────────────────
# stock_page.render() 와 같은 DOM 을 만든다. 숫자 표기는 파이썬 '{:,.1f}' 규칙(정확히 반이면 짝수로)을 따른다.
PAGE_JS = r'''/* ===== 종목 페이지 — 데이터로 그린다 (stock_page.render 와 같은 DOM) ===== */
(function(){
'use strict';
__CONST__
var LIVE=(window.KOS_LIVE_DATA&&KOS_LIVE_DATA.stocks)||[];
var DATA_DATE=String((window.KOS_LIVE_DATA&&KOS_LIVE_DATA.dataDate)||'');
var REPORTS=(window.KOS_REPORTS&&KOS_REPORTS.reports)||{};
var VALS=(window.KOS_VALUATION&&KOS_VALUATION.stocks)||{};
var SITE_URL='https://kosai.kr/stock.html?ticker=';
var T={ watch:'관심종목 추가', watched:'관심종목 추가됨',
  lockTitle:'리포트 전문은 구독 회원에게 제공됩니다', lockSub:'BASIC 월 9,900원부터', lockSubN:'{s}개 섹션 · 약 {m}분 분량 · BASIC 월 9,900원부터',
  cta:'멤버십 보기', ctaLogin:'로그인하고 이어보기', ctaOpen:'이어서 읽기', loading:'불러오는 중…',
  note:'이미 구독 중이시라면 로그인하여 주시기 바랍니다.',
  limitT:'일일 열람 한도에 도달했습니다', limitS:'열람 한도는 매일 자정(한국 시간)에 초기화됩니다.', upgrade:'PRO로 업그레이드',
  errNone:'이 종목은 유료 구간이 아직 준비되지 않았습니다.', errFail:'불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.' };
var LOCK_SVG='<svg class="lk" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>';
function qp(n){ return new URLSearchParams(location.search).get(n); }

var TK=String(qp('ticker')||'').replace(/[^0-9A-Za-z]/g,'');
if(!TK){ var ks=Object.keys(REPORTS); TK=ks[0]||(LIVE[0]&&LIVE[0].ticker)||'005930'; }
var STOCK=null,i; for(i=0;i<LIVE.length;i++){ if(LIVE[i].ticker===TK){ STOCK=LIVE[i]; break; } }
var REP=null, TIER='none', KNOWN=!!STOCK, LOADED=false;

/* ── 글자·숫자 (stock_page.py 의 esc·fwon·fjo·pct·fdate·pk 와 같은 결과) ── */
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
function fwon(v){ if(v==null)return '—'; var a=Math.abs(v); if(a>=1e12)return pyf(v/1e12,1,true)+'조'; if(a>=1e8)return pyf(v/1e8,0,true)+'억'; return pyf(v,0,true); }
function fjo(v){ return v==null?'—':pyf(v/1e12,1,true); }
function pct(v,signed){ if(v==null)return '—'; var s=(signed?(v<0?'':'+')+pyf(v,2):pyf(v,1))+'%'; return s.replace(/-/g,'−'); }
function fdate(d){ d=String(d==null?'':d); return /^\d{8}$/.test(d)?d.slice(0,4)+'-'+d.slice(4,6)+'-'+d.slice(6):d; }
function pk(o){ if(o==null)return ''; if(typeof o==='object')return o.ko||o.en||''; return o||''; }
function pad(x){ return x<10?'0'+x:''+x; }

/* ── 문단 — 실사이트 stock.html 의 것을 그대로(빌드할 때 떼어 온다). 손으로 고치지 말 것 ── */
__LIVE_FUNCS__
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
      marks.push([lft?x:x+bw/2, up?(y0-bh-5):(y0+bh+5), up, fjo(val), lft]);
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
  var vol=st.volume;
  var rows=[
    ['시가총액', f(st.mcap,function(x){ return pyf(x,1,true)+'조원'; })],
    ['거래대금', st.trading_value!=null?fwon(st.trading_value)+'원':'—'],
    ['거래량', ((vol||0)<1e4)?f(vol,function(x){ return pyf(x,0,true)+'주'; }):pyf((vol||0)/1e4,0,true)+'만주'],
    ['상장주식수', f(st.shares?st.shares/1e8:null,function(x){ return pyf(x,1,true)+'억주'; })],
    ['PER', f(per,function(x){ return pyf(x,1)+'배'; })],
    ['PBR', f(pbr,function(x){ return pyf(x,1)+'배'; })],
    ['EPS', f(eps,function(x){ return pyf(x,0,true)+'원'; })],
    ['배당수익률', f(div,function(x){ return pyf(x,2)+'%'; })]];
  var html=rows.map(function(r){ return '<div class="st"><div class="st-k">'+esc(r[0])+'</div><div class="st-v">'+esc(r[1])+'</div></div>'; }).join('');
  if(TIER==='v2') note='PER·EPS·PBR·BPS 는 최근 4개 분기('+esc(win)+') 기준 자체 산출'+(dps!=null?' · 배당수익률은 주당 '+pyf(dps,0,true)+'원 기준':'');
  else note='PER·PBR·배당수익률은 최근 확정 실적(EPS·BPS·주당배당금)과 현재 주가로 산출';
  return {html:html, note:note};
}

/* ── 본문 v2 — 13개 절. 앞 셋과 참고 출처는 무료, 04~12 는 구독 구간(scripts/report_split.py 의 PAID_KEYS) ── */
function v2Parts(){
  var q=REP.quant||{}, val=q.valuation||{};
  var annual=(q.annual||[]).slice().sort(function(a,b){ return a.year-b.year; }), quarterly=q.quarterly||[];
  var qChart=barChart(quarterly.map(function(x){ return [String(x.q).slice(2,4)+'Q'+String(x.q).slice(-1), x.rev, x.op]; }));
  var aChart=barChart(annual.map(function(a){ return [String(a.year), a.rev, a.op]; }));
  var annRows=annual.map(function(a){ return '<tr><th scope="row">'+a.year+'</th><td>'+fjo(a.rev)+'</td><td>'+fjo(a.op)+'</td><td>'+fjo(a.np_owner)+'</td><td>'+pct(a.opm)+'</td><td>'+pct(a.roe)+'</td><td>'+pct(a.debt_ratio)+'</td></tr>'; }).join('');
  var qtrRows=quarterly.map(function(x){ return '<tr><th scope="row">'+esc(x.q)+'</th><td>'+fjo(x.rev)+'</td><td>'+fjo(x.op)+'</td><td>'+((x.rev&&x.op!=null)?pct(x.op/x.rev*100):'—')+'</td></tr>'; }).join('');
  var lg='<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div>';
  var fin='<div class="tiles"><figure class="tile"><figcaption>분기 매출 · 영업이익 <span>단위: 조원</span></figcaption>'+qChart+lg+'</figure><figure class="tile"><figcaption>연간 매출 · 영업이익 <span>단위: 조원</span></figcaption>'+aChart+lg+'</figure></div>'
    +'<div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>분기 실적 · 최근 '+quarterly.length+'분기</span><span class="u">단위: 조원</span></div></caption><thead><tr><th>분기</th><th>매출액</th><th>영업이익</th><th>영업이익률</th></tr></thead><tbody>'+qtrRows+'</tbody></table></div>'
    +'<div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>연간 실적</span><span class="u">단위: 조원</span></div></caption><thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>지배주주 순이익</th><th>영업이익률</th><th>ROE</th><th>부채비율</th></tr></thead><tbody>'+annRows+'</tbody></table></div>'
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

/* ── 유료 구간 잠금 ─────────────────────────────────────────
   정적 파일에는 무료 구간만 담기고 hasPaid:true 가 붙는다. 유료 구간은 서버(Firestore)에만 있고
   KOSPaywall.fetchPaid 가 받아온다. 전환 전 데이터에는 hasPaid 가 없어 실사이트에서는 그대로 다 보인다.
   스테이징은 기본이 잠금(FORCE_LOCK) — ?paywall=0 으로 끈다. */
var PAID=null, _lockOff=null, _lockWait=false, FORCE_LOCK=(qp('paywall')!=='0');
function paywalled(){ return TIER==='v2' && !PAID && (FORCE_LOCK || (REP&&REP.hasPaid===true)); }
function nextParam(){ var page=location.pathname.split('/').pop()||'stock.html'; return encodeURIComponent(page+(location.search||'')); }

/* 흐린 미리보기 — 서버가 주는 것은 '어느 절에 문단이 몇 개, 각각 몇 글자' 뿐이다(teaser). 글자는 여기서 아무 뜻 없이
   만들어 깔고 흐린다. 진짜 본문을 내려보내 흐리게 덮으면 개발자 도구에서 filter 한 줄만 지워도 다 읽힌다.
   문단 수·항목 수·길이와 마크업은 실제 렌더와 같게 맞춘다 — 그래야 흐린 판이 진짜 리포트가 이어지는 것처럼 보인다. */
var TZ_KEYS=['earnings','industry','outlook','valuation_comment','bull','bear','risks','checkpoints','verdict'];
var TZ_NUM={earnings:4,industry:5,outlook:6,valuation_comment:7,bull:8,bear:9,risks:10,checkpoints:11,verdict:12};
var TZ_POOL='매출영업이익수요공급가격전망성장확대둔화개선부담경쟁점유율투자비용시장실적기준증가감소'
           +'대비수익구조원가환율금리재고출하단가물량비중전년동기수준유지회복'
           +'0123456789.%()0123456789조원억달러202520262027';
var _tzSeed=0;
/* 길이만 맞춘 글자. 같은 리포트면 늘 같은 모양이 나오도록 난수는 결정적으로 돌린다 — 다시 그릴 때마다 출렁이면 거슬린다. */
function fillerText(len){
  var out='',gap=0,k,r=(_tzSeed=(_tzSeed*1103515245+12345)&0x7fffffff)||9973;
  len=Math.max(2,Math.round(len));
  for(k=0;k<len;k++){
    r=(r*1103515245+12345)&0x7fffffff;
    out+=TZ_POOL.charAt(r%TZ_POOL.length);
    if(++gap>=2+(r>>9)%5 && k<len-1){ out+=' '; gap=0; }   /* 서너 글자마다 띄어 줄바꿈 자리가 실제와 비슷해진다 */
  }
  return out;
}
function tzP(n){ return '<p>'+esc(fillerText(n))+'</p>'; }
function tzLens(v){ return v==null ? [] : (v.length===undefined ? [v] : v); }
function tzSum(v){ var t=0; tzLens(v).forEach(function(L){ t+=L; }); return t; }
function tzPs(v){ return tzLens(v).map(tzP).join(''); }
/* publish_paid.py 를 아직 안 돌린 동안에는 정적 파일에 본문이 그대로 있다. 그때도 미리보기를 확인할 수 있게
   같은 뼈대(문단별 글자 수)를 여기서 만든다. 서버가 teaser 를 주기 시작하면 쓰이지 않는다. */
function deriveTeaser(){
  function paras(o){ var t=pk(o); if(!t) return []; var out=[]; String(t).split(/\n\n+/).forEach(function(b){ chunkPara(b.trim()).forEach(function(c){ if(c) out.push(c.length); }); }); return out; }
  function items(arr,a,b,split){ return (arr||[]).map(function(x){ return [pk(x[a]).length, split?paras(x[b]):pk(x[b]).length]; }); }
  var out=[];
  function add(k,t,v){ if(v&&v.length) out.push({k:k,t:t,paras:(t==='prose'||t==='wrapup')?v:null,items:(t==='prose'||t==='wrapup')?null:v}); }
  add('earnings','prose',paras(REP.earnings));
  add('industry','prose',paras(REP.industry));
  add('outlook','prose',paras(REP.outlook));
  add('valuation_comment','prose',paras(REP.valuation_comment));
  add('bull','factors',items(REP.bull,'title','body',true));
  add('bear','factors',items(REP.bear,'title','body',true));
  add('risks','pairs',items(REP.risks,'cat','body',true));
  add('checkpoints','pairs',items(REP.checkpoints,'when','what'));
  add('verdict','wrapup',REP.verdict?paras(REP.verdict.body):[]);
  return out;
}
/* 실제 렌더(prose · factors · risksH · cpsH · verdictH)와 같은 마크업 — 클래스가 다르면 여백이 달라져 덩어리 위치가 어긋난다. */
function tzSection(t){
  var n=0;
  if(t.t==='prose'){ (t.paras||[]).forEach(function(L){ n+=L; }); return {h:'<div class="prose">'+(t.paras||[]).map(tzP).join('')+'</div>', n:n}; }
  if(t.t==='wrapup'){ (t.paras||[]).forEach(function(L){ n+=L; }); return {h:'<div class="prose verdict">'+(t.paras||[]).map(tzP).join('')+'</div>', n:n}; }
  if(t.t==='factors'){ return {h:'<div class="fcs">'+(t.items||[]).map(function(it){ n+=it[0]+tzSum(it[1]); return '<article class="fc '+(t.k==='bull'?'bull':'bear')+'"><h4><i class="dot"></i>'+esc(fillerText(it[0]))+'</h4>'+tzPs(it[1])+'</article>'; }).join('')+'</div>', n:n}; }
  if(t.t==='pairs'&&t.k==='risks'){ return {h:'<div class="rks">'+(t.items||[]).map(function(it){ n+=it[0]+tzSum(it[1]); return '<div class="rk"><div class="rk-c">'+esc(fillerText(it[0]))+'</div><div class="rk-b">'+tzPs(it[1])+'</div></div>'; }).join('')+'</div>', n:n}; }
  if(t.t==='pairs'){ return {h:'<ol class="cps">'+(t.items||[]).map(function(it){ n+=it[0]+it[1]; return '<li><span class="when">'+esc(fillerText(it[0]))+'</span><p>'+esc(fillerText(it[1]))+'</p></li>'; }).join('')+'</ol>', n:n}; }
  return {h:'', n:0};
}
/* 잠긴 절 04~12 를 번호 그대로 흐리게 깐다. 절 번호는 열렸을 때와 같아야 목차가 흔들리지 않는다. */
function teaserPane(P){
  var tz=REP.teaser; if(!tz||!tz.length) tz=deriveTeaser();
  var byKey={}; (tz||[]).forEach(function(t){ byKey[t.k]=t; });
  _tzSeed=0;
  var h='', chars=0, names=[];
  P.paid.forEach(function(s){
    var key=TZ_KEYS[s[0]-4], t=byKey[key], body=t?tzSection(t):{h:'',n:0};
    if(key==='valuation_comment') body.h=P.vstrip+body.h+P.vnote;   /* 지표 띠·각주는 무료 구간 값 — 그대로 둔다 */
    chars+=body.n; names.push(s[1]);
    h+=secH(s[0],s[1],body.h,s[3],s[4],'div');
  });
  return {html:h, secs:P.paid.length, names:names, mins:Math.max(1,Math.round(chars/500))};   /* 묵독 분당 500자 */
}
/* 잠금 카드. 두 번째 단추는 스크립트가 못 떠도 죽지 않도록 링크로 두고, wireLock() 이 로그인·구독 상태에 맞는 동작을 얹는다. */
function lockBlock(tz){
  var sub=tz?T.lockSubN.replace('{s}',tz.secs).replace('{m}',tz.mins):T.lockSub;
  var names=(tz&&tz.names&&tz.names.length)?tz.names:['실적 분석','산업 분석','전망','밸류에이션','리스크 요인','종합 의견'];
  return '<div class="tz" id="tz">'+(tz&&tz.html?'<div class="tz-body" aria-hidden="true">'+tz.html+'</div>':'')
    +'<div class="lockwrap"><div class="lock" id="lockCard">'
    +'<h3>'+esc(T.lockTitle)+'</h3><p class="lock-sub">'+esc(sub)+'</p>'
    +'<div class="lock-list">'+names.map(function(x){ return '<span>'+esc(x)+'</span>'; }).join('')+'</div>'
    +'<div class="lock-cta"><a class="btn btn-ink" href="pricing.html">'+esc(T.cta)+'</a><a class="btn btn-soft" id="lockBtn" href="Login.html?next='+nextParam()+'">'+esc(T.ctaLogin)+'</a></div>'
    +'<p class="lock-note">'+esc(T.note)+'</p><div class="lock-err" id="lockErr"></div>'
    +'</div></div></div>';
}
/* 잠금 카드의 단추 — 로그인·구독 상태에 따라 문구와 동작이 달라진다. render() 마다 다시 건다. */
function wireLock(){
  var btn=document.getElementById('lockBtn'), err=document.getElementById('lockErr'), card=document.getElementById('lockCard');
  if(_lockOff){ _lockOff(); _lockOff=null; }   /* 이전 리스너부터 뗀다 — 잠금이 풀려 단추가 사라진 뒤에도 남으면 안 된다 */
  if(!btn) return;
  var P=window.KOSPaywall;
  /* 본문은 같은 도메인 JSON 하나로 그려지는데 paywall 모듈은 파이어베이스 묶음까지 받아야 뜬다 — 거의 늘 본문이 먼저다.
     모듈이 자리를 잡으면 알려 주니(kos-paywall-ready) 그때 다시 건다. 끝내 안 뜨면 링크 그대로(로그인 페이지). */
  if(!P){ if(!_lockWait){ _lockWait=true; document.addEventListener('kos-paywall-ready',function(){ _lockWait=false; wireLock(); },{once:true}); } return; }
  function show(msg){ err.textContent=msg; err.classList.add('show'); }
  var note=card&&card.querySelector('.lock-note'), wrapEl=card&&card.parentNode;
  /* 로그인·구독을 기억하면(P.peek — 모의 결제에만 있다) 확인이 끝날 때까지 카드를 자리만 잡고 숨긴다 */
  if(wrapEl&&P.peek&&P.ready&&P.ready.then){ var pv=P.peek(); if(pv&&pv.provisional&&pv.active){ wrapEl.classList.add('pending'); P.ready.then(function(){ wrapEl.classList.remove('pending'); }); } }
  _lockOff=P.onChange(function(st){
    if(!st.user){ btn.style.display=''; btn.textContent=T.ctaLogin; if(note) note.style.display=''; }          /* 비로그인 */
    else if(st.active){ btn.style.display=''; btn.textContent=T.ctaOpen; if(note) note.style.display='none'; } /* 구독 중 */
    else{ btn.style.display='none'; if(note) note.style.display='none'; }                                     /* 로그인 · 구독 없음 — 멤버십 보기 하나면 된다 */
    if(st.user&&st.active&&!PAID&&!btn.dataset.busy) open();   /* 구독이 확인되면 누르지 않아도 연다(결제 직후 돌아온 경우) */
  });
  async function open(ev){
    if(ev) ev.preventDefault();
    var st=P.state();
    if(!st.user){ location.href='Login.html?next='+nextParam(); return; }
    if(!st.active){ location.href='pricing.html'; return; }
    btn.dataset.busy='1'; btn.disabled=true; btn.textContent=T.loading;
    try{
      var r=await P.fetchPaid(TK);
      if(!r||!r.paid||!Object.keys(r.paid).length){ var e0=new Error('빈 응답'); e0.code='not-found'; throw e0; }   /* 빈 응답으로 풀면 텅 빈 절이 열린다 */
      PAID=r.paid;
      Object.keys(PAID).forEach(function(key){ REP[key]=PAID[key]; });
      render();
    }catch(e){
      btn.disabled=false; delete btn.dataset.busy; btn.textContent=T.ctaOpen;
      if(e.code==='resource-exhausted'){
        /* 이미 구독자다 — 카드 머리의 '월 9,900원부터'와 '멤버십 보기'는 맞는 말이 아니다. 한도 안내로 바꿔 단다. */
        var st2=P.state(), pro=(st2.plans&&st2.plans.pro)||{};
        var h3=card&&card.querySelector('h3'), sb=card&&card.querySelector('.lock-sub'), cta=card&&card.querySelector('.lock-cta');
        if(h3) h3.textContent=T.limitT;
        if(sb) sb.textContent=T.limitS;
        if(cta){ if(st2.plan==='basic'&&pro.limit) cta.innerHTML='<a class="btn btn-ink" href="billing.html">'+esc(T.upgrade)+'</a>'; else cta.style.display='none'; }   /* BASIC 이면 올릴 자리 · PRO 는 더 올릴 데가 없다 */
      }
      else if(e.code==='not-found') show(T.errNone);
      else if(e.code==='unauthenticated') location.href='Login.html?next='+nextParam();
      else if(e.code==='permission-denied') location.href='pricing.html';
      else show(T.errFail);
    }
  }
  btn.addEventListener('click',open);
}

/* ── 목차 · 페이지 ── */
function tocH(titles,locked){
  var lk={}; locked.forEach(function(i){ lk[i]=1; });
  var toc=titles.map(function(t,i){ var n=pad(i+1); return '<a href="#s'+n+'"'+(lk[i]?' data-lock="1"':'')+'><span class="n">'+n+'</span>'+esc(t)+(lk[i]?LOCK_SVG:'')+'</a>'; }).join('');
  var chips=titles.map(function(t,i){ var n=pad(i+1); return '<a href="#s'+n+'"'+(lk[i]?' data-lock="1"':'')+'>'+n+' '+esc(t)+(lk[i]?LOCK_SVG:'')+'</a>'; }).join('');
  return {toc:toc, chips:chips};
}
function pendingH(){
  var li=PRIMARY_SRC.map(function(s){ return '<li><a href="'+esc(s[1])+'" target="_blank" rel="noopener">'+esc(s[0])+'</a></li>'; }).join('');
  return '<div class="pending"><h2>이 종목의 리포트는 준비 중입니다</h2><p>새로 상장된 종목은 첫 사업·분기보고서가 공시된 뒤에 리포트를 작성합니다. 시세·시가총액·PER·PBR 같은 지표는 매 거래일 저녁에 갱신됩니다.</p><ol class="srcs">'+li+'</ol><p class="disc">'+DISC+'</p></div>';
}
function notFoundH(){
  return '<div class="pending"><h2>종목을 찾을 수 없습니다</h2><p>요청하신 종목코드('+esc(TK)+')에 해당하는 종목이 없습니다. <a href="Reports.html">리포트 목록</a>에서 종목을 다시 찾아 주시기 바랍니다.</p></div>';
}
function render(){
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
  /* 휴대폰 목차 띠가 헤더 안에 붙어 있으면(pin) 본문 밖에 있다 — 새로 그리기 전에 뗀다. 안 그러면 id 가 둘이 된다. */
  var old=document.getElementById('chipsBar'); if(old) old.parentNode.removeChild(old);
  var main=document.getElementById('page'); main.innerHTML=h;
  if(LOADED) main.setAttribute('data-tier',REP?TIER:(KNOWN?'none':'unknown'));
  if(window.kosTocInit) window.kosTocInit();
  syncWatch();
  if(locked) wireLock();
  else if(_lockOff){ _lockOff(); _lockOff=null; }   /* 열렸으면 잠금 카드의 구독 리스너를 뗀다 — 사라진 단추를 붙들고 있지 않게 */
  if(LOADED) setSEO(locked);
}

/* 잠긴 절의 목차 항목 — 흐린 판 속으로 들어가지 않고 유료 구간이 시작하는 자리로 간다 */
document.addEventListener('click',function(e){
  var a=e.target.closest&&e.target.closest('#toc a[data-lock], #chips a[data-lock]'); if(!a) return;
  var tz=document.getElementById('tz'); if(!tz) return;
  e.preventDefault(); e.stopPropagation();
  var padTop=parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)||0;
  window.scrollTo({top:tz.getBoundingClientRect().top+window.scrollY-padTop,behavior:'smooth'});
  try{ history.replaceState(null,'',a.getAttribute('href')); }catch(x){}
},true);

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
    var url=SITE_URL+encodeURIComponent(TK), name=(STOCK&&STOCK.name)||(REP&&REP.name)||TK, rt=REP?pk(REP.title):'', ttl, dsc;
    if(REP){ ttl=rt?name+'('+TK+') 리포트 — '+rt+' | KOSAI':name+'('+TK+') 리포트 | KOSAI'; dsc=String(pk(REP.lead)||pk(REP.desc)).replace(/\s+/g,' ').slice(0,158); }
    else if(KNOWN){ ttl=name+'('+TK+') 종목 — 리포트 준비 중 | KOSAI'; dsc=name+'('+TK+') 시세·시가총액·PER·PBR. AI 분석 리포트는 첫 정기보고서가 공시된 뒤 작성됩니다.'; }
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
render();   /* 히어로·지표는 바로 — 본문은 받은 뒤 */
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
})();'''


def page_js():
    const = ('var DISC=' + json.dumps(S.DISC, ensure_ascii=False) + ', PRIMARY_SRC=' + json.dumps(S.PRIMARY_SRC, ensure_ascii=False)
             + ', SECTIONS_V2=' + json.dumps(S.SECTIONS_V2, ensure_ascii=False) + ';')
    return PAGE_JS.replace('__CONST__', const).replace('__LIVE_FUNCS__', live_paragraph_code())


def build_html():
    extra = (f'<meta name="description" content="{S.esc(DESC)}">\n'
             '<link rel="canonical" href="https://kosai.kr/stock.html">\n'
             f'<meta property="og:title" content="{S.esc(TITLE)}">\n<meta property="og:description" content="{S.esc(DESC)}">\n'
             '<meta property="og:url" content="https://kosai.kr/stock.html">\n<meta property="og:type" content="article">\n'
             + CANON_JS + '\n'
             '<style>\n' + C.CSS + '\n' + S.PAGE_CSS + '\n' + LOCK_CSS + '\n</style>\n')
    head = C.head(TITLE, extra=extra)
    return f'''{head}
</head>
<body>
{C.nav('리포트')}
<main class="wrap" id="page"></main>
{C.FOOTER}
<script src="/data/stocks.js"></script>
<script src="/data/valuation.js"></script>
<script src="/data/reports-index.js"></script>
<script>
{C.TOC_JS}
{C.JS}
{page_js()}
</script>
</body>
</html>'''


def build(out_dir):
    out = Path(out_dir) / 'stock.html'
    html = build_html()
    C.emit(str(out), html)
    return out


def unstamped(s):
    """모듈 주소의 ?v=해시를 뗀 글 — stamp_assets.py 가 붙인 도장은 생성기 결과와 비교할 때 뺀다."""
    return re.sub(r'\?v=[0-9a-f]{8}', '', s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'staging'), help='내보낼 폴더 (파일 이름은 stock.html)')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            made = build(td).read_text(encoding='utf-8')
            cur = ROOT / 'staging/stock.html'
            same = cur.exists() and unstamped(cur.read_text(encoding='utf-8')) == unstamped(made)
            print('✅ staging/stock.html = 생성기 결과' if same else '❌ staging/stock.html 이 생성기와 다르다 → python3 scripts/build_stock_staging.py')
            sys.exit(0 if same else 1)
    out = build(a.out)
    if out.resolve() == (ROOT / 'staging/stock.html').resolve():
        subprocess.run([sys.executable, str(ROOT / 'scripts/stamp_assets.py')], check=True)   # 모듈 주소에 ?v=해시 (build_staging.py 와 같다)
    print(f'✅ {out} · {out.stat().st_size:,}바이트')


if __name__ == '__main__':
    main()
