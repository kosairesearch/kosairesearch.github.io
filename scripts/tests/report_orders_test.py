#!/usr/bin/env python3
"""리포트 주문 · 사용량 기록 회귀 검사 — DART · Anthropic 없이 가짜로 돌린다.

  python3 scripts/tests/report_orders_test.py

무엇을 고정해 두나 (전부 2026-10-03 에 확인한 일이다)
  ① 공시 트리거   목록 색인(reports-index.js)만 보고 대상을 골라, 08:57 에 회수한 9개 종목을 09:38 에
                  같은 공시로 다시 주문했다($2.65 · 계산값). 색인은 워치독 동기화 때만 고쳐진다 —
                  리포트 파일의 날짜도 본다.
  ② 신규 상장     같은 원인. 색인에 아직 없는 리포트 파일도 '있음'으로 친다.
  ③ 사용량 기록   옛 생성기 · 신규 상장용 배치 생성기는 사용량을 남기지 않았다. 잘려 버린 시도까지 센다.
  ④ 재시도 한도   옛 생성기가 실패 한 번에 '1회 최대 생성 수'를 1로 덮어썼다(REPORT_LIMIT 2 → 1개만).
  ⑤ 못 받은 배치  신규 상장용 배치가 80분을 넘기면 그대로 버려졌다(2026-09-24). 다음 실행이 먼저 받는다.
  ⑥ 정정 공시     정정 공시만 나온 종목을 따로 알린다(생성기가 숫자를 견준다). 숫자가 같았던 정정 공시는
                  다시 고르지 않는다(2026-10-07 같은 숫자로 14개를 다시 써 $3.97).
"""
import io
import json
import os
import sys
import tempfile
import types
from contextlib import redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import _reports_state as S            # noqa: E402
import check_filings as CF            # noqa: E402
import new_listings as NL             # noqa: E402
import generate_reports as G          # noqa: E402
import generate_reports_batch as GB   # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


# ── 상태 파일 · 리포트 폴더를 임시 폴더로 돌린다 ─────────────────────────────
TMP = Path(tempfile.mkdtemp(prefix="kosai_orders_"))
DATA = TMP / "data"
DATA.mkdir()
for attr in ("OUT_DIR", "V1_DIR", "SKIP_DIR", "HOLD_DIR", "FAIL_DIR", "BATCH_DIR", "CHECKED_DIR"):
    setattr(S, attr, DATA / getattr(S, attr).name)
    getattr(S, attr).mkdir(exist_ok=True)
S.LEGACY_STATE = DATA / "batch_state_v2.json"
S.REFRESH_FILE = DATA / "reports_v2_refresh"
S.SKIP_LEGACY = DATA / "reports_v2_skip.txt"
S.STOCKS_JS = DATA / "stocks.js"

A, B, C, D, E = "111111", "222222", "333333", "444444", "555555"
STOCKS = {"stocks": [
    {"ticker": A, "name": "가회사", "mcap": 5.0}, {"ticker": B, "name": "나회사", "mcap": 4.0},
    {"ticker": C, "name": "다회사", "mcap": 3.0}, {"ticker": D, "name": "라회사", "mcap": 2.0},
    {"ticker": E, "name": "마회사", "mcap": 1.0}], "dataDate": "20261002"}
STOCKS_JS = DATA / "stocks.js"
STOCKS_JS.write_text("window.KOS_LIVE_DATA = " + json.dumps(STOCKS, ensure_ascii=False) + ";\n", encoding="utf-8")
INDEX_JS = DATA / "reports-index.js"


def write_index(entries):
    INDEX_JS.write_text("window.KOS_REPORTS = " + json.dumps({"reports": entries}, ensure_ascii=False) + ";\n",
                        encoding="utf-8")


def write_report(folder, tk, date, title=True):
    rep = {"reportDate": date}
    if title:
        rep["title"] = {"ko": f"{tk} 제목", "en": "title"}
    (folder / f"{tk}.json").write_text(json.dumps(rep, ensure_ascii=False), encoding="utf-8")


