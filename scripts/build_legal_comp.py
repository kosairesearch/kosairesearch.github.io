#!/usr/bin/env python3
"""이용약관(Terms.html) · 개인정보처리방침(Privacy.html) — 새 디자인 시안(comp).

    python3 scripts/build_legal_comp.py            # preview/terms.html · preview/privacy.html

본문은 실사이트 파일의 .legal 안 글을 그대로 옮긴다 — 약관 글자는 한 자도 바꾸지 않는다(아래 check 가 지킨다).
바뀌는 것은 옷뿐: 카드 상자를 없애고 720px 한 단, 리포트 상세와 같은 목차(데스크톱 왼쪽 세로선 · 휴대폰 밑줄 칩).
공고일·시행일 줄은 제목 아래 메타로, 머리말 두 문단은 제목 아래 글로 간다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

PAGES = {
    'terms':   dict(src='Terms.html',   out='preview/terms.html',   h1='이용약관',
                    title='이용약관 — 디자인 시안 | KOSAI', num=re.compile(r'^제(\d+)조\s*\((.*)\)\s*$')),
    'privacy': dict(src='Privacy.html', out='preview/privacy.html', h1='개인정보처리방침',
                    title='개인정보처리방침 — 디자인 시안 | KOSAI', num=re.compile(r'^(\d+)\.\s*(.*)$')),
}

CSS = '''
.sec-h h2{font-size:20px;line-height:28px} .sec{padding-bottom:56px} .sec:last-child{padding-bottom:24px}
.intro{margin-top:28px}
/* 맺음 주석 — 실사이트의 회색 상자. 여기서는 위 선 하나와 작은 회색 글자(각주) */
.prose .note{margin-top:32px;padding-top:16px;border-top:1px solid var(--hair);font:400 13px/20px var(--font);color:var(--ink-55)}
'''
MOBILE_CSS = '''@media (max-width:820px){ .sec-h h2{font-size:18px;line-height:26px} .sec{padding-bottom:44px} }'''


def text_of(html):
    t = re.sub(r'<[^>]+>', ' ', html)
    return re.sub(r'\s+', ' ', t).strip()


def extract(src_html):
    lede = re.search(r'<div class="head">.*?<p>(.*?)</p>', src_html, re.S).group(1).strip()
    a = src_html.index('<div class="legal card glass">') + len('<div class="legal card glass">')
    b = src_html.index('</main>', a)
    legal = src_html[a:b].rstrip()
    while legal.endswith('</div>'):
        legal = legal[:-len('</div>')].rstrip()
    upd = re.search(r'<p class="upd">(.*?)</p>', legal, re.S).group(1).strip()
    rest = legal[re.search(r'<p class="upd">.*?</p>', legal, re.S).end():]
    parts = re.split(r'(?=<h2[^>]*>)', rest)
    intro = parts[0].strip()
    sections = []
    for part in parts[1:]:
        m = re.match(r'<h2[^>]*>(.*?)</h2>(.*)', part, re.S)
        body_html = m.group(2).strip()
        # 주석 안의 '운영자: … · 문의: …' 는 제 줄에 — 글자는 그대로, 줄바꿈만 넣는다(글자 검사는 공백을 하나로 본다)
        body_html = re.sub(r'(<div class="note">[^<]*?)\s+(운영자:)', r'\1<br>\2', body_html)
        sections.append((m.group(1).strip(), body_html))
    return lede, upd, intro, sections, legal


def build(key, out_path=None):
    cfg = PAGES[key]
    src = (ROOT / cfg['src']).read_text(encoding='utf-8')
    lede, upd, intro, sections, legal = extract(src)
    toc, chips, body = [], [], []
    for i, (title, inner) in enumerate(sections, 1):
        m = cfg['num'].match(text_of(title))
        short = m.group(2) if m else text_of(title)
        toc.append(f'<a href="#s{i:02d}"><span class="n">{i:02d}</span>{short}</a>')
        chips.append(f'<a href="#s{i:02d}">{i:02d} {short}</a>')
        body.append(f'<section class="sec" id="s{i:02d}"><div class="sec-h"><h2>{title}</h2></div><div class="prose">{inner}</div></section>')
    html = (C.head(cfg['title']) + '\n<style>\n' + C.CSS + '\n' + C.PROSE_CSS + '\n' + C.TOC_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + C.TOC_MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + f'''
<main class="wrap">
  <header class="page-hero">
    <p class="crumb">정책</p>
    <h1>{cfg['h1']}</h1>
    <p class="sub">{lede}</p>
    <p class="meta">{upd}</p>
    <div class="prose intro">{intro}</div>
  </header>
  <div class="body">
    <aside class="toc" id="toc">{''.join(toc)}</aside>
    <div class="content">
      <div class="chips-mark" id="chipsMark"></div><div class="chips-bar" id="chipsBar"><nav class="chips" id="chips">{''.join(chips)}</nav></div>
      {''.join(body)}
    </div>
  </div>
</main>
''' + C.FOOTER + '\n<script>\n' + C.TOC_JS + '\n' + C.JS + '\n</script>\n</body>\n</html>')
    # 글자 검사 — 실사이트 .legal 의 글(공고일 줄 포함)과 시안 본문의 글이 같아야 한다
    want = text_of(legal)
    got = text_of(f'<p>{upd}</p>' + intro + ''.join(f'<h2>{t}</h2>{b}' for t, b in sections))
    assert want == got, f'{key}: 본문 글자가 실사이트와 다르다'
    out = ROOT / cfg['out']
    if out_path:
        out = Path(out_path)
    C.emit(out, html)
    print(f'✅ {out} · {len(sections)}절 · {len(html):,}자 · 글자 일치')


if __name__ == '__main__':
    for k in (sys.argv[1:] or PAGES):
        build(k)
