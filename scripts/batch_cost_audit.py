#!/usr/bin/env python3
"""배치 비용 점검 — 지난 N일 동안 이 계정이 낸 배치를 결과에서 하나도 빼지 않고 다시 센다(모델 호출 없음 · 돈 안 듦).

    python3 scripts/batch_cost_audit.py            # 지난 29일
    AUDIT_DAYS=7 python3 scripts/batch_cost_audit.py

2026-10-27 사장 "예전에는 100편 만드는 데 10달러도 안 들었다 · 지금은 거의 10배다 · 이유를 찾아라". 우리 쪽 사용량
기록은 생성기마다 따로 남긴 것뿐이고(리포트 v2 는 9월 4일부터 · 옛 형식은 10월 15일부터), 회수한 배치만 센다. 계정 전체에서
실제로 나간 돈을 한 자리에서 본 적이 없었다. 이 스크립트는 Anthropic 에 남아 있는 배치(결과는 만든 날부터 29일 보관)를 전부
읽어, 요청마다 응답에 실려 온 사용량과 청구 조건으로 금액을 다시 계산한다.

  · 청구 조건 — 응답의 usage 에 실려 온 그대로 쓴다: 요금 등급(service_tier — batch 면 절반), 처리 지역(inference_geo —
    us 면 1.1배), 캐시 쓰기의 보관 시간(cache_creation — 5분 1.25배 · 1시간 2배). 생성기의 기록 방식(generate_reports.cost_usd —
    전부 배치 · 5분 캐시로 가정)과 나란히 적어, 우리 기록이 실제 조건과 어긋나는지 본다.
  · 사고 토큰은 usage.output_tokens_details.thinking_tokens 로 정확히 센다(없는 응답만 토큰 세기 표본으로 어림한다 · 무료).
  · 일의 종류는 요청 이름(custom_id)으로 가른다 — KIND 의 표. 종목코드 그대로면 리포트 작성이다.
  · 주문 대비 저장 — 같은 종목을 다시 주문한 것, 주문한 날 뒤로 저장된 리포트가 없는 것(회수 못 함 · 저장 문턱)을 센다.
  · 즉시 호출(모닝브리핑)은 배치가 아니라 여기 없다 — data/briefs 의 meta.usage(usdAll)를 같은 기간으로 더한다.
결과는 표로 찍고(실행 요약에도) 아무것도 저장 · 커밋하지 않는다. 실제 청구서는 콘솔이 답이다 — 이 표와 콘솔이 크게 다르면
배치가 아닌 호출(즉시 호출 · 다른 프로그램)이 있다는 뜻이다.
지키는 검사 scripts/tests/batch_cost_audit_test.py(가짜 배치로 종류 · 금액 · 청구 조건 · 즉시 호출 없음).
"""

import datetime
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

KST = datetime.timezone(datetime.timedelta(hours=9))
DAYS = int(os.getenv("AUDIT_DAYS", "29"))
SAMPLES = int(os.getenv("AUDIT_SAMPLES", "12"))     # 사고 토큰이 없는 응답만 — 모델마다 글 토큰을 잴 표본 수

# 요청 이름 → 일의 종류. 위에서부터 처음 맞는 것.
KIND = [
    (re.compile(r"^[0-9][0-9A-Z]{5}$"), "리포트 작성"),
    (re.compile(r"^[0-9][0-9A-Z]{5}-[0-9a-f]{24}$"), "리포트 v2 보정"),
    (re.compile(r"^fx\d+_"), "신규 상장 · 옛 형식 교정"),
    (re.compile(r"^en_"), "옛 형식 영문 채우기"),
    (re.compile(r"^rv_"), "저장 전 검토"),
    (re.compile(r"^sec_"), "업종 분석 작성"),
    (re.compile(r"^rep_"), "검토 시험"),
    (re.compile(r"^trial-"), "비용 시험"),
    (re.compile(r"^c\d+$"), "업종 분류"),
    (re.compile(r"^report$"), "마케팅 주간 보고"),
    (re.compile(r"^brief$"), "모닝브리핑(배치)"),
]
WRITE_KINDS = {"리포트 작성", "업종 분석 작성"}


def kind_of(custom_id):
    for rx, name in KIND:
        if rx.match(custom_id or ""):
            return name
    return "기타"


def _usage(message):
    import generate_reports as g
    return g.usage_of(message)


