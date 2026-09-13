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

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
