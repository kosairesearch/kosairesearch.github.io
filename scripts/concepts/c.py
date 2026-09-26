"""시안 C — 쇼케이스. 한 장면에 한 메시지, 큰 제목, 제품(리포트)을 제품 사진처럼 보여 준다."""
from data import (BY, esc, sign, arrow, cls, won, money, jo, kdate, kdate_full, grp, latest, sectors, movers,
                  valuation, report, brief, PRICE_DATE, MINUS)
from common import chunk, paras, bars_svg, line_svg, treemap, q_label, spark

FONTS = ('<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>'
         '<link href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">')

CSS = r"""
:root{
  --bg:#fff; --bg2:#f5f5f7; --t1:#1d1d1f; --t2:#6e6e73; --t3:#86868b; --line:#d2d2d7; --line2:#e8e8ed;
  --up:#d0182f; --down:#0a62c7;
  --sans:'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo',sans-serif;
  --w:1024px; --wide:1260px; --ease:cubic-bezier(.2,.8,.2,1);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:110px;overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--t1);font:400 17px/1.47 var(--sans);letter-spacing:-.012em;-webkit-font-smoothing:antialiased;
  word-break:keep-all;overflow-wrap:anywhere;overflow-x:clip}
a{color:inherit;text-decoration:none}
h1,h2,h3,h4,p{margin:0}
.wrap{max-width:var(--w);margin:0 auto;padding:0 22px}
.wide{max-width:var(--wide);margin:0 auto;padding:0 22px}
.tnum{font-variant-numeric:tabular-nums}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--t2)}

/* 전역 머리 */
.gnav{position:sticky;top:0;z-index:50;height:48px;background:rgba(251,251,253,.8);backdrop-filter:saturate(1.8) blur(20px);-webkit-backdrop-filter:saturate(1.8) blur(20px)}
.gnav-in{max-width:1024px;margin:0 auto;padding:0 22px;height:48px;display:flex;align-items:center;justify-content:space-between;font:400 13px/1 var(--sans)}
.gnav a{color:rgba(0,0,0,.8);transition:color .2s} .gnav a:hover{color:#000}
.gnav .logo{font:700 15px/1 var(--sans);letter-spacing:.24em;margin-right:-.24em;color:var(--t1)}
.gnav svg{width:16px;height:16px;display:block}
.lnav{position:sticky;top:48px;z-index:45;height:52px;background:rgba(255,255,255,.8);backdrop-filter:saturate(1.8) blur(20px);-webkit-backdrop-filter:saturate(1.8) blur(20px);
  border-bottom:1px solid rgba(0,0,0,.12)}
.lnav-in{max-width:1024px;margin:0 auto;padding:0 22px;height:52px;display:flex;align-items:center;gap:24px}
.lnav h2{font:650 21px/1 var(--sans);letter-spacing:-.02em;margin-right:auto}
.lnav a{font:400 12.5px/1 var(--sans);color:rgba(0,0,0,.72)} .lnav a:hover{color:#000} .lnav a.on{color:#000;font-weight:600} .lnav a.btn{color:#fff}
.btn{display:inline-flex;align-items:center;justify-content:center;height:44px;padding:0 22px;border-radius:980px;background:var(--t1);color:#fff;
  font:500 17px/1 var(--sans);letter-spacing:-.02em;transition:background .2s}
.btn:hover{background:#000}
.btn.sm{height:28px;padding:0 12px;font-size:12.5px;font-weight:500}
.btn.light{background:#fff;color:var(--t1)} .btn.light:hover{background:#f0f0f2}
.more{font:400 17px/1 var(--sans);color:var(--t1);display:inline-flex;align-items:center;gap:4px}
.more:hover{text-decoration:underline;text-underline-offset:.2em}
.more::after{content:"›";font-size:1.25em;line-height:0;transform:translateY(-1px)}

/* 첫 장면 */
.hero{padding:88px 0 0;text-align:center;background:var(--bg);overflow:hidden}
.eyebrow{font:600 21px/1.2 var(--sans);letter-spacing:-.01em;color:#bf4800}
.h1{margin-top:10px;font:700 88px/1.04 var(--sans);letter-spacing:-.045em;text-wrap:balance}
.lead{margin:22px auto 0;max-width:640px;font:500 24px/1.4 var(--sans);letter-spacing:-.022em;color:var(--t2)}
.ctas{margin-top:30px;display:flex;justify-content:center;align-items:center;gap:30px}
.phones{position:relative;margin:70px auto 0;height:640px;max-width:900px}
.phone{position:absolute;top:0;width:310px;height:640px;border-radius:54px;background:#1b1b1d;padding:11px;
  box-shadow:0 0 0 1.5px #3a3a3c inset,0 2px 0 rgba(255,255,255,.2) inset,0 50px 80px -30px rgba(0,0,0,.35),0 30px 60px -40px rgba(0,0,0,.4)}
.phone .scr{position:relative;width:100%;height:100%;border-radius:44px;overflow:hidden;background:#fff;text-align:left}
.phone .isl{position:absolute;top:11px;left:50%;transform:translateX(-50%);width:96px;height:28px;border-radius:20px;background:#000;z-index:2}
.phone.p1{left:50%;transform:translateX(-100%) translateX(-18px) translateY(40px) rotate(-3deg)}
.phone.p2{left:50%;transform:translateX(18px) rotate(3deg)}
.sb{height:50px;display:flex;align-items:center;justify-content:space-between;padding:6px 26px 0 30px;font:600 14px/1 var(--sans)}
.sb i{display:inline-block;width:24px;height:11px;border:1.5px solid #1d1d1f;border-radius:3px;position:relative}
.sb i::after{content:"";position:absolute;inset:1.5px 5px 1.5px 1.5px;background:#1d1d1f;border-radius:1px}
.ap{padding:4px 20px 0}
.ap .bar{display:flex;justify-content:space-between;align-items:center;font:700 12px/1 var(--sans);letter-spacing:.2em;margin:6px 0 18px}
.ap .kk{font:600 11.5px/1 var(--sans);color:var(--t2)}
.ap .nm{font:700 26px/1.1 var(--sans);letter-spacing:-.035em;margin-top:6px}
.ap .px{display:flex;align-items:baseline;gap:8px;margin-top:10px;font:600 30px/1 var(--sans);letter-spacing:-.03em}
.ap .px small{font:600 13px/1 var(--sans)}
.ap .th{margin-top:16px;font:650 17px/1.35 var(--sans);letter-spacing:-.03em}
.ap .ch{margin-top:14px;background:var(--bg2);border-radius:16px;padding:12px 12px 4px}
.ap .ch b{display:flex;justify-content:space-between;font:600 11px/1 var(--sans);color:var(--t2)}
.ap .ch b span{color:var(--t1);font-size:13px}
.ap .kp{margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ap .kp div{background:var(--bg2);border-radius:14px;padding:10px 12px}
.ap .kp dt{font:500 10.5px/1 var(--sans);color:var(--t2)} .ap .kp dd{margin:6px 0 0;font:650 16px/1 var(--sans)}
.ap .bdate{font:600 12px/1.2 var(--sans);color:#bf4800;margin-top:4px}
.ap .bh{font:700 22px/1.28 var(--sans);letter-spacing:-.035em;margin-top:8px}
.ap .bp{font:400 13px/1.6 var(--sans);color:#424245;margin-top:12px}
.ap .mk{margin-top:14px;border-top:1px solid var(--line2)}
.ap .mk div{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--line2);font:500 12.5px/1 var(--sans)}

/* 숫자 띠 */
.band{background:#000;color:#f5f5f7;padding:110px 0 120px;text-align:center;margin-top:-40px;position:relative}
.band h2{font:700 56px/1.08 var(--sans);letter-spacing:-.04em}
.band h2 span{color:#86868b}
.nums{margin:70px auto 0;max-width:980px;display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.nums b{display:block;font:700 64px/1 var(--sans);letter-spacing:-.045em;background:linear-gradient(180deg,#fff,#b8b8c0);-webkit-background-clip:text;background-clip:text;color:transparent}
.nums span{display:block;margin-top:12px;font:500 17px/1.4 var(--sans);color:#a1a1a6}

/* 타일 */
.gal{background:var(--bg2);padding:110px 0}
.gal h2.t{font:700 56px/1.08 var(--sans);letter-spacing:-.04em;text-align:center}
.gal p.s{margin:16px auto 0;max-width:620px;text-align:center;font:500 21px/1.4 var(--sans);color:var(--t2)}
.grid{margin-top:56px;display:grid;grid-template-columns:repeat(6,1fr);gap:20px}
.tile{background:#fff;border-radius:28px;padding:36px 36px 34px;overflow:hidden;position:relative;min-height:420px;display:flex;flex-direction:column}
.tile.s2{grid-column:span 2} .tile.s3{grid-column:span 3} .tile.s4{grid-column:span 4} .tile.s6{grid-column:span 6}
.tile.dark{background:#000;color:#f5f5f7}
.tile .ey{font:600 17px/1.2 var(--sans);color:var(--t2)} .tile.dark .ey{color:#a1a1a6}
.tile h3{margin-top:8px;font:700 32px/1.14 var(--sans);letter-spacing:-.035em;text-wrap:balance}
.tile p{margin-top:12px;font:400 17px/1.5 var(--sans);color:var(--t2)} .tile.dark p{color:#a1a1a6}
.tile .more{margin-top:auto;padding-top:22px}
.tile.dark .more{color:#2997ff}
.tmap{position:relative;width:100%;aspect-ratio:1000/620;margin-top:24px;border-radius:16px;overflow:hidden}
.tl{position:absolute;box-shadow:inset 0 0 0 1.5px #fff;padding:10px 11px;overflow:hidden;color:#fff}
.tl .tn{display:block;font:650 13px/1.2 var(--sans)} .tl .tc{display:block;font:500 12.5px/1 var(--sans);margin-top:3px;opacity:.9}
.tl.l3{padding:18px} .tl.l3 .tn{font:700 24px/1.1 var(--sans);letter-spacing:-.03em} .tl.l3 .tc{font:600 20px/1 var(--sans);margin-top:6px}
.tl.l1 .tc,.tl.l0 .tn,.tl.l0 .tc,.tl .ts{display:none} .tl.l1{padding:7px 8px} .tl.l1 .tn{font-size:11.5px} .tl.l0{padding:0}
.big{font:700 72px/1 var(--sans);letter-spacing:-.05em;margin-top:18px}
.big small{font:600 24px/1 var(--sans);letter-spacing:-.02em;margin-left:4px}
.plans{display:flex;gap:26px;margin-top:22px}
.plans div{font:500 14px/1.4 var(--sans);color:#a1a1a6} .plans b{display:block;font:700 30px/1 var(--sans);letter-spacing:-.04em;color:#f5f5f7;margin-bottom:6px}
.wl{margin-top:22px;border-radius:18px;background:var(--bg2);padding:6px 16px}
.wl div{display:grid;grid-template-columns:1fr auto auto;gap:14px;align-items:center;padding:13px 0;border-bottom:1px solid var(--line2);font:500 15px/1 var(--sans)}
.wl div:last-child{border:0} .wl b{font-weight:650}
.rlist{margin-top:18px}
.topics{list-style:none;margin:26px 0 0;padding:0;border-top:1px solid var(--line2)}
.topics li{display:flex;gap:14px;padding:13px 0;border-bottom:1px solid var(--line2);font:600 17px/1.4 var(--sans);letter-spacing:-.02em}
.topics li span{color:#bf4800;font-weight:700;width:14px}
.rlist a{display:block;padding:14px 0;border-top:1px solid var(--line2)}
.rlist a span{display:block;font:500 13px/1 var(--sans);color:var(--t2);margin-bottom:6px}
.rlist a b{font:650 18px/1.35 var(--sans);letter-spacing:-.025em}

/* 캐러셀 */
.car{padding:110px 0 120px;background:var(--bg)}
.car-h{display:flex;justify-content:space-between;align-items:flex-end}
.car-h h2{font:700 48px/1.1 var(--sans);letter-spacing:-.04em}
.track{display:flex;gap:20px;overflow-x:auto;scroll-snap-type:x mandatory;padding:40px max(22px,calc((100vw - 1260px)/2 + 22px)) 30px;scroll-padding:0 max(22px,calc((100vw - 1260px)/2 + 22px));scrollbar-width:none}
.track::-webkit-scrollbar{display:none}
.rc{flex:none;width:372px;height:500px;scroll-snap-align:start;border-radius:28px;background:var(--bg2);padding:34px 32px;display:flex;flex-direction:column;
  transition:transform .35s var(--ease)}
.rc:hover{transform:scale(1.015)}
.rc .ey{font:600 14px/1 var(--sans);color:var(--t2)}
.rc h3{margin-top:14px;font:700 30px/1.2 var(--sans);letter-spacing:-.04em;text-wrap:balance}
.rc p{margin-top:14px;font:400 16px/1.55 var(--sans);color:var(--t2);display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}
.rc .spk{margin-top:auto;display:flex;justify-content:space-between;align-items:flex-end;font:500 13px/1 var(--sans);color:var(--t2);padding-bottom:18px;border-bottom:1px solid var(--line)}
.rc .ft{margin-top:18px;display:flex;align-items:baseline;justify-content:space-between;font:600 17px/1 var(--sans)}
.rc .ft small{font:600 14px/1}
.arrows{display:flex;gap:14px}
.arrows button{width:36px;height:36px;border-radius:50%;border:0;background:#e8e8ed;color:#1d1d1f;font:400 20px/1 var(--sans);cursor:pointer}

.foot{background:var(--bg2);padding:34px 0 40px;font:400 12px/1.6 var(--sans);color:var(--t2)}
.foot .fin{border-bottom:1px solid var(--line);padding-bottom:18px;margin-bottom:18px}
.f-cols{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-bottom:22px}
.f-cols b{display:block;color:var(--t1);font-weight:600;margin-bottom:8px}
.f-cols a{display:block;margin-bottom:6px} .f-cols a:hover{text-decoration:underline}

/* 종목 */
.s-hero{padding:80px 0 0;text-align:center}
.s-hero .eyebrow{font-size:19px}
.s-name{margin-top:8px;font:700 96px/1.02 var(--sans);letter-spacing:-.05em}
.s-th{margin:22px auto 0;max-width:760px;font:650 34px/1.25 var(--sans);letter-spacing:-.035em;text-wrap:balance}
.s-px{margin-top:26px;display:flex;justify-content:center;align-items:baseline;gap:12px;font:600 24px/1 var(--sans);letter-spacing:-.02em}
.s-px small{font:500 15px/1 var(--sans);color:var(--t2)}
.s-ctas{margin-top:30px;display:flex;justify-content:center;gap:28px;align-items:center}
.hl{margin-top:90px;display:grid;grid-template-columns:repeat(4,1fr);gap:20px}
.hl div{background:var(--bg2);border-radius:28px;padding:34px 30px 30px;text-align:left}
.hl b{display:block;font:700 48px/1 var(--sans);letter-spacing:-.05em}
.hl span{display:block;margin-top:14px;font:500 17px/1.4 var(--sans);color:var(--t2)}
.hl em{font-style:normal;color:var(--t1);font-weight:650}
.sec{padding:120px 0 0}
.sec.alt{background:var(--bg2);padding:110px 0 120px;margin-top:120px}
.sec h2.t{font:700 56px/1.08 var(--sans);letter-spacing:-.04em;text-align:center;text-wrap:balance}
.sec p.s{margin:18px auto 0;max-width:680px;text-align:center;font:500 21px/1.45 var(--sans);color:var(--t2)}
.kp5{margin:56px auto 0;max-width:820px;list-style:none;padding:0;counter-reset:k}
.kp5 li{counter-increment:k;display:grid;grid-template-columns:64px 1fr;padding:24px 0;border-top:1px solid var(--line2);font:500 21px/1.5 var(--sans);letter-spacing:-.02em}
.kp5 li::before{content:counter(k);font:700 21px/1.5 var(--sans);color:#bf4800}
.charts{margin-top:60px;display:grid;grid-template-columns:1fr 1fr;gap:20px}
.cht{background:#fff;border-radius:28px;padding:34px 30px 24px}
.cht h3{font:600 17px/1 var(--sans);color:var(--t2)}
.cht .v{margin-top:10px;font:700 44px/1 var(--sans);letter-spacing:-.045em}
.cht .v small{font:600 17px/1 var(--sans);color:var(--t2);margin-left:8px;letter-spacing:-.01em}
.art{max-width:692px;margin:0 auto}
.art section{padding-top:100px}
.art .no{font:600 17px/1 var(--sans);color:#bf4800}
.art h2{margin-top:10px;font:700 40px/1.12 var(--sans);letter-spacing:-.04em}
.art p{margin-top:22px;font:400 19px/1.68 var(--sans);letter-spacing:-.02em;color:#1d1d1f}
.art p.intro{font:600 24px/1.45 var(--sans);letter-spacing:-.03em}
.tbl{width:100%;border-collapse:collapse;margin-top:34px;font:500 15px/1 var(--sans)}
.tbl caption{text-align:left;font:600 15px/1 var(--sans);color:var(--t2);padding-bottom:14px}
.tbl th{font:600 13px/1 var(--sans);color:var(--t2);text-align:right;padding:12px 0 12px 10px;border-bottom:1px solid var(--line)}
.tbl td{text-align:right;padding:15px 0 15px 10px;border-bottom:1px solid var(--line2);font-variant-numeric:tabular-nums}
.tbl th:first-child,.tbl td:first-child{text-align:left;padding-left:0}
.bb{margin-top:60px;display:grid;grid-template-columns:1fr 1fr;gap:20px;text-align:left}
.bbt{background:#fff;border-radius:28px;padding:36px 34px}
.bbt .ey{font:600 17px/1 var(--sans)} .bbt.bull .ey{color:var(--up)} .bbt.bear .ey{color:var(--down)}
.bbt h3{margin-top:8px;font:700 32px/1.15 var(--sans);letter-spacing:-.04em}
.bbt .it{padding:22px 0;border-top:1px solid var(--line2)} .bbt .it:first-of-type{margin-top:20px}
.bbt h4{margin:0;font:650 19px/1.4 var(--sans);letter-spacing:-.025em}
.bbt p{margin-top:8px;font:400 15.5px/1.65 var(--sans);color:#424245}
.rk{margin-top:56px;display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.rk div{background:var(--bg2);border-radius:28px;padding:32px 30px}
.rk b{display:block;font:650 21px/1.3 var(--sans);letter-spacing:-.025em}
.rk p{margin-top:12px;font:400 15.5px/1.65 var(--sans);color:#424245}
.cps{margin:56px auto 0;max-width:820px}
.cps div{display:grid;grid-template-columns:190px 1fr;gap:28px;padding:26px 0;border-top:1px solid var(--line2)}
.cps b{font:700 21px/1.3 var(--sans);letter-spacing:-.03em}
.cps p{font:400 17px/1.6 var(--sans);color:#424245}
.quote{margin:60px auto 0;max-width:880px;text-align:center;font:650 32px/1.4 var(--sans);letter-spacing:-.035em;text-wrap:balance}
.vrest{margin:34px auto 0;max-width:692px}
.vrest p{margin-top:18px;font:400 19px/1.68 var(--sans);letter-spacing:-.02em}
.srcs{margin:56px auto 0;max-width:820px;display:flex;flex-wrap:wrap;justify-content:center;gap:8px 18px;font:400 13px/1.6 var(--sans);color:var(--t2)}
.disc{margin:26px auto 0;max-width:680px;text-align:center;font:400 13px/1.6 var(--sans);color:var(--t2)}

@media (max-width:1068px){
  .grid{grid-template-columns:repeat(2,1fr)} .tile.s2,.tile.s3,.tile.s4{grid-column:span 1} .tile.s6{grid-column:span 2}
  .hl{grid-template-columns:repeat(2,1fr)} .rk{grid-template-columns:1fr}
}
@media (max-width:734px){
  body{font-size:17px}
  .gnav-in a:not(.logo):not(.ic){display:none}
  .hero{padding-top:56px}
  .eyebrow{font-size:17px}
  .h1{font-size:48px;line-height:1.08}
  .lead{font-size:19px}
  .ctas{flex-direction:column;gap:18px}
  .phones{height:520px;margin-top:50px}
  .phone{width:250px;height:520px;border-radius:44px;padding:9px} .phone .scr{border-radius:36px}
  .phones{height:470px} .phone{width:224px;height:466px;border-radius:40px;padding:8px} .phone .scr{border-radius:33px}
  .phone.p1{transform:translateX(-96%) translateY(22px) rotate(-4deg)} .phone.p2{transform:translateX(-6%) rotate(4deg)}
  .ap .bp{display:none} .ap .kp{display:none}
  .ap{padding:0 16px} .ap .nm{font-size:22px} .ap .px{font-size:25px} .ap .th{font-size:15px} .ap .bh{font-size:19px}
  .band{padding:80px 0} .band h2{font-size:34px} .nums{grid-template-columns:1fr 1fr;row-gap:40px;margin-top:50px} .nums b{font-size:48px}
  .gal{padding:80px 0} .gal h2.t,.sec h2.t{font-size:36px} .gal p.s,.sec p.s{font-size:18px}
  .grid{grid-template-columns:1fr} .tile.s2,.tile.s3,.tile.s4,.tile.s6{grid-column:span 1} .tile{min-height:0;padding:30px 26px} .tile h3{font-size:26px}
  .big{font-size:56px}
  .car{padding:80px 0} .car-h h2{font-size:34px} .arrows{display:none}
  .rc{width:300px;height:440px;padding:28px 26px} .rc h3{font-size:25px}
  .f-cols{grid-template-columns:1fr 1fr}
  .lnav a{display:none} .lnav .btn{display:inline-flex}
  .s-hero{padding-top:50px} .s-name{font-size:56px} .s-th{font-size:25px}
  .hl{grid-template-columns:1fr 1fr;gap:12px;margin-top:60px} .hl div{padding:24px 20px;border-radius:22px} .hl b{font-size:34px} .hl span{font-size:14.5px}
  .kp5 li{grid-template-columns:40px 1fr;font-size:18px}
  .charts{grid-template-columns:1fr} .cht .v{font-size:36px}
  .art h2{font-size:30px} .art p{font-size:17px} .art p.intro{font-size:20px}
  .bb{grid-template-columns:1fr}
  .cps div{grid-template-columns:1fr;gap:8px}
  .quote{font-size:24px}
  .vrest p{font-size:17px}
}
"""

