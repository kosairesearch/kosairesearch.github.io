#!/usr/bin/env python3
"""
KOS ai — AI 리포트 '대량' 생성 (Message Batches API · 50% 저렴)

시총 상위 N개(기본 100) 종목 리포트를 Batch API로 한 번에 제출/회수합니다.
generate_reports.py 의 프롬프트·DART·파싱 로직을 그대로 재사용합니다.

모드:
  submit   — 대상 종목 요청을 묶어 배치 제출, data/batch_state.json 저장
  collect  — 저장된 batch_id 결과를 회수해 data/reports.js 갱신
  auto     — submit 후 완료까지 폴링하고 collect (기본)
  dump     — 회수한 배치의 결과를 다시 읽어 저장하지 못한 글의 사정을 찍는다(모델을 부르지 않는다 · 저장 · 커밋 없음)

환경변수: ANTHROPIC_API_KEY(필수), DART_API_KEY, REPORT_MODEL, REPORT_TOP_N,
          REPORT_FRESH_DAYS, REPORT_FORCE, BATCH_MAX_WAIT_SEC, REPORT_TICKERS, REPORT_SKIP_FAILED

쓰는 곳: 신규 상장 작업(new_listings.yml · 평일 밤), 공시 트리거(filing_reports.yml — 새 형식을 만들 수 없는 종목의
옛 형식 리포트를 그 공시로 다시 쓴다 · 2026-10-27), 손으로 돌리는 대량 생성(generate_reports_batch.yml).
"""

import os
import re
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
# 공시 트리거가 넘긴 종목(REPORT_SKIP_FAILED=1)은 저장하지 못한 횟수가 FAIL_MAX 번인 종목을 뺀다(2026-10-27). 공시 트리거는
# 리포트가 공시보다 낡으면 하루 세 번 같은 종목을 다시 고른다 — 같은 이유로 또 걸리면 돈만 나간다. 리포트 v2 와 같이
# 마지막 실패에서 FAIL_RESET_DAYS(14일)가 지나면 다시 고른다. 손으로 종목을 지정한 실행은 빼지 않는다.
SKIP_FAILED = os.getenv("REPORT_SKIP_FAILED", "") == "1"
FAIL_RESET_DAYS = 14


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


def stuck_tickers(fails, today=None):
    """저장하지 못한 횟수가 FAIL_MAX 번 이상이고 마지막 실패가 FAIL_RESET_DAYS 안인 종목."""
    today = today or datetime.date.today()
    out = set()
    for tk, e in (fails or {}).items():
        if not isinstance(e, dict) or int(e.get("n", 0)) < FAIL_MAX:
            continue
        try:
            last = datetime.date.fromisoformat(str(e.get("last", ""))[:10])
        except ValueError:
            last = today                     # 날짜를 모르면 막는다(돈이 나가는 쪽을 피한다)
        if (today - last).days <= FAIL_RESET_DAYS:
            out.add(tk)
    return out


def bump_fail(fails, tk, why, as_of):
    n = int((fails.get(tk) or {}).get("n", 0)) + 1
    fails[tk] = {"n": n, "last": as_of, "why": str(why)[:120]}
    return n

# 2026-10-27 Sonnet 4.6 → Sonnet 5.5(사장 "소넷 5.5 사용해" — 배치 단가 $1.5/$7.5 → $1/$5). 사고는 그대로 adaptive.
MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-5-5")
TOP_N = int(os.getenv("REPORT_TOP_N", "100"))
FRESH_DAYS = int(os.getenv("REPORT_FRESH_DAYS", "6"))
FORCE = os.getenv("REPORT_FORCE", "") == "1"
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "4800"))  # 80분
# 저장 전 검토 — 회수한 리포트를 값싼 모델이 한 번 더 읽고 고칠 곳만 돌려준다(배치 · 리포트 한 편 약 2~4센트).
# 끄면 정리 · 검사만 하고, 검사에 걸리는 리포트는 저장하지 않는다. 기본은 끔(2026-10-09) — 시험에서 검토 모델이
# 반올림한 재료 수치로 정확한 본문 수치를 바꾸는 등 틀린 고침을 냈다. 고친 뒤 시험을 통과하면 NEW_LISTING_REVIEW=1 로 켠다.
REVIEW = os.getenv("NEW_LISTING_REVIEW", "0") == "1"
# 저장 전 교정(2026-10-23) — 검사에 걸린 글을 버리지 않고 걸린 문장만 값싼 모델이 고친다(리포트 v2 회수 단계와 같은
# check_report_text.repair · 배치로만). 전에는 걸리면 곧바로 버려, 10/23 모비콘텐츠테크가 '주당순이익 669원' 한 문장
# 때문에 작성비(약 0.4달러)를 날리고 다음 실행이 처음부터 다시 썼다. 교정 배치는 한 편에 1~2센트다.
REPAIR = os.getenv("NEW_LISTING_REPAIR", "1") != "0"
REPAIR_WAIT = int(os.getenv("NEW_LISTING_REPAIR_WAIT_SEC", "1800"))   # 교정 배치를 기다리는 시간(30분)
REPAIR_ROUNDS = 2                    # 한 번에 다 고치지 못하면 남은 위반으로 한 번 더

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
          "blocked_domains": g.BLOCKED_DOMAINS,
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
    if SKIP_FAILED:
        stuck = stuck_tickers(load_fails())
        held = [s["ticker"] for s in targets if s["ticker"] in stuck]
        if held:
            log(f"- 저장하지 못한 횟수가 {FAIL_MAX}번인 {len(held)}개는 다시 주문하지 않는다"
                f"(data/new_listing_fail.json · 마지막 실패에서 {FAIL_RESET_DAYS}일 뒤 다시 고른다): {','.join(held[:20])}")
            targets = [s for s in targets if s["ticker"] not in stuck]
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
                # 사고 토큰도 이 안에서 센다. 한 편에 4만 1천 안팎을 써 48,000 에 닿으면 글이 끝에서 잘렸다
                # (2026-10-23 디티에스 — 종합 의견까지 오지 않아 버렸다). 리포트 v2 와 같은 한도다. 쓴 만큼만 낸다.
                max_tokens=96000,
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
        "tickers": [r["custom_id"] for r in reqs],
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


