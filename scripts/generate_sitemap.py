#!/usr/bin/env python3
"""sitemap.xml 생성 — 정적 페이지 + 전 종목 상세 페이지 URL.

data/stocks.js 를 읽어 종목별 URL을 만들고, 데이터 갱신 워크플로에서
collect_data 이후에 실행해 sitemap을 항상 최신으로 유지한다.
"""
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://kosai.kr"

STATIC_PAGES = [
    ("/", "daily", "1.0"),
    ("/Home.html", "daily", "0.9"),
    ("/Reports.html", "daily", "0.9"),
    ("/Screener.html", "daily", "0.8"),
    ("/industry.html", "daily", "0.7"),
    ("/About.html", "monthly", "0.5"),
    ("/Contact.html", "monthly", "0.3"),
    ("/Feedback.html", "monthly", "0.3"),
    ("/Privacy.html", "monthly", "0.2"),
    ("/Terms.html", "monthly", "0.2"),
]


def main():
    raw = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
    m = re.search(r"window\.KOS_LIVE_DATA\s*=\s*(\{.*)", raw, re.S)
    data = json.loads(m.group(1).rstrip().rstrip(";"))
    tickers = [s["ticker"] for s in data["stocks"]]

    # 업종 상세 페이지(industry.html?sector=...) — AI 분석이 있는 섹터를 색인 대상에 포함
    sectors = []
    sec_path = ROOT / "data" / "sectors.js"
    if sec_path.exists():
        sraw = sec_path.read_text(encoding="utf-8")
        sm = re.search(r"window\.KOS_SECTORS\s*=\s*(\{.*)", sraw, re.S)
        if sm:
            sdata = json.loads(sm.group(1).rstrip().rstrip(";"))
            sectors = list(sdata.get("sectors", {}).keys())

    dd = data.get("dataDate", "")
    lastmod = (
        f"{dd[:4]}-{dd[4:6]}-{dd[6:8]}" if len(dd) == 8 else date.today().isoformat()
    )

    out = ['<?xml version="1.0" encoding="UTF-8"?>']
    out.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for path, freq, prio in STATIC_PAGES:
        out.append(
            f"<url><loc>{SITE}{path}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        )
    for sec in sectors:
        loc = f"{SITE}/industry.html?sector={quote(sec)}"
        out.append(
            f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>weekly</changefreq><priority>0.6</priority></url>"
        )
    for t in tickers:
        out.append(
            f"<url><loc>{SITE}/stock.html?ticker={t}</loc>"
            f"<lastmod>{lastmod}</lastmod><changefreq>daily</changefreq>"
            f"<priority>0.6</priority></url>"
        )
    out.append("</urlset>\n")

    (ROOT / "sitemap.xml").write_text("\n".join(out), encoding="utf-8")
    print(
        f"sitemap.xml: 정적 {len(STATIC_PAGES)} + 업종 {len(sectors)} "
        f"+ 종목 {len(tickers)} URL"
    )


if __name__ == "__main__":
    main()
