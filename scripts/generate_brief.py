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

import number_spacing       # 금액 표기 통일(79조3,187억원 → 79조 3,187억원)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "briefs"
sys.path.insert(0, str(Path(__file__).resolve().parent))

KST = datetime.timezone(datetime.timedelta(hours=9))

MODEL = os.getenv("BRIEF_MODEL", "claude-opus-5")
# 사고(thinking) 토큰도 이 한도 안에서 센다. 통과한 글이 9,500~11,600 토큰을
# 썼는데 한도가 16,000 이면 재료가 많은 날 잘린다 — 잘린 JSON 은 repair 가
# 억지로 닫아 빈 칸 투성이 글이 되고, 그건 거부돼 $0.3 가 날아간다. 쓴 만큼만
# 내므로 한도를 올리는 데는 돈이 안 든다.
MAX_TOKENS = int(os.getenv("BRIEF_MAX_TOKENS", "24000"))
# 1차 글이 검사에 걸렸을 때 그 자리만 고치는 모델. 글 전체를 Opus 로 다시
# 쓰면 $0.31, 걸린 자리만 Sonnet 으로 고치면 $0.05 안팎이다.
REPAIR_MODEL = os.getenv("BRIEF_REPAIR_MODEL", "claude-sonnet-5")
# 사고(thinking)는 켜지 않는다. 편집이라 필요 없고, 9/21 시험에서 사고 토큰이
# 한도 8,000 을 먹어 답이 잘리고 $0.14 가 나갔다. 한도는 넉넉히 — 쓴 만큼만 낸다.
REPAIR_MAX_TOKENS = 16000
USE_BATCH = os.getenv("BRIEF_USE_BATCH", "") == "1"
BATCH_CUTOFF = int(os.getenv("BRIEF_BATCH_CUTOFF", "2400"))
# 뉴스를 종목별로 받을 개수. 구글 뉴스는 1초에 여덟 번 때리면 503 을 준다.
NEWS_TICKERS = int(os.getenv("BRIEF_NEWS_TICKERS", "4"))
# stocks.js 의 날짜가 직전 거래일과 며칠까지 벌어져도 넘어갈지. 기본은 0 —
# 어긋나면 발행하지 않는다. 이유는 gather() 에 적었다.
MAX_DATA_LAG = int(os.getenv("BRIEF_MAX_DATA_LAG", "0"))

# 백만 토큰당 (입력, 출력) 달러. 예상 비용 표시용이며 청구와 무관하다.
# Sonnet 5 는 2026-08-31 까지 도입가 $2/$10 이 적용된다.
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-5": (2.0, 10.0),     # 9/21 요금표 확인 — 출시 특가 $2/$10 이 정식 요금이 됐다
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
USD_KRW = float(os.getenv("BRIEF_USD_KRW", "1400"))

# 분량. 설계 문서 0절이 2,500~3,000자다. 이 밖이면 경고하고, 아래 하한/상한을
# 벗어나면 거부한다 — 1,200자짜리 브리핑은 브리핑이 아니고, 5,000자는 안 읽힌다.
# 실측: 네 편이 2,175 · 2,327 · 2,421 · 2,636자로 나왔다. 목표를 2,500~3,000 으로
# 잡아 뒀는데 모델이 실제로 앉는 자리는 2,300~2,600 이다. 하한을 2,200 으로 두니
# 8월 18일 06:00 시도에서 2차가 2,175자로 25자 모자라 거부됐고 그날 발행이 막혔다.
# 분량은 글의 질이 아니라 형식이다 — 25자 때문에 브리핑을 못 내보내면 규칙이 잘못된 것이다.
# 하한을 1,900 → 1,000 으로 내린다(2026-09-14). 규칙에는 "할 말이 적으면
# 짧게 끝내라" 고 적어 두고 바로 밑에서 2,000자를 요구했다 — 모순이었고, 그
# 빈자리를 채우느라 매일 열두 재료를 다 훑었다(여덟 편 중 여덟 편). 길이가
# 날마다 다른 것이 정상이다. 상한은 그대로 둔다 — 3,600자는 브리핑이 아니다.
LEN_MIN, LEN_MAX = 1000, 3600
LEN_WANT = (1200, 2800)
# 설계 문서 1절: "4번(커버리지)은 전체의 25%를 넘지 않는다."
COVERAGE_CAP = 0.25
COVERAGE_HARD = 0.30      # 재시도 후에도 이걸 넘으면 발행하지 않는다

# 섹션은 고정하지 않는다.
#
# 예전에는 us·domestic·ahead·coverage 넷을 이 순서로 박아 두고 칸마다 글자
# 수까지 배정했다. 18일치를 재 보니 네 칸 구성이 18일 중 18일 똑같았고,
# 리드가 '미국/뉴욕/간밤' 으로 시작한 날이 14일, 제목에 '반도체'가 들어간
# 날이 11일이었다. 재료가 부족해서가 아니다 — 뼈대가 같으니 리듬이 같았다.
#
# 그래서 몇 개를 쓸지, 무엇을 먼저 놓을지, 각각에 얼마를 쓸지를 모델이
# 정하게 두었다. 화면(render_brief.py)이 섹션 id 에 기대는 것은 coverage
# 하나뿐이다 — 그 섹션 위에만 출처 표시를 단다. 나머지는 몇 개든 어떤
# 순서든 그대로 그린다.
COVERAGE_ID = "coverage"

# 제목 길이. 상한과 하한이 하는 일이 다르다.
#
# 하한(6자)은 남긴다. '볼 것'·'간밤 뉴욕' 처럼 내용이 없는 고정 이름을 막는
# 것이 이 값의 일이고, 그건 지금도 필요하다. 낮춰 봤더니 '간밤 뉴욕'(5자)이
# 그대로 통과해서 되돌렸다.
#
# 상한은 30 → 44 로 연다. 30자라는 좁은 자리가 "A는 올랐고 B는 내렸다" 식의
# 짧은 대비 제목만 살아남게 만들었다(18일 중 8일). 한 줄을 넘기지 않는 선만
# 지키면 되고, 제목의 모양은 글쓴이가 정한다.
HEAD_MIN, HEAD_MAX = 6, 44
# 2차 시도에서만 주는 길이 여유. 9/18 에 2차 글이 소제목 45자 하나로 거부돼
# $0.3 를 버리고 그날 브리핑을 놓칠 뻔했다. 44자를 넘으면 문장이라는 판정은
# 그대로 두되, 한두 글자 차이로 하루치를 잃지는 않는다. 48자도 휴대폰에서는
# 44자와 같은 3줄이다.
HEAD_SLACK = 4
# 영어 제목을 그대로 옮긴 티가 나는 끝맺음.
HEAD_TRANSLATIONESE = re.compile(r"(에서|에 관하여|에 관해|에 대하여|에 대해|으로부터|로부터)$")
# 미국이 어젯밤에 열리지 않은 날에는 쓸 수 없는 말.
TIME_WORDS = re.compile(r"간밤|어젯밤|지난밤|하룻밤|어제")
# 회사명은 언제나 KOSAI 다. 한글 표기가 섞이면 브랜드가 화면마다 달라 보인다.
BRAND_KO = re.compile(r"코사이")

# 요약이 목록으로 흐르는 것을 잡는다. 줄바꿈, 글머리표(· • - ―), "1." 같은
# 번호 매김. 이어지는 문장으로 써야 사람이 쓴 글로 읽힌다.
# 줄표(– —)는 뺀다. 이 글은 "…했다 — 연준이…" 처럼 줄표를 문장부호로 쓰는데,
# 9/21 시험 생성의 요약이 그 줄표 하나로 '글머리표' 라며 거부됐다. 목록 표시는
# 가운뎃점·불릿·붙임표와 번호만 본다(줄 머리의 것은 repair_summary 가 먼저 뗀다).
SUM_LIST = re.compile(r"[\n\r]|(?:^|\s)[·•▪◦\-]\s|(?:^|\s)\d[.)]\s")

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
    "당신은 한국 주식시장(코스피·코스닥)을 오래 본 이코노미스트입니다. "
    "매일 장 시작 전에 발행되는 모닝 브리핑을 씁니다. 시세를 읽어 주는 사람이 아니라, "
    "무엇이 왜 움직였고 그래서 오늘 무엇을 봐야 하는지를 짧게 말하는 사람입니다. "
    "주어진 사실 블록에 있는 숫자만 사용하고, 없는 값은 추측하지 않습니다. "
    "이유도 사실 블록과 뉴스에 있는 것만 붙이고, 없으면 붙이지 않습니다. "
    "당신의 글은 한국어와 영어로 동시에 제공되며, 영문을 비워 두면 발행되지 않습니다."
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


def stale_data(prev, data_date):
    """우리 시세 파일(stocks.js)의 날짜가 직전 거래일과 같은가. 다르면 그 이유.

    1차 실행에서 여기가 어긋났다. 브랜치의 stocks.js 가 8월 4일이었는데 직전
    거래일은 8월 14일이었다. 지수·수급은 yfinance·네이버에서 14일 값을 받아
    오므로, 한 문단에 "코스피 6,977.94(14일)"와 "상승 2,220 대 하락 271(4일)"이
    같은 장의 일처럼 섞여 나갔다.

    값이 없는 것보다 나쁘다 — 없으면 문장이 빠지지만, 이건 틀린 문장이
    나간다. 그래서 경고가 아니라 정지다.
    """
    if not (prev and data_date):
        return None
    try:
        a = datetime.date.fromisoformat(f"{prev[:4]}-{prev[4:6]}-{prev[6:]}")
        b = datetime.date.fromisoformat(f"{data_date[:4]}-{data_date[4:6]}-{data_date[6:]}")
    except ValueError:
        return f"날짜를 읽을 수 없다: 직전 거래일 {prev!r}, 데이터 {data_date!r}"
    lag = abs((a - b).days)
    if lag <= MAX_DATA_LAG:
        return None
    return (f"우리 시세 데이터가 {data_date} 인데 직전 거래일은 {prev} 다 ({lag}일 차이)."
            " 국내 장 문단이 다른 날 숫자를 섞게 된다 — data/stocks.js 를 최신으로"
            " 맞춰라 (무시하려면 BRIEF_MAX_DATA_LAG)")


def overnight_ok(facts):
    """'간밤'·'어젯밤'을 쓸 수 있는 날인가. (쓸 수 있나, 사실 블록에 적을 문장)

    미국이 어젯밤에 열렸을 때만 쓸 수 있다. 그런 날은 화~금 아침뿐이다 —
    월요일 아침의 마지막 미국 세션은 금요일이고, 연휴 뒤에는 두 번 이상이다.

    어제 나간 브리핑 제목이 '간밤 뉴욕'이었는데 그 글은 금요일과 월요일
    두 세션을 다뤘다. 모델이 날짜를 보고 알아서 판단하게 두면 이런 게 새므로,
    쓸 수 있는지 없는지를 사실 블록에 문장으로 적어 넘긴다.
    """
    cal = ((facts or {}).get("domestic") or {}).get("calendar") or {}
    ser = (facts or {}).get("markets") or {}
    today_s = cal.get("today") or ""
    us_date = (ser.get("sp500") or ser.get("nasdaq") or {}).get("date")
    if not (re.fullmatch(r"\d{8}", today_s) and us_date):
        return True, None          # 판단 근거가 없으면 막지 않는다
    try:
        today = datetime.date.fromisoformat(f"{today_s[:4]}-{today_s[4:6]}-{today_s[6:]}")
        us = datetime.date.fromisoformat(us_date)
    except ValueError:
        return True, None
    gap = (today - us).days
    if gap == 1:
        return True, None
    return False, (f"[표현 주의] 미국 지수 기준일은 {us_date} 이고 오늘은 "
                   f"{today.isoformat()} 다 — 어젯밤에 미국이 열리지 않았다."
                   " '간밤'·'어젯밤'·'지난밤'을 쓰지 마라."
                   " 직전 거래일도 어제가 아니므로 '어제'도 쓸 수 없다.")


