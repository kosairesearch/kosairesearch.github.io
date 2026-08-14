#!/usr/bin/env python3
"""아침 브리핑이 쓸 '사실'만 모은다 — 여기엔 AI가 없다.

브리핑을 한 스크립트에서 다 처리하면 문장이 이상할 때 원인이 둘로 갈린다.
숫자를 잘못 모은 건지, 모델이 잘못 쓴 건지. 그래서 사실 수집을 떼어냈다.
이 파일은 혼자 돌려서 눈으로 검증할 수 있어야 한다.

  python3 scripts/brief_data.py           # 사람이 읽는 요약
  python3 scripts/brief_data.py --json    # generate_brief.py 가 먹는 형태

무엇을 모으나
  · 지수·수급   pykrx (없으면 생략 — 브리핑은 그래도 나간다)
  · 등락        data/stocks.js 의 change/trading_value
  · 섹터        시총가중 등락률
  · 공시        DART 정기보고서 신규 접수 (check_filings.py 와 같은 방식)
  · 체크포인트  공시 낸 종목의 리포트에 적어 둔 '다음에 볼 것'

마지막 항목이 이 브리핑의 존재 이유다. 연합뉴스도 등락률은 쓴다.
"석 달 전 리포트에서 이걸 보라고 했는데 오늘 그게 나왔다"는 우리만 쓴다.

⚠️ checkpoints 는 유료 구간이다(report_split.PAID_KEYS). 원문을 브리핑에
   그대로 실으면 돈 받고 파는 걸 무료로 뿌리는 셈이 된다. 여기서는 모델에게
   '맥락'으로만 넘기고, 생성 쪽에서 한 구절 요약 + 리포트 링크로만 쓰게 한다.
"""
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
REPORTS_INDEX = ROOT / "data" / "reports-index.js"
REPORTS_V2 = ROOT / "data" / "reports_v2"
REPORTS_V1 = ROOT / "data" / "reports"

# 등락 상위를 뽑을 때의 시총 하한(조원). 이게 없으면 매일 잡주 상한가만 올라온다.
MIN_MCAP = float(os.getenv("BRIEF_MIN_MCAP", "0.3"))     # 3,000억원
TOP_MOVERS = int(os.getenv("BRIEF_TOP_MOVERS", "6"))     # 상승/하락 각각
TOP_ACTIVES = int(os.getenv("BRIEF_TOP_ACTIVES", "6"))
TOP_SECTORS = int(os.getenv("BRIEF_TOP_SECTORS", "5"))
# '시장 대비 선전/부진'을 판단할 대형주 모집단. 여기 안에서 상대 등락을 본다.
BIG_CAP_N = int(os.getenv("BRIEF_BIG_CAP_N", "60"))
# 섹터 집계에서 종목 수가 너무 적은 섹터는 뺀다 — 한 종목이 섹터를 대표할 수 없다.
MIN_SECTOR_N = int(os.getenv("BRIEF_MIN_SECTOR_N", "3"))

KST = datetime.timezone(datetime.timedelta(hours=9))
FILING_KINDS = ("분기보고서", "반기보고서", "사업보고서")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _blob(path):
    """data/*.js 는 'window.X = {...}' 형태다. 중괄호만 떼어 읽는다."""
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


# ────────────────────────────── 커버리지 ──────────────────────────────

def coverage():
    """리포트가 있는 종목 집합. 브리핑은 우리가 다루는 종목만 이야기한다.

    커버리지 밖 종목까지 쓰기 시작하면 그냥 시황 뉴스가 되고, 그 싸움은
    연합뉴스·이데일리를 이길 수 없다.
    """
    out = set()
    if REPORTS_INDEX.exists():
        try:
            out |= set((_blob(REPORTS_INDEX).get("reports") or {}).keys())
        except Exception as e:
            log(f"⚠️ reports-index.js 파싱 실패: {e}")
    for d in (REPORTS_V2, REPORTS_V1):          # 인덱스가 밀렸을 때의 보정
        if d.exists():
            out |= {f.stem for f in d.glob("*.json") if f.stem != "index"}
    return out


def load_report(ticker):
    """v2 우선, 없으면 v1. 없으면 None."""
    for d in (REPORTS_V2, REPORTS_V1):
        f = d / f"{ticker}.json"
        if f.exists():
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(r, dict):
                    return r
            except Exception:
                pass
    return None


def ko(v):
    """이중언어 필드에서 한국어를 꺼낸다."""
    if isinstance(v, dict):
        return (v.get("ko") or v.get("en") or "").strip()
    return v.strip() if isinstance(v, str) else ""


# ────────────────────────────── 시세 ──────────────────────────────

def load_stocks():
    o = _blob(STOCKS_JS)
    return o.get("stocks") or [], str(o.get("dataDate") or ""), str(o.get("lastUpdated") or "")


