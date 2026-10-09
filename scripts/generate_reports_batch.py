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
import check_report_text as C   # 저장 전 정리 · 검사 · 검토(2026-10-09 — 리포트 v2 · 업종 분석과 같은 기준)

ROOT = Path(__file__).resolve().parent.parent
STATE_JS = ROOT / "data" / "batch_state.json"
# 저장하지 못한 신규 상장 종목의 연속 횟수(2026-10-09). 저장하지 못한 종목은 '리포트 없음'으로 남아 신규 상장 작업이 평일 밤마다
# 다시 주문하는데, 같은 이유(검사 위반 · 잘린 글)로 계속 걸리면 상한 없이 돈이 나간다. new_listings.py 가 FAIL_MAX 번째부터
# 재시도하지 않는다. 저장하면 그 종목 줄을 지운다. 사람이 다시 시도하게 하려면 이 파일에서 그 종목을 지운다.
FAIL_JS = ROOT / "data" / "new_listing_fail.json"
FAIL_MAX = 3


def load_fails():
    try:
        return json.loads(FAIL_JS.read_text(encoding="utf-8")) if FAIL_JS.exists() else {}
    except Exception:                                            # noqa: BLE001
        return {}


def save_fails(fails):
    if fails:
        FAIL_JS.write_text(json.dumps(fails, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif FAIL_JS.exists():
        FAIL_JS.unlink()


def bump_fail(fails, tk, why, as_of):
    n = int((fails.get(tk) or {}).get("n", 0)) + 1
    fails[tk] = {"n": n, "last": as_of, "why": str(why)[:120]}
    return n

MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-4-6")
TOP_N = int(os.getenv("REPORT_TOP_N", "100"))
FRESH_DAYS = int(os.getenv("REPORT_FRESH_DAYS", "6"))
FORCE = os.getenv("REPORT_FORCE", "") == "1"
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "4800"))  # 80분
# 저장 전 검토 — 회수한 리포트를 값싼 모델이 한 번 더 읽고 고칠 곳만 돌려준다(배치 · 리포트 한 편 약 2~4센트).
# 끄면 정리 · 검사만 하고, 검사에 걸리는 리포트는 저장하지 않는다. 기본은 끔(2026-10-09) — 시험에서 검토 모델이
# 반올림한 재료 수치로 정확한 본문 수치를 바꾸는 등 틀린 고침을 냈다. 고친 뒤 시험을 통과하면 NEW_LISTING_REVIEW=1 로 켠다.
REVIEW = os.getenv("NEW_LISTING_REVIEW", "0") == "1"

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
          "blocked_domains": ["namu.wiki", "librewiki.net", "dcinside.com", "fmkorea.com"],
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    # 즉시 호출 창구를 막는다(2026-10-09 — 저장 전 검토를 붙이며). 생성 · 검토 모두 배치로만 보낸다.
    def _blocked(*_a, **_kw):
        raise RuntimeError("신규 상장 리포트는 Batch API 로만 보낸다(요금 절반) — messages.batches.create 를 쓸 것")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked
    return cl


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


def fix_shape(rep):
    """곁키에 빠진 영문을 제자리로 — {"body": {"ko": …, "body_en_placeholder": ""}, "body_en": "…"} → {"body": {"ko", "en"}}.
    2026-10-09 신규 상장 리포트 두 편의 종합 의견이 이 꼴이라 영어 화면에 한국어가 그대로 나왔다(리포트 v2 는 normalize_shape 가 한다)."""
    def rec(o):
        if isinstance(o, list):
            return [rec(x) for x in o]
        if not isinstance(o, dict):
            return o
        o = {k: rec(v) for k, v in o.items()}
        for k in list(o):
            if k.endswith("_en") and isinstance(o[k], str):
                base = k[:-3]
                tgt = o.get(base)
                if isinstance(tgt, dict) and "ko" in tgt and not (tgt.get("en") or "").strip():
                    tgt["en"] = o.pop(k)
        if "ko" in o:
            if not (o.get("en") or "").strip():
                side = next((k for k in o if k.endswith("_en") and isinstance(o[k], str) and o[k].strip()), None)
                if side:
                    o["en"] = o[side]
            for k in [k for k in o if k not in ("ko", "en")]:
                o.pop(k)
        return o
    return rec(rep)


