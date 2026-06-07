#!/usr/bin/env python3
"""
KOS ai — DART 정기보고서(분기·반기·사업) 신규 제출 감지 (전 종목 대상)

상장 전 종목 중, '마지막 리포트 날짜보다 새로운' 정기보고서를 제출한 종목을 골라
GitHub Actions output(new_tickers, count)으로 내보낸다.

상태는 별도 파일이 아니라 data/reports.js(각 종목 reportDate) 자체를 사용한다.
  · 리포트가 없거나, 공시 접수일(rcept_dt)이 기존 reportDate보다 최신 → 재생성 대상
  · 생성에 성공하면 reportDate 가 갱신되어 자동으로 대상에서 빠진다
  · 생성 실패/타임아웃 종목은 reportDate 가 그대로라 다음 실행에서 자동 재시도(누락 방지)

대량 공시(실적 시즌) 대비, 1회 실행당 시총 상위순으로 MAX_PER_RUN 개만 내보내
여러 번에 나눠 백로그를 비운다(분산 처리).
"""

import os
import sys
import json
import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
REPORTS_JS = ROOT / "data" / "reports-index.js"   # 분할 구조: 가벼운 인덱스(reportDate 포함)

DART_API_KEY = os.getenv("DART_API_KEY")
# 1회 실행당 최대 생성 종목 수(0=무제한). 종목당 ~1분이므로 120≈2h (Actions 6h 한도 내).
MAX_PER_RUN = int(os.getenv("FILINGS_MAX_PER_RUN", "120") or "0")
# 조회 창. 백로그를 다 비울 때까지 공시가 창 안에 남아 있어야 하므로 넉넉히.
LOOKBACK = int(os.getenv("FILINGS_LOOKBACK_DAYS", "30"))
KEYWORDS = ("분기보고서", "반기보고서", "사업보고서")


def _load_json_blob(path):
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def universe():
    """ticker -> (name, mcap). 상장 전 종목."""
    o = _load_json_blob(STOCKS_JS)
    return {s["ticker"]: (s["name"], s.get("mcap", 0) or 0) for s in o["stocks"]}


def report_dates():
    """ticker -> reportDate('YYYYMMDD'). 리포트 없으면 키 없음."""
    out = {}
    if REPORTS_JS.exists():
        try:
            o = _load_json_blob(REPORTS_JS)
            for tk, r in (o.get("reports") or {}).items():
                d = str(r.get("reportDate", "")).replace("-", "").strip()
                if d:
                    out[tk] = d
        except Exception as e:
            print(f"⚠️ reports.js 파싱 실패(전부 신규로 간주): {e}")
    return out


def gh_output(**kv):
    path = os.getenv("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def main():
    if not DART_API_KEY:
        print("❌ DART_API_KEY 없음")
        gh_output(new_tickers="", count=0)
        sys.exit(1)

    import OpenDartReader
    dart = OpenDartReader(DART_API_KEY)

    uni = universe()
    reps = report_dates()

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=LOOKBACK)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    try:
        df = dart.list(start=start, end=end, kind="A", final=False)
    except Exception as e:
        print(f"⚠️ DART list 조회 실패: {e}")
        gh_output(new_tickers="", count=0)
        sys.exit(0)

    # ticker -> 가장 최신 공시 접수일(YYYYMMDD)
    cand = {}
    if df is not None and not getattr(df, "empty", True):
        for _, r in df.iterrows():
            sc = str(r.get("stock_code", "")).strip()
            nm = str(r.get("report_nm", ""))
            if sc not in uni or not any(k in nm for k in KEYWORDS):
                continue
            fdate = str(r.get("rcept_dt", "")).strip() or str(r.get("rcept_no", ""))[:8]
            if len(fdate) != 8 or not fdate.isdigit():
                continue
            # 기존 리포트보다 새로운 공시만(없으면 신규)
            if fdate <= reps.get(sc, ""):
                continue
            if fdate > cand.get(sc, ""):
                cand[sc] = fdate

    # 시총 상위순으로 정렬 후 1회 실행분만 선별(분산 처리)
    ranked = sorted(cand.keys(), key=lambda sc: uni[sc][1], reverse=True)
    total = len(ranked)
    picked = ranked[:MAX_PER_RUN] if MAX_PER_RUN > 0 else ranked

    for sc in picked:
        print(f"  · 갱신 대상: {sc} {uni[sc][0]} — 공시 {cand[sc]} (기존 리포트 {reps.get(sc,'없음')})")

    backlog = total - len(picked)
    print(f"\n📋 {start}~{end} 정기보고서 기준 갱신 대상 {total}개 중 이번 실행 {len(picked)}개"
          + (f" · 남은 백로그 {backlog}개(다음 실행에서 이어서)" if backlog > 0 else ""))
    gh_output(new_tickers=",".join(picked), count=len(picked))


if __name__ == "__main__":
    main()