def breadth(stocks):
    """장 전체의 폭 — 오른 종목이 몇 개고 시장이 통째로 얼마나 움직였나.

    이게 없으면 모델이 개별 등락을 정반대로 읽는다. 시장이 +3% 오른 날의
    '+0.2%'는 상승이 아니라 부진이다. 절대 등락률만 넘기면 그걸 구분 못 한다.
    """
    ch = [(s.get("change"), s.get("mcap") or 0) for s in stocks
          if isinstance(s.get("change"), (int, float))]
    if not ch:
        return {"weighted": 0.0, "median": 0.0, "advancers": 0, "decliners": 0,
                "unchanged": 0, "total": 0}
    w = sum(m for _, m in ch) or 1.0
    vals = sorted(c for c, _ in ch)
    mid = len(vals) // 2
    return {
        "weighted": round(sum(c * m for c, m in ch) / w, 2),   # 시총가중 = 지수에 가장 가까움
        "median": round(vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2, 2),
        "advancers": sum(1 for c, _ in ch if c > 0),
        "decliners": sum(1 for c, _ in ch if c < 0),
        "unchanged": sum(1 for c, _ in ch if c == 0),
        "total": len(ch),
    }


def _row(s, base=0.0):
    ch = s.get("change")
    return {
        "ticker": s["ticker"],
        "name": s.get("name") or s["ticker"],
        "sector": s.get("sector") or "",
        "market": s.get("market") or "",
        "price": s.get("price"),
        "change": ch,
        # 시장(시총가중) 대비 초과 등락. 브리핑에서 '선전/부진'의 근거는 이 값이다.
        "rel": round(ch - base, 2) if isinstance(ch, (int, float)) else None,
        "mcap": round(s.get("mcap") or 0, 3),                    # 조원
        "tradingValue": round((s.get("trading_value") or 0) / 1e8),  # 억원
    }


def movers(stocks, cov, base=0.0):
    """커버리지 종목의 등락 상위. 시총 하한으로 노이즈를 걷는다.

    절대 등락(up/down)만으로는 매일 소형주 급등락만 올라온다. 그래서 시총
    상위 대형주 중 '시장 대비' 두드러진 종목(leaders/laggards)을 따로 뽑는다.
    보통 그날의 진짜 이야기는 이쪽에 있다.
    """
    pool = [s for s in stocks
            if s["ticker"] in cov
            and isinstance(s.get("change"), (int, float))
            and (s.get("mcap") or 0) >= MIN_MCAP]
    up = sorted([s for s in pool if s["change"] > 0], key=lambda s: -s["change"])
    dn = sorted([s for s in pool if s["change"] < 0], key=lambda s: s["change"])
    act = sorted(pool, key=lambda s: -(s.get("trading_value") or 0))

    big = sorted(pool, key=lambda s: -(s.get("mcap") or 0))[:BIG_CAP_N]
    by_rel = sorted(big, key=lambda s: -(s["change"] - base))
    return {
        "up": [_row(s, base) for s in up[:TOP_MOVERS]],
        "down": [_row(s, base) for s in dn[:TOP_MOVERS]],
        "actives": [_row(s, base) for s in act[:TOP_ACTIVES]],
        "leaders": [_row(s, base) for s in by_rel[:TOP_MOVERS]],
        "laggards": [_row(s, base) for s in list(reversed(by_rel))[:TOP_MOVERS]],
        "poolSize": len(pool),
        "bigCapN": len(big),
    }


def sector_moves(stocks, cov, base=0.0):
    """섹터별 시총가중 등락률.

    단순평균을 쓰면 시총 500억짜리와 삼성전자가 같은 무게를 갖는다.
    '반도체가 올랐다'는 말은 삼성전자·SK하이닉스가 올랐다는 뜻이어야 한다.
    """
    agg = {}
    for s in stocks:
        if s["ticker"] not in cov:
            continue
        sec, ch, mc = s.get("sector"), s.get("change"), s.get("mcap") or 0
        if not sec or not isinstance(ch, (int, float)) or mc <= 0:
            continue
        a = agg.setdefault(sec, {"w": 0.0, "wc": 0.0, "n": 0, "mcap": 0.0})
        a["w"] += mc
        a["wc"] += mc * ch
        a["n"] += 1
        a["mcap"] += mc
    rows = [{"sector": k,
             "change": round(v["wc"] / v["w"], 2),
             "rel": round(v["wc"] / v["w"] - base, 2),
             "count": v["n"],
             "mcap": round(v["mcap"], 1)}
            for k, v in agg.items() if v["n"] >= MIN_SECTOR_N and v["w"] > 0]
    rows.sort(key=lambda r: -r["change"])
    return {"up": rows[:TOP_SECTORS], "down": list(reversed(rows[-TOP_SECTORS:]))}


