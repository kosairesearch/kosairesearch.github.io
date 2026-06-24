#!/usr/bin/env python3
"""하루 1종목 — X(트위터) 게시용 글을 텔레그램으로 푸시.

매일 정해진 시간에 종목 1개를 골라(겹치지 않게 로테이션) 우리 리포트·시세를
근거로 Claude가 X용 영어 글 + 한국어 검수본을 작성, 텔레그램으로 보낸다.
사람은 검토 후 X에 복붙만 하면 됨. (자동 게시 X — 계정정지·스팸 방지)

원칙: 중립. 매수/매도·목표주가·단정적 주가 방향성 금지. 사실+분석만.

필요 시크릿: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY
환경변수(옵션): NEWS_MODEL(기본 claude-sonnet-4-6), X_TICKER(수동지정),
              X_FORCE(1이면 같은 날 재전송 허용·테스트용)
"""
import os
import re
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "_x_daily.json"
KST = timezone(timedelta(hours=9))

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("NEWS_MODEL", "claude-sonnet-4-6")
NO_REPEAT = 45   # 최근 N종목은 다시 안 뽑음(로테이션)
POOL = 180       # 인지도 높은 상위 시총 N개 중에서만 선정


def log(*a):
    print(*a, flush=True)


def loadjs(path, var):
    t = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(re.escape(var) + r"\s*=\s*(\{.*)", t, re.S)
    return json.loads(m.group(1).rstrip().rstrip(";"))


def load_state():
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_date": "", "recent": []}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def pick_ticker(st):
    """오늘 올릴 종목 1개 선정 — 리포트 있는 상위 시총에서 미사용분 우선."""
    forced = os.getenv("X_TICKER", "").strip()
    live = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")["stocks"]
    have_report = set(p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json"))
    by_mcap = sorted(live, key=lambda x: x.get("mcap", 0) or 0, reverse=True)
    pool = [s for s in by_mcap if s["ticker"] in have_report][:POOL]
    if forced:
        hit = next((s for s in live if s["ticker"] == forced), None)
        return hit
    recent = set(st.get("recent", [])[-NO_REPEAT:])
    for s in pool:                       # 시총 큰 순 + 최근 미사용
        if s["ticker"] not in recent:
            return s
    return pool[0] if pool else None      # 전부 썼으면 맨 위부터 재시작


def t2(node, lang="en"):
    if isinstance(node, dict):
        return (node.get(lang) or node.get("ko") or "").strip()
    return (node or "").strip() if isinstance(node, str) else ""


def build_brief(stock):
    """Claude에 넘길 종목 브리프(영어) 구성 — 리포트 본문 + 시세 스냅샷."""
    tk = stock["ticker"]
    rp = json.loads((ROOT / "data" / "reports_v2" / f"{tk}.json").read_text(encoding="utf-8"))
    val = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"].get(tk, {})
    p = stock.get("price")
    eps, bps, dps = val.get("eps"), val.get("bps"), val.get("dps")
    per = round(p / eps, 1) if (eps and eps > 0 and p) else None
    pbr = round(p / bps, 2) if (bps and p) else None
    div = round(dps / p * 100, 2) if (dps and p) else None
    snap = {
        "name_en": stock.get("name_en") or stock.get("name"),
        "name_ko": stock.get("name"),
        "ticker": tk,
        "sector": stock.get("sector"),
        "price_krw": p,
        "mcap_tn_krw": round(stock.get("mcap", 0), 1) if stock.get("mcap") else None,
        "PER": per, "PBR": pbr, "div_yield_pct": div,
    }
    lines = ["[LIVE SNAPSHOT]", json.dumps(snap, ensure_ascii=False)]
    lines += ["", "[OUR REPORT — facts to draw from]"]
    lines.append("Title: " + t2(rp.get("title")))
    lines.append("Lead: " + t2(rp.get("lead")))
    kps = rp.get("keypoints") or []
    if kps:
        lines.append("Key points:")
        for k in kps[:5]:
            lines.append(" - " + t2(k))
    for sec in ("earnings", "outlook", "valuation_comment"):
        v = t2(rp.get(sec))
        if v:
            lines.append(f"{sec}: {v}")
    for side in ("bull", "bear"):
        arr = rp.get(side) or []
        if arr:
            lines.append(f"{side}:")
            for it in arr[:3]:
                lines.append(f" - {t2(it.get('title'))}: {t2(it.get('body'))[:240]}")
    return "\n".join(lines), snap


def draft(brief, snap):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    sys_p = (
        "You write a single daily X (Twitter) post for KOSAI, an English-language research "
        "brand covering Korean stocks (KOSPI/KOSDAQ). Audience: global finance Twitter. "
        "You are given ONE company's live snapshot and our research notes. Write one strong, "
        "self-contained post about that company. "
        "LENGTH & SHAPE: a developed mini-narrative, roughly 3-5 short paragraphs. Build the "
        "story: (1) a hook with what just happened and the key numbers, (2) the main driver, "
        "(3) capital return or another supporting point if relevant, (4) the bear side / what "
        "cuts the other way, (5) one line of valuation and earnings-trend context. Not a clipped "
        "list, not a long essay. Every paragraph earns its place. "
        "STYLE: concrete numbers (revenue, operating profit, growth, multiple) woven into "
        "sentences, not bullet dumps; confident but human voice; vary sentence length. "
        "NO em-dashes, NO '~', NO 'worth noting', NO 'in a world where', NO dramatic colon "
        "reveals, NO emojis, NO hashtags, NO links in the body. "
        "COMPLIANCE (hard rules, KOSAI is not a registered advisor): neutral only. "
        "NO buy/sell calls, NO price targets, NO 'will go up/down', NO 'undervalued, should rerate'. "
        "Present what is happening and the bull vs bear setup with equal weight; let the reader "
        "judge. Numbers must come only from the snapshot/notes; never invent figures."
    )
    usr = (
        f"{brief}\n\n"
        "Write the post. Return ONLY JSON: {\"en\": \"<the X post>\", "
        "\"ko\": \"<Korean gloss so the operator can verify accuracy and tone>\"}."
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=2500, system=sys_p,
        messages=[{"role": "user", "content": usr}],
    )
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    if getattr(msg, "stop_reason", "") == "max_tokens":
        log("⚠ 응답이 max_tokens로 잘림 — 상한을 더 올려야 할 수 있음.")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        log("draft 파싱 실패. 응답 앞부분:", txt[:200].replace("\n", " "))
        return None
    try:
        from json_repair import repair_json
        return json.loads(repair_json(m.group(0)))
    except Exception as e:
        log("draft JSON 복구 실패:", e, "| 응답 앞부분:", txt[:200].replace("\n", " "))
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _send_one(text):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT, "text": text, "disable_web_page_preview": "true"},
            timeout=20,
        )
        if not r.ok:
            log("텔레그램 응답 오류:", r.status_code, r.text[:300])
        return r.ok
    except Exception as e:
        log("텔레그램 예외:", e)
        return False


