#!/usr/bin/env python3
"""실제 청구 내역 조회 — Anthropic 관리자 키로 콘솔의 비용 · 사용량 기록을 받아 월별 · 모델별 · 항목별로 묶는다(돈 안 듦).

    ANTHROPIC_ADMIN_KEY=... KEY=<공개 열쇠 한 줄> python3 scripts/billing_report.py     # 잠근 줄만 찍는다

2026-10-27 사장 "저번 분기에 모든 종목 리포트를 다 작성하는데 10만원 들었다". 우리 사용량 기록(응답의 usage × 정가)으로는
같은 작업이 그 열 배로 나와, 실제 청구서를 직접 봐야 차이가 어디서 났는지 확정된다. 콘솔의 비용(Cost) · 사용량(Usage) 화면과
같은 자료를 관리자 키로 받는다(`/v1/organizations/cost_report` · `/v1/organizations/usage_report/messages` — 읽기만 한다).

  · 금액은 비용 기록(cost_report · 하루 단위 · 센트 단위 문자열)을 쓰고, 설명(description)으로 묶어 모델 · 항목(입력 · 출력 ·
    캐시 쓰기 · 캐시 읽기 · 웹 검색) · 요금 등급(배치 · 일반)을 가른다.
  · 토큰 수는 사용량 기록(usage_report · 하루 단위 · 모델 · 요금 등급별)으로 따로 센다 — 우리 기록과 견줄 때 쓴다.
  · 결과는 공개 실행 기록에 그대로 찍지 않는다 — 묻는 세션이 넘긴 공개 열쇠(KEY)로 잠근 줄만 찍는다(scripts/marketing_seal.py).
    열쇠가 없으면 아무 숫자도 찍지 않고 끝난다. 관리자 키는 어디에도 찍지 않는다.
지키는 검사 scripts/tests/billing_report_test.py.
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

API = "https://api.anthropic.com/v1/organizations"
SINCE = os.getenv("BILLING_SINCE", "2026-06-01")


class BillingError(Exception):
    pass


def _http_get(url, admin_key):
    req = urllib.request.Request(url, headers={"x-api-key": admin_key, "anthropic-version": "2023-06-01",
                                               "user-agent": "kosai-billing-report/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            raise BillingError(f"관리자 키가 거절됐다({e.code}) — 콘솔의 관리자 키(sk-ant-admin01-…)인지, 만료되지 않았는지 확인할 것")
        raise BillingError(f"조회 실패({e.code}): {body}")


def fetch_all(path, params, admin_key, get=None):
    """기간 전체를 쪽(page)을 넘기며 받는다 → 하루 단위 칸(bucket)의 목록."""
    get = get or _http_get
    out, page = [], None
    for _ in range(200):
        q = list(params)
        if page:
            q.append(("page", page))
        res = get(f"{API}/{path}?{urllib.parse.urlencode(q)}", admin_key)
        out.extend(res.get("data") or [])
        if not res.get("has_more"):
            return out
        page = res.get("next_page")
        if not page:
            return out
    raise BillingError("쪽이 너무 많다 — 기간을 줄일 것")


def _dollars(amount):
    """비용 기록의 금액(센트 단위 문자열) → 달러."""
    try:
        return float(amount) / 100.0
    except (TypeError, ValueError):
        return 0.0


def _item(r):
    """비용 항목 이름 — 웹 검색 · 코드 실행은 그대로, 토큰은 종류별로."""
    ct = (r.get("cost_type") or "").lower()
    if ct and ct != "tokens":
        return {"web_search": "웹 검색", "code_execution": "코드 실행"}.get(ct, ct)
    tt = (r.get("token_type") or "").lower()
    if "output" in tt:
        return "출력"
    if "cache_read" in tt:
        return "캐시 읽기"
    if "cache_creation" in tt or "ephemeral" in tt:
        return "캐시 쓰기"
    if "input" in tt:
        return "입력"
    return tt or (r.get("description") or "기타")


def summarize_cost(buckets):
    """비용 기록 칸들 → 월별 합계 · 월별 모델 · 월별 항목 · 월별 요금 등급 · 일별 합계."""
    s = {"month": defaultdict(float), "model": defaultdict(lambda: defaultdict(float)),
         "item": defaultdict(lambda: defaultdict(float)), "tier": defaultdict(lambda: defaultdict(float)),
         "day": defaultdict(float)}
    for b in buckets:
        day = (b.get("starting_at") or "")[:10]
        mon = day[:7]
        for r in b.get("results") or []:
            usd = _dollars(r.get("amount"))
            if not usd:
                continue
            s["month"][mon] += usd
            s["day"][day] += usd
            s["model"][mon][r.get("model") or "(모델 없음)"] += usd
            s["item"][mon][_item(r)] += usd
            s["tier"][mon][r.get("service_tier") or "(등급 없음)"] += usd
    return s


def summarize_usage(buckets):
    """사용량 기록 칸들 → 월별 · 모델별 토큰과 웹 검색 횟수."""
    u = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    for b in buckets:
        mon = (b.get("starting_at") or "")[:7]
        for r in b.get("results") or []:
            key = f"{r.get('model') or '?'} · {r.get('service_tier') or '?'}"
            a = u[mon][key]
            cc = r.get("cache_creation") or {}
            a["입력"] += r.get("uncached_input_tokens") or 0
            a["캐시 쓰기"] += (cc.get("ephemeral_5m_input_tokens") or 0) + (cc.get("ephemeral_1h_input_tokens") or 0)
            a["캐시 읽기"] += r.get("cache_read_input_tokens") or 0
            a["출력"] += r.get("output_tokens") or 0
            a["웹 검색"] += (r.get("server_tool_use") or {}).get("web_search_requests") or 0
    return u


def render(cost, usage, since, until):
    L = []
    w = L.append
    w(f"실제 청구 내역 — {since} ~ {until} (Anthropic 콘솔 비용 기록 · 달러)")
    w("")
    w("[월별 합계]")
    for m in sorted(cost["month"]):
        w(f"  {m}  ${cost['month'][m]:,.2f}")
    w(f"  합계  ${sum(cost['month'].values()):,.2f}")
    for title, key in (("월별 · 모델별", "model"), ("월별 · 항목별", "item"), ("월별 · 요금 등급별(batch = 배치 할인)", "tier")):
        w("")
        w(f"[{title}]")
        for m in sorted(cost[key]):
            parts = sorted(cost[key][m].items(), key=lambda x: -x[1])
            w(f"  {m}  " + " · ".join(f"{k} ${v:,.2f}" for k, v in parts))
    w("")
    w("[금액이 큰 날 25일]")
    for d, v in sorted(cost["day"].items(), key=lambda x: -x[1])[:25]:
        w(f"  {d}  ${v:,.2f}")
    w("")
    w("[월별 · 모델별 사용량 — 토큰 · 웹 검색 횟수]")
    for m in sorted(usage):
        for k, a in sorted(usage[m].items(), key=lambda x: -x[1]["출력"]):
            w(f"  {m}  {k}  입력 {a['입력']:,} · 캐시 쓰기 {a['캐시 쓰기']:,} · 캐시 읽기 {a['캐시 읽기']:,} · "
              f"출력 {a['출력']:,} · 웹 검색 {a['웹 검색']:,}")
    return "\n".join(L)


def run(admin_key, since=SINCE, today=None, get=None):
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    until = (today + datetime.timedelta(days=1)).isoformat()
    base = [("starting_at", f"{since}T00:00:00Z"), ("ending_at", f"{until}T00:00:00Z")]
    cost = fetch_all("cost_report", base + [("group_by[]", "description"), ("limit", "31")], admin_key, get)
    usage = fetch_all("usage_report/messages", base + [("bucket_width", "1d"), ("group_by[]", "model"),
                                                       ("group_by[]", "service_tier"), ("limit", "31")], admin_key, get)
    return render(summarize_cost(cost), summarize_usage(usage), since, today.isoformat())


def main():
    import marketing_seal as M
    admin_key = os.getenv("ANTHROPIC_ADMIN_KEY", "").strip()
    key = os.getenv("KEY", "").strip()
    if not admin_key:
        print("::error title=관리자 키 없음::저장소 비밀 값 ANTHROPIC_ADMIN_KEY 가 없다 — 콘솔 관리자 키를 등록한 뒤 다시 돌린다")
        sys.exit(1)
    if not key:
        print("::error title=열쇠 없음::key 가 비어 있어 조회하지 않았다 — 청구 금액은 잠가서만 찍는다(공개 기록)")
        sys.exit(1)
    try:
        M.public_key(key)                 # 열쇠가 쓸 만한지 먼저 본다 — 조회한 뒤 못 잠그는 일이 없게
        text = run(admin_key)
        lines = M.seal(key, text.encode("utf-8"))
    except (BillingError, M.SealError) as e:
        print(f"::error title=청구 내역 조회 실패::{e}")
        sys.exit(1)
    print("\n".join(lines))
    print(f"잠근 답 {len(lines)}줄 — 묻는 세션에서 marketing_seal.py open 으로 연다")


if __name__ == "__main__":
    main()
