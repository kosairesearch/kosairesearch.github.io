#!/usr/bin/env python3
"""
밸류에이션 자동 검증(audit) — 사람이 종목을 일일이 뒤지지 않아도 시스템이 오류를 잡아낸다.

data/valuation.js(그리드·스크리너용 EPS·BPS·ROE·DPS) + 당일 주가로 PER·PBR·배당을 만들어
네이버 값과 전 종목 자동 대조하고, 결과를 data/valuation_audit.txt 로 남긴다.

분류:
  OK        — 네이버와 허용오차(기본 8%) 이내
  MISMATCH  — 우리 값이 있는데 네이버와 어긋남  ← 가장 위험(틀린 값 노출). 0이어야 정상.
  BLANK     — 네이버엔 값이 있는데 우리는 비어 있음  ← 커버리지 격차(줄여야 함)
  NO_NAVER  — 네이버에도 값이 없음(적자·신규 등) → 빈칸이 정상

매분기 재수집 후 자동 실행 → 신규 보고서로 생긴 오류도 사람 없이 잡힌다.

환경변수: BUDGET_MIN(기본 50, 네이버 호출 분산), AUDIT_TOL(기본 0.08)
"""
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_reports as g
import generate_reports_v2 as v2

VAL = ROOT / "data" / "valuation.js"
OUT = ROOT / "data" / "valuation_audit.txt"
STATE = ROOT / "data" / "valuation_audit_state.json"
log = g.log
TOL = float(os.getenv("AUDIT_TOL", "0.08"))


def load_val():
    m = re.search(r"window\.KOS_VALUATION\s*=\s*(\{.*)", VAL.read_text(encoding="utf-8"), re.S)
    return json.loads(m.group(1).rstrip().rstrip(";")).get("stocks", {})


def main():
    data = g.load_stocks()
    px = {s["ticker"]: s.get("price") for s in data["stocks"]}
    nm = {s["ticker"]: s.get("name") for s in data["stocks"]}
    val = load_val()

    # 시총순 — 큰 종목부터 검증
    order = sorted(val.keys(), key=lambda t: next((s.get("mcap", 0) or 0 for s in data["stocks"] if s["ticker"] == t), 0), reverse=True)

    state = {}
    if STATE.exists():
        try:
            state = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    # 이번 데이터일자에 이미 검증한 종목은 건너뜀(이어받기)
    day = data.get("dataDate", "")
    if state.get("day") != day:
        state = {"day": day, "results": {}}
    results = state["results"]

    budget = int(os.getenv("BUDGET_MIN", "50")) * 60
    t0 = time.time()
    checked = 0
    for tk in order:
        if tk in results:
            continue
        if time.time() - t0 > budget:
            log(f"- 시간예산 초과 — {checked}건 검증, 나머지는 다음 실행")
            break
        e = val.get(tk, {})
        p = px.get(tk)

        def per():
            return round(p / e["eps"], 2) if (e.get("eps") and p) else None

        def pbr():
            return round(p / e["bps"], 2) if (e.get("bps") and p) else None

        nv = v2.naver_valuation(tk) or {}

        def nvget(*ks):
            for k in ks:
                if nv.get(k) not in (None, 0):
                    return nv.get(k)
            return None

        # 우리가 화면에 '표시하는' 모든 지표를 네이버와 대조
        div_ours = round(e["dps"] / p * 100, 2) if (e.get("dps") and p) else None
        roe_ours = e.get("roe")
        checks = (
            ("eps", e.get("eps"), nvget("eps")),
            ("bps", e.get("bps"), nvget("bps")),
            ("per", per(),        nvget("per")),
            ("pbr", pbr(),        nvget("pbr")),
            ("div", div_ours,     nvget("dividend", "dividendyield", "dvr", "dividendratio")),
            ("roe", roe_ours,     nvget("roe")),
        )
        rec = {"naver": bool(nv)}
        for key, ours, ref in checks:
            if ref in (None, 0):
                rec[key] = "no_naver" if ours is None else "ok_unverified"
            elif ours is None:
                rec[key] = "blank"          # 네이버엔 있는데 우리 없음
            else:
                diff = abs(ours - ref) / abs(ref)
                rec[key] = "ok" if diff <= TOL else f"mismatch({ours} vs {ref})"
        # ROE 내부 sanity(네이버 미제공 대비): 비현실적 값은 외부대조 없이도 잡는다
        if roe_ours is not None and abs(roe_ours) > 120 and not str(rec.get("roe", "")).startswith("mismatch"):
            rec["roe"] = f"mismatch(sanity {roe_ours})"
        results[tk] = rec
        if checked == 0:  # 첫 종목: 네이버 제공 코드 확인용(필드명 검증)
            state["naver_codes"] = sorted(nv.keys())
        checked += 1
        time.sleep(0.1)

    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    # 리포트 작성
    def tally(field, label):
        blank = [tk for tk, r in results.items() if r.get(field) == "blank"]
        mism = [tk for tk, r in results.items() if str(r.get(field, "")).startswith("mismatch")]
        ok = sum(1 for r in results.values() if r.get(field) == "ok")
        return blank, mism, ok, label

    lines = [f"# 밸류에이션 자동 검증 — {datetime.datetime.utcnow()+datetime.timedelta(hours=9):%Y-%m-%d %H:%M} KST",
             f"# 데이터일자 {day} · 검증 {len(results)}/{len(val)}종목 · 허용오차 {TOL*100:.0f}%",
             f"# 네이버 제공 항목(코드): {', '.join(state.get('naver_codes', []))}", ""]
    for field, label in (("per", "PER"), ("pbr", "PBR"), ("eps", "EPS"), ("bps", "BPS"), ("div", "배당수익률"), ("roe", "ROE")):
        blank, mism, ok, lab = tally(field, label)
        lines.append(f"[{lab}] 일치 {ok} · 빈칸 {len(blank)} · 불일치 {len(mism)}")
        if mism:
            lines.append("   ⚠️ 불일치(틀린값 노출 위험): " +
                         ", ".join(f"{nm.get(t,t)}({t}) {results[t][field]}" for t in mism[:30]))
        if blank:
            lines.append("   · 빈칸(네이버엔 있음): " +
                         ", ".join(f"{nm.get(t,t)}({t})" for t in blank[:40]))
        lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")

    # 콘솔 요약
    for field, label in (("per", "PER"), ("pbr", "PBR"), ("eps", "EPS"), ("bps", "BPS"), ("div", "배당수익률"), ("roe", "ROE")):
        blank, mism, ok, lab = tally(field, label)
        log(f"  [{lab}] 일치 {ok} · 빈칸 {len(blank)} · 불일치 {len(mism)}")
    total_mism = sum(1 for r in results.values() for f in ("per", "pbr", "eps", "bps", "div", "roe")
                     if str(r.get(f, "")).startswith("mismatch"))
    if len(results) >= len(val):
        log(f"\n✅ AUDIT_COMPLETE — 전 종목 검증. 불일치 총 {total_mism}건(0이어야 정상) → data/valuation_audit.txt")
    else:
        log(f"\n- AUDIT_REMAINING {len(val)-len(results)}개 남음(다음 실행 이어받기)")


if __name__ == "__main__":
    main()
