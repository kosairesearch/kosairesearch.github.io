#!/usr/bin/env python3
"""
KOSAI 리포트 v2 — '정량 + 정성 분리' 구조 (Message Batches API)

핵심 원칙: 재무 숫자는 AI가 쓰지 않는다.
  - 정량(연간 4개년·분기 5개 분기 실적, 밸류에이션, TTM PER)은 이 스크립트가
    DART(fnlttSinglAcntAll)·KRX(pykrx 로그인)에서 직접 수집해 JSON에 넣는다.
  - AI(batch)는 그 숫자를 '근거'로 받아 해석·서술 섹션만 작성한다.

모드:
  quant    — 정량 데이터만 수집해 검증 로그 출력 (배치 미제출, 검증용)
  submit   — 정량 수집 + 배치 제출 (data/batch_state_v2.json)
  collect  — 배치 결과 회수 → data/reports_v2/{ticker}.json
  auto     — submit 후 폴링, collect

환경변수: ANTHROPIC_API_KEY, DART_API_KEY, KRX_ID, KRX_PW,
          REPORT_MODEL_V2(기본 claude-opus-5), REPORT_TICKERS, REPORT_TOP_N(기본 10),
          BATCH_MAX_WAIT_SEC
"""

import datetime
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_reports as g  # log/extract_text/collect_sources/load_stocks 재사용
import check_report_text     # 생성 직후 금지 표현 검사(프롬프트가 못 막은 것)

OUT_DIR = ROOT / "data" / "reports_v2"
STATE_JS = ROOT / "data" / "batch_state_v2.json"
# 있으면 돈이 드는 모드(submit·collect·auto·recover)를 전부 멈춘다. main() 참고.
PAUSE_FILE = ROOT / "data" / "reports_paused"
# 생성 불가 종목(DART 재무 없음: 인프라펀드·스팩·일부 지주 등) — 백필이 영원히 재시도하지 않도록 기록.
# 종목별 마커 파일(디렉터리)로 저장 → 병렬 run이 서로 겹치지 않아 git 커밋 충돌이 없다.
SKIP_DIR = ROOT / "data" / "reports_v2_skip"


def load_skip():
    out = set()
    if SKIP_DIR.exists():
        out |= {p.name for p in SKIP_DIR.iterdir() if p.is_file() and not p.name.startswith(".")}
    # 구버전 단일 파일도 함께 읽어 호환
    legacy = ROOT / "data" / "reports_v2_skip.txt"
    if legacy.exists():
        out |= {ln.strip() for ln in legacy.read_text(encoding="utf-8").splitlines() if ln.strip()}
    return out


def add_skip(tickers):
    if not tickers:
        return
    SKIP_DIR.mkdir(parents=True, exist_ok=True)
    for t in tickers:
        (SKIP_DIR / t).write_text("", encoding="utf-8")

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
    "cfo":          ("영업활동현금흐름", "영업활동으로인한현금흐름"),
}


# 계정명 접두(로마숫자·번호 + 구분점) 제거용 — "IV.영업이익"→"영업이익", "1.기본주당이익"→"기본주당이익"
_NM_PREFIX = re.compile(r"^[IVXLCDM0-9]{1,4}[.)]\s*")


def _fin_all(dart, ticker, year, reprt):
    """fnlttSinglAcntAll → {key: {"amt": 당기, "add": 누적}}.
    연결(CFS) 우선, 자회사가 없어 연결재무제표가 없는 단독기업은 별도(OFS)로 폴백."""
    df = None
    for fs in ("CFS", "OFS"):
        try:
            df = dart.finstate_all(ticker, year, reprt_code=reprt, fs_div=fs)
        except Exception:
            df = None
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
                     g._num(r.get("thstrm_add_amount"))))

    def sj_ok(key, sj):
        if key in ("rev", "rev_ins", "op", "np", "np_owner", "np_nci", "eps_basic"):
            return sj in ("IS", "CIS")
        if key in ("assets", "liab", "equity", "equity_owner"):
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
    for aid, anm, sj, amt, add in rows:
        for key in ACC_IDS:
            if key in out or amt is None or not sj_ok(key, sj):
                continue
            if aid in ACC_IDS[key]:
                out[key] = {"amt": amt, "add": add}
    # 2차: 계정명 폴백 — 포괄손익 계열 행 배제.
    #   np_owner 는 CIS의 '총포괄손익 귀속-지배기업소유주지분'과 행 이름이 같아
    #   오추출 위험이 커서 손익계산서(IS)에서만 명칭 매칭을 허용한다.
    for aid, anm, sj, amt, add in rows:
        for key in ACC_IDS:
            if key in out or amt is None or not sj_ok(key, sj):
                continue
            if "포괄" in anm:
                continue
            if key in ("np_owner", "np_nci") and sj != "IS":
                continue
            # 은행 등은 계정명에 로마숫자·번호 접두("IV.영업이익","I.영업수익")가 붙어
            # 정확매칭이 실패한다 → 접두 제거 후 비교.
            anm2 = _NM_PREFIX.sub("", anm)
            if anm in ACC_NAMES[key] or anm2 in ACC_NAMES[key]:
                out[key] = {"amt": amt, "add": add}
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
            for aid, anm, sj, amt, add in rows:
                if sj in ("IS", "CIS"):
                    fp.write(f"  {sj:<4} 당기={amt}  누적={add}  | {anm} | {aid}\n")
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


