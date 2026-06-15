#!/usr/bin/env python3
"""X(트위터) 게시용 스레드 자동 생성 — 우리 데이터에서 '오늘 올릴 글'을 뽑는다.

비용 0(LLM 미사용·외부호출 없음). data/valuation.js + data/stocks.js만 읽어
스크리닝 인사이트 스레드와 종목 스냅샷을 게시용 텍스트로 출력한다.
운영: 사람이 검토 후 게시(자동 포스팅 X — 스팸·계정정지 방지).

원칙: 매수/매도 단정·권유 금지(중립). 정확한 수치는 '오늘 기준' 스냅샷.
출력: marketing/x_threads_YYYYMMDD.txt
"""
import json
import re
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "marketing"
SITE = "kosai.kr"


def loadjs(path, var):
    t = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(re.escape(var) + r"\s*=\s*(\{.*)", t, re.S)
    return json.loads(m.group(1).rstrip().rstrip(";"))


def main():
    val = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"]
    live = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")["stocks"]
    reports = set(p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json"))

    # 종목 결합 — 상위 시총 위주(인지도 높은 종목이 인게이지먼트↑)
    rows = []
    for s in sorted(live, key=lambda x: x.get("mcap", 0) or 0, reverse=True):
        tk = s["ticker"]
        e = val.get(tk)
        if not e:
            continue
        p = s.get("price")
        eps, bps, roe, dps = e.get("eps"), e.get("bps"), e.get("roe"), e.get("dps")
        per = round(p / eps, 1) if (eps and eps > 0 and p) else None
        pbr = round(p / bps, 2) if (bps and p) else None
        div = round(dps / p * 100, 2) if (dps and p) else None
        rows.append({"tk": tk, "name": s.get("name"), "sector": s.get("sector"),
                     "mcap": s.get("mcap"), "price": p, "per": per, "pbr": pbr,
                     "roe": roe, "div": div, "has_report": tk in reports})

    # 인지도 높은 상위 200 시총으로 제한 → 트친들이 아는 종목, 인게이지먼트↑
    top = [r for r in rows[:200]]

    # 상식 범위 필터(이상치·추출 잡음 제외) — 비현실적 숫자 노출은 신뢰 직결
    def sane(r, field, lo, hi):
        v = r.get(field)
        return v is not None and lo <= v <= hi

    threads = []

    # ── 스레드 1: 고ROE TOP 5 (현실 범위 5~80%) ──
    hi_roe = sorted([r for r in top if sane(r, "roe", 5, 80)], key=lambda r: r["roe"], reverse=True)[:5]
    if hi_roe:
        lines = ["🧵 자본을 가장 잘 굴리는 코스피 대형주 — ROE TOP 5 (오늘 기준)", ""]
        for i, r in enumerate(hi_roe, 1):
            lines.append(f"{i}. {r['name']} — ROE {r['roe']}%")
        lines += ["",
                  "ROE는 회사가 자기자본으로 얼마나 이익을 내는지를 보여주는 핵심 지표.",
                  "단, 높은 ROE가 곧 '싸다'는 뜻은 아님 — 밸류에이션은 따로 봐야 함.",
                  "",
                  f"PER·PBR·배당까지 한눈에 → {SITE}",
                  "#주식 #코스피 #ROE #가치투자"]
        threads.append("\n".join(lines))

    # ── 스레드 2: 저PER (현실 범위 1~40배) ──
    lo_per = sorted([r for r in top if sane(r, "per", 1, 40)], key=lambda r: r["per"])[:5]
    if lo_per:
        lines = ["🧵 이익 대비 저평가? 코스피 대형주 저PER 5선 (오늘 기준)", ""]
        for i, r in enumerate(lo_per, 1):
            lines.append(f"{i}. {r['name']} — PER {r['per']}배")
        lines += ["",
                  "PER이 낮다는 건 이익 대비 주가가 낮다는 뜻 — 다만 '왜 싼지'를 봐야 함(업황·일회성 이익 등).",
                  "",
                  f"실적 추이·AI 분석까지 → {SITE}",
                  "#주식 #저PER #밸류에이션 #코스피"]
        threads.append("\n".join(lines))

    # ── 스레드 3: 고배당 (현실 범위 0.5~12%, 특별배당 등 이상치 제외) ──
    hi_div = sorted([r for r in top if sane(r, "div", 0.5, 12)], key=lambda r: r["div"], reverse=True)[:5]
    if hi_div:
        lines = ["🧵 배당 챙기는 투자자라면 — 코스피 대형주 고배당 5선 (오늘 기준)", ""]
        for i, r in enumerate(hi_div, 1):
            lines.append(f"{i}. {r['name']} — 배당수익률 {r['div']}%")
        lines += ["",
                  "배당수익률 = 주당 배당금 ÷ 현재가. 주가가 떨어지면 수익률은 올라가니 '왜 높은지'도 확인.",
                  "",
                  f"배당·실적·밸류에이션 → {SITE}",
                  "#배당주 #고배당 #주식 #코스피"]
        threads.append("\n".join(lines))

    # ── 스레드 4: 종목 스냅샷(리포트 보유 + 인지도 높은 1종목 회전) ──
    day = datetime.date.today()
    spot_pool = [r for r in top if r["has_report"] and sane(r, "per", 1, 60) and sane(r, "roe", -20, 80)]
    if spot_pool:
        r = spot_pool[day.toordinal() % len(spot_pool)]   # 매일 다른 종목 회전
        lines = [f"🧵 {r['name']}, 숫자로 보는 현재 (오늘 기준)", "",
                 f"· 업종: {r['sector']}",
                 f"· PER {r['per']}배 / PBR {r['pbr']}배" if r["pbr"] else f"· PER {r['per']}배",
                 f"· ROE {r['roe']}%" + (f" / 배당수익률 {r['div']}%" if r["div"] else ""),
                 "",
                 "매수·매도 의견 없이, 팩트와 AI 분석만.",
                 f"전체 리포트 → {SITE} 에서 '{r['name']}' 검색",
                 f"#{r['name'].replace(' ','')} #주식 #{(r['sector'] or '').replace(' ','')}"]
        threads.append("\n".join(lines))

    # ── 출력 ──
    OUTDIR.mkdir(exist_ok=True)
    out = OUTDIR / f"x_threads_{day:%Y%m%d}.txt"
    head = [f"# KOSAI X 스레드 초안 — {day:%Y-%m-%d}",
            "# 검토 후 게시. 각 블록이 1개 게시물(또는 스레드). 숫자는 '오늘 기준' 스냅샷.",
            "# 매수/매도 단정 금지 — 중립 유지.",
            "=" * 60, ""]
    body = ("\n\n" + "-" * 60 + "\n\n").join(threads)
    out.write_text("\n".join(head) + body + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))
    print(f"\n→ {out} ({len(threads)}개 스레드)")


if __name__ == "__main__":
    main()
