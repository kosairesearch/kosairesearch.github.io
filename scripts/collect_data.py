#!/usr/bin/env python3
"""
KOS ai — 일별 데이터 수집 스크립트
pykrx + DART API로 실제 주식 데이터를 수집해 data/stocks.js를 생성합니다.
매일 장 마감 후 GitHub Actions에서 자동 실행됩니다.
"""

import os
import json
import time
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")

# ── 업종 매핑 (시총 상위 150개 종목) ──────────────────────────────────────────
SECTOR_MAP = {
    # 반도체
    "005930": "반도체",   # 삼성전자
    "000660": "반도체",   # SK하이닉스
    "042700": "반도체",   # 한미반도체
    "058470": "반도체",   # 리노공업
    "000990": "반도체",   # DB하이텍
    "240810": "반도체",   # 원익IPS
    "357780": "반도체",   # 솔브레인
    "336370": "반도체",   # 에스에프에이
    "322000": "반도체",   # 코스텍시스
    "088390": "반도체",   # 유니테스트
    "036830": "반도체",   # 솔브레인홀딩스
    "102780": "반도체",   # 원익홀딩스
    # IT 서비스
    "035420": "IT 서비스", # NAVER
    "035720": "IT 서비스", # 카카오
    "323410": "IT 서비스", # 카카오뱅크
    "259960": "IT 서비스", # 크래프톤
    "036570": "IT 서비스", # 엔씨소프트
    "251270": "IT 서비스", # 넷마블
    "263750": "IT 서비스", # 펄어비스
    "293490": "IT 서비스", # 카카오게임즈
    # 2차전지
    "373220": "2차전지",  # LG에너지솔루션
    "006400": "2차전지",  # 삼성SDI
    "003670": "2차전지",  # 포스코퓨처엠
    "247540": "2차전지",  # 에코프로비엠
    "086520": "2차전지",  # 에코프로
    "066970": "2차전지",  # 엘앤에프
    "272290": "2차전지",  # 이노메트리
    # 바이오/제약
    "068270": "바이오/제약", # 셀트리온
    "207940": "바이오/제약", # 삼성바이오로직스
    "196170": "바이오/제약", # 알테오젠
    "000100": "바이오/제약", # 유한양행
    "009290": "바이오/제약", # HLB
    "128940": "바이오/제약", # 한미약품
    "000020": "바이오/제약", # 동화약품
    "185750": "바이오/제약", # 종근당
    "069620": "바이오/제약", # 대웅제약
    # 자동차
    "005380": "자동차",   # 현대차
    "000270": "자동차",   # 기아
    "012330": "자동차",   # 현대모비스
    "011210": "자동차",   # 현대위아
    "073240": "자동차",   # 금호타이어
    "161390": "자동차",   # 한국타이어앤테크놀로지
    # 금융
    "032830": "금융",     # 삼성생명
    "105560": "금융",     # KB금융
    "055550": "금융",     # 신한지주
    "086790": "금융",     # 하나금융지주
    "316140": "금융",     # 우리금융지주
    "003550": "금융",     # LG
    "000810": "금융",     # 삼성화재
    "002550": "금융",     # 미래에셋증권
    "006800": "금융",     # 미래에셋증권 우
    "071050": "금융",     # 한국금융지주
    # 에너지/화학
    "096770": "에너지",   # SK이노베이션
    "010950": "에너지",   # S-Oil
    "051910": "화학",     # LG화학
    "011170": "화학",     # 롯데케미칼
    "006360": "화학",     # GS건설
    # 철강/소재
    "005490": "철강",     # POSCO홀딩스
    "004020": "철강",     # 현대제철
    "001440": "철강",     # 태영건설
    # 조선/방산
    "009540": "조선·방산", # HD한국조선해양
    "329180": "조선·방산", # HD현대중공업
    "010140": "조선·방산", # 삼성중공업
    "042660": "조선·방산", # 한화오션
    "012450": "조선·방산", # 한화에어로스페이스
    "047810": "조선·방산", # 한국항공우주
    "079550": "조선·방산", # LIG넥스원
    # 통신
    "017670": "통신",     # SK텔레콤
    "030200": "통신",     # KT
    "032640": "통신",     # LG유플러스
    # 유통/소비재
    "139480": "유통·소비재", # 이마트
    "004170": "유통·소비재", # 신세계
    "069960": "유통·소비재", # 현대백화점
    "282330": "유통·소비재", # BGF리테일
    # 식품
    "000080": "식품",     # 하이트진로
    "097950": "식품",     # CJ제일제당
    "271560": "식품",     # 오리온
    "033780": "식품",     # KT&G
    # 엔터/미디어
    "041510": "엔터·미디어", # 에스엠
    "035900": "엔터·미디어", # JYP Ent.
    "122870": "엔터·미디어", # YG PLUS
    "352820": "엔터·미디어", # 하이브
    # 건설
    "000720": "건설",     # 현대건설
    "047040": "건설",     # 대우건설
    "028050": "건설",     # 삼성엔지니어링
    # 기계/로봇
    "064350": "기계·로봇", # 현대로보틱스
    "267260": "기계·로봇", # 현대일렉트릭
}


