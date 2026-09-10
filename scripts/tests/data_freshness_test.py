#!/usr/bin/env python3
"""시세 신선도 회귀 검사 — 네트워크·pykrx 없이 가짜로 돌린다.

  python3 scripts/tests/data_freshness_test.py

무엇을 못 박아 두나 (2026-09-08~09-10 에 실제로 났던 사고)
  원본(FinanceData KRX 캐시 CSV)이 09-08 부터 404 가 됐다. 수집기는 최대 8일을
  조용히 거슬러 올라가 09-07 CSV 를 읽고서, dataDate 에는 요청 날짜(09-09)를
  찍었다. 그래서 2,686 종목 전부가 09-07 종가인 채로 '09-09 종가'라는 이름을
  달고 사흘간 게시됐다. 아무도 몰랐다 — 라벨이 데이터와 무관하게 만들어졌고,
  결과물을 보고 판정하는 감시선이 없었기 때문이다.

  ① 라벨은 데이터에 각인된 거래일에서만 나온다(build_output).
  ② 캐시는 기본적으로 요청한 거래일 파일만 받는다(max_back=0).
  ③ 캐시가 죽으면 pykrx 로 넘어간다(로그인 조건 제거).
  ④ 장 마감 전에는 당일을 기준일로 삼지 않는다(장중가 종가 오염 차단).
  ⑤ 기준일 판정 불가 시 '오늘'을 지어내지 않는다.
  ⑥ 게시본보다 과거로 되돌아가지 않는다.
  ⑦ 결과물만 보고 낡음을 판정하는 감시선이 따로 있다(check_data_freshness).
"""
import datetime
import io
import json
import os
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# python-dotenv 는 검사 환경에 없다. 수집기가 import 만 하고 쓰지 않으므로 대체한다.
if "dotenv" not in sys.modules:
    _d = types.ModuleType("dotenv")
    _d.load_dotenv = lambda *a, **k: None
    sys.modules["dotenv"] = _d

PASS = FAIL = 0


def ok(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}" + (f"  — {extra}" if extra else ""))


# ── 가짜 KRX 캐시 CSV ────────────────────────────────────────────────────────
def make_csv(n=600, price=1000):
    head = "idx,Code,Name,MarketId,Close,ChagesRatio,Volume,Amount,Marcap,Stocks\n"
    rows = "".join(
        f"{i},{str(100000 + i).zfill(6)},종목{i},STK,{price + i},1.5,1000,100000,1.5,1000000\n"
        for i in range(n)
    )
    return head + rows


AVAILABLE = {}          # {"2026-09-07": csv텍스트}


class FakeResp:
    def __init__(self, status, text=""):
        self.status_code = status
        self.text = text
        self.headers = {"Content-Length": str(len(text))}

    def close(self):
        pass


def fake_get(url, timeout=None, stream=False):
    d = url.rsplit("/", 1)[-1].replace(".csv", "")
    return FakeResp(200, AVAILABLE[d]) if d in AVAILABLE else FakeResp(404, "")


_req = types.ModuleType("requests")
_req.get = fake_get
sys.modules["requests"] = _req

import collect_data as M                          # noqa: E402
import check_data_freshness as F                  # noqa: E402


def set_now(y, mo, d, h):
    M.now_kst = lambda: datetime.datetime(y, mo, d, h, 0, tzinfo=M.KST)


def fake_pykrx(dates_with_data):
    """pykrx 가 데이터를 가진 날짜 집합을 주면 그렇게 답하는 가짜를 심는다."""
    import pandas as pd
    mod = types.ModuleType("pykrx")
    stock = types.SimpleNamespace()

    def ohlcv_by_date(a, b, tk):
        return pd.DataFrame({"종가": [1]}) if a in dates_with_data else pd.DataFrame()

    stock.get_market_ohlcv_by_date = ohlcv_by_date
    mod.stock = stock
    sys.modules["pykrx"] = mod


def drop_pykrx():
    sys.modules.pop("pykrx", None)
    mod = types.ModuleType("pykrx")

    def boom(*a, **k):
        raise RuntimeError("pykrx 죽음")
    mod.__getattr__ = lambda name: boom()
    sys.modules["pykrx"] = mod