def skip_reason(cal, allow_closed=False):
    """오늘 브리핑을 낼 날인가. 내지 않을 이유가 있으면 그 문장을.

    모닝 브리핑은 국내 장이 열리는 날에만 나간다. 주말·공휴일·대체공휴일에는
    아무것도 발행하지 않는다.

    처음 설계에는 '휴장일에는 다른 글이 나간다'고 적어 뒀는데 그게 틀렸다.
    장 준비용 글이므로 준비할 장이 없는 날에는 쓸 이유가 없다. 8월 17일에
    나간 휴장일 브리핑은 발행 전 품질을 보려고 만든 것이고, 그 목적으로만
    allow_closed 를 남겨 둔다.
    """
    if allow_closed:
        return None
    if (cal or {}).get("open"):
        return None
    return (f"오늘({(cal or {}).get('today')})은 국내 증시 휴장 — 브리핑을 만들지 않는다"
            f" (다음 개장 {(cal or {}).get('next')})")


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

    stale = stale_data(cal.get("prev"), dom.get("tradeDate"))
    if stale:
        return facts, stale

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
        # None 이 아니라 '비었고 그 이유가 있다'로 남긴다.
        #
        #   예전에는 None 이었다. 그러면 사실 블록이 "[일정] 없음" 만 적고,
        #   "이 목록은 불완전하다" 경고는 붙지 않았다 — health 가 없으니까.
        #   일부만 실패하면 경고가 붙는데 통째로 실패하면 안 붙는, 뒤집힌
        #   구조였다. 제일 나쁜 경우가 제일 조용했다. 9월 11일 "일정은
        #   FOMC 하나뿐"이 나간 것과 같은 병이다.
        facts["schedule"] = {"events": [], "health": {
            "ok": False,
            "problems": [f"일정 수집이 통째로 실패했다: {type(e).__name__} {e}"]}}

    # ④ 뉴스. 없으면 인과를 쓰지 않는다(지어내는 것보다 낫다).
    if skip_news:
        # '안 받은 것'과 '못 받은 것'은 다르다. --facts-only 는 공짜 미리보기라
        # 일부러 뉴스를 건너뛰는데, 예전에는 결과가 "한 건도 받지 못했다"로
        # 찍혀 막힌 것처럼 보였다. 일정에서 당한 것과 같은 병이다.
        facts["news"] = {"skipped": True, "groups": {}, "tickers": {}}
    else:
        try:
            import news_data
            tks, names = _news_tickers(dom)
            facts["news"] = news_data.collect(tks, names)
        except Exception as e:
            log(f"⚠️ 뉴스 조회 실패 — '왜'를 쓰지 않는다: {type(e).__name__} {e}")
            # 일정과 같은 이유로 None 을 쓰지 않는다 — 통째로 실패한 것이
            # 조용히 넘어가면 안 된다.
            facts["news"] = {"groups": {}, "tickers": {}, "health": {
                "ok": False,
                "problems": [f"뉴스 수집이 통째로 실패했다: {type(e).__name__} {e}"]}}


    # ── 재료가 빠졌으면 소리를 낸다 ────────────────────────────────
    # 발행은 막지 않는다. 재료가 조금 부실해도 브리핑은 나가야 한다.
    # 다만 조용히 넘어가면 안 된다 — 9월 11일 "일정은 FOMC 하나뿐"이
    # 그렇게 나갔다. 두 주 넘게 말라 있었는데 아무 데서도 소리가 안 났다.
    for name, block in (("일정", facts.get("schedule")), ("뉴스", facts.get("news"))):
        hl = (block or {}).get("health") or {}
        for problem in hl.get("problems") or []:
            log(f"⚠️ {name} 수집이 부실하다 — {problem}")
            print(f"::warning title=브리핑 {name} 수집::{problem}", flush=True)

    return facts, None


# ────────────────────────────── 사실 → 텍스트 ──────────────────────────────

def _n(v, nd=2):
    return "—" if v is None else f"{v:,.{nd}f}"


def _pct(v):
    return "—" if v is None else f"{v:+.2f}%"


WEEK_KO = "월화수목금토일"


def _date8(s):
    """'20260914' → date. 아니면 None."""
    try:
        return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except (TypeError, ValueError):
        return None


def _wk(d):
    """9월 14일(월) 꼴."""
    return f"{d.month}월 {d.day}일({WEEK_KO[d.weekday()]})"


def week_of(today):
    """오늘이 속한 주의 월요일과 일요일."""
    mon = today - datetime.timedelta(days=today.weekday())
    return mon, mon + datetime.timedelta(days=6)


def week_tag(d, today):
    """어떤 날짜가 오늘 기준으로 '이번 주'인지 '다음 주'인지 — 글이 아니라
    계산이 답한다. 9월 14일(월) 브리핑이 9월 21일(다음 주 월) 시한을
    '이번 주 안에' 라고 적어 나간 적이 있다."""
    mon, sun = week_of(today)
    if mon <= d <= sun:
        return "이번 주"
    if sun < d <= sun + datetime.timedelta(days=7):
        return "다음 주"
    if d < mon:
        return "지난 주" if d >= mon - datetime.timedelta(days=7) else "그 전"
    return "그 다음"


def week_note(cal):
    """사실 블록 맨 위에 붙는 '오늘이 무슨 요일이고 이번 주가 어디까지인가'."""
    today = _date8((cal or {}).get("today"))
    if not today:
        return None
    mon, sun = week_of(today)
    nxt = sun + datetime.timedelta(days=1)
    return (f"  [요일] 오늘 {_wk(today)} · 이번 주 {_wk(mon)}~{_wk(sun)} · "
            f"{_wk(nxt)}부터 다음 주. 날짜를 '이번 주'·'다음 주'로 옮길 때는 이 범위만 쓴다 —"
            " 범위 밖 날짜에 '이번 주 안에'를 붙이지 마라.")


_KDATE = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일")


def _dates_in(text, year):
    """문장 속 'M월 D일'을 date 로. 연도가 없으면 올해."""
    out = []
    for m in _KDATE.finditer(text or ""):
        y = int(m.group(1)) if m.group(1) else year
        try:
            out.append(datetime.date(y, int(m.group(2)), int(m.group(3))))
        except ValueError:
            continue
    return out


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

    wn = week_note(cal)
    if wn:
        L.append(wn)

    ok_overnight, note = overnight_ok(facts)
    if note:
        L.append("  " + note)

    # 해외
    if ser:
        L.append("\n[미국·해외 · 종가와 전일 대비]")
        for key in ("sp500", "nasdaq", "dow", "sox", "ust10y", "wti", "dxy"):
            v = ser.get(key)
            if not v:
                continue
            if key == "ust10y" and v.get("prev") is not None:
                # 금리의 '+0.63%' 는 수익률의 상대 변화(4.94→4.97)지 %p 가
                # 아니다. 그대로 적으면 독자는 %p 로 읽는다 — 4.97%(+0.63%) 가
                # 그렇게 나갔다. 사람이 쓰는 단위(%p)로 바꿔 넘긴다.
                dp = v["close"] - v["prev"]
                L.append(f"  {v['label']}: {_n(v['close'])}% (전일 {_n(v['prev'])}% → "
                         f"{dp:+.2f}%p · 상대 변화 {_pct(v.get('change'))})  (기준일 {v.get('date')})")
                continue
            L.append(f"  {v['label']}: {_n(v['close'])}{v['unit']} {_pct(v.get('change'))}"
                     f"  (기준일 {v.get('date')})")
        # 넓힌 재료 — 묶음별 한 줄. 같은 묶음이 같은 기준일이면 끝에 한 번만 적는다.
        from market_data import SERIES_GROUPS
        for gname, keys in SERIES_GROUPS:
            got = [(k, ser[k]) for k in keys if ser.get(k)]
            if not got:
                continue
            dates = {v.get("date") for _, v in got}
            same = len(dates) == 1
            cells = []
            for k, v in got:
                cell = f"{v['label']} {_n(v['close'])}{v['unit']} {_pct(v.get('change'))}"
                if not same:
                    cell += f"({v.get('date')})"
                cells.append(cell)
            # 브리핑은 07:30 에 나간다. 도쿄·홍콩·상하이는 그 뒤에 연다 — 여기
            # 적힌 값은 언제나 직전 마감값이다. 9/14 낮 시험 생성이 금요일
            # 마감값을 "오늘 아시아는 … 엇갈려 있다" 로 썼다. 값 옆에 그 사실을
            # 적어 두면 그렇게 쓰지 않는다.
            head = (f"{gname}(오늘 장은 아직 열리기 전 · 아래는 직전 마감값)"
                    if gname == "아시아" else gname)
            L.append(f"  {head}: " + " · ".join(cells)
                     + (f"  (기준일 {dates.pop()})" if same else ""))
        miss = [lbl for k, lbl, *_ in SERIES
                if k not in ser and k not in ("kospi", "kosdaq")]
        if miss:
            L.append("  못 받은 값(쓰지 말 것): " + ", ".join(miss))
    else:
        L.append("\n[간밤 해외] 시세를 하나도 받지 못했다 — 섹션 1을 생략하라.")

    # 국내 지수·수급
    L.append(f"\n[직전 국내 장 · {dom['tradeDate']} ({dom['tradeDateKo']})]")
    idx = dom.get("index") or {}
    mismatch = [k for k, v in idx.items() if v.get("dateMismatch")]
    if mismatch:
        # 1차 실행에서 '날짜를 쓰지 말 것'이라고만 적었더니, 모델이 날짜는
        # 안 쓰면서 두 날짜의 값을 한 문단에 섞었다. 무엇을 하지 말아야
        # 하는지를 정확히 적는다.
        L.append(f"  ⚠️ 아래 지수는 {idx[mismatch[0]].get('date')} 값이고, 등락 종목 수·업종·"
                 f"거래대금은 {dom['tradeDate']} 값이다 — 다른 날이다."
                 " 두 묶음을 같은 장의 일처럼 한 문단에 섞지 마라."
                 " 섞을 수 없으면 지수 쪽을 버리고 등락·업종만 쓰라.")
    for key, lbl in (("kospi", "코스피"), ("kosdaq", "코스닥")):
        v = idx.get(key)
        if v:
            warn = f"  ⚠️기준일 {v.get('date')}" if v.get("dateMismatch") else ""
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
        # 업종을 괄호 안에 같이 적는다. 없으면 모델이 '같은 부품 안에서도'
        # 처럼 제 짐작으로 묶는다 — 반도체 장비주 다섯과 전자·부품(삼화콘덴서)
        # 을 한 묶음으로 쓴 적이 있다.
        L.append(f"  {title}: " + " · ".join(
            f"{r['name']}({r['ticker']}{'·' + r['sector'] if r.get('sector') else ''}) "
            f"{_pct(r['change'])} rel {r['rel']:+.2f}" for r in got))

    rows("대형주 선전(시장 대비)", "leaders")
    rows("대형주 부진(시장 대비)", "laggards")
    rows("절대 상승", "up")
    rows("절대 하락", "down")
    acts = m.get("actives") or []
    if acts:
        L.append("  거래대금 상위: " + " · ".join(
            f"{r['name']}({r['ticker']}{'·' + r['sector'] if r.get('sector') else ''}) "
            f"{r['tradingValue']:,}억원 {_pct(r['change'])}"
            for r in acts))
    if any(m.get(k) for k in ("leaders", "laggards", "up", "down", "actives")):
        L.append("  이 목록을 다 옮기지 마라. 한 문단에 종목 넷·등락률 대여섯 개까지다. 나머지는"
                 " 업종으로 묶어 말하라 — 목록은 화면의 표가 보여 준다.")
        L.append("  종목 괄호 안 뒤쪽이 업종이다. 종목을 '같은 업종·같은 부품·같은 반도체'"
                 " 처럼 묶어 쓸 때는 이 업종이 같을 때만 그렇게 쓴다. 다르면 '옆 업종인'"
                 " 처럼 다르다고 쓴다.")

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
        # 이 값은 야후 KRW=X 다 — 서울 외환시장 15:30 마감가가 아니라
        # 하루 종일 도는 시세의 한 시점이고, 등락률도 그 시계열의 직전 봉
        # 대비다. 그래서 뉴스의 '1,345.9원 마감·6.7원 상승'과 숫자도
        # 방향도 어긋난다. 무엇 대비인지 적어 두어야 모델이 두 값을
        # 같은 것으로 견주지 않는다.
        prev = f" · 직전 값 {_n(fx['prev'])}원 대비" if fx.get("prev") is not None else ""
        L.append(f"\n[환율] 원/달러 {_n(fx['close'])}원 {_pct(fx.get('change'))}{prev}"
                 f" (야후 KRW=X · 기준일 {fx.get('date')})")
        L.append("  ※ 서울 외환시장 마감가와 다른 시계열이다. 뉴스 제목의 '마감 환율'과"
                 " 이 값의 등락률을 같은 자리에서 견주지 마라 — 쓰려면 '기준값' 이라고"
                 " 부르고 기준일을 붙여라.")

    # 일정
    sch = facts.get("schedule") or {}
    evs = sch.get("events") or []
    hl = sch.get("health") or {}
    if evs:
        L.append(f"\n[일정 · {sch.get('from')} ~ {sch.get('to')}]")
        today_d = _date8(cal.get("today"))
        for e in evs[:14]:
            est = " (공개일 추정)" if e.get("estimated") else ""
            tag = ""
            try:
                d = datetime.date.fromisoformat(str(e["date"]))
                tag = f"({WEEK_KO[d.weekday()]}" + (f"·{week_tag(d, today_d)})" if today_d else ")")
            except (ValueError, KeyError, TypeError):
                pass
            L.append(f"  {e['date']}{tag} {e.get('kind', '')} {e.get('title', '')}{est}")
    else:
        L.append("\n[일정] 없음 — 일정 문장을 쓰지 말 것.")
    # 일정이 적은 것이 '조용한 주'인지 '우리가 못 가져온 것'인지를 밝힌다.
    # 9월 11일 브리핑이 "앞으로 2주 일정은 FOMC 하나뿐"이라고 썼는데, 정말
    # 하나뿐인 게 아니라 수집이 말라 있었다. 모델은 그걸 알 길이 없었다.
    if hl and not hl.get("ok", True):
        L.append("  ⚠️ 이 일정 목록은 불완전하다 — " + " / ".join(hl.get("problems") or []))
        L.append("  그러므로 '일정이 하나뿐'·'일정이 없다' 처럼 달력이 비어 있다는 것을"
                 " 시장의 사실로 쓰지 마라. 적힌 일정만 쓰고, 없는 것을 없다고 말하지 마라.")

    # 공시 + 확인 지점
    fils = dom.get("filings") or []
    if fils:
        total = fils[0].get("totalFilings") or len(fils)
        more = f" (전체 {total:,}건 중 시총 상위 {len(fils)}건)" if total > len(fils) else ""
        L.append(f"\n[정기보고서 접수 · 커버리지 종목{more}]")
        for f in fils[:12]:
            L.append(f"  {f['name']}({f['ticker']}) {f['report']} · 시총 {f.get('mcap', 0):.1f}조")
            if f.get("reportDate"):
                L.append(f"     └ 리포트 작성일 {f['reportDate']}"
                         + (f" · 제목 「{f['reportTitle']}」" if f.get("reportTitle") else ""))
            for c in (f.get("checkpoints") or [])[:2]:
                when = c.get("when", "")
                tag = ""
                td = _date8(cal.get("today"))
                if td:
                    ds = _dates_in(when, td.year)
                    if ds:
                        tag = f" ← {_wk(ds[0])}, {week_tag(ds[0], td)}"
                L.append(f"     └ 확인 지점 [{when}]{tag} {c.get('what', '')}")
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
    elif (facts.get("news") or {}).get("skipped"):
        L.append("\n[뉴스] 이번 실행에서는 일부러 받지 않았다(미리보기) — "
                 "실제 발행 때는 들어온다. 이 목록만 보고 '뉴스가 없다'고 판단하지 말 것.")
    else:
        L.append("\n[뉴스] 한 건도 받지 못했다 — 숫자만 쓰고 인과는 쓰지 말 것.")

    return "\n".join(L)


