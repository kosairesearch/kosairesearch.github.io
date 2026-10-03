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
import number_spacing  # noqa: E402  금액 표기 통일(render_brief.main 과 같은 규칙)

CSS = '''
/* 글 한 단 — 읽기 폭 720 */
.mb{max-width:720px;padding:44px 0 0}
.mb-date{font:500 13px/20px var(--font);color:var(--ink-62)} .mb-date::before{content:"모닝브리핑 · "} html[lang="en"] .mb-date::before{content:"Morning Brief · "}
.mb h1{margin:12px 0 0;font:700 36px/48px var(--font);letter-spacing:-.025em;text-wrap:balance}
.mb-lead{margin:18px 0 0;font:400 18px/30px var(--font);color:var(--ink-72)}
.mb-meta{margin-top:14px;font:400 13px/20px var(--font);color:var(--ink-62)}
/* 요약 — 상자 대신 위아래 줄 */
.mb-sum{margin:36px 0 0;padding:26px 0 8px;border-top:1px solid var(--line);border-bottom:1px solid var(--hair)}
.mb-sum-h{font:600 12px/16px var(--font);color:var(--ink-62);margin:0 0 14px}
.mb-sum-p{margin:0 0 18px;font:400 18px/30px var(--font);letter-spacing:-.005em}
/* 절 */
.mb-sec{padding-top:48px}
.mb-sec h2{margin:0 0 18px;font:700 24px/32px var(--font);letter-spacing:-.02em;text-wrap:balance}
.mb-sec p{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em} .mb-sec p:last-child{margin-bottom:0}
.mb-sec a{text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px;text-decoration-thickness:1px} .mb-sec a:hover{text-decoration-color:var(--ink)}
.mb-sec b{font-weight:600}
/* KOSAI 리포트 확인 지점 — 우리 리포트에서 나온 절이라 줄 하나로 구분 */
.mb-sec--cov{margin-top:56px;padding-top:36px;border-top:1px solid var(--line)}
.mb-src{font:600 12px/16px var(--font);color:var(--ink-62);margin:0 0 10px}
.mb-disc{margin:56px 0 0;padding-top:18px;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-62)}
'''

MOBILE_CSS = '''@media (max-width:820px){
  .mb{padding:20px 0 0} .mb h1{font-size:28px;line-height:38px} .mb-lead{font-size:16px;line-height:27px}
  .mb-sum{margin-top:28px;padding:22px 0 4px} .mb-sum-p{font-size:16px;line-height:27px}
  .mb-sec{padding-top:40px} .mb-sec h2{font-size:21px;line-height:29px} .mb-sec p{font-size:16px;line-height:27px}
  .mb-sec--cov{margin-top:44px;padding-top:30px}
}'''

# ── 지난 호(2026-10-04 사장 "모닝브리핑 지난 호 스테이징에 만들어봐" → "그냥 최대한 좋은 쪽으로 해줘") ─────────────────────────
# 발행한 브리핑(meta.publishedAt)마다 호별 페이지 brief-YYYY-MM-DD.html 과 목록 brief-archive.html 을 낸다 — 스테이징과 실사이트(루트).
# 시안(preview)에는 없다 — page_html() 은 issue 를 주지 않으면 전과 글자 하나까지 같은 페이지를 낸다.
# 페이지는 폴더(brief/…) 없이 다른 페이지와 같은 층에 둔다 — 모듈 · 도장(?v=) · 검사가 모두 그 층을 본다.
#   · 호수는 발행할 때 브리핑에 적어 둔 meta.issueNo 다(render_brief 가 처음 발행할 때 적는다 · 그 전 31편은 발행한 순서로 채웠다).
#     매번 세지 않으므로 지난 호 하나를 내려도 뒤 호수가 밀리지 않는다. 적힌 호수가 없으면 발행한 순서로 센다.
#   · 대표 주소(canonical) — 가장 최근 호는 brief.html 이 대표다(같은 글이 두 주소에 있어 검색엔진에 하나를 알린다). 그날 고정 페이지는
#     다음 호가 나오면 자기 주소가 대표가 된다. 지난 호마다 그 호의 요약으로 검색 설명을 단다(실사이트만 · 스테이징은 noindex).
ARCHIVE = 'brief-archive.html'

