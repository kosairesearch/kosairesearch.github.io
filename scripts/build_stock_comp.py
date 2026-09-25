#!/usr/bin/env python3
"""종목 리포트 페이지 — 새 디자인 시안(comp) 한 장. 그리는 일은 stock_page.py 가 한다.

    python3 scripts/build_stock_comp.py [종목코드] [출력 경로]    # 기본 005930 → preview/stock.html

2026-09-25 사장: 덧칠(글꼴·선만 바꾼 것)은 리디자인이 아니다. 레이아웃·위치를 다 바꿔도 되니 애플·Fey 급으로.
그래서 기존 stock.html 위에 CSS 를 얹지 않고, 리포트 JSON(data/reports_v2)·시세(data/stocks.js)로 페이지를
처음부터 그린다. 기능(관심종목·로그인·한/영)은 여기서는 그림만이다.

이 파일은 CSS·JS 를 안에 넣은 한 장짜리 시안이다. 전 종목을 미리 만드는 실제 생성기는
scripts/build_stock_pages.py — 같은 stock_page.render 를 쓰므로 둘의 옷은 늘 같다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import stock_page as S  # noqa: E402

# 다른 시안 생성기가 참고하던 이름들 — 그대로 내보낸다
SECTIONS = S.SECTIONS_V2
esc, chunk, paras, fwon, fjo, pct, bar_chart = S.esc, S.chunk, S.paras, S.fwon, S.fjo, S.pct, S.bar_chart


def build(tk, out_path):
    D = S.load_data()
    html, tier = S.render(tk, D, inline=True, index=False, dir_path='preview')
    # 시안 한 장의 주소는 preview/stock.html 이다 — canonical·OG 주소를 거기에 맞춘다
    html = html.replace(f'{S.SITE}/preview/{tk}.html', f'{S.SITE}/preview/stock.html')
    html = html.replace(' | KOSAI</title>', ' — 디자인 시안 | KOSAI</title>', 1)
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'✅ {out_path} · {len(html):,}자 · {tier}')


if __name__ == '__main__':
    tk = sys.argv[1] if len(sys.argv) > 1 else '005930'
    out = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'preview/stock.html')
    build(tk, out)
