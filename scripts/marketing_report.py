#!/usr/bin/env python3
"""주 1회 성과 보고 — GA4 숫자를 사람 말로 옮긴다.

왜 모델에게 맡기나
------------------
숫자를 나열하는 것은 표가 더 잘한다. 사람이 알고 싶은 건 "그래서 뭐가
달라졌고 뭘 해야 하나"다. 그건 숫자 사이의 관계를 봐야 나오는 말이라
모델이 낫다.

대신 산수는 모델에게 시키지 않는다. 증감·비율은 여기서 파이썬으로
계산해서 넘긴다 — 모델이 숫자를 다시 세다가 틀리면 보고서 전체를
믿을 수 없게 된다. 모델은 이미 맞는 숫자를 읽고 해석만 한다.

    python3 scripts/marketing_report.py --dry     # 재료만 보고 끝 (공짜)
    python3 scripts/marketing_report.py           # 보고서 생성
    python3 scripts/marketing_report.py --send    # 생성 + 텔레그램
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "ga4" / "weekly.json"
OUTDIR = ROOT / "data" / "ga4" / "reports"
KST = datetime.timezone(datetime.timedelta(hours=9))

MODEL = os.getenv("MARKETING_MODEL", "claude-opus-5")
MAX_TOKENS = 4000
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

SYSTEM = """너는 KOSAI 라는 한국 주식 리포트 사이트의 마케팅 담당이다.
사장에게 지난주 성과를 보고한다.

사장은 개발자가 아니다. 어려운 말을 쓰면 읽지 않는다.
'세션', '이탈률', '전환', '오가닉', '트래픽', 'CTR', 'UV' 같은 말을 쓰지 마라.
꼭 써야 하면 괄호로 쉬운 말을 붙여라. 예: 세션(방문 횟수).

