"""GET /api/health — 상태 점검(비밀키 불필요). 대기열·체크포인트만 노출."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        info = {"ok": True}
        try:
            from lib import store
            info["pending"] = store.jobs_len()
            info["checkpoint"] = store.get_checkpoint()
        except Exception as e:
            info["store_error"] = str(e)
        for k in ("APIFY_TOKEN", "ANTHROPIC_API_KEY", "X_API_KEY", "X_ACCESS_TOKEN",
                  "UPSTASH_REDIS_REST_URL", "BOT_HANDLE"):
            info[k] = "set" if os.environ.get(k) else "MISSING"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(info).encode())
