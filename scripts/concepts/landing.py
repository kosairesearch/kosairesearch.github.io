"""랜딩 시안 5판 — 스테이징 옷 그대로, 절마다 '큰 제목 · 짧은 서브 · 그림' 하나씩.

    python3 scripts/concepts/landing.py      # → preview/concepts/landing/index.html · landing.css

  · 3판은 사장 피드백(2026-09-27)대로 줄였다 — 리포트 카드 · 최근 목록 · 업종 칸 · 요금 · 질문 · 브리핑 카드를 빼고,
    멤버십은 머리·꼬리 메뉴에서도 뺐다(가격 문구는 유료화 법정 절차 뒤 — CLAUDE.md).
  · 5판(같은 날 사장 "AI가 씁니다는 싸구려 · 이름 띠는 구리다 · 판단은 읽는 분의 몫도 구리다 · 대기업 말투로 ·
    강세·약세를 왜 바로 보여 주나 · 플리토 출처는 왜 · 특정 종목 예시는 왜"):
      - 첫 화면은 이름 띠 대신 행성 하나 — 뒤에서 올라오는 빛에 윤곽이 드러난다(점의 자리와 수는 ORB_JS 의 grid).
      - 문구는 대기업 말투(끝까지 쓴 합쇼체 서브, 꾸밈 없는 사실). 첫 화면 서브에 'AI' 없음.
      - 둘째 절은 얻는 것(한 편에 담은 기업 분석)으로 열고 강세·약세 요인은 그 근거로만.
      - 특정 종목은 어디에도 없다 — 예시 링크 · 칩 · 검색창 안내의 '예: 삼성전자'까지 뺐다.
  · 절 순서: 첫 화면 → 숫자 하나(증권사 리포트가 없는 상장사 — 첫 화면 제목의 증거) → 리포트 → 태도(가운데 선언) → 원칙 셋 → 갱신 →
    업종 → 모닝브리핑(어두운 띠) → 마지막. 절마다 앞 절이 남긴 질문에 답한다(보고서 5부). 2026-10-01 사장 승인으로 원칙을 갱신 앞으로,
    업종을 브리핑 앞으로 옮겼다 — 이음말이 '그리고'로만 이어지던 자리를 없앴다: 태도 → 그 근거(원칙) → 발행 뒤에도(갱신) → 업종으로
    넓히면 → 시장으로 넓히면(브리핑) → 다시 내 종목으로(검색).
  · 문구는 copy_text() 한 곳에 모았다. 제목은 명사형을 기본으로 절마다 모양을 바꾸고, 서브는 합쇼체. 해요체 평서문과
    쉼표로 가른 'A, B' 제목은 쓰지 않는다. 근거와 규칙은 reports/카피라이팅과 랜딩페이지 구성 이론 총정리.md 와 노트 16–20.
  · 그림·영상·3D 는 만들지 않는다. 들어갈 자리만 표시한다(종류 · 비율 · 한 줄 이름). 첫 화면의 행성은 그림이 아니라
    data/ 로 그린 캔버스다.
  · 숫자는 전부 data/ 에서 계산한다 — 손으로 적은 숫자·날짜 없음. 스테이징·실사이트 파일은 건드리지 않는다.
"""
import datetime
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from data import ROOT, BY, STOCKS, INDEX, esc, brief, now_date  # noqa: E402
from common import g  # noqa: E402

OUT = os.path.join(ROOT, "preview", "concepts", "landing")
ASSETS = "../../../assets"
FONTS = "../../../fonts"
BASE = datetime.date.fromisoformat(f"{now_date()[:4]}-{now_date()[4:6]}-{now_date()[6:8]}")   # 데이터의 '오늘'
# 범위는 '국내 상장'으로 묶는다(사장 2026-10-01 — 첫 화면 서브의 '코스피, 코스닥, 코넥스' 나열 대신). 세 시장이 다 들어가는 말이라
# 정확하다(상장 2,685 = 코스피 831 · 코스닥 1,747 · 코넥스 107). 시장 이름을 따로 쓸 때는 셋 다 쓴다 — 둘만 쓰면 틀린 말이 된다
SCOPE = "국내 상장"
ORB_SEED = 2680                                         # 첫 화면 구의 점 순서 — 고정 씨앗(빌드마다 같게)
# 증권사 리포트가 없는 상장사 — 우리 데이터가 아니라 바깥 통계라 출처 줄을 단다(사장 2026-10-01 "첫 화면 말고 스크롤했을 때").
# 한국IR협의회 기업리서치센터가 해마다 2월쯤 전년 집계를 낸다 — 그때 이 넷을 고친다. 2025년: 2,674곳 중 1,573곳(뉴스핌 2026-02-11 보도)
GAP = {"year": 2025, "none": 1573, "total": 2674, "src": "한국IR협의회 기업리서치센터"}

# 스크롤 등장 — .rv 가 화면 높이 90% 선 위로 들어오면 한 번 올라온다(CSS .rv-on .rv · 애플의 시작점 't - 90vh'). 같은 순간 함께 들어온 글끼리만
# 0.08초씩 차례를 두고(최대 0.4초), 이미 지나간 글(앵커·되돌아온 스크롤 자리)은 곧바로 보인다. 어디서든 실패하면 숨김을 풀어 글을 살린다
# 숫자 카운트(.cnt — 58.8% 하나만, 사장 2026-10-01): 나타나는 순간 0에서 최종값까지 1초, 올라오는 움직임과 같은 곡선.
# 원래 글에서 글자마다 시작 자리를 재어(Range — 커닝 · 자간 포함) 그 간격대로 칸을 고정하므로 세는 동안 줄이 흔들리지 않는다.
# 끝나도 원래 글로 되돌리지 않는다 — 되돌리면 사파리가 글자 간격을 다시 계산해 '%'가 끝에서 움직였다(사장 휴대폰 2026-10-01).
# 칸 폭은 em 이라 화면 크기가 바뀌어도 같이 커진다. 세기 시작하면 제목에 aria-label(최종값)을 달고 숫자 칸은 읽는 프로그램에서
# 숨긴다(칸이 한 글자씩 읽히지 않게). 지나친 숫자 · 움직임 줄임 · 글꼴을 받기 전에는 세지 않는다
RV_JS = (
    "(function(){var r=document.documentElement;if(!r.classList.contains('rv-on'))return;"
    "function bz(x){var lo=0,hi=1,t=x,u;for(var i=0;i<24;i++){t=(lo+hi)/2;u=1-t;if(3*u*u*t*.2+3*u*t*t*.2+t*t*t<x)lo=t;else hi=t}"
    "u=1-t;return 3*u*u*t*.7+3*u*t*t+t*t*t}"   # cubic-bezier(.2,.7,.2,1)
    r"function cnt(el,d){var s=el.textContent,m=s.match(/^(\d+)(?:\.(\d+))?(\D*)$/),tn=el.firstChild;"
    "if(!m||!tn||(document.fonts&&document.fonts.status!=='loaded'))return;"
    "var hd=el.parentNode,ip=m[1],fp=m[2]||'',to=parseFloat(ip+(fp?'.'+fp:'')),dp=fp.length,ch=s.split(''),h='',i,b,x=[],"
    "fs=parseFloat(getComputedStyle(el).fontSize),rg=document.createRange();"
    "for(i=0;i<ch.length;i++){rg.setStart(tn,i);rg.setEnd(tn,i+1);b=rg.getBoundingClientRect();x.push([b.left,b.width])}"
    "hd.setAttribute('aria-label',hd.textContent);el.setAttribute('aria-hidden','true');el.style.whiteSpace='nowrap';"
    "for(i=0;i<ch.length;i++)h+='<span>'+ch[i]+'</span>';el.innerHTML=h;var sp=el.children;"
    "for(i=0;i<sp.length;i++)sp[i].style.cssText='display:inline-block;text-align:center;width:'+((i<sp.length-1?x[i+1][0]-x[i][0]:x[i][1])/fs).toFixed(4)+'em';"
    "function show(v){var a=v.toFixed(dp).split('.'),n=ip.length,k;for(i=0;i<n;i++){k=a[0].length-n+i;sp[i].textContent=k>=0?a[0].charAt(k):''}"
    "for(i=0;i<dp;i++)sp[n+1+i].textContent=(a[1]||'').charAt(i)}"
    "show(0);var t0=null;function f(ts){if(t0===null)t0=ts+d*1000;var p=Math.max(0,Math.min(1,(ts-t0)/1000));"
    "if(p<1){show(to*bz(p));requestAnimationFrame(f)}else for(i=0;i<sp.length;i++)sp[i].textContent=ch[i]}"
    "requestAnimationFrame(f)}"
    "try{var io=new IntersectionObserver(function(es){var j=0;for(var k=0;k<es.length;k++){var e=es[k],t=e.target;"
    "if(e.isIntersecting){var d=Math.min(j++,5)*.08;t.style.setProperty('--d',d+'s');t.classList.add('in');io.unobserve(t);"
    "var c=t.querySelector('.cnt');if(c)cnt(c,d)}"
    "else if(e.boundingClientRect.top<0){t.classList.add('in');io.unobserve(t)}}},{rootMargin:'0px 0px -10% 0px'});"
    "var rv=document.querySelectorAll('.rv');for(var k=0;k<rv.length;k++)io.observe(rv[k])}catch(x){r.classList.remove('rv-on')}})();"
)

