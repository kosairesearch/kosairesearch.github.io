#!/usr/bin/env python3
"""자체 검산의 항등식을 어긴 종목 티커만 쉼표로 출력한다(없으면 빈 줄).

쓰임: 검산이 깨졌을 때 전 종목이 아니라 그 종목만 다시 계산하려고.
      DART 하루 호출 한도가 2만 건인데 전 종목 재수집은 한 번에 그걸 다 먹는다.
      실제로 하루에 세 번 돌렸다가 한도를 넘겨 반나절을 잃었다.

  python scripts/_check_failed_tickers.py [최대개수]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_valuation as C

cap = int(sys.argv[1]) if len(sys.argv) > 1 else 400

grid = C.load_grid()
bad = []
for f in sorted((ROOT / "data" / "reports_v2").glob("*.json")):
    try:
        r = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(r, dict) or "quant" not in r:
        continue
    q = r["quant"]
    v = q.get("valuation") or {}
    tk = r.get("ticker") or f.stem
    for _code, _desc, fn in C.HARD:
        try:
            hit = fn(v, q, grid.get(tk))
        except Exception:
            hit = "검사 중 예외"
        if hit:
            bad.append(tk)
            break

# 너무 많으면 아무것도 내지 않는다. 그 상황은 '몇 종목이 틀렸다' 가 아니라
# '산식이 통째로 바뀌었다' 는 뜻이고, 그때는 사람이 전 종목 재수집을 결정해야 한다.
print("" if len(bad) > cap else ",".join(bad))
