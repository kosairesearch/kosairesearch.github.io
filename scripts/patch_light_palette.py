#!/usr/bin/env python3
"""라이트 모드 팔레트 — 바탕 #f9f8f6 · 검정 #141414. 실사이트·스테이징 모두.

    python3 scripts/patch_light_palette.py [--check]

2026-09-24 사장이 레퍼런스 이미지(따뜻한 회백색 바탕에 먹색 글자)를 주며 "라이트 모드 배경을 이 배경색으로,
검정도 이 검정으로" 라고 했다. 이미지에서 잰 값이 바탕 rgb(249,248,246)=#f9f8f6, 글자 rgb(20,20,20)=#141414 다.
전에는 바탕 #f2f3f5(푸른 기 도는 회색) · 글자 순검정 rgb(0,0,0) 이었다.

무엇을 바꾸나 — 테마 변수(--fg-1)가 있는 페이지 전부, 랜딩(index.html)은 뺀다(항상 다크라 라이트 규칙이 안 먹는다).
  · :root 의 --fg-1:rgb(0,0,0) → rgb(20,20,20), --bg-1:rgb(242,243,250) → rgb(249,248,246)
    (--bg-1 은 '페이지 바탕색' 토큰이다 — 스테이징 stock 의 페이월 흐림이 이 색으로 사라지므로 바탕과 같아야 이음새가 없다)
  · body · body::after 의 background:#f2f3f5 → #f9f8f6
  · <style> 안의 라이트 규칙(선택자에 data-theme="dark" 가 없는 규칙)에 박힌 순검정 #000 → #141414
    — 검정 단추(.btn-primary · .watch-btn · .search-go · 탭 active · 체크박스). 다크 규칙의 #000(흰 단추의 글자)은 그대로.
  · 반투명 검정 rgba(0,0,0,.x)(--fg-2 · --fg-3 · 선 · 그림자)은 '검정'이 아니라 농도라 손대지 않는다.
auth-guard.js 의 가림창·팝업 덮개(rgba(247,248,252,…) — 페이지색 94%·88%)도 새 바탕색을 따른다.

--check 는 바꾸지 않고 옛 팔레트가 남은 자리가 있는지만 본다(check_all.sh 가 돌린다). 생성기(build_admin_page ·
build_consent_page)가 옛 페이지에서 CSS 를 베끼거나 스테이징을 실사이트로 옮길 때 되돌아오는 것을 막으려는 것이다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE_BG_OLD, PAGE_BG = '#f2f3f5', '#f9f8f6'
INK_OLD, INK = 'rgb(0,0,0)', 'rgb(20,20,20)'
BG1_OLD, BG1 = 'rgb(242,243,250)', 'rgb(249,248,246)'
SCRIM_OLD, SCRIM = 'rgba(247,248,252,', 'rgba(249,248,246,'
HEX_BLACK_RE = re.compile(r'#000\b')
STYLE_RE = re.compile(r'<style[^>]*>.*?</style>', re.S)
RULE_RE = re.compile(r'([^{}]*)\{([^{}]*)\}')          # 가장 안쪽 규칙: 선택자 { 선언 }
COMMENT_RE = re.compile(r'/\*.*?\*/', re.S)


def patch_rules(css):
    """라이트 규칙의 #000 만 #141414 로. 선택자(주석 뺀 것)에 data-theme="dark" 가 있으면 다크 규칙이라 둔다."""
    def one(m):
        sel, decl = m.group(1), m.group(2)
        if 'data-theme="dark"' in COMMENT_RE.sub('', sel):
            return m.group(0)
        # 선언마다 본다 — mask-image 의 #000 은 색이 아니라 투명도(알파)라 그대로 둔다
        parts = [d if 'mask' in d.split(':', 1)[0] else HEX_BLACK_RE.sub('#141414', d) for d in decl.split(';')]
        return sel + '{' + ';'.join(parts) + '}'
    return RULE_RE.sub(one, css)


def patch_page(s):
    out = s.replace('--fg-1:' + INK_OLD, '--fg-1:' + INK).replace('--bg-1:' + BG1_OLD, '--bg-1:' + BG1)
    out = out.replace('background:' + PAGE_BG_OLD, 'background:' + PAGE_BG)
    return STYLE_RE.sub(lambda m: patch_rules(m.group(0)), out)


def themed_pages():
    pages = sorted(ROOT.glob('*.html')) + sorted((ROOT / 'staging').glob('*.html'))
    return [p for p in pages if p.name != 'index.html' and '--fg-1:' in p.read_text(encoding='utf-8')]


def main():
    check = '--check' in sys.argv
    targets = [(p, patch_page) for p in themed_pages()]
    targets += [(ROOT / n, lambda s: s.replace(SCRIM_OLD, SCRIM)) for n in ('auth-guard.js', 'staging/auth-guard.js')]
    changed = []
    for p, fn in targets:
        s = p.read_text(encoding='utf-8')
        out = fn(s)
        if out != s:
            changed.append(p.relative_to(ROOT).as_posix())
            if not check:
                p.write_text(out, encoding='utf-8')
    if check:
        if changed:
            print(f"❌ 옛 라이트 팔레트(#f2f3f5 · 순검정)가 남은 파일 {len(changed)}개: {' '.join(changed)}")
            print("   python3 scripts/patch_light_palette.py")
            return 1
        print(f"✅ 라이트 팔레트 {PAGE_BG} · #141414 · {len(targets)}개 확인")
        return 0
    print(f"✅ 라이트 팔레트 적용 {len(changed)}개 / {len(targets)}개")
    if changed:
        print('   ' + ' '.join(changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
