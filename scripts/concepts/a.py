"""시안 A — 종이 에디션. 인쇄된 리서치 저널: 명조 제목, 세리프 숫자, 괘선, 발행의 연속성."""
from data import (BY, esc, sign, arrow, cls, won, money, jo, kdate, kdate_full, grp, latest, sectors, movers,
                  valuation, report, brief, PRICE_DATE, MINUS)
from common import chunk, paras, bars_svg, line_svg, treemap, q_label, spark

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,300..600;1,6..72,300..500'
         '&family=Noto+Serif+KR:wght@400;500;600&display=swap" rel="stylesheet">'
         '<link href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">')

CSS = r"""
:root{
  --paper:#f9f8f6; --ink:#141414; --ink2:rgba(20,20,20,.76); --ink3:rgba(20,20,20,.62);
  --rule:rgba(20,20,20,.18); --hair:rgba(20,20,20,.1);
  --up:#c8102e; --down:#1e5fbf;
  --serif:'Noto Serif KR','Newsreader',serif;
  --num:'Newsreader','Noto Serif KR',serif;
  --sans:'Pretendard Variable',Pretendard,-apple-system,'Apple SD Gothic Neo',sans-serif;
  --w:1240px; --pad:48px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-padding-top:72px}
body{margin:0;background:var(--paper);color:var(--ink);font:400 17px/1.8 var(--sans);letter-spacing:-.006em;
  -webkit-font-smoothing:antialiased;word-break:keep-all;overflow-wrap:anywhere;font-feature-settings:"ss01" 0}
body::after{content:"";position:fixed;inset:0;pointer-events:none;background:url(grain.png);opacity:.045;z-index:50}
a{color:inherit;text-decoration:none}
h1,h2,h3,p{margin:0}
.wrap{max-width:var(--w);margin:0 auto;padding:0 var(--pad)}
.num{font-family:var(--num);font-variant-numeric:lining-nums tabular-nums;font-feature-settings:"lnum","tnum"}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--ink3)}

/* ── 발행면 머리 ── */
.util{font:500 12.5px/1 var(--sans);color:var(--ink3);border-bottom:1px solid var(--hair)}
.util-in{display:flex;align-items:center;gap:10px;height:40px}
.util .sp{flex:1}
.util a{color:var(--ink2)} .util a:hover{color:var(--ink)}
.util .u-sub{color:var(--ink);font-weight:600}
.mast{text-align:center;padding:38px 0 22px}
.nameplate{font-family:'Newsreader',serif;font-optical-sizing:auto;font-weight:500;font-size:84px;line-height:1;letter-spacing:.2em;
  margin-right:-.2em;display:inline-block;color:var(--ink)}
.motto{font:400 15px/1.6 var(--serif);color:var(--ink2);margin-top:14px;letter-spacing:.01em}
.secnav{border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);position:sticky;top:0;z-index:20;
  background:rgba(249,248,246,.94);backdrop-filter:saturate(1.4) blur(10px);-webkit-backdrop-filter:saturate(1.4) blur(10px)}
.secnav-in{display:flex;align-items:center;justify-content:center;gap:36px;height:50px;font:500 15px/1 var(--sans);position:relative}
.secnav a{white-space:nowrap;flex:none;color:var(--ink2);padding:6px 0;border-bottom:1.5px solid transparent;transition:color .2s,border-color .2s}
.secnav a:hover{color:var(--ink)} .secnav a.on{color:var(--ink);font-weight:650;border-bottom-color:var(--ink)}
.secnav .find{position:absolute;right:var(--pad);display:flex;align-items:center;gap:8px;color:var(--ink2);font-weight:500;border:0}
.secnav .find svg{width:16px;height:16px}
.secnav .mini{position:absolute;left:var(--pad);font-family:'Newsreader',serif;font-weight:500;font-size:19px;letter-spacing:.2em;
  color:var(--ink);border:0;opacity:0;transition:opacity .25s}
.secnav.stuck .mini{opacity:1}

/* ── 공통 머리말 ── */
.kicker{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;color:var(--ink)}
.kicker .k2{font-weight:500;color:var(--ink3);letter-spacing:0}
.sec{padding:64px 0 0}
.sec-h{display:flex;align-items:baseline;justify-content:space-between;gap:24px;border-top:2px solid var(--ink);padding-top:14px;margin-bottom:34px}
.sec-h h2{font:500 30px/1.3 var(--serif);letter-spacing:-.02em}
.sec-h .more{font:500 14px/1 var(--sans);color:var(--ink2);white-space:nowrap}
.sec-h .more:hover{color:var(--ink)}
.sec-d{font:400 15px/1.6 var(--sans);color:var(--ink3);max-width:720px;margin:-18px 0 26px}

/* ── 1면 ── */
.front{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:56px;padding:44px 0 8px}
.lead-h{font:500 54px/1.2 var(--serif);letter-spacing:-.035em;margin:18px 0 22px;text-wrap:balance}
.lead-h a{background-image:linear-gradient(var(--ink),var(--ink));background-size:0 1.5px;background-position:0 94%;background-repeat:no-repeat;transition:background-size .35s ease}
.lead-h a:hover{background-size:100% 1.5px}
.lead-deck{font:400 19px/1.75 var(--serif);color:var(--ink2);max-width:680px}
.lead-meta{display:flex;gap:18px;align-items:center;margin-top:22px;font:500 14px/1 var(--sans);color:var(--ink3)}
.lead-meta .more{color:var(--ink);font-weight:650}
.lead-subs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;margin-top:40px;border-top:1px solid var(--rule);padding-top:22px}
.sub h3{font:500 18px/1.5 var(--serif);letter-spacing:-.02em;margin-bottom:8px}
.sub p{font:400 14.5px/1.7 var(--sans);color:var(--ink2)}
.sub:hover h3{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.22em}

.markets{border-left:1px solid var(--rule);padding-left:34px}
.rail-h{display:flex;justify-content:space-between;align-items:baseline;font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;
  border-bottom:1px solid var(--ink);padding-bottom:9px;margin-bottom:4px}
.rail-h span{font-weight:500;color:var(--ink3);letter-spacing:0}
.mk{width:100%;border-collapse:collapse}
.mk th{font:500 14.5px/1 var(--sans);text-align:left;padding:11px 0;color:var(--ink);border-bottom:1px solid var(--hair);white-space:nowrap}
.mk td{text-align:right;padding:11px 0;border-bottom:1px solid var(--hair);font:400 17px/1 var(--num);font-variant-numeric:lining-nums tabular-nums}
.mk td.c{width:74px;font-size:15px}
.rail-h2{font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;margin:30px 0 12px;display:flex;justify-content:space-between}
.rail-h2 span{font-weight:500;color:var(--ink3)}
.flows .fl{display:grid;grid-template-columns:44px 1fr 72px;align-items:center;gap:10px;height:30px;font:500 13.5px/1 var(--sans)}
.flows .ax{position:relative;height:10px}
.flows .ax::before{content:"";position:absolute;left:50%;top:-4px;bottom:-4px;width:1px;background:var(--ink3)}
.flows .ax i{position:absolute;top:0;bottom:0}
.flows .ax i.up{left:50%;background:var(--up)} .flows .ax i.down{right:50%;background:var(--down)}
.flows b{font:400 15px/1 var(--num);text-align:right;font-variant-numeric:lining-nums tabular-nums}
.breadth{display:flex;height:10px;gap:2px}
.breadth i{display:block}
.breadth .b-up{background:var(--up)} .breadth .b-dn{background:var(--down)} .breadth .b-fl{background:rgba(20,20,20,.22)}
.breadth-l{display:flex;justify-content:space-between;margin-top:9px;font:500 13px/1 var(--sans);color:var(--ink3)}
.breadth-l b{font:400 15px/1 var(--num);color:var(--ink);margin-left:4px;font-variant-numeric:lining-nums tabular-nums}
.rail-note{font:400 12.5px/1.6 var(--sans);color:var(--ink3);margin-top:22px}

/* ── 리포트 면 ── */
.rep-grid{display:grid;grid-template-columns:minmax(0,1.08fr) minmax(0,1fr);gap:48px}
.feat{border-right:1px solid var(--rule);padding-right:48px}
.feat-h{font:500 38px/1.28 var(--serif);letter-spacing:-.03em;margin:14px 0 18px;text-wrap:balance}
.feat-p{font:400 17px/1.8 var(--sans);color:var(--ink2)}
.px{display:flex;gap:14px;align-items:baseline;margin-top:18px;font:500 13px/1 var(--sans);color:var(--ink3)}
.px b{font:400 18px/1 var(--num);color:var(--ink);font-variant-numeric:lining-nums tabular-nums}
.px .up,.px .down{font:400 15px/1 var(--num);font-variant-numeric:lining-nums tabular-nums}
.op{display:flex;align-items:flex-end;gap:12px;margin-top:14px;font:500 12px/1 var(--sans);color:var(--ink3)}
.op span{align-self:center} .op b{font:400 15px/1 var(--num);color:var(--ink);font-variant-numeric:lining-nums tabular-nums}
.quad{display:grid;grid-template-columns:1fr 1fr;gap:0 36px}
.card{padding:0 0 24px;margin-bottom:24px;border-bottom:1px solid var(--hair)}
.card:nth-last-child(-n+2){border-bottom:0;margin-bottom:0}
.card h3{font:500 21px/1.45 var(--serif);letter-spacing:-.025em;margin:10px 0 12px;text-wrap:balance}
.card:hover h3,.feat:hover .feat-h{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.2em}
.rep-list{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 36px;border-top:1px solid var(--rule);margin-top:34px}
.rl{display:block;padding:16px 0;border-bottom:1px solid var(--hair)}
.rl .rl-n{display:block;font:650 12.5px/1.4 var(--sans);margin-bottom:5px}
.rl .rl-t{font:500 16px/1.5 var(--serif);letter-spacing:-.02em}
.rl:hover .rl-t{text-decoration:underline;text-decoration-thickness:1px;text-underline-offset:.2em}

/* ── 시장 지도 ── */
.tmap{position:relative;width:100%;aspect-ratio:1000/520;background:var(--paper)} .tm-m{display:none;aspect-ratio:1000/1450}
.tile{position:absolute;box-shadow:inset 0 0 0 1px var(--paper);padding:10px 12px;overflow:hidden;color:var(--ink)}
.tile .tn{font:600 14px/1.25 var(--sans);letter-spacing:-.01em;display:block}
.tile .tc{font:400 15px/1.2 var(--num);display:block;margin-top:3px;font-variant-numeric:lining-nums tabular-nums}
.tile.l3{padding:22px 24px}
.tile.l3 .tn{font:500 30px/1.2 var(--serif);letter-spacing:-.03em}
.tile.l3 .tc{font-size:26px;margin-top:8px}
.tile.l3 .ts{display:block;font:400 14px/1.6 var(--sans);color:var(--ink2);margin-top:14px;max-width:420px}
.tile .ts{display:none}
.tile.l1 .tc,.tile.l0 .tn,.tile.l0 .tc{display:none}
.tile.l1{padding:7px 8px} .tile.l1 .tn{font-size:12px} .tile.l0{padding:0}
.tmap-foot{display:flex;justify-content:space-between;gap:20px;margin-top:14px;font:400 12.5px/1.5 var(--sans);color:var(--ink3)}
.legend{display:flex;align-items:center;gap:8px}
.legend i{display:inline-block;width:22px;height:10px}

/* ── 움직인 종목 ── */
.two{display:grid;grid-template-columns:1fr 1fr;gap:56px}
.mv{list-style:none;margin:0;padding:0;counter-reset:m}
.mv li{display:grid;grid-template-columns:28px 1fr auto auto;gap:14px;align-items:baseline;padding:13px 0;border-bottom:1px solid var(--hair);counter-increment:m}
.mv li::before{content:counter(m);font:400 16px/1 var(--num);color:var(--ink3)}
.mv .n{font:600 16px/1.3 var(--sans)} .mv .s{font:400 13px/1 var(--sans);color:var(--ink3);margin-left:8px;font-weight:500}
.mv .p{font:400 16px/1 var(--num);font-variant-numeric:lining-nums tabular-nums}
.mv .c{font:400 16px/1 var(--num);width:74px;text-align:right;font-variant-numeric:lining-nums tabular-nums}
.note{font:400 12.5px/1.6 var(--sans);color:var(--ink3);margin-top:14px}

/* ── 구독 ── */
.member{margin-top:80px;border-top:2px solid var(--ink);padding:56px 0 20px;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.35fr);gap:56px;align-items:start}
.member h2{font:500 40px/1.3 var(--serif);letter-spacing:-.035em}
.member .m-p{font:400 16px/1.8 var(--sans);color:var(--ink2);margin-top:18px;max-width:420px}
.plans{display:grid;grid-template-columns:repeat(3,1fr);border-left:1px solid var(--rule)}
.plan{padding:4px 26px 0;border-right:1px solid var(--rule)}
.plan h3{font:650 12.5px/1.4 var(--sans);letter-spacing:.06em}
.plan .pr{font:400 44px/1 var(--num);margin:18px 0 6px;font-variant-numeric:lining-nums tabular-nums;letter-spacing:-.01em}
.plan .pr span{display:block;font:500 13px/1 var(--sans);color:var(--ink3);margin-top:10px;letter-spacing:0}
.plan p{font:400 14px/1.7 var(--sans);color:var(--ink2)}
.btn{display:inline-flex;align-items:center;justify-content:center;height:46px;padding:0 24px;border:1px solid var(--ink);background:var(--ink);color:var(--paper);
  font:600 15px/1 var(--sans);letter-spacing:-.01em;transition:background .2s,color .2s}
.btn:hover{background:transparent;color:var(--ink)}
.btn.ghost{background:transparent;color:var(--ink)} .btn.ghost:hover{background:var(--ink);color:var(--paper)}

/* ── 판권 ── */
.colophon{margin-top:88px;border-top:2px solid var(--ink);padding:40px 0 56px}
.c-top{display:grid;grid-template-columns:260px minmax(0,1fr) auto;gap:48px;align-items:start}
.c-top .nameplate{font-size:30px;letter-spacing:.2em}
.c-top p{font:400 15px/1.8 var(--serif);color:var(--ink2);max-width:560px}
.c-cols{display:flex;gap:40px;font:500 14px/2 var(--sans)}
.c-cols div{display:flex;flex-direction:column}
.c-cols b{font:650 12.5px/2 var(--sans);letter-spacing:.02em;color:var(--ink3)}
.c-cols a{color:var(--ink2)} .c-cols a:hover{color:var(--ink)}
.c-fine{border-top:1px solid var(--hair);margin-top:36px;padding-top:18px;font:400 12.5px/1.9 var(--sans);color:var(--ink3);display:flex;flex-wrap:wrap;gap:0 18px}

/* ── 리포트 표지 ── */
.crumb{font:500 13.5px/1 var(--sans);color:var(--ink3);padding:26px 0 0;display:flex;gap:8px}
.crumb a:hover{color:var(--ink)}
.cover{padding:30px 0 0}
.cv-meta{display:flex;justify-content:space-between;gap:20px;border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);padding:12px 0;
  font:650 12.5px/1.4 var(--sans);letter-spacing:.02em}
.cv-meta span:last-child{font-weight:500;color:var(--ink3);letter-spacing:0}
.cv-grid{display:grid;grid-template-columns:minmax(0,1fr) 332px;grid-template-areas:"main data" "keys data";grid-template-rows:auto 1fr;column-gap:64px;padding:40px 0 48px;border-bottom:1px solid var(--rule)}
.cv-main{grid-area:main} .cv-data{grid-area:data;align-self:start} .keys{grid-area:keys}
.cv-co{font:600 20px/1.3 var(--sans);letter-spacing:-.01em;display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.cv-co .en{font:italic 400 19px/1 'Newsreader',serif;color:var(--ink3);letter-spacing:0}
.cv-h{font:500 66px/1.17 var(--serif);letter-spacing:-.045em;margin:22px 0 26px;text-wrap:balance}
.cv-deck{font:400 20px/1.8 var(--serif);color:var(--ink2);max-width:700px}
.cv-by{margin-top:28px;display:flex;flex-wrap:wrap;gap:8px 22px;font:500 13.5px/1.4 var(--sans);color:var(--ink3)}
.cv-by b{color:var(--ink);font-weight:600}
.cv-data{border-left:1px solid var(--rule);padding-left:34px}
.px-big{font:400 64px/1 var(--num);letter-spacing:-.02em;font-variant-numeric:lining-nums tabular-nums}
.px-big span{font:500 18px/1 var(--sans);margin-left:6px;letter-spacing:0;color:var(--ink2)}
.px-chg{display:flex;align-items:baseline;gap:12px;margin-top:12px;font:400 20px/1 var(--num);font-variant-numeric:lining-nums tabular-nums}
.px-chg span{font:500 13px/1 var(--sans);color:var(--ink3)}
.kv{display:grid;grid-template-columns:1fr 1fr;margin:28px 0 26px;border-top:1px solid var(--ink)}
.kv div{padding:12px 0 11px;border-bottom:1px solid var(--hair)}
.kv div:nth-child(odd){padding-right:14px} .kv div:nth-child(even){padding-left:14px;border-left:1px solid var(--hair)}
.kv dt{font:500 12.5px/1.3 var(--sans);color:var(--ink3)}
.kv dd{margin:5px 0 0;font:400 19px/1.2 var(--num);font-variant-numeric:lining-nums tabular-nums}
.watch{display:flex;width:100%;height:46px;align-items:center;justify-content:center;gap:8px;border:1px solid var(--ink);background:transparent;color:var(--ink);
  font:600 15px/1 var(--sans);cursor:pointer;transition:background .2s,color .2s}
.watch:hover{background:var(--ink);color:var(--paper)}
.watch svg{width:15px;height:15px}
.cv-fine{font:400 12px/1.6 var(--sans);color:var(--ink3);margin-top:14px}

.keys{margin-top:40px;border-top:1px solid var(--ink);padding-top:12px;max-width:760px}
.keys-h{font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;margin-bottom:6px}
.keys ol{list-style:none;margin:0;padding:0;counter-reset:k}
.keys li{counter-increment:k;display:grid;grid-template-columns:44px 1fr;gap:4px;padding:13px 0;border-bottom:1px solid var(--hair);font:400 16px/1.7 var(--sans)}
.keys li:last-child{border-bottom:0}
.keys li::before{content:counter(k,decimal-leading-zero);font:400 20px/1.3 var(--num);color:var(--ink3);font-variant-numeric:lining-nums}

.figure{margin-top:48px;border-top:2px solid var(--ink);padding-top:16px}
.fig-h{font:500 30px/1.35 var(--serif);letter-spacing:-.03em;max-width:880px}
.fig-d{font:400 14.5px/1.6 var(--sans);color:var(--ink3);margin-top:8px}
.smalls{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:44px;margin-top:30px}
.smalls h4{margin:0 0 6px;font:650 13px/1.4 var(--sans);letter-spacing:.02em;display:flex;justify-content:space-between;align-items:baseline}
.smalls h4 span{font:400 21px/1 var(--num);letter-spacing:0;font-variant-numeric:lining-nums tabular-nums}
.fig-src{font:400 12.5px/1.6 var(--sans);color:var(--ink3);margin-top:16px;border-top:1px solid var(--hair);padding-top:10px}

.rbody{display:grid;grid-template-columns:240px minmax(0,1fr);gap:56px;margin-top:64px}
.toc{position:sticky;top:78px;align-self:start;font:500 14px/1.5 var(--sans)}
.toc b{display:block;font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;border-bottom:1px solid var(--ink);padding-bottom:9px;margin-bottom:6px}
.toc a{display:grid;grid-template-columns:30px 1fr;padding:7px 0;color:var(--ink3);transition:color .2s}
.toc a span{font:400 14px/1.5 var(--num);font-variant-numeric:lining-nums tabular-nums}
.toc a:hover,.toc a.on{color:var(--ink)}
.toc a.on{font-weight:650}
.text{max-width:720px}
.text section{padding-bottom:56px}
.text section+section{border-top:1px solid var(--rule);padding-top:26px}
.sn{font:400 15px/1 var(--num);color:var(--ink3);font-variant-numeric:lining-nums}
.text h2{font:500 32px/1.35 var(--serif);letter-spacing:-.03em;margin:8px 0 22px}
.text p{margin:0 0 20px;font:400 17.5px/1.85 var(--sans);color:var(--ink)}
.text p.lede{font:400 20px/1.8 var(--serif);color:var(--ink2)}
.tbl{width:100%;border-collapse:collapse;margin:12px 0 26px;font:500 14px/1 var(--sans)}
.tbl caption{text-align:left;font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;padding-bottom:10px}
.tbl caption span{font-weight:500;color:var(--ink3);margin-left:8px;letter-spacing:0}
.tbl th{font:500 12.5px/1.3 var(--sans);color:var(--ink3);text-align:right;padding:9px 0 9px 12px;border-top:1px solid var(--ink);border-bottom:1px solid var(--rule)}
.tbl th:first-child,.tbl td:first-child{text-align:left;padding-left:0}
.tbl td{text-align:right;padding:11px 0 11px 12px;border-bottom:1px solid var(--hair);font:400 16px/1 var(--num);font-variant-numeric:lining-nums tabular-nums}
.tbl td:first-child{font:500 14px/1 var(--sans)}
.tbl tr:last-child td{border-bottom:1px solid var(--ink)}
.pq{font:500 25px/1.6 var(--serif);letter-spacing:-.025em;border-top:2px solid var(--ink);border-bottom:1px solid var(--rule);padding:22px 0 24px;margin:8px 0 30px}
.bb{display:grid;grid-template-columns:1fr 1fr;gap:0;border-top:1px solid var(--ink)}
.bb>div{padding:18px 0 0}
.bb>div:first-child{padding-right:28px;border-right:1px solid var(--rule)} .bb>div:last-child{padding-left:28px}
.bb h3{font:650 12.5px/1.4 var(--sans);letter-spacing:.02em;margin-bottom:16px;display:flex;gap:8px;align-items:center}
.bb h3 i{width:8px;height:8px;display:inline-block}
.bb h4{font:500 18px/1.5 var(--serif);letter-spacing:-.02em;margin:0 0 8px}
.bb p{font:400 15.5px/1.8 var(--sans) !important;color:var(--ink2) !important;margin:0 0 12px !important}
.bb .item{padding-bottom:20px;margin-bottom:20px;border-bottom:1px solid var(--hair)}
.bb .item:last-child{border-bottom:0;margin-bottom:0}
.risk{display:grid;grid-template-columns:132px 1fr;gap:24px;padding:18px 0;border-bottom:1px solid var(--hair)}
.risk:first-of-type{border-top:1px solid var(--ink)}
.risk b{font:650 13.5px/1.5 var(--sans)}
.risk p{margin:0 !important;font-size:16px !important;color:var(--ink2) !important}
.cp{display:grid;grid-template-columns:132px 1fr;gap:24px;padding:16px 0;border-bottom:1px solid var(--hair);position:relative}
.cp:first-of-type{border-top:1px solid var(--ink)}
.cp b{font:500 16px/1.5 var(--serif);letter-spacing:-.02em}
.cp p{margin:0 !important;font-size:16px !important;color:var(--ink2) !important}
.verdict p{font:400 19px/1.9 var(--serif) !important;color:var(--ink) !important}
.srcs{columns:2;column-gap:36px;font:400 13px/1.7 var(--sans);color:var(--ink3);padding-left:18px;margin:0}
.srcs li{break-inside:avoid;margin-bottom:6px;word-break:break-all}
.disc{font:400 13px/1.8 var(--sans);color:var(--ink3);border-top:1px solid var(--rule);padding-top:16px;margin-top:10px}

/* ── 좁은 화면 ── */
@media (max-width:1100px){
  :root{--pad:32px}
  .front{grid-template-columns:1fr;gap:40px}
  .markets{border-left:0;padding-left:0;border-top:2px solid var(--ink);padding-top:14px;display:grid;grid-template-columns:1fr 1fr;gap:0 40px}
  .markets .rail-h{grid-column:1/-1}
  .rep-grid{grid-template-columns:1fr} .feat{border-right:0;padding-right:0;border-bottom:1px solid var(--rule);padding-bottom:30px}
  .cv-grid{grid-template-columns:1fr;grid-template-areas:"main" "data" "keys";row-gap:36px} .cv-data{border-left:0;padding-left:0;border-top:1px solid var(--rule);padding-top:28px}
  .rbody{grid-template-columns:1fr;gap:28px} .toc{display:none}
  .member{grid-template-columns:1fr}
  .c-top{grid-template-columns:1fr;gap:24px}
}
@media (max-width:720px){
  :root{--pad:20px}
  body{font-size:16.5px}
  .util .hide-m{display:none}
  .mast{padding:28px 0 16px}
  .nameplate{font-size:50px}
  .motto{font-size:13px;margin-top:10px}
  .secnav-in{justify-content:flex-start;gap:24px;overflow-x:auto;scrollbar-width:none;padding-right:64px}
  .secnav-in::-webkit-scrollbar{display:none}
  .secnav .find{right:0;background:linear-gradient(90deg,rgba(249,248,246,0),var(--paper) 30%);padding:0 var(--pad) 0 28px;height:100%}
  .secnav .find span{display:none}
  .secnav .mini{display:none}
  .front{padding-top:30px}
  .lead-h{font-size:34px;line-height:1.28;margin:14px 0 16px}
  .lead-deck{font-size:17px}
  .lead-subs{grid-template-columns:1fr;gap:18px}
  .markets{grid-template-columns:1fr}
  .sec{padding-top:48px}
  .sec-h h2{font-size:24px}
  .feat-h{font-size:28px}
  .quad{grid-template-columns:1fr} .card:nth-last-child(2){border-bottom:1px solid var(--hair);margin-bottom:24px}
  .rep-list{grid-template-columns:1fr}
  .tm-d{display:none} .tm-m{display:block}
  .tile.l3{padding:14px} .tile.l3 .tn{font-size:22px} .tile.l3 .tc{font-size:19px} .tile.l3 .ts{display:none}
  .tile.l2{padding:8px 9px} .tile.l2 .tn{font-size:12.5px} .tile.l2 .tc{font-size:13.5px}
  .tile.l1{padding:6px 7px} .tile.l1 .tn{font-size:11.5px}
  .tmap-foot{flex-direction:column}
  .two{grid-template-columns:1fr;gap:36px}
  .member{padding:40px 0} .member h2{font-size:30px}
  .plans{grid-template-columns:1fr;border-left:0} .plan{border-right:0;border-top:1px solid var(--rule);padding:18px 0}
  .plan .pr{font-size:36px;margin:10px 0 4px}
  .c-cols{flex-wrap:wrap;gap:24px 40px}
  .cv-h{font-size:38px;line-height:1.24;margin:16px 0 18px}
  .cv-deck{font-size:17.5px}
  .px-big{font-size:52px}
  .smalls{grid-template-columns:1fr;gap:26px}
  .fig-h{font-size:24px}
  .text h2{font-size:26px}
  .text p{font-size:16.5px}
  .text p.lede{font-size:18px}
  .bb{grid-template-columns:1fr} .bb>div:first-child{padding-right:0;border-right:0;border-bottom:1px solid var(--rule);padding-bottom:18px} .bb>div:last-child{padding-left:0}
  .risk,.cp{grid-template-columns:1fr;gap:6px}
  .srcs{columns:1}
  .pq{font-size:21px}
}
"""

