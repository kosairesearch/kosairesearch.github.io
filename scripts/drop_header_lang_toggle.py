#!/usr/bin/env python3
"""헤더의 KO/EN 토글을 걷어낸다. 17개 페이지를 한 번에 고친다.

왜 스크립트인가. i18n 엔진이 페이지마다 통째로 복사돼 있어서 같은
buildToggle 이 17벌 있다. 손으로 고치면 한두 장이 빠지고, 그러면 어떤
화면에만 토글이 남는다.

언어 전환은 설정 화면에 있다(settings-panel.js 의 '언어' 줄). 헤더에서
빼도 전환 수단이 사라지지 않는다.

  python3 scripts/drop_header_lang_toggle.py            # 고치기
  python3 scripts/drop_header_lang_toggle.py --check    # 쓰지 않고 검사만
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# buildToggle 은 지우지 않고 속을 비운다. init() 이 부르고 있고, 호출 자리를
# 같이 건드리면 페이지마다 조금씩 다른 init 을 17벌 손봐야 한다.
#
# updateToggle 은 그대로 둔다 — 엘리먼트가 없으면 스스로 빠져나가고(첫 줄의
# `if(!wrap) return;`), 언젠가 토글을 되살릴 때 짝이 맞아 있는 편이 낫다.
NEW = '''  /* ---- toggle UI ---- */
  /* 헤더의 KO/EN 토글은 걷어냈다. 언어는 설정 화면에서 바꾼다
     (settings-panel.js 의 '언어' 줄). 같은 것을 두 곳에 두면 헤더가
     붐비고, 테마 토글과 나란히 있어 무엇이 무엇인지 한눈에 안 잡혔다.

     함수는 남겨 둔다 — init() 이 부르고 있어서, 지우려면 페이지마다 조금씩
     다른 init 을 17벌 손봐야 한다. updateToggle 도 그대로다. 엘리먼트가
     없으면 스스로 빠져나간다. */
  function buildToggle(){ return; }
'''

# `/* ---- toggle UI ---- */` 부터 `function updateToggle` 직전까지.
PAT = re.compile(
    r"  /\* ---- toggle UI ---- \*/\n"
    r"  function buildToggle\(\)\{.*?\n  \}\n"
    r"(?=  function updateToggle)",
    re.S)


def patch(path, check=False):
    s = orig = path.read_text(encoding="utf-8")

    if "function buildToggle(){ return; }" in s:
        return False, "이미 걷어냄"

    s, n = PAT.subn(NEW, s)
    if n != 1:
        return None, f"토글 블록을 찾지 못함(매칭 {n}건)"

    # 남은 흔적이 없는지 확인한다. 스타일 주입도 buildToggle 안에 있었으므로
    # 통째로 사라져야 한다.
    for token in ("langToggle", "insertBefore(wrap, theme)"):
        if token in s.replace("#langToggle", ""):   # updateToggle 의 조회는 남는다
            pass
    if "insertBefore(wrap, theme)" in s:
        return None, "삽입 코드가 남아 있음"

    if not check:
        path.write_text(s, encoding="utf-8")
    return (s != orig), "걷어냄"


def main():
    check = "--check" in sys.argv
    pages = sorted(p for p in ROOT.glob("*.html")
                   if "buildToggle" in p.read_text(encoding="utf-8"))
    changed = failed = 0
    for p in pages:
        did, note = patch(p, check)
        if did is None:
            print(f"  ❌ {p.name:22} {note}")
            failed += 1
            continue
        if did:
            changed += 1
        print(f"  {'·' if did else ' '} {p.name:22} {note}")
    print(f"\n{'검사만 — ' if check else ''}{len(pages)}개 중 {changed}개 변경"
          f"{f' · 실패 {failed}' if failed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
