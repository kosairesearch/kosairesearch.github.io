"""GET /api/subscribe?key=<POLL_SECRET> — 계정 이벤트 구독을 API로 직접 생성.

콘솔 UI의 '구독 만들기'가 OAuth 사용자 토큰을 요구하며 거부할 때의 우회 경로.
Vercel 환경변수의 OAuth1.0a 사용자 컨텍스트(액세스 토큰)로
POST /2/account_activity/webhooks/{id}/subscriptions/all 을 호출한다.
성공/실패와 X의 응답 원문을 그대로 보여준다(브라우저에서 열면 됨).
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

from lib.xclient import _oauth_header

API = "https://api.x.com/2"


def _call(method, url, body=None):
    oauth = {
        "oauth_consumer_key": os.environ["X_API_KEY"],
        "oauth_token": os.environ["X_ACCESS_TOKEN"],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    headers = {"Authorization": _oauth_header(method, url, oauth)}
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = requests.request(method, url, json=body, headers=headers, timeout=20)
    try:
        detail = r.json()
    except ValueError:
        detail = r.text[:500]
    return r.status_code, detail


def run():
    steps = []
    # ① 등록된 웹훅 목록에서 우리 URL 찾기
    code, hooks = _call("GET", f"{API}/webhooks")
    steps.append({"step": "list_webhooks", "http": code, "resp": hooks})
    hook_id = None
    target = (os.environ.get("APP_URL", "").rstrip("/") + "/api/webhook").lstrip("/")
    for h in (hooks.get("data") or []) if isinstance(hooks, dict) else []:
        if target and h.get("url", "").rstrip("/").endswith("/api/webhook"):
            hook_id = h.get("id")
            break
    if not hook_id:
        return {"ok": False, "reason": "웹훅을 찾지 못함 — 콘솔에서 웹훅 먼저 등록", "steps": steps}

    # ② 구독 생성 (OAuth1.0a 사용자 컨텍스트)
    code, resp = _call("POST", f"{API}/account_activity/webhooks/{hook_id}/subscriptions/all")
    steps.append({"step": "subscribe", "webhook_id": hook_id, "http": code, "resp": resp})
    ok = code in (200, 201, 204) or code == 409  # 409 = 이미 구독됨
    # ③ 구독 목록 확인
    code, subs = _call("GET", f"{API}/account_activity/webhooks/{hook_id}/subscriptions/all/list")
    steps.append({"step": "list_subscriptions", "http": code, "resp": subs})
    return {"ok": ok, "webhook_id": hook_id, "steps": steps}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        try:
            out = run()
            code, body = 200, json.dumps(out, ensure_ascii=False, indent=1)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())
