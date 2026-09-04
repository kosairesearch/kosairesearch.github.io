#!/usr/bin/env python3
"""
KOSAI 리포트 v2 — '정량 + 정성 분리' 구조 (Message Batches API)

핵심 원칙: 재무 숫자는 AI가 쓰지 않는다.
  - 정량(연간 4개년·분기 5개 분기 실적, 밸류에이션, TTM PER)은 이 스크립트가
    DART(fnlttSinglAcntAll)·KRX(pykrx 로그인)에서 직접 수집해 JSON에 넣는다.
  - AI(batch)는 그 숫자를 '근거'로 받아 해석·서술 섹션만 작성한다.

모드:
  quant    — 정량 데이터만 수집해 검증 로그 출력 (배치 미제출, 검증용)
  patch    — 기존 리포트의 정량 블록만 교체 (API 미호출·무료)
  submit   — 정량 수집 + 배치 제출 → data/batches_v2/<batch_id>.json
  pickup   — 끝난 배치를 전부 회수 → data/reports_v2/{ticker}.json (collect 도 같다)
  auto     — submit 후 잠깐(BATCH_SHORT_WAIT_SEC) 기다려 끝났으면 회수, 아니면 pickup 에 맡긴다
  recover  — 상태 파일이 없는 배치를 ID 로 회수 (RECOVER_BATCH_ID)
  batches  — 최근 배치 목록 (진단)

주문(submit)과 회수(pickup)는 분리돼 있다. 배치는 24시간까지 걸릴 수 있고 잡은
6시간에 잘리므로 주문한 자리에서 기다리지 않는다. 주문마다 상태 파일을 하나
남기고(병렬 run 이 서로 덮어쓰지 않는다) 워크플로가 그 파일을 커밋한다.
collect_batch 워크플로가 30분마다 남은 파일을 보고 회수한다. 상태 파일이 커밋되지
않으면 배치 ID 가 run 과 함께 사라져 돈만 나간다 — 8월 20일 479건이 그랬다.

돈이 나가는 주문 앞에는 빗장이 셋이다.
  · data/reports_paused 가 있으면 주문하지 않는다.
  · 이미 주문이 들어가 있는 종목(진행 중 배치)은 다시 주문하지 않는다.
  · 정량 숫자가 항등식(check_valuation.HARD)에 걸리는 종목은 글을 쓰지 않는다.
    그 종목만 빼고 나머지는 진행한다 — 한 종목의 공시 오류가 전체를 멈추지 않는다.

환경변수: ANTHROPIC_API_KEY, DART_API_KEY, KRX_ID, KRX_PW,
          REPORT_MODEL_TOP/REST/TOP_N, REPORT_TICKERS, REPORT_TOP_N(기본 10),
          REPORT_FILL_TO/FROM/SHARDS/SHARD(자동 백필), REPORT_BACKFILL(skip 재시도 run),
          REPORT_ALLOW_INFLIGHT(진행 중인 종목도 다시 주문), BATCH_SHORT_WAIT_SEC
"""

import contextlib
import datetime
import io
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_reports as g  # log/extract_text/collect_sources/load_stocks 재사용
import check_report_text     # 생성 직후 금지 표현 검사 + 걸린 문장 교정(프롬프트가 못 막은 것)
import fix_hanja             # 본문에 섞인 한자를 한글로(모델이 '전년比' 처럼 쓴다)
import check_valuation       # 종목별 항등식 — 숫자가 깨진 종목은 글을 쓰지 않는다
import _reports_state as S   # skip·hold·fail 마커 · 배치 상태 파일 · 갱신 기준일

OUT_DIR = S.OUT_DIR
BATCH_DIR = S.BATCH_DIR
# 있으면 돈이 드는 모드(submit·auto·recover)를 전부 멈춘다. main() 참고.
PAUSE_FILE = S.PAUSE_FILE
# 생성 불가 종목(DART 재무 없음: 인프라펀드·스팩·일부 지주 등) — 백필이 영원히 재시도하지 않도록 기록.
SKIP_DIR = S.SKIP_DIR
load_skip = S.load_skip
add_skip = S.add_skip

# 종료 코드. 워크플로가 이 값으로 '무엇이 막았는지' 를 가른다.
EXIT_DART_UNAVAILABLE = 3     # DART 한도 초과·점검·키 문제 — 종목 탓이 아니다. skip 을 남기지 않는다.

MODEL = os.getenv("REPORT_MODEL_V2", "claude-opus-5")  # 폴백
# 모델 정책: 시총 상위 MODEL_TOP_N개는 고급 모델(Opus), 나머지는 효율 모델(Sonnet)
MODEL_TOP = os.getenv("REPORT_MODEL_TOP", "claude-opus-5")
MODEL_REST = os.getenv("REPORT_MODEL_REST", "claude-sonnet-5")
MODEL_TOP_N = int(os.getenv("REPORT_MODEL_TOP_N", "300"))
TOP_N = int(os.getenv("REPORT_TOP_N", "10"))
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "10800"))
# auto 가 주문 직후 기다리는 시간. 짧게 끝나는 배치만 그 자리에서 받고,
# 오래 걸리면 collect_batch 워크플로에 넘긴다(6시간 제한을 무의미하게).
SHORT_WAIT = int(os.getenv("BATCH_SHORT_WAIT_SEC", "1800"))


def model_for(rank):
    """시총 순위(1=최대)에 따른 모델 선택."""
    return MODEL_TOP if (rank is not None and rank <= MODEL_TOP_N) else MODEL_REST

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6,
          "blocked_domains": ["namu.wiki", "librewiki.net", "dcinside.com", "fmkorea.com"],
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log


class DartUnavailable(RuntimeError):
    """DART 가 지금 응답을 주지 않는다 — 하루 한도 초과(020)·점검(800)·키 문제(01x).
    종목 탓이 아니므로 이 예외가 나면 run 을 통째로 멈추고 skip 을 남기지 않는다."""

    def __init__(self, status, message=""):
        super().__init__(f"DART status {status}: {message}")
        self.status = status
        self.message = message


# DART 응답 코드. 000 정상 · 013 조회 데이터 없음 — 이 둘만 '종목의 사정' 이다.
# 나머지(010/011/012 키 · 020/021 한도 · 800 점검 · 900 오류)는 우리 쪽 사정이다.
_DART_STATUS = re.compile(r"'status':\s*'(\d{3})'(?:,\s*'message':\s*'([^']*)')?")


def _dart_call(fn, *args, **kw):
    """OpenDartReader 함수를 부른다. 라이브러리는 status≠000 이면 예외 대신 그 사실을
    stdout 에 print 하고 빈 DataFrame 을 돌려준다. 그래서 하루 한도를 넘긴 뒤의
    호출은 전부 '재무제표 없음' 과 똑같이 생겼고, 자동 백필은 그 종목들을 생성
    불가로 영구 기록해 버렸다. 여기서 print 를 잡아 코드를 읽는다."""
    buf = io.StringIO()
    err = None
    try:
        with contextlib.redirect_stdout(buf):
            df = fn(*args, **kw)
    except DartUnavailable:
        raise
    except Exception as e:                     # 'could not find corp' 등 — 그 종목의 사정
        df, err = None, f"{type(e).__name__}: {e}"
    out = buf.getvalue()
    for m in _DART_STATUS.finditer(out + (err or "")):
        if m.group(1) not in ("000", "013"):
            raise DartUnavailable(m.group(1), m.group(2) or "")
    for ln in out.splitlines():                # 라이브러리의 진단 출력은 그대로 남긴다(잡음만 뺀다)
        if ln.strip() and not ln.startswith("reprt_code=") and "조회된 데이타가 없습니다" not in ln:
            print(ln)
    return df


import re as _re_src
# 저신뢰 출처(블로그·위키·커뮤니티) 차단 — 신뢰도 하락 방지
LOW_TRUST_SRC = (
    "blog.naver.com", "blog.daum.net", "tistory.com", "brunch.co.kr",
    "velog.io", "medium.com", "blogspot.", "wordpress.com", "postype.com",
    "egloos.com", "steemit.com", "namu.wiki", "wikipedia.org", "fandom.com",
    "wikidocs.net", "dcinside.com", "fmkorea.com", "clien.net", "ruliweb.com",
    "inven.co.kr", "cafe.naver.com", "cafe.daum.net", "ppomppu.co.kr",
)
def _low_trust_src(url):
    try:
        host = _re_src.sub(r"^https?://", "", url or "").split("/")[0].lower()
    except Exception:
        return False
    if host.startswith("blog.") or host.startswith("m.blog."):
        return True
    return any(b in host for b in LOW_TRUST_SRC)


def collect_sources_v2(message):
    """출처 URL을 인용(citations) + 웹검색 결과(web_search_tool_result) 양쪽에서 수집한다.
    모델이 JSON만 출력해 인용 태그가 안 붙어도, 실제 검색이 반환한 URL을 확보한다."""
    cited, searched = [], []
    for block in getattr(message, "content", []) or []:
        # 1) 본문 인용
        for c in (getattr(block, "citations", None) or []):
            u = getattr(c, "url", None)
            if u and u not in cited:
                cited.append(u)
        # 2) 웹검색 도구 결과
        if getattr(block, "type", None) == "web_search_tool_result":
            items = getattr(block, "content", None) or []
            for it in items:
                u = getattr(it, "url", None)
                if u and u not in searched:
                    searched.append(u)
    # 인용된 출처를 앞에, 그 외 검색결과를 뒤에 (중복 제거)
    out = list(cited)
    for u in searched:
        if u not in out:
            out.append(u)
    return [u for u in out if not _low_trust_src(u)]


# ── 정량 1: DART 전체 재무제표 ────────────────────────────────────────
# account_id 우선, 계정명 폴백. 연결(CFS) 기준.
ACC_IDS = {
    "rev":          ("ifrs-full_Revenue", "ifrs_Revenue"),
    "rev_ins":      ("ifrs-full_InsuranceRevenue", "ifrs_InsuranceRevenue"),
    "op":           ("dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities",
                     "ifrs_ProfitLossFromOperatingActivities"),
    "np":           ("ifrs-full_ProfitLoss", "ifrs_ProfitLoss"),
    "np_owner":     ("ifrs-full_ProfitLossAttributableToOwnersOfParent",
                     "ifrs_ProfitLossAttributableToOwnersOfParent"),
    "np_nci":       ("ifrs-full_ProfitLossAttributableToNoncontrollingInterests",
                     "ifrs_ProfitLossAttributableToNoncontrollingInterests"),
    "eps_basic":    ("ifrs-full_BasicEarningsLossPerShare", "ifrs_BasicEarningsPerShare"),
    "assets":       ("ifrs-full_Assets", "ifrs_Assets"),
    "liab":         ("ifrs-full_Liabilities", "ifrs_Liabilities"),
    "equity":       ("ifrs-full_Equity", "ifrs_Equity"),
    "equity_owner": ("ifrs-full_EquityAttributableToOwnersOfParent",
                     "ifrs_EquityAttributableToOwnersOfParent"),
    "equity_nci":   ("ifrs-full_NoncontrollingInterests", "ifrs_NoncontrollingInterests"),
    "cfo":          ("ifrs-full_CashFlowsFromUsedInOperatingActivities",
                     "ifrs_CashFlowsFromUsedInOperatingActivities"),
}
ACC_NAMES = {
    "rev":          ("매출액", "수익(매출액)", "영업수익", "매출"),
    "rev_ins":      ("보험수익",),
    "op":           ("영업이익", "영업이익(손실)", "영업손익"),
    "np":           ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"),
    "np_owner":     ("지배기업소유주지분", "지배기업의소유주에게귀속되는당기순이익",
                     "지배기업소유주귀속당기순이익", "지배주주순이익"),
    "np_nci":       ("비지배주주지분", "비지배지분", "비지배주주귀속당기순이익"),
    "eps_basic":    ("기본주당이익", "기본주당순이익", "기본주당이익(손실)", "기본및희석주당이익"),
    "assets":       ("자산총계",),
    "liab":         ("부채총계",),
    "equity":       ("자본총계",),
    "equity_owner": ("지배기업소유주지분", "지배기업의소유주에게귀속되는자본"),
    "equity_nci":   ("비지배지분", "비지배주주지분"),
    "cfo":          ("영업활동현금흐름", "영업활동으로인한현금흐름"),
}


# 계정명 접두(로마숫자·번호 + 구분점) 제거용 — "IV.영업이익"→"영업이익", "1.기본주당이익"→"기본주당이익"
_NM_PREFIX = re.compile(r"^[IVXLCDMⅠ-Ⅻ0-9]{1,4}[.)]\s*")
# 계정명 꼬리 — "(손실)"·"(손익)"·"(주1)"·"*" 같은 표기 차이로 같은 계정을 못 알아보는 일이
# 분기 순이익 빈칸 155건·매출 빈칸 177건의 상당수였다.
_NM_SUFFIX = re.compile(r"(\((순)?손실\)|\(손익\)|\(결손\)|\(주\d*\)|\*+|\(단위:[^)]*\))+$")


def _norm_acc(anm):
    """계정명을 비교하기 좋은 꼴로: 접두 번호·꼬리 표기를 떼고 공백 없이."""
    s = _NM_PREFIX.sub("", anm.replace(" ", ""))
    return _NM_SUFFIX.sub("", s)


# 정확한 이름 목록(ACC_NAMES)에 없는 변형을 받는 정규식. sj_ok 로 재무제표 종류가
# 먼저 걸러진 뒤에 쓰인다 — 손익계산서에서 '지배…' 로 시작하는 행은 지배주주 순이익이고,
# 재무상태표에서 같은 접두는 지배지분이다. '포괄' 과 '주당' 이 들어간 행은 뺀다
# (총포괄손익 귀속분·주당이익은 다른 계정이다).
_ACC_RE = {
    "np_owner":     re.compile(r"^지배(?!.*(포괄|주당)).*"),
    "np_nci":       re.compile(r"^비지배(?!.*(포괄|주당)).*"),
    "np":           re.compile(r"^(연결)?(당기|분기|반기)?순(이익|손익)$"),
    "eps_basic":    re.compile(r"^(지배.*?)?(보통주)?기본(및희석)?주당(순)?(이익|손익)$|^주당(순)?(이익|손익)$"),
    "equity_owner": re.compile(r"^지배(?!.*포괄).*"),
    "equity_nci":   re.compile(r"^비지배(?!.*포괄).*"),
    "cfo":          re.compile(r"^영업활동.*현금흐름$"),
    "rev":          re.compile(r"^(총)?매출(액)?(\(수익\))?$|^수익\(매출액\)$|^영업수익$"),
    "op":           re.compile(r"^영업(이익|손익)$"),
}


def _name_hit(key, anm):
    """계정명이 이 키에 해당하는가 — 정확한 목록 먼저, 그 다음 정규화한 이름, 마지막으로 정규식."""
    if anm in ACC_NAMES[key]:
        return True
    a2 = _norm_acc(anm)
    if a2 in ACC_NAMES[key]:
        return True
    rx = _ACC_RE.get(key)
    return bool(rx and rx.fullmatch(a2))


def _fin_all(dart, ticker, year, reprt):
    """fnlttSinglAcntAll → {key: {"amt": 당기, "add": 누적}}.
    연결(CFS) 우선, 자회사가 없어 연결재무제표가 없는 단독기업은 별도(OFS)로 폴백."""
    df = None
    for fs in ("CFS", "OFS"):
        df = _dart_call(dart.finstate_all, ticker, year, reprt_code=reprt, fs_div=fs)
        if df is not None and not getattr(df, "empty", True):
            break
    if df is None or getattr(df, "empty", True):
        return None
    rows = []
    for _, r in df.iterrows():
        rows.append((str(r.get("account_id", "")).strip(),
                     str(r.get("account_nm", "")).replace(" ", ""),
                     str(r.get("sj_div", "")),
                     g._num(r.get("thstrm_amount")),
                     g._num(r.get("thstrm_add_amount")),
                     g._num(r.get("frmtrm_amount"))))      # 전기(직전 연도) — 빠진 해를 채울 때 쓴다

    def sj_ok(key, sj):
        if key in ("rev", "rev_ins", "op", "np", "np_owner", "np_nci", "eps_basic"):
            return sj in ("IS", "CIS")
        if key in ("assets", "liab", "equity", "equity_owner", "equity_nci"):
            return sj == "BS"
        return sj == "CF"

    _dump_on = ticker in os.getenv("DUMP_EPS", "").replace(" ", "").split(",")
    out = {}
    # 손익 항목은 손익계산서(IS) 행을 포괄손익계산서(CIS) 행보다 먼저 본다.
    #
    # '지배기업소유주지분' 이라는 이름은 두 곳에 나온다. 손익계산서에서는
    # 당기순이익 중 지배주주 몫이고, 포괄손익계산서에서는 총포괄손익 중
    # 지배주주 몫이다. 총포괄손익에는 환산차·평가손익이 섞여 순이익과 크게
    # 다르다. 행 순서대로 먼저 만나는 것을 집으면 회사마다 다른 값이 잡힌다.
    #
    # 이마트에서 실제로 그랬다. 포괄손익 행(당기 5,743억)이 잡혀 주당이익과
    # 어긋났고, 그래서 주식수가 1,600만주(실제 2,760만주)로 역산됐다.
    rows.sort(key=lambda r: 0 if r[2] == "IS" else 1)

    # 1차: 표준 account_id 정확 일치 (가장 신뢰)
    for aid, anm, sj, amt, add, prv in rows:
        for key in ACC_IDS:
            if key in out or amt is None or not sj_ok(key, sj):
                continue
            if aid in ACC_IDS[key]:
                out[key] = {"amt": amt, "add": add, "prv": prv}
    # 2차: 계정명 폴백 — 포괄손익 계열 행 배제.
    #   np_owner 는 CIS의 '총포괄손익 귀속-지배기업소유주지분'과 행 이름이 같아
    #   오추출 위험이 커서 손익계산서(IS)에서만 명칭 매칭을 허용한다.
    for aid, anm, sj, amt, add, prv in rows:
        for key in ACC_IDS:
            if key in out or amt is None or not sj_ok(key, sj):
                continue
            if "포괄" in anm:
                continue
            if key in ("np_owner", "np_nci") and sj != "IS":
                continue
            # 은행 등은 계정명에 로마숫자·번호 접두("IV.영업이익","I.영업수익")가 붙고,
            # 적자 회사는 꼬리에 "(손실)" 이 붙는다 → 정규화한 뒤 비교(_name_hit).
            if _name_hit(key, anm):
                out[key] = {"amt": amt, "add": add, "prv": prv}
    # 지배주주 순이익이 제대로 잡혔는지 본다.
    #
    # 전에는 '|지배주주| ≤ |전체|×1.02' 를 어기면 포괄손익을 잘못 집은 것으로
    # 보고 전체 순이익으로 갈아 끼웠다. 그 전제가 틀렸다. 지배주주가 적자이고
    # 비지배주주가 흑자면 |지배주주| 가 |전체| 보다 클 수 있다. 뺄셈이지
    # 덧셈이 아니다.
    #
    #   이마트 2026 반기   지배주주 -964.7억
    #                     비지배주주  +390.9억
    #                     합계       -573.9억      |지배| > |전체| 이지만 정상
    #
    # 그래서 지배주주 -964.7억이 전체 -573.9억으로 갈아 끼워졌고, 그 값을
    # 공시 주당이익(-3,601원)으로 나누니 주식수가 1,600만주(실제 2,760만주)로
    # 나왔다. 그 분모로 자본을 나눠 BPS 824,830원(주가 7만원대)이 됐다.
    #
    # 옳은 검사는 항등식이다:  지배주주 + 비지배주주 = 전체
    # 비지배주주 값이 없으면 부호가 같을 때만 크기를 본다.
    if "np" in out and "np_owner" in out:
        np_v, npo_v = out["np"]["amt"], out["np_owner"]["amt"]
        nci_v = out.get("np_nci", {}).get("amt")
        bad = False
        if np_v is not None and npo_v is not None:
            if nci_v is not None:
                # 항등식이 1% 안에서 맞으면 정상 (분모가 0에 가까우면 절대오차로)
                gap = abs((npo_v + nci_v) - np_v)
                bad = gap > max(abs(np_v) * 0.01, 1e6)
            elif (np_v >= 0) == (npo_v >= 0):
                bad = abs(npo_v) > abs(np_v) * 1.02
        if bad:
            out["np_owner"] = dict(out["np"])
    if _dump_on:
        with open(ROOT / "data" / "_debug_eps.txt", "a", encoding="utf-8") as fp:
            fp.write(f"  >>> 최종 선택 {reprt}: ")
            for k in ("np", "np_owner", "np_nci", "eps_basic"):
                v = out.get(k)
                fp.write(f"{k}={'없음' if not v else (str(v['amt'])+'/'+str(v['add']))}  ")
            fp.write("\n")
    if not out:
        return None
    # 이 숫자가 연결(CFS)인지 별도(OFS)인지 남긴다. 누적 차감으로 단일 분기를 만들 때
    # 기준이 다른 두 보고서를 빼면 결과가 통째로 거짓이 되므로, 뺄 때 이걸 대조한다.
    out["_fs"] = fs
    # 어느 보고서에서 온 값인지 남긴다. 주당이익은 누적 칸이 비어 있는 경우가
    # 많은데, 분기보고서에서 그 칸이 비면 옆 칸은 '3개월치'다. 연간보고서에서는
    # 같은 칸이 '1년치'다. 구분하지 못하면 6개월 순이익을 3개월 주당이익으로
    # 나누게 된다 — 이마트에서 주식수가 1,600만주로 잡힌 원인이었다.
    out["_reprt"] = reprt
    # 공시 통화. 국내 상장 외국기업(9xxxxx)은 위안·달러로 낸다. 그 숫자를
    # 원으로 착각하면 BPS 가 주가의 몇십분의 일로 나온다(엑세스바이오 BPS 9원).
    try:
        cy = str(df.iloc[0].get("currency") or "").strip().upper()
    except Exception:
        cy = ""
    out["_ccy"] = cy or "KRW"
    # 주당이익 원문 덤프 — DUMP_EPS=티커,티커 로 켠다. 어느 행을 집었는지,
    # 그 행의 당기/누적 칸이 각각 얼마인지 그대로 찍는다. 결과만 봐서는
    # '회사가 낸 값' 과 '우리가 고른 값' 을 구분할 수 없어 원인을 못 좁혔다.
    if _dump_on:
        # 로그는 길어지면 잘려 못 본다. 파일로 남긴다(워크플로가 커밋한다).
        dbg = ROOT / "data" / "_debug_eps.txt"
        with open(dbg, "a", encoding="utf-8") as fp:
            fp.write(f"\n### {ticker} {reprt}/{fs}\n")
            for aid, anm, sj, amt, add, prv in rows:
                if sj in ("IS", "CIS"):
                    fp.write(f"  {sj:<4} 당기={amt}  누적={add}  | {anm} | {aid}\n")
    return out