def _chunk(text, limit=4000):
    """텔레그램 4096자 한도 대비 — 줄 경계 우선으로 분할."""
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > limit and cur:
            parts.append(cur)
            cur = ""
        # 한 줄 자체가 한도를 넘으면 강제 분할
        while len(line) > limit:
            parts.append(line[:limit])
            line = line[limit:]
        cur = line if not cur else cur + "\n" + line
    if cur:
        parts.append(cur)
    return parts


def tg_send(text):
    ok = True
    for part in _chunk(text):
        ok = _send_one(part) and ok
    return ok


def main():
    miss = [n for n, v in (("TELEGRAM_BOT_TOKEN", TG_TOKEN),
                           ("TELEGRAM_CHAT_ID", TG_CHAT),
                           ("ANTHROPIC_API_KEY", ANTHROPIC_KEY)) if not v]
    if miss:
        log("❌ 시크릿 미설정:", ", ".join(miss), "— 레포 Settings>Secrets 확인 필요.")
        sys.exit(1)
    today = datetime.now(KST).strftime("%Y%m%d")
    force = os.getenv("X_FORCE", "").lower() in ("1", "true", "yes")
    st = load_state()
    if st.get("last_date") == today and not force and not os.getenv("X_TICKER"):
        log(f"⏭ 오늘({today}) 이미 전송함 — 스킵(재전송하려면 force 체크).")  # 백업 크론 중복 방지
        return

    stock = pick_ticker(st)
    if not stock:
        log("❌ 후보 종목 없음 — 종료.")
        sys.exit(1)
    log(f"선정: {stock['ticker']} {stock.get('name')}")
    brief, snap = build_brief(stock)
    d = draft(brief, snap)
    if not d or not d.get("en"):
        log("❌ 초안 생성 실패(Claude 응답 파싱 불가) — 종료.")
        sys.exit(1)

    tk = stock["ticker"]
    head = (f"📅 오늘의 X 종목글 — {snap['name_ko']} ({tk}) · {snap.get('sector','')}\n"
            f"{snap.get('price_krw')}원 · 시총 {snap.get('mcap_tn_krw')}조 "
            f"· PER {snap.get('PER')} · PBR {snap.get('PBR')}\n"
            f"링크: https://kosai.kr/stock.html?ticker={tk}")
    # 메시지 2건 분리 — ① X 복붙용 영어글(깔끔하게 단독), ② 한국어 검수본
    msg_en = f"{head}\n\n— EN (아래만 X에 복붙) —\n{d['en']}"
    msg_ko = f"— KR (검수용) —\n{d.get('ko','')}"
    if tg_send(msg_en) and tg_send(msg_ko):
        st["last_date"] = today
        st.setdefault("recent", []).append(tk)
        st["recent"] = st["recent"][-200:]
        save_state(st)
        log(f"✅ 전송 완료 — {tk} {snap['name_ko']}")
    else:
        log("❌ 텔레그램 전송 실패 — 위 '텔레그램 응답 오류' 로그 확인.")
        sys.exit(1)


if __name__ == "__main__":
    main()
