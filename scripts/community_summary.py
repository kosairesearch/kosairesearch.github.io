#!/usr/bin/env python3
"""종목명/종목코드 → 커뮤니티 댓글용 '중립 요약'(평문, 400자 이내)을 출력.

사용법:
    python scripts/community_summary.py 삼성전자
    python scripts/community_summary.py 005930

동작 원칙
· 이미 생성된 KOSAI 리포트(data/reports_v2/{코드}.json)가 있으면 '그 내용만' 근거로 쓴다.
  리포트가 없을 때만 DART·pykrx를 새로 호출해 최소 정보를 수집한다(비용·호출 절약).
· 출력 형식(코드가 100% 조립 — 모델은 각 항목 '내용'만 JSON으로 낸다):
    종목명(코드)
    <무슨 회사인지 2줄>
    <사업·수익구조 2줄>
    <최근 실적 2줄>
    지표(YYYY-MM-DD 기준): 주가 … · 시총 … · PER … · PBR … · 배당 …
    리스크: <1개>
· 매수/매도/목표주가/투자의견에 해당하는 표현은 절대 넣지 않는다(코드로 재검열).
· 주가·시가총액처럼 매일 바뀌는 값에는 '조회 날짜'를 함께 표기한다.
· 전체 400자 이내, 마크다운 없이 평문.

필요 환경변수: ANTHROPIC_API_KEY (요약 문장 압축용)
              DART_API_KEY / (선택)KRX_ID·KRX_PW — 리포트가 없는 종목을 신규 조회할 때만.
"""
import os
import re
import sys
import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("SUMMARY_MODEL", "claude-sonnet-4-6")
MAXLEN = 400

# 매수/매도·투자의견에 해당하는 금지 표현(코드 재검열). 하나라도 있으면 해당 문장을 덜어낸다.
BANNED = ["매수", "매도", "목표주가", "투자의견", "비중확대", "비중축소", "비중 확대", "비중 축소",
          "추천", "사라", "사야", "팔아", "팔라", "담아", "손절", "익절", "추격", "저평가", "고평가",
          "저점 매수", "매집", "적정주가", "상승 여력", "하락 여력", "오를", "내릴"]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def loadjs(path, var):
    t = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(re.escape(var) + r"\s*=\s*(\{.*)", t, re.S)
    return json.loads(m.group(1).rstrip().rstrip(";"))


def t2(node, lang="ko"):
    if isinstance(node, dict):
        return (node.get(lang) or node.get("ko") or "").strip()
    return (node or "").strip() if isinstance(node, str) else ""


