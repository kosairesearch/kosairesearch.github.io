#!/usr/bin/env python3
"""업종 분류(scripts/classify_sectors.py)가 상장 직후 종목을 '기타'로 굳히지 않는지.

  python3 scripts/tests/classify_sectors_test.py

상장 당일에는 공시 업종코드(KSIC)가 없어 분류 모델이 이름만 보고 '기타'를 냈고, 그 답이 캐시에 굳었다 — 액스비스 ·
인벤테라(10/27), 티앤이코리아(10/29 · SOFC 발전용 에어블로워 제조사).

  ① 회사 설명 — 이미 쓴 리포트(새 형식 먼저)의 사업 · 요약 칸 첫 문장을 150자까지 꺼낸다. 없으면 빈 글.
  ② 지시문 — 업종코드가 없는 종목에만 회사 설명을 붙이고, 줄 머리 모양('- 종목코드 이름 (KSIC …)')은 그대로다.
  ③ 캐시 — 업종코드도 회사 설명도 없이 나온 '기타'는 적지 않는다. 근거가 있는 '기타'와 다른 업종은 적는다(가짜 배치).
  ④ 작업 파일 — 신규 상장 작업이 리포트를 쓴 뒤 한 번 더 분류한다.
"""
import contextlib
import io
import json
import os
import re
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import classify_sectors as C  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


tmp = Path(tempfile.mkdtemp(prefix="kosai_cls2_"))
v2dir, v1dir = tmp / "reports_v2", tmp / "reports"
v2dir.mkdir()
v1dir.mkdir()
(v1dir / "0053F0.json").write_text(json.dumps({
    "lead": {"ko": "상장 첫날 주가가 급등했다.", "en": "x"},
    "business": {"ko": "티앤이코리아는 2014년에 설립된 고속 터보기계 시스템 개발·생산 기업이며,\n본사는 충북 오송에 있다. "
                       "주력 제품은 SOFC 발전용 에어블로워다.", "en": "x"}}, ensure_ascii=False), encoding="utf-8")
(v2dir / "0011A0.json").write_text(json.dumps({"business": {"ko": "가" * 400, "en": "x"}}, ensure_ascii=False), encoding="utf-8")
(v1dir / "0011A0.json").write_text(json.dumps({"business": {"ko": "옛 형식 설명이다.", "en": "x"}}, ensure_ascii=False), encoding="utf-8")
(v1dir / "0099Z0.json").write_text(json.dumps({"desc": "요약 칸만 있는 옛 리포트다. 둘째 문장."}, ensure_ascii=False), encoding="utf-8")
_saved_dirs = C.REPORT_DIRS
C.REPORT_DIRS = (v2dir, v1dir)

print("① 회사 설명")
d = C.describe("0053F0")
ok(d == "티앤이코리아는 2014년에 설립된 고속 터보기계 시스템 개발·생산 기업이며, 본사는 충북 오송에 있다.",
   "사업 칸의 첫 문장(줄바꿈은 한 칸으로)", d)
ok(C.describe("0011A0") == "가" * 150, "새 형식이 먼저 · 150자까지")
ok(C.describe("0099Z0") == "요약 칸만 있는 옛 리포트다.", "사업 칸이 없으면 요약 칸")
ok(C.describe("999999") == "", "리포트가 없으면 빈 글")

print("② 지시문")
chunk = [{"ticker": "0053F0", "name": "티앤이코리아", "induty_code": None},
         {"ticker": "005930", "name": "삼성전자", "induty_code": "264"}]
p = C.build_prompt(chunk, {"0053F0": d, "005930": "쓰이면 안 되는 설명"})
lines = [ln for ln in p.splitlines() if ln.startswith("- 0053F0") or ln.startswith("- 005930")]
ok(lines[0] == f"- 0053F0 티앤이코리아 (KSIC -) — 회사 설명: {d}", "업종코드가 없으면 회사 설명을 붙인다", lines[0][:60])
ok(lines[1] == "- 005930 삼성전자 (KSIC 264)", "업종코드가 있으면 붙이지 않는다")
ok(re.findall(r"^- ([0-9][0-9A-Z]{5}) ", p, re.M) == ["0053F0", "005930"], "줄 머리 모양은 그대로(배치 답 대조용)")
ok(C.build_prompt(chunk) == C.build_prompt(chunk, {}), "설명 없이도 부를 수 있다(전 종목 재분류)")

