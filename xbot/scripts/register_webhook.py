"""X 웹훅 등록 + 계정 구독 — 배포 후 1회 실행.

실행 전 환경변수: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET,
WEBHOOK_URL (예: https://<vercel-도메인>/api/process 가 아니라 /api/webhook)

사용법:
  python scripts/register_webhook.py            # 상태 확인 → 없으면 등록 → 구독
  python scripts/register_webhook.py delete <id>  # 웹훅 삭제

X API v2 웹훅 엔드포인트를 쓴다. 등록 시 X가 즉시 CRC(GET) 검증을 보내므로
Vercel 배포가 먼저 완료돼 있어야 한다.
(개발자 콘솔 툴박스→웹훅 UI에서도 같은 작업이 가능 — 스크립트가 실패하면 UI로.)
"""
import json
import os
import sys

import requests
from requests_oauthlib import OAuth1

API = "https://api.x.com/2"


def auth():
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])


def show(r):
    print(f"  HTTP {r.status_code}: {r.text[:500]}")
    return r


def list_webhooks(a):
    r = show(requests.get(f"{API}/webhooks", auth=a, timeout=20))
    try:
        return r.json().get("data", []) or []
    except Exception:
        return []


def main():
    a = auth()
    if len(sys.argv) > 2 and sys.argv[1] == "delete":
        print("웹훅 삭제:", sys.argv[2])
        show(requests.delete(f"{API}/webhooks/{sys.argv[2]}", auth=a, timeout=20))
        return

    url = os.environ["WEBHOOK_URL"]
    print("① 등록된 웹훅 확인")
    hooks = list_webhooks(a)
    hook = next((h for h in hooks if h.get("url") == url), None)

    if not hook:
        print(f"② 웹훅 등록 (CRC 검증이 즉시 옴): {url}")
        r = show(requests.post(f"{API}/webhooks", json={"url": url},
                               auth=a, timeout=30))
        if not r.ok:
            sys.exit("등록 실패 — Vercel 배포/CRC 응답을 먼저 확인하세요.")
        hook = r.json().get("data", {})
    else:
        print("  이미 등록됨:", hook.get("id"))

    wid = hook.get("id")
    print(f"③ 계정 이벤트 구독 (webhook {wid})")
    r = show(requests.post(
        f"{API}/account_activity/webhooks/{wid}/subscriptions/all",
        auth=a, timeout=30))
    if r.status_code in (200, 204):
        print("✅ 완료 — 이제 @멘션이 웹훅으로 들어옵니다.")
    elif r.status_code == 409:
        print("✅ 이미 구독돼 있음.")
    else:
        print("구독 실패 — 콘솔 툴박스→이벤트 구독 UI에서 수동 구독을 시도하세요.")


if __name__ == "__main__":
    main()
