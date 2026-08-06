#!/usr/bin/env python3
"""생성물에 박힌 문장 중간 개행 제거(1회성 보수).

원인은 generate_reports.extract_text 가 응답 text 블록을 "\\n" 으로 이어 붙인 것.
웹 검색을 쓰면 인용이 붙는 구간마다 블록이 쪼개지고 그 경계가 문장 한가운데라,
저장된 문장이 '…주목\\n하고 있다' 처럼 끊겼다. 원인은 그쪽에서 고쳤고(구분자 제거),
이 스크립트는 이미 만들어져 배포된 데이터를 되돌린다.

빈 줄(\\n\\n)은 글쓴이가 의도한 문단 구분이므로 보존한다.

파일은 다시 직렬화하지 않고 원문 텍스트에서 이스케이프된 개행만 고친다.
생성기마다 indent 가 달라(compact / indent=1) 재직렬화하면 내용과 무관한
줄바꿈 차이로 파일 전체가 diff 에 잡히기 때문이다.

  python3 scripts/fix_stray_newlines.py            # 검사만
  python3 scripts/fix_stray_newlines.py --write    # 실제 수정
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARA = "\x00PARA\x00"          # 문단 구분 자리표시자

# JSON 원문에서의 개행은 역슬래시+n 두 글자다. 앞에 역슬래시가 또 있으면
# 이스케이프된 역슬래시이므로 건드리지 않는다.
NL = r"(?<!\\)\\n"


def _join(a, b, gap):
    """개행 한 개를 무엇으로 바꿀지. 붙여 쓰던 자리는 붙이고, 띄던 자리는 띄운다."""
    if " " in gap or "\t" in gap:
        return a + " " + b                      # 원래 공백이 있던 자리
    if re.match(r"[0-9A-Za-z]", a) and re.match(r"[0-9A-Za-z]", b):
        return a + " " + b                      # 영문 단어끼리는 공백이 필요
    return a + b                                # 한글·문장부호는 그대로 붙인다


def clean(t):
    """파싱된 문자열 기준의 정답. 원문 수정 결과를 이걸로 검증한다."""
    if "\n" not in t:
        return t
    t = re.sub(r"\n[ \t]*\n+", PARA, t)
    t = re.sub(r"(.)([ \t]*)\n([ \t]*)(.)",
               lambda m: _join(m.group(1), m.group(4), m.group(2) + m.group(3)), t)
    t = t.replace("\n", "")
    return t.replace(PARA, "\n\n").strip()


def clean_raw(raw):
    """JSON 원문 문자열. 이스케이프된 개행만 손대고 나머지는 한 글자도 안 바꾼다."""
    if "\\n" not in raw:
        return raw
    out = re.sub(NL + r"[ ]*" + NL + r"(?:[ ]*" + NL + r")*", PARA, raw)
    out = re.sub(r"(.)([ ]*)" + NL + r"([ ]*)(.)",
                 lambda m: _join(m.group(1), m.group(4), m.group(2) + m.group(3)), out)
    out = re.sub(NL, "", out)
    return out.replace(PARA, "\\n\\n")


def walk(o):
    """dict/list 안 모든 문자열에 clean() 을 적용한 사본. (바뀐 개수, 값)"""
    if isinstance(o, dict):
        n, out = 0, {}
        for k, v in o.items():
            c, out[k] = walk(v)
            n += c
        return n, out
    if isinstance(o, list):
        n, out = 0, []
        for v in o:
            c, w = walk(v)
            n += c
            out.append(w)
        return n, out
    if isinstance(o, str):
        c = clean(o)
        return (1 if c != o else 0), c
    return 0, o


def fix_file(path, write, head_len=0):
    """원문을 고치고, 결과가 clean() 기준과 정확히 같은지 확인한 뒤 저장한다."""
    raw = path.read_text(encoding="utf-8")
    body = raw[head_len:]
    fixed = clean_raw(body)
    if fixed == body:
        return 0
    i, j = body.find("{"), body.rfind("}")
    before = json.loads(body[i:j + 1])
    n, want = walk(before)
    i2, j2 = fixed.find("{"), fixed.rfind("}")
    got = json.loads(fixed[i2:j2 + 1])          # 깨진 JSON 을 쓰지 않도록 파싱 검증
    if got != want:
        raise SystemExit(f"❌ {path.name}: 원문 수정 결과가 기준과 다름 — 저장 중단")
    if write:
        path.write_text(raw[:head_len] + fixed, encoding="utf-8")
    return n


if __name__ == "__main__":
    write = "--write" in sys.argv
    total = 0

    js = ROOT / "data" / "sectors.js"
    head = js.read_text(encoding="utf-8").find("{")
    n = fix_file(js, write, head)
    total += n
    print(f"{js.relative_to(ROOT)}: 문자열 {n}개")

    for sub in ("reports_v2", "reports"):
        d = ROOT / "data" / sub
        if not d.exists():
            continue
        cnt = files = 0
        for f in sorted(d.glob("*.json")):
            n = fix_file(f, write)
            if n:
                cnt += n
                files += 1
        total += cnt
        print(f"{d.relative_to(ROOT)}: 파일 {files}개 · 문자열 {cnt}개")

    print(("✅ 수정 완료 · " if write else "🔍 검사만 함(--write 로 실제 수정) · ") + f"총 {total}개")
