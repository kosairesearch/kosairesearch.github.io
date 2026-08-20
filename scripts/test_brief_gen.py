#!/usr/bin/env python3
"""브리핑 생성기 회귀 테스트 — 네트워크도 API 키도 필요 없다.

왜 필요한가. 여기서 막는 것들은 전부 '조용히 잘못 나가는' 종류다.

  · 금지 표현이 새면 투자권유 문장이 발행된다. 그런데 '순매수'는 사실이라
    막아선 안 된다 — 이 경계가 정규식 한 글자에 걸려 있다.
  · 커버리지 25% 상한이 안 지켜지면 브리핑이 리포트 홍보물이 된다.
    사용자가 8월 17일 초안을 보고 처음 지적한 게 그거였다(당시 45%).
  · 모델이 만든 [이름](코드) 링크를 검증 없이 넣으면 우리가 안 만든 링크가
    페이지에 걸린다.
  · 영문 누락은 화면에서 한국어가 그대로 남아 티가 잘 안 난다.

    python3 scripts/test_brief_gen.py
"""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_brief as G

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


def has(reasons, needle):
    return any(needle in r for r in reasons)


# ────────────────────── 정상 브리핑 하나 만들기 ──────────────────────

KO = ("지수는 올랐지만 폭은 좁았다. 외국인이 사들인 곳과 지수가 오른 곳이 같지 "
      "않아서, 같은 날을 두고도 체감이 갈렸다. ")
EN = ("The index rose but the breadth was narrow, so the day felt different "
      "depending on what you held. ")


def para(n):
    """한국어 n자 안팎의 문단과 영문 대역."""
    reps = max(1, round(n / len(KO)))
    return {"ko": (KO * reps).strip(), "en": (EN * reps).strip()}


def cov_para(n):
    """커버리지 문단. 출처(리포트)와 종목 링크가 있어야 검증을 통과한다."""
    p = para(n)
    p["ko"] = "5월 리포트에서 확인 지점으로 꼽아 둔 것이 이번 주에 나온다. [현대차](005380). " + p["ko"]
    p["en"] = "A checkpoint the May report flagged lands this week. [Hyundai](005380). " + p["en"]
    return p


def sample(us=700, dom=650, ahead=700, cov=550):
    return {
        "title": {"ko": "휴장 하루, 미국은 두 번 열린다", "en": "One holiday, two US sessions"},
        "lead": para(120),
        # 요약 — 목록이 아니라 이어지는 한 문단이어야 한다(규칙 9-1).
        "summary": {
            "ko": "미국은 세 지수가 나란히 올랐지만 필라델피아 반도체만 2% 넘게 밀렸다. "
                  "국내도 같은 자리가 눌렸는데, 지수를 끌어내린 무게가 시가총액 상위 몇 "
                  "종목에 몰려 있었던 하루였다. 오늘 새벽에는 미국 소비자물가가 나온다.",
            "en": "US indexes edged up together while the Philadelphia semiconductor "
                  "gauge fell more than 2%. Seoul sagged in the same place, with the "
                  "weight that pulled the index down sitting in a handful of the "
                  "largest names. US consumer prices land before the open.",
        },
        "sections": [
            # 제목은 매일 새로 쓴다 — 고정 이름("간밤 뉴욕", "볼 것")은 검증이
            # 거부한다. ⑦-5 에서 그걸 확인한다.
            {"id": "us", "heading": {"ko": "반도체는 비켜갔다",
                                     "en": "Chips sidestepped it"},
             "paragraphs": [para(us)]},
            {"id": "domestic", "heading": {"ko": "지수는 올랐지만 폭은 좁았다",
                                           "en": "The index rose, the breadth did not"},
             "paragraphs": [para(dom)]},
            {"id": "ahead", "heading": {"ko": "18일이 두 번을 받는다",
                                        "en": "Tuesday absorbs two sessions"},
             "paragraphs": [para(ahead)]},
            {"id": "coverage", "heading": {"ko": "현대차그룹 세 곳",
                                           "en": "Three Hyundai names"},
             "paragraphs": [cov_para(cov)]},
        ],
    }


print("① 기본형은 통과해야 한다")
base = sample()
n, ratio = G.measure(base)
ok(f"분량 {n:,}자가 통과 범위 안", G.LEN_MIN <= n <= G.LEN_MAX, f"({n})")
ok(f"커버리지 {ratio*100:.0f}% ≤ 25%", ratio <= G.COVERAGE_CAP, f"({ratio:.3f})")
check("거부 이유 없음", G.validate(base), [])

