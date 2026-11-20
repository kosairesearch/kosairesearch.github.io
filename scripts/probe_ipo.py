#!/usr/bin/env python3
"""(임시 · 작업 가지에서만) scripts/ipo_filing.collect 를 실제 공시로 돌려 작성 재료 블록을 찍는다(돈 안 듦 · 저장 · 커밋 없음).

실행 기록은 공개다 — 공개 공시에서 읽은 값만 찍는다(키를 찍지 않는다).
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
KEY = os.getenv("DART_API_KEY", "").strip()
# 안내의 정식명 꼴('(주)…' · '주식회사 …')과 약명
NAMES = [("(주)하나에어로다이내믹스", "하나에어로"), ("(주)에이엘로봇", "에이엘로봇"), ("주식회사 유캐스트", "유캐스트"),
         ("(주)엠비디", "엠비디"), ("(주)옵토닉스", "옵토닉스"), ("(주)래블업", "래블업"), ("(주)이에스티", "이에스티"),
         ("(주)동원파츠", "동원파츠"), ("(주)바로팜", "바로팜"), ("(주)넥스아이", "넥스아이"), ("(주)영광와이케이엠씨", "영광와이케이엠씨")]


def main():
    import dart_reader
    import ipo_filing as F
    codes = dart_reader.reader(KEY).corp_codes
    ok = 0
    for full, short in NAMES:
        print(f"\n======== {full} ========", flush=True)
        fin = F.collect(KEY, codes, full, short, today=datetime.date.today(), log=lambda *a: print(*a, flush=True))
        if not fin:
            print("  → 읽지 못함")
            continue
        ok += 1
        print(F.material_lines(fin))
        q = F.quant(fin)
        print("  [검사 값]", [(a["year"], a.get("rev"), a.get("op"), a.get("np")) for a in (q or {}).get("annual", [])])
    print(f"\n읽음 {ok}/{len(NAMES)}")


if __name__ == "__main__":
    if not KEY:
        print("DART_API_KEY 없음")
        sys.exit(0)
    main()
