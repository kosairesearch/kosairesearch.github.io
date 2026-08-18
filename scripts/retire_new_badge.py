#!/usr/bin/env python3
"""헤더 '모닝브리핑' 옆의 new 배지를 뗀다 — 첫 발행 7일 뒤에 자동으로.

배지는 새로 생긴 메뉴를 알리려고 붙인 것이라 수명이 있다. 한 달 뒤에도
'new' 가 붙어 있으면 오히려 관리가 안 되는 사이트로 보인다. 그런데 사람이
날짜를 기억했다가 떼는 건 잘 안 되는 종류의 일이라 코드로 옮긴다.

제거일은 하드코딩하지 않는다. data/briefs/*.json 중 meta.publishedAt 이 있는
가장 이른 것 — 즉 실제로 화면에 나간 첫 브리핑 — 의 날짜에 7일을 더한다.
publishedAt 은 render_brief 가 페이지를 쓸 때만 남기므로, 품질 확인용으로
만들었지만 발행하지 않은 브리핑은 여기 걸리지 않는다.

몇 번을 돌려도 결과가 같다. 이미 뗐으면 아무것도 하지 않는다.

    python3 scripts/retire_new_badge.py --check   # 언제 떼는지 보기만
    python3 scripts/retire_new_badge.py           # 때가 됐으면 뗀다
    python3 scripts/retire_new_badge.py --force   # 날짜 무시하고 지금 뗀다
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "data" / "briefs"
KST = datetime.timezone(datetime.timedelta(hours=9))

DAYS = 7

# 배지 마크업과 CSS. 붙일 때 넣은 것과 짝이 맞아야 한다 — 한쪽만 지우면
# 화면에는 안 보이는데 규칙만 남거나, 규칙 없는 <sup> 이 맨몸으로 보인다.
BADGE = re.compile(r'<sup class="nav-new">new</sup>')
CSS = re.compile(
    r'\n/\* 새로 생긴 메뉴 표시\..*?'
    r'\.mobile-menu \.nav-new\{[^}]*\}\n',
    re.S)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def first_published():
    """실제로 화면에 나간 첫 브리핑의 날짜. 없으면 None."""
    dates = []
    for f in sorted(BRIEFS.glob("*.json")):
        if not re.fullmatch(r"\d{4}-\d\d-\d\d", f.stem):
            continue
        try:
            at = (json.loads(f.read_text(encoding="utf-8")).get("meta") or {}).get("publishedAt")
        except Exception:
            continue
        if at:
            dates.append(datetime.date.fromisoformat(at[:10]))
    return min(dates) if dates else None


def pages():
    return sorted(p for p in ROOT.glob("*.html") if p.is_file())


def retire(paths):
    """(고친 파일 수, 남은 배지 수)."""
    changed = 0
    for p in paths:
        s = p.read_text(encoding="utf-8")
        out, n_badge = BADGE.subn("", s)
        out, n_css = CSS.subn("\n", out)
        if n_badge or n_css:
            p.write_text(out, encoding="utf-8")
            changed += 1
            log(f"  · {p.name}  배지 {n_badge}곳 · CSS {n_css}블록")
    left = sum(len(BADGE.findall(p.read_text(encoding='utf-8'))) for p in paths)
    return changed, left


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="언제 떼는지 보기만 한다")
    ap.add_argument("--force", action="store_true", help="날짜와 무관하게 지금 뗀다")
    a = ap.parse_args()

    paths = pages()
    have = sum(len(BADGE.findall(p.read_text(encoding="utf-8"))) for p in paths)
    if not have:
        log("· 배지가 이미 없다 — 할 일 없음")
        return 0

    today = datetime.datetime.now(KST).date()
    first = first_published()
    if not first:
        # 아직 한 번도 발행 안 됐다. 배지는 그대로 둔다 — 셀 기준이 없다.
        log("· 발행된 브리핑이 없어 제거일을 정할 수 없다 — 배지를 그대로 둔다")
        return 0
    due = first + datetime.timedelta(days=DAYS)

    log(f"· 첫 발행 {first} · 제거 예정 {due} · 오늘 {today} · 배지 {have}곳")
    if not a.force and today < due:
        log(f"· 아직 {(due - today).days}일 남았다 — 그대로 둔다")
        return 0
    if a.check:
        log("· --check 라 쓰지 않는다")
        return 0

    changed, left = retire(paths)
    log(f"✅ {changed}개 파일에서 뗐다 · 남은 배지 {left}곳")
    return 0 if left == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