print("③ 캐시 — 근거 없는 '기타'는 적지 않는다")
ANS = {"0053F0": "기계·장비", "0077A0": "기타", "000001": "기타", "0099Z0": "기타"}


class FakeBatches:
    def __init__(self):
        self.created = []

    def create(self, requests):
        self.created.append(requests)
        return types.SimpleNamespace(id="msgbatch_cls2", processing_status="ended")

    def retrieve(self, bid):
        return types.SimpleNamespace(id=bid, processing_status="ended")

    def results(self, bid):
        for r in self.created[-1]:
            tks = re.findall(r"^- ([0-9][0-9A-Z]{5}) ", r["params"]["messages"][0]["content"], re.M)
            text = json.dumps({tk: {"s": ANS[tk], "ai": False, "robot": False} for tk in tks}, ensure_ascii=False)
            msg = types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)])
            yield types.SimpleNamespace(custom_id=r["custom_id"], result=types.SimpleNamespace(type="succeeded", message=msg))


fb = FakeBatches()
stocks = [{"ticker": "0053F0", "name": "티앤이코리아", "induty_code": None},      # 업종코드 없음 · 리포트 설명 있음
          {"ticker": "0077A0", "name": "새상장", "induty_code": ""},              # 업종코드 없음 · 설명 없음 → '기타' 보류
          {"ticker": "000001", "name": "교육회사", "induty_code": "85503"},        # 업종코드 있는 '기타'는 적는다
          {"ticker": "0099Z0", "name": "옛리포트", "induty_code": None}]          # 설명이 있는 '기타'는 적는다
(tmp / "stocks.js").write_text("window.KOS_LIVE_DATA = " + json.dumps({"stocks": stocks}, ensure_ascii=False) + ";",
                               encoding="utf-8")
(tmp / "sector_map.json").write_text("{}", encoding="utf-8")
saved = (C.STOCKS_JS, C.CACHE, C.time.sleep, C.anthropic.Anthropic, os.environ.get("ANTHROPIC_API_KEY"))
C.STOCKS_JS, C.CACHE, C.time.sleep = tmp / "stocks.js", tmp / "sector_map.json", (lambda *_: None)
C.anthropic.Anthropic = lambda api_key=None: types.SimpleNamespace(
    messages=types.SimpleNamespace(batches=fb, create=None, stream=None))
os.environ["ANTHROPIC_API_KEY"] = "x"
out = io.StringIO()
try:
    with contextlib.redirect_stdout(out):
        C.main()
finally:
    C.STOCKS_JS, C.CACHE, C.time.sleep, C.anthropic.Anthropic = saved[:4]
    if saved[4] is None:
        os.environ.pop("ANTHROPIC_API_KEY", None)
    else:
        os.environ["ANTHROPIC_API_KEY"] = saved[4]
cache = json.loads((tmp / "sector_map.json").read_text(encoding="utf-8"))
sent = fb.created[0][0]["params"]["messages"][0]["content"]
ok("— 회사 설명: 티앤이코리아는 2014년에" in sent and "— 회사 설명: 요약 칸만" in sent, "요청에 회사 설명이 실린다")
ok(cache.get("0053F0", {}).get("s") == "기계·장비", "회사 설명으로 고른 업종을 적는다", str(cache.get("0053F0")))
ok("0077A0" not in cache, "업종코드 · 설명 없이 나온 '기타'는 적지 않는다(다음 실행이 다시 분류)")
ok(cache.get("000001", {}).get("s") == "기타" and cache.get("0099Z0", {}).get("s") == "기타",
   "업종코드나 설명이 있는 '기타'는 적는다")
log = out.getvalue()
ok("회사 설명을 함께 주는 종목 2개" in log and "0077A0 새상장" in log, "기록에 남긴다", log.strip().splitlines()[-1][:60])
C.REPORT_DIRS = _saved_dirs

print("④ 작업 파일")
wf = (ROOT / ".github" / "workflows" / "new_listings.yml").read_text(encoding="utf-8")
i_rep, i_cls2 = wf.find("4) 신규 종목 리포트 생성"), wf.find("4-2) 신규 종목 업종 다시 분류")
blk = wf[i_cls2:wf.find("- name:", i_cls2 + 10)] if i_cls2 > 0 else ""
ok(0 < i_rep < i_cls2 and "python scripts/classify_sectors.py" in blk and "steps.detect.outputs.has_new == '1'" in blk,
   "신규 상장 작업이 리포트를 쓴 뒤 한 번 더 분류한다")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