print("\n② 분량 — 짧으면 거부, 길면 거부")
ok("1,200자짜리 거부", has(G.validate(sample(300, 300, 300, 200)), "분량"))
ok("5,000자짜리 거부", has(G.validate(sample(1400, 1400, 1400, 900)), "분량"))

print("\n③ 커버리지 25% 상한 — 사용자가 처음 지적한 지점")
fat = sample(us=500, dom=450, ahead=450, cov=1200)
n2, r2 = G.measure(fat)
ok(f"커버리지 {r2*100:.0f}% 는 거부", has(G.validate(fat), "커버리지 섹션"), f"{r2:.3f}")
ok("2차(30% 완화)에서도 거부", has(G.validate(fat, strict_coverage=False), "커버리지 섹션"))
mid = sample(us=600, dom=550, ahead=550, cov=750)
_, r3 = G.measure(mid)
ok(f"{r3*100:.0f}% 는 1차 거부 / 2차 통과",
   has(G.validate(mid), "커버리지 섹션") and not has(G.validate(mid, strict_coverage=False),
                                                 "커버리지 섹션"), f"{r3:.3f}")

print("\n④ 금지 표현 — 투자권유가 새는 걸 막는다")
for bad_text, label in [
        ("삼성전자의 목표주가를 3만원으로 본다", "목표주가"),
        ("지금 매수 추천 구간이다", "매수 추천"),
        ("투자의견을 중립으로 제시한다", "투자의견"),
        ("현재 주가는 저평가 상태다", "저평가"),
        ("추가 상승 여지가 남아 있다", "상승 여지"),
        ("다음 주에는 오를 것으로 보인다", "오를 것"),
        ("지금 사야 하는 유망주다", "유망주"),
        ("비중 확대가 필요한 시점이다", "비중 확대")]:
    b = copy.deepcopy(base)
    b["sections"][0]["paragraphs"][0]["ko"] += " " + bad_text
    ok(f"거부: {label}", has(G.validate(b), "금지 표현"), bad_text)

print("\n④-2 사실 표현은 막지 않는다 — 여기서 과하게 잡으면 브리핑을 못 쓴다")
for good_text, label in [
        ("외국인이 3조387억원을 순매수했다", "순매수"),
        ("기관은 1조298억원을 순매도했다", "순매도"),
        ("개인의 매수 우위가 이어졌다", "매수 우위"),
        ("거래대금이 매도 물량을 흡수했다", "매도 물량"),
        ("증권사는 실적 전망을 높였다고 밝혔다", "인용된 전망"),
        ("반도체 업종의 상승 폭이 가장 컸다", "상승 폭")]:
    b = copy.deepcopy(base)
    b["sections"][1]["paragraphs"][0]["ko"] += " " + good_text
    reasons = [r for r in G.validate(b) if "금지 표현" in r]
    ok(f"통과: {label}", not reasons, str(reasons))

print("\n④-3 영문 본문도 검사한다 — 한국어만 막으면 영어 화면으로 새 나간다")
for bad_en, label in [
        ("Our price target is 30,000 won.", "price target"),
        ("This is a buy rating.", "buy rating"),
        ("The stock looks undervalued.", "undervalued"),
        ("There is upside potential from here.", "upside potential"),
        ("Shares will rise next week.", "will rise"),
        ("One of our top picks.", "top picks"),
        ("We move to overweight.", "overweight")]:
    b = copy.deepcopy(base)
    b["sections"][0]["paragraphs"][0]["en"] += " " + bad_en
    ok(f"거부: {label}", has(G.validate(b), "금지 표현"), bad_en)

print("\n④-4 영문 사실 표현은 막지 않는다")
for good_en, label in [
        ("Foreigners bought a net 3.04 trillion won.", "net buying"),
        ("Institutions were net sellers.", "net sellers"),
        ("The brokerage said it raised its earnings estimate.", "attributed view"),
        ("Semiconductors led the gains.", "led the gains"),
        ("Trading value was concentrated in two names.", "trading value")]:
    b = copy.deepcopy(base)
    b["sections"][1]["paragraphs"][0]["en"] += " " + good_en
    reasons = [r for r in G.validate(b) if "금지 표현" in r]
    ok(f"통과: {label}", not reasons, str(reasons))

