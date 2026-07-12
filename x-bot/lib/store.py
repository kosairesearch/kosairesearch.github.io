"""Upstash Redis (REST) — 캐시 · 중복방지 · 체크포인트 · 환율캐시.

redis 클라이언트 없이 HTTP REST만 사용(서버리스 번들 최소화).
env: UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN
"""
import json
import os
import time

import requests

_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")

PROC_TTL = 7 * 24 * 3600          # 처리한 멘션ID 보관 7일
FX_TTL = 24 * 3600                # 환율 1일 캐시


def _cmd(*args):
    """Upstash REST: JSON 배열 형태의 Redis 명령을 실행하고 result를 반환."""
    if not _URL or not _TOKEN:
        raise RuntimeError("UPSTASH_REDIS_REST_URL/TOKEN 미설정")
    r = requests.post(_URL, headers={"Authorization": f"Bearer {_TOKEN}"},
                      data=json.dumps([str(a) for a in args]), timeout=10)
    r.raise_for_status()
    return r.json().get("result")


# ---- 범용 ----
def get(key):
    return _cmd("GET", key)


def set(key, value, ex=None):
    if ex:
        return _cmd("SET", key, value, "EX", ex)
    return _cmd("SET", key, value)


# ---- 중복 방지 ----
def mark_if_new(tweet_id):
    """처음 보는 멘션이면 True(예약 성공), 이미 처리했으면 False.
    SET ... NX 로 원자적 처리 — 동시 실행돼도 한 번만 답글."""
    res = _cmd("SET", f"proc:{tweet_id}", "1", "NX", "EX", PROC_TTL)
    return res == "OK"


def unmark(tweet_id):
    """처리 실패 시 예약 해제(다음 폴링에서 재시도되게)."""
    _cmd("DEL", f"proc:{tweet_id}")


# ---- 체크포인트(마지막으로 본 멘션 시각, epoch초) ----
def get_checkpoint():
    v = get("mention:last_ts")
    try:
        return float(v) if v else 0.0
    except (TypeError, ValueError):
        return 0.0


def set_checkpoint(ts):
    set("mention:last_ts", str(ts))


# ---- 서술(narrative) 캐시: 종목_언어 분리, 생성일 포함 ----
# CACHE_VER: 문체·프롬프트가 바뀌면 버전을 올려 기존 캐시를 통째로 무효화한다.
_CACHE_VER = os.environ.get("CACHE_VER", "v2")


def get_narrative(ticker, lang):
    v = get(f"cache:{_CACHE_VER}:{ticker}:{lang}")
    if not v:
        return None
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


def set_narrative(ticker, lang, data):
    set(f"cache:{_CACHE_VER}:{ticker}:{lang}", json.dumps(data, ensure_ascii=False))


# ---- 처리 대기열(멘션 잡) — 감지와 생성을 분리해 함수 타임아웃을 피한다 ----
def push_job(job):
    _cmd("RPUSH", "jobs", json.dumps(job, ensure_ascii=False))


def pop_job():
    v = _cmd("LPOP", "jobs")
    if not v:
        return None
    try:
        return json.loads(v)
    except (TypeError, ValueError):
        return None


def jobs_len():
    try:
        return int(_cmd("LLEN", "jobs") or 0)
    except (TypeError, ValueError):
        return 0


# ---- 환율 캐시(USD/KRW) ----
def get_fx():
    v = get("fx:usdkrw")
    try:
        return float(v) if v else None
    except (TypeError, ValueError):
        return None


def set_fx(rate):
    set("fx:usdkrw", str(rate), ex=FX_TTL)
