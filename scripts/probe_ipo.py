#!/usr/bin/env python3
"""상장 예정 종목을 언제, 어디서 미리 알 수 있는지 러너에서 한 번에 본다(일회성 · 돈 안 듦 · 저장 · 커밋 없음).

왜 필요한가. 신규 상장 리포트는 상장 다음 날 새벽 ~ 아침에 올라간다(2026-11 래블업 · 이에스티 · 동원파츠 · 바로팜 · 넥스아이 —
상장일 시세가 시세 자료에 들어온 뒤에야 종목을 알아서다). 상장 당일 아침, 늦어도 장 시작 전에 리포트를 내려면 상장 예정 종목의
종목코드 · 이름 · 시장 · 상장일 · 공모가를 그 전에 알아야 한다. 샌드박스에서는 한국거래소 · KIND · DART 에 닿지 않아 러너에서 본다.

  ① 한국거래소 전종목 기본정보(pykrx · 로그인) — 상장일(LIST_DD)이 오늘 이후인 종목이 미리 오르는가
  ② KIND 상장법인목록 내려받기 — 같은 질문
  ③ KIND 공모 · 신규상장 화면 — 상장예정일 · 공모가 · 종목코드가 있는가
  ④ DART — 발행공시(공모) · 거래소공시('상장')에서 상장 예정 회사와 종목코드를 찾을 수 있는가

실행 기록은 공개다 — 공개 정보만 찍는다(키 · 로그인 아이디를 찍지 않는다).
"""
import datetime
import io
import json
import os
import re
import sys
import traceback

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI-probe/1.0)"}
KST = datetime.timezone(datetime.timedelta(hours=9))
TODAY = datetime.datetime.now(KST).date()
SINCE = TODAY - datetime.timedelta(days=21)


def hr(title):
    print("\n" + "=" * 8 + " " + title + " " + "=" * 8, flush=True)


def squeeze(html, n=2500):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"&nbsp;", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n]


def krx_basic():
    hr("① 한국거래소 전종목 기본정보 — 최근 · 앞으로 상장일")
    try:
        from pykrx.website.krx.market.core import 전종목기본정보
        df = 전종목기본정보().fetch(mktId="ALL")
        print("열:", list(df.columns))
        print("전체", len(df))
        d = df.copy()
        d["LIST_DD"] = d["LIST_DD"].astype(str).str.replace("/", "-")
        recent = d[d["LIST_DD"] >= SINCE.isoformat()].sort_values("LIST_DD")
        keep = [c for c in ("ISU_SRT_CD", "ISU_ABBRV", "MKT_TP_NM", "LIST_DD", "LIST_SHRS", "SECUGRP_NM",
                            "KIND_STKCERT_TP_NM", "PARVAL", "ISU_ENG_NM") if c in d.columns]
        print(recent[keep].to_string(index=False))
        print("가장 늦은 상장일:", d["LIST_DD"].max(), " · 오늘:", TODAY)
    except Exception as e:                                     # noqa: BLE001
        print("실패:", type(e).__name__, str(e)[:300])
        traceback.print_exc(limit=2)


def kind_corplist():
    hr("② KIND 상장법인목록 — 최근 · 앞으로 상장일")
    try:
        r = requests.get("https://kind.krx.co.kr/corpgeneral/corpList.do",
                         params={"method": "download", "searchType": "13"}, headers=UA, timeout=30)
        print("HTTP", r.status_code, "길이", len(r.content))
        r.encoding = "euc-kr"
        import pandas as pd
        tabs = pd.read_html(io.StringIO(r.text))
        df = tabs[0]
        print("열:", list(df.columns), "행", len(df))
        col = next((c for c in df.columns if "상장일" in str(c)), None)
        if col:
            df[col] = df[col].astype(str)
            rec = df[df[col] >= SINCE.isoformat()].sort_values(col)
            print(rec.to_string(index=False)[:4000])
            print("가장 늦은 상장일:", df[col].max())
    except Exception as e:                                     # noqa: BLE001
        print("실패:", type(e).__name__, str(e)[:300])