SEARCH = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'
USER = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="8.5" r="3.6"/><path d="M4.8 19.5c1.3-3.3 4-4.9 7.2-4.9s5.9 1.6 7.2 4.9"/></svg>'


def head(title):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#ffffff">'
            f'<title>{esc(title)}</title>{FONTS}<link rel="stylesheet" href="c.css"></head><body>')


def gnav():
    items = "".join(f'<a href="#">{n}</a>' for n in ["리포트", "업종", "모닝브리핑", "관심종목", "멤버십", "소개"])
    return (f'<nav class="gnav"><div class="gnav-in"><a class="logo" href="index.html">KOSAI</a>{items}'
            f'<a class="ic" href="#" aria-label="검색">{SEARCH}</a><a class="ic" href="#" aria-label="계정">{USER}</a></div></nav>')


def footer():
    return ('<footer class="foot"><div class="wrap"><p class="fin">KOSAI의 리포트는 AI가 공시·재무 데이터와 보도를 분석해 작성한 정보이며, 투자 권유가 아닙니다. '
            '시세는 한국거래소, 재무는 금융감독원 전자공시(DART) 자료를 씁니다.</p>'
            '<div class="f-cols"><div><b>읽기</b><a href="#">리포트</a><a href="#">업종</a><a href="#">모닝브리핑</a></div>'
            '<div><b>계정</b><a href="#">관심종목</a><a href="#">멤버십</a><a href="#">설정</a></div>'
            '<div><b>KOSAI</b><a href="#">소개</a><a href="#">문의</a><a href="#">피드백</a></div>'
            '<div><b>정책</b><a href="#">이용약관</a><a href="#">개인정보처리방침</a></div></div>'
            '<p>상호 코사이 · 대표 임범준 · 사업자등록번호 380-25-02019 · 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호 · hello@kosai.kr</p>'
            '<p style="margin-top:6px">Copyright © 2026 KOSAI. All rights reserved.</p></div></footer>')