print("\n⑤ 양국어 — 영문 누락은 화면에서 티가 안 난다")
b = copy.deepcopy(base)
b["sections"][2]["paragraphs"][0]["en"] = ""
ok("문단 영문 누락 거부", has(G.validate(b), "대응하는 영문이 없다"), str(G.validate(b)))
b = copy.deepcopy(base)
b["title"]["en"] = ""
ok("제목 영문 누락 거부", has(G.validate(b), "title.en"))

print("\n⑥ 섹션 구조")
b = copy.deepcopy(base)
b["sections"][0]["id"] = "intro"
ok("모르는 섹션 id 거부", has(G.validate(b), "모르는 섹션"))
b = copy.deepcopy(base)
b["sections"][0], b["sections"][3] = b["sections"][3], b["sections"][0]
ok("섹션 순서 뒤바뀜 거부", has(G.validate(b), "섹션 순서"))
b = copy.deepcopy(base)
b["sections"][1]["paragraphs"] = []
ok("빈 섹션 거부", has(G.validate(b), "문단이 없다"))
# 데이터가 없어 섹션이 빠지는 건 정상이다(설계 4절)
b = copy.deepcopy(base)
b["sections"] = [s for s in b["sections"] if s["id"] != "us"]
b["sections"][0]["paragraphs"] = [para(1000)]
reasons = [r for r in G.validate(b) if "섹션" in r]
ok("섹션 하나가 없는 건 허용", not reasons, str(reasons))

print("\n⑦ 종목 링크 — 커버리지에 있는 코드만 남긴다")
COV = {"005380", "005930"}
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = "[현대차](005380) 와 [없는회사](999999) 와 [셋](abc)."
b["sections"][3]["paragraphs"][0]["en"] = "[Hyundai](005380) and [Ghost](999999)."
dropped = G.normalize_links(b, COV)
p = b["sections"][3]["paragraphs"][0]
check("유효한 링크는 남는다", "[현대차](005380)" in p["ko"], True)
check("커버리지에 없는 코드는 평문", p["ko"].count("없는회사") == 1 and "999999" not in p["ko"], True)
check("여섯 자리가 아니면 평문", "abc" not in p["ko"] and "셋" in p["ko"], True)
check("영문에도 같이 적용", "[Hyundai](005380)" in p["en"] and "999999" not in p["en"], True)
ok("떨어낸 링크를 보고한다", len(dropped) == 3, str(dropped))

print("\n⑦-2 분량은 링크·강조 표시를 빼고 센다")
plain = G._plain("[현대차](005380)가 **6.05%** 올랐다")
check("표시 문자만 남는다", plain, "현대차가 6.05% 올랐다")
a = sample()
c = copy.deepcopy(a)
c["sections"][0]["paragraphs"][0]["ko"] = \
    c["sections"][0]["paragraphs"][0]["ko"].replace("지수는", "[지수는](005930)", 1)
check("링크를 걸어도 글자 수는 같다", G.measure(c)[0], G.measure(a)[0])
# 표시 문자열이 80자를 넘으면 링크로 의도한 게 아니다 — 문단을 통째로 감싼 것.
long_label = "[" + "가" * 200 + "](005930)"
ok("지나치게 긴 라벨은 링크로 보지 않는다", G._plain(long_label) == long_label)
b = copy.deepcopy(base)
b["sections"][0]["paragraphs"][0]["ko"] = long_label
ok("그런 것은 평문화 대상도 아니다", G.normalize_links(b, COV) == [])

print("\n⑦-3 영문에 링크가 없으면 거부 — 2차 실행에서 13개가 날아갔다")
b = copy.deepcopy(base)
b["sections"][1]["paragraphs"][0]["ko"] += " [SK하이닉스](000660)가 1위였다."
b["sections"][1]["paragraphs"][0]["en"] += " SK Hynix topped turnover."
ok("한국어에만 링크가 있으면 거부", has(G.validate(b), "영문에 없다"), str(G.validate(b)))
b["sections"][1]["paragraphs"][0]["en"] += " [SK Hynix](000660)"
reasons = [r for r in G.validate(b) if "링크" in r]
ok("영문에도 있으면 통과", not reasons, str(reasons))
b = copy.deepcopy(base)
b["sections"][1]["paragraphs"][0]["en"] += " [Samsung](005930)"
ok("영문에만 있는 링크는 거부", has(G.validate(b), "영문에만 있는"))

