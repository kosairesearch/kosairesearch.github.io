#!/usr/bin/env python3
"""
KOS ai — DART 정기보고서(분기·반기·사업) 신규 제출 감지

우리 유니버스(시총 상위 TOP_N) 중 최근 정기보고서를 '새로' 제출한 종목을 골라
GitHub Actions output(new_tickers, count)으로 내보낸다.
처리 이력은 data/filings_state.json 에 누적(rcept_no 기준 중복 방지).
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
STATE = ROOT / "data" / "filings_state.json"

DART_API_KEY = os.getenv("DART_API_KEY")
TOP_N = int(os.getenv("REPORT_TOP_N", "100"))
LOOKBACK = int(os.getenv("FILINGS_LOOKBACK_DAYS", "3"))
KEYWORDS = ("분기보고서", "반기보고서", "사업보고서")


def universe():
    raw = STOCKS_JS.read_text(encoding="utf-8")
    o = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    top = sorted(o["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:TOP_N]
    return {s["ticker"]: s["name"] for s in top}


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
    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    seen = set(state.get("seen_rcept", []))

    today = datetime.date.today()
    start = (today - datetime.timedelta(days=LOOKBACK)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    try:
        df = dart.list(start=start, end=end, kind="A", final=False)
    except Exception as e:
        print(f"⚠️ DART list 조회 실패: {e}")
        df = None

    new = {}   # ticker -> name
    if df is not None and not getattr(df, "empty", True):
        for _, r in df.iterrows():
            sc = str(r.get("stock_code", "")).strip()
            nm = str(r.get("report_nm", ""))
            rc = str(r.get("rcept_no", "")).strip()
            if sc in uni and rc and rc not in seen and any(k in nm for k in KEYWORDS):
                new[sc] = uni[sc]
                seen.add(rc)
                print(f"  · 신규 공시: {sc} {uni[sc]} — {nm} ({rc})")

    STATE.write_text(json.dumps(
        {"updated": end, "seen_rcept": sorted(seen)}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    tickers = ",".join(new.keys())
    print(f"\n📋 {start}~{end} 정기보고서 신규 제출(유니버스 내): {len(new)}개 {list(new.values())}")
    gh_output(new_tickers=tickers, count=len(new))


if __name__ == "__main__":
    main()