print("① 기준일 판정 — 장 마감 전에는 당일을 쓰지 않는다")
fake_pykrx({"20260910", "20260909", "20260907"})
set_now(2026, 9, 10, 13)                                  # 목 13시 — 장중
ok(M.get_latest_trading_date() == "20260909", "장중(13시)에는 전 거래일이 기준일",
   M.get_latest_trading_date())
ok("20260910" not in M.candidate_trading_dates(), "장중에는 당일이 후보에서 빠진다")
set_now(2026, 9, 10, 17)                                  # 17시 — 아직 이르다
ok(M.get_latest_trading_date() == "20260909",
   "마감 직후(17시)에도 당일을 안 쓴다 — pykrx 종가는 저녁에 게시된다",
   M.get_latest_trading_date())
set_now(2026, 9, 10, 18)                                  # 18시 — 기준 시각
ok(M.get_latest_trading_date() == "20260910", "저녁(18시)부터 당일이 기준일",
   M.get_latest_trading_date())
ok(M.MARKET_CLOSE_HOUR == 18, "마감 기준 시각이 저녁으로 잡혀 있다", M.MARKET_CLOSE_HOUR)
set_now(2026, 9, 12, 20)                                  # 토요일 20시
cands = M.candidate_trading_dates(limit=3)
ok(cands == ["20260911", "20260910", "20260909"], "주말은 후보에서 제외", cands)
set_now(2026, 9, 14, 9)                                   # 월요일 09시(장 전)
ok(M.candidate_trading_dates(limit=1) == ["20260911"],
   "월요일 장 전에는 지난 금요일이 최신 후보", M.candidate_trading_dates(limit=1))

print("② 기준일 판정 불가 시 '오늘'을 지어내지 않는다")
drop_pykrx()
AVAILABLE.clear()
set_now(2026, 9, 10, 13)
ok(M.get_latest_trading_date() is None, "두 경로 모두 실패하면 None")

print("③ 두 경로 중 하나만 살아 있어도 기준일을 잡는다")
drop_pykrx()
AVAILABLE.clear()
AVAILABLE["2026-09-09"] = make_csv()
set_now(2026, 9, 10, 13)
ok(M.get_latest_trading_date() == "20260909", "pykrx 죽어도 캐시 CSV 로 판정")

print("④ 캐시는 기본적으로 요청한 거래일 파일만 받는다")
AVAILABLE.clear()
AVAILABLE["2026-09-07"] = make_csv()
res, used = M.collect_krx_cache("20260909")                # max_back 기본 0
ok(res == {} and used is None, "09-09 요청에 09-07 을 몰래 내주지 않는다", f"used={used}")
res, used = M.collect_krx_cache("20260907")
ok(used == "20260907" and len(res) == 600, "요청 날짜가 있으면 정상 수집", f"used={used}")
ok(all(r[M.SRC_DATE_KEY] == "20260907" for r in res.values()),
   "모든 레코드에 실제 거래일이 각인된다")

print("⑤ 과거로 되짚을 때도 라벨은 실제 날짜다")
res, used = M.collect_krx_cache("20260909", max_back=8)
ok(used == "20260907", "되짚어 찾은 날짜를 그대로 돌려준다", f"used={used}")
ok(all(r[M.SRC_DATE_KEY] == "20260907" for r in res.values()),
   "되짚은 데이터도 실제 날짜로 각인")

print("⑥ build_output — 라벨과 데이터가 어긋나면 절대 쓰지 않는다")


def try_build(records, label):
    """임시 디렉터리에서 build_output 을 돌리고 (성공?, 기록된 dataDate) 를 준다."""
    with tempfile.TemporaryDirectory() as td:
        cwd = os.getcwd()
        os.chdir(td)
        try:
            M.build_output({r["ticker"]: r for r in records}, label)
            raw = Path("data/stocks.js").read_text(encoding="utf-8")
            obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return True, obj
        except SystemExit:
            return False, None
        finally:
            os.chdir(cwd)


def rec(tk, src=None, price=1000, mcap=1.5):
    r = {"ticker": tk, "name": f"종목{tk}", "price": price, "mcap": mcap,
         "trading_value": 100, "volume": 10}
    if src:
        r[M.SRC_DATE_KEY] = src
    return r