print("\n⑦-4 **이름**(코드) 는 링크로 고친다 — 재시도 350원을 아낀다")
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = "**SK하이닉스**(000660)가 1위였다."
b["sections"][3]["paragraphs"][0]["en"] = "For **SK Hynix**(000660), turnover led."
n_fixed = G.repair_links(b)
check("두 곳을 고쳤다", n_fixed, 2)
check("한국어가 링크가 됐다", b["sections"][3]["paragraphs"][0]["ko"],
      "[SK하이닉스](000660)가 1위였다.")
check("영문도 링크가 됐다", b["sections"][3]["paragraphs"][0]["en"],
      "For [SK Hynix](000660), turnover led.")
# 이미 올바른 형식은 건드리지 않는다
b2 = copy.deepcopy(base)
b2["sections"][3]["paragraphs"][0]["ko"] = "[현대차](005380)는 올랐다. **6.05%** 다."
check("올바른 형식과 굵게는 그대로", G.repair_links(b2), 0)
check("굵게가 살아 있다", "**6.05%**" in b2["sections"][3]["paragraphs"][0]["ko"], True)

print("\n⑦-5 섹션 제목 — 매일 새로 쓰기로 했으니 매일 검증한다")


def with_heads(*ko_heads):
    b = copy.deepcopy(base)
    for s, h in zip(b["sections"], ko_heads):
        s["heading"]["ko"] = h
    return b


good = with_heads("반도체는 비켜갔다", "지수는 올랐지만 폭은 좁았다",
                  "18일이 두 번을 받는다", "현대차그룹 세 곳의 반기보고서")
check("내용을 담은 제목은 통과", G.check_headings(good), [])
ok("'볼 것' 은 거부(너무 짧다)",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "볼 것",
                                   "현대차그룹 세 곳")), "자 이상"))
ok("'코사이 커버리지에서' 는 번역체로 거부",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다",
                                   "18일이 두 번을 받는다", "코사이 커버리지에서")), "번역체"))
ok("너무 긴 제목 거부",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다",
                                   "18일이 두 번을 받는다",
                                   "현대차그룹 세 곳의 반기보고서가 어제 접수되어 확인 지점이 걸렸다")),
       "문장이다"))
# 8월 18일에 25자 제목이 거부돼 발행이 막혔다. 이제 30자까지 받는다.
ok("25자 제목은 통과",
   not has(G.check_headings(with_heads("반도체는 비켜갔다", "올린 건 지수, 오른 건 상위 몇 종목",
                                       "18일이 두 번을 받는다", "현대차그룹 세 곳")), "문장이다"))
ok("겹치는 제목 거부",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "반도체는 비켜갔다",
                                   "18일이 두 번을 받는다", "현대차그룹 세 곳")), "겹친다"))
b = with_heads("휴장 하루, 미국은 두 번 열린다", "지수는 올랐다",
               "18일이 두 번을 받는다", "현대차그룹 세 곳")
b["title"]["ko"] = "휴장 하루, 미국은 두 번 열린다"
ok("기사 제목을 그대로 쓰면 거부", has(G.check_headings(b), "기사 제목과 같다"))
# 제목에 링크·강조가 들어와도 글자 수를 제대로 센다
ok("링크 표시를 뺀 길이로 센다",
   G.check_headings(with_heads("[SK하이닉스](000660)가 끌었다", "지수는 올랐다",
                               "18일이 두 번을 받는다", "현대차그룹 세 곳")) == [])

# 사용자가 어색하다고 한 옛 제목 한 벌. 이제 통째로 거부돼야 한다.
old = G.check_headings(with_heads("간밤 뉴욕", "직전 국내 장", "볼 것", "코사이 커버리지에서"))
ok("옛 제목 한 벌은 거부", len(old) >= 3, str(old))

print("\n⑦-6 '간밤' — 미국이 어젯밤에 열린 날에만 쓸 수 있다")
TUE = {"domestic": {"calendar": {"today": "20260818"}},
       "markets": {"sp500": {"date": "2026-08-17"}}}      # 화요일 아침: 어젯밤 열렸다
MON = {"domestic": {"calendar": {"today": "20260817"}},
       "markets": {"sp500": {"date": "2026-08-14"}}}      # 월요일 아침: 금요일이 마지막
ok("화요일엔 쓸 수 있다", G.overnight_ok(TUE)[0])
ok("월요일엔 못 쓴다", not G.overnight_ok(MON)[0])
ok("못 쓰는 날엔 사실 블록에 이유를 적는다",
   "어젯밤에 미국이 열리지 않았다" in (G.overnight_ok(MON)[1] or ""))
