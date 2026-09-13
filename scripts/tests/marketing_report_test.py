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

print("\n⑫ 행동 — 손님이 무엇을 했나")
BEH = wk("2026-09-07", "2026-09-13", 400, 350, 50, 500, 400, 1200, 200,
         pages=PAGES_B,
         events=[{"eventName": "sign_up", "eventCount": 6}],
         tickers=[{"eventName": "stock_click", "customEvent:ticker": "005930",
                   "eventCount": 18},
                  {"eventName": "stock_click", "customEvent:ticker": "000660",
                   "eventCount": 11},
                  {"eventName": "stock_click", "customEvent:ticker": "(not set)",
                   "eventCount": 99},
                  {"eventName": "page_view", "customEvent:ticker": "005930",
                   "eventCount": 500}],
         scroll=[{"customEvent:percent": "25", "eventCount": 200},
                 {"customEvent:percent": "50", "eventCount": 150},
                 {"customEvent:percent": "100", "eventCount": 60},
                 {"customEvent:percent": "(not set)", "eventCount": 7}],
         entrySource=[{"customEvent:entry_source": "naver", "eventCount": 300},
                      {"customEvent:entry_source": "direct", "eventCount": 100}],
         signupSource=[{"customEvent:entry_source": "naver", "eventCount": 6}],
         signupPage=[{"customEvent:from_page": "/stock.html", "eventCount": 5},
                     {"customEvent:from_page": "/Home.html", "eventCount": 1}],
         landings=[{"landingPage": "/stock.html", "sessions": 300,
                    "bounceRate": 0.72},
                   {"landingPage": "/", "sessions": 100, "bounceRate": 0.31}],
         leave=[{"customEvent:from_page": "/stock.html", "eventCount": 280}],
         byVisitor=[{"newVsReturning": "returning", "pagePath": "/brief.html",
                     "screenPageViews": 90},
                    {"newVsReturning": "new", "pagePath": "/stock.html",
                     "screenPageViews": 400},
                    {"newVsReturning": "returning", "pagePath": "/Admin.html",
                     "screenPageViews": 300}])

tk = M.top_tickers(BEH)
eq("종목 이름표를 붙인다", tk[0], ("삼성전자", 18))
eq("큰 순서", [n for n, _ in tk], ["삼성전자", "SK하이닉스"])
ok("stock_click 이 아닌 줄은 안 센다", all(c != 500 for _, c in tk))
ok("(not set) 은 버린다", all(n != "(not set)" for n, _ in tk))
eq("행동 자료가 없으면 빈 목록", M.top_tickers(A), [])

eq("끝까지 읽은 비율 = 100÷25", M.read_through(BEH), (30, 200, 60))
eq("25 가 없으면 못 잰다", M.read_through(A), None)
eq("숫자가 아닌 칸은 버린다",
   M.read_through(wk("x", "y", 1, 1, 1, 1, 1, 1, 1,
                     scroll=[{"customEvent:percent": "25", "eventCount": 10},
                             {"customEvent:percent": "(not set)",
                              "eventCount": 999}])), (0, 10, 0))

fn = M.source_funnel(BEH)
eq("유입처 이름을 옮긴다", fn[0][0], "네이버")
eq("들어옴·가입·전환율", (fn[0][1], fn[0][2], round(fn[0][3], 1)), (300, 6, 2.0))
eq("가입이 없는 유입처는 0", (fn[1][0], fn[1][2]), ("주소 직접·즐겨찾기", 0))

bv = M.by_visitor(BEH)
eq("재방문이 본 콘텐츠", bv["재방문"], [("모닝 브리핑", 90)])
eq("신규가 본 콘텐츠", bv["신규"], [("종목 리포트", 400)])
ok("관리자 페이지는 취향이 아니다",
   all("관리자" not in n for n, _ in bv["재방문"]))

ok("행동 자료가 있는지 안다", M.has_behavior(BEH) and not M.has_behavior(A))

