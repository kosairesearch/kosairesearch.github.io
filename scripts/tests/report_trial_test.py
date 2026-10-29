#!/usr/bin/env python3
"""리포트 비용 시험(scripts/report_trial.py)이 리포트 v2 와 같은 요청을 내고, 비용을 공식 단가로 세고, 아무것도 저장하지 않는지.

  python3 scripts/tests/report_trial_test.py

  ① 설정 이름 — 모델 · 웹 검색 횟수 · 사고 깊이를 읽는다. 모르는 이름은 거절한다.
  ② 요청 — 리포트 v2 와 같은 시스템 지시문 · 작성 지시문 · 출력 한도 · 사고 · 검색 차단 도메인. 바뀌는 것은 세 가지뿐이다.
  ③ 비용 — 배치 단가 · 5분/1시간 캐시 쓰기 · 캐시 읽기 · 검색 요금, 하이쿠 5.5 의 긴 프롬프트 단가.
  ④ 받은 글 — 저장된 리포트를 모델 답처럼 넣으면 모양 · 검사를 통과한다. 깨진 답은 사유를 남긴다.
  ⑤ 표본 · 요청 이름 — 시총 순위가 고르게 퍼진 종목, 배치 이름 규칙, 비용 점검의 종류 분류.
  ⑥ 실행 — 가짜 배치로 끝까지 돌려 결과 표가 나오고, 즉시 호출을 막고, 요청 수 상한을 지키고, 파일을 바꾸지 않는다.
  ⑦ 작업 파일 — 수동 실행 · 읽기 권한 · 커밋 없음.
"""
import io
import json
import os
import subprocess
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import report_trial as T          # noqa: E402
import generate_reports_v2 as v2  # noqa: E402
import batch_cost_audit as A      # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


NS = types.SimpleNamespace
CONTENT_KEYS = ("title", "lead", "keypoints", "business", "earnings", "industry", "outlook",
                "valuation_comment", "bull", "bear", "risks", "checkpoints", "verdict")


def stored(tk):
    return json.loads((v2.OUT_DIR / f"{tk}.json").read_text(encoding="utf-8"))


def fake_message(tk, text=None, usage=None, stop="end_turn"):
    """저장된 리포트의 글 칸만 모델 답처럼 담은 가짜 응답."""
    if text is None:
        rep = stored(tk)
        text = "===JSON_START===" + json.dumps({k: rep[k] for k in CONTENT_KEYS}, ensure_ascii=False) + "===JSON_END==="
    u = usage or {"in": 9000, "cw": 30000, "cw1": 0, "cr": 40000, "out": 12000, "think": 3000, "search": 2}
    return NS(content=[NS(type="text", text=text, citations=None)], stop_reason=stop,
              usage=NS(input_tokens=u["in"], cache_creation_input_tokens=u["cw"],
                       cache_creation=NS(ephemeral_1h_input_tokens=u["cw1"], ephemeral_5m_input_tokens=u["cw"] - u["cw1"]),
                       cache_read_input_tokens=u["cr"], output_tokens=u["out"],
                       output_tokens_details=NS(thinking_tokens=u["think"]),
                       server_tool_use=NS(web_search_requests=u["search"])))


data = T.g.load_stocks()
stocks = data["stocks"]
by_tk = {s["ticker"]: s for s in stocks}

print("① 설정 이름")
ok(T.parse_config("h2") == {"model": "claude-haiku-5-5", "search": 2, "effort": None}, "h2 = 하이쿠 5.5 · 검색 2회 · 기본 사고")
ok(T.parse_config("s2l") == {"model": "claude-sonnet-5-5", "search": 2, "effort": "low"}, "s2l = 소넷 5.5 · 검색 2회 · 낮음")
ok(T.parse_config("o6m") == {"model": "claude-opus-5-5", "search": 6, "effort": "medium"}, "o6m = 지금 상위 300 설정")
bad_names = []
for nm in ("x2", "h", "h12", "s2q", ""):
    try:
        T.parse_config(nm)
    except ValueError:
        bad_names.append(nm)
ok(len(bad_names) == 5, "모르는 이름은 거절한다", str(bad_names))

print("② 요청 — 리포트 v2 와 같고 세 가지만 다르다")
st = by_tk["005930"]
q = T.material(st)
as_of = "2026-10-29 18:00"
p_h0 = T.request_params("h0", st, q, as_of, stocks)
p_h2 = T.request_params("h2", st, q, as_of, stocks)
p_s2l = T.request_params("s2l", st, q, as_of, stocks)
same_prompt = v2.build_prompt_v2(st, q, as_of, stocks=stocks)
ok(p_h2["messages"][0]["content"] == same_prompt and p_h2["system"][0]["text"] == v2.SYSTEM_V2
   and p_h2["system"][0].get("cache_control") == {"type": "ephemeral"}, "작성 지시문 · 시스템 지시문이 리포트 v2 와 같다")