ISSUE_EN = {'지난 호': 'Past issues', '이전 호': 'Previous issue', '다음 호': 'Next issue', '지난 호 전체 보기': 'View all past issues',
            '지난 호입니다.': 'This is a past issue.', '최신 호 보기': 'Read the latest issue', '이전 호와 다음 호': 'Previous and next issues',
            '모닝브리핑 지난 호': 'Morning Brief archive'}

ISSUE_CSS = '''
/* 지난 호 — 날짜 줄의 호수 · 지난 호 알림 · 이전 호와 다음 호 */
.mb-date[data-no]::before{content:"모닝브리핑 " attr(data-no) " · "} html[lang="en"] .mb-date[data-no]::before{content:"Morning Brief No. " attr(data-n) " · "}
.mb-old{margin:0 0 22px;padding:0 0 12px;border-bottom:1px solid var(--hair);font:500 13px/20px var(--font);color:var(--ink-62)}
.mb-old a{margin-left:6px;color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .mb-old a:hover{text-decoration-color:var(--ink)}
.mb-nav{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:0 40px;margin:56px 0 0;border-top:1px solid var(--line)}
.mb-nv{display:block;padding:20px 0 0}
.mb-nv--next{grid-column:2;text-align:right}
.mb-nv-k{display:block;font:600 12px/16px var(--font);color:var(--ink-62)}
.mb-nv-t{display:block;margin-top:8px;font:600 16px/24px var(--font);letter-spacing:-.01em;color:var(--ink);text-wrap:pretty}
.mb-nv:hover .mb-nv-t{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
.mb-nv-d{display:block;margin-top:6px;font:400 13px/20px var(--font);color:var(--ink-62)} .mb-nv-d span+span::before{content:" · "}
.mb-all{margin:32px 0 0;padding-top:18px;border-top:1px solid var(--hair)}
.mb-all a{display:inline-flex;align-items:center;gap:6px;font:500 14px/20px var(--font);color:var(--ink-72)} .mb-all a:hover{color:var(--ink)}
.mb-all svg{width:14px;height:14px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
'''
ISSUE_MOBILE_CSS = '''@media (max-width:820px){
  .mb-nav{grid-template-columns:minmax(0,1fr);margin-top:44px}
  .mb-nv--next{grid-column:1;text-align:left;margin-top:20px;border-top:1px solid var(--hair)}
  .mb-nv-t{font-size:15px;line-height:23px}
}'''

ARCHIVE_CSS = '''
.ba{max-width:720px;padding:0 0 88px}
.ba-m{margin-top:44px}
.ba-m h2{margin:0;padding-bottom:10px;border-bottom:1px solid var(--line);font:600 13px/20px var(--font);color:var(--ink-62)}
.ba-list{list-style:none;margin:0;padding:0}
.ba-list a{display:grid;grid-template-columns:64px 112px minmax(0,1fr);gap:0 16px;align-items:baseline;padding:15px 0;border-bottom:1px solid var(--hair)}
.ba-no{font:500 13px/22px var(--font);color:var(--ink-62);white-space:nowrap}
.ba-d{font:400 14px/22px var(--font);color:var(--ink-72);white-space:nowrap}
.ba-t{font:600 16px/24px var(--font);letter-spacing:-.01em;color:var(--ink);text-wrap:pretty}
.ba-list a:hover .ba-t{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
'''
ARCHIVE_MOBILE_CSS = '''@media (max-width:820px){
  .ba-m{margin-top:36px}
  .ba-list a{grid-template-columns:auto minmax(0,1fr);gap:2px 10px;padding:14px 0}
  .ba-t{grid-column:1/-1;font-size:15px;line-height:23px}
}'''

ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'


def issue_file(date):
    return f'brief-{date}.html'


def _day(s):
    return datetime.date.fromisoformat(s)


def _date_ko(s):
    d = _day(s)
    return f'{d.year}년 {d.month}월 {d.day}일 ({RB.WEEK_KO[d.weekday()]})'


