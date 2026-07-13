"""GET /api/poll?key=<POLL_SECRET> — 외부 크론(1~2분)이 호출. 새 멘션 감지 → 큐 → work.

웹훅 배달이 안 되는 X 티어 이슈 대응: 공식 API GET /2/users/:id/mentions 를
since_id 기준으로 폴링한다. 무거운 생성·게시는 work가 담당(타임아웃 회피).
(Apify 경로가 필요하면 xclient.scrape_mentions로 교체 가능 — 지금은 공식 API 사용.)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lib import store, xclient, kick


def _max_id(a, b):
    """더 큰 트윗 id(문자열 숫자) 반환."""
    if not a:
        return b
    if not b:
        return a
    return a if int(a) >= int(b) else b


def diag():
    """?debug=1 — users/me·mentions 원시 HTTP 상태를 그대로 노출(에러 원인 파악)."""
    from lib.xclient import _oauth1_get
    def body(r):
        try:
            return r.json()
        except ValueError:
            return r.text[:300]
    out = {}
    r = _oauth1_get("https://api.x.com/2/users/me")
    out["users_me"] = {"http": r.status_code, "body": body(r)}
    uid = None
    try:
        uid = (r.json().get("data") or {}).get("id")
    except Exception:
        pass
    out["uid"] = uid
    if uid:
        url = (f"https://api.x.com/2/users/{uid}/mentions"
               f"?max_results=10&tweet.fields=created_at,author_id")
        r2 = _oauth1_get(url)
        out["mentions"] = {"http": r2.status_code, "body": body(r2)}
    return out


def run():
    since = store.get("mention:since_id")
    mentions = xclient.mentions_x(since_id=since, store=store, max_results=25)
    queued, newest = 0, since
    for m in mentions:
        newest = _max_id(newest, m["id"])
        if not store.mark_if_new(m["id"]):       # 이미 처리/예약됨
            continue
        store.push_job({"id": m["id"], "text": m["text"], "attempts": 0})
        queued += 1
    if newest and newest != since:
        store.set("mention:since_id", newest)
    if queued:
        kick.kick("/api/work")                   # 처리 시작(비동기)
    return {"fetched": len(mentions), "queued": queued,
            "pending": store.jobs_len(), "since_id": newest}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        try:
            out = diag() if q.get("debug", [""])[0] else run()
            code, body = 200, json.dumps(out, ensure_ascii=False)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body.encode())