NAV = [("오늘", "index.html"), ("리포트", "#"), ("업종", "#"), ("모닝브리핑", "#"), ("관심종목", "#"), ("멤버십", "#")]
SEARCH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>'


def head(title):
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#f9f8f6">'
            f'<title>{esc(title)}</title>{FONTS}<link rel="stylesheet" href="a.css"></head><body>')


def masthead(b, active="오늘", big=True):
    util = (f'<div class="util"><div class="wrap util-in"><span>{kdate_full(b["date"])}</span>'
            f'<span class="hide-m">·</span><span class="hide-m">모닝브리핑 제{b["_no"]}호</span><span class="sp"></span>'
            f'<a href="#">로그인</a><a class="u-sub" href="#">구독하기</a></div></div>')
    mast = ('<header class="mast"><div class="wrap"><a class="nameplate" href="index.html">KOSAI</a>'
            '<p class="motto">한국 상장사 리서치 — 매 거래일 아침 일곱 시에 발행합니다</p></div></header>') if big else ""
    on = ' class="on"'
    links = "".join(f'<a href="{h}"{on if n == active else ""}>{n}</a>' for n, h in NAV)
    nav = (f'<nav class="secnav{"" if big else " stuck"}" id="secnav"><div class="wrap secnav-in"><a class="mini" href="index.html">KOSAI</a>{links}'
           f'<a class="find" href="#">{SEARCH_SVG}<span>종목 찾기</span></a></div></nav>')
    return util + mast + nav


