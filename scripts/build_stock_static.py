#!/usr/bin/env python3
"""실사이트 종목 페이지 — 종목마다 미리 만든 HTML(stock/{종목코드}.html). 2026-10-03 사장 결정('1안').

    python3 scripts/build_stock_static.py              # stock/ 를 다시 만든다(바뀐 페이지만 쓴다)
    python3 scripts/build_stock_static.py 005930 ...   # 고른 종목만(시험용 · 없어진 종목을 지우지 않는다)
    python3 scripts/build_stock_static.py --check      # 공용 파일 · 페이지 틀이 생성기와 같은지, 종목이 빠지거나 남지 않았는지

왜
  옛 실사이트의 종목 화면(stock.html?ticker=)은 2,685 종목이 같이 쓰는 빈 틀이라, 자바스크립트를 돌리지 않는 검색 · AI 로봇에게는
  모든 종목이 같은 빈 페이지였다. 그래서 로봇용 사본(r/{종목코드}.html)을 따로 만들어 왔고, 검색으로 들어온 사람이 머리도 꼬리도
  없는 그 사본에 떨어졌다. 사장 "대기업처럼 해줘"(2026-09-25) · "1안"(2026-10-03): 사람과 로봇이 같은 페이지를 보게 종목마다
  완성된 페이지를 미리 만든다. 설계와 옮긴 순서는 docs/design/static-stock-pages.md.

어떻게
  · 글은 리포트 상세 화면의 스크립트(build_stock_staging.PAGE_JS 의 실사이트 판)를 노드에서 가짜 문서로 돌려 받는다
    (scripts/prerender_stock.mjs). 같은 코드가 같은 자료로 그리므로 미리 그린 글과 브라우저가 그리는 글이 글자 하나까지 같다.
    파이썬 판(stock_page.render)은 문단 자르기가 달라 쓰지 않는다(CLAUDE.md '리포트 본문 문단 자르는 방식').
  · 브라우저는 자료(시세 · 리포트)를 받은 뒤 같은 스크립트로 한 번 더 그려 지문(kosHash)을 견준다 — 같으면 그대로 두고, 그사이
    자료가 바뀌었으면 새로 그린다. 영어로 정한 사람에게는 처음부터 영어로 그린다(미리 그린 한국어 글은 가려 둔다 — PRE_CSS).
  · 옷(CSS) · 스크립트 · 영어 사전은 stock/assets/ 에 한 벌. 주소에 내용 해시(?v=)를 붙인다. 페이지마다 다른 것은 머리(제목 · 설명 ·
    canonical · 공유 · 구조화 데이터)와 본문뿐이다.
  · 머리 · 꼬리 · 모듈은 실사이트 다른 페이지와 같은 생성기(comp_common live 모드)다. 폴더 한 단 아래라 모듈 주소를 맨 위부터 쓴다.
  · 시세는 매일 바뀌므로 데이터 갱신 작업(update_data.yml)이 매일, 새 상장은 신규 상장 작업(new_listings.yml)이 그 자리에서, 리포트가
    새로 쓰이면 리포트 워치독(30분)이 다시 만든다. 바뀐 페이지만 쓰므로 자료가 그대로면 커밋도 없다.
  · 종목 하나가 그리다 멈추면 그 종목만 옛 페이지로 두고 나머지를 만든 뒤 실패로 끝난다. 시세 자료가 지금 페이지 수의 절반 아래로 줄면 멈춘다.
  · 모듈의 ?v= 도장은 여기서 찍는다(stamp_assets.py 는 루트 · 스테이징만 본다) — 모듈을 고쳤으면 이것(또는 build_live.py)을 돌린다.

옛 주소
  · stock.html?ticker= — 껍데기(build_stock_staging, 실사이트 판)가 머리 맨 앞에서 /stock/{종목코드}.html 로 넘긴다.
  · r/{종목코드}.html — scripts/retire_r_pages.py 가 새 주소로 보내는 껍데기(메타 리프레시 + canonical)로 한 번 갈아 두었다.
"""
import argparse
import hashlib
import html as H
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402
import stock_page as S  # noqa: E402
import build_stock_staging as B  # noqa: E402

OUT = ROOT / 'stock'
TICKER = re.compile(r'^[0-9A-Z]{6}$')
SITE = 'https://kosai.kr'

