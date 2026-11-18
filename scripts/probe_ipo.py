#!/usr/bin/env python3
"""(임시 · 작업 가지에서만) 증권신고서 · 투자설명서의 요약재무정보 · 자금의 사용목적 표를 행 단위로 찍는다(돈 안 듦 · 저장 · 커밋 없음).

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
NAMES = ["하나에어로다이내믹스", "에이엘로봇", "유캐스트", "엠비디", "옵토닉스", "래블업", "이에스티", "동원파츠",
         "바로팜", "넥스아이", "영광와이케이엠씨"]
TODAY = datetime.date.today()
CELL = re.compile(r"<(TD|TH|TE|TU)\b[^>]*>(.*?)</\1>", re.S)


def hr(t):
    print("\n" + "=" * 8 + " " + t + " " + "=" * 8, flush=True)


def text_of(x):
    t = re.sub(r"<[^>]+>", " ", x)
    t = re.sub(r"&nbsp;|&#160;", " ", t).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", t).strip()


def dump_section(doc, start, end, max_lines):
    """start~end 사이의 글(P)과 표(TABLE)를 차례대로 찍는다."""
    seg = doc[start:end]
    n = 0
    pos = 0
    for m in re.finditer(r"<TABLE\b.*?</TABLE>", seg, re.S):
        pre = text_of(seg[pos:m.start()])
        if pre:
            print("   [글]", pre[:300])
            n += 1
        for tr in re.findall(r"<TR\b.*?</TR>", m.group(0), re.S):
            cells = [text_of(c[1]) for c in CELL.findall(tr)]
            print("   |", " | ".join(cells)[:400])
            n += 1
            if n >= max_lines:
                print("   … (줄 한도)")
                return
        print("   [표 끝]")
        pos = m.end()
    tail = text_of(seg[pos:])
    if tail:
        print("   [글]", tail[:300])


def main():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    import dart_reader
    dart = dart_reader.reader(KEY)
    cc = dart.corp_codes
    for nm in NAMES:
        hr(nm)
        hits = cc[cc["corp_name"] == nm]
        if hits.empty:
            print("회사 번호 없음")
            continue
        rows, code = [], None
        for _, h in hits.iterrows():
            j = requests.get("https://opendart.fss.or.kr/api/list.json", params={
                "crtfc_key": KEY, "corp_code": h["corp_code"],
                "bgn_de": (TODAY - datetime.timedelta(days=200)).strftime("%Y%m%d"),
                "end_de": TODAY.strftime("%Y%m%d"), "page_count": 100}, timeout=30).json()
            rr = [r for r in (j.get("list") or [])
                  if "투자설명서" in r["report_nm"] or "증권신고서(지분증권)" in r["report_nm"]]
            print("회사 번호", h["corp_code"], "종목코드", repr(h["stock_code"]), "공모 서류", len(rr),
                  "· 정기보고서", [r["report_nm"] for r in (j.get("list") or [])
                                  if re.search(r"(분기|반기|사업)보고서", r["report_nm"])][:3])
            if rr and not rows:
                rows, code = rr, h["corp_code"]
        if not rows:
            print("  공모 서류 없음")
            continue
        pick = max(rows, key=lambda r: r["rcept_no"])
        print("  → 읽을 문서(가장 최근):", pick["rcept_no"], pick["report_nm"])
        z = requests.get("https://opendart.fss.or.kr/api/document.xml",
                         params={"crtfc_key": KEY, "rcept_no": pick["rcept_no"]}, timeout=90)
        try:
            zf = zipfile.ZipFile(io.BytesIO(z.content))
        except zipfile.BadZipFile:
            print("  zip 아님:", z.content[:200])
            continue
        names = [i.filename for i in zf.infolist()]
        print("  파일", [(i.filename, i.file_size) for i in zf.infolist()][:8])
        main_name = f"{pick['rcept_no']}.xml" if f"{pick['rcept_no']}.xml" in names else \
            max(zf.infolist(), key=lambda i: i.file_size).filename
        raw = zf.read(main_name)
        doc = raw.decode("utf-8", "replace")
        if doc.count("�") > 50:
            doc = raw.decode("euc-kr", "replace")
        titles = [(m.start(), text_of(m.group(1))) for m in re.finditer(r"<TITLE\b[^>]*>(.*?)</TITLE>", doc, re.S)]
        print("  제목 수", len(titles), "· 정정 대비표 있음" if "정정사항" in doc[:200000] else "")
        print("  재무 · 자금 관련 제목:", [t for _, t in titles if re.search(r"재무|자금|요약", t)][:20])
        for i, (pos, t) in enumerate(titles):
            if "요약" in t and "재무" in t:
                end = titles[i + 1][0] if i + 1 < len(titles) else len(doc)
                print(f"  ── [{t}] {pos}~{end}")
                dump_section(doc, pos, end, 110)
        for i, (pos, t) in enumerate(titles):
            if re.search(r"자금의\s*사용\s*목적", t):
                end = titles[i + 1][0] if i + 1 < len(titles) else len(doc)
                print(f"  ── [{t}] {pos}~{end}")
                dump_section(doc, pos, end, 40)
                break


if __name__ == "__main__":
    if not KEY:
        print("DART_API_KEY 없음")
        sys.exit(0)
    main()
