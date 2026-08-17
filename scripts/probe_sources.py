#!/usr/bin/env python3
"""모닝 브리핑에 필요한 데이터 소스가 실제로 되는지 한 번에 판정한다.

왜 필요한가. 브리핑에 뭘 넣을지는 정했는데, 그 값을 어디서 가져올지가
남았다. 후보는 여럿이고 대부분 무료지만, 막상 돌려 보면 차단되거나
형식이 다르거나 값이 비어 오는 것들이 섞여 있다. 하나씩 코드를 짜서
확인하면 시간이 오래 걸린다. 그래서 후보를 전부 한 파일에 모아 놓고
Actions 에서 한 번 돌려, 되는 것과 안 되는 것을 표로 받는다.

1차 실행에서 pykrx 와 Stooq 가 전부 실패했다. 다만 실패 사유가
'차단'이 아니라 KeyError/ValueError 였다 — 소스가 막힌 게 아니라
호출 방식이나 응답 형식을 내가 잘못 안 것이다. 그래서 이 파일은 판정만
하지 않고, 실패한 소스의 **실제 응답 모양**까지 같이 찍는다. 한 번 더
돌려서 맞는 사용법을 확정하려는 것이다(--raw).

    python scripts/probe_sources.py          # 판정표
    python scripts/probe_sources.py --raw    # 판정표 + 실패 원인 진단
"""
import argparse
import datetime
import io
import os
import sys
import traceback

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI-probe/1.0)"}
TIMEOUT = 20

RESULTS = []
NOTES = []


def probe(name, need=None):
    """판정 하나를 등록하는 데코레이터. need 는 필요한 환경변수 이름."""
    def deco(fn):
        if need and not os.getenv(need):
            RESULTS.append(("SKIP", name, f"{need} 없음 — 키 발급 후 재실행"))
            return fn
        try:
            sample = fn()
            RESULTS.append(("OK", name, str(sample)[:110]))
        except Exception as e:
            line = traceback.format_exc().strip().splitlines()[-1]
            RESULTS.append(("FAIL", name, f"{type(e).__name__}: {str(e)[:80] or line[:80]}"))
        return fn
    return deco


def note(title, body):
    NOTES.append((title, body))


def _recent_bday():
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


# ──────────────────────────────────────────────────────────────
# 1. 해외 + 국내 지수 · 환율 · 금리 · 유가  — yfinance
#    1차에서 유일하게 통과한 경로. 코스피까지 여기서 되면 pykrx 의존이 준다.
# ──────────────────────────────────────────────────────────────
YF = {
    "S&P 500": "^GSPC", "나스닥": "^IXIC", "다우": "^DJI",
    "필라델피아 반도체": "^SOX", "미 10년물": "^TNX",
    "WTI": "CL=F", "달러인덱스": "DX-Y.NYB", "원/달러": "KRW=X",
    "코스피": "^KS11", "코스닥": "^KQ11",
}


def _yf(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="7d")
    if h is None or h.empty:
        raise RuntimeError("빈 응답")
    last, prev = h["Close"].iloc[-1], (h["Close"].iloc[-2] if len(h) > 1 else None)
    chg = f" ({(last/prev-1)*100:+.2f}%)" if prev else ""
    return f"{h.index[-1].date()} {last:,.2f}{chg}"


for _label, _sym in YF.items():
    def _mk(label=_label, sym=_sym):
        @probe(f"yfinance · {label}")
        def _():
            return _yf(sym)
    _mk()


# ──────────────────────────────────────────────────────────────
# 2. 국내 — 지수 · 수급 · 휴장일 (pykrx)
#    1차 실패는 전부 내 호출 방식 문제로 보인다. 변형을 여러 개 시도한다.
# ──────────────────────────────────────────────────────────────
@probe("pykrx · 영업일(휴장일 판정)")
def _():
    from pykrx import stock
    today = datetime.date.today()
    errs = []
    # 후보 A: get_previous_business_days(year=, month=)
    try:
        days = stock.get_previous_business_days(year=today.year, month=today.month)
        ds = {getattr(d, "date", lambda: d)() for d in days}
        return f"[A] 이번달 영업일 {len(ds)}일 · 오늘 개장={today in ds}"
    except Exception as e:
        errs.append(f"A {type(e).__name__}: {e}")
    # 후보 B: 지수 시세가 나오는 날 = 개장일
    try:
        start = (today - datetime.timedelta(days=20)).strftime("%Y%m%d")
        df = stock.get_index_ohlcv(start, today.strftime("%Y%m%d"), "1001")
        ds = {i.date() for i in df.index}
        return f"[B] 최근 20일 중 개장 {len(ds)}일 · 오늘 개장={today in ds}"
    except Exception as e:
        errs.append(f"B {type(e).__name__}: {e}")
    raise RuntimeError(" / ".join(errs))


