#!/usr/bin/env python3
"""사실을 글로 바꾼다 — 모닝 브리핑 본문 생성.

수집기(market_data · flows · calendar_data · news_data · brief_data)는 숫자와
사실만 뱉는다. 이 파일이 그걸 읽어 기사 본문을 만든다. 8월 17일 브리핑은
사람이 로그를 읽고 손으로 썼는데, 그 일을 여기서 한다.

왜 템플릿이 아니라 모델인가. 빈칸 채우기("코스피는 {등락}하여 {지수}로
마감했습니다")로는 AI 티가 나는 글이 나온다. 그리고 브리핑에서 값이 나가는
문장은 사실 나열이 아니라 연결이다 — "S&P는 내렸는데 반도체는 −0.31%뿐이었다,
브로드컴이 지수를 끌었고 엔비디아는 비켜갔다" 같은 판단은 조건문으로 못 쓴다.

왜 동기 호출인가(배치가 아닌가). Batch API 는 50% 싸지만 비동기다 — 대부분
1시간 안에 끝나고 최대 24시간이다. 브리핑은 07:30 에 나가야 하므로 그 꼬리에
걸리면 발행을 못 한다. 아껴지는 돈은 월 5,000원 남짓이고, 조용히 안 나가는
게 최악이다. 그래도 쓸 수 있게 BRIEF_USE_BATCH=1 을 두었다 — 배치로 내고
BRIEF_BATCH_CUTOFF 초 안에 안 끝나면 취소하고 동기로 다시 부른다.
(리포트 생성은 반대다. 2,692종목을 한꺼번에 내고 마감이 없으니 배치가 맞다 —
 generate_reports_batch.py 가 그쪽이다.)

프롬프트 캐싱은 여기서 값을 못 한다. 캐시 TTL 이 5분 또는 1시간인데 브리핑은
하루 한 번이라 언제나 만료돼 있다. 캐시 쓰기는 1.25배이므로 붙이면 오히려 손해다.

    python3 scripts/generate_brief.py --facts-only     # 사실만 보고 끝(무료)
    python3 scripts/generate_brief.py --dry-run        # 프롬프트·토큰·예상비용(무료)
    python3 scripts/generate_brief.py                  # 실제 생성 (과금)

환경변수
    ANTHROPIC_API_KEY   필수(생성 시)
    BRIEF_MODEL         기본 claude-opus-5
    BRIEF_USE_BATCH     1 이면 Batch API 시도 후 실패 시 동기로 폴백
    BRIEF_BATCH_CUTOFF  배치를 기다릴 최대 초(기본 2400 = 40분)
    DART_API_KEY        공시 섹션용(없으면 그 부분만 빠진다)
"""
import argparse
import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "briefs"
sys.path.insert(0, str(Path(__file__).resolve().parent))

KST = datetime.timezone(datetime.timedelta(hours=9))

MODEL = os.getenv("BRIEF_MODEL", "claude-opus-5")
MAX_TOKENS = int(os.getenv("BRIEF_MAX_TOKENS", "16000"))
USE_BATCH = os.getenv("BRIEF_USE_BATCH", "") == "1"
BATCH_CUTOFF = int(os.getenv("BRIEF_BATCH_CUTOFF", "2400"))
# 뉴스를 종목별로 받을 개수. 구글 뉴스는 1초에 여덟 번 때리면 503 을 준다.
NEWS_TICKERS = int(os.getenv("BRIEF_NEWS_TICKERS", "4"))

# 백만 토큰당 (입력, 출력) 달러. 예상 비용 표시용이며 청구와 무관하다.
# Sonnet 5 는 2026-08-31 까지 도입가 $2/$10 이 적용된다.
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
USD_KRW = float(os.getenv("BRIEF_USD_KRW", "1400"))

# 분량. 설계 문서 0절이 2,500~3,000자다. 이 밖이면 경고하고, 아래 하한/상한을
# 벗어나면 거부한다 — 1,200자짜리 브리핑은 브리핑이 아니고, 5,000자는 안 읽힌다.
LEN_MIN, LEN_MAX = 2200, 3600
LEN_WANT = (2500, 3000)
# 설계 문서 1절: "4번(커버리지)은 전체의 25%를 넘지 않는다."
COVERAGE_CAP = 0.25
COVERAGE_HARD = 0.30      # 재시도 후에도 이걸 넘으면 발행하지 않는다

SECTIONS = [
    ("us",       "간밤 뉴욕"),
    ("domestic", "직전 국내 장"),
    ("ahead",    "볼 것"),
    ("coverage", "코사이 커버리지에서"),
]

