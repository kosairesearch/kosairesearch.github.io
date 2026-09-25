#!/usr/bin/env python3
"""종목 페이지를 종목마다 미리 만든다 — 큰 회사들이 하는 정적 생성(SSG).

    python3 scripts/build_stock_pages.py --sample 40                    # 표본 40장 → preview/stock/ (기본)
    python3 scripts/build_stock_pages.py 005930 000660                  # 고른 종목만
    python3 scripts/build_stock_pages.py --all --out stock --index      # 전 종목 → stock/ · 검색 허용 (실사이트로 옮길 때)

만드는 것
  · {out}/{ticker}.html          — 리포트 글·표·지표가 HTML 에 다 들어 있다. 로봇도 사람도 이 한 장을 본다.
  · {out}/assets/stock.css · stock.js — 한 벌. 주소에 내용 해시(?v=)를 붙여 바뀔 때만 다시 받는다.
  · {out}/index.html             — 만든 목록(표본을 훑어볼 때)

--index 가 없으면 noindex 다(미리보기용). 실사이트로 옮기는 날의 순서는 docs/design/static-stock-pages.md 에 있다.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402
import stock_page as S  # noqa: E402

TIER_KO = {'v2': '전체 리포트', 'v1': '기본 리포트(옛 형식)', 'none': '리포트 준비 중'}


def pick_sample(D, n):
    """표본: 삼성전자 + 시가총액 상위(v2) + 옛 형식(v1) 몇 + 리포트 없는 종목 몇. 매번 같은 목록."""
    stocks = D['stocks']
    by_mcap = sorted(stocks.values(), key=lambda s: -(s.get('mcap') or 0))
    v2 = [s['ticker'] for s in by_mcap if s['ticker'] in D['v2']]
    v1 = [s['ticker'] for s in by_mcap if s['ticker'] not in D['v2'] and s['ticker'] in D['v1']]
    none = [s['ticker'] for s in by_mcap if s['ticker'] not in D['v2'] and s['ticker'] not in D['v1']]
    out = ['005930']
    for tk in v2[: max(0, n - 10)] + v1[:6] + none[:4]:
        if tk not in out:
            out.append(tk)
    return out[:n] if n < len(out) else out


def write_assets(out_dir):
    css = C.CSS + '\n' + S.PAGE_CSS
    js = S.PAGE_JS
    (out_dir / 'assets').mkdir(parents=True, exist_ok=True)
    (out_dir / 'assets/stock.css').write_text(css, encoding='utf-8')
    (out_dir / 'assets/stock.js').write_text(js, encoding='utf-8')
    return {'css': f'assets/stock.css?v={S.asset_version(css)}', 'js': f'assets/stock.js?v={S.asset_version(js)}'}


def build_index(out_dir, rows, dir_path, index):
    """만든 목록 — 표본을 훑어볼 때. 실사이트에서는 리포트 목록(Reports)이 이 자리다."""
    tr = ''.join(f'<tr><td><a href="{tk}.html">{S.esc(name)}</a></td><td>{tk}</td><td>{S.esc(TIER_KO[tier])}</td><td>{size // 1024}KB</td></tr>' for tk, name, tier, size in rows)
    html = (C.head(f'종목 페이지 {len(rows):,}장 | KOSAI', robots='noindex,nofollow') + '\n<style>\n' + C.CSS + '\n.wrap{padding-top:44px} h1{margin:0 0 8px;font:700 32px/40px var(--font);letter-spacing:-.02em} .sub{margin:0 0 28px;font:400 15px/24px var(--font);color:var(--ink-72)} .tbl td a{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('리포트') + f'''
<main class="wrap"><h1>종목 페이지 {len(rows):,}장</h1><p class="sub">종목마다 미리 만든 페이지. 리포트 글·표·지표가 HTML 에 들어 있어 로봇과 사람이 같은 페이지를 본다. {'검색 허용' if index else '미리보기(noindex)'}.</p>
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>종목</th><th>코드</th><th>리포트</th><th>크기</th></tr></thead><tbody>{tr}</tbody></table></div></main>
''' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n</body>\n</html>')
    (out_dir / 'index.html').write_text(html, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='*')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--out', default='preview/stock')
    ap.add_argument('--index', action='store_true', help='검색 허용(index,follow). 실사이트로 옮길 때만')
    ap.add_argument('--base', default=S.SITE)
    a = ap.parse_args()
    t0 = time.time()
    D = S.load_data()
    if a.all:
        tickers = sorted(D['stocks'].keys() | D['v2'] | D['v1'])
    elif a.tickers:
        tickers = a.tickers
    else:
        tickers = pick_sample(D, a.sample or 40)
    out_dir = ROOT / a.out
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = write_assets(out_dir)
    rows, tiers, total = [], {'v2': 0, 'v1': 0, 'none': 0}, 0
    for tk in tickers:
        try:
            html, tier = S.render(tk, D, inline=False, assets=assets, index=a.index, base=a.base, dir_path=a.out.strip('/'))
        except KeyError:
            print(f'  · {tk}: 시세도 리포트도 없어 건너뜀')
            continue
        (out_dir / f'{tk}.html').write_text(html, encoding='utf-8')
        size = len(html.encode('utf-8'))
        total += size
        tiers[tier] += 1
        rows.append((tk, D['stocks'].get(tk, {}).get('name', tk), tier, size))
    build_index(out_dir, rows, a.out, a.index)
    n = len(rows)
    print(f'✅ {out_dir} · {n:,}장 (전체 {tiers["v2"]} · 옛 형식 {tiers["v1"]} · 준비 중 {tiers["none"]}) · 평균 {total // max(n, 1) // 1024}KB · 합계 {total / 1e6:,.1f}MB · {time.time() - t0:.1f}초'
          + (f' · 전 종목({len(D["stocks"]):,})이면 약 {total / max(n, 1) * len(D["stocks"]) / 1e6:,.0f}MB' if not a.all else ''))


if __name__ == '__main__':
    main()