def _date_en(s):
    d = _day(s)
    return f'{RB.WEEK_EN[d.weekday()][:3]}, {RB.MON_EN[d.month - 1][:3]} {d.day}, {d.year}'


def _md_ko(s):
    d = _day(s)
    return f'{d.month}월 {d.day}일 ({RB.WEEK_KO[d.weekday()]})'


def _md_en(s):
    d = _day(s)
    return f'{RB.WEEK_EN[d.weekday()][:3]}, {RB.MON_EN[d.month - 1][:3]} {d.day}'


def _no(n):
    return f'제{n}호', f'No. {n}'


def _titles(doc):
    """(한국어, 영어) 제목 — 본문 h1 과 같은 글자(금액 표기를 맞춘 뒤 · 링크와 굵게 표시를 뺀 글)."""
    t = number_spacing.normalize_report(doc)[1]['title']
    return RB.to_key(t.get('ko') or ''), (t.get('en') or '').strip()


def number_of(doc, pos):
    """호수 — 발행할 때 적어 둔 meta.issueNo. 없으면 pos(발행한 순서 · 1부터)."""
    n = (doc.get('meta') or {}).get('issueNo')
    return n if isinstance(n, int) and not isinstance(n, bool) and n > 0 else pos


def next_issue_no(date):
    """처음 발행하는 브리핑(date)에 붙일 호수 — 이미 발행한 다른 호 가운데 가장 큰 호수 + 1(render_brief 가 부른다)."""
    others = [doc for d, doc in published() if d != date]
    return max((number_of(doc, j + 1) for j, doc in enumerate(others)), default=0) + 1


