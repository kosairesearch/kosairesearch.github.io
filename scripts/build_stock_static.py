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

영어 페이지(en/stock/{종목코드}.html · 2026-10-03 사장 승인)
  · 옛 로봇용 사본(r/)에는 영어 본문도 있어 영어로 묻는 검색 · 인공지능이 그것을 읽었다. 한국어 페이지만 미리 만들면 그 영어가
    빠진다 — 그래서 같은 종목의 영어 페이지를 따로 미리 만든다(말마다 다른 주소 · 구글이 권하는 방식).
  · 페이지 스크립트를 영어 화면으로 돌리고(prerender_stock.mjs · lang en), 남은 한국어 라벨은 브라우저와 같은 번역 엔진(i18n.js)이
    사전으로 바꾼다 — 머리 · 꼬리도 같다. 그래서 자바스크립트 없이도 영어다(<html lang="en"> · 영어 제목 · 설명 · 구조화 데이터).
  · 두 페이지는 서로를 hreflang 으로 가리킨다(x-default 는 한국어). 영어 페이지는 머리에서 KOS_PAGE_LANG='en' 을 달아,
    저장된 말과 관계없이 영어로 보인다(staging/i18n.js · 저장된 말은 바꾸지 않는다). 한국어 페이지를 영어로 정한 사람은 지금처럼
    화면이 영어로 그린다.
  · 지문(data-pre)은 번역 전의 글로 잰다 — 브라우저의 페이지 스크립트가 영어 화면에서 그린 글과 견주어 같으면 그대로 둔다.

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
OUT_EN = ROOT / 'en' / 'stock'
TICKER = re.compile(r'^[0-9A-Z]{6}$')
SITE = 'https://kosai.kr'

# 영어로 정한 사람에게 미리 그린 한국어 글이 비치지 않게 — 번역 엔진(i18n.js)이 머리에서 html[lang] 을 정하고, 페이지 스크립트가
# 영어로 다시 그리며 data-pre 를 걷는다. 스크립트가 끝내 못 뜨면 4초 뒤 그대로 보인다(번역 엔진의 1.5초 가림과 같은 장치).
# 영어 페이지(data-pre-lang="en")는 미리 그린 글이 이미 영어라 가리지 않는다.
PRE_CSS = ('html[lang="en"] #page[data-pre]:not([data-pre-lang="en"]){visibility:hidden;animation:kosPreShow 0s 4s forwards} '
           '@keyframes kosPreShow{to{visibility:visible}}')


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


