#!/usr/bin/env python3
"""디자인 미리보기 — 실사이트 페이지 한 장을 preview/ 에 복사하고 덮어쓰기 스타일을 얹는다.

    python3 scripts/make_preview.py stock.html <override.css>

왜 있나(2026-09-25). 사장이 디자인을 통째로 맡기며 "페이지 하나부터 정하자" 고 했다. 스테이징은 유료화
작업이 들어 있어 섞을 수 없고(CLAUDE.md), 스크린샷으로는 휴대폰에서의 느낌을 알 수 없다. 그래서 링크
없는 미리보기 폴더 kosai.kr/preview/ 에 그 한 장을 두고 실기기(사파리)로 본다. 검색에는 안 나오게 한다
(robots.txt Disallow · noindex). 디자인이 정해지면 같은 규칙을 실사이트·스테이징에 스크립트로 넣고 이
폴더는 지운다.

무엇을 하나. 페이지의 상대 경로(data/ · fonts/ · assets/ · *.js · *.html 링크 · fetch('data/…'))를
루트 절대 경로(/data/ …)로 바꿔 어디에 있어도 같은 자료를 읽게 하고, </head> 앞에
<link rel="stylesheet" href="/preview/<css>"> 와 noindex 메타를 넣는다. 원본 페이지는 손대지 않는다.
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'preview'


def absolutize(s):
    # src="data/x.js" · src="auth-state.js?v=" · href="Home.html" · href="fonts/…" · url("fonts/…") · fetch('data/…')
    s = re.sub(r'(src|href)="(?!https?:|//|#|/|mailto:|tel:|javascript:)([^"]+)"', r'\1="/\2"', s)
    s = re.sub(r'url\("(?!https?:|//|/|data:)([^"]+)"\)', r'url("/\1")', s)
    s = re.sub(r"url\('(?!https?:|//|/|data:)([^']+)'\)", r"url('/\1')", s)
    s = re.sub(r"(fetch\()'data/", r"\1'/data/", s)
    s = re.sub(r'(fetch\()"data/', r'\1"/data/', s)
    return s


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    page, css = sys.argv[1], Path(sys.argv[2])
    src = (ROOT / page).read_text(encoding='utf-8')
    out = absolutize(src)
    css_name = css.name
    inject = (f'<meta name="robots" content="noindex,nofollow">\n'
              f'<!-- 디자인 미리보기 — scripts/make_preview.py 가 만든다. 원본은 /{page} -->\n'
              f'<link rel="stylesheet" href="/preview/{css_name}">\n')
    assert '</head>' in out
    out = out.replace('</head>', inject + '</head>', 1)
    OUT.mkdir(exist_ok=True)
    (OUT / page).write_text(out, encoding='utf-8')
    shutil.copyfile(css, OUT / css_name)
    n_rel = len(re.findall(r'(src|href)="(?!https?:|//|#|/|mailto:|tel:|javascript:)', out))
    print(f'✅ preview/{page} + preview/{css_name} · 남은 상대 경로 {n_rel}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
