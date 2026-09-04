#!/usr/bin/env python3
"""밸류에이션 자체 검산 — 외부 값 없이, 우리 데이터끼리 반드시 맞아야 하는 항등식만 본다.

왜 따로 만드나
---------------
audit_valuation.py 는 네이버와 대조한다. 그런데 네이버 종목 화면의 EPS 는
최근 결산(연간) 기준이고 우리는 최근 4개 분기(TTM) 기준이다. 기준이 다르니
멀쩡한 종목도 3~4배 어긋나게 찍힌다 — 실제로 "대형 오차 1,364건" 중 대부분이
그것이었다. 경보가 늘 울리고 있으면 아무도(나도) 그 안에서 진짜 오류를 못 찾는다.
오류가 계속 튀어나온 진짜 이유는 계산이 아니라 이 '고장 난 경보기' 다.

그래서 이 파일은 외부 값을 아예 안 쓴다. 여기 걸리는 건 방법론 차이가 아니라
전부 우리 쪽 버그다. 참/거짓이 분명하니 CI 에서 막을 수 있다.

  실행:  python3 scripts/check_valuation.py            → 요약 + data/valuation_check.txt
         python3 scripts/check_valuation.py --strict   → 오류가 있으면 exit 1 (CI 차단용)

생성기(generate_reports_v2.submit)는 check_quant() 로 종목마다 새로 모은 숫자를
검산해, 걸린 종목만 빼고 주문한다. 저장된 리포트 전체를 보는 이 파일의 main 은
그 뒤의 감시용이다 — universe 에 없는 종목(상장폐지 등 유령 리포트)은 다시
만들 수도 고칠 수도 없으므로 여기서 세지 않는다.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports_v2"
GRID = ROOT / "data" / "valuation.js"
OUT = ROOT / "data" / "valuation_check.txt"
STOCKS = ROOT / "data" / "stocks.js"


def load_universe():
    """현재 상장 종목 티커 집합. 못 읽으면 빈 집합(그러면 전부 검사한다)."""
    try:
        raw = STOCKS.read_text(encoding="utf-8")
        obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        return {s["ticker"] for s in obj.get("stocks", [])}
    except Exception:
        return set()


def load_grid():
    if not GRID.exists():
        return {}
    m = re.search(r"window\.KOS_VALUATION\s*=\s*(\{.*)", GRID.read_text(encoding="utf-8"), re.S)
    if not m:
        return {}
    return json.loads(m.group(1).rstrip().rstrip(";")).get("stocks", {})


def near(a, b, tol):
    """a 가 b 의 ±tol 안인가. b 가 0 이면 a 도 0 이어야 한다."""
    if a is None or b is None:
        return True                      # 값이 없으면 이 규칙은 판단 대상이 아니다
    if b == 0:
        return a == 0
    return abs(a / b - 1) <= tol


# ── 규칙 ─────────────────────────────────────────────────────────────────
# 각 규칙은 (코드, 설명, 검사함수) 다. 검사함수는 어긋났을 때 사람이 읽을
# 문자열을, 멀쩡하면 None 을 돌려준다. 새 버그를 고칠 때마다 여기에 규칙을
# 한 줄 더 붙이면, 같은 버그가 두 번 나갈 수 없다.

def r_per(v, q, g):
    """PER 은 소수 첫째 자리로 반올림해 저장한다. PER 이 작을수록 그 반올림만으로도
    비율이 크게 벌어지므로(PER 0.5 면 ±10%), 허용폭에 반올림 몫을 얹어 준다."""
    per, eps, price = v.get("per"), v.get("eps"), v.get("price")
    if not (per and eps and price):
        return None
    if not near(per * eps, price, max(0.01, 0.05 / abs(per))):
        return f"PER×EPS={per * eps:,.0f} 인데 주가는 {price:,}"


def r_pbr(v, q, g):
    """PBR 은 소수 둘째 자리 반올림 — 위와 같은 이유로 허용폭을 보정한다."""
    pbr, bps, price = v.get("pbr"), v.get("bps"), v.get("price")
    if not (pbr and bps and price):
        return None
    if not near(pbr * bps, price, max(0.01, 0.005 / abs(pbr))):
        return f"PBR×BPS={pbr * bps:,.0f} 인데 주가는 {price:,}"


def _q4(q):
    qs = [x.get("np_owner") for x in (q.get("quarterly") or [])[-4:]]
    return sum(qs) if len(qs) == 4 and all(x is not None for x in qs) else None


def r_ttm_vs_quarters(v, q, g):
    ttm, s = v.get("ttm_np_owner"), _q4(q)
    if ttm is None or s is None:
        return None
    if not near(ttm, s, 0.10):
        return f"TTM 순이익 {ttm / 1e8:,.0f}억 인데 화면의 분기 4개 합은 {s / 1e8:,.0f}억"


def r_eps_denom(v, q, g):
    """EPS × 주식수 가 TTM 순이익과 맞는가. 잣대는 EPS 가 어디서 왔느냐에 따라 다르다.

    · 순이익÷주식수로 만든 EPS 는 되돌리면 정확히 맞아야 한다(항등식) → 10%
    · 회사 공시 주당이익을 이어붙인 EPS 는 각 기간이 그때의 가중평균주식수로
      나뉜 값이라, 지금 주식수를 곱하면 원래 안 맞는다. 유상증자·자기주식이
      있으면 20~30% 는 예사다(가온전선 1.27배 · 한화 0.77배). 여기서 잡을 것은
      방법론 차이가 아니라 자릿수·단위 오류다 → 3배
    """
    eps, ttm = v.get("eps"), v.get("ttm_np_owner")
    if not eps or not ttm:
        return None
    cands = [d for d in (v.get("wavg_shares"), v.get("total_shares"), v.get("shares")) if d]
    if not cands:
        return None
    tol = 0.10 if v.get("eps_src") == "순이익÷주식수" else 2.0
    # EPS 는 정수 원으로 저장된다. 순이익÷주식수 가 -6.9 면 -7 로 실리고, 거꾸로
    # 곱하면 순이익과 ±0.5원×주식수 만큼 어긋난다. 이익이 0 근처인 회사에서는
    # 그것만으로 10% 를 넘는다(지엘팜텍 -1억). 반올림 몫은 항등식 위반이 아니다.
    if any(near(eps * d, ttm, tol) or abs(eps * d - ttm) <= 0.5 * d + 1 for d in cands):
        return None
    best = min(cands, key=lambda d: abs(eps * d / ttm - 1))
    return (f"EPS {eps:,} × 주식수 {best:,} = {eps * best / 1e8:,.0f}억 인데 "
            f"TTM 순이익은 {ttm / 1e8:,.0f}억 "
            f"(EPS 출처 {v.get('eps_src') or '기록 없음'} · 허용 {tol:.0%})")


def r_roe_sign(v, q, g):
    roe, ttm = v.get("roe_ttm"), v.get("ttm_np_owner")
    # ROE 는 소수 첫째 자리 반올림이라, 순이익이 아주 작으면 0.0 으로 찍힌다.
    # 0.0 은 '음수' 가 아니라 '반올림해서 0' 이므로 부호 위반이 아니다.
    if roe is None or ttm is None or ttm == 0 or roe == 0:
        return None
    if (roe > 0) != (ttm > 0):
        return f"ROE {roe}% 인데 TTM 순이익은 {ttm / 1e8:,.0f}억 (부호 반대)"


def r_eps_sign(v, q, g):
    eps, ttm = v.get("eps"), v.get("ttm_np_owner")
    if not eps or not ttm:
        return None
    if (eps > 0) != (ttm > 0):
        return f"EPS {eps:,} 인데 TTM 순이익은 {ttm / 1e8:,.0f}억 (부호 반대)"


def r_share_multiple(v, q, g):
    """DART 발행주식총수가 KRX 주식수의 딱 정수배면 같은 줄을 여러 번 더한 것이다.
    (우선주가 섞여 1.1~1.3배가 되는 것은 정상이라 정수 근방만 잡는다.)"""
    a, b = v.get("total_shares"), v.get("shares")
    if not (a and b):
        return None
    r = a / b
    for n in range(2, 11):
        if abs(r - n) < 0.005:
            return f"발행주식총수 {a:,} 가 KRX {b:,} 의 정확히 {n}배 (중복 합산)"


def r_neg_rev(v, q, g):
    for x in (q.get("quarterly") or []):
        if x.get("rev") is not None and x["rev"] < 0:
            return f"{x['q']} 매출이 음수 {x['rev'] / 1e8:,.0f}억 (누적/당기 혼동)"


def r_q_over_year(v, q, g):
    """한 분기 매출이 그 분기를 끝으로 하는 4개 분기 합의 60% 를 넘는가.

    처음에는 '그 해 연간 매출' 과 견줬는데, 올해는 연간이 아직 없어서 작년
    연간과 비교하게 된다. 그러면 매출이 빠르게 느는 회사가 죄다 걸린다 —
    119종목이 그렇게 잡혔고 대부분 정상이었다(SK하이닉스·키움증권).

    분기 추출 자체는 따로 확인했다. Q1~Q4 가 다 있는 연도 66곳에서
    '분기 4개 합 = 연간 매출' 이 하나도 어긋나지 않았다. 그러니 여기서
    잡을 것은 성장이 아니라 '한 분기에 여러 분기가 뭉쳐 들어온 것' 이고,
    그건 자기가 속한 4개 분기 안에서 봐야 드러난다."""
    qs = [x for x in (q.get("quarterly") or []) if x.get("rev") is not None]
    for i, x in enumerate(qs):
        win = [y["rev"] for y in qs[max(0, i - 3):i + 1]]
        if len(win) < 4:
            continue
        tot = sum(win)
        if tot > 0 and x["rev"] > tot * 0.6:
            return (f"{x['q']} 매출 {x['rev'] / 1e8:,.0f}억 이 "
                    f"직전 4개 분기 합 {tot / 1e8:,.0f}억 의 60% 초과")


def r_rev_scale(v, q, g):
    """매출로 성립할 수 없는 크기가 한 분기에 들어와 있는가.

    진코스텍 2026Q2 매출이 30.9조로 실려 있었다 — 시가총액 719억, 직전 연간
    매출 486억인 회사다. 한 분기에 여러 기간이 뭉쳐 들어온 것이다.
    직전 연간의 3배를 넘고 시가총액의 5배도 넘을 때만 잡는다 — 매출이 0 에서
    뛰는 신약개발사를 잘못 걸지 않으려면 두 조건이 다 필요하다."""
    mcap = (v.get("mcap") or 0) * 1e12
    if not mcap:
        return None
    ann = {a.get("year"): a for a in (q.get("annual") or []) if isinstance(a, dict)}
    for x in (q.get("quarterly") or []):
        rev = x.get("rev")
        if not rev or rev <= 0:
            continue
        y = int(str(x.get("q", "0000"))[:4])
        base = (ann.get(y) or {}).get("rev") or (ann.get(y - 1) or {}).get("rev")
        if base and base > 0 and rev > base * 3 and rev > mcap * 5:
            return (f"{x['q']} 매출 {rev / 1e8:,.0f}억 이 직전 연간 {base / 1e8:,.0f}억 의 "
                    f"{rev / base:.0f}배 · 시가총액 {mcap / 1e8:,.0f}억 의 {rev / mcap:.0f}배")


def r_equity_identity(v, q, g):
    """지배지분은 자본총계를 넘을 수 없다(비지배지분이 음수인 예외는 5% 여유로 흡수)."""
    ann = q.get("annual") or []
    if not ann:
        return None
    a0 = ann[0]
    eo, et, nci = a0.get("equity_owner"), a0.get("equity"), a0.get("equity_nci")
    if not (eo and et and et > 0):
        return None
    # 지배지분 + 비지배지분 = 자본총계. 비지배지분을 읽었으면 이 식으로 본다
    # (지배지분이 자본총계보다 큰 것 자체는 비지배지분이 음수면 정상이다).
    # 비지배지분이 실제로 읽혔을 때만 항등식으로 판정할 수 있다.
    # 값이 0 근처면 '비지배지분이 없다' 인지 '못 읽었다' 인지 구분되지 않는다.
    if nci and abs(nci) > abs(et) * 0.01:
        if abs((eo + nci) - et) > abs(et) * 0.01:
            return (f"{a0.get('year')} 지배 {eo / 1e8:,.0f}억 + 비지배 {nci / 1e8:,.0f}억 "
                    f"≠ 자본총계 {et / 1e8:,.0f}억")
        return None
    # 못 읽었으면 확인할 길이 없다 — 자릿수가 틀린 수준만 막는다.
    if eo > et * 1.5:
        return (f"{a0.get('year')} 지배지분 {eo / 1e8:,.0f}억 > 자본총계 {et / 1e8:,.0f}억 "
                f"(1.5배 초과 · 비지배지분을 못 읽어 확인 불가)")


def r_equity_gap(v, q, g):
    """비지배지분을 못 읽었는데 지배지분과 자본총계가 다르다.

    셋 중 하나는 틀렸는데 어느 것인지 가릴 재료가 없다. 값이 틀렸다고 단정할 수
    없으므로 막지는 않고 눈으로 볼 목록에만 올린다."""
    ann = q.get("annual") or []
    if not ann:
        return None
    a0 = ann[0]
    eo, et, nci = a0.get("equity_owner"), a0.get("equity"), a0.get("equity_nci")
    if not (eo and et and et > 0):
        return None
    if nci and abs(nci) > abs(et) * 0.01:
        return None                      # 위 항등식 규칙이 판정한다
    if abs(eo - et) > abs(et) * 0.01:
        return (f"{a0.get('year')} 지배지분 {eo / 1e8:,.0f}억 ≠ 자본총계 {et / 1e8:,.0f}억 "
                f"인데 비지배지분을 못 읽어 어느 쪽이 맞는지 알 수 없다")


def r_sanity(v, q, g):
    per, pbr, roe = v.get("per"), v.get("pbr"), v.get("roe_ttm")
    bad = []
    # 이익이 0 에 가까우면 PER 은 수천이 되고, 자본이 0 에 가까우면 ROE 는
    # ±1,000% 가 된다 — 계산이 틀린 게 아니라 원래 그런 값이다. 그래서
    # 여기 폭은 '눈으로 볼 만큼 드문가' 를 가르는 선이지 오류 판정이 아니다.
    if per is not None and not (0 < per <= 5000):
        bad.append(f"PER {per}")
    if pbr is not None and not (0 < pbr <= 100):
        bad.append(f"PBR {pbr}")
    if roe is not None and not (-2000 <= roe <= 2000):
        bad.append(f"ROE {roe}%")
    if bad:
        return "상식 밖 " + " · ".join(bad)


def r_annual_derived(v, q, g):
    """연간 표의 파생값을 재료로 다시 계산해 본다.

    화면에 나가는 영업이익률·부채비율·ROE 는 같은 줄의 재료로 만든 값이다.
    저장된 값과 다시 계산한 값이 다르면 둘 중 하나가 옛 값이거나 다른 줄에서
    온 것이다. 재료가 같은 곳에 있으니 외부 값 없이 확인된다."""
    for a in (q.get("annual") or []):
        if not isinstance(a, dict):
            continue
        y = a.get("year")
        rev, op, li = a.get("rev"), a.get("op"), a.get("liab")
        eq, eqo, npo = a.get("equity"), a.get("equity_owner"), a.get("np_owner")
        checks = (
            ("영업이익률", a.get("opm"), (op / rev * 100) if (op is not None and rev) else None),
            ("부채비율", a.get("debt_ratio"), (li / eq * 100) if (li is not None and eq) else None),
            ("ROE", a.get("roe"),
             (npo / (eqo or eq) * 100) if (npo is not None and (eqo or eq) and (eqo or eq) > 0) else None),
        )
        for label, got, want in checks:
            if got is None or want is None:
                continue
            # 소수 첫째 자리 반올림이라 ±0.05 는 정상이다.
            if abs(got - want) > max(0.06, abs(want) * 0.01):
                return f"{y} {label} {got} 인데 재료로 다시 계산하면 {want:,.1f}"


def r_annual_years(v, q, g):
    """연간 표의 연도가 내림차순으로 이어지는가. 한 해가 빠지면 표가 거짓말을 한다."""
    ys = [a.get("year") for a in (q.get("annual") or []) if isinstance(a, dict)]
    ys = [y for y in ys if isinstance(y, int)]
    if len(ys) < 2:
        return None
    if ys != sorted(ys, reverse=True):
        return f"연간 표 연도가 내림차순이 아니다: {ys}"
    if len(set(ys)) != len(ys):
        return f"연간 표에 같은 해가 두 번 있다: {ys}"


def r_grid_sync(v, q, g):
    if g is None:
        return "그리드(valuation.js)에 이 종목이 없다"
    for key, gk, name in (("eps", "eps", "EPS"), ("bps", "bps", "BPS"), ("roe_ttm", "roe", "ROE")):
        a, b = v.get(key), g.get(gk)
        if a is None and b is None:
            continue
        if a is None or b is None or not near(a, b, 0.02):
            return f"그리드 {name} {b} ≠ 리포트 {a}"


# 반드시 0 이어야 하는 항등식. 여기 걸리면 예외 없이 우리 버그다 → CI 차단.
HARD = [
    ("PER정합", "PER × EPS 가 주가와 맞는가", r_per),
    ("PBR정합", "PBR × BPS 가 주가와 맞는가", r_pbr),
    ("TTM분기합", "TTM 순이익이 화면의 분기 4개 합과 맞는가", r_ttm_vs_quarters),
    ("EPS분모", "EPS × 주식수 가 TTM 순이익과 맞는가", r_eps_denom),
    ("EPS부호", "EPS 부호가 순이익 부호와 같은가", r_eps_sign),
    ("ROE부호", "ROE 부호가 순이익 부호와 같은가", r_roe_sign),
    ("주식수중복", "발행주식총수가 KRX 주식수의 정수배가 아닌가", r_share_multiple),
    ("음수매출", "분기 매출이 음수가 아닌가", r_neg_rev),
    ("매출규모", "분기 매출이 회사 규모로 설명되는가", r_rev_scale),
    ("자본항등", "지배지분이 자본총계의 1.5배를 넘지 않는가", r_equity_identity),
    ("연간파생", "영업이익률·부채비율·ROE 가 같은 줄의 재료와 맞는가", r_annual_derived),
    ("연간연도", "연간 표의 연도가 내림차순으로 이어지는가", r_annual_years),
    ("그리드동기", "그리드 값이 리포트와 같은가", r_grid_sync),
]

# 0 이 아닐 수도 있는 것들. 실적이 실제로 튀면 걸리므로 차단하지 않고 눈으로 본다.
SOFT = [
    ("분기과다", "분기 매출이 직전 4개 분기 합의 60% 를 넘지 않는가", r_q_over_year),
    ("상식범위", "PER·PBR·ROE 가 상식 범위인가", r_sanity),
]

RULES = HARD + SOFT

# 정량 블록만 있으면 판정할 수 있는 항등식 — 생성기가 주문 전에 종목마다 본다.
# 그리드동기는 저장된 두 파일을 맞대는 규칙이라 새 숫자에는 적용할 수 없다.
INTRINSIC = [(c, d, f) for c, d, f in HARD if c != "그리드동기"]


def check_quant(q):
    """새로 모은 정량 블록이 항등식을 지키는가. [(규칙, 설명)] — 비어 있으면 통과.
    검사 자체가 예외를 내면 그것도 실패로 친다(모르는 값으로 글을 쓰지 않는다)."""
    if not isinstance(q, dict):
        return [("형식", "정량 블록이 없다")]
    v = q.get("valuation") or {}
    out = []
    for code, _, fn in INTRINSIC:
        try:
            msg = fn(v, q, None)
        except Exception as e:
            msg = f"검사 중 예외 {type(e).__name__}: {e}"
        if msg:
            out.append((code, msg))
    return out


def main():
    grid = load_grid()
    universe = load_universe()
    files = sorted(REPORTS.glob("*.json"))
    hits = {code: [] for code, _, _ in RULES}
    blank = []
    cover = Counter()
    n = 0
    ghosts = 0
    for f in files:
        if universe and f.stem not in universe:
            ghosts += 1                      # 상장폐지 등 — 다시 만들 수 없는 리포트
            continue
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(r, dict) or "quant" not in r:
            continue
        q = r["quant"]
        v = q.get("valuation") or {}
        tk = r.get("ticker") or f.stem
        name = r.get("name") or tk
        n += 1
        _a0 = (q.get("annual") or [{}])[0]
        _eo, _et, _nci = _a0.get("equity_owner"), _a0.get("equity"), _a0.get("equity_nci")
        if _eo and _et and _et > 0:
            cover["대상"] += 1
            if _nci and abs(_nci) > abs(_et) * 0.01:
                cover["비지배지분 읽음"] += 1
            elif abs(_eo - _et) <= abs(_et) * 0.01:
                cover["비지배지분 없음(지배=총계)"] += 1
            else:
                cover["못 읽음 — 확인 불가"] += 1
        if v.get("eps") is None and v.get("bps") is None:
            blank.append(f"{name}({tk})")
        for code, _, fn in RULES:
            try:
                msg = fn(v, q, grid.get(tk))
            except Exception as e:
                msg = f"검사 중 예외 {type(e).__name__}: {e}"
            if msg:
                hits[code].append(f"{name}({tk}) — {msg}")

    hard = sum(len(hits[c]) for c, _, _ in HARD)
    soft = sum(len(hits[c]) for c, _, _ in SOFT)
    lines = [f"# 밸류에이션 자체 검산 — 리포트 {n}종목 (외부 참조값 안 씀"
             + (f" · universe 밖 {ghosts}종목 제외" if ghosts else "") + ")",
             f"# 항등식 위반 {hard}건(0 이어야 함) · 눈으로 볼 것 {soft}건 · "
             f"EPS·BPS 둘 다 빈칸 {len(blank)}종목", "",
             "── 항등식: 걸리면 예외 없이 우리 버그 ──"]
    for group, title in ((HARD, None), (SOFT, "── 참고: 실적이 실제로 튀어도 걸린다 ──")):
        if title:
            lines += ["", title]
        for code, desc, _ in group:
            v = hits[code]
            mark = "✅" if not v else "❌"
            lines.append(f"{mark} [{code}] {desc} — {len(v)}건")
            for s in v[:25]:
                lines.append(f"      {s}")
            if len(v) > 25:
                lines.append(f"      … 외 {len(v) - 25}건")
    if cover:
        lines += ["", "── 자본 구성 확인 범위 (오류 아님 · 재료가 있는지의 문제) ──"]
        for k in ("비지배지분 읽음", "비지배지분 없음(지배=총계)", "못 읽음 — 확인 불가"):
            if cover.get(k):
                lines.append(f"   {cover[k]:5}  {k}")
    if blank:
        lines += ["", f"· EPS·BPS 둘 다 빈칸 {len(blank)}종목: " + ", ".join(blank[:40])
                  + (f" … 외 {len(blank) - 40}" if len(blank) > 40 else "")]
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)

    if "--strict" in sys.argv and hard:
        print(f"❌ 자체 검산 실패 — 항등식 위반 {hard}건. 배포를 막는다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
