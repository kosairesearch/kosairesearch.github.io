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
  await import("./settings-panel.js")   → 큰따옴표도 같이 본다
  import { x } from "./consent.js"      → 정적 import 도 같이 본다

해시는 그 파일의 내용에서 뽑는다. 내용이 바뀌면 주소가 바뀌고, 바뀌지
않으면 그대로다 — 즉 필요할 때만 새로 받는다. 날짜나 판 번호를 손으로
올리는 방식은 올리는 것을 잊는다.

세 가지를 놓치고 있었다. 그리고 그 셋이 겹치는 자리가 하필 설정 창이었다.

  · html 만 열어 봤다. .js 가 다른 .js 를 부르는 곳은 아무도 안 봤다
  · import() 의 작은따옴표만 봤다. auth-state.js 는 큰따옴표를 쓴다
  · 정적 import(from "./x.js")는 아예 대상이 아니었다

그래서 settings-panel.js 는 저장소 어디에서도 판본이 붙지 않았다.
auth-state.js 는 판본이 붙어 캐시가 갈렸지만, 그 안에서 부르는 설정
창은 맨 주소라 브라우저가 옛것을 그대로 썼다. 창을 두 칸으로 새로
짜고 배포했는데 화면은 한 줄짜리 옛 창이었다 — 같은 함정에 두 번째로
빠진 것이다(첫 번째는 auth-hint.js 였다).

.js 에 도장을 찍으면 그 파일의 내용이 바뀌고, 내용이 바뀌면 그 파일의
해시도 바뀐다. 그래서 한 번 훑어서는 끝나지 않는다 — 더 바뀌지 않을
때까지 돌린다.

배포 전에 돌린다(idempotent — 여러 번 돌려도 결과가 같다).

  python3 scripts/stamp_assets.py            # 붙이기/갱신
  python3 scripts/stamp_assets.py --check    # 쓰지 않고 검사만
"""
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def digest(text):
    """도장을 찍은 뒤의 내용으로 잰다 — 브라우저가 받아 가는 것이 그것이다."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


_SRC = re.compile(r'(\bsrc=)"([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?"')
_DYN = re.compile(r"""import\(\s*(['"])\./([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?\1\s*\)""")
_FROM = re.compile(r"""(\bfrom\s+)(['"])\./([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?\2""")


def stamp(text, hashes):
    """<script src>, import('./x.js'), from "./x.js" 세 모양을 모두 갈아 끼운다.

    우리 파일이 아니면 손대지 않는다 — 파이어베이스 같은 바깥 주소에
    우리 해시를 붙이면 그 주소는 없는 주소가 된다."""
    n = 0

    def sub(name, make):
        nonlocal n
        if name not in hashes:
            return None
        n += 1
        return make(hashes[name])

    def src_sub(m):
        r = sub(m.group(2), lambda h: f'{m.group(1)}"{m.group(2)}?v={h}"')
        return m.group(0) if r is None else r

    def dyn_sub(m):
        q = m.group(1)
        r = sub(m.group(2), lambda h: f"import({q}./{m.group(2)}?v={h}{q})")
        return m.group(0) if r is None else r

    def from_sub(m):
        q = m.group(2)
        r = sub(m.group(3), lambda h: f"{m.group(1)}{q}./{m.group(3)}?v={h}{q}")
        return m.group(0) if r is None else r

    text = _SRC.sub(src_sub, text)
    text = _DYN.sub(dyn_sub, text)
    text = _FROM.sub(from_sub, text)
    return text, n


def main():
    check = "--check" in sys.argv
    # 저장소 최상단만 본다. scripts/ 는 파이썬이고, functions/ 는 서버라
    # 브라우저가 받지 않는다. staging/ 은 제 것을 따로 갖는다.
    js = sorted(ROOT.glob("*.js"))
    if not js:
        print("  ❌ 대상 자바스크립트를 찾지 못함")
        return 1
    files = js + sorted(ROOT.glob("*.html"))
    orig = {p: p.read_text(encoding="utf-8") for p in files}

    # .js 에 도장을 찍으면 그 파일의 해시가 바뀌고, 그러면 그 파일을 부르는
    # 쪽의 주소도 다시 써야 한다. 더 바뀌지 않을 때까지 돌린다.
    cur = dict(orig)
    for _ in range(10):
        hashes = {p.name: digest(cur[p]) for p in js}
        nxt = {p: stamp(cur[p], hashes)[0] for p in files}
        if nxt == cur:
            break
        cur = nxt
    else:
        print("  ❌ 해시가 멎지 않는다 — 모듈이 서로를 돌아가며 부르는지 볼 것")
        return 1

    changed = [p for p in files if cur[p] != orig[p]]
    for p in changed:
        if not check:
            p.write_text(cur[p], encoding="utf-8")
        print(f"  · {p.name:22} {stamp(orig[p], hashes)[1]}곳")

    print(f"\n{'검사만 — ' if check else ''}자바스크립트 {len(js)}개 · "
          f"파일 {len(changed)}개 갱신")
    if check and changed:
        print("  ❌ 해시가 최신이 아니다 — python3 scripts/stamp_assets.py 를 돌릴 것")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