def collect_quant(dart, ticker, krx_row, stock):
    """한 종목의 정량 블록을 수집한다."""
    cur = datetime.date.today().year  # 2026

    # 연간 4개년 (최근 결산 = cur-1)
    annual = []
    annual_fs = {}          # 연도 → 연결(CFS)/별도(OFS). 4분기를 뺄 때 기준 대조에 쓴다.
    for yr in range(cur - 1, cur - 5, -1):
        d = _fin_all(dart, ticker, yr, "11011")
        if not d:
            continue
        annual_fs[yr] = d.get("_fs")
        rev, op = _cum(d, "rev"), _cum(d, "op")
        np_, npo = _cum(d, "np"), _cum(d, "np_owner")
        eq, eqo, li = _bs(d, "equity"), _bs(d, "equity_owner"), _bs(d, "liab")
        row = {
            "year": yr, "rev": rev, "op": op, "np": np_,
            "np_owner": npo if npo is not None else np_,
            "equity": eq, "equity_owner": (eqo if eqo is not None else eq),
            "liab": li, "cfo": _cum(d, "cfo"),
            "eps_basic": _cum_eps(d),
        }
        row["opm"] = round(op / rev * 100, 1) if (op is not None and rev) else None
        base_np = row["np_owner"]
        base_eq = eqo if eqo is not None else eq
        # 자본잠식(자본 ≤ 0) 연도는 ROE 무의미 → 숨김
        row["roe"] = round(base_np / base_eq * 100, 1) if (base_np is not None and base_eq and base_eq > 0) else None
        row["debt_ratio"] = round(li / eq * 100, 1) if (li is not None and eq) else None
        annual.append(row)
        time.sleep(0.3)

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
        d = g._extract_fin(g._safe_finstate(dart, ticker, year, reprt))
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
            d_yr = _fin_all(dart, ticker, row["year"], "11011")
            ins_vals[row["year"]] = _cum(d_yr, "rev_ins")
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

    quarterly = [{"q": l, "rev": rev_q.get(l), "op": op_q.get(l),
                  "np_owner": npo_q.get(l) if npo_q.get(l) is not None else np_q.get(l)}
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

    ttm_np = None
    fy_np = fy_row["np_owner"] if fy_row else None
    if fy_np is not None:
        if cur_qi:
            pv, cv = _npo(d_py_same), _npo(d_cur)
            if None not in (pv, cv):
                ttm_np = fy_np - pv + cv
        else:
            ttm_np = fy_np
    ttm_label = f"{py}Q{cur_qi + 1}~{cur}Q{cur_qi}" if cur_qi else f"{py}Q1~{py}Q4"

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
    fx = 1.0
    if ccy not in ("KRW", ""):
        fx = fx_to_krw(ccy) or 0
        log(f"  💱 {ticker} 공시 통화 {ccy}"
            + (f" — 원화 환산 ×{fx:,.2f}" if fx else " — 환율을 구하지 못해 주당지표를 숨긴다"))
    ccy_unknown = bool(ccy not in ("KRW", "") and not fx)
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
        money = ("rev", "op", "np", "np_owner", "equity", "equity_owner", "cfo", "liab", "assets")
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
    if eps_disc and eps_alt and abs(eps_disc - eps_alt) > 0.30 * max(abs(eps_disc), abs(eps_alt)):
        r = abs(eps_alt / eps_disc)
        if any(abs(r / c - 1) < 0.05 for n in range(2, 41) for c in (float(n), 1.0 / n)):
            log(f"  ⚠️ 주당이익 기준이 섞였다(공시 {eps_disc:,.0f} vs 순이익÷주식수 "
                f"{eps_alt:,.0f}, {r:.1f}배) — 액면병합·감자로 본다. 순이익 쪽을 쓴다.")
            eps_pick = eps_alt
        else:
            # 배수로도 안 떨어진다. 회사가 공시한 두 값이 서로 다르다는 뜻인데,
            # 어느 쪽이 맞는지 우리는 모른다. 모르면 안 보여준다 — 틀린 숫자를
            # 내보내는 것보다 빈칸이 낫다. 리포트를 다시 만들면 채워진다.
            log(f"  ❌ 두 공시가 어긋난다(공시 {eps_disc:,.0f} vs 순이익÷주식수 "
                f"{eps_alt:,.0f}, {r:.2f}배) — 어느 쪽인지 몰라 EPS·PER 숨김")
            eps_pick = None
            eps_disc = None
            eps_hidden = True
    eps_ttm = eps_pick if eps_pick is not None else (
        None if eps_hidden else (int(ttm_np / total_sh) if (ttm_np and total_sh) else None))
    eps_ttm = int(eps_ttm) if eps_ttm is not None else None
    per_ttm = round(price / eps_ttm, 1) if (eps_ttm and eps_ttm > 0 and price) else None

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
        f"{int(ttm_np/total_sh) if (ttm_np and total_sh) else '없음'}"
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
    eps_indep = (ttm_np / total_sh) if (ttm_np and total_sh) else None
    eps_self_ok = bool(
        eps_disc and eps_indep and (eps_disc > 0) == (eps_indep > 0)
        and (1 / 3.3) <= abs(eps_indep / eps_disc) <= 3.3)

    # ROE 신뢰성: 순이익 추출(ttm_np)이 공시 EPS와 30% 넘게 어긋나면(추출 오류) 공시 EPS로 ttm_np 보정.
    #   → EPS는 맞는데 ROE만 0%/이상치로 나오는 모순 제거(원익QnC 등).
    if eps_disc is not None and total_sh:
        implied_np = eps_disc * total_sh
        if ttm_np is None or (implied_np and abs(ttm_np - implied_np) > 0.3 * abs(implied_np)):
            ttm_np = implied_np

    bps_denom = wavg or total_sh
    # 지배지분이 잡히면 그것, 아니면 총자본. 어느 쪽을 썼는지 남긴다 —
    # 비지배지분이 큰 지주·보험에서 폴백이 걸리면 BPS 가 통째로 부풀어
    # 오르는데, 결과만 보면 자본이 늘어난 것과 구분이 안 된다.
    eqo_owner = _bs(d_cur, "equity_owner")
    eqo_total = _bs(d_cur, "equity")
    eqo_q = (eqo_owner or eqo_total)
    if eqo_q is not None:
        eqo_q *= unit
    # 자본잠식(자본 ≤ 0)이면 BPS·PBR은 무의미 → 숨김
    # EPS 를 숨겼다는 건 주식수(가중평균)를 못 믿는다는 뜻이다. BPS 도 같은
    # 분모로 나눈 값이므로 같이 숨긴다. 이마트가 그랬다 — 분모가 1,600만주로
    # 잡혀(실제 2,760만주) BPS 824,830원·PBR 0.09 가 나왔다. 주가는 7만원대다.
    bps_q = (None if eps_hidden
             else (int(eqo_q / bps_denom) if (eqo_q and eqo_q > 0 and bps_denom) else None))
    log(f"  · BPS 입력: 자본 {(eqo_q or 0)/1e12:,.1f}조"
        f"({'지배지분' if eqo_owner else ('총자본-폴백' if eqo_total else '없음')})"
        f" ÷ 주식수 {(bps_denom or 0)/1e6:,.0f}백만"
        f"({'가중평균' if wavg else '발행총수'}) = BPS {bps_q}")
    pbr_q = round(price / bps_q, 2) if (bps_q and price) else None

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
    if bps_q and eqo_owner and eqo_total and eqo_owner > eqo_total * 1.01:
        log(f"  ❌ 자본 정합성 실패 → BPS·PBR 숨김: 지배지분 "
            f"{eqo_owner * unit/1e12:,.1f}조 > 자본총계 {eqo_total * unit/1e12:,.1f}조")
        bps_q = pbr_q = None

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
        try:
            df = dart.report(ticker, "주식총수", year, code)
        except Exception:
            df = None
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
        try:
            df = dart.report(ticker, "배당", year, "11011")
        except Exception:
            df = None
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
  "valuation_comment": {"ko": "밸류에이션 해설 4~6문장. ★현재 PER·PBR·배당수익률·현재가·시가총액은 주가 따라 매일 바뀌므로 '정확한 수치'를 문장에 쓰지 말 것(그 값은 화면 카드가 실시간 표시). 대신 수준을 관계로 서술 — 예: 과거 거래 밴드 상단/하단, 업종 평균 상회/하회, 순자산 대비 프리미엄/할인. ★ROE(자기자본이익률)는 절대 언급하지 말 것(서비스에서 제외된 지표). EPS·BPS를 언급할 땐 제공된 valuation의 헤드라인 값(eps, bps = 화면 카드와 동일)만 사용. 특정 연도 연간 EPS 수치는 valuation_comment에 쓰지 말 것(연간 추이 해설은 earnings 섹션이 담당). 다년 변화가 필요하면 '적자→흑자 전환', '이익 회복' 같은 방향으로만 표현. 'TTM'·'후행' 등 전문 용어는 표면에 쓰지 말 것. '비싸다/싸다' 단정·권유 금지, 사실 비교만", "en": "..."},
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
    return f"""다음 종목의 기업 리서치 리포트(v2)를 작성하세요.

[기준 데이터 — {as_of} KST]
- 종목명: {stock['name']} ({stock['ticker']}) · {stock.get('market','')} · {stock.get('sector','')}
- 현재가 {stock.get('price'):,}원 · 시가총액 {stock.get('mcap'):,.1f}조원

[확정 재무 — DART 공시·KRX 공식 값. 모든 단위 원. 아래 JSON의 숫자만 '사실'로 사용]
{qjson}

[작성 지침]
1. web_search로 최신 사업 현황·업황·뉴스·가이던스를 조사하세요(한국어, 3~6회). 신뢰 출처만: DART·기업 IR·증권사 리포트·주요 언론. 나무위키 등 위키·블로그·커뮤니티 금지.
2. **재무 수치는 위 [확정 재무] JSON의 값만 사용하세요.** 검색에서 다른 수치가 나오면 위 값을 우선합니다. 거기 없는 숫자(예: 부문별 매출액)는 검색으로 확인된 것만 출처·시점과 함께 쓰고, 확인 안 되면 정성 서술로 대체하세요. 숫자를 절대 지어내지 마세요.
3. earnings 섹션은 제공된 연간·분기 실적 수치(과거 확정치라 안 변함)를 구체적으로 인용·해석하세요. **valuation_comment 에서는 '현재 PER·PBR·배당수익률·현재가·시가총액'의 정확한 수치를 문장에 쓰지 마세요** — 이 값들은 주가 따라 매일 바뀌고 화면 카드가 실시간으로 표시합니다. 대신 그 수준을 '관계'로 서술하세요(예: "과거 거래 밴드(약 10~20배)의 상단을 웃돈다", "배당수익률은 업종 평균을 밑도는 편", "순자산 대비 프리미엄이 큰 구간"). 과거 PER 밴드, DPS, 다년 실적 추세는 인용해도 됩니다. **★ROE(자기자본이익률)는 절대 언급하지 마세요 — 서비스에서 제외된 지표입니다.** EPS·BPS는 [확정 재무]의 valuation.eps·bps(사용자 카드와 동일한 값)만 쓰고, 연도별 EPS 수치는 valuation_comment에 넣지 마세요(연간 실적 해설은 earnings 섹션에서). 다년 변화가 필요하면 "적자에서 흑자로 전환", "이익 회복" 처럼 방향으로만 표현하세요. 'TTM'·'선행/후행' 같은 용어와 '비싸다/싸다' 단정·매수/매도 권유는 금지.
4. checkpoints 는 '다음에 무엇을 확인해야 하는가'입니다 — 다가오는 분기 실적 발표, 수주·증설·규제 이벤트 등 확인 가능한 일정 위주로.
5. 균형: 강세·약세 요인을 같은 무게로. **우리(코사이)의 투자의견·매수/매도·목표주가는 절대 제시하지 말 것**(정보 제공용).
5-0. **증권사 목표주가 인용은 허용** — 우리 의견이 아니라 '누가 무엇을 제시했다'는 사실이기 때문이다. 다만 아래 셋을 모두 지킬 때만 쓰고, 하나라도 못 지키면 아예 쓰지 말 것.
   ① **출처와 시점을 함께** 쓴다 — "KB증권이 2026년 6월 리포트에서 …로 제시했다". 증권사명이나 시점 중 하나라도 확인되지 않으면 쓰지 않는다.
   ② **우리 판단이 아님이 문장에서 분명**해야 한다 — 전달 동사("제시했다", "밝혔다", "전망했다")로 끝내고, 우리 voice로 동조하거나 평가하지 않는다.
   ③ **6개월이 지난 것은 쓰지 않는다** — 낡은 목표주가를 현재형으로 옮기면 사실상 거짓이 된다. 시점이 오래됐으면 숫자 대신 정성 서술로 대체한다.
5-1. **단정적 주가 방향성 금지(중립 필수)**: KOSAI는 등록된 투자자문업자가 아니다. "상승 여력(이 충분/크다)", "추가 상승 여지", "재평가 모멘텀이 온다", "조정 후 반등", "저평가라 오를 것", "매집 신호=강세" 같은 *주가가 오른다/내린다는 우리 자신의 단정·예측*은 절대 쓰지 말 것. 대신 사실과 강세 vs 약세 구도를 제시하고 판단은 독자에게 맡긴다. ㅇ 밸류에이션·방향성 의견은 *출처를 명시한 인용*으로만 허용("○○증권은 …라고 평가했다") — 이때도 우리 voice로 동조하지 말 것. ㅇ '상승 여력'은 *영업이익률·가동률·침투율·환원율 등 사업 지표*의 개선 여지에만 한정해 쓰고, *주가/밸류 멀티플*에는 쓰지 말 것. ㅇ 내부자·기관의 지분 매수는 '매집해서 오른다'가 아니라 사실(누가·언제·얼마)과 중립 해석으로만.
6. 한국어(ko)/영어(en) 모두 작성. 영어에 한국어 혼입 금지.
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


def valid_v2(rep):
    try:
        need = ("title", "lead", "keypoints", "business", "earnings", "industry",
                "outlook", "valuation_comment", "bull", "bear", "risks",
                "checkpoints", "verdict")
        missing = [k for k in need if k not in rep]
        if missing:
            log(f"    (검증 실패: 누락 키 {missing})")
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
def pick_targets():
    data = g.load_stocks()
    env = os.getenv("REPORT_TICKERS", "").replace(" ", "")
    if env:
        want = [t for t in env.split(",") if t]
        by = {s["ticker"]: s for s in data["stocks"]}
        return data, [by[t] for t in want if t in by]
    # 자동 백필(fill): 시총 순위 [FILL_FROM, FILL_TO) 구간 중 아직 v2 리포트가 없는 종목.
    #   SHARDS/SHARD로 종목을 안정적으로 분할 → 여러 run이 겹치지 않게 병렬 백필 가능.
    fill_to = int(os.getenv("REPORT_FILL_TO", "0") or "0")
    if fill_to:
        import zlib
        fill_from = int(os.getenv("REPORT_FILL_FROM", "0") or "0")
        shards = int(os.getenv("REPORT_FILL_SHARDS", "1") or "1")
        shard = int(os.getenv("REPORT_FILL_SHARD", "0") or "0")
        skip = load_skip()
        ranked = sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:fill_to]
        ranked = ranked[fill_from:]
        missing = [s for s in ranked
                   if not (OUT_DIR / f"{s['ticker']}.json").exists() and s["ticker"] not in skip]
        if shards > 1:
            missing = [s for s in missing if zlib.crc32(s["ticker"].encode()) % shards == shard]
        return data, missing[:TOP_N]
    # 시총 상위 [FILL_FROM, FILL_FROM+TOP_N) 구간. patch 처럼 '이미 리포트가 있는'
    # 종목을 훑을 때는 위의 백필 경로(없는 것만 고름)를 쓸 수 없어 여기서 자른다.
    #   전 종목 patch 는 종목당 30초 안팎이라 한 잡에 다 안 들어간다(6시간 제한).
    #   FILL_FROM 을 0·700·1400·2100 으로 나눠 이어 돌린다.
    start = int(os.getenv("REPORT_FILL_FROM", "0") or "0")
    ranked = sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)
    stocks = ranked[start:start + TOP_N]
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
    # BPS 는 참조값이 가장 늦게 따라오는 지표다. 대신 collect_quant 에서
    # '분기말 자본이 이익으로 설명되는가' 를 이미 확인했다 — 시차를 타지 않는
    # 자체 기준이라 이쪽이 더 믿을 만하다. 참조값 대조는 그 뒤의 그물로 남긴다.
    if gross_error(valuation.get("bps"), nv.get("bps")):
        issues.append(f"BPS {valuation.get('bps')}↔ref {nv.get('bps')}")
        valuation["bps"] = valuation["pbr"] = None
    # 배당수익률 게이트 — 네이버 배당수익률과 30% 넘게 어긋나면 DPS 숨김.
    #   액면분할(분할 전 DPS) 등 배당 오류를 자동 차단. 배당은 시점·특별배당 차이로 30% 허용.
    our_div, nv_div = valuation.get("div"), nv.get("dividendyieldratio")
    if our_div and nv_div and abs(our_div - nv_div) / abs(nv_div) > 0.30:
        issues.append(f"배당 {our_div}%↔ref {nv_div}%")
        valuation["dps"] = valuation["div"] = None
    if issues:
        log(f"  ❌ {name} 중대오류 차단 → 해당 지표 숨김: {' / '.join(issues)}")
    else:
        log(f"  ✅ {name} 검증 통과 PER {valuation.get('per')} PBR {valuation.get('pbr')} "
            f"EPS {valuation.get('eps')} BPS {valuation.get('bps')}"
            f"{' (EPS 는 자체 대조로 확인 — 참조값 시차)' if skip_eps_ref else ''}")


def collect_all_quant(targets, data):
    dart = g.get_dart()
    if not dart:
        log("❌ DART 초기화 실패 — 정량 수집 불가")
        sys.exit(1)
    fund = krx_fundamentals(data.get("dataDate", ""))
    out = {}
    for st in targets:
        tk = st["ticker"]
        log(f"- 정량 수집 {tk} {st['name']}...")
        krx_row = None
        if fund is not None and tk in fund.index:
            krx_row = fund.loc[tk]
        try:
            out[tk] = collect_quant(dart, tk, krx_row, st)
            cross_check(tk, st["name"], out[tk]["valuation"])
            log(quant_summary(st["name"], out[tk]))
        except Exception as e:
            log(f"  ⚠️ {tk} 정량 수집 실패: {type(e).__name__}: {e}")
    return out


# ── 배치 제출/회수 ────────────────────────────────────────────────────
def submit(cl, as_of):
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    data, targets = pick_targets()
    # 전체 universe 시총 순위(1=최대) → 종목별 모델 결정
    ranked = sorted(data["stocks"], key=lambda s: s.get("mcap", 0) or 0, reverse=True)
    rank_of = {s["ticker"]: i + 1 for i, s in enumerate(ranked)}
    log(f"## 🤖 리포트 v2 Batch 제출 — {len(targets)}개 · 상위{MODEL_TOP_N} {MODEL_TOP} / 나머지 {MODEL_REST}")
    quants = collect_all_quant(targets, data)

    reqs, models, excluded = [], {}, []
    for st in targets:
        tk = st["ticker"]
        if tk not in quants or not quants[tk]["annual"]:
            log(f"  · ⚠️ {tk} 정량 데이터 없음 — 제외")
            excluded.append(tk)
            continue
        mdl = model_for(rank_of.get(tk))
        models[tk] = mdl
        prompt = build_prompt_v2(st, quants[tk], as_of)
        reqs.append(Request(
            custom_id=tk,
            params=MessageCreateParamsNonStreaming(
                model=mdl, max_tokens=96000,
                system=[{"type": "text", "text": SYSTEM_V2, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=[{"role": "user", "content": prompt}],
            ),
        ))
    # 백필(fill) 모드에서 정량 데이터가 없어 제외된 종목은 skip 목록에 기록 →
    # self-chain/watchdog이 같은 종목을 영원히 재시도하지 않고 정상 종료한다.
    # (명시적 티커 지정 run은 skip을 건드리지 않아 병렬 실행 시 파일 충돌이 없다.)
    if os.getenv("REPORT_FILL_TO", "0") not in ("0", "") and excluded:
        add_skip(excluded)
        log(f"- 생성 불가 {len(excluded)}개 skip 기록 → data/reports_v2_skip.txt")
    if not reqs:
        log("❌ 제출할 요청이 없습니다.")
        sys.exit(0)
    n_top = sum(1 for m in models.values() if m == MODEL_TOP)
    log(f"- 모델 배분: {MODEL_TOP} {n_top}개 · {MODEL_REST} {len(models)-n_top}개")

    batch = cl.messages.batches.create(requests=reqs)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {"batch_id": batch.id, "created": as_of, "model": MODEL, "models": models,
             "dataDate": data.get("dataDate", ""), "count": len(reqs),
             "quant": quants}
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건)")
    return batch.id


def pickup(cl, as_of):
    """남아 있는 배치가 끝났으면 회수한다. 재과금 없다.

    auto 가 주문만 넣고 끝내므로 누군가는 결과를 받으러 와야 한다. 그게
    이 함수고, collect_batch 워크플로가 30분마다 부른다.

    이미 회수한 배치를 또 회수하면 리포트를 같은 내용으로 덮어쓴다. 그래서
    회수가 끝나면 상태에 표시를 남기고, 표시가 있으면 건너뛴다.
    """
    if not STATE_JS.exists():
        log("- 남은 배치 없음")
        return
    state = json.loads(STATE_JS.read_text(encoding="utf-8"))
    bid = state.get("batch_id")
    if not bid:
        log("- 남은 배치 없음")
        return
    if state.get("collected"):
        log(f"- {bid} 는 이미 회수했다")
        return
    if state.get("abandoned"):
        log(f"- {bid} 는 버리기로 한 배치다 — 건너뛴다")
        return
    b = cl.messages.batches.retrieve(bid)
    rc = b.request_counts
    log(f"- {bid} · 상태 {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
    if b.processing_status != "ended":
        log("- 아직 처리 중 — 다음 차례에 다시 온다")
        return
    collect(cl, as_of)
    state = json.loads(STATE_JS.read_text(encoding="utf-8"))
    state["collected"] = as_of
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"✅ {bid} 회수 완료")


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


def collect(cl, as_of):
    state = json.loads(STATE_JS.read_text(encoding="utf-8"))
    batch_id = state["batch_id"]
    b = cl.messages.batches.retrieve(batch_id)
    if b.processing_status != "ended":
        log(f"- 아직 처리 중({b.processing_status}).")
        return False

    data = g.load_stocks()
    by_tk = {s["ticker"]: s for s in data["stocks"]}
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ok, fail, done, flagged = 0, 0, [], []
    for result in cl.messages.batches.results(batch_id):
        tk = result.custom_id
        if result.result.type != "succeeded":
            fail += 1
            log(f"  · ⚠️ {tk} 결과 {result.result.type}")
            continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            _sanitize(rep)
            if not valid_v2(rep):
                fail += 1
                log(f"  · ⚠️ {tk} 스키마 불완전 — 건너뜀")
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
                "dataDate": data.get("dataDate", ""),
                "quant": state["quant"].get(tk, {}),
            })
            # 금지 표현 검사 — 프롬프트는 부탁이지 강제가 아니다. 실제로 2,563개 중
            # 96개(3.7%)가 금지해 둔 표현을 담고 있었다. 여기서 걸러 로그에 남기면
            # 어느 종목을 다시 만들어야 하는지 run 로그만 보고 알 수 있다.
            # 리포트는 그대로 쓴다 — 글 하나 때문에 종목을 통째로 비우는 게 더 나쁘다.
            try:
                bad_text = check_report_text.check(rep)
            except Exception:
                bad_text = []
            if bad_text:
                flagged.append(tk)
                kinds = sorted({h["rule"] for h in bad_text})
                risky = any(h["level"] == "위험" for h in bad_text)
                log(f"  · {'🚫' if risky else '⚠️'} {tk} 금지 표현 {len(bad_text)}건 "
                    f"({', '.join(kinds)}) — {bad_text[0]['sentence'][:70]}")

            (OUT_DIR / f"{tk}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            done.append(tk)
            ok += 1
        except Exception as e:
            fail += 1
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e}")

    # 전역 인덱스(reports-index.js)는 병렬 커밋 충돌을 피하려 여기서 쓰지 않는다.
    # → 워치독이 reindex(단일 직렬)로 전체 v2에서 재생성한다. 이 run은 자기 종목 JSON만 커밋.
    have = sorted(p.stem for p in OUT_DIR.glob("*.json") if p.stem.isdigit())
    log(f"\n✅ v2 회수 완료 · 성공 {ok}/실패 {fail} → data/reports_v2/ ({len(have)}개)")
    if flagged:
        log(f"⚠️ 금지 표현이 남은 {len(flagged)}개 — 다시 만들 대상: {','.join(flagged)}")
    return True


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


def patch_quant(as_of):
    """기존 v2 리포트의 정량(quant) 블록만 다시 수집해 교체한다(LLM 재호출 없음·무료).
    본문 텍스트는 그대로 두고 숫자만 최신 방식으로 갱신할 때 사용."""
    data, targets = pick_targets()
    quants = collect_all_quant(targets, data)
    n = 0
    for st in targets:
        tk = st["ticker"]
        f = OUT_DIR / f"{tk}.json"
        if tk in quants and f.exists():
            rep = json.loads(f.read_text(encoding="utf-8"))
            rep["quant"] = quants[tk]
            rep["dataDate"] = data.get("dataDate", rep.get("dataDate", ""))
            f.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
            log(f"  · 정량 교체 {tk} {st['name']}")
    log(f"\n✅ 정량 patch 완료: {n}건 (본문 텍스트 유지)")


def recover(cl, as_of, batch_id=""):
    """취소된 run에서 제출됐으나 회수 못한 배치를 ID로 회수한다(재과금 없음).
    제출 시점 quant(state)가 유실됐으므로 현재 데이터로 재수집해 채운다(표시용이라 무방).
    batch_id 비우면 가장 최근 배치를 사용."""
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
    data, targets = pick_targets()
    ranked = sorted(data["stocks"], key=lambda s: s.get("mcap", 0) or 0, reverse=True)
    rank_of = {s["ticker"]: i + 1 for i, s in enumerate(ranked)}
    log(f"- 정량 재수집 {len(targets)}개(제출시점 quant 유실분 재구성)...")
    quants = collect_all_quant(targets, data)
    models = {st["ticker"]: model_for(rank_of.get(st["ticker"])) for st in targets}
    state = {"batch_id": batch_id, "created": as_of, "model": MODEL, "models": models,
             "dataDate": data.get("dataDate", ""), "count": len(quants), "quant": quants}
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"- 상태 재구성 완료(quant {len(quants)}) → 회수 시작")
    collect(cl, as_of)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    if mode == "quant":
        data, targets = pick_targets()
        collect_all_quant(targets, data)
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
    #
    # 켜고 끄는 법:  파일을 지우면 다시 돈다.  touch data/reports_paused 로 멈춘다.
    if PAUSE_FILE.exists():
        why = PAUSE_FILE.read_text(encoding="utf-8").strip()
        log(f"⏸️  과금 정지 중 — '{mode}' 를 건너뛴다.")
        log(f"    {PAUSE_FILE.relative_to(ROOT)} 을 지우면 다시 돈다.")
        if why:
            log(f"    사유: {why.splitlines()[0]}")
        return

    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음")
        sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    if mode == "submit":
        submit(cl, as_of)
    elif mode == "collect":
        collect(cl, as_of)
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
        # 취소된 배치 회수: ID로 배치 지정 → 정량 재수집 후 결과 회수(재과금 없음)
        recover(cl, as_of, os.getenv("RECOVER_BATCH_ID", ""))
    elif mode == "pickup":
        pickup(cl, as_of)
    else:
        # auto — 주문을 넣고 잠깐만 기다린다.
        #
        # 전에는 여기서 최대 5시간을 기다렸다. 배치는 24시간까지 걸릴 수
        # 있는데 잡은 6시간에 잘리므로, 기다리다 잘리면 결과를 못 받는다.
        # 8월 20일 새벽 479건이 그렇게 날아갔다. 돈은 이미 나간 뒤였다.
        #
        # 그래서 짧게만 기다리고(SHORT_WAIT), 안 끝났으면 그대로 끝낸다.
        # 남은 배치는 collect_batch 워크플로가 30분마다 와서 회수한다.
        # 주문과 회수가 분리되면 6시간 제한이 의미가 없어진다.
        bid = submit(cl, as_of)
        if bid and poll(cl, bid, budget=SHORT_WAIT):
            collect(cl, as_of)
        elif bid:
            log(f"- 아직 처리 중 — 여기서 끝낸다. collect_batch 가 회수한다({bid}).")


if __name__ == "__main__":
    main()
