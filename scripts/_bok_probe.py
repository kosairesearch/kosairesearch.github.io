#!/usr/bin/env python3
"""한국은행 금통위 일정의 '진짜 주소'를 찾는다 — 일회성 조사.

listYear.do 는 472KB 가 열리는데 날짜가 없다. 화면에서 그려진다는 뜻이고,
그렇다면 그 목록을 실제로 주는 주소가 어딘가 있다. 페이지 안의 스크립트가
그 주소를 들고 있을 것이므로 훑어서 찾는다.

찾으면 여기에 적어 두고 이 파일은 지운다.
"""
import re
import sys

import requests

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                     " (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"),
      "Accept-Language": "ko-KR,ko;q=0.9"}
BASE = "https://www.bok.or.kr"
PAGES = [
    ("금통위 목록(국문)", f"{BASE}/portal/singl/crncyPolicyDrcMtg/listYear.do?mtgSe=A&menuNo=200755"),
    ("통화정책 첫화면",    f"{BASE}/portal/main/contents.do?menuNo=200755"),
]


def show(name, url):
    print(f"\n{'='*74}\n{name}\n{url}\n{'='*74}")
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except Exception as e:
        print(f"  실패: {type(e).__name__}: {e}")
        return
    h = r.text
    print(f"  상태 {r.status_code} · {len(h):,}바이트 · {r.headers.get('content-type','')}")

    # ① 페이지 안의 .do 주소 — 목록을 주는 것이 여기 섞여 있을 것이다
    dos = sorted({m.group(0) for m in re.finditer(r"[\w/]*[A-Za-z]\w*\.do", h)})
    hit = [d for d in dos if any(k in d.lower() for k in
                                 ("mtg", "list", "ajax", "json", "search", "sched"))]
    print(f"\n  · .do 주소 {len(dos)}개 · 그중 목록처럼 보이는 것 {len(hit)}개")
    for d in hit[:30]:
        print(f"      {d}")

    # ② 목록을 불러오는 자바스크립트 호출
    for pat, label in ((r"\$\.ajax\s*\(", "$.ajax"), (r"\$\.post\s*\(", "$.post"),
                       (r"\$\.get(?:JSON)?\s*\(", "$.get"), (r"\bfetch\s*\(", "fetch"),
                       (r"XMLHttpRequest", "XHR"), (r"axios", "axios")):
        n = len(re.findall(pat, h))
        if n:
            print(f"  · {label} {n}곳")

    # ③ 스크립트 안에 박힌 날짜 — 화면이 아니라 자료로 들어 있을 수도 있다
    for pat, label in ((r"20\d\d[.\-/]\d{1,2}[.\-/]\d{1,2}", "yyyy.mm.dd"),
                       (r"20\d\d\d{4}", "yyyymmdd"),
                       (r"20\d\d년\s*\d{1,2}월\s*\d{1,2}일", "yyyy년 mm월 dd일")):
        got = sorted({m.group(0) for m in re.finditer(pat, h)})
        keep = [g for g in got if g.startswith(("2026", "2027"))]
        if keep:
            print(f"  · {label} {len(keep)}개: {keep[:12]}")

    # ④ '통화정책방향' 주변에 무엇이 있나
    for m in list(re.finditer(r"통화정책방향", h))[:3]:
        a, b = max(0, m.start() - 130), m.end() + 130
        near = re.sub(r"\s+", " ", h[a:b])
        print(f"  · 주변: …{near}…")


for name, url in PAGES:
    show(name, url)

# ⑤ 흔히 쓰는 목록 주소를 직접 두드려 본다
print(f"\n{'='*74}\n짐작되는 목록 주소 직접 두드리기\n{'='*74}")
for path in ("/portal/singl/crncyPolicyDrcMtg/listYearAjax.do?mtgSe=A",
             "/portal/singl/crncyPolicyDrcMtg/list.do?mtgSe=A&menuNo=200755",
             "/portal/singl/crncyPolicyDrcMtg/listYear.json?mtgSe=A",
             "/portal/singl/crncyPolicyDrcMtg/selectListYear.do?mtgSe=A",
             "/portal/singl/crncyPolicyDrcMtg/mtgScheduleList.do?mtgSe=A"):
    try:
        r = requests.get(BASE + path, headers=UA, timeout=20)
        d = sorted({m.group(0) for m in re.finditer(r"20\d\d[.\-/]\d{1,2}[.\-/]\d{1,2}", r.text)})
        d = [x for x in d if x.startswith(("2026", "2027"))]
        print(f"  {r.status_code}  {len(r.text):>8,}B  날짜 {len(d):>2}개  {path}")
        if d:
            print(f"          {d[:12]}")
    except Exception as e:
        print(f"  실패  {type(e).__name__}  {path}")
sys.exit(0)
