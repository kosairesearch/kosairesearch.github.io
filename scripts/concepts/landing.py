"""랜딩 시안 2판 — 스테이징 디자인 그대로(부품·너비·글꼴) + 카피·구성 이론(research_notes/카피라이팅과 랜딩페이지 구성 이론 총정리).

    python3 scripts/concepts/landing.py      # → preview/concepts/landing/index.html · landing.css

  · 그림·영상·3D 는 만들지 않는다. 들어갈 자리만 표시한다(종류 · 비율 · 들어갈 내용).
  · 숫자는 전부 data/ 에서 계산한다(기준일을 함께 적는다). 글은 스테이징에 이미 있는 사실 문장에서만 가져온다.
  · 스테이징·실사이트 파일은 건드리지 않는다.
"""
import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from data import (ROOT, BY, STOCKS, INDEX, SECTORS_AI, esc, cls, grp, jo, kdate, report, brief, publish_time, briefs,  # noqa: E402
                  PRICE_DATE)
from common import g, chart_bars  # noqa: E402

OUT = os.path.join(ROOT, "preview", "concepts", "landing")
ASSETS = "../../../assets"
FONTS = "../../../fonts"
SAMPLE = "052330"                      # 코텍 — 코스닥 소형주, 5개 분기 연속 이익 증가
BASE = datetime.date(2026, 9, 26)      # 이 시안의 '기준일'
TOC = [("무엇으로 돈을 버는 회사인가", ["리포트 개요", "사업 구조", "실적 추이"], True),
       ("숫자 뒤의 이유", ["실적 분석", "산업 분석", "전망", "밸류에이션"], False),
       ("양쪽 이유와 다음 일정", ["강세 요인", "약세 요인", "리스크 요인", "다음 체크포인트", "종합 의견"], False),
       ("근거", ["참고 출처"], True)]      # staging/stock.html 의 실제 목차 13개 절을 네 묶음으로(무료 = True)

