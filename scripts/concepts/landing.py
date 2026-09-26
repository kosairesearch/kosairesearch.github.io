"""랜딩 시안 — 스테이징 디자인(Pretendard · #f9f8f6 · #141414 · 알약 단추 · 가는 선) 위에 해외 제품 사이트의 '느낌'.

    python3 scripts/concepts/landing.py      # → preview/concepts/landing/index.html · landing.css

  · 그림·영상·3D 는 만들지 않는다. 들어갈 자리만 표시한다(종류 · 비율 · 들어갈 내용).
  · 숫자와 글은 실제 데이터와 스테이징에 이미 있는 문장에서 가져온다.
  · 스테이징·실사이트 파일은 건드리지 않는다.
"""
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from data import (ROOT, BY, STOCKS, INDEX, SECTORS_AI, esc, sign, cls, won, jo, grp, kdate, report, brief,  # noqa: E402
                  publish_time)
from common import g, chunk, chart_bars, q_label, sources_grouped, read_minutes  # noqa: E402

OUT = os.path.join(ROOT, "preview", "concepts", "landing")
ASSETS = "../../../assets"
FONT = '<link href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">'
SAMPLE = "298000"      # 효성화학 — 소형주 리포트 견본

CSS = r"""
:root{
  --bg:#f9f8f6; --surface:#fff; --surface-2:#f1efeb; --slot:#e9e7e2;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-62:rgba(20,20,20,.62); --ink-30:rgba(20,20,20,.3);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --up:#c8102e; --down:#1e5fbf;
  --font:'Pretendard Variable',Pretendard,-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo',sans-serif;
  --max:1280px; --pad:40px; --ease:cubic-bezier(.2,.7,.2,1);
  color-scheme:light;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;
  word-break:keep-all;overflow-wrap:break-word;letter-spacing:-.01em}
a{color:inherit;text-decoration:none}
h1,h2,h3,p,ul,ol,figure{margin:0}
ul,ol{padding:0;list-style:none}
button,input{font:inherit;color:inherit}
.w{max-width:var(--max);margin:0 auto;padding:0 var(--pad)}
.nw{white-space:nowrap}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--ink-62)}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
svg.i{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* 머리 */
.nav{position:sticky;top:0;z-index:50;transition:background-color .3s,box-shadow .3s}
.nav.on{background:rgba(249,248,246,.86);-webkit-backdrop-filter:saturate(1.6) blur(16px);backdrop-filter:saturate(1.6) blur(16px);box-shadow:0 1px 0 var(--hair)}
.nav-in{height:68px;display:flex;align-items:center;justify-content:space-between;position:relative}
.brand img{height:14px;display:block}
.links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:32px}
.links a{font:500 14.5px/1 var(--font);color:var(--ink-72);transition:color .15s} .links a:hover{color:var(--ink)}
.right{display:flex;align-items:center;gap:8px}
.login{font:500 14.5px/1 var(--font);color:var(--ink-72);padding:14px 10px} .login:hover{color:var(--ink)}
.menu{display:none;width:44px;height:44px;border:0;background:none;align-items:center;justify-content:center;margin-right:-10px;cursor:pointer}
.menu svg{width:22px;height:22px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round}

/* 단추 */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:999px;background:var(--ink);color:#f9f8f6;
  font:650 14.5px/1 var(--font);letter-spacing:-.01em;white-space:nowrap;transition:opacity .2s,background-color .2s}
.btn:hover{opacity:.86}
.btn.sm{height:38px;padding:0 16px;font-size:14px}
.btn.lg{height:52px;padding:0 26px;font-size:15.5px}
.btn.ghost{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)}
.btn.ghost:hover{opacity:1;background:rgba(20,20,20,.04)}
.btn svg.i{transition:transform .25s var(--ease)} .btn:hover svg.i{transform:translateX(3px)}
.link{display:inline-flex;align-items:center;gap:6px;font:650 15px/1 var(--font);padding:10px 0;border-bottom:1px solid var(--ink)}
.link svg.i{transition:transform .25s var(--ease)} .link:hover svg.i{transform:translateX(3px)}

/* 첫 화면 */
.hero{padding-top:84px}
.news{display:inline-flex;align-items:center;gap:12px;max-width:100%;height:38px;padding:0 14px 0 16px;border-radius:999px;background:var(--surface);
  box-shadow:0 0 0 1px var(--hair);font:500 13.5px/1 var(--font);color:var(--ink-72);transition:box-shadow .2s}
.news:hover{box-shadow:0 0 0 1px var(--line)}
.news b{font-weight:650;color:var(--ink);white-space:nowrap}
.news .sep{width:1px;height:14px;background:var(--line);flex:none}
.news .nt{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hero h1{margin-top:30px;font:700 clamp(44px,7.3vw,106px)/1.02 var(--font);letter-spacing:-.056em}
.hrow{display:flex;justify-content:space-between;align-items:flex-end;gap:48px;margin-top:44px}
.lead{max-width:470px;font:400 17px/1.7 var(--font);color:var(--ink-62);letter-spacing:-.012em;text-wrap:pretty}
.ctas{display:flex;gap:10px;flex:none}

/* 그림 자리 — 만들지 않고 표시만 */
.slot{position:relative;border-radius:28px;overflow:hidden;background-color:var(--slot);
  background-image:repeating-linear-gradient(-45deg,rgba(20,20,20,.045) 0 1px,transparent 1px 13px);box-shadow:inset 0 0 0 1px rgba(20,20,20,.06)}
.slot .st{position:absolute;top:20px;left:20px;display:inline-flex;align-items:center;gap:7px;height:30px;padding:0 13px 0 11px;border-radius:999px;background:var(--surface);
  font:650 12.5px/1 var(--font);color:var(--ink);box-shadow:0 1px 2px rgba(20,20,20,.06)}
.slot .st svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.slot .sr{position:absolute;top:28px;right:24px;font:500 12.5px/1 var(--font);color:var(--ink-62);letter-spacing:.02em}
.slot figcaption{position:absolute;left:24px;right:24px;bottom:22px;max-width:460px;font:400 13.5px/1.6 var(--font);color:var(--ink-62);text-wrap:pretty}
.slot figcaption b{display:block;margin-bottom:4px;font:650 14.5px/1.4 var(--font);color:var(--ink)}
.s-hero{margin-top:76px;aspect-ratio:21/9}

/* 숫자 */
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-top:96px;border-top:1px solid var(--line)}
.stats>div{padding:28px 24px 4px 0}
.stats>div+div{padding-left:28px;border-left:1px solid var(--hair)}
.stats b{display:block;font:700 58px/1 var(--font);letter-spacing:-.05em}
.stats span{display:block;margin-top:16px;font:650 15px/1.35 var(--font)}
.stats small{display:block;margin-top:6px;font:400 13px/1.55 var(--font);color:var(--ink-62)}

/* 절 머리 */
.sec{padding-top:184px}
.sh{display:flex;align-items:baseline;gap:14px;padding-top:16px;border-top:1px solid var(--ink);font:650 13.5px/1 var(--font)}
.sh .no{font-weight:500;color:var(--ink-62)}
.sh .mt{margin-left:auto;font-weight:500;color:var(--ink-62)}
.h2{margin-top:60px;max-width:900px;font:700 clamp(36px,5.2vw,72px)/1.06 var(--font);letter-spacing:-.052em}
.sub{margin-top:26px;max-width:470px;font:400 16.5px/1.72 var(--font);color:var(--ink-62);text-wrap:pretty}

/* 01 리포트 */
.split{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:72px;align-items:start;margin-top:60px}
.split .sub{margin-top:0}
.idx{margin-top:40px;display:grid;grid-template-columns:1fr 1fr;column-gap:28px;border-top:1px solid var(--hair);counter-reset:i}
.idx li{counter-increment:i;display:flex;gap:12px;padding:13px 0;border-bottom:1px solid var(--hair);font:500 15px/1.3 var(--font)}
.idx li::before{content:counter(i,decimal-leading-zero);font-weight:500;color:var(--ink-62);min-width:22px}
.split .link{margin-top:36px}
.spec{background:var(--surface);border-radius:24px;box-shadow:0 0 0 1px var(--hair),0 24px 48px -32px rgba(20,20,20,.22);padding:34px 36px 30px}
.sp-top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
.sp-top b{display:block;font:700 18px/1.2 var(--font)}
.sp-top span{display:block;margin-top:6px;font:500 13px/1 var(--font);color:var(--ink-62)}
.sp-px{text-align:right} .sp-px b{font-size:17px} .sp-px span{font-weight:650}
.sp-meta{margin-top:18px;padding-bottom:18px;border-bottom:1px solid var(--hair);font:400 12.5px/1.5 var(--font);color:var(--ink-62)}
.spec h3{margin-top:24px;font:700 30px/1.22 var(--font);letter-spacing:-.045em;text-wrap:balance}
.sp-lede{margin-top:14px;font:400 15px/1.72 var(--font);color:var(--ink-72);text-wrap:pretty}
.sp-chart{margin-top:26px;padding:20px 20px 10px;border-radius:16px;background:var(--bg)}
.sp-chart p{display:flex;justify-content:space-between;font:650 13.5px/1 var(--font)} .sp-chart p span{font-weight:500;color:var(--ink-62)}
.sp-chart svg{margin-top:10px}
.sp-chart .cm{display:none}
.sp-bb{margin-top:22px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.sp-bb h4{margin:0 0 10px;display:flex;align-items:center;gap:8px;font:650 13.5px/1 var(--font)}
.sp-bb h4 i{width:7px;height:7px;border-radius:50%}
.sp-bb li{padding:8px 0;border-top:1px solid var(--hair);font:500 14px/1.4 var(--font);color:var(--ink-72)}
.sp-foot{margin-top:22px;font:400 12.5px/1 var(--font);color:var(--ink-62)}
.spec-cap{margin:16px 4px 0;font:400 13px/1.6 var(--font);color:var(--ink-62)}

/* 02 업종 */
.sgrid{margin-top:64px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));column-gap:28px;border-top:1px solid var(--line)}
.sgrid li{padding:18px 0 16px;border-bottom:1px solid var(--hair)}
.sgrid .sn{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font:650 15.5px/1.3 var(--font)}
.sgrid .sn b{font:500 14px/1 var(--font);color:var(--ink-62)}
.sgrid .bar{display:block;height:2px;margin-top:12px;background:var(--hair)}
.sgrid .bar i{display:block;height:100%;background:var(--ink)}
.fine{margin-top:18px;font:400 13px/1.6 var(--font);color:var(--ink-62)}

/* 03 모닝브리핑 — 어두운 띠 */
.dark{margin-top:184px;padding:120px 0 128px;background:#141414;color:#f4f4f2}
.dark .sh{border-top-color:#f4f4f2}
.dark .sh .no,.dark .sh .mt{color:rgba(244,244,242,.6)}
.dark .sub{color:rgba(244,244,242,.62)}
.split.b{grid-template-columns:minmax(0,7fr) minmax(0,5fr);align-items:end}
.dark .spec{background:rgba(255,255,255,.04);box-shadow:0 0 0 1px rgba(255,255,255,.1);margin-top:40px}
.brf .bm{font:500 13px/1.4 var(--font);color:rgba(244,244,242,.6)}
.brf h3{margin-top:16px;font:700 28px/1.3 var(--font);letter-spacing:-.04em;text-wrap:balance}
.bsec{margin-top:24px;border-top:1px solid rgba(255,255,255,.1);counter-reset:b}
.bsec li{counter-increment:b;display:flex;gap:14px;padding:12px 0;border-bottom:1px solid rgba(255,255,255,.08);font:500 15px/1.45 var(--font);color:rgba(244,244,242,.86)}
.bsec li::before{content:counter(b);min-width:14px;color:rgba(244,244,242,.5)}
.bnums{margin-top:24px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.bnums div{padding:14px 14px 13px;border-radius:14px;background:rgba(255,255,255,.05)}
.bnums span{display:block;font:500 12.5px/1 var(--font);color:rgba(244,244,242,.6)}
.bnums b{display:block;margin-top:10px;font:650 18px/1 var(--font);letter-spacing:-.02em}
.bnums i{display:block;margin-top:7px;font:600 12.5px/1 var(--font);font-style:normal}
.dark .up{color:#ff7a7a} .dark .down{color:#8ab4ff} .dark .flat{color:rgba(244,244,242,.6)}
.dark .slot{background-color:#1f1f1f;background-image:repeating-linear-gradient(-45deg,rgba(255,255,255,.05) 0 1px,transparent 1px 13px);box-shadow:inset 0 0 0 1px rgba(255,255,255,.08)}
.dark .slot .st{background:#f4f4f2;color:#141414}
.dark .slot .sr,.dark .slot figcaption{color:rgba(244,244,242,.6)}
.dark .slot figcaption b{color:#f4f4f2}
.phone{width:100%;max-width:360px;aspect-ratio:9/19;border-radius:48px;justify-self:end}
.dark .btn{background:#f4f4f2;color:#141414}

/* 04 만드는 방법 */
.steps{margin-top:64px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:40px}
.steps>div{border-top:1px solid var(--line);padding-top:22px}
.steps .k{font:500 13.5px/1 var(--font);color:var(--ink-62)}
.steps h3{margin-top:28px;font:700 26px/1.2 var(--font);letter-spacing:-.04em}
.steps p{margin-top:14px;font:400 15.5px/1.72 var(--font);color:var(--ink-62);text-wrap:pretty}
.stance{margin-top:64px;display:flex;gap:18px;align-items:baseline;padding:26px 30px;border-radius:20px;background:var(--surface-2)}
.stance b{flex:none;font:650 14.5px/1.5 var(--font)}
.stance p{font:400 15px/1.7 var(--font);color:var(--ink-72)}

/* 05 멤버십 */
.plans{margin-top:64px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--surface);border-radius:28px;box-shadow:0 0 0 1px var(--hair)}
.plan{padding:36px 36px 34px;display:flex;flex-direction:column}
.plan+.plan{border-left:1px solid var(--hair)}
.plan h3{font:650 15px/1 var(--font)}
.plan .pp{margin-top:26px;font:500 15px/1 var(--font);color:var(--ink-62)}
.plan .pp b{font:700 50px/1 var(--font);letter-spacing:-.045em;color:var(--ink);margin-right:4px}
.plan .pd{margin-top:12px;font:400 13.5px/1.5 var(--font);color:var(--ink-62)}
.plan ul{margin:28px 0 32px;border-top:1px solid var(--hair);flex:1}
.plan li{display:flex;gap:10px;padding:12px 0;border-bottom:1px solid var(--hair);font:400 14.5px/1.5 var(--font);color:var(--ink-72)}
.plan li svg.i{margin-top:3px;width:15px;height:15px;color:var(--ink)}
.plan .btn{width:100%}

/* 질문 */
.faq{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,8fr);gap:72px;margin-top:60px}
.faq .h2{margin-top:0;font-size:clamp(32px,3.6vw,48px)}
.qa{border-top:1px solid var(--hair)}
.qa:last-child{border-bottom:1px solid var(--hair)}
.qa summary{list-style:none;display:flex;justify-content:space-between;align-items:center;gap:20px;padding:24px 0;font:650 18px/1.45 var(--font);letter-spacing:-.02em;cursor:pointer}
.qa summary::-webkit-details-marker{display:none}
.qa summary i{position:relative;width:14px;height:14px;flex:none}
.qa summary i::before,.qa summary i::after{content:"";position:absolute;left:0;top:6px;width:14px;height:1.6px;background:var(--ink);transition:transform .3s var(--ease)}
.qa summary i::after{transform:rotate(90deg)}
.qa[open] summary i::after{transform:rotate(0)}
.qa p{padding:0 48px 26px 0;font:400 15.5px/1.75 var(--font);color:var(--ink-62);text-wrap:pretty}

/* 마무리 */
.end{display:grid;grid-template-columns:minmax(0,6fr) minmax(0,6fr);gap:72px;align-items:center}
.end .h2{margin-top:0}
.find{margin-top:40px;display:flex;align-items:center;gap:10px;height:60px;max-width:500px;padding:0 8px 0 22px;border-radius:999px;background:var(--surface);
  box-shadow:0 0 0 1px var(--line);transition:box-shadow .2s}
.find:focus-within{box-shadow:0 0 0 1.5px var(--ink)}
.find svg.i{width:18px;height:18px;color:var(--ink-62)}
.find input{flex:1;min-width:0;border:0;background:transparent;outline:0;font:400 16px/1 var(--font)}
.find input::placeholder{color:var(--ink-62)}
.chips{margin-top:18px;display:flex;flex-wrap:wrap;gap:8px}
.chips a{display:inline-flex;align-items:center;height:34px;padding:0 14px;border-radius:999px;box-shadow:inset 0 0 0 1px var(--line);font:500 13.5px/1 var(--font);color:var(--ink-72);transition:background .2s}
.chips a:hover{background:var(--surface)}
.s-end{aspect-ratio:4/3}

/* 꼬리 — 스테이징 그대로 */
.foot{margin-top:184px;border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand img{height:13px}
.ftag{margin-top:14px;font:400 14px/22px var(--font);color:var(--ink-72);max-width:280px}
.fgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;max-width:560px;margin-top:32px}
.fcol{display:flex;flex-direction:column}
.fcol h4{margin:0 0 8px;font:600 12.5px/1 var(--font);color:var(--ink-62)}
.fcol a{font:400 14px/1 var(--font);color:var(--ink-72);padding:9px 0} .fcol a:hover{color:var(--ink)}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-62)}
.copy{margin-top:28px;font:400 12px/18px var(--font);color:var(--ink-62)}

/* 나타나기 */
.js .rv{opacity:0;transform:translateY(22px);transition:opacity .9s var(--ease),transform .9s var(--ease)}
.js .rv.in{opacity:1;transform:none}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}.js .rv{opacity:1;transform:none;transition:none}}

@media (max-width:1100px){
  .links{display:none}
  .split,.split.b,.faq,.end{grid-template-columns:minmax(0,1fr);gap:48px}
  .split.b .phone{justify-self:start}
  .sgrid{grid-template-columns:repeat(3,minmax(0,1fr))}
  .hrow{flex-direction:column;align-items:flex-start;gap:32px}
}
@media (max-width:720px){
  :root{--pad:20px}
  html{scroll-padding-top:72px}
  .nav-in{height:60px}
  .login{display:none} .menu{display:inline-flex} .lg-only{display:none}
  .hero{padding-top:40px}
  .news{height:36px;font-size:13px;gap:10px}
  .hero h1{margin-top:24px;font-size:43px;line-height:1.1;letter-spacing:-.052em}
  .hrow{margin-top:26px}
  .lead{font-size:16px}
  .ctas{width:100%;flex-direction:column}
  .ctas .btn{width:100%}
  .s-hero{margin-top:44px;aspect-ratio:4/5;border-radius:22px}
  .slot figcaption{left:20px;right:20px;bottom:18px;font-size:13px}
  .stats{grid-template-columns:1fr 1fr;margin-top:64px}
  .stats>div{padding:24px 12px 22px 0;border-bottom:1px solid var(--hair)}
  .stats>div+div{padding-left:0;border-left:0}
  .stats>div:nth-child(even){padding-left:18px;border-left:1px solid var(--hair)}
  .stats b{font-size:40px}
  .stats span{font-size:14px;margin-top:12px}
  .sec{padding-top:120px}
  .h2{margin-top:40px;font-size:37px;line-height:1.1}
  .sub{font-size:15.5px;margin-top:20px}
  .split{margin-top:36px}
  .idx{grid-template-columns:1fr 1fr;column-gap:18px}
  .idx li{font-size:14.5px}
  .spec{padding:26px 22px 24px;border-radius:20px}
  .spec h3{font-size:25px}
  .sp-chart{padding:16px 12px 8px}
  .sp-chart .cd{display:none} .sp-chart .cm{display:block}
  .sp-bb{grid-template-columns:1fr;gap:18px}
  .sgrid{grid-template-columns:1fr 1fr;column-gap:20px;margin-top:40px}
  .sgrid .sn{font-size:14.5px}
  .dark{margin-top:120px;padding:88px 0 96px}
  .brf h3{font-size:23px}
  .bnums{grid-template-columns:1fr 1fr}
  .phone{max-width:300px;justify-self:center}
  .steps{grid-template-columns:1fr;gap:36px;margin-top:40px}
  .steps h3{margin-top:18px;font-size:23px}
  .stance{flex-direction:column;gap:8px;padding:22px}
  .plans{grid-template-columns:1fr;margin-top:40px;border-radius:22px}
  .plan{padding:28px 24px 26px}
  .plan+.plan{border-left:0;border-top:1px solid var(--hair)}
  .plan .pp b{font-size:44px}
  .faq{margin-top:40px;gap:24px}
  .qa summary{font-size:16.5px;padding:20px 0}
  .qa p{padding-right:0}
  .find{height:56px}
  .s-end{border-radius:22px}
  .foot{margin-top:120px}
}
"""

