#!/usr/bin/env python3
"""모델 호출은 Batch API 로만 — 모닝브리핑만 예외(2026-10-08 사장 "우리는 무조건 batch API만을 사용해야 된다고. 모닝브리핑 제외하고.").

  python3 scripts/tests/batch_only_test.py

즉시 호출(messages.create · messages.stream)은 배치의 두 배 값이다. 10월 8일에 훑어보니 예약 작업 둘이
즉시 호출을 하고 있었다 — 신규 상장 작업의 업종 분류(평일 밤)와 마케팅 주간 보고(매주 월요일 아침).
리포트 회수 단계의 보정(영문 채우기 · 표현 교정)도 즉시 호출이었다. 전부 배치로 바꾸고, 새로 생기면
여기서 걸리게 한다.

  ① scripts/ 의 즉시 호출 자리를 모두 찾는다(파이썬은 구문 나무로 — 주석 · 문자열은 세지 않는다).
     허용은 셋뿐이다.
       · 모닝브리핑(generate_brief.py) — 사장이 정한 예외.
       · 배치 대기열을 거치는 보정 함수 셋(영문 채우기 · 표현 교정 · 저장 전 검토) — 받는 cl 이 _RepairQueue 다
         (리포트 파이프라인 검사 (j) · (l)이 본다).
       · 쓰지 않는 옛 스크립트 — 예약(schedule) 작업이 돌리지 않을 때만. 예약을 걸면 여기서 걸린다.
  ② 배치로 바꾼 생성기가 즉시 호출 창구를 막아 두었는지 — 실수로 부르면 그 자리에서 멈춘다.
  ③ 업종 분류가 배치 하나로 주문하고 답으로 캐시를 채우는지, 늦으면 취소하는지(가짜 배치로).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT / ".github" / "workflows"

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


# 즉시 호출을 해도 되는 파일 — 사유와 함께
ALLOWED = {
    "scripts/generate_brief.py": "모닝브리핑 — 사장이 정한 예외(발행 시각을 지켜야 한다)",
}
# 받는 클라이언트가 배치 대기열(_RepairQueue)인 함수
ROUTED = {
    ("scripts/generate_reports_v2.py", "fill_missing_en"): "회수 단계 영문 채우기 — 배치 대기열로 간다",
    ("scripts/check_report_text.py", "repair"): "회수 단계 표현 교정 — 배치 대기열로 간다",
    ("scripts/check_report_text.py", "review"): "회수 단계 저장 전 검토(2026-10-09) — 배치 대기열로 간다",
}
# 쓰지 않는 옛 스크립트 — 수동 실행만 남아 있다. 예약 작업이 돌리면 실패한다.
LEGACY = {
    "scripts/daily_x_post.py": "엑스 자동 게시 — 쓰지 않는다(2026-10-08 사장 '나 X 안 해')",
    "scripts/news_alert.py": "뉴스 알림 — 수동 실행만",
    "scripts/generate_reports.py": "옛 리포트 생성기(즉시 호출) — 수동 실행만",
}


def py_sites(path):
    """[(줄, 감싼 함수 이름, 'create'|'stream')] — x.messages.create(…) · x.messages.stream(…) 꼴의 호출."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []

    def walk(node, fn):
        for ch in ast.iter_child_nodes(node):
            name = ch.name if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            if isinstance(ch, ast.Call) and isinstance(ch.func, ast.Attribute) and ch.func.attr in ("create", "stream"):
                v = ch.func.value
                if isinstance(v, ast.Attribute) and v.attr == "messages":
                    out.append((ch.lineno, fn, ch.func.attr))
            walk(ch, name)

    walk(tree, None)
    return out


JS_CALL = re.compile(r"\.messages\.(create|stream)\s*\(|api\.anthropic\.com/v1/messages(?![/\w]*(batches|count_tokens))")


def js_sites(path):
    out = []
    for i, ln in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        s = ln.strip()
        if s.startswith("//") or s.startswith("*"):
            continue
        if JS_CALL.search(ln):
            out.append((i, None, "http"))
    return out


