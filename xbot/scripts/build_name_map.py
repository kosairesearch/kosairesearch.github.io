"""종목명 매핑(data/name_map.json) 생성 — 로컬/CI에서 실행 후 커밋.

한글명·시장 = pykrx 상장종목 리스트, 영문명·DART코드 = DART corpCode 파일.
실행: DART_API_KEY=... python scripts/build_name_map.py
"""
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "data" / "name_map.json"

# 한글 별칭 사전 — 트위터에서 실제로 쓰는 줄임말들. 필요할 때마다 추가.
ALIASES = {
    "삼전": "005930", "삼성전자": "005930",
    "하닉": "000660", "sk하이닉스": "000660", "하이닉스": "000660",
    "현차": "005380", "현대차": "005380",
    "엘지엔솔": "373220", "엔솔": "373220",
    "네이버": "035420", "카카오": "035720",
    "셀트": "068270", "포스코": "005490", "포홀": "005490",
    "금양": "001570", "에코프로": "086520", "에코비": "247540",
    "레인보우": "277810", "로보틱스": "277810",
}


def krx_names():
    from pykrx import stock as krx
    out = {}
    for market in ("KOSPI", "KOSDAQ"):
        for code in krx.get_market_ticker_list(market=market):
            out[code] = {"code": code, "ko": krx.get_market_ticker_name(code),
                         "market": market}
    return out


def dart_english(api_key):
    """DART corpCode.zip → {6자리 종목코드: (영문명, DART 8자리 코드)}"""
    r = requests.get("https://opendart.fss.or.kr/api/corpCode.xml",
                     params={"crtfc_key": api_key}, timeout=60)
    z = zipfile.ZipFile(io.BytesIO(r.content))
    xml = z.read(z.namelist()[0]).decode("utf-8")
    out = {}
    for m in re.finditer(
            r"<list>.*?<corp_code>(.*?)</corp_code>.*?"
            r"<corp_eng_name>(.*?)</corp_eng_name>.*?"
            r"<stock_code>(.*?)</stock_code>.*?</list>", xml, re.S):
        dart, en, stock = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        if stock:
            out[stock] = (en, dart)
    return out


def main():
    key = os.getenv("DART_API_KEY", "")
    if not key:
        sys.exit("DART_API_KEY 환경변수가 필요합니다.")
    stocks = krx_names()
    eng = dart_english(key)
    for code, st in stocks.items():
        en, dart = eng.get(code, ("", ""))
        st["en"] = en
        st["dart"] = dart
    # 별칭 정규화(공백 제거·소문자) — 런타임 norm()과 동일 규칙일 필요는 없고 키만 단순하게
    aliases = {re.sub(r"\s+", "", k.lower()): v for k, v in ALIASES.items()
               if v in stocks}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"stocks": stocks, "aliases": aliases},
                              ensure_ascii=False), encoding="utf-8")
    n_en = sum(1 for s in stocks.values() if s["en"])
    print(f"저장: {OUT} · 종목 {len(stocks)}개 · 영문명 {n_en}개 · 별칭 {len(aliases)}개")


if __name__ == "__main__":
    main()
