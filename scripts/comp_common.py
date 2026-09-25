"""디자인 시안(comp) 공통 부품 — 머리(head)·토큰·바탕 CSS·헤더·푸터·공통 스크립트.

preview/ 의 시안 페이지들(build_stock_comp.py · build_home_comp.py …)이 같은 것을 쓴다.
한 곳을 고치면 모든 시안이 같이 바뀐다. 실사이트에 옮길 때는 patch_header.py / patch_biz_footer.py 가 맡는다.
"""


IND_JS = '''
<script>
/* 활성 표시선 — 컨테이너마다 선 하나를 두고, 활성 항목(.on)의 자리로 미끄러뜨린다.
   axis 'x' = 밑줄, 'y' = 왼쪽 세로선. sel 로 활성 항목 선택자를 바꿀 수 있다(기본 .on).
   첫 자리는 그냥 놓고, 그 뒤부터 element.animate() 로 이전 자리에서 새 자리로 움직인다.
   CSS transition 을 안 쓰는 이유: 휴대폰 목차 띠가 헤더 안으로 옮겨 붙는 프레임에 항목이 같이 바뀌면
   방금 옮겨진 요소라 transition 이 시작되지 않는다. animate() 는 DOM 이동과 무관하게 움직인다.
   window.kosIndMs 로 길이를 바꿀 수 있다(시험용). 움직임 줄이기 설정이면 바로 놓는다. */
window.kosInd=function(box,axis,sel){
  if(!box)return function(){};
  if(box.__ind)return box.__ind;
  var ind=document.createElement('span');ind.className='ind '+(axis==='y'?'ind-v':'ind-h');ind.setAttribute('aria-hidden','true');box.appendChild(ind);
  var last=null,placed=false,anim=null,rm=window.matchMedia?matchMedia('(prefers-reduced-motion:reduce)'):null;
  function move(force){
    var a=box.querySelector(sel||'.on');
    if(!a){ind.style.opacity='0';last=null;return}
    if(a===last&&!force)return;
    var b=box.getBoundingClientRect(),r=a.getBoundingClientRect();
    if(!r.width&&!r.height)return;
    last=a;
    var x=r.left-b.left-box.clientLeft+box.scrollLeft,y=r.top-b.top-box.clientTop+box.scrollTop;
    var to={transform:'translate('+x+'px,'+(axis==='y'?y:y+r.height-2)+'px)'};
    if(axis==='y')to.height=r.height+'px';else to.width=r.width+'px';
    var from=null;
    if(placed&&ind.animate&&!(rm&&rm.matches)){var cs=getComputedStyle(ind);from={transform:cs.transform};if(axis==='y')from.height=cs.height;else from.width=cs.width;if(anim){anim.cancel();anim=null}}
    ind.style.opacity='';ind.style.transform=to.transform;if(axis==='y')ind.style.height=to.height;else ind.style.width=to.width;
    if(from){anim=ind.animate([from,to],{duration:window.kosIndMs||300,easing:'cubic-bezier(.2,.8,.2,1)'});anim.onfinish=function(){anim=null}}
    placed=true;
  }
  addEventListener('resize',function(){move(true)});
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){move(true)});
  box.__ind=move;move();return move;
};
</script>'''

