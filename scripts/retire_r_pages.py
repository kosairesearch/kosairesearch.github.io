#!/usr/bin/env python3
"""옛 로봇용 사본(r/{종목코드}.html)을 새 주소(/stock/{종목코드}.html)로 보내는 껍데기로 바꾼다 — 2026-10-03.

    python3 scripts/retire_r_pages.py           # r/*.html 을 껍데기로(이미 껍데기면 그대로 둔다)
    python3 scripts/retire_r_pages.py --check   # 모두 껍데기인지 · 가리키는 페이지가 있는지

왜 지우지 않나
  r/ 주소는 구글 · 네이버에 색인되어 있다. 지우면 404 가 되어 검색에서 들어온 사람이 빈 페이지를 보고, 그 주소에 쌓인
  평판도 새 주소로 넘어가지 않는다. GitHub Pages 는 서버 쪽 이동(301)을 할 수 없어서, 네이버 서치어드바이저가 그런 경우에
  권하는 메타 리프레시(0초)와 canonical(새 주소)로 보낸다 — 구글도 0초 메타 리프레시를 영구 이동으로 본다.
  사람은 바로 새 페이지(머리 · 꼬리가 있는 새 디자인)를 보게 된다. 유입 꼬리표(utm) · #절은 그대로 실어 가고, 넘기기 전에 원래
  출처(검색 결과 등)를 남겨 둔다 — 넘어간 페이지의 방문 통계가 그것을 쓴다(analytics.js · 남기지 않으면 검색 유입이 '직접'으로 잡힌다).
  이미 껍데기인 파일은 회사 이름이 바뀌어도 다시 쓰지 않는다 — 가리키는 주소와 넘김 방식만 견준다(mask).

언제 지우나
  지우지 않는다. 구글 지침이 '리디렉션을 최대한 오랫동안, 일반적으로 최소 1년'(사용자 쪽에서는 무기한)이다 — 그동안
  다른 사이트의 링크 · 북마크 · 검색 결과가 새 주소로 옮겨 간다. 껍데기라 약 1MB 다. 2027-10-05 예약 점검이 다시 본다.
  매일 만들던 scripts/generate_geo_pages.py 는 지웠다 — 돌리면 옛 사본이 되살아난다.
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
<script>try{{sessionStorage.setItem("kos-fwd-ref",document.referrer||"")}}catch(e){{}}location.replace("{target}"+location.search+location.hash)</script>
</head>
<body><p><a href="{target}">{H.escape(label, quote=False)}</a></p></body>
</html>
'''


def mask(text):
    """제목 · 링크 글(회사 이름)을 뺀 모양 — 이름이 바뀌어도 껍데기는 그대로 둔다(가리키는 주소와 넘김 방식만 본다)."""
    return re.sub(r'(<a href="[^"]+">)[^<]*(</a>)', r'\1#\2', re.sub(r'<title>.*?</title>', '<title>#</title>', text))


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
    diff = [n for n, t in want.items() if mask((R / n).read_text(encoding='utf-8')) != mask(t)]
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