# 투자권유로 읽히는 표현. 종목 리포트와 같은 규칙이다(6-1항).
# '순매수'는 사실이므로 막지 않는다 — 그래서 매수/매도는 뒤에 추천·의견·권유가
# 붙은 형태만 잡는다. 영문 본문도 같이 검사하므로 영어 표현을 함께 넣는다.
# 한국어만 막아 두면 화면을 영어로 바꿨을 때 그대로 나간다.
BANNED = [(re.compile(p, re.I), n) for p, n in [
    (r"목표\s*주가|목표가|적정\s*주가|price\s+target|target\s+price", "목표주가"),
    (r"매수\s*(추천|의견|권유|시점)|매도\s*(추천|의견|권유|시점)"
     r"|\b(buy|sell)\s+(rating|recommendation|call)\b"
     r"|recommend\w*\s+(buying|selling)", "매수·매도 권유"),
    (r"투자\s*의견|비중\s*(확대|축소)|investment\s+(rating|opinion)"
     r"|\b(overweight|underweight)\b", "투자의견·비중"),
    (r"저평가|고평가|밸류에이션\s*매력|\b(under|over)valued\b"
     r"|attractive\s+valuation|cheap\s+valuation", "저평가·고평가 단정"),
    (r"상승\s*여력|추가\s*상승\s*여지|재평가\s*모멘텀"
     r"|upside\s+(potential|room)|room\s+to\s+run|re-?rating\s+", "주가 방향 단정"),
    (r"오를\s*것(으로|이다|입니다)|내릴\s*것(으로|이다|입니다)"
     r"|상승할\s*것|하락할\s*것|반등할\s*것"
     r"|will\s+(rise|fall|climb|drop|rally|rebound)"
     r"|poised\s+to\s+(rise|gain|rally)", "주가 예측"),
    (r"지금\s*(사|담|들어)|유망주|추천\s*종목|수익률\s*\d"
     r"|\btop\s+picks?\b|must-?(buy|own)|\bstocks?\s+to\s+buy\b", "권유성 표현"),
]]

SYSTEM = (
    "당신은 한국 주식시장(코스피·코스닥)을 다루는 시니어 리서치 애널리스트입니다. "
    "매일 장 시작 전에 발행되는 모닝 브리핑을 씁니다. "
    "주어진 사실 블록에 있는 숫자만 사용하고, 없는 값은 추측하지 않습니다. "
    "당신의 글은 한국어와 영어로 동시에 제공됩니다."
)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ────────────────────────────── 사실 모으기 ──────────────────────────────

def _news_tickers(dom):
    """뉴스를 종목별로 받을 대상 고르기.

    전 종목을 돌면 2,692번 요청이 되고 구글 뉴스가 막는다. 그날 이야기가
    있을 만한 곳만 고른다 — 시장 대비 두드러진 대형주, 거래가 몰린 종목,
    그리고 정기보고서를 낸 종목(브리핑이 실제로 다룰 곳).
    """
    m = dom.get("movers") or {}
    picks = []
    for key, n in (("leaders", 2), ("laggards", 1), ("actives", 1)):
        for row in (m.get(key) or [])[:n]:
            picks.append((row["ticker"], row.get("name")))
    for f in (dom.get("filings") or [])[:2]:
        picks.append((f["ticker"], f.get("name")))

    seen, tks, names = set(), [], {}
    for tk, nm in picks:
        if tk in seen:
            continue
        seen.add(tk)
        tks.append(tk)
        if nm:
            names[tk] = nm
        if len(tks) >= NEWS_TICKERS:
            break
    return tks, names


def gather(trade_date=None, days=14, skip_news=False):
    """브리핑이 쓸 사실 전부. (facts, 치명적 실패 이유) 를 돌려준다.

    실패에는 등급이 있다. 뉴스가 없으면 '왜'를 안 쓰고 숫자만 쓰면 되지만,
    개장 여부를 모르면 글의 전제가 틀린다 — 8월 17일에 실제로 그렇게 틀렸다.
    그건 발행을 멈춘다.
    """
    import brief_data

    facts = {"generatedAt": datetime.datetime.now(KST).isoformat(timespec="seconds")}

    # ① 국내 사실. 개장 여부 판정이 여기 들어 있다.
    dom = brief_data.collect(trade_date)
    facts["domestic"] = dom
    cal = dom.get("calendar") or {}
    if cal.get("open") is None:
        return facts, "개장 여부를 판정하지 못했다(holidays 조회 실패)"

    # ② 시세. brief_data 가 이미 코스피·코스닥을 받았고 fetch 는 결과를
    #    기억하므로, 여기서 부르는 건 미국 지수·금리·환율 몫이다.
    try:
        from market_data import fetch as _fetch
        facts["markets"] = _fetch() or None
    except Exception as e:
        log(f"⚠️ 시세 조회 실패 — 섹션 1을 생략한다: {type(e).__name__} {e}")
        facts["markets"] = None

    # ③ 일정
    try:
        import calendar_data
        facts["schedule"] = calendar_data.collect(days)
    except Exception as e:
        log(f"⚠️ 일정 조회 실패 — 섹션 3에서 일정을 뺀다: {type(e).__name__} {e}")
        facts["schedule"] = None

    # ④ 뉴스. 없으면 인과를 쓰지 않는다(지어내는 것보다 낫다).
    if skip_news:
        facts["news"] = None
    else:
        try:
            import news_data
            tks, names = _news_tickers(dom)
            facts["news"] = news_data.collect(tks, names)
        except Exception as e:
            log(f"⚠️ 뉴스 조회 실패 — '왜'를 쓰지 않는다: {type(e).__name__} {e}")
            facts["news"] = None

    return facts, None