mb = M.metrics_block({"weeks": [B, BEH], "health": {"ok": True}})
ok("숫자판에 종목 이름이 나온다", "삼성전자 18회" in mb, mb)
ok("숫자판에 완독 비율이 나온다", "끝까지 읽음" in mb and "30%" in mb, mb)
ok("이름표와 숫자가 달라붙지 않는다", "끝까지 읽음 " in mb, mb)
eq("칸보다 긴 이름도 한 칸은 띄운다", M._pad("아주아주긴이름표입니다", 4),
   "아주아주긴이름표입니다 ")
ok("완독 비율의 분모를 밝힌다", "내려 읽기 시작" in mb, mb)
mb0 = M.metrics_block(GOOD)
ok("행동 자료가 없으면 왜 없는지 말한다",
   "손님이 무엇을 봤나" in mb0 and "아직 쌓이지 않았습니다" in mb0, mb0)
ok("자료가 있으면 그 말을 하지 않는다", "아직 쌓이지 않았습니다" not in mb, mb)

eq("(not set) 은 사람 말로 바꾼다", M.page_label("(not set)"), "어딘지 기록 안 됨")
eq("빈 값도 마찬가지", M.page_label(""), "어딘지 기록 안 됨")
eq("아는 주소는 이름표를", M.page_label("/stock.html"), "종목 리포트")
eq("물음표 뒤는 떼고 본다", M.page_label("/stock.html?ticker=005930"), "종목 리포트")
eq("모르는 주소는 그대로", M.page_label("/새페이지.html"), "/새페이지.html")

NOTSET = wk("2026-09-07", "2026-09-13", 10, 9, 1, 10, 5, 20, 30, pages=PAGES_B,
            signupPage=[{"customEvent:from_page": "(not set)", "eventCount": 4}])
ok("재료에도 영어가 그대로 안 나간다",
   "(not set)" not in M.facts_text({"weeks": [NOTSET]}),
   M.facts_text({"weeks": [NOTSET]}))

ft = M.facts_text({"weeks": [B, BEH], "health": {"ok": True}})
for want in ("가장 많이 눌린 종목", "얼마나 내려 읽나", "유입처별 들어옴 → 가입",
             "어느 페이지에서 가입을 눌렀나", "처음 열린 페이지",
             "어느 페이지에서 떠났나", "누가 무엇을 보나"):
    ok(f"재료에 '{want}' 가 있다", want in ft)
ok("그냥 나간 비율을 %로 적는다", "그냥 나감 72%" in ft, ft)
ok("완독률을 방문자로 나누지 말라고 일러 준다", "방문자 수로 나눠 말하지 마라" in ft)
ok("행동 자료가 없으면 그 칸을 안 만든다",
   "가장 많이 눌린 종목" not in M.facts_text(GOOD))

MISS = wk("2026-09-07", "2026-09-13", 10, 9, 1, 10, 5, 20, 30,
          pages=PAGES_B, _missing={"scroll": "400 …", "tickers": "400 …"})
ok("못 받은 것은 못 받았다고 적는다",
   "[못 받은 행동 자료]" in M.facts_text({"weeks": [MISS]}))
ok("못 받은 것을 0 으로 말하지 말라고 일러 준다",
   "0 이었다고 말하지 마라" in M.facts_text({"weeks": [MISS]}))

print("\n⑫-2 한 곳에서 온 것은 묶어서 센다")
# 2026-09-13 에 실제로 이렇게 흩어져 왔다.
SPLIT = wk("2026-09-07", "2026-09-13", 400, 350, 50, 484, 400, 1200, 200,
           pages=PAGES_B,
           sources=[{"sessionSource": s, "sessions": n} for s, n in [
               ("m.search.naver.com", 228), ("naver", 141),
               ("(direct)", 77), ("nid.naver.com", 15), ("chatgpt.com", 7),
               ("ntp.msn.com", 4), ("google", 3), ("kauth.kakao.com", 2),
               ("link.naver.com", 2), ("m.keep.naver.com", 2)]],
           entrySource=[{"customEvent:entry_source": "(not set)",
                         "eventCount": 485}],
           signupSource=[{"customEvent:entry_source": "(not set)",
                          "eventCount": 4}])
import ga4_data as GD
rows = dict(M.labeled(SPLIT, "sources", "sessionSource", "sessions",
                      GD.source_label))
