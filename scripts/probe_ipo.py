#!/usr/bin/env python3
"""상장 예정 종목의 종목코드를 상장일 전에 알 수 있는지 러너에서 본다(일회성 · 돈 안 듦 · 저장 · 커밋 없음).

1 · 2차 결과(2026-11-18) — 한국거래소 전종목 기본정보 · 종목 검색 · KIND 상장법인목록은 상장일부터 종목을 올린다. DART 회사
개황의 종목코드는 상장 전에 비어 있다. KIND 공모진행 현황은 상장예정일 · 확정 공모가 · 시장 · 주관사를 몇 주 전부터 준다.
KIND 오늘의 공시에 코스닥시장본부의 '신규상장' 안내가 상장 이틀 전 오후에 오른다(에이엘로봇 11/16 18:06 → 11/18 상장 ·
하나에어로 11/18 17:03 → 11/20 상장). 3차는 그 안내 문서를 열어 종목코드 · 상장일 · 상장주식수가 있는지 본다.

  ① KIND 오늘의 공시에서 '신규상장' 줄의 접수번호 · 회사 번호
  ② 공시 뷰어 → 문서 번호 → 본문(종목코드 · 표준코드 · 상장일 · 상장주식수 …)
  ③ 회사 요약(회사 번호) — 종목코드가 미리 있는가

실행 기록은 공개다 — 공개 정보만 찍는다.
"""
import datetime
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI-probe/1.0)"}
KST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.now(KST)
TODAY = NOW.date()
KIND = "https://kind.krx.co.kr"
S = requests.Session()
S.headers.update(UA)


def hr(title):
    print("\n" + "=" * 8 + " " + title + " " + "=" * 8, flush=True)


def squeeze(html, n=2500):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]


def dec(r):
    t = r.content.decode("utf-8", "replace")
    if t.count("�") > 20:
        t = r.content.decode("euc-kr", "replace")
    return t


def today_rows(d):
    url = KIND + "/disclosure/todaydisclosure.do"
    S.get(url, params={"method": "searchTodayDisclosureMain"}, timeout=30)
    r = S.post(url, data={"method": "searchTodayDisclosureSub", "currentPageSize": "300", "pageIndex": "1",
                          "orderMode": "0", "orderStat": "D", "forward": "todaydisclosure_sub", "chose": "S",
                          "todayFlag": "N", "selDate": d.isoformat(), "marketType": ""},
               headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"}, timeout=30)
    return re.findall(r"<tr[^>]*>(.*?)</tr>", dec(r), re.S)


def notices(days=6):
    hr("① KIND 오늘의 공시 — '신규상장' 줄")
    out = []
    for back in range(days):
        d = TODAY - datetime.timedelta(days=back)
        for tr in today_rows(d):
            if "신규상장" not in tr:
                continue
            acpt = re.findall(r"openDisclsViewer\('(\d+)'", tr)
            isur = re.findall(r"companysummary_open\('([0-9A-Z]+)'\)", tr)
            title = re.findall(r"title='([^']*)'", tr)
            print(f"  {d} · {squeeze(tr, 160)} · 접수번호 {acpt} · 회사 번호 {isur} · 제목 {title}")
            out.append((d, acpt[0] if acpt else None, isur[0] if isur else None, squeeze(tr, 200)))
    return out


def viewer(acpt):
    hr(f"② 공시 뷰어 — {acpt}")
    r = S.get(KIND + "/common/disclsviewer.do", params={"method": "search", "acptno": acpt, "docno": "",
                                                      "viewerhost": "", "viewerport": ""}, timeout=30)
    html = dec(r)
    print("HTTP", r.status_code, len(html))
    docs = re.findall(r"<option[^>]*value=['\"]([^'\"]+)['\"][^>]*>([^<]*)</option>", html)
    print("문서 목록:", docs[:10])
    js = re.findall(r"(searchContents[^;]{0,200})", html)
    print("본문 호출 흔적:", js[:5])
    for val, _name in docs[:3]:
        doc = val.split("|")[0]
        if not doc:
            continue
        rc = S.get(KIND + "/common/disclsviewer.do", params={"method": "searchContents", "docNo": doc}, timeout=30)
        body = dec(rc)
        print(f"\n  [문서 {doc}] HTTP {rc.status_code} · {squeeze(body, 600)}")
        paths = re.findall(r"(/external/[^'\"\s]+?\.htm)", body) + re.findall(r"(https?://[^'\"\s]+?\.htm)", body)
        print("  본문 경로:", paths[:5])
        for p in paths[:2]:
            u = p if p.startswith("http") else KIND + p
            rp = S.get(u, timeout=30)
            t = squeeze(dec(rp), 4000)
            print(f"\n  [본문] HTTP {rp.status_code} · {t}")
            for k in ("종목코드", "단축코드", "표준코드", "상장일", "상장예정일", "상장주식수", "매매개시일", "공모가", "기준가"):
                m = re.search(k + r".{0,80}", t)
                if m:
                    print(f"    · {m.group(0)}")
            return
    # 문서 목록이 없으면 원문 일부
    print(squeeze(html, 1500))


def company(isur):
    hr(f"③ 회사 요약 — {isur}")
    for params in ({"method": "searchCompanySummary", "strIsurCd": isur},
                   {"method": "searchCompanySummaryOvrvwDetail", "menuIndex": "0", "strIsurCd": isur, "lstCd": "undefined",
                    "taskDv": "", "spotIsuTrdMktTpCd": "", "methodType": "0"}):
        try:
            r = S.get(KIND + "/common/companysummary.do", params=params, timeout=30)
            t = squeeze(dec(r), 1800)
            print(f"  [{params['method']}] HTTP {r.status_code}: {t}")
        except Exception as e:                                 # noqa: BLE001
            print(f"  [{params['method']}] 실패 {type(e).__name__}")


if __name__ == "__main__":
    print("지금(한국 시간):", NOW.strftime("%Y-%m-%d %H:%M"))
    got = notices()
    seen = set()
    for d, acpt, isur, txt in got:
        if acpt and acpt not in seen and len(seen) < 3:
            seen.add(acpt)
            try:
                viewer(acpt)
            except Exception as e:                             # noqa: BLE001
                print("뷰어 실패:", type(e).__name__, str(e)[:200])
        if isur:
            try:
                company(isur)
            except Exception as e:                             # noqa: BLE001
                print("회사 요약 실패:", type(e).__name__)
    sys.exit(0)
