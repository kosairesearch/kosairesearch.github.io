#!/usr/bin/env python3
"""리포트 비용 시험 — 모델 · 웹 검색 횟수 · 사고 깊이를 바꿔 리포트 몇 편을 배치로 써 보고, 응답의 실제 사용량으로
편당 비용과 저장 전 검사 결과를 잰다. 아무것도 저장 · 커밋하지 않는다.

    REPORT_TRIAL_CONFIGS=h2,h0,s2l python3 scripts/report_trial.py        # 주문 → 기다림 → 결과
    REPORT_TRIAL_BATCH=msgbatch_… python3 scripts/report_trial.py          # 낸 시험 배치를 다시 받는다

2026-10-29 사장 "전 종목 다시 작성해도 20만원 이하가 나와야한다". 지금 설정(시총 상위 300 오퍼스 5.5 · 나머지 소넷 5.5 ·
웹 검색 최대 6회)으로는 그 기준을 넘는다. 어느 설정이 기준 안에 들고 글이 검사를 통과하는지 추정이 아니라 실제로 써서 잰다.

  · 설정 이름은 모델 한 글자(h 하이쿠 5.5 · s 소넷 5.5 · o 오퍼스 5.5) + 웹 검색 최대 횟수(0 이면 도구 없음) + 사고 깊이
    (l 낮음 · m 중간 · h 높음 · 없으면 모델 기본값)다. 예: h2 · h0 · s2l · s6(지금 설정 — 시총 301위 아래) · o6m(지금 상위 300).
  · 재료는 저장된 리포트의 정량(오늘 시세로 고친 값)이다 — 공시를 다시 부르지 않는다. 요청 모양(시스템 지시문 · 작성
    지시문 · 출력 한도 · 사고 adaptive · 검색 차단 도메인)은 리포트 v2 와 같고, 위 세 가지만 바꾼다.
  · 비용 = 응답 사용량 × 공식 배치 단가(2026-10-29 요금표) + 검색 1회 0.01달러. 하이쿠 5.5 는 한 요청의 입력 합계(캐시
    읽기 · 쓰기 포함)가 10만 토큰을 넘으면 높은 단가다 — 서버 도구 반복의 합계로 보수적으로 가른다.
  · 받은 글은 회수 단계와 같은 무료 정리(check_report_text.prepare)를 거쳐 check() 로 검사한다. 영문 채우기 · 교정 ·
    저장은 하지 않는다 — 그 대신 저장 문턱에 걸릴 글이 몇 편인지 센다.
지키는 검사 scripts/tests/report_trial_test.py.
"""

import datetime
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_reports as g          # noqa: E402 — 응답 글 꺼내기 · JSON 읽기 · 쓰지 않는 사이트
import generate_reports_v2 as v2      # noqa: E402 — 같은 지시문 · 재료 · 모양 검증
import check_report_text              # noqa: E402 — 저장 전 정리 · 검사

MODELS = {"h": "claude-haiku-5-5", "s": "claude-sonnet-5-5", "o": "claude-opus-5-5"}
EFFORTS = {"": None, "l": "low", "m": "medium", "h": "high"}
# 공식 배치 단가(USD / 100만 토큰 · 2026-10-29 요금표 — 정가의 절반): 입력 · 5분 캐시 쓰기 · 캐시 읽기 · 출력.
# 1시간 캐시 쓰기는 입력의 2배다. 하이쿠 5.5 는 한 요청의 입력 합계가 10만 토큰을 넘으면 '긴 프롬프트' 단가다.
PRICE = {
    "claude-opus-5-5": (2.0, 2.5, 0.10, 10.0),
    "claude-sonnet-5-5": (1.0, 1.25, 0.05, 5.0),
    "claude-haiku-5-5": (0.05, 0.0625, 0.005, 0.25),
    "claude-haiku-5-5@long": (0.25, 0.3125, 0.025, 1.25),
}
LONG = {"claude-haiku-5-5": 100_000}
SEARCH_USD = 0.01
# 기본 표본 — 시총 순위가 고르게 퍼지게(대형 · 중형 · 소형). 그 순위부터 저장된 정량이 있는 첫 종목.
RANKS = (1, 40, 150, 400, 900, 1500, 2100, 2500)
PREFIX = "trial-"
MAX_REQ = 60                           # 한 번에 낼 수 있는 시험 요청 수 — 실수로 큰돈이 나가지 않게
WAIT_SEC = int(os.getenv("REPORT_TRIAL_WAIT", "5400") or "5400")
KRW = float(os.getenv("REPORT_TRIAL_KRW", "1450") or "1450")   # 환산용 원/달러(보수적으로 높게 잡는다)


