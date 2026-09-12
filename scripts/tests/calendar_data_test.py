#!/usr/bin/env python3
"""브리핑 일정 수집을 검증한다 — 특히 '조용히 비는 것'을 막는지.

왜 필요한가
-----------
9월 11일 브리핑이 "앞으로 2주간 일정은 9월 16일 FOMC 하나뿐"이라고 썼다.
사실이 아니었다. 일정의 절반을 사람이 data/calendar.json 에 손으로 넣는
구조였는데 8월 27일 이후 비어 있었고, 아무도 몰랐다. 비었을 때 알려 주는
장치가 없었기 때문이다.

그래서 이 시험이 보는 것은 두 가지다.

  ① 파서가 제대로 읽는가                — 읽어야 할 것을 읽는가
  ② 못 읽었을 때 그렇다고 말하는가      ← 이쪽이 이번 사고의 본질이다

실제 사이트는 여기서 막혀 있어 부를 수 없다. 그래서 내려받기를 가짜로
바꿔 끼우고 파싱과 판정만 본다. 사이트가 실제로 그 모양인지는 Actions
에서 확인한다 — 이 시험이 대신해 주지 못하는 부분이라 적어 둔다.

  실행:  python3 scripts/tests/calendar_data_test.py
"""
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import calendar_data as C  # noqa: E402

PASS = FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}" + (f"\n      {detail}" if detail else ""))


def fake(pages):
    """주소별 응답을 정해 둔다. 목록에 없으면 실패한 것으로 친다."""
    def _get(url):
        for frag, body in pages.items():
            if frag in url:
                return body, ""
        return None, "ConnectionError: 막힘"
    return _get


# ── 가짜 BLS 표 — 실제 페이지가 쓰는 몇 가지 모양을 섞어 둔다 ──────────
def bls_html(year=2026, n=12):
    rows = []
    for m in range(1, n + 1):
        mon = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m]
        prev = ["", "December", "January", "February", "March", "April", "May",
                "June", "July", "August", "September", "October", "November"][m]
        py = year - 1 if m == 1 else year
        rows.append(
            f'<tr><td class="nr-date">{mon}. {10 + m}, {year}</td>'
            f'<td>08:30 AM</td>'
            f'<td><a href="/x">Consumer Price Index for {prev} {py}</a></td></tr>')
        # 모양이 다른 줄도 섞는다 — 열 클래스에 기대면 안 된다
        rows.append(
            f'<tr><th scope="row">{mon} {3 + m}, {year}</th>'
            f'<td>Employment Situation for {prev} {py}</td><td>08:30</td></tr>')
    # 우리가 안 쓰는 발표 — 걸러져야 한다
    rows.append('<tr><td>Mar. 02, 2026</td><td>County Employment and Wages</td></tr>')
    # 날짜가 없는 줄 — 무시돼야 한다
    rows.append('<tr><td>Consumer Price Index</td><td>TBD</td></tr>')
    return "<table>" + "".join(rows) + "</table>"


def bok_html(year=2026, months=(1, 2, 4, 5, 7, 8, 10, 11), noise=True):
    """금통위 목록 비슷한 것. 바닥글 게시일 같은 잡음을 일부러 섞는다."""
    items = [f'<li><span class="date">{year}.{m:02d}.{10 + m:02d}</span>'
             f'<a href="#">통화정책방향 결정회의</a></li>' for m in months]
    tail = (f'<footer>게시일 {year}.09.12</footer>'
            f'<li><span>{year}.06.30</span> 금융안정보고서 발간</li>'
            f'<p>{year}.03.03 보도자료 목록</p>') if noise else ""
    return "<ul>" + "".join(items) + "</ul>" + tail


print("── BLS: 읽어야 할 것을 읽는가 ──")
C._get = fake({"bls.gov": bls_html()})
rows, h = C.bls(2026)
ok("소비자물가 12건을 읽는다",
   sum(1 for r in rows if r["title"] == "미국 소비자물가") == 12, str(len(rows)))
ok("고용보고서도 읽는다",
   sum(1 for r in rows if r["title"] == "미국 고용보고서") == 12)
ok("목록에 없는 발표는 버린다",
   not any("County" in r["title"] for r in rows))
ok("건강 ok", h["ok"] and h["found"] == 24, json.dumps(h, ensure_ascii=False))
ok("발표 대상 기간을 남긴다",
   any("December 2025" in r["detail"] for r in rows),
   str([r["detail"] for r in rows[:2]]))
ok("날짜가 제대로 들어간다",
   any(r["date"] == "2026-01-11" for r in rows),
   str(sorted(r["date"] for r in rows)[:3]))

print("\n── BLS: 못 읽었을 때 그렇다고 말하는가 ──")
C._get = fake({})
rows, h = C.bls(2026)
ok("못 받으면 ok=False", rows == [] and not h["ok"])
ok("사유를 적는다", "실패" in h["note"], h["note"])
C._get = fake({"bls.gov": "<html>모양이 바뀌었다</html>"})
rows, h = C.bls(2026)
ok("빈 표면 ok=False (조용히 0건 금지)", not h["ok"], json.dumps(h, ensure_ascii=False))
C._get = fake({"bls.gov": bls_html(n=3)})
rows, h = C.bls(2026)
ok("너무 적게 읽히면 ok=False", not h["ok"], json.dumps(h, ensure_ascii=False))

