#!/usr/bin/env python3
"""리포트 본문의 금액 표기를 한 가지로 맞춘다.

무엇이 문제였나
---------------
본문은 LLM 이 쓴다. 표기 규칙을 정해 주지 않으면 같은 파이프라인이
매번 다르게 쓴다. 실제로 2,564개를 세어 보니 이랬다.

    만 단위   붙임 9,074 (72%)  ·  띄움 3,458 (28%)
    '원' 앞   붙임 101,534 (98%)  ·  띄움 2,093 (2%)

한 리포트 안에서 두 방식이 섞인 것도 34개 있었다.
같은 문서에 "3조 3,168억원" 과 "2조6020억원" 이 함께 나온다.

무엇이 맞나
-----------
한글 맞춤법 **제44항** — 수를 적을 적에는 '만(萬)' 단위로 띄어 쓴다.
    십이억 삼천사백오십육만 칠천팔백구십팔 / 12억 3456만 7898
단정형이고 예외가 없다. "79조3,187억" 은 틀렸다. "79조 3,187억" 이다.

한글 맞춤법 **제43항** — 단위를 나타내는 명사는 띄어 쓴다. 다만,
순서를 나타내거나 *숫자와 어울리어 쓰이는 경우에는 붙여 쓸 수 있다*
(80원 · 10개 · 두시 삼십분 오초). '원' 은 단위 명사이므로 원칙은
"3,187억 원" 이지만 붙여 쓰는 것도 허용된다. 언론은 거의 다 붙여 쓴다.

그래서 이렇게 정한다
--------------------
    79조 3,187억원        ← 만 단위는 띄우고, '원' 은 붙인다

쉼표는 그대로 둔다. 규범이 금지하지 않고, 없으면 읽기 나쁘다.

왜 숫자가 앞에 와야만 고치는가
------------------------------
'조·억·만' 은 평범한 한국어 음절이기도 하다. 앞을 보지 않고 고치면
멀쩡한 글이 망가진다. 실제 본문에서 걸린 것들이다.

    "다만 원가 절감과…"   → '만'+' 원'  으로 읽혀 "다만원가" 가 된다 (91군데)
    "제조1동을 준공했고"   → '조'+숫자   로 읽혀 "제조 1동" 이 된다 (6군데)

그래서 두 규칙 모두 **바로 앞이 숫자(또는 자릿쉼표)일 때만** 손댄다.
이 조건을 넣으면 위 97군데가 전부 빠지고, 남는 것은 전부 금액이다.
("20억 원가량" 은 '원'+'가량' 이라 붙이는 것이 맞다 — 규칙에 걸려도 된다.)

    python3 scripts/number_spacing.py           # 세어만 본다
    python3 scripts/number_spacing.py --apply   # 고쳐 쓴다
    python3 scripts/number_spacing.py --apply data/reports_v2
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = ("data/reports_v2", "data/reports")

# 본문이 아닌 것 — 숫자 덩어리와 URL 이라 손댈 이유가 없다.
SKIP_KEYS = ("quant", "sources")

# 가로 공백만 — 줄바꿈을 먹으면 문단이 붙는다.
_SP = r"[^\S\r\n]"

# 제44항 — 만 단위로 띄어 쓴다.  79조3,187억 → 79조 3,187억
UNIT_GAP = re.compile(r"(?<=[\d,])([조억만])(?=\d)")
# 제43항 단서 — 숫자와 어울린 '원' 은 붙여 쓴다.  3,187억 원 → 3,187억원
WON_JOIN = re.compile(r"(?<=[\d,])([조억만])" + _SP + r"+원")


def _bare(s):
    """공백을 모두 걷어낸 알맹이 — 고치기 전후가 같아야 한다."""
    return re.sub(r"\s+", "", s)


def normalize(text):
    """금액 표기를 '79조 3,187억원' 꼴로 맞춘다. 여러 번 돌려도 결과가 같다."""
    if not text:
        return text
    out = UNIT_GAP.sub(r"\1 ", text)
    out = WON_JOIN.sub(r"\1원", out)
    # 이 함수가 할 수 있는 일은 '가로 공백을 넣거나 빼는 것' 뿐이다.
    # 글자가 하나라도 바뀌면 규칙이 잘못 걸린 것이므로 쓰기 전에 멈춘다.
    if _bare(out) != _bare(text):
        raise AssertionError(
            "공백 말고 글자가 바뀌었다\n  전: %r\n  후: %r" % (text, out))
    return out


def normalize_report(obj, _key=None):
    """리포트 한 건의 한국어 본문을 모두 손본다. (바뀐 곳 수, 객체) 를 준다."""
    n = 0
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in SKIP_KEYS:
                continue
            if k == "ko" and isinstance(v, str):
                fixed = normalize(v)
                if fixed != v:
                    # 바뀐 '군데' 수 — 문자열 하나에 여러 군데일 수 있다
                    n += len(UNIT_GAP.findall(v)) + len(WON_JOIN.findall(v))
                    obj[k] = fixed
            else:
                c, obj[k] = normalize_report(v, k)
                n += c
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            c, obj[i] = normalize_report(v, _key)
            n += c
    return n, obj


# 파일마다 저장 형식이 다르다. reports_v2 만 해도 indent=1 로 쓴 것과
# 한 줄로 쓴 것이 섞여 있다(서로 다른 스크립트가 써 넣었다). 형식을 하나로
# 통일해 버리면 글자는 그대로인데 5,248개가 통째로 다시 쓰인 것처럼 보인다.
# 그래서 원본을 그대로 되살리는 형식을 찾아서, 그 형식으로만 쓴다.
_DUMP_STYLES = (
    dict(ensure_ascii=False, indent=1),
    dict(ensure_ascii=False, separators=(",", ":")),
    dict(ensure_ascii=False),
    dict(ensure_ascii=False, indent=2),
)


def dump_like(original, obj):
    """원본과 같은 형식으로 직렬화한다. 형식을 못 찾으면 None."""
    for kw in _DUMP_STYLES:
        for tail in ("", "\n"):
            try:
                if json.dumps(json.loads(original), **kw) + tail == original:
                    return json.dumps(obj, **kw) + tail
            except Exception:
                pass
    return None


def run(dirs, apply):
    total_files = total_hits = touched = 0
    skipped = []
    for d in dirs:
        p = ROOT / d
        if not p.is_dir():
            print(f"  {d}: 폴더 없음 — 건너뜀")
            continue
        files = sorted(p.glob("*.json"))
        hits = tf = 0
        for f in files:
            try:
                raw = f.read_text(encoding="utf-8")
                rep = json.loads(raw)
            except Exception as e:
                print(f"  ⚠️ {f.name} 읽기 실패: {e}")
                continue
            n, rep = normalize_report(rep)
            if n:
                hits += n
                tf += 1
                if apply:
                    out = dump_like(raw, rep)
                    if out is None:
                        print(f"  ⚠️ {f.name} 저장 형식을 못 찾았다 — 건너뜀")
                        skipped.append(f.name)
                        continue
                    f.write_text(out, encoding="utf-8")
        print(f"  {d}: {len(files):,}개 중 {tf:,}개 · {hits:,}군데")
        total_files += len(files)
        total_hits += hits
        touched += tf
    verb = "고쳤다" if apply else "고칠 곳"
    print(f"합계 {total_files:,}개 중 {touched:,}개 · {total_hits:,}군데 {verb}")
    if skipped:
        print(f"⚠️ 저장 형식을 못 찾아 건너뛴 파일 {len(skipped)}개: "
              + ", ".join(skipped[:10]))
    return total_hits


# 업종 분석은 JSON 이 아니라 "window.KOS_SECTORS = {…};" 꼴의 자바스크립트다.
# 앞뒤를 떼고 가운데만 같은 규칙으로 손본 뒤 원래 형식 그대로 되돌린다.
SECTORS = "data/sectors.js"
_SECTORS_HEAD = "window.KOS_SECTORS = "


def run_sectors(apply):
    f = ROOT / SECTORS
    if not f.is_file():
        print(f"  {SECTORS}: 파일 없음 — 건너뜀")
        return 0
    raw = f.read_text(encoding="utf-8")
    head, sep, body = raw.partition(_SECTORS_HEAD)
    tail = raw[len(raw.rstrip()):]
    payload = body.rstrip()
    if not sep or not payload.endswith(";"):
        print(f"  ⚠️ {SECTORS}: 모양이 예상과 다르다 — 건너뜀")
        return 0
    obj = json.loads(payload[:-1])
    n, obj = normalize_report(obj)
    if n and apply:
        out = head + sep + json.dumps(obj, ensure_ascii=False, indent=2) + ";" + tail
        # 글자가 아니라 공백만 바뀌었는지 파일 단위로도 확인한다
        if _bare(out) != _bare(raw):
            print(f"  ⚠️ {SECTORS}: 공백 말고 다른 것이 바뀌려 한다 — 건너뜀")
            return 0
        f.write_text(out, encoding="utf-8")
    print(f"  {SECTORS}: {n:,}군데")
    return n


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--apply"]
    apply = "--apply" in sys.argv
    total = run(args or DEFAULT_DIRS, apply)
    if not args:
        total += run_sectors(apply)
        print(f"업종 분석까지 합쳐 {total:,}군데")
