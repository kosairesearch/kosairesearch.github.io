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
ok("800자짜리 거부", has(G.validate(sample(150, 150, 150, 90)), "분량"))
ok("1,100자짜리는 통과(하한 1,000)", not has(G.validate(sample(300, 300, 300, 200)), "분량"))
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

print("\n⑤-b 틀이 어긋난 글 — 터지지 말고 거부해야 한다")
# 자유롭게 쓰라고 풀었더니 모델이 문단을 {"ko":…,"en":…} 대신 글자로 줬다.
# 예전에는 _walk 가 AttributeError 로 통째로 터져 그날 발행이 막혔을 것이다.
b = copy.deepcopy(base)
b["sections"][0]["paragraphs"] = ["그냥 글자로 온 문단"]
ok("문단이 글자면 거부(안 터짐)", has(G.validate(b), "문단이 객체가 아니다"))
ok("_walk 도 안 터진다", isinstance(list(G._walk(b)), list))
b = copy.deepcopy(base)
b["sections"][0]["heading"] = "글자 제목"
ok("heading 이 글자면 거부", has(G.validate(b), "heading 이"))
b = copy.deepcopy(base)
b["title"] = "글자 제목"
ok("title 이 글자면 거부", has(G.validate(b), "title 가"))
b = copy.deepcopy(base)
b["sections"] = "섹션이 아님"
ok("sections 가 배열이 아니면 거부", has(G.validate(b), "배열이 아니다"))
b = copy.deepcopy(base)
b["sections"][1] = "섹션이 글자"
ok("섹션이 객체가 아니면 거부", has(G.validate(b), "섹션이 객체가 아니다"))
ok("멀쩡한 글은 틀 검사에 안 걸린다", G._shape_bad(copy.deepcopy(base)) == [])

print("\n⑥ 섹션 구조")
# 섹션은 고정하지 않는다. 18일치가 18일 모두 같은 네 칸이었던 것이 "매일
# 같은 글"의 뼈대였다. 무엇을 몇 개, 어떤 순서로 쓸지는 글쓴이가 정한다.
b = copy.deepcopy(base)
b["sections"][0]["id"] = "oil"
ok("처음 보는 섹션 id 도 통과", G.validate(b) == [], str(G.validate(b)))
b = copy.deepcopy(base)
b["sections"][0], b["sections"][3] = b["sections"][3], b["sections"][0]
ok("순서를 바꿔도 통과", G.validate(b) == [], str(G.validate(b)))
b = copy.deepcopy(base)
b["sections"] = b["sections"][:2]
# 칸을 줄이면 분량 하한에 걸린다 — 그건 섹션 규칙이 아니라 별개의 안전선이다.
# 여기서 보려는 건 "칸이 두 개인 것 자체"에 불만이 없는지다.
ok("두 칸만 써도 섹션 구조로는 안 걸린다",
   not any(("섹션" in r and "분량" not in r) for r in G.validate(b)),
   str(G.validate(b)))
b = copy.deepcopy(base)
b["sections"][1]["id"] = b["sections"][0]["id"]
ok("id 가 겹치면 거부", has(G.validate(b), "겹친다"))
b = copy.deepcopy(base)
b["sections"][1]["id"] = ""
ok("id 가 비면 거부", has(G.validate(b), "id 가 없다"))
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

print("\n⑦-4b 섹션 제목의 링크도 본문과 똑같이 다룬다")
# 화면(render_brief.to_html)은 제목에도 링크를 건다. 그런데 repair_links 와
# normalize_links 가 제목을 건너뛰고 있었다 — 그래서 커버리지에 없는 여섯
# 자리를 제목에 쓰면, 없는 종목 페이지로 가는 링크가 그대로 나갔다.
import render_brief as R
b = copy.deepcopy(base)
b["sections"][0]["heading"] = {"ko": "[없는회사](999999) 가 끌어올린 하루",
                               "en": "[Ghost](999999) led the day"}
b["sections"][1]["heading"] = {"ko": "[현대차](005380) 는 그대로 둔다",
                               "en": "[Hyundai](005380) stays"}
b["sections"][2]["heading"] = {"ko": "**삼성전자**(005930) 굵게만 썼다",
                               "en": "**Samsung**(005930) bold only"}
n_fixed = G.repair_links(b)
check("제목의 **이름**(코드) 도 링크로 고친다", n_fixed, 2)
dropped = G.normalize_links(b, COV)
h0 = b["sections"][0]["heading"]
ok("제목의 없는 코드는 평문이 된다", "999999" not in h0["ko"] and "999999" not in h0["en"],
   str(h0))
ok("없는 종목 링크를 화면에 내보내지 않는다",
   "ticker=999999" not in R.to_html(h0["ko"]), R.to_html(h0["ko"]))
ok("있는 종목 링크는 제목에서도 살아 있다",
   'ticker=005380' in R.to_html(b["sections"][1]["heading"]["ko"]))
ok("굵게만 쓴 것도 제목에서 링크가 된다",
   'ticker=005930' in R.to_html(b["sections"][2]["heading"]["ko"]))
ok("떨어낸 제목 링크도 보고한다", any("999999" in x for x in dropped), str(dropped))
# 본문은 예전과 똑같이 동작해야 한다
b2 = copy.deepcopy(base)
b2["sections"][3]["paragraphs"][0]["ko"] = "[현대차](005380) 는 올랐다."
check("제목을 보게 해도 본문 처리는 그대로", G.normalize_links(b2, COV), [])

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
ok("정말 긴 제목은 거부(45자 이상)",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다",
                                   "18일이 두 번을 받는다",
                                   "현대차그룹 세 곳의 반기보고서가 어제 한꺼번에 접수되면서 확인 지점이 한 번에 걸렸다")),
       "문장이다"))
# 9월 18일에 2차 글이 소제목 45자 하나로 거부돼 $0.3 를 버리고 그날 브리핑을
# 놓칠 뻔했다. 1차는 44자 그대로 막고, 2차(slack=HEAD_SLACK)는 4자 여유를 준다.
_long = "반도체와자동차가같은날반대로움직인이유는환율과유가가운데어느쪽인가하는물음이다그답은아직없고내일도없을것이다"
assert len(_long) >= 49, len(_long)
_h45, _h48, _h49 = _long[:45], _long[:48], _long[:49]
ok("45자 소제목 — 1차(여유 없음)는 거부",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다", _h45)),
       "문장이다"))
ok("45자 소제목 — 2차(여유 4자)는 통과",
   not has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다", _h45),
                            slack=G.HEAD_SLACK), "문장이다"))
