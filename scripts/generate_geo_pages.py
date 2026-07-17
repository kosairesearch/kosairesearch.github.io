#!/usr/bin/env python3
"""GEO 정적 리포트 페이지 생성 — r/{ticker}.html (+ r/index.html).

AI 크롤러(GPTBot·ClaudeBot·PerplexityBot 등)는 대부분 JS를 실행하지 않아
stock.html(클라이언트 렌더링)의 리포트를 읽지 못한다. 이미 생성된 리포트
JSON(v2 우선, v1 폴백)을 순수 HTML로 변환해 커밋하면 크롤러가 전문을 읽고
인용할 수 있다(GEO). 구글도 JS 없이 전문을 읽게 되어 SEO에도 플러스.

- 영어 본문 중심(글로벌 엔진 타깃) + 한국어 회사명 병기(한국어 질의 앵커)
- 지표(가격·시총·P/E·P/B·배당·ROE)는 stocks.js/valuation.js에서 매일 새로 주입
- schema.org JSON-LD(isAccessibleForFree=true), canonical, 면책 문구 포함
- update_data.yml에서 매일 실행 → 항상 최신. 표준 라이브러리만 사용.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "r"
SITE = "https://kosai.kr"

DISCLAIMER = ("This report is AI-generated from public disclosures (DART) and market "
              "data (KRX) for informational purposes only. It is not investment advice.")

CSS = ("body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
       "max-width:760px;margin:0 auto;padding:24px 16px;line-height:1.65;color:#1a1a1a;"
       "background:#fff}h1{font-size:1.5rem;line-height:1.3}h2{font-size:1.15rem;"
       "margin-top:2em;border-bottom:1px solid #e5e5e5;padding-bottom:4px}h3{font-size:1rem}"
       "table{border-collapse:collapse;width:100%;font-size:.95rem}td,th{border:1px solid"
       " #e0e0e0;padding:6px 10px;text-align:left}th{background:#f7f7f7}a{color:#0a5bd3}"
       ".muted{color:#666;font-size:.9rem}.disc{font-size:.85rem;color:#777;border-top:"
       "1px solid #e5e5e5;margin-top:2.5em;padding-top:1em}ul{padding-left:1.2em}"
       "@media(prefers-color-scheme:dark){body{background:#111;color:#e6e6e6}"
       "th{background:#1d1d1d}td,th{border-color:#333}h2{border-color:#333}"
       "a{color:#7fb3ff}.muted,.disc{color:#999}.disc{border-color:#333}}")


def parse_js(path, var):
    raw = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(var + r"\s*=\s*(\{.*)", raw, re.S)
    return json.loads(m.group(1).rstrip().rstrip(";"))


_SUFFIX = re.compile(r"[\s,]*(CO\W{0,3}LTD\W?|Co\W{0,3}Ltd\W?|Corporation|Corp\.?|"
                     r"Inc\.?|Company\s+Limited|Limited|LTD\.?)\s*$", re.I)


def display_name(name):
    """법인 접미어(CO,.LTD 등) 제거 + 과도한 대문자면 타이틀케이스로."""
    n = _SUFFIX.sub("", (name or "").strip()).strip(" ,.")
    if n and n == n.upper() and len(n) > 3:      # 전부 대문자인 공식명 → 읽기 좋게
        n = n.title()
    return n or (name or "").strip()


def pk(v):
    """이중언어 필드에서 영어 우선으로 텍스트를 꺼낸다."""
    if isinstance(v, dict):
        return (v.get("en") or v.get("ko") or "").strip()
    return (v or "").strip() if isinstance(v, str) else ""


def esc(s):
    return html.escape(pk(s) if not isinstance(s, str) else s.strip())


def para(title, body):
    t = pk(body)
    return f"<h2>{esc(title)}</h2>\n<p>{esc(t)}</p>\n" if t else ""


def bullets(title, items):
    if not items:
        return ""
    lis = "".join(f"<li>{esc(pk(x))}</li>" for x in items if pk(x))
    return f"<h2>{esc(title)}</h2>\n<ul>{lis}</ul>\n" if lis else ""


def cases(title, items):
    """bull/bear: [{title:{},body:{}}] → h3+p 묶음."""
    if not items:
        return ""
    out = [f"<h2>{esc(title)}</h2>"]
    for it in items:
        t, b = pk((it or {}).get("title")), pk((it or {}).get("body"))
        if b:
            out.append(f"<h3>{esc(t)}</h3>\n<p>{esc(b)}</p>" if t else f"<p>{esc(b)}</p>")
    return "\n".join(out) + "\n" if len(out) > 1 else ""


def risks_html(items):
    if not items:
        return ""
    out = ["<h2>Risk factors</h2>", "<ul>"]
    for it in items:
        c, b = pk((it or {}).get("cat")), pk((it or {}).get("body") or it)
        if b:
            out.append(f"<li><strong>{esc(c)}:</strong> {esc(b)}</li>" if c
                       else f"<li>{esc(b)}</li>")
    out.append("</ul>")
    return "\n".join(out) + "\n" if len(out) > 3 or len(out) == 3 else ""


def checkpoints_html(items):
    if not items:
        return ""
    rows = []
    for it in items:
        w, what = pk((it or {}).get("when")), pk((it or {}).get("what") or it)
        if what:
            rows.append(f"<li><strong>{esc(w)}</strong> — {esc(what)}</li>" if w
                        else f"<li>{esc(what)}</li>")
    if not rows:
        return ""
    return "<h2>What to watch</h2>\n<ul>" + "".join(rows) + "</ul>\n"


def fmt_krw(n):
    return f"₩{n:,.0f}"


def metrics_rows(st, val):
    """stocks.js + valuation.js → (지표행 리스트, 요약용 dict)."""
    price = st.get("price") or 0
    shares = st.get("shares") or 0
    v = val or {}
    eps, bps, dps = v.get("eps") or 0, v.get("bps") or 0, v.get("dps") or 0
    rows, summ = [], {}
    if price:
        rows.append(("Price", fmt_krw(price)))
        summ["price"] = price
    if price and shares:
        mcap = price * shares
        rows.append(("Market cap", f"₩{mcap/1e12:,.2f}T"))
        summ["mcap_t"] = round(mcap / 1e12, 2)
    if price and eps and eps > 0:
        rows.append(("P/E", f"{price/eps:,.1f}"))
    if price and bps and bps > 0:
        rows.append(("P/B", f"{price/bps:,.2f}"))
    if v.get("roe") is not None:
        rows.append(("ROE", f"{v['roe']}%"))
    if price and dps:
        rows.append(("Dividend yield", f"{dps/price*100:,.2f}%"))
    return rows, summ


def build_page(tk, st, val, rep, tier, data_date):
    official_en = (st.get("name_en") or "").strip() or st.get("name", tk)
    name_en = display_name(official_en)
    name_ko = st.get("name", "")
    sector = st.get("sector") or rep.get("sector") or ""
    market = st.get("market") or rep.get("market") or ""
    title_line = pk(rep.get("title"))
    lead = pk(rep.get("lead"))
    desc = (pk(rep.get("desc")) or lead)[:300]
    meta_desc = esc(re.sub(r"\s+", " ", desc)[:158])
    rep_date = rep.get("reportDate") or ""
    url = f"{SITE}/r/{tk}.html"

    rows, summ = metrics_rows(st, val)
    mtable = ""
    if rows:
        trs = "".join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a, b in rows)
        mtable = (f"<h2>Key metrics <span class=\"muted\">(as of {data_date})</span></h2>"
                  f"\n<table>{trs}</table>\n")

    body = [para("Summary", rep.get("lead"))]
    body.append(bullets("Key points", rep.get("keypoints")))
    body.append(para("Business", rep.get("business")))
    body.append(para("Earnings", rep.get("earnings") or rep.get("recent")))
    body.append(para("Industry", rep.get("industry")))
    body.append(mtable)
    body.append(para("Outlook", rep.get("outlook")))
    body.append(para("Valuation", rep.get("valuation_comment")))
    body.append(cases("Bull case", rep.get("bull")))
    body.append(cases("Bear case", rep.get("bear")))
    body.append(risks_html(rep.get("risks")))
    body.append(checkpoints_html(rep.get("checkpoints")))
    body.append(para("Bottom line", (rep.get("verdict") or {}).get("body")))

    srcs = [s for s in (rep.get("sources") or []) if isinstance(s, str)][:12]
    if srcs:
        lis = "".join(f'<li><a href="{esc(s)}" rel="nofollow">{esc(s[:90])}</a></li>'
                      for s in srcs)
        body.append(f"<h2>Sources</h2>\n<ul class=\"muted\">{lis}</ul>\n")

    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"{name_en} ({tk}) — {title_line}" if title_line else f"{name_en} ({tk})",
        "datePublished": rep_date or data_date, "dateModified": data_date,
        "inLanguage": "en", "isAccessibleForFree": True,
        "mainEntityOfPage": url,
        "author": {"@type": "Organization", "name": "KOSAI",
                   "url": SITE},
        "about": {"@type": "Corporation", "name": name_en,
                  "legalName": official_en,
                  "alternateName": name_ko, "tickerSymbol": tk},
    }

    h1 = f"{esc(name_en)} ({tk})" + (f" — {esc(title_line)}" if title_line else "")
    sub = " · ".join(x for x in (esc(name_ko), esc(sector), esc(market),
                                 f"Report {esc(rep_date)}" if rep_date else "") if x)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name_en)} ({tk}) Stock Analysis — {esc(name_ko)} | KOSAI</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(name_en)} ({tk}) Stock Analysis | KOSAI">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<p class="muted"><a href="{SITE}/">KOSAI — Korean Stocks in English</a> ·
<a href="{SITE}/stock.html?ticker={tk}">Interactive report ↗</a> ·
<a href="{SITE}/r/">All companies</a></p>
<h1>{h1}</h1>
<p class="muted">{sub}</p>
{''.join(b for b in body if b)}
<p class="disc">{DISCLAIMER}<br>Data as of {data_date} · Generated by
<a href="{SITE}/">KOSAI</a> ({'full' if tier == 'v2' else 'standard'} report)</p>
</body>
</html>
"""


