"""디자인 시안(preview/concepts/)이 쓰는 실제 데이터 — 읽기만 한다.

스테이징·실사이트 생성기(comp_common · stock_page …)는 건드리지 않는다. 시안은 따로 논다.
"""
import json
import os
from datetime import date

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MINUS = "−"   # 진짜 마이너스 — 하이픈보다 넓어 + 와 폭이 같다
WEEK = "월화수목금토일"


def _js(path):
    s = open(os.path.join(ROOT, path), encoding="utf-8").read()
    return json.loads(s[s.index("{"):s.rindex("}") + 1])


STOCKS = _js("data/stocks.js")
BY = {s["ticker"]: s for s in STOCKS["stocks"]}
INDEX = _js("data/reports-index.js")["reports"]
SECTORS_AI = _js("data/sectors.js")["sectors"]
VAL = _js("data/valuation.js")["stocks"]
PRICE_DATE = STOCKS["dataDate"]            # '20260923'


def report(tk):
    p = os.path.join(ROOT, "data/reports_v2", f"{tk}.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def briefs():
    d = os.path.join(ROOT, "data/briefs")
    return sorted(f for f in os.listdir(d) if f.endswith(".json"))


def brief(name=None):
    names = briefs()
    name = name or names[-1]
    b = json.load(open(os.path.join(ROOT, "data/briefs", name), encoding="utf-8"))
    b["_no"] = names.index(name) + 1          # 제 n호 — 발행한 브리핑 수
    b["_facts"] = parse_facts(b.get("factsDigest") or "")
    return b


def parse_facts(fd):
    """factsDigest 글에서 지수·금리·환율 같은 값만 꺼낸다."""
    import re
    out = {}
    pats = {
        "코스피": r"코스피: ([\d,\.]+) ([+\-][\d\.]+)%",
        "코스닥": r"코스닥: ([\d,\.]+) ([+\-][\d\.]+)%",
        "S&P 500": r"S&P 500: ([\d,\.]+) ([+\-][\d\.]+)%",
        "나스닥": r"나스닥: ([\d,\.]+) ([+\-][\d\.]+)%",
        "다우": r"다우: ([\d,\.]+) ([+\-][\d\.]+)%",
        "필라델피아 반도체": r"필라델피아 반도체: ([\d,\.]+) ([+\-][\d\.]+)%",
        "WTI": r"WTI: ([\d,\.]+)달러 ([+\-][\d\.]+)%",
        "달러인덱스": r"달러인덱스: ([\d,\.]+) ([+\-][\d\.]+)%",
        "VIX": r"VIX ([\d,\.]+) ([+\-][\d\.]+)%",
        "금": r"금 ([\d,\.]+)달러 ([+\-][\d\.]+)%",
    }
    for k, p in pats.items():
        m = re.search(p, fd)
        if m:
            out[k] = (m.group(1), float(m.group(2)))
    m = re.search(r"미 10년물: ([\d\.]+)% \(전일 ([\d\.]+)%", fd)
    if m:
        out["미 10년물"] = (m.group(1) + "%", round(float(m.group(1)) - float(m.group(2)), 2))
    m = re.search(r"원/달러[^:]*: ([\d,\.]+)원 ([+\-][\d\.]+)%", fd)
    if m:
        out["원/달러"] = (m.group(1), float(m.group(2)))
    m = re.search(r"개인 ([+\-][\d,]+)억원 · 외국인 ([+\-][\d,]+)억원 · 기관 ([+\-][\d,]+)억원", fd)
    if m:
        out["flows"] = [("개인", int(m.group(1).replace(",", ""))), ("외국인", int(m.group(2).replace(",", ""))),
                        ("기관", int(m.group(3).replace(",", "")))]
    m = re.search(r"상승 ([\d,]+) / 하락 ([\d,]+) / 보합 ([\d,]+)", fd)
    if m:
        out["breadth"] = tuple(int(g.replace(",", "")) for g in m.groups())
    m = re.search(r"\[직전 국내 장 · (\d{8})", fd)
    if m:
        out["kr_date"] = m.group(1)
    m = re.search(r"기준일 (\d{4}-\d{2}-\d{2})", fd)
    if m:
        out["us_date"] = m.group(1)
    return out


# ── 숫자 ─────────────────────────────────────────────

def grp(n):
    return f"{n:,}"


def sign(x, digits=2, pct=True):
    """+3.25% · −1.20% · 0.00% (진짜 마이너스)"""
    if x is None:
        return "—"
    s = f"{abs(x):.{digits}f}" + ("%" if pct else "")
    if round(x, digits) > 0:
        return "+" + s
    if round(x, digits) < 0:
        return MINUS + s
    return s


def arrow(x):
    return "▲" if x and x > 0 else ("▼" if x and x < 0 else "")


def cls(x):
    return "up" if x and x > 0 else ("down" if x and x < 0 else "flat")


def won(n):
    return f"{int(round(n)):,}원"


def money(v, unit=True):
    """원 단위 값 → 171.5조 · 4,676억 · 3,000만 (실사이트와 같은 결)"""
    if v is None:
        return "—"
    sg = MINUS if v < 0 else ""
    a = abs(v)
    if a >= 1e12:
        return sg + f"{a / 1e12:,.1f}".rstrip("0").rstrip(".") + "조"
    if a >= 1e8:
        return sg + f"{round(a / 1e8):,}억"
    if a >= 1e4:
        return sg + f"{round(a / 1e4):,}만"
    return sg + f"{round(a):,}"


def jo(x):
    """조 단위 값(시가총액) → 1,669조 · 4,639억"""
    if not x:
        return "—"
    if x >= 100:
        return f"{x:,.0f}조"
    if x >= 1:
        return f"{x:,.1f}".rstrip("0").rstrip(".") + "조"
    return f"{round(x * 10000):,}억"


def kdate(ymd, weekday=True):
    """'20260923' 또는 '2026-09-23' → '9월 23일(수)'"""
    s = ymd.replace("-", "")
    d = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return f"{d.month}월 {d.day}일" + (f"({WEEK[d.weekday()]})" if weekday else "")


def kdate_full(ymd):
    s = ymd.replace("-", "")
    d = date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return f"{d.year}년 {d.month}월 {d.day}일 {WEEK[d.weekday()]}요일"


# ── 묶음 ─────────────────────────────────────────────

def latest(n=12, v2_only=True):
    out = []
    for tk, r in sorted(INDEX.items(), key=lambda kv: kv[1].get("reportTs", ""), reverse=True):
        rep = report(tk) if v2_only else None
        if v2_only and not rep:
            continue
        s = BY.get(tk)
        if not s:
            continue
        qq = ((rep or {}).get("quant") or {}).get("quarterly") or []
        out.append({"tk": tk, "name": s["name"], "sector": s.get("sector"), "market": s.get("market"),
                    "price": s.get("price"), "change": s.get("change"), "mcap": s.get("mcap"),
                    "title": r["title"]["ko"], "date": r.get("reportDate"),
                    "lead": (rep or {}).get("lead", {}).get("ko", ""),
                    "ops": [x.get("op") for x in qq], "qs": [x.get("q") for x in qq]})
        if len(out) >= n:
            break
    return out


def sectors():
    agg = {}
    for s in STOCKS["stocks"]:
        sec = s.get("sector") or "기타"
        a = agg.setdefault(sec, {"name": sec, "n": 0, "mcap": 0.0, "w": 0.0, "top": []})
        a["n"] += 1
        m = s.get("mcap") or 0
        a["mcap"] += m
        a["w"] += m * (s.get("change") or 0)
        a["top"].append((m, s["name"]))
    tot = sum(a["mcap"] for a in agg.values())
    out = []
    for a in agg.values():
        a["chg"] = a["w"] / a["mcap"] if a["mcap"] else 0
        a["share"] = a["mcap"] / tot * 100
        a["top"] = [nm for _, nm in sorted(a["top"], reverse=True)[:3]]
        a["lead"] = (SECTORS_AI.get(a["name"], {}).get("lead") or {}).get("ko", "")
        out.append(a)
    return sorted(out, key=lambda a: -a["mcap"]), tot


def movers(k=5, min_mcap=1.0):
    big = [s for s in STOCKS["stocks"] if (s.get("mcap") or 0) >= min_mcap and s.get("change") is not None]
    up = sorted(big, key=lambda s: -s["change"])[:k]
    dn = sorted(big, key=lambda s: s["change"])[:k]
    return up, dn


def valuation(tk):
    """현재가로 다시 잰 PER·PBR·배당수익률 (실사이트 방식)"""
    s = BY[tk]
    v = VAL.get(tk, {})
    px = s["price"]
    eps, bps, dps = v.get("eps"), v.get("bps"), v.get("dps")
    return {
        "per": px / eps if eps and eps > 0 else None,
        "pbr": px / bps if bps and bps > 0 else None,
        "div": dps / px * 100 if dps else None,
        "eps": eps, "bps": bps, "dps": dps, "roe": v.get("roe"),
    }


def squarify(items, x, y, w, h):
    """면적 비례 사각 배치(Bruls 외 squarified treemap). items: [(값, 데이터)] 큰 순. → [(x, y, w, h, 데이터)]"""
    out = []
    items = [it for it in items if it[0] > 0]
    total = sum(v for v, _ in items)
    if not items or total <= 0:
        return out
    scale = w * h / total
    rest = [(v * scale, d) for v, d in items]

    def worst(row, side):
        s = sum(a for a, _ in row)
        mx = max(a for a, _ in row)
        mn = min(a for a, _ in row)
        return max(side * side * mx / (s * s), (s * s) / (side * side * mn))

    while rest:
        side = min(w, h)
        row = [rest.pop(0)]
        while rest and worst(row + [rest[0]], side) <= worst(row, side):
            row.append(rest.pop(0))
        s = sum(a for a, _ in row)
        if w >= h:                       # 왼쪽에 세로 줄
            cw = s / h
            yy = y
            for a, d in row:
                ch = a / cw
                out.append((x, yy, cw, ch, d))
                yy += ch
            x += cw
            w -= cw
        else:                            # 위쪽에 가로 줄
            chh = s / w
            xx = x
            for a, d in row:
                cww = a / chh
                out.append((xx, y, cww, chh, d))
                xx += cww
            y += chh
            h -= chh
    return out


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))
