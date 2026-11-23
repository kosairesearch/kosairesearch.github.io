#!/usr/bin/env python3
"""리포트 표현 교정(걸린 문장만 · 배치) 회귀 검사 — Anthropic 없이 가짜 배치로 돌린다(2026-11-23).

  python3 scripts/tests/repair_rules_test.py

왜 있나 — 11/18 규칙 전에 쓴 리포트 537편의 연도 상대 표현('올해 · 지난해 · 내년')을 해가 바뀌기 전에 숫자로 고친다
(scripts/repair_rules_batch.py · repair_rules.yml). 글 전체를 다시 쓰지 않고 걸린 문장만 고치므로, 고친 글이 사실을 바꾸거나
그 사이 다시 쓰인 글을 덮으면 안 된다.

  ① 대상      화면에 나오는 리포트(새 형식 전부 · 새 형식이 없는 종목의 옛 형식)에서 규칙에 걸린 글만 · 개수 제한
  ② 주문      걸린 칸만 요청에 담고, 칸 지문을 남긴다 · 즉시 호출 없이 배치로
  ③ 끼우기    연도로 바꾼 답은 저장 · 원래 파일 꼴(들여쓰기 · 끝 줄바꿈) 그대로 · textRules 는 그대로
  ④ 저장 문턱  숫자를 지움 · 연도 아닌 숫자를 더함 · 다른 검사 위반 · 영어 빈 칸 · 위반이 줄지 않음 · 칸 구조가 다름 → 저장하지 않는다
               연도에 붙은 분기 · 월 번호('2025년 3분기' · 'Q3 2025') · 그 칸에 이미 있던 숫자는 새 숫자로 치지 않는다(11/23)
  ⑤ 덮지 않기  배치를 기다리는 동안 다시 쓰인 글(칸 지문이 다름)은 건드리지 않는다
  ⑥ 작업 파일  수동 · 기본은 세기만 · 최신 main 으로 맞춘 뒤 끼운다 · push_main.sh · 워치독 정리 · 실패를 넘기지 않는다(pipefail)
"""
import json
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import repair_rules_batch as R  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


TMP = Path(tempfile.mkdtemp(prefix="kosai_repair_"))
(TMP / "data" / "reports_v2").mkdir(parents=True)
(TMP / "data" / "reports").mkdir(parents=True)
R.ROOT = TMP
R.STATE = TMP / "state.json"


def rep_of(tk, earnings_ko, earnings_en, rules=2, extra=None):
    r = {"ticker": tk, "name": f"회사{tk}", "reportDate": "2026-11-12", "textRules": rules,
         "title": {"ko": "실적 개선이 이어진 해", "en": "A year of better earnings"},
         "earnings": {"ko": earnings_ko, "en": earnings_en},
         "outlook": {"ko": "2027년 1분기 수주 잔고가 다음 확인 지점이다.", "en": "The 2027 first-quarter backlog is the next checkpoint."}}
    r.update(extra or {})
    return r


def write(kind, tk, rep, indent=1, tail=""):
    p = TMP / "data" / kind / f"{tk}.json"
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=indent) + tail, encoding="utf-8")
    return p


KO = "올해 3분기 매출은 1,234억원으로 늘었다. 영업이익은 56억원이다."
EN = "Revenue this year rose to KRW 123.4 billion. Operating profit was KRW 5.6 billion."
p1 = write("reports_v2", "111110", rep_of("111110", KO, EN))
p2 = write("reports_v2", "222220", rep_of("222220", "2026년 3분기 매출은 10억원이다.", "Revenue in the third quarter of 2026 was KRW 1 billion."))
p3 = write("reports", "333330", rep_of("333330", "지난해 매출은 20억원이다.", "Revenue last year was KRW 2 billion.", rules=0), indent=2, tail="\n")
p4 = write("reports", "111110", rep_of("111110", "지난해 옛 형식 글이다.", "Last year old format."))     # 새 형식이 있어 화면에 안 나온다
p5 = write("reports_v2", "444440", rep_of("444440", "내년 매출 목표는 30억원이다.", "Next year's target is KRW 3 billion."))

