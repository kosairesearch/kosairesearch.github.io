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


def _stats(stock, valmap):
    p = stock.get("price")
    e = valmap.get(stock["ticker"], {})
    eps, bps, dps = e.get("eps"), e.get("bps"), e.get("dps")
    per = round(p / eps, 1) if (eps and eps > 0 and p) else None
    pbr = round(p / bps, 2) if (bps and bps > 0 and p) else None
    div = round(dps / p * 100, 2) if (dps and p) else None
    return per, pbr, div


def _thesis(tk):
    try:
        rp = json.loads((ROOT / "data" / "reports_v2" / f"{tk}.json").read_text(encoding="utf-8"))
        return t2(rp.get("title")), t2(rp.get("lead"))
    except Exception:
        return "", ""


def build_candidates(st):
    """오늘 올릴 만한 후보 추림 — ① 당일 상승(긍정적 이슈 프록시) ② 저평가 셋업."""
    live = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")["stocks"]
    valmap = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"]
    have = set(p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json"))
    by_mcap = sorted(live, key=lambda x: x.get("mcap", 0) or 0, reverse=True)
    rankpool = [s for s in by_mcap if s["ticker"] in have][:POOL]   # 인지도 컷
    recent = set(st.get("recent", [])[-NO_REPEAT:])
    pool = [s for s in rankpool if s["ticker"] not in recent]

    # ① 모멘텀: 당일 +1.5% 이상 & 거래대금 충분(유동성 있는 실제 이슈)
    movers = sorted(
        [s for s in pool if (s.get("change") or 0) >= 1.5 and (s.get("trading_value") or 0) >= 1e10],
        key=lambda s: s.get("change") or 0, reverse=True)[:10]

    # ② 밸류: 흑자(eps>0) & 합리적 저PER·저PBR(부실·이상치 제외)
    def cheap(s):
        per, pbr, _ = _stats(s, valmap)
        return per is not None and pbr is not None and 2 <= per <= 12 and 0.2 <= pbr <= 1.5
    value = sorted([s for s in pool if cheap(s)],
                   key=lambda s: (_stats(s, valmap)[0] or 99))[:10]

    seen, cands = set(), []
    for tag, lst in (("mover", movers), ("value", value)):
        for s in lst:
            if s["ticker"] in seen:
                continue
            seen.add(s["ticker"])
            per, pbr, div = _stats(s, valmap)
            title, lead = _thesis(s["ticker"])
            cands.append({"stock": s, "tag": tag, "per": per, "pbr": pbr, "div": div,
                          "change": s.get("change"), "title": title, "lead": lead})
    fallback = pool[0] if pool else (rankpool[0] if rankpool else None)
    return cands, fallback


def choose_with_judgment(cands):
    """후보 중 '오늘 올릴 1개'를 Claude 편집 판단으로 선정."""
    if len(cands) == 1:
        return cands[0]["stock"]
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    rows = []
    for c in cands:
        s = c["stock"]
        rows.append(
            f'{s["ticker"]} {s.get("name")} | {s.get("sector")} | 당일 {c["change"]}% '
            f'| 시총 {round(s.get("mcap",0),1)}조 | PER {c["per"]} | PBR {c["pbr"]} '
            f'| 배당 {c["div"]}% | [{c["tag"]}] | 논지: {(c["lead"] or c["title"])[:160]}')
    sys_p = (
        "You are the editor of KOSAI, an English research brand on Korean stocks. "
        "Pick exactly ONE stock from the list that is the most worth a single research post TODAY. "
        "Prefer (a) a clear positive development today (a strong up-move usually reflects real news/catalyst), "
        "or (b) a genuinely interesting valuation or quality setup with a solid business. "
        "Avoid names whose only story is decline, distress, or a one-off spike with no substance. "
        "KOSAI is neutral: do NOT pick because 'it will go up' — pick what is most informative and discussion-worthy. "
        "Return ONLY JSON: {\"ticker\":\"<6 digits>\",\"why\":\"<short reason in Korean>\"}."
    )
    usr = "후보:\n" + "\n".join(rows)
    try:
        msg = client.messages.create(model=MODEL, max_tokens=300, system=sys_p,
                                     messages=[{"role": "user", "content": usr}])
        txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", txt, re.S)
        data = json.loads(m.group(0)) if m else {}
        tk = (data.get("ticker") or "").strip()
        log("편집 선정:", tk, "|", data.get("why", ""))
        hit = next((c["stock"] for c in cands if c["stock"]["ticker"] == tk), None)
        return hit or cands[0]["stock"]
    except Exception as e:
        log("선정 판단 실패, 첫 후보 사용:", e)
        return cands[0]["stock"]


def pick_ticker(st):
    """오늘 올릴 종목 1개 — 모멘텀/밸류 후보군에서 Claude가 편집 선정(시총순 아님)."""
    forced = os.getenv("X_TICKER", "").strip()
    if forced:
        live = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")["stocks"]
        return next((s for s in live if s["ticker"] == forced), None)
    cands, fallback = build_candidates(st)
    if not cands:
        log("후보 없음 — 폴백(시총 상위 미사용분) 사용.")
        return fallback
    log(f"후보 {len(cands)}종목(모멘텀+밸류) 중 선정 진행.")
    return choose_with_judgment(cands)


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


STYLE_FILE = ROOT / "data" / "x_style_examples.json"


def build_style_block(n=5):
    """data/x_style_examples.json(반응 좋은 실제 X 글)에서 몇 개를 뽑아 '문체 참고' 블록을 만든다.
    내용·종목·추천은 절대 인용 금지 — 톤·리듬·훅만 학습. 파일이 없으면 빈 문자열(기존 동작 유지)."""
    try:
        data = json.loads(STYLE_FILE.read_text(encoding="utf-8"))
        ex = [e.get("text", "").strip() for e in data.get("examples", []) if e.get("text")]
    except Exception:
        return ""
    if not ex:
        return ""
    import random
    pick = random.sample(ex, min(n, len(ex)))
    log(f"🎨 스타일 예시 {len(ex)}개 중 {len(pick)}개 반영")
    joined = "\n\n".join(f"- {t}" for t in pick)
    return (
        " STYLE REFERENCE (voice + format, NOT content): below are real, high-engagement posts "
        "from finance X. Closely emulate their human VOICE, rhythm, sentence shape, how they open, "
        "and how they BREAK LINES and structure the post — write like these were written. Do NOT "
        "borrow their tickers, facts, opinions, or any buy/sell stance; those are theirs, not "
        "ours, and the COMPLIANCE and content rules above always win.\n"
        + joined
    )


def draft(brief, snap):
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    sys_p = (
        "You write a single daily X (Twitter) post for KOSAI, an English-language research "
        "brand covering Korean stocks (KOSPI/KOSDAQ). Audience: global finance Twitter. "
        "You are given ONE company's live snapshot and our research notes. Write one strong, "
        "self-contained post about that company. "
        "ABOVE ALL, WRITE IN THE EXACT STYLE of the STYLE REFERENCE posts at the end: copy their "
        "sentence length, their heavy line breaks, their punchy casual human voice. "
        "SENTENCES: keep them SHORT. If a sentence runs long, split it into two. No long "
        "analytical run-on sentences. "
        "PARAGRAPHS: SHORT. Mostly one short sentence per line, with frequent line breaks, like the "
        "references — not dense blocks. "
        "You MAY cover the full story (what happened, the driver, the bull case, the bear case, "
        "valuation) — but each as its own short punchy line, never as long paragraphs. Cut filler. "
        "STYLE: concrete numbers (revenue, operating profit, growth, multiple) woven into "
        "sentences, not bullet dumps; confident but human voice; vary sentence length. "
        "NO em-dashes, NO '~', NO 'worth noting', NO 'in a world where', NO dramatic colon "
        "reveals, NO emojis, NO hashtags, NO links in the body. "
        "COMPLIANCE (hard rules, KOSAI is not a registered advisor): neutral only. "
        "NO buy/sell calls, NO price targets, NO 'will go up/down', NO 'undervalued, should rerate'. "
        "Present what is happening and the bull vs bear setup with equal weight; let the reader "
        "judge. Numbers must come only from the snapshot/notes; never invent figures. "
        "TICKER: the FIRST time you mention the company name, put its 6-digit ticker (from the "
        "snapshot) in parentheses right after it, e.g. 'ISC (095340)'. Only on that first mention. "
        "SOUND HUMAN, NOT AI (important): write like a sharp human markets person, not a language "
        "model. Avoid AI tells completely: no 'moreover', 'furthermore', 'notably', 'it's worth "
        "noting', 'in conclusion', 'in summary', 'overall', 'that said' as a crutch, and no tidy "
        "wrap-up sentence. Skip robotic perfectly-balanced hedging and formulaic transitions. Use "
        "contractions, plain words, and a real point of view on what's interesting (still neutral "
        "on direction). Vary rhythm hard: mix a punchy short line with a longer one; a sentence "
        "fragment is fine. Open with something a person would actually say, not a template."
    )
    style = build_style_block()
    if style:
        sys_p += style
    usr = (
        f"{brief}\n\n"
        "Write the post. Return ONLY JSON: {\"en\": \"<the X post>\", "
        "\"ko\": \"<Korean gloss so the operator can verify accuracy and tone>\"}."
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=2000, system=sys_p,
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
            log("텔레그램 응답 오류:", r.status_code, r.text[:400])
        else:
            try:
                res = r.json().get("result", {})
                ch = res.get("chat", {})
                log(f"텔레그램 OK · msg_id {res.get('message_id')} · chat_id {ch.get('id')} "
                    f"· {ch.get('type')} · {ch.get('title') or ch.get('username') or ch.get('first_name')}")
            except Exception:
                pass
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


_ABBRS = ["Co.", "Ltd.", "Inc.", "Corp.", "Pharm.", "Ph.", "Dr.", "Mr.", "Ms.", "Mrs.",
          "vs.", "U.S.", "e.g.", "i.e.", "No.", "St.", "Sr.", "Jr.", "etc.", "approx."]


def format_paragraphs(text):
    """문단을 코드로 강제 정리 — 문장 하나당 한 줄, 문장 사이 빈 줄.
    모델 출력이 들쭉날쭉해도 항상 짧게 띄운 형태로 통일한다. 약어(Co.·Ltd.·U.S. 등)와
    소수점(34.6)·통화(1,547.5bn)에서는 끊지 않는다."""
    t = re.sub(r"\s*\n\s*", " ", (text or "")).strip()
    for a in _ABBRS:                       # 약어 마침표 임시 보호
        t = t.replace(a, a.replace(".", "\x00"))
    # 문장부호 뒤 + 공백 + 다음이 대문자/숫자/$/따옴표일 때만 분리(소수점·약어 회피)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9$\"'‘“])", t)
    parts = [p.replace("\x00", ".").strip() for p in parts if p.strip()]
    return "\n\n".join(parts)


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
    log("=== 생성된 EN 글 ===\n" + d["en"] + "\n=== 끝 ===")

    tk = stock["ticker"]
    # 상단 헤더 없이 영어 글만 단독 발송. 문단은 코드로 강제 정리(문장당 한 줄 + 빈 줄).
    msg_en = format_paragraphs(d["en"])
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
