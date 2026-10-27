#!/usr/bin/env python3
"""배치 비용 점검(scripts/batch_cost_audit.py)이 모델을 부르지 않고 배치 결과만으로 바르게 세는지.

  python3 scripts/tests/batch_cost_audit_test.py

  ① 요청 이름으로 일의 종류를 가른다 — 리포트 작성 · v2 보정 · 교정 · 영문 채우기 · 검토 · 업종 분석 · 업종 분류 · 마케팅 · 브리핑.
  ② 가짜 배치 셋(기간 안 둘 · 기간 밖 하나)에서 성공한 요청만 배치 단가로 더하고, 기간 밖과 오류는 빼며, 처리 중인 배치는 따로 둔다.
     응답의 청구 조건(요금 등급 · 처리 지역 · 1시간 캐시)이 다르면 금액이 달라지고, 사고 토큰은 응답에서 정확히 센다.
  ③ 작성 요청은 모델별로 평균을 내고 잘린 글(max_tokens)을 센다. 표에 종류 · 날짜 · 배치가 모두 나온다.
  ④ 모델을 부르는 창구(messages.create · stream · batches.create)를 막고 돈다 — 부르면 실패.
"""
import datetime
import sys
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import batch_cost_audit as A  # noqa: E402
import generate_reports as g  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


print("① 요청 이름 → 일의 종류")
for cid, want in [("005930", "리포트 작성"), ("0126Z0", "리포트 작성"),
                  ("005930-0123456789abcdef01234567", "리포트 v2 보정"), ("fx1_005930_abc", "신규 상장 · 옛 형식 교정"),
                  ("en_005930_abc", "옛 형식 영문 채우기"), ("rv_005930_abc", "저장 전 검토"),
                  ("sec_0123456789abcdef", "업종 분석 작성"), ("c12", "업종 분류"), ("report", "마케팅 주간 보고"),
                  ("brief", "모닝브리핑(배치)"), ("zz", "기타")]:
    ok(A.kind_of(cid) == want, f"{cid} → {want}", A.kind_of(cid))

NOW = datetime.datetime(2026, 10, 27, 12, 0, tzinfo=datetime.timezone.utc)


def usage(i, cw, cr, o, s, tier="batch", geo="global", cw1h=0, think=None):
    return NS(input_tokens=i, cache_creation_input_tokens=cw, cache_read_input_tokens=cr, output_tokens=o,
              server_tool_use=NS(web_search_requests=s), service_tier=tier, inference_geo=geo,
              cache_creation=NS(ephemeral_5m_input_tokens=cw - cw1h, ephemeral_1h_input_tokens=cw1h),
              output_tokens_details=NS(thinking_tokens=think) if think is not None else None)


def msg(model, u, stop="end_turn", text="본문", think="생각"):
    return NS(model=model, usage=u, stop_reason=stop,
              content=[NS(type="thinking", thinking=think), NS(type="server_tool_use"),
                       NS(type="web_search_tool_result"), NS(type="text", text=text)])


def res(cid, m=None, typ="succeeded"):
    return NS(custom_id=cid, result=NS(type=typ, message=m))


def batch(bid, created, status="ended", n=0):
    return NS(id=bid, created_at=created, processing_status=status,
              request_counts=NS(succeeded=n, errored=0, canceled=0, expired=0, processing=0 if status == "ended" else n))


S55, O55 = "claude-sonnet-5-5", "claude-opus-5-5"
U1 = usage(5000, 50000, 40000, 16000, 5, think=9000)
U2 = usage(8000, 60000, 80000, 20000, 4, think=12000)
U3 = usage(3000, 0, 0, 1500, 0)
RESULTS = {
    "b_new": [res("005930", msg(S55, U1)), res("000660", msg(O55, U2, stop="max_tokens")),
              res("005930-0123456789abcdef01234567", msg(S55, U3)), res("035420", None, typ="errored")],
    "b_sec": [res("sec_0123456789abcdef", msg(S55, U1))],
    "b_old": [res("005380", msg(S55, U1))],
}
BATCHES = [batch("b_new", NOW - datetime.timedelta(hours=3), n=3),
           batch("b_run", NOW - datetime.timedelta(hours=1), status="in_progress", n=2),
           batch("b_sec", NOW - datetime.timedelta(days=2), n=1),
           batch("b_gone", NOW - datetime.timedelta(days=28, hours=20), n=7)] + \
          [batch(f"b_old{i}", NOW - datetime.timedelta(days=40 + i), n=1) for i in range(25)]


