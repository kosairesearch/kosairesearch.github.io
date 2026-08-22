#!/usr/bin/env python3
"""리포트에 굳어 있는 옛날 주식수로 계산된 EPS·BPS 를 바로잡는다.

무엇이 잘못됐나
---------------
리포트를 만들 때의 주식수로 EPS·BPS 를 계산해 저장해 둔다. 그 뒤 회사가
액면병합이나 감자를 하면 주식수가 바뀌는데, 리포트는 다시 만들지 않는 한
옛날 분모를 그대로 들고 있다.

    한국제지  리포트 190,150,720주  →  오늘 38,030,144주  (정확히 5배)
    기가레인  리포트  84,883,347주  →  오늘  8,488,334주  (정확히 10배)

BPS 가 5배 작으면 PBR 은 5배 크게 나온다. 화면의 PER·PBR 은 현재가를 우리
EPS·BPS 로 나눠 만들기 때문에, 분모 하나가 틀리면 네 값이 다 틀린다.

어떻게 고치나
-------------
주식수가 바뀐 이유를 셋으로 나눈다. 이유마다 할 수 있는 일이 다르다.

  ① ±10% 안쪽          자기주식 취득·소각, 소규모 증자 같은 잔변동.
                       원래 오차 범위 안이다. 건드리지 않는다.

  ② 정확히 n배·1/n배   액면병합·액면분할·감자. 자본과 순이익은 그대로이고
                       주식 수만 바뀐 것이므로, EPS·BPS 에 그 배수를
                       곱하면 정확히 맞는다. 추정이 아니라 산수다.

  ③ 그 밖의 배수       증자처럼 자본 자체가 바뀐 경우가 섞여 있다. 자본이
                       얼마가 됐는지는 새 재무제표를 받아야 알 수 있다.
                       모르는 것을 아는 척하지 않는다 — EPS·BPS 를 지운다.
                       화면에서는 '—' 로 나오고, 리포트를 다시 만들면
                       제대로 채워진다.

ROE 와 TTM 순이익은 주식수와 무관하므로 그대로 둔다.

쓰는 법
-------
    python3 scripts/patch_share_counts.py            # 무엇이 바뀌는지만 본다
    python3 scripts/patch_share_counts.py --apply    # 실제로 고친다
"""
import json, glob, os, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPLY = "--apply" in sys.argv
TODAY = datetime.date.today().isoformat()

DRIFT = 0.10        # 이 안쪽은 잔변동으로 보고 건드리지 않는다
TOL = 0.01          # n배로 인정하는 오차
MAX_N = 40


def log(m): print(m, flush=True)


def current_shares():
    """오늘 자 KRX 상장주식수. data/stocks.js 는 매일 갱신된다."""
    raw = open(os.path.join(ROOT, "data", "stocks.js"), encoding="utf-8").read()
    d = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    return {s["ticker"]: s for s in d["stocks"]}


def clean_factor(r):
    """r 이 n배 또는 1/n배에 (오차 1% 안에서) 맞으면 그 값을, 아니면 None."""
    for n in range(2, MAX_N + 1):
        for cand in (float(n), 1.0 / n):
            if abs(r / cand - 1) < TOL:
                return cand
    return None


