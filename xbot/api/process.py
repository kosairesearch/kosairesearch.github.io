"""멘션 1건 처리 파이프라인 (webhook.js가 백그라운드로 호출).

종목 매칭 → (캐시 없으면) Claude+웹서치로 설명 생성 → pykrx 실시간 지표 →
답글 조립 → X에 게시 → 처리완료 마킹. 지표는 매번 새로 채우고
서술 설명만 Redis에 캐시한다({{METRICS}} 자리에 지표 블록을 끼워 넣는 구조).
"""
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import requests

REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL", "").rstrip("/")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN", "")
BOT_HANDLE = os.getenv("X_BOT_HANDLE", "kosai_x")
CACHE_TTL_DAYS = int(os.getenv("CACHE_TTL_DAYS", "90"))
MODEL = os.getenv("XBOT_MODEL", "claude-sonnet-4-6")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def log(*a):
    print("[process]", *a, flush=True)


# ---------------- Redis (Upstash REST) ----------------

def rcmd(*args):
    """Upstash REST로 Redis 명령 실행. 실패해도 봇이 죽지 않게 None."""
    if not REDIS_URL:
        return None
    try:
        r = requests.post(
            REDIS_URL, json=[str(a) for a in args],
            headers={"Authorization": f"Bearer {REDIS_TOKEN}"}, timeout=10,
        )
        return r.json().get("result")
    except Exception as e:
        log("redis 오류:", e)
        return None


# ---------------- 종목 매칭 ----------------

_SUFFIX = re.compile(
    r"\b(co|ltd|inc|corp|corporation|company|holdings|co\.,?\s*ltd)\b\.?", re.I)


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower().strip()
    s = _SUFFIX.sub("", s)
    return re.sub(r"[\s\.,·&\-'\"()]+", "", s)


def load_name_map():
    with open(DATA_DIR / "name_map.json", encoding="utf-8") as f:
        return json.load(f)


def match_stock(query, nm):
    """멘션에서 추출한 질의어 → 종목. 정확일치 > 별칭 > 접두 > 부분일치."""
    q = norm(query)
    if not q:
        return None
    if re.fullmatch(r"\d{6}", query.strip()):          # 6자리 코드 직접 입력
        return nm["stocks"].get(query.strip())
    alias = nm.get("aliases", {}).get(q)
    if alias and alias in nm["stocks"]:
        return nm["stocks"][alias]
    exact, prefix, partial = [], [], []
    for code, st in nm["stocks"].items():
        names = [norm(st.get("ko", "")), norm(st.get("en", ""))]
        if q in names:
            exact.append(st)
        elif any(n.startswith(q) for n in names if n):
            prefix.append(st)
        elif any(q in n for n in names if n and len(q) >= 2):
            partial.append(st)
    for bucket in (exact, prefix, partial):
        if bucket:  # 동률이면 이름이 짧은(=질의어와 더 가까운) 쪽
            return sorted(bucket, key=lambda s: len(s.get("ko", "")))[0]
    return None


def extract_query(text):
    """멘션 텍스트에서 @핸들·URL·기호를 걷어내고 종목 질의어만 남긴다."""
    t = re.sub(r"@\w+", " ", text)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"[#$]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def is_korean(text):
    return bool(re.search(r"[가-힣]", text))


# ---------------- 실시간 지표 (pykrx, 실패 시 kosai.kr 폴백) ----------------

def fx_usdkrw():
    cached = rcmd("GET", "fx:usdkrw")
    if cached:
        return float(cached)
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=USD&to=KRW",
                         timeout=10).json()
        rate = float(r["rates"]["KRW"])
        rcmd("SET", "fx:usdkrw", rate, "EX", 86400)   # 환율은 1일 캐시
        return rate
    except Exception as e:
        log("환율 조회 실패:", e)
        return None


def metrics_pykrx(code):
    from pykrx import stock as krx
    day = krx.get_nearest_business_day_in_a_week()
    out = {}
    cap = krx.get_market_cap_by_date(day, day, code)
    if len(cap):
        out["price"] = int(cap["종가"].iloc[-1])
        out["mcap"] = int(cap["시가총액"].iloc[-1])
    f = krx.get_market_fundamental(day, day, code)
    if len(f):
        row = f.iloc[-1]
        for k, col in (("per", "PER"), ("pbr", "PBR"), ("div", "DIV"),
                       ("eps", "EPS"), ("bps", "BPS")):
            v = float(row[col])
            if v:
                out[k] = v
    return out


