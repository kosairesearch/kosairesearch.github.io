#!/usr/bin/env python3
"""GA4 자료를 어디에 둘지 — 저장소가 아니라 Firestore.

왜 옮겼나 (2026-09-13)
----------------------
이 저장소는 공개다(GitHub Pages 무료 요금제라 공개여야 한다). 그래서
data/ga4/weekly.json 을 커밋한 순간 방문자 수·유입 경로·인기 페이지가
인터넷에 그대로 열렸다. 76분 만에 알아채고 내렸다.

숫자를 쌓아 두는 것 자체는 필요하다 — GA4 는 오래된 기록을 지우므로
매주 받아 두어야 '작년 이맘때' 와 비교할 수 있다. 둘 곳만 바꾼다.

Firestore 를 고른 이유
  · 이미 있다. 파이어베이스 프로젝트도, 서비스 계정 열쇠도.
  · 기본이 비공개다. 규칙에 열어 주지 않는 컬렉션은 아무도 못 읽는다.
  · 영구적이다. 깃 기록을 다시 쓰지 않아도 된다.

    marketing/weekly          주간 숫자 (weeks 배열)
    marketing/experiments     실험 대장

열쇠가 없으면(내 컴퓨터에서 시험할 때) 로컬 파일로 떨어진다. 그때 쓰는
파일은 .gitignore 에 걸려 있어 실수로 커밋되지 않는다.
"""
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data" / "ga4"          # 열쇠가 없을 때만. .gitignore 됨
COLLECTION = "marketing"
KST = datetime.timezone(datetime.timedelta(hours=9))


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _client():
    """Firestore. 열쇠가 없으면 None — 부르는 쪽이 로컬로 떨어진다."""
    raw = os.environ.get("GCP_SA_KEY", "").strip()
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not raw and not (path and Path(path).exists()):
        return None
    try:
        from google.cloud import firestore
        from google.oauth2 import service_account
        if raw:
            info = json.loads(raw)
            cred = service_account.Credentials.from_service_account_info(info)
            return firestore.Client(project=info.get("project_id"), credentials=cred)
        info = json.loads(Path(path).read_text(encoding="utf-8"))
        cred = service_account.Credentials.from_service_account_file(path)
        return firestore.Client(project=info.get("project_id"), credentials=cred)
    except Exception as e:
        log(f"· Firestore 에 붙지 못했다 — 로컬 파일을 쓴다: {type(e).__name__} {e}")
        return None


def _local(name):
    return LOCAL / f"{name}.json"


def load(name, default=None):
    """marketing/<name> 을 읽는다. 없으면 default."""
    cl = _client()
    if cl:
        try:
            snap = cl.collection(COLLECTION).document(name).get()
            if snap.exists:
                return snap.to_dict()
            return default if default is not None else {}
        except Exception as e:
            log(f"· Firestore 읽기 실패 — 로컬로 떨어진다: {type(e).__name__} {e}")
    f = _local(name)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            log(f"· 로컬 파일을 읽지 못했다: {e}")
    return default if default is not None else {}


def save(name, doc):
    """marketing/<name> 에 쓴다. 어디에 썼는지를 돌려준다."""
    doc = dict(doc)
    doc["savedAt"] = datetime.datetime.now(KST).isoformat(timespec="seconds")
    cl = _client()
    if cl:
        try:
            cl.collection(COLLECTION).document(name).set(doc)
            return "firestore"
        except Exception as e:
            log(f"· Firestore 쓰기 실패 — 로컬에 남긴다: {type(e).__name__} {e}")
    LOCAL.mkdir(parents=True, exist_ok=True)
    _local(name).write_text(json.dumps(doc, ensure_ascii=False, indent=2),
                            encoding="utf-8")
    return f"local:{_local(name).relative_to(ROOT)}"


def where():
    """지금 어디에 저장되는지. 사람에게 보여 주는 용도."""
    return "Firestore(비공개)" if _client() else f"로컬 파일 {LOCAL.relative_to(ROOT)}"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="읽어서 찍어 볼 문서 이름 (weekly·experiments)")
    a = ap.parse_args()
    log(f"저장 위치: {where()}")
    if a.show:
        print(json.dumps(load(a.show), ensure_ascii=False, indent=2)[:4000])
