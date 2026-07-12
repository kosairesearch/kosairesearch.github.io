"""내부 엔드포인트를 '기다리지 않고' 깨우기 — 감지→처리 자기연쇄(self-chain).

서버리스 함수 타임아웃을 피하려고 poll은 감지만, work는 생성·게시만 담당하고,
서로를 짧은 타임아웃의 요청으로 깨운다(응답을 안 기다림). 크론이 백스톱.
env: APP_URL(배포 URL), POLL_SECRET
"""
import os

import requests

APP_URL = os.environ.get("APP_URL", "").rstrip("/")
SECRET = os.environ.get("POLL_SECRET", "")


def kick(path):
    if not APP_URL:
        return
    try:
        requests.get(f"{APP_URL}/{path.lstrip('/')}", params={"key": SECRET}, timeout=2)
    except Exception:
        pass          # 응답 안 기다림 — 요청 발사만 하면 됨
