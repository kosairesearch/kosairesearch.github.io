#!/usr/bin/env python3
"""실사이트(kosai.kr 루트)를 새 디자인으로 낸다 — 2026-10-03 사장 "우리가 새로 디자인한 페이지들 … 실사이트로 옮겨줘.
근데 실사이트에는 멤버십 페이지가 없잖아. 그런 거 잘 고려해서 옮겨줘".

    python3 scripts/build_live.py            # 루트 페이지 · 모듈 둘(i18n.js · auth-state.js) · 첫 화면 그림을 다시 만들고 ?v= 를 찍는다
    python3 scripts/build_live.py --check    # 만든 결과가 저장소와 같은지 · 멤버십 흔적이 없는지만 본다 (check_all.sh)

스테이징(build_staging.py)과 같은 생성기가 comp_common.set_mode('live') 로 돈다. 다른 점은 comp_common 의 live 모드가 맡는다 —
절대 주소, STAGING 띠 · 모의 결제 없음, 멤버십 없음(머리 · 꼬리 메뉴, 종목 잠금, 결제 모듈, 설정의 구독 칸), 검색 노출 머리(LIVE_SEO),
번역 엔진 · 통계 머리 스크립트, 루트 모듈 꼬리.

루트 모듈 가운데 둘은 스테이징 모듈에서 만든다:
  · i18n.js     — staging/i18n.js 그대로(두 사이트가 같은 엔진)
  · auth-state.js — staging/auth-state.js 에서 /*@paid*/ … /*@/paid*/ (구독 안내)를 빼고 /*@live … @*/ 를 푼 것
나머지 모듈은 루트 파일을 그대로 쓴다(settings-panel.js 는 구독 칸이 없는 루트 판 — tests/settings-panel.test.mjs).

매일 바뀌는 첫 화면 값(data-live="이름")은 --check 가 빼고 견준다 — 값은 stamp_counts.py 가 30분마다 맞추고 그쪽 --check 가 본다.
모닝브리핑(brief.html)은 아침 작업의 render_brief.py 가 같은 생성기로 그린다(발행된 가장 최근 브리핑).
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

C.set_mode('live')
import build_about_comp, build_auth_comp, build_brief_comp, build_forms_comp, build_home_comp  # noqa: E402
import build_industry_comp, build_legal_comp, build_reports_comp, build_watchlist_comp  # noqa: E402
import build_settings_staging, build_stock_staging, build_404  # noqa: E402
import stamp_assets  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent / 'concepts'))
import landing  # noqa: E402

PAGES = ['index.html', 'Home.html', 'Reports.html', 'industry.html', 'Watchlist.html', 'brief.html', 'About.html', 'Terms.html', 'Privacy.html',
         'Contact.html', 'Feedback.html', 'Login.html', 'Signup.html', 'Consent.html', 'auth-action.html', 'Settings.html', 'stock.html', '404.html']
MODULES = ['i18n.js', 'auth-state.js']
NOINDEX = {'Watchlist.html', 'Consent.html', 'auth-action.html', '404.html'}   # 옛 실사이트와 같다

_PAID = re.compile(r'/\*@paid\*/(.*?)/\*@/paid\*/', re.S)
_LIVE = re.compile(r'/\*@live\n(.*?)\n@\*/', re.S)


def live_module(src):
    """스테이징 모듈 → 실사이트 모듈: 유료 구간(/*@paid*/ … /*@/paid*/)을 빼고 실사이트 전용(/*@live … @*/)을 푼다."""
    out = _LIVE.sub(lambda m: m.group(1), _PAID.sub('', src))
    assert '/*@' not in out and '@*/' not in out
    return out


def build_modules(out_dir: Path):
    stg = ROOT / 'staging'
    (out_dir / 'i18n.js').write_text((stg / 'i18n.js').read_text(encoding='utf-8'), encoding='utf-8')
    head = ('/* 실사이트 사본 — scripts/build_live.py 가 staging/auth-state.js 에서 만든다(구독 안내 구간 @paid 를 빼고). 여기를 고치지 말고\n'
            '   staging/auth-state.js 를 고친 뒤 python3 scripts/build_live.py 를 돌린다. */\n')
    (out_dir / 'auth-state.js').write_text(head + live_module((stg / 'auth-state.js').read_text(encoding='utf-8')), encoding='utf-8')


def build_pages(out_dir: Path):
    C.set_mode('live')
    o = lambda n: str(out_dir / n)  # noqa: E731
    build_home_comp.build(o('Home.html'))
    build_reports_comp.build(o('Reports.html'))
    build_industry_comp.build(o('industry.html'))
    build_watchlist_comp.build(o('Watchlist.html'))
    build_brief_comp.build(None, o('brief.html'))   # 발행된 가장 최근 브리핑
    build_about_comp.build(o('About.html'))
    build_legal_comp.build('terms', o('Terms.html'))
    build_legal_comp.build('privacy', o('Privacy.html'))
    build_forms_comp.build({'contact': o('Contact.html'), 'feedback': o('Feedback.html')})
    build_auth_comp.build({'login': o('Login.html'), 'signup': o('Signup.html'), 'consent': o('Consent.html'),
                           'action': o('auth-action.html'), 'settings': o('_unused.html')})   # 설정은 아래 build_settings_staging(live)
    build_settings_staging.build(o('Settings.html'), live=True)
    C.set_mode('live')
    build_stock_staging.build(out_dir)
    build_404.build(o('404.html'))
    landing.build_live(str(out_dir))
    C.set_mode('live')


# 실사이트에 있으면 안 되는 것 — 멤버십 화면 · 결제 · 모의 결제 · 스테이징 · 시안의 흔적
FORBIDDEN = ('pricing.html', 'checkout.html', 'billing.html', 'paywall.js', 'checkout.js', 'subscription-api', 'payment-config',
             'demo-backend', 'KOSPaywall', '__KOSDEMO', 'kos-staging-bar', 'data-staging', '/preview/', '../data/', '../assets/', '../fonts/',
             'lockCard', 'paywall=')
FORBIDDEN_JS = {'auth-state.js': ('subscriptions', 'KOSPaywall', '구독 관리로 이동', 'wd-sub', 'wd-tosubs', 'activeSub(uid)'),
                'settings-panel.js': ('subscription-api', 'payment-config', 'paneSubscription')}


def visible_text(html):
    t = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.S)
    t = re.sub(r'<!--.*?-->', ' ', t, flags=re.S)
    return re.sub(r'<[^>]+>', ' ', t)


def audit(dir_: Path):
    """멤버십 · 스테이징 흔적, 색인 설정, 모듈 문법. 문제 목록을 돌려준다."""
    bad = []
    for name in PAGES:
        f = dir_ / name
        if not f.exists():
            bad.append(f'{name} 없음')
            continue
        h = f.read_text(encoding='utf-8')
        for w in FORBIDDEN:
            if w in h:
                bad.append(f'{name}: "{w}"')
        vt = visible_text(h) + ' '.join(re.findall(r'<title>(.*?)</title>', h, re.S))
        for w in ('멤버십', '디자인 시안', 'STAGING'):
            if w in vt:
                bad.append(f'{name}: 화면 글 · 제목에 "{w}"')
        ni = bool(re.search(r'<meta name="robots" content="[^"]*noindex', h))
        if ni != (name in NOINDEX):
            bad.append(f'{name}: 색인 설정이 옛 실사이트와 다르다(noindex={ni})')
        if name != '404.html':
            if '<link rel="canonical"' not in h:
                bad.append(f'{name}: canonical 없음')
            if 'src="analytics.js' not in h or 'src="i18n.js' not in h:
                bad.append(f'{name}: 통계 · 번역 머리 스크립트 없음')
    for name, words in FORBIDDEN_JS.items():
        f = dir_ / name if (dir_ / name).exists() else ROOT / name
        s = f.read_text(encoding='utf-8')
        for w in words:
            if w in s:
                bad.append(f'{name}: "{w}"')
    node = shutil.which('node')
    if node:
        for name in MODULES:
            f = dir_ / name
            if f.exists():
                r = subprocess.run([node, '--check', str(f)], capture_output=True, text=True)
                if r.returncode:
                    bad.append(f'{name}: 문법 오류 {r.stderr.strip()[:200]}')
    return bad


def unstamped(s):
    return re.sub(r'\?v=[0-9a-f]{8}', '', s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td)
            try:
                build_modules(t)
                build_pages(t)
            except Exception as e:  # noqa: BLE001
                print(f'❌ 실사이트 생성기가 멈췄다: {type(e).__name__}: {e}')
                sys.exit(1)
            diff = []
            for name in MODULES:
                cur = ROOT / name
                if not cur.exists() or unstamped(cur.read_text(encoding='utf-8')) != unstamped((t / name).read_text(encoding='utf-8')):
                    diff.append(name)
            for name in PAGES:
                cur = ROOT / name
                have = cur.read_text(encoding='utf-8') if cur.exists() else None
                fresh = (t / name).read_text(encoding='utf-8')
                if name == 'index.html' and have is not None:   # 첫 화면 — 매일 바뀌는 값(data-live · 머리의 종목 수)은 빼고 견준다
                    have, fresh = (re.sub(r'(국내 상장 )[\d,]+(개 종목)', r'\1#\2', landing.mask(x)) for x in (have, fresh))
                if have != fresh:
                    diff.append(name)
            for f in sorted((t / 'img').glob('*.webp')):
                cur = ROOT / 'img' / f.name
                if not cur.exists() or cur.read_bytes() != f.read_bytes():
                    diff.append('img/' + f.name)
            bad = audit(ROOT)
            if diff:
                print('❌ 실사이트가 생성기와 다르다: ' + ', '.join(diff) + ' → python3 scripts/build_live.py')
            if bad:
                print('❌ 실사이트 점검:\n   ' + '\n   '.join(bad))
            if not diff and not bad:
                print(f'✅ 실사이트 = 생성기 결과 ({len(PAGES)}장 · 모듈 {len(MODULES)}) · 멤버십 · 스테이징 흔적 없음')
            sys.exit(1 if diff or bad else 0)
    build_modules(ROOT)
    subprocess.run([sys.executable, str(ROOT / 'scripts/stamp_assets.py')], check=True)   # 새 모듈 안의 import 에 ?v= — 페이지 도장의 바탕
    build_pages(ROOT)
    subprocess.run([sys.executable, str(ROOT / 'scripts/stamp_assets.py')], check=True)   # 모듈이 바뀌어 도장이 달라진 페이지(관리자 화면 등)까지
    bad = audit(ROOT)
    if bad:
        print('❌ 실사이트 점검:\n   ' + '\n   '.join(bad))
        sys.exit(1)
    print(f'✅ 실사이트 {len(PAGES)}장 · 모듈 {len(MODULES)}')


if __name__ == '__main__':
    main()
