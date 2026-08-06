#!/usr/bin/env python3
"""본문에 섞인 한자를 한글로 되돌린다(1회성 보수).

모델이 '전년比', '삼성디스플레이向', '데이터센터發' 같은 신문식 한자 약어를 섞어
썼고, '示사하듯'(시사)·'후退할'(후퇴)처럼 아예 잘못 쓴 곳도 있었다. 읽는 사람이
못 읽는 글자는 그 자체로 결함이다. 생성 쪽 프롬프트에서 한자를 금지했고,
이 스크립트는 이미 저장된 데이터를 고친다.

건드리지 않는 것
  · 한국어 뒤에 괄호로 붙인 한자 병기 — '상저하고(上低下高)' 처럼 한글이 이미
    앞에 있어 읽는 데 지장이 없다.
  · 영어(en) 본문 — 'QQ音速', '天賜材料·Tinci' 처럼 고유명사가 대부분이다.

  python3 scripts/fix_hanja.py            # 검사만(바뀔 내용 출력)
  python3 scripts/fix_hanja.py --write    # 실제 수정
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 한자 → 한글. 긴 것부터 적용해야 '對中' 이 '對'+'中' 으로 갈라지지 않는다.
MAP = {
    "北美": "북미", "南美": "남미", "對美": "대미", "對中": "대중",
    "前夜": "전야", "乖離": "괴리", "激化": "격화", "累積": "누적",
    "大幅": "대폭", "深化": "심화", "消滅": "소멸", "中企": "중소기업",
    "電荷": "전하", "上低下高": "상저하고", "特配": "특배",
    "比": " 대비", "向": " 대상", "社": "사", "發": "발", "前": "전",
    "美": "미국", "中": "중국", "日": "일본", "英": "영국",
    "無": "없음", "新": "신", "舊": "구", "對": "대", "全": "전",
    "非": "비", "現": "현", "株": "주", "外": "외", "産": "산",
    "先": "선", "後": "후", "績": "적", "州": "주", "示": "시",
    "月": "월", "故": "고", "退": "퇴", "約": "약", "展": "전",
    "率": "율", "多": "많음", "益": "익", "未": "미", "鮮": "선",
    "高": "고",   # '高부채' → '고부채', 홀로 쓰이면 아래에서 '높음'
}
# 뜻이 갈리거나 고유명사라 손대지 않는 덩어리(매칭된 한자 덩어리 전체와 비교)
SKIP = {"子", "母", "重水", "深底", "白羊", "業費率", "音速", "眼",
        "天賜材料", "企業價値", "提高", "万"}

HAN = re.compile(r"[一-鿿]+")
_KEYS = sorted(MAP, key=len, reverse=True)

# 한자는 대개 받침 없는 음(무·다·고)으로 읽혀 '無가'처럼 적혔는데, 한글로 풀면
# 받침이 생겨('없음') 조사를 바꿔야 한다.
JOSA = {"가": "이", "를": "을", "로": "으로", "는": "은", "와": "과"}


def jong(ch):
    """한글 음절에 받침이 있나."""
    return "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 != 0


def convert(s):
    """한 문자열의 한자를 한글로. 바꾼 (원문, 결과) 목록도 함께 돌려준다."""
    out, changes, i = [], [], 0
    for m in HAN.finditer(s):
        a, b = m.start(), m.end()
        chunk = m.group()
        # 한자 병기 '(漢字)' 는 앞에 한글 풀이가 있으므로 그대로 둔다
        if s[a - 1:a] == "(" and s[b:b + 1] == ")":
            continue
        if chunk in SKIP:
            continue
        rep = chunk
        for k in _KEYS:
            rep = rep.replace(k, MAP[k])
        if HAN.search(rep):          # 매핑에 없는 글자가 남으면 통째로 건너뛴다
            continue
        # 홀로 쓰인 '高'(민감도 高)는 '고'가 아니라 '높음'
        if chunk == "高" and not re.match(r"[가-힣]", s[b:b + 1]):
            rep = "높음"
        # '舊우리산업'·'故최한순'·'全공정'은 붙여 쓰면 읽기 어려워 띄어 준다.
        # '新시장'·'前단'은 '신시장'·'전단'이 굳어진 말이라 붙여 둔다.
        if chunk in ("舊", "故", "全") and re.match(r"[가-힣A-Za-z]", s[b:b + 1]):
            rep += " "
        # 받침이 생기면 뒤 조사도 바뀐다: '無가' → '없음이', '無로' → '없음으로'
        j2 = b
        if rep and jong(rep[-1]) and s[b:b + 1] in JOSA:
            out.append(s[i:a]); out.append(rep + JOSA[s[b]]); i = j2 = b + 1
        else:
            out.append(s[i:a]); out.append(rep); i = b
        changes.append((s[max(0, a - 16):j2 + 14], rep))
    if not changes:
        return s, []
    out.append(s[i:])
    res = re.sub(r"[ ]{2,}", " ", "".join(out))
    res = re.sub(r"\(\s+", "(", res)
    return res, changes


def walk(o, ko=False):
    """dict/list 를 훑어 'ko' 키 아래 문자열만 고친다. (결과, 변경목록)"""
    if isinstance(o, dict):
        out, ch = {}, []
        for k, v in o.items():
            w, c = walk(v, ko=(k == "ko"))
            out[k] = w; ch += c
        return out, ch
    if isinstance(o, list):
        out, ch = [], []
        for v in o:
            w, c = walk(v, ko)
            out.append(w); ch += c
        return out, ch
    if isinstance(o, str) and ko:
        return convert(o)
    return o, []


def fix(path, write, head=0):
    """head>0 이면 'window.KOS_… = {…};' 형태(sectors.js), 아니면 순수 JSON 파일."""
    raw = path.read_text(encoding="utf-8")
    body = raw[head:]
    if head:
        i, j = body.find("{"), body.rfind("}")
        pre, tail, indent = body[:i], body[j + 1:], 2
        data = json.loads(body[i:j + 1])
    else:
        pre, tail, indent = "", "", None
        data = json.loads(body)
    if not isinstance(data, dict):          # reports_v2/index.json 같은 티커 배열
        return []
    fixed, ch = walk(data)
    if ch and write:
        path.write_text(raw[:head] + pre
                        + json.dumps(fixed, ensure_ascii=False, indent=indent) + tail,
                        encoding="utf-8")
    return ch


if __name__ == "__main__":
    write = "--write" in sys.argv
    total, files, samples = 0, 0, []
    js = ROOT / "data" / "sectors.js"
    ch = fix(js, write, js.read_text(encoding="utf-8").find("{"))
    if ch:
        files += 1; total += len(ch); samples += [("sectors.js", c) for c in ch]
    for sub in ("reports_v2", "reports"):
        d = ROOT / "data" / sub
        for f in sorted(d.glob("*.json")) if d.exists() else []:
            ch = fix(f, write)
            if ch:
                files += 1; total += len(ch); samples += [(f.stem, c) for c in ch]
    for tk, (ctx, rep) in samples:
        print(f"  [{tk}] …{ctx}… → {rep!r}")
    print(("✅ 수정 " if write else "🔍 검사(--write 로 실제 수정) ")
          + f"· 파일 {files}개 · {total}곳")
