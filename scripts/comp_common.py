"""디자인 시안(comp) 공통 부품 — 머리(head)·토큰·바탕 CSS·헤더·푸터·공통 스크립트.

preview/ 의 시안 페이지들(build_stock_comp.py · build_home_comp.py …)이 같은 것을 쓴다.
한 곳을 고치면 모든 시안이 같이 바뀐다. 실사이트에 옮길 때는 patch_header.py / patch_biz_footer.py 가 맡는다.
"""


def head(title):
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#f9f8f6">
<title>{title}</title>
<link rel="icon" href="/assets/favicon.png?v=k2">
<script>(function(){{var t='light';try{{t=localStorage.getItem('kos-theme')||'light'}}catch(e){{}}document.documentElement.setAttribute('data-theme',t);}})();</script>'''


# 글꼴 · 색 토큰 · 바탕 · 헤더 · 푸터. 라이트 바탕 #f9f8f6 · 먹색 #141414 (CLAUDE.md 2026-09-24 결정).
CSS = '''@font-face{font-family:"Pretendard";font-weight:400;font-display:swap;src:url("/fonts/Pretendard-Regular.woff2") format("woff2")}
@font-face{font-family:"Pretendard";font-weight:500;font-display:swap;src:url("/fonts/Pretendard-Medium.woff2") format("woff2")}
@font-face{font-family:"Pretendard";font-weight:600;font-display:swap;src:url("/fonts/Pretendard-SemiBold.woff2") format("woff2")}
@font-face{font-family:"Pretendard";font-weight:700;font-display:swap;src:url("/fonts/Pretendard-Bold.woff2") format("woff2")}
:root{
  --bg:#f9f8f6; --surface:#ffffff; --surface-2:#f1efeb;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-55:rgba(20,20,20,.55); --ink-30:rgba(20,20,20,.30);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --up:#c8102e; --down:#1e5fbf; --up-bg:rgba(200,16,46,.08); --down-bg:rgba(30,95,191,.08);
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --nav-bar:rgba(249,248,246,.72);
  color-scheme:light;
}
:root[data-theme="dark"]{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-55:rgba(236,236,234,.55); --ink-30:rgba(236,236,234,.30);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14);
  --up:#f0655f; --down:#6f9cf5; --up-bg:rgba(240,101,95,.12); --down-bg:rgba(111,156,245,.12);
  --nav-bar:rgba(13,13,14,.72);
  color-scheme:dark;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:84px;overflow-x:clip}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;word-break:keep-all;overflow-wrap:anywhere}
