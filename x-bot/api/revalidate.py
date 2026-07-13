"""GET /api/revalidate?key=<POLL_SECRET> — 웹훅 유효성 확인 + 재검증(되살리기).

OAuth 2.0 앱 전용 토큰(client_credentials)으로:
① GET /2/webhooks  → 현재 valid 플래그 확인 (status가 OAuth1로 못 읽던 부분)
② PUT /2/webhooks/{id} → 수동 CRC 재검증 트리거(성공 시 204, valid 복구)
③ GET 재확인
웹훅이 401 이벤트 거부 등으로 무효화됐을 때 배달을 재개시킨다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests

API = "https://api.x.com/2"


def _app_bearer():
    r = requests.post("https://api.x.com/oauth2/token",
                      auth=(os.environ["X_API_KEY"], os.environ["X_API_SECRET"]),
                      data={"grant_type": "client_credentials"}, timeout=15)
    return r.json().get("access_token") if r.ok else None


def _get(url, bearer):
    r = requests.get(url, headers={"Authorization": f"Bearer {bearer}"}, timeout=15)
    try:
        return {"http": r.status_code, "resp": r.json()}
    except ValueError:
        return {"http": r.status_code, "resp": r.text[:300]}


def run():
    out = {}
    bearer = _app_bearer()
    out["app_bearer"] = bool(bearer)
    if not bearer:
        return {"ok": False, "reason": "앱 전용 토큰 실패", **out}

    listed = _get(f"{API}/webhooks", bearer)
    out["before"] = listed
    hook_id = os.environ.get("X_WEBHOOK_ID", "")
    for h in ((listed["resp"] or {}).get("data") or []) if isinstance(listed["resp"], dict) else []:
        if "/api/webhook" in (h.get("url") or ""):
            hook_id = h.get("id")
    if not hook_id:
        return {"ok": False, "reason": "웹훅 id 못 찾음", **out}

    # 재검증 트리거 — X가 우리 /api/webhook 에 CRC(GET)를 보내고, 통과하면 204+valid
    r = requests.put(f"{API}/webhooks/{hook_id}",
                     headers={"Authorization": f"Bearer {bearer}"}, timeout=20)
    try:
        rv = r.json()
    except ValueError:
        rv = r.text[:200] or "(빈 응답)"
    out["revalidate"] = {"http": r.status_code, "resp": rv}

    out["after"] = _get(f"{API}/webhooks", bearer)
    valid = False
    for h in ((out["after"]["resp"] or {}).get("data") or []) if isinstance(out["after"]["resp"], dict) else []:
        if h.get("id") == hook_id:
            valid = bool(h.get("valid"))
    out["ok"] = valid
    out["webhook_id"] = hook_id
    return out


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
