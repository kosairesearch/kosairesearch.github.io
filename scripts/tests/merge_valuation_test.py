#!/usr/bin/env python3
"""valuation.js 합치기를 검증한다 — 합쳐야 할 것과, 손대면 안 될 때.

이 스크립트는 rebase 충돌이라는 드문 상황에서만 돈다. 드물게 도는 코드가
틀려 있으면 정작 필요한 순간에 터진다. 그래서 두 방향을 다 본다.

  ① 제대로 합치는가      — 양쪽 종목이 다 남고, 이번 수집이 이기는가
  ② 이상하면 멈추는가    — 못 읽는 입력에 쓰레기를 쓰지 않고 물러나는가

②가 더 중요하다. 이 스크립트가 실패하면 워크플로는 예전처럼 물러나
재시도한다. 즉 '아무것도 안 함'은 안전하지만 '잘못 씀'은 위험하다.

  실행:  python3 scripts/tests/merge_valuation_test.py
"""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import merge_valuation as M  # noqa: E402

PASS = FAIL = 0


def eq(name, got, want):
    global PASS, FAIL
    if got == want:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}\n      받음: {got!r}\n      기대: {want!r}")


def js(stocks, asof="2026-09-12 10:00", dd="20260911"):
    return M.render({"asOf": asof, "dataDate": dd, "count": len(stocks), "stocks": stocks})


print("── 제대로 합치는가 ──")
onto = {"005930": {"bps": 85688}, "000660": {"bps": 100}}          # 기준(origin/main)
ours = {"008040": {"bps": 7940}, "000660": {"bps": 999}}           # 이번 실행
o, u = M.parse(js(onto)), M.parse(js(ours, asof="2026-09-12 12:00"))
m = M.merge(o, u)
eq("양쪽 종목이 다 남는다", sorted(m["stocks"]), ["000660", "005930", "008040"])
eq("겹치는 종목은 이번 수집이 이긴다", m["stocks"]["000660"]["bps"], 999)
eq("상대만 가진 종목은 그대로", m["stocks"]["005930"]["bps"], 85688)
eq("이번에 새로 넣은 종목", m["stocks"]["008040"]["bps"], 7940)
eq("count 를 다시 센다", m["count"], 3)
eq("asOf 는 늦은 쪽", m["asOf"], "2026-09-12 12:00")

print("\n── 되읽을 수 있는가 ──")
again = M.parse(M.render(m))
eq("써 놓은 것을 다시 읽어도 같다", again["stocks"], m["stocks"])
eq("머리말이 붙는다", M.render(m).startswith("// KOS ai"), True)
eq("꼬리가 맞는다", M.render(m).endswith("};\n"), True)

print("\n── 이상하면 멈추는가 (더 중요) ──")
eq("빈 입력", M.parse(""), None)
eq("JSON 이 깨진 입력", M.parse("window.KOS_VALUATION = {깨짐;"), None)
eq("stocks 가 없는 입력", M.parse('window.KOS_VALUATION = {"asOf":"x"};'), None)
eq("stocks 가 사전이 아닌 입력", M.parse('window.KOS_VALUATION = {"stocks":[1,2]};'), None)
eq("충돌 표식이 그대로 든 입력", M.parse("<<<<<<< HEAD\nwindow.KOS_VALUATION = {오류"), None)

with tempfile.TemporaryDirectory() as d:
    a, b = Path(d) / "a.js", Path(d) / "b.js"
    a.write_text(js({"005930": {"bps": 1}}), encoding="utf-8")
    b.write_text("망가진 파일", encoding="utf-8")
    eq("한쪽이 못 읽는 파일이면 1 을 돌려준다", M.main([str(a), str(b)]), 1)
    eq("인자가 하나면 1 을 돌려준다", M.main([str(a)]), 1)

print("\n── 실제 파일 한 번 ──")
real = Path(M.ROOT) / "data" / "valuation.js"
if real.exists():
    p = M.parse(real.read_text(encoding="utf-8"))
    eq("지금 쓰는 valuation.js 를 읽을 수 있다", p is not None, True)
    if p:
        eq("종목이 2,000개 넘는다", len(p["stocks"]) > 2000, True)
        # 자기 자신과 합치면 종목 수가 그대로여야 한다
        eq("자기 자신과 합쳐도 종목 수가 같다",
           len(M.merge(p, p)["stocks"]), len(p["stocks"]))
else:
    print("  (data/valuation.js 없음 — 건너뜀)")

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
