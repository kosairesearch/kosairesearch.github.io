#!/usr/bin/env python3
"""마케팅 담당을 클로드 안으로 — MCP 서버.

무엇인가
--------
텔레그램으로 오는 주간 보고는 한 방향이다. 읽고 나서 "그럼 네이버에서
온 사람은 몇 명이야?" 하고 되물을 데가 없다. 이 파일은 그 되묻기를
가능하게 한다. 클로드가 이 서버에 붙으면, 클로드한테 한국말로 물어보면
클로드가 알아서 여기 있는 도구를 골라 Firestore 에서 숫자를 꺼내 온다.

    사장: "지난주에 네이버에서 온 사람 중 가입한 사람 비율이 어떻게 돼?"
    클로드: (traffic 도구를 부른다) → "네이버 300명 중 6명, 2.0%입니다"

무엇을 할 수 있나
----------------
    weekly        주간 숫자판 (텔레그램에 오는 그 표)
    traffic       어디서 왔나 · 유입처별 가입 전환
    pages         어느 페이지·어느 종목을 봤나
    behavior      얼마나 읽고 어디서 떠났나
    trend         한 지표의 여러 주 흐름
    report        지난 주간 보고서 원문
    experiments   실험 대장 보기
    experiment_add / experiment_start / experiment_drop
    refresh       GA4 에서 지금 새로 받아오기
    weeks         받아 둔 주가 몇 개인지

어떻게 붙이나 (Claude Desktop)
------------------------------
설정 파일에 아래를 넣는다. 윈도우는
%APPDATA%\\Claude\\claude_desktop_config.json,
맥은 ~/Library/Application Support/Claude/claude_desktop_config.json.

    {
      "mcpServers": {
        "kosai-marketing": {
          "command": "python",
          "args": ["C:\\\\경로\\\\scripts\\\\marketing_mcp.py"],
          "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": "C:\\\\경로\\\\firebase-key.json",
            "GA4_PROPERTY_ID": "숫자 9자리"
          }
        }
      }
    }

위 설정을 손으로 적지 말고 아래로 뽑아 쓴다 — 경로를 틀리는 게 가장
흔한 실패다.

    python scripts/marketing_mcp.py --config

붙이기 전에 먼저 이것부터 돌려 본다. 안 되면 왜 안 되는지 말해 준다.

    python scripts/marketing_mcp.py --selftest

클로드 앱을 안 깔았으면 — 깃허브 Actions 의 '마케팅 숫자 물어보기' 를
돌리면 된다. 그게 이 파일의 --ask 를 부른다.

왜 규약을 직접 구현했나
----------------------
MCP 표준 라이브러리를 쓰면 pydantic·starlette·uvicorn 까지 딸려 온다.
이 서버는 stdin/stdout 으로 JSON 한 줄씩 주고받는 게 전부라 그게 필요
없다. 사장 컴퓨터에 설치할 것이 적을수록 안 깨진다. 규약의 핵심(초기화·
도구 목록·도구 실행)은 판이 바뀌어도 그대로다.

중요 — stdout 에는 JSON 말고 아무것도 쓰면 안 된다. print() 로 뭘 찍는
순간 클로드가 서버를 못 읽는다. 사람에게 할 말은 전부 stderr 로 간다.
"""
import datetime
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

NAME = "kosai-marketing"
VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
KST = datetime.timezone(datetime.timedelta(hours=9))


def log(*a, **kw):
    # stdout 은 클로드와 주고받는 통로다. 사람에게 할 말은 전부 여기로.
    print(*a, file=sys.stderr, flush=True, **kw)


# ── 숫자를 꺼내 오는 쪽 ────────────────────────────────────────────

def _weekly():
    import ga4_store
    doc = ga4_store.load("weekly")
    if not isinstance(doc.get("weeks"), list):
        doc["weeks"] = []
    return doc


def _pick(doc, week=None):
    """주를 고른다. week 가 없으면 가장 최근. 없는 주를 달라고 하면 None."""
    weeks = doc.get("weeks") or []
    if not weeks:
        return None
    if not week:
        return weeks[-1]
    for w in weeks:
        if w.get("week") == week:
            return w
    return None


