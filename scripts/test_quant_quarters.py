#!/usr/bin/env python3
"""분기 실적 창(window)·TTM 회귀 검증 — DART 없이 가짜 누적 데이터로 돌린다.

  python3 scripts/test_quant_quarters.py

이 테스트가 있는 이유: 분기 표가 한때 (전년 Q1~Q4 + 올해 Q1) 로 고정돼 있었다.
1분기 시즌에는 그게 정답이라 아무도 눈치채지 못했고, 반기보고서가 나온 뒤에야
2026년 2분기가 통째로 빠진 게 드러났다. 같은 일이 3분기·연초에 반복되지 않도록
네 시즌을 전부 고정해 둔다.

확인하려는 것
  1) 어느 시즌이든(1분기·반기·3분기·연초) 최신 분기까지 표에 들어오는가
  2) TTM 이 '전년 연간 − 전년 같은 기간 + 올해 같은 기간' 으로 계산되는가
  3) 분기 표가 항상 시간순 연속 5개인가
"""
import sys, types, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for name in ("anthropic", "OpenDartReader"):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
sys.modules["anthropic"].Anthropic = object

import generate_reports_v2 as M                                  # noqa: E402

CUR = 2026
REAL_DATE = datetime.date
M.datetime.date = type("D", (), {"today": staticmethod(lambda: REAL_DATE(CUR, 8, 15))})

# 분기별 '단일 분기' 실적(원). 여기서 누적을 만들어 DART 흉내를 낸다.
TRUE = {
    (2024, 1): 100, (2024, 2): 200, (2024, 3): 300, (2024, 4): 400,
    (2025, 1): 110, (2025, 2): 220, (2025, 3): 330, (2025, 4): 440,
    (2026, 1): 150, (2026, 2): 260, (2026, 3): 370, (2026, 4): 480,
}
UNIT = 1_000_000_000
CODE_Q = {"11013": 1, "11012": 2, "11014": 3, "11011": 4}


def fy(year):
    return sum(TRUE[(year, q)] for q in (1, 2, 3, 4)) * UNIT


