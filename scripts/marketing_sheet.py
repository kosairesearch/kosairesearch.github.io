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

처음 한 번 — 사장이 한다 (5분)
  1. 구글 시트를 하나 만든다. 이름은 아무거나.
  2. 오른쪽 위 '공유' 에 서비스 계정 이메일을 '편집자' 로 넣는다.
     이메일은 GitHub Actions ▸ '주간 성과 보고' ▸ Run workflow ▸ setup 을
     켜고 돌리면 요약(Summary)에 나온다. 이메일은 비밀이 아니다.
  3. 시트 주소에서 /d/ 와 /edit 사이의 긴 글자를 복사해
     GitHub ▸ Settings ▸ Secrets ▸ MARKETING_SHEET_ID 에 넣는다.
  4. 구글 클라우드 콘솔 ▸ API 및 서비스 ▸ 'Google Sheets API' 를 켠다.
     (Firestore·GA4 와 같은 프로젝트다. 한 번만 켜면 된다.)

시크릿이 없으면 아무것도 안 하고 조용히 끝난다.
실패하면 0 이 아닌 값으로 끝난다 — 워크플로가 그 단계를 빨갛게 남기되
보고는 그대로 나간다. 조용히 넘어가서 한 주를 잃은 적이 있다(2026-09-14).

두 탭
  주간   한 주가 한 줄. A~V 열을 매번 다시 쓴다. 그 오른쪽(W 열부터)은
         건드리지 않는다 — 사장이 메모를 적는 자리다.
  실험   대장 그대로. 매번 통째로 다시 쓴다.

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

# 사람이 읽는 이름표다. 고치면 시트 첫 줄이 바뀐다 — 그래프가 그 줄을
# 가리키고 있으면 그래프도 손봐야 한다.
WEEK_HEAD = [
    "주(월요일)", "끝(일요일)", "방문자", "처음 온", "다시 온", "재방문율 %",
    "방문 횟수", "페이지 조회", "제대로 본 방문 %", "머문 시간(초)",
    "손님이 본 페이지", "우리 발자국 %", "회원가입", "관심종목 담기",
    "리포트 연 사람", "붙잡는 힘 % (1주 뒤)", "네이버", "구글", "주소 직접",
    "휴대폰 %", "4주 평균 방문자", "흔한 출렁임 %",
]
EXP_HEAD = [
    "번호", "제목", "상태", "볼 지표", "시작값", "제안일", "실행한 주",
    "판정", "판정 기준", "결과값", "변화 %", "왜", "할 일",
]


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _r(x, n=1):
    return round(x, n) if isinstance(x, (int, float)) else None


def _clean(rows):
    """None 은 빈칸으로. 시트에 null 을 보내지 않는다."""
    return [["" if v is None else v for v in row] for row in rows]


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
        # 붙잡는 힘. 가장 최근 주는 '1주 뒤' 창이 아직 안 지나서 몇 시간치만
        # 들어 있다 — 비워 둔다. 숫자판(latest_cohort)과 같은 규칙이다.
        hold = None
        if i < len(weeks) - 1:
            co = ret.get(w.get("week")) or {}
            b1 = (co.get("back") or {}).get("1")
            if b1 is not None and co.get("size"):
                hold = b1 / co["size"] * 100
        avg = M.four_week_avg(upto, lambda x: x.get("users"))
        rd = M.report_readers(w)
        rows.append([
            w.get("week"), w.get("to"),
            w.get("users"), w.get("newUsers"), w.get("returningUsers"),
            _r(M._rate(w.get("returningUsers"), w.get("users"))),
            w.get("sessions"), w.get("pageViews"),
            _r(M._rate(w.get("engagedSessions"), w.get("sessions")), 0),
            w.get("avgSessionSec"),
            kinds["콘텐츠"] if tot else None,
            _r(inner / tot * 100, 0) if tot else None,
            (evs.get("sign_up") or {}).get("eventCount"),
            (evs.get("watchlist_add") or {}).get("eventCount"),
            rd,
            _r(hold, 0),
            src.get("네이버"), src.get("구글"), src.get("주소 직접·즐겨찾기"),
            _r(dev.get("휴대폰"), 0),
            _r(avg, 0),
            _r(M.swing_pct(upto), 0),
        ])
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
        made = ensure_tabs(s, sid, [WEEK_TAB, EXP_TAB])
        wr = weekly_rows(doc)
        write(s, sid, WEEK_TAB, wr)
        er = experiment_rows(exp)
        write(s, sid, EXP_TAB, er, clear=True)
    except Exception as e:
        log(f"❌ 시트에 붙이지 못했다: {type(e).__name__} {e}")
        log("   서비스 계정을 시트에 '편집자' 로 공유했는지, 클라우드 콘솔에서"
            " Google Sheets API 를 켰는지 확인해라. 맨 위 설명 참고.")
        return 1
    log(f"✅ 시트에 붙였다 · 주간 {len(wr) - 1}줄 · 실험 {len(er) - 1}줄"
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