def light_bars(vals, labels, w=460, h=240, color="#1d1d1f", fmt=money):
    return bars_svg(vals, labels, w=w, h=h, fill="#d2d2d7", highlight_last=True, fill_last=color, font="inherit", fsize=14, tsize=13, weight=600,
                    label_fill="#1d1d1f", tick_fill="#6e6e73", axis="#d2d2d7", radius=6, fmt=fmt)


def phones(b):
    s = BY["005930"]
    r = report("005930")
    v = valuation("005930")
    q = r["quant"]["quarterly"]
    ch = bars_svg([x["op"] for x in q], [q_label(x["q"]) for x in q], w=260, h=120, fill="#d2d2d7", highlight_last=True, fill_last="#1d1d1f",
                  font="inherit", fsize=10.5, tsize=9.5, weight=600, label_fill="#1d1d1f", tick_fill="#86868b", axis="#d2d2d7", radius=3, top_pad=18, bottom_pad=18)
    f = b["_facts"]
    mk = "".join(f'<div><span>{k}</span><span class="tnum">{f[k][0]} <b class="{cls(f[k][1])}">{sign(f[k][1])}</b></span></div>' for k in ["코스피", "코스닥", "나스닥", "WTI"])
    p1 = (f'<div class="phone p1"><div class="scr"><div class="isl"></div><div class="sb"><span>7:28</span><i></i></div><div class="ap">'
          f'<div class="bar"><span>KOSAI</span></div><p class="bdate">모닝브리핑 · {kdate(b["date"])}</p><p class="bh">{esc(b["title"]["ko"])}</p>'
          f'<p class="bp">{esc(chunk(b["summary"]["ko"], 120)[0])}</p><div class="mk">{mk}</div></div></div></div>')
    p2 = (f'<div class="phone p2"><div class="scr"><div class="isl"></div><div class="sb"><span>9:41</span><i></i></div><div class="ap">'
          f'<div class="bar"><span>KOSAI</span></div><p class="kk">반도체 · 코스피 005930</p><p class="nm">{esc(s["name"])}</p>'
          f'<p class="px tnum">{grp(s["price"])}원<small class="{cls(s["change"])}">{arrow(s["change"])}{abs(s["change"]):.2f}%</small></p>'
          f'<p class="th">{esc(r["title"]["ko"])}</p><div class="ch"><b>분기 영업이익<span>{money(q[-1]["op"])}</span></b>{ch}</div>'
          f'<dl class="kp"><div><dt>PER</dt><dd class="tnum">{v["per"]:.1f}배</dd></div><div><dt>ROE</dt><dd class="tnum">{v["roe"]:.1f}%</dd></div></dl></div></div></div>')
    return f'<div class="phones">{p1}{p2}</div>'