ok("근거가 없으면 막지 않는다", G.overnight_ok({})[0])

hb = with_heads("간밤 뉴욕은 물러섰다", "지수는 올랐다", "18일이 두 번을 받는다",
                "현대차그룹 세 곳")
ok("월요일에 '간밤' 제목은 거부", has(G.check_headings(hb, MON), "간밤"))
ok("화요일에는 통과", not has(G.check_headings(hb, TUE), "간밤"))
b = copy.deepcopy(good)
b["lead"]["ko"] = "간밤 뉴욕은 세 지수가 함께 내렸다. " + b["lead"]["ko"]
ok("리드에 새도 잡는다", has(G.check_headings(b, MON), "lead.ko"))
ok("본문 문단은 막지 않는다(사실 블록이 경고한다)",
   not has(G.check_headings(good, MON), "us.p0"))
print("\n⑦-7 커버리지 출처 표시 — 이 섹션이 브리핑의 존재 이유다")
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = para(550)["ko"] + " [현대차](005380)"
ok("'리포트' 언급이 없으면 거부", has(G.validate(b), "'리포트'라는 말이 없다"), str(G.validate(b)))
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = "5월 리포트가 확인 지점으로 뒀다. " + para(520)["ko"]
ok("종목 링크가 없으면 거부", has(G.validate(b), "종목 링크가 없다"))
reasons = [r for r in G.validate(base) if "coverage" in r]
ok("둘 다 있으면 통과", not reasons, str(reasons))

print("\n⑦-8 회사명은 언제나 KOSAI — 한글 '코사이'는 거부")
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = \
    b["sections"][3]["paragraphs"][0]["ko"].replace("5월 리포트", "코사이가 5월 리포트")
ok("본문의 '코사이' 거부", has(G.validate(b), "'코사이'"), str(G.validate(b)))
b = copy.deepcopy(base)
b["title"]["ko"] = "코사이가 짚은 것"
ok("제목의 '코사이' 거부", has(G.validate(b), "'코사이'"))
b = copy.deepcopy(base)
b["sections"][3]["paragraphs"][0]["ko"] = \
    b["sections"][3]["paragraphs"][0]["ko"].replace("5월 리포트", "KOSAI가 5월 리포트")
reasons = [r for r in G.validate(b) if "코사이" in r]
ok("KOSAI 표기는 통과", not reasons, str(reasons))

print("\n⑦-9 '코사이' 는 거부 전에 자동 교정한다 — 표기 하나로 발행을 멈추지 않는다")
b = copy.deepcopy(base)
b["title"]["ko"] = "코사이가 짚은 것"
b["lead"]["ko"] = "코사이 리포트에서 " + b["lead"]["ko"]
b["sections"][3]["heading"]["ko"] = "코사이 커버리지"
b["sections"][3]["paragraphs"][0]["ko"] = \
    b["sections"][3]["paragraphs"][0]["ko"].replace("5월", "코사이 5월")
b["sections"][3]["paragraphs"][0]["en"] = "코사이 report. " + b["sections"][3]["paragraphs"][0]["en"]
n = G.repair_brand(b)
check("다섯 곳을 고쳤다", n, 5)
check("제목", b["title"]["ko"], "KOSAI가 짚은 것")
ok("섹션 제목도", b["sections"][3]["heading"]["ko"] == "KOSAI 커버리지")
ok("영문도", "KOSAI report." in b["sections"][3]["paragraphs"][0]["en"])
reasons = [r for r in G.validate(b) if "코사이" in r]
ok("교정 뒤에는 검증을 통과한다", not reasons, str(reasons))
check("고칠 게 없으면 0", G.repair_brand(copy.deepcopy(base)), 0)

print("\n⑦-10 발행 시각이 날짜 옆에 분까지 찍힌다")
import datetime as _dt
sys.path.insert(0, str(Path(__file__).resolve().parent))
import render_brief as R
_doc = {"date": "2026-08-18", "tradeDate": "20260814", "marketOpen": True,
        "title": {"ko": "제목", "en": "T"}, "lead": {"ko": "리드", "en": "L"}, "sections": []}
