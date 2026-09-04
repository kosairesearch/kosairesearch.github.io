#!/usr/bin/env python3
"""BPS 를 잘못된 주식수로 나눈 리포트를 바로잡는다.

무엇이 잘못됐나
---------------
EPS 와 BPS 를 같은 분모(가중평균 유통주식수)로 나누고 있었다. EPS 는 그게
맞다 — 한 해 동안 번 돈이니 그 기간의 평균 주식수로 나눠야 한다.

BPS 는 아니다. 자본은 '지금 이 시점' 의 값이라 '지금 이 시점' 의 주식수로
나눠야 한다. 연중에 주식을 크게 늘린 회사는 이 둘이 크게 벌어진다.

    태영건설  발행주식총수 298,240,052  ·  가중평균 159,368,756  (1.87배)
              우리 BPS 3,673  ·  KRX 공식 BPS 2,037

    자본을 절반의 주식수로 나눠서 BPS 가 1.8배로 나왔다. BPS 가 크면
    PBR 은 그만큼 작아진다 — 실제보다 싸 보인다.

평소에는 티가 안 난다. 주식수가 그대로인 회사는 가중평균과 기말 주식수가
거의 같기 때문이다. 2,563종목 중 이 문제가 드러나는 건 86종목이다.

왜 '기말 주식수로 바꿔라' 로 끝내지 않나
----------------------------------------
KRX 가 무엇으로 나누는지 재 봤더니 한 가지가 아니었다. 판별력이 있는
523종목에서 가중평균이 382건, 발행총수가 119건이었다. KRX 는 '발행주식수
− 자기주식' 을 쓰는데, 자기주식이 많은 회사에서는 그게 가중평균과 비슷해지고
연중 증자한 회사에서는 발행총수와 비슷해진다. 우리는 자기주식 수를 따로
갖고 있지 않아서 어느 쪽인지 미리 알 수 없다.

그래서 규칙으로 정하지 않고 **KRX 에게 물어본다.**

    KRX 가 나눈 주식수 = 최근 결산 지배지분 ÷ KRX 가 공표한 BPS

이렇게 역산한 수가 우리 주식수 후보 중 하나와 3% 안에서 맞으면, KRX 가 그걸
썼다는 뜻이다. 우리가 다른 걸 썼고 그 차이가 8% 를 넘을 때만 손댄다.

무엇을 고치나
-------------
분자(분기말 자본)는 그대로 둔다. 그게 우리가 KRX 보다 나은 점이다 — KRX 는
최근 결산 자본을 쓰는데 우리는 분기말 자본을 쓴다. 분모만 바꾼다.

    새 BPS = (기존 BPS × 기존 분모) ÷ KRX 가 쓴 분모
    새 PBR = 주가 ÷ 새 BPS

EPS·PER·ROE 는 건드리지 않는다. 그쪽 분모는 원래 맞다.

  실행
    python3 scripts/patch_bps_denominator.py            무엇을 바꿀지 보여만 준다
    python3 scripts/patch_bps_denominator.py --write    실제로 고친다
"""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports_v2"

MATCH_TOL = 0.03      # KRX 역산값이 후보와 이만큼 안에서 맞으면 '그걸 썼다'
OURS_TOL = 0.08       # 우리 분모가 이만큼 넘게 벗어나야 손댄다


def candidates(v):
    return {k: x for k, x in (("발행총수", v.get("total_shares")),
                              ("가중평균", v.get("wavg_shares")),
                              ("시장주식수", v.get("shares"))) if x}