ORB_JS = r"""(function(){
var cv=document.getElementById('orb');if(!cv||!cv.getContext)return;
var D=JSON.parse(document.getElementById('orbData').textContent),N=D.n,RS=null,i;
/* 모양 — 축을 뒤로 0.3 눕혀 북극이 윗변 너머에 숨는다(경선은 그쪽으로 모이고, 위선은 지평선과 나란한 호가 된다).
   반지름은 PC 화면 폭의 0.64배(최대 1240), 휴대폰은 폭의 1.4배 */
var TL=-.3,ct=Math.cos(TL),st=Math.sin(TL);
var ctx=cv.getContext('2d'),P=null,NP=0,sp=document.createElement('canvas');sp.width=sp.height=32;
var sx=sp.getContext('2d'),g=sx.createRadialGradient(16,16,0,16,16,16);
g.addColorStop(0,'rgba(248,247,244,1)');g.addColorStop(.45,'rgba(248,247,244,.85)');g.addColorStop(1,'rgba(248,247,244,0)');sx.fillStyle=g;sx.fillRect(0,0,32,32);
var G=document.createElement('canvas'),gx=G.getContext('2d');
var root=document.documentElement,W=0,H=0,dpr=1,rad=0,cx=0,cy=0,SZ=1,PD=47,band='#141414',ang=.9,last=0,t0=0,on=false,rz=0,
    red=matchMedia('(prefers-reduced-motion: reduce)').matches,pt=0,pv=0;
function col(){band=getComputedStyle(root).getPropertyValue('--band').trim()||'#141414'}
function rgba(hx,a){var h=hx.replace('#','');if(h.length===3)h=h.replace(/(.)/g,'$1$1');var n=parseInt(h,16);return 'rgba('+(n>>16&255)+','+(n>>8&255)+','+(n&255)+','+a+')'}
/* 규칙적인 점 — 지구본의 경위선처럼 경선 M개와 위선 L개가 만나는 자리마다 점 하나. 경선은 360°를 같은 간격으로, 위선은
   화면에 보이는 위도 띠(lo~hi)를 같은 간격으로 나눈다. 경선이 극 쪽으로 모이고 위선이 둥글게 휘어 구의 입체가 드러난다.
   점의 수는 종목 수가 아니라 간격에서 나온다(사장 2026-10-01 "점 수를 종목 수만큼 넣을 필요는 없어 … 너무 촘촘해 … 점들 사이의
   간격이 완벽한 비율로"). 첫 화면에서 눈이 머무는 빛 띠의 가운데(정면에서 60° 기운 곳, z=.5)에서 이웃한 점이 가로·세로 모두
   시각도 0.9° 떨어지게 M 과 L 을 고른다.
   · 0.9° — 점 사이가 약 1°보다 좁으면 눈은 점을 하나하나 보지 않고 결(texture)로 뭉쳐 본다. 경계는 점 지름 0.25°에서 0.96°,
     0.58°에서 1.05°로 점이 작을수록 조금 좁다(Anobile 외 2015, J Vis 15(5):4). 여기 점은 지름 약 0.05°라 직선으로 늘려 잡아 0.9°.
   · 가로=세로 — 두 방향 간격이 1.5배 넘게 벌어지면 가까운 쪽으로 줄이 져 점이 아니라 선으로 읽힌다(Kubovy 외 1998, 근접성의 법칙).
     빛 띠에서 아래로 내려오면 간격이 조금씩 넓어지고 윤곽 쪽은 좁아진다 — 곡면이 멀어지며 결이 촘촘해지는 것(결의 기울기)이
     구의 입체를 만드니 그대로 둔다.
   · 각도를 픽셀로: 1° = PC 47px(CSS 기준 픽셀이 팔 길이에서 0.0213°) · 휴대폰 34px(웹을 볼 때 눈과 화면 32cm, Bababekova 외 2011) */
function grid(lo,hi){
  var band=hi-lo,gs=.9*PD,M=Math.max(24,Math.round(2*Math.PI*rad*Math.cos(Math.PI/3+TL)/gs)),L=Math.max(4,Math.round(band*rad*.5/gs)),k,j,n=0;
  NP=M*L;P=new Float32Array(NP*3);cv.setAttribute('data-grid',M+'x'+L);
  RS=new Uint8Array(NP);D.r.slice(0,Math.round(NP*D.r.length/N)).forEach(function(r){RS[r%NP]=1});
  for(k=0;k<L;k++){var ph=lo+(k+.5)*band/L,cp=Math.cos(ph),s1=Math.sin(ph);
    for(j=0;j<M;j++,n++){var th=2*Math.PI*j/M;P[n*3]=cp*Math.cos(th);P[n*3+1]=s1;P[n*3+2]=cp*Math.sin(th)}}
}
/* 빛 — 크기가 바뀔 때 한 번만 그려 둔다. 뒤에서 올라오는 새벽빛, 가장자리가 빛 속으로 풀리는 몸, 가장자리를 가운데로
   안팎으로 번지는 대기(선 없음 — 위쪽이 가장 밝고 옆으로 내려가며 옅어진다) */
function light(){
  G.width=cv.width;G.height=cv.height;gx.setTransform(dpr,0,0,dpr,0,0);gx.clearRect(0,0,W,H);
  var top=cy-rad,A=Math.PI*2;
  var b=gx.createRadialGradient(cx,top+rad*.06,0,cx,top+rad*.06,rad*.95);
  b.addColorStop(0,'rgba(255,255,255,.13)');b.addColorStop(.3,'rgba(255,255,255,.05)');b.addColorStop(1,'rgba(255,255,255,0)');
  gx.fillStyle=b;gx.fillRect(0,0,W,H);
  var re=rad*1.025,bd=gx.createRadialGradient(cx,cy,0,cx,cy,re);
  bd.addColorStop(0,rgba(band,1));bd.addColorStop(rad*.9/re,rgba(band,1));bd.addColorStop(1,rgba(band,0));
  gx.fillStyle=bd;gx.beginPath();gx.arc(cx,cy,re,0,A);gx.fill();
  var R=document.createElement('canvas');R.width=G.width;R.height=G.height;var rx=R.getContext('2d');rx.setTransform(dpr,0,0,dpr,0,0);
  var r0=rad*.82,r1=rad*1.3,a=rx.createRadialGradient(cx,cy,r0,cx,cy,r1);
  function at(r,al){a.addColorStop((r-r0)/(r1-r0),'rgba(246,245,242,'+al+')')}
  at(r0,0);at(rad*.93,.045);at(rad*.97,.11);at(rad,.19);at(rad*1.03,.13);at(rad*1.08,.06);at(rad*1.16,.022);at(r1,0);
  rx.fillStyle=a;rx.fillRect(0,0,W,H);
  rx.globalCompositeOperation='destination-in';
  var v=rx.createLinearGradient(0,top-rad*.08,0,top+rad*.85);
  v.addColorStop(0,'rgba(0,0,0,1)');v.addColorStop(.4,'rgba(0,0,0,.6)');v.addColorStop(1,'rgba(0,0,0,.18)');
  rx.fillStyle=v;rx.fillRect(0,0,W,H);
  gx.setTransform(1,0,0,1,0,0);gx.drawImage(R,0,0);
}
/* 한 장 — 빛을 깔고 점을 찍는다. 점은 가장자리에 가까울수록 빛 속으로 사라지고(경계를 만들지 않는다), 윤곽 쪽과 위쪽이 조금 더 밝다.
   최근 14일 안에 새로 쓴 리포트의 비율만큼 점이 천천히 밝아졌다 어두워진다 */
function draw(t){
  if(!t0)t0=t;var e=red?1:Math.min(1,(t-t0)/1800);e=1-Math.pow(1-e,3);
  var oy=(1-e)*50,c=cy+oy;
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,cv.width,cv.height);
  ctx.globalAlpha=e;ctx.drawImage(G,0,Math.round(oy*dpr));ctx.globalAlpha=1;ctx.setTransform(dpr,0,0,dpr,0,0);
  pv+=(pt-pv)*.05;var qq=ang+pv,ca=Math.cos(qq),sa=Math.sin(qq);
  for(i=0;i<NP;i++){
    var x=P[i*3],y=P[i*3+1],z=P[i*3+2],x1=x*ca-z*sa,z1=x*sa+z*ca,y2=y*ct-z1*st,z2=y*st+z1*ct;
    if(z2<=0)continue;var px=cx+x1*rad,py=c-y2*rad;if(py<-4||py>H+4||px<-4||px>W+4)continue;
    var f=1-z2,s=Math.min(1,z2/.32),fade=s*s*(3-2*s),al=Math.min(1,(.3+.45*f*f)*(.55+.45*(y2+1)/2)*fade*e*1.25);
    if(RS[i])al=Math.min(1,al+.3*(.5+.5*Math.sin(t*.0014+i*1.7))*fade*e);
    if(al<.01)continue;ctx.globalAlpha=al;ctx.drawImage(sp,px-SZ,py-SZ,SZ*2,SZ*2)
  }
  ctx.globalAlpha=1
}
function fit(){
  var bx=cv.getBoundingClientRect(),V=cv.parentNode.getBoundingClientRect().height;dpr=Math.min(window.devicePixelRatio||1,2);
  W=bx.width;H=bx.height;cv.width=Math.round(W*dpr);cv.height=Math.round(H*dpr);var EX=H-V,T;
  if(W>820){rad=Math.min(W*.64,1240);T=100;SZ=1.2;PD=47}else{rad=W*1.4;T=64;SZ=1.05;PD=34}
  cx=W/2;cy=EX+T+rad;
  /* 보이는 위도 — 캔버스 아래쪽(92%)에서 보이는 가장 낮은 위도부터, 꼭대기 너머로 넘어가는 위도까지 */
  var vmin=Math.max(-1,Math.min(1,(cy-H*.92)/rad));
  grid(Math.max(-Math.PI/2,Math.asin(vmin)+TL-.03),Math.min(Math.PI/2,Math.PI/2+TL+.03));col();light();draw(performance.now())
}
function tick(t){if(!on)return;if(!last||t-last>=32){ang+=(last?Math.min(t-last,64):32)*.00004;last=t;draw(t)}requestAnimationFrame(tick)}
function go(v){if(red||v===on)return;on=v;last=0;if(v)requestAnimationFrame(tick)}
fit();addEventListener('resize',function(){cancelAnimationFrame(rz);rz=requestAnimationFrame(fit)});
new MutationObserver(function(){col();light();if(!on)draw(performance.now())}).observe(root,{attributes:true,attributeFilter:['data-theme']});
/* 마우스가 있으면 행성이 손을 따라 아주 조금 돈다 */
if(matchMedia('(pointer:fine)').matches)addEventListener('mousemove',function(ev){pt=(ev.clientX/innerWidth-.5)*.5},{passive:true});
if('IntersectionObserver' in window)new IntersectionObserver(function(en){go(en[0].isIntersecting&&!document.hidden)}).observe(cv);else go(true);
document.addEventListener('visibilitychange',function(){go(!document.hidden&&cv.getBoundingClientRect().bottom>0)})
})();"""