print("\n── 금통위 ──")
C._get = fake({"bok.or.kr": bok_html()})
rows, h = C.bok(2026)
ok("연 8회를 정확히 읽는다", len(rows) == 8, f"{len(rows)}건 {[r['date'] for r in rows]}")
ok("기준금리 결정으로 적는다",
   bool(rows) and all(r["detail"] == "기준금리 결정" for r in rows))
ok("건강 ok", h["ok"] and h["found"] == 8, json.dumps(h, ensure_ascii=False))
# ← 이 시험이 실제 결함을 잡았다. 예전 파서는 바닥글 '게시일 2026.09.12'
#   까지 회의로 주워 9건을 만들었다. 없는 금통위가 브리핑에 실렸을 것이다.
ok("바닥글 게시일을 회의로 세지 않는다",
   "2026-09-12" not in [r["date"] for r in rows], str([r["date"] for r in rows]))
ok("금융안정보고서·보도자료 날짜도 세지 않는다",
   not ({"2026-06-30", "2026-03-03"} & {r["date"] for r in rows}),
   str([r["date"] for r in rows]))
# 잡음이 없는 페이지에서도 같은 8건이 나와야 한다
C._get = fake({"bok.or.kr": bok_html(noise=False)})
rows2, _ = C.bok(2026)
ok("잡음이 있든 없든 같은 결과", [r["date"] for r in rows] == [r["date"] for r in rows2])
C._get = fake({"bok.or.kr": "<html>" + "".join(
    f"<p>통화정책방향 2026.{m:02d}.{d:02d}</p>"
    for m in range(1, 13) for d in (1, 5, 9)) + "</html>"})
rows, h = C.bok(2026)
ok("날짜가 쏟아지면 ok=False (쓰레기 내보내지 않기)", not h["ok"],
   f"{len(rows)}건 {h['note']}")
C._get = fake({"bok.or.kr": "<html><p>2026.01.15</p><p>2026.02.13</p>"
                            "<p>2026.04.09</p><p>2026.05.28</p>"
                            "<p>2026.07.09</p><p>2026.08.27</p>"
                            "<p>2026.10.15</p><p>2026.11.26</p></html>"})
rows, h = C.bok(2026)
ok("회의라는 표시가 없으면 날짜만으로는 안 쓴다", not h["ok"],
   f"{len(rows)}건 {h['note']}")
C._get = fake({})
rows, h = C.bok(2026)
ok("다 막히면 ok=False", rows == [] and not h["ok"])

print("\n── 수동 등록이 말라붙는 것 ──")
rows, h = C.manual()
ok("지금 저장소의 calendar.json 은 말라 있다 (이번 사고)",
   not h["ok"] and "말라붙은" in h["note"], h["note"])

print("\n── 조립: 비었을 때 소리를 지르는가 ──")
C._get = fake({})
C.MANUAL = HERE / "_없는파일.json"
d = C.collect(14)
ok("전부 실패하면 health.ok=False", not d["health"]["ok"])
ok("얇다고 표시한다", d["health"]["thin"])
ok("문제를 하나하나 적는다", len(d["health"]["problems"]) >= 3,
   json.dumps(d["health"]["problems"], ensure_ascii=False))
ok("sources 에 갈래별 상태가 다 있다", len(d["sources"]) >= 4)

print("\n── 조립: 멀쩡할 때는 조용한가 ──")
today = datetime.datetime.now(C.KST).date()
soon = [(today + datetime.timedelta(days=k)) for k in (1, 3, 5, 8)]
C._get = fake({
    "bls.gov": "<table>" + "".join(
        f'<tr><td>{d.strftime("%b")}. {d.day}, {d.year}</td>'
        f'<td>Consumer Price Index for x</td></tr>' for d in soon) + "</table>",
})
# BLS 는 12건 문턱이 있으므로 연간분을 같이 넣어 통과시킨다
C._get = fake({"bls.gov": bls_html() + "<table>" + "".join(
    f'<tr><td>{d.strftime("%b")}. {d.day}, {d.year}</td>'
    f'<td>Producer Price Index for x</td></tr>' for d in soon) + "</table>"})
d = C.collect(14)
near = [e for e in d["events"]]
ok("앞으로 14일에 3건 이상이면 thin 아님", not d["health"]["thin"],
   f"{len(near)}건")

print("\n── summarize 가 상태를 보여 주는가 ──")
txt = C.summarize(d)
ok("갈래별 상태를 찍는다", "갈래별 상태" in txt)
C._get = fake({})
bad = C.summarize(C.collect(14))
ok("문제가 있으면 눈에 띄게 찍는다", "손봐야 할 것" in bad)

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
