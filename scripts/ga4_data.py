#!/usr/bin/env python3
"""GA4 에서 주간 성과 숫자를 받아 온다.

왜 주 단위인가
--------------
하루치는 요일마다 널뛴다. 월요일이 많고 토요일이 적은 건 매주 그런
것이라 '좋아졌다/나빠졌다'를 말해 주지 않는다. 주 단위로 묶으면 요일
효과가 상쇄된다.

왜 저장해 두는가
----------------
GA4 는 오래된 기록을 지운다(기본 14개월). 매주 받아서 저장소에 쌓아
두면 1년 뒤에도 '작년 이맘때'와 비교할 수 있다. 파일로 남아 있으니
읽는 쪽은 열쇠가 없어도 된다.

조심할 것 — 이용자 수는 더할 수 없다
------------------------------------
월요일 100명, 화요일 100명이라고 이틀에 200명이 아니다. 같은 사람이
이틀 다 왔으면 한 명이다. GA4 의 이용자 수는 '중복을 뺀 수'라서,
하루치를 받아 더하면 실제보다 부풀려진다. 그래서 주마다 따로 물어본다.
요청 수가 늘지만 숫자가 맞는 쪽을 택한다.

    python3 scripts/ga4_data.py --whoami          # 서비스 계정 이메일만 찍는다
    python3 scripts/ga4_data.py --weeks 8         # 받아서 보여주기만
    python3 scripts/ga4_data.py --weeks 8 --write # data/ga4/weekly.json 에 저장
    python3 scripts/ga4_data.py --check           # 비었으면 1 로 끝난다
"""
import argparse
import datetime
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "ga4" / "weekly.json"
KST = datetime.timezone(datetime.timedelta(hours=9))

# 페이지 주소를 사람이 읽는 이름으로. 보고서에 /stock.html 보다
# '종목 리포트'가 낫다.
# 페이지 주소 → 사람이 읽는 이름. 실제 파일 이름이 대문자로 시작하므로
# (Home.html·Reports.html…) 그대로 적는다. 소문자로 적어 뒀더니 이름표가
# 하나도 안 붙어 보고서에 /Home.html 이 그대로 나갔다.
PAGE_NAMES = {
    "/": "홈",
    "/index.html": "홈",
    "/Home.html": "홈(구 주소)",
    "/brief.html": "모닝 브리핑",
    "/stock.html": "종목 리포트",
    "/Reports.html": "리포트 목록",
    "/industry.html": "업종 분석",
    "/Screener.html": "종목 검색",
    "/Watchlist.html": "관심종목",
    "/About.html": "회사 소개",
    "/Contact.html": "문의",
    "/Feedback.html": "의견 보내기",
    "/Login.html": "로그인",
    "/Signup.html": "회원가입",
    "/Consent.html": "약관 동의",
    "/Settings.html": "설정",
    "/Admin.html": "관리자",
    "/Privacy.html": "개인정보처리방침",
    "/Terms.html": "이용약관",
}

# 페이지를 세 갈래로 나눈다. 마케팅이 보는 것은 '콘텐츠'뿐이다.
#
#   2026-09-13 에 이걸 넣은 이유 — 8/24 주 조회의 28%가 내부였다.
#   로그인 240 · 동의 68 · 가입 33 · 관리자 49 가 다음 주에 한꺼번에
#   23 으로 떨어졌는데, 첫 보고서는 이걸 "이용자가 빠졌다"로 읽고
#   "링크가 끊겼을 수 있다"는 틀린 결론을 냈다. 사장이 그 주에 사이트
#   시험을 멈춘 것뿐이었다. 내 발자국을 손님 발자국으로 세면 안 된다.
CONTENT_PAGES = {"/", "/index.html", "/Home.html", "/brief.html", "/stock.html",
                 "/Reports.html", "/industry.html", "/Screener.html",
                 "/About.html", "/Contact.html", "/Feedback.html"}
