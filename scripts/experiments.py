#!/usr/bin/env python3
"""실험 대장 — 제안하고 끝내지 않는다.

왜 있나
-------
매주 새 제안만 쏟아내는 것은 잔소리다. 지난주에 뭘 하자고 했는지, 그래서
했는지, 했더니 어떻게 됐는지를 따라가야 '일'이 된다.

    1주차  제안   "리포트 페이지에 가입 버튼이 없다. 넣어보자"
                 → 무엇을 볼지(지표)와 그때 값을 같이 적어 둔다
    2주차  실행   사람이 하고 나서 '했다'고 표시 (--start)
    3주차  검증   그 지표가 어떻게 됐는지 자동으로 대 본다

지표와 '시작 시점의 값'을 제안할 때 미리 박아 두는 게 핵심이다. 나중에
고르면 좋아 보이는 숫자를 고르게 된다.

    python3 scripts/experiments.py --list
    python3 scripts/experiments.py --start exp_3
    python3 scripts/experiments.py --drop exp_3 --why "안 하기로 함"
"""
import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "data" / "ga4" / "experiments.json"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 검증에 쓸 수 있는 지표. 모델이 아무 말이나 적으면 다음 주에 대 볼 수 없다.
METRICS = {
    "users": "방문자 수",
    "returningUsers": "재방문자 수",
    "returnRate": "재방문율(%)",
    "sessions": "방문 횟수",
    "pageViews": "페이지 조회",
    "engagedRate": "제대로 본 방문 비율(%)",
    "avgSessionSec": "머문 시간(초)",
    "signUp": "회원가입 건수",
    "signUpRate": "가입 전환율(%)",
    "watchlistAdd": "관심종목 담기",
}
STATUS = ("제안됨", "진행중", "끝남", "버림")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load():
    """실험 대장도 저장소가 아니라 Firestore 다 — 무엇을 시험 중인지가
    사업 전략이라서 공개 저장소에 둘 것이 아니다."""
    import ga4_store
    doc = ga4_store.load("experiments", {"items": []})
    # 저장된 문서에 items 가 없을 수도 있다(처음이거나, 다른 모양으로
    # 저장된 적이 있거나). 여기서 한 번 채워 두면 아래 모든 함수가
    # doc["items"] 를 그냥 써도 된다.
    if not isinstance(doc.get("items"), list):
        doc["items"] = []
    return doc


def save(doc):
    import ga4_store
    doc["updatedAt"] = datetime.datetime.now(KST).isoformat(timespec="seconds")
    ga4_store.save("experiments", doc)


def value_of(week, key):
    """한 주 기록에서 지표 하나를 꺼낸다. 없으면 None."""
    if not week:
        return None
    if key == "returnRate":
        u = week.get("users") or 0
        return round(week.get("returningUsers", 0) / u * 100, 1) if u else None
    if key == "engagedRate":
        s = week.get("sessions") or 0
        return round(week.get("engagedSessions", 0) / s * 100, 1) if s else None
    if key in ("signUp", "watchlistAdd"):
        name = "sign_up" if key == "signUp" else "watchlist_add"
        for e in (week.get("events") or []):
            if e.get("eventName") == name:
                return e.get("eventCount")
        return None
    if key == "signUpRate":
        u = week.get("users") or 0
        su = value_of(week, "signUp")
        return round(su / u * 100, 2) if (u and su is not None) else None
    return week.get(key)


def propose(doc, title, why, metric, action, week):
    """모델이 낸 제안을 대장에 올린다. 같은 제목이 이미 있으면 올리지 않는다."""
    if metric not in METRICS:
        return None, f"모르는 지표: {metric}"
    live = [x for x in doc["items"] if x["status"] in ("제안됨", "진행중")]
    if any(x["title"].strip() == title.strip() for x in live):
        return None, "같은 제안이 이미 대장에 있다"
    # 번호는 '지금 몇 개냐' 가 아니라 '지금까지 가장 큰 번호' 에서 잇는다.
    # 개수로 매기면 중간에 하나를 지웠을 때 이미 쓴 번호를 다시 내주고,
    # 그러면 보고서에 적어 보낸 exp_3 이 다른 실험을 가리키게 된다.
    used = []
    for x in doc["items"]:
        tail = str(x.get("id", "")).rsplit("_", 1)[-1]
        if tail.isdigit():
            used.append(int(tail))
    item = {
        "id": f"exp_{(max(used) + 1) if used else 1}",
        "title": title.strip(),
        "why": why.strip(),
        "action": action.strip(),
        "metric": metric,
        "metricLabel": METRICS[metric],
        "baseWeek": week.get("week"),
        "baseValue": value_of(week, metric),
        "proposedAt": datetime.datetime.now(KST).date().isoformat(),
        "status": "제안됨",
        "startedWeek": None,
        "result": None,
    }
    doc["items"].append(item)
    return item, None