def colophon():
    return ('<footer class="colophon"><div class="wrap"><div class="c-top"><a class="nameplate" href="index.html">KOSAI</a>'
            '<p>KOSAI는 코스피·코스닥에 상장된 2,682개 회사의 공시·재무·시세를 모아 AI가 분석한 리서치를 매 거래일 아침에 발행합니다. '
            '투자 권유가 아니라 판단에 필요한 정보를 한곳에 모으는 것이 목적입니다.</p>'
            '<div class="c-cols"><div><b>읽기</b><a href="#">리포트</a><a href="#">업종</a><a href="#">모닝브리핑</a></div>'
            '<div><b>회사</b><a href="#">소개</a><a href="#">멤버십</a><a href="#">문의</a></div>'
            '<div><b>정책</b><a href="#">이용약관</a><a href="#">개인정보처리방침</a></div></div></div>'
            '<div class="c-fine"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span>'
            '<span>서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>hello@kosai.kr</span><span>© 2026 KOSAI</span></div>'
            '</div></footer>')


STICKY_JS = ("<script>(function(){var n=document.getElementById('secnav');if(!n)return;var m=document.querySelector('.mast');"
             "if(!m)return;var o=new IntersectionObserver(function(e){n.classList.toggle('stuck',!e[0].isIntersecting)},{threshold:0});o.observe(m);})();</script>")


