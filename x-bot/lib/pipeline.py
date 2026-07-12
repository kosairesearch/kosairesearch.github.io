"""핵심 파이프라인 — 멘션 1건 처리, 답글 문자열 생성.

lazy 캐시: 종목_언어별 서술은 첫 요청 때 생성·저장, 이후 재사용. 오래되면 재생성.
지표는 매번 실시간(quotes)로 채운다. 숫자는 모델이 아니라 코드가 채운다.
"""
import os
from datetime import datetime, timezone, timedelta

from lib import tickers, quotes, dart, narrative, compose, store, xclient

STALE_MONTHS = int(os.environ.get("CACHE_STALE_MONTHS", "3"))
MAX_ATTEMPTS = 3


def _stale(built):
    if not built:
        return True
    try:
        d = datetime.strptime(built, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        return True
    return datetime.now(timezone.utc) - d > timedelta(days=STALE_MONTHS * 31)


def get_or_build_narrative(ticker, stock, lang):
    cached = store.get_narrative(ticker, lang)
    if cached and not _stale(cached.get("_built")):
        return cached
    disc = dart.recent_disclosures(ticker)
    nar = narrative.generate(stock, disc, lang)
    if not nar:
        return cached                       # 생성 실패 시 옛 캐시라도(있으면)
    kst = timezone(timedelta(hours=9))
    nar["_built"] = datetime.now(kst).strftime("%Y-%m-%d")
    store.set_narrative(ticker, lang, nar)
    return nar


def build_reply(query_text, lang=None):
    """멘션 텍스트(또는 종목명/코드)로 답글 문자열 생성. (reply, ticker) 또는 (None, None)."""
    ticker, stock = tickers.match(query_text)
    if not ticker or not stock:
        return None, None
    if lang is None:
        lang = "ko" if tickers.has_hangul(query_text) else "en"
    metrics = quotes.get_metrics(ticker)
    if not metrics:
        return None, ticker
    # 서술의 회사명 등에 최신 name 반영
    stock = dict(stock, name=metrics.get("name") or stock.get("ko"),
                 name_en=metrics.get("name_en") or stock.get("en"),
                 sector=metrics.get("sector"), market=metrics.get("market"),
                 ticker=ticker)
    nar = get_or_build_narrative(ticker, stock, lang)
    if not nar:
        return None, ticker
    fx = quotes.get_usdkrw(store) if lang == "en" else 0
    return compose.build(stock, metrics, nar, lang, fx), ticker


def process_mention(job, log=print):
    """멘션 잡 1건 처리 → 답글 게시. 실패 시 재시도 큐로 되돌림."""
    text, tid = job.get("text", ""), job.get("id")
    lang = "ko" if tickers.has_hangul(text) else "en"
    reply, ticker = build_reply(text, lang)
    if not reply:
        log(f"↷ 종목 매칭/데이터 없음 — 스킵 (tweet {tid})")
        return {"ok": True, "skipped": True}          # 마킹 유지(재시도 안 함)
    ok, detail = xclient.post_reply(reply, tid)
    if ok:
        log(f"✅ 답글 게시 — {ticker} ({lang}) → tweet {tid}")
        return {"ok": True, "ticker": ticker, "reply_id": detail.get("data", {}).get("id")}
    # 실패 → 재시도
    job["attempts"] = job.get("attempts", 0) + 1
    if job["attempts"] < MAX_ATTEMPTS:
        store.push_job(job)
        log(f"⚠ 게시 실패({job['attempts']}회) 재큐 — {detail}")
    else:
        log(f"✖ 게시 최종 실패({MAX_ATTEMPTS}회) 포기 — {detail}")
    return {"ok": False, "detail": str(detail)}