def scheduled_runners(rel):
    """그 스크립트를 돌리는 예약 작업 파일 이름들."""
    hits = []
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        txt = wf.read_text(encoding="utf-8")
        if re.search(r"^\s*schedule\s*:", txt, re.M) and re.search(rf"(^|[\s/]){re.escape(rel)}\b", txt):
            hits.append(wf.name)
    return hits


print("① 즉시 호출 자리 — 모닝브리핑 · 배치 대기열 보정 · 예약 없는 옛 스크립트만")
# 엑스 맨션 자동응답 봇(x-bot/)은 보지 않는다 — 쓰지 않는 기능이다(2026-10-08 사장 "나 X 안 해").
found = {}
files = [p for p in sorted(SCRIPTS.rglob("*")) if "tests" not in p.relative_to(SCRIPTS).parts]
files += sorted((ROOT / "functions").rglob("*")) if (ROOT / "functions").exists() else []
for p in files:
    if not p.is_file() or "node_modules" in p.parts or "tests" in p.relative_to(ROOT).parts:
        continue
    rel = p.relative_to(ROOT).as_posix()
    if p.suffix == ".py":
        try:
            sites = py_sites(p)
        except SyntaxError as e:
            ok(False, f"{rel} 를 읽을 수 없다", str(e))
            continue
    elif p.suffix in (".js", ".mjs"):
        sites = js_sites(p)
    else:
        continue
    if sites:
        found[rel] = sites

bad = []
for rel, sites in found.items():
    if rel in ALLOWED:
        continue
    if rel in LEGACY:
        runners = scheduled_runners(rel)
        ok(not runners, f"{rel} — {LEGACY[rel]}", "예약 작업이 돌린다: " + ", ".join(runners) if runners else "예약 없음")
        continue
    for ln, fn, kind in sites:
        if (rel, fn) in ROUTED:
            continue
        bad.append(f"{rel}:{ln} ({fn or '모듈'} · {kind})")
ok(not bad, "그 밖의 즉시 호출이 없다", "; ".join(bad) if bad else f"즉시 호출이 있는 파일 {len(found)}개는 모두 허용 목록")
for (rel, fn), why in ROUTED.items():
    ok(any(f == fn for _, f, _k in found.get(rel, [])), f"{rel} {fn} — {why}",
       "자리가 없어졌으면 허용 목록에서 지울 것")
ok("scripts/generate_brief.py" in found, "모닝브리핑은 즉시 호출(예외) — 목록이 낡지 않았는지")

print("② 배치로 바꾼 생성기는 즉시 호출 창구를 막아 둔다")
for rel in ("scripts/generate_reports_v2.py", "scripts/generate_sectors.py", "scripts/classify_sectors.py",
            "scripts/generate_reports_batch.py"):
    txt = (ROOT / rel).read_text(encoding="utf-8")
    ok(re.search(r"\.messages\.create\s*=\s*_blocked", txt) and re.search(r"\.messages\.stream\s*=\s*_blocked", txt),
       f"{rel} 가 create · stream 을 막는다")
txt = (ROOT / "scripts/marketing_report.py").read_text(encoding="utf-8")
ok("batches.create" in txt and "messages.stream" not in txt, "scripts/marketing_report.py 는 배치로 쓴다")

print("③ 업종 분류(신규 상장 작업이 평일 밤마다 돌린다)는 배치 하나로 주문하고, 늦으면 취소한다")
import json as _json
import os as _os
import tempfile as _tf
import types as _types
sys.path.insert(0, str(SCRIPTS))
import classify_sectors as C   # noqa: E402


