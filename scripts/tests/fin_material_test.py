#!/usr/bin/env python3
"""작성 재료(fin_material) 시험 — 앞으로 만들 리포트에 숫자 오류가 생기지 않게 하는 예방책을 지킨다(2026-10-10).

사장: "지금 만든 리포트를 고치는 것보다 앞으로 만들어질 리포트에 오류가 안 생기는 게 더 중요하다."

작성 모델은 원 단위 원자료(JSON)를 받아 '억 · 만'으로 직접 옮기다 자리를 틀렸다(영업이익 7,373만원 → '7.4억원').
이제 코드가 본문 표기로 바꿔 주고(won · won_en), 증감 · 전환 · 연속을 세어 준다(chg · 연속 줄). 여기서는
  ① 표기가 맞는가 — 조 · 억 · 만, 영어 trillion · billion · million, 절반 올림
  ② 재료를 그대로 옮긴 문장이 저장 전 금액 검사(check_report_text.amount_hits)를 통과하는가 — 화면에 나오는 리포트의
     공시 값 전부로 본다. 어긋나면 재료를 그대로 옮긴 리포트가 저장되지 않는다(돈만 나간다).
  ③ 재료의 '연속' 줄을 옮긴 문장이 연속 연수 검사(streak_hits)를 통과하는가 — 같은 이유
  ④ 재료에 본문에 쓰면 안 되는 값(ROE · 주당지표)과 지시문의 말('제공한' · '분기 창' · 'ttm_window')이 없는가
  ⑤ 영문명 — 공시 영문명을 본문에 쓸 꼴로, 이름이 비슷한 회사를 함께 준다(화천기공 · 화천기계)
  ⑥ 리포트 지시문(build_prompt_v2) · 신규 상장 지시문(build_prompt)에 재료 · 영문명 · 규칙이 들어가고 원자료는 빠졌는가

  실행:  python3 scripts/tests/fin_material_test.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

import check_report_text as C  # noqa: E402
import fin_material as F  # noqa: E402

PASS = FAIL = 0


def eq(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}\n      받음: {got!r}\n      기대: {want!r}")


print("── ① 표기 ──")
eq("조 · 억", F.won(333605938000000), "333조 6,059억원")
eq("딱 1조", F.won(1e12), "1조원")
eq("억 반올림이 1조가 되면 조로", F.won(999_950_000_000), "1조원")
eq("100억 이상은 억 정수", F.won(34_273_774_505), "343억원")
eq("1억 이상 100억 미만은 소수 한 자리", F.won(127_090_000), "1.3억원")
eq("소수 .0 은 뗀다", F.won(1_200_000_000), "12억원")
eq("100억 바로 아래가 100억으로 올라가면", F.won(9_996_000_000), "100억원")
eq("1억 미만은 만원", F.won(73_726_189), "7,373만원")
eq("만원이 1억으로 올라가면", F.won(99_996_000), "1억원")
eq("음수는 크기만(손익 이름이 가른다)", F.won(-81_436_366), "8,144만원")
eq("절반 올림(화면 표와 같다)", F.won(25_000_000), "2,500만원")
eq("영어 — 조", F.won_en(333605938000000), "KRW 333.6 trillion")
eq("영어 — 10조 미만 조는 소수 둘", F.won_en(1_044_088_716_546), "KRW 1.04 trillion")
eq("영어 — 100억 이상 1조 미만은 billion 소수 하나", F.won_en(467_600_000_000), "KRW 467.6 billion")
eq("영어 — 10억 이상 100억 미만은 billion 소수 둘", F.won_en(2_460_000_000), "KRW 2.46 billion")
eq("영어 — 1억 이상 10억 미만은 million 정수", F.won_en(990_000_000), "KRW 990 million")
eq("영어 — 1억 미만은 million 소수 둘", F.won_en(73_726_189), "KRW 73.73 million")
eq("분기 이름", F.qtext("2026Q2"), "2026년 2분기")
eq("증가율", F.chg(110, 100), "10.0% 증가")
eq("감소율 · 천 단위 쉼표", F.chg(1, 20), "95.0% 감소")
eq("큰 증가율의 쉼표", F.chg(19.138, 1), "1,813.8% 증가")
eq("흑자 전환", F.chg(10, -5, True), "흑자 전환")
eq("적자 전환", F.chg(-5, 10, True), "적자 전환")
eq("적자 지속(손실 축소)", F.chg(-3, -5, True), "적자 지속(손실 축소)")
eq("적자 지속(손실 확대)", F.chg(-6, -5, True), "적자 지속(손실 확대)")
eq("매출은 전환 말을 쓰지 않는다", F.chg(10, -5), "")
eq("한쪽이 비면 쓰지 않는다", F.chg(None, 5), "")
eq("조사 — 받침", (F._eun("2023년"), F._eun("2025년 4분기")), ("은", "는"))

# 화면에 나오는 리포트의 공시 값 전부
quants = []
for f in sorted((ROOT / "data" / "reports_v2").glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        continue
    if isinstance(d, dict) and isinstance(d.get("quant"), dict):
        quants.append((f.stem, d.get("name") or "", d["quant"]))

print(f"\n── ② 재료를 그대로 옮긴 문장이 금액 검사를 통과한다 (리포트 {len(quants):,}편의 공시 값 전부) ──")
bad, n = [], 0
for tk, name, q in quants:
    if str((q.get("valuation") or {}).get("ccy") or "KRW").upper() != "KRW":
        continue
    sents_ko, sents_en = [], []
    for a in q.get("annual") or []:
        for key, nm, loss_nm in (("rev", "매출", None), ("op", "영업이익", "영업손실"), ("np_owner", "지배주주 순이익", "지배주주 순손실")):
            v = F._val(a, key)
            if v is None:
                continue
            label = loss_nm if (loss_nm and v < 0) else nm
            sents_ko.append(f"{a['year']}년 {label} {F.won(v)}이다.")
            en_m = {"rev": "revenue", "op": "operating loss" if v < 0 else "operating profit",
                    "np_owner": "net loss attributable to owners" if v < 0 else "net profit attributable to owners"}[key]
            sents_en.append(f"{a['year']} {en_m} was {F.won_en(v)}.")
    for r in q.get("quarterly") or []:
        if not re.fullmatch(r"\d{4}Q[1-4]", str(r.get("q") or "")):
            continue
        for key, nm, loss_nm in (("rev", "매출", None), ("op", "영업이익", "영업손실"), ("np_owner", "지배주주 순이익", "지배주주 순손실")):
            v = F._val(r, key)
            if v is None:
                continue
            label = loss_nm if (loss_nm and v < 0) else nm
            sents_ko.append(f"{F.qtext(r['q'])} {label} {F.won(v)}이다.")
            y, k = r["q"].split("Q")
            en_m = {"rev": "revenue", "op": "operating loss" if v < 0 else "operating profit",
                    "np_owner": "net loss attributable to owners" if v < 0 else "net profit attributable to owners"}[key]
            sents_en.append(f"Q{k} {y} {en_m} was {F.won_en(v)}.")
    rep = {"name": name, "quant": q, "earnings": {"ko": " ".join(sents_ko), "en": " ".join(sents_en)}}
    n += len(sents_ko) + len(sents_en)
    bad += [(tk, h["sentence"][:60], h["why"][:50]) for h in C.amount_hits(rep)]
for b in bad[:6]:
    print("      ", b)
eq(f"재료 표기 그대로의 문장 {n:,}개 — 금액 검사 위반 0", len(bad), 0)

print("\n── ③ 재료의 '연속' 줄을 옮긴 문장이 연속 연수 검사를 통과한다 ──")
bad, n = [], 0
RUN = re.compile(r"(?:(\d{4})년\((저점|정점)\) 다음 )?(?:\d{4})년부터 (\d{4})년까지 (\d)년 연속 (증가|감소)")
for tk, name, q in quants:
    text = F.material(q, name)
    for line in text.splitlines():
        if not line.lstrip().startswith("·"):
            continue
        for m in RUN.finditer(line):
            start, kind, _end, k, verb = m.groups()
            if not start:
                continue                                              # 표의 첫 해에서 시작 — 앞을 모르니 정점 연도를 쓰지 않는다
            metric = "영업이익" if "영업이익" in text.split(line)[0].splitlines()[-1] else "매출"
            s = f"{metric}은 {start}년 {kind} 이후 {k}년 연속 {verb}했다."
            n += 1
            hits = C.streak_hits({"quant": q, "earnings": {"ko": s, "en": "x"}})
            bad += [(tk, s, h["why"][:60]) for h in hits]
for b in bad[:6]:
    print("      ", b)
eq(f"재료의 연속 줄 {n:,}개를 옮긴 문장 — 연속 연수 검사 위반 0", len(bad), 0)
SAMPLE = {"annual": [{"year": 2022, "rev": 300, "op": 50}, {"year": 2023, "rev": 290, "op": 40}, {"year": 2024, "rev": 280, "op": 30},
                     {"year": 2025, "rev": 270, "op": -10}], "quarterly": [], "valuation": {}}
mt = F.material(SAMPLE)
eq("첫 해에서 시작한 감소 — 그 앞은 확인되지 않았다고 밝힌다",
   "2023년부터 2025년까지 3년 연속 감소(2022년에서 시작 · 2022년보다 앞은 확인되지 않았다" in mt
   and "그 앞까지 이어졌다고 쓰려면 출처가 있어야 한다" in mt, True)
eq("가장 큰 · 작은 해는 기간으로 — '표의 N개 연도' 처럼 재료를 가리키지 않는다",
   ("2022~2025년 중 가장 큰 해 2022년" in mt, "표의" in mt, "표 안에서" in mt), (True, False, False))
SAMPLE2 = {"annual": [{"year": 2022, "rev": 250, "op": 50}, {"year": 2023, "rev": 300, "op": 40}, {"year": 2024, "rev": 280, "op": 30},
                      {"year": 2025, "rev": 270, "op": 20}], "quarterly": [], "valuation": {}}
mt2 = F.material(SAMPLE2)
eq("정점 다음 해부터 센다 — 2023년 정점 → 2024 · 2025년 감소 = 2년 연속",
   "2023년(정점) 다음 2024년부터 2025년까지 2년 연속 감소(2023년은 세지 않는다)" in mt2, True)
SAMPLE3 = {"annual": [{"year": 2022, "rev": 250, "op": 50}, {"year": 2023, "rev": 300, "op": -40}, {"year": 2024, "rev": 280, "op": -30},
                      {"year": 2025, "rev": 270, "op": -50}], "quarterly": [], "valuation": {}}
mt3 = F.material(SAMPLE3)
eq("적자 연수는 손실을 낸 해의 수 — 2023 · 2024 · 2025년 = 3년 연속 적자",
   "2023년부터 2025년까지 3년 연속 적자(손실을 낸 해의 수)" in mt3, True)
eq("손익은 값마다 이름 — 영업손실 · 적자 전환 · 적자 지속(손실 확대)",
   ("2023년 영업손실" in mt3, "적자 전환" in mt3, "적자 지속(손실 확대)" in mt3), (True, True, True))

print("\n── ④ 재료에 쓰면 안 되는 값과 지시문의 말이 없다 ──")
leak = []
BAN = re.compile(r"ROE|EPS|BPS|DPS|주당|np_owner|ttm_window|eps_basic|제공|확정 데이터|분기 창|JSON|\"rev\"|window")
for tk, name, q in quants:
    m = BAN.search(F.material(q, name))
    if m:
        leak.append((tk, m.group(0)))
eq(f"리포트 {len(quants):,}편의 재료 — 금지 값 · 지시문 말 0", leak[:5], [])
eq("보험수익 칸은 회사 전체 매출로 쓰지 말라고 붙인다",
   "회사 전체의 매출이나 영업수익으로 쓰지 말 것" in F.material({"rev_label": {"ko": "보험수익"}, "annual": [{"year": 2025, "rev": 1e12, "op": 2e12}]}), True)
eq("매출 0 은 '자료 없음'(0원으로 옮기지 않는다)",
   "2024년 자료 없음" in F.material({"annual": [{"year": 2024, "rev": 0, "op": 5e9}, {"year": 2025, "rev": 3e12, "op": 6e9}]}), True)
eq("외화 공시 회사는 원화 환산이라고 밝힌다",
   "원화로 환산한 값" in F.material({"annual": [{"year": 2025, "rev": 1e12, "op": 1e11}], "valuation": {"ccy": "USD"}}), True)

print("\n── ⑤ 영문명 ──")
eq("공시 영문명의 꼬리 · 대문자", F.en_name("SAMSUNG ELECTRONICS CO,.LTD"), "Samsung Electronics")
eq("짧은 약어는 대문자로", F.en_name("HS HWASUNG CO.,LTD"), "HS Hwasung")
eq("하이픈 뒤도 대문자", F.en_name("SAMSUNG ELECTRO-MECHANICS CO.,LTD"), "Samsung Electro-Mechanics")
eq("붙여 쓴 이름은 붙은 꼬리를 떼고 띄운다", F.en_name("KohYoungTechnologyInc."), "Koh Young Technology")
eq("브랜드 꼴은 그대로", (F.en_name("KakaoBank Corp."), F.en_name("PHILOPTICS CO.,LTD.")), ("KakaoBank", "Philoptics"))
eq("대문자뿐인 붙은 이름은 그대로 두고 표시", F.en_name("HYUNDAIMARINE&FIREINSURANCECO.,LTD.").startswith("HYUNDAIMARINE&FIREINSURANCECO(공시 영문명이 붙어"), True)
STOCKS = [{"ticker": "000850", "name": "화천기공", "name_en": "HWACHEON MACHINE TOOL CO.,LTD", "sector": "기계·장비", "mcap": 0.1},
          {"ticker": "010660", "name": "화천기계", "name_en": "HWACHEON MACHINERY CO.,LTD", "sector": "기계·장비", "mcap": 0.08},
          {"ticker": "005930", "name": "삼성전자", "name_en": "SAMSUNG ELECTRONICS CO,.LTD", "sector": "반도체", "mcap": 1500}]
nb = F.name_block(STOCKS[0], STOCKS)
eq("이 회사의 영문명", "이 회사: 화천기공(Hwacheon Machine Tool)" in nb, True)
eq("이름이 비슷한 회사를 함께 — 섞지 말라고", "이름이 비슷한 상장사(서로 다른 회사다" in nb and "화천기계(Hwacheon Machinery)" in nb, True)
eq("시가총액 상위", "삼성전자(Samsung Electronics)" in nb, True)

print("\n── ⑥ 지시문 ──")
import generate_reports_v2 as G2  # noqa: E402
import generate_reports as G1  # noqa: E402
tk, name, q = next(x for x in quants if x[0] == "005930")
st = {"ticker": tk, "name": name, "name_en": "SAMSUNG ELECTRONICS CO,.LTD", "market": "코스피", "sector": "반도체", "price": 255500, "mcap": 1493.7}
pr = G2.build_prompt_v2(st, q, "2026-10-10 01:00", stocks=STOCKS)
eq("리포트 지시문 — 재료 · 영문명이 들어갔다", ("[공시 실적" in pr, "[회사 영문명" in pr, "333조 6,059억원" in pr), (True, True, True))
eq("리포트 지시문 — 원자료(JSON)가 빠졌다", ("333605938000000" in pr, "np_owner" in pr, "ttm_window" in pr), (False, False, False))
eq("리포트 지시문 — 본문으로 새던 말이 없다",
   [w for w in ("제공한 확정", "제공된 연간", "[확정 재무]", "분기 창 ", "JSON의 값", "기준 데이터") if w in pr], [])
eq("리포트 지시문 — 새 규칙(이름 · 문장 끝 · 되풀이 · 영문명 · 연속은 재료대로)",
   all(x in pr for x in ("6-3. **[공시 실적]의 이름을 지킬 것**", "6-4. **문장 끝**", "6-5. **같은 문장을 되풀이하지 않는다**",
                         "6-6. **영어(en) 본문의 회사 이름은 [회사 영문명]을 쓴다**", "[공시 실적]에 적힌 그대로만 쓴다")), True)
pr1 = G1.build_prompt({"ticker": "000850", "name": "화천기공", "name_en": "HWACHEON MACHINE TOOL CO.,LTD", "market": "코스피",
                       "sector": "기계·장비", "price": 50000, "change": 0.5, "mcap": 0.1, "trading_value": 1e9}, "2026-10-10 01:00", "")
eq("신규 상장 지시문 — 영문명 · 표기 규칙", ("[회사 영문명" in pr1, "6-2. **표기 · 시점 · 서술**" in pr1, "[DART 공시 확정 재무]" in pr1),
   (True, True, False))

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