class FakeBatches:
    def __init__(self):
        self.read = []

    def list(self, limit=100):
        return iter(BATCHES)

    def results(self, bid):
        self.read.append(bid)
        if bid == "b_gone":     # 보관 기간 경계 — 결과가 먼저 지워졌다(실제 404 'has no available results')
            raise RuntimeError("Batch b_gone has no available results.")
        return iter(RESULTS.get(bid, RESULTS["b_old"]))

    def create(self, **_kw):
        raise AssertionError("배치를 만들면 안 된다")


class FakeMessages:
    def __init__(self):
        self.batches = FakeBatches()
        self.counted = 0

    def create(self, **_kw):
        raise AssertionError("즉시 호출을 하면 안 된다")

    stream = create

    def count_tokens(self, model, messages):
        self.counted += 1
        return NS(input_tokens=8 + len(messages[0]["content"]) * 100)


print("② 기간 안의 성공한 요청만 배치 단가로 센다")
cl = NS(messages=FakeMessages())
r = A.scan(cl, days=29, now=NOW, log=lambda *_: None)
ok(sorted(x["id"] for x in r["batches"]) == ["b_new", "b_sec"], "기간 안 · 끝난 배치 둘만 읽는다",
   str(cl.messages.batches.read))
ok(not any(b.startswith("b_old") for b in cl.messages.batches.read), "기간 밖 배치의 결과는 받지 않는다")
ok([p["id"] for p in r["pending"]] == ["b_run"], "처리 중인 배치는 따로 둔다")
ok([g_["id"] for g_ in r["gone"]] == ["b_gone"], "결과가 이미 지워진 배치는 멈추지 않고 따로 적는다")
want = g.cost_usd(S55, A._usage(msg(S55, U1)), batch=True) * 2 + g.cost_usd(O55, A._usage(msg(O55, U2)), batch=True) \
    + g.cost_usd(S55, A._usage(msg(S55, U3)), batch=True)
got = sum(b["usd"] for b in r["by_kind"].values())
ok(abs(got - want) < 1e-9, "합계 = 성공한 넷의 배치 단가 합(오류 하나는 빠짐)", f"{got:.4f} / {want:.4f}")
rec = sum(b["rec"] for b in r["by_kind"].values())
ok(abs(rec - want) < 1e-9, "청구 조건이 기록 방식과 같으면(배치 · 5분 캐시 · 전역) 두 합계가 같다")
ok(dict(r["tier"]) == {"batch": 4} and dict(r["geo"]) == {"global": 4}, "청구 조건을 센다", f"{dict(r['tier'])} {dict(r['geo'])}")
ok(r["by_kind"]["리포트 작성"]["n"] == 2 and r["by_kind"]["업종 분석 작성"]["n"] == 1
   and r["by_kind"]["리포트 v2 보정"]["n"] == 1, "종류별 요청 수")
one = g.cost_usd(S55, A._usage(msg(S55, U1)), batch=True)
ok(abs(one - ((5000 + 50000 * 1.25 + 40000 * 0.05) * 1.0 + 16000 * 5.0) / 1e6 - 0.05) < 1e-9,
   "Sonnet 5.5 배치 단가 — 입력 $1 · 캐시 쓰기 1.25배 · 캐시 읽기 0.05배 · 출력 $5 · 검색 $0.01", f"${one:.4f}")

print("③ 작성 요청의 모델별 평균 · 잘림 · 표")
ok(set(r["by_model_write"]) == {f"리포트 작성 · {S55}", f"리포트 작성 · {O55}", f"업종 분석 작성 · {S55}"},
   "작성 요청은 종류 · 모델로 나눈다", str(sorted(r["by_model_write"])))
ok(r["stop"][f"리포트 작성 · {O55}"].get("max_tokens") == 1, "잘린 글(max_tokens)을 센다")
share = A.text_share(cl, r["samples"], log=lambda *_: None)
ok(cl.messages.counted == 0 and not share, "사고 토큰이 실려 오면 토큰 세기를 하지 않는다", str(share))
bk = r["by_model_write"][f"리포트 작성 · {S55}"]
ok(bk["think_n"] == 1 and bk["think"] == 9000, "사고 토큰은 응답의 output_tokens_details 로 정확히 센다")

