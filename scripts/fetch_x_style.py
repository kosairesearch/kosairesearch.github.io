#!/usr/bin/env python3
"""X(트위터) 스타일 예시 수집 — Apify로 반응 좋은 영어 금융/투자 글을 긁어와,
data/x_style_examples.json 에 상위 예시만 저장한다.

이 파일은 daily_x_post.py가 '문체 참고(스타일)'로만 읽는다 — 내용·종목·매수추천은
절대 따라 쓰지 않고, 사람 같은 톤·리듬·훅(첫 문장)만 학습시키기 위한 것.

동작:
  Apify actor(기본 apidojo/tweet-scraper)를 run-sync로 실행 → 데이터셋 결과를 받아
  영어·비리트윗·적정 길이·최소 좋아요 필터 후 좋아요순 상위 N개를 저장.

환경변수:
  APIFY_TOKEN            (필수) Apify API 토큰
  X_STYLE_ACTOR          Apify actor id (기본 apidojo~tweet-scraper)
  X_STYLE_QUERIES        검색어들을 '|'로 구분(비우면 기본값). 트위터 고급검색 연산자 사용 가능.
  X_STYLE_MAXITEMS       Apify가 긁어올 최대 트윗 수(기본 120)
  X_STYLE_MIN_LIKES      예시 채택 최소 좋아요(기본 500)
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
MAXITEMS = int(os.getenv("X_STYLE_MAXITEMS", "120") or "120")
MIN_LIKES = int(os.getenv("X_STYLE_MIN_LIKES", "500") or "500")
KEEP = int(os.getenv("X_STYLE_KEEP", "15") or "15")

# 기본 검색어 — 반응 좋은 '영어 금융/주식/실적' 글. 답글·링크·리트윗 제외로 본문 위주.
# (min_faves는 트위터 고급검색 연산자 — Apify가 그대로 X 검색에 넘긴다.)
DEFAULT_QUERIES = [
    f"stocks min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"earnings min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"stock market min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
    f"semiconductor OR chips min_faves:{MIN_LIKES} lang:en -filter:replies -filter:links -filter:nativeretweets",
]

# 저품질/과장/스팸 톤 배제 — 이런 글을 스타일로 학습하면 규정 위반·AI 스팸 느낌이 난다.
BLOCK = re.compile(
    r"(🚀{2,}|100x|1000x|guaranteed|get rich|dm me|join (my|the)|link in bio|"
    r"pump|financial freedom|to the moon|not financial advice|nfa\b|giveaway|"
    r"retweet to win|follow (me|back)|👇{2,})",
    re.I,
)


def _f(d, *keys, default=0):
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)) and v is not None:
            return v
    return default


def _text(d):
    for k in ("text", "fullText", "full_text", "rawContent", "content"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _author(d):
    a = d.get("author") or d.get("user") or {}
    if isinstance(a, dict):
        return a.get("userName") or a.get("username") or a.get("screen_name") or ""
    return str(a or "")


def _is_retweet(d, text):
    if d.get("isRetweet") or d.get("retweeted"):
        return True
    return text.startswith("RT @")


def run_apify(queries):
    url = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items?token={TOKEN}"
    payload = {
        "searchTerms": queries,
        "sort": "Top",
        "maxItems": MAXITEMS,
        "tweetLanguage": "en",
    }
    r = requests.post(url, json=payload, timeout=280)
    if not r.ok:
        print(f"❌ Apify 응답 오류 {r.status_code}: {r.text[:400]}")
        sys.exit(1)
    try:
        return r.json()
    except Exception as e:
        print(f"❌ Apify 결과 파싱 실패: {e}")
        sys.exit(1)


def main():
    if not TOKEN:
        print("❌ APIFY_TOKEN 미설정 — GitHub Secrets에 APIFY_TOKEN 등록 필요.")
        sys.exit(1)

    env_q = [q.strip() for q in os.getenv("X_STYLE_QUERIES", "").split("|") if q.strip()]
    queries = env_q or DEFAULT_QUERIES
    print(f"🔎 Apify actor {ACTOR} · 검색 {len(queries)}건 · maxItems {MAXITEMS}")

    items = run_apify(queries)
    print(f"- 수집 원본 {len(items)}건")

    seen, cand = set(), []
    for d in items:
        if not isinstance(d, dict):
            continue
        text = _text(d)
        if not text or _is_retweet(d, text):
            continue
        lang = (d.get("lang") or d.get("language") or "en").lower()
        if lang not in ("en", "en-gb", "en-us", ""):
            continue
        likes = int(_f(d, "likeCount", "favoriteCount", "likes", "favorite_count"))
        if likes < MIN_LIKES:
            continue
        clean = re.sub(r"https?://\S+", "", text).strip()  # 링크 제거(문체만 학습)
        if not (80 <= len(clean) <= 1200):   # 너무 짧거나(한 줄) 스레드 덤프는 제외
            continue
        if BLOCK.search(clean):
            continue
        key = re.sub(r"\W+", "", clean.lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        cand.append({
            "text": clean,
            "likes": likes,
            "retweets": int(_f(d, "retweetCount", "retweet_count")),
            "author": _author(d),
            "url": d.get("url") or d.get("twitterUrl") or "",
        })

    cand.sort(key=lambda x: x["likes"], reverse=True)
    top = cand[:KEEP]
    print(f"- 필터 통과 {len(cand)}건 → 상위 {len(top)}건 저장")

    if len(top) < 3:
        # 결과가 너무 적으면(검색 실패·필터 과함) 기존 파일을 덮어써 망가뜨리지 않는다.
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
    print(f"✅ 저장 완료 → {OUT.relative_to(ROOT)} ({len(top)}건)")


if __name__ == "__main__":
    main()