class _FakeBatches:
    def __init__(self, never_end=False):
        self.created, self.cancelled, self.never_end, self.polls = [], False, never_end, 0

    def create(self, requests):
        self.created.append(requests)
        return _types.SimpleNamespace(id="msgbatch_cls", processing_status="in_progress")

    def retrieve(self, bid):
        self.polls += 1
        if self.cancelled:
            return _types.SimpleNamespace(id=bid, processing_status="ended")
        return _types.SimpleNamespace(id=bid, processing_status="in_progress" if self.never_end else "ended")

    def cancel(self, bid):
        self.cancelled = True

    def results(self, bid):
        out = []
        for r in self.created[-1]:
            if self.cancelled and r["custom_id"] != "c0":
                out.append(_types.SimpleNamespace(custom_id=r["custom_id"], result=_types.SimpleNamespace(type="canceled")))
                continue
            tks = re.findall(r"^- ([0-9][0-9A-Z]{5}) ", r["params"]["messages"][0]["content"], re.M)
            text = _json.dumps({tk: {"s": "반도체", "ai": False, "robot": False} for tk in tks})
            msg = _types.SimpleNamespace(content=[_types.SimpleNamespace(type="text", text=text)])
            out.append(_types.SimpleNamespace(custom_id=r["custom_id"], result=_types.SimpleNamespace(type="succeeded", message=msg)))
        return out


def _fake_client(fb):
    def _sync(*a, **k):
        raise AssertionError("즉시 호출")
    return _types.SimpleNamespace(messages=_types.SimpleNamespace(batches=fb, create=_sync, stream=_sync))


tmp = Path(_tf.mkdtemp(prefix="kosai_cls_"))
stocks = [{"ticker": f"9{i:05d}", "name": f"회사{i}", "induty_code": "26"} for i in range(85)]
(tmp / "stocks.js").write_text("window.KOS_LIVE_DATA = " + _json.dumps({"stocks": stocks}, ensure_ascii=False) + ";", encoding="utf-8")
(tmp / "sector_map.json").write_text(_json.dumps({"900000": {"s": "화학", "ai": False, "robot": False}}), encoding="utf-8")
_saved = (C.STOCKS_JS, C.CACHE, C.time.sleep, C.anthropic.Anthropic, C.WAIT, _os.environ.get("ANTHROPIC_API_KEY"))
C.STOCKS_JS, C.CACHE, C.time.sleep = tmp / "stocks.js", tmp / "sector_map.json", (lambda *_: None)
_os.environ["ANTHROPIC_API_KEY"] = "x"
try:
    fb = _FakeBatches()
    holder = {}

    def _make(api_key=None):
        holder["c"] = _fake_client(fb)
        return holder["c"]

    C.anthropic.Anthropic = _make
    import io as _io
    import contextlib as _cl
    with _cl.redirect_stdout(_io.StringIO()):
        C.main()
    cache = _json.loads((tmp / "sector_map.json").read_text(encoding="utf-8"))
    ok(len(fb.created) == 1 and len(fb.created[0]) == 3, "새 종목 84개를 40개씩 3건으로 배치 하나에 주문한다",
       f"주문 {len(fb.created)} · 건 {len(fb.created[0]) if fb.created else 0}")
    ok(len(cache) == 85 and cache["900000"]["s"] == "화학", "답으로 캐시를 채우고 있던 분류는 그대로 둔다", str(len(cache)))
    try:
        holder["c"].messages.create(model="x")
        blocked = False
    except RuntimeError:
        blocked = True
    ok(blocked, "즉시 호출 창구를 막아 둔다")
    # 시간 안에 끝나지 않으면 취소한다 — 처리 전 요청은 청구되지 않는다. 끝난 묶음의 답은 쓴다.
    fb2 = _FakeBatches(never_end=True)
    C.WAIT = 60
    with _cl.redirect_stdout(_io.StringIO()):
        got = C.classify_batch(_fake_client(fb2), [stocks[:40], stocks[40:80], stocks[80:]])
    ok(fb2.cancelled and list(got) == [0] and len(got[0]) == 40, "늦으면 취소하고, 그 사이 끝난 묶음의 답만 쓴다",
       f"취소 {fb2.cancelled} · 답 {list(got)}")
finally:
    C.STOCKS_JS, C.CACHE, C.time.sleep, C.anthropic.Anthropic, C.WAIT = _saved[:5]
    if _saved[5] is None:
        _os.environ.pop("ANTHROPIC_API_KEY", None)
    else:
        _os.environ["ANTHROPIC_API_KEY"] = _saved[5]

print()
print(f"통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
