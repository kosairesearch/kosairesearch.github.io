#!/usr/bin/env python3
"""증권신고서 · 투자설명서에서 요약재무정보 · 수요예측 결과를 읽을 수 있는지 러너에서 본다(일회성 · 돈 안 듦 · 저장 · 커밋 없음).

상장 전 회사는 DART 재무 조회(정기보고서)에 값이 없다. 회사가 낸 증권신고서 · 투자설명서 원문(document.xml)에 감사받은 요약재무정보
(최근 3년 · 최근 분기)와 수요예측 결과 · 공모 자금 사용 목적이 있다. 문서 구조(표 태그 · 단위 · 열)를 본다.

실행 기록은 공개다 — 공개 공시만 찍는다(키를 찍지 않는다).
"""
import datetime
import io
import os
import re
import sys
import zipfile

import requests

KEY = os.getenv("DART_API_KEY", "").strip()
NAMES = ["하나에어로다이내믹스", "에이엘로봇", "아델", "유캐스트", "엠비디", "옵토닉스"]
TODAY = datetime.date.today()


def hr(t):
    print("\n" + "=" * 8 + " " + t + " " + "=" * 8, flush=True)


def text_of(x):
    t = re.sub(r"<[^>]+>", " ", x)
    t = re.sub(r"&nbsp;|&#160;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    import dart_reader
    dart = dart_reader.reader(KEY)
    cc = dart.corp_codes
    for nm in NAMES:
        hr(nm)
        hit = cc[cc["corp_name"] == nm]
        if hit.empty:
            print("회사 번호 없음 — 비슷한 이름:", list(cc[cc["corp_name"].str.contains(nm[:3], na=False)]["corp_name"][:8]))
            continue
        code = hit.iloc[0]["corp_code"]
        print("회사 번호", code, "종목코드", repr(hit.iloc[0]["stock_code"]))
        j = requests.get("https://opendart.fss.or.kr/api/list.json", params={
            "crtfc_key": KEY, "corp_code": code, "bgn_de": (TODAY - datetime.timedelta(days=200)).strftime("%Y%m%d"),
            "end_de": TODAY.strftime("%Y%m%d"), "page_count": 100}, timeout=30).json()
        rows = j.get("list") or []
        for r in rows[:25]:
            print(f"  {r['rcept_dt']} {r['rcept_no']} {r['report_nm']}")
        pick = next((r for r in rows if r["report_nm"].strip().startswith("투자설명서")), None) \
            or next((r for r in rows if "증권신고서(지분증권)" in r["report_nm"]), None)
        if not pick:
            print("  증권신고서 · 투자설명서 없음")
            continue
        print("  → 읽을 문서:", pick["rcept_no"], pick["report_nm"])
        z = requests.get("https://opendart.fss.or.kr/api/document.xml",
                         params={"crtfc_key": KEY, "rcept_no": pick["rcept_no"]}, timeout=60)
        print("  내려받기", z.status_code, len(z.content), "바이트", z.headers.get("content-type"))
        try:
            zf = zipfile.ZipFile(io.BytesIO(z.content))
        except zipfile.BadZipFile:
            print("  zip 아님:", z.content[:300])
            continue
        for info in zf.infolist():
            print("   파일", info.filename, info.file_size)
        main_name = max(zf.infolist(), key=lambda i: i.file_size).filename
        raw = zf.read(main_name)
        doc = raw.decode("utf-8", "replace")
        if doc.count("�") > 50:
            doc = raw.decode("euc-kr", "replace")
        print("  본문 글자 수", len(doc), "· 표 태그", sorted(set(re.findall(r"<(TABLE|TR|TD|TH|TE|TU|P|SPAN|TITLE)\b", doc)))[:12])
        for kw in ("요약재무정보", "요약 재무정보", "요약재무"):
            i = doc.find(kw)
            if i >= 0:
                print(f"  [{kw}] 첫 자리 {i} · 원문 앞부분:")
                print("   ", doc[i:i + 2500].replace("\n", " ")[:2500])
                print("  [글만]", text_of(doc[i:i + 9000])[:2500])
                break
        for kw in ("수요예측 결과", "수요예측결과", "의무보유확약", "경쟁률"):
            for m in list(re.finditer(kw, doc))[:2]:
                print(f"  [{kw}]", text_of(doc[max(0, m.start() - 200): m.start() + 900])[:600])
        e = requests.get("https://opendart.fss.or.kr/api/estkRs.json", params={
            "crtfc_key": KEY, "corp_code": code, "bgn_de": (TODAY - datetime.timedelta(days=200)).strftime("%Y%m%d"),
            "end_de": TODAY.strftime("%Y%m%d")}, timeout=30).json()
        for g in (e.get("group") or []):
            if g.get("title") in ("자금의사용목적", "증권의종류", "일반사항"):
                print(f"  [주요정보 {g['title']}]", [{k: v for k, v in x.items() if k not in ('corp_cls', 'corp_code', 'corp_name')}
                                                  for x in (g.get('list') or [])][:4])


if __name__ == "__main__":
    if not KEY:
        print("DART_API_KEY 없음")
        sys.exit(0)
    main()
