#!/usr/bin/env python3
"""모닝브리핑(brief.html) — 새 디자인 시안(comp). 본문은 실사이트와 같은 scripts/render_brief.py 의 build() 로 만든다.

    python3 scripts/build_brief_comp.py [YYYY-MM-DD] [출력 경로]    # 기본: 가장 최근 브리핑 → preview/brief.html

본문 마크업·문단 나누기·날짜 줄·면책 문구는 실사이트 렌더러 그대로다(같은 함수). 시안은 그 위에 옷(CSS)만 다르게 입힌다.
한/영 사전·로그인 상태는 시안에서는 뺐다 — 옮길 때 붙인다. 종목 링크는 실사이트 종목 페이지(/stock.html)로 간다.
"""
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402
import render_brief as RB  # noqa: E402

CSS = '''
/* 글 한 단 — 읽기 폭 720 */
.mb{max-width:720px;padding:44px 0 0}
.mb-date{font:500 13px/20px var(--font);color:var(--ink-55)} .mb-date::before{content:"모닝브리핑 · "}
.mb h1{margin:12px 0 0;font:700 36px/48px var(--font);letter-spacing:-.025em;text-wrap:balance}
.mb-lead{margin:18px 0 0;font:400 18px/30px var(--font);color:var(--ink-72)}
.mb-meta{margin-top:14px;font:400 13px/20px var(--font);color:var(--ink-55)}
/* 요약 — 상자 대신 위아래 줄 */
.mb-sum{margin:36px 0 0;padding:26px 0 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--hair)}
.mb-sum-h{font:600 12px/16px var(--font);color:var(--ink-55);margin:0 0 14px}
.mb-sum-p{margin:0 0 18px;font:400 18px/30px var(--font);letter-spacing:-.005em}
/* 절 */
.mb-sec{padding-top:48px}
.mb-sec h2{margin:0 0 18px;font:700 24px/32px var(--font);letter-spacing:-.02em;text-wrap:balance}
.mb-sec p{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em} .mb-sec p:last-child{margin-bottom:0}
.mb-sec a{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;text-decoration-thickness:1px} .mb-sec a:hover{text-decoration-color:var(--ink)}
.mb-sec b{font-weight:600}
/* KOSAI 리포트 확인 지점 — 우리 리포트에서 나온 절이라 줄 하나로 구분 */
.mb-sec--cov{margin-top:56px;padding-top:36px;border-top:1px solid var(--line)}
.mb-src{font:600 12px/16px var(--font);color:var(--ink-55);margin:0 0 10px}
.mb-disc{margin:56px 0 0;padding-top:18px;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-55)}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .mb{padding:20px 0 0} .mb h1{font-size:28px;line-height:38px} .mb-lead{font-size:16px;line-height:27px}
  .mb-sum{margin-top:28px;padding:22px 0 4px} .mb-sum-p{font-size:16px;line-height:27px}
  .mb-sec{padding-top:40px} .mb-sec h2{font-size:21px;line-height:29px} .mb-sec p{font-size:16px;line-height:27px}
  .mb-sec--cov{margin-top:44px;padding-top:30px}
}'''


def build(date=None, out_path=None):
    path = (RB.BRIEFS / f'{date}.json') if date else RB.latest()
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    pub = (doc.get('meta') or {}).get('publishedAt')
    at = datetime.datetime.fromisoformat(pub) if pub else None
    body, _dic = RB.build(doc, at)
    body = body.replace('href="stock.html?ticker=', 'href="/stock.html?ticker=')   # 시안 폴더 밖 실사이트 종목 페이지로
    title = re.sub(r'<[^>]+>', '', (doc['title'].get('ko') or '')).strip()
    html = (C.head(f'{title} — 모닝브리핑 디자인 시안 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('모닝브리핑') + '\n<main class="wrap">\n  <article class="mb">\n' + body + '\n  </article>\n</main>\n' + C.FOOTER + '\n'
            + '<script>\n' + C.JS + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'preview/brief.html'
    C.emit(out, html)
    print(f'✅ {out} · {Path(path).stem} · {len(html):,}자')


if __name__ == '__main__':
    a = sys.argv[1:]
    date = a[0] if a and re.fullmatch(r'\d{4}-\d\d-\d\d', a[0]) else None
    out = (a[1] if date and len(a) > 1 else (a[0] if a and not date else None))
    build(date, out)