def make_fin(available, fs_map=None, cum_override=None):
    """available: {(year, code)} — 그 시점까지 제출된 보고서만 존재한다.
    fs_map: {(year, code): "CFS"|"OFS"} — 연결/별도 기준을 일부러 어긋내 볼 때 쓴다.
    cum_override: {(year, code): 누적값} — 누적이 깨진 공시를 흉내 낼 때 쓴다."""
    def _fin(dart, ticker, year, reprt):
        if (year, reprt) not in available:
            return None
        upto = CODE_Q[reprt]
        cum = sum(TRUE[(year, q)] for q in range(1, upto + 1)) * UNIT
        if cum_override and (year, reprt) in cum_override:
            cum = cum_override[(year, reprt)]
        eq = 5000 * UNIT
        return {
            "_fs": (fs_map or {}).get((year, reprt), "CFS"),
            "rev": {"amt": cum * 10, "add": cum * 10},
            "op": {"amt": cum, "add": cum},
            "np": {"amt": cum, "add": cum},
            "np_owner": {"amt": cum, "add": cum},
            "eps_basic": {"amt": cum // UNIT, "add": cum // UNIT},
            "equity": {"amt": eq, "add": None},
            "equity_owner": {"amt": eq, "add": None},
            "liab": {"amt": eq, "add": None},
            "cfo": {"amt": cum, "add": cum},
            "assets": {"amt": eq * 2, "add": None},
        }
    return _fin


def run(label, available, expect_last, expect_ttm_window, fs_map=None,
        cum_override=None, expect_rev_none=(), expect_all_positive=True):
    M._fin_all = make_fin(available, fs_map, cum_override)
    M.dart_total_shares = lambda d, t: 1_000_000
    M.dart_dps = lambda d, t: None
    M.g._safe_finstate = lambda *a, **k: None
    M.g._extract_fin = lambda *a, **k: None
    M.time.sleep = lambda *_: None

    q = M.collect_quant(None, "005930", None, {"price": 10000, "mcap": 10, "shares": 1_000_000})
    qs = [r["q"] for r in q["quarterly"]]
    ttm_w = q["valuation"].get("ttm_window")

    ok_last = qs and qs[-1] == expect_last
    ok_len = len(qs) == 5
    ok_seq = True
    for a, b in zip(qs, qs[1:]):
        ya, qa = int(a[:4]), int(a[-1]); yb, qb = int(b[:4]), int(b[-1])
        if (yb, qb) != ((ya, qa + 1) if qa < 4 else (ya + 1, 1)):
            ok_seq = False
    ok_ttm = ttm_w == expect_ttm_window

    # 값 검증: 표에 실린 영업이익이 '단일 분기' 실값과 같은가
    ok_val = True
    for r in q["quarterly"]:
        y, qi = int(r["q"][:4]), int(r["q"][-1])
        want = TRUE[(y, qi)] * UNIT
        if r["q"] in expect_rev_none:
            continue
        if r["op"] is not None and r["op"] != want:
            ok_val = False
    # 방어 로직: 못 믿을 분기는 실리지 않아야 한다
    got_none = {r["q"] for r in q["quarterly"] if r["rev"] is None}
    ok_guard = set(expect_rev_none) <= got_none
    ok_pos = (not expect_all_positive) or all(
        (r["rev"] is None or r["rev"] >= 0) for r in q["quarterly"])
    ok_val = ok_val and ok_guard and ok_pos

    mark = lambda b: "✓" if b else "✗"
    print(f"{mark(ok_last and ok_len and ok_seq and ok_ttm and ok_val)} {label}")
    print(f"    분기표 {qs}")
    print(f"    최신={qs[-1] if qs else '—'} {mark(ok_last)} · 5개 {mark(ok_len)} · 연속 {mark(ok_seq)}"
          f" · 값일치 {mark(ok_val)} · TTM창={ttm_w} {mark(ok_ttm)}")
    return ok_last and ok_len and ok_seq and ok_ttm and ok_val


A = set()
for y in (2024, 2025):
    for c in ("11013", "11012", "11014", "11011"):
        A.add((y, c))

cases = [
    ("① 1분기 시즌 (5월) — 올해 1분기까지",
     A | {(2026, "11013")}, "2026Q1", "2025Q2~2026Q1"),
    ("② 반기 시즌 (8월) — 올해 반기까지  ★지금 상황",
     A | {(2026, "11013"), (2026, "11012")}, "2026Q2", "2025Q3~2026Q2"),
    ("③ 3분기 시즌 (11월) — 올해 3분기까지",
     A | {(2026, "11013"), (2026, "11012"), (2026, "11014")}, "2026Q3", "2025Q4~2026Q3"),
    ("④ 연초 (2월) — 올해 보고서 아직 없음",
     A, "2025Q4", "2025Q1~2025Q4"),
    # ⑤ 반기보고서만 별도(OFS)로 잡힌 경우 — 1분기(연결)와 빼면 거짓이 된다
    # 반기가 별도(OFS)로만 잡히면 1분기(연결)와 뺄 수 없다 → 표도 TTM 도 1분기에 머문다.
    # 표는 1분기까지인데 PER 만 반기 기준이 되는 어긋남이 없어야 한다.
    ("⑤ 연결/별도가 섞이면 표도 TTM 도 그 분기를 쓰지 않는다",
     A | {(2026, "11013"), (2026, "11012")}, "2026Q1", "2025Q2~2026Q1",
     {(2026, "11012"): "OFS"}),
    # ⑥ 사업보고서 연간이 3분기 누적보다 작은 경우(상상인 038540 실제 사례)
    ("⑥ 음수로 튀는 분기 매출은 싣지 않는다",
     A, "2025Q4", "2025Q1~2025Q4", None,
     {(2025, "11011"): 1 * UNIT}, {"2025Q4"}),
]
print("=" * 66)
allok = all(run(*c) for c in cases)
print("=" * 66)
print("전체:", "통과 ✓" if allok else "실패 ✗")
sys.exit(0 if allok else 1)