def diagnose(message):
    """저장 문턱(valid_report)에 걸린 글의 사정 — 무엇이 빠졌고 JSON 이 어디서 깨졌는가(2026-10-27). 그날 옛 형식 110편 중
    3편이 정상 종료(end_turn)인데 필수 항목이 비어 버려졌고, 원문이 남지 않아 까닭을 알 수 없었다. 돈이 들지 않는다."""
    text = g.extract_text(message)
    m = re.search(r"===JSON_START===(.*?)===JSON_END===", text, re.S)
    out = {"stop": getattr(message, "stop_reason", None), "len": len(text),
           "markers": text.count("===JSON_START==="), "closed": bool(m)}
    chunk = (m.group(1) if m else text).strip()
    a, b = chunk.find("{"), chunk.rfind("}")
    chunk = chunk[a:b + 1] if a >= 0 and b > a else chunk
    try:
        json.loads(chunk)
        out["json"] = "ok"
    except json.JSONDecodeError as e:
        out["json"] = f"{e.msg} @{e.pos}/{len(chunk)}"
        out["near"] = chunk[max(0, e.pos - 160): e.pos + 160].replace("\n", "⏎")
    try:
        rep = g.parse_report(text)
    except Exception as e:                                   # noqa: BLE001
        rep, out["parse"] = None, type(e).__name__
    if isinstance(rep, dict):
        out["need"] = {"verdict": bool(rep.get("verdict")), "risks": len(rep.get("risks") or []),
                       "keypoints": len(rep.get("keypoints") or []), "business": bool(rep.get("business"))}
        out["keys"] = ",".join(sorted(rep))
    return out


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


class _Ask(BaseException):
    """check_report_text.repair 가 보내려던 요청. 모델을 부르지 않고 받아 둔다 — BaseException 이라 부르는 쪽의
    'except Exception' 이 삼키지 않는다."""

    def __init__(self, params):
        super().__init__()
        self.params = params


class _OneShot:
    """repair 에 넘기는 대리인 — 답이 없으면 요청을 _Ask 로 던지고, 있으면 그 답을 돌려준다. 즉시 호출은 하지 않는다."""

    def __init__(self, answer=None):
        outer = self
        self.answer = answer

        class _Msgs:
            def create(self, **kw):
                if outer.answer is None:
                    raise _Ask(kw)
                return outer.answer

        self.messages = _Msgs()


