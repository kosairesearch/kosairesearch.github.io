#!/usr/bin/env python3
"""리포트 본문 금지 표현 검사 — 프롬프트가 못 막은 것을 잡는다.

프롬프트는 부탁이지 강제가 아니다. 2,563개를 점검했더니 금지해 둔 표현이
26건 새어 나와 있었다(ROE 8 · TTM 용어 11 · '저평가/고평가' 단정 7).
비율로는 1% 미만이지만, 통제 수단이 프롬프트뿐이면 만들 때마다 그만큼 샌다.

  · 생성 파이프라인(generate_reports_v2.collect)이 리포트마다 호출해 로그에 남긴다
  · 단독 실행하면 이미 쌓인 리포트를 전수 검사한다

      python3 scripts/check_report_text.py                 # data/reports_v2 전체
      python3 scripts/check_report_text.py 005930 000660   # 특정 종목만

검사는 '틀린 것'이 아니라 '우리가 안 쓰기로 한 것'을 본다. 법적 위험(가치
판단 단정)과 품질 문제(화면에 없는 지표·전문 용어)가 섞여 있고, 심각도는
level 로 구분한다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "reports_v2"

# 본문을 이루는 필드들 — 새 섹션이 생기면 여기에 더한다.
PROSE_KEYS = ("lead", "business", "earnings", "industry", "outlook",
              "valuation_comment")
LIST_KEYS = ("keypoints", "risks", "bull", "bear", "checkpoints")

# 면책 문구는 금지어를 포함할 수밖에 없다 — 검사 대상에서 뺀다.
DISCLAIMER = re.compile(r"(투자\s*권유|정보\s*제공\s*목적|투자\s*판단(의|에)?\s*책임)")

# 증권사명 / 시점 — 목표주가 인용의 조건을 확인할 때 쓴다.
BROKER = re.compile(r"[가-힣A-Za-z]{2,10}(증권|투자증권|자산운용|리서치)")
WHEN = re.compile(r"(20\d{2}\s*년|\d{1,2}\s*월|분기|상반기|하반기|최근)")
# 목표주가 '숫자'를 옮길 때만 인용 조건을 따진다. 숫자 없이 "목표주가를 하향했다"는
# 시장 사실 전달이라 조건을 걸 대상이 아니다.
PRICE_NUM = re.compile(r"\d[\d,]*\s*(원|만원)")
# 증권사 + 전달 동사가 같은 문장에 있으면 '우리 판단'이 아니라 인용이다.
SAY = re.compile(r"(평가|분석|제시|전망|판단|진단|추정|설명)(했|하)")

RULES = (
    # (키, 심각도, 정규식, 설명)
    ("roe", "품질", re.compile(r"\bROE\b|자기자본이익률"),
     "서비스 화면에서 뺀 지표 — 글에만 나오면 독자가 찾을 곳이 없다"),
    ("term", "품질", re.compile(r"\bTTM\b|선행\s*PER|후행\s*PER"),
     "일반 독자가 모르는 용어 — '최근 네 개 분기 기준'처럼 풀어 쓸 것"),
    ("valuejudge", "위험", re.compile(
        r"(저평가|고평가)\s*(된|되어|다|이다|구간|상태|영역)|제값을\s*못\s*받"),
     "가치 판단 단정 — 손실 분쟁 시 근거가 된다. 사실 비교로 대체할 것"),
    # 리포트 본문은 '…이다/…한다' 로 쓴다. 독자에게 말을 거는 순간
    # 리서치가 아니라 권유문이 된다. 2,563개 중 한 건(001520)의
    # 체크포인트가 통째로 "…확인하세요" 로 새어 나와 있었다.
    #
    # 문장 끝(.!?)이 뒤따를 때만 잡는다. 그냥 글자만 보면 작품 제목
    # ('사랑이라 말해요')이나 '식품위해요소' 같은 말이 걸린다.
    ("tone", "품질", re.compile(r"(하세요|해요|주세요|보세요|인가요|나요)(?=\s*[.!?])"),
     "독자에게 말을 거는 말투 — 본문은 '…이다/…한다' 로 쓸 것"),
    ("solicit", "위험", re.compile(
        r"매수\s*(추천|권[유고])|매도\s*(추천|권[유고])|지금이\s*기회"
        r"|(?<![가-힣])담을\s*만하|사\s*모을\s*만하"),
     "투자 권유로 읽히는 표현"),
)


def _ko(v):
    if isinstance(v, dict):
        return (v.get("ko") or "").strip()
    return v.strip() if isinstance(v, str) else ""


def sentences(rep):
    """(섹션명, 문장) 목록. 문장 단위로 봐야 어디가 문제인지 짚어 줄 수 있다."""
    out = []

    def add(sec, text):
        for s in re.split(r"(?<=[.。!?])\s+|\n+", text or ""):
            s = s.strip()
            if s:
                out.append((sec, s))

    for k in PROSE_KEYS:
        add(k, _ko(rep.get(k)))
    add("verdict", _ko((rep.get("verdict") or {}).get("body")))
    for k in LIST_KEYS:
        for x in (rep.get(k) or []):
            if isinstance(x, dict):
                for f in ("title", "what", "when", "body"):
                    add(k, _ko(x.get(f)))
            else:
                add(k, _ko(x))
    return out


def check(rep):
    """위반 목록을 돌려준다. [] 면 통과."""
    hits = []
    for sec, s in sentences(rep):
        if DISCLAIMER.search(s):
            continue
        cited = bool(BROKER.search(s) and SAY.search(s))
        for key, level, pat, why in RULES:
            m = pat.search(s)
            # 가치 판단이라도 출처를 밝힌 인용이면 허용한다(규칙 5-1).
            if m and key == "valuejudge" and cited:
                continue
            if m:
                hits.append({"rule": key, "level": level, "section": sec,
                             "match": m.group(0), "why": why,
                             "sentence": s[:160]})
        # 목표주가는 허용하되 조건부 — 출처(증권사)와 시점이 같은 문장에 있어야 한다.
        if re.search(r"목표\s*주가", s) and PRICE_NUM.search(s):
            miss = []
            if not BROKER.search(s):
                miss.append("증권사명 없음")
            if not WHEN.search(s):
                miss.append("시점 없음")
            if miss:
                hits.append({"rule": "target_price", "level": "위험",
                             "section": sec, "match": "목표주가",
                             "why": "인용 조건 미충족(" + " · ".join(miss) + ")",
                             "sentence": s[:160]})
    return hits


def summary_line(ticker, hits):
    if not hits:
        return None
    by = {}
    for h in hits:
        by[h["rule"]] = by.get(h["rule"], 0) + 1
    worst = "위험" if any(h["level"] == "위험" for h in hits) else "품질"
    return f"  [{worst}] {ticker} — " + ", ".join(f"{k}×{v}" for k, v in by.items())


def main():
    only = set(sys.argv[1:])
    files = sorted(OUT_DIR.glob("*.json"))
    n = bad = 0
    per_rule = {}
    for f in files:
        if f.stem == "index" or (only and f.stem not in only):
            continue
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rep, dict):
            continue
        n += 1
        hits = check(rep)
        if not hits:
            continue
        bad += 1
        for h in hits:
            per_rule[h["rule"]] = per_rule.get(h["rule"], 0) + 1
        print(summary_line(f.stem, hits))
        if only:                       # 특정 종목을 지정했을 땐 문장까지 보여 준다
            for h in hits:
                print(f"      · {h['section']}: {h['match']} — {h['why']}")
                print(f"        {h['sentence']}")
    print(f"\n검사 {n:,}개 · 위반 {bad:,}개 ({bad/n*100:.1f}%)" if n else "대상 없음")
    for k, v in sorted(per_rule.items(), key=lambda kv: -kv[1]):
        why = next((r[3] for r in RULES if r[0] == k), "목표주가 인용 조건 미충족")
        print(f"  {v:5d}  {k:12} {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