ACCOUNT_PAGES = {"/Login.html", "/Signup.html", "/Consent.html", "/Settings.html",
                 "/Watchlist.html", "/Privacy.html", "/Terms.html",
                 "/auth-action.html"}
ADMIN_PAGES = {"/Admin.html"}


def page_kind(path):
    """'콘텐츠' · '계정' · '관리자' · '테스트' 중 하나."""
    p = (path or "").split("?")[0]
    if p.startswith("/staging/"):
        return "테스트"
    if p in ADMIN_PAGES:
        return "관리자"
    if p in ACCOUNT_PAGES:
        return "계정"
    if p in CONTENT_PAGES:
        return "콘텐츠"
    return "콘텐츠"          # 모르는 주소는 일단 콘텐츠로 본다


# GA4 가 주는 영어 이름을 사람 말로. 보고서를 읽는 사람이 개발자가 아니다.
CHANNEL_NAMES = {
    "Organic Search": "검색으로 들어옴",
    "Direct": "주소 직접·즐겨찾기",
    "Organic Social": "SNS",
    "Referral": "다른 사이트 링크",
    "Paid Search": "검색 광고",
    "Paid Social": "SNS 광고",
    "Email": "이메일",
    "Organic Video": "동영상",
    "Display": "배너 광고",
    "Unassigned": "분류 안 됨",
}
DEVICE_NAMES = {
    "mobile": "휴대폰",
    "desktop": "컴퓨터",
    "tablet": "태블릿",
    "smart tv": "TV",
}
SOURCE_NAMES = {
    "(direct)": "주소 직접·즐겨찾기",
    "google": "구글",
    "naver": "네이버",
    "daum": "다음",
    "t.co": "X(트위터)",
    "bing": "빙",
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _health(name, ok, note=""):
    return {"name": name, "ok": bool(ok), "note": note}


# ────────────────────────────── 자격 ──────────────────────────────

def _creds():
    """서비스 계정. GCP_SA_KEY(JSON 문자열) 나 파일 경로 둘 다 받는다."""
    from google.oauth2 import service_account
    raw = os.environ.get("GCP_SA_KEY", "").strip()
    if raw:
        info = json.loads(raw)
        return service_account.Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if path and Path(path).exists():
        return service_account.Credentials.from_service_account_file(
            path, scopes=["https://www.googleapis.com/auth/analytics.readonly"])
    raise SystemExit("❌ GCP_SA_KEY 가 없다 — GitHub 시크릿을 확인하라")


def whoami():
    """서비스 계정 이메일. GA4 에 이 이메일을 뷰어로 넣어야 한다.

    이메일은 비밀이 아니다(신분증이지 열쇠가 아니다). 열쇠인 private_key
    는 찍지 않는다. 구글 콘솔을 뒤지지 않아도 되게 여기서 꺼내 준다.
    """
    raw = os.environ.get("GCP_SA_KEY", "").strip()
    if raw:
        info = json.loads(raw)
    else:
        path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not (path and Path(path).exists()):
            raise SystemExit("❌ GCP_SA_KEY 가 없다")
        info = json.loads(Path(path).read_text(encoding="utf-8"))
    return info.get("client_email", ""), info.get("project_id", "")


def _client():
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    return BetaAnalyticsDataClient(credentials=_creds())


def _property():
    pid = (os.environ.get("GA4_PROPERTY_ID") or "").strip()
    if not pid:
        raise SystemExit("❌ GA4_PROPERTY_ID 가 없다 — GA4 관리>속성 의 숫자 9자리")
    return f"properties/{pid.lstrip('properties/')}"


# ────────────────────────────── 조회 ──────────────────────────────

def _run(client, prop, start, end, metrics, dimensions=None, limit=25, order=None,
         event_filter=None):
    """GA4 한 번 물어보기. (행 목록) 을 돌려준다.

    event_filter 를 주면 그 이름의 이벤트만 센다. 'sign_up 이 어느 페이지에서
    일어났나' 처럼, 같은 매개변수를 여러 이벤트가 공유할 때 꼭 필요하다 —
    안 거르면 모든 이벤트의 from_page 가 뭉쳐서 아무 뜻도 없는 수가 된다.
    """
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest, OrderBy,
        FilterExpression, Filter)
    req = RunReportRequest(
        property=prop,
        date_ranges=[DateRange(start_date=start, end_date=end)],
        metrics=[Metric(name=m) for m in metrics],
        dimensions=[Dimension(name=d) for d in (dimensions or [])],
        limit=limit,
    )
    if event_filter:
        req.dimension_filter = FilterExpression(filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=event_filter)))
    if order:
        req.order_bys = [OrderBy(metric=OrderBy.MetricOrderBy(metric_name=order),
                                 desc=True)]
    resp = client.run_report(req)
    out = []
    for r in resp.rows:
        row = {}
        for i, d in enumerate(dimensions or []):
            row[d] = r.dimension_values[i].value
        for i, m in enumerate(metrics):
            v = r.metric_values[i].value
            try:
                row[m] = float(v) if "." in v else int(v)
            except ValueError:
                row[m] = 0
        out.append(row)
    return out


