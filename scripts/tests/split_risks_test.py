#!/usr/bin/env python3
"""리스크 요인 나누기(약세 요인과 같은 사안만 · 배치) 회귀 검사 — Anthropic 없이 가짜 배치로 돌린다(2026-11-26).

  python3 scripts/tests/split_risks_test.py

왜 있나 — 무작위 30편 중 28편에서 리스크 요인이 약세 요인의 사안을 같은 수치와 함께 다시 썼다(사장이 에이피알 리포트에서 먼저 봤다).
고친 지시문(textRules 4) 전에 쓴 리포트는 scripts/split_risks_batch.py 가 같은 사안인 리스크 항목만 바꾼다. 바꾼 글이 새 사실을 만들거나,
같은 사안을 다른 말로 되풀이하거나, 그 사이 다시 쓰인 글을 덮으면 안 된다.

  ① 대상      화면에 나오는 리포트 가운데 고친 지시문 전 글(textRules < 4) · 아직 보지 않은 글(riskSplit 없음) · 약세 · 리스크가 제 모양
  ② 주문      글마다 요청 하나(하이쿠 · 배치) · 글 칸 전부(숫자 · 출처 칸 제외) · 약세 · 리스크 지문
  ③ 끼우기    같은 사안인 항목만 바뀌고 나머지 항목 · 다른 칸은 그대로 · riskSplit 표시 · 원래 파일 꼴 · textRules 그대로
  ④ 저장 문턱  리포트에 없는 수치 · 약세 요인의 수치 · 다른 칸 문장 그대로 · 검사 위반(영어 속 한글 · 연도 상대 표현 · 독자 호칭) ·
               분류 겹침 · 판단과 다른 바꿈 · 빠진 판단 · 빈 칸 · 짧은 본문 → 저장하지 않는다 · 같은 사안이 없으면 표시만
  ⑤ 덮지 않기  배치를 기다리는 동안 다시 쓰인 글(약세 · 리스크 지문이 다름)은 건드리지 않는다
  ⑥ 작업 파일  수동 · 기본은 세기만 · 저장은 main 에서만 · 최신 main 으로 맞춘 뒤 끼운다 · push_main.sh · 워치독 정리 · pipefail
  ⑦ 판        생성기가 다는 지금 판(TEXT_RULES)은 이 도구가 보지 않는 판이다 · riskSplit 은 글 칸이 아니다
"""
import copy
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import split_risks_batch as S  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


TMP = Path(tempfile.mkdtemp(prefix="kosai_split_"))
(TMP / "data" / "reports_v2").mkdir(parents=True)
(TMP / "data" / "reports").mkdir(parents=True)
S.ROOT = TMP
S.R.ROOT = TMP
S.STATE = TMP / "state.json"


def T(ko, en):
    return {"ko": ko, "en": en}


