#!/usr/bin/env python3
"""
KOS ai — 업종(섹터) AI 분석 생성기 (Batch API 전용 · Sonnet)

각 업종에 대해 개요·구조(가치사슬)·최근동향·전망·리스크를 한/영으로 생성해
data/sectors.js (window.KOS_SECTORS) 를 만든다. 업종별 상위 종목·집계 통계와
작성 기준일, 상위 종목의 최근 분기 실적(공시 확정치 · 기업 리포트 자료)을
프롬프트에 제공한다. 종목 리포트 배치 로직을 일부 재사용.

■ 2026-10-08 보완 — 근거 숫자 · 시점 · 출처

  9월 4일 판 30편을 전수로 보니 셋이 약했다.
    · 재료가 업종 이름 · 상위 종목 이름뿐이라 우리가 가진 공시 실적을 쓰지 못했다
      (6편은 금액 · 비율 수치가 하나도 없었다).
    · 작성 기준일을 주지 않아, 이미 끝난 분기를 '예상'으로 쓴 문장이 나왔다
      (반도체 '최근 동향' — 9월 4일 작성인데 2분기 가격을 전망으로 썼다).
    · 7편은 웹 검색 인용이 0건인데 화면에는 '웹 검색 참고'라고 나갔다.
  그래서 기준일과 상위 종목의 최근 분기 실적을 재료로 주고, 웹 검색을 반드시 하게
  하고, 저장 전에 리포트와 같은 글자 검사(check_report_text)를 돌린다. 출처가 0건인
  글은 다시 쓰게 하되 마지막 회차는 받는다 — 같은 이유로 계속 버리면 그 업종이
  옛 글에 갇히고 돈만 나간다. 그런 글은 화면이 '웹 검색 참고'를 빼고 보여 준다
  (build_industry_comp).

■ Batch API 만 쓴다 (예외 없음)

  같은 모델·같은 프롬프트라도 Batch 로 보내면 요금이 절반이다. 30개 업종을
  한 번에 내는 일은 급할 이유가 없으므로 즉시 응답에 두 배를 낼 까닭이 없다.

  '그렇게 하기로 한다' 는 약속은 언젠가 새어 나간다. 그래서 client() 에서
  즉시 호출 창구(messages.create)를 막아 둔다. 실수로 부르면 그 자리에서
  멈추고, 조용히 두 배를 물지 않는다.

■ 언제 도는가

  분기 1회, 정기보고서 마감 한 주 뒤.

    사업보고서   3월 31일  →   4월  7일
    1분기        5월 15일  →   5월 21일
    반기         8월 14일  →   8월 21일
    3분기       11월 14일  →  11월 21일

  마감 당일로 붙이지 않는다. 그날은 제출이 몰려 데이터가 다음 날에야
  정리되고, 업황 해설도 아직 안 나와 검색할 것이 없다.

모드: submit / collect / auto(기본)
환경변수: ANTHROPIC_API_KEY(필수), REPORT_MODEL(기본 claude-sonnet-5), SECTOR_FORCE, BATCH_MAX_WAIT_SEC
"""
import os
import re
import sys
import json
import time
import hashlib
import datetime
from collections import Counter, defaultdict
from pathlib import Path

import number_spacing       # 금액 표기 통일(79조3,187억원 → 79조 3,187억원)

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

import generate_reports as g  # extract_text / parse_report / collect_sources 재사용
import check_report_text as C  # clean_markup · defects · 검토(review) — 리포트 본문과 같은 기준
import fix_hanja               # 한자 → 한글(리포트와 같은 저장 전 정리)

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
REPORTS_V2 = ROOT / "data" / "reports_v2"   # 기업 리포트 — quant.quarterly 가 공시 확정 분기 실적이다
OUT_JS = ROOT / "data" / "sectors.js"
STATE = ROOT / "data" / "sector_batch_state.json"

MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-5")
FORCE = os.getenv("SECTOR_FORCE", "") == "1"
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "4800"))
# 걸러진 것을 다시 만드는 횟수(1차 포함). 회차마다 대상이 줄어든다.
ROUNDS = max(1, int(os.getenv("SECTOR_ROUNDS", "3")))

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3,
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log

SYSTEM = (
    "너는 한국 증시 섹터(업종) 애널리스트다. 주어진 업종의 한국 상장사들을 바탕으로 "
    "투자 참고용 업종 분석을 작성한다. 매수/매도·목표주가 등 투자권유 표현은 쓰지 않는다. "
    "수치는 확인된 것만 쓰고 과장·날조하지 않는다. 전문 애널리스트 톤.\n\n"
    "[집계]로 주는 수치(업종 시가총액 합계·전체 시장 비중·상장 종목 수)와 "
    "[시총 상위 종목]의 시총 금액은 문장에 그대로 옮기지 않는다. 이 값들은 매 거래일 "
    "바뀌고 화면이 본문 위에서 최신 값을 따로 보여 주므로, 문장에 박으면 그날부터 "
    "화면과 본문이 서로 다른 숫자를 말하게 된다. 규모는 '관계'로 서술한다.\n"
    "  (X) 업종 시가총액은 약 2786.3조원으로 전체 시장의 48.8%를 차지한다\n"
    "  (O) 전체 시장 시가총액의 절반에 가까운 비중을 차지하는 최대 업종이다\n"
    "  (X) 상장 종목은 119개로 시가총액 합계는 약 47.5조원이다\n"
    "  (O) 종목 수는 많지만 개별 규모는 작아 시장 비중은 1%를 밑도는 업종이다\n"
    "개별 기업의 점유율·실적·수주처럼 공시나 검색으로 확인한 값은 수치로 써도 된다.\n\n"
    "[상위 종목 최근 분기 실적]은 공시 확정치다. 매 거래일 바뀌는 값이 아니므로 최근 동향의 근거로 "
    "수치를 인용해도 된다. 그 자료를 '제공된 자료'·'주어진 데이터'처럼 받은 자료로 가리키지 말고 "
    "'2분기 공시 기준'처럼 출처로 말한다.\n"
    "[작성 기준일]보다 앞서 끝난 기간(지난 분기·지난해)은 이미 나온 결과로 쓴다. 그 기간을 "
    "'예상된다'·'전망이다'처럼 앞으로의 일로 쓰지 않는다. 검색 결과가 그 기간을 아직 전망으로 "
    "다루고 있으면 실제 결과를 확인해 쓰고, 확인하지 못하면 그 내용은 쓰지 않는다.\n"
    "최근 업황은 반드시 웹 검색으로 확인하고, 검색으로 확인한 사실은 그 결과를 인용해 쓴다.\n\n"
    # 2026-10-09 — 10월 8일 판 30편을 사람이 읽으니 아래가 나왔다(사장이 크게 질책했다). 저장 전 검토가 다시 보지만
    # 처음부터 쓰지 않게 지시한다.
    "문장은 한 문장에 한 사실로 쓴다. 검색 결과의 문장을 이어 붙여 주어가 둘이 되거나 같은 말을 되풀이하지 않는다\n"
    "  (X) 174,000㎥급 LNG운반선 가격은 17만 4000m3급 LNG선의 신조선가는 척당 …\n"
    "  (O) 17만 4,000㎥급 LNG운반선의 신조선가는 척당 2억 4,850만달러로 …\n"
    "[상위 종목 최근 분기 실적]에 있는 회사의 수치는 그 값 그대로 쓴다. 여러 회사를 묶어 말할 때('대부분' · '60~90%대' ·\n"
    "'두 자릿수' · '70% 넘게')는 묶은 회사의 실제 값이 모두 그 안에 들 때만 쓰고, 아니면 회사별 값이나 실제 범위로 쓴다.\n"
    "  (X) 주요 기업 대부분이 영업이익이 60~90%대로 급증했다   ← 실제는 37.2~113.0%\n"
    "  (O) 영업이익 증가율은 HD현대일렉트릭 37.2%에서 대한전선 113.0%까지 분포했다\n"
    "적자 회사를 이익이 늘어난 것처럼 쓰지 않는다. 요약(lead) · 본문 · 위험 요인이 같은 대상을 서로 반대로 말하지 않게 한다.\n"
    "회사의 사업은 [회사 설명]에 맞게 쓴다. 업종 분류상 함께 묶였지만 사업이 다른 회사(예: 전기장비 업종의 의료기기 회사)는\n"
    "그 사업으로 소개하고, 영어 문장의 회사명은 [회사 설명]의 영문명을 쓴다.\n"
    "상대 시점(지난달 · 이번 주 · 어제 · 오늘 · 다음 달)을 쓰지 않는다 — 글은 몇 달 동안 걸려 있으므로 '2026년 9월'처럼 날짜로\n"
    "쓴다. 검색한 기사의 날짜를 확인해, [작성 기준일]보다 오래된 기사의 계획 · 전망은 결과를 확인해 쓰거나 빼고, 이미 끝난\n"
    "일(이미 가동 중인 공장 · 지난 분기 일정)을 앞으로의 일로 쓰지 않는다.\n"
    "상장 종목 수는 어림수('170여 개' · '200개를 웃돈다')로도 쓰지 않는다. 1,000 이상의 수에는 쉼표를 쓴다(9,000억원).\n"
    "한국어 문장에 영어 낱말(Phase · niche)이나 과장 표현(폭증 · 폭발적 · 역대급)을 섞지 않는다. 영어 문장에는 같은 칸\n"
    "한국어의 수치를 빠짐없이 옮긴다."
)

