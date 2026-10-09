#!/usr/bin/env python3
"""업종 분석 생성기(generate_sectors.py) — 2026-10-08 보완을 실제로 돌려 본다. 돈이 들지 않는다(모델을 부르지 않는다).

9월 4일 판 30편을 전수로 보니 셋이 약했다 — 재료에 우리 공시 실적이 없었고(6편은 금액 · 비율 수치가 0),
작성 기준일이 없어 이미 끝난 분기를 '예상'으로 썼고(반도체 '최근 동향'), 7편은 웹 검색 인용이 0건인데
화면에 '웹 검색 참고'가 나갔다. 고친 것이 그대로 있는지 본다.

  ① 금액 · 증감 표기(_won · _chg)               ② 상위 종목 분기 실적 한 줄(_fin_line)
  ③ 실제 자료로 만든 재료(load_sectors)          ④ 지시문에 기준일 · 실적 · 웹 검색 필수(build_prompt)
  ⑤ 집계 수치 검사는 온전한 수로만(live_number_hits) ⑥ 글자 결함 · 출처 0건(defects) · 저장 전 정리(clean)
  ⑦ 회수(collect) — 가짜 배치로: 출처 없는 글은 거르고, 마지막 회차는 받는다 · 저장 전 검토(배치)가 고친 글만 저장
  ⑧ 저장 전 정리(prepare) · 상장 종목 수 · 회사 설명 · 검토 단서(2026-10-09)

    python3 scripts/tests/sectors_gen_test.py
"""
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import generate_sectors as S  # noqa: E402

ok = fail = 0