def rep_of(tk, rules=3, extra=None):
    r = {"title": T("수출 호조 속 환율 부담", "Export strength meets FX pressure"),
         "lead": T("2026년 3분기 매출은 1,234억원이다.", "Third-quarter 2026 revenue was KRW 123.4 billion."),
         "business": T("회사는 화장품과 미용기기를 만든다. 해외 매출 비중은 94%다. 미국 관세 정책 변화에 대응해 현지 생산을 검토하고 있다. "
                       "오프라인 매장 입점을 늘리고 있다.",
                       "The company makes cosmetics and beauty devices. Overseas sales are 94% of revenue. It is reviewing local "
                       "production in response to US tariff policy. It is expanding offline retail placements."),
         "industry": T("미국 의료기기 규제는 미용 목적 기기와 의료기기를 나눈다. 신규 공장 증설에 1,500억원을 투자한다.",
                       "US device rules separate cosmetic devices from medical devices. It is investing KRW 150 billion in a new plant."),
         "outlook": T("2027년 상반기 새 공장이 가동된다.", "The new plant starts operating in the first half of 2027."),
         "bear": [{"title": T("환율이 수익성을 누른다", "FX weighs on margins"),
                   "body": T("2026년 3분기 영업이익률은 20.8%로 직전 분기 24.8%에서 낮아졌다. 회사 추산 환율 영향은 약 278억원이다.",
                             "The third-quarter 2026 margin fell to 20.8% from 24.8%. The company put the FX impact at about KRW 27.8 billion.")},
                  {"title": T("디바이스 둔화", "Device slowdown"),
                   "body": T("디바이스 매출은 847억원으로 17.9% 줄었다.", "Device sales fell 17.9% to KRW 84.7 billion.")},
                  {"title": T("채널 의존", "Channel dependence"),
                   "body": T("온라인 채널 매출 비중은 66.6%다.", "Online channels are 66.6% of sales.")}],
         "risks": [{"cat": T("환율·수익성", "FX and margins"),
                    "body": T("원화 강세가 이어지면 환손실이 생긴다. 회사 추산 환율 영향은 약 278억원이다.",
                              "A strong won creates FX losses. The FX impact was about KRW 27.8 billion.")},
                   {"cat": T("규제·인허가", "Regulation"),
                    "body": T("의료기기 허가 절차가 일정과 비용을 좌우한다.", "Device approvals drive timing and cost.")},
                   {"cat": T("플랫폼 의존", "Platform dependence"),
                    "body": T("온라인 플랫폼 정책이 바뀌면 판매에 영향을 준다. 온라인 비중은 66.6%다.",
                              "Platform policy changes affect sales. Online is 66.6%.")}],
         "verdict": T("수출은 견조하다.", "Exports are solid."),
         "ticker": tk, "name": f"회사{tk}", "name_en": f"Company {tk}", "market": "KOSPI", "reportDate": "2026-11-14",
         "model": "claude-haiku-5-5", "textRules": rules, "quant": {}, "sources": [{"title": "x", "url": "https://example.com"}]}
    r.update(extra or {})
    return r


def write(kind, tk, rep, indent=1, tail=""):
    p = TMP / "data" / kind / f"{tk}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=indent) + tail, encoding="utf-8")
    return p


BODY1 = ("미국의 화장품 관세 정책이 바뀌면 현지 판매 가격과 마진이 달라질 수 있다. 회사는 현지 생산을 검토하고 있으나 결정 전까지 "
         "비용 구조가 정해지지 않는다. 정책 발표 시점에 따라 분기 실적의 변동 폭이 커질 수 있다.")
BODY1_EN = ("Changes in US cosmetics tariff policy could alter local pricing and margins. The company is reviewing local production, "
            "but its cost structure stays open until a decision. The timing of announcements could widen quarterly swings.")
BODY3 = ("새 공장 증설에 1,500억원을 투자하며 2027년 상반기 가동이 목표다. 가동이 늦어지거나 초기 가동률이 낮으면 고정비 부담이 커질 수 "
         "있다. 증설 자금 조달 방식에 따라 재무 구조도 달라질 수 있다.")
BODY3_EN = ("The company is investing KRW 150 billion in a new plant targeted to start in the first half of 2027. Delays or low "
            "initial utilization could raise the fixed-cost burden. Financing choices could also change the balance sheet.")
GOOD = {"judge": [{"risk": 1, "same_as": 1, "why": "환율 영향 같은 사안"}, {"risk": 2, "same_as": 0, "why": "약세에 없음"},
                  {"risk": 3, "same_as": 3, "why": "채널 의존 같은 사안"}],
        "replace": [{"risk": 1, "cat": T("관세·통상", "Tariffs and trade"), "body": T(BODY1, BODY1_EN)},
                    {"risk": 3, "cat": T("증설 실행", "Plant execution"), "body": T(BODY3, BODY3_EN)}]}