def head(title, robots='noindex,nofollow', extra=''):
    """머리. 시안은 noindex(기본). 실제 종목 페이지 생성기는 robots='index,follow' 와 extra(설명·canonical·OG·JSON-LD)를 준다."""
    robots_tag = f'<meta name="robots" content="{robots}">\n' if robots else ''
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{robots_tag}<meta name="theme-color" content="#f9f8f6">
<title>{title}</title>
{extra}<link rel="icon" href="/assets/favicon.png?v=k2">
<script>(function(){{var t='light';try{{t=localStorage.getItem('kos-theme')||'light'}}catch(e){{}}document.documentElement.setAttribute('data-theme',t);}})();</script>''' + IND_JS


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
[hidden]{display:none!important} /* hidden 속성이 .pager{display:flex} 같은 클래스 규칙에 밀리지 않게 */
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
@media (max-width:820px){.links,.login,.acct{display:none} .menu{display:inline-flex}}
/* 휴대폰 메뉴 — ☰ 를 누르면 헤더 아래를 페이지색 한 장이 다 덮는다. 큰 글자 다섯 · 계정 · 맨 아래 작은 링크.
   (9/26 사장: 헤더에서 내려오던 목록이 안 예쁘다 — 그건 기능만 있던 자리였다.) nav 바깥에 둔다: .nav.scrolled 의
   backdrop-filter 가 fixed 의 기준이 되어 안에 두면 내린 뒤 여는 순간 높이가 0 이 된다. */
.menu .x{display:none} .nav.menu-open .menu .ham{display:none} .nav.menu-open .menu .x{display:block}
.mmenu{display:none;position:fixed;top:60px;left:0;right:0;bottom:0;z-index:49;background:var(--bg);flex-direction:column;box-sizing:border-box;padding:22px var(--pad) max(28px,env(safe-area-inset-bottom));overflow:auto;overscroll-behavior:contain;-webkit-overflow-scrolling:touch}
@media (max-width:820px){.mmenu.open{display:flex;animation:mmIn .18s ease-out}} @keyframes mmIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}} @media (prefers-reduced-motion:reduce){.mmenu.open{animation:none}}
.mm-links{display:flex;flex-direction:column} .mm-links a{display:block;padding:10px 0;font:600 28px/36px var(--font);letter-spacing:-.02em;color:var(--ink-72);text-decoration:none} .mm-links a.on{color:var(--ink);font-weight:700}
.mmenu .sep{height:1px;background:var(--hair);margin:20px 0 22px}
.mm-auth{display:flex;flex-wrap:wrap;align-items:center;gap:12px 24px} .mm-auth a,.mm-auth button{border:0;background:none;padding:0;font:600 16px/24px var(--font);color:var(--ink);text-decoration:none;cursor:pointer}
.mm-foot{margin-top:auto;padding-top:32px;display:flex;flex-wrap:wrap;gap:6px 18px} .mm-foot a{font:400 13px/20px var(--font);color:var(--ink-55);text-decoration:none}
/* 계정(로그인 상태) — 이메일 첫 글자 동그라미와 작은 메뉴. 시안은 ?user=이메일 로 켠다 */
.acct{position:relative;display:none;align-items:center} .acct.show{display:inline-flex} .right.user .login{display:none}
.avatar{width:30px;height:30px;border-radius:50%;background:var(--ink);color:var(--bg);font:600 13px/1 var(--font);display:inline-flex;align-items:center;justify-content:center;border:0;cursor:pointer;padding:0;margin:0 4px}
.acct-menu{display:none;position:absolute;right:0;top:calc(100% + 10px);min-width:220px;background:var(--surface);border:1px solid var(--hair);border-radius:12px;padding:6px 0;box-shadow:0 8px 24px rgba(20,20,20,.08);z-index:60}
.acct.open .acct-menu{display:block} .acct-menu .em{padding:8px 16px 10px;font:400 12px/16px var(--font);color:var(--ink-55);border-bottom:1px solid var(--hair);margin-bottom:4px;word-break:break-all}
.acct-menu a,.acct-menu button{display:block;width:100%;box-sizing:border-box;text-align:left;border:0;background:none;padding:9px 16px;font:500 14px/20px var(--font);color:var(--ink-72);cursor:pointer;text-decoration:none} .acct-menu a:hover,.acct-menu button:hover{background:var(--surface-2);color:var(--ink)}
/* 단추 */
/* 활성 표시선(kosInd) — 목차 세로선·밑줄 탭·쪽 번호가 쓴다. 움직임은 IND_JS 의 animate() */
.ind{position:absolute;left:0;top:0;background:var(--ink);pointer-events:none;will-change:transform} .ind-v{width:2px} .ind-h{height:2px}
.btn{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 18px;border-radius:999px;border:0;font:600 14px/1 var(--font);cursor:pointer;transition:background-color .12s,color .12s} .btn.ico{padding-left:14px}
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

# 미리보기끼리 이어지게 — 시안은 kosai.kr/preview/ 에 있어 실사이트 주소(/Reports.html)로 가면 옛 디자인이 뜬다.
# 9/26 사장: 시안에서 로그인해도 설정으로 못 갔다(메뉴가 실사이트 /Settings.html 로 보냈다). 실사이트로 옮기는 날 PREVIEW = False.
PREVIEW = True
LIVE2PREVIEW = {'/': '/preview/home.html', '/Home.html': '/preview/home.html', '/Reports.html': '/preview/reports.html', '/industry.html': '/preview/industry.html',
                '/Watchlist.html': '/preview/watchlist.html', '/brief.html': '/preview/brief.html', '/About.html': '/preview/about.html', '/Contact.html': '/preview/contact.html',
                '/Feedback.html': '/preview/feedback.html', '/Terms.html': '/preview/terms.html', '/Privacy.html': '/preview/privacy.html', '/Login.html': '/preview/login.html',
                '/Signup.html': '/preview/signup.html', '/Settings.html': '/preview/settings.html'}


def links(html):
    """헤더·푸터·메뉴의 실사이트 주소를 미리보기 주소로. PREVIEW 가 아니면 그대로."""
    if not PREVIEW:
        return html
    for live, prev in LIVE2PREVIEW.items():
        html = html.replace(f'href="{live}"', f'href="{prev}"')
    return html


def nav(active):
    lk = ''.join(f'<a href="{h}" class="on">{t}</a>' if t == active else f'<a href="{h}">{t}</a>' for h, t in PAGES)
    return links(f'''<div id="kosEdgeTop" aria-hidden="true"></div><div id="kosEdgeBot" aria-hidden="true"></div>
