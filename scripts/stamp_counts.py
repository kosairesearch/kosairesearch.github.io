#!/usr/bin/env python3
"""랜딩 페이지의 'AI 리포트' 수를 실제 값으로 박아 넣는다.

왜 있는가. 그 숫자가 index.html 에 손으로 적혀 있었고, 아무도 안 고쳤다.
그래서 리포트가 늘어날 때마다 조금씩 어긋났고(2,684 인데 실제는 2,686),
페이지가 뜬 뒤 자바스크립트가 뒤늦게 진짜 값으로 갈아 끼웠다. 방문자에게는
숫자가 한 번 튀는 것으로 보인다.

게다가 그 자바스크립트는 숫자 하나를 고치려고 data/reports-index.js 를 통째로
받았다 — 600KB다. 가장 많이 열리는 페이지에서 매번.

빌드할 때 맞는 값을 적어 두면 튈 일도, 받아 올 일도 없다. 리포트를 새로
만드는 워크플로가 이 스크립트를 부른다.

사용
    python scripts/stamp_counts.py            # 고쳐 쓴다
    python scripts/stamp_counts.py --check    # 어긋났는지만 본다(고치지 않음)

어긋나 있으면 --check 는 1 로 끝난다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "reports-index.js"
PAGE = ROOT / "index.html"

# <b id="lpRepN" data-i18n-skip>2,684</b>
PATTERN = re.compile(r'(<b id="lpRepN"[^>]*>)([^<]*)(</b>)')


def stock_count() -> int:
    """리포트 인덱스가 말하는 종목 수. 리포트 페이지가 쓰는 값과 같아야 한다."""
    text = INDEX.read_text(encoding="utf-8")
    payload = json.loads(text[text.index("=") + 1:].strip().rstrip(";"))
    n = payload.get("stockCount") or len(payload.get("reports") or {})
    if not n:
        raise SystemExit("stamp_counts: 종목 수를 읽지 못했습니다.")
    return int(n)


def main() -> int:
    check = "--check" in sys.argv
    want = f"{stock_count():,}"
    html = PAGE.read_text(encoding="utf-8")

    m = PATTERN.search(html)
    if not m:
        # 마크업이 바뀌었는데 이 스크립트만 그대로면 조용히 아무것도 안 하게 된다.
        print("stamp_counts: index.html 에서 lpRepN 을 찾지 못했습니다.", file=sys.stderr)
        return 1

    have = m.group(2).strip()
    if have == want:
        print(f"stamp_counts: 그대로 — AI 리포트 {want}")
        return 0

    if check:
        print(f"stamp_counts: 어긋남 — 페이지 {have} · 실제 {want}", file=sys.stderr)
        return 1

    PAGE.write_text(PATTERN.sub(rf"\g<1>{want}\g<3>", html, count=1), encoding="utf-8")
    print(f"stamp_counts: {have} → {want}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