def gh_out(run):
    """GITHUB_OUTPUT 으로 내보낸 값과 찍힌 글을 돌려준다."""
    path = TMP / "gh_output.txt"
    path.write_text("", encoding="utf-8")
    os.environ["GITHUB_OUTPUT"] = str(path)
    buf = io.StringIO()
    with redirect_stdout(buf):
        run()
    out = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        if "=" in ln:
            k, v = ln.split("=", 1)
            out[k] = v
    return out, buf.getvalue()


# ═══ ⓪ 리포트 파일의 날짜 ═══════════════════════════════════════════════
print("⓪ 리포트 파일의 날짜 — 색인과 같은 기준(제목이 있는 파일)")
write_report(S.OUT_DIR, A, "2026-10-03")
write_report(S.V1_DIR, A, "2026-09-01")
ok(S.file_report_date(A) == "2026-10-03", "v2 · v1 중 늦은 날짜", str(S.file_report_date(A)))
write_report(S.V1_DIR, C, "2026-10-03")
ok(S.file_report_date(C) == "2026-10-03", "v1 파일만 있어도 날짜를 읽는다")
write_report(S.OUT_DIR, E, "2026-10-03", title=False)
ok(S.file_report_date(E) is None, "제목 없는 파일은 세지 않는다(색인에도 오르지 않는다)")
(S.OUT_DIR / f"{D}.json").write_text("{깨진", encoding="utf-8")
ok(S.file_report_date(D) is None, "깨진 파일은 세지 않는다")
(S.OUT_DIR / f"{D}.json").unlink()
ok(S.file_report_date("999999") is None, "파일이 없으면 None")

# ═══ ① 공시 트리거 ═════════════════════════════════════════════════════
print("① 공시 트리거 — 회수 직후(색인 동기화 전)에 같은 공시로 다시 주문하지 않는다")
# 오늘 그대로: 색인은 9월 5일, 리포트 파일은 10월 3일(08:57 회수), 공시는 10월 2일.
write_index({A: {"reportDate": "2026-09-05"}, B: {"reportDate": "2026-09-05"}, E: {"reportDate": "2026-09-05"}})
write_report(S.OUT_DIR, B, "2026-09-05")           # B — 정말 낡은 리포트 → 다시 만든다
ROWS = [{"stock_code": tk, "report_nm": "[기재정정]반기보고서 (2026.06)", "rcept_dt": "20261002"}
        for tk in (A, B, C, D, E)]
ROWS.append({"stock_code": B, "report_nm": "주요사항보고서", "rcept_dt": "20261003"})   # 정기보고서 아님


class FakeDF:
    def __init__(self, rows):
        self.rows, self.empty = rows, not rows

    def iterrows(self):
        for i, r in enumerate(self.rows):
            yield i, r


class FakeDart:
    def __init__(self, key):
        pass

    def list(self, start=None, end=None, kind=None, final=None):
        return FakeDF(ROWS)


sys.modules["OpenDartReader"] = FakeDart
CF.STOCKS_JS, CF.REPORTS_JS, CF.DART_API_KEY, CF.MAX_PER_RUN = STOCKS_JS, INDEX_JS, "x", 120
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(A not in got, "A — 색인은 9월 5일이지만 파일이 10월 3일 → 뺀다(오늘 중복 주문된 경우)", str(got))
ok(C not in got, "C — 색인에 없어도 v1 파일이 10월 3일 → 뺀다", str(got))
ok(got == [B, D, E], "B(낡은 리포트) · D(리포트 없음) · E(제목 없는 파일) 만 주문, 시총 순", str(got))
ok("색인보다 새 리포트 파일이 있어 뺀 종목 2개" in text, "뺀 이유를 로그에 남긴다",
   next((ln.strip() for ln in text.splitlines() if "색인보다" in ln), "없음"))
ok(f"{B} 나회사 — 공시 20261002 (기존 리포트 20260905)" in text, "기존 리포트 날짜를 같이 찍는다")
ok(out.get("corrections") == f"{B}:20261002,{D}:20261002,{E}:20261002",
   "⑥ 정정 공시만 나온 종목은 접수일과 함께 따로 알린다", str(out.get("corrections")))