def _fin_summary(dart, ticker, year):
    """전체 재무제표(fnlttSinglAcntAll)가 없는 해를 요약재무(fnlttSinglAcnt)로 채운다.

    보험·증권 등 금융사 180곳이 2022년 칸이 비어 연간 표가 3년치였다(IFRS17 전환
    전 보고서는 계정 체계가 달라 전체 재무제표에서 아무 계정도 못 집는다). 요약재무는
    매출액·영업이익·당기순이익·자산·부채·자본총계를 표준 이름으로 준다. 지배주주
    구분은 없다 — 호출자가 다른 해의 비지배 유무를 보고 np_owner 를 정한다.
    _fin_all 과 같은 모양의 dict 를 돌려준다(없으면 None)."""
    df = _dart_call(g._safe_finstate, dart, ticker, year, "11011")
    if df is None or getattr(df, "empty", True):
        return None
    want = {"매출액": "rev", "영업이익": "op", "당기순이익": "np",
            "자산총계": "assets", "부채총계": "liab", "자본총계": "equity"}
    out, fs_used = {}, None
    for fs in ("CFS", "OFS"):
        rows = df[df["fs_div"].astype(str) == fs] if "fs_div" in df.columns else df
        got = {}
        for _, r in rows.iterrows():
            nm = _norm_acc(str(r.get("account_nm", "")))
            key = want.get(nm)
            if key and key not in got:
                v = g._num(r.get("thstrm_amount"))
                if v is not None:
                    got[key] = {"amt": v, "add": v}
        if got:
            out, fs_used = got, fs
            break
    if not out:
        return None
    out["_fs"] = fs_used
    out["_reprt"] = "11011"
    out["_ccy"] = "KRW"
    out["_src"] = "요약재무"
    return out


def _shift_prev(d):
    """다음 해 보고서의 '전기' 칸으로 그 전 해를 만든다.

    보험사 180곳의 2022년은 전체 재무제표에서도 요약재무에서도 안 나온다(IFRS17
    전환 전 보고서는 계정 체계가 달라 조회가 안 된다). 그런데 2023년 보고서의
    전기 비교치는 2022년을 IFRS17 로 다시 쓴 값이라 — 같은 기준이라 오히려 비교에
    낫다. _fin_all 결과와 같은 모양으로 돌려준다. 전기 값이 하나도 없으면 None."""
    if not d:
        return None
    out = {}
    for k, v in d.items():
        if isinstance(v, dict) and v.get("prv") is not None:
            out[k] = {"amt": v["prv"], "add": v["prv"], "prv": None}
    if not out:
        return None
    for k in ("_fs", "_reprt", "_ccy"):
        if k in d:
            out[k] = d[k]
    out["_src"] = "전기 비교치"
    return out


def _cum(d, key):
    """보고서 기준 누적값: thstrm_add_amount 우선, 없으면 thstrm_amount."""
    if not d or key not in d:
        return None
    v = d[key]
    return v["add"] if v["add"] is not None else v["amt"]


def _cum_eps(d):
    """누적 주당이익. 확실할 때만 돌려주고, 아니면 None.

    DART 는 주당이익 행의 '누적' 칸을 비워 두는 회사가 많다. _cum 은 그럴 때
    옆 칸(당기)을 대신 쓰는데, 분기보고서에서 그 칸은 '그 분기 3개월치'다.
    순이익은 누적으로 잡히므로, 둘을 나누면 6개월 순이익 ÷ 3개월 주당이익이
    된다. 이마트가 그래서 주식수 1,600만주(실제 2,760만주)로 잡혔고 BPS 가
    82만원(주가 7만원대)으로 나갔다.

    연간보고서(11011)는 당기 칸이 곧 1년치라 그대로 써도 된다."""
    if not d or "eps_basic" not in d:
        return None
    v = d["eps_basic"]
    if v["add"] is not None:
        return v["add"]
    return v["amt"] if d.get("_reprt") == "11011" else None


def _bs(d, key):
    """재무상태표 기말값."""
    if not d or key not in d:
        return None
    return d[key]["amt"]


def _sub(a, b):
    return (a - b) if (a is not None and b is not None) else None


def _owner_equity(eqo, eq, nci):
    """지배지분을 항등식(지배 + 비지배 = 자본총계)에 맞게 되찾는다.

    · 지배지분 태그를 못 읽었는데 비지배지분은 읽었으면  지배 = 총계 − 비지배.
      예전에는 그냥 자본총계로 대신했다. 유한양행은 그 바람에 지배지분이
      23,623억(= 자본총계)으로 실렸는데, 비지배지분 554억을 빼면 23,069억이다.
    · 지배지분이 자본총계와 '똑같은데' 비지배지분이 따로 있으면, 지배 칸에
      총계를 적은 것이다(한울앤제주 2025: 지배 160억 = 총계 160억, 비지배 2억).
      셋이 동시에 맞을 수는 없다. 그대로 두면 항등식 검산에 걸려 생성이 막힌다.
      이때도 지배 = 총계 − 비지배 다.
    그 밖에는 읽은 값을 그대로 둔다 — 비지배지분이 음수라 지배 > 총계 인
    회사는 정상이다."""
    if eq is None or nci in (None, 0):
        return eqo
    if eqo is None:
        return eq - nci
    if abs(eqo - eq) <= abs(eq) * 0.001 and abs(nci) > abs(eq) * 0.001:
        return eq - nci
    return eqo


