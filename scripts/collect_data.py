#!/usr/bin/env python3
"""
KOS ai — 일별 데이터 수집 스크립트
pykrx + DART API로 실제 주식 데이터를 수집해 data/stocks.js를 생성합니다.
매일 장 마감 후 GitHub Actions에서 자동 실행됩니다.
"""

import os
import sys
import json
import time
import traceback
import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY")

# 전 종목(universe) 수집 모드. 미설정이면 기존 SECTOR_MAP 방식(daily cron 안전).
FULL_UNIVERSE = os.getenv("FULL_UNIVERSE", "") == "1"
# 0이면 무제한. 디버그/부분 수집용 상한.
UNIVERSE_LIMIT = int(os.getenv("UNIVERSE_LIMIT", "0") or "0")

# GitHub Actions Step Summary 지원
STEP_SUMMARY = os.getenv("GITHUB_STEP_SUMMARY")

def log_summary(msg):
    print(msg)
    if STEP_SUMMARY:
        with open(STEP_SUMMARY, "a", encoding="utf-8") as f:
            f.write(msg + "\n")

# ── 업종 매핑 (시총 상위 종목) ──────────────────────────────────────────
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
    # ── 시총 상위 100 커버용 추가 대형주 ──
    "015760": "에너지",      # 한국전력
    "047050": "유통·소비재", # 포스코인터내셔널
    "028260": "건설",        # 삼성물산
    "034730": "금융",        # SK(주)
    "018260": "IT 서비스",   # 삼성에스디에스
    "009150": "전자·부품",   # 삼성전기
    "011070": "전자·부품",   # LG이노텍
    "066570": "전자·부품",   # LG전자
    "034220": "전자·부품",   # LG디스플레이
    "011200": "운송",        # HMM
    "086280": "운송",        # 현대글로비스
    "003490": "운송",        # 대한항공
    "034020": "기계·로봇",   # 두산에너빌리티
    "241560": "기계·로봇",   # 두산밥캣
    "000150": "금융",        # 두산
    "051900": "유통·소비재", # LG생활건강
    "090430": "유통·소비재", # 아모레퍼시픽
    "023530": "유통·소비재", # 롯데쇼핑
    "004990": "금융",        # 롯데지주
    "008770": "유통·소비재", # 호텔신라
    "024110": "금융",        # 기업은행
    "138040": "금융",        # 메리츠금융지주
    "029780": "금융",        # 삼성카드
    "326030": "바이오/제약", # SK바이오팜
    "011790": "화학",        # SKC
    "010060": "화학",        # OCI홀딩스
    "285130": "화학",        # SK케미칼
    "267250": "조선·방산",   # HD현대
    "375500": "건설",        # DL이앤씨
    "010130": "철강·금속",   # 고려아연
    # 로봇 (핫테마 — universe 보강)
    "454910": "기계·장비",   # 두산로보틱스
    "277810": "기계·장비",   # 레인보우로보틱스
}

# ════════════════════════════════════════════════════════════════════
# 카테고리 체계 (다중 태그 + 대표 1개)
#   - 대표 카테고리(primary): 종목의 본업. KSIC 자동분류 + 예외 override.
#   - 카테고리 태그(categories): 대표 + 핫테마(인공지능/로봇 등). 종목당 여러 개.
# ════════════════════════════════════════════════════════════════════

# ── KSIC 업종코드 → 대표 카테고리 (전 시장 자동분류) ──
KSIC4 = {"2042": "화장품"}   # 화장품 세분(20 화학에서 분리)
KSIC3 = {
    "261": "반도체", "262": "전자·부품", "263": "전자·부품", "264": "전자·부품",
    "265": "전자·부품", "266": "전자·부품",
    "281": "전기장비", "282": "2차전지", "283": "전기장비", "284": "전기장비",
    "301": "자동차", "302": "자동차", "303": "자동차",
    "311": "조선", "312": "운송·물류", "313": "항공·방산",
    "351": "에너지·전력", "352": "에너지·전력",
    "211": "바이오·제약", "212": "바이오·제약",
    "581": "미디어·엔터", "582": "게임", "591": "미디어·엔터", "601": "미디어·엔터",
    "611": "통신", "612": "통신", "613": "통신",
    "620": "IT·소프트웨어", "631": "IT·소프트웨어",
}
KSIC2 = {
    "10": "식음료", "11": "식음료", "12": "식음료",
    "13": "섬유·패션·생활", "14": "섬유·패션·생활", "15": "섬유·패션·생활",
    "16": "섬유·패션·생활", "17": "섬유·패션·생활", "18": "섬유·패션·생활",
    "19": "정유", "20": "화학", "21": "바이오·제약", "22": "섬유·패션·생활",
    "23": "건설·건자재", "24": "철강·금속", "25": "철강·금속",
    "26": "전자·부품", "27": "전자·부품", "28": "전기장비",
    "29": "기계·장비", "30": "자동차", "31": "항공·방산",
    "32": "섬유·패션·생활", "33": "섬유·패션·생활",
    "35": "에너지·전력", "36": "에너지·전력",
    "41": "건설·건자재", "42": "건설·건자재",
    "45": "유통·소비재", "46": "유통·소비재", "47": "유통·소비재",
    "49": "운송·물류", "50": "운송·물류", "51": "운송·물류", "52": "운송·물류",
    "55": "호텔·레저", "56": "식음료",
    "58": "IT·소프트웨어", "59": "미디어·엔터", "60": "미디어·엔터",
    "61": "통신", "62": "IT·소프트웨어", "63": "IT·소프트웨어",
    "64": "금융", "65": "보험", "66": "금융",
    "68": "부동산·기타서비스", "70": "부동산·기타서비스", "71": "부동산·기타서비스",
    "72": "건설·건자재", "73": "부동산·기타서비스", "85": "부동산·기타서비스",
    "86": "바이오·제약", "90": "미디어·엔터", "91": "호텔·레저",
}

