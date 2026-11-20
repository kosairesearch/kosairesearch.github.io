#!/usr/bin/env python3
"""상장 전 · 상장 당일에 게시한 신규 상장 종목의 목록(data/ipo.json) — 표준 라이브러리만(워치독이 pip 없이 부른다).

왜 있나(2026-11-18 사장 "상장 당일에 리포트를 뿌려야 유입이 많이 되는데, 당일에 일찍 리포트를 만들 수 없어?")
  신규 상장 리포트는 상장일 시세가 시세 자료(data/stocks.js)에 들어온 뒤에야 종목을 알아 상장 다음 날 새벽 ~ 아침에 올라갔다.
  이제 한국거래소가 상장 이틀 전 오후에 KIND 에 올리는 '신규상장' 안내로 종목코드를 미리 알아, 상장 전날 아침(늦어도 상장일 아침)에
  리포트를 쓰고 게시한다(scripts/ipo_reports.py · .github/workflows/ipo_reports.yml).

  그 종목은 상장일 장 마감 뒤 시세 갱신 전까지 시세 자료에 없다. 시세 자료에 없는 종목은 원래 상장 폐지 종목처럼 다룬다 — 페이지는
  noindex · 사이트맵 제외(build_stock_static.listed · generate_sitemap), 리포트 색인에서 정리(_reindex · generate_reports.write_reports),
  옛 형식 리포트 파일도 지운다. 이 목록에 있는 종목은 그 정리에서 뺀다 — 상장 전에 게시해야 검색에 오르고, 지우면 쓴 글이 사라진다.

  창: 상장일 WINDOW_BEFORE 일 전부터 WINDOW_AFTER 일 뒤까지. 시세 자료에 오르면 그때부터는 원래 상장 종목이다. 상장이 미뤄지거나
  철회돼 창이 지나도 시세 자료에 없으면 원래대로 정리된다.

  { "updated": "2026-11-19 06:52",
    "stocks": { "0123A0": { "name": "하나에어로", "market": "코스닥", "list_date": "2026-11-20", "offer_price": 5700,
                            "shares": 12345678, "published": "2026-11-19 07:20" } } }
"""
import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IPO_JSON = ROOT / "data" / "ipo.json"
KST = datetime.timezone(datetime.timedelta(hours=9))
WINDOW_BEFORE = 7     # 상장일 며칠 전부터 상장 종목으로 보나 — 안내는 상장 이틀(영업일) 전에 나온다 · 연휴를 넉넉히
WINDOW_AFTER = 14     # 상장일 며칠 뒤까지 — 그 안에 시세 자료에 오른다(평일 저녁 시세 갱신). 못 오르면 원래대로 정리된다


def today_kst():
    return datetime.datetime.now(KST).date()


def load(path=None):
    p = Path(path) if path else IPO_JSON
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001 — 없거나 깨졌으면 빈 목록(정리에서 빼는 종목이 없을 뿐)
        return {"updated": "", "stocks": {}}
    if not isinstance(obj, dict) or not isinstance(obj.get("stocks"), dict):
        return {"updated": "", "stocks": {}}
    return obj


def save(obj, path=None):
    p = Path(path) if path else IPO_JSON
    obj = dict(obj)
    obj["stocks"] = {k: obj["stocks"][k] for k in sorted(obj.get("stocks") or {})}
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def in_window(entry, today=None):
    """상장일이 창 안인가 — 상장일 WINDOW_BEFORE 일 전 ~ WINDOW_AFTER 일 뒤."""
    today = today or today_kst()
    try:
        d = datetime.date.fromisoformat(str((entry or {}).get("list_date", ""))[:10])
    except ValueError:
        return False
    return d - datetime.timedelta(days=WINDOW_BEFORE) <= today <= d + datetime.timedelta(days=WINDOW_AFTER)


def active(today=None, path=None):
    """창 안의 종목코드 — 시세 자료에 아직 없어도 상장 종목으로 다룬다(색인 · 사이트맵 · 리포트 정리)."""
    return {tk for tk, e in (load(path).get("stocks") or {}).items() if in_window(e, today)}


def prune(obj, today=None):
    """창이 지난 줄을 걷는다(목록이 끝없이 늘지 않게). 걷은 수를 돌려준다."""
    today = today or today_kst()
    st = obj.get("stocks") or {}
    old = [tk for tk, e in st.items() if not in_window(e, today) and _past(e, today)]
    for tk in old:
        st.pop(tk, None)
    return len(old)


def _past(entry, today):
    try:
        return datetime.date.fromisoformat(str(entry.get("list_date", ""))[:10]) < today
    except ValueError:
        return True


def stock_dict(tk, e):
    """리포트 생성기(generate_reports_batch)가 쓰는 종목 꼴 — 시세 칸은 비우고 공모 정보(ipo)를 단다."""
    of = e.get("offer") or {}
    ipo = {k: v for k, v in {
        "list_date": e.get("list_date"), "offer_price": of.get("offer_price"), "shares": e.get("shares"),
        "offer_amount_mil": of.get("offer_amount_mil"), "underwriter": of.get("underwriter") or e.get("underwriter"),
        "bookbuild": of.get("bookbuild"), "subscribe": of.get("subscribe"), "division": e.get("division"),
        "industry": e.get("industry"), "products": e.get("products"), "holders": e.get("holders"),
        "full_name": e.get("full_name"), "ceo": e.get("ceo"), "par": e.get("par"),
        "filing": e.get("filing"),       # 증권신고서 요약재무정보 · 공모 자금 사용 계획(scripts/ipo_filing.py)
    }.items() if v not in (None, "", {})}
    return {"ticker": tk, "name": e.get("name") or tk, "name_en": e.get("name_en") or "", "market": e.get("market") or "",
            "sector": e.get("sector") or "기타", "categories": e.get("categories") or [], "price": None, "change": None,
            "mcap": None, "trading_value": None, "volume": None, "shares": e.get("shares"), "ipo": ipo}


def extra_stocks(path=None, today=None):
    """창 안의 종목을 생성기의 종목 꼴로 — {종목코드: 종목}. 시세 자료에 없는 종목을 생성기가 찾을 수 있게."""
    return {tk: stock_dict(tk, e) for tk, e in (load(path).get("stocks") or {}).items() if in_window(e, today)}
