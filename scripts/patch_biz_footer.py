#!/usr/bin/env python3
"""사업자 정보를 전 페이지 푸터에 넣는다 — 여기가 유일한 원본이다.

왜 스크립트로 두나. 사업자 정보는 페이지마다 같은 내용이 들어가야 하는데,
푸터가 있는 페이지가 17개다. 손으로 넣으면 주소나 연락처가 바뀔 때 한두
페이지가 빠지고, 그러면 '사이트마다 사업자 정보가 다른' 상태가 된다.
카카오 비즈니스 정보 심사에서 가장 많은 반려 사유가 바로 그 불일치다.

아래 BIZ 만 고치고 이 파일을 다시 돌리면 전 페이지가 같이 갱신된다.

  python3 scripts/patch_biz_footer.py            # 넣기/갱신
  python3 scripts/patch_biz_footer.py --check    # 쓰지 않고 검사만
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 사업자 정보 (원본) ────────────────────────────────────────────────
#   사업자등록증과 글자 하나까지 같아야 한다. 카카오 비즈 앱에 등록하는
#   회사명·사업자번호도 여기와 같아야 심사를 통과한다.
BIZ = [
    ("상호", "코사이", "KOSAI"),
    ("대표", "임범준", "Beomjun Lim"),
    ("사업자등록번호", "380-25-02019", None),
    ("주소", "서울시 양천구 목동동로12길 50, 동성빌딩 4층 459호",
     "#459, 4F Dongseong Bldg., 50 Mokdongdong-ro 12-gil, Yangcheon-gu, Seoul, Republic of Korea"),
    ("전자우편", "hello@kosai.kr", None),
]
# 라벨 번역
LABEL_EN = {
    "상호": "Company", "대표": "CEO", "사업자등록번호": "Business Reg. No.",
    "주소": "Address", "전자우편": "Email",
}
# 통신판매업 신고번호와 대표전화는 아직 없다. 실사이트에 결제를 붙이는
# 시점에 전자상거래법상 필수가 되므로 그때 위 BIZ 에 추가한다.

MARK_START = "<!-- BIZ:START · scripts/patch_biz_footer.py 가 넣는다 -->"
MARK_END = "<!-- BIZ:END -->"

CSS_BOX = (".biz{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:18px;padding-top:16px;"
           "border-top:1px solid var(--border-2);font:500 12px/1.7 var(--font-sans);"
           "color:var(--fg-3)}\n")
CSS_B = ".biz b{font-weight:600;color:var(--fg-2)}\n"


def block(indent):
    rows = "".join(f'{indent}  <span>{label} <b>{ko}</b></span>\n' for label, ko, _ in BIZ)
    return (f'{indent}{MARK_START}\n'
            f'{indent}<div class="biz">\n{rows}{indent}</div>\n'
            f'{indent}{MARK_END}\n')


def dict_entries():
    pairs = [(k, v) for k, v in LABEL_EN.items()]
    pairs += [(ko, en) for _, ko, en in BIZ if en]
    return "".join(f'  "{k}":"{v}",\n' for k, v in pairs)


def patch(path, check=False):
    s = orig = path.read_text(encoding="utf-8")
    notes = []

    # ① 마크업 — foot-bottom 바로 앞에 넣는다(면책 조항 아래·저작권 위).
    #    disclaimer 는 페이지마다 형태가 달라(한 줄·여러 줄·JS 로 채우는 빈 div)
    #    앵커로 못 쓴다. foot-bottom 은 17개 페이지가 모두 같은 모양이다.
    m = re.search(r'^([ \t]*)<div class="foot-bottom"', s, re.M)
    if not m:
        return None, ["foot-bottom 을 못 찾음"]
    indent = m.group(1)
    new_block = block(indent)
    if MARK_START in s:
        s = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n",
                   new_block, s, flags=re.S)
        notes.append("마크업 갱신")
    else:
        s = s[:m.start()] + new_block + s[m.start():]
        notes.append("마크업 추가")

    # ② CSS — 이미 있는 규칙은 다시 넣지 않는다. 어떤 페이지는 .biz b 만
    #    미리 갖고 있어서, 통째로 넣으면 같은 선언이 두 번 생긴다.
    add = ""
    if ".biz{" not in s:
        add += CSS_BOX
    if ".biz b{" not in s:
        add += CSS_B
    if add:
        s = re.sub(r"^([ \t]*)\.foot-bottom\{", add + r"\1.foot-bottom{", s, count=1, flags=re.M)
        notes.append("CSS 추가")

    # ③ 영문 사전 — 첫 register({ 바로 뒤에 넣는다. 이미 있으면 통째로 갈아끼운다.
    entries = dict_entries()
    tag_s, tag_e = "  /* BIZ:I18N:START */\n", "  /* BIZ:I18N:END */\n"
    if tag_s in s:
        s = re.sub(re.escape(tag_s) + r".*?" + re.escape(tag_e), tag_s + entries + tag_e,
                   s, flags=re.S)
        notes.append("사전 갱신")
    else:
        m2 = re.search(r"KOSi18n\.register\(\{\s*\n", s)
        if m2:
            s = s[:m2.end()] + tag_s + entries + tag_e + s[m2.end():]
            notes.append("사전 추가")
        else:
            notes.append("⚠️ register({ 를 못 찾아 사전은 건너뜀")

    if s != orig and not check:
        path.write_text(s, encoding="utf-8")
    return (s != orig), notes


def main():
    check = "--check" in sys.argv
    pages = sorted(p for p in ROOT.glob("*.html")
                   if 'class="foot-bottom"' in p.read_text(encoding="utf-8"))
    changed = 0
    for p in pages:
        did, notes = patch(p, check)
        if did is None:
            print(f"  ❌ {p.name}: {notes[0]}")
            continue
        if did:
            changed += 1
        print(f"  {'·' if did else ' '} {p.name:22} {' / '.join(notes)}")
    print(f"\n{'검사만 — ' if check else ''}푸터 {len(pages)}개 중 {changed}개 갱신")
    return 0


if __name__ == "__main__":
    sys.exit(main())