# ── 예외 override: KSIC가 본업을 잘못 잡는 종목만 수동 교정 ──
PRIMARY_OVERRIDE = {
    "005930": "반도체",       # 삼성전자 (KSIC 264 통신·방송장비)
    "042700": "반도체",       # 한미반도체 (KSIC 기계)
    "240810": "반도체",       # 원익IPS (반도체장비)
    "058470": "반도체",       # 리노공업 (반도체 테스트)
    "357780": "반도체",       # 솔브레인 (반도체 소재)
    "036830": "반도체",       # 솔브레인홀딩스
    "102780": "반도체",       # 원익홀딩스
    "028260": "건설·건자재",  # 삼성물산 (상사로 등록)
    "161390": "자동차",       # 한국타이어 (고무)
    "079550": "항공·방산",    # LIG (금속가공 등록)
    # 지주회사(64992 등) → 실제 사업/순수지주
    "034730": "지주", "003550": "지주", "000150": "지주",
    "004990": "지주", "267250": "지주", "010060": "화학",
    "086520": "2차전지",      # 에코프로(지주)
    "009540": "조선",         # HD한국조선해양(지주)
    "034020": "에너지·전력",  # 두산에너빌리티 (발전·원전 설비)
    # 바이오 지주/연구 등록 교정
    "196170": "바이오·제약", "326030": "바이오·제약",
}

# ── 핫테마 태그: 대표 외에 추가로 다는 카테고리(종목당 여러 개) ──
THEME_TAGS = {
    # 인공지능(AI)
    "005930": ["인공지능(AI)"], "000660": ["인공지능(AI)"],
    "035420": ["인공지능(AI)"], "035720": ["인공지능(AI)"],
    "018260": ["인공지능(AI)"], "042700": ["인공지능(AI)"],
    # 로봇 (순수 로봇주만)
    "454910": ["로봇", "인공지능(AI)"], "277810": ["로봇", "인공지능(AI)"],
    # 자율주행·전기차
    "005380": ["자율주행·전기차"], "000270": ["자율주행·전기차"],
    "012330": ["자율주행·전기차"],
    # 원전·전력
    "034020": ["원전·전력", "수소·신재생"], "015760": ["원전·전력"],
    "267260": ["원전·전력"],
    # 우주·방산
    "012450": ["우주·방산"], "047810": ["우주·방산"], "079550": ["우주·방산"],
    "064350": ["우주·방산"],
    # 바이오·신약
    "207940": ["바이오·신약"], "068270": ["바이오·신약"], "196170": ["바이오·신약"],
    # K-콘텐츠·엔터
    "352820": ["K-콘텐츠·엔터"], "035900": ["K-콘텐츠·엔터"],
}


def _digits(code):
    return "".join(ch for ch in str(code) if ch.isdigit())


def primary_category(induty_code, ticker="", fallback="기타"):
    """대표 카테고리: override 우선 → KSIC 자동 → fallback(SECTOR_MAP)."""
    if ticker in PRIMARY_OVERRIDE:
        return PRIMARY_OVERRIDE[ticker]
    d = _digits(induty_code)
    if d == "64992":   # 지주회사 → 수동분류 우선, 없으면 지주
        return fallback if fallback and fallback != "기타" else "지주"
    if len(d) >= 4 and d[:4] in KSIC4:
        return KSIC4[d[:4]]
    if len(d) >= 3 and d[:3] in KSIC3:
        return KSIC3[d[:3]]
    if len(d) >= 2 and d[:2] in KSIC2:
        return KSIC2[d[:2]]
    return fallback


def categories_for(ticker, primary):
    """대표 + 핫테마 태그를 합친 카테고리 목록(중복 제거, 대표가 맨 앞)."""
    cats = [primary]
    for t in THEME_TAGS.get(ticker, []):
        if t and t not in cats:
            cats.append(t)
    return cats


