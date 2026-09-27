"""랜딩 시안 2판 — 스테이징 디자인 그대로(토큰 · 헤더 · 부품 · 너비 · 글꼴) + 카피·구성 이론.

    python3 scripts/concepts/landing.py      # → preview/concepts/landing/index.html · landing.css

  · 이론과 카피 가이드: reports/카피라이팅과 랜딩페이지 구성 이론 총정리.md (노트 15갈래는 research_notes/ 같은 이름 폴더).
  · 그림·영상·3D 는 만들지 않는다. 들어갈 자리만 표시한다(종류 · 비율 · 들어갈 내용). 유료화 뒤 들어갈 법정 문구 자리도 같은 식으로 표시한다.
  · 숫자는 전부 data/ 에서 계산하고 기준일을 붙인다. 사실 주장은 보고서 4부 8절(사실 장부)과 맞춰 본다 — 손으로 적은 숫자·날짜 없음.
  · 스테이징·실사이트 파일은 건드리지 않는다.
"""
import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from data import (ROOT, BY, STOCKS, INDEX, esc, grp, jo, kdate, report, brief, publish_time, briefs,  # noqa: E402
                  now_date, PRICE_DATE)
from common import g  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from stock_page import fwon  # noqa: E402  # 실적 라벨 — 스테이징·실사이트와 같은 표기('24억' · '-64,097,966원')

OUT = os.path.join(ROOT, "preview", "concepts", "landing")
ASSETS = "../../../assets"
FONTS = "../../../fonts"
SAMPLE = "300080"   # 플리토 — 코스닥 소형주. 흑자 전환 뒤 1분기 적자 → 2분기 흑자: 제목·차트·강세/약세가 모두 '좋은 이야기만'이 아니다(결함 0)
HERO_REPORT = "005930"                     # 첫 화면 보조 링크 — 누구나 아는 대형주 한 편
CHIPS = ["005930", "000660", SAMPLE, "093240"]   # 마무리 칩 — 시가총액 1,669조부터 182억까지
BASE = datetime.date.fromisoformat(f"{now_date()[:4]}-{now_date()[4:6]}-{now_date()[6:8]}")   # 데이터의 '오늘'(리포트·시세·브리핑 가운데 가장 늦은 날)
MARKETS = "코스피·코스닥·코넥스"          # stocks.js 의 시장 셋 — 코넥스 107곳도 리포트가 있다
TOC = [("무엇으로 돈을 버는 회사인가", ["리포트 개요", "사업 구조", "실적 추이"], True),
       ("실적의 배경과 전망", ["실적 분석", "산업 분석", "전망", "밸류에이션"], False),
       ("강세와 약세, 다음 일정", ["강세 요인", "약세 요인", "리스크 요인", "다음 체크포인트", "종합 의견"], False),
       ("근거", ["참고 출처"], True)]      # staging/stock.html 의 실제 목차 13개 절을 네 묶음으로(무료 = True)

