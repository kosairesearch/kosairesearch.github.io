#!/usr/bin/env python3
"""GEO 정적 리포트 페이지 생성 — r/{ticker}.html (+ r/index.html).

AI 크롤러(GPTBot·ClaudeBot·PerplexityBot·네이버 등)는 대부분 JS를 실행하지 않아
stock.html(클라이언트 렌더링)의 리포트를 읽지 못한다. 이미 생성된 리포트
JSON(v2 우선, v1 폴백)을 순수 HTML로 변환해 커밋하면 크롤러가 전문을 읽고
인용할 수 있다(GEO). 구글·네이버도 JS 없이 전문을 읽게 되어 SEO에도 플러스.

- 한국어 본문 우선(국내 타깃) + 영어 전문 병기(글로벌 엔진·기존 색인 URL 유지)
- 지표(가격·시총·PER·PBR·ROE·배당)는 stocks.js/valuation.js에서 매일 새로 주입
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

DISC = {
    "ko": "본 리포트는 공시(DART)·시장 데이터(KRX) 기반의 AI 생성 정보 자료이며 "
          "투자 권유가 아닙니다.",
    "en": "This report is AI-generated from public disclosures (DART) and market "
          "data (KRX) for informational purposes only. It is not investment advice.",
}

# 섹션 제목 — 한국어판은 국내 관례(PER·PBR), 영어판은 P/E·P/B
H = {
    "ko": {"summary": "요약", "keypoints": "핵심 포인트", "business": "사업 개요",
           "earnings": "실적", "industry": "산업 동향", "metrics": "핵심 지표",
           "outlook": "전망", "valuation": "밸류에이션", "bull": "강세 논리",
           "bear": "약세 논리", "risks": "리스크 요인", "watch": "체크포인트",
           "verdict": "결론", "sources": "출처"},
    "en": {"summary": "Summary", "keypoints": "Key points", "business": "Business",
           "earnings": "Earnings", "industry": "Industry", "metrics": "Key metrics",
           "outlook": "Outlook", "valuation": "Valuation", "bull": "Bull case",
           "bear": "Bear case", "risks": "Risk factors", "watch": "What to watch",
           "verdict": "Bottom line", "sources": "Sources"},
}

CSS = ("body{font-family:-apple-system,Segoe UI,Roboto,'Apple SD Gothic Neo','Malgun Gothic',"
       "Helvetica,Arial,sans-serif;max-width:760px;margin:0 auto;padding:24px 16px;"
       "line-height:1.65;color:#1a1a1a;background:#fff}h1{font-size:1.5rem;line-height:1.3}"
       "h2{font-size:1.15rem;margin-top:2em;border-bottom:1px solid #e5e5e5;padding-bottom:4px}"
       "h3{font-size:1rem}table{border-collapse:collapse;width:100%;font-size:.95rem}"
       "td,th{border:1px solid #e0e0e0;padding:6px 10px;text-align:left}th{background:#f7f7f7}"
       "a{color:#0a5bd3}.muted{color:#666;font-size:.9rem}.disc{font-size:.85rem;color:#777;"
       "border-top:1px solid #e5e5e5;margin-top:2.5em;padding-top:1em}ul{padding-left:1.2em}"
       "hr{border:0;border-top:2px solid #ddd;margin:3em 0 1em}"
       "@media(prefers-color-scheme:dark){body{background:#111;color:#e6e6e6}"
       "th{background:#1d1d1d}td,th{border-color:#333}h2{border-color:#333}hr{border-color:#333}"
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
    if n and n == n.upper() and len(n) > 3:
        n = n.title()
    return n or (name or "").strip()


def pk(v, lang):
    """이중언어 필드에서 lang 우선으로 텍스트를 꺼낸다(없으면 반대 언어)."""
    if isinstance(v, dict):
        other = "en" if lang == "ko" else "ko"
        return (v.get(lang) or v.get(other) or "").strip()
    return (v or "").strip() if isinstance(v, str) else ""


def esc(s):
    return html.escape(s if isinstance(s, str) else "")


def para(title, body, lang):
    t = pk(body, lang)
    return f"<h2>{esc(title)}</h2>\n<p>{esc(t)}</p>\n" if t else ""


def bullets(title, items, lang):
    if not items:
        return ""
    lis = "".join(f"<li>{esc(pk(x, lang))}</li>" for x in items if pk(x, lang))
    return f"<h2>{esc(title)}</h2>\n<ul>{lis}</ul>\n" if lis else ""


def cases(title, items, lang):
    """bull/bear: [{title:{},body:{}}] → h3+p 묶음."""
    if not items:
        return ""
    out = [f"<h2>{esc(title)}</h2>"]
    for it in items:
        t, b = pk((it or {}).get("title"), lang), pk((it or {}).get("body"), lang)
        if b:
            out.append(f"<h3>{esc(t)}</h3>\n<p>{esc(b)}</p>" if t else f"<p>{esc(b)}</p>")
    return "\n".join(out) + "\n" if len(out) > 1 else ""


def risks_html(items, lang):
    if not items:
        return ""
    rows = []
    for it in items:
        c = pk((it or {}).get("cat"), lang)
        b = pk((it or {}).get("body") or it, lang)
        if b:
            rows.append(f"<li><strong>{esc(c)}:</strong> {esc(b)}</li>" if c
                        else f"<li>{esc(b)}</li>")
    if not rows:
        return ""
    return f"<h2>{esc(H[lang]['risks'])}</h2>\n<ul>" + "".join(rows) + "</ul>\n"


def checkpoints_html(items, lang):
    if not items:
        return ""
    rows = []
    for it in items:
        w = pk((it or {}).get("when"), lang)
        what = pk((it or {}).get("what") or it, lang)
        if what:
            rows.append(f"<li><strong>{esc(w)}</strong> — {esc(what)}</li>" if w
                        else f"<li>{esc(what)}</li>")
    if not rows:
        return ""
    return f"<h2>{esc(H[lang]['watch'])}</h2>\n<ul>" + "".join(rows) + "</ul>\n"


def metrics_table(st, val, lang, data_date):
    price = st.get("price") or 0
    shares = st.get("shares") or 0
    v = val or {}
    eps, bps, dps = v.get("eps") or 0, v.get("bps") or 0, v.get("dps") or 0
    rows = []
    if price:
        rows.append(("주가" if lang == "ko" else "Price", f"₩{price:,.0f}"))
    if price and shares:
        mcap = price * shares
        if lang == "ko":
            mc = f"{mcap/1e12:,.1f}조원" if mcap >= 1e12 else f"{mcap/1e8:,.0f}억원"
        else:
            mc = f"₩{mcap/1e12:,.2f}T"
        rows.append(("시가총액" if lang == "ko" else "Market cap", mc))
    if price and eps and eps > 0:
        rows.append(("PER" if lang == "ko" else "P/E", f"{price/eps:,.1f}"))
    if price and bps and bps > 0:
        rows.append(("PBR" if lang == "ko" else "P/B", f"{price/bps:,.2f}"))
    if v.get("roe") is not None:
        rows.append(("ROE", f"{v['roe']}%"))
    if price and dps:
        rows.append(("배당수익률" if lang == "ko" else "Dividend yield",
                     f"{dps/price*100:,.2f}%"))
    if not rows:
        return ""
    trs = "".join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a, b in rows)
    label = "기준" if lang == "ko" else "as of"
    return (f"<h2>{esc(H[lang]['metrics'])} "
            f"<span class=\"muted\">({data_date} {label})</span></h2>"
            f"\n<table>{trs}</table>\n")


def lang_sections(rep, st, val, lang, data_date):
    h = H[lang]
    parts = [para(h["summary"], rep.get("lead"), lang),
             bullets(h["keypoints"], rep.get("keypoints"), lang),
             para(h["business"], rep.get("business"), lang),
             para(h["earnings"], rep.get("earnings") or rep.get("recent"), lang),
             para(h["industry"], rep.get("industry"), lang),
             metrics_table(st, val, lang, data_date),
             para(h["outlook"], rep.get("outlook"), lang),
             para(h["valuation"], rep.get("valuation_comment"), lang),
             cases(h["bull"], rep.get("bull"), lang),
             cases(h["bear"], rep.get("bear"), lang),
             risks_html(rep.get("risks"), lang),
             checkpoints_html(rep.get("checkpoints"), lang),
             para(h["verdict"], (rep.get("verdict") or {}).get("body"), lang)]
    return "".join(p for p in parts if p)


def build_page(tk, st, val, rep, tier, data_date):
    official_en = (st.get("name_en") or "").strip() or st.get("name", tk)
    name_en = display_name(official_en)
    name_ko = st.get("name", "") or name_en
    sector = st.get("sector") or rep.get("sector") or ""
    market = st.get("market") or rep.get("market") or ""
    t_ko, t_en = pk(rep.get("title"), "ko"), pk(rep.get("title"), "en")
    rep_date = rep.get("reportDate") or ""
    url = f"{SITE}/r/{tk}.html"

    lead_ko = re.sub(r"\s+", " ", pk(rep.get("desc"), "ko") or pk(rep.get("lead"), "ko"))
    meta_desc = esc(lead_ko[:158])

    ko_html = lang_sections(rep, st, val, "ko", data_date)
    en_html = lang_sections(rep, st, val, "en", data_date)

    srcs = [s for s in (rep.get("sources") or []) if isinstance(s, str)][:12]
    src_html = ""
    if srcs:
        lis = "".join(f'<li><a href="{esc(s)}" rel="nofollow">{esc(s[:90])}</a></li>'
                      for s in srcs)
        src_html = f"<h2>{H['ko']['sources']} · Sources</h2>\n<ul class=\"muted\">{lis}</ul>\n"

    ld = {
        "@context": "https://schema.org", "@type": "Article",
        "headline": f"{name_ko} ({tk}) — {t_ko}" if t_ko else f"{name_ko} ({tk})",
        "datePublished": rep_date or data_date, "dateModified": data_date,
        "inLanguage": ["ko", "en"], "isAccessibleForFree": True,
        "mainEntityOfPage": url,
        "author": {"@type": "Organization", "name": "KOSAI", "url": SITE},
        "about": {"@type": "Corporation", "name": name_ko,
                  "legalName": official_en,
                  "alternateName": name_en, "tickerSymbol": tk},
    }

    h1 = f"{esc(name_ko)} ({tk})" + (f" — {esc(t_ko)}" if t_ko else "")
    sub = " · ".join(x for x in (esc(name_en), esc(sector), esc(market),
                                 f"리포트 {esc(rep_date)}" if rep_date else "") if x)
    en_h1 = f"{esc(name_en)} ({tk})" + (f" — {esc(t_en)}" if t_en else "")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name_ko)} ({tk}) 종목 분석 리포트 — {esc(name_en)} | KOSAI</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(name_ko)} ({tk}) 종목 분석 리포트 | KOSAI">
<meta property="og:description" content="{meta_desc}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
<style>{CSS}</style>
</head>
<body>
<p class="muted"><a href="{SITE}/">KOSAI — AI 종목 리서치</a> ·
<a href="{SITE}/stock.html?ticker={tk}">인터랙티브 리포트 ↗</a> ·
<a href="{SITE}/r/">전체 종목</a></p>
<h1>{h1}</h1>
<p class="muted">{sub}</p>
{ko_html}{src_html}
<hr>
<p class="muted">English version</p>
<h1>{en_h1}</h1>
{en_html}
<p class="disc">{DISC['ko']}<br>{DISC['en']}<br>
데이터 기준 {data_date} · <a href="{SITE}/">KOSAI</a>
({'full' if tier == 'v2' else 'standard'} report)</p>
</body>
</html>
"""


