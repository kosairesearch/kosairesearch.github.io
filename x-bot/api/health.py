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
            # 웹훅 디버깅 — 마지막 수신 이벤트 시각/파싱 결과/원문(4KB 한도)
            info["last_event_at"] = store.get("debug:last_event_at")
            info["last_event_parsed"] = store.get("debug:last_parsed")
            info["last_event"] = store.get("debug:last_event")
        except Exception as e:
            info["store_error"] = str(e)
        for k in ("APIFY_TOKEN", "ANTHROPIC_API_KEY", "X_API_KEY", "X_ACCESS_TOKEN",
                  "UPSTASH_REDIS_REST_URL", "BOT_HANDLE"):
            info[k] = "set" if os.environ.get(k) else "MISSING"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(info).encode())