p1 = write("reports_v2", "111110", rep_of("111110"))
p2 = write("reports_v2", "222220", rep_of("222220", rules=4))                                   # 고친 지시문으로 쓴 글
p3 = write("reports", "333330", rep_of("333330", rules=0), indent=2, tail="\n")                 # 옛 형식(새 형식 없음)
p4 = write("reports", "111110", rep_of("111110", rules=0))                                      # 새 형식이 있어 화면에 안 나온다
p5 = write("reports_v2", "444440", rep_of("444440", extra={"riskSplit": 1}))                    # 이미 본 글
p6 = write("reports_v2", "555550", rep_of("555550", extra={"risks": {"ko": "깨진 칸", "en": "broken"}}))   # 모양이 다른 글
p7 = write("reports_v2", "666660", rep_of("666660"))

print("① 대상")
ts = S.targets()
ok(sorted(f.stem + "/" + f.parent.name for f, _ in ts) == ["111110/reports_v2", "333330/reports", "666660/reports_v2"],
   "고친 지시문 전 글 · 아직 보지 않은 글 · 제 모양인 글만 · 새 형식이 있는 종목의 옛 형식은 빼고",
   str([f.stem + "/" + f.parent.name for f, _ in ts]))
ok(len(S.targets(limit=1)) == 1 and [f.stem for f, _ in S.targets(only={"666660"})] == ["666660"], "개수 제한 · 종목 지정")


def msg(obj, raw=None):
    text = raw if raw is not None else "===JSON_START===" + json.dumps(obj, ensure_ascii=False) + "===JSON_END==="
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)],
                                 usage=types.SimpleNamespace(input_tokens=12000, output_tokens=3000, cache_creation_input_tokens=0,
                                                             cache_read_input_tokens=0))


class FakeBatches:
    def __init__(self, answers):
        self.answers, self.created, self.polls, self.by_id = answers, [], 0, {}

    def create(self, requests):
        self.created.append(requests)
        bid = f"msgbatch_SPLIT{len(self.created)}"
        self.by_id[bid] = requests
        return types.SimpleNamespace(id=bid)

    def retrieve(self, bid):
        self.polls += 1
        return types.SimpleNamespace(processing_status="ended" if self.polls > 1 else "in_progress")

    def results(self, bid):
        out = []
        for r in self.by_id[bid]:
            a = self.answers.get(r["custom_id"])
            if a is None:
                out.append(types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(type="errored")))
            else:
                out.append(types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(type="succeeded", message=msg(a))))
        return out


print("② 주문")
NODUP = {"judge": [{"risk": i, "same_as": 0, "why": "다른 사안"} for i in (1, 2, 3)], "replace": []}
BADNUM = copy.deepcopy(GOOD)
BADNUM["replace"][1]["body"] = T(BODY3.replace("1,500억원", "2,000억원"), BODY3_EN.replace("150 billion", "200 billion"))
fb = FakeBatches({"v2_111110": GOOD, "v1_333330": NODUP, "v2_666660": BADNUM})
cl = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb))
bid = S.cmd_order(cl, 0, sleep=lambda s: None)
st = json.loads(S.STATE.read_text(encoding="utf-8"))
reqs = fb.created[-1] if fb.created else []
ok(bid == ["msgbatch_SPLIT1"] and sorted(r["custom_id"] for r in reqs) == ["v1_333330", "v2_111110", "v2_666660"] and fb.polls == 2,
   "글마다 요청 하나 · 끝날 때까지 기다린다", str(sorted(r["custom_id"] for r in reqs)))
p = next(r["params"] for r in reqs if r["custom_id"] == "v2_111110")
body = p["messages"][0]["content"]
ok(p["model"] == "claude-haiku-5-5" and p["thinking"] == {"type": "adaptive"} and p["max_tokens"] >= 8000,
   "하이쿠 5.5 · 적응형 사고(리포트 작성과 같은 모델)")
ok('"bear"' in body and '"risks"' in body and '"business"' in body and '"industry"' in body and '"verdict"' in body
   and '"quant"' not in body and '"sources"' not in body and "textRules" not in body,
   "글 칸은 모두 담고 숫자 · 출처 · 메타 칸은 보내지 않는다")