@probe("pykrx · 코스피/코스닥 지수")
def _():
    from pykrx import stock
    end = _recent_bday().strftime("%Y%m%d")
    start = (_recent_bday() - datetime.timedelta(days=10)).strftime("%Y%m%d")
    errs = []
    for label, fn in (("get_index_ohlcv", lambda: stock.get_index_ohlcv(start, end, "1001")),
                      ("get_index_ohlcv_by_date",
                       lambda: getattr(stock, "get_index_ohlcv_by_date")(start, end, "1001"))):
        try:
            df = fn()
            if df is None or df.empty:
                errs.append(f"{label}: 빈 응답"); continue
            note(f"pykrx {label} 컬럼", f"{list(df.columns)} · index={df.index[-1]}")
            close = df.iloc[-1][[c for c in df.columns if "종가" in str(c) or "Close" in str(c)][0]]
            return f"[{label}] 코스피 {close:,.2f} ({df.index[-1]})"
        except Exception as e:
            errs.append(f"{label}: {type(e).__name__} {e}")
    raise RuntimeError(" / ".join(errs)[:150])


@probe("pykrx · 투자자별 순매수(외국인/기관)")
def _():
    from pykrx import stock
    end = _recent_bday().strftime("%Y%m%d")
    errs = []
    for label, fn in (
        ("by_investor(KOSPI)",
         lambda: stock.get_market_trading_value_by_investor(end, end, "KOSPI")),
        ("by_date(KOSPI)",
         lambda: getattr(stock, "get_market_trading_value_by_date")(end, end, "KOSPI")),
    ):
        try:
            df = fn()
            if df is None or df.empty:
                errs.append(f"{label}: 빈 응답"); continue
            note(f"pykrx {label} 모양", f"columns={list(df.columns)} · index={list(df.index)[:8]}")
            return f"[{label}] 컬럼 {list(df.columns)[:4]}"
        except Exception as e:
            errs.append(f"{label}: {type(e).__name__} {e}")
    raise RuntimeError(" / ".join(errs)[:150])


@probe("pykrx · 버전/함수 목록")
def _():
    import pykrx
    from pykrx import stock
    v = getattr(pykrx, "__version__", "?")
    fns = [f for f in dir(stock) if f.startswith("get_index") or "business" in f
           or "investor" in f]
    note("pykrx 관련 함수", ", ".join(fns))
    return f"버전 {v} · 관련 함수 {len(fns)}개"


# ──────────────────────────────────────────────────────────────
# 3. Stooq — 1차에서 헤더 파싱 실패. 원문을 찍어 형식을 확인한다.
# ──────────────────────────────────────────────────────────────
@probe("Stooq · 응답 형식 확인 (^spx)")
def _():
    r = requests.get("https://stooq.com/q/d/l/?s=%5Espx&i=d", headers=UA, timeout=TIMEOUT)
    head = r.text[:200].replace("\n", " ⏎ ")
    note("Stooq 원문 앞 200자", f"HTTP {r.status_code} · {head!r}")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    if "Close" not in r.text.splitlines()[0]:
        raise RuntimeError(f"헤더에 Close 없음: {r.text.splitlines()[0][:60]!r}")
    rows = r.text.strip().splitlines()
    h = rows[0].split(",")
    return f"{rows[-1].split(',')[0]} 종가 {rows[-1].split(',')[h.index('Close')]}"


