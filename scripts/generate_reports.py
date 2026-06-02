#!/usr/bin/env python3
"""
KOS ai — AI 기업 리서치 리포트 생성 스크립트

data/stocks.js 의 시가총액 상위 N개 종목에 대해 Claude(claude-opus-4-8)로
한국어/영어 동시 리서치 리포트를 생성하고 data/reports.js 를 만듭니다.

- 웹 검색(web_search) 도구로 최신 사실에 근거(grounding)하여 작성합니다.
- 구체적 수치는 검색으로 확인된 것만 사용하고, 확인 불가 시 정성적으로 서술합니다.
- GitHub Actions 에서 수동/주간 실행됩니다 (ANTHROPIC_API_KEY 시크릿 필요).
"""

import os
import re
import sys
import json
import time
import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import anthropic

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
REPORTS_JS = ROOT / "data" / "reports.js"

MODEL = os.getenv("REPORT_MODEL", "claude-opus-4-8")
TOP_N = int(os.getenv("REPORT_TOP_N", "5"))

STEP_SUMMARY = os.getenv("GITHUB_STEP_SUMMARY")


def log(msg):
    print(msg, flush=True)
    if STEP_SUMMARY:
        with open(STEP_SUMMARY, "a", encoding="utf-8") as f:
            f.write(msg + "\n")


# ── stocks.js 파싱 ────────────────────────────────────────────────────
def load_stocks():
    raw = STOCKS_JS.read_text(encoding="utf-8")
    obj = raw[raw.find("{"): raw.rfind("}") + 1]
    return json.loads(obj)


def fmt_won(v):
    """원 단위 정수를 사람이 읽는 한글 단위로."""
    if v is None:
        return "-"
    v = float(v)
    if v >= 1e12:
        return f"{v/1e12:.1f}조원"
    if v >= 1e8:
        return f"{v/1e8:.0f}억원"
    return f"{v:,.0f}원"


# ── DART 공시 재무 (리포트 근거용 1차 데이터) ─────────────────────────
DART_API_KEY = os.getenv("DART_API_KEY")
_dart = None
REPRT_NAME = {"11011": "사업보고서(연간)", "11013": "1분기", "11012": "반기", "11014": "3분기"}


def get_dart():
    global _dart
    if _dart is None:
        if not DART_API_KEY:
            _dart = False
        else:
            try:
                import OpenDartReader
                _dart = OpenDartReader(DART_API_KEY)
            except Exception as e:
                log(f"- (DART 초기화 실패) {e}")
                _dart = False
    return _dart or None


def _num(x):
    try:
        return int(str(x).replace(",", "").strip())
    except Exception:
        return None


def _won_unit(v):
    if v is None:
        return "-"
    a = abs(v)
    if a >= 1e12:
        return f"{v/1e12:.1f}조원"
    if a >= 1e8:
        return f"{v/1e8:,.0f}억원"
    return f"{v:,}원"


def _safe_finstate(dart, ticker, year, reprt):
    try:
        return dart.finstate(ticker, year, reprt)
    except Exception:
        return None


def _extract_fin(df):
    """finstate DF에서 매출액/영업이익/당기순이익(연결 CFS 우선)의 당기·전기 금액 추출."""
    if df is None or getattr(df, "empty", True):
        return None
    out = {}
    for _, r in df.iterrows():
        nm = str(r.get("account_nm", "")).replace(" ", "")
        fs = str(r.get("fs_div", ""))
        cur = _num(r.get("thstrm_amount"))
        prv = _num(r.get("frmtrm_amount"))
        key = None
        if ("매출액" in nm or nm == "수익(매출액)" or nm == "영업수익") and "원가" not in nm and "총이익" not in nm:
            key = "매출액"
        elif nm.startswith("영업이익"):
            key = "영업이익"
        elif "당기순이익" in nm:
            key = "당기순이익"
        if key and cur is not None:
            prev = out.get(key)
            if prev is None or (fs == "CFS" and prev.get("fs") != "CFS"):
                out[key] = {"cur": cur, "prv": prv, "fs": fs}
    return out or None


