#!/usr/bin/env python3
"""X(트위터) 스타일 예시 수집 — Apify로 반응 좋은 영어 금융/투자 글을 긁어와,
data/x_style_examples.json 에 인기순으로 저장한다.

이 파일은 daily_x_post.py가 '문체 참고(스타일)'로만 읽는다 — 내용·종목·매수추천은
절대 따라 쓰지 않고, 사람 같은 톤·리듬·훅(첫 문장)만 학습시키기 위한 것.

여러 X 스크래퍼 액터를 순서대로 시도해, 트윗을 실제로 반환하는 첫 액터의 결과를 쓴다
(어떤 액터가 X 차단 등으로 noResults만 주면 다음 액터로 폴백). pay-per-result라
결과 0건 액터는 비용이 거의 없다.

환경변수:
  APIFY_TOKEN            (필수) Apify API 토큰
  X_STYLE_ACTORS         시도할 actor id들(콤마 구분). 비우면 기본 목록.
  X_STYLE_QUERIES        검색어들을 '|'로 구분(비우면 기본 금융 키워드).
  X_STYLE_MAXITEMS       actor당 최대 수집 트윗 수(기본 1000)
  X_STYLE_MIN_LIKES      채택 최소 좋아요(기본 200)
  X_STYLE_KEEP           최종 저장 예시 개수(기본 80, 인기순)
"""
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "x_style_examples.json"
KST = timezone(timedelta(hours=9))

TOKEN = os.getenv("APIFY_TOKEN", "").strip()
MAXITEMS = int(os.getenv("X_STYLE_MAXITEMS", "500") or "500")
MIN_LIKES = int(os.getenv("X_STYLE_MIN_LIKES", "200") or "200")
KEEP = int(os.getenv("X_STYLE_KEEP", "80") or "80")
POLL_SEC = int(os.getenv("X_STYLE_POLL_SEC", "600") or "600")  # 액터당 완료 대기 상한

# pay-per-result 액터 우선(무료 플랜에서도 동작). apidojo 계열은 무료 플랜에서
# demo/noResults만 반환해 기본 목록에서 제외.
DEFAULT_ACTORS = [
    "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest",
]

DEFAULT_QUERIES = [
    "stock market", "stocks", "earnings", "semiconductor",
    "chip stocks", "tech stocks", "investing", "Korean stocks",
]

BLOCK = re.compile(
    r"(🚀{2,}|100x|1000x|guaranteed|get rich|dm me|join (my|the)|link in bio|"
    r"pump|financial freedom|to the moon|not financial advice|nfa\b|giveaway|"
    r"retweet to win|follow (me|back)|👇{2,})",
    re.I,
)

LIKE_KEYS = ("likeCount", "favoriteCount", "favorite_count", "like_count", "likes", "favouriteCount")
RT_KEYS = ("retweetCount", "retweet_count", "retweets")
NEST = ("legacy", "stats", "public_metrics", "publicMetrics", "metrics", "tweet")


def _num_in(d, keys):
    for k in keys:
        v = d.get(k)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.replace(",", "").isdigit():
            return int(v.replace(",", ""))
    return None


def _count(d, keys):
    v = _num_in(d, keys)
    if v is not None:
        return v
    for sub in NEST:
        s = d.get(sub)
        if isinstance(s, dict):
            v = _num_in(s, keys)
            if v is not None:
                return v
    return 0


