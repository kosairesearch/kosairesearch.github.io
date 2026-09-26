#!/usr/bin/env python3
"""모닝 브리핑에 필요한 데이터 소스가 실제로 되는지 한 번에 판정한다.

왜 필요한가. 브리핑에 뭘 넣을지는 정했는데, 그 값을 어디서 가져올지가
남았다. 후보는 여럿이고 대부분 무료지만, 막상 돌려 보면 차단되거나
형식이 다르거나 값이 비어 오는 것들이 섞여 있다. 하나씩 코드를 짜서
확인하면 시간이 오래 걸린다. 그래서 후보를 전부 한 파일에 모아 놓고
Actions 에서 한 번 돌려, 되는 것과 안 되는 것을 표로 받는다.

지금까지의 결과
  1차 — Stooq 8개와 pykrx 3개 실패. 사유가 차단이 아니라 KeyError 여서
        호출 방식 문제로 보고 진단을 붙였다.
  2차 — yfinance 로 코스피(^KS11)·코스닥·필라델피아 반도체·미10년물·
        WTI·달러인덱스·원달러가 전부 나왔다. 구글 뉴스는 한국어·영어
        모두 100건. Stooq 는 자바스크립트 봇 차단 페이지를 돌려주므로
        버린다. pykrx 는 KRX 응답 형식이 바뀐 듯 전부 죽었다.
  3차(지금) — 남은 세 구멍만 판정한다.
        ① 휴장일: pykrx 가 죽어서 대체 수단이 필요하다. 내 기억으로
           하드코딩하면 지금 고치려는 버그를 다시 만든다.
        ② 투자자별 순매수(외국인 3조): pykrx 말고 어디서 받나.
        ③ FOMC 일정: HTTP 200 인데 내 정규식이 안 맞았다.

    python scripts/probe_sources.py          # 판정표
    python scripts/probe_sources.py --raw    # 판정표 + 진단
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
    def deco(fn):
        if need and not os.getenv(need):
            RESULTS.append(("SKIP", name, f"{need} 없음 — 키 발급 후 재실행"))
            return fn
        try:
            RESULTS.append(("OK", name, str(fn())[:120]))
        except Exception as e:
            line = traceback.format_exc().strip().splitlines()[-1]
            RESULTS.append(("FAIL", name, f"{type(e).__name__}: {str(e)[:90] or line[:90]}"))
        return fn
    return deco


def note(title, body):
    NOTES.append((title, body))


def _recent_bday():
    d = datetime.date.today()
    while d.weekday() >= 5:
        d -= datetime.timedelta(days=1)
    return d


# ══════════════════════════════════════════════════════════════
# ① 휴장일 — 오늘 장이 열리는지. 없으면 브리핑을 내면 안 되는 값.
#    07:30 에 판정해야 하므로 '지난 시세가 있나'로는 알 수 없다.
# ══════════════════════════════════════════════════════════════

# 이 날짜들이 정답이다. 8월 17일은 광복절(8/15 토)의 대체공휴일이고,
# 8월 14일과 18일은 개장일이다. 어떤 후보든 이 셋을 맞혀야 쓸 수 있다.
TRUTH = {
    datetime.date(2026, 8, 14): True,    # 금 · 개장
    datetime.date(2026, 8, 17): False,   # 월 · 광복절 대체공휴일
    datetime.date(2026, 8, 18): True,    # 화 · 개장
}


def _verdict(is_open):
    """후보 판정기를 정답 셋에 대고 채점한다."""
    got = {d: is_open(d) for d in TRUTH}
    wrong = {d: (got[d], TRUTH[d]) for d in TRUTH if got[d] != TRUTH[d]}
    if wrong:
        raise RuntimeError("오답 " + ", ".join(
            f"{d}: 판정={g} 정답={t}" for d, (g, t) in wrong.items()))
    return " · ".join(f"{d.strftime('%m/%d')}={'개장' if got[d] else '휴장'}" for d in sorted(got))


@probe("휴장일 · holidays 패키지(오프라인·무키)")
def _():
    import holidays as H
    kr = H.country_holidays("KR", years=[2026, 2027])
    note("holidays · 2026년 8월 항목",
         str({str(k): v for k, v in sorted(kr.items()) if k.year == 2026 and k.month == 8}))
    note("holidays 패키지 버전", getattr(H, "__version__", "?"))

    def is_open(d):
        return d.weekday() < 5 and d not in kr
    return _verdict(is_open)


@probe("휴장일 · 한국천문연구원 특일정보 API", need="HOLIDAY_API_KEY")
def _():
    key = os.environ["HOLIDAY_API_KEY"]
    r = requests.get("http://apis.data.go.kr/B090041/openapi/service/SpcdeInfoService/getRestDeInfo",
                     params={"serviceKey": key, "solYear": 2026, "solMonth": "08",
                             "_type": "json", "numOfRows": 30},
                     timeout=TIMEOUT)
    r.raise_for_status()
    body = r.json()["response"]["body"]
    items = body.get("items") or {}
    rows = items.get("item") or []
    rows = rows if isinstance(rows, list) else [rows]
    note("특일정보 2026-08", str([(i.get("locdate"), i.get("dateName")) for i in rows]))
    days = {str(i["locdate"]) for i in rows}

    def is_open(d):
        return d.weekday() < 5 and d.strftime("%Y%m%d") not in days
    return _verdict(is_open)


@probe("휴장일 · KRX 휴장일 조회")
def _():
    r = requests.post("http://open.krx.co.kr/contents/OPN/99/OPN99000001.jspx",
                      headers=UA, timeout=TIMEOUT)
    note("KRX 휴장일 페이지", f"HTTP {r.status_code} · {r.text[:120]!r}")
    raise RuntimeError(f"HTTP {r.status_code} · 형식 확인용")


# ══════════════════════════════════════════════════════════════
# ② 투자자별 순매수 — '외국인 3조 순매수'. pykrx 가 죽었다.
# ══════════════════════════════════════════════════════════════
@probe("수급 · pykrx 재확인(컬럼 진단)")
def _():
    from pykrx import stock
    end = _recent_bday().strftime("%Y%m%d")
    df = stock.get_market_trading_value_by_investor(end, end, "KOSPI")
    note("pykrx 수급 데이터프레임", f"columns={list(df.columns)} · index={list(df.index)}")
    return f"컬럼 {list(df.columns)}"


@probe("수급 · KRX 통계 JSON (투자자별 거래실적)")
def _():
    d = _recent_bday().strftime("%Y%m%d")
    r = requests.post("http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd",
                      data={"bld": "dbms/MDC/STAT/standard/MDCSTAT02203",
                            "mktId": "STK", "trdVolVal": "2", "askBid": "3",
                            "strtDd": d, "endDd": d},
                      headers={**UA, "Referer": "http://data.krx.co.kr/contents/MDC/MDI/mdiLoader/index.cmd"},
                      timeout=TIMEOUT)
    note("KRX JSON 응답", f"HTTP {r.status_code} · {r.text[:180]!r}")
    r.raise_for_status()
    j = r.json()
    rows = j.get("output") or j.get("OutBlock_1") or []
    if not rows:
        raise RuntimeError(f"빈 응답 · 키={list(j.keys())}")
    note("KRX JSON 첫 행", str(rows[0])[:300])
    return f"{len(rows)}행 · 키 {list(rows[0].keys())[:5]}"


@probe("수급 · 네이버 금융 투자자별 매매동향")
def _():
    import re as _re
    r = requests.get("https://finance.naver.com/sise/sise_deal_rank.naver?investor_gubun=1000",
                     headers=UA, timeout=TIMEOUT)
    r.encoding = "euc-kr"
    ok = "투자자" in r.text or "순매수" in r.text
    note("네이버 금융 수급 페이지", f"HTTP {r.status_code} · 한글 렌더={ok} · {len(r.text):,}바이트")
    if not ok:
        raise RuntimeError(f"HTTP {r.status_code} · 예상 문구 없음")
    return f"HTTP 200 · {len(r.text):,}바이트 (파싱 가능)"


# ══════════════════════════════════════════════════════════════
# ③ FOMC 일정 — HTTP 200 인데 파서가 틀렸다. 실제 마크업을 본다.
# ══════════════════════════════════════════════════════════════
@probe("일정 · FOMC 페이지 파서")
def _():
    import re as _re
    r = requests.get("https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                     headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    t = r.text
    pats = {
        "fomc-tabs 연도": r'id="fomc-(\d{4})"',
        "panel h4 연도": r"<h4[^>]*>\s*(\d{4})\s+FOMC",
        "그냥 4자리연도+FOMC": r"(\d{4})\s+FOMC\s+Meetings",
        "월 이름 셀": r'class="fomc-meeting__month[^"]*"[^>]*>\s*<strong>([A-Z][a-z]+)',
        "날짜 셀": r'class="fomc-meeting__date[^"]*"[^>]*>\s*([\d\-–\s]+)',
        "minutes 링크": r"(minutes\d{8})",
    }
    found = {k: (_re.findall(p, t)[:6] or "없음") for k, p in pats.items()}
    for k, v in found.items():
        note(f"FOMC 패턴 · {k}", str(v))
    hit = [k for k, v in found.items() if v != "없음"]
    if not hit:
        note("FOMC 원문 일부", t[t.find("FOMC Meeting"):t.find("FOMC Meeting") + 400].replace("\n", " "))
        raise RuntimeError("어떤 패턴도 안 맞음 — 원문 진단 참고")
    return f"맞은 패턴 {len(hit)}/{len(pats)}: {', '.join(hit)}"


# ══════════════════════════════════════════════════════════════
# 이미 확인된 것들 — 회귀 확인용으로 가볍게 유지
# ══════════════════════════════════════════════════════════════
YF = {"S&P 500": "^GSPC", "나스닥": "^IXIC", "필라델피아 반도체": "^SOX",
      "원/달러": "KRW=X", "코스피": "^KS11", "코스닥": "^KQ11", "미 10년물": "^TNX"}


def _yf(sym):
    import yfinance as yf
    h = yf.Ticker(sym).history(period="7d")
    if h is None or h.empty:
        raise RuntimeError("빈 응답")
    last = h["Close"].iloc[-1]
    prev = h["Close"].iloc[-2] if len(h) > 1 else None
    chg = f" ({(last/prev-1)*100:+.2f}%)" if prev is not None else ""
    return f"{h.index[-1].date()} {last:,.2f}{chg}"


for _l, _s in YF.items():
    def _mk(label=_l, sym=_s):
        @probe(f"yfinance · {label}")
        def _():
            return _yf(sym)
    _mk()


@probe("구글 뉴스 · 한국어 시황")
def _():
    import xml.etree.ElementTree as ET
    url = ("https://news.google.com/rss/search?q="
           + requests.utils.quote("코스피 마감 외국인") + "&hl=ko&gl=KR&ceid=KR:ko")
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    items = ET.parse(io.StringIO(r.text)).getroot().findall(".//item")
    if not items:
        raise RuntimeError("기사 0건")
    return f"{len(items)}건 · «{items[0].findtext('title', '')[:52]}»"


@probe("DART · 국내 공시", need="DART_API_KEY")
def _():
    end = datetime.date.today().strftime("%Y%m%d")
    start = (datetime.date.today() - datetime.timedelta(days=5)).strftime("%Y%m%d")
    r = requests.get("https://opendart.fss.or.kr/api/list.json",
                     params={"crtfc_key": os.environ["DART_API_KEY"], "bgn_de": start,
                             "end_de": end, "page_count": 5, "corp_cls": "Y"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    j = r.json()
    if j.get("status") != "000":
        raise RuntimeError(f"{j.get('status')} {j.get('message')}")
    return f"{j.get('total_count')}건"


# ══════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", action="store_true")
    ap.parse_args()

    order = {"OK": 0, "SKIP": 1, "FAIL": 2}
    RESULTS.sort(key=lambda r: (order[r[0]], r[1]))
    w = max(len(n) for _, n, _ in RESULTS)
    print("\n" + "=" * 108)
    print("모닝 브리핑 데이터 소스 판정 (3차 — 남은 세 구멍)")
    print("=" * 108)
    for st, name, detail in RESULTS:
        print(f"{{'OK':'  ✅','SKIP':'  ⏭️ ','FAIL':'  ❌'}}"[0] if False else
              {"OK": "  ✅", "SKIP": "  ⏭️ ", "FAIL": "  ❌"}[st]
              + f" {name:<{w}}  {detail}")
    c = {k: sum(1 for s, _, _ in RESULTS if s == k) for k in ("OK", "SKIP", "FAIL")}
    print("=" * 108)
    print(f"되는 것 {c['OK']} · 건너뜀 {c['SKIP']} · 안 되는 것 {c['FAIL']}")
    print("=" * 108)

    if NOTES:
        print("\n진단")
        print("-" * 108)
        for t, b in NOTES:
            print(f"  · {t}\n      {b}")
        print("-" * 108 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