def _cost(model, u):
    """생성기의 기록 방식 그대로(전부 배치 · 캐시 쓰기는 5분으로 가정) — 우리 사용량 기록과 같은 계산."""
    import generate_reports as g
    return g.cost_usd(model, u, batch=True)


def _terms(message):
    """응답의 청구 조건 — 요금 등급 · 처리 지역 · 캐시 쓰기 보관 시간(5분 · 1시간) · 사고 토큰(없으면 None)."""
    u = getattr(message, "usage", None)
    cc = getattr(u, "cache_creation", None)
    od = getattr(u, "output_tokens_details", None)
    think = getattr(od, "thinking_tokens", None) if od is not None else None
    return {"tier": getattr(u, "service_tier", None) or "?",
            "geo": getattr(u, "inference_geo", None) or "?",
            "cw5m": getattr(cc, "ephemeral_5m_input_tokens", None) if cc is not None else None,
            "cw1h": (getattr(cc, "ephemeral_1h_input_tokens", 0) or 0) if cc is not None else 0,
            "think": think}


def _bill(model, u, t):
    """응답에 실려 온 청구 조건으로 계산한 금액. 요금 등급이 batch 가 아니면 할인이 없다."""
    import generate_reports as g
    pin, pout = g.PRICE.get(model, (5.0, 25.0))
    cw1h = t["cw1h"]
    cw5m = t["cw5m"] if t["cw5m"] is not None else max(0, u["cache_w"] - cw1h)
    tok = (u["in"] + cw5m * 1.25 + cw1h * 2.0 + u["cache_r"] * g.CACHE_R.get(model, 0.1)) * pin + u["out"] * pout
    mult = (0.5 if t["tier"] in ("batch", "?") else 1.0) * (1.1 if t["geo"] == "us" else 1.0)
    return tok * mult / 1e6 + u["search"] * 0.01


def _text(message):
    return "".join(getattr(b, "text", "") or "" for b in getattr(message, "content", None) or []
                   if getattr(b, "type", "") == "text")


def _new_book():
    return {"n": 0, "in": 0, "cache_w": 0, "cache_r": 0, "out": 0, "search": 0, "usd": 0.0, "rec": 0.0,
            "think": 0, "think_n": 0}


def _add(book, u, usd, rec, t):
    book["n"] += 1
    for k in ("in", "cache_w", "cache_r", "out", "search"):
        book[k] += u[k]
    book["usd"] += usd
    book["rec"] += rec
    if t["think"] is not None:
        book["think"] += t["think"]
        book["think_n"] += 1


