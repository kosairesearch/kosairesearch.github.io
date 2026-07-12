"""OAuth 2.0 승인 1회용 엔드포인트 — 브라우저로 열어 X 승인 → 토큰 저장 → 구독까지.

① GET /api/oauth2?key=<POLL_SECRET>  → X 승인 페이지로 리다이렉트 (PKCE)
② X가 승인 후 이 주소로 돌아오면(code 포함) 토큰 교환·저장 → 웹훅 구독 자동 시도
   → 결과 JSON 표시.
사전 조건: 콘솔 앱의 콜백 URI에 {APP_URL}/api/oauth2 등록,
Vercel 환경변수 X_CLIENT_ID / X_CLIENT_SECRET 설정.
"""
import json
import os
import secrets
import sys
from urllib.parse import urlencode, urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler

import requests

from lib import store, oauth2

API = "https://api.x.com/2"


def _redirect_uri():
    return os.environ.get("APP_URL", "").rstrip("/") + "/api/oauth2"


def try_subscribe(user_bearer):
    """앱 전용 토큰으로 웹훅을 찾고, 사용자 토큰으로 구독 생성."""
    steps = []
    r = requests.post("https://api.x.com/oauth2/token",
                      auth=(os.environ["X_API_KEY"], os.environ["X_API_SECRET"]),
                      data={"grant_type": "client_credentials"}, timeout=15)
    app_bearer = r.json().get("access_token") if r.ok else None
    steps.append({"step": "app_bearer", "http": r.status_code, "ok": bool(app_bearer)})

    hook_id = os.environ.get("X_WEBHOOK_ID", "")
    if app_bearer:
        r = requests.get(f"{API}/webhooks",
                         headers={"Authorization": f"Bearer {app_bearer}"}, timeout=15)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        steps.append({"step": "list_webhooks", "http": r.status_code, "resp": data})
        for h in (data.get("data") or []):
            if "/api/webhook" in (h.get("url") or ""):
                hook_id = h.get("id")
                break
    if not hook_id:
        return {"ok": False, "reason": "웹훅 id를 찾지 못함", "steps": steps}

    r = requests.post(f"{API}/account_activity/webhooks/{hook_id}/subscriptions/all",
                      headers={"Authorization": f"Bearer {user_bearer}"}, timeout=20)
    try:
        resp = r.json()
    except ValueError:
        resp = r.text[:300]
    steps.append({"step": "subscribe", "webhook_id": hook_id, "http": r.status_code, "resp": resp})
    ok = r.status_code in (200, 201, 204, 409)
    return {"ok": ok, "webhook_id": hook_id, "steps": steps}


class handler(BaseHTTPRequestHandler):
    def _out(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body.encode())

    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        code = q.get("code", [""])[0]

        if not code:
            # ① 승인 시작 — 키 확인 후 X 인가 페이지로 리다이렉트
            if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
                self._out(403, '{"error":"forbidden"}'); return
            if not os.environ.get("X_CLIENT_ID"):
                self._out(500, '{"error":"X_CLIENT_ID/X_CLIENT_SECRET 환경변수를 먼저 넣고 재배포"}'); return
            verifier = secrets.token_urlsafe(43)
            state = secrets.token_urlsafe(16)
            store.set("oauth2:verifier", verifier, ex=600)
            store.set("oauth2:state", state, ex=600)
            params = urlencode({
                "response_type": "code",
                "client_id": os.environ["X_CLIENT_ID"],
                "redirect_uri": _redirect_uri(),
                "scope": oauth2.SCOPES,
                "state": state,
                "code_challenge": verifier,
                "code_challenge_method": "plain",
            })
            self.send_response(302)
            self.send_header("Location", f"https://x.com/i/oauth2/authorize?{params}")
            self.end_headers()
            return

        # ② 콜백 — 토큰 교환 후 구독까지 자동 시도
        if q.get("state", [""])[0] != (store.get("oauth2:state") or ""):
            self._out(403, '{"error":"state 불일치 — 처음부터 다시 시도"}'); return
        http, tok = oauth2.exchange_code(code, _redirect_uri(),
                                         store.get("oauth2:verifier") or "")
        if http != 200:
            self._out(500, json.dumps({"step": "token_exchange", "http": http,
                                       "resp": tok}, ensure_ascii=False)); return
        result = try_subscribe(tok["access_token"])
        result["token_saved"] = True
        self._out(200, json.dumps(result, ensure_ascii=False, indent=1))
