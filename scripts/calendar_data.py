#!/usr/bin/env python3
"""이번 주에 뭐가 있나 — 브리핑 '볼 것' 섹션의 일정.

이 파일이 왜 이렇게 생겼나 (2026-09-12)
----------------------------------------
9월 11일 브리핑에 이렇게 나갔다.

    "앞으로 2주간 일정표에 잡힌 이벤트는 9월 16일 FOMC 회의 종료 하나뿐이다"

사실이 아니다. 정말 하나뿐인 게 아니라 **우리가 안 넣어서** 하나였다.
일정의 절반은 data/calendar.json 에 사람이 손으로 적는 구조였는데, 마지막
등록이 8월 27일이었다. 2주 넘게 말라 있었고 아무도 몰랐다. 비었을 때
알려 주는 장치가 없었기 때문이다.

그래서 두 가지를 바꿨다.

  1. 사람 손을 빼고 가져올 수 있는 것은 가져온다(FOMC·BLS·한국은행).
  2. **더 중요한 것** — 갈래마다 "가져왔는지"를 보고하게 했다. 예전에는
     실패해도 빈 목록을 돌려줘서, 받는 쪽이 '못 가져온 것'과 '진짜 없는
     것'을 구분할 수 없었다. 이제 collect() 는 events 와 함께 health 를
     돌려주고, 앞으로 며칠에 일정이 너무 적으면 그 자체를 문제로 적는다.
     브리핑 프롬프트에도 그 사실이 넘어가므로, 모델이 "일정이 하나뿐"을
     시장의 사실인 양 쓰지 않는다.

갈래
  1. FOMC        연준 사이트. 회의 날짜와 의사록 공개일까지.
  2. 미국 지표    BLS 연간 공표 일정. 소비자물가·생산자물가·고용보고서 등.
  3. 금통위      한국은행 통화정책방향 회의.
  4. 수동 등록    data/calendar.json. 위 셋으로 안 잡히는 것(엔비디아 실적,
                 잭슨홀 등)만. 이제 비면 경보가 울린다.
  5. 국내 공시    brief_data.py 가 이미 본다. 여기서 중복해서 받지 않는다.

    python3 scripts/calendar_data.py                 # 앞으로 14일
    python3 scripts/calendar_data.py --days 30 --json
    python3 scripts/calendar_data.py --check         # 비었으면 1 을 돌려준다
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
MANUAL = ROOT / "data" / "calendar.json"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
# 미국 지표 일정. bls.gov 는 통째로 막혀 있다 — 2026-09-12 에 재 보니
# 연간표·첫 화면·RSS 어느 주소든, 기본 UA 든 브라우저 UA 든 403 에
# 1,325바이트짜리 차단 페이지만 온다. GitHub 러너 IP 를 막는 것으로 보인다.
# 대신 세인트루이스 연준(FRED)이 같은 발표 일정을 API 로 준다. 열쇠가
# 필요하지만 무료다(https://fredaccount.stlouisfed.org/apikeys).
FRED_URL = "https://api.stlouisfed.org/fred/releases/dates"
BOK_FILE = ROOT / "data" / "bok_meetings.json"
# (아래 주석은 왜 파일에서 읽는지를 적어 둔 것이다.)
# 금통위 일정은 그냥 긁어서는 못 가져온다 — 2026-09-12 에 후보 4개를 재 봤다.
# 국문 페이지는 472,179바이트가 열리는데 그 안에 한국식 날짜가 2개뿐이고
# '통화정책방향'은 18번 나온다(메뉴 글자). 목록이 화면에서 그려진다는 뜻
# 이라 긁을 것이 없다. 영문 페이지도 같고, 한은 RSS 는 500, 통계청은
# 148바이트를 준다. ECOS API 는 통계 수치용이지 회의 일정을 주지 않는다.
#
# 그래서 실제 브라우저로 띄워 읽는다 — scripts/bok_schedule.py 가 한 달에
# 한 번 돌며 data/bok_meetings.json 에 적고, 여기서는 그 파일만 읽는다.
# 매일 도는 브리핑이 브라우저를 띄울 이유는 없다.


def bok():
    """data/bok_meetings.json — 한국은행 페이지에서 읽어 둔 금통위 일정."""
    if not BOK_FILE.exists():
        return [], _health("금통위", True, 0,
                           "아직 읽어 둔 것이 없다 — scripts/bok_schedule.py --write")
    try:
        doc = json.loads(BOK_FILE.read_text(encoding="utf-8"))
        rows = doc.get("rows") or []
    except Exception as e:
        return [], _health("금통위", False, 0, f"파일을 못 읽었다 — {e}")

    out = []
    for r in rows:
        try:
            datetime.date.fromisoformat(r["date"])
        except Exception:
            continue
        out.append({"kind": "국내 지표", "date": r["date"],
                    "title": "한국은행 금융통화위원회(통화정책방향)",
                    "detail": "기준금리 결정"})
    # 읽어 둔 것이 낡았나. 올해 것이 없으면 갱신이 멈춘 것이다.
    today = datetime.datetime.now(KST).date()
    if not any(r["date"][:4] == str(today.year) for r in out):
        return out, _health("금통위", False, len(out),
                            f"{doc.get('year')}년치뿐이다 — {today.year}년 일정을 다시 읽어야 한다")
    if len(out) != 8:
        return out, _health("금통위", False, len(out), "연 8회와 다르다")
    return out, _health("금통위", True, len(out),
                        f"{doc.get('year')}년 · {str(doc.get('readAt'))[:10]} 에 읽음")
# 앞으로 이 기간에 일정이 이 수보다 적으면 "수집이 빠졌을 수 있다"로 본다.
# 9월 11일 사고 때가 14일에 1건이었다.
THIN_DAYS, THIN_MIN = 14, 3
# 수동 등록이 이보다 오래 갱신되지 않았으면 말라붙은 것으로 본다.
MANUAL_STALE_DAYS = 21
# FRED 에서 집어올 발표. 전부 가져오면 하루에 수십 건이라 잡음이 된다.
FRED_WANT = [
    ("Consumer Price Index", "미국 소비자물가"),
    ("Producer Price Index", "미국 생산자물가"),
    ("Employment Situation", "미국 고용보고서"),
    ("Real Earnings", "미국 실질임금"),
    ("Job Openings and Labor Turnover", "미국 구인·이직(JOLTS)"),
    ("Employment Cost Index", "미국 고용비용지수"),
    ("Import and Export Price Indexes", "미국 수출입물가"),
    ("Gross Domestic Product", "미국 GDP"),
    ("Personal Income and Outlays", "미국 개인소비·PCE"),
    ("Advance Monthly Sales for Retail", "미국 소매판매"),
]
# 우리를 봇이라고 밝히면 막는 곳이 있다. bls.gov 가 403 을 줬다.
# 연준은 지금 UA 로 잘 되므로 기본은 그대로 두고, 막히는 곳에만 브라우저
# UA 를 쓴다. 거짓말을 하려는 게 아니라 공개 페이지를 읽으려는 것이다.
UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0)"}
UA_BROWSER = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                   " (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.8",
}
TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))

MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _health(name, ok, found, note=""):
    """갈래 하나의 상태. ok=False 는 '못 가져왔다'이지 '없다'가 아니다.

    이 구분이 이 파일의 핵심이다. 예전에는 실패해도 빈 목록만 돌려줘서
    받는 쪽이 둘을 구분할 수 없었고, 그래서 "일정이 하나뿐"이라는 문장이
    시장의 사실인 것처럼 브리핑에 나갔다.
    """
    return {"name": name, "ok": bool(ok), "found": int(found), "note": note}


def _get(url, headers=None):
    """(본문, 실패사유). 실패해도 예외를 올리지 않는다.

    403 은 '없다'가 아니라 '우리를 막았다'이다. 그럴 때는 브라우저 UA 로
    한 번 더 두드린다 — bls.gov 가 실제로 그랬다.
    """
    last = ""
    for hdr in ([headers] if headers else [UA, UA_BROWSER]):
        try:
            r = requests.get(url, headers=hdr, timeout=TIMEOUT)
            r.raise_for_status()
            return r.text, ""
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            code = getattr(getattr(e, "response", None), "status_code", None)
            if code not in (401, 403, 406, 429):
                break
    return None, last


# ────────────────────────────── FOMC ──────────────────────────────

def fomc(year=None):
    """연준 페이지에서 회의 일정과 의사록 공개일.

    의사록은 회의 3주 뒤에 공개된다. 그런데 '3주 뒤'로 계산하면 며칠씩
    틀린다. 페이지에 minutes<회의날짜> 링크가 있고 그 링크가 걸린 셀에
    공개일이 적혀 있으므로, 계산하지 말고 읽는다.
    """
    year = year or datetime.datetime.now(KST).year
    html, err = _get(FOMC_URL)
    if html is None:
        log(f"· FOMC 페이지 실패: {err}")
        return [], _health("FOMC", False, 0, f"내려받기 실패 — {err}")

    # 연도 블록을 자른다. '2026 FOMC Meetings' 부터 다음 연도 제목까지.
    marks = [(m.start(), int(m.group(1)))
             for m in re.finditer(r"(\d{4})\s+FOMC\s+Meetings", html)]
    if not marks:
        log("· FOMC 연도 구획을 못 찾았다")
        return [], _health("FOMC", False, 0, "페이지 모양이 바뀌었다 — 연도 구획을 못 찾았다")
    block = None
    for i, (pos, y) in enumerate(marks):
        if y == year:
            end = marks[i + 1][0] if i + 1 < len(marks) else len(html)
            block = html[pos:end]
            break
    if block is None:
        log(f"· FOMC {year}년 구획 없음")
        return [], _health("FOMC", False, 0, f"{year}년 구획이 페이지에 없다")

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
    # 회의는 연 8회다. 한 자리도 못 읽었으면 파싱이 깨진 것이다.
    ok = len([x for x in out if x["kind"] == "FOMC"]) >= 4
    return out, _health(f"FOMC {year}", ok, len(out),
                        "" if ok else "연 8회인데 4건도 못 읽었다 — 파싱이 깨졌을 수 있다")


# ────────────────────────────── 미국 지표 (BLS) ──────────────────────────────

_TAG = re.compile(r"<[^>]+>")


def _text(html):
    return re.sub(r"\s+", " ", _TAG.sub(" ", html)).strip()


def fred(year=None):
    """미국 주요 지표 발표 일정 — 세인트루이스 연준(FRED) API.

    왜 BLS 가 아니라 FRED 인가
    --------------------------
    bls.gov 를 긁으려 했는데 통째로 403 이다. 연간표·첫 화면·RSS 를 기본
    UA 와 브라우저 UA 로 각각 두드려 봤고 여섯 번 다 1,325바이트짜리
    차단 페이지가 왔다. 러너 IP 를 막는 것이라 UA 로는 못 넘는다.

    FRED 는 같은 발표(소비자물가·고용보고서 등)의 일정을 API 로 준다.
    열쇠가 없으면 조용히 건너뛴다 — 그건 고장이 아니라 설정이 안 된 것이라
    경보를 울리지 않는다. 매일 울리는 경보는 곧 아무도 안 보는 경보가 된다.
    열쇠가 있는데 실패하면 그때는 문제로 잡는다.
    """
    key = os.getenv("FRED_API_KEY", "").strip()
    if not key:
        return [], _health("미국 지표", True, 0,
                           "FRED 열쇠(FRED_API_KEY)가 없어 건너뛴다 — "
                           "무료 발급: https://fredaccount.stlouisfed.org/apikeys")
    today = datetime.datetime.now(KST).date()
    # sort_order 를 안 주면 최신순(desc)이라 지난 발표만 1,000건 받아 온다.
    # 실제로 그렇게 돌려 보니 '11건 읽음'인데 앞으로 60일에는 하나도 없었다.
    # 우리가 필요한 것은 앞으로의 일정이므로 오늘부터 오름차순으로 받는다.
    # include_release_dates_with_no_data 는 '아직 자료가 안 나온 예정일'을
    # 포함시키는 것이다 — 이게 없으면 미래가 통째로 빠진다.
    url = (f"{FRED_URL}?api_key={key}&file_type=json"
           f"&realtime_start={today}&realtime_end={today + datetime.timedelta(days=120)}"
           f"&include_release_dates_with_no_data=true&sort_order=asc&limit=1000")
    body, err = _get(url, headers=UA)
    if body is None:
        return [], _health("미국 지표", False, 0, f"FRED 내려받기 실패 — {err}")
    try:
        rows = json.loads(body).get("release_dates") or []
    except Exception as e:
        return [], _health("미국 지표", False, 0, f"FRED 응답을 못 읽었다 — {e}")

    out, seen = [], set()
    for r in rows:
        nm = r.get("release_name") or ""
        for needle, ko in FRED_WANT:
            if needle.lower() not in nm.lower():
                continue
            d = r.get("date") or ""
            if (d, ko) in seen:
                continue
            seen.add((d, ko))
            out.append({"kind": "해외 지표", "date": d, "title": ko,
                        "detail": f"{nm} · FRED 공표 일정"})
            break
    ahead = [r for r in out if r["date"] >= today.isoformat()]
    # '읽었다'와 '쓸 수 있다'는 다르다. 지난 발표만 잔뜩 읽고 ok 라고 하면
    # 실제로는 일정이 비어 있는데 아무도 모른다 — 한 번 그랬다.
    ok = bool(ahead)
    return out, _health("미국 지표", ok, len(out),
                        f"앞으로 {len(ahead)}건" if ok else
                        f"{len(out)}건을 읽었지만 앞으로의 일정이 하나도 없다 — "
                        "지난 발표만 받아 온 것이다")


# ────────────────────────────── 수동 등록 ──────────────────────────────

def manual():
    """data/calendar.json — 사람이 적어 두는 일정.

    형식:
      [{"date": "2026-08-26", "kind": "해외 실적",
        "title": "엔비디아 2분기 실적", "detail": "현지 오후 5시"}]
    """
    if not MANUAL.exists():
        log(f"· {MANUAL.relative_to(ROOT)} 없음 — 수동 일정 생략")
        return [], _health("수동 등록", True, 0, "파일이 없다(자동 갈래만 쓴다)")
    try:
        rows = json.loads(MANUAL.read_text(encoding="utf-8"))
    except Exception as e:
        log(f"· calendar.json 파싱 실패: {e}")
        return [], _health("수동 등록", False, 0, f"파싱 실패 — {e}")
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
    # 말라붙었나. 8월 27일이 마지막이었는데 아무도 몰랐던 게 이번 사고다.
    # 파일이 '있는데 앞날이 없는' 상태를 정상으로 보면 안 된다.
    today = datetime.datetime.now(KST).date()
    ahead = [r for r in out if datetime.date.fromisoformat(r["date"]) >= today]
    last = max((r["date"] for r in out), default="")
    if not ahead:
        gap = (today - datetime.date.fromisoformat(last)).days if last else 9999
        return out, _health("수동 등록", False, len(out),
                            f"앞으로 잡힌 것이 하나도 없다 — 마지막 등록 {last or '없음'}"
                            f"({gap}일 지남). 손으로 채우는 파일이라 말라붙은 것이다")
    return out, _health("수동 등록", True, len(out), f"앞으로 {len(ahead)}건")


# ────────────────────────────── 조립 ──────────────────────────────

def collect(days=14, today=None):
    """일정 + 건강 기록.

    건강 기록이 이 함수의 절반이다. 일정이 적을 때 그것이 '조용한 주'인지
    '우리가 못 가져온 것'인지를 부르는 쪽이 알 수 있어야 한다.
    """
    today = today or datetime.datetime.now(KST).date()
    end = today + datetime.timedelta(days=days)
    years = sorted({today.year, end.year})

    rows, sources = [], []
    for y in years:
        for fn in (fomc, fred):
            got, h = fn(y)
            rows += got
            sources.append(h)
    got, h = bok()
    rows += got
    sources.append(h)
    got, h = manual()
    rows += got
    sources.append(h)

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

    problems = [f"{h['name']}: {h['note'] or '가져오지 못했다'}"
                for h in sources if not h["ok"]]
    # 갈래가 다 성공해도 앞이 비어 있을 수 있다. 그 자체를 문제로 본다 —
    # 9월 11일에 14일치가 1건이었는데 아무 데서도 소리가 나지 않았다.
    near = [r for r in kept
            if datetime.date.fromisoformat(r["date"]) <= today + datetime.timedelta(days=THIN_DAYS)]
    thin = len(near) < THIN_MIN
    if thin:
        problems.append(f"앞으로 {THIN_DAYS}일에 {len(near)}건뿐이다"
                        f"(최소 {THIN_MIN}건은 나와야 정상) — 수집이 빠졌을 수 있다")

    return {
        "generatedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "from": today.isoformat(),
        "to": end.isoformat(),
        "events": kept,
        "sources": sources,
        "health": {"ok": not problems, "thin": thin, "problems": problems},
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
    L.append("")
    L.append("■ 갈래별 상태")
    for h in d.get("sources") or []:
        mark = "✅" if h["ok"] else "❌"
        L.append(f"  {mark} {h['name']}: {h['found']}건"
                 + (f" — {h['note']}" if h["note"] else ""))
    hl = d.get("health") or {}
    if hl.get("problems"):
        L.append("")
        L.append("■ ⚠️ 손봐야 할 것")
        for x in hl["problems"]:
            L.append(f"  · {x}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=14)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true",
                    help="문제가 있으면 1 을 돌려준다(감시 잡용)")
    a = ap.parse_args()
    d = collect(a.days)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    if a.check and not d["health"]["ok"]:
        for x in d["health"]["problems"]:
            print(f"::warning title=브리핑 일정::{x}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
