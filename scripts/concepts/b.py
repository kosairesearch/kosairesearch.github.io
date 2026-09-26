"""시안 B — 다크 시네마틱. 깊은 검정 위 새벽빛 하나(매일 07:00 발행), 실제 데이터로 그린 제품 화면."""
from data import (BY, esc, sign, arrow, cls, won, money, jo, kdate, kdate_full, grp, latest, sectors, movers,
                  valuation, report, brief, PRICE_DATE, MINUS)
from common import chunk, paras, bars_svg, line_svg, treemap, q_label, spark

FONTS = ('<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>'
         '<link href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">')

CSS = r"""
:root{
  --bg:#07070a; --bg2:#0b0b0f; --bg3:#101015;
  --t1:#f4f3f1; --t2:rgba(244,243,241,.68); --t3:rgba(244,243,241,.52); --t4:rgba(244,243,241,.34);
  --line:rgba(255,255,255,.08); --line2:rgba(255,255,255,.14);
  --up:#ff5d63; --down:#5e9dff; --dawn:#ff9a57; --dawn2:#ffcfa6;
  --sans:'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo',sans-serif;
  --w:1200px; --pad:40px; --ease:cubic-bezier(.2,.8,.2,1);
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:120px;background:var(--bg);overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--t1);font:400 16px/1.7 var(--sans);letter-spacing:-.01em;-webkit-font-smoothing:antialiased;
  -moz-osx-font-smoothing:grayscale;word-break:keep-all;overflow-wrap:anywhere;overflow-x:clip}
a{color:inherit;text-decoration:none}
h1,h2,h3,h4,p{margin:0}
.wrap{max-width:var(--w);margin:0 auto;padding:0 var(--pad)}
.tnum{font-variant-numeric:tabular-nums} .nw{white-space:nowrap}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--t3)}

/* 머리 */
.hdr{position:fixed;inset:0 0 auto;z-index:40;height:64px;background:rgba(7,7,10,.55);backdrop-filter:saturate(1.6) blur(18px);-webkit-backdrop-filter:saturate(1.6) blur(18px);
  border-bottom:1px solid var(--line)}
.hdr-in{display:flex;align-items:center;height:64px;gap:28px}
.logo{font:650 16px/1 var(--sans);letter-spacing:.34em;margin-right:-.34em;color:var(--t1)}
.nav{display:flex;gap:26px;margin-left:34px;font:500 14px/1 var(--sans)}
.nav a{color:var(--t2);transition:color .2s} .nav a:hover,.nav a.on{color:var(--t1)}
.hdr .sp{flex:1}
.kbar{display:flex;align-items:center;gap:10px;height:36px;padding:0 10px 0 12px;border-radius:10px;border:1px solid var(--line2);background:rgba(255,255,255,.04);
  color:var(--t3);font:500 13.5px/1 var(--sans);min-width:220px;transition:border-color .2s,background .2s}
.kbar:hover{border-color:rgba(255,255,255,.24);background:rgba(255,255,255,.06)}
.kbar svg{width:15px;height:15px}
kbd{margin-left:auto;font:500 11.5px/1 var(--sans);color:var(--t3);border:1px solid var(--line2);border-radius:6px;padding:4px 6px;background:rgba(255,255,255,.03)}
.login{font:500 14px/1 var(--sans);color:var(--t2)} .login:hover{color:var(--t1)}
.pill{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:38px;padding:0 18px;border-radius:999px;background:var(--t1);color:#0a0a0c;
  font:650 14px/1 var(--sans);letter-spacing:-.01em;transition:transform .2s var(--ease),box-shadow .2s}
.pill:hover{transform:translateY(-1px);box-shadow:0 8px 30px rgba(255,170,110,.25)}
.pill.ghost{background:rgba(255,255,255,.06);color:var(--t1);border:1px solid var(--line2)}
.pill.ghost:hover{box-shadow:none;background:rgba(255,255,255,.1)}

/* 첫 장면 */
.hero{position:relative;padding:176px 0 0;text-align:center;isolation:isolate}
.hero::before{content:"";position:absolute;z-index:-1;left:50%;top:-420px;width:1500px;height:1100px;transform:translateX(-50%);
  background:radial-gradient(closest-side,rgba(255,146,76,.34),rgba(255,120,60,.12) 42%,rgba(255,120,60,0) 72%);filter:blur(10px)}
.hero::after{content:"";position:absolute;z-index:-1;left:50%;top:-120px;width:760px;height:420px;transform:translateX(-50%);
  background:radial-gradient(closest-side,rgba(255,214,176,.20),rgba(255,214,176,0) 70%)}
.grain{position:absolute;inset:0;z-index:-1;opacity:.06;background:url(../a/grain.png);mix-blend-mode:overlay;pointer-events:none}
.badge{display:inline-flex;align-items:center;gap:10px;height:34px;padding:0 14px 0 12px;border-radius:999px;border:1px solid rgba(255,190,140,.22);
  background:rgba(255,160,100,.07);font:500 13.5px/1 var(--sans);color:var(--t2);transition:border-color .2s}
.badge:hover{border-color:rgba(255,190,140,.45)}
.badge i{width:7px;height:7px;border-radius:50%;background:var(--dawn);box-shadow:0 0 0 4px rgba(255,154,87,.18),0 0 12px var(--dawn)}
.badge b{color:var(--t1);font-weight:600}
.h-title{margin:30px auto 0;max-width:980px;font:640 76px/1.06 var(--sans);letter-spacing:-.045em;text-wrap:balance;
  background:linear-gradient(180deg,#fff 0%,#fff 46%,#ffe3cc 78%,#ffc79c 100%);-webkit-background-clip:text;background-clip:text;color:transparent}
.h-sub{margin:26px auto 0;max-width:600px;font:400 19px/1.65 var(--sans);color:var(--t2);letter-spacing:-.015em}
.search{margin:40px auto 0;max-width:580px;display:flex;align-items:center;gap:12px;height:58px;padding:0 12px 0 20px;border-radius:16px;
  border:1px solid var(--line2);background:linear-gradient(180deg,rgba(255,255,255,.07),rgba(255,255,255,.03));
  box-shadow:0 1px 0 rgba(255,255,255,.06) inset,0 20px 60px rgba(0,0,0,.4);color:var(--t3);font:500 16px/1 var(--sans);text-align:left}
.search svg{width:19px;height:19px;flex:none}
.search span{flex:1}
.h-meta{margin-top:22px;display:flex;justify-content:center;gap:22px;font:500 13.5px/1 var(--sans);color:var(--t3)}
.h-meta b{color:var(--t1);font-weight:600;margin-right:5px}

/* 제품 창 */
.stage{position:relative;margin:78px auto 0;max-width:1180px;perspective:2400px}
.stage::before{content:"";position:absolute;left:8%;right:8%;top:-40px;height:160px;background:radial-gradient(closest-side,rgba(255,150,90,.22),transparent);filter:blur(30px);z-index:-1}
.win{border-radius:18px;border:1px solid rgba(255,255,255,.12);background:linear-gradient(180deg,#101016,#0a0a0e);overflow:hidden;
  box-shadow:0 0 0 1px rgba(0,0,0,.6),0 50px 120px -20px rgba(0,0,0,.8),0 1px 0 rgba(255,255,255,.1) inset;transform:rotateX(9deg);transform-origin:50% 0;text-align:left}
.win-bar{height:40px;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid var(--line);background:rgba(255,255,255,.02)}
.win-bar i{width:11px;height:11px;border-radius:50%;background:rgba(255,255,255,.14)}
.win-bar span{margin-left:auto;margin-right:auto;font:500 12px/1 var(--sans);color:var(--t3);padding-right:40px}
.win-body{display:grid;grid-template-columns:230px minmax(0,1fr) 290px;min-height:560px}
.pane{padding:18px}
.pane+.pane{border-left:1px solid var(--line)}
.p-h{font:600 11.5px/1 var(--sans);letter-spacing:.06em;color:var(--t3);text-transform:uppercase;margin:4px 4px 12px}
.wl a{display:grid;grid-template-columns:1fr auto;gap:2px 8px;padding:10px 10px;border-radius:10px;font:500 13px/1.3 var(--sans)}
.wl a.on{background:rgba(255,255,255,.06);box-shadow:0 0 0 1px rgba(255,255,255,.06) inset}
.wl .n{color:var(--t1);font-weight:600} .wl .p{text-align:right;color:var(--t2)} .wl .t{color:var(--t3);font-size:11.5px} .wl .c{text-align:right;font-size:12px}
.m-top{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.m-name{font:650 22px/1.2 var(--sans);letter-spacing:-.02em} .m-tk{font:500 13px/1 var(--sans);color:var(--t3)}
.m-px{display:flex;align-items:baseline;gap:12px;margin-top:10px}
.m-px b{font:300 46px/1 var(--sans);letter-spacing:-.03em} .m-px small{font:500 14px/1 var(--sans);color:var(--t2)}
.chip{display:inline-flex;align-items:center;height:24px;padding:0 9px;border-radius:7px;font:600 12.5px/1 var(--sans)}
.chip.up{background:rgba(255,93,99,.14)} .chip.down{background:rgba(94,157,255,.14)} .chip.flat{background:rgba(255,255,255,.07)}
.m-thesis{margin-top:18px;font:600 19px/1.45 var(--sans);letter-spacing:-.025em;color:var(--t1)}
.m-lead{margin-top:8px;font:400 13.5px/1.7 var(--sans);color:var(--t2)}
.m-chart{margin-top:18px;border:1px solid var(--line);border-radius:12px;padding:14px 14px 6px;background:rgba(255,255,255,.02)}
.m-chart h5{margin:0 0 4px;font:600 12px/1 var(--sans);color:var(--t3);display:flex;justify-content:space-between}
.m-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:14px}
.m-stats div{border:1px solid var(--line);border-radius:10px;padding:10px 12px;background:rgba(255,255,255,.02)}
.m-stats dt{font:500 11.5px/1 var(--sans);color:var(--t3)} .m-stats dd{margin:7px 0 0;font:500 15px/1 var(--sans)}
.bf h4{font:600 15px/1.45 var(--sans);letter-spacing:-.02em;margin:0 0 10px}
.bf ul{margin:0;padding:0;list-style:none}
.bf li{position:relative;padding:0 0 10px 14px;font:400 12.5px/1.65 var(--sans);color:var(--t2)}
.bf li::before{content:"";position:absolute;left:0;top:.72em;width:5px;height:5px;border-radius:50%;background:var(--dawn)}
.mini{width:100%;border-collapse:collapse;margin-top:14px}
.mini td{padding:8px 0;border-top:1px solid var(--line);font:500 12.5px/1 var(--sans)}
.mini td+td{text-align:right}
.fade{position:absolute;left:0;right:0;bottom:-2px;height:220px;background:linear-gradient(180deg,rgba(7,7,10,0),var(--bg) 85%);pointer-events:none}

/* 절 */
.sec{padding:120px 0 0;position:relative}
.eyebrow{font:600 13px/1 var(--sans);letter-spacing:.02em;color:var(--dawn)}
.s-title{margin-top:14px;font:640 44px/1.15 var(--sans);letter-spacing:-.04em;text-wrap:balance}
.s-title .dim{color:var(--t3)}
.s-sub{margin-top:14px;font:400 17px/1.7 var(--sans);color:var(--t2);max-width:640px}
.s-head{display:flex;align-items:flex-end;justify-content:space-between;gap:30px;margin-bottom:40px}
.link{font:600 14px/1 var(--sans);color:var(--t2);display:inline-flex;gap:6px;align-items:center;white-space:nowrap;transition:color .2s}
.link:hover{color:var(--t1)}

.tiles{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--line);border:1px solid var(--line);border-radius:18px;overflow:hidden}
.tile{background:var(--bg);padding:22px 22px 20px;transition:background .3s}
.tile:hover{background:#0c0c11}
.tile dt{font:500 13px/1 var(--sans);color:var(--t3);display:flex;justify-content:space-between}
.tile dd{margin:14px 0 0;font:300 30px/1 var(--sans);letter-spacing:-.03em}
.tile .c{display:block;margin-top:10px;font:600 13px/1 var(--sans)}
.note{margin-top:14px;font:400 13px/1.6 var(--sans);color:var(--t3)}

.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.card{position:relative;display:flex;flex-direction:column;min-height:250px;padding:24px;border-radius:18px;border:1px solid var(--line);
  background:linear-gradient(180deg,rgba(255,255,255,.035),rgba(255,255,255,.012));overflow:hidden;transition:border-color .3s,transform .3s var(--ease)}
.card::before{content:"";position:absolute;inset:0;background:radial-gradient(420px circle at var(--mx,50%) var(--my,-20%),rgba(255,170,110,.12),transparent 45%);
  opacity:0;transition:opacity .3s}
.card:hover{border-color:rgba(255,255,255,.16);transform:translateY(-2px)} .card:hover::before{opacity:1}
.card .k{display:flex;gap:8px;align-items:center;font:500 12.5px/1 var(--sans);color:var(--t3)}
.card .k b{color:var(--t1);font-weight:600;font-size:14px}
.card h3{margin:16px 0 0;font:620 21px/1.42 var(--sans);letter-spacing:-.03em;text-wrap:balance}
.card .sp{margin-left:auto} .card .cfoot{margin-top:auto;padding-top:22px;display:flex;align-items:center;gap:10px;font:500 13px/1 var(--sans);color:var(--t3)}
.card .cfoot b{color:var(--t1);font-weight:500;font-size:14.5px}
.card .cfoot .d{margin-left:auto}

.tmap{position:relative;width:100%;aspect-ratio:1000/500;border-radius:18px;overflow:hidden;border:1px solid var(--line)}
.tm-m{display:none;aspect-ratio:1000/1450}
.tl{position:absolute;box-shadow:inset 0 0 0 1px var(--bg);padding:12px 14px;overflow:hidden;transition:filter .2s}
.tl:hover{filter:brightness(1.25)}
.tl .tn{display:block;font:600 13.5px/1.25 var(--sans)} .tl .tc{display:block;margin-top:4px;font:500 13px/1 var(--sans);color:var(--t2)}
.tl.l3{padding:26px 28px} .tl.l3 .tn{font:640 34px/1.1 var(--sans);letter-spacing:-.035em} .tl.l3 .tc{font:300 30px/1 var(--sans);margin-top:10px;color:var(--t1)}
.tl.l3 .ts{display:block;margin-top:18px;max-width:380px;font:400 14px/1.7 var(--sans);color:var(--t2)}
.tl .ts{display:none} .tl.l1 .tc,.tl.l0 .tn,.tl.l0 .tc{display:none} .tl.l1{padding:8px 9px} .tl.l1 .tn{font-size:12px} .tl.l0{padding:0}
.legend{display:flex;justify-content:space-between;margin-top:14px;font:400 13px/1.6 var(--sans);color:var(--t3)}
.legend span{display:flex;gap:6px;align-items:center} .legend i{width:24px;height:8px;border-radius:2px;display:inline-block}

.rhythm{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;position:relative}
.rh{padding:28px 26px;border-radius:18px;border:1px solid var(--line);background:rgba(255,255,255,.02)}
.rh time{display:block;font:300 40px/1 var(--sans);letter-spacing:-.04em;color:var(--t1)}
.rh time span{font:500 13px/1 var(--sans);color:var(--dawn);letter-spacing:0;margin-left:8px;vertical-align:middle}
.rh h3{margin-top:24px;font:620 19px/1.4 var(--sans);letter-spacing:-.025em}
.rh p{margin-top:8px;font:400 14.5px/1.7 var(--sans);color:var(--t2)}

.cta{margin:140px 0 0;padding:90px 40px;border-radius:28px;text-align:center;position:relative;overflow:hidden;border:1px solid var(--line);
  background:radial-gradient(900px 380px at 50% 120%,rgba(255,140,70,.25),transparent 70%),linear-gradient(180deg,#0d0d12,#09090c)}
.cta h2{font:640 52px/1.12 var(--sans);letter-spacing:-.045em}
.cta p{margin:18px auto 0;max-width:520px;font:400 17px/1.7 var(--sans);color:var(--t2)}
.cta .btns{margin-top:32px;display:flex;justify-content:center;gap:12px}
.cta .pill{height:46px;padding:0 24px;font-size:15px}
.plans{margin-top:40px;display:flex;justify-content:center;gap:40px;font:500 14px/1.4 var(--sans);color:var(--t3)}
.plans b{display:block;font:300 28px/1 var(--sans);color:var(--t1);letter-spacing:-.03em;margin-bottom:8px}

.site-foot{border-top:1px solid var(--line);margin-top:120px;padding:48px 0 60px;font:400 13px/1.8 var(--sans);color:var(--t3)}
.f-top{display:flex;justify-content:space-between;gap:40px;margin-bottom:36px}
.f-cols{display:flex;gap:56px}
.f-cols div{display:flex;flex-direction:column;gap:4px}
.f-cols b{color:var(--t2);font-weight:600;margin-bottom:6px}
.f-cols a:hover{color:var(--t1)}
.f-fine{display:flex;flex-wrap:wrap;gap:4px 18px}

/* 종목 */
.s-hero{position:relative;padding:136px 0 0;isolation:isolate}
.s-hero::before{content:"";position:absolute;z-index:-1;left:30%;top:-420px;width:1300px;height:900px;transform:translateX(-50%);
  background:radial-gradient(closest-side,rgba(255,146,76,.22),rgba(255,120,60,.06) 50%,transparent 75%)}
.crumbs{display:flex;gap:8px;flex-wrap:wrap}
.crumbs span{display:inline-flex;align-items:center;height:28px;padding:0 11px;border-radius:999px;border:1px solid var(--line2);font:500 12.5px/1 var(--sans);color:var(--t2)}
.sh-grid{display:grid;grid-template-columns:minmax(0,1fr) 470px;gap:56px;align-items:end;margin-top:22px}
.sh-name{font:650 56px/1.08 var(--sans);letter-spacing:-.045em}
.sh-en{margin-top:10px;font:500 14px/1 var(--sans);color:var(--t3);letter-spacing:.02em}
.sh-px{display:flex;align-items:baseline;flex-wrap:wrap;gap:14px;margin-top:30px}
.sh-px b{font:250 76px/1 var(--sans);letter-spacing:-.045em}
.sh-px .won{font:500 20px/1 var(--sans);color:var(--t2);margin-left:-6px}
.sh-px .chip{height:30px;font-size:14px;padding:0 11px;border-radius:9px;align-self:center}
.sh-px small{font:500 13.5px/1 var(--sans);color:var(--t3);align-self:center}
.sh-btns{display:flex;gap:10px;margin-top:30px}
.panel{border:1px solid var(--line);border-radius:20px;background:linear-gradient(180deg,rgba(255,255,255,.045),rgba(255,255,255,.015));padding:22px 22px 12px;
  box-shadow:0 1px 0 rgba(255,255,255,.05) inset,0 30px 80px -30px rgba(0,0,0,.6)}
.panel h3{display:flex;justify-content:space-between;align-items:baseline;font:600 13px/1 var(--sans);color:var(--t3);margin-bottom:6px}
.panel h3 b{font:300 26px/1 var(--sans);color:var(--t1);letter-spacing:-.03em}
.panel .cap{font:400 12.5px/1.6 var(--sans);color:var(--t3);border-top:1px solid var(--line);margin-top:6px;padding-top:10px}
.thesis{margin-top:64px;padding-top:40px;border-top:1px solid var(--line);display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:56px}
.thesis h2{font:640 40px/1.22 var(--sans);letter-spacing:-.04em;text-wrap:balance;
  background:linear-gradient(180deg,#fff 40%,var(--dawn2));-webkit-background-clip:text;background-clip:text;color:transparent}
.thesis p{margin-top:18px;font:400 18px/1.75 var(--sans);color:var(--t2)}
.stat{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:16px;overflow:hidden;align-self:start}
.stat div{background:var(--bg);padding:16px 18px}
.stat dt{font:500 12.5px/1 var(--sans);color:var(--t3)} .stat dd{margin:9px 0 0;font:400 20px/1 var(--sans);letter-spacing:-.02em}
.tabs{position:sticky;top:76px;z-index:30;margin:64px auto 0;display:flex;gap:4px;padding:5px;border-radius:14px;border:1px solid var(--line2);width:max-content;max-width:100%;
  background:rgba(12,12,16,.72);backdrop-filter:blur(16px) saturate(1.5);-webkit-backdrop-filter:blur(16px) saturate(1.5);overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tabs a{flex:none;height:34px;display:flex;align-items:center;padding:0 13px;border-radius:10px;font:500 13.5px/1 var(--sans);color:var(--t2);transition:background .2s,color .2s}
.tabs a:hover{color:var(--t1)} .tabs a.on{background:rgba(255,255,255,.1);color:var(--t1)}
.read{max-width:760px;margin:0 auto}
.read section{padding-top:88px}
.read .no{font:600 13px/1 var(--sans);color:var(--dawn);letter-spacing:.02em}
.read h2{margin-top:12px;font:640 34px/1.25 var(--sans);letter-spacing:-.04em}
.read p{margin-top:20px;font:400 17.5px/1.85 var(--sans);color:rgba(244,243,241,.84)}
.read .lede{font:500 20px/1.75 var(--sans);color:var(--t1);letter-spacing:-.02em}
.keys{list-style:none;margin:26px 0 0;padding:0;counter-reset:k;display:grid;gap:10px}
.keys li{counter-increment:k;display:grid;grid-template-columns:44px 1fr;gap:6px;padding:18px 20px;border-radius:14px;border:1px solid var(--line);background:rgba(255,255,255,.02);
  font:400 16px/1.7 var(--sans);color:rgba(244,243,241,.88)}
.keys li::before{content:counter(k,decimal-leading-zero);font:300 22px/1.2 var(--sans);color:var(--dawn);letter-spacing:-.02em}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:28px}
.tbl{width:100%;border-collapse:collapse;margin-top:28px;font:500 14px/1 var(--sans)}
.tbl caption{text-align:left;font:600 13px/1 var(--sans);color:var(--t3);padding-bottom:12px}
.tbl th{font:500 12.5px/1 var(--sans);color:var(--t3);text-align:right;padding:11px 0 11px 12px;border-bottom:1px solid var(--line2)}
.tbl td{text-align:right;padding:13px 0 13px 12px;border-bottom:1px solid var(--line);font-variant-numeric:tabular-nums;color:rgba(244,243,241,.9)}
.tbl th:first-child,.tbl td:first-child{text-align:left;padding-left:0}
.tbl tr:last-child td{color:var(--t1);font-weight:600}
.bb{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:28px}
.bbp{border-radius:18px;border:1px solid var(--line);padding:22px;background:rgba(255,255,255,.02);position:relative;overflow:hidden}
.bbp::before{content:"";position:absolute;left:0;right:0;top:0;height:1px}
.bbp.bull::before{background:linear-gradient(90deg,transparent,var(--up),transparent)} .bbp.bear::before{background:linear-gradient(90deg,transparent,var(--down),transparent)}
.bbp h3{display:flex;align-items:center;gap:8px;font:600 13px/1 var(--sans);color:var(--t2);margin-bottom:18px}
.bbp h3 i{width:7px;height:7px;border-radius:50%}
.bbp h4{font:620 17px/1.45 var(--sans);letter-spacing:-.025em;margin:0}
.bbp p{margin-top:8px !important;font-size:14.5px !important;line-height:1.75 !important;color:var(--t2) !important}
.bbp .it{padding-bottom:18px;margin-bottom:18px;border-bottom:1px solid var(--line)} .bbp .it:last-child{border:0;margin:0;padding:0}
.risk{margin-top:12px;padding:20px 22px;border-radius:16px;border:1px solid var(--line);background:rgba(255,255,255,.02)}
.risk .chip{background:rgba(255,154,87,.12);color:var(--dawn2)}
.risk p{margin-top:12px !important;font-size:15.5px !important;color:var(--t2) !important}
.tl2{position:relative;margin-top:28px;padding-left:28px}
.tl2::before{content:"";position:absolute;left:5px;top:8px;bottom:8px;width:1px;background:linear-gradient(var(--dawn),rgba(255,154,87,.05))}
.tl2 .cp{position:relative;padding-bottom:26px}
.tl2 .cp::before{content:"";position:absolute;left:-28px;top:7px;width:11px;height:11px;border-radius:50%;background:var(--bg);border:2px solid var(--dawn)}
.tl2 b{font:600 14px/1.4 var(--sans);color:var(--dawn2)}
.tl2 p{margin-top:6px !important;font-size:15.5px !important;color:var(--t2) !important}
.verdict{margin-top:28px;padding:30px 30px 26px;border-radius:22px;position:relative;background:linear-gradient(180deg,rgba(255,154,87,.08),rgba(255,255,255,.02));
  border:1px solid rgba(255,180,130,.22)}
.verdict p:first-child{margin-top:0;font:500 19px/1.8 var(--sans);color:var(--t1);letter-spacing:-.02em}
.srcs{margin-top:22px;padding:0;list-style:none;display:flex;flex-wrap:wrap;gap:8px}
.srcs li{font:500 12.5px/1 var(--sans);color:var(--t3);border:1px solid var(--line);border-radius:999px;padding:8px 11px}
.disc{margin-top:26px;font:400 13px/1.7 var(--sans);color:var(--t3)}

@media (prefers-reduced-motion:no-preference){
  .rise{animation:rise .9s var(--ease) both} .rise.d1{animation-delay:.08s} .rise.d2{animation-delay:.16s} .rise.d3{animation-delay:.24s} .rise.d4{animation-delay:.34s}
  @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
}
@media (max-width:1100px){
  :root{--pad:28px}
  .nav{display:none} .kbar{min-width:0}
  .win-body{grid-template-columns:minmax(0,1fr) 270px} .win-body .pane:first-child{display:none}
  .tiles{grid-template-columns:repeat(2,1fr)} .cards{grid-template-columns:repeat(2,1fr)}
  .sh-grid,.thesis{grid-template-columns:1fr}
}
@media (max-width:720px){
  :root{--pad:20px}
  .kbar span,.kbar kbd,.login{display:none} .kbar{min-width:0;width:38px;padding:0;justify-content:center}
  .hero{padding-top:124px}
  .h-title{font-size:42px;line-height:1.12}
  .h-sub{font-size:16.5px}
  .search{height:52px;font-size:15px} .search kbd{display:none}
  .h-meta{flex-wrap:wrap;gap:10px 16px}
  .stage{margin-top:48px}
  .win{transform:none;border-radius:14px}
  .win-body{grid-template-columns:1fr;min-height:0} .win-body .pane:last-child{display:none}
  .m-px b{font-size:38px}
  .m-stats{grid-template-columns:1fr 1fr}
  .fade{height:120px}
  .sec{padding-top:88px}
  .s-title{font-size:32px} .s-head{flex-direction:column;align-items:flex-start;gap:16px}
  .tiles{grid-template-columns:1fr 1fr} .tile{padding:18px} .tile dd{font-size:24px}
  .cards{grid-template-columns:1fr} .card{min-height:0}
  .tm-d{display:none} .tm-m{display:block}
  .tl.l3{padding:16px} .tl.l3 .tn{font-size:24px} .tl.l3 .tc{font-size:22px} .tl.l3 .ts{display:none}
  .tl.l2{padding:8px 9px} .tl.l2 .tn{font-size:12.5px} .tl.l1{padding:6px 7px} .tl.l1 .tn{font-size:11.5px}
  .legend{flex-direction:column;gap:8px}
  .rhythm{grid-template-columns:1fr}
  .cta{padding:60px 22px;border-radius:22px} .cta h2{font-size:34px} .plans{gap:22px}
  .f-top{flex-direction:column} .f-cols{gap:32px;flex-wrap:wrap}
  .s-hero{padding-top:100px}
  .sh-name{font-size:40px} .sh-px b{font-size:56px}
  .thesis{margin-top:44px} .thesis h2{font-size:28px} .thesis p{font-size:16.5px}
  .tabs{top:72px;margin-top:44px;width:100%}
  .read h2{font-size:27px} .read p{font-size:16.5px} .read .lede{font-size:18px}
  .charts,.bb{grid-template-columns:1fr}
}
"""