_at = _dt.datetime(2026, 8, 18, 7, 27, tzinfo=R.KST)
(dko, den), _, _ = R.head_lines(_doc, _at)
check("한국어 날짜줄", dko, "2026년 8월 18일 (화) 07:27")
check("영문 날짜줄", den, "Tuesday, August 18, 2026 · 07:27 KST")
# 한 자리 시각도 두 자리로 채운다 — 7:3 처럼 나오면 안 된다
(d2, e2), _, _ = R.head_lines(_doc, _dt.datetime(2026, 8, 18, 7, 3, tzinfo=R.KST))
check("영(0) 채움", d2, "2026년 8월 18일 (화) 07:03")
ok("영문도 0 채움", "07:03 KST" in e2, e2)
# 사전 키와 값이 짝이 맞아야 영어 모드에서 한글이 안 남는다
_body, _dic = R.build(_doc, _at)
ok("사전에 날짜줄이 있다", dko in _dic and _dic[dko] == den, str(_dic.get(dko)))
ok("화면 HTML 에 시각이 있다", "07:27" in _body, _body[:120])

print("\n⑦-11 요약 — 목록이 아니라 이어지는 한 문단이어야 한다")
b = copy.deepcopy(base)
ok("기본 요약은 통과", not [r for r in G.validate(b) if "요약" in r], str(G.validate(b)))
b = copy.deepcopy(base)
b["summary"]["ko"] = "· 나스닥 1.2% 하락 · 코스피 0.4% 상승 · 오늘 CPI 발표"
ok("글머리표가 있으면 거부", has(G.validate(b), "글머리표"))
b = copy.deepcopy(base)
b["summary"]["ko"] = base["summary"]["ko"].replace(". ", ".\n")
ok("줄바꿈이 있으면 거부", has(G.validate(b), "글머리표"))
b = copy.deepcopy(base)
b["summary"]["ko"] = "코스피가 올랐다."
ok("너무 짧으면 거부", has(G.validate(b), "요약이"))
# 모델이 목록으로 써 와도 거부하기 전에 한 문단으로 편다
b = {"summary": {"ko": "1. 나스닥 하락\n2. 코스피 상승", "en": "1. down\n2. up"}}
n = G.repair_summary(b)
ok("목록을 한 문단으로 이어 붙인다", n == 2 and "\n" not in b["summary"]["ko"], repr(b["summary"]["ko"]))
ok("번호를 떼어 낸다", not G.SUM_LIST.search(b["summary"]["ko"]), repr(b["summary"]["ko"]))
b = {"summary": {"ko": "[현대차](005380) 가 **올랐다**.", "en": "x"}}
G.repair_summary(b)
check("요약에서 링크·강조를 벗긴다", b["summary"]["ko"], "현대차 가 올랐다.")
# 요약이 없으면 1차는 거부, 2차는 통과 — 요약 하나로 발행을 멈추지 않는다
b = copy.deepcopy(base)
b["summary"] = {}
ok("1차는 빈 요약 거부", has(G.validate(b), "summary 가 비었다"))
ok("2차는 빈 요약 허용", not has(G.validate(b, strict_coverage=False), "summary 가 비었다"))

print("\n⑧ 응답 파싱")
body = json.dumps(sample(), ensure_ascii=False)
check("마커 안쪽만 읽는다",
      G.parse("설명 문장\n===JSON_START===\n" + body + "\n===JSON_END===\n뒷말")["title"]["ko"],
      "휴장 하루, 미국은 두 번 열린다")
check("코드펜스 제거", G.parse("```json\n" + body + "\n```")["title"]["ko"],
      "휴장 하루, 미국은 두 번 열린다")
check("마커 없는 맨 JSON", G.parse(body)["title"]["ko"], "휴장 하루, 미국은 두 번 열린다")

# ────────────────────── 사실 블록 ──────────────────────

