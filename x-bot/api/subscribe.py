"""GET /api/subscribe?key=<POLL_SECRET> — X Activity API 구독 생성 (신형 규격).

확인된 규격: POST /2/activity/subscriptions
  body {"event_type": "...", "filter": {"user_id": "<숫자ID>"}, "webhook_id": "...", "tag": "..."}
  인증: OAuth 1.0a 사용자 컨텍스트 (OAuth 2.0 사용자 토큰은 알려진 403 버그 — 폴백으로만 시도)
멘션 이벤트 타입 문자열은 문서에 없어 후보를 차례로 시도하고,
X 에러 응답(유효값 안내)을 그대로 노출해 확정한다.
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

from lib import oauth2
from lib.xclient import _oauth_header

API = "https://api.x.com/2"

EVENT_CANDIDATES = ["post.mention.create", "post.mention_create",
                    "mention.create", "post.mention"]


def _oauth1(method, url, body=None):
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
    return requests.request(method, url, json=body, headers=headers, timeout=20)


def _rec(label, r, body=None):
    try:
        resp = r.json()
    except ValueError:
        resp = r.text[:400]
    return {"step": label, "body": body, "http": r.status_code, "resp": resp}


def run():
    steps = []
    # ① 봇 계정 숫자 ID (filter.user_id 용)
    r = _oauth1("GET", f"{API}/users/me")
    steps.append(_rec("users_me(oauth1)", r))
    user_id = None
    if r.ok:
        user_id = (r.json().get("data") or {}).get("id")
    if not user_id:
        tok = oauth2.user_token()
        if tok:
            r = requests.get(f"{API}/users/me",
                             headers={"Authorization": f"Bearer {tok}"}, timeout=15)
            steps.append(_rec("users_me(oauth2)", r))
            if r.ok:
                user_id = (r.json().get("data") or {}).get("id")
    if not user_id:
        return {"ok": False, "reason": "봇 계정 user_id 조회 실패", "steps": steps}

    hook_id = os.environ.get("X_WEBHOOK_ID", "2076314919981436928")

    # ② 기존 구독 목록
    r = _oauth1("GET", f"{API}/activity/subscriptions")
    steps.append(_rec("list_subscriptions(oauth1)", r))

    # ③ 구독 생성 — 이벤트 타입 후보 × 인증(OAuth1 → OAuth2 폴백)
    for ev in EVENT_CANDIDATES:
        body = {"event_type": ev, "filter": {"user_id": str(user_id)},
                "webhook_id": hook_id, "tag": "kosai-mention-bot"}
        r = _oauth1("POST", f"{API}/activity/subscriptions", body)
        steps.append(_rec(f"create(oauth1,{ev})", r, body))
        if 200 <= r.status_code < 300:
            return {"ok": True, "event_type": ev, "user_id": user_id,
                    "webhook_id": hook_id, "steps": steps}
        # event_type이 문제라는 응답이면 다음 후보로, 아니면(권한 등) OAuth2도 시도
        txt = r.text.lower()
        if "event_type" in txt or "event type" in txt:
            continue
        tok = oauth2.user_token()
        if tok:
            r2 = requests.post(f"{API}/activity/subscriptions", json=body,
                               headers={"Authorization": f"Bearer {tok}",
                                        "Content-Type": "application/json"}, timeout=20)
            steps.append(_rec(f"create(oauth2,{ev})", r2, body))
            if 200 <= r2.status_code < 300:
                return {"ok": True, "event_type": ev, "user_id": user_id,
                        "webhook_id": hook_id, "steps": steps}
    return {"ok": False, "user_id": user_id, "webhook_id": hook_id, "steps": steps}


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