SEARCH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'


def head(title):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#07070a"><meta name="color-scheme" content="dark">'
            f'<title>{esc(title)}</title>{FONTS}<link rel="stylesheet" href="b.css"></head><body>')


def header(active=""):
    nav = "".join(f'<a href="{h}"{" class=on" if n == active else ""}>{n}</a>' for n, h in
                  [("리포트", "#"), ("업종", "#"), ("모닝브리핑", "#"), ("관심종목", "#"), ("멤버십", "#")])
    return (f'<header class="hdr"><div class="wrap hdr-in"><a class="logo" href="index.html">KOSAI</a><nav class="nav">{nav}</nav><span class="sp"></span>'
            f'<a class="kbar" href="#">{SEARCH_SVG}<span>종목 찾기</span><kbd>⌘K</kbd></a><a class="login" href="#">로그인</a>'
            f'<a class="pill" href="#">무료로 시작</a></div></header>')


def footer():
    return ('<footer class="site-foot"><div class="wrap"><div class="f-top"><a class="logo" href="index.html">KOSAI</a>'
            '<div class="f-cols"><div><b>읽기</b><a href="#">리포트</a><a href="#">업종</a><a href="#">모닝브리핑</a></div>'
            '<div><b>회사</b><a href="#">소개</a><a href="#">멤버십</a><a href="#">문의</a></div>'
            '<div><b>정책</b><a href="#">이용약관</a><a href="#">개인정보처리방침</a></div></div></div>'
            '<div class="f-fine"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span>'
            '<span>서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>hello@kosai.kr</span></div>'
            '<p style="margin-top:14px">KOSAI의 리포트는 AI가 공시·재무 데이터와 보도를 분석한 정보이며 투자 권유가 아닙니다. © 2026 KOSAI</p></div></footer>')