CSS = r"""
:root{
  --bg:#f9f8f6; --surface:#fff; --surface-2:#f1efeb; --slot:#ebe9e5;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-62:rgba(20,20,20,.62); --ink-50:rgba(20,20,20,.5); --ink-30:rgba(20,20,20,.3);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --up:#c8102e; --down:#1e5fbf;
  --band:#141414; --band-ink:#f2f1ee; --band-62:rgba(242,241,238,.62); --band-hair:rgba(255,255,255,.12);
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --gap:24px; --sec:168px;
}
:root[data-theme="dark"]{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20; --slot:#1b1b1d;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-62:rgba(236,236,234,.62); --ink-50:rgba(236,236,234,.5); --ink-30:rgba(236,236,234,.3);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14);
  --up:#ff5a5f; --down:#6aa2ff;
  --band:#161617; --band-ink:#ececea; --band-62:rgba(236,236,234,.62); --band-hair:rgba(255,255,255,.1);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:80px}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;
  word-break:keep-all;overflow-wrap:break-word}
a{color:inherit;text-decoration:none}
h1,h2,h3,h4,p,ul,ol,figure,dl,dd{margin:0}
ul,ol{padding:0;list-style:none}
button,input{font:inherit;color:inherit}
.w{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}
.nw{white-space:nowrap}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--ink-62)}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
svg.i{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.brand .dk{display:none} :root[data-theme="dark"] .brand .lt{display:none} :root[data-theme="dark"] .brand .dk{display:block}

/* 머리 — 스테이징과 같은 자리, 같은 말 */
.nav{position:sticky;top:0;z-index:50;height:64px;background:var(--bg);transition:box-shadow .2s}
.nav.on{box-shadow:0 1px 0 var(--hair)}
.nav-in{height:64px;display:flex;align-items:center;justify-content:space-between;position:relative}
.brand img{height:14px;display:block}
.links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:28px}
.links a{font:500 14px/1 var(--font);color:var(--ink-72);transition:color .12s}
.links a:hover{color:var(--ink)}
.right{display:flex;align-items:center;gap:4px}
.login{font:500 14px/1 var(--font);color:var(--ink-72);padding:14px 10px}
.ib{width:40px;height:40px;border:0;background:none;display:inline-flex;align-items:center;justify-content:center;border-radius:20px;cursor:pointer;color:var(--ink)}
.ib svg{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.menu{display:none}

/* 단추 — 스테이징 btn · btn-ink · btn-soft */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:999px;border:0;
  font:600 14.5px/1 var(--font);white-space:nowrap;cursor:pointer;transition:opacity .12s,background-color .12s}
.btn-ink{background:var(--ink);color:var(--bg)} .btn-ink:hover{opacity:.9}
.btn-soft{background:var(--surface-2);color:var(--ink)} .btn-soft:hover{background:var(--line)}
.more{display:inline-flex;align-items:center;gap:6px;font:600 15px/1 var(--font);color:var(--ink);padding:12px 0}
.more svg.i{width:15px;height:15px;transition:transform .2s}
.more:hover svg.i{transform:translateX(3px)}

/* 검색 — 스테이징 밑줄 검색창 */
.search{display:flex;align-items:center;gap:12px;height:60px;border-bottom:1px solid var(--line);transition:border-color .15s}
.search:focus-within{border-bottom-color:var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-62);flex:none}
.search input{flex:1;min-width:0;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0}
.search input::placeholder{color:var(--ink-62)}
.search .btn{height:40px;padding:0 18px;font-size:14px}
.hint{margin-top:14px;display:flex;flex-wrap:wrap;gap:6px 14px;align-items:baseline;font:400 13.5px/1.5 var(--font);color:var(--ink-62)}
.hero-alt{margin-top:10px}
.hint a{color:var(--ink);font-weight:500;text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.hint a:hover{text-decoration-color:var(--ink)}

/* 첫 화면 */
.hero{padding-top:88px}
.pill{display:inline-flex;align-items:center;gap:10px;height:34px;padding:0 14px;border-radius:999px;background:var(--surface-2);font:500 13px/1 var(--font);color:var(--ink-72)}
.pill b{font-weight:600;color:var(--ink)}
.pill svg.i{width:14px;height:14px}
.hero h1{margin-top:28px;max-width:960px;font:700 clamp(38px,5.4vw,72px)/1.14 var(--font);letter-spacing:-.035em;text-wrap:balance}
.hero .lede{margin-top:24px;max-width:540px;font:400 18px/1.7 var(--font);color:var(--ink-72);text-wrap:pretty}
.hero .search{margin-top:40px;max-width:600px}
.hero .hint{max-width:600px}

/* 그림 자리 — 만들지 않고 표시만 */
.slot{position:relative;border-radius:16px;overflow:hidden;background-color:var(--slot);
  background-image:repeating-linear-gradient(-45deg,rgba(128,128,128,.07) 0 1px,transparent 1px 12px)}
.slot .st{position:absolute;top:18px;left:18px;display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 12px 0 10px;border-radius:999px;background:var(--surface);
  font:600 12.5px/1 var(--font);color:var(--ink)}
.slot .st svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.slot .sr{position:absolute;top:25px;right:20px;font:500 12px/1 var(--font);color:var(--ink-62)}
.slot figcaption{position:absolute;left:20px;right:20px;bottom:18px;max-width:520px;font:400 13.5px/1.6 var(--font);color:var(--ink-62);text-wrap:pretty}
.slot figcaption b{display:block;margin-bottom:4px;font:600 14px/1.4 var(--font);color:var(--ink)}
.m-hero{margin-top:64px;aspect-ratio:21/9}
.m-end{aspect-ratio:21/8}

/* 절 머리 — 작은 이름표 · 요점을 말하는 문장 하나 · 설명은 작게 */
.sec{padding-top:var(--sec)}
.eyebrow{margin-bottom:18px;font:600 13px/1 var(--font);color:var(--ink-62)}
.band .eyebrow{color:var(--band-62)}
/* 한 문단 선언 — 대안이 알려 주는 것(흐리게) 뒤에 KOSAI 가 쓰는 것(진하게) */
.statement{padding-top:var(--sec)}
.statement p{max-width:920px;font:600 clamp(26px,3.2vw,42px)/1.42 var(--font);letter-spacing:-.028em;text-wrap:pretty}
.statement p span{color:var(--ink-50)}
.h2{font:700 clamp(30px,3.9vw,50px)/1.2 var(--font);letter-spacing:-.03em;text-wrap:balance}
.sub{margin-top:20px;max-width:520px;font:400 17px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:var(--gap)}
.c-l{grid-column:1/6} .c-r{grid-column:7/13}
.fine{font:400 13px/1.65 var(--font);color:var(--ink-62);text-wrap:pretty}

/* 리포트 한 편 */
.demo{margin-top:56px;align-items:start}
.demo .c-l{position:sticky;top:104px}
.toc{margin-top:36px;border-top:1px solid var(--hair)}
.toc li{padding:15px 0 14px;border-bottom:1px solid var(--hair)}
.toc .tg{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font:600 15px/1.4 var(--font)}
.toc .tg span{font:500 12px/1 var(--font);color:var(--ink-62)}
.toc .tn{margin-top:5px;font:400 14px/1.6 var(--font);color:var(--ink-62)}
.demo .more{margin-top:20px}
.card{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:32px 32px 28px}
.cd-top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.cd-top b{display:block;font:700 18px/1.25 var(--font)}
.cd-top span{display:block;margin-top:6px;font:400 13px/1 var(--font);color:var(--ink-62)}
.cd-px{text-align:right} .cd-px b{font-size:17px} .cd-px span{font-weight:600}
.cd-meta{margin-top:16px;padding-bottom:18px;border-bottom:1px solid var(--hair);font:400 12.5px/1.5 var(--font);color:var(--ink-62)}
.card h3{margin-top:22px;font:700 26px/1.3 var(--font);letter-spacing:-.025em;text-wrap:balance}
.cd-lede{margin-top:12px;font:400 15px/1.72 var(--font);color:var(--ink-72);text-wrap:pretty}
.cd-chart{margin-top:24px;padding:18px 18px 8px;border-radius:12px;background:var(--bg)}
.cd-chart p{display:flex;justify-content:space-between;font:600 13px/1 var(--font)} .cd-chart p span{font-weight:400;color:var(--ink-62)}
.cd-chart svg{margin-top:8px} .cd-chart .cm{display:none}
.bb{margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:24px}
.bb h4{font:600 13px/1 var(--font);padding-bottom:10px;border-bottom:1px solid var(--line)}
.bb h4 span{margin-left:6px;font-weight:400;color:var(--ink-62)}
.bb li{padding:10px 0;border-bottom:1px solid var(--hair);font:500 14px/1.45 var(--font);color:var(--ink-72)}
.cd-foot{margin-top:18px;display:flex;justify-content:space-between;gap:12px;font:400 12.5px/1.4 var(--font);color:var(--ink-62)}
.card-note{margin-top:16px}

/* 다시 쓰는 리포트 */
.fresh{margin-top:56px}
.rows{border-top:1px solid var(--line)}
.row{display:grid;grid-template-columns:200px minmax(0,1fr) 132px 72px;gap:24px;align-items:center;padding:17px 0;border-bottom:1px solid var(--hair)}
.row .nm{font:600 15.5px/1.3 var(--font)} .row .cd{display:block;margin-top:4px;font:400 12.5px/1 var(--font);color:var(--ink-62)}
.row .tt{font:400 15.5px/1.45 var(--font)}
.row .mc,.row .dt{text-align:right;font:400 13.5px/1 var(--font);color:var(--ink-62);white-space:nowrap}
.row:hover .tt{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.rows-cap{display:flex;justify-content:space-between;align-items:baseline;margin:0 0 12px;font:600 13px/1 var(--font)}
.rows-cap span{font-weight:400;color:var(--ink-62)}
.trust{margin-top:64px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 var(--gap);align-items:start;border-top:1px solid var(--line)}
.trust>div{padding-top:24px}
.trust h3{font:600 15px/1.5 var(--font)}
.trust p{margin-top:8px;font:400 15px/1.7 var(--font);color:var(--ink-72);text-wrap:pretty}
.trust .more{margin-top:6px;font-size:14.5px}

/* 모닝브리핑 — 어두운 띠 하나 */
.band{margin-top:var(--sec);padding:128px 0 136px;background:var(--band);color:var(--band-ink)}
.band .sub{color:var(--band-62);margin-top:0}
.bgrid{margin-top:48px;align-items:start}
.band .more{color:var(--band-ink);margin-top:28px}
.band .fine{color:var(--band-62);margin-top:14px}
.bcard{border:1px solid var(--band-hair);border-radius:16px;padding:30px 30px 26px}
.bcard .bm{font:400 13px/1.4 var(--font);color:var(--band-62)}
.bcard h3{margin-top:14px;font:700 24px/1.36 var(--font);letter-spacing:-.025em;text-wrap:balance}
.bsec{margin-top:22px;border-top:1px solid var(--band-hair);counter-reset:b}
.bsec li{counter-increment:b;display:grid;grid-template-columns:22px 1fr;padding:11px 0;border-bottom:1px solid var(--band-hair);font:400 14.5px/1.5 var(--font);color:var(--band-ink)}
.bsec li::before{content:counter(b);color:var(--band-62)}
.bstats{margin-top:22px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.bstats dt{font:500 12px/16px var(--font);color:var(--band-62)}
.bstats dd{margin-top:6px;font:600 17px/22px var(--font);letter-spacing:-.01em;white-space:nowrap}
.bstats dd small{display:block;margin-top:2px;font:500 12.5px/16px var(--font)}
.band .up{color:#ff6b70} .band .down{color:#7fb0ff}

/* 업종 */
.sgrid{margin-top:56px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));column-gap:var(--gap);border-top:1px solid var(--line)}
.sgrid li{padding:16px 0 14px;border-bottom:1px solid var(--hair)}
.sgrid .sn{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font:500 15px/1.3 var(--font)}
.sgrid .sn b{font:400 13.5px/1 var(--font);color:var(--ink-62)}
.sgrid .bar{display:block;height:2px;margin-top:11px;background:var(--hair)}
.sgrid .bar i{display:block;height:100%;background:var(--ink-30)}
.sgrid li:hover .bar i{background:var(--ink)}
.s-foot{margin-top:16px;display:flex;justify-content:space-between;gap:16px;align-items:baseline}
.s-all{margin-left:auto}

/* 하지 않는 것 */
.stance{align-items:end}
.stance .h2{font-size:clamp(34px,4.6vw,60px);line-height:1.12}
.stance p{font:400 17px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}
.stance p+p{margin-top:16px;color:var(--ink-62);font-size:15.5px}

/* 멤버십 — 스테이징 요금제 세 단(상자 없이 가는 선) */
.plans{margin-top:48px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 40px;border-top:1px solid var(--line)}
.plan{display:flex;flex-direction:column;padding:28px 0 8px}
.plan-name{font:600 12px/16px var(--font);letter-spacing:.06em;color:var(--ink-62)}
.plan-price{margin-top:12px;font:700 36px/44px var(--font);letter-spacing:-.02em}
.plan-price small{margin-left:4px;font:500 15px/1 var(--font);letter-spacing:0;color:var(--ink-62)}
.plan-sub{margin-top:6px;font:400 14px/1.5 var(--font);color:var(--ink-72);min-height:42px}
.plan ul{margin:18px 0 24px;border-top:1px solid var(--hair);flex:1}
.plan li{padding:10px 0;border-bottom:1px solid var(--hair);font:400 14px/1.5 var(--font);color:var(--ink-72)}
.plan .btn{width:100%}
.plan .under{margin-top:10px;font:400 12.5px/1.5 var(--font);color:var(--ink-62);text-align:center;min-height:19px}
.same{margin-top:40px}
.same+.plans{margin-top:16px}

/* 질문 */
.faq{margin-top:48px;align-items:start}
.qa{border-top:1px solid var(--hair)} .qa:last-child{border-bottom:1px solid var(--hair)}
.qa summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:20px 0;font:600 17px/1.45 var(--font)}
.qa summary::-webkit-details-marker{display:none}
.qa summary::after{content:"+";flex:none;font:400 22px/1 var(--font);color:var(--ink-62);transition:transform .2s}
.qa[open] summary::after{transform:rotate(45deg)}
.qa p{padding:0 40px 22px 0;font:400 15.5px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}

/* 마무리 */
.end .h2{margin-top:56px}
.end .search{margin-top:32px;max-width:600px}
.chips{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px}
.chips a{display:inline-flex;align-items:center;height:36px;padding:0 14px;border-radius:999px;background:var(--surface-2);font:500 14px/1 var(--font);color:var(--ink);transition:background-color .12s}
.chips a:hover{background:var(--line)}
.chips a span{margin-left:6px;font-weight:400;color:var(--ink-62)}

/* 꼬리 — 스테이징 그대로(한 줄 소개만 고침) */
.foot{margin-top:var(--sec);border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand img{height:13px}
.ftag{margin-top:14px;font:400 14px/22px var(--font);color:var(--ink-72);max-width:300px}
.fgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;max-width:560px;margin-top:32px}
.fcol{display:flex;flex-direction:column}
.fcol h4{margin:0 0 6px;font:600 12.5px/1 var(--font);color:var(--ink-62)}
.fcol a{font:400 14px/1 var(--font);color:var(--ink-72);padding:9px 0} .fcol a:hover{color:var(--ink)}
.fcol a.pp{font-weight:600;color:var(--ink)}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-62)}
.copy{margin-top:28px;font:400 12px/18px var(--font);color:var(--ink-62)}

@media (max-width:1060px){
  .links{display:none} .menu{display:inline-flex}
  .grid{display:block}
  .demo .c-l{position:static}
  .c-r{margin-top:40px}
  .row{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"nm mc" "tt tt";gap:8px 12px}
  .row>div:first-child{grid-area:nm} .row .tt{grid-area:tt} .row .mc{grid-area:mc} .row .dt{display:none}
  .sgrid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .plans{grid-template-columns:1fr;gap:0}
  .plan{padding-bottom:28px;border-bottom:1px solid var(--hair)}
  .plan-sub{min-height:0}
  .stance p{margin-top:20px}
  .trust{grid-template-columns:1fr;border-top:0}
  .trust>div{padding:22px 0;border-top:1px solid var(--hair)}
  .trust>div:first-child{border-top-color:var(--line)}
}
@media (max-width:720px){
  :root{--pad:20px; --sec:112px}
  html{scroll-padding-top:68px}
  .nav,.nav-in{height:56px}
  .login{display:none}
  .hero{padding-top:44px}
  .pill{height:32px;font-size:12.5px;gap:8px}
  .hero h1{margin-top:22px;font-size:clamp(28px,8.1vw,34px);line-height:1.24;letter-spacing:-.03em}   /* 360~390px 에서 두 줄 · 뜻 단위로만 끊김 */
  .hero .lede{margin-top:18px;font-size:16px}
  .hero .search{margin-top:30px;height:60px}
  .end .search{height:60px}
  .search input{font-size:16px}
  .search .btn{height:44px;padding:0 16px;font-size:14px}
  .hint{font-size:13px}
  .m-hero{margin-top:40px;aspect-ratio:4/5}
  .slot figcaption{font-size:13px}
  .h2{font-size:28px;line-height:1.3}
  .statement p{font-size:23px;line-height:1.48}
  .eyebrow{margin-bottom:14px}
  .sub{font-size:16px;margin-top:16px}
  .demo{margin-top:36px}
  .card{padding:22px 18px 20px}
  .card h3{font-size:22px}
  .cd-chart{padding:14px 10px 6px} .cd-chart .cd{display:none} .cd-chart .cm{display:block}
  .bb{grid-template-columns:1fr;gap:18px}
  .band{padding:88px 0 96px}
  .bcard{padding:22px 18px 18px}
  .bcard h3{font-size:20px}
  .bstats{grid-template-columns:1fr 1fr;gap:14px 12px}
  .sgrid{grid-template-columns:1fr 1fr;column-gap:18px;margin-top:36px}
  .sgrid li:nth-child(n+11){display:none}
  .s-foot{flex-direction:column;gap:4px}
  .s-all{margin-left:0}
  .stance .h2{font-size:34px}
  .qa summary{font-size:16px;padding:18px 0}
  .qa p{padding-right:0;font-size:15px}
  .m-end{aspect-ratio:4/3}
  .end .h2{margin-top:40px}
  .foot{padding-top:44px}
}
"""

