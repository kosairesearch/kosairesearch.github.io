#!/usr/bin/env python3
"""X(트위터) 스타일 예시 수집 — Apify로 반응 좋은 영어 금융/투자 글을 긁어와,
data/x_style_examples.json 에 상위 예시만 저장한다.

이 파일은 daily_x_post.py가 '문체 참고(스타일)'로만 읽는다 — 내용·종목·매수추천은
절대 따라 쓰지 않고, 사람 같은 톤·리듬·훅(첫 문장)만 학습시키기 위한 것.

환경변수:
  APIFY_TOKEN            (필수) Apify API 토큰
  X_STYLE_ACTOR          Apify actor id (기본 apidojo~tweet-scraper)
  X_STYLE_QUERIES        검색어들을 '|'로 구분(비우면 기본값). 트위터 고급검색 연산자 사용 가능.
  X_STYLE_MAXITEMS       Apify가 긁어올 최대 트윗 수(기본 200)
  X_STYLE_MIN_LIKES      예시 채택 최소 좋아요(기본 300)
  X_STYLE_KEEP           최종 저장할 예시 개수(기본 15)
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
MAXITEMS = int(os.getenv("X_STYLE_MAXITEMS", "200") or "200")
MIN_LIKES = int(os.getenv("X_STYLE_MIN_LIKES", "300") or "300")
KEEP = int(os.getenv("X_STYLE_KEEP", "15") or "15")

DEFAULT_QUERIES = [
    f"stocks min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"earnings min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"stock market min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"semiconductor OR chips min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
]

# 저품질/과장/스팸 톤 배제 — 이런 글을 학습하면 규정 위반·AI 스팸 느낌이 난다.
BLOCK = re.compile(
    r"(🚀{2,}|100x|1000x|guaranteed|get rich|dm me|join (my|the)|link in bio|"
    r"pump|financial freedom|to the moon|not financial advice|nfa\b|giveaway|"
    r"retweet to win|follow (me|back)|👇{2,})",
    re.I,
)

# 좋아요/리트윗 카운트가 담길 수 있는 필드명(액터 버전마다 다름) + 중첩 딕셔너리도 탐색.
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
    payload = {"searchTerms": queries, "sort": "Top", "maxItems": MAXITEMS, "tweetLanguage": "en"}
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
        # 에러 객체이거나 {items:[...]} 형태일 수 있음
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
    print(f"🔎 Apify actor {ACTOR} · 검색 {len(queries)}건 · maxItems {MAXITEMS} · 최소좋아요 {MIN_LIKES}")

    items = run_apify(queries)
    print(f"- 수집 원본 {len(items)}건")
    if items and isinstance(items[0], dict):
        # 진단: 액터가 주는 실제 필드명 확인용(좋아요 필드 못 찾는 문제 대비)
        print(f"- 원본 첫 항목 키: {sorted(items[0].keys())}")
        print(f"- 원본 첫 항목 샘플: {json.dumps(items[0], ensure_ascii=False)[:700]}")

    seen, cand = set(), []
    for d in items:
        if not isinstance(d, dict):
            continue
        text = _text(d)
        if not text or text.startswith("RT @") or d.get("isRetweet") or d.get("retweeted"):
            continue
        lang = (d.get("lang") or d.get("language") or "en").lower()
        if lang not in ("en", "en-gb", "en-us", ""):
            continue
        likes = _count(d, LIKE_KEYS)
        if likes < MIN_LIKES:
            continue
        clean = re.sub(r"https?://\S+", "", text).strip()  # 링크 제거(문체만 학습)
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

    cand.sort(key=lambda x: x["likes"], reverse=True)
    top = cand[:KEEP]
    print(f"- 필터 통과 {len(cand)}건 → 상위 {len(top)}건 저장")

    if len(top) < 3:
        print("⚠ 채택 예시가 3건 미만 — 기존 예시 파일 보존(덮어쓰지 않음). "
              "위 '원본 첫 항목 키'를 보고 필터/필드명을 조정하세요.")
        sys.exit(0)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "source": f"apify:{ACTOR}",
        "note": "문체(스타일) 참고용. 내용·종목·추천은 daily_x_post에서 절대 인용하지 않음.",
        "count": len(top),
        "examples": top,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 저장 완료 → {OUT.relative_to(ROOT)} ({len(top)}건)")


if __name__ == "__main__":
    main()