a{color:inherit;text-decoration:none}
::selection{background:rgba(20,20,20,.14)} :root[data-theme="dark"] ::selection{background:rgba(255,255,255,.22)}
.wrap{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}
.up{color:var(--up)} .down{color:var(--down)} .flat{color:var(--ink-55)}
/* 헤더 — 사이트 규칙 그대로(60px · 맨 위 투명 · 내리면 띠) */
.nav{position:sticky;top:0;z-index:50;height:60px;display:flex;align-items:center;justify-content:space-between;padding:0;transition:background-color .2s,box-shadow .2s}
.nav.scrolled{background:var(--nav-bar);box-shadow:0 1px 0 var(--hair);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px)}
.nav-in{width:100%;max-width:var(--wrap);margin:0 auto;padding:0 var(--pad);display:flex;align-items:center;justify-content:space-between;position:relative}
.brand img{height:14px;display:block} .brand .dk{display:none} :root[data-theme="dark"] .brand .lt{display:none} :root[data-theme="dark"] .brand .dk{display:block}
.links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:28px}
.links a{font:500 14px/1 var(--font);color:var(--ink-72);transition:color .12s} .links a:hover,.links a.on{color:var(--ink)} .links a.on{font-weight:600}
.right{display:flex;align-items:center;gap:6px} .login{font:600 13px/1 var(--font);color:var(--ink-72);padding:8px 10px} .login:hover{color:var(--ink)}
.ib{width:38px;height:38px;border:0;background:transparent;color:var(--ink-72);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;border-radius:10px} .ib:hover{color:var(--ink)} .ib svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.menu{display:none}
@media (max-width:820px){.links,.login{display:none} .menu{display:inline-flex}}
/* 단추 */
.btn{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 18px 0 14px;border-radius:999px;border:0;font:600 14px/1 var(--font);cursor:pointer;transition:background-color .12s,color .12s}
.btn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}
.btn-ink{background:var(--ink);color:var(--bg)} .btn-ink:hover{opacity:.9}
.btn-soft{background:var(--surface-2);color:var(--ink)} .btn-soft:hover{background:var(--line)}
/* 절 제목 · 더보기 링크 */
.sec-h{display:flex;align-items:baseline;gap:14px;margin:0 0 22px}
.sec-h .num{font:600 13px/20px var(--font);color:var(--ink-30)}
.sec-h h2{margin:0;font:700 24px/32px var(--font);letter-spacing:-.02em}
.sec-h .more{margin-left:auto;display:inline-flex;align-items:center;gap:6px;font:500 14px/20px var(--font);color:var(--ink-72);white-space:nowrap} .sec-h .more:hover{color:var(--ink)}
.sec-h .more svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
/* 표 — 틀 없이 줄로만 */
.tbl-wrap{overflow-x:auto}
.tbl{width:100%;border-collapse:collapse}
.tbl caption{text-align:left;padding:0 0 10px} .tbl .cap{display:flex;justify-content:space-between;align-items:baseline;font:500 13px/20px var(--font);color:var(--ink-72)} .tbl .cap .u{font-weight:400;color:var(--ink-55)}
.tbl th,.tbl td{padding:11px 12px;font:400 14px/20px var(--font);text-align:right;white-space:nowrap;border-top:1px solid var(--hair)}
.tbl thead th{font:500 12px/16px var(--font);color:var(--ink-55);border-top:0;border-bottom:1px solid var(--line);padding-top:0}
.tbl th:first-child,.tbl td:first-child{text-align:left;padding-left:0;font-weight:500} .tbl th:last-child,.tbl td:last-child{padding-right:0}
.tbl tbody th{font-weight:500}
/* 푸터 */
.foot{margin-top:96px;border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand img{height:13px} .ftag{margin:14px 0 0;font:400 14px/22px var(--font);color:var(--ink-72);max-width:260px}
.fgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;max-width:560px;margin-top:32px}
.fcol{display:flex;flex-direction:column;gap:9px} .fcol h4{margin:0 0 4px;font:600 12px/16px var(--font);color:var(--ink-55)} .fcol a{font:400 14px/20px var(--font);color:var(--ink-72)} .fcol a:hover{color:var(--ink)}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-55)} .copy{margin-top:32px;font:400 12px/18px var(--font);color:var(--ink-55)}
/* 휴대폰 사파리 상태바·주소창 뒤 색 — 페이지색 띠 (CLAUDE.md 2026-09-24) */
#kosEdgeTop,#kosEdgeBot{display:none}
@media (hover:none) and (pointer:coarse){#kosEdgeTop,#kosEdgeBot{display:block;position:fixed;left:0;right:0;height:12px;z-index:60;pointer-events:none;opacity:.2;background:var(--bg)} #kosEdgeTop{top:0} #kosEdgeBot{bottom:0}}'''

# 휴대폰 공통 — 여백 20px · 헤더는 불투명 두 줄 구조(목차 띠가 들어올 수 있게) · 표는 옆으로 넘기고 첫 열 고정
MOBILE_CSS = '''@media (max-width:820px){
  :root{--pad:20px}
  .nav{display:block;height:60px;padding:0} .nav-in{height:60px;padding:0 var(--pad)}
  .nav,.nav.scrolled{background:var(--bg);-webkit-backdrop-filter:none;backdrop-filter:none}
  .sec-h h2{font-size:22px;line-height:28px}
  .tbl th,.tbl td{padding:10px 10px;font-size:13px} .tbl th:first-child,.tbl td:first-child{position:sticky;left:0;background:var(--bg)}
}'''

PAGES = [('/Home.html', '홈'), ('/Reports.html', '리포트'), ('/industry.html', '업종 분석'), ('/Watchlist.html', '관심종목'), ('/brief.html', '모닝브리핑')]


def nav(active):
    links = ''.join(f'<a href="{h}" class="on">{t}</a>' if t == active else f'<a href="{h}">{t}</a>' for h, t in PAGES)
    return f'''<div id="kosEdgeTop" aria-hidden="true"></div><div id="kosEdgeBot" aria-hidden="true"></div>
<nav class="nav" id="nav"><div class="nav-in">
  <a class="brand" href="/"><img class="lt" src="/assets/kosai-wordmark-black.png" alt="KOSAI"><img class="dk" src="/assets/kosai-wordmark-white.png" alt="KOSAI"></a>
  <div class="links">{links}</div>
  <div class="right"><a class="login" href="/Login.html">로그인</a>
    <button class="ib" id="themeBtn" aria-label="테마 전환"><svg viewBox="0 0 24 24" id="themeIcon"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    <button class="ib menu" aria-label="메뉴"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button></div>
</div></nav>'''


FOOTER = '''<footer class="foot"><div class="wrap">
  <a class="brand" href="/"><img class="lt" src="/assets/kosai-wordmark-black.png" alt="KOSAI"><img class="dk" src="/assets/kosai-wordmark-white.png" alt="KOSAI"></a>
  <p class="ftag">한국 상장사를 위한 AI 투자 리서치. 데이터와 분석을 한 페이지에.</p>
  <div class="fgrid">
    <div class="fcol"><h4>서비스</h4><a href="/Home.html">홈</a><a href="/Reports.html">리포트</a><a href="/industry.html">업종 분석</a><a href="/Watchlist.html">관심종목</a><a href="/brief.html">모닝브리핑</a></div>
    <div class="fcol"><h4>회사</h4><a href="/About.html">About</a><a href="/Contact.html">문의하기</a><a href="/Feedback.html">피드백</a></div>
    <div class="fcol"><h4>정책</h4><a href="/Terms.html">이용약관</a><a href="/Privacy.html">개인정보처리방침</a></div>
  </div>
  <div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>
  <div class="copy">© 2026 KOSAI — All rights reserved.</div>
</div></footer>'''


# 헤더 띠(내리면 배경) · 테마 전환. 페이지가 스크롤마다 할 일이 있으면 window.kosOnScroll 에 넣는다.
JS = '''(function(){
  var nav=document.getElementById('nav'),tick=false;
  function upd(){tick=false;nav.classList.toggle('scrolled',window.scrollY>32);if(window.kosOnScroll)window.kosOnScroll()}
  addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(upd)}},{passive:true});upd();
  var sun='<path d="M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',moon='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();
  document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{localStorage.setItem('kos-theme',t)}catch(e){}paint();});
})();'''


# 본문 두 단 — 왼쪽 붙박이 목차 · 오른쪽 절. 절은 <section class="sec" id="sNN"> · 목차는 #toc a[href=#sNN] · 휴대폰 탭은 #chips a
TOC_CSS = '''.body{display:grid;grid-template-columns:200px minmax(0,1fr);gap:64px;padding:56px 0 0}
.toc{position:sticky;top:84px;align-self:start;display:flex;flex-direction:column;gap:2px}
.toc a{display:flex;gap:10px;align-items:baseline;padding:7px 0 7px 12px;border-left:2px solid transparent;font:500 13px/18px var(--font);color:var(--ink-55);transition:color .12s}
.toc a .n{font-weight:500;font-size:11px;color:var(--ink-30);min-width:18px}
.toc a:hover{color:var(--ink)} .toc a.on{color:var(--ink);border-left-color:var(--ink);font-weight:600} .toc a.on .n{color:var(--ink-55)}
.chips-bar,.chips-mark{display:none}
.content{min-width:0}
.sec{max-width:720px;padding:0 0 88px} .sec.wide{max-width:880px}'''

# 휴대폰: 목차는 헤더 아래 밑줄 탭. 표식(#chipsMark)이 헤더 아래로 지나가면 탭 띠를 헤더 안으로 옮겨 붙인다(TOC_JS).
TOC_MOBILE_CSS = '''@media (max-width:820px){
  .body{display:block;padding-top:8px} .toc{display:none}
  .chips-mark{display:block;height:0}
  .chips-bar{display:block;background:var(--bg);margin:0 calc(-1 * var(--pad)) 12px;border-bottom:1px solid var(--hair)}
  .nav .chips-bar{position:absolute;top:60px;left:0;right:0;margin:0}
  html{scroll-padding-top:116px}
  .chips{position:relative;display:flex;gap:22px;height:44px;padding:0 var(--pad);overflow-x:auto;overflow-y:hidden;scrollbar-width:none;touch-action:pan-x;overscroll-behavior-x:contain} .chips::-webkit-scrollbar{display:none}
  .chips a{flex:none;position:relative;font:500 13px/44px var(--font);color:var(--ink-55);transition:color .12s} .chips a.on{color:var(--ink);font-weight:600}
  .chips a.on::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--ink)}
  .sec{padding-bottom:64px}
}'''

# 헤더 안으로 옮겨 붙이기(pin) · 현재 절 표시(spy). 절을 나중에 그리는 페이지는 그린 뒤 window.kosTocInit() 을 다시 부른다.
TOC_JS = '''window.kosTocInit=function(){
  var nav=document.getElementById('nav'),mark=document.getElementById('chipsMark'),bar=document.getElementById('chipsBar'),mq=window.matchMedia('(max-width:820px)');
  if(!mark||!bar){window.kosOnScroll=null;window.__kosSpy=null;return}
  function pin(){var inNav=bar.parentNode===nav;
    if(!mq.matches){if(inNav){mark.after(bar);mark.style.height=''}return}
    var top=mark.getBoundingClientRect().top;
    if(!inNav&&top<=60){mark.style.height=(bar.offsetHeight+12)+'px';nav.appendChild(bar)}
    else if(inNav&&top>60){mark.after(bar);mark.style.height=''}}
  window.kosOnScroll=pin;
  var links=[].slice.call(document.querySelectorAll('#toc a, #chips a')),secs=[].slice.call(document.querySelectorAll('section.sec'));
  function spy(){if(!secs.length)return;var y=window.scrollY+window.innerHeight*.3,cur=secs[0];secs.forEach(function(s){if(s.offsetTop<=y)cur=s});links.forEach(function(a){var on=a.getAttribute('href')==='#'+cur.id;if(on&&!a.classList.contains('on')&&a.parentNode.id==='chips'){a.parentNode.scrollTo({left:Math.max(0,a.offsetLeft-20),behavior:'smooth'})}a.classList.toggle('on',on)})}
  if(!window.__kosSpyBound){addEventListener('scroll',function(){if(window.__kosSpy)requestAnimationFrame(window.__kosSpy)},{passive:true});window.__kosSpyBound=true}
  window.__kosSpy=spy;spy();pin();
};
window.kosTocInit();'''
