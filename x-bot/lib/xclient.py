"""X 연동 — 멘션 감지(Apify 스크래핑) + 답글 게시(X API v2, OAuth1.0a).

웹훅(Activity API)은 Enterprise 전용이라, 저비용으로 '거의 실시간'을 내기 위해
Apify로 @핸들 멘션을 짧은 주기로 긁는다. 답글은 X Free 티어 POST /2/tweets(무료)로.
OAuth1.0a 서명은 표준 라이브러리만으로 구현(번들 최소화).

env: APIFY_TOKEN, X_MENTION_ACTOR(기본 kaito),
     X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, BOT_HANDLE
"""
import hashlib
import hmac
import os
import time
import urllib.parse
import uuid

import requests

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
MENTION_ACTOR = os.environ.get(
    "X_MENTION_ACTOR",
    "kaitoeasyapi~twitter-x-data-tweet-scraper-pay-per-result-cheapest")
BOT_HANDLE = os.environ.get("BOT_HANDLE", "kosai_x").lstrip("@")

_ID_KEYS = ("id", "id_str", "tweetId", "conversationId")
_TEXT_KEYS = ("text", "full_text", "fullText", "content")
_TIME_KEYS = ("createdAt", "created_at", "timestamp", "date")


def _first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _author(d):
    for k in ("author", "user", "tweetBy"):
        u = d.get(k)
        if isinstance(u, dict):
            return (u.get("userName") or u.get("screen_name") or u.get("username")
                    or u.get("handle") or "").lstrip("@")
        if isinstance(u, str):
            return u.lstrip("@")
    return (d.get("username") or d.get("screen_name") or "").lstrip("@")


def _to_epoch(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v if v < 1e12 else v / 1000)
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d %H:%M:%S"):
        try:
            from datetime import datetime, timezone
            dt = datetime.strptime(v, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            continue
    return 0.0


def scrape_mentions(limit=20, poll_sec=45):
    """@BOT_HANDLE 을 포함한 최근 트윗을 Apify로 긁어 최신순 리스트로.
    반환: [{id, text, author, ts}] (실패 시 [])."""
    if not APIFY_TOKEN:
        return []
    base = "https://api.apify.com/v2"
    query = f"@{BOT_HANDLE} -filter:retweets -filter:nativeretweets"
    payload = {
        "searchTerms": [query],
        "sort": "Latest",
        "maxItems": limit,
        "maxTweets": limit,
        "includeSearchTerms": False,
    }
    try:
        r = requests.post(f"{base}/acts/{MENTION_ACTOR}/runs?token={APIFY_TOKEN}",
                          json=payload, timeout=30)
        if not r.ok:
            return []
        run = (r.json() or {}).get("data", {})
        run_id, ds = run.get("id"), run.get("defaultDatasetId")
        if not run_id:
            return []
        status = run.get("status")
        deadline = time.time() + poll_sec
        while time.time() < deadline and status not in (
                "SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT", "TIMED_OUT"):
            time.sleep(4)
            s = (requests.get(f"{base}/actor-runs/{run_id}?token={APIFY_TOKEN}",
                              timeout=20).json() or {}).get("data", {})
            status = s.get("status", status)
            ds = s.get("defaultDatasetId", ds)
        if status != "SUCCEEDED" or not ds:
            return []
        items = requests.get(
            f"{base}/datasets/{ds}/items?token={APIFY_TOKEN}&clean=true&format=json",
            timeout=60).json()
    except Exception:
        return []
    out = []
    for it in items if isinstance(items, list) else []:
        if it.get("noResults") or it.get("demo"):
            continue
        tid = _first(it, _ID_KEYS)
        text = _first(it, _TEXT_KEYS)
        if not tid or not text:
            continue
        author = _author(it)
        if author.lower() == BOT_HANDLE.lower():          # 내 글은 제외
            continue
        out.append({"id": str(tid), "text": text, "author": author,
                    "ts": _to_epoch(_first(it, _TIME_KEYS))})
    out.sort(key=lambda x: x["ts"])                       # 오래된→최신
    return out


# ---------------- X API v2 답글 게시 (OAuth1.0a) ----------------
def _oauth_header(method, url, oauth):
    params = {k: v for k, v in oauth.items()}
    enc = lambda s: urllib.parse.quote(str(s), safe="~")
    base_str = "&".join([
        method.upper(), enc(url),
        enc("&".join(f"{enc(k)}={enc(params[k])}" for k in sorted(params))),
    ])
    key = f"{enc(os.environ['X_API_SECRET'])}&{enc(os.environ['X_ACCESS_SECRET'])}"
    sig = hmac.new(key.encode(), base_str.encode(), hashlib.sha1).digest()
    import base64
    oauth = dict(oauth, oauth_signature=base64.b64encode(sig).decode())
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(oauth.items()))


def post_reply(text, in_reply_to_id):
    """답글 게시. 반환: (ok, detail)."""
    url = "https://api.x.com/2/tweets"
    oauth = {
        "oauth_consumer_key": os.environ["X_API_KEY"],
        "oauth_token": os.environ["X_ACCESS_TOKEN"],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    auth = _oauth_header("POST", url, oauth)
    body = {"text": text, "reply": {"in_reply_to_tweet_id": str(in_reply_to_id)}}
    try:
        r = requests.post(url, json=body,
                          headers={"Authorization": auth, "Content-Type": "application/json"},
                          timeout=20)
    except Exception as e:
        return False, f"예외 {e}"
    if r.status_code in (200, 201):
        return True, r.json()
    return False, f"HTTP {r.status_code} {r.text[:300]}"
