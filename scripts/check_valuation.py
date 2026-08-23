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
    """EPS × (가중평균 또는 발행총수) 가 TTM 순이익과 맞아야 한다.
    둘 중 어느 쪽으로도 안 맞으면 분자·분모가 서로 다른 데서 온 것이다."""
    eps, ttm = v.get("eps"), v.get("ttm_np_owner")
    if not eps or not ttm:
        return None
    cands = [d for d in (v.get("wavg_shares"), v.get("total_shares"), v.get("shares")) if d]
    if not cands:
        return None
    if any(near(eps * d, ttm, 0.10) for d in cands):
        return None
    best = min(cands, key=lambda d: abs(eps * d / ttm - 1))
    return (f"EPS {eps:,} × 주식수 {best:,} = {eps * best / 1e8:,.0f}억 인데 "
            f"TTM 순이익은 {ttm / 1e8:,.0f}억 (어느 주식수로도 안 맞음)")


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
    """한 분기 매출이 직전 연간 매출의 60% 를 넘으면 누적값을 당기로 잘못 읽은 것이다."""
    ann = q.get("annual") or []
    fy = ann[0].get("rev") if ann else None
    if not fy or fy <= 0:
        return None
    for x in (q.get("quarterly") or []):
        if x.get("rev") and x["rev"] > fy * 0.6:
            return f"{x['q']} 매출 {x['rev'] / 1e8:,.0f}억 이 연간 {fy / 1e8:,.0f}억 의 60% 초과"


def r_equity_identity(v, q, g):
    """지배지분은 자본총계를 넘을 수 없다(비지배지분이 음수인 예외는 5% 여유로 흡수)."""
    ann = q.get("annual") or []
    if not ann:
        return None
    eo, et = ann[0].get("equity_owner"), ann[0].get("equity")
    if not (eo and et and et > 0):
        return None
    # 지배지분 + 비지배지분 = 자본총계 라서, 비지배지분이 음수면 지배지분이
    # 자본총계보다 커도 정상이다. 여기서 잡을 것은 그 정도 차이가 아니라
    # 추출이 통째로 어긋난 경우다.
    if eo > et * 1.5:
        return f"{ann[0].get('year')} 지배지분 {eo / 1e8:,.0f}억 > 자본총계 {et / 1e8:,.0f}억 (1.5배 초과)"


def r_sanity(v, q, g):
    per, pbr, roe = v.get("per"), v.get("pbr"), v.get("roe_ttm")
    bad = []
    if per is not None and not (0 < per <= 500):
        bad.append(f"PER {per}")
    if pbr is not None and not (0 < pbr <= 50):
        bad.append(f"PBR {pbr}")
    if roe is not None and not (-300 <= roe <= 300):
        bad.append(f"ROE {roe}%")
    if bad:
        return "상식 밖 " + " · ".join(bad)


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
    ("자본항등", "지배지분이 자본총계의 1.5배를 넘지 않는가", r_equity_identity),
    ("그리드동기", "그리드 값이 리포트와 같은가", r_grid_sync),
]

# 0 이 아닐 수도 있는 것들. 실적이 실제로 튀면 걸리므로 차단하지 않고 눈으로 본다.
SOFT = [
    ("분기과다", "분기 매출이 그 해 연간의 60% 를 넘지 않는가", r_q_over_year),
    ("상식범위", "PER·PBR·ROE 가 상식 범위인가", r_sanity),
]

RULES = HARD + SOFT


def main():
    grid = load_grid()
    files = sorted(REPORTS.glob("*.json"))
    hits = {code: [] for code, _, _ in RULES}
    blank = []
    n = 0
    for f in files:
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
    lines = [f"# 밸류에이션 자체 검산 — 리포트 {n}종목 (외부 참조값 안 씀)",
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