# en 자리를 ""로 비워 보였더니 모델이 템플릿 그대로 빈 문자열을 내놓는 일이 있었다
# (2026-08 생성분에서 조선·2차전지의 본문 영어가 통째로 비었다). 그래서 en 에도
# 무엇을 쓸지 명시하고, 비우지 말라는 규칙을 따로 둔다.
SCHEMA = """다음 JSON 스키마로만 출력하세요. 모든 텍스트는 {"ko":"한국어","en":"영어"} 형식입니다.
===JSON_START===
{
  "lead":     {"ko":"업종 한 줄 요약(매수/매도 표현 금지)","en":"same, in English"},
  "overview": {"ko":"업종 개요: 어떤 산업이고 한국 증시에서의 위치·특성 (4~6문장)","en":"same, in English"},
  "structure":{"ko":"산업 구조·가치사슬: 밸류체인 단계와 대표 종목 배치, 집중도 (4~6문장)","en":"same, in English"},
  "trends":   {"ko":"최근 업황·동향: 실적/수요/사이클 흐름 (4~6문장)","en":"same, in English"},
  "outlook":  {"ko":"향후 전망: 성장 동인과 관전 포인트 (4~6문장)","en":"same, in English"},
  "risks":    [ {"title":{"ko":"제목","en":"title in English"},
                 "body":{"ko":"2~3문장","en":"same, in English"}}, ... 3개 ]
}
===JSON_END===
규칙
- 마커 사이에 JSON만. 한국어는 자연스럽게, 영어는 전문 번역체로.
- 문장은 반드시 끝맺을 것. 분량이 부담되면 문장 수를 줄이되 중간에 끊지 않는다.
- 한자를 섞지 말 것(예: '고객사向' → '고객사 대상', '美' → '미국').

★ 마지막으로 반드시 지킬 것 — 영어를 비우지 말 것

  "en" 자리는 하나도 빠짐없이 채운다. lead·overview·structure·trends·outlook
  다섯 개와 risks 세 개의 title·body 까지, 총 16개 자리가 전부 영어 문장이어야
  한다. "same, in English" 는 무엇을 쓰라는 지시이지 그대로 옮겨 적을 값이
  아니며, 빈 문자열("")도 안 된다.

  분량이 부담되면 한국어 쪽 문장 수를 줄여라. 영어를 비우는 것보다 양쪽을
  짧게 쓰는 편이 낫다 — 영어가 비면 영어 화면에 한국어가 그대로 노출된다.

  출력을 끝내기 전에 "en" 이 빈 자리가 하나라도 있는지 세어 보고, 있으면
  채운 뒤 내보낼 것."""


class BatchOnly(RuntimeError):
    """즉시 호출 창구를 부르려 했다. Batch 로만 보내기로 한 규칙을 어긴 것이다."""


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음"); sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    # 즉시 호출 창구를 실제로 막는다. 주석으로 "Batch 만 쓴다" 고 적어 두는
    # 것과 부를 수 없게 만드는 것은 다르다 — 앞의 것은 다음에 고치는 사람이
    # 안 읽으면 그대로 새고, 새더라도 요금이 두 배가 될 뿐 화면은 멀쩡해서
    # 아무도 모른다. 여기서 막으면 그 자리에서 멈춘다.
    def _blocked(*_a, **_kw):
        raise BatchOnly(
            "업종 분석은 Batch API 로만 보낸다(요금 절반). "
            "messages.create 가 아니라 messages.batches.create 를 쓸 것.")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked
    return cl


def load_sectors():
    raw = STOCKS_JS.read_text(encoding="utf-8")
    stocks = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]
    total = sum(s.get("mcap", 0) or 0 for s in stocks)
    by = defaultdict(list)
    for s in stocks:
        cats = s.get("categories") or [s.get("sector", "기타")]
        for c in cats:
            by[c].append(s)
    out, tops = {}, {}
    for sec, lst in by.items():
        mc = sum(s.get("mcap", 0) or 0 for s in lst)
        top = sorted(lst, key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:12]
        tops[sec] = top
        out[sec] = {
            "count": len(lst), "mcap": round(mc, 1),
            "weight": round(mc / total * 100, 1) if total else 0,
            "top": [(t["name"], t.get("mcap", 0) or 0) for t in top],
        }
    # 상위 종목의 최근 분기 실적 — 기업 리포트 자료(quant · 공시 확정치)에서. 돈이 들지 않는다.
    # '가장 최근 분기' 는 상위 종목들의 마지막 분기 가운데 가장 많은 것(지금 2026Q2)이다.
    # 그보다 늦은 이름의 분기가 있는 회사는 결산월이 달라 회계 분기 이름이 앞서는 것이라 뺀다
    # (금비 · 풍강 등 '2026Q3' — 달력으로는 아직 공시될 수 없는 분기다).
    qs = {}
    for top in tops.values():
        for t in top:
            tk = t.get("ticker")
            if tk and tk not in qs:
                qs[tk] = _quant(tk)
    lasts = [r[-1]["q"] for r in (_rows(q) for q in qs.values()) if r]
    latest = Counter(lasts).most_common(1)[0][0] if lasts else None
    for sec, top in tops.items():
        out[sec]["latestQ"] = latest
        out[sec]["fin"] = [x for x in (_fin_line(t["name"], qs.get(t.get("ticker")), latest,
                                                 no_rev=t.get("sector") in NO_REV) for t in top) if x]
    return out