def tint(chg):
    """업종 지도 칠 — 종이 위 옅은 물감. 붉은·푸른 기운은 3% 등락에서 가장 짙다."""
    a = min(abs(chg) / 3.0, 1.0)
    if chg > 0.05:
        return f"rgba(160,40,40,{0.045 + a * 0.15:.3f})"
    if chg < -0.05:
        return f"rgba(40,80,150,{0.045 + a * 0.15:.3f})"
    return "rgba(20,20,20,.045)"


def home():
    b = brief()
    f = b["_facts"]
    reps = latest(13)
    secs, tot = sectors()
    up, dn = movers(6)
    subs = [s for s in b["sections"] if s.get("id") in ("oil", "chips", "breadth")][:3]
    first_sentence = lambda t: (chunk(t, 90) or [""])[0]
    lead = "".join(
        f'<a class="sub" href="#"><h3>{esc(s["heading"]["ko"])}</h3><p>{esc(first_sentence(s["paragraphs"][0]["ko"]))}</p></a>' for s in subs)
    deck = chunk(b["summary"]["ko"], 150)[0]
    rows = ""
    order = ["코스피", "코스닥", "S&P 500", "나스닥", "필라델피아 반도체", "미 10년물", "WTI", "달러인덱스"]
    for k in order:
        if k not in f:
            continue
        v, c = f[k]
        cc = sign(c, 2, pct=not k.endswith("10년물")) + ("%p" if k.endswith("10년물") else "")
        rows += f'<tr><th>{k}</th><td class="v">{v}</td><td class="c {cls(c)}">{cc}</td></tr>'
    mx = max(abs(v) for _, v in f["flows"])
    flows = ""
    for name, v in f["flows"]:
        wpc = abs(v) / mx * 50
        flows += (f'<div class="fl"><span>{name}</span><span class="ax"><i class="{cls(v)}" style="width:{wpc:.1f}%"></i></span>'
                  f'<b class="{cls(v)}">{("+" if v > 0 else MINUS if v < 0 else "") + grp(abs(v))}</b></div>')
    bu, bd, bf = f["breadth"]
    markets = (f'<aside class="markets"><h2 class="rail-h">시장<span>{kdate(f["kr_date"])} 마감</span></h2>'
               f'<table class="mk">{rows}</table>'
               f'<div><h3 class="rail-h2">코스피 투자자별 순매수<span>억 원</span></h3><div class="flows">{flows}</div>'
               f'<h3 class="rail-h2">오른 종목과 내린 종목<span>코스피·코스닥</span></h3>'
               f'<div class="breadth"><i class="b-up" style="flex:{bu}"></i><i class="b-fl" style="flex:{bf}"></i><i class="b-dn" style="flex:{bd}"></i></div>'
               f'<div class="breadth-l"><span>상승<b>{grp(bu)}</b></span><span>보합<b>{grp(bf)}</b></span><span>하락<b>{grp(bd)}</b></span></div>'
               f'<p class="rail-note">미국 지수는 현지 {kdate(f["us_date"], False)} 종가, 국내는 {kdate(f["kr_date"], False)} 종가 기준입니다.</p></div></aside>')
    front = (f'<section class="front"><article class="lead"><div class="kicker"><span>모닝브리핑</span>'
             f'<span class="k2">{kdate(b["date"])} 오전 7시 28분 · 제{b["_no"]}호</span></div>'
             f'<h1 class="lead-h"><a href="#">{esc(b["title"]["ko"])}</a></h1><p class="lead-deck">{esc(deck)}</p>'
             f'<div class="lead-meta"><span>{len(b["sections"])}개 주제 · 3분 읽기</span><a class="more" href="#">브리핑 읽기 →</a></div>'
             f'<div class="lead-subs">{lead}</div></article>{markets}</section>')

    def pxline(r, show_date=True):
        c = r["change"] or 0
        return (f'<div class="px"><b>{won(r["price"])}</b><span class="{cls(c)}">{arrow(c)} {abs(c):.2f}%</span>'
                + (f'<span>{kdate(r["date"], False)} 발행</span>' if show_date else "") + "</div>")

    def opline(r, w=96, h=26):
        ops = r.get("ops") or []
        if not [o for o in ops if o is not None]:
            return ""
        last = next((o for o in reversed(ops) if o is not None), None)
        return (f'<div class="op"><span>분기 영업이익</span>{spark(ops, w=w, h=h, fill="rgba(20,20,20,.2)", last="#141414", neg="rgba(20,20,20,.2)")}'
                f'<b>{money(last)}</b></div>')

    ft = reps[0]
    feat = (f'<article class="feat"><div class="kicker"><span>{esc(ft["sector"])}</span><span class="k2">{esc(ft["name"])} · {esc(ft["market"])} {ft["tk"]}</span></div>'
            f'<h3 class="feat-h"><a href="stock.html">{esc(ft["title"])}</a></h3><p class="feat-p">{esc(ft["lead"])}</p>{pxline(ft)}{opline(ft, 150, 40)}</article>')
    quad = "".join(
        f'<article class="card"><div class="kicker"><span>{esc(r["sector"])}</span><span class="k2">{esc(r["name"])}</span></div>'
        f'<h3><a href="stock.html">{esc(r["title"])}</a></h3>{pxline(r)}{opline(r)}</article>' for r in reps[1:5])
    lst = "".join(f'<a class="rl" href="stock.html"><span class="rl-n">{esc(r["name"])}</span><span class="rl-t">{esc(r["title"])}</span></a>' for r in reps[5:11])
    reports = (f'<section class="sec"><header class="sec-h"><h2>새로 나온 리포트</h2><a class="more" href="#">2,680편 전체 보기 →</a></header>'
               f'<div class="rep-grid">{feat}<div class="quad">{quad}</div></div><div class="rep-list">{lst}</div></section>')

    def tile(s, x, y, w, h, size):
        tsum = f'<span class="ts">{esc(chunk(s["lead"], 110)[0] if s["lead"] else "")}</span>' if size == "l3" else ""
        return (f'<a class="tile {size}" href="#" style="left:{x:.3f}%;top:{y:.3f}%;width:{w:.3f}%;height:{h:.3f}%;background:{tint(s["chg"])}" '
                f'title="{esc(s["name"])} {sign(s["chg"])} · {jo(s["mcap"])}"><span class="tn">{esc(s["name"])}</span>'
                f'<span class="tc {cls(s["chg"])}">{sign(s["chg"])}</span>{tsum}</a>')
    top = secs[0]
    tm = (f'<section class="sec"><header class="sec-h"><h2>반도체 한 업종이 시가총액의 {top["share"]:.0f}%</h2><a class="more" href="#">업종 분석 →</a></header>'
          f'<p class="sec-d">코스피·코스닥 {len(secs)}개 업종의 크기와 오늘의 방향. 면적은 업종 시가총액, 색은 시가총액 가중 등락률입니다.</p>'
          f'<div class="tmap tm-d">{treemap(secs, tile=tile)}</div><div class="tmap tm-m">{treemap(secs, W=1000, H=1450, tile=tile, px=0.35)}</div>'
          f'<div class="tmap-foot"><span>{kdate(PRICE_DATE)} 종가 · 전체 시가총액 {jo(tot)}</span>'
          f'<span class="legend">−3%<i style="background:{tint(-3)}"></i><i style="background:{tint(-1)}"></i><i style="background:{tint(0)}"></i>'
          f'<i style="background:{tint(1)}"></i><i style="background:{tint(3)}"></i>+3%</span></div></section>')

    def mvli(s):
        return (f'<li><span><span class="n">{esc(s["name"])}</span><span class="s">{esc(s["sector"])}</span></span>'
                f'<span class="p">{won(s["price"])}</span><span class="c {cls(s["change"])}">{sign(s["change"])}</span></li>')
    mv = (f'<section class="sec"><header class="sec-h"><h2>오늘 크게 움직인 종목</h2><a class="more" href="#">전체 순위 →</a></header>'
          f'<div class="two"><div><h3 class="rail-h">오른 종목<span>시가총액 1조 원 이상</span></h3><ol class="mv">{"".join(mvli(s) for s in up)}</ol></div>'
          f'<div><h3 class="rail-h">내린 종목<span>시가총액 1조 원 이상</span></h3><ol class="mv">{"".join(mvli(s) for s in dn)}</ol></div></div>'
          f'<p class="note">{kdate(PRICE_DATE)} 종가 기준입니다.</p></section>')
    member = ('<section class="member"><div><h2>데이터는 무료로,<br>해석은 구독으로.</h2>'
              '<p class="m-p">시세·재무·핵심 지표는 누구에게나 공개합니다. 그 숫자를 읽어 낸 분석과 전망, 리스크 진단은 구독으로 받아 보실 수 있습니다.</p>'
              '<p style="margin-top:28px"><a class="btn" href="#">멤버십 보기</a></p></div>'
              '<div class="plans"><div class="plan"><h3>무료</h3><p class="pr">0<span>원</span></p><p>시세·핵심 지표<br>리포트 개요와 사업 구조</p></div>'
              '<div class="plan"><h3>BASIC</h3><p class="pr">9,900<span>원/월</span></p><p>리포트 전문<br>하루 5편</p></div>'
              '<div class="plan"><h3>PRO</h3><p class="pr">14,900<span>원/월</span></p><p>리포트 전문<br>하루 15편</p></div></div></section>')
    return (head("KOSAI — 시안 A · 종이 에디션") + masthead(b) + f'<main class="wrap">{front}{reports}{tm}{mv}{member}</main>'
            + colophon() + STICKY_JS + "</body></html>")