def parse_config(name):
    """'h2' · 's2l' · 'o6m' → {model, search, effort}. 모르는 이름이면 ValueError."""
    m = re.fullmatch(r"([hso])(\d)([lmh]?)", (name or "").strip())
    if not m:
        raise ValueError(f"설정 이름을 읽을 수 없다: {name!r} (예: h2 · h0 · s2l)")
    return {"model": MODELS[m[1]], "search": int(m[2]), "effort": EFFORTS[m[3]]}


def pick(stocks, tickers=None):
    """시험할 종목. 지정이 없으면 RANKS 의 시총 순위마다 저장된 정량이 있는 첫 종목."""
    ranked = sorted(stocks, key=lambda s: s.get("mcap") or 0, reverse=True)
    by_tk = {s["ticker"]: s for s in ranked}
    if tickers:
        missing = [t for t in tickers if t not in by_tk or not v2.stored_quant(t)]
        if missing:
            raise ValueError(f"시세 자료나 저장된 정량이 없는 종목: {','.join(missing)}")
        return [by_tk[t] for t in tickers]
    out, seen = [], set()
    for r in RANKS:
        for s in ranked[r - 1:]:
            if s["ticker"] not in seen and v2.stored_quant(s["ticker"]):
                out.append(s)
                seen.add(s["ticker"])
                break
    return out


def material(st):
    return v2._repriced(v2.stored_quant(st["ticker"]), st)


def request_params(cfg, st, q, as_of, stocks):
    """리포트 v2 와 같은 요청 — 모델 · 웹 검색 횟수 · 사고 깊이만 설정대로."""
    c = parse_config(cfg)
    p = {"model": c["model"], "max_tokens": 96000,
         "system": [{"type": "text", "text": v2.SYSTEM_V2, "cache_control": {"type": "ephemeral"}}],
         "thinking": {"type": "adaptive"},
         "messages": [{"role": "user", "content": v2.build_prompt_v2(st, q, as_of, stocks=stocks)}]}
    if c["search"]:
        tool = dict(v2.TOOLS[0])
        tool["max_uses"] = c["search"]
        p["tools"] = [tool]
    if c["effort"]:
        p["output_config"] = {"effort": c["effort"]}
    return p


def custom_id(cfg, tk):
    return f"{PREFIX}{cfg}-{tk}"


def split_id(cid):
    """'trial-h2-005930' → ('h2', '005930'). 시험 요청이 아니면 None."""
    m = re.fullmatch(re.escape(PREFIX) + r"([hso]\d[lmh]?)-([0-9A-Z]{6})", cid or "")
    return (m[1], m[2]) if m else None


def build_requests(configs, picked, as_of, stocks):
    reqs = []
    for st in picked:
        q = material(st)
        for cfg in configs:
            reqs.append({"custom_id": custom_id(cfg, st["ticker"]),
                         "params": request_params(cfg, st, q, as_of, stocks)})
    return reqs


def usage_of(message):
    """응답 하나의 사용량. 사고 토큰은 output_tokens_details 가 있을 때만."""
    u = getattr(message, "usage", None)
    if u is None:
        return None
    cc = getattr(u, "cache_creation", None)
    st = getattr(u, "server_tool_use", None)
    det = getattr(u, "output_tokens_details", None)
    return {"in": getattr(u, "input_tokens", 0) or 0,
            "cw": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cw1": (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0) if cc is not None else 0,
            "cr": getattr(u, "cache_read_input_tokens", 0) or 0,
            "out": getattr(u, "output_tokens", 0) or 0,
            "think": getattr(det, "thinking_tokens", None) if det is not None else None,
            "search": (getattr(st, "web_search_requests", 0) or 0) if st is not None else 0}