ok(CF.is_amendment("[기재정정]반기보고서 (2026.06)") and CF.is_amendment(" [첨부추가]사업보고서 (2025.12)")
   and not CF.is_amendment("반기보고서 (2026.06)"), "⑥ 보고서명 앞 꼬리표로 정정 공시를 가린다")

# ⑥ 처음 내는 보고서가 하나라도 있으면 정정 공시로 치지 않는다(새 기간의 숫자다)
ROWS.append({"stock_code": D, "report_nm": "반기보고서 (2026.06)", "rcept_dt": "20261001"})
out, text = gh_out(CF.main)
ok(out.get("corrections") == f"{B}:20261002,{E}:20261002", "⑥ 원래 보고서가 함께 있는 D 는 정정 목록에서 뺀다",
   str(out.get("corrections")))
ok(f"{B} 나회사 — 공시 20261002 (기존 리포트 20260905) · 정정 공시 — 숫자가 바뀐 경우에만 다시 쓴다" in text,
   "⑥ 정정 공시라는 것을 로그에 남긴다")
ROWS.pop()

# ⑥ 숫자가 같았던 정정 공시는 다시 고르지 않는다 — 그보다 새 공시가 오면 다시 고른다
S.mark_checked(B, "20261002")
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(got == [D, E], "⑥ 숫자가 같았던 B 는 같은 공시로 다시 고르지 않는다", str(got))
ok(f"정정 공시를 견줘 숫자가 같았던 종목 1개는 뺀다: {B}" in text, "⑥ 뺀 이유를 로그에 남긴다")
ROWS.append({"stock_code": B, "report_nm": "[기재정정]반기보고서 (2026.06)", "rcept_dt": "20261005"})
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(got == [B, D, E] and f"{B}:20261005" in out.get("corrections", ""), "⑥ 그 뒤의 새 정정 공시는 다시 고른다",
   f"{got} {out.get('corrections')}")
ok("숫자가 같았던 종목" not in text, "⑥ 다시 고른 종목은 '뺐다'고 적지 않는다")
ROWS.pop()
(S.CHECKED_DIR / B).unlink()

# ⑦ 저장 문턱에 연속으로 걸린 종목은 공시 트리거가 다시 주문하지 않는다(2026-10-10) — 저장하지 못한 리포트는 공시보다
#    낡은 채로 남아 하루 세 번 같은 공시로 다시 주문됐다. 고치기 전 코드면 B 가 계속 주문된다.
for _ in range(S.FAIL_LIMIT):
    S.bump_fail(B)
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(B not in got and got == [D, E], "⑦ 저장 문턱에 3번 연속 걸린 B 는 다시 주문하지 않는다", str(got))
ok(f"저장 문턱에 {S.FAIL_LIMIT}번 연속 걸려 뺀 종목 1개" in text and B in text, "⑦ 뺀 이유를 로그에 남긴다",
   next((ln.strip() for ln in text.splitlines() if "저장 문턱" in ln), "없음"))
S.clear_fail(B)
S.bump_fail(B)
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(got == [B, D, E], "⑦ 한두 번 실패는 그대로 다시 주문한다(일시 장애 · 다음 회차가 다시 만든다)", str(got))
S.clear_fail(B)