def _need(doc, week):
    """고르지 못했을 때 사람에게 할 말."""
    weeks = doc.get("weeks") or []
    if not weeks:
        return ("받아 둔 숫자가 한 주도 없습니다. refresh 도구로 GA4 에서"
                " 먼저 받아오거나, GitHub Actions 의 '주간 성과 보고' 를"
                " 한 번 돌려 주세요.")
    have = ", ".join(w.get("week", "?") for w in weeks[-12:])
    return f"{week} 주는 받아 둔 것이 없습니다. 있는 주: {have}"


# ── 도구 하나하나 ──────────────────────────────────────────────────

def t_weekly(week=None, weeks=1):
    import marketing_report as M
    doc = _weekly()
    all_w = doc.get("weeks") or []
    if not all_w:
        return _need(doc, week)
    cur = _pick(doc, week)
    if not cur:
        return _need(doc, week)
    # 고른 주에서 끝나는 창. 주를 골라 놓고 흐름만 '가장 최근 N주' 를
    # 보여 주면, 표와 흐름이 서로 다른 기간을 말하게 된다.
    i = all_w.index(cur)
    out = [M.metrics_block({"weeks": all_w[max(0, i - 1):i + 1],
                            "health": doc.get("health")})]
    n = max(1, min(int(weeks or 1), 52))
    if n > 1:
        out.append("\n■ 더 긴 흐름 (주 / 방문자 / 다시 온 / 재방문율)")
        for w in all_w[max(0, i + 1 - n):i + 1]:
            u = w.get("users") or 0
            r = (w.get("returningUsers", 0) / u * 100) if u else 0
            out.append(f"  {w.get('week')}  {u:>6,}명  "
                       f"{w.get('returningUsers', 0):>5,}명  {r:>5.1f}%")
    return "\n".join(out)


def t_traffic(week=None):
    import ga4_data as G
    import marketing_report as M
    doc = _weekly()
    cur = _pick(doc, week)
    if not cur:
        return _need(doc, week)
    L = [f"[{cur['week']} ~ {cur.get('to')}] 어디서 왔나"]
    ch = M._pairs(cur, "channels", "sessionDefaultChannelGroup", "sessions")
    if ch:
        L.append("\n■ 유입 경로 · 방문 횟수")
        for k, n in ch:
            L.append(f"  {G.CHANNEL_NAMES.get(k, k)}: {n:,}")
    src = M.labeled(cur, "sources", "sessionSource", "sessions", G.source_label)
    if src:
        L.append("\n■ 어느 사이트에서 · 방문 횟수")
        for name, n in src[:12]:
            L.append(f"  {name}: {n:,}")
        L.append("  ※ 같은 곳은 묶여 있다(m.search.naver.com 과 naver 는 둘 다 네이버).")
        L.append("  ※ '로그인하고 돌아옴' 은 새 손님이 아니다 — 우리 사이트에서"
                 " 네이버·카카오 로그인을 누르고 되돌아온 것이다.")
    fn = M.source_funnel(cur)
    if fn and all(name == "알 수 없음" for name, *_ in fn):
        L.append("\n■ 유입처별 들어옴 → 가입  아직 가를 수 없습니다 —"
                 " 이 주의 기록에는 유입처가 안 붙어 있습니다. 다음 주부터 나옵니다.")
    elif fn:
        L.append("\n■ 유입처별 들어옴 → 가입")
        for name, v, su, r in fn:
            rr = f" · 가입 {r:.1f}%" if r is not None else ""
            L.append(f"  {name}: 들어옴 {v:,} / 가입 {su:,}{rr}")
        L.append("  ※ 들어옴이 30 미만이면 비율은 널뛰니 말하지 않는 게 낫다.")
    if len(L) == 1:
        L.append("  이 주에는 유입 자료가 없습니다.")
    return "\n".join(L)