def get_dart_financials(ticker):
    """DART 요약재무제표에서 최근 연간·분기 매출/영업이익/순이익을 텍스트로 반환.
    실패 시 빈 문자열(→ 웹검색만 사용)."""
    dart = get_dart()
    if not dart:
        return ""
    cur = datetime.date.today().year

    annual, ann_year = None, None
    for yr in (cur - 1, cur - 2):
        d = _extract_fin(_safe_finstate(dart, ticker, yr, "11011"))
        if d:
            annual, ann_year = d, yr
            break

    quarter, q_label = None, None
    for reprt in ("11014", "11012", "11013"):
        d = _extract_fin(_safe_finstate(dart, ticker, cur, reprt))
        if d:
            quarter, q_label = d, f"{cur}년 {REPRT_NAME[reprt]}(누적)"
            break

    if not annual and not quarter:
        return ""

    def fmt(d, label):
        if not d:
            return None
        parts = []
        for k in ("매출액", "영업이익", "당기순이익"):
            if k in d:
                v = d[k]
                s = _won_unit(v["cur"])
                if v.get("prv"):
                    try:
                        yoy = (v["cur"] - v["prv"]) / abs(v["prv"]) * 100
                        s += f" (전기대비 {yoy:+.1f}%)"
                    except Exception:
                        pass
                parts.append(f"{k} {s}")
        return f"- {label}: " + ", ".join(parts) if parts else None

    lines = ["[DART 공시 확정 재무 — 아래 숫자는 공시 원문(연결 기준)이므로 '사실'로 사용하세요. "
             "기사/추정값과 충돌하면 이 값을 우선합니다.]"]
    for blk in (fmt(annual, f"{ann_year}년 연간"), fmt(quarter, q_label)):
        if blk:
            lines.append(blk)
    return "\n".join(lines) if len(lines) > 1 else ""


# ── 프롬프트 ──────────────────────────────────────────────────────────
SCHEMA_DESC = """{
  "lead":      {"ko": "한 문장 핵심 메시지", "en": "one-sentence thesis"},
  "desc":      {"ko": "리포트 개요 1~2문장", "en": "..."},
  "keypoints": [ {"ko": "핵심 포인트", "en": "..."}, ... 3개 ],
  "business":  {"ko": "사업구조 문단(3~5문장)", "en": "..."},
  "recent":    {"ko": "최근 실적/주가 흐름 문단", "en": "..."},
  "outlook":   {"ko": "향후 전망 문단", "en": "..."},
  "bull":      [ {"title": {"ko":"","en":""}, "body": {"ko":"","en":""}}, ... 2~3개 ],
  "bear":      [ {"title": {"ko":"","en":""}, "body": {"ko":"","en":""}}, ... 2~3개 ],
  "risks":     [ {"cat": {"ko":"거시 리스크","en":"Macro"}, "body": {"ko":"","en":""}}, ... 2~3개 ],
  "verdict":   {"stance": {"ko":"긍정적/중립/신중","en":"Constructive/Neutral/Cautious"},
                "body": {"ko":"종합의견 문단", "en":"..."}},
  "sources":   [ "https://...", ... ]
}"""

SYSTEM = (
    "당신은 한국 주식시장(코스피·코스닥)을 다루는 시니어 리서치 애널리스트입니다. "
    "공시·뉴스·시장 데이터를 근거로 균형 잡힌 기업 리서치 리포트를 작성합니다. "
    "당신의 글은 한국어/영어 양국어로 동시에 제공됩니다."
)


