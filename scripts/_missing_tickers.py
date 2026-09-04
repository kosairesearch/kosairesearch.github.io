#!/usr/bin/env python3
"""리포트 없는 종목 백필용 — universe 중 v2 리포트가 '아예 없는' 종목 티커를
쉼표로 출력한다. 시총 상위부터, 최대 N개(기본 100).

  python scripts/_missing_tickers.py [N]

자동 백필(fill)이 영영 안 채우는 종목이 여기 대상이다.
  · skip 된 종목 — DART 재무제표가 없어 생성 불가로 기록된 것. 신규 상장·DART
    지연으로 잠시 없던 재무제표는 나중에 생기므로, 기록한 지 SKIP_RETRY_DAYS 가
    지났거나 언제 기록했는지 모르는(옛 마커) 것은 다시 시도한다. 이 목록을
    REPORT_TICKERS 로 넘기면 명시 지정 run 이라 skip 을 만들지 않고, 백필 run
    (REPORT_BACKFILL=1)만 '또 없음' 이면 날짜를 갱신해 30일 뒤에 다시 본다.
  · hold·fail 초과 종목은 여기서도 뺀다 — 돈을 더 써도 같은 결과다. 사람이 본다.
  · 진행 중 배치에 있는 종목은 뺀다.

갱신 기준일(reports_v2_refresh)은 여기서 보지 않는다 — 낡은 리포트를 새로 쓰는
일은 자동 백필(워치독 샤드)의 몫이고, 여기까지 그걸 보면 같은 종목을 두 갈래가
동시에 주문한다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _reports_state as S  # noqa: E402

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100

uni = S.load_universe()
stocks = sorted(uni.values(), key=lambda x: x.get("mcap", 0) or 0, reverse=True)
skip = S.load_skip()
hold = set(S.load_hold())
failed_out = S.load_failed_out()
inflight = S.inflight_tickers()

missing = []
for s in stocks:
    tk = s["ticker"]
    if S.has_current_report(tk) or tk in hold or tk in failed_out or tk in inflight:
        continue
    if tk in skip and not S.skip_retryable(tk):
        continue
    missing.append(tk)
print(",".join(missing[:limit]))