SPOT_JS = ("<script>document.querySelectorAll('.card').forEach(function(c){c.addEventListener('pointermove',function(e){var r=c.getBoundingClientRect();"
           "c.style.setProperty('--mx',(e.clientX-r.left)+'px');c.style.setProperty('--my',(e.clientY-r.top)+'px')})});</script>")


def tint(chg):
    a = min(abs(chg) / 3.0, 1.0)
    if chg > 0.05:
        return f"rgba(255,93,99,{0.07 + a * 0.30:.3f})"
    if chg < -0.05:
        return f"rgba(94,157,255,{0.07 + a * 0.30:.3f})"
    return "rgba(255,255,255,.05)"


def chg_chip(c):
    return f'<span class="chip {cls(c)}">{arrow(c)} {abs(c):.2f}%</span>' if c else '<span class="chip flat">0.00%</span>'


def product_window(b):
    f = b["_facts"]
    r = report("005930")
    s = BY["005930"]
    v = valuation("005930")
    wl = ["005930", "000660", "373220", "005380", "068270", "035420", "207940"]
    rows = ""
    for i, tk in enumerate(wl):
        x = BY[tk]
        rows += (f'<a class="{"on" if i == 0 else ""}" href="stock.html"><span class="n">{esc(x["name"])}</span><span class="p tnum">{grp(x["price"])}</span>'
                 f'<span class="t">{esc(x["sector"])}</span><span class="c tnum {cls(x["change"])}">{sign(x["change"])}</span></a>')
    q = r["quant"]["quarterly"]
    ops = [x["op"] for x in q]
    ch = bars_svg(ops, [q_label(x["q"]) for x in q], w=520, h=150, fill="rgba(255,255,255,.16)", highlight_last=True, fill_last="url(#g1)",
                  grad=None, font="inherit", fsize=12, tsize=11, weight=500, label_fill="rgba(244,243,241,.8)", tick_fill="rgba(244,243,241,.45)",
                  axis="rgba(255,255,255,.14)", radius=4, top_pad=22, bottom_pad=22)
    ch = ch.replace('<svg ', '<svg ', 1).replace('role="img" style="font-family:inherit">',
                                                 'role="img" style="font-family:inherit"><defs><linearGradient id="g1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffcfa6"/><stop offset="1" stop-color="#ff8a45"/></linearGradient></defs>', 1)
    stats = [("PER", f'{v["per"]:.1f}배'), ("PBR", f'{v["pbr"]:.2f}배'), ("ROE", f'{v["roe"]:.1f}%'), ("시가총액", jo(s["mcap"]))]
    st = "".join(f"<div><dt>{k}</dt><dd class=tnum>{x}</dd></div>" for k, x in stats)
    subs = [sx["heading"]["ko"] for sx in b["sections"][:3]]
    mk = "".join(f'<tr><td>{k}</td><td class="tnum">{f[k][0]} <span class="{cls(f[k][1])}">{sign(f[k][1])}</span></td></tr>' for k in ["코스피", "코스닥", "나스닥", "WTI"])
    return (f'<div class="stage rise d4"><div class="win"><div class="win-bar"><i></i><i></i><i></i><span>kosai.kr — 삼성전자 리포트</span></div>'
            f'<div class="win-body"><div class="pane wl"><div class="p-h">관심종목</div>{rows}</div>'
            f'<div class="pane"><div class="m-top"><span class="m-name">{esc(s["name"])}</span><span class="m-tk">코스피 · {esc(s["sector"])} · 005930</span></div>'
            f'<div class="m-px"><b class="tnum">{grp(s["price"])}</b><small>원</small>{chg_chip(s["change"])}</div>'
            f'<p class="m-thesis">{esc(r["title"]["ko"])}</p><p class="m-lead">{esc(r["lead"]["ko"])}</p>'
            f'<div class="m-chart"><h5><span>분기 영업이익</span><span>{money(ops[-1])}</span></h5>{ch}</div><dl class="m-stats">{st}</dl></div>'
            f'<div class="pane bf"><div class="p-h">모닝브리핑 · {kdate(b["date"], False)} 07:28</div><h4>{esc(b["title"]["ko"])}</h4>'
            f'<ul>{"".join(f"<li>{esc(t)}</li>" for t in subs)}</ul><table class="mini">{mk}</table></div></div></div><div class="fade"></div></div>')


