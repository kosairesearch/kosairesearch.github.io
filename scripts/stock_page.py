#!/usr/bin/env python3
"""종목 페이지 한 장을 데이터에서 통째로 그리는 모듈 — 사람과 로봇이 같은 페이지를 본다.

큰 회사들처럼: HTML 을 받는 순간 리포트 글·표·지표가 다 들어 있고, 자바스크립트는 그 위에
목차 따라가기·관심종목·테마 같은 상호작용만 얹는다. 종목마다 주소가 따로 있고(stock/005930.html),
canonical·설명·OG·schema.org(JSON-LD)가 페이지마다 붙는다. 그래서 r/ 의 로봇용 사본이 필요 없다.

쓰는 곳
  · scripts/build_stock_comp.py   — 삼성전자 한 장을 CSS·JS 를 안에 넣은 시안(preview/stock.html)으로
  · scripts/build_stock_pages.py  — 전 종목(또는 표본)을 stock/{ticker}.html 로. CSS·JS 는 assets/ 에 한 벌

리포트 등급
  · v2 (data/reports_v2)  — 13개 절 전부. 차트·표·밸류에이션 포함
  · v1 (data/reports)     — 재무 수치가 없는 옛 형식. 개요·사업·최근 동향·전망·강세·약세·리스크·종합·출처
  · 없음                  — 새 상장 등. 시세·지표와 '리포트 준비 중' 안내

뼈대는 stock.html 과 같다: 절 이름·순서, 170자 문단 나누기(chunk), 숫자 표기(조/억), 면책 한 줄.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

SITE = 'https://kosai.kr'
PARA_KO = 170
SECTIONS_V2 = ['리포트 개요', '사업 구조', '실적 추이', '실적 분석', '산업 분석', '전망', '밸류에이션',
               '강세 요인', '약세 요인', '리스크 요인', '다음 체크포인트', '종합 의견', '참고 출처']
PRIMARY_SRC = [('한국거래소 (KRX) — 시세 · 시가총액 · 거래량', 'https://www.krx.co.kr'),
               ('금융감독원 전자공시 (DART) — 재무제표 · 배당 공시', 'https://dart.fss.or.kr')]
DISC = '본 콘텐츠는 AI가 시장 데이터와 웹 검색 결과를 분석한 정보 제공용이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 책임은 투자자 본인에게 있습니다. 데이터는 지연되거나 오류가 포함될 수 있습니다.'


# ── 글자·숫자 ────────────────────────────────────────────────────────────────
def esc(s):
    return str(s if s is not None else '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def chunk(text, budget=PARA_KO):
    """문장 경계에서만 자른다 — stock.html 의 chunkPara 와 같은 규칙(글자 수 예산)."""
    sents = [s for s in re.split(r'(?<=[.!?])\s+', (text or '').strip()) if s]
    out, cur = [], ''
    for s in sents:
        if cur and len(cur) + 1 + len(s) > budget:
            out.append(cur)
            cur = s
        else:
            cur = (cur + ' ' + s).strip()
    if cur:
        out.append(cur)
    return out


def paras(text):
    return ''.join(f'<p>{esc(p)}</p>' for p in chunk(text))


def pk(v):
    """{'ko':…,'en':…} 이든 문자열이든 한국어 글."""
    if isinstance(v, dict):
        return v.get('ko') or v.get('en') or ''
    return v or ''


def fwon(v):
    if v is None:
        return '—'
    a = abs(v)
    if a >= 1e12:
        return f'{v / 1e12:,.1f}조'
    if a >= 1e8:
        return f'{v / 1e8:,.0f}억'
    return f'{v:,.0f}'


def fjo(v):
    return '—' if v is None else f'{v / 1e12:,.1f}'


def pct(v, signed=False):
    if v is None:
        return '—'
    s = f'{v:+.2f}%' if signed else f'{v:.1f}%'
    return s.replace('-', '−')


def fdate(d):
    d = str(d or '')
    return f'{d[:4]}-{d[4:6]}-{d[6:]}' if re.fullmatch(r'\d{8}', d) else d


# ── 데이터 ───────────────────────────────────────────────────────────────────
def _parse_js(path, var):
    s = (ROOT / path).read_text(encoding='utf-8')
    i = s.index(var)
    i = s.index('=', i) + 1
    j = s.rindex('}')
    return json.loads(s[i:j + 1].strip().rstrip(';'))


def load_data():
    live = _parse_js('data/stocks.js', 'KOS_LIVE_DATA')
    stocks = {s['ticker']: s for s in live['stocks']}
    try:
        val = _parse_js('data/valuation.js', 'KOS_VALUATION').get('stocks', {})
    except Exception:
        val = {}
    v2 = {p.stem for p in (ROOT / 'data/reports_v2').glob('*.json')}
    v1 = {p.stem for p in (ROOT / 'data/reports').glob('*.json')} if (ROOT / 'data/reports').exists() else set()
    return {'stocks': stocks, 'dataDate': str(live.get('dataDate') or ''), 'val': val, 'v2': v2, 'v1': v1}


def load_report(tk, D):
    if tk in D['v2']:
        return json.load(open(ROOT / f'data/reports_v2/{tk}.json', encoding='utf-8')), 'v2'
    if tk in D['v1']:
        return json.load(open(ROOT / f'data/reports/{tk}.json', encoding='utf-8')), 'v1'
    return None, 'none'


# ── 차트 ─────────────────────────────────────────────────────────────────────
def bar_chart(groups, w=520, h=220, pad_l=8, pad_r=8, top=28, bottom=28):
    """groups: [(label, rev, op)] → 막대 둘(매출 먹색 · 영업이익 옅은 먹색) + 값·연도 라벨.

    막대는 SVG 가 그리되 가로로만 늘어나고(preserveAspectRatio none · 높이는 px 고정), 라벨은 HTML 로 얹는다 — 칸이
    좁아져도 글자가 12px 그대로다. 전에는 라벨까지 SVG 안에 있어 휴대폰(358px)에서 13px 이 8.8px 로 줄었다(2026-09-26).
    적자(음수)는 0선 아래로 그린다. 전에는 max(val, 0) 으로 잘라 적자가 흑자처럼 0선 위 2px 막대로 보였다.
    음수가 있으면 아래 라벨 자리 20px 을 더 둔다. 한 묶음의 두 라벨이 같은 쪽에서 겹치면 바깥쪽 라벨을 14px 더 민다.
    영업이익 흑자 라벨은 막대 왼쪽 끝에서 오른쪽으로 쓴다(가운데면 휴대폰에서 옆 매출 막대를 덮는다).
    build_stock_staging.barChart(JS)가 같은 좌표·표기를 쓴다 — 한쪽만 고치지 말 것."""
    n = len(groups)
    if not n:
        return ''
    vals = [v for g in groups for v in (g[1], g[2]) if v is not None]
    mx = max([0] + vals)
    mn = min([0] + vals)
    if mx == mn:
        mx = 1
    extra = 20 if mn < 0 else 0
    H = h + extra
    plot_h = h - top - bottom
    rng = mx - mn
    y0 = top + plot_h * mx / rng
    gw = (w - pad_l - pad_r) / n
    bw = min(22, gw * 0.24)
    gap = 6
    svg = [f'<svg viewBox="0 0 {w} {H}" preserveAspectRatio="none" aria-hidden="true">',
           f'<line x1="{pad_l}" y1="{y0:.1f}" x2="{w - pad_r}" y2="{y0:.1f}" class="ch-base" vector-effect="non-scaling-stroke"/>']
    labs = []
    for i, (label, rev, op) in enumerate(groups):
        cx = pad_l + gw * i + gw / 2
        marks = []
        for j, (val, cls) in enumerate([(rev, 'ch-rev'), (op, 'ch-op')]):
            if val is None:
                continue
            x = cx - bw - gap / 2 if j == 0 else cx + gap / 2
            bh = plot_h * abs(val) / rng
            if val:
                bh = max(1.5, bh)
                y = y0 - bh if val > 0 else y0
                svg.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}"/>')
            up = val >= 0
            # 영업이익(오른쪽) 흑자 라벨은 막대 왼쪽 끝에서 오른쪽으로 쓴다 — 가운데에 두면 옆의 더 긴 매출 막대 위로 번진다
            lft = j == 1 and up
            marks.append([x if lft else x + bw / 2, (y0 - bh - 5) if up else (y0 + bh + 5), up, fjo(val), lft])
        if len(marks) == 2 and marks[0][2] == marks[1][2] and abs(marks[0][1] - marks[1][1]) < 14:
            a, b = marks
            if a[2]:
                hi, lo = (a, b) if a[1] <= b[1] else (b, a)
                hi[1] = lo[1] - 14
            else:
                deep, sh = (a, b) if a[1] >= b[1] else (b, a)
                deep[1] = sh[1] + 14
        for mx_, ly, up, txt, lft in marks:
            cls = 'ch-val' + ('' if up else ' dn') + (' l' if lft else '')
            labs.append(f'<span class="{cls}" style="left:{mx_ / w * 100:.2f}%;top:{ly:.1f}px">{txt}</span>')
        labs.append(f'<span class="ch-lab" style="left:{cx / w * 100:.2f}%;top:{H - 20}px">{esc(label)}</span>')
    svg.append('</svg>')
    return (f'<div class="ch" role="img" aria-label="매출·영업이익 막대그래프" style="height:{H}px">'
            + ''.join(svg) + ''.join(labs) + '</div>')


# ── 옷 ───────────────────────────────────────────────────────────────────────
PAGE_CSS = '''
/* 히어로 */
.hero{padding:32px 0 36px}
.eyebrow{font:500 13px/20px var(--font);color:var(--ink-62);display:flex;gap:10px;align-items:center}
.eyebrow b{font-weight:500;color:var(--ink-72)}
h1.name{margin:10px 0 0;font:700 44px/52px var(--font);letter-spacing:-.025em}
.price{margin-top:22px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.price .p{font:600 40px/44px var(--font);letter-spacing:-.02em}
.price .c{font:600 17px/24px var(--font)}
.price .d{font:400 13px/20px var(--font);color:var(--ink-62)}
.actions{margin-top:26px;display:flex;gap:10px;align-items:center}
/* 관심종목 단추 — 더하기(추가) → 체크(추가됨). 목록 페이지의 +/✓ 와 같은 기호. 켜면 선 테두리 알약 */
.btn .wb-on{display:none} .btn.on .wb-add{display:none} .btn.on .wb-on{display:block;stroke-width:2.4}
.btn.on{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)} .btn.on:hover{box-shadow:inset 0 0 0 1px var(--ink)}
.tile figcaption{font:500 13px/20px var(--font);color:var(--ink-72);display:flex;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid var(--hair)}
.tile figcaption span{color:var(--ink-62);font-weight:400}
.ch{position:relative;margin-top:10px} .ch svg{position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible}
.ch-base{stroke:var(--line);stroke-width:1} .ch-rev{fill:var(--ink)} .ch-op{fill:var(--ink-30)}
.ch-val,.ch-lab{position:absolute;white-space:nowrap;font:500 12px/1 var(--font);color:var(--ink-62);font-variant-numeric:tabular-nums}
.ch-val{transform:translate(-50%,-100%)} .ch-val.dn,.ch-lab{transform:translateX(-50%)} .ch-val.l{transform:translateY(-100%)}
.lg{display:flex;align-items:center;gap:6px;font:400 12px/16px var(--font);color:var(--ink-62);margin-top:8px}
.lg i{width:10px;height:10px;border-radius:2px;display:inline-block;margin-left:10px} .lg i:first-child{margin-left:0} .l-rev{background:var(--ink)} .l-op{background:var(--ink-30)}
/* 지표 스트립 */
.stats{border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:22px 0;display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:16px}
.stats-note{margin:10px 0 0;font:400 12px/16px var(--font);color:var(--ink-62)}
.st-k{font:500 12px/16px var(--font);color:var(--ink-62)} .st-v{margin-top:6px;font:600 19px/24px var(--font);letter-spacing:-.01em;white-space:nowrap} .st-s{margin-top:4px;font:400 11px/14px var(--font);color:var(--ink-62)}
/* 본문 */
''' + C.TOC_CSS + '''
.sec-h.sec-h-quiet h2{font-size:13px;line-height:20px;font-weight:600;color:var(--ink-62);letter-spacing:0}
.prose p{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em} .prose p:last-child{margin-bottom:0}
.note{margin:16px 0 0;font:400 12px/18px var(--font);color:var(--ink-62)}
/* 초록(요약) — 상자 없이 제목·요지·핵심 목록 */
.abstract{padding:0}
.ab-title{margin:4px 0 0;font:700 30px/40px var(--font);letter-spacing:-.02em;text-wrap:balance}
.ab-lead{margin:20px 0 0;font:400 18px/30px var(--font);color:var(--ink-72)}
.kp{list-style:none;margin:26px 0 0;padding:22px 0 0;border-top:1px solid var(--hair);display:grid;gap:12px}
.kp li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;align-items:baseline} .kp .n{font:600 12px/24px var(--font);color:var(--ink-62)} .kp p{margin:0;font:400 15px/24px var(--font)}
/* 차트 타일 · 표 */
.tiles{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-bottom:32px}
.tile{margin:0;padding:0}
.tbl-wrap{margin-top:28px}
/* 밸류 스트립 */
.vstrip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:16px;padding:20px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);margin-bottom:28px}
/* 요인 — 줄로 나눈 목록 */
.fcs{border-top:1px solid var(--line)}
.fc{padding:22px 0 20px;border-bottom:1px solid var(--hair)}
.fc h4{margin:0 0 10px;font:600 16px/24px var(--font);letter-spacing:-.01em;display:flex;gap:10px;align-items:baseline}
.fc .dot{width:8px;height:8px;border-radius:50%;flex:none;position:relative;top:-2px} .fc.bull .dot{background:var(--up)} .fc.bear .dot{background:var(--down)}
.fc p{margin:0 0 12px;font:400 15px/24px var(--font);color:var(--ink-72)} .fc p:last-child{margin-bottom:0}
/* 리스크 */
.rks{border-top:1px solid var(--line)}
.rk{display:grid;grid-template-columns:180px minmax(0,1fr);gap:24px;padding:20px 0;border-bottom:1px solid var(--hair)}
.rk-c{font:600 14px/24px var(--font)} .rk-b p{margin:0 0 12px;font:400 15px/24px var(--font);color:var(--ink-72)} .rk-b p:last-child{margin:0}
/* 체크포인트 */
.cps{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}
.cps li{display:grid;grid-template-columns:120px minmax(0,1fr);gap:16px;align-items:start;padding:16px 0;border-bottom:1px solid var(--hair)}
.cps .when{font:500 13px/24px var(--font);color:var(--ink-62);white-space:nowrap}
.cps p{margin:0;font:400 15px/24px var(--font)}
.verdict p{font-size:17px}
/* 출처 */
.srcs{margin:0;padding:0 0 0 22px;display:grid;gap:8px} .srcs li{font:400 14px/20px var(--font);color:var(--ink-62)} .srcs a{color:var(--ink-72);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px} .srcs a:hover{color:var(--ink);text-decoration-color:var(--ink)}
.srcmore summary{margin-top:14px;font:500 13px/20px var(--font);color:var(--ink-62);cursor:pointer;list-style:none} .srcmore[open] summary{margin-bottom:8px}
.rdate{max-width:880px;margin:-40px 0 0;font:500 13px/20px var(--font);color:var(--ink-62)}
.disc{max-width:880px;margin:24px 0 0;padding:18px 0 0;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-62)}
/* 리포트가 아직 없는 종목 */
.pending{max-width:720px;padding:48px 0 24px} .pending h2{margin:0;font:700 24px/32px var(--font);letter-spacing:-.02em} .pending p{margin:14px 0 0;font:400 16px/27px var(--font);color:var(--ink-72)}
.pending .srcs{margin-top:28px}
/* 태블릿·휴대폰 */
@media (max-width:1100px){.stats{grid-template-columns:repeat(4,minmax(0,1fr));gap:20px 16px} .body{grid-template-columns:180px minmax(0,1fr);gap:40px} .vstrip{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:820px){
  .hero{padding:20px 0 26px}
  h1.name{font-size:32px;line-height:38px;margin-top:8px} .price{margin-top:16px} .price .p{font-size:32px;line-height:36px}
  .stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 12px;padding:18px 0} .st-v{font-size:17px}
  .ab-title{font-size:24px;line-height:32px} .ab-lead{font-size:16px;line-height:26px}
  .tiles{grid-template-columns:1fr} .vstrip{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px 10px;padding:16px 0}
  .rk{grid-template-columns:1fr;gap:6px;padding:16px 0} .cps li{grid-template-columns:1fr;gap:4px;padding:14px 0}
  .prose p{font-size:16px;line-height:27px}
  .pending{padding-top:28px} .pending h2{font-size:20px;line-height:28px}
}
''' + C.MOBILE_CSS + '\n' + C.TOC_MOBILE_CSS

PAGE_JS = ('/* 관심종목 단추 — 실사이트에서는 KOSWatch(Firestore)가 켜고 끈다. 여기서는 화면 안에서만 */\n'
           "(function(){var b=document.getElementById('watchBtn'),t=document.getElementById('watchTxt');if(!b)return;b.addEventListener('click',function(){var on=!b.classList.contains('on');b.classList.toggle('on',on);b.setAttribute('aria-pressed',on?'true':'false');t.textContent=on?'관심종목 추가됨':'관심종목 추가'})})();\n"
           + C.TOC_JS + '\n' + C.JS)


def asset_version(text):
    return hashlib.sha1(text.encode('utf-8')).hexdigest()[:8]


# ── 한 장 ────────────────────────────────────────────────────────────────────
def _stats(st, rep, tier, D):
    """지표 여덟. v2 는 리포트의 quant.valuation, 나머지는 valuation.js 로 리포트 목록 페이지와 같은 식."""
    price = st.get('price')
    if tier == 'v2':
        val = rep['quant']['valuation']
        per, pbr, eps, div, dps, window = val.get('per'), val.get('pbr'), val.get('eps'), val.get('div'), val.get('dps'), val.get('ttm_window')
    else:
        v = D['val'].get(st['ticker']) or {}
        eps, bps, dps = v.get('eps'), v.get('bps'), v.get('dps')
        per = round(price / eps, 1) if eps and eps > 0 and price else None
        pbr = round(price / bps, 2) if bps and bps > 0 and price else None
        div = round(dps / price * 100, 2) if dps is not None and price else None
        window = None
    def f(v, fmt):
        return '—' if v is None else fmt.format(v)
    stats = [('시가총액', f(st.get('mcap'), '{:,.1f}조원')), ('거래대금', (fwon(st.get('trading_value')) + '원') if st.get('trading_value') is not None else '—'),
             ('거래량', f(st.get('volume'), '{:,.0f}주') if (st.get('volume') or 0) < 1e4 else f((st.get('volume') or 0) / 1e4, '{:,.0f}만주')),
             ('상장주식수', f((st.get('shares') or 0) / 1e8 if st.get('shares') else None, '{:,.1f}억주')),
             ('PER', f(per, '{:.1f}배')), ('PBR', f(pbr, '{:.1f}배')), ('EPS', f(eps, '{:,.0f}원')), ('배당수익률', f(div, '{:.2f}%'))]
    html = ''.join(f'<div class="st"><div class="st-k">{esc(k)}</div><div class="st-v">{esc(v)}</div></div>' for k, v in stats)
    if tier == 'v2':
        note = f'PER·EPS·PBR·BPS 는 최근 4개 분기({esc(window)}) 기준 자체 산출 · 배당수익률은 주당 {dps:,.0f}원 기준' if dps is not None else f'PER·EPS·PBR·BPS 는 최근 4개 분기({esc(window)}) 기준 자체 산출'
    else:
        note = 'PER·PBR·배당수익률은 최근 확정 실적(EPS·BPS·주당배당금)과 현재 주가로 산출'
    return html, note


def _sources(rep):
    srcs = [s for s in (rep.get('sources') or []) if isinstance(s, str)] if rep else []
    def host(u):
        return re.sub(r'^www\.', '', re.sub(r'^https?://', '', u).split('/')[0])
    li = ''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(t)}</a></li>' for t, u in PRIMARY_SRC)
    more = ''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener nofollow">{esc(host(u))}</a></li>' for u in srcs)
    if srcs:
        return f'<ol class="srcs">{li}</ol><details class="srcmore"><summary>기사·자료 {len(srcs)}건 더 보기</summary><ol class="srcs">{more}</ol></details>'
    return f'<ol class="srcs">{li}</ol>'


def _sec(i, title, inner, wide=False, quiet=False):
    return f'<section class="sec{" wide" if wide else ""}" id="s{i:02d}"><div class="sec-h{" sec-h-quiet" if quiet else ""}"><span class="num">{i:02d}</span><h2>{esc(title)}</h2></div>{inner}</section>'


def _factors(items, kind):
    return ''.join(f'<article class="fc {kind}"><h4><i class="dot"></i>{esc(pk(b.get("title")))}</h4>' + paras(pk(b.get('body'))) + '</article>' for b in items or [])


def _body_v2(rep):
    q = rep['quant']
    val = q['valuation']
    annual = sorted(q.get('annual') or [], key=lambda a: a['year'])
    quarterly = q.get('quarterly') or []
    q_chart = bar_chart([(x['q'][2:4] + 'Q' + x['q'][-1], x.get('rev'), x.get('op')) for x in quarterly])
    a_chart = bar_chart([(str(a['year']), a.get('rev'), a.get('op')) for a in annual])
    ann_rows = ''.join(f'<tr><th scope="row">{a["year"]}</th><td>{fjo(a.get("rev"))}</td><td>{fjo(a.get("op"))}</td><td>{fjo(a.get("np_owner"))}</td><td>{pct(a.get("opm"))}</td><td>{pct(a.get("roe"))}</td><td>{pct(a.get("debt_ratio"))}</td></tr>' for a in annual)
    qtr_rows = ''.join(f'<tr><th scope="row">{esc(x["q"])}</th><td>{fjo(x.get("rev"))}</td><td>{fjo(x.get("op"))}</td><td>{pct(x["op"] / x["rev"] * 100) if x.get("rev") and x.get("op") is not None else "—"}</td></tr>' for x in quarterly)
    risk_rows = ''.join(f'<div class="rk"><div class="rk-c">{esc(pk(r.get("cat")))}</div><div class="rk-b">{paras(pk(r.get("body")))}</div></div>' for r in rep.get('risks') or [])
    cp_rows = ''.join(f'<li><span class="when">{esc(pk(c.get("when")))}</span><p>{esc(pk(c.get("what")))}</p></li>' for c in rep.get('checkpoints') or [])
    kp = ''.join(f'<li><span class="n">{i + 1}</span><p>{esc(pk(k))}</p></li>' for i, k in enumerate(rep.get('keypoints') or []))
    def v(key, fmt):
        x = val.get(key)
        return '—' if x is None else fmt.format(x)
    secs = [
        f'''<section class="sec" id="s01"><div class="sec-h sec-h-quiet"><span class="num">01</span><h2>리포트 개요</h2></div>
        <div class="abstract"><h3 class="ab-title">{esc(pk(rep.get("title")))}</h3><p class="ab-lead">{esc(pk(rep.get("lead")))}</p><ol class="kp">{kp}</ol></div></section>''',
        _sec(2, '사업 구조', f'<div class="prose">{paras(pk(rep.get("business")))}</div>'),
        _sec(3, '실적 추이', f'''<div class="tiles"><figure class="tile"><figcaption>분기 매출 · 영업이익 <span>단위: 조원</span></figcaption>{q_chart}<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div></figure>
        <figure class="tile"><figcaption>연간 매출 · 영업이익 <span>단위: 조원</span></figcaption>{a_chart}<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div></figure></div>
        <div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>분기 실적 · 최근 {len(quarterly)}분기</span><span class="u">단위: 조원</span></div></caption><thead><tr><th>분기</th><th>매출액</th><th>영업이익</th><th>영업이익률</th></tr></thead><tbody>{qtr_rows}</tbody></table></div>
        <div class="tbl-wrap"><table class="tbl"><caption><div class="cap"><span>연간 실적</span><span class="u">단위: 조원</span></div></caption><thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>지배주주 순이익</th><th>영업이익률</th><th>ROE</th><th>부채비율</th></tr></thead><tbody>{ann_rows}</tbody></table></div>
        <p class="note">연결 기준(자회사 실적을 합친 재무제표) · DART 공시 확정치 · 순이익은 지배주주 기준 · 데이터 {esc(q.get("asOf"))}</p>''', wide=True),
        _sec(4, '실적 분석', f'<div class="prose">{paras(pk(rep.get("earnings")))}</div>'),
        _sec(5, '산업 분석', f'<div class="prose">{paras(pk(rep.get("industry")))}</div>'),
        _sec(6, '전망', f'<div class="prose">{paras(pk(rep.get("outlook")))}</div>'),
        _sec(7, '밸류에이션', f'''<div class="vstrip"><div class="st"><div class="st-k">PER</div><div class="st-v">{v("per", "{:.1f}배")}</div></div><div class="st"><div class="st-k">PBR</div><div class="st-v">{v("pbr", "{:.1f}배")}</div></div><div class="st"><div class="st-k">ROE</div><div class="st-v">{v("roe_ttm", "{:.1f}%")}</div></div><div class="st"><div class="st-k">EPS</div><div class="st-v">{v("eps", "{:,.0f}원")}</div></div><div class="st"><div class="st-k">BPS</div><div class="st-v">{v("bps", "{:,.0f}원")}</div></div><div class="st"><div class="st-k">주당배당금</div><div class="st-v">{v("dps", "{:,.0f}원")}</div></div></div>
        <div class="prose">{paras(pk(rep.get("valuation_comment")))}</div><p class="note">{esc(val.get("basis"))} · 기준 {esc(q.get("asOf"))}</p>''', wide=True),
        _sec(8, '강세 요인', f'<div class="fcs">{_factors(rep.get("bull"), "bull")}</div>'),
        _sec(9, '약세 요인', f'<div class="fcs">{_factors(rep.get("bear"), "bear")}</div>'),
        _sec(10, '리스크 요인', f'<div class="rks">{risk_rows}</div>', wide=True),
        _sec(11, '다음 체크포인트', f'<ol class="cps">{cp_rows}</ol>'),
        _sec(12, '종합 의견', f'<div class="prose verdict">{paras(pk((rep.get("verdict") or {}).get("body")))}</div>'),
        _sec(13, '참고 출처', _sources(rep)),
    ]
    return SECTIONS_V2, ''.join(secs)


def _body_v1(rep):
    """옛 형식 — 재무 수치·체크포인트가 없다. 있는 절만 그린다."""
    kp = ''.join(f'<li><span class="n">{i + 1}</span><p>{esc(pk(k))}</p></li>' for i, k in enumerate(rep.get('keypoints') or []))
    risk_rows = ''.join(f'<div class="rk"><div class="rk-c">{esc(pk(r.get("cat")))}</div><div class="rk-b">{paras(pk(r.get("body")))}</div></div>' for r in rep.get('risks') or [])
    items = [('리포트 개요', f'<div class="abstract"><h3 class="ab-title">{esc(pk(rep.get("title")))}</h3><p class="ab-lead">{esc(pk(rep.get("lead")))}</p><ol class="kp">{kp}</ol></div>', False, True),
             ('사업 구조', f'<div class="prose">{paras(pk(rep.get("business")) or pk(rep.get("desc")))}</div>', False, False)]
    if pk(rep.get('recent')):
        items.append(('최근 동향', f'<div class="prose">{paras(pk(rep.get("recent")))}</div>', False, False))
    items += [('전망', f'<div class="prose">{paras(pk(rep.get("outlook")))}</div>', False, False),
              ('강세 요인', f'<div class="fcs">{_factors(rep.get("bull"), "bull")}</div>', False, False),
              ('약세 요인', f'<div class="fcs">{_factors(rep.get("bear"), "bear")}</div>', False, False),
              ('리스크 요인', f'<div class="rks">{risk_rows}</div>', True, False),
              ('종합 의견', f'<div class="prose verdict">{paras(pk((rep.get("verdict") or {}).get("body")))}</div>', False, False),
              ('참고 출처', _sources(rep), False, False)]
    titles = [t for t, _, _, _ in items]
    return titles, ''.join(_sec(i + 1, t, inner, wide, quiet) for i, (t, inner, wide, quiet) in enumerate(items))


def render(tk, D, inline=True, assets=None, index=False, base=SITE, dir_path='stock', preview=False):
    """한 장. inline=True 면 CSS·JS 를 안에 넣고(시안), 아니면 assets={'css':href,'js':href} 를 잇는다."""
    st = D['stocks'].get(tk)
    rep, tier = load_report(tk, D)
    if st is None:
        if rep is None:
            raise KeyError(tk)
        st = {'ticker': tk, 'name': rep.get('name', tk), 'name_en': rep.get('name_en', ''), 'market': rep.get('market', ''), 'sector': rep.get('sector', ''), 'price': None, 'change': 0}
    name = st.get('name') or (rep or {}).get('name') or tk
    market = st.get('market') or (rep or {}).get('market') or ''
    sector = st.get('sector') or (rep or {}).get('sector') or ''
    price, chg = st.get('price'), st.get('change') or 0
    chg_cls = 'up' if chg > 0 else ('down' if chg < 0 else 'flat')
    arrow = '▲' if chg > 0 else ('▼' if chg < 0 else '')
    price_date = fdate(D['dataDate'])
    price_html = (f'<span class="p">{price:,.0f}원</span><span class="c {chg_cls}">{arrow} {pct(abs(chg), True).lstrip("+")}</span><span class="d">{price_date} 장마감</span>'
                  if price is not None else '<span class="d">시세 없음</span>')
    stat_html, stat_note = _stats(st, rep, tier, D)

    if tier == 'v2':
        titles, body = _body_v2(rep)
    elif tier == 'v1':
        titles, body = _body_v1(rep)
    else:
        titles, body = [], ''
    toc = ''.join(f'<a href="#s{i + 1:02d}"><span class="n">{i + 1:02d}</span>{esc(t)}</a>' for i, t in enumerate(titles))
    chips = ''.join(f'<a href="#s{i + 1:02d}">{i + 1:02d} {esc(t)}</a>' for i, t in enumerate(titles))

    if rep:
        head_title = f'{name}({tk}) 리포트 — {pk(rep.get("title"))} | KOSAI' if pk(rep.get('title')) else f'{name}({tk}) 리포트 | KOSAI'
        desc = re.sub(r'\s+', ' ', pk(rep.get('lead')) or pk(rep.get('desc')))[:158]
        rdate = f'<p class="rdate">리포트 작성 {esc(rep.get("reportDate"))} · 데이터 기준 {fdate(rep.get("dataDate"))}</p>'
        main_body = f'''<div class="body">
    <aside class="toc" id="toc">{toc}</aside>
    <div class="content">
      <div class="chips-mark" id="chipsMark"></div><div class="chips-bar" id="chipsBar"><nav class="chips" id="chips">{chips}</nav></div>
      {body}
      {rdate}
      <p class="disc">{DISC}</p>
    </div>
  </div>'''
    else:
        head_title = f'{name}({tk}) 종목 — 리포트 준비 중 | KOSAI'
        desc = f'{name}({tk}) 시세·시가총액·PER·PBR. AI 분석 리포트는 첫 정기보고서가 공시된 뒤 작성됩니다.'
        main_body = f'''<div class="pending"><h2>이 종목의 리포트는 준비 중입니다</h2>
    <p>새로 상장된 종목은 첫 사업·분기보고서가 공시된 뒤에 리포트를 작성합니다. 시세·시가총액·PER·PBR 같은 지표는 매 거래일 저녁에 갱신됩니다.</p>
    <ol class="srcs">{''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(t)}</a></li>' for t, u in PRIMARY_SRC)}</ol>
    <p class="disc">{DISC}</p></div>'''

    url = f'{base}/{dir_path}/{tk}.html'
    ld = {'@context': 'https://schema.org', '@type': 'Article',
          'headline': f'{name} ({tk}) — {pk(rep.get("title"))}' if rep and pk(rep.get('title')) else f'{name} ({tk})',
          'datePublished': (rep or {}).get('reportDate') or fdate(D['dataDate']), 'dateModified': fdate(D['dataDate']),
          'inLanguage': 'ko', 'isAccessibleForFree': True, 'mainEntityOfPage': url,
          'author': {'@type': 'Organization', 'name': 'KOSAI', 'url': base},
          'about': {'@type': 'Corporation', 'name': name, 'legalName': st.get('name_en') or name, 'tickerSymbol': tk}}
    extra = (f'<meta name="description" content="{esc(desc)}">\n<link rel="canonical" href="{url}">\n'
             f'<meta property="og:title" content="{esc(head_title)}">\n<meta property="og:description" content="{esc(desc)}">\n<meta property="og:url" content="{url}">\n<meta property="og:type" content="article">\n'
             f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n')
    if inline:
        extra += '<style>\n' + C.CSS + '\n' + PAGE_CSS + '\n</style>\n'
    else:
        extra += f'<link rel="stylesheet" href="{assets["css"]}">\n'
    head = C.head(esc(head_title), robots=('index,follow' if index else 'noindex,nofollow'), extra=extra)
    script = ('<script>\n' + PAGE_JS + '\n</script>') if inline else f'<script src="{assets["js"]}" defer></script>'
    return f'''{head}
</head>
<body>
{C.nav('리포트')}
<main class="wrap">
  <header class="hero">
    <div>
      <div class="eyebrow"><b>{esc(market)}</b><span>{esc(sector)}</span><span>{tk}</span></div>
      <h1 class="name">{esc(name)}</h1>
      <div class="price">{price_html}</div>
      <div class="actions"><button type="button" class="btn btn-ink ico" id="watchBtn" aria-pressed="false"><svg class="wb-add" viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg><svg class="wb-on" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg><span id="watchTxt">관심종목 추가</span></button></div>
    </div>
  </header>
  <section class="stats" aria-label="핵심 지표">{stat_html}</section>
  <p class="stats-note">{stat_note} · 시세 {price_date} 장마감</p>
  {main_body}
</main>
{C.FOOTER}
{script}
</body>
</html>''', tier
