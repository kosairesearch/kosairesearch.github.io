#!/usr/bin/env python3
"""리포트 v2 파이프라인 회귀 검사 — DART·Anthropic 없이 가짜로 돌린다.

  python3 scripts/tests/reports_pipeline_test.py

무엇을 고정해 두나 (전부 2026-09-05 에 실제로 났던 결함이다)
  ① 보해양조   5:1 액면병합. 공시 EPS(옛 주식수 기준)를 버리고 순이익÷주식수를 택한
               뒤, ROE 폴백 블록이 그 버린 공시값으로 TTM 순이익을 덮어써 같은
               리포트 안에서 EPS 와 TTM 이 5배 어긋났다.
  ② 지엘팜텍   순이익÷주식수 -6.9 를 int() 로 잘라 -6. 거꾸로 곱하면 13% 어긋난다.
  ③ 한울앤제주 DART 가 지배지분 칸에 자본총계를 적었다(비지배 2억 별도). 항등식 위반.
  ④ DART 한도  라이브러리는 status 020 을 print 하고 빈 표를 돌려준다. '재무제표
               없음' 과 구분이 안 돼 한 run 의 종목 전부가 생성 불가로 영구 기록됐다.
  ⑤ 배치 상태  주문마다 파일 하나. 회수는 파일별로 한 번. 진행 중 종목은 재주문 금지.
  ⑥ 대상 선정  갱신 기준일·hold·fail·skip·진행 중 배치를 생성기와 워치독이 같은 규칙으로 본다.
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
for name in ("OpenDartReader",):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)

import pandas as PD                   # noqa: E402  — 아래 날짜 패치보다 먼저 들여와야 한다
import _reports_state as S            # noqa: E402
import check_valuation as C           # noqa: E402
import generate_reports_v2 as M       # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


# ── 상태 파일을 임시 폴더로 돌린다 ───────────────────────────────────────
TMP = Path(tempfile.mkdtemp(prefix="kosai_pipe_"))
DATA = TMP / "data"
DATA.mkdir()
for attr in ("OUT_DIR", "SKIP_DIR", "HOLD_DIR", "FAIL_DIR", "BATCH_DIR"):
    setattr(S, attr, DATA / getattr(S, attr).name)
S.SKIP_LEGACY = DATA / "reports_v2_skip.txt"
S.LEGACY_STATE = DATA / "batch_state_v2.json"
S.REFRESH_FILE = DATA / "reports_v2_refresh"
S.PAUSE_FILE = DATA / "reports_paused"
S.QUOTA_FILE = DATA / "dart_quota_exhausted"
# 새 전역 마커를 여기 안 넣으면 검사가 진짜 저장소의 파일을 읽는다. 실제로
# 그랬다 — 잔액 마커가 저장소에 생긴 날 ⑥ 주문 검사가 통째로 무너졌다.
S.CREDIT_FILE = DATA / "anthropic_credit_exhausted"
S.STOCKS_JS = DATA / "stocks.js"
M.OUT_DIR = S.OUT_DIR
M.BATCH_DIR = S.BATCH_DIR
M.PAUSE_FILE = S.PAUSE_FILE
M.SKIP_DIR = S.SKIP_DIR
M.time.sleep = lambda *_: None
M.ROOT = TMP

STOCKS = [
    {"ticker": "005930", "name": "삼성전자", "price": 281500, "mcap": 1645.7, "shares": 5846278608, "market": "코스피", "sector": "반도체"},
    {"ticker": "000890", "name": "보해양조", "price": 1406, "mcap": 0.0388, "shares": 27624025, "market": "코스피", "sector": "식음료"},
    {"ticker": "204840", "name": "지엘팜텍", "price": 5300, "mcap": 0.0822, "shares": 15509801, "market": "코스닥", "sector": "제약"},
    {"ticker": "276730", "name": "한울앤제주", "price": 1309, "mcap": 0.0309, "shares": 23607980, "market": "코스닥", "sector": "식음료"},
    {"ticker": "000020", "name": "동화약품", "price": 9000, "mcap": 0.25, "shares": 27931470, "market": "코스피", "sector": "제약"},
    {"ticker": "000040", "name": "KR모터스", "price": 500, "mcap": 0.05, "shares": 100000000, "market": "코스피", "sector": "자동차"},
]
S.STOCKS_JS.write_text("window.KOS_LIVE_DATA = " + json.dumps(
    {"dataDate": "20260904", "stocks": STOCKS}, ensure_ascii=False) + ";", encoding="utf-8")
M.g.load_stocks = lambda: {"dataDate": "20260904", "stocks": STOCKS}


def write_report(tk, date):
    S.OUT_DIR.mkdir(exist_ok=True)
    (S.OUT_DIR / f"{tk}.json").write_text(json.dumps(
        {"ticker": tk, "title": {"ko": "t", "en": "t"}, "reportDate": date, "v": 2}), encoding="utf-8")


UNIT = 1
CUR = 2026
REAL_DATE = datetime.date          # M.datetime 은 같은 모듈 객체라 아래 패치가 여기도 미친다
M.datetime.date = type("D", (), {"today": staticmethod(lambda: REAL_DATE(CUR, 9, 5)),
                                 "fromisoformat": staticmethod(REAL_DATE.fromisoformat)})


def fin_factory(annual_rows, quarters=None, ccy="KRW"):
    """annual_rows: {year: dict(rev, op, np, np_owner, np_nci, equity, equity_owner, equity_nci, liab, eps)}
    quarters: {(year, code): 누적 dict(np_owner, np, eps, equity_owner, equity, equity_nci)}"""
    def _fin(dart, ticker, year, reprt):
        if reprt == "11011":
            r = annual_rows.get(year)
            if not r:
                return None
            out = {"_fs": "CFS", "_reprt": reprt, "_ccy": ccy}
            prev = r.get("_prev") or {}
            for k in ("rev", "op", "np", "np_owner", "np_nci", "cfo"):
                if r.get(k) is not None:
                    out[k] = {"amt": r[k], "add": r[k], "prv": prev.get(k)}
            for k in ("equity", "equity_owner", "equity_nci", "liab", "assets"):
                if r.get(k) is not None:
                    out[k] = {"amt": r[k], "add": None, "prv": prev.get(k)}
            if r.get("eps") is not None:
                out["eps_basic"] = {"amt": r["eps"], "add": r["eps"], "prv": prev.get("eps")}
            return out
        q = (quarters or {}).get((year, reprt))
        if not q:
            return None
        out = {"_fs": "CFS", "_reprt": reprt, "_ccy": ccy}
        for k in ("rev", "op", "np", "np_owner", "np_nci"):
            if q.get(k) is not None:
                out[k] = {"amt": q[k], "add": q[k]}
        for k in ("equity", "equity_owner", "equity_nci", "liab"):
            if q.get(k) is not None:
                out[k] = {"amt": q[k], "add": None}
        if q.get("eps") is not None:
            out["eps_basic"] = {"amt": q["eps"], "add": q["eps"]}
        return out
    return _fin


def run_quant(stock, annual_rows, quarters=None, total_shares=None):
    M._fin_all = fin_factory(annual_rows, quarters)
    M.dart_total_shares = lambda d, t: total_shares
    M.dart_dps = lambda d, t: 0.0
    M.g._safe_finstate = lambda *a, **k: None
    M.g._extract_fin = lambda *a, **k: None
    return M.collect_quant(None, stock["ticker"], None, stock)


# ═══ ① 보해양조 — 액면병합 뒤 EPS 와 TTM 이 서로 맞아야 한다 ═══════════════
print("① 보해양조 — 액면병합(5:1) 뒤 EPS·TTM 정합")
st = STOCKS[1]
ann = {2025: dict(rev=89_900_000_000, op=3_800_000_000, np=3_489_630_597, np_owner=3_489_630_597,
                  equity=90_222_397_527, equity_owner=90_222_397_527, liab=56_000_000_000, eps=25),
       2024: dict(rev=87_600_000_000, op=2_300_000_000, np=6_685_688_838, np_owner=6_685_688_838,
                  equity=87_043_381_312, equity_owner=87_043_381_312, liab=51_000_000_000, eps=49),
       2023: dict(rev=93_100_000_000, op=-2_800_000_000, np=-3_555_068_227, np_owner=-3_555_068_227,
                  equity=80_013_889_453, equity_owner=80_013_889_453, liab=63_000_000_000, eps=-26),
       2022: dict(rev=90_900_000_000, op=100_000_000, np=-2_828_783_632, np_owner=-2_828_783_632,
                  equity=82_456_280_259, equity_owner=82_456_280_259, liab=65_000_000_000, eps=-20)}
# DART 발행총수는 병합 전(138M = KRX 27.6M 의 5.001배) → 생성기가 KRX 를 쓴다
q = run_quant(st, ann, total_shares=138_145_639)
v = q["valuation"]
ok(v["eps"] == 126, "EPS 는 순이익÷현재주식수(126)", f"eps={v['eps']} src={v['eps_src']}")
ok(v["ttm_np_owner"] == 3_489_630_597, "TTM 순이익이 공시 EPS×주식수로 덮어써지지 않는다",
   f"ttm={v['ttm_np_owner']:,}")
ok(abs(v["eps"] * st["shares"] / v["ttm_np_owner"] - 1) < 0.01, "EPS × 주식수 = TTM (항등식)")
bad = C.check_quant(q)
ok(not bad, "check_quant 통과", str(bad))

# ═══ ② 지엘팜텍 — 정수 반올림 ═══════════════════════════════════════════
print("② 지엘팜텍 — EPS 반올림(-6.9 → -7)")
st = STOCKS[2]
ann = {2025: dict(rev=35_300_000_000, op=300_000_000, np=12_489_192, np_owner=12_489_192,
                  equity=19_918_857_122, equity_owner=19_918_857_122, equity_nci=0, liab=28_000_000_000, eps=0),
       2024: dict(rev=26_000_000_000, op=-1_800_000_000, np=-2_337_462_825, np_owner=-2_337_462_825,
                  equity=19_667_919_316, equity_owner=19_667_919_316, liab=22_000_000_000, eps=-31),
       2023: dict(rev=26_000_000_000, op=-3_200_000_000, np=-3_748_514_692, np_owner=-3_748_514_692,
                  equity=12_282_299_531, equity_owner=12_282_299_531, liab=27_000_000_000, eps=-60),
       2022: dict(rev=16_700_000_000, op=-3_300_000_000, np=-790_167_314, np_owner=-790_167_314,
                  equity=16_090_489_292, equity_owner=16_090_489_292, liab=24_000_000_000, eps=-13)}
# 2025 반기·3분기·2026 1분기·반기 누적 → 마지막 4개 분기 합 = -107,109,567
qs = {
    (2025, "11013"): dict(rev=8_000_000_000, op=100_000_000, np=20_000_000, np_owner=20_000_000, eps=1,
                          equity=19_500_000_000, equity_owner=19_500_000_000),
    (2025, "11012"): dict(rev=16_358_911_235, op=281_602_821, np=77_055_750, np_owner=77_055_750, eps=1,
                          equity=19_600_000_000, equity_owner=19_600_000_000),
    (2025, "11014"): dict(rev=25_893_895_882, op=534_258_123, np=209_828_890, np_owner=209_828_890, eps=1,
                          equity=19_700_000_000, equity_owner=19_700_000_000),
    (2026, "11013"): dict(rev=9_433_733_122, op=34_628_475, np=-119_998_685, np_owner=-119_998_685, eps=0,
                          equity=19_800_000_000, equity_owner=19_800_000_000),
    (2026, "11012"): dict(rev=19_135_446_046, op=265_641_616, np=-38_469_890, np_owner=-38_469_890, eps=0,
                          equity=19_880_000_000, equity_owner=19_880_000_000),
}
q = run_quant(st, ann, qs, total_shares=15_509_801)
v = q["valuation"]
last4 = sum(x["np_owner"] for x in q["quarterly"][-4:])
# Q3 = 209,828,890−77,055,750 · Q4 = 12,489,192−209,828,890 · 2026Q1 · Q2 = −38,469,890−(−119,998,685)
ok(last4 == -103_036_448, "분기 4개 합이 기대값", f"{last4:,}")
ok(v["ttm_np_owner"] == last4, "TTM = 분기 4개 합")
ok(v["eps"] == -7, "EPS 가 -7 로 반올림(-103,036,448 ÷ 15,509,801 = -6.64 · 절삭이면 -6)", f"eps={v['eps']}")
ok(not C.check_quant(q), "check_quant 통과", str(C.check_quant(q)))
# 검산기: 반올림 폭(±0.5원×주식수)을 넘게 어긋난 값은 여전히 걸린다
q_old = json.loads(json.dumps(q)); q_old["valuation"]["eps"] = -5
ok(any(c == "EPS분모" for c, _ in C.check_quant(q_old)), "반올림 폭을 넘는 값(-5)은 검산에 걸린다")

# ═══ ③ 한울앤제주 — 지배지분 칸에 자본총계 ═════════════════════════════
print("③ 한울앤제주 — 지배지분 == 자본총계 인데 비지배지분 별도")
st = STOCKS[3]
ann = {2025: dict(rev=13_900_000_000, op=-4_900_000_000, np=-11_513_655_522, np_owner=-11_513_655_522,
                  equity=15_979_664_433, equity_owner=15_979_664_433, equity_nci=164_946_283,
                  liab=44_000_000_000),
       2024: dict(rev=18_300_000_000, op=-4_800_000_000, np=-20_945_446_528, np_owner=-20_945_446_528,
                  equity=8_298_781_016, equity_owner=8_298_781_016, liab=24_000_000_000),
       2023: dict(rev=22_400_000_000, op=-11_000_000_000, np=-12_390_083_212, np_owner=-12_609_991_453,
                  equity=22_806_470_350, equity_owner=18_185_486_753, equity_nci=4_620_983_597,
                  liab=27_000_000_000, eps=-218),
       2022: dict(rev=24_000_000_000, op=-11_600_000_000, np=-24_764_349_316, np_owner=-24_636_258_234,
                  equity=34_348_911_755, equity_owner=29_947_836_399, equity_nci=4_401_075_356,
                  liab=27_000_000_000, eps=-434)}
q = run_quant(st, ann, total_shares=22_149_847)
a0 = q["annual"][0]
ok(a0["equity_owner"] == 15_979_664_433 - 164_946_283, "지배지분 = 자본총계 − 비지배지분", f"{a0['equity_owner']:,}")
ok(not any(c == "자본항등" for c, _ in C.check_quant(q)), "자본항등 통과")
ok(M._owner_equity(18_185_486_753, 22_806_470_350, 4_620_983_597) == 18_185_486_753,
   "정상 값(지배 ≠ 총계)은 건드리지 않는다")
ok(M._owner_equity(1_000, 900, -100) == 1_000, "비지배가 음수라 지배 > 총계 인 회사는 그대로")
ok(M._owner_equity(None, 1_000, 100) == 900, "지배지분 태그를 못 읽으면 항등식으로 되찾는다")
ok(M._owner_equity(None, 1_000, None) is None, "재료가 없으면 None 그대로(호출자가 총계로 폴백)")

# ═══ ④ DART 한도 — 데이터 없음과 구분 ══════════════════════════════════
print("④ DART 응답 코드 구분")
# pandas 는 여기서 쓰지 않는다 — 위의 날짜 패치 뒤에 import 하면 C 확장이 거부한다.
EMPTY = types.SimpleNamespace(empty=True)
def dart_prints(status, msg):
    def fn(*a, **k):
        print({"status": status, "message": msg})
        return EMPTY
    return fn
try:
    M._dart_call(dart_prints("020", "요청 제한을 초과하였습니다."))
    ok(False, "020 은 DartUnavailable")
except M.DartUnavailable as e:
    ok(e.status == "020", "020(한도 초과) → DartUnavailable", str(e))
try:
    M._dart_call(dart_prints("800", "시스템 점검 중입니다."))
    ok(False, "800 은 DartUnavailable")
except M.DartUnavailable as e:
    ok(e.status == "800", "800(점검) → DartUnavailable")
try:
    M._dart_call(dart_prints("010", "등록되지 않은 키입니다."))
    ok(False, "010 은 DartUnavailable")
except M.DartUnavailable as e:
    ok(e.status == "010", "010(키) → DartUnavailable")
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    df = M._dart_call(dart_prints("013", "조회된 데이타가 없습니다."))
finally:
    sys.stdout = old
ok(df is not None and df.empty, "013(데이터 없음) → 빈 표 그대로(예외 아님)")
ok("조회된 데이타가 없습니다" not in buf.getvalue(), "013 잡음은 로그에서 뺀다")
def raises(*a, **k):
    raise ValueError('could not find "999999"')
ok(M._dart_call(raises) is None, "그 종목만의 예외(corp 없음) → None")
def ok_fn(*a, **k):
    print("reprt_code='11011', fs_div='CFS'")
    return types.SimpleNamespace(empty=False, n=1)
buf = io.StringIO(); sys.stdout = buf
try:
    df = M._dart_call(ok_fn)
finally:
    sys.stdout = old
ok(df is not None and df.n == 1 and "reprt_code" not in buf.getvalue(), "정상 응답은 그대로, reprt_code 잡음 제거")

# collect_all_quant: 한도에 걸리면 모은 것만 돌려주고 unavailable 을 표시한다
REAL_COLLECT_QUANT, REAL_CROSS, REAL_KRX, REAL_GET_DART = M.collect_quant, M.cross_check, M.krx_fundamentals, M.g.get_dart
REAL_COLLECT_ALL = M.collect_all_quant
calls = {"n": 0}
def quant_or_die(dart, tk, row, stock):
    calls["n"] += 1
    if calls["n"] == 2:
        raise M.DartUnavailable("020", "요청 제한을 초과하였습니다.")
    return {"annual": [{"year": 2025, "rev": 1, "op": 1, "np_owner": 1, "opm": 1.0, "roe": 1.0, "debt_ratio": 1.0}],
            "quarterly": [], "valuation": {}}
M.collect_quant = quant_or_die
M.cross_check = lambda *a, **k: None
M.krx_fundamentals = lambda d: None
M.g.get_dart = lambda: object()
out, errors, unavailable = M.collect_all_quant(STOCKS[:3], {"dataDate": "20260904"})
ok(list(out) == ["005930"], "한도에 걸리면 그때까지 모은 것만", str(list(out)))
ok(unavailable is not None and unavailable.status == "020", "unavailable 에 사유")
ok(not errors, "종목 오류로 세지 않는다")
M.collect_quant, M.krx_fundamentals, M.g.get_dart = REAL_COLLECT_QUANT, REAL_KRX, REAL_GET_DART   # cross_check 는 계속 가짜(네이버 호출 없음)
# 실패 횟수의 유효기간 — 오래된 실패는 0 으로 본다
S.FAIL_DIR.mkdir(exist_ok=True)
(S.FAIL_DIR / "000020").write_text("3 2026-08-01", encoding="utf-8")
ok(S.fail_count("000020", day=REAL_DATE(2026, 9, 5)) == 0, "2주 지난 실패 횟수는 0")
ok(S.fail_count("000020", day=REAL_DATE(2026, 8, 5)) == 3, "최근 실패는 그대로")
S.clear_fail("000020")

# ═══ ⑤ 대상 선정 ═══════════════════════════════════════════════════════
print("⑤ 대상 선정 — 갱신 기준일·hold·fail·skip·진행 중")
for tk, d in (("005930", "2026-08-14"), ("000890", "2026-06-19"), ("204840", "2026-06-19"),
              ("276730", "2026-06-19"), ("000020", "2026-09-04")):
    write_report(tk, d)
# 000040 은 리포트 없음
os.environ.pop("REPORT_TICKERS", None)
os.environ["REPORT_FILL_TO"] = "3000"
os.environ["REPORT_TOP_N"] = "100"
M.TOP_N = 100
data, t = M.pick_targets()
ok([s["ticker"] for s in t] == ["000040"], "기준일 없음 → 리포트 없는 종목만", str([s["ticker"] for s in t]))
S.REFRESH_FILE.write_text("# 전 종목 갱신\n2026-09-01\n", encoding="utf-8")
data, t = M.pick_targets()
ok({s["ticker"] for s in t} == {"005930", "000890", "204840", "276730", "000040"},
   "기준일 2026-09-01 → 그 전 리포트는 '없음' 취급, 09-04 는 유지", str(sorted(s["ticker"] for s in t)))
S.add_hold("000890", "[EPS분모] 테스트")
S.add_skip(["276730"])
for _ in range(S.FAIL_LIMIT):
    S.bump_fail("204840")
S.BATCH_DIR.mkdir(exist_ok=True)
(S.BATCH_DIR / "msgbatch_test1.json").write_text(json.dumps(
    {"batch_id": "msgbatch_test1", "tickers": ["005930"], "models": {"005930": "m"}, "quant": {}}), encoding="utf-8")
data, t = M.pick_targets()
ok([s["ticker"] for s in t] == ["000040"], "hold·skip·fail≥3·진행 중 배치는 뺀다", str([s["ticker"] for s in t]))
stocks_sorted = sorted(STOCKS, key=lambda x: x["mcap"], reverse=True)
ok(S.remaining_tickers(stocks_sorted, 3000) == ["000040"], "_fill_remaining 도 같은 답(워치독=생성기)")
os.environ["REPORT_ALLOW_INFLIGHT"] = "1"
data, t = M.pick_targets()
ok({s["ticker"] for s in t} == {"005930", "000040"}, "REPORT_ALLOW_INFLIGHT=1 이면 진행 중도 대상")
os.environ.pop("REPORT_ALLOW_INFLIGHT")
# 샤드 분할: 두 샤드의 합집합 = 전체, 교집합 = 없음
os.environ.update({"REPORT_FILL_SHARDS": "2", "REPORT_FILL_SHARD": "0"})
os.environ["REPORT_ALLOW_INFLIGHT"] = "1"
S.clear_hold("000890"); S.remove_skip("276730"); S.clear_fail("204840")
_, a = M.pick_targets()
os.environ["REPORT_FILL_SHARD"] = "1"
_, b = M.pick_targets()
sa, sb = {s["ticker"] for s in a}, {s["ticker"] for s in b}
ok(sa | sb == {"005930", "000890", "204840", "276730", "000040"} and not (sa & sb), "샤드가 겹치지 않고 빠짐없다")
for k in ("REPORT_FILL_SHARDS", "REPORT_FILL_SHARD", "REPORT_ALLOW_INFLIGHT", "REPORT_FILL_TO"):
    os.environ.pop(k, None)
# 명시 지정: universe 밖·진행 중 제외
os.environ["REPORT_TICKERS"] = "005930,000020,999999"
_, t = M.pick_targets()
ok([s["ticker"] for s in t] == ["000020"], "명시 지정도 진행 중(005930)·universe 밖(999999) 제외", str([s["ticker"] for s in t]))
os.environ.pop("REPORT_TICKERS")
# skip 재시도 판정(백필)
S.add_skip(["276730"], day=REAL_DATE(2026, 8, 1))
ok(S.skip_retryable("276730", day=REAL_DATE(2026, 9, 5)), "skip 30일 지나면 다시 시도")
S.add_skip(["276730"], day=REAL_DATE(2026, 9, 1))
ok(not S.skip_retryable("276730", day=REAL_DATE(2026, 9, 5)), "skip 며칠 안 됐으면 기다린다")
(S.SKIP_DIR / "000040").write_text("", encoding="utf-8")
ok(S.skip_retryable("000040"), "날짜 없는 옛 마커는 시도 대상")
S.remove_skip("276730"); S.remove_skip("000040")

# ═══ ⑥ 주문(submit) ═════════════════════════════════════════════════════
print("⑥ submit — 상태 파일·hold·skip·부분 주문")
class FakeBatches:
    def __init__(self): self.created = []; self.store = {}
    def create(self, requests):
        bid = f"msgbatch_fake{len(self.created)+1}"
        self.created.append((bid, requests)); return types.SimpleNamespace(id=bid)
    def retrieve(self, bid):
        return self.store[bid]
    def results(self, bid):
        return self.store[bid]._results
    def list(self, limit=1):
        return []
class FakeClient:
    def __init__(self): self.messages = types.SimpleNamespace(batches=FakeBatches())

GOOD_Q = lambda: {"asOf": "2026-09-05", "annual": [{"year": 2025, "rev": 100, "op": 10, "np_owner": 8, "equity": 50, "equity_owner": 50, "liab": 20, "opm": 10.0, "roe": 16.0, "debt_ratio": 40.0}],
                  "quarterly": [], "valuation": {"price": 1000, "eps": 100, "per": 10.0, "bps": 500, "pbr": 2.0, "ttm_np_owner": 100 * 1_000_000, "shares": 1_000_000, "total_shares": 1_000_000, "eps_src": "순이익÷주식수"}}
BAD_Q = lambda: {"asOf": "2026-09-05", "annual": [{"year": 2025}], "quarterly": [],
                 "valuation": {"price": 1000, "eps": 100, "per": 10.0, "ttm_np_owner": 5 * 1_000_000, "shares": 1_000_000, "total_shares": 1_000_000, "eps_src": "순이익÷주식수"}}
def fake_collect_all(targets, data, die_after=None, no_data=()):
    out = {}
    for i, st in enumerate(targets):
        tk = st["ticker"]
        if die_after is not None and i >= die_after:
            return out, {}, M.DartUnavailable("020", "요청 제한을 초과하였습니다.")
        if tk in no_data:
            out[tk] = {"annual": [], "quarterly": [], "valuation": {}}
        elif tk == "000890":
            out[tk] = BAD_Q()
        else:
            out[tk] = GOOD_Q()
    return out, {}, None

cl = FakeClient()
os.environ["REPORT_FILL_TO"] = "3000"; M.TOP_N = 100
M.collect_all_quant = lambda targets, data, allow_reuse=False: fake_collect_all(targets, data, no_data={"000040"})
S.REFRESH_FILE.write_text("2026-09-01\n", encoding="utf-8")
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
r = M.submit(cl, "2026-09-05 02:00")
ok(r["batch_id"] == "msgbatch_fake1", "배치 생성", str(r["batch_id"]))
ok(set(r["tickers"]) == {"005930", "204840", "276730"}, "정상 종목만 주문(보해양조 hold · 000040 no-data)", str(r["tickers"]))
ok("000890" in S.load_hold(), "항등식 걸린 종목은 hold 마커")
ok("000040" in S.load_skip() and "000890" not in S.load_skip(), "fill 모드: 재무제표 없는 종목만 skip")
path = S.batch_path("msgbatch_fake1")
stt = json.loads(path.read_text(encoding="utf-8"))
ok(path.exists() and stt["tickers"] == r["tickers"] and set(stt["quant"]) == set(r["tickers"]), "상태 파일에 tickers·quant")
ok(S.inflight_tickers() == set(r["tickers"]), "주문한 종목은 곧바로 '진행 중'")
req = cl.messages.batches.created[0][1][0]
ok(req["params"]["model"] in ("claude-opus-5", "claude-sonnet-5") and req["params"]["thinking"] == {"type": "adaptive"}
   and req["params"]["max_tokens"] == 96000, "요청 모양(모델·adaptive thinking·max_tokens)")
# 같은 조건으로 다시 주문하면 진행 중이라 아무것도 안 한다
r2 = M.submit(cl, "2026-09-05 02:01")
ok(r2["batch_id"] is None and len(cl.messages.batches.created) == 1, "진행 중 종목은 재주문하지 않는다")
# DART 가 도중에 막히면 모은 것만 주문하고 unavailable 을 알린다
S.clear_hold("000890")
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
M.collect_all_quant = lambda targets, data, allow_reuse=False: fake_collect_all(targets, data, die_after=2)
r3 = M.submit(cl, "2026-09-05 02:02")
ok(r3["batch_id"] is not None and r3["unavailable"] is not None and len(r3["tickers"]) == 2, "한도에 걸려도 모은 만큼 주문 + unavailable", f"{r3['tickers']} {r3['unavailable']}")
ok(not (set(S.load_skip()) - {"000040"}), "한도로 못 모은 종목은 skip 이 아니다", str(S.load_skip()))
os.environ.pop("REPORT_FILL_TO")

# ═══ ⑦ 회수(pickup) ═════════════════════════════════════════════════════
print("⑦ pickup — 여러 배치, 파일별 한 번, 실패 횟수")
os.environ["REPORT_REPAIR"] = "0"
def report_text(tk):
    para = lambda s: {"ko": (s + " 문장이다. ") * 24, "en": ("Plain English sentence. ") * 24}
    item = {"title": {"ko": "a", "en": "a"}, "body": {"ko": "b" * 20, "en": "b" * 20}}
    rep = {"title": {"ko": f"{tk} 제목", "en": "title"}, "lead": {"ko": "lead", "en": "lead"},
           "keypoints": [{"ko": "k", "en": "k"}] * 4, "business": para("사업"), "earnings": para("실적"),
           "industry": para("산업"), "outlook": para("전망"), "valuation_comment": {"ko": "v", "en": "v"},
           "bull": [item] * 3, "bear": [item] * 3,
           "risks": [{"cat": {"ko": "c", "en": "c"}, "body": {"ko": "r" * 20, "en": "r" * 20}}] * 3,
           "checkpoints": [{"when": {"ko": "w", "en": "w"}, "what": {"ko": "x", "en": "x"}}] * 3,
           "verdict": {"body": {"ko": "종합 " * 50, "en": "verdict " * 30}}}
    return "===JSON_START===" + json.dumps(rep, ensure_ascii=False) + "===JSON_END==="
def result(tk, kind="succeeded", text=None, usage=None):
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text or report_text(tk), citations=None)],
                                usage=usage)
    return types.SimpleNamespace(custom_id=tk, result=types.SimpleNamespace(type=kind, message=msg))
USAGE = types.SimpleNamespace(input_tokens=100_000, cache_creation_input_tokens=2_000, cache_read_input_tokens=8_000,
                              output_tokens=20_000, server_tool_use=types.SimpleNamespace(web_search_requests=5))
def batch_obj(bid, status, results):
    b = types.SimpleNamespace(id=bid, processing_status=status,
                              request_counts=types.SimpleNamespace(processing=0, succeeded=0, errored=0, expired=0, canceled=0))
    b._results = results
    return b
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
for p in S.OUT_DIR.glob("*.json"):
    p.unlink()
mk = lambda bid, tks: (S.BATCH_DIR / f"{bid}.json").write_text(json.dumps(
    {"batch_id": bid, "created": "2026-09-05 01:00", "tickers": tks, "models": {t: "claude-sonnet-5" for t in tks},
     "dataDate": "20260904", "count": len(tks), "quant": {t: GOOD_Q() for t in tks}}), encoding="utf-8")
mk("msgbatch_A", ["005930", "000020", "000040", "204840"])
mk("msgbatch_B", ["276730"])
cl = FakeClient()
cl.messages.batches.store["msgbatch_A"] = batch_obj("msgbatch_A", "ended", [
    result("005930", usage=USAGE), result("000020", "errored"), result("000040", "expired"),
    result("204840", text="===JSON_START==={\"title\": 1}===JSON_END==="),
])
cl.messages.batches.store["msgbatch_B"] = batch_obj("msgbatch_B", "in_progress", [])
S.bump_fail("005930")            # 예전에 한 번 실패했던 종목 — 성공하면 지워져야
S.add_hold("005930", "old")
n = M.pickup(cl, "2026-09-05 03:00")
ok(n == 1, "끝난 배치만 회수", f"n={n}")
rep = json.loads((S.OUT_DIR / "005930.json").read_text(encoding="utf-8"))
ok(rep["v"] == 2 and rep["ticker"] == "005930" and rep["reportDate"] and rep["quant"]["valuation"]["eps"] == 100, "리포트 파일 작성(quant 는 주문 시점 것)")
ok(rep["model"] == "claude-sonnet-5" and rep["name"] == "삼성전자", "메타 정보")
ok(S.fail_count("005930") == 0 and "005930" not in S.load_hold(), "성공한 종목은 fail·hold 마커를 뗀다")
ok(S.fail_count("000020") == 1, "errored 는 실패 횟수 +1")
ok(S.fail_count("000040") == 0, "expired 는 종목 탓이 아니라 세지 않는다")
ok(S.fail_count("204840") == 1 and not (S.OUT_DIR / "204840.json").exists(), "스키마 불완전 → 파일 안 쓰고 실패 +1")
stA = json.loads(S.batch_path("msgbatch_A").read_text(encoding="utf-8"))
ok(stA.get("collected") and "quant" not in stA and stA["result"] == {"ok": 1, "fail": 3}, "회수한 배치는 collected 표시 + quant 제거", str(stA.get("result")))
ua = (stA.get("usage") or {}).get("claude-sonnet-5") or {}
# (100,000 + 2,000×1.25 + 8,000×0.1) × $1/M + 20,000 × $5/M + 5 × $0.01 = 0.1033 + 0.1 + 0.05
ok(ua.get("n") == 1 and ua.get("in") == 100_000 and ua.get("search") == 5 and abs(ua.get("usd", 0) - 0.2533) < 0.001,
   "사용량·추정 비용을 모델별로 남긴다", str(ua))
stB = json.loads(S.batch_path("msgbatch_B").read_text(encoding="utf-8"))
ok(not stB.get("collected") and "quant" in stB, "안 끝난 배치는 그대로")
ok(S.inflight_tickers() == {"276730"}, "회수한 종목은 '진행 중' 에서 빠진다")
n = M.pickup(cl, "2026-09-05 03:30")
ok(n == 0, "이미 회수한 배치는 다시 받지 않는다")
# 만료(NotFound)된 배치는 버린다
import anthropic
class NF(anthropic.NotFoundError):
    def __init__(self): pass
def retrieve_nf(bid):
    if bid == "msgbatch_B":
        raise NF()
    return cl.messages.batches.store[bid]
cl.messages.batches.retrieve = retrieve_nf
M.pickup(cl, "2026-09-05 04:00")
stB = json.loads(S.batch_path("msgbatch_B").read_text(encoding="utf-8"))
ok(stB.get("abandoned") and not S.inflight_tickers(), "찾을 수 없는 배치는 abandoned — 진행 중에서 빠진다")
# 정리: 30일 지난 회수 파일은 지운다
stA["collected"] = "2026-07-01 00:00"
S.batch_path("msgbatch_A").write_text(json.dumps(stA), encoding="utf-8")
M._housekeep_batches()
ok(not S.batch_path("msgbatch_A").exists() and S.batch_path("msgbatch_B").exists(), "오래된 회수 파일만 정리")

# ═══ ⑧ DART 한도 마커 · 정지 스위치 ═════════════════════════════════════
print("⑧ 한도 마커 · 정지 스위치")
try:
    M._die_dart(M.DartUnavailable("020", "x"))
    ok(False, "_die_dart 는 종료해야 한다")
except SystemExit as e:
    ok(e.code == M.EXIT_DART_UNAVAILABLE and S.quota_exhausted_today(), "020 → exit 3 + 오늘 날짜 마커")
S.QUOTA_FILE.write_text("2026-09-04\n", encoding="utf-8")
ok(not S.quota_exhausted_today(), "어제 마커는 오늘 효력 없음")
try:
    M._die_dart(M.DartUnavailable("800", "점검"))
except SystemExit as e:
    ok(e.code == M.EXIT_DART_UNAVAILABLE and not S.quota_exhausted_today(), "800 → exit 3, 한도 마커는 안 남김")

# ═══ ⑨ 리포트 품질 — 데이터 보강 · 프롬프트 · 검증 · 교정 ═══════════════
print("⑨ 품질 보강")
# (a) 요약재무 폴백 — 전체 재무제표가 없는 해를 채운다
st = STOCKS[4]
ann3 = {2025: dict(rev=100, op=10, np=8, np_owner=7, np_nci=1, equity=50, equity_owner=45, equity_nci=5, liab=20, eps=100),
        2024: dict(rev=90, op=9, np=7, np_owner=6, np_nci=1, equity=45, equity_owner=40, equity_nci=5, liab=18, eps=90),
        2023: dict(rev=80, op=8, np=6, np_owner=5, np_nci=1, equity=40, equity_owner=36, equity_nci=4, liab=16, eps=80)}
def summary_2022(dart, ticker, year, reprt):
    if year != 2022:
        return None
    return PD.DataFrame([
        {"account_nm": "매출액", "fs_div": "CFS", "thstrm_amount": "70"},
        {"account_nm": "영업이익", "fs_div": "CFS", "thstrm_amount": "7"},
        {"account_nm": "당기순이익", "fs_div": "CFS", "thstrm_amount": "5"},
        {"account_nm": "자본총계", "fs_div": "CFS", "thstrm_amount": "35"},
        {"account_nm": "부채총계", "fs_div": "CFS", "thstrm_amount": "14"},
    ])
M._fin_all = fin_factory(ann3)
M.dart_total_shares = lambda d, t: 1_000_000
M.dart_dps = lambda d, t: None
M.g._safe_finstate = summary_2022
M.g._extract_fin = lambda *a, **k: None
q = M.collect_quant(None, st["ticker"], None, st)
yrs = [r["year"] for r in q["annual"]]
r22 = next((r for r in q["annual"] if r["year"] == 2022), None)
ok(yrs == [2025, 2024, 2023, 2022], "2022 를 요약재무로 채워 4년이 된다", str(yrs))
ok(r22 and r22["rev"] == 70 and r22["equity"] == 35 and r22["liab"] == 14 and r22.get("src") == "요약재무", "요약재무 값이 들어간다", str(r22))
ok(r22 and r22["np_owner"] is None and r22["roe"] is None, "비지배지분이 있는 회사면 요약 해의 지배순이익은 비운다")
ok(r22 and r22["debt_ratio"] == 40.0 and r22["opm"] == 10.0, "파생값은 재료로 다시 계산된다")

# (a2) 요약재무도 없는 해 — 다음 해 보고서의 전기 비교치로 채운다 (보험사 2022)
ann_ins = {2025: dict(rev=None, op=26_591, np=21_000, np_owner=20_183, equity=212_000, equity_owner=210_000, equity_nci=2_000, liab=750_000, eps=47_478),
           2024: dict(rev=None, op=26_496, np=21_500, np_owner=20_736, equity=180_000, equity_owner=178_000, equity_nci=2_000, liab=820_000, eps=48_000),
           2023: dict(rev=None, op=23_573, np=19_000, np_owner=18_184, equity=160_000, equity_owner=158_000, equity_nci=2_000, liab=680_000, eps=42_000,
                      _prev=dict(op=20_000, np=16_000, np_owner=15_500, equity=150_000, equity_owner=148_500, equity_nci=1_500, liab=650_000, eps=36_000))}
M._fin_all = fin_factory(ann_ins)
M.dart_total_shares = lambda d, t: 43_000_000
M.g._safe_finstate = lambda *a, **k: None       # 요약재무도 없다
q = M.collect_quant(None, STOCKS[4]["ticker"], None, STOCKS[4])
yrs = [r["year"] for r in q["annual"]]
r22 = next((r for r in q["annual"] if r["year"] == 2022), None)
ok(yrs == [2025, 2024, 2023, 2022], "2022 를 2023 보고서의 전기 칸으로 채운다", str(yrs))
_u = (r22["equity"] / 150_000) if r22 else 1          # 단위 자동보정(천원·백만원 공시 추정)이 걸릴 수 있어 배수로 본다
ok(r22 and r22["op"] == 20_000 * _u and r22["np_owner"] == 15_500 * _u and r22["equity_owner"] == 148_500 * _u and r22.get("src") == "전기 비교치", "전기 비교치가 들어간다", str(r22))
ok(r22 and r22["eps_basic"] == 36_000 and r22["roe"] == round(15_500 / 148_500 * 100, 1), "주당이익·파생값도 전기 값으로")
ok(not C.check_quant(q), "check_quant 통과", str(C.check_quant(q)))

# (b) 분기 지배지분 태그가 없고 비지배지분이 큰 회사 — 자본총계에서 결산 비지배지분을 뺀다
st = STOCKS[0]
W = 1_000_000   # 백만원 → 원
ann_skc = {2025: dict(rev=1_000_000*W, op=10_000*W, np=-60_000*W, np_owner=-50_000*W, np_nci=-10_000*W, equity=2_025_734*W, equity_owner=832_066*W, equity_nci=1_193_667*W, liab=4_710_000*W, eps=-1321),
           2024: dict(rev=1_000_000*W, op=10_000*W, np=-50_000*W, np_owner=-40_000*W, np_nci=-10_000*W, equity=2_292_732*W, equity_owner=1_172_309*W, equity_nci=1_120_423*W, liab=4_500_000*W, eps=-1056)}
qs_skc = {(2026, "11012"): dict(rev=500_000*W, op=5_000*W, np=-30_000*W, np_owner=-25_000*W, eps=-660, equity=1_994_000*W),   # equity_owner 없음
          (2025, "11012"): dict(rev=500_000*W, op=5_000*W, np=-30_000*W, np_owner=-25_000*W, eps=-660, equity=2_200_000*W, equity_owner=1_000_000*W)}
M._fin_all = fin_factory(ann_skc, qs_skc)
M.dart_total_shares = lambda d, t: 37_868_298
M.g._safe_finstate = lambda *a, **k: None
q = M.collect_quant(None, st["ticker"], None, dict(st, shares=37_868_298, price=20_000, mcap=0.76))
v = q["valuation"]
_den = v.get("wavg_shares") or v.get("total_shares")
ok(v["bps"] is not None and abs(v["bps"] * _den - (1_994_000 - 1_193_667) * W) < _den, "BPS 분자 = 분기 자본총계 − 결산 비지배지분 (SKC: 52,663 이 아니라 ≈21,000)", f"bps={v['bps']} denom={_den}")

# (b2) 지배지분 태그는 있는데 값이 자본총계와 똑같다 — 실제로 이쪽이 더 많았다(20종목)
qs_skc2 = {(2026, "11012"): dict(rev=500_000*W, op=5_000*W, np=-30_000*W, np_owner=-25_000*W, eps=-660,
                                 equity=1_994_000*W, equity_owner=1_994_000*W),   # 지배 = 총계, 비지배 태그 없음
           (2025, "11012"): dict(rev=500_000*W, op=5_000*W, np=-30_000*W, np_owner=-25_000*W, eps=-660,
                                 equity=2_200_000*W, equity_owner=1_000_000*W)}
M._fin_all = fin_factory(ann_skc, qs_skc2)
q2 = M.collect_quant(None, st["ticker"], None, dict(st, shares=37_868_298, price=20_000, mcap=0.76))
v2_ = q2["valuation"]
_den2 = v2_.get("wavg_shares") or v2_.get("total_shares")
ok(v2_["bps"] is not None and abs(v2_["bps"] * _den2 - (1_994_000 - 1_193_667) * W) < _den2,
   "지배 칸에 총계가 들어와도 결산 비지배지분을 뺀다(SKC 52,664 가 아니라 ≈21,000)", f"bps={v2_['bps']}")

# (b3) 분기 지배지분이 총계와 다르면 손대지 않는다 — 보험사 분기말 자본은 그 값이 맞다
qs_ins = {(2026, "11012"): dict(rev=500_000*W, op=5_000*W, np=30_000*W, np_owner=25_000*W, eps=660,
                                equity=3_000_000*W, equity_owner=2_500_000*W)}
M._fin_all = fin_factory(ann_skc, qs_ins)
q3 = M.collect_quant(None, st["ticker"], None, dict(st, shares=37_868_298, price=20_000, mcap=0.76))
v3 = q3["valuation"]
_den3 = v3.get("wavg_shares") or v3.get("total_shares")
ok(v3["bps"] is not None and abs(v3["bps"] * _den3 - 2_500_000 * W) < _den3,
   "지배 ≠ 총계면 분기 지배지분을 그대로 쓴다", f"bps={v3['bps']}")
M._fin_all = fin_factory(ann_skc, qs_skc)

# (c) 숨긴 지표의 사유
ok(v.get("hidden", {}).get("per") == "loss", "적자면 PER 사유 loss", str(v.get("hidden")))
ok(v.get("hidden", {}).get("dps") == "no_div", "배당 없음 사유 no_div")
q_imp = run_quant(STOCKS[3], {2025: dict(rev=100, op=-10, np=-20, np_owner=-20, equity=-5, equity_owner=-5, liab=50)}, total_shares=1_000_000)
ok(q_imp["valuation"].get("hidden", {}).get("bps") == "impaired", "자본잠식이면 BPS 사유 impaired", str(q_imp["valuation"].get("hidden")))

# (d) valid_v2 — 영문이 빠진 항목을 거른다
good = json.loads(report_text("005930")[len("===JSON_START==="):-len("===JSON_END===")])
ok(M.valid_v2(good), "정상 구조는 통과")
bad = json.loads(json.dumps(good)); bad["bull"][0] = {"title": {"ko": "a"}, "body": {"ko": "b" * 20}}
ok(not M.valid_v2(bad), "bull 항목에 en 이 없으면 실패")
bad2 = json.loads(json.dumps(good)); bad2["keypoints"][0] = {"ko": "k"}
ok(not M.valid_v2(bad2), "keypoints 에 en 이 없으면 실패")

# (e) 프롬프트 — 반영 범위·주당 지표 금지·영문 한글 금지
pr = M.build_prompt_v2(STOCKS[0], q, "2026-09-05 02:00")
ok("재무 반영 범위" in pr and "2026Q2" in pr and "checkpoints 의 when 은 이 날짜 이후" in pr, "기준 범위·체크포인트 날짜 지시")
ok("주당 지표(EPS·BPS·DPS)의 수치도" in pr and "valuation.eps·bps" not in pr, "주당 지표 수치 인용 금지")
ok("한글 문자를 한 글자도" in pr and "증권사명 없이 범위를" in pr, "영문 한글 금지·목표주가 범위 금지")

# (f) 교정 — 가짜 클라이언트가 고친 JSON 을 돌려주면 채택, 모양이 다르면 버린다
import check_report_text as T
rep0 = {"lead": {"ko": "저평가된 상태다.", "en": "GC녹십자 is fine."}, "business": {"ko": "본문.", "en": "Body."}}
hits0 = T.check(rep0)
ok({h["rule"] for h in hits0} == {"valuejudge", "hangul_en"}, "검사가 둘 다 잡는다", str([h["rule"] for h in hits0]))
class FakeMsgs:
    def __init__(self, reply): self.reply = reply
    def create(self, **kw):
        assert "===INPUT===" in kw["messages"][0]["content"]
        return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=self.reply)])
fixed_json = json.dumps({"lead": {"ko": "순자산 대비 할인 폭이 크다.", "en": "GC Biopharma is fine."}}, ensure_ascii=False)
cl_ok = types.SimpleNamespace(messages=FakeMsgs("===JSON_START===" + fixed_json + "===JSON_END==="))
res = T.repair(cl_ok, rep0, hits0)
ok(res is not None and res[0]["lead"]["ko"].startswith("순자산") and res[1] == [] and res[0]["business"] == rep0["business"], "교정 결과 채택·다른 섹션 보존", str(res and res[0]))
cl_bad = types.SimpleNamespace(messages=FakeMsgs('===JSON_START==={"lead": {"ko": "x"}}===JSON_END==='))
ok(T.repair(cl_bad, rep0, hits0) is None, "모양이 다르면(en 누락) 버린다")
cl_same = types.SimpleNamespace(messages=FakeMsgs("===JSON_START===" + json.dumps({"lead": rep0["lead"]}, ensure_ascii=False) + "===JSON_END==="))
ok(T.repair(cl_same, rep0, hits0) is None, "위반이 줄지 않으면 버린다")

# (g) collect 에서 한자 변환·교정이 실제로 적용된다
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
mk("msgbatch_C", ["000020"])
cl = FakeClient()
txt = report_text("000020").replace("실적 문장이다.", "실적은 전년比 개선됐고 저평가된 상태다.", 1)
cl.messages.batches.store["msgbatch_C"] = batch_obj("msgbatch_C", "ended", [result("000020", text=txt, usage=USAGE)])
def _repair_stub(cl_, rep, hits, model=None):
    new = json.loads(json.dumps(rep))
    for k in ("business", "earnings", "industry", "outlook", "lead", "valuation_comment"):
        if isinstance(new.get(k), dict):
            new[k]["ko"] = new[k]["ko"].replace("저평가된 상태다", "순자산을 밑도는 구간이다")
    rem = T.check(new)
    return (new, rem) if len(rem) < len(hits) else None
T.repair = _repair_stub
os.environ["REPORT_REPAIR"] = "1"
M.pickup(cl, "2026-09-05 05:00")
rep = json.loads((S.OUT_DIR / "000020.json").read_text(encoding="utf-8"))
ok("比" not in rep["earnings"]["ko"] and "전년 대비" in rep["earnings"]["ko"], "한자 '比' 가 '대비' 로", rep["earnings"]["ko"][:60])
ok("저평가된" not in rep["earnings"]["ko"] and "순자산을 밑도는" in rep["earnings"]["ko"], "교정된 문장이 저장된다")
ok(not T.check(rep), "저장된 리포트는 검사를 통과한다")

# ═══ ⑩ 정량 재사용 — 이미 맞다는 것이 확인될 때만 ═══════════════════════
print("⑩ 정량 재사용")
M.collect_all_quant = REAL_COLLECT_ALL          # ⑥에서 가짜로 바꿔 둔 것을 되돌린다
TODAY = REAL_DATE(2026, 9, 5)
ok(M.latest_quarter_label(TODAY) == "2026Q2", "9월이면 최근 분기는 2026Q2")
ok(M.latest_quarter_label(REAL_DATE(2026, 4, 24)) == "2025Q4", "1분기 마감 전이면 작년 Q4")
ok(not M._reprt_available("11014", 2026, TODAY), "9월엔 3분기 보고서를 묻지 않는다")
ok(M._reprt_available("11012", 2026, TODAY) and M._reprt_available("11014", 2025, TODAY), "반기·지난해 보고서는 묻는다")

# 스스로 앞뒤가 맞는 표본: 분기 4개 합 = TTM = EPS × 주식수, BPS × 주식수 = 지배자본
GOOD = {"asOf": "2026-08-23", "annual": [
            {"year": y, "rev": 2_000_000_000, "op": 200_000_000, "np": 100_000_000, "np_owner": 100_000_000,
             "equity": 500_000_000, "equity_owner": 500_000_000, "equity_nci": 0, "liab": 200_000_000,
             "opm": 10.0, "roe": 20.0, "debt_ratio": 40.0} for y in (2025, 2024, 2023, 2022)],
        "quarterly": [{"q": q, "rev": 500_000_000, "op": 50_000_000, "np_owner": 25_000_000} for q in
                      ("2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2")],
        "valuation": {"price": 1000, "eps": 100, "per": 10.0, "bps": 500, "pbr": 2.0, "dps": 10.0, "div": 1.0,
                      "ttm_window": "2025Q3~2026Q2", "ttm_np_owner": 100_000_000, "shares": 1_000_000,
                      "total_shares": 1_000_000, "wavg_shares": 1_000_000, "eps_src": "순이익÷주식수",
                      "bps_src": "자체", "bps_krx": 520.0}}
STK = {"ticker": "000020", "name": "동화약품", "price": 1200, "mcap": 0.3, "shares": 1_000_000}

def put(tk, quant):
    S.OUT_DIR.mkdir(exist_ok=True)
    (S.OUT_DIR / f"{tk}.json").write_text(json.dumps({"ticker": tk, "quant": quant}, ensure_ascii=False), encoding="utf-8")

put("000020", GOOD)
q, why = M.reusable_quant("000020", STK, today=TODAY)
ok(q is not None and why is None, "완전·최신 정량은 재사용", str(why))
v = (q or {}).get("valuation", {})
ok(v.get("price") == 1200 and v.get("per") == 12.0 and v.get("pbr") == 2.4 and v.get("div") == 0.83,
   "가격 딸린 값만 오늘 시세로 다시 계산", str({k: v.get(k) for k in ("price", "per", "pbr", "div")}))
ok(v.get("eps") == 100 and v.get("bps") == 500 and q["annual"][0]["rev"] == 2_000_000_000, "재무 숫자는 그대로")
ok(json.loads((S.OUT_DIR / "000020.json").read_text(encoding="utf-8"))["quant"]["valuation"]["price"] == 1000,
   "원본 파일은 건드리지 않는다(복사본을 고친다)")

def refuse(mut, label):
    d = json.loads(json.dumps(GOOD)); mut(d); put("000020", d)
    q, why = M.reusable_quant("000020", STK, today=TODAY)
    ok(q is None, label, f"why={why}")

refuse(lambda d: d["valuation"].update(ttm_window="2025Q2~2026Q1"), "최근 분기가 빠졌으면 재수집")
refuse(lambda d: d.__setitem__("annual", d["annual"][:3]), "연간 3년치면 재수집")
refuse(lambda d: d["quarterly"][2].update(np_owner=None), "분기 빈칸이면 재수집")
refuse(lambda d: d["valuation"].update(bps=None), "BPS 가 없으면 재수집")
refuse(lambda d: d["valuation"].update(hidden={"eps": "mismatch"}), "추출 문제로 숨겼으면 재수집")
refuse(lambda d: d["valuation"].update(eps=5, per=200.0), "항등식(EPS×주식수≠TTM)이 깨지면 재수집")
# KRX 는 '결산' 지배지분을 쓴다. 분기 사이에 자본이 크게 움직인 회사는 값이 벌어지는
# 게 정상이다(삼성화재: 우리 850,994 · KRX 500,071 인데 KRX×분모 = 2025년말 지배자본).
# 분모까지 어긋날 때만 우리 잘못일 수 있다 — 그때만 다시 받는다.
d = json.loads(json.dumps(GOOD))
# 결산 자본 3억(분기말은 BPS 500 × 100만주 = 5억). 파생값도 같이 맞춰 둔다 —
# 안 그러면 '연간파생' 항등식에 먼저 걸려 이 시험이 무엇을 재는지 흐려진다.
d["annual"][0].update(equity=300_000_000, equity_owner=300_000_000,
                      roe=round(100_000_000 / 300_000_000 * 100, 1),
                      debt_ratio=round(200_000_000 / 300_000_000 * 100, 1))
d["valuation"]["bps_krx"] = 300.0                                     # 300 × 100만주 = 결산 자본
put("000020", d)
q, why = M.reusable_quant("000020", STK, today=TODAY)
ok(q is not None, "KRX 가 결산 기준이라 늦은 것이면 재사용(분모는 맞다)", f"why={why}")
refuse(lambda d: d["valuation"].update(bps_krx=200.0),
       "KRX 와 30% 넘게 다르고 분모도 안 맞으면 재수집")
put("000020", GOOD)
# 비지배지분까지 나눈 BPS (SKC 형) — 항등식은 통과하지만 재사용하지 않는다
def nci_bug(d):
    d["annual"][0].update(equity=500_000_000, equity_owner=200_000_000, equity_nci=300_000_000)
    d["valuation"].update(bps_krx=490.0)     # BPS 500 × 100만주 = 5억 = 자본총계(지배 2억이 아니다)
refuse(nci_bug, "BPS 가 비지배지분까지 나눈 값이면 재수집")
# 회사 사정(적자·무배당)은 재사용을 막지 않는다
d = json.loads(json.dumps(GOOD))
d["valuation"].update(eps=-100, per=None, dps=None, div=None, ttm_np_owner=-100_000_000,
                      hidden={"per": "loss", "dps": "no_div"})
for x in d["quarterly"]:
    x["np_owner"] = -25_000_000
for r in d["annual"]:
    r.update(np=-100_000_000, np_owner=-100_000_000, roe=-20.0)
put("000020", d)
q, why = M.reusable_quant("000020", STK, today=TODAY)
ok(q is not None, "적자·무배당은 재사용을 막지 않는다", f"why={why}")
ok(q and q["valuation"].get("per") is None, "적자면 PER 은 계산하지 않는다")
put("000020", GOOD)

# collect_all_quant: 재사용은 DART 를 부르지 않는다
put("005930", GOOD)
called = []
M.collect_quant = lambda dart, tk, row, stock: (called.append(tk), GOOD)[1]
M.cross_check = lambda *a, **k: None
M.krx_fundamentals = lambda d: None
M.g.get_dart = lambda: object()
tgt = [dict(STK), {"ticker": "005930", "name": "삼성전자", "price": 90000, "mcap": 500.0, "shares": 5_000_000},
       {"ticker": "000040", "name": "KR모터스", "price": 500, "mcap": 0.05, "shares": 100_000}]
out, errors, un = M.collect_all_quant(tgt, {"dataDate": "20260904"}, allow_reuse=True)
ok(set(out) == {"000020", "005930", "000040"} and called == ["000040"], "재사용 2 · DART 는 리포트 없는 1개만", str(called))
ok(out["005930"]["valuation"]["price"] == 90000, "재사용분도 오늘 시세로")
called.clear()
M.collect_all_quant(tgt, {"dataDate": "20260904"}, allow_reuse=False)
ok(len(called) == 3, "allow_reuse=False 면 전부 다시 받는다(patch 모드)", str(called))
os.environ["REPORT_NO_REUSE"] = "1"
called.clear()
M.collect_all_quant(tgt, {"dataDate": "20260904"}, allow_reuse=True)
ok(len(called) == 3, "REPORT_NO_REUSE=1 로 재사용을 끌 수 있다", str(called))
os.environ.pop("REPORT_NO_REUSE")


print()
print("⑪ 구조 복구 — 돈이 나간 글을 구조 하나 때문에 버리지 않는다")
GOODREP = lambda: json.loads(report_text("005930")[len("===JSON_START==="):-len("===JSON_END===")])

# (a) 항목 안 곁키(body_en_placeholder) — 모델을 부르지 않고 공짜로 산다
r = GOODREP()
r["risks"][0] = {"cat": {"ko": "규제", "en": "Regulation"},
                 "body": {"ko": "r" * 20, "en": ""}, "body_en_placeholder": "R" * 20}
ok(not M.valid_v2(r, quiet=True), "곁키만 있으면 검증 실패")
n = M.normalize_shape(r)
ok(n == 1 and M.valid_v2(r, quiet=True), "곁키를 제자리로 옮겨 되살린다", f"n={n}")
ok(r["risks"][0]["body"]["en"] == "R" * 20 and "body_en_placeholder" not in r["risks"][0], "곁키는 지워진다")

# (a2) 곁키 이름은 미리 다 알 수 없다 — 한 run 에서 본 네 가지를 다 받는다
for junk, why in (("body_en", "맨 _en"), ("body_en_note", "_en_note"),
                  ("body_en_unused", "_en_unused"), ("body_en_placeholder", "_en_placeholder")):
    r = GOODREP()
    r["bear"][0] = {"title": {"ko": "가", "en": "A"}, "body": {"ko": "b" * 20, "en": ""}, junk: "B" * 20}
    M.normalize_shape(r)
    ok(r["bear"][0]["body"]["en"] == "B" * 20 and junk not in r["bear"][0], f"곁키 {why} 흡수")
r = GOODREP()
r["bear"][0] = {"title": {"ko": "가", "en": "A"}, "body": {"ko": "b" * 20, "en": ""},
                "body_en_placeholder": "(TODO)", "body_en": "Real English."}
M.normalize_shape(r)
ok(r["bear"][0]["body"]["en"] == "Real English.", "곁키가 둘이면 맨 _en 을 먼저 믿는다", r["bear"][0]["body"]["en"])

# (a3) 항목 안 en 뭉치 — {"title": …, "body": …, "en": {"title": …, "body": …}}
r = GOODREP()
r["bull"][0] = {"title": {"ko": "가", "en": ""}, "body": {"ko": "b" * 20, "en": ""},
                "en": {"title": "Up", "body": "B" * 20}}
n = M.normalize_shape(r)
ok(n == 2 and r["bull"][0]["title"]["en"] == "Up" and "en" not in r["bull"][0],
   "항목 안 en 뭉치를 자리마다 나눠 담는다", f"n={n} {r['bull'][0]}")

# (b) 최상위 bull_en 목록 흡수
r = GOODREP()
r["bull"] = [{"title": {"ko": "가", "en": ""}, "body": {"ko": "b" * 20, "en": ""}} for _ in range(3)]
r["bull_en"] = [{"title": "Up", "body": "B" * 20} for _ in range(3)]
n = M.normalize_shape(r)
ok(n == 6 and M.valid_v2(r, quiet=True) and "bull_en" not in r, "bull_en 목록을 항목마다 흡수", f"n={n}")

# (c) 길이가 다르면 짝으로 인정하지 않는다 — 엉뚱한 짝짓기가 더 나쁘다
r = GOODREP()
r["bull"] = [{"title": {"ko": "가", "en": ""}, "body": {"ko": "b" * 20, "en": ""}} for _ in range(3)]
r["bull_en"] = [{"title": "Up", "body": "B" * 20}]
ok(M.normalize_shape(r) == 0 and not M.valid_v2(r, quiet=True), "길이가 다른 _en 목록은 쓰지 않는다")

# (d) 문자열만 온 자리는 {ko, en:""} 로 감싼다 → 영문 채우기가 그 자리를 찾는다
r = GOODREP()
r["bull"][0] = {"title": "가나다", "body": "라마바" * 8}
M.normalize_shape(r)
ok(r["bull"][0]["title"] == {"ko": "가나다", "en": ""}, "문자열만 온 자리를 감싼다", str(r["bull"][0]["title"]))
ok(M.valid_v2(r, en=False, quiet=True), "감싸고 나면 한국어 검증은 통과")

# (e) 이미 영문이 있으면 곁키가 덮어쓰지 못한다
r = GOODREP()
r["risks"][0] = {"cat": {"ko": "규제", "en": "Regulation"},
                 "body": {"ko": "r" * 20, "en": "KEEP" * 5}, "body_en_note": "OVER" * 5}
M.normalize_shape(r)
ok(r["risks"][0]["body"]["en"] == "KEEP" * 5, "제자리 값이 곁키보다 우선", r["risks"][0]["body"]["en"])

# (f) 메타 키 name_en 은 곁키로 오인하지 않는다
r = GOODREP(); r["name_en"] = "Samsung Electronics"
M.normalize_shape(r)
ok(r.get("name_en") == "Samsung Electronics", "name_en 은 건드리지 않는다")

# (g) 스키마에 없는 키는 걷어낸다 — 저장소에 쓰레기를 남기지 않는다
r = GOODREP(); r["bull"][0]["why"] = "쓸데없음"; r["verdict"]["score"] = 7; r["lead"]["note"] = "x"
M.normalize_shape(r)
ok("why" not in r["bull"][0] and "score" not in r["verdict"] and "note" not in r["lead"], "쓰레기 키 제거")

# (h) en=False 검증 — 영문만 빠진 글과 통째로 잘린 글을 가른다
r = GOODREP()
for x in r["bull"]:
    x["title"]["en"] = ""; x["body"]["en"] = ""
ok(not M.valid_v2(r, quiet=True) and M.valid_v2(r, en=False, quiet=True), "영문만 빠진 글은 en=False 로 통과")
trunc = GOODREP(); del trunc["verdict"]; del trunc["checkpoints"]
ok(not M.valid_v2(trunc, en=False, quiet=True), "잘린 글은 en=False 로도 실패 — 돈을 더 쓰지 않는다")
short = GOODREP(); short["outlook"]["en"] = "too short"
ok(M.valid_v2(short, en=False, quiet=True) and not M.valid_v2(short, quiet=True), "영문 분량 부족도 en=False 로는 통과")

# (i) fill_missing_en — 값싼 모델이 돌려준 영문을 제자리에, 순서대로 넣는다
class FillMsgs:
    def __init__(self): self.sent = []
    def create(self, **kw):
        self.sent.append(kw)
        payload = json.loads(kw["messages"][0]["content"].split("\n\n", 1)[1])
        out = {k: f"EN{k}" for k in payload}
        return types.SimpleNamespace(content=[types.SimpleNamespace(
            type="text", text="===JSON_START===" + json.dumps(out) + "===JSON_END===")])
fm = FillMsgs()
cl_fill = types.SimpleNamespace(messages=fm)
r = GOODREP()
for x in r["bull"]:
    x["title"]["en"] = ""; x["body"]["en"] = ""
n = M.fill_missing_en(cl_fill, r)
ok(n == 6 and M.valid_v2(r, quiet=True), "빈 영문 6곳을 채운다", f"n={n}")
ok(r["bull"][0]["title"]["en"] == "EN0" and r["bull"][2]["body"]["en"] == "EN5", "순서대로 제자리에", str([x["title"]["en"] for x in r["bull"]]))
ok(fm.sent[0]["model"] == "claude-sonnet-5", "값싼 모델을 쓴다", str(fm.sent[0]["model"]))
ok(M.fill_missing_en(cl_fill, GOODREP()) == 0 and len(fm.sent) == 1, "채울 자리가 없으면 모델을 부르지 않는다")

# (j) 회수 경로 통합 — 영문이 빠진 배치 결과가 저장까지 간다
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
(S.OUT_DIR / "005930.json").unlink(missing_ok=True)
mk("msgbatch_EN", ["005930"])
noen = GOODREP()
for x in noen["bull"]:
    x["title"]["en"] = ""; x["body"]["en"] = ""
noen["risks"][0]["body"]["en"] = ""; noen["risks"][0]["body_en_note"] = "Regulatory pressure."
cl2 = FakeClient()
fm2 = FillMsgs(); cl2.messages.create = fm2.create
cl2.messages.batches.store["msgbatch_EN"] = batch_obj("msgbatch_EN", "ended", [
    result("005930", text="===JSON_START===" + json.dumps(noen, ensure_ascii=False) + "===JSON_END===")])
S.bump_fail("005930")
M.pickup(cl2, "2026-09-05 03:00")
saved = S.OUT_DIR / "005930.json"
ok(saved.exists(), "영문이 빠진 결과도 되살려 저장한다")
got = json.loads(saved.read_text(encoding="utf-8")) if saved.exists() else {}
ok(bool(got) and got["bull"][0]["body"]["en"].startswith("EN"), "저장된 글에 영문이 있다", str(got.get("bull", [{}])[0]))
ok(bool(got) and got["risks"][0]["body"]["en"] == "Regulatory pressure." and "body_en_note" not in got["risks"][0],
   "곁키는 제자리로 가고 사라진다", str(got.get("risks", [{}])[0]))
ok("005930" not in S.load_failed_out() and S.fail_count("005930") == 0, "되살린 종목은 실패 기록이 지워진다")

# (k) 통째로 잘린 결과는 모델을 부르지 않고 버린다
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
(S.OUT_DIR / "000020.json").unlink(missing_ok=True)
mk("msgbatch_CUT", ["000020"])
cut = GOODREP(); del cut["verdict"]
cl3 = FakeClient()
fm3 = FillMsgs(); cl3.messages.create = fm3.create
cl3.messages.batches.store["msgbatch_CUT"] = batch_obj("msgbatch_CUT", "ended", [
    result("000020", text="===JSON_START===" + json.dumps(cut, ensure_ascii=False) + "===JSON_END===")])
M.pickup(cl3, "2026-09-05 03:00")
ok(not (S.OUT_DIR / "000020.json").exists() and fm3.sent == [], "잘린 글은 버리고 돈을 더 쓰지 않는다", f"calls={len(fm3.sent)}")
ok(S.fail_count("000020") >= 1, "실패로 세어 다음 run 이 다시 만든다")


print()
print("⑫ 그리드 동기화 — 화면 위 숫자는 리포트에서 나온다")
import _sync_grid as G                                  # noqa: E402
G.OUT = DATA / "valuation.js"

ok(S.grid_summary({"eps": 81, "bps": 3793, "roe_ttm": 2.1, "dps": 270.0}, [{"rev": 110}, {"rev": 100}])
   == {"eps": 81, "bps": 3793, "roe": 2.1, "dps": 270.0, "rev_g": 10.0}, "요약은 리포트 값을 그대로 옮긴다")
ok(S.grid_summary({"eps": None, "bps": 1}, []) == {"bps": 1}, "없는 값은 넣지 않는다")
ok(S.grid_summary({}, [{"rev": 10}, {"rev": 0}]) == {}, "작년 매출이 0이면 성장률을 만들지 않는다")

for p in S.OUT_DIR.glob("*.json"):
    p.unlink()
def grid_rep(tk, eps, bps):
    (S.OUT_DIR / f"{tk}.json").write_text(json.dumps(
        {"ticker": tk, "quant": {"valuation": {"eps": eps, "bps": bps}, "annual": []}}), encoding="utf-8")
grid_rep("451800", 81, 3793)        # 그리드는 80·3792 — 갱신돼야 한다
grid_rep("005930", 22626, 85688)    # 그리드와 같다 — 날짜까지 그대로여야 한다
grid_rep("000020", 5, 50)           # 그리드에 없다 — 새로 들어와야 한다
G.OUT.write_text("// x\nwindow.KOS_VALUATION = " + json.dumps({
    "asOf": "2026-09-04 10:00", "dataDate": "20260904", "count": 3,
    "stocks": {"451800": {"eps": 80, "bps": 3792, "_v": "r8", "_d": "2026-09-04"},
               "005930": {"eps": 22626, "bps": 85688, "_v": "r8", "_d": "2026-08-01"},
               "999999": {"eps": 1, "_v": "r8", "_d": "2026-08-01"}}}) + ";\n", encoding="utf-8")
G.main()
got = json.loads(G.OUT.read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
gs, TD = got["stocks"], S.today_kst().isoformat()
ok(gs["451800"] == {"eps": 81, "bps": 3793, "_v": "r8", "_d": TD}, "달라진 종목은 리포트 값으로", str(gs["451800"]))
ok(gs["005930"]["_d"] == "2026-08-01", "값이 같으면 날짜도 건드리지 않는다", str(gs["005930"]))
ok(gs["000020"] == {"eps": 5, "bps": 50, "_v": "r8", "_d": TD}, "리포트만 있던 종목이 들어온다", str(gs.get("000020")))
ok(gs["999999"] == {"eps": 1, "_v": "r8", "_d": "2026-08-01"}, "리포트 없는 종목은 그대로 둔다")
ok(got["dataDate"] == "20260904" and got["count"] == 4 and got["asOf"] != "2026-09-04 10:00",
   "나머지는 지키고 개수·시각만 갱신", f"count={got['count']} asOf={got['asOf']}")
before = G.OUT.read_text(encoding="utf-8")
G.main()
ok(G.OUT.read_text(encoding="utf-8") == before, "바뀐 값이 없으면 파일을 다시 쓰지 않는다")
G.OUT.write_text("망가진 파일", encoding="utf-8")
G.main()
ok(G.OUT.read_text(encoding="utf-8") == "망가진 파일", "못 읽는 그리드는 건드리지 않는다")


print()
print("⑬ 계정이 막힌 날 — 바깥 탓을 종목 탓으로 적지 않는다")
import anthropic                                        # noqa: E402

def _err(cls, msg, status=400):
    """anthropic 예외를 만든다 — 생성자 시그니처가 판마다 달라 우회한다."""
    e = cls.__new__(cls)
    Exception.__init__(e, msg)
    e.status_code = status
    return e

CREDIT = _err(anthropic.BadRequestError,
              "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
              "'message': 'Your credit balance is too low to access the Anthropic API.'}}")
BADCONTENT = _err(anthropic.BadRequestError, "Error code: 400 - messages.0: too long")
ok(M._api_unavailable(CREDIT) and M._no_credit(CREDIT), "잔액 부족은 '바깥이 막힘'")
ok(not M._api_unavailable(BADCONTENT) and not M._no_credit(BADCONTENT), "내용 탓 400 은 종목 문제")
ok(M._api_unavailable(_err(anthropic.InternalServerError, "boom", 500)), "5xx 도 바깥이 막힘")
ok(not M._api_unavailable(ValueError("json")), "파싱 오류는 종목 문제")

# 마커는 날짜라서 다음 날 저절로 풀린다
S.mark_credit_exhausted("테스트")
ok(S.credit_exhausted_today(), "마커를 남기면 오늘은 막힌 것으로 본다")
S.CREDIT_FILE.write_text("2026-09-01\n", encoding="utf-8")
ok(not S.credit_exhausted_today(), "어제 날짜 마커는 오늘을 막지 않는다")

# submit 은 DART 를 부르기 전에 마커부터 본다 — run 하나가 600 호출을 태우지 않게
S.mark_credit_exhausted("테스트")
called = []
REAL_PICK = M.pick_targets
M.pick_targets = lambda *a, **k: (called.append("dart"), ({}, []))[1]
r = M.submit(types.SimpleNamespace(), "2026-09-05 10:00")
ok(r.get("no_credit") and called == [], "잔액 마커가 오늘이면 정량 수집도 하지 않는다", str(called))
M.pick_targets = REAL_PICK
S.CREDIT_FILE.unlink(missing_ok=True)

# 회수 중에 막히면 — 실패로 세지 않고, 배치를 버리지도 않는다
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()
(S.OUT_DIR / "000020.json").unlink(missing_ok=True)
S.clear_fail("000020")
mk("msgbatch_NOCREDIT", ["000020"])
noen = GOODREP()
for x in noen["bull"]:
    x["title"]["en"] = ""; x["body"]["en"] = ""
class DeadMsgs:
    def create(self, **kw):
        raise CREDIT
cl4 = FakeClient(); cl4.messages.create = DeadMsgs().create
cl4.messages.batches.store["msgbatch_NOCREDIT"] = batch_obj("msgbatch_NOCREDIT", "ended", [
    result("000020", text="===JSON_START===" + json.dumps(noen, ensure_ascii=False) + "===JSON_END===")])
try:
    M.pickup(cl4, "2026-09-05 10:00")
    raised = None
except M.ApiUnavailable as e:
    raised = e
except SystemExit as e:
    raised = e
ok(isinstance(raised, M.ApiUnavailable), "회수 중 잔액이 막히면 ApiUnavailable 로 멈춘다", type(raised).__name__)
ok(S.fail_count("000020") == 0, "그 종목에 실패를 적지 않는다", str(S.fail_count("000020")))
st = json.loads((S.BATCH_DIR / "msgbatch_NOCREDIT.json").read_text(encoding="utf-8"))
ok(S.is_pending(st) and "abandoned" not in st and "collected" not in st,
   "배치는 그대로 둔다 — 충전 뒤 다시 받는다", str(sorted(st)))
ok(S.credit_exhausted_today(), "회수 중 감지해도 마커를 남긴다")
S.CREDIT_FILE.unlink(missing_ok=True)
for p in S.BATCH_DIR.glob("*.json"):
    p.unlink()

print()
print(f"통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
