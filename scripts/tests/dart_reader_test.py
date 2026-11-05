#!/usr/bin/env python3
"""영문이 섞인 종목코드의 공시 조회 — 네트워크 없이 가짜 회사 목록으로 돌린다.

  python3 scripts/tests/dart_reader_test.py

무엇을 못 박아 두나 (2026-10-27)
  공시 라이브러리(OpenDartReader)는 숫자 6자리만 종목코드로 보고, 그 밖은 회사 이름으로 찾는다. 한국거래소가
  새 상장 종목에 매기는 영문이 섞인 코드('0011A0')는 그래서 늘 '찾을 수 없음'이었고, 리포트 생성기는 그것을
  '재무 자료 없음'으로 읽어 '생성 불가'로 빼 왔다 — 상장 36개 종목(액스비스 · 삼성에피스홀딩스 …)이 6월 옛
  형식 리포트에 넉 달 가까이 머물렀다.

  ① 진짜 라이브러리의 찾기가 영문 섞인 코드를 못 찾는다(고친 판이 하는 일을 보이려고 · 라이브러리가 고쳐지면 알린다).
  ② dart_reader 로 바꾼 객체는 영문 섞인 코드를 종목코드 칸에서 찾고, 숫자 코드 · 회사 이름 · 고유번호는 원래대로.
  ③ 라이브러리의 다른 조회(재무제표 등)가 바꾼 찾기를 그대로 쓴다.
  ④ OpenDartReader( 를 직접 부르는 스크립트가 없다 — 모두 dart_reader.reader() 로 만든다.
  ⑤ 리포트 생성기는 회사 번호를 못 찾은 종목을 '재무 자료 없음'이 아니라 그 종목의 실패로 센다.
  ⑥ 잘못 남은 생성 불가 기록 — 영문 섞인 상장 종목에 고치기 전 날짜의 기록이 없다.
"""
import os
import re
import sys
import types
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent))

if "dotenv" not in sys.modules:
    _d = types.ModuleType("dotenv")
    _d.load_dotenv = lambda *a, **k: None
    sys.modules["dotenv"] = _d

import dart_reader as D  # noqa: E402

PASS = FAIL = 0


