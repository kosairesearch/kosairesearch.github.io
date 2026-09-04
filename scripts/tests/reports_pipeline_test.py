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
            for k in ("rev", "op", "np", "np_owner", "np_nci", "cfo"):
                if r.get(k) is not None:
                    out[k] = {"amt": r[k], "add": r[k]}
            for k in ("equity", "equity_owner", "equity_nci", "liab", "assets"):
                if r.get(k) is not None:
                    out[k] = {"amt": r[k], "add": None}
            if r.get("eps") is not None:
                out["eps_basic"] = {"amt": r["eps"], "add": r["eps"]}
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
M.collect_all_quant = lambda targets, data: fake_collect_all(targets, data, no_data={"000040"})
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
M.collect_all_quant = lambda targets, data: fake_collect_all(targets, data, die_after=2)
r3 = M.submit(cl, "2026-09-05 02:02")
ok(r3["batch_id"] is not None and r3["unavailable"] is not None and len(r3["tickers"]) == 2, "한도에 걸려도 모은 만큼 주문 + unavailable", f"{r3['tickers']} {r3['unavailable']}")
ok(not (set(S.load_skip()) - {"000040"}), "한도로 못 모은 종목은 skip 이 아니다", str(S.load_skip()))
os.environ.pop("REPORT_FILL_TO")

# ═══ ⑦ 회수(pickup) ═════════════════════════════════════════════════════
print("⑦ pickup — 여러 배치, 파일별 한 번, 실패 횟수")
def report_text(tk):
    para = lambda s: {"ko": (s + " 문장이다. ") * 24, "en": (s + " sentence. ") * 24}
    item = {"title": {"ko": "a", "en": "a"}, "body": {"ko": "b" * 20, "en": "b" * 20}}
    rep = {"title": {"ko": f"{tk} 제목", "en": "title"}, "lead": {"ko": "lead", "en": "lead"},
           "keypoints": [{"ko": "k", "en": "k"}] * 4, "business": para("사업"), "earnings": para("실적"),
           "industry": para("산업"), "outlook": para("전망"), "valuation_comment": {"ko": "v", "en": "v"},
           "bull": [item] * 3, "bear": [item] * 3,
           "risks": [{"cat": {"ko": "c", "en": "c"}, "body": {"ko": "r" * 20, "en": "r" * 20}}] * 3,
           "checkpoints": [{"when": {"ko": "w", "en": "w"}, "what": {"ko": "x", "en": "x"}}] * 3,
           "verdict": {"body": {"ko": "종합 " * 50, "en": "verdict " * 30}}}
    return "===JSON_START===" + json.dumps(rep, ensure_ascii=False) + "===JSON_END==="
def result(tk, kind="succeeded", text=None):
    msg = types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text or report_text(tk), citations=None)])
    return types.SimpleNamespace(custom_id=tk, result=types.SimpleNamespace(type=kind, message=msg))
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
    result("005930"), result("000020", "errored"), result("000040", "expired"),
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

print()
print(f"통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