# ────────────────────────────── 사실 → 텍스트 ──────────────────────────────

def _n(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%"


def _facts_text(facts):
    """모델에게 넘길 사실 블록.

    JSON 을 그대로 넘기지 않는다. movers 다섯 묶음과 공시 40건을 JSON 으로
    말면 입력이 세 배가 되고, 모델이 표를 읽느라 문장을 못 본다. 대신 사람이
    읽을 수 있는 형태로 압축한다 — 그러면 발행된 브리핑이 이상할 때 이
    블록만 보고 '숫자를 잘못 모았나, 모델이 잘못 썼나'를 가릴 수 있다.
    그래서 이 텍스트를 결과 파일에도 같이 저장한다.

    종목은 반드시 코드를 붙인다. 모델이 링크를 달 때 그 코드를 쓴다.
    """
    from market_data import SERIES

    dom = facts["domestic"]
    cal = dom.get("calendar") or {}
    ser = facts.get("markets") or {}
    L = []

    # 오늘의 전제
    today = cal.get("today", "")
    if cal.get("open") is None:
        # 여기까지 올 일은 없다(gather 가 먼저 멈춘다). 그래도 '모른다'를
        # '휴장'으로 적어 두면 안 된다 — 사실 블록이 거짓말을 하는 셈이다.
        L.append(f"[오늘] {today} · 개장 여부를 판정하지 못했다 — 이 상태로는 브리핑을 쓰지 마라")
    elif cal.get("open"):
        L.append(f"[오늘] {today} · 국내 증시 개장 · 직전 거래일 {cal.get('prev')}")
    else:
        gap = cal.get("gapDays") or 0
        L.append(f"[오늘] {today} · 국내 증시 휴장 · 직전 거래일 {cal.get('prev')}"
                 f" → 다음 개장 {cal.get('next')}")
        if gap >= 2:
            L.append(f"  ※ 직전 거래일과 다음 개장 사이가 {gap}일이다. 그 사이 미국 시장이"
                     f" 여러 번 열리므로, 다음 개장일이 그것을 한꺼번에 반영한다.")

    # 해외
    if ser:
        L.append("\n[간밤 해외 · 종가와 전일 대비]")
        for key in ("sp500", "nasdaq", "dow", "sox", "ust10y", "wti", "dxy"):
            v = ser.get(key)
            if v:
                L.append(f"  {v['label']}: {_n(v['close'])}{v['unit']} {_pct(v.get('change'))}"
                         f"  (기준일 {v.get('date')})")
        miss = [lbl for k, lbl, *_ in SERIES
                if k not in ser and k not in ("kospi", "kosdaq")]
        if miss:
            L.append("  못 받은 값(쓰지 말 것): " + ", ".join(miss))
    else:
        L.append("\n[간밤 해외] 시세를 하나도 받지 못했다 — 섹션 1을 생략하라.")

    # 국내 지수·수급
    L.append(f"\n[직전 국내 장 · {dom['tradeDate']} ({dom['tradeDateKo']})]")
    idx = dom.get("index") or {}
    for key, lbl in (("kospi", "코스피"), ("kosdaq", "코스닥")):
        v = idx.get(key)
        if v:
            warn = "  ⚠️기준일이 거래일과 다르다 — 날짜를 쓰지 말 것" if v.get("dateMismatch") else ""
            L.append(f"  {lbl}: {_n(v['close'])} {_pct(v.get('change'))}{warn}")
    if not idx:
        L.append("  지수를 받지 못했다 — 지수 숫자를 쓰지 말고 아래 장폭으로 서술하라.")

    fl = dom.get("flows") or {}
    for key, lbl in (("kospi", "코스피"), ("kosdaq", "코스닥")):
        v = fl.get(key)
        if v:
            body = " · ".join(f"{a} {b:+,}억원" for a, b in v.items() if not a.startswith("_"))
            L.append(f"  {lbl} 투자자별 순매수: {body}")
    if not fl:
        L.append("  투자자별 순매수를 받지 못했다 — 외국인·기관 얘기를 쓰지 말 것.")

    b = dom["breadth"]
    L.append(f"  장폭: 시총가중 {_pct(b['weighted'])} · 중앙값 {_pct(b['median'])}"
             f" · 상승 {b['advancers']:,} / 하락 {b['decliners']:,} / 보합 {b['unchanged']:,}"
             f" (총 {b['total']:,})")
    L.append(f"  기준 등락률 {_pct(dom['base'])} — 아래 rel 은 이 값 대비 초과 등락이다."
             " 시장이 +2% 오른 날의 +0.2% 는 상승이 아니라 부진이다.")

    m = dom.get("movers") or {}

    def rows(title, key):
        got = m.get(key) or []
        if not got:
            return
        L.append(f"  {title}: " + " · ".join(
            f"{r['name']}({r['ticker']}) {_pct(r['change'])} rel {r['rel']:+.2f}" for r in got))

    rows("대형주 선전(시장 대비)", "leaders")
    rows("대형주 부진(시장 대비)", "laggards")
    rows("절대 상승", "up")
    rows("절대 하락", "down")
    acts = m.get("actives") or []
    if acts:
        L.append("  거래대금 상위: " + " · ".join(
            f"{r['name']}({r['ticker']}) {r['tradingValue']:,}억원 {_pct(r['change'])}"
            for r in acts))

    sec = dom.get("sectors") or {}
    if sec.get("up"):
        L.append("  업종 상위(시총가중): " + " · ".join(
            f"{s['sector']} {_pct(s['change'])}" for s in sec["up"]))
    if sec.get("down"):
        L.append("  업종 하위: " + " · ".join(
            f"{s['sector']} {_pct(s['change'])}" for s in sec["down"]))

    # 환율은 섹션 3에서 쓴다
    fx = ser.get("usdkrw") if ser else None
    if fx:
        L.append(f"\n[환율] 원/달러 {_n(fx['close'])}원 {_pct(fx.get('change'))}"
                 f" (기준일 {fx.get('date')})")

    # 일정
    sch = facts.get("schedule") or {}
    evs = sch.get("events") or []
    if evs:
        L.append(f"\n[일정 · {sch.get('from')} ~ {sch.get('to')}]")
        for e in evs[:14]:
            est = " (공개일 추정)" if e.get("estimated") else ""
            L.append(f"  {e['date']} {e.get('kind', '')} {e.get('title', '')}{est}")
    else:
        L.append("\n[일정] 없음 — 일정 문장을 쓰지 말 것.")

    # 공시 + 확인 지점
    fils = dom.get("filings") or []
    if fils:
        total = fils[0].get("totalFilings") or len(fils)
        more = f" (전체 {total:,}건 중 시총 상위 {len(fils)}건)" if total > len(fils) else ""
        L.append(f"\n[정기보고서 접수 · 커버리지 종목{more}]")
        for f in fils[:12]:
            L.append(f"  {f['name']}({f['ticker']}) {f['report']} · 시총 {f.get('mcap', 0):.1f}조")
            for c in (f.get("checkpoints") or [])[:2]:
                L.append(f"     └ 확인 지점 [{c.get('when', '')}] {c.get('what', '')}")
            for k, lbl in (("bull", "강세"), ("bear", "약세")):
                if f.get(k):
                    L.append(f"     └ {lbl}: " + " / ".join(f[k]))
    else:
        L.append("\n[정기보고서] 해당 거래일에 커버리지 종목 접수 없음.")

    L.append(f"\n[커버리지] 리포트 보유 {dom['coverage']:,}종목")

    # 뉴스 — 제목만. 숫자는 여기서 가져오지 않는다.
    nw = facts.get("news") or {}
    groups = nw.get("groups") or {}
    if any(groups.values()) or nw.get("tickers"):
        L.append("\n[뉴스 제목 — '왜 움직였나'의 단서. 제목 속 숫자는 쓰지 말 것]")
        for label, items in groups.items():
            if not items:
                continue
            L.append(f"  · {label}")
            for r in items[:6]:
                src = f" ({r['source']})" if r.get("source") else ""
                L.append(f"      {r['title']}{src}")
        for tk, v in (nw.get("tickers") or {}).items():
            L.append(f"  · {v['name']}({tk})")
            for r in v["items"][:4]:
                L.append(f"      {r['title']}")
    else:
        L.append("\n[뉴스] 한 건도 받지 못했다 — 숫자만 쓰고 인과는 쓰지 말 것.")

    return "\n".join(L)


# ────────────────────────────── 프롬프트 ──────────────────────────────

RULES = """규칙

1. 분량 2,500~3,000자(한국어 본문 기준, 제목·리드 포함). 스크롤 두세 번.
2. 섹션은 아래 넷을 이 순서로. 데이터가 없는 섹션은 통째로 빼라(빈 섹션을 만들지 마라).
   us       간밤 뉴욕 — 미국 3대 지수와 반도체 지수, 움직인 이유, 국내로 옮겨붙을 성격인지 (약 700자)
   domestic 직전 국내 장 — 지수·수급, 폭(중앙값 vs 시총가중), 업종, 거래 쏠림 (약 650자)
   ahead    볼 것 — 환율·금리, 일정, 다음 개장까지의 관전 지점 (약 700자)
   coverage 코사이 커버리지에서 — 커버 종목에 걸린 확인 지점 중 결과가 나온/나올 것 (약 600자)
3. **coverage 섹션은 전체 분량의 25%를 넘지 않는다.** 이 브리핑은 우리 리포트
   홍보물이 아니라 장 준비용 글이다. 커버리지 얘기는 "실제로 움직였거나 이번 주에
   결과가 나오는 것"만 넣는다.
4. 사실 블록에 있는 숫자만 쓴다. 없는 값은 추측하지 않고 그 문장을 뺀다.
   뉴스 제목에 나오는 숫자를 본문에 옮기지 마라 — 숫자는 시세에서, 이유는 뉴스에서
   가져온다. (실제로 기사의 '반도체지수 1% 하락'을 옮겼다가 실측 -0.31% 와 어긋난 적이 있다.)
5. 단정하지 않는다. 저평가·고평가, 매수·매도, 목표주가, 투자의견, "오를 것", "상승 여력"
   같은 표현은 쓰지 않는다. 인과는 확인된 것만 쓰고, 추정은 "~때문으로 보인다"가 아니라
   "~와 겹친다", "~가 함께 나왔다"처럼 사실 병치로 쓴다.
   시장 전망·의견이 필요하면 출처를 밝힌 인용으로만 쓴다.
6. 확인 지점(checkpoints)은 유료 리포트 내용이다. 원문을 그대로 옮기지 말고 한 구절로
   요약하고, 종목 링크로 리포트를 가리킨다.
7. 종목을 처음 언급할 때는 링크를 단다. 형식은 [현대차](005380) — 대괄호에 표시할 말,
   소괄호에 여섯 자리 종목코드. 코드는 사실 블록에 적힌 것만 쓴다. 강조는 **굵게**.
   그 밖의 마크업이나 HTML 태그는 쓰지 마라.
8. 제목은 그날의 한 가지를 잡는다(12~30자). "코스피 상승, 외국인 순매수" 같은 나열이
   아니라 "휴장 하루, 미국은 두 번 열린다"처럼 관점이 있어야 한다.
9. 리드는 두 문장. 오늘 무엇을 준비해야 하는지가 리드에서 끝나야 한다.
10. 영어는 번역투가 아니라 영문 기사로 읽히게 쓴다. 한국어와 같은 사실, 같은 순서.
    종목 링크와 **굵게**는 영어에도 같이 넣는다.

출력 형식 — 머리말·설명 없이 곧바로 마커부터. 마커 앞뒤에 어떤 문장도 쓰지 마라.

===JSON_START===
{
  "title": {"ko": "제목", "en": "headline"},
  "lead":  {"ko": "리드 두 문장", "en": "..."},
  "sections": [
    {"id": "us", "heading": {"ko": "간밤 뉴욕", "en": "..."},
     "paragraphs": [{"ko": "문단", "en": "paragraph"}]}
  ]
}
===JSON_END===
"""


def build_prompt(facts, retry_note=None):
    dom = facts["domestic"]
    cal = dom.get("calendar") or {}
    pub = dom.get("publishDate") or datetime.datetime.now(KST).date().isoformat()
    state = "개장" if cal.get("open") else "휴장"

    head = (f"{pub} 아침에 발행할 모닝 브리핑 본문을 쓴다. 오늘 국내 증시는 {state}이다.\n"
            f"독자는 개장 전에 이 글 하나로 오늘(또는 다음 개장일) 준비를 마치려는 사람이다.\n")
    if not cal.get("open"):
        head += ("휴장일이므로 '오늘 장'을 준비하는 글이 아니다. 다음 개장일이 무엇을"
                 " 한꺼번에 반영해야 하는지가 그날의 핵심이다.\n")

    parts = [head, "\n=== 사실 블록 (여기 있는 값만 쓴다) ===\n", _facts_text(facts),
             "\n=== 사실 블록 끝 ===\n\n", RULES]
    if retry_note:
        parts.append("\n주의 — 앞선 출력이 아래 이유로 거부됐다. 같은 실수를 반복하지 마라.\n"
                     + retry_note + "\n")
    return "".join(parts)


# ────────────────────────────── 모델 호출 ──────────────────────────────

def _client():
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 가 없습니다.")
        sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def _params(prompt):
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM,
        # 어려운 판단이 들어가는 글이다 — 어느 숫자를 버릴지, 무엇을 제목으로
        # 잡을지. 사고 예산은 모델이 정하게 둔다.
        "thinking": {"type": "adaptive"},
        "messages": [{"role": "user", "content": prompt}],
    }