print("① 대상")
ts = R.targets("stale_year")
ok(sorted(f.stem + "/" + f.parent.name for f, _, _ in ts) == ["111110/reports_v2", "333330/reports", "444440/reports_v2"],
   "걸린 글만 · 새 형식이 있는 종목의 옛 형식은 빼고(화면에 안 나온다) · 규칙 전 글에도 건다(textRules 0 · 2)",
   str([f.stem + "/" + f.parent.name for f, _, _ in ts]))
ok(len(R.targets("stale_year", limit=1)) == 1, "개수 제한")


def msg(obj):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text="===JSON_START===" + json.dumps(obj, ensure_ascii=False) + "===JSON_END===")],
                                 usage=types.SimpleNamespace(input_tokens=1000, output_tokens=400, cache_creation_input_tokens=0, cache_read_input_tokens=0))


class FakeBatches:
    def __init__(self, answers):
        self.answers, self.created, self.polls = answers, [], 0

    def create(self, requests):
        self.created.append(requests)
        return types.SimpleNamespace(id="msgbatch_FIX1")

    def retrieve(self, bid):
        self.polls += 1
        return types.SimpleNamespace(processing_status="ended" if self.polls > 1 else "in_progress")

    def results(self, bid):
        out = []
        for r in self.created[-1]:
            a = self.answers.get(r["custom_id"])
            if a is None:
                out.append(types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(type="errored")))
            else:
                out.append(types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(type="succeeded", message=msg(a))))
        return out


print("② 주문")
GOOD = {"earnings": {"ko": "2026년 3분기 매출은 1,234억원으로 늘었다. 영업이익은 56억원이다.",
                     "en": "Revenue in 2026 rose to KRW 123.4 billion. Operating profit was KRW 5.6 billion."}}
LOSE = {"earnings": {"ko": "2025년 매출은 늘었다.", "en": "Revenue in 2025 rose."}}                    # 333330 — 숫자 '20'을 지움
ADD = {"earnings": {"ko": "2027년 매출 목표는 30억원이며 영업이익률은 15%다.", "en": "The 2027 target is KRW 3 billion with a 15% margin."}}
fb = FakeBatches({"v2_111110": GOOD, "v1_333330": LOSE, "v2_444440": ADD})
cl = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb))
bid = R.cmd_order(cl, "stale_year", 0, sleep=lambda s: None)
st = json.loads(R.STATE.read_text(encoding="utf-8"))
reqs = fb.created[-1] if fb.created else []
ok(bid == "msgbatch_FIX1" and sorted(r["custom_id"] for r in reqs) == ["v1_333330", "v2_111110", "v2_444440"] and fb.polls == 2,
   "걸린 글마다 요청 하나 · 끝날 때까지 기다린다", str(sorted(r["custom_id"] for r in reqs)))
p = next(r["params"] for r in reqs if r["custom_id"] == "v2_111110")
ok(p["model"] == R.C.REPAIR_MODEL and "stale_year" in p["messages"][0]["content"] and '"earnings"' in p["messages"][0]["content"]
   and '"outlook"' not in p["messages"][0]["content"],
   "교정 모델 · 위반 설명 · 걸린 칸만 담는다(걸리지 않은 칸은 보내지 않는다)")
ok(st["items"]["v2_111110"]["sections"] == ["earnings"] and len(st["items"]["v2_111110"]["fp"]) == 40
   and st["items"]["v1_333330"]["file"] == "data/reports/333330.json", "칸 · 칸 지문 · 파일 경로를 남긴다")

print("③ 끼우기 · ④ 저장 문턱")
before3 = p3.read_text(encoding="utf-8")
res = R.cmd_apply(cl)
r1 = json.loads(p1.read_text(encoding="utf-8"))
ok(res["saved"] == ["111110"] and r1["earnings"]["ko"].startswith("2026년 3분기 매출은 1,234억원") and r1["textRules"] == 2
   and R.C.year_hits(dict(r1, textRules=3)) == [], "연도로 바꾼 답은 저장한다 · textRules 는 그대로 · 위반 0", str(res))
ok(p1.read_text(encoding="utf-8") == json.dumps(r1, ensure_ascii=False, indent=1), "원래 파일 꼴 그대로(들여쓰기 1 · 끝 줄바꿈 없음)")
ok(p3.read_text(encoding="utf-8") == before3 and res["skip"].get("숫자가") == 1, "숫자를 지운 답은 저장하지 않는다", str(res["skip"]))
ok(json.loads(p5.read_text(encoding="utf-8"))["earnings"]["ko"].startswith("내년") and res["skip"].get("연도가") == 1,
   "연도가 아닌 숫자를 더한 답(15%)은 저장하지 않는다")
