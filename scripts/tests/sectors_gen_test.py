#!/usr/bin/env python3
"""업종 분석 생성기(generate_sectors.py) — 2026-10-08 보완을 실제로 돌려 본다. 돈이 들지 않는다(모델을 부르지 않는다).

9월 4일 판 30편을 전수로 보니 셋이 약했다 — 재료에 우리 공시 실적이 없었고(6편은 금액 · 비율 수치가 0),
작성 기준일이 없어 이미 끝난 분기를 '예상'으로 썼고(반도체 '최근 동향'), 7편은 웹 검색 인용이 0건인데
화면에 '웹 검색 참고'가 나갔다. 고친 것이 그대로 있는지 본다.

  ① 금액 · 증감 표기(_won · _chg)               ② 상위 종목 분기 실적 한 줄(_fin_line)
  ③ 실제 자료로 만든 재료(load_sectors)          ④ 지시문에 기준일 · 실적 · 웹 검색 필수(build_prompt)
  ⑤ 집계 수치 검사는 온전한 수로만(live_number_hits) ⑥ 글자 결함 · 출처 0건(defects) · 저장 전 정리(clean)
  ⑦ 회수(collect) — 가짜 배치로: 출처 없는 글은 거르고, 마지막 회차는 받는다

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


class FakeBatches:
    def __init__(self, results):
        self._r = results

    def retrieve(self, bid):
        return NS(processing_status="ended")

    def results(self, bid):
        return iter(self._r)


def run_collect(strict):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        S.OUT_JS, S.STATE, S.RETRY = td / "sectors.js", td / "state.json", td / "retry.json"
        S.OUT_JS.write_text("window.KOS_SECTORS = " + json.dumps({"sectors": {"옛업종": {"lead": {"ko": "옛 글."}}}},
                                                                ensure_ascii=False) + ";\n", encoding="utf-8")
        cid = {S._cid(s): s for s in ("가업종", "나업종", "다업종")}
        S.STATE.write_text(json.dumps({"batch_id": "b1", "model": "x", "cid_map": cid,
                                       "agg": {s: INFO for s in cid.values()}}, ensure_ascii=False), encoding="utf-8")
        res = [NS(custom_id=S._cid("가업종"), result=NS(type="succeeded", message=msg(rep("업황이<sup>1</sup> 좋다."), ["https://www.reuters.com/a"]))),
               NS(custom_id=S._cid("나업종"), result=NS(type="succeeded", message=msg(rep(), []))),
               NS(custom_id=S._cid("다업종"), result=NS(type="succeeded", message=msg(rep("제공된 자료를 보면 좋다."), ["https://www.reuters.com/b"])))]
        S.collect(NS(messages=NS(batches=FakeBatches(res))), "2026-10-08 19:00", strict_sources=strict)
        raw = S.OUT_JS.read_text(encoding="utf-8")
        saved = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["sectors"]
        retry = json.loads(S.RETRY.read_text(encoding="utf-8"))["failed"] if S.RETRY.exists() else []
        return saved, retry


saved, retry = run_collect(True)
true("출처 있는 글은 저장(태그를 지운 채)", saved.get("가업종", {}).get("trends", {}).get("ko") == "업황이 좋다."
     and saved["가업종"].get("sources") == ["https://www.reuters.com/a"])
true("출처 0건은 저장하지 않고 다시 쓸 목록에", "나업종" not in saved and "나업종" in retry)
true("받은 자료를 가리키는 글은 저장하지 않는다", "다업종" not in saved and "다업종" in retry)
true("있던 업종은 그대로", "옛업종" in saved)
saved, retry = run_collect(False)
true("마지막 회차는 출처 0건도 받는다(출처 칸 없이)", "나업종" in saved and "sources" not in saved["나업종"])
eq("마지막 회차에도 글자 결함은 거른다", ("다업종" in saved, retry), (False, ["다업종"]))

# ── 묶는 줄 — 회차마다 출처 기준을 넘긴다 ───────────────────────
gen = (ROOT / "scripts" / "generate_sectors.py").read_text(encoding="utf-8")
true("auto 의 회차마다 마지막만 출처 0건을 받는다", "collect(cl, as_of, strict_sources=(rnd < ROUNDS))" in gen)

print(f"\n통과 {ok} · 실패 {fail}")
sys.exit(1 if fail else 0)