def get_latest_trading_date():
    """가장 최근 영업일을 반환합니다."""
    from pykrx import stock as krx
    for days_back in range(10):
        date = datetime.date.today() - datetime.timedelta(days=days_back)
        if date.weekday() >= 5:
            continue
        datestr = date.strftime("%Y%m%d")
        try:
            df = krx.get_market_ohlcv_by_date(datestr, datestr, "005930")
            if df is not None and not df.empty:
                return datestr
        except Exception:
            continue
    return datetime.date.today().strftime("%Y%m%d")


def collect_pykrx(date):
    """pykrx로 시세·지표 데이터를 수집합니다."""
    from pykrx import stock as krx

    print(f"  [pykrx] {date} 데이터 수집 중...")

    results = {}

    for market_code, market_label in [("KOSPI", "코스피"), ("KOSDAQ", "코스닥")]:
        try:
            # 시가총액·상장주식수
            cap = krx.get_market_cap_by_ticker(date, market=market_code)
            # PER·PBR·EPS·BPS·배당수익률
            fund = krx.get_market_fundamental_by_ticker(date, market=market_code)
            # 당일 OHLCV (등락률 포함)
            ohlcv = krx.get_market_ohlcv_by_ticker(date, market=market_code)

            for ticker in cap.index:
                name = krx.get_market_ticker_name(ticker)
                if not name:
                    continue

                cap_row  = cap.loc[ticker]  if ticker in cap.index  else {}
                fund_row = fund.loc[ticker] if ticker in fund.index else {}
                ohlcv_row= ohlcv.loc[ticker]if ticker in ohlcv.index else {}

                mcap_won = int(cap_row.get("시가총액", 0))

                results[ticker] = {
                    "ticker":  ticker,
                    "name":    name,
                    "market":  market_label,
                    "sector":  SECTOR_MAP.get(ticker, "기타"),
                    # 시세
                    "price":  int(ohlcv_row.get("종가", 0)),
                    "change": round(float(ohlcv_row.get("등락률", 0)), 2),
                    "volume":       int(ohlcv_row.get("거래량", 0)),
                    "trading_value":int(ohlcv_row.get("거래대금", 0)),
                    # 시총
                    "mcap":  round(mcap_won / 1e12, 1),   # 원 → 조원
                    "shares":int(cap_row.get("상장주식수", 0)),
                    # 밸류에이션
                    "per": round(float(fund_row.get("PER", 0)), 1),
                    "pbr": round(float(fund_row.get("PBR", 0)), 1),
                    "eps": int(fund_row.get("EPS", 0)),
                    "bps": int(fund_row.get("BPS", 0)),
                    "div": round(float(fund_row.get("DIV", 0)), 1),
                    # 재무비율 (DART로 채울 예정, 기본값 0)
                    "roe":  0.0,
                    "rev":  0.0,   # 매출 성장률
                    "opm":  0.0,   # 영업이익률
                    "debt": 0.0,   # 부채비율
                }
            print(f"    {market_label} {len(cap)}개 종목 완료")
            time.sleep(0.5)
        except Exception as e:
            print(f"    [경고] {market_label} 수집 오류: {e}")

    return results