def fix_mixed_eps(files, cur, apply):
    """주당이익 기준이 섞인 종목을 바로잡는다.

    회사가 작년에 공시한 주당이익은 옛 주식수 기준이고 올해 공시한 것은 새
    주식수 기준이다. 액면병합·감자를 한 회사에서 그 둘을 그대로 더하고 빼면
    단위가 다른 것을 섞게 된다.

    순이익은 주당이 아니라 총액이고 주식수는 현재 기준이므로 그 길은 기준이
    섞이지 않는다. 두 길이 30% 넘게 벌어지고 차이가 배수로 떨어지면 순이익
    쪽으로 바꾼다. 배수로 안 떨어지면 원인이 다른 것이므로 두고 본다."""
    fixed, hidden = [], []
    for path in files:
        tk = os.path.basename(path)[:-5]
        s = cur.get(tk)
        if not s:
            continue
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        q = doc.get("quant")
        if not isinstance(q, dict):
            continue
        v = q.get("valuation") or {}
        qs = [x for x in (q.get("quarterly") or []) if isinstance(x, dict)]
        a = v.get("eps")
        w = v.get("wavg_shares") or v.get("total_shares")
        if a is None or not w or len(qs) < 4:
            continue
        npo = [x.get("np_owner") for x in qs[-4:]]
        if any(n is None for n in npo):
            continue
        b = sum(npo) / w
        if abs(a) < 100 or abs(b) < 100:
            continue
        if abs(a - b) <= 0.30 * max(abs(a), abs(b)):
            continue
        r = abs(b / a)
        f = clean_factor(r)
        if not f:
            # 배수로도 안 떨어진다 = 회사가 공시한 두 값이 서로 다르다.
            # 어느 쪽이 맞는지 모르므로 안 보여준다. 틀린 숫자보다 빈칸이 낫다.
            # 두 공시가 어긋난다는 건 '주당' 으로 환산하는 분모(가중평균주식수)를
            # 못 믿는다는 뜻이기도 하다. BPS 도 같은 분모로 나눈 값이므로 같이
            # 숨긴다. 실제로 이마트는 이 분모가 틀려 BPS 824,830원·PBR 0.09 라는
            # 말이 안 되는 값이 화면에 나가고 있었다.
            for k in ("eps", "per", "bps", "pbr"):
                v[k] = None
            v["eps_hidden"] = {"on": TODAY, "공시": a, "순이익÷주식수": int(b),
                               "배수": round(r, 2),
                               "why": "두 공시가 어긋나 어느 쪽인지 모른다"}
            hidden.append((s.get("name", tk), tk, a, int(b), r))
            if apply:
                with open(path, "w", encoding="utf-8") as fp:
                    json.dump(doc, fp, ensure_ascii=False, indent=1)
            continue
        v["eps"] = int(round(b))
        px = s.get("price")
        if px:
            v["price"] = px
            v["per"] = round(px / v["eps"], 2) if v["eps"] > 0 else None
        v["eps_basis_fixed"] = {"on": TODAY, "공시": a, "순이익÷주식수": int(b),
                                "배수": round(r, 2),
                                "why": "액면병합·감자로 주당이익 기준이 섞였다"}
        fixed.append((s.get("name", tk), tk, a, int(b), r))
        if apply:
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(doc, fp, ensure_ascii=False, indent=1)
    return fixed, hidden


