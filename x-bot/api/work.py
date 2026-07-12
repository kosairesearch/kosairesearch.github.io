"""GET /api/work — 대기열에서 멘션 1건을 꺼내 생성·게시. 남으면 자기연쇄.

한 번에 1건만 처리해 함수 타임아웃(maxDuration) 안에 안전하게 끝낸다.
poll이 깨우고, 처리 후 큐가 남았으면 다시 자신을 깨운다. 크론이 백스톱.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lib import store, pipeline, kick


def run():
    job = store.pop_job()
    if not job:
        return {"processed": 0, "pending": 0}
    logs = []
    result = pipeline.process_mention(job, log=logs.append)
    remaining = store.jobs_len()
    if remaining:
        kick.kick("/api/work")                   # 다음 건 처리
    return {"processed": 1, "pending": remaining, "result": result, "log": logs}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        try:
            out = run()
            code, body = 200, json.dumps(out, ensure_ascii=False)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())