def cost(model, u):
    """(달러, 긴 프롬프트 단가였는가). 배치 단가 + 검색 요금."""
    key = model
    if model in LONG and u["in"] + u["cw"] + u["cr"] > LONG[model]:
        key = model + "@long"
    pin, pcw, pcr, pout = PRICE[key]
    tok = (u["in"] * pin + (u["cw"] - u["cw1"]) * pcw + u["cw1"] * pin * 2 + u["cr"] * pcr + u["out"] * pout) / 1e6
    return tok + u["search"] * SEARCH_USD, key != model


def text_size(rep):
    """두 말 칸의 글자 수 (한국어, 영어)."""
    ko = en = 0
    for c, k in v2._bilingual_slots(rep):
        val = c[k]
        if isinstance(val, dict):
            ko += len(val.get("ko") or "")
            en += len(val.get("en") or "")
        elif isinstance(val, str):
            ko += len(val)
    return ko, en


def evaluate(message, cfg, st, q):
    """응답 하나 → (결과 줄, 정리한 리포트 또는 None). 회수 단계의 무료 처리까지만 한다."""
    model = parse_config(cfg)["model"]
    row = {"cfg": cfg, "tk": st["ticker"], "name": st.get("name", ""), "model": model,
           "stop": getattr(message, "stop_reason", None), "usd": None, "long": False}
    u = usage_of(message)
    row["usage"] = u
    if u:
        row["usd"], row["long"] = cost(model, u)
    row["leak"] = len(g.no_use_urls(message))
    try:
        rep = g.parse_report(g.extract_text(message))
    except Exception as e:                                   # noqa: BLE001 — 시험은 사유를 남기고 계속한다
        row["error"] = f"JSON 읽기 실패({type(e).__name__})"
        return row, None
    if not isinstance(rep, dict):
        row["error"] = "JSON 이 객체가 아님"
        return row, None
    v2._sanitize(rep)
    v2.normalize_shape(rep)
    row["valid"] = v2.valid_v2(rep, quiet=True)
    row["valid_ko"] = row["valid"] or v2.valid_v2(rep, en=False, quiet=True)
    srcs = v2.collect_sources_v2(message)
    rep["sources"] = srcs[:18]
    rep.update({"v": 2, "model": model, "ticker": st["ticker"], "name": st.get("name", ""),
                "name_en": st.get("name_en") or st.get("name", ""), "market": st.get("market", ""),
                "sector": st.get("sector", ""), "quant": q})
    rep = check_report_text.prepare(rep)
    try:
        bad = check_report_text.check(rep) if row["valid_ko"] else []
    except Exception as e:                                   # noqa: BLE001
        bad = [{"rule": f"검사 예외 {type(e).__name__}", "level": "위험", "section": "", "sentence": ""}]
    row["bad"] = bad
    row["sources"] = len(srcs)
    row["ko"], row["en"] = text_size(rep)
    return row, rep