ok(res["usd"] > 0 and res["left"] == 0, "사용량을 적는다(배치 단가)")
rep = R.load(p5)[0]
ok(R.judge("stale_year", rep, msg({"earnings": {"ko": "2027년 매출 목표는 30억원이다.", "en": ""}}))[0] is None,
   "영어 칸을 비운 답은 저장하지 않는다")
bad_new = R.judge("stale_year", rep, msg({"earnings": {"ko": "2027년 매출 목표는 30억원이다. 독자는 이를 확인할 필요가 있다.",
                                                       "en": "The 2027 target is KRW 3 billion."}}))
ok(bad_new[0] is None and "다른 검사" in bad_new[1], "다른 검사 위반이 생긴 답은 저장하지 않는다", bad_new[1])
ok(R.judge("stale_year", rep, msg({"earnings": {"ko": "내년 매출 목표는 30억원이다.", "en": "Next year's target is KRW 3 billion."}}))[0] is None,
   "위반이 줄지 않은 답은 저장하지 않는다")
ok(R.judge("stale_year", rep, msg({"earnings": "2027년"}))[0] is None, "칸 구조가 다른 답은 저장하지 않는다")
good5 = R.judge("stale_year", rep, msg({"earnings": {"ko": "2027년 매출 목표는 30억원이다.", "en": "The 2027 target is KRW 3 billion."}}))
ok(good5[0] is not None and good5[1] == "2 → 0", "한국어 · 영어 두 곳을 모두 고친 답은 통과", good5[1])
# 11/23 두 번째 실행 — '2025년 3분기' · 같은 칸의 날짜를 쓴 맞는 답 13편이 '연도가 아닌 새 숫자'로 버려졌다
rep7 = rep_of("777770", "2026년 3분기 영업이익률은 9.9%로 지난해 같은 기간 2.6%보다 높았다. 수주액은 2026년 5월 24일 기준 집계다.",
              "The Q3 2026 operating margin was 9.9%, up from 2.6% last year. Orders are as of May 24, 2026.")
q7 = R.judge("stale_year", rep7, msg({"earnings": {
    "ko": "2026년 3분기 영업이익률은 9.9%로 2025년 3분기 2.6%보다 높았다. 수주액은 2026년 5월 24일 기준 집계다.",
    "en": "The Q3 2026 operating margin was 9.9%, up from 2.6% in Q3 2025. Orders are as of May 24, 2026."}}))
ok(q7[0] is not None, "연도에 붙은 분기 번호('2025년 3분기' · 'Q3 2025')는 새 숫자로 치지 않는다", q7[1])
q7b = R.judge("stale_year", rep7, msg({"earnings": {
    "ko": "2026년 3분기 영업이익률은 9.9%로 2025년 1~3분기 2.6%보다 높았다. 2026년 수주액은 5월 24일 기준 집계다.",
    "en": "The Q3 2026 operating margin was 9.9%, up from 2.6% in 3Q 2025. Orders are as of May 24, 2026."}}))
ok(q7b[0] is not None, "기간 범위('2025년 1~3분기') · 그 칸에 이미 있던 날짜(24)도 새 숫자로 치지 않는다", q7b[1])
q7c = R.judge("stale_year", rep7, msg({"earnings": {
    "ko": "2026년 3분기 영업이익률은 9.9%로 2025년 3분기 2.6%보다 7.3%포인트 높았다. 수주액은 2026년 5월 24일 기준 집계다.",
    "en": "The Q3 2026 operating margin was 9.9%, up 7.3 points from 2.6% in Q3 2025. Orders are as of May 24, 2026."}}))
ok(q7c[0] is None and "연도가 아닌 새 숫자 7.3" in q7c[1], "연도에 붙지 않은 새 숫자(7.3)는 여전히 막는다", q7c[1])
q7d = R.judge("stale_year", rep7, msg({"earnings": {
    "ko": "2026년 3분기 영업이익률은 9.9%로 2025년 같은 기간 2.6%보다 높았다. 수주액은 2026년 5월 기준 집계다.",
    "en": "The Q3 2026 operating margin was 9.9%, up from 2.6% in 2025. Orders are as of May 2026."}}))
