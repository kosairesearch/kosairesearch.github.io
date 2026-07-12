"""실시간 지표 — kosai.kr가 매일 갱신하는 공개 데이터에서 채운다.

가격·시총·상장주식수 = stocks.js, eps·bps·dps·roe·매출성장 = valuation.js.
PER=가격/eps, PBR=가격/bps, 배당수익률=dps/가격 을 코드로 계산(숫자는 모델이 안 쓴다).
env: DATA_BASE(기본 https://kosai.kr/data)
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


def get_metrics(ticker):
    """종목 지표 dict. 데이터 없으면 None."""
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