보고서는 짧다. 2,000자 안쪽이다. 읽는 데 2분이면 끝나야 한다."""


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _n(x):
    return f"{x:,}" if isinstance(x, (int, float)) else "?"


def _delta(now, before):
    """(변화량 문구, 증감률). 비교할 게 없으면 (None, None)."""
    if not isinstance(now, (int, float)) or not isinstance(before, (int, float)):
        return None, None
    if before == 0:
        return ("새로 생김" if now else None), None
    pct = (now - before) / before * 100
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.0f}%", pct


def facts_text(doc):
    """모델이 읽을 재료. 산수는 여기서 끝낸다."""
    weeks = doc.get("weeks") or []
    hl = doc.get("health") or {}
    L = []
    if not weeks:
        L.append("[숫자] 한 주도 받지 못했다.")
        L.append("  ⚠️ 숫자가 없으므로 성과를 말하지 마라. 받지 못했다고만 적어라.")
        return "\n".join(L)

    cur = weeks[-1]
    prev = weeks[-2] if len(weeks) >= 2 else None

    L.append(f"[이번 보고 대상] {cur['week']} ~ {cur['to']} (월~일 한 주)")
    if prev:
        L.append(f"[비교 대상] 그 앞 주 {prev['week']} ~ {prev['to']}")
    else:
        L.append("[비교 대상] 없다 — 앞 주 기록이 아직 없다. 증감을 말하지 마라.")

    L.append("\n[핵심 숫자]")
    pairs = [
        ("찾아온 사람", "users"),
        ("  그중 처음 온 사람", "newUsers"),
        ("  그중 다시 온 사람", "returningUsers"),
        ("방문 횟수", "sessions"),
        ("  그중 제대로 본 방문", "engagedSessions"),
        ("페이지를 본 횟수", "pageViews"),
    ]
    for label, key in pairs:
        now = cur.get(key)
        line = f"  {label}: {_n(now)}"
        if prev:
            d, _ = _delta(now, prev.get(key))
            line += f"  (앞 주 {_n(prev.get(key))}" + (f" · {d})" if d else ")")
        L.append(line)

    if cur.get("users"):
        r = cur.get("returningUsers", 0) / cur["users"] * 100
        line = f"  다시 온 사람 비율: {r:.0f}%"
        if prev and prev.get("users"):
            pr = prev.get("returningUsers", 0) / prev["users"] * 100
            line += f"  (앞 주 {pr:.0f}%)"
        L.append(line)
    sec = cur.get("avgSessionSec") or 0
    L.append(f"  한 번 오면 머무는 시간: {sec // 60}분 {sec % 60}초")

    if len(weeks) >= 3:
        L.append("\n[최근 흐름 — 찾아온 사람 / 다시 온 사람]")
        for w in weeks[-8:]:
            L.append(f"  {w['week']}  {_n(w.get('users')):>7} / {_n(w.get('returningUsers')):>7}")

    def block(title, key, dim, met, top=8, namer=None):
        """한 갈래(유입 경로·페이지…)를 앞 주와 나란히 적는다."""
        rows = cur.get(key) or []
        if not rows:
            L.append(f"\n[{title}] 받지 못했다 — 이 항목은 말하지 마라.")
            return
        L.append(f"\n[{title}]")
        # 앞 주 값은 원래 이름(사람이 보기 좋게 바꾸기 전)으로 찾는다.
        before = {r.get(dim): r.get(met) for r in ((prev or {}).get(key) or [])}
        # 큰 것부터. GA4 가 정렬해서 주지만, 옛 파일이나 손으로 넣은 값이
        # 섞여 들어와도 보고서가 뒤죽박죽으로 보이지 않게 여기서 한 번 더.
        rows = sorted(rows, key=lambda r: r.get(met) or 0, reverse=True)
        for r in rows[:top]:
            raw = r.get(dim, "")
            name = namer(raw) if namer else raw
            line = f"  {name}: {_n(r.get(met))}"
            if raw in before:
                d, _ = _delta(r.get(met), before[raw])
                if d:
                    line += f" (앞 주 {_n(before[raw])} · {d})"
            L.append(line)

    import ga4_data
    block("어디로 들어왔나(유입 경로)", "channels", "sessionDefaultChannelGroup",
          "sessions", namer=lambda x: ga4_data.CHANNEL_NAMES.get(x, x))
    block("많이 본 페이지", "pages", "pagePath", "screenPageViews",
          namer=lambda p: ga4_data.PAGE_NAMES.get(p, p))
    block("기기", "devices", "deviceCategory", "totalUsers", top=4,
          namer=lambda x: ga4_data.DEVICE_NAMES.get(x, x))
    block("어느 사이트에서 왔나", "sources", "sessionSource", "sessions",
          namer=lambda x: ga4_data.SOURCE_NAMES.get(x, x))

    evs = cur.get("events") or []
    if evs:
        want = {"sign_up": "회원가입", "watchlist_add": "관심종목 담기"}
        picked = [e for e in evs if e.get("eventName") in want]
        if picked:
            L.append("\n[우리가 따로 세는 행동]")
            for e in picked:
                L.append(f"  {want[e['eventName']]}: {_n(e.get('eventCount'))}")

    if not hl.get("ok", True):
        L.append("\n⚠️ 이 숫자는 온전하지 않다 — " + " / ".join(hl.get("problems") or []))
        L.append("  빠진 것을 '0이었다'로 말하지 마라. 못 받았다고 적어라.")
    return "\n".join(L)


PROMPT = """아래는 KOSAI 사이트의 지난주 숫자다. 산수는 이미 끝나 있으니
다시 계산하지 말고, 적힌 값을 그대로 쓰면 된다.

{facts}

이걸 읽고 사장에게 보낼 주간 보고서를 써라.