# 하위호환: 기존 호출부가 ksic_name을 쓰면 대표 카테고리를 반환
def ksic_name(code, fallback="기타"):
    return primary_category(code, "", fallback)


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


def collect_pykrx_bulk(date):
    """pykrx 벌크 API로 전체 시장 데이터를 수집합니다."""
    from pykrx import stock as krx

    results = {}

    for market_code, market_label in [("KOSPI", "코스피"), ("KOSDAQ", "코스닥")]:
        try:
            print(f"    [{market_label}] 시가총액 조회...")
            cap = krx.get_market_cap_by_ticker(date, market=market_code)
            print(f"    [{market_label}] cap: {len(cap)}행, 컬럼: {list(cap.columns)}")

            print(f"    [{market_label}] 기본지표 조회...")
            fund = krx.get_market_fundamental_by_ticker(date, market=market_code)
            print(f"    [{market_label}] fund: {len(fund)}행, 컬럼: {list(fund.columns)}")

            print(f"    [{market_label}] OHLCV 조회...")
            ohlcv = krx.get_market_ohlcv_by_ticker(date, market=market_code)
            print(f"    [{market_label}] ohlcv: {len(ohlcv)}행, 컬럼: {list(ohlcv.columns)}")

            if cap.empty:
                print(f"    [{market_label}] 경고: 시가총액 데이터 없음")
                continue

            # 컬럼명 자동 감지
            mcap_col  = next((c for c in cap.columns  if "시가총액" in c), "시가총액")
            shares_col = next((c for c in cap.columns if "상장주식수" in c), "상장주식수")
            close_col  = next((c for c in ohlcv.columns if "종가" in c), "종가")
            chg_col    = next((c for c in ohlcv.columns if "등락률" in c), "등락률")
            vol_col    = next((c for c in ohlcv.columns if "거래량" in c), "거래량")
            tvol_col   = next((c for c in ohlcv.columns if "거래대금" in c), "거래대금")

            for ticker in cap.index:
                name = krx.get_market_ticker_name(ticker)
                if not name:
                    continue

                cap_row   = cap.loc[ticker]   if ticker in cap.index   else {}
                fund_row  = fund.loc[ticker]  if ticker in fund.index  else {}
                ohlcv_row = ohlcv.loc[ticker] if ticker in ohlcv.index else {}

                mcap_won = int(cap_row.get(mcap_col, 0) if hasattr(cap_row, "get") else 0)

                results[ticker] = {
                    "ticker":  ticker,
                    "name":    name,
                    "market":  market_label,
                    "sector":  SECTOR_MAP.get(ticker, "기타"),
                    "price":   int(ohlcv_row.get(close_col, 0) if hasattr(ohlcv_row, "get") else 0),
                    "change":  round(float(ohlcv_row.get(chg_col, 0) if hasattr(ohlcv_row, "get") else 0), 2),
                    "volume":       int(ohlcv_row.get(vol_col, 0)  if hasattr(ohlcv_row, "get") else 0),
                    "trading_value":int(ohlcv_row.get(tvol_col, 0) if hasattr(ohlcv_row, "get") else 0),
                    "mcap":  round(mcap_won / 1e12, 1),
                    "shares":int(cap_row.get(shares_col, 0) if hasattr(cap_row, "get") else 0),
                    "per": round(float(fund_row.get("PER", 0) if hasattr(fund_row, "get") else 0), 1),
                    "pbr": round(float(fund_row.get("PBR", 0) if hasattr(fund_row, "get") else 0), 1),
                    "eps": int(fund_row.get("EPS", 0) if hasattr(fund_row, "get") else 0),
                    "bps": int(fund_row.get("BPS", 0) if hasattr(fund_row, "get") else 0),
                    "div": round(float(fund_row.get("DIV", 0) if hasattr(fund_row, "get") else 0), 1),
                    "roe":  0.0,
                    "rev":  0.0,
                    "opm":  0.0,
                    "debt": 0.0,
                }

            market_count = sum(1 for v in results.values() if v["market"] == market_label)
            print(f"    [{market_label}] {market_count}개 종목 처리 완료")
            time.sleep(0.5)

        except Exception as e:
            print(f"    [{market_label}] 오류: {e}")
            traceback.print_exc()

    return results


def safe_int(val, default=0):
    """문자열/숫자를 안전하게 int로 변환합니다."""
    try:
        return int(float(str(val).replace(",", "").strip()))
    except Exception:
        return default


def safe_float(val, default=0.0):
    """문자열/숫자를 안전하게 float로 변환합니다."""
    try:
        return float(str(val).replace(",", "").strip())
    except Exception:
        return default


def find_col(columns, *keywords):
    """컬럼 목록에서 키워드를 포함하는 첫 번째 컬럼을 반환합니다."""
    for kw in keywords:
        for c in columns:
            if kw in str(c):
                return c
    return None