CSS = r"""
:root{
  --bg:#f9f8f6; --surface:#fff; --surface-2:#f1efeb; --slot:#ebe9e5;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-62:rgba(20,20,20,.62); --ink-30:rgba(20,20,20,.3);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14); --bar:rgba(20,20,20,.2);
  --up:#c8102e; --down:#1e5fbf;
  --band:#141414; --band-ink:#f2f1ee; --band-62:rgba(242,241,238,.62); --band-hair:rgba(255,255,255,.12); --band-up:#f0655f; --band-down:#6f9cf5;
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --gap:24px; --sec:168px; --sec-s:112px; --sec-l:216px; --nav-bar:rgba(249,248,246,.72);
  color-scheme:light;
}
:root[data-theme="dark"]{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20; --slot:#1b1b1d;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-62:rgba(236,236,234,.62); --ink-30:rgba(236,236,234,.3);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14); --bar:rgba(236,236,234,.4);
  --up:#f0655f; --down:#6f9cf5;
  --band:#1c1c1e; --band-ink:#ececea; --band-62:rgba(236,236,234,.62); --band-hair:rgba(255,255,255,.1);
  --nav-bar:rgba(13,13,14,.72);
  color-scheme:dark;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px;overflow-x:clip}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;
  word-break:keep-all;overflow-wrap:anywhere}
::selection{background:rgba(20,20,20,.14)} :root[data-theme="dark"] ::selection{background:rgba(255,255,255,.22)}
a{color:inherit;text-decoration:none}
h1,h2,h3,h4,p,ul,ol,figure,dl,dd{margin:0}
ul,ol{padding:0;list-style:none}
button,input{font:inherit;color:inherit}
.w{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}
.nw{white-space:nowrap}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--ink-62)}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.band :focus-visible{outline-color:var(--band-ink)}
svg.i{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* 가운뎃점 목록 — 항목은 한 덩어리, 점은 CSS 로 앞 항목 끝에 붙인다(점이 줄 첫머리에 오지 않고, 이름 속 '·'와 헷갈리지 않게) */
.dl{display:flex;flex-wrap:wrap;row-gap:2px}
.dl>span{white-space:nowrap}
.dl>span:not(:last-child)::after{content:"";display:inline-block;width:3px;height:3px;border-radius:50%;background:currentColor;opacity:.5;margin:0 9px;vertical-align:middle;transform:translateY(-2px)}

/* 머리 — 스테이징 그대로(60px · 맨 위 투명 · 내리면 흐린 띠) */
.nav{position:sticky;top:0;z-index:50;height:60px;display:flex;align-items:center;transition:background-color .2s,box-shadow .2s}
.nav.scrolled{background:var(--nav-bar);box-shadow:0 1px 0 var(--hair);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px)}
.nav-in{width:100%;max-width:var(--wrap);margin:0 auto;padding:0 var(--pad);display:flex;align-items:center;justify-content:space-between;position:relative}
.brand{display:flex;align-items:center;min-height:44px}
.brand img{height:14px;display:block} .brand .dk{display:none} :root[data-theme="dark"] .brand .lt{display:none} :root[data-theme="dark"] .brand .dk{display:block}
.links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:28px}
.links a{font:500 14px/1 var(--font);color:var(--ink-72);transition:color .12s} .links a:hover{color:var(--ink)}
.right{display:flex;align-items:center;gap:6px}
.login{font:600 13px/1 var(--font);color:var(--ink-72);padding:15px 10px} .login:hover{color:var(--ink)}
.ib{width:44px;height:44px;border:0;background:transparent;color:var(--ink-72);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;border-radius:10px} .ib:hover{color:var(--ink)}
.ib svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.menu{display:none} .menu .x{display:none} .nav.menu-open .menu .ham{display:none} .nav.menu-open .menu .x{display:block}
.mmenu{display:none;position:fixed;top:60px;left:0;right:0;bottom:0;z-index:49;background:var(--bg);flex-direction:column;padding:22px var(--pad) max(28px,env(safe-area-inset-bottom));overflow:auto;overscroll-behavior:contain}
.mm-links{display:flex;flex-direction:column} .mm-links a{display:block;padding:10px 0;font:600 28px/36px var(--font);letter-spacing:-.02em;color:var(--ink-72)}
.mmenu .sep{height:1px;background:var(--hair);margin:20px 0 22px}
.mm-auth{display:flex;flex-wrap:wrap;gap:12px 24px} .mm-auth a{font:600 16px/24px var(--font);color:var(--ink);padding:10px 0}
.mm-foot{margin-top:auto;padding-top:32px;display:flex;flex-wrap:wrap;gap:6px 18px} .mm-foot a{font:400 13px/20px var(--font);color:var(--ink-62);padding:6px 0}
#kosEdgeTop,#kosEdgeBot{display:none}
@media (hover:none) and (pointer:coarse){#kosEdgeTop,#kosEdgeBot{display:block;position:fixed;left:0;right:0;height:12px;z-index:60;pointer-events:none;opacity:.2;background:var(--bg)} #kosEdgeTop{top:0} #kosEdgeBot{bottom:0}}

/* 단추 — 스테이징 btn · btn-ink · btn-soft */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:999px;border:0;
  font:600 14px/1 var(--font);white-space:nowrap;cursor:pointer;transition:opacity .12s,background-color .12s}
.btn-ink{background:var(--ink);color:var(--bg)} .btn-ink:hover{opacity:.9}
.btn-soft{background:var(--surface-2);color:var(--ink)} .btn-soft:hover{background:var(--line)}
.more{display:inline-flex;align-items:center;gap:6px;min-height:44px;font:600 15px/1 var(--font);color:var(--ink)}
.more svg.i{width:15px;height:15px;transition:transform .2s}
.more:hover svg.i{transform:translateX(3px)}

/* 검색 — 스테이징 밑줄 검색창(초점은 밑줄 2px) */
.search{display:flex;align-items:center;gap:12px;height:60px;border-bottom:1px solid var(--line);transition:border-color .15s,box-shadow .15s}
.search:focus-within{border-bottom-color:var(--ink);box-shadow:0 1px 0 0 var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-62);flex:none}
.search input{flex:1;min-width:0;align-self:stretch;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0}
.search input::placeholder{color:var(--ink-62)}
.search .btn{height:40px;padding:0 18px}

/* 첫 화면 — 제목 · 서브 · 검색 · 걱정 하나 · 제품이 보이는 장면 */
.hero{padding-top:72px}
.hero h1{max-width:1000px;font:600 clamp(40px,6.2vw,88px)/1.14 var(--font);letter-spacing:-.04em;text-wrap:balance}
.hero h1 br.m{display:none}
.hero .lede{margin-top:28px;max-width:560px;font:400 18px/1.7 var(--font);color:var(--ink-72);text-wrap:pretty}
.hero .search{margin-top:40px;max-width:600px}
.hint-row{max-width:600px;margin-top:10px;display:flex;justify-content:space-between;align-items:center;gap:4px 20px;flex-wrap:wrap}
.hint{font:400 13px/1.5 var(--font);color:var(--ink-62)}

/* 그림 자리 — 만들지 않고 표시만 */
.slot{position:relative;border-radius:8px;overflow:hidden;background-color:var(--slot);
  background-image:repeating-linear-gradient(-45deg,rgba(128,128,128,.07) 0 1px,transparent 1px 12px)}
.slot .st{position:absolute;top:16px;left:16px;display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 12px 0 10px;border-radius:999px;background:var(--surface);
  font:600 12px/1 var(--font);color:var(--ink)}
.slot .st svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.slot .sr{position:absolute;top:23px;right:18px;font:500 12px/1 var(--font);color:var(--ink-62)}
.slot figcaption{position:absolute;left:18px;right:18px;bottom:16px;max-width:560px;font:400 13px/1.6 var(--font);color:var(--ink-62);text-wrap:pretty}
.slot figcaption b{display:block;margin-bottom:4px;font:600 14px/1.4 var(--font);color:var(--ink)}
.m-hero{margin-top:56px;aspect-ratio:21/9}
/* 유료화 뒤 들어갈 문구 자리 — 그림 자리처럼 표시만 */
.note-slot{border:1px dashed var(--line);border-radius:8px;padding:14px 16px;font:400 13px/1.6 var(--font);color:var(--ink-62)}
.note-slot b{display:block;margin-bottom:2px;font-weight:600;color:var(--ink-72)}

/* 절 머리 — 작은 이름표 · 요점을 말하는 문장 하나 · 설명은 작게 */
.sec{padding-top:var(--sec)} .sec.s{padding-top:var(--sec-s)} .sec.l{padding-top:var(--sec-l)}
.eyebrow{margin-bottom:18px;font:600 13px/1 var(--font);color:var(--ink-62)}
.band .eyebrow{color:var(--band-62)}
.h2{font:600 clamp(30px,3.9vw,50px)/1.2 var(--font);letter-spacing:-.03em;text-wrap:balance}
.sub{margin-top:20px;max-width:520px;font:400 17px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}
.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:var(--gap)}
.c-l{grid-column:1/6} .c-r{grid-column:7/13}
.fine{font:400 13px/1.65 var(--font);color:var(--ink-62);text-wrap:pretty}

/* 한 문단 선언 — 대안이 알려 주는 것(옅게) 뒤에 KOSAI 가 쓰는 것(진하게). 움직이지 않는다 */
.statement{padding-top:var(--sec-s)}
.statement p{max-width:920px;font:600 clamp(26px,3.2vw,42px)/1.42 var(--font);letter-spacing:-.028em;text-wrap:pretty}
.statement p span{color:var(--ink-62)}

/* 리포트 한 편 */
.demo{margin-top:56px;align-items:start}
.demo .c-l{position:sticky;top:96px}
.toc{margin-top:36px;border-top:1px solid var(--hair)}
.toc li{padding:15px 0 14px;border-bottom:1px solid var(--hair)}
.toc .tg{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font:600 15px/1.4 var(--font)}
.toc .tg span{font:500 12px/1 var(--font);color:var(--ink-62)}
.toc .tn{margin-top:5px;font:400 14px/1.6 var(--font);color:var(--ink-62)}
.demo .c-l>.more{margin-top:14px}
.card{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:32px 32px 28px}
.cd-top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.cd-top b{display:block;font:700 18px/1.25 var(--font)}
.cd-top .dl{margin-top:6px;font:400 13px/1.4 var(--font);color:var(--ink-62)}
.cd-px{text-align:right} .cd-px b{font-size:17px} .cd-px span{display:block;margin-top:6px;font:600 13px/1 var(--font)}
.cd-px .up{color:var(--up)} .cd-px .down{color:var(--down)} .cd-px .flat{color:var(--ink-62)}
.cd-meta{margin-top:16px;padding-bottom:18px;border-bottom:1px solid var(--hair);font:400 12px/1.5 var(--font);color:var(--ink-62)}
.card h3{margin-top:22px;font:700 24px/1.32 var(--font);letter-spacing:-.025em;text-wrap:balance}
.cd-lede{margin-top:12px;font:400 15px/1.72 var(--font);color:var(--ink-72);text-wrap:pretty}
.cd-chart{margin-top:24px;padding:18px 18px 10px;border-radius:12px;background:var(--bg)}
.cd-chart p{display:flex;flex-wrap:wrap;justify-content:space-between;gap:2px 12px;font:600 13px/1.3 var(--font);white-space:nowrap} .cd-chart p span{font-weight:400;color:var(--ink-62)}
/* 실적 막대 — 막대는 SVG(가로로만 늘어남), 라벨은 HTML 12px 고정(스테이징 stock_page.bar_chart 와 같은 방식). 적자는 0선 아래 */
.ch{position:relative;margin-top:10px} .ch svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible}
.ch-base{stroke:var(--line);stroke-width:1} .ch-op{fill:var(--bar)} .ch-last{fill:var(--ink)}
.ch-val,.ch-lab{position:absolute;white-space:nowrap;font:500 12px/1 var(--font);color:var(--ink-62);font-variant-numeric:tabular-nums}
.ch-val{transform:translate(-50%,-100%)} .ch-val.dn,.ch-lab{transform:translateX(-50%)} .ch-val.last{color:var(--ink);font-weight:600}
.bb{margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:24px}
.bb h4{font:600 13px/1 var(--font);padding-bottom:10px;border-bottom:1px solid var(--line)}
.bb h4 span{margin-left:6px;font-weight:400;color:var(--ink-62)}
.bb li{padding:10px 0;border-bottom:1px solid var(--hair);font:500 14px/1.45 var(--font);color:var(--ink-72)}
.cd-foot{margin-top:18px;display:flex;justify-content:space-between;gap:12px;font:400 12px/1.4 var(--font);color:var(--ink-62)}
.card-note{margin-top:16px}

/* 다시 쓰는 리포트 */
.fresh{margin-top:56px}
.rows{border-top:1px solid var(--line)}
.row{display:grid;grid-template-columns:200px minmax(0,1fr) 132px 72px;gap:24px;align-items:center;padding:17px 0;border-bottom:1px solid var(--hair)}
.row .nm{font:600 15px/1.3 var(--font)} .row .cd{display:block;margin-top:4px;font:400 12px/1 var(--font);color:var(--ink-62)}
.row .tt{font:400 15px/1.45 var(--font)}
.row .mc,.row .dt{text-align:right;font:400 13px/1 var(--font);color:var(--ink-62);white-space:nowrap}
.row:hover .tt{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:4px}
.rows-cap{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin:0 0 12px;font:600 13px/1 var(--font)}
.rows-cap .dl{font-weight:400;color:var(--ink-62)}
.fresh>.more{margin-top:6px}
.trust{margin-top:96px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 var(--gap);align-items:start;border-top:1px solid var(--line)}
.trust>div{padding-top:26px}
.trust h3{font:600 19px/1.4 var(--font);letter-spacing:-.015em;text-wrap:balance}
.trust p{margin-top:10px;font:400 15px/1.7 var(--font);color:var(--ink-72);text-wrap:pretty}
.trust .more{margin-top:4px;font-size:14px}

/* 모닝브리핑 — 어두운 띠 하나 */
.band{margin-top:var(--sec);padding:128px 0 136px;background:var(--band);color:var(--band-ink)}
:root[data-theme="dark"] .band{box-shadow:inset 0 1px 0 var(--hair),inset 0 -1px 0 var(--hair)}
.band .sub{color:var(--band-62);margin-top:0}
.bgrid{margin-top:48px;align-items:stretch}
.bgrid .c-l{display:flex;flex-direction:column}
.band .more{color:var(--band-ink);margin-top:20px;align-self:flex-start}
.band .fine{color:var(--band-62);margin-top:6px}
.m-brief{margin-top:auto;aspect-ratio:3/2;background-color:#1e1e20}
.m-brief .st{background:#2a2a2d;color:var(--band-ink)} .m-brief .sr,.m-brief figcaption{color:var(--band-62)} .m-brief figcaption b{color:var(--band-ink)}
.bcard{border:1px solid var(--band-hair);border-radius:16px;padding:30px 30px 26px}
.bcard .bm{font:400 13px/1.4 var(--font);color:var(--band-62)}
.bcard h3{margin-top:14px;font:700 24px/1.36 var(--font);letter-spacing:-.025em;text-wrap:balance}
.bsec{margin-top:22px;border-top:1px solid var(--band-hair);counter-reset:b}
.bsec li{counter-increment:b;display:grid;grid-template-columns:22px 1fr;padding:11px 0;border-bottom:1px solid var(--band-hair);font:400 14px/1.5 var(--font);color:var(--band-ink)}
.bsec li::before{content:counter(b);color:var(--band-62)}
.bstats{margin-top:22px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.bstats dt{font:500 12px/16px var(--font);color:var(--band-62)}
.bstats dd{margin-top:6px;font:600 17px/22px var(--font);letter-spacing:-.01em;white-space:nowrap}
.bstats dd small{display:block;margin-top:2px;font:500 12px/16px var(--font)}
.band .up{color:var(--band-up)} .band .down{color:var(--band-down)}

/* 업종 */
.sgrid{margin-top:56px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));column-gap:var(--gap);border-top:1px solid var(--line)}
.sgrid a{display:block;padding:16px 0 14px;border-bottom:1px solid var(--hair)}
.sgrid .sn{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font:500 15px/1.3 var(--font)}
.sgrid .sn b{font:400 13px/1 var(--font);color:var(--ink-62)}
.sgrid .bar{display:block;height:2px;margin-top:11px;background:var(--hair)}
.sgrid .bar i{display:block;height:100%;background:var(--ink-30)}
.sgrid a:hover .bar i,.sgrid a:focus-visible .bar i{background:var(--ink)}
.s-foot{margin-top:16px;display:flex;justify-content:space-between;gap:16px;align-items:center}
.s-all{margin-left:auto}

/* 하지 않는 것 */
.stance{align-items:end}
.stance .h2{font-size:clamp(34px,4.6vw,60px);line-height:1.14}
.stance p{font:400 17px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}
.stance p+p{margin-top:16px;color:var(--ink-62);font-size:15px}

/* 멤버십 — 스테이징 요금제 세 단(상자 없이 가는 선) */
.same{margin-top:40px}
.plans{margin-top:16px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid var(--line)}
.plan{display:flex;flex-direction:column;padding:28px 0 36px;border-bottom:1px solid var(--hair)}
.plan+.plan{border-left:1px solid var(--hair);padding-left:32px}
.plan:not(:last-child){padding-right:32px}
.plan-name{font:600 12px/16px var(--font);letter-spacing:.06em;color:var(--ink-62)} .plan-name.ko{letter-spacing:0}
.plan-price{margin-top:12px;font:700 36px/44px var(--font);letter-spacing:-.02em}
.plan-price small{margin-right:6px;font:500 15px/1 var(--font);letter-spacing:0;color:var(--ink-62)}
.plan-sub{margin-top:6px;font:400 14px/1.5 var(--font);color:var(--ink-72);min-height:42px}
.plan ul{margin:18px 0 24px;border-top:1px solid var(--hair);flex:1}
.plan li{padding:10px 0;border-bottom:1px solid var(--hair);font:400 14px/1.5 var(--font);color:var(--ink)}
.plan .btn{width:100%}
.plan .under{margin-top:10px;font:400 12px/1.5 var(--font);color:var(--ink-62);justify-content:center;min-height:18px}
.price-fine{margin-top:20px}
.price-note{margin-top:16px;max-width:760px}

/* 질문 */
.faq{margin-top:48px;align-items:start}
.qa{border-top:1px solid var(--hair)} .qa:last-child{border-bottom:1px solid var(--hair)}
.qa summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:20px 0;font:600 17px/1.45 var(--font)}
.qa summary::-webkit-details-marker{display:none}
.qa summary::after{content:"+";flex:none;font:400 22px/1 var(--font);color:var(--ink-30)}
.qa[open] summary::after{content:"–";color:var(--ink-62)}
.qa p{padding:0 40px 22px 0;font:400 16px/1.75 var(--font);color:var(--ink-72);text-wrap:pretty}

/* 마무리 — 첫 약속을 짧게 한 번 더 · 같은 검색창 · 옆에 그림 한 장 */
.end{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:var(--gap);align-items:center}
.end>.h2,.end>.search,.end>.chips{grid-column:1/6}
.end>.m-end{grid-column:7/13;grid-row:1/4;aspect-ratio:1/1}
.end .h2{font-size:clamp(30px,3.3vw,42px)}
.end .search{margin-top:32px}
.chips{margin-top:16px;display:flex;flex-wrap:wrap;gap:8px;align-self:start}
.chips a{display:inline-flex;align-items:center;height:40px;padding:0 14px;border-radius:999px;background:var(--surface-2);font:500 14px/1 var(--font);color:var(--ink);transition:background-color .12s}
.chips a:hover{background:var(--line)}
.chips a span{margin-left:6px;font-weight:400;color:var(--ink-62)}

/* 꼬리 — 스테이징 그대로(한 줄 소개 · 회사 소개 · 개인정보 처리방침 구분 표시만 고침) */
.foot{margin-top:var(--sec);border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand{min-height:0} .foot .brand img{height:13px}
.ftag{margin-top:14px;font:400 14px/22px var(--font);color:var(--ink-72);max-width:320px}
.fgrid{display:grid;grid-template-columns:auto auto auto;justify-content:start;column-gap:72px;margin-top:32px}
.fcol{display:flex;flex-direction:column}
.fcol h4{margin:0 0 6px;font:600 12px/16px var(--font);color:var(--ink-62)}
.fcol a{font:400 14px/20px var(--font);color:var(--ink-72);padding:6px 0;white-space:nowrap} .fcol a:hover{color:var(--ink)}
.fcol a.pp{font-weight:600;color:var(--ink)}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-62)}
.foot .note-slot{margin-top:14px;font-size:12px;max-width:760px}
.copy{margin-top:28px;font:400 12px/18px var(--font);color:var(--ink-62)}

/* 태블릿·작은 노트북 — 열은 유지하고 폭만 줄인다 */
@media (max-width:1060px){
  .c-r{grid-column:6/13}
  .row{grid-template-columns:180px minmax(0,1fr) 120px} .row .dt{display:none}
  .sgrid{grid-template-columns:repeat(4,minmax(0,1fr))}
  .plan+.plan{padding-left:24px} .plan:not(:last-child){padding-right:24px}
  .end>.h2,.end>.search,.end>.chips{grid-column:1/7} .end>.m-end{grid-column:8/13}
}
/* 한 열 — 스테이징과 같은 820px 에서 접는다 */
@media (max-width:820px){
  :root{--pad:24px}
  .links,.login{display:none} .menu{display:inline-flex}
  .nav,.nav.scrolled{background:var(--bg);-webkit-backdrop-filter:none;backdrop-filter:none}
  .mmenu.open{display:flex}
  .grid{display:block}
  .c-r{margin-top:40px}
  .demo{display:flex;flex-direction:column}
  .demo .c-l{display:contents}
  .demo .c-l>.sub{order:1} .demo .c-r{order:2;margin-top:32px} .demo .toc{order:3;margin-top:40px} .demo .c-l>.more{order:4;align-self:flex-start}
  .demo .c-r,.bgrid .c-r{max-width:640px}
  .row{grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"nm mc" "tt tt";gap:8px 12px}
  .row>div:first-child{grid-area:nm} .row .tt{grid-area:tt} .row .mc{grid-area:mc}
  .trust{grid-template-columns:1fr;border-top:0;margin-top:72px}
  .trust>div{padding:22px 0;border-top:1px solid var(--hair)} .trust>div:first-child{border-top-color:var(--line)}
  .m-brief{display:none}
  .sgrid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .stance p{margin-top:20px}
  .plans{grid-template-columns:1fr}
  .plan,.plan+.plan{border-left:0;padding-left:0;padding-right:0}
  .plan-sub{min-height:0}
  .end{display:block}
  .end>.m-end{display:none}
  .end .search{max-width:600px}
}
/* 휴대폰 */
@media (max-width:720px){
  :root{--pad:20px; --sec:112px; --sec-s:88px; --sec-l:136px}
  html{scroll-padding-top:72px}
  .hero{padding-top:40px}
  .hero h1 br.m{display:inline}
  .hero h1{font-size:min(40px,11vw);line-height:1.18;letter-spacing:-.035em}
  .hero .lede{margin-top:20px;font-size:17px}
  .hero .search{margin-top:30px}
  .search input{font-size:16px}
  .search .btn{height:44px;padding:0 16px}
  .hint-row{flex-direction:column;align-items:flex-start;gap:2px}
  .m-hero{margin-top:36px;aspect-ratio:1/1}
  .slot figcaption{font-size:12px}
  .h2{font-size:28px;line-height:1.3}
  .statement p{font-size:24px;line-height:1.46}
  .eyebrow{margin-bottom:14px}
  .sub{font-size:16px;margin-top:16px}
  .demo{margin-top:32px}
  .card{padding:22px 18px 20px}
  .card h3{font-size:21px}
  .cd-chart{padding:14px 12px 8px}
  .bb{grid-template-columns:1fr;gap:18px}
  .rows .row:nth-child(n+5){display:none}
  .band{padding:88px 0 96px}
  .bcard{padding:22px 18px 18px}
  .bcard h3{font-size:20px}
  .bstats{grid-template-columns:1fr 1fr;gap:14px 12px}
  .sgrid{grid-template-columns:1fr 1fr;column-gap:18px;margin-top:36px}
  .sgrid li:nth-child(n+11){display:none}
  .s-foot{flex-direction:column;align-items:flex-start;gap:4px}
  .s-all{margin-left:0}
  .stance .h2{font-size:34px}
  .qa summary{font-size:16px;padding:18px 0}
  .qa p{padding-right:0;font-size:15px}
  .chips a{height:44px}
  .fgrid{grid-template-columns:auto auto auto;justify-content:space-between;column-gap:16px}
  .fcol a{padding:12px 0}
  .foot{padding-top:44px}
}
"""