# 매출 칸이 매출이 아닌 업종(영업수익 · 일부 계정) — 실적 줄에 매출을 싣지 않는다(_fin_line).
NO_REV = ("금융", "보험")


def _quant(ticker):
    """기업 리포트의 quant(공시 확정 재무). 없거나 깨졌으면 None."""
    try:
        d = json.loads((REPORTS_V2 / f"{ticker}.json").read_text(encoding="utf-8"))
    except Exception:
        return None
    q = d.get("quant") if isinstance(d, dict) else None
    return q if isinstance(q, dict) else None


def _rows(q):
    """분기 실적 줄 가운데 매출이나 영업이익이 있는 것(시간순)."""
    return [x for x in ((q or {}).get("quarterly") or [])
            if isinstance(x, dict) and re.fullmatch(r"\d{4}Q[1-4]", str(x.get("q") or ""))
            and (x.get("rev") is not None or x.get("op") is not None)]


def _won(v):
    """원 → '74조 5,663억원' · '2,078억원' · '8,500만원' — 리포트 금액 표기(맞춤법 제44항)와 같은 꼴."""
    a = abs(v)
    eok = round(a / 1e8)
    sign = "-" if v < 0 else ""
    if eok >= 10000:
        jo, rest = divmod(eok, 10000)
        return sign + (f"{jo:,}조 {rest:,}억원" if rest else f"{jo:,}조원")
    if a >= 1e8:
        return sign + f"{eok:,}억원"
    return sign + f"{round(a / 1e4):,}만원"


def _qtext(label):
    """'2026Q2' → '2026년 2분기'"""
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(label or ""))
    return f"{m.group(1)}년 {m.group(2)}분기" if m else str(label or "")


def _chg(cur, prev, op=False):
    """전년 같은 분기와 견준 말. 증감률은 둘 다 양수일 때만 — 적자가 끼면 비율이 뜻을 잃어 영업이익만 말로 쓴다."""
    if cur is None or prev is None:
        return ""
    if cur > 0 and prev > 0:
        return f"전년 동기 대비 {(cur / prev - 1) * 100:+,.1f}%"
    if not op:
        return ""
    if prev <= 0 < cur:
        return "흑자 전환"
    if prev > 0 >= cur:
        return "적자 전환"
    if prev < 0 and cur < 0:
        return "적자 지속"
    return ""


def _fin_line(name, q, latest, no_rev=False):
    """상위 종목 한 곳의 최근 분기 실적 한 줄 — '삼성전자(연결): 2026년 2분기 매출 …(전년 동기 대비 +5.1%), 영업이익 …'.
    자료가 없거나, 마지막 분기 이름이 latest 보다 늦은 회사(결산월이 다르다)는 None.
    no_rev 면 매출을 싣지 않는다 — 금융 · 보험의 '매출' 칸은 영업수익이나 일부 계정이라(신한지주 9,164억원 ·
    영업이익 2조 4,763억원) 매출로 읽히면 틀린 문장이 된다. 다른 업종도 매출이 영업이익보다 작으면 같은 경우라 뺀다."""
    rows = _rows(q)
    if not rows or not latest or rows[-1]["q"] > latest:
        return None
    cur = rows[-1]
    y, n = cur["q"].split("Q")
    prev = next((x for x in rows if x["q"] == f"{int(y) - 1}Q{n}"), {})
    basis = str(q.get("fs_basis") or "").split("(")[0].strip()          # '연결' · '별도'
    parts = []
    if cur.get("rev") is not None and not no_rev and not (cur.get("op") is not None and 0 < cur["rev"] < cur["op"]):
        c = _chg(cur["rev"], prev.get("rev"))
        parts.append(f"매출 {_won(cur['rev'])}" + (f"({c})" if c else ""))
    if cur.get("op") is not None:
        c = _chg(cur["op"], prev.get("op"), op=True)
        amt = f"영업이익 {_won(cur['op'])}" if cur["op"] >= 0 else f"영업손실 {_won(-cur['op'])}"
        parts.append(amt + (f"({c})" if c else ""))
    return f"{name}{f'({basis})' if basis in ('연결', '별도') else ''}: {_qtext(cur['q'])} " + ", ".join(parts)