def published():
    """발행한 브리핑 — [(날짜, 문서)] 오래된 순. 만들어만 두고 올리지 않은 원고(9월 13일 시험 원고 등)는 빠진다."""
    out = []
    for f in sorted(p for p in RB.BRIEFS.glob('*.json') if re.fullmatch(r'\d{4}-\d\d-\d\d', p.stem)):
        try:
            doc = json.loads(f.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if (doc.get('meta') or {}).get('publishedAt'):
            out.append((f.stem, doc))
    return out


def issue_info(items, i):
    """items[i] 의 호수 · 이전 호 · 다음 호 · 최신 여부."""
    def side(j):
        if 0 <= j < len(items):
            d, doc = items[j]
            return {'date': d, 'no': number_of(doc, j + 1), 'title': _titles(doc)}
        return None
    return {'no': number_of(items[i][1], i + 1), 'date': items[i][0], 'prev': side(i - 1), 'next': side(i + 1), 'latest': i == len(items) - 1}


def _issue_parts(body, dic, issue):
    """호별 페이지의 덧붙임 — 날짜 줄의 호수, 지난 호 알림(최신 호가 아닐 때), 이전 호와 다음 호."""
    no_ko, no_en = _no(issue['no'])
    body = body.replace('<div class="mb-date">', f'<div class="mb-date" data-no="{no_ko}" data-n="{issue["no"]}">', 1)
    if not issue['latest']:
        body = '    <p class="mb-old">지난 호입니다.<a href="brief.html">최신 호 보기</a></p>\n' + body
    cards = []
    for side, cls, k in (('prev', 'mb-nv--prev', '이전 호'), ('next', 'mb-nv--next', '다음 호')):
        s = issue[side]
        if not s:
            continue
        sno_ko, sno_en = _no(s['no'])
        t_ko, t_en = s['title']
        cards.append(f'<a class="mb-nv {cls}" href="{issue_file(s["date"])}"><span class="mb-nv-k">{k}</span>'
                     f'<span class="mb-nv-t">{html_escape(t_ko)}</span>'
                     f'<span class="mb-nv-d"><span>{sno_ko}</span><span>{_date_ko(s["date"])}</span></span></a>')
        dic[sno_ko] = sno_en
        dic[_date_ko(s['date'])] = _date_en(s['date'])
        if t_en:
            dic[t_ko] = t_en
    body += ('\n    <nav class="mb-nav" aria-label="이전 호와 다음 호">' + ''.join(cards) + '</nav>'
             f'\n    <p class="mb-all"><a href="{ARCHIVE}">지난 호 전체 보기 {ARROW}</a></p>')
    dic.update(ISSUE_EN)
    return body, dic


def _issue_desc(doc, issue, limit=110):
    """호별 페이지의 검색 설명 — '2026년 10월 2일 (금) 모닝브리핑 제31호.' 뒤에 그 호의 요약을 문장 단위로 limit 자까지.
    요약(summary)이 없는 초기 호(8월 18일 무렵)는 머리말(lead)을 쓴다."""
    ko = lambda v: ((v.get('ko') if isinstance(v, dict) else v) or '') if v else ''  # noqa: E731
    text = RB.to_key(ko(doc.get('summary')) or ko(doc.get('lead')))
    out = f"{_date_ko(issue['date'])} 모닝브리핑 {_no(issue['no'])[0]}."
    for sent in re.split(r'(?<=다\.)\s+', text):
        if len(out) + 1 + len(sent) <= limit:
            out += ' ' + sent
            continue
        if len(out) < limit * 0.65:   # 아직 짧으면(첫 문장부터 길거나 앞 문장이 짧으면) 낱말 경계에서 자르고 줄임표
            cut = sent[:max(0, limit - len(out) - 2)].rsplit(' ', 1)[0].rstrip(',')
            out += (' ' + cut + '…') if cut else ''
        break
    return out


def _issue_seo(doc, issue, head_title):
    """실사이트 호별 페이지의 검색 노출 머리. 가장 최근 호는 brief.html 이 대표 주소다 — 다음 호가 나오면 자기 주소가 된다."""
    import html as _h
    url = f"{C.SITE}/{issue_file(issue['date'])}"
    canon = f'{C.SITE}/brief.html' if issue['latest'] else url
    return C.seo_tags(canon, _h.unescape(head_title), _issue_desc(doc, issue), og_type='article')


def html_escape(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def latest_published():
    """페이지에 낼 브리핑 — 발행된 것(meta.publishedAt) 가운데 가장 늦은 날. 만들어만 두고 올리지 않은 원고
    (발행 대기 초안 · 휴장일 시험 · 9월 13일 시험 원고)가 페이지에 나가지 않게 한다. 발행된 것이 하나도 없으면 가장 늦은 파일."""
    files = sorted(p for p in RB.BRIEFS.glob('*.json') if re.fullmatch(r'\d{4}-\d\d-\d\d', p.stem))
    for f in reversed(files):
        try:
            if (json.loads(f.read_text(encoding='utf-8')).get('meta') or {}).get('publishedAt'):
                return f
        except (ValueError, OSError):
            continue
    return files[-1] if files else None


def page_html(doc, at, issue=None, page='brief.html'):
    """브리핑 한 편의 페이지(모드에 맞는 옷). 본문은 실사이트와 같은 render_brief.build() — 아침 브리핑 작업(render_brief.py)도 이 함수로
    실사이트 brief.html 을 그린다. 금액 표기는 render_brief 와 같은 규칙으로 맞춘 뒤 그린다(두 길이 같은 글을 내게).
    issue(issue_info) 를 주면 지난 호 덧붙임(호수 · 지난 호 알림 · 이전 호와 다음 호)을 넣는다(스테이징 · 실사이트).
    page — 내보낼 파일 이름. 실사이트의 호별 페이지(brief-YYYY-MM-DD.html)는 검색 노출 머리를 여기서 단다(brief.html 은 finish 가 LIVE_SEO 로)."""
    _n, doc = number_spacing.normalize_report(doc)
    body, dic = RB.build(doc, at)
    if issue:
        body, dic = _issue_parts(body, dic, issue)
    body = body.replace('href="stock.html?ticker=', 'href="/stock.html?ticker=')   # 시안 폴더 밖 실사이트 종목 페이지로
    title = re.sub(r'<[^>]+>', '', (doc['title'].get('ko') or '')).strip()
    head_title = f'{title} — ' + (C.title('모닝브리핑') if C.MODE != 'preview' else '모닝브리핑 디자인 시안 | KOSAI')
    # 영어 화면(i18n.js) — 본문 문단은 data-i18n-block 이고, 그 영어는 실사이트와 같은 render_brief 사전(dic)이다.
    # 문서 제목은 제목 안의 ' — ' 때문에 조각으로는 못 맞추므로 통째로 넣는다.
    i18n = ''
    if C.MODE in ('staging', 'live'):
        title_en = re.sub(r'<[^>]+>', '', (doc['title'].get('en') or '')).strip()
        if title_en:
            dic[C._i18n_norm(head_title)] = f'{title_en} — Morning Brief | KOSAI'
        if C.MODE == 'live':   # 영어 문단의 종목 링크도 종목마다 만든 페이지로(본문 쪽은 comp_common.finish 가 바꾼다)
            dic = {k: re.sub(r'href="stock\.html\?ticker=([0-9A-Za-z]{6})"', r'href="/stock/\1.html"', v) if isinstance(v, str) else v
                   for k, v in dic.items()}
        i18n = ('<script type="application/json" data-kos-i18n>'
                + json.dumps(dic, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + '</script>\n')
    css = C.CSS + '\n' + CSS + ('\n' + ISSUE_CSS if issue else '') + '\n' + C.MOBILE_CSS + '\n' + MOBILE_CSS + ('\n' + ISSUE_MOBILE_CSS if issue else '')
    extra = _issue_seo(doc, issue, head_title) if C.MODE == 'live' and issue and page != 'brief.html' else ''
    return (C.head(head_title, extra=extra) + '\n<style>\n' + css + '\n</style>\n</head>\n<body>\n'
            + C.nav('모닝브리핑') + '\n<main class="wrap">\n  <article class="mb">\n' + body + '\n  </article>\n</main>\n' + C.FOOTER + '\n' + i18n
            + '<script>\n' + C.JS + '\n</script>\n</body>\n</html>')


def _at(doc):
    pub = (doc.get('meta') or {}).get('publishedAt')
    return datetime.datetime.fromisoformat(pub) if pub else None


def build(date=None, out_path=None):
    path = (RB.BRIEFS / f'{date}.json') if date else latest_published()
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    issue = None
    if C.MODE in ('staging', 'live'):   # 지난 호(위 '지난 호' 머리말). 이웃 호를 못 읽어도 이번 호는 그린다(--check 는 build_archive 가 잡는다)
        try:
            items = published()
            dates = [d for d, _ in items]
            if Path(path).stem in dates:
                issue = issue_info(items, dates.index(Path(path).stem))
        except Exception as e:
            print(f'⚠ 지난 호 연결(이전 호 · 다음 호)을 붙이지 못했다 — 이번 호만 그린다: {e}')
            issue = None
    html = page_html(doc, _at(doc), issue)
    out = Path(out_path) if out_path else ROOT / 'preview/brief.html'
    C.emit(out, html)
    print(f'✅ {out} · {Path(path).stem} · {len(html):,}자')


def archive_html(items):
    """지난 호 목록 — 최신 호부터, 달마다 묶는다. 제목 · 날짜 · 호수의 영어는 이 페이지의 사전에 싣는다."""
    n = len(items)
    dic = dict(ISSUE_EN)
    sub = f'지금까지 발행한 모닝브리핑 {n}편을 최신 호부터 보여 드립니다.'
    dic[sub] = f'All {n} issues of the Morning Brief published so far, newest first.'
    head_title = C.title('모닝브리핑 지난 호')
    dic[C._i18n_norm(head_title)] = 'Morning Brief archive | KOSAI'
    groups, cur = [], None
    for i in range(n - 1, -1, -1):
        d, doc = items[i]
        mon = d[:7]
        if mon != cur:
            dd = _day(d)
            mk, me = f'{dd.year}년 {dd.month}월', f'{RB.MON_EN[dd.month - 1]} {dd.year}'
            dic[mk] = me
            groups.append([mk, []])
            cur = mon
        no_ko, no_en = _no(number_of(doc, i + 1))
        t_ko, t_en = _titles(doc)
        dic[no_ko] = no_en
        dic[_md_ko(d)] = _md_en(d)
        if t_en:
            dic[t_ko] = t_en
        groups[-1][1].append(f'<li><a href="{issue_file(d)}"><span class="ba-no">{no_ko}</span><span class="ba-d">{_md_ko(d)}</span>'
                             f'<span class="ba-t">{html_escape(t_ko)}</span></a></li>')
    lists = ''.join(f'\n  <section class="ba-m"><h2>{mk}</h2><ol class="ba-list">' + ''.join(rows) + '</ol></section>' for mk, rows in groups)
    i18n = ('<script type="application/json" data-kos-i18n>'
            + json.dumps(dic, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + '</script>\n')
    extra = C.seo_tags(f'{C.SITE}/{ARCHIVE}', head_title, sub) if C.MODE == 'live' else ''   # 실사이트 — 대표 주소 · 검색 설명
    return (C.head(head_title, extra=extra) + '\n<style>\n' + C.CSS + '\n' + C.PROSE_CSS + '\n' + ARCHIVE_CSS + '\n' + C.MOBILE_CSS + '\n' + ARCHIVE_MOBILE_CSS
            + '\n</style>\n</head>\n<body>\n' + C.nav('모닝브리핑') + '\n<main class="wrap">\n  <header class="page-hero">\n'
            + '    <p class="crumb">모닝브리핑</p>\n    <h1>지난 호</h1>\n' + f'    <p class="sub">{sub}</p>\n  </header>\n'
            + '  <div class="ba">' + lists + '\n  </div>\n</main>\n' + C.FOOTER + '\n' + i18n + '<script>\n' + C.JS + '\n</script>\n</body>\n</html>')


def build_archive(out_dir):
    """지난 호(스테이징 · 실사이트) — 발행한 브리핑마다 brief-YYYY-MM-DD.html, 그리고 목록 brief-archive.html. 발행 목록에서 빠진 호의 페이지
    (원고를 내렸을 때)는 지운다 — 남겨 두면 목록에 없는 호가 주소로는 열린다.
    모두 만든 뒤에 쓴다 — 중간에 멈추면 있던 파일을 하나도 건드리지 않는다(아침 브리핑 작업이 반쯤 바뀐 지난 호를 올리지 않게).
    발행한 브리핑을 하나도 못 읽었거나 한 번에 세 호 이상이 목록에서 빠지면 지우지 않고 멈춘다 — 자료를 잘못 읽은 날 지난 호가 통째로
    사라지거나 호수가 밀리지 않게."""
    assert C.MODE in ('staging', 'live'), C.MODE
    out_dir = Path(out_dir)
    items = published()
    if not items:
        raise RuntimeError('발행한 브리핑을 하나도 읽지 못했다 — 지난 호를 만들지 않는다')
    done = (lambda h: C.live_stamp(h)) if C.MODE == 'live' else (lambda h: h)   # C.emit 과 같다 — 실사이트는 ?v= 도장까지
    pages = {}
    for i, (d, doc) in enumerate(items):
        name = issue_file(d)
        pages[name] = done(C.finish(page_html(doc, _at(doc), issue_info(items, i), page=name), name))
    pages[ARCHIVE] = done(C.finish(archive_html(items), ARCHIVE))
    stale = sorted(f for f in out_dir.glob('brief-????-??-??.html') if f.name not in pages)
    if len(stale) > 2:
        raise RuntimeError(f'발행 목록에서 {len(stale)}호가 한꺼번에 빠졌다 — 지우지 않고 멈춘다: ' + ', '.join(f.name for f in stale[:5]))
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, html in pages.items():
        (out_dir / name).write_text(html, encoding='utf-8')
    for f in stale:
        f.unlink()
        print(f'🗑 {f.name} — 발행 목록에 없는 호라 지웠다')
    print(f'✅ {out_dir / ARCHIVE} · 지난 호 {len(items)}편')


if __name__ == '__main__':
    a = sys.argv[1:]
    date = a[0] if a and re.fullmatch(r'\d{4}-\d\d-\d\d', a[0]) else None
    out = (a[1] if date and len(a) > 1 else (a[0] if a and not date else None))
    build(date, out)
