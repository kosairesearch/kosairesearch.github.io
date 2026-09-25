/* 관심종목 단추 — 실사이트에서는 KOSWatch(Firestore)가 켜고 끈다. 여기서는 화면 안에서만 */
(function(){var b=document.getElementById('watchBtn'),t=document.getElementById('watchTxt');if(!b)return;b.addEventListener('click',function(){var on=!b.classList.contains('on');b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false');t.textContent=on?'관심종목 추가됨':'관심종목 추가'})})();
window.kosTocInit=function(){
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
window.kosTocInit();
(function(){
  var nav=document.getElementById('nav'),tick=false;
  function upd(){tick=false;nav.classList.toggle('scrolled',window.scrollY>32);if(window.kosOnScroll)window.kosOnScroll()}
  addEventListener('scroll',function(){if(!tick){tick=true;requestAnimationFrame(upd)}},{passive:true});upd();
  var sun='<path d="M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',moon='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();window.__kosPaintTheme=paint;
  document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{localStorage.setItem('kos-theme',t)}catch(e){}paint();});
  /* 휴대폰 메뉴 */
  var mb=document.getElementById('menuBtn');
  function setMenu(on){nav.classList.toggle('menu-open',on);mb.setAttribute('aria-expanded',on?'true':'false')}
  mb.addEventListener('click',function(){setMenu(!nav.classList.contains('menu-open'))});
  document.getElementById('mback').addEventListener('click',function(){setMenu(false)});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')setMenu(false)});
  window.matchMedia('(min-width:821px)').addEventListener('change',function(e){if(e.matches)setMenu(false)});
  /* 로그인 상태(시안) — 실사이트에서는 auth-state.js 가 Firebase 세션으로 같은 자리를 채운다. ?user=1 또는 ?user=이메일 */
  var qs=new URLSearchParams(location.search),u=qs.get('user');
  if(u){var email=(u==='1'||u==='')?'you@example.com':u,init=(email.charAt(0)||'K').toUpperCase(),acct=document.getElementById('acct');
    document.getElementById('navRight').classList.add('user');acct.classList.add('show');
    acct.innerHTML='<button type="button" class="avatar" id="acctBtn" aria-haspopup="true" aria-expanded="false" aria-label="계정 메뉴">'+init+'</button><div class="acct-menu" role="menu"><div class="em">'+email+'</div><a href="/Settings.html">설정</a><button type="button" id="signOut">로그아웃</button></div>';
    var ab=document.getElementById('acctBtn');ab.addEventListener('click',function(e){e.stopPropagation();var on=!acct.classList.contains('open');acct.classList.toggle('open',on);ab.setAttribute('aria-expanded',on?'true':'false')});
    document.addEventListener('click',function(e){if(!acct.contains(e.target)){acct.classList.remove('open');ab.setAttribute('aria-expanded','false')}});
    document.getElementById('mauth').innerHTML='<div class="em">'+email+'</div><a href="/Settings.html">설정</a><button type="button" id="signOutM">로그아웃</button>';
    var out=function(){var url=new URL(location.href);url.searchParams.delete('user');location.href=url.pathname+(url.search||'')};document.getElementById('signOut').addEventListener('click',out);document.getElementById('signOutM').addEventListener('click',out);}
})();