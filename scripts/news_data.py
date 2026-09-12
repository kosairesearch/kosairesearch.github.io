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
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0)"}
TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))
# 요청 사이 최소 간격(초)과 재시도 대기의 기준. 구글 뉴스가 503 을 주는 걸
# 4차 드라이런에서 확인해서 넣었다.
MIN_GAP = float(os.getenv("NEWS_MIN_GAP", "1.2"))
BACKOFF = float(os.getenv("NEWS_BACKOFF", "3"))

# 이 표현이 제목에 있으면 버린다. 투자권유로 읽히는 문장이 브리핑에
# 흘러드는 경로를 여기서 끊는다.
DROP = re.compile(
    r"목표가|목표주가|주가\s*전망|매수\s*추천|매도\s*추천|지금\s*사|사야\s*할|"
    r"급등주|유망주|수익률\s*\d|추천\s*종목|무료\s*상담|리딩|카톡|텔레그램|"
    r"단독\s*공개|비법|대박|긴급\s*속보|세력|작전주|이것만|필독|"
    r"\d+배\s*수익|얼마나\s*될까")

# 검색어는 짧아야 한다. 구글 뉴스는 낱말을 **전부** 만족하는 기사만 준다.
# 처음에 네다섯 낱말로 길게 썼다가 실제로 재 보니 이랬다.
#
#   소비자물가 상승률 생산자물가 통계청   →  0건
#   금융위원회 기획재정부 증시 대책        →  0건
#   oil prices OPEC gold copper          →  0건
#   US economic data inflation consumer  →  0건
#   원달러 환율 마감                      → 12건
#   한국은행 기준금리 금통위               → 10건
#
# 서로 다른 주제를 한 줄에 묶으면(생산자물가+통계청, 금·구리+유가) 그 전부가
# 들어간 기사가 없어서 0이 된다. 두세 낱말로 한 주제만 노린다.
#
# 갈래를 늘릴 때는 '무엇을 쓸지'가 아니라 '무엇을 볼 수 있게 할지'로 생각한다.
# 브리핑은 지난 장을 정리하고 오늘을 준비하게 하는 글이라, 지수와 종목만으로는
# 재료가 모자란다. 한국 거시가 통째로 빠져 있었다 — 금리·물가·수출입이
# 재료에 아예 없어서 쓸 수가 없었다.
QUERIES_KO = [
    ("시황", "코스피 마감 외국인 순매수"),
    ("환율", "원달러 환율 마감"),
    ("국내 금리·통화정책", "한국은행 기준금리 금통위"),
    ("국내 물가·경기", "소비자물가 상승률"),
    ("국내 수출입·무역", "수출 무역수지"),
    ("국내 정책·제도", "금융위원회 증시"),
]
QUERIES_EN = [
    ("미국 지수", "stock market close S&P 500 Nasdaq"),
    ("미국 반도체", "semiconductor stocks Nvidia Broadcom"),
    ("미국 지표", "US inflation data"),
    ("미국 금리·연준", "Federal Reserve rate decision Treasury yields"),
    ("원자재·에너지", "oil prices OPEC"),
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def window_hours(default=54):
    """기사를 몇 시간 전까지 볼 것인가.

    48시간으로 고정했더니 8월 17일(광복절 대체공휴일) 드라이런에서 '시황'이
    0건으로 나왔다. 직전 거래일이 14일 금요일이라 마감 기사가 이미 72시간
    전이었기 때문이다. 그래서 휴장으로 벌어진 만큼 창을 늘린다.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from market_data import open_today
        _, around = open_today()
        if around:
            prev = datetime.date.fromisoformat(around["prev"])
            gap = (datetime.datetime.now(KST).date() - prev).days
            return max(default, gap * 24 + 30)
    except Exception as e:
        log(f"· 조회 창 계산 실패, 기본 {default}시간: {e}")
    return default


_LAST_CALL = [0.0]


def _polite_get(url, tries=3):
    """구글 뉴스는 연달아 때리면 503 을 준다.

    4차 드라이런에서 여덟 쿼리가 전부 503 이었다. 하루에 열 번쯤 요청하는
    건 과하지 않지만, 1초 안에 몰아 치면 막힌다. 그래서 요청 사이에 간격을
    두고, 503·429 는 잠깐 쉬고 다시 시도한다. 그래도 안 되면 포기한다 —
    뉴스가 없으면 브리핑은 '왜'를 안 쓰고 숫자만 쓴다.
    """
    for i in range(tries):
        gap = MIN_GAP - (time.time() - _LAST_CALL[0])
        if gap > 0:
            time.sleep(gap)
        _LAST_CALL[0] = time.time()
        try:
            r = requests.get(url, headers=UA, timeout=TIMEOUT)
            if r.status_code in (429, 503, 502, 500) and i < tries - 1:
                wait = BACKOFF * (2 ** i)
                log(f"· HTTP {r.status_code} — {wait:.0f}초 쉬고 재시도 ({i+1}/{tries-1})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            if i >= tries - 1:
                raise
            wait = BACKOFF * (2 ** i)
            log(f"· {type(e).__name__} — {wait:.0f}초 쉬고 재시도 ({i+1}/{tries-1})")
            time.sleep(wait)
    raise RuntimeError("재시도 소진")


def _clean(s):
    return re.sub(r"\s+", " ", _html.unescape(s or "")).strip()


def rss(query, hl="ko", gl="KR", ceid="KR:ko", limit=12, since_hours=None):
    """구글 뉴스 RSS. 최근 것만, 제목·매체·링크만."""
    since_hours = since_hours or window_hours()
    url = ("https://news.google.com/rss/search?q=" + requests.utils.quote(query)
           + f"&hl={hl}&gl={gl}&ceid={ceid}")
    try:
        root = ET.parse(io.StringIO(_polite_get(url).text)).getroot()
    except Exception as e:
        log(f"· «{query}» 실패: {type(e).__name__} {str(e)[:90]}")
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


# 경보를 두 단으로 나눈다.
#
# 갈래 하나가 비는 것은 조용한 날일 수 있다 — '국내 정책·제도'는 아무
# 일도 없는 날이 있다. 그걸 매번 문제라고 하면 경보가 무뎌지고, 무뎌진
# 경보는 없는 것과 같다.
#
# 그런데 '시황'과 '미국 지수'는 다르다. 장이 열린 다음 날 이게 비는 일은
# 없다. 비었다면 기사가 없는 게 아니라 우리가 막힌 것이다. 그래서 이 둘은
# 하나만 비어도 문제로 본다.
CORE_GROUPS = ("시황", "미국 지수")
# 그 밖에는 전체의 이만큼이 한꺼번에 비면 문제로 본다.
#
# 처음에 3분의 1로 잡았다가 첫 실전에서 바로 울렸다 — 11갈래 중 4갈래가
# 비었는데, 일요일 새벽이라 '국내 정책·제도'나 '원자재' 같은 데 기사가
# 없었을 뿐이다. 그건 막힌 게 아니라 조용한 것이다. 평일마다 울리는
# 경보는 곧 아무도 안 보는 경보가 되고, 그러면 정작 진짜 고장을 놓친다.
#
# 우리가 잡고 싶은 것은 '우리가 막혔다'이고, 그건 대부분이 한꺼번에 비는
# 모습으로 나타난다(실제로 막혔을 때 11갈래 중 11갈래가 비었다).
EMPTY_ALARM = 0.6


def collect(tickers=None, names=None):
    """뉴스 + 건강 기록.

    rss() 는 실패해도 빈 목록을 돌려준다. 그 자체는 맞다 — 뉴스 하나 때문에
    브리핑을 멈출 이유가 없다. 문제는 '못 가져온 것'과 '기사가 없는 것'이
    구분되지 않는다는 점이다. 일정에서 똑같은 병으로 한 번 당했다(9월 11일
    '일정은 FOMC 하나뿐'). 그래서 여기서도 갈래별로 몇 건 왔는지 남긴다.
    """
    groups = {}
    for label, q in QUERIES_KO:
        groups[label] = rss(q, "ko", "KR", "KR:ko") + naver(q)
    for label, q in QUERIES_EN:
        groups[label] = rss(q, "en-US", "US", "US:en")

    empty = [k for k, v in groups.items() if not v]
    problems = []
    core_empty = [k for k in CORE_GROUPS if k in groups and not groups[k]]
    if core_empty:
        problems.append(f"핵심 갈래가 비었다({', '.join(core_empty)}) — "
                        "장이 열린 다음 날 이게 빌 수는 없다. 막힌 것이다")
    floor = max(2, math.ceil(len(groups) * EMPTY_ALARM))
    if groups and len(empty) >= floor:
        problems.append(f"뉴스 {len(groups)}갈래 중 {len(empty)}갈래가 비었다"
                        f"({', '.join(empty)}) — 막혔을 수 있다")
    health = {"ok": not problems, "problems": problems,
              "counts": {k: len(v) for k, v in groups.items()}}

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
        "health": health,
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
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from brief_data import load_stocks
            stocks, _, _ = load_stocks()
            names = {s["ticker"]: s.get("name") for s in stocks}
        except Exception as e:
            log(f"· 종목명 조회 실패(코드로 검색): {e}")

    d = collect(tks, names)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    # 뉴스는 없어도 브리핑이 나가는 값이다(그 문장만 빠진다). 그래서 0 건이어도
    # 실패로 끝내지 않고 경고만 남긴다 — 여기서 1 을 돌려주면 워크플로가
    # 붉어져서, 정작 봐야 할 실패와 구분이 안 된다.
    if not any(d["groups"].values()):
        log("⚠️ 뉴스를 한 건도 받지 못했다 — 브리핑은 숫자만 쓰고 '왜'는 쓰지 않는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
