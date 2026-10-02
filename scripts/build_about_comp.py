#!/usr/bin/env python3
"""About(About.html) — 새 디자인 시안(comp).

    python3 scripts/build_about_comp.py            # preview/about.html

본문 글은 실사이트 About.html 에서 그대로 가져온다(생성기가 글자 일치를 검사). 머리(제목 · 서브 · 세 단계)만 카피 가이드대로
새로 썼다(2026-10-02 — 실사이트 머리는 마침표 끝 제목 · '코스피·코스닥 전 종목' · 영문 COLLECT 같은 표기라). 바뀌는 것은 그 밖에 옷뿐:
유리 카드(단계·출처·표·면책·연락처)를 선 목록과 열린 표로 바꾸고, 리포트 상세와 같은 목차를 붙인다.
영문 kicker(WHAT WE DO …)는 번호만 남긴다 — 한글 제목이 이미 그 말을 한다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
/* 세 단계 — 머리 띠 바로 아래. 카드 대신 위 선 하나씩 */
.steps3{display:grid;grid-template-columns:repeat(3,1fr);gap:0 32px;margin-top:56px;max-width:820px}
.steps3>div{border-top:1px solid var(--line);padding-top:14px} .steps3 .k{font:500 12px/16px var(--font);color:var(--ink-62)} .steps3 h3{margin:8px 0 6px;font:600 16px/24px var(--font)} .steps3 p{margin:0;font:400 14px/22px var(--font);color:var(--ink-72)}
/* 절 안 부품 */
.sec .prose{max-width:720px}
.steps4{display:grid;grid-template-columns:1fr 1fr;gap:0 32px;margin-top:32px} .steps4>div{border-top:1px solid var(--hair);padding:14px 0 18px} .steps4 .k{font:500 12px/16px var(--font);color:var(--ink-62)} .steps4 h4{margin:6px 0 4px;font:600 15px/22px var(--font)} .steps4 p{margin:0;font:400 14px/22px var(--font);color:var(--ink-72)}
.srcs{margin-top:28px;border-top:1px solid var(--line)} .src{display:grid;grid-template-columns:160px minmax(0,1fr);gap:4px 24px;padding:18px 0;border-bottom:1px solid var(--hair);color:inherit;text-decoration:none}
.src h4{margin:0;font:600 16px/24px var(--font)} .src .kind{font:500 12px/16px var(--font);color:var(--ink-62)} .src p{margin:0;font:400 14px/22px var(--font);color:var(--ink-72)} .src .link{margin-top:6px;font:500 12px/16px var(--font);color:var(--ink-62);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .src:hover .link{color:var(--ink)}
.abil{display:grid;grid-template-columns:1fr 1fr;gap:0 40px;margin-top:32px} .abil>div{border-top:1px solid var(--line);padding-top:14px} .abil .k{font:500 12px/16px var(--font);color:var(--ink-62)} .abil h4{margin:6px 0 10px;font:600 16px/24px var(--font)} .abil ul{margin:0;padding-left:18px;font:400 14px/22px var(--font);color:var(--ink-72)} .abil li{margin:0 0 6px} .abil li::marker{color:var(--ink-30)}
.tbl.sched th:nth-child(1){width:160px} .tbl.sched th:nth-child(2){width:100px} .tbl.sched th:nth-child(3){width:200px} .tbl.sched th,.tbl.sched td{text-align:left} .tbl.sched td{white-space:normal;vertical-align:top} .tbl.sched td b{font-weight:600}
.tbl-note{margin:14px 0 0;font:400 13px/20px var(--font);color:var(--ink-62)}
.disc-list{margin-top:28px;border-top:1px solid var(--line)} .disc-list>div{padding:16px 0;border-bottom:1px solid var(--hair)} .disc-list b{display:block;font:600 15px/22px var(--font)} .disc-list p{margin:4px 0 0;font:400 14px/22px var(--font);color:var(--ink-72)}
.disc-final{margin:24px 0 0;font:600 16px/26px var(--font)}
.contacts{display:grid;grid-template-columns:1fr 1fr;gap:0 40px;margin-top:8px} .contacts>div{border-top:1px solid var(--line);padding-top:14px} .contacts .k{font:500 12px/16px var(--font);color:var(--ink-62)} .contacts .v{margin:6px 0 6px;font:600 18px/26px var(--font)} .contacts p{margin:0;font:400 14px/22px var(--font);color:var(--ink-72)}
'''
MOBILE_CSS = '''@media (max-width:820px){
  .steps3{grid-template-columns:1fr;gap:0;margin-top:36px} .steps3>div{padding:14px 0 18px;border-top:1px solid var(--hair)} .steps3>div:first-child{border-top-color:var(--line)}
  .steps4,.abil,.contacts{grid-template-columns:1fr;gap:0} .abil>div+div,.contacts>div+div{margin-top:28px}
  .src{grid-template-columns:1fr;gap:4px}
}
/* 갱신 주기 표 — 휴대폰에서는 네 칸이 안 들어가 '비고'가 한 글자씩 세로로 떨어졌다(2026-09-26 사장). 행을 세로로 쌓는다:
   이름 / 갱신 주기 · 다음 업데이트(이름표는 ::before) / 비고는 작은 글로. 행 markup 은 실사이트와 같아야 해서(check_sectors) CSS 만 쓴다. */
@media (max-width:720px){
  .tbl.sched thead{display:none}
  .tbl.sched,.tbl.sched tbody,.tbl.sched tr,.tbl.sched td{display:block;width:auto}
  .tbl.sched tr{padding:16px 0 18px;border-top:1px solid var(--hair)} .tbl.sched tbody tr:first-child{border-top:1px solid var(--line)}
  .tbl.sched td{padding:0;border:0;position:static;background:none;font:400 14px/22px var(--font);color:var(--ink);white-space:normal}
  .tbl.sched td:first-child{font:600 15px/22px var(--font);margin-bottom:8px}
  .tbl.sched td:nth-child(2),.tbl.sched td:nth-child(3){display:flex;gap:12px;margin-top:2px}
  .tbl.sched td:nth-child(2)::before{content:'갱신 주기'} .tbl.sched td:nth-child(3)::before{content:'다음 업데이트'}
  .tbl.sched td:nth-child(2)::before,.tbl.sched td:nth-child(3)::before{flex:0 0 88px;color:var(--ink-62)}
  .tbl.sched td:nth-child(4){margin-top:10px;font:400 13px/20px var(--font);color:var(--ink-62)}
  .tbl.sched td:empty{display:none}
}'''


# 머리 — 실사이트의 "한국 상장사 정보, 누구나 제대로 이해할 수 있도록." · "코스피·코스닥 전 종목의 …" 를 다시 썼다
H1 = '누구나 제대로 이해할\u00a0수\u00a0있는 상장사 정보'   # '이해할 / 수' 로 끊기지 않게(카피 가이드 4-5 줄바꿈)
SUB = ('KOSAI는 국내 상장 종목의 공시와 시세 자료를 바탕으로 기업 분석 리포트를 발행합니다. '
       '개인 투자자가 종목을 검토할 때 출발점으로 삼을 수 있는 자료를 만드는 것이 목표입니다.')
STEPS = [('01 수집', '시세와 시가총액, 공시', '여러 곳에 흩어진 원천 데이터를 모읍니다.'),
         ('02 정리', 'AI 분석과 정리', '사람이 읽기 쉬운 형태로 구조화합니다.'),
         ('03 공개', '출처 공개', '근거 데이터와 갱신 시각을 함께 표시합니다.')]


def text_of(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


def g(pat, s, flags=re.S):
    m = re.search(pat, s, flags)
    return m.group(1).strip() if m else ''


def build(out_path):
    src = (ROOT / 'About.html').read_text(encoding='utf-8')
    a = src.index('<div class="wrap" data-screen-label="08 About">')
    b = src.index('<footer', a)
    live = re.sub(r'<script.*?</script>', '', src[a:b], flags=re.S)

    # 머리 — 새로 쓴 글(위 H1 · SUB · STEPS)
    steps3 = ''.join(f'<div><div class="k">{k}</div><h3>{h}</h3><p>{p}</p></div>' for k, h, p in STEPS)

    secs = re.findall(r'<section class="sec"[^>]*>(.*?)</section>', live, re.S)
    toc, chips, body, pieces = [], [], [], []
    for i, sc in enumerate(secs, 1):
        title = g(r'<h2 class="sec-title">(.*?)</h2>', sc)
        parts = []
        lead = g(r'<p class="sec-lead">(.*?)</p>', sc)
        prose = g(r'<div class="prose">(.*?)</div>', sc)
        if prose:
            parts.append(f'<div class="prose">{prose}</div>')
        if lead and 'sec-lead" style' not in sc.split(lead)[0][-40:]:
            parts.append(f'<div class="prose lead"><p>{lead}</p></div>')
        notes = re.findall(r'<p class="sec-lead" style="[^"]*">(.*?)</p>', sc, re.S)
        stepc = re.findall(r'<div class="stepc glass"><span class="n">(.*?)</span><h4>(.*?)</h4><p>(.*?)</p></div>', sc, re.S)
        if stepc:
            parts.append('<div class="steps4">' + ''.join(f'<div><div class="k">{k}</div><h4>{h}</h4><p>{p}</p></div>' for k, h, p in stepc) + '</div>')
        srcs = re.findall(r'<a class="src glass" href="([^"]+)"[^>]*><div class="src-head"><h4>(.*?)</h4><span class="src-kind">(.*?)</span></div><p>(.*?)</p><span class="link">(.*?)</span></a>', sc, re.S)
        if srcs:
            parts.append('<div class="srcs">' + ''.join(f'<a class="src" href="{u}" target="_blank" rel="noopener"><div><h4>{n}</h4><div class="kind">{k}</div></div><div><p>{p}</p><div class="link">{l}</div></div></a>' for u, n, k, p, l in srcs) + '</div>')
        abil = re.findall(r'<div class="ability (?:can|cant) glass">\s*<div class="ah">(.*?)</div><h4>(.*?)</h4>\s*(<ul>.*?</ul>)\s*</div>', sc, re.S)
        if abil:
            parts.append('<div class="abil">' + ''.join(f'<div><div class="k">{k}</div><h4>{h}</h4>{ul}</div>' for k, h, ul in abil) + '</div>')
        table = g(r'(<table class="dt">.*?</table>)', sc)
        if table:
            table = table.replace('class="dt"', 'class="tbl sched"')   # 행은 그대로 — check_sectors.py 가 실사이트 행과 글자 하나까지 견준다
            table = re.sub(r' style="width:\d+px"', '', table)
            parts.append(f'<div class="tbl-wrap" style="margin-top:28px">{table}</div>')
        items = re.findall(r'<div class="item"><b>(.*?)</b><p>(.*?)</p></div>', sc, re.S)
        if items:
            parts.append('<div class="disc-list">' + ''.join(f'<div><b>{t}</b><p>{p}</p></div>' for t, p in items) + '</div>')
            fin = g(r'<p class="disc-final glass">(.*?)</p>', sc)
            if fin:
                parts.append(f'<p class="disc-final">{fin}</p>')
        for n in notes:
            parts.append(f'<p class="tbl-note">{n}</p>')
        contacts = re.findall(r'<div class="contact glass"><div class="lbl">(.*?)</div><div class="val">(.*?)</div><div class="desc">(.*?)</div></div>', sc, re.S)
        if contacts:
            parts.append('<div class="contacts">' + ''.join(f'<div><div class="k">{k}</div><div class="v">{v}</div><p>{d}</p></div>' for k, v, d in contacts) + '</div>')
        toc.append(f'<a href="#s{i:02d}"><span class="n">{i:02d}</span>{title}</a>')
        chips.append(f'<a href="#s{i:02d}">{i:02d} {title}</a>')
        body.append(f'<section class="sec wide" id="s{i:02d}"><div class="sec-h"><span class="num">{i:02d}</span><h2>{title}</h2></div>{"".join(parts)}</section>')
        pieces.append(title + ' ' + ' '.join(parts))

    html = (C.head(C.title('회사 소개')) + '\n<style>\n' + C.CSS + '\n' + C.PROSE_CSS + '\n' + C.TOC_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n' + C.TOC_MOBILE_CSS + '\n' + MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + f'''
<main class="wrap">
  <header class="ph dz">
    <p class="crumb">회사 소개</p>
    <h1>{H1}</h1>
    <p class="sub">{C.sents(SUB)}</p>
  </header>
  <div class="steps3">{steps3}</div>
  <div class="body">
    <aside class="toc" id="toc">{''.join(toc)}</aside>
    <div class="content">
      <div class="chips-mark" id="chipsMark"></div><div class="chips-bar" id="chipsBar"><nav class="chips" id="chips">{''.join(chips)}</nav></div>
      {''.join(body)}
    </div>
  </div>
</main>
''' + C.FOOTER + '\n<script>\n' + C.TOC_JS + '\n' + C.JS + '\n</script>\n</body>\n</html>')

    # 글자 검사 — 본문 여덟 절은 영문 kicker(WHAT WE DO …)만 빼고 실사이트와 같아야 한다. 머리는 새로 썼으므로 견주지 않는다
    body_live = re.sub(r'<header class="hero">.*?</header>', '', live, flags=re.S)
    want = text_of(re.sub(r'<div class="sec-kicker">.*?</div>', '', body_live, flags=re.S))
    got = text_of(' '.join(pieces))
    want_words, got_words = want.split(), got.split()
    missing = [w for w in want_words if w not in got_words and w not in ('홈', '/', 'About', 'ABOUT', 'KOSAI', '·')]
    assert not missing, f'About: 빠진 글 {missing[:12]}'
    C.emit(out_path, html)
    print(f'✅ {out_path} · {len(secs)}절 · {len(html):,}자 · 글 빠짐 없음')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'preview/about.html'))