# ────────────────────────────── 프롬프트 ──────────────────────────────

RULES = """이 글이 하는 일

독자는 장이 열리기 전 아침에 이 글 하나를 읽고 오늘을 준비한다. 그 사람에게
오늘 필요한 것을 준다. 그게 전부다.

무엇을 쓸지는 네가 고른다

사실 블록에 오늘 쓸 수 있는 재료가 다 들어 있다 — 미국·해외 지수, 국내 지수와
수급, 업종, 거래가 몰린 곳, 개별 종목의 움직임, 환율·금리·유가, 앞으로의 일정과
지표 발표, 공시, 뉴스 제목, 그리고 KOSAI 리포트에 적어 둔 확인 지점.

그중 오늘 이야기할 값이 있는 것을 네가 고른다. 무엇을 먼저 놓을지, 각각에
얼마나 쓸지 — 정해진 틀이 없다. 어떤 날은 유가 하나가 그날의 전부이고, 어떤 날은
서로 상관없는 다섯 가지를 짧게 훑는 것이 맞다. 미국 지수부터 시작해야 할 이유는
없다. 그날 가장 중요한 것부터 쓰면 된다.

고른다는 것은 뺀다는 뜻이다. 사실 블록에 있다고 다 쓰지 않는다. 오늘 이야기가
안 되는 재료는 한 줄도 쓰지 않는다. 몇 개를 쓸지는 정해져 있지 않다 — 하나로
끝나는 날도, 여덟 개를 짧게 엮는 날도 있다. 다만 사실 블록의 항목을 차례로 읽어
주는 글은 안 된다. 여덟 편이 연달아 그렇게 나가서 "매일 같은 글"이 됐다.

어떻게 읽혀야 하나

증권사 모닝브리핑을 떠올려라. 그 글들은 시세표를 읽어 주지 않는다. **원인을 먼저
말하고 숫자는 근거로 붙인다.** 문단마다 "그래서 오늘 무엇을 보나"가 있다. 관심
업종·종목에는 반드시 '왜'가 붙는다. 그 리듬을 빌린다. 다만 그 글들이 하는 "상승
출발 전망"·"매수 유효" 같은 전망·추천은 우리가 쓸 수 없다(아래 규칙 2) — 방향을
말하지 않고도 이야기는 된다. 같은 사실을 두 가지로 쓸 수 있다.

  낭독:  코스피는 6,909.91(-1.76%)로 마감했다. 외국인은 2조 2,984억원을 순매도했다.
         조선은 3.48% 올랐고 정유는 4.41% 내렸다.
  이야기: 지수는 1.76% 빠졌는데 종목 중앙값은 -0.17%였다 — 내린 것은 대형주 몇 개다.
         외국인이 판 2조 3천억원이 그 자리에 있었고, 그 사이 조선은 HD현대중공업의
         증설 보도와 겹치며 3.48% 올랐다.

둘 다 사실 블록의 숫자만 썼다. 다른 것은 숫자 사이의 관계를 말했느냐다. 쓰기 전에
스스로 답하라 — 개장 전 독자가 알아야 할 것은 무엇이고, 왜 그런가. 그 답이 첫
문단이다. 나머지는 그 답에 붙는 이야기다. 어제 글(아래 '이미 쓴 글')의 첫 문단과
같은 이야기로 시작하지 마라.

숫자와 이유 — 이코노미스트의 규칙

너는 시세를 읽어 주는 사람이 아니다. 독자가 알아야 하는 것은 '무엇이 얼마나'가
아니라 '무엇이 왜, 그래서 오늘 무엇을 보나'다.

  · 이유가 있으면 한 구절로 붙인다 — "유가가 물러서며", "인텔과의 협상 보도가 나온
    뒤", "연준이 올린 다음 날". 길게 풀지 않는다. 브리핑이다.
  · 이유가 사실 블록·뉴스에 없으면 붙이지 않는다. 그냥 올랐다고 쓰고 넘어간다.
    지어낸 이유 하나가 글 전체의 믿음을 깎는다. 비어 있는 것이 낫다.
  · 숫자는 근거다. 한 문장에 두어 개면 족하다. "S&P 500 +1.14%, 나스닥 +1.69%,
    다우 +0.61%" 처럼 셋을 차례로 적는 것은 시세표다 — 같은 방향이면 대표 하나,
    갈렸으면 갈린 둘만. "숫자로 보면 …" 하고 시세를 나열하는 문장은 쓰지 않는다.
  · 종목을 늘어놓지 않는다. 한 문단에 종목 링크는 넷까지, 등락률 숫자는 대여섯
    개까지다. 그 이상은 이름을 빼고 업종으로 묶어 말한다 — "조선은 HD현대가
    6.52% 빠지며 업종 전체가 밀렸다" 로 충분하다. 삼성중공업·HD한국조선해양의
    등락률까지 붙이면 시세표가 된다. 상승 상위·하락 상위를 순서대로 읽어 주지
    마라. 독자는 표를 원하면 화면의 표를 본다. 글은 표가 못 하는 일을 한다.
  · 출처를 문장마다 달지 않는다. "연합뉴스는 …전했고 MBC는 …보도했다"는 기사
    모음이지 브리핑이 아니다. 인용이 꼭 필요한 곳에서 한 번만 밝힌다.
  · 중국·일본·홍콩 시장, 엔·위안, 해외 거시(일본은행·중국 지표·미국 고용·물가)는
    한국 시장에 닿는 날에만 쓴다 — 닛케이가 크게 움직였거나, 엔이나 위안이 원화와
    함께 밀렸거나, 중국 지표가 우리 수출 업종에 연결되는 날. 그런 날이 아니면
    아시아 줄은 한 문장도 쓰지 않는다. 매일 넣으면 매일 같은 글이 된다.
  · 쓸지 말지의 기준은 하나다 — 오늘 개장 전 독자가 이것을 알아야 하나. 아니면 뺀다.

다만 이건 '브리핑'이다. 아침에 읽는 글이니 보통 1,400~2,400자, 길어도 2,800자
안에서 끝난다 — 스크롤 두 번이다. 하한은 없다시피 하다(1,000자). 그날 할 말이
적으면 1,200자로 끝내라, 채우려고 늘리지 마라. 채우려고 늘린 글은 시세 낭독이
된다. 반대로 2,800자를 넘어가면 브리핑이 아니라 리포트가 된다(3,600자를 넘으면
아예 발행되지 않는다).
분량이 날마다 다른 것이 정상이다. 조용한 날과 시끄러운 날이 같은 길이일 이유가 없다.

섹션은 필요한 만큼 만들고, 각 섹션에 짧은 영문 id 를 붙인다(us · oil · rates ·
chips · flows · calendar · fx … 그날 내용에 맞게). KOSAI 리포트의 확인 지점을
다루는 섹션에만 id 를 coverage 로 붙여라 — 화면이 그 섹션에 출처 표시를 달아
준다. 그런 내용이 없는 날은 그 섹션을 만들지 않는다.

이미 쓴 글

아래에 최근에 나간 브리핑이 붙어 있다. 같은 각도, 같은 문장 구조, 같은 주인공을
반복하지 마라. 특히 "A는 올랐고 B는 내렸다" 식의 대비로 제목을 잡는 것은 이미
충분히 했다. 지수 등락률을 차례로 늘어놓는 것도 그렇다.

거꾸로, 이어지는 이야기는 환영한다. 지난 글에서 볼 것으로 꼽아 둔 것의 결과가
오늘 나왔다면 그것이 오늘의 첫 이야기일 수 있다. "지난주에 적어 둔 그것이 이렇게
됐다"는 하루짜리 시황이 줄 수 없는 것이다.

지켜야 할 것 — 여기부터는 취향이 아니라 지켜야 하는 선이다

1. 사실 블록에 있는 숫자만 쓴다. 없는 값은 추측하지 않고 그 문장을 뺀다.
   뉴스 제목에 나오는 숫자를 본문에 옮기지 마라 — 숫자는 시세에서, 이유는 뉴스에서
   가져온다. (기사의 '반도체지수 1% 하락'을 옮겼다가 실측 -0.31% 와 어긋난 적이 있다.)
2. 단정하지 않는다. 저평가·고평가, 매수·매도, 목표주가, 투자의견, "오를 것",
   "상승 여력" 같은 표현은 쓰지 않는다. 인과는 확인된 것만 쓰고, 추정은
   "~때문으로 보인다"가 아니라 "~와 겹친다", "~가 함께 나왔다"처럼 사실 병치로
   쓴다. 시장 전망·의견이 필요하면 출처를 밝힌 인용으로만 쓴다. 제목과 요약에도
   똑같이 적용된다.
3. 확인 지점은 유료 리포트 내용이다. 원문을 그대로 옮기지 말고 한 구절로 요약하고,
   종목 링크로 리포트를 가리킨다. 그리고 **언제 적어 둔 것인지**를 밝혀라 —
   "5월 리포트에서 확인 지점으로 꼽아 둔" 처럼. 시점이 핵심이다. 오늘 급하게 쓴
   말이 아니라는 뜻이기 때문이다. 그리고 이 브리핑은 리포트 홍보물이 아니다 —
   커버리지 얘기는 전체의 4분의 1을 넘지 않게 하고, 실제로 움직였거나 곧 결과가
   나오는 것만 넣는다.
4. 우리 회사는 언제나 `KOSAI` 라고 쓴다. 한국어 본문에서도 '코사이'라고 쓰지 마라.
5. 종목을 처음 언급할 때 링크를 단다. [현대차](005380) — 대괄호에 표시할 말,
   소괄호에 여섯 자리 종목코드. 코드는 사실 블록에 적힌 것만 쓴다. 강조는 **굵게**.
   그 밖의 마크업이나 HTML 태그는 쓰지 마라. 영문도 똑같은 형식으로 링크를 단다 —
   [SK Hynix](000660) 이다. **SK Hynix**(000660) 은 링크가 아니다. 한국어 문단에
   링크가 있으면 대응하는 영문 문단에도 있어야 한다.
6. 시간 표현을 조심하라. 사실 블록에 '[표현 주의]' 가 적혀 있으면 '간밤'·'어젯밤'·
   '어제'를 쓸 수 없는 날이다. 미국은 화~금 아침에만 어젯밤에 열렸다.
7. 영어는 번역투가 아니라 영문 기사로 읽히게 쓴다. 한국어와 같은 사실, 같은 순서.
   종목 링크와 **굵게**는 영어에도 같이 넣는다. title·lead·summary 의 en 도 본문과
   똑같이 채운다 — en 을 빈 문자열로 두면 그날 글은 발행되지 않는다.
8. 요약(summary)은 이어지는 문장으로 쓴다. 줄바꿈·글머리표·번호를 쓰지 마라 —
   항목을 나눠 늘어놓으면 사람이 쓴 글이 아니라 기계가 뽑아낸 목록처럼 읽힌다.
   본문에 없는 사실을 요약에만 새로 쓰지 말고, 종목 링크와 굵게는 요약에 쓰지 않는다.
   요약도 등락률 숫자는 대여섯 개면 족하다. 그날의 방향과 이유가 요약이지 시세가 아니다.
9. 섹션 제목은 그날 그 섹션에서 가장 중요한 사실을 담는다. '간밤 뉴욕'·'볼 것'
   같은 빈 이름이나 '~에서'·'~에 대하여' 로 끝나는 번역체는 쓰지 마라. 기사 제목과
   같은 말을 섹션 제목으로 다시 쓰지 말고, 섹션끼리도 겹치지 않게 한다.
10. 날짜를 '이번 주'·'다음 주'로 옮길 때는 사실 블록 맨 위 [요일] 의 범위로만
    옮긴다. 월요일 아침에 다음 주 월요일 시한을 '이번 주 안에' 라고 쓴 적이 있다.
    제목에서 특히 조심하라 — 본문은 맞고 제목만 틀리면 제목만 읽는 사람이 속는다.
11. 종목을 '같은 업종·같은 부품·같은 반도체' 처럼 한 묶음으로 쓸 때는 사실 블록의
    괄호 안 업종이 같을 때만 그렇게 쓴다. 업종이 다르면 '옆 업종인' 처럼 다르다고
    쓴다. 반도체 장비주들 옆에 전자·부품(콘덴서)을 '같은 부품' 으로 붙인 적이 있다.
12. 기준일이 다른 값을 한 문장에 섞지 마라. 환율은 오늘 기준값이고 유가·지수는
    직전 세션 값이다 — 같은 문단에 놓을 때는 '오늘 기준값' 처럼 어느 날 값인지
    붙여라. 수급을 요약에 옮길 때는 큰 쪽부터 쓴다(개인이 기타법인보다 크면
    개인을 먼저, 작은 쪽만 골라 쓰지 않는다).
13. 사실 블록의 ※ 나 '…하지 마라' 는 너에게 주는 규칙이지 독자에게 할 말이
    아니다. 그 문장을 글에 옮겨 적지 마라 — "…와 나란히 두지 않는 게 낫다" 처럼
    쓰면 독자는 누구에게 하는 말인지 알 수 없다. 규칙은 지키되 말하지 않는다.
14. 한 문단에 종목 링크는 넷까지, 등락률 숫자는 대여섯 개까지다. 사실 블록의
    상승·하락·거래대금 목록을 차례로 옮기지 마라 — 그 목록은 화면의 표에 있다.
    이 선을 넘긴 문단은 발행 전에 잘려 나간다.

출력 형식 — 머리말·설명 없이 곧바로 마커부터. 마커 앞뒤에 어떤 문장도 쓰지 마라.

===JSON_START===
{
  "title": {"ko": "제목", "en": "English headline"},
  "lead":  {"ko": "리드", "en": "English lead — same facts as ko, never empty"},
  "summary": {"ko": "요약 한 문단 — 줄바꿈도 글머리표도 없이 이어지는 문장",
              "en": "English summary — same facts as ko, never empty"},
  "sections": [
    {"id": "그날 내용에 맞는 짧은 영문 id", "heading": {"ko": "섹션 제목", "en": "..."},
     "paragraphs": [{"ko": "문단", "en": "paragraph"}]}
  ]
}
===JSON_END===

섹션 개수와 id 는 자유지만 **이 모양은 자유가 아니다**. title·lead·summary·heading 은
{"ko": …, "en": …} 객체이고, paragraphs 의 각 항목도 {"ko": …, "en": …} 객체다.
문단을 글자로만 주면 화면이 읽지 못해 그날 브리핑이 나가지 못한다.
"""