def _text(d):
    for k in ("text", "fullText", "full_text", "rawContent", "content", "tweetText"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    leg = d.get("legacy")
    if isinstance(leg, dict):
        for k in ("full_text", "text"):
            v = leg.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _author(d):
    a = d.get("author") or d.get("user") or {}
    if isinstance(a, dict):
        return a.get("userName") or a.get("username") or a.get("screen_name") or a.get("screenName") or ""
    return str(a or "")


def run_actor(actor, queries):
    """actor 하나를 '비동기'로 실행: 시작 → 완료까지 폴링 → 데이터셋 회수.
    run-sync의 300초 한도에 안 잘리므로 대량 스크래핑도 안전. 실패 시 빈 리스트."""
    import time
    base = "https://api.apify.com/v2"
    payload = {
        "searchTerms": queries,
        "sort": "Top",
        "maxItems": MAXITEMS,
        "maxTweets": MAXITEMS,          # 액터별 필드명 차이 대비(무시되면 그만)
        "tweetLanguage": "en",
        "minimumFavorites": MIN_LIKES,
        "includeSearchTerms": False,
    }
    try:
        r = requests.post(f"{base}/acts/{actor}/runs?token={TOKEN}", json=payload, timeout=60)
    except Exception as e:
        print(f"  · {actor}: 시작 예외 {e}")
        return []
    if not r.ok:
        print(f"  · {actor}: 시작 HTTP {r.status_code} {r.text[:200]}")
        return []
    run = (r.json() or {}).get("data", {})
    run_id, ds = run.get("id"), run.get("defaultDatasetId")
    if not run_id:
        print(f"  · {actor}: run id 없음")
        return []
    deadline, status = time.time() + POLL_SEC, run.get("status")
    while time.time() < deadline and status not in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"):
        time.sleep(8)
        try:
            s = (requests.get(f"{base}/actor-runs/{run_id}?token={TOKEN}", timeout=30).json() or {}).get("data", {})
            status, ds = s.get("status", status), s.get("defaultDatasetId", ds)
        except Exception:
            continue
    print(f"  · {actor}: 상태 {status}")
    if status != "SUCCEEDED" or not ds:
        return []
    try:
        items = requests.get(f"{base}/datasets/{ds}/items?token={TOKEN}&clean=true&format=json", timeout=120).json()
    except Exception as e:
        print(f"  · {actor}: 데이터셋 회수 실패 {e}")
        return []
    return items if isinstance(items, list) else []


def extract(items):
    seen, cand = set(), []
    rej = {"notext": 0, "rt": 0, "lang": 0, "likes": 0, "len": 0, "block": 0, "dup": 0}
    for d in items:
        if not isinstance(d, dict) or d.get("noResults"):
            continue
        text = _text(d)
        if not text:
            rej["notext"] += 1; continue
        if text.startswith("RT @") or d.get("isRetweet") or d.get("retweeted"):
            rej["rt"] += 1; continue
        lang = str(d.get("lang") or d.get("language") or "").lower()
        if lang and not lang.startswith("en"):   # 언어 정보 있고 영어 아니면 제외(없으면 통과)
            rej["lang"] += 1; continue
        likes = _count(d, LIKE_KEYS)
        if likes < MIN_LIKES:
            rej["likes"] += 1; continue
        clean = re.sub(r"https?://\S+", "", text).strip()
        clean = re.sub(r"\s+\n", "\n", clean).strip()
        if not (40 <= len(clean) <= 1500):
            rej["len"] += 1; continue
        if BLOCK.search(clean):
            rej["block"] += 1; continue
        key = re.sub(r"\W+", "", clean.lower())[:80]
        if key in seen:
            rej["dup"] += 1; continue
        seen.add(key)
        cand.append({
            "text": clean, "likes": likes, "retweets": _count(d, RT_KEYS),
            "author": _author(d), "url": d.get("url") or d.get("twitterUrl") or "",
        })
    if not cand and any(rej.values()):
        print(f"      제외 사유: {rej}")
    return cand


def main():
    if not TOKEN:
        print("❌ APIFY_TOKEN 미설정 — GitHub Secrets에 APIFY_TOKEN 등록 필요.")
        sys.exit(1)

    actors = [a.strip() for a in os.getenv("X_STYLE_ACTORS", "").split(",") if a.strip()] or DEFAULT_ACTORS
    queries = [q.strip() for q in os.getenv("X_STYLE_QUERIES", "").split("|") if q.strip()] or DEFAULT_QUERIES

    # kaito는 sort:Top·minimumFavorites를 무시하고 '최신순(좋아요 0)'을 반환한다.
    # → X 고급검색 연산자를 검색어에 직접 넣어 인기 글만 받는다(kaito는 X 검색을 실제 수행).
    def with_ops(q):
        if "min_faves" in q or "filter:" in q:
            return q
        return f"{q} min_faves:{MIN_LIKES} lang:en -filter:replies -filter:nativeretweets"
    queries = [with_ops(q) for q in queries]

    print(f"🔎 actor {len(actors)}개 시도 · maxItems {MAXITEMS} · 최소좋아요 {MIN_LIKES} · KEEP {KEEP}")
    print(f"   검색어: {queries}")

    cand = []
    for actor in actors:
        items = run_actor(actor, queries)
        real = [d for d in items if isinstance(d, dict) and not d.get("noResults")]
        print(f"  · {actor}: 원본 {len(items)}건 · 유효 {len(real)}건")
        if real:
            print(f"      첫 항목 샘플: {json.dumps(real[0], ensure_ascii=False)[:600]}")
        cand = extract(items)
        print(f"      필터 통과 {len(cand)}건")
        if len(cand) >= 3:
            print(f"  ✅ 사용 액터: {actor}")
            break

    if len(cand) < 3:
        print("⚠ 어떤 액터도 트윗을 반환하지 않음(모두 noResults/차단 추정). 기존 예시 보존. "
              "X_STYLE_ACTORS로 다른 액터를 지정해보세요.")
        sys.exit(0)

    cand.sort(key=lambda x: x["likes"], reverse=True)   # 인기순
    top = cand[:KEEP]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "note": "문체(스타일) 참고용. 내용·종목·추천은 daily_x_post에서 절대 인용하지 않음.",
        "count": len(top),
        "examples": top,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 저장 완료 → {OUT.relative_to(ROOT)} ({len(top)}건, 인기순)")


if __name__ == "__main__":
    main()