ok("48자 — 2차는 통과(여유의 끝)",
   not has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다", _h48),
                            slack=G.HEAD_SLACK), "문장이다"))
ok("49자 — 2차에도 거부(여유를 넘었다)",
   has(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다", _h49),
                        slack=G.HEAD_SLACK), "문장이다"))
ok("여유는 4자로 고정", G.HEAD_SLACK == 4 and G.HEAD_MAX == 44)

# ── 수리(repair): 1차 글이 검사에 걸리면 Opus 로 다시 쓰지 않고 걸린 자리만
#    Sonnet 으로 고친다. 여기서는 API 없이 조각을 끼우는 부분만 본다. ──
_b = copy.deepcopy(good)
_b["lead"]["en"] = ""
_paths = {p for p, _ in G._walk(_b)}
ok("경로 목록에 lead.en 과 섹션 문단이 있다",
   "lead.en" in _paths and any(p.endswith(".p0.ko") for p in _paths), str(sorted(_paths))[:200])
_sid = _b["sections"][0]["id"]
_n = G.apply_patch(_b, {"lead.en": "The Fed hiked; yields eased.",
                        f"{_sid}.heading.ko": "새 제목",
                        f"{_sid}.p0.en": "New first paragraph.",
                        "없는.경로.ko": "버려야 한다", "title.ko": "   ", "summary.en": 42})
ok("아는 경로 셋만 들어간다(모르는 경로·빈 값·글자 아닌 값은 버린다)", _n == 3, str(_n))
ok("lead.en 이 채워졌다", _b["lead"]["en"] == "The Fed hiked; yields eased.")
ok("섹션 제목·문단이 바뀌었다",
   _b["sections"][0]["heading"]["ko"] == "새 제목" and _b["sections"][0]["paragraphs"][0]["en"] == "New first paragraph.")
ok("다른 자리는 그대로", _b["sections"][0]["paragraphs"][0]["ko"] == good["sections"][0]["paragraphs"][0]["ko"])
ok("patch 가 객체가 아니면 0", G.apply_patch(copy.deepcopy(good), ["x"]) == 0 and G.apply_patch(copy.deepcopy(good), None) == 0)
# 9/21 시험: 수리 모델이 조각 대신 글 전체를 돌려줘 0곳으로 끝났다. 이제는 원문과
# 다른 자리만 골라 끼운다. 그리고 사유가 가리킨 자리 밖은 손대지 못한다.
_orig = copy.deepcopy(good)
_whole = copy.deepcopy(good)
_whole["lead"]["en"] = "Whole-document echo: new lead."
_whole["sections"][0]["paragraphs"][0]["ko"] = "통째로 돌려준 글의 바뀐 문단."
_whole["sections"][1]["heading"]["ko"] = "사유에 없는 자리를 멋대로 바꿈"
_t = copy.deepcopy(_orig); _ch = []
_sid0, _sid1 = good["sections"][0]["id"], good["sections"][1]["id"]
ok("글 전체가 와도 바뀐 자리 셋을 조각으로 끼운다",
   G.apply_patch(_t, _whole, None, _ch) == 3 and set(_ch) == {"lead.en", f"{_sid0}.p0.ko", f"{_sid1}.heading.ko"}, str(_ch))
_allow = G._allowed_paths(_orig, ["lead.en 가 비었다", f"{_sid0}.p0 에 종목 링크 7개 · 등락률 10개 — 나열이다"])
ok("사유가 가리킨 자리(lead·그 문단)의 ko·en 만 허용", {"lead.ko", "lead.en", f"{_sid0}.p0.ko", f"{_sid0}.p0.en"} <= _allow and f"{_sid1}.heading.ko" not in _allow, str(sorted(_allow)))
_t = copy.deepcopy(_orig); _ch = []
ok("허용 밖(다른 섹션 제목)은 버린다", G.apply_patch(_t, _whole, _allow, _ch) == 2 and _t["sections"][1]["heading"]["ko"] == _orig["sections"][1]["heading"]["ko"], str(_ch))
ok("제목 사유는 heading 을, '요약' 사유는 summary 를 연다",
   f"{_sid1}.heading.ko" in G._allowed_paths(_orig, [f"섹션 {_sid1} 제목에 '이번 주' — …"])
   and "summary.en" in G._allowed_paths(_orig, ["요약에 글머리표·번호가 있다"]))
ok("분량 사유면 전부 연다", G._allowed_paths(_orig, ["분량 3,700자 — 1,000~3,600자를 벗어났다"]) == {p for p, _ in G._walk(_orig)})
_u = type("Usage", (), {"input_tokens": 20000, "output_tokens": 5000})()   # 아래 ⑬의 U() 와 같은 값
ok("수리 모델은 Sonnet · 값이 그 단가로 계산된다 (2만/5천 토큰 → $0.135, Opus 면 $0.225)",
   G.REPAIR_MODEL == "claude-sonnet-5" and abs(G.cost(_u, model="claude-sonnet-5")["usd"] - 0.135) < 1e-6
   and abs(G.cost(_u)["usd"] - 0.225) < 1e-6, str(G.cost(_u, model="claude-sonnet-5")))
ok("출력 한도 24,000 — 사고 토큰까지 담는다", G.MAX_TOKENS >= 24000)
# 30자 상한이 "A는 올랐고 B는 내렸다" 식 짧은 대비 제목만 살아남게 했다.
ok("35자 제목은 이제 통과",
   G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다",
                               "유가가 100달러를 넘은 자리에서 정유와 항공이 갈라섰다")) == [],
   str(G.check_headings(with_heads("반도체는 비켜갔다", "지수는 올랐다", "18일이 두 번을 받는다",
                                   "유가가 100달러를 넘은 자리에서 정유와 항공이 갈라섰다"))))
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

print("\n⑨-b 일정이 말라 있으면 재료가 그렇다고 말하는가")
# 9월 11일 브리핑이 "앞으로 2주 일정은 FOMC 하나뿐"이라고 썼다. 정말
# 하나뿐인 게 아니라 수동 등록이 8월 27일에 멈춰 있었다. 모델은 알 길이
# 없었다. 이제 불완전하다는 사실 자체를 재료에 실어 보낸다.
import copy as _copy
_f = _copy.deepcopy(FACTS)
_f["schedule"] = {"from": "2026-09-12", "to": "2026-09-26", "events": [],
                  "health": {"ok": False, "thin": True,
                             "problems": ["수동 등록: 앞으로 잡힌 것이 하나도 없다",
                                          "앞으로 14일에 0건뿐이다"]}}
