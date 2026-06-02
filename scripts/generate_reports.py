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


def build_prompt(stock, as_of):
    name = stock["name"]
    sector = stock.get("sector", "")
    market = stock.get("market", "")
    price = stock.get("price")
    change = stock.get("change")
    mcap_eok = stock.get("mcap")  # 조 단위로 저장됨 (예: 2065.95 = 2,065.95조? -> 실제는 조)
    trading_value = stock.get("trading_value")

    mcap_txt = f"{mcap_eok:,.1f}조원" if mcap_eok else "-"
    return f"""다음 종목에 대한 기업 리서치 리포트를 작성하세요.

[기준 데이터 — {as_of} KST]
- 종목명: {name} ({stock['ticker']})
- 시장/업종: {market} · {sector}
- 현재가: {price:,}원 (전일대비 {change:+.2f}%)
- 시가총액: {mcap_txt}
- 거래대금: {fmt_won(trading_value)}

[작성 지침]
1. 먼저 web_search 도구로 이 기업의 최신 실적, 사업 현황, 업종 동향, 최근 뉴스를 조사하세요(한국어로 검색). 최소 2~4회 검색합니다.
2. 검색으로 **확인된 사실과 수치만** 사용하세요. 확인되지 않은 구체적 숫자(영업이익, 점유율 등)는 추정하지 말고 정성적으로 서술하세요. 데이터를 지어내지 마세요.
3. 시점에 민감한 수치는 "최근 보도에 따르면", "2025년 기준" 처럼 출처/시점을 함께 밝히세요.
4. 균형 있게: 강세 요인과 약세 요인을 모두 제시하세요.
5. 한국어(ko)와 영어(en) 두 버전을 모두 작성하세요. 영어 버전에 한국어가 섞이면 안 됩니다.
6. 문체는 전문 애널리스트 리포트 톤. 투자 권유·매수/매도 추천 표현은 쓰지 마세요(정보 제공용).

[출력 형식]
조사를 마친 뒤, 최종 결과를 아래 스키마의 **JSON 하나**로만 출력하세요.
반드시 `===JSON_START===` 와 `===JSON_END===` 마커 사이에 넣고, 마커 뒤에는 아무것도 쓰지 마세요.

스키마:
{SCHEMA_DESC}

===JSON_START===
(여기에 JSON)
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


def generate_one(client, stock, as_of):
    prompt = build_prompt(stock, as_of)
    with client.messages.stream(
        model=MODEL,
        max_tokens=20000,
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

    reports = {}
    total_searches = 0
    # Tier 1 = 분당 입력 30,000 토큰 제한. 종목 사이 간격을 두어 한도를 피한다.
    GAP = int(os.getenv("REPORT_GAP_SEC", "60"))
    MAX_ATTEMPTS = 4
    for i, st in enumerate(stocks, 1):
        tk, nm = st["ticker"], st["name"]
        log(f"\n### [{i}/{len(stocks)}] {nm} ({tk})")
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                t0 = time.time()
                rep, searches = generate_one(client, st, as_of)
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
                wait = 70
                log(f"- ⏳ 시도 {attempt} 속도제한(429) — {wait}초 대기 후 재시도")
                if attempt == MAX_ATTEMPTS:
                    log(f"- ❌ {nm} 리포트 생성 실패(속도제한) — 건너뜀")
                else:
                    time.sleep(wait)
            except Exception as e:
                log(f"- ⚠️ 시도 {attempt} 실패: {type(e).__name__}: {e}")
                if attempt == MAX_ATTEMPTS:
                    log(f"- ❌ {nm} 리포트 생성 실패 — 건너뜀")
                else:
                    time.sleep(10)
        # 다음 종목 전 분당 입력 토큰 한도 회복을 위해 간격
        if i < len(stocks):
            time.sleep(GAP)

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

    log(f"\n✅ 총 {len(reports)}개 리포트 생성 · 웹검색 {total_searches}회 · → data/reports.js")


if __name__ == "__main__":
    main()
