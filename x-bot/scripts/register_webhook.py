"""X 웹훅 등록 + 계정 이벤트 구독 — Vercel 배포 후 로컬에서 1회 실행.

X API v2 웹훅 엔드포인트 사용. 등록하는 순간 X가 웹훅 URL로 CRC(GET) 검증을
보내므로 반드시 배포가 먼저 끝나 있어야 한다.
(개발자 콘솔 툴박스 → 웹훅 UI에서도 같은 작업 가능 — 스크립트 실패 시 UI로.)

실행:
  export X_API_KEY=... X_API_SECRET=... X_ACCESS_TOKEN=... X_ACCESS_SECRET=...
  export WEBHOOK_URL=https://<프로젝트>.vercel.app/api/webhook
  python x-bot/scripts/register_webhook.py            # 확인→등록→구독
  python x-bot/scripts/register_webhook.py delete <웹훅ID>
"""
import json
import os
import sys
import time
import uuid

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.xclient import _oauth_header  # OAuth1.0a 서명 재사용

API = "https://api.x.com/2"


def call(method, url, body=None):
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
    r = requests.request(method, url, json=body, headers=headers, timeout=30)
    print(f"  {method} {url.replace(API, '')} → HTTP {r.status_code}: {r.text[:400]}")
    return r


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "delete":
        call("DELETE", f"{API}/webhooks/{sys.argv[2]}")
        return

    url = os.environ["WEBHOOK_URL"]
    print("① 등록된 웹훅 확인")
    r = call("GET", f"{API}/webhooks")
    hooks = (r.json().get("data") or []) if r.ok else []
    hook = next((h for h in hooks if h.get("url") == url), None)

    if hook:
        print(f"  이미 등록됨: id {hook.get('id')} · valid={hook.get('valid')}")
    else:
        print(f"② 웹훅 등록 (X가 즉시 CRC 검증을 보냄): {url}")
        r = call("POST", f"{API}/webhooks", {"url": url})
        if not r.ok:
            sys.exit("등록 실패 — Vercel 배포와 /api/webhook CRC 응답부터 확인하세요.")
        hook = r.json().get("data", {})

    wid = hook.get("id")
    print(f"③ 계정 이벤트 구독 (webhook {wid}) — 봇 계정의 멘션이 이 웹훅으로 들어옴")
    r = call("POST", f"{API}/account_activity/webhooks/{wid}/subscriptions/all")
    if r.status_code in (200, 201, 204):
        print("✅ 완료 — @멘션이 실시간으로 들어옵니다.")
    elif r.status_code == 409:
        print("✅ 이미 구독돼 있음.")
    else:
        print("⚠ 구독 실패 — 개발자 콘솔 툴박스→이벤트 구독 UI에서 수동 구독하세요.")


if __name__ == "__main__":
    main()
