#!/usr/bin/env python3
"""스테이징 브랜치를 실제 주소로 띄운다 — https://kosai.kr/staging/

왜 필요한가. 브랜치에서 만든 화면을 확인할 방법이 없었다. GitHub Pages 는 한
브랜치(main)만 서빙하므로, 브랜치의 결제·구독 화면은 주소가 없어 눌러 볼 수가
없다. 그래서 브랜치의 페이지들을 main 의 /staging/ 폴더로 복사해 둔다.
같은 도메인 아래에 얹히므로 링크·폰트·로그인이 실제 사이트와 똑같이 동작한다.

지키는 것
  · 실제 페이지는 하나도 건드리지 않는다. /staging/ 아래에만 쓴다.
  · 데이터(102MB)는 복사하지 않고 실제 사이트 것을 그대로 쓴다
    (data/… → ../data/…). 저장소가 두 배로 불어나면 안 된다.
  · noindex + robots.txt 차단. 검색에 나오면 안 되는 미완성 화면이다.
  · 위에 STAGING 띠를 붙여, 실제 사이트로 착각하지 않게 한다.

  python3 scripts/publish_staging.py <브랜치 체크아웃 경로> [출력폴더]
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 스테이징에 올릴 페이지 — 유료화 관련 화면과 그 페이지들이 부르는 스크립트
PAGES = ["pricing.html", "checkout.html", "billing.html", "stock.html",
         "Terms.html", "About.html", "Home.html", "Reports.html", "industry.html",
         "Screener.html", "Watchlist.html", "Login.html", "Signup.html",
         "Privacy.html", "Contact.html", "Feedback.html"]
SCRIPTS = ["paywall.js", "checkout.js", "billing.js", "payment-config.js",
           "firebase-config.js", "auth-state.js", "auth-guard.js", "auth-emails.js",
           "social-login.js", "watchlist.js", "submit-form.js", "analytics.js"]

BANNER = """<div class="kos-staging-bar">
  <b>STAGING</b><span>브랜치 미리보기입니다. 실제 서비스가 아닙니다.</span>
  <a href="../">실제 사이트로</a>
</div>
<style>
.kos-staging-bar{position:sticky;top:0;z-index:200;display:flex;flex-wrap:wrap;align-items:center;
  gap:12px;padding:9px 16px;background:#b4341f;color:#fff;
  font:600 12.5px var(--font-sans),system-ui,sans-serif}
.kos-staging-bar b{font-weight:800;letter-spacing:.05em}
.kos-staging-bar a{margin-left:auto;color:#fff;text-decoration:underline;text-underline-offset:2px}
</style>
"""


def fix(html):
    """폴더 한 칸 아래로 내려가므로 공용 자원 경로를 부모로 돌린다.
    HTML 속성(src/href)과 CSS url(), 그리고 JS 안의 fetch 경로까지 본다."""
    for kind in ("data", "assets", "fonts"):
        html = re.sub(rf'((?:src|href)=")({kind}/)', r"\1../\2", html)
        html = re.sub(rf'(url\(")({kind}/)', r"\1../\2", html)
        html = re.sub(rf"((?:fetch\(|url\()')({kind}/)", r"\1../\2", html)
    # 스테이징에서는 잠금을 기본으로 켠다.
    # 잠금은 데이터가 정한다 — 리포트 JSON 에 hasPaid 가 붙어야 잠긴다. 그런데
    # publish_paid.py 를 아직 안 돌려 정적 파일에 전문이 그대로 있고, 스테이징은
    # 실제 사이트의 data/ 를 함께 쓴다. 그래서 그냥 두면 전부 열려 보인다.
    # 스테이징은 '출시 후 모습'을 보는 곳이므로 여기서만 강제로 켠다(?paywall=0 이면 해제).
    html = html.replace("FORCE_LOCK=(qp('paywall')==='1')",
                        "FORCE_LOCK=(qp('paywall')!=='0')   /* staging: 기본 잠금 */")
    # 검색 노출 금지 — 미완성 화면이 색인되면 실제 페이지와 경쟁한다
    if 'name="robots"' not in html:
        html = html.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow" />', 1)
    else:
        html = re.sub(r'<meta name="robots" content="[^"]*"', '<meta name="robots" content="noindex,nofollow"', html)
    # canonical 은 실제 페이지를 가리키게 둔다(중복 콘텐츠 방지)
    html = html.replace("<body>", "<body>\n" + BANNER, 1)
    return html


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / "staging"
    out.mkdir(parents=True, exist_ok=True)

    n = 0
    for name in PAGES:
        f = src / name
        if not f.exists():
            print(f"  · 없음 {name}")
            continue
        (out / name).write_text(fix(f.read_text(encoding="utf-8")), encoding="utf-8")
        n += 1
    for name in SCRIPTS:
        f = src / name
        if f.exists():
            shutil.copy2(f, out / name)

    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow">'
        '<meta http-equiv="refresh" content="0; url=pricing.html">'
        '<title>KOSAI staging</title><a href="pricing.html">요금제로 이동</a>',
        encoding="utf-8")
    print(f"✅ staging/ — 페이지 {n}개 · 스크립트 {len(SCRIPTS)}개")
    print("   확인: https://kosai.kr/staging/pricing.html")


if __name__ == "__main__":
    main()