def build_universe(date):
    """수집 대상 티커 목록 {ticker: sector_default} 을 만듭니다.

    기본: SECTOR_MAP(수기 목록).
    FULL_UNIVERSE=1: 전 상장사. pykrx 전종목 티커목록을 우선 시도하고,
    실패(Actions에서 차단)하면 DART corp_codes로, 그것도 안 되면 SECTOR_MAP으로
    단계적으로 폴백합니다. SECTOR_MAP 값이 있으면 그 업종을 유지합니다.
    """
    if not FULL_UNIVERSE:
        return dict(SECTOR_MAP)

    dbg = {"FULL_UNIVERSE": FULL_UNIVERSE, "UNIVERSE_LIMIT": UNIVERSE_LIMIT}
    universe = {}

    # 1) pykrx 전종목 티커 목록 (pykrx 1.2.8은 KRX 로그인 필요 → Actions에선 보통 실패)
    try:
        from pykrx import stock as krx
        for mkt in ("KOSPI", "KOSDAQ"):
            try:
                lst = list(krx.get_market_ticker_list(date, market=mkt) or [])
                for tk in lst:
                    universe[str(tk)] = SECTOR_MAP.get(str(tk), "기타")
                dbg[f"pykrx_{mkt}"] = len(lst)
                print(f"  [universe] pykrx {mkt}: {len(lst)}개")
            except Exception as e:
                dbg[f"pykrx_{mkt}_err"] = f"{type(e).__name__}: {e}"
                print(f"  [universe] pykrx {mkt} 실패: {type(e).__name__}: {e}")
    except Exception as e:
        dbg["pykrx_load_err"] = str(e)

    # 2) DART corp_codes(전 상장사=stock_code 6자리) — Actions에서 DART 키가 작동하므로 주 경로
    if len(universe) < 200 and DART_API_KEY:
        try:
            import OpenDartReader
            dart = OpenDartReader(DART_API_KEY)
            cc = getattr(dart, "corp_codes", None)
            if cc is None and hasattr(dart, "corp_code"):
                cc = dart.corp_code  # 일부 버전 호환
            dbg["dart_cc_type"] = type(cc).__name__
            if cc is not None:
                dbg["dart_cc_cols"] = [str(c) for c in getattr(cc, "columns", [])]
                dbg["dart_cc_rows"] = int(len(cc))
                col = next((c for c in cc.columns if "stock" in str(c).lower()), None)
                dbg["dart_stock_col"] = str(col)
                n = 0
                if col is not None:
                    for sc in cc[col].dropna().astype(str):
                        sc = sc.strip()
                        if len(sc) == 6 and sc.isdigit():
                            universe.setdefault(sc, SECTOR_MAP.get(sc, "기타"))
                            n += 1
                dbg["dart_listed"] = n
                print(f"  [universe] DART corp_codes 상장사: {n}개 (누적 {len(universe)})")
        except Exception as e:
            import traceback as _tb
            dbg["dart_cc_err"] = f"{type(e).__name__}: {e}"
            print(f"  [universe] DART corp_codes 실패: {type(e).__name__}: {e}")
            _tb.print_exc()

    # 3) 둘 다 실패하면 SECTOR_MAP
    if len(universe) < 50:
        print("  [universe] 전종목 목록 확보 실패 — SECTOR_MAP으로 폴백")
        universe = dict(SECTOR_MAP)
        dbg["fallback"] = "SECTOR_MAP"
    else:
        for tk, sec in SECTOR_MAP.items():
            universe.setdefault(tk, sec)

    if UNIVERSE_LIMIT and len(universe) > UNIVERSE_LIMIT:
        universe = dict(list(universe.items())[:UNIVERSE_LIMIT])
    dbg["universe_final"] = len(universe)
    print(f"  [universe] 최종 수집 대상: {len(universe)}개")
    try:
        Path("data").mkdir(exist_ok=True)
        Path("data/universe_debug.json").write_text(
            json.dumps(dbg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return universe


def collect_pykrx_fallback(date, universe=None):
    """개별 종목 OHLCV 수집(universe 목록 대상)."""
    from pykrx import stock as krx

    if universe is None:
        universe = dict(SECTOR_MAP)
    print(f"  [폴백] 개별 종목 OHLCV 수집 중... (대상 {len(universe)}개)")
    results = {}
    debug_info = {}

    for ticker, sector in universe.items():
        try:
            df_ohlcv = krx.get_market_ohlcv_by_date(date, date, ticker)
            if df_ohlcv is None or df_ohlcv.empty:
                continue

            row = df_ohlcv.iloc[0]
            name = krx.get_market_ticker_name(ticker)
            if not name:
                continue

            # 첫 종목의 컬럼 구조 디버그 저장
            if not debug_info:
                debug_info["ohlcv_cols"] = [str(c) for c in df_ohlcv.columns]
                debug_info["ohlcv_sample"] = {str(k): str(v) for k, v in row.items()}

            # 컬럼 감지 (이름 기반 우선, 위치 기반 폴백)
            cols = list(df_ohlcv.columns)
            close_col = find_col(cols, "종가")
            chg_col   = find_col(cols, "등락률", "등락")
            vol_col   = find_col(cols, "거래량")

            price  = safe_int(row[close_col]) if close_col else 0
            change = safe_float(row[chg_col]) if chg_col else 0.0
            volume = safe_int(row[vol_col])   if vol_col  else 0

            # 위치 기반 폴백 (실측 컬럼: 시가0 고가1 저가2 종가3 거래량4 등락률5)
            if price == 0 and len(cols) > 3:
                price = safe_int(row.iloc[3])
            if volume == 0 and len(cols) > 4:
                volume = safe_int(row.iloc[4])
            if change == 0.0 and len(cols) > 5:
                change = safe_float(row.iloc[5])

            # 거래대금 근사: ohlcv에 거래대금 컬럼이 없으므로 가격 × 거래량으로 추정
            tvol = price * volume if (price > 0 and volume > 0) else 0

            # 시총·주식수·영문명은 enrich_with_dart()에서 DART로 채움
            results[ticker] = {
                "ticker":  ticker,
                "name":    name,
                "name_en": "",   # 영문 종목명 (enrich_with_dart에서 DART로 채움)
                "market":  "코스피",
                "sector":  sector,
                "price":   price,
                "change":  round(change, 2),
                "volume":       volume,
                "trading_value":tvol,
                "mcap":  0.0,
                "shares":0,
            }
            time.sleep(0.05)

        except Exception as e:
            print(f"    [{ticker}] 오류: {e}")

    print(f"  [폴백] {len(results)}개 종목 수집 완료")

    # 디버그 정보 파일로 저장 (GitHub API로 확인 가능)
    try:
        Path("data").mkdir(exist_ok=True)
        Path("data/debug.json").write_text(
            json.dumps(debug_info, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [디버그] data/debug.json 저장 완료")
    except Exception:
        pass

    return results


def collect_pykrx(date):
    """pykrx로 시세 데이터를 수집합니다.

    KRX 전종목 벌크 API(get_market_*_by_ticker)와 시총/펀더멘털 API는
    GitHub Actions 환경에서 차단되어 빈 값을 반환하므로, 작동이 확인된
    개별 종목 OHLCV 조회(get_market_ohlcv_by_date)만 사용합니다.
    시총·PER·PBR 등은 enrich_with_dart()에서 DART로 채웁니다.
    """
    print(f"  [pykrx] {date} OHLCV 데이터 수집 중...")
    universe = build_universe(date)
    results = collect_pykrx_fallback(date, universe)

    valid = [v for v in results.values() if v["price"] > 0]
    print(f"  [pykrx] 수집 결과: {len(results)}개 (가격 유효: {len(valid)}개)")
    return results


CORP_CLS_MARKET = {"Y": "코스피", "K": "코스닥", "N": "코넥스", "E": "기타"}


def get_dart_shares(dart, corp_code, debug_info, dump=False):
    """DART 주식총수 현황 API로 발행주식수와 시장구분을 가져옵니다.

    반환: (common:int, total:int, market:str|None)
      common = 보통주 발행주식총수 (시가총액 계산용)
      total  = 보통주 + 우선주 발행주식총수 (주당지표 분모용, 네이버 방식)
    """
    import requests

    def istc(r):
        for col in ("istc_totqy", "isu_stock_totqy", "now_to_isu_stock_totqy", "distb_stock_co"):
            v = safe_int(r.get(col, 0))
            if v > 0:
                return v
        return 0

    # 사업보고서(11011) → 3분기(11014) → 반기(11012) → 1분기(11013) 순으로 시도
    for year in (datetime.date.today().year - 1, datetime.date.today().year - 2):
        for reprt in ("11011", "11014", "11012", "11013"):
            try:
                url = "https://opendart.fss.or.kr/api/stockTotqySttus.json"
                params = {
                    "crtfc_key": DART_API_KEY,
                    "corp_code": corp_code,
                    "bsns_year": str(year),
                    "reprt_code": reprt,
                }
                jo = requests.get(url, params=params, timeout=20).json()

                if dump:
                    debug_info.setdefault("share_attempts", []).append(
                        {"year": year, "reprt": reprt, "status": jo.get("status"),
                         "msg": jo.get("message"),
                         "ses": [str(r.get("se", "")) for r in jo.get("list", [])]})

                if jo.get("status") != "000" or "list" not in jo:
                    continue

                rows = jo["list"]
                market = CORP_CLS_MARKET.get(str(rows[0].get("corp_cls", "")).upper()) if rows else None

                if dump:
                    debug_info["share_dump"] = [
                        {"se": str(r.get("se", "")), "istc": str(r.get("istc_totqy", "")),
                         "isu": str(r.get("isu_stock_totqy", ""))} for r in rows]

                # se 표기: '보통주'/'우선주' 또는 '의결권이 있는 주식'/'의결권이 없는 주식'
                common = 0
                total = 0
                total_row = 0
                for r in rows:
                    se = str(r.get("se", ""))
                    v = istc(r)
                    if "합계" in se:
                        total_row = max(total_row, v)
                    elif "보통" in se or "의결권이 있는" in se:
                        common = v
                        total += v
                    elif "우선" in se or "의결권이 없는" in se:
                        total += v

                # 보통주 행을 못 찾으면 합계 행으로 폴백
                if common == 0:
                    common = total_row
                if total < common:
                    total = total_row or common

                if common > 0:
                    return common, (total if total >= common else common), market
            except Exception as e:
                if "share_error" not in debug_info:
                    debug_info["share_error"] = f"{type(e).__name__}: {e}"
    return 0, 0, None


def detect_latest_quarter(dart):
    """현재 연도에서 가장 최근 제출된 분기보고서를 1회 탐지합니다.

    반환: (year, reprt_code). 분기보고서가 아직 없으면 (전년, 사업보고서).
    """
    cur = datetime.date.today().year
    for reprt in ("11014", "11012", "11013"):   # 3분기 → 반기 → 1분기
        try:
            q = dart.finstate("005930", cur, reprt)
            if q is not None and not q.empty:
                return cur, reprt
        except Exception:
            pass
    return cur - 1, "11011"


def get_dart_controlling_equity(dart, ticker, q_year, q_reprt, debug_info, dump=False):
    """DART 전체재무제표(연결)에서 최근 분기 지배주주지분(원)을 가져옵니다.

    네이버 PBR은 최근 분기 지배주주지분 기준이므로 연간이 아닌 최근 분기를 씁니다.
    (속도 최적화: 탐지된 최근 분기 1개만 조회, 실패 시 전년 사업보고서로 폴백)
    """
    cur = datetime.date.today().year

    def extract(yr, reprt):
        try:
            fa = dart.finstate_all(ticker, yr, reprt, fs_div="CFS")
            if fa is None or fa.empty:
                return 0
            controlling = 0   # 지배기업 소유주지분 (직접 행)
            equity_total = 0  # 자본총계 (정확히 일치)
            noncontrol = 0    # 비지배지분
            for _, r in fa.iterrows():
                nm = str(r.get("account_nm", "")).strip()
                sj = str(r.get("sj_div", ""))
                if sj != "BS":
                    continue
                v = safe_int(r.get("thstrm_amount", 0))
                nm_compact = nm.replace(" ", "")
                if "지배" in nm and "소유" in nm:           # 지배기업 소유주지분
                    controlling = max(controlling, v)
                elif "비지배" in nm:                         # 비지배지분
                    noncontrol = max(noncontrol, v)
                elif nm_compact == "자본총계":               # 자본총계(정확히) — 부채와자본총계 제외
                    equity_total = max(equity_total, v)
            # 우선순위: 지배지분 직접 행 > (자본총계 - 비지배지분) > 자본총계
            if controlling > 0:
                result = controlling
            elif equity_total > 0:
                result = equity_total - noncontrol
            else:
                result = 0
            if dump:
                debug_info.setdefault("equity_calc", []).append(
                    {"yr": yr, "reprt": reprt, "controlling": controlling,
                     "equity_total": equity_total, "noncontrol": noncontrol, "result": result})
            return result
        except Exception as e:
            if "equity_error" not in debug_info:
                debug_info["equity_error"] = f"{type(e).__name__}: {e}"
            return 0

    # 탐지된 최근 분기 1개만 조회, 실패 시 전년 사업보고서로 폴백
    for yr, reprt in [(q_year, q_reprt), (cur - 1, "11011")]:
        eq = extract(yr, reprt)
        if eq > 0:
            if dump:
                debug_info["equity_pick"] = {"yr": yr, "reprt": reprt, "equity": eq}
            return eq
    return 0


def get_dart_pershare(dart, corp_code, debug_info, dump=False):
    """DART 배당 리포트(alotMatter)에서 공식 주당지표를 가져옵니다.

    반환: {"eps": (연결)주당순이익(원), "dps": 주당현금배당금(원, 보통주)}
    네이버·FnGuide가 표시하는 것과 동일한 공식 수치입니다.
    """
    import requests

    for year in (datetime.date.today().year - 1, datetime.date.today().year - 2):
        try:
            url = "https://opendart.fss.or.kr/api/alotMatter.json"
            params = {
                "crtfc_key": DART_API_KEY,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": "11011",
            }
            jo = requests.get(url, params=params, timeout=20).json()
            if jo.get("status") != "000" or "list" not in jo:
                continue

            if "div_cols" not in debug_info and jo["list"]:
                debug_info["div_cols"] = list(jo["list"][0].keys())
            if dump:
                debug_info["samsung_div"] = [
                    {"se": str(r.get("se", "")), "knd": str(r.get("stock_knd", "")),
                     "thstrm": str(r.get("thstrm", ""))}
                    for r in jo["list"]
                ]

            eps = dps = 0
            for r in jo["list"]:
                se  = str(r.get("se", ""))
                knd = str(r.get("stock_knd", ""))
                is_common = knd in ("-", "") or "보통" in knd
                # (연결)주당순이익 → 공식 EPS (적자는 음수)
                if "주당순이익" in se and eps == 0:
                    v = safe_int(r.get("thstrm", 0))
                    if v != 0:
                        eps = v
                # 주당 현금배당금 (보통주)
                if "주당" in se and "현금배당금" in se and is_common and dps == 0:
                    v = safe_int(r.get("thstrm", 0))
                    if v > 0:
                        dps = v
            if eps != 0 or dps > 0:
                return {"eps": eps, "dps": dps}
        except Exception as e:
            if "div_error" not in debug_info:
                debug_info["div_error"] = f"{type(e).__name__}: {e}"
    return {"eps": 0, "dps": 0}


def get_ttm_ratio(dart, ticker, total_annual_ni, q_year, q_reprt, debug_info, dump=False):
    """TTM(최근 4분기) 순이익 / 연간 순이익 비율을 구합니다.

    네이버 EPS는 최근 4분기 합산(TTM) 기준이므로,
    EPS(TTM) = 연간공식EPS × (TTM순이익/연간순이익) 로 환산합니다.
    (속도 최적화: 탐지된 최근 분기 1개만 조회)
    """
    if total_annual_ni <= 0:
        return 1.0
    if q_reprt == "11011":   # 분기보고서 없음 → 연간 그대로
        return 1.0

    def q_ni(yr):
        try:
            q = dart.finstate(ticker, yr, q_reprt)
            if q is None or q.empty:
                return None
            r = q[q["account_nm"].str.contains("당기순이익", na=False)]
            if r.empty:
                return None
            return int(str(r.iloc[0].get("thstrm_amount", "0")).replace(",", "") or 0)
        except Exception:
            return None

    cq = q_ni(q_year)
    pq = q_ni(q_year - 1)
    if cq is not None and pq is not None:
        ttm = total_annual_ni + cq - pq
        ratio = ttm / total_annual_ni
        if dump:
            debug_info.setdefault("ttm", {})[ticker] = {
                "reprt": q_reprt, "cur_q": cq, "prev_q": pq,
                "annual": total_annual_ni, "ttm": ttm, "ratio": round(ratio, 3)}
        # 음수(TTM 적자) 허용. 극단값만 방어 (분기 데이터 오류 대비)
        if ratio != 0 and abs(ratio) < 200:
            return ratio
    return 1.0


def enrich_with_dart(results):
    """DART API로 영문 종목명·상장주식수(시가총액)·시장구분만 보완합니다.

    PER/PBR/배당/ROE 등 계산형 지표는 사이트에서 제공하지 않습니다
    (사이트별 산정방식 차이로 외부값과 불일치가 잦아 제거). 핵심 시세만 유지.
    """
    if not DART_API_KEY:
        print("  [DART] API 키 없음, 보강 생략")
        return results

    try:
        import OpenDartReader
        dart = OpenDartReader(DART_API_KEY)
    except Exception as e:
        print(f"  [DART] 초기화 실패: {e}")
        return results

    debug_info = {}
    ranked = sorted(results.values(), key=lambda x: x["trading_value"], reverse=True)
    # 전 종목 모드면 모두 보강(시총 채워야 가드 통과 + 순위 산정). 아니면 상위 130개.
    targets = ranked if FULL_UNIVERSE else ranked[:130]
    print(f"  [DART] {len(targets)}개 종목 영문명·주식수(시총) 수집 중...")

    for i, stock in enumerate(targets):
        ticker = stock["ticker"]
        price = stock["price"]
        try:
            corp_code = dart.find_corp_code(ticker)
            if not corp_code:
                continue

            # 영문 종목명(영어 모드 표시용) + 업종코드(induty_code, 한국표준산업분류)
            try:
                info = dart.company(corp_code)
                if info is not None and hasattr(info, "get"):
                    name_en = info.get("corp_name_eng") or ""
                    if name_en:
                        results[ticker]["name_en"] = name_en.strip()
                    induty = (info.get("induty_code") or "").strip()
                    if induty:
                        results[ticker]["induty_code"] = induty
            except Exception:
                pass

            # 상장주식수·시장구분 → 시가총액(가격 × 보통주 발행주식수)
            common_sh, total_sh, market = get_dart_shares(dart, corp_code, debug_info)
            if market:
                results[ticker]["market"] = market
            if common_sh > 0:
                results[ticker]["shares"] = common_sh
                results[ticker]["mcap"]   = round(price * common_sh / 1e12, 2)

            if i % 20 == 0:
                print(f"    {i+1}/{len(targets)} 완료...")
            time.sleep(0.15)

        except Exception as e:
            if "enrich_error" not in debug_info:
                debug_info["enrich_error"] = f"{ticker}: {type(e).__name__}: {e}"

    try:
        dbg_path = Path("data/debug.json")
        existing = {}
        if dbg_path.exists():
            existing = json.loads(dbg_path.read_text(encoding="utf-8"))
        existing["dart"] = debug_info
        dbg_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # ── 전 종목 대표 카테고리 + 다중 태그 부여 ──
    for tk, st in results.items():
        prev = st.get("sector", "기타")          # 수동 SECTOR_MAP 값(폴백)
        primary = primary_category(st.get("induty_code", ""), tk, prev)
        st["sector"] = primary                   # 프론트 호환: 대표 카테고리
        st["categories"] = categories_for(tk, primary)

    print("  [DART] 영문명·시총·카테고리 보강 완료")
    return results



def load_existing_stocks():
    """기존 data/stocks.js 를 {ticker: record} 로 읽습니다(병합용)."""
    p = Path("data/stocks.js")
    if not p.exists():
        return {}
    try:
        raw = p.read_text(encoding="utf-8")
        obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        return {s["ticker"]: s for s in obj.get("stocks", [])}
    except Exception as e:
        print(f"  [merge] 기존 stocks.js 로드 실패: {e}")
        return {}


def build_output(results, date):
    """웹사이트용 JS 파일을 생성합니다. (시총>0 종목 전부 보존 — 페이지네이션)"""
    valid = [s for s in results.values() if s["price"] > 0]
    with_mcap = [s for s in valid if (s.get("mcap") or 0) > 0]

    # 시총 있는 종목이 충분하면 시총순 전체 보존(0조 종목은 출력 제외).
    if with_mcap and len(with_mcap) >= 0.4 * len(valid):
        stocks = sorted(with_mcap, key=lambda x: x["mcap"], reverse=True)
    else:
        # 시총 대량 실패 시 거래대금 기준(기존 동작) — 상위 100개만.
        print("  [경고] 시가총액 정보 부족 — 거래대금 기준 상위 100개")
        stocks = sorted(valid, key=lambda x: x["trading_value"], reverse=True)[:100]

    if len(stocks) < 5:
        # 가격 0 포함해서라도 채움
        stocks = sorted(results.values(), key=lambda x: x["mcap"] + x["trading_value"], reverse=True)[:100]

    for i, s in enumerate(stocks):
        s["rank"] = i + 1

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

    log_summary(f"✅ data/stocks.js 생성 완료 — {len(stocks)}개 종목 ({last_updated} KST)")
    return len(stocks)


def main():
    print("=" * 55)
    print("  KOS ai 데이터 수집 시작")
    print("=" * 55)

    date = get_latest_trading_date()
    print(f"  기준일: {date}\n")
    log_summary(f"## KOS ai 데이터 수집 — {date}")

    results = collect_pykrx(date)
    log_summary(f"- pykrx 수집: {len(results)}개 종목")

    results = enrich_with_dart(results)

    # 수집 실패 가드: 이번에 새로 수집한 종목이 너무 적으면 갱신 건너뜀(기존 데이터 보존)
    if len(results) < 50:
        log_summary(f"❌ 수집 종목 {len(results)}개로 비정상(50 미만) — stocks.js 갱신 건너뜀, 기존 데이터 유지")
        sys.exit(1)

    # 시총 가드: 이번 수집분의 시총>0 비율이 절반 미만이면 DART 실패로 보고 건너뜀
    mcap_ok = sum(1 for s in results.values() if (s.get("mcap") or 0) > 0)
    if mcap_ok < len(results) * 0.5:
        log_summary(f"❌ 시가총액>0 종목 {mcap_ok}/{len(results)}개로 비정상(DART 수집 실패 추정) — stocks.js 갱신 건너뜀, 기존 데이터 유지")
        sys.exit(1)

    # 기존 universe와 병합: 새로 수집한 종목은 갱신하고, 이번에 안 건드린 종목은 보존.
    # (SECTOR_MAP만 도는 일일 실행이 전체 universe를 100개로 줄이지 않도록)
    existing = load_existing_stocks()
    before = len(existing)
    existing.update(results)
    log_summary(f"- 병합: 기존 {before}개 + 신규수집 {len(results)}개 → {len(existing)}개")
    results = existing

    count = build_output(results, date)
    log_summary(f"- 최종 출력: {count}개 종목")

    print("=" * 55)

    if count == 0:
        print("[오류] 수집된 종목이 없습니다.")


if __name__ == "__main__":
    try:
        # 이전 에러 로그 제거
        Path("data").mkdir(exist_ok=True)
        err_path = Path("data/error.log")
        if err_path.exists():
            err_path.unlink()
        main()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        try:
            Path("data").mkdir(exist_ok=True)
            Path("data/error.log").write_text(tb, encoding="utf-8")
        except Exception:
            pass
        # exit 0으로 종료해 커밋 단계가 실행되도록 함 (error.log 확인용)