ok(st["items"]["v2_111110"]["fp"] == S.fingerprint(rep_of("111110")) and st["items"]["v1_333330"]["file"] == "data/reports/333330.json",
   "약세 · 리스크 지문 · 파일 경로를 남긴다")

print("③ 끼우기")
before1 = rep_of("111110")
res = S.cmd_apply(cl)
r1 = json.loads(p1.read_text(encoding="utf-8"))
ok(res["changed"] == 1 and res["items"] == 2 and r1["risks"][0]["cat"]["ko"] == "관세·통상" and r1["risks"][2]["cat"]["ko"] == "증설 실행",
   "같은 사안인 항목(1 · 3)을 바꾼다", str(res))
ok(r1["risks"][1] == before1["risks"][1] and r1["bear"] == before1["bear"]
   and all(r1[k] == before1[k] for k in before1 if k not in ("risks",)),
   "같은 사안이 아닌 항목 · 약세 요인 · 다른 칸은 그대로 · textRules 그대로")
ok(r1.get("riskSplit") == 1 and p1.read_text(encoding="utf-8") == json.dumps(r1, ensure_ascii=False, indent=1),
   "본 글에 riskSplit 표시 · 원래 파일 꼴(들여쓰기 1 · 끝 줄바꿈 없음)")
r3 = json.loads(p3.read_text(encoding="utf-8"))
ok(r3.get("riskSplit") == 1 and r3["risks"] == rep_of("333330")["risks"] and p3.read_text(encoding="utf-8").endswith("\n"),
   "같은 사안이 없으면 글은 그대로 두고 표시만(옛 형식 · 들여쓰기 2 · 끝 줄바꿈 그대로)")
ok("riskSplit" not in json.loads(p7.read_text(encoding="utf-8")) and any(k.startswith("리포트에") for k in res["skip"]),
   "리포트에 없는 수치(2,000억원)를 쓴 답은 저장하지 않는다 — 다음 실행이 다시 묻는다", str(res["skip"]))
ok(res["usd"] > 0, "사용량을 적는다(배치 단가)")
ok(not S.targets(only={"111110", "333330"}), "본 글은 다시 묻지 않는다")

print("④ 저장 문턱")
base = rep_of("777770")


def J(ans):
    return S.judge(base, ans)


def with_body(i, ko, en, cat=None):
    a = copy.deepcopy(GOOD)
    a["replace"][i]["body"] = T(ko, en)
    if cat:
        a["replace"][i]["cat"] = cat
    return a


ok(J(GOOD)[0] is not None, "맞는 답은 통과", J(GOOD)[1])
echo = with_body(0, BODY1.replace("변동 폭이 커질 수 있다.", "변동 폭이 커질 수 있다. 환율 영향은 278억원이었다."),
                 BODY1_EN + " The FX impact was KRW 27.8 billion.")
ok(J(echo)[0] is None and "약세 요인의 수치" in J(echo)[1], "약세 요인의 수치(278억원)를 다시 쓴 답은 막는다", J(echo)[1])
copied = with_body(1, BODY3.replace("새 공장 증설에 1,500억원을 투자하며", "미국 의료기기 규제는 미용 목적 기기와 의료기기를 나눈다. 새 공장 증설에 1,500억원을 투자하며"),
                   BODY3_EN)