def build_prompt(stock, as_of, dart_block=""):
    name = stock["name"]
    sector = stock.get("sector", "")
    market = stock.get("market", "")
    price = stock.get("price")
    change = stock.get("change")
    mcap_eok = stock.get("mcap")  # 조 단위로 저장됨 (예: 2065.95 = 2,065.95조? -> 실제는 조)
    trading_value = stock.get("trading_value")

    mcap_txt = f"{mcap_eok:,.1f}조원" if mcap_eok else "-"
    dart_section = ("\n" + dart_block + "\n") if dart_block else ""
    return f"""다음 종목에 대한 기업 리서치 리포트를 작성하세요.

[기준 데이터 — {as_of} KST]
- 종목명: {name} ({stock['ticker']})
- 시장/업종: {market} · {sector}
- 현재가: {price:,}원 (전일대비 {change:+.2f}%)
- 시가총액: {mcap_txt}
- 거래대금: {fmt_won(trading_value)}
{dart_section}
[작성 지침]
1. 먼저 web_search 도구로 이 기업의 최신 실적, 사업 현황, 업종 동향, 최근 뉴스를 조사하세요(한국어로 검색). 최소 2~4회 검색합니다.
2. 재무 수치는 위 **[DART 공시 확정 재무]** 값을 최우선으로 사용하세요(공시 원문). 그 외 수치는 검색으로 **확인된 것만** 쓰고, 확인 안 된 구체적 숫자는 추정하지 말고 정성적으로 서술하세요. 데이터를 지어내지 마세요.
3. 시점에 민감한 수치는 "최근 보도에 따르면", "2025년 기준" 처럼 출처/시점을 함께 밝히세요.
4. 균형 있게: 강세 요인과 약세 요인을 모두 제시하세요.
5. 한국어(ko)와 영어(en) 두 버전을 모두 작성하세요. 영어 버전에 한국어가 섞이면 안 됩니다.
6. 문체는 전문 애널리스트 리포트 톤. 투자 권유·매수/매도 추천 표현은 쓰지 마세요(정보 제공용).

[출력 형식 — 매우 중요]
- 검색이 끝나면 **머리말·설명·요약 없이** 곧바로 `===JSON_START===` 부터 출력하세요. 마커 앞에 어떤 문장도 쓰지 마세요(예: "아래는...", "조사를 완료했습니다" 금지).
- 최종 결과는 아래 스키마의 **JSON 하나**이며, `===JSON_START===` 와 `===JSON_END===` 사이에 넣습니다. 마커 뒤에는 아무것도 쓰지 마세요.
- 각 문단(business/recent/outlook)은 **3~4문장 이내**로 간결하게. ko/en 합쳐 분량이 과하지 않게 작성하세요.
- JSON은 **반드시 완결**되어야 합니다(중간에 끊기지 않도록 분량을 조절).

스키마:
{SCHEMA_DESC}

===JSON_START===
(여기에 JSON, 마커 앞뒤에 다른 텍스트 금지)
===JSON_END==="""


def extract_text(message):
    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(parts)


def parse_report(text):
    m = re.search(r"===JSON_START===(.*?)===JSON_END===", text, re.S)
    chunk = m.group(1) if m else text
    chunk = chunk.strip()
    # 혹시 코드펜스가 들어간 경우 제거
    chunk = re.sub(r"^```(?:json)?", "", chunk).strip()
    chunk = re.sub(r"```$", "", chunk).strip()
    # 첫 { 부터 마지막 } 까지
    start, end = chunk.find("{"), chunk.rfind("}")
    if start >= 0 and end > start:
        chunk = chunk[start:end + 1]
    return json.loads(chunk)