def metrics_kosai(code):
    """pykrx 불가 시 폴백 — kosai.kr가 매일 갱신하는 공개 데이터."""
    out = {}
    try:
        js = requests.get("https://kosai.kr/data/stocks.js", timeout=15).text
        obj = json.loads(re.search(r"=\s*(\{.*)", js, re.S).group(1).strip().rstrip(";"))
        for s in obj.get("stocks", []):
            if s.get("ticker") == code:
                if s.get("price") and s.get("shares"):
                    out["price"] = int(s["price"])
                    out["mcap"] = int(s["price"]) * int(s["shares"])
                break
    except Exception as e:
        log("kosai 폴백 실패:", e)
    return out


def get_metrics(code):
    try:
        m = metrics_pykrx(code)
        if m.get("price"):
            return m
    except Exception as e:
        log("pykrx 실패 → 폴백:", e)
    return metrics_kosai(code)


def _won(n):
    if n >= 1e12:
        return f"{n/1e12:.1f}조"
    if n >= 1e8:
        return f"{n/1e8:,.0f}억"
    return f"{n:,.0f}"


def metrics_block(m, lang):
    if not m.get("price"):
        return ""
    if lang == "ko":
        parts = [f"주가 {m['price']:,}원"]
        if m.get("mcap"):
            parts.append(f"시총 {_won(m['mcap'])}원")
        if m.get("per"):
            parts.append(f"PER {m['per']:.1f}")
        if m.get("pbr"):
            parts.append(f"PBR {m['pbr']:.2f}")
        if m.get("div"):
            parts.append(f"배당수익률 {m['div']:.2f}%")
        return "📊 " + " · ".join(parts)
    fx = fx_usdkrw()
    p_usd = f" (${m['price']/fx:,.1f})" if fx else ""
    parts = [f"Price ₩{m['price']:,}{p_usd}"]
    if m.get("mcap"):
        c_usd = f" (${m['mcap']/fx/1e9:,.1f}B)" if fx else ""
        parts.append(f"Mcap ₩{m['mcap']/1e12:.1f}T{c_usd}")
    if m.get("per"):
        parts.append(f"P/E {m['per']:.1f}")
    if m.get("pbr"):
        parts.append(f"P/B {m['pbr']:.2f}")
    if m.get("div"):
        parts.append(f"Div yield {m['div']:.2f}%")
    return "📊 " + " · ".join(parts)


# ---------------- DART 최근 공시 ----------------

def recent_filings(dart_code):
    key = os.getenv("DART_API_KEY", "")
    if not (key and dart_code):
        return []
    try:
        end = datetime.now().strftime("%Y%m%d")
        bgn = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
        r = requests.get(
            "https://opendart.fss.or.kr/api/list.json",
            params={"crtfc_key": key, "corp_code": dart_code,
                    "bgn_de": bgn, "end_de": end, "page_count": 8},
            timeout=15).json()
        return [f"{x['rcept_dt']} {x['report_nm'].strip()}"
                for x in r.get("list", [])]
    except Exception as e:
        log("DART 조회 실패:", e)
        return []


# ---------------- 설명 생성 (Claude + web search) ----------------

SYS_KO = (
    "당신은 한국 상장주식을 처음 접하는 사람에게 종목을 설명하는 리서치 라이터다. "
    "주어진 종목에 대해 X(트위터) 장문 답글 본문을 한국어로 작성하라. 웹 검색으로 "
    "최신 사실을 확인하라.\n"
    "구조(섹션 제목 없이 자연스러운 문단으로): ① 회사가 무엇을 하는 회사인지 정의 문단으로 "
    "바로 시작 — 첫 280자 안에 핵심 정의가 들어가야 한다 ② 사업 구조와 돈 버는 방식 "
    "③ 핵심 사건이나 최근 상황 ④ 그 다음 줄에 정확히 {{METRICS}} 라고만 쓴 줄 하나 "
    "⑤ 참고할 리스크.\n"
    "규칙: 총 1200~1700자. 종목 규모가 작아 쓸 내용이 적으면 억지로 늘리지 말고 짧게. "
    "매수/매도/목표가 등 투자 권유 절대 금지, 사실만 서술. 비유 대신 어려운 용어는 "
    "괄호 안 한 줄 설명으로 풀 것. 사건성 내용은 반드시 '올해 1월', '작년 3분기'처럼 "
    "시점을 명시. 이모지·해시태그 금지. 제공된 최근 공시 목록과 검색 결과에 없는 "
    "수치는 지어내지 말 것."
)

SYS_EN = (
    "You are a research writer explaining a Korean listed stock to someone new to it. "
    "Write the body of a long-form X reply in English. Use web search to verify "
    "current facts.\n"
    "Structure (natural paragraphs, no section headers): ① open directly with a "
    "definition of what the company does — the core definition must appear within the "
    "first 280 characters ② how the business makes money ③ key recent events or "
    "situation ④ then one line containing exactly {{METRICS}} ⑤ risks to be aware of.\n"
    "Rules: 900-1400 characters total. If the company is small and there is little to "
    "say, keep it short — do not pad. Absolutely no buy/sell/target-price language; "
    "facts only. Explain jargon with a short parenthetical, not analogies. Anchor any "
    "event in time ('this January', 'Q3 last year'). No emojis, no hashtags. Use "
    "standard English financial terms (P/E, P/B — never PER/PBR). Do not invent "
    "figures not present in the provided filings or search results."
)