def stock(tk="005930"):
    b = brief()
    r = report(tk)
    s = BY[tk]
    v = valuation(tk)
    q = r["quant"]["quarterly"]
    ann = r["quant"]["annual"]
    c = s["change"]
    title = r["title"]["ko"]
    kv = [("시가총액", jo(s["mcap"])), ("거래대금", money(s["trading_value"])), ("PER", f'{v["per"]:.1f}배' if v["per"] else "—"),
          ("PBR", f'{v["pbr"]:.2f}배' if v["pbr"] else "—"), ("ROE", f'{v["roe"]:.1f}%' if v["roe"] is not None else "—"),
          ("배당수익률", f'{v["div"]:.2f}%' if v["div"] else "—"), ("EPS", won(v["eps"]) if v["eps"] else "—"), ("BPS", won(v["bps"]) if v["bps"] else "—")]
    kvh = "".join(f"<div><dt>{k}</dt><dd>{x}</dd></div>" for k, x in kv)
    nsrc = len(r.get("sources") or [])
    words = sum(len((r.get(k) or {}).get("ko", "")) for k in ("business", "earnings", "industry", "outlook", "valuation_comment"))
    mins = max(6, round((words + 2400) / 500))
    keys = "".join(f"<li><span>{esc(k['ko'])}</span></li>" for k in r["keypoints"])
    cover = (f'<div class="crumb"><a href="#">리포트</a><span>/</span><a href="#">{esc(s["sector"])}</a><span>/</span><span>{esc(s["name"])}</span></div>'
             f'<section class="cover"><div class="cv-meta"><span>KOSAI 리서치 리포트</span>'
             f'<span>{kdate_full(r["reportDate"])[:-4]} 발행 · 재무 {kdate(r["quant"]["asOf"], False)} 기준</span></div>'
             f'<div class="cv-grid"><div class="cv-main"><p class="cv-co">{esc(s["name"])}<span class="en">Samsung Electronics</span></p>'
             f'<h1 class="cv-h">{esc(title)}</h1><p class="cv-deck">{esc(r["lead"]["ko"])}</p>'
             f'<div class="cv-by"><span><b>{esc(s["market"])}</b> {tk}</span><span><b>{esc(s["sector"])}</b></span><span>10개 절 · 약 {mins}분</span><span>출처 {nsrc}건</span></div>'
             f'</div><div class="keys"><h2 class="keys-h">요점</h2><ol>{keys}</ol></div>'
             f'<aside class="cv-data"><div class="px-big">{grp(s["price"])}<span>원</span></div>'
             f'<div class="px-chg {cls(c)}">{arrow(c)} {abs(c):.2f}%<span>{kdate(PRICE_DATE)} 종가</span></div>'
             f'<dl class="kv">{kvh}</dl><button class="watch" type="button"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M12 5v14M5 12h14"/></svg>관심종목에 추가</button>'
             f'<p class="cv-fine">PER·PBR·배당수익률은 {kdate(PRICE_DATE, False)} 종가와 최근 네 분기 실적으로 계산했습니다.</p></aside></div></section>')
    labels = [q_label(x["q"]) for x in q]
    revs = [x["rev"] for x in q]
    ops = [x["op"] for x in q]
    opm = [x["op"] / x["rev"] * 100 for x in q]
    INK = "#141414"
    common = dict(w=340, h=210, font="'Newsreader',serif", fsize=14, tsize=12.5, tick_fill="rgba(20,20,20,.62)", axis=INK, weight=400)
    ch1 = bars_svg(revs, labels, fill="rgba(20,20,20,.22)", fill_last=INK, highlight_last=True, **common)
    ch2 = bars_svg(ops, labels, fill="rgba(20,20,20,.22)", fill_last=INK, highlight_last=True, **common)
    ch3 = line_svg(opm, labels, w=340, h=210, stroke=INK, dot=INK, font="'Newsreader',serif", fsize=14, tsize=12.5,
                   weight=400, fmt=lambda x: f"{x:.1f}%", zero=True)
    fig = (f'<section class="figure"><h2 class="fig-h">영업이익률, 다섯 분기 만에 {opm[0]:.1f}%에서 {opm[-1]:.1f}%로</h2>'
           f'<p class="fig-d">분기 실적 · 연결 기준 · {q[0]["q"][:4]}년 {q[0]["q"][-1]}분기 ~ {q[-1]["q"][:4]}년 {q[-1]["q"][-1]}분기</p>'
           f'<div class="smalls"><div><h4>매출<span>{money(revs[-1])}</span></h4>{ch1}</div><div><h4>영업이익<span>{money(ops[-1])}</span></h4>{ch2}</div>'
           f'<div><h4>영업이익률<span>{opm[-1]:.1f}%</span></h4>{ch3}</div></div>'
           f'<p class="fig-src">자료: 금융감독원 전자공시(DART) 확정치 · 연결 재무제표 · 영업이익률은 KOSAI 계산</p></section>')
    # 본문
    secs = [("s1", "사업 구조", "business"), ("s2", "실적", "earnings"), ("s3", "산업", "industry"), ("s4", "전망", "outlook"),
            ("s5", "밸류에이션", "valuation_comment")]
    toc_items = [(sid, name) for sid, name, _ in secs] + [("s6", "강세와 약세"), ("s7", "리스크"), ("s8", "체크포인트"), ("s9", "종합 의견"), ("s10", "출처")]
    toc = '<nav class="toc"><b>차례</b>' + "".join(
        f'<a href="#{sid}"><span>{i + 1:02d}</span>{esc(n)}</a>' for i, (sid, n) in enumerate(toc_items)) + "</nav>"
    body = ""
    for i, (sid, name, key) in enumerate(secs):
        txt = r[key]["ko"]
        ps = chunk(txt, 170)
        digits = sum(ch.isdigit() for ch in ps[0]) / max(1, len(ps[0]))
        first = f'<p class="lede">{esc(ps[0])}</p>' if digits < 0.06 else f"<p>{esc(ps[0])}</p>"
        inner = first + "".join(f"<p>{esc(p)}</p>" for p in ps[1:])
        if key == "earnings":
            qrows = "".join(f'<tr><td>{x["q"][:4]}년 {x["q"][-1]}분기</td><td>{money(x["rev"])}</td><td>{money(x["op"])}</td>'
                            f'<td>{x["op"] / x["rev"] * 100:.1f}%</td></tr>' for x in q)
            arows = "".join(f'<tr><td>{a["year"]}</td><td>{money(a["rev"])}</td><td>{money(a["op"])}</td><td>{money(a["np_owner"])}</td>'
                            f'<td>{a["opm"]:.1f}%</td><td>{a["roe"]:.1f}%</td></tr>' for a in ann)
            inner += (f'<table class="tbl"><caption>분기 실적<span>연결 · 원</span></caption><thead><tr><th>분기</th><th>매출</th><th>영업이익</th><th>영업이익률</th></tr></thead><tbody>{qrows}</tbody></table>'
                      f'<table class="tbl"><caption>연간 실적<span>연결 · 원 · 순이익은 지배주주</span></caption><thead><tr><th>연도</th><th>매출</th><th>영업이익</th><th>순이익</th><th>영업이익률</th><th>ROE</th></tr></thead><tbody>{arows}</tbody></table>')
        body += f'<section id="{sid}"><div class="sn">{i + 1:02d}</div><h2>{esc(name)}</h2>{inner}</section>'
    bull = "".join(f'<div class="item"><h4>{esc(x["title"]["ko"])}</h4>{paras(x["body"]["ko"], 150)}</div>' for x in r["bull"])
    bear = "".join(f'<div class="item"><h4>{esc(x["title"]["ko"])}</h4>{paras(x["body"]["ko"], 150)}</div>' for x in r["bear"])
    body += (f'<section id="s6"><div class="sn">06</div><h2>강세와 약세</h2><div class="bb"><div><h3><i style="background:var(--up)"></i>강세 요인 {len(r["bull"])}</h3>{bull}</div>'
             f'<div><h3><i style="background:var(--down)"></i>약세 요인 {len(r["bear"])}</h3>{bear}</div></div></section>')
    risks = "".join(f'<div class="risk"><b>{esc(x["cat"]["ko"])}</b><p>{esc(x["body"]["ko"])}</p></div>' for x in r["risks"])
    body += f'<section id="s7"><div class="sn">07</div><h2>리스크</h2>{risks}</section>'
    cps = "".join(f'<div class="cp"><b>{esc(x["when"]["ko"])}</b><p>{esc(x["what"]["ko"])}</p></div>' for x in r["checkpoints"])
    body += f'<section id="s8"><div class="sn">08</div><h2>다음 체크포인트</h2>{cps}</section>'
    vparts = chunk(r["verdict"]["body"]["ko"], 170)
    body += (f'<section id="s9" class="verdict"><div class="sn">09</div><h2>종합 의견</h2><blockquote class="pq">{esc(vparts[0])}</blockquote>'
             + "".join(f"<p>{esc(p)}</p>" for p in vparts[1:]) + "</section>")
    srcs = "".join(f"<li>{esc(u.split('//')[-1].split('/')[0])}</li>" for u in (r.get("sources") or []))
    body += (f'<section id="s10"><div class="sn">10</div><h2>출처</h2><ol class="srcs">{srcs}</ol>'
             f'<p class="disc">이 리포트는 AI가 공시·재무 데이터와 보도를 분석해 작성한 정보이며 투자 권유가 아닙니다. 투자 판단과 책임은 투자자 본인에게 있습니다.</p></section>')
    toc_js = ("<script>(function(){var a=[].slice.call(document.querySelectorAll('.toc a'));var m={};a.forEach(function(x){m[x.getAttribute('href').slice(1)]=x});"
              "var o=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){a.forEach(function(x){x.classList.remove('on')});"
              "var t=m[e.target.id];if(t)t.classList.add('on')}})},{rootMargin:'-30% 0px -60% 0px'});"
              "if(a[0])a[0].classList.add('on');document.querySelectorAll('.text section[id]').forEach(function(s){o.observe(s)});var f=document.getElementById('s1');"
              "addEventListener('scroll',function(){if(f&&scrollY<f.offsetTop-innerHeight*.5){a.forEach(function(x){x.classList.remove('on')});a[0].classList.add('on')}},{passive:true})})();</script>")
    page = (head(f"{s['name']} — {title} · KOSAI 시안 A") + masthead(b, active="리포트", big=False)
            + f'<main class="wrap">{cover}{fig}<div class="rbody">{toc}<article class="text">{body}</article></div></main>'
            + colophon() + toc_js + "</body></html>")
    return page
