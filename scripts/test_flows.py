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

print("\n② HTML 표 — 네이버 실제 11칸 구조 (3차 실행에서 받은 값)")
# 날짜 | 개인 | 외국인 | 기관계 | 금융투자 보험 투신 은행 기타금융 연기금등 | 기타법인
# 이 값은 2026-08-14 코스피 실측이다. 외국인 +3조387억.
HTML = """<table summary="일자별 순매수에 관한 표 입니다.">
<tr class="udline"><th rowspan="2" class="noln">날짜</th><th rowspan="2">개인</th>
<th rowspan="2">외국인</th><th rowspan="2">기관계</th><th colspan="6">기관</th>
<th rowspan="2">기타법인</th></tr>
<tr><th class="sub">금융투자</th><th class="sub">보험</th><th class="sub">투신</th>
<th class="sub">은행</th><th class="sub">기타금융기관</th><th class="sub">연기금등</th></tr>
<tr><td>2026.08.14</td><td>-19,820</td><td>30,387</td><td>-10,298</td>
<td>-11,634</td><td>210</td><td>-450</td><td>-80</td><td>-44</td><td>1,700</td>
<td>-142</td></tr>
<tr><td>2026.08.13</td><td>3,145</td><td>-659</td><td>-2,524</td>
<td>-2,123</td><td>-50</td><td>-120</td><td>-20</td><td>-11</td><td>-200</td>
<td>-103</td></tr></table>"""
rows = F._from_html(HTML)
ok("두 행을 읽었다", len(rows) == 2, f"({len(rows)}행)")
d, vals = sorted(rows)[-1]
check("최신 행의 날짜", d, D)
# 자리로 맞추므로 세부 항목이 '기관' 이름을 훔치지 않아야 한다
check("주체 이름", sorted(vals), ["개인", "기관계", "기타법인", "외국인"])
check("외국인", vals["외국인"], 30387)
check("개인", vals["개인"], -19820)
check("기관계", vals["기관계"], -10298)
check("기타법인", vals["기타법인"], -142)
ok("금융투자가 '기관'으로 새지 않았다", "기관" not in vals, str(vals))
passed, why = F._score(vals)
# 3차 실행에서 여기가 0.37 로 나와 정상 데이터를 버렸다. 원인은 기관계+기관 이중계산.
ok("합 검증 통과 (이중계산 없음)", passed, why)
check("단위 판정", F._unit(vals)[1], "억원(그대로)")

print("\n②-2 이중계산 회귀 — '기관계'와 '기관'이 함께 오면 하나만 센다")
both = {"개인": -19820, "외국인": 30387, "기관계": -10298, "기관": -11634, "기타법인": -142}
p2, w2 = F._score(both)
ok("둘 다 있어도 통과해야 한다", p2, w2)

print("\n②-3 백만원으로 오는 표 (칸이 적은 형태)")
SMALL = """<table><tr><th>날짜</th><th>개인</th><th>외국인</th><th>기관계</th></tr>
<tr><td>2026.08.14</td><td>-2,650,000</td><td>3,038,700</td><td>-420,000</td></tr></table>"""
srows = F._from_html(SMALL)
ok("한 행을 읽었다", len(srows) == 1, str(srows))
if srows:
    _, svals = srows[0]
    ok("기타법인을 억지로 만들지 않는다", "기타법인" not in svals, str(svals))
    smul, snote = F._unit(svals)
    check("단위 판정", snote, "백만원→억원")
    check("외국인(억원)", round(svals["외국인"] * smul), 30387)

print("\n③ 껍데기만 온 응답 — 데이터 행이 없으면 빈 결과여야 한다")
SHELL = """<table summary="일자별 순매수에 관한 표 입니다."><caption>일자별 순매수</caption>
<tr class="udline"><th rowspan="2" class="noln">날짜</th><th rowspan="2">개인</th>
<th rowspan="2">외국인</th></tr></table>"""
ok("헤더만 있으면 0행", F._from_html(SHELL) == [], str(F._from_html(SHELL)))