def collect_quant(dart, ticker, krx_row, stock):
    """한 종목의 정량 블록을 수집한다."""
    cur = datetime.date.today().year  # 2026

    # 연간 4개년 (최근 결산 = cur-1). 먼저 해마다 보고서를 모으고, 못 구한 해는
    # ① 요약재무 ② 다음 해 보고서의 전기 비교치 순으로 채운 뒤 표를 만든다.
    annual = []
    annual_fs = {}          # 연도 → 연결(CFS)/별도(OFS). 4분기를 뺄 때 기준 대조에 쓴다.
    d_by_year = {}
    for yr in range(cur - 1, cur - 5, -1):
        d = _fin_all(dart, ticker, yr, "11011")
        if not d:
            d = _fin_summary(dart, ticker, yr)      # 전체 재무제표가 없는 해 — 요약재무로
            if d:
                log(f"  · {yr} 연간은 요약재무로 채운다(전체 재무제표에서 계정을 못 읽음)")
        if d:
            d_by_year[yr] = d
        time.sleep(0.3)
    for yr in range(cur - 2, cur - 5, -1):
        if yr not in d_by_year and (yr + 1) in d_by_year:
            d = _shift_prev(d_by_year[yr + 1])
            if d:
                d_by_year[yr] = d
                log(f"  · {yr} 연간은 {yr + 1} 보고서의 전기 비교치로 채운다(같은 회계 기준으로 다시 쓴 값)")
    for yr in sorted(d_by_year, reverse=True):
        d = d_by_year[yr]
        annual_fs[yr] = d.get("_fs")
        rev, op = _cum(d, "rev"), _cum(d, "op")
        np_, npo = _cum(d, "np"), _cum(d, "np_owner")
        eq, eqo, li = _bs(d, "equity"), _bs(d, "equity_owner"), _bs(d, "liab")
        _nci = _bs(d, "equity_nci")
        eqo = _owner_equity(eqo, eq, _nci)      # 지배 + 비지배 = 총계 (_owner_equity 참고)
        row = {
            "year": yr, "rev": rev, "op": op, "np": np_,
            "np_owner": npo if npo is not None else np_,
            "equity": eq, "equity_owner": (eqo if eqo is not None else eq),
            # 비지배지분은 화면에 안 쓴다. 나중에 '지배 + 비지배 = 총계' 를
            # 검산하려면 이 값이 있어야 하는데, 없어서 '지배지분 > 자본총계'
            # 인 회사가 오류인지 정상(비지배지분이 음수)인지 가릴 수 없었다.
            "equity_nci": _nci,
            "liab": li, "cfo": _cum(d, "cfo"),
            "eps_basic": _cum_eps(d),
        }
        if d.get("_src"):
            row["src"] = d["_src"]                   # 요약재무(지배주주 구분 없음 — 아래에서 정리) · 전기 비교치
        row["opm"] = round(op / rev * 100, 1) if (op is not None and rev) else None
        base_np = row["np_owner"]
        base_eq = eqo if eqo is not None else eq
        # 자본잠식(자본 ≤ 0) 연도는 ROE 무의미 → 숨김
        row["roe"] = round(base_np / base_eq * 100, 1) if (base_np is not None and base_eq and base_eq > 0) else None
        row["debt_ratio"] = round(li / eq * 100, 1) if (li is not None and eq) else None
        annual.append(row)

    # 요약재무로 채운 해에는 지배주주 순이익이 없다. 다른 해에서 전체와 지배가 갈리는
    # 회사(비지배지분 있음)면 전체 순이익을 지배주주 칸에 넣지 않는다 — 표의 머리말과
    # 다른 값이 된다. 갈리지 않는 회사(전체 = 지배)면 그대로 둔다.
    _split = any(r.get("src") != "요약재무" and r.get("np") is not None and r.get("np_owner") is not None
                 and abs(r["np"] - r["np_owner"]) > abs(r["np"]) * 0.01 for r in annual)
    for r in annual:
        if r.get("src") == "요약재무" and _split:
            r["np_owner"] = None
            r["roe"] = None

    # ── 분기 실적: '최근 5개 분기'를 굴려서 만든다 ─────────────────────────
    # 예전에는 (전년 Q1~Q4 + 올해 Q1)로 고정돼 있었다. 1분기 시즌에는 그게
    # 정답이라 문제가 드러나지 않았지만, 반기보고서가 나오는 8월이면 2분기가,
    # 11월이면 3분기가 영영 빠진다. 나오는 보고서를 따라가야 한다.
    #
    # DART 정기보고서는 '누적'으로 공시된다 → 단일 분기는 누적을 빼서 만든다.
    #   Q1 = 1분기보고서(11013)           Q3 = 3분기보고서(11014) − 반기
    #   Q2 = 반기보고서(11012) − 1분기     Q4 = 사업보고서(11011)  − 3분기
    py = cur - 1
    Q_CODE = ("11013", "11012", "11014")      # 1분기 · 반기 · 3분기 (모두 누적)

    _fin_cache = {}

    def fin(year, code):
        """같은 (연도, 보고서)를 여러 계정이 함께 쓰므로 한 번만 받아 캐시한다."""
        k = (year, code)
        if k not in _fin_cache:
            _fin_cache[k] = _fin_all(dart, ticker, year, code)
            time.sleep(0.3)
        return _fin_cache[k]

    ann = {a["year"]: a for a in annual}
    fy_row = ann.get(py)

    # 올해 나온 '가장 최근' 정기보고서. 분기표·TTM·BPS·ROE가 모두 이 시점을 기준으로 삼는다.
    # cur_qi = 1(1분기) · 2(반기) · 3(3분기) · 0(연초라 올해 보고서가 아직 없음)
    cur_qi, d_cur = 0, None
    base_fs = annual_fs.get(py)
    for qi, code in enumerate(Q_CODE, 1):
        # 아직 제출 시기가 아닌 보고서는 묻지 않는다. 없는 것을 묻는 데도 CFS·OFS
        # 두 번이 나가는데, 전 종목이면 그것만으로 하루 한도의 4분의 1이다.
        if not _reprt_available(code, cur):
            continue
        d = fin(cur, code)
        if not d:
            continue
        # TTM·EPS·BPS·ROE 가 전부 이 시점을 기준으로 계산된다. 전년 같은 기간이나
        # 전년 연간과 기준(연결/별도)이 어긋나면 뺄셈이 성립하지 않으므로 채택하지
        # 않고 한 분기 앞의 보고서를 기준으로 남긴다. 분기 표만 막고 TTM 을 두면
        # 표는 1분기까지인데 PER 은 반기 기준인 상태가 된다.
        dp, fs = fin(py, code), d.get("_fs")
        if dp is not None and dp.get("_fs") != fs:
            continue
        if base_fs is not None and fs != base_fs:
            continue
        cur_qi, d_cur = qi, d
    # TTM 뺄셈의 짝 — 반드시 '전년 같은 기간' 누적이어야 뺄셈이 성립한다.
    # (반기까지 나왔으면 전년도 반기를 빼야지 전년도 1분기를 빼면 안 된다.)
    d_py_same = fin(py, Q_CODE[cur_qi - 1]) if cur_qi else None

    # 매출 폴백 — 보험·금융사는 전체 재무제표에 '매출액' 행이 없어
    # DART 요약재무(매출액/영업수익)로 보충한다.
    def rev_fallback(year, reprt):
        d = g._extract_fin(_dart_call(g._safe_finstate, dart, ticker, year, reprt))
        v = (d or {}).get("매출액")
        return v["cur"] if v else None

    for row in annual:
        if row["rev"] is None:
            row["rev"] = rev_fallback(row["year"], "11011")
            if row["rev"] and row["op"] is not None:
                row["opm"] = round(row["op"] / row["rev"] * 100, 1)

    # 보험사: 매출액이 전무하면 '보험수익'을 매출 행으로 사용(라벨도 전환)
    rev_label = None
    if all(row["rev"] is None for row in annual):
        ins_vals = {}
        for row in annual:
            ins_vals[row["year"]] = _cum(d_by_year.get(row["year"]), "rev_ins")
        if any(v is not None for v in ins_vals.values()):
            rev_label = {"ko": "보험수익", "en": "Insurance revenue"}
            for row in annual:
                row["rev"] = ins_vals.get(row["year"])
                row["opm"] = None  # 보험수익 대비 영업이익률은 비표준 → 미표시

    rev_key = "rev_ins" if rev_label else "rev"

    def diff(a, b, fa, fb):
        """누적 차감으로 단일 분기를 만든다.

        두 수치의 기준(연결/별도)이 다르면 만들지 않는다. 섞어서 빼면 결과가
        음수로 튀거나 — 더 나쁘게는 — 그럴듯한 오답이 되어 그대로 실린다.
        예: 상상인(038540)은 3분기 누적 5,225억인데 사업보고서 연간이 4,186억으로
            잡혀 4분기 매출이 −1,039억으로 나왔다.
        """
        if fa is not None and fb is not None and fa != fb:
            return None
        return _sub(a, b)

    def year_q(year, key, fy_total, fy_fs=None, getter=None):
        """그 해의 Q1~Q4 단일 분기값. 해당 보고서가 없으면 그 분기는 None."""
        if getter:                       # 요약재무 폴백 — 기준 표시가 없어 대조는 생략
            c1, ch, c9 = (getter(year, c) for c in Q_CODE)
            f1 = fh = f9 = None
        else:
            ds = [fin(year, c) for c in Q_CODE]
            c1, ch, c9 = (_cum(d, key) for d in ds)
            f1, fh, f9 = ((d or {}).get("_fs") for d in ds)
        return {f"{year}Q1": c1,
                f"{year}Q2": diff(ch, c1, fh, f1),
                f"{year}Q3": diff(c9, ch, f9, fh),
                f"{year}Q4": diff(fy_total, c9, fy_fs, f9)}

    def series(key, fy_key, years, getter=None):
        s = {}
        for y in years:
            s.update(year_q(y, key, (ann.get(y) or {}).get(fy_key), annual_fs.get(y), getter))
        return s

    def build(years):
        return (series(rev_key, "rev", years), series("op", "op", years),
                series("np_owner", "np_owner", years), series("np", "np", years))

    def window_of(years, *maps):
        """값이 있는 마지막 분기에서 5개를 거슬러 자른다.
        중간이 비어도 건너뛰지 않는다 — 시간축이 어긋나면 표가 거짓말을 한다."""
        labels = [f"{y}Q{i}" for y in years for i in (1, 2, 3, 4)]
        idx = [i for i, l in enumerate(labels) if any(m.get(l) is not None for m in maps)]
        if not idx:
            return []
        return labels[max(0, idx[-1] - 4): idx[-1] + 1]

    years = [py, cur]
    rev_q, op_q, npo_q, np_q = build(years)
    win = window_of(years, rev_q, op_q, npo_q, np_q)
    if len(win) < 5:            # 연초 등 — 두 해로 5개를 못 채우면 한 해 더 거슬러 올라간다
        years = [cur - 2] + years
        rev_q, op_q, npo_q, np_q = build(years)
        win = window_of(years, rev_q, op_q, npo_q, np_q)

    # 매출이 통째로 비면(보험·금융) 요약재무 기준으로 다시 만든다.
    # 차감 결과가 음수면 '누적 공시' 가정이 깨진 것이므로 채택하지 않는다.
    if win and all(rev_q.get(l) is None for l in win):
        cand = series(rev_key, "rev", years, getter=lambda yr, code: rev_fallback(yr, code))
        if not any(v is not None and v < 0 for v in cand.values()):
            rev_q = cand

    # 분기 '지배주주 순이익' 칸이 비면 전체 순이익으로 대신 채우고 있었다.
    # 자회사가 없는 회사(전체 = 지배)에서는 맞는 대체지만, 비지배지분이 있는
    # 회사에서는 표의 머리말과 다른 값을 넣는 셈이다. 그러면 그 분기만 크기가
    # 달라져 TTM 과도 어긋난다(한화손해보험 TTM 2,292억 vs 분기합 3,125억).
    # 연간에서 전체와 지배가 갈리는 회사면 대체하지 않는다 — 빈칸이 낫다.
    _has_nci = any(r.get("np") is not None and r.get("np_owner") is not None
                   and abs(r["np"] - r["np_owner"]) > abs(r["np"]) * 0.01
                   for r in annual)
    quarterly = [{"q": l, "rev": rev_q.get(l), "op": op_q.get(l),
                  "np_owner": (npo_q.get(l) if (npo_q.get(l) is not None or _has_nci)
                               else np_q.get(l))}
                 for l in win]

    # 마지막 방어 — 매출에는 있을 수 없는 값이 있다. 나오면 싣지 않는다.
    #   · 음수 매출: 누적 차감이 어긋난 것이지 실제 매출이 아니다
    #   · 그 해 연간 매출을 넘는 분기: 나머지 분기가 음수여야 성립하므로 불가능
    # 틀린 숫자를 보여 주느니 빈칸이 낫다. 빈칸은 의심이라도 하지만,
    # 그럴듯한 오답은 그대로 믿는다.
    for x in quarterly:
        rev, fy = x["rev"], (ann.get(int(x["q"][:4])) or {}).get("rev")
        if rev is None:
            continue
        if rev < 0 or (fy and fy > 0 and rev > fy * 1.02):
            x["rev"] = None

    # TTM 지배주주 순이익 = 전년 연간 − 전년 같은 기간 + 올해 같은 기간
    #   반기까지 나왔으면  FY2025 − 2025상반기 + 2026상반기
    #   올해 보고서가 아직 없으면 전년 연간이 곧 TTM
    def _npo(d):
        v = _cum(d, "np_owner")
        return v if v is not None else _cum(d, "np")

    # 화면에 실리는 분기 4개 합을 그대로 TTM 으로 쓴다.
    #
    # 롤포워드(작년연간 − 작년동기누적 + 올해동기누적)와 분기 4개 합은 대수적으로
    # 같은 값이다. 그런데 중간에 한쪽만 대체값을 쓰면(연결/별도 기준이 갈려 차감을
    # 못 하거나, 지배순이익 칸이 비어 전체 순이익으로 메워지거나) 두 값이 갈린다.
    # 그러면 화면 위의 TTM 과 바로 아래 분기표가 어긋난다 — 82종목이 그랬다.
    #
    # 사용자가 보는 것은 분기표다. 헤드라인을 표에 맞춘다. 분기 4개가 다 있을
    # 때만 쓰고, 하나라도 비면 아래 롤포워드로 내려간다(중간이 빈 경우엔 롤포워드가
    # 더 튼튼하다).
    ttm_np = None
    ttm_label = None
    _last4 = [x.get("np_owner") for x in quarterly[-4:]]
    if len(_last4) == 4 and all(v is not None for v in _last4):
        ttm_np = sum(_last4)
        ttm_label = f"{quarterly[-4]['q']}~{quarterly[-1]['q']}"

    fy_np = fy_row["np_owner"] if fy_row else None
    if ttm_np is None and fy_np is not None:
        if cur_qi:
            pv, cv = _npo(d_py_same), _npo(d_cur)
            if None not in (pv, cv):
                ttm_np = fy_np - pv + cv
                ttm_label = f"{py}Q{cur_qi + 1}~{cur}Q{cur_qi}"
        if ttm_np is None:   # 롤포워드도 안 되면 작년 연간 그대로
            # 작년 같은 기간이 없으면(상장 1년 미만 등) 뺄셈이 성립하지 않는다.
            # 그렇다고 비워 두면 EPS·PER·ROE 가 통째로 사라진다 — 31종목이
            # 그랬다. 작년 연간을 그대로 TTM 으로 쓴다(네이버도 그렇게 한다).
            ttm_np = fy_np
            ttm_label = f"{py}Q1~{py}Q4"

    # ── 단위 자동 보정 ──
    # 일부 기업은 재무제표를 천원·백만원 단위로 공시 → 우리는 원으로 읽어 값이 1,000/1,000,000배 작게 나온다.
    # 시가총액(원)을 기준으로 자본총계가 비현실적으로 작으면(=PBR이 비정상적으로 큼) 단위 배수를 감지해 전 금액에 곱한다.
    mcap_won = (stock.get("mcap") or 0) * 1e12
    ref_eq = _bs(d_cur, "equity_owner") or _bs(d_cur, "equity") or (fy_row.get("equity_owner") if fy_row else None)
    # ── 공시 통화 ──
    # 국내 상장 외국기업(9xxxxx)은 위안·달러로 공시한다. 그 숫자를 원으로
    # 두면 주당지표가 통째로 어긋난다 — 엑세스바이오 BPS 9원(PBR 250),
    # GRT BPS 68원(PBR 50.6). 주가는 원인데 자본은 달러·위안이었다.
    _d_ccy = d_cur if d_cur is not None else fin(py, "11011")
    ccy = str((_d_ccy or {}).get("_ccy") or "KRW").upper()
    # 아는 통화 코드일 때만 외화로 본다. DART 가 'KRW' 대신 다른 표기를 보내면
    # 전 종목이 외화로 잡혀 지표가 통째로 사라진다 — 그 사고를 막는 빗장이다.
    fx = 1.0
    if ccy in _FX_BAND:
        fx = fx_to_krw(ccy) or 0
        log(f"  💱 {ticker} 공시 통화 {ccy}"
            + (f" — 원화 환산 ×{fx:,.2f}" if fx else " — 환율을 구하지 못해 주당지표를 숨긴다"))
    elif ccy not in ("KRW", ""):
        log(f"  ⚠️ {ticker} 공시 통화 표기 '{ccy}' 를 모른다 — 원화로 본다")
        ccy = "KRW"
    ccy_unknown = bool(ccy in _FX_BAND and not fx)
    unit = fx or 1.0
    if mcap_won and ref_eq and ref_eq > 0:
        ratio = mcap_won / (ref_eq * unit)    # ≈ PBR. 정상 0.05~300, 그 이상이면 단위 축소 의심
        if ratio > 300:
            for f in (1000, 1_000_000):
                if 0.05 <= mcap_won / (ref_eq * unit * f) <= 300:
                    unit *= f
                    break
    if unit != 1:
        log(f"  [단위보정] {ticker} ×{unit:,.4g}"
            f" ({'환율 환산 포함 · ' if fx and fx != 1 else ''}천원/백만원 단위 공시 추정)")
        money = ("rev", "op", "np", "np_owner", "equity", "equity_owner", "equity_nci", "cfo", "liab", "assets")
        for row in annual:
            for k in money:
                if row.get(k) is not None:
                    row[k] = row[k] * unit
        for row in quarterly:
            for k in ("rev", "op", "np_owner"):
                if row.get(k) is not None:
                    row[k] = row[k] * unit
        if ttm_np is not None:
            ttm_np *= unit

    # ── 규모 방어: 한 분기에 여러 기간이 뭉쳐 들어온 것을 잡는다 ────────
    # 앞의 방어는 '그 해 연간 매출' 과 견주는데, 올해는 연간이 아직 없어서
    # 그냥 통과한다. 진코스텍 2026Q2 매출이 30.9조로 실려 있었다 — 시가총액이
    # 719억인 회사다. 직전 연간의 3배를 넘고 동시에 시가총액의 5배도 넘으면
    # 매출로 성립할 수 없는 크기다. 두 조건을 모두 걸어야 매출이 0 에서
    # 뛰는 신약개발사(큐라클·바이젠셀)를 잘못 지우지 않는다.
    _ann_by_year = {r["year"]: r for r in annual}
    for x in quarterly:
        rev = x.get("rev")
        if rev is None or rev <= 0 or not mcap_won:
            continue
        _y = int(x["q"][:4])
        base = ((_ann_by_year.get(_y) or {}).get("rev")
                or (_ann_by_year.get(_y - 1) or {}).get("rev"))
        if base and base > 0 and rev > base * 3 and rev > mcap_won * 5:
            log(f"  ❌ {x['q']} 매출 {rev/1e8:,.0f}억 — 직전 연간 {base/1e8:,.0f}억 의 "
                f"{rev/base:.0f}배 · 시가총액 {mcap_won/1e8:,.0f}억 의 {rev/mcap_won:.0f}배 → 숨김")
            x["rev"] = x["op"] = None

    # ── 페이지 스스로의 증인 ─────────────────────────────────────────
    # TTM 순이익이 바로 아래 분기표 4개 합과 맞으면, 그 숫자는 외부 참조값
    # 없이도 확인된 것이다. 아래에서 '숨길까 말까' 를 정할 때 이 값을 쓴다.
    # 지금까지는 이런 증인이 없어서, 회사가 낸 두 값이 어긋나기만 하면
    # EPS 를 숨겼고 BPS 까지 딸려 숨겨졌다(EPS 108 · BPS 113종목).
    # 두 기간이 같을 때만 견준다. TTM 이 롤포워드가 아니라 '작년 연간' 으로
    # 물러난 경우(상장 1년 미만)에는 분기표 마지막 4개와 기간이 달라서,
    # 그대로 비교하면 맞는 값을 틀렸다고 하거나 그 반대가 된다.
    _q4 = [x.get("np_owner") for x in quarterly[-4:]]
    q4_sum = sum(_q4) if (len(_q4) == 4 and all(v is not None for v in _q4)) else None
    _same_window = bool(quarterly and ttm_label
                        and quarterly[-1].get("q") == ttm_label.split("~")[-1])
    ttm_verified = bool(ttm_np and q4_sum and _same_window
                        and abs(ttm_np / q4_sum - 1) <= 0.10)

    # KRX 가 매일 내는 공식 BPS. 네이버와 달리 분기 반영이 늦지 않아
    # BPS 를 검증할 독립 잣대가 된다.
    try:
        bps_krx_ref = float((krx_row or {}).get("BPS"))
        bps_krx_ref = bps_krx_ref if bps_krx_ref > 0 else None
    except Exception:
        bps_krx_ref = None

    price = stock.get("price")
    sh = stock.get("shares") or 0          # KRX 발행주식수(정확)
    total_sh = dart_total_shares(dart, ticker) or sh
    # DART 주식총수(보통주+우선주)가 KRX 상장주식수(보통주)와 다른 것은 정상이다.
    #   삼성전자 1.15배 · 현대차 1.30배 · LG화학 1.11배 — 우선주 몫이다.
    # 그래서 여기를 좁게 잠그면 안 된다. 실제로 5% 로 좁혀 보니 삼성전자의
    # 가중평균주식수(65.9억)가 KRX 보통주(58.5억)의 1.05배를 넘어 버려져
    # BPS 가 85,687 → 96,663 으로 틀어졌다(네이버는 85,687).
    #
    # 잡아야 할 것은 '정확히 정수배' 다 — 같은 구분이 여러 줄로 와서 중복
    # 집계된 흔적이다. 우선주 때문에 생기는 비율은 1.11·1.15·1.30 처럼
    # 어중간하지 정확히 2.000 이 되지 않는다.
    if sh and total_sh:
        r = total_sh / sh
        dup = any(abs(r - n) < 0.005 for n in range(2, 11))
        if dup or not (0.5 * sh <= total_sh <= 3 * sh):
            log(f"  · 발행주식총수 DART {total_sh:,} ↔ KRX {sh:,} ({r:.3f}배) — KRX 를 쓴다")
            total_sh = sh

    # 가중평균 유통주식수 = 회사 공시 (지배주주 순이익 ÷ 공시 기본EPS) 로 역산.
    #   네이버·토스가 쓰는 분모와 같아져 EPS·PER이 일치한다. 자기주식이 자동 제외됨.
    #   최근 시점 우선(올해 Q1 → 직전 연간). 둘 다 없으면 발행주식총수로 폴백.
    def implied_wavg(npo, eps):
        if npo and eps and abs(eps) > 1:
            w = npo / eps
            if w > 0 and 0.3 * total_sh <= w <= 1.05 * total_sh:  # 상식 범위(자기주식 차감 고려)
                return w
        return None

    wavg = (implied_wavg(_cum(d_cur, "np_owner"), _cum_eps(d_cur))
            or (implied_wavg(fy_row["np_owner"], fy_row["eps_basic"]) if fy_row else None))

    # EPS(TTM): 1순위 = 회사 공시 기본주당이익(EPS) 직접 합산(최근결산 − 작년1Q + 올해1Q).
    #   순이익·주식수 추출을 건너뛰어 가장 견고하고, 네이버와 동일 기준(회사 공시 EPS).
    #   2순위(공시 EPS 누락 시) = 지배순이익 ÷ 발행주식총수.
    fy_eps = fy_row.get("eps_basic") if fy_row else None
    qp_eps = _cum_eps(d_py_same)
    qc_eps = _cum_eps(d_cur)
    # 단위 보정: 천원/백만원 공시 기업은 EPS도 같은 단위로 공시된다(예: 두산밥캣 '4.14'=4,140원).
    #   금액과 달리 EPS는 위 money 보정에서 빠져 있어 따로 곱한다.
    if unit != 1:
        fy_eps = fy_eps * unit if fy_eps is not None else None
        qp_eps = qp_eps * unit if qp_eps is not None else None
        qc_eps = qc_eps * unit if qc_eps is not None else None

    # ── 액면분할·병합 보정 ────────────────────────────────────────────
    # 뺄셈이 성립하려면 세 값이 같은 주식수를 기준으로 해야 한다. 그 사이에
    # 액면분할을 하면 옛 값만 기준이 달라, 그대로 빼고 더하면 단위가 다른
    # 것을 섞는 셈이 된다.
    #
    #   LS ELECTRIC  9,647 − 4,610 + 1,607 = 6,644   (실제는 2,613)
    #
    # 각 기간의 '순이익 ÷ 그 기간 공시 주당이익' 이 곧 그때의 주식수다.
    # 옛 기간 대비 몇 배가 됐는지가 분할 배수이고, 그 배수로 옛 주당이익을
    # 나누면 현재 기준이 된다. LS ELECTRIC 은 4.96배(=5:1 분할)로 잡힌다.
    #
    # 유상증자처럼 어중간한 비율까지 건드리면 멀쩡한 값을 망가뜨리므로,
    # 정수배(또는 그 역수) 근처일 때만 손댄다 — 분할·병합의 지문이다.
    def _sh_at(npo, eps_v):
        return (npo / eps_v) if (npo and eps_v and abs(eps_v) > 1) else None

    _n_cur, _n_py = _npo(d_cur), _npo(d_py_same)
    sh_cur = _sh_at(_n_cur * unit if _n_cur is not None else None, qc_eps)
    sh_py = _sh_at(_n_py * unit if _n_py is not None else None, qp_eps)
    sh_fy = _sh_at(fy_row.get("np_owner") if fy_row else None, fy_eps)

    def _unsplit(eps_v, sh_old, label):
        if not (eps_v and sh_cur and sh_old):
            return eps_v
        r = sh_cur / sh_old
        for n in range(2, 41):
            for c in (float(n), 1.0 / n):
                if abs(r / c - 1) < 0.05:
                    log(f"  ⚖️ 주식수가 {r:.2f}배로 바뀌었다(액면분할·병합) — "
                        f"{label} 주당이익 {eps_v:,.0f} → {eps_v / c:,.0f}")
                    return eps_v / c
        return eps_v

    fy_eps = _unsplit(fy_eps, sh_fy, "작년연간")
    qp_eps = _unsplit(qp_eps, sh_py, "작년동기누적")

    eps_disc = (fy_eps - qp_eps + qc_eps) if None not in (fy_eps, qp_eps, qc_eps) else (fy_eps if not cur_qi else None)

    # 액면병합·감자를 한 회사에서는 위 뺄셈이 성립하지 않는다.
    # 작년 연간 주당이익은 옛 주식수 기준이고 올해 누적은 새 주식수 기준인데,
    # 그대로 더하고 빼면 단위가 다른 것을 섞는 셈이다. 실제로 30종목에서
    # 공시 주당이익과 '순이익÷주식수' 가 정확히 2·3·7·9배로 갈렸다.
    #
    # 순이익은 주당이 아니라 총액이고 주식수는 현재 기준이므로, 그 길은
    # 기준이 섞이지 않는다. 두 길이 30% 넘게 벌어지고 그 차이가 배수로
    # 떨어지면 순이익 쪽을 쓴다. 배수로 안 떨어지면 원인이 다른 것이므로
    # 건드리지 않는다.
    eps_alt = (ttm_np / (wavg or total_sh)) if (ttm_np and (wavg or total_sh)) else None
    eps_hidden = False
    eps_pick = eps_disc
    eps_src = "공시"     # 공시 주당이익 롤포워드 | 순이익÷주식수
    if eps_disc and eps_alt and abs(eps_disc - eps_alt) > 0.30 * max(abs(eps_disc), abs(eps_alt)):
        r = abs(eps_alt / eps_disc)
        if any(abs(r / c - 1) < 0.05 for n in range(2, 41) for c in (float(n), 1.0 / n)):
            log(f"  ⚠️ 주당이익 기준이 섞였다(공시 {eps_disc:,.0f} vs 순이익÷주식수 "
                f"{eps_alt:,.0f}, {r:.1f}배) — 액면병합·감자로 본다. 순이익 쪽을 쓴다.")
            eps_pick = eps_alt
            eps_src = "순이익÷주식수"
        elif ttm_verified:
            # 배수로는 안 떨어지지만, 순이익 쪽은 바로 아래 분기표 4개 합과
            # 맞는다 — 페이지 안에서 확인된 값이다. 공시 주당이익은 확인할
            # 방법이 없다(그 값 하나뿐이다). 확인된 쪽을 쓴다.
            #
            # 예전에는 여기서 둘 다 버렸다. 그런데 이 갈림길은 대개 이익이
            # 0 근처인 회사에서 생긴다 — 분자가 0 에 가까우면 비율은 조금만
            # 움직여도 30% 를 넘는다(금비 TTM −0.6억). 정상인 회사를 통째로
            # 지우고 있었고, BPS 까지 딸려 나갔다.
            log(f"  · 두 공시가 어긋난다(공시 {eps_disc:,.0f} vs 순이익÷주식수 "
                f"{eps_alt:,.0f}, {r:.2f}배) — 분기표와 맞는 순이익 쪽을 쓴다")
            eps_pick = eps_alt
            eps_src = "순이익÷주식수"
        else:
            # 순이익 쪽도 확인이 안 된다. 어느 쪽이 맞는지 알 길이 없다.
            # 모르면 안 보여준다 — 틀린 숫자보다 빈칸이 낫다.
            log(f"  ❌ 두 공시가 어긋나고 분기표로도 확인이 안 된다(공시 "
                f"{eps_disc:,.0f} vs 순이익÷주식수 {eps_alt:,.0f}, {r:.2f}배) — EPS·PER 숨김")
            eps_pick = None
            eps_disc = None
            eps_hidden = True
    if eps_pick is None:
        eps_src = "순이익÷주식수"
    eps_ttm = eps_pick if eps_pick is not None else (
        None if eps_hidden else ((ttm_np / total_sh) if (ttm_np and total_sh) else None))
    # int() 는 0 쪽으로 자른다. 지엘팜텍 -6.9 → -6 이 됐고, 거꾸로 곱하면 순이익과
    # 13% 어긋나 항등식 검산에 걸렸다. 화면은 정수 원이므로 반올림한다.
    eps_ttm = round(eps_ttm) if eps_ttm is not None else None
    # 소수 첫째 자리로 자르면 PER 이 작을 때 주가÷EPS 와 10% 까지 벌어진다
    # (삼부토건 0.452 → 0.5). 화면은 어차피 오늘 주가로 다시 계산하니, 저장값은
    # 항등식이 성립하도록 넉넉히 남긴다.
    per_ttm = round(price / eps_ttm, 3) if (eps_ttm and eps_ttm > 0 and price) else None

    # EPS 가 어디서 나왔는지 남긴다. 지주회사 20여 곳에서 네이버와 1.5~3.7배
    # 차이가 나는데, 나눗셈은 맞으니 들어가는 값이 다르다는 뜻이다. 결과만
    # 봐서는 '공시 EPS 를 그대로 썼는지' 와 '순이익÷주식수로 때웠는지' 가
    # 구분이 안 돼 원인을 좁힐 수가 없었다.
    log(f"  · EPS 입력: 공시롤포워드="
        f"{'없음' if eps_disc is None else f'{eps_disc:,.0f}'}"
        f"(작년연간 {fy_eps if fy_eps is None else f'{fy_eps:,.0f}'}"
        f" − 작년동기누적 {qp_eps if qp_eps is None else f'{qp_eps:,.0f}'}"
        f" + 올해누적 {qc_eps if qc_eps is None else f'{qc_eps:,.0f}'})"
        f" · 대안=순이익÷발행총수 "
        f"{round(ttm_np/total_sh) if (ttm_np and total_sh) else '없음'}"
        f" → 채택 {eps_ttm}")

    # ── 자체 대조: 회사가 낸 두 값이 서로 크기를 확인해 주는가 ──────────────
    # 외부 참조값은 분기를 늦게 반영해서 '크기' 를 재는 잣대로 못 쓴다. 대신
    # 회사가 낸 두 값을 서로 맞춰 본다.
    #
    #   ① 공시 기본주당이익 롤포워드      ② 지배순이익 ÷ 발행주식총수
    #
    # 둘은 들어가는 값이 겹치지 않는다(①은 주당 공시, ②는 총액과 주식총수).
    # 한쪽만 단위·자릿수를 잘못 집으면 반드시 어긋난다.
    #
    # 허용 폭은 3.3배로 넓게 둔다. 자기주식이 많은 회사에서는 ②의 분모가
    # 실제 유통주식수보다 커서 값이 낮게 나온다 — SK 는 자기주식이 24%다.
    # 여기서 잡으려는 건 그런 차이가 아니라 1,000배 오류다.
    #
    # 주의: eps_alt 는 가중평균주식수를 쓰는데, 그 주식수 자체가 공시 EPS 로
    # 역산한 값이라 ①과 순환한다. 그래서 여기서는 발행총수로 나눈 값을 쓴다.
    # 직전 분기까지만 넣었으면 얼마였을지도 남긴다. 참조값이 이 값과
    # 같으면 그쪽이 한 분기 뒤에 있다는 뜻이고, 그러면 우리가 틀린 게
    # 아니라 그쪽이 아직 안 따라온 것이다. 추측으로 답하지 않으려고
    # 숫자를 남긴다.
    if fy_eps is not None and qp_eps is not None and qc_eps is not None:
        log(f"  · 직전분기 기준이면 EPS {fy_eps:,.0f}"
            f" (작년연간 그대로 · 올해 {qc_eps:,.0f} 를 아직 안 넣은 상태)")

    eps_indep = (ttm_np / total_sh) if (ttm_np and total_sh) else None
    eps_self_ok = bool(
        eps_disc and eps_indep and (eps_disc > 0) == (eps_indep > 0)
        and (1 / 3.3) <= abs(eps_indep / eps_disc) <= 3.3)
    # 회사가 기본주당이익을 아예 공시하지 않으면 위 대조가 성립하지 않는다.
    # 그러면 참조값 게이트가 그대로 걸려, 적자 전환·흑자 전환한 회사의 EPS 가
    # 부호 반대로 잘려 나갔다(17종목). 분기표와 맞는 것도 똑같이 유효한
    # 자체 검증이다.
    eps_self_ok = eps_self_ok or ttm_verified

    # ROE 신뢰성: 순이익 추출(ttm_np)이 깨졌을 때만 공시 EPS 로 되살린다.
    #   원래는 30% 만 어긋나도 'eps_disc × 발행주식총수' 로 덮어썼는데, 두 군데가 틀렸다.
    #     ① 분모가 짝이 안 맞는다. 공시 기본주당이익은 가중평균 유통주식수로 나눈 값이라
    #        발행주식총수를 도로 곱하면 자기주식만큼 부풀어 오른다(SK 는 자기주식이 24%다).
    #     ② 30% 는 너무 좁다. 멀쩡히 추출된 순이익이 그 부풀린 값으로 덮여, 리포트 안에서
    #        TTM 순이익이 바로 아래 분기표의 4개 분기 합과 어긋났다 — 2,287곳 중 162곳(7.1%).
    #   그래서 분모를 가중평균으로 바꾸고, 부호가 뒤집히거나 3배 넘게 벌어질 때만 —
    #   즉 추출이 실제로 깨졌을 때만 — 갈아끼운다(원익QnC 등 원래 잡으려던 경우).
    #   ③ 분기표 4개 합과 이미 맞는 순이익은 손대지 않는다. 확인된 값을
    #      덮어쓰면 화면 위아래가 어긋나고, 그러면 검산에서 다시 걸린다.
    #   ④ 위에서 공시 주당이익을 버리고 순이익÷주식수를 택했으면(액면병합·감자,
    #      또는 분기표와 맞는 쪽) 여기서 그 공시값으로 순이익을 덮어쓰면 안 된다.
    #      보해양조가 그랬다 — 5:1 병합으로 공시 EPS 25 는 옛 주식수 기준이라
    #      EPS 는 126(순이익÷주식수)을 택해 놓고, 바로 아래에서 TTM 순이익을
    #      25 × 27.6M = 7억으로 갈아 끼웠다(실제 35억). 같은 리포트 안에서
    #      EPS 와 TTM 이 서로 5배 어긋나 항등식 검산에 걸렸다.
    np_denom = wavg or total_sh
    if not ttm_verified and eps_disc is not None and np_denom and eps_src == "공시":
        implied_np = eps_disc * np_denom
        broken = implied_np and (
            ttm_np is None
            or (ttm_np > 0) != (implied_np > 0)
            or not ((1 / 3) <= abs(ttm_np / implied_np) <= 3))
        if broken:
            log(f"  · 순이익 추출 {'없음' if ttm_np is None else f'{ttm_np/1e8:,.0f}억'} 이 "
                f"공시 EPS 환산 {implied_np/1e8:,.0f}억 과 어긋난다 — 공시값을 쓴다")
            ttm_np = implied_np

    bps_denom = wavg or total_sh
    # 지배지분이 잡히면 그것, 아니면 총자본. 어느 쪽을 썼는지 남긴다 —
    # 비지배지분이 큰 지주·보험에서 폴백이 걸리면 BPS 가 통째로 부풀어
    # 오르는데, 결과만 보면 자본이 늘어난 것과 구분이 안 된다.
    eqo_owner = _bs(d_cur, "equity_owner")
    eqo_total = _bs(d_cur, "equity")
    eqo_owner = _owner_equity(eqo_owner, eqo_total, _bs(d_cur, "equity_nci"))
    eq_src = "분기말"
    # 분기 재무상태표에서 지배지분 태그를 못 읽었는데 비지배지분이 큰 회사는 자본총계로
    # 대신하면 안 된다. SKC 는 자본총계 2.03조 중 비지배가 1.19조라 BPS 가 52,663
    # (KRX 22,956)으로 2.4배가 됐다 — 34종목이 그랬다. 비지배지분은 분기에 크게
    # 움직이지 않으므로 결산 비지배지분을 빼서 지배지분으로 본다.
    if eqo_owner is None and eqo_total is not None and fy_row:
        _fy_nci, _fy_eq = fy_row.get("equity_nci"), fy_row.get("equity")
        if _fy_nci and _fy_eq and abs(_fy_nci) > abs(_fy_eq) * 0.01:
            eqo_owner = eqo_total - _fy_nci / unit       # 연간 값은 이미 단위보정됐다
            eq_src = "분기말·결산 비지배지분 차감"
            log(f"  · 분기 지배지분 태그 없음 — 자본총계 {eqo_total * unit / 1e12:,.2f}조에서 "
                f"결산 비지배지분 {_fy_nci / 1e12:,.2f}조를 뺀다")
    eqo_q = (eqo_owner or eqo_total)
    if eqo_q is not None:
        eqo_q *= unit
    if eqo_q is None and fy_row:
        # 분기 재무상태표에서 자본을 못 집는 회사가 272곳이었다. 연간에는
        # 값이 있는데 분기 보고서 형식이 달라 놓치는 경우다.
        #
        # 자본은 이익과 달리 분기마다 크게 뛰지 않는다. 직전 결산 자본으로
        # 대신한다 — 네이버도 새 분기가 안 나왔을 때는 그렇게 한다. 빈칸보다
        # 낫고, 다음 분기에 값이 잡히면 저절로 갱신된다.
        eqo_q = fy_row.get("equity_owner") or fy_row.get("equity")   # 이미 단위보정됨
        eq_src = f"{fy_row['year']}년말"
    # 자본잠식(자본 ≤ 0)이면 BPS·PBR은 무의미 → 숨김
    # EPS 를 숨겼다는 건 주식수(가중평균)를 못 믿는다는 뜻이다. BPS 도 같은
    # 분모로 나눈 값이므로 같이 숨긴다. 이마트가 그랬다 — 분모가 1,600만주로
    # 잡혀(실제 2,760만주) BPS 824,830원·PBR 0.09 가 나왔다. 주가는 7만원대다.
    bps_q = (None if eps_hidden
             else (round(eqo_q / bps_denom) if (eqo_q and eqo_q > 0 and bps_denom) else None))
    log(f"  · BPS 입력: 자본 {(eqo_q or 0)/1e12:,.1f}조"
        f"({eq_src}·{'지배지분' if eqo_owner else ('총자본-폴백' if eqo_total else '연간폴백')})"
        f" ÷ 주식수 {(bps_denom or 0)/1e6:,.0f}백만"
        f"({'가중평균' if wavg else '발행총수'}) = BPS {bps_q}")
    pbr_q = round(price / bps_q, 4) if (bps_q and price) else None   # 위와 같은 이유

    # ── 분모가 맞는지 KRX 에게 물어본다 ──────────────────────────────────
    # EPS 와 BPS 를 같은 분모(가중평균 유통주식수)로 나누고 있다. EPS 는 그게
    # 맞다 — 한 해 동안 번 돈이니 그 기간의 평균 주식수로 나눠야 한다.
    #
    # BPS 는 아니다. 자본은 '지금 이 시점' 값이라 '지금 이 시점' 주식수로
    # 나눠야 한다. 연중에 주식을 크게 늘린 회사는 둘이 크게 벌어진다.
    #
    #     태영건설  발행총수 298,240,052 · 가중평균 159,368,756 (1.87배)
    #               우리 BPS 3,673 · KRX 공식 BPS 2,037
    #
    #     자본을 절반의 주식수로 나눠 BPS 가 1.8배가 됐다. BPS 가 크면 PBR 은
    #     그만큼 작아진다 — 실제보다 싸 보인다. 2,563종목 중 58종목이 그랬다.
    #
    # 그렇다고 '기말 주식수를 써라' 로 바꾸면 안 된다. KRX 가 무엇으로 나누는지
    # 재 봤더니 한 가지가 아니었다 — 판별력 있는 523종목에서 가중평균 382건,
    # 발행총수 119건이었다. KRX 는 '발행주식수 − 자기주식' 을 쓰는데, 자기주식이
    # 많으면 가중평균과 비슷해지고 연중 증자하면 발행총수와 비슷해진다. 우리는
    # 자기주식 수를 따로 갖고 있지 않아 미리 알 수가 없다.
    #
    # 그래서 규칙으로 정하지 않고 거꾸로 나눠 물어본다.
    #
    #     KRX 가 나눈 주식수 = 최근 결산 지배지분 ÷ KRX 가 공표한 BPS
    #
    # 역산한 수가 우리 후보 중 하나와 3% 안에서 맞고 우리 분모는 8% 넘게
    # 벗어날 때만 바꾼다. 분자(분기말 자본)는 그대로 둔다 — 그게 KRX 보다
    # 나은 점이다.
    if bps_q and bps_krx_ref and bps_krx_ref > 0 and price and fy_row:
        _fy_eqo = fy_row.get("equity_owner") or fy_row.get("equity")
        if _fy_eqo and _fy_eqo > 0 and abs(bps_q / bps_krx_ref - 1) > 0.15:
            _implied = _fy_eqo / bps_krx_ref
            _cands = {"발행총수": total_sh, "가중평균": wavg, "시장주식수": sh}
            _cands = {k: v for k, v in _cands.items() if v}
            if _cands:
                _best = min(_cands, key=lambda k: abs(_cands[k] / _implied - 1))
                _gap_best = abs(_cands[_best] / _implied - 1)
                _gap_ours = abs(bps_denom / _implied - 1)
                if _gap_best <= 0.03 and _gap_ours > 0.08:
                    _new = round(eqo_q / _cands[_best])
                    if _new > 0 and abs(_new / bps_krx_ref - 1) < abs(bps_q / bps_krx_ref - 1):
                        log(f"  · BPS 분모를 바꾼다: {'가중평균' if wavg else '발행총수'} "
                            f"{bps_denom:,} → {_best} {_cands[_best]:,} "
                            f"(KRX 공식 BPS {bps_krx_ref:,.0f} 를 재현하는 주식수). "
                            f"BPS {bps_q:,} → {_new:,}")
                        bps_q = _new
                        bps_denom = _cands[_best]
                        pbr_q = round(price / bps_q, 4)

    # ROE(TTM) = 최근 4개 분기 지배순이익 ÷ 평균 지배자본(TTM 시작시점~끝시점) — 토스와 정합
    fy_eqo = fy_row.get("equity_owner") if fy_row else None       # 이미 단위보정됨(annual 일괄)

    # ── 자본 정합성: BPS 를 외부 참조값 대신 '스스로' 검증한다 ──────────────
    # 외부 참조값(네이버)은 분기 반영이 늦고, 늦는 정도가 항목마다 다르다.
    # 2026 반기를 재 보니 EPS 는 477종목이 갱신됐는데 BPS 는 162종목뿐이었다.
    # 참조값에 기대면 우리가 맞는데도 시차 때문에 지표가 지워진다.
    #
    # 그래서 재무상태표 자체의 항등식으로 본다 — 지배지분은 자본총계를 넘을 수
    # 없다. 태그를 잘못 집으면 이 관계가 깨지므로, 깨졌을 때만 숨긴다.
    #
    # 처음에는 '자본 증가가 순이익으로 설명되는가' 로 짰다가 되돌렸다.
    # 삼성생명이 2.24배로 걸렸는데 DART 원문을 떠 보니 지배지분 144.84조 ·
    # 비지배지분 2.12조 · 자본총계 146.96조로 우리 추출이 정확했다. 보험사는
    # IFRS17 할인율 변동으로 기타포괄손익이 순이익의 수십 배로 움직여서
    # 이익으로 자본을 설명하려는 전제 자체가 성립하지 않는다. 맞는 값을
    # 지우는 검증은 없는 것만 못하다.
    # 앞서 순이익에서 저지른 것과 똑같은 실수가 여기에도 있었다.
    #
    #     |지배지분| ≤ |자본총계| × 1.01   ← 틀린 전제
    #
    # 지배지분 = 자본총계 − 비지배지분이다. 자회사가 결손이 쌓여 비지배지분이
    # 음수가 되면 지배지분이 자본총계보다 커진다 — 정상이다. 이 검사에
    # 걸려 272종목의 BPS·PBR 이 통째로 사라지고 있었다(동부건설·EG·
    # 티움바이오·그린플러스 등).
    #
    # 옳은 검사는 크기 비교가 아니라 항등식이다.
    #
    #     지배지분 + 비지배지분 = 자본총계
    #
    # 비지배지분을 못 읽는 회사는 확인할 길이 없으므로, 자릿수가 틀린
    # 수준(1.5배 초과)일 때만 막는다.
    eq_nci = _bs(d_cur, "equity_nci")
    eq_broken = False
    if bps_q and eqo_owner and eqo_total:
        if eq_nci is not None:
            gap = abs((eqo_owner + eq_nci) - eqo_total)
            broken = gap > abs(eqo_total) * 0.01
        else:
            broken = eqo_owner > eqo_total * 1.5
        if broken and bps_krx_ref and abs(bps_q / bps_krx_ref - 1) <= 0.30:
            # 항등식은 깨졌는데 우리가 낸 BPS 는 KRX 공식값과 맞는다.
            # 그러면 자본 추출이 아니라 비지배지분 태그를 못 읽은 쪽이 문제다.
            # 맞는 값을 지우는 검증은 없는 것만 못하다 — 살린다.
            log(f"  · 자본 항등식은 깨졌지만 BPS {bps_q:,} 가 KRX 공식값 "
                f"{bps_krx_ref:,.0f} 과 맞는다 — 그대로 쓴다")
            broken = False
        if broken:
            log(f"  ❌ 자본 정합성 실패 → BPS·PBR 숨김: 지배지분 "
                f"{eqo_owner * unit/1e12:,.2f}조 + 비지배지분 "
                f"{(eq_nci or 0) * unit/1e12:,.2f}조 ≠ 자본총계 "
                f"{eqo_total * unit/1e12:,.2f}조")
            bps_q = pbr_q = None
            eq_broken = True

    # 이익으로 설명되지 않는 자본 변동은 막지 않되 로그로는 남긴다. 대개
    # 기타포괄손익·유상증자지만, 추출 오류를 뒤늦게 되짚을 때 실마리가 된다.
    cur_np = sum(x["np_owner"] for x in quarterly
                 if x.get("np_owner") and str(x.get("q", "")).startswith(str(cur)))
    if bps_q and fy_eqo and fy_eqo > 0 and eqo_q:
        explained = fy_eqo + cur_np
        if explained > 0 and eqo_q > explained * 1.5:
            log(f"  ⚠️ 자본이 이익보다 빠르게 늘었다(참고): 분기말 지배자본 "
                f"{eqo_q/1e12:,.1f}조 vs 이익으로 설명되는 {explained/1e12:,.1f}조 "
                f"({eqo_q/explained:.2f}배)")
    # 여기까지 와서도 BPS 가 비어 있으면 KRX 가 매일 내는 공식 BPS 를 쓴다.
    # 거래소가 산출·공표하는 값이라 출처가 분명하고, 네이버와 달리 분기
    # 반영이 늦지 않다. 우리가 못 뽑았다고 빈칸으로 두는 것보다 낫다.
    bps_src = "자체"
    if bps_q is None and bps_krx_ref and price:
        bps_q = round(bps_krx_ref)
        pbr_q = round(price / bps_q, 4)
        bps_src = "KRX"
        log(f"  · BPS 를 자체 산출하지 못해 KRX 공식값 {bps_q:,} 을 쓴다")

    # BPS 도 자체 증인을 둔다. KRX 공식값과 30% 안에서 맞으면 참조값(네이버)
    # 대조는 건너뛴다 — 네이버 BPS 는 분기 반영이 가장 늦어, 우리가 맞는데도
    # 시차 때문에 지워지는 일이 가장 많았다.
    bps_self_ok = bool(bps_q and bps_krx_ref and abs(bps_q / bps_krx_ref - 1) <= 0.30)

    eqo_begin = (_bs(d_py_same, "equity_owner") or _bs(d_py_same, "equity"))  # TTM 시작(전년 같은 분기말) 자본
    if eqo_begin is not None:
        eqo_begin *= unit
    # 자본이 양(+)일 때만 ROE 산출 — 자본잠식이면 ROE는 무의미(예: 1057%)라 숨김
    def _roe(eq): return round(ttm_np / eq * 100, 1) if (ttm_np is not None and eq and eq > 0) else None
    avg_win = ((eqo_begin + eqo_q) / 2) if (eqo_begin and eqo_q and (eqo_begin + eqo_q) > 0) else None
    roe_ttm = _roe(avg_win) or _roe(fy_eqo) or _roe(eqo_q)

    valuation = {
        "price": price, "mcap": stock.get("mcap"), "shares": stock.get("shares"),
        "total_shares": total_sh, "wavg_shares": int(wavg) if wavg else None,
        "per": per_ttm, "eps": eps_ttm,          # 최근 4개 분기 순이익 ÷ 가중평균유통주식수 (네이버 방식)
        "pbr": pbr_q, "bps": bps_q,              # 최근 분기말 지배주주 자본 ÷ 유통주식수 (네이버 방식)
        "roe_ttm": roe_ttm,                      # 헤드라인 ROE(최근 4분기 ÷ 평균자본)
        "ttm_window": ttm_label if ttm_np else None,
        "ttm_np_owner": ttm_np,
        "ccy": ccy,                              # 공시 통화(원화 환산 후에도 출처를 남긴다)
        "_eps_self": eps_self_ok,                # 검증용 임시 플래그 — cross_check 에서 떼어낸다
        "_bps_self": bps_self_ok,                # 〃 (KRX 공식 BPS 와 맞는가)
        "bps_src": bps_src,                      # 자체 산출인지 KRX 공식값인지
        "eps_src": eps_src if eps_ttm is not None else None,   # 공시 롤포워드인지 순이익÷주식수인지
        "pbr_krx": None, "bps_krx": None,        # KRX 공식값(참고·대조용)
        "basis": "PER·EPS·PBR·BPS 모두 자체 산출(네이버·토스와 동일 방식) · 배당은 DART 공시 주당현금배당금(보완:KRX) ÷ 현재가",
    }
    # 환율을 못 구했으면 주당지표를 내지 않는다. 외화 숫자를 원으로 두면
    # 주가와 견줄 수 없다 — 틀린 배수를 보여 주느니 빈칸이 낫다.
    if ccy_unknown:
        for k in ("eps", "per", "bps", "pbr"):
            valuation[k] = None

    # 배당: DART 공시 주당현금배당금(보통주) 우선, 실패 시 KRX DPS 보완.
    #   현재가 기준으로 배당수익률 산출. DPS=0 은 '무배당'(유효)로 보존.
    dps = dart_dps(dart, ticker)
    if dps is None and krx_row is not None:
        try:
            dps = round(float(krx_row.get("DPS")), 1)
        except Exception:
            dps = None
    valuation["dps"] = round(dps, 1) if dps is not None else None
    valuation["div"] = round(dps / price * 100, 2) if (dps is not None and price) else None
    # PBR·BPS 의 KRX 공식값은 참고·대조용으로만 보관.
    if krx_row is not None:
        for src, dst in (("PBR", "pbr_krx"), ("BPS", "bps_krx")):
            try:
                v = float(krx_row.get(src))
                valuation[dst] = v if v > 0 else None
            except Exception:
                valuation[dst] = None

    # 빈칸에는 이유가 있다. 화면이 '—' 만 보여 주면 독자는 데이터가 없는지 회사가
    # 이상한지 모른다. 코드로 남기고 화면(stock.html)이 문장으로 풀어 보여 준다.
    #   loss 적자 · fx 환율 없음 · shares 주식수 없음 · mismatch 회사 공시 간 불일치 ·
    #   no_income 순이익 없음 · impaired 자본잠식 · equity_check 자본 항등식 불일치 ·
    #   no_equity 자본 없음 · no_div 배당 공시 없음 · ref_mismatch 참조값과 크게 다름(cross_check)
    hidden = {}
    if valuation["eps"] is None:
        hidden["eps"] = ("fx" if ccy_unknown else "shares" if not total_sh else
                         "mismatch" if eps_hidden else "no_income" if ttm_np is None else "unknown")
    elif valuation["eps"] <= 0:
        hidden["per"] = "loss"
    if valuation["bps"] is None:
        hidden["bps"] = ("fx" if ccy_unknown else "impaired" if (eqo_q is not None and eqo_q <= 0) else
                         "equity_check" if eq_broken else "mismatch" if eps_hidden else "no_equity")
    if valuation["dps"] is None:
        hidden["dps"] = "no_div"
    if hidden:
        valuation["hidden"] = hidden

    out = {
        "asOf": datetime.date.today().isoformat(),
        "fs_basis": "연결(CFS) · DART 공시 확정치 · 지배주주 기준 순이익",
        "annual": annual,
        "quarterly": quarterly,
        "valuation": valuation,
    }
    if rev_label:
        out["rev_label"] = rev_label
    return out


