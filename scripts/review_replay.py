#!/usr/bin/env python3
"""저장 전 검토(check_report_text.review)를 지금 사이트에 걸린 글에 시험으로 돌려 본다 — 고침 목록만 찍고 저장하지 않는다.

    python3 scripts/review_replay.py sectors                      # 업종 분석 전부
    python3 scripts/review_replay.py reports 005930 000660        # 고른 리포트
    python3 scripts/review_replay.py reports --recent 20          # 최근에 쓴 리포트 20편

왜 있나(2026-10-09). 업종 분석 30편을 사람이 읽으니 검사를 다 통과한 글에 깨진 문장 · 재료와 다른 수치 · 회사 설명 오류 ·
낡은 기사가 있었다(사장이 크게 질책했다). 그래서 생성기가 저장 전에 값싼 모델이 글을 한 번 더 읽게 했다(업종 분석은 기본으로
켬, 리포트는 REPORT_REVIEW). 이 스크립트는 같은 요청을 지금 글에 보내 무엇을 고치려 하는지 미리 본다 — 리포트 쪽을 켜기 전에
고침의 품질과 값을 확인하고, 사람이 고친 글을 한 번 더 읽히는 데 쓴다.

  · 배치로만 보낸다(즉시 호출 창구는 막는다). Sonnet 5 배치 — 글 한 편에 3~5센트 안팎.
  · 저장하지 않는다. 받은 고침은 실행 기록에 'PATCH<TAB>{json}' 줄과 사람이 읽을 줄로 찍는다 — 고칠지는 사람이 정한다.
  · 받은 고침은 생성기와 같은 문을 지난다(apply_review — 옛 글이 그 칸에 한 번만 · 새 수치 금지 · 길이). 버린 고침도 사유와 찍는다.
"""
import datetime
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_report_text as C  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WAIT = int(os.getenv("REVIEW_WAIT_SEC", "3600"))
RATE = (1.0, 5.0)        # Sonnet 5 배치 — 1M 토큰당 입력 · 출력(정가의 절반 · generate_reports_v2._PRICE 와 같다)


def client():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        print("❌ ANTHROPIC_API_KEY 가 없다")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    def _blocked(*_a, **_kw):
        raise RuntimeError("시험 검토는 Batch API 로만 보낸다")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked
    return cl


def sector_jobs():
    import generate_sectors as S
    raw = (ROOT / "data" / "sectors.js").read_text(encoding="utf-8")
    secs = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["sectors"]
    agg = S.load_sectors()
    jobs, ctx = {}, {}
    for i, (sec, rep) in enumerate(secs.items()):
        info = agg.get(sec) or {}
        part = {k: rep[k] for k in S.REVIEW_KEYS if k in rep}
        material = "\n".join(f"  - {x}" for x in info.get("fin") or [])
        names = "\n".join(S.company_lines(S.mentioned(part, [nm for nm, _ in info.get("top") or []])))
        hits = [h for h in C.check(S._as_report(rep)) if h["level"] == "위험" or h["rule"] in S.GATE_RULES]
        as_of = S._day(rep.get("generatedAt") or "") or ""
        params = C.review_params(part, kind="sector", as_of=as_of, material=material, names=names, hits=hits,
                                 hints=S.review_hints(rep, info))
        key = f"sec_{i:02d}"
        jobs[key] = params
        ctx[key] = (sec, part, f"{material}\n{names}", rep.get("generatedAt") or "")
    return jobs, ctx


def report_jobs(tickers, recent):
    import generate_reports_v2 as M
    d = ROOT / "data" / "reports_v2"
    if recent:
        rows = []
        for p in d.glob("*.json"):
            try:
                r = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(r, dict) and r.get("reportTs"):
                rows.append((r["reportTs"], p.stem))
        tickers = [tk for _, tk in sorted(rows, reverse=True)[:recent]]
    jobs, ctx = {}, {}
    for tk in tickers:
        p = d / f"{tk}.json"
        if not p.exists():
            print(f"  · {tk}: 리포트 없음 — 건너뜀")
            continue
        rep = json.loads(p.read_text(encoding="utf-8"))
        part = {k: v for k, v in rep.items() if k not in C._NOT_TEXT}
        material = M.review_material(rep.get("name") or tk, rep.get("quant"))
        names = f"  - {rep.get('name') or tk}({C.clean_en(rep.get('name_en'))}) — 이 리포트의 회사"
        params = C.review_params(part, kind="report", as_of=rep.get("reportDate") or "", material=material, names=names,
                                 hits=C.check(rep), hints=C.en_gap_hints(rep))
        key = f"rep_{tk}"
        jobs[key] = params
        ctx[key] = (f"{tk} {rep.get('name')}", part, f"{material}\n{names}", rep.get("reportDate") or "")
    return jobs, ctx


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ("sectors", "reports"):
        print(__doc__)
        sys.exit(2)
    if args[0] == "sectors":
        jobs, ctx = sector_jobs()
    else:
        recent = int(args[args.index("--recent") + 1]) if "--recent" in args else 0
        tickers = [a for a in args[1:] if a != "--recent" and not (recent and a == str(recent))]
        jobs, ctx = report_jobs(tickers, recent)
    if not jobs:
        print("보낼 글이 없다")
        return
    print(f"## 저장 전 검토 시험 — {args[0]} {len(jobs)}편 · {C.REVIEW_MODEL} 배치 · "
          f"{datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))):%Y-%m-%d %H:%M} KST")
    got = C.send_batch(client(), jobs, wait_sec=WAIT, log=print)
    tin = tout = 0
    n_ok = n_drop = n_fail = 0
    for key, msg in got.items():
        name, part, extra, as_of = ctx[key]
        if msg is None:
            n_fail += 1
            print(f"\n### {name} — 답 없음(오류)")
            continue
        u = getattr(msg, "usage", None)
        if u:
            tin += (getattr(u, "input_tokens", 0) or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) \
                + (getattr(u, "cache_creation_input_tokens", 0) or 0)
            tout += getattr(u, "output_tokens", 0) or 0
        text = C.message_text(msg)
        new, applied, dropped = C.apply_review(part, text, extra=extra, as_of=as_of)
        print(f"\n### {name} — 고침 {applied}곳 · 버림 {len(dropped)}곳")
        if new is None:
            n_fail += 1
            print("  (답을 읽지 못함) " + "; ".join(dropped))
            continue
        n_ok += applied
        n_drop += len(dropped)
        try:
            patches = (C._parse_json(text) or {}).get("patches") or []
        except Exception:                                   # noqa: BLE001
            patches = []
        for p in patches:
            if not isinstance(p, dict):
                continue
            print(f"  · [{p.get('path')}.{p.get('lang')}] {p.get('why')}\n      - {p.get('old')}\n      + {p.get('new')}")
            print("PATCH\t" + json.dumps({"doc": name, **p}, ensure_ascii=False))
        for d in dropped:
            print(f"  ✗ 버림: {d}")
        if new is not None:
            left = C.check(new) if args[0] == "reports" else []
            if left:
                print(f"  ! 고친 뒤에도 남는 위반 {len(left)}건: " + ", ".join(sorted({h['rule'] for h in left})))
    usd = tin / 1e6 * RATE[0] + tout / 1e6 * RATE[1]
    print(f"\n■ 합계 — 고침 {n_ok}곳 · 버림 {n_drop}곳 · 답 없음 {n_fail}편 · 입력 {tin:,} · 출력 {tout:,} 토큰 → 약 ${usd:.2f}(배치 추정)")


if __name__ == "__main__":
    main()
