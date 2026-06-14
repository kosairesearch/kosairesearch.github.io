#!/usr/bin/env python3
"""일회성 디버그 — 특정 종목의 손익계산서 계정(account_id/nm/sj_div/금액)을 덤프.
은행 영업이익 미추출 원인 파악용. DART_API_KEY 필요(Actions).
사용: python scripts/_debug_dart.py 323410 2024
결과: data/_debug_dart.txt 로 기록."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_reports as g

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "_debug_dart.txt"

ticker = sys.argv[1] if len(sys.argv) > 1 else "323410"
year = sys.argv[2] if len(sys.argv) > 2 else "2024"
reprt = sys.argv[3] if len(sys.argv) > 3 else "11011"

dart = g.get_dart()
lines = [f"# {ticker} {year} {reprt}"]
for fs in ("CFS", "OFS"):
    try:
        df = dart.finstate_all(ticker, int(year), reprt_code=reprt, fs_div=fs)
    except Exception as e:
        lines.append(f"[{fs}] 예외: {e}")
        continue
    if df is None or getattr(df, "empty", True):
        lines.append(f"[{fs}] 없음")
        continue
    lines.append(f"\n[{fs}] {len(df)}행 — 손익(IS/CIS)만:")
    for _, r in df.iterrows():
        sj = str(r.get("sj_div", ""))
        if sj not in ("IS", "CIS"):
            continue
        aid = str(r.get("account_id", "")).strip()
        anm = str(r.get("account_nm", "")).strip()
        amt = r.get("thstrm_amount")
        add = r.get("thstrm_add_amount")
        lines.append(f"  [{sj}] id={aid} | nm={anm} | amt={amt} | add={add}")

OUT.write_text("\n".join(lines), encoding="utf-8")
print("\n".join(lines))
print(f"\n→ {OUT}")
