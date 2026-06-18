#!/usr/bin/env python3
"""reports-index.js(목록 페이지용)의 제목·날짜를 reports_v2/*.json과 동기화.

병렬 리포트 생성 run들은 서로 겹치지 않는 종목 JSON만 커밋한다(충돌 방지).
전역 인덱스(reports-index.js)는 충돌을 피하려 이 스크립트가 '단일 직렬'로 재생성한다.
표준 라이브러리만 사용(워치독에서 pip 없이 실행)."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "reports_v2"
IDX = ROOT / "data" / "reports-index.js"

TICKER = re.compile(r"[0-9][0-9A-Za-z]{5}")

t = IDX.read_text(encoding="utf-8")
m = re.search(r"window\.KOS_REPORTS\s*=\s*(\{.*\});", t, re.S)
payload = json.loads(m.group(1))
reports = payload.setdefault("reports", {})

n = 0
for f in sorted(V2.glob("*.json")):
    if not TICKER.fullmatch(f.stem):
        continue
    try:
        v2 = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not v2.get("title"):
        continue
    reports[f.stem] = {"title": v2.get("title"),
                       "reportDate": v2.get("reportDate"),
                       "reportTs": v2.get("reportTs")}
    n += 1

IDX.write_text(
    "// KOS ai — 리포트 인덱스(자동 생성). 전체 본문은 data/reports 폴더의 종목별 JSON 참조.\n"
    "window.KOS_REPORTS = " + json.dumps(payload, ensure_ascii=False) + ";\n",
    encoding="utf-8")
print(f"reindex: {n} v2 reports synced into reports-index.js")