def _text_of(message):
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts)


def call_sync(cl, prompt):
    """스트리밍으로 부른다. 3,000자 양국어면 출력이 길어서 논스트리밍은
    요청 타임아웃에 걸릴 수 있다."""
    with cl.messages.stream(**_params(prompt)) as s:
        msg = s.get_final_message()
    return _text_of(msg), msg.usage


def call_batch(cl, prompt):
    """Batch API. 50% 싸지만 최대 24시간이다.

    끝날 때까지 기다리지 않는다 — BATCH_CUTOFF 안에 안 되면 취소하고
    None 을 돌려준다. 부르는 쪽이 동기로 다시 부른다. 발행 시각을 지키는
    것이 반값보다 중요하다.
    """
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    batch = cl.messages.batches.create(requests=[Request(
        custom_id="brief", params=MessageCreateParamsNonStreaming(**_params(prompt)))])
    log(f"· 배치 제출 {batch.id} — 최대 {BATCH_CUTOFF // 60}분 기다린다")

    waited = 0
    while waited < BATCH_CUTOFF:
        time.sleep(20)
        waited += 20
        b = cl.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            for r in cl.messages.batches.results(batch.id):
                if r.result.type == "succeeded":
                    log(f"· 배치 완료 ({waited}초) — 반값으로 받았다")
                    return _text_of(r.result.message), r.result.message.usage
                log(f"· 배치 결과 {r.result.type} — 동기로 다시 부른다")
            return None, None
        if waited % 300 == 0:
            log(f"· 배치 대기 {waited // 60}분 ({b.processing_status})")

    log(f"⚠️ {BATCH_CUTOFF // 60}분 내 미완료 — 취소하고 동기로 부른다")
    try:
        cl.messages.batches.cancel(batch.id)
    except Exception as e:
        log(f"· 배치 취소 실패(무시): {type(e).__name__} {e}")
    return None, None


