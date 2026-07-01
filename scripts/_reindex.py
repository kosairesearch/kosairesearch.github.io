#!/usr/bin/env python3
"""reports-index.js(목록 페이지용)의 제목·날짜를 reports_v2/*.json과 동기화.

병렬 리포트 생성 run들은 서로 겹치지 않는 종목 JSON만 커밋한다(충돌 방지).
전역 인덱스(reports-index.js)는 충돌을 피하려 이 스크립트가 '단일 직렬'로 재생성한다.
표준 라이브러리만 사용(워치독에서 pip 없이 실행).

추가로 두 가지를 함께 처리한다.
  · 유령 리포트 정리: 현재 universe(data/stocks.js)에 없는 종목(상장폐지 등)의
    인덱스 항목을 제거한다. reindex는 '추가'만 하므로 상폐 종목이 계속 남는데,
    universe 기준으로 매번 정리해 랜딩/리포트 카운트가 실제 종목 수와 일치하게 한다.
  · stockCount: universe 종목 수를 payload에 기록 → 랜딩 페이지가 리포트 페이지와
    동일한 기준(전 종목 수)으로 카운트를 표시하도록 통일한다."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "data" / "reports_v2"
IDX = ROOT / "data" / "reports-index.js"
STOCKS = ROOT / "data" / "stocks.js"

TICKER = re.compile(r"[0-9][0-9A-Za-z]{5}")


def load_universe():
    """data/stocks.js에서 현재 상장 종목 티커 집합을 읽는다(표준 라이브러리만)."""
    try:
        src = STOCKS.read_text(encoding="utf-8")
        obj = json.loads(re.search(r"=\s*(\{.*)", src, re.S).group(1).strip().rstrip(";"))
        return {s["ticker"] for s in obj.get("stocks", [])}
    except Exception:
        return set()


t = IDX.read_text(encoding="utf-8")
m = re.search(r"window\.KOS_REPORTS\s*=\s*(\{.*\});", t, re.S)
payload = json.loads(m.group(1))
reports = payload.setdefault("reports", {})

universe = load_universe()

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

# 유령 리포트 정리 — universe에 없는(상장폐지 등) 종목 항목 제거.
# universe 로딩에 실패하면(빈 집합) 안전하게 정리를 건너뛴다.
pruned = 0
if universe:
    for tk in [tk for tk in reports if tk not in universe]:
        del reports[tk]
        pruned += 1
    # 랜딩/리포트 카운트 통일용 — 전 종목 수를 함께 기록.
    payload["stockCount"] = len(universe)

IDX.write_text(
    "// KOS ai — 리포트 인덱스(자동 생성). 전체 본문은 data/reports 폴더의 종목별 JSON 참조.\n"
    "window.KOS_REPORTS = " + json.dumps(payload, ensure_ascii=False) + ";\n",
    encoding="utf-8")
print(f"reindex: {n} v2 reports synced · {pruned} ghost(s) pruned · stockCount={payload.get('stockCount')}")