def build_index(entries, data_date):
    lis = "".join(
        f'<li><a href="/r/{tk}.html">{esc(ne)} ({tk})</a>'
        f'<span class="muted"> — {esc(nk)}</span></li>'
        for tk, ne, nk in entries)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>All Korean Stock Reports (KOSPI·KOSDAQ) | KOSAI</title>
<meta name="description" content="AI-generated English research reports on {len(entries):,}
 Korean listed companies, updated daily from DART filings and KRX market data.">
<link rel="canonical" href="{SITE}/r/">
<style>{CSS}</style>
</head>
<body>
<p class="muted"><a href="{SITE}/">KOSAI — Korean Stocks in English</a></p>
<h1>Korean Stock Reports in English</h1>
<p>AI-generated research reports on {len(entries):,} KOSPI and KOSDAQ companies —
business, earnings, valuation, bull/bear cases and risks. Updated daily from public
disclosures (DART) and market data (KRX). Data as of {data_date}.</p>
<ul>{lis}</ul>
<p class="disc">{DISCLAIMER}</p>
</body>
</html>
"""


def main():
    live = parse_js("data/stocks.js", r"window\.KOS_LIVE_DATA")
    stocks = {s["ticker"]: s for s in live.get("stocks", [])}
    dd = live.get("dataDate", "")
    data_date = f"{dd[:4]}-{dd[4:6]}-{dd[6:8]}" if len(dd) == 8 else date.today().isoformat()
    try:
        vals = parse_js("data/valuation.js", r"window\.KOS_VALUATION").get("stocks", {})
    except Exception:
        vals = {}

    OUT.mkdir(exist_ok=True)
    made, entries = 0, []
    for tk, st in stocks.items():
        rep, tier = None, None
        for d, t in (("reports_v2", "v2"), ("reports", "v1")):
            p = ROOT / "data" / d / f"{tk}.json"
            if p.exists():
                try:
                    rep, tier = json.loads(p.read_text(encoding="utf-8")), t
                    break
                except Exception:
                    continue
        if not rep:
            continue
        try:
            page = build_page(tk, st, vals.get(tk), rep, tier, data_date)
        except Exception as e:
            print(f"⚠ {tk} 생성 실패: {e}")
            continue
        (OUT / f"{tk}.html").write_text(page, encoding="utf-8")
        entries.append((tk, display_name(st.get("name_en") or st.get("name") or tk),
                        st.get("name", "")))
        made += 1

    entries.sort(key=lambda x: x[1].lower())
    (OUT / "index.html").write_text(build_index(entries, data_date), encoding="utf-8")

    # 유니버스에서 빠진 종목의 잔존 페이지 제거(상장폐지 등)
    keep = {f"{tk}.html" for tk, _, _ in entries} | {"index.html"}
    removed = 0
    for f in OUT.glob("*.html"):
        if f.name not in keep:
            f.unlink()
            removed += 1
    print(f"GEO 페이지 {made}개 생성 (+index), 잔존 {removed}개 제거 · 기준일 {data_date}")


if __name__ == "__main__":
    main()
