#!/usr/bin/env python3
"""종목 리포트 페이지 — 새 디자인 시안(comp)을 실제 데이터로 통째로 만든다.

    python3 scripts/build_stock_comp.py 005930 [출력 경로]    # 기본 preview/stock.html

2026-09-25 사장: 덧칠(글꼴·선만 바꾼 것)은 리디자인이 아니다. 레이아웃·위치를 다 바꿔도 되니 애플·Fey 급으로.
그래서 기존 stock.html 위에 CSS 를 얹지 않고, 리포트 JSON(data/reports_v2)·시세(data/stocks.js)로 페이지를
처음부터 그린다. 기능(관심종목·로그인·한/영)은 여기서는 그림만이다 — 시안이 통과하면 stock.html 에 옮긴다.

뼈대는 그대로: 13개 절의 이름·순서, 170자 문단 나누기(chunk), 숫자 표기(조/억 · 소수 자리), 면책 한 줄.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARA_KO = 170
SECTIONS = ['리포트 개요', '사업 구조', '실적 추이', '실적 분석', '산업 분석', '전망', '밸류에이션',
            '강세 요인', '약세 요인', '리스크 요인', '다음 체크포인트', '종합 의견', '참고 출처']


def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


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


def paras(text, cls='p'):
    return ''.join(f'<p>{esc(p)}</p>' for p in chunk(text))


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
    return f'{v / 1e12:,.1f}'


def pct(v, signed=False):
    if v is None:
        return '—'
    s = f'{v:+.2f}%' if signed else f'{v:.1f}%'
    return s.replace('-', '−')


def load_stock(tk):
    s = (ROOT / 'data/stocks.js').read_text(encoding='utf-8')
    i = s.find(f'"{tk}"')
    j = s.find('}', i)
    blob = '{' + s[i:j + 1].split('{', 1)[1] if '{' in s[i:j] else None
    m = re.search(r'"ticker":\s*"' + tk + r'"[^{}]*?\}', s)
    # 안전한 방법: ticker 가 든 객체를 앞뒤 중괄호로 찾는다
    k = s.rfind('{', 0, i)
    j = s.find('}', i)
    return json.loads(s[k:j + 1])


def bar_chart(groups, w=520, h=200, pad_l=8, pad_r=8, top=28, bottom=28, ink='var(--ink)', dim='var(--ink-30)'):
    """groups: [(label, rev, op)] → 두 막대(매출 먹색 · 영업이익 옅은 먹색) + 값 라벨. SVG 문자열."""
    n = len(groups)
    mx = max(max(g[1], g[2] or 0) for g in groups) or 1
    gw = (w - pad_l - pad_r) / n
    bw = min(22, gw * 0.24)
    gap = 6
    plot_h = h - top - bottom
    out = [f'<svg class="ch" viewBox="0 0 {w} {h}" role="img" aria-label="매출·영업이익 막대그래프">']
    out.append(f'<line x1="{pad_l}" y1="{top + plot_h}" x2="{w - pad_r}" y2="{top + plot_h}" class="ch-base"/>')
    for i, (label, rev, op) in enumerate(groups):
        cx = pad_l + gw * i + gw / 2
        for j, (val, cls) in enumerate([(rev, 'ch-rev'), (op, 'ch-op')]):
            if val is None:
                continue
            bh = max(2, plot_h * val / mx)
            x = cx - bw - gap / 2 if j == 0 else cx + gap / 2
            y = top + plot_h - bh
            out.append(f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2"/>')
            out.append(f'<text class="ch-val" x="{x + bw / 2:.1f}" y="{y - 6:.1f}" text-anchor="middle">{fjo(val)}</text>')
        out.append(f'<text class="ch-lab" x="{cx:.1f}" y="{h - 8}" text-anchor="middle">{esc(label)}</text>')
    out.append('</svg>')
    return ''.join(out)


def build(tk, out_path):
    rep = json.load(open(ROOT / f'data/reports_v2/{tk}.json', encoding='utf-8'))
    st = load_stock(tk)
    q = rep['quant']
    val = q['valuation']
    name = rep['name']
    price = st['price']
    chg = st['change']
    up = chg > 0
    chg_cls = 'up' if up else ('down' if chg < 0 else 'flat')
    arrow = '▲' if up else ('▼' if chg < 0 else '')
    annual = sorted(q['annual'], key=lambda a: a['year'])
    quarterly = q['quarterly']
    data_date = rep['dataDate']
    data_date_f = f'{data_date[:4]}-{data_date[4:6]}-{data_date[6:]}'
    price_date = '2026-09-23'  # stocks.js 에 장마감 날짜가 없다 — 시안에서는 고정(실제 구현은 stock.html 의 asOf 를 쓴다)

    # ── 히어로 차트: 분기 매출·영업이익 (최근 5분기)
    qgroups = [(x['q'].replace('20', "'", 1).replace('Q', 'Q'), x['rev'], x['op']) for x in quarterly]
    qgroups = [(x['q'][2:4] + 'Q' + x['q'][-1], x['rev'], x['op']) for x in quarterly]
    q_chart = bar_chart(qgroups, w=520, h=220)
    agroups = [(str(a['year']), a['rev'], a['op']) for a in annual]
    annual_chart = bar_chart(agroups, w=520, h=220)

    # ── 지표 스트립
    stats = [
        ('시가총액', f'{st["mcap"]:,.1f}조원', None),
        ('거래대금', fwon(st['trading_value']) + '원', None),
        ('거래량', f'{st["volume"] / 1e4:,.0f}만주', None),
        ('상장주식수', f'{st["shares"] / 1e8:,.1f}억주', None),
        ('PER', f'{val["per"]:.1f}배', None),
        ('PBR', f'{val["pbr"]:.1f}배', None),
        ('EPS', f'{val["eps"]:,.0f}원', None),
        ('배당수익률', f'{val["div"]:.2f}%', None),
    ]
    stat_html = ''.join(
        f'<div class="st"><div class="st-k">{esc(k)}</div><div class="st-v">{esc(v)}</div>' + (f'<div class="st-s">{esc(s)}</div>' if s else '') + '</div>'
        for k, v, s in stats)

    # ── 표: 연간
    def row(cells, cls=''):
        return f'<tr class="{cls}">' + ''.join(cells) + '</tr>'
    ann_rows = ''.join(row([
        f'<th scope="row">{a["year"]}</th>', f'<td>{fjo(a["rev"])}</td>', f'<td>{fjo(a["op"])}</td>',
        f'<td>{fjo(a["np_owner"])}</td>', f'<td>{pct(a["opm"])}</td>', f'<td>{pct(a["roe"])}</td>', f'<td>{pct(a["debt_ratio"])}</td>'
    ]) for a in annual)
    qtr_rows = ''.join(row([
        f'<th scope="row">{x["q"]}</th>', f'<td>{fjo(x["rev"])}</td>', f'<td>{fjo(x["op"])}</td>',
        f'<td>{pct(x["op"] / x["rev"] * 100)}</td>'
    ]) for x in quarterly)

    # ── 요인·리스크·체크포인트·출처
    def factor_cards(items, kind):
        return ''.join(
            f'<article class="fc {kind}"><h4><i class="dot"></i>{esc(b["title"]["ko"])}</h4>' + ''.join(f'<p>{esc(p)}</p>' for p in chunk(b['body']['ko'])) + '</article>'
            for b in items)
    risk_rows = ''.join(
        f'<div class="rk"><div class="rk-c">{esc(r["cat"]["ko"])}</div><div class="rk-b">' + ''.join(f'<p>{esc(p)}</p>' for p in chunk(r['body']['ko'])) + '</div></div>'
        for r in rep['risks'])
    cp_rows = ''.join(
        f'<li><span class="when">{esc(c["when"]["ko"])}</span><p>{esc(c["what"]["ko"])}</p></li>' for c in rep['checkpoints'])

    def host(u):
        return re.sub(r'^www\.', '', re.sub(r'^https?://', '', u).split('/')[0])
    srcs = rep['sources']
    src_li = ''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(host(u))}</a></li>' for u in srcs[:6])
    src_more = ''.join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(host(u))}</a></li>' for u in srcs[6:])
    kp_li = ''.join(f'<li><span class="n">{i + 1}</span><p>{esc(k["ko"])}</p></li>' for i, k in enumerate(rep['keypoints']))
    toc = ''.join(f'<a href="#s{i + 1:02d}"><span class="n">{i + 1:02d}</span>{esc(t)}</a>' for i, t in enumerate(SECTIONS))
    chips = ''.join(f'<a href="#s{i + 1:02d}">{i + 1:02d} {esc(t)}</a>' for i, t in enumerate(SECTIONS))

    def sec(i, title, inner, wide=False):
        return f'<section class="sec{" wide" if wide else ""}" id="s{i:02d}"><div class="sec-h"><span class="num">{i:02d}</span><h2>{esc(title)}</h2></div>{inner}</section>'

    body = ''.join([
        # 01 개요 — 초록(abstract) 카드
        f'''<section class="sec" id="s01"><div class="sec-h sec-h-quiet"><span class="num">01</span><h2>리포트 개요</h2></div>
        <div class="abstract"><h3 class="ab-title">{esc(rep["title"]["ko"])}</h3><div class="ab-meta">AI 작성 · 리포트 {esc(rep["reportDate"])} · 데이터 {data_date_f}</div>
        <p class="ab-lead">{esc(rep["lead"]["ko"])}</p>
        <ol class="kp">{kp_li}</ol></div></section>''',
        sec(2, '사업 구조', f'<div class="prose">{paras(rep["business"]["ko"])}</div>'),
        sec(3, '실적 추이', f'''<div class="tiles"><figure class="tile"><figcaption>분기 매출 · 영업이익 <span>조원</span></figcaption>{q_chart}<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div></figure>
        <figure class="tile"><figcaption>연간 매출 · 영업이익 <span>조원 · 연결</span></figcaption>{annual_chart}<div class="lg"><i class="l-rev"></i>매출액<i class="l-op"></i>영업이익</div></figure></div>
        <div class="tbl-wrap"><table class="tbl"><caption>연간 실적 · 연결 · 조원</caption><thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>지배주주 순이익</th><th>영업이익률</th><th>ROE</th><th>부채비율</th></tr></thead><tbody>{ann_rows}</tbody></table></div>
        <div class="tbl-wrap"><table class="tbl narrow"><caption>분기 실적 · 최근 5분기 · 조원</caption><thead><tr><th>분기</th><th>매출액</th><th>영업이익</th><th>영업이익률</th></tr></thead><tbody>{qtr_rows}</tbody></table></div>
        <p class="note">{esc(q["fs_basis"])} · 기준 {esc(q["asOf"])}</p>''', wide=True),
        sec(4, '실적 분석', f'<div class="prose">{paras(rep["earnings"]["ko"])}</div>'),
        sec(5, '산업 분석', f'<div class="prose">{paras(rep["industry"]["ko"])}</div>'),
        sec(6, '전망', f'<div class="prose">{paras(rep["outlook"]["ko"])}</div>'),
        sec(7, '밸류에이션', f'''<div class="vstrip"><div class="st"><div class="st-k">PER</div><div class="st-v">{val["per"]:.1f}배</div></div><div class="st"><div class="st-k">PBR</div><div class="st-v">{val["pbr"]:.1f}배</div></div><div class="st"><div class="st-k">ROE</div><div class="st-v">{val["roe_ttm"]:.1f}%</div></div><div class="st"><div class="st-k">EPS</div><div class="st-v">{val["eps"]:,.0f}원</div></div><div class="st"><div class="st-k">BPS</div><div class="st-v">{val["bps"]:,.0f}원</div></div><div class="st"><div class="st-k">주당배당금</div><div class="st-v">{val["dps"]:,.0f}원</div></div></div>
        <div class="prose">{paras(rep["valuation_comment"]["ko"])}</div><p class="note">{esc(val["basis"])} · 기준 {esc(q["asOf"])}</p>''', wide=True),
        sec(8, '강세 요인', f'<div class="fcs">{factor_cards(rep["bull"], "bull")}</div>'),
        sec(9, '약세 요인', f'<div class="fcs">{factor_cards(rep["bear"], "bear")}</div>'),
        sec(10, '리스크 요인', f'<div class="rks">{risk_rows}</div>', wide=True),
        sec(11, '다음 체크포인트', f'<ol class="cps">{cp_rows}</ol>'),
        sec(12, '종합 의견', f'<div class="prose verdict">{paras(rep["verdict"]["body"]["ko"])}</div>'),
        sec(13, '참고 출처', f'<ol class="srcs">{src_li}</ol><details class="srcmore"><summary>출처 {len(srcs) - 6}건 더 보기</summary><ol class="srcs" start="7">{src_more}</ol></details>'),
    ])

    html = f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex,nofollow">
<meta name="theme-color" content="#f9f8f6">
<title>{esc(name)}({tk}) 리포트 — 디자인 시안 | KOSAI</title>
<link rel="icon" href="/assets/favicon.png?v=k2">
<script>(function(){{var t='light';try{{t=localStorage.getItem('kos-theme')||'light'}}catch(e){{}}document.documentElement.setAttribute('data-theme',t);}})();</script>
<style>
@font-face{{font-family:"Pretendard";font-weight:400;font-display:swap;src:url("/fonts/Pretendard-Regular.woff2") format("woff2")}}
@font-face{{font-family:"Pretendard";font-weight:500;font-display:swap;src:url("/fonts/Pretendard-Medium.woff2") format("woff2")}}
@font-face{{font-family:"Pretendard";font-weight:600;font-display:swap;src:url("/fonts/Pretendard-SemiBold.woff2") format("woff2")}}
@font-face{{font-family:"Pretendard";font-weight:700;font-display:swap;src:url("/fonts/Pretendard-Bold.woff2") format("woff2")}}
:root{{
  --bg:#f9f8f6; --surface:#ffffff; --surface-2:#f1efeb;
  --ink:#141414; --ink-72:rgba(20,20,20,.72); --ink-55:rgba(20,20,20,.55); --ink-30:rgba(20,20,20,.30);
  --hair:rgba(20,20,20,.08); --line:rgba(20,20,20,.14);
  --up:#c8102e; --down:#1e5fbf; --up-bg:rgba(200,16,46,.08); --down-bg:rgba(30,95,191,.08);
  --font:"Pretendard",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --wrap:1120px; --pad:32px; --nav-bar:rgba(249,248,246,.72);
  color-scheme:light;
}}
:root[data-theme="dark"]{{
  --bg:#0d0d0e; --surface:#161617; --surface-2:#1e1e20;
  --ink:#ececea; --ink-72:rgba(236,236,234,.72); --ink-55:rgba(236,236,234,.55); --ink-30:rgba(236,236,234,.30);
  --hair:rgba(255,255,255,.08); --line:rgba(255,255,255,.14);
  --up:#f0655f; --down:#6f9cf5; --up-bg:rgba(240,101,95,.12); --down-bg:rgba(111,156,245,.12);
  --nav-bar:rgba(13,13,14,.72);
  color-scheme:dark;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth;scroll-padding-top:84px}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:var(--font);-webkit-font-smoothing:antialiased;font-variant-numeric:tabular-nums lining-nums;word-break:keep-all;overflow-wrap:anywhere}}
a{{color:inherit;text-decoration:none}}
::selection{{background:rgba(20,20,20,.14)}} :root[data-theme="dark"] ::selection{{background:rgba(255,255,255,.22)}}
.wrap{{max-width:var(--wrap);margin:0 auto;padding:0 var(--pad)}}
/* 헤더 — 사이트 규칙 그대로(60px · 맨 위 투명 · 내리면 띠) */
.nav{{position:sticky;top:0;z-index:50;height:60px;display:flex;align-items:center;justify-content:space-between;padding:0 var(--pad);transition:background-color .2s,box-shadow .2s}}
.nav.scrolled{{background:var(--nav-bar);box-shadow:0 1px 0 var(--hair);-webkit-backdrop-filter:blur(16px);backdrop-filter:blur(16px)}}
.nav-in{{width:100%;max-width:var(--wrap);margin:0 auto;display:flex;align-items:center;justify-content:space-between;position:relative}}
.brand img{{height:14px;display:block}} .brand .dk{{display:none}} :root[data-theme="dark"] .brand .lt{{display:none}} :root[data-theme="dark"] .brand .dk{{display:block}}
.links{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;gap:28px}}
.links a{{font:500 14px/1 var(--font);color:var(--ink-72);transition:color .12s}} .links a:hover,.links a.on{{color:var(--ink)}} .links a.on{{font-weight:600}}
.right{{display:flex;align-items:center;gap:6px}} .login{{font:600 13px/1 var(--font);color:var(--ink-72);padding:8px 10px}} .login:hover{{color:var(--ink)}}
.ib{{width:38px;height:38px;border:0;background:transparent;color:var(--ink-72);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;border-radius:10px}} .ib:hover{{color:var(--ink)}} .ib svg{{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}}
.menu{{display:none}}
@media (max-width:820px){{.links,.login{{display:none}} .menu{{display:inline-flex}}}}
/* 히어로 */
.hero{{padding:32px 0 36px}}
.eyebrow{{font:500 13px/20px var(--font);color:var(--ink-55);display:flex;gap:10px;align-items:center}}
.eyebrow b{{font-weight:500;color:var(--ink-72)}}
h1.name{{margin:10px 0 0;font:700 44px/52px var(--font);letter-spacing:-.025em}}
.price{{margin-top:22px;display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}}
.price .p{{font:600 40px/44px var(--font);letter-spacing:-.02em}}
.price .c{{font:600 17px/24px var(--font)}} .up{{color:var(--up)}} .down{{color:var(--down)}} .flat{{color:var(--ink-55)}}
.price .d{{font:400 13px/20px var(--font);color:var(--ink-55)}}
.actions{{margin-top:26px;display:flex;gap:10px;align-items:center}}
.btn{{display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 18px 0 14px;border-radius:999px;border:0;font:600 14px/1 var(--font);cursor:pointer;transition:background-color .12s,color .12s}}
.btn svg{{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round}}
.btn-ink{{background:var(--ink);color:var(--bg)}} .btn-ink:hover{{opacity:.9}}
.btn-soft{{background:var(--surface-2);color:var(--ink)}} .btn-soft:hover{{background:var(--line)}}
.tile figcaption{{font:500 13px/20px var(--font);color:var(--ink-72);display:flex;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid var(--hair)}}
.tile figcaption span{{color:var(--ink-55);font-weight:400}}
.ch{{width:100%;height:auto;display:block;margin-top:10px}}
.ch-base{{stroke:var(--line);stroke-width:1}} .ch-rev{{fill:var(--ink)}} .ch-op{{fill:var(--ink-30)}}
.ch-val{{font:500 13px var(--font);fill:var(--ink-55)}} .ch-lab{{font:500 13px var(--font);fill:var(--ink-55)}}
.lg{{display:flex;align-items:center;gap:6px;font:400 12px/16px var(--font);color:var(--ink-55);margin-top:8px}}
.lg i{{width:10px;height:10px;border-radius:2px;display:inline-block;margin-left:10px}} .lg i:first-child{{margin-left:0}} .l-rev{{background:var(--ink)}} .l-op{{background:var(--ink-30)}}
/* 지표 스트립 */
.stats{{border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);padding:22px 0;display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:16px}}
.stats-note{{margin:10px 0 0;font:400 12px/16px var(--font);color:var(--ink-55)}}
.st-k{{font:500 12px/16px var(--font);color:var(--ink-55)}} .st-v{{margin-top:6px;font:600 19px/24px var(--font);letter-spacing:-.01em;white-space:nowrap}} .st-s{{margin-top:4px;font:400 11px/14px var(--font);color:var(--ink-55)}}
/* 본문 */
.body{{display:grid;grid-template-columns:200px minmax(0,1fr);gap:64px;padding:56px 0 0}}
.toc{{position:sticky;top:84px;align-self:start;display:flex;flex-direction:column;gap:2px}}
.toc a{{display:flex;gap:10px;align-items:baseline;padding:7px 0 7px 12px;border-left:2px solid transparent;font:500 13px/18px var(--font);color:var(--ink-55);transition:color .12s}}
.toc a .n{{font-weight:500;font-size:11px;color:var(--ink-30);min-width:18px}}
.toc a:hover{{color:var(--ink)}} .toc a.on{{color:var(--ink);border-left-color:var(--ink);font-weight:600}} .toc a.on .n{{color:var(--ink-55)}}
.chips{{display:none}}
.content{{min-width:0}}
.sec{{max-width:720px;padding:0 0 88px}} .sec.wide{{max-width:880px}}
.sec-h{{display:flex;align-items:baseline;gap:14px;margin:0 0 22px}}
.sec-h .num{{font:600 13px/20px var(--font);color:var(--ink-30)}} .sec-h-quiet h2{{font-size:13px;line-height:20px;font-weight:600;color:var(--ink-55);letter-spacing:0}}
.sec-h h2{{margin:0;font:700 24px/32px var(--font);letter-spacing:-.02em}}
.prose p{{margin:0 0 20px;font:400 17px/28px var(--font);letter-spacing:-.005em}} .prose p:last-child{{margin-bottom:0}}
.note{{margin:16px 0 0;font:400 12px/18px var(--font);color:var(--ink-55)}}
/* 초록(요약) — 상자 없이 제목·바이라인·요지·핵심 목록 */
.abstract{{padding:0}}
.ab-title{{margin:4px 0 0;font:700 30px/40px var(--font);letter-spacing:-.02em;text-wrap:balance}}
.ab-meta{{margin-top:12px;font:500 12px/16px var(--font);color:var(--ink-55)}}
.ab-lead{{margin:20px 0 0;font:400 18px/30px var(--font);color:var(--ink-72)}}
.kp{{list-style:none;margin:26px 0 0;padding:22px 0 0;border-top:1px solid var(--hair);display:grid;gap:12px}}
.kp li{{display:grid;grid-template-columns:22px minmax(0,1fr);gap:10px;align-items:baseline}} .kp .n{{font:600 12px/24px var(--font);color:var(--ink-30)}} .kp p{{margin:0;font:400 15px/24px var(--font)}}
/* 차트 타일 · 표 */
.tiles{{display:grid;grid-template-columns:1fr 1fr;gap:40px;margin-bottom:32px}}
.tile{{margin:0;padding:0}}
.tbl-wrap{{overflow-x:auto;margin-top:28px}}
.tbl{{width:100%;border-collapse:collapse}} .tbl.narrow{{max-width:560px}}
.tbl caption{{text-align:left;font:500 13px/20px var(--font);color:var(--ink-72);padding:0 0 10px}}
.tbl th,.tbl td{{padding:11px 12px;font:400 14px/20px var(--font);text-align:right;white-space:nowrap;border-top:1px solid var(--hair)}}
.tbl thead th{{font:500 12px/16px var(--font);color:var(--ink-55);border-top:0;border-bottom:1px solid var(--line);padding-top:0}}
.tbl th:first-child,.tbl td:first-child{{text-align:left;padding-left:0;font-weight:500}} .tbl th:last-child,.tbl td:last-child{{padding-right:0}}
.tbl tbody th{{font-weight:500}}
/* 밸류 스트립 */
.vstrip{{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:16px;padding:20px 0;border-top:1px solid var(--hair);border-bottom:1px solid var(--hair);margin-bottom:28px}}
/* 요인 — 줄로 나눈 목록 */
.fcs{{border-top:1px solid var(--line)}}
.fc{{padding:22px 0 20px;border-bottom:1px solid var(--hair)}}
.fc h4{{margin:0 0 10px;font:600 16px/24px var(--font);letter-spacing:-.01em;display:flex;gap:10px;align-items:baseline}}
.fc .dot{{width:8px;height:8px;border-radius:50%;flex:none;position:relative;top:-2px}} .fc.bull .dot{{background:var(--up)}} .fc.bear .dot{{background:var(--down)}}
.fc p{{margin:0 0 12px;font:400 15px/24px var(--font);color:var(--ink-72)}} .fc p:last-child{{margin-bottom:0}}
/* 리스크 */
.rks{{border-top:1px solid var(--line)}}
.rk{{display:grid;grid-template-columns:180px minmax(0,1fr);gap:24px;padding:20px 0;border-bottom:1px solid var(--hair)}}
.rk-c{{font:600 14px/24px var(--font)}} .rk-b p{{margin:0 0 12px;font:400 15px/24px var(--font);color:var(--ink-72)}} .rk-b p:last-child{{margin:0}}
/* 체크포인트 */
.cps{{list-style:none;margin:0;padding:0;border-top:1px solid var(--line)}}
.cps li{{display:grid;grid-template-columns:120px minmax(0,1fr);gap:16px;align-items:start;padding:16px 0;border-bottom:1px solid var(--hair)}}
.cps .when{{font:500 13px/24px var(--font);color:var(--ink-55);white-space:nowrap}}
.cps p{{margin:0;font:400 15px/24px var(--font)}}
.verdict p{{font-size:17px}}
/* 출처 */
.srcs{{margin:0;padding:0 0 0 22px;display:grid;gap:8px}} .srcs li{{font:400 14px/20px var(--font);color:var(--ink-55)}} .srcs a{{color:var(--ink-72);text-decoration:underline;text-decoration-color:var(--line);text-underline-offset:3px}} .srcs a:hover{{color:var(--ink);text-decoration-color:var(--ink)}}
.srcmore summary{{margin-top:14px;font:500 13px/20px var(--font);color:var(--ink-55);cursor:pointer;list-style:none}} .srcmore[open] summary{{margin-bottom:8px}}
.disc{{max-width:880px;margin:8px 0 0;padding:18px 0 0;border-top:1px solid var(--hair);font:400 12px/18px var(--font);color:var(--ink-55)}}
/* 푸터 */
.foot{{margin-top:96px;border-top:1px solid var(--hair);padding:56px 0 48px}}
.foot .brand img{{height:13px}} .flinks{{display:flex;flex-wrap:wrap;gap:8px 24px;margin-top:20px}} .flinks a{{font:400 14px/20px var(--font);color:var(--ink-72)}} .flinks a:hover{{color:var(--ink)}}
.biz{{margin-top:40px;display:flex;flex-wrap:wrap;gap:4px 16px;font:400 12px/18px var(--font);color:var(--ink-55)}} .copy{{margin-top:32px;font:400 12px/18px var(--font);color:var(--ink-55)}}
#kosEdgeTop,#kosEdgeBot{{display:none}}
@media (hover:none) and (pointer:coarse){{#kosEdgeTop,#kosEdgeBot{{display:block;position:fixed;left:0;right:0;height:12px;z-index:60;pointer-events:none;opacity:.2;background:var(--bg)}} #kosEdgeTop{{top:0}} #kosEdgeBot{{bottom:0}}}}
/* 태블릿·휴대폰 */
@media (max-width:1100px){{.stats{{grid-template-columns:repeat(4,minmax(0,1fr));gap:20px 16px}} .body{{grid-template-columns:180px minmax(0,1fr);gap:40px}} .fcs{{grid-template-columns:1fr}} .vstrip{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media (max-width:820px){{
  :root{{--pad:20px}}
  .hero{{padding:20px 0 26px}}
  h1.name{{font-size:32px;line-height:38px;margin-top:8px}} .price{{margin-top:16px}} .price .p{{font-size:32px;line-height:36px}}
  .stats{{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 12px;padding:18px 0}} .st-v{{font-size:17px}}
  .body{{display:block;padding-top:8px}} .toc{{display:none}}
  .chips{{display:flex;gap:22px;overflow-x:auto;margin:0 calc(-1 * var(--pad)) 12px;padding:0 var(--pad);scrollbar-width:none;position:sticky;top:60px;z-index:5;background:var(--bg);border-bottom:1px solid var(--hair)}} .chips::-webkit-scrollbar{{display:none}}
  .chips a{{flex:none;font:500 13px/42px var(--font);color:var(--ink-55);border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .12s}} .chips a.on{{color:var(--ink);font-weight:600;border-bottom-color:var(--ink)}}
  .sec{{padding-bottom:64px}} .sec-h h2{{font-size:22px;line-height:28px}}
  .ab-title{{font-size:24px;line-height:32px}} .ab-lead{{font-size:16px;line-height:26px}}
  .tiles{{grid-template-columns:1fr}} .fcs{{grid-template-columns:1fr}} .vstrip{{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px 10px;padding:16px 0}}
  .rk{{grid-template-columns:1fr;gap:6px;padding:16px 0}} .cps li{{grid-template-columns:1fr;gap:4px;padding:14px 0}}
  .tbl th,.tbl td{{padding:10px 10px;font-size:13px}} .tbl th:first-child,.tbl td:first-child{{position:sticky;left:0;background:var(--bg)}}
  .prose p{{font-size:16px;line-height:27px}}
}}
</style>
</head>
<body>
<div id="kosEdgeTop" aria-hidden="true"></div><div id="kosEdgeBot" aria-hidden="true"></div>
<nav class="nav" id="nav"><div class="nav-in">
  <a class="brand" href="/"><img class="lt" src="/assets/kosai-wordmark-black.png" alt="KOSAI"><img class="dk" src="/assets/kosai-wordmark-white.png" alt="KOSAI"></a>
  <div class="links"><a href="/Home.html">홈</a><a href="/Reports.html" class="on">리포트</a><a href="/industry.html">업종 분석</a><a href="/Watchlist.html">관심종목</a><a href="/brief.html">모닝브리핑</a></div>
  <div class="right"><a class="login" href="/Login.html">로그인</a>
    <button class="ib" id="themeBtn" aria-label="테마 전환"><svg viewBox="0 0 24 24" id="themeIcon"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg></button>
    <button class="ib menu" aria-label="메뉴"><svg viewBox="0 0 24 24"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button></div>
</div></nav>
<main class="wrap">
  <header class="hero">
    <div>
      <div class="eyebrow"><b>{esc(rep["market"])}</b><span>{esc(rep["sector"])}</span><span>{tk}</span></div>
      <h1 class="name">{esc(name)}</h1>
      <div class="price"><span class="p">{price:,.0f}원</span><span class="c {chg_cls}">{arrow} {pct(abs(chg), True).lstrip("+")}</span><span class="d">{price_date} 장마감</span></div>
      <div class="actions"><button class="btn btn-ink"><svg viewBox="0 0 24 24"><path d="M12 5v14M5 12h14"/></svg>관심종목 추가</button></div>
    </div>
  </header>
  <section class="stats" aria-label="핵심 지표">{stat_html}</section>
  <p class="stats-note">PER·EPS·PBR·BPS 는 최근 4개 분기({esc(val["ttm_window"])}) 기준 자체 산출 · 배당수익률은 주당 {val["dps"]:,.0f}원 기준 · 시세 {price_date} 장마감</p>
  <div class="body">
    <aside class="toc" id="toc">{toc}</aside>
    <div class="content">
      <nav class="chips" id="chips">{chips}</nav>
      {body}
      <p class="disc">본 콘텐츠는 AI가 시장 데이터와 웹 검색 결과를 분석한 정보 제공용이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 책임은 투자자 본인에게 있습니다. 데이터는 지연되거나 오류가 포함될 수 있습니다.</p>
    </div>
  </div>
</main>
<footer class="foot"><div class="wrap">
  <a class="brand" href="/"><img class="lt" src="/assets/kosai-wordmark-black.png" alt="KOSAI"><img class="dk" src="/assets/kosai-wordmark-white.png" alt="KOSAI"></a>
  <div class="flinks"><a href="/Home.html">홈</a><a href="/Reports.html">리포트</a><a href="/industry.html">업종 분석</a><a href="/Watchlist.html">관심종목</a><a href="/brief.html">모닝브리핑</a><a href="/About.html">About</a><a href="/Contact.html">문의하기</a><a href="/Feedback.html">피드백</a><a href="/Terms.html">이용약관</a><a href="/Privacy.html">개인정보처리방침</a></div>
  <div class="biz"><span>상호 코사이</span><span>대표 임범준</span><span>사업자등록번호 380-25-02019</span><span>주소 서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호</span><span>이메일 hello@kosai.kr</span></div>
  <div class="copy">© 2026 KOSAI — All rights reserved.</div>
</div></footer>
<script>
(function(){{
  var nav=document.getElementById('nav'),tick=false;
  function upd(){{tick=false;nav.classList.toggle('scrolled',window.scrollY>32)}} addEventListener('scroll',function(){{if(!tick){{tick=true;requestAnimationFrame(upd)}}}},{{passive:true}});upd();
  var sun='<path d="M12 4V2M12 22v-2M4.9 4.9 3.5 3.5M20.5 20.5l-1.4-1.4M4 12H2M22 12h-2M4.9 19.1l-1.4 1.4M20.5 3.5l-1.4 1.4"/><circle cx="12" cy="12" r="4"/>',moon='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
  var root=document.documentElement,icon=document.getElementById('themeIcon');function paint(){{icon.innerHTML=root.getAttribute('data-theme')==='dark'?sun:moon}}paint();
  document.getElementById('themeBtn').addEventListener('click',function(){{var t=root.getAttribute('data-theme')==='dark'?'light':'dark';root.setAttribute('data-theme',t);try{{localStorage.setItem('kos-theme',t)}}catch(e){{}}paint();}});
  var links=[].slice.call(document.querySelectorAll('#toc a, #chips a')),secs=[].slice.call(document.querySelectorAll('section.sec'));
  function spy(){{var y=window.scrollY+window.innerHeight*.3,cur=secs[0];secs.forEach(function(s){{if(s.offsetTop<=y)cur=s}});links.forEach(function(a){{var on=a.getAttribute('href')==='#'+cur.id;if(on&&!a.classList.contains('on')&&a.parentNode.id==='chips'){{a.parentNode.scrollTo({{left:Math.max(0,a.offsetLeft-20),behavior:'smooth'}})}}a.classList.toggle('on',on)}})}}
  addEventListener('scroll',function(){{requestAnimationFrame(spy)}},{{passive:true}});spy();
}})();
</script>
</body>
</html>'''
    Path(out_path).write_text(html, encoding='utf-8')
    print(f'✅ {out_path} · {len(html):,}자 · 절 {len(SECTIONS)}')


if __name__ == '__main__':
    tk = sys.argv[1] if len(sys.argv) > 1 else '005930'
    out = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'preview/stock.html')
    build(tk, out)