ok(J(copied)[0] is None and "그대로 옮김" in J(copied)[1], "다른 칸의 문장을 글자 그대로 옮긴 답은 막는다", J(copied)[1])
hangul = with_body(0, BODY1, BODY1_EN.replace("US cosmetics", "US 화장품"))
ok(J(hangul)[0] is None and "검사 위반" in J(hangul)[1], "영어에 한글을 쓴 답은 막는다(지금 판의 검사)", J(hangul)[1])
year = with_body(0, BODY1.replace("정책 발표 시점에 따라", "올해 정책 발표 시점에 따라"), BODY1_EN)
ok(J(year)[0] is None and "검사 위반" in J(year)[1], "연도 상대 표현('올해')을 쓴 답은 막는다 — 옛 판 글이어도 새 문장은 지금 판으로", J(year)[1])
reader = with_body(0, BODY1.replace("커질 수 있다.", "커질 수 있어 투자자는 정책 발표를 확인할 필요가 있다."), BODY1_EN)
ok(J(reader)[0] is None and "검사 위반" in J(reader)[1], "독자 · 투자자를 부르는 답은 막는다", J(reader)[1])
samecat = with_body(1, BODY3, BODY3_EN, cat=T("규제·인허가", "Regulation 2"))
ok(J(samecat)[0] is None and "분류가 겹침" in J(samecat)[1], "남은 항목과 분류가 겹치는 답은 막는다", J(samecat)[1])
mism = copy.deepcopy(GOOD)
mism["judge"][2]["same_as"] = 0
ok(J(mism)[0] is None and "판단과 다름" in J(mism)[1], "같은 사안이 아니라고 판단한 항목을 바꾼 답은 막는다", J(mism)[1])
miss = copy.deepcopy(GOOD)
miss["judge"] = miss["judge"][:2]
ok(J(miss)[0] is None and "빠진" in J(miss)[1], "판단이 빠진 항목이 있는 답은 막는다", J(miss)[1])
empty = with_body(0, BODY1, "")
ok(J(empty)[0] is None and "비었음" in J(empty)[1], "영어를 비운 답은 막는다", J(empty)[1])
short = with_body(0, "관세가 바뀔 수 있다.", "Tariffs may change and the company is exposed to that over time.")
ok(J(short)[0] is None and "길이" in J(short)[1], "본문이 짧은 답은 막는다(100~300자)", J(short)[1])
ok(S.judge(base, None)[0] is None and S.judge(base, {"judge": "x"})[0] is None, "읽지 못한 답 · 모양이 다른 답은 막는다")
ok(S.parse(msg(None, raw="그냥 글")) in (None, "", {}, []) or S.judge(base, S.parse(msg(None, raw="그냥 글")))[0] is None,
   "마커 없는 글은 저장하지 않는다")
nd = S.judge(base, NODUP)
ok(nd[0] is not None and nd[0]["risks"] == base["risks"] and nd[0]["riskSplit"] == 1 and nd[1] == "같은 사안 없음",
   "같은 사안이 없다는 답은 글을 바꾸지 않고 표시만")
ok(S.judge(dict(base, textRules=4), GOOD)[0] is None and S.judge(dict(base, riskSplit=1), GOOD)[0] is None,
   "끼우는 순간에도 새 판 · 이미 본 글이면 건드리지 않는다")
selfko = with_body(0, BODY1.replace("정책 발표 시점에 따라", "리포트에는 관세율이 제시되지 않아 정책 발표 시점에 따라"), BODY1_EN)
ok(J(selfko)[0] is None and "리포트 자체" in J(selfko)[1], "리포트 자체를 가리키는 말('리포트에는 … 제시되지 않아')은 막는다", J(selfko)[1])
selfsec = with_body(0, BODY1.replace("미국의 화장품 관세 정책이", "산업 분석은 관세 영향을 설명했으나 미국의 화장품 관세 정책이"), BODY1_EN)
ok(J(selfsec)[0] is None and "리포트 자체" in J(selfsec)[1], "다른 절을 가리키는 말('산업 분석은 …')은 막는다", J(selfsec)[1])
selfen = with_body(0, BODY1, BODY1_EN + " The report does not give tariff rates.")
ok(J(selfen)[0] is None and "리포트 자체" in J(selfen)[1], "영어의 'The report does not …'도 막는다", J(selfen)[1])
broker = with_body(0, BODY1.replace("정책 발표 시점에 따라", "KB증권은 2026년 5월 리포트에서 관세 영향을 분석하지 않았고, 정책 발표 시점에 따라"), BODY1_EN)
ok(J(broker)[0] is not None, "증권사 리포트를 가리키는 말('KB증권은 … 리포트에서')은 막지 않는다", J(broker)[1])
stale = with_body(1, BODY3.replace("2027년 상반기 가동이 목표다.", "2026년 8월 첫 선적이 예정되어 있다.").replace("1,500억원", "1,500억원"),
                  BODY3_EN)
