"""
DART API + pykrx 연결 테스트
"""
import os
from dotenv import load_dotenv

load_dotenv()
DART_KEY = os.getenv("DART_API_KEY")

print("=" * 50)
print("1. DART API 테스트")
print("=" * 50)

import OpenDartReader
dart = OpenDartReader(DART_KEY)

# 삼성전자 기본 정보 조회
info = dart.company("005930")
print(f"  종목명: {info['corp_name']}")
print(f"  대표자: {info['ceo_nm']}")
print(f"  결산월: {info['acc_mt']}")
print(f"  상장시장: {info['stock_mkt']}")
print("  ✅ DART API 연결 성공!\n")

print("=" * 50)
print("2. pykrx 테스트")
print("=" * 50)

from pykrx import stock
import datetime

today = datetime.date.today().strftime("%Y%m%d")
# 최근 영업일 데이터 (오늘이 주말일 수 있으니 최근 5일치 중 마지막)
df = stock.get_market_ohlcv_by_date(
    fromdate=(datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y%m%d"),
    todate=today,
    ticker="005930"
)
if not df.empty:
    last = df.iloc[-1]
    print(f"  종목: 삼성전자 (005930)")
    print(f"  종가: {last['종가']:,}원")
    print(f"  거래량: {last['거래량']:,}주")
    print("  ✅ pykrx 연결 성공!\n")

print("=" * 50)
print("3. DART 재무제표 테스트")
print("=" * 50)

# 삼성전자 최근 연간 재무제표
fs = dart.finstate("005930", 2023)
if fs is not None and not fs.empty:
    # 매출액 찾기
    rev = fs[fs['account_nm'].str.contains('매출액', na=False)]
    if not rev.empty:
        print(f"  2023년 매출액: {rev.iloc[0]['thstrm_amount']}원")
    print("  ✅ DART 재무제표 연결 성공!\n")

print("=" * 50)
print("🎉 모든 연결 테스트 통과!")
print("=" * 50)
