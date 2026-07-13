"""GET /api/status?key=<POLL_SECRET> — 읽기 전용 진단.

① X 웹훅 목록(valid 여부) ② 구독 목록 ③ 자가진단: 우리 /api/webhook 에
합성 이벤트를 POST해 Redis 기록 경로가 살아있는지 확인(부작용 없음 — 멘션 0건).
어디서 막혔는지(‘X가 배달을 안 함’ vs ‘우리 핸들러가 죽음’)를 가른다.
"""
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from lib import store
from lib.xclient import _oauth_header

API = "https://api.x.com/2"


def _oauth1_get(url):
    oauth = {
        "oauth_consumer_key": os.environ["X_API_KEY"],
        "oauth_token": os.environ["X_ACCESS_TOKEN"],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    r = requests.get(url, headers={"Authorization": _oauth_header("GET", url, oauth)},
                     timeout=15)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:300]


def run(host):
    out = {}
    out["webhooks"] = dict(zip(("http", "resp"), _oauth1_get(f"{API}/webhooks")))
    out["subscriptions"] = dict(zip(("http", "resp"),
                                    _oauth1_get(f"{API}/activity/subscriptions")))

    # 자가진단 — 합성 이벤트로 핸들러+Redis 기록 확인(멘션 0건이라 답글 안 나감)
    before = store.get("debug:last_event_at")
    try:
        requests.post(f"https://{host}/api/webhook",
                      json={"selftest": True, "tweet_create_events": []},
                      headers={"content-type": "application/json"}, timeout=8)
    except Exception as e:
        out["selftest_post_error"] = str(e)
    time.sleep(1)
    after = store.get("debug:last_event_at")
    out["selftest"] = {"before": before, "after": after,
                       "handler_ok": bool(after and after != before)}
    out["last_event_at"] = after
    out["last_parsed"] = store.get("debug:last_parsed")
    return out


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        try:
            out = run(self.headers.get("host", ""))
            code, body = 200, json.dumps(out, ensure_ascii=False, indent=1)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())