def build_index(entries, data_date):
    lis = "".join(
        f'<li><a href="/r/{tk}.html">{esc(nk)} ({tk})</a>'
        f'<span class="muted"> — {esc(ne)}</span></li>'
        for tk, ne, nk in entries)
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>전 종목 AI 분석 리포트 (코스피·코스닥 {len(entries):,}개) | KOSAI</title>
<meta name="description" content="코스피·코스닥 {len(entries):,}개 상장사 AI 분석 리포트 —
 사업·실적·밸류에이션·리스크. DART 공시와 KRX 데이터 기반, 매일 갱신.">
<link rel="canonical" href="{SITE}/r/">
<style>{CSS}</style>
</head>
<body>
<p class="muted"><a href="{SITE}/">KOSAI — AI 종목 리서치</a></p>
<h1>전 종목 AI 분석 리포트</h1>
<p>코스피·코스닥 {len(entries):,}개 상장사의 AI 분석 리포트입니다 — 사업 구조, 실적,
밸류에이션, 강세/약세 논리, 리스크까지. DART 공시·KRX 시장 데이터 기반으로 매일
갱신됩니다. 데이터 기준 {data_date}. (English included on each page.)</p>
<ul>{lis}</ul>
<p class="disc">{DISC['ko']}</p>
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

    entries.sort(key=lambda x: x[2] or x[1])
    (OUT / "index.html").write_text(build_index(entries, data_date), encoding="utf-8")

    keep = {f"{tk}.html" for tk, _, _ in entries} | {"index.html"}
    removed = 0
    for f in OUT.glob("*.html"):
        if f.name not in keep:
            f.unlink()
            removed += 1
    print(f"GEO 페이지 {made}개 생성 (+index), 잔존 {removed}개 제거 · 기준일 {data_date}")


if __name__ == "__main__":
    main()
