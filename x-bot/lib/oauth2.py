"""OAuth 2.0 사용자 토큰 관리 — 발급(인가코드 교환)·저장(Redis)·자동 갱신.

새 X 콘솔은 웹훅 구독 등에 OAuth 2.0 사용자 토큰을 요구한다(1.0a 거부).
api/oauth2.py 가 브라우저 승인 1회로 토큰을 받아 Redis에 저장하면,
이후 어디서든 user_token()으로 꺼내 쓰고 만료 시 refresh 토큰으로 자동 갱신.
env: X_CLIENT_ID, X_CLIENT_SECRET
"""
import os

import requests

from lib import store

TOKEN_URL = "https://api.x.com/2/oauth2/token"
SCOPES = "tweet.read tweet.write users.read offline.access"


def _creds():
    return os.environ.get("X_CLIENT_ID", ""), os.environ.get("X_CLIENT_SECRET", "")


def save_tokens(tok):
    if tok.get("access_token"):
        ex = max(60, int(tok.get("expires_in", 7200)) - 300)
        store.set("oauth2:access", tok["access_token"], ex=ex)
    if tok.get("refresh_token"):
        store.set("oauth2:refresh", tok["refresh_token"])


def exchange_code(code, redirect_uri, verifier):
    """인가 코드 → 액세스/리프레시 토큰."""
    cid, csec = _creds()
    r = requests.post(TOKEN_URL, auth=(cid, csec), data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": redirect_uri, "code_verifier": verifier,
        "client_id": cid}, timeout=20)
    try:
        tok = r.json()
    except ValueError:
        return r.status_code, {"raw": r.text[:300]}
    if r.ok:
        save_tokens(tok)
    return r.status_code, tok


def _refresh():
    cid, csec = _creds()
    rt = store.get("oauth2:refresh")
    if not (rt and cid):
        return None
    r = requests.post(TOKEN_URL, auth=(cid, csec), data={
        "grant_type": "refresh_token", "refresh_token": rt,
        "client_id": cid}, timeout=20)
    if r.ok:
        save_tokens(r.json())
        return store.get("oauth2:access")
    return None


def user_token():
    """유효한 사용자 액세스 토큰(없으면 refresh 시도, 그래도 없으면 None)."""
    return store.get("oauth2:access") or _refresh()
