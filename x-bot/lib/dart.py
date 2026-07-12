"""DART OpenAPI — 최근 공시 목록(시점 앵커링 + 사건성 근거).

DART list.json은 8자리 corp_code가 필요하다. 6자리 종목코드→corp_code 매핑은
scripts/build_corpmap.py가 corpCode.xml로 미리 만들어 data/corpmap.json에 둔다.
맵이 없거나 키가 없으면 조용히 []를 반환(웹서치가 사건을 커버하므로 치명적 아님).
env: DART_API_KEY
"""
import json
import os
from datetime import datetime, timedelta, timezone

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORPMAP_PATH = os.path.join(_HERE, "..", "data", "corpmap.json")
_KEY = os.environ.get("DART_API_KEY", "")
_MAP = None


def _corpmap():
    global _MAP
    if _MAP is None:
        try:
            with open(_CORPMAP_PATH, encoding="utf-8") as f:
                _MAP = json.load(f)
        except Exception:
            _MAP = {}
    return _MAP


def recent_disclosures(ticker, months=6, limit=8):
    """최근 공시 [{title, date}] 목록. 실패 시 []."""
    if not _KEY:
        return []
    corp = _corpmap().get(ticker)
    if not corp:
        return []
    kst = timezone(timedelta(hours=9))
    end = datetime.now(kst)
    bgn = end - timedelta(days=months * 31)
    try:
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={
                "crtfc_key": _KEY, "corp_code": corp,
                "bgn_de": bgn.strftime("%Y%m%d"), "end_de": end.strftime("%Y%m%d"),
                "page_count": 100,
            }, timeout=12).json()
    except Exception:
        return []
    if r.get("status") != "013" and r.get("status") != "000":
        # 013=데이터없음
        pass
    out = []
    for it in (r.get("list") or [])[:limit]:
        nm = it.get("report_nm", "").strip()
        dt = it.get("rcept_dt", "")
        if nm and dt:
            out.append({"title": nm, "date": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"})
    return out