담아야 할 것
  · 지난주에 무슨 일이 있었나. 늘었나 줄었나, 그게 의미 있는 변화인가.
  · 다시 온 사람(재방문)이 어떻게 됐나. 사장이 제일 궁금해하는 숫자다.
    한 번 오고 마는 사이트인지, 붙잡고 있는지가 여기서 보인다.
  · 눈에 띄는 것 하나둘. 특정 페이지가 갑자기 떴다든지, 새 유입 경로가
    생겼다든지. 없으면 억지로 만들지 마라.
  · 다음 주에 해볼 만한 것. 숫자에서 나온 것만. 일반론은 쓰지 마라.
    ("SEO를 강화하자" 같은 말은 아무 데나 붙는 말이라 쓸모가 없다.)

쓰지 말 것
  · 숫자를 지어내지 마라. 위에 없는 것은 없는 것이다.
  · '받지 못했다'고 적힌 항목을 0이라고 하지 마라.
  · 한 주 숫자로 큰 결론을 내지 마라. 흐름이 두세 주 이어질 때만
    "추세"라고 불러라.

모양
  제목 한 줄로 시작한다. 그 주를 한마디로 요약하는 말이다.
  그다음은 자유롭게 쓴다. 항목을 몇 개로 나눌지도 네가 정한다.
  마크다운 표는 쓰지 마라 — 휴대폰 메신저로 읽는다.
  굵게(**)도 쓰지 마라. 그냥 글로 써라."""


def build_prompt(doc):
    return PROMPT.format(facts=facts_text(doc))


def generate(prompt):
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("❌ ANTHROPIC_API_KEY 가 없다")
    cl = anthropic.Anthropic(api_key=key)
    with cl.messages.stream(model=MODEL, max_tokens=MAX_TOKENS, system=SYSTEM,
                            thinking={"type": "adaptive"},
                            messages=[{"role": "user", "content": prompt}]) as s:
        msg = s.get_final_message()
    text = "\n".join(b.text for b in msg.content
                     if getattr(b, "type", None) == "text").strip()
    return text, msg.usage


def send_telegram(text):
    """4,096자가 한 통 한도라 길면 나눠 보낸다."""
    import requests
    if not (TG_TOKEN and TG_CHAT):
        log("· 텔레그램 열쇠가 없다 — 보내지 않는다")
        return False
    chunks, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) + 2 > 3800:
            chunks.append(cur.strip())
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        chunks.append(cur.strip())
    okall = True
    for i, c in enumerate(chunks):
        head = "" if i == 0 else f"(이어서 {i + 1}/{len(chunks)})\n\n"
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                data={"chat_id": TG_CHAT, "text": head + c,
                      "disable_web_page_preview": "true"}, timeout=20)
            if not r.ok:
                log("텔레그램 오류:", r.status_code, r.text[:300])
                okall = False
        except Exception as e:
            log("텔레그램 예외:", e)
            okall = False
    return okall


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="재료만 보고 끝(공짜)")
    ap.add_argument("--send", action="store_true", help="텔레그램으로 보낸다")
    ap.add_argument("--data", help="쓸 파일 (기본 data/ga4/weekly.json)")
    a = ap.parse_args()

    path = Path(a.data) if a.data else DATA
    if not path.exists():
        log(f"❌ {path} 가 없다 — 먼저 scripts/ga4_data.py --write 를 돌려라")
        return 2
    doc = json.loads(path.read_text(encoding="utf-8"))

    if a.dry:
        print(build_prompt(doc))
        return 0

    weeks = doc.get("weeks") or []
    if not weeks:
        log("❌ 숫자가 한 주도 없다 — 보고서를 만들지 않는다")
        return 2

    text, usage = generate(build_prompt(doc))
    if not text:
        log("❌ 빈 응답")
        return 3

    cur = weeks[-1]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    f = OUTDIR / f"{cur['week']}.md"
    f.write_text(text + "\n", encoding="utf-8")
    log(f"✅ {f.relative_to(ROOT)} · {len(text):,}자")
    print(text)

    if a.send:
        log("· 텔레그램 " + ("보냄" if send_telegram(text) else "실패"))
    if usage:
        log(f"· 입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,} 토큰")
    return 0


if __name__ == "__main__":
    sys.exit(main())