def prerender(tks, page_js, lang='ko', shell=None):
    """노드로 미리 그린다 — 종목마다 dict 를 하나씩 내놓는다(prerender_stock.mjs 의 출력 한 줄). 영어(lang='en')는 맨 앞에
    번역한 머리 · 꼬리({'shell': [...]})가 한 줄 먼저 온다. 번역 엔진은 실사이트가 싣는 루트 i18n.js 다."""
    node = shutil.which('node')
    if not node:
        raise SystemExit('❌ node 가 없다 — 종목 페이지는 노드로 미리 그린다')
    with tempfile.TemporaryDirectory() as td:
        js = Path(td) / 'stock-page.js'
        js.write_text(page_js, encoding='utf-8')
        spec = json.dumps({'root': str(ROOT), 'js': str(js), 'tickers': tks, 'lang': lang, 'engine': str(ROOT / 'i18n.js'),
                           'dict': shell_dict() if lang == 'en' else {}, 'shell': shell or []}, ensure_ascii=False)
        err = (Path(td) / 'stderr.txt').open('w+', encoding='utf-8')   # 파이프가 아니라 파일 — 두 말을 함께 돌려도 막히지 않게
        p = subprocess.Popen([node, str(ROOT / 'scripts/prerender_stock.mjs')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             stderr=err, text=True, encoding='utf-8')
        p.stdin.write(spec)
        p.stdin.close()
        for line in p.stdout:
            if line.strip():
                yield json.loads(line)
        rc = p.wait()
        err.seek(0)
        msg = err.read()
        err.close()
        if rc:
            raise SystemExit(f'❌ 미리 그리기 실패({lang}): {msg.strip()[:500]}')


def abs_modules(page):
    """도장 찍은 루트 모듈 주소(src="auth-state.js?v=…")를 맨 위부터 쓴 주소로 — 페이지가 /stock/ 아래에 있다."""
    return re.sub(r'(\bsrc=")([A-Za-z0-9_-]+\.js\?v=[0-9a-f]{8}")', r'\1/\2', page)


def url_of(tk, lang='ko'):
    return f'{SITE}/en/stock/{tk}.html' if lang == 'en' else f'{SITE}/stock/{tk}.html'


def alternates(tk):
    """두 말의 페이지가 서로를 가리킨다 — 말을 정하지 않은 사람(x-default)은 한국어."""
    ko, en = url_of(tk), url_of(tk, 'en')
    return (f'<link rel="alternate" hreflang="ko" href="{ko}">\n<link rel="alternate" hreflang="en" href="{en}">\n'
            f'<link rel="alternate" hreflang="x-default" href="{ko}">\n')


# 영어 페이지 — 번역 엔진(i18n.js)보다 먼저. 저장된 말과 관계없이 이 페이지는 영어다(staging/i18n.js 의 KOS_PAGE_LANG).
PAGE_LANG_EN = "<script>window.KOS_PAGE_LANG='en'</script>\n"


def peers_script(peers):
    """같은 업종의 다른 리포트 — 미리 그릴 때 고른 목록([종목코드, 제목, 영어 제목, 발행일] 다섯)을 페이지 스크립트보다 먼저 싣는다.
    종목 페이지는 리포트 색인(reports-index.js · 수백 KB)을 받지 않으므로, 이것으로 그려야 브라우저가 다시 그린 글이 미리 그린 글과
    같다(지문이 맞는다). 빈 목록('기타' · 시세 없는 종목)도 싣는다 — 색인이 없는 브라우저가 고르려 들지 않게."""
    js = json.dumps(peers or [], ensure_ascii=False, separators=(',', ':'))
    js = js.replace('</', '<\\/').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return f'<script>window.KOS_PEERS={js};</script>\n'


def page_html(r, ver, on_market=True, lang='ko', shell=None):
    """종목 한 장. r 은 미리 그린 결과(prerender_stock.mjs 한 줄), ver 는 공용 파일의 내용 해시. on_market=False 는 시세 자료에 없는 종목(noindex).
    본문 자리에 미리 그릴 때의 리포트 형식(data-pre-tier)과 시세 유무(data-pre-known)를 단다 — 화면이 자료를 못 받았을 때(통신 끊김 ·
    검색 로봇의 렌더링) 미리 그린 글을 '준비 중'으로 덮지 않는 근거다(build_stock_staging.PAGE_JS render).
    lang='en' 은 영어 페이지 — shell 은 번역한 [머리, 꼬리], 본문 자리에 data-pre-lang="en"(대표 주소 · 가림 · 지문 견주기의 근거)."""
    tk, title, desc, url = r['tk'], r['title'], r['desc'] or '', r['canonical']
    want = url_of(tk, lang)
    assert url == want and r['ogUrl'] == want, f'{tk}: 대표 주소가 다르다 ({url} · {want})'
    seo = C.seo_tags(url, title, desc, robots=None if on_market else 'noindex,follow', og_type='article')
    if lang == 'en':
        assert seo.count('<meta property="og:locale" content="ko_KR">') == 1
        seo = seo.replace('<meta property="og:locale" content="ko_KR">', '<meta property="og:locale" content="en_US">', 1)
    extra = (seo + alternates(tk)
             + '<script type="application/ld+json" id="kos-jsonld">' + (r['ld'] or '{}').replace('</', '<\\/') + '</script>\n'
             + f'<link rel="stylesheet" href="/stock/assets/stock.css?v={ver["stock.css"]}">\n')
    head = C.head(H.escape(title, quote=False), extra=extra)
    nav, foot, mark = C.nav('리포트'), C.FOOTER, ''
    if lang == 'en':
        assert head.count('<html lang="ko">') == 1 and head.count('<meta charset="utf-8">\n') == 1
        head = head.replace('<html lang="ko">', '<html lang="en">', 1).replace('<meta charset="utf-8">\n', '<meta charset="utf-8">\n' + PAGE_LANG_EN, 1)
        nav, foot = shell
        mark = ' data-pre-lang="en"'
    body = (f'\n</head>\n<body>\n{nav}\n'
            f'<main class="wrap" id="page" data-tk="{tk}" data-pre="{r["hash"]}" data-pre-tier="{r["tier"]}" data-pre-known="{1 if on_market else 0}"{mark}>'
            f'{r["h"]}</main>\n'
            f'{foot}\n'
            '<script src="/data/stocks.js"></script>\n<script src="/data/valuation.js"></script>\n'
            + peers_script(r.get('peers'))
            + f'<script src="/stock/assets/stock.js?v={ver["stock.js"]}"></script>\n'
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


# /en/stock/ — 영어 쪽도 목록(리포트 페이지)으로. /en/ 은 첫 화면으로(영어 페이지가 종목 페이지뿐이라 그 위 폴더는 비어 있다).
EN_INDEX = INDEX.replace('<html lang="ko">', '<html lang="en">').replace('<title>리포트 | KOSAI</title>', '<title>Reports | KOSAI</title>') \
    .replace('리포트 목록으로 이동합니다', 'Go to the report list')
EN_ROOT = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>KOSAI</title>
<meta name="robots" content="noindex,follow">
<link rel="canonical" href="https://kosai.kr/">
<meta http-equiv="refresh" content="0; url=/">
<script>location.replace("/")</script>
</head>
<body><p><a href="/">Go to KOSAI</a></p></body>
</html>
'''


def pages_js(tks):
    """옛 주소 껍데기(stock.html)가 넘길지 정하는 목록 — 페이지가 있는 종목코드. 껍데기는 주소에 ?v= 없이 부른다(10분 캐시 안에서 늦어도
    새 종목은 '찾을 수 없습니다' 대신 그다음 방문부터 넘어간다)."""
    return ('/* 종목마다 미리 만든 페이지가 있는 종목코드 — scripts/build_stock_static.py 가 쓴다. 옛 주소 껍데기(stock.html)가 넘길지 정한다 */\n'
            'window.KOS_STOCK_PAGES="' + ','.join(tks) + '";\n')


def on_disk(out=OUT):
    return sorted(p.stem for p in out.glob('*.html') if TICKER.match(p.stem))


def write_if_changed(path, text):
    if path.exists() and path.read_text(encoding='utf-8') == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return True


def hangul_left(h, names):
    """영어 페이지 글에 남은 한글 글자 수 — 영문명이 없는 종목명(names)은 뺀다. 태그 · 속성 밖의 글만 본다."""
    t = re.sub(r'<[^>]*>', ' ', h)
    for n in names:
        if n:
            t = t.replace(n, ' ')
    return len(re.findall(r'[가-힣]', t)), t


def build(only=None):
    C.set_mode('live')
    files = assets()
    ver = {k: digest(v) for k, v in files.items()}
    changed = sum(write_if_changed(OUT / 'assets' / k, v) for k, v in files.items())
    changed += write_if_changed(OUT / 'index.html', INDEX)
    changed += write_if_changed(OUT_EN / 'index.html', EN_INDEX)
    changed += write_if_changed(OUT_EN.parent / 'index.html', EN_ROOT)
    tks = only or tickers()
    have = {p.stem for p in OUT.glob('*.html') if TICKER.match(p.stem)}
    if not only and have and len(tks) < len(have) * 0.5:
        raise SystemExit(f'❌ 만들 종목이 {len(tks)}개뿐이다(지금 {len(have)}장) — 자료가 깨졌을 수 있어 아무것도 지우지 않고 멈춘다')
    market = listed()
    # 시세 자료가 갑자기 크게 줄면(수집이 일부만 받은 날) 대부분의 페이지가 noindex · 시세 없음으로 바뀌고 사이트맵이 줄어든다 — 멈춘다
    if not only and have and len(market) < len(have) * 0.5:
        raise SystemExit(f'❌ 시세 자료의 종목이 {len(market)}개뿐이다(지금 페이지 {len(have)}장) — 자료가 깨졌을 수 있어 아무것도 바꾸지 않고 멈춘다')
    D = S.load_data()
    pj = B.page_js()
    # 두 말을 함께 그린다(노드 둘). 같은 종목 순서로 한 줄씩 나오므로 짝지어 쓴다 — 한쪽이라도 그리다 멈춘 종목은 두 페이지 모두 옛것으로 둔다
    g_ko = prerender(tks, pj, 'ko')
    g_en = prerender(tks, pj, 'en', shell=[C.nav('리포트'), C.FOOTER])
    head = next(g_en)
    shell = head.get('shell')
    if not shell or len(shell) != 2:
        raise SystemExit('❌ 영어 머리 · 꼬리를 번역하지 못했다')
    sh_left = [hangul_left(x, ())[0] for x in shell]
    if any(sh_left):
        raise SystemExit(f'❌ 영어 머리 · 꼬리에 번역되지 않은 한국어가 남았다(머리 {sh_left[0]} · 꼬리 {sh_left[1]}자) — scripts/i18n/*.json 을 볼 것')
    tiers, made, made_en, wrote, failed, han = {}, set(), set(), 0, [], []
    for rk, re_ in zip(g_ko, g_en):
        tk = rk['tk']
        if re_['tk'] != tk:
            raise SystemExit(f'❌ 한국어 · 영어 종목 순서가 어긋났다({tk} · {re_["tk"]})')
        on = tk in market
        # 그리다 멈춘 쪽(깨진 리포트 파일 · 번역 오류 등)만 옛 페이지를 그대로 두고 끝에 실패로 알린다. 다른 쪽은 쓴다 — 영어만 멈췄는데
        # 한국어까지 쓰지 않으면 새 상장 종목은 한국어 페이지가 없어 홈 검색 · 업종 표의 링크가 빈 주소가 된다(독립 검토 2026-10-03)
        if rk.get('error'):
            failed.append((tk, rk['error']))
        else:
            made.add(tk)
            tiers[rk['tier']] = tiers.get(rk['tier'], 0) + 1
            wrote += write_if_changed(OUT / f'{tk}.html', page_html(rk, ver, on))
        if re_.get('error'):
            failed.append((tk, '영어: ' + re_['error']))
            continue
        made_en.add(tk)
        wrote += write_if_changed(OUT_EN / f'{tk}.html', page_html(re_, ver, on, 'en', shell))
        if re_.get('han'):   # 영어판이 없는 리포트 칸 · 영문명이 없는 종목명 — 종목명은 빼고 센다
            st = D['stocks'].get(tk)
            name = st.get('name') if st and not st.get('name_en') else ((S.load_report(tk, D)[0] or {}).get('name') if not st else None)
            # 같은 업종의 다른 리포트에 실린 종목도 영문명이 없으면 한국어 이름으로 보인다 — 그 이름도 뺀다
            names = {name} if name else set()
            for p in re_.get('peers') or []:
                ps = D['stocks'].get(p[0])
                if ps and not ps.get('name_en') and ps.get('name'):
                    names.add(ps['name'])
            n, _ = hangul_left(re_['h'], names)
            if n:
                han.append((tk, n, re_['han'].get('sample', '')))
    for g in (g_ko, g_en):   # 둘 다 끝까지 읽어야 노드의 실패(종료 코드)가 드러난다
        if next(g, None) is not None:
            raise SystemExit('❌ 한국어 · 영어 종목 수가 다르다')
    gone = 0
    if not only:
        bad_tk = {t for t, _ in failed}
        for out, mk in ((OUT, made), (OUT_EN, made_en)):
            for tk in sorted({p.stem for p in out.glob('*.html') if TICKER.match(p.stem)} - mk - bad_tk):
                (out / f'{tk}.html').unlink()
                gone += 1
    changed += write_if_changed(OUT / 'assets' / 'pages.js', pages_js(on_disk()))
    print(f'✅ stock/ {len(made):,}장 · en/stock/ {len(made_en):,}장 (전체 {tiers.get("v2", 0):,} · 옛 형식 {tiers.get("v1", 0):,} · '
          f'준비 중 {tiers.get("none", 0):,} · 시세 없음 {len(made - market):,}) · 새로 쓴 페이지 {wrote:,} · 지운 페이지 {gone} · 공용 파일 갱신 {changed}')
    if han:   # 영어판이 빈 칸이 조금 있는 것은 자료 사정(옛 형식 리포트 2편의 종합 의견 등) — 많으면 사전이 빠진 것이다
        print(f'  ⚠ 영어 페이지 {len(han)}장에 영어판이 없는 글이 남았다(한국어로 보인다): '
              + ' · '.join(f'{t} {n}자 "{smp[:24]}"' for t, n, smp in han[:5]))
    odd = {k: v for k, v in tiers.items() if k not in ('v2', 'v1', 'none')}
    if odd:
        raise SystemExit(f'❌ 그릴 수 없는 종목이 있다: {odd}')
    if failed:
        raise SystemExit(f'❌ 그리다 멈춘 종목 {len(failed)}개 — 옛 페이지를 그대로 두었다(리포트 파일을 확인할 것):\n   '
                         + '\n   '.join(f'{t}: {e[:200]}' for t, e in failed[:10]))
    if len(han) > max(20, len(made_en) // 50):
        raise SystemExit(f'❌ 영어 페이지 {len(han)}장에 한국어가 남았다 — 번역 사전(scripts/i18n/*.json)이 빠졌을 수 있다')


# ── 검사 ────────────────────────────────────────────────────────────────────
def skeleton(page):
    """종목마다 다른 것(제목 · 설명 · 공유 문구 · 구조화 데이터 · 본문 · 종목코드)을 지운 틀 — 같은 말의 모든 페이지가 같아야 한다."""
    s = re.sub(r'<title>.*?</title>', '<title>#</title>', page, count=1, flags=re.S)
    s = s.replace('<meta name="robots" content="noindex,follow">\n', '', 1)
    s = re.sub(r'(<meta (?:name|property)="(?:description|og:title|og:description|twitter:title|twitter:description)" content=")[^"]*"', r'\1#"', s)
    s = re.sub(r'(<script type="application/ld\+json" id="kos-jsonld">).*?(</script>)', r'\1#\2', s, count=1, flags=re.S)
    s = re.sub(r'<main class="wrap" id="page" data-tk="[0-9A-Z]{6}" data-pre="[0-9a-f]{8}" data-pre-tier="(?:v2|v1|none)" data-pre-known="[01]"( data-pre-lang="en")?>.*?</main>',
               r'<main #\1>#</main>', s, count=1, flags=re.S)
    s = re.sub(r'<script>window\.KOS_PEERS=.*?;</script>', '<script>window.KOS_PEERS=#;</script>', s, count=1, flags=re.S)
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
    for f, want_txt in ((OUT / 'index.html', INDEX), (OUT_EN / 'index.html', EN_INDEX), (OUT_EN.parent / 'index.html', EN_ROOT)):
        if not f.exists() or f.read_text(encoding='utf-8') != want_txt:
            bad.append(f'{f.relative_to(ROOT)} 가 생성기와 다르다')
    pj = OUT / 'assets' / 'pages.js'
    if not pj.exists() or pj.read_text(encoding='utf-8') != pages_js(on_disk()):
        bad.append('stock/assets/pages.js 가 있는 페이지 목록과 다르다(옛 주소 넘김) → python3 scripts/build_stock_static.py')
    want = set(tickers())
    have = {p.stem for p in OUT.glob('*.html') if TICKER.match(p.stem)}
    have_en = {p.stem for p in OUT_EN.glob('*.html') if TICKER.match(p.stem)}
    # 틀 — 종목 하나를 새로 그려 말마다 틀을 얻고, 모든 페이지의 틀이 그것과 같은지 본다(머리 · 꼬리 · 모듈 도장 · 공용 파일 해시)
    sample = sorted(want & have & have_en)[:5] or sorted(want)[:5]
    pj_ = B.page_js()
    ref = {}
    g_en = prerender(sample, pj_, 'en', shell=[C.nav('리포트'), C.FOOTER])
    shell = next(g_en).get('shell')
    for lang, gen in (('ko', prerender(sample, pj_, 'ko')), ('en', g_en)):
        for r in gen:   # 첫 종목이 그리다 멈춰도 다음 종목으로 틀을 얻는다
            if lang not in ref and not r.get('error'):
                ref[lang] = skeleton(page_html(r, ver, True, lang, shell))
    for lang in ('ko', 'en'):
        if lang not in ref:
            bad.append(f'틀을 얻을 종목을 하나도 그리지 못했다({lang}) — python3 scripts/build_stock_static.py 의 오류를 볼 것')
    market = listed()
    off, drift = {'ko': [], 'en': []}, []
    for lang, out in (('ko', OUT), ('en', OUT_EN)):
        for p in sorted(out.glob('*.html')):
            if not TICKER.match(p.stem):
                continue
            t = p.read_text(encoding='utf-8')
            if skeleton(t) != ref.get(lang):
                off[lang].append(p.stem)
            elif (f'<link rel="canonical" href="{url_of(p.stem, lang)}">' not in t or f'data-tk="{p.stem}"' not in t
                  or alternates(p.stem) not in t):
                off[lang].append(p.stem)
            elif ('<meta name="robots" content="noindex' in t) == (p.stem in market):
                drift.append(f'{lang}:{p.stem}')   # 시세 자료에 있는 종목은 색인, 없는 종목만 noindex — 시세 자료가 바뀐 뒤 아직 다시 안 만든 경우
    for lang, xs in off.items():
        if xs:
            bad.append(f'틀이 생성기와 다른 {"영어 " if lang == "en" else ""}페이지 {len(xs):,}장({", ".join(xs[:5])} …) → python3 scripts/build_stock_static.py')
    missing, extra = sorted(want - have), sorted(have - want)
    missing_en, extra_en = sorted(want - have_en), sorted(have_en - want)
    # 자료가 바뀐 직후(종목이 늘거나 줄거나 시세 자료에서 빠지거나)에는 자동 작업(데이터 갱신 · 신규 상장 · 리포트 워치독 30분)이
    # 맞출 때까지 어긋날 수 있다 — 조금이면 알리기만 한다. 틀(머리 · 꼬리 · 모듈 도장)의 어긋남은 위에서 늘 실패다.
    if missing or extra or drift or missing_en or extra_en:
        msg = (f'페이지가 없는 종목 {len(missing)}개({", ".join(missing[:5])}) · 종목이 없어진 페이지 {len(extra)}장({", ".join(extra[:5])}) · '
               f'영어 페이지가 없는 종목 {len(missing_en)}개({", ".join(missing_en[:5])}) · 종목이 없어진 영어 페이지 {len(extra_en)}장 · '
               f'색인 여부가 시세 자료와 다른 페이지 {len(drift)}장({", ".join(drift[:5])})')
        # 종목 수로 센다 — 한 종목의 한국어 · 영어 페이지가 함께 어긋나도 한 종목이다(두 번 세면 허용치가 절반이 된다 · 독립 검토)
        n = len(set(missing) | set(extra) | set(missing_en) | set(extra_en) | {d.split(':', 1)[1] for d in drift})
        (bad if n > max(20, len(want) // 50) else warn).append(msg)
    for w in warn:
        print(f'  ⚠ {w} — 자동 작업이 곧 맞춘다')
    if bad:
        print('❌ 종목 페이지:\n   ' + '\n   '.join(bad))
        return 1
    print(f'✅ 종목 페이지 {len(have):,}장 · 영어 {len(have_en):,}장 — 틀 · 공용 파일 = 생성기 결과 · 멤버십 흔적 없음')
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