wrote, _ = try_build([rec("000001", "20260907"), rec("000002", "20260907")], "20260909")
ok(not wrote, "★ 사고 재현: 09-07 데이터에 09-09 라벨 → 쓰지 않고 죽는다")

wrote, obj = try_build([rec("000001", "20260907"), rec("000002", "20260907")], "20260907")
ok(wrote and obj["dataDate"] == "20260907", "라벨이 맞으면 정상 기록",
   obj and obj.get("dataDate"))
ok(wrote and all(M.SRC_DATE_KEY not in s for s in obj["stocks"]),
   "내부 표식은 게시물에 새어 나가지 않는다")

# 수집 경로에 따라 게시물의 모양이 달라지면 안 된다. pykrx 벌크는 KRX 의
# PER·PBR 을 함께 주는데, 그게 새어 나가면 우리가 일부러 가린 PBR 과 충돌한다.
bulky = [dict(rec(str(i).zfill(6), "20260907"),
              per=9.9, pbr=1.1, eps=100, bps=200, div=1.0, roe=0.0,
              rev=0.0, opm=0.0, debt=0.0) for i in range(20)]
wrote, obj = try_build(bulky, "20260907")
leaked = sorted({k for st in obj["stocks"] for k in st} - set(M.PUBLIC_STOCK_FIELDS)) if wrote else ["기록실패"]
ok(wrote and not leaked, "★ 벌크 경로의 KRX PER/PBR 이 게시물로 새지 않는다", leaked)

wrote, _ = try_build([rec("000001"), rec("000002")], "20260909")
ok(not wrote, "각인이 아예 없으면 쓰지 않는다")

wrote, _ = try_build([rec("000001", "20260907"), rec("000002", "20260909")], "20260909")
ok(not wrote, "서로 다른 거래일이 섞이면 쓰지 않는다")

print("⑥-2 병합 경로 — 옛 레코드가 섞여도 새 데이터 날짜로 라벨링된다")
# main() 의 폴백 병합은 기존 stocks.js 레코드(각인 없음)와 새 수집분을 섞는다.
# 실제 운영에서 늘 지나는 길이므로 여기서 못 박는다.
# ⚠ build_output 에는 '출력이 5개 미만이면 가격 0 까지 끌어와 채운다'는 구제
#   분기가 있다. 표본을 3~4개로 잡으면 그 분기가 걸려 실제와 다른 것을 재게 된다.
#   그래서 아래 검사들은 운영 규모(수십 건)로 돌린다.
mixed = [rec(str(i).zfill(6)) for i in range(20)]                    # 각인 없는 옛 레코드
mixed += [rec(str(100 + i).zfill(6), "20260909") for i in range(10)]  # 새 수집분
wrote, obj = try_build(mixed, "20260909")
ok(wrote and obj["dataDate"] == "20260909",
   "각인 없는 옛 레코드가 섞여도 새 거래일로 정상 기록", obj and obj.get("dataDate"))
ok(wrote and len(obj["stocks"]) == 30, "옛 레코드도 그대로 보존된다",
   wrote and len(obj["stocks"]))

print("⑥-3 새 데이터가 한 건도 안 남으면 쓰지 않는다")
# 개별 폴백은 시총을 0 으로 두고 DART 가 채운다. DART 까지 죽으면 새 레코드가
# 시총 필터에 전부 걸려 사라지고 출력이 옛 레코드만 남는다. 예전이라면 그
# 옛 값에 새 날짜를 찍었다.
only_old = [rec(str(i).zfill(6)) for i in range(20)]
fresh_no_mcap = [rec(str(100 + i).zfill(6), "20260909", mcap=0) for i in range(10)]
wrote, _ = try_build(only_old + fresh_no_mcap, "20260909")
ok(not wrote, "★ 새 수집분이 전부 걸러지면 옛 데이터를 새 날짜로 찍지 않는다")

print("⑦ 수집 경로 — 캐시가 죽으면 pykrx 로 넘어간다")
AVAILABLE.clear()
AVAILABLE["2026-09-07"] = make_csv()
calls = []


def bulk_stub(date, names=None):
    calls.append(date)
    return {str(i).zfill(6): dict(rec(str(i).zfill(6), date), **{M.SRC_DATE_KEY: date})
            for i in range(600)}


