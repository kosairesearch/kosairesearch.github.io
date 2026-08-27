#!/usr/bin/env python3
"""로컬 자바스크립트 주소에 내용 해시를 붙인다 — 브라우저가 옛 파일을 쥐고
있는 것을 막는다.

왜 필요한가. 저장소 어디에도 캐시 무효화가 없었다. GitHub Pages 는 정적
파일에 캐시 헤더를 붙여 내보내므로, 파일을 고쳐 올려도 브라우저는 한동안
받아 둔 것을 계속 쓴다.

실제로 그 때문에 시간을 버렸다. auth-hint.js 의 문구를 한 줄로 줄여
배포했는데 화면에는 두 줄이 그대로 나왔다. 코드는 이미 고쳐져 있었고,
브라우저가 옛 파일을 쓰고 있었을 뿐이다. 고친 사람도 본 사람도 '왜 안
바뀌지' 로 한참을 헤맸다.

  <script src="auth-state.js">          → auth-state.js?v=1a2b3c4d
  await import('./auth-hint.js')        → './auth-hint.js?v=5e6f7a8b'

해시는 그 파일의 내용에서 뽑는다. 내용이 바뀌면 주소가 바뀌고, 바뀌지
않으면 그대로다 — 즉 필요할 때만 새로 받는다. 날짜나 판 번호를 손으로
올리는 방식은 올리는 것을 잊는다.

배포 전에 돌린다(idempotent — 여러 번 돌려도 결과가 같다).

  python3 scripts/stamp_assets.py            # 붙이기/갱신
  python3 scripts/stamp_assets.py --check    # 쓰지 않고 검사만
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()[:8]


def stamp(html, hashes):
    """<script src="x.js"> 와 import('./x.js') 두 모양을 모두 갈아 끼운다."""
    n = 0

    def src_sub(m):
        nonlocal n
        name = m.group(2)
        if name not in hashes:
            return m.group(0)                     # 우리 파일이 아니면 손대지 않는다
        n += 1
        return f'{m.group(1)}"{name}?v={hashes[name]}"'

    html = re.sub(r'(\bsrc=)"([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?"', src_sub, html)

    def imp_sub(m):
        nonlocal n
        name = m.group(1)
        if name not in hashes:
            return m.group(0)
        n += 1
        return f"import('./{name}?v={hashes[name]}')"

    html = re.sub(r"import\('\./([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?'\)", imp_sub, html)
    return html, n


def main():
    check = "--check" in sys.argv
    # 저장소 최상단의 .js 만 대상으로 한다. scripts/ 는 파이썬이고,
    # functions/ 는 서버라 브라우저가 받지 않는다.
    hashes = {p.name: digest(p) for p in ROOT.glob("*.js")}
    if not hashes:
        print("  ❌ 대상 자바스크립트를 찾지 못함")
        return 1

    changed = 0
    for page in sorted(ROOT.glob("*.html")):
        orig = page.read_text(encoding="utf-8")
        out, n = stamp(orig, hashes)
        if out != orig:
            changed += 1
            if not check:
                page.write_text(out, encoding="utf-8")
            print(f"  · {page.name:22} {n}곳")

    print(f"\n{'검사만 — ' if check else ''}자바스크립트 {len(hashes)}개 · "
          f"페이지 {changed}개 갱신")
    if check and changed:
        print("  ❌ 해시가 최신이 아니다 — python3 scripts/stamp_assets.py 를 돌릴 것")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