def week_bounds(end_date, n):
    """[(월요일, 일요일)] n 개. 최근 것이 뒤로 간다.

    주는 월요일에 시작한다. 끝나지 않은 이번 주는 넣지 않는다 — 반쪽짜리
    주를 지난주와 나란히 놓으면 '반토막 났다'로 읽힌다.
    """
    last_sun = end_date - datetime.timedelta(days=(end_date.weekday() + 1) % 7)
    if last_sun >= end_date:
        last_sun -= datetime.timedelta(days=7)
    weeks = []
    for i in range(n):
        sun = last_sun - datetime.timedelta(days=7 * i)
        mon = sun - datetime.timedelta(days=6)
        weeks.append((mon, sun))
    return list(reversed(weeks))


def one_week(client, prop, mon, sun, deep=False):
    """한 주의 숫자. deep 이면 유입 경로·페이지까지 본다."""
    s, e = mon.isoformat(), sun.isoformat()
    core = _run(client, prop, s, e,
                ["totalUsers", "newUsers", "sessions", "engagedSessions",
                 "screenPageViews", "averageSessionDuration"])
    core = core[0] if core else {}

    # 재방문. newVsReturning 차원으로 갈라 본다 — totalUsers 에서 newUsers 를
    # 빼는 방식은 GA4 가 권하지 않는다(둘의 집계 기준이 달라 음수가 나온다).
    nvr = _run(client, prop, s, e, ["totalUsers"], ["newVsReturning"], limit=10)
    buckets = {r.get("newVsReturning", ""): r.get("totalUsers", 0) for r in nvr}

    row = {
        "week": mon.isoformat(),
        "to": sun.isoformat(),
        "users": core.get("totalUsers", 0),
        "newUsers": core.get("newUsers", 0),
        "returningUsers": buckets.get("returning", 0),
        "sessions": core.get("sessions", 0),
        "engagedSessions": core.get("engagedSessions", 0),
        "pageViews": core.get("screenPageViews", 0),
        "avgSessionSec": round(core.get("averageSessionDuration", 0) or 0),
    }
    if deep:
        row["channels"] = _run(client, prop, s, e, ["sessions", "totalUsers"],
                               ["sessionDefaultChannelGroup"], limit=12,
                               order="sessions")
        row["pages"] = _run(client, prop, s, e,
                            ["screenPageViews", "totalUsers", "userEngagementDuration"],
                            ["pagePath"], limit=20, order="screenPageViews")
        row["events"] = _run(client, prop, s, e, ["eventCount"],
                             ["eventName"], limit=30, order="eventCount")
        row["devices"] = _run(client, prop, s, e, ["totalUsers"],
                              ["deviceCategory"], limit=5, order="totalUsers")
        row["sources"] = _run(client, prop, s, e, ["sessions", "totalUsers"],
                              ["sessionSource"], limit=15, order="sessions")

        # ── 행동 ──────────────────────────────────────────────────
        # 아래는 GA4 '맞춤 측정기준' 등록이 필요한 것들이다. 등록 전에는
        # 400 이 나므로 하나씩 감싸서, 안 되는 것만 비워 두고 나머지는 살린다.
        # 통째로 터뜨리면 주간 보고가 통째로 못 나간다.
        def soft(name, metrics, dims, limit=15, order=None, filt=None):
            try:
                return _run(client, prop, s, e, metrics, dims, limit=limit,
                            order=order, event_filter=filt)
            except Exception as ex:
                row.setdefault("_missing", {})[name] = f"{type(ex).__name__}: {str(ex)[:120]}"
                return []

        # 어디로 들어와서 어디서 나가나
        row["landings"] = soft("landings", ["sessions", "bounceRate"],
                               ["landingPage"], order="sessions")
        # 재방문자는 뭘 보나 (신규와 갈라서)
        row["byVisitor"] = soft("byVisitor", ["screenPageViews"],
                                ["newVsReturning", "pagePath"], limit=30,
                                order="screenPageViews")
        # 가장 많이 본 리포트 · 가장 많이 눌린 종목
        row["tickers"] = soft("tickers", ["eventCount"],
                              ["eventName", "customEvent:ticker"], limit=40,
                              order="eventCount")
        # 어느 페이지에서 · 어느 유입처에서 가입했나
        row["signupPage"] = soft("signupPage", ["eventCount"],
                                 ["customEvent:from_page"], limit=15,
                                 order="eventCount", filt="sign_up")
        row["signupSource"] = soft("signupSource", ["eventCount"],
                                   ["customEvent:entry_source"], limit=15,
                                   order="eventCount", filt="sign_up")
        # 유입처별 방문자 (가입과 나란히 놓고 전환을 본다)
        row["entrySource"] = soft("entrySource", ["eventCount"],
                                  ["customEvent:entry_source"], limit=15,
                                  order="eventCount", filt="session_start")
        # 얼마나 내려 읽나
        row["scroll"] = soft("scroll", ["eventCount"],
                             ["customEvent:percent"], limit=6,
                             order="eventCount", filt="scroll_depth")
        # 어느 페이지에서 떠나나
        row["leave"] = soft("leave", ["eventCount"],
                            ["customEvent:from_page"], limit=15,
                            order="eventCount", filt="page_leave")
    return row


