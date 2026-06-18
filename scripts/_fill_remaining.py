#!/usr/bin/env python3
"""자동 백필 self-chain용 — 시총 상위 N개 중 아직 v2 리포트가 없는 종목 수를 출력.
사용: python scripts/_fill_remaining.py <N>"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fill_to = int(sys.argv[1]) if len(sys.argv) > 1 else 1000

t = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
obj = json.loads(re.search(r"=\s*(\{.*)", t, re.S).group(1).strip().rstrip(";"))
stocks = sorted(obj["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:fill_to]
have = {p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json")}
print(sum(1 for s in stocks if s["ticker"] not in have))
