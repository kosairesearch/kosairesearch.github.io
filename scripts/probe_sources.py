#!/usr/bin/env python3
"""브리핑 재료 공급처 진단 — 무엇이 살아 있고 무엇이 죽었는지 한 번에 본다.

왜 있나. 9/18 에 네이버가 옛 '투자자별 매매동향' 주소를 닫았다(410). 브리핑은
"재료 하나 없어도 발행한다" 라서 겉으로는 멀쩡했고, 외국인·기관 수급이 나흘째
빠진 것을 9/22 에야 알았다. 이 저장소가 도는 곳(GitHub Actions)과 사람이 앉은
곳(개발 샌드박스)은 네트워크가 달라서, 주소가 살았는지는 러너에서 직접 찔러
봐야 한다. 이 스크립트는 그 '찔러 보기'다 — 돈이 들지 않는다(API 호출 없음).

    Actions → 📰 브리핑 다시 써 보기 → probe 켜기
    python3 scripts/probe_sources.py            # 러너에서

세 가지를 한다.
  1. 지수 — 네이버 모바일 지수 API 의 원본 행을 그대로 보여 준다(필드 이름·
     날짜·부호 규칙을 확인하려고).
  2. 수급 — 후보 주소들을 차례로 찔러 상태·크기·JSON 뼈대를 보여 준다.
  3. 발견 — 네이버 새 금융 사이트(React)의 스크립트를 내려받아 'investor' 가
     들어간 API 경로를 긁어낸다. 추측 대신 실제 주소를 찾는다.
"""
import json
import re
import sys

import requests

TIMEOUT = 20
WEB_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
MOB_UA = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"),
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json",
}
DAUM = {**WEB_UA, "Referer": "https://finance.daum.net/", "Accept": "application/json"}


def shape(o, depth=0):
    if depth > 3:
        return "…"
    if isinstance(o, dict):
        return "{" + ", ".join(f"{k}:{shape(v, depth + 1)}" for k, v in list(o.items())[:14]) + "}"
    if isinstance(o, list):
        return f"[{len(o)}×{shape(o[0], depth + 1) if o else ''}]"
    return type(o).__name__


def get(url, headers):
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
    except Exception as e:
        return None, f"요청 실패 {type(e).__name__} {str(e)[:80]}"
    return r, f"{r.status_code} · {len(r.content):,}바이트 · {r.headers.get('content-type', '')[:40]}"


def show(name, url, headers, raw=0):
    r, info = get(url, headers)
    print(f"\n[{name}] {url}\n   {info}")
    if r is None or r.status_code != 200:
        return None
    body = r.text
    try:
        j = r.json()
    except Exception:
        j = None
    if j is not None:
        print(f"   JSON 뼈대: {shape(j)}")
        if raw:
            print("   원본(앞부분): " + json.dumps(j, ensure_ascii=False)[:raw])
        return j
    txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>", "", body, flags=re.S))
    print(f"   HTML · <td> {txt.count('<td')}개 · 앞부분: {txt[:160]!r}")
    return body


def main():
    print("■ 1. 지수 — 네이버 모바일 지수 API (야후가 하루 늦는 날의 예비)")
    for code in ("KOSPI", "KOSDAQ"):
        show(f"index/{code}/price", f"https://m.stock.naver.com/api/index/{code}/price?pageSize=5",
             MOB_UA, raw=700)
        show(f"index/{code}/basic", f"https://m.stock.naver.com/api/index/{code}/basic",
             MOB_UA, raw=500)

    print("\n■ 2. 수급 — 후보 주소")
    cands = [
        ("naver mob investorTrend", "https://m.stock.naver.com/api/index/KOSPI/investorTrend", MOB_UA),
        ("naver mob investors", "https://m.stock.naver.com/api/index/KOSPI/investors?pageSize=5", MOB_UA),
        ("naver mob investor", "https://m.stock.naver.com/api/index/KOSPI/investor?pageSize=5", MOB_UA),
        ("naver mob investorTrendDaily", "https://m.stock.naver.com/api/index/KOSPI/investorTrendDaily?pageSize=5", MOB_UA),
        ("naver mob trend", "https://m.stock.naver.com/api/index/KOSPI/trend?pageSize=5", MOB_UA),
        ("naver mob investorDealTrend", "https://m.stock.naver.com/api/index/KOSPI/investorDealTrend?pageSize=5", MOB_UA),
        ("naver api.stock", "https://api.stock.naver.com/index/KOSPI/investorTrend", MOB_UA),
        ("naver finance api", "https://finance.naver.com/api/sise/investorDealTrendDay?sosok=01&page=1", WEB_UA),
        ("daum investor/days", "https://finance.daum.net/api/investor/days?market=KOSPI&perPage=5&page=1&fieldName=tradeDate&order=desc", DAUM),
        ("daum market index", "https://finance.daum.net/api/market_index/days?market=KOSPI&perPage=3&page=1", DAUM),
    ]
    for name, url, h in cands:
        show(name, url, h, raw=500)

    print("\n■ 3. 발견 — 새 네이버 금융 사이트 스크립트에서 API 경로 긁기")
    found = set()
    for page in ("https://finance.naver.com/market/stock/kr/index",
                 "https://finance.naver.com/market/stock/kr/investor",
                 "https://finance.naver.com/sise/sise_index.naver?code=KOSPI"):
        r, info = get(page, WEB_UA)
        print(f"\n[페이지] {page}\n   {info}")
        if r is None or r.status_code != 200:
            continue
        html = r.text
        for m in re.finditer(r"https?://[^\s\"'<>]*api[^\s\"'<>]*", html):
            found.add(m.group(0)[:160])
        srcs = re.findall(r"<script[^>]+src=[\"']([^\"']+)[\"']", html)
        print(f"   스크립트 {len(srcs)}개")
        total = 0
        for s in srcs[:25]:
            u = s if s.startswith("http") else ("https://finance.naver.com" + s if s.startswith("/") else s)
            rr, _ = get(u, WEB_UA)
            if rr is None or rr.status_code != 200:
                continue
            js = rr.text
            total += len(js)
            for m in re.finditer(r"[\"'`](/?(?:api|[a-z0-9.-]*\.naver\.com)[^\"'`\s]{0,120}(?:investor|Investor|deal|Deal|trend|Trend)[^\"'`\s]{0,80})[\"'`]", js):
                found.add(m.group(1)[:200])
            for m in re.finditer(r"[\"'`]((?:https?:)?//[a-z0-9.-]*stock\.naver\.com/api[^\"'`\s]{0,120})[\"'`]", js):
                found.add(m.group(1)[:200])
            if total > 12_000_000:
                break
        print(f"   내려받은 스크립트 {total:,}바이트")
    print("\n   후보 경로:")
    for f in sorted(found):
        print("   ·", f)
    if not found:
        print("   (없음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
