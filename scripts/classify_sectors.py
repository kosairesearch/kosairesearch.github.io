#!/usr/bin/env python3
"""
KOS ai — AI(Haiku) 전 종목 업종 분류기.

종목명 + KSIC 업종코드를 보고 각 종목을 고정 카테고리 1개로 분류해
data/sector_map.json {ticker: 카테고리} 캐시를 만든다.
한 번 분류하면 캐시를 재사용하고, 캐시에 없는(신규 상장) 종목만 추가 분류한다.
(CLASSIFY_FORCE=1 이면 전 종목 재분류)

비용: 웹검색 없음, 짧은 출력 → 매우 저렴(Haiku). 약 40종목/요청.
"""
import os
import re
import sys
import json
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
CACHE = ROOT / "data" / "sector_map.json"

MODEL = os.getenv("CLASSIFY_MODEL", "claude-haiku-4-5")
FORCE = os.getenv("CLASSIFY_FORCE", "") == "1"
BATCH = int(os.getenv("CLASSIFY_BATCH", "40"))

# 고정 카테고리(프론트 필터와 동일하게 유지). 이 목록에서만 선택.
CATEGORIES = [
    "반도체", "전자·부품", "IT·소프트웨어", "게임", "기계·장비", "전기장비",
    "2차전지", "자동차", "조선", "항공·방산", "바이오·제약", "화학", "화장품",
    "정유", "에너지·전력", "철강·금속", "건설·건자재", "식음료", "섬유·패션·생활",
    "유통·소비재", "미디어·엔터", "통신", "금융", "보험", "지주", "운송·물류",
    "부동산·리츠", "호텔·레저", "기타",
]
VALID = set(CATEGORIES)

SYSTEM = (
    "너는 한국 주식 종목을 업종으로 분류하는 애널리스트다. 주어진 카테고리 목록에서만 "
    "골라 각 종목에 가장 알맞은 1개를 배정한다. 회사의 실제 주력 사업(매출 비중)을 기준으로 "
    "판단하고, KSIC 코드는 참고만 한다. 반드시 JSON만 출력한다."
)


def log(m):
    print(m, flush=True)


def load_stocks():
    raw = STOCKS_JS.read_text(encoding="utf-8")
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]


def load_cache():
    if CACHE.exists():
        try:
            return json.loads(CACHE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache):
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


def build_prompt(chunk):
    lines = [
        "카테고리 목록(반드시 이 중에서만 선택):",
        ", ".join(CATEGORIES),
        "",
        "분류 지침:",
        "- 회사의 실제 주력 사업 기준. 지주회사는 '지주', 리츠/부동산임대는 '부동산·리츠'.",
        "- 신약개발 바이오텍(연구개발업)도 '바이오·제약'. 석유 도매/주유는 '유통·소비재'(정유는 정제사만).",
        "- 증권/은행/카드/캐피탈은 '금융', 손해/생명보험은 '보험'. 광고/엔터/방송은 '미디어·엔터'.",
        "- 여행/카지노/레저는 '호텔·레저'. 정수기/렌탈/생활가전은 '유통·소비재'.",
        "- 애매하면 가장 비중 큰 사업으로. 도저히 모르면 '기타'.",
        "",
        '출력은 JSON만: {"종목코드":"카테고리", ...}',
        "",
        "분류할 종목:",
    ]
    for s in chunk:
        lines.append(f"- {s['ticker']} {s['name']} (KSIC {s.get('induty_code') or '-'})")
    return "\n".join(lines)


def parse_json(text):
    chunk = text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(chunk)
    except Exception:
        try:
            from json_repair import repair_json
            return repair_json(chunk, return_objects=True)
        except Exception:
            return {}


def classify_chunk(client, chunk):
    msg = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_prompt(chunk)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return parse_json(text)


def main():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음")
        sys.exit(1)
    client = anthropic.Anthropic(api_key=key)

    stocks = load_stocks()
    cache = load_cache()
    todo = [s for s in stocks if FORCE or s["ticker"] not in cache]
    log(f"## AI 업종 분류 — 대상 {len(todo)}/{len(stocks)}개 · 모델 {MODEL}")
    if not todo:
        log("- 분류할 신규 종목 없음(캐시 최신).")
        return

    done = 0
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        try:
            res = classify_chunk(client, chunk)
        except Exception as e:
            log(f"  · ⚠️ 배치 {i//BATCH+1} 오류: {type(e).__name__}: {e} — 재시도")
            time.sleep(3)
            try:
                res = classify_chunk(client, chunk)
            except Exception as e2:
                log(f"  · ❌ 재시도 실패: {e2}")
                continue
        if not isinstance(res, dict):
            res = {}
        for s in chunk:
            c = res.get(s["ticker"]) or res.get(str(s["ticker"]))
            if c in VALID:
                cache[s["ticker"]] = c
                done += 1
        save_cache(cache)
        log(f"  · {min(i+BATCH, len(todo))}/{len(todo)} 처리 (누적 분류 {done})")

    log(f"\n✅ 분류 완료 · 신규 {done}개 · 캐시 총 {len(cache)}개 → data/sector_map.json")


if __name__ == "__main__":
    main()
