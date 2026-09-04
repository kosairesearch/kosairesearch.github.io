#!/usr/bin/env python3
"""숫자 삼각 대조 — 한 값을 세 각도에서 재 보고, 어긋나면 어느 쪽이 틀렸는지 가른다.

왜 또 만드나
------------
check_valuation.py 는 '항등식' 을 본다 — PER×EPS 가 주가와 맞는가 같은 것.
그런데 EPS 가 틀렸으면 PER 도 같이 틀리게 계산돼서, 둘을 곱하면 도로 주가가
나온다. 틀린 값끼리 맞아떨어져 아무것도 안 걸린다.

실제로 삼성생명이 그랬다. BPS 806,537 이 KRX 공식값 349,293 의 2.3배인데
PBR×BPS=주가 는 완벽히 통과했다. 항등식만으로는 못 잡는다.

그래서 여기서는 같은 값을 **서로 다른 재료로** 만들어 맞대 본다.

무엇을 '결정적' 이라 부르는가
-----------------------------
BPS 를 두고 우리와 KRX 가 다를 때, 자본이 달라서인지 주식수가 달라서인지
결과만 봐서는 모른다. 그래서 나눗셈을 거꾸로 한다.

    KRX 가 나눈 주식수 = 최근 결산 지배지분 ÷ KRX 가 공표한 BPS

이렇게 역산한 주식수를 우리가 가진 세 개(발행총수·가중평균·시장데이터)와
대 보면, KRX 가 어느 것을 썼는지 딱 나온다. 우리가 다른 것을 썼으면 그건
방법론 차이가 아니라 분모를 잘못 고른 것이다 — 고쳐야 한다.

무엇이 '오류' 가 아닌가
-----------------------
우리 BPS 는 최근 '분기말' 자본, KRX 는 최근 '결산' 자본이다. 그 사이에 번
돈만큼 자본이 늘어 있는 게 정상이다. SK하이닉스는 2026 상반기에만 134조를
벌어 자본이 120조에서 262조가 됐다. 배수로 막으면 이런 회사가 걸린다.
그래서 크기가 아니라 '결산 자본 + 올해 번 돈' 으로 설명되는지를 본다.

설명이 안 돼도 바로 오류라고 하지 않는 자리가 있다. 보험·금융·지주·리츠는
기타포괄손익이 순이익의 수십 배로 움직인다. 삼성생명이 IFRS17 할인율 때문에
반년 만에 자본이 두 배가 됐는데, 그걸 오류로 보고 지웠다가 맞는 값을 날릴
뻔했다. 이 업종은 '확인불가' 로 남긴다 — 맞는 값을 지우는 검증은 없는 것만
못하다.

판정 세 갈래
    오류     — 어느 기준으로도 설명이 안 된다. 고쳐야 한다.
    방법론   — 기준 차이로 설명된다. 정상이다.
    확인불가 — 재료가 없거나, 업종 특성상 여기서 판단할 수 없다.

  실행
    python3 scripts/verify_numbers.py              표본 173종목
    python3 scripts/verify_numbers.py --all        전 종목
    python3 scripts/verify_numbers.py --ticker 000500
    python3 scripts/verify_numbers.py --strict     오류가 있으면 exit 1
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports_v2"
SAMPLE = ROOT / "data" / "verify_sample.json"
GRID = ROOT / "data" / "valuation.js"
OUT = ROOT / "data" / "verify_numbers.txt"

# 기타포괄손익이 순이익보다 크게 움직여, '자본 = 결산 + 번 돈' 이 성립하지
# 않는 업종. 보험은 IFRS17 할인율, 지주·금융은 보유 지분 평가손익 때문이다.
OCI_HEAVY = {"보험", "금융", "지주", "부동산·리츠"}

ERROR, METHOD, UNKNOWN = "오류", "방법론", "확인불가"


# ── 도구 ────────────────────────────────────────────────────────────────
def rel(a, b):
    """a 가 b 에서 벗어난 비율. 둘 다 있고 b 가 0 이 아니어야 한다."""
    if a is None or b is None or b == 0:
        return None
    return abs(a / b - 1)


def decimals_of(x):
    """저장된 수가 소수 몇째 자리까지 적혀 있나.

    자릿수를 고정으로 보면 안 된다. 같은 PBR 인데 어떤 리포트는 0.4 로,
    어떤 리포트는 0.4073 으로 저장돼 있다 — 만든 시기가 달라서다.
    0.4 는 참값이 0.35~0.45 라는 뜻이라 12.5% 까지 벌어질 수 있고,
    0.4073 은 0.012% 다. 같은 잣대를 대면 앞의 것이 매번 걸린다."""
    if x is None:
        return 0
    s = repr(float(x))
    if "e" in s or "E" in s:
        return 12
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def round_tol(stored, decimals=None):
    """반올림해 저장한 값이라면 이 정도 비율 오차는 반올림 몫이다.

    영업이익률을 2.157 로 계산해 2.2 로 저장하면 2% 어긋난 것처럼 보인다.
    작은 값일수록 반올림 한 칸이 차지하는 비율이 커진다 — 0.5 로 저장된 값은
    ±10% 다. 이걸 안 봐주면 멀쩡한 종목 수십 개가 매번 걸린다.

    decimals 를 안 주면 저장된 값에서 읽어낸다."""
    if not stored:
        return 1.0
    if decimals is None:
        decimals = decimals_of(stored)
    return (0.5 * 10 ** (-decimals)) / abs(stored)


def fmt(v, unit=""):
    if v is None:
        return "없음"
    if isinstance(v, float) and abs(v) < 1000:
        return f"{v:,.4g}{unit}"
    return f"{v:,.0f}{unit}"


def jo(v):
    if v is None:
        return "없음"
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:,.2f}조"
    if a >= 1e8:
        return f"{v/1e8:,.0f}억"
    return f"{v:,.0f}원"


class Finding:
    __slots__ = ("tk", "name", "sector", "code", "verdict", "msg")

    def __init__(self, tk, name, sector, code, verdict, msg):
        self.tk, self.name, self.sector = tk, name, sector
        self.code, self.verdict, self.msg = code, verdict, msg

    def line(self):
        return f"  [{self.code}] {self.name}({self.tk}) · {self.sector} — {self.msg}"


# ── 각도별 검사 ─────────────────────────────────────────────────────────
def a_bps_denominator(c):
    """KRX 가 나눈 주식수를 역산해, 우리가 같은 것으로 나눴는지 본다.

    이게 이 파일에서 가장 결정적인 검사다. 자본이 달라서 어긋난 것인지
    주식수가 달라서인지를 결과만으로는 못 가리는데, 거꾸로 나누면 가려진다."""
    krx, fy_eqo, ours_den = c["bps_krx"], c["fy_eqo"], c["bps_denom"]
    if not (krx and krx > 0 and fy_eqo and fy_eqo > 0 and ours_den):
        return []
    # 결과가 KRX 와 맞으면 어느 분모를 썼든 볼 일이 아니다.
    #
    # 처음에는 이 조건 없이 '우리가 어느 필드로 나눴나' 만 봤다. 그래서 값을
    # 바로잡은 뒤에도 wavg_shares 필드는 그대로라 계속 걸렸다 — 58종목을
    # 고쳤는데 경보는 2건만 줄었다. 검사는 필드가 아니라 결과를 봐야 한다.
    if c["bps"] and rel(c["bps"], krx) is not None and rel(c["bps"], krx) <= 0.15:
        return []
    implied = fy_eqo / krx                      # KRX 가 쓴 주식수
    cands = {k: v for k, v in c["denoms"].items() if v}
    if not cands:
        return []
    best = min(cands, key=lambda k: abs(cands[k] / implied - 1))
    gap_best = abs(cands[best] / implied - 1)
    gap_ours = abs(ours_den / implied - 1)

    # KRX 가 쓴 주식수가 우리 후보 중 하나와 딱 맞는데, 우리는 다른 걸 썼다
    if gap_best <= 0.03 and gap_ours > 0.08 and best != c["denom_name"]:
        return [Finding(c["tk"], c["name"], c["sector"], "BPS분모", ERROR,
                        f"KRX 는 {fmt(implied)}주로 나눴다(={best} {fmt(cands[best])}). "
                        f"우리는 {c['denom_name']} {fmt(ours_den)} 로 나눠 BPS "
                        f"{fmt(c['bps'])} — KRX 는 {fmt(krx)}. 분모가 {ours_den/implied:.2f}배다")]
    # 어느 후보로도 KRX 를 재현 못 하면 자본 쪽이 다르다는 뜻 — 판단 보류
    if gap_best > 0.15:
        return [Finding(c["tk"], c["name"], c["sector"], "BPS역산불가", UNKNOWN,
                        f"KRX BPS {fmt(krx)} 를 내려면 {fmt(implied)}주여야 하는데 "
                        f"우리 주식수 후보({', '.join(f'{k} {fmt(v)}' for k, v in cands.items())}) "
                        f"어느 것과도 안 맞는다")]
    return []


def b_bps_level(c):
    """우리 BPS 가 뜻하는 분기말 자본이 '결산 자본 + 올해 번 돈' 으로 설명되는가."""
    bps, den, fy = c["bps"], c["bps_denom"], c["fy_eqo"]
    krx = c["bps_krx"]
    if not (bps and den and fy and fy > 0):
        return []
    if krx and rel(bps, krx) is not None and rel(bps, krx) <= 0.15:
        return []                               # KRX 와 맞으면 볼 것 없다
    implied_eq = bps * den
    explained = fy + (c["ytd_np"] or 0)
    if explained <= 0:
        return []
    mult = implied_eq / explained
    if 0.5 <= mult <= 2.0:
        return [Finding(c["tk"], c["name"], c["sector"], "BPS분기차", METHOD,
                        f"우리 {fmt(bps)} vs KRX {fmt(krx)} — 분기말 자본 {jo(implied_eq)} 이 "
                        f"결산 {jo(fy)} + 올해 순이익 {jo(c['ytd_np'])} 로 설명된다({mult:.2f}배)")]
    if c["sector"] in OCI_HEAVY:
        return [Finding(c["tk"], c["name"], c["sector"], "BPS기타포괄", UNKNOWN,
                        f"우리 {fmt(bps)}(자본 {jo(implied_eq)}) 이 결산+이익 {jo(explained)} 의 "
                        f"{mult:.1f}배 — 이 업종은 기타포괄손익으로 흔들려 여기서 못 가린다")]
    return [Finding(c["tk"], c["name"], c["sector"], "BPS수준", ERROR,
                    f"우리 {fmt(bps)} 는 분기말 자본 {jo(implied_eq)} 을 뜻하는데, 결산 {jo(fy)} 에 "
                    f"올해 순이익 {jo(c['ytd_np'])} 을 더해도 {jo(explained)} 다({mult:.1f}배). "
                    f"KRX 는 {fmt(krx)}")]


def c_eps_formula(c):
    """저장된 EPS 가 어떤 나눗셈으로 나온 값인지 찾아본다.

    EPS 는 두 경로로 만들어진다 — 회사가 공시한 기본주당이익을 굴린 값과,
    TTM 순이익을 주식수로 나눈 값. 앞의 것은 회사가 쓴 가중평균주식수를
    따르므로 우리 주식수로는 재현이 안 된다. 재현이 안 된다고 오류가 아니다.
    그러나 부호가 뒤집히거나 자릿수가 다르면 그건 어느 경로로도 설명이 안 된다."""
    eps, np_ttm = c["eps"], c["ttm_np"]
    if eps is None or not np_ttm:
        return []
    cands = {k: v for k, v in c["denoms"].items() if v}
    for k, den in cands.items():
        if rel(eps, np_ttm / den) is not None and rel(eps, np_ttm / den) <= 0.02:
            return []                           # 어느 주식수로든 재현된다
    base = np_ttm / (c["total_shares"] or c["wavg_shares"] or 1)
    if (eps > 0) != (base > 0) and abs(base) > 1:
        return [Finding(c["tk"], c["name"], c["sector"], "EPS부호", ERROR,
                        f"저장 EPS {fmt(eps)} 인데 TTM 순이익 {jo(np_ttm)} 을 주식수로 나누면 "
                        f"{fmt(base)} — 부호가 반대다")]
    if abs(base) < 1 or eps == 0:
        return [Finding(c["tk"], c["name"], c["sector"], "EPS영에가까움", METHOD,
                        f"TTM순이익÷주식수 {fmt(base)} — 정수로 저장하면 {int(base)} 다")]
    if base and not (1 / 3.3 <= abs(eps / base) <= 3.3):
        return [Finding(c["tk"], c["name"], c["sector"], "EPS자릿수", ERROR,
                        f"저장 EPS {fmt(eps)} 가 TTM순이익÷주식수 {fmt(base)} 의 "
                        f"{abs(eps/base):.1f}배 — 어느 경로로도 설명이 안 된다")]
    return [Finding(c["tk"], c["name"], c["sector"], "EPS공시경로", METHOD,
                    f"저장 EPS {fmt(eps)} 는 우리 주식수로 재현되지 않는다"
                    f"(÷발행총수 {fmt(base)}) — 회사 공시 기본주당이익을 굴린 값으로 보인다")]


def d_identity(c):
    """PER×EPS 와 PBR×BPS 가 주가와 맞는가. 저장 자릿수의 반올림 몫은 봐 준다."""
    out, price = [], c["price"]
    if not price:
        return out
    for nm, a, b in (("PER", c["per"], c["eps"]), ("PBR", c["pbr"], c["bps"])):
        if a and b:
            got = a * b
            # EPS·BPS 도 정수로 잘려 저장되므로 그 몫도 얹는다
            tol = max(0.005, round_tol(a) + (0.5 / abs(b) if b else 0))
            d = rel(got, price)
            if d is not None and d > tol:
                out.append(Finding(c["tk"], c["name"], c["sector"], f"{nm}항등", ERROR,
                                   f"{nm}×{'EPS' if nm=='PER' else 'BPS'}={fmt(got)} 인데 "
                                   f"주가는 {fmt(price)} ({d*100:.1f}% 차)"))
    return out


def e_denom_consistency(c):
    """EPS 와 BPS 가 같은 주식수로 나뉘었는가 — 다르면 PER 과 PBR 의 잣대가 다르다."""
    a, b = c["np_denom"], c["bps_denom"]
    if a and b and rel(a, b) and rel(a, b) > 0.001:
        return [Finding(c["tk"], c["name"], c["sector"], "분모불일치", ERROR,
                        f"EPS 는 {c['np_denom_name']} {fmt(a)}, BPS 는 {c['denom_name']} {fmt(b)}")]
    return []


def f_mcap_anchor(c):
    """시가총액 = 주가 × 시장데이터 주식수.

    시가총액은 우리가 계산한 게 아니라 시장데이터에서 받아온 값이라, 주식수의
    독립 증인이 된다. 여기서 어긋나면 받아온 값 자체가 깨진 것이다."""
    m, p, s = c["mcap"], c["price"], c["shares"]
    if not (m and p and s):
        return []
    calc = p * s / 1e12
    d = rel(m, calc)
    if d is not None and d > max(0.01, round_tol(m)):
        return [Finding(c["tk"], c["name"], c["sector"], "시총불일치", ERROR,
                        f"시가총액 {fmt(m)}조 인데 주가 {fmt(p)} × 시장주식수 {fmt(s)} = "
                        f"{calc:,.3f}조 ({d*100:.0f}% 차)")]
    return []


def g_share_sources(c):
    """시장데이터 주식수와 DART 발행총수가 크게 어긋나는가.

    액면변경·증자 뒤 한쪽만 갱신되면 여기서 벌어진다. EPS·BPS 는 DART 쪽으로
    나누고 시가총액은 시장 쪽으로 계산하므로, 벌어진 채 두면 화면 안에서
    서로 안 맞는 숫자가 나란히 놓인다."""
    s, t = c["shares"], c["total_shares"]
    if not (s and t):
        return []
    r = s / t
    if abs(r - 1) <= 0.10:
        return []
    clean = next((k for k in (2, 3, 4, 5, 10, 20, 50, 100)
                  if abs(r - k) < 0.02 or abs(r - 1 / k) < 0.02), None)
    live = c["eps"] is not None or c["bps"] is not None
    if not live:
        return []
    kind = f"정확히 {clean}배(액면변경)" if clean else "깔끔한 배수가 아니다(증자 등)"
    verdict = ERROR if clean else UNKNOWN
    return [Finding(c["tk"], c["name"], c["sector"], "주식수출처", verdict,
                    f"시장 {fmt(s)} vs DART {fmt(t)} = {r:.2f}배 — {kind}. "
                    f"EPS·BPS 가 살아 있다(EPS {fmt(c['eps'])} · BPS {fmt(c['bps'])})")]


def h_dividend(c):
    div, dps, p = c["div"], c["dps"], c["price"]
    if not (div and dps and p):
        return []
    calc = dps / p * 100
    tol = max(0.02, round_tol(div, 2))
    if rel(div, calc) and rel(div, calc) > tol:
        return [Finding(c["tk"], c["name"], c["sector"], "배당률", ERROR,
                        f"배당수익률 {fmt(div)}% 인데 DPS {fmt(dps)} ÷ 주가 {fmt(p)} = {calc:.2f}%")]
    return []


def i_annual_derived(c):
    """연간 표의 파생 지표가 같은 줄 재료와 맞는가.

    부채비율은 은행·보험·증권·리츠에서 수백~수천%가 정상이다. 크기로 막지 않고
    '같은 줄 재료로 계산한 값과 맞는가' 만 본다 — 그건 업종과 무관하게 참이다."""
    out = []
    for a in c["annual"][:3]:
        y = a.get("year")
        rev, op, np_o = a.get("rev"), a.get("op"), a.get("np_owner")
        eq, eq_o, li = a.get("equity"), a.get("equity_owner"), a.get("liab")
        for nm, stored, calc, dec, extra in (
            ("영업이익률", a.get("opm"), (op / rev * 100) if (op is not None and rev) else None, 1, 0.01),
            ("부채비율", a.get("debt_ratio"), (li / eq * 100) if (li is not None and eq) else None, 1, 0.01),
            ("ROE", a.get("roe"), (np_o / eq_o * 100) if (np_o is not None and eq_o) else None, 1, 0.05),
        ):
            if stored is None or calc is None:
                continue
            # 반올림 오차는 계산값에 대해 재야 한다. stored 로 나누면
            # 0.2(참값 0.1506)처럼 반올림으로 크게 뛴 값을 못 봐준다.
            tol = max(extra, (0.5 * 10 ** (-dec)) / abs(calc))
            d = rel(stored, calc)
            if d is not None and d > tol:
                out.append(Finding(c["tk"], c["name"], c["sector"], f"연간{nm}", ERROR,
                                   f"{y}년 {nm} {fmt(stored)} 인데 같은 줄 재료로는 {fmt(calc)} "
                                   f"(허용 {tol*100:.1f}%)"))
    return out


def j_equity_identity(c):
    """지배지분 + 비지배지분 = 자본총계.

    크기 비교로 하면 안 된다 — 자회사 결손으로 비지배지분이 음수면 지배지분이
    총계보다 커지는 게 정상이다. 항등식으로만 본다."""
    out = []
    for a in c["annual"][:3]:
        eo, nci, tot = a.get("equity_owner"), a.get("equity_nci"), a.get("equity")
        if eo is None or nci is None or tot is None:
            continue
        if abs((eo + nci) - tot) > abs(tot) * 0.01:
            out.append(Finding(c["tk"], c["name"], c["sector"], "자본항등", ERROR,
                               f"{a.get('year')}년 지배 {jo(eo)} + 비지배 {jo(nci)} "
                               f"≠ 자본총계 {jo(tot)} (차 {jo((eo+nci)-tot)})"))
    return out


def k_series_sanity(c):
    """연간 매출·자본이 해마다 자릿수로 튀는가 — 단위 오인의 흔적."""
    out = []
    for key, label in (("rev", "매출"), ("equity", "자본총계")):
        vals = [(a.get("year"), a.get(key)) for a in c["annual"] if a.get(key)]
        for (y1, v1), (y2, v2) in zip(vals, vals[1:]):
            if v1 and v2 and v2 != 0:
                r = abs(v1 / v2)
                if r > 9.5 or r < 1 / 9.5:
                    out.append(Finding(c["tk"], c["name"], c["sector"], f"{label}급변", UNKNOWN,
                                       f"{y2}년 {jo(v2)} → {y1}년 {jo(v1)} ({r:.1f}배)"))
    return out


def _qkey(s):
    m = re.fullmatch(r"(\d{4})Q(\d)", str(s or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def l_ttm_quarters(c):
    """TTM 순이익이 'ttm_window 에 적힌 그 분기들' 의 합과 맞는가.

    처음에는 '마지막 4개 분기' 를 더해서 맞대 봤는데 58종목이 걸렸다. 전부
    오탐이었다 — 어떤 종목은 TTM 창이 2025Q1~Q4 인데 화면 표에는 2026Q2 까지
    실려 있어서, 서로 다른 기간을 맞대고 있었던 것이다. 무엇을 더해야 하는지는
    창이 이미 말해 주고 있었다."""
    win, ttm = c["ttm_window"], c["ttm_np"]
    if not ttm or not win or "~" not in str(win):
        return []
    a, b = [_qkey(x) for x in str(win).split("~", 1)]
    if not (a and b):
        return []
    inside = [x["np_owner"] for x in c["quarterly"]
              if _qkey(x.get("q")) and a <= _qkey(x["q"]) <= b and x.get("np_owner") is not None]
    span = (b[0] - a[0]) * 4 + (b[1] - a[1]) + 1
    if len(inside) < span:
        return []                               # 창 안의 분기가 다 있지 않다 — 맞댈 수 없다
    s = sum(inside)
    if s == 0:
        return []
    d = rel(ttm, s)
    if d is not None and d > 0.10:
        return [Finding(c["tk"], c["name"], c["sector"], "TTM분기합", ERROR,
                        f"TTM 순이익 {jo(ttm)} 인데 창({win}) 안의 분기 합은 {jo(s)} ({d*100:.0f}% 차)")]
    return []


def q_ttm_vs_annual(c):
    """TTM 창이 딱 한 회계연도면, TTM 순이익은 그 해 연간 순이익과 같아야 한다.

    분기가 하나라도 비면 분기 합으로는 맞대 볼 수가 없다. 그런데 창이
    '2025Q1~2025Q4' 처럼 한 해를 통째로 가리키는 경우에는 연간 표에 그 답이
    이미 적혀 있다. 보해양조가 그랬다 — 창은 2025년 한 해인데 TTM 순이익은
    6.9억, 같은 리포트의 2025년 연간 순이익은 34.9억이었다."""
    win, ttm = c["ttm_window"], c["ttm_np"]
    if not ttm or not win or "~" not in str(win):
        return []
    a, b = [_qkey(x) for x in str(win).split("~", 1)]
    if not (a and b) or a[0] != b[0] or a[1] != 1 or b[1] != 4:
        return []                               # 한 회계연도 창이 아니다
    row = next((x for x in c["annual"] if x.get("year") == a[0]), None)
    ann = (row or {}).get("np_owner")
    if ann is None or ann == 0:
        return []
    d = rel(ttm, ann)
    if d is not None and d > 0.10:
        return [Finding(c["tk"], c["name"], c["sector"], "TTM연간불일치", ERROR,
                        f"TTM 창이 {win}(한 해 통째) 인데 TTM 순이익 {jo(ttm)} 이 "
                        f"같은 리포트의 {a[0]}년 연간 순이익 {jo(ann)} 과 다르다 ({d*100:.0f}% 차)")]
    return []


def p_ttm_stale(c):
    """TTM 창이 화면에 실린 최신 분기보다 뒤처져 있는가.

    카드에는 작년 실적으로 만든 PER 이 뜨고, 바로 아래 표에는 올해 분기가
    실려 있으면 같은 화면 안에서 두 시점이 섞인다. 최신 분기에 순이익이
    있는데도 안 쓴 것이면 우리가 안 쓴 것이고, 없으면 못 쓴 것이다."""
    win = c["ttm_window"]
    if not win or "~" not in str(win):
        return []
    end = _qkey(str(win).split("~", 1)[1])
    keys = [(_qkey(x.get("q")), x.get("np_owner")) for x in c["quarterly"]]
    keys = [(k, v) for k, v in keys if k]
    if not (end and keys):
        return []
    latest = max(k for k, _ in keys)
    if latest <= end:
        return []
    behind = (latest[0] - end[0]) * 4 + (latest[1] - end[1])

    # 최신 분기로 끝나는 4개 분기가 '빠짐없이' 있어야 새 TTM 을 만들 수 있다.
    #
    # 처음에는 '창 뒤쪽 분기에 순이익이 있으면 쓸 수 있었던 것' 으로 봤는데
    # 틀렸다. 보해양조는 2026Q1·Q2 순이익이 다 있지만 그 사이 2025Q3 이 비어
    # 있어서 2025Q3~2026Q2 를 못 만든다. 하나만 비어도 창 전체를 못 만든다.
    want = set()
    y, qn = latest
    for _ in range(4):
        want.add((y, qn))
        qn -= 1
        if qn == 0:
            y, qn = y - 1, 4
    have = {k for k, v in keys if v is not None}
    missing = sorted(want - have)
    if not missing:
        return [Finding(c["tk"], c["name"], c["sector"], "TTM창낡음", ERROR,
                        f"TTM 창이 {win} 인데 표에는 {latest[0]}Q{latest[1]} 까지 있고 "
                        f"최근 4개 분기 순이익이 빠짐없이 있다({behind}분기 뒤처짐) "
                        f"— 새 창으로 만들 수 있었다")]
    return [Finding(c["tk"], c["name"], c["sector"], "TTM창낡음", UNKNOWN,
                    f"TTM 창이 {win} 인데 표에는 {latest[0]}Q{latest[1]} 까지 있다"
                    f"({behind}분기 뒤처짐). "
                    f"{', '.join(f'{a}Q{b}' for a, b in missing)} 순이익이 비어 새 창을 못 만든다")]


def r_annual_years(c):
    """연간 표의 연도가 최근 것부터 한 해씩 내려가는가.

    변이 검사에서 연도를 뒤죽박죽으로 바꿔 넣었더니 아무 검사도 안 걸렸다.
    연도가 어긋나면 그 아래 모든 해석이 엉뚱한 해를 가리키게 된다."""
    ys = [a.get("year") for a in c["annual"] if a.get("year") is not None]
    if len(ys) < 2:
        return []
    if ys != sorted(ys, reverse=True):
        return [Finding(c["tk"], c["name"], c["sector"], "연간연도순서", ERROR,
                        f"연간 표의 연도가 내림차순이 아니다: {ys}")]
    dup = [y for y in set(ys) if ys.count(y) > 1]
    if dup:
        return [Finding(c["tk"], c["name"], c["sector"], "연간연도중복", ERROR,
                        f"연간 표에 같은 해가 두 번 있다: {sorted(dup)}")]
    gaps = [(a, b) for a, b in zip(ys, ys[1:]) if a - b != 1]
    if gaps:
        return [Finding(c["tk"], c["name"], c["sector"], "연간연도구멍", UNKNOWN,
                        f"연간 표의 해가 이어지지 않는다: {ys}")]
    return []


def m_roe(c):
    roe, np_o = c["roe_ttm"], c["ttm_np"]
    if roe is None or np_o is None:
        return []
    if (roe > 0) != (np_o > 0) and abs(roe) > 0.05:
        return [Finding(c["tk"], c["name"], c["sector"], "ROE부호", ERROR,
                        f"ROE {fmt(roe)}% 인데 TTM 순이익은 {jo(np_o)}")]
    if abs(roe) > 300:
        return [Finding(c["tk"], c["name"], c["sector"], "ROE과대", UNKNOWN,
                        f"ROE {fmt(roe)}% — 자본이 거의 없는 회사인지 확인 필요")]
    return []


def n_grid_sync(c):
    g = c["grid"]
    if not g:
        return []
    out = []
    for key in ("eps", "bps"):
        a, b = c[key], g.get(key)
        if a is not None and b is not None and rel(a, b) and rel(a, b) > 0.01:
            out.append(Finding(c["tk"], c["name"], c["sector"], "그리드동기", ERROR,
                               f"리포트 {key.upper()} {fmt(a)} vs 화면 그리드 {fmt(b)}"))
    return out


def o_share_multiple(c):
    """발행총수가 가중평균의 정수배 근처인가 — 중복 합산의 흔적."""
    t, w = c["total_shares"], c["wavg_shares"]
    if not (t and w):
        return []
    r = t / w
    for k in (2, 3, 4):
        if abs(r - k) < 0.02:
            return [Finding(c["tk"], c["name"], c["sector"], "주식수중복", ERROR,
                            f"발행총수 {fmt(t)} 가 가중평균 {fmt(w)} 의 정확히 {k}배")]
    return []


CHECKS = [
    ("BPS분모", "KRX 가 쓴 주식수를 역산해 우리 분모와 대 본다", a_bps_denominator),
    ("BPS수준", "BPS 가 결산 자본 + 올해 번 돈으로 설명되는가", b_bps_level),
    ("EPS경로", "EPS 가 어떤 나눗셈으로 나온 값인가", c_eps_formula),
    ("항등식", "PER×EPS · PBR×BPS 가 주가와 맞는가", d_identity),
    ("분모일치", "EPS 와 BPS 가 같은 주식수로 나뉘었는가", e_denom_consistency),
    ("시총닻", "시가총액이 주가 × 시장주식수와 맞는가", f_mcap_anchor),
    ("주식수출처", "시장 주식수와 DART 발행총수가 어긋나는가", g_share_sources),
    ("배당", "배당수익률이 DPS ÷ 주가와 맞는가", h_dividend),
    ("연간파생", "영업이익률·부채비율·ROE 가 같은 줄 재료와 맞는가", i_annual_derived),
    ("자본항등", "지배 + 비지배 = 자본총계", j_equity_identity),
    ("시계열", "연간 값이 자릿수로 튀는가", k_series_sanity),
    ("TTM분기합", "TTM 순이익이 창 안의 분기 합과 맞는가", l_ttm_quarters),
    ("TTM창낡음", "TTM 창이 최신 분기보다 뒤처졌는가", p_ttm_stale),
    ("TTM연간불일치", "한 해짜리 TTM 창이 그 해 연간 순이익과 맞는가", q_ttm_vs_annual),
    ("연간연도", "연간 표의 해가 내림차순으로 이어지는가", r_annual_years),
    ("ROE", "ROE 부호·크기", m_roe),
    ("그리드", "화면 그리드가 리포트와 같은가", n_grid_sync),
    ("주식수중복", "발행총수가 가중평균의 정수배인가", o_share_multiple),
]


# ── 재료 준비 ───────────────────────────────────────────────────────────
def load_grid():
    if not GRID.exists():
        return {}
    m = re.search(r"window\.KOS_VALUATION\s*=\s*(\{.*)", GRID.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(1).rstrip().rstrip(";")).get("stocks", {})
    except Exception:
        return {}


def context(tk, j, grid):
    q = j.get("quant") or {}
    v = q.get("valuation") or {}
    annual = [a for a in (q.get("annual") or []) if isinstance(a, dict)]
    quarterly = [x for x in (q.get("quarterly") or []) if isinstance(x, dict)]
    fy = annual[0] if annual else {}
    total_sh, wavg = v.get("total_shares"), v.get("wavg_shares")
    bps_denom = wavg or total_sh
    fy_eqo = fy.get("equity_owner") or fy.get("equity")

    # 올해 누적 지배순이익 — 결산 이후 자본이 얼마나 늘었을지 설명하는 재료
    ytd = None
    years = [str(x.get("q", ""))[:4] for x in quarterly if str(x.get("q", ""))[:4].isdigit()]
    if years:
        cur = max(years)
        if fy.get("year") is not None and int(cur) > int(fy["year"]):
            ytd = sum(x.get("np_owner") or 0 for x in quarterly
                      if str(x.get("q", "")).startswith(cur))
    return {
        "tk": tk, "name": j.get("name") or tk, "sector": j.get("sector") or "?",
        "price": v.get("price"), "mcap": v.get("mcap"),
        "per": v.get("per"), "eps": v.get("eps"),
        "pbr": v.get("pbr"), "bps": v.get("bps"),
        "bps_krx": v.get("bps_krx"), "pbr_krx": v.get("pbr_krx"),
        "roe_ttm": v.get("roe_ttm"), "ttm_np": v.get("ttm_np_owner"),
        "dps": v.get("dps"), "div": v.get("div"),
        "shares": v.get("shares"), "total_shares": total_sh, "wavg_shares": wavg,
        "bps_denom": bps_denom,
        "denom_name": "가중평균" if wavg else "발행총수",
        "np_denom": wavg or total_sh,
        "np_denom_name": "가중평균" if wavg else "발행총수",
        "denoms": {"발행총수": total_sh, "가중평균": wavg, "시장주식수": v.get("shares")},
        "fy_eqo": fy_eqo, "fy_year": fy.get("year"), "ytd_np": ytd,
        "fy_eps_basic": fy.get("eps_basic"),
        "ttm_window": v.get("ttm_window"),
        "annual": annual, "quarterly": quarterly,
        "grid": grid.get(tk) or {},
    }


def run(tickers, grid):
    findings, seen, missing = [], 0, []
    for tk in tickers:
        f = REPORTS / f"{tk}.json"
        if not f.exists():
            missing.append(tk)
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            findings.append(Finding(tk, tk, "?", "읽기실패", ERROR, str(e)[:80]))
            continue
        seen += 1
        c = context(tk, j, grid)
        for code, _desc, fn in CHECKS:
            try:
                findings.extend(fn(c))
            except Exception as e:
                findings.append(Finding(tk, c["name"], c["sector"], code, ERROR,
                                        f"검사가 터졌다: {e.__class__.__name__} {e}"))
    return findings, seen, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ticker")
    ap.add_argument("--strict", action="store_true", help="오류가 하나라도 있으면 exit 1")
    ap.add_argument("--max", type=int, default=None,
                    help="오류가 이 수를 넘으면 exit 1. 지금 남은 것은 리포트를 "
                         "다시 만들어야 없어지므로, 늘어나는 것만 막는다")
    ap.add_argument("--verdict", choices=[ERROR, METHOD, UNKNOWN])
    ap.add_argument("--code", help="이 검사 코드만")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    grid = load_grid()
    if args.ticker:
        tickers, scope = [args.ticker], f"{args.ticker} 한 종목"
    elif args.all:
        tickers = sorted(f.stem for f in REPORTS.glob("*.json") if re.fullmatch(r"\d{6}", f.stem))
        scope = f"전 종목 {len(tickers)}"
    else:
        s = json.loads(SAMPLE.read_text(encoding="utf-8"))
        tickers = [x["ticker"] for x in s["종목"]]
        scope = f"표본 {len(tickers)}종목"

    findings, seen, missing = run(tickers, grid)
    if args.code:
        findings = [f for f in findings if f.code == args.code]

    by_verdict = Counter(f.verdict for f in findings)
    lines = [f"# 숫자 삼각 대조 — {scope} (읽은 종목 {seen})",
             f"# 오류 {by_verdict[ERROR]}건 · 방법론으로 설명됨 {by_verdict[METHOD]}건 "
             f"· 확인불가 {by_verdict[UNKNOWN]}건"]
    if missing:
        lines.append(f"# 리포트 없음 {len(missing)}건: {', '.join(missing[:10])}")

    for verdict in (ERROR, UNKNOWN, METHOD):
        if args.verdict and verdict != args.verdict:
            continue
        group = [f for f in findings if f.verdict == verdict]
        head = {ERROR: "── 오류: 어느 기준으로도 설명이 안 된다 ──",
                UNKNOWN: "── 확인불가: 재료가 없거나 업종 특성상 못 가린다 ──",
                METHOD: "── 방법론 차이로 설명됨(정상) ──"}[verdict]
        lines += ["", f"{head}  {len(group)}건"]
        by_code = defaultdict(list)
        for f in group:
            by_code[f.code].append(f)
        for code in sorted(by_code, key=lambda k: -len(by_code[k])):
            g = by_code[code]
            lines.append(f"  ▸ [{code}] {len(g)}건")
            for f in g[:300]:
                lines.append("  " + f.line())

    sec_tot, sec_err = Counter(), Counter()
    for tk in tickers:
        p = REPORTS / f"{tk}.json"
        if p.exists():
            try:
                sec_tot[json.loads(p.read_text(encoding="utf-8")).get("sector") or "?"] += 1
            except Exception:
                pass
    for f in findings:
        if f.verdict == ERROR:
            sec_err[f.sector] += 1
    lines += ["", "── 업종별 오류 밀도 (한 업종에만 몰리면 그 업종 규칙을 의심한다) ──"]
    for sec in sorted(sec_tot, key=lambda s: -(sec_err[s] / max(1, sec_tot[s]))):
        if sec_err[sec]:
            lines.append(f"  {sec}: {sec_err[sec]}건 / {sec_tot[sec]}종목 "
                         f"({sec_err[sec]/max(1,sec_tot[sec]):.2f}건/종목)")

    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text if not args.quiet else "\n".join(lines[:2]))
    if args.strict and by_verdict[ERROR]:
        sys.exit(1)
    if args.max is not None and by_verdict[ERROR] > args.max:
        print(f"\n❌ 오류 {by_verdict[ERROR]}건 — 기준선 {args.max}건을 넘었다. "
              f"새로 생긴 것을 찾아 고칠 것.")
        sys.exit(1)


if __name__ == "__main__":
    main()
