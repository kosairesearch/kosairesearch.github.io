#!/usr/bin/env python3
"""이번 주에 뭐가 있나 — 브리핑 '볼 것' 섹션의 일정.

세 갈래에서 모은다.

  1. FOMC        연준 사이트에서 파싱. 회의 날짜와 의사록 공개일까지 나온다.
                 판정 3차에서 의사록 링크가 'minutes20260429' 형태로 박혀
                 있는 걸 확인했다 — 추측하지 않고 확정 날짜를 쓸 수 있다.
  2. 수동 등록    data/calendar.json. 잭슨홀, 엔비디아 실적, 미국 CPI 처럼
                 무료로 깔끔히 긁을 데가 없는 것들. 한 달에 열 줄이면 된다.
                 유료 캘린더 API 를 붙이는 건 브리핑이 돈을 벌고 나서 해도
                 늦지 않다.
  3. 국내 공시    리포트 확인 지점과 DART 는 brief_data.py 가 이미 본다.
                 여기서는 중복해서 받지 않는다.

    python3 scripts/calendar_data.py                 # 앞으로 14일
    python3 scripts/calendar_data.py --days 30 --json
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "calendar.json"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0)"}
TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ────────────────────────────── FOMC ──────────────────────────────

def fomc(year=None):
    """연준 페이지에서 회의 일정과 의사록 공개일.

    의사록은 회의 3주 뒤에 공개된다. 그런데 '3주 뒤'로 계산하면 며칠씩
    틀린다. 페이지에 minutes<회의날짜> 링크가 있고 그 링크가 걸린 셀에
    공개일이 적혀 있으므로, 계산하지 말고 읽는다.
    """
    year = year or datetime.datetime.now(KST).year
    try:
        r = requests.get(FOMC_URL, headers=UA, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        log(f"· FOMC 페이지 실패: {type(e).__name__} {e}")
        return []
    html = r.text

    # 연도 블록을 자른다. '2026 FOMC Meetings' 부터 다음 연도 제목까지.
    marks = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"(\d{4})\s+FOMC\s+Meetings", html)]
    if not marks:
        log("· FOMC 연도 구획을 못 찾았다")
        return []
    block = None
    for i, (pos, y) in enumerate(marks):
        if y == year:
            end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
            block = html[pos:end]
            break
    if block is None:
        log(f"· FOMC {year}년 구획 없음")
        return []

    months = re.findall(r'fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*([A-Z][a-z]+)', block)
    dates = re.findall(r'fomc-meeting__date[^>]*>\s*([^<]+?)\s*<', block)
    # 의사록: minutes20260429 → 회의 종료일. 그 앞의 텍스트에 공개일이 있다.
    minutes = re.findall(r"minutes(\d{8})", block)

    out = []
    for mon, dat in zip(months, dates):
        mi = MONTHS.get(mon.split("/")[0].strip())
        if not mi:
            continue
        nums = re.findall(r"\d{1,2}", dat)
        if not nums:
            continue
        try:
            end_day = int(nums[-1])
            meet_end = datetime.date(year, mi, end_day)
        except ValueError:
            continue
        stamp = meet_end.strftime("%Y%m%d")
        out.append({
            "kind": "FOMC",
            "date": meet_end.isoformat(),
            "title": f"{mi}월 FOMC 회의 종료",
            "detail": f"{mon} {dat}",
            # 의사록 링크에 이 회의가 잡혀 있으면 이미 공개된 것이다.
            "minutesPublished": stamp in minutes,
        })
        # 의사록 공개일은 통상 회의 종료 3주 뒤 수요일. 링크가 없으면(아직
        # 미공개) 이 추정을 쓰되, 추정임을 표시한다.
        if stamp not in minutes:
            est = meet_end + datetime.timedelta(days=21)
            est += datetime.timedelta(days=(2 - est.weekday()) % 7)   # 다음 수요일
            out.append({
                "kind": "FOMC 의사록",
                "date": est.isoformat(),
                "title": f"{mi}월 FOMC 의사록 공개(예정)",
                "detail": f"{meet_end.isoformat()} 회의분 · 날짜는 통상 관행 기준 추정",
                "estimated": True,
            })
    return out


# ────────────────────────────── 수동 등록 ──────────────────────────────

def manual():
    """data/calendar.json — 사람이 적어 두는 일정.

    형식:
      [{"date": "2026-08-26", "kind": "해외 실적",
        "title": "엔비디아 2분기 실적", "detail": "현지 오후 5시"}]
    """
    if not MANUAL.exists():
        log(f"· {MANUAL.relative_to(ROOT)} 없음 — 수동 일정 생략")
        return []
    try:
        rows = json.loads(MANUAL.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"· calendar.json 파싱 실패: {e}")
        return []
    if isinstance(rows, dict):
        rows = rows.get("events") or []
    out = []
    for r in rows:
        try:
            datetime.date.fromisoformat(str(r["date"]))
        except Exception:
            log(f"· 날짜 형식 이상, 건너뜀: {r}")
            continue
        out.append({"kind": r.get("kind") or "일정", "date": r["date"],
                    "title": r.get("title") or "", "detail": r.get("detail") or "",
                    "manual": True})
    return out


# ────────────────────────────── 조립 ──────────────────────────────

def collect(days=14, today=None):
    today = today or datetime.datetime.now(KST).date()
    end = today + datetime.timedelta(days=days)
    rows = fomc(today.year) + fomc(today.year + 1 if end.year != today.year else today.year) + manual()

    seen, kept = set(), []
    for r in rows:
        key = (r["date"], r["kind"], r["title"])
        if key in seen:
            continue
        seen.add(key)
        d = datetime.date.fromisoformat(r["date"])
        if today <= d <= end:
            kept.append(r)
    kept.sort(key=lambda r: (r["date"], r["kind"]))
    return {
        "generatedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "from": today.isoformat(),
        "to": end.isoformat(),
        "events": kept,
    }


def summarize(d):
    L = [f"■ {d['from']} ~ {d['to']} · {len(d['events'])}건"]
    if not d["events"]:
        L.append("  (해당 기간에 등록된 일정이 없다)")
    for e in d["events"]:
        wd = "월화수목금토일"[datetime.date.fromisoformat(e["date"]).weekday()]
        flag = " ※추정" if e.get("estimated") else ""
        L.append(f"  {e['date']}({wd})  [{e['kind']}] {e['title']}{flag}")
        if e.get("detail"):
            L.append(f"                  {e['detail']}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = collect(a.days)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