def t_pages(week=None, top=15):
    import ga4_data as G
    import marketing_report as M
    doc = _weekly()
    cur = _pick(doc, week)
    if not cur:
        return _need(doc, week)
    L = [f"[{cur['week']} ~ {cur.get('to')}] 무엇을 봤나"]
    rows = M._pairs(cur, "pages", "pagePath", "screenPageViews")
    if rows:
        L.append("\n■ 페이지별 조회 (갈래)")
        for p, n in rows[:max(1, min(int(top or 15), 40))]:
            L.append(f"  {M.page_label(p)} [{G.page_kind(p)}]: {n:,}")
        kinds, tot = M.split_pages(cur)
        inner = kinds["계정"] + kinds["관리자"] + kinds["테스트"]
        if tot:
            L.append(f"  ─ 콘텐츠 {kinds['콘텐츠']:,} · 우리 발자국 {inner:,}"
                     f" ({inner / tot * 100:.0f}%)")
            L.append("  ※ 계정·관리자·staging 은 대개 우리가 본 것이라 성과가 아니다.")
    tk = M.top_tickers(cur, 15)
    if tk:
        L.append("\n■ 많이 눌린 종목")
        for name, c in tk:
            L.append(f"  {name}: {c:,}회")
    if len(L) == 1:
        L.append("  이 주에는 페이지 자료가 없습니다.")
    return "\n".join(L)


def t_behavior(week=None):
    import marketing_report as M
    doc = _weekly()
    cur = _pick(doc, week)
    if not cur:
        return _need(doc, week)
    L = [f"[{cur['week']} ~ {cur.get('to')}] 어떻게 읽고 어디서 떠났나"]
    rt = M.read_through(cur)
    if rt:
        pct, start, end = rt
        L.append(f"\n■ 얼마나 내려 읽나  25%까지 {start:,}회 · 끝까지 {end:,}회"
                 f" → 시작한 것 중 {pct}%")
        L.append("  ※ '방문자 중 완독률' 이 아니다. 내려 읽기 시작한 것 중 비율이다.")
    lp = M._pairs(cur, "landings", "landingPage", "sessions")
    if lp:
        b = {r.get("landingPage"): r.get("bounceRate")
             for r in (cur.get("landings") or [])}
        L.append("\n■ 처음 열린 페이지 · 방문 · 그냥 나간 비율")
        for p, n in lp[:10]:
            v = b.get(p)
            bs = f" · 그냥 나감 {v * 100:.0f}%" if isinstance(v, (int, float)) else ""
            L.append(f"  {M.page_label(p)}: {n:,}{bs}")
    lv = M._pairs(cur, "leave", "customEvent:from_page")
    if lv:
        L.append("\n■ 어느 페이지에서 떠났나")
        for p, n in lv[:10]:
            L.append(f"  {M.page_label(p)}: {n:,}")
    sp = M._pairs(cur, "signupPage", "customEvent:from_page")
    if sp:
        L.append("\n■ 어느 페이지에서 가입을 눌렀나")
        for p, n in sp[:10]:
            L.append(f"  {M.page_label(p)}: {n:,}")
    bv = M.by_visitor(cur, 8)
    if bv.get("재방문") or bv.get("신규"):
        L.append("\n■ 누가 무엇을 보나 (콘텐츠만)")
        for who in ("재방문", "신규"):
            if bv.get(who):
                L.append(f"  {who}: " + " · ".join(f"{n} {c:,}" for n, c in bv[who]))
    miss = cur.get("_missing") or {}
    if miss:
        L.append("\n■ 못 받은 자료: " + ", ".join(sorted(miss)))
        L.append("  ※ GA4 '맞춤 측정기준' 등록 전이거나 아직 안 쌓인 것. 0 이 아니다.")
    if len(L) == 1:
        L.append("  이 주에는 행동 자료가 없습니다.")
    return "\n".join(L)


def t_trend(metric="users", weeks=12):
    import experiments as X
    if metric not in X.METRICS:
        return "쓸 수 있는 지표: " + ", ".join(X.METRICS)
    doc = _weekly()
    rows = (doc.get("weeks") or [])[-max(2, min(int(weeks or 12), 52)):]
    if not rows:
        return _need(doc, None)
    L = [f"[{X.METRICS[metric]}] 주별 흐름"]
    vals = []
    for w in rows:
        v = X.value_of(w, metric)
        vals.append(v)
        L.append(f"  {w.get('week')}  {'받지 못함' if v is None else f'{v:,}'}")
    got = [v for v in vals if isinstance(v, (int, float))]
    if len(got) >= 3:
        up = sum(1 for a, b in zip(got, got[1:]) if b > a)
        down = sum(1 for a, b in zip(got, got[1:]) if b < a)
        L.append(f"  ─ 오른 주 {up}번 · 내린 주 {down}번 ·"
                 f" 가장 낮음 {min(got):,} · 가장 높음 {max(got):,}")
        L.append("  ※ 세 주 이상 같은 방향일 때만 '추세' 라고 부를 수 있다.")
    return "\n".join(L)


