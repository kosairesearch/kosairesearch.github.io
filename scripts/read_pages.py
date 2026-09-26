#!/usr/bin/env python3
"""러너에서 웹 페이지를 읽어 글만 로그에 찍는다 — 임시 도구.

샌드박스는 네이버 개발자센터(developers.naver.com)에 닿지 않는다. 러너는 닿는다.
약관 전문을 읽으려고 잠깐 둔다. 돈이 들지 않는다(API 호출 없음).

    python3 scripts/read_pages.py URL [URL ...] [--follow 정규식] [--max 30]

--follow 를 주면 첫 페이지들에 걸린 같은 사이트 링크 중 정규식에 맞는 것을
한 단계 더 읽는다.
"""
import argparse
import html
import re
import sys
import urllib.parse

import requests

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def get(url):
    r = requests.get(url, headers=UA, timeout=25)
    ctype = r.headers.get("content-type", "")
    if "charset" not in ctype.lower():
        r.encoding = r.apparent_encoding or "utf-8"
    return r, ctype


def links_of(base, raw):
    out = []
    for m in re.finditer(r"""href\s*=\s*["']([^"'#]+)""", raw):
        u = urllib.parse.urljoin(base, html.unescape(m.group(1)).strip())
        if u.startswith("http") and u not in out:
            out.append(u)
    return out


def text_of(raw):
    try:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(raw, "lxml")
        for t in s(["script", "style", "noscript"]):
            t.decompose()
        txt = s.get_text("\n")
    except Exception:
        txt = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", raw, flags=re.S)
        txt = html.unescape(re.sub(r"<[^>]+>", "\n", txt))
    lines = [re.sub(r"[ \t ]+", " ", l).strip() for l in txt.splitlines()]
    return "\n".join(l for l in lines if l)


def show(url):
    print("\n" + "=" * 100)
    print(f"■ {url}")
    try:
        r, ctype = get(url)
    except Exception as e:
        print(f"  요청 실패: {type(e).__name__} {str(e)[:120]}")
        return None
    print(f"  {r.status_code} · {len(r.content):,}바이트 · {ctype[:50]} · 최종 {r.url}")
    raw = r.text
    body = text_of(raw) if "html" in ctype.lower() or raw.lstrip().startswith("<") else raw
    print("-" * 100)
    print(body)
    if len(body) < 400:
        # 글이 거의 없으면 스크립트로 그리는 페이지다 — 불러오는 주소를 찾으려고 원문 앞부분을 본다
        print("-" * 40 + " (글이 거의 없다 — 원문 앞부분)")
        print(raw[:4000])
        for s in re.findall(r"""<script[^>]+src=["']([^"']+)""", raw)[:30]:
            print("  script:", urllib.parse.urljoin(url, s))
    return r.url, raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--follow", default="")
    ap.add_argument("--max", type=int, default=30)
    a = ap.parse_args()

    seen, queue = set(), []
    for u in a.urls:
        seen.add(u)
        got = show(u)
        if got and a.follow:
            final, raw = got
            host = urllib.parse.urlparse(final).netloc
            for l in links_of(final, raw):
                if (urllib.parse.urlparse(l).netloc == host and re.search(a.follow, l)
                        and l not in seen and l not in queue):
                    queue.append(l)
    if a.follow:
        print("\n" + "=" * 100)
        print(f"■ 따라갈 링크 {len(queue)}개 (최대 {a.max}개 읽음)")
        for l in queue:
            print("  ·", l)
    for l in queue[:a.max]:
        seen.add(l)
        show(l)
    return 0


if __name__ == "__main__":
    sys.exit(main())