# 영어로 정한 사람에게 미리 그린 한국어 글이 비치지 않게 — 번역 엔진(i18n.js)이 머리에서 html[lang] 을 정하고, 페이지 스크립트가
# 영어로 다시 그리며 data-pre 를 걷는다. 스크립트가 끝내 못 뜨면 4초 뒤 그대로 보인다(번역 엔진의 1.5초 가림과 같은 장치).
PRE_CSS = 'html[lang="en"] #page[data-pre]{visibility:hidden;animation:kosPreShow 0s 4s forwards} @keyframes kosPreShow{to{visibility:visible}}'


def digest(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]


def tickers():
    """페이지를 만들 종목 — 시세가 있는 종목 + 리포트가 있는 종목(상장 폐지 뒤에도 리포트는 남는다). 옛 화면이 그리던 범위와 같다."""
    D = S.load_data()
    return sorted(t for t in (D['stocks'].keys() | D['v2'] | D['v1']) if TICKER.match(t))


def listed():
    """시세 자료(data/stocks.js)에 있는 종목. 나머지(상장 폐지 · 합병 · 거래 정지 등으로 리포트만 남은 종목)는 페이지는 두되 검색에
    올리지 않는다(noindex · 사이트맵 제외) — 옛 실사이트에서도 사이트맵 · 로봇용 사본(r/)에 없던 종목이다. 시세가 다시 생기면 저절로 올라간다."""
    return set(S.load_data()['stocks'])


def shell_dict():
    """영어 사전 — 옛 주소 껍데기(stock.html)의 사전과 같은 것. 페이지 스크립트 · 모듈에 나오는 문구로 고른다(comp_common.i18n_block)."""
    page = C.finish(B.build_html(), 'stock.html')
    m = re.search(r'<script type="application/json" data-kos-i18n>(.*?)</script>\n<script>window.KOSi18n&&KOSi18n.load\(\)</script>', page, re.S)
    assert m, '껍데기에서 영어 사전을 찾지 못했다'
    return json.loads(m.group(1).replace('<\\/', '</'))


