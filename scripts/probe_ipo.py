#!/usr/bin/env python3
"""상장 예정 종목의 종목코드를 상장일 전에 알 수 있는지 러너에서 본다(일회성 · 돈 안 듦 · 저장 · 커밋 없음).

1차 결과(2026-11-18) — 한국거래소 전종목 기본정보 · KIND 상장법인목록은 상장일부터 종목을 올리고(그날 상장한 에이엘로봇이 있다 ·
앞으로의 상장일은 없다), DART 회사 개황의 종목코드는 상장 이틀 전 하나에어로다이내믹스(11/20 상장)도 비어 있다. KIND 공모진행
현황은 상장예정일 · 확정 공모가를 몇 주 전부터 준다(종목코드는 글에 없었다). 2차는 —

  ① KIND 공모진행 현황 — 줄마다 붙은 링크 값(회사 번호)과 표
  ② 한국거래소 종목 검색(finder) — 상장 전 종목이 미리 오르는가(종목코드 · 표준코드)
  ③ KIND 회사 요약 — 상장 예정 회사의 종목코드가 미리 있는가
  ④ KIND 오늘의 공시 — 상장 전날 '신규상장' 안내(종목코드)가 있는가

실행 기록은 공개다 — 공개 정보만 찍는다.
"""
import datetime
import io
import re
import sys
import traceback

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI-probe/1.0)"}
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.date()
KIND = "https://kind.krx.co.kr"


def hr(title):
    print("\n" + "=" * 8 + " " + title + " " + "=" * 8, flush=True)


def squeeze(html, n=2500):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]


S = requests.Session()
S.headers.update(UA)


def kind_ipo():
    hr("① KIND 공모진행 현황 — 줄과 링크 값")
    url = KIND + "/listinvstg/pubofrprogcom.do"
    S.get(url, params={"method": "searchPubofrProgComMain"}, timeout=30)
    r = S.post(url, data={"method": "searchPubofrProgComSub", "currentPageSize": "30", "pageIndex": "1", "orderMode": "1",
                          "orderStat": "D", "searchMode": "", "marketType": "", "searchCorpName": "", "repIsuSrtCd": ""},
               headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
    html = r.content.decode("utf-8", "replace")
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    print("HTTP", r.status_code, "줄", len(rows))
    out = []
    for i, tr in enumerate(rows):
        cells = [squeeze(c, 200) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if not cells:
            continue
        links = re.findall(r"(?:onclick|href)=\"([^\"]+)\"", tr)
        if i <= 3:
            print("  원문:", re.sub(r"\s+", " ", tr)[:900])
        print("  ·", " | ".join(cells), "| 링크:", " ; ".join(links)[:300])
        out.append((cells, links))
    return out


def krx_finder(names):
    hr("② 한국거래소 종목 검색(finder) — 상장 전 종목이 미리 오르는가")
    try:
        from pykrx.website.krx.market.core import 상장종목검색, 전종목기본정보
        df = 상장종목검색().fetch(mktsel="ALL", searchText="")
        print("검색 목록", len(df), "열", list(df.columns))
        base = 전종목기본정보().fetch(mktId="ALL")
        listed = set(base["ISU_SRT_CD"].astype(str))
        extra = df[~df["short_code"].astype(str).isin(listed)]
        print(f"기본정보에 없는 검색 목록 종목 {len(extra)}개(상장 전 등록 · 우선주 · 리츠 등):")
        print(extra.head(60).to_string(index=False))
        for nm in names:
            for q in {nm, nm[:3]}:
                hit = 상장종목검색().fetch(mktsel="ALL", searchText=q)
                print(f"  검색 '{q}':", (hit[["short_code", "codeName", "marketName", "full_code"]].to_string(index=False)
                                         if len(hit) else "없음"))
    except Exception as e:                                     # noqa: BLE001
        print("실패:", type(e).__name__, str(e)[:300])
        traceback.print_exc(limit=2)


def kind_company(links):
    hr("③ KIND 회사 요약 — 상장 예정 회사의 종목코드")
    seen = set()
    for lk in links:
        for code in re.findall(r"'([0-9A-Z]{5,6})'", lk):
            if code in seen:
                continue
            seen.add(code)
            for meth, params in (
                ("요약", {"method": "searchCompanySummary", "strIsurCd": code}),
                ("개요", {"method": "searchCompanySummaryOvrvwDetail", "menuIndex": "0", "strIsurCd": code,
                         "lstCd": "undefined", "taskDv": "", "spotIsuTrdMktTpCd": "", "methodType": "0"}),
            ):
                try:
                    r = S.get(KIND + "/common/companysummary.do", params=params, timeout=30)
                    txt = squeeze(r.content.decode("utf-8", "replace"), 1500)
                    print(f"\n  [{code} {meth}] HTTP {r.status_code}: {txt}")
                except Exception as e:                         # noqa: BLE001
                    print(f"  [{code} {meth}] 실패 {type(e).__name__}")
            if len(seen) >= 4:
                return


def kind_today(days=4):
    hr("④ KIND 오늘의 공시 — '신규상장' · '상장' 안내")
    url = KIND + "/disclosure/todaydisclosure.do"
    S.get(url, params={"method": "searchTodayDisclosureMain"}, timeout=30)
    for back in range(days):
        d = TODAY - datetime.timedelta(days=back)
        try:
            r = S.post(url, data={"method": "searchTodayDisclosureSub", "currentPageSize": "300", "pageIndex": "1",
                                  "orderMode": "0", "orderStat": "D", "forward": "todaydisclosure_sub", "chose": "S",
                                  "todayFlag": "N", "selDate": d.isoformat(), "marketType": ""},
                       headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
            html = r.content.decode("utf-8", "replace")
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
            hits = [squeeze(tr, 300) for tr in rows if "신규상장" in tr or "상장예정" in tr or "주권상장" in tr]
            print(f"\n  {d}: HTTP {r.status_code} · 줄 {len(rows)} · 신규상장 관련 {len(hits)}")
            for h in hits[:12]:
                print("   ·", h)
            if back == 0 and rows:
                print("   (첫 줄 원문)", re.sub(r"\s+", " ", rows[1] if len(rows) > 1 else rows[0])[:700])
        except Exception as e:                                 # noqa: BLE001
            print(f"  {d}: 실패 {type(e).__name__} {str(e)[:200]}")


if __name__ == "__main__":
    print("지금(한국 시간):", NOW.strftime("%Y-%m-%d %H:%M"))
    rows = kind_ipo()
    upcoming, links = [], []
    for cells, lk in rows:
        dates = [c for c in cells if re.fullmatch(r"20\d\d-\d\d-\d\d", c)]
        if dates and dates[-1] >= TODAY.isoformat():
            upcoming.append(cells[0])
            links += lk
    print("\n상장예정일이 오늘 이후인 회사:", upcoming)
    krx_finder(upcoming[:6])
    kind_company(links)
    kind_today()
    sys.exit(0)
