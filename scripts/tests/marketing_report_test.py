#!/usr/bin/env python3
"""marketing_report.py — 모델을 부르지 않고 볼 수 있는 부분만."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import marketing_report as M

P = F = 0


def ok(name, cond, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  ✅ {name}")
    else:
        F += 1
        print(f"  ❌ {name}  {extra}")


def wk(w, to, u, n, r, s, e, pv, sec, **kw):
    d = dict(week=w, to=to, users=u, newUsers=n, returningUsers=r, sessions=s,
             engagedSessions=e, pageViews=pv, avgSessionSec=sec)
    d.update(kw)
    return d


A = wk("2026-08-31", "2026-09-06", 1310, 940, 370, 1810, 1240, 6100, 131)
B = wk("2026-09-07", "2026-09-13", 1480, 1010, 470, 2120, 1490, 7400, 146,
       channels=[{"sessionDefaultChannelGroup": "Organic Search", "sessions": 1102},
                 {"sessionDefaultChannelGroup": "Direct", "sessions": 657}],
       pages=[{"pagePath": "/", "screenPageViews": 2220},
              {"pagePath": "/stock.html", "screenPageViews": 3108}],
       devices=[{"deviceCategory": "mobile", "totalUsers": 1006}],
       events=[{"eventName": "sign_up", "eventCount": 12},
               {"eventName": "watchlist_add", "eventCount": 32}])
GOOD = {"weeks": [A, B], "health": {"ok": True, "problems": []}}

print("① 증감 계산 — 모델이 산수하게 두지 않는다")
ok("늘면 +", M._delta(1480, 1310)[0] == "+13%", M._delta(1480, 1310)[0])
ok("줄면 -", M._delta(1000, 1310)[0] == "-24%", M._delta(1000, 1310)[0])
ok("앞이 0이면 나누지 않는다", M._delta(50, 0)[0] == "새로 생김")
ok("둘 다 0이면 조용히", M._delta(0, 0)[0] is None)
ok("값이 없으면 조용히", M._delta(None, 10) == (None, None))

print("\n② 핵심 숫자가 재료에 그대로 실린다")
t = M.facts_text(GOOD)
ok("찾아온 사람", "찾아온 사람: 1,480" in t)
ok("다시 온 사람", "다시 온 사람: 470" in t)
ok("앞 주와 증감", "앞 주 370 · +27%" in t)
ok("재방문 비율", "다시 온 사람 비율: 32%" in t and "앞 주 28%" in t, t[:0])
ok("머문 시간이 분·초", "2분 26초" in t)
ok("비교 대상 주를 밝힌다", "2026-08-31 ~ 2026-09-06" in t)

print("\n③ 영어를 사람 말로 바꾼다")
ok("유입 경로", "검색으로 들어옴" in t and "Organic Search" not in t)
ok("페이지", "종목 리포트" in t and "/stock.html" not in t)
ok("기기", "휴대폰" in t and "mobile" not in t)

print("\n④ 큰 것부터 나온다")
i_stock, i_home = t.find("종목 리포트"), t.find("홈:")
ok("조회 많은 페이지가 위로", 0 < i_stock < i_home, f"{i_stock} {i_home}")

print("\n⑤ 없는 것을 있는 척하지 않는다")
t0 = M.facts_text({"weeks": [], "health": {"ok": False, "problems": ["권한 없음"]}})
ok("한 주도 없으면 그렇게 적는다", "한 주도 받지 못했다" in t0)
ok("성과를 말하지 말라고 한다", "성과를 말하지 마라" in t0)

t1 = M.facts_text({"weeks": [B], "health": {"ok": True, "problems": []}})
ok("앞 주가 없으면 증감을 말하지 말라고 한다", "증감을 말하지 마라" in t1)
ok("앞 주 비교를 붙이지 않는다", "앞 주" not in t1.split("[최근 흐름")[0].split("[핵심 숫자]")[1])

t2 = M.facts_text({"weeks": [A, B], "health": {"ok": False, "problems": ["조회 실패"]}})
ok("일부 실패를 재료에 적는다", "온전하지 않다" in t2 and "조회 실패" in t2)
ok("0으로 말하지 말라고 한다", "'0이었다'로 말하지 마라" in t2)

t3 = M.facts_text({"weeks": [A], "health": {"ok": True, "problems": []}})
ok("세부 항목이 없으면 말하지 말라고 한다", "이 항목은 말하지 마라" in t3)

print("\n⑥ 우리가 세는 행동만 골라 적는다")
ok("회원가입", "회원가입: 12" in t)
ok("관심종목", "관심종목 담기: 32" in t)
ok("page_view 같은 건 안 적는다", "page_view" not in t)

print("\n⑦ 텔레그램 한 통 한도(4,096자)를 넘기지 않는다")
import types
sent = []


class _R:
    ok = True

    @staticmethod
    def json():
        return {"result": {}}


fake = types.SimpleNamespace(post=lambda url, **kw: (sent.append(kw["data"]["text"]), _R)[1])
real_tok, real_chat = M.TG_TOKEN, M.TG_CHAT
M.TG_TOKEN, M.TG_CHAT = "x", "y"
sys.modules["requests"] = fake
try:
    long_text = "\n\n".join(f"{i}번 문단 " + "가" * 300 for i in range(40))
    M.send_telegram(long_text)
finally:
    M.TG_TOKEN, M.TG_CHAT = real_tok, real_chat
    import importlib
    sys.modules["requests"] = importlib.import_module("requests")
ok("여러 통으로 나뉜다", len(sent) > 1, f"{len(sent)}통")
ok("모든 통이 한도 안", all(len(c) < 4096 for c in sent),
   str([len(c) for c in sent]))
ok("내용이 유실되지 않는다",
   all(f"{i}번 문단" in "".join(sent) for i in range(40)))

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
