#!/usr/bin/env python3
"""모닝 브리핑에 필요한 데이터 소스가 실제로 되는지 한 번에 판정한다.

왜 필요한가. 브리핑에 뭘 넣을지는 정했는데, 그 값을 어디서 가져올지가
남았다. 후보는 여럿이고 대부분 무료지만, 막상 돌려 보면 차단되거나
형식이 다르거나 값이 비어 오는 것들이 섞여 있다. 하나씩 코드를 짜서
확인하면 시간이 오래 걸린다. 그래서 후보를 전부 한 파일에 모아 놓고
Actions 에서 한 번 돌려, 되는 것과 안 되는 것을 표로 받는다.

출력은 소스별로 한 줄:
    [OK]   이름   샘플값
    [FAIL] 이름   이유

키가 필요한 소스는 키가 없으면 SKIP 으로 지나간다 — 키를 받기 전에도
나머지 판정은 나와야 한다.

    python scripts/probe_sources.py
"""
import datetime
import io
import os
import sys
import traceback

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI-probe/1.0)"}
TIMEOUT = 20

RESULTS = []


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


# ──────────────────────────────────────────────────────────────
# 1. 국내 — 지수 · 수급 · 휴장일  (pykrx, 키 불필요)
# ──────────────────────────────────────────────────────────────
def _recent_bday():
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


@probe("pykrx · 코스피/코스닥 지수")
def _():
    from pykrx import stock
    end = _recent_bday().strftime("%Y%m%d")
    start = (_recent_bday() - datetime.timedelta(days=10)).strftime("%Y%m%d")
    kospi = stock.get_index_ohlcv(start, end, "1001")
    kosdaq = stock.get_index_ohlcv(start, end, "2001")
    if kospi.empty:
        raise RuntimeError("코스피 지수 빈 응답")
    last = kospi.iloc[-1]
    return (f"코스피 {last['종가']:,.2f} ({kospi.index[-1].date()}) · "
            f"코스닥 {kosdaq.iloc[-1]['종가']:,.2f}")


@probe("pykrx · 투자자별 순매수(외국인/기관)")
def _():
    from pykrx import stock
    end = _recent_bday().strftime("%Y%m%d")
    df = stock.get_market_trading_value_by_investor(end, end, "KOSPI")
    if df.empty:
        raise RuntimeError("빈 응답")
    # 순매수 = 매수 - 매도
    col = "순매수" if "순매수" in df.columns else df.columns[-1]
    foreign = [i for i in df.index if "외국인" in str(i)]
    return f"행 {list(df.index)[:4]} · 외국인 {df.loc[foreign[0], col]:,.0f}" if foreign else str(df.index[:4])


@probe("pykrx · 영업일(휴장일 판정)")
def _():
    from pykrx import stock
    today = datetime.date.today()
    days = stock.get_previous_business_days(year=today.year, month=today.month)
    ds = {d.date() for d in days}
    open_today = today in ds
    return f"{today} 개장={open_today} · 이번달 영업일 {len(ds)}일"


# ──────────────────────────────────────────────────────────────
# 2. 해외 지수 · 환율 · 금리 · 유가
#    후보 A: Stooq (키 불필요, CSV)
# ──────────────────────────────────────────────────────────────
STOOQ = {
    "S&P 500": "^spx", "나스닥": "^ndq", "다우": "^dji",
    "필라델피아 반도체": "^sox", "원/달러": "usdkrw",
    "미 10년물": "10ustby", "WTI": "cl.f", "달러인덱스": "dx.f",
}


