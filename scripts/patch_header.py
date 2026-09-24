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
  2. </body> 앞에 <style id="kosNav"> 와 스크립트 한 덩이를 넣는다(있으면 갈아 끼운다). 맨 아래라
     페이지의 .nav 규칙(스테이징 띠 밑으로 내리는 top 까지)을 다 이긴다.
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
       생기는 네모 박스 없애줘. 글씨에 빛만 들어오게", 사장). 지금 페이지를 알리는 .active 상자는 둔다.
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
MARK = 'id="kosNav"'
BLOCK = '''<!-- 헤더 — 상자 없이 · 내리면 화면 폭 띠 · 메뉴 가운데. scripts/patch_header.py 가 넣는다. 손으로 고치지 말 것. -->
<style id="kosNav">
:root{--nav-bar:rgba(255,255,255,.58);--nav-line:rgba(0,0,0,.06)}
:root[data-theme="dark"]{--nav-bar:rgba(14,14,22,.55);--nav-line:rgba(255,255,255,.08)}
.nav{top:var(--kos-bar-h,0px);margin:0;max-width:none;width:auto;min-height:60px;border:0;border-radius:0;
  padding:11px calc(max(var(--pad),(100% - 1120px)/2) + 12px) 11px calc(max(var(--pad),(100% - 1120px)/2) + 16px);
  background:transparent;box-shadow:none;-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px);
  transition:background-color .25s ease,box-shadow .25s ease}
.nav.scrolled{background:var(--nav-bar);box-shadow:0 1px 0 var(--nav-line)}
.nav-spacer{min-height:32px}
.nav-links{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);margin-left:0;gap:14px}
.nav-links a:hover,.nav .icon-btn:hover,:root[data-theme="dark"] .nav-links a:hover,:root[data-theme="dark"] .nav .icon-btn:hover{background:transparent}
.mobile-menu{top:calc(60px + var(--kos-bar-h,0px))}
</style>
<script>
(function(){
  var nav=document.querySelector('.nav'); if(!nav) return; var tick=false;
  function upd(){ tick=false; nav.classList.toggle('scrolled',(window.scrollY||document.documentElement.scrollTop)>32); }
  addEventListener('scroll',function(){ if(!tick){ tick=true; requestAnimationFrame(upd); } },{passive:true});
  upd();
})();
</script>
'''
BLOCK_RE = re.compile(r'<!-- 헤더 — 상자 없이[^\n]*\n<style id="kosNav">.*?</script>\n', re.S)


def has_std_header(s):
    m = re.search(r'<nav class="nav[^"]*"[^>]*>(.*?)</nav>', s, re.S)
    return bool(m and 'class="brand"' in m.group(1) and 'class="nav-links"' in m.group(1)
                and 'class="nav-spacer"' in m.group(1))


def apply(s):
    """헤더가 있는 페이지의 본문에 적용한 결과를 돌려준다. 없으면 그대로."""
    if not has_std_header(s):
        return s
    s = s.replace('<nav class="nav glass"', '<nav class="nav"')
    s = BLOCK_RE.sub('', s)
    if '</body>' not in s:
        raise SystemExit('❌ </body> 가 없습니다')
    return s.replace('</body>', BLOCK + '</body>', 1)


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
