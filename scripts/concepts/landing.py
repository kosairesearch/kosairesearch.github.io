"""랜딩 시안 3판 — 스테이징 옷 그대로, 절마다 '큰 제목 · 짧은 서브 · 그림' 하나씩.

    python3 scripts/concepts/landing.py      # → preview/concepts/landing/index.html · landing.css

  · 3판은 사장 피드백(2026-09-27)대로 줄였다 — "초중반에 글이 너무 많다 · 메인카피·서브카피·이미지 · 여백 ·
    리포트 이미지를 넣으니 글이 많아진다 · 랜딩에서 멤버십 이야기를 왜 꺼내나 · -다로만 끝나 지루하다(AI 톤)".
    그래서 리포트 카드 · 최근 목록 · 업종 칸 · 신뢰 세 기둥의 긴 글 · 요금 · 질문 · 브리핑 카드 · 그림 자리의 긴 설명을 뺐다.
  · 문구는 COPY 한 곳에 모았다. 말끝은 섞는다(제목은 조각·조사 끝, 서브는 해요체 중심). 근거와 규칙은
    reports/카피라이팅과 랜딩페이지 구성 이론 총정리.md 와 노트 16–19(한국어 카피 말끝 · AI 말투).
  · 그림·영상·3D 는 만들지 않는다. 들어갈 자리만 표시한다(종류 · 비율 · 한 줄 이름). 권장 소재는 보고서 5부.
  · 숫자는 전부 data/ 에서 계산한다 — 손으로 적은 숫자·날짜 없음. 스테이징·실사이트 파일은 건드리지 않는다.
"""
import datetime
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from data import ROOT, BY, STOCKS, INDEX, esc, jo, brief, now_date  # noqa: E402
from common import g  # noqa: E402

OUT = os.path.join(ROOT, "preview", "concepts", "landing")
ASSETS = "../../../assets"
FONTS = "../../../fonts"
HERO_REPORT = "005930"                                  # 첫 화면 보조 링크 — 누구나 아는 대형주 한 편
CHIPS = ["005930", "000660", "300080", "093240"]        # 마무리 칩 — 시가총액 1,669조부터 182억까지(넷 다 글자 결함 0)
BASE = datetime.date.fromisoformat(f"{now_date()[:4]}-{now_date()[4:6]}-{now_date()[6:8]}")   # 데이터의 '오늘'
MARKETS = "코스피·코스닥·코넥스"