def scan(cl, days=DAYS, now=None, log=print):
    """지난 days 일의 배치를 읽어 합계를 돌려준다. 모델을 부르지 않는다(목록 · 결과 받기뿐)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)
    out = {"batches": [], "by_day": defaultdict(lambda: defaultdict(_new_book)),
           "by_kind": defaultdict(_new_book), "by_model_write": defaultdict(_new_book),
           "samples": defaultdict(list), "stop": defaultdict(lambda: defaultdict(int)), "pending": [],
           "orders": defaultdict(list), "tier": defaultdict(int), "geo": defaultdict(int),
           "cw5m": 0, "cw1h": 0, "gone": []}
    older = 0
    for b in cl.messages.batches.list(limit=100):
        created = b.created_at
        if created < cutoff:
            older += 1
            if older >= 20:          # 목록은 최근 것부터다 — 기간 밖이 스무 개 이어지면 끝
                break
            continue
        older = 0
        rc = b.request_counts
        row = {"id": b.id, "created": created.astimezone(KST), "status": b.processing_status,
               "ok": rc.succeeded, "err": rc.errored, "cancel": rc.canceled, "expired": rc.expired,
               "proc": rc.processing, "kinds": defaultdict(int), "models": defaultdict(int),
               "usd": 0.0, "out": 0, "search": 0}
        if b.processing_status != "ended":
            out["pending"].append(row)
            continue
        day = row["created"].strftime("%m-%d")
        try:
            results = list(cl.messages.batches.results(b.id))
        except Exception as e:      # 보관 기간 경계에서 결과가 먼저 지워진 배치 — 'has no available results'(404)
            log(f"  · {b.id} 결과를 받을 수 없음({type(e).__name__}) — 건너뜀")
            out["gone"].append(row)
            continue
        for r in results:
            if getattr(r.result, "type", "") != "succeeded":
                continue                 # 오류 · 취소 · 만료는 청구되지 않는다
            m = r.result.message
            u = _usage(m)
            if u is None:
                continue
            model = getattr(m, "model", "?")
            t = _terms(m)
            usd, rec = _bill(model, u, t), _cost(model, u)
            kind = kind_of(r.custom_id)
            out["tier"][t["tier"]] += 1
            out["geo"][t["geo"]] += 1
            out["cw1h"] += t["cw1h"]
            out["cw5m"] += t["cw5m"] if t["cw5m"] is not None else max(0, u["cache_w"] - t["cw1h"])
            row["kinds"][kind] += 1
            row["models"][model] += 1
            row["usd"] += usd
            row["out"] += u["out"]
            row["search"] += u["search"]
            _add(out["by_day"][day][kind], u, usd, rec, t)
            _add(out["by_kind"][kind], u, usd, rec, t)
            if kind == "리포트 작성":
                out["orders"][r.custom_id].append((row["created"].strftime("%Y-%m-%d"), usd, b.id))
            if kind in WRITE_KINDS:
                key = f"{kind} · {model}"
                _add(out["by_model_write"][key], u, usd, rec, t)
                out["stop"][key][getattr(m, "stop_reason", "?")] += 1
                if t["think"] is None and len(out["samples"][key]) < SAMPLES:
                    text = _text(m)
                    if text:
                        out["samples"][key].append((model, u["out"], text))
        out["batches"].append(row)
    return out


def text_share(cl, samples, log=print):
    """사고 토큰이 오지 않은 응답만 — 표본마다 글 토큰 / 출력 토큰 → 평균 비율. 토큰 세기는 무료다."""
    share = {}
    for key, items in samples.items():
        rs = []
        for model, out_tok, text in items:
            try:
                n = cl.messages.count_tokens(model=model, messages=[{"role": "user", "content": text}]).input_tokens
            except Exception as e:
                log(f"  · 토큰 세기 실패({key}): {type(e).__name__}")
                continue
            if out_tok:
                rs.append(min(1.0, max(0, n - 8) / out_tok))
        if rs:
            share[key] = sum(rs) / len(rs)
    return share


def report_dates(root=ROOT):
    """종목 → 지금 화면에 있는 리포트의 작성일(새 형식 · 옛 형식 중 늦은 날)."""
    dates = {}
    for sub in ("reports_v2", "reports"):
        for p in (root / "data" / sub).glob("*.json"):
            try:
                d = json.loads(p.read_text(encoding="utf-8")).get("reportDate") or ""
            except Exception:
                continue
            if d > dates.get(p.stem, ""):
                dates[p.stem] = d
    return dates


def waste(orders, dates):
    """리포트 작성 주문 가운데 같은 종목을 다시 주문한 것 · 주문한 날 뒤로 저장된 리포트가 없는 것.

    배치를 주문한 뒤 회수하지 못하거나(작업이 끊김 · 상태 파일 유실) 저장 문턱에 걸리면 돈은 나가고 리포트는
    없다 — 그러면 다음 회차가 같은 종목을 다시 주문한다. 우리 사용량 기록은 회수한 배치만 세므로 이런 돈은
    기록에 없다. 새 공시로 다시 쓴 것도 '다시 주문'에 들어간다 — 낭비인지는 날짜를 보고 가른다."""
    n = sum(len(v) for v in orders.values())
    repeat = {tk: v for tk, v in orders.items() if len(v) > 1}
    extra_n = sum(len(v) - 1 for v in repeat.values())
    extra_usd = sum(sum(x[1] for x in sorted(v)[:-1]) for v in repeat.values())
    unsaved = [(tk, d, usd) for tk, v in orders.items() for d, usd, _ in v if dates.get(tk, "") < d]
    return {"n": n, "tickers": len(orders), "repeat": repeat, "extra_n": extra_n, "extra_usd": extra_usd,
            "unsaved_n": len(unsaved), "unsaved_usd": sum(x[2] for x in unsaved),
            "unsaved": sorted(unsaved, key=lambda x: x[1])}


def brief_cost(days=DAYS, now=None):
    """모닝브리핑(즉시 호출) — 발행 기록의 usdAll 을 같은 기간으로 더한다."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    since = (now - datetime.timedelta(days=days)).astimezone(KST).strftime("%Y-%m-%d")
    tot, n = 0.0, 0
    for p in sorted((ROOT / "data" / "briefs").glob("*.json")):
        if p.stem < since:
            continue
        try:
            u = (json.loads(p.read_text(encoding="utf-8")).get("meta") or {}).get("usage") or {}
        except Exception:
            continue
        v = u.get("usdAll", u.get("usd"))
        if isinstance(v, (int, float)):
            tot += v
            n += 1
    return n, tot


