#!/usr/bin/env python3
"""marketing_mcp.py — 클로드가 실제로 말을 거는 그대로 시험한다.

함수만 불러 보는 것으로는 모자라다. 규약을 직접 구현했으므로, 진짜로
프로세스를 띄워서 stdin/stdout 으로 JSON 을 주고받아 봐야 한다.
여기서 통과하면 클로드 설정에 붙여도 된다.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SERVER = ROOT / "scripts" / "marketing_mcp.py"
sys.path.insert(0, str(ROOT / "scripts"))

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


# ── 시험용 숫자. 진짜 Firestore 를 건드리지 않도록 임시 폴더에 둔다 ──
WEEKS = []
for w, to, u, n, r in [("2026-08-24", "2026-08-30", 427, 400, 70),
                       ("2026-08-31", "2026-09-06", 382, 354, 55),
                       ("2026-09-07", "2026-09-13", 400, 350, 50)]:
    WEEKS.append({
        "week": w, "to": to, "users": u, "newUsers": n, "returningUsers": r,
        "sessions": 500, "engagedSessions": 400, "pageViews": 1200,
        "avgSessionSec": 200,
        "pages": [{"pagePath": "/stock.html", "screenPageViews": 481},
                  {"pagePath": "/Admin.html", "screenPageViews": 16}],
        "events": [{"eventName": "sign_up", "eventCount": 6}],
        "channels": [{"sessionDefaultChannelGroup": "Organic Search",
                      "sessions": 300}],
        "sources": [{"sessionSource": "naver", "sessions": 220}],
        "tickers": [{"eventName": "stock_click",
                     "customEvent:ticker": "005930", "eventCount": 18}],
        "scroll": [{"customEvent:percent": "25", "eventCount": 200},
                   {"customEvent:percent": "100", "eventCount": 60}],
        "entrySource": [{"customEvent:entry_source": "naver", "eventCount": 220}],
        "signupSource": [{"customEvent:entry_source": "naver", "eventCount": 5}],
        "landings": [{"landingPage": "/stock.html", "sessions": 300,
                      "bounceRate": 0.72}],
        "leave": [{"customEvent:from_page": "/stock.html", "eventCount": 280}],
        "byVisitor": [{"newVsReturning": "returning", "pagePath": "/brief.html",
                       "screenPageViews": 90}],
    })

BOX = tempfile.mkdtemp(prefix="mcp-test-")
(Path(BOX) / "weekly.json").write_text(
    json.dumps({"weeks": WEEKS, "health": {"ok": True, "problems": []}},
               ensure_ascii=False), encoding="utf-8")
(Path(BOX) / "reports.json").write_text(
    json.dumps({"items": [{"week": "2026-09-07", "to": "2026-09-13",
                           "text": "지난주 보고서 원문입니다."}]},
               ensure_ascii=False), encoding="utf-8")

# 열쇠를 빼고 KOSAI_GA4_DIR 로 임시 폴더를 가리킨다. 그래야 진짜
# Firestore 도, 저장소의 data/ga4 도 건드리지 않는다.
def env_for(box):
    e = dict(os.environ)
    for k in ("GCP_SA_KEY", "GOOGLE_APPLICATION_CREDENTIALS", "GA4_PROPERTY_ID"):
        e.pop(k, None)
    e["KOSAI_GA4_DIR"] = box
    return e


ENV = env_for(BOX)


class Server:
    env = ENV

    def __enter__(self):
        self.p = subprocess.Popen([sys.executable, str(SERVER)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, bufsize=1,
                                  env=self.env, cwd=str(ROOT))
        return self

    def __exit__(self, *a):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()

    def send(self, **obj):
        obj.setdefault("jsonrpc", "2.0")
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def raw(self):
        return self.p.stdout.readline()

    def ask(self, **obj):
        self.send(**obj)
        return json.loads(self.raw())

    def call(self, name, **args):
        r = self.ask(id=99, method="tools/call",
                     params={"name": name, "arguments": args})
        c = r["result"]["content"][0]
        return c["text"], r["result"].get("isError", False)


print("① 손을 잡는다 (initialize)")
with Server() as s:
    r = s.ask(id=1, method="initialize",
              params={"protocolVersion": "2025-06-18", "capabilities": {},
                      "clientInfo": {"name": "claude", "version": "1"}})
    eq("판 번호를 그대로 돌려준다", r["result"]["protocolVersion"], "2025-06-18")
    eq("이름을 밝힌다", r["result"]["serverInfo"]["name"], "kosai-marketing")
    ok("도구가 있다고 알린다", "tools" in r["result"]["capabilities"])
    ok("쓰는 법을 같이 준다", "instructions" in r["result"])
    eq("id 를 맞춰 돌려준다", r["id"], 1)

with Server() as s:
    r = s.ask(id=1, method="initialize",
              params={"protocolVersion": "3000-비정상"})
    eq("모르는 판 번호면 우리 기본값", r["result"]["protocolVersion"], "2025-06-18")

with Server() as s:
    r = s.ask(id=1, method="initialize",
              params={"protocolVersion": "2024-11-05"})
    eq("옛 판도 맞춰 준다", r["result"]["protocolVersion"], "2024-11-05")

print("\n② 알림에는 답하지 않는다")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})
    s.send(method="notifications/initialized")      # id 가 없다
    s.send(method="notifications/cancelled", params={"requestId": 1})
    r = s.ask(id=2, method="ping")
    eq("알림 뒤에도 다음 답이 어긋나지 않는다", r["id"], 2)
    eq("ping 은 빈 답", r["result"], {})

print("\n③ 도구 목록")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})
    tools = s.ask(id=2, method="tools/list")["result"]["tools"]
    names = [t["name"] for t in tools]
    ok("숫자 도구가 다 있다",
       all(n in names for n in ("weekly", "traffic", "pages", "behavior",
                                "trend", "report", "weeks", "refresh")))
    ok("실험 도구가 다 있다",
       all(n in names for n in ("experiments", "experiment_add",
                                "experiment_start", "experiment_drop")))
    ok("이름이 겹치지 않는다", len(names) == len(set(names)))
    ok("모두 설명이 있다", all(len(t.get("description", "")) > 10 for t in tools))
    ok("모두 스키마가 object", all(t["inputSchema"]["type"] == "object"
                                 for t in tools))
    ok("필수 인자는 properties 안에 있다",
       all(set(t["inputSchema"].get("required", []))
           <= set(t["inputSchema"].get("properties", {})) for t in tools))
    ok("이름은 영문·밑줄뿐", all(n.replace("_", "").isalnum() and n.islower()
                              for n in names))

print("\n④ 도구를 부른다")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})

    t, err = s.call("weekly")
    ok("주간 숫자판이 온다", "KOSAI 주간 성과 보고" in t and not err, t[:80])
    ok("가장 최근 주다", "9월 7일" in t, t[:200])

    t, _ = s.call("weekly", week="2026-08-31")
    ok("주를 골라 볼 수 있다", "8월 31일" in t, t[:200])

    t, _ = s.call("weekly", week="1999-01-04")
    ok("없는 주는 있는 주를 알려 준다", "있는 주" in t, t)

    t, _ = s.call("weekly", weeks=3)
    ok("여러 주 흐름도 붙는다", "더 긴 흐름" in t and "2026-08-24" in t, t[-300:])

    t, _ = s.call("weekly", week="2026-08-31", weeks=2)
    ok("주를 고르면 흐름도 그 주에서 끝난다",
       "2026-08-31" in t and "2026-09-07" not in t, t[-300:])

    t, err = s.call("traffic")
    ok("유입 경로가 온다", "검색으로 들어옴" in t and not err, t[:200])
    ok("유입처별 가입 전환이 온다", "들어옴 220" in t and "가입 5" in t, t)

    t, _ = s.call("pages")
    ok("페이지에 갈래가 붙는다", "[관리자]" in t, t)
    ok("종목에 이름표가 붙는다", "삼성전자" in t, t)

    t, _ = s.call("behavior")
    ok("완독 비율이 온다", "끝까지" in t and "30%" in t, t)
    ok("그냥 나간 비율이 온다", "그냥 나감 72%" in t, t)

    t, _ = s.call("trend", metric="returnRate", weeks=3)
    ok("재방문율 흐름이 온다", "재방문율" in t and "12.5" in t, t)
    t, _ = s.call("trend", metric="없는지표")
    ok("모르는 지표는 쓸 수 있는 것을 알려 준다", "쓸 수 있는 지표" in t, t)

    t, _ = s.call("report")
    eq("보고서 원문이 온다", t, "지난주 보고서 원문입니다.")

    t, _ = s.call("weeks")
    ok("몇 주를 갖고 있는지 말한다", "받아 둔 주 3개" in t, t)
    ok("어디에 저장돼 있는지 말한다", "저장 위치" in t, t)

print("\n⑤ 실험 대장 — 제안 → 실행 → 검증")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})
    t, _ = s.call("experiments")
    ok("처음엔 비어 있다", "비어 있습니다" in t, t)

    t, err = s.call("experiment_add", title="리포트에 가입 버튼",
                    why="리포트는 481회 보는데 가입이 6건", metric="signUpRate",
                    action="stock.html 본문 끝에 버튼을 넣는다")
    ok("제안이 올라간다", "exp_1" in t and not err, t)
    ok("다음에 뭘 해야 하는지 알려 준다", "experiment_start" in t, t)

    t, _ = s.call("experiment_add", title="리포트에 가입 버튼", why="또",
                  metric="users", action="또")
    ok("같은 제목은 두 번 안 올라간다", "올리지 않았습니다" in t, t)

    t, _ = s.call("experiment_add", title="지표 틀림", why="x",
                  metric="아무거나", action="y")
    ok("모르는 지표는 고를 것을 알려 준다", "지표는 이 중 하나" in t, t)

    t, _ = s.call("experiment_start", id="exp_1")
    ok("실행 표시가 된다", "진행중" in t and "2026-09-07" in t, t)

    t, _ = s.call("experiments")
    ok("대장에 진행중으로 보인다", "[진행중] exp_1" in t, t)

    t, _ = s.call("experiment_start", id="exp_9")
    ok("없는 번호는 없다고 말한다", "대장에 없습니다" in t, t)

    t, _ = s.call("experiment_drop", id="exp_1", why="생각해보니 아님")
    ok("버릴 수 있다", "버렸습니다" in t, t)

print("\n⑥ 잘못 물어봐도 서버가 죽지 않는다")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})

    t, err = s.call("없는도구")
    ok("없는 도구는 오류로 알린다", err and "그런 도구가 없습니다" in t, t)

    t, err = s.call("weekly", 이상한인자=1)
    ok("모르는 인자는 오류로 알린다", err and "모르는 인자입니다" in t, t)
    ok("쓸 수 있는 인자를 알려 준다", "week" in t, t)

    r = s.ask(id=2, method="tools/call", params={"name": "weekly"})
    ok("arguments 가 없어도 돈다", not r["result"].get("isError"), r)

    r = s.ask(id=3, method="없는방법")
    eq("모르는 방법은 -32601", r["error"]["code"], -32601)

    s.p.stdin.write("이건 JSON 이 아니다\n")
    s.p.stdin.flush()
    r = json.loads(s.raw())
    eq("깨진 줄은 -32700", r["error"]["code"], -32700)

    r = s.ask(id=4, method="tools/list")
    ok("그 뒤에도 살아 있다", len(r["result"]["tools"]) > 0)

    # 옛 판에서는 한 줄에 여럿을 묶어 보냈다. 묶음이 와도 죽지 않아야 한다.
    s.p.stdin.write(json.dumps([
        {"jsonrpc": "2.0", "id": 7, "method": "ping"},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 8, "method": "ping"}]) + "\n")
    s.p.stdin.flush()
    b = json.loads(s.raw())
    ok("묶음에는 묶음으로 답한다", isinstance(b, list) and len(b) == 2, b)
    ok("묶음 안 알림에는 답하지 않는다",
       isinstance(b, list) and [x.get("id") for x in b] == [7, 8], b)

    s.p.stdin.write("[]\n")
    s.p.stdin.flush()
    ok("빈 묶음도 답은 준다", json.loads(s.raw()).get("error") is not None)

    s.p.stdin.write('"객체가 아님"\n')
    s.p.stdin.flush()
    eq("객체가 아니면 -32600", json.loads(s.raw())["error"]["code"], -32600)

    r = s.ask(id=9, method="tools/list")
    ok("이상한 것을 여러 번 받아도 살아 있다", len(r["result"]["tools"]) > 0)

    eq("resources/list 는 빈 목록",
       s.ask(id=5, method="resources/list")["result"], {"resources": []})
    eq("prompts/list 는 빈 목록",
       s.ask(id=6, method="prompts/list")["result"], {"prompts": []})

print("\n⑦ stdout 에는 JSON 말고 아무것도 없다")
with Server() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})
    for i, (name, args) in enumerate([("weekly", {}), ("traffic", {}),
                                      ("pages", {}), ("behavior", {}),
                                      ("weeks", {}), ("없는도구", {})]):
        s.send(id=100 + i, method="tools/call",
               params={"name": name, "arguments": args})
    good = True
    for i in range(6):
        ln = s.raw()
        try:
            j = json.loads(ln)
            good = good and j.get("jsonrpc") == "2.0" and j.get("id") == 100 + i
        except Exception:
            good = False
    ok("모든 줄이 제대로 된 JSON-RPC 한 줄", good)
    # refresh 는 열쇠가 없으면 설명만 하고 끝나야 한다 (터지면 안 된다)
    t, err = s.call("refresh")
    ok("열쇠가 없으면 왜 없는지 말한다",
       "GA4_PROPERTY_ID" in t and not err, t)

print("\n⑧ 숫자가 하나도 없을 때")
EMPTY = tempfile.mkdtemp(prefix="mcp-empty-")


class Empty(Server):
    env = env_for(EMPTY)


with Empty() as s:
    s.ask(id=1, method="initialize", params={"protocolVersion": "2025-06-18"})
    for name in ("weekly", "traffic", "pages", "behavior", "trend"):
        t, err = s.call(name)
        ok(f"{name}: 없으면 어떻게 하라고 알려 준다",
           not err and ("refresh" in t or "받아 둔 숫자가" in t), t[:80])
    t, _ = s.call("experiment_add", title="ㄱ", why="ㄴ", action="ㄷ",
                  metric="users")
    ok("시작값을 못 잡으면 올리지 않는다", "refresh" in t, t)

print("\n⑨ 붙이기 전 자가 점검 (--selftest)")
r = subprocess.run([sys.executable, str(SERVER), "--selftest"],
                   capture_output=True, text=True, cwd=str(ROOT), env=ENV)
eq("성공으로 끝난다", r.returncode, 0)
ok("사람이 읽을 안내가 stderr 로 나온다", "도구" in r.stderr, r.stderr[:200])
eq("stdout 은 비어 있다", r.stdout.strip(), "")

print("\n" + "=" * 52)
print(f"PASS {P}  FAIL {F}")
sys.exit(1 if F else 0)
