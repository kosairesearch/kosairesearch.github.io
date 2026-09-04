#!/usr/bin/env python3
"""검증기를 검증한다 — 일부러 망가뜨린 값을 넣고 진짜로 걸리는지 본다.

왜 필요한가
-----------
검사가 '0건 통과' 를 내면 두 가지 중 하나다. 정말 멀쩡하거나, 검사가 아무것도
안 보고 있거나. 둘은 결과가 똑같이 생겼다.

실제로 이 작업에서 그런 일이 세 번 있었다.
  · 시가총액을 DART 발행총수로 곱해서 31종목이 걸렸다 — 시가총액은 시장
    주식수로 만들어진 값이었다. 전부 오탐이었다.
  · 영업이익률 2.2 를 2.157 과 비교해 24종목이 걸렸다 — 반올림이었다.
  · TTM 을 '마지막 4개 분기' 와 맞대 58종목이 걸렸다 — 창에 적힌 기간과
    다른 기간을 더하고 있었다.
셋 다 검사가 틀린 것이었지 데이터가 틀린 게 아니었다.

그래서 반대로도 확인한다. 멀쩡한 리포트를 가져다 한 군데씩 망가뜨리고,
망가뜨린 그 항목이 걸리는지 본다. 안 걸리면 그 검사는 없는 것과 같다.

두 방향을 다 본다
  ① 망가뜨렸는데 안 걸린다  → 검사가 헛돌고 있다(제일 나쁘다)
  ② 안 망가뜨렸는데 걸린다  → 오탐. 경보가 늘 울리면 아무도 안 본다

  실행:  python3 scripts/tests/verify_numbers_test.py
"""
import copy
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verify_numbers as V           # noqa: E402

REPORTS = ROOT / "data" / "reports_v2"

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


def findings(j, grid=None):
    c = V.context(j.get("ticker") or "000000", j, grid or {})
    out = []
    for _code, _desc, fn in V.CHECKS:
        out.extend(fn(c))
    return out


def codes(j, grid=None, verdict=V.ERROR):
    """판정이 verdict 인 검사 코드들."""
    return {f.code for f in findings(j, grid) if f.verdict == verdict}


def any_codes(j, grid=None):
    """판정과 무관하게 '무언가 걸린' 검사 코드들.

    망가뜨린 걸 찾았는지 볼 때는 판정을 가리면 안 된다. 발행총수를 반으로
    줄였을 때 검사는 제대로 걸렸는데 판정이 '확인불가' 라 못 본 적이 있다 —
    검사가 아니라 시험이 눈을 감고 있었던 것이다."""
    return {f.code for f in findings(j, grid)}


def load(tk):
    return json.loads((REPORTS / f"{tk}.json").read_text(encoding="utf-8"))


def clean_tickers(n):
    """지금 아무 검사에도 안 걸리는 종목들 — 망가뜨릴 바탕으로 쓴다."""
    out = []
    for f in sorted(REPORTS.glob("*.json")):
        if not re.fullmatch(r"\d{6}", f.stem):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        v = (j.get("quant") or {}).get("valuation") or {}
        # 망가뜨릴 재료가 다 있어야 시험이 성립한다
        if not all(v.get(k) for k in ("price", "eps", "bps", "per", "pbr",
                                      "mcap", "shares", "total_shares", "ttm_np_owner")):
            continue
        if not [a for a in (j.get("quant") or {}).get("annual") or [] if a.get("rev")]:
            continue
        if codes(j):
            continue
        out.append((f.stem, j))
        if len(out) >= n:
            break
    return out


print("\n══ 바탕 고르기 ══")
base = clean_tickers(6)
ok(len(base) >= 5, "지금 아무 오류도 없는 종목을 바탕으로 확보",
   ", ".join(f"{j.get('name')}({tk})" for tk, j in base))
if len(base) < 3:
    print("바탕이 모자라 시험을 진행할 수 없다")
    sys.exit(1)


# ── ① 안 망가뜨리면 안 걸려야 한다 ──────────────────────────────────────
print("\n══ ① 멀쩡한 것에 경보가 울리지 않는가 ══")
for tk, j in base:
    ok(not codes(j), f"{j.get('name')}({tk}) 그대로면 오류 0건")


# ── ② 망가뜨리면 걸려야 한다 ────────────────────────────────────────────
# (설명, 어떻게 망가뜨리나, 걸려야 하는 검사 코드들 중 하나)
def m_val(key, fn):
    def go(j):
        v = j["quant"]["valuation"]
        if not v.get(key):          # None 도 0 도 망가뜨릴 수 없다
            return False
        v[key] = fn(v[key])
        return True
    return go


