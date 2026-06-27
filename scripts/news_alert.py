#!/usr/bin/env python3
"""뉴스 모니터 → X 게시용 초안 → 텔레그램 알림.

GitHub Actions에서 주기 실행(기본 10분). 한국 증시·반도체(HBM/DRAM) 이슈를
Google News RSS로 감지해, 게시할 만하면 Claude가 영어 글 + 한국어 검수본을
만들어 텔레그램으로 즉시 푸시한다. (X에 복붙만 하면 됨)

필요 시크릿(레포 Secrets):
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ANTHROPIC_API_KEY(기존)
환경변수(옵션): NEWS_MODEL(기본 claude-sonnet-4-6), NEWS_MAX_PER_RUN(기본 4)
"""
import os
import re
import sys
import json
import html
import hashlib
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "_news_seen.json"

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL = os.getenv("NEWS_MODEL", "claude-sonnet-4-6")
MAX_PER_RUN = int(os.getenv("NEWS_MAX_PER_RUN", "2"))
DAILY_MAX = int(os.getenv("NEWS_DAILY_MAX", "8"))       # 하루 알림 하드캡(폭주 방지)
RECENCY_MIN = int(os.getenv("NEWS_RECENCY_MIN", "120"))  # 최근 N분 내 기사만(크론 지연 대비 넓게)

# 감시 키워드(이 중 하나라도 제목에 있어야 후보) + Google News 검색식
QUERIES = [
    '("SK Hynix" OR "Samsung Electronics" OR HBM OR DRAM) chip Korea',
    'KOSPI OR KOSDAQ OR "Korean stocks" OR "Korea stocks" OR "Korean won"',
]
KEYWORDS = [
    "hynix", "samsung", "hbm", "dram", "nand", "micron", "memory chip",
    "kospi", "kosdaq", "korea", "korean", "tsmc", "nvidia", "won",
    "반도체", "하이닉스", "삼성전자", "메모리", "코스피", "코스닥", "증시",
]


def log(*a):
    print(*a, flush=True)


def load_state():
    """{'seen':[id...], 'day':'YYYYMMDD', 'sent_today':N}. 구버전(list)도 호환."""
    try:
        d = json.loads(SEEN.read_text(encoding="utf-8"))
        if isinstance(d, list):
            return {"seen": d, "day": "", "sent_today": 0}
        return {"seen": list(d.get("seen", [])), "day": d.get("day", ""),
                "sent_today": int(d.get("sent_today", 0))}
    except Exception:
        return {"seen": [], "day": "", "sent_today": 0}


def save_state(stt):
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    # seen은 '리스트(순서 보존)'로 저장 — 최근 N개만(set 정렬불가 버그 방지)
    stt["seen"] = stt["seen"][-1000:]
    if "titles" in stt:
        stt["titles"] = stt["titles"][-120:]   # 최근 제목 핵심단어(유사중복 비교용)
    SEEN.write_text(json.dumps(stt, ensure_ascii=False), encoding="utf-8")


def fetch_items():
    """Google News RSS에서 후보 기사 수집."""
    items = []
    for q in QUERIES:
        url = ("https://news.google.com/rss/search?q="
               + requests.utils.quote(q + " when:1d")
               + "&hl=en-US&gl=US&ceid=US:en")
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 KOSAI-news"})
            root = ET.fromstring(r.content)
        except Exception as e:
            log("RSS 실패:", e)
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = (it.findtext("pubDate") or "").strip()
            src_el = it.find("{http://news.google.com/}source") or it.find("source")
            source = (src_el.text.strip() if src_el is not None and src_el.text else "")
            if not title or not link:
                continue
            items.append({"title": html.unescape(title), "link": link,
                          "pub": pub, "source": source})
    return items


def recent(pub):
    try:
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt) <= timedelta(minutes=RECENCY_MIN)
    except Exception:
        return False


def relevant(title):
    t = title.lower()
    return any(k in t for k in KEYWORDS)


# 유사(같은 사건·다른 제목) 중복 차단용 — 너무 흔해 변별력 없는 단어 제외
_STOP = set((
    "the a an to of in on for and or as at is are was be by with after amid over from "
    "up down vs into out new news report reports says say said will would could may "
    "korea korean koreas kospi kosdaq stock stocks share shares market markets won "
    "this that it its their his her than more most amid set sets year years day days "
    "등 것 중 그 및 또 더 약 위 이 가 의 에 를 은 는 도 한 수"
).split())


def _tokens(title):
    """제목 → 핵심 단어 집합(출처 꼬리 제거, 불용어/짧은 토큰 제외)."""
    t = re.sub(r"\s+-\s+[^-]+$", "", title or "").lower()
    out = set()
    for w in re.split(r"[^0-9a-z가-힣]+", t):
        if len(w) >= 2 and w not in _STOP:
            out.add(w)
    return out


def _near_dup(toks, recent_sets):
    """이미 본 제목들과 핵심 단어가 크게 겹치면(같은 사건) True."""
    if len(toks) < 3:
        return False
    for ps in recent_sets:
        if len(ps) < 3:
            continue
        inter = len(toks & ps)
        if inter < 3:                              # 핵심단어 3개 미만 공유면 별개로 봄
            continue
        if inter / len(toks | ps) >= 0.45:         # 자카드 유사도
            return True
        if inter / min(len(toks), len(ps)) >= 0.6:  # 한쪽이 다른 쪽에 상당부분 포함
            return True
    return False


