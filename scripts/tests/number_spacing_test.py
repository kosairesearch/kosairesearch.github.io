#!/usr/bin/env python3
"""금액 표기 정규화를 검증한다 — 고쳐야 할 것과 건드리면 안 될 것.

이 검사가 필요한 이유는 하나다. '조·억·만' 은 금액 단위이기도 하지만
평범한 한국어 음절이기도 하다. 규칙을 대충 쓰면 멀쩡한 문장이 망가진다.
실제 본문에서 나온 것들을 그대로 넣어 둔다.

    "다만 원가 절감과…"  ← '만' + ' 원' 으로 읽힌다 (본문에 91군데)
    "제조1동을 준공"      ← '조' + 숫자 로 읽힌다 (본문에 6군데)

두 방향을 다 본다.
  ① 고쳐야 하는데 안 고친다 → 규칙이 헛돈다
  ② 건드리면 안 되는데 고친다 → 글이 망가진다 (더 나쁘다)

  실행:  python3 scripts/tests/number_spacing_test.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from number_spacing import normalize, normalize_report  # noqa: E402

PASS = FAIL = 0


def eq(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}\n      받음: {got!r}\n      기대: {want!r}")


print("── 고쳐야 하는 것 ──")
eq("조 다음 만 단위를 띄운다",
   normalize("79조3,187억원"), "79조 3,187억원")
eq("사용자가 본 그 문장",
   normalize("2026년 매출 79조3,187억원을 기록했다"),
   "2026년 매출 79조 3,187억원을 기록했다")
eq("쉼표 없는 형태도 띄운다",
   normalize("2조6020억원"), "2조 6020억원")
eq("조·억·만 세 단계 모두",
   normalize("1조2,345억6,789만원"), "1조 2,345억 6,789만원")
eq("띄어 쓴 '원' 을 붙인다",
   normalize("1,507억 원으로 늘었다"), "1,507억원으로 늘었다")
eq("'원' 앞 띄움과 만 단위 붙임이 한 문장에",
   normalize("3조3,168억 원에서"), "3조 3,168억원에서")
eq("'20억 원가량' 은 '원'+'가량' 이라 붙이는 게 맞다",
   normalize("매년 20억 원가량의 금융손익"), "매년 20억원가량의 금융손익")

print("\n── 건드리면 안 되는 것 ──")
eq("'다만 원가' — '만'+' 원' 으로 읽히면 안 된다",
   normalize("마진이 낮지만 원가 절감과 상품 개선"),
   "마진이 낮지만 원가 절감과 상품 개선")
eq("'다만 원자재'",
   normalize("도움이 될 수 있지만 원자재 수입 비용 부담"),
   "도움이 될 수 있지만 원자재 수입 비용 부담")
eq("'다만 원재료'",
   normalize("완화되었다. 다만 원재료인 철스크랩 가격도"),
   "완화되었다. 다만 원재료인 철스크랩 가격도")
eq("'제조1동' — '조'+숫자 로 읽히면 안 된다",
   normalize("세종캠퍼스 제조1동을 준공했고"), "세종캠퍼스 제조1동을 준공했고")
eq("이미 맞는 표기는 그대로",
   normalize("79조 3,187억원"), "79조 3,187억원")
eq("만원은 그대로 (만 다음이 '원')",
   normalize("5,000만원 규모"), "5,000만원 규모")
eq("조원도 그대로",
   normalize("시가총액 3조원"), "시가총액 3조원")
eq("영어 본문은 손대지 않는다",
   normalize("KRW 340.4bn in 2022, up 45%"), "KRW 340.4bn in 2022, up 45%")
eq("줄바꿈을 먹지 않는다",
   normalize("영업이익 100억\n원자재 가격"), "영업이익 100억\n원자재 가격")
eq("연도·숫자만 있는 문장",
   normalize("2026년 3월에 2,000명을 채용"), "2026년 3월에 2,000명을 채용")

print("\n── 여러 번 돌려도 같은가 ──")
once = normalize("79조3,187억 원과 1조2,345만 원")
eq("두 번 돌린 결과가 한 번과 같다", normalize(once), once)
eq("그 결과가 맞는 표기다", once, "79조 3,187억원과 1조 2,345만원")

print("\n── 리포트 한 건 통째로 ──")
rep = {
    "title": {"ko": "매출 79조3,187억원", "en": "Revenue KRW 79.3tn"},
    "lead": {"ko": "영업이익 1,507억 원", "en": "OP KRW 150.7bn"},
    "keypoints": [{"ko": "1조2,000억원 투자", "en": "KRW 1.2tn capex"}],
    "quant": {"annual": [{"rev": 79318700000000}], "note": {"ko": "3조4,000억원"}},
    "sources": ["https://example.com/1조2,345억원"],
}
n, out = normalize_report(rep)
eq("제목", out["title"]["ko"], "매출 79조 3,187억원")
eq("리드", out["lead"]["ko"], "영업이익 1,507억원")
eq("목록 항목", out["keypoints"][0]["ko"], "1조 2,000억원 투자")
eq("영어는 그대로", out["title"]["en"], "Revenue KRW 79.3tn")
eq("quant 는 건너뛴다", out["quant"]["note"]["ko"], "3조4,000억원")
eq("sources 도 건너뛴다", out["sources"][0], "https://example.com/1조2,345억원")
eq("바뀐 곳 수를 센다 — 제목·리드·목록 셋", n, 3)

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