def repair_all(cl, todo):
    """검사에 걸린 글의 걸린 문장만 교정 배치로 고친다 — ({종목: (리포트, 남은 위반)}, 사용량).

    한 회차에 걸린 글 전부를 배치 하나로 보낸다. 고쳐서 위반이 줄었지만 남은 글만 다음 회차로 넘기고(REPAIR_ROUNDS),
    답이 없거나 고치지 못한 글은 그대로 돌려준다(부르는 쪽이 저장하지 않는다)."""
    import hashlib
    cur, use = dict(todo), {}
    left = [tk for tk, (_, bad) in cur.items() if bad]
    for rnd in range(1, REPAIR_ROUNDS + 1):
        jobs, ctx = {}, {}
        for tk in left:
            rep, bad = cur[tk]
            try:
                C.repair(_OneShot(), rep, bad)          # 고칠 섹션이 없으면 요청 없이 끝난다
            except _Ask as a:
                h = hashlib.sha1(json.dumps(a.params, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()
                jobs[f"fx{rnd}_{tk}_{h[:12]}"] = a.params
                ctx[f"fx{rnd}_{tk}_{h[:12]}"] = tk
        if not jobs:
            break
        try:
            got = C.send_batch(cl, jobs, wait_sec=REPAIR_WAIT, log=log, label="교정")
        except TimeoutError as e:
            log(f"  · ⚠️ {e} — 이번 교정은 받지 않는다")
            break
        left = []
        for key, msg in got.items():
            tk = ctx[key]
            rep, bad = cur[tk]
            if msg is None:
                log(f"  · ⚠️ {tk} 교정 답 없음")
                continue
            u = g.usage_of(msg)
            if u:
                g.add_usage(use, C.REPAIR_MODEL, u, batch=True)
            try:
                fixed = C.repair(_OneShot(msg), rep, bad)
            except Exception as e:                     # noqa: BLE001
                fixed = None
                log(f"  · ⚠️ {tk} 교정 답을 읽지 못함: {type(e).__name__}: {e}")
            if not fixed:
                log(f"  · ⚠️ {tk} 교정이 위반을 줄이지 못함 — 고치기 전 글로 판정한다")
                continue
            rep2 = C.prepare(fixed[0])
            cur[tk] = (rep2, C.check(rep2))
            log(f"  · ✏️ {tk} 표현 교정 {len(bad)}건 → 남은 {len(cur[tk][1])}건")
            if cur[tk][1]:
                left.append(tk)
        if not left:
            break
    return cur, use


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
        # 협의 없이 쓰지 않는 사이트(치킨스탁 등)가 검색 결과 · 인용에 들어왔으면 그 글은 저장하지 않는다(2026-10-19).
        leak = g.no_use_urls(result.result.message)
        if leak:
            fail += 1
            bump_fail(fails, tk, "쓰지 않기로 한 사이트가 검색 결과에 들어옴", as_of)
            log(f"  · 🚫 {tk} 쓰지 않기로 한 사이트가 검색 결과에 들어왔다({leak[0]} 등 {len(leak)}건) — 저장하지 않음")
            continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            if not g.valid_report(rep):
                fail += 1
                why = getattr(result.result.message, "stop_reason", None)   # max_tokens 면 한도에 닿아 잘린 것이다
                bump_fail(fails, tk, f"불완전(잘림 의심 · 중단 사유 {why})", as_of)
                log(f"  · ⚠️ {tk} 불완전(잘림 의심 · 중단 사유 {why}) — 건너뜀, 기존 유지")
                d = diagnose(result.result.message)
                log(f"    사정: JSON {d.get('json')} · 필수 항목 {d.get('need')} · 표시 {d.get('markers')}개"
                    + (f" · 깨진 곳 …{d['near']}…" if d.get("near") else ""))
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
    # 검사(check)를 거쳐 위반이 하나도 없는 글만 저장한다. 걸린 글은 교정(배치)으로 걸린 문장만 고친 뒤 다시 보고(2026-10-23),
    # 그래도 걸리면 저장하지 않는다 — 신규 상장 작업이 리포트 없는 종목을 다음 실행에서 다시 주문한다.
    reviewed, judged = {}, {}
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
        judged[tk] = (rep, C.check(rep))
    # 걸린 글은 버리기 전에 걸린 문장만 고친다(배치). 고친 뒤에도 남으면 저장하지 않는다.
    to_fix = {tk: v for tk, v in judged.items() if v[1]}
    if to_fix and REPAIR:
        try:
            fixed, use_fx = repair_all(cl, to_fix)
        except Exception as e:                         # noqa: BLE001
            fixed, use_fx = {}, {}
            log(f"  · ⚠️ 교정 배치 실패: {type(e).__name__}: {e} — 걸린 글은 저장하지 않는다(다음 실행이 다시 주문한다)")
        judged.update(fixed)
        if use_fx:
            for mdl, a in use_fx.items():
                log(g.usage_line(mdl, a, "교정 배치"))
                a["usd"] = round(a["usd"], 4)
            state["usage_repair"] = use_fx     # 교정 배치 사용량 — 생성 배치(usage)와 섞지 않는다
    for tk, (rep, bad) in judged.items():
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


def dump(cl):
    """회수한 배치의 결과를 다시 읽어 종목마다 사정(diagnose)과 글의 끝부분을 찍는다. 모델을 부르지 않는다 — 결과 조회는
    무료다. 대상은 REPORT_TICKERS(비우면 저장하지 못한 종목 — data/new_listing_fail.json), 배치는 DUMP_BATCH_ID(비우면 상태 파일)."""
    st = json.loads(STATE_JS.read_text(encoding="utf-8")) if STATE_JS.exists() else {}
    bid = os.getenv("DUMP_BATCH_ID", "").strip() or st.get("batch_id")
    want = [t for t in os.getenv("REPORT_TICKERS", "").replace(" ", "").split(",") if t] or sorted(load_fails())
    log(f"## 배치 결과 진단 — {bid} · 대상 {len(want)}개")
    seen = set()
    for r in cl.messages.batches.results(bid):
        tk = r.custom_id
        if tk not in want:
            continue
        seen.add(tk)
        if r.result.type != "succeeded":
            log(f"### {tk} — 결과 {r.result.type}")
            continue
        log(f"### {tk}")
        for k, v in diagnose(r.result.message).items():
            log(f"  · {k}: {v}")
        log("  · 끝 400자: " + g.extract_text(r.result.message)[-400:].replace("\n", "⏎"))
    missing = [t for t in want if t not in seen]
    if missing:
        log(f"- 이 배치에 없는 종목: {','.join(missing)}")
    return seen


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    cl = client()
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if mode == "dump":
        dump(cl)
    elif mode == "submit":
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