I = {
    "arrow": '<svg class="i" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "search": '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>',
    "video": '<svg viewBox="0 0 24 24"><path d="M8 6.5v11l9-5.5z"/></svg>',
    "image": '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 16l5-5 4 4 3-3 5 5"/></svg>',
    "moon": '<svg viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
    "menu": '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
}


def slot(klass, kind, icon, ratio, title, note):
    return (f'<figure class="slot {klass}" aria-label="{esc(kind)} 자리 — {esc(title)}"><span class="st">{I[icon]}{esc(kind)}</span>'
            f'<span class="sr">{esc(ratio)}</span><figcaption><b>{esc(title)}</b>{esc(note)}</figcaption></figure>')


def arrow_pct(c):
    """스테이징과 같은 등락 표기 — ▲/▼ + 색"""
    if c is None:
        return '<span class="flat">—</span>'
    if round(c, 2) > 0:
        return f'<span class="up">▲ {abs(c):.2f}%</span>'
    if round(c, 2) < 0:
        return f'<span class="down">▼ {abs(c):.2f}%</span>'
    return '<span class="flat">0.00%</span>'


def ymd(s):
    s = s.replace("-", "")
    return f"{int(s[4:6])}월 {int(s[6:8])}일"


def nav():
    return (f'<nav class="nav" id="nav"><div class="w nav-in"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a>'
            '<div class="links"><a href="#">홈</a><a href="#report">리포트</a><a href="#sectors">업종 분석</a><a href="#">관심종목</a><a href="#pricing">멤버십</a><a href="#brief">모닝브리핑</a></div>'
            f'<div class="right"><a class="login" href="#">로그인</a><button class="ib" id="themeBtn" aria-label="테마 전환">{I["moon"]}</button>'
            f'<button class="ib menu" aria-label="메뉴">{I["menu"]}</button></div></div></nav>')


