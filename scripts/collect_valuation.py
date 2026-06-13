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


def collect_one(dart, ticker, stock):
    """한 종목의 분기성 밸류에이션 빌딩블록 수집. {eps,bps,dps,roe,rev_g} (없으면 키 생략)."""
    cur = datetime.date.today().year
    py = cur - 1
    a1 = v2._fin_all(dart, ticker, py, "11011")        # 최근 결산
    if not a1:
        a1 = v2._fin_all(dart, ticker, cur - 2, "11011")  # 결산 미공시 시 그 전년
        py = cur - 2
    a2 = v2._fin_all(dart, ticker, py - 1, "11011")    # 성장률용 직전 연도
    q_cur = v2._fin_all(dart, ticker, cur, "11013")    # 올해 1분기
    q_py = v2._fin_all(dart, ticker, py, "11013")      # 작년 1분기

    out = {}
    total_sh = v2.dart_total_shares(dart, ticker) or stock.get("shares") or 0
    price = stock.get("price") or 0

    # 지배주주 순이익(연간·분기)
    a1_np = v2._cum(a1, "np_owner") if a1 else None
    a1_eqo = (v2._bs(a1, "equity_owner") or v2._bs(a1, "equity")) if a1 else None
    qc_np = v2._cum(q_cur, "np_owner") if q_cur else None
    qp_np = v2._cum(q_py, "np_owner") if q_py else None
    qc_eqo = (v2._bs(q_cur, "equity_owner") or v2._bs(q_cur, "equity")) if q_cur else None

    # TTM EPS = (최근연간 − 작년1Q + 올해1Q) ÷ 발행주식총수
    if None not in (a1_np, qp_np, qc_np) and total_sh:
        ttm = a1_np - qp_np + qc_np
        out["eps"] = int(ttm / total_sh)

    # BPS = 최근 분기말 지배자본 ÷ 가중평균유통주식수(자기주식 제외)
    def implied_wavg(npo, eps):
        if npo and eps and abs(eps) > 1:
            w = npo / eps
            if w > 0 and 0.3 * total_sh <= w <= 1.05 * total_sh:
                return w
        return None
    wavg = (implied_wavg(qc_np, v2._cum(q_cur, "eps_basic") if q_cur else None)
            or implied_wavg(a1_np, v2._cum(a1, "eps_basic") if a1 else None))
    eqo_latest = qc_eqo or a1_eqo
    bps_denom = wavg or total_sh
    if eqo_latest and bps_denom:
        out["bps"] = int(eqo_latest / bps_denom)

    # ROE = 최근연간 지배순이익 ÷ 최근연간 지배자본
    if a1_np is not None and a1_eqo:
        out["roe"] = round(a1_np / a1_eqo * 100, 1)

    # 매출성장률(YoY)
    r1 = v2._cum(a1, "rev") if a1 else None
    r2 = v2._cum(a2, "rev") if a2 else None
    if r1 and r2 and r2 != 0:
        out["rev_g"] = round((r1 - r2) / abs(r2) * 100, 1)

    # DPS(주당현금배당금) — DART 우선, KRX 보완
    dps = v2.dart_dps(dart, ticker)
    if dps is not None:
        out["dps"] = round(dps, 1)
    return out


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
    quarter_tag = data_date  # 같은 데이터일자 기준 재수집 방지(분기 갱신은 FORCE로)
    stocks = sorted(data["stocks"], key=lambda s: s.get("mcap", 0) or 0, reverse=True)

    existing = {} if os.getenv("FORCE") == "1" else load_existing()
    budget = int(os.getenv("BUDGET_MIN", "50")) * 60
    t0 = time.time()

    done = 0
    skipped = 0
    new = 0
    for s in stocks:
        tk = s["ticker"]
        if tk in existing and existing[tk].get("_q") == quarter_tag:
            skipped += 1
            continue
        if time.time() - t0 > budget:
            log(f"- ⏳ 시간예산 초과 — 저장 후 종료(다음 실행 이어받기). 처리 {new}건")
            break
        try:
            v = collect_one(dart, tk, s)
            v["_q"] = quarter_tag
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
    have = sum(1 for s in stocks if s["ticker"] in existing)
    log(f"\n✅ 밸류에이션 수집 — 이번 {new}건 신규 / 건너뜀 {skipped} / 누적 {have}/{total}개")
    if have < total:
        log(f"- 남은 {total-have}개는 다음 실행에서 이어받기")


if __name__ == "__main__":
    main()
