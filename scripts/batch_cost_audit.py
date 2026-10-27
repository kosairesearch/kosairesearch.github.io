#!/usr/bin/env python3
"""배치 비용 점검 — 지난 N일 동안 이 계정이 낸 배치를 결과에서 하나도 빼지 않고 다시 센다(모델 호출 없음 · 돈 안 듦).

    python3 scripts/batch_cost_audit.py            # 지난 29일
    AUDIT_DAYS=7 python3 scripts/batch_cost_audit.py

2026-10-27 사장 "예전에는 100편 만드는 데 10달러도 안 들었다 · 지금은 거의 10배다 · 이유를 찾아라". 우리 쪽 사용량
기록은 생성기마다 따로 남긴 것뿐이고(리포트 v2 는 9월 4일부터 · 옛 형식은 10월 15일부터), 계정 전체에서 실제로 나간 돈을
한 자리에서 본 적이 없었다. 이 스크립트는 Anthropic 에 남아 있는 배치(결과는 만든 날부터 29일 보관)를 전부 읽어 요청마다의
사용량(입력 · 캐시 쓰기 · 캐시 읽기 · 출력 · 웹 검색)을 배치 단가(generate_reports.PRICE 의 절반)로 다시 계산한다.

  · 일의 종류는 요청 이름(custom_id)으로 가른다 — KIND 의 표. 종목코드 그대로면 리포트 작성이다.
  · 리포트 · 업종 분석 작성은 출력 토큰을 '글'과 '사고 · 검색 호출'로 나눈다. 글 토큰은 응답의 text 블록을 이어 붙여
    토큰 수 세기(count_tokens · 무료)로 잰 표본의 비율로 어림한다 — 응답에 오는 사고는 요약본이라 글자 수로는 잴 수 없다.
  · 즉시 호출(모닝브리핑)은 배치가 아니라 여기 없다 — data/briefs 의 meta.usage(usdAll)를 같은 기간으로 더한다.
결과는 표로 찍고(실행 요약에도) 아무것도 저장 · 커밋하지 않는다. 숫자는 추정이다 — 실제 청구는 콘솔이 답이다.
지키는 검사 scripts/tests/batch_cost_audit_test.py(가짜 배치로 종류 · 금액 · 즉시 호출 없음).
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
SAMPLES = int(os.getenv("AUDIT_SAMPLES", "12"))     # 모델마다 글 토큰을 잴 표본 수

# 요청 이름 → 일의 종류. 위에서부터 처음 맞는 것.
KIND = [
    (re.compile(r"^[0-9][0-9A-Z]{5}$"), "리포트 작성"),
    (re.compile(r"^[0-9][0-9A-Z]{5}-[0-9a-f]{24}$"), "리포트 v2 보정"),
    (re.compile(r"^fx\d+_"), "신규 상장 · 옛 형식 교정"),
    (re.compile(r"^en_"), "옛 형식 영문 채우기"),
    (re.compile(r"^rv_"), "저장 전 검토"),
    (re.compile(r"^sec_"), "업종 분석 작성"),
    (re.compile(r"^rep_"), "검토 시험"),
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
    import generate_reports as g
    return g.cost_usd(model, u, batch=True)


def _blocks(message):
    """응답 블록 → (글, 사고 글자 수, 블록 종류별 개수)."""
    text, think, kinds = [], 0, defaultdict(int)
    for b in getattr(message, "content", None) or []:
        t = getattr(b, "type", "")
        kinds[t] += 1
        if t == "text":
            text.append(getattr(b, "text", "") or "")
        elif t == "thinking":
            think += len(getattr(b, "thinking", "") or "")
    return "".join(text), think, dict(kinds)


def _new_book():
    return {"n": 0, "in": 0, "cache_w": 0, "cache_r": 0, "out": 0, "search": 0, "usd": 0.0}


def _add(book, u, usd):
    book["n"] += 1
    for k in ("in", "cache_w", "cache_r", "out", "search"):
        book[k] += u[k]
    book["usd"] += usd


def scan(cl, days=DAYS, now=None, log=print):
    """지난 days 일의 배치를 읽어 합계를 돌려준다. 모델을 부르지 않는다(목록 · 결과 받기뿐)."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    cutoff = now - datetime.timedelta(days=days)
    out = {"batches": [], "by_day": defaultdict(lambda: defaultdict(_new_book)),
           "by_kind": defaultdict(_new_book), "by_model_write": defaultdict(_new_book),
           "samples": defaultdict(list), "stop": defaultdict(lambda: defaultdict(int)),
           "think_chars": defaultdict(int), "text_chars": defaultdict(int), "pending": []}
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
               "usd": 0.0, "out": 0, "search": 0, "cache_w": 0}
        if b.processing_status != "ended":
            out["pending"].append(row)
            continue
        day = row["created"].strftime("%m-%d")
        for r in cl.messages.batches.results(b.id):
            if getattr(r.result, "type", "") != "succeeded":
                continue                 # 오류 · 취소 · 만료는 청구되지 않는다
            m = r.result.message
            u = _usage(m)
            if u is None:
                continue
            model = getattr(m, "model", "?")
            usd = _cost(model, u)
            kind = kind_of(r.custom_id)
            row["kinds"][kind] += 1
            row["models"][model] += 1
            row["usd"] += usd
            row["out"] += u["out"]
            row["search"] += u["search"]
            row["cache_w"] += u["cache_w"]
            _add(out["by_day"][day][kind], u, usd)
            _add(out["by_kind"][kind], u, usd)
            if kind in WRITE_KINDS:
                key = f"{kind} · {model}"
                _add(out["by_model_write"][key], u, usd)
                out["stop"][key][getattr(m, "stop_reason", "?")] += 1
                text, think, _ = _blocks(m)
                out["think_chars"][key] += think
                out["text_chars"][key] += len(text)
                if len(out["samples"][key]) < SAMPLES and text:
                    out["samples"][key].append((model, u["out"], text))
        out["batches"].append(row)
    return out