_t = G._facts_text(_f)
ok("불완전하다고 적는다", "이 일정 목록은 불완전하다" in _t)
ok("빠진 사유를 그대로 넘긴다", "앞으로 14일에 0건뿐이다" in _t)
ok("'일정이 없다'를 사실로 쓰지 말라고 적는다", "시장의 사실로 쓰지 마라" in _t)
_f["schedule"]["events"] = [{"date": "2026-09-16", "kind": "FOMC",
                             "title": "9월 FOMC 회의 종료"}]
_f["schedule"]["health"] = {"ok": True, "thin": False, "problems": []}
ok("멀쩡하면 경고를 붙이지 않는다", "불완전하다" not in G._facts_text(_f))

print("\n⑨-b2 수집이 '통째로' 터진 경우가 제일 조용하면 안 된다")
# 일부만 실패하면 "불완전하다" 경고가 붙는데, 통째로 실패하면(collect 가
# 예외를 던지면) 예전에는 schedule=None 이 되어 경고가 아예 안 붙었다.
# 제일 나쁜 경우가 제일 조용한 뒤집힌 구조였다.
import io as _io, contextlib as _ctx
import calendar_data as _cd, news_data as _nd
_boom = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("사이트 모양이 바뀌었다"))
_cd_save, _nd_save = _cd.collect, _nd.collect
_cd.collect, _nd.collect = _boom, _boom
try:
    _out = _io.StringIO()
    with _ctx.redirect_stderr(_io.StringIO()), _ctx.redirect_stdout(_out):
        _fx, _fatal = G.gather(skip_news=False)
finally:
    _cd.collect, _nd.collect = _cd_save, _nd_save
_warns = [l for l in _out.getvalue().split("\n") if "::warning" in l]
ok("통째로 터져도 발행을 막지는 않는다", _fatal is None, str(_fatal))
ok("일정이 통째로 터지면 워크플로에 경고가 뜬다",
   any("일정 수집" in w for w in _warns), str(_warns))
ok("뉴스가 통째로 터져도 경고가 뜬다",
   any("뉴스 수집" in w for w in _warns), str(_warns))
_tx = G._facts_text(_fx)
ok("통째로 터진 것도 '불완전하다'고 재료에 적는다", "이 일정 목록은 불완전하다" in _tx)
ok("'일정이 없다'를 사실로 쓰지 말라고 적는다", "없는 것을 없다고 말하지 마라" in _tx)

print("\n⑨-c 뉴스를 '안 받은 것'과 '못 받은 것'을 구분하는가")
# --facts-only 는 공짜 미리보기라 일부러 뉴스를 건너뛴다. 그런데 결과가
# "한 건도 받지 못했다"로 찍혀 막힌 것처럼 보였다. 일정에서 당한 것과
# 같은 병이라 같이 고친다.
_g = _copy.deepcopy(FACTS)
_g["news"] = None
ok("정말 못 받았으면 그렇게 적는다", "한 건도 받지 못했다" in G._facts_text(_g))
_g["news"] = {"skipped": True, "groups": {}, "tickers": {}}
_t2 = G._facts_text(_g)
ok("일부러 건너뛴 것은 그렇게 적는다", "일부러 받지 않았다" in _t2)
ok("건너뛴 것을 '못 받았다'고 하지 않는다", "한 건도 받지 못했다" not in _t2)
ok("미리보기만 보고 판단하지 말라고 적는다", "뉴스가 없다'고 판단하지 말 것" in _t2)

print("\n⑩ 프롬프트 — 못을 박은 규칙이 실제로 들어가는지")
p = G.build_prompt(FACTS)
ok("커버리지 비중 제한이 프롬프트에 있다", "4분의 1을 넘지 않게" in p)
# 여기부터는 "매일 같은 글"을 고치려고 새로 넣은 것들이다.
ok("무엇을 쓸지 고르라고 말한다", "네가 고른다" in p)
ok("칸을 못 박지 않는다", "정해진 틀이 없다" in p)
ok("미국부터 시작할 이유가 없다고 적는다", "미국 지수부터" in p)
ok("대비 제목을 그만하라고 적는다", "A는 올랐고 B는 내렸다" in p)
ok("이어지는 이야기를 권한다", "이어지는 이야기는 환영한다" in p)
ok("사실 블록의 지시문을 글에 옮겨 적지 말라고 한다",
   "옮겨 적지 마라" in p and "독자에게 할 말이" in p, p[-600:])

print("\n⑩-b 최근 브리핑은 '실제로 올라간 것'만 보여주는가")
# 품질 확인용으로 발행 없이 돌린 초안이 남는다. 그것까지 "이미 나간 글"
# 이라고 내밀면 아무도 못 본 글을 피해 쓰게 된다.
import json as _json
import tempfile as _tf
from pathlib import Path as _P
_dir = _P(_tf.mkdtemp())


def _brief(day, title, published):
    (_dir / f"2026-09-{day:02d}.json").write_text(_json.dumps({
        "date": f"2026-09-{day:02d}",
        "title": {"ko": title, "en": "x"},
        "lead": {"ko": "리드", "en": "x"},
        "sections": [{"id": "us", "heading": {"ko": "제목", "en": "x"},
                      "paragraphs": [{"ko": "본문", "en": "x"}]}],
        "meta": ({"publishedAt": "2026-09-01T07:28+09:00"} if published else {}),
    }, ensure_ascii=False), encoding="utf-8")


for _d in range(1, 10):
    _brief(_d, f"올라간 글 {_d}", True)
_brief(10, "안 올라간 초안", False)
_old_dir, G.OUT_DIR = G.OUT_DIR, _dir
try:
    _t = G.recent_briefs("2026-09-11", 7)
    ok("올라간 글만 보여준다", "안 올라간 초안" not in _t)
    ok("7개로 자른다", _t.count("[2026-09-") == 7, str(_t.count("[2026-09-")))
    ok("가장 최근 것이 들어 있다", "올라간 글 9" in _t)
    ok("거르기 전에 자르지 않는다 (초안이 섞여도 7개를 채운다)",
       "올라간 글 3" in _t, _t[:200])
    _brief(10, "안 올라간 초안", False)
    for _d in range(1, 10):
        (_dir / f"2026-09-{_d:02d}.json").unlink()
    ok("올라간 글이 하나도 없으면 아무것도 안 붙인다",
       G.recent_briefs("2026-09-11", 7) == "")
finally:
    G.OUT_DIR = _old_dir
ok("칸마다 글자 수를 배정하지 않는다",
   not any(x in p for x in ("약 700자", "약 650자", "약 600자")))