def recent_briefs(pub, n=7, out_dir=None):
    """최근에 나간 브리핑을 짧게 간추린다 — 같은 글을 또 쓰지 않게.

    왜 필요한가
    -----------
    여태 모델은 어제 자기가 뭐라고 썼는지 몰랐다. 매일 백지에서 같은 규칙과
    비슷한 재료로 시작하니 같은 답에 수렴한다. 18일치를 세어 보니 제목에
    '반도체'가 11일, 리드가 '미국/뉴욕/간밤' 으로 시작한 날이 14일이었다.
    재료 탓이 아니라 기억이 없어서다.

    본문을 통째로 넣지는 않는다. 7일치면 2만 자가 넘고, 그러면 모델이 지난
    글을 흉내 내기 시작한다. 필요한 것은 "무엇을 이미 말했나" 뿐이므로
    제목·리드·섹션 제목, 그리고 그날 볼 것으로 꼽은 대목만 넘긴다.
    """
    d = out_dir or OUT_DIR
    if not d.exists():
        return ""
    # 올라간 것만 센다. 만들어만 두고 안 올린 초안(품질 확인용으로 돌린 것,
    # 발행이 막힌 날의 잔해)은 아무도 못 본 글이다. 그것까지 "이미 나간
    # 글"이라고 내밀면 없는 독자를 피해 쓰게 된다.
    #
    # 그래서 넉넉히 읽고 거른 뒤에 n개로 자른다. 거르기 전에 자르면 초안이
    # 섞인 만큼 실제로 보여 주는 수가 줄어든다.
    files = []
    for x in sorted(d.glob("*.json"), reverse=True):
        if x.stem >= str(pub):
            continue
        try:
            if ((json.loads(x.read_text(encoding="utf-8")).get("meta") or {})
                    .get("publishedAt")):
                files.append(x)
        except Exception:
            continue
        if len(files) >= n:
            break
    files.reverse()
    if not files:
        return ""
    L = ["\n=== 최근에 이미 나간 브리핑 (같은 글을 또 쓰지 않기 위해 보여준다) ===\n"]
    for f in files:
        try:
            b = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        L.append(f"[{b.get('date', f.stem)}] {(b.get('title') or {}).get('ko', '')}")
        lead = (b.get("lead") or {}).get("ko", "")
        if lead:
            L.append(f"   리드: {lead[:120]}")
        heads = [(x.get("heading") or {}).get("ko", "") for x in (b.get("sections") or [])]
        heads = [h for h in heads if h]
        if heads:
            L.append("   섹션: " + " / ".join(heads))
        um = used_materials(b)
        if um:
            L.append(f"   다룬 재료({len(um)}/{len(MATERIALS)}): " + " · ".join(um))
        # 그날 '볼 것'으로 꼽아 둔 대목 — 오늘 결과가 나왔으면 그게 오늘 이야기다.
        for sec in b.get("sections") or []:
            body = " ".join((x.get("ko") or "") for x in (sec.get("paragraphs") or []))
            if any(k in body for k in ("볼 것", "지켜볼", "확인할", "관전")):
                L.append(f"   그날 볼 것으로 꼽음: {body[:180]}")
                break
    if len(L) == 1:            # 머리말만 남았다 — 보여 줄 것이 없다
        return ""
    L.append("\n=== 최근 브리핑 끝 ===\n")
    return "\n".join(L)


def build_prompt(facts, retry_note=None):
    dom = facts["domestic"]
    cal = dom.get("calendar") or {}
    pub = dom.get("publishDate") or datetime.datetime.now(KST).date().isoformat()
    state = "개장" if cal.get("open") else "휴장"

    head = (f"{pub} 아침에 발행할 모닝 브리핑 본문을 쓴다. 오늘 국내 증시는 {state}이다.\n"
            f"독자는 개장 전에 이 글 하나로 오늘(또는 다음 개장일) 준비를 마치려는 사람이다.\n"
            "쓰기 전에 한 문장으로 답하라 — 개장 전 독자가 알아야 할 것은 무엇이고, 왜 그런가."
            " 그 답이 첫 문단이 된다.\n")
    if not cal.get("open"):
        head += ("휴장일이므로 '오늘 장'을 준비하는 글이 아니다. 다음 개장일이 무엇을"
                 " 한꺼번에 반영해야 하는지가 그날의 핵심이다.\n")

    parts = [head, "\n=== 사실 블록 (여기 있는 값만 쓴다) ===\n", _facts_text(facts),
             "\n=== 사실 블록 끝 ===\n", recent_briefs(pub), "\n", RULES]
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


def _lang(box, lang):
    """{"ko": …, "en": …} 에서 한 쪽을 꺼낸다. 모양이 다르면 빈 문자열.

    모델이 가끔 {"ko":…,"en":…} 대신 글자를 그냥 준다. 예전에는 여기서
    AttributeError 로 통째로 터져 그날 브리핑이 못 나갔다. 검사기는 터지는
    곳이 아니라 거부 사유를 돌려주는 곳이다 — 그래야 다시 써 달라고 할 수
    있다. 모양 자체가 틀린 것은 validate 의 _shape_bad 가 따로 잡는다.
    """
    if isinstance(box, dict):
        v = box.get(lang)
        return v if isinstance(v, str) else ""
    return ""


def _shape_bad(brief):
    """틀이 어긋난 곳. 비어 있으면 나머지 검사를 그대로 돌려도 된다."""
    bad = []
    for key in ("title", "lead", "summary"):
        v = brief.get(key)
        if v is not None and not isinstance(v, dict):
            bad.append(f"{key} 가 {{\"ko\": …, \"en\": …}} 가 아니다")
    secs = brief.get("sections")
    if secs is not None and not isinstance(secs, list):
        return bad + ["sections 가 배열이 아니다"]
    for n, s in enumerate(secs or []):
        if not isinstance(s, dict):
            bad.append(f"{n+1}번째 섹션이 객체가 아니다")
            continue
        sid = s.get("id") or f"#{n}"
        if s.get("heading") is not None and not isinstance(s.get("heading"), dict):
            bad.append(f"{sid} 의 heading 이 {{\"ko\": …, \"en\": …}} 가 아니다")
        ps = s.get("paragraphs")
        if ps is not None and not isinstance(ps, list):
            bad.append(f"{sid} 의 paragraphs 가 배열이 아니다")
            continue
        for i, p in enumerate(ps or []):
            if not isinstance(p, dict):
                bad.append(f"{sid} 의 {i+1}번째 문단이 객체가 아니다 — 문단은 "
                           '{"ko": "…", "en": "…"} 로 쓴다. 글자만 주면 안 된다')
    return bad


def _walk(brief):
    """(경로, 문자열) 전부. ko/en 양쪽. 모양이 달라도 터지지 않는다."""
    for key in ("title", "lead", "summary"):
        for lang in ("ko", "en"):
            yield f"{key}.{lang}", _lang(brief.get(key), lang)
    secs = brief.get("sections")
    for n, s in enumerate(secs if isinstance(secs, list) else []):
        if not isinstance(s, dict):
            continue
        sid = s.get("id") or f"#{n}"
        for lang in ("ko", "en"):
            yield f"{sid}.heading.{lang}", _lang(s.get("heading"), lang)
        ps = s.get("paragraphs")
        for i, p in enumerate(ps if isinstance(ps, list) else []):
            for lang in ("ko", "en"):
                yield f"{sid}.p{i}.{lang}", _lang(p, lang)


def _set_path(brief, path, value):
    """_walk 가 내는 경로에 값을 쓴다. 성공하면 True.

    수리(repair)가 돌려준 조각을 제자리에 넣을 때 쓴다. 경로는 _walk 와 같은
    규칙이다 — title.ko · lead.en · {섹션id}.heading.ko · {섹션id}.p{n}.en.
    """
    parts = path.rsplit(".", 2)
    if len(parts) == 2 and parts[0] in ("title", "lead", "summary") and parts[1] in ("ko", "en"):
        if not isinstance(brief.get(parts[0]), dict):
            brief[parts[0]] = {}
        brief[parts[0]][parts[1]] = value
        return True
    if len(parts) == 3 and parts[2] in ("ko", "en"):
        sid, what, lang = parts
        secs = brief.get("sections")
        for n, s in enumerate(secs if isinstance(secs, list) else []):
            if not isinstance(s, dict) or (s.get("id") or f"#{n}") != sid:
                continue
            if what == "heading":
                if not isinstance(s.get("heading"), dict):
                    s["heading"] = {}
                s["heading"][lang] = value
                return True
            m = re.fullmatch(r"p(\d+)", what)
            ps = s.get("paragraphs")
            if m and isinstance(ps, list):
                i = int(m.group(1))
                if i < len(ps) and isinstance(ps[i], dict):
                    ps[i][lang] = value
                    return True
    return False


