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
MAX_PER_RUN = int(os.getenv("NEWS_MAX_PER_RUN", "4"))
RECENCY_MIN = int(os.getenv("NEWS_RECENCY_MIN", "35"))  # 최근 N분 내 기사만

# 감시 키워드(이 중 하나라도 제목에 있어야 후보) + Google News 검색식
QUERIES = [
    '("SK Hynix" OR "Samsung Electronics" OR HBM OR DRAM) memory chip Korea',
    'KOSPI OR KOSDAQ Korean stock semiconductor',
]
KEYWORDS = [
    "hynix", "samsung", "hbm", "dram", "nand", "micron", "memory chip",
    "kospi", "kosdaq", "korea chip", "korean chip", "tsmc", "nvidia",
    "반도체", "하이닉스", "삼성전자", "메모리",
]


def log(*a):
    print(*a, flush=True)


def load_seen():
    try:
        return set(json.loads(SEEN.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen(s):
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(list(s)[-800:], ensure_ascii=False), encoding="utf-8")


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


def draft(item):
    """Claude로 게시 가치 판단 + 초안 생성. 가치 없으면 None."""
    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    sys_p = (
        "You write X (Twitter) posts for KOSAI, an English-language research brand "
        "covering Korean stocks (KOSPI/KOSDAQ), especially semiconductors/HBM/memory. "
        "Audience: global finance Twitter. Decide if a news headline is worth an original post. "
        "Rules for the post: hook in line 1; short (2-4 short lines / 1-2 paragraphs); one idea; "
        "numbers over adjectives; confident brand voice but human; NO em-dashes, NO '~', "
        "NO phrases like 'worth noting'; NO emojis; NO links; neutral (not buy/sell advice). "
        "Only flag as worthy if it's genuinely notable (milestone, big move, surprising data, policy). "
        "Skip routine/duplicate/PR fluff."
    )
    usr = (
        f"Headline: {item['title']}\nSource: {item['source']}\n\n"
        "Return ONLY JSON: {\"worthy\": true|false, \"en\": \"<post in English>\", "
        "\"ko\": \"<Korean translation for the operator to verify>\"}. "
        "If not worthy, return {\"worthy\": false}."
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
        return r.ok
    except Exception as e:
        log("텔레그램 실패:", e)
        return False


def main():
    if not (TG_TOKEN and TG_CHAT):
        log("⚠ TELEGRAM_BOT_TOKEN/CHAT_ID 미설정 — 종료(셋업 후 동작).")
        return
    if os.getenv("NEWS_TEST", "").lower() in ("1", "true", "yes"):
        ok = tg_send("✅ KOSAI 알림봇 연결 성공 — 이제 이슈가 뜨면 여기로 초안이 옵니다.")
        log("테스트 전송:", ok)
        return
    seen = load_seen()
    first_run = len(seen) == 0
    items = fetch_items()
    log(f"후보 {len(items)}건, seen {len(seen)}건, first_run={first_run}")

    new = []
    for it in items:
        iid = hashlib.sha1(it["link"].encode()).hexdigest()[:16]
        if iid in seen:
            continue
        seen.add(iid)
        if first_run:
            continue  # 첫 실행은 폭주 방지: 전부 seen 처리만, 알림 X
        if relevant(it["title"]) and recent(it["pub"]):
            new.append(it)

    sent = 0
    for it in new[:MAX_PER_RUN]:
        if not ANTHROPIC_KEY:
            break
        d = draft(it)
        if not d:
            continue
        text = (
            f"🚨 ISSUE — {it['title']}\n{it['link']}\n"
            f"\n— EN (post) —\n{d.get('en','')}\n"
            f"\n— KR (검수) —\n{d.get('ko','')}"
        )
        if tg_send(text):
            sent += 1

    save_seen(seen)
    log(f"신규 {len(new)}건 / 알림 {sent}건 전송. 완료.")


if __name__ == "__main__":
    main()
