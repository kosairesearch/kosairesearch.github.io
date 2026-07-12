"""실시간 지표 — 기본은 kosai.kr 일일 데이터, USE_PYKRX=1이면 pykrx 우선.

kosai 경로: 가격·시총·상장주식수 = stocks.js, eps·bps·dps·roe·매출성장 = valuation.js.
PER=가격/eps, PBR=가격/bps, 배당수익률=dps/가격 을 코드로 계산(숫자는 모델이 안 쓴다).
pykrx 경로: KRX에서 직접 조회(최근 영업일 종가·시총·PER·PBR·배당). pandas 번들이
커서 Vercel 배포가 무거워지므로 옵션(requirements.txt에 pykrx 추가 + USE_PYKRX=1).
pykrx 실패 시 자동으로 kosai 경로 폴백 — 어느 쪽이든 KRX 공식 일일 수치다.
env: DATA_BASE(기본 https://kosai.kr/data), USE_PYKRX(기본 0)
"""
import json
import os
import re
import time

import requests

DATA_BASE = os.environ.get("DATA_BASE", "https://kosai.kr/data").rstrip("/")
FX_URL = os.environ.get("FX_URL", "https://open.er-api.com/v6/latest/USD")

_MEMO = {"t": 0, "stocks": None, "val": None}   # 프로세스 내 1분 메모


def _parse_js(text):
    return json.loads(re.search(r"=\s*(\{.*)", text, re.S).group(1).strip().rstrip(";"))


def _load():
    """stocks.js + valuation.js 로드(프로세스 내 60초 메모)."""
    now = time.time()
    if _MEMO["stocks"] and now - _MEMO["t"] < 60:
        return _MEMO["stocks"], _MEMO["val"]
    s = _parse_js(requests.get(f"{DATA_BASE}/stocks.js", timeout=15).text)
    v = _parse_js(requests.get(f"{DATA_BASE}/valuation.js", timeout=15).text)
    stocks = {x["ticker"]: x for x in s.get("stocks", [])}
    val = v.get("stocks", {})
    _MEMO.update(t=now, stocks=stocks, val=val, sdate=s.get("dataDate"))
    return stocks, val


def _metrics_pykrx(ticker):
    """pykrx로 최근 영업일 지표 조회. 미설치/실패 시 None."""
    try:
        from pykrx import stock as krx
        day = krx.get_nearest_business_day_in_a_week()
        cap = krx.get_market_cap_by_date(day, day, ticker)
        if not len(cap):
            return None
        out = {"ticker": ticker,
               "price": int(cap["종가"].iloc[-1]),
               "mcap_trillion": round(int(cap["시가총액"].iloc[-1]) / 1e12, 4),
               "data_date": f"{day[:4]}-{day[4:6]}-{day[6:]}"}
        f = krx.get_market_fundamental(day, day, ticker)
        if len(f):
            row = f.iloc[-1]
            if float(row["PER"]):
                out["per"] = round(float(row["PER"]), 1)
            if float(row["PBR"]):
                out["pbr"] = round(float(row["PBR"]), 2)
            if float(row["DIV"]):
                out["div_yield"] = round(float(row["DIV"]), 2)
        return out
    except Exception:
        return None


def get_metrics(ticker):
    """종목 지표 dict. 데이터 없으면 None."""
    if os.environ.get("USE_PYKRX") == "1":
        m = _metrics_pykrx(ticker)
        if m:
            # 이름·섹터 등 부가정보는 kosai 데이터에서 보충
            try:
                stocks, _ = _load()
                s = stocks.get(ticker) or {}
                m.setdefault("name", s.get("name"))
                m.setdefault("name_en", s.get("name_en"))
                m.setdefault("market", s.get("market"))
                m.setdefault("sector", s.get("sector"))
            except Exception:
                pass
            return m
    stocks, val = _load()
    s = stocks.get(ticker)
    if not s:
        return None
    v = val.get(ticker, {}) if isinstance(val, dict) else {}
    price = s.get("price") or 0
    eps = v.get("eps") or 0
    bps = v.get("bps") or 0
    dps = v.get("dps") or 0
    per = round(price / eps, 1) if eps and eps > 0 else None
    pbr = round(price / bps, 2) if bps and bps > 0 else None
    dyield = round(dps / price * 100, 2) if price and dps else None
    return {
        "ticker": ticker,
        "name": s.get("name"),
        "name_en": s.get("name_en"),
        "market": s.get("market"),
        "sector": s.get("sector"),
        "price": price,
        "change": s.get("change"),
        "mcap_trillion": s.get("mcap"),       # 조원
        "shares": s.get("shares"),
        "per": per,
        "pbr": pbr,
        "div_yield": dyield,
        "roe": v.get("roe"),
        "eps": eps,
        "bps": bps,
        "dps": dps,
        "rev_g": v.get("rev_g"),
        "data_date": _MEMO.get("sdate"),
    }


def get_usdkrw(store=None):
    """USD/KRW 환율. store가 있으면 1일 캐시 사용."""
    if store:
        cached = store.get_fx()
        if cached:
            return cached
    try:
        r = requests.get(FX_URL, timeout=10).json()
        rate = float(r["rates"]["KRW"])
    except Exception:
        rate = 1380.0                          # 폴백(대략치)
    if store:
        store.set_fx(rate)
    return rate