def _day(as_of):
    """'2026-10-08 18:20' → '2026년 10월 8일'"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", as_of or "")
    return f"{int(m.group(1))}년 {int(m.group(2))}월 {int(m.group(3))}일" if m else ""


_META = None


def _stock_meta():
    """종목 이름 → (종목코드, 영문명, 업종). 시세 자료에서 한 번만 읽는다."""
    global _META
    if _META is None:
        try:
            raw = STOCKS_JS.read_text(encoding="utf-8")
            st = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]
        except Exception:
            st = []
        _META = {s["name"]: (s.get("ticker"), s.get("name_en") or "", s.get("sector") or "") for s in st if s.get("name")}
    return _META


def _first_sentence(ticker):
    """기업 리포트 사업 칸의 첫 문장(160자 안) — 회사가 무엇을 하는 곳인지 한 줄. 없으면 ''."""
    try:
        d = json.loads((REPORTS_V2 / f"{ticker}.json").read_text(encoding="utf-8"))
        b = ((d.get("business") or {}).get("ko") or "").strip()
    except Exception:
        return ""
    s = re.split(r"(?<=[.!?])\s+", b)[0] if b else ""
    return s if len(s) <= 160 else s[:157] + "…"


def _clean_en(s):
    """영문명을 화면과 같은 꼴로 — check_report_text.clean_en(리포트 검토와 같은 함수)."""
    return C.clean_en(s)


def company_lines(names):
    """[회사 설명] 줄 — '삼성전자(Samsung Electronics) · 업종 분류 반도체 · 삼성전자는 …'.

    2026-10-08 판에서 회사의 사업을 틀리게 쓴 문장이 여럿 나왔다 — 콘크리트 펌프카 회사(전진건설로봇)를 '건설 중장비용 로봇',
    핀테크 회사(더즌)를 '알뜰폰 통신사', 중형 조선소(대한조선)를 '블록 협력사', 협동로봇 회사(뉴로메카)를 '소프트웨어' 로.
    영문명도 'Yujin Robotics'(유일로보틱스 — 유진로봇은 다른 회사다) · 'Daehan Cable'(대한전선) 처럼 지어냈다. 업종 분류만 보고
    짐작하지 않게, 우리가 가진 기업 리포트의 첫 문장과 공시 영문명을 같이 준다(돈이 들지 않는다)."""
    meta = _stock_meta()
    out = []
    for nm in names:
        m = meta.get(nm)
        if not m:
            continue
        tk, en, sec = m
        desc = _first_sentence(tk) if tk else ""
        out.append(f"  - {nm}({_clean_en(en) or '영문명 없음'}) · 업종 분류 {sec or '—'}" + (f" · {desc}" if desc else ""))
    return out


def mentioned(rep, extra=()):
    """본문에 나온 상장사 이름(긴 이름부터) + extra. 두 글자 이름은 앞이 한글이 아닐 때만 — '투자 대상' 의 '대상' 을 줄인다."""
    text = " ".join(v.get("ko", "") for v in C._flat_fields(rep).values())
    seen = list(dict.fromkeys(extra))
    for nm in sorted(_stock_meta(), key=len, reverse=True):
        if nm in seen or len(nm) < 2:
            continue
        i = text.find(nm)
        if i < 0 or (len(nm) == 2 and i > 0 and "가" <= text[i - 1] <= "힣"):
            continue
        seen.append(nm)
        text = text.replace(nm, "□")
    return seen[:30]


def build_prompt(sec, info, as_of=None):
    tops = "\n".join(f"  - {nm} (시총 {number_spacing.mcap_text(mc)})" for nm, mc in info["top"])
    day, lq, fin = _day(as_of), info.get("latestQ"), info.get("fin") or []
    head = (f"[작성 기준일] {day}" + (f" · 공시로 확인되는 가장 최근 분기는 {_qtext(lq)}" if lq else "") + "\n") if day else ""
    fins = ("[상위 종목 최근 분기 실적 · 공시 확정치, 수치 인용 가능]\n"
            + "\n".join(f"  - {x}" for x in fin) + "\n\n") if fin else ""
    comp = company_lines([nm for nm, _ in info.get("top") or []])
    comps = ("[회사 설명 · 각 회사의 사업(기업 리포트 첫 문장) · 영문명 — 회사 소개와 영어 회사명은 이것에 맞출 것]\n"
             + "\n".join(comp) + "\n\n") if comp else ""
    return (
        head
        + f"[업종] {sec}\n"
        f"[집계 · 참고용, 본문에 수치로 옮기지 말 것] 상장 종목 {info['count']}개 · "
        f"업종 시가총액 합계 약 {info['mcap']}조원 (전체 시장의 약 {info['weight']}%)\n"
        f"[시총 상위 종목 · 종목명은 쓰되 시가총액 금액은 본문에 옮기지 말 것]\n{tops}\n\n"
        + fins
        + comps
        + "위 업종에 대해 한국 증시 관점의 업종 분석을 작성하세요. 위 상위 종목들을 적절히 언급하고, "
        "반드시 웹 검색으로 최근 업황을 확인하세요.\n\n" + SCHEMA
    )


# 지난 실행에서 걸러진 업종을 적어 두는 파일.
RETRY = ROOT / "data" / "sector_retry.json"


def load_retry():
    """지난 실행에서 걸러진 업종. 파일이 없거나 깨졌으면 빈 목록."""
    try:
        return set(json.loads(RETRY.read_text(encoding="utf-8")).get("failed") or [])
    except Exception:
        return set()


def save_retry(failed, as_of):
    """이번에 걸러진 업종을 적어 둔다. 없으면 파일을 치운다."""
    if failed:
        RETRY.write_text(json.dumps({"at": as_of, "failed": sorted(failed)},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    elif RETRY.exists():
        RETRY.unlink()


def submit(cl, as_of, force=None):
    force = FORCE if force is None else force
    sectors = load_sectors()
    existing = load_existing()
    # 걸러진 업종을 다시 대상에 넣는다.
    #
    # defects() 가 잡아낸 업종은 저장되지 않으므로 옛 글이 그대로 남는다.
    # 그런데 대상을 고르는 조건이 's not in existing'(없는 업종) 뿐이라,
    # 옛 글이 남아 있는 그 업종은 다음 실행에서도 건너뛰어졌다 — 영영 낡은
    # 채로 갇힌다. FORCE 로 전부 다시 만드는 길밖에 없었고, 그건 멀쩡한
    # 스물몇 개까지 다시 만드는 것이라 돈이 그만큼 더 든다.
    #
    # 2026-09-04 실행에서 30개 중 11개가 걸러졌다(영문이 비거나 글자가 깨진
    # 출력). 그때 이 목록이 없어서 11개가 8월 글 그대로 남았다.
    retry = load_retry()
    targets = [s for s in sectors if force or s not in existing or s in retry]
    if retry and not force:
        log(f"- 지난번에 걸러진 {len(retry)}개를 다시 만든다: {', '.join(sorted(retry))}")
    # '기타'는 업종 분석 의미가 적어 제외
    targets = [s for s in targets if s != "기타"]
    log(f"## 업종 분석 batch 제출 — 대상 {len(targets)}개 / 전체 {len(sectors)}개 · 모델 {MODEL}")
    if not targets:
        log("- 생성할 업종 없음(모두 보유). 종료."); return None
    reqs = []
    for sec in targets:
        reqs.append(Request(
            custom_id=_cid(sec),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=24000,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"}, tools=TOOLS,
                messages=[{"role": "user", "content": build_prompt(sec, sectors[sec], as_of)}],
            )))
        log(f"  · 준비 {sec} ({sectors[sec]['count']}종목)")
    batch = cl.messages.batches.create(requests=reqs)
    cid_map = {_cid(s): s for s in targets}
    if len(cid_map) != len(targets):                 # sha1 이 겹칠 일은 없지만, 겹치면 업종이 조용히 사라진다
        log("❌ custom_id 가 겹쳤다 — 중단"); sys.exit(1)
    # 프롬프트에 넣어 준 집계를 그대로 적어 둔다. 회수할 때 '이 숫자가 본문에
    # 박혔는지' 를 보는데, 그때 시세를 다시 읽으면 값이 이미 움직여 있어서
    # 정작 박힌 숫자를 놓친다(실제로 8월 생성분 4개가 그렇게 새 나갔다).
    agg = {s: sectors[s] for s in targets}
    STATE.write_text(json.dumps({"batch_id": batch.id, "created": as_of, "model": MODEL,
                                 "cid_map": cid_map, "agg": agg},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건)")
    return batch.id


def _cid(sec):
    """custom_id 는 영숫자·언더스코어만 쓴다. 업종 이름은 한글이라 못 쓴다.

    파이썬의 hash() 를 쓰고 있었는데 그건 실행마다 값이 바뀐다(해시 무작위화).
    제출·회수를 따로 돌리면 cid_map 을 파일에 적어 두므로 동작은 했지만,
    같은 업종이 실행마다 다른 번호를 받아 로그를 맞대 볼 수 없었다.
    sha1 은 언제 돌려도 같은 값이 나온다.
    """
    return "sec_" + hashlib.sha1(sec.encode("utf-8")).hexdigest()[:16]


def poll(cl, bid):
    waited = 0
    while waited < MAX_WAIT:
        b = cl.messages.batches.retrieve(bid)
        rc = b.request_counts
        log(f"  · {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
        if b.processing_status == "ended":
            return True
        time.sleep(60); waited += 60
    return False


def load_existing():
    if OUT_JS.exists():
        try:
            raw = OUT_JS.read_text(encoding="utf-8")
            return json.loads(raw[raw.find("{"): raw.rfind("}") + 1]).get("sectors", {}) or {}
        except Exception:
            return {}
    return {}


BODY_KEYS = ("lead", "overview", "structure", "trends", "outlook")
_ENDS = re.compile(r'[.!?…"”\')\]]\s*$')


def _num_variants(v):
    """모델이 같은 수를 적을 수 있는 여러 모양. 2786.3 → 2786.3 · 2,786.3 · 2786 …"""
    out = {f"{v:g}"}
    s = f"{v:g}"
    if "." in s:                                   # 소수를 떼고 적기도 한다
        out.add(s.split(".")[0])
    for x in list(out):
        if len(x) > 3 and x.isdigit():             # 천 단위 쉼표를 넣기도 한다
            out.add(f"{int(x):,}")
    return {x for x in out if x and x != "0"}


# 화면이 본문 위에서 실시간으로 다시 계산해 보여 주는 집계 수치.
# 문장에 그대로 박히면 그날부터 위아래가 서로 다른 숫자를 말한다.
_LIVE = (
    ("업종 시가총액 합계", "mcap", r"\s*조", r"(시가총액|시총|시장\s*규모)"),
    ("전체 시장 비중", "weight", r"\s*%", r"(비중|차지|전체\s*시장|시장의|시장\s*전체)"),
    ("상장 종목 수", "count", r"\s*개", r"(종목|상장사|기업)"),
)


def live_number_hits(rep, info):
    """프롬프트에 넣어 준 집계 수치가 본문에 그대로 옮겨졌는지 본다.

    우리가 준 값이 무엇인지 아니까 그 값만 찾는다 — '숫자가 있으면 잡는다' 가
    아니다. 개별 기업의 점유율·실적 수치는 확인된 정보라 그대로 둬야 한다.

    숫자 옆(앞뒤 30자)에 '시가총액'·'비중'·'종목' 같은 말이 있을 때만 잡는다.
    같은 숫자가 우연히 다른 뜻으로 나올 수 있기 때문이다(영업이익률 0.8% 등).

    숫자는 온전한 수로만 찾는다 — 앞에 다른 숫자가 붙어 있으면 다른 수다. 비중 '2' 를
    찾다가 '매출 비중 12%' 의 '2%' 를 잡으면 멀쩡한 글을 버리고 다시 쓰게 된다(2026-10-08 ·
    상위 종목 분기 실적을 재료로 넣으면서 본문의 숫자가 늘었다).
    """
    if not info:
        return []
    body = " ".join(
        (rep.get(k) or {}).get(lang, "")
        for k in BODY_KEYS for lang in ("ko", "en")
    ) + " " + " ".join(
        ((r or {}).get("body") or {}).get(lang, "")
        for r in (rep.get("risks") or []) for lang in ("ko", "en")
    )
    hits = []
    for label, key, unit, near in _LIVE:
        val = info.get(key)
        if not val:
            continue
        for var in _num_variants(val):
            for m in re.finditer(r"(?<![\d.,])" + re.escape(var) + unit, body):
                a, b = max(0, m.start() - 30), m.end() + 30
                if re.search(near, body[a:b]):
                    hits.append(f"{label}({var}) 본문에 박힘")
                    break
            else:
                continue
            break
    return hits


# 저장을 막는 리포트 검사 규칙(위험 등급은 모두) — 2026-10-09 상대 시점 · 영어 낱말을 더했다(10월 8일 판의 '지난달에만' ·
# 'Phase에 진입' · 'niche 영역'). 리포트 화면용 품질 규칙(ROE · TTM · 말투 · 주당지표)은 업종 분석에 걸지 않는다.
GATE_RULES = ("hanja", "meta", "hangul_en", "stale_time", "en_word")

# 상장 종목 수 — 어림수도 매 거래일 바뀌는 값이고 화면이 본문 위에서 정확한 수를 보여 준다. 10월 8일 판에 '170여 개' ·
# '200개를 웃돌' · '20개에 못 미치는' · '100개를 넘지만' · 'roughly 170 listed companies' 가 있었다(live_number_hits 는 준 값과
# 똑같은 수만 봐서 놓쳤다). 업계 집계('섬유패션 상장사 76개사')처럼 '개사' 로 끝나는 바깥 통계는 뺀다.
_LISTED_KO = re.compile(r"상장\s*(?:종목|기업|회사|사)\s*(?:수(?:는|가)?|은|는|이|가)(?![가-힣])\s*[^.\n]{0,12}?\d[\d,]*\s*(?:여\s*)?개(?!사)"
                        r"|(?<!상위 )(?<![~∼\d,])[1-9]\d[\d,]*\s*(?:여\s*)?개(?!사)(?:의)?\s*(?:상장\s*)?(?:종목|상장사)"
                        r"|(?<!상위 )(?<![~∼\d,])[1-9]\d[\d,]*\s*(?:여\s*)?개(?:를|가|에)?\s*(?:웃도는|넘는|넘어서는|밑도는|못 미치는|안팎의|가량의)"
                        r"\s*(?:상장\s*)?(?:종목|상장사)")
_LISTED_EN = re.compile(r"\b\d{2,4}\+?\s+listed\s+(?:companies|names|stocks|firms|issuers)"
                        r"|listed\s+(?:companies|names|stocks|firms)\s+(?:exceeds?|tops?|totals?|numbers?)\s+"
                        r"(?:roughly\s+|about\s+|over\s+|more than\s+|nearly\s+)?\d{2,4}", re.I)


def listed_count_hits(rep):
    """본문에 상장 종목 수를 수치로 쓴 자리."""
    hits = []
    for path, v in C._flat_fields({k: rep.get(k) for k in BODY_KEYS + ("risks",) if rep.get(k)}).items():
        for lang, pat in (("ko", _LISTED_KO), ("en", _LISTED_EN)):
            m = pat.search(v.get(lang) or "")
            if m:
                hits.append(f"상장 종목 수({path}.{lang}) {m.group(0)!r}")
    return hits


def defects(rep, message=None, info=None, sources=None):
    """저장하면 안 되는 결함 목록. 비어 있으면 정상.

    2026-08 생성분에서 실제로 나온 것들이다. 한 번 저장되면 다음 분기까지 그대로
    사이트에 걸리므로 여기서 거른다. 걸러진 업종은 save_retry 가 적어 두고
    다음 실행이 그것만 다시 만든다 — 그 목록이 없던 동안에는 옛 글이 남아
    있다는 이유로 '이미 있는 업종' 으로 분류돼 영영 건너뛰어졌다.
      · 영어 본문이 통째로 빈 채로 저장 → 영어 모드에서 한국어가 그대로 노출
      · max_tokens 로 잘려 json_repair 가 문장 중간을 닫아버림
      · 인코딩이 깨진 자리(U+FFFD)가 본문에 박힘

    2026-10-08 부터 둘을 더 본다.
      · 글자 결함 · 금지 표현 — 리포트 본문과 같은 검사(check_report_text: 깨진 글자 · 태그 ·
        받은 자료를 가리키는 말 · 한자 · 투자 권유 · 가치 단정 · 영문 속 한글). 검사 묶음의 전수
        검사가 data/sectors.js 도 보는데, 생성기는 저장 전에 보지 않아 결함이 있으면 사이트에
        먼저 걸릴 수 있었다.
      · 출처 0건 — sources 를 넘기면(목록) 웹 검색 인용이 하나도 없는 글을 거른다.
        None 이면 보지 않는다(마지막 회차 · collect 의 strict_sources 참고).
    """
    out = []
    if getattr(message, "stop_reason", None) == "max_tokens":
        out.append("max_tokens 로 잘림")
    if not rep.get("risks") or len(rep["risks"]) < 3:
        out.append("리스크 3개 미만")

    def check(label, o):
        for lang in ("ko", "en"):
            s = (o or {}).get(lang, "")
            if not (s or "").strip():
                out.append(f"{label}.{lang} 빔")
            elif not _ENDS.search(s):
                out.append(f"{label}.{lang} 문장 안 끝남")

    for k in BODY_KEYS:
        check(k, rep.get(k))
    for i, r in enumerate(rep.get("risks") or []):
        check(f"risks[{i}].body", (r or {}).get("body"))
        for lang in ("ko", "en"):
            if not ((r or {}).get("title") or {}).get(lang, "").strip():
                out.append(f"risks[{i}].title.{lang} 빔")
    if "�" in json.dumps(rep, ensure_ascii=False):
        out.append("깨진 문자(U+FFFD)")
    out += live_number_hits(rep, info)
    out += listed_count_hits(rep)
    for h in C.check(_as_report(rep)):
        if h["level"] == "위험" or h["rule"] in GATE_RULES:
            out.append(f"글자 결함 {h['rule']}({_FROM_REPORT.get(h['section'], h['section'])}) {h['match']!r}")
    if sources is not None and not sources:
        out.append("출처 0건(웹 검색 인용 없음)")
    return out


# 리포트 본문 검사(check_report_text.check)는 리포트의 칸 이름으로 훑는다 — 업종 분석의 개요 · 구조 · 동향을 리포트 칸에
# 옮겨 넣어 같은 검사를 다 받게 한다(옮기지 않으면 요지 · 전망 · 리스크만 훑는다). 걸러 내는 것은 위험 등급(투자 권유 ·
# 가치 단정 · 목표주가 인용 조건 · 태그 · 깨진 글자)과 한자 · 받은 자료 언급 · 영문 속 한글 — 리포트 화면용 품질 규칙
# (ROE · TTM · 말투 · 주당지표 수치)은 업종 분석에 걸지 않는다(금융 업종의 'ROE' 같은 말이 다시 쓰기를 부른다).
_AS_REPORT = {"lead": "lead", "overview": "business", "structure": "industry", "trends": "earnings",
              "outlook": "outlook", "risks": "risks"}
_FROM_REPORT = {v: k for k, v in _AS_REPORT.items()}


def _as_report(rep):
    return {_AS_REPORT[k]: v for k, v in (rep or {}).items() if k in _AS_REPORT}


def clean(o):
    """태그 · 인용 표시 · 마크다운을 지운다(감싼 글은 남긴다) — 리포트와 같은 저장 전 정리(clean_markup).
    결정적이라 돈이 들지 않는다. 출처 목록은 건드리지 않는다."""
    if isinstance(o, str):
        return C.clean_markup(o)
    if isinstance(o, list):
        return [clean(x) for x in o]
    if isinstance(o, dict):
        return {k: (v if k == "sources" else clean(v)) for k, v in o.items()}
    return o


def _tally(use, message):
    """이번 회수분이 실제로 쓴 양을 더한다.

    여태 로그에는 배치 제출·회수 기록만 있고 얼마를 썼는지가 없었다. 그래서
    "업종 분석을 월 1회로 늘리면 얼마 더 드나" 를 기록으로 답할 수 없었다.
    """
    u = getattr(message, "usage", None)
    if not u:
        return
    for k in ("input_tokens", "output_tokens",
              "cache_read_input_tokens", "cache_creation_input_tokens"):
        use[k] += getattr(u, k, 0) or 0
    stu = getattr(u, "server_tool_use", None)
    use["web_search"] += getattr(stu, "web_search_requests", 0) or 0 if stu else 0


# Batch API 요금(1M 토큰당, 즉시 호출의 절반). 요금표가 바뀌면 아래 추정액만
# 어긋난다 — 토큰 수 자체는 그대로 남으므로 나중에 다시 계산할 수 있다.
# 리포트 생성기의 배치 단가표(generate_reports_v2._PRICE)와 같아야 한다 — 한때 옛 정가의
# 절반을 적어 두어 추정액이 실제보다 1.5배 크게 찍혔다(check_sectors 가 두 표를 견준다).
_RATE = {"claude-sonnet-5": (1.00, 5.00), "claude-opus-5": (2.50, 12.50)}
_WEB_SEARCH_PER_1K = 10.0                       # 웹 검색 1,000회당(배치 할인 없음)


def _log_usage(use, model):
    if not use:
        log("- 사용량 정보 없음(회수 결과에 usage 가 없다)")
        return
    ins = use["input_tokens"] + use["cache_read_input_tokens"] + use["cache_creation_input_tokens"]
    outs = use["output_tokens"]
    log(f"\n■ 사용량 — 입력 {ins:,} 토큰 · 출력 {outs:,} 토큰 · 웹 검색 {use['web_search']}회")
    rate = _RATE.get(model)
    if rate:
        cost = ins / 1e6 * rate[0] + outs / 1e6 * rate[1] \
             + use["web_search"] / 1000 * _WEB_SEARCH_PER_1K
        log(f"  대략 ${cost:,.2f} (Batch 요금 · {model} · 2026-09 요금표 기준 추정)")
    else:
        log(f"  요금표에 없는 모델({model}) — 토큰 수로 직접 계산할 것")


def prepare(rep):
    """저장 전 결정적 정리 — 태그 · 마크다운(clean) · 한자(fix_hanja) · 금액 표기와 천 단위 쉼표(number_spacing).
    돈이 들지 않고 몇 번 돌려도 결과가 같다. 리포트 생성기와 같은 정리다."""
    rep = clean(rep)
    try:
        rep, _ = fix_hanja.walk(rep)
    except Exception as e:                              # noqa: BLE001
        log(f"  · (한자 변환 실패: {type(e).__name__}: {e})")
    _n, rep = number_spacing.normalize_report(rep, commas=True)
    return rep


# 검토로 고칠 수 없는 결함 — 글이 잘렸거나 비었거나 출처가 없다. 이런 글은 다시 쓴다(다음 회차).
_REWRITE = ("max_tokens", "리스크 3개 미만", " 빔", "문장 안 끝남", "출처 0건")
# 검토를 켜고 끈다. 끄면 2026-10-08 판처럼 기계 검사만 하고 저장한다(검토 비용이 들지 않는다).
REVIEW = os.getenv("SECTOR_REVIEW", "1") != "0"
REVIEW_KEYS = BODY_KEYS + ("risks",)


def _needs_rewrite(why):
    return [w for w in why if any(t in w for t in _REWRITE)]


_PCT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*%")


def review_hints(rep, info):
    """검토에 넘길 '확인할 곳' — 기계가 의심한 자리(틀렸을 때만 고치라고 한다).
      · 재료에 있는 회사가 나온 문장의 증감률이 그 회사 재료에 없다(묶음 범위 · 다른 회사 값 · 오기일 수 있다)
      · 한 문장에서 같은 말이 되풀이된다
      · 한국어에 있는 비율이 같은 칸의 영어에 없다"""
    fin = (info or {}).get("fin") or []
    comp = {}
    for line in fin:
        nm = line.split("(")[0].split(":")[0].strip()
        comp[nm] = {x.replace(",", "") for x in _PCT.findall(line)}
    out = []
    for path, v in C._flat_fields({k: rep.get(k) for k in REVIEW_KEYS if rep.get(k)}).items():
        ko, en = v.get("ko") or "", v.get("en") or ""
        for sent in re.split(r"(?<=[.!?])\s+", ko):
            names = [n for n in comp if n and n in sent]
            pcts = [x.replace(",", "") for x in _PCT.findall(sent)]
            if names and pcts:
                miss = [x for x in pcts if not any(x in comp[n] for n in names)]
                if miss:
                    ref = " / ".join(f"{n}: {', '.join(sorted(comp[n])) or '증감률 없음'}" for n in names)
                    out.append(f"[{path}] 재료에 없는 비율 {miss} — 재료({ref}) · 문장: {sent[:140]}")
            toks = sent.split()
            for n in (3, 2):
                grams = [" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)]
                dup = next((g for i, g in enumerate(grams) if len(g.replace(" ", "")) >= 6 and not re.search(r"\d", g)
                            and g in grams[i + n:]), None)
                if dup:
                    out.append(f"[{path}] 같은 말 되풀이 '{dup}' · 문장: {sent[:140]}")
                    break
        miss_en = sorted({x for x in (y.replace(",", "") for y in _PCT.findall(ko))} - {y.replace(",", "") for y in _PCT.findall(en)})
        if miss_en:
            out.append(f"[{path}] 한국어의 비율 {miss_en[:6]} 이 영어에 없다")
    return out[:25]


def review_round(cl, cand, agg, as_of, use):
    """검토 배치 하나 — {업종: (고친 글 또는 None, 기록)}. 배치로만 보낸다(요금 절반 · 즉시 호출 창구는 막혀 있다).
    재료(상위 종목 분기 실적) · 회사 설명(본문에 나온 회사의 기업 리포트 첫 문장 · 영문명) · 기계 검사 결과를 함께 준다."""
    day = _day(as_of) or as_of
    reqs, cmap, ctx = [], {}, {}
    for sec, (rep, _srcs, why) in cand.items():
        info = agg.get(sec) or {}
        part = {k: rep[k] for k in REVIEW_KEYS if k in rep}
        material = "\n".join(f"  - {x}" for x in info.get("fin") or [])
        names = "\n".join(company_lines(mentioned(part, [nm for nm, _ in info.get("top") or []])))
        hits = [dict(h, section=_FROM_REPORT.get(h["section"], h["section"])) for h in C.check(_as_report(rep))
                if h["level"] == "위험" or h["rule"] in GATE_RULES]
        hits += [{"section": w.split("(")[1].split(")")[0] if "(" in w else "본문", "rule": "listed_count",
                  "why": "상장 종목 수를 수치로 썼다 — 관계로", "sentence": w} for w in why if w.startswith("상장 종목 수")]
        hits += [{"section": "본문", "rule": "live_number", "why": "집계 수치를 본문에 옮겼다 — 관계로", "sentence": w}
                 for w in why if "본문에 박힘" in w]
        params = C.review_params(part, kind="sector", as_of=day, material=material, names=names, hits=hits,
                                 hints=review_hints(rep, info))
        cid = "rv_" + _cid(sec)[4:]
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params)))
        cmap[cid] = sec
        ctx[sec] = (part, f"{material}\n{names}")
    batch = cl.messages.batches.create(requests=reqs)
    log(f"- 🔎 검토 배치 제출: {batch.id} ({len(reqs)}건 · {C.REVIEW_MODEL})")
    if not poll(cl, batch.id):
        raise RuntimeError(f"검토 배치가 {MAX_WAIT // 60}분 안에 끝나지 않았다({batch.id})")
    out = {}
    for r in cl.messages.batches.results(batch.id):
        sec = cmap.get(r.custom_id)
        if not sec:
            continue
        if r.result.type != "succeeded":
            out[sec] = (None, f"검토 {r.result.type}")
            continue
        _tally(use, r.result.message)
        text = "".join(getattr(x, "text", "") for x in r.result.message.content if getattr(x, "type", "") == "text")
        part, extra = ctx[sec]
        new_part, applied, dropped = C.apply_review(part, text, extra=extra, as_of=as_of)
        if new_part is None:
            out[sec] = (None, "검토 답을 읽지 못함 — " + "; ".join(dropped))
            continue
        merged = dict(cand[sec][0])
        merged.update(new_part)
        out[sec] = (merged, f"검토 고침 {applied}곳" + (f" · 버림 {len(dropped)}곳({'; '.join(dropped[:2])})" if dropped else ""))
    return out


def collect(cl, as_of, strict_sources=True):
    """회수해 저장한다. strict_sources 면 웹 검색 인용이 0건인 글을 거르고(다음 회차가 다시 쓴다),
    아니면 받는다 — 마지막 회차에서까지 거르면 그 업종은 옛 글에 갇힌 채 돈만 나간다. 그렇게 받은
    글은 출처가 없으므로 화면이 '웹 검색 참고' 를 빼고 보여 준다(build_industry_comp).

    2026-10-09 — 저장 전에 검토를 한 번 거친다(review_round · 배치). 기계 검사가 못 잡는 깨진 문장 · 재료와 다른 서술 ·
    앞뒤 모순 · 낡은 기사 · 회사 설명 오류를 고친다. 고친 글을 다시 정리 · 검사해 결함이 하나라도 남으면 저장하지 않는다
    (있던 글 그대로 · 다음 회차가 다시 만든다). 검토 답이 없거나 읽을 수 없는 업종도 저장하지 않는다."""
    if not STATE.exists():
        log("❌ state 없음"); sys.exit(1)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    b = cl.messages.batches.retrieve(st["batch_id"])
    if b.processing_status != "ended":
        log(f"- 아직 처리 중({b.processing_status})."); return False
    cid_map = st["cid_map"]
    sectors = load_existing()
    # 제출할 때 적어 둔 집계를 쓴다. 옛 state 에는 없으므로 그때만 다시 읽는다.
    agg = st.get("agg") or load_sectors()
    use = defaultdict(int)
    use_rv = defaultdict(int)
    dropped = []                       # 결함으로 저장하지 않은 업종
    ok = fail = 0
    cand = {}                          # 검토로 넘길 글 — {업종: (글, 출처, 결함)}
    for result in cl.messages.batches.results(st["batch_id"]):
        sec = cid_map.get(result.custom_id)
        if not sec:
            continue
        if result.result.type != "succeeded":
            fail += 1; dropped.append(sec)
            log(f"  · ⚠️ {sec} {result.result.type}"); continue
        _tally(use, result.result.message)
        try:
            text = g.extract_text(result.result.message)
            rep = prepare(g.parse_report(text))
            srcs = g.collect_sources(result.result.message)
            why = defects(rep, result.result.message, agg.get(sec),
                          sources=srcs if strict_sources else None)
            hard = _needs_rewrite(why) if REVIEW else why
            if hard:
                fail += 1; dropped.append(sec)
                log(f"  · ⚠️ {sec} 불완전 — 건너뜀 ({'; '.join(why)})"); continue
            cand[sec] = (rep, srcs, why)
        except Exception as e:
            fail += 1; dropped.append(sec)
            log(f"  · ⚠️ {sec} 파싱 실패: {e}")
    reviewed = {}
    if cand and REVIEW:
        try:
            reviewed = review_round(cl, cand, agg, st.get("created") or as_of, use_rv)
        except Exception as e:                           # noqa: BLE001
            log(f"  · ⚠️ 검토 배치 실패: {type(e).__name__}: {e} — 이번 회수분은 저장하지 않는다(다음 회차가 다시 만든다)")
    for sec, (rep, srcs, why) in cand.items():
        if REVIEW:
            got, note = reviewed.get(sec, (None, "검토 답 없음"))
            if got is None:
                fail += 1; dropped.append(sec)
                log(f"  · ⚠️ {sec} {note} — 저장하지 않음"); continue
            rep = prepare(got)
            why = defects(rep, None, agg.get(sec), sources=srcs if strict_sources else None)
            if why:
                fail += 1; dropped.append(sec)
                log(f"  · ⚠️ {sec} 검토 뒤에도 결함 — 저장하지 않음 ({'; '.join(why)})"); continue
            log(f"  · 🔎 {sec} {note}")
        rep.pop("sources", None)        # 출처는 웹 검색 인용에서만 — 모델이 글 안에 적은 목록은 쓰지 않는다
        if srcs:
            rep["sources"] = srcs[:10]
        else:
            log(f"  · {sec} 출처 0건 — 마지막 회차라 저장한다(화면은 '웹 검색 참고' 를 빼고 보인다)")
        rep["sector"] = sec
        # 업종별 작성 시점. FORCE 없이 돌리면 새로 만든 업종과 예전 것이 섞이므로
        # 전체 lastUpdated 만으로는 화면에 정확한 날짜를 못 쓴다.
        rep["generatedAt"] = as_of
        sectors[sec] = rep
        ok += 1
    # 걸러진 업종을 적어 둔다. 다음 실행이 이 목록만 다시 만든다.
    save_retry(dropped, as_of)
    _log_usage(use, st.get("model", MODEL))
    if use_rv:
        log("  (검토)")
        _log_usage(use_rv, C.REVIEW_MODEL)
    payload = {"lastUpdated": as_of, "model": st.get("model", MODEL), "sectors": sectors}
    # 금액 표기 통일 — 리포트와 같은 규칙(한글 맞춤법 제44항 · 천 단위 쉼표)
    _nsp, payload = number_spacing.normalize_report(payload, commas=True)
    if _nsp:
        print(f"  · 금액 표기 {_nsp}곳 정리")
    OUT_JS.write_text("// KOS ai — 업종 AI 분석 (자동 생성). 직접 수정 금지.\n"
                      "window.KOS_SECTORS = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
                      encoding="utf-8")
    log(f"\n✅ 회수 완료 · 성공 {ok}/실패 {fail} · 총 {len(sectors)}개 → data/sectors.js")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    log(f"## generate_sectors 시작 — mode={mode!r} · MODEL={MODEL} · FORCE={FORCE}")
    sys.stdout.flush()
    cl = client()
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if mode == "submit":
        submit(cl, as_of)
        return
    if mode == "collect":
        collect(cl, as_of)
        return

    # ── auto — 걸러진 것이 없을 때까지 되풀이한다 ──────────────
    #
    # 프롬프트를 아무리 다듬어도 모델 출력은 확률이다. 2026-09-04 실행에서
    # 30개 중 11개가 걸러졌는데(대부분 영어를 비운 출력), 그때는 한 번 내고
    # 끝이라 11개가 8월 글 그대로 남았다. 다시 만들려면 사람이 알아채고
    # 손으로 또 돌려야 했다.
    #
    # 되풀이는 확률이 아니다. 걸러진 것만 다시 내므로 회차마다 대상이 줄고,
    # 요금도 그만큼만 더 든다. 두 번째 회차부터는 FORCE 를 끈다 — 켜 두면
    # 멀쩡한 것까지 통째로 다시 만든다.
    #
    # 끝까지 못 만든 것이 있으면 0 이 아닌 값으로 끝낸다.
    #
    # 조용히 성공으로 끝나면 아무도 모른다. 이 파이프라인은 분기에 한 번만
    # 도니까 '모른다' 는 곧 '다음 분기까지 낡은 글이 걸려 있다' 는 뜻이다.
    # 실제로 7·8월 크론이 아무것도 안 하고 성공으로 끝난 적이 있다.
    #
    # 만들어진 것은 그대로 저장된다 — 워크플로의 커밋 단계가 if: always()
    # 라서, 실패로 끝나도 19개가 새로 쓰였으면 그 19개는 올라간다.
    for rnd in range(1, ROUNDS + 1):
        if rnd > 1:
            as_of = datetime.datetime.now(
                datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
        bid = submit(cl, as_of, force=(FORCE if rnd == 1 else False))
        if not bid:
            break                                  # 만들 것이 없다
        if not poll(cl, bid):
            log(f"\n❌ {rnd}차 배치가 {MAX_WAIT // 60}분 안에 안 끝났다.")
            log("   만들어진 것이 없다. 실행 기록을 보고 다시 돌릴 것.")
            sys.exit(1)
        collect(cl, as_of, strict_sources=(rnd < ROUNDS))
        left = load_retry()
        if not left:
            log(f"\n■ {rnd}차에서 전부 저장됐다.")
            return
        if rnd == ROUNDS:
            log(f"\n❌ {ROUNDS}차까지 했는데 {len(left)}개가 남았다: {', '.join(sorted(left))}")
            log("   그 업종은 지난번 글이 그대로 걸려 있다.")
            log("   워치독이 하루 뒤에 이 목록만 다시 만든다.")
            sys.exit(1)
        log(f"\n■ {rnd}차에서 {len(left)}개가 걸러졌다 — 그것만 다시 만든다: {', '.join(sorted(left))}")


def _entry():
    try:
        main()
    except Exception as e:
        import traceback
        msg = "❌ generate_sectors 예외: " + "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(msg, flush=True)
        try:
            (ROOT / "data" / "sectors_run.log").open("a", encoding="utf-8").write(msg + "\n")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    _entry()