def m_annual(key, fn, idx=0):
    def go(j):
        a = [x for x in j["quant"]["annual"] if isinstance(x, dict)]
        if len(a) <= idx or not a[idx].get(key):
            return False
        a[idx][key] = fn(a[idx][key])
        return True
    return go


def m_nci(j):
    a = [x for x in j["quant"]["annual"] if isinstance(x, dict)]
    if not a:
        return False
    a[0]["equity_owner"] = (a[0].get("equity") or 0) * 0.5
    a[0]["equity_nci"] = (a[0].get("equity") or 0) * 0.1     # 합이 총계와 안 맞게
    return True


def m_ttm_window(j):
    v = j["quant"]["valuation"]
    qs = [x.get("q") for x in j["quant"].get("quarterly") or [] if x.get("q")]
    if len(qs) < 5:
        return False
    v["ttm_window"] = f"{qs[0]}~{qs[-2]}"                    # 한 분기 뒤로 민다
    return True


MUTATIONS = [
    ("BPS 를 2배로 부풀린다", m_val("bps", lambda x: x * 2), {"BPS수준", "BPS분모", "PBR항등"}),
    ("BPS 를 절반으로 줄인다", m_val("bps", lambda x: max(1, x // 2)), {"BPS수준", "BPS분모", "PBR항등"}),
    ("BPS 를 10배로", m_val("bps", lambda x: x * 10), {"BPS수준", "BPS분모", "PBR항등"}),
    ("EPS 부호를 뒤집는다", m_val("eps", lambda x: -x), {"EPS부호", "PER항등"}),
    ("EPS 를 10배로", m_val("eps", lambda x: x * 10), {"EPS자릿수", "PER항등"}),
    ("EPS 를 1/10 로", m_val("eps", lambda x: max(1, x // 10)), {"EPS자릿수", "PER항등"}),
    ("PER 을 2배로", m_val("per", lambda x: x * 2), {"PER항등"}),
    ("PER 을 0.5배로", m_val("per", lambda x: x * 0.5), {"PER항등"}),
    ("PBR 을 3배로", m_val("pbr", lambda x: x * 3), {"PBR항등"}),
    ("PBR 을 0.3배로", m_val("pbr", lambda x: x * 0.3), {"PBR항등"}),
    ("주가만 2배로 (PER·PBR 은 그대로)", m_val("price", lambda x: x * 2),
     {"PER항등", "PBR항등", "시총불일치"}),
    ("시가총액을 2배로", m_val("mcap", lambda x: x * 2), {"시총불일치"}),
    ("시가총액을 0.7배로", m_val("mcap", lambda x: x * 0.7), {"시총불일치"}),
    ("시장주식수를 1.5배로", m_val("shares", lambda x: int(x * 1.5)), {"시총불일치"}),
    ("발행총수를 가중평균의 3배로",
     lambda j: (j["quant"]["valuation"].__setitem__(
         "total_shares", int((j["quant"]["valuation"].get("wavg_shares") or 0) * 3)),
         bool(j["quant"]["valuation"].get("wavg_shares")))[1],
     {"주식수중복", "주식수출처"}),
    ("DART 발행총수만 절반으로", m_val("total_shares", lambda x: x // 2),
     {"주식수출처", "BPS분모", "분모불일치"}),
    ("배당금을 2배로", m_val("dps", lambda x: x * 2), {"배당률"}),
    ("배당수익률만 3배로", m_val("div", lambda x: x * 3), {"배당률"}),
    ("TTM 순이익 부호를 뒤집는다", m_val("ttm_np_owner", lambda x: -x),
     {"ROE부호", "TTM분기합", "EPS부호", "TTM연간불일치"}),
    ("TTM 순이익을 3배로", m_val("ttm_np_owner", lambda x: x * 3),
     {"TTM분기합", "EPS자릿수", "TTM연간불일치"}),
    ("ROE 부호를 뒤집는다", m_val("roe_ttm", lambda x: -x), {"ROE부호"}),
    ("ROE 를 1000% 로", m_val("roe_ttm", lambda _: 1000.0), {"ROE과대", "ROE부호"}),
    ("TTM 창을 한 분기 뒤로 민다", m_ttm_window, {"TTM창낡음", "TTM분기합", "TTM연간불일치"}),
    ("연간 영업이익률을 2배로", m_annual("opm", lambda x: x * 2), {"연간영업이익률"}),
    ("연간 부채비율을 2배로", m_annual("debt_ratio", lambda x: x * 2), {"연간부채비율"}),
    ("연간 ROE 를 3배로", m_annual("roe", lambda x: x * 3), {"연간ROE"}),
    ("연간 매출을 100배로", m_annual("rev", lambda x: x * 100),
     {"매출급변", "연간영업이익률"}),
    ("연간 매출을 1/100 로", m_annual("rev", lambda x: x / 100),
     {"매출급변", "연간영업이익률"}),
    ("연간 자본총계를 100배로", m_annual("equity", lambda x: x * 100),
     {"자본총계급변", "연간부채비율", "자본항등"}),
    ("비지배지분을 총계와 안 맞게 바꾼다", m_nci, {"자본항등", "연간ROE", "BPS분모", "BPS수준"}),
    ("연간 영업이익만 3배로", m_annual("op", lambda x: x * 3), {"연간영업이익률"}),
    ("연간 부채만 5배로", m_annual("liab", lambda x: x * 5), {"연간부채비율"}),
    ("연간 지배순이익만 4배로", m_annual("np_owner", lambda x: x * 4), {"연간ROE"}),
    ("연간 연도를 뒤죽박죽으로", m_annual("year", lambda x: x - 5),
     {"연간연도순서", "연간연도구멍", "TTM연간불일치"}),
    ("연간 첫 줄 연도를 두 번째와 같게", m_annual("year", lambda x: x - 1),
     {"연간연도순서", "연간연도중복", "TTM연간불일치"}),
]

print(f"\n══ ② 망가뜨리면 걸리는가 ({len(MUTATIONS)}가지 × 바탕 {len(base)}종목) ══")
for label, mut, want in MUTATIONS:
    caught = tried = 0
    missed_on = []
    for tk, j in base:
        mj = copy.deepcopy(j)
        try:
            applied = mut(mj)
        except Exception:
            applied = False
        if applied is False:
            continue
        tried += 1
        got = any_codes(mj)
        if got & want:
            caught += 1
        else:
            missed_on.append(f"{mj.get('name')}({tk}){'→' + ','.join(sorted(got)) if got else '→아무것도'}")
    if tried == 0:
        ok(False, label, "망가뜨릴 재료가 있는 바탕이 없다")
    else:
        ok(caught == tried, label,
           f"{caught}/{tried} 걸림" + (f" · 놓침: {'; '.join(missed_on[:2])}" if missed_on else ""))


# ── ③ 그리드 어긋남 ─────────────────────────────────────────────────────
print("\n══ ③ 화면 그리드가 리포트와 어긋나면 걸리는가 ══")
for tk, j in base[:3]:
    v = (j.get("quant") or {}).get("valuation") or {}
    grid = {tk: {"eps": (v.get("eps") or 0) * 2, "bps": v.get("bps")}}
    jj = copy.deepcopy(j)
    jj["ticker"] = tk
    ok("그리드동기" in codes(jj, grid), f"{j.get('name')}({tk}) 그리드 EPS 를 2배로 바꾸면 걸린다")


# ── ④ 도구 자체 ─────────────────────────────────────────────────────────
print("\n══ ④ 허용오차 계산이 맞는가 ══")
ok(V.decimals_of(0.4) == 1, "0.4 는 소수 1자리로 읽는다")
ok(V.decimals_of(0.4073) == 4, "0.4073 은 4자리")
ok(V.decimals_of(21.052) == 3, "21.052 는 3자리")
ok(V.decimals_of(5) == 0, "정수는 0자리")
ok(abs(V.round_tol(0.4) - 0.125) < 1e-9, "0.4 의 반올림 허용폭은 12.5%")
ok(abs(V.round_tol(0.4073) - 0.00005 / 0.4073) < 1e-9, "0.4073 의 허용폭은 0.012%")
ok(V.round_tol(0.4) > V.round_tol(0.4073), "자릿수가 적을수록 허용폭이 넓다")
ok(abs(V.rel(110, 100) - 0.1) < 1e-9, "rel(110,100)=0.1")
ok(V.rel(None, 100) is None, "값이 없으면 판단하지 않는다")
ok(V.rel(100, 0) is None, "0 으로는 나누지 않는다")

print("\n══ ⑤ 검사 목록이 다 등록돼 있는가 ══")
src = (ROOT / "scripts" / "verify_numbers.py").read_text(encoding="utf-8")
defined = set(re.findall(r"^def ([a-z]_\w+)\(c\):", src, re.M))
registered = set(re.findall(r"^\s+\(\"[^\"]+\", \"[^\"]+\", (\w+)\),", src, re.M))
ok(defined <= registered, "정의만 하고 CHECKS 에 안 넣은 검사가 없다",
   f"빠진 것: {sorted(defined - registered) or '없음'}")
ok(len(V.CHECKS) >= 15, f"검사 {len(V.CHECKS)}가지가 돌고 있다")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
