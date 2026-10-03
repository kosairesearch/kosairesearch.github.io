#!/usr/bin/env python3
"""
KOS ai — AI 리포트 '대량' 생성 (Message Batches API · 50% 저렴)

시총 상위 N개(기본 100) 종목 리포트를 Batch API로 한 번에 제출/회수합니다.
generate_reports.py 의 프롬프트·DART·파싱 로직을 그대로 재사용합니다.

모드:
  submit   — 대상 종목 요청을 묶어 배치 제출, data/batch_state.json 저장
  collect  — 저장된 batch_id 결과를 회수해 data/reports.js 갱신
  auto     — submit 후 완료까지 폴링하고 collect (기본)

환경변수: ANTHROPIC_API_KEY(필수), DART_API_KEY, REPORT_MODEL, REPORT_TOP_N,
          REPORT_FRESH_DAYS, REPORT_FORCE, BATCH_MAX_WAIT_SEC
"""

import os
import sys
import json
import time
import datetime
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

import generate_reports as g  # 프롬프트/DART/파싱 재사용 (import 시 main 실행 안 됨)

ROOT = Path(__file__).resolve().parent.parent
STATE_JS = ROOT / "data" / "batch_state.json"

MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-4-6")
TOP_N = int(os.getenv("REPORT_TOP_N", "100"))
FRESH_DAYS = int(os.getenv("REPORT_FRESH_DAYS", "6"))
FORCE = os.getenv("REPORT_FORCE", "") == "1"
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "4800"))  # 80분

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
          "blocked_domains": ["namu.wiki", "librewiki.net", "dcinside.com", "fmkorea.com"],
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def load_existing():
    reports = g.load_existing_reports()
    fresh = set()
    today = datetime.date.today()
    for tk, r in reports.items():
        try:
            d = datetime.date.fromisoformat(r.get("reportDate", ""))
            if (today - d).days <= FRESH_DAYS:
                fresh.add(tk)
        except Exception:
            pass
    return reports, fresh


