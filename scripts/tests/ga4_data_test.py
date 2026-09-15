#!/usr/bin/env python3
"""ga4_data.py — 네트워크 없이 볼 수 있는 부분만 시험한다."""
import datetime
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ga4_data as G

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


print("① 주 경계 — 월요일에 시작하고, 안 끝난 주는 넣지 않는다")
# 2026-09-14 는 월요일. 직전 완결 주는 09-07(월)~09-13(일).
w = G.week_bounds(datetime.date(2026, 9, 14), 1)
eq("월요일에 물으면 직전 주 월~일", (w[0][0].isoformat(), w[0][1].isoformat()),
   ("2026-09-07", "2026-09-13"))
# 2026-09-13 은 일요일. 그 주는 오늘 끝나므로 아직 완결이 아니다.
w = G.week_bounds(datetime.date(2026, 9, 13), 1)
eq("일요일에 물어도 그 주는 빼고 앞 주", (w[0][0].isoformat(), w[0][1].isoformat()),
   ("2026-08-31", "2026-09-06"))
w = G.week_bounds(datetime.date(2026, 9, 16), 1)      # 수요일
eq("주중에 물어도 직전 완결 주", (w[0][0].isoformat(), w[0][1].isoformat()),
   ("2026-09-07", "2026-09-13"))

print("\n② 여러 주 — 겹치지 않고 비지 않고 오래된 것이 앞")
w = G.week_bounds(datetime.date(2026, 9, 14), 8)
eq("요청한 만큼 나온다", len(w), 8)
ok("오래된 것이 앞", w[0][0] < w[-1][0])
ok("모두 월요일 시작", all(m.weekday() == 0 for m, _ in w))
ok("모두 일요일 끝", all(s.weekday() == 6 for _, s in w))
ok("한 주는 정확히 7일", all((s - m).days == 6 for m, s in w))
gaps = [(w[i + 1][0] - w[i][1]).days for i in range(len(w) - 1)]
ok("주 사이에 틈도 겹침도 없다", all(g == 1 for g in gaps), str(gaps))

print("\n③ 어느 요일에 돌려도 깨지지 않는다 (1년 전부)")
bad = []
d = datetime.date(2026, 1, 1)
while d < datetime.date(2027, 1, 1):
    ws = G.week_bounds(d, 4)
    if len(ws) != 4 or any((s - m).days != 6 for m, s in ws):
        bad.append(d.isoformat())
    if ws[-1][1] >= d:                 # 끝난 주만 나와야 한다
        bad.append(f"{d} 미완결주 포함")
    d += datetime.timedelta(days=1)
ok("365일 모두 정상", not bad, str(bad[:3]))

print("\n④ 기록 합치기 — 옛 주를 지우지 않는다")
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "weekly.json"
    G.merge_save({"weeks": [{"week": "2026-08-31", "users": 10},
                            {"week": "2026-09-07", "users": 20}]}, p)
    n = G.merge_save({"weeks": [{"week": "2026-09-07", "users": 22},
                                {"week": "2026-09-14", "users": 30}]}, p)
    saved = json.loads(p.read_text(encoding="utf-8"))["weeks"]
    eq("주 개수가 합쳐진다", n, 3)
    eq("옛 주가 남아 있다", saved[0]["week"], "2026-08-31")
    eq("날짜 순으로 정렬된다", [x["week"] for x in saved],
       ["2026-08-31", "2026-09-07", "2026-09-14"])
    eq("같은 주는 새 값으로 덮인다", saved[1]["users"], 22)

    # 파일이 깨져 있어도 이번 것은 저장돼야 한다
    p.write_text("{망가진 파일", encoding="utf-8")
    n = G.merge_save({"weeks": [{"week": "2026-09-21", "users": 40}]}, p)
    eq("깨진 파일이어도 새로 쓴다", n, 1)

print("\n④-2 합칠 때 옛 주의 자세한 것을 지우지 않는다")
# 2026-09-15. 매주 최근 두 주만 자세히 받는데 _merge 가 통째로 덮어서,
# 3주 전부터의 유입처·기기·사람 수가 매주 지워지고 있었다.
deep_old = {"weeks": [{"week": "2026-08-24", "to": "2026-08-30", "users": 427,
                       "sources": [{"sessionSource": "naver", "sessions": 300}],
                       "devices": [{"deviceCategory": "mobile", "totalUsers": 250}],
                       "_missing": {"tickers": "400"}}]}
shallow_new = {"weeks": [{"week": "2026-08-24", "to": "2026-08-30", "users": 430}]}
m2 = G._merge(deep_old, shallow_new)
eq("숫자는 새것으로", m2["weeks"][0]["users"], 430)
ok("유입처는 남는다", m2["weeks"][0].get("sources") == deep_old["weeks"][0]["sources"])
ok("기기도 남는다", "devices" in m2["weeks"][0])
deep_new = {"weeks": [{"week": "2026-08-24", "to": "2026-08-30", "users": 431,
                       "sources": [{"sessionSource": "google", "sessions": 5}]}]}
m3 = G._merge(deep_old, deep_new)
eq("새 기록에 자세한 것이 있으면 그것이 이긴다",
   m3["weeks"][0]["sources"], deep_new["weeks"][0]["sources"])
ok("새 기록에 없는 칸은 여전히 옛것", "devices" in m3["weeks"][0])
m4 = G._merge({}, shallow_new)
eq("옛 기록이 없으면 그냥 들어간다", m4["weeks"][0]["users"], 430)

