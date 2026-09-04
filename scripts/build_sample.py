#!/usr/bin/env python3
"""검증용 173종목 표본을 뽑는다 — 매번 같은 종목이 나오게.

왜 표본인가
-----------
전 종목(2,563)에 규칙을 돌리면 숫자는 나오지만 사람이 한 건씩 되짚을 수가
없다. 되짚지 못한 경보는 없는 것과 같다. 실제로 그래서 오탐이 쌓였다.

왜 하필 업종을 갈라 뽑나
------------------------
회계가 업종마다 다르다. 보험은 IFRS17 할인율 때문에 기타포괄손익이 순이익의
수십 배로 움직이고, 은행은 '매출액' 이라는 항목 자체가 없으며, 증권·리츠는
부채비율이 수백~수천%인 게 정상이고, 지주는 비지배지분이 지배지분만큼 크다.

제조업 상위 10종목만 보고 만든 규칙은 이 다섯 곳에서 반드시 깨진다.
실제로 삼성생명이 '자본이 이익보다 빠르게 늘었다' 로 걸렸는데, DART 원문을
떠 보니 우리 추출이 정확했다 — 규칙이 틀렸던 것이다. 맞는 값을 지우는
검증은 없는 것만 못하다.

그래서 특수 회계 업종을 일부러 두껍게 담는다. 보험 13종목은 전수다.

표본 구성 (173)
---------------
  ① 특수 회계        73  보험 13(전수) · 금융 20 · 지주 20 · 부동산리츠 20
  ② 나머지 업종       75  25개 업종 × 대·중·소 각 1
  ③ 깨지기 쉬운 것    25  빈칸 · KRX폴백 · 적자 · 극단 PER/PBR · 비지배지분 큼

  실행:  python3 scripts/build_sample.py
  결과:  data/verify_sample.json
"""
import json
import os
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports_v2"
OUT = ROOT / "data" / "verify_sample.json"

# 회계가 달라서 반드시 두껍게 봐야 하는 업종 → 뽑을 수
HEAVY = {"보험": 13, "금융": 20, "지주": 20, "부동산·리츠": 20}
PER_OTHER_SECTOR = 3          # 나머지 업종은 대·중·소 하나씩
FRAGILE_TARGET = 25


def load():
    out = {}
    for f in sorted(REPORTS.glob("*.json")):
        tk = f.stem
        if not re.fullmatch(r"\d{6}", tk):
            continue
        try:
            out[tk] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return out


def mcap(j):
    v = (j.get("quant") or {}).get("valuation") or {}
    return v.get("mcap") or 0


def pick_spread(items, n):
    """시가총액 순으로 늘어놓고 n 개를 고르게 집는다.

    상위 n 개를 집으면 큰 회사만 남는다. 큰 회사는 공시가 깔끔해서 오류가
    잘 안 난다 — 정작 깨지는 건 작은 회사다. 그래서 등간격으로 집는다."""
    if not items:
        return []
    items = sorted(items, key=lambda t: -mcap(t[1]))
    if len(items) <= n:
        return [tk for tk, _ in items]
    step = (len(items) - 1) / (n - 1) if n > 1 else 1
    idx = sorted({int(round(i * step)) for i in range(n)})
    # 반올림이 겹치면 뒤에서 채운다
    i = 0
    while len(idx) < n and i < len(items):
        if i not in idx:
            idx.append(i)
            idx.sort()
        i += 1
    return [items[i][0] for i in idx[:n]]


def fragile(rows, already):
    """규칙이 깨지기 쉬운 자리들. 각 유형에서 몇 개씩 가져온다."""
    buckets = defaultdict(list)
    for tk, j in rows.items():
        if tk in already:
            continue
        v = (j.get("quant") or {}).get("valuation") or {}
        q = j.get("quant") or {}
        eps, bps = v.get("eps"), v.get("bps")
        per, pbr = v.get("per"), v.get("pbr")
        bk = v.get("bps_krx")

        if eps is None and bps is None:
            buckets["둘다빈칸"].append(tk)
        if v.get("bps_src") == "KRX":
            buckets["KRX폴백"].append(tk)
        if eps is not None and eps < 0:
            buckets["적자"].append(tk)
        if per and per > 200:
            buckets["극단PER"].append(tk)
        if pbr and (pbr > 20 or pbr < 0.15):
            buckets["극단PBR"].append(tk)
        if bps and bk and bk > 0 and abs(bps / bk - 1) > 0.5:
            buckets["KRX와크게어긋남"].append(tk)
        ann = [a for a in (q.get("annual") or []) if isinstance(a, dict)]
        if ann and ann[0].get("equity_nci") and ann[0].get("equity"):
            if abs(ann[0]["equity_nci"]) > abs(ann[0]["equity"]) * 0.3:
                buckets["비지배지분큼"].append(tk)
        if v.get("total_shares") and v.get("wavg_shares"):
            r = v["total_shares"] / v["wavg_shares"]
            if r > 1.3 or r < 0.77:
                buckets["주식수차이큼"].append(tk)

    # 유형마다 골고루 담되, 목표 수에 모자라면 유형을 한 바퀴씩 더 돌며 채운다.
    # 어느 한 유형만으로 채우면 그 유형에만 강한 검증이 된다.
    out, depth = [], 0
    while len(out) < FRAGILE_TARGET and depth < 50:
        added = False
        for name in sorted(buckets):
            lst = sorted(buckets[name])
            if depth < len(lst) and lst[depth] not in out:
                out.append(lst[depth])
                added = True
                if len(out) >= FRAGILE_TARGET:
                    break
        if not added:
            break
        depth += 1
    return out[:FRAGILE_TARGET], {k: len(v) for k, v in sorted(buckets.items())}


def main():
    rows = load()
    by_sec = defaultdict(list)
    for tk, j in rows.items():
        by_sec[j.get("sector") or "(없음)"].append((tk, j))

    picked, why = [], {}

    def add(tk, reason):
        if tk not in why:
            picked.append(tk)
            why[tk] = reason

    # ① 특수 회계 업종
    for sec, n in HEAVY.items():
        for tk in pick_spread(by_sec.get(sec, []), n):
            add(tk, f"특수회계·{sec}")

    # ② 나머지 업종 — 대·중·소
    for sec in sorted(by_sec):
        if sec in HEAVY:
            continue
        for tk in pick_spread(by_sec[sec], PER_OTHER_SECTOR):
            add(tk, f"업종·{sec}")

    # ③ 깨지기 쉬운 것
    frag, stats = fragile(rows, set(why))
    for tk in frag:
        add(tk, "취약")

    sample = {
        "생성기준": "scripts/build_sample.py",
        "종목수": len(picked),
        "업종별두껍게": HEAVY,
        "취약유형별전체수": stats,
        "종목": [
            {"ticker": tk, "name": rows[tk].get("name"),
             "sector": rows[tk].get("sector"), "market": rows[tk].get("market"),
             "mcap": mcap(rows[tk]), "뽑은이유": why[tk]}
            for tk in picked
        ],
    }
    OUT.write_text(json.dumps(sample, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"표본 {len(picked)}종목 → {OUT.relative_to(ROOT)}")
    cnt = defaultdict(int)
    for tk in picked:
        cnt[rows[tk].get("sector")] += 1
    print("\n업종별:")
    for k in sorted(cnt, key=lambda k: -cnt[k]):
        mark = " ★특수회계" if k in HEAVY else ""
        print(f"  {k}: {cnt[k]}{mark}")
    print("\n취약 유형별 전체 모집단:")
    for k, v in stats.items():
        print(f"  {k}: {v}종목")


if __name__ == "__main__":
    main()