def review(doc, weeks):
    """진행중인 실험을 지금 숫자에 대 본다. (끝난 것 목록)"""
    if not weeks:
        return []
    cur = weeks[-1]
    done = []
    for it in doc["items"]:
        if it["status"] != "진행중" or not it.get("startedWeek"):
            continue
        # 시작한 주는 어수선하다(그 주 중간에 바꿨을 수 있다). 그 다음 주부터 본다.
        if cur.get("week") <= it["startedWeek"]:
            continue
        now = value_of(cur, it["metric"])
        base = it.get("baseValue")
        if now is None or base is None:
            it["result"] = {"week": cur.get("week"), "now": now, "base": base,
                            "verdict": "잴 수 없음",
                            "note": "그 지표를 받지 못했다"}
        else:
            diff = now - base
            pct = (diff / base * 100) if base else None
            # 5% 안쪽 움직임은 주간 널뛰기와 구분되지 않는다.
            if pct is None:
                verdict = "잴 수 없음"
            elif pct >= 5:
                verdict = "효과 있음"
            elif pct <= -5:
                verdict = "역효과"
            else:
                verdict = "변화 없음"
            it["result"] = {"week": cur.get("week"), "now": now, "base": base,
                            "diff": round(diff, 2),
                            "pct": round(pct, 1) if pct is not None else None,
                            "verdict": verdict}
        it["status"] = "끝남"
        done.append(it)
    return done


def text_for_model(doc, weeks):
    """재료에 실을 대장 요약."""
    live = [x for x in doc.get("items", []) if x["status"] in ("제안됨", "진행중")]
    done = [x for x in doc.get("items", []) if x["status"] == "끝남" and x.get("result")]
    L = ["\n[실험 대장]"]
    if not live and not done:
        L.append("  아직 비어 있다. 이번 주에 한두 개 제안해라.")
        return "\n".join(L)
    for it in done[-4:]:
        r = it["result"]
        v = f"{r['base']} → {r['now']}" + (f" ({r['pct']:+.0f}%)" if r.get("pct") is not None else "")
        L.append(f"  [끝남·{r['verdict']}] {it['title']}")
        L.append(f"        {it['metricLabel']} {v}")
    for it in live:
        mark = "진행중" if it["status"] == "진행중" else "아직 실행 안 함"
        L.append(f"  [{mark}] {it['title']}")
        L.append(f"        볼 지표: {it['metricLabel']} (시작값 {it.get('baseValue')})")
    L.append("  · 이미 대장에 있는 것과 같은 제안을 또 하지 마라.")
    L.append("  · '끝남' 으로 판정된 것은 결과를 보고서에서 한 번 짚어 줘라.")
    return "\n".join(L)


def show(doc):
    items = doc.get("items") or []
    if not items:
        log("대장이 비어 있다")
        return
    for it in items:
        r = it.get("result") or {}
        tail = ""
        if r:
            tail = f" · {r.get('verdict')} ({r.get('base')}→{r.get('now')})"
        log(f"  [{it['status']:<4}] {it['id']:<7} {it['title']}{tail}")
        log(f"           지표 {it['metricLabel']} · 제안 {it['proposedAt']}"
            + (f" · 시작 {it['startedWeek']}" if it.get("startedWeek") else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--start", help="실행했다고 표시할 실험 id")
    ap.add_argument("--drop", help="버릴 실험 id")
    ap.add_argument("--why", default="", help="버리는 이유")
    a = ap.parse_args()

    doc = load()
    if a.start:
        it = next((x for x in doc["items"] if x["id"] == a.start), None)
        if not it:
            log(f"❌ {a.start} 가 없다")
            return 2
        import ga4_store
        weeks = ga4_store.load("weekly").get("weeks") or []
        it["status"] = "진행중"
        it["startedWeek"] = weeks[-1]["week"] if weeks else None
        # 시작 시점의 값으로 다시 잡는다 — 제안한 주와 실행한 주가 다를 수 있다.
        if weeks:
            it["baseValue"] = value_of(weeks[-1], it["metric"])
        save(doc)
        log(f"✅ {it['id']} 진행중 · 기준 {it['metricLabel']}={it['baseValue']}")
        return 0
    if a.drop:
        it = next((x for x in doc["items"] if x["id"] == a.drop), None)
        if not it:
            log(f"❌ {a.drop} 가 없다")
            return 2
        it["status"] = "버림"
        it["why_dropped"] = a.why
        save(doc)
        log(f"✅ {it['id']} 버림")
        return 0
    show(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
