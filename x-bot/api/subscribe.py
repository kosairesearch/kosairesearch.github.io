"""GET /api/subscribe?key=<POLL_SECRET> — 신형 구독 API 경로 진단 + 구독 생성 시도.

/api/oauth2 승인으로 저장된 OAuth 2.0 사용자 토큰을 사용해, 새 콘솔이 쓰는
구독 엔드포인트 후보들을 차례로 호출한다. X의 에러 응답(필수 필드 안내 등)을
그대로 보여줘서 올바른 규격을 역추적할 수 있게 한다. 2xx가 하나라도 나오면 성공.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

from lib import oauth2

API = "https://api.x.com/2"


def _req(method, url, bearer, body=None):
    headers = {"Authorization": f"Bearer {bearer}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    r = requests.request(method, url, json=body, headers=headers, timeout=20)
    try:
        resp = r.json()
    except ValueError:
        resp = r.text[:400]
    return {"method": method, "url": url.replace(API, ""), "body": body,
            "http": r.status_code, "resp": resp}


def run():
    steps = []
    # 앱 전용 토큰 — 웹훅 id 조회용
    r = requests.post("https://api.x.com/oauth2/token",
                      auth=(os.environ["X_API_KEY"], os.environ["X_API_SECRET"]),
                      data={"grant_type": "client_credentials"}, timeout=15)
    app_bearer = r.json().get("access_token") if r.ok else None
    hook_id = os.environ.get("X_WEBHOOK_ID", "")
    if app_bearer:
        s = _req("GET", f"{API}/webhooks", app_bearer)
        steps.append(s)
        for h in ((s["resp"] or {}).get("data") or []) if isinstance(s["resp"], dict) else []:
            if "/api/webhook" in (h.get("url") or ""):
                hook_id = h.get("id")

    user_tok = oauth2.user_token()
    if not user_tok:
        return {"ok": False, "reason": "사용자 토큰 없음 — /api/oauth2?key= 먼저 승인",
                "steps": steps}

    handle = os.environ.get("BOT_HANDLE", "kosai_x").lstrip("@")
    # 후보 엔드포인트 배터리 — 에러 메시지로 규격 역추적
    battery = [
        ("GET", f"{API}/account_activity/subscriptions", None),
        ("POST", f"{API}/account_activity/subscriptions",
         {"webhook_id": hook_id, "event_type": "post_mention_create"}),
        ("POST", f"{API}/account_activity/subscriptions",
         {"webhook_id": hook_id, "category": "post",
          "event_type": "post_mention_create", "user_handle": handle}),
        ("POST", f"{API}/webhooks/{hook_id}/subscriptions", {}),
        ("POST", f"{API}/account_activity/webhooks/{hook_id}/subscriptions/all", None),
    ]
    ok = False
    for method, url, body in battery:
        s = _req(method, url, user_tok, body)
        steps.append(s)
        if method == "POST" and 200 <= s["http"] < 300:
            ok = True
            break
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