eq("네이버가 한 줄로 묶인다", rows["네이버"], 228 + 141 + 2 + 2)
eq("로그인은 따로 샌다", rows["로그인하고 돌아옴"], 15 + 2)
ok("네이버가 가장 큰 곳으로 보인다",
   max(rows, key=rows.get) == "네이버", rows)
eq("묶은 합이 원래 합과 같다", sum(rows.values()), 481)

ft2 = M.facts_text({"weeks": [SPLIT]})
ok("재료에 묶인 숫자가 나온다", "네이버: 373" in ft2, ft2)
ok("숫자 줄에 날주소가 그대로 나가지 않는다",
   "m.search.naver.com: " not in ft2 and "nid.naver.com: " not in ft2, ft2)
ok("로그인 되돌아온 것을 유입으로 세지 말라고 일러 준다",
   "유입으로 세지 마라" in ft2, ft2)
ok("전부 '알 수 없음' 이면 전환율을 말하지 않는다",
   "아직 가를 수 없다" in ft2 and "알 수 없음: 들어옴" not in ft2, ft2)

print("\n⑬ 실험 제안 블록")
BODY = "■ 한 줄로 말하면\n좋았다.\n"
GOTTEXT = BODY + "<<실험제안>>\n제목: 가입 버튼\n이유: 가입이 적다\n" \
                 "할일: 버튼을 넣는다\n지표: signUpRate\n<<끝>>"
rest, got = M.take_proposal(GOTTEXT)
eq("본문만 남는다", rest, BODY.strip())
eq("제목을 읽는다", got["제목"], "가입 버튼")
eq("지표를 읽는다", got["지표"], "signUpRate")
ok("꺾쇠가 보고서에 남지 않는다", "<<" not in rest)

rest2, got2 = M.take_proposal(BODY)
eq("블록이 없으면 글 그대로", rest2, BODY.strip())
eq("블록이 없으면 제안도 없다", got2, None)

rest3, got3 = M.take_proposal(BODY + "<<실험제안>>\n제목: 반쪽\n<<끝>>")
eq("칸이 빠지면 버린다", got3, None)
ok("버려도 본문은 살린다", rest3 == BODY.strip())

rest4, got4 = M.take_proposal(BODY + "<< 실험제안 >>\n제목: ㄱ\n이유: ㄴ\n"
                                     "할일: ㄷ\n지표: users\n<< 끝 >>")
ok("꺾쇠 안 띄어쓰기를 봐준다", got4 is not None and got4["지표"] == "users")

BLK = "<<실험제안>>\n제목: {}\n이유: ㄴ\n할일: ㄷ\n지표: users\n<<끝>>\n"
rest5, got5 = M.take_proposal(BODY + BLK.format("첫째") + BLK.format("둘째"))
eq("두 번 붙여 보내면 첫 것만 읽는다", got5["제목"], "첫째")
ok("두 번째 블록도 본문에서 지운다", "<<" not in rest5 and "둘째" not in rest5, rest5)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import experiments as X

EXP = {"items": [
    {"id": "exp_1", "title": "끝난 것", "status": "끝남",
     "metricLabel": "가입 전환율(%)",
     "result": {"verdict": "효과 있음", "base": 0.9, "now": 1.4, "pct": 55.6}},
    {"id": "exp_2", "title": "하는 중", "status": "진행중",
     "metricLabel": "방문자 수", "baseValue": 382},
    {"id": "exp_3", "title": "안 한 것", "status": "제안됨",
     "metricLabel": "방문자 수", "baseValue": 382},
]}
FRESH0 = {"id": "exp_4", "title": "새것", "why": "왜", "action": "함",
          "metricLabel": "가입 건수", "baseValue": 6}
blk = M.exp_block(EXP, None, [EXP["items"][0]])
ok("끝난 실험의 판정을 적는다", "[끝남 · 효과 있음]" in blk, blk)
ok("하는 중을 적는다", "[하는 중] 하는 중" in blk, blk)
ok("안 한 것의 번호를 적는다", "exp_3" in blk, blk)
ok("어떻게 표시하는지 알려 준다", "Run workflow" in blk, blk)
ok("번호가 하나면 '중 하나를' 이라고 하지 않는다",
   "중 하나를" not in M.exp_block({"items": [EXP["items"][2]]}), blk)