ok(J(stale)[0] is None and "지난 일정" in J(stale)[1], "작성일보다 앞선 달의 일정을 '예정'으로 쓴 답은 막는다(작성일 2026-11-14)", J(stale)[1])
ok("작성일(2026-11-14)" in S.params_of(rep_of("1"))["messages"][0]["content"], "지시문에 작성일을 적는다(지난 일정을 고르지 않게)")
yr = with_body(1, BODY3.replace("2027년 상반기 가동이", "2027년 3분기 가동이"),
               BODY3_EN.replace("first half of 2027", "third quarter of 2027"))
ok(J(yr)[0] is not None, "연도 · 연도에 붙은 분기 번호는 새 수치로 치지 않는다", J(yr)[1])
# 약세 요인과는 금액 · 비율 · 배수만 견준다 — 한 자리 개수 · 날짜 · 기간이 겹친 것은 같은 사안의 표시가 아니다(첫 전체 실행 307편 중 약 220편)
cnt_base = rep_of("777771", extra={"business": T("회사는 화장품과 미용기기를 만든다. 해외 매출 비중은 94%다. 국내 2개 공장을 운영한다. "
                                                 "11월 30일 CVS 매장 입점을 시작했다.",
                                                 "The company makes cosmetics and beauty devices. Overseas sales are 94% of revenue. "
                                                 "It runs 2 plants in Korea. It began CVS placements on Nov. 30.")})
cnt_base["bear"][1]["body"] = T("디바이스 매출은 847억원으로 17.9% 줄었고 2년 연속 감소했다. 11월 30일 신제품을 냈으나 판매가 약하다.",
                                "Device sales fell 17.9% to KRW 84.7 billion, down 2 years in a row. A new model launched Nov. 30 sells weakly.")
cnt = with_body(1, BODY3.replace("새 공장 증설에 1,500억원을 투자하며", "국내 2개 공장에 더해 새 공장 증설에 1,500억원을 투자하며"),
                BODY3_EN.replace("The company is investing", "On top of its 2 plants in Korea, the company is investing"))
ok(S.judge(cnt_base, cnt)[0] is not None, "약세 요인과 한 자리 개수('2년' ↔ '2개 공장')만 겹친 답은 막지 않는다",
   S.judge(cnt_base, cnt)[1])
pct_base = rep_of("777772")
pct_base["bear"][2]["body"] = T("온라인 채널 매출 비중은 66.6%다. 2026년 3분기 영업이익률은 3% 낮아졌다.",
                                "Online channels are 66.6% of sales. The Q3 2026 margin fell 3%.")
pct = with_body(0, BODY1.replace("마진이 달라질 수 있다.", "마진이 3% 낮아질 수 있다."),
                BODY1_EN.replace("alter local pricing and margins.", "cut margins by 3%."))
ok(S.judge(pct_base, pct)[0] is None and "약세 요인의 수치" in S.judge(pct_base, pct)[1],
   "비율('3%')은 한 자리여도 · 같은 글에 '3분기'가 있어도 약세 요인과 견준다", S.judge(pct_base, pct)[1])
fig = S._figures("11월 30일까지 3곳에 입점하고 3배 늘었다. In Q3 margin fell 3%. By Nov. 30 it opens 2 plants.")
ok(fig == {"3배", "3%"}, "견줄 수치에서 날짜 · 기간 · 개수를 뺀다(배수 · 비율은 단위와 함께 남긴다)", str(fig))
ok(not (S._figures("부채비율은 200%다.") & S._figures("200억원을 투자한다.")), "단위가 다른 같은 수('200%' · '200억원')는 같은 수치가 아니다")
ok(not (S._figures("매출은 1조 2,345억원이다.") & S._figures("투자 규모는 1조 5,000억원이다.")),
   "'1조 2,345억원'과 '1조 5,000억원'은 '1조'만 겹친 다른 금액이다")
