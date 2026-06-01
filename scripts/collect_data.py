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


def collect_pykrx_fallback(date):
    """개별 종목 조회 폴백 — SECTOR_MAP 종목만 수집합니다."""
    from pykrx import stock as krx

    print("  [폴백] 개별 종목 OHLCV 수집 중...")
    results = {}
    debug_info = {}

    for ticker, sector in SECTOR_MAP.items():
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
    results = collect_pykrx_fallback(date)

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
    targets = sorted(results.values(), key=lambda x: x["trading_value"], reverse=True)[:90]
    print(f"  [DART] {len(targets)}개 종목 영문명·주식수(시총) 수집 중...")

    for i, stock in enumerate(targets):
        ticker = stock["ticker"]
        price = stock["price"]
        try:
            corp_code = dart.find_corp_code(ticker)
            if not corp_code:
                continue

            # 영문 종목명 (영어 모드 표시용)
            try:
                info = dart.company(corp_code)
                name_en = (info.get("corp_name_eng") if (info is not None and hasattr(info, "get")) else "") or ""
                if name_en:
                    results[ticker]["name_en"] = name_en.strip()
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

    print("  [DART] 영문명·시총 보강 완료")
    return results



def build_output(results, date):
    """웹사이트용 JS 파일을 생성합니다."""
    valid = [s for s in results.values() if s["price"] > 0]

    # mcap이 모두 0이면 거래대금으로 정렬
    if valid and all(s["mcap"] == 0 for s in valid):
        print("  [경고] 시가총액 0 — 거래대금 기준으로 정렬")
        stocks = sorted(valid, key=lambda x: x["trading_value"], reverse=True)[:100]
    else:
        stocks = sorted(valid, key=lambda x: x["mcap"], reverse=True)[:100]

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