KIND_TRIES = [
    ("공모진행 현황(첫 화면)", "GET", "https://kind.krx.co.kr/listinvstg/pubofrprogcom.do",
     {"method": "searchPubofrProgComMain"}),
    ("공모진행 현황(목록)", "POST", "https://kind.krx.co.kr/listinvstg/pubofrprogcom.do",
     {"method": "searchPubofrProgComSub", "currentPageSize": "50", "pageIndex": "1", "orderMode": "1",
      "orderStat": "D", "searchMode": "", "marketType": "", "searchCorpName": "", "repIsuSrtCd": ""}),
    ("신규상장기업 현황(첫 화면)", "GET", "https://kind.krx.co.kr/listinvstg/listingcompany.do",
     {"method": "searchListingTypeMain"}),
    ("신규상장기업 현황(목록)", "POST", "https://kind.krx.co.kr/listinvstg/listingcompany.do",
     {"method": "searchListingTypeSub", "currentPageSize": "50", "pageIndex": "1", "orderMode": "1",
      "orderStat": "D", "marketType": "", "country": "", "industry": "", "repMbrNm": "",
      "fromDate": SINCE.isoformat(), "toDate": (TODAY + datetime.timedelta(days=30)).isoformat()}),
    ("공모일정(첫 화면)", "GET", "https://kind.krx.co.kr/listinvstg/pubofrschdl.do",
     {"method": "searchPubofrScholMain"}),
    ("상장예비심사 현황(첫 화면)", "GET", "https://kind.krx.co.kr/listinvstg/listinvstgcom.do",
     {"method": "searchListingInvestigationMain"}),
]