I = {
    "arrow": '<svg class="i" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "search": '<svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>',
    "video": '<svg viewBox="0 0 24 24"><path d="M8 6.5v11l9-5.5z"/></svg>',
    "image": '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 16l5-5 4 4 3-3 5 5"/></svg>',
    "moon": '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>',
    "ham": '<svg class="ham" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg>',
    "x": '<svg class="x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg>',
}
LINKS = [("홈", "#"), ("리포트", "#report"), ("업종 분석", "#sectors"), ("관심종목", "#"), ("멤버십", "#pricing"), ("모닝브리핑", "#brief")]


def dots(items):
    """가운뎃점 목록 — 항목은 한 덩어리(nowrap), 점은 CSS 가 앞 항목 끝에 그린다."""
    return '<span class="dl">' + "".join(f"<span>{x}</span>" for x in items if x) + "</span>"


def tail(html_text):
    """제목 끝 두 어절을 붙여 한두 음절짜리 외톨이 줄을 막는다 · '다음 주'도 한 덩어리."""
    t = html_text.replace("다음 주", "다음 주")
    i = t.rfind(" ")
    return t if i < 0 or len(t) - i > 8 else t[:i] + " " + t[i + 1:]


def slot(klass, kind, icon, ratio, title, note):
    return (f'<figure class="slot {klass}" aria-label="{esc(kind)} 자리 — {esc(title)}"><span class="st">{I[icon]}{esc(kind)}</span>'
            f'<span class="sr">{esc(ratio)}</span><figcaption><b>{esc(title)}</b>{esc(note)}</figcaption></figure>')


