"""(일회성 진단) 한국거래소 영문 종목명이 붙어 있는 공시 영문명을 띄어 쓴 꼴인지 본다 — 공개 정보(상장사 영문명)만 찍는다."""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_report_text as C  # noqa: E402
import collect_data as D  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
s = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
stocks = json.loads(s[s.index("{"):s.rindex("}") + 1])["stocks"]
krx = D.krx_english_names()
print(f"한국거래소 영문명 {len(krx)}개 · 시세 자료 {len(stocks)}개")


def letters(x):
    return re.sub(r"[^A-Za-z]", "", x or "").upper()


same = spaced = 0
rows = []
for st in stocks:
    ne = st.get("name_en") or ""
    c = C.clean_en(ne)
    k = krx.get(st["ticker"], "")
    if " " not in c and len(letters(c)) > 8:
        rows.append((st["ticker"], ne, c, k))
    if k and letters(C.clean_en(k)) == letters(c):
        same += 1
        if " " in k and " " not in c:
            spaced += 1
print(f"글자가 같은 종목 {same}개 · 그중 한국거래소만 띄어 쓴 종목 {spaced}개")
print(f"\n붙은 이름 후보 {len(rows)}개 — 종목코드 | 공시 영문명 | 화면 꼴 | 한국거래소 영문명")
for r in rows:
    print(" | ".join(r))
print("\n표본(앞 15개):")
for st in stocks[:15]:
    print(st["ticker"], "|", st.get("name_en"), "|", krx.get(st["ticker"], ""))