def _allowed_paths(brief, reasons):
    """거부 사유가 가리키는 자리만 고치게 한다.

    사유 문장은 검사기가 _walk 경로 그대로 쓴다("chips.p0 에 …", "lead.en 가
    비었다"). 그 자리의 ko·en 만 허용한다. 제목 사유("섹션 X 제목에", "X 제목이
    45자")는 X.heading 이고, '요약' 은 summary 다. 분량·커버리지처럼 자리가 없는
    사유가 있으면 전부 허용한다.
    """
    known = [p for p, _ in _walk(brief)]
    text = " ".join(reasons)
    if not any(p[:-3] in text for p in known) and "요약" not in text and "제목" not in text \
            or any(("분량" in r or "커버리지" in r) for r in reasons):
        return set(known)
    # 영문만 비었으면 영문 칸만 연다. 9/21 시험에서 lead.en 만 비었는데 모델이
    # lead.ko 까지 새로 써 왔다 — 멀쩡한 한국어를 새 주사위에 걸 이유가 없다.
    en_only = set()
    for m in re.finditer(r"(\S+)\.en 가 비었다|(\S+)\.ko 에 대응하는 영문이 없다", text):
        en_only.add(m.group(1) or m.group(2))
    both = set()
    for r in reasons:
        if re.search(r"\.en 가 비었다|에 대응하는 영문이 없다", r):
            continue
        both |= {p[:-3] for p in known if p[:-3] in r}
        for m in re.finditer(r"섹션 (\S+) 제목|(\S+) 제목이 \d+자", r):
            both.add(f"{m.group(1) or m.group(2)}.heading")
        if "요약" in r:
            both.add("summary")
    out = set()
    for p in known:
        stem = p[:-3]
        if stem in both or (stem in en_only and p.endswith(".en")):
            out.add(p)
    return out or set(known)


def apply_patch(brief, patch, allowed=None, changed=None):
    """수리 결과({경로: 새 글})를 글에 넣는다. 넣은 자리 수를 돌려준다.

    모르는 경로·빈 값·허용되지 않은 자리는 버린다. 그래서 수리 모델이 엉뚱한
    키를 내거나 사유에 없는 문단까지 손대도 글이 깨지지 않는다.

    모델이 조각 대신 글 전체를 돌려주는 날이 있다(9/21 시험 — 그래서 0곳으로
    끝났다). 그러면 원문과 다른 자리만 골라 조각으로 바꿔 넣는다.
    """
    if not isinstance(patch, dict):
        return 0
    known = {p for p, _ in _walk(brief)}
    if allowed is None:
        allowed = known
    if any(k in ("title", "lead", "summary", "sections") for k in patch):
        before = dict(_walk(brief))
        patch = {p: v for p, v in _walk(patch) if v.strip() and v != before.get(p)}
    n = 0
    for k, v in patch.items():
        if (k in known and k in allowed and isinstance(v, str) and v.strip()
                and _set_path(brief, k, v.strip())):
            n += 1
            if changed is not None:
                changed.append(k)
    return n


def _repair_prompt(brief, reasons):
    """수리 모델에게 줄 글. 문서를 통째로 주지 않는다.

    9/21 시험 둘 다 모델이 조각 대신 글 전체를 되돌려 보냈다(출력 8,000 토큰 ·
    $0.15). "전체를 돌려주지 마라" 고 써도 소용없었다 — 손에 문서가 있으니
    문서를 낸다. 그래서 문서를 주지 않는다. 사유가 가리킨 칸만 현재 글과 함께
    목록으로 주고, 나머지는 제목·섹션 제목만 참고로 준다. 되돌려 보낼 문서가
    없으니 답은 고친 칸뿐이다.
    """
    allowed = _allowed_paths(brief, reasons)
    cur = dict(_walk(brief))
    fields = [p for p in cur if p in allowed]
    # 영문 칸만 열린 자리는 한국어 원문을 읽기용으로 같이 준다 — 옮길 글이 있어야 한다.
    ref = [p[:-3] + ".ko" for p in fields if p.endswith(".en") and p[:-3] + ".ko" not in allowed]
    rules = RULES[RULES.index("지켜야 할 것"):RULES.index("출력 형식")]
    heads = " / ".join(_plain((x.get("heading") or {}).get("ko") or "")
                       for x in (brief.get("sections") or []) if isinstance(x, dict))
    title = _plain((brief.get("title") or {}).get("ko") or "")
    block = "\n".join(f"[{p}]\n{cur[p].strip() or '(비어 있음)'}\n" for p in fields)
    if ref:
        block += "\n읽기만 — 옮길 원문(고치지 말 것):\n\n" + "\n".join(
            f"[{p}] (참고)\n{cur[p].strip()}\n" for p in ref)
    ex = ", ".join(f'{{"path": "{p}", "text": "…"}}' for p in fields[:2]) \
        or '{"path": "lead.en", "text": "…"}'
    return (
        "모닝 브리핑 한 편이 발행 전 검사에서 거부됐다. 거부 사유:\n"
        + "\n".join(f"· {r}" for r in reasons)
        + "\n\n아래 칸만 고친다. 다른 칸은 보이지도 않고 고칠 수도 없다.\n"
        "고치는 법:\n"
        "· '영문이 없다'·'en 가 비었다' → 그 자리의 한국어(.ko)를 영문 기사처럼 옮긴다. 같은 사실,"
        " 같은 순서, 같은 종목 링크([Name](005930))와 **굵게**.\n"
        "· 한국어(.ko)를 고쳤으면 짝인 영문(.en)도 같이 고친다.\n"
        "· '제목이 …자' → 44자 이하로 줄인다. 그날 내용은 담는다.\n"
        "· '업종이 다른 종목을 …묶었다' → 사유에 적힌 업종대로, 다르면 '옆 업종인' 처럼 다르다고 쓴다.\n"
        "· '금지 표현' → 그 표현만 사실 병치로 바꾼다.\n"
        "· '분량'·'커버리지 … 초과' → 지목된 쪽을 줄인다. 새 사실은 넣지 않는다.\n"
        "· '나열이다' → 종목 이름과 등락률을 빼 링크 넷·등락률 대여섯 개 안으로 만든다. 뺀 종목은"
        " 업종으로 묶어 한 구절로 말한다. 한국어·영문 같이.\n"
        "· 새 숫자·새 사실을 넣지 마라. 사유와 상관없는 문장은 그대로 둔다.\n\n"
        + rules
        + f"\n참고 — 글 제목: {title}\n참고 — 섹션 제목: {heads}\n\n"
        "고칠 칸(현재 글):\n\n" + block
        + "\n출력은 JSON 하나뿐이다. changes 목록에 고친 칸만 넣는다 — path 는 위 [경로] 그대로, "
        "text 는 그 칸에 들어갈 글 전체. 바꾸지 않는 칸은 넣지 마라. 설명은 쓰지 마라.\n"
        f'{{"changes": [{ex}]}}\n'
    ), allowed


def _repair_schema(allowed):
    """수리 출력의 틀. output_config.format 으로 넘겨 JSON 밖의 글을 한 글자도 못 내게 한다.

    9/21 시험 셋 다 출력이 7,700~8,300 토큰이었다. 고칠 칸은 여섯이었는데 —
    나머지는 설명과 사고였다. 틀로 묶으면 답은 고친 칸의 글뿐이다.
    """
    return {
        "type": "object",
        "properties": {"changes": {"type": "array", "items": {
            "type": "object",
            "properties": {"path": {"type": "string", "enum": sorted(allowed)},
                           "text": {"type": "string"}},
            "required": ["path", "text"], "additionalProperties": False}}},
        "required": ["changes"], "additionalProperties": False,
    }


def _patch_of(obj):
    """수리 모델의 답을 {경로: 새 글} 로. {"changes":[{"path","text"}]} 도, 옛 모양(경로가
    바로 키)도, 글 전체를 돌려준 것도(apply_patch 가 조각으로 가른다) 받는다."""
    if isinstance(obj, dict) and isinstance(obj.get("changes"), list):
        return {c.get("path"): c.get("text") for c in obj["changes"]
                if isinstance(c, dict) and isinstance(c.get("path"), str)}
    return obj


def repair(cl, brief, reasons):
    """검사에 걸린 자리만 고친다 — 글 전체를 다시 쓰지 않는다.

    왜. 1차 글이 거부되면 전에는 Opus 로 처음부터 다시 썼다($0.31). 그런데
    거부 사유는 대개 '영문이 비었다'·'소제목이 길다'·'나열이다' 같은 한두
    자리다. 그 자리만 Sonnet 에게 고치게 하면 $0.05 안팎이고, 잘 쓴 나머지
    문단을 새 주사위에 걸지 않는다. 9/18 에 한 편 내려고 다섯 번 생성한 뒤에
    만들었다.

    돌려주는 것: (고친 자리 수, usage). 0 이면 부르는 쪽이 포기한다.
    """
    prompt, allowed = _repair_prompt(brief, reasons)
    # 사고는 끈다. Sonnet 5 는 thinking 을 비워 두면 사고가 *켜진다* — 9/21 시험에서
    # 출력 7,745 토큰 중 고친 글은 2,000 남짓이고 나머지가 사고였다. 옮기고 줄이는
    # 일이라 사고 없이 된다. 출력 틀(output_config.format)은 JSON 밖의 글을 막는다.
    params = dict(model=REPAIR_MODEL, max_tokens=REPAIR_MAX_TOKENS,
                  thinking={"type": "disabled"},
                  messages=[{"role": "user", "content": prompt}])
    try:
        msg = cl.messages.create(output_config={"format": {
            "type": "json_schema", "schema": _repair_schema(allowed)}}, **params)
    except Exception as e:
        # 틀 자체를 API 가 안 받는 날(400) — 그날 브리핑을 잃는 것보다 자유 출력이 낫다.
        if type(e).__name__ != "BadRequestError":
            raise
        log(f"⚠️ 수리 출력 틀을 못 받았다 — 자유 출력으로 부른다: {e}")
        msg = cl.messages.create(**params)
    try:
        patch = _patch_of(parse(_text_of(msg)))
    except Exception as e:
        log(f"⚠️ 수리 결과를 읽을 수 없다: {type(e).__name__} {e}")
        return 0, msg.usage
    changed = []
    n = apply_patch(brief, patch, allowed, changed)
    if changed:
        log("· 수리한 자리: " + ", ".join(changed))
    return n, msg.usage


BOLD_CODE = re.compile(r"\*\*([^*\n]{1,80})\*\*\s*\((\d{6})\)")


def repair_links(brief):
    """모델이 자주 내는 링크 형식 실수를 고친다.

    2차 실행에서 한국어는 [SK하이닉스](000660) 으로 제대로 썼는데 영문만
    **SK Hynix**(000660) 으로 냈다. 그 결과 영어 모드에서 종목 링크 13개가
    전부 사라지고 괄호 안의 숫자만 남았다 — 사전 값에 태그가 없으면 엔진이
    textContent 로 넣기 때문이다.

    '굵게 쓴 이름 + 바로 뒤 여섯 자리 괄호'는 의도가 분명하므로 여기서
    링크로 고친다. 이것 때문에 재시도를 돌리면 한 편당 350원이 또 나간다.
    형식이 이보다 모호한 경우는 고치지 않고 validate 가 거부한다.
    """
    fixed = []

    def fix(s):
        out, n = BOLD_CODE.subn(r"[\1](\2)", s or "")
        if n:
            fixed.append(n)
        return out

    for key in ("title", "lead", "summary"):
        for lang in ("ko", "en"):
            if (brief.get(key) or {}).get(lang):
                brief[key][lang] = fix(brief[key][lang])
    for s in brief.get("sections") or []:
        # 제목도 본문과 똑같이 본다. 화면(render_brief.to_html)이 제목에도
        # 링크를 거는데 여기서 빼 두면, 고쳐 주는 자리와 링크가 걸리는 자리가
        # 어긋난다.
        for lang in ("ko", "en"):
            if (s.get("heading") or {}).get(lang):
                s["heading"][lang] = fix(s["heading"][lang])
        for p in s.get("paragraphs") or []:
            for lang in ("ko", "en"):
                if p.get(lang):
                    p[lang] = fix(p[lang])
    return sum(fixed)


def repair_brand(brief):
    """'코사이' 를 'KOSAI' 로 고친다.

    검증에서 거부하고 재시도하게 둘 수도 있지만, 그러면 한 편당 400원이 더
    나가고 두 번 다 실패하면 그날 브리핑이 아예 안 나간다. 표기 하나 때문에
    발행을 멈출 이유가 없다 — 의도가 분명하니 여기서 고친다.
    검증(BRAND_KO)은 이 뒤에도 남은 게 있는지 보는 그물로만 쓴다.
    """
    n = 0

    def fix(x):
        nonlocal n
        if "코사이" in (x or ""):
            n += x.count("코사이")
            return x.replace("코사이", "KOSAI")
        return x

    for key in ("title", "lead", "summary"):
        for lang in ("ko", "en"):
            if (brief.get(key) or {}).get(lang):
                brief[key][lang] = fix(brief[key][lang])
    for sec in brief.get("sections") or []:
        for lang in ("ko", "en"):
            if (sec.get("heading") or {}).get(lang):
                sec["heading"][lang] = fix(sec["heading"][lang])
        for para in sec.get("paragraphs") or []:
            for lang in ("ko", "en"):
                if para.get(lang):
                    para[lang] = fix(para[lang])
    return n


