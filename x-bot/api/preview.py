"""GET /api/preview?q=삼성전자&lang=ko — 답글을 '게시하지 않고' 문자열로 반환.

X 계정 승인 전에도 생성 품질을 바로 확인할 수 있는 테스트 엔드포인트.
lang 생략 시 q에 한글 있으면 ko, 없으면 en 자동.
"""
import json
import hmac
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lib import pipeline


def _key_ok(q):
    """?key= 가 POLL_SECRET 과 같은가. 비밀이 아예 없으면 무조건 거부한다.

    전에는 POLL_SECRET 이 비어 있으면 검사를 건너뛰었다 — 환경변수 하나
    빠뜨리면 이 주소를 아는 누구나 봇을 돌릴 수 있는 구조였다. 비교는
    글자 수 차이로 새지 않게 compare_digest 로 한다."""
    secret = os.environ.get("POLL_SECRET") or ""
    key = (q.get("key") or [""])[0]
    return bool(secret) and hmac.compare_digest(key.encode("utf-8"), secret.encode("utf-8"))


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if not _key_ok(q):
            self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
        query = q.get("q", [""])[0]
        lang = q.get("lang", [None])[0]
        if not query:
            self.send_response(400); self.end_headers()
            self.wfile.write(b'{"error":"q required"}'); return
        try:
            reply, ticker = pipeline.build_reply(query, lang)
            out = {"ticker": ticker, "chars": len(reply or ""), "reply": reply}
            code, body = (200 if reply else 404), json.dumps(out, ensure_ascii=False)
        except Exception as e:
            code, body = 500, json.dumps({"error": str(e)})
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())
