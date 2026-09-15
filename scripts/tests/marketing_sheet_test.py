#!/usr/bin/env python3
"""marketing_sheet.py — 시트 없이 볼 수 있는 부분. 붙이는 쪽은 가짜 세션으로."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import marketing_sheet as S

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


A = wk("2026-08-24", "2026-08-30", 427, 400, 70, 551, 500, 1859, 120,
       pages=[{"pagePath": "/stock.html", "screenPageViews": 583, "totalUsers": 300},
              {"pagePath": "/Login.html", "screenPageViews": 240}],
       events=[{"eventName": "sign_up", "eventCount": 29}])
B = wk("2026-08-31", "2026-09-06", 382, 354, 55, 483, 420, 1136, 244,
       pages=[{"pagePath": "/stock.html", "screenPageViews": 481, "totalUsers": 330}],
       sources=[{"sessionSource": "m.search.naver.com", "sessions": 300},
                {"sessionSource": "naver", "sessions": 69},
                {"sessionSource": "google", "sessions": 3},
                {"sessionSource": "(direct)", "sessions": 77}],
       devices=[{"deviceCategory": "mobile", "totalUsers": 220},
                {"deviceCategory": "desktop", "totalUsers": 162}],
       events=[{"eventName": "sign_up", "eventCount": 4},
               {"eventName": "watchlist_add", "eventCount": 16}])
C = wk("2026-09-07", "2026-09-13", 444, 396, 76, 583, 480, 1260, 287,
       mau28=1200, wau7=444, dauAvg=63.4, stickiness=5.28,
       pages=[{"pagePath": "/stock.html", "screenPageViews": 900, "totalUsers": 387}],
       events=[{"eventName": "watchlist_add", "eventCount": 33, "totalUsers": 3},
               {"eventName": "sign_up", "eventCount": 4, "totalUsers": 3}])
DOC = {"weeks": [A, B, C], "retention": [
    {"week": "2026-08-24", "size": 400, "back": {"1": 12}},
    {"week": "2026-08-31", "size": 353, "back": {"1": 10}},
    {"week": "2026-09-07", "size": 396, "back": {"1": 4}},      # 몇 시간치 — 비워야 한다
]}
EXP = {"items": [
    {"id": "exp_1", "title": "버튼", "status": "제안됨", "metricLabel": "관심종목 담기",
     "baseValue": 16, "proposedAt": "2026-09-13", "startedWeek": None, "result": None,
     "why": "적어서", "action": "단다"},
    {"id": "exp_2", "title": "끝난 것", "status": "끝남", "metricLabel": "방문자 수",
     "baseValue": 400, "proposedAt": "2026-09-01", "startedWeek": "2026-09-07",
     "result": {"verdict": "변화 없음", "rule": "±10%", "now": 430, "pct": 7.5},
     "why": "w", "action": "a"},
]}
h = {name: i for i, name in enumerate(S.WEEK_HEAD)}

print("① 칸 이름은 사장의 말 — 낯선 말이 없고, 설명이 빠짐없이 있다")
for bad in ("발자국", "붙잡는 힘", "출렁임 %", "코호트", "세션", "전환"):
    ok(f"머리줄에 '{bad}' 가 없다", not any(bad in n for n in S.WEEK_HEAD))
ok("칸마다 단위가 붙어 있다 (명·회·건·%·날짜)",
   all(any(u in n for u in ("(명)", "(회)", "(건)", "(%)", "(±%)", "(초)", "(월)", "(일)"))
       for n in S.WEEK_HEAD), S.WEEK_HEAD)
ok("가입이 '완료' 인지 '페이지' 인지 이름에서 보인다", "가입 완료(건)" in S.WEEK_HEAD)
ok("건수와 사람 수가 따로 있다", "가입한 사람(명)" in S.WEEK_HEAD and "관심종목 담은 사람(명)" in S.WEEK_HEAD)
ok("칸마다 뜻이 적혀 있다", all(c[1] for c in S.WEEK_COLS), [c[0] for c in S.WEEK_COLS if not c[1]])
eq("이름이 겹치지 않는다", len(set(S.WEEK_HEAD)), len(S.WEEK_HEAD))

print("\n② 주간 줄 — 한 주가 한 줄, 오래된 것이 위")
rows = S.weekly_rows(DOC)
eq("머리줄 + 3주", len(rows), 4)
eq("머리줄", rows[0], S.WEEK_HEAD)
eq("첫 줄이 가장 오래된 주", rows[1][0], "2026-08-24")
eq("다시 온 사람 비율은 소수 한 자리", rows[2][h["다시 온 사람 비율(%)"]], 14.4)
eq("네이버는 조각을 합친 것", rows[2][h["네이버에서 온 방문(회)"]], 369)
eq("주소 직접", rows[2][h["주소 직접 친 방문(회)"]], 77)
eq("휴대폰 비율", rows[2][h["휴대폰으로 본 사람 비율(%)"]], 58)
eq("리포트 연 사람", rows[3][h["리포트 연 사람(명)"]], 387)
eq("우리가 본 조회 비율", rows[1][h["우리가 본 조회 비율(%)"]], 29)
ok("모든 줄의 칸 수가 머리줄과 같다", all(len(r) == len(S.WEEK_HEAD) for r in rows))

print("\n③ 건수와 사람 수")
eq("가입 완료 건수", rows[3][h["가입 완료(건)"]], 4)
eq("가입한 사람 수", rows[3][h["가입한 사람(명)"]], 3)
eq("담기 건수", rows[3][h["관심종목 담기(건)"]], 33)
eq("담은 사람 수 — 33건이 3명", rows[3][h["관심종목 담은 사람(명)"]], 3)
eq("옛 기록엔 사람 수가 없다 — 빈칸", (rows[2][h["가입한 사람(명)"]], rows[2][h["관심종목 담은 사람(명)"]]), ("", ""))

print("\n③-2 업계 표준 — MAU · DAU · 습관")
eq("지난 28일 동안 온 사람", rows[3][h["지난 28일 동안 온 사람(명)"]], 1200)
eq("하루 평균 온 사람", rows[3][h["하루 평균 온 사람(명)"]], 63.4)
eq("습관은 소수 한 자리", rows[3][h["한 달에 온 사람 중 하루에 오는 비율(%)"]], 5.3)
eq("안 받은 주는 빈칸", rows[2][h["지난 28일 동안 온 사람(명)"]], "")

print("\n④ 다음 주 다시 온 비율 — 가장 최근 주는 비운다")
k = h["처음 온 사람 중 다음 주 다시 온 비율(%)"]
eq("8/24 코호트", rows[1][k], 3)
eq("8/31 코호트", rows[2][k], 3)
eq("최근 주(9/7)는 몇 시간치라 빈칸", rows[3][k], "")

print("\n⑤ 없는 값은 빈칸 — null 을 보내지 않는다")
ok("None 이 하나도 없다", all(v is not None for row in rows for v in row))
eq("유입처가 없는 주는 빈칸", rows[1][h["네이버에서 온 방문(회)"]], "")
eq("4주 평균은 앞 주가 있어야", (rows[1][h["앞 4주 평균 방문자(명)"]], rows[3][h["앞 4주 평균 방문자(명)"]]), ("", 404.0))
eq("오르내리는 폭은 세 주부터", (rows[2][h["방문자가 보통 한 주에 오르내리는 폭(±%)"]],
                          rows[3][h["방문자가 보통 한 주에 오르내리는 폭(±%)"]] != ""), ("", True))

print("\n⑥ 실험 줄")
er = S.experiment_rows(EXP)
eq("머리줄 + 2건", len(er), 3)
eq("끝난 것은 판정·기준·결과가 붙는다", er[2][7:11], ["변화 없음", "±10%", 430, 7.5])
eq("제안만 된 것은 그 칸이 빈칸", er[1][7:11], ["", "", "", ""])
ok("실험 칸마다 뜻이 있다 (제안한 날은 이름이 곧 뜻)",
   all(what or name == "제안한 날" for name, what in S.EXP_COLS))

print("\n⑦ 설명 탭 — 주간 칸 전부와 실험 칸 전부")
ex = S.explain_rows()
names = [r[0] for r in ex]
ok("주간 칸이 빠짐없이 있다", all(n in names for n in S.WEEK_HEAD),
   [n for n in S.WEEK_HEAD if n not in names])
ok("실험 칸이 빠짐없이 있다", all(n in names for n in S.EXP_HEAD))
ok("가입 완료의 설명에 '페이지를 연 수가 아니다' 가 있다",
   any(r[0] == "가입 완료(건)" and "연 수가 아니" in r[3] for r in ex))
ok("메모 자리를 알려 준다", any("메모" in r[0] for r in ex))


class Fake:
    """시트 API 흉내. 부른 것을 적어 둔다."""
    def __init__(self, tabs=("주간",), fail=None):
        self.tabs, self.fail, self.calls = list(tabs), fail, []

    class R:
        def __init__(self, code, body=None, text=""):
            self.status_code, self._b, self.text = code, body or {}, text
        def json(self):
            return self._b

    def get(self, url, params=None):
        self.calls.append(("GET", url))
        if self.fail == "get":
            return self.R(403, text="The caller does not have permission")
        return self.R(200, {"sheets": [{"properties": {"title": t}} for t in self.tabs]})

    def post(self, url, json=None):
        self.calls.append(("POST", url, json))
        return self.R(200)

    def put(self, url, params=None, json=None):
        self.calls.append(("PUT", url, json))
        return self.R(200)


print("\n⑧ 붙이기 — 없는 탭은 만들고, 주간은 덮어쓰고, 실험·설명은 지우고 쓴다")
f = Fake(tabs=("주간",))
eq("됐다", S.push(f, "SID", DOC, EXP), 0)
posts = [c for c in f.calls if c[0] == "POST"]
made = [c for c in posts if "batchUpdate" in c[1]]
ok("실험·설명 탭을 만들었다", made and "실험" in str(made[0][2]) and "설명" in str(made[0][2]), made)
puts = [c for c in f.calls if c[0] == "PUT"]
eq("세 탭에 썼다", len(puts), 3)
ok("주간 줄이 갔다", puts[0][2]["values"][0] == S.WEEK_HEAD)
ok("한글 탭 이름을 주소에 맞게 바꿨다", "%EC%A3%BC%EA%B0%84" in puts[0][1], puts[0][1])
ok("주간 탭은 지우지 않는다 — 오른쪽 메모를 살린다",
   not any(":clear" in c[1] and "%EC%A3%BC%EA%B0%84" in c[1] for c in posts))
ok("설명 탭은 지우고 쓴다", any(":clear" in c[1] and "%EC%84%A4%EB%AA%85" in c[1] for c in posts))

print("\n⑨ 못 붙이면 1 로 끝난다 — 조용히 넘어가지 않는다")
g = Fake(fail="get")
eq("권한 없으면 1", S.push(g, "SID", DOC, EXP), 1)

print("\n⑩ 시크릿이 없으면 아무것도 안 하고 0")
os.environ.pop("MARKETING_SHEET_ID", None)
os.environ["KOSAI_GA4_DIR"] = tempfile.mkdtemp(prefix="sheet-test-")   # 저장소 밖
sys.argv = ["x"]
eq("0 으로 끝난다", S.main(), 0)

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
