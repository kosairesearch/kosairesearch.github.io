#!/usr/bin/env python3
"""이용약관(Terms.html) · 개인정보처리방침(Privacy.html) — 새 디자인 시안(comp).

    python3 scripts/build_legal_comp.py            # preview/terms.html · preview/privacy.html

본문은 원문 파일(scripts/content/terms.src.html · privacy.src.html — 옛 실사이트 파일의 .legal 그대로)의 글을 옮긴다 —
약관 글자는 한 자도 바꾸지 않는다(아래 check 가 지킨다). 실사이트 · 스테이징 · 시안이 모두 이 원문에서 나온다.
바뀌는 것은 옷뿐: 카드 상자를 없애고 720px 한 단, 리포트 상세와 같은 목차(데스크톱 왼쪽 세로선 · 휴대폰 밑줄 칩).
공고일·시행일 줄은 제목 아래 메타로, 머리말 두 문단은 제목 아래 글로 간다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

# 유료화(2027-01-01 시행) — 약관 · 방침은 두 판이 있다. src 는 지금 효력이 있는 판(무료), paid 는 유료판(금융감독원 신고 서류의 약관과
# 같은 글). 스테이징은 늘 유료판, 실사이트는 시행일(C.PAID_LIVE)부터 유료판이다. 공지 기간(C.NOTICE_LIVE)에는 실사이트에 유료판을
# Terms-2027.html · Privacy-2027.html 로 미리 싣고(upcoming), 현행 약관 화면 위에 개정 안내 상자를 단다. 공지는 notice.
PAGES = {
    'terms':   dict(src='scripts/content/terms.src.html', paid='scripts/content/terms.paid.src.html', out='preview/terms.html', h1='이용약관',
                    title='이용약관', num=re.compile(r'^제(\d+)조\s*\((.*)\)\s*$'), cur='Terms.html', nxt='Terms-2027.html', noun='약관'),
    'privacy': dict(src='scripts/content/privacy.src.html', paid='scripts/content/privacy.paid.src.html', out='preview/privacy.html', h1='개인정보 처리방침',
                    title='개인정보 처리방침', num=re.compile(r'^(\d+)\.\s*(.*)$'), cur='Privacy.html', nxt='Privacy-2027.html', noun='방침'),
    'notice':  dict(src='scripts/content/notice.src.html', out='preview/notice.html', h1='이용약관 및 개인정보 처리방침 개정 안내',
                    title='약관 개정 안내', crumb='공지', num=re.compile(r'^(\d+)\.\s*(.*)$')),
    # 리포트 열람 방법 변경(2026-11-26 공고 · 12-03 시행 — 실적 분석 ~ 종합 의견을 로그인한 회원에게 · 무료). 실사이트만(C.ACCESS_NOTICE).
    'access':  dict(src='scripts/content/notice-access.src.html', out='preview/notice-access.html', h1='리포트 열람 방법 변경 안내',
                    title='리포트 열람 방법 변경 안내', crumb='공지', num=re.compile(r'^(\d+)\.\s*(.*)$')),
}

CSS = '''
.sec-h h2{font-size:20px;line-height:28px} .sec{padding-bottom:56px} .sec:last-child{padding-bottom:24px}
.intro{margin-top:28px}
/* 맺음 주석 — 실사이트의 회색 상자. 여기서는 위 선 하나와 작은 회색 글자(각주) */
.prose .note{margin-top:32px;padding-top:16px;border-top:1px solid var(--hair);font:400 13px/20px var(--font);color:var(--ink-62)}
'''
# 개정 안내 상자 — 현행 약관 화면(공지 기간) · 개정 전문 화면(시행 예정). 본문 글자 검사(.meta · .intro · section.sec) 밖에 둔다.
# 상자가 있을 때만 싣는다(실사이트 옷은 NOTICE_LIVE 를 켤 때까지 그대로).
BOX_CSS = '''.notice-box{margin:20px 0 0;padding:12px 16px;border-left:2px solid var(--ink);font:400 14px/22px var(--font);color:var(--ink)}
.notice-box a{color:inherit;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
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


def build(key, out_path=None, paid=None, upcoming=False):
    """paid — 유료판 원문으로(None 이면 스테이징이거나 시행일 뒤의 실사이트일 때). upcoming — 실사이트 공지 기간의 개정 전문 화면."""
    cfg = PAGES[key]
    if paid is None:
        paid = bool(cfg.get('paid')) and (C.MODE == 'staging' or C.PAID_LIVE)
    src = (ROOT / (cfg['paid'] if (paid or upcoming) else cfg['src'])).read_text(encoding='utf-8')
    lede, upd, intro, sections, legal = extract(src)
    h1, page_title, box = cfg['h1'], cfg['title'], ''
    # 안내 상자는 문장과 링크를 따로 둔다 — 번역 엔진은 글 조각마다 바꾸므로 링크가 문장 가운데 끼면 영어 어순이 깨진다.
    # 영어는 scripts/i18n/paid.json(실사이트에는 NOTICE_LIVE 부터 실린다).
    if upcoming:
        h1, page_title = '개정 ' + cfg['h1'], '개정 ' + cfg['title']
        # 공지 기간은 신고 수리 전일 수 있다 — 개정 전문의 '신고한 유사투자자문업자'(약관 제16조)는 시행일부터의 조문임을 상자에서 밝힌다(2026-11-25)
        box = (f'<p class="notice-box">이 {cfg["noun"]}은 2027년 1월 1일부터 시행합니다. 유료 서비스는 유사투자자문업 신고가 수리된 뒤에 시작합니다. '
               f'<a href="/{cfg["cur"]}">지금 적용되는 {cfg["h1"]} 보기</a> · <a href="/Notice.html">개정 안내 보기</a></p>')
    elif cfg.get('paid') and not paid and C.notice_on():
        box = (f'<p class="notice-box">{cfg["h1"]}이 개정되어 2027년 1월 1일부터 시행합니다. '
               f'<a href="/Notice.html">개정 안내 보기</a> · <a href="/{cfg["nxt"]}">개정 {cfg["h1"]} 보기</a></p>')
    toc, chips, body = [], [], []
    for i, (title, inner) in enumerate(sections, 1):
        m = cfg['num'].match(text_of(title))
        short = m.group(2) if m else text_of(title)
        toc.append(f'<a href="#s{i:02d}"><span class="n">{i:02d}</span>{short}</a>')
        chips.append(f'<a href="#s{i:02d}">{i:02d} {short}</a>')
        body.append(f'<section class="sec" id="s{i:02d}"><div class="sec-h"><h2>{title}</h2></div><div class="prose">{C.links(inner)}</div></section>')
    html = (C.head(C.title(page_title)) + '\n<style>\n' + C.CSS + '\n' + C.PROSE_CSS + '\n' + C.TOC_CSS + '\n' + CSS + (BOX_CSS if box else '') + '\n' + C.MOBILE_CSS + '\n' + C.TOC_MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + f'''
<main class="wrap">
  <header class="page-hero">
    <p class="crumb">{cfg.get('crumb', '정책')}</p>
    <h1>{h1}</h1>
    <p class="sub">{lede}</p>
    <p class="meta">{upd}</p>{C.links(box)}
    <div class="prose intro">{C.links(intro)}</div>
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
