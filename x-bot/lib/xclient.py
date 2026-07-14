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


# ---------------- 공식 멘션 조회 (웹훅 배달이 안 될 때의 안정적 대체) ----------------
def _oauth1_get(url):
    """OAuth1.0a 사용자 컨텍스트 GET."""
    oauth = {
        "oauth_consumer_key": os.environ["X_API_KEY"],
        "oauth_token": os.environ["X_ACCESS_TOKEN"],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    return requests.get(url, headers={"Authorization": _oauth_header("GET", url, oauth)},
                        timeout=20)


def bot_user_id(store=None):
    """봇 계정 숫자 ID. env(X_BOT_ID) → Redis 캐시 → GET /2/users/me 순."""
    envid = os.environ.get("X_BOT_ID", "").strip()
    if envid:
        return envid
    if store is not None:
        cached = store.get("bot:id")
        if cached:
            return cached
    try:
        r = _oauth1_get("https://api.x.com/2/users/me")
        uid = (r.json().get("data") or {}).get("id") if r.ok else None
    except Exception:
        uid = None
    if uid and store is not None:
        store.set("bot:id", uid)
    return uid


def mentions_x(since_id=None, store=None, max_results=25):
    """GET /2/users/:id/mentions — @봇 멘션을 공식 API로 조회.
    since_id 이후의 새 멘션만 오래된→최신 순으로. 반환: [{id, text, author_id, ts}]."""
    uid = bot_user_id(store)
    if not uid:
        return []
    url = (f"https://api.x.com/2/users/{uid}/mentions"
           f"?max_results={max_results}&tweet.fields=created_at,author_id")
    if since_id:
        url += f"&since_id={since_id}"
    try:
        r = _oauth1_get(url)
        if not r.ok:
            return []
        data = r.json().get("data") or []
    except Exception:
        return []
    out = []
    for t in data:
        if str(t.get("author_id")) == str(uid):           # 내 글 제외
            continue
        out.append({"id": str(t["id"]), "text": t.get("text", ""),
                    "author_id": str(t.get("author_id") or ""),
                    "ts": _to_epoch(t.get("created_at"))})
    out.sort(key=lambda x: int(x["id"]))                  # id 오름차순 = 오래된→최신
    return out


# ---------------- X API v2 답글 게시 (OAuth1.0a) ----------------
def _oauth_header(method, url, oauth):
    enc = lambda s: urllib.parse.quote(str(s), safe="~")
    # OAuth1 서명 base string: (1) 쿼리 파라미터를 반드시 서명 대상에 포함하고
    # (2) base URI에서는 쿼리를 제외해야 한다. (예전엔 URL을 통째로 넣어 쿼리 있는
    #  엔드포인트에서 서명이 깨졌다 → mentions 401.)
    split = urllib.parse.urlsplit(url)
    base_uri = urllib.parse.urlunsplit((split.scheme, split.netloc, split.path, "", ""))
    params = dict(oauth)
    for k, v in urllib.parse.parse_qsl(split.query, keep_blank_values=True):
        params[k] = v
    param_str = "&".join(f"{enc(k)}={enc(params[k])}" for k in sorted(params))
    base_str = "&".join([method.upper(), enc(base_uri), enc(param_str)])
    key = f"{enc(os.environ['X_API_SECRET'])}&{enc(os.environ['X_ACCESS_SECRET'])}"
    sig = hmac.new(key.encode(), base_str.encode(), hashlib.sha1).digest()
    import base64
    # Authorization 헤더에는 oauth_* 파라미터만 넣는다(쿼리 파라미터는 제외).
    header = dict(oauth, oauth_signature=base64.b64encode(sig).decode())
    return "OAuth " + ", ".join(f'{enc(k)}="{enc(v)}"' for k, v in sorted(header.items()))


def post_reply(text, in_reply_to_id):
    """답글 게시. 반환: (ok, detail).
    OAuth1.0a로 먼저 시도하고, 이 티어가 1.0a를 거부하면(Unsupported Authentication)
    OAuth 2.0 사용자 토큰(lib/oauth2, /api/oauth2 승인으로 발급)으로 자동 폴백."""
    url = "https://api.x.com/2/tweets"
    body = {"text": text, "reply": {"in_reply_to_tweet_id": str(in_reply_to_id)}}
    oauth = {
        "oauth_consumer_key": os.environ["X_API_KEY"],
        "oauth_token": os.environ["X_ACCESS_TOKEN"],
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_version": "1.0",
    }
    auth = _oauth_header("POST", url, oauth)
    try:
        r = requests.post(url, json=body,
                          headers={"Authorization": auth, "Content-Type": "application/json"},
                          timeout=20)
    except Exception as e:
        return False, f"예외 {e}"
    if r.status_code in (200, 201):
        return True, r.json()
    if r.status_code in (401, 403) and "Unsupported Authentication" in r.text:
        try:
            from lib import oauth2
            tok = oauth2.user_token()
        except Exception:
            tok = None
        if tok:
            try:
                r2 = requests.post(url, json=body,
                                   headers={"Authorization": f"Bearer {tok}",
                                            "Content-Type": "application/json"},
                                   timeout=20)
            except Exception as e:
                return False, f"OAuth2 폴백 예외 {e}"
            if r2.status_code in (200, 201):
                return True, r2.json()
            return False, f"OAuth2 폴백 HTTP {r2.status_code} {r2.text[:300]}"
        return False, (f"HTTP {r.status_code} 1.0a 거부 — OAuth2 토큰 없음. "
                       f"/api/oauth2?key=<POLL_SECRET> 로 승인 필요")
    return False, f"HTTP {r.status_code} {r.text[:300]}"