# ────────────────────────────── 지수·수급 (선택) ──────────────────────────────

def index_and_flows(trade_date):
    """pykrx 로 지수·투자자별 수급을 받는다. 실패하면 None — 브리핑은 계속된다.

    지수를 못 받았다고 브리핑을 통째로 거르면 안 된다. 우리 브리핑의 값은
    커버리지 종목 이야기에 있지 지수 숫자에 있지 않다.
    """
    try:
        from pykrx import stock
    except ImportError:
        log("· pykrx 없음 — 지수·수급 생략")
        return None, None

    idx, flows = {}, {}
    for name, code in (("kospi", "1001"), ("kosdaq", "2001")):
        try:
            df = stock.get_index_ohlcv(trade_date, trade_date, code)
            if df is None or df.empty:
                continue
            r = df.iloc[-1]
            close, op = float(r["종가"]), float(r["시가"])
            idx[name] = {
                "close": round(close, 2),
                "change": round(float(r.get("등락률", 0.0)), 2),
                "open": round(op, 2),
                "volume": int(r.get("거래량", 0) or 0),
            }
        except Exception as e:
            log(f"· 지수({name}) 조회 실패: {e}")

    for name, mkt in (("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")):
        try:
            df = stock.get_market_trading_value_by_investor(trade_date, trade_date, mkt)
            if df is None or df.empty:
                continue
            # 억원 단위로 줄여서 넘긴다 — 모델에게 원 단위 13자리를 주면 자릿수를 틀린다.
            pick = {}
            for label, key in (("외국인", "foreign"), ("기관합계", "institution"), ("개인", "retail")):
                if label in df.index:
                    pick[key] = round(float(df.loc[label, "순매수거래대금"]) / 1e8)
            if pick:
                flows[name] = pick
        except Exception as e:
            log(f"· 수급({name}) 조회 실패: {e}")

    return (idx or None), (flows or None)


# ────────────────────────────── 공시 ──────────────────────────────

def filings(trade_date, cov, names):
    """해당 거래일에 접수된 정기보고서 중 커버리지 종목.

    실적은 대부분 장 마감 뒤에 나온다. 아침 브리핑이 마감 브리핑보다 나은
    이유가 여기 있다 — 마감 시점엔 아직 이게 없다.
    """
    key = os.getenv("DART_API_KEY")
    if not key:
        log("· DART_API_KEY 없음 — 공시 생략")
        return []
    try:
        import OpenDartReader
        dart = OpenDartReader(key)
        df = dart.list(start=trade_date, end=trade_date, kind="A", final=False)
    except Exception as e:
        log(f"· DART 조회 실패: {e}")
        return []
    if df is None or getattr(df, "empty", True):
        return []

    out, seen = [], set()
    for _, r in df.iterrows():
        sc = str(r.get("stock_code", "")).strip()
        nm = str(r.get("report_nm", ""))
        if sc not in cov or sc in seen or not any(k in nm for k in FILING_KINDS):
            continue
        seen.add(sc)
        out.append({
            "ticker": sc,
            "name": names.get(sc, sc),
            "report": nm.strip(),
            "rceptNo": str(r.get("rcept_no", "")).strip(),
        })
    return out


def with_checkpoints(rows):
    """공시 낸 종목의 리포트에서 '다음에 볼 것'을 끌어온다.

    ⚠️ 유료 구간이다. 원문을 그대로 내보내지 않는다 — 생성 쪽에서 한 구절로
       요약하고 리포트로 보낸다. 여기서는 모델이 판단할 재료로만 넘긴다.
    """
    for row in rows:
        rep = load_report(row["ticker"])
        if not rep:
            continue
        row["reportDate"] = rep.get("reportDate") or ""
        row["reportTitle"] = ko(rep.get("title"))
        cps = []
        for c in (rep.get("checkpoints") or [])[:3]:
            when, what = ko(c.get("when")), ko(c.get("what"))
            if what:
                cps.append({"when": when, "what": what})
        if cps:
            row["checkpoints"] = cps
        # 강세/약세도 한 줄씩 — 공시 결과가 어느 쪽 논리를 지지하는지 판단시킨다.
        for k in ("bull", "bear"):
            items = [ko(x if isinstance(x, str) else (x or {}).get("title") or x)
                     for x in (rep.get(k) or [])[:2]]
            items = [x for x in items if x]
            if items:
                row[k] = items
    return rows


# ────────────────────────────── 조립 ──────────────────────────────

