#!/usr/bin/env python3
"""실제 청구 내역 조회(scripts/billing_report.py)가 쪽을 넘기며 다 받고, 바르게 묶고, 잠가서만 찍는지.

  python3 scripts/tests/billing_report_test.py

  ① 비용 기록(센트 단위 문자열)을 달러로 바꿔 월별 · 모델별 · 항목별 · 요금 등급별 · 일별로 묶는다.
  ② 쪽(page)을 끝까지 넘겨 받는다 — 관리자 키는 머리글(x-api-key)로만 보낸다.
  ③ 사용량 기록은 월별 · 모델 · 등급별 토큰과 웹 검색 횟수로 묶는다.
  ④ 관리자 키 · 열쇠가 없으면 숫자를 하나도 찍지 않고 멈춘다. 열쇠가 있으면 잠근 줄만 찍고, 연 글이 원문과 같다.
  ⑤ 작업 파일 — billing 단계에만 관리자 키를 넘기고, 커밋하지 않는다.
"""
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import billing_report as B  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


COST_PAGES = {
    None: {"data": [{"starting_at": "2026-09-05T00:00:00Z", "results": [
        {"amount": "2500.5", "model": "claude-sonnet-5", "cost_type": "tokens", "token_type": "output_tokens",
         "service_tier": "batch", "description": "Claude Sonnet 5 Usage - Output Tokens, Batch"},
        {"amount": "1000", "model": "claude-sonnet-5", "cost_type": "tokens",
         "token_type": "cache_creation.ephemeral_5m_input_tokens", "service_tier": "batch"},
        {"amount": "463", "cost_type": "web_search", "description": "Web Search"}]}],
        "has_more": True, "next_page": "p2"},
    "p2": {"data": [{"starting_at": "2026-10-20T00:00:00Z", "results": [
        {"amount": "4000", "model": "claude-opus-5-5", "cost_type": "tokens", "token_type": "output_tokens",
         "service_tier": "batch"},
        {"amount": "30", "model": "claude-opus-5-5", "cost_type": "tokens", "token_type": "uncached_input_tokens",
         "service_tier": "standard"}]}], "has_more": False},
}
USAGE_PAGES = {
    None: {"data": [{"starting_at": "2026-09-05T00:00:00Z", "results": [
        {"model": "claude-sonnet-5", "service_tier": "batch", "uncached_input_tokens": 100,
         "cache_creation": {"ephemeral_5m_input_tokens": 50, "ephemeral_1h_input_tokens": 5},
         "cache_read_input_tokens": 70, "output_tokens": 900, "server_tool_use": {"web_search_requests": 4}}]}],
        "has_more": False},
}
SEEN = []


def fake_get(url, admin_key):
    SEEN.append((url, admin_key))
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    page = (q.get("page") or [None])[0]
    pages = COST_PAGES if "/cost_report" in url else USAGE_PAGES
    return pages[page]


print("① 비용 기록을 달러로 묶는다")
cost = B.summarize_cost(COST_PAGES[None]["data"] + COST_PAGES["p2"]["data"])
ok(abs(cost["month"]["2026-09"] - 39.635) < 1e-9, "9월 합계 = (2500.5 + 1000 + 463) 센트", f"${cost['month']['2026-09']:.4f}")
ok(abs(cost["month"]["2026-10"] - 40.30) < 1e-9, "10월 합계", f"${cost['month']['2026-10']:.2f}")
ok(cost["item"]["2026-09"]["출력"] == 25.005 and cost["item"]["2026-09"]["캐시 쓰기"] == 10.0
   and cost["item"]["2026-09"]["웹 검색"] == 4.63, "항목 — 출력 · 캐시 쓰기 · 웹 검색", str(dict(cost["item"]["2026-09"])))
ok(abs(cost["tier"]["2026-10"]["standard"] - 0.30) < 1e-9 and cost["tier"]["2026-10"]["batch"] == 40.0,
   "요금 등급 — 배치와 일반을 가른다", str(dict(cost["tier"]["2026-10"])))