ok("번호가 여럿이면 고르라고 한다",
   "중 하나를" in M.exp_block(EXP, FRESH0, []), blk)
eq("대장이 비면 칸을 안 만든다", M.exp_block({"items": []}), "")

FRESH = {"id": "exp_4", "title": "새것", "why": "왜냐면", "action": "이걸 한다",
         "metricLabel": "가입 건수", "baseValue": 6}
blk2 = M.exp_block(EXP, FRESH, [])
ok("새 제안에 할 일이 적힌다", "이걸 한다" in blk2, blk2)
ok("새 제안에 볼 지표가 적힌다", "가입 건수" in blk2, blk2)

d0 = {"items": []}
w0 = dict(BEH)
it, why = X.propose(d0, "ㄱ", "ㄴ", "signUp", "ㄷ", w0)
eq("제안이 대장에 올라간다", (it["id"], it["baseValue"]), ("exp_1", 6))
eq("같은 제목은 두 번 안 올라간다", X.propose(d0, "ㄱ", "x", "users", "y", w0)[0], None)
eq("모르는 지표는 안 올라간다", X.propose(d0, "ㄴ", "x", "몰라", "y", w0)[0], None)

d0["items"][0]["status"] = "진행중"
d0["items"][0]["startedWeek"] = "2026-08-31"
d0["items"][0]["baseValue"] = 4
done = X.review(d0, [B, BEH])
eq("시작한 다음 주부터 판정한다", (done[0]["result"]["verdict"], done[0]["status"]),
   ("효과 있음", "끝남"))
eq("판정한 것은 다시 판정하지 않는다", X.review(d0, [B, BEH]), [])

d1 = {"items": [{"id": "exp_9", "title": "x", "status": "진행중",
                 "metric": "users", "metricLabel": "방문자 수",
                 "baseValue": 400, "startedWeek": "2026-09-07"}]}
eq("시작한 그 주에는 판정하지 않는다", X.review(d1, [B, BEH]), [])

print("\n⑬-2 채팅창 규칙과 텔레그램 규칙이 섞이지 않았나")
# 한 번 섞였다. 텔레그램은 표가 깨지니까 '표를 그리지 마라' 인데,
# 그걸 채팅창 담당에게도 복사해 놓아서 사장이 줄글을 받았다.
SKILL = Path(__file__).resolve().parent.parent.parent / ".claude/skills/마케팅/SKILL.md"
ok("마케팅 담당 설명서가 있다", SKILL.exists(), str(SKILL))
if SKILL.exists():
    sk = SKILL.read_text(encoding="utf-8")
    ok("채팅창에서는 표를 쓰라고 한다", "표가 먼저다" in sk)
    ok("채팅창에 '표를 그리지 마라' 가 들어가 있지 않다",
       "표를 그리지 마라" not in sk)
    ok("텔레그램은 다르다고 못 박아 뒀다", "텔레그램으로 가는" in sk)
    ok("숫자 칸 오른쪽 정렬을 일러 준다", "---:" in sk)
    ok("'됐는지 아는 법' 에 선을 적으라고 한다", "30회를 넘으면" in sk)
    ok("도구가 준 것을 그대로 붙이지 말라고 한다",
       "그대로 붙이지 마라" in sk)
    ok("report 가 텔레그램용 줄글이라고 일러 준다",
       "텔레그램으로 보낸 줄글 원문" in sk)
    ok("성과를 물으면 weekly 를 부르라고 한다",
       "어느 도구를 부를지" in sk and "`weekly`" in sk)
ok("텔레그램 보고에는 표를 그리지 말라고 남아 있다",
   "표를 그리지 마라" in M.PROMPT)
ok("텔레그램 보고는 줄글 대신 짧은 줄로 쓰게 한다",
   "문단으로 쓰지 마라" in M.PROMPT)

print("\n⑭ 보고서 한 바퀴 — 판정 → 글 → 제안 → 저장 (모델은 가짜)")
import contextlib
import io
import os
import tempfile