def tint(chg):
    a = min(abs(chg) / 3.0, 1.0)
    if chg > 0.05:
        return f"rgb({int(232 - a * 40)},{int(80 - a * 50)},{int(96 - a * 50)})"
    if chg < -0.05:
        return f"rgb({int(80 - a * 50)},{int(140 - a * 50)},{int(225 - a * 25)})"
    return "#8e8e93"


def home():
    b = brief()
    reps = latest(8)
    secs, tot = sectors()
    hero = (f'<section class="hero"><div class="wrap"><p class="eyebrow">매 거래일 아침 7시</p><h1 class="h1">상장사 전부를,<br>한 장씩.</h1>'
            f'<p class="lead">코스피·코스닥 2,682개 종목의 공시와 실적을 AI가 읽고, 종목마다 한 편의 리포트로 씁니다.</p>'
            f'<div class="ctas"><a class="btn" href="stock.html">리포트 둘러보기</a><a class="more" href="#">오늘의 모닝브리핑</a></div></div>{phones(b)}</section>')
    band = ('<section class="band"><div class="wrap"><h2>숫자는 무료로.<br><span>해석은 매일 아침.</span></h2>'
            '<div class="nums"><div><b class="tnum">2,682</b><span>코스피·코스닥<br>전 종목</span></div><div><b class="tnum">2,680</b><span>종목별<br>분석 리포트</span></div>'
            f'<div><b class="tnum">29</b><span>업종 분석과<br>시장 지도</span></div><div><b class="tnum">{b["_no"]}</b><span>호째 이어진<br>모닝브리핑</span></div></div></div></section>')

    def tile_t(s, x, y, w, h, size):
        return (f'<span class="tl {size}" style="left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;background:{tint(s["chg"])}">'
                f'<span class="tn">{esc(s["name"])}</span><span class="tc tnum">{sign(s["chg"])}</span></span>')
    tm = treemap(secs, W=1000, H=620, tile=tile_t, px=0.4)
    wl = "".join(f'<div><b>{esc(BY[t]["name"])}</b><span class="tnum">{grp(BY[t]["price"])}</span><span class="tnum {cls(BY[t]["change"])}">{sign(BY[t]["change"])}</span></div>'
                 for t in ["005930", "000660", "005380", "035420"])
    rl = "".join(f'<a href="stock.html"><span>{esc(r["name"])} · {esc(r["sector"])}</span><b>{esc(r["title"])}</b></a>' for r in reps[:3])
    gal = (f'<section class="gal"><div class="wide"><h2 class="t">필요한 건, 한 곳에.</h2>'
           f'<p class="s">브리핑으로 시장을 읽고, 지도로 흐름을 보고, 리포트로 한 회사를 깊게.</p><div class="grid">'
           f'<div class="tile s4"><p class="ey">모닝브리핑 · {kdate(b["date"])} 07:28</p><h3>{esc(b["title"]["ko"])}</h3>'
           f'<p>{esc(chunk(b["summary"]["ko"], 160)[0])}</p><ol class="topics">' + "".join(f'<li><span>{i + 1}</span>{esc(sx["heading"]["ko"])}</li>' for i, sx in enumerate(b["sections"][:4])) + '</ol><a class="more" href="#">브리핑 읽기</a></div>'
           f'<div class="tile s2 dark"><p class="ey">멤버십</p><h3>데이터는 무료.<br>해석은 구독.</h3>'
           f'<div class="plans"><div><b class="tnum">9,900</b>BASIC · 월</div><div><b class="tnum">14,900</b>PRO · 월</div></div>'
           f'<p>시세·재무·핵심 지표는 누구에게나 무료. 분석과 전망, 리스크 진단은 멤버십으로 읽습니다.</p><a class="more" href="#">알아보기</a></div>'
           f'<div class="tile s3"><p class="ey">시장 지도</p><h3>시가총액의 {secs[0]["share"]:.0f}%가 반도체.</h3><div class="tmap">{tm}</div><a class="more" href="#">업종 분석</a></div>'
           f'<div class="tile s3"><p class="ey">관심종목</p><h3>어느 기기에서나<br>같은 목록.</h3><div class="wl">{wl}</div><a class="more" href="#">관심종목 보기</a></div>'
           f'<div class="tile s6" style="min-height:0"><p class="ey">새로 나온 리포트</p><h3>오늘 밤에도 새 리포트가 쓰입니다.</h3><div class="rlist">{rl}</div></div>'
           f'</div></div></section>')
    cards = "".join(
        f'<a class="rc" href="stock.html"><p class="ey">{esc(r["sector"])} · {esc(r["name"])}</p><h3>{esc(r["title"])}</h3><p>{esc(r["lead"])}</p>'
        f'<div class="spk"><span>분기 영업이익</span>{spark(r.get("ops") or [], w=140, h=44, fill="#d2d2d7", last="#1d1d1f", neg="#d2d2d7", zero="#c7c7cc", radius=2)}</div>'
        f'<div class="ft"><span class="tnum">{won(r["price"])}</span><small class="tnum {cls(r["change"])}">{arrow(r["change"])} {abs(r["change"] or 0):.2f}%</small></div></a>'
        for r in reps)
    car = (f'<section class="car"><div class="wide car-h"><h2>새로 나온 리포트.</h2><div class="arrows"><button aria-label="이전">‹</button><button aria-label="다음">›</button></div></div>'
           f'<div class="track">{cards}</div></section>')
    js = ("<script>(function(){var t=document.querySelector('.track'),b=document.querySelectorAll('.arrows button');if(!t||!b.length)return;"
          "b[0].onclick=function(){t.scrollBy({left:-392,behavior:'smooth'})};b[1].onclick=function(){t.scrollBy({left:392,behavior:'smooth'})};})();</script>")
    return head("KOSAI — 시안 C · 쇼케이스") + gnav() + f"<main>{hero}{band}{gal}{car}</main>" + footer() + js + "</body></html>"