ICON = {
    "arrow": '<svg class="i" viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
    "search": '<svg class="i" viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M21 21l-3.5-3.5"/></svg>',
    "check": '<svg class="i" viewBox="0 0 24 24"><path d="M5 12.5l4.2 4.2L19 7"/></svg>',
    "video": '<svg viewBox="0 0 24 24"><path d="M8 6.5v11l9-5.5z"/></svg>',
    "image": '<svg viewBox="0 0 24 24"><rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M3.5 16l5-5 4 4 3-3 5 5"/></svg>',
    "cube": '<svg viewBox="0 0 24 24"><path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/></svg>',
}


def slot(cls_, kind, icon, ratio, title, note):
    """그림 자리 — 무엇을(종류) · 어떤 비율로 · 무엇을 담을지."""
    return (f'<figure class="slot {cls_} rv" aria-label="{esc(kind)} 자리 — {esc(title)}"><span class="st">{ICON[icon]}{esc(kind)}</span>'
            f'<span class="sr">{esc(ratio)}</span><figcaption><b>{esc(title)}</b>{esc(note)}</figcaption></figure>')


def nav():
    return (f'<nav class="nav" id="nav"><div class="w nav-in"><a class="brand" href="#"><img src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI"></a>'
            '<div class="links"><a href="#report">리포트</a><a href="#sectors">업종 분석</a><a href="#brief">모닝브리핑</a><a href="#pricing">멤버십</a></div>'
            '<div class="right"><a class="login" href="#">로그인</a><a class="btn sm" href="#"><span class="lg-only">무료로 </span>시작하기</a>'
            '<button class="menu" aria-label="메뉴"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button></div></div></nav>')