def submit(cl, as_of):
    data = g.load_stocks()
    tickers_env = os.getenv("REPORT_TICKERS", "").replace(" ", "")
    if tickers_env:
        want = [t for t in tickers_env.split(",") if t]
        by_tk = {s["ticker"]: s for s in data["stocks"]}
        stocks = [by_tk[t] for t in want if t in by_tk]
    else:
        stocks = sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:TOP_N]
    _, fresh = load_existing()
    targets = [s for s in stocks if FORCE or s["ticker"] not in fresh]
    log(f"## 🤖 Batch 제출 — 대상 {len(targets)}개 / 상위 {TOP_N}개 (최근 {len(fresh)}개 건너뜀) · 모델 {MODEL}")
    if not targets:
        log("- 갱신할 종목이 없습니다(모두 최근). 종료.")
        return None

    reqs = []
    for st in targets:
        dart = g.get_dart_financials(st["ticker"])
        prompt = g.build_prompt(st, as_of, dart)
        reqs.append(Request(
            custom_id=st["ticker"],
            params=MessageCreateParamsNonStreaming(
                model=MODEL,
                max_tokens=48000,
                system=[{"type": "text", "text": g.SYSTEM, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=[{"role": "user", "content": prompt}],
            ),
        ))
        log(f"  · 준비 {st['ticker']} {st['name']} (DART {'O' if dart else 'X'})")

    batch = cl.messages.batches.create(requests=reqs)
    state = {
        "batch_id": batch.id,
        "created": as_of,
        "model": MODEL,
        "dataDate": data.get("dataDate", ""),
        "count": len(reqs),
        "pending": True,      # 회수하면 지운다 — 다음 실행이 못 받은 배치를 먼저 받는다(collect_pending)
    }
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"- ✅ 배치 제출 완료: {batch.id} ({len(reqs)}건) → data/batch_state.json")
    return batch.id


def poll(cl, batch_id):
    waited = 0
    while waited < MAX_WAIT:
        b = cl.messages.batches.retrieve(batch_id)
        rc = b.request_counts
        log(f"  · 상태 {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
        if b.processing_status == "ended":
            return True
        time.sleep(60)
        waited += 60
    log(f"- ⏳ {MAX_WAIT//60}분 내 미완료. 나중에 `collect` 모드로 회수하세요.")
    return False


def collect(cl, as_of):
    if not STATE_JS.exists():
        log("❌ data/batch_state.json 이 없습니다. 먼저 submit 하세요.")
        sys.exit(1)
    state = json.loads(STATE_JS.read_text(encoding="utf-8"))
    batch_id = state["batch_id"]
    b = cl.messages.batches.retrieve(batch_id)
    if b.processing_status != "ended":
        log(f"- 아직 처리 중({b.processing_status}). 나중에 다시 collect 하세요.")
        return False

    data = g.load_stocks()
    by_tk = {s["ticker"]: s for s in data["stocks"]}
    now_kst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    report_date = now_kst.strftime("%Y-%m-%d")
    report_ts = now_kst.strftime("%Y-%m-%d %H:%M")

    reports, _ = load_existing()
    ok, fail = 0, 0
    usage = {}   # 모델별 사용량 — 버린 결과까지 센다(돈은 나갔다)
    for result in cl.messages.batches.results(batch_id):
        tk = result.custom_id
        rt = result.result.type
        if rt == "succeeded":
            u = g.usage_of(result.result.message)
            if u:
                g.add_usage(usage, state.get("model", MODEL), u, batch=True)
        if rt != "succeeded":
            fail += 1
            log(f"  · ⚠️ {tk} 결과 {rt}")
            continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            if not g.valid_report(rep):
                fail += 1
                log(f"  · ⚠️ {tk} 불완전(잘림 의심) — 건너뜀, 기존 유지")
                continue
            srcs = g.collect_sources(result.result.message)
            if srcs:
                rep["sources"] = srcs[:18]
            st = by_tk.get(tk, {})
            rep.update({
                "ticker": tk, "name": st.get("name", tk),
                "name_en": st.get("name_en", st.get("name", tk)),
                "sector": st.get("sector", ""), "categories": st.get("categories", []),
                "market": st.get("market", ""),
                "reportDate": report_date, "reportTs": report_ts,
                "dataDate": data.get("dataDate", ""),
            })
            reports[tk] = rep
            ok += 1
        except Exception as e:
            fail += 1
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e}")

    g.write_reports(reports, state.get("model", MODEL), as_of)
    log(f"\n✅ 회수 완료 · 성공 {ok}/실패 {fail} · 총 보유 {len(reports)}개 → data/reports/ + reports-index.js")
    for mdl, a in usage.items():
        log(g.usage_line(mdl, a, "배치"))
        a["usd"] = round(a["usd"], 3)
    state.pop("pending", None)
    state["collected"] = as_of
    if usage:
        state["usage"] = usage
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def collect_pending(cl, as_of):
    """지난 실행이 시간 안에 받지 못한 배치를 먼저 받는다. 돈은 이미 나갔다 — 받지 않으면 리포트가 없는
    것으로 보여 같은 종목을 다시 주문한다(2026-09-24 1건이 80분을 넘겨 그대로 버려졌다). 받은 리포트는
    '최근' 이 되어 바로 이어지는 주문에서 빠진다. 'pending' 표시는 이 판부터 붙는다 — 표시가 없는 옛 상태
    파일은 이미 받았는지 알 수 없어 건드리지 않는다(다시 받으면 날짜만 바뀐다)."""
    if not STATE_JS.exists():
        return
    try:
        st = json.loads(STATE_JS.read_text(encoding="utf-8"))
    except Exception:
        return
    if not st.get("pending") or not st.get("batch_id"):
        return
    try:
        b = cl.messages.batches.retrieve(st["batch_id"])
    except Exception as e:
        log(f"- 지난 배치 {st['batch_id']} 를 찾지 못해 건너뛴다({type(e).__name__})")
        st.pop("pending", None)
        st["abandoned"] = as_of
        STATE_JS.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    if b.processing_status != "ended":
        log(f"- 지난 배치 {st['batch_id']} 가 아직 처리 중({b.processing_status}) — 다음 실행에서 받는다")
        return
    log(f"- 지난 실행이 받지 못한 배치 {st['batch_id']} 를 먼저 회수한다")
    collect(cl, as_of)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    cl = client()
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if mode == "submit":
        submit(cl, as_of)
    elif mode == "collect":
        collect(cl, as_of)
    else:  # auto
        collect_pending(cl, as_of)
        if STATE_JS.exists() and json.loads(STATE_JS.read_text(encoding="utf-8")).get("pending"):
            # 지난 배치가 아직 처리 중이다. 새로 주문하면 상태 파일을 덮어써 지난 배치를 잃는다.
            log("- 지난 배치를 받기 전에는 새로 주문하지 않는다 — 다음 실행에서 이어 간다")
            return
        bid = submit(cl, as_of)
        if not bid:
            return
        if poll(cl, bid):
            collect(cl, as_of)


if __name__ == "__main__":
    main()