def generate(cl, prompt):
    if USE_BATCH:
        text, usage = call_batch(cl, prompt)
        if text:
            return text, usage, True
    text, usage = call_sync(cl, prompt)
    return text, usage, False


# ────────────────────────────── 파싱·검증 ──────────────────────────────

def parse(text):
    m = re.search(r"===JSON_START===(.*?)===JSON_END===", text, re.S)
    chunk = (m.group(1) if m else text).strip()
    chunk = re.sub(r"^```(?:json)?", "", chunk).strip()
    chunk = re.sub(r"```$", "", chunk).strip()
    i, j = chunk.find("{"), chunk.rfind("}")
    if i >= 0 and j > i:
        chunk = chunk[i:j + 1]
    try:
        return json.loads(chunk)
    except Exception:
        from json_repair import repair_json
        return repair_json(chunk, return_objects=True)


# 표시 문자열 상한 80자. 회사 이름이나 짧은 구절이 들어오는 자리이므로 이보다
# 길면 링크로 의도한 게 아니다(문단을 통째로 감싼 것). 그런 건 링크로 보지 않는다.
LINK = re.compile(r"\[([^\[\]]{1,80})\]\((\d{6})\)")
ANY_LINK = re.compile(r"\[([^\[\]]{1,80})\]\(([^)]*)\)")