def foot():
    return (f'<footer class="foot"><div class="w"><a class="brand" href="#"><img src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI"></a>'
            '<p class="ftag">한국 상장사를 위한 AI 투자 리서치. 데이터와 분석을 한 페이지에.</p>'
            '<div class="fgrid"><div class="fcol"><h4>서비스</h4><a href="#">홈</a><a href="#">리포트</a><a href="#">업종 분석</a><a href="#">관심종목</a><a href="#">멤버십</a><a href="#">모닝브리핑</a></div>'
            '<div class="fcol"><h4>회사</h4><a href="#">About</a><a href="#">문의하기</a><a href="#">피드백</a></div>'
            '<div class="fcol"><h4>정책</h4><a href="#">이용약관</a><a href="#">개인정보처리방침</a></div></div>'
            '<div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>'
            '<div class="copy">© 2026 KOSAI — All rights reserved.</div></div></footer>')


def page():
    n_listed = len(STOCKS["stocks"])
    n_rep = len(INDEX)
    b = brief()
    f = b["_facts"]
    s = BY[SAMPLE]
    r = report(SAMPLE)
    srcg = sources_grouped(r.get("sources"))

    # 첫 화면
    hero = (f'<header class="hero w"><a class="news rv" href="#brief"><b>모닝브리핑 제{b["_no"]}호</b><span class="sep"></span>'
            f'<span class="nt">{esc(b["title"]["ko"])}</span>{ICON["arrow"]}</a>'
            '<h1 class="rv">한국 주식 전 종목의<br>리서치 리포트.</h1>'
            f'<div class="hrow rv"><p class="lead">증권사가 다루지 않는 소형주까지, 코스피·코스닥 {n_rep:,}개 종목을 AI가 같은 틀로 분석합니다. '
            '매 거래일 장이 열리기 전에는 시장 브리핑을 발행합니다.</p>'
            f'<div class="ctas"><a class="btn lg" href="#">무료로 시작하기</a><a class="btn lg ghost" href="#report">리포트 둘러보기 {ICON["arrow"]}</a></div></div>'
            + slot("s-hero", "영상 · 3D", "video", "21 : 9  ·  휴대폰 4 : 5", "첫 화면의 얼굴",
                   "한 장면을 6~10초 동안 아주 느리게, 소리 없이 반복합니다. 글자와 숫자는 그림에 넣지 않고 페이지가 얹습니다.")
            + '</header>')

    # 숫자
    stats = (f'<section class="stats w rv"><div><b>{n_rep:,}</b><span>종목 리포트</span><small>코스피·코스닥 상장사 {n_listed:,}곳 가운데</small></div>'
             f'<div><b>{len(SECTORS_AI)}</b><span>업종 분석</span><small>업종마다 흐름과 주요 종목</small></div>'
             f'<div><b>{avg_sources()}</b><span>리포트 한 편의 평균 출처</span><small>공시 · 재무제표 · 보도</small></div>'
             '<div><b>10</b><span>리포트마다 같은 열 개의 절</span><small>사업 구조부터 종합 의견까지</small></div></section>')

    # 01 리포트 — 소형주 견본
    q = r["quant"]["quarterly"]
    ops = [x["op"] for x in q]
    chart = chart_bars(ops, [q_label(x["q"]) for x in q], w=540, h=210, uid="lp", bg="#f9f8f6", fill="rgba(20,20,20,.15)", last="#141414", text="#141414",
                       tick="rgba(20,20,20,.62)", axis="rgba(20,20,20,.3)", font="'Pretendard Variable',Pretendard,sans-serif", fsize=13, tsize=12,
                       weight=500, radius=4, top_pad=30, bottom_pad=46)
    chart_m = chart_bars(ops, [q_label(x["q"]) for x in q], w=330, h=200, uid="lpm", bg="#f9f8f6", fill="rgba(20,20,20,.15)", last="#141414", text="#141414",
                         tick="rgba(20,20,20,.62)", axis="rgba(20,20,20,.3)", font="'Pretendard Variable',Pretendard,sans-serif", fsize=12.5, tsize=11.5,
                         weight=500, radius=3, top_pad=28, bottom_pad=44)
    rd = r["reportDate"]
    bull = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bull"])
    bear = "".join(f"<li>{esc(x['title']['ko'])}</li>" for x in r["bear"])
    spec = (f'<article class="spec rv" aria-label="{esc(s["name"])} 리포트 견본"><div class="sp-top"><div><b>{esc(s["name"])}</b><span>{esc(s["market"])} · {esc(s["sector"])} · {SAMPLE}</span></div>'
            f'<div class="sp-px"><b>{won(s["price"])}</b><span class="{cls(s["change"])}">{sign(s["change"])}</span></div></div>'
            f'<p class="sp-meta">시가총액 {jo(s["mcap"])} · {rd[:4]}년 {int(rd[5:7])}월 {int(rd[8:10])}일 발행 · 재무 {kdate(r["quant"]["asOf"], False)} 기준</p>'
            f'<h3>{g(r["title"]["ko"])}</h3><p class="sp-lede">{g(r["lead"]["ko"])}</p>'
            f'<div class="sp-chart"><p>분기 영업이익<span>연결 · {q_label(q[0]["q"])}~{q_label(q[-1]["q"])}</span></p><div class="cd">{chart}</div><div class="cm">{chart_m}</div></div>'
            f'<div class="sp-bb"><div><h4><i style="background:var(--up)"></i>강세 요인</h4><ul>{bull}</ul></div>'
            f'<div><h4><i style="background:var(--down)"></i>약세 요인</h4><ul>{bear}</ul></div></div>'
            f'<p class="sp-foot">출처 {len(srcg)}곳 · 10개 절 · 약 {read_minutes(r)}분</p></article>')
    spec = f'<div class="specw">{spec}<p class="spec-cap rv">{esc(s["name"])} 리포트의 실제 첫 부분입니다. 숫자와 문장을 고치지 않았습니다.</p></div>'
    idx = "".join(f"<li><span>{n}</span></li>" for n in ["사업 구조", "실적", "산업", "전망", "밸류에이션", "강세 요인", "약세 요인", "리스크", "체크포인트", "종합 의견"])
    sec1 = (f'<section class="sec w" id="report"><div class="sh rv"><span class="no">01</span><span>리포트</span><span class="mt">{n_rep:,}편</span></div>'
            '<h2 class="h2 rv">소형주에도,<br>리서치가 있습니다.</h2>'
            '<div class="split"><div class="rv"><p class="sub">대형주와 같은 틀로 씁니다. 모든 리포트에 같은 열 개의 절이 들어 있어, 처음 보는 종목도 익숙한 순서로 읽고 서로 견주어 볼 수 있습니다.</p>'
            f'<ol class="idx">{idx}</ol><a class="link" href="#">{esc(s["name"])} 리포트 전체 보기 {ICON["arrow"]}</a></div>{spec}</div></section>')

    # 02 업종
    cnt = Counter(c for x in STOCKS["stocks"] for c in (x.get("categories") or []) if c != "기타")
    top = cnt.most_common()
    mx = top[0][1]
    grid = "".join(f'<li><span class="sn">{esc(k)}<b>{v:,}</b></span><span class="bar"><i style="width:{v / mx * 100:.1f}%"></i></span></li>' for k, v in top)
    sec2 = (f'<section class="sec w" id="sectors"><div class="sh rv"><span class="no">02</span><span>업종 분석</span><span class="mt">{len(top)}개 업종</span></div>'
            f'<h2 class="h2 rv">{len(top)}개 업종,<br>{n_listed:,}개 상장사.</h2>'
            '<p class="sub rv">업종마다 흐름과 주요 종목을 따로 정리합니다. 한 회사를 읽을 때 그 회사가 속한 판도 함께 볼 수 있습니다.</p>'
            f'<ul class="sgrid rv">{grid}</ul><p class="fine rv">숫자는 업종에 속한 상장사 수입니다. 한 회사가 두 업종에 들기도 합니다.</p></section>')

    # 03 모닝브리핑 — 어두운 띠
    secs = "".join(f"<li><span>{g(x['heading']['ko'])}</span></li>" for x in b["sections"])
    nums = ""
    for k in ["코스피", "나스닥", "WTI", "미 10년물"]:
        v, c = f[k]
        cc = (sign(c, 2, pct=False) + "%p") if k.endswith("10년물") else sign(c)
        nums += f'<div><span>{k}</span><b>{v}</b><i class="{cls(c)}">{cc}</i></div>'
    brief_spec = (f'<article class="spec brf rv" aria-label="모닝브리핑 견본"><p class="bm">제{b["_no"]}호 · {kdate(b["date"])} {publish_time(b)} 발행</p>'
                  f'<h3>{g(b["title"]["ko"])}</h3><ol class="bsec">{secs}</ol><div class="bnums">{nums}</div></article>')
    sec3 = (f'<section class="dark" id="brief"><div class="w"><div class="sh rv"><span class="no">03</span><span>모닝브리핑</span><span class="mt">매 거래일 장 시작 전</span></div>'
            '<h2 class="h2 rv">장이 열리기 전에,<br>밤사이 일을 정리합니다.</h2>'
            '<div class="split b"><div><p class="sub rv">미국 증시와 금리, 유가, 환율, 수급 가운데 한국 시장에 닿는 것만 골라 씁니다. 숫자마다 이유를 한 구절 붙입니다.</p>'
            f'{brief_spec}</div>'
            + slot("phone", "영상", "video", "9 : 19", "휴대폰에서 읽는 브리핑", "실제 화면을 녹화해 넣습니다. 엄지로 천천히 넘기는 10초 안팎.")
            + '</div></div></section>')

    # 04 만드는 방법
    sec4 = ('<section class="sec w" id="how"><div class="sh rv"><span class="no">04</span><span>만드는 방법</span></div>'
            '<h2 class="h2 rv">모으고, 읽고,<br>다시 씁니다.</h2><div class="steps">'
            '<div class="rv"><span class="k">01</span><h3>모읍니다</h3><p>한국거래소 시세와 금융감독원 전자공시(DART)의 공시·재무제표, 관련 보도를 모읍니다. 시장 데이터는 매 거래일 저녁에 갱신됩니다.</p></div>'
            '<div class="rv"><span class="k">02</span><h3>읽습니다</h3><p>AI가 모든 종목을 같은 열 개의 절로 분석합니다. 좋게 볼 이유와 조심할 이유를 나란히 적습니다.</p></div>'
            f'<div class="rv"><span class="k">03</span><h3>다시 씁니다</h3><p>기업이 사업보고서·반기보고서·분기보고서를 내면 최신 실적으로 리포트를 다시 씁니다. 쓴 자료는 출처로 남깁니다.</p></div></div>'
            '<div class="stance rv"><b>KOSAI가 하지 않는 것</b><p>매수·매도 의견이나 목표주가를 내지 않습니다. 공시와 실적을 근거로 한 분석·전망·리스크를 정리하고, 판단은 읽는 분께 맡깁니다.</p></div></section>')

    # 05 멤버십 — 스테이징 요금제 그대로
    plans = [
        ("무료", "0", "원", "가입 없이", ["현재가·시가총액·PER·PBR 등 핵심 지표", "리포트 개요와 핵심 요약", "사업 구조", "최근 4개 연도·5개 분기 실적 추이", "조건 검색 · 업종 분석 · 관심종목"],
         '<a class="btn ghost" href="#">리포트 둘러보기</a>'),
        ("BASIC", "9,900", "원 / 월", "하루 5개 리포트 전문", ["무료 플랜의 모든 항목", "잠금 없이 리포트 전문 열람", f"리포트 {n_rep:,}편", "하루 5개 리포트 열람"],
         '<a class="btn" href="#">BASIC 시작하기</a>'),
        ("PRO", "14,900", "원 / 월", "하루 15개 리포트 전문", ["무료 플랜의 모든 항목", "잠금 없이 리포트 전문 열람", f"리포트 {n_rep:,}편", "하루 15개 리포트 열람"],
         '<a class="btn" href="#">PRO 시작하기</a>'),
    ]
    ph = "".join(f'<div class="plan"><h3>{nm}</h3><p class="pp"><b>{pr}</b>{unit}</p><p class="pd">{sub}</p><ul>'
                 + "".join(f"<li>{ICON['check']}<span>{esc(x)}</span></li>" for x in fs) + f"</ul>{cta}</div>" for nm, pr, unit, sub, fs, cta in plans)
    sec5 = ('<section class="sec w" id="pricing"><div class="sh rv"><span class="no">05</span><span>멤버십</span><span class="mt">언제든 해지할 수 있습니다</span></div>'
            '<h2 class="h2 rv">데이터는 무료로.<br>리포트 전문은 구독으로.</h2>'
            f'<div class="plans rv">{ph}</div>'
            '<p class="fine rv">표시 금액은 부가가치세 포함입니다. BASIC과 PRO는 내용이 같고, 하루에 열 수 있는 리포트 수만 다릅니다.</p></section>')

    # 질문 — 스테이징 요금제 페이지의 답을 줄여 씀
    qa = [
        ("종목 추천이나 목표주가를 주나요?", "아닙니다. KOSAI는 매수·매도 의견이나 목표주가를 제시하지 않습니다. 공시와 실적을 근거로 분석·전망·리스크를 정리하며, 투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있습니다."),
        ("리포트는 언제 새로 쓰나요?", "기업이 DART에 사업보고서·반기보고서·분기보고서를 제출하면 최신 실적을 반영해 다시 씁니다. 주가·시가총액·PER 같은 시장 데이터는 매 거래일 저녁에 갱신됩니다."),
        ("무료로는 어디까지 볼 수 있나요?", "핵심 지표, 리포트 개요와 요약, 사업 구조, 최근 4개 연도·5개 분기 실적은 가입 없이 보실 수 있습니다."),
        ("구독은 언제든 해지할 수 있나요?", "설정의 구독 항목에서 직접 해지하실 수 있습니다. 해지한 뒤에도 이미 결제한 기간이 끝날 때까지 그대로 이용하실 수 있습니다."),
    ]
    qh = "".join(f'<details class="qa"{" open" if i == 0 else ""}><summary>{esc(qq)}<i></i></summary><p>{g(aa)}</p></details>' for i, (qq, aa) in enumerate(qa))
    faq = f'<section class="sec w"><div class="sh rv"><span>자주 묻는 질문</span></div><div class="faq rv"><h2 class="h2">궁금하신 점</h2><div>{qh}</div></div></section>'

    # 마무리
    picks = ["005930", "000660", "005380", "035420", SAMPLE, "005950"]
    chips = "".join(f'<a href="#">{esc(BY[t]["name"])}</a>' for t in picks if t in BY)
    end = ('<section class="sec w"><div class="end"><div class="rv"><h2 class="h2">관심 있는 종목부터<br>찾아보세요.</h2>'
           f'<form class="find" role="search" onsubmit="return false">{ICON["search"]}<input placeholder="종목명 또는 종목코드" aria-label="종목 찾기"><button class="btn" type="button">찾기</button></form>'
           f'<div class="chips">{chips}</div></div>'
           + slot("s-end", "이미지", "image", "4 : 3", "마무리 장면", "첫 화면과 같은 빛·재질로 만든 정지 그림 한 장. 첫 화면 영상의 마지막 장면을 써도 됩니다.")
           + '</div></section>')

    js = ("<script>document.documentElement.classList.add('js');(function(){var n=document.getElementById('nav');function s(){n.classList.toggle('on',scrollY>8)}"
          "addEventListener('scroll',s,{passive:true});s();if(!('IntersectionObserver'in window)){document.querySelectorAll('.rv').forEach(function(e){e.classList.add('in')});return}"
          "var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{rootMargin:'0px 0px -8% 0px'});"
          "document.querySelectorAll('.rv').forEach(function(e){io.observe(e)})})();</script>")
    head = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#f9f8f6"><title>KOSAI — 한국 주식 전 종목의 리서치 리포트</title>'
            f'{FONT}<link rel="stylesheet" href="landing.css"></head><body>')
    return head + nav() + f"<main>{hero}{stats}{sec1}{sec2}{sec3}{sec4}{sec5}{faq}{end}</main>" + foot() + js + "</body></html>"


def briefs_first():
    from data import briefs
    return briefs()[0][:10]


def avg_sources():
    import json
    d = os.path.join(ROOT, "data/reports_v2")
    n = []
    for f in os.listdir(d):
        if not f.endswith(".json"):
            continue
        r = json.load(open(os.path.join(d, f), encoding="utf-8"))
        if isinstance(r, dict) and r.get("sources"):
            n.append(len(r["sources"]))
    return round(sum(n) / len(n))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "landing.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    html = page()
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    print(f"preview/concepts/landing/index.html {len(html):,}자 · landing.css {len(CSS):,}자")