# 칸별 배정은 없애되 전체 분량은 알려 줘야 한다. 목표를 모른 채 쓰다 상한을
# 넘기면 거부 → 다시 쓰기가 되고, 최악이면 그날 발행이 막힌다.
ok("전체 분량은 알려 준다 (상한 2,800자 · 하한 1,000자)", "길어도 2,800자" in p and "1,000자" in p)
ok("상한을 넘기면 어떻게 되는지도 알려 준다", "발행되지 않는다" in p)
ok("날마다 길이가 달라도 된다고 적는다", "같은 길이일 이유가 없다" in p)
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

print("\n⑫ 렌더러 — 문단 나누기")

# 여태 이 파일은 생성기만 봤고 렌더러는 아무도 안 봤다. 그래서 2026-08-25
# 브리핑이 발행되지 못했다. 글은 06:23 에 멀쩡히 만들어졌는데 07:28 발행
# 슬롯에서 render_brief.chunk_text 가 IndexError 로 죽었고, 예비 슬롯도 같은
# 곳에서 죽었다. 생성은 성공했으니 '브리핑 생성 실패' 알림도 안 왔다.
#
# 원인은 한 줄이었다.
#     out[-2] = out[-2] + " " + out.pop()
# 파이썬은 오른쪽을 먼저 계산하고 왼쪽 첨자를 그 뒤에 본다. pop 이 리스트를
# 줄인 뒤 out[-2] 를 평가하므로 조각이 둘이면 죽고 셋 이상이면 한 칸 앞
# 문단에 갖다 붙인다. 같은 로직의 자바스크립트 판(stock.html)은 += 의 왼쪽
# 참조를 먼저 잡아서 멀쩡했다 — 옮겨 적을 때 평가 순서를 놓쳤다.
import render_brief as R

# 조각이 정확히 둘이고 마지막이 짧을 때. 여기가 죽던 자리다.
_two = "코스피가 어제보다 올랐다. " * 12 + "짧다."
_r = R.chunk_text(_two, R.PARA_KO)
ok("조각 2개 + 짧은 꼬리에서 죽지 않는다", bool(_r) and all(_r), str(_r)[:120])

# 조각이 셋 이상일 때 문장이 사라지거나 딴 문단에 복사되지 않는지.
# 문장마다 고유한 표식을 넣는다('1번'이 '11번'에 겹치지 않도록 <n> 로 감쌈).
_sents = [f"<{i}> 이 문장은 여기에 있다." for i in range(1, 40)]
_r3 = R.chunk_text(" ".join(_sents), R.PARA_KO)
_joined = " ".join(_r3)
ok("조각 3개 이상 — 문장 유실 없음",
   all(s in _joined for s in _sents),
   f"조각 {len(_r3)}개")
ok("조각 3개 이상 — 문단 중복 복사 없음",
   all(_joined.count(f"<{i}>") == 1 for i in range(1, 40)))

ok("빈 문단은 조각도 없다", R.chunk_text("", R.PARA_KO) == [])
ok("한 문장은 자르지 않는다", len(R.chunk_text("한 문장뿐이다.", R.PARA_KO)) == 1)

# 한국어와 영어는 반드시 같은 개수로 잘려야 한다. 개수가 어긋나면 잘린
# 조각이 사전에 없어 영어 모드에서 그 문단만 한국어로 남는다.
_ko = "".join(f"{i}번째 문장이 여기 있다. " for i in range(1, 25))
_en = "".join(f"This is sentence number {i}. " for i in range(1, 25))
_pairs = R.chunk_pair(_ko, _en)
ok("한국어·영어 조각 수가 같다", bool(_pairs) and all(k and e for k, e in _pairs),
   f"{len(_pairs)}쌍")

# 영어 문장이 조각 수보다 적으면 자르지 않고 통째로 둔다(짝을 못 맞추느니).
_pairs2 = R.chunk_pair(_ko, "One long English sentence without any splits at all.")
ok("영어가 모자라면 짝을 깨지 않는다",
   all(k and e for k, e in _pairs2), str(len(_pairs2)))


# ────────── ⑯ 요일·주 범위, 업종, 환율 기준 — 9월 14일 브리핑에서 새어 나간 것들 ──────────
#
# 9/14(월) 발행분이 (1) 9/21(다음 주 월) 시한을 제목에서 '이번 주 안에' 라고
# 썼고, (2) 반도체 장비주 다섯 옆에 전자·부품(삼화콘덴서)을 '같은 부품' 으로
# 붙였다. 둘 다 사실 블록에 답이 없어서 모델이 짐작한 자리다. 답을 사실
# 블록에 적어 주고, 그래도 틀리면 검사가 거부한다.

print("\n⑯ 요일·주 범위가 사실 블록에 적힌다")
F16 = copy.deepcopy(FACTS)
F16["domestic"]["calendar"] = {"today": "20260914", "open": True, "prev": "20260911",
                               "next": "20260915", "gapDays": 2}
F16["domestic"]["movers"] = {
    "leaders": [{"ticker": "000810", "name": "삼성화재", "sector": "보험",
                 "change": 6.03, "rel": 7.79, "tradingValue": 1200}],
    "laggards": [], "up": [
        {"ticker": "001820", "name": "삼화콘덴서", "sector": "전자·부품",
         "change": 18.76, "rel": 20.52, "tradingValue": 5435}],
    "down": [{"ticker": "042700", "name": "한미반도체", "sector": "반도체",
              "change": -8.70, "rel": -6.94, "tradingValue": 3000},
             {"ticker": "348210", "name": "넥스틴", "sector": "반도체",
              "change": -8.42, "rel": -6.66, "tradingValue": 900}],
    "actives": []}
F16["domestic"]["filings"] = [{"ticker": "001470", "name": "삼부토건", "report": "사업보고서",
    "mcap": 0.2, "totalFilings": 3,
    "checkpoints": [{"when": "2026년 9월 21일까지", "what": "거래소 기업심사위원회 심의 대상 여부 결정"}]}]
F16["markets"]["ust10y"] = {"label": "미 10년물", "close": 4.97, "prev": 4.94,
                            "change": 0.63, "date": "2026-09-11", "unit": "%"}
F16["markets"]["usdkrw"] = {"label": "원/달러", "close": 1344.15, "prev": 1348.19,
                            "change": -0.30, "date": "2026-09-14", "unit": "원"}
F16["schedule"] = {"from": "2026-09-14", "to": "2026-09-28",
                   "events": [{"date": "2026-09-16", "kind": "FOMC", "title": "9월 FOMC 회의 종료"},
                              {"date": "2026-09-21", "kind": "기타", "title": "삼부토건 심의 시한"}]}