ok(p_h2["max_tokens"] == 96000 and p_h2["thinking"] == {"type": "adaptive"}, "출력 한도 96,000 · 사고 adaptive")
ok("tools" not in p_h0, "검색 0회면 도구를 싣지 않는다")
t = p_h2["tools"][0]
ok(t["max_uses"] == 2 and t["type"] == v2.TOOLS[0]["type"] and "chickstockfi.com" in t["blocked_domains"]
   and v2.TOOLS[0]["max_uses"] == 6, "검색 횟수만 바꾸고 차단 도메인은 그대로(원본 설정은 건드리지 않는다)")
ok(p_s2l.get("output_config") == {"effort": "low"} and "output_config" not in p_h2, "사고 깊이는 적은 설정에만")
ok(p_h2["model"] == "claude-haiku-5-5" and p_s2l["model"] == "claude-sonnet-5-5", "모델")

print("③ 비용 — 공식 배치 단가")
u = {"in": 10000, "cw": 40000, "cw1": 0, "cr": 40000, "out": 12000, "think": 3000, "search": 2}
usd, long_ = T.cost("claude-haiku-5-5", u)
exp = (10000 * 0.05 + 40000 * 0.0625 + 40000 * 0.005 + 12000 * 0.25) / 1e6 + 0.02
ok(abs(usd - exp) < 1e-12 and not long_, "하이쿠 5.5 — 입력 합계 9만 토큰은 기본 단가", f"${usd:.5f}")
u_long = dict(u, cr=60000)
usd_l, long_l = T.cost("claude-haiku-5-5", u_long)
exp_l = (10000 * 0.25 + 40000 * 0.3125 + 60000 * 0.025 + 12000 * 1.25) / 1e6 + 0.02
ok(long_l and abs(usd_l - exp_l) < 1e-12, "하이쿠 5.5 — 10만 토큰을 넘으면 긴 프롬프트 단가", f"${usd_l:.5f}")
usd_s, long_s = T.cost("claude-sonnet-5-5", dict(u_long, cw1=10000))
exp_s = (10000 * 1.0 + 30000 * 1.25 + 10000 * 2.0 + 60000 * 0.05 + 12000 * 5.0) / 1e6 + 0.02
ok(not long_s and abs(usd_s - exp_s) < 1e-12, "소넷 5.5 — 1시간 캐시 쓰기는 입력의 2배 · 긴 단가 없음", f"${usd_s:.5f}")
u0 = {"in": 10000, "cw": 0, "cw1": 0, "cr": 0, "out": 12000, "think": 0, "search": 0}
ok(abs(T.cost("claude-haiku-5-5", u0)[0] * 20 - T.cost("claude-sonnet-5-5", u0)[0]) < 1e-12,
   "캐시 · 검색이 없으면 하이쿠 5.5 는 소넷 5.5 의 20분의 1", f"${T.cost('claude-haiku-5-5', u0)[0]:.4f} · ${T.cost('claude-sonnet-5-5', u0)[0]:.4f}")

print("④ 받은 글 — 저장된 리포트를 모델 답처럼")
row, rep = T.evaluate(fake_message("005930"), "h2", st, q)
ok(row["valid"] and row["bad"] == [] and not row.get("error") and T._passes(row),
   "저장된 리포트는 모양 · 검사를 통과한다", f"위반 {len(row['bad'])}건")
ok(row["usage"]["think"] == 3000 and row["usage"]["search"] == 2 and abs(row["usd"] - T.cost("claude-haiku-5-5", row["usage"])[0]) < 1e-12,
   "사용량 · 비용을 응답에서 읽는다")
s_ko, s_en = T.text_size(stored("005930"))
ok(row["ko"] == s_ko and row["en"] > 0, "글자 수 — 저장된 글과 같다", f"{row['ko']:,} · {row['en']:,}")
row_b, rep_b = T.evaluate(fake_message("005930", text="죄송합니다. 작성할 수 없습니다."), "h2", st, q)
ok(rep_b is None and row_b.get("error") and not T._passes(row_b), "JSON 이 없는 답은 사유를 남긴다", row_b.get("error", ""))
half = stored("000660")
half_text = json.dumps({k: half[k] for k in ("title", "lead", "keypoints")}, ensure_ascii=False)
row_h, _ = T.evaluate(fake_message("000660", text=half_text), "h2", by_tk["000660"], T.material(by_tk["000660"]))
ok(not row_h["valid"] and not T._passes(row_h), "절이 빠진 답은 모양 불통과")

print("⑤ 표본 · 요청 이름")
picked = T.pick(stocks)
ranked = [s["ticker"] for s in sorted(stocks, key=lambda s: s.get("mcap") or 0, reverse=True)]
pos = [ranked.index(s["ticker"]) + 1 for s in picked]
ok(len(picked) == len(T.RANKS) and len({s["ticker"] for s in picked}) == len(picked) and pos == sorted(pos)
   and all(p >= r for p, r in zip(pos, T.RANKS)), "시총 순위가 고르게 퍼진 서로 다른 종목", str(pos))