_real_bulk = M.collect_pykrx_bulk
M.collect_pykrx_bulk = bulk_stub
res, src = M.collect_pykrx("20260909")
ok(calls == ["20260909"], "요청 날짜 캐시가 없으면 pykrx 벌크를 부른다", calls)
ok(src == "20260909" and len(res) == 600, "벌크가 성공하면 그 날짜로 수집", src)

calls.clear()
AVAILABLE["2026-09-09"] = make_csv()
res, src = M.collect_pykrx("20260909")
ok(calls == [] and src == "20260909", "캐시에 요청 날짜가 있으면 pykrx 를 안 부른다", calls)
M.collect_pykrx_bulk = _real_bulk

print("⑧ 감시선 — 결과물만 보고 낡음을 판정한다")
cases = [
    (("20260909", "20260909", "20260910"), F.OK,    "최신 거래일과 일치 → 정상"),
    (("20260909", "20260910", "20260910"), F.HOLD,  "당일 원본 지연 → 보류"),
    (("20260907", "20260909", "20260910"), F.STALE, "★ 사고 상황: 하루 이상 놓침 → 실패"),
    (("20260907", "20260908", "20260909"), F.STALE, "이틀 전 데이터 → 실패"),
    (("",         "20260909", "20260910"), F.STALE, "dataDate 없음 → 실패"),
    (("20260911", "20260909", "20260910"), F.STALE, "미래 날짜 → 실패"),
    (("20260907", None,       "20260910"), F.HOLD,  "최신일 판정 불가 → 보류(오탐 방지)"),
]
for (pub, tgt, today), want, label in cases:
    got, why = F.judge(pub, tgt, today)
    ok(got == want, label, f"기대 {want} / 실제 {got} ({why})")

print("⑧-2 감시선 — valuation 시차는 정상, 역전은 오류")
with tempfile.TemporaryDirectory() as td:
    tdp = Path(td)
    (tdp / "stocks.js").write_text(
        "window.KOS_LIVE_DATA = " + json.dumps(
            {"lastUpdated": "x", "dataDate": "20260909", "stocks": [rec("000001")]}) + ";",
        encoding="utf-8")
    (tdp / "valuation.js").write_text(
        "window.KOS_VALUATION = " + json.dumps(
            {"asOf": "x", "dataDate": "20260907", "stocks": {}}) + ";", encoding="utf-8")
    _S, _V = F.STOCKS, F.VALUATION
    F.STOCKS, F.VALUATION = tdp / "stocks.js", tdp / "valuation.js"
    M.get_latest_trading_date = lambda: "20260909"
    M.today_kst = lambda: datetime.date(2026, 9, 10)

    def set_val(dd):
        (tdp / "valuation.js").write_text(
            "window.KOS_VALUATION = " + json.dumps(
                {"asOf": "x", "dataDate": dd, "stocks": {}}) + ";", encoding="utf-8")

    try:
        # collect_valuation.yml 은 2시간마다 따로 돈다. 뒤처진 상태가 정상이므로
        # 여기서 실패시키면 멀쩡한 날에도 워크플로가 빨갛게 된다.
        ok(F.main() == 0, "★ valuation 이 뒤처진 것은 정상 시차 — 실패시키지 않는다")
        set_val("20260910")
        ok(F.main() == 1, "★ valuation 이 시세보다 미래면 오염 — 실패")
        set_val("20260909")
        ok(F.main() == 0, "둘이 같고 최신이면 통과")
    finally:
        F.STOCKS, F.VALUATION = _S, _V

print("⑨ main() — 게시본보다 과거로 되돌아가지 않는다")
with tempfile.TemporaryDirectory() as td:
    cwd = os.getcwd()
    os.chdir(td)
    try:
        Path("data").mkdir()
        Path("data/stocks.js").write_text(
            "window.KOS_LIVE_DATA = " + json.dumps(
                {"lastUpdated": "x", "dataDate": "20260909",
                 "stocks": [rec("000001")]}) + ";", encoding="utf-8")
        ok(M.load_existing_data_date() == "20260909", "게시본 dataDate 를 읽는다")

        M.get_latest_trading_date = lambda: "20260909"
        M.collect_pykrx = lambda d: ({"000001": rec("000001", "20260907")}, "20260907")
        before = Path("data/stocks.js").read_text(encoding="utf-8")
        M.main()
        after = Path("data/stocks.js").read_text(encoding="utf-8")
        ok(before == after, "★ 과거 데이터를 받아도 기존 게시본을 건드리지 않는다")

        M.get_latest_trading_date = lambda: None
        M.main()
        ok(Path("data/stocks.js").read_text(encoding="utf-8") == before,
           "기준일 판정 불가면 아무것도 쓰지 않는다")
    finally:
        os.chdir(cwd)