t16 = G._facts_text(F16)
ok("오늘 요일을 적는다", "오늘 9월 14일(월)" in t16, t16[:300])
ok("이번 주 범위를 적는다", "이번 주 9월 14일(월)~9월 20일(일)" in t16)
ok("다음 주 시작을 적는다", "9월 21일(월)부터 다음 주" in t16)
ok("일정에 요일·주 꼬리표", "2026-09-16(수·이번 주)" in t16 and "2026-09-21(월·다음 주)" in t16, t16)
ok("확인 지점 날짜에 주 꼬리표", "9월 21일(월), 다음 주" in t16)
ok("종목 괄호에 업종", "한미반도체(042700·반도체)" in t16 and "삼화콘덴서(001820·전자·부품)" in t16)
ok("묶을 때 규칙을 적는다", "업종이 같을 때만" in t16)
ok("10년물을 %p 로도 적는다", "4.94% → +0.03%p" in t16, t16)
ok("환율 직전값·시계열을 밝힌다", "직전 값 1,348.19원 대비" in t16 and "KRW=X" in t16)
ok("환율을 마감가와 견주지 말라고 적는다", "서울 외환시장 마감가와 다른 시계열" in t16)

print("\n⑯-2 주(週) 계산 자체")
_d = _dt.date
ok("월요일 기준 이번 주", G.week_tag(_d(2026, 9, 20), _d(2026, 9, 14)) == "이번 주")
ok("다음 주 월요일은 다음 주", G.week_tag(_d(2026, 9, 21), _d(2026, 9, 14)) == "다음 주")
ok("지난 금요일은 지난 주", G.week_tag(_d(2026, 9, 11), _d(2026, 9, 14)) == "지난 주")
ok("일요일도 같은 주에 든다", G.week_tag(_d(2026, 9, 14), _d(2026, 9, 20)) == "이번 주")
ok("2주 뒤는 그 다음", G.week_tag(_d(2026, 9, 28), _d(2026, 9, 14)) == "그 다음")

print("\n⑯-3 '이번 주' 가 틀리면 거부한다")
b = sample()
b["sections"][3]["heading"] = {"ko": "삼부토건, 이번 주 안에 거래소 결정이 걸려 있다",
                               "en": "Sambu: exchange decision due this week"}
b["sections"][3]["paragraphs"][0]["ko"] = ("9월 12일자 리포트는 9월 21일까지를 확인 지점으로 적어 뒀다. "
                                          "[삼부토건](001470). " + b["sections"][3]["paragraphs"][0]["ko"])
b["sections"][3]["paragraphs"][0]["en"] = "The Sept 12 report flags Sept 21. [Sambu](001470). " + b["sections"][3]["paragraphs"][0]["en"]
r = G.validate(b, facts=F16)
ok("제목의 '이번 주' 를 본문 날짜로 잡아낸다", has(r, "이번 주") and has(r, "다음 주"), str(r))
b2 = copy.deepcopy(b)
b2["sections"][3]["heading"]["ko"] = "삼부토건, 다음 주 월요일까지 거래소 결정이 걸려 있다"
ok("맞게 고치면 통과", not has(G.validate(b2, facts=F16), "이번 주"), str(G.validate(b2, facts=F16)))
b3 = sample()
b3["lead"]["ko"] = "9월 21일 결정이 이번 주 안에 나온다. " + b3["lead"]["ko"]
ok("같은 문장 안의 날짜로도 잡는다", has(G.validate(b3, facts=F16), "lead.ko"), str(G.validate(b3, facts=F16)))
b4 = sample()
b4["lead"]["ko"] = "이번 주는 조용하다. " + b4["lead"]["ko"]
ok("날짜가 없는 '이번 주' 는 건드리지 않는다", not has(G.validate(b4, facts=F16), "이번 주"))
ok("달력이 없으면 검사하지 않는다", G.check_weeks(b, {}) == [])
b4b = sample()
b4b["lead"]["ko"] = "지난 주 9월 11일에 판 뒤, 이번 주 9월 16일에 FOMC 가 끝난다. " + b4b["lead"]["ko"]
ok("한 문장에 '지난 주 …'·'이번 주 …' 가 같이 와도 헛걸리지 않는다",
   not has(G.validate(b4b, facts=F16), "lead.ko"), str(G.validate(b4b, facts=F16)))
b4c = sample()
b4c["summary"]["ko"] = "국내도 같은 자리가 눌렸는데, 지수를 끌어내린 무게가 상위에 몰렸다. " + b4c["summary"]["ko"]
ok("'같은 자리' 같은 관용구는 업종 묶음으로 보지 않는다",
   not has(G.validate(b4c, facts=F16), "묶었다"))

# ⑯-3b 9/14 낮 시험 생성에서 실제로 난 일 — "9월 12일(토) 공시가 … 다음 주
# 월요일까지" 를 두 번 다 거부해 그날 글이 안 만들어졌다. 옛 방식은 문장 안에서
# 가장 가까운 낱말과 날짜를 무조건 짝지었다. 이제는 바로 옆에 붙은 날짜만 본다.
print("\n⑯-3b 멀리 있는 날짜와는 짝짓지 않는다 — 거짓 거부 하나가 그날 브리핑을 지운다")
def _lead(text):
    x = sample()
    x["lead"]["ko"] = text + " " + x["lead"]["ko"]
    return G.validate(x, facts=F16)
ok("'9월 12일(토) 공시가 나왔고, 다음 주 월요일까지' 는 통과 (실제 거부됐던 문장)",
   not has(_lead("9월 12일(토) 공시가 나왔고, 다음 주 월요일까지 거래소 결정이 걸려 있다."), "lead.ko"),
   str(_lead("9월 12일(토) 공시가 나왔고, 다음 주 월요일까지 거래소 결정이 걸려 있다.")))
ok("'이번 주 후반부터 9월 24일 연휴' 는 통과 (부터 = 다른 시점)",
   not has(_lead("이번 주 후반부터 9월 24일 추석 연휴가 시작된다."), "lead.ko"))
ok("'9월 12일 공시 뒤 다음 주에' 는 통과 (뒤 = 다른 시점)",
   not has(_lead("9월 12일 공시 뒤 다음 주에 결정된다."), "lead.ko"))
ok("'다음 주 월요일(9월 21일)' 은 통과", not has(_lead("다음 주 월요일(9월 21일)에 결정된다."), "lead.ko"))
ok("'이번 주 월요일(9월 21일)' 은 거부 — 옆에 붙은 날짜는 본다",
   has(_lead("이번 주 월요일(9월 21일)에 결정된다."), "lead.ko"))
