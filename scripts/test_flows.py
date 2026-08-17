#!/usr/bin/env python3
"""수급 파서 회귀 테스트 — 네트워크 없이 돈다.

왜 필요한가. 네이버가 표 구조나 응답 형식을 바꾸면 파서를 고쳐야 하는데,
그때 예전에 되던 형식이 깨지는지 알 방법이 없다. 여기 고정해 둔다.

특히 단위 환산을 지킨다. 2026년 8월 14일 코스피 외국인 순매수는 3조387억원
이었다. 백만원 단위로 오는 값(3,038,700)을 억원(30,387)으로 바꾸는 걸 틀리면
브리핑에 '외국인이 303억 순매수'라고 나간다. 이건 눈에 잘 안 띄는 종류의
오류라서 사람이 검토해도 지나친다.

    python3 scripts/test_flows.py
"""
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flows as F

FAIL = []


def check(name, got, want):
    if got == want:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}\n       받음 {got!r}\n       기대 {want!r}")
        FAIL.append(name)


def ok(name, cond, detail=""):
    if cond:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name} {detail}")
        FAIL.append(name)


print("① 날짜 형식 — 네이버는 페이지마다 다르게 준다")
D = datetime.date(2026, 8, 14)
check("2026.08.14", F._date("2026.08.14"), D)
check("26.08.14 (두 자리 연도)", F._date("26.08.14"), D)
check("20260814 (구분자 없음)", F._date("20260814"), D)
check("2026-08-14", F._date("2026-08-14"), D)
check("08/14 (연도 없음)", F._date("08/14", today=datetime.date(2026, 8, 17)), D)
check("숫자 아님", F._date("합계"), None)
check("존재하지 않는 날", F._date("2026.02.30"), None)
# 연말에 1월 날짜가 나오면 다음 해로 넘어가야 한다
check("12월에 본 01/05",
      F._date("01/05", today=datetime.date(2026, 12, 28)), datetime.date(2027, 1, 5))

print("\n② HTML 표 — 백만원으로 오는 실제 구조")
HTML = """<table summary="일자별 순매수에 관한 표 입니다."><caption>일자별 순매수</caption>
<tr class="udline"><th rowspan="2" class="noln">날짜</th><th rowspan="2">개인</th>
<th rowspan="2">외국인</th><th rowspan="2">기관계</th></tr>
<tr><td>2026.08.14</td><td>-2,650,000</td><td>3,038,700</td><td>-420,000</td></tr>
<tr><td>2026.08.13</td><td>1,100,000</td><td>-900,000</td><td>-150,000</td></tr></table>"""
rows = F._from_html(HTML)
ok("두 행을 읽었다", len(rows) == 2, f"({len(rows)}행)")
d, vals = sorted(rows)[-1]
check("최신 행의 날짜", d, D)
check("주체 이름", sorted(vals), ["개인", "기관계", "외국인"])
passed, why = F._score(vals)
ok("합 검증 통과", passed, why)
mul, note = F._unit(vals)
check("단위 판정", note, "백만원→억원")
conv = {k: round(v * mul) for k, v in vals.items()}
# 이 숫자가 이 테스트의 핵심이다. 3조387억.
check("외국인 순매수(억원)", conv["외국인"], 30387)
check("개인 순매수(억원)", conv["개인"], -26500)

print("\n③ 껍데기만 온 응답 — 데이터 행이 없으면 빈 결과여야 한다")
SHELL = """<table summary="일자별 순매수에 관한 표 입니다."><caption>일자별 순매수</caption>
<tr class="udline"><th rowspan="2" class="noln">날짜</th><th rowspan="2">개인</th>
<th rowspan="2">외국인</th></tr></table>"""
ok("헤더만 있으면 0행", F._from_html(SHELL) == [], str(F._from_html(SHELL)))

print("\n④ JSON — 원 단위로 오는 모바일 API 형태")
JS = {"investorTrend": [
    {"localTradedAt": "2026-08-14", "individual": -2650000000000,
     "foreigner": 3038700000000, "institution": -420000000000},
    {"localTradedAt": "2026-08-13", "individual": 110000000000,
     "foreigner": -90000000000, "institution": -15000000000}]}
jrows, keys = F._from_json(JS)
ok("두 행을 읽었다", len(jrows) == 2, f"({len(jrows)}행)")
if jrows:
    jd, jvals = sorted(jrows)[-1]
    check("최신 행의 날짜", jd, D)
    jmul, jnote = F._unit(jvals)
    check("단위 판정", jnote, "원→억원")
    check("외국인 순매수(억원)", round(jvals["외국인"] * jmul), 30387)

print("\n⑤ 오독 검출 — 컬럼을 잘못 읽으면 버려야 한다")
# 세 주체가 모두 순매수면 있을 수 없다(누가 사면 누가 팔았다)
bad = {"개인": 1000, "외국인": 2000, "기관계": 3000}
ok("합이 안 맞으면 거부", not F._score(bad)[0], F._score(bad)[1])
ok("주체가 둘뿐이면 거부", not F._score({"개인": 1, "외국인": -1})[0])

print("\n⑥ 단위 판정 — 자릿수가 이상하면 버린다")
ok("억원대는 그대로", F._unit({"a": 30387, "b": -26500, "c": -4200})[1] == "억원(그대로)")
ok("너무 작으면 거부", F._unit({"a": 3, "b": -2, "c": -1})[0] is None)
ok("빈 값 거부", F._unit({"a": 0})[0] is None)

print("\n" + "=" * 60)
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: {', '.join(FAIL)}")
    sys.exit(1)
print("✅ 전부 통과")