print("\n③-2 날짜 열이 없는 형태 — sise_index 처럼 하루치 한 줄")
LABELED = """<div class="invest_trend"><h4>투자자별 매매동향</h4>
<table class="type_2"><tr><th scope="row">개인</th><td class="num">-26,500</td></tr>
<tr><th scope="row">외국인</th><td class="num">+30,387</td></tr>
<tr><th scope="row">기관계</th><td class="num">-4,200</td></tr></table></div>"""
lrows = F._from_labeled(LABELED, D)
ok("한 행을 만들었다", len(lrows) == 1, str(lrows))
if lrows:
    _, lvals = lrows[0]
    check("외국인", lvals["외국인"], 30387)
    check("개인", lvals["개인"], -26500)
    ok("합 검증 통과", F._score(lvals)[0], F._score(lvals)[1])
# 네이버는 부호를 △▽ 로 쓰는 화면도 있다
TRI = ("<tr><th>개인</th><td>▽26,500</td></tr><tr><th>외국인</th><td>△30,387</td></tr>"
       "<tr><th>기관계</th><td>▽4,200</td></tr>")
trows = F._from_labeled(TRI, D)
ok("△▽ 부호 처리", trows and trows[0][1]["외국인"] == 30387 and trows[0][1]["개인"] == -26500,
   str(trows))
ok("주체가 둘뿐이면 거부",
   F._from_labeled("<tr><th>개인</th><td>100</td></tr><tr><th>외국인</th><td>-100</td></tr>", D) == [])
# 주체 이름이 본문에 지나가듯 나오는 페이지에서 엉뚱한 숫자를 물면 안 된다
NOISE = "<p>외국인 투자자 동향에 관심이 모인다</p><p>개인 투자자도 늘었다</p>"
ok("숫자 없는 언급은 무시", F._from_labeled(NOISE, D) == [], str(F._from_labeled(NOISE, D)))

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
bad = {"개인": 1000, "외국인": 2000, "기관계": 3000}   # 셋 다 순매수 = 있을 수 없다
ok("합이 안 맞으면 거부", not F._score(bad)[0], F._score(bad)[1])
ok("주체가 둘뿐이면 거부", not F._score({"개인": 1, "외국인": -1})[0])

print("\n⑥ 단위 판정 — 자릿수가 이상하면 버린다")
ok("억원대는 그대로", F._unit({"a": 30387, "b": -26500, "c": -4200})[1] == "억원(그대로)")
ok("너무 작으면 거부", F._unit({"a": 3, "b": -2, "c": -1})[0] is None)
ok("빈 값 거부", F._unit({"a": 0})[0] is None)

print("\n⑦ 지수 예비 — 네이버 모바일 지수 API 파서 (야후가 하루 늦는 날)")
import market_data as M
ROWS = [  # 9/22 러너 실측 뼈대 — 최근 행이 먼저 온다, 값은 쉼표 든 문자열
    {"localTradedAt": "2026-09-21", "closePrice": "3,532.11", "compareToPreviousClosePrice": "91.50",
     "compareToPreviousPrice": {"code": "2", "text": "상승", "name": "RISING"}, "fluctuationsRatio": "2.66"},
    {"localTradedAt": "2026-09-18", "closePrice": "3,440.61", "compareToPreviousClosePrice": "-10.00",
     "compareToPreviousPrice": {"code": "5", "text": "하락", "name": "FALLING"}, "fluctuationsRatio": "-0.29"},
    {"localTradedAt": "2026-09-17", "closePrice": "3,450.61", "compareToPreviousClosePrice": "0",
     "compareToPreviousPrice": {"code": "3", "text": "보합", "name": "STEADY"}, "fluctuationsRatio": "0.00"},
]
g = M.parse_naver_index(ROWS, "2026-09-21")
ok("그날 행을 찾아 종가를 읽는다", g and g["date"] == "2026-09-21" and g["close"] == 3532.11, str(g))
ok("등락률은 앞뒤 종가로 계산한다 (부호 규칙을 믿지 않는다)", g and abs(g["change"] - 2.66) < 0.01, str(g))
ok("원하는 날이 없으면 None — 다른 날 값을 그날 값인 척 주지 않는다", M.parse_naver_index(ROWS, "2026-09-22") is None)
ok("날짜를 안 주면 가장 최근 행", M.parse_naver_index(ROWS)["date"] == "2026-09-21")
ok("날짜가 20260921 꼴이어도 읽는다",
   M.parse_naver_index([{"localTradedAt": "20260921", "closePrice": 3532.11}])["date"] == "2026-09-21")
