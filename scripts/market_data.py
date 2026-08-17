#!/usr/bin/env python3
"""간밤 해외 시장과 국내 지수를 모은다 — 브리핑 1·2·3 섹션의 숫자.

왜 별도 파일인가. brief_data.py 는 우리 저장소 안의 데이터(stocks.js,
리포트)를 읽는다. 이 파일은 바깥에서 받아 온다. 실패의 성격이 달라서
섞으면 원인을 못 가린다 — 바깥은 네트워크가 죽거나 형식이 바뀌지만
안쪽은 그럴 일이 없다.

무엇을 받나
  · 미국    S&P 500 · 나스닥 · 다우 · 필라델피아 반도체(SOX)
  · 금리    미 10년물
  · 원자재  WTI
  · 통화    원/달러 · 달러인덱스
  · 국내    코스피 · 코스닥

왜 yfinance 인가. Stooq 는 자바스크립트 봇 차단 페이지를 돌려주고,
pykrx 는 KRX 응답 형식이 바뀌어 지수·수급이 전부 죽었다. 판정을
돌려 보니 yfinance 만 전부 통과했다. 코스피(^KS11)까지 나오므로
국내 지수도 여기서 받는다. 키가 필요 없다.

    python3 scripts/market_data.py           # 사람이 읽는 표
    python3 scripts/market_data.py --json    # 브리핑 생성이 먹는 형태
"""
import argparse
import datetime
import json
import sys

# 이름 → (야후 심볼, 소수점, 표시 단위). 순서가 출력 순서다.
SERIES = [
    ("sp500",    "S&P 500",       "^GSPC",     2, ""),
    ("nasdaq",   "나스닥",         "^IXIC",     2, ""),
    ("dow",      "다우",           "^DJI",      2, ""),
    ("sox",      "필라델피아 반도체", "^SOX",      2, ""),
    ("ust10y",   "미 10년물",      "^TNX",      3, "%"),
    ("wti",      "WTI",           "CL=F",      2, "달러"),
    ("dxy",      "달러인덱스",      "DX-Y.NYB",  2, ""),
    ("usdkrw",   "원/달러",        "KRW=X",     2, "원"),
    ("kospi",    "코스피",         "^KS11",     2, ""),
    ("kosdaq",   "코스닥",         "^KQ11",     2, ""),
]

KST = datetime.timezone(datetime.timedelta(hours=9))


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def fetch(period="10d"):
    """심볼별로 최근 종가와 전일 대비 등락률. 실패한 심볼은 빠지고 나머지는 남는다.

    하나가 죽었다고 전부 버리면 브리핑에서 미국 시장 문단이 통째로 사라진다.
    개별 실패는 그 값만 빼고 넘어간다.
    """
    try:
        import yfinance as yf
    except ImportError:
        log("❌ yfinance 없음 — pip install yfinance")
        return {}

    out = {}
    for key, label, sym, nd, unit in SERIES:
        try:
            h = yf.Ticker(sym).history(period=period)
            if h is None or h.empty or "Close" not in h:
                log(f"· {label}({sym}) 빈 응답")
                continue
            closes = h["Close"].dropna()
            if closes.empty:
                log(f"· {label}({sym}) 종가 없음")
                continue
            last = float(closes.iloc[-1])
            prev = float(closes.iloc[-2]) if len(closes) > 1 else None
            out[key] = {
                "label": label,
                "symbol": sym,
                "date": closes.index[-1].date().isoformat(),
                "close": round(last, nd),
                # 등락률은 우리가 계산한다. 제공되는 값을 믿으면 기준일이
                # 심볼마다 달라 하루씩 밀린 값이 섞인다.
                "change": round((last / prev - 1) * 100, 2) if prev else None,
                "prev": round(prev, nd) if prev else None,
                "unit": unit,
            }
        except Exception as e:
            log(f"· {label}({sym}) 실패: {type(e).__name__} {e}")
    return out


def open_today(d=None):
    """오늘 국내 증시가 열리나. 못 판정하면 None — 브리핑을 내면 안 된다.

    8월 15일 광복절이 토요일이라 17일 월요일이 대체공휴일이었는데 그걸
    확인하지 않고 '오늘 장을 준비하는 글'을 썼다. 주말만 피하면 되는 게
    아니다. 대체공휴일은 달력 계산으로 안 나온다.

    지난 시세가 있는지로는 판정할 수 없다 — 브리핑은 개장 전 07:30 에
    나가므로, 개장일에도 그날 시세는 아직 없다.
    """
    d = d or datetime.datetime.now(KST).date()
    try:
        import holidays as H
    except ImportError:
        log("❌ holidays 없음 — 개장 여부를 판정할 수 없다")
        return None, None
    kr = H.country_holidays("KR", years=[d.year - 1, d.year, d.year + 1])
    # 근로자의날과 연말 폐장일은 법정공휴일이 아니지만 증시는 쉰다.
    extra = {datetime.date(y, 5, 1) for y in (d.year - 1, d.year, d.year + 1)}
    extra |= {datetime.date(y, 12, 31) for y in (d.year - 1, d.year, d.year + 1)}

    def is_open(x):
        return x.weekday() < 5 and x not in kr and x not in extra

    prev = d - datetime.timedelta(days=1)
    while not is_open(prev):
        prev -= datetime.timedelta(days=1)
    nxt = d if is_open(d) else d + datetime.timedelta(days=1)
    while not is_open(nxt):
        nxt += datetime.timedelta(days=1)
    return is_open(d), {"prev": prev.isoformat(), "next": nxt.isoformat()}


def collect():
    is_open, around = open_today()
    return {
        "collectedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "marketOpenToday": is_open,
        "session": around,
        "series": fetch(),
    }


def summarize(d):
    L = []
    o = d["marketOpenToday"]
    if o is None:
        L.append("■ 개장 여부 판정 실패 — 이 상태로 브리핑을 내면 안 된다")
    else:
        s = d["session"] or {}
        L.append(f"■ 오늘 국내 증시 {'개장' if o else '휴장'}"
                 f" · 직전 {s.get('prev')} · 다음 {s.get('next')}")
    L.append(f"■ 수집 {d['collectedAt']}")
    ser = d["series"]
    if not ser:
        L.append("  (시세를 하나도 받지 못했다)")
        return "\n".join(L)
    w = max(len(v["label"]) for v in ser.values())
    for key, _, _, _, _ in SERIES:
        v = ser.get(key)
        if not v:
            continue
        ch = f"{v['change']:+.2f}%" if v["change"] is not None else "   —   "
        L.append(f"  {v['label']:<{w}}  {v['close']:>12,.2f}{v['unit']:<4} {ch:>9}  ({v['date']})")
    missing = [lbl for k, lbl, *_ in SERIES if k not in ser]
    if missing:
        L.append("  못 받음: " + ", ".join(missing))
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = collect()
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    # 시세를 하나도 못 받았으면 실패로 끝낸다 — 조용히 빈 브리핑이 나가면 안 된다.
    return 0 if d["series"] else 1


if __name__ == "__main__":
    sys.exit(main())