def arrow_pct(c, unit="%"):
    """스테이징과 같은 등락 표기 — ▲/▼ + 색"""
    if c is None:
        return '<span class="flat">—</span>'
    if round(c, 2) > 0:
        return f'<span class="up">▲ {abs(c):.2f}{unit}</span>'
    if round(c, 2) < 0:
        return f'<span class="down">▼ {abs(c):.2f}{unit}</span>'
    return f'<span class="flat">0.00{unit}</span>'


def ymd(s):
    s = s.replace("-", "")
    return f"{int(s[4:6])}월 {int(s[6:8])}일"


def op_chart(q, h=176, top=24, bottom=26):
    """분기 영업이익 막대 — 막대는 SVG(가로로만 늘어남), 라벨은 HTML(12px 고정). 적자는 0선 아래.
    스테이징 stock_page.bar_chart 와 같은 방식(9/26 에 SVG 속 라벨이 휴대폰에서 8.8px 로 줄던 것을 고친 방식)의 한 계열판."""
    vals = [x["op"] for x in q]
    mx, mn = max([0] + vals), min([0] + vals)
    extra = 20 if mn < 0 else 0
    H = h + extra
    plot_h = h - top - bottom
    rng = (mx - mn) or 1
    y0 = top + plot_h * mx / rng
    n = len(vals)
    gw = 100 / n
    bw = gw * 0.42
    svg = [f'<svg viewBox="0 0 100 {H}" preserveAspectRatio="none" aria-hidden="true">'
           f'<line x1="0" y1="{y0:.1f}" x2="100" y2="{y0:.1f}" class="ch-base" vector-effect="non-scaling-stroke"/>']
    labs = []
    for i, (x, v) in enumerate(zip(q, vals)):
        cx = gw * i + gw / 2
        last = i == n - 1
        bh = max(1.5, plot_h * abs(v) / rng) if v else 0
        y = y0 - bh if v > 0 else y0
        if v:
            svg.append(f'<rect class="{"ch-last" if last else "ch-op"}" x="{cx - bw / 2:.2f}" y="{y:.1f}" width="{bw:.2f}" height="{bh:.1f}"/>')
        up = v >= 0
        ly = (y0 - bh - 6) if up else (y0 + bh + 6)
        labs.append(f'<span class="ch-val{"" if up else " dn"}{" last" if last else ""}" style="left:{cx:.2f}%;top:{ly:.1f}px">{fwon(v)}</span>')
        labs.append(f'<span class="ch-lab" style="left:{cx:.2f}%;top:{H - 18}px">{x["q"][2:4]}Q{x["q"][-1]}</span>')
    svg.append("</svg>")
    return f'<div class="ch" role="img" aria-label="분기 영업이익 막대그래프" style="height:{H}px">' + "".join(svg) + "".join(labs) + "</div>"


