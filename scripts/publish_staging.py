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

모의 결제
  결제 키(토스)도 서버 함수도 아직 없어서 가입을 눌러 볼 수가 없었다. 그래서
  스테이징에만 staging_demo.js 를 demo-backend.js 로 얹어, 구독을 브라우저
  안에서 흉내 낸다. 로그인은 진짜, 구독만 가짜다. 이 파일은 /staging/ 밖으로
  나가지 않으므로 실제 사이트의 결제 흐름은 그대로다.

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
  <b>STAGING</b><span>미리보기입니다. 결제는 모의 결제이며 실제로 돈이 오가지 않습니다.</span>
  <a href="#" id="kosDemoReset">구독 초기화</a>
  <a href="../">실제 사이트로</a>
</div>
<style>
.kos-staging-bar{position:sticky;top:0;z-index:200;display:flex;flex-wrap:wrap;align-items:center;
  gap:12px;padding:9px 16px;background:#b4341f;color:#fff;
  font:600 12.5px var(--font-sans),system-ui,sans-serif}
.kos-staging-bar b{font-weight:800;letter-spacing:.05em}
.kos-staging-bar span{margin-right:auto}
.kos-staging-bar a{color:#fff;text-decoration:underline;text-underline-offset:2px}
</style>
<script>
/* 모의 구독을 지운다. 여러 상태(비구독 → BASIC → PRO → 해지)를 몇 번이고
   다시 밟아 볼 수 있어야 미리보기가 쓸모 있다. 모듈보다 먼저 실행되므로
   KOSDemo 는 누를 때 찾는다. */
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('#kosDemoReset');
  if (!a) return;
  e.preventDefault();
  if (window.KOSDemo) window.KOSDemo.reset();
  else ['kos-demo-sub', 'kos-demo-reads', 'kos-demo-pays'].forEach(function (k) {
    try { localStorage.removeItem(k); } catch (err) {}
  });
  location.reload();
});
</script>
"""

DEMO_TAG = '<script type="module" src="demo-backend.js"></script>'

# 모의 백엔드를 붙이려면 스크립트 세 개를 스테이징에서만 살짝 비켜 세워야 한다.
# 원본을 고치지 않고 여기서 바꿔 쓴다 — 실제 사이트에는 이 우회가 없어야 한다.
PATCH = {
    "paywall.js": [(
        "window.KOSPaywall = {\n  ready,",
        # demo-backend 가 먼저 실행돼 window.KOSPaywall 을 잡아 둔다. 그냥 두면
        # 나중에 뜨는 이 모듈이 덮어써서 모의 구독이 무시된다.
        "if (!window.__KOSDEMO) window.KOSPaywall = {\n  ready,",
    )],
    "checkout.js": [
        # 토스 클라이언트 키가 자리표시자라 payReady 가 false 다 — 그대로 두면
        # 어떤 화면을 열어도 '결제 준비 중입니다'에서 끝난다.
        ('import { PLANS, TOSS, payReady, planOf, won } from "./payment-config.js";',
         'import { PLANS, TOSS, payReady as _payReady, planOf, won } from "./payment-config.js";\n'
         "const payReady = window.__KOSDEMO ? true : _payReady;"),
        # 결제창 대신 모의 구독을 만든다. 잠깐 기다리는 건 '결제창을 여는 중…'
        # 문구가 한 프레임 만에 사라지지 않게 하려는 것.
        ("    try {\n      const { loadTossPayments }",
         "    try {\n      if (window.__KOSDEMO) {\n"
         "        await new Promise((r) => setTimeout(r, 700));\n"
         "        if (method) { window.KOSDemo.updateCard(); location.replace('billing.html?card=1'); }\n"
         "        else { window.KOSDemo.subscribe(plan.id); location.replace('billing.html?welcome=1'); }\n"
         "        return;\n"
         "      }\n"
         "      const { loadTossPayments }"),
    ],
    # 스테이징에서 탈퇴를 눌러 실제 파이어베이스 계정이 지워지면 안 된다.
    # deleteAccount 를 모의 백엔드로 돌리고, 실패 시 폴백도 막는다.
    "auth-state.js": [
        # 구독 여부도 모의 상태에서 읽는다 — 진짜 Firestore 에는 모의 구독이 없다.
        ("async function activeSub(uid){\n  try{",
         "async function activeSub(uid){\n"
         "  if (window.__KOSDEMO) {\n"
         "    var st = window.KOSPaywall && window.KOSPaywall.state();\n"
         "    return st && st.active ? st.sub : null;\n"
         "  }\n"
         "  try{"),
        ('      await httpsCallable(fns, "deleteAccount")({});',
         "      if (window.__KOSDEMO) await window.KOSDemo.call('deleteAccount');\n"
         '      else await httpsCallable(fns, "deleteAccount")({});'),
        ("      if(hadSub) throw e;",
         "      if(hadSub || window.__KOSDEMO) throw e;"),
    ],
    "billing.js": [
        ("const call = (n, d) => httpsCallable(fns, n)(d || {});",
         "const call = (n, d) => (window.__KOSDEMO\n"
         "  ? window.KOSDemo.call(n, d || {})\n"
         "  : httpsCallable(fns, n)(d || {}));"),
        # 열람 현황도 모의 백엔드에서 받는다.
        ('const res = await httpsCallable(fns, "getUsage")({});',
         'const res = await call("getUsage");'),
        ("async function loadPayments(uid) {\n  if (!isConfigured) return [];",
         "async function loadPayments(uid) {\n"
         "  if (window.__KOSDEMO) return window.KOSDemo.payments();\n"
         "  if (!isConfigured) return [];"),
    ],
}


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
    # 모의 백엔드는 반드시 다른 모듈보다 먼저 실행돼야 한다(module 은 문서 순서대로
    # 실행된다). 그래서 body 끝이 아니라 head 맨 앞에 넣는다.
    html = html.replace("<head>", "<head>\n" + DEMO_TAG, 1)
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
        if not f.exists():
            continue
        if name in PATCH:
            js = f.read_text(encoding="utf-8")
            for old, new in PATCH[name]:
                # 원본이 바뀌어 못 찾으면 조용히 지나가면 안 된다. 모의 결제가
                # 안 걸린 스테이징은 '결제 준비 중입니다'만 띄우고 끝난다.
                if js.count(old) != 1:
                    sys.exit(f"❌ {name}: 패치 지점을 찾지 못했습니다 — {old.splitlines()[0]!r}")
                js = js.replace(old, new, 1)
            (out / name).write_text(js, encoding="utf-8")
        else:
            shutil.copy2(f, out / name)

    demo = src / "scripts" / "staging_demo.js"
    if not demo.exists():
        demo = ROOT / "scripts" / "staging_demo.js"
    shutil.copy2(demo, out / "demo-backend.js")

    (out / "index.html").write_text(
        '<!doctype html><meta charset="utf-8">'
        '<meta name="robots" content="noindex,nofollow">'
        '<meta http-equiv="refresh" content="0; url=pricing.html">'
        '<title>KOSAI staging</title><a href="pricing.html">요금제로 이동</a>',
        encoding="utf-8")
    print(f"✅ staging/ — 페이지 {n}개 · 스크립트 {len(SCRIPTS)}개 + 모의 백엔드")
    print("   확인: https://kosai.kr/staging/pricing.html")


if __name__ == "__main__":
    main()
