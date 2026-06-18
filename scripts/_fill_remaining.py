#!/usr/bin/env python3
"""자동 백필 self-chain용 — 시총 상위 N개 중 아직 v2 리포트가 없는 종목 수를 출력.
사용: python scripts/_fill_remaining.py <N> [git-ref]
git-ref 지정 시 작업트리 대신 해당 ref의 파일을 읽는다(모니터링용, 작업트리 무변경)."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
fill_to = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
ref = sys.argv[2] if len(sys.argv) > 2 else None

if ref:
    stocks_js = subprocess.check_output(["git", "show", f"{ref}:data/stocks.js"], cwd=ROOT, text=True)
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref, "data/reports_v2"], cwd=ROOT, text=True)
    have = {Path(n).stem for n in names.splitlines() if n.endswith(".json")}
else:
    stocks_js = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
    have = {p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json")}

obj = json.loads(re.search(r"=\s*(\{.*)", stocks_js, re.S).group(1).strip().rstrip(";"))
stocks = sorted(obj["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:fill_to]
print(sum(1 for s in stocks if s["ticker"] not in have))
