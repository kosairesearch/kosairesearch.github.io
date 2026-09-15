#!/usr/bin/env python3
"""marketing_sheet.py — 시트 없이 볼 수 있는 부분. 붙이는 쪽은 가짜 세션으로."""
import os
import sys
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
       pages=[{"pagePath": "/stock.html", "screenPageViews": 900, "totalUsers": 387}],
       events=[{"eventName": "watchlist_add", "eventCount": 33}])
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

print("① 주간 줄 — 한 주가 한 줄, 오래된 것이 위")
rows = S.weekly_rows(DOC)
eq("머리줄 + 3주", len(rows), 4)
eq("머리줄", rows[0], S.WEEK_HEAD)
eq("첫 줄이 가장 오래된 주", rows[1][0], "2026-08-24")
h = {name: i for i, name in enumerate(S.WEEK_HEAD)}
eq("재방문율은 소수 한 자리 %", rows[2][h["재방문율 %"]], 14.4)
eq("네이버는 조각을 합친 것", rows[2][h["네이버"]], 369)
eq("주소 직접", rows[2][h["주소 직접"]], 77)
eq("휴대폰 몫", rows[2][h["휴대폰 %"]], 58)
eq("리포트 연 사람", rows[3][h["리포트 연 사람"]], 387)
eq("우리 발자국 %", rows[1][h["우리 발자국 %"]], 29)

print("\n② 붙잡는 힘 — 가장 최근 주는 비운다")
eq("8/24 코호트 1주 뒤", rows[1][h["붙잡는 힘 % (1주 뒤)"]], 3)
eq("8/31 코호트 1주 뒤", rows[2][h["붙잡는 힘 % (1주 뒤)"]], 3)
eq("최근 주(9/7)는 몇 시간치라 빈칸", rows[3][h["붙잡는 힘 % (1주 뒤)"]], "")

print("\n③ 없는 값은 빈칸 — null 을 보내지 않는다")
ok("None 이 하나도 없다", all(v is not None for row in rows for v in row))
eq("유입처가 없는 주는 빈칸", rows[1][h["네이버"]], "")
eq("가입이 없는 주는 빈칸", rows[3][h["회원가입"]], "")
# 9/7 줄의 4주 평균은 앞 두 주 (427+382)/2 = 404.5 → 반올림 404
eq("4주 평균은 앞 주가 있어야", (rows[1][h["4주 평균 방문자"]], rows[3][h["4주 평균 방문자"]]),
   ("", 404.0))
eq("출렁임은 세 주부터", (rows[2][h["흔한 출렁임 %"]], rows[3][h["흔한 출렁임 %"]] != ""), ("", True))

print("\n④ 실험 줄")
er = S.experiment_rows(EXP)
eq("머리줄 + 2건", len(er), 3)
eq("끝난 것은 판정·기준·결과가 붙는다", er[2][7:11], ["변화 없음", "±10%", 430, 7.5])
eq("제안만 된 것은 그 칸이 빈칸", er[1][7:11], ["", "", "", ""])


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


print("\n⑤ 붙이기 — 없는 탭은 만들고, 주간은 덮어쓰고, 실험은 지우고 쓴다")
f = Fake(tabs=("주간",))
eq("됐다", S.push(f, "SID", DOC, EXP), 0)
posts = [c for c in f.calls if c[0] == "POST"]
ok("실험 탭을 만들었다", any("batchUpdate" in c[1] and "실험" in str(c[2]) for c in posts), posts)
ok("실험 탭을 지웠다", any(":clear" in c[1] for c in posts))
puts = [c for c in f.calls if c[0] == "PUT"]
eq("두 탭에 썼다", len(puts), 2)
ok("주간 줄이 갔다", puts[0][2]["values"][0] == S.WEEK_HEAD)
ok("한글 탭 이름을 주소에 맞게 바꿨다", "%EC%A3%BC%EA%B0%84" in puts[0][1], puts[0][1])
ok("주간 탭은 지우지 않는다 — 오른쪽 메모를 살린다",
   not any(":clear" in c[1] and "%EC%A3%BC%EA%B0%84" in c[1] for c in posts))

print("\n⑥ 못 붙이면 1 로 끝난다 — 조용히 넘어가지 않는다")
g = Fake(fail="get")
eq("권한 없으면 1", S.push(g, "SID", DOC, EXP), 1)

print("\n⑦ 시크릿이 없으면 아무것도 안 하고 0")
os.environ.pop("MARKETING_SHEET_ID", None)
import tempfile
os.environ["KOSAI_GA4_DIR"] = tempfile.mkdtemp(prefix="sheet-test-")   # 저장소 밖
sys.argv = ["x"]
eq("0 으로 끝난다", S.main(), 0)

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
