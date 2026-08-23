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


REPORTS = ROOT / "data" / "reports_v2"


LAG_TOL = float(os.getenv("AUDIT_LAG_TOL", "0.15"))


def lag_bases(tk):
    """네이버가 아직 안 따라왔을 때 그쪽이 들고 있을 법한 우리 값들.

    네이버는 우리보다 늦게 반영한다. 우리는 DART 를 직접 읽어 반기·3분기가
    나오는 즉시 넣는데, 네이버는 며칠~몇 주 뒤에 따라온다. 그 사이에는 우리가
    맞는데도 '어긋남' 으로 찍힌다. 이걸 안 걸러내면 경보가 늘 울리고, 경보가
    늘 울리면 그 안에서 진짜 오류를 아무도 못 찾는다.

    어느 시점에 멈춰 있는지는 종목마다 다르다. [EPS] 어긋남 30건을 뜯어보니
    직전 분기 TTM 23건 · 최근 결산 연간 5건 · 현재 TTM 2건이었고, 15% 안으로
    설명되는 게 26건(87%)이었다. 그래서 한 가지만 대 보지 않고 후보를 다 만든다.

    돌려주는 것: {"eps": [...], "bps": [...]} — 각각 그럴듯한 과거 기준값 목록.
    """
    f = REPORTS / f"{tk}.json"
    if not f.exists():
        return {}
    try:
        q = (json.loads(f.read_text(encoding="utf-8")).get("quant") or {})
    except Exception:
        return {}
    v = q.get("valuation") or {}
    ann = [x for x in (q.get("annual") or []) if isinstance(x, dict)]
    qs = [x for x in (q.get("quarterly") or []) if isinstance(x, dict)]
    w = v.get("wavg_shares") or v.get("total_shares")

    eps, bps = [], []
    if w:
        # 1~2분기 전 기준 TTM — 네이버가 최근 보고서를 아직 안 받은 경우
        for back in (1, 2):
            if len(qs) >= 4 + back:
                npo = [x.get("np_owner") for x in qs[len(qs) - 4 - back:len(qs) - back]]
                if all(n is not None for n in npo):
                    eps.append(int(sum(npo) / w))
        # 최근 결산 자본 ÷ 주식수 — BPS 는 분기 자본을 안 받고 연간에 머무는 일이 잦다
        if ann and ann[0].get("equity_owner"):
            bps.append(int(ann[0]["equity_owner"] / w))
    # 회사가 공시한 최근 결산 연간 주당이익 그대로
    if ann and ann[0].get("eps_basic") is not None:
        eps.append(int(ann[0]["eps_basic"]))
    return {"eps": eps, "bps": bps}


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
            ("div", div_ours,     nvget("dividendyieldratio")),   # 배당수익률(%) — 'dividend'(원)와 혼동 금지
            ("roe", roe_ours,     nvget("roe")),                  # 네이버 미제공 → 내부 sanity로만 검증
        )
        rec = {"naver": bool(nv)}
        lag = lag_bases(tk)           # 네이버가 멈춰 있을 법한 과거 기준값들
        for key, ours, ref in checks:
            if ref in (None, 0):
                rec[key] = "no_naver" if ours is None else "ok_unverified"
            elif ours is None:
                rec[key] = "blank"          # 네이버엔 있는데 우리 없음
            else:
                diff = abs(ours - ref) / abs(ref)
                if diff <= TOL:
                    rec[key] = "ok"
                    continue
                # 네이버가 아직 새 분기를 안 받은 경우를 걸러낸다.
                # 우리가 반기보고서를 먼저 넣으면 네이버와 값이 벌어지는데,
                # 그건 우리가 틀린 게 아니라 우리가 앞선 것이다. 한 분기 전
                # 기준으로 계산한 값이 네이버와 맞으면 그렇게 본다.
                # 지연 후보를 하나씩 대 본다. 하나라도 맞으면 '우리가 틀린 것'이
                # 아니라 '네이버가 아직 안 따라온 것'이다. 지연값은 분모(주식수)도
                # 같이 움직여서 딱 떨어지지 않으므로 허용폭을 따로 둔다.
                alts = []
                if key in ("eps", "bps"):
                    alts = lag.get(key) or []
                elif key == "per" and p:
                    alts = [round(p / e2, 2) for e2 in (lag.get("eps") or []) if e2 and e2 > 0]
                elif key == "pbr" and p:
                    alts = [round(p / b2, 2) for b2 in (lag.get("bps") or []) if b2 and b2 > 0]
                hit = next((a for a in alts if a and abs(a - ref) / abs(ref) <= LAG_TOL), None)
                if hit is not None:
                    rec[key] = f"naver_lag({ours} vs {ref} · 과거기준 {hit})"
                    continue
                rec[key] = f"mismatch({ours} vs {ref})"
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
        lag = [tk for tk, r in results.items() if str(r.get(field, "")).startswith("naver_lag")]
        ok = sum(1 for r in results.values() if r.get(field) == "ok")
        return blank, mism, ok, lag

    # 대형 오차(>25%) 색출 — 우선 수정 대상(정밀격차가 아닌 진짜 버그)
    big = []
    for tk, r in results.items():
        for field in ("per", "pbr", "eps", "bps", "div", "roe"):
            s = str(r.get(field, ""))
            mm = re.search(r"mismatch\(([\-\d.]+) vs ([\d.]+)\)", s)
            if mm:
                o, ref = float(mm.group(1)), float(mm.group(2))
                if ref and abs(o - ref) / abs(ref) > 0.25:
                    big.append((abs(o - ref) / abs(ref), field, tk, o, ref))
    big.sort(reverse=True)

    lines = [f"# 밸류에이션 자동 검증 — {datetime.datetime.utcnow()+datetime.timedelta(hours=9):%Y-%m-%d %H:%M} KST",
             f"# 데이터일자 {day} · 검증 {len(results)}/{len(val)}종목 · 허용오차 {TOL*100:.0f}%",
             f"# 네이버 제공 항목(코드): {', '.join(state.get('naver_codes', []))}", ""]
    lines.append(f"⛔ 대형 오차(>25%) — 우선 수정 대상: {len(big)}건")
    for d, field, tk, o, ref in big[:60]:
        lines.append(f"   {d*100:4.0f}% [{field}] {nm.get(tk,tk)}({tk}) {o} vs {ref}")
    lines.append("")
    for field, label in (("per", "PER"), ("pbr", "PBR"), ("eps", "EPS"), ("bps", "BPS"), ("div", "배당수익률"), ("roe", "ROE")):
        blank, mism, ok, lag = tally(field, label)
        # 오차 크기순 정렬(큰 것 먼저)
        def _mag(t):
            mm = re.search(r"mismatch\(([\-\d.]+) vs ([\d.]+)\)", str(results[t].get(field, "")))
            return abs(float(mm.group(1)) - float(mm.group(2))) / abs(float(mm.group(2))) if (mm and float(mm.group(2))) else 0
        mism.sort(key=_mag, reverse=True)
        lines.append(f"[{label}] 일치 {ok} · 빈칸 {len(blank)} · 불일치 {len(mism)}"
                     + (f" · 네이버가 아직 안 따라옴 {len(lag)}" if lag else ""))
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
        blank, mism, ok, lag = tally(field, label)
        log(f"  [{label}] 일치 {ok} · 빈칸 {len(blank)} · 불일치 {len(mism)}"
            + (f" · 네이버 미추종 {len(lag)}" if lag else ""))
    total_mism = sum(1 for r in results.values() for f in ("per", "pbr", "eps", "bps", "div", "roe")
                     if str(r.get(f, "")).startswith("mismatch"))
    if len(results) >= len(val):
        log(f"\n✅ AUDIT_COMPLETE — 전 종목 검증. 불일치 총 {total_mism}건(0이어야 정상) → data/valuation_audit.txt")
    else:
        log(f"\n- AUDIT_REMAINING {len(val)-len(results)}개 남음(다음 실행 이어받기)")


if __name__ == "__main__":
    main()
