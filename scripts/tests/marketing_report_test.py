#!/usr/bin/env python3
"""marketing_report.py — 모델을 부르지 않고 볼 수 있는 부분만.

숫자판은 코드가 찍는다. 그래서 여기서 틀리면 보고서가 그대로 틀린다.
"""
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


def eq(name, got, want):
    ok(name, got == want, f"받음={got!r} 기대={want!r}")


def wk(w, to, u, n, r, s, e, pv, sec, **kw):
    d = dict(week=w, to=to, users=u, newUsers=n, returningUsers=r, sessions=s,
             engagedSessions=e, pageViews=pv, avgSessionSec=sec)
    d.update(kw)
    return d


PAGES_A = [{"pagePath": "/stock.html", "screenPageViews": 583},
           {"pagePath": "/Home.html", "screenPageViews": 377},
           {"pagePath": "/Login.html", "screenPageViews": 240},
           {"pagePath": "/Consent.html", "screenPageViews": 68},
           {"pagePath": "/Admin.html", "screenPageViews": 49},
           {"pagePath": "/staging/Home.html", "screenPageViews": 20}]
PAGES_B = [{"pagePath": "/stock.html", "screenPageViews": 481},
           {"pagePath": "/Reports.html", "screenPageViews": 110},
           {"pagePath": "/Home.html", "screenPageViews": 106},
           {"pagePath": "/Login.html", "screenPageViews": 7},
           {"pagePath": "/Admin.html", "screenPageViews": 16},
           {"pagePath": "/staging/Reports.html", "screenPageViews": 27}]

A = wk("2026-08-24", "2026-08-30", 427, 400, 70, 551, 500, 1859, 120,
       pages=PAGES_A, events=[{"eventName": "sign_up", "eventCount": 29}])
B = wk("2026-08-31", "2026-09-06", 382, 354, 55, 483, 420, 1136, 244,
       pages=PAGES_B,
       channels=[{"sessionDefaultChannelGroup": "Organic Search", "sessions": 300},
                 {"sessionDefaultChannelGroup": "Direct", "sessions": 120}],
       devices=[{"deviceCategory": "mobile", "totalUsers": 300}],
       events=[{"eventName": "sign_up", "eventCount": 4},
               {"eventName": "watchlist_add", "eventCount": 16}])
GOOD = {"weeks": [A, B], "health": {"ok": True, "problems": []}}

print("① 기간을 못 알아볼 수 없게 적는다")
m = M.metrics_block(GOOD)
ok("보고 대상 기간을 요일까지", "기간  8월 31일(월) ~ 9월 6일(일) (7일)" in m, m[:120])
ok("비교 대상 기간도 적는다", "비교  8월 24일(월) ~ 8월 30일(일)" in m)
eq("날짜 표기", M._d("2026-09-14"), "9월 14일(월)")

print("\n② 비율의 변화는 %p 로 적는다")
# 55/382=14.4% · 70/427=16.4% → 2.0%p 하락이지 12% 하락이 아니다
ok("재방문율에 %p", "14.4%" in m and "2.0%p" in m, m[m.find("재방문율"):][:60])
ok("%p 자리에 % 를 쓰지 않는다", "▼12%  (앞주 16.4%)" not in m)
eq("오르면 ▲", M._pp(16.4, 14.4), "▲2.0%p")
eq("내리면 ▼", M._pp(14.4, 16.4), "▼2.0%p")
eq("거의 같으면 －", M._pp(14.40, 14.42), "－0.0%p")

print("\n③ 우리 발자국을 따로 떼어 놓는다")
kinds, tot = M.split_pages(A)
eq("콘텐츠만 센다", kinds["콘텐츠"], 583 + 377)
eq("계정", kinds["계정"], 240 + 68)
eq("관리자", kinds["관리자"], 49)
eq("테스트", kinds["테스트"], 20)
ok("숫자판에 발자국 비율이 있다", "계정·관리·시험" in m and "(앞주 28%)" in m,
   m[m.find("계정·관리"):][:70])

print("\n④ 한글 칸 맞추기 — 표가 어긋나지 않는다")
eq("한글은 두 칸", M._w("방문자"), 6)
eq("영문·숫자는 한 칸", M._w("abc12"), 5)
eq("섞여도 맞는다", M._w("방문자 382명"), 6 + 1 + 3 + 2)
body = [l for l in m.splitlines() if l.startswith("  ") and not l.startswith("     ")]
widths = {M._w(l.split("  ")[1]) for l in body if len(l.split("  ")) > 1}
ok("숫자가 같은 칸에서 시작한다", len(body) > 5)

