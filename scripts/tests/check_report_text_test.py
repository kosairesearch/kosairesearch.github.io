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

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