print("⑨-2 시장 하나가 통째로 비면 상폐가 아니라 수집 구멍이다")
# 실제로 냈던 사고다. pykrx 벌크를 켜면서 시장 목록에 코넥스를 빼먹었더니,
# 코넥스 108종목이 '수집분에 없는 종목' = 상장폐지로 분류돼 사이트에서 사라졌다.
# 108 은 기존 임계(150개)보다 작아 조용히 넘어갔다.
import inspect                                                        # noqa: E402
src_bulk = inspect.getsource(M.collect_pykrx_bulk)
ok('"KONEX"' in src_bulk and '"코넥스"' in src_bulk,
   "★ 벌크 수집이 코넥스도 훑는다")

# KRX 는 코넥스에 PER·PBR·EPS·BPS 를 공시하지 않는다. pykrx 가 KeyError 를 던지고,
# 시장 루프 전체가 하나의 try 로 묶여 있어 그 하나 때문에 코넥스 108종목이 통째로
# 버려졌다. 게시 필드에도 안 들어가는 보조 값이 시장을 죽이면 안 된다.
def fake_bulk_krx():
    import pandas as pd
    counts = {"KOSPI": 3, "KOSDAQ": 3, "KONEX": 2}
    # 시장별로 티커가 겹치면 안 된다(KOSPI·KOSDAQ 는 앞 세 글자가 같다).
    prefix = {"KOSPI": "P", "KOSDAQ": "Q", "KONEX": "X"}
    def idx(market):
        return [f"{prefix[market]}{i:05d}" for i in range(counts[market])]
    def cap(date, market=None):
        i = idx(market)
        return pd.DataFrame({"시가총액": [1e11] * len(i), "상장주식수": [1000] * len(i)}, index=i)
    def fund(date, market=None):
        if market == "KONEX":            # 실제 KRX 응답을 그대로 흉내낸다
            raise KeyError("None of [Index(['BPS','PER','PBR','EPS','DIV','DPS'])] are in the [columns]")
        i = idx(market)
        return pd.DataFrame({"PER": [1.0] * len(i), "PBR": [1.0] * len(i), "EPS": [1] * len(i),
                             "BPS": [1] * len(i), "DIV": [1.0] * len(i)}, index=i)
    def ohlcv(date, market=None):
        i = idx(market)
        return pd.DataFrame({"종가": [1000] * len(i), "등락률": [1.5] * len(i),
                             "거래량": [10] * len(i), "거래대금": [100] * len(i)}, index=i)
    mod = types.ModuleType("pykrx")
    mod.stock = types.SimpleNamespace(
        get_market_cap_by_ticker=cap, get_market_fundamental_by_ticker=fund,
        get_market_ohlcv_by_ticker=ohlcv, get_market_ticker_name=lambda tk: "이름" + tk)
    sys.modules["pykrx"] = mod

fake_bulk_krx()
got = M.collect_pykrx_bulk("20260909")
konex = [v for v in got.values() if v["market"] == "코넥스"]
ok(len(got) == 8, "세 시장 모두 수집된다", len(got))
ok(len(konex) == 2, "★ 기본지표가 없는 시장도 버려지지 않는다", f"코넥스 {len(konex)}개")
ok(all(v[M.SRC_DATE_KEY] == "20260909" for v in got.values()), "벌크 레코드에도 거래일 각인")

