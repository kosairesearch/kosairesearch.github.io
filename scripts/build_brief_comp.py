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

# 머리의 새벽 그림 — 랜딩 브리핑 띠와 같은 그림(scripts/concepts/landing.py 의 DAWN_JS · 사장 2026-10-02). 아침 브리핑 작업이 이 생성기를
# 돌리므로(build_staging) 가져오지 못해도 페이지는 만든다 — 그때는 그림 없이 어두운 띠만 남는다.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'concepts'))
    from landing import DAWN_JS  # noqa: E402
except Exception as e:  # pragma: no cover
    print(f'⚠ 새벽 그림을 가져오지 못했다 — 그림 없이 만든다: {e}')
    DAWN_JS = ''

# 머리 글 — 랜딩 브리핑 띠와 같은 말(landing.copy_text 의 'brief')
MAST = ('모닝브리핑', '개장 전에 읽는<br>시장 브리핑',
        '전일 국내 증시와 간밤의 해외 시장, 주요\u00a0일정을\u00a0정리합니다. 발행 시각은 거래일 오전\u00a07시\u00a030분 전후입니다.')

CSS = '''
/* 머리 — 랜딩 브리핑 띠와 같은 무대 · 같은 그림(DAWN_JS). 글은 왼쪽 위, 그림은 글 단 오른쪽(넓은 화면) · 글 아래(한 열).
   그림의 배치 규칙은 랜딩과 같다 — 물가는 띠 아래 끝에서 140(넓은 화면) · 96(한 열) 위, 한 열에서는 글 아래에 그림 자리를 비워 둔다
   (52 + 가장 높은 탑 305 × 배율 — 랜딩 #brief>.w 와 같은 식, 띠의 아래 여백 72 에 더한다). 띠 높이는 그림이 배율 1 로 서는 640(넓은 화면) */
.mast{min-height:640px}
.mast .dawn{position:absolute;left:0;top:0;width:100%;height:100%;display:block;pointer-events:none}
.mast>.tx{position:relative;z-index:1;width:40%;min-width:360px;max-width:460px}
/* 글 한 단 — 읽기 폭 720 */
.mb{max-width:720px;padding:56px 0 0}
.mb-date{font:500 13px/20px var(--font);color:var(--ink-62)} .mb-date .no{margin-right:10px;font-weight:600;color:var(--ink)}
.mb h1{margin:12px 0 0;font:600 40px/1.3 var(--font);letter-spacing:-.03em;text-wrap:balance}
.mb-lead{margin:18px 0 0;font:400 18px/30px var(--font);color:var(--ink-72)}
.mb-meta{margin-top:14px;font:400 13px/20px var(--font);color:var(--ink-62)}
/* 요약 — 상자 대신 위아래 줄 */
.mb-sum{margin:36px 0 0;padding:26px 0 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--hair)}
.mb-sum-h{font:600 12px/16px var(--font);color:var(--ink-62);margin:0 0 14px}
.mb-sum-p{margin:0 0 18px;font:400 18px/30px var(--font);letter-spacing:-.005em}
/* 절 */
.mb-sec{padding-top:48px}
.mb-sec h2{margin:0 0 18px;font:600 24px/32px var(--font);letter-spacing:-.025em;text-wrap:balance}
.mb-sec p{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em} .mb-sec p:last-child{margin-bottom:0}
.mb-sec a{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;text-decoration-thickness:1px} .mb-sec a:hover{text-decoration-color:var(--ink)}
.mb-sec b{font-weight:600}
/* KOSAI 리포트 확인 지점 — 우리 리포트에서 나온 절이라 줄 하나로 구분 */
.mb-sec--cov{margin-top:56px;padding-top:36px;border-top:1px solid var(--line)}
.mb-src{font:600 12px/16px var(--font);color:var(--ink-62);margin:0 0 10px}
.mb-disc{margin:56px 0 0;padding-top:18px;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-62)}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .mast{min-height:0;padding-bottom:calc(72px + 52px + min(66.474vw, 305px))} .mast>.tx{width:auto;min-width:0;max-width:none}   /* 그림 자리는 띠의 아래 여백으로 — 글 묶음(.tx)에 주면 그림이 글 끝을 그만큼 아래로 읽는다 */
  .mb{padding:40px 0 0} .mb h1{font-size:28px;line-height:1.35;letter-spacing:-.025em} .mb-lead{font-size:16px;line-height:27px}
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
    # 호수 — 발행한 브리핑 수(랜딩 '제N호 읽기'와 같은 셈 · scripts/concepts/data.brief)
    names = sorted(p.name for p in RB.BRIEFS.glob('*.json'))
    no = names.index(Path(path).name) + 1 if Path(path).name in names else 0
    if no:
        assert body.count('<div class="mb-date">') == 1
        body = body.replace('<div class="mb-date">', f'<div class="mb-date"><span class="no">제{no}호</span>', 1)
    title = re.sub(r'<[^>]+>', '', (doc['title'].get('ko') or '')).strip()
    crumb, h, sub = MAST
    mast = (f'<header class="ph dz mast"><canvas class="dawn" id="dawn" aria-hidden="true"></canvas><div class="tx">'
            f'<p class="crumb">{crumb}</p><p class="h1">{h}</p><p class="sub">{C.sents(sub)}</p></div></header>')
    html = (C.head(C.title(f'{title} — 모닝브리핑')) + '\n<style>\n' + C.CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('모닝브리핑') + '\n<main class="wrap">\n  ' + mast + '\n  <article class="mb">\n' + body + '\n  </article>\n</main>\n' + C.FOOTER + '\n'
            + '<script>\n' + C.JS + '\n</script>\n' + (f'<script>{DAWN_JS}</script>\n' if DAWN_JS else '') + '</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'preview/brief.html'
    C.emit(out, html)
    print(f'✅ {out} · {Path(path).stem} · {len(html):,}자')


if __name__ == '__main__':
    a = sys.argv[1:]
    date = a[0] if a and re.fullmatch(r'\d{4}-\d\d-\d\d', a[0]) else None
    out = (a[1] if date and len(a) > 1 else (a[0] if a and not date else None))
    build(date, out)