def stock(tk="005930"):
    r = report(tk)
    s = BY[tk]
    v = valuation(tk)
    q = r["quant"]["quarterly"]
    ann = r["quant"]["annual"]
    c = s["change"]
    labels = [q_label(x["q"]) for x in q]
    revs = [x["rev"] for x in q]
    ops = [x["op"] for x in q]
    opm = [x["op"] / x["rev"] * 100 for x in q]
    lnav = ('<nav class="lnav"><div class="lnav-in"><h2>' + esc(s["name"]) + '</h2>'
            + "".join(f'<a href="#{i}">{n}</a>' for i, n in [("k", "요점"), ("e", "실적"), ("o", "전망"), ("bb", "강세와 약세"), ("v", "결론")])
            + '<a class="btn sm" href="#">관심종목 추가</a></div></nav>')
    hero = (f'<section class="s-hero"><div class="wrap"><p class="eyebrow">{esc(s["sector"])} · {esc(s["market"])} {tk}</p><h1 class="s-name">{esc(s["name"])}</h1>'
            f'<p class="s-th">{esc(r["title"]["ko"])}</p>'
            f'<p class="s-px"><span class="tnum">{grp(s["price"])}원</span><span class="tnum {cls(c)}">{arrow(c)} {abs(c):.2f}%</span><small>{kdate(PRICE_DATE)} 종가</small></p>'
            f'<div class="s-ctas"><a class="btn" href="#">관심종목에 추가</a><a class="more" href="#e">실적 보기</a></div>'
            f'<div class="hl"><div><b class="tnum">{money(revs[-1])}</b><span>분기 매출, <em>사상 최대</em><br>{q[-1]["q"][:4]}년 {q[-1]["q"][-1]}분기</span></div>'
            f'<div><b class="tnum">{opm[-1]:.1f}%</b><span>영업이익률<br>다섯 분기 전 <em>{opm[0]:.1f}%</em></span></div>'
            f'<div><b class="tnum">{v["per"]:.1f}배</b><span>PER<br>현재가 · 최근 네 분기</span></div>'
            f'<div><b class="tnum">{v["roe"]:.1f}%</b><span>ROE<br>시가총액 {jo(s["mcap"])}</span></div></div></div></section>')
    kp = "".join(f"<li><span>{esc(k['ko'])}</span></li>" for k in r["keypoints"])
    keys = (f'<section class="sec" id="k"><div class="wrap"><h2 class="t">다섯 문장으로.</h2><p class="s">{esc(r["lead"]["ko"])}</p>'
            f'<ol class="kp5">{kp}</ol></div></section>')
    charts = (f'<section class="sec alt" id="e"><div class="wide"><h2 class="t">이익률, 다섯 분기 만에<br>{opm[0]:.0f}%에서 {opm[-1]:.0f}%로.</h2>'
              f'<p class="s">다섯 분기 동안 매출은 {revs[-1] / revs[0]:.1f}배, 영업이익은 {ops[-1] / ops[0]:.0f}배가 됐습니다. 연결 기준, DART 확정치.</p>'
              f'<div class="charts"><div class="cht"><h3>분기 매출</h3><p class="v tnum">{money(revs[-1])}<small>{q[-1]["q"][:4]}년 {q[-1]["q"][-1]}분기</small></p>{light_bars(revs, labels)}</div>'
              f'<div class="cht"><h3>분기 영업이익</h3><p class="v tnum">{money(ops[-1])}<small>이익률 {opm[-1]:.1f}%</small></p>{light_bars(ops, labels, color="#bf4800")}</div></div></div></section>')
    art = ""
    for i, (sid, name, key) in enumerate([("b", "사업 구조", "business"), ("ea", "실적", "earnings"), ("in", "산업", "industry"),
                                          ("o", "전망", "outlook"), ("va", "밸류에이션", "valuation_comment")]):
        ps = chunk(r[key]["ko"], 170)
        digits = sum(ch.isdigit() for ch in ps[0]) / max(1, len(ps[0]))
        inner = (f'<p class="intro">{esc(ps[0])}</p>' if digits < 0.06 else f"<p>{esc(ps[0])}</p>") + "".join(f"<p>{esc(p)}</p>" for p in ps[1:])
        if key == "earnings":
            arows = "".join(f'<tr><td>{a["year"]}</td><td>{money(a["rev"])}</td><td>{money(a["op"])}</td><td>{money(a["np_owner"])}</td>'
                            f'<td>{a["opm"]:.1f}%</td><td>{a["roe"]:.1f}%</td></tr>' for a in ann)
            inner += (f'<table class="tbl"><caption>연간 실적 · 연결 · 순이익은 지배주주</caption><thead><tr><th>연도</th><th>매출</th><th>영업이익</th><th>순이익</th>'
                      f'<th>영업이익률</th><th>ROE</th></tr></thead><tbody>{arows}</tbody></table>')
        art += f'<section id="{sid}"><p class="no">{i + 1:02d}</p><h2>{esc(name)}</h2>{inner}</section>'
    body = f'<section class="sec" style="padding-top:0"><div class="wrap"><article class="art">{art}</article></div></section>'
    bull = "".join(f'<div class="it"><h4>{esc(x["title"]["ko"])}</h4><p>{esc(chunk(x["body"]["ko"], 200)[0])}</p></div>' for x in r["bull"])
    bear = "".join(f'<div class="it"><h4>{esc(x["title"]["ko"])}</h4><p>{esc(chunk(x["body"]["ko"], 200)[0])}</p></div>' for x in r["bear"])
    bb = (f'<section class="sec alt" id="bb"><div class="wide"><h2 class="t">좋은 이유, 걱정할 이유.</h2><p class="s">같은 시점에 함께 있는 강세 요인과 약세 요인.</p>'
          f'<div class="bb"><div class="bbt bull"><p class="ey">강세 요인 {len(r["bull"])}</p><h3>좋아지는 것.</h3>{bull}</div>'
          f'<div class="bbt bear"><p class="ey">약세 요인 {len(r["bear"])}</p><h3>걱정할 것.</h3>{bear}</div></div>'
          f'<div class="rk">' + "".join(f'<div><b>{esc(x["cat"]["ko"])}</b><p>{esc(chunk(x["body"]["ko"], 180)[0])}</p></div>' for x in r["risks"]) + '</div></div></section>')
    cps = "".join(f'<div><b>{esc(x["when"]["ko"])}</b><p>{esc(x["what"]["ko"])}</p></div>' for x in r["checkpoints"])
    vp = chunk(r["verdict"]["body"]["ko"], 170)
    first = vp[0].split(". ")[0].rstrip(".") + "."
    rest = [vp[0][len(first):].strip()] + vp[1:]
    srcs = "".join(f"<span>{esc(u.split('//')[-1].split('/')[0].replace('www.', ''))}</span>" for u in (r.get("sources") or []))
    tail = (f'<section class="sec"><div class="wrap"><h2 class="t">다음에 확인할 것.</h2><div class="cps">{cps}</div></div></section>'
            f'<section class="sec" id="v"><div class="wrap"><p class="eyebrow" style="text-align:center">종합 의견</p><p class="quote">{esc(first)}</p>'
            f'<div class="vrest">' + "".join(f"<p>{esc(p)}</p>" for p in rest if p) + '</div>'
            f'<div class="srcs">{srcs}</div><p class="disc">이 리포트는 AI가 공시·재무 데이터와 보도를 분석해 작성한 정보이며 투자 권유가 아닙니다. '
            f'{kdate_full(r["reportDate"])[:-4]} 발행 · 재무 {kdate(r["quant"]["asOf"], False)} 기준</p></div></section>')
    return (head(f"{s['name']} — {r['title']['ko']} · KOSAI 시안 C") + gnav() + lnav
            + f"<main>{hero}{keys}{charts}{body}{bb}{tail}</main><div style='height:120px'></div>" + footer() + "</body></html>")
