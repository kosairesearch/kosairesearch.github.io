#!/usr/bin/env python3
"""스테이징(kosai.kr/staging/)을 새 디자인으로 통째로 낸다 — 사장 2026-09-26 "여태까지 디자인한 것들을 스테이징에 적용".

    python3 scripts/build_staging.py              # staging/*.html 을 다시 만들고 ?v= 를 찍는다
    python3 scripts/build_staging.py --out /tmp/x # 다른 곳에 내 본다(검사·비교용)
    python3 scripts/build_staging.py --check      # 만든 결과가 저장소와 같은지만 본다 (check_all.sh)

시안 빌더(build_*_comp.py)와 같은 코드가 comp_common.set_mode('staging') 으로 돈다 — 상대 경로 · STAGING 띠 ·
실제 모듈 연결은 comp_common.finish() 가 한다. 그래서 시안과 스테이징의 옷은 늘 같다.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

C.set_mode('staging')
import build_about_comp, build_auth_comp, build_brief_comp, build_forms_comp, build_home_comp  # noqa: E402
import build_industry_comp, build_legal_comp, build_reports_comp, build_watchlist_comp  # noqa: E402
import build_pricing, build_checkout, build_settings_staging  # noqa: E402


def build_all(out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    build_home_comp.build(str(out_dir / 'Home.html'))
    build_reports_comp.build(str(out_dir / 'Reports.html'))
    build_industry_comp.build(str(out_dir / 'industry.html'))
    build_watchlist_comp.build(str(out_dir / 'Watchlist.html'))
    build_brief_comp.build(None, str(out_dir / 'brief.html'))
    build_about_comp.build(str(out_dir / 'About.html'))
    build_legal_comp.build('terms', str(out_dir / 'Terms.html'))
    build_legal_comp.build('privacy', str(out_dir / 'Privacy.html'))
    build_forms_comp.build({'contact': str(out_dir / 'Contact.html'), 'feedback': str(out_dir / 'Feedback.html')})
    build_auth_comp.build({'login': str(out_dir / 'Login.html'), 'signup': str(out_dir / 'Signup.html'), 'consent': str(out_dir / 'Consent.html'),
                           'action': str(out_dir / 'auth-action.html'), 'settings': str(out_dir / '_unused.html')})   # 설정은 build_settings_staging
    build_pricing.build(str(out_dir / 'pricing.html'))
    build_checkout.build(str(out_dir / 'checkout.html'))
    build_settings_staging.build(str(out_dir / 'Settings.html'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=str(ROOT / 'staging'))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        import stamp_assets  # noqa: E402  저장소의 페이지는 ?v= 가 찍혀 있다 — 같은 규칙으로 찍은 뒤 견준다
        hashes = {p.name: stamp_assets.digest(p.read_text(encoding='utf-8')) for p in (ROOT / 'staging').glob('*.js')}
        with tempfile.TemporaryDirectory() as td:
            build_all(Path(td))
            bad = []
            for f in sorted(Path(td).glob('*.html')):
                cur = ROOT / 'staging' / f.name
                fresh, _ = stamp_assets.stamp(f.read_text(encoding='utf-8'), hashes)
                if not cur.exists() or cur.read_text(encoding='utf-8') != fresh:
                    bad.append(f.name)
            print(('❌ 스테이징이 생성기와 다르다: ' + ', '.join(bad) + ' → python3 scripts/build_staging.py') if bad else '✅ 스테이징 = 생성기 결과')
            sys.exit(1 if bad else 0)
    build_all(Path(a.out))
    if Path(a.out).resolve() == (ROOT / 'staging').resolve():
        subprocess.run([sys.executable, str(ROOT / 'scripts/stamp_assets.py')], check=True)   # 모듈 주소에 ?v=해시
    print(f'✅ {a.out}')


if __name__ == '__main__':
    main()
