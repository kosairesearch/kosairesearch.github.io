#!/usr/bin/env python3
"""옛 로봇용 사본(r/{종목코드}.html)을 새 주소(/stock/{종목코드}.html)로 보내는 껍데기로 바꾼다 — 2026-10-03.

    python3 scripts/retire_r_pages.py           # r/*.html 을 껍데기로(이미 껍데기면 그대로 둔다)
    python3 scripts/retire_r_pages.py --check   # 모두 껍데기인지 · 가리키는 페이지가 있는지

왜 지우지 않나
  r/ 주소는 구글 · 네이버에 색인되어 있다. 지우면 404 가 되어 검색에서 들어온 사람이 빈 페이지를 보고, 그 주소에 쌓인
  평판도 새 주소로 넘어가지 않는다. GitHub Pages 는 서버 쪽 이동(301)을 할 수 없어서, 네이버 서치어드바이저가 그런 경우에
  권하는 메타 리프레시(0초)와 canonical(새 주소)로 보낸다 — 구글도 0초 메타 리프레시를 영구 이동으로 본다.
  사람은 바로 새 페이지(머리 · 꼬리가 있는 새 디자인)를 보게 된다.

언제 지우나
  검색 엔진이 새 주소를 색인한 뒤(몇 주 — 서치 콘솔 · 서치어드바이저에서 r/ 이 빠졌는지 보고) 폴더째 지운다.
  그 전에는 지우지 말 것. 매일 만들던 scripts/generate_geo_pages.py 는 지웠다 — 돌리면 옛 사본이 되살아난다.
"""
import argparse
import html as H
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stock_page as S  # noqa: E402

R = ROOT / 'r'
TICKER = re.compile(r'^[0-9A-Z]{6}$')


def shell(target, title, label):
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>{H.escape(title, quote=False)}</title>
<link rel="canonical" href="https://kosai.kr{target}">
<meta http-equiv="refresh" content="0; url={target}">
<script>location.replace("{target}"+location.hash)</script>
</head>
<body><p><a href="{target}">{H.escape(label, quote=False)}</a></p></body>
</html>
'''


def plan():
    """{파일 이름: 껍데기 내용} — 지금 r/ 에 있는 파일마다."""
    D = S.load_data()
    pages = {p.stem for p in (ROOT / 'stock').glob('*.html') if TICKER.match(p.stem)}
    out = {}
    for f in sorted(R.glob('*.html')):
        tk = f.stem
        if tk == 'index' or tk not in pages:   # 목록 · 페이지가 없는 종목은 리포트 목록으로
            out[f.name] = shell('/Reports.html', '리포트 | KOSAI', '리포트 목록으로 이동합니다')
            continue
        name = (D['stocks'].get(tk) or {}).get('name') or tk
        out[f.name] = shell(f'/stock/{tk}.html', f'{name}({tk}) 리포트 | KOSAI', f'{name} 리포트로 이동합니다')
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if not R.exists():
        print('r/ 가 없다 — 이미 지웠으면 이 검사는 필요 없다(check_all.sh 에서 뺄 것)')
        return 0
    want = plan()
    diff = [n for n, t in want.items() if (R / n).read_text(encoding='utf-8') != t]
    if a.check:
        if diff:
            print(f'❌ r/ 에 옛 사본이 {len(diff)}장 남았다({", ".join(diff[:5])} …) → python3 scripts/retire_r_pages.py')
            return 1
        print(f'✅ r/ {len(want):,}장 모두 새 주소로 보내는 껍데기')
        return 0
    for n in diff:
        (R / n).write_text(want[n], encoding='utf-8')
    print(f'✅ r/ {len(want):,}장 중 {len(diff):,}장을 껍데기로 바꿨다')
    return 0


if __name__ == '__main__':
    sys.exit(main())
