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
import os
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
    def _get(url, headers=None):
        for frag, body in pages.items():
            if frag in url:
                return body, ""
        return None, "ConnectionError: 막힘"
    return _get


# ── 가짜 FRED 응답 ───────────────────────────────────────────────
# bls.gov 는 통째로 403 이라(러너 IP 차단) FRED API 로 갈아탔다.
def fred_json(n=12, year=2026):
    rows = []
    for m in range(1, n + 1):
        rows.append({"release_id": 10, "release_name": "Consumer Price Index",
                     "date": f"{year}-{m:02d}-{10 + m:02d}"})
        rows.append({"release_id": 50, "release_name": "Employment Situation",
                     "date": f"{year}-{m:02d}-{3 + m:02d}"})
    # 우리가 안 쓰는 발표 — 걸러져야 한다
    rows.append({"release_id": 99, "release_name": "County Employment and Wages",
                 "date": f"{year}-03-02"})
    return json.dumps({"release_dates": rows})


print("── 미국 지표(FRED): 열쇠가 있을 때 ──")
os.environ["FRED_API_KEY"] = "시험용"
C._get = fake({"stlouisfed.org": fred_json()})
rows, h = C.fred(2026)
ok("소비자물가 12건을 읽는다",
   sum(1 for r in rows if r["title"] == "미국 소비자물가") == 12, str(len(rows)))
ok("고용보고서도 읽는다",
   sum(1 for r in rows if r["title"] == "미국 고용보고서") == 12)
ok("목록에 없는 발표는 버린다", not any("County" in r["title"] for r in rows))
ok("건강 ok", h["ok"] and h["found"] == 24, json.dumps(h, ensure_ascii=False))
ok("날짜가 제대로 들어간다", any(r["date"] == "2026-01-11" for r in rows),
   str(sorted(r["date"] for r in rows)[:3]))
ok("원래 발표 이름을 남긴다", any("Consumer Price Index" in r["detail"] for r in rows))

print("\n── 미국 지표: 지난 발표만 오면 경보 ──")
# 실제로 당했다. '11건 읽음'인데 앞으로 60일에 하나도 없었다. 최신순이
# 기본이라 지난 발표만 1,000건 받아 온 것이다. 읽은 건수만 세면 모른다.
_past = (datetime.datetime.now(C.KST).date() - datetime.timedelta(days=30)).isoformat()
os.environ["FRED_API_KEY"] = "시험용"
C._get = fake({"stlouisfed.org": json.dumps({"release_dates": [
    {"release_name": "Consumer Price Index", "date": _past}]})})
rows, h = C.fred(2026)
ok("지난 것만 오면 ok=False", not h["ok"], json.dumps(h, ensure_ascii=False))
ok("왜 그런지 적는다", "지난 발표만" in h["note"], h["note"])
_soon = (datetime.datetime.now(C.KST).date() + datetime.timedelta(days=5)).isoformat()
C._get = fake({"stlouisfed.org": json.dumps({"release_dates": [
    {"release_name": "Consumer Price Index", "date": _past},
    {"release_name": "Consumer Price Index", "date": _soon}]})})
rows, h = C.fred(2026)
ok("앞으로 것이 하나라도 있으면 ok", h["ok"] and "앞으로 1건" in h["note"], h["note"])
# 주소를 실제로 들여다본다. 상수만 보면 조립 단계에서 빠져도 모른다.
_asked = {}


def _spy(url, headers=None):
    _asked["url"] = url
    return json.dumps({"release_dates": []}), ""


C._get = _spy
C.fred(2026)
ok("주소에 sort_order=asc 가 들어간다", "sort_order=asc" in _asked.get("url", ""),
   _asked.get("url", "")[:120])
ok("예정일 포함을 요청한다",
   "include_release_dates_with_no_data=true" in _asked.get("url", ""))
os.environ.pop("FRED_API_KEY", None)

print("\n── 미국 지표: 열쇠가 없을 때는 경보가 아니다 ──")
# 설정이 안 된 것은 고장이 아니다. 매일 울리는 경보는 곧 아무도 안 본다.
os.environ.pop("FRED_API_KEY", None)
rows, h = C.fred(2026)
ok("건너뛰지만 ok=True", rows == [] and h["ok"], json.dumps(h, ensure_ascii=False))
ok("어떻게 켜는지 알려 준다", "fredaccount" in h["note"], h["note"])

print("\n── 미국 지표: 열쇠가 있는데 실패하면 경보 ──")
os.environ["FRED_API_KEY"] = "시험용"
C._get = fake({})
rows, h = C.fred(2026)
ok("못 받으면 ok=False", not h["ok"], json.dumps(h, ensure_ascii=False))
C._get = fake({"stlouisfed.org": "{ 망가진 JSON"})
rows, h = C.fred(2026)
ok("응답이 깨졌으면 ok=False", not h["ok"], h["note"])
C._get = fake({"stlouisfed.org": json.dumps({"release_dates": [
    {"release_name": "County Employment and Wages", "date": "2026-03-02"}]})})
rows, h = C.fred(2026)
ok("쓸 발표가 하나도 없으면 ok=False", not h["ok"], h["note"])
os.environ.pop("FRED_API_KEY", None)

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
ok("문제를 하나하나 적는다", len(d["health"]["problems"]) >= 2,
   json.dumps(d["health"]["problems"], ensure_ascii=False))
ok("sources 에 갈래별 상태가 다 있다", len(d["sources"]) >= 3,
   str([x["name"] for x in d["sources"]]))
ok("어느 갈래가 죽었는지 이름으로 말한다",
   any("FOMC" in x for x in d["health"]["problems"]),
   json.dumps(d["health"]["problems"], ensure_ascii=False))

print("\n── 조립: 멀쩡할 때는 조용한가 (경보가 무뎌지면 안 된다) ──")
today = datetime.datetime.now(C.KST).date()
soon = [today + datetime.timedelta(days=k) for k in (1, 3, 5, 8)]
os.environ["FRED_API_KEY"] = "시험용"
C._get = fake({"stlouisfed.org": json.dumps({"release_dates": [
    {"release_name": "Consumer Price Index", "date": d.isoformat()} for d in soon]})})
C.MANUAL = HERE / "_없는파일.json"
d = C.collect(14)
ok("앞으로 14일에 3건 이상이면 thin 아님", not d["health"]["thin"],
   f"{len(d['events'])}건")
ok("FOMC 가 죽어도 그 사실은 남는다",
   any("FOMC" in x for x in d["health"]["problems"]),
   json.dumps(d["health"]["problems"], ensure_ascii=False))
os.environ.pop("FRED_API_KEY", None)

print("\n── summarize 가 상태를 보여 주는가 ──")
txt = C.summarize(d)
ok("갈래별 상태를 찍는다", "갈래별 상태" in txt)
C._get = fake({})
bad = C.summarize(C.collect(14))
ok("문제가 있으면 눈에 띄게 찍는다", "손봐야 할 것" in bad)

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