<nav class="nav" id="nav"><div class="nav-in">
  <a class="brand" href="/"><img class="lt" src="/assets/kosai-wordmark-black.png" alt="KOSAI"><img class="dk" src="/assets/kosai-wordmark-white.png" alt="KOSAI"></a>
  <div class="links">{lk}</div>
  <div class="right" id="navRight"><a class="login" href="/Login.html">로그인</a><div class="acct" id="acct"></div>
    <button class="ib" id="themeBtn" aria-label="테마 전환"><svg viewBox="0 0 24 24" id="themeIcon"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    <button class="ib menu" id="menuBtn" aria-label="메뉴" aria-expanded="false" aria-controls="mmenu"><svg class="ham" viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg><svg class="x" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>
</div>
</nav>
<div class="mmenu" id="mmenu"><div class="mm-links">{lk}</div><div class="sep"></div><div class="mm-auth" id="mauth"><a href="/Login.html">로그인</a><a href="/Signup.html">회원가입</a></div>
<div class="mm-foot"><a href="/About.html">About</a><a href="/Contact.html">문의하기</a><a href="/Feedback.html">피드백</a><a href="/Terms.html">이용약관</a><a href="/Privacy.html">개인정보처리방침</a></div></div>''')


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
FOOTER = links(FOOTER)


# 헤더 띠(내리면 배경) · 테마 전환. 페이지가 스크롤마다 할 일이 있으면 window.kosOnScroll 에 넣는다.
JS = '''(function(){
  var nav=document.getElementById('nav'),tick=false;
  function upd(){tick=false;nav.classList.toggle('scrolled',window.scrollY>32);if(window.kosOnScroll)window.kosOnScroll()}
  addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(upd)}},{passive:true});upd();
  var sun='<path d="M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',moon='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();window.__kosPaintTheme=paint;
  document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{localStorage.setItem('kos-theme',t)}catch(e){}paint();});
  /* 휴대폰 메뉴 */
  var mb=document.getElementById('menuBtn'),mm=document.getElementById('mmenu');
  function setMenu(on){nav.classList.toggle('menu-open',on);mm.classList.toggle('open',on);mb.setAttribute('aria-expanded',on?'true':'false');document.documentElement.style.overflow=on?'hidden':''}  /* html 에 건다 — body 에 걸면 sticky 헤더가 사라진다(html 이 overflow-x:hidden 이라 body 가 스크롤 상자가 됨) */
  mb.addEventListener('click',function(){setMenu(!nav.classList.contains('menu-open'))});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&nav.classList.contains('menu-open'))setMenu(false)});
  window.matchMedia('(min-width:821px)').addEventListener('change',function(e){if(e.matches)setMenu(false)});
  /* 로그인 상태(시안) — 실사이트에서는 auth-state.js 가 Firebase 세션으로 같은 자리를 채운다. ?user=1 또는 ?user=이메일 */
  var qs=new URLSearchParams(location.search),u=qs.get('user');
  if(u){var email=(u==='1'||u==='')?'you@example.com':u,init=(email.charAt(0)||'K').toUpperCase(),acct=document.getElementById('acct');
    document.getElementById('navRight').classList.add('user');acct.classList.add('show');
    acct.innerHTML='<button type="button" class="avatar" id="acctBtn" aria-haspopup="true" aria-expanded="false" aria-label="계정 메뉴">'+init+'</button><div class="acct-menu" role="menu"><div class="em">'+email+'</div><a href="/Settings.html">설정</a><button type="button" id="signOut">로그아웃</button></div>';
    var ab=document.getElementById('acctBtn');ab.addEventListener('click',function(e){e.stopPropagation();var on=!acct.classList.contains('open');acct.classList.toggle('open',on);ab.setAttribute('aria-expanded',on?'true':'false')});
    document.addEventListener('click',function(e){if(!acct.contains(e.target)){acct.classList.remove('open');ab.setAttribute('aria-expanded','false')}});
    document.getElementById('mauth').innerHTML='<a href="/Settings.html">설정</a><button type="button" id="signOutM">로그아웃</button>';  /* 이메일·동그라미 줄은 뺐다(9/26 사장) — 헤더의 동그라미가 이미 로그인 상태를 말한다 */
    var out=function(){var url=new URL(location.href);url.searchParams.delete('user');location.href=url.pathname+(url.search||'')};document.getElementById('signOut').addEventListener('click',out);document.getElementById('signOutM').addEventListener('click',out);
    /* 미리보기끼리 오갈 때 로그인 상태(?user=)를 같이 들고 간다 — 시안에서만 */
    document.querySelectorAll('a[href^="/preview/"]').forEach(function(a){var h=a.getAttribute('href');if(h.indexOf('user=')<0)a.setAttribute('href',h+(h.indexOf('?')<0?'?':'&')+'user='+encodeURIComponent(email))});}
})();'''
JS = links(JS)


# 폼 — 밑줄 입력(검색과 같은 문법) · 구분 탭 · 체크 · 오류 글. 문의·피드백·로그인·회원가입·리포트 필터 창이 쓴다
FORM_CSS = """.fld{display:block;margin:0 0 26px} .fld>label,.fld .lbl{display:block;font:500 12px/16px var(--font);color:var(--ink-55);margin-bottom:4px} .fld .opt{font-weight:400;color:var(--ink-30)}
.fld input:not([type=checkbox]):not([type=radio]),.fld textarea{display:block;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent;font:400 16px/24px var(--font);color:var(--ink);padding:8px 0;outline:0;transition:border-color .15s;-webkit-appearance:none;appearance:none}
.fld input:focus,.fld textarea:focus{border-bottom-color:var(--ink)} .fld input::placeholder,.fld textarea::placeholder{color:var(--ink-30)} .fld textarea{min-height:120px;resize:vertical}
.fld.err input,.fld.err textarea{border-bottom-color:var(--up)} .fld .msg{display:none;margin-top:6px;font:400 12px/16px var(--font);color:var(--up)} .fld.err .msg{display:block}
.seg{position:relative;display:flex;gap:22px;border-bottom:1px solid var(--hair);overflow-x:auto;scrollbar-width:none} .seg::-webkit-scrollbar{display:none}
.seg button{flex:none;border:0;background:none;padding:0;font:500 13px/40px var(--font);color:var(--ink-55);cursor:pointer;transition:color .12s;white-space:nowrap} .seg button:hover{color:var(--ink)} .seg button.on{color:var(--ink);font-weight:600}
.check{display:flex;align-items:center;gap:12px;padding:9px 0;font:400 14px/20px var(--font);color:var(--ink);cursor:pointer;border-bottom:1px solid var(--hair);user-select:none} .check:last-child{border-bottom:0}
.check .box{width:18px;height:18px;border:1px solid var(--line);border-radius:5px;display:inline-flex;align-items:center;justify-content:center;flex:none;color:var(--bg);transition:background-color .12s,border-color .12s}
.check .box svg{width:12px;height:12px;fill:none;stroke:currentColor;stroke-width:3;stroke-linecap:round;stroke-linejoin:round;opacity:0} .check.on .box{background:var(--ink);border-color:var(--ink)} .check.on .box svg{opacity:1}
.check .count{margin-left:auto;font:400 12px/16px var(--font);color:var(--ink-55)}
.submit{display:flex;align-items:center;gap:20px;margin-top:8px;flex-wrap:wrap} .form-note{margin:0;font:400 13px/20px var(--font);color:var(--ink-55)}
.btn:disabled{opacity:.35;cursor:default}
/* 경고 글 — 상자·선 없이 붉은 글 한 줄, 단추 바로 위. 칸 하나에 매인 오류는 .fld .msg 로 그 칸 밑에 (2026-09-26 사장: "빨간 줄이 왜 있어?") */
.alert{display:none;margin:0 0 18px;font:400 13px/20px var(--font);color:var(--up)} .alert.show{display:block}
.tbtn{border:0;background:none;padding:0;font:500 13px/1 var(--font);color:var(--ink-72);cursor:pointer;transition:color .12s} .tbtn:hover{color:var(--ink)} .tbtn.danger{color:var(--up)}
.sent{padding:8px 0 24px;max-width:520px} .sent h2{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em} .sent p{margin:12px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}"""

# 글 — 약관·방침·소개처럼 읽는 페이지. 720px 단, 16/28
PROSE_CSS = """.prose{font:400 16px/28px var(--font);color:var(--ink)} .prose p{margin:0 0 18px} .prose p:last-child{margin-bottom:0}
.prose ul,.prose ol{margin:0 0 18px;padding-left:20px} .prose li{margin:0 0 6px} .prose li::marker{color:var(--ink-30)}
.prose h3,.prose h4{margin:26px 0 8px;font:600 16px/24px var(--font)} .prose b{font-weight:600}
.prose a{color:inherit;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .prose a:hover{text-decoration-color:var(--ink)}
.prose.lead{font-size:17px;color:var(--ink-72)}
.page-hero{padding:44px 0 0;max-width:720px} .page-hero .crumb{font:500 13px/20px var(--font);color:var(--ink-55)} .page-hero h1{margin:12px 0 0;font:700 44px/52px var(--font);letter-spacing:-.025em} .page-hero .sub{margin:16px 0 0;font:400 17px/28px var(--font);color:var(--ink-72)}
.page-hero .meta{margin:20px 0 0;font:400 13px/20px var(--font);color:var(--ink-55)}
.page-body{padding:40px 0 64px;max-width:720px}
.hr{height:1px;background:var(--hair);margin:8px 0 32px}
@media (max-width:820px){.page-hero{padding-top:20px} .page-hero h1{font-size:32px;line-height:38px} .page-hero .sub{font-size:15px;line-height:24px} .prose{font-size:15px;line-height:26px} .page-body{padding:28px 0 48px}}"""

# 계정 — 로그인·회원가입·약관 동의·계정 인증·설정. 400px 한 단
AUTH_CSS = """.auth{max-width:400px;padding:44px 0 72px} .auth .crumb{font:500 13px/20px var(--font);color:var(--ink-55)} .auth h1{margin:12px 0 0;font:700 32px/40px var(--font);letter-spacing:-.02em} .auth .sub{margin:12px 0 0;font:400 15px/24px var(--font);color:var(--ink-72)}
.social{display:flex;flex-direction:column;gap:10px;margin-top:32px}
.sbtn{display:flex;align-items:center;justify-content:center;gap:10px;height:44px;border:1px solid var(--line);border-radius:999px;background:transparent;font:600 14px/1 var(--font);color:var(--ink);cursor:pointer;transition:border-color .12s} .sbtn:hover{border-color:var(--ink)} .sbtn svg{width:18px;height:18px;flex:none}
.sbtn.kakao{background:#FEE500;border-color:#FEE500;color:#191600} .sbtn.naver{background:#03C75A;border-color:#03C75A;color:#fff}
.divider{display:flex;align-items:center;gap:12px;margin:26px 0 22px;font:400 12px/16px var(--font);color:var(--ink-55)} .divider::before,.divider::after{content:"";flex:1;height:1px;background:var(--hair)}
.auth .btn{width:100%;justify-content:center;height:44px;font-size:14px}
.auth .row-r{display:flex;justify-content:flex-end;margin:-14px 0 22px} .auth .row-r a{font:400 13px/20px var(--font);color:var(--ink-55);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .auth .row-r a:hover{color:var(--ink)}
.auth-foot{margin:24px 0 0;font:400 13px/20px var(--font);color:var(--ink-55);text-align:center} .auth-foot a{color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
.auth-note{margin:28px 0 0;padding-top:16px;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-55)}
.spin{width:22px;height:22px;border:2px solid var(--line);border-top-color:var(--ink);border-radius:50%;animation:kspin .8s linear infinite;margin:12px 0} @keyframes kspin{to{transform:rotate(360deg)}}
@media (prefers-reduced-motion:reduce){.spin{animation:none}}
@media (max-width:820px){.auth{padding-top:20px} .auth h1{font-size:28px;line-height:36px}}"""

# 본문 두 단 — 왼쪽 붙박이 목차 · 오른쪽 절. 절은 <section class="sec" id="sNN"> · 목차는 #toc a[href=#sNN] · 휴대폰 탭은 #chips a
TOC_CSS = '''.body{display:grid;grid-template-columns:200px minmax(0,1fr);gap:64px;padding:56px 0 0}
.toc{position:sticky;top:84px;align-self:start;display:flex;flex-direction:column;gap:2px}
.toc a{display:flex;gap:10px;align-items:baseline;padding:7px 0 7px 12px;border-left:2px solid transparent;font:500 13px/18px var(--font);color:var(--ink-55);transition:color .12s}
.toc a .n{font-weight:500;font-size:11px;color:var(--ink-30);min-width:18px}
.toc a:hover{color:var(--ink)} .toc a.on{color:var(--ink);font-weight:600} .toc a.on .n{color:var(--ink-55)}
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
  .sec{padding-bottom:64px}
}'''

# 헤더 안으로 옮겨 붙이기(pin) · 현재 절 표시(spy). 절을 나중에 그리는 페이지는 그린 뒤 window.kosTocInit() 을 다시 부른다.
TOC_JS = '''window.kosTocInit=function(){
  var nav=document.getElementById('nav'),mark=document.getElementById('chipsMark'),bar=document.getElementById('chipsBar'),mq=window.matchMedia('(max-width:820px)');
  if(!mark||!bar){window.kosOnScroll=null;window.__kosSpy=null;return}
  function pin(){var inNav=bar.parentNode===nav;
    if(!mq.matches){if(inNav){mark.after(bar);mark.style.height=''}return}
    var top=mark.getBoundingClientRect().top;
    if(!inNav&&top<=60){mark.style.height=(bar.offsetHeight+12)+'px';nav.appendChild(bar);void bar.offsetHeight}
    else if(inNav&&top>60){mark.after(bar);mark.style.height='';void bar.offsetHeight}}
  window.kosOnScroll=pin;
  var links=[].slice.call(document.querySelectorAll('#toc a, #chips a')),secs=[].slice.call(document.querySelectorAll('section.sec'));
  var mvT=window.kosInd(document.getElementById('toc'),'y'),mvC=window.kosInd(document.getElementById('chips'),'x');
  // 목차 클릭 — 앵커 이동은 해시마다 방문 기록을 쌓아 뒤로가기가 이전 목차로 간다. 스크롤만 하고 주소는 replaceState 로 바꾼다.
  links.forEach(function(a){if(a.__tocBound)return;a.__tocBound=true;a.addEventListener('click',function(e){var id=(a.getAttribute('href')||'').slice(1),s=id&&document.getElementById(id);if(!s)return;e.preventDefault();
    var pad=parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop)||0;window.scrollTo({top:s.getBoundingClientRect().top+window.scrollY-pad,behavior:'smooth'});
    try{history.replaceState(null,'','#'+id)}catch(x){}})});
  function spy(){if(!secs.length)return;var y=window.scrollY+window.innerHeight*.3,cur=secs[0];secs.forEach(function(s){if(s.offsetTop<=y)cur=s});links.forEach(function(a){var on=a.getAttribute('href')==='#'+cur.id;if(on&&!a.classList.contains('on')&&a.parentNode.id==='chips'){a.parentNode.scrollTo({left:Math.max(0,a.offsetLeft-20),behavior:'smooth'})}a.classList.toggle('on',on)});mvT();mvC()}
  if(!window.__kosSpyBound){addEventListener('scroll',function(){if(window.__kosSpy)requestAnimationFrame(window.__kosSpy)},{passive:true});window.__kosSpyBound=true}
  window.__kosSpy=spy;spy();pin();
};
window.kosTocInit();'''