def foot():
    return (f'<footer class="foot"><div class="w"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a>'
            '<p class="ftag">코스피·코스닥 상장사의 리포트, 업종 분석, 모닝브리핑.</p>'
            '<div class="fgrid"><div class="fcol"><h4>서비스</h4><a href="#">홈</a><a href="#">리포트</a><a href="#">업종 분석</a><a href="#">관심종목</a><a href="#">멤버십</a><a href="#">모닝브리핑</a></div>'
            '<div class="fcol"><h4>회사</h4><a href="#">회사 소개</a><a href="#">문의하기</a><a href="#">피드백</a></div>'
            '<div class="fcol"><h4>정책</h4><a href="#">이용약관</a><a class="pp" href="#">개인정보처리방침</a></div></div>'
            '<div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>'
            '<div class="copy">© 2026 KOSAI</div></div></footer>')


def search_box(ph="종목명 또는 종목코드 (예: 삼성전자, 005930)", ph_m="종목명 또는 종목코드"):
    """휴대폰은 칸이 좁아 예시가 잘리므로 짧은 안내(data-m)로 바꾼다."""
    return (f'<form class="search" role="search" onsubmit="return false">{I["search"]}<input placeholder="{ph}" data-m="{ph_m}" aria-label="종목 검색" autocomplete="off">'
            '<button class="btn btn-ink" type="button">리포트 찾기</button></form>')