# GA4 에 실제로 뭘 물어볼 수 있는지 확인할 후보들.
#
#   추측으로 만들면 "된다더니 안 되네" 가 난다. 특히 customEvent: 로 시작하는
#   것들은 GA4 관리화면에서 '맞춤 측정기준' 으로 등록해야만 조회된다. 코드가
#   이벤트에 값을 실어 보내고 있어도 등록 전에는 안 나온다. 그 사실을 여기서
#   눈으로 확인하고 넘어간다.
PROBE_METRICS = [
    "totalUsers", "newUsers", "activeUsers", "sessions", "engagedSessions",
    "bounceRate", "engagementRate", "screenPageViews", "screenPageViewsPerSession",
    "averageSessionDuration", "userEngagementDuration", "eventCount",
    "keyEvents", "sessionsPerUser", "eventCountPerUser",
]
PROBE_DIMENSIONS = [
    "pagePath", "pageTitle", "landingPage", "landingPagePlusQueryString",
    "sessionSource", "sessionMedium", "sessionSourceMedium",
    "sessionDefaultChannelGroup", "firstUserDefaultChannelGroup", "firstUserSource",
    "newVsReturning", "deviceCategory", "eventName", "browser",
    "operatingSystem", "country", "city", "sessionCampaignName",
    # 실제로 우리가 보내는 매개변수 이름 그대로여야 한다. 다른 이름으로
    # 찔러 보면 "등록이 안 됐다" 와 "이름을 잘못 물었다" 가 구분되지 않는다.
    "customEvent:ticker", "customEvent:method", "customEvent:from_page",
    "customEvent:entry_source", "customEvent:entry_page", "customEvent:percent",
]