ok(cost["model"]["2026-09"]["(모델 없음)"] == 4.63, "모델이 없는 줄(웹 검색)도 빠뜨리지 않는다")

print("② 쪽을 끝까지 받고, 관리자 키는 머리글로만")
text = B.run("sk-ant-admin01-test", since="2026-06-01", today=__import__("datetime").date(2026, 10, 27), get=fake_get)
cost_urls = [u for u, _ in SEEN if "/cost_report" in u]
ok(len(cost_urls) == 2 and "page=p2" in cost_urls[1], "비용 기록 두 쪽을 받는다", str(len(cost_urls)))
ok(all("sk-ant-admin01" not in u for u, _ in SEEN) and all(k == "sk-ant-admin01-test" for _, k in SEEN),
   "관리자 키는 주소에 넣지 않는다")
ok("starting_at=2026-06-01T00%3A00%3A00Z" in cost_urls[0] and "ending_at=2026-10-28" in cost_urls[0]
   and "group_by%5B%5D=description" in cost_urls[0], "기간과 묶음 조건", cost_urls[0][:160])
ok(f"2026-09  ${39.635:,.2f}" in text and "2026-10  $40.30" in text and f"합계  ${39.635 + 40.30:,.2f}" in text,
   "월별 · 전체 합계가 글에 나온다")

print("③ 사용량 기록")
ok("claude-sonnet-5 · batch  입력 100 · 캐시 쓰기 55 · 캐시 읽기 70 · 출력 900 · 웹 검색 4" in text,
   "월별 · 모델 · 등급별 토큰과 웹 검색 횟수")

print("④ 키 · 열쇠가 없으면 숫자를 찍지 않고, 있으면 잠근 줄만")


def run_main(env):
    old = dict(os.environ)
    os.environ.update(env)
    for k in ("ANTHROPIC_ADMIN_KEY", "KEY"):
        if k not in env:
            os.environ.pop(k, None)
    buf = io.StringIO()
    code = 0
    try:
        with redirect_stdout(buf):
            try:
                B.main()
            except SystemExit as e:
                code = e.code or 0
    finally:
        os.environ.clear()
        os.environ.update(old)
    return code, buf.getvalue()


code, out = run_main({})
ok(code == 1 and "$" not in out and "관리자 키 없음" in out, "관리자 키가 없으면 멈춘다")
code, out = run_main({"ANTHROPIC_ADMIN_KEY": "sk-ant-admin01-test"})
ok(code == 1 and "$" not in out and "열쇠 없음" in out, "잠글 열쇠가 없으면 조회하지 않는다")

with tempfile.TemporaryDirectory() as td:
    os.environ["KOSAI_MARKETING_KEY"] = str(Path(td) / "k.pem")
    import importlib
    import marketing_seal as M
    importlib.reload(M)
    pub = M.newkey()
    orig_run = B.run
    B.run = lambda admin_key, **kw: "실제 청구 내역 — 시험\n  2026-09  $39.64"
    try:
        code, out = run_main({"ANTHROPIC_ADMIN_KEY": "sk-ant-admin01-test", "KEY": pub})
    finally:
        B.run = orig_run
    ok(code == 0 and "$39.64" not in out and "KOSAI-SEALED" in out and "sk-ant-admin01" not in out,
       "열쇠가 있으면 잠근 줄만 찍고, 금액 · 관리자 키는 기록에 없다")
    opened = M.open_sealed(out).decode("utf-8")
    ok("$39.64" in opened, "연 글이 원문과 같다")
    os.environ.pop("KOSAI_MARKETING_KEY", None)

print("⑤ 작업 파일")
wf = (ROOT / ".github" / "workflows" / "cost_audit.yml").read_text(encoding="utf-8")
ok(wf.count("secrets.ANTHROPIC_ADMIN_KEY") == 1 and "if: ${{ inputs.mode == 'billing' }}" in wf,
   "관리자 키는 billing 단계에만 넘긴다")
ok("git push" not in wf and "contents: read" in wf and "schedule" not in wf, "수동 · 읽기 권한 · 커밋 없음")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