ok(q7d[0] is None and "숫자가 빠짐" in q7d[1], "있던 날짜(24)를 지운 답은 여전히 막는다", q7d[1])

print("⑤ 덮지 않기")
p6 = write("reports_v2", "555550", rep_of("555550", "올해 매출은 40억원이다.", "Revenue this year was KRW 4 billion."))
fb2 = FakeBatches({"v2_555550": {"earnings": {"ko": "2026년 매출은 40억원이다.", "en": "Revenue in 2026 was KRW 4 billion."}},
                   "v2_444440": {"earnings": {"ko": "2027년 매출 목표는 30억원이다.", "en": "The 2027 target is KRW 3 billion."}},
                   "v1_333330": {"earnings": {"ko": "2025년 매출은 20억원이다.", "en": "Revenue in 2025 was KRW 2 billion."}}})
cl2 = types.SimpleNamespace(messages=types.SimpleNamespace(batches=fb2))
R.cmd_order(cl2, "stale_year", 0, sleep=lambda s: None)
again = rep_of("555550", "올해 매출은 45억원이다(공시로 다시 씀).", "Revenue this year was KRW 4.5 billion.")
write("reports_v2", "555550", again)                       # 배치를 기다리는 동안 다른 작업이 다시 썼다
res2 = R.cmd_apply(cl2)
ok("555550" not in res2["saved"] and json.loads(p6.read_text(encoding="utf-8"))["earnings"]["ko"].startswith("올해 매출은 45억원")
   and res2["skip"].get("그 사이 다시 쓰임") == 1, "그 사이 다시 쓰인 글은 건드리지 않는다", str(res2["skip"]))
ok(sorted(res2["saved"]) == ["333330", "444440"] and p3.read_text(encoding="utf-8").endswith("\n")
   and p3.read_text(encoding="utf-8") == json.dumps(json.loads(p3.read_text(encoding="utf-8")), ensure_ascii=False, indent=2) + "\n",
   "옛 형식(들여쓰기 2 · 끝 줄바꿈)도 원래 꼴로 저장", str(res2["saved"]))
ok(R.targets("stale_year") and [f.stem for f, _, _ in R.targets("stale_year")] == ["555550"], "남은 대상은 다시 쓰인 글뿐")

print("⑥ 작업 파일")
wf = (REPO / ".github" / "workflows" / "repair_rules.yml").read_text(encoding="utf-8")
import yaml  # noqa: E402
y = yaml.safe_load(wf)
on = y.get(True) or y.get("on")
steps = y["jobs"]["repair"]["steps"]
names = [s.get("name", "") for s in steps]
ok(list(on) == ["workflow_dispatch"] and on["workflow_dispatch"]["inputs"]["dry"]["default"] is True,
   "수동 실행만 · 기본은 세기만(돈 안 듦)")
ok(y["concurrency"]["group"] == "kos-repair", "공용 실행 순서(kos-data) 밖 — 대기 중인 다른 작업을 취소하지 않는다")
i_order = next(i for i, n in enumerate(names) if n.startswith("2)"))
i_reset = next(i for i, n in enumerate(names) if n.startswith("3)"))
i_apply = next(i for i, n in enumerate(names) if n.startswith("4)"))
ok(i_order < i_reset < i_apply and "git reset --hard origin/main" in steps[i_reset]["run"],
   "주문 → 최신 main 으로 맞춤 → 끼우기 순서")
ok(all("set -o pipefail" in steps[i]["run"] for i in (i_order, i_apply)), "주문 · 끼우기 실패를 넘기지 않는다(pipefail)")
ok("bash scripts/push_main.sh" in wf and "reports_watchdog.yml -f sync_only=true" in wf and "git add data/reports_v2 data/reports" in wf,
   "올리기는 push_main.sh · 리포트 파일만 · 워치독 정리 요청")
ok("ANTHROPIC_API_KEY" in steps[i_order].get("env", {}) and "ANTHROPIC_API_KEY" not in (steps[0].get("env") or {}),
   "키는 주문 · 끼우기 단계에만")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