def draft(item, recent_headlines=None):
    """Claude로 게시 가치 판단 + 의미 기반 중복 차단 + 초안 생성. 가치 없으면 None."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    sys_p = (
        "You write X (Twitter) posts for KOSAI, an English-language research brand "
        "covering Korean stocks (KOSPI/KOSDAQ), especially semiconductors/HBM/memory. "
        "Audience: global finance Twitter. Decide if a news headline is worth an original post. "
        "Rules for the post: hook in line 1; short (2-4 short lines / 1-2 paragraphs); one idea; "
        "numbers over adjectives; confident brand voice but human; NO em-dashes, NO '~', "
        "NO phrases like 'worth noting'; NO emojis; NO links; neutral (not buy/sell advice). "
        "Be STRICT: most headlines are NOT worthy. Default to worthy=false. Only flag a genuinely "
        "market-moving event: a sharp index move (KOSPI/KOSDAQ selling off or rallying hard), a "
        "major single-stock move with a real catalyst, a clear earnings surprise, sizable M&A, "
        "significant regulation/policy, or a major supply/demand shift. "
        "Skip routine updates, opinion/analysis pieces, previews/recaps, PR fluff, listicles, "
        "small daily noise, and anything that merely restates a known story. When in doubt, skip. "
        "DEDUP RULE (critical): you will get a list of headlines we ALREADY posted recently. If the "
        "new headline is about the SAME underlying event or story as ANY of them, even if worded "
        "differently, from another outlet, or a follow-up/update, it is a DUPLICATE. Return "
        "{\"worthy\": false}. Only worthy if it is a genuinely NEW event not yet covered."
    )
    already = ""
    if recent_headlines:
        already = ("\n\nAlready posted recently (do NOT repeat the same story):\n"
                   + "\n".join(f"- {h}" for h in recent_headlines[-25:]))
    usr = (
        f"New headline: {item['title']}\nSource: {item['source']}{already}\n\n"
        "Return ONLY JSON: {\"worthy\": true|false, \"en\": \"<post in English>\", "
        "\"ko\": \"<Korean translation for the operator to verify>\"}. "
        "If not worthy or duplicate, return {\"worthy\": false}."
    )
    try:
        msg = client.messages.create(
            model=MODEL, max_tokens=700,
            system=sys_p, messages=[{"role": "user", "content": usr}],
        )
        txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            return None
        try:
            from json_repair import repair_json
            data = json.loads(repair_json(m.group(0)))
        except Exception:
            data = json.loads(m.group(0))
        if not data.get("worthy"):
            return None
        return data
    except Exception as e:
        log("draft 실패:", e)
        return None


def tg_send(text):
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


def main():
    if not (TG_TOKEN and TG_CHAT):
        log("⚠ TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — 종료(셋업 후 동작).")
        return
    if os.getenv("NEWS_TEST", "").lower() in ("1", "true", "yes"):
        ok = tg_send("✅ KOSAI 알림봇 연결 성공 — 이제 이슈가 뜨면 여기로 초안이 옵니다.")
        log("테스트 전송:", ok)
        return
    stt = load_state()
    seen = set(stt["seen"])
    first_run = len(seen) == 0
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y%m%d")
    if stt.get("day") != today:           # 자정(KST) 일일 카운터 리셋
        stt["day"] = today
        stt["sent_today"] = 0
    items = fetch_items()
    recent_sets = [set(x) for x in stt.get("titles", [])]   # 최근 제목 핵심단어
    log(f"후보 {len(items)}건, seen {len(seen)}건, 오늘발송 {stt['sent_today']}/{DAILY_MAX}, first_run={first_run}")

    new = []
    for it in items:
        # 1) 완전 동일 제목: 글자 기준 해시(출처 꼬리 제거 + 영숫자/한글만)
        core = re.sub(r"\s+-\s+[^-]+$", "", (it["title"] or "")).lower()
        core = re.sub(r"[^0-9a-z가-힣]+", "", core)
        iid = hashlib.sha1(core.encode("utf-8")).hexdigest()[:16]
        if iid in seen:
            continue
        # 2) 유사 제목(같은 사건·다른 문장): 핵심단어 겹침으로 차단
        toks = _tokens(it["title"])
        dup = _near_dup(toks, recent_sets)
        seen.add(iid)
        stt["seen"].append(iid)
        if not dup and len(toks) >= 3:
            recent_sets.append(toks)                 # 이후 항목·다음 실행과 비교용
            stt.setdefault("titles", []).append(sorted(toks))
        if first_run or dup:
            continue  # 첫 실행/유사중복은 기록만, 알림 X
        if relevant(it["title"]) and recent(it["pub"]):
            new.append(it)

    sent = 0
    sent_titles = stt.get("sent_titles", [])      # 최근 '실제 발송' 제목(의미 기반 중복차단용)
    for it in new[:MAX_PER_RUN]:
        if stt["sent_today"] >= DAILY_MAX:
            log(f"⛔ 일일 상한({DAILY_MAX}) 도달 — 추가 알림 보류.")
            break
        if not ANTHROPIC_KEY:
            break
        d = draft(it, recent_headlines=sent_titles)   # Claude가 같은 사건이면 worthy=false
        if not d:
            continue
        text = (
            f"🚨 ISSUE — {it['title']}\n{it['link']}\n"
            f"\n— EN (post) —\n{d.get('en','')}\n"
            f"\n— KR (검수) —\n{d.get('ko','')}"
        )
        if tg_send(text):
            sent += 1
            stt["sent_today"] += 1
            sent_titles.append(it["title"])
    stt["sent_titles"] = sent_titles[-60:]

    save_state(stt)
    log(f"신규 {len(new)}건 / 알림 {sent}건 전송(오늘 누적 {stt['sent_today']}/{DAILY_MAX}). 완료.")


if __name__ == "__main__":
    main()