def nav():
    lk = "".join(f'<a href="{h}">{t}</a>' for t, h in LINKS)
    return ('<div id="kosEdgeTop" aria-hidden="true"></div><div id="kosEdgeBot" aria-hidden="true"></div>'
            f'<nav class="nav" id="nav"><div class="nav-in"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a><div class="links">{lk}</div>'
            f'<div class="right"><a class="login" href="#">로그인</a><button class="ib" id="themeBtn" aria-label="테마 전환"><svg viewBox="0 0 24 24" id="themeIcon">{I["moon"]}</svg></button>'
            f'<button class="ib menu" id="menuBtn" aria-label="메뉴" aria-expanded="false" aria-controls="mmenu">{I["ham"]}{I["x"]}</button></div></div></nav>'
            f'<div class="mmenu" id="mmenu"><div class="mm-links">{lk}</div><div class="sep"></div><div class="mm-auth"><a href="#">로그인</a><a href="#">회원가입</a></div>'
            '<div class="mm-foot"><a href="#">회사 소개</a><a href="#">문의하기</a><a href="#">피드백</a><a href="#">이용약관</a><a href="#">개인정보 처리방침</a></div></div>')


def foot():
    return (f'<footer class="foot"><div class="w"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a>'
            '<p class="ftag">국내 상장사 리포트, 업종 분석, 모닝브리핑</p>'
            '<div class="fgrid"><div class="fcol"><h4>서비스</h4><a href="#">홈</a><a href="#">리포트</a><a href="#">업종 분석</a><a href="#">관심종목</a><a href="#">멤버십</a><a href="#">모닝브리핑</a></div>'
            '<div class="fcol"><h4>회사</h4><a href="#">회사 소개</a><a href="#">문의하기</a><a href="#">피드백</a></div>'
            '<div class="fcol"><h4>정책</h4><a href="#">이용약관</a><a class="pp" href="#">개인정보 처리방침</a></div></div>'
            '<div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>'
            '<p class="note-slot"><b>유료 개시 전에 더할 줄</b>통신판매업 신고번호 · 대표전화 · 호스팅서비스 제공자 · 공정거래위원회 사업자정보확인 링크 '
            '(전자상거래법 제10조·제13조, 시행령 제11조의4 — scripts/patch_biz_footer.py 의 BIZ 한 곳)</p>'
            '<div class="copy">© 2026 KOSAI</div></div></footer>')