FACTS = {
    "generatedAt": "2026-08-17T06:05:00+09:00",
    "domestic": {
        "tradeDate": "20260814", "tradeDateKo": "8월 14일",
        "publishDate": "2026-08-17", "coverage": 2692, "base": 2.42,
        "calendar": {"today": "20260817", "open": False, "prev": "20260814",
                     "next": "20260818", "gapDays": 3},
        "index": {"kospi": {"close": 6977.94, "change": 2.42},
                  "kosdaq": {"close": 864.65, "change": 0.38}},
        "flows": {"kospi": {"개인": -19820, "외국인": 30387, "기관계": -10298,
                            "_date": "2026-08-14"}},
        "breadth": {"weighted": 2.31, "median": 0.38, "advancers": 1518,
                    "decliners": 941, "unchanged": 226, "total": 2685},
        "movers": {"leaders": [{"ticker": "005380", "name": "현대차", "change": 6.05,
                                "rel": 3.63, "tradingValue": 8200}],
                   "laggards": [], "up": [], "down": [],
                   "actives": [{"ticker": "000660", "name": "SK하이닉스", "change": 3.1,
                                "rel": 0.68, "tradingValue": 74897}]},
        "sectors": {"up": [{"sector": "자동차", "change": 6.05}], "down": []},
        "filings": [{"ticker": "005380", "name": "현대차", "report": "반기보고서",
                     "mcap": 61.2, "totalFilings": 2040,
                     "checkpoints": [{"when": "8월 중", "what": "자주포 계약 확정 여부"}],
                     "bull": ["믹스 개선"]}],
    },
    "markets": {
        "sp500": {"label": "S&P 500", "close": 7785.76, "change": -0.17,
                  "date": "2026-08-14", "unit": ""},
        "sox": {"label": "필라델피아 반도체", "close": 12417.05, "change": -0.31,
                "date": "2026-08-14", "unit": ""},
        "usdkrw": {"label": "원/달러", "close": 1413.22, "change": 0.12,
                   "date": "2026-08-14", "unit": "원"},
    },
    "schedule": {"from": "2026-08-17", "to": "2026-08-31",
                 "events": [{"date": "2026-08-19", "kind": "FOMC", "title": "7월 의사록 공개"}]},
    "news": {"groups": {"시황": [{"title": "코스피 5거래일 연속 상승", "source": "연합뉴스"}]},
             "tickers": {}},
}

print("\n⑨ 사실 블록 — 모델이 읽는 것과 사람이 검증하는 것이 같아야 한다")
txt = G._facts_text(FACTS)
ok("휴장을 명시한다", "휴장" in txt, txt[:120])
ok("휴장 간격을 설명한다", "미국 시장이 여러 번 열리" in txt)
ok("종목코드를 붙인다", "현대차(005380)" in txt)
ok("외국인 순매수 단위가 억원", "외국인 +30,387억원" in txt)
ok("rel 기준을 설명한다", "부진이다" in txt)
ok("못 받은 값을 알린다", "못 받은 값(쓰지 말 것)" in txt and "나스닥" in txt)
ok("뉴스 숫자 사용을 막는다", "제목 속 숫자는 쓰지 말 것" in txt)
# 오늘 08-17, 미국 기준일 08-14 — 어젯밤에 미국이 열리지 않은 날이다
ok("'간밤' 을 쓸 수 없다고 적는다", "[표현 주의]" in txt and "어젯밤에 미국이 열리지 않았다" in txt)
ok("판정도 같은 답을 준다", not G.overnight_ok(FACTS)[0])
ok("확인 지점을 넘긴다", "자주포 계약 확정 여부" in txt)
ok("공시 전체 건수를 알린다", "전체 2,040건" in txt)

print("\n⑨-2 값이 빠졌을 때 — 지어내지 말라고 적어 준다")
f2 = copy.deepcopy(FACTS)
f2["markets"] = None
f2["domestic"]["flows"] = None
f2["domestic"]["index"] = None
f2["schedule"] = None
f2["news"] = None
t2 = G._facts_text(f2)
ok("시세 없으면 섹션 1 생략 지시", "섹션 1을 생략하라" in t2)
ok("수급 없으면 외국인 얘기 금지", "외국인·기관 얘기를 쓰지 말 것" in t2)
ok("지수 없으면 장폭으로", "장폭으로 서술하라" in t2)
ok("일정 없으면 문장 금지", "일정 문장을 쓰지 말 것" in t2)
ok("뉴스 없으면 인과 금지", "인과는 쓰지 말 것" in t2)

print("\n⑨-3 개장일이면 전제가 바뀐다")
f3 = copy.deepcopy(FACTS)
f3["domestic"]["calendar"] = {"today": "20260818", "open": True, "prev": "20260814",
                              "next": "20260819", "gapDays": 0}
t3 = G._facts_text(f3)
ok("개장으로 적는다", "국내 증시 개장" in t3)
ok("휴장 간격 문구는 없다", "여러 번 열리" not in t3)

