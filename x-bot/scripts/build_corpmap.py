#!/usr/bin/env python3
"""오프라인 빌드: 6자리 종목코드 → 8자리 DART corp_code 매핑 생성.

DART corpCode.xml(전체 기업 고유번호 파일)을 내려받아 상장사만 추려 매핑한다.
결과: x-bot/data/corpmap.json  { "005930": "00126380", ... }

실행: DART_API_KEY=xxxx python x-bot/scripts/build_corpmap.py
(온보딩 때 DART 키를 넣고 한 번만 돌리면 된다. 종목 편입은 가끔이라 주기적 갱신은 선택.)
"""
import io
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

import requests

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "corpmap.json")


def main():
    key = os.environ.get("DART_API_KEY", "").strip()
    if not key:
        print("❌ DART_API_KEY 환경변수가 필요합니다.")
        sys.exit(1)
    r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml",
                     params={"crtfc_key": key}, timeout=30)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    xml = zf.read(zf.namelist()[0])
    root = ET.fromstring(xml)
    mp = {}
    for el in root.iter("list"):
        corp = (el.findtext("corp_code") or "").strip()
        stock = (el.findtext("stock_code") or "").strip()
        if stock and corp and len(stock) == 6:
            mp[stock] = corp
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(mp, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ 상장사 {len(mp)}개 매핑 → {OUT}")


if __name__ == "__main__":
    main()
