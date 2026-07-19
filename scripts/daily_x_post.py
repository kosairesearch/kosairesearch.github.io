#!/usr/bin/env python3
"""하루 1종목 — X(트위터) 게시용 '한국어' 글을 텔레그램으로 푸시.

장 마감 후 실행. 그날 '급등한 종목'(거래대금·시총으로 거른 진짜 급등주) 중 1개를
골라, 우리 리포트·시세를 근거로 Claude가 개인투자자가 흥미롭게 읽을 한국어 X 글을
작성해 텔레그램으로 보낸다. 사람은 검토 후 X에 복붙만 하면 됨(자동 게시 X — 정지·스팸 방지).

훅은 '오늘 몇 % 급등'이고, 본문은 '이 회사가 뭐 하는 곳인지'를 리포트로 풀어준다.
급등 촉매를 확실히 모르면 지어내지 않는다.

원칙: 중립. 매수/매도·목표주가·"오른다/추격" 금지. 사실+양면(강/약)만. 끝에 면책 1줄.

필요 시크릿: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY
환경변수(옵션): NEWS_MODEL(기본 claude-sonnet-4-6), X_TICKER(수동지정),
              X_FORCE(1이면 같은 날 재전송 허용·테스트용),
              X_SURGE_MIN(급등 기준 %, 기본 7), X_TV_MIN(거래대금 하한 원, 기본 5e9),
              X_MCAP_MIN(시총 하한 조, 기본 0.05)
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


SURGE_MIN = float(os.getenv("X_SURGE_MIN", "7"))     # 급등 기준(%)
TV_MIN = float(os.getenv("X_TV_MIN", "5e9"))          # 거래대금 하한(원) — 실제 관심의 증거
MCAP_MIN = float(os.getenv("X_MCAP_MIN", "0.05"))     # 시총 하한(조) — 순수 잡주 제외


def build_candidates(st):
    """그날 '급등한 종목' 후보 추림. 순수 상위 상승주엔 초소형 잡주가 많으므로
    거래대금(관심)·시총 하한으로 걸러 '진짜 급등주'만 남긴다. 리포트 있는 종목만."""
    live = loadjs("data/stocks.js", "window.KOS_LIVE_DATA")["stocks"]
    valmap = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"]
    have = set(p.stem for p in (ROOT / "data" / "reports_v2").glob("*.json"))
    recent = set(st.get("recent", [])[-NO_REPEAT:])
    base = [s for s in live if s["ticker"] in have and s["ticker"] not in recent
            and (s.get("trading_value") or 0) >= TV_MIN
            and (s.get("mcap") or 0) >= MCAP_MIN]

    # 급등 문턱을 점진적으로 완화(장 전체가 약한 날에도 항상 후보 확보)
    movers = []
    for thr in (SURGE_MIN, 5, 3, 1.5, 0.5):
        movers = sorted([s for s in base if (s.get("change") or 0) >= thr],
                        key=lambda s: s.get("change") or 0, reverse=True)[:15]
        if movers:
            log(f"급등 기준 {thr}% · 후보 {len(movers)}종목")
            break

    cands = []
    for s in movers:
        per, pbr, div = _stats(s, valmap)
        title, lead = _thesis(s["ticker"])
        cands.append({"stock": s, "tag": "surge", "per": per, "pbr": pbr, "div": div,
                      "change": s.get("change"), "title": title, "lead": lead})
    # 최후 폴백: 그래도 없으면 거래대금 상위 상승주(리포트 보유) 1개
    fb = sorted([s for s in live if s["ticker"] in have and (s.get("change") or 0) > 0],
                key=lambda s: s.get("trading_value") or 0, reverse=True)
    fallback = fb[0] if fb else None
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
    """Claude에 넘길 종목 브리프(한국어) — 당일 급등 + 리포트 본문 + 시세 스냅샷."""
    tk = stock["ticker"]
    rp = json.loads((ROOT / "data" / "reports_v2" / f"{tk}.json").read_text(encoding="utf-8"))
    val = loadjs("data/valuation.js", "window.KOS_VALUATION")["stocks"].get(tk, {})
    p = stock.get("price")
    eps, bps, dps = val.get("eps"), val.get("bps"), val.get("dps")
    per = round(p / eps, 1) if (eps and eps > 0 and p) else None
    pbr = round(p / bps, 2) if (bps and p) else None
    div = round(dps / p * 100, 2) if (dps and p) else None
    tv = stock.get("trading_value") or 0
    snap = {
        "name_ko": stock.get("name"),
        "name_en": stock.get("name_en") or stock.get("name"),
        "ticker": tk,
        "sector": stock.get("sector"),
        "당일등락_pct": stock.get("change"),
        "현재가_원": p,
        "거래대금_억": round(tv / 1e8) if tv else None,
        "시총_조": round(stock.get("mcap", 0), 2) if stock.get("mcap") else None,
        "PER": per, "PBR": pbr, "배당수익률_pct": div,
    }
    L = lambda node: t2(node, "ko")   # 리포트는 한국어로 뽑는다
    lines = ["[오늘 시세 스냅샷]", json.dumps(snap, ensure_ascii=False)]
    lines += ["", "[우리 리포트 — 여기 있는 사실만 활용]"]
    lines.append("제목: " + L(rp.get("title")))
    lines.append("리드: " + L(rp.get("lead")))
    kps = rp.get("keypoints") or []
    if kps:
        lines.append("핵심 포인트:")
        for k in kps[:5]:
            lines.append(" - " + L(k))
    for sec, label in (("business", "사업"), ("earnings", "실적"),
                       ("outlook", "전망"), ("valuation_comment", "밸류에이션")):
        v = L(rp.get(sec))
        if v:
            lines.append(f"{label}: {v}")
    for side, label in (("bull", "강세논리"), ("bear", "약세논리")):
        arr = rp.get(side) or []
        if arr:
            lines.append(f"{label}:")
            for it in arr[:3]:
                lines.append(f" - {L(it.get('title'))}: {L(it.get('body'))[:240]}")
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
        "너는 KOSAI(한국 주식 리서치)의 X(트위터) 담당이다. 그날 '급등한 종목' 하나에 대해 "
        "개인투자자가 흥미롭게 끝까지 읽을 한국어 게시글 1개를 쓴다. 한국어로만 쓴다.\n"
        "훅(첫 줄): 스냅샷의 '당일등락_pct'를 활용해 오늘 급등했다는 사실로 시작한다. "
        "예: '오늘 +23% 급등한 OO(123456), 대체 뭐 하는 회사길래.' 궁금하게 만들어라.\n"
        "촉매 주의: 오늘 왜 올랐는지 '구체적 이유'를 우리가 모를 수 있다. 모르면 절대 지어내지 마라. "
        "'급등 배경은 확인 필요' 정도로 두고, 대신 '이 회사가 어떤 회사고 뭘로 돈 버는지'를 리포트로 풀어라. "
        "그게 이 글의 진짜 값이다.\n"
        "구성(각 항목은 짧은 문장, 문단 사이는 빈 줄): ① 훅 ② 무슨 회사·뭘로 돈 버나 "
        "③ 실적/밸류 숫자(스냅샷·노트의 매출·이익·PER·PBR 등) ④ 강세 포인트 vs 약세 포인트 "
        "⑤ 짚어볼 리스크. 종목이 작아 쓸 내용이 적으면 억지로 늘리지 말고 짧게.\n"
        "문체: 사람이 쓴 듯한 구어체. 문장 짧게, 줄바꿈 자주. 한 줄에 한 문장 위주. "
        "이모지·해시태그·링크·물결(~)·전각 대시 금지.\n"
        "AI 티 금지: '따라서, 또한, 한편, 결론적으로, 정리하면, 요약하면, 살펴보자' 같은 상투어와 "
        "깔끔한 마무리 문장 쓰지 마라. 사람이 실제로 할 말로 시작하라.\n"
        "컴플라이언스(엄수 — KOSAI는 등록 투자자문사가 아니다): 중립. 매수/매도 권유, 목표주가, "
        "'오른다/더 간다/지금 사라/저평가라 오를 것' 절대 금지. 급등했다고 추격을 부추기지 마라. "
        "무슨 일이 있었나 + 강세·약세를 같은 무게로 제시하고 판단은 독자에게 맡겨라. "
        "숫자는 스냅샷/노트에 있는 것만. 지어내지 마라.\n"
        "표기: 종목명을 처음 쓸 때 옆에 6자리 코드를 괄호로 붙인다(예: 'ISC (095340)'). 첫 언급에만. "
        "지표는 국내 관례대로 PER·PBR로 쓴다.\n"
        "면책 문장은 네가 쓰지 마라(코드가 맨 끝에 자동으로 붙인다)."
    )
    usr = (
        f"{brief}\n\n"
        "위 종목으로 X 게시글을 써라. JSON만 반환: {\"ko\": \"<한국어 X 게시글>\"}."
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


def normalize_terms(text):
    """영어 글은 해외 독자용 — 한국/일본식 약어를 영어권 표준으로 강제 치환.
    프롬프트가 어겨도 코드가 확실히 바꾼다(포맷 강제와 동일 원칙).
    · PER → P/E, PBR → P/B (대문자 토큰만; 영어 단어 'per'는 건드리지 않음)
    · BPS → book value per share (대문자 토큰만; 소수점/'50 bps'(basis points)는 소문자라 제외)"""
    t = text or ""
    t = re.sub(r"\bPER\b", "P/E", t)
    t = re.sub(r"\bPBR\b", "P/B", t)
    t = re.sub(r"\bBPS\b", "book value per share", t)
    return t


def _sentences(block):
    """한 블록을 문장 리스트로 분할(한/영 공용). 약어·소수점에서는 안 끊는다.
    한글 문장('~했다. 다음은')과 영어 문장 모두 '문장부호+공백'에서 끊는다."""
    t = re.sub(r"\s*\n\s*", " ", (block or "")).strip()
    for a in _ABBRS:                       # 영어 약어 마침표 임시 보호
        t = t.replace(a, a.replace(".", "\x00"))
    t = re.sub(r"(\d)\.(\d)", "\\1\x01\\2", t)   # 소수점(48.0 등) 보호
    parts = re.split(r"(?<=[.!?])\s+", t)         # 한글·영어 공통: 종결부호+공백
    return [p.replace("\x00", ".").replace("\x01", ".").strip()
            for p in parts if p.strip()]


def format_paragraphs(text):
    """문단을 코드로 강제 정리 — 짧은 문장 + 명확한 문단 구분(빈 줄).
    · 그룹(문단) 사이는 빈 줄로 구분, 그룹 안은 문장마다 한 줄(단일 줄바꿈).
    · 모델이 문단 구분을 했으면(빈 줄) 그 그룹을 존중하고, 안 했으면(한 덩어리)
      문장 3개씩 묶어 구분을 만든다 → 항상 '짧은 줄 묶음 + 빈 줄'."""
    blocks = [b for b in re.split(r"\n\s*\n", (text or "").strip()) if b.strip()]
    if len(blocks) <= 1:                    # 모델이 안 나눔 → 문장 3개씩 그룹핑
        s = _sentences(blocks[0]) if blocks else []
        groups = ["\n".join(s[i:i + 3]) for i in range(0, len(s), 3)]
    else:                                   # 모델 문단 그룹 존중, 그룹 안만 문장별 줄바꿈
        groups = ["\n".join(_sentences(b)) for b in blocks]
    return "\n\n".join(g for g in groups if g)


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
    log(f"선정: {stock['ticker']} {stock.get('name')} · 당일 {stock.get('change')}%")
    brief, snap = build_brief(stock)
    d = draft(brief, snap)
    if not d or not d.get("ko"):
        log("❌ 초안 생성 실패(Claude 응답 파싱 불가) — 종료.")
        sys.exit(1)
    log("=== 생성된 KO 글 ===\n" + d["ko"] + "\n=== 끝 ===")

    tk = stock["ticker"]
    # 한국어 글만 단독 발송. 문단은 코드로 강제 정리(문장당 한 줄 + 빈 줄), 면책은 코드가 자동 부착.
    msg = format_paragraphs(d["ko"]).rstrip()
    msg += "\n\n※ 공시·공개데이터 기반 정보이며 투자 권유가 아닙니다."
    if tg_send(msg):
        st["last_date"] = today
        st.setdefault("recent", []).append(tk)
        st["recent"] = st["recent"][-200:]
        save_state(st)
        log(f"✅ 전송 완료 — {tk} {snap['name_ko']} (당일 {stock.get('change')}%)")
    else:
        log("❌ 텔레그램 전송 실패 — 위 '텔레그램 응답 오류' 로그 확인.")
        sys.exit(1)


if __name__ == "__main__":
    main()