def stored_size(tk):
    """지금 저장된 리포트(지금 설정으로 쓴 글)의 글자 수와 출처 수 — 비교용."""
    try:
        rep = json.loads((v2.OUT_DIR / f"{tk}.json").read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return None
    ko, en = text_size(rep)
    return {"ko": ko, "en": en, "sources": len(rep.get("sources") or []), "model": rep.get("model", "")}


def _passes(r):
    return bool(r.get("valid")) and not r.get("bad") and not r.get("leak") and not r.get("error")


def render(rows, n_all, failed=()):
    """시험 결과 글. rows 는 evaluate 의 결과 줄들, failed 는 (custom_id, 사유)."""
    L = []
    w = L.append
    w("## 🧪 리포트 비용 시험 — 실제 사용량 × 공식 배치 단가(2026-10-29 요금표)")
    w("")
    w(f"전 종목 환산은 편당 평균 × {n_all:,}편, 원화는 1달러 {KRW:,.0f}원으로 계산했다(재작성 기준 20만 원 = "
      f"{200000 / KRW:,.0f}달러 · 편당 {200000 / KRW / n_all * 100:,.2f}센트).")
    w("")
    w("| 설정 | 편수 | 모양 통과 | 검사 통과 | 위험 위반 | 편당 평균 | 편당 최대 | 전 종목 환산 | 출력(사고) | 검색 | 출처 | 한국어 · 영어 글자 |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|")
    by = {}
    for r in rows:
        by.setdefault(r["cfg"], []).append(r)
    for cfg, rs in by.items():
        usd = [r["usd"] for r in rs if r.get("usd") is not None]
        avg = statistics.mean(usd) if usd else 0.0
        us = [r["usage"] for r in rs if r.get("usage")]
        out = statistics.mean(u["out"] for u in us) if us else 0
        th = [u["think"] for u in us if u.get("think") is not None]
        think = f"{statistics.mean(th):,.0f}" if th else "?"
        srch = statistics.mean(u["search"] for u in us) if us else 0
        ok = [r for r in rs if r.get("valid")]
        src = statistics.mean(r["sources"] for r in ok) if ok else 0
        ko = statistics.mean(r["ko"] for r in ok) if ok else 0
        en = statistics.mean(r["en"] for r in ok) if ok else 0
        risky = sum(1 for r in rs if any(h.get("level") == "위험" for h in (r.get("bad") or [])))
        total = avg * n_all
        w(f"| {cfg} ({rs[0]['model']}) | {len(rs)} | {len(ok)} | {sum(1 for r in rs if _passes(r))} | {risky} | "
          f"${avg:,.4f} ({avg * KRW:,.0f}원) | ${max(usd) if usd else 0:,.4f} | ${total:,.0f} ({total * KRW / 10000:,.1f}만 원) | "
          f"{out:,.0f} ({think}) | {srch:.1f} | {src:.1f} | {ko:,.0f} · {en:,.0f} |")
    long_n = sum(1 for r in rows if r.get("long"))
    if long_n:
        w("")
        w(f"하이쿠 5.5 '긴 프롬프트'(입력 합계 10만 토큰 초과) 단가로 센 응답 {long_n}건.")
    w("")
    w("### 위반 규칙(설정별 · 저장 문턱에 걸리는 것)")
    for cfg, rs in by.items():
        c = Counter(h.get("rule") for r in rs for h in (r.get("bad") or []))
        w(f"- {cfg}: " + (" · ".join(f"{k} {v}" for k, v in c.most_common()) if c else "없음"))
    w("")
    w("### 편별")
    w("| 설정 | 종목 | 비용 | 출력(사고) | 검색 | 출처 | 모양 | 위반 | 중단 사유 | 지금 저장된 글(글자 · 출처) |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda x: (x["tk"], x["cfg"])):
        u = r.get("usage") or {}
        stored = stored_size(r["tk"]) or {}
        rules = ", ".join(sorted({h.get("rule", "") for h in (r.get("bad") or [])})) or "-"
        w(f"| {r['cfg']} | {r['tk']} {r['name']} | ${(r.get('usd') or 0):,.4f} | {u.get('out', 0):,} ({u.get('think') if u.get('think') is not None else '?'}) | "
          f"{u.get('search', 0)} | {r.get('sources', 0)} | {'통과' if r.get('valid') else (r.get('error') or ('한국어만' if r.get('valid_ko') else '불완전'))} | "
          f"{rules}{' · 쓰지 않는 사이트' if r.get('leak') else ''} | {r.get('stop')} | "
          f"{stored.get('ko', 0):,} · {stored.get('sources', 0)} ({stored.get('model', '')}) |")
    if failed:
        w("")
        w("### 받지 못한 요청")
        for cid, why in failed:
            w(f"- {cid}: {why}")
    return "\n".join(L)


def show(reps, n):
    """본문을 기록에 찍는다 — 앞의 n개 종목의 설정별 한국어 핵심 칸(사람이 읽고 견주는 용도)."""
    tks = []
    for (cfg, tk) in reps:
        if tk not in tks:
            tks.append(tk)
    for tk in tks[:n]:
        for (cfg, t), rep in reps.items():
            if t != tk or rep is None:
                continue
            print(f"\n===== {tk} {rep.get('name', '')} · 설정 {cfg} =====")
            for k in ("title", "lead", "earnings", "industry", "outlook", "valuation_comment"):
                v = rep.get(k)
                print(f"[{k}] {(v.get('ko') if isinstance(v, dict) else v) or ''}")
            for k in ("bull", "bear", "risks"):
                for x in rep.get(k) or []:
                    if isinstance(x, dict):
                        head = x.get("title") or x.get("cat") or {}
                        body = x.get("body") or {}
                        print(f"[{k}] {(head.get('ko') if isinstance(head, dict) else head) or ''} — "
                              f"{(body.get('ko') if isinstance(body, dict) else body) or ''}")
            vb = (rep.get("verdict") or {}).get("body")
            print(f"[verdict] {(vb.get('ko') if isinstance(vb, dict) else vb) or ''}")
            print(f"[sources] {', '.join(rep.get('sources') or [])}")


def wait(cl, bid, budget=WAIT_SEC):
    waited = 0
    while True:
        b = cl.messages.batches.retrieve(bid)
        rc = b.request_counts
        if b.processing_status == "ended":
            return True
        if waited >= budget:
            return False
        if waited % 600 == 0:
            print(f"  · {bid} 처리 {rc.processing} · 성공 {rc.succeeded} · 오류 {rc.errored}", flush=True)
        time.sleep(60)
        waited += 60


def collect(cl, bid, by_tk):
    rows, reps, failed = [], {}, []
    mats = {}
    for res in cl.messages.batches.results(bid):
        got = split_id(res.custom_id)
        if not got:
            continue
        cfg, tk = got
        if res.result.type != "succeeded":
            err = getattr(getattr(res.result, "error", None), "error", None)
            failed.append((res.custom_id, f"{res.result.type} {getattr(err, 'message', '') or ''}".strip()))
            continue
        st = by_tk.get(tk)
        if st is None:
            failed.append((res.custom_id, "시세 자료에 없는 종목"))
            continue
        if tk not in mats:
            mats[tk] = material(st)
        row, rep = evaluate(res.result.message, cfg, st, mats[tk])
        rows.append(row)
        reps[(cfg, tk)] = rep
    return rows, reps, failed


def main():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    def _blocked(*_a, **_kw):
        raise RuntimeError("비용 시험은 배치로만 부른다(2026-10-08 사장 '무조건 batch API')")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked

    data = g.load_stocks()
    stocks = data["stocks"]
    by_tk = {s["ticker"]: s for s in stocks}
    bid = os.getenv("REPORT_TRIAL_BATCH", "").strip()
    if not bid:
        configs = [c.strip() for c in os.getenv("REPORT_TRIAL_CONFIGS", "h2,h0,s2l").split(",") if c.strip()]
        for c in configs:
            parse_config(c)
        tickers = [t.strip() for t in os.getenv("REPORT_TRIAL_TICKERS", "").split(",") if t.strip()]
        picked = pick(stocks, tickers)
        as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
        reqs = build_requests(configs, picked, as_of, stocks)
        if len(reqs) > MAX_REQ:
            print(f"❌ 시험 요청 {len(reqs)}건 — 한 번에 {MAX_REQ}건까지(설정이나 종목을 줄일 것)")
            sys.exit(1)
        b = cl.messages.batches.create(requests=reqs)
        bid = b.id
        print(f"- 시험 배치 {bid} — {len(reqs)}건 · 설정 {','.join(configs)} · 종목 "
              + ", ".join(f"{s['ticker']} {s['name']}" for s in picked), flush=True)
    if not wait(cl, bid):
        msg = f"⏳ {bid} 가 {WAIT_SEC // 60}분 안에 끝나지 않았다 — batch_id 에 이 값을 넣어 다시 돌리면 결과만 받는다."
        print(msg)
        summ = os.getenv("GITHUB_STEP_SUMMARY")
        if summ:
            with open(summ, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        return
    rows, reps, failed = collect(cl, bid, by_tk)
    text = render(rows, len(stocks), failed) + f"\n\n시험 배치 {bid}"
    print(text)
    summ = os.getenv("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    show(reps, int(os.getenv("REPORT_TRIAL_SHOW", "2") or "2"))


if __name__ == "__main__":
    main()
