#!/usr/bin/env python3
"""주간 숫자를 구글 시트에 한 줄씩 쌓는다 — 시간이 갈수록 한 눈에 보이게.

왜 시트인가
  월요일 보고는 그 주 하나를 보여 준다. "석 달 전보다 나아졌나" 는 줄을
  세워 놓고 봐야 보인다. 사장이 이미 쓰는 도구가 시트이고, 그래프는
  거기서 두 번 누르면 나온다. 2026-09-15 에 사장이 물었다 — "매주 지표들을
  시간 지날수록 한 눈에 볼 수 있게끔 스프레드시트를 만들까?"

왜 저장소가 아니라 시트인가
  이 저장소는 공개다. 2026-09-13 에 weekly.json 을 커밋했다가 76분간
  방문자 수·유입 경로가 인터넷에 열렸다. 시트는 사장과 서비스 계정만 본다.

칸 이름은 업계 용어로, 뜻은 설명 탭에 사장의 말로 쓴다
  처음엔 '우리 발자국 %' '붙잡는 힘 % (1주 뒤)' '흔한 출렁임 %' 라고
  썼다. 사장이 말했다 — "이게 도대체 뭔 뜻인지 모르겠어. 니만 알아들을 수
  있으면 되냐." 맞는 말이다. 이름표는 읽는 사람의 말이어야 한다. 그리고
  '설명' 탭에 칸마다 무슨 뜻인지, 어떻게 셌는지, 읽을 때 뭘 조심할지를
  적어 둔다. 새 칸을 넣으면 그 표에도 한 줄 넣어라 — 시험이 센다.
  그 뒤 2026-09-15 에 사장이 "업계에서 사용하는 용어가 있으면 업계 용어로
  바꿔줘" 라고 했다. 마케팅 회사에 보여 줄 스펙이기도 하다. 그래서 칸
  이름은 업계 용어(사용자·세션·페이지뷰·참여율·리텐션·전환·유입·DAU/MAU),
  뜻은 설명 탭에 사장의 말. 보고서는 쉬운 말 그대로라, 이름이 다른 칸은
  설명 탭에 "보고서의 'OO'" 라고 다리를 놓는다. 내가 만든 말은 여전히 금지.

처음 한 번 — 사장이 한다 (5분)
  1. 구글 시트를 하나 만든다. 이름은 아무거나.
  2. 오른쪽 위 '공유' 에 서비스 계정 이메일을 '편집자' 로 넣는다.
     이메일은 GitHub Actions ▸ '주간 성과 보고' ▸ Run workflow ▸ setup 을
     켜고 돌리면 요약(Summary)에 나온다. 이메일은 비밀이 아니다.
  3. 시트 주소에서 /d/ 와 /edit 사이의 긴 글자를 복사해
     GitHub ▸ Settings ▸ Secrets ▸ MARKETING_SHEET_ID 에 넣는다.
  4. 구글 클라우드 콘솔 ▸ API 및 서비스 ▸ 'Google Sheets API' 를 켠다.

시크릿이 없으면 아무것도 안 하고 조용히 끝난다.
실패하면 0 이 아닌 값으로 끝난다 — 워크플로가 그 단계를 빨갛게 남기되
보고는 그대로 나간다. 조용히 넘어가서 한 주를 잃은 적이 있다(2026-09-14).

세 탭
  주간   한 주가 한 줄. A 열부터 칸 수만큼(지금 AB 열까지)을 매번 다시 쓴다.
         그 오른쪽은 건드리지 않는다 — 사장이 메모를 적는 자리다.
  실험   대장 그대로. 매번 통째로 다시 쓴다.
  설명   주간·실험 탭의 칸마다 뜻·세는 법·조심할 것. 매번 통째로 다시 쓴다.

    python3 scripts/marketing_sheet.py          # 붙인다
    python3 scripts/marketing_sheet.py --show   # 붙일 줄만 찍어 본다 (시트 안 건드림)
"""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

API = "https://sheets.googleapis.com/v4/spreadsheets"
WEEK_TAB = "주간"
EXP_TAB = "실험"
DOC_TAB = "설명"

