#!/usr/bin/env python3
"""'왜 움직였나' — 구글 뉴스에서 제목만 모은다.

브리핑에서 이게 없으면 "S&P 500이 0.17% 내렸다"까지밖에 못 쓴다.
"미시간대 소비자심리가 예상을 밑돌아서"는 뉴스가 있어야 나온다.

판정 3차에서 구글 뉴스 RSS 가 한국어(hl=ko&gl=KR)로 100건씩 물어오는 걸
확인했다. 네이버 검색 API 는 없어도 된다 — 있으면 보강한다.

지키는 것
  · 제목과 매체명, 링크만 받는다. 본문은 가져오지 않는다. 기사 전문을
    긁어다 재가공하면 저작권 문제가 되고, 브리핑에 필요한 것도 '무슨 일이
    있었나'라는 단서뿐이다. 해석은 우리가 데이터를 보고 쓴다.
  · 제목을 그대로 브리핑에 옮기지 않는다. 생성 쪽에 '맥락'으로만 넘긴다.
  · 광고성·추천성 제목은 걸러 낸다. '목표가', '수익률', '지금 사야'
    같은 표현이 브리핑에 흘러들면 투자권유가 된다.

    python3 scripts/news_data.py                       # 시황 + 지수
    python3 scripts/news_data.py --tickers 005930,000660
"""
import argparse
import datetime
import html as _html
import io
import json
import re
import sys
import xml.etree.ElementTree as ET

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0)"}
TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))

# 이 표현이 제목에 있으면 버린다. 투자권유로 읽히는 문장이 브리핑에
# 흘러드는 경로를 여기서 끊는다.
DROP = re.compile(
    r"목표가|목표주가|매수\s*추천|매도\s*추천|지금\s*사|사야\s*할|급등주|"
    r"유망주|수익률\s*\d|추천\s*종목|무료\s*상담|리딩|카톡|텔레그램|"
    r"단독\s*공개|비법|대박")

QUERIES_KO = [
    ("시황", "코스피 마감 외국인 순매수"),
    ("환율", "원달러 환율 마감"),
]
QUERIES_EN = [
    ("미국 지수", "stock market close S&P 500 Nasdaq"),
    ("미국 반도체", "semiconductor stocks Nvidia Broadcom"),
    ("미국 지표", "US economic data inflation consumer"),
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(s or "")).strip()


def rss(query, hl="ko", gl="KR", ceid="KR:ko", limit=12, since_hours=48):
    """구글 뉴스 RSS. 최근 것만, 제목·매체·링크만."""
    url = ("https://news.google.com/rss/search?q=" + requests.utils.quote(query)
           + f"&hl={hl}&gl={gl}&ceid={ceid}")
    try:
        r = requests.get(url, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
        root = ET.parse(io.StringIO(r.text)).getroot()
    except Exception as e:
        log(f"· «{query}» 실패: {type(e).__name__} {e}")
        return []

    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=since_hours)
    out, dropped = [], 0
    for it in root.findall(".//item"):
        title = _clean(it.findtext("title"))
        if not title:
            continue
        if DROP.search(title):
            dropped += 1
            continue
        # 구글은 제목 끝에 ' - 매체명' 을 붙인다. 매체를 떼어 따로 둔다.
        src = it.findtext("source") or ""
        if not src and " - " in title:
            title, src = title.rsplit(" - ", 1)
        pub = it.findtext("pubDate") or ""
        when = None
        try:
            when = datetime.datetime.strptime(pub, "%a, %d %b %Y %H:%M:%S %Z")
            when = when.replace(tzinfo=datetime.timezone.utc)
        except Exception:
            pass
        if when and when < cutoff:
            continue
        out.append({"title": _clean(title), "source": _clean(src),
                    "published": when.isoformat() if when else None,
                    "link": (it.findtext("link") or "").strip()})
        if len(out) >= limit:
            break
    if dropped:
        log(f"· «{query}» 광고성 제목 {dropped}건 제외")
    return out


def naver(query, limit=8):
    """네이버 검색 API. 키가 없으면 조용히 건너뛴다 — 없어도 브리핑은 나간다."""
    import os
    cid, csec = os.getenv("NAVER_CLIENT_ID"), os.getenv("NAVER_CLIENT_SECRET")
    if not (cid and csec):
        return []
    try:
        r = requests.get("https://openapi.naver.com/v1/search/news.json",
                         params={"query": query, "display": limit, "sort": "date"},
                         headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": csec},
                         timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception as e:
        log(f"· 네이버 «{query}» 실패: {type(e).__name__} {e}")
        return []
    out = []
    for i in items:
        t = _clean(re.sub(r"<[^>]+>", "", i.get("title") or ""))
        if not t or DROP.search(t):
            continue
        out.append({"title": t, "source": "네이버", "published": i.get("pubDate"),
                    "link": i.get("originallink") or i.get("link") or ""})
    return out


def collect(tickers=None, names=None):
    groups = {}
    for label, q in QUERIES_KO:
        groups[label] = rss(q, "ko", "KR", "KR:ko") + naver(q)
    for label, q in QUERIES_EN:
        groups[label] = rss(q, "en-US", "US", "US:en")

    # 종목별은 요청받은 것만. 전 종목을 돌면 수천 번 요청이 된다.
    per_ticker = {}
    for tk in (tickers or []):
        nm = (names or {}).get(tk) or tk
        rows = rss(f"{nm} 주가", "ko", "KR", "KR:ko", limit=6)
        if rows:
            per_ticker[tk] = {"name": nm, "items": rows}

    return {
        "collectedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "groups": groups,
        "tickers": per_ticker,
    }


def summarize(d):
    L = [f"■ 수집 {d['collectedAt']}"]
    for label, rows in d["groups"].items():
        L.append(f"\n◆ {label} — {len(rows)}건")
        for r in rows[:6]:
            src = f" ({r['source']})" if r["source"] else ""
            L.append(f"   · {r['title'][:80]}{src}")
    for tk, v in d["tickers"].items():
        L.append(f"\n● {v['name']} ({tk}) — {len(v['items'])}건")
        for r in v["items"][:4]:
            L.append(f"   · {r['title'][:80]}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="쉼표로 구분한 종목코드")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    names = None
    tks = [t.strip() for t in (a.tickers or "").split(",") if t.strip()]
    if tks:
        try:
            sys.path.insert(0, str(__file__.rsplit("/", 1)[0]))
            from brief_data import load_stocks
            stocks, _, _ = load_stocks()
            names = {s["ticker"]: s.get("name") for s in stocks}
        except Exception as e:
            log(f"· 종목명 조회 실패(코드로 검색): {e}")

    d = collect(tks, names)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    return 0 if any(d["groups"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
