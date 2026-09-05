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

실사이트와 스테이징을 각각 제 폴더 안에서 본다. 같은 이름의 파일을 두 곳이
각자 갖고 있으므로 한 자루에 담으면 한쪽 해시가 다른 쪽 주소에 붙는다.

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
# import "./paywall.js";  — 가져올 이름 없이 실행만 시키는 모양
_BARE = re.compile(r"""(\bimport\s+)(['"])\./([A-Za-z0-9_-]+\.js)(?:\?v=[0-9a-f]+)?\2""")
# 도장이 안 붙은 채로 남은 우리 모듈 주소를 찾는 그물. 규칙이 어떤 모양을
# 놓치면 여기서만 걸린다 — 맨 주소는 '낡은 해시' 가 아니라 '해시 없음' 이라
# 해시를 맞춰 보는 것으로는 영영 안 걸린다(settings-panel.js 가 그랬다).
_ANY = re.compile(r"""["'`](?:\./)?([A-Za-z0-9_-]+\.js)(\?v=[0-9a-f]+)?["'`]""")


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

    def bare_sub(m):
        q = m.group(2)
        r = sub(m.group(3), lambda h: f"{m.group(1)}{q}./{m.group(3)}?v={h}{q}")
        return m.group(0) if r is None else r

    text = _SRC.sub(src_sub, text)
    text = _DYN.sub(dyn_sub, text)
    text = _FROM.sub(from_sub, text)
    text = _BARE.sub(bare_sub, text)
    return text, n


def bare_refs(text, names):
    """도장이 안 붙은 채 남은 우리 모듈 주소. 따옴표 세 가지를 다 본다 —
    백틱으로 쓴 주소를 규칙이 못 보는 일이 실제로 있었다."""
    return [m.group(0) for m in _ANY.finditer(text)
            if m.group(1) in names and not m.group(2)]


def one(base):
    """한 폴더 안에서 서로를 부르는 것만 본다.

    실사이트와 스테이징은 같은 이름의 파일을 각자 갖고 있고, 페이지도 제 폴더
    안의 것을 부른다. 두 벌을 한 자루에 담으면 한쪽 해시가 다른 쪽 주소에
    붙는다. 데이터(../data/*.js)는 대상이 아니다 — 리포트가 새로 만들어질
    때마다 내용이 바뀌므로, 도장을 찍으면 종목 하나가 갱신될 때마다 모든
    페이지가 같이 커밋된다.

    돌려주는 값: (자바스크립트 수, 바뀐 파일 목록, 마지막 해시) · 실패는 None"""
    js = sorted(base.glob("*.js"))
    if not js:
        return None
    files = js + sorted(base.glob("*.html"))
    orig = {p: p.read_text(encoding="utf-8") for p in files}

    # .js 에 도장을 찍으면 그 파일의 해시가 바뀌고, 그러면 그 파일을 부르는
    # 쪽의 주소도 다시 써야 한다. 더 바뀌지 않을 때까지 돌린다.
    cur = dict(orig)
    hashes = {}
    for _ in range(10):
        hashes = {p.name: digest(cur[p]) for p in js}
        nxt = {p: stamp(cur[p], hashes)[0] for p in files}
        if nxt == cur:
            break
        cur = nxt
    else:
        print(f"  ❌ {base.name}: 해시가 멎지 않는다 — 모듈이 서로를 돌아가며 부르는지 볼 것")
        return None

    names = {p.name for p in js}
    left = [(p, r) for p in files for r in bare_refs(cur[p], names)]
    return js, [(p, cur[p], stamp(orig[p], hashes)[1]) for p in files if cur[p] != orig[p]], left


def main():
    check = "--check" in sys.argv
    # 저장소 최상단과 스테이징. scripts/ 는 파이썬이고, functions/ 는 서버라
    # 브라우저가 받지 않는다.
    bases = [ROOT, ROOT / "staging"]
    total_js = total_changed = 0
    leftover = []
    for base in bases:
        if not base.is_dir():
            continue
        got = one(base)
        if got is None:
            return 1
        js, changed, left = got
        total_js += len(js)
        total_changed += len(changed)
        for path, text, n in changed:
            if not check:
                path.write_text(text, encoding="utf-8")
            rel = path.relative_to(ROOT)
            print(f"  · {str(rel):32} {n}곳")
        for path, ref in left:
            leftover.append(f"{path.relative_to(ROOT)}  {ref}")

    print(f"\n{'검사만 — ' if check else ''}자바스크립트 {total_js}개 · "
          f"파일 {total_changed}개 갱신")
    if leftover:
        print("  ❌ 도장이 안 붙은 주소가 남았다 — 위 규칙이 이 모양을 못 본다:")
        for x in leftover:
            print("     " + x)
        return 1
    if check and total_changed:
        print("  ❌ 해시가 최신이 아니다 — python3 scripts/stamp_assets.py 를 돌릴 것")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
