#!/usr/bin/env python3
"""지난 날짜의 재료로 브리핑을 다시 써 본다 — 발행하지 않는다.

왜 필요한가
-----------
"매일 같은 내용처럼 보인다"를 고치려고 프롬프트에서 틀을 걷어냈다. 그게
실제로 다른 글을 만드는지는 눈으로 봐야 안다. 그런데 내일 아침을 기다려
확인하면 이미 발행된 뒤다.

data/briefs/<날짜>.json 에는 그날 모델에게 준 재료(factsDigest)가 통째로
들어 있다. 그걸 그대로 다시 먹이면 **재료는 같고 규칙만 다른** 글이 나온다.
변수가 하나여야 비교가 된다.

아무것도 커밋하지 않는다. data/briefs 를 건드리지 않고 따로 적어 둔다.

    python3 scripts/brief_replay.py 2026-09-11 2026-09-10 2026-09-09

끝나면 이 파일과 .github/workflows/brief_replay.yml 은 지운다.
"""
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_brief as G  # noqa: E402

OUT = ROOT / "data" / "_replay"


def replay(cl, date):
    src = G.OUT_DIR / f"{date}.json"
    if not src.exists():
        print(f"❌ {date} — 그날 브리핑이 없다", file=sys.stderr)
        return None
    old = json.loads(src.read_text(encoding="utf-8"))
    digest = old.get("factsDigest")
    if not digest:
        print(f"❌ {date} — 저장된 재료가 없다", file=sys.stderr)
        return None

    # 그날의 재료를 그대로 쓴다. 수집기를 다시 돌리면 오늘 값이 섞인다.
    G._facts_text = lambda facts: digest
    facts = {"domestic": {"publishDate": date,
                          "calendar": {"open": bool(old.get("marketOpen", True)),
                                       "today": old.get("tradeDate") or ""}},
             "markets": {}}
    prompt = G.build_prompt(facts)
    print(f"· {date} 프롬프트 {len(prompt):,}자 — 모델 호출", file=sys.stderr)
    text, usage = G.call_sync(cl, prompt)
    try:
        new = G.parse(text)
    except Exception as e:
        print(f"❌ {date} 읽기 실패: {type(e).__name__}: {e}", file=sys.stderr)
        print(text[:1500], file=sys.stderr)
        return None

    # 검사는 막지 않고 알려만 준다 — 보려고 만든 글이지 내보낼 글이 아니다.
    bad = G.validate(new, strict_coverage=False, facts=facts)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{date}.json").write_text(
        json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'='*78}\n{date}\n{'='*78}")
    print(f"[예전] {old['title']['ko']}")
    print(f"       {old['lead']['ko'][:100]}")
    print("       칸: " + " / ".join(
        (s.get('heading') or {}).get('ko', '') for s in old.get('sections', [])))
    print(f"\n[새것] {new['title']['ko']}")
    print(f"       {new['lead']['ko'][:100]}")
    print("       칸: " + " / ".join(
        f"{s.get('id')}◂{(s.get('heading') or {}).get('ko','')}▸"
        for s in new.get('sections', [])))
    n, ratio = G.measure(new)
    print(f"\n       분량 {n:,}자 · 칸 {len(new.get('sections') or [])}개 "
          f"· 커버리지 {ratio*100:.0f}%")
    if bad:
        print(f"       ⚠️ 검사 지적 {len(bad)}건: {bad[:3]}")
    else:
        print("       검사 통과")
    print("\n─ 본문 ─")
    for s in new.get("sections") or []:
        print(f"\n■ {(s.get('heading') or {}).get('ko','')}  [{s.get('id')}]")
        for p in s.get("paragraphs") or []:
            print("  " + (p.get("ko") or ""))
    return usage


def main(argv):
    dates = argv or [
        (datetime.date.today() - datetime.timedelta(days=i)).isoformat() for i in (1, 2, 3)]
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY 가 없다", file=sys.stderr)
        return 1
    cl = G._client()
    used = 0.0
    for d in dates:
        u = replay(cl, d)
        if u:
            used += G.cost(u)["usd"]
    print(f"\n{'='*78}\n끝. 결과는 data/_replay/ 에 있다(커밋하지 않는다).")
    if used:
        print(f"이번 시험 비용 약 ${used:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
