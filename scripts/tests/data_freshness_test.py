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
set_now(2026, 9, 10, 16)                                  # 16시 — 마감 후
ok(M.get_latest_trading_date() == "20260910", "마감 후(16시)에는 당일이 기준일",
   M.get_latest_trading_date())
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