def generate_desc(st, code, lang, filings):
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    name = st["ko"] if lang == "ko" else (st.get("en") or st["ko"])
    fil = "\n".join(filings) or "(없음)"
    usr = (f"종목: {st['ko']} / {st.get('en','')} (코드 {code}, {st.get('market','')})\n"
           f"최근 DART 공시:\n{fil}\n\n답글 본문을 작성하라." if lang == "ko" else
           f"Stock: {st.get('en') or st['ko']} / {st['ko']} (code {code}, "
           f"{st.get('market','')})\nRecent DART filings:\n{fil}\n\nWrite the reply body.")
    msg = client.messages.create(
        model=MODEL, max_tokens=3000,
        system=SYS_KO if lang == "ko" else SYS_EN,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": usr}],
    )
    text = "".join(b.text for b in msg.content
                   if getattr(b, "type", "") == "text").strip()
    # 인용 각주 등 검색 부산물 제거
    return re.sub(r"\s*\[\d+\]", "", text)


def get_desc(st, code, lang, filings):
    key = f"desc:{code}_{lang}"
    cached = rcmd("GET", key)
    if cached:
        log("캐시 사용:", key)
        return cached
    desc = generate_desc(st, code, lang, filings)
    if desc:
        rcmd("SET", key, desc, "EX", CACHE_TTL_DAYS * 86400)
    return desc


# ---------------- 답글 조립 + 게시 ----------------

DISCLAIMER = {"ko": "공시·공개 데이터 기반 정보이며 투자 권유가 아닙니다.",
              "en": "Based on public filings and market data. Not investment advice."}


def compose(st, code, lang, desc, mblock):
    name = st["ko"] if lang == "ko" else (st.get("en") or st["ko"])
    header = f"{name} ({code})"
    if "{{METRICS}}" in desc:
        body = desc.replace("{{METRICS}}", mblock or "")
    else:
        body = desc + ("\n\n" + mblock if mblock else "")
    text = f"{header}\n\n{body}\n\n{DISCLAIMER[lang]}"
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def post_reply(text, in_reply_to):
    from requests_oauthlib import OAuth1
    auth = OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                  os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])
    r = requests.post(
        "https://api.x.com/2/tweets",
        json={"text": text, "reply": {"in_reply_to_tweet_id": in_reply_to}},
        auth=auth, timeout=20)
    log("X 게시 응답:", r.status_code, r.text[:300])
    return r.ok


# ---------------- 메인 ----------------

def run(payload):
    tweet_id = payload["tweet_id"]
    # 중복 방지 — 같은 멘션은 한 번만 (SET NX)
    if rcmd("SET", f"done:{tweet_id}", "1", "NX", "EX", 604800) is None and REDIS_URL:
        log("이미 처리한 멘션:", tweet_id)
        return {"skipped": "duplicate"}

    text = payload.get("text", "")
    lang = "ko" if is_korean(text) else "en"
    query = extract_query(text)
    nm = load_name_map()
    st = match_stock(query, nm)
    log(f"멘션 {tweet_id} · 질의 '{query}' · lang {lang} · "
        f"매칭 {st['ko'] + '(' + st['code'] + ')' if st else '실패'}")

    if not st:
        msg = (f"'{query}' 종목을 찾지 못했어요. 정식 종목명이나 6자리 코드로 "
               f"다시 멘션해 주세요." if lang == "ko" else
               f"Couldn't find a Korean listed stock matching '{query}'. "
               f"Try the official name or 6-digit code.")
        post_reply(msg, tweet_id)
        return {"matched": False}

    code = st["code"]
    filings = recent_filings(st.get("dart"))
    desc = get_desc(st, code, lang, filings)
    if not desc:
        log("설명 생성 실패 — 중단")
        return {"error": "generation failed"}
    mblock = metrics_block(get_metrics(code), lang)
    reply = compose(st, code, lang, desc, mblock)
    ok = post_reply(reply, tweet_id)
    return {"matched": True, "posted": ok, "code": code, "lang": lang}


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.headers.get("x-internal-secret") != os.getenv("INTERNAL_SECRET"):
            self.send_response(401); self.end_headers(); return
        try:
            body = json.loads(self.rfile.read(
                int(self.headers.get("content-length", 0)) or 0) or b"{}")
            result = run(body)
            out = json.dumps(result).encode()
            self.send_response(200)
        except Exception as e:
            log("처리 실패:", repr(e))
            out = json.dumps({"error": str(e)}).encode()
            self.send_response(500)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(out)
