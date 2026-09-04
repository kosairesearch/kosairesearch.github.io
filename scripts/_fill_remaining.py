#!/usr/bin/env python3
"""자동 백필 self-chain·워치독용 — 시총 상위 N개 중 '지금 만들어야 할' v2 리포트 수를 출력.

  python scripts/_fill_remaining.py <N>

판정은 생성기(generate_reports_v2.pick_targets)와 같은 함수(_reports_state.wanted)를
쓴다. 둘이 따로 세면 워치독은 '남았다' 고 하고 생성기는 '할 게 없다' 고 하는
식으로 어긋나 30분마다 빈 run 이 뜬다.

'만들어야 할' 종목 = 리포트가 없거나 갱신 기준일(data/reports_v2_refresh)보다
오래된 것. 다음은 뺀다.
  · skip   — DART 에 재무제표가 없다(백필이 30일마다 따로 다시 본다)
  · hold   — 숫자가 항등식에 걸렸다(사람이 봐야 한다)
  · fail   — 배치 결과가 FAIL_LIMIT 번 깨졌다(사람이 봐야 한다)
  · 진행 중 — 이미 주문이 들어가 결과를 기다리는 중이다(다시 주문하면 돈만 두 번)
표준 라이브러리만 쓴다(워치독은 pip 없이 돈다)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _reports_state as S  # noqa: E402

fill_to = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
stocks = sorted(S.load_universe().values(), key=lambda x: x.get("mcap", 0) or 0, reverse=True)
print(len(S.remaining_tickers(stocks, fill_to)))