ok("'이번 주에는 9월 16일(수)' 은 통과", not has(_lead("이번 주에는 9월 16일(수) FOMC 가 있다."), "lead.ko"))
ok("'9월 21일 결정이 이번 주 안에' 는 여전히 거부", has(_lead("9월 21일 결정이 이번 주 안에 나온다."), "lead.ko"))
# 9/21 시험 생성: "이번 주에는 없고 9월 29일 JOLTS" 를 짝지어 걸었다. '없·비어' 사이면 다른 시점이다.
ok("'이번 주에는 없고 9월 21일 결정' 은 통과 (없고 = 다른 시점)", not has(_lead("미국 지표는 이번 주에는 없고 9월 21일 결정이 먼저다."), "lead.ko"),
   str(_lead("미국 지표는 이번 주에는 없고 9월 21일 결정이 먼저다.")))
ok("'이번 주 비어 있고 9월 21일' 도 통과", not has(_lead("일정은 이번 주 비어 있고 9월 21일 GDP 가 나온다."), "lead.ko"))
# 제목이 '다음 주 월요일까지' 처럼 요일까지 박은 것은 본문 날짜가 전부 지난 주여도 틀린 게 아니다.
b8 = sample()
b8["sections"][3]["heading"] = {"ko": "삼부토건, 다음 주 월요일까지 거래소 결정이 걸려 있다",
                                "en": "Sambu: exchange decision due by next Monday"}
b8["sections"][3]["paragraphs"][0]["ko"] = ("9월 12일(토)에 나온 공시가 있다. 거래소 결정은 다음 주 월요일까지 걸려 있다. "
                                           "[삼부토건](001470). " + b8["sections"][3]["paragraphs"][0]["ko"])
b8["sections"][3]["paragraphs"][0]["en"] = "Filed Sept 12. Decision due next Monday. [Sambu](001470). " + b8["sections"][3]["paragraphs"][0]["en"]
ok("제목 '다음 주 월요일까지' + 본문 날짜가 9월 12일뿐이어도 통과",
   not has(G.validate(b8, facts=F16), "다음 주"), str(G.validate(b8, facts=F16)))
b9 = copy.deepcopy(b8)
b9["sections"][3]["heading"]["ko"] = "삼부토건, 이번 주 결정을 기다린다"
ok("제목 '이번 주' 인데 본문은 '다음 주 월요일까지' 면 거부", has(G.validate(b9, facts=F16), "이번 주"),
   str(G.validate(b9, facts=F16)))
# 2차 시도에서는 문장 검사로 글을 막지 않는다 — 경고만 남기고 내보낸다.
b10 = sample()
b10["lead"]["ko"] = "9월 21일 결정이 이번 주 안에 나온다. " + b10["lead"]["ko"]
ok("1차(기본)는 거부", has(G.validate(b10, facts=F16), "이번 주"))
ok("2차(strict_text=False)는 통과", not has(G.validate(b10, facts=F16, strict_text=False), "이번 주"))
# 9/21 에 실제로 난 일 — 제목 "이번 주 미 지표는 비어 있고, 다음 주 29일부터 넷이
# 몰린다" 를 앞 낱말('이번 주')만 보고 걸어 $0.05 수리를 헛되이 썼다. 제목의 주
# 낱말 가운데 하나라도 본문 날짜와 맞으면 제목은 맞는 것이다.
b11 = sample()
b11["sections"][3]["heading"] = {"ko": "이번 주 미 지표는 비어 있고, 다음 주 21일부터 넷이 몰린다",
                                 "en": "No US data this week; four land next week from the 21st"}
b11["sections"][3]["paragraphs"][0]["ko"] = ("이번 주에는 확인할 미국 지표가 없다. 다음 주 9월 21일 구인·이직, "
                                            "9월 22일 GDP 가 나온다. " + b11["sections"][3]["paragraphs"][0]["ko"])
b11["sections"][3]["paragraphs"][0]["en"] = ("No US data this week. Next week Sept 21 JOLTS, Sept 22 GDP. "
                                            + b11["sections"][3]["paragraphs"][0]["en"])
ok("제목에 '이번 주'와 '다음 주'가 같이 있고 본문 날짜가 다음 주면 통과 (9/21 실제 오탐)",
   not has(G.validate(b11, facts=F16), "제목에"), str(G.validate(b11, facts=F16)))
b12 = copy.deepcopy(b11)
b12["sections"][3]["heading"]["ko"] = "이번 주 안에 미 지표 넷이 몰린다"
ok("제목이 '이번 주' 뿐인데 본문 날짜가 다음 주면 여전히 거부",
   has(G.validate(b12, facts=F16), "제목에"), str(G.validate(b12, facts=F16)))

# ⑯-5 나열 — 9/21 사장: "너무 나열하는 느낌이 강하다". 그날 글의 문단 그대로.
print("\n⑯-5 종목·등락률을 늘어놓으면 잡는다 (2차에는 막지 않는다)")
_listy = ("업종 상위는 전기장비 5.48%, 반도체 4.66%, 전자·부품 3.35% 순이었다. [SK하이닉스](000660)가 6.42% "
          "오르며 하루 거래대금 8조 7,781억원을 혼자 소화했고, [삼성전자](005930)는 3.37% 올라 4조 5,543억원이 "
          "붙었다. [SK스퀘어](402340)는 7.04%로 대형주 중 가장 앞섰다. 같은 전기장비 안에서는 [가온전선](000500)이 "
          "25.53%, [LS ELECTRIC](010120)이 4.70% 올랐고, 옆 업종인 전자·부품에서 [대한광통신](010170)이 13.58%, "
          "지주로 분류된 [LS에코에너지](229640)가 14.15% 상승해 전선·전력 쪽 이름들이 함께 움직였다.")
_tight = ("업종 상위는 전기장비 5.48%, 반도체 4.66% 였다. [SK하이닉스](000660)가 6.42% 오르며 거래대금 8조 7,781억원을 "
          "혼자 소화했고 [삼성전자](005930)가 3.37% 따라왔다. 전선·전력 쪽에서는 [가온전선](000500)이 25.53% 뛰며 "
          "업종 전체가 함께 움직였다.")