with tempfile.TemporaryDirectory() as td:
    cwd = os.getcwd()
    os.chdir(td)
    try:
        Path("data").mkdir()
        kospi = [dict(rec(str(i).zfill(6)), market="코스피") for i in range(600)]
        konex = [dict(rec(str(700 + i).zfill(6)), market="코넥스") for i in range(108)]
        Path("data/stocks.js").write_text(
            "window.KOS_LIVE_DATA = " + json.dumps(
                {"lastUpdated": "x", "dataDate": "20260907",
                 "stocks": kospi + konex}) + ";", encoding="utf-8")

        fresh = {r["ticker"]: dict(r, **{M.SRC_DATE_KEY: "20260909"}) for r in kospi}
        M.get_latest_trading_date = lambda: "20260909"
        M.collect_pykrx = lambda d: (dict(fresh), "20260909")
        M.enrich_with_dart = lambda r: r          # DART 호출 차단
        M.apply_categories = lambda r: r
        M.main()

        raw = Path("data/stocks.js").read_text(encoding="utf-8")
        got = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        tickers = {s["ticker"] for s in got["stocks"]}
        kept = sum(1 for s in got["stocks"] if s["market"] == "코넥스")
        ok(got["dataDate"] == "20260909", "새 거래일로 갱신은 된다", got["dataDate"])
        ok(kept == 108, "★ 수집 못 한 시장의 종목이 지워지지 않는다", f"코넥스 {kept}개")
        ok(len(tickers) == 708, "전체 종목 수가 유지된다", len(tickers))
    finally:
        os.chdir(cwd)

print("⑪ 두 수집 경로가 같은 결과를 내놓는가 — 차등 대조")
# 이 검사가 없어서 사고가 났다. 운영에서는 캐시 경로만 돌고 있었고 벌크 경로는
# 한 번도 안 돌아본 채로 켜졌다. 필드 하나(name_en)가 없고, 우선주·가격0 을 안
# 거르고, 종목 단위 방어가 없어 값 하나가 NaN 이면 시장이 통째로 날아갔다.
# 같은 시장 데이터를 두 경로에 똑같이 넣고 나온 레코드를 필드 단위로 맞댄다.
#   (코드, 이름, 종가, 등락률, 거래량, 거래대금, 시총(원), 주식수)
ROWS = [
    ("000001", "정상종목",      1000,  1.50, 100, 10000, 1_500_000_000_000, 1000000),
    ("000002", "정상종목우",     900,  0.50,  50,  5000, 1_000_000_000_000,  500000),
    ("000003", "케이비스팩1호",   800,  0.00,  10,  1000,   100_000_000_000,  100000),
    ("000004", "무거래종목",        0,  0.00,   0,     0,                 0,       0),
    ("000005", "정상둘",         2000, -2.00, 200, 20000, 2_500_000_000_000, 2000000),
]

def _namer(rows, boom_ticker):
    """종목명 조회. boom_ticker 는 예외를 던진다 — 개별 호출이라 실제로 잘 끊긴다."""
    table = {r[0]: r[1] for r in rows}
    def get(tk):
        if boom_ticker and tk == boom_ticker:
            raise RuntimeError("KRX 응답 없음")
        return table.get(tk, "")
    return get


AVAILABLE.clear()
head = "idx,Code,Name,MarketId,Close,ChagesRatio,Volume,Amount,Marcap,Stocks\n"
AVAILABLE["2026-09-09"] = head + "".join(
    f"{i},{c},{nm},STK,{px},{ch},{vol},{amt},{mc},{sh}\n"
    for i, (c, nm, px, ch, vol, amt, mc, sh) in enumerate(ROWS)) + "#" * 1100

def fake_krx_from_rows(rows, nan_ticker=None, boom_ticker=None):
    import pandas as pd
    idx = [r[0] for r in rows]
    def pick(j):
        return [(float("nan") if (nan_ticker and r[0] == nan_ticker) else r[j]) for r in rows]
    def cap(date, market=None):
        if market != "KOSPI":
            return pd.DataFrame()
        return pd.DataFrame({"시가총액": pick(6), "상장주식수": pick(7)}, index=idx)
    def ohlcv(date, market=None):
        if market != "KOSPI":
            return pd.DataFrame()
        return pd.DataFrame({"종가": pick(2), "등락률": pick(3),
                             "거래량": pick(4), "거래대금": pick(5)}, index=idx)
    def fund(date, market=None):
        return pd.DataFrame()
    mod = types.ModuleType("pykrx")
    mod.stock = types.SimpleNamespace(
        get_market_cap_by_ticker=cap, get_market_fundamental_by_ticker=fund,
        get_market_ohlcv_by_ticker=ohlcv,
        get_market_ticker_name=_namer(rows, boom_ticker))
    sys.modules["pykrx"] = mod