print("\n⑤ 열쇠가 없으면 — 조용히 0 을 돌려주지 않는다")
import os
_save = {k: os.environ.pop(k, None) for k in ("GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS")}
try:
    doc = G.collect(weeks=2)
    ok("건강 기록이 실패라고 말한다", doc["health"]["ok"] is False, str(doc["health"]))
    ok("이유를 적어 준다", bool(doc["health"].get("note") or doc["health"].get("problems")),
       str(doc["health"]))
    eq("주 목록은 비어 있다", doc["weeks"], [])
finally:
    for k, v in _save.items():
        if v is not None:
            os.environ[k] = v

print("\n⑥ 페이지 이름표")
ok("홈은 두 주소 다 같은 이름", G.PAGE_NAMES["/"] == G.PAGE_NAMES["/index.html"])
ok("브리핑 이름이 있다", G.PAGE_NAMES.get("/brief.html") == "모닝 브리핑")

print("\n⑦ 유입처 이름 묶기 — 2026-09-13 에 실제로 나온 줄들")
eq("네이버 검색(모바일)", G.source_label("m.search.naver.com"), "네이버")
eq("네이버 (GA4 가 주는 짧은 이름)", G.source_label("naver"), "네이버")
eq("네이버 링크", G.source_label("link.naver.com"), "네이버")
eq("네이버 킵", G.source_label("m.keep.naver.com"), "네이버")
ok("네이버 로그인은 유입이 아니다",
   G.source_label("nid.naver.com") == "로그인하고 돌아옴")
ok("카카오 로그인도 마찬가지",
   G.source_label("kauth.kakao.com") == "로그인하고 돌아옴")
eq("직접 들어옴", G.source_label("(direct)"), "주소 직접·즐겨찾기")
eq("챗GPT", G.source_label("chatgpt.com"), "챗GPT")
eq("MSN 새 탭", G.source_label("ntp.msn.com"), "MSN")
eq("구글", G.source_label("google"), "구글")
eq("www. 는 떼고 본다", G.source_label("www.naver.com"), "네이버")
eq("빈 값은 알 수 없음", G.source_label(""), "알 수 없음")
eq("(not set) 도 알 수 없음", G.source_label("(not set)"), "알 수 없음")
eq("모르는 곳은 그대로", G.source_label("blog.example.kr"), "blog.example.kr")
ok("네이버를 가리키는 주소가 카카오로 새지 않는다",
   G.source_label("naver.com.evil.kr") == "naver.com.evil.kr")
ok("AI 챗봇 갈래에 이름표가 있다",
   G.CHANNEL_NAMES.get("AI Assistant") is not None)

print("\n⑧ Firestore 가 받는 모양 — 표의 열쇠는 글자여야 한다")
# 2026-09-14 사고. 코호트의 '몇 주째' 가 숫자 열쇠라 문서 전체가
# 거절당했고, 지난주 숫자가 통째로 안 쌓였다. 그런데도 단계는 성공으로
# 끝나서 보고가 지지난주 숫자를 '지난주' 라고 말했다.
import ga4_store as S


def all_keys_str(v):
    if isinstance(v, dict):
        return all(isinstance(k, str) for k in v) and all(
            all_keys_str(x) for x in v.values())
    if isinstance(v, list):
        return all(all_keys_str(x) for x in v)
    return True


messy = {"retention": [{"week": "2026-09-07", "size": 10,
                        "back": {1: 3, 2: 1}}],
         "weeks": [{"week": "2026-09-07", "deep": {3: {4: "x"}}}]}
ok("숫자 열쇠가 있으면 걸러내기 전에는 어긋나 있다", not all_keys_str(messy))
ok("_map_safe 를 거치면 모든 열쇠가 글자다", all_keys_str(S._map_safe(messy)))
eq("값은 그대로 둔다", S._map_safe(messy)["retention"][0]["back"]["1"], 3)
eq("깊은 곳도 바꾼다", S._map_safe(messy)["weeks"][0]["deep"]["3"]["4"], "x")

print("\n⑨ 저장이 실패하면 --check 가 알아채야 한다")
_load, _save = S.load, S.save
try:
    S.load = lambda name, default=None: {}
    S.save = lambda name, doc: "failed:data/ga4/weekly.json"
    doc = {"weeks": [{"week": "2026-09-07"}],
           "health": {"ok": True, "problems": []}}
    G.merge_save(doc)
    ok("건강 기록이 '문제 있음' 으로 바뀐다", doc["health"]["ok"] is False)
    ok("무엇이 문제인지 적힌다",
       any("Firestore" in x for x in doc["health"]["problems"]),
       doc["health"]["problems"])

    S.save = lambda name, doc: "firestore"
    doc2 = {"weeks": [{"week": "2026-09-07"}],
            "health": {"ok": True, "problems": []}}
    G.merge_save(doc2)
    ok("잘 들어갔으면 건드리지 않는다", doc2["health"]["ok"] is True)

    # 내 컴퓨터에서 시험할 때(열쇠 없음)는 파일로 떨어져도 정상이다.
    S.save = lambda name, doc: "local:data/ga4/weekly.json"
    doc3 = {"weeks": [{"week": "2026-09-07"}],
            "health": {"ok": True, "problems": []}}
    G.merge_save(doc3)
    ok("열쇠가 없어 파일에 둔 것은 실패가 아니다", doc3["health"]["ok"] is True)
finally:
    S.load, S.save = _load, _save

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