b13 = sample()
b13["sections"][0]["paragraphs"][0]["ko"] = _listy
b13["sections"][0]["paragraphs"][0]["en"] = "[SK Hynix](000660) [Samsung](005930) [SK Square](402340) [Gaon](000500) [LS ELECTRIC](010120) [Daehan](010170) [LS Eco](229640) rose."
r13 = G.check_listing(b13)
ok("링크 7개·등락률 10개 문단은 나열로 잡힌다", has(r13, "나열이다") and "링크 7개" in str(r13) and "등락률 10개" in str(r13), str(r13))
ok("1차(기본)는 거부 사유에 든다", has(G.validate(b13, facts=F16), "나열이다"))
ok("2차(strict_text=False)는 막지 않는다", not has(G.validate(b13, facts=F16, strict_text=False), "나열이다"))
b14 = sample()
b14["sections"][0]["paragraphs"][0]["ko"] = _tight
b14["sections"][0]["paragraphs"][0]["en"] = "[SK Hynix](000660) [Samsung](005930) [Gaon](000500) rose."
ok("링크 3개·등락률 5개로 줄인 문단은 통과", G.check_listing(b14) == [], str(G.check_listing(b14)))
b15 = sample()
b15["sections"][0]["paragraphs"][0]["ko"] = "S&P 500이 0.17%, 나스닥이 0.39% 오르는 동안 반도체 지수만 2.78% 뛰었고 VIX는 4.08% 내렸다. 마이크론이 3.92%, 엔비디아가 1.34% 올랐다. 다우는 0.18% 내렸다."
ok("등락률 7개(경계)는 통과 — 한두 개 차이로 수리를 부르지 않는다", G.check_listing(b15) == [], str(G.check_listing(b15)))
b16 = sample()
b16["summary"]["ko"] = "A 1%, B 2%, C 3%, D 4%, E 5%, F 6%, G 7%, H 8%, I 9%, J 10% 올랐다."
ok("요약에 등락률 10개면 나열", has(G.check_listing(b16), "summary.ko"))
ok("요약 등락률 9개까지는 둔다", G.check_listing({**sample(), "summary": {"ko": "A 1%, B 2%, C 3%, D 4%, E 5%, F 6%, G 7%, H 8%, I 9%.", "en": "x"}}) == [])
# 9/21 시험 생성: 요약 가운데의 줄표(" — ")를 글머리표로 보고 거부했다. 줄표는 문장부호다.
ok("요약 가운데 줄표는 글머리표가 아니다", not G.SUM_LIST.search("유가는 내렸다 — 금리는 남았다. 원화는 7일째 밀렸다."))
ok("가운뎃점 목록('· 항목')은 여전히 잡는다", bool(G.SUM_LIST.search("유가 · 금리 · 환율 순으로 본다 · 반도체")))
ok("번호 목록('1. ')도 잡는다", bool(G.SUM_LIST.search("볼 것은 셋이다. 1. 유가 2. 금리")))
ok("2차에도 제목 검사(길이·번역체)는 그대로 — 검사 자체가 꺼진 게 아니다",
   has(G.validate({**sample(), "sections": [dict(sample()["sections"][0], heading={"ko": "볼 것", "en": "x"})]},
                  facts=F16, strict_text=False), "볼 것"))

print("\n⑯-4 업종이 다른 종목을 '같은 …' 으로 묶으면 거부한다")
b5 = sample()
b5["sections"][1]["paragraphs"][0]["ko"] = (
    "[한미반도체](042700) -8.70%, [넥스틴](348210) -8.42%였다. "
    "다만 같은 부품 안에서도 [삼화콘덴서](001820)가 18.76% 오르며 상위권에 들었다. "
    + b5["sections"][1]["paragraphs"][0]["ko"])
b5["sections"][1]["paragraphs"][0]["en"] = (
    "[Hanmi](042700) fell 8.70% and [Nextin](348210) 8.42%. Within the same parts group "
    "[Samwha Capacitor](001820) rose 18.76%. " + b5["sections"][1]["paragraphs"][0]["en"])
r5 = G.validate(b5, facts=F16)
ok("반도체+전자·부품을 '같은 부품' 으로 묶은 것을 잡는다", has(r5, "같은 부품") and has(r5, "전자·부품"), str(r5))
b6 = copy.deepcopy(b5)
b6["sections"][1]["paragraphs"][0]["ko"] = b6["sections"][1]["paragraphs"][0]["ko"].replace(
    "다만 같은 부품 안에서도", "다만 옆 업종인 전자·부품에서는")
ok("다르다고 쓰면 통과", not has(G.validate(b6, facts=F16), "묶었다"), str(G.validate(b6, facts=F16)))
b7 = sample()
b7["sections"][1]["paragraphs"][0]["ko"] = (
    "같은 반도체 안에서 [한미반도체](042700)와 [넥스틴](348210)이 나란히 밀렸다. "
    + b7["sections"][1]["paragraphs"][0]["ko"])
b7["sections"][1]["paragraphs"][0]["en"] = "[Hanmi](042700) and [Nextin](348210). " + b7["sections"][1]["paragraphs"][0]["en"]
ok("업종이 같으면 묶어도 된다", not has(G.validate(b7, facts=F16), "묶었다"), str(G.validate(b7, facts=F16)))
ok("업종 정보가 없으면 검사하지 않는다", G.check_sector_grouping(b5, {}) == [])

# ⑯-4b 9/14 낮 시험 생성이 1차에서 거부당한 문장 — "같은 반도체 안에서도 A는
# 올랐고, 옆 업종인 전자·부품에서는 B가 올랐다". 글쓴이가 스스로 갈라 놓은
# 것인데 창에 같이 잡혀 걸렸다. '같은 X' 뒤의 '옆 업종·반면·한편' 에서 끊는다.
print("\n⑯-4b '같은 X … 옆 업종인 Y' 는 묶은 게 아니다")
def _chips(text):
    x = sample()
    x["sections"][1]["paragraphs"][0]["ko"] = (
        "[한미반도체](042700) -8.70%, [넥스틴](348210) -8.42%였다. " + text + " "
        + x["sections"][1]["paragraphs"][0]["ko"])
    x["sections"][1]["paragraphs"][0]["en"] = (
        "[Hanmi](042700), [Nextin](348210), [Samwha](001820). " + x["sections"][1]["paragraphs"][0]["en"])
    return G.validate(x, facts=F16)
ok("'같은 반도체 안에서도 A …, 옆 업종인 전자·부품에서는 B' 는 통과 (실제 거부됐던 꼴)",
   not has(_chips("다만 같은 반도체 안에서도 [한미반도체](042700)는 덜 밀렸고, 옆 업종인 전자·부품에서는 "
                  "[삼화콘덴서](001820)가 18.76% 오르며 상위에 들었다."), "묶었다"),
   str(_chips("다만 같은 반도체 안에서도 [한미반도체](042700)는 덜 밀렸고, 옆 업종인 전자·부품에서는 [삼화콘덴서](001820)가 18.76% 오르며 상위에 들었다.")))