def repair_summary(brief):
    """요약을 이어지는 한 문단으로 다듬는다. 고친 항목 수를 돌려준다.

    요약에는 링크도 굵게도 목록도 넣지 말라고 했지만 모델이 가끔 넣는다.
    거부하는 대신 벗겨낸다 — 장식 하나 때문에 그날 브리핑을 버릴 이유가 없다.

    모델이 목록으로 써 온 경우(줄바꿈 + 글머리표)는 글머리표를 떼고 줄을
    이어 붙인다. 문장으로 다시 쓰지는 못하지만, 적어도 화면에서 목록으로
    보이지는 않는다. 그래도 남는 어색함은 validate 가 잡는다.
    """
    s = brief.get("summary")
    if not isinstance(s, dict):
        return 0
    fixed = 0
    for lang in ("ko", "en"):
        x = s.get(lang)
        if not isinstance(x, str) or not x.strip():
            continue
        out = LINK.sub(r"\1", x)
        out = ANY_LINK.sub(r"\1", out)
        out = out.replace("**", "")
        # 줄 단위로 글머리표·번호를 떼고 한 줄로 잇는다
        lines = [re.sub(r"^\s*(?:[·•▪◦\-–—]|\d[.)])\s*", "", ln).strip()
                 for ln in out.splitlines()]
        out = " ".join(ln for ln in lines if ln)
        out = re.sub(r"\s{2,}", " ", out).strip()
        if out != x.strip():
            fixed += 1
        s[lang] = out
    return fixed


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

    for key in ("title", "lead", "summary"):
        for lang in ("ko", "en"):
            if (brief.get(key) or {}).get(lang):
                brief[key][lang] = fix(brief[key][lang])
    for s in brief.get("sections") or []:
        # 섹션 제목이 빠져 있었다. 제목은 매일 모델이 새로 쓰는 자리라
        # 거기에 종목 링크가 들어올 수 있는데, 화면은 제목에도 링크를 건다
        # (render_brief.py 의 to_html). 그래서 커버리지에 없는 여섯 자리가
        # 제목에 들어오면 없는 종목 페이지로 가는 링크가 그대로 나갔다.
        for lang in ("ko", "en"):
            if (s.get("heading") or {}).get(lang):
                s["heading"][lang] = fix(s["heading"][lang])
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
        if path.startswith(COVERAGE_ID + "."):
            cov += n
    return total, (cov / total if total else 0.0)


def check_headings(brief, facts=None, slack=0):
    """섹션 제목 검사. 제목을 매일 새로 쓰기로 했으니 여기가 그 대가다.

    slack — 길이 상한에 얹는 여유(자). 1차는 0, 2차는 HEAD_SLACK.

    고정 제목이면 한 번 정하고 끝인데, 매일 달라지면 매일 검증해야 한다.
    사용자가 그 비용을 알고 고른 선택이므로 조용히 넘기지 않는다.
    """
    bad = []
    heads, ok_overnight = [], overnight_ok(facts)[0]
    title_ko = ((brief.get("title") or {}).get("ko") or "").strip()

    for n, s in enumerate(brief.get("sections") or []):
        sid = s.get("id") or f"#{n}"
        ko = _plain((s.get("heading") or {}).get("ko") or "").strip()
        if not ko:
            continue
        heads.append((sid, ko))
        if len(ko) < HEAD_MIN:
            bad.append(f"{sid} 제목 '{ko}' 이 {len(ko)}자 — {HEAD_MIN}자 이상. "
                       "그날 내용을 담아라('볼 것' 같은 건 내용이 없다)")
        elif len(ko) > HEAD_MAX + slack:
            bad.append(f"{sid} 제목이 {len(ko)}자 — {HEAD_MAX + slack}자 이하. 제목이 아니라 문장이다")
        if HEAD_TRANSLATIONESE.search(ko):
            bad.append(f"{sid} 제목 '{ko}' 이 번역체로 끝난다 — "
                       "'~에서', '~에 대하여' 로 끝내지 마라")
        if title_ko and ko == _plain(title_ko).strip():
            bad.append(f"{sid} 제목이 기사 제목과 같다 — 섹션마다 다른 것을 잡아라")
        if not ok_overnight and TIME_WORDS.search(ko):
            m = TIME_WORDS.search(ko)
            bad.append(f"{sid} 제목에 '{m.group(0)}' — 어젯밤에 미국이 열리지 않은 날이다. "
                       "사실 블록의 [표현 주의] 를 보라")

    dup = {k for k, c in
           {h: [x for _, x in heads].count(h) for _, h in heads}.items() if c > 1}
    if dup:
        bad.append(f"섹션 제목이 겹친다: {', '.join(sorted(dup))}")

    # 제목만 막고 본문을 열어 두면 첫 문장에서 그대로 샌다.
    if not ok_overnight:
        for path, s in _walk(brief):
            if not path.endswith(".ko"):
                continue
            if path.startswith(("title.", "lead.")) and TIME_WORDS.search(s):
                m = TIME_WORDS.search(s)
                bad.append(f"{path} 에 '{m.group(0)}' — 어젯밤에 미국이 열리지 않은 날이다")
    return bad


# 사실 블록이 주는 재료 열두 묶음. 브리핑이 이 중 무엇을 다뤘는지 센다.
#
# 왜 세나. 여덟 편을 재 보니 여덟 편 전부가 열두 묶음을 다 다뤘다(지수를 못
# 받은 날만 열한 개). 섹션 이름과 제목은 날마다 달라졌지만 내용은 같은 열두
# 가지의 낭독이었다 — 사장이 "내용이 매일 똑같다" 고 한 것이 이것이다.
# 규칙에 "그날 이야기할 것을 네가 고른다" 고 적어 두었지만 고르라는 말만으로는
# 고르지 않는다. 그래서 몇 개까지인지를 정하고 검사가 센다.
MATERIALS = [
    ("미국지수",  re.compile(r"S&P|나스닥|다우")),
    ("반도체지수", re.compile(r"필라델피아")),
    ("국내지수",  re.compile(r"코스피[^.]{0,20}\d[\d,]*\.\d|코스닥[^.]{0,20}\d[\d,]*\.\d")),
    ("수급",     re.compile(r"(외국인|기관|개인|기타법인)[^.]{0,30}(순매수|순매도|억원)")),
    ("장폭",     re.compile(r"중앙값|상승 \d[\d,]*개|하락 \d[\d,]*개|장폭")),
    ("업종",     re.compile(r"업종 (상위|하위)|업종은 |업종에서 ")),
    ("종목",     None),                       # 링크가 5개 이상
    ("환율",     re.compile(r"원/달러|원·달러|달러당")),
    ("유가",     re.compile(r"WTI|유가|브렌트")),
    ("금리",     re.compile(r"10년물|국채 금리|기준금리|금통위")),
    ("일정",     re.compile(r"FOMC|발표된다|발표한다|공개된다|일정")),
    ("커버리지",  re.compile(r"리포트")),
    # 2026-09-14 에 넓힌 종류 — market_data.SERIES 의 새 시리즈와 짝이다
    ("아시아",    re.compile(r"닛케이|항셍|상하이")),
    ("미국개별",  re.compile(r"엔비디아|TSMC|마이크론|테슬라")),
    ("원자재",    re.compile(r"금값|금 가격|온스|구리|천연가스")),
    ("공포지수",  re.compile(r"VIX|공포지수|변동성지수")),
    ("비트코인",  re.compile(r"비트코인")),
]


def _body_ko(brief):
    b = brief or {}
    parts = [(b.get("lead") or {}).get("ko") or "", (b.get("summary") or {}).get("ko") or ""]
    for sec in b.get("sections") or []:
        parts += [(p.get("ko") or "") for p in sec.get("paragraphs") or []]
    return " ".join(parts)


def used_materials(brief):
    """브리핑이 다룬 재료 묶음의 이름들(정의 순서)."""
    body = _body_ko(brief)
    out = []
    for name, pat in MATERIALS:
        if pat is None:
            hit = len(LINK.findall(body)) >= 5
        else:
            hit = bool(pat.search(_plain(body)))
        if hit:
            out.append(name)
    return out


def yesterday_materials(pub, out_dir=None):
    """직전에 나간 브리핑이 다룬 재료. 없으면 None."""
    d = out_dir or OUT_DIR
    if not d.exists():
        return None
    for x in sorted(d.glob("*.json"), reverse=True):
        if x.stem >= str(pub):
            continue
        try:
            b = json.loads(x.read_text(encoding="utf-8"))
        except Exception:
            continue
        if ((b.get("meta") or {}).get("publishedAt")):
            return used_materials(b)
    return None


# 재료 상한(7개)과 '어제와 같은 조합' 거부는 넣었다가 뺐다(2026-09-14).
# 사장: "규칙을 넣으니까 너무 규격화된다." 맞는 말이다 — 몇 개를 쓸지는
# 글쓴이가 정한다. 검출기(used_materials)는 로그와 '이미 쓴 글' 표시에만 쓴다.


_SENT = re.compile(r"(?<=[.!?。])\s+|\n")
_WEEKWORD = re.compile(r"(이번\s*주|다음\s*주|지난\s*주)")
# '같은 …' 으로 종목을 한 묶음으로 만드는 말. 업종이 다르면 거짓이 된다.
_SAME_GROUP = re.compile(r"같은\s*(업종|부품|반도체|섹터|장비|소재|업계)")
# '같은 X' 뒤에 이런 말이 오면 그 뒤 종목은 다른 묶음이다 — "같은 반도체
# 안에서도 A는 올랐고, 옆 업종인 전자·부품에서는 B가 올랐다". 9/14 낮 시험
# 생성이 이 문장을 1차에서 거부당했다(2차 관용으로 살았다). 맞는 문장이었다.
_GROUP_CUT = re.compile(r"(?:옆|다른|별개의|바깥|인접)\s*(?:업종|섹터|묶음|그룹|분야)"
                        r"|업종(?:이|은|과|와)\s*다른|반면|한편|달리|밖에서|바깥에서")


def _sector_map(facts):
    """종목코드 → 업종. 사실 블록에 적힌 것과 같은 출처(movers)다."""
    out = {}
    m = (((facts or {}).get("domestic") or {}).get("movers") or {})
    for key in ("leaders", "laggards", "up", "down", "actives"):
        for r in m.get(key) or []:
            if r.get("ticker") and r.get("sector"):
                out[r["ticker"]] = r["sector"]
    return out


def _ko_texts(brief):
    """(경로, 한국어 문장들) — 제목·리드·요약·섹션 제목·문단."""
    for path, s in _walk(brief):
        if path.endswith(".ko"):
            yield path, [x.strip() for x in _SENT.split(_plain(s)) if x.strip()]


# '다음 주 월요일'·'이번 주 후반' — 낱말이 스스로 날짜를 이룬다. 이런 것은
# 문장 앞쪽의 다른 날짜와 짝지으면 안 된다.
_WEEK_SELF = re.compile(r"^\s*(?:[월화수목금토일]요일|초|중반|후반|말|주말)")
# 두 시점을 잇는 말. 이게 사이에 끼면 앞뒤 날짜는 서로 다른 일을 가리킨다 —
# "9월 12일 공시 뒤 다음 주", "이번 주 후반부터 9월 24일 연휴".
# '없·비어' — "이번 주에는 없고 9월 29일 JOLTS" 는 이번 주가 비었다는 말이고 9월
# 29일은 그다음 얘기다. 9/21 시험 생성이 이 꼴로 걸렸다. 모르면 판정하지 않는다.
_WEEK_SEQ = re.compile(r"부터|까지|이후|이전|뒤|후|전에|앞서|지나|이어|다음|없|비어")
_WEEK_AFTER, _WEEK_BEFORE = 10, 8


def _week_date(sent, m, today):
    """'이번 주' 낱말(m)이 가리키는 날짜. 바로 옆에 붙어 있을 때만 답한다.

    9월 14일(월) 시험 생성에서 "9월 12일(토) 공시가 … 다음 주 월요일까지"
    를 두 번 다 거부해 그날 글이 안 만들어졌다. 옛 방식은 문장 안에서
    글자 거리가 가장 가까운 낱말과 날짜를 무조건 짝지었는데, 그 문장의
    '다음 주' 는 월요일(9월 21일)을 말하는 것이지 9월 12일을 말하는 게
    아니었다. 멀리 있는 날짜는 무엇을 가리키는지 모른다 — 모르면 판정하지
    않는다. 거짓 거부 하나가 그날 브리핑 전체를 지운다.

      · 뒤에 붙은 날짜   "이번 주 9월 16일", "다음 주 월요일(9월 21일)"
      · 낱말이 스스로 날짜  "다음 주 월요일까지" → 앞 날짜와 짝짓지 않는다
      · 앞에 붙은 날짜   "9월 21일 결정이 이번 주 안에"
      · 사이에 '부터·까지·뒤·이후' 가 있으면 다른 시점이다 → 짝짓지 않는다
    """
    tail = sent[m.end():]
    dm = _KDATE.search(tail)
    if dm and dm.start() <= _WEEK_AFTER and not _WEEK_SEQ.search(tail[:dm.start()]):
        d = _dates_in(dm.group(0), today.year)
        return d[0] if d else None
    if _WEEK_SELF.match(tail):
        return None
    head = sent[:m.start()]
    last = None
    for dm in _KDATE.finditer(head):
        last = dm
    if last and len(head) - last.end() <= _WEEK_BEFORE \
            and not _WEEK_SEQ.search(head[last.end():]):
        d = _dates_in(last.group(0), today.year)
        return d[0] if d else None
    return None