CSS = r"""
:root{
  --bg:#f9f8f6; --surface:#fff; --surface-2:#f1efeb; --slot:#eceae6; --slot-2:#e3e1dc;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-62:rgba(20,20,20,.62); --ink-30:rgba(20,20,20,.3);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --band:#141414; --band-ink:#f2f1ee; --band-62:rgba(242,241,238,.62); --band-slot:#222224; --band-slot-2:#1a1a1c;
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --gap:24px; --sec:216px; --nav-bar:rgba(249,248,246,.72);
  color-scheme:light;
}
:root[data-theme="dark"]{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20; --slot:#18181a; --slot-2:#202023;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-62:rgba(236,236,234,.62); --ink-30:rgba(236,236,234,.3);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14);
  --band:#1c1c1e; --band-ink:#ececea; --band-62:rgba(236,236,234,.62); --band-slot:#262628; --band-slot-2:#202022;
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
h1,h2,h3,h4,p,ul,ol,figure{margin:0}
ul,ol{padding:0;list-style:none}
button,input{font:inherit;color:inherit}
.w{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}
.nw{white-space:nowrap}
:focus-visible{outline:2px solid var(--ink);outline-offset:3px}
.band :focus-visible{outline-color:var(--band-ink)}
svg.i{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}

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

/* 단추 · 링크 · 검색 — 스테이징 부품 */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 20px;border-radius:999px;border:0;
  font:600 14px/1 var(--font);white-space:nowrap;cursor:pointer;transition:opacity .12s,background-color .12s}
.btn-ink{background:var(--ink);color:var(--bg)} .btn-ink:hover{opacity:.9}
.more{display:inline-flex;align-items:center;gap:6px;min-height:44px;font:600 15px/1 var(--font);color:var(--ink)}
.more svg.i{width:15px;height:15px;transition:transform .2s}
.more:hover svg.i{transform:translateX(3px)}
.search{display:flex;align-items:center;gap:12px;height:60px;border-bottom:1px solid var(--line);transition:border-color .15s,box-shadow .15s}
.search:focus-within{border-bottom-color:var(--ink);box-shadow:0 1px 0 0 var(--ink)}
.search svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;color:var(--ink-62);flex:none}
.search input{flex:1;min-width:0;align-self:stretch;border:0;background:transparent;font:400 17px/24px var(--font);color:var(--ink);outline:0;padding:0}
.search input::placeholder{color:var(--ink-62)}
.search .btn{height:40px;padding:0 18px}

/* 그림 자리 — 만들지 않고 표시만(종류 · 비율 · 한 줄 이름) */
.slot{position:relative;border-radius:20px;overflow:hidden;background-color:var(--slot);background-image:linear-gradient(155deg,var(--slot),var(--slot-2))}
.slot::before{content:"";position:absolute;inset:0;background-image:repeating-linear-gradient(-45deg,rgba(128,128,128,.055) 0 1px,transparent 1px 14px)}
.slot .st{position:absolute;top:18px;left:18px;display:inline-flex;align-items:center;gap:7px;height:28px;padding:0 12px 0 10px;border-radius:999px;background:var(--surface);
  font:600 12px/1 var(--font);color:var(--ink)}
.slot .st svg{width:13px;height:13px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linejoin:round}
.slot .st span{font-weight:500;color:var(--ink-62)}
.slot figcaption{position:absolute;left:22px;right:22px;bottom:20px;font:500 14px/1.45 var(--font);color:var(--ink-62)}

/* 첫 화면 */
.hero{padding-top:104px}
.hero h1{max-width:1040px;font:600 clamp(44px,6.4vw,92px)/1.12 var(--font);letter-spacing:-.045em;text-wrap:balance}
.hero h1 br.m{display:none}
.lede{margin-top:30px;max-width:540px;font:400 19px/1.65 var(--font);color:var(--ink-62);text-wrap:pretty}
.hero .search{margin-top:48px;max-width:560px}
.hero .alt{margin-top:6px}
.hero .slot{margin-top:96px;aspect-ratio:16/9}

/* 절 — 작은 이름표 · 큰 제목 · 짧은 서브 · 그림 */
.sec{padding-top:var(--sec)}
.eyebrow{margin-bottom:22px;font:600 13px/1 var(--font);color:var(--ink-62)}
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
.solo .h2{font-size:clamp(40px,5.8vw,80px);line-height:1.1;letter-spacing:-.045em}
.solo .sub{max-width:520px}

/* 모닝브리핑 — 어두운 띠 하나 */
.band{margin-top:var(--sec);padding:184px 0;background:var(--band);color:var(--band-ink)}
:root[data-theme="dark"] .band{box-shadow:inset 0 1px 0 var(--hair),inset 0 -1px 0 var(--hair)}
.band .eyebrow,.band .sub{color:var(--band-62)}
.band .more{color:var(--band-ink)}
.band .slot{background-color:var(--band-slot);background-image:linear-gradient(155deg,var(--band-slot),var(--band-slot-2))}
.band .slot .st{background:#2e2e31;color:var(--band-ink)} .band .slot .st span,.band .slot figcaption{color:var(--band-62)}

/* 마무리 — 질문 하나 · 같은 검색창 · 종목 칩 */
.end{padding-top:var(--sec);text-align:center}
.end .h2{margin:0 auto;max-width:820px}
.end .search{margin:48px auto 0;max-width:560px;text-align:left}
.chips{margin-top:18px;display:flex;flex-wrap:wrap;justify-content:center;gap:8px}
.chips a{display:inline-flex;align-items:center;height:40px;padding:0 14px;border-radius:999px;background:var(--surface-2);font:500 14px/1 var(--font);color:var(--ink);transition:background-color .12s}
.chips a:hover{background:var(--line)}
.chips a span{margin-left:6px;font-weight:400;color:var(--ink-62)}

/* 꼬리 — 스테이징 그대로 */
.foot{margin-top:var(--sec);border-top:1px solid var(--hair);padding:56px 0 48px}
.foot .brand{min-height:0} .foot .brand img{height:13px}
.ftag{margin-top:14px;font:400 14px/22px var(--font);color:var(--ink-72);max-width:320px}
.fgrid{display:grid;grid-template-columns:auto auto auto;justify-content:start;column-gap:72px;margin-top:32px}
.fcol{display:flex;flex-direction:column}
.fcol h4{margin:0 0 6px;font:600 12px/16px var(--font);color:var(--ink-62)}
.fcol a{font:400 14px/20px var(--font);color:var(--ink-72);padding:6px 0;white-space:nowrap} .fcol a:hover{color:var(--ink)}
.fcol a.pp{font-weight:600;color:var(--ink)}
.biz{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-62)}
.copy{margin-top:28px;font:400 12px/18px var(--font);color:var(--ink-62)}

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
  .band{padding:136px 0}
}
/* 휴대폰 */
@media (max-width:720px){
  :root{--pad:20px; --sec:136px}
  html{scroll-padding-top:72px}
  .hero{padding-top:52px}
  .hero h1 br.m,.h2 br.m{display:inline}
  .hero h1{font-size:min(42px,11.2vw);line-height:1.18;letter-spacing:-.035em}
  .lede{margin-top:22px;font-size:17px}
  .hero .search{margin-top:36px}
  .search input{font-size:16px}
  .search .btn{height:44px;padding:0 16px}
  .hero .slot{margin-top:56px;aspect-ratio:1/1}
  .eyebrow{margin-bottom:16px}
  .h2{font-size:32px;line-height:1.25;letter-spacing:-.03em}
  .solo .h2{font-size:36px;line-height:1.2}
  .sub{margin-top:18px;font-size:16px}
  .split>.slot,.stack>.slot{margin-top:44px;aspect-ratio:1/1}
  .slot{border-radius:16px}
  .band{padding:112px 0}
  .end .search{margin-top:36px}
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
LINKS = [("홈", "#"), ("리포트", "#report"), ("업종 분석", "#sectors"), ("관심종목", "#"), ("멤버십", "#"), ("모닝브리핑", "#brief")]


def slot(kind, icon, ratio, name):
    """그림 자리 — 이름표(종류 · 비율)와 한 줄 이름만. 자세한 권장 소재는 보고서에."""
    return (f'<figure class="slot" aria-label="{esc(kind)} 자리 — {esc(name)}"><span class="st">{I[icon]}{esc(kind)}<span>{esc(ratio)}</span></span>'
            f'<figcaption>{esc(name)}</figcaption></figure>')


def more(label, href="#"):
    return f'<a class="more" href="{href}">{label} {I["arrow"]}</a>'


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
            '<div class="copy">© 2026 KOSAI</div></div></footer>')


def search_box(ph="종목명 또는 종목코드(예: 삼성전자, 005930)", ph_m="종목명 또는 종목코드"):
    """휴대폰(과 좁은 칸)은 예시가 잘리므로 짧은 안내(data-m)로 바꾼다."""
    return (f'<form class="search" role="search" onsubmit="return false">{I["search"]}<input placeholder="{ph}" data-m="{ph_m}" aria-label="종목 검색" autocomplete="off">'
            '<button class="btn btn-ink" type="button">리포트 찾기</button></form>')


def copy_text(n_rep, n_sec, brief_no, asof):
    """랜딩 문구 전부 — KOSAI 가 이미 쓰는 목소리(노트 20 실측): 제목은 명사형(사이트 제목의 90% 이상), 서브는 합쇼체에
    명사로 끝나는 짧은 줄을 섞고, 해요체는 질문에만. 제목 모양은 절마다 다르게 — 조사 끝 · 명사구 · 관형형+명사 · 질문 ·
    의+명사구 · 숫자+명사구 · 합쇼체 단언 · 조사 끝. 쉼표로 가른 'A, B' 제목은 쓰지 않는다(3판 초안은 8개 중 6개였다).
    첫 제목의 '까지'와 마지막 제목의 '부터'가 짝이다."""
    return {
        "h1": "증권사가 다루지 않는<br>종목까지",
        "h1_plain": "증권사가 다루지 않는 종목까지",
        "lede": (f"{MARKETS} {n_rep:,}개 종목의", f"리포트({asof}).", "실적 표는 공시에서 가져오고, 해석은 AI가 씁니다."),   # 가운데 조각은 한 덩어리
        "report": ("리포트", "좋게 볼 이유와<br>조심할 이유",
                   "리포트마다 강세 요인과 약세 요인을 셋씩 나란히 적습니다. 사업 구조에서 종합 의견까지, 늘 같은 순서로."),
        "fresh": ("갱신", "공시가 나오면<br>다시 쓰는 리포트",
                  "분기·반기·사업보고서가 공시되면 최신 실적으로 고쳐\u00a0씁니다. 주가와 PER은 거래일 저녁마다 새 값으로."),
        "trust": ("근거", "AI가 쓴 리포트를<br>믿어도 될까요?",
                  "실적 표와 차트는 DART 공시에서 그대로 옮깁니다. AI가 쓰는 것은 그 숫자를 읽은 해석입니다."),
        "brief": ("모닝브리핑", "장이 열리기 전의<br>한 편",
                  "전날 국내 시장과 밤사이 해외 소식, 오늘 일정까지. 거래일\u00a0아침 7시 30분 무렵에 나옵니다."),
        "sectors": ("업종 분석", f"{n_sec}개 업종의 흐름",
                    "업종마다 업황과 주요 종목을 따로 정리합니다. 한 회사를 읽을\u00a0때 옆 회사도 함께."),
        "stance": ("", "사라고도 팔라고도<br>하지 않습니다",
                   "매수·매도 의견과 목표주가 대신 판단에 쓸 근거를 모읍니다."),
        "end": "궁금한 종목부터",
        "brief_link": f"제{brief_no}호 읽기",
        "sectors_link": f"{n_sec}개 업종 분석 보기",
        "desc": f"{MARKETS} {n_rep:,}개 종목의 리포트. 실적 표는 공시에서 가져오고, 해석은 AI가 씁니다.",
        "og_desc": f"{MARKETS} {n_rep:,}개 종목의 리포트와 모닝브리핑",
    }


def page():
    n_rep = len(INDEX)
    b = brief()
    cnt = Counter(c for x in STOCKS["stocks"] for c in (x.get("categories") or []) if c != "기타")
    C = copy_text(n_rep, len(cnt), b["_no"], f"{BASE.month}월 {BASE.day}일 기준")

    def head_block(key, link=""):
        eb, h, sub = C[key]
        return ((f'<p class="eyebrow">{eb}</p>' if eb else "") + f'<h2 class="h2">{h}</h2><p class="sub">{g(sub)}</p>' + link)

    la, lb, lc = C["lede"]
    hero = (f'<header class="hero w"><h1>{C["h1"]}</h1><p class="lede">{g(la)} <span class="nw">{g(lb)}</span> {g(lc)}</p>'
            + search_box()
            + f'<div class="alt">{more(esc(BY[HERO_REPORT]["name"]) + " 리포트 보기")}</div>'
            + slot("영상 · 사진", "video", "16:9 · 휴대폰 1:1", "손에 든 휴대폰 속 KOSAI 리포트")
            + '</header>')
    sec_report = (f'<section class="sec w" id="report"><div class="split"><div class="tx">{head_block("report")}</div>'
                  + slot("이미지", "image", "4:5", "리포트 화면 — 강세·약세 요인") + '</div></section>')
    sec_fresh = (f'<section class="sec w" id="fresh"><div class="split rev"><div class="tx">{head_block("fresh")}</div>'
                 + slot("이미지", "image", "4:5", "공시가 나온 뒤 새로 쓴 리포트") + '</div></section>')
    sec_trust = f'<section class="sec w solo">{head_block("trust", more("틀린 곳 알리기"))}</section>'
    sec_brief = (f'<section class="band" id="brief"><div class="w split"><div class="tx">{head_block("brief", more(C["brief_link"]))}</div>'
                 + slot("사진", "image", "4:5", "개장 전 아침, 책상 위 휴대폰") + '</div></section>')
    sec_sectors = (f'<section class="sec w stack" id="sectors">{head_block("sectors", more(C["sectors_link"]))}'
                   + slot("이미지", "image", "21:9 · 휴대폰 1:1", "업종 분석 화면") + '</section>')
    sec_stance = f'<section class="sec w solo">{head_block("stance")}</section>'
    chips = "".join(f'<a href="#">{esc(BY[t]["name"])}<span>{jo(BY[t]["mcap"])}</span></a>' for t in CHIPS if t in BY)
    sec_end = (f'<section class="end w"><h2 class="h2">{C["end"]}</h2>{search_box(ph="종목명 또는 종목코드")}'
               f'<div class="chips">{chips}</div></section>')

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
    theme = ("<script>(function(){var t='light';try{t=localStorage.getItem('kos-theme')||'light'}catch(e){}document.documentElement.setAttribute('data-theme',t)})();</script>"
             "<script>(function(){var m=document.querySelector('meta[name=\"theme-color\"]'),r=document.documentElement;"
             "function tc(){m.setAttribute('content',r.getAttribute('data-theme')==='dark'?'#0d0d0e':'#f9f8f6')}"
             "tc();new MutationObserver(tc).observe(r,{attributes:true,attributeFilter:['data-theme']})})();</script>")
    head = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#f9f8f6"><title>KOSAI — {esc(C["h1_plain"])}</title>'
            f'<meta name="description" content="{esc(C["desc"])}"><meta property="og:title" content="{esc(C["h1_plain"])}">'
            f'<meta property="og:description" content="{esc(C["og_desc"])}">'
            f'<link rel="stylesheet" href="{FONTS}/pretendard-subset.css"><link rel="stylesheet" href="landing.css">{theme}</head><body>')
    return (head + nav() + f"<main>{hero}{sec_report}{sec_fresh}{sec_trust}{sec_brief}{sec_sectors}{sec_stance}{sec_end}</main>"
            + foot() + js + "</body></html>")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    open(os.path.join(OUT, "landing.css"), "w", encoding="utf-8").write(CSS.strip() + "\n")
    html = page()
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
    print(f"preview/concepts/landing/index.html {len(html):,}자 · landing.css {len(CSS):,}자")