def kind_pages():
    hr("③ KIND 공모 · 신규상장 화면")
    s = requests.Session()
    s.headers.update(UA)
    for name, meth, url, params in KIND_TRIES:
        try:
            if meth == "GET":
                r = s.get(url, params=params, timeout=30)
            else:
                r = s.post(url, data=params, timeout=30,
                           headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"})
            print(f"\n--- {name}: HTTP {r.status_code} · {len(r.content)}바이트")
            txt = r.content.decode("utf-8", "replace")
            if "�" in txt[:2000]:
                txt = r.content.decode("euc-kr", "replace")
            # 표의 머리 · 몇 줄 · 폼의 숨은 입력 이름(목록 요청에 필요한 칸을 알기 위해)
            inputs = sorted(set(re.findall(r'name="([A-Za-z_]+)"', txt)))
            if inputs:
                print("입력 칸:", ",".join(inputs[:60]))
            fns = sorted(set(re.findall(r"method=([A-Za-z]+)", txt)))
            if fns:
                print("method 값:", ",".join(fns[:30]))
            print(squeeze(txt, 3000))
        except Exception as e:                                 # noqa: BLE001
            print(f"\n--- {name}: 실패 {type(e).__name__} {str(e)[:200]}")


def dart_list(key, **params):
    out, page = [], 1
    while page <= 30:
        p = dict(crtfc_key=key, page_count=100, page_no=page, **params)
        r = requests.get("https://opendart.fss.or.kr/api/list.json", params=p, timeout=30)
        j = r.json()
        if j.get("status") != "000":
            if page == 1:
                print("  DART 상태", j.get("status"), j.get("message"))
            break
        out += j.get("list") or []
        if page >= int(j.get("total_page") or 1):
            break
        page += 1
    return out


def dart():
    key = os.getenv("DART_API_KEY", "").strip()
    hr("④ DART — 공모(발행공시) · 거래소공시('상장')")
    if not key:
        print("DART_API_KEY 없음 — 건너뜀")
        return
    try:
        bgn = (TODAY - datetime.timedelta(days=7)).strftime("%Y%m%d")
        end = TODAY.strftime("%Y%m%d")
        items = dart_list(key, bgn_de=bgn, end_de=end, pblntf_ty="I")
        print(f"[거래소공시 7일] {len(items)}건 · '상장'이 든 제목:")
        names = {}
        for it in items:
            nm = it.get("report_nm", "")
            if "상장" in nm:
                names.setdefault(nm, []).append(f"{it.get('corp_name')}({it.get('stock_code') or '-'},{it.get('corp_cls')}) "
                                                f"{it.get('rcept_dt')} {it.get('flr_nm')}")
        for nm, rows in sorted(names.items(), key=lambda x: -len(x[1]))[:40]:
            print(f"  {len(rows):3d} · {nm} · 예: {' | '.join(rows[:4])}")
    except Exception as e:                                     # noqa: BLE001
        print("거래소공시 실패:", type(e).__name__, str(e)[:300])

    cands = {}
    try:
        bgn = (TODAY - datetime.timedelta(days=60)).strftime("%Y%m%d")
        end = TODAY.strftime("%Y%m%d")
        items = dart_list(key, bgn_de=bgn, end_de=end, pblntf_ty="C", corp_cls="E")
        print(f"\n[발행공시 60일 · 기타법인(비상장)] {len(items)}건 · 제목 종류:")
        kinds = {}
        for it in items:
            kinds[it.get("report_nm", "")] = kinds.get(it.get("report_nm", ""), 0) + 1
        for nm, n in sorted(kinds.items(), key=lambda x: -x[1])[:30]:
            print(f"  {n:3d} · {nm}")
        for it in items:
            nm = it.get("report_nm", "")
            if "지분증권" in nm or "투자설명서" in nm or "증권발행실적" in nm:
                c = cands.setdefault(it["corp_code"], {"name": it.get("corp_name"), "docs": []})
                c["docs"].append(f"{it.get('rcept_dt')} {nm}")
        print(f"\n[공모 진행 회사] {len(cands)}곳")
        for cc, c in list(cands.items())[:40]:
            print(f"  {c['name']} ({cc}) · " + " / ".join(sorted(c["docs"])[-4:]))
    except Exception as e:                                     # noqa: BLE001
        print("발행공시 실패:", type(e).__name__, str(e)[:300])

    # 회사 개황의 종목코드 · 업종코드 · 결산월 — 상장 전에도 종목코드가 있는가
    print("\n[공모 진행 회사의 회사 개황]")
    for cc, c in list(cands.items())[:25]:
        try:
            j = requests.get("https://opendart.fss.or.kr/api/company.json",
                             params={"crtfc_key": key, "corp_code": cc}, timeout=20).json()
            print(f"  {c['name']}: stock_code={j.get('stock_code')!r} corp_cls={j.get('corp_cls')} "
                  f"induty={j.get('induty_code')} acc_mt={j.get('acc_mt')} eng={j.get('corp_name_eng')!r}")
        except Exception as e:                                 # noqa: BLE001
            print(f"  {c['name']}: 실패 {type(e).__name__}")

    # 지분증권 증권신고서 주요정보 — 일정(청약 · 납입 · 상장예정일?) 칸이 있는가
    print("\n[지분증권 증권신고서 주요정보 — 한 곳]")
    for cc, c in list(cands.items())[:3]:
        try:
            j = requests.get("https://opendart.fss.or.kr/api/estkRs.json",
                             params={"crtfc_key": key, "corp_code": cc,
                                     "bgn_de": (TODAY - datetime.timedelta(days=120)).strftime("%Y%m%d"),
                                     "end_de": TODAY.strftime("%Y%m%d")}, timeout=30).json()
            print(f"  {c['name']}: 상태 {j.get('status')} {j.get('message')}")
            for g in (j.get("group") or [])[:8]:
                rows = g.get("list") or []
                print(f"    · {g.get('title')} ({len(rows)}줄) 예: {json.dumps(rows[:1], ensure_ascii=False)[:600]}")
        except Exception as e:                                 # noqa: BLE001
            print(f"  {c['name']}: 실패 {type(e).__name__} {str(e)[:200]}")


if __name__ == "__main__":
    print("오늘(한국 시간):", TODAY, "· 기준:", SINCE, "이후")
    krx_basic()
    kind_corplist()
    kind_pages()
    dart()
    sys.exit(0)
