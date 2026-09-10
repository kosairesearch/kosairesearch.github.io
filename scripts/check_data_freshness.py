#!/usr/bin/env python3
"""
KOS ai — 게시된 시세 데이터가 실제로 최신인지 판정한다.

왜 따로 두는가
--------------
2026-09-08~09-10, 원본 CSV가 끊긴 걸 아무도 몰라서 2026-09-07 종가가 사흘간
'09-08 종가'·'09-09 종가'라는 이름으로 게시됐다. 수집기 안의 가드만으로는
수집기가 아예 안 돌거나 조용히 실패하는 경우를 못 잡는다. 그래서 결과물만
보고 판정하는 감시기를 수집기 바깥에 따로 세운다.

판정 규칙
--------
  게시일 == 최신 확정 거래일            → 정상
  게시일 <  최신 확정 거래일 == 오늘     → 당일 원본 지연(정상 범위). 경고만.
  게시일 <  최신 확정 거래일 != 오늘     → 거래일을 통째로 놓쳤다. 실패.
  최신 확정 거래일 판정 불가             → 판단 보류(오탐 방지). 통과.

exit 0 = 정상/보류, exit 1 = 데이터가 낡음(사람이 봐야 함).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
STOCKS = ROOT / "data" / "stocks.js"
VALUATION = ROOT / "data" / "valuation.js"

OK, STALE, HOLD = "ok", "stale", "hold"


def read_js_object(path):
    """window.KOS_* = {...}; 형태의 파일에서 최상위 객체만 뽑는다."""
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def judge(published, target, today):
    """(상태, 사유) 를 돌려준다. 네트워크 없이 단위 테스트할 수 있게 순수 함수로 뒀다.

    published: 게시된 dataDate(YYYYMMDD) 또는 ""
    target:    최신 확정 거래일(YYYYMMDD) 또는 None(판정 불가)
    today:     오늘 날짜(YYYYMMDD, KST)
    """
    if not target:
        return HOLD, "최신 거래일을 판정할 수 없어 보류한다(원본 장애 가능성)."
    if not published:
        return STALE, "게시된 dataDate 가 없다."
    if published > target:
        return STALE, f"게시일({published})이 최신 거래일({target})보다 미래다 — 라벨 오염."
    if published == target:
        return OK, f"최신 거래일 {target} 종가가 게시돼 있다."
    if target == today:
        return HOLD, (f"게시일 {published}, 최신 거래일 {target}(오늘). "
                      "당일 종가 원본이 아직 안 올라온 정상 범위.")
    return STALE, (f"게시일 {published} 인데 최신 확정 거래일은 {target} 다 — "
                   "거래일을 통째로 놓쳤다.")


def main():
    if not STOCKS.exists():
        print("❌ data/stocks.js 가 없다.")
        return 1

    try:
        stocks = read_js_object(STOCKS)
    except Exception as e:
        print(f"❌ data/stocks.js 파싱 실패: {type(e).__name__}: {e}")
        return 1

    published = str(stocks.get("dataDate") or "")
    rows = stocks.get("stocks") or []
    print(f"게시본: dataDate={published or '없음'}  종목 {len(rows)}개  "
          f"lastUpdated={stocks.get('lastUpdated')}")

    # 밸류에이션은 collect_valuation.yml 이 2시간마다 따로 돌면서 stocks.js 의
    # dataDate 를 그대로 물려받는다. 그래서 '시세보다 뒤처진' 상태는 정상 시차다.
    # 반대로 '시세보다 앞선' 날짜는 물려받을 수 없는 값이므로 오염을 뜻한다.
    if VALUATION.exists():
        try:
            vdate = str(read_js_object(VALUATION).get("dataDate") or "")
            if vdate and published and vdate > published:
                print(f"❌ valuation.js({vdate})가 stocks.js({published})보다 미래다 — 라벨 오염.")
                return 1
            if vdate and published and vdate < published:
                print(f"⚠️ valuation.js({vdate})가 시세({published})보다 뒤처짐 — "
                      "collect_valuation 이 아직 안 돈 정상 시차(최대 2시간).")
            else:
                print(f"valuation.js dataDate={vdate or '없음'} — 시세와 일치")
        except Exception as e:
            print(f"⚠️ valuation.js 확인 실패(무시): {type(e).__name__}: {e}")

    # 최신 거래일 판정은 수집기와 같은 규칙을 쓴다(장 마감 시각·주말·공휴일).
    # 이 판정 자체가 실패하면 '낡음'이 아니라 '판단 불가'다. 감시기가 자기
    # 사정으로 거짓 경보를 내면 진짜 경보까지 무시당한다.
    try:
        from collect_data import get_latest_trading_date, today_kst
        target = get_latest_trading_date()
        today = today_kst().strftime("%Y%m%d")
    except Exception as e:
        print(f"⏸️ 판단 보류 — 최신 거래일 판정기를 부르지 못했다: {type(e).__name__}: {e}")
        return 0

    state, why = judge(published, target, today)
    if state == OK:
        print(f"✅ 신선도 정상 — {why}")
        return 0
    if state == HOLD:
        print(f"⏸️ 판단 보류 — {why}")
        return 0

    print(f"::error::시세 데이터가 낡았다 — {why}")
    print("   원인 후보: ① 원본(FinanceData KRX 캐시 CSV) 미게시 "
          "② pykrx 경로 장애 ③ 수집 워크플로 미실행")
    return 1


if __name__ == "__main__":
    sys.exit(main())
