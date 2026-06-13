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
          REPORT_MODEL_V2(기본 claude-opus-4-8), REPORT_TICKERS, REPORT_TOP_N(기본 10),
          BATCH_MAX_WAIT_SEC
"""

import datetime
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate_reports as g  # log/extract_text/collect_sources/load_stocks 재사용

OUT_DIR = ROOT / "data" / "reports_v2"
STATE_JS = ROOT / "data" / "batch_state_v2.json"

MODEL = os.getenv("REPORT_MODEL_V2", "claude-opus-4-8")
TOP_N = int(os.getenv("REPORT_TOP_N", "10"))
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "10800"))

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6,
          "blocked_domains": ["namu.wiki", "librewiki.net", "dcinside.com", "fmkorea.com"],
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log


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
    return out


# ── 정량 1: DART 전체 재무제표 ────────────────────────────────────────
# account_id 우선, 계정명 폴백. 연결(CFS) 기준.
ACC_IDS = {
    "rev":          ("ifrs-full_Revenue", "ifrs_Revenue"),
    "rev_ins":      ("ifrs-full_InsuranceRevenue", "ifrs_InsuranceRevenue"),
    "op":           ("dart_OperatingIncomeLoss",),
    "np":           ("ifrs-full_ProfitLoss", "ifrs_ProfitLoss"),
    "np_owner":     ("ifrs-full_ProfitLossAttributableToOwnersOfParent",
                     "ifrs_ProfitLossAttributableToOwnersOfParent"),
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
    "op":           ("영업이익", "영업이익(손실)"),
    "np":           ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"),
    "np_owner":     ("지배기업소유주지분", "지배기업의소유주에게귀속되는당기순이익",
                     "지배기업소유주귀속당기순이익", "지배주주순이익"),
    "eps_basic":    ("기본주당이익", "기본주당순이익", "기본주당이익(손실)", "기본및희석주당이익"),
    "assets":       ("자산총계",),
    "liab":         ("부채총계",),
    "equity":       ("자본총계",),
    "equity_owner": ("지배기업소유주지분", "지배기업의소유주에게귀속되는자본"),
    "cfo":          ("영업활동현금흐름", "영업활동으로인한현금흐름"),
}


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
        if key in ("rev", "rev_ins", "op", "np", "np_owner", "eps_basic"):
            return sj in ("IS", "CIS")
        if key in ("assets", "liab", "equity", "equity_owner"):
            return sj == "BS"
        return sj == "CF"

    out = {}
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
            if key == "np_owner" and sj != "IS":
                continue
            if anm in ACC_NAMES[key]:
                out[key] = {"amt": amt, "add": add}
    # 불변식: |지배주주 순이익| ≤ |전체 순이익|×1.02 (어기면 포괄손익 오추출 → 전체 순이익 사용)
    if "np" in out and "np_owner" in out:
        np_v, npo_v = out["np"]["amt"], out["np_owner"]["amt"]
        if np_v is not None and npo_v is not None and abs(npo_v) > abs(np_v) * 1.02:
            out["np_owner"] = dict(out["np"])
    return out or None


def _cum(d, key):
    """보고서 기준 누적값: thstrm_add_amount 우선, 없으면 thstrm_amount."""
    if not d or key not in d:
        return None
    v = d[key]
    return v["add"] if v["add"] is not None else v["amt"]


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
    for yr in range(cur - 1, cur - 5, -1):
        d = _fin_all(dart, ticker, yr, "11011")
        if not d:
            continue
        rev, op = _cum(d, "rev"), _cum(d, "op")
        np_, npo = _cum(d, "np"), _cum(d, "np_owner")
        eq, eqo, li = _bs(d, "equity"), _bs(d, "equity_owner"), _bs(d, "liab")
        row = {
            "year": yr, "rev": rev, "op": op, "np": np_,
            "np_owner": npo if npo is not None else np_,
            "equity": eq, "equity_owner": (eqo if eqo is not None else eq),
            "liab": li, "cfo": _cum(d, "cfo"),
            "eps_basic": _cum(d, "eps_basic"),
        }
        row["opm"] = round(op / rev * 100, 1) if (op is not None and rev) else None
        base_np = row["np_owner"]
        base_eq = eqo if eqo is not None else eq
        row["roe"] = round(base_np / base_eq * 100, 1) if (base_np is not None and base_eq) else None
        row["debt_ratio"] = round(li / eq * 100, 1) if (li is not None and eq) else None
        annual.append(row)
        time.sleep(0.3)

    # 분기: 전년 Q1~Q4 + 올해 Q1 (누적 차감으로 단일 분기화)
    py = cur - 1
    dq1 = _fin_all(dart, ticker, py, "11013")
    dh1 = _fin_all(dart, ticker, py, "11012")
    d9m = _fin_all(dart, ticker, py, "11014")
    dfy = next((dict(a=a) for a in []), None)  # placeholder
    fy_row = next((a for a in annual if a["year"] == py), None)
    dq1c = _fin_all(dart, ticker, cur, "11013")
    time.sleep(0.3)

    def quarters(key, fy_total):
        c1, ch, c9 = _cum(dq1, key), _cum(dh1, key), _cum(d9m, key)
        q = {
            f"{py}Q1": c1,
            f"{py}Q2": _sub(ch, c1),
            f"{py}Q3": _sub(c9, ch),
            f"{py}Q4": _sub(fy_total, c9),
            f"{cur}Q1": _cum(dq1c, key),
        }
        return q

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

    quarterly = []
    rev_key = "rev_ins" if rev_label else "rev"
    rev_q = quarters(rev_key, fy_row["rev"] if fy_row else None)
    if all(v is None for v in rev_q.values()):
        c1 = rev_fallback(py, "11013")
        ch = rev_fallback(py, "11012")
        c9 = rev_fallback(py, "11014")
        fy = fy_row["rev"] if fy_row else None
        cq = rev_fallback(cur, "11013")
        cand = {f"{py}Q1": c1, f"{py}Q2": _sub(ch, c1), f"{py}Q3": _sub(c9, ch),
                f"{py}Q4": _sub(fy, c9), f"{cur}Q1": cq}
        # 차감 결과 음수(누적 가정 오류)면 채택하지 않음
        if not any(v is not None and v < 0 for v in cand.values()):
            rev_q = cand
    op_q = quarters("op", fy_row["op"] if fy_row else None)
    npo_q = quarters("np_owner", fy_row["np_owner"] if fy_row else None)
    np_q = quarters("np", fy_row["np"] if fy_row else None)
    for label in (f"{py}Q1", f"{py}Q2", f"{py}Q3", f"{py}Q4", f"{cur}Q1"):
        npo = npo_q.get(label)
        quarterly.append({
            "q": label, "rev": rev_q.get(label), "op": op_q.get(label),
            "np_owner": npo if npo is not None else np_q.get(label),
        })

    # TTM 지배주주 순이익 = 전년 연간 − 전년 Q1 + 올해 Q1
    ttm_np = None
    if fy_row:
        py_q1 = npo_q.get(f"{py}Q1") or np_q.get(f"{py}Q1")
        cy_q1 = npo_q.get(f"{cur}Q1") or np_q.get(f"{cur}Q1")
        fy_np = fy_row["np_owner"]
        if None not in (py_q1, cy_q1, fy_np):
            ttm_np = fy_np - py_q1 + cy_q1

    price = stock.get("price")
    total_sh = dart_total_shares(dart, ticker) or stock.get("shares") or 0

    # 가중평균 유통주식수 = 회사 공시 (지배주주 순이익 ÷ 공시 기본EPS) 로 역산.
    #   네이버·토스가 쓰는 분모와 같아져 EPS·PER이 일치한다. 자기주식이 자동 제외됨.
    #   최근 시점 우선(올해 Q1 → 직전 연간). 둘 다 없으면 발행주식총수로 폴백.
    def implied_wavg(npo, eps):
        if npo and eps and abs(eps) > 1:
            w = npo / eps
            if w > 0 and 0.3 * total_sh <= w <= 1.05 * total_sh:  # 상식 범위(자기주식 차감 고려)
                return w
        return None

    wavg = (implied_wavg(_cum(dq1c, "np_owner"), _cum(dq1c, "eps_basic"))
            or (implied_wavg(fy_row["np_owner"], fy_row["eps_basic"]) if fy_row else None))

    # 경험칙(상위 10개 ↔ 네이버 대조 결과): EPS·PER 은 발행주식총수,
    #   BPS·PBR 은 가중평균 유통주식수(자기주식 제외)일 때 네이버와 가장 일치한다.
    eps_ttm = int(ttm_np / total_sh) if (ttm_np and total_sh) else None
    per_ttm = round(price / eps_ttm, 1) if (eps_ttm and eps_ttm > 0 and price) else None

    bps_denom = wavg or total_sh
    eqo_q = _bs(dq1c, "equity_owner") or _bs(dq1c, "equity")
    bps_q = int(eqo_q / bps_denom) if (eqo_q and bps_denom) else None
    pbr_q = round(price / bps_q, 2) if (bps_q and price) else None

    # ROE(TTM) = 최근 4개 분기 지배순이익 ÷ 평균 지배자본(전기말·최근분기말) — 토스·FnGuide 방식
    fy_eqo = fy_row.get("equity_owner") if fy_row else None
    avg_eq = ((fy_eqo + eqo_q) / 2) if (fy_eqo and eqo_q) else (eqo_q or fy_eqo)
    roe_ttm = round(ttm_np / avg_eq * 100, 1) if (ttm_np is not None and avg_eq) else None

    valuation = {
        "price": price, "mcap": stock.get("mcap"), "shares": stock.get("shares"),
        "total_shares": total_sh, "wavg_shares": int(wavg) if wavg else None,
        "per": per_ttm, "eps": eps_ttm,          # 최근 4개 분기 순이익 ÷ 가중평균유통주식수 (네이버 방식)
        "pbr": pbr_q, "bps": bps_q,              # 최근 분기말 지배주주 자본 ÷ 유통주식수 (네이버 방식)
        "roe_ttm": roe_ttm,                      # 헤드라인 ROE(최근 4분기 ÷ 평균자본)
        "ttm_window": f"{py}Q2~{cur}Q1" if ttm_np else None,
        "ttm_np_owner": ttm_np,
        "pbr_krx": None, "bps_krx": None,        # KRX 공식값(참고·대조용)
        "basis": "PER·EPS·PBR·BPS 모두 자체 산출(네이버·토스와 동일 방식) · 배당은 DART 공시 주당현금배당금(보완:KRX) ÷ 현재가",
    }
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
        tot = 0
        for _, r in df.iterrows():
            se = str(r.get("se", "")).replace(" ", "")
            if se in ("보통주", "우선주"):
                v = g._num(r.get("istc_totqy"))
                if v and v > 0:
                    tot += v
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
        best, saw_row = None, False
        for _, r in df.iterrows():
            se = str(r.get("se", "")).replace(" ", "")
            knd = str(r.get("stock_knd", "")).replace(" ", "")
            if "주당현금배당금" in se:
                if knd and "보통" not in knd:
                    continue
                saw_row = True
                v = g._num(r.get("thstrm"))   # '-'/공란 → None
                if v is not None and v >= 0:
                    best = v
                    if not knd or "보통" in knd:
                        break
        if best is not None:
            return float(best)
        # 배당 항목은 있으나 값이 '-' → 해당 연도 현금배당 없음(0). 단, 그 전년도 먼저 재확인.
        if saw_row and year == cur - 1:
            continue
        if saw_row:
            return 0.0
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
                 f"BPS {v.get('bps')} | ROE(TTM) {v.get('roe_ttm')} | 배당 {v.get('div')}% | DPS {v.get('dps')}")
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
  "valuation_comment": {"ko": "밸류에이션 해설 4~6문장. 제공된 PER·PBR·배당 수치를 과거 밴드·업종 맥락에서 서술. 'TTM' 등 전문 용어 금지. '비싸다/싸다' 단정·권유 금지, 사실 비교만", "en": "..."},
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
3. earnings 섹션은 제공된 분기 추이(전 분기·전년 동기 비교)를 구체적으로 해석하세요. valuation_comment 는 제공된 per·pbr·배당 수치를 인용하며 과거 수준·업종 평균과 비교해 서술하세요(예: "PER 26배로 과거 평균 대비…"). 제공된 PER·PBR·EPS·BPS 숫자는 그대로 본문에 써도 됩니다. 다만 'TTM', '12개월 선행/후행' 같은 전문 용어는 쓰지 말고(필요하면 "최근 4개 분기 기준" 정도로), '비싸다/싸다' 단정이나 매수·매도 권유는 하지 마세요.
4. checkpoints 는 '다음에 무엇을 확인해야 하는가'입니다 — 다가오는 분기 실적 발표, 수주·증설·규제 이벤트 등 확인 가능한 일정 위주로.
5. 균형: 강세·약세 요인을 같은 무게로. 투자의견·매수/매도·목표주가 표현 금지(정보 제공용).
6. 한국어(ko)/영어(en) 모두 작성. 영어에 한국어 혼입 금지.

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
    stocks = sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:TOP_N]
    return data, stocks


def naver_valuation(ticker):
    """네이버 모바일 증권 API에서 PER/PBR/EPS/BPS 참조값. 실패 시 {}."""
    import requests
    try:
        r = requests.get(f"https://m.stock.naver.com/api/stock/{ticker}/integration",
                         headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        out = {}
        for it in (r.json().get("totalInfos") or []):
            cd = str(it.get("code", "")).lower()
            if cd in ("per", "pbr", "eps", "bps"):
                v = str(it.get("value", "")).replace(",", "")
                v = v.replace("배", "").replace("원", "").replace("%", "").strip()
                try:
                    out[cd] = float(v)
                except ValueError:
                    pass
        return out
    except Exception:
        return {}


def cross_check(tk, name, valuation):
    """자체 산출하는 PER·EPS만 네이버와 대조해 '중대 오류'(부호 반대·30% 초과)일 때만 숨긴다.
    미세 차이(가중평균주식수·결산시점 등 방법론 차이)는 정상이므로 표시한다.
    PBR·BPS·배당은 KRX 공식값이라 검증 없이 표시한다."""
    nv = naver_valuation(tk)
    valuation["naver_ref"] = nv or None
    if not nv:
        valuation["verify"] = "unverified(네이버 참조 없음)"
        log(f"  ⚠️ {name}: 네이버 참조 없음 — 자체 PER·EPS 미검증 표시")
        return

    def gross_error(mine, ref):
        if mine is None or ref in (None, 0):
            return False
        if (mine > 0) != (ref > 0):           # 부호 반대 = 중대 오류
            return True
        return abs(mine - ref) / abs(ref) > 0.15   # 15% 초과 = 중대 오류(네이버와 크게 어긋남)

    issues = []
    if gross_error(valuation.get("eps"), nv.get("eps")):
        issues.append(f"EPS {valuation.get('eps')}↔네이버 {nv.get('eps')}")
        valuation["eps"] = valuation["per"] = None
    if gross_error(valuation.get("bps"), nv.get("bps")):
        issues.append(f"BPS {valuation.get('bps')}↔네이버 {nv.get('bps')}")
        valuation["bps"] = valuation["pbr"] = None
    valuation["verify"] = ("blocked(중대오류): " + " / ".join(issues)) if issues else "ok"
    if issues:
        log(f"  ❌ {name} 중대오류 차단 → 해당 지표 숨김: {' / '.join(issues)}")
    else:
        log(f"  ✅ {name} PER {valuation.get('per')}(네이버 {nv.get('per')}) "
            f"PBR {valuation.get('pbr')}(네이버 {nv.get('pbr')}) "
            f"EPS {valuation.get('eps')}(네이버 {nv.get('eps')}) "
            f"BPS {valuation.get('bps')}(네이버 {nv.get('bps')})")


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
    log(f"## 🤖 리포트 v2 Batch 제출 — {len(targets)}개 · 모델 {MODEL}")
    quants = collect_all_quant(targets, data)

    reqs = []
    for st in targets:
        tk = st["ticker"]
        if tk not in quants or not quants[tk]["annual"]:
            log(f"  · ⚠️ {tk} 정량 데이터 없음 — 제외")
            continue
        prompt = build_prompt_v2(st, quants[tk], as_of)
        reqs.append(Request(
            custom_id=tk,
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=96000,
                system=[{"type": "text", "text": SYSTEM_V2, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"},
                tools=TOOLS,
                messages=[{"role": "user", "content": prompt}],
            ),
        ))
    if not reqs:
        log("❌ 제출할 요청이 없습니다.")
        sys.exit(1)

    batch = cl.messages.batches.create(requests=reqs)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {"batch_id": batch.id, "created": as_of, "model": MODEL,
             "dataDate": data.get("dataDate", ""), "count": len(reqs),
             "quant": quants}
    STATE_JS.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건)")
    return batch.id


def poll(cl, batch_id):
    waited = 0
    while waited < MAX_WAIT:
        b = cl.messages.batches.retrieve(batch_id)
        rc = b.request_counts
        log(f"  · 상태 {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
        if b.processing_status == "ended":
            return True
        time.sleep(60)
        waited += 60
    log("- ⏳ 시간 내 미완료. collect 모드로 회수하세요.")
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

    ok, fail, done = 0, 0, []
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
                "v": 2, "model": state.get("model", MODEL),
                "ticker": tk, "name": st.get("name", tk),
                "name_en": st.get("name_en", st.get("name", tk)),
                "sector": st.get("sector", ""), "categories": st.get("categories", []),
                "market": st.get("market", ""),
                "reportDate": now.strftime("%Y-%m-%d"),
                "reportTs": now.strftime("%Y-%m-%d %H:%M"),
                "dataDate": data.get("dataDate", ""),
                "quant": state["quant"].get(tk, {}),
            })
            (OUT_DIR / f"{tk}.json").write_text(
                json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
            done.append(tk)
            ok += 1
        except Exception as e:
            fail += 1
            log(f"  · ⚠️ {tk} 파싱 실패: {type(e).__name__}: {e}")

    # 인덱스(존재하는 v2 리포트 목록)
    have = sorted(p.stem for p in OUT_DIR.glob("*.json") if p.stem.isdigit())
    (OUT_DIR / "index.json").write_text(json.dumps(have), encoding="utf-8")
    sync_list_index(have)
    log(f"\n✅ v2 회수 완료 · 성공 {ok}/실패 {fail} → data/reports_v2/ ({len(have)}개)")
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
    else:
        bid = submit(cl, as_of)
        if bid and poll(cl, bid):
            collect(cl, as_of)


if __name__ == "__main__":
    main()
