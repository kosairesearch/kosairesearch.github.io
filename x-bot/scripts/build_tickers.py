#!/usr/bin/env python3
"""오프라인 빌드: 전 상장종목 매칭 테이블(tickers.json) 생성.

스펙상 한글명은 pykrx 상장리스트, 영문명은 DART corpCode 영문 회사명을 쓰라고 했는데,
KOSAI 파이프라인이 이미 그 둘을 병합해 data/stocks.js(name=KRX 한글, name_en=DART 영문)로
매일 관리하고 있다. 그래서 같은 데이터를 단일 소스(stocks.js)에서 뽑아 유니버스와 항상
동기화되게 한다. (별도로 pykrx/DART를 재조회하면 종목 편입/퇴출이 어긋난다.)

출력: x-bot/data/tickers.json
  { "built": "YYYY-MM-DD",
    "stocks": [ {"t": 코드, "ko": 한글명, "en": 영문명, "mcap": 시총조}, ... ],
    "aliases": { 정규화된별칭: 코드, ... } }
"""
import json
import os
import re
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STOCKS_JS = os.path.join(ROOT, "data", "stocks.js")
OUT = os.path.join(ROOT, "x-bot", "data", "tickers.json")

# 한글 별칭 사전 — 코드로 직접 매핑(정규화 후 키). 사용자가 자유롭게 추가 가능.
# key: 사람들이 실제로 부르는 약칭/별명, value: 6자리 종목코드
ALIAS_TO_TICKER = {
    "삼전": "005930", "삼성": "005930", "갤럭시": "005930",
    "하이닉스": "000660", "sk하이닉스": "000660", "sk하닉": "000660", "하닉": "000660",
    "현차": "005380", "현대차": "005380",
    "기아차": "000270",
    "네이버": "035420", "naver": "035420",
    "카톡": "035720", "카카오톡": "035720",
    "lg엔솔": "373220", "엔솔": "373220", "lg에너지": "373220",
    "삼바": "207940", "삼성바이오": "207940",
    "셀트": "068270",
    "포스코": "005490", "포스코홀딩스": "005490",
    "현모비스": "012330",
    "삼성sdi": "006400", "삼디": "006400",
    "한전": "015760", "한국전력": "015760",
    "케이비": "105560", "kb금융": "105560",
    "신한지주": "055550",
    "현중": "329180", "현대중공업": "329180",
    "두산에너빌": "034020", "두산에너빌리티": "034020",
    "레인보우": "277810", "레인보우로보틱스": "277810",
    "에코프로비엠": "247540", "에코비엠": "247540",
    "에코프로": "086520",
    "삼성전기": "009150",
    "엘지전자": "066570", "lg전자": "066570",
    "엘지화학": "051910", "lg화학": "051910",
}

_EN_STOP = {"co", "ltd", "inc", "corp", "corporation", "company", "limited",
            "holdings", "holding", "group", "co.", "ltd.", "inc.", "the"}


def norm_ko(s):
    """한글명 정규화: 소문자화 + 공백/문장부호 제거."""
    s = (s or "").lower()
    return re.sub(r"[\s\.\,\/\(\)·\-&']", "", s)


def norm_en(s):
    """영문명 정규화: 소문자 + Co./Ltd 등 접미어 토큰 제거 + 공백/부호 제거."""
    s = (s or "").lower()
    s = re.sub(r"[\.\,\/\(\)·\-&']", " ", s)
    toks = [t for t in s.split() if t and t not in _EN_STOP]
    return "".join(toks)


def main():
    raw = open(STOCKS_JS, encoding="utf-8").read()
    obj = json.loads(re.search(r"=\s*(\{.*)", raw, re.S).group(1).strip().rstrip(";"))
    out_stocks = []
    for s in obj.get("stocks", []):
        t = s.get("ticker")
        if not t:
            continue
        out_stocks.append({
            "t": t,
            "ko": s.get("name") or "",
            "en": s.get("name_en") or "",
            "mcap": s.get("mcap") or 0,
        })
    # 별칭 정규화
    aliases = {}
    for k, v in ALIAS_TO_TICKER.items():
        aliases[norm_ko(k)] = v

    kst = timezone(timedelta(hours=9))
    payload = {
        "built": datetime.now(kst).strftime("%Y-%m-%d"),
        "stocks": out_stocks,
        "aliases": aliases,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"✅ {len(out_stocks)} 종목 · 별칭 {len(aliases)}개 → {OUT}")


if __name__ == "__main__":
    main()