def t_report(week=None):
    import ga4_store
    box = ga4_store.load("reports", {"items": []})
    items = box.get("items") or []
    if not items:
        return "저장된 보고서가 없습니다."
    if week:
        hit = [x for x in items if x.get("week") == week]
        if not hit:
            have = ", ".join(x.get("week", "?") for x in items[-12:])
            return f"{week} 주 보고서가 없습니다. 있는 주: {have}"
        return hit[-1].get("text") or "(내용 없음)"
    return items[-1].get("text") or "(내용 없음)"


def t_experiments():
    import experiments as X
    doc = X.load()
    items = doc.get("items") or []
    if not items:
        return ("실험 대장이 비어 있습니다. experiment_add 로 하나 올려 두면"
                " 다음 주부터 효과를 잽니다.")
    L = ["■ 실험 대장"]
    for it in items:
        r = it.get("result") or {}
        tail = (f" → {r.get('verdict')} ({r.get('base')}→{r.get('now')})"
                if r else "")
        L.append(f"  [{it.get('status')}] {it.get('id')} · {it.get('title')}{tail}")
        L.append(f"       왜: {it.get('why')}")
        L.append(f"       할 일: {it.get('action')}")
        L.append(f"       볼 지표: {it.get('metricLabel')}"
                 f" (시작값 {it.get('baseValue')})")
    L.append("  ※ '제안됨' 은 아직 손대지 않은 것. 실제로 했으면"
             " experiment_start 로 표시해야 다음 주에 효과를 잰다.")
    return "\n".join(L)


def t_experiment_add(title=None, why=None, action=None, metric=None):
    import experiments as X
    if not all([title, why, action, metric]):
        return "제목·이유·할일·지표를 모두 적어야 합니다."
    if metric not in X.METRICS:
        return ("지표는 이 중 하나여야 합니다: "
                + ", ".join(f"{k}({v})" for k, v in X.METRICS.items()))
    doc = X.load()
    weeks = _weekly().get("weeks") or []
    if not weeks:
        return "받아 둔 숫자가 없어 시작값을 잡을 수 없습니다. 먼저 refresh 하세요."
    it, err = X.propose(doc, title, why, metric, action, weeks[-1])
    if not it:
        return f"올리지 않았습니다 — {err}"
    X.save(doc)
    return (f"✅ {it['id']} 대장에 올렸습니다.\n"
            f"  {it['title']}\n"
            f"  볼 지표: {it['metricLabel']} · 지금 값 {it['baseValue']}\n"
            f"  실제로 하고 나면 experiment_start 로 '{it['id']}' 를 표시하세요."
            " 그 다음 주부터 효과를 잽니다.")


def t_experiment_start(id=None):
    import experiments as X
    doc = X.load()
    it = next((x for x in doc["items"] if x.get("id") == id), None)
    if not it:
        return f"{id} 가 대장에 없습니다."
    weeks = _weekly().get("weeks") or []
    it["status"] = "진행중"
    it["startedWeek"] = weeks[-1]["week"] if weeks else None
    if weeks:
        it["baseValue"] = X.value_of(weeks[-1], it["metric"])
    X.save(doc)
    return (f"✅ {it['id']} 를 '진행중' 으로 표시했습니다.\n"
            f"  기준: {it['metricLabel']} = {it['baseValue']}"
            f" ({it['startedWeek']} 주)\n"
            "  다음 주 숫자가 들어오면 자동으로 판정합니다.")


def t_experiment_drop(id=None, why=""):
    import experiments as X
    doc = X.load()
    it = next((x for x in doc["items"] if x.get("id") == id), None)
    if not it:
        return f"{id} 가 대장에 없습니다."
    it["status"] = "버림"
    it["why_dropped"] = why or ""
    X.save(doc)
    return f"✅ {it['id']} ({it['title']}) 를 버렸습니다."


