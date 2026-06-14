#!/usr/bin/env python3
"""
전 종목 밸류에이션(정량) 수집 — 상단 그리드·스크리너용 데이터.

종목별로 EPS·BPS·DPS·ROE·매출성장률을 DART에서 직접 수집해
data/valuation.js (window.KOS_VALUATION) 로 저장한다.
  - PER·PBR·배당수익률은 '주가 ÷ EPS/BPS', 'DPS ÷ 주가' 라서 저장하지 않고
    화면에서 그날 주가로 즉석 계산한다(매일 라이브). 여기엔 분기성 값만 저장.

설계: DART 호출이 많아(종목당 ~6회) 한 번에 다 못 돌리므로
  - 시총 큰 종목부터 처리(가장 많이 보는 종목 우선)
  - 이미 수집된(같은 분기) 종목은 건너뜀(이어받기)
  - 시간예산(BUDGET_MIN) 초과 시 안전 저장 후 종료 → 다음 실행이 이어받음
  - 50종목마다 중간 저장(중단되어도 진행분 보존)

환경변수: DART_API_KEY(필수), KRX_ID/KRX_PW(선택, 배당 보완),
          BUDGET_MIN(기본 50), FORCE(1이면 전부 재수집)
"""
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_reports as g
import generate_reports_v2 as v2

OUT = ROOT / "data" / "valuation.js"
log = g.log


def load_existing():
    if not OUT.exists():
        return {}
    try:
        m = re.search(r"window\.KOS_VALUATION\s*=\s*(\{.*)", OUT.read_text(encoding="utf-8"), re.S)
        obj = json.loads(m.group(1).rstrip().rstrip(";"))
        return obj.get("stocks", {})
    except Exception as e:
        log(f"- 기존 valuation.js 로드 실패: {type(e).__name__}: {e}")
        return {}