# 갱신 기준일(전 종목 다시 쓰기)이 있으면 그보다 낡은 리포트는 워치독 몫 — 판단도 늦은 날짜로
S.REFRESH_FILE.write_text("2026-09-20\n", encoding="utf-8")
out, text = gh_out(CF.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(got == [], "갱신 기준일보다 낡은 B · D · E 는 워치독 몫으로 뺀다", str(got))
S.REFRESH_FILE.unlink()

# ═══ ② 신규 상장 ═══════════════════════════════════════════════════════
print("② 신규 상장 — 색인에 아직 없는 리포트 파일도 '있음'")
known = DATA / "known_tickers.json"
known.write_text(json.dumps([A, B, C, D, E]), encoding="utf-8")   # 신규 진입 없음 — 재시도만 본다
write_index({A: {"reportDate": "2026-09-05"}, B: {"reportDate": "2026-09-05"}})
NL.STOCKS_JS, NL.KNOWN, NL.REPORTS_JS = STOCKS_JS, known, INDEX_JS
out, text = gh_out(NL.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(C not in got, "C — 리포트 파일이 있으니 다시 만들지 않는다", str(got))
ok(got == [D, E], "D(파일 없음) · E(제목 없는 파일) 만 재시도", str(got))
ok("색인 동기화 전 리포트 파일이 있는 종목 1개" in text, "로그에 남긴다")
# 연속 3번 저장하지 못한 종목은 다시 주문하지 않는다(2026-10-09) — 2번까지는 다시 주문한다
NL.FAIL_JS = DATA / "new_listing_fail.json"
NL.FAIL_JS.write_text(json.dumps({D: {"n": 3, "last": "2026-10-09 23:30", "why": "검사 위반(style)"},
                                  E: {"n": 2, "last": "2026-10-09 23:30", "why": "불완전(잘림 의심)"}}), encoding="utf-8")
out, text = gh_out(NL.main)
got = out.get("new_tickers", "").split(",") if out.get("new_tickers") else []
ok(got == [E] and "다시 주문하지 않는다" in text and D in text, "연속 3번 저장하지 못한 D 는 빼고, 2번인 E 는 다시 주문한다", str(got))
NL.FAIL_JS.unlink()
# 색인을 못 읽으면 재시도하지 않는다(폭주 방지 그대로) — 파일로 채운 수가 그 판단을 바꾸지 않는다
INDEX_JS.write_text("깨진 색인", encoding="utf-8")
out, text = gh_out(NL.main)
ok(out.get("new_tickers") == "" and "재시도 대상은 이번에 보지 않는다" in text,
   "색인이 깨지면 파일이 있어도 재시도하지 않는다(폭주 방지 그대로)", repr(out.get("new_tickers")))
for p in S.OUT_DIR.glob("*.json"):
    p.unlink()
for p in S.V1_DIR.glob("*.json"):
    p.unlink()

# ═══ ③ 옛 생성기 사용량 ═════════════════════════════════════════════════
print("③ 옛 생성기 — 사용량 기록(잘려 버린 시도 포함)")
USAGE = types.SimpleNamespace(input_tokens=100_000, cache_creation_input_tokens=2_000, cache_read_input_tokens=8_000,
                              output_tokens=20_000, server_tool_use=types.SimpleNamespace(web_search_requests=5))
u = G.usage_of(types.SimpleNamespace(usage=USAGE))
ok(u == {"in": 100_000, "cache_w": 2_000, "cache_r": 8_000, "out": 20_000, "search": 5}, "응답의 사용량을 읽는다", str(u))
# Sonnet 4.6 정가 $3/$15: (100,000 + 2,000×1.25 + 8,000×0.1)×3/1M + 20,000×15/1M + 5×0.01
ok(abs(G.cost_usd("claude-sonnet-4-6", u) - 0.6599) < 1e-6, "정가 계산", f"{G.cost_usd('claude-sonnet-4-6', u):.4f}")
ok(abs(G.cost_usd("claude-sonnet-4-6", u, batch=True) - 0.35495) < 1e-6, "배치는 토큰 값의 절반 · 검색은 그대로",
   f"{G.cost_usd('claude-sonnet-4-6', u, batch=True):.5f}")
ok(G.usage_of(types.SimpleNamespace()) is None, "사용량이 없는 응답은 None")


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return self.msg


class FakeMsgs:
    def __init__(self, msgs):
        self.msgs, self.calls = list(msgs), 0

    def stream(self, **kw):
        self.calls += 1
        return FakeStream(self.msgs.pop(0))


def msg(text, usage=USAGE, stop="end_turn"):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text, citations=None)],
                                 usage=usage, stop_reason=stop)


G.build_prompt = lambda *a, **k: "프롬프트"
G.log = lambda *a, **k: None
G.MODEL = "claude-sonnet-4-6"
G.SPENT.clear()
cut = msg('===JSON_START==={"business": "x"}===JSON_END===', stop="max_tokens")
try:
    G.generate_one(types.SimpleNamespace(messages=FakeMsgs([cut])), {"ticker": A, "name": "가회사"}, "2026-10-03 02:00")
    ok(False, "잘린 글은 예외여야 한다")