print("③-1 청구 조건이 다르면 금액이 다르다")
u1 = A._usage(msg(S55, U1))
base = A._bill(S55, u1, A._terms(msg(S55, U1)))
std = A._bill(S55, u1, A._terms(msg(S55, usage(5000, 50000, 40000, 16000, 5, tier="standard"))))
us = A._bill(S55, u1, A._terms(msg(S55, usage(5000, 50000, 40000, 16000, 5, geo="us"))))
h1 = A._bill(S55, u1, A._terms(msg(S55, usage(5000, 50000, 40000, 16000, 5, cw1h=50000))))
tok = base - 0.05
ok(abs((std - 0.05) - tok * 2) < 1e-9, "요금 등급이 standard 면 배치 할인이 없다(두 배)", f"${base:.4f} → ${std:.4f}")
ok(abs((us - 0.05) - tok * 1.1) < 1e-9, "처리 지역 us 는 1.1배", f"${us:.4f}")
ok(abs((h1 - base) - 50000 * (2.0 - 1.25) * 1.0 / 1e6) < 1e-9, "1시간 캐시 쓰기는 2배(5분은 1.25배)", f"${h1:.4f}")
old_resp = NS(model=S55, stop_reason="end_turn", content=[NS(type="text", text="본문")],
              usage=NS(input_tokens=10, cache_creation_input_tokens=0, cache_read_input_tokens=0, output_tokens=100,
                       server_tool_use=None))
t_old = A._terms(old_resp)
ok(t_old["tier"] == "?" and t_old["think"] is None, "청구 조건이 없는 응답도 읽는다(배치로 보고 · 사고는 모름)")
RESULTS["b_sec"] = [res("sec_0123456789abcdef", old_resp)]
cl2 = NS(messages=FakeMessages())
r2 = A.scan(cl2, days=29, now=NOW, log=lambda *_: None)
share2 = A.text_share(cl2, r2["samples"], log=lambda *_: None)
ok(cl2.messages.counted == 1 and f"업종 분석 작성 · {S55}" in share2, "사고 토큰이 없는 응답만 토큰 세기 표본으로 어림한다")
RESULTS["b_sec"] = [res("sec_0123456789abcdef", msg(S55, U1))]
text = A.report(r, share, (2, 0.5), days=29, dates={})
for need in ("청구 조건 확인", "일의 종류별", "모델별 평균", "금액 구성", "날짜별", "배치별", "리포트 v2 보정", "(처리 중)",
             "모닝브리핑(즉시 호출) 2편 $0.50", "9,000 (56%)", "(결과 지워짐)", "결과가 이미 지워진 배치 1개"):
    ok(need in text, f"표에 '{need}'")

print("③-2 주문 대비 저장 — 다시 주문한 종목 · 저장되지 않은 주문")
orders = {"005930": [("2026-10-20", 0.3, "b1"), ("2026-10-27", 0.2, "b2")],   # 두 번 주문 · 마지막 주문 뒤 저장
          "000660": [("2026-10-27", 0.4, "b2")],                              # 저장 안 됨(리포트가 그 전 날짜)
          "035420": [("2026-10-26", 0.25, "b3")]}                             # 저장됨
dates = {"005930": "2026-10-27", "000660": "2026-09-05", "035420": "2026-10-26"}
ws = A.waste(orders, dates)
ok(ws["n"] == 4 and ws["tickers"] == 3, "주문 4건 · 종목 3개")
ok(set(ws["repeat"]) == {"005930"} and ws["extra_n"] == 1 and abs(ws["extra_usd"] - 0.3) < 1e-9,
   "다시 주문 — 앞선 주문의 금액을 낭비로 센다", f"{ws['extra_n']} · ${ws['extra_usd']}")
ok(ws["unsaved_n"] == 1 and abs(ws["unsaved_usd"] - 0.4) < 1e-9,
   "주문한 날 뒤로 리포트가 없는 주문은 000660 하나(005930 의 앞선 주문은 다시 주문으로 센다)", str(ws["unsaved"]))
text2 = A.report(r, share, (0, 0.0), days=29, dates={})
ok("주문 대비 저장" in text2 and "저장되지 않은 주문" in text2, "표에 주문 대비 저장 절")

print("④ 모델을 부르는 창구는 막혀 있다")
src = (ROOT / "scripts" / "batch_cost_audit.py").read_text(encoding="utf-8")
ok("cl.messages.create = _blocked" in src and "cl.messages.batches.create = _blocked" in src,
   "main 이 즉시 호출 · 배치 만들기를 막는다")
wf = (ROOT / ".github" / "workflows" / "cost_audit.yml").read_text(encoding="utf-8")
ok("schedule" not in wf and "git push" not in wf and "contents: read" in wf, "작업 파일 — 수동 · 읽기 권한 · 커밋 없음")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