def t_weeks():
    doc = _weekly()
    weeks = doc.get("weeks") or []
    import ga4_store
    if not weeks:
        return f"받아 둔 주가 없습니다. 저장 위치: {ga4_store.where()}"
    L = [f"받아 둔 주 {len(weeks)}개 · 저장 위치: {ga4_store.where()}"]
    for w in weeks:
        L.append(f"  {w.get('week')} ~ {w.get('to')}  방문자 {w.get('users', 0):,}명"
                 + ("  (행동 자료 있음)" if any(
                     w.get(k) for k in ("tickers", "scroll", "landings")) else ""))
    hl = doc.get("health") or {}
    if not hl.get("ok", True):
        L.append("⚠️ 온전하지 않음 — " + " / ".join(hl.get("problems") or []))
    return "\n".join(L)


def t_refresh(weeks=12):
    """GA4 에서 지금 새로 받아온다. 열쇠가 없으면 왜 없는지 말해 준다."""
    import ga4_data as G
    if not os.environ.get("GA4_PROPERTY_ID"):
        return ("GA4_PROPERTY_ID 가 없습니다. 클로드 설정 파일의 env 에"
                " GA4_PROPERTY_ID(숫자 9자리)를 넣어 주세요.")
    import ga4_store
    try:
        doc = G.collect(weeks=max(2, min(int(weeks or 12), 52)))
    except (Exception, SystemExit) as e:
        # SystemExit 까지 잡는다 — 열쇠가 없으면 ga4_data 가 그것으로 끝낸다.
        # 서버가 같이 죽으면 클로드 쪽에는 '연결 끊김' 으로만 보인다.
        return f"GA4 에서 받지 못했습니다 — {type(e).__name__}: {e}"
    rows = doc.get("weeks") or []
    hl = doc.get("health") or {}
    if not rows:
        return ("GA4 가 한 주도 주지 않았습니다"
                + (" — " + " / ".join(hl.get("problems") or []) if hl.get("problems")
                   else "."))
    total = G.merge_save(doc)
    last = rows[-1]
    L = [f"✅ {len(rows)}주치를 새로 받았습니다. 쌓인 주는 모두 {total}개입니다.",
         f"  저장 위치: {ga4_store.where()}",
         f"  가장 최근: {last.get('week')} ~ {last.get('to')}"
         f" · 방문자 {last.get('users', 0):,}명"]
    if not hl.get("ok", True):
        L.append("⚠️ 온전하지 않음 — " + " / ".join(hl.get("problems") or []))
    return "\n".join(L)


# ── 도구 목록 (클로드가 읽는 설명) ─────────────────────────────────
def _week_arg(extra=""):
    return {"type": "string",
            "description": "볼 주의 월요일 날짜 (YYYY-MM-DD). 비우면 가장 최근 주." + extra}


