#!/usr/bin/env python3
"""네이버에 종목 페이지 주소를 한 번에 알린다(IndexNow · 수동).

왜 있나
  2026-10-03 종목 페이지 주소가 stock.html?ticker= · r/ 에서 stock/{종목코드}.html 로 바뀐 뒤,
  네이버 검색으로 들어온 방문이 10월 9일부터 개편 전의 절반 안팎으로 줄었다(2026-10-19 · 10-26 주간 보고).
  네이버가 새 주소를 빨리 수집하도록, 사이트맵의 종목 페이지(한국어 · 영어)를 한 번에 알린다.

언제 돌리나
  주소가 대량으로 새로 생겼을 때만, 손으로 한 번(Actions → 🔎 네이버 수집 요청). 같은 주소를 매일
  되풀이해 보내지 않는다 — 네이버 안내가 반복 요청은 필요 없고 남용은 제한된다고 한다(CLAUDE.md '네이버 검색').
  그래서 예약 실행(schedule)에서는 보내지 않고 멈춘다. 수집 · 색인을 보장하지는 않는다.

열쇠
  루트의 33884466dd252645f1cbf9b139d8da02.txt (내용 = 파일 이름). 공개해 두는 것이 원래 방식이라 비밀이 아니다.
  지우거나 내용을 바꾸면 알림이 거절된다(403).

  python3 scripts/naver_indexnow.py            # 몇 개를 보낼지만 찍는다(보내지 않음)
  python3 scripts/naver_indexnow.py --send     # 보낸다 — 보낸 주소 수와 응답 코드만 찍는다
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOST = "kosai.kr"
KEY = "33884466dd252645f1cbf9b139d8da02"
# 시험은 이 주소를 로컬 서버로 바꿔 보낸 내용을 받아 본다.
ENDPOINT = os.environ.get("NAVER_INDEXNOW_URL", "https://searchadvisor.naver.com/indexnow")
BATCH = 10000  # 네이버 안내 — 한 번에 최대 10,000개
STOCK = re.compile(r"^https://kosai\.kr/(?:en/)?stock/[0-9A-Z]{6}\.html$")
MEANING = {200: "받음", 202: "받음(열쇠 확인 중)", 400: "요청 형식 오류", 403: "열쇠 확인 실패",
           422: "이 사이트의 주소가 아니거나 열쇠와 맞지 않음", 429: "너무 자주 보냄"}


def key_ok(root=ROOT):
    f = Path(root) / f"{KEY}.txt"
    return f.is_file() and f.read_text(encoding="utf-8").strip() == KEY


def stock_urls(sitemap=None):
    """사이트맵의 종목 페이지만 — 색인 제외(noindex) 종목은 사이트맵에 없으므로 같이 빠진다."""
    text = Path(sitemap or ROOT / "sitemap.xml").read_text(encoding="utf-8")
    seen, out = set(), []
    for u in re.findall(r"<loc>([^<]+)</loc>", text):
        u = u.strip()
        if STOCK.match(u) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def payload(urls):
    return {"host": HOST, "key": KEY, "keyLocation": f"https://{HOST}/{KEY}.txt", "urlList": urls}


def send(urls, endpoint=None, timeout=60):
    """[(보낸 수, 응답 코드)] — 응답 본문은 찍지 않는다."""
    codes = []
    for i in range(0, len(urls), BATCH):
        part = urls[i:i + BATCH]
        req = urllib.request.Request(endpoint or ENDPOINT, method="POST",
                                     data=json.dumps(payload(part)).encode("utf-8"),
                                     headers={"Content-Type": "application/json; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                code = r.status
        except urllib.error.HTTPError as e:
            code = e.code
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  네이버에 닿지 못했다 — {type(e).__name__}: {e}")
            code = 0
        codes.append((len(part), code))
    return codes


def main(argv=None):
    ap = argparse.ArgumentParser(description="네이버에 종목 페이지 주소를 한 번에 알린다(IndexNow).")
    ap.add_argument("--send", action="store_true", help="실제로 보낸다(없으면 몇 개를 보낼지만 찍는다)")
    a = ap.parse_args(argv)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        print("예약 실행에서는 보내지 않는다 — 같은 주소를 되풀이해 보내지 않는다(CLAUDE.md '네이버 검색').")
        return 1
    if not key_ok():
        print(f"열쇠 파일({KEY}.txt)이 없거나 내용이 다르다 — 보내면 거절된다(403).")
        return 1
    urls = stock_urls()
    if not urls:
        print("사이트맵에 종목 페이지가 없다 — 보내지 않는다.")
        return 1
    en = sum(1 for u in urls if "/en/stock/" in u)
    print(f"보낼 주소 {len(urls):,}개 (한국어 {len(urls) - en:,} · 영어 {en:,}) · 한 번에 {BATCH:,}개까지")
    if not a.send:
        print("보내지 않고 확인만 했다 — 보내려면 --send")
        return 0
    good = True
    for n, code in send(urls):
        print(f"  {n:,}개 → {code} {MEANING.get(code, '알 수 없는 응답')}")
        good = good and code in (200, 202)
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())