def check_weeks(brief, facts):
    """'이번 주'·'다음 주'가 실제 달력과 맞는지.

    9월 14일(월) 브리핑이 9월 21일(다음 주 월) 시한을 '이번 주 안에' 라고
    제목에 달았다. 본문에는 날짜가 맞게 적혀 있었다 — 날짜를 주(週)로
    옮기는 그 한 걸음에서 미끄러진 것이다. 그 걸음은 계산으로 검사할 수 있다.

    보수적으로 본다: 같은 문장 안에 'M월 D일' 이 있을 때만 판정한다.
    날짜가 없는 '이번 주'는 무엇을 가리키는지 모르므로 건드리지 않는다.
    """
    today = _date8((((facts or {}).get("domestic") or {}).get("calendar") or {}).get("today"))
    if not today:
        return []
    bad = []
    for path, sents in _ko_texts(brief):
        for sent in sents:
            for m in _WEEKWORD.finditer(sent):
                d = _week_date(sent, m, today)
                if not d:
                    continue
                word = re.sub(r"\s+", " ", m.group(1))
                real = week_tag(d, today)
                if real != word and real in ("이번 주", "다음 주", "지난 주"):
                    bad.append(f"{path} 에 '{word}' — 그 문장의 {_wk(d)}은 {real}다"
                               f" (오늘 {_wk(today)}). 사실 블록의 [요일] 범위를 보라")
                    break
    # 제목·섹션 제목은 날짜가 같은 문장에 없는 경우가 많다(제목은 짧다).
    # 그럴 때는 본문의 확인 지점 날짜로 대신 판정한다 — 제목이 '이번 주'
    # 라고 했는데 그 섹션 본문에 적힌 날짜가 전부 다음 주면 제목이 틀린 것.
    for sec in brief.get("sections") or []:
        head = _plain((sec.get("heading") or {}).get("ko") or "")
        m = _WEEKWORD.search(head)
        if not m or _KDATE.search(head):
            continue
        word = re.sub(r"\s+", " ", m.group(1))
        # '다음 주 월요일까지' 는 스스로 날짜다. 본문 날짜가 전부 지난 주여도
        # (지난 주 공시 이야기를 하다 다음 주 시한을 말하는 글) 틀린 게 아니다.
        if _WEEK_SELF.match(head[m.end():]):
            continue
        body = " ".join(_plain(p.get("ko") or "") for p in sec.get("paragraphs") or [])
        # 본문이 같은 말을 '다음 주 월요일' 처럼 요일까지 박아 쓰고 있으면
        # 제목은 그 문장을 줄인 것이다. 본문 날짜가 전부 지난 주(공시 날짜)여도
        # 틀린 게 아니므로 본문 날짜를 끌어다 걸지 않는다.
        if re.search(word.replace(" ", r"\s*") + r"\s*(?:[월화수목금토일]요일|초|중반|후반|말|주말)", body):
            continue
        ds = _dates_in(body, today.year)
        if not ds:
            continue
        tags = {week_tag(d, today) for d in ds}
        # 제목에 주(週) 낱말이 둘 이상이면 어느 하나라도 본문 날짜와 맞으면 된다.
        # 9/21 에 "이번 주 미 지표는 비어 있고, 다음 주 29일부터 넷이 몰린다" 를
        # 앞 낱말('이번 주')만 보고 걸어서, 맞는 제목을 고치느라 $0.05 를 썼다.
        words = {re.sub(r"\s+", " ", x.group(1)) for x in _WEEKWORD.finditer(head)}
        if not (words & tags) and tags <= {"이번 주", "다음 주", "지난 주", "그 다음", "그 전"}:
            got = " · ".join(f"{_wk(d)}={week_tag(d, today)}" for d in ds[:3])
            bad.append(f"섹션 {sec.get('id')} 제목에 '{word}' — 본문의 날짜는 {got} 다"
                       f" (오늘 {_wk(today)})")
    return bad


# 이 수를 넘으면 나열로 본다. 프롬프트는 넷·대여섯을 말하고 여기는 그보다 조금
# 위에서 잡는다 — 한두 개 차이로 수리 호출($0.05)을 부르지 않기 위해서다.
LIST_LINKS, LIST_PCTS = 5, 7
_PCT = re.compile(r"[-+]?\d+(?:[.,]\d+)?%")


def check_listing(brief):
    """한 문단에 종목·등락률을 늘어놓았는지.

    9/21 사장: "너무 나열하는 느낌이 강하다". 그날 글에 종목 링크 7개·등락률
    11개짜리 문단이 둘 있었다. 링크·숫자를 세는 것이라 짐작은 아니지만
    어디까지가 나열인지는 취향의 선이므로, 문장 검사와 같이 2차에는 막지
    않는다 — 1차에 걸리면 수리가 그 문단만 줄인다.
    """
    bad = []
    for n, s in enumerate(brief.get("sections") or []):
        sid = s.get("id") or f"#{n}"
        for i, p in enumerate(s.get("paragraphs") if isinstance(s.get("paragraphs"), list) else []):
            ko = (p.get("ko") or "") if isinstance(p, dict) else ""
            links = len(LINK.findall(ko))
            pcts = len(_PCT.findall(_plain(ko)))
            if links > LIST_LINKS or pcts > LIST_PCTS:
                bad.append(f"{sid}.p{i} 에 종목 링크 {links}개 · 등락률 {pcts}개 — 나열이다. "
                           "링크는 넷까지, 등락률은 대여섯 개까지. 나머지는 이름을 빼고 업종으로 묶어 말하라")
    # 리드·요약은 하루를 눌러 담는 자리라 조금 더 준다.
    for key in ("lead", "summary"):
        pcts = len(_PCT.findall(_plain(_lang(brief.get(key), "ko"))))
        if pcts > LIST_PCTS + 2:
            bad.append(f"{key}.ko 에 등락률 {pcts}개 — 나열이다. 대여섯 개까지만 두고 나머지는 말로 하라")
    return bad


def check_sector_grouping(brief, facts):
    """'같은 부품 안에서도' 처럼 묶어 놓은 종목들의 업종이 정말 같은지.

    한미반도체·넥스틴·DB하이텍(반도체)을 늘어놓고 '같은 부품 안에서도
    삼화콘덴서(전자·부품)가 올랐다' 고 쓴 적이 있다. 종목 링크의 코드로
    업종을 찾을 수 있으니, 한 문장 안에서 두 업종 이상이 '같은' 으로
    묶이면 거부한다.
    """
    smap = _sector_map(facts)
    if not smap:
        return []
    bad = []
    for path, sents in _ko_texts(brief):
        # 링크는 _plain 이 벗기므로 원문에서 다시 본다.
        raw = next((v for pth, v in _walk(brief) if pth == path), "")
        raw_sents = [x for x in _SENT.split(raw) if x.strip()]
        for i, sent in enumerate(raw_sents):
            g = _SAME_GROUP.search(sent)
            if not g:
                continue
            # 묶음은 두 문장에 걸친다 — 앞 문장에 종목을 늘어놓고, 다음 문장이
            # "다만 같은 부품 안에서도 X가 올랐다" 로 받는다. 실제로 그렇게
            # 나갔다. 그래서 '같은 …' 문장과 바로 앞 문장을 한 창으로 본다.
            # 다만 '같은 X' 뒤에서 글쓴이가 스스로 "옆 업종인 …" 하고 갈라
            # 놓았으면 거기까지만 본다 — 그 뒤 종목은 같은 묶음이 아니다.
            cut = _GROUP_CUT.search(sent, g.end())
            cur = sent[:cut.start()] if cut else sent
            window = (raw_sents[i - 1] + " " if i > 0 else "") + cur
            codes = [m.group(2) for m in LINK.finditer(window)]
            secs = {smap[c] for c in codes if c in smap}
            if len(secs) >= 2:
                pairs = ", ".join(f"{c}={smap[c]}" for c in codes if c in smap)
                bad.append(f"{path} 에서 업종이 다른 종목을 '{_SAME_GROUP.search(sent).group(0)}'"
                           f" 으로 묶었다 — {pairs}. 업종이 다르면 다르다고 써라")
    return bad


def validate(brief, strict_coverage=True, facts=None, strict_text=True,
             head_slack=0):
    """거부 이유 목록. 빈 목록이면 통과.

    head_slack — 소제목 길이 상한에 얹는 여유(자). 2차에서 HEAD_SLACK 을 준다.
    검사 자체는 2차에도 산다(길이는 짐작이 아니라 셈이라 틀릴 수 없다). 다만
    한두 글자 차이로 $0.3 글을 버리고 그날 브리핑을 놓치지는 않는다.

    strict_text — 문장을 읽어 판정하는 검사(주 범위·업종 묶음)를 거부
    사유로 칠지. 1차에서는 친다. 2차에서는 경고만 남기고 내보낸다: 이
    검사들은 글을 짐작으로 읽는 것이라 틀릴 수 있고, 같은 이유로 두 번
    거부되면 그날 브리핑이 통째로 사라진다. 한 문장의 '이번 주' 가 어긋난
    글이 글이 없는 것보다 낫다. 1차 거부 사유는 2차 프롬프트에 붙으므로
    진짜 틀린 것은 2차에서 대개 고쳐져 온다.
    """
    bad = []
    if not isinstance(brief, dict):
        return ["JSON 이 객체가 아니다"]
    # 틀이 어긋나 있으면 아래 검사들이 엉뚱한 데서 터진다. 여기서 끊고
    # 사유를 돌려줘야 다시 써 달라고 할 수 있다.
    shape = _shape_bad(brief)
    if shape:
        return shape

    for key in ("title", "lead", "summary"):
        for lang in ("ko", "en"):
            if not ((brief.get(key) or {}).get(lang) or "").strip():
                bad.append(f"{key}.{lang} 가 비었다")

    # 요약은 화면 맨 위, 본문 앞에 놓인다. 목록이 아니라 이어지는 문장이어야
    # 한다 — 항목을 나눠 늘어놓으면 사람이 쓴 글로 읽히지 않는다.
    ko_sum = _plain((brief.get("summary") or {}).get("ko") or "")
    if not ko_sum:
        # 1차에서는 다시 받아 온다. 2차에도 없으면 요약 없이 내보낸다 —
        # 렌더러가 그 블록만 건너뛰므로, 요약 하나 때문에 그날 브리핑을
        # 통째로 버리는 것보다 낫다.
        if strict_coverage:
            bad.append("summary 가 비었다 — 맨 위 요약 문단이 있어야 한다")
    else:
        # 길이는 글쓰기 규칙이 아니라 화면이 견디는 선이다. 예전 110~400자는
        # 요약의 모양까지 정해 버렸다. 한 문단으로 읽히기만 하면 된다.
        n = len(ko_sum)
        if not 60 <= n <= 900:
            bad.append(f"요약이 {n}자 — 60~900자여야 한다(화면이 견디는 선)")
        # 문장 수는 세지 않는다. 마침표 개수로 재면 소수점·약어에 걸려
        # 멀쩡한 글을 거부한다. 목록으로 흐르는 것만 막으면 충분하다.
        if SUM_LIST.search(ko_sum):
            bad.append("요약에 글머리표·번호가 있다 — 이어지는 문장으로 써야 한다")

    secs = brief.get("sections") or []
    ids = [s.get("id") for s in secs]
    if not secs:
        bad.append("sections 가 비었다")
    # 어떤 id 를 몇 개, 어떤 순서로 쓸지는 글쓴이가 정한다. 화면은 순서대로
    # 그대로 그리므로 여기서 막을 것이 없다. 다만 id 는 있어야 하고(화면이
    # coverage 를 알아봐야 한다) 겹치면 안 된다.
    for n_, sid in enumerate(ids):
        if not (sid or "").strip():
            bad.append(f"{n_+1}번째 섹션에 id 가 없다 — 짧은 영문 id 를 붙여라")
    dup_ids = {x for x in ids if x and ids.count(x) > 1}
    if dup_ids:
        bad.append(f"섹션 id 가 겹친다: {', '.join(sorted(dup_ids))}")
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

    # 종목 링크가 한국어에만 있으면 영어 모드에서 그 링크가 통째로 사라진다.
    # 2차 실행에서 실제로 13개가 날아갔다. 화면을 영어로 바꿔 보지 않으면
    # 모르는 종류라서 여기서 막는다.
    for n_sec, s in enumerate(brief.get("sections") or []):
        sid = s.get("id") or f"#{n_sec}"
        for i, p in enumerate(s.get("paragraphs") or []):
            ko_codes = {m.group(2) for m in LINK.finditer(p.get("ko") or "")}
            en_codes = {m.group(2) for m in LINK.finditer(p.get("en") or "")}
            if ko_codes and not en_codes:
                bad.append(f"{sid}.p{i} 의 종목 링크 {len(ko_codes)}개가 영문에 없다 — "
                           "영문도 [Name](005930) 형식으로 링크를 달아라 "
                           "(**Name**(005930) 은 링크가 아니다)")
            elif en_codes - ko_codes:
                bad.append(f"{sid}.p{i} 영문에만 있는 종목 링크: "
                           f"{', '.join(sorted(en_codes - ko_codes))}")

    bad += check_headings(brief, facts, slack=head_slack)
    soft = check_weeks(brief, facts) + check_sector_grouping(brief, facts) + check_listing(brief)
    if strict_text:
        bad += soft
    else:
        for x in soft:
            log(f"⚠️ 2차라 넘긴다(문장 검사): {x}")
            if os.getenv("GITHUB_ACTIONS"):
                print(f"::warning title=브리핑 문장 검사::{x}")

    # coverage 섹션은 출처를 밝혀야 한다. 이게 이 브리핑의 존재 이유인데,
    # 어디서 온 얘기인지 안 적으면 독자는 그냥 종목 소식으로 읽고 지나간다.
    for s_ in brief.get("sections") or []:
        if s_.get("id") != COVERAGE_ID:
            continue
        body = " ".join((p.get("ko") or "") for p in (s_.get("paragraphs") or []))
        if "리포트" not in body:
            bad.append("coverage 섹션에 '리포트'라는 말이 없다 — 확인 지점이 코사이 "
                       "리포트에서 나온 것임을 독자가 알 수 없다. 언제 적어 둔 것인지와 "
                       "함께 밝혀라")
        if not LINK.search(body):
            bad.append("coverage 섹션에 종목 링크가 없다 — 링크가 근거를 가리키는 표시다")

    # 회사명 표기. 한 군데만 '코사이'로 새도 브랜드가 흔들려 보인다.
    for path, txt in _walk(brief):
        m = BRAND_KO.search(txt)
        if m:
            bad.append(f"{path} 에 '코사이' — 회사명은 언제나 'KOSAI' 로 쓴다")

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
        "summary": brief.get("summary") or {},
        "sections": brief["sections"],
        # 발행된 글이 이상할 때 원인을 가리는 유일한 단서다. 모델에게 넘긴
        # 것과 같은 텍스트를 그대로 남긴다.
        "factsDigest": _facts_text(facts),
        "meta": meta,
    }
    path = out_dir / f"{pub}.json"
    # 금액 표기 통일 — 리포트·업종과 같은 규칙(한글 맞춤법 제44항)
    _nsp, doc = number_spacing.normalize_report(doc)
    if _nsp:
        print(f"  · 금액 표기 {_nsp}곳 정리")
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def cost(usage, batch=False, model=None):
    if not usage:
        return None
    pin, pout = PRICES.get(model or MODEL, (0.0, 0.0))
    i = getattr(usage, "input_tokens", 0) or 0
    o = getattr(usage, "output_tokens", 0) or 0
    usd = (i * pin + o * pout) / 1e6
    if batch:
        usd *= 0.5
    return {"inputTokens": i, "outputTokens": o,
            "usd": round(usd, 4), "krw": round(usd * USD_KRW)}