_FX_CACHE = {}
# 통화별 상식 범위(원). 여기 벗어난 값이 오면 응답 형식이 바뀐 것으로 보고 버린다.
_FX_BAND = {"USD": (500, 3000), "EUR": (500, 4000), "CNY": (50, 500),
            "HKD": (50, 500), "JPY": (3, 30), "GBP": (700, 4000),
            "SGD": (300, 2000), "VND": (0.01, 1.0)}


def fx_to_krw(ccy):
    """1 <통화> 가 몇 원인지. 국내 상장 외국기업이 위안·달러로 낸 재무제표를
    원으로 옮기는 데만 쓴다. 못 구하면 None — 그때는 주당지표를 숨긴다."""
    ccy = (ccy or "").upper()
    if ccy in ("", "KRW"):
        return 1.0
    if ccy in _FX_CACHE:
        return _FX_CACHE[ccy]
    lo, hi = _FX_BAND.get(ccy, (0.001, 100000))
    import requests
    rate = None
    for get in (
        lambda: float(requests.get(f"https://open.er-api.com/v6/latest/{ccy}", timeout=10)
                      .json()["rates"]["KRW"]),
        lambda: float(requests.get(
            "https://m.stock.naver.com/front-api/marketIndex/prices"
            f"?category=exchange&reutersCode=FX_{ccy}KRW&page=1&pageSize=1",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            .json()["result"][0]["closePrice"].replace(",", "")),
    ):
        try:
            v = get()
            if lo <= v <= hi:
                rate = v
                break
        except Exception:
            continue
    _FX_CACHE[ccy] = rate
    return rate


def dart_total_shares(dart, ticker):
    """발행주식총수(보통주+우선주) — 네이버·토스와 같은 주당지표 분모.
    최신 분기보고서 → 직전 사업보고서 순으로 시도. 실패 시 None."""
    cur = datetime.date.today().year
    for year, code in ((cur, "11013"), (cur - 1, "11011")):
        df = _dart_call(dart.report, ticker, "주식총수", year, code)
        if df is None or getattr(df, "empty", True):
            continue
        # 같은 구분(보통주/우선주)이 여러 줄로 오는 회사가 있다 — 정정공시나
        # 표 구성 탓이다. 그대로 더하면 발행주식총수가 두세 배가 된다.
        #
        #   웅진씽크빅   113,654,171  (실제 56,827,085 · 정확히 2배)
        #   마니커        63,511,228  (실제 31,755,614 · 정확히 2배)
        #   졸스          35,119,757  (실제 11,706,586 · 정확히 3배)
        #
        # 그 분모로 자본을 나누면 BPS 가 절반·3분의 1로 나간다. 구분별로
        # 가장 큰 값 하나만 쓰고 더한다.
        best = {}
        for _, r in df.iterrows():
            se = str(r.get("se", "")).replace(" ", "")
            if se in ("보통주", "우선주"):
                v = g._num(r.get("istc_totqy"))
                if v and v > 0:
                    best[se] = max(best.get(se, 0), v)
        tot = sum(best.values())
        if tot:
            return tot
    return None


def dart_dps(dart, ticker):
    """최근 결산 주당 현금배당금(보통주, 원) — DART '배당에 관한 사항' 공시.
    KRX 배당값은 갱신이 늦어(신규 배당 미반영) 신뢰도가 낮으므로 DART 공시를 직접 사용.
    최근 사업연도 → 그 전년 순으로 시도. 실패 시 None."""
    cur = datetime.date.today().year
    for year in (cur - 1, cur - 2):
        df = _dart_call(dart.report, ticker, "배당", year, "11011")
        if df is None or getattr(df, "empty", True):
            continue
        # 보통주 '주당현금배당금'을 전부 합산 — 리츠(반기)·분기/중간배당은 행이 여러 개라
        #   하나만 잡으면 연간 배당이 과소계상된다. 일반 기업은 행이 1개라 합=그 값.
        total, saw_row = 0.0, False
        for _, r in df.iterrows():
            se = str(r.get("se", "")).replace(" ", "")
            knd = str(r.get("stock_knd", "")).replace(" ", "")
            if "주당현금배당금" in se:
                if knd and "보통" not in knd:        # 우선주 제외
                    continue
                saw_row = True
                v = g._num(r.get("thstrm"))          # '-'/공란 → None
                if v is not None and v > 0:
                    total += v
        if saw_row:
            return float(total)                       # 0이면 무배당(유효)
    return None


# ── 정량 2: KRX 공식 밸류에이션 ───────────────────────────────────────
def krx_fundamentals(date):
    try:
        from pykrx import stock as krx
        import pandas as pd
        frames = []
        for mkt in ("KOSPI", "KOSDAQ"):
            frames.append(krx.get_market_fundamental_by_ticker(date, market=mkt))
        fund = pd.concat(frames)
        return fund[~fund.index.duplicated()]
    except Exception as e:
        log(f"- (KRX 펀더멘털 실패: {type(e).__name__}: {e}) — KRX 값 없이 진행")
        return None


# ── 표시용 포맷(검증 로그) ────────────────────────────────────────────
def _eok(v):
    return f"{v/1e8:,.0f}억" if v is not None else "—"


def quant_summary(name, q):
    lines = [f"### {name}"]
    for a in q["annual"]:
        lines.append(f"  {a['year']}: 매출 {_eok(a['rev'])} 영업이익 {_eok(a['op'])} "
                     f"지배순이익 {_eok(a['np_owner'])} OPM {a['opm']}% ROE {a['roe']}% 부채비율 {a['debt_ratio']}%")
    for r in q["quarterly"]:
        lines.append(f"  {r['q']}: 매출 {_eok(r['rev'])} 영업이익 {_eok(r['op'])} 지배순이익 {_eok(r['np_owner'])}")
    v = q["valuation"]
    lines.append(f"  PER {v.get('per')} | EPS {v.get('eps')} | PBR {v.get('pbr')} | "
                 f"BPS {v.get('bps')} | ROE {v.get('roe_ttm')} | 배당 {v.get('div')}% | DPS {v.get('dps')}")
    return "\n".join(lines)


# ── 프롬프트(v2) ──────────────────────────────────────────────────────
SCHEMA_V2 = """{
  "title":    {"ko": "리포트 헤드라인(핵심 관점, 12~24자 위주, 30자 이내, 매수/매도 표현 금지)", "en": "headline"},
  "lead":     {"ko": "한 문장 핵심 메시지", "en": "..."},
  "keypoints":[ {"ko": "핵심 포인트", "en": "..."}, ... 4~5개 ],
  "business": {"ko": "사업 구조 문단(7~9문장). 부문별 매출 비중·주요 제품·고객·경쟁구도", "en": "..."},
  "earnings": {"ko": "실적 분석 문단(7~9문장). 아래 [확정 재무]의 연간·분기 수치를 직접 인용·해석. 증감 원인, 마진 추이, 일회성 요인", "en": "..."},
  "industry": {"ko": "산업 분석 문단(6~8문장). 전방시장 수급·사이클 위치·경쟁사 대비 포지션", "en": "..."},
  "outlook":  {"ko": "전망 문단(6~8문장). 회사 가이던스·수주·증설·신제품 일정 등 확인된 사실 기반", "en": "..."},
  "valuation_comment": {"ko": "밸류에이션 해설 4~6문장. ★현재 PER·PBR·배당수익률·현재가·시가총액은 주가 따라 매일 바뀌므로 '정확한 수치'를 문장에 쓰지 말 것(그 값은 화면 카드가 실시간 표시). ★EPS·BPS·DPS 같은 주당 지표의 수치도 쓰지 말 것 — 공시가 갱신되면 값이 바뀌어 본문만 낡은 숫자로 남는다. 대신 수준을 관계로 서술 — 예: 과거 거래 밴드 상단/하단, 업종 평균 상회/하회, 순자산 대비 프리미엄/할인. ★ROE(자기자본이익률)는 절대 언급하지 말 것(서비스에서 제외된 지표). 특정 시점의 주가 수준(…원대)도 쓰지 말 것. 다년 변화가 필요하면 '적자→흑자 전환', '이익 회복' 같은 방향으로만 표현. 'TTM'·'후행' 등 전문 용어는 표면에 쓰지 말 것. '비싸다/싸다' 단정·권유 금지, 사실 비교만", "en": "..."},
  "bull":     [ {"title": {"ko":"","en":""}, "body": {"ko":"3~4문장","en":""}}, ... 3개 ],
  "bear":     [ {"title": {"ko":"","en":""}, "body": {"ko":"3~4문장","en":""}}, ... 3개 ],
  "risks":    [ {"cat": {"ko":"","en":""}, "body": {"ko":"3~4문장","en":""}}, ... 3개 ],
  "checkpoints": [ {"when": {"ko":"2026년 7월 말","en":"Late July 2026"}, "what": {"ko":"확인할 이벤트·지표와 그 의미 1~2문장","en":""}}, ... 3~5개 ],
  "verdict":  {"body": {"ko":"종합 요약 5~7문장. 투자의견·등급·목표주가 금지", "en":"..."}}
}"""

SYSTEM_V2 = (
    "당신은 한국 주식시장(코스피·코스닥)을 다루는 시니어 리서치 애널리스트입니다. "
    "공시·뉴스·시장 데이터를 근거로 깊이 있는 기업 리서치 리포트를 작성합니다. "
    "재무 수치는 사용자가 제공한 확정 데이터만 사용하며, 투자 권유 없이 정보를 제공합니다. "
    "당신의 글은 한국어/영어 양국어로 동시에 제공됩니다."
)


def build_prompt_v2(stock, quant, as_of):
    qjson = json.dumps(quant, ensure_ascii=False)
    _yrs = ", ".join(str(a.get("year")) for a in (quant.get("annual") or []))
    _qs = quant.get("quarterly") or []
    _qwin = f"{_qs[0]['q']}~{_qs[-1]['q']}" if _qs else "없음"
    _ttm = (quant.get("valuation") or {}).get("ttm_window") or "없음"
    return f"""다음 종목의 기업 리서치 리포트(v2)를 작성하세요.

[기준 데이터 — {as_of} KST]
- 종목명: {stock['name']} ({stock['ticker']}) · {stock.get('market','')} · {stock.get('sector','')}
- 현재가 {stock.get('price'):,}원 · 시가총액 {stock.get('mcap'):,.1f}조원
- 재무 반영 범위: 연간 {_yrs} · 분기 {_qwin} · 최근 4개 분기 창 {_ttm}. 이보다 최신 분기 실적은 아직 공시 확정 전이니 '확정치' 로 쓰지 말 것(검색으로 확인된 잠정치는 출처·시점과 함께 잠정임을 밝힐 것).
- 오늘은 {as_of[:10]} 이다. checkpoints 의 when 은 이 날짜 이후에 오는 일정만 쓸 것(이미 지난 일정 금지).

[확정 재무 — DART 공시·KRX 공식 값. 모든 단위 원. 아래 JSON의 숫자만 '사실'로 사용]
{qjson}

[작성 지침]
1. web_search로 최신 사업 현황·업황·뉴스·가이던스를 조사하세요(한국어, 3~6회). 신뢰 출처만: DART·기업 IR·증권사 리포트·주요 언론. 나무위키 등 위키·블로그·커뮤니티 금지.
2. **재무 수치는 위 [확정 재무] JSON의 값만 사용하세요.** 검색에서 다른 수치가 나오면 위 값을 우선합니다. 거기 없는 숫자(예: 부문별 매출액)는 검색으로 확인된 것만 출처·시점과 함께 쓰고, 확인 안 되면 정성 서술로 대체하세요. 숫자를 절대 지어내지 마세요.
3. earnings 섹션은 제공된 연간·분기 실적 수치(과거 확정치라 안 변함)를 구체적으로 인용·해석하세요. **valuation_comment 에서는 '현재 PER·PBR·배당수익률·현재가·시가총액'의 정확한 수치를 문장에 쓰지 마세요** — 이 값들은 주가 따라 매일 바뀌고 화면 카드가 실시간으로 표시합니다. **주당 지표(EPS·BPS·DPS)의 수치도 어느 섹션에든 쓰지 마세요** — 공시가 갱신되면 값이 바뀌는데 본문은 그대로 남아 낡은 숫자가 됩니다. 대신 그 수준을 '관계'로 서술하세요(예: "과거 거래 밴드(약 10~20배)의 상단을 웃돈다", "배당수익률은 업종 평균을 밑도는 편", "순자산 대비 프리미엄이 큰 구간", "주당순자산을 크게 밑도는 주가"). 과거 특정 시점의 주가 수준("3만원대까지 올랐다가 7,500원대")도 쓰지 마세요 — 오늘 주가는 화면에 있고 옛 주가는 독자에게 소용이 없습니다. 과거 PER 밴드, 다년 실적 추세는 인용해도 됩니다. **★ROE(자기자본이익률)는 절대 언급하지 마세요 — 서비스에서 제외된 지표입니다.** 다년 변화가 필요하면 "적자에서 흑자로 전환", "이익 회복" 처럼 방향으로만 표현하세요. 'TTM'·'선행/후행' 같은 용어와 '비싸다/싸다' 단정·매수/매도 권유는 금지.
4. checkpoints 는 '다음에 무엇을 확인해야 하는가'입니다 — 다가오는 분기 실적 발표, 수주·증설·규제 이벤트 등 확인 가능한 일정 위주로.
5. 균형: 강세·약세 요인을 같은 무게로. **우리(코사이)의 투자의견·매수/매도·목표주가는 절대 제시하지 말 것**(정보 제공용).
5-0. **증권사 목표주가 인용은 허용** — 우리 의견이 아니라 '누가 무엇을 제시했다'는 사실이기 때문이다. 다만 아래 셋을 모두 지킬 때만 쓰고, 하나라도 못 지키면 아예 쓰지 말 것.
   ① **출처와 시점을 함께** 쓴다 — "KB증권이 2026년 6월 리포트에서 …로 제시했다". 증권사명이나 시점 중 하나라도 확인되지 않으면 쓰지 않는다. "주요 증권사들이 제시한 목표주가는 37만~67만원" 처럼 증권사명 없이 범위를 옮기는 것도 금지다.
   ② **우리 판단이 아님이 문장에서 분명**해야 한다 — 전달 동사("제시했다", "밝혔다", "전망했다")로 끝내고, 우리 voice로 동조하거나 평가하지 않는다.
   ③ **6개월이 지난 것은 쓰지 않는다** — 낡은 목표주가를 현재형으로 옮기면 사실상 거짓이 된다. 시점이 오래됐으면 숫자 대신 정성 서술로 대체한다.
5-1. **단정적 주가 방향성 금지(중립 필수)**: KOSAI는 등록된 투자자문업자가 아니다. "상승 여력(이 충분/크다)", "추가 상승 여지", "재평가 모멘텀이 온다", "조정 후 반등", "저평가라 오를 것", "매집 신호=강세" 같은 *주가가 오른다/내린다는 우리 자신의 단정·예측*은 절대 쓰지 말 것. 대신 사실과 강세 vs 약세 구도를 제시하고 판단은 독자에게 맡긴다. ㅇ 밸류에이션·방향성 의견은 *출처를 명시한 인용*으로만 허용("○○증권은 …라고 평가했다") — 이때도 우리 voice로 동조하지 말 것. ㅇ '상승 여력'은 *영업이익률·가동률·침투율·환원율 등 사업 지표*의 개선 여지에만 한정해 쓰고, *주가/밸류 멀티플*에는 쓰지 말 것. ㅇ 내부자·기관의 지분 매수는 '매집해서 오른다'가 아니라 사실(누가·언제·얼마)과 중립 해석으로만.
6. 한국어(ko)/영어(en) 모두 작성. **영어(en) 문장에는 한글 문자를 한 글자도 쓰지 말 것** — 회사·제품·기관 고유명사는 로마자 또는 영문 명칭으로 쓴다(예: "GC녹십자" → "GC Biopharma", "조선제분" → "Chosun Flour Mills"). 인용문도 영어로 옮긴다.
7. **전 섹션 공통 금지어** — 아래는 valuation_comment 뿐 아니라 lead·keypoints·business·earnings·industry·outlook·bull·bear·risks·checkpoints·verdict 어디에도 쓰지 말 것. (이 규칙이 valuation_comment 설명 안에만 있던 동안 다른 섹션으로 계속 새어 나왔다.)
   · **ROE·자기자본이익률** — 서비스 화면에서 뺀 지표다. 화면에 없는 지표가 글에만 나오면 독자가 찾을 곳이 없다. 수익성을 말해야 하면 영업이익률로 쓴다.
   · **'TTM'·'선행 PER'·'후행 PER'** — 일반 독자가 모르는 용어다. 꼭 필요하면 "최근 네 개 분기 기준"처럼 풀어 쓴다.
   · **'저평가/고평가' 단정** — "저평가된 상태다", "고평가 구간이다", "제값을 못 받고 있다" 같은 가치 판단은 쓰지 않는다. 사실 비교는 된다.
        (O) "주가순자산비율이 과거 5년 밴드의 하단에 있다"
        (O) "동종업계 평균을 밑도는 배수에서 거래된다"
        (X) "저평가된 상태가 지속되고 있다"
   · 매수·매도 권유, "지금이 기회" "담을 만하다" 류의 표현.
   면책 문구에서 이 단어들을 쓰는 것("매수·매도 의견을 포함하지 않는다")은 예외다.
6-1. **한자를 섞지 말 것**: '전년比'→'전년 대비', '삼성디스플레이向'→'삼성디스플레이 대상', '데이터센터發'→'데이터센터발', '美/中/日'→'미국/중국/일본', 'A社'→'A사'. 한자를 읽지 못하는 독자가 많다. 한국어 뒤 괄호 병기('상저하고(上低下高)')만 예외.

[출력 형식]
- 검색 후 **머리말 없이** `===JSON_START===` 부터 출력. 마커 사이에 아래 스키마의 JSON 하나만. 마커 뒤에 아무것도 쓰지 않기.
- **스키마에 없는 키를 만들지 말 것** (예: en_placeholder·body_en_note·bull_en·risks_en 금지). 모든 글은 {{"ko": …, "en": …}} 쌍 안에 넣는다. 항목의 en 을 비워 두거나 다른 키로 빼지 말 것 — 구조가 다르면 리포트 전체가 폐기된다.
- JSON은 반드시 완결시킬 것.

스키마:
{SCHEMA_V2}

===JSON_START===
(여기에 JSON)
===JSON_END==="""


def _sanitize(obj):
    """모델이 가끔 줄바꿈을 '<개행>' 같은 리터럴 태그로 출력하는 것을 정리(재귀)."""
    import re as _re
    if isinstance(obj, dict):
        for k, v in obj.items():
            obj[k] = _sanitize(v)
        return obj
    if isinstance(obj, list):
        return [_sanitize(x) for x in obj]
    if isinstance(obj, str):
        s = _re.sub(r"\s*<\s*개행\s*>\s*", "\n\n", obj)
        s = s.replace("<개행>", " ").replace("개행", "")
        return _re.sub(r"[ \t]+\n", "\n", s).strip()
    return obj


def _bi(o):
    """ko·en 이 둘 다 비어 있지 않은 문자열인가."""
    return (isinstance(o, dict) and isinstance(o.get("ko"), str) and o["ko"].strip() != ""
            and isinstance(o.get("en"), str) and o["en"].strip() != "")


def valid_v2(rep):
    try:
        need = ("title", "lead", "keypoints", "business", "earnings", "industry",
                "outlook", "valuation_comment", "bull", "bear", "risks",
                "checkpoints", "verdict")
        missing = [k for k in need if k not in rep]
        if missing:
            log(f"    (검증 실패: 누락 키 {missing})")
            return False
        # 모양도 본다. 모델이 가끔 bull 을 한국어만 쓰고 bull_en 을 따로 만들거나,
        # 항목의 en 을 빠뜨린다(012450). 그러면 영어 화면에 빈칸·undefined 가 뜬다.
        for k in ("title", "lead", "business", "earnings", "industry", "outlook", "valuation_comment"):
            if not _bi(rep[k]):
                log(f"    (검증 실패: {k} 에 ko/en 이 없다)")
                return False
        if not all(_bi(x) for x in rep["keypoints"]):
            log("    (검증 실패: keypoints 항목에 ko/en 이 없다)")
            return False
        for k, fields in (("bull", ("title", "body")), ("bear", ("title", "body")),
                          ("risks", ("cat", "body")), ("checkpoints", ("when", "what"))):
            for x in rep[k]:
                if not isinstance(x, dict) or not all(_bi(x.get(f)) for f in fields):
                    log(f"    (검증 실패: {k} 항목 구조 {list(x) if isinstance(x, dict) else type(x).__name__})")
                    return False
        if not _bi((rep.get("verdict") or {}).get("body")):
            log("    (검증 실패: verdict.body 에 ko/en 이 없다)")
            return False
        for k in ("business", "earnings", "industry", "outlook"):
            if len(rep[k]["ko"]) < 150 or len(rep[k]["en"]) < 150:
                log(f"    (검증 실패: {k} 분량 부족 ko={len(rep[k]['ko'])} en={len(rep[k]['en'])})")
                return False
        for k, n in (("bull", 3), ("bear", 3), ("risks", 3), ("checkpoints", 3)):
            if len(rep[k]) < n:
                log(f"    (검증 실패: {k} {len(rep[k])}<{n})")
                return False
        if len(rep["verdict"]["body"]["ko"]) <= 80:
            log(f"    (검증 실패: verdict 분량 부족)")
            return False
        return True
    except Exception as e:
        log(f"    (검증 예외: {type(e).__name__}: {e})")
        return False


# ── 대상 선정 ─────────────────────────────────────────────────────────
def _ranked(data):
    return sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)