ok(S._figures("환율 영향은 278억원이다.") & S._figures("약 278억 원의 손실") == {"278억"}, "같은 금액('278억원' · '278억 원')은 같은 수치다")
ok(not S._figures("BAL0891은 초기 임상 단계다. MP010의 완치율은 동물실험 결과다. SAL200 · 5G · 3Q25") and S._figures("금리가 25bp 올랐다") == {"25%"},
   "영문자에 붙은 수(제품 · 분기 이름)는 견주지 않는다('25bp'는 수치)", str(S._figures("BAL0891은 초기 임상 단계다.")))
jo = with_body(1, BODY3.replace("새 공장 증설에 1,500억원을 투자하며", "새 공장 증설에 1조 5,000억원을 투자하며"),
               BODY3_EN.replace("KRW 150 billion", "KRW 1.5 trillion"))
jo_base = rep_of("777773", extra={"industry": T("미국 의료기기 규제는 미용 목적 기기와 의료기기를 나눈다. 신규 공장 증설에 1조 5,000억원을 투자한다.",
                                                "US device rules separate cosmetic devices from medical devices. It is investing KRW 1.5 trillion in a new plant.")})
jo_base["bear"][1]["body"] = T("디바이스 매출은 1조 847억원으로 17.9% 줄었다.", "Device sales fell 17.9% to KRW 1.08 trillion.")
ok(S.judge(jo_base, jo)[0] is not None, "약세 요인의 '1조 847억원'과 새 리스크의 '1조 5,000억원'은 막지 않는다", S.judge(jo_base, jo)[1])

print("⑤ 덮지 않기")
p8 = write("reports_v2", "888880", rep_of("888880"))
fb2 = FakeBatches({"v2_888880": GOOD, "v2_666660": GOOD})
cl2 = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb2))
S.cmd_order(cl2, 0, sleep=lambda s: None)
again = rep_of("888880")
again["risks"][1]["body"] = T("공시로 다시 쓴 리스크다.", "Rewritten after a filing.")
write("reports_v2", "888880", again)                       # 배치를 기다리는 동안 다른 작업이 다시 썼다
res2 = S.cmd_apply(cl2)
ok("888880" not in res2["saved"] and json.loads(p8.read_text(encoding="utf-8"))["risks"][1]["body"]["ko"] == "공시로 다시 쓴 리스크다."
   and res2["skip"].get("그 사이 다시 쓰임") == 1, "그 사이 다시 쓰인 글은 건드리지 않는다", str(res2["skip"]))
ok(res2["saved"] == ["666660"] and json.loads(p7.read_text(encoding="utf-8")).get("riskSplit") == 1, "지난번에 막힌 글은 다음 실행에서 다시 묻는다")
fb3 = FakeBatches({"v2_888880": GOOD})
cl3 = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb3))
S.cmd_order(cl3, 0, sleep=lambda s: None)
before8 = p8.read_text(encoding="utf-8")
res3 = S.cmd_apply(cl3, dry=True)
ok(p8.read_text(encoding="utf-8") == before8 and res3["changed"] == 1, "시험(--dry)은 판단만 하고 저장하지 않는다")

print("⑤-b 여러 배치로 나눠 주문 · 모두 받기")
for tk in ("911110", "922220", "933330"):
    write("reports_v2", tk, rep_of(tk))
S.CHUNK = 2
fb4 = FakeBatches({"v2_911110": NODUP, "v2_922220": GOOD, "v2_933330": NODUP})
cl4 = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb4))
bids4 = S.cmd_order(cl4, 0, only={"911110", "922220", "933330"}, sleep=lambda s: None)
st4 = json.loads(S.STATE.read_text(encoding="utf-8"))
ok(len(bids4) == 2 and [len(r) for r in fb4.created] == [2, 1] and st4["batch_ids"] == bids4 and len(st4["items"]) == 3,
   "배치 하나에 정해 둔 수까지 · 넘으면 배치를 나눈다 · 상태 파일에 배치 번호를 모두 남긴다", str([len(r) for r in fb4.created]))