def repair_only(path):
    """수리 경로만 돌려 본다(시험용 · Sonnet 한 번 · $0.05 안팎).

    나간 글 하나를 읽어 lead.en 을 비우고(영문 번역이 걸리게), 나열 검사가
    잡는 문단은 그대로 둔 채 repair() 를 부른다. 9/21 live 시험에서 수리가
    0곳으로 끝나 $0.55 를 버린 뒤, 생성($0.31) 없이 수리만 확인하는 길을 뒀다.
    """
    cl = _client()
    doc = json.loads(path.read_text(encoding="utf-8"))
    brief = {k: doc[k] for k in ("title", "lead", "summary", "sections") if k in doc}
    brief["lead"]["en"] = ""
    reasons = validate(brief, strict_coverage=True, facts=None, strict_text=True,
                       head_slack=HEAD_SLACK)
    log("거부 사유(시험):\n" + "\n".join(f"· {r}" for r in reasons))
    if not reasons:
        log("· 잡히는 것이 없다 — 시험할 것이 없다")
        return 0
    n, usage = repair(cl, brief, reasons)
    c = cost(usage, False, model=REPAIR_MODEL) or {}
    log(f"· 수리: {n}곳 · ${c.get('usd', 0):.3f} (입력 {c.get('inputTokens', 0):,} / "
        f"출력 {c.get('outputTokens', 0):,} 토큰)")
    left = validate(brief, strict_coverage=False, facts=None, strict_text=False,
                    head_slack=HEAD_SLACK)
    for r in left:
        log(f"  남은 사유: {r}")
    listing_left = check_listing(brief)
    for r in listing_left:
        log(f"  나열 남음(2차 관용): {r}")
    ok = n > 0 and not left and bool((brief["lead"].get("en") or "").strip())
    log("✅ 수리 경로 정상" if ok else "❌ 수리 경로 실패")
    return 0 if ok else 2


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
    ap.add_argument("--allow-closed", action="store_true",
                    help="휴장일에도 만든다 (품질 확인용. 발행하는 글이 아니다)")
    ap.add_argument("--out", help="출력 폴더 (기본 data/briefs)")
    ap.add_argument("--repair-only", metavar="BRIEF_JSON",
                    help="시험용: 나간 글 하나를 읽어 수리 경로만 돌린다 (Sonnet 한 번 · 약 $0.05)")
    a = ap.parse_args()

    out_dir = Path(a.out) if a.out else OUT_DIR
    if a.repair_only:
        return repair_only(Path(a.repair_only))

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

    skip = skip_reason(facts["domestic"].get("calendar"), a.allow_closed)
    if skip:
        # 실패가 아니라 '오늘은 낼 날이 아니다'다. 0 으로 끝내야 주말마다
        # 붉은 X 가 뜨지 않는다 — 그러면 정작 봐야 할 실패와 구분이 안 된다.
        log("· " + skip)
        return 0
    if a.allow_closed and not (facts["domestic"].get("calendar") or {}).get("open"):
        log("⚠️ 휴장일인데 --allow-closed 로 만든다 — 발행용이 아니다")

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
    prev_mat = yesterday_materials(pub, out_dir)

    # 시도마다 쓴 돈. 버려진 글도 돈은 나갔다 — 전에는 통과한 글의 값만 남겨서
    # 콘솔 청구와 로그가 안 맞았다(9/18: 다섯 번 생성, 기록은 한 편 값).
    spent = []

    def bail(cand, reasons):
        """두 번 다 실패하면 사람이 봐야 한다. 대충 고쳐 내보내지 않는다."""
        log("❌ 두 번 시도했으나 규칙을 통과하지 못했다 — 발행하지 않는다")
        (out_dir / "_rejected").mkdir(parents=True, exist_ok=True)
        f = out_dir / "_rejected" / f"{pub}.json"
        f.write_text(json.dumps({"brief": cand, "reasons": reasons, "spent": spent},
                                ensure_ascii=False, indent=2), encoding="utf-8")
        log(f"   거부된 결과를 {f} 에 남겼다")
        usd = sum(x.get("usd", 0) for x in spent)
        log(f"   버린 돈  {len(spent)}회 생성 · ${usd:.3f} (약 {round(usd * USD_KRW):,}원)")

    brief, batched, usage, note = None, False, None, None
    cand, last_bad, repaired = None, None, 0
    gen_usage, gen_batched = None, False      # Opus 생성분만 — 수리 호출과 따로 센다
    for attempt in (1, 2):
        if attempt == 2 and isinstance(cand, dict) and last_bad:
            # 1차 글은 틀이 멀쩡하고 검사에서만 걸렸다. 그 자리만 고친다 —
            # 하루에 글 한 편 값만 쓰자는 것이 이 자리의 목적이다.
            try:
                repaired, usage = repair(cl, cand, last_bad)
            except Exception as e:
                # 수리 호출 자체가 실패하면(통신·API) 글은 그대로 두고 포기한다.
                # 예비 실행이 새로 쓴다. 여기서 터져 워크플로가 통째로 죽는 것보다 낫다.
                log(f"⚠️ 수리 호출 실패: {type(e).__name__} {e}")
                repaired, usage = 0, None
            spent.append(cost(usage, False, model=REPAIR_MODEL) or {})
            log(f"· 수리: {REPAIR_MODEL} 가 {repaired}곳을 고쳤다"
                f" (${(spent[-1].get('usd') or 0):.3f})")
            if not repaired:
                bail(cand, last_bad + ["수리 결과를 적용하지 못했다"])
                return 3
        else:
            text, usage, batched = generate(cl, build_prompt(facts, note))
            gen_usage, gen_batched = usage, batched
            spent.append(cost(usage, batched) or {})
            try:
                cand = parse(text)
            except Exception as e:
                cand = None
                note = f"JSON 을 읽을 수 없었다: {type(e).__name__} {e}"
                log(f"⚠️ {attempt}차 파싱 실패 — {note}")
                if attempt == 2:
                    bail(text, [note])
                    return 3
                continue
            # 틀부터 본다. 아래 수리 함수들(repair_links·normalize_links…)은
            # 문단이 {"ko":…,"en":…} 인 줄 알고 도므로, 모양이 어긋나 있으면
            # 검사기에 닿기도 전에 터진다. 실제로 그렇게 한 번 죽었다.
            shape = _shape_bad(cand)
            if shape:
                cand = None
                note = "\n".join(f"· {x}" for x in shape)
                log(f"⚠️ {attempt}차 틀이 어긋났다:\n{note}")
                if attempt == 2:
                    bail(text, shape)
                    return 3
                continue
        n_fixed = repair_links(cand)
        if n_fixed:
            log(f"· **이름**(코드) 형식 {n_fixed}곳을 링크로 고쳤다")
        n_brand = repair_brand(cand)
        if n_brand:
            log(f"· '코사이' {n_brand}곳을 'KOSAI' 로 고쳤다")
        dropped = normalize_links(cand, tickers)
        if dropped:
            log("· 확인되지 않은 종목 링크를 평문으로 바꿨다: " + ", ".join(dropped[:8]))
        n_sum = repair_summary(cand)
        if n_sum:
            log(f"· 요약 {n_sum}곳에서 링크·강조·글머리표를 벗겨 한 문단으로 이었다")
        # 1차는 설계대로 25% 로 본다. 2차는 30% 까지 눈감아 준다 — 발행이
        # 안 되는 것보다는 커버리지가 조금 긴 게 낫다. 그 위는 발행하지 않는다.
        # 소제목 길이 여유는 1차에도 준다 — 45자 하나로 $0.05 라도 더 쓸 이유가 없다.
        bad = validate(cand, strict_coverage=(attempt == 1), facts=facts,
                       strict_text=(attempt == 1), head_slack=HEAD_SLACK)
        if not bad:
            brief = cand
            break
        last_bad = bad
        note = "\n".join(f"· {x}" for x in bad)
        log(f"⚠️ {attempt}차 거부:\n{note}")
        if attempt == 2:
            bail(cand, bad)
            return 3

    n, ratio = measure(brief)
    c = cost(gen_usage, gen_batched)
    if c and len(spent) > 1:
        # usd 는 Opus 가 쓴 글 한 편의 값이고, 그날 실제로 쓴 돈은 usdAll 이다
        # (수리 호출이나 1차 실패분이 더해진다). 콘솔 청구와 맞춰 볼 때는 이쪽을 본다.
        c["attempts"] = len(spent)
        c["usdAll"] = round(sum(x.get("usd", 0) for x in spent), 4)
        if repaired:
            c["repaired"] = {"model": REPAIR_MODEL, "fields": repaired,
                             "usd": spent[-1].get("usd")}
    meta = {"model": MODEL, "batched": batched, "chars": n,
            "coverageRatio": round(ratio, 3), "usage": c,
            "generatedAt": facts["generatedAt"]}
    path = save(brief, facts, meta, out_dir)

    log(f"\n✅ {path}")
    log(f"   제목  {brief['title']['ko']}")
    log(f"   분량  {n:,}자 (목표 {LEN_WANT[0]:,}~{LEN_WANT[1]:,}) · "
        f"커버리지 {ratio*100:.0f}% (상한 {COVERAGE_CAP*100:.0f}%)")
    log(f"   섹션  " + " → ".join(s["id"] for s in brief["sections"]))
    um = used_materials(brief)
    same = len(set(um) & set(prev_mat)) if prev_mat else None
    log(f"   재료  {len(um)}/{len(MATERIALS)} ({' · '.join(um)})"
        + (f" · 어제와 겹침 {same}" if same is not None else ""))
    if c:
        log(f"   비용  입력 {c['inputTokens']:,} / 출력 {c['outputTokens']:,} 토큰 · "
            f"${c['usd']} (약 {c['krw']:,}원)" + ("  ← 배치 반값" if batched else ""))
        if c.get("repaired"):
            log(f"   수리  {REPAIR_MODEL} 가 {repaired}곳 · ${c['repaired']['usd']}"
                f" → 그날 합계 ${c['usdAll']}")
        elif c.get("attempts", 1) > 1:
            log(f"   전체  {c['attempts']}회 생성 · ${c['usdAll']} — 1차는 버렸다")
    if n < LEN_WANT[0] or n > LEN_WANT[1]:
        log("   ⚠️ 목표 분량을 벗어났다(통과 범위 안이라 발행은 한다)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