# 진짜 Firestore 도 저장소의 data/ga4 도 건드리지 않는다.
os.environ["KOSAI_GA4_DIR"] = tempfile.mkdtemp(prefix="report-loop-")
os.environ.pop("GCP_SA_KEY", None)
os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
os.environ.pop("GITHUB_STEP_SUMMARY", None)      # CI 요약을 더럽히지 않는다
import ga4_store
import experiments as X2

ga4_store.save("weekly", {"weeks": [A, B], "health": {"ok": True, "problems": []}})


class FakeUsage:
    input_tokens, output_tokens = 3000, 1000


SAID = ("■ 한 줄로 말하면\n  손님은 늘었습니다.\n\n"
        "■ 다음 주에 할 것\n  가입 버튼을 넣습니다.\n\n"
        "<<실험제안>>\n제목: 리포트에 가입 버튼\n이유: 리포트는 481회 보는데 가입이 4건\n"
        "할일: stock.html 본문 끝에 버튼을 넣는다\n지표: signUpRate\n<<끝>>")
_real_generate = M.generate
M.generate = lambda prompt: (SAID, FakeUsage())
sys.argv = ["marketing_report.py"]

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    rc = M.main()
out = buf.getvalue()
eq("정상으로 끝난다", rc, 0)
ok("숫자판이 맨 앞", out.startswith("📊 KOSAI 주간 성과 보고"), out[:60])
ok("모델 해설이 가운데", "손님은 늘었습니다" in out)
ok("실험 대장이 맨 뒤", out.rstrip().rsplit("■", 1)[-1].startswith(" 실험 대장"), out[-300:])
ok("꺾쇠가 사장 화면에 안 나간다", "<<" not in out, out[-300:])
ok("새 제안이 보고서에 적힌다", "[새 제안] exp_1" in out, out[-400:])
ok("어떻게 표시하는지 알려 준다", "Run workflow" in out)

saved = ga4_store.load("reports", {"items": []})
eq("보고서가 저장된다", len(saved.get("items") or []), 1)
eq("저장된 글이 화면과 같다", saved["items"][0]["text"].strip(), out.strip())
eq("어느 주 것인지 적힌다", saved["items"][0]["week"], B["week"])

led = X2.load()
eq("제안이 대장에 올라간다", len(led["items"]), 1)
eq("아직 실행 전이다", led["items"][0]["status"], "제안됨")
eq("시작값을 지난주 값으로 잡는다", led["items"][0]["baseValue"],
   X2.value_of(B, "signUpRate"))

# 같은 주에 또 돌려도 제안이 겹쳐 쌓이지 않는다
with contextlib.redirect_stdout(io.StringIO()):
    M.main()
eq("같은 제안이 두 번 안 쌓인다", len(X2.load()["items"]), 1)
eq("보고서도 같은 주 것은 하나만", len(ga4_store.load("reports")["items"]), 1)

# 사장이 '했다'고 표시하고, 다음 주 숫자가 들어오면 판정된다
led = X2.load()
led["items"][0]["status"] = "진행중"
led["items"][0]["startedWeek"] = B["week"]
led["items"][0]["baseValue"] = 1.0
X2.save(led)

NEXT = wk("2026-09-07", "2026-09-13", 500, 420, 80, 600, 500, 1500, 240,
          pages=PAGES_B, events=[{"eventName": "sign_up", "eventCount": 20}])
ga4_store.save("weekly", {"weeks": [A, B, NEXT], "health": {"ok": True}})
M.generate = lambda prompt: ("■ 한 줄로 말하면\n  효과가 있었습니다.", FakeUsage())
buf2 = io.StringIO()
with contextlib.redirect_stdout(buf2):
    M.main()
out2 = buf2.getvalue()
led = X2.load()
eq("다음 주에 판정된다", led["items"][0]["status"], "끝남")
eq("효과를 재서 적는다", led["items"][0]["result"]["verdict"], "효과 있음")
ok("보고서에 결과가 보인다", "[끝남 · 효과 있음]" in out2, out2[-400:])
ok("재료에도 실려 모델이 짚을 수 있다",
   "실험 대장" in M.build_prompt(ga4_store.load("weekly"), X2.load()))
M.generate = _real_generate

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