def plan_one(j):
    """이 리포트를 고쳐야 하는가. 고친다면 무엇으로. 아니면 None."""
    q = j.get("quant") or {}
    v = q.get("valuation") or {}
    bps, price = v.get("bps"), v.get("price")
    krx = v.get("bps_krx")
    if not (bps and krx and krx > 0 and price):
        return None
    ann = [a for a in (q.get("annual") or []) if isinstance(a, dict)]
    if not ann:
        return None
    fy_eqo = ann[0].get("equity_owner") or ann[0].get("equity")
    if not (fy_eqo and fy_eqo > 0):
        return None

    ours_name = "가중평균" if v.get("wavg_shares") else "발행총수"
    ours_den = v.get("wavg_shares") or v.get("total_shares")
    if not ours_den:
        return None

    implied = fy_eqo / krx                      # KRX 가 나눈 주식수
    cands = candidates(v)
    if not cands:
        return None
    best = min(cands, key=lambda k: abs(cands[k] / implied - 1))
    if abs(cands[best] / implied - 1) > MATCH_TOL:
        return None                             # KRX 를 재현 못 한다 — 손대지 않는다
    if abs(ours_den / implied - 1) <= OURS_TOL or best == ours_name:
        return None                             # 우리도 같은 걸 썼다

    new_den = cands[best]
    new_bps = int(round(bps * ours_den / new_den))
    if new_bps <= 0:
        return None
    new_pbr = round(price / new_bps, 4)
    return {"from_name": ours_name, "from_den": ours_den, "to_name": best, "to_den": new_den,
            "old_bps": bps, "new_bps": new_bps,
            "old_pbr": v.get("pbr"), "new_pbr": new_pbr, "krx": krx}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="실제로 파일을 고친다")
    args = ap.parse_args()

    plans, worse = [], []
    for f in sorted(REPORTS.glob("*.json")):
        if not re.fullmatch(r"\d{6}", f.stem):
            continue
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        p = plan_one(j)
        if not p:
            continue
        # 고쳐서 오히려 KRX 에서 멀어지면 고치지 않는다. 이 검사가 없으면
        # '고쳤다' 는 사실만 남고 좋아졌는지는 아무도 모른다.
        before = abs(p["old_bps"] / p["krx"] - 1)
        after = abs(p["new_bps"] / p["krx"] - 1)
        p.update(tk=f.stem, name=j.get("name"), sector=j.get("sector"),
                 before=before, after=after, path=f)
        (plans if after < before else worse).append(p)

    plans.sort(key=lambda p: -(p["before"] - p["after"]))
    print(f"고칠 종목 {len(plans)}건" + (f" · 고치면 나빠져서 건너뛴 것 {len(worse)}건" if worse else ""))
    print(f"{'종목':<22}{'분모 바꿈':<26}{'BPS 우리→새값(KRX)':<34}{'KRX 대비 오차'}")
    print("─" * 118)
    for p in plans[:40]:
        print(f"{(p['name'] or '')[:10]}({p['tk']}){'':<6}"
              f"{p['from_name']}→{p['to_name']:<16}"
              f"{p['old_bps']:>9,} → {p['new_bps']:>9,} ({p['krx']:>9,.0f}){'':<4}"
              f"{p['before']*100:>5.0f}% → {p['after']*100:>4.0f}%")
    if len(plans) > 40:
        print(f"  … 외 {len(plans)-40}건")
    if worse:
        print("\n건너뛴 것(고치면 KRX 에서 더 멀어진다):")
        for p in worse[:10]:
            print(f"  {p['name']}({p['tk']}) {p['before']*100:.0f}% → {p['after']*100:.0f}%")

    # 분모를 바로잡고도 KRX 에서 30% 넘게 떨어져 있으면, 그 종목은 분모 말고
    # 다른 것도 틀렸다는 뜻이다. 반쯤 고친 값을 보여 주면 '고쳐졌다' 는 인상만
    # 남고 숫자는 여전히 틀리다. 그런 건 값을 지운다 — 화면에 '—' 로 나오고,
    # 리포트를 다시 만들면 제대로 채워진다.
    hide = [p for p in plans if p["after"] > 0.30]
    fix = [p for p in plans if p["after"] <= 0.30]
    if hide:
        print(f"\n분모를 고쳐도 KRX 와 30% 넘게 벌어지는 {len(hide)}건 — 값을 지운다"
              f"(분모 말고 다른 것도 틀렸다):")
        for p in hide:
            print(f"  {p['name']}({p['tk']}) {p['before']*100:.0f}% → {p['after']*100:.0f}%")

    if not args.write:
        print(f"\n※ 보여주기만 했다 — 고칠 {len(fix)}건 · 지울 {len(hide)}건. 실제로 하려면 --write")
        return

    grid_edits = {}
    for p in fix + hide:
        j = json.loads(p["path"].read_text(encoding="utf-8"))
        v = j["quant"]["valuation"]
        if p in fix:
            v["bps"], v["pbr"] = p["new_bps"], p["new_pbr"]
            v["bps_denom_fixed"] = p["to_name"]          # 무엇으로 바꿨는지 남긴다
            grid_edits[p["tk"]] = p["new_bps"]
        else:
            v["bps"] = v["pbr"] = None
            v["bps_hidden_reason"] = "분모를 바로잡아도 KRX 공식 BPS 와 크게 어긋난다"
            grid_edits[p["tk"]] = None
        p["path"].write_text(json.dumps(j, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # 화면 그리드도 같은 값을 들고 있다. 한쪽만 고치면 리포트와 목록이 어긋난다.
    gp = ROOT / "data" / "valuation.js"
    if gp.exists() and grid_edits:
        raw = gp.read_text(encoding="utf-8")
        m = re.search(r"(window\.KOS_VALUATION\s*=\s*)(\{.*?)(;?\s*)$", raw, re.S)
        if m:
            data = json.loads(m.group(2).rstrip().rstrip(";"))
            n = 0
            for tk, val in grid_edits.items():
                row = (data.get("stocks") or {}).get(tk)
                if not row or "bps" not in row:
                    continue
                if val is None:
                    row.pop("bps", None)
                else:
                    row["bps"] = val
                n += 1
            gp.write_text(m.group(1) + json.dumps(data, ensure_ascii=False,
                                                  separators=(",", ":")) + ";\n",
                          encoding="utf-8")
            print(f"화면 그리드(valuation.js) {n}건도 맞췄다.")

    print(f"\n고친 {len(fix)}건 · 지운 {len(hide)}건.")


if __name__ == "__main__":
    main()