def enrich_with_dart(results):
    """DART API로 재무비율(ROE, 매출성장률, 영업이익률, 부채비율)을 보완합니다."""
    if not DART_API_KEY:
        print("  [DART] API 키 없음, 재무비율 생략")
        return results

    try:
        import OpenDartReader
        dart = OpenDartReader(DART_API_KEY)
    except Exception as e:
        print(f"  [DART] 초기화 실패: {e}")
        return results

    # 시총 상위 50개만 DART 보강 (API 호출 제한 고려)
    top50 = sorted(results.values(), key=lambda x: x["mcap"], reverse=True)[:50]

    print(f"  [DART] 상위 50개 종목 재무비율 수집 중...")
    for i, stock in enumerate(top50):
        ticker = stock["ticker"]
        try:
            year = datetime.date.today().year - 1  # 전년도 연간 데이터
            fs = dart.finstate(ticker, year)
            if fs is None or fs.empty:
                continue

            def get_amount(account_name):
                row = fs[fs["account_nm"].str.contains(account_name, na=False)]
                if row.empty:
                    return 0
                val = row.iloc[0].get("thstrm_amount", "0")
                return int(str(val).replace(",", "").replace("-", "0") or 0)

            revenue      = get_amount("매출액")
            revenue_prev = get_amount("전기매출액") or get_amount("매출액")  # fallback
            op_profit    = get_amount("영업이익")
            net_income   = get_amount("당기순이익")
            equity       = get_amount("자본총계")
            liabilities  = get_amount("부채총계")

            roe  = round(net_income / equity * 100, 1) if equity > 0 else 0
            opm  = round(op_profit / revenue * 100, 1) if revenue > 0 else 0
            debt = round(liabilities / equity * 100, 1) if equity > 0 else 0

            results[ticker]["roe"]  = roe
            results[ticker]["opm"]  = opm
            results[ticker]["debt"] = debt

            if i % 10 == 0:
                print(f"    {i+1}/50 완료...")
            time.sleep(0.3)

        except Exception as e:
            pass  # DART 오류는 조용히 무시 (시세 데이터는 이미 있음)

    print("  [DART] 재무비율 보강 완료")
    return results


def build_output(results, date):
    """웹사이트용 JS 파일을 생성합니다."""

    # 시가총액순 정렬, 상위 100개
    stocks = sorted(results.values(), key=lambda x: x["mcap"], reverse=True)
    stocks = [s for s in stocks if s["price"] > 0][:100]

    # 순위 추가
    for i, s in enumerate(stocks):
        s["rank"] = i + 1

    # 마지막 업데이트 시각
    now_kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
    last_updated = now_kst.strftime("%Y-%m-%d %H:%M")

    output = {
        "lastUpdated": last_updated,
        "dataDate":    date,
        "stocks":      stocks,
    }

    js = "// KOS ai — 자동 생성 데이터 파일. 직접 수정하지 마세요.\n"
    js += f"window.KOS_LIVE_DATA = {json.dumps(output, ensure_ascii=False, indent=2)};\n"

    Path("data").mkdir(exist_ok=True)
    Path("data/stocks.js").write_text(js, encoding="utf-8")
    print(f"\n✅ data/stocks.js 생성 완료 — {len(stocks)}개 종목 ({last_updated} KST)")


def main():
    print("=" * 55)
    print("  KOS ai 데이터 수집 시작")
    print("=" * 55)

    date = get_latest_trading_date()
    print(f"  기준일: {date}\n")

    results = collect_pykrx(date)
    results = enrich_with_dart(results)
    build_output(results, date)

    print("=" * 55)


if __name__ == "__main__":
    main()