def home():
    b = brief()
    f = b["_facts"]
    reps = latest(6)
    secs, tot = sectors()
    hero = (f'<section class="hero"><div class="grain"></div><div class="wrap">'
            f'<a class="badge rise" href="#"><i></i><span><b>모닝브리핑 제{b["_no"]}호</b> · {kdate(b["date"])} 07:28 발행</span><span>→</span></a>'
            f'<h1 class="h-title rise d1">장이 열리기 전에,<br>모든 종목을 <span class="nw">읽어 둡니다.</span></h1>'
            f'<p class="h-sub rise d2">코스피·코스닥 2,682개 종목의 공시·실적·뉴스를 AI가 밤새 분석해 아침 7시에 한 장으로 정리합니다.</p>'
            f'<a class="search rise d3" href="#">{SEARCH_SVG}<span>종목 이름이나 코드로 찾기 — 삼성전자, 005930</span><kbd>⌘K</kbd></a>'
            f'<div class="h-meta rise d3"><span><b>2,680</b>편의 리포트</span><span><b>29</b>개 업종 분석</span><span><b>매 거래일</b>07:00 발행</span></div>'
            f'{product_window(b)}</div></section>')
    order = ["코스피", "코스닥", "나스닥", "S&P 500", "필라델피아 반도체", "미 10년물", "WTI", "달러인덱스"]
    tl = ""
    for k in order:
        val, c = f[k]
        cc = (sign(c, 2, pct=False) + "%p") if k.endswith("10년물") else sign(c)
        tl += f'<div class="tile"><dt><span>{k}</span></dt><dd class="tnum">{val}</dd><span class="c tnum {cls(c)}">{cc}</span></div>'
    market = (f'<section class="sec"><div class="wrap"><div class="s-head"><div><p class="eyebrow">오늘 아침의 숫자</p>'
              f'<h2 class="s-title">유가는 6% 내렸고,<span class="dim"> 코스피는 제자리.</span></h2></div>'
              f'<a class="link" href="#">브리핑 전문 →</a></div><dl class="tiles">{tl}</dl>'
              f'<p class="note">국내 {kdate(f["kr_date"])} · 미국 현지 {kdate(f["us_date"])} 종가 기준</p></div></section>')
    cards = ""
    for r in reps:
        sp = spark(r.get("ops") or [], w=88, h=30, fill="rgba(255,255,255,.16)", last="#ff9a57", neg="rgba(255,255,255,.16)", zero="rgba(255,255,255,.18)", radius=1.5)
        cards += (f'<a class="card" href="stock.html"><div class="k"><b>{esc(r["name"])}</b><span>{esc(r["sector"])}</span><span class="sp">{sp}</span></div>'
                  f'<h3>{esc(r["title"])}</h3><div class="cfoot"><b class="tnum">{won(r["price"])}</b>{chg_chip(r["change"])}<span class="d">{kdate(r["date"], False)}</span></div></a>')
    reports = (f'<section class="sec"><div class="wrap"><div class="s-head"><div><p class="eyebrow">새로 나온 리포트</p>'
               f'<h2 class="s-title">매일 밤, 새 리포트가 쌓입니다.</h2></div><a class="link" href="#">2,680편 모두 보기 →</a></div>'
               f'<div class="cards">{cards}</div></div></section>')

    def tile(s, x, y, w, h, size):
        tsum = f'<span class="ts">{esc(chunk(s["lead"], 110)[0] if s["lead"] else "")}</span>' if size == "l3" else ""
        return (f'<a class="tl {size}" href="#" style="left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;background:{tint(s["chg"])}" '
                f'title="{esc(s["name"])} {sign(s["chg"])}"><span class="tn">{esc(s["name"])}</span><span class="tc tnum">{sign(s["chg"])}</span>{tsum}</a>')
    tm = (f'<section class="sec"><div class="wrap"><div class="s-head"><div><p class="eyebrow">시장 지도</p>'
          f'<h2 class="s-title">시가총액의 {secs[0]["share"]:.0f}%가<span class="dim"> 반도체 한 업종.</span></h2></div><a class="link" href="#">업종 분석 →</a></div>'
          f'<div class="tmap tm-d">{treemap(secs, W=1000, H=500, tile=tile, px=1.12)}</div><div class="tmap tm-m">{treemap(secs, W=1000, H=1450, tile=tile, px=0.35)}</div>'
          f'<div class="legend"><span>면적은 업종 시가총액, 색은 시가총액 가중 등락률 · {kdate(PRICE_DATE)} 종가</span>'
          f'<span>−3%<i style="background:{tint(-3)}"></i><i style="background:{tint(-1)}"></i><i style="background:{tint(0)}"></i><i style="background:{tint(1)}"></i><i style="background:{tint(3)}"></i>+3%</span></div></div></section>')
    rhythm = ('<section class="sec"><div class="wrap"><div class="s-head"><div><p class="eyebrow">하루의 리듬</p>'
              '<h2 class="s-title">시장보다 먼저 움직입니다.</h2></div></div><div class="rhythm">'
              '<div class="rh"><time>07:00<span>개장 전</span></time><h3>모닝브리핑</h3><p>밤사이 해외 시장과 금리·환율, 오늘 볼 공시를 한 장으로. 이코노미스트의 문장으로 씁니다.</p></div>'
              '<div class="rh"><time>15:30<span>장 마감</span></time><h3>시세와 업종 지도</h3><p>2,682개 종목의 종가·거래대금과 29개 업종의 흐름을 마감 직후 갱신합니다.</p></div>'
              '<div class="rh"><time>02:00<span>새벽</span></time><h3>리포트 갱신</h3><p>새 공시와 실적이 나온 회사의 리포트를 다시 씁니다. 사업·실적·전망·리스크까지 열 개 절.</p></div>'
              '</div></div></section>')
    cta = ('<section class="wrap"><div class="cta"><h2>데이터는 무료.<br>해석은 구독.</h2>'
           '<p>시세·재무·핵심 지표는 누구에게나 열려 있습니다. 숫자를 읽어 낸 분석과 전망은 멤버십으로.</p>'
           '<div class="btns"><a class="pill" href="#">무료로 시작</a><a class="pill ghost" href="#">멤버십 보기</a></div>'
           '<div class="plans"><div><b class="tnum">0원</b>무료</div><div><b class="tnum">9,900원</b>BASIC · 월</div><div><b class="tnum">14,900원</b>PRO · 월</div></div></div></section>')
    return (head("KOSAI — 시안 B · 다크 시네마틱") + header() + f"<main>{hero}{market}{reports}{tm}{rhythm}{cta}</main>" + footer() + SPOT_JS + "</body></html>")