def text_share(cl, samples, log=print):
    """표본마다 글 토큰 / 출력 토큰 → 모델 · 종류별 평균 비율. 토큰 세기는 무료다."""
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


def report(res, share, brief, days=DAYS):
    L = []
    w = L.append
    allusd = sum(k["usd"] for k in res["by_kind"].values())
    w(f"## 💵 배치 비용 점검 — 지난 {days}일 (배치 단가 · 추정)")
    w("")
    w(f"배치 {len(res['batches'])}개 · 합계 **${allusd:,.2f}** · 모닝브리핑(즉시 호출) {brief[0]}편 ${brief[1]:,.2f}"
      + (f" · 아직 처리 중인 배치 {len(res['pending'])}개(결과 전이라 빠짐)" if res["pending"] else ""))
    w("")
    w("### 일의 종류별")
    w("| 종류 | 요청 | 금액 | 요청당 | 출력 토큰(평균) | 검색(평균) |")
    w("|---|---:|---:|---:|---:|---:|")
    for kind, b in sorted(res["by_kind"].items(), key=lambda x: -x[1]["usd"]):
        n = max(b["n"], 1)
        w(f"| {kind} | {b['n']:,} | ${b['usd']:,.2f} | ${b['usd']/n:.3f} | {b['out']//n:,} | {b['search']/n:.1f} |")
    w("")
    w("### 작성 요청의 모델별 평균 — 한 편에 무엇이 드는가")
    w("| 종류 · 모델 | 편수 | 편당 | 입력 | 캐시 쓰기 | 캐시 읽기 | 출력 | 그중 글(어림) | 검색 | 잘림 |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for key, b in sorted(res["by_model_write"].items(), key=lambda x: -x[1]["n"]):
        n = max(b["n"], 1)
        sh = share.get(key)
        txt = f"{int(b['out']/n*sh):,} ({sh:.0%})" if sh is not None else "—"
        cut = res["stop"][key].get("max_tokens", 0)
        w(f"| {key} | {b['n']:,} | ${b['usd']/n:.3f} | {b['in']//n:,} | {b['cache_w']//n:,} | {b['cache_r']//n:,} "
          f"| {b['out']//n:,} | {txt} | {b['search']/n:.1f} | {cut} |")
    w("")
    w("### 작성 요청의 금액 구성(모델별)")
    w("| 종류 · 모델 | 출력(사고 포함) | 캐시 쓰기(검색 결과) | 검색 요금 | 입력 · 캐시 읽기 |")
    w("|---|---:|---:|---:|---:|")
    import generate_reports as g
    for key, b in sorted(res["by_model_write"].items(), key=lambda x: -x[1]["n"]):
        model = key.split(" · ")[-1]
        pin, pout = g.PRICE.get(model, (5.0, 25.0))
        pin, pout = pin / 2, pout / 2
        cr = g.CACHE_R.get(model, 0.1)
        parts = [b["out"] * pout / 1e6, b["cache_w"] * 1.25 * pin / 1e6, b["search"] * 0.01,
                 (b["in"] + b["cache_r"] * cr) * pin / 1e6]
        tot = sum(parts) or 1
        w(f"| {key} | {parts[0]/tot:.0%} | {parts[1]/tot:.0%} | {parts[2]/tot:.0%} | {parts[3]/tot:.0%} |")
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
