#!/usr/bin/env python3
"""네이버 수집 요청(scripts/naver_indexnow.py)이 정한 대로만 보내는가.

종목 페이지 주소가 바뀐 뒤(2026-10-03) 네이버 검색 방문이 줄어, 사이트맵의 종목 페이지를 네이버에 한 번에
알리는 수동 작업을 만들었다(2026-10-26). 같은 주소를 매일 되풀이해 보내면 안 되고(CLAUDE.md '네이버 검색'),
사이트맵에 없는 주소(색인 제외 종목 · 다른 페이지)를 보내도 안 된다. 진짜 네이버 대신 로컬 서버로 받아 본다.

  ① 사이트맵에서 종목 페이지(한국어 · 영어)만 고른다 — 다른 페이지 · 다른 사이트 · 겹친 주소는 뺀다
  ② 열쇠 파일이 루트에 있고 내용이 열쇠와 같다
  ③ 보내는 모양 — host · key · keyLocation · urlList 와 지금 사이트맵의 종목 페이지 전부
  ④ 한 번에 10,000개를 넘기지 않고 나눠 보낸다
  ⑤ --send 없이는 보내지 않는다 · 예약 실행에서는 보내지 않는다
  ⑥ 거절(403) · 닿지 못함이면 실패로 끝난다
  ⑦ 작업 흐름에 예약이 없다

  실행:  python3 scripts/tests/naver_indexnow_test.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import naver_indexnow as N  # noqa: E402

PASS = FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}" + (f"\n      {detail}" if detail else ""))


class Naver(BaseHTTPRequestHandler):
    """받은 요청을 쌓아 두고 정해 둔 코드로 답하는 가짜 네이버."""
    got, code = [], 200

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        Naver.got.append((self.headers.get("Content-Type"), json.loads(self.rfile.read(n))))
        self.send_response(Naver.code)
        self.end_headers()

    def log_message(self, *a):
        pass


srv = HTTPServer(("127.0.0.1", 0), Naver)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = f"http://127.0.0.1:{srv.server_port}/indexnow"


def run(*args, event=None, endpoint=URL):
    env = dict(os.environ, NAVER_INDEXNOW_URL=endpoint)
    env.pop("GITHUB_EVENT_NAME", None)
    if event:
        env["GITHUB_EVENT_NAME"] = event
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "naver_indexnow.py"), *args],
                          cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)


print("── ① 사이트맵에서 종목 페이지만 고른다 ──")
with tempfile.TemporaryDirectory() as d:
    sm = Path(d) / "sitemap.xml"
    sm.write_text("""<?xml version="1.0" encoding="UTF-8"?><urlset>
<url><loc>https://kosai.kr/</loc></url>
<url><loc>https://kosai.kr/stock/005930.html</loc></url>
<url><loc>https://kosai.kr/en/stock/005930.html</loc></url>
<url><loc>https://kosai.kr/stock/0158S0.html</loc></url>
<url><loc>https://kosai.kr/stock/005930.html</loc></url>
<url><loc>https://kosai.kr/stock.html?ticker=005930</loc></url>
<url><loc>https://kosai.kr/r/005930.html</loc></url>
<url><loc>https://kosai.kr/industry.html?sector=%ED%86%B5%EC%8B%A0</loc></url>
<url><loc>https://example.com/stock/005930.html</loc></url>
</urlset>""", encoding="utf-8")
    got = N.stock_urls(sm)
ok("종목 페이지 셋만(한국어 둘 · 영어 하나, 겹친 주소 한 번)",
   got == ["https://kosai.kr/stock/005930.html", "https://kosai.kr/en/stock/005930.html",
           "https://kosai.kr/stock/0158S0.html"], got)
real = N.stock_urls()
loc = (ROOT / "sitemap.xml").read_text(encoding="utf-8").count("<loc>https://kosai.kr/")
ok(f"지금 사이트맵의 종목 페이지 {len(real):,}개 · 한국어와 영어가 같은 수",
   real and sum("/en/stock/" in u for u in real) * 2 == len(real), len(real))
ok("사이트맵의 다른 페이지는 고르지 않는다", 0 < len(real) < loc, f"{len(real)} / {loc}")

print("\n── ② 열쇠 파일 ──")
ok("루트에 열쇠 파일이 있고 내용이 열쇠와 같다", N.key_ok())
with tempfile.TemporaryDirectory() as d:
    (Path(d) / f"{N.KEY}.txt").write_text("다른 값", encoding="utf-8")
    ok("내용이 다르면 알아챈다", not N.key_ok(d))

print("\n── ③ 보내는 모양 ──")
Naver.got, Naver.code = [], 200
r = run("--send")
ok("보내고 성공으로 끝난다", r.returncode == 0, r.stdout + r.stderr)
ok("한 번에 보낸다(10,000개 안쪽)", len(Naver.got) == 1, len(Naver.got))
if Naver.got:
    ctype, body = Naver.got[0]
    ok("JSON 으로 보낸다", (ctype or "").startswith("application/json"), ctype)
    ok("host · key · keyLocation 이 맞다",
       body.get("host") == "kosai.kr" and body.get("key") == N.KEY
       and body.get("keyLocation") == f"https://kosai.kr/{N.KEY}.txt", {k: body.get(k) for k in ("host", "key", "keyLocation")})
    ok("지금 사이트맵의 종목 페이지를 빠짐없이 보낸다", body.get("urlList") == real, len(body.get("urlList") or []))
ok("기록에는 보낸 수와 응답 코드만 찍는다",
   "200 받음" in r.stdout and "https://" not in r.stdout, r.stdout)

print("\n── ④ 10,000개를 넘기면 나눠 보낸다 ──")
Naver.got = []
old, N.BATCH = N.BATCH, 10
codes = N.send([f"https://kosai.kr/stock/{i:06d}.html" for i in range(25)], endpoint=URL)
N.BATCH = old
ok("25개를 10 · 10 · 5 로 세 번", [n for n, _ in codes] == [10, 10, 5] and len(Naver.got) == 3, codes)
ok("실제 한도는 네이버 안내대로 10,000개", N.BATCH == 10000, N.BATCH)

print("\n── ⑤ 보내지 않아야 할 때 ──")
Naver.got = []
r = run()
ok("--send 없이는 보내지 않는다", r.returncode == 0 and not Naver.got and "보내지 않고" in r.stdout, r.stdout)
r = run("--send", event="schedule")
ok("예약 실행에서는 보내지 않고 멈춘다", r.returncode == 1 and not Naver.got, r.stdout)

print("\n── ⑥ 거절 · 닿지 못함은 실패 ──")
Naver.got, Naver.code = [], 403
r = run("--send")
ok("403 이면 실패로 끝난다", r.returncode == 1 and "403" in r.stdout, r.stdout)
Naver.code = 200
r = run("--send", endpoint="http://127.0.0.1:9/indexnow")
ok("네이버에 닿지 못하면 실패로 끝난다", r.returncode == 1 and "닿지 못했다" in r.stdout, r.stdout + r.stderr)

print("\n── ⑦ 작업 흐름 ──")
wf = yaml.safe_load((ROOT / ".github" / "workflows" / "naver_indexnow.yml").read_text(encoding="utf-8"))
on = wf.get(True) or wf.get("on") or {}
ok("손으로만 돌린다(예약 없음)", set(on) == {"workflow_dispatch"}, list(on))
ok("기본값은 보내지 않음", on["workflow_dispatch"]["inputs"]["send"]["default"] is False)

srv.shutdown()
print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