def _plain(s):
    """분량을 셀 때 쓰는 순수 텍스트. 링크·강조 표시는 빼고 센다."""
    s = LINK.sub(r"\1", s or "")
    s = ANY_LINK.sub(r"\1", s)
    return re.sub(r"\*\*", "", s)


def _walk(brief):
    """(경로, 문자열) 전부. ko/en 양쪽."""
    for key in ("title", "lead"):
        for lang in ("ko", "en"):
            yield f"{key}.{lang}", ((brief.get(key) or {}).get(lang) or "")
    for n, s in enumerate(brief.get("sections") or []):
        sid = s.get("id") or f"#{n}"
        for lang in ("ko", "en"):
            yield f"{sid}.heading.{lang}", ((s.get("heading") or {}).get(lang) or "")
        for i, p in enumerate(s.get("paragraphs") or []):
            for lang in ("ko", "en"):
                yield f"{sid}.p{i}.{lang}", ((p or {}).get(lang) or "")


def normalize_links(brief, valid_tickers):
    """커버리지에 없는 코드나 형식이 틀린 링크는 평문으로 되돌린다.

    모델이 만든 마크업을 그대로 페이지에 넣으면 우리가 안 만든 링크가
    걸린다. 여기서 걸러 두면 렌더링 쪽은 형식만 신뢰하면 된다.
    """
    dropped = []

    def fix(s):
        def one(mm):
            label, code = mm.group(1), mm.group(2)
            if re.fullmatch(r"\d{6}", code) and code in valid_tickers:
                return mm.group(0)
            dropped.append(f"{label}({code})")
            return label
        return ANY_LINK.sub(one, s or "")

    for key in ("title", "lead"):
        for lang in ("ko", "en"):
            if (brief.get(key) or {}).get(lang):
                brief[key][lang] = fix(brief[key][lang])
    for s in brief.get("sections") or []:
        for p in s.get("paragraphs") or []:
            for lang in ("ko", "en"):
                if p.get(lang):
                    p[lang] = fix(p[lang])
    return dropped