def collect(trade_date=None):
    stocks, data_date, last_updated = load_stocks()
    if not stocks:
        raise SystemExit("❌ data/stocks.js 를 읽지 못했습니다.")
    trade_date = trade_date or data_date
    if not re.fullmatch(r"\d{8}", trade_date or ""):
        raise SystemExit(f"❌ 거래일이 이상합니다: {trade_date!r}")

    cov = coverage()
    names = {s["ticker"]: s.get("name") or s["ticker"] for s in stocks}
    idx, flows = index_and_flows(trade_date)
    fl = with_checkpoints(filings(trade_date, cov, names))

    br = breadth(stocks)
    # 지수를 받았으면 그걸 기준으로, 못 받았으면 시총가중 등락률로 대신한다.
    base = (idx or {}).get("kospi", {}).get("change", br["weighted"])

    d = datetime.datetime.strptime(trade_date, "%Y%m%d").date()
    return {
        "tradeDate": trade_date,
        "tradeDateKo": f"{d.month}월 {d.day}일",
        "publishDate": datetime.datetime.now(KST).date().isoformat(),
        "dataUpdated": last_updated,
        "coverage": len(cov),
        "index": idx,
        "flows": flows,
        "breadth": br,
        "base": base,
        "movers": movers(stocks, cov, base),
        "sectors": sector_moves(stocks, cov, base),
        "filings": fl,
    }


def summarize(d):
    """사람이 눈으로 검증하는 출력. 여기가 이상하면 브리핑도 이상하다."""
    L = [f"■ 거래일 {d['tradeDate']} · 발행 {d['publishDate']} · 커버리지 {d['coverage']:,}종목",
         f"  (stocks.js 갱신 {d['dataUpdated']})"]
    if d["index"]:
        for k, v in d["index"].items():
            L.append(f"  지수 {k.upper():6} {v['close']:>10,.2f}  {v['change']:+.2f}%")
    else:
        L.append("  지수 — 없음(pykrx 미설치 또는 조회 실패)")
    if d["flows"]:
        for k, v in d["flows"].items():
            L.append(f"  수급 {k.upper():6} " + " · ".join(f"{a} {b:+,}억" for a, b in v.items()))

    b = d["breadth"]
    L.append(f"  장폭  시총가중 {b['weighted']:+.2f}% · 중앙값 {b['median']:+.2f}% · "
             f"상승 {b['advancers']:,} / 하락 {b['decliners']:,} / 보합 {b['unchanged']:,}")
    L.append(f"  기준  {d['base']:+.2f}%  ← 아래 rel 은 이 값 대비")

    m = d["movers"]

    def rows(title, key, fmt):
        L.append(title)
        for s in m[key]:
            L.append("   " + fmt(s))

    rows(f"\n▲ 절대 상승 (대상 {m['poolSize']:,}종목 중)", "up",
         lambda s: f"{s['change']:+6.2f}% (rel {s['rel']:+6.2f}) {s['name']:<14} {s['sector']:<10} {s['mcap']}조")
    rows("▼ 절대 하락", "down",
         lambda s: f"{s['change']:+6.2f}% (rel {s['rel']:+6.2f}) {s['name']:<14} {s['sector']:<10} {s['mcap']}조")
    rows(f"\n★ 대형주 선전 (시총 상위 {m['bigCapN']} 중, 시장 대비)", "leaders",
         lambda s: f"rel {s['rel']:+6.2f}  ({s['change']:+.2f}%) {s['name']:<14} {s['mcap']}조")
    rows("☆ 대형주 부진", "laggards",
         lambda s: f"rel {s['rel']:+6.2f}  ({s['change']:+.2f}%) {s['name']:<14} {s['mcap']}조")
    rows("\n● 거래대금", "actives",
         lambda s: f"{s['tradingValue']:>7,}억  {s['name']:<14} {s['change']:+.2f}% (rel {s['rel']:+.2f})")

    L.append("\n◆ 섹터 (시총가중)")
    for s in d["sectors"]["up"]:
        L.append(f"   {s['change']:+6.2f}% (rel {s['rel']:+6.2f}) {s['sector']:<12} {s['count']}종목")
    L.append("   ---")
    for s in d["sectors"]["down"]:
        L.append(f"   {s['change']:+6.2f}% (rel {s['rel']:+6.2f}) {s['sector']:<12} {s['count']}종목")

    L.append(f"\n□ 정기보고서 {len(d['filings'])}건")
    for f in d["filings"][:12]:
        cp = f" · 체크포인트 {len(f['checkpoints'])}개" if f.get("checkpoints") else ""
        L.append(f"   {f['name']:<14} {f['report']}{cp}")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="JSON 출력(생성 스크립트용)")
    ap.add_argument("--date", help="거래일 YYYYMMDD (기본: stocks.js 의 dataDate)")
    a = ap.parse_args()
    d = collect(a.date)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))


if __name__ == "__main__":
    main()
