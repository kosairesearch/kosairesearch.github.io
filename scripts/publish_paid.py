#!/usr/bin/env python3
"""리포트를 무료/유료로 갈라, 유료 구간을 Firestore 로 올리고 정적 파일에서 뺀다.

이걸 돌리기 전에는 유료화가 성립하지 않는다. 지금은 리포트 전문이
data/reports_v2/{ticker}.json 으로 GitHub Pages 에 그대로 올라가 있어서,
화면에 잠금을 아무리 잘 그려도 주소만 치면 원문이 나온다.

  정적 파일  → 무료 구간만 + hasPaid:true   (검색 유입·미리보기용)
  Firestore  → 유료 구간 reports_paid/{ticker}  (getReport 로만 나감)

기준은 scripts/report_split.py 한 곳에서만 정한다. v1 리포트는 유료 구간이
없으므로 전문이 그대로 남는다(hasPaid:false).

  python3 scripts/publish_paid.py            # 검사만 — 무엇이 바뀌는지 출력
  python3 scripts/publish_paid.py --write    # 정적 파일 수정
  python3 scripts/publish_paid.py --write --upload   # Firestore 업로드까지

⚠️ --write 만 하고 업로드를 안 하면 유료 구간이 어디에도 없게 된다.
   순서는 반드시 업로드 → 정적 파일 제거.

환경변수
  GOOGLE_APPLICATION_CREDENTIALS  서비스 계정 키 파일 경로
  또는 FIREBASE_SERVICE_ACCOUNT   서비스 계정 JSON 문자열(깃허브 시크릿용)
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_split import split, unknown_keys                      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DIRS = ("reports_v2", "reports")
BATCH = 400          # Firestore 배치 쓰기 상한은 500


def log(m):
    print(m, flush=True)


def firestore():
    """서비스 계정으로 Firestore 클라이언트를 만든다. 없으면 None."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore as fs
    except ImportError:
        log("❌ firebase-admin 이 없습니다 — pip install firebase-admin")
        return None
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT")
    if raw:
        cred = credentials.Certificate(json.loads(raw))
    elif os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        cred = credentials.ApplicationDefault()
    else:
        log("❌ 서비스 계정이 없습니다 — FIREBASE_SERVICE_ACCOUNT 또는 GOOGLE_APPLICATION_CREDENTIALS")
        return None
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)
    return fs.client()


def main():
    write = "--write" in sys.argv
    upload = "--upload" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]

    db = firestore() if upload else None
    if upload and db is None:
        sys.exit(1)

    # 화면이 실제로 서빙하는 파일만 다룬다. 같은 종목의 v1 이 남아 있으면
    # 그건 stock.html 이 안 읽는 파일이므로 건드리지 않는다.
    served, seen = [], set()
    for sub in DIRS:
        d = ROOT / "data" / sub
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            if f.stem in seen or f.stem == "index":
                continue
            if only and f.stem not in only:
                continue
            seen.add(f.stem)
            served.append(f)

    log(f"## 대상 {len(served)}개 · write={write} upload={upload}")
    n_paid = n_free = n_unknown = 0
    batch, pending = (db.batch() if db else None), 0
    changed = []

    for f in served:
        rep = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(rep, dict):
            continue
        unk = unknown_keys(rep)
        if unk:
            n_unknown += 1
            log(f"  ⚠️ {f.stem} 미정의 키(유료 처리됨): {unk}")
        free, paid = split(rep)
        if not paid:
            n_free += 1
            continue
        n_paid += 1
        changed.append((f, free, paid))

        if db is not None:
            batch.set(db.document(f"reports_paid/{f.stem}"), paid)
            pending += 1
            if pending >= BATCH:
                batch.commit(); batch = db.batch(); pending = 0
                log(f"  · 업로드 {n_paid}건…")

    if db is not None and pending:
        batch.commit()
    if upload:
        log(f"- ✅ Firestore 업로드 {n_paid}건")

    if write:
        # 업로드를 건너뛴 채 정적 파일만 비우면 유료 구간이 사라진다.
        if not upload:
            log("❌ --upload 없이 --write 는 막습니다 — 유료 구간이 어디에도 남지 않습니다.")
            sys.exit(2)
        for f, free, _ in changed:
            f.write_text(json.dumps(free, ensure_ascii=False), encoding="utf-8")
        log(f"- ✅ 정적 파일 {len(changed)}개에서 유료 구간 제거")

    log(f"\n요약 · 유료 분리 {n_paid} / 전문 무료(v1) {n_free} / 미정의 키 {n_unknown}")
    if changed and not write:
        f, free, paid = changed[0]
        log(f"예시 [{f.stem}] 무료 {len(json.dumps(free, ensure_ascii=False)):,}자 "
            f"· 유료 {len(json.dumps(paid, ensure_ascii=False)):,}자")


if __name__ == "__main__":
    main()