def measure(brief):
    """한국어 본문 글자 수와 커버리지 섹션 비중."""
    total, cov = 0, 0
    for path, s in _walk(brief):
        if not path.endswith(".ko"):
            continue
        n = len(_plain(s))
        total += n
        if path.startswith("coverage."):
            cov += n
    return total, (cov / total if total else 0.0)


def validate(brief, strict_coverage=True):
    """거부 이유 목록. 빈 목록이면 통과."""
    bad = []
    if not isinstance(brief, dict):
        return ["JSON 이 객체가 아니다"]

    for key in ("title", "lead"):
        for lang in ("ko", "en"):
            if not ((brief.get(key) or {}).get(lang) or "").strip():
                bad.append(f"{key}.{lang} 가 비었다")

    secs = brief.get("sections") or []
    ids = [s.get("id") for s in secs]
    if not secs:
        bad.append("sections 가 비었다")
    known = {k for k, _ in SECTIONS}
    for sid in ids:
        if sid not in known:
            bad.append(f"모르는 섹션 id: {sid!r} (허용: {', '.join(known)})")
    # 나온 순서대로 설계상의 자리번호를 매겨 오름차순인지 본다. SECTIONS 를
    # 훑어서 만들면 언제나 정렬돼 있어서 아무것도 걸러내지 못한다.
    rank = {k: i for i, (k, _) in enumerate(SECTIONS)}
    order = [rank[sid] for sid in ids if sid in rank]
    if order != sorted(order):
        bad.append("섹션 순서가 설계와 다르다 (us → domestic → ahead → coverage)")
    for s in secs:
        if not (s.get("paragraphs") or []):
            bad.append(f"섹션 {s.get('id')} 에 문단이 없다")

    # 양국어가 짝을 이루는지
    for path, s in _walk(brief):
        if path.endswith(".en") and not s.strip():
            ko_path = path[:-3] + ".ko"
            if any(p == ko_path and v.strip() for p, v in _walk(brief)):
                bad.append(f"{ko_path} 에 대응하는 영문이 없다")

    # 금지 표현 — 한국어·영어 모두 본다
    for path, s in _walk(brief):
        for pat, name in BANNED:
            m = pat.search(s)
            if m:
                bad.append(f"{path} 에 금지 표현({name}): …{m.group(0)}…")

    n, ratio = measure(brief)
    if n < LEN_MIN or n > LEN_MAX:
        bad.append(f"분량 {n:,}자 — {LEN_MIN:,}~{LEN_MAX:,}자를 벗어났다 "
                   f"(목표 {LEN_WANT[0]:,}~{LEN_WANT[1]:,})")
    cap = COVERAGE_CAP if strict_coverage else COVERAGE_HARD
    if ratio > cap:
        bad.append(f"커버리지 섹션이 전체의 {ratio*100:.0f}% — 상한 {cap*100:.0f}% 초과. "
                   "장 준비에 쓰이는 내용으로 옮기고 커버리지 문단을 줄여라")
    return bad


# ────────────────────────────── 저장 ──────────────────────────────

def save(brief, facts, meta, out_dir=OUT_DIR):
    pub = facts["domestic"].get("publishDate") or datetime.datetime.now(KST).date().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {
        "date": pub,
        "tradeDate": facts["domestic"]["tradeDate"],
        "marketOpen": (facts["domestic"].get("calendar") or {}).get("open"),
        "title": brief["title"],
        "lead": brief["lead"],
        "sections": brief["sections"],
        # 발행된 글이 이상할 때 원인을 가리는 유일한 단서다. 모델에게 넘긴
        # 것과 같은 텍스트를 그대로 남긴다.
        "factsDigest": _facts_text(facts),
        "meta": meta,
    }
    path = out_dir / f"{pub}.json"
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cost(usage, batch=False):
    if not usage:
        return None
    pin, pout = PRICES.get(MODEL, (0.0, 0.0))
    i = getattr(usage, "input_tokens", 0) or 0
    o = getattr(usage, "output_tokens", 0) or 0
    usd = (i * pin + o * pout) / 1e6
    if batch:
        usd *= 0.5
    return {"inputTokens": i, "outputTokens": o,
            "usd": round(usd, 4), "krw": round(usd * USD_KRW)}