print("\n⑨-4 개장 여부를 모를 때 — '모른다'를 '휴장'으로 적으면 안 된다")
f4 = copy.deepcopy(FACTS)
f4["domestic"]["calendar"] = {"today": "20260817", "open": None, "prev": None, "next": None}
t4 = G._facts_text(f4)
ok("판정 실패를 그대로 적는다", "개장 여부를 판정하지 못했다" in t4)
ok("휴장이라고 적지 않는다", "국내 증시 휴장" not in t4, t4[:120])

print("\n⑨-0 휴장일에는 브리핑을 만들지 않는다")
OPEN = {"today": "20260818", "open": True, "prev": "20260814", "next": "20260819"}
CLOSED = {"today": "20260817", "open": False, "prev": "20260814", "next": "20260818"}
ok("개장일이면 만든다", G.skip_reason(OPEN) is None)
r = G.skip_reason(CLOSED)
ok("휴장일이면 건너뛴다", r and "만들지 않는다" in r, str(r))
ok("다음 개장일을 알려 준다", r and "20260818" in r)
ok("--allow-closed 면 휴장일에도 만든다", G.skip_reason(CLOSED, allow_closed=True) is None)
ok("판정 실패(None)도 건너뛴다", G.skip_reason({"today": "x", "open": None}) is not None)
ok("달력이 아예 없어도 건너뛴다", G.skip_reason(None) is not None)

print("\n⑨-5 데이터가 묵었으면 발행하지 않는다 — 1차 실행에서 실제로 난 일")
ok("같은 날이면 통과", G.stale_data("20260814", "20260814") is None)
r = G.stale_data("20260814", "20260804")
ok("10일 묵었으면 정지", r and "10일 차이" in r, str(r))
ok("이유에 고칠 곳이 적혀 있다", r and "data/stocks.js" in r)
ok("하루만 어긋나도 정지(기본 0)", G.stale_data("20260814", "20260813") is not None)
ok("값이 없으면 이 검사는 넘어간다", G.stale_data(None, "20260814") is None)
ok("이상한 날짜는 알린다", "읽을 수 없다" in (G.stale_data("2026xxxx", "20260814") or ""))

print("\n⑨-6 시세 날짜가 거래일과 다를 때 — 섞지 말라고 정확히 적는다")
f5 = copy.deepcopy(FACTS)
f5["domestic"]["tradeDate"] = "20260804"
f5["domestic"]["tradeDateKo"] = "8월 4일"
f5["domestic"]["index"]["kospi"]["dateMismatch"] = True
f5["domestic"]["index"]["kospi"]["date"] = "2026-08-14"
t5 = G._facts_text(f5)
ok("다른 날임을 밝힌다", "다른 날이다" in t5, t5[:200])
ok("섞지 말라고 적는다", "한 문단에 섞지 마라" in t5)
ok("어느 쪽을 버릴지 알려 준다", "지수 쪽을 버리고" in t5)
ok("어긋나지 않으면 경고 없다", "다른 날이다" not in G._facts_text(FACTS))

print("\n⑩ 프롬프트 — 못을 박은 규칙이 실제로 들어가는지")
p = G.build_prompt(FACTS)
ok("25% 상한이 프롬프트에 있다", "25%를 넘지 않는다" in p)
ok("분량이 프롬프트에 있다", "2,500~3,000자" in p)
ok("휴장 전제를 알려 준다", "'오늘 장'을 준비하는 글이 아니다" in p)
ok("링크 형식을 지정한다", "[현대차](005380)" in p)
ok("숫자 출처 규칙", "숫자는 시세에서, 이유는 뉴스에서" in p)
ok("유료 구간 보호", "원문을 그대로 옮기지 말고" in p)
ok("사실 블록이 들어 있다", "현대차(005380)" in p)
pr = G.build_prompt(FACTS, retry_note="· 커버리지 섹션이 전체의 41%")
ok("재시도 사유를 붙인다", "같은 실수를 반복하지 마라" in pr and "41%" in pr)

print("\n⑪ 비용 계산")


class U:
    input_tokens = 20000
    output_tokens = 5000


c = G.cost(U(), batch=False)
# opus-5 는 입력 $5 / 출력 $25 — 20K*5 + 5K*25 = 100,000 + 125,000 = $0.225
ok("동기 비용", abs(c["usd"] - 0.225) < 1e-6, str(c))
ok("배치는 반값", abs(G.cost(U(), batch=True)["usd"] - 0.1125) < 1e-6)
ok("키가 없으면 None", G.cost(None) is None)

print("\n" + "=" * 60)
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: {', '.join(FAIL)}")
    sys.exit(1)
print("✅ 전부 통과")