try:
    T.pick(stocks, ["999999"])
    ok(False, "없는 종목은 거절한다")
except ValueError:
    ok(True, "없는 종목은 거절한다")
cid = T.custom_id("s2l", "0011A0")
import re  # noqa: E402
ok(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", cid) and T.split_id(cid) == ("s2l", "0011A0") and T.split_id("005930") is None,
   "요청 이름 — 배치 규칙에 맞고 되읽힌다", cid)
ok(A.kind_of(cid) == "비용 시험", "비용 점검이 시험 요청을 따로 센다", A.kind_of(cid))

print("⑥ 실행 — 가짜 배치")


class FakeBatches:
    def __init__(self):
        self.created = []

    def create(self, requests):
        self.created.append(requests)
        return NS(id="msgbatch_trialfake")

    def retrieve(self, bid):
        return NS(processing_status="ended", request_counts=NS(processing=0, succeeded=1, errored=0))

    def results(self, bid):
        for r in self.created[-1]:
            cfg, tk = T.split_id(r["custom_id"])
            if tk == "000660" and cfg == "s2l":
                yield NS(custom_id=r["custom_id"], result=NS(type="errored", error=NS(error=NS(message="overloaded"))))
                continue
            yield NS(custom_id=r["custom_id"], result=NS(type="succeeded", message=fake_message(tk)))


class FakeClient:
    last = None

    def __init__(self, api_key=None):
        self.messages = NS(create=None, stream=None, batches=FakeBatches())
        FakeClient.last = self


def run_main(env):
    old_env, old_mod = dict(os.environ), sys.modules.get("anthropic")
    os.environ.update(env)
    sys.modules["anthropic"] = NS(Anthropic=FakeClient)
    buf, code = io.StringIO(), 0
    try:
        with redirect_stdout(buf):
            try:
                T.main()
            except SystemExit as e:
                code = e.code or 0
    finally:
        os.environ.clear()
        os.environ.update(old_env)
        if old_mod is not None:
            sys.modules["anthropic"] = old_mod
    return code, buf.getvalue()


def git_status():
    return subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout


before = git_status()
code, out = run_main({"ANTHROPIC_API_KEY": "sk-fake", "REPORT_TRIAL_CONFIGS": "h2,s2l",
                      "REPORT_TRIAL_TICKERS": "005930,000660", "REPORT_TRIAL_BATCH": "", "REPORT_TRIAL_SHOW": "1",
                      "GITHUB_STEP_SUMMARY": ""})
cl = FakeClient.last
reqs = cl.messages.batches.created[0] if cl and cl.messages.batches.created else []
ok(code == 0 and len(reqs) == 4 and {r["custom_id"] for r in reqs} == {
    "trial-h2-005930", "trial-s2l-005930", "trial-h2-000660", "trial-s2l-000660"}, "설정 2 × 종목 2 = 요청 4건을 배치 하나로", str(len(reqs)))
ok("| h2 (claude-haiku-5-5) | 2 |" in out and "| s2l (claude-sonnet-5-5) | 1 |" in out and "전 종목 환산" in out,
   "설정별 결과 표")
ok("받지 못한 요청" in out and "trial-s2l-000660: errored overloaded" in out, "받지 못한 요청을 사유와 함께")
ok("===== 005930" in out and "[verdict]" in out, "본문을 기록에 찍는다(앞 종목 하나)")
blocked = []
for fn in (cl.messages.create, cl.messages.stream):
    try:
        fn(model="x")
    except RuntimeError:
        blocked.append(1)
ok(len(blocked) == 2, "즉시 호출 창구를 막는다")
code2, out2 = run_main({"ANTHROPIC_API_KEY": "sk-fake", "REPORT_TRIAL_CONFIGS": "h2,h0,s2l,s6,o6m,h1,h3,h4",
                        "REPORT_TRIAL_TICKERS": "", "REPORT_TRIAL_BATCH": "", "GITHUB_STEP_SUMMARY": ""})
ok(code2 == 1 and not FakeClient.last.messages.batches.created and f"{T.MAX_REQ}건까지" in out2,
   "요청이 상한을 넘으면 주문하지 않는다", out2.strip()[:60])
ok(git_status() == before, "파일을 하나도 바꾸지 않는다")

print("⑦ 작업 파일")
wf = (ROOT / ".github" / "workflows" / "report_trial.yml").read_text(encoding="utf-8")
ok("workflow_dispatch" in wf and "schedule" not in wf and "contents: read" in wf and "git push" not in wf
   and "git commit" not in wf, "수동 실행 · 읽기 권한 · 커밋 없음")
ok(wf.count("secrets.ANTHROPIC_API_KEY") == 1 and "scripts/report_trial.py" in wf, "시험 단계에만 모델 열쇠를 넘긴다")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