# ────────────────────────────── main ──────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--facts-only", action="store_true", help="사실 블록만 출력(무료)")
    ap.add_argument("--dry-run", action="store_true",
                    help="프롬프트와 입력 토큰·예상 비용만(생성하지 않음)")
    ap.add_argument("--date", help="거래일 YYYYMMDD (기본: stocks.js 의 dataDate)")
    ap.add_argument("--days", type=int, default=14, help="일정을 며칠 앞까지 볼지")
    ap.add_argument("--no-news", action="store_true", help="뉴스 수집 생략")
    ap.add_argument("--force", action="store_true", help="같은 날 파일이 있어도 다시 만든다")
    ap.add_argument("--out", help="출력 폴더 (기본 data/briefs)")
    a = ap.parse_args()

    out_dir = Path(a.out) if a.out else OUT_DIR

    facts, fatal = gather(a.date, a.days, skip_news=a.no_news or a.facts_only)
    prompt = None
    if fatal:
        # 설계 4절: 휴장일 판정 실패는 대체할 수 없다.
        log(f"❌ {fatal} — 발행하지 않는다")
        if a.facts_only:
            print(_facts_text(facts) if facts.get("domestic") else "(사실 없음)")
        return 2

    if a.facts_only:
        print(_facts_text(facts))
        return 0

    pub = facts["domestic"].get("publishDate")
    existing = out_dir / f"{pub}.json"
    if existing.exists() and not a.force and not a.dry_run:
        # 아침에 세 번 시도하는 구조라서 이 장치가 필요하다. 없으면 성공한
        # 뒤에도 두 번 더 만들어 돈을 세 배로 쓴다.
        log(f"· {existing.name} 이 이미 있다 — 건너뛴다 (다시 만들려면 --force)")
        return 0

    prompt = build_prompt(facts)

    if a.dry_run:
        print(prompt)
        try:
            cl = _client()
            n = cl.messages.count_tokens(
                model=MODEL, system=SYSTEM,
                messages=[{"role": "user", "content": prompt}]).input_tokens
            pin, pout = PRICES.get(MODEL, (0.0, 0.0))
            # 출력은 양국어 3,000자 안팎 → 5,000토큰 정도로 잡는다.
            est = (n * pin + 5000 * pout) / 1e6
            log(f"\n■ 모델 {MODEL} · 입력 {n:,}토큰 (프롬프트 {len(prompt):,}자)")
            log(f"■ 예상 비용 한 편당 ${est:.3f} (약 {est*USD_KRW:,.0f}원)"
                + ("  ※ 배치 사용 시 절반" if USE_BATCH else ""))
        except SystemExit:
            log(f"\n■ 프롬프트 {len(prompt):,}자 (키가 없어 토큰은 못 셌다)")
        return 0

    cl = _client()
    from brief_data import load_stocks
    tickers = {s["ticker"] for s in load_stocks()[0]}

    def bail(cand, reasons):
        """두 번 다 실패하면 사람이 봐야 한다. 대충 고쳐 내보내지 않는다."""
        log("❌ 두 번 시도했으나 규칙을 통과하지 못했다 — 발행하지 않는다")
        (out_dir / "_rejected").mkdir(parents=True, exist_ok=True)
        f = out_dir / "_rejected" / f"{pub}.json"
        f.write_text(json.dumps({"brief": cand, "reasons": reasons},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"   거부된 결과를 {f} 에 남겼다")

    brief, batched, usage, note = None, False, None, None
    for attempt in (1, 2):
        text, usage, batched = generate(cl, build_prompt(facts, note))
        try:
            cand = parse(text)
        except Exception as e:
            note = f"JSON 을 읽을 수 없었다: {type(e).__name__} {e}"
            log(f"⚠️ {attempt}차 파싱 실패 — {note}")
            if attempt == 2:
                bail(text, [note])
                return 3
            continue
        dropped = normalize_links(cand, tickers)
        if dropped:
            log("· 확인되지 않은 종목 링크를 평문으로 바꿨다: " + ", ".join(dropped[:8]))
        # 1차는 설계대로 25% 로 본다. 2차는 30% 까지 눈감아 준다 — 발행이
        # 안 되는 것보다는 커버리지가 조금 긴 게 낫다. 그 위는 발행하지 않는다.
        bad = validate(cand, strict_coverage=(attempt == 1))
        if not bad:
            brief = cand
            break
        note = "\n".join(f"· {x}" for x in bad)
        log(f"⚠️ {attempt}차 거부:\n{note}")
        if attempt == 2:
            bail(cand, bad)
            return 3

    n, ratio = measure(brief)
    c = cost(usage, batched)
    meta = {"model": MODEL, "batched": batched, "chars": n,
            "coverageRatio": round(ratio, 3), "usage": c,
            "generatedAt": facts["generatedAt"]}
    path = save(brief, facts, meta, out_dir)

    log(f"\n✅ {path}")
    log(f"   제목  {brief['title']['ko']}")
    log(f"   분량  {n:,}자 (목표 {LEN_WANT[0]:,}~{LEN_WANT[1]:,}) · "
        f"커버리지 {ratio*100:.0f}% (상한 {COVERAGE_CAP*100:.0f}%)")
    log(f"   섹션  " + " → ".join(s["id"] for s in brief["sections"]))
    if c:
        log(f"   비용  입력 {c['inputTokens']:,} / 출력 {c['outputTokens']:,} 토큰 · "
            f"${c['usd']} (약 {c['krw']:,}원)" + ("  ← 배치 반값" if batched else ""))
    if n < LEN_WANT[0] or n > LEN_WANT[1]:
        log("   ⚠️ 목표 분량을 벗어났다(통과 범위 안이라 발행은 한다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