TOOLS = [
    {"name": "weekly", "fn": t_weekly,
     "description": "KOSAI 주간 성과 숫자판 — 방문자·재방문율·조회·가입·"
                    "우리 발자국 비율까지. 텔레그램으로 가는 그 표와 같다. "
                    "'지난주 어땠어' 같은 물음에 먼저 이것부터 부른다.",
     "inputSchema": {"type": "object", "properties": {
         "week": _week_arg(),
         "weeks": {"type": "integer",
                   "description": "함께 볼 지난 주 수 (기본 1, 최대 52)"}}}},
    {"name": "traffic", "fn": t_traffic,
     "description": "손님이 어디서 왔나 — 검색·SNS·직접 유입 경로, 사이트별 "
                    "방문, 그리고 유입처별 '들어옴 → 가입' 전환.",
     "inputSchema": {"type": "object", "properties": {"week": _week_arg()}}},
    {"name": "pages", "fn": t_pages,
     "description": "무엇을 봤나 — 페이지별 조회수(콘텐츠·계정·관리자 갈래 "
                    "표시)와 가장 많이 눌린 종목.",
     "inputSchema": {"type": "object", "properties": {
         "week": _week_arg(),
         "top": {"type": "integer", "description": "보여 줄 페이지 수 (기본 15)"}}}},
    {"name": "behavior", "fn": t_behavior,
     "description": "어떻게 읽고 어디서 떠났나 — 완독 비율, 처음 열린 페이지와 "
                    "그냥 나간 비율, 떠난 페이지, 가입을 누른 페이지, "
                    "신규와 재방문이 각각 본 것.",
     "inputSchema": {"type": "object", "properties": {"week": _week_arg()}}},
    {"name": "trend", "fn": t_trend,
     "description": "한 지표의 여러 주 흐름. 한 주 움직임으로 추세를 말하지 "
                    "않으려면 이것을 본다.",
     "inputSchema": {"type": "object", "properties": {
         "metric": {"type": "string",
                    "enum": ["users", "returningUsers", "returnRate", "sessions",
                             "pageViews", "engagedRate", "avgSessionSec",
                             "signUp", "signUpRate", "watchlistAdd"],
                    "description": "볼 지표 (기본 users)"},
         "weeks": {"type": "integer", "description": "몇 주치 (기본 12)"}}}},
    {"name": "report", "fn": t_report,
     "description": "저장해 둔 주간 보고서 원문 — 텔레그램으로 보낸 줄글 "
                    "그대로다. '지난주에 뭐라고 했었지' 처럼 지난 보고서 "
                    "자체를 찾을 때만 써라. 성과를 물었으면 weekly 를 써라. "
                    "그리고 이 글을 그대로 옮기지 말고 표로 다시 짜서 보여 줘라.",
     "inputSchema": {"type": "object", "properties": {"week": _week_arg()}}},
    {"name": "experiments", "fn": t_experiments,
     "description": "실험 대장 — 무엇을 하자고 했고, 했는지, 효과가 있었는지.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "experiment_add", "fn": t_experiment_add,
     "description": "새 실험을 대장에 올린다. 무엇을 볼지(지표)를 미리 못 "
                    "박아 두면 나중에 좋아 보이는 숫자를 고르게 되므로 지표는 필수.",
     "inputSchema": {"type": "object", "properties": {
         "title": {"type": "string", "description": "한 줄 제목 (25자 안쪽)"},
         "why": {"type": "string", "description": "어느 숫자 때문인지"},
         "action": {"type": "string", "description": "사람이 실제로 손댈 일"},
         "metric": {"type": "string",
                    "enum": ["users", "returningUsers", "returnRate", "sessions",
                             "pageViews", "engagedRate", "avgSessionSec",
                             "signUp", "signUpRate", "watchlistAdd"],
                    "description": "효과를 잴 지표"}},
         "required": ["title", "why", "action", "metric"]}},
    {"name": "experiment_start", "fn": t_experiment_start,
     "description": "그 실험을 실제로 했다고 표시한다. 이걸 해야 다음 주부터 "
                    "효과를 잰다.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string", "description": "실험 번호 (예: exp_3)"}},
         "required": ["id"]}},
    {"name": "experiment_drop", "fn": t_experiment_drop,
     "description": "안 하기로 한 실험을 대장에서 내린다.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string", "description": "실험 번호 (예: exp_3)"},
         "why": {"type": "string", "description": "안 하는 이유"}},
         "required": ["id"]}},
    {"name": "weeks", "fn": t_weeks,
     "description": "받아 둔 주가 몇 개이고 어디에 저장돼 있는지. 숫자가 "
                    "안 나올 때 여기부터 본다.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "refresh", "fn": t_refresh,
     "description": "GA4 에서 지금 새로 받아와 저장한다. 월요일 자동 수집을 "
                    "기다리지 않고 최신 숫자를 볼 때. 몇 초 걸린다.",
     "inputSchema": {"type": "object", "properties": {
         "weeks": {"type": "integer", "description": "몇 주치를 받을지 (기본 12)"}}}},
]
BY_NAME = {t["name"]: t for t in TOOLS}


def call_tool(name, args):
    """도구 하나를 부른다. 무슨 일이 나도 서버는 죽지 않는다 —
    죽으면 클로드 쪽에서는 그냥 '연결 끊김' 으로만 보여서 왜 그런지 알 수 없다."""
    import inspect
    t = BY_NAME.get(name)
    if not t:
        return f"그런 도구가 없습니다: {name}", True
    args = args if isinstance(args, dict) else {}
    # 부르기 전에 인자 이름을 맞춰 본다. 부르고 나서 TypeError 로 알면,
    # 도구 안에서 난 TypeError 까지 '인자가 틀렸다'로 잘못 말하게 된다.
    want = set(inspect.signature(t["fn"]).parameters)
    extra = [k for k in args if k not in want]
    if extra:
        return (f"모르는 인자입니다: {', '.join(extra)}."
                f" 쓸 수 있는 것: {', '.join(sorted(want)) or '없음'}"), True
    try:
        return (t["fn"](**args) or "(빈 결과)"), False
    except (Exception, SystemExit) as e:
        log(f"[{name}] {type(e).__name__}: {e}")
        return f"{name} 실행 중 문제 — {type(e).__name__}: {e}", True


