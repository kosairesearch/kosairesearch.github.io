#!/usr/bin/env python3
"""일회성 디버그 — 종목의 손익(IS/CIS)+재무상태표(BS) 핵심계정 + 배당 분배내역 + 네이버값.
특수구조(리츠 등) 추출 원인 파악용. 사용: python scripts/_debug_dart.py 432320 2025 11011"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_reports as g
import generate_reports_v2 as v2

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "_debug_dart.txt"
ticker = sys.argv[1] if len(sys.argv) > 1 else "432320"
year = sys.argv[2] if len(sys.argv) > 2 else "2025"
reprt = sys.argv[3] if len(sys.argv) > 3 else "11011"

dart = g.get_dart()
L = [f"# {ticker} {year} {reprt}"]
L.append(f"[네이버] {v2.naver_valuation(ticker)}")
try: L.append(f"[주식총수] {v2.dart_total_shares(dart, ticker)}")
except Exception as e: L.append(f"[주식총수] 예외 {e}")

WANT = ("영업", "매출", "수익", "이익", "손익", "순이", "주당", "자본", "자산총", "부채총", "지배", "비용", "분배")
for fs in ("CFS", "OFS"):
    try: df = dart.finstate_all(ticker, int(year), reprt_code=reprt, fs_div=fs)
    except Exception as e: L.append(f"\n[{fs}] 예외 {e}"); continue
    if df is None or getattr(df, "empty", True): L.append(f"\n[{fs}] 없음"); continue
    L.append(f"\n[{fs}] 핵심계정:")
    for _, r in df.iterrows():
        anm = str(r.get("account_nm", "")).strip()
        if not any(w in anm for w in WANT): continue
        L.append(f"  [{r.get('sj_div','')}] id={str(r.get('account_id','')).strip()} | nm={anm} | amt={r.get('thstrm_amount')} | add={r.get('thstrm_add_amount')}")

# 배당 분배내역(여러 기간 확인)
L.append("\n[배당 공시 행]")
for yr in (int(year), int(year)-1):
    try: dv = dart.report(ticker, "배당", yr, "11011")
    except Exception as e: dv = None; L.append(f"  {yr} 예외 {e}")
    if dv is None or getattr(dv, "empty", True): continue
    for _, r in dv.iterrows():
        se = str(r.get("se","")).replace(" ","")
        if "주당" in se or "배당" in se:
            L.append(f"  {yr} se={se} knd={r.get('stock_knd')} thstrm={r.get('thstrm')} frmtrm={r.get('frmtrm')}")

OUT.write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