CSS = r"""
:root{
  --bg:#f9f8f6; --surface:#fff; --surface-2:#f1efeb; --slot:#eceae6; --slot-2:#e3e1dc;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-62:rgba(20,20,20,.62); --ink-30:rgba(20,20,20,.3);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --band:#141414; --band-ink:#f2f1ee; --band-62:rgba(242,241,238,.62); --band-hair:rgba(255,255,255,.14); --band-slot:#222224; --band-slot-2:#1a1a1c;
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --gap:24px; --sec:216px; --nav-bar:rgba(249,248,246,.72);
  color-scheme:light;
}
:root[data-theme="dark"]{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20; --slot:#18181a; --slot-2:#202023;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-62:rgba(236,236,234,.62); --ink-30:rgba(236,236,234,.3);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14);
  --band:#1c1c1e; --band-ink:#ececea; --band-62:rgba(236,236,234,.62); --band-hair:rgba(255,255,255,.12); --band-slot:#262628; --band-slot-2:#202022;
  --nav-bar:rgba(13,13,14,.72);
  color-scheme:dark;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:84px;overflow-x:clip}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;
  word-break:keep-all;overflow-wrap:anywhere}
::selection{background:rgba(20,20,20,.14)} :root[data-theme="dark"] ::selection{background:rgba(255,255,255,.22)}
/* 어두운 무대(.dz — 첫 화면 · 브리핑 띠)에서는 라이트 모드에서도 밝은 선택 색. 반투명 검정은 어두운 바탕에서 보이지 않아
   첫 화면 검색창에서 더블클릭 · 드래그로 고른 글이 안 고른 것처럼 보였다(사장 2026-10-01). 선택과 지우기 자체는 늘 됐다 */
.dz ::selection{background:rgba(255,255,255,.22)}
a{color:inherit;text-decoration:none}
h1,h2,h3,h4,p,ul,ol,figure{margin:0}
ul,ol{padding:0;list-style:none}
button,input{font:inherit;color:inherit}
.w{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}
.nw{white-space:nowrap}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.band :focus-visible,.hero :focus-visible{outline-color:var(--band-ink)}
svg.i{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}

/* 머리 — 스테이징 그대로(60px · 맨 위 투명 · 내리면 흐린 띠) */
.nav{position:sticky;top:0;z-index:50;height:60px;display:flex;align-items:center;transition:background-color .2s,box-shadow .2s}
.nav.scrolled{background:var(--nav-bar);box-shadow:0 1px 0 var(--hair);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px)}
.nav-in{width:100%;max-width:var(--wrap);margin:0 auto;padding:0 var(--pad);display:flex;align-items:center;justify-content:space-between;position:relative}
.brand{display:flex;align-items:center;min-height:44px}
.brand img{height:14px;display:block} .brand .dk{display:none} :root[data-theme="dark"] .brand .lt{display:none} :root[data-theme="dark"] .brand .dk{display:block}
.links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:28px}
.links a{padding:15px 0;font:500 14px/1 var(--font);color:var(--ink-72);transition:color .12s} .links a:hover{color:var(--ink)}
.nav.on-band{--nav-bar:rgba(20,20,20,.72);--ink:#f2f1ee;--ink-72:rgba(242,241,238,.72);--hair:rgba(255,255,255,.1)}
.nav.on-band .brand .lt{display:none} .nav.on-band .brand .dk{display:block}
:root[data-theme="dark"] .nav.on-band{--nav-bar:rgba(28,28,30,.72)}
.right{display:flex;align-items:center;gap:6px}
.login{font:600 13px/1 var(--font);color:var(--ink-72);padding:15px 10px} .login:hover{color:var(--ink)}
.ib{width:44px;height:44px;border:0;background:transparent;color:var(--ink-72);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;border-radius:10px} .ib:hover{color:var(--ink)}
.ib svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.menu{display:none} .menu .x{display:none} .nav.menu-open .menu .ham{display:none} .nav.menu-open .menu .x{display:block}
.mmenu{display:none;position:fixed;top:60px;left:0;right:0;bottom:0;z-index:49;background:var(--bg);flex-direction:column;padding:22px var(--pad) max(28px,env(safe-area-inset-bottom));overflow:auto;overscroll-behavior:contain}
.mm-links{display:flex;flex-direction:column} .mm-links a{display:block;padding:10px 0;font:600 28px/36px var(--font);letter-spacing:-.02em;color:var(--ink-72)}
.mmenu .sep{height:1px;background:var(--hair);margin:20px 0 22px}
.mm-auth{display:flex;flex-wrap:wrap;gap:12px 24px} .mm-auth a{font:600 16px/24px var(--font);color:var(--ink);padding:10px 0}
.mm-foot{margin-top:auto;padding-top:32px;display:flex;flex-wrap:wrap;gap:0 18px} .mm-foot a{font:400 13px/20px var(--font);color:var(--ink-62);padding:12px 0}
#kosEdgeTop,#kosEdgeBot{display:none}
@media (hover:none) and (pointer:coarse){#kosEdgeTop,#kosEdgeBot{display:block;position:fixed;left:0;right:0;height:12px;z-index:60;pointer-events:none;opacity:.2;background:var(--bg)} #kosEdgeTop{top:0} #kosEdgeBot{bottom:0}
  html.band-top #kosEdgeTop,html.band-bot #kosEdgeBot{background:var(--band)}}

/* 단추 · 링크 · 검색 — 스테이징 부품 */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:999px;border:0;
  font:600 14px/1 var(--font);white-space:nowrap;cursor:pointer;transition:opacity .12s,background-color .12s}
.btn-ink{background:var(--ink);color:var(--bg)} .btn-ink:hover{opacity:.9}
.more{display:inline-flex;align-items:center;gap:6px;min-height:44px;font:600 15px/1 var(--font);color:var(--ink)}
.more svg.i{width:15px;height:15px;transition:transform .2s}
.more:hover svg.i{transform:translateX(3px)}
.more:focus-visible{border-radius:6px}
.search{display:flex;align-items:center;gap:12px;height:60px;border-bottom:1px solid var(--line);transition:border-color .15s,box-shadow .15s}
.search:focus-within{border-bottom-color:var(--ink);box-shadow:0 1px 0 0 var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-62);flex:none}
.search input{flex:1;min-width:0;align-self:stretch;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0}
.search input::placeholder{color:var(--ink-62)}
.search .btn{height:40px;padding:0 18px}

/* 그림 자리 — 만들지 않고 표시만(종류 · 비율 · 한 줄 이름) */
.slot{position:relative;border-radius:20px;overflow:hidden;background-color:var(--slot);background-image:linear-gradient(155deg,var(--slot),var(--slot-2))}
.slot .st{position:absolute;top:18px;left:18px;display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 12px 0 10px;border-radius:999px;border:1px solid var(--line);
  font:600 12px/1 var(--font);color:var(--ink-72)}
.slot .st svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.slot .st span{font-weight:500;color:var(--ink-62)}
.slot figcaption{position:absolute;left:22px;right:22px;bottom:20px;font:500 14px/1.45 var(--font);color:var(--ink-62)}

/* 첫 화면 — 어두운 무대 · 큰 제목 · 검색 · 아래에서 떠오르는 종목의 행성(그림 없이 데이터로) */
.hero{--orb-v:clamp(320px,62vh,640px);--orb-x:280px;
  position:relative;isolation:isolate;margin-top:-60px;min-height:100vh;min-height:100svh;display:flex;flex-direction:column;
  background:var(--band);color:var(--band-ink);overflow:hidden}
.hero::before{content:"";position:absolute;z-index:-1;left:50%;top:-18%;width:min(1280px,130vw);height:78%;transform:translateX(-50%);
  background:radial-gradient(closest-side,rgba(255,255,255,.06),rgba(255,255,255,0));pointer-events:none}
.hero-in{position:relative;width:100%;padding-top:calc(60px + 104px);text-align:center}
.hero h1{margin:0 auto;max-width:1120px;font:600 clamp(46px,7.6vw,116px)/1.06 var(--font);letter-spacing:-.05em;text-wrap:balance}
.lede{margin-top:30px;max-width:540px;font:400 19px/1.65 var(--font);color:var(--ink-62);text-wrap:pretty}
.lede .s,.sub .s{display:inline-block}
.hero .lede{margin:32px auto 0;max-width:620px;color:var(--band-62)}
.hero .search{margin:44px auto 0;max-width:560px;text-align:left;border-bottom-color:rgba(255,255,255,.24)}
.hero .search:focus-within{border-bottom-color:var(--band-ink);box-shadow:0 1px 0 0 var(--band-ink)}
.hero .search svg,.hero .search input::placeholder{color:var(--band-62)}
.hero .search input{color:var(--band-ink)}
.hero .btn-ink{background:var(--band-ink);color:var(--band)}
.hero .alt{margin-top:8px}
.hero .more{color:var(--band-ink)}
/* 행성 — 경위선 격자의 점(ORB_JS). 뒤에서 올라오는 빛에 윤곽만 밝게 드러나는 행성.
   캔버스는 글 뒤로 --orb-x 만큼 올라가 빛이 잘리지 않게 번진다 */
.orb-box{position:relative;margin-top:auto;height:var(--orb-v);pointer-events:none}
.orb{position:absolute;left:0;right:0;bottom:0;z-index:-1;display:block;width:100%;height:calc(100% + var(--orb-x));
  -webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 16%,#000 66%,transparent 100%);mask-image:linear-gradient(to bottom,transparent 0,#000 16%,#000 66%,transparent 100%)}
/* 처음 열 때 — 글이 먼저 올라오고 행성의 빛이 뒤따라 밝아진다(움직임 줄임이면 없음) */
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:no-preference){
  .hero-in>*{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}
  .hero-in>.lede{animation-delay:.12s} .hero-in>.search{animation-delay:.22s} .hero-in>.alt{animation-delay:.3s}
}
/* 스크롤 등장 — 첫 화면 아래의 글이 아래에서 위로 조용히 올라온다(사장 2026-10-01 "애플이나 Valley AI 처럼, 화려하지 않고 과하지 않게").
   거리는 애플(--content-offset-y-distance 24px), 빠르기는 Valley AI(0.6초 ease-out — 90%까지 0.41초)와 같다: 24px · 1초 강한
   ease-out(90%까지 0.44초, 0.59초면 1px 안). Valley 의 50px 는 쓰지 않는다(과하지 않게). 한 번만. 한꺼번에 들어온 글끼리만
   0.08초씩 차례로(RV_JS 가 --d 를 준다 — 혼자 들어온 글은 기다리지 않는다).
   스크립트가 켤 때만 숨기고(html.rv-on — 스크립트가 안 돌거나 실패하면 처음부터 보인다), 움직임 줄임이면 켜지 않는다.
   그림 자리는 움직이지 않는다 */
.rv-on .rv{opacity:0;transform:translate3d(0,24px,0);transition:opacity 1s cubic-bezier(.2,.7,.2,1) var(--d,0s),transform 1s cubic-bezier(.2,.7,.2,1) var(--d,0s)}
.rv-on .rv.in{opacity:1;transform:none}
@media print,(prefers-reduced-motion:reduce){.rv-on .rv{opacity:1;transform:none;transition:none}}

/* 절 — 작은 이름표 · 큰 제목 · 짧은 서브 · 그림 */
.sec{padding-top:var(--sec)}
#report,#sectors{scroll-margin-top:calc(-1*var(--sec) + 24px)}
.eyebrow{margin-bottom:22px;font:600 13px/1 var(--font);color:var(--ink)}
.h2{font:600 clamp(36px,4.6vw,62px)/1.16 var(--font);letter-spacing:-.038em;text-wrap:balance}
.h2 br.m{display:none}
.sub{margin-top:24px;max-width:440px;font:400 18px/1.7 var(--font);color:var(--ink-62);text-wrap:pretty}
.tx .more{margin-top:22px}
.split{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));column-gap:var(--gap);align-items:center}
.split>.tx{grid-column:1/6;grid-row:1}
.split>.slot{grid-column:7/13;grid-row:1;aspect-ratio:4/5}
.split.rev>.tx{grid-column:8/13}
.split.rev>.slot{grid-column:1/7}
.stack>.slot{margin-top:80px;aspect-ratio:21/9}
/* 태도 절 — 그림 없는 선언 한 줄은 가운데에(빈 반쪽이 그림 빠진 자리처럼 보이지 않게) */
.solo{text-align:center} .solo .h2{margin:0 auto;max-width:900px} .solo .sub{margin-left:auto;margin-right:auto;max-width:560px}
/* 숫자 하나 — 첫 화면 제목('증권사가 다루지 않는 종목까지')의 증거라 첫 화면 바로 다음 절(사장 2026-10-01). 숫자가 그림 몫이고,
   바깥 통계라 출처 줄을 단다 */
.stat-n{font:600 clamp(72px,9vw,132px)/1 var(--font);letter-spacing:-.05em}
.stat .sub{margin-top:28px}
.src{margin-top:16px;font:400 13px/1.6 var(--font);color:var(--ink-62)}
.vh{position:absolute;width:1px;height:1px;margin:-1px;padding:0;border:0;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
/* 근거 절 — 믿을 근거 셋(짧은 이름 + 한두 문장) */
.proof{margin-top:56px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));column-gap:var(--gap)}
.proof li{padding-top:22px;border-top:1px solid var(--line)}
.proof h3{margin:0;font:600 19px/1.4 var(--font);letter-spacing:-.01em}
.proof p{margin-top:10px;max-width:330px;font:400 16px/1.7 var(--font);color:var(--ink-62);text-wrap:pretty}
.trust>.more{margin-top:40px}
#fresh .split>.slot{aspect-ratio:4/3}

/* 모닝브리핑 — 어두운 띠 하나 */
.band{margin-top:var(--sec);min-height:calc(100vh - 60px);min-height:calc(100svh - 60px);display:flex;align-items:center;padding:96px 0;background:var(--band);color:var(--band-ink);scroll-margin-top:-24px}
.band>.w{width:100%}
@media (min-width:821px){.band .slot{aspect-ratio:1/1}}
:root[data-theme="dark"] .band{box-shadow:inset 0 1px 0 var(--hair),inset 0 -1px 0 var(--hair)}
.band .eyebrow{color:var(--band-ink)} .band .sub{color:var(--band-62)}
.band .more{color:var(--band-ink)}
.band .slot{background-color:var(--band-slot);background-image:linear-gradient(155deg,var(--band-slot),var(--band-slot-2))}
.band .slot .st{border-color:var(--band-hair);color:var(--band-ink)} .band .slot .st span,.band .slot figcaption{color:var(--band-62)}

/* 마무리 — 질문 하나 · 같은 검색창(특정 종목 칩은 두지 않는다) */
.end{padding-top:var(--sec);text-align:center}
.end .h2{margin:0 auto;max-width:820px;font-size:clamp(40px,5.8vw,80px);line-height:1.1;letter-spacing:-.045em}
.end .search{margin:48px auto 0;max-width:560px;text-align:left}

/* 꼬리 — 스테이징 옷. 로고 아래 소개 문장은 두지 않는다 — 바로 아래 '서비스' 목록과 같은 말이고, 명사만 늘어놓은 줄은 한국어로
   메뉴처럼 읽힌다(사장 2026-10-01 "카피 이론을 잘 활용하는 건 중요하지. 근데 한국어로 자연스럽게").
   개인정보 처리방침은 옆 링크보다 한 단계만 굵게(500, 색은 같게) — 표준 개인정보 보호지침 제20조①의 '다른 고지사항과 구분'.
   굵기는 법 의무가 아니라 위원회 권장 기준(법 제12조)이고, 국내 6곳 실측도 구분은 하되 컬리 · 카카오페이는 한 단계만이었다 */
.foot{margin-top:var(--sec);border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand{display:inline-flex;min-height:44px} .foot .brand img{height:13px}
.fgrid{display:grid;grid-template-columns:auto auto auto;justify-content:start;column-gap:72px;margin-top:32px}
.fcol{display:flex;flex-direction:column}
.fcol h4{margin:0 0 6px;font:600 12px/16px var(--font);color:var(--ink-62)}
.fcol a{font:400 14px/20px var(--font);color:var(--ink-72);padding:6px 0;white-space:nowrap} .fcol a:hover{color:var(--ink)}
.fcol a.pp{font-weight:500}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-62)}
.copy{margin-top:28px;font:400 12px/18px var(--font);color:var(--ink-62)}

/* 낮은 노트북 창 — 첫 화면 끝에 다음 그림이 걸치게(가짜 바닥 막기) */
@media (min-width:821px) and (max-height:820px){
  .hero-in{padding-top:calc(60px + 56px)}
  .hero h1{font-size:clamp(46px,min(7.6vw,12vh),116px)}
  .hero .lede{margin-top:22px}
  .hero .search{margin-top:32px}
}
/* 태블릿·작은 노트북 */
@media (max-width:1060px){
  .split>.tx{grid-column:1/7} .split.rev>.tx{grid-column:7/13}
}
/* 한 열 — 스테이징과 같은 820px 에서 접는다 */
@media (max-width:820px){
  :root{--pad:24px; --sec:168px}
  .links,.login{display:none} .menu{display:inline-flex}
  .nav,.nav.scrolled{background:var(--bg);-webkit-backdrop-filter:none;backdrop-filter:none}
  .mmenu.open{display:flex}
  .split{display:block}
  .split>.slot{margin-top:56px;aspect-ratio:4/5;max-width:560px}
  .nav.on-band,.nav.on-band.scrolled{background:var(--band)}
  .nav.on-band:not(.scrolled){background:transparent}   /* 첫 화면 맨 위에서는 무대의 빛이 머리 뒤까지 이어지게 */
  .proof{grid-template-columns:1fr;row-gap:28px;margin-top:40px}
  .proof p{max-width:none}
}
/* 태블릿 세로(721~820px) — 그림은 전폭 4:3 */
@media (min-width:721px) and (max-width:820px){
  .split>.slot{max-width:none;aspect-ratio:4/3}
}
/* 휴대폰 */
@media (max-width:720px){
  :root{--pad:20px; --sec:136px}
  html{scroll-padding-top:72px}
  .hero-in{padding-top:calc(60px + 56px)}
  .hero h1 br.m,.h2 br.m{display:inline}
  .hero h1{font-size:min(44px,calc((100vw - 40px) / 8));line-height:1.16;letter-spacing:-.04em}   /* 첫 줄 폭 = 글자 크기 × 7.8 — 두 줄을 지킨다 */
  .lede{margin-top:22px;font-size:17px}
  .hero .lede{margin-top:22px}
  .hero .search{margin-top:32px}
  .hero{--orb-v:clamp(300px,58vh,520px);--orb-x:180px}
  .search input{font-size:16px}
  .search .btn{height:44px;padding:0 16px}
  .eyebrow{margin-bottom:16px}
  .h2{font-size:32px;line-height:1.25;letter-spacing:-.03em}
  .end .h2{font-size:36px;line-height:1.2}
  .sub{margin-top:18px;font-size:16px}
  .solo{text-align:left} .solo .h2,.solo .sub{margin-left:0}   /* 한 열에서는 빈 반쪽이 없으니 다른 절처럼 왼쪽 정렬 */
  .stat .sub{margin-top:20px}
  .split>.slot,.stack>.slot,#fresh .split>.slot{margin-top:44px;aspect-ratio:1/1}
  .slot{border-radius:16px}
  .band{padding:72px 0}
  .end .search{margin-top:36px}
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
LINKS = [("홈", "#"), ("리포트", "#report"), ("업종 분석", "#sectors"), ("관심종목", "#"), ("모닝브리핑", "#brief")]   # 멤버십은 뺐다 — 랜딩은 KOSAI 소개, 가격 문구는 유료화 법정 절차 뒤(CLAUDE.md)


def sents(text):
    """문장마다 한 덩어리(.s = inline-block) — 줄은 문장 사이에서만 바뀐다. 한 문장이 칸보다 길면 그 안에서 바뀐다."""
    return " ".join(f'<span class="s">{g(x)}</span>' for x in re.split(r"(?<=[.?!])\s+", text) if x)


def slot(kind, icon, ratio, name):
    """그림 자리 — 이름표(종류 · 비율)와 한 줄 이름만. 자세한 권장 소재는 보고서에."""
    return (f'<figure class="slot" aria-label="{esc(kind)} 자리 — {esc(name)}"><span class="st">{I[icon]}{esc(kind)}<span>{esc(ratio)}</span></span>'
            f'<figcaption>{esc(name)}</figcaption></figure>')


def more(label, href="#"):
    return f'<a class="more" href="{href}">{label} {I["arrow"]}</a>'


def nav():
    lk = "".join(f'<a href="{h}">{t}</a>' for t, h in LINKS)
    return ('<div id="kosEdgeTop" aria-hidden="true"></div><div id="kosEdgeBot" aria-hidden="true"></div>'
            f'<nav class="nav on-band" id="nav"><div class="nav-in"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a><div class="links">{lk}</div>'
            f'<div class="right"><a class="login" href="#">로그인</a><button class="ib" id="themeBtn" aria-label="테마 전환"><svg viewBox="0 0 24 24" id="themeIcon">{I["moon"]}</svg></button>'
            f'<button class="ib menu" id="menuBtn" aria-label="메뉴" aria-expanded="false" aria-controls="mmenu">{I["ham"]}{I["x"]}</button></div></div></nav>'
            f'<div class="mmenu" id="mmenu"><div class="mm-links">{lk}</div><div class="sep"></div><div class="mm-auth"><a href="#">로그인</a><a href="#">회원가입</a></div>'
            '<div class="mm-foot"><a href="#">회사 소개</a><a href="#">문의하기</a><a href="#">피드백</a><a href="#">이용약관</a><a href="#">개인정보 처리방침</a></div></div>')


def foot():
    return (f'<footer class="foot"><div class="w"><a class="brand" href="#"><img class="lt" src="{ASSETS}/kosai-wordmark-black.png" alt="KOSAI">'
            f'<img class="dk" src="{ASSETS}/kosai-wordmark-white.png" alt="KOSAI"></a>'
            '<div class="fgrid"><div class="fcol"><h4>서비스</h4><a href="#">홈</a><a href="#">리포트</a><a href="#">업종 분석</a><a href="#">관심종목</a><a href="#">모닝브리핑</a></div>'
            '<div class="fcol"><h4>회사</h4><a href="#">회사 소개</a><a href="#">문의하기</a><a href="#">피드백</a></div>'
            '<div class="fcol"><h4>정책</h4><a href="#">이용약관</a><a class="pp" href="#">개인정보 처리방침</a></div></div>'
            '<div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>'
            '<div class="copy">© 2026 KOSAI</div></div></footer>')


def search_box(ph="종목명 또는 종목코드"):
    """검색창 — 안내에 특정 종목 예시를 넣지 않는다(사장 "예시로 특정 종목을 왜 보여주나")."""
    return (f'<form class="search" role="search" onsubmit="return false">{I["search"]}<input placeholder="{ph}" aria-label="종목 검색" autocomplete="off">'
            '<button class="btn btn-ink" type="button">리포트 찾기</button></form>')


def orb_data():
    """첫 화면의 행성 — 점은 모두 같은 크기로 경위선 격자의 교차점에 놓이고, 점의 수는 종목 수가 아니라 간격에서 나온다(ORB_JS 의
    grid — 눈에 보이는 간격 0.9°. 사장 2026-10-01 "점 수를 종목 수만큼 넣을 필요는 없어"). 여기서 넘기는 것은 반짝임의 몫뿐이다 —
    최근 14일 안에 새로 쓴 리포트(r)가 전체 종목(n)에서 차지하는 비율만큼 점이 천천히 밝아졌다 어두워진다. 종목 순서는 고정 씨앗으로
    섞어 빌드마다 같다.
    5판 뒤 구 다듬기(사장 2026-09-27 "점이 불규칙하게 위치해 있어서 규칙적으로") — 피보나치 배치와 시가총액 크기를 버렸다."""
    import json
    import random
    rnd = random.Random(ORB_SEED)
    tks = [t for t in INDEX if t in BY]
    rnd.shuffle(tks)
    recent = [i for i, t in enumerate(tks)
              if INDEX[t].get("reportDate") and (BASE - datetime.date.fromisoformat(INDEX[t]["reportDate"])).days <= 14]
    return json.dumps({"n": len(tks), "r": recent}, separators=(",", ":"))


def sources_avg():
    """화면에 나오는 리포트(새 형식, 없으면 옛 형식)의 출처 수 평균 — 소수 첫째 자리까지."""
    import json
    tot = n = 0
    for t in INDEX:
        for d in ("reports_v2", "reports"):
            f = os.path.join(ROOT, "data", d, f"{t}.json")
            if os.path.exists(f):
                tot += len(json.load(open(f, encoding="utf-8")).get("sources") or [])
                n += 1
                break
    v = round(tot / n, 1)
    return f"{v:g}"


def copy_text(n_rep, n_sec, brief_no, src_avg):
    """랜딩 문구 전부 — 5판(2026-09-27 사장 "AI 말투를 없애고 대기업 말투를 적용해"):
    서브는 조각 없이 끝까지 쓴 합쇼체 문장으로, 말장난·대구·'~의 몫' 같은 꾸밈 없이 사실을 담담하게. 주어가 필요하면 'KOSAI'.
    제목은 명사구 중심, 합쇼체 단언 하나(태도), 요청 하나(마지막). 가운뎃점 없음 · 기준일 없음 · 특정 종목 예시 링크 없음.
    첫 화면 서브에서 'AI가 씁니다'를 뺐다(사장 "싸구려 느낌") — AI 는 원칙 절에서 한 번, 무엇을 AI 가 하지 않는지로 말한다.
    둘째 절은 '좋게 볼 이유와 조심할 이유'가 아니라 방문자가 얻는 것(한 편에 담은 기업 분석)으로 연다 — 강세·약세 요인은 그 근거로.
    첫 화면 다음에는 숫자 하나(2026-10-01 사장) — 제목 '증권사가 다루지 않는 종목까지'의 증거다. 숫자 절 끝의
    'KOSAI는 해당 기업에 대해서도 분석 리포트를 제공합니다'(2026-10-01 사장 승인)가 숫자와 리포트 절 사이의 '그래서'를 드러낸다 — 리포트가 없는
    상장사가 2026년 9월 신규 상장 2개사뿐임을 확인한 문장이다(보고서 4-8). 리포트가 빠진 상장사가 늘면 다시 확인할 것.
    처음 문장 '이들 기업의 리포트도 발행합니다'는 '기업이 낸 보고서'로도 읽히고 앞 문장의 '보고서 · 발간'과 말이 엇갈려(사장 "어색하다")
    '해당 기업에 대해서도'(무엇에 관한 리포트인지 분명) · '제공합니다'(첫 화면 서브와 같은 동사)로 고쳤다."""
    pct = f"{GAP['none'] / GAP['total'] * 100:.1f}"
    when = "지난해" if BASE.year == GAP["year"] + 1 else f"{GAP['year']}년"   # 집계가 묵으면 '지난해'가 틀린 말이 된다
    return {
        "h1": "증권사가 다루지\u00a0않는<br>종목까지",
        "h1_plain": "증권사가 다루지 않는 종목까지",
        "lede": f"{SCOPE} {n_rep:,}개 종목의 기업\u00a0분석\u00a0리포트를 제공합니다.",
        # '10곳 중 6곳'은 60%라 부풀린 말이 된다 — 정확한 비율로. 총수(2,674)는 첫 화면의 종목 수와 헷갈리니 출처 줄에만
        # 대기업 말투 — '나오다'(구어) 대신 '발간', '한 건도' 같은 강조 없이, 회사 수는 '개사'(사장 2026-10-01 "대기업 말투 좀 써")
        "gap": (f"{pct}%", f"{when} 증권사 기업분석 보고서가 발간되지\u00a0않은 국내\u00a0상장사는 {GAP['none']:,}개사입니다. "
                           "KOSAI는 해당 기업에 대해서도 분석\u00a0리포트를\u00a0제공합니다.",
                f"자료: {GAP['src']}, {GAP['year']}년 상장사 {GAP['total']:,}개사 집계"),
        "gap_sr": f"{when} 증권사 기업분석 보고서가 발간되지 않은 국내 상장사 비율",
        "report": ("리포트", "한 편에 담은<br>기업 분석",
                   "사업 구조와 실적, 업황, 전망, 리스크를 차례로 정리합니다. 강세 요인과 약세 요인을 함께 제시해 어느\u00a0한쪽으로\u00a0치우치지\u00a0않습니다."),
        # '목표주가도 없습니다'는 틀린 말 — 새 형식 2,563편 중 616편이 증권사 목표주가를 출처와 함께 인용한다. KOSAI 가 제시하지 않을 뿐('자체')
        "stance": ("", "매수도 매도도<br>권하지 않습니다",
                   "KOSAI는 자체 투자의견과 목표주가를 제시하지 않습니다. 투자 판단에 필요한 사실과 근거를 정리하는 데 집중합니다."),
        "fresh": ("", "공시와 함께<br>갱신되는 리포트",
                  "분기보고서와 반기보고서, 사업보고서가 공시되면 리포트를\u00a0새로\u00a0작성합니다. 주가와 밸류에이션 지표는 거래일마다 반영합니다."),
        # 원칙 셋 — 코드로 확인한 사실만(보고서 4부 사실 장부). '숫자는 AI가 만들지 않는다'처럼 넓히지 않는다(AI 해석 문장의 숫자는 검증 밖)
        "trust": ("", "리포트의<br>세 가지 원칙", ""),
        "trust_points": [
            ("공시 원본 수치", "실적 표와 차트의 수치는 금융감독원 전자공시\u2060(DART) 원본에서 가져오며, AI가\u00a0생성하지\u00a0않습니다."),
            ("출처 공개", f"분석의 근거가 된 자료를 리포트마다 출처로\u00a0공개합니다. 한\u00a0편당 평균\u00a0{src_avg}건입니다."),
            ("발행 전 검수", "투자 권유로 읽힐 수 있는 표현은 발행\u00a0전에 자동으로 검수해\u00a0수정합니다."),
        ],
        "trust_link": "작성 방식 자세히 보기",
        "hero_link": "전체 리포트 보기",
        "brief": ("모닝브리핑", "개장 전에 읽는<br>시장 브리핑",
                  "전일 국내 증시와 간밤의 해외 시장, 주요\u00a0일정을\u00a0정리합니다. 발행 시각은 거래일 오전\u00a07시\u00a030분 전후입니다."),
        "sectors": ("업종 분석", f"{n_sec}개 업종의 흐름",
                    "업종마다 업황과 주요 종목을 정리합니다. 개별 기업을 산업 전체의 맥락에서 살펴볼 수 있습니다."),
        "end": "궁금한 종목의<br>리포트를 확인하세요",
        "brief_link": f"제{brief_no}호 읽기",
        "sectors_link": "전체 업종 보기",
        "title": f"KOSAI — {SCOPE} {n_rep:,}개 종목의 기업 분석 리포트",
        "og_title": "KOSAI — 증권사가 다루지 않는 종목까지",
        "desc": f"{SCOPE} {n_rep:,}개 종목의 기업 분석 리포트와 모닝브리핑, 업종 분석을 제공합니다.",
        "og_desc": f"{SCOPE} {n_rep:,}개 종목의 기업 분석 리포트",
    }


def page():
    n_rep = len(INDEX)
    b = brief()
    cnt = Counter(c for x in STOCKS["stocks"] for c in (x.get("categories") or []) if c != "기타")
    C = copy_text(n_rep, len(cnt), b["_no"], sources_avg())

    def head_block(key, link=""):   # .rv — 스크롤 등장(RV_JS)
        eb, h, sub = C[key]
        return ((f'<p class="eyebrow rv">{eb}</p>' if eb else "") + f'<h2 class="h2 rv">{h}</h2><p class="sub rv">{sents(sub)}</p>'
                + link.replace('class="more"', 'class="more rv"', 1))

    num = f"{n_rep:,}"
    lede = g(C["lede"]).replace(num, f'<span class="num">{num}</span>', 1)   # 실사이트로 옮기면 stamp_counts 가 맞추는 자리
    # 첫 화면 — 어두운 무대(.dz: 머리·사파리 가장자리 띠가 어두운 색을 따른다) · 큰 제목 · 검색 · 아래에서 떠오르는 종목의 구
    hero = (f'<header class="hero dz" id="hero"><div class="hero-in w"><h1>{C["h1"]}</h1><p class="lede"><span class="s">{lede}</span></p>'
            + search_box()
            + f'<div class="alt">{more(C["hero_link"])}</div></div>'
            f'<div class="orb-box" aria-hidden="true"><canvas class="orb" id="orb"></canvas></div>'
            f'<script type="application/json" id="orbData">{orb_data()}</script></header>')
    # 숫자 하나 — 첫 화면 제목의 증거라 바로 다음 절. 숫자가 그림 몫이고, 제목 목록에서도 뜻이 통하게 숨은 설명을 붙인다
    gp, gs, gsrc = C["gap"]
    sec_gap = (f'<section class="sec w solo stat" id="gap"><h2 class="stat-n rv"><span class="cnt">{esc(gp)}</span><span class="vh">, {esc(C["gap_sr"])}</span></h2>'
               f'<p class="sub rv">{sents(gs)}</p><p class="src rv">{g(gsrc)}</p></section>')
    sec_report = (f'<section class="sec w" id="report"><div class="split"><div class="tx">{head_block("report")}</div>'
                  + slot("이미지", "image", "PC 4:5 / 휴대폰 1:1", "리포트 한 편의 화면") + '</div></section>')
    sec_fresh = (f'<section class="sec w" id="fresh"><div class="split rev"><div class="tx">{head_block("fresh")}</div>'
                 + slot("이미지", "image", "PC 4:3 / 휴대폰 1:1", "공시 반영 뒤 바뀐 기준일(확대)") + '</div></section>')
    pts = "".join(f'<li class="rv"><h3>{g(t)}</h3><p>{sents(d)}</p></li>' for t, d in C["trust_points"])
    sec_trust = (f'<section class="sec w trust"><h2 class="h2 rv">{C["trust"][1]}</h2><ul class="proof">{pts}</ul>'
                 + more(C["trust_link"]).replace('class="more"', 'class="more rv"', 1) + '</section>')   # 링크는 작성 방식(회사 소개) — 특정 종목 예시는 두지 않는다(사장)
    sec_brief = (f'<section class="band dz" id="brief"><div class="w split"><div class="tx">{head_block("brief", more(C["brief_link"]))}</div>'
                 + slot("사진", "image", "1:1", "개장 전 아침, 책상 위 휴대폰") + '</div></section>')
    sec_sectors = (f'<section class="sec w stack" id="sectors">{head_block("sectors", more(C["sectors_link"]))}'
                   + slot("이미지", "image", "21:9 / 휴대폰 1:1", "업종 분석 화면") + '</section>')
    sec_stance = f'<section class="sec w solo">{head_block("stance")}</section>'
    sec_end = (f'<section class="end w"><h2 class="h2 rv">{C["end"]}</h2>'
               + f'<div class="rv">{search_box()}</div></section>')   # 검색창은 밑줄 transition 이 있어 감싼 상자를 올린다

    orb_js = "<script>" + ORB_JS + "</script>"
    rv_js = "<script>" + RV_JS + "</script>"   # 다른 스크립트와 따로 — 저쪽이 실패해도 글이 숨은 채로 남지 않게
    js = ("<script>(function(){"
          "var root=document.documentElement,nav=document.getElementById('nav'),zs=[].slice.call(document.querySelectorAll('.dz')),"
          "meta=document.querySelector('meta[name=\"theme-color\"]'),tick=false;"
          "function over(y){for(var i=0;i<zs.length;i++){var b=zs[i].getBoundingClientRect();if(b.top<=y&&b.bottom>=y)return true}return false}"
          "function upd(){tick=false;nav.classList.toggle('scrolled',scrollY>32);"
          "var open=nav.classList.contains('menu-open'),H=innerHeight,top=!open&&over(6);"
          "nav.classList.toggle('on-band',!open&&over(30));root.classList.toggle('band-top',top);root.classList.toggle('band-bot',!open&&over(H-6));"
          "var cs=getComputedStyle(root);meta.setAttribute('content',(top?cs.getPropertyValue('--band'):cs.getPropertyValue('--bg')).trim())}"
          "function req(){if(!tick){tick=true;requestAnimationFrame(upd)}}"
          "addEventListener('scroll',req,{passive:true});addEventListener('resize',req);upd();"
          "var sun='<path d=\"M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4\"/><circle cx=\"12\" cy=\"12\" r=\"4\"/>',"
          "moon='" + I["moon"] + "';"
          "var icon=document.getElementById('themeIcon');function paint(){icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}paint();"
          "document.getElementById('themeBtn').addEventListener('click',function(){var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);"
          "try{localStorage.setItem('kos-theme',t)}catch(e){}paint();upd()});"
          "var mb=document.getElementById('menuBtn'),mm=document.getElementById('mmenu'),mn=document.querySelector('main'),ft=document.querySelector('footer');"
          "function setMenu(on){nav.classList.toggle('menu-open',on);mm.classList.toggle('open',on);mb.setAttribute('aria-expanded',on?'true':'false');root.style.overflow=on?'hidden':'';mn.inert=on;ft.inert=on;upd()}"
          "mb.addEventListener('click',function(){setMenu(!nav.classList.contains('menu-open'))});"
          "mm.addEventListener('click',function(e){if(e.target.closest('a'))setMenu(false)});"
          "document.addEventListener('keydown',function(e){if(e.key==='Escape'&&nav.classList.contains('menu-open')){setMenu(false);mb.focus()}});"
          "matchMedia('(min-width:821px)').addEventListener('change',function(e){if(e.matches)setMenu(false)})"
          "})();</script>")
    # 첫 화면이 어두운 무대라 처음 색은 무대 색 — 내리면 upd() 가 페이지 색으로 바꾼다
    theme = ("<script>(function(){var t='light';try{t=localStorage.getItem('kos-theme')||'light'}catch(e){}var r=document.documentElement;"
             "r.setAttribute('data-theme',t);r.classList.add('band-top');"
             "if('IntersectionObserver' in window&&!matchMedia('(prefers-reduced-motion: reduce)').matches)r.classList.add('rv-on');"
             "document.querySelector('meta[name=\"theme-color\"]').setAttribute('content',t==='dark'?'#1c1c1e':'#141414')})();</script>")
    head = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#141414"><title>{esc(C["title"])}</title>'
            f'<meta name="description" content="{esc(C["desc"])}"><meta property="og:title" content="{esc(C["og_title"])}">'
            f'<meta property="og:description" content="{esc(C["og_desc"])}">'
            f'<link rel="stylesheet" href="{FONTS}/pretendard-subset.css"><link rel="stylesheet" href="landing.css">{theme}</head><body>')
    return (head + nav() + f"<main>{hero}{sec_gap}{sec_report}{sec_stance}{sec_trust}{sec_fresh}{sec_sectors}{sec_brief}{sec_end}</main>"
            + foot() + rv_js + orb_js + js + "</body></html>")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "landing.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    html = page()
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    print(f"preview/concepts/landing/index.html {len(html):,}자 · landing.css {len(CSS):,}자")