# ── 주간 탭 — (칸 이름, 무슨 뜻, 어떻게 셌나, 읽을 때 조심할 것) ─────────
# 칸 이름이 곧 시트 첫 줄이다. 순서가 곧 열 순서다. 고치면 그래프가 그
# 열을 가리키고 있는지 보라.
# 칸 이름은 업계 용어로 쓴다. 사장이 2026-09-15 에 "스프레드시트 항목 중에
# 업계에서 사용하는 용어가 있으면 업계 용어로 바꿔줘" 라고 했다(마케팅 회사에
# 보여 줄 스펙이기도 하다). 뜻은 설명 탭에 사장의 말로 푼다. 업계 용어가 없는
# 칸(관심종목 담기 같은 우리 사이트 행동)은 쉬운 말 그대로 둔다. 내가 만든 말
# ('발자국' '붙잡는 힘' '출렁임')은 업계 용어가 아니니 여전히 안 쓴다.
# 보고서는 쉬운 말을 쓰므로, 뜻 칸에 "보고서의 'OO'" 라고 다리를 놓는다.
WEEK_COLS = [
    ("주 시작(월)", "그 주 월요일 날짜", "", ""),
    ("주 끝(일)", "그 주 일요일 날짜", "", ""),
    ("사용자(명)", "그 주에 사이트에 온 사람 수. 한 사람이 세 번 와도 1명. 보고서의 '방문자'. 업계 말 Users · UV(순방문자)",
     "GA4 '총 사용자'. 브라우저 단위로 센다",
     "같은 사람이 휴대폰과 컴퓨터로 오면 2명으로 잡힌다"),
    ("신규 사용자(명)", "그 주에 생전 처음 온 사람 수. 보고서의 '처음'. 업계 말 New Users", "GA4 '새 사용자'",
     "신규 + 재방문 ≠ 사용자. 같은 주에 처음 오고 또 온 사람은 양쪽에 다 들어간다"),
    ("재방문 사용자(명)", "그 주에 왔는데 전에도 온 적이 있는 사람 수. 보고서의 '다시 온'. 업계 말 Returning Users", "GA4 '재방문'",
     "위와 같다. 둘을 더해서 사용자를 만들지 마라"),
    ("재방문율(%)", "재방문 사용자 ÷ 사용자 × 100. 이번 주 손님 중 전에도 왔던 사람의 비율", "",
     "리텐션이 아니다 — 새 손님이 몰리면 붙잡는 힘이 그대로여도 내려간다. 비율의 변화는 %p 로 읽는다. 14.4 → 17.1 은 '2.7%p 올랐다' 다"),
    # DAU·WAU·MAU 는 사장이 아는 말이라 풀어 쓰지 않고 그대로 쓴다
    # (2026-09-15 "그냥 내가 알고 있는 단어니까 단어 그대로 써줘").
    ("DAU(명)", "하루 평균 온 사람. 그 주 7일 각각 온 사람 수의 평균. Daily Active Users",
     "GA4 activeUsers 를 날짜별로 받아 7 로 나눈다", "아무도 안 온 날도 0 으로 쳐서 나눈다"),
    ("WAU(명)", "그 주 7일 동안 온 사람. Weekly Active Users", "GA4 active7DayUsers (그 주 일요일 기준)",
     "사용자와 거의 같다. 사용자는 한 번이라도 온 사람, WAU 는 그중 활동한 사람이라 몇 명 적을 수 있다"),
    ("MAU(명)", "그 주 일요일 기준으로 지난 28일 동안 한 번이라도 온 사람. Monthly Active Users",
     "GA4 active28DayUsers", "주 넷을 더한 것이 아니다. 같은 사람은 한 번만 센다"),
    ("DAU/MAU(%)", "DAU ÷ MAU × 100. 한 달에 온 사람이 하루에 몇 % 오나. 업계 말 Stickiness(습관)",
     "", "10% 면 한 달에 3일쯤 온다는 뜻. 매일 오는 사이트가 돈을 받는다"),
    ("세션(회)", "온 횟수. 한 사람이 세 번 오면 3회. 보고서의 '방문 횟수'. 업계 말 Sessions", "GA4 '세션'", ""),
    ("페이지뷰 PV(회)", "열린 페이지 수 전부. 보고서의 '페이지 조회'. 업계 말 Pageviews", "GA4 '조회수'",
     "우리가 본 것도 섞여 있다. '내부 트래픽 비율' 칸 참고"),
    ("참여율(%)",
     "세션 중, 10초 넘게 머물렀거나 2장 넘게 봤거나 가입 같은 행동을 한 세션의 비율. 보고서의 '제대로 본 방문'. 업계 말 Engagement Rate",
     "GA4 '참여 세션' ÷ 세션",
     "문턱이 낮아 늘 80%대다. 갑자기 떨어질 때만 뜻이 있다"),
    ("평균 세션 시간(초)", "세션 한 번당 평균 머문 시간. 보고서의 '머문 시간'. 업계 말 Avg. Session Duration", "GA4 '평균 세션 시간'", ""),
    ("내부 트래픽 뺀 PV(회)", "로그인·가입·동의·관리자·시험 페이지를 뺀 페이지뷰. 손님이 본 것에 가까운 숫자",
     "페이지 주소로 가른다", "업계에서 우리 회사 사람이 낸 방문을 '내부 트래픽(Internal Traffic)' 이라고 부른다"),
    ("내부 트래픽 비율(%)",
     "로그인·가입·동의·관리자·staging 페이지뷰가 전체 페이지뷰의 몇 % 인가. 보고서의 '우리 발자국'",
     "페이지 주소로 가른다",
     "대개 사장이 시험한 것이다. 2026-09-13 부터는 아예 안 보내므로 그 뒤로는 0 에 가까워진다"),
    ("가입 전환(건)", "회원가입을 끝낸 횟수. 업계에서 손님이 목표 행동을 마치는 것을 '전환(Conversion)' 이라고 한다",
     "약관 동의까지 마쳐 계정이 만들어진 순간 1건",
     "가입 페이지를 연 수가 아니다. 조회수도 아니다. 한 사람이 두 계정을 만들면 2건"),
    ("가입 전환 사용자(명)", "가입을 끝낸 사람 수", "위 건수를 사람으로 센 것",
     "2026-09-15 이후 받은 자료부터 있다. 그 전 주는 빈칸"),
    ("관심종목 담기(건)", "관심종목에 종목을 담은 횟수. 우리 사이트만의 행동이라 업계 용어가 없다",
     "로그인한 사람이 담기를 누를 때마다 1건", "한 사람이 열 개 담으면 10건"),
    ("관심종목 담은 사람(명)", "담은 사람 수", "위 건수를 사람으로 센 것",
     "33건이 3명일 수 있다. 사람 수를 봐야 한다"),
    ("리포트 조회 사용자(명)", "종목 리포트를 한 장이라도 연 사람 수. 보고서의 '리포트를 열어 봄'", "/stock.html 을 본 사람",
     "사용자 대비 몇 명인가가 퍼널(Funnel)의 첫 단계"),
    ("1주 리텐션(%)",
     "그 주에 처음 온 사람 가운데, 바로 다음 주에 다시 온 사람의 비율. 보고서의 '붙잡는 힘'. 업계 말 Week-1 Retention",
     "GA4 코호트(같은 주에 처음 온 사람 묶음)를 한 주 뒤까지 따라간다",
     "사이트가 손님을 붙잡는 힘이다. 재방문율과 다르다. 가장 최근 주는 다음 주가 아직 안 지나서 빈칸. 8주보다 오래된 주도 빈칸"),
    ("네이버 유입 세션(회)", "네이버 검색 등 네이버에서 들어온 세션 수. 업계 말 유입(Acquisition) · 소스(Source)",
     "GA4 유입 소스. 네이버 조각(m.search.naver.com 등)을 합쳤다",
     "'로그인하고 돌아옴' 은 뺐다 — 새 손님이 아니다"),
    ("구글 유입 세션(회)", "구글에서 들어온 세션 수", "GA4 유입 소스", ""),
    ("직접 유입 세션(회)", "주소를 직접 치거나 즐겨찾기로 온 세션 수. 업계 말 Direct", "GA4 'direct'", ""),
    ("모바일 비율(%)", "사용자 중 휴대폰으로 온 사람의 비율", "GA4 기기 카테고리",
     "나머지는 컴퓨터·태블릿"),
    ("직전 4주 평균 사용자(명)", "그 주를 뺀 앞 4주의 사용자 평균. 업계에서 견주는 기준을 '베이스라인(Baseline)' 이라고 한다", "",
     "앞주 한 주와 견주는 것보다 믿을 만한 기준"),
    ("사용자 WoW 변동폭(±%)",
     "지난 8주 동안 사용자가 주마다 오르내린 폭의 가운데값. WoW 는 Week over Week, 앞주 대비 변화율",
     "주간 변화율의 절댓값 중앙값",
     "이 폭 안의 변화는 우연일 수 있다. ±26% 면 +16% 는 흔한 출렁임이다"),
]
WEEK_HEAD = [c[0] for c in WEEK_COLS]