def probe(days=28):
    """뭐가 되고 뭐가 안 되는지 하나씩 물어본다. 되는 것만 쓴다."""
    from google.analytics.data_v1beta.types import (
        DateRange, Dimension, Metric, RunReportRequest)
    client, prop = _client(), _property()
    end = datetime.datetime.now(KST).date()
    start = end - datetime.timedelta(days=days)
    rng = [DateRange(start_date=start.isoformat(), end_date=end.isoformat())]

    def try_one(metrics, dimensions):
        try:
            r = client.run_report(RunReportRequest(
                property=prop, date_ranges=rng,
                metrics=[Metric(name=m) for m in metrics],
                dimensions=[Dimension(name=d) for d in dimensions], limit=3))
            rows = len(r.rows)
            sample = ""
            if r.rows and dimensions:
                sample = r.rows[0].dimension_values[0].value[:40]
            elif r.rows:
                sample = r.rows[0].metric_values[0].value[:20]
            return True, f"{rows}행 {sample}"
        except Exception as e:
            return False, f"{type(e).__name__}: {str(e)[:90]}"

    out = {"metrics": {}, "dimensions": {}}
    log(f"■ 지표 {len(PROBE_METRICS)}개 ({start} ~ {end})")
    for m in PROBE_METRICS:
        okx, note = try_one([m], [])
        out["metrics"][m] = {"ok": okx, "note": note}
        log(f"  {'✅' if okx else '❌'} {m:<30} {note}")
    log(f"\n■ 차원 {len(PROBE_DIMENSIONS)}개 (totalUsers 와 함께)")
    for d in PROBE_DIMENSIONS:
        okx, note = try_one(["totalUsers"], [d])
        out["dimensions"][d] = {"ok": okx, "note": note}
        log(f"  {'✅' if okx else '❌'} {d:<30} {note}")

    log("\n■ 우리가 쓰려는 조합")
    combos = [
        ("종목별 리포트 조회", ["eventCount"], ["eventName", "customEvent:ticker"]),
        ("유입처별 가입", ["eventCount"], ["customEvent:entry_source", "eventName"]),
        ("가입한 페이지", ["eventCount"], ["customEvent:from_page", "eventName"]),
        ("스크롤 깊이", ["eventCount"], ["customEvent:percent", "eventName"]),
        ("유입경로별 가입", ["eventCount"], ["sessionDefaultChannelGroup", "eventName"]),
        ("착지 페이지별 이탈", ["sessions", "bounceRate"], ["landingPage"]),
        ("재방문자가 보는 페이지", ["screenPageViews"], ["newVsReturning", "pagePath"]),
        ("페이지별 참여시간", ["userEngagementDuration"], ["pagePath"]),
    ]
    for name, ms, ds in combos:
        okx, note = try_one(ms, ds)
        out.setdefault("combos", {})[name] = {"ok": okx, "note": note,
                                              "metrics": ms, "dimensions": ds}
        log(f"  {'✅' if okx else '❌'} {name:<24} {note}")
    return out


def collect(weeks=8, today=None):
    """주간 숫자 + 건강 기록.

    건강 기록을 같이 돌려주는 이유는 다른 수집기와 같다 — 받는 쪽이
    '못 가져온 것'과 '진짜 0인 것'을 구분할 수 있어야 한다.
    """
    today = today or datetime.datetime.now(KST).date()
    bounds = week_bounds(today, weeks)
    try:
        client, prop = _client(), _property()
    except SystemExit as e:
        return {"weeks": [], "health": _health("GA4", False, str(e))}

    rows, problems = [], []
    for i, (mon, sun) in enumerate(bounds):
        deep = i >= len(bounds) - 2      # 최근 두 주만 자세히
        try:
            rows.append(one_week(client, prop, mon, sun, deep=deep))
        except Exception as ex:
            problems.append(f"{mon.isoformat()} 주 조회 실패: {type(ex).__name__} {ex}")

    if not rows:
        problems.append("한 주도 받지 못했다")
    elif rows and rows[-1]["users"] == 0:
        # 0 은 '아무도 안 왔다'일 수도 있지만, 권한이 빠져도 0 이 온다.
        # 구분할 수 없으니 문제로 적어 둔다.
        problems.append("가장 최근 주의 이용자가 0명이다 — 권한이나 속성 ID 를 확인하라")

    return {
        "collectedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "propertyId": os.environ.get("GA4_PROPERTY_ID", ""),
        "weeks": rows,
        "health": {"ok": not problems, "problems": problems},
    }


