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


# ── 정량 1: DART 전체 재무제표 ────────────────────────────────────────
# account_id 우선, 계정명 폴백. 연결(CFS) 기준.
ACC_IDS = {
    "rev":          ("ifrs-full_Revenue", "ifrs_Revenue"),
    "op":           ("dart_OperatingIncomeLoss",),
    "np":           ("ifrs-full_ProfitLoss", "ifrs_ProfitLoss"),
    "np_owner":     ("ifrs-full_ProfitLossAttributableToOwnersOfParent",
                     "ifrs_ProfitLossAttributableToOwnersOfParent"),
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
    "op":           ("영업이익", "영업이익(손실)"),
    "np":           ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익"),
    "np_owner":     ("지배기업소유주지분", "지배기업의소유주에게귀속되는당기순이익",
                     "지배기업소유주귀속당기순이익", "지배주주순이익"),
    "assets":       ("자산총계",),
    "liab":         ("부채총계",),
    "equity":       ("자본총계",),
    "equity_owner": ("지배기업소유주지분", "지배기업의소유주에게귀속되는자본"),
    "cfo":          ("영업활동현금흐름", "영업활동으로인한현금흐름"),
}


def _fin_all(dart, ticker, year, reprt):
    """fnlttSinglAcntAll(연결) → {key: {"amt": 당기, "add": 누적}}"""
    try:
        df = dart.finstate_all(ticker, year, reprt_code=reprt, fs_div="CFS")
    except Exception as e:
        log(f"    (finstate_all {year}/{reprt} 실패: {type(e).__name__})")
        return None
    if df is None or getattr(df, "empty", True):
        return None
    out = {}
    for _, r in df.iterrows():
        aid = str(r.get("account_id", "")).strip()
        anm = str(r.get("account_nm", "")).replace(" ", "")
        sj = str(r.get("sj_div", ""))
        amt = g._num(r.get("thstrm_amount"))
        add = g._num(r.get("thstrm_add_amount"))
        for key in ACC_IDS:
            if key in out:
                continue
            # 손익 항목은 IS/CIS, 재무상태 항목은 BS, 현금흐름은 CF에서만
            if key in ("rev", "op", "np", "np_owner") and sj not in ("IS", "CIS"):
                continue
            if key in ("assets", "liab", "equity", "equity_owner") and sj != "BS":
                continue
            if key == "cfo" and sj != "CF":
                continue
            if aid in ACC_IDS[key] or anm in ACC_NAMES[key]:
                if amt is not None:
                    out[key] = {"amt": amt, "add": add}
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
            "equity": eq, "liab": li, "cfo": _cum(d, "cfo"),
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

    quarterly = []
    rev_q = quarters("rev", fy_row["rev"] if fy_row else None)
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

    mcap_won = (stock.get("mcap") or 0) * 1e12
    shares = stock.get("shares") or 0
    per_ttm = round(mcap_won / ttm_np, 1) if (ttm_np and ttm_np > 0 and mcap_won) else None
    eps_ttm = int(ttm_np / shares) if (ttm_np and shares) else None

    valuation = {
        "price": stock.get("price"), "mcap": stock.get("mcap"), "shares": shares,
        "per_ttm": per_ttm, "eps_ttm": eps_ttm,
        "ttm_window": f"{py}Q2~{cur}Q1" if ttm_np else None,
        "ttm_np_owner": ttm_np,
    }
    if krx_row is not None:
        for src, dst in (("PER", "per_krx"), ("PBR", "pbr_krx"), ("EPS", "eps_krx"),
                         ("BPS", "bps_krx"), ("DIV", "div_krx"), ("DPS", "dps_krx")):
            try:
                v = float(krx_row.get(src))
                valuation[dst] = v if v > 0 else None
            except Exception:
                valuation[dst] = None

    return {
        "asOf": datetime.date.today().isoformat(),
        "fs_basis": "연결(CFS) · DART 공시 확정치 · 지배주주 기준 순이익",
        "annual": annual,
        "quarterly": quarterly,
        "valuation": valuation,
    }


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
    lines.append(f"  PER(TTM) {v.get('per_ttm')} | PER(KRX결산) {v.get('per_krx')} | "
                 f"PBR {v.get('pbr_krx')} | 배당 {v.get('div_krx')}% | EPS(TTM) {v.get('eps_ttm')}")
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
  "valuation_comment": {"ko": "밸류에이션 해설 4~6문장. 제공된 PER(TTM/결산)·PBR 수치를 과거 밴드·업종 맥락에서 서술. '비싸다/싸다' 단정·권유 금지, 사실 비교만", "en": "..."},
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
3. earnings 섹션은 제공된 분기 추이(전 분기·전년 동기 비교)를 구체적으로 해석하세요. valuation_comment 는 per_ttm(최근 4개 분기 기준)과 per_krx(직전 결산 기준)가 왜 다른지도 자연스럽게 짚어주세요(실적 급변 시).
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


def valid_v2(rep):
    try:
        need = ("title", "lead", "keypoints", "business", "earnings", "industry",
                "outlook", "valuation_comment", "bull", "bear", "risks",
                "checkpoints", "verdict")
        if any(k not in rep for k in need):
            return False
        for k in ("business", "earnings", "industry", "outlook"):
            if len(rep[k]["ko"]) < 150 or len(rep[k]["en"]) < 150:
                return False
        return (len(rep["bull"]) >= 3 and len(rep["bear"]) >= 3
                and len(rep["risks"]) >= 3 and len(rep["checkpoints"]) >= 3
                and len(rep["verdict"]["body"]["ko"]) > 80)
    except Exception:
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
                model=MODEL, max_tokens=60000,
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
            if not valid_v2(rep):
                fail += 1
                log(f"  · ⚠️ {tk} 스키마 불완전 — 건너뜀")
                continue
            srcs = g.collect_sources(result.result.message)
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
    log(f"\n✅ v2 회수 완료 · 성공 {ok}/실패 {fail} → data/reports_v2/ ({len(have)}개)")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")

    if mode == "quant":
        data, targets = pick_targets()
        collect_all_quant(targets, data)
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
