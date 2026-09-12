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
# 200 을 돌려주는 것이 확인된 주소만 쓴다. curYear 같은 매개변수를 멋대로
# 붙였다가 화면이 안 그려진 적이 있다 — 확인 안 된 것을 끼워 넣지 않는다.
URL = "https://www.bok.or.kr/portal/singl/crncyPolicyDrcMtg/listYear.do?mtgSe=A&menuNo=200755"
KST = datetime.timezone(datetime.timedelta(hours=9))
DATE = re.compile(r"(20\d\d)[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def rows_from_page(year, headless=True):
    """(행 목록, 오류). 행은 {date, text}.

    화면이 이렇게 찍힌다 — 연도가 날짜에 안 붙어 있다.

        02월 26일(목)
            통화정책방향 관련 총재 기자간담회 (2026.02)
        04월 10일(금)
            통화정책방향 관련 총재 기자간담회 (2026.04)

    연도는 위쪽 '년도선택' 상자에 따로 있다. 처음에는 네 자리 연도를 찾는
    정규식을 썼다가 한 줄도 못 읽었다. 그래서 DOM 구조에 기대지 않고
    화면 글자를 줄 단위로 읽는다 — 표가 되든 목록이 되든 사람 눈에
    보이는 것은 이 글자들이고, 그게 가장 덜 깨진다.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "playwright 가 없다 — pip install playwright 후 playwright install chromium"

    head = re.compile(r"^\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일\s*(?:\(([월화수목금토일])\))?")
    inline_year = re.compile(r"\((20\d\d)[.\-/](\d{1,2})\)")

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless)
        pg = b.new_page(locale="ko-KR")
        try:
            pg.goto(URL, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(2000)

            # 연도를 고른다. 상자가 없거나 그 해가 없으면 보이는 대로 읽는다.
            sel = pg.query_selector("select")
            if sel:
                opts = [(o.get_attribute("value") or "", (o.inner_text() or "").strip())
                        for o in sel.query_selector_all("option")]
                want = [v for v, t in opts if str(year) in (v or "") or str(year) in t]
                if want:
                    sel.select_option(want[0])
                    pg.wait_for_load_state("networkidle", timeout=60000)
                    pg.wait_for_timeout(2000)
                else:
                    log(f"· {year}년이 년도선택에 없다: {[t for _, t in opts][:6]}")

            lines = (pg.inner_text("body") or "").split("\n")
        except Exception as e:
            b.close()
            return None, f"{type(e).__name__}: {e}"
        b.close()

    out, seen = [], set()
    for i, ln in enumerate(lines):
        m = head.match(ln)
        if not m:
            continue
        # 뒤따르는 줄에서 무슨 회의인지와 연도를 찾는다
        tail = " ".join(x.strip() for x in lines[i + 1:i + 6] if x.strip())[:220]
        ym = inline_year.search(tail) or inline_year.search(ln)
        y = int(ym.group(1)) if ym else year
        try:
            d = datetime.date(y, int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
        if d.isoformat() in seen:
            continue
        seen.add(d.isoformat())
        # 화면에 적힌 요일과 실제 요일이 다르면 연도를 잘못 붙인 것이다.
        wd = m.group(3)
        if wd and "월화수목금토일"[d.weekday()] != wd:
            log(f"· 요일이 어긋난다 — 화면 {wd} / 계산 "
                f"{'월화수목금토일'[d.weekday()]} ({d}) — 연도를 잘못 붙였을 수 있다. 버린다")
            continue
        out.append({"date": d.isoformat(), "text": tail, "sel": "본문 줄"})
    return sorted(out, key=lambda r: r["date"]), ""


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
           "source": URL,
           "readAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
           "rows": rows}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{OUT.relative_to(ROOT)} 에 {len(rows)}줄 적었다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