def eq(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print(f"  PASS {name}")
    else:
        fail += 1
        print(f"  FAIL {name}\n       got:  {got!r}\n       want: {want!r}")


def true(name, cond, detail=""):
    eq(name + (f" — {detail}" if detail and not cond else ""), bool(cond), True)


# ── ① 금액 · 증감 표기 ────────────────────────────────────────
print("① 금액 · 증감 표기")
eq("조 · 억", S._won(74566317000000), "74조 5,663억원")
eq("딱 1조", S._won(1e12), "1조원")
eq("억 반올림이 1조가 되면 조로", S._won(999_950_000_000), "1조원")
eq("억", S._won(207755000000), "2,078억원")
eq("1억 미만은 만", S._won(85_000_000), "8,500만원")
eq("음수", S._won(-207755000000), "-2,078억원")
eq("증가율 · 천 단위 쉼표", S._chg(1913.8e8, 100e8), "전년 동기 대비 +1,813.8%")
eq("감소율", S._chg(50, 100, op=True), "전년 동기 대비 -50.0%")
eq("흑자 전환", S._chg(10, -5, op=True), "흑자 전환")
eq("적자 전환", S._chg(-5, 10, op=True), "적자 전환")
eq("적자 지속", S._chg(-5, -3, op=True), "적자 지속")
eq("매출은 적자 말을 쓰지 않는다", S._chg(10, -5), "")
eq("한쪽이 비면 쓰지 않는다", S._chg(None, 5), "")
eq("분기 이름", S._qtext("2026Q2"), "2026년 2분기")
eq("기준일", S._day("2026-10-08 18:40"), "2026년 10월 8일")

# ── ② 상위 종목 분기 실적 한 줄 ─────────────────────────────────
print("② 분기 실적 한 줄")
Q = {"fs_basis": "연결(CFS) · DART 공시 확정치",
     "quarterly": [{"q": "2025Q2", "rev": 100e8, "op": 10e8}, {"q": "2025Q3", "rev": 110e8, "op": 9e8},
                   {"q": "2025Q4", "rev": 120e8, "op": 8e8}, {"q": "2026Q1", "rev": 130e8, "op": 2e8},
                   {"q": "2026Q2", "rev": 150e8, "op": -5e8}]}
eq("매출 · 영업손실 · 전환", S._fin_line("가나", Q, "2026Q2"),
   "가나(연결): 2026년 2분기 매출 150억원(전년 동기 대비 +50.0%), 영업손실 5억원(적자 전환)")
eq("금융 · 보험은 매출을 싣지 않는다", S._fin_line("가나", Q, "2026Q2", no_rev=True),
   "가나(연결): 2026년 2분기 영업손실 5억원(적자 전환)")
eq("가장 최근 분기보다 늦은 이름(결산월이 다름)은 뺀다", S._fin_line("가나", Q, "2026Q1"), None)
Q2 = {"fs_basis": "별도(OFS)", "quarterly": [{"q": "2026Q2", "rev": 1e8, "op": 5e8}]}
eq("매출이 영업이익보다 작으면 매출이 아니다", S._fin_line("다라", Q2, "2026Q2"), "다라(별도): 2026년 2분기 영업이익 5억원")
eq("자료가 없으면 None", S._fin_line("마바", None, "2026Q2"), None)

# ── ③ 실제 자료로 만든 재료 ───────────────────────────────────
print("③ 실제 자료(load_sectors)")
secs = S.load_sectors()
lq = next(iter(secs.values())).get("latestQ")
true("가장 최근 분기가 정해진다", bool(lq) and len(lq) == 6, str(lq))
semi = secs.get("반도체", {}).get("fin") or []
true("반도체 첫 줄은 삼성전자 분기 실적", bool(semi) and semi[0].startswith("삼성전자(연결): ") and "매출 " in semi[0],
     semi[0] if semi else "없음")
fin_rev = [x for k in ("금융", "보험") for x in (secs.get(k, {}).get("fin") or []) if "매출 " in x]
eq("금융 · 보험 줄에 매출이 없다", fin_rev, [])
n = sum(len(v.get("fin") or []) for k, v in secs.items() if k != "기타")
true("업종마다 실적 줄이 붙는다(전체 200줄 이상)", n >= 200, f"{n}줄")

# ── ④ 지시문 ─────────────────────────────────────────────────
print("④ 지시문(build_prompt)")
P = S.build_prompt("반도체", secs["반도체"], "2026-10-08 18:40")
true("작성 기준일", P.startswith("[작성 기준일] 2026년 10월 8일 · 공시로 확인되는 가장 최근 분기는 "), P[:60])
true("상위 종목 분기 실적 블록", "[상위 종목 최근 분기 실적 · 공시 확정치, 수치 인용 가능]" in P and semi[0] in P)
true("웹 검색을 반드시 하게 한다", "반드시 웹 검색으로" in P and "필요하면 웹 검색" not in P)
true("시스템 지시 — 지난 기간을 예상으로 쓰지 않는다", "앞으로의 일로 쓰지 않는다" in S.SYSTEM)
true("시스템 지시 — 받은 자료를 가리키지 않는다", "'제공된 자료'" in S.SYSTEM)
eq("기준일이 없으면 머리줄 없이(옛 호출 그대로)", S.build_prompt("반도체", secs["반도체"]).startswith("[업종] 반도체"), True)
true("상장 종목 수는 수치 없이 준다(2026-10-09 화장품이 '37개 종목'을 옮겨 적었다)",
     f"상장 종목 {secs['반도체']['count']}개" not in P and "상장 종목 수는 업종 가운데 많은 편" in P
     and S._count_band(37) == "적은 편" and S._count_band(90) == "중간 수준", P[P.find("[집계"):][:80])

# ── ⑤ 집계 수치 검사는 온전한 수로만 ──────────────────────────
print("⑤ 집계 수치(live_number_hits)")
INFO = {"count": 16, "mcap": 47.5, "weight": 2.0}


def body(ko):
    return {k: {"ko": ko if k == "trends" else "업황이 이어진다.", "en": "Steady."} for k in S.BODY_KEYS}


eq("'매출 비중 12%' 의 2% 를 잡지 않는다", S.live_number_hits(body("주요 기업의 매출 비중은 12%로 높다."), INFO), [])
eq("'116개 종목' 의 16개를 잡지 않는다", S.live_number_hits(body("상장 기업 116개 종목이 있다."), INFO), [])
eq("'147조' 의 47조를 잡지 않는다", S.live_number_hits(body("업종 시가총액은 147조 수준이다."), INFO), [])
true("진짜 비중 2% 는 잡는다", S.live_number_hits(body("전체 시장의 2% 비중을 차지한다."), INFO))
true("진짜 종목 수 16개는 잡는다", S.live_number_hits(body("상장 종목 16개로 이뤄진다."), INFO))

# ── ⑥ 글자 결함 · 출처 · 저장 전 정리 ──────────────────────────


def rep(trends="업황이 회복되고 있다."):
    r = {k: {"ko": "업황이 이어진다.", "en": "Conditions continue."} for k in S.BODY_KEYS}
    r["trends"] = {"ko": trends, "en": "Conditions are recovering."}
    r["risks"] = [{"title": {"ko": "수요 둔화", "en": "Demand"}, "body": {"ko": "수요가 줄 수 있다.", "en": "Demand may fall."}}
                  for _ in range(3)]
    return r


print("⑥ 결함(defects) · 정리(clean)")
eq("멀쩡한 글은 결함 없음", S.defects(rep(), None, INFO, sources=["https://www.reuters.com/a"]), [])
true("출처 0건은 거른다", "출처 0건(웹 검색 인용 없음)" in S.defects(rep(), None, INFO, sources=[]))
eq("sources=None 이면 출처를 보지 않는다(마지막 회차)", S.defects(rep(), None, INFO, sources=None), [])
true("받은 자료를 가리키는 말은 거른다(리포트와 같은 검사)",
     any(x.startswith("글자 결함 meta") for x in S.defects(rep("제공된 데이터에 따르면 업황이 좋다."), None, INFO, sources=["u"])))
true("한자가 붙은 말은 거른다", any(x.startswith("글자 결함 hanja") for x in S.defects(rep("오너家 지배력이 크다."), None, INFO, sources=["u"])))
true("개요 · 구조 · 동향의 투자 권유도 거른다(리포트 칸에 옮겨 검사)",
     any(x.startswith("글자 결함 solicit(trends)") for x in S.defects(rep("지금이 기회다."), None, INFO, sources=["u"])))
r_en = rep(); r_en["structure"] = {"ko": "구조가 단순하다.", "en": "Samsung 전자 leads the chain."}
true("영문에 남은 한글을 거른다", any(x.startswith("글자 결함 hangul_en(structure)") for x in S.defects(r_en, None, INFO, sources=["u"])))
eq("리포트 화면용 품질 규칙(ROE)은 걸지 않는다", S.defects(rep("증권사는 ROE 유지가 관건이다."), None, INFO, sources=["u"]), [])
c = S.clean({**rep("업황이<sup>3</sup> 좋다. **수요**가 늘었다."), "sources": ["https://x.com/<a>"]})
eq("태그 · 굵게 표시를 지운다", c["trends"]["ko"], "업황이 좋다. 수요가 늘었다.")
eq("출처 목록은 건드리지 않는다", c["sources"], ["https://x.com/<a>"])
eq("정리한 글은 결함이 없다", S.defects(c, None, INFO, sources=["u"]), [])

# ── ⑦ 회수 — 가짜 배치 ────────────────────────────────────────
print("⑦ 회수(collect) — 가짜 배치")


def msg(rep_obj, urls):
    text = "===JSON_START===" + json.dumps(rep_obj, ensure_ascii=False) + "===JSON_END==="
    cit = [NS(url=u) for u in urls]
    return NS(content=[NS(type="text", text=text, citations=cit)], stop_reason="end_turn",
              usage=NS(input_tokens=1000, output_tokens=500, cache_read_input_tokens=0,
                       cache_creation_input_tokens=0, server_tool_use=NS(web_search_requests=len(urls))))


def fix_meta(params):
    """가짜 검토 — '제공된 자료를 보면 ' 을 지우는 고침 하나. 고칠 것이 없으면 빈 목록."""
    c = params["messages"][0]["content"]
    inp = json.loads(c.split("===INPUT===\n", 1)[1].rsplit("\n===INPUT_END===", 1)[0])
    pt = [{"path": k, "lang": "ko", "old": "제공된 자료를 보면 좋다.", "new": "업황이 좋다.", "why": "6"}
          for k, v in inp.items() if "제공된 자료를 보면 좋다." in v.get("ko", "")]
    return "===JSON_START===" + json.dumps({"patches": pt}, ensure_ascii=False) + "===JSON_END==="


class FakeBatches:
    """첫 배치(b1)는 받은 결과를 돌려주고, 그 뒤에 만든 배치(검토)는 reviewer(요청)의 답으로 채운다."""

    def __init__(self, results, reviewer=None, fail_create=False):
        self.store = {"b1": results}
        self.reviewer = reviewer
        self.fail_create = fail_create
        self.created = []

    def create(self, requests):
        if self.fail_create:
            raise RuntimeError("배치 주문 실패(가짜)")
        bid = f"rv{len(self.created) + 1}"
        self.created.append(requests)
        out = []
        for rq in requests:
            ans = self.reviewer(rq["params"]) if self.reviewer else None
            if ans is None:
                out.append(NS(custom_id=rq["custom_id"], result=NS(type="errored")))
            else:
                out.append(NS(custom_id=rq["custom_id"], result=NS(type="succeeded", message=NS(
                    content=[NS(type="text", text=ans)], stop_reason="end_turn",
                    usage=NS(input_tokens=800, output_tokens=200, cache_read_input_tokens=0,
                             cache_creation_input_tokens=0, server_tool_use=None)))))
        self.store[bid] = out
        return NS(id=bid)

    def retrieve(self, bid):
        return NS(processing_status="ended",
                  request_counts=NS(processing=0, succeeded=len(self.store.get(bid, [])), errored=0))

    def results(self, bid):
        return iter(self.store[bid])


def run_collect(strict, reviewer=fix_meta, review=True, fail_create=False, extra=()):
    S.REVIEW = review
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        S.OUT_JS, S.STATE, S.RETRY = td / "sectors.js", td / "state.json", td / "retry.json"
        S.OUT_JS.write_text("window.KOS_SECTORS = " + json.dumps({"sectors": {"옛업종": {"lead": {"ko": "옛 글."}}}},
                                                                ensure_ascii=False) + ";\n", encoding="utf-8")
        names = ("가업종", "나업종", "다업종") + tuple(k for k, _ in extra)
        cid = {S._cid(s): s for s in names}
        S.STATE.write_text(json.dumps({"batch_id": "b1", "model": "x", "cid_map": cid, "created": "2026-10-08 18:40",
                                       "agg": {s: INFO for s in cid.values()}}, ensure_ascii=False), encoding="utf-8")
        res = [NS(custom_id=S._cid("가업종"), result=NS(type="succeeded", message=msg(rep("업황이<sup>1</sup> 좋다."), ["https://www.reuters.com/a"]))),
               NS(custom_id=S._cid("나업종"), result=NS(type="succeeded", message=msg(rep(), []))),
               NS(custom_id=S._cid("다업종"), result=NS(type="succeeded", message=msg(rep("제공된 자료를 보면 좋다."), ["https://www.reuters.com/b"])))]
        res += [NS(custom_id=S._cid(k), result=NS(type="succeeded", message=msg(r, ["https://www.reuters.com/c"]))) for k, r in extra]
        fb = FakeBatches(res, reviewer, fail_create)
        S.collect(NS(messages=NS(batches=fb)), "2026-10-08 19:00", strict_sources=strict)
        raw = S.OUT_JS.read_text(encoding="utf-8")
        saved = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["sectors"]
        retry = json.loads(S.RETRY.read_text(encoding="utf-8"))["failed"] if S.RETRY.exists() else []
        S.REVIEW = True
        return saved, retry, fb


saved, retry, fb = run_collect(True)
true("출처 있는 글은 저장(태그를 지운 채)", saved.get("가업종", {}).get("trends", {}).get("ko") == "업황이 좋다."
     and saved["가업종"].get("sources") == ["https://www.reuters.com/a"])
true("출처 0건은 검토에 보내지 않고 다시 쓸 목록에", "나업종" not in saved and "나업종" in retry)
true("받은 자료를 가리키는 글은 검토가 고쳐 저장한다", saved.get("다업종", {}).get("trends", {}).get("ko") == "업황이 좋다.",
     str(saved.get("다업종", {}).get("trends")))
true("있던 업종은 그대로", "옛업종" in saved)
eq("검토 배치는 한 번 · 다시 쓸 글은 빼고 두 건", [sorted(r["custom_id"][:3] for r in q) for q in fb.created], [["rv_", "rv_"]])
rq = fb.created[0][0]["params"]
true("검토 요청 — 배치 · 값싼 모델 · 작성 기준일 · 재료", rq["model"] == "claude-sonnet-5"
     and "[작성 기준일] 2026년 10월 8일" in rq["messages"][0]["content"], rq["messages"][0]["content"][:80])
dreq = next(r["params"]["messages"][0]["content"] for r in fb.created[0] if "제공된 자료를 보면" in r["params"]["messages"][0]["content"])
true("기계 검사에 걸린 곳을 '반드시 고칠 것' 으로 넘긴다", "[기계 검사에서 걸린 곳 — 반드시 고칠 것]" in dreq and "meta" in dreq)

saved, retry, _ = run_collect(False)
true("마지막 회차는 출처 0건도 받는다(출처 칸 없이)", "나업종" in saved and "sources" not in saved["나업종"])
eq("마지막 회차에도 검토 · 결함 검사를 거친다", ("다업종" in saved, retry), (True, []))


def no_fix(params):
    return "===JSON_START===" + json.dumps({"patches": []}) + "===JSON_END==="


saved, retry, _ = run_collect(True, reviewer=no_fix)
true("검토가 고치지 못하면 저장하지 않는다(다음 회차가 다시 쓴다)", "다업종" not in saved and "다업종" in retry)
true("멀쩡한 글은 고칠 것이 없어도 저장한다", "가업종" in saved)
saved, retry, _ = run_collect(True, reviewer=lambda p: "읽을 수 없는 답")
true("검토 답을 읽지 못하면 저장하지 않는다", "가업종" not in saved and "다업종" not in saved and {"가업종", "다업종"} <= set(retry))
saved, retry, _ = run_collect(True, reviewer=lambda p: None)
true("검토가 실패(errored)하면 저장하지 않는다", "가업종" not in saved and "가업종" in retry)
saved, retry, _ = run_collect(True, fail_create=True)
true("검토 배치를 주문하지 못하면 이번 회수분은 저장하지 않는다", set(saved) == {"옛업종"} and {"가업종", "다업종"} <= set(retry))


def add_number(params):
    c = params["messages"][0]["content"]
    if "제공된 자료를 보면" not in c:
        return no_fix(params)
    pt = [{"path": "trends", "lang": "ko", "old": "제공된 자료를 보면 좋다.", "new": "영업이익이 52.7% 늘었다.", "why": "2"}]
    return "===JSON_START===" + json.dumps({"patches": pt}, ensure_ascii=False) + "===JSON_END==="


saved, retry, _ = run_collect(True, reviewer=add_number)
true("검토가 본문 · 재료에 없는 수치를 넣으면 그 고침을 버린다(그래서 결함이 남아 저장하지 않는다)",
     "다업종" not in saved and "다업종" in retry)
saved, retry, fb = run_collect(True, review=False)
true("SECTOR_REVIEW=0 이면 검토 없이 전처럼(결함은 거른다)", fb.created == [] and "가업종" in saved and "다업종" in retry)
r_cnt = rep("업황이 좋다. 매출은 9000억원, 영업이익은 1조 2902억원이다.")
r_cnt["structure"] = {"ko": "상장 종목 수는 170여 개에 달한다.", "en": "There are roughly 170 listed companies."}
saved, retry, _ = run_collect(True, reviewer=no_fix, extra=[("라업종", r_cnt)])
true("상장 종목 수를 수치로 쓴 글은 검토가 못 고치면 저장하지 않는다", "라업종" not in saved and "라업종" in retry)

# ── ⑧ 저장 전 정리 · 상장 종목 수 · 회사 설명 · 검토 단서(2026-10-09) ───────────────────
print("⑧ 저장 전 정리(prepare) · 상장 종목 수 · 회사 설명 · 검토 단서")
p = S.prepare(rep("매출은 9000억원, 영업이익은 1조 2902억원이며 ESS向 공급과 88億원 투자가 있었다."))
eq("천 단위 쉼표 · 한자를 고친다", p["trends"]["ko"], "매출은 9,000억원, 영업이익은 1조 2,902억원이며 ESS 대상 공급과 88억원 투자가 있었다.")
eq("정리는 몇 번 돌려도 같다", S.prepare(p), p)
true("'170여 개' 를 잡는다", S.listed_count_hits({"overview": {"ko": "상장 종목 수는 170여 개에 달해 공급망이 두텁다.", "en": "x."}}))
true("'200개를 웃도는 종목' 을 잡는다", S.listed_count_hits({"overview": {"ko": "200개를 웃도는 상장사가 있다.", "en": "x."}}))
true("영어 'roughly 170 listed companies' 를 잡는다",
     S.listed_count_hits({"overview": {"ko": "가.", "en": "With roughly 170 listed companies, the chain is deep."}}))
eq("'상위 4~5개 종목' · '76개사'(바깥 통계)는 잡지 않는다",
   S.listed_count_hits({"overview": {"ko": "상위 4~5개 종목이 이끈다. 상장사 76개사가 참여했다.", "en": "Top 4-5 names lead."}}), [])
eq("영문명은 화면과 같은 꼴로", [S._clean_en(x) for x in ("SAMSUNG ELECTRONICS CO,.LTD", "SK hynix Inc.", "LG CHEM, LTD.", "HD HYUNDAI HEAVY INDUSTRIES CO.,LTD")],
   ["Samsung Electronics", "SK hynix", "LG Chem", "HD Hyundai Heavy Industries"])
eq("검사 규칙에 상대 시점 · 영어 낱말이 들어 있다", all(k in S.GATE_RULES for k in ("stale_time", "en_word", "hanja", "meta")), True)
true("'지난달에만' 을 거른다", any("stale_time" in x for x in S.defects(rep("효성중공업은 지난달에만 수주가 늘었다."), None, INFO, sources=["u"])))
true("'niche 영역' 을 거른다", any("en_word" in x for x in S.defects(rep("특정 niche 영역에서 성장했다."), None, INFO, sources=["u"])))
P = S.build_prompt("반도체", secs["반도체"], "2026-10-08 18:40")
true("지시문에 회사 설명(기업 리포트 첫 문장 · 영문명)", "[회사 설명 · 각 회사의 사업" in P
     and "  - 삼성전자(Samsung Electronics) · 업종 분류 반도체 · " in P, P[P.find("[회사 설명"):][:160])
true("시스템 지시 — 상대 시점 · 쉼표 · 묶은 말 · 회사 설명", all(x in S.SYSTEM for x in ("지난달", "1,000", "[회사 설명]")))
eq("본문에 나온 상장사 이름을 찾는다(두 글자 이름은 앞이 한글이 아닐 때만)",
   S.mentioned({"lead": {"ko": "삼성전자와 SK하이닉스가 이끌고 투자 대상이 넓다.", "en": ""}})[:2], ["SK하이닉스", "삼성전자"])
hint_info = {"fin": ["가나(연결): 2026년 2분기 매출 150억원(전년 동기 대비 +50.0%), 영업이익 10억원(전년 동기 대비 +25.0%)"]}
hr = rep("가나는 영업이익이 70% 넘게 늘었다.")
hs = S.review_hints(hr, hint_info)
true("재료에 없는 비율을 확인할 곳으로 넘긴다", any("재료에 없는 비율 ['70']" in x for x in hs), str(hs))
true("한국어의 비율이 영어에 없으면 확인할 곳으로", any("영어에 없다" in x for x in hs), str(hs))
eq("재료와 같은 비율은 넘기지 않는다", S.review_hints(rep("가나는 영업이익이 25.0% 늘었다."), hint_info)[:1],
   ["[trends] 한국어의 비율 ['25.0'] 이 영어에 없다"])

# ── 묶는 줄 — 회차마다 출처 기준을 넘긴다 ───────────────────────
gen = (ROOT / "scripts" / "generate_sectors.py").read_text(encoding="utf-8")
true("auto 의 회차마다 마지막만 출처 0건을 받는다", "collect(cl, as_of, strict_sources=(rnd < ROUNDS))" in gen)

print(f"\n통과 {ok} · 실패 {fail}")
sys.exit(1 if fail else 0)