def pick_targets():
    """(data, targets). 돈이 나가는 주문의 대상은 여기서만 정한다.

    세 갈래다.
      · REPORT_TICKERS   명시 지정(공시 트리거·백필·수동). 지정한 대로 만든다.
      · REPORT_FILL_TO   자동 백필. 시총 상위 N 중 '지금 만들어야 할' 종목만 —
                         리포트가 없거나 갱신 기준일(data/reports_v2_refresh)보다
                         오래된 것. skip·hold·fail 초과·진행 중 배치는 뺀다
                         (_reports_state.wanted). SHARDS/SHARD 로 안정적으로 나눠
                         여러 run 이 겹치지 않게 병렬 백필한다.
      · 그 밖(quant·patch) 시총 상위 구간을 그대로 훑는다. 전 종목 patch 는 종목당
                         30초 안팎이라 한 잡에 다 안 들어간다(6시간 제한) —
                         FILL_FROM 을 0·700·1400·2100 으로 나눠 이어 돌린다.

    진행 중인 배치에 들어 있는 종목은 앞의 두 갈래에서 뺀다. 결과가 오기 전에
    또 주문하면 돈만 두 번 나간다 — 워치독이 30분마다 재가동하는 구조라 이게
    없으면 같은 종목이 시간마다 다시 주문된다(submit 에서 한 번 더 거른다).
    REPORT_ALLOW_INFLIGHT=1 로 풀 수 있다(회수를 포기한 배치를 다시 주문할 때).
    """
    data = g.load_stocks()
    allow_inflight = os.getenv("REPORT_ALLOW_INFLIGHT") == "1"
    inflight = set() if allow_inflight else S.inflight_tickers()

    env = os.getenv("REPORT_TICKERS", "").replace(" ", "")
    if env:
        want = [t for t in env.split(",") if t]
        by = {s["ticker"]: s for s in data["stocks"]}
        unknown = [t for t in want if t not in by]
        if unknown:
            log(f"- universe 에 없는 티커 {len(unknown)}개는 뺀다: {','.join(unknown[:20])}")
        busy = [t for t in want if t in by and t in inflight]
        if busy:
            log(f"- 이미 주문이 들어가 있는 {len(busy)}개는 뺀다(회수 뒤 다시): {','.join(busy[:20])}")
        return data, [by[t] for t in want if t in by and t not in inflight]

    fill_to = int(os.getenv("REPORT_FILL_TO", "0") or "0")
    if fill_to:
        import zlib
        fill_from = int(os.getenv("REPORT_FILL_FROM", "0") or "0")
        shards = int(os.getenv("REPORT_FILL_SHARDS", "1") or "1")
        shard = int(os.getenv("REPORT_FILL_SHARD", "0") or "0")
        ctx = S.fill_context(allow_inflight=allow_inflight)
        if ctx["refresh"]:
            log(f"- 갱신 기준일 {ctx['refresh']} — 그 전에 만든 리포트는 다시 만든다")
        ranked = _ranked(data)[:fill_to][fill_from:]
        missing = [s for s in ranked
                   if S.wanted(s["ticker"], ctx["refresh"], ctx["skip"], ctx["hold"],
                               ctx["failed_out"], ctx["inflight"])]
        if shards > 1:
            missing = [s for s in missing if zlib.crc32(s["ticker"].encode()) % shards == shard]
        return data, missing[:TOP_N]

    start = int(os.getenv("REPORT_FILL_FROM", "0") or "0")
    stocks = _ranked(data)[start:start + TOP_N]
    if start:
        log(f"- 시총 {start+1}~{start+len(stocks)}위 구간 {len(stocks)}종목")
    return data, stocks


