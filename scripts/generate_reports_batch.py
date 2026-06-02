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
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def load_existing():
    reports, fresh = {}, set()
    if STATE_JS.parent.joinpath("reports.js").exists():
        try:
            raw = (STATE_JS.parent / "reports.js").read_text(encoding="utf-8")
            prev = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            if "샘플" not in str(prev.get("model", "")):
                reports = prev.get("reports", {}) or {}
                today = datetime.date.today()
                for tk, r in reports.items():
                    try:
                        d = datetime.date.fromisoformat(r.get("reportDate", ""))
                        if (today - d).days <= FRESH_DAYS:
                            fresh.add(tk)
                    except Exception:
                        pass
        except Exception as e:
            log(f"- (기존 리포트 로드 실패) {e}")
    return reports, fresh


def submit(cl, as_of):
    data = g.load_stocks()
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
                max_tokens=32000,
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
    report_date = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")

    reports, _ = load_existing()
    ok, fail = 0, 0
    for result in cl.messages.batches.results(batch_id):
        tk = result.custom_id
        rt = result.result.type
        if rt != "succeeded":
            fail += 1
            log(f"  · ⚠️ {tk} 결과 {rt}")
            continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            st = by_tk.get(tk, {})
            rep.update({
                "ticker": tk, "name": st.get("name", tk),
                "name_en": st.get("name_en", st.get("name", tk)),
                "sector": st.get("sector", ""), "market": st.get("market", ""),
                "reportDate": report_date, "dataDate": data.get("dataDate", ""),
            })
            reports[tk] = rep
            ok += 1
        except Exception as e:
            fail += 1
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e}")

    payload = {"lastUpdated": as_of, "model": state.get("model", MODEL), "reports": reports}
    (ROOT / "data" / "reports.js").write_text(
        "// KOS ai — AI 리서치 리포트 (자동 생성). 직접 수정하지 마세요.\n"
        "window.KOS_REPORTS = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8")
    log(f"\n✅ 회수 완료 · 성공 {ok}/실패 {fail} · 총 보유 {len(reports)}개 → data/reports.js")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    cl = client()
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if mode == "submit":
        submit(cl, as_of)
    elif mode == "collect":
        collect(cl, as_of)
    else:  # auto
        bid = submit(cl, as_of)
        if not bid:
            return
        if poll(cl, bid):
            collect(cl, as_of)


if __name__ == "__main__":
    main()
