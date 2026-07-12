"""GET /api/poll — 외부 크론(1분)이 호출. 새 멘션 감지 → 큐 적재 → work 깨움.

무거운 생성·게시는 안 한다(타임아웃 회피). Apify 스크래핑 + 중복/체크포인트만.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lib import store, xclient, kick


def run():
    mentions = xclient.scrape_mentions(limit=25)
    checkpoint = store.get_checkpoint()
    newest = checkpoint
    queued = 0
    for m in mentions:
        if m["ts"] and m["ts"] <= checkpoint:
            continue
        if not store.mark_if_new(m["id"]):       # 이미 처리/예약됨
            newest = max(newest, m["ts"])
            continue
        store.push_job({"id": m["id"], "text": m["text"], "attempts": 0})
        queued += 1
        newest = max(newest, m["ts"])
    if newest > checkpoint:
        store.set_checkpoint(newest)
    if queued:
        kick.kick("/api/work")                   # 처리 시작(비동기)
    return {"scraped": len(mentions), "queued": queued, "pending": store.jobs_len()}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        try:
            out = run()
            code, body = 200, json.dumps(out)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())