EXP_COLS = [
    ("번호", "실험 번호. 실행 표시할 때 이 번호를 적는다"),
    ("제목", "무엇을 하는 실험인가"),
    ("상태", "제안됨 → 진행중 → 끝남. 버림은 안 하기로 한 것"),
    ("지표", "효과를 잴 때 보는 칸. 업계 말 Metric"),
    ("기준값 Baseline", "실행 표시한 주의 그 숫자. 견주는 기준"),
    ("제안한 날", ""),
    ("실행 표시한 주", "사장이 '했다' 고 표시한 주"),
    ("판정", "효과 있음 · 변화 없음 · 역효과 · 잴 수 없음"),
    ("판정 기준", "수가 적을수록 문턱이 높다. 16건은 ±50%, 400건은 ±10%. 비율은 ±2%p"),
    ("측정값", "다음 주의 그 숫자"),
    ("변화율 Lift(%)", "기준값 대비 몇 % 움직였나. 업계에서 실험 효과의 크기를 Lift 라고 한다"),
    ("왜 하나", "어느 숫자 때문에 이 실험을 내놓았나"),
    ("무엇을 하나", "사람이 실제로 손댈 일"),
]
EXP_HEAD = [c[0] for c in EXP_COLS]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _r(x, n=1):
    return round(x, n) if isinstance(x, (int, float)) else None


