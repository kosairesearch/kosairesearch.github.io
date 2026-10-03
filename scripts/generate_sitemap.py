#!/usr/bin/env python3
"""sitemap.xml 생성 — 정적 페이지 + 업종 상세 + 종목 페이지(stock/{종목코드}.html).

데이터 갱신 워크플로에서 종목 페이지를 만든 뒤(build_stock_static.py) 실행해 sitemap을 항상 최신으로 유지한다.
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
    # 평일 아침마다 새 글이 올라간다. 우선순위를 리포트와 같게 둔다 —
    # 검색에서 들어오는 글이라 색인이 늦으면 그날 값이 없어진다.
    ("/brief.html", "daily", "0.9"),
    # Screener.html 은 리포트 페이지로 보내는 껍데기라 넣지 않는다.
    # noindex 인 주소를 사이트맵에 올리면 "색인하지 마라" 와 "색인해라" 를
    # 동시에 말하는 셈이 된다.
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
    # 종목 페이지 — 2026-10-03 부터 종목마다 미리 만든 페이지(stock/{종목코드}.html · scripts/build_stock_static.py)다.
    # canonical 이 저마다 자기 주소이고, 자바스크립트 없이 리포트 글이 다 들어 있다. 지금 상장된 종목만 올린다 — 상장 폐지로
    # 리포트만 남은 종목의 페이지는 noindex 라 올리지 않는다("색인하지 마라" 와 "색인해라" 를 같이 말하지 않게).
    #
    # 옛 주소 둘은 올리지 않는다.
    #   · stock.html?ticker=…  — 새 주소로 넘기는 껍데기다. 전에 2,687줄을 올렸다가, canonical 이 하나라 크롤러에게 전부
    #     "나는 /stock.html 이다" 라고 답해 네이버에서 'kosai' 를 찾으면 종목 상세가 사이트 대표로 올라온 일이 있었다.
    #   · r/{종목코드}.html     — 옛 로봇용 사본. 새 주소로 보내는 껍데기(scripts/retire_r_pages.py)로 바뀌었다.
    listed = set(tickers)
    pages = sorted(f for f in (ROOT / "stock").glob("*.html") if f.stem in listed) if (ROOT / "stock").exists() else []
    for f in pages:
        out.append(
            f"<url><loc>{SITE}/stock/{f.name}</loc><lastmod>{lastmod}</lastmod>"
            f"<changefreq>daily</changefreq><priority>0.7</priority></url>"
        )
    out.append("</urlset>\n")

    (ROOT / "sitemap.xml").write_text("\n".join(out), encoding="utf-8")
    # 세는 것과 적는 것이 같아야 한다. tickers 를 세고 있었는데 그 목록은
    # 이제 사이트맵에 들어가지 않는다 — 실제로 적힌 줄만 센다.
    print(
        f"sitemap.xml: 정적 {len(STATIC_PAGES)} + 업종 {len(sectors)} "
        f"+ 종목 페이지 {len(pages)} URL (종목 {len(tickers)}개 중)"
    )


if __name__ == "__main__":
    main()
