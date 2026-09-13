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
# 100만 토큰당 달러 (입력, 출력). generate_brief.py 와 같은 표다.
PRICES = {
    "claude-opus-5": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
USD_KRW = float(os.getenv("BRIEF_USD_KRW", "1400"))
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


WEEK_KO = ["월", "화", "수", "목", "금", "토", "일"]


def _d(iso):
    """'2026-09-07' → '9월 7일(월)'"""
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{m}월 {d}일({WEEK_KO[datetime.date(y, m, d).weekday()]})"


def _arrow(pct):
    if pct is None:
        return ""
    if pct > 0.5:
        return "▲"
    if pct < -0.5:
        return "▼"
    return "－"


def _pp(now, before):
    """비율끼리의 차이는 %p 로 적는다. 14.4% 와 16.3% 의 차이는
    '1.9%p 하락' 이지 '11% 하락' 이 아니다. 이걸 섞어 쓰면 보고서를
    믿을 수 없게 된다."""
    if now is None or before is None:
        return ""
    diff = now - before
    mark = "▲" if diff > 0.05 else ("▼" if diff < -0.05 else "－")
    return f"{mark}{abs(diff):.1f}%p"


def _rate(a, b):
    return (a / b * 100) if b else None


def _w(t):
    """화면에서 차지하는 칸 수. 한글·한자는 한 글자가 두 칸이다.
    len() 으로 맞추면 표가 어긋나 보고서가 지저분해진다."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in str(t))


def _pad(t, width):
    return str(t) + " " * max(0, width - _w(t))


def _line(label, now, before, unit="", pad=16):
    """'방문자   382명  ▼11% (앞주 427명)' 한 줄."""
    d, pct = _delta(now, before)
    tail = f"  {_arrow(pct)}{d.lstrip('+-') if d else ''}" if d else ""
    prev = f"  (앞주 {_n(before)}{unit})" if isinstance(before, (int, float)) else ""
    return f"  {_pad(label, pad)}{_n(now)}{unit}{tail}{prev}"


def split_pages(week):
    """페이지를 콘텐츠·계정·관리자·테스트로 갈라 합계를 낸다."""
    import ga4_data
    out = {"콘텐츠": 0, "계정": 0, "관리자": 0, "테스트": 0}
    rows = week.get("pages") or []
    for r in rows:
        out[ga4_data.page_kind(r.get("pagePath"))] += r.get("screenPageViews") or 0
    return out, sum(out.values())


def metrics_block(doc):
    """사람이 그대로 읽는 숫자판. 모델을 거치지 않는다.

    모델이 숫자를 옮겨 적다가 한 자리 틀리면 보고서 전체를 못 믿는다.
    그래서 숫자는 코드가 찍고, 모델은 그 아래에 해석만 쓴다.
    """
    weeks = doc.get("weeks") or []
    if not weeks:
        return "📊 KOSAI 주간 성과\n\n숫자를 받지 못했습니다."
    cur = weeks[-1]
    prev = weeks[-2] if len(weeks) >= 2 else None
    L = []
    L.append("📊 KOSAI 주간 성과 보고")
    L.append(f"기간  {_d(cur['week'])} ~ {_d(cur['to'])} (7일)")
    if prev:
        L.append(f"비교  {_d(prev['week'])} ~ {_d(prev['to'])}")
    else:
        L.append("비교  없음 (앞 주 기록이 아직 없습니다)")
    L.append("")

    L.append("■ 얼마나 왔나")
    L.append(_line("방문자", cur.get("users"), (prev or {}).get("users"), "명"))
    L.append(_line("├ 처음", cur.get("newUsers"), (prev or {}).get("newUsers"), "명"))
    L.append(_line("└ 다시 온", cur.get("returningUsers"),
                   (prev or {}).get("returningUsers"), "명"))
    r_now = _rate(cur.get("returningUsers"), cur.get("users"))
    r_bef = _rate((prev or {}).get("returningUsers"), (prev or {}).get("users")) if prev else None
    if r_now is not None:
        tail = f"  {_pp(r_now, r_bef)}" if r_bef is not None else ""
        prevs = f"  (앞주 {r_bef:.1f}%)" if r_bef is not None else ""
        L.append(f"  {_pad('재방문율', 16)}{r_now:.1f}%{tail}{prevs}")
        L.append("     └ 다시 온 사람 ÷ 전체 방문자. 붙잡고 있는지를 보는 숫자입니다.")
    L.append("")

    L.append("■ 얼마나 봤나")
    L.append(_line("방문 횟수", cur.get("sessions"), (prev or {}).get("sessions"), "회"))
    L.append(_line("페이지 조회", cur.get("pageViews"), (prev or {}).get("pageViews"), "회"))
    pv_now = (cur.get("pageViews") or 0) / cur["sessions"] if cur.get("sessions") else None
    pv_bef = ((prev or {}).get("pageViews") or 0) / prev["sessions"] if prev and prev.get("sessions") else None
    if pv_now:
        prevs = f"  (앞주 {pv_bef:.1f}장)" if pv_bef else ""
        L.append(f"  {_pad('방문당 조회', 16)}{pv_now:.1f}장{prevs}")
    e_now = _rate(cur.get("engagedSessions"), cur.get("sessions"))
    e_bef = _rate((prev or {}).get("engagedSessions"), (prev or {}).get("sessions")) if prev else None
    if e_now is not None:
        tail = f"  {_pp(e_now, e_bef)}" if e_bef is not None else ""
        L.append(f"  {_pad('제대로 본 방문', 16)}{e_now:.0f}%{tail}")
        L.append("     └ 10초 넘게 머물거나 2장 이상 본 방문의 비율입니다.")
    sec = cur.get("avgSessionSec") or 0
    L.append(f"  {_pad('머문 시간', 16)}{sec // 60}분 {sec % 60}초")
    L.append("")

    # 내부 발자국. 이걸 따로 떼어 놓지 않으면 성장 숫자가 허구가 된다.
    kinds, tot = split_pages(cur)
    pk, ptot = split_pages(prev) if prev else ({}, 0)
    inner = kinds["계정"] + kinds["관리자"] + kinds["테스트"]
    pinner = (pk.get("계정", 0) + pk.get("관리자", 0) + pk.get("테스트", 0)) if prev else None
    if tot:
        L.append("■ 이 중 우리 발자국 (상위 페이지 기준)")
        L.append(f"  {_pad('콘텐츠', 16)}{_n(kinds['콘텐츠'])}회")
        L.append(f"  {_pad('계정·관리·시험', 16)}{_n(inner)}회  ({inner / tot * 100:.0f}%)"
                 + (f"  (앞주 {pinner / ptot * 100:.0f}%)" if pinner is not None and ptot else ""))
        L.append("     └ 로그인·가입·관리자·staging 은 대개 우리가 본 것입니다.")
        L.append("        늘거나 줄어도 성과 변화로 읽으면 안 됩니다.")
        L.append("")

    evs = {e.get("eventName"): e.get("eventCount") for e in (cur.get("events") or [])}
    pevs = {e.get("eventName"): e.get("eventCount") for e in ((prev or {}).get("events") or [])}
    if evs.get("sign_up") is not None or evs.get("watchlist_add") is not None:
        L.append("■ 무엇을 했나")
        su = evs.get("sign_up")
        if su is not None:
            cv = _rate(su, cur.get("users"))
            L.append(_line("회원가입", su, pevs.get("sign_up"), "건")
                     + (f"  · 방문자의 {cv:.1f}%" if cv is not None else ""))
        wl = evs.get("watchlist_add")
        if wl is not None:
            L.append(_line("관심종목 담기", wl, pevs.get("watchlist_add"), "건"))
        L.append("")

    hl = doc.get("health") or {}
    if not hl.get("ok", True):
        L.append("⚠️ 이 숫자는 온전하지 않습니다 — " + " / ".join(hl.get("problems") or []))
        L.append("")
    return "\n".join(L).rstrip()


def facts_text(doc):
    """모델이 읽을 재료. 산수는 여기서 끝낸다."""
    import ga4_data
    weeks = doc.get("weeks") or []
    hl = doc.get("health") or {}
    L = []
    if not weeks:
        L.append("[숫자] 한 주도 받지 못했다.")
        L.append("  ⚠️ 숫자가 없으므로 성과를 말하지 마라. 받지 못했다고만 적어라.")
        return "\n".join(L)

    cur = weeks[-1]
    prev = weeks[-2] if len(weeks) >= 2 else None

    L.append("[사람이 이미 보고 있는 숫자판 — 여기 있는 숫자를 다시 나열하지 마라]")
    L.append(metrics_block(doc))
    L.append("")
    if not prev:
        L.append("[비교 대상] 없다 — 앞 주 기록이 아직 없다. 증감을 말하지 마라.")

    if len(weeks) >= 3:
        L.append("\n[더 긴 흐름 — 주 / 방문자 / 재방문 / 재방문율]")
        for w in weeks[-8:]:
            r = (w.get("returningUsers", 0) / w["users"] * 100) if w.get("users") else 0
            L.append(f"  {w['week']}  {_n(w.get('users')):>6}  "
                     f"{_n(w.get('returningUsers')):>5}  {r:>5.1f}%")

    def block(title, key, dim, met, top=8, namer=None, kinder=None):
        rows = cur.get(key) or []
        if not rows:
            L.append(f"\n[{title}] 받지 못했다 — 이 항목은 말하지 마라.")
            return
        L.append(f"\n[{title}]")
        before = {r.get(dim): r.get(met) for r in ((prev or {}).get(key) or [])}
        rows = sorted(rows, key=lambda r: r.get(met) or 0, reverse=True)
        for r in rows[:top]:
            raw = r.get(dim, "")
            name = namer(raw) if namer else raw
            kind = f" [{kinder(raw)}]" if kinder else ""
            line = f"  {name}{kind}: {_n(r.get(met))}"
            if raw in before:
                d, _p = _delta(r.get(met), before[raw])
                if d:
                    line += f" (앞주 {_n(before[raw])} · {d})"
            L.append(line)

    block("어디로 들어왔나(유입 경로) · 방문 횟수", "channels",
          "sessionDefaultChannelGroup", "sessions",
          namer=lambda x: ga4_data.CHANNEL_NAMES.get(x, x))
    block("어느 사이트에서 왔나 · 방문 횟수", "sources", "sessionSource", "sessions",
          namer=lambda x: ga4_data.SOURCE_NAMES.get(x, x))
    block("페이지별 조회", "pages", "pagePath", "screenPageViews", top=12,
          namer=lambda p: ga4_data.PAGE_NAMES.get(p, p),
          kinder=ga4_data.page_kind)
    block("기기", "devices", "deviceCategory", "totalUsers", top=4,
          namer=lambda x: ga4_data.DEVICE_NAMES.get(x, x))

    # 가입·관심종목도 우리가 시험하면 올라간다. 계정 페이지가 같이
    # 움직였으면 그 얘기를 먼저 해야 한다 — 8/24 주 가입 29건이
    # 그런 경우였다(같은 주 가입 페이지 33회·동의 68회).
    if prev:
        acc_now = split_pages(cur)[0]["계정"] + split_pages(cur)[0]["관리자"]
        acc_bef = split_pages(prev)[0]["계정"] + split_pages(prev)[0]["관리자"]
        if acc_bef and abs(acc_now - acc_bef) / acc_bef > 0.5:
            L.append(f"\n[주의] 계정·관리자 페이지 조회가 {acc_bef}회에서 {acc_now}회로"
                     " 크게 움직였다. 가입·관심종목 같은 숫자도 우리가 시험하면 같이"
                     " 움직인다. 이 변화를 손님의 행동으로 읽지 마라.")

    L.append("\n[페이지 갈래가 뜻하는 것]")
    L.append("  콘텐츠 = 손님이 보러 오는 글. 마케팅이 키워야 할 숫자.")
    L.append("  계정   = 로그인·가입·동의. 손님 것도 있지만 우리가 시험한 것이 많이 섞인다.")
    L.append("  관리자·테스트 = 사실상 전부 우리가 본 것. 성과가 아니다.")

    if not hl.get("ok", True):
        L.append("\n⚠️ 이 숫자는 온전하지 않다 — " + " / ".join(hl.get("problems") or []))
        L.append("  빠진 것을 '0이었다'로 말하지 마라. 못 받았다고 적어라.")
    return "\n".join(L)


PROMPT = """아래는 KOSAI 사이트의 지난주 숫자다. 산수는 이미 끝나 있다.

{facts}

사장이 읽을 주간 보고의 **해석 부분**을 써라. 숫자판은 네 글 위에 이미
붙어 있으니, 거기 있는 숫자를 다시 늘어놓지 마라. 사장이 숫자판을 보고
"그래서 뭐?" 라고 물었을 때의 대답이 네 글이다.

이 모양으로 쓴다. 각 제목은 그대로 쓰고, 내용만 채운다.

■ 한 줄로 말하면
  지난주를 한 문장으로. 판단이 들어가야 한다.
  "방문자가 줄었습니다"는 숫자판이 이미 말했다. 그게 좋은 일인지 나쁜
  일인지, 걱정할 일인지 아닌지를 말해라.

■ 무슨 일이 있었나
  숫자 뒤의 이야기. 두세 문단.
  · 서로 맞물리는 숫자를 붙여서 읽어라. 방문자는 줄었는데 재방문율은
    올랐다면 그건 '나빠졌다'가 아니라 '뜨내기가 줄었다'일 수 있다.
  · 원인을 말할 때는 근거가 되는 숫자를 같이 대라. 근거가 없으면
    "이유는 이 숫자만으로 알 수 없다"고 적어라. 그게 정직한 보고다.
  · 우리 발자국(계정·관리자·테스트)이 크게 움직였으면 그건 성과가
    아니라고 명시해라. 성과 얘기에서 빼고 말해야 한다.

■ 다음 주에 할 것
  두세 개. 많을수록 좋은 게 아니다.
  각 항목은 이렇게 쓴다 — 무엇을 / 왜(어느 숫자 때문에) / 그래서 뭘 보면
  됐는지 알 수 있나.
  이번 주 숫자에서 나온 것만 써라. "SEO를 강화하자", "콘텐츠를 늘리자"
  같은 말은 어느 사이트에나 붙는 말이라 아무 쓸모가 없다.

지켜야 할 것
  · 한 주 움직임으로 추세를 말하지 마라. 세 주 이상 같은 방향일 때만
    "추세"라는 말을 써라. 긴 흐름표가 위에 있으니 그걸 보고 판단해라.
  · 비율의 변화는 %p 다. 14.4%에서 16.3%로 갔으면 '1.9%p 올랐다'이지
    '13% 올랐다'가 아니다.
  · 위에 없는 숫자를 지어내지 마라. '받지 못했다'고 적힌 것을 0으로
    바꿔 말하지 마라.
  · 표를 그리지 마라. 굵게(**)도 쓰지 마라. 휴대폰 메신저로 읽는다.
  · 전체 1,200자 안쪽. 짧고 정확한 것이 길고 그럴듯한 것보다 낫다."""


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
    # 숫자판이 먼저, 해석이 뒤. 숫자는 코드가 찍었으므로 틀릴 수 없다.
    text = metrics_block(doc) + "\n\n" + text

    cur = weeks[-1]
    OUTDIR.mkdir(parents=True, exist_ok=True)
    f = OUTDIR / f"{cur['week']}.md"
    f.write_text(text + "\n", encoding="utf-8")
    log(f"✅ {f.relative_to(ROOT)} · {len(text):,}자")
    print(text)

    if a.send:
        log("· 텔레그램 " + ("보냄" if send_telegram(text) else "실패"))
    # 얼마 들었는지는 한 번 보고 끝낼 것이 아니라 매주 눈에 보여야 한다.
    # 조용히 새는 비용은 아무도 안 본다.
    if usage:
        pin, pout = PRICES.get(MODEL, (0.0, 0.0))
        usd = (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6
        line = (f"입력 {usage.input_tokens:,} / 출력 {usage.output_tokens:,} 토큰 · "
                f"${usd:.3f} (약 {usd * USD_KRW:,.0f}원)")
        log("· " + line)
        sm = os.environ.get("GITHUB_STEP_SUMMARY")
        if sm:
            with open(sm, "a", encoding="utf-8") as f:
                f.write(f"\n\n_이번 보고 비용 — {line}_\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