def _clean(rows):
    """None 은 빈칸으로. 시트에 null 을 보내지 않는다."""
    return [["" if v is None else v for v in row] for row in rows]


def _people(week, name):
    """그 일을 한 사람 수. 옛 기록엔 없으므로 그때는 None."""
    got = _event(week, name)
    return got[0] if got and got[1] == "명" else None


def _event(week, name):
    import marketing_report as M
    return M.event_users(week, name)


def weekly_rows(doc):
    """[머리줄, 주1, 주2, …] 오래된 주가 위."""
    import marketing_report as M
    import ga4_data as G
    weeks = doc.get("weeks") or []
    ret = {c.get("week"): c for c in (doc.get("retention") or [])}
    rows = [WEEK_HEAD]
    for i, w in enumerate(weeks):
        upto = weeks[:i + 1]
        kinds, tot = M.split_pages(w)
        inner = kinds["계정"] + kinds["관리자"] + kinds["테스트"]
        evs = {e.get("eventName"): e for e in (w.get("events") or [])}
        src = dict(M.labeled(w, "sources", "sessionSource", "sessions", G.source_label))
        dev = dict(M.device_split(w))
        # 다음 주 다시 온 비율. 가장 최근 주는 다음 주가 아직 안 지나서 몇
        # 시간치만 들어 있다 — 비워 둔다. 숫자판(latest_cohort)과 같은 규칙.
        hold = None
        if i < len(weeks) - 1:
            co = ret.get(w.get("week")) or {}
            b1 = (co.get("back") or {}).get("1")
            if b1 is not None and co.get("size"):
                hold = b1 / co["size"] * 100
        avg = M.four_week_avg(upto, lambda x: x.get("users"))
        rows.append([
            w.get("week"), w.get("to"),
            w.get("users"), w.get("newUsers"), w.get("returningUsers"),
            _r(M._rate(w.get("returningUsers"), w.get("users"))),
            _r(w.get("dauAvg")), w.get("wau7"), w.get("mau28"), _r(w.get("stickiness")),
            w.get("sessions"), w.get("pageViews"),
            _r(M._rate(w.get("engagedSessions"), w.get("sessions")), 0),
            w.get("avgSessionSec"),
            kinds["콘텐츠"] if tot else None,
            _r(inner / tot * 100, 0) if tot else None,
            (evs.get("sign_up") or {}).get("eventCount"),
            _people(w, "sign_up"),
            (evs.get("watchlist_add") or {}).get("eventCount"),
            _people(w, "watchlist_add"),
            M.report_readers(w),
            _r(hold, 0),
            src.get("네이버"), src.get("구글"), src.get("주소 직접·즐겨찾기"),
            _r(dev.get("휴대폰"), 0),
            _r(avg, 0),
            _r(M.swing_pct(upto), 0),
        ])
    assert all(len(r) == len(WEEK_HEAD) for r in rows), "칸 수가 머리줄과 다르다"
    return _clean(rows)


def experiment_rows(exp):
    rows = [EXP_HEAD]
    for it in (exp or {}).get("items") or []:
        r = it.get("result") or {}
        rows.append([
            it.get("id"), it.get("title"), it.get("status"), it.get("metricLabel"),
            it.get("baseValue"), it.get("proposedAt"), it.get("startedWeek"),
            r.get("verdict"), r.get("rule"), r.get("now"), r.get("pct"),
            it.get("why"), it.get("action"),
        ])
    return _clean(rows)


