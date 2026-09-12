#!/usr/bin/env python3
"""한국은행 금융통화위원회 일정을 공식 페이지에서 직접 읽는다.

왜 브라우저로 여는가
--------------------
통화정책방향 결정회의 목록(listYear.do)은 472KB 가 열리는데 그 안에 날짜가
하나뿐이다. 표가 화면에서 그려지기 때문이다. 첫화면(contents.do)에는 6개가
있지만 연 8회와 맞지 않고, 무엇이 회의일이고 무엇이 의사록 공개일인지
구분되지 않는다. 여기서 짐작하면 없는 회의를 만들게 된다 — 실제로 초안
파서가 바닥글의 게시일을 회의로 셌던 적이 있다.

그래서 실제 브라우저로 띄워 사람이 보는 표를 그대로 읽는다. 느리지만
(30초 남짓) 한 달에 한 번만 돌면 된다. 매일 쓰는 브리핑은 여기서 나온
파일만 읽으므로 느려지지 않는다.

    python3 scripts/bok_schedule.py            # 무엇이 있는지 보기만
    python3 scripts/bok_schedule.py --write    # data/bok_meetings.json 에 쓴다
    python3 scripts/bok_schedule.py --year 2027
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "bok_meetings.json"
URL = ("https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do"
       "?mtgSe=A&menuNo=200755&curYear={year}")
KST = datetime.timezone(datetime.timedelta(hours=9))
DATE = re.compile(r"(20\d\d)[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def rows_from_page(year, headless=True):
    """(행 목록, 오류). 행은 {date, text} — 판정은 부르는 쪽에서."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright 가 없다 — pip install playwright 후 playwright install chromium"

    out = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless)
        pg = b.new_page(locale="ko-KR")
        try:
            pg.goto(URL.format(year=year), wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(2500)
            # 표든 목록이든, 날짜가 들어 있는 가장 작은 덩어리를 모은다.
            for sel in ("table tr", "ul li", ".board-list li", ".tbl-list tr"):
                for el in pg.query_selector_all(sel):
                    t = re.sub(r"\s+", " ", (el.inner_text() or "")).strip()
                    if not t or len(t) > 400:
                        continue
                    m = DATE.search(t)
                    if not m:
                        continue
                    try:
                        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                    except ValueError:
                        continue
                    out.append({"date": d.isoformat(), "text": t[:200], "sel": sel})
                if out:
                    break
        except Exception as e:
            b.close()
            return None, f"{type(e).__name__}: {e}"
        b.close()
    # 같은 날짜가 여러 선택자로 잡히면 하나로
    seen, uniq = set(), []
    for r in sorted(out, key=lambda x: x["date"]):
        if r["date"] in seen:
            continue
        seen.add(r["date"])
        uniq.append(r)
    return uniq, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=datetime.datetime.now(KST).year)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    rows, err = rows_from_page(a.year)
    if rows is None:
        log(f"❌ {a.year} 읽기 실패: {err}")
        return 1
    print(f"■ {a.year}년 · 표에서 읽은 줄 {len(rows)}개")
    for r in rows:
        wd = "월화수목금토일"[datetime.date.fromisoformat(r["date"]).weekday()]
        print(f"  {r['date']}({wd})  [{r['sel']}]  {r['text']}")
    if not rows:
        print("  (아무것도 못 읽었다 — 화면 구조가 다르다는 뜻이다)")
        return 1

    if not a.write:
        print("\n보기만 했다. 내용이 맞으면 --write 로 다시 돌린다.")
        return 0

    doc = {"year": a.year,
           "source": URL.format(year=a.year),
           "readAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
           "rows": rows}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{OUT.relative_to(ROOT)} 에 {len(rows)}줄 적었다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
