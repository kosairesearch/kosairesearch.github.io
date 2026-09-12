#!/usr/bin/env python3
"""금통위 일정 읽기를 검증한다 — 없는 회의를 만들지 않는지.

왜 이렇게까지 하나
------------------
이 값은 브리핑에 "다음 금통위는 10월 22일" 처럼 그대로 실린다. 틀린
날짜가 실리는 것은 빠지는 것보다 나쁘다. 실제로 두 번 당할 뻔했다.

  ① 초안 파서가 바닥글의 '게시일 2026.09.12' 를 회의로 셌다(8건→9건).
  ② 2027년을 눌렀더니 화면은 2026년 목록을 줬는데 인자를 믿고 연도를
     붙여 2027-10-22, 2027-11-26 이라는 없는 회의가 나왔다.

②는 요일 검산이 막았다. 화면에 '10월 22일(목)'이라고 적혀 있는데
2027년으로 계산하면 금요일이라 어긋난다.

아래 화면 글자는 Actions 에서 실제로 받아 온 것을 그대로 옮긴 것이다.
네트워크 없이 판정만 시험한다.

  실행:  python3 scripts/tests/bok_schedule_test.py
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import bok_schedule as B  # noqa: E402

PASS = FAIL = 0

# 2026-09-12 에 한국은행 페이지에서 실제로 받은 화면. 앞 6개는 자료가
# 붙어 있어 줄에 연도가 있고, 뒤 2개는 앞으로의 회의라 연도가 없다.
REAL = """01월 15일(목)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.01)
02월 26일(목)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.02)
04월 10일(금)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.04)
05월 28일(목)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.05)
07월 16일(목)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.07)
08월 27일(목)
 첨부파일 있습니다 통화정책방향 관련 총재 기자간담회 (2026.08)
10월 22일(목)
11월 26일(목)
 주 : 1) 금융·경제 이슈는 통화정책방향 결정회의 D+7일, 의사록은 …
게시일 2026.09.12
유용한 정보가 되었나요?""".split("\n")

WANT = ["2026-01-15", "2026-02-26", "2026-04-10", "2026-05-28",
        "2026-07-16", "2026-08-27", "2026-10-22", "2026-11-26"]


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}" + (f"\n      {detail}" if detail else ""))


def parse(lines, year):
    """rows_from_page 의 판정 부분만 떼어 돌린다(브라우저 없이)."""
    B._LINES_FOR_TEST = lines
    return B.parse_lines(lines, year)


print("── 실제 화면에서 연 8회를 읽는가 ──")
rows, ly = parse(REAL, 2026)
got = [r["date"] for r in rows]
ok("8건", len(rows) == 8, f"{len(rows)}건 {got}")
ok("날짜가 정확하다", got == WANT, str(got))
ok("목록 연도를 2026으로 본다", ly == 2026, str(ly))

print("\n── 인자에 흔들리지 않는가 ──")
rows2, ly2 = parse(REAL, 2027)
ok("2027년을 요청해도 화면대로 2026년 8건",
   [r["date"] for r in rows2] == WANT and ly2 == 2026,
   f"{ly2}년 {[r['date'] for r in rows2]}")

print("\n── 없는 회의를 만들지 않는가 ──")
ok("바닥글 '게시일 2026.09.12' 를 회의로 세지 않는다",
   "2026-09-12" not in got, str(got))
bad = [ln.replace("(목)", "(월)") if ln.startswith("10월") else ln for ln in REAL]
rows3, _ = parse(bad, 2026)
ok("요일이 어긋나면 그 줄을 버린다",
   "2026-10-22" not in [r["date"] for r in rows3],
   str([r["date"] for r in rows3]))
rows4, _ = parse(["02월 30일(목)", " 통화정책방향 (2026.02)"], 2026)
ok("있을 수 없는 날짜(2월 30일)는 버린다", rows4 == [], str(rows4))

print("\n── 연도가 섞여 있을 때 ──")
# 2025-10-22 는 수요일이다. 화면에 (수)라고 적혀 있어야 그 줄을 믿는다.
mixed = REAL[:6] + ["10월 22일(수)", " 통화정책방향 관련 총재 기자간담회 (2025.10)"]
rows5, ly5 = parse(mixed, 2026)
ok("줄에 적힌 연도가 있으면 그 줄은 그걸 쓴다",
   "2025-10-22" in [r["date"] for r in rows5],
   str([r["date"] for r in rows5]))
ok("나머지는 다수결 연도(2026)를 쓴다", ly5 == 2026, str(ly5))
# 같은 줄을 (목)으로 적어 두면 — 2025년엔 수요일이므로 — 버려야 한다
mixed_bad = REAL[:6] + ["10월 22일(목)", " 통화정책방향 관련 총재 기자간담회 (2025.10)"]
rows5b, _ = parse(mixed_bad, 2026)
ok("줄의 연도와 요일이 안 맞으면 그 줄을 버린다",
   "2025-10-22" not in [r["date"] for r in rows5b],
   str([r["date"] for r in rows5b]))

print("\n── 아무것도 없을 때 ──")
rows6, _ = parse(["관련 자료가 없습니다", "유용한 정보가 되었나요?"], 2026)
ok("빈 화면이면 빈 목록", rows6 == [], str(rows6))

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