def main():
    cur = current_shares()
    files = sorted(glob.glob(os.path.join(ROOT, "data", "reports_v2", "*.json"))
                   + glob.glob(os.path.join(ROOT, "data", "reports", "*.json")))

    skipped = fixed = cleared = 0
    fixes, clears = [], []

    for path in files:
        tk = os.path.basename(path)[:-5]
        s = cur.get(tk)
        if not s:
            continue
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        val = (doc.get("quant") or {}).get("valuation")
        if not val:
            continue

        old_sh, new_sh = val.get("shares"), s.get("shares")
        if not old_sh or not new_sh:
            continue
        ratio = old_sh / new_sh
        if abs(ratio - 1) <= DRIFT:
            skipped += 1
            continue

        name = s.get("name", tk)
        price = s.get("price")
        f = clean_factor(ratio)

        if f:
            # ② 자본·순이익은 그대로, 분모만 바뀌었다 → 배수를 곱한다
            for k in ("eps", "bps", "bps_krx"):
                if val.get(k) is not None:
                    val[k] = round(val[k] * f) if k != "bps_krx" else round(val[k] * f, 1)
            for k, div in (("total_shares", f), ("wavg_shares", f)):
                if val.get(k):
                    val[k] = int(round(val[k] / div))
            val["shares"] = new_sh
            if price:
                val["price"] = price
                val["per"] = round(price / val["eps"], 2) if val.get("eps") else None
                val["pbr"] = round(price / val["bps"], 2) if val.get("bps") else None
                val["pbr_krx"] = (round(price / val["bps_krx"], 2)
                                  if val.get("bps_krx") else None)
            val["shares_patched"] = {"on": TODAY, "was": old_sh, "now": new_sh,
                                     "factor": f, "why": "액면병합·분할·감자 — 배수로 환산"}
            fixed += 1
            fixes.append((name, tk, ratio, f, val.get("bps"), val.get("eps")))
        else:
            # ③ 자본이 얼마가 됐는지 모른다 → 지운다
            for k in ("eps", "bps", "per", "pbr", "bps_krx", "pbr_krx"):
                val[k] = None
            val["shares"] = new_sh
            if price:
                val["price"] = price
            val["shares_patched"] = {"on": TODAY, "was": old_sh, "now": new_sh,
                                     "factor": None,
                                     "why": "주식수가 배수로 안 떨어진다(증자 등) — "
                                            "자본을 다시 받아야 해서 값을 숨긴다"}
            cleared += 1
            clears.append((name, tk, ratio))

        if APPLY:
            # generate_reports_v2.py 와 같은 모양으로 쓴다(indent=1). 형식이
            # 갈리면 한 줄만 고쳐도 파일 전체가 바뀐 것으로 보여 diff 를 못 읽는다.
            with open(path, "w", encoding="utf-8") as fp:
                json.dump(doc, fp, ensure_ascii=False, indent=1)

    eps_fixed, eps_hidden = fix_mixed_eps(files, cur, APPLY)

    # 화면이 실제로 읽는 건 data/valuation.js 다. 리포트만 고치고 두면 다음
    # 수집이 돌 때까지 사이트에는 틀린 값이 그대로 걸려 있다. 같이 고친다.
    vpath = os.path.join(ROOT, "data", "valuation.js")
    touched = 0
    if os.path.exists(vpath):
        raw = open(vpath, encoding="utf-8").read()
        head, body = raw[:raw.find("{")], raw[raw.find("{"): raw.rfind("}") + 1]
        tail = raw[raw.rfind("}") + 1:]
        vd = json.loads(body)
        for name, tk, ratio, f, bps, eps in fixes:
            e = vd["stocks"].get(tk)
            if not e:
                continue
            if bps is not None: e["bps"] = bps
            if eps is not None: e["eps"] = eps
            e["_d"] = TODAY
            touched += 1
        for name, tk, a, b, r in eps_fixed:
            e = vd["stocks"].get(tk)
            if e:
                e["eps"] = b
                e["_d"] = TODAY
                touched += 1
        for name, tk, a, b, r in eps_hidden:
            e = vd["stocks"].get(tk)
            if e:
                e.pop("eps", None); e.pop("bps", None)
                e["_d"] = TODAY
                touched += 1
        for name, tk, ratio in clears:
            e = vd["stocks"].get(tk)
            if not e:
                continue
            e.pop("bps", None); e.pop("eps", None)
            e["_d"] = TODAY
            touched += 1
        if APPLY:
            with open(vpath, "w", encoding="utf-8") as fp:
                fp.write(head + json.dumps(vd, ensure_ascii=False,
                                           separators=(",", ":")) + tail)

    log(f"\n{'고쳤다' if APPLY else '고칠 것(미적용)'} — 리포트 {len(files):,}개 훑음\n")
    log(f"  valuation.js 에서 손댄 종목        {touched:,}")
    log(f"  ① 그대로 둠 (±{int(DRIFT*100)}% 잔변동)  {skipped:,}")
    log(f"  ② 배수로 환산                  {fixed:,}")
    log(f"  ③ 값을 숨김                    {cleared:,}")
    log(f"\n  주당이익 기준이 섞여 바로잡음   {len(eps_fixed):,}")
    log(f"  두 공시가 어긋나 숨김          {len(eps_hidden):,}")
    for name, tk, a, b, r in sorted(eps_fixed, key=lambda x: -x[4])[:10]:
        log(f"     {name}({tk})  공시 {a:,} → {b:,}  ({r:.1f}배)")

    if fixes:
        log("\n② 환산한 종목 (상위 15)")
        for n, t, r, f, b, e in sorted(fixes, key=lambda x: -x[2])[:15]:
            log(f"   {n}({t})  {r:.2f}배 → EPS·BPS ×{f:g}   BPS={b} EPS={e}")
    if clears:
        log("\n③ 숨긴 종목 (상위 15) — 리포트를 다시 만들면 채워진다")
        for n, t, r in sorted(clears, key=lambda x: -abs(x[2] - 1))[:15]:
            log(f"   {n}({t})  {r:.3f}배")

    if not APPLY:
        log("\n실제로 고치려면:  python3 scripts/patch_share_counts.py --apply")


if __name__ == "__main__":
    main()