def search_box(ph="종목명 또는 종목코드(예: 삼성전자, 005930)", ph_m="종목명 또는 종목코드"):
    """휴대폰(과 좁은 칸)은 예시가 잘리므로 짧은 안내(data-m)로 바꾼다."""
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

    # ── 첫 화면 — 제목(차별 하나) · 서브(범위 · 방법) · 검색 · 걱정 하나와 태도 · 제품이 보이는 장면 ──
    hero = ('<header class="hero w"><h1>증권사가<br class="m"> 다루지 않는 종목도<br>리포트가 있습니다</h1>'
            f'<p class="lede"><span class="nw">{MARKETS}</span> {n_rep:,}개 종목을 <span class="nw">다룹니다({asof}).</span> '
            '<span class="nw">실적 표는</span> 공시에서 그대로 가져오고, 해석은 AI가 씁니다.</p>'
            + search_box()
            + f'<div class="hint-row"><p class="hint">{dots(["요약과 실적은 가입 없이 무료", "매수·매도 의견과 목표주가는 없습니다"])}</p>'
            + f'<a class="more" href="#">{esc(BY[HERO_REPORT]["name"])} 리포트 보기 {I["arrow"]}</a></div>'
            + slot("m-hero", "영상 · 사진", "video", "21:9 · 휴대폰 1:1", "첫 화면의 얼굴",
                   "권장: 실제 리포트가 읽히는 크기로 보이는 장면 — 자연광 아래 손에 든 휴대폰으로 리포트를 넘기는 모습(촬영, 또는 같은 장면의 3D 렌더). "
                   "유리 구·프리즘 같은 추상 오브젝트는 쓰지 않습니다. 영상이면 6~8초·소리 없음·멈춤 단추. "
                   "종목이 보이면 캡션 '화면 속 종목은 예시이며 투자 권유가 아닙니다'.")
            + '</header>')

    # ── 한 문단 선언 — 대안이 주는 것 · KOSAI 가 쓰는 것 ──
    stmt = ('<section class="statement w"><p><span>시세 앱과 뉴스는 오늘 무슨 일이 있었는지 알려 줍니다.</span> '
            'KOSAI 리포트는 회사가 무엇으로 돈을 벌고, 무엇을 조심해야 하는지 씁니다.</p></section>')

    # ── 리포트 한 편(플리토) — 글과 숫자를 고치지 않고 옮긴다 ──
    q = r["quant"]["quarterly"]
    rd = r["reportDate"]
    bull = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bull"])
    bear = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bear"])
    q0, q1 = q[0]["q"], q[-1]["q"]
    card = (f'<article class="card" aria-label="{esc(s["name"])} 리포트에서 옮긴 부분"><div class="cd-top"><div><b>{esc(s["name"])}</b>'
            f'{dots([esc(s["market"]), esc(s["sector"]), SAMPLE])}</div>'
            f'<div class="cd-px"><b>{grp(s["price"])}원</b>{arrow_pct(s["change"])}</div></div>'
            f'<p class="cd-meta">{dots(["시가총액 " + jo(s["mcap"]), ymd(rd) + " 발행", "재무 " + ymd(r["quant"]["asOf"]) + " 기준", "주가 " + ymd(PRICE_DATE) + " 종가"])}</p>'
            f'<h3>{g(r["title"]["ko"])}</h3><p class="cd-lede">{g(r["lead"]["ko"])}</p>'
            f'<div class="cd-chart"><p>분기 영업이익<span>연결 · DART 공시 · {q0[2:4]}년 {q0[-1]}분기~{q1[2:4]}년 {q1[-1]}분기</span></p>{op_chart(q)}</div>'
            f'<div class="bb"><div><h4>강세 요인<span>{len(r["bull"])}</span></h4><ul>{bull}</ul></div>'
            f'<div><h4>약세 요인<span>{len(r["bear"])}</span></h4><ul>{bear}</ul></div></div>'
            f'<p class="cd-foot"><span>참고 출처 {len(r.get("sources") or [])}개</span><span>리포트 13개 절 가운데 일부</span></p></article>')
    toc = "".join(f'<li><p class="tg">{t}{"<span>무료</span>" if free else ""}</p><p class="tn">{dots(ns)}</p></li>' for t, ns, free in TOC)
    sec_report = ('<section class="sec w" id="report"><p class="eyebrow">리포트</p><h2 class="h2">좋은 이야기만 쓰지 않습니다</h2>'
                  '<div class="grid demo"><div class="c-l"><p class="sub">리포트마다 강세 요인 셋과 약세 요인 셋을 같은 무게로 담습니다. '
                  '사업 구조부터 종합 의견까지 순서가 같아서, 처음 보는 회사의 리포트도 낯설지 않습니다.</p>'
                  f'<ul class="toc" aria-label="리포트 목차">{toc}</ul>'
                  f'<a class="more" href="#">{esc(s["name"])} 리포트 보기 {I["arrow"]}</a></div>'
                  f'<div class="c-r">{card}<p class="fine card-note">{esc(s["name"])} 리포트에서 옮긴 부분입니다. 문장과 숫자는 고치지 않았습니다. '
                  '예시로 고른 종목이며, 투자 권유가 아닙니다.</p></div></div></section>')

    # ── 다시 쓰는 리포트 + 숫자 · 출처 · 한계 ──────────────
    recent = sorted(((rr.get("reportTs") or rr.get("reportDate") or "", tk, rr) for tk, rr in INDEX.items() if tk in BY), reverse=True)[:6]
    n7 = sum(1 for rr in INDEX.values() if rr.get("reportDate") and 0 <= (BASE - datetime.date.fromisoformat(rr["reportDate"])).days < 7)
    rows = "".join(f'<a class="row" href="#"><div><span class="nm">{esc(BY[tk]["name"])}</span><span class="cd">{esc(BY[tk]["market"])} · {esc(BY[tk]["sector"])}</span></div>'
                   f'<span class="tt">{g(rr["title"]["ko"])}</span><span class="mc">시가총액 {jo(BY[tk]["mcap"])}</span><span class="dt">{ymd(rr["reportDate"])}</span></a>'
                   for _, tk, rr in recent)
    sec_fresh = ('<section class="sec s w" id="fresh"><p class="eyebrow">갱신</p><h2 class="h2">공시가 나오면 리포트도 바뀝니다</h2>'
                 '<p class="sub">회사가 분기·반기·사업보고서를 DART에 공시하면 <span class="nw">최신 실적으로</span> 다시 씁니다. 주가·시가총액·PER은 거래일마다 저녁에 갱신합니다.</p>'
                 f'<div class="fresh"><p class="rows-cap">최근에 쓴 리포트{dots(["지난 7일 " + str(n7) + "편", asof])}</p><div class="rows">{rows}</div>'
                 f'<a class="more" href="#">최근에 쓴 리포트 모두 보기 {I["arrow"]}</a></div>'
                 '<div class="trust"><div><h3>실적 표와 차트는 AI가 쓰지 않습니다</h3>'
                 '<p>최근 4년·5분기 실적 표와 차트는 금융감독원 <span class="nw">전자공시시스템(DART)에서</span>, 주가는 한국거래소 종가 자료에서 가져옵니다. '
                 'AI는 그 숫자를 근거로 해석을 씁니다.</p></div>'
                 '<div><h3>참고한 자료는 링크로 남깁니다</h3>'
                 f'<p>사업 현황과 업황을 알아보며 읽은 뉴스와 자료를 리포트 끝에 모아 둡니다. 한 편에 보통 {n_src}개입니다.</p></div>'
                 '<div><h3>해석은 AI가 씁니다. 그래서 틀릴 수 있습니다.</h3><p>틀린 곳을 알려 주시면 확인해서 고칩니다.</p>'
                 f'<a class="more" href="#">틀린 곳 알리기 {I["arrow"]}</a></div></div></section>')

    # ── 모닝브리핑 — 어두운 띠 ─────────────────────────
    secs = "".join(f"<li><span>{tail(g(x['heading']['ko']))}</span></li>" for x in b["sections"])
    stats = ""
    for k in ["코스피", "나스닥", "WTI", "미 10년물"]:
        v, c = f[k]
        stats += f"<div><dt>{k}</dt><dd>{v}<small>{arrow_pct(c, '%p' if k.endswith('10년물') else '%')}</small></dd></div>"
    first = briefs()[0][:10]
    sec_brief = ('<section class="band" id="brief"><div class="w"><p class="eyebrow">모닝브리핑</p><h2 class="h2">장이 열리기 전에 읽는 한 편</h2><div class="grid bgrid"><div class="c-l">'
                 f'<p class="sub">{g("전날 국내 시장과 밤사이 해외 시장, 다가올 일정 가운데 오늘 장에 필요한 것만 골라 정리합니다. 숫자가 움직인 이유가 분명하면 한 구절로 덧붙입니다.")}</p>'
                 f'<a class="more" href="#">제{b["_no"]}호 읽기 {I["arrow"]}</a>'
                 f'<p class="fine">{dots(["거래일 아침 7시 30분 무렵 발행", ymd(first) + " 창간"])}</p>'
                 + slot("m-brief", "사진", "image", "3:2 · 휴대폰에서는 숨김", "개장 전 아침",
                        "자연광이 드는 이른 아침의 책상, 사람 얼굴 없이. 브리핑이 열린 휴대폰이 보여도 좋습니다. 이 페이지에서 분위기만으로 뜻이 더해지는 유일한 자리입니다.")
                 + f'</div><div class="c-r"><article class="bcard" aria-label="모닝브리핑 제{b["_no"]}호"><p class="bm">제{b["_no"]}호 · {kdate(b["date"])} {publish_time(b)} 발행</p>'
                 f'<h3>{g(b["title"]["ko"])}</h3><ol class="bsec">{secs}</ol><dl class="bstats">{stats}</dl></article></div></div></div></section>')

    # ── 업종 ─────────────────────────────────────────
    cnt = Counter(c for x in STOCKS["stocks"] for c in (x.get("categories") or []) if c != "기타")
    top = cnt.most_common()
    mx = top[0][1]
    grid = "".join(f'<li><a href="#"><span class="sn">{esc(k)}<b>{v:,}</b></span><span class="bar"><i style="width:{v / mx * 100:.1f}%"></i></span></a></li>' for k, v in top)
    sub_sec = f"{len(top)}개 업종마다 업황과 주요 종목을 따로 정리합니다. 한 회사를 읽을\u00a0때 그 업종의 흐름도 함께 볼 수 있습니다."
    sec_sectors = ('<section class="sec w" id="sectors"><p class="eyebrow">업종 분석</p><h2 class="h2">업종 안에서 회사를 봅니다</h2>'
                   f'<p class="sub">{g(sub_sec)}</p>'
                   f'<ul class="sgrid">{grid}</ul><div class="s-foot"><p class="fine">숫자는 업종에 속한 종목 수입니다. 한 종목이 여러 업종에 들기도 합니다.</p>'
                   f'<a class="more s-all" href="#">{len(top)}개 업종 분석 보기 {I["arrow"]}</a></div></section>')

    # ── 하지 않는 것 — 그리고 누구를 위해 쓰는가 ─────────────
    sec_stance = ('<section class="sec l w"><div class="grid stance"><h2 class="h2 c-l">사라고도 팔라고도<br>하지 않습니다</h2>'
                  '<div class="c-r"><p>매수·매도 의견도, 목표주가도 내지 않습니다. 사실과 근거를 모으고, 판단은 읽는 분께 맡깁니다.</p>'
                  '<p>직접 종목을 고르는 분을 위한 리포트입니다.</p></div></div></section>')

    # ── 멤버십 — 경계를 한 줄로 · 같은 내용 먼저 · 법정 문구 자리 ─────
    plans = [
        ("무료", True, "0원", "", "종목을 처음 살필 때", ["핵심 지표 — 주가·시가총액·PER", "리포트 개요와 요약", "사업 구조", "최근 4년·5분기 실적", "참고 출처"],
         '<a class="btn btn-soft" href="#">리포트 찾기</a>', ["가입 없이"]),
        ("BASIC", False, "9,900원", "월", "보유 종목을 꾸준히 챙길 때", ["무료로 보는 것 모두", "리포트 전체 — 실적 분석부터 종합 의견까지", "하루 5개 종목"],
         '<a class="btn btn-ink" href="#">BASIC 시작하기</a>', ["부가세 포함", "매달 자동 결제", "언제든 해지"]),
        ("PRO", False, "14,900원", "월", "여러 종목을 견줘 볼 때", ["무료로 보는 것 모두", "리포트 전체 — 실적 분석부터 종합 의견까지", "하루 15개 종목"],
         '<a class="btn btn-ink" href="#">PRO 시작하기</a>', ["부가세 포함", "매달 자동 결제", "언제든 해지"]),
    ]
    ph = "".join(f'<div class="plan"><p class="plan-name{" ko" if ko else ""}">{nm}</p><p class="plan-price">{f"<small>{unit}</small>" if unit else ""}{pr}</p>'
                 f'<p class="plan-sub">{sub}</p><ul>' + "".join(f"<li>{esc(x)}</li>" for x in fs) + f'</ul>{cta}<p class="under dl">'
                 + "".join(f"<span>{u}</span>" for u in under) + '</p></div>'
                 for nm, ko, pr, unit, sub, fs, cta, under in plans)
    sec_price = ('<section class="sec w" id="pricing"><p class="eyebrow">멤버십</p><h2 class="h2">요약과 실적은 무료입니다</h2>'
                 '<p class="sub">요약과 사업 구조, 최근 실적은 가입 없이 읽을 수 있습니다. 실적 분석부터 종합 의견까지, 리포트 전체는 구독하면 열립니다.</p>'
                 '<p class="fine same">BASIC과 PRO는 리포트 내용이 같고, 하루에 볼 수 있는 <span class="nw">종목 수만</span> 다릅니다.</p>'
                 f'<div class="plans">{ph}</div>'
                 '<p class="fine price-fine">재무 공시가 없어 실적 표가 없는 종목은 리포트 전체를 무료로 공개합니다.</p>'
                 '<p class="note-slot price-note"><b>유료 개시 뒤 이 자리에 들어갈 문구</b>유사투자자문업 신고번호 · 개별 투자 상담과 자금 운용을 하지 않는다는 안내 · '
                 '원금 손실이 생길 수 있다는 안내(자본시장법 제101조의3). 요금 절은 유료화 법정 절차가 끝난 뒤에만 실사이트에 올립니다. 문구는 변호사 확인 뒤 확정합니다.</p></section>')

    # ── 자주 묻는 질문 — 믿어도 되나 · 추천인가 · 무엇이 다른가 · 누가 · 해지 ──
    qa = [
        ("AI가 쓴 리포트, 믿어도 되나요?", "리포트는 AI가 쓰기 때문에 틀릴 수 있습니다. 다만 실적 표와 차트의 숫자는 AI가 쓰지 않고 DART 공시에서 그대로 가져옵니다. "
         "글을 쓰며 참고한 자료는 리포트 끝에 링크로 남기니, 중요한 내용은 원문에서 한 번 더 확인하세요. 틀린 곳을 알려 주시면 확인해서 고칩니다."),
        ("종목을 추천해 주나요?", "아닙니다. 매매 신호나 목표주가를 찾으신다면 KOSAI는 맞지 않습니다. 리포트는 참고 자료이고, 판단과 그 결과는 읽는 분의 몫입니다."),
        ("증권사 리포트와 무엇이 다른가요?", "증권사 리포트는 애널리스트가 회사를 취재해 쓰고, 주로 규모가 큰 회사를 다룹니다. "
         f"KOSAI 리포트는 공개된 자료로 AI가 쓰고, {MARKETS} {n_listed:,}개 종목 가운데 {n_rep:,}개를 다룹니다. "
         f"나머지 {n_listed - n_rep}개는 새로 상장한 종목이라 리포트를 준비하고 있습니다. 증권사 리포트가 있는 종목이라면 함께 읽고, 없는 종목은 여기서 먼저 읽어 보세요."),
        ("누가 만드나요?", "코사이(대표 임범준)가 만듭니다. 리포트는 AI가 씁니다. 사람은 AI가 따를 작성 규칙을 정하고, "
         "깨진 글자·태그·금지 표현이 있는 글을 저장하기 전에 걸러 내는 검사를 만듭니다. 사업자 정보는 이 페이지 맨 아래에 있습니다."),
        ("구독은 언제든 해지할 수 있나요?", "설정의 구독 항목에서 바로 해지할 수 있습니다. 해지한 뒤에도 이미 결제한 기간이 끝날 때까지 그대로 볼 수 있습니다."),
    ]
    qh = "".join(f'<details class="qa"{" open" if i == 0 else ""}><summary>{esc(qq)}</summary><p>{g(aa)}</p></details>' for i, (qq, aa) in enumerate(qa))
    sec_faq = f'<section class="sec s w"><div class="grid faq"><h2 class="h2 c-l">자주 묻는 질문</h2><div class="c-r">{qh}</div></div></section>'

    # ── 마무리 — 첫 약속을 짧게 한 번 더, 같은 검색창, 옆에 그림 한 장 ──────
    chips = "".join(f'<a href="#">{esc(BY[t]["name"])}<span>{jo(BY[t]["mcap"])}</span></a>' for t in CHIPS if t in BY)
    sec_end = ('<section class="sec s w end">'
               f'<h2 class="h2">{n_rep:,}개 종목의<br>리포트가 이미 있습니다</h2>{search_box(ph="종목명 또는 종목코드")}<div class="chips">{chips}</div>'
               + slot("m-end", "이미지", "image", "1:1 · 휴대폰에서는 숨김", "마무리 장면",
                      "첫 화면과 같은 빛과 재질의 정지 그림 한 장. 첫 화면 영상의 마지막 장면을 써도 됩니다.")
               + '</section>')

    js = ("<script>(function(){"
          "var nav=document.getElementById('nav'),tick=false;function upd(){tick=false;nav.classList.toggle('scrolled',scrollY>32)}"
          "addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(upd)}},{passive:true});upd();"
          "var sun='<path d=\"M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4\"/><circle cx=\"12\" cy=\"12\" r=\"4\"/>',"
          "moon='" + I["moon"] + "';"
          "var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();"
          "document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);"
          "try{localStorage.setItem('kos-theme',t)}catch(e){}paint()});"
          "var mb=document.getElementById('menuBtn'),mm=document.getElementById('mmenu');"
          "function setMenu(on){nav.classList.toggle('menu-open',on);mm.classList.toggle('open',on);mb.setAttribute('aria-expanded',on?'true':'false');root.style.overflow=on?'hidden':''}"
          "mb.addEventListener('click',function(){setMenu(!nav.classList.contains('menu-open'))});"
          "mm.addEventListener('click',function(e){if(e.target.closest('a'))setMenu(false)});"
          "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&nav.classList.contains('menu-open'))setMenu(false)});"
          "matchMedia('(min-width:821px)').addEventListener('change',function(e){if(e.matches)setMenu(false)});"
          "if(matchMedia('(max-width:720px)').matches)document.querySelectorAll('input[data-m]').forEach(function(i){i.placeholder=i.getAttribute('data-m')})"
          "})();</script>")
    h1 = "증권사가 다루지 않는 종목도 리포트가 있습니다"
    desc = f"{MARKETS} {n_rep:,}개 종목의 리포트. 실적 표는 공시에서 그대로 가져오고, 해석은 AI가 씁니다."
    theme = ("<script>(function(){var t='light';try{t=localStorage.getItem('kos-theme')||'light'}catch(e){}document.documentElement.setAttribute('data-theme',t)})();</script>"
             "<script>(function(){var m=document.querySelector('meta[name=\"theme-color\"]'),r=document.documentElement;"
             "function tc(){m.setAttribute('content',r.getAttribute('data-theme')==='dark'?'#0d0d0e':'#f9f8f6')}"
             "tc();new MutationObserver(tc).observe(r,{attributes:true,attributeFilter:['data-theme']})})();</script>")
    head = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#f9f8f6"><title>KOSAI — {h1}</title>'
            f'<meta name="description" content="{desc}"><meta property="og:title" content="{h1}">'
            f'<meta property="og:description" content="{MARKETS} {n_rep:,}개 종목의 리포트 · 요약과 실적은 무료">'
            f'<link rel="stylesheet" href="{FONTS}/pretendard-subset.css"><link rel="stylesheet" href="landing.css">{theme}</head><body>')
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
