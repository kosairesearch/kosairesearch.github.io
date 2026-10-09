#!/usr/bin/env python3
"""본문 금지 표현 검사를 검증한다 — 특히 새로 넣은 pershare 규칙.

왜 필요한가
-----------
주당지표(EPS·BPS)의 '수치'를 본문에 쓰면 공시가 갱신될 때 본문만 낡은
숫자로 남는다. 2,563개 중 38개(1.5%)가 그랬고, 42군데는 지금 값과 크게
어긋나 있었다. 최악은 부호가 뒤집힌 것이다 — 본문 "EPS 785원"인데
실제는 -155원(적자)이라 흑자로 읽힌다.

이 검사는 걸린 문장을 작은 모델에 넘겨 고쳐 쓰게 한다. 그래서 오탐이
특히 위험하다 — 멀쩡한 사실을 고쳐 쓰면 없던 오류가 생긴다. 두 방향을
다 본다.

  ① 잡아야 할 것을 잡는가
  ② 건드리면 안 될 것을 안 건드리는가  ← 이쪽이 더 중요하다

pershare 규칙을 넣으면서 cited(증권사 인용) 면제 조건도 건드렸다.
기존 규칙이 그대로 도는지도 같이 본다.

  실행:  python3 scripts/tests/check_report_text_test.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import check_report_text as C  # noqa: E402

PASS = FAIL = 0


def rules_of(ko, en="ok"):
    return sorted(h["rule"] for h in C.check({"lead": {"ko": ko, "en": en}}))


def eq(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}\n      받음: {got!r}\n      기대: {want!r}")


print("── pershare: 잡아야 하는 것 ──")
for ko in [
    "현재 주가는 주당 순자산(BPS 906원)과 거의 같은 수준에 형성돼 있다.",
    "순이익이 적자(EPS –992원)인 현 구간에서는 배율 산출이 어렵다.",
    "주당순이익(EPS)은 약 3,478원 수준이다.",
    "주당순자산 1,569원 대비 현 주가는 낮은 편이다.",
    "지배주주순이익도 94억원(EPS 1,427원)으로 줄었다.",
]:
    eq(ko[:34], "pershare" in rules_of(ko), True)

print("\n── pershare: 건드리면 안 되는 것 ──")
eq("배당금은 규칙에서 뺐다 — 계약 조건 서술이 섞인다",
   rules_of("KCC의 특별배당은 삼성물산 주당배당금에서 2,500원을 초과하는 부분을 기준으로 한다."), [])
eq("주당 배당금 결정 사실",
   rules_of("주당 배당금은 850원으로 결정됐다."), [])
eq("증권사 인용은 면제 — '우리 숫자'가 아니다",
   rules_of("KB증권은 2026년 6월 리포트에서 EPS 3,000원을 전망했다고 밝혔다."), [])
eq("수치 없이 관계로만 서술",
   rules_of("현재 주가는 순자산 대비 프리미엄이 큰 구간이다."), [])
eq("금액이지만 주당지표가 아님",
   rules_of("2025년 연간 매출은 2조 4,985억원으로 줄었다."), [])
eq("주당지표 이름만 있고 수치 없음",
   rules_of("주당순자산 대비 주가 수준은 업종 평균을 밑돈다."), [])
eq("수치가 멀리 떨어져 있으면 안 잡는다",
   rules_of("BPS 는 자본을 주식수로 나눈 값이고, 이 회사 자본은 1,200억원이다."), [])

print("\n── 기존 규칙이 그대로 도는가 (cited 조건을 건드렸다) ──")
eq("roe", rules_of("ROE 는 15% 수준이다."), ["roe"])
eq("term", rules_of("TTM 기준으로 보면 그렇다."), ["term"])
eq("valuejudge", rules_of("현재 주가는 저평가된 구간이다."), ["valuejudge"])
eq("valuejudge 는 증권사 인용이면 면제 (예전 그대로)",
   rules_of("KB증권은 2026년 6월 리포트에서 저평가된 구간이라고 평가했다."), [])
eq("tone", rules_of("실적을 확인하세요."), ["tone"])
eq("solicit", rules_of("지금이 기회다."), ["solicit"])
eq("면책 문구는 검사 대상이 아니다",
   rules_of("본 자료는 투자 권유 목적이 아니며 투자 판단의 책임은 본인에게 있다."), [])
eq("멀쩡한 문장은 아무것도 안 걸린다",
   rules_of("2026년 상반기 영업이익이 전년 대비 큰 폭으로 늘었다."), [])

print("\n── 교정 프롬프트에 새 규칙이 들어갔나 ──")
eq("_RULE_TEXT 에 pershare 설명이 있다", "pershare" in C._RULE_TEXT, True)

# ── 글자 결함 (2026-09-26) ───────────────────────────────────────────────
# 사장이 HLB 본문에서 '<sup index="36-2,36-3"></sup>' 를 먼저 봤다. 전수로 훑으니 태그 5개 리포트,
# 깨진 글자(�) 186개 리포트, '경쁴력'·'플랕폼' 같은 엉뚱한 글자 150여 곳이 있었다. 금지 표현 검사는
# 표현만 봤지 글자를 보지 않았다. 여기서는 검사가 그것을 잡는지, 멀쩡한 말은 건드리지 않는지,
# 그리고 지금 화면에 나오는 리포트·업종 분석 전부에 결함이 없는지 본다(맨 아래 '전수').
print("\n── 글자 결함: 태그·인용 표시는 지우고 감싼 글은 남긴다 (clean_markup) ──")
cm = C.clean_markup
eq("sup 인용 번호", cm('HLB이엔지로 나뉜다<sup index="36-2,36-3"></sup>. 즉'), "HLB이엔지로 나뉜다. 즉")
eq("citation", cm('평가된다<citation index="29-13"></citation>. 사업은'), "평가된다. 사업은")
eq("a href — 감싼 글은 남긴다", cm('나뉘는데, <a href="https://x.kr/1">멤피스 공장은 유일하다</a>. 끝'), "나뉘는데, 멤피스 공장은 유일하다. 끝")
eq("br", cm("Birmingham.'<br> With"), "Birmingham.' With")
eq("br 뒤 문단", cm("있다.\n\n</br>또한"), "있다.\n\n또한")
eq("마크다운 굵게", cm("크게 **하이테크 사업부문**과"), "크게 하이테크 사업부문과")
eq("HTML 이름표", cm("LS CABLE &amp; SYSTEM"), "LS CABLE & SYSTEM")
eq("꺾쇠로 쓴 제목은 그대로", cm("<세브란스: 단절> 과 <A Killer Paradox>"), "<세브란스: 단절> 과 <A Killer Paradox>")
eq("멀쩡한 글은 그대로", cm("매출은 1,797억원이다."), "매출은 1,797억원이다.")
# 2026-10-03 — 태그가 반쯤 지워진 조각(조흥 · 한스바이오메드)과 따옴표 앞 역슬래시(스튜디오미르)
NS = "antml:cite"   # 모델 자신의 인용 태그 — '<' 와 붙여 쓰지 않으려고 따로 적는다
eq("인용 태그 조각", cm("공동 개발\\" + NS + "> 등 신규"), "공동 개발 등 신규")
eq("인용 태그 — 감싼 글은 남긴다", cm("매출은 <" + NS + ' index="3-1">1,797억원이다<' + "/" + NS + ">."), "매출은 1,797억원이다.")
eq("속성 끝 조각", cm('항소 포기서를 제출">하며 소송이'), "항소 포기서를 제출하며 소송이")
eq("따옴표 앞 역슬래시", cm("'도타: 용의 피', 'X-Men \\'97' 등"), "'도타: 용의 피', 'X-Men '97' 등")
eq("꺾쇠 안 따옴표는 그대로", cm("<'오징어 게임'>은 흥행했다"), "<'오징어 게임'>은 흥행했다")
eq("닫힌 꺾쇠 뒤 조각은 지운다", cm('<세브란스: 단절> 흥행 뒤 제출">하며'), "<세브란스: 단절> 흥행 뒤 제출하며")


def drules(ko, en="ok"):
    return sorted({h["rule"] for h in C.defects({"lead": {"ko": ko, "en": en}})})


print("\n── 글자 결함: 잡아야 하는 것 ──")
for ko in ["규모의 경�제 측면에서", "가격 경쁴력을 갖췄다", "경쟟하는 구조다", "공개경쥉입찰", "AI 신약개발 플랕폼",
           "성장 동력으로 꾽힌다", "흑자전환 딖 HBM 훈풍", "정�ّ밀부품", "경쨍하는 시장", "뇌졭중 영역"]:
    eq(ko, drules(ko), ["broken_char"])
eq("영문에 섞인 한자", drules("정상", "the半-year report"), ["broken_char"])
eq("남은 태그", drules('나뉜다<sup index="1-2"></sup>.'), ["markup"])
eq("인용 태그 조각", drules("수익성 개선이 제한\\" + NS + ">될 수"), ["markup"])
eq("속성 끝 조각", drules('존속이 어렵다고 부연">했다'), ["markup"])
eq("역슬래시", drules("'X-Men \\'97'"), ["markup"])
eq("영문 역슬래시", drules("정상", "the \\'97 series"), ["markup"])
eq("단어에 붙은 한자", drules("영업이익은 88億원"), ["hanja"])
eq("받은 자료를 가리키는 말", drules("3분기 수치는 제공된 데이터셋에 포함되지 않아"), ["meta"])
eq("영문 data window", drules("정상", "the highest within the disclosed data window"), ["meta"])
eq("제목·라벨도 본다", sorted({h["section"] for h in C.defects({"title": {"ko": "손익은 널�뛰기", "en": "t"}})}), ["title"])

print("\n── 글자 결함: 건드리면 안 되는 것 ──")
for ko in ["디스플레이용 웻 스테이션", "쓰촨성 몐양 라인", "초전도 코일 퀜치 검출", "중수(重水) 사업", "상저하고(上低下高) 흐름",
           "TGF-β 억제제", "경쟁 구도가 치열하다", "경제·경영·경향·경우·경기", "달걀노른자 추출물", "<세브란스: 단절> 흥행",
           "AI 학습용 데이터셋 사업"]:
    eq(ko, drules(ko), [])
eq("영문 TGF-β·®", drules("정상", "TGF-β and NeoPAC® are fine"), [])
eq("꺾쇠 안 따옴표", drules("<'오징어 게임'>은 흥행했다"), [])
eq("영문 화살표 · 부등호", drules("정상", "KRW 35.9bn -> 54.4bn (<100-employee businesses)"), [])
eq("출처·숫자 칸은 보지 않는다", C.defects({"sources": ["https://x.kr/<sup>"], "quant": {"note": "�"}}), [])

print("\n── 교정 지시에 글자 결함 규칙이 들어갔나 ──")
eq("_RULE_TEXT 에 broken_char·markup·meta·hanja", all(k in C._RULE_TEXT for k in ("broken_char", "markup", "meta", "hanja")), True)

# ── 2026-10-09: 상대 시점 · 영어 낱말 · 받은 자료 언급(넓힘) · 투자 판단 · 핵심 포인트 칸 · 검토 ─────────────────────
# 업종 분석 30편을 사람이 읽으니 검사를 다 통과한 글에 결함이 많았다(사장이 크게 질책했다). 리포트에도 같은 종류가 85편에
# 있었다. 규칙을 넓히고, 저장 전에 글 전체를 읽는 검토(review)를 붙였다. 여기서는 규칙이 잡을 것을 잡고 멀쩡한 말은
# 건드리지 않는지, 검토의 고침을 그대로 믿지 않는지(옛 글이 한 번만 · 새 수치 금지 · 길이) 본다.
print("\n── 상대 시점(stale_time): 잡아야 하는 것 ──")
for ko in ["효성중공업은 지난달에만 수주가 늘었다.", "이달 초 정례회의에서 의결된다.", "이달 정례회의에서 의결이 예상된다.",
           "다음 달 1일부터 매수에 들어간다.", "오늘 기준 아직 도래하지 않았다.", "지난 주말 인기 순위 1위를 차지했다.",
           "어제와 같은 흐름이다.", "이번 주 발표된다.", "다음달 중 공급한다.", "이달(2026년 9월) 서울에서 열린다."]:
    eq(ko, "stale_time" in drules(ko), True)
print("\n── 상대 시점: 건드리면 안 되는 것 ──")
for ko in ["오늘이엔엠의 실적이 늘었다.", "모레모 브랜드가 성장했다.", "오늘의집 거래액이 늘었다.", "미디어오늘 보도에 따르면",
           "그 다음 달에 회복했다.", "'내일도 출근!' 이 흥행했다.", "올해 매출이 늘었다.", "지난해 영업이익이 줄었다.",
           "지난 2분기 실적이 개선됐다.", "2026년 9월 정례회의에서 의결됐다."]:
    eq(ko, drules(ko), [])
print("\n── 영어 낱말(en_word) · 한자(hanja) ──")
for ko in ["특정 niche 영역에서 성장했다.", "Phase에 진입했다.", "valuation의 핵심 변수다.", "실적 risk", "이 discount가 좁혀질지 관건이다.",
           "체질전환 momentum"]:
    eq(ko, "en_word" in drules(ko), True)
for ko in ["니치(niche) 시장이다.", "Point-of-Care 진단기기다.", "Phase 3 임상에 들어갔다.", "임상 3상 upLIFT 연구가 진행 중이다.",
           "Core·Growth·Financial·Seed로 나눈다.", "Growth(성장·30%) 자산이다.", "Tier 1 고객사다.", "RISK 관리 체계를 갖췄다."]:
    eq(ko, drules(ko), [])
eq("영문 옆 한자도 잡는다 — 'ESS向'", drules("ESS向 공급이 늘었다."), ["hanja"])
eq("읽기를 붙인 이름은 그대로 — '楽一(라쿠이치)'", drules("楽一(라쿠이치) 브랜드다."), [])
print("\n── 받은 자료를 가리키는 말(meta): 넓힌 꼴 ──")
for ko in ["제공된 분기 구간 중 최대였다.", "제공된 다섯 개 분기 가운데 가장 높다.", "제공된 5개 분기 중 최고치다.", "최근 4개 분기 창에서 가장 강했다.",
           "본 리포트의 확정 데이터 범위 내에서 특정되지 않는다.", "우리 확정 데이터 범위 밖의 정보다.", "분기 기준 첫 흑자 전환(제공 데이터 기준)",
           "제공된 [확정 재무] 데이터에는 없다.", "제시된 분기 구간 내 최고 수준이다.", "시가총액은 제공된 기준 데이터상 0.0조원이다."]:
    eq(ko, "meta" in drules(ko), True)
for en in ["the highest of the five quarters provided", "in the disclosed quarterly window", "outside our confirmed dataset",
           "the strongest quarter in the dataset", "not yet reflected in the confirmed financial data used in this report",
           "The provided results are on a pre-split basis."]:
    eq(en, "meta" in drules("정상", en), True)
for ko in ["담보로 제공된 유형자산 비중이 높다.", "통합 물류 서비스를 제공한다.", "IMS 데이터 기준 점유율 16%다.", "임상 확정 데이터 공개 여부를 본다.",
           "2026년 2분기 창사 이래 첫 흑자다.", "한국경제 시장 데이터 기준 52주 최고가다.", "모델에 활용 가능한 데이터 범위를 제한한다."]:
    eq(ko, drules(ko), [])
for en in ["the first confirmed data point on margins", "the highest of the four years shown", "growth in the data center market",
           "a lack of data provided by subsidiaries", "with four data center steam turbines"]:
    eq(en, drules("정상", en), [])
print("\n── 우리 목소리의 투자 판단(stance) ──")
for ko in ["가시화되기 전까지는 보수적 접근이 타당하다는 판단이다.", "신중한 접근이 합리적이다.",
           "현 밸류에이션이 실행 위험을 충분히 반영하지 않은 상태로 판단된다.", "시장이 자산가치를 아직 온전히 반영하지 않은 상태로 볼 수 있다.",
           "업사이드 기대가 아직 주가에 충분히 반영되지 않았을 가능성이 있다."]:
    eq(ko[:30], "stance" in rules_of(ko), True)
for ko in ["KB증권은 단기 실적에는 보수적 접근이 바람직하다고 평가했다.", "규제기관의 보수적 접근이 심화될 리스크가 있다.",
           "분기 실적을 순차적으로 확인하는 접근이 유효하다."]:
    eq(ko[:30], rules_of(ko), [])
print("\n── 검사 범위: 핵심 포인트 {ko, en} · 제목 · 옛 형식 칸 · 문자열 종합 의견 ──")
eq("핵심 포인트의 가치 단정", [h["rule"] for h in C.check({"keypoints": [{"ko": "장부가치 대비 현저히 저평가된 상태", "en": "x"}]})], ["valuejudge"])
eq("핵심 포인트 영문의 한글", [h["rule"] for h in C.check({"keypoints": [{"ko": "정상", "en": "Naver's '가 Sejong' data center"}]})], ["hangul_en"])
eq("제목의 가치 단정", [h["rule"] for h in C.check({"title": {"ko": "저평가된 상태", "en": "t"}})], ["valuejudge"])
eq("옛 형식 '최근 동향'", [h["rule"] for h in C.check({"recent": {"ko": "저평가 상태로 인식하고 있다.", "en": "x"}})], ["valuejudge"])
eq("종합 의견이 문자열이어도 멈추지 않는다", C.check({"verdict": "종합 의견"}), [])
eq("명령줄 집계의 사유 — 규칙마다 제 설명", (C._WHY_EXTRA["stale_time"], C._WHY_EXTRA["meta"]), ("상대 시점(지난달 · 이번 주 · 오늘)", "받은 자료를 가리키는 말"))

print("\n── 저장 전 정리(prepare) ──")
pr = C.prepare({"lead": {"ko": "매출 9000억원<sup>1</sup>, ESS向 공급", "en": "x"}, "quant": {"n": "9000억원"}, "sources": ["https://a/<b>"]})
eq("태그 · 한자 · 쉼표를 한 번에", pr["lead"]["ko"], "매출 9,000억원, ESS 대상 공급")
eq("숫자 · 출처 칸은 그대로", (pr["quant"], pr["sources"]), ({"n": "9000억원"}, ["https://a/<b>"]))
eq("몇 번 돌려도 같다", C.prepare(pr), pr)
eq("영문명을 화면 꼴로", [C.clean_en(x) for x in ("SAMSUNG ELECTRONICS CO,.LTD", "SK hynix Inc.", "NAVER Corp.")],
   ["Samsung Electronics", "SK hynix", "NAVER"])
eq("검토 단서 — 한국어의 비율이 영어에 없다", C.en_gap_hints({"lead": {"ko": "영업이익이 37.2% 늘었다.", "en": "Profit rose."}}),
   ["[lead] 한국어의 비율 ['37.2'] 이 영어에 없다"])

print("\n── 검토(review): 고침을 그대로 믿지 않는다 ──")
import json as _json  # noqa: E402
REP = {"lead": {"ko": "매출은 1,234억원으로 늘었다. 제공된 분기 구간 중 최대였다.", "en": "Revenue rose to KRW 123.4bn."},
       "risks": [{"cat": {"ko": "수요", "en": "Demand"}, "body": {"ko": "수요가 줄 수 있다.", "en": "Demand may fall."}}],
       "quant": {"x": 1}}


def ans(patches):
    return "===JSON_START===" + _json.dumps({"patches": patches}, ensure_ascii=False) + "===JSON_END==="


new, n_ok, dropped = C.apply_review(REP, ans([
    {"path": "lead", "lang": "ko", "old": "제공된 분기 구간 중 최대였다.", "new": "최근 5개 분기 중 최대였다.", "why": "6"},
    {"path": "lead", "lang": "en", "old": "KRW 123.4bn.", "new": "KRW 123.4bn, up 52.7%.", "why": "7"},
    {"path": "lead", "lang": "ko", "old": "없는 글", "new": "x", "why": "1"},
    {"path": "business", "lang": "ko", "old": "x", "new": "y", "why": "1"},
    {"path": "risks.0.body", "lang": "ko", "old": "수요가 줄 수 있다.", "new": "", "why": "1"},
    {"path": "lead", "lang": "ko", "old": "늘었다.", "new": "늘었다. " * 80, "why": "1"},
]), extra="  - 가나 2026Q2: 매출 1,234억", as_of="2026-10-08")
eq("맞는 고침만 적용(1곳)", (n_ok, new["lead"]["ko"]), (1, "매출은 1,234억원으로 늘었다. 최근 5개 분기 중 최대였다."))
eq("새 수치(52.7) · 없는 옛 글 · 없는 칸 · 칸이 비게 됨 · 너무 긴 새 글은 버린다", len(dropped), 5)
eq("원본은 건드리지 않는다", REP["lead"]["ko"], "매출은 1,234억원으로 늘었다. 제공된 분기 구간 중 최대였다.")
eq("숫자 칸은 보내지도 바꾸지도 않는다", "quant" in _json.loads(C.review_params({k: v for k, v in REP.items() if k not in C._NOT_TEXT})["messages"][0]["content"].split("===INPUT===\n", 1)[1].rsplit("\n===INPUT_END===", 1)[0]), False)
eq("읽을 수 없는 답", C.apply_review(REP, "모르겠다")[0], None)
amt = C._amount_forms("영업이익 4조 1,246억원 · 3,865억원 · 1억 3,341만달러")
eq("한국어 금액의 영어 꼴(4.1246 tn · 386.5 bn · 133.41 mn)은 새 수치가 아니다", all(x in amt for x in ("4.1246", "386.5", "133.41")), True)


class _Msgs:
    def __init__(self, text):
        self.text, self.sent = text, []

    def create(self, **kw):
        self.sent.append(kw)
        from types import SimpleNamespace as _NS
        return _NS(content=[_NS(type="text", text=self.text)])


cl_rv = type("CL", (), {})()
cl_rv.messages = _Msgs(ans([{"path": "lead", "lang": "ko", "old": "제공된 분기 구간 중 최대였다.", "new": "최근 5개 분기 중 최대였다.", "why": "6"}]))
got = C.review(cl_rv, REP, C.check(REP), kind="report", as_of="2026-10-08", material="  - 가나: 매출 1,234억")
eq("review — 고친 글 · 남은 위반 0 · 기록", (got[0]["lead"]["ko"].endswith("최근 5개 분기 중 최대였다."), got[1], got[2]),
   (True, [], "검토 고침 1곳"))
p0 = cl_rv.messages.sent[0]
eq("review 요청 — 값싼 모델 · 사고 · 기준일 · 재료 · 반드시 고칠 곳", (p0["model"], p0["thinking"], "[작성 기준일] 2026-10-08" in p0["messages"][0]["content"],
   "[재료 — 공시 확정치" in p0["messages"][0]["content"], "meta" in p0["messages"][0]["content"]),
   ("claude-sonnet-5", {"type": "adaptive"}, True, True, True))
cl_bad = type("CL", (), {})()
cl_bad.messages = _Msgs(ans([{"path": "lead", "lang": "ko", "old": "늘었다.", "new": "늘었다<sup>1</sup>.", "why": "1"}]))
eq("review — 고친 글에 태그가 생기면 검토 전체를 버린다", C.review(cl_bad, REP, []), None)


class _Batches:
    def __init__(self):
        self.reqs = None

    def create(self, requests):
        self.reqs = requests
        from types import SimpleNamespace as _NS
        return _NS(id="b1")

    def retrieve(self, bid):
        from types import SimpleNamespace as _NS
        return _NS(processing_status="ended")

    def results(self, bid):
        from types import SimpleNamespace as _NS
        return [_NS(custom_id="a", result=_NS(type="succeeded", message=_NS(content=[_NS(type="text", text="ok")]))),
                _NS(custom_id="b", result=_NS(type="errored"))]


cl_b = type("CL", (), {})()
cl_b.messages = type("M", (), {})()
cl_b.messages.batches = _Batches()
res = C.send_batch(cl_b, {"a": C.review_params({"lead": {"ko": "가.", "en": "a."}}), "b": C.review_params({"lead": {"ko": "나.", "en": "b."}})},
                   log=lambda *_: None, sleep=lambda *_: None)
eq("send_batch — 배치 하나 · 성공은 답 · 실패는 None", (len(cl_b.messages.batches.reqs), C.message_text(res["a"]), res["b"]), (2, "ok", None))

print("\n── 전수: 화면에 나오는 리포트·업종 분석에 글자 결함이 없다 ──")
import json, re  # noqa: E402
ROOT = HERE.parent.parent
v2 = {f.stem for f in (ROOT / "data" / "reports_v2").glob("*.json")}
files = sorted((ROOT / "data" / "reports_v2").glob("*.json")) + \
    [f for f in sorted((ROOT / "data" / "reports").glob("*.json")) if f.stem not in v2]   # v2 가 있으면 v1 은 안 나온다
bad, n = [], 0
for f in files:
    try:
        rep = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if not isinstance(rep, dict):
        continue
    n += 1
    bad += [(f.parent.name + "/" + f.stem, h) for h in C.check(rep)]        # 2026-10-09 부터 모든 규칙(생성기의 저장 문턱과 같다)
sec_js = (ROOT / "data" / "sectors.js").read_text(encoding="utf-8")
sectors = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", sec_js, re.S).group(1)).get("sectors") or {}
# 업종 분석은 생성기(generate_sectors.defects)와 같은 기준 — 리포트 칸으로 옮겨 위험 등급 · 글자 결함 · 상대 시점 · 영어 낱말 ·
# 영문 속 한글을 본다(리포트 화면용 품질 규칙 ROE · 말투 · 주당지표는 걸지 않는다).
AS_REPORT = {"lead": "lead", "overview": "business", "structure": "industry", "trends": "earnings", "outlook": "outlook", "risks": "risks"}
SEC_GATE = ("hanja", "meta", "hangul_en", "stale_time", "en_word")
for name, obj in sectors.items():
    if isinstance(obj, dict):
        bad += [("sectors/" + name, h) for h in C.defects(obj)]
        bad += [("sectors/" + name, h) for h in C.check({AS_REPORT[k]: v for k, v in obj.items() if k in AS_REPORT})
                if h["level"] == "위험" or h["rule"] in SEC_GATE]
for where, h in bad[:8]:
    print(f"      {where} [{h['section']}] {h['rule']} {h['match']!r} — {h['sentence'][:70]}")
eq(f"리포트 {n:,}개 · 업종 {len(sectors)}개 — 검사 위반 0(글자 결함 · 받은 자료 언급 · 상대 시점 · 영어 낱말 · 투자 판단 · 주당지표 …)", len(bad), 0)
miss = []
for f in files:
    try:
        rep = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(rep, dict):
        miss += [(f.stem, k) for k, v in C._flat_fields({k: x for k, x in rep.items() if k not in C._NOT_TEXT}).items()
                 if (v.get("ko") or "").strip() and not (v.get("en") or "").strip()]
eq("영문이 빈 칸 0 — 영어 화면에 한국어가 나오지 않는다", miss[:5], [])
import number_spacing as _N  # noqa: E402
nc = []
for f in files:
    try:
        rep = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(rep, dict):
        nc += [(f.stem, m.group(0)) for k, v in C._flat_fields({k: x for k, x in rep.items() if k not in C._NOT_TEXT}).items()
               for m in _N.no_comma_hits(v.get("ko") or "")]
eq("천 단위 쉼표가 빠진 수 0", nc[:5], [])

# 모닝브리핑 — 화면은 [이름](여섯 자리) 만 링크로 바꾸므로 나머지 대괄호는 괄호째 찍힌다(9/2 '[기재정정]' ·
# 10/2 '[마이크론]'). 생성기의 strip_brackets 가 저장 전에 벗긴다. 이 전수는 아침 작업의 회귀 시험
# (test_brief_gen)에 두지 않는다 — 지난 호 하나 때문에 그날 브리핑이 막히면 안 된다.
print("\n── 전수: 발행한 모닝브리핑에 링크가 아닌 대괄호가 없다 ──")
BARE = re.compile(r"\[[^\[\]\n]{1,80}\](?!\(\d{6}\))")
bb, nb = [], 0
for f in sorted((ROOT / "data" / "briefs").glob("*.json")):
    doc = json.loads(f.read_text(encoding="utf-8"))
    if not (doc.get("meta") or {}).get("publishedAt"):
        continue
    nb += 1
    texts = [(doc.get(k) or {}).get(lg) for k in ("title", "lead", "summary") for lg in ("ko", "en")]
    for s in doc.get("sections") or []:
        texts += [(s.get("heading") or {}).get(lg) for lg in ("ko", "en")]
        texts += [p.get(lg) for p in s.get("paragraphs") or [] for lg in ("ko", "en")]
    bb += [(f.stem, m.group(0)) for t in texts if isinstance(t, str) for m in BARE.finditer(t)]
for where, h in bb[:8]:
    print(f"      {where} {h}")
eq(f"브리핑 {nb}편 — 링크가 아닌 대괄호 0", len(bb), 0)

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