def review_all(cl, cand, as_of):
    """검토 배치 하나 — {종목: (고친 리포트 또는 None, 기록)}."""
    import hashlib
    jobs, ctx = {}, {}
    for tk, rep in cand.items():
        part = {k: v for k, v in rep.items() if k not in C._NOT_TEXT}
        names = (f"  - {rep.get('name') or tk}({C.clean_en(rep.get('name_en'))}) — 이 리포트의 회사"
                 + (f" · 업종 분류 {rep.get('sector')}" if rep.get("sector") else ""))
        params = C.review_params(part, kind="report", as_of=(as_of or "")[:10], names=names, hits=C.check(rep),
                                 hints=C.en_gap_hints(rep))
        key = "rv_" + tk + "_" + hashlib.sha1(json.dumps(params, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:12]
        jobs[key] = params
        ctx[key] = (tk, part, names)
    got = C.send_batch(cl, jobs, wait_sec=MAX_WAIT, log=log)
    out, use = {}, {}
    for key, msg in got.items():
        tk, part, names = ctx[key]
        if msg is None:
            out[tk] = (None, "검토 답 없음")
            continue
        u = g.usage_of(msg)
        if u:
            g.add_usage(use, C.REVIEW_MODEL, u, batch=True)
        new_part, applied, dropped = C.apply_review(part, C.message_text(msg), extra=names, as_of=as_of or "")
        if new_part is None:
            out[tk] = (None, "검토 답을 읽지 못함 — " + "; ".join(dropped))
            continue
        merged = dict(cand[tk])
        merged.update(new_part)
        out[tk] = (merged, f"검토 고침 {applied}곳" + (f" · 버림 {len(dropped)}곳" if dropped else ""))
    for mdl, a in use.items():
        log(g.usage_line(mdl, a, "검토 배치"))
        a["usd"] = round(a["usd"], 4)
    return out, use


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
    fails = load_fails()     # 저장하지 못한 연속 횟수 — 글이 왔는데 쓰지 못한 경우만 센다(돈은 나갔다)
    cand = {}    # 검토 · 검사를 거칠 글 — {종목: 리포트}
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
                bump_fail(fails, tk, "불완전(잘림 의심)", as_of)
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
            cand[tk] = C.prepare(fix_shape(rep))
        except Exception as e:
            fail += 1
            bump_fail(fails, tk, f"파싱 실패 {type(e).__name__}", as_of)
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e}")

    # 저장 전 검토 · 검사(2026-10-09). 전에는 회수한 글을 그대로 저장해, 신규 상장 리포트에 영문 속 한글 · 가치 단정 ·
    # 받은 자료 언급('제공된 기준 데이터상 0.0조원') · 곁키에 빠진 영문이 그대로 걸렸다. 정리(prepare) → 검토(배치) →
    # 검사(check)를 거쳐 위반이 하나도 없는 글만 저장한다. 걸린 종목은 저장하지 않는다 — 신규 상장 작업이 리포트 없는 종목을
    # 다음 실행에서 다시 주문한다.
    reviewed = {}
    if cand and REVIEW:
        try:
            reviewed, use_rv = review_all(cl, cand, state.get("created") or as_of)
            if use_rv:
                state["usage_review"] = use_rv     # 검토 배치 사용량 — 생성 배치(usage)와 섞지 않는다
        except Exception as e:                                   # noqa: BLE001
            log(f"  · ⚠️ 검토 배치 실패: {type(e).__name__}: {e} — 이번 회수분은 저장하지 않는다(다음 실행이 다시 주문한다)")
            reviewed = {tk: (None, "검토 배치 실패") for tk in cand}
    for tk, rep in cand.items():
        if REVIEW:
            got, note = reviewed.get(tk, (None, "검토 답 없음"))
            if got is None:
                fail += 1
                log(f"  · ⚠️ {tk} {note} — 저장하지 않음")
                continue
            rep = C.prepare(got)
            log(f"  · 🔎 {tk} {note}")
        bad = C.check(rep)
        if bad:
            fail += 1
            rules = ", ".join(sorted({h['rule'] for h in bad}))
            n = bump_fail(fails, tk, f"검사 위반({rules})", as_of)
            log(f"  · 🚫 {tk} 검사 위반 {len(bad)}건({rules}) — 저장하지 않음 · "
                f"[{bad[0]['section']}] {bad[0]['match']!r} · {bad[0]['sentence'][:60]}"
                + (f" · 연속 {n}번째 — 신규 상장 작업이 더는 다시 주문하지 않는다" if n >= FAIL_MAX else ""))
            continue
        reports[tk] = rep
        fails.pop(tk, None)
        ok += 1

    g.write_reports(reports, state.get("model", MODEL), as_of)
    save_fails(fails)
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