# ── MCP 규약 (JSON-RPC 2.0 over stdio) ─────────────────────────────

def _result(rid, payload):
    return {"jsonrpc": "2.0", "id": rid, "result": payload}


def _error(rid, code, msg):
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}


def handle(msg):
    """요청 하나에 대한 답. 알림(id 없음)이면 None — 답하면 안 된다."""
    rid = msg.get("id")
    method = msg.get("method") or ""
    params = msg.get("params") or {}
    if rid is None:
        return None                     # notifications/initialized 등

    if method == "initialize":
        # 상대가 말한 판을 그대로 되돌려 준다. 우리가 쓰는 것(도구 목록·
        # 도구 실행)은 어느 판에나 있으므로, 모르는 판이라고 거절하는 것보다
        # 맞춰 주는 쪽이 안 깨진다. 날짜 모양이 아니면 우리 기본값을 쓴다.
        want = str(params.get("protocolVersion") or "")
        ver = want if (len(want) == 10 and want[4] == want[7] == "-") else DEFAULT_PROTOCOL
        return _result(rid, {
            "protocolVersion": ver,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": NAME, "version": VERSION},
            "instructions": "KOSAI 사이트의 GA4 숫자와 실험 대장을 읽고 씁니다. "
                            "숫자를 물으면 weekly 부터 부르고, 더 파고들 때 "
                            "traffic·pages·behavior 를 씁니다. 여기 없는 숫자는 "
                            "지어내지 말고 '받지 못했다'고 말하세요.",
        })
    if method == "ping":
        return _result(rid, {})
    if method == "tools/list":
        return _result(rid, {"tools": [
            {k: t[k] for k in ("name", "description", "inputSchema")} for t in TOOLS]})
    if method == "tools/call":
        text, bad = call_tool(params.get("name"), params.get("arguments"))
        return _result(rid, {"content": [{"type": "text", "text": text}],
                             "isError": bool(bad)})
    # 우리가 안 내건 기능들. 없다고 말하는 대신 빈 목록을 준다 — 굳이
    # 물어보는 상대가 있는데 오류를 돌려주면 붙는 데서 멈춰 버린다.
    if method == "resources/list":
        return _result(rid, {"resources": []})
    if method == "prompts/list":
        return _result(rid, {"prompts": []})
    return _error(rid, -32601, f"모르는 방법: {method}")


def _one(msg):
    """요청 하나. 무슨 일이 나도 답은 돌려준다 — 답이 없으면 클로드는
    그냥 멈춰 서서 기다린다."""
    if not isinstance(msg, dict):
        return _error(None, -32600, "요청은 객체여야 한다")
    try:
        return handle(msg)
    except Exception as e:
        log("처리 중 예외:", type(e).__name__, e)
        return _error(msg.get("id"), -32603, f"{type(e).__name__}: {e}")


def _answer(msg):
    """한 줄에 여럿이 묶여 올 수도 있다(옛 판의 묶음 요청). 묶음이면
    묶음으로 답한다. 알림만 들어 있으면 아무 답도 하지 않는다."""
    if isinstance(msg, list):
        if not msg:
            return _error(None, -32600, "빈 묶음")
        outs = [a for a in (_one(m) for m in msg) if a is not None]
        return outs or None
    return _one(msg)


def serve(inp=sys.stdin, outp=sys.stdout):
    for raw in inp:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception as e:
            log("JSON 이 아닌 줄이 들어왔다:", e)
            outp.write(json.dumps(_error(None, -32700, "JSON 이 아니다")) + "\n")
            outp.flush()
            continue
        ans = _answer(msg)
        if ans is not None:
            outp.write(json.dumps(ans, ensure_ascii=False) + "\n")
            outp.flush()