def fmt_date(yyyymmdd):
    s = str(yyyymmdd or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else datetime.date.today().isoformat()


def resolve(arg, stocks):
    """인자(6자리 코드 또는 종목명)를 stocks.js 종목 1개로 해석."""
    a = arg.strip()
    if re.fullmatch(r"\d{6}", a):
        return next((s for s in stocks if s["ticker"] == a), None)
    exact = [s for s in stocks if (s.get("name") or "") == a]
    if exact:
        return exact[0]
    part = [s for s in stocks if a and a in (s.get("name") or "")]
    part.sort(key=lambda s: len(s.get("name") or ""))   # 가장 짧은(정확한) 이름 우선
    return part[0] if part else None


def metrics(stock, valmap, data_date):
    """지표 스냅샷 + 조회 날짜. mcap은 stocks.js 기준 '조' 단위."""
    p = stock.get("price")
    v = valmap.get(stock["ticker"], {})
    eps, bps, dps = v.get("eps"), v.get("bps"), v.get("dps")
    per = round(p / eps, 1) if (eps and eps > 0 and p) else None
    pbr = round(p / bps, 2) if (bps and bps > 0 and p) else None
    div = round(dps / p * 100, 2) if (dps and p) else None
    return {"price": p, "mcap_jo": round(stock.get("mcap", 0), 2) if stock.get("mcap") else None,
            "per": per, "pbr": pbr, "div": div, "date": fmt_date(data_date)}


def metrics_line(m):
    bits = []
    if m.get("price"):
        bits.append(f"주가 {m['price']:,}원")
    if m.get("mcap_jo"):
        bits.append(f"시총 {m['mcap_jo']}조")
    if m.get("per") is not None:
        bits.append(f"PER {m['per']}")
    if m.get("pbr") is not None:
        bits.append(f"PBR {m['pbr']}")
    if m.get("div") is not None:
        bits.append(f"배당 {m['div']}%")
    return f"지표({m['date']} 기준): " + " · ".join(bits)


# ── 리포트 기반(기본 경로) ─────────────────────────────────────────────
def brief_from_report(stock):
    tk = stock["ticker"]
    rp = json.loads((ROOT / "data" / "reports_v2" / f"{tk}.json").read_text(encoding="utf-8"))
    bear = rp.get("bear") or []
    risk = ""
    if bear:
        risk = f"{t2(bear[0].get('title'))}: {t2(bear[0].get('body'))}"
    return {
        "company": t2(rp.get("business")) or t2(rp.get("lead")),
        "biz": t2(rp.get("business")),
        "earnings": t2(rp.get("earnings")),
        "risk": risk or t2(rp.get("valuation_comment")),
    }


# ── 신규 조회(리포트 없을 때만) ────────────────────────────────────────
def latest_trading_date():
    from pykrx import stock as krx
    for back in range(10):
        d = datetime.date.today() - datetime.timedelta(days=back)
        if d.weekday() >= 5:
            continue
        ds = d.strftime("%Y%m%d")
        try:
            df = krx.get_market_ohlcv_by_date(ds, ds, "005930")
            if df is not None and not df.empty:
                return ds
        except Exception:
            continue
    return datetime.date.today().strftime("%Y%m%d")


def fresh_fetch(stock):
    """리포트가 없는 종목만: pykrx(시세·지표)·DART(개요·실적)를 새로 호출.
    실패해도 확보된 만큼만 반환(있는 값만 표기)."""
    tk = stock["ticker"]
    m = {"price": stock.get("price"), "mcap_jo": round(stock.get("mcap", 0), 2) if stock.get("mcap") else None,
         "per": None, "pbr": None, "div": None, "date": fmt_date(None)}
    biz_line = f"{stock.get('sector') or ''} 업종의 상장사."
    earn_line = ""
    try:
        from pykrx import stock as krx
        date = latest_trading_date()
        m["date"] = fmt_date(date)
        try:
            f = krx.get_market_fundamental_by_ticker(date).loc[tk]
            m["per"] = float(f.get("PER")) or None
            m["pbr"] = float(f.get("PBR")) or None
            m["div"] = float(f.get("DIV")) or None
        except Exception as e:
            log("pykrx fundamental 실패:", e)
        try:
            cap = krx.get_market_cap_by_ticker(date).loc[tk]
            price = int(cap.get("종가")) if cap.get("종가") else stock.get("price")
            m["price"] = price or m["price"]
            m["mcap_jo"] = round(float(cap.get("시가총액", 0)) / 1e12, 2) or m["mcap_jo"]
        except Exception as e:
            log("pykrx cap 실패:", e)
    except Exception as e:
        log("pykrx 로드 실패:", e)

    try:
        import generate_reports as g
        dart = g.get_dart()
        if dart:
            try:
                info = dart.company(tk)
                est = (info or {}).get("est_dt") or ""
                if est:
                    biz_line = f"{stock.get('name')}는 {est[:4]}년 설립된 {stock.get('sector') or ''} 업종 상장사다."
            except Exception as e:
                log("DART company 실패:", e)
        # 최근 연간·분기 재무를 텍스트로(연도 폴백 내장). 앞머리 안내([...]) 줄은 제거.
        try:
            fin = g.get_dart_financials(tk) or ""
            earn_line = " ".join(l.strip(" -") for l in fin.splitlines()
                                 if l.strip() and not l.lstrip().startswith("["))
        except Exception as e:
            log("DART 재무 실패:", e)
    except Exception as e:
        log("generate_reports 로드/ DART 실패:", e)

    return {
        "company": f"{stock.get('name')}는 {stock.get('sector') or ''} 업종에 속한 국내 상장사다.",
        "biz": biz_line,
        "earnings": earn_line or "정기보고서 데이터가 제한적이라 최근 실적 수치는 확인이 필요하다.",
        "risk": "신규/데이터 부족 종목으로, 공시 이력이 짧아 실적 추세 판단에 한계가 있다.",
    }, m


# ── 요약 문장 압축(모델은 내용만, 레이아웃은 코드) ──────────────────────
def compose(name, ticker, sector, src):
    """src(리포트/신규조회에서 뽑은 원문 4항목)를 짧은 평문으로 압축."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    sys_p = (
        "너는 KOSAI의 애널리스트다. 아래 '자료'만 근거로, 커뮤니티 댓글용 짧은 요약의 '내용'을 만든다. "
        "한국어 평문. 자료에 없는 사실·수치는 지어내지 마라.\n"
        "[출력 — JSON만] {\n"
        '  "company": "<이 회사가 무엇을 하는 곳인지. 2문장, 총 55자 이내>",\n'
        '  "biz": "<핵심 사업·수익구조(무엇으로 돈을 버는가). 2문장, 총 60자 이내>",\n'
        '  "earnings": "<최근 실적 흐름(매출·이익 방향). 2문장, 총 65자 이내>",\n'
        '  "risk": "<가장 중요한 리스크 1가지. 1문장, 55자 이내>"\n'
        "}\n"
        "[문체] 애널리스트 문어체 '~다' 종결. 짧고 명확하게. 이모지·해시태그·마크다운(**, # 등)·물결(~)·전각대시(—) 금지.\n"
        "[절대 금지 — 중립] 매수/매도/추천/목표주가/투자의견, '오른다·내린다·사라·팔아라·저평가·고평가·상승여력' "
        "같은 방향성·권유 표현을 어떤 형태로도 쓰지 마라. 사실만 중립적으로 기술한다. 지표(주가·PER 등)는 코드가 따로 붙이니 넣지 마라."
    )
    usr = (
        f"종목: {name}({ticker}) · 업종 {sector}\n\n[자료]\n"
        f"- 회사/사업: {src.get('company','')}\n{src.get('biz','')}\n"
        f"- 최근 실적: {src.get('earnings','')}\n"
        f"- 리스크: {src.get('risk','')}\n\n"
        "위 자료로 JSON을 채워라."
    )
    msg = client.messages.create(model=MODEL, max_tokens=700, system=sys_p,
                                 messages=[{"role": "user", "content": usr}])
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        from json_repair import repair_json
        return json.loads(repair_json(m.group(0)))
    except Exception:
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


# ── 재검열·정리 ───────────────────────────────────────────────────────
def strip_md(s):
    s = re.sub(r"[*_#`>]", "", s or "")
    s = s.replace("—", ", ").replace("–", ", ").replace("~", "")
    return re.sub(r"\s+", " ", s).strip()


def _sentences(t):
    t = re.sub(r"(\d)\.(\d)", "\\1\x01\\2", t or "")
    parts = re.split(r"(?<=[.!?。])\s+", t)
    return [p.replace("\x01", ".").strip() for p in parts if p.strip()]


def neutralize(s):
    """금지 표현이 든 문장은 통째로 제거(중립성 코드 강제)."""
    out = [sent for sent in _sentences(s) if not any(b in sent for b in BANNED)]
    return " ".join(out).strip()


def clip(s, n):
    """n자 이내로: 문장 경계 우선, 안 되면 잘라서 말줄임."""
    s = (s or "").strip()
    if len(s) <= n:
        return s
    acc = ""
    for sent in _sentences(s):
        if len(acc) + len(sent) + 1 > n:
            break
        acc = sent if not acc else acc + " " + sent
    if not acc:
        acc = s[:max(0, n - 1)].rstrip() + "…"
    return acc


def build_output(stock, comp, m):
    name, tk = stock.get("name"), stock["ticker"]
    company = clip(neutralize(strip_md(comp.get("company", ""))), 55)
    biz = clip(neutralize(strip_md(comp.get("biz", ""))), 62)
    earn = clip(neutralize(strip_md(comp.get("earnings", ""))), 66)
    risk = clip(neutralize(strip_md(comp.get("risk", ""))), 58)
    mline = metrics_line(m)

    lines = [f"{name}({tk})", company, biz, earn, mline]
    if risk:
        lines.append(f"리스크: {risk}")
    out = "\n".join(x for x in lines if x)

    # 전체 400자 강제 — 초과 시 뒤쪽(리스크→실적) 순으로 줄인다.
    if len(out) > MAXLEN:
        over = len(out) - MAXLEN
        risk2 = clip(risk, max(0, len(risk) - over))
        lines = [f"{name}({tk})", company, biz, earn, mline]
        if risk2:
            lines.append(f"리스크: {risk2}")
        out = "\n".join(x for x in lines if x)
    if len(out) > MAXLEN:
        out = out[:MAXLEN].rstrip()
    return out


def main():
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        log("사용법: python scripts/community_summary.py <종목명 또는 6자리코드>")
        sys.exit(2)
    if not ANTHROPIC_KEY:
        log("❌ ANTHROPIC_API_KEY 미설정 — 요약 문장 압축에 필요합니다.")
        sys.exit(1)

    arg = sys.argv[1]
    data = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")
    stocks = data["stocks"]
    valmap = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"]
    data_date = data.get("dataDate", "")

    stock = resolve(arg, stocks)
    if not stock:
        log(f"❌ '{arg}'에 해당하는 종목을 찾지 못했습니다.")
        sys.exit(1)

    tk = stock["ticker"]
    has_report = (ROOT / "data" / "reports_v2" / f"{tk}.json").exists()
    if has_report:
        log(f"· 리포트 사용: {tk} {stock.get('name')} (신규 조회 없음)")
        src = brief_from_report(stock)
        m = metrics(stock, valmap, data_date)
    else:
        log(f"· 리포트 없음 → DART·pykrx 신규 조회: {tk} {stock.get('name')}")
        src, m = fresh_fetch(stock)

    comp = compose(stock.get("name"), tk, stock.get("sector") or "", src)
    if not comp:
        log("❌ 요약 생성 실패(모델 응답 파싱 불가).")
        sys.exit(1)

    out = build_output(stock, comp, m)
    log(f"· 글자 수: {len(out)}자")
    print(out)   # 최종 결과는 stdout으로만


if __name__ == "__main__":
    main()