def assets():
    """stock/assets/ 의 세 파일 — {이름: 내용}. 껍데기(stock.html)의 <style> · <script> 와 같은 순서로 묶는다."""
    dic = json.dumps(shell_dict(), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    return {
        'stock.css': C.CSS + '\n' + S.PAGE_CSS + '\n' + PRE_CSS + '\n',
        'stock.js': C.TOC_JS + '\n' + C.JS + '\n' + S.CHART_FIT_JS + '\n' + B.page_js() + '\n',
        # 영어일 때만 읽는다 — 다른 페이지의 페이지 끝 사전(KOSi18n.load)과 같은 조건
        'i18n-dict.js': "if(window.KOSi18n&&KOSi18n.lang==='en')KOSi18n.register(" + dic + ');\n',
    }


def prerender(tks, page_js):
    """노드로 미리 그린다 — 종목마다 dict 를 하나씩 내놓는다(prerender_stock.mjs 의 출력 한 줄)."""
    node = shutil.which('node')
    if not node:
        raise SystemExit('❌ node 가 없다 — 종목 페이지는 노드로 미리 그린다')
    with tempfile.TemporaryDirectory() as td:
        js = Path(td) / 'stock-page.js'
        js.write_text(page_js, encoding='utf-8')
        spec = json.dumps({'root': str(ROOT), 'js': str(js), 'tickers': tks})
        p = subprocess.Popen([node, str(ROOT / 'scripts/prerender_stock.mjs')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, encoding='utf-8')
        p.stdin.write(spec)
        p.stdin.close()
        for line in p.stdout:
            if line.strip():
                yield json.loads(line)
        err = p.stderr.read()
        if p.wait():
            raise SystemExit(f'❌ 미리 그리기 실패: {err.strip()[:500]}')


def abs_modules(page):
    """도장 찍은 루트 모듈 주소(src="auth-state.js?v=…")를 맨 위부터 쓴 주소로 — 페이지가 /stock/ 아래에 있다."""
    return re.sub(r'(\bsrc=")([A-Za-z0-9_-]+\.js\?v=[0-9a-f]{8}")', r'\1/\2', page)


def page_html(r, ver, on_market=True):
    """종목 한 장. r 은 미리 그린 결과(prerender_stock.mjs 한 줄), ver 는 공용 파일의 내용 해시. on_market=False 는 시세 자료에 없는 종목(noindex).
    본문 자리에 미리 그릴 때의 리포트 형식(data-pre-tier)과 시세 유무(data-pre-known)를 단다 — 화면이 자료를 못 받았을 때(통신 끊김 ·
    검색 로봇의 렌더링) 미리 그린 글을 '준비 중'으로 덮지 않는 근거다(build_stock_staging.PAGE_JS render)."""
    tk, title, desc, url = r['tk'], r['title'], r['desc'] or '', r['canonical']
    assert url == f'{SITE}/stock/{tk}.html' and r['ogUrl'] == url, f'{tk}: 대표 주소가 다르다 ({url})'
    extra = (C.seo_tags(url, title, desc, robots=None if on_market else 'noindex,follow', og_type='article')
             + '<script type="application/ld+json" id="kos-jsonld">' + (r['ld'] or '{}').replace('</', '<\\/') + '</script>\n'
             + f'<link rel="stylesheet" href="/stock/assets/stock.css?v={ver["stock.css"]}">\n')
    head = C.head(H.escape(title, quote=False), extra=extra)
    body = (f'\n</head>\n<body>\n{C.nav("리포트")}\n'
            f'<main class="wrap" id="page" data-tk="{tk}" data-pre="{r["hash"]}" data-pre-tier="{r["tier"]}" data-pre-known="{1 if on_market else 0}">'
            f'{r["h"]}</main>\n'
            f'{C.FOOTER}\n'
            '<script src="/data/stocks.js"></script>\n<script src="/data/valuation.js"></script>\n'
            f'<script src="/stock/assets/stock.js?v={ver["stock.js"]}"></script>\n'
            f'<script src="/stock/assets/i18n-dict.js?v={ver["i18n-dict.js"]}"></script>\n'
            + ''.join(f'<script type="module" src="{m}"></script>\n' for m in C.LIVE_PAGE_SCRIPTS['stock.html'])
            + '<script src="lenis.js"></script>\n<script src="smooth-scroll.js"></script>\n</body>\n</html>\n')
    return abs_modules(C.live_stamp(head + body))


# /stock/ 자체 — 목록은 리포트 페이지다. 주소를 줄여 들어온 사람을 그리로 보낸다(Screener.html 껍데기와 같은 방식).
INDEX = '''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>리포트 | KOSAI</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="https://kosai.kr/Reports.html">
<meta http-equiv="refresh" content="0; url=/Reports.html">
<script>location.replace("/Reports.html")</script>
</head>
<body><p><a href="/Reports.html">리포트 목록으로 이동합니다</a></p></body>
</html>
'''


def pages_js(tks):
    """옛 주소 껍데기(stock.html)가 넘길지 정하는 목록 — 페이지가 있는 종목코드. 껍데기는 주소에 ?v= 없이 부른다(10분 캐시 안에서 늦어도
    새 종목은 '찾을 수 없습니다' 대신 그다음 방문부터 넘어간다)."""
    return ('/* 종목마다 미리 만든 페이지가 있는 종목코드 — scripts/build_stock_static.py 가 쓴다. 옛 주소 껍데기(stock.html)가 넘길지 정한다 */\n'
            'window.KOS_STOCK_PAGES="' + ','.join(tks) + '";\n')


def on_disk():
    return sorted(p.stem for p in OUT.glob('*.html') if TICKER.match(p.stem))


def write_if_changed(path, text):
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return True


def build(only=None):
    C.set_mode('live')
    files = assets()
    ver = {k: digest(v) for k, v in files.items()}
    changed = sum(write_if_changed(OUT / 'assets' / k, v) for k, v in files.items())
    changed += write_if_changed(OUT / 'index.html', INDEX)
    tks = only or tickers()
    have = {p.stem for p in OUT.glob('*.html') if TICKER.match(p.stem)}
    if not only and have and len(tks) < len(have) * 0.5:
        raise SystemExit(f'❌ 만들 종목이 {len(tks)}개뿐이다(지금 {len(have)}장) — 자료가 깨졌을 수 있어 아무것도 지우지 않고 멈춘다')
    market = listed()
    # 시세 자료가 갑자기 크게 줄면(수집이 일부만 받은 날) 대부분의 페이지가 noindex · 시세 없음으로 바뀌고 사이트맵이 줄어든다 — 멈춘다
    if not only and have and len(market) < len(have) * 0.5:
        raise SystemExit(f'❌ 시세 자료의 종목이 {len(market)}개뿐이다(지금 페이지 {len(have)}장) — 자료가 깨졌을 수 있어 아무것도 바꾸지 않고 멈춘다')
    tiers, made, wrote, failed = {}, set(), 0, []
    for r in prerender(tks, B.page_js()):
        if r.get('error'):   # 그 종목만 그리다 멈췄다(깨진 리포트 파일 등) — 옛 페이지를 그대로 두고 끝에 실패로 알린다
            failed.append((r['tk'], r['error']))
            continue
        made.add(r['tk'])
        tiers[r['tier']] = tiers.get(r['tier'], 0) + 1
        wrote += write_if_changed(OUT / f'{r["tk"]}.html', page_html(r, ver, r['tk'] in market))
    gone = 0
    if not only:
        for tk in sorted(have - made - {t for t, _ in failed}):
            (OUT / f'{tk}.html').unlink()
            gone += 1
    changed += write_if_changed(OUT / 'assets' / 'pages.js', pages_js(on_disk()))
    print(f'✅ stock/ {len(made):,}장 (전체 {tiers.get("v2", 0):,} · 옛 형식 {tiers.get("v1", 0):,} · 준비 중 {tiers.get("none", 0):,} · '
          f'시세 없음 {len(made - market):,}) · 새로 쓴 페이지 {wrote:,} · 지운 페이지 {gone} · 공용 파일 갱신 {changed}')
    odd = {k: v for k, v in tiers.items() if k not in ('v2', 'v1', 'none')}
    if odd:
        raise SystemExit(f'❌ 그릴 수 없는 종목이 있다: {odd}')
    if failed:
        raise SystemExit(f'❌ 그리다 멈춘 종목 {len(failed)}개 — 옛 페이지를 그대로 두었다(리포트 파일을 확인할 것):\n   '
                         + '\n   '.join(f'{t}: {e[:200]}' for t, e in failed[:10]))


# ── 검사 ────────────────────────────────────────────────────────────────────
def skeleton(page):
    """종목마다 다른 것(제목 · 설명 · 공유 문구 · 구조화 데이터 · 본문 · 종목코드)을 지운 틀 — 모든 페이지가 같아야 한다."""
    s = re.sub(r'<title>.*?</title>', '<title>#</title>', page, count=1, flags=re.S)
    s = s.replace('<meta name="robots" content="noindex,follow">\n', '', 1)
    s = re.sub(r'(<meta (?:name|property)="(?:description|og:title|og:description|twitter:title|twitter:description)" content=")[^"]*"', r'\1#"', s)
    s = re.sub(r'(<script type="application/ld\+json" id="kos-jsonld">).*?(</script>)', r'\1#\2', s, count=1, flags=re.S)
    s = re.sub(r'<main class="wrap" id="page" data-tk="[0-9A-Z]{6}" data-pre="[0-9a-f]{8}" data-pre-tier="(?:v2|v1|none)" data-pre-known="[01]">.*?</main>',
               '<main #>#</main>', s, count=1, flags=re.S)
    return re.sub(r'/stock/[0-9A-Z]{6}\.html', '/stock/#.html', s)


# 실사이트에 있으면 안 되는 것 — build_live.FORBIDDEN 과 같은 뜻(멤버십 · 결제 · 스테이징 · 시안의 흔적)
FORBIDDEN = ('pricing.html', 'checkout.html', 'billing.html', 'paywall.js', 'checkout.js', 'subscription-api', 'payment-config',
             'demo-backend', 'KOSPaywall', '__KOSDEMO', 'kos-staging-bar', 'data-staging', '/preview/', '../data/', '../assets/', '../fonts/',
             'lockCard', 'paywall=')
DICT_FORBIDDEN = ('멤버십', '모의 결제', '구독 관리', '구독 초기화', '결제 내역')


def check():
    C.set_mode('live')
    bad, warn = [], []
    files = assets()
    ver = {k: digest(v) for k, v in files.items()}
    for k, v in files.items():
        f = OUT / 'assets' / k
        if not f.exists() or f.read_text(encoding='utf-8') != v:
            bad.append(f'stock/assets/{k} 가 생성기와 다르다')
        for w in FORBIDDEN:
            if w in v:
                bad.append(f'stock/assets/{k}: "{w}"')
    stg = {re.sub(r'\s+', ' ', k).strip() for k in json.loads((ROOT / 'scripts/i18n/staging.json').read_text(encoding='utf-8')) if not k.startswith('//')}
    for k in shell_dict():
        if k in stg or any(w in k for w in DICT_FORBIDDEN):
            bad.append(f'stock/assets/i18n-dict.js: 멤버십 · 스테이징 문구 "{k[:30]}"')
    if not (OUT / 'index.html').exists() or (OUT / 'index.html').read_text(encoding='utf-8') != INDEX:
        bad.append('stock/index.html 가 생성기와 다르다')
    pj = OUT / 'assets' / 'pages.js'
    if not pj.exists() or pj.read_text(encoding='utf-8') != pages_js(on_disk()):
        bad.append('stock/assets/pages.js 가 있는 페이지 목록과 다르다(옛 주소 넘김) → python3 scripts/build_stock_static.py')
    want = set(tickers())
    have = {p.stem for p in OUT.glob('*.html') if TICKER.match(p.stem)}
    # 틀 — 종목 하나를 새로 그려 틀을 얻고, 모든 페이지의 틀이 그것과 같은지 본다(머리 · 꼬리 · 모듈 도장 · 공용 파일 해시)
    ref = None
    for r in prerender(sorted(want & have)[:5] or sorted(want)[:5], B.page_js()):   # 첫 종목이 그리다 멈춰도 다음 종목으로 틀을 얻는다
        if not r.get('error'):
            ref = skeleton(page_html(r, ver))
            break
    if ref is None:
        bad.append('틀을 얻을 종목을 하나도 그리지 못했다 — python3 scripts/build_stock_static.py 의 오류를 볼 것')
    off, drift, market = [], [], listed()
    for p in sorted(OUT.glob('*.html')):
        if not TICKER.match(p.stem):
            continue
        t = p.read_text(encoding='utf-8')
        if skeleton(t) != ref:
            off.append(p.stem)
        elif f'<link rel="canonical" href="{SITE}/stock/{p.stem}.html">' not in t or f'data-tk="{p.stem}"' not in t:
            off.append(p.stem)
        elif ('<meta name="robots" content="noindex' in t) == (p.stem in market):
            drift.append(p.stem)   # 시세 자료에 있는 종목은 색인, 없는 종목만 noindex — 시세 자료가 바뀐 뒤 아직 다시 안 만든 경우
    if off:
        bad.append(f'틀이 생성기와 다른 페이지 {len(off):,}장({", ".join(off[:5])} …) → python3 scripts/build_stock_static.py')
    missing, extra = sorted(want - have), sorted(have - want)
    # 자료가 바뀐 직후(종목이 늘거나 줄거나 시세 자료에서 빠지거나)에는 자동 작업(데이터 갱신 · 신규 상장 · 리포트 워치독 30분)이
    # 맞출 때까지 어긋날 수 있다 — 조금이면 알리기만 한다. 틀(머리 · 꼬리 · 모듈 도장)의 어긋남은 위에서 늘 실패다.
    if missing or extra or drift:
        msg = (f'페이지가 없는 종목 {len(missing)}개({", ".join(missing[:5])}) · 종목이 없어진 페이지 {len(extra)}장({", ".join(extra[:5])}) · '
               f'색인 여부가 시세 자료와 다른 페이지 {len(drift)}장({", ".join(drift[:5])})')
        (bad if len(missing) + len(extra) + len(drift) > max(20, len(want) // 50) else warn).append(msg)
    for w in warn:
        print(f'  ⚠ {w} — 자동 작업이 곧 맞춘다')
    if bad:
        print('❌ 종목 페이지:\n   ' + '\n   '.join(bad))
        return 1
    print(f'✅ 종목 페이지 {len(have):,}장 — 틀 · 공용 파일 = 생성기 결과 · 멤버십 흔적 없음')
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tickers', nargs='*')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        sys.exit(check())
    only = [t.upper() for t in a.tickers] or None
    build(only)


if __name__ == '__main__':
    main()