def stock(tk="005930"):
    r = report(tk)
    s = BY[tk]
    v = valuation(tk)
    q = r["quant"]["quarterly"]
    ann = r["quant"]["annual"]
    c = s["change"]
    labels = [q_label(x["q"]) for x in q]
    ops = [x["op"] for x in q]
    revs = [x["rev"] for x in q]
    opm = [x["op"] / x["rev"] * 100 for x in q]
    grad = ('<defs><linearGradient id="g2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd6b3"/><stop offset="1" stop-color="#ff8a45"/></linearGradient>'
            '<filter id="gl" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')

    def dark_bars(vals, w=440, h=230, fmt=money, glow=True):
        svg = bars_svg(vals, labels, w=w, h=h, fill="rgba(255,255,255,.14)", highlight_last=True, fill_last="url(#g2)", font="inherit", fsize=13, tsize=12,
                       weight=500, label_fill="rgba(244,243,241,.82)", tick_fill="rgba(244,243,241,.45)", axis="rgba(255,255,255,.16)", radius=5, fmt=fmt,
                       glow="gl" if glow else None)
        return svg.replace('style="font-family:inherit">', 'style="font-family:inherit">' + grad, 1).replace('<defs><filter id="gl"', '<defs><filter id="glx"', 1)
    hero_chart = dark_bars(ops)
    stats = [("시가총액", jo(s["mcap"])), ("거래대금", money(s["trading_value"])), ("PER", f'{v["per"]:.1f}배'), ("PBR", f'{v["pbr"]:.2f}배'),
             ("ROE", f'{v["roe"]:.1f}%'), ("배당수익률", f'{v["div"]:.2f}%'), ("EPS", won(v["eps"])), ("BPS", won(v["bps"]))]
    st = "".join(f"<div><dt>{k}</dt><dd class=tnum>{x}</dd></div>" for k, x in stats)
    hero = (f'<section class="s-hero"><div class="grain"></div><div class="wrap"><div class="crumbs rise"><span>코스피</span><span>{esc(s["sector"])}</span><span>{tk}</span>'
            f'<span>리포트 {kdate(r["reportDate"], False)}</span></div>'
            f'<div class="sh-grid"><div><h1 class="sh-name rise d1">{esc(s["name"])}</h1><p class="sh-en rise d1">SAMSUNG ELECTRONICS</p>'
            f'<div class="sh-px rise d2"><b class="tnum">{grp(s["price"])}</b><span class="won">원</span>{chg_chip(c)}<small>{kdate(PRICE_DATE)} 종가</small></div>'
            f'<div class="sh-btns rise d3"><a class="pill" href="#">＋ 관심종목</a><a class="pill ghost" href="#">공유</a></div></div>'
            f'<div class="panel rise d3"><h3><span>분기 영업이익</span><b class="tnum">{money(ops[-1])}</b></h3>{hero_chart}'
            f'<p class="cap">영업이익률 {opm[0]:.1f}% → {opm[-1]:.1f}% · 연결 · DART 확정치</p></div></div>'
            f'<div class="thesis"><div><h2>{esc(r["title"]["ko"])}</h2><p>{esc(r["lead"]["ko"])}</p></div><dl class="stat">{st}</dl></div></div></section>')
    tabs_items = [("s0", "요점"), ("s1", "사업"), ("s2", "실적"), ("s3", "산업"), ("s4", "전망"), ("s5", "밸류에이션"), ("s6", "강세·약세"),
                  ("s7", "리스크"), ("s8", "체크포인트"), ("s9", "결론")]
    tabs = '<nav class="tabs" id="tabs">' + "".join(f'<a href="#{i}">{n}</a>' for i, n in tabs_items) + "</nav>"
    body = ""
    keys = "".join(f"<li><span>{esc(k['ko'])}</span></li>" for k in r["keypoints"])
    body += f'<section id="s0"><p class="no">01</p><h2>요점</h2><ol class="keys">{keys}</ol></section>'
    for i, (sid, name, key) in enumerate([("s1", "사업 구조", "business"), ("s2", "실적", "earnings"), ("s3", "산업", "industry"),
                                          ("s4", "전망", "outlook"), ("s5", "밸류에이션", "valuation_comment")]):
        ps = chunk(r[key]["ko"], 170)
        digits = sum(ch.isdigit() for ch in ps[0]) / max(1, len(ps[0]))
        inner = (f'<p class="lede">{esc(ps[0])}</p>' if digits < 0.06 else f"<p>{esc(ps[0])}</p>") + "".join(f"<p>{esc(p)}</p>" for p in ps[1:])
        if key == "earnings":
            c1 = dark_bars(revs, w=360, h=220, glow=False)
            c2 = line_svg(opm, labels, w=360, h=220, stroke="#ff9a57", dot="#ffcfa6", label_fill="rgba(244,243,241,.82)", tick_fill="rgba(244,243,241,.45)",
                          fsize=13, tsize=12, weight=500, fmt=lambda x: f"{x:.1f}%", zero=True, width=2, glow="lg",
                          area=("ar", "rgba(255,154,87,.28)", "rgba(255,154,87,0)"))
            inner = (f'{inner}<div class="charts"><div class="panel"><h3><span>분기 매출</span><b class="tnum">{money(revs[-1])}</b></h3>{c1}</div>'
                     f'<div class="panel"><h3><span>영업이익률</span><b class="tnum">{opm[-1]:.1f}%</b></h3>{c2}</div></div>')
            arows = "".join(f'<tr><td>{a["year"]}</td><td>{money(a["rev"])}</td><td>{money(a["op"])}</td><td>{money(a["np_owner"])}</td>'
                            f'<td>{a["opm"]:.1f}%</td><td>{a["roe"]:.1f}%</td></tr>' for a in ann)
            inner += (f'<table class="tbl"><caption>연간 실적 · 연결 · 순이익은 지배주주</caption><thead><tr><th>연도</th><th>매출</th><th>영업이익</th><th>순이익</th>'
                      f'<th>영업이익률</th><th>ROE</th></tr></thead><tbody>{arows}</tbody></table>')
        body += f'<section id="{sid}"><p class="no">{i + 2:02d}</p><h2>{esc(name)}</h2>{inner}</section>'
    bull = "".join(f'<div class="it"><h4>{esc(x["title"]["ko"])}</h4>{paras(x["body"]["ko"], 150)}</div>' for x in r["bull"])
    bear = "".join(f'<div class="it"><h4>{esc(x["title"]["ko"])}</h4>{paras(x["body"]["ko"], 150)}</div>' for x in r["bear"])
    body += (f'<section id="s6"><p class="no">07</p><h2>강세와 약세</h2><div class="bb"><div class="bbp bull"><h3><i style="background:var(--up)"></i>강세 요인</h3>{bull}</div>'
             f'<div class="bbp bear"><h3><i style="background:var(--down)"></i>약세 요인</h3>{bear}</div></div></section>')
    risks = "".join(f'<div class="risk"><span class="chip">{esc(x["cat"]["ko"])}</span><p>{esc(x["body"]["ko"])}</p></div>' for x in r["risks"])
    body += f'<section id="s7"><p class="no">08</p><h2>리스크</h2>{risks}</section>'
    cps = "".join(f'<div class="cp"><b>{esc(x["when"]["ko"])}</b><p>{esc(x["what"]["ko"])}</p></div>' for x in r["checkpoints"])
    body += f'<section id="s8"><p class="no">09</p><h2>다음 체크포인트</h2><div class="tl2">{cps}</div></section>'
    vp = chunk(r["verdict"]["body"]["ko"], 170)
    srcs = "".join(f"<li>{esc(u.split('//')[-1].split('/')[0].replace('www.', ''))}</li>" for u in (r.get("sources") or []))
    body += (f'<section id="s9"><p class="no">10</p><h2>종합 의견</h2><div class="verdict">' + "".join(f"<p>{esc(p)}</p>" for p in vp) + "</div>"
             f'<ul class="srcs">{srcs}</ul><p class="disc">이 리포트는 AI가 공시·재무 데이터와 보도를 분석해 작성한 정보이며 투자 권유가 아닙니다. 투자 판단과 책임은 투자자 본인에게 있습니다.</p></section>')
    tab_js = ("<script>(function(){var a=[].slice.call(document.querySelectorAll('#tabs a')),m={};a.forEach(function(x){m[x.getAttribute('href').slice(1)]=x});"
              "if(a[0])a[0].classList.add('on');var o=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){a.forEach(function(x){x.classList.remove('on')});"
              "var t=m[e.target.id];if(t){t.classList.add('on');t.scrollIntoView({block:'nearest',inline:'nearest'})}}})},{rootMargin:'-35% 0px -60% 0px'});"
              "document.querySelectorAll('.read section[id]').forEach(function(s){o.observe(s)});var f=document.getElementById('s0');"
              "addEventListener('scroll',function(){if(f&&scrollY<f.offsetTop-innerHeight*.5){a.forEach(function(x){x.classList.remove('on')});a[0].classList.add('on')}},{passive:true})})();</script>")
    return (head(f"{s['name']} — {r['title']['ko']} · KOSAI 시안 B") + header("리포트")
            + f'<main>{hero}<div class="wrap">{tabs}<article class="read">{body}</article></div></main>' + footer() + tab_js + "</body></html>")
