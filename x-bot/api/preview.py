"""GET /api/preview?q=삼성전자&lang=ko — 답글을 '게시하지 않고' 문자열로 반환.

X 계정 승인 전에도 생성 품질을 바로 확인할 수 있는 테스트 엔드포인트.
lang 생략 시 q에 한글 있으면 ko, 없으면 en 자동.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from lib import pipeline


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if os.environ.get("POLL_SECRET") and q.get("key", [""])[0] != os.environ["POLL_SECRET"]:
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
