#!/usr/bin/env python3
"""404 페이지 — GitHub Pages 는 루트 /404.html 하나를 모든 없는 주소에 쓴다. 새 디자인(comp_common · live 모드).

    python3 scripts/build_404.py        # → 404.html
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

C.set_mode('live')

CSS = '''
.nf{max-width:640px;padding:48px 0 96px}
.nf .acts{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center}
.nf .alt{margin:40px 0 0;padding-top:24px;border-top:1px solid var(--hair);font:400 14px/22px var(--font);color:var(--ink-62)} .nf .alt a{color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
@media (max-width:820px){.nf{padding:36px 0 72px}}'''

BODY = '''<main class="wrap"><header class="ph dz"><p class="crumb">404</p><h1>페이지를 찾을 수 없습니다</h1>
  <p class="sub"><span class="s">주소가 바뀌었거나 잘못 입력되었을 수 있습니다.</span> <span class="s">종목 리포트는 리포트 목록에서 종목명이나 종목코드로 찾을 수 있습니다.</span></p></header><div class="nf">
  <div class="acts"><a class="btn btn-ink" href="/Reports.html">전체 리포트 보기</a><a class="tbtn" href="/Home.html">홈으로</a></div>
  <p class="alt">계속 같은 화면이 보이면 <a href="/Contact.html">문의하기</a>로 알려 주시기 바랍니다. 주소를 함께 적어 주시면 빠르게 확인하겠습니다.</p>
</div></main>'''


def build(out_path=None):
    html = (C.head('페이지를 찾을 수 없습니다 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + '\n' + BODY + '\n' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / '404.html'
    C.emit(out, html)
    print(f'✅ {out} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