except ValueError:
    pass
sp = G.SPENT.get("claude-sonnet-4-6") or {}
ok(sp.get("n") == 1 and sp.get("out") == 20_000 and abs(sp.get("usd", 0) - 0.6599) < 1e-6,
   "잘려 버린 시도도 사용량을 센다", str(sp))

# ═══ ④ 재시도 한도가 '1회 최대 생성 수'를 덮어쓰지 않는다 ═══════════════
print("④ 옛 생성기 — 한 번 실패해도 1회 최대 생성 수는 그대로")
calls = []


def fake_generate_one(client, st, as_of, dart_block=""):
    calls.append(st["ticker"])
    if calls.count(st["ticker"]) == 1 and st["ticker"] == A:
        raise ValueError("불완전한 리포트(잘림 의심, stop=max_tokens)")
    return {"title": {"ko": "t", "en": "t"}}, 0


written = {}
G.generate_one = fake_generate_one
G.load_stocks = lambda: {"stocks": [{"ticker": A, "name": "가회사"}, {"ticker": B, "name": "나회사"}], "dataDate": "20261002"}
G.load_existing_reports = lambda: {}
G.get_dart_financials = lambda tk: ""
G.write_reports = lambda reports, model, as_of: written.update(reports)
G.time.sleep = lambda *_: None
G.anthropic.Anthropic = lambda **k: object()
os.environ.update({"ANTHROPIC_API_KEY": "x", "REPORT_TICKERS": f"{A},{B}", "REPORT_LIMIT": "2"})
G.main()
ok(sorted(written) == [A, B], "REPORT_LIMIT 2 — A 가 한 번 실패해도 A · B 둘 다 만든다", f"만든 종목 {sorted(written)} · 호출 {calls}")
for k in ("REPORT_TICKERS", "REPORT_LIMIT"):
    os.environ.pop(k, None)

# ═══ ⑤ 신규 상장용 배치 — 사용량 · 못 받은 배치 먼저 회수 ════════════════
print("⑤ 신규 상장용 배치 — 사용량 기록 · 지난 실행이 못 받은 배치를 먼저 회수")
GOOD = {"title": {"ko": "제목", "en": "t"}, "verdict": "종합 의견", "business": "사업",
        "keypoints": ["a", "b", "c"], "risks": [{"x": 1}, {"y": 2}]}


def bres(tk, kind="succeeded", text=None):
    m = msg(text or ("===JSON_START===" + json.dumps(GOOD, ensure_ascii=False) + "===JSON_END==="))
    return types.SimpleNamespace(custom_id=tk, result=types.SimpleNamespace(type=kind, message=m))


class FakeBatches:
    """생성 배치는 받은 결과를, 검토 배치(2026-10-09)는 '고칠 것 없음' 답을 돌려준다."""
    def __init__(self, status, results):
        self.status, self._results, self.retrieved, self.reviews = status, results, [], []

    def create(self, requests):
        self.reviews.append(requests)
        return types.SimpleNamespace(id=f"msgbatch_RV{len(self.reviews)}")

    def retrieve(self, bid):
        self.retrieved.append(bid)
        return types.SimpleNamespace(processing_status="ended" if bid.startswith("msgbatch_RV") else self.status,
                                     request_counts=types.SimpleNamespace(processing=0, succeeded=1, errored=0))

    def results(self, bid):
        if bid.startswith("msgbatch_RV"):
            reqs = self.reviews[int(bid[11:]) - 1]
            return [types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(
                type="succeeded", message=msg("===JSON_START===" + json.dumps({"patches": []}) + "===JSON_END==="))) for r in reqs]
        return list(self._results)


def fake_client(status, results):
    return types.SimpleNamespace(messages=types.SimpleNamespace(batches=FakeBatches(status, results)))


GB.STATE_JS = DATA / "batch_state.json"
GB.FAIL_JS = DATA / "new_listing_fail.json"
GB.load_existing = lambda: ({}, set())
GB.log = lambda *a, **k: None
written.clear()
G.load_stocks = lambda: {"stocks": [{"ticker": D, "name": "라회사"}], "dataDate": "20261002"}