def report(res, share, brief, days=DAYS, dates=None):
    L = []
    w = L.append
    ws = waste(res["orders"], dates if dates is not None else report_dates())
    allusd = sum(k["usd"] for k in res["by_kind"].values())
    allrec = sum(k["rec"] for k in res["by_kind"].values())
    w(f"## 💵 배치 비용 점검 — 지난 {days}일")
    w("")
    w(f"배치 {len(res['batches'])}개 · 응답의 청구 조건으로 계산한 합계 **${allusd:,.2f}** "
      f"(생성기 기록 방식으로는 ${allrec:,.2f}) · 모닝브리핑(즉시 호출) {brief[0]}편 ${brief[1]:,.2f}"
      + (f" · 아직 처리 중인 배치 {len(res['pending'])}개(결과 전이라 빠짐)" if res["pending"] else "")
      + (f" · 결과가 이미 지워진 배치 {len(res['gone'])}개(빠짐 — 성공 {sum(r['ok'] for r in res['gone']):,}건)"
         if res["gone"] else ""))
    w("")
    w("### 청구 조건 확인 — 응답에 실려 온 그대로")
    tiers = " · ".join(f"{k} {v:,}건" for k, v in sorted(res["tier"].items(), key=lambda x: -x[1]))
    geos = " · ".join(f"{k} {v:,}건" for k, v in sorted(res["geo"].items(), key=lambda x: -x[1]))
    cw = res["cw5m"] + res["cw1h"]
    w(f"- 요금 등급(service_tier): {tiers or '—'} — batch 가 아니면 배치 할인이 없다")
    w(f"- 처리 지역(inference_geo): {geos or '—'} — us 면 1.1배")
    w(f"- 캐시 쓰기: 5분 {res['cw5m']:,} · 1시간 {res['cw1h']:,} 토큰"
      + (f"(1시간 {res['cw1h'] / cw:.0%} — 1시간은 1.25배가 아니라 2배)" if cw else ""))
    w("")
    w("### 일의 종류별")
    w("| 종류 | 요청 | 금액 | 요청당 | 출력 토큰(평균) | 검색(평균) |")
    w("|---|---:|---:|---:|---:|---:|")
    for kind, b in sorted(res["by_kind"].items(), key=lambda x: -x[1]["usd"]):
        n = max(b["n"], 1)
        w(f"| {kind} | {b['n']:,} | ${b['usd']:,.2f} | ${b['usd']/n:.3f} | {b['out']//n:,} | {b['search']/n:.1f} |")
    w("")
    w("### 작성 요청의 모델별 평균 — 한 편에 무엇이 드는가")
    w("| 종류 · 모델 | 편수 | 편당 | 입력 | 캐시 쓰기 | 캐시 읽기 | 출력 | 그중 사고 | 검색 | 잘림 |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for key, b in sorted(res["by_model_write"].items(), key=lambda x: -x[1]["n"]):
        n = max(b["n"], 1)
        if b["think_n"]:
            th = b["think"] / b["think_n"]
            think = f"{int(th):,} ({th / max(b['out'] / n, 1):.0%})"
        elif key in share:
            think = f"{int(b['out'] / n * (1 - share[key])):,} (어림 {1 - share[key]:.0%})"
        else:
            think = "—"
        cut = res["stop"][key].get("max_tokens", 0)
        w(f"| {key} | {b['n']:,} | ${b['usd']/n:.3f} | {b['in']//n:,} | {b['cache_w']//n:,} | {b['cache_r']//n:,} "
          f"| {b['out']//n:,} | {think} | {b['search']/n:.1f} | {cut} |")
    w("")
    w("### 작성 요청의 금액 구성(모델별 · 배치 단가)")
    w("| 종류 · 모델 | 사고 | 글(출력 − 사고) | 캐시 쓰기(검색 결과) | 검색 요금 | 입력 · 캐시 읽기 |")
    w("|---|---:|---:|---:|---:|---:|")
    import generate_reports as g
    for key, b in sorted(res["by_model_write"].items(), key=lambda x: -x[1]["n"]):
        model = key.split(" · ")[-1]
        pin, pout = g.PRICE.get(model, (5.0, 25.0))
        pin, pout = pin / 2, pout / 2
        cr = g.CACHE_R.get(model, 0.1)
        think = b["think"] * b["n"] / b["think_n"] if b["think_n"] else (
            b["out"] * (1 - share[key]) if key in share else 0)
        parts = [think * pout / 1e6, (b["out"] - think) * pout / 1e6, b["cache_w"] * 1.25 * pin / 1e6,
                 b["search"] * 0.01, (b["in"] + b["cache_r"] * cr) * pin / 1e6]
        tot = sum(parts) or 1
        w(f"| {key} | " + " | ".join(f"{p / tot:.0%}" for p in parts) + " |")
    w("")
    w("### 주문 대비 저장 — 돈은 나갔는데 리포트로 남지 않은 주문")
    w(f"- 리포트 작성 주문 {ws['n']:,}건 · 종목 {ws['tickers']:,}개")
    w(f"- 같은 종목을 두 번 이상 주문: {len(ws['repeat']):,}개 종목 · 추가 주문 {ws['extra_n']:,}건 · ${ws['extra_usd']:,.2f}")
    w(f"- 주문한 날 뒤로 저장된 리포트가 없는 주문: {ws['unsaved_n']:,}건 · ${ws['unsaved_usd']:,.2f}")
    if ws["repeat"]:
        top = sorted(ws["repeat"].items(), key=lambda x: (-len(x[1]), x[0]))[:15]
        w("- 여러 번 주문한 종목(많은 순): " + " · ".join(
            f"{tk} {len(v)}회(${sum(x[1] for x in v):.2f})" for tk, v in top))
    if ws["unsaved"]:
        w("- 저장되지 않은 주문(앞 20건): " + " · ".join(f"{tk} {d[5:]}" for tk, d, _ in ws["unsaved"][:20]))
    w("")
    w("### 날짜별(배치를 만든 날 · 한국 시간)")
    w("| 날짜 | 리포트 작성 편수 | 작성 금액 | 그 밖의 배치 | 합계 |")
    w("|---|---:|---:|---:|---:|")
    for day in sorted(res["by_day"]):
        kinds = res["by_day"][day]
        wr = kinds.get("리포트 작성")
        n_wr = wr["n"] if wr else 0
        usd_wr = wr["usd"] if wr else 0.0
        rest = sum(b["usd"] for k, b in kinds.items() if k != "리포트 작성")
        w(f"| {day} | {n_wr:,} | ${usd_wr:,.2f} | ${rest:,.2f} | ${usd_wr + rest:,.2f} |")
    w("")
    w("### 배치별")
    w("| 만든 시각(KST) | 배치 | 종류 | 모델 | 성공/오류/취소/만료 | 출력 토큰 | 검색 | 금액 |")
    w("|---|---|---|---|---|---:|---:|---:|")
    for r in sorted(res["batches"], key=lambda x: x["created"]):
        kinds = ", ".join(f"{k} {v}" for k, v in sorted(r["kinds"].items(), key=lambda x: -x[1]))
        models = ", ".join(f"{k.replace('claude-', '')} {v}" for k, v in sorted(r["models"].items(), key=lambda x: -x[1]))
        w(f"| {r['created']:%m-%d %H:%M} | {r['id'][-10:]} | {kinds or '—'} | {models or '—'} "
          f"| {r['ok']}/{r['err']}/{r['cancel']}/{r['expired']} | {r['out']:,} | {r['search']} | ${r['usd']:,.2f} |")
    for r in res["pending"]:
        w(f"| {r['created']:%m-%d %H:%M} | {r['id'][-10:]} | (처리 중) | — | 처리 {r['proc']} | — | — | — |")
    for r in res["gone"]:
        w(f"| {r['created']:%m-%d %H:%M} | {r['id'][-10:]} | (결과 지워짐) | — "
          f"| {r['ok']}/{r['err']}/{r['cancel']}/{r['expired']} | — | — | — |")
    return "\n".join(L)


def main():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    def _blocked(*_a, **_kw):
        raise RuntimeError("비용 점검은 모델을 부르지 않는다 — 목록 · 결과 받기 · 토큰 세기만")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked
    cl.messages.batches.create = _blocked
    res = scan(cl)
    share = text_share(cl, res["samples"])
    text = report(res, share, brief_cost())
    print(text)
    summ = os.getenv("GITHUB_STEP_SUMMARY")
    if summ:
        with open(summ, "a", encoding="utf-8") as f:
            f.write(text + "\n")


if __name__ == "__main__":
    main()