ok("첫 행이면 등락률 없음(앞 행이 없다)", M.parse_naver_index(ROWS, "2026-09-17")["change"] is None)
ok("빈 응답·엉뚱한 모양은 None", M.parse_naver_index([]) is None and M.parse_naver_index([{"x": 1}, "junk"]) is None)
ok("문자열 숫자 읽기", M._num("3,432.11") == 3432.11 and M._num("+2.66") == 2.66 and M._num("abc") is None)

print("\n⑧ 2026-09-22 에 살아 있던 두 응답 — 네이버 trend · 다음 market_index")
TREND = {"bizdate": "20260921", "personalValue": "-15,996", "foreignValue": "+2,010", "institutionalValue": "-479"}
rows8, keys8 = F._from_json(TREND)
ok("네이버 trend 한 줄을 읽는다", len(rows8) == 1 and rows8[0][0] == datetime.date(2026, 9, 21), str(rows8))
ok("부호·쉼표 든 문자열 값", rows8 and rows8[0][1] == {"개인": -15996, "외국인": 2010, "기관": -479}, str(rows8))
ok("쓴 키가 이름 붙은 키다", set(keys8[0]) <= F.NAMED_KEYS, str(keys8))
DAUM = {"code": 200, "message": "OK", "data": [
    {"date": "2026-09-22 00:00:00", "tradePrice": 7054.37, "change": "RISE", "changePrice": 46.65,
     "individualStraightPurchasePrice": -1593102465713.0, "foreignStraightPurchasePrice": 199506469641.0,
     "institutionStraightPurchasePrice": -59706459775.0},
    {"date": "2026-09-21 00:00:00", "tradePrice": 7007.72, "change": "RISE", "changePrice": 113.49,
     "individualStraightPurchasePrice": -820000000000.0, "foreignStraightPurchasePrice": 500000000000.0,
     "institutionStraightPurchasePrice": 250000000000.0}]}
drows, dkeys = F._from_json(DAUM)
ok("다음 응답은 날짜별 행이 된다", len(drows) == 2 and {r[0] for r in drows} == {datetime.date(2026, 9, 21), datetime.date(2026, 9, 22)}, str(drows))
pick = F._pick(drows, "20260921")
ok("거래일이 맞는 행만 고른다 — 장중의 오늘 미완성 행(9/22)을 집지 않는다", pick and pick[0] == datetime.date(2026, 9, 21), str(pick))
ok("그날 행이 없으면 None", F._pick(drows, "20260918") is None)
mul, note = F._unit(pick[1])
ok("원 단위는 억원으로", mul == 1 / 1e8 and round(pick[1]["외국인"] * mul) == 5000, f"{mul} {note}")
sc, why = F._score(rows8[0][1], named=True)
ok("셋뿐인 응답은 합이 0 이 아니어도 통과(이름 붙은 키)", sc, why)
ok("같은 값을 이름 없는 키로 읽었다면 여전히 거부", not F._score(rows8[0][1])[0], F._score(rows8[0][1])[1])
ok("후보 맨 앞 둘이 살아 있는 주소다",
   [c[0] for c in F.candidates("01", "KOSPI", "20260921")[:2]] == ["모바일 API · trend", "다음 market_index/days"])
ok("다음 요청에는 Referer 가 있다", "daum" in F.DAUM_UA["Referer"])

print("\n" + "=" * 60)

if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: {', '.join(FAIL)}")
    sys.exit(1)
print("✅ 전부 통과")