def ok(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {label}")
    else:
        FAIL += 1
        print(f"  ✘ {label}" + (f"  — {extra}" if extra else ""))


CODES = pd.DataFrame([
    {"corp_code": "01910000", "corp_name": "액스비스", "stock_code": "0011A0"},
    {"corp_code": "01920000", "corp_name": "삼성에피스홀딩스", "stock_code": "0126Z0"},
    {"corp_code": "00126380", "corp_name": "삼성전자", "stock_code": "005930"},
    {"corp_code": "00999999", "corp_name": "비상장회사", "stock_code": " "},
])

print("① 진짜 라이브러리의 찾기")
try:
    import OpenDartReader as ODR          # 패키지가 sys.modules 를 클래스로 바꿔 둔다
    real = ODR.__new__(ODR)               # 생성자는 회사 목록을 내려받으므로 거치지 않는다
    real.corp_codes = CODES.copy()
    ok(real.find_corp_code("005930") == "00126380", "숫자 6자리는 찾는다")
    lib_finds = real.find_corp_code("0011A0")
    ok(lib_finds is None, "★ 영문이 섞인 '0011A0' 은 못 찾는다 — 이 파일이 고치는 일",
       f"{lib_finds} — 라이브러리가 고쳐졌으면 dart_reader 를 걷어 내도 된다")
    D.patch(real)
    ok(real.find_corp_code("0011A0") == "01910000", "★ 바꾼 뒤에는 진짜 라이브러리 객체도 찾는다")
except ImportError:
    print("  (OpenDartReader 가 없는 환경 — ① 은 건너뛴다)")


class Fake:
    """라이브러리와 같은 꼴: 조회 함수가 self.find_corp_code 를 거친다."""
    def __init__(self):
        self.corp_codes = CODES.copy()
        self.asked = []

    def find_corp_code(self, corp):           # OpenDartReader 0.2.2 의 판정 그대로
        if not corp.isdigit():
            df = self.corp_codes[self.corp_codes["corp_name"] == corp]
        elif corp.isdigit() and len(corp) == 6:
            df = self.corp_codes[self.corp_codes["stock_code"] == corp]
        else:
            df = self.corp_codes[self.corp_codes["corp_code"] == corp]
        return None if df.empty else df.iloc[0]["corp_code"]

    def finstate_all(self, corp, bsns_year, reprt_code="11011", fs_div="CFS"):
        code = self.find_corp_code(corp)
        if not code:
            raise ValueError(f'could not find "{corp}"')
        self.asked.append(code)
        return code


print("② 바꾼 찾기 — 영문 섞인 코드는 종목코드 칸, 나머지는 원래대로")
f = Fake()
ok(f.find_corp_code("0011A0") is None, "바꾸기 전 가짜도 못 찾는다(라이브러리와 같은 판정)")
D.patch(f)
ok(f.find_corp_code("0011A0") == "01910000", "★ '0011A0' → 액스비스")
ok(f.find_corp_code("0126Z0") == "01920000", "'0126Z0' → 삼성에피스홀딩스")
ok(f.find_corp_code("005930") == "00126380", "숫자 6자리는 원래대로")
ok(f.find_corp_code("삼성전자") == "00126380", "회사 이름은 원래대로")
ok(f.find_corp_code("00126380") == "00126380", "고유번호(8자리)는 원래대로")
ok(f.find_corp_code("0099Z9") is None, "목록에 없는 영문 섞인 코드는 None")
ok(f.find_corp_code(" 0011A0 ") == "01910000", "앞뒤 공백은 지운다")
again = f.find_corp_code
D.patch(f)
ok(f.find_corp_code is again, "두 번 불러도 한 번만 바꾼다")
bare = types.SimpleNamespace(list=lambda **k: [])
ok(D.patch(bare) is bare and not hasattr(bare, "_kos_alnum"), "회사 목록이 없는 객체는 그대로 둔다(시험의 가짜)")

print("③ 다른 조회가 바꾼 찾기를 쓴다")
ok(f.finstate_all("0011A0", 2025) == "01910000" and f.asked == ["01910000"], "★ 재무제표 조회가 '0011A0' 으로 된다")

print("④ OpenDartReader( 를 직접 부르는 스크립트가 없다")
direct = []
for p in sorted((ROOT / "scripts").glob("*.py")):
    if p.name == "dart_reader.py":
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        code = line.split("#", 1)[0]
        if re.search(r"\bOpenDartReader\s*\(", code):
            direct.append(f"{p.name}:{i}")
ok(not direct, "공시 객체는 모두 dart_reader.reader() 로 만든다", ", ".join(direct))
src = {n: (ROOT / "scripts" / n).read_text(encoding="utf-8")
       for n in ("generate_reports.py", "collect_data.py", "check_filings.py")}
ok(all("dart_reader.reader(" in s for s in src.values()), "리포트 생성기 · 시세 수집 · 공시 트리거가 reader() 를 쓴다")

print("⑤ 리포트 생성기 — 회사 번호를 못 찾으면 '재무 자료 없음'이 아니라 실패")
import generate_reports_v2 as M                     # noqa: E402
import _reports_state as S                           # noqa: E402
import tempfile                                      # noqa: E402
called = []
saved = (M.collect_quant, M.cross_check, M.krx_fundamentals, M.g.get_dart, S.FAIL_DIR)
with tempfile.TemporaryDirectory() as td:
    try:
        S.FAIL_DIR = Path(td) / "fail"
        S.FAIL_DIR.mkdir()
        Q = {"annual": [{"year": 2025, "rev": 1, "op": 1, "np_owner": 1, "opm": 1.0, "roe": 1.0, "debt_ratio": 1.0}],
             "quarterly": [], "valuation": {}}
        M.collect_quant = lambda dart, tk, row, st: (called.append(tk), Q)[1]
        M.cross_check = lambda *a, **k: None
        M.krx_fundamentals = lambda d: None
        lost = Fake()                                 # 바꾸지 않은 객체 — 고치기 전과 같다
        M.g.get_dart = lambda: lost
        tg = [{"ticker": "0011A0", "name": "액스비스", "price": 1, "mcap": 0.07, "shares": 1},
              {"ticker": "005930", "name": "삼성전자", "price": 1, "mcap": 500.0, "shares": 1}]
        out, errors, un = M.collect_all_quant(tg, {"dataDate": "20261027"})
        ok("0011A0" in errors and "0011A0" not in out, "★ 못 찾은 종목은 errors(실패) — skip 으로 가는 빈 정량을 만들지 않는다",
           f"errors={errors} out={list(out)}")
        ok(called == ["005930"], "못 찾은 종목은 재무제표 조회를 하지 않는다", str(called))
        ok((S.FAIL_DIR / "0011A0").exists(), "실패 횟수를 센다(세 번이면 2주 쉬었다가 다시 본다)")
        called.clear()
        M.g.get_dart = lambda: D.patch(Fake())       # 고친 객체
        out, errors, un = M.collect_all_quant(tg, {"dataDate": "20261027"})
        ok(not errors and set(out) == {"0011A0", "005930"}, "★ 고친 객체면 두 종목 모두 정량을 모은다", f"{errors} {list(out)}")
    finally:
        M.collect_quant, M.cross_check, M.krx_fundamentals, M.g.get_dart, S.FAIL_DIR = saved

print("⑥ 영문 섞인 상장 종목에 고치기 전의 생성 불가 기록이 남아 있지 않다")
# 고친 날(2026-10-27) 뒤의 기록은 고친 조회로 회사를 찾고도 연간 재무가 없던 종목이다 — 상장 직후라 사업보고서가
# 아직 없다(그날 15개). 그 기록은 30일 뒤 다시 본다. 고치기 전 날짜의 기록만 '못 찾아서 빠진' 잘못된 기록이다.
FIXED = __import__("datetime").date(2026, 10, 27)
raw = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
stocks = __import__("json").loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]
alnum = sorted(s["ticker"] for s in stocks if not s["ticker"].isdigit())
marked = [t for t in alnum if (S.SKIP_DIR / t).exists()]
left = [t for t in marked if not (S.skip_date(t) and S.skip_date(t) >= FIXED)]
ok(alnum and not left, f"영문 섞인 상장 종목 {len(alnum)}개 — 고치기 전 날짜의 생성 불가 기록 0"
   f" (고친 뒤 기록 {len(marked) - len(left)}개는 연간 재무가 아직 없는 종목)", ", ".join(left[:10]))

print()
print(f"통과 {PASS} · 실패 {FAIL}")
sys.exit(1 if FAIL else 0)