# ──────────────────────────────────────────────────────────────
# 4. 뉴스 — 1차에서 구글 RSS 한국어가 통과했다. 범위를 넓혀 확인한다.
# ──────────────────────────────────────────────────────────────
def _gnews(q, hl, gl, ceid):
    import xml.etree.ElementTree as ET
    url = (f"https://news.google.com/rss/search?q={requests.utils.quote(q)}"
           f"&hl={hl}&gl={gl}&ceid={ceid}")
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    items = ET.parse(io.StringIO(r.text)).getroot().findall(".//item")
    if not items:
        raise RuntimeError("기사 0건")
    return f"{len(items)}건 · «{items[0].findtext('title', '')[:50]}»"


@probe("구글 뉴스 · 한국어 종목")
def _():
    return _gnews("현대차 주가", "ko", "KR", "KR:ko")


@probe("구글 뉴스 · 한국어 시황")
def _():
    return _gnews("코스피 마감 외국인", "ko", "KR", "KR:ko")


@probe("구글 뉴스 · 미국 지수(영어)")
def _():
    return _gnews("stock market close S&P 500", "en-US", "US", "US:en")


@probe("구글 뉴스 · 미국 개별종목(영어)")
def _():
    return _gnews("Nvidia stock", "en-US", "US", "US:en")


@probe("네이버 검색 API · 뉴스", need="NAVER_CLIENT_ID")
def _():
    r = requests.get("https://openapi.naver.com/v1/search/news.json",
                     params={"query": "현대차", "display": 3, "sort": "date"},
                     headers={"X-Naver-Client-Id": os.environ["NAVER_CLIENT_ID"],
                              "X-Naver-Client-Secret": os.environ.get("NAVER_CLIENT_SECRET", "")},
                     timeout=TIMEOUT)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        raise RuntimeError("기사 0건")
    return f"{len(items)}건 · «{items[0]['title'][:45]}»"


# ──────────────────────────────────────────────────────────────
# 5. 일정
# ──────────────────────────────────────────────────────────────
@probe("연준 · FOMC 연간 일정 페이지")
def _():
    import re as _re
    r = requests.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    yrs = sorted(set(_re.findall(r"panel-heading[^>]*>\s*(\d{4})", r.text)))
    note("FOMC 페이지에서 찾은 연도", str(yrs) or "(패턴 불일치 — 파서 조정 필요)")
    return f"HTTP 200 · {len(r.text):,}바이트 · 연도 {yrs or '미검출'}"


@probe("DART · 국내 공시", need="DART_API_KEY")
def _():
    key = os.environ["DART_API_KEY"]
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=5)).strftime("%Y%m%d")
    r = requests.get("https://opendart.fss.or.kr/api/list.json",
                     params={"crtfc_key": key, "bgn_de": start, "end_de": end,
                             "page_count": 5, "corp_cls": "Y"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "000":
        raise RuntimeError(f"{j.get('status')} {j.get('message')}")
    return f"{j.get('total_count')}건 · 예: {j['list'][0]['report_nm'][:40]}"


# ──────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true", help="실패 원인 진단까지 출력")
    a = ap.parse_args()

    order = {"OK": 0, "SKIP": 1, "FAIL": 2}
    RESULTS.sort(key=lambda r: (order[r[0]], r[1]))
    w = max(len(n) for _, n, _ in RESULTS)
    print("\n" + "=" * 104)
    print("모닝 브리핑 데이터 소스 판정")
    print("=" * 104)
    for status, name, detail in RESULTS:
        mark = {"OK": "  ✅", "SKIP": "  ⏭️ ", "FAIL": "  ❌"}[status]
        print(f"{mark} {name:<{w}}  {detail}")
    n_ok = sum(1 for s, _, _ in RESULTS if s == "OK")
    n_skip = sum(1 for s, _, _ in RESULTS if s == "SKIP")
    n_fail = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    print("=" * 104)
    print(f"되는 것 {n_ok} · 키 없어 건너뜀 {n_skip} · 안 되는 것 {n_fail}")
    print("=" * 104)

    if NOTES:
        print("\n진단 — 실패한 소스가 실제로 무엇을 돌려줬나")
        print("-" * 104)
        for title, body in NOTES:
            print(f"  · {title}\n      {body}")
        print("-" * 104 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