def generate_one(client, stock, as_of, dart_block=""):
    prompt = build_prompt(stock, as_of, dart_block)
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5,
                "user_location": {"type": "approximate", "country": "KR",
                                  "timezone": "Asia/Seoul"}}],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()

    searches = 0
    try:
        searches = message.usage.server_tool_use.web_search_requests
    except Exception:
        pass

    text = extract_text(message)
    try:
        report = parse_report(text)
    except Exception:
        # 디버깅용: 파싱 실패 시 응답 앞부분을 남긴다
        head = (text or "").strip()[:300].replace("\n", " ")
        log(f"  · 파싱 실패 응답(앞 300자): {head!r} · stop={message.stop_reason}")
        raise
    return report, searches


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log("❌ ANTHROPIC_API_KEY 가 설정되어 있지 않습니다. GitHub Secrets 에 추가하세요.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    data = load_stocks()
    stocks = sorted(data["stocks"], key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:TOP_N]

    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    as_of = now.strftime("%Y-%m-%d %H:%M")
    report_date = now.strftime("%Y-%m-%d")

    log(f"## 🤖 AI 리포트 생성 — {as_of} KST")
    log(f"- 모델: `{MODEL}` · 대상: 시총 상위 {TOP_N}개")

    # ── 이어하기: 기존 리포트를 불러온다. 최근(FRESH_DAYS일 이내) 리포트는
    #    재생성하지 않고 유지(같은 날 재실행=복구). 오래된 것은 갱신(주간 자동실행). ──
    reports = {}
    force = os.getenv("REPORT_FORCE", "") == "1"
    FRESH_DAYS = int(os.getenv("REPORT_FRESH_DAYS", "6"))
    fresh = set()
    if REPORTS_JS.exists():
        try:
            raw = REPORTS_JS.read_text(encoding="utf-8")
            prev = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            if "샘플" not in str(prev.get("model", "")):  # 샘플 파일은 무시
                reports = prev.get("reports", {}) or {}
                today = now.date()
                for tk, r in reports.items():
                    try:
                        d = datetime.date.fromisoformat(r.get("reportDate", ""))
                        if (today - d).days <= FRESH_DAYS:
                            fresh.add(tk)
                    except Exception:
                        pass
                log(f"- 기존 리포트 {len(reports)}개 로드 · 최근({FRESH_DAYS}일내) {len(fresh)}개 유지")
        except Exception as e:
            log(f"- (기존 리포트 로드 실패, 새로 생성) {e}")

    total_searches = 0
    aborted = False
    # Tier 1 = 분당 입력 30,000 토큰 제한. 종목 사이 간격을 두어 한도를 피한다.
    GAP = int(os.getenv("REPORT_GAP_SEC", "60"))
    PARSE_RETRY = 1   # 파싱/잘림 실패 시 재시도 횟수(비용 절약 위해 최소화)
    RL_WAITS = 3      # 속도제한(429) 대기-재시도 횟수
    last_gen = -1
    for i, st in enumerate(stocks, 1):
        tk, nm = st["ticker"], st["name"]
        if tk in fresh and not force:
            log(f"\n### [{i}/{len(stocks)}] {nm} ({tk}) — 최근 리포트 존재, 건너뜀")
            continue
        log(f"\n### [{i}/{len(stocks)}] {nm} ({tk})")

        if last_gen >= 0:  # 직전에 실제 생성을 했다면 한도 회복 간격
            time.sleep(GAP)

        dart_block = get_dart_financials(tk)
        log(f"- DART 재무: {'확보' if dart_block else '없음(웹검색만)'}")

        parse_tries, rl_waits = 0, 0
        while True:
            try:
                t0 = time.time()
                rep, searches = generate_one(client, st, as_of, dart_block)
                total_searches += searches
                rep.update({
                    "ticker": tk, "name": nm,
                    "name_en": st.get("name_en", nm),
                    "sector": st.get("sector", ""),
                    "market": st.get("market", ""),
                    "reportDate": report_date,
                    "dataDate": data.get("dataDate", ""),
                })
                reports[tk] = rep
                log(f"- ✅ 완료 ({time.time()-t0:.0f}s · 검색 {searches}회)")
                break
            except anthropic.RateLimitError:
                rl_waits += 1
                if rl_waits > RL_WAITS:
                    log(f"- ❌ {nm} 실패(속도제한 지속) — 건너뜀")
                    break
                log(f"- ⏳ 속도제한(429) — 70초 대기 후 재시도 ({rl_waits}/{RL_WAITS})")
                time.sleep(70)
            except anthropic.BadRequestError as e:
                if "credit balance" in str(e).lower():
                    log("- ⛔ 크레딧 잔액 부족 — 생성을 중단합니다. console.anthropic.com 에서 충전 후 다시 실행하세요.")
                    aborted = True
                    break
                log(f"- ⚠️ 요청 오류: {e}")
                break
            except Exception as e:
                parse_tries += 1
                log(f"- ⚠️ 시도 실패: {type(e).__name__}: {e}")
                if parse_tries > PARSE_RETRY:
                    log(f"- ❌ {nm} 리포트 생성 실패 — 건너뜀")
                    break
                time.sleep(10)
        last_gen = i
        if aborted:
            break

    if not reports:
        log("❌ 생성된 리포트가 없습니다.")
        sys.exit(1)

    payload = {
        "lastUpdated": as_of,
        "model": MODEL,
        "reports": reports,
    }
    REPORTS_JS.parent.mkdir(parents=True, exist_ok=True)
    js = ("// KOS ai — AI 리서치 리포트 (자동 생성). 직접 수정하지 마세요.\n"
          "window.KOS_REPORTS = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")
    REPORTS_JS.write_text(js, encoding="utf-8")

    log(f"\n✅ 현재 리포트 {len(reports)}개 보유 · 이번 실행 웹검색 {total_searches}회 · → data/reports.js")
    if aborted:
        log("⛔ 크레딧 부족으로 일부 종목이 생성되지 않았습니다. 충전 후 워크플로를 다시 실행하면 남은 종목만 이어서 생성합니다.")
        sys.exit(2)


if __name__ == "__main__":
    main()