def selftest():
    """붙이기 전에 여기서 먼저 확인한다. 무엇이 안 되는지 말해 준다."""
    log("① 규약 —", end=" ")
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-06-18"}})
    assert r["result"]["serverInfo"]["name"] == NAME
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    lst = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    log(f"초기화 OK · 도구 {len(lst)}개")

    log("② 저장 위치 —", end=" ")
    import ga4_store
    log(ga4_store.where())

    log("③ 숫자 —", end=" ")
    doc = _weekly()
    n = len(doc.get("weeks") or [])
    log(f"받아 둔 주 {n}개" if n else "없음 (refresh 또는 주간 워크플로를 한 번 돌리세요)")

    log("④ 도구 실행 —")
    bad = 0
    for t in TOOLS:
        if t["name"].startswith("experiment_") or t["name"] == "refresh":
            continue                     # 쓰는 도구는 시험에서 부르지 않는다
        text, err = call_tool(t["name"], {})
        head = (text or "").splitlines()[0][:60] if text else ""
        log(f"   {'❌' if err else '✅'} {t['name']:<16} {head}")
        bad += 1 if err else 0
    log("")
    if bad:
        log(f"❌ {bad}개가 실패했습니다. 위에 적힌 이유를 보세요.")
        return 1
    if not n:
        log("⚠️ 서버는 정상입니다. 다만 아직 받아 둔 숫자가 없습니다.")
        return 0
    log("✅ 잘 돌아갑니다. 클로드 설정에 붙여도 됩니다.")
    return 0


def config():
    """클로드 설정 파일에 그대로 붙여 넣을 것을 찍어 준다.

    경로를 손으로 적다 틀리는 게 가장 흔한 실패라 여기서 채워서 준다."""
    me = str(Path(__file__).resolve())
    key = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    block = {"mcpServers": {NAME: {
        "command": sys.executable,
        "args": [me],
        "env": {
            "GOOGLE_APPLICATION_CREDENTIALS": key or "여기에 firebase 열쇠 파일 경로",
            "GA4_PROPERTY_ID": os.environ.get("GA4_PROPERTY_ID", "").strip()
                               or "여기에 GA4 속성 번호(숫자 9자리)",
        }}}}
    log("아래를 클로드 설정 파일에 넣고 클로드를 껐다 켜세요.")
    log("  윈도우  %APPDATA%\\Claude\\claude_desktop_config.json")
    log("  맥      ~/Library/Application Support/Claude/claude_desktop_config.json")
    log("")
    log(json.dumps(block, ensure_ascii=False, indent=2))
    log("")
    log("이미 mcpServers 가 있으면 그 안에 " + NAME + " 칸만 더하세요.")
    if not key:
        log("⚠️ firebase 열쇠 경로를 아직 모릅니다. 열쇠가 없으면 이 컴퓨터의"
            " data/ga4 폴더만 보게 되어 숫자가 비어 있을 수 있습니다.")
    return 0


def ask(tool, argtext=""):
    """도구 하나를 불러서 그냥 찍는다. 클로드 앱을 안 깔아도,
    깃허브 Actions 에서 이걸 돌리면 숫자를 볼 수 있다.

        python scripts/marketing_mcp.py --ask weekly
        python scripts/marketing_mcp.py --ask trend --args "metric=returnRate weeks=8"
    """
    args = {}
    for bit in (argtext or "").replace(",", " ").split():
        if "=" not in bit:
            continue
        k, v = bit.split("=", 1)
        k, v = k.strip(), v.strip()
        if not k:
            continue
        args[k] = int(v) if v.lstrip("-").isdigit() else v
    if tool not in BY_NAME:
        log("쓸 수 있는 것: " + ", ".join(BY_NAME))
        return 2
    text, bad = call_tool(tool, args)
    print(text)
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--ask" in sys.argv:
        i = sys.argv.index("--ask")
        tool = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        argtext = ""
        if "--args" in sys.argv:
            j = sys.argv.index("--args")
            argtext = sys.argv[j + 1] if len(sys.argv) > j + 1 else ""
        return ask(tool, argtext)
    if "--config" in sys.argv:
        return config()
    if "--tools" in sys.argv:
        for t in TOOLS:
            log(f"  {t['name']:<18} {t['description'][:60]}")
        return 0
    log(f"{NAME} {VERSION} — 클로드가 붙기를 기다립니다 (stdio)")
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