res4 = S.cmd_apply(cl4)
ok(sorted(res4["saved"]) == ["911110", "922220", "933330"] and res4["changed"] == 1, "나눈 배치의 답을 모두 받아 끼운다", str(res4))
S.CHUNK = 800
ok(S.cmd_apply(cl4, state={"batch_id": "msgbatch_SPLIT1", "items": {}}) == {"saved": [], "changed": 0, "items": 0, "skip": {}, "usd": 0.0},
   "예전 꼴의 상태 파일(batch_id 하나)도 읽는다")

print("⑥ 작업 파일")
import yaml  # noqa: E402
y = yaml.safe_load((REPO / ".github" / "workflows" / "split_risks.yml").read_text(encoding="utf-8"))
on = y.get(True) or y.get("on")
steps = y["jobs"]["split"]["steps"]
names = [s.get("name", "") for s in steps]
inp = on["workflow_dispatch"]["inputs"]
ok(list(on) == ["workflow_dispatch"] and inp["dry"]["default"] is True and inp["save"]["default"] is False,
   "수동 실행만 · 기본은 세기만(돈 안 듦) · 저장은 켜야만")
ok(y["concurrency"]["group"] == "kos-repair", "공용 실행 순서(kos-data) 밖 — 대기 중인 다른 작업을 취소하지 않는다")
g = next(s for s in steps if s.get("name", "").startswith("0)"))
ok("refs/heads/main" in g["if"] and "exit 1" in g["run"], "저장은 main 에서만(가지에서는 시험만)")
i_order = next(i for i, n in enumerate(names) if n.startswith("2)"))
i_reset = next(i for i, n in enumerate(names) if n.startswith("3)"))
i_apply = next(i for i, n in enumerate(names) if n.startswith("4)"))
i_push = next(i for i, n in enumerate(names) if n.startswith("5)"))
ok(i_order < i_reset < i_apply < i_push and "git reset --hard origin/main" in steps[i_reset]["run"]
   and "inputs.save" in steps[i_reset]["if"], "저장할 때는 배치 뒤 최신 main 으로 맞춘 다음 끼운다")
ok("push_main.sh" in steps[i_push]["run"] and "inputs.save" in steps[i_push]["if"], "올리기는 push_main.sh 로 · 저장할 때만")
ok(all("set -o pipefail" in s.get("run", "") for s in steps if "| tee" in s.get("run", "")), "실패를 넘기지 않는다(pipefail)")
ok("--show --dry" in steps[i_apply]["run"], "시험은 전 · 후를 실행 요약에 찍기만 한다")
ok(any("reports_watchdog.yml" in s.get("run", "") and "sync_only=true" in s.get("run", "") for s in steps),
   "고친 글이 있으면 워치독 정리를 부른다")
ok(all("${{ inputs.only }}" not in s.get("run", "") and "${{ inputs.limit }}" not in s.get("run", "") for s in steps),
   "입력값은 환경 변수로 넘긴다(명령 줄에 그대로 넣지 않는다)")

print("⑦ 판")
ok(S.C.TEXT_RULES >= S.SPLIT_RULES, "생성기가 다는 지금 판은 이 도구가 보지 않는 판이다(새 지시문으로 쓴 글은 건드리지 않는다)")
ok("riskSplit" in S.C._NOT_TEXT and S.MARK == "riskSplit", "riskSplit 은 글 칸이 아니다(정리 · 검사 · 전수 검사가 보지 않는다)")
ok(S.C.prepare(dict(rep_of("1"), riskSplit=1))["riskSplit"] == 1, "저장 전 정리가 표시를 건드리지 않는다")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