def merge_save(doc, path=None):
    """이번에 받은 주를 기존 기록에 합친다. 옛 주는 지우지 않는다.

    저장 위치는 Firestore 다 — 이 저장소는 공개라 여기 커밋하면 방문자
    수가 인터넷에 열린다(2026-09-13 에 실제로 76분간 열려 있었다).
    path 를 주면 그 파일에 쓴다. 시험할 때만 쓴다.
    """
    if path is not None:
        prev = {}
        if path.exists():
            try:
                prev = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                log(f"· 기존 파일을 읽지 못했다(새로 쓴다): {e}")
        merged = _merge(prev, doc)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return len(merged["weeks"])

    import ga4_store
    merged = _merge(ga4_store.load("weekly"), doc)
    ga4_store.save("weekly", merged)
    log(f"· 저장 위치: {ga4_store.where()}")
    return len(merged["weeks"])


def _merge(prev, doc):
    old = {w["week"]: w for w in (prev or {}).get("weeks") or []}
    for w in doc.get("weeks") or []:
        old[w["week"]] = w
    out = dict(doc)
    out["weeks"] = [old[k] for k in sorted(old)]
    return out


def show(doc):
    hs = doc.get("health") or {}
    for w in doc.get("weeks") or []:
        ret = w["returningUsers"]
        share = f"{ret / w['users'] * 100:.0f}%" if w["users"] else "—"
        log(f"  {w['week']}~{w['to'][5:]}  이용자 {w['users']:>5,}"
            f" (신규 {w['newUsers']:>5,} · 재방문 {ret:>5,} {share:>4})"
            f"  세션 {w['sessions']:>5,}  조회 {w['pageViews']:>6,}")
    if not hs.get("ok", True):
        for p in hs.get("problems") or []:
            log(f"  ⚠️ {p}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=8, help="몇 주치를 받을지")
    ap.add_argument("--write", action="store_true", help="data/ga4/weekly.json 에 저장")
    ap.add_argument("--check", action="store_true", help="비었으면 1 로 끝난다")
    ap.add_argument("--whoami", action="store_true", help="서비스 계정 이메일만 찍는다")
    ap.add_argument("--probe", action="store_true",
                    help="GA4 에 뭘 물어볼 수 있는지 하나씩 확인한다")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.whoami:
        email, proj = whoami()
        print(f"서비스 계정 : {email}")
        print(f"프로젝트    : {proj}")
        print()
        print("이 이메일을 GA4 에 뷰어로 넣어야 숫자를 읽을 수 있다.")
        print("  GA4 → 관리(왼쪽 아래 톱니) → 속성 → 속성 액세스 관리")
        print("  → 오른쪽 위 [+] → 사용자 추가 → 위 이메일 → 역할 '뷰어'")
        return 0

    if a.probe:
        out = probe()
        if a.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    doc = collect(a.weeks)
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    else:
        show(doc)
    if a.write:
        n = merge_save(doc)
        log(f"\n✅ {OUT.relative_to(ROOT)} · 모두 {n}주치")
    hs = doc.get("health") or {}
    if a.check and not hs.get("ok", True):
        for p in hs.get("problems") or []:
            print(f"::warning title=GA4 수집::{p}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