fake_krx_from_rows(ROWS)
cache_res, _ = M.collect_krx_cache("20260909")
bulk_res = M.collect_pykrx_bulk("20260909")

ok(set(cache_res) == set(bulk_res),
   "★ 두 경로가 고르는 종목이 같다(우선주·스팩·가격0 제외 기준까지)",
   f"캐시 {sorted(cache_res)} / 벌크 {sorted(bulk_res)}")

COMPARE = ("ticker", "name", "name_en", "market", "sector",
           "price", "change", "volume", "trading_value", "mcap", "shares")
mismatch = []
for tk in sorted(set(cache_res) & set(bulk_res)):
    for f in COMPARE:
        a, b = cache_res[tk].get(f, "<없음>"), bulk_res[tk].get(f, "<없음>")
        if a != b:
            mismatch.append(f"{tk}.{f}: 캐시={a!r} 벌크={b!r}")
ok(not mismatch, "★ 게시 대상 필드 값이 두 경로에서 모두 같다", "; ".join(mismatch[:4]))

missing_keys = set(next(iter(cache_res.values()))) - set(next(iter(bulk_res.values())))
ok(not missing_keys, "★ 벌크에 빠진 필드가 없다", sorted(missing_keys))

print("⑪-2 한 종목이 터져도 시장 전체가 날아가지 않는다")
# 실제로 예외가 나는 지점을 골라야 한다. NaN 은 _cell 이 0 으로 바꿔 주므로
# 종목 단위 방어를 지나가지도 않는다 — 그걸로 검사하면 헛돈다(실제로 헛돌았다).
# 종목명 개별 조회는 종목마다 왕복이라 실전에서 가장 잘 끊기는 자리다.
# ⚠ 터뜨릴 종목은 목록의 '맨 앞'이어야 한다. 중간에서 터뜨리면 그 앞 종목들은
#   이미 results 에 들어가 있어서, 가드를 없애도 검사가 통과해 버린다(실제로
#   그렇게 헛돌았다). 가드가 진짜로 지키는 것은 '터진 종목 뒤에 오는 종목들'이다.
fake_krx_from_rows(ROWS, boom_ticker="000001")
broken = M.collect_pykrx_bulk("20260909")          # names 없이 → 개별 조회로 감
ok("000005" in broken, "★ 앞 종목이 터져도 뒤 종목이 살아서 나온다",
   f"수집 {sorted(broken)}")
ok("000001" not in broken, "터진 종목만 빠진다", f"수집 {sorted(broken)}")

fake_krx_from_rows(ROWS, nan_ticker="000005")      # 값이 전부 NaN 인 경우
nanres = M.collect_pykrx_bulk("20260909")
ok("000001" in nanres and "000005" not in nanres,
   "값이 NaN 인 종목은 조용히 제외되고 나머지는 남는다", f"수집 {sorted(nanres)}")

print("⑩ 모듈 표면 — 함수를 통째로 갈아끼우다 상수를 흘리지 않았는지")
# 실제로 한 번 흘렸다. collect_pykrx 를 정규식으로 잘라 바꾸면서 바로 뒤에
# 붙어 있던 CORP_CLS_MARKET 이 같이 지워졌고, 962줄에서 그걸 쓰는 DART 보강이
# NameError 로 죽을 뻔했다. 문법 검사로는 안 잡힌다.
for nm in ("CORP_CLS_MARKET", "KRX_CACHE_URL", "KRX_MKT_ID", "SECTOR_MAP",
           "NAME_EN_OVERRIDE", "SRC_DATE_KEY", "PUBLIC_STOCK_FIELDS",
           "MIN_BULK_TICKERS", "MARKET_CLOSE_HOUR"):
    ok(hasattr(M, nm), f"모듈 상수 {nm} 가 살아 있다")

print()
print(f"통과 {PASS} / 실패 {FAIL}")
sys.exit(1 if FAIL else 0)