ok("'반면' 으로 갈라도 통과",
   not has(_chips("같은 반도체 안에서 [넥스틴](348210)이 밀린 반면 [삼화콘덴서](001820)는 올랐다."), "묶었다"))
ok("갈라 놓지 않고 '같은 부품 안에서도 B' 라고 쓰면 여전히 거부",
   has(_chips("다만 같은 부품 안에서도 [삼화콘덴서](001820)가 18.76% 올랐다."), "묶었다"))
ok("'같은 X' 앞쪽의 '반면' 은 창을 끊지 않는다 — 뒤에서만 끊는다",
   has(_chips("한편 같은 부품 안에서도 [삼화콘덴서](001820)가 18.76% 올랐다."), "묶었다"))


# ────────── ⑰ 재료 상한 · 어제와 같은 조합 — "내용이 매일 똑같다" ──────────
#
# 여덟 편을 재 보니 여덟 편 전부가 열두 재료를 다 다뤘다. 섹션 이름은 날마다
# 달라졌지만 내용은 같은 열두 가지의 낭독이었다. 규칙에 "고른다"고만 적어서는
# 고르지 않는다 — 몇 개까지인지를 정하고 검사가 센다.

print("\n⑰ 다룬 재료를 센다")
_full = ("S&P 500이 올랐고 필라델피아 반도체가 뛰었다. 코스피는 6,909.91로 마감했다. "
         "외국인이 2조원을 순매도했다. 중앙값은 -0.17%였다. 업종 상위는 조선이었다. "
         "[a](000001) [b](000002) [c](000003) [d](000004) [e](000005). "
         "원/달러는 1,344원이다. WTI는 100달러다. 미 10년물은 4.97%다. 16일 FOMC가 끝난다. "
         "9월 리포트가 확인 지점으로 꼽았다.")
_fb = sample(); _fb["lead"]["ko"] = _full
um = G.used_materials(_fb)
ok("열두 묶음을 다 잡는다", len(um) == 12, str(um))
ok("표본(sample)은 두 묶음뿐", len(G.used_materials(sample())) == 2, str(G.used_materials(sample())))
_half = sample(); _half["lead"]["ko"] = "S&P 500이 올랐다. 외국인이 순매도했다. WTI는 100달러다. "
ok("셋만 쓰면 셋+표본 둘 = 다섯", len(G.used_materials(_half)) == 5, str(G.used_materials(_half)))

def _with(n):
    b = sample()
    parts = ["S&P 500이 올랐다.", "코스피는 6,909.91로 마감했다.", "외국인이 순매도했다.",
             "중앙값은 -0.17%다.", "업종 상위는 조선이다.", "원/달러는 1,344원이다.",
             "WTI는 100달러다.", "미 10년물은 4.97%다.", "16일 FOMC가 끝난다.",
             "[a](000001) [b](000002) [c](000003) [d](000004) [e](000005)."]
    b["lead"]["ko"] = " ".join(parts[:n])
    return b

print("\n⑰-4 어제 재료는 나간 글에서만 읽는다")
def _mat_brief(published):
    b = _with(3)                       # 미국지수·국내지수·수급 + 반도체지수·커버리지
    b["meta"] = {"publishedAt": "2026-09-12T07:28+09:00"} if published else {}
    return b
with _tf.TemporaryDirectory() as _d:
    _dd = _P(_d)
    (_dd / "2026-09-12.json").write_text(_json.dumps(_mat_brief(True), ensure_ascii=False), encoding="utf-8")
    (_dd / "2026-09-13.json").write_text(_json.dumps(_mat_brief(False), ensure_ascii=False), encoding="utf-8")
    ym = G.yesterday_materials("2026-09-14", _dd)
    ok("초안(미발행)은 건너뛰고 나간 글을 읽는다", ym is not None, str(ym))
    ok("오늘 이후 파일은 읽지 않는다", G.yesterday_materials("2026-09-12", _dd) is None)
    ok("폴더가 없으면 None", G.yesterday_materials("2026-09-14", _dd / "없음") is None)


print("\n⑱ 넓힌 재료 — 아시아·미국 개별·원자재·심리")
F18 = copy.deepcopy(FACTS)
F18["markets"].update({
    "nikkei":   {"label": "닛케이",   "close": 45210.3, "change": 1.12, "date": "2026-08-14", "unit": ""},
    "hangseng": {"label": "항셍",     "close": 24188.0, "change": -0.4, "date": "2026-08-14", "unit": ""},
    "nvda":     {"label": "엔비디아", "close": 182.4,  "change": 2.3,  "date": "2026-08-14", "unit": "달러"},
    "gold":     {"label": "금",       "close": 3410.5, "change": 0.8,  "date": "2026-08-14", "unit": "달러"},
    "vix":      {"label": "VIX",      "close": 14.2,   "change": -5.1, "date": "2026-08-13", "unit": ""},
    "btc":      {"label": "비트코인", "close": 63412.0, "change": 1.2,  "date": "2026-08-14", "unit": "달러"},
})
t18 = G._facts_text(F18)
ok("아시아 묶음 한 줄 — 개장 전이라 직전 마감값이라고 적는다",
   "아시아(오늘 장은 아직 열리기 전 · 아래는 직전 마감값): 닛케이 45,210.30 +1.12% · 항셍 24,188.00 -0.40%  (기준일 2026-08-14)" in t18, t18)
ok("미국 개별 묶음", "미국 개별: 엔비디아 182.40달러 +2.30%" in t18)
ok("원자재 묶음", "원자재: 금 3,410.50달러 +0.80%" in t18)
ok("기준일이 다르면 항목마다 붙는다", "심리·기타: VIX 14.20 -5.10%(2026-08-13) · 비트코인 63,412.00달러 +1.20%(2026-08-14)" in t18, [l for l in t18.split("\n") if "심리" in l])
ok("못 받은 새 시리즈는 이름이 실린다", "못 받은 값(쓰지 말 것)" in t18 and "상하이종합" in t18 and "테슬라" in t18)
ok("검출기가 새 종류를 센다",
   {"아시아", "미국개별", "원자재", "공포지수"} <= set(G.used_materials(
       {"lead": {"ko": "닛케이가 올랐고 엔비디아가 뛰었다. 금값도 올랐다. VIX는 내렸다."}, "summary": {}, "sections": []})))
ok("분량 하한이 1,000 이다", G.LEN_MIN == 1000, str(G.LEN_MIN))
ok("재료 상한 검사는 없다", not hasattr(G, "check_materials"))

print("\n" + "=" * 60)
if FAIL:
    print(f"❌ 실패 {len(FAIL)}건: {', '.join(FAIL)}")
    sys.exit(1)
print("✅ 전부 통과")
