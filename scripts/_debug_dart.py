#!/usr/bin/env python3
"""일회성 디버그 — 종목의 손익(IS/CIS)+재무상태표(BS) 핵심계정 + 공시EPS + 주식총수 + 네이버값 덤프.
단위·주식수·EPS 추출 원인 파악용. DART_API_KEY 필요(Actions).
사용: python scripts/_debug_dart.py 241560 2024 11011"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_reports as g
import generate_reports_v2 as v2

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "_debug_dart.txt"

ticker = sys.argv[1] if len(sys.argv) > 1 else "241560"
year = sys.argv[2] if len(sys.argv) > 2 else "2024"
reprt = sys.argv[3] if len(sys.argv) > 3 else "11011"

dart = g.get_dart()
lines = [f"# {ticker} {year} {reprt}"]

# 네이버 참조
nv = v2.naver_valuation(ticker)
lines.append(f"[네이버] {nv}")

# 주식총수
try:
    lines.append(f"[주식총수] {v2.dart_total_shares(dart, ticker)}")
except Exception as e:
    lines.append(f"[주식총수] 예외 {e}")

WANT_NM = ("영업이익", "매출", "수익", "당기순이익", "순이익", "주당", "자본", "자산총계", "부채총계", "지배")
for fs in ("CFS", "OFS"):
    try:
        df = dart.finstate_all(ticker, int(year), reprt_code=reprt, fs_div=fs)
    except Exception as e:
        lines.append(f"\n[{fs}] 예외: {e}")
        continue
    if df is None or getattr(df, "empty", True):
        lines.append(f"\n[{fs}] 없음")
        continue
    lines.append(f"\n[{fs}] {len(df)}행 — 핵심계정:")
    for _, r in df.iterrows():
        anm = str(r.get("account_nm", "")).strip()
        if not any(w in anm for w in WANT_NM):
            continue
        sj = str(r.get("sj_div", ""))
        aid = str(r.get("account_id", "")).strip()
        amt = r.get("thstrm_amount")
        add = r.get("thstrm_add_amount")
        lines.append(f"  [{sj}] id={aid} | nm={anm} | amt={amt} | add={add}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
