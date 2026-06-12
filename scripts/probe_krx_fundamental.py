#!/usr/bin/env python3
"""KRX 전종목 PER/PBR/배당수익률 커버리지 검증 — 일회성 프로브.

우리 universe(data/stocks.js) 종목 중 몇 개에 KRX 공식 밸류에이션 값이
실제로 존재하는지 확인한다. 사이트에는 아무것도 쓰지 않는다.
"""
import datetime
import json
import re
from pathlib import Path


def main():
    raw = Path("data/stocks.js").read_text(encoding="utf-8")
    data = json.loads(
        re.search(r"window\.KOS_LIVE_DATA\s*=\s*(\{.*)", raw, re.S)
        .group(1).rstrip().rstrip(";")
    )
    universe = {s["ticker"]: s for s in data["stocks"]}
    date = data.get("dataDate") or datetime.date.today().strftime("%Y%m%d")
    print(f"universe: {len(universe)}개 / 기준일 {date}")

    import pandas as pd
    from pykrx import stock as krx

    frames = []
    for mkt in ("KOSPI", "KOSDAQ"):
        f = krx.get_market_fundamental_by_ticker(date, market=mkt)
        print(f"[{mkt}] {len(f)}행, 컬럼: {list(f.columns)}")
        frames.append(f)
    fund = pd.concat(frames)
    fund = fund[~fund.index.duplicated()]

    matched = fund.index.intersection(list(universe.keys()))
    missing = sorted(set(universe) - set(fund.index))
    print(f"\nKRX 펀더멘털 {len(fund)}행 | universe 매칭 {len(matched)}개 "
          f"| KRX에 없는 universe 종목 {len(missing)}개")

    sub = fund.loc[matched]
    n_u = len(universe)
    for col in ("PER", "PBR", "EPS", "BPS", "DIV"):
        if col in sub.columns:
            n = int((sub[col] > 0).sum())
            print(f"  {col} > 0 : {n}개 ({n / n_u * 100:.1f}%)")

    def sample(rows, label):
        print(f"\n{label}:")
        for s in rows:
            t = s["ticker"]
            if t in fund.index:
                r = fund.loc[t]
                print(f"  {s['name']}({t}) PER={r.get('PER')} PBR={r.get('PBR')} "
                      f"EPS={r.get('EPS')} BPS={r.get('BPS')} DIV={r.get('DIV')}")
            else:
                print(f"  {s['name']}({t}) — KRX 펀더멘털에 없음")

    by_mcap = sorted(universe.values(), key=lambda s: -(s.get("mcap") or 0))
    sample(by_mcap[:10], "시총 상위 10")
    sample(by_mcap[len(by_mcap) // 2:len(by_mcap) // 2 + 10], "시총 중간 10")
    sample(by_mcap[-10:], "시총 하위 10")

    if missing:
        print(f"\nKRX에 없는 universe 종목 예시 15개:",
              [f"{universe[t]['name']}({t})" for t in missing[:15]])


if __name__ == "__main__":
    main()