def _col_letter(i):
    """0 → A, 25 → Z, 26 → AA. 자동으로 쓰는 칸 바로 오른쪽 열을 설명 탭에 적으려고."""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def explain_rows():
    """'설명' 탭. 주간 칸, 빈 줄, 실험 칸."""
    rows = [["[주간 탭]", "", "", ""],
            ["칸", "무슨 뜻인가", "어떻게 셌나", "읽을 때 조심할 것"]]
    rows += [list(c) for c in WEEK_COLS]
    rows += [["", "", "", ""],
             ["[실험 탭]", "", "", ""],
             ["칸", "무슨 뜻인가", "", ""]]
    rows += [[name, what, "", ""] for name, what in EXP_COLS]
    rows += [["", "", "", ""],
             ["이 탭과 주간·실험 탭의 첫 줄은 매주 자동으로 다시 씁니다. 손으로 고쳐도 다음 주에 돌아옵니다.", "", "", ""],
             [f"주간 탭의 오른쪽 빈 열({_col_letter(len(WEEK_HEAD))} 열부터)은 건드리지 않습니다. 메모는 거기에 적으세요.", "", "", ""]]
    return rows


# ── 구글 시트 ─────────────────────────────────────────────────────────

def session():
    """서비스 계정으로 시트 API 에 붙는다. 열쇠가 없으면 None."""
    raw = os.environ.get("GCP_SA_KEY", "").strip()
    if not raw:
        return None
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    cred = service_account.Credentials.from_service_account_info(
        json.loads(raw), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return AuthorizedSession(cred)


def _ok(resp, what):
    if resp.status_code >= 300:
        raise RuntimeError(f"{what}: HTTP {resp.status_code} {resp.text[:300]}")
    return resp


def ensure_tabs(s, sid, names):
    """없는 탭을 만든다. 만든 탭 이름 목록을 돌려준다."""
    r = _ok(s.get(f"{API}/{sid}", params={"fields": "sheets.properties.title"}), "시트 읽기")
    have = {sh["properties"]["title"] for sh in r.json().get("sheets", [])}
    missing = [n for n in names if n not in have]
    if missing:
        body = {"requests": [{"addSheet": {"properties": {"title": n}}} for n in missing]}
        _ok(s.post(f"{API}/{sid}:batchUpdate", json=body), "탭 만들기")
    return missing


def write(s, sid, tab, rows, clear=False):
    if clear:
        rng = quote(f"{tab}!A1:Z2000", safe="")
        _ok(s.post(f"{API}/{sid}/values/{rng}:clear"), f"{tab} 지우기")
    rng = quote(f"{tab}!A1", safe="")
    _ok(s.put(f"{API}/{sid}/values/{rng}", params={"valueInputOption": "USER_ENTERED"},
              json={"majorDimension": "ROWS", "values": rows}), f"{tab} 쓰기")


def push(s, sid, doc, exp):
    """붙인다. 0 이면 됐고, 1 이면 못 붙였다(이유는 로그에)."""
    try:
        made = ensure_tabs(s, sid, [WEEK_TAB, EXP_TAB, DOC_TAB])
        wr = weekly_rows(doc)
        write(s, sid, WEEK_TAB, wr)
        er = experiment_rows(exp)
        write(s, sid, EXP_TAB, er, clear=True)
        write(s, sid, DOC_TAB, explain_rows(), clear=True)
    except Exception as e:
        log(f"❌ 시트에 붙이지 못했다: {type(e).__name__} {e}")
        log("   서비스 계정을 시트에 '편집자' 로 공유했는지, 클라우드 콘솔에서"
            " Google Sheets API 를 켰는지 확인해라. 맨 위 설명 참고.")
        return 1
    log(f"✅ 시트에 붙였다 · 주간 {len(wr) - 1}줄 · 실험 {len(er) - 1}줄 · 설명 탭"
        + (f" · 새 탭 {', '.join(made)}" if made else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="붙일 줄만 찍어 본다")
    a = ap.parse_args()

    import ga4_store
    import experiments
    doc = ga4_store.load("weekly")
    exp = experiments.load()
    if a.show:
        for row in weekly_rows(doc):
            print("\t".join(str(v) for v in row))
        print()
        for row in experiment_rows(exp):
            print("\t".join(str(v) for v in row))
        return 0

    sid = os.environ.get("MARKETING_SHEET_ID", "").strip()
    if not sid:
        log("· MARKETING_SHEET_ID 가 없다 — 시트에는 붙이지 않는다. 붙이려면 맨 위 설명 참고.")
        return 0
    s = session()
    if s is None:
        log("❌ GCP_SA_KEY 가 없다 — 시트에 붙일 수 없다")
        return 1
    if not doc.get("weeks"):
        log("❌ 받아 둔 숫자가 없다 — 먼저 ga4_data.py --write")
        return 1
    return push(s, sid, doc, exp)


if __name__ == "__main__":
    sys.exit(main())
