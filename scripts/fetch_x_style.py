#!/usr/bin/env python3
"""X(트위터) 스타일 예시 수집 — Apify로 반응 좋은 영어 금융/투자 글을 긁어와,
data/x_style_examples.json 에 인기순으로 저장한다.

이 파일은 daily_x_post.py가 '문체 참고(스타일)'로만 읽는다 — 내용·종목·매수추천은
절대 따라 쓰지 않고, 사람 같은 톤·리듬·훅(첫 문장)만 학습시키기 위한 것.

환경변수:
  APIFY_TOKEN            (필수) Apify API 토큰
  X_STYLE_ACTOR          Apify actor id (기본 apidojo~tweet-scraper)
  X_STYLE_QUERIES        검색어들을 '|'로 구분(비우면 기본 금융 키워드). 평범한 키워드 권장.
  X_STYLE_MAXITEMS       Apify가 긁어올 최대 트윗 수(기본 1000 — 무료 한도 내 대량)
  X_STYLE_MIN_LIKES      채택 최소 좋아요(기본 200)
  X_STYLE_KEEP           최종 저장할 예시 개수(기본 60, 인기순)
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
ACTOR = os.getenv("X_STYLE_ACTOR", "apidojo~tweet-scraper").strip().replace("/", "~")
MAXITEMS = int(os.getenv("X_STYLE_MAXITEMS", "1000") or "1000")
MIN_LIKES = int(os.getenv("X_STYLE_MIN_LIKES", "200") or "200")
KEEP = int(os.getenv("X_STYLE_KEEP", "60") or "60")

# 평범한 키워드(고급검색 연산자 없이) — 연산자는 액터가 못 먹어 noResults가 났다.
# 최소 좋아요는 아래 payload의 minimumFavorites(액터 전용 필드)로 건다.
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


def run_apify(queries):
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={TOKEN}"
    payload = {
        "searchTerms": queries,
        "sort": "Top",                 # 인기순(반응 좋은 글부터)
        "maxItems": MAXITEMS,
        "tweetLanguage": "en",
        "minimumFavorites": MIN_LIKES,  # 액터 전용 '최소 좋아요' 필터
        "includeSearchTerms": False,
    }
    print(f"- Apify 입력: {json.dumps({k: v for k, v in payload.items() if k != 'searchTerms'})} · 검색어 {queries}")
    r = requests.post(url, json=payload, timeout=290)
    if not r.ok:
        print(f"❌ Apify 응답 오류 {r.status_code}: {r.text[:500]}")
        sys.exit(1)
    try:
        data = r.json()
    except Exception as e:
        print(f"❌ Apify 결과 파싱 실패: {e}")
        sys.exit(1)
    if isinstance(data, dict):
        if data.get("error"):
            print(f"❌ Apify 에러: {json.dumps(data)[:500]}")
            sys.exit(1)
        data = data.get("items") or data.get("results") or []
    return data if isinstance(data, list) else []


def main():
    if not TOKEN:
        print("❌ APIFY_TOKEN 미설정 — GitHub Secrets에 APIFY_TOKEN 등록 필요.")
        sys.exit(1)

    env_q = [q.strip() for q in os.getenv("X_STYLE_QUERIES", "").split("|") if q.strip()]
    queries = env_q or DEFAULT_QUERIES
    print(f"🔎 Apify actor {ACTOR} · maxItems {MAXITEMS} · 최소좋아요 {MIN_LIKES} · KEEP {KEEP}")

    items = run_apify(queries)
    # 검색 결과 없음 마커 제거
    real = [d for d in items if isinstance(d, dict) and not d.get("noResults")]
    print(f"- 수집 원본 {len(items)}건 (유효 {len(real)}건)")
    if not real:
        print("⚠ 유효 트윗 0건 — 검색이 결과를 반환하지 않음. 기존 예시 보존. "
              "검색어(X_STYLE_QUERIES)나 actor(X_STYLE_ACTOR)를 조정하세요.")
        if items:
            print(f"- 원본 샘플: {json.dumps(items[0], ensure_ascii=False)[:400]}")
        sys.exit(0)
    print(f"- 유효 첫 항목 키: {sorted(real[0].keys())}")

    seen, cand = set(), []
    for d in real:
        text = _text(d)
        if not text or text.startswith("RT @") or d.get("isRetweet") or d.get("retweeted"):
            continue
        lang = (d.get("lang") or d.get("language") or "en").lower()
        if lang not in ("en", "en-gb", "en-us", ""):
            continue
        likes = _count(d, LIKE_KEYS)
        if likes < MIN_LIKES:
            continue
        clean = re.sub(r"https?://\S+", "", text).strip()
        if not (60 <= len(clean) <= 1200):
            continue
        if BLOCK.search(clean):
            continue
        key = re.sub(r"\W+", "", clean.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        cand.append({
            "text": clean, "likes": likes, "retweets": _count(d, RT_KEYS),
            "author": _author(d), "url": d.get("url") or d.get("twitterUrl") or "",
        })

    cand.sort(key=lambda x: x["likes"], reverse=True)   # 인기순(좋아요 많은 순)
    top = cand[:KEEP]
    print(f"- 필터 통과 {len(cand)}건 → 인기순 상위 {len(top)}건 저장")

    if len(top) < 3:
        print("⚠ 채택 예시가 3건 미만 — 기존 예시 파일 보존(덮어쓰지 않음).")
        sys.exit(0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "source": f"apify:{ACTOR}",
        "note": "문체(스타일) 참고용. 내용·종목·추천은 daily_x_post에서 절대 인용하지 않음.",
        "count": len(top),
        "examples": top,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 저장 완료 → {OUT.relative_to(ROOT)} ({len(top)}건, 인기순)")


if __name__ == "__main__":
    main()