def page():
    n_listed, n_rep = len(STOCKS["stocks"]), len(INDEX)
    n_src = med_sources()
    b = brief()
    f = b["_facts"]
    s = BY[SAMPLE]
    r = report(SAMPLE)
    asof = f"{BASE.month}월 {BASE.day}일 기준"

    # ── 첫 화면 — 눈썹(지금 신호) · H1(차별 하나) · 서브(어떻게 · 범위 · 갱신) · 검색 · 걱정 하나 ──
    hero = (f'<header class="hero w"><a class="pill" href="#brief"><b>모닝브리핑 제{b["_no"]}호</b>'
            f'<span>{kdate(b["date"])} {publish_time(b)}</span>{I["arrow"]}</a>'
            '<h1>증권사가 다루지 않는 종목도<br>리포트가 있습니다</h1>'
            '<p class="lede">실적 숫자는 공시에서 그대로 가져오고, 해석은 AI가 씁니다. '
            f'<span class="nw">코스피와 코스닥</span> {n_rep:,}개 종목을 다루고, 실적이 새로 공시되면 다시 씁니다.</p>'
            + search_box()
            + f'<p class="hint"><span>요약과 실적은 가입 없이 무료 · {asof}</span></p>'
            + f'<a class="more hero-alt" href="#">삼성전자 리포트 보기 {I["arrow"]}</a>'
            + slot("m-hero", "영상 · 3D", "video", "21 : 9 · 휴대폰 4 : 5", "첫 화면의 얼굴",
                   "권장: 실제 리포트 화면이 보이는 장면 — 예를 들어 좋은 빛 아래 노트북과 휴대폰에 열린 리포트. "
                   "6~8초, 소리 없이 반복, 멈춤 단추. 글자와 숫자는 그림에 넣지 않고 페이지가 얹습니다.")
            + '</header>')

    # ── 한 문단 선언 — 대안이 주는 것 · KOSAI 가 쓰는 것 ──
    stmt = ('<section class="statement w"><p><span>시세 앱과 뉴스는 오늘 무슨 일이 있었는지 알려 줍니다.</span> '
            'KOSAI 리포트는 그 회사가 무엇으로 돈을 벌고, 무엇을 조심해야 하는지 씁니다.</p></section>')

    # ── 리포트 한 편(코텍) ────────────────────────────
    q = r["quant"]["quarterly"]
    ops = [x["op"] for x in q]
    labels = [f'{x["q"][2:4]}Q{x["q"][-1]}' for x in q]
    ck = dict(uid="kc", bg="var(--bg)", fill="rgba(128,128,128,.28)", last="currentColor", text="currentColor", tick="rgba(128,128,128,.95)",
              axis="rgba(128,128,128,.4)", font="Pretendard,sans-serif", weight=500, radius=3)
    chart_d = chart_bars(ops, labels, w=520, h=190, fsize=13, tsize=12, top_pad=28, bottom_pad=30, **ck)
    chart_m = chart_bars(ops, labels, w=320, h=180, fsize=12.5, tsize=11.5, top_pad=26, bottom_pad=28, **{**ck, "uid": "km"})
    rd = r["reportDate"]
    bull = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bull"])
    bear = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bear"])
    card = (f'<article class="card" aria-label="{esc(s["name"])} 리포트에서 옮긴 부분"><div class="cd-top"><div><b>{esc(s["name"])}</b>'
            f'<span>{esc(s["market"])} · {esc(s["sector"])} · {SAMPLE}</span></div>'
            f'<div class="cd-px"><b>{grp(s["price"])}원</b>{arrow_pct(s["change"])}</div></div>'
            f'<p class="cd-meta">시가총액 {jo(s["mcap"])} · {rd[:4]}년 {int(rd[5:7])}월 {int(rd[8:10])}일 발행 · 재무 {ymd(r["quant"]["asOf"])} 기준 · 주가 {ymd(PRICE_DATE)} 종가</p>'
            f'<h3>{g(r["title"]["ko"])}</h3><p class="cd-lede">{g(r["lead"]["ko"])}</p>'
            f'<div class="cd-chart"><p>분기 영업이익<span>연결 · DART 공시 · {labels[0]}~{labels[-1]}</span></p><div class="cd">{chart_d}</div><div class="cm">{chart_m}</div></div>'
            f'<div class="bb"><div><h4>강세 요인<span>{len(r["bull"])}</span></h4><ul>{bull}</ul></div>'
            f'<div><h4>약세 요인<span>{len(r["bear"])}</span></h4><ul>{bear}</ul></div></div>'
            f'<p class="cd-foot"><span>참고 출처 {len(r.get("sources") or [])}개</span><span>리포트 13개 절 가운데 일부</span></p></article>')
    toc = "".join(f'<li><p class="tg">{t}{"<span>무료</span>" if free else ""}</p><p class="tn">{" · ".join(ns)}</p></li>' for t, ns, free in TOC)
    sec_report = ('<section class="sec w" id="report"><p class="eyebrow">리포트</p><h2 class="h2">좋은 이야기만 쓰지 않습니다</h2>'
                  '<div class="grid demo"><div class="c-l"><p class="sub">리포트마다 강세 요인 셋과 약세 요인 셋을 같은 무게로 씁니다. '
                  '사업 구조에서 종합 의견까지 순서가 정해져 있어, 처음 보는 회사도 익숙하게 읽힙니다.</p>'
                  f'<ul class="toc" aria-label="리포트 목차">{toc}</ul>'
                  f'<a class="more" href="#">{esc(s["name"])} 리포트 전체 보기 {I["arrow"]}</a></div>'
                  f'<div class="c-r">{card}<p class="fine card-note">{esc(s["name"])} 리포트에서 옮긴 부분입니다. 문장과 숫자는 고치지 않았습니다. '
                  'KOSAI 리포트는 공개된 정보로 AI가 쓴 참고 자료이며, 매수·매도 의견이나 목표주가는 없습니다.</p></div></div></section>')

    # ── 다시 쓰는 리포트 + 숫자 · 출처 · 한계 ──────────────
    recent = sorted(((rr.get("reportTs") or rr.get("reportDate") or "", tk, rr) for tk, rr in INDEX.items() if tk in BY), reverse=True)[:6]
    n7 = sum(1 for rr in INDEX.values() if rr.get("reportDate") and (BASE - datetime.date.fromisoformat(rr["reportDate"])).days <= 7)
    rows = "".join(f'<a class="row" href="#"><div><span class="nm">{esc(BY[tk]["name"])}</span><span class="cd">{esc(BY[tk]["market"])} · {esc(BY[tk]["sector"])}</span></div>'
                   f'<span class="tt">{g(rr["title"]["ko"])}</span><span class="mc">시가총액 {jo(BY[tk]["mcap"])}</span><span class="dt">{ymd(rr["reportDate"])}</span></a>'
                   for _, tk, rr in recent)
    sec_fresh = ('<section class="sec w" id="fresh"><p class="eyebrow">갱신</p><h2 class="h2">공시가 나오면 리포트도 바뀝니다</h2>'
                 '<p class="sub">회사가 분기·반기·사업보고서를 DART에 내면 최신 실적으로 다시 씁니다. 주가와 시가총액, PER은 거래일마다 저녁에 갱신합니다.</p>'
                 f'<div class="fresh"><p class="rows-cap">최근에 쓴 리포트<span>지난 7일 {n7}편 · {asof}</span></p><div class="rows">{rows}</div>'
                 f'<a class="more" href="#">최근 갱신된 리포트 보기 {I["arrow"]}</a></div>'
                 '<div class="trust"><div><h3>실적 숫자는 AI가 쓰지 않습니다</h3>'
                 '<p>분기·연간 실적과 재무제표 숫자는 금융감독원 전자공시(DART)에서, 주가는 한국거래소에서 직접 가져옵니다. AI는 그 숫자를 근거로 해석을 씁니다.</p></div>'
                 '<div><h3>참고한 자료는 링크로 남깁니다</h3>'
                 f'<p>사업 현황과 업황, 뉴스를 찾아 읽은 자료를 리포트 끝에 모아 둡니다. 한 편에 보통 {n_src}개입니다.</p></div>'
                 '<div><h3>AI가 씁니다. 그래서 틀릴 수 있습니다.</h3><p>틀린 곳을 알려 주시면 확인해서 고칩니다.</p>'
                 f'<a class="more" href="#">틀린 곳 알리기 {I["arrow"]}</a></div></div></section>')

    # ── 모닝브리핑 — 어두운 띠 ─────────────────────────
    secs = "".join(f"<li><span>{g(x['heading']['ko'])}</span></li>" for x in b["sections"])
    stats = ""
    for k in ["코스피", "나스닥", "WTI", "미 10년물"]:
        v, c = f[k]
        chg = (f'<small class="{cls(c)}">{"+" if c > 0 else ""}{c:.2f}%p</small>' if k.endswith("10년물") else f"<small>{arrow_pct(c)}</small>")
        stats += f"<div><dt>{k}</dt><dd>{v}{chg}</dd></div>"
    first = briefs()[0][:10]
    sec_brief = ('<section class="band" id="brief"><div class="w"><p class="eyebrow">모닝브리핑</p><h2 class="h2">장이 열리기 전에 읽는 한 편</h2><div class="grid bgrid"><div class="c-l">'
                 '<p class="sub">밤사이 해외 시장에서 일어난 일 가운데 한국 시장에 닿는 것만 골라 씁니다. 움직인 이유가 분명한 숫자에는 이유를 한 구절 붙입니다.</p>'
                 f'<a class="more" href="#">제{b["_no"]}호 읽기 {I["arrow"]}</a>'
                 f'<p class="fine">거래일 아침, 보통 7시 30분 무렵에 나옵니다 · {ymd(first)} 창간</p></div>'
                 f'<div class="c-r"><article class="bcard" aria-label="모닝브리핑 제{b["_no"]}호"><p class="bm">제{b["_no"]}호 · {kdate(b["date"])} {publish_time(b)} 발행</p>'
                 f'<h3>{g(b["title"]["ko"])}</h3><ol class="bsec">{secs}</ol><dl class="bstats">{stats}</dl></article></div></div></div></section>')

    # ── 업종 ─────────────────────────────────────────
    cnt = Counter(c for x in STOCKS["stocks"] for c in (x.get("categories") or []) if c != "기타")
    top = cnt.most_common()
    mx = top[0][1]
    grid = "".join(f'<li><span class="sn">{esc(k)}<b>{v:,}</b></span><span class="bar"><i style="width:{v / mx * 100:.1f}%"></i></span></li>' for k, v in top)
    sec_sectors = ('<section class="sec w" id="sectors"><p class="eyebrow">업종 분석</p><h2 class="h2">업종 안에서 회사를 봅니다</h2>'
                   f'<p class="sub">{len(top)}개 업종마다 업황과 주요 종목을 따로 정리합니다. 한 회사를 읽을 때 그 업종의 흐름도 함께 볼 수 있습니다.</p>'
                   f'<ul class="sgrid">{grid}</ul><div class="s-foot"><p class="fine">숫자는 업종에 속한 종목 수입니다. 한 종목이 두 업종에 들기도 합니다.</p>'
                   f'<a class="more s-all" href="#">{len(top)}개 업종 분석 보기 {I["arrow"]}</a></div></section>')

    # ── 하지 않는 것 — 그리고 누구를 위해 쓰는가 ─────────────
    sec_stance = ('<section class="sec w"><div class="grid stance"><h2 class="h2 c-l">사라, 팔라<br>하지 않습니다</h2>'
                  '<div class="c-r"><p>매수·매도 의견도, 목표주가도 내지 않습니다. 판단에 필요한 사실과 근거를 모으고, 판단은 읽는 분께 맡깁니다.</p>'
                  '<p>직접 종목을 고르는 분을 위해 씁니다. 시세와 주문은 쓰던 앱에서, 사기 전의 공부는 여기서.</p></div></div></section>')

    # ── 멤버십 ───────────────────────────────────────
    plans = [
        ("무료", "0원", "", "종목을 처음 살필 때", ["핵심 지표 — 현재가·시가총액·PER", "리포트 개요와 요약", "사업 구조", "최근 4개 연도·5개 분기 실적"],
         '<a class="btn btn-soft" href="#">무료 리포트 보기</a>', "가입 없이 읽을 수 있습니다"),
        ("BASIC", "9,900원", " / 월", "보유 종목을 꾸준히 챙길 때", ["리포트 전체 — 실적 분석부터 종합 의견까지", "하루 5개 종목"],
         '<a class="btn btn-ink" href="#">BASIC 시작하기</a>', "부가세 포함 · 매달 자동 결제 · 언제든 해지"),
        ("PRO", "14,900원", " / 월", "여러 종목을 견줘 볼 때", ["리포트 전체 — 실적 분석부터 종합 의견까지", "하루 15개 종목"],
         '<a class="btn btn-ink" href="#">PRO 시작하기</a>', "부가세 포함 · 매달 자동 결제 · 언제든 해지"),
    ]
    ph = "".join(f'<div class="plan"><p class="plan-name">{nm}</p><p class="plan-price">{pr}<small>{unit}</small></p><p class="plan-sub">{sub}</p><ul>'
                 + "".join(f"<li>{esc(x)}</li>" for x in fs) + f'</ul>{cta}<p class="under">{under}</p></div>'
                 for nm, pr, unit, sub, fs, cta, under in plans)
    sec_price = ('<section class="sec w" id="pricing"><p class="eyebrow">멤버십</p><h2 class="h2">리포트 요약은 무료입니다</h2>'
                 '<p class="sub">모든 리포트의 요약과 사업 구조, 최근 실적은 가입 없이 읽을 수 있습니다. 실적 분석부터 종합 의견까지, 리포트 전체는 구독하면 열립니다.</p>'
                 '<p class="fine same">두 유료 플랜의 내용은 같습니다. 다른 것은 하루에 볼 수 있는 종목 수뿐입니다.</p>'
                 f'<div class="plans">{ph}</div></section>')

    # ── 자주 묻는 질문 — 믿어도 되나 · 추천인가 · 무엇이 다른가 · 누가 · 해지 ──
    qa = [
        ("AI가 쓴 리포트, 믿어도 되나요?", "리포트는 AI가 쓰고, 그래서 틀릴 수 있습니다. 다만 실적과 재무제표 숫자는 AI가 쓰지 않고 DART 공시에서 그대로 가져옵니다. "
         "글을 쓰며 참고한 자료는 리포트 끝에 링크로 남기니, 중요한 내용은 원문에서 한 번 더 확인하세요. 틀린 곳을 알려 주시면 확인해서 고칩니다."),
        ("종목을 추천해 주나요?", "아닙니다. KOSAI는 매수·매도 의견도, 목표주가도 내지 않습니다. 리포트는 판단을 돕는 참고 자료이고, 판단과 그 결과는 읽는 분의 몫입니다."),
        ("증권사 리포트와 무엇이 다른가요?", f"증권사 리포트는 주로 규모가 큰 회사를 다룹니다. KOSAI는 코스피·코스닥 상장사 {n_listed:,}곳 가운데 {n_rep:,}곳의 리포트를 씁니다. "
         f"나머지 {n_listed - n_rep}곳은 새로 상장해 준비하고 있습니다. 증권사 리포트가 있는 종목이라면 함께 읽고, 없는 종목이라면 여기서 시작해 보세요."),
        ("누가 만드나요?", "코사이가 만듭니다. 리포트는 AI가 쓰고, 코사이는 AI가 따를 작성 규칙을 정하고 저장하기 전에 결함 있는 글을 거르는 검사를 만들어 고칩니다. "
         "사업자 정보는 이 페이지 맨 아래에 있습니다."),
        ("구독은 언제든 해지할 수 있나요?", "설정의 구독 항목에서 바로 해지할 수 있습니다. 해지한 뒤에도 이미 결제한 기간이 끝날 때까지 그대로 볼 수 있습니다."),
    ]
    qh = "".join(f'<details class="qa"{" open" if i == 0 else ""}><summary>{esc(qq)}</summary><p>{g(aa)}</p></details>' for i, (qq, aa) in enumerate(qa))
    sec_faq = f'<section class="sec w"><div class="grid faq"><h2 class="h2 c-l">자주 묻는 질문</h2><div class="c-r">{qh}</div></div></section>'

    # ── 마무리 — 첫 약속을 짧게 한 번 더, 같은 검색창 ──────────
    picks = ["005930", "000660", SAMPLE, "093240"]
    chips = "".join(f'<a href="#">{esc(BY[t]["name"])}<span>{jo(BY[t]["mcap"])}</span></a>' for t in picks if t in BY)
    sec_end = ('<section class="sec w end">'
               + slot("m-end", "이미지", "image", "21 : 8 · 휴대폰 4 : 3", "마무리 장면",
                      "첫 화면과 같은 빛과 재질로 만든 정지 그림 한 장. 첫 화면 영상의 마지막 장면을 써도 됩니다.")
               + f'<h2 class="h2">찾는 종목의 리포트가<br>이미 있습니다</h2>{search_box()}<div class="chips">{chips}</div></section>')

    js = ("<script>(function(){var n=document.getElementById('nav');function s(){n.classList.toggle('on',scrollY>4)}addEventListener('scroll',s,{passive:true});s();"
          "var r=document.documentElement,b=document.getElementById('themeBtn');try{var t=localStorage.getItem('kos-landing-theme');if(t)r.setAttribute('data-theme',t)}catch(e){}"
          "b&&b.addEventListener('click',function(){var d=r.getAttribute('data-theme')==='dark'?'light':'dark';r.setAttribute('data-theme',d);try{localStorage.setItem('kos-landing-theme',d)}catch(e){}});"
          "if(matchMedia('(max-width:720px)').matches)document.querySelectorAll('input[data-m]').forEach(function(i){i.placeholder=i.getAttribute('data-m')})})();</script>")
    h1 = "증권사가 다루지 않는 종목도 리포트가 있습니다"
    desc = f"코스피·코스닥 {n_rep:,}개 종목의 리포트. 실적 숫자는 공시에서 그대로 가져오고, 해석은 AI가 씁니다."
    head = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#f9f8f6"><title>KOSAI — {h1}</title>'
            f'<meta name="description" content="{desc}"><meta property="og:title" content="{h1}">'
            f'<meta property="og:description" content="코스피·코스닥 {n_rep:,}개 종목의 리포트 · 요약은 무료">'
            f'<link rel="stylesheet" href="{FONTS}/pretendard-subset.css"><link rel="stylesheet" href="landing.css"></head><body>')
    return (head + nav() + f"<main>{hero}{stmt}{sec_report}{sec_fresh}{sec_brief}{sec_sectors}{sec_stance}{sec_price}{sec_faq}{sec_end}</main>"
            + foot() + js + "</body></html>")


def med_sources():
    """화면에 나오는 리포트(v2 + v2 없는 v1)의 참고 출처 수 중앙값 — '보통 N개'."""
    import json
    import statistics
    n = []
    for tk in INDEX:
        for d in ("data/reports_v2", "data/reports"):
            p = os.path.join(ROOT, d, f"{tk}.json")
            if os.path.exists(p):
                rr = json.load(open(p, encoding="utf-8"))
                if isinstance(rr, dict):
                    n.append(len(rr.get("sources") or []))
                break
    return round(statistics.median(n))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "landing.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    html = page()
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    print(f"preview/concepts/landing/index.html {len(html):,}자 · landing.css {len(CSS):,}자")