# (a) 표시가 없는 옛 상태 파일 — 이미 받았는지 모르니 건드리지 않는다
GB.STATE_JS.write_text(json.dumps({"batch_id": "msgbatch_OLD", "model": "claude-sonnet-4-6", "count": 1}), encoding="utf-8")
cl = fake_client("ended", [bres(D)])
GB.collect_pending(cl, "2026-10-03 23:30")
ok(cl.messages.batches.retrieved == [] and not written, "표시 없는 옛 상태는 다시 받지 않는다")

# (b) 지난 실행이 80분을 넘겨 못 받은 배치 — 다음 실행이 먼저 받고 사용량을 남긴다
GB.STATE_JS.write_text(json.dumps({"batch_id": "msgbatch_LATE", "model": "claude-sonnet-4-6", "count": 1,
                                   "pending": True}), encoding="utf-8")
cl = fake_client("ended", [bres(D), bres(E, text="===JSON_START==={\"business\": \"x\"}===JSON_END===")])
ok(GB.REVIEW is False, "저장 전 검토는 기본으로 꺼져 있다(2026-10-09 시험에서 틀린 고침 · NEW_LISTING_REVIEW=1 로만 켠다)", str(GB.REVIEW))
GB.REVIEW = True                    # 아래는 검토를 켰을 때의 길 — 검토 요청이 배치 하나로 나가는지 본다
GB.collect_pending(cl, "2026-10-03 23:30")
GB.REVIEW = False
st = json.loads(GB.STATE_JS.read_text(encoding="utf-8"))
ok(D in written and E not in written, "못 받은 배치의 리포트를 저장한다(불완전한 글은 버린다)", str(sorted(written)))
fl = json.loads(GB.FAIL_JS.read_text(encoding="utf-8")) if GB.FAIL_JS.exists() else {}
ok(fl.get(E, {}).get("n") == 1 and D not in fl, "저장하지 못한 E 를 센다(저장한 D 는 세지 않는다)", str(fl))
ok(len(cl.messages.batches.reviews) == 1 and [r["custom_id"][:9] for r in cl.messages.batches.reviews[0]] == ["rv_" + D],
   "저장 전 검토를 배치 하나로 주문한다(완전한 글만)", str([[r["custom_id"] for r in q] for q in cl.messages.batches.reviews]))
ok(not st.get("pending") and st.get("collected") == "2026-10-03 23:30", "회수 표시", str({k: st.get(k) for k in ('pending', 'collected')}))
ua = (st.get("usage") or {}).get("claude-sonnet-4-6") or {}
ok(ua.get("n") == 2 and abs(ua.get("usd", 0) - round(0.35495 * 2, 3)) < 1e-6,
   "버린 결과까지 배치 단가로 사용량을 남긴다", str(ua))

# (c) 지난 배치가 아직 처리 중이면 새로 주문하지 않는다 — 상태 파일을 덮어써 지난 배치를 잃지 않게
GB.STATE_JS.write_text(json.dumps({"batch_id": "msgbatch_SLOW", "model": "claude-sonnet-4-6", "count": 1,
                                   "pending": True}), encoding="utf-8")
submitted = []
GB.submit = lambda cl, as_of: submitted.append(as_of) or "msgbatch_NEW"
GB.client = lambda: fake_client("in_progress", [])
sys.argv = ["generate_reports_batch.py", "auto"]
GB.main()
st = json.loads(GB.STATE_JS.read_text(encoding="utf-8"))
ok(submitted == [] and st.get("batch_id") == "msgbatch_SLOW" and st.get("pending"),
   "처리 중인 지난 배치가 있으면 새 주문을 미룬다", f"submit {len(submitted)}회 · {st.get('batch_id')}")

# (d) 받은 뒤에는 평소대로 주문한다
GB.STATE_JS.write_text(json.dumps({"batch_id": "msgbatch_DONE", "model": "claude-sonnet-4-6", "count": 1,
                                   "collected": "2026-10-02 05:00"}), encoding="utf-8")
GB.poll = lambda cl, bid: False
GB.main()
ok(submitted != [], "받을 배치가 없으면 평소대로 주문한다")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