def write_out(stocks, data_date):
    payload = {
        "asOf": (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M"),
        "dataDate": data_date,
        "count": len(stocks),
        "stocks": stocks,
    }
    OUT.write_text(
        "// KOS ai — 전 종목 밸류에이션(자동 생성). PER·PBR·배당은 화면에서 주가로 즉석 계산.\n"
        "window.KOS_VALUATION = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8")


REPORTS_V2 = ROOT / "data" / "reports_v2"


def _summary_from_valuation(val, annual):
    """리포트 quant.valuation → 그리드용 {eps,bps,roe,dps,rev_g} 요약."""
    out = {}
    if val.get("eps") is not None:
        out["eps"] = val["eps"]
    if val.get("bps") is not None:
        out["bps"] = val["bps"]
    if val.get("roe_ttm") is not None:
        out["roe"] = val["roe_ttm"]
    if val.get("dps") is not None:
        out["dps"] = val["dps"]
    if len(annual) >= 2 and annual[0].get("rev") and annual[1].get("rev"):
        out["rev_g"] = round((annual[0]["rev"] - annual[1]["rev"]) / abs(annual[1]["rev"]) * 100, 1)
    return out


def collect_one(dart, ticker, stock):
    """한 종목의 그리드용 밸류에이션 {eps,bps,dps,roe,rev_g}.

    ⚠️ 리포트(reports_v2)와 동일한 정량 파이프라인(collect_quant)을 사용한다.
       추출 로직이 두 벌로 갈라져 그리드만 값이 비던 문제(카카오뱅크 등)를 없애기 위함.
       이미 v2 리포트가 있으면 그 quant 값을 그대로 재사용 → 그리드 = 리포트 항상 일치.
    """
    rp = REPORTS_V2 / f"{ticker}.json"
    if rp.exists():
        try:
            q = json.loads(rp.read_text(encoding="utf-8"))["quant"]
            return _summary_from_valuation(q.get("valuation", {}), q.get("annual", []))
        except Exception:
            pass
    # 리포트 없음 → 리포트와 똑같은 collect_quant로 산출 + 네이버 대조 게이트
    q = v2.collect_quant(dart, ticker, None, stock)
    val = q.get("valuation", {})
    v2.cross_check(ticker, stock.get("name", ticker), val)   # EPS·BPS 네이버 대조(어긋나면 숨김)
    return _summary_from_valuation(val, q.get("annual", []))


def main():
    if not os.getenv("DART_API_KEY"):
        log("❌ DART_API_KEY 없음")
        sys.exit(1)
    dart = g.get_dart()
    if not dart:
        log("❌ DART 초기화 실패")
        sys.exit(1)

    data = g.load_stocks()
    data_date = data.get("dataDate", "")
    stocks = sorted(data["stocks"], key=lambda s: s.get("mcap", 0) or 0, reverse=True)

    # 특정 종목만(공시 트리거 등) 즉시 재수집: VAL_TICKERS="A,B,C"
    #   기존 데이터는 보존하고 지정 종목만 신선도 무시하고 다시 가져온다.
    only = [t for t in os.getenv("VAL_TICKERS", "").replace(" ", "").split(",") if t]
    only_mode = bool(only)
    if only_mode:
        want = set(only)
        stocks = [s for s in stocks if s["ticker"] in want]
        log(f"- VAL_TICKERS 지정 — {len(stocks)}개만 즉시 재수집")

    # 갱신 정책: 종목별로 산식버전(_v)이 같고 최근 REFRESH_DAYS 이내에 수집했으면 건너뜀.
    #   → 평소엔 종목당 약 한 달마다 자동 재수집(분기 실적을 한 달 내 자동 반영),
    #     산식(VERSION)이 바뀌면 1회 전체 재수집. 매일 전체 재수집하지 않는다.
    VERSION = "r7"  # 추출 통합: 리포트와 동일 파이프라인(collect_quant) 사용
    REFRESH_DAYS = int(os.getenv("REFRESH_DAYS", "30"))
    today = datetime.date.today()
    force = os.getenv("FORCE") == "1"
    existing = {} if force else load_existing()

    def needs(tk):
        if only_mode:        # 지정 종목은 무조건 재수집
            return True
        e = existing.get(tk)
        if not e or e.get("_v") != VERSION:
            return True
        d = e.get("_d")
        try:
            if d and (today - datetime.date.fromisoformat(d)).days < REFRESH_DAYS:
                return False
        except Exception:
            pass
        return True

    budget = int(os.getenv("BUDGET_MIN", "50")) * 60
    t0 = time.time()

    done = 0
    skipped = 0
    new = 0
    for s in stocks:
        tk = s["ticker"]
        if not force and not needs(tk):
            skipped += 1
            continue
        if time.time() - t0 > budget:
            log(f"- ⏳ 시간예산 초과 — 저장 후 종료(다음 실행 이어받기). 처리 {new}건")
            break
        try:
            v = collect_one(dart, tk, s)
            v["_v"] = VERSION
            v["_d"] = today.isoformat()
            existing[tk] = v
            new += 1
            if v:
                log(f"  · {tk} {s['name']}: EPS={v.get('eps')} BPS={v.get('bps')} "
                    f"ROE={v.get('roe')} DPS={v.get('dps')} 성장={v.get('rev_g')}")
        except Exception as e:
            log(f"  · ⚠️ {tk} {s.get('name')} 실패: {type(e).__name__}: {e}")
        done += 1
        if new % 50 == 0 and new:
            write_out(existing, data_date)
        time.sleep(0.12)

    write_out(existing, data_date)
    total = len(data["stocks"])
    have = len(existing)
    remaining = 0 if only_mode else sum(1 for s in stocks if needs(s["ticker"]))
    log(f"\n✅ 밸류에이션 수집 — 이번 {new}건 신규 / 건너뜀 {skipped} / 보유 {have}/{total}개 / 갱신필요 {remaining}개")
    if remaining > 0:
        log(f"- VALUATION_REMAINING {remaining}개 (다음 실행에서 이어받기)")
    else:
        log("- VALUATION_COMPLETE 전 종목 최신 — 추가 수집 없음")


if __name__ == "__main__":
    main()