def naver_valuation(ticker):
    """네이버 모바일 증권 API 참조값(전 항목). totalInfos의 모든 숫자 코드를 수집한다.
    PER/PBR/EPS/BPS 외에 배당수익률·ROE 등도 제공되면 함께 담겨 검증에 쓰인다. 실패 시 {}."""
    import requests
    try:
        r = requests.get(f"https://m.stock.naver.com/api/stock/{ticker}/integration",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        out = {}
        for it in (r.json().get("totalInfos") or []):
            cd = str(it.get("code", "")).lower()
            v = str(it.get("value", "")).replace(",", "")
            v = v.replace("배", "").replace("원", "").replace("%", "").replace("주", "").strip()
            try:
                out[cd] = float(v)
            except ValueError:
                pass
        return out
    except Exception:
        return {}


def cross_check(tk, name, valuation):
    """자체 산출값을 외부 참조값과 대조해 '중대 오류'일 때만 숨긴다.
    미세 차이(가중평균주식수·결산시점 등 방법론 차이)는 정상이므로 표시한다.

    기준은 두 단계다. 참조값이 우리와 같은 시점이면 15%, 우리가 앞서가는
    구간(TTM 이 올해 분기로 끝날 때)이면 3배 — 그 구간에서 잡을 것은
    단위·자릿수 오류와 부호 반대뿐이다. 부호 반대는 언제나 차단한다.

    ⚠️ 참조값(nv)은 검증 게이트 용도로만 메모리에서 사용하고, 저장/배포되는 valuation에는
    절대 기록하지 않는다(외부 데이터값이 사이트 코드로 노출되지 않도록)."""
    eps_self_ok = valuation.pop("_eps_self", False)   # 저장 대상이 아니다 — 여기서 떼어낸다
    bps_self_ok = valuation.pop("_bps_self", False)
    nv = naver_valuation(tk)
    if not nv:
        log(f"  ⚠️ {name}: 참조값 없음 — 자체 PER·EPS 미검증")
        return

    # 참조값이 우리보다 낡을 수 있다. 우리는 DART 를 직접 읽어 반기·3분기가
    # 나오는 즉시 반영하는데, 참조값은 며칠~몇 주 뒤에 따라온다. 실제로 2026
    # 반기(8/14 마감)를 재 보니 EPS 는 8/18 에야 따라왔고 BPS 는 그보다도 늦었다.
    # 그 사이에는 우리가 맞는데도 '15% 초과' 로 걸려 지표가 통째로 사라진다.
    #
    # 그래서 TTM 이 '올해 분기' 로 끝나면 — 참조값이 아직 못 따라왔을 구간이면
    # — 기준을 3배로 연다. 이때 잡으려는 것은 방법론 차이가 아니라 단위·자릿수
    # 오류(1,000배)와 부호 반대뿐이고, 둘 다 3배로 충분히 걸린다.
    ttm_window = valuation.get("ttm_window") or ""
    cur = datetime.date.today().year
    stale_ref = bool(ttm_window and ttm_window.split("~")[-1].startswith(str(cur)))
    limit = 3.0 if stale_ref else 0.15

    def gross_error(mine, ref):
        if mine is None or ref in (None, 0):
            return False
        if (mine > 0) != (ref > 0):
            # 부호 반대. 참조값이 우리와 같은 시점이면 중대 오류가 맞다.
            #
            # 그런데 우리가 앞서가는 구간에서는 부호가 갈리는 것이 정상이다.
            # 적자였던 회사가 이번 분기에 흑자로 돌아서면, 새 분기를 넣은
            # 우리는 흑자이고 아직 못 넣은 참조값은 적자다. 흑자 전환한
            # 회사가 전부 여기 걸려 EPS 가 통째로 사라졌다.
            #
            #   SK       2025Q4 -22,500억 → 2026Q2 +59,643억
            #   삼성SDI   2025Q4  -3,243억 → 2026Q2  +3,422억
            #
            # 추출 오류는 참조값 없이도 잡는다 — 회사가 낸 두 공시(주당이익과
            # 순이익)를 서로 맞춰 보는 검사가 collect_quant 에 있다. 시차를
            # 타지 않으므로 이쪽이 더 믿을 만하다. 여기서는 크기만 본다.
            if not stale_ref:
                return True
            return abs(abs(mine) - abs(ref)) / abs(ref) > limit
        return abs(mine - ref) / abs(ref) > limit

    # ── 우리가 앞서가는 구간에서는 참조값으로 크기를 재지 않는다 ────────────
    # 이익은 1년에 열 배씩도 움직인다 — SK하이닉스 2026Q2 지배순이익은 1년
    # 전의 13배다. 그래서 '3배 넘게 다르면 오류' 라는 기준 자체가 성립하지
    # 않는다. 실적이 뛴 회사가 줄줄이 걸려 EPS 가 지워졌다.
    #
    #   SK          146,041 ↔ 참조 35,981 (3.06배)
    #   두산         20,560 ↔ 참조  4,286 (3.80배)
    #   한국가스공사   6,438 ↔ 참조  1,441 (3.47배)
    #
    # 셋 다 회사가 낸 두 값(공시 주당이익 · 순이익÷발행총수)이 서로 맞는다.
    # 그 대조는 시차를 타지 않으므로 참조값보다 믿을 만하다. 자체 대조가
    # 통과했으면 참조값 대조는 건너뛴다. 자체 대조가 없을 때만(공시 주당이익이
    # 없어 한 갈래로만 계산했을 때) 참조값을 마지막 그물로 쓴다.
    skip_eps_ref = stale_ref and eps_self_ok

    issues = []
    if not skip_eps_ref and gross_error(valuation.get("eps"), nv.get("eps")):
        issues.append(f"EPS {valuation.get('eps')}↔ref {nv.get('eps')}")
        valuation["eps"] = valuation["per"] = None
        valuation.setdefault("hidden", {})["eps"] = "ref_mismatch"
        valuation["hidden"].pop("per", None)
    # BPS 는 참조값이 가장 늦게 따라오는 지표다. 대신 collect_quant 에서
    # '분기말 자본이 이익으로 설명되는가' 를 이미 확인했다 — 시차를 타지 않는
    # 자체 기준이라 이쪽이 더 믿을 만하다. 참조값 대조는 그 뒤의 그물로 남긴다.
    # KRX 공식 BPS 와 맞으면 참조값 대조는 건너뛴다. 거래소가 공표한 값과
    # 맞는데 네이버와 다르다는 이유로 지우는 것은 앞뒤가 안 맞는다.
    if not bps_self_ok and gross_error(valuation.get("bps"), nv.get("bps")):
        issues.append(f"BPS {valuation.get('bps')}↔ref {nv.get('bps')}")
        valuation["bps"] = valuation["pbr"] = None
        valuation.setdefault("hidden", {})["bps"] = "ref_mismatch"
    # 배당수익률 게이트 — 네이버 배당수익률과 30% 넘게 어긋나면 DPS 숨김.
    #   액면분할(분할 전 DPS) 등 배당 오류를 자동 차단. 배당은 시점·특별배당 차이로 30% 허용.
    our_div, nv_div = valuation.get("div"), nv.get("dividendyieldratio")
    if our_div and nv_div and abs(our_div - nv_div) / abs(nv_div) > 0.30:
        issues.append(f"배당 {our_div}%↔ref {nv_div}%")
        valuation["dps"] = valuation["div"] = None
        valuation.setdefault("hidden", {})["dps"] = "ref_mismatch"
    if issues:
        log(f"  ❌ {name} 중대오류 차단 → 해당 지표 숨김: {' / '.join(issues)}")
    else:
        # 참조값을 통과했을 때도 같이 남긴다.
        #
        # "네이버랑 다른데?" 라는 물음에 답하려면 그때 네이버가 무엇을
        # 보여 주고 있었는지가 있어야 한다. 막힌 경우에만 찍고 있어서
        # 통과한 종목은 비교할 자료가 아무 데도 없었다. 값은 로그에만
        # 남고 저장·배포되는 valuation 에는 들어가지 않는다.
        log(f"  ✅ {name} 검증 통과 PER {valuation.get('per')} PBR {valuation.get('pbr')} "
            f"EPS {valuation.get('eps')} BPS {valuation.get('bps')}"
            f" | 참조 EPS {nv.get('eps')} BPS {nv.get('bps')} PER {nv.get('per')}"
            f"{' · EPS 는 자체 대조로 확인(참조값 시차)' if skip_eps_ref else ''}")


# 저장된 정량을 그대로 써도 되는지 가른다. 전 종목 갱신은 '글' 을 다시 쓰는 일인데,
# 숫자까지 전부 다시 받으면 DART 하루 한도(2만 건)를 넘겨 며칠이 걸린다. 종목당
# 호출이 15회쯤이라 2,547종목이면 3만~6만 회다.
#
# 그렇다고 아무거나 재사용하면 옛 코드의 버그가 그대로 굳는다. 그래서 '이미 맞다는
# 것이 확인되는' 것만 재사용한다 — 최신 분기까지 반영됐고, 표가 다 차 있고, 항등식을
# 통과하고, 외부 공표값과도 크게 어긋나지 않는 것.
#
# 실제로 세어 보니 2,552장 중 1,865장이 여기 해당했고 재수집 대상은 687장이었다
# (DART 약 1만 회 — 하루 한도 안).
_REUSE_HIDDEN_OK = {"loss", "no_div"}          # 회사 사정이라 다시 받아도 안 바뀐다

# 정기보고서 제출 마감. 그 전에는 그 분기 보고서가 없으므로 아예 부르지 않는다
# (없는 보고서 하나를 물어보는 데 CFS·OFS 두 번을 쓴다).
_REPRT_OPEN = {"11013": (4, 25), "11012": (7, 25), "11014": (10, 25)}


def _reprt_available(code, year, today=None):
    """그 해 그 보고서가 나왔을 만한 시점인가. 지난 해는 언제나 참."""
    today = today or datetime.date.today()
    if year < today.year:
        return True
    m, d = _REPRT_OPEN.get(code, (1, 1))
    return (today.month, today.day) >= (m, d)


def latest_quarter_label(today=None):
    """공시 마감이 지나 '있어야 하는' 가장 최근 분기. 2026년 9월이면 2026Q2."""
    today = today or datetime.date.today()
    y, md = today.year, (today.month, today.day)
    if md >= (10, 25):
        return f"{y}Q3"
    if md >= (7, 25):
        return f"{y}Q2"
    if md >= (4, 25):
        return f"{y}Q1"
    return f"{y - 1}Q4"


def _repriced(q, stock):
    """저장된 정량의 '가격에 딸린 값' 만 오늘 시세로 다시 계산한다(DART 호출 없음).
    재무 숫자는 그대로 둔다 — 같은 공시에서 온 값이라 바뀔 이유가 없다."""
    q = json.loads(json.dumps(q))
    v = q.get("valuation") or {}
    price = stock.get("price")
    if not price:
        return q
    v["price"] = price
    v["mcap"] = stock.get("mcap")
    v["shares"] = stock.get("shares")
    eps, bps, dps = v.get("eps"), v.get("bps"), v.get("dps")
    v["per"] = round(price / eps, 3) if (eps and eps > 0) else None
    v["pbr"] = round(price / bps, 4) if bps else None
    v["div"] = round(dps / price * 100, 2) if dps is not None else None
    q["valuation"] = v
    return q


def reusable_quant(tk, stock, today=None):
    """저장된 리포트의 정량을 그대로 쓸 수 있으면 (오늘 시세로 고친) 정량을, 아니면 None.
    돌려주지 않는 이유는 로그로 남긴다 — 왜 다시 받는지 알 수 있어야 한다."""
    p = OUT_DIR / f"{tk}.json"
    if not p.exists():
        return None, "리포트 없음"
    try:
        q = (json.loads(p.read_text(encoding="utf-8")) or {}).get("quant") or {}
    except Exception:
        return None, "리포트를 읽지 못함"
    v = q.get("valuation") or {}
    a = q.get("annual") or []
    qs = q.get("quarterly") or []
    last_q = latest_quarter_label(today)
    if not str(v.get("ttm_window", "")).endswith(last_q):
        return None, f"최근 분기({last_q})가 반영되지 않음"
    if len(a) < 4:
        return None, f"연간 표가 {len(a)}년치"
    if len(qs) < 5 or any(x.get("np_owner") is None or x.get("rev") is None for x in qs):
        return None, "분기 표에 빈칸"
    if v.get("eps") is None or v.get("bps") is None:
        return None, "EPS·BPS 가 없음"
    # hidden 은 {지표: 사유} 다. 막아야 하는 것은 '사유' 가 추출 문제일 때다
    # (적자·무배당은 회사 사정이라 다시 받아도 그대로다).
    extra = set((v.get("hidden") or {}).values()) - _REUSE_HIDDEN_OK
    if extra:
        return None, f"숨긴 사유({', '.join(sorted(extra))})"
    bad = check_valuation.check_quant(q)
    if bad:
        return None, f"항등식 {bad[0][0]}"
    # 옛 코드는 분기 지배지분을 못 읽으면 자본총계(비지배 포함)로 대신했다. 그 값은
    # 항등식을 통과하면서도 틀렸다(SKC BPS 52,663 · KRX 22,956). 되짚어 잡는다.
    a0, den = a[0], (v.get("wavg_shares") or v.get("total_shares"))
    eq, eqo, nci = a0.get("equity"), a0.get("equity_owner"), a0.get("equity_nci")
    if den and eq and eqo and nci and abs(nci) > abs(eq) * 0.05:
        imp = v["bps"] * den
        if abs(imp / eq - 1) < 0.15 and abs(imp / eqo - 1) > 0.15:
            return None, "BPS 가 비지배지분까지 나눈 값으로 보임"
    # KRX 가 매일 공표하는 BPS 와 크게 어긋나면 어느 쪽이 맞는지 여기서 못 가린다.
    # 이익이 급증한 해에는 우리 쪽이 맞는 경우가 많지만, 확인 없이 옛 값을 물려주지 않는다.
    if v.get("bps_krx") and v.get("bps_src") == "자체" and abs(v["bps"] / v["bps_krx"] - 1) > 0.30:
        return None, f"BPS {v['bps']:,} 가 KRX 공표값 {v['bps_krx']:,.0f} 과 30% 초과 차이"
    return _repriced(q, stock), None


def collect_all_quant(targets, data, allow_reuse=False):
    """(quants, errors, unavailable).

    quants      {ticker: quant} — 수집된 것
    errors      {ticker: 사유} — 그 종목만의 예외(파싱 실패 등). skip 대상이 아니다.
    unavailable DartUnavailable 또는 None. DART 가 한도·점검으로 막히면 그 자리에서
                멈추고 그때까지 모은 것만 돌려준다. 호출자는 부분 결과로 할 일을
                끝낸 뒤 EXIT_DART_UNAVAILABLE 로 나간다(워크플로가 실패로 표시하고
                워치독이 오늘은 재가동하지 않는다). 예전에는 이 경우가 '재무제표
                없음' 과 구분되지 않아 한 run 의 종목 전부가 생성 불가로 영구
                기록됐다.
    """
    # 이미 맞다는 것이 확인되는 정량은 다시 받지 않는다(reusable_quant 참고).
    # 글을 다시 쓰는 갱신에서 DART 하루 한도를 아끼는 유일한 방법이다.
    reused, need = {}, []
    if allow_reuse and os.getenv("REPORT_NO_REUSE") != "1":
        why_count = {}
        for st in targets:
            q, why = reusable_quant(st["ticker"], st)
            if q is not None:
                reused[st["ticker"]] = q
            else:
                need.append(st)
                why_count[why] = why_count.get(why, 0) + 1
        if reused:
            log(f"- 정량 재사용 {len(reused)}개(숫자가 이미 최신·완전) · 다시 받을 {len(need)}개")
            for why, c in sorted(why_count.items(), key=lambda x: -x[1])[:6]:
                log(f"    · 다시 받는 이유 {c}개: {why}")
    else:
        need = list(targets)
    if not need:
        return reused, {}, None

    dart = g.get_dart()
    if not dart:
        log("❌ DART 초기화 실패 — 정량 수집 불가")
        why = getattr(g, "_dart_err", "") or "키 없음"
        m = _DART_STATUS.search(why)
        return reused, {}, DartUnavailable(m.group(1) if m else "init", f"DART 초기화 실패({why[:120]})")
    fund = krx_fundamentals(data.get("dataDate", ""))
    out, errors = dict(reused), {}
    for st in need:
        tk = st["ticker"]
        log(f"- 정량 수집 {tk} {st['name']}...")
        krx_row = None
        if fund is not None and tk in fund.index:
            krx_row = fund.loc[tk]
        try:
            out[tk] = collect_quant(dart, tk, krx_row, st)
            cross_check(tk, st["name"], out[tk]["valuation"])
            log(quant_summary(st["name"], out[tk]))
        except DartUnavailable as e:
            log(f"  ⛔ DART 를 쓸 수 없다({e}) — 여기서 멈춘다. 모은 {len(out)}개로 진행.")
            out.pop(tk, None)
            return out, errors, e
        except Exception as e:
            # 그 종목만의 예외. 실패 횟수를 세어 두어 같은 종목이 30분마다 DART 호출만
            # 태우며 영영 돌지 않게 한다(FAIL_LIMIT 번이면 백필에서 빠지고, 2주 뒤 다시 본다).
            errors[tk] = f"{type(e).__name__}: {e}"
            n = S.bump_fail(tk)
            log(f"  ⚠️ {tk} 정량 수집 실패: {errors[tk]} ({n}번째)")
    return out, errors, None


# ── 배치 제출/회수 ────────────────────────────────────────────────────
def _write_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def submit(cl, as_of):
    """정량 수집 → 종목별 항등식 검사 → 배치 제출.

    돌려주는 것: {"batch_id", "path", "tickers", "unavailable"}.
    상태 파일 data/batches_v2/<batch_id>.json 을 남긴다. 워크플로가 이 파일을
    커밋해야 collect_batch 가 회수할 수 있다.
    """
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    result = {"batch_id": None, "path": None, "tickers": [], "unavailable": None}
    data, targets = pick_targets()
    # 마지막 빗장 — 어느 갈래로 왔든 진행 중인 종목은 다시 주문하지 않는다.
    if os.getenv("REPORT_ALLOW_INFLIGHT") != "1":
        inflight = S.inflight_tickers()
        busy = [s["ticker"] for s in targets if s["ticker"] in inflight]
        if busy:
            log(f"- 진행 중인 배치에 있는 {len(busy)}개는 다시 주문하지 않는다: {','.join(busy[:20])}")
            targets = [s for s in targets if s["ticker"] not in inflight]
    if not targets:
        log("- 주문할 종목이 없다.")
        return result
    # 전체 universe 시총 순위(1=최대) → 종목별 모델 결정
    rank_of = {s["ticker"]: i + 1 for i, s in enumerate(_ranked(data))}
    log(f"## 🤖 리포트 v2 Batch 제출 — {len(targets)}개 · 상위{MODEL_TOP_N} {MODEL_TOP} / 나머지 {MODEL_REST}")
    quants, errors, unavailable = collect_all_quant(targets, data, allow_reuse=True)
    result["unavailable"] = unavailable

    fill_mode = os.getenv("REPORT_FILL_TO", "0") not in ("0", "")
    backfill = os.getenv("REPORT_BACKFILL") == "1"
    reqs, models, tickers = [], {}, []
    no_data, held, broken = [], [], []
    for st in targets:
        tk = st["ticker"]
        if tk in errors:
            broken.append(tk)                 # 이번 run 의 예외 — 다음에 다시. skip 아님.
            continue
        q = quants.get(tk)
        if q is None:
            continue                          # DART 가 막혀 못 모은 종목 — 다음 run
        if not q.get("annual"):
            log(f"  · ⚠️ {tk} 정량 데이터 없음 — 제외")
            no_data.append(tk)
            continue
        # 숫자가 항등식에 걸리면 그 종목은 글을 쓰지 않는다. 틀린 근거로 쓴 글은
        # 나중에 숫자만 고쳐도 본문에 그대로 남고, 다시 만들려면 돈이 또 든다.
        # 전체를 멈추지는 않는다 — 한 회사의 공시 오류가 2,600개를 세울 이유는 없다.
        bad = check_valuation.check_quant(q)
        if bad:
            reason = " / ".join(f"[{c}] {m}" for c, m in bad)
            log(f"  · ⛔ {tk} {st['name']} 숫자가 항등식에 걸린다 — 글을 쓰지 않는다: {reason}")
            S.add_hold(tk, reason)
            held.append(tk)
            continue
        S.clear_hold(tk)
        mdl = model_for(rank_of.get(tk))
        models[tk] = mdl
        tickers.append(tk)
        reqs.append(Request(
            custom_id=tk,
            params=MessageCreateParamsNonStreaming(
                model=mdl, max_tokens=96000,
                system=[{"type": "text", "text": SYSTEM_V2, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=[{"role": "user", "content": build_prompt_v2(st, q, as_of)}],
            ),
        ))
    # skip 은 DART 가 '조회된 데이터 없음' 을 준 종목만, 그리고 자동 백필(fill)과
    # 백필 run 에서만 남긴다. 명시 지정 run 은 skip 을 건드리지 않는다(병렬 안전).
    # 한도 초과·점검으로 못 모은 종목은 여기 오지 않는다(quants 에 없다).
    if (fill_mode or backfill) and no_data:
        S.add_skip(no_data)
        log(f"- 생성 불가 {len(no_data)}개 skip 기록 → data/reports_v2_skip/ (30일 뒤 백필이 다시 본다)")
    if held:
        log(f"- 항등식에 걸려 보류 {len(held)}개 → data/reports_v2_hold/: {','.join(held[:30])}")
    if broken:
        log(f"- 수집 예외 {len(broken)}개(다음 run 에 다시): {','.join(broken[:30])}")
    if not reqs:
        log("❌ 제출할 요청이 없습니다.")
        return result
    n_top = sum(1 for m in models.values() if m == MODEL_TOP)
    log(f"- 모델 배분: {MODEL_TOP} {n_top}개 · {MODEL_REST} {len(models)-n_top}개")

    batch = cl.messages.batches.create(requests=reqs)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {"batch_id": batch.id, "created": as_of, "model": MODEL, "models": models,
             "tickers": tickers, "dataDate": data.get("dataDate", ""), "count": len(reqs),
             "quant": {tk: quants[tk] for tk in tickers}}
    path = S.batch_path(batch.id)
    _write_state(path, state)
    if backfill:
        for tk in tickers:
            S.remove_skip(tk)                 # 만들 수 있게 됐다 — 생성 불가 표시를 뗀다
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건) → {path.relative_to(ROOT)}")
    result.update({"batch_id": batch.id, "path": path, "tickers": tickers})
    return result


def pickup(cl, as_of):
    """끝난 배치를 전부 회수한다. 재과금 없다. 회수한 배치 수를 돌려준다.

    주문(auto/submit)은 넣고 바로 끝나므로 누군가는 결과를 받으러 와야 한다.
    그게 이 함수고, collect_batch 워크플로가 30분마다 부른다. 상태 파일마다
    한 번만 회수한다 — 두 번 회수하면 리포트를 같은 내용으로 덮어쓴다.
    """
    import anthropic
    pend = S.pending_batches()
    if not pend:
        log("- 남은 배치 없음")
        _housekeep_batches()
        return 0
    n = 0
    for path, state in pend:
        bid = state["batch_id"]
        try:
            b = cl.messages.batches.retrieve(bid)
        except anthropic.NotFoundError:
            log(f"- {bid} 를 찾을 수 없다(만료·삭제) — 버린다")
            state["abandoned"] = f"{as_of} · 배치를 찾을 수 없음"
            state.pop("quant", None)
            _write_state(path, state)
            continue
        rc = b.request_counts
        log(f"- {bid} · 상태 {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}"
            f"/만료 {rc.expired}/취소 {rc.canceled} · 주문 {state.get('created')}")
        if b.processing_status != "ended":
            log("  아직 처리 중 — 다음 차례에 다시 온다")
            continue
        try:
            ok, fail = collect(cl, as_of, state)
        except Exception as e:
            # 결과 자체를 못 받는 경우(29일 지나 만료 등). 다음 차례에 또 실패할 것이라
            # 무한히 시도하지 않고 버린다. 리포트가 없는 종목은 백필이 다시 주문한다.
            log(f"  ⚠️ {bid} 결과 회수 실패: {type(e).__name__}: {e} — 버린다")
            state["abandoned"] = f"{as_of} · 회수 실패 {type(e).__name__}"
            state.pop("quant", None)
            _write_state(path, state)
            continue
        state["collected"] = as_of
        state["result"] = {"ok": ok, "fail": fail}
        state.pop("quant", None)              # 회수 뒤에는 필요 없다 — 저장소를 작게
        _write_state(path, state)
        log(f"✅ {bid} 회수 완료 · 성공 {ok}/실패 {fail}")
        n += 1
    _housekeep_batches()
    return n


def _housekeep_batches(keep_days=30):
    """회수·포기한 지 keep_days 지난 상태 파일을 지운다. 기록은 git 에 남는다."""
    today = S.today_kst()
    for path, state in S.load_batches():
        if path == S.LEGACY_STATE or S.is_pending(state):
            continue
        when = str(state.get("collected") or state.get("abandoned") or "")[:10]
        try:
            if (today - datetime.date.fromisoformat(when)).days > keep_days:
                path.unlink()
        except ValueError:
            continue


def poll(cl, batch_id, budget=None):
    waited = 0
    limit = MAX_WAIT if budget is None else budget
    while waited < limit:
        b = cl.messages.batches.retrieve(batch_id)
        rc = b.request_counts
        log(f"  · 상태 {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
        if b.processing_status == "ended":
            return True
        time.sleep(60)
        waited += 60
    log("- ⏳ 시간 내 미완료 — 남은 배치는 collect_batch 가 회수한다")
    return False


# 배치 단가(USD / 1M 토큰). 배치는 정가의 절반이다. 캐시 읽기는 입력의 10%,
# 캐시 쓰기는 125% 로 잡는다. 웹 검색은 1,000회에 $10. 청구서가 아니라 규모를
# 가늠하는 추정이다 — 실제 청구는 콘솔이 답이다.
_PRICE = {"claude-opus-5": (2.5, 12.5), "claude-sonnet-5": (1.0, 5.0),
          "claude-opus-4-8": (2.5, 12.5), "claude-sonnet-4-6": (1.5, 7.5)}


def _usage_of(message):
    """응답 하나의 사용량 → dict. 없으면 None."""
    u = getattr(message, "usage", None)
    if u is None:
        return None
    st = getattr(u, "server_tool_use", None)
    return {"in": getattr(u, "input_tokens", 0) or 0,
            "cache_w": getattr(u, "cache_creation_input_tokens", 0) or 0,
            "cache_r": getattr(u, "cache_read_input_tokens", 0) or 0,
            "out": getattr(u, "output_tokens", 0) or 0,
            "search": (getattr(st, "web_search_requests", 0) or 0) if st else 0}


def _cost_usd(model, u):
    pin, pout = _PRICE.get(model, (2.5, 12.5))
    return ((u["in"] + u["cache_w"] * 1.25 + u["cache_r"] * 0.1) * pin
            + u["out"] * pout) / 1e6 + u["search"] * 0.01


def collect(cl, as_of, state):
    """배치 하나의 결과를 리포트 파일로 쓴다. (성공 수, 실패 수).

    성공한 종목은 fail·hold 마커를 뗀다. 오류·스키마 불완전은 fail 횟수를 올린다 —
    FAIL_LIMIT 번 연속이면 자동 백필이 그 종목에 더 돈을 쓰지 않는다(사람이 본다).
    만료·취소는 종목 탓이 아니라 세지 않는다.

    사용량(토큰·검색 횟수)을 모델별로 합쳐 state["usage"] 에 남긴다. 리포트 한 장에
    얼마가 드는지를 추정이 아니라 실측으로 알기 위해서다.
    """
    batch_id = state["batch_id"]
    data = g.load_stocks()
    by_tk = {s["ticker"]: s for s in data["stocks"]}
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ok, fail, done, flagged = 0, 0, [], []
    usage = {}
    for result in cl.messages.batches.results(batch_id):
        tk = result.custom_id
        if result.result.type == "succeeded":
            u = _usage_of(result.result.message)
            if u:
                mdl = state.get("models", {}).get(tk) or state.get("model", MODEL)
                agg = usage.setdefault(mdl, {"n": 0, "in": 0, "cache_w": 0, "cache_r": 0, "out": 0, "search": 0, "usd": 0.0})
                agg["n"] += 1
                for k in ("in", "cache_w", "cache_r", "out", "search"):
                    agg[k] += u[k]
                agg["usd"] += _cost_usd(mdl, u)
        if result.result.type != "succeeded":
            fail += 1
            if result.result.type == "errored":
                n = S.bump_fail(tk)
                log(f"  · ⚠️ {tk} 결과 errored ({n}번째 실패)")
            else:
                log(f"  · ⚠️ {tk} 결과 {result.result.type}")
            continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            _sanitize(rep)
            if not valid_v2(rep):
                fail += 1
                n = S.bump_fail(tk)
                log(f"  · ⚠️ {tk} 스키마 불완전 — 건너뜀 ({n}번째 실패)")
                continue
            srcs = collect_sources_v2(result.result.message)
            if srcs:
                rep["sources"] = srcs[:18]
            st = by_tk.get(tk, {})
            rep.update({
                "v": 2, "model": (state.get("models", {}).get(tk) or state.get("model", MODEL)),
                "ticker": tk, "name": st.get("name", tk),
                # name_en이 빈 문자열이어도(DART 영문명 없음) 한글명으로 폴백 — 빈 영문명 방지.
                "name_en": st.get("name_en") or st.get("name") or tk,
                "sector": st.get("sector", ""), "categories": st.get("categories", []),
                "market": st.get("market", ""),
                "reportDate": now.strftime("%Y-%m-%d"),
                "reportTs": now.strftime("%Y-%m-%d %H:%M"),
                "dataDate": state.get("dataDate") or data.get("dataDate", ""),
                "quant": (state.get("quant") or {}).get(tk, {}),
            })
            # 한자 → 한글. 프롬프트가 금지해도 '전년比'·'-253億원' 처럼 샌다(228개 리포트).
            # 읽는 사람이 못 읽는 글자는 그 자체로 결함이라 저장 전에 고친다.
            try:
                rep, _hanja = fix_hanja.walk(rep)
                if _hanja:
                    log(f"  · {tk} 한자 {len(_hanja)}곳 한글로: " + ", ".join(f"{a.strip()[:14]}→{b}" for a, b in _hanja[:3]))
            except Exception as e:
                log(f"  · ({tk} 한자 변환 실패: {type(e).__name__}: {e})")
            # 금지 표현 검사 — 프롬프트는 부탁이지 강제가 아니다. 실제로 2,563개 중
            # 99개(3.9%)가 금지해 둔 표현을 담고 있었다. 걸리면 그 섹션만 작은 모델에
            # 넘겨 위반 문장을 고쳐 쓴다(check_report_text.repair). 고친 결과가 검사에
            # 덜 걸릴 때만 채택한다. 그래도 남으면 로그에 남기고 리포트는 그대로 쓴다 —
            # 글 하나 때문에 종목을 통째로 비우는 게 더 나쁘다.
            try:
                bad_text = check_report_text.check(rep)
            except Exception:
                bad_text = []
            if bad_text and os.getenv("REPORT_REPAIR", "1") != "0":
                try:
                    fixed = check_report_text.repair(cl, rep, bad_text)
                except Exception as e:
                    fixed = None
                    log(f"  · ({tk} 교정 호출 실패: {type(e).__name__}: {e})")
                if fixed:
                    rep, remaining = fixed
                    log(f"  · ✏️ {tk} 표현 교정 {len(bad_text)}건 → 남은 {len(remaining)}건")
                    bad_text = remaining
            if bad_text:
                flagged.append(tk)
                kinds = sorted({h["rule"] for h in bad_text})
                risky = any(h["level"] == "위험" for h in bad_text)
                log(f"  · {'🚫' if risky else '⚠️'} {tk} 금지 표현 {len(bad_text)}건 "
                    f"({', '.join(kinds)}) — {bad_text[0]['sentence'][:70]}")

            (OUT_DIR / f"{tk}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            S.clear_fail(tk)
            S.clear_hold(tk)
            done.append(tk)
            ok += 1
        except Exception as e:
            fail += 1
            n = S.bump_fail(tk)
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e} ({n}번째 실패)")

    # 전역 인덱스(reports-index.js)는 병렬 커밋 충돌을 피하려 여기서 쓰지 않는다.
    # → 워치독이 reindex(단일 직렬)로 전체 v2에서 재생성한다. 이 run은 자기 종목 JSON만 커밋.
    have = sum(1 for p in OUT_DIR.glob("*.json") if S.TICKER.fullmatch(p.stem))
    log(f"\n✅ v2 회수 완료 · 성공 {ok}/실패 {fail} → data/reports_v2/ ({have}개)")
    if flagged:
        log(f"⚠️ 금지 표현이 남은 {len(flagged)}개 — 다시 만들 대상: {','.join(flagged)}")
    if usage:
        for mdl, a in usage.items():
            a["usd"] = round(a["usd"], 3)
            log(f"💵 {mdl} {a['n']}건 · 입력 {a['in']:,}(캐시쓰기 {a['cache_w']:,}·읽기 {a['cache_r']:,}) "
                f"· 출력 {a['out']:,} · 검색 {a['search']} → 약 ${a['usd']:.2f} "
                f"(장당 ${a['usd'] / a['n']:.3f})")
        state["usage"] = usage
    return ok, fail


def sync_list_index(tickers):
    """리포트 목록(reports-index.js)의 제목·날짜를 v2와 일치시킨다."""
    import re as _re
    p = ROOT / "data" / "reports-index.js"
    if not p.exists():
        return
    try:
        m = _re.search(r"window\.KOS_REPORTS\s*=\s*(\{.*\});", p.read_text(encoding="utf-8"), _re.S)
        payload = json.loads(m.group(1))
        n = 0
        for tk in tickers:
            f = OUT_DIR / f"{tk}.json"
            if tk in payload.get("reports", {}) and f.exists():
                v2 = json.loads(f.read_text(encoding="utf-8"))
                payload["reports"][tk] = {"title": v2.get("title"),
                                          "reportDate": v2.get("reportDate"),
                                          "reportTs": v2.get("reportTs")}
                n += 1
        p.write_text("// KOS ai — 리포트 인덱스(자동 생성). 전체 본문은 data/reports 폴더의 종목별 JSON 참조.\n"
                     "window.KOS_REPORTS = " + json.dumps(payload, ensure_ascii=False) + ";\n",
                     encoding="utf-8")
        log(f"- 목록 인덱스 제목 동기화: {n}건")
    except Exception as e:
        log(f"- (인덱스 동기화 실패: {type(e).__name__}: {e})")


def _quant_ok(new, old):
    """새로 수집한 정량이 기존보다 확실히 부실하면 갈아 끼우지 않는다.

    DART 가 일시적으로 막히거나 하루 호출 한도를 넘기면 빈 값이 돌아온다.
    그걸 그대로 덮어쓰면 멀쩡하던 리포트가 통째로 빈다. 589종목을 한꺼번에
    다시 돌리기 전에 걸어 두는 빗장이다."""
    if not isinstance(new, dict):
        return False

    def filled(q):
        return [a for a in (q.get("annual") or [])
                if a.get("np_owner") is not None or a.get("rev") is not None]

    if not filled(new):
        return False
    if isinstance(old, dict) and filled(old):
        # 결산 시점에 한 해쯤 밀리는 건 정상이므로 한 칸은 봐준다.
        if len(filled(new)) < len(filled(old)) - 1:
            return False
    return True


def patch_quant(as_of):
    """기존 v2 리포트의 정량(quant) 블록만 다시 수집해 교체한다(LLM 재호출 없음·무료).
    본문 텍스트는 그대로 두고 숫자만 최신 방식으로 갱신할 때 사용."""
    data, targets = pick_targets()
    quants, errors, unavailable = collect_all_quant(targets, data)
    n = kept = 0
    for st in targets:
        tk = st["ticker"]
        f = OUT_DIR / f"{tk}.json"
        if tk in quants and f.exists():
            rep = json.loads(f.read_text(encoding="utf-8"))
            if not _quant_ok(quants[tk], rep.get("quant")):
                kept += 1
                log(f"  ⏭️  {tk} {st['name']} — 새로 수집한 값이 부실해 기존 값을 지킨다")
                continue
            rep["quant"] = quants[tk]
            rep["dataDate"] = data.get("dataDate", rep.get("dataDate", ""))
            f.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
            log(f"  · 정량 교체 {tk} {st['name']}")
    log(f"\n✅ 정량 patch 완료: {n}건 (본문 텍스트 유지)"
        + (f" · 기존 값 지킴 {kept}건" if kept else ""))
    if unavailable:
        _die_dart(unavailable)


def recover(cl, as_of, batch_id=""):
    """상태 파일이 없는 배치(옛 run 에서 제출됐으나 파일이 커밋되지 않은 것)를
    ID 로 회수한다(재과금 없음). 제출 시점 quant 가 없으므로 현재 데이터로
    재수집해 채운다(표시용이라 무방). batch_id 비우면 가장 최근 배치."""
    if not batch_id:
        recent = list(cl.messages.batches.list(limit=1))
        if not recent:
            log("❌ 배치가 없습니다.")
            return
        batch_id = recent[0].id
        log(f"- batch_id 미지정 → 최근 배치 사용: {batch_id}")
    b = cl.messages.batches.retrieve(batch_id)
    log(f"- 배치 {batch_id} 상태: {b.processing_status} · 성공 {b.request_counts.succeeded}")
    if b.processing_status != "ended":
        log("- 아직 처리 끝나지 않음 — 나중에 다시 recover")
        return
    # 배치에 어떤 종목이 들어 있는지는 결과에서 읽는다 — REPORT_TICKERS 를 안 줘도 된다.
    ids = [r.custom_id for r in cl.messages.batches.results(batch_id)]
    os.environ["REPORT_TICKERS"] = ",".join(ids)
    os.environ["REPORT_ALLOW_INFLIGHT"] = "1"
    data, targets = pick_targets()
    rank_of = {s["ticker"]: i + 1 for i, s in enumerate(_ranked(data))}
    log(f"- 정량 재수집 {len(targets)}개(제출시점 quant 유실분 재구성)...")
    quants, errors, unavailable = collect_all_quant(targets, data)
    models = {st["ticker"]: model_for(rank_of.get(st["ticker"])) for st in targets}
    state = {"batch_id": batch_id, "created": as_of, "model": MODEL, "models": models,
             "tickers": ids, "dataDate": data.get("dataDate", ""), "count": len(ids),
             "quant": quants, "recovered": True}
    path = S.batch_path(batch_id)
    _write_state(path, state)
    log(f"- 상태 재구성 완료(quant {len(quants)}) → 회수 시작")
    ok, fail = collect(cl, as_of, state)
    state["collected"] = as_of
    state["result"] = {"ok": ok, "fail": fail}
    state.pop("quant", None)
    _write_state(path, state)
    if unavailable:
        _die_dart(unavailable)


def _die_dart(e):
    """DART 가 막혔다. 여기까지 만든 것은 그대로 두고(호출자가 이미 저장했다) 실패로 나간다."""
    log(f"⛔ DART 를 쓸 수 없다 — {e}. 이 run 은 여기서 멈춘다. skip 은 남기지 않았다.")
    if getattr(e, "status", "") in ("020", "021"):
        S.mark_quota_exhausted()
        log("    하루 호출 한도 초과 — 한국시간 자정에 풀린다. "
            "data/dart_quota_exhausted 에 오늘 날짜를 남겨 워치독이 오늘은 재가동하지 않게 한다.")
    sys.exit(EXIT_DART_UNAVAILABLE)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    if mode == "quant":
        data, targets = pick_targets()
        _, _, unavailable = collect_all_quant(targets, data)
        if unavailable:
            _die_dart(unavailable)
        return
    if mode == "patch":
        patch_quant(as_of)
        return

    # ── 과금 정지 스위치 ────────────────────────────────────────────────
    # data/reports_paused 파일이 있으면 돈이 드는 모드를 전부 건너뛴다.
    #
    # 여기 두는 이유: 리포트를 만드는 길이 여럿이다(공시 트리거, 워치독의
    # 자동 재가동, 수동 실행). 워크플로마다 스위치를 달면 하나를 빠뜨린다.
    # 전부 이 함수를 지나므로 여기 한 곳이면 새는 곳이 없다.
    #
    # quant·patch 는 계산만 하고 API 를 부르지 않으므로 막지 않는다.
    # pickup 은 이미 결제된 결과를 받아오는 것이라 막지 않는다 — 멈춰 있는 동안
    # 배치가 만료(29일)되면 낸 돈이 그대로 사라진다.
    #
    # 켜고 끄는 법:  파일을 지우면 다시 돈다.  touch data/reports_paused 로 멈춘다.
    if PAUSE_FILE.exists() and mode not in ("pickup", "collect", "batches", "recover"):
        why = PAUSE_FILE.read_text(encoding="utf-8").strip()
        log(f"⏸️  과금 정지 중 — '{mode}' 를 건너뛴다.")
        log(f"    {PAUSE_FILE.relative_to(ROOT)} 을 지우면 다시 돈다.")
        if why:
            log(f"    사유: {why.splitlines()[0]}")
        return

    # 예전에는 여기서 저장된 리포트 전체를 검산해 하나라도 걸리면 아무것도
    # 시작하지 않았다. 그 검산은 '지금 주문할 종목의 새 숫자' 와는 무관한
    # 데다(옛 리포트를 본다), 한 회사의 공시 오류가 2,600종목의 갱신을 통째로
    # 세웠다. 지금은 submit 이 종목마다 새로 모은 숫자를 검산해 걸린 종목만 뺀다.

    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    if mode == "submit":
        r = submit(cl, as_of)
        if r["unavailable"]:
            _die_dart(r["unavailable"])
    elif mode in ("collect", "pickup"):
        pickup(cl, as_of)
    elif mode == "batches":
        # 최근 배치 목록 — 취소된 run에서 제출된 배치 회수 여부 진단용
        lines = ["# 최근 Anthropic 배치"]
        for b in cl.messages.batches.list(limit=20):
            rc = b.request_counts
            tot = rc.processing + rc.succeeded + rc.errored + rc.canceled + rc.expired
            lines.append(f"{b.id} | {b.processing_status} | created {b.created_at} | "
                         f"성공 {rc.succeeded}/{tot} (처리 {rc.processing}·오류 {rc.errored}·만료 {rc.expired})")
        (ROOT / "data" / "_batches.txt").write_text("\n".join(lines), encoding="utf-8")
        log("\n".join(lines))
    elif mode == "recover":
        recover(cl, as_of, os.getenv("RECOVER_BATCH_ID", ""))
    else:
        # auto — 주문을 넣고 잠깐만 기다린다.
        #
        # 전에는 여기서 최대 5시간을 기다렸다. 배치는 24시간까지 걸릴 수
        # 있는데 잡은 6시간에 잘리므로, 기다리다 잘리면 결과를 못 받는다.
        # 8월 20일 새벽 479건이 그렇게 날아갔다. 돈은 이미 나간 뒤였다.
        #
        # 그래서 짧게만 기다리고(SHORT_WAIT), 안 끝났으면 그대로 끝낸다.
        # 남은 배치는 collect_batch 워크플로가 30분마다 와서 회수한다.
        # 주문과 회수가 분리되면 6시간 제한이 의미가 없어진다. 상태 파일
        # (data/batches_v2/)이 커밋되는 것이 그 전제다 — 워크플로를 볼 것.
        r = submit(cl, as_of)
        bid = r["batch_id"]
        if bid and not r["unavailable"]:
            if poll(cl, bid, budget=SHORT_WAIT):
                pickup(cl, as_of)
            else:
                log(f"- 아직 처리 중 — 여기서 끝낸다. collect_batch 가 회수한다({bid}).")
        if r["unavailable"]:
            _die_dart(r["unavailable"])


if __name__ == "__main__":
    main()