def _stooq(sym):
    r = requests.get(f"https://stooq.com/q/d/l/?s={sym}&i=d", headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    txt = r.text.strip()
    if not txt or txt.lower().startswith("no data") or "\n" not in txt:
        raise RuntimeError(f"데이터 없음: {txt[:40]!r}")
    rows = txt.splitlines()
    head, last = rows[0].split(","), rows[-1].split(",")
    close = last[head.index("Close")]
    return f"{last[0]} 종가 {close}"


for _label, _sym in STOOQ.items():
    def _make(label=_label, sym=_sym):
        @probe(f"Stooq · {label}")
        def _():
            return _stooq(sym)
    _make()


# 후보 B: yfinance (야후가 종종 막는다 — 폴백용)
@probe("yfinance · S&P 500")
def _():
    import yfinance as yf
    h = yf.Ticker("^GSPC").history(period="5d")
    if h.empty:
        raise RuntimeError("빈 응답(야후 차단 가능)")
    return f"{h.index[-1].date()} 종가 {h['Close'].iloc[-1]:,.2f}"


@probe("yfinance · 원/달러")
def _():
    import yfinance as yf
    h = yf.Ticker("KRW=X").history(period="5d")
    if h.empty:
        raise RuntimeError("빈 응답")
    return f"{h.index[-1].date()} {h['Close'].iloc[-1]:,.2f}원"


# 후보 C: FRED (미 금리·달러인덱스 원본, 키 무료·발급 필요)
@probe("FRED · 미 10년물 금리", need="FRED_API_KEY")
def _():
    key = os.environ["FRED_API_KEY"]
    r = requests.get("https://api.stlouisfed.org/fred/series/observations",
                     params={"series_id": "DGS10", "api_key": key, "file_type": "json",
                             "sort_order": "desc", "limit": 3},
                     timeout=TIMEOUT)
    r.raise_for_status()
    o = r.json()["observations"][0]
    return f"{o['date']} {o['value']}%"


# 후보 D: 한국은행 ECOS (환율·국고채 원본, 키 무료·발급 필요)
@probe("한국은행 ECOS · 원/달러", need="ECOS_API_KEY")
def _():
    key = os.environ["ECOS_API_KEY"]
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=14)).strftime("%Y%m%d")
    url = f"https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/kr/1/5/731Y001/D/{start}/{end}/0000001"
    r = requests.get(url, timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    rows = j.get("StatisticSearch", {}).get("row")
    if not rows:
        raise RuntimeError(str(j)[:80])
    return f"{rows[-1]['TIME']} {rows[-1]['DATA_VALUE']}원"


# ──────────────────────────────────────────────────────────────
# 3. 뉴스 — '왜 움직였나'
# ──────────────────────────────────────────────────────────────
@probe("구글 뉴스 RSS · 한국어 종목 검색")
def _():
    import xml.etree.ElementTree as ET
    url = ("https://news.google.com/rss/search?q=" + requests.utils.quote("현대차 주가")
           + "&hl=ko&gl=KR&ceid=KR:ko")
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    items = ET.parse(io.StringIO(r.text)).getroot().findall(".//item")
    if not items:
        raise RuntimeError("기사 0건")
    return f"{len(items)}건 · 최신 «{items[0].findtext('title', '')[:45]}»"


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
    return f"{len(items)}건 · 최신 «{items[0]['title'][:45]}»"


# ──────────────────────────────────────────────────────────────
# 4. 일정 — 이번 주에 뭐가 있나
# ──────────────────────────────────────────────────────────────
@probe("연준 · FOMC 연간 일정 페이지")
def _():
    r = requests.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    if "FOMC Meeting" not in r.text and "fomc" not in r.text.lower():
        raise RuntimeError("예상 문구 없음 — 구조 변경")
    return f"HTTP 200 · {len(r.text):,}바이트 (연 8회 일정 파싱 가능)"


@probe("DART · 국내 공시(배당·주총·실적 일정의 원천)", need="DART_API_KEY")
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
    order = {"OK": 0, "SKIP": 1, "FAIL": 2}
    RESULTS.sort(key=lambda r: (order[r[0]], r[1]))
    w = max(len(n) for _, n, _ in RESULTS)
    print("\n" + "=" * 100)
    print("모닝 브리핑 데이터 소스 판정")
    print("=" * 100)
    for status, name, detail in RESULTS:
        mark = {"OK": "  ✅", "SKIP": "  ⏭️ ", "FAIL": "  ❌"}[status]
        print(f"{mark} {name:<{w}}  {detail}")
    n_ok = sum(1 for s, _, _ in RESULTS if s == "OK")
    n_skip = sum(1 for s, _, _ in RESULTS if s == "SKIP")
    n_fail = sum(1 for s, _, _ in RESULTS if s == "FAIL")
    print("=" * 100)
    print(f"되는 것 {n_ok} · 키 없어 건너뜀 {n_skip} · 안 되는 것 {n_fail}")
    print("=" * 100 + "\n")
    # 실패가 있어도 워크플로는 성공으로 끝낸다 — 이건 판정이지 검사가 아니다.
    return 0


if __name__ == "__main__":
    sys.exit(main())
