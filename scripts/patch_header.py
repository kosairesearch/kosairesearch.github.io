#!/usr/bin/env python3
"""헤더를 Resend 식으로 — 상자 없이, 조금 내리면 화면 폭 띠, 메뉴는 가운데.

    python3 scripts/patch_header.py [폴더=staging] [--check]

왜 있나. 2026-09-24 사장: "상단 헤더에 박스가 없고 그냥 배경에 로고라든지 있잖아. 근데 조금만
스크롤해서 내리면 박스가 또 저렇게 생겨 · 다른 페이지에서도 헤더 박스 없애야지 · 홈, 리포트,
업종 분석 버튼들 중앙으로 옮겨줘 resend 웹사이트처럼". 페이지마다 CSS 가 따로 박혀 있어(공유
스타일시트가 없다) 손으로 열여섯 장을 고치면 하나는 빠진다. 그래서 patch_biz_footer.py 처럼
한 스크립트가 같은 것을 같은 자리에 넣는다. 실사이트로 옮길 때는 폴더만 바꿔 다시 돌린다.

무엇을 하나 — 표준 헤더(<nav class="nav"> 안에 .brand · .nav-links · .nav-spacer)가 있는 페이지만:
  1. <nav class="nav glass"> 의 glass 를 뗀다 — 유리 상자(배경·테두리·그림자·둥근 모서리)가 없어진다.
  2. </head> 앞에 <style id="kosNav">(+ 테마 선적용 스크립트)를, </body> 앞에 스크롤 스크립트를
     넣는다(있으면 갈아 끼운다). 처음에는 둘 다 본문 끝에 넣었는데, 페이지를 옮길 때마다 첫 그림에
     옛 헤더(왼쪽 정렬 메뉴 · 지금 페이지 상자)가 잠깐 그려진 뒤 바뀌어 "0.1초 깜빡이고 단추 둘레에
     상자가 보인다"(사장)고 했다. 첫 그림부터 맞으려면 스타일이 <head> 에 있어야 한다. 그러면 본문
     안의 스테이징 띠 스타일(.nav{top:…} · .mobile-menu{top:…})이 뒤에 오므로, 선택자마다 html 을
     앞에 붙여 특이도로 이긴다(순서에 기대지 않는다).
     · 테마도 같은 이유로 <head> 에서 먼저 정한다 — 원래는 본문 끝 applyTheme() 가 정해서 다크로
       쓰는 사람에게는 매 이동마다 밝은 바탕이 한 번 번쩍였다. 저장 키 kos-theme, 기본 다크,
       랜딩은 늘 다크(본문의 "랜딩은 항상 다크" 표시로 안다).
     · @view-transition{navigation:auto} — 같은 사이트 안에서 페이지를 옮길 때 브라우저가 옛 화면과
       새 화면을 0.25초 겹쳐 보여 준다(크롬 126+ · 사파리 18.2+, 나머지는 그냥 넘어간다).
       Resend 처럼 "부드럽게 전환"되는 느낌은 여기서 온다.
     · 글꼴 미리 받기(<link rel="preload"> 넷: 400·500·600·700) — GitHub Pages 는 모든 파일에
       max-age=600 을 붙이므로 10분이 지나면 브라우저가 글꼴을 서버에 다시 물어본다(304). 그 왕복
       동안 글씨가 대체 글꼴로 그려졌다가 바뀌어 "가끔 깜빡"였다. 머리에서 먼저 물어보면 본문의
       큰 스크립트(data/stocks.js)를 받는 사이에 답이 와서 첫 그림부터 제 글꼴이다. 주소는 페이지의
       @font-face 에서 읽는다(실사이트 fonts/ · 스테이징 ../fonts/).
     · .nav 를 화면 폭으로 펴고, 안쪽 여백을 max(--pad, (100% - 1120px)/2) 로 잡아 로고·단추가
       전과 같은 기둥(1120px) 안에 놓이게 한다. 높이는 60px 이고 글자·단추는 그 한가운데다 —
       처음에는 위 12px 를 투명 테두리로 두고 70px 였는데 띠가 생기면 글자가 아래로 치우쳐
       보였다("위 아래 간격이 다르잖아", 사장). Resend 처럼 조금 더 위로(글자 중심 38 → 30px).
       휴대폰 메뉴는 그 밑(60px + 스테이징 띠)에 붙인다.
     · 맨 위에서는 투명. 32px 넘게 내리면 .scrolled — 반투명 배경 + 아래 선(box-shadow 라 높이가
       안 변한다). 흐림(backdrop-filter)은 늘 켜 둔다 — 맨 위에서는 뒤에 바탕뿐이라 표가 안 나고,
       켰다 껐다 하면 툭 튄다. 배경은 라이트 흰색 .58 · 다크 #0e0e16 .55 — .72 로 했더니
       "박스가 너무 진해, Resend 처럼 조금만 더 투명하게"(사장).
     · 메뉴 글자와 아이콘 단추에 마우스를 올리면 네모 상자 없이 글자만 밝아진다("호버했을 때
       생기는 네모 박스 없애줘. 글씨에 빛만 들어오게", 사장). 지금 페이지를 알리는 .active 도 상자 없이
       글자만 밝고 굵게("홈 버튼에 저렇게 네모 박스가 유지되어 있는데 저것도 없애줘", 사장).
     · .nav-links 는 헤더 가운데에 절대 배치 — 로고·단추 폭과 상관없이 화면 가운데(Resend 처럼).
       메뉴 사이는 14px(글자 사이 40px) — 2px 였을 때 "버튼들이 너무 붙어있어"(사장).
       휴대폰(767px 이하)에서는 전처럼 숨고 메뉴 단추가 대신한다.
     · .nav-spacer 에 최소 높이를 줘 단추가 없는 페이지(랜딩은 테마 단추를 숨긴다)도 높이가 준다.
     · 색은 --nav-bar · --nav-line 변수다. 랜딩(항상 남색)은 body 에서 제 값으로 덮는다.
  3. 스테이징 띠(.kos-staging-bar)가 있는 페이지는 그 밑에 붙는다(top: var(--kos-bar-h)).

--check 는 바꾸지 않고, 표준 헤더가 있는 페이지가 모두 이 상태인지만 본다(check_all.sh 가 돌린다).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEME_JS = "(function(){var t='dark';try{t=localStorage.getItem('kos-theme')||'dark'}catch(e){}document.documentElement.setAttribute('data-theme',t)})();"
THEME_JS_DARK = "document.documentElement.setAttribute('data-theme','dark');"
HEAD = '''<!-- 헤더 — 상자 없이 · 내리면 화면 폭 띠 · 메뉴 가운데. scripts/patch_header.py 가 넣는다. 손으로 고치지 말 것. -->
<script id="kosTheme">%s</script>
<style id="kosNav">
@view-transition{navigation:auto}
:root{--nav-bar:rgba(255,255,255,.58);--nav-line:rgba(0,0,0,.06)}
:root[data-theme="dark"]{--nav-bar:rgba(14,14,22,.55);--nav-line:rgba(255,255,255,.08)}
html .nav{top:var(--kos-bar-h,0px);margin:0;max-width:none;width:auto;min-height:60px;border:0;border-radius:0;
  padding:11px calc(max(var(--pad),(100%% - 1120px)/2) + 12px) 11px calc(max(var(--pad),(100%% - 1120px)/2) + 16px);
  background:transparent;box-shadow:none;-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
  transition:background-color .25s ease,box-shadow .25s ease}
html .nav.scrolled{background:var(--nav-bar);box-shadow:0 1px 0 var(--nav-line)}
html .nav-spacer{min-height:32px}
html .nav-links{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);margin-left:0;gap:14px}
html .nav-links a:hover,html .nav .icon-btn:hover,html:root[data-theme="dark"] .nav-links a:hover,html:root[data-theme="dark"] .nav .icon-btn:hover{background:transparent}
html .nav-links a.active,html:root[data-theme="dark"] .nav-links a.active{background:transparent}
html .mobile-menu{top:calc(60px + var(--kos-bar-h,0px))}
</style>
'''
BODY = '''<script id="kosNavJs">
/* 헤더 띠 — 32px 넘게 내리면 .scrolled (head 의 #kosNav 참고). 프레임마다 한 번만 본다. */
(function(){
  var nav=document.querySelector('.nav'); if(!nav) return; var tick=false;
  function upd(){ tick=false; nav.classList.toggle('scrolled',(window.scrollY||document.documentElement.scrollTop)>32); }
  addEventListener('scroll',function(){ if(!tick){ tick=true; requestAnimationFrame(upd); } },{passive:true});
  upd();
})();
</script>
'''
# 전에 넣은 것(본문 끝의 스타일+스크립트 한 덩이)과 지금 것(head 의 스타일 · 본문 끝의 스크립트) 모두 걷는다
OLD_RE = re.compile(r'<!-- 헤더 — 상자 없이[^\n]*\n<style id="kosNav">.*?</script>\n', re.S)
HEAD_RE = re.compile(r'<!-- 헤더 — 상자 없이[^\n]*\n<script id="kosTheme">.*?</style>\n(?:<link rel="preload" as="font"[^\n]*\n)*', re.S)
BODY_RE = re.compile(r'<script id="kosNavJs">.*?</script>\n', re.S)


def has_std_header(s):
    m = re.search(r'<nav class="nav[^"]*"[^>]*>(.*?)</nav>', s, re.S)
    return bool(m and 'class="brand"' in m.group(1) and 'class="nav-links"' in m.group(1)
                and 'class="nav-spacer"' in m.group(1))


def apply(s):
    """헤더가 있는 페이지의 본문에 적용한 결과를 돌려준다. 없으면 그대로."""
    if not has_std_header(s):
        return s
    s = s.replace('<nav class="nav glass"', '<nav class="nav"')
    s = OLD_RE.sub('', s)
    s = HEAD_RE.sub('', s)
    s = BODY_RE.sub('', s)
    if '</head>' not in s or '</body>' not in s:
        raise SystemExit('❌ </head> 나 </body> 가 없습니다')
    theme = THEME_JS_DARK if '랜딩은 항상 다크' in s else THEME_JS
    m = re.search(r'url\("([^"]*)Pretendard-Regular\.woff2"\)', s)
    pre = ''.join(f'<link rel="preload" as="font" type="font/woff2" crossorigin href="{m.group(1)}Pretendard-{w}.woff2">\n'
                  for w in ('Regular', 'Medium', 'SemiBold', 'Bold')) if m else ''
    s = s.replace('</head>', (HEAD % theme) + pre + '</head>', 1)
    return s.replace('</body>', BODY + '</body>', 1)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    check = '--check' in sys.argv
    folder = ROOT / (args[0] if args else 'staging')
    pages = sorted(p for p in folder.glob('*.html'))
    changed, done, skipped = [], [], []
    for p in pages:
        s = p.read_text(encoding='utf-8')
        if not has_std_header(s):
            skipped.append(p.name)
            continue
        out = apply(s)
        if out == s:
            done.append(p.name)
        else:
            changed.append(p.name)
            if not check:
                p.write_text(out, encoding='utf-8')
    if check:
        if changed:
            print(f"❌ 헤더가 아직 옛 모양인 페이지 {len(changed)}장: {' '.join(changed)}")
            print("   python3 scripts/patch_header.py " + folder.name)
            return 1
        print(f"✅ 헤더 {len(done)}장 모두 상자 없는 모양 · 건너뜀 {len(skipped)}장({' '.join(skipped)})")
        return 0
    print(f"✅ 헤더 고침 {len(changed)}장 · 이미 돼 있음 {len(done)}장 · 표준 헤더 없음 {len(skipped)}장({' '.join(skipped)})")
    if changed:
        print('   ' + ' '.join(changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