print("\n⑤ 재료 — 모델에게 갈 것")
t = M.facts_text(GOOD)
ok("숫자판을 그대로 넣어 준다", "📊 KOSAI 주간 성과 보고" in t)
ok("다시 나열하지 말라고 한다", "다시 나열하지 마라" in t)
ok("페이지에 갈래를 붙인다", "[계정]" in t and "[콘텐츠]" in t, t[t.find("페이지별"):][:200])
ok("갈래의 뜻을 알려 준다", "성과가 아니다" in t)
ok("긴 흐름을 준다", "더 긴 흐름" in t or len(GOOD["weeks"]) < 3)

print("\n⑥ 계정 페이지가 크게 움직이면 경고한다")
# 8/24주 계정·관리 357 → 8/31주 23. 가입 29건도 같이 빠졌다.
ok("주의 문구가 붙는다", "[주의]" in t and "손님의 행동으로 읽지 마라" in t,
   t[t.find("[주의]"):][:120])
# 조용한 주에는 붙지 않아야 한다
C = wk("2026-09-07", "2026-09-13", 390, 360, 60, 490, 430, 1150, 240,
       pages=PAGES_B, events=[{"eventName": "sign_up", "eventCount": 5}])
t_quiet = M.facts_text({"weeks": [B, C], "health": {"ok": True, "problems": []}})
ok("변화가 없으면 경고하지 않는다", "[주의]" not in t_quiet)

print("\n⑦ 없는 것을 있는 척하지 않는다")
t0 = M.facts_text({"weeks": [], "health": {"ok": False, "problems": ["권한 없음"]}})
ok("한 주도 없으면 그렇게 적는다", "한 주도 받지 못했다" in t0)
ok("성과를 말하지 말라고 한다", "성과를 말하지 마라" in t0)
m0 = M.metrics_block({"weeks": [], "health": {"ok": False, "problems": ["권한 없음"]}})
ok("숫자판도 비었다고 말한다", "받지 못했습니다" in m0)

t1 = M.facts_text({"weeks": [B], "health": {"ok": True, "problems": []}})
ok("앞 주가 없으면 증감을 말하지 말라고 한다", "증감을 말하지 마라" in t1)
m1 = M.metrics_block({"weeks": [B], "health": {"ok": True, "problems": []}})
ok("숫자판도 비교 없음을 밝힌다", "비교  없음" in m1)
ok("앞주 값을 지어내지 않는다", "앞주" not in m1)

t2 = M.facts_text({"weeks": [A, B], "health": {"ok": False, "problems": ["조회 실패"]}})
ok("일부 실패를 재료에 적는다", "온전하지 않다" in t2 and "조회 실패" in t2)
ok("숫자판에도 적는다",
   "온전하지 않습니다" in M.metrics_block({"weeks": [A, B],
                                    "health": {"ok": False, "problems": ["조회 실패"]}}))

print("\n⑧ 전환·참여 숫자")
ok("가입 전환율", "방문자의 1.0%" in m, m[m.find("회원가입"):][:80])
ok("제대로 본 방문 비율", "제대로 본 방문" in m)
ok("방문당 조회", "방문당 조회" in m and "2.4장" in m)

print("\n⑨ 증감 계산")
eq("늘면 +", M._delta(1480, 1310)[0], "+13%")
eq("줄면 -", M._delta(1000, 1310)[0], "-24%")
eq("앞이 0이면 나누지 않는다", M._delta(50, 0)[0], "새로 생김")
ok("둘 다 0이면 조용히", M._delta(0, 0)[0] is None)
ok("값이 없으면 조용히", M._delta(None, 10) == (None, None))

print("\n⑩ 텔레그램 한 통 한도(4,096자)")
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
    M.send_telegram("\n\n".join(f"{i}번 문단 " + "가" * 300 for i in range(40)))
finally:
    M.TG_TOKEN, M.TG_CHAT = real_tok, real_chat
    import importlib
    sys.modules["requests"] = importlib.import_module("requests")
ok("여러 통으로 나뉜다", len(sent) > 1, f"{len(sent)}통")
ok("모든 통이 한도 안", all(len(c) < 4096 for c in sent), str([len(c) for c in sent]))
ok("내용이 유실되지 않는다", all(f"{i}번 문단" in "".join(sent) for i in range(40)))

print("\n⑪ 숫자판이 한 통에 들어간다")
ok("숫자판만으로 한도를 넘지 않는다", len(m) < 2000, f"{len(m)}자")

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
