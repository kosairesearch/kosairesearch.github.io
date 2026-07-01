#!/usr/bin/env python3
"""자동 백필용 — 현재 universe(data/stocks.js) 중 '리포트가 아예 없는' 종목 티커를
쉼표로 출력한다. 시총 상위부터, 최대 N개(기본 100).

'리포트 있음' 판단은 목록 페이지가 실제로 보여주는 reports-index.js를 기준으로 한다
(v1·v2 무관 — 사이트에 리포트가 노출되면 '있음'). 따라서 이 목록은 사이트에 리포트가
전혀 없는 종목만 담는다.

_fill_remaining.py는 skip 목록을 제외하지만, 이 스크립트는 skip도 '포함'해 재시도한다.
  - fill 모드(REPORT_FILL_TO)는 정량 데이터가 없는 종목을 영구 skip 처리하는데,
    신규 상장·일시적 DART 누락 등으로 skip된 종목이 나중에 생성 가능해질 수 있다.
  - 이 목록을 REPORT_TICKERS로 넘기면(명시적 티커 지정) skip을 건드리지 않고 재시도하므로,
    '리포트 없는 종목'이 결국 백필된다.

사용: python scripts/_missing_tickers.py [N]
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100

stocks_js = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
obj = json.loads(re.search(r"=\s*(\{.*)", stocks_js, re.S).group(1).strip().rstrip(";"))

idx_js = (ROOT / "data" / "reports-index.js").read_text(encoding="utf-8")
idx = json.loads(re.search(r"window\.KOS_REPORTS\s*=\s*(\{.*\});", idx_js, re.S).group(1))
have = set(idx.get("reports", {}).keys())

stocks = sorted(obj["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)
missing = [s["ticker"] for s in stocks if s["ticker"] not in have]
print(",".join(missing[:limit]))
