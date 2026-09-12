#!/usr/bin/env python3
"""브리핑 뉴스 수집을 검증한다 — 특히 '조용히 비는 것'을 막는지.

왜 필요한가
-----------
일정에서 한 번 당했다. 9월 11일 브리핑이 "앞으로 2주 일정은 FOMC 하나뿐"
이라고 썼는데, 정말 하나뿐인 게 아니라 수집이 말라 있었다. 실패해도 빈
목록만 돌려주니 받는 쪽이 '못 가져온 것'과 '없는 것'을 구분할 수 없었다.

뉴스도 같은 구조였다. rss() 는 무엇이 터져도 [] 를 돌려준다. 그 자체는
맞다 — 기사 하나 때문에 브리핑을 멈출 이유는 없다. 하지만 몇 갈래가
비었는지 아무도 세지 않으면 똑같은 일이 벌어진다.

경보는 두 단이다.
  · 핵심 갈래(시황·미국 지수)는 하나만 비어도 문제. 장이 열린 다음 날
    이게 빌 수는 없다.
  · 그 밖에는 전체의 3분의 1이 한꺼번에 비면 문제.
한 갈래가 조용한 날까지 매번 문제라고 하면 경보가 무뎌지고, 무뎌진 경보는
없는 것과 같다. 그 균형을 여기서 못박는다.

  실행:  python3 scripts/tests/news_data_test.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import news_data as N  # noqa: E402

PASS = FAIL = 0
ART = [{"title": "기사 제목", "source": "매체", "published": None, "link": ""}]
CORE_Q = ("코스피 마감 외국인 순매수", "stock market close S&P 500 Nasdaq")


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}" + (f"\n      {detail}" if detail else ""))


def run(rss_impl):
    N.rss, N.naver = rss_impl, (lambda *a, **k: [])
    return N.collect()


print("── 갈래가 실제로 늘었는가 ──")
labels = [l for l, _ in N.QUERIES_KO] + [l for l, _ in N.QUERIES_EN]
ok("한국 거시가 들어왔다",
   all(any(k in l for l in labels) for k in ("금리", "물가", "수출입")), str(labels))
ok("원자재도 본다", any("원자재" in l for l in labels))
ok("핵심 갈래 이름이 실제 갈래와 맞는다",
   all(c in labels for c in N.CORE_GROUPS), f"{N.CORE_GROUPS} vs {labels}")

print("\n── 비었을 때 소리를 지르는가 ──")
h = run(lambda *a, **k: [])["health"]
ok("전부 막히면 경보", not h["ok"])
ok("핵심이 비었다고 짚는다", any("핵심 갈래" in p for p in h["problems"]),
   str(h["problems"]))

h = run(lambda q, *a, **k: [] if q in CORE_Q else ART)["health"]
ok("핵심 둘만 비어도 경보", not h["ok"], str(h["problems"]))
ok("핵심이 원인이라고 짚는다", any("핵심 갈래" in p for p in h["problems"]))

_n = [0]


def _half(q, *a, **k):
    _n[0] += 1
    return ART if _n[0] % 2 else []


_n[0] = 0
h = run(_half)["health"]
ok("절반이 비면 경보", not h["ok"], str(h["problems"]))

print("\n── 멀쩡할 때 조용한가 (경보가 무뎌지면 안 된다) ──")
h = run(lambda *a, **k: ART)["health"]
ok("다 오면 조용", h["ok"], str(h["problems"]))
ok("갈래별 건수를 남긴다", len(h["counts"]) == len(labels), str(h["counts"]))

# 상수가 진짜로 문턱을 움직이는가. 값만 써 두고 코드는 숫자를 박아 넣는
# 일이 실제로 한 번 있었다 — 그러면 나중에 값을 조정해도 아무 일도 안 난다.
import math as _math  # noqa: E402

_ALL = N.QUERIES_KO + N.QUERIES_EN
_NONCORE = [q for l, q in _ALL if l not in N.CORE_GROUPS]


def _empty_k(k):
    dead = set(_NONCORE[:k])
    return lambda q, *a, **kw: ([] if q in dead else ART)


_keep = N.EMPTY_ALARM
try:
    for _alarm in (1 / 3, 0.9):
        N.EMPTY_ALARM = _alarm
        _floor = max(2, _math.ceil(len(_ALL) * _alarm))
        if _floor - 1 <= len(_NONCORE):
            N.rss = _empty_k(_floor - 1)
            ok(f"상수 {_alarm:.2f}: 문턱({_floor})보다 하나 적으면 조용",
               N.collect()["health"]["ok"])
        if _floor <= len(_NONCORE):
            N.rss = _empty_k(_floor)
            ok(f"상수 {_alarm:.2f}: 문턱({_floor})에 닿으면 경보",
               not N.collect()["health"]["ok"])
finally:
    N.EMPTY_ALARM = _keep

one_quiet = "한국은행 기준금리 금통위"
h = run(lambda q, *a, **k: [] if q == one_quiet else ART)["health"]
ok("한 갈래만 조용한 날은 문제 아님", h["ok"], str(h["problems"]))

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
