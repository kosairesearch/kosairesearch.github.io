#!/usr/bin/env python3
"""첫 화면(index.html)의 매일 바뀌는 값을 실제 값으로 박아 넣는다 — 그리고 그 값의 정의를 한 곳에 둔다.

왜 있는가. 그 숫자가 index.html 에 손으로 적혀 있었고, 아무도 안 고쳤다.
그래서 리포트가 늘어날 때마다 조금씩 어긋났고(2,684 인데 실제는 2,686),
페이지가 뜬 뒤 자바스크립트가 뒤늦게 진짜 값으로 갈아 끼웠다. 방문자에게는
숫자가 한 번 튀는 것으로 보인다.

게다가 그 자바스크립트는 숫자 하나를 고치려고 data/reports-index.js 를 통째로
받았다 — 600KB다. 가장 많이 열리는 페이지에서 매번.

빌드할 때 맞는 값을 적어 두면 튈 일도, 받아 올 일도 없다. 리포트 워치독(30분 예약)과
모닝브리핑(발행 직후)이 이 스크립트를 부른다.

첫 화면은 새 디자인 랜딩이다(2026-10-03 실사이트 이전 · scripts/concepts/landing.py). 매일 바뀌는 값마다
data-live="이름" 표시가 있고, 이 스크립트가 그 자리를 고친다.

    rep    '국내 상장 N개 종목'의 N — 리포트가 있는 상장 종목 수(상장 종목 ∩ 리포트 색인). 홈 · 리포트 페이지
           머리 줄과 같은 정의다. 문서 제목 · 검색 설명 · 공유 설명에는 숫자를 두지 않으므로(2026-10-04 · 네이버 가이드 —
           메인 페이지 제목 · 설명을 자주 바꾸지 않는다) 머리는 고치지 않는다.
    sec    업종 분석 수 — 분석 글이 있는 대표 업종(sector_count)
    src    출처 평균 — 화면에 나오는 리포트의 출처 수 평균(sources_avg)
    brief  모닝브리핑 호수 — 가장 최근 호의 호수(발행할 때 적는 meta.issueNo · 없으면 발행한 브리핑 수 · brief_no)
    when   '지난해' — 바깥 통계(GAP)의 집계 해 다음 해에만 '지난해', 그 뒤는 'YYYY년'
    orb    첫 화면 행성의 반짝임 몫(최근 14일 리포트)

랜딩 생성기(landing.py)와 검사(check_seo.py 7번)도 여기 함수를 쓴다 — 세 곳이 같은 값을 낸다.
워치독은 패키지를 깔지 않으므로 이 파일은 표준 라이브러리만 쓴다.

사용
    python scripts/stamp_counts.py            # 고쳐 쓴다
    python scripts/stamp_counts.py --check    # 어긋났는지만 본다(고치지 않음)

어긋나 있으면 --check 는 1 로 끝난다. 표시를 하나라도 못 찾으면 고치지 않고 1 로 끝난다
(마크업이 바뀌었는데 이 스크립트만 그대로면 조용히 아무것도 안 하게 된다).
"""
import datetime
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "data" / "reports-index.js"
SECTORS = ROOT / "data" / "sectors.js"
STOCKS = ROOT / "data" / "stocks.js"
BRIEFS = ROOT / "data" / "briefs"
PAGE = ROOT / "index.html"

# 증권사 리포트가 없는 상장사 — 우리 데이터가 아니라 바깥 통계다(랜딩 숫자 절 · 사장 2026-10-01).
# 한국IR협의회 기업리서치센터가 해마다 2월쯤 전년 집계를 낸다 — 그때 이 넷을 고친다. 2025년: 2,674곳 중 1,573곳(뉴스핌 2026-02-11 보도)
GAP = {"year": 2025, "none": 1573, "total": 2674, "src": "한국IR협의회 기업리서치센터"}
ORB_SEED = 2680   # 첫 화면 구의 점 순서 — 고정 씨앗(빌드마다 같게)


def _payload(path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text[text.index("{"):text.rindex("}") + 1])


_CACHE = {}


def _data(name):
    if name not in _CACHE:
        _CACHE[name] = _payload({"index": INDEX, "stocks": STOCKS, "sectors": SECTORS}[name])
    return _CACHE[name]


def stock_count() -> int:
    """리포트 인덱스가 말하는 종목 수(stockCount = 상장 종목 수). 옛 첫 화면의 '리포트' 숫자였다 —
    새 상장이 리포트를 기다리는 동안 실제 리포트 수보다 많아서 report_count() 로 바꿨다."""
    payload = _data("index")
    n = payload.get("stockCount") or len(payload.get("reports") or {})
    if not n:
        raise SystemExit("stamp_counts: 종목 수를 읽지 못했습니다.")
    return int(n)


def report_count() -> int:
    """리포트가 있는 상장 종목 수 — 상장 종목(data/stocks.js) 가운데 리포트 색인에 있는 것.
    색인 항목 수(len)를 그대로 쓰면 상장폐지 종목이 색인에 남은 동안 많게 나오고(9/21 실측 2,682 · 실제 2,679),
    stockCount 를 쓰면 새 상장이 리포트를 기다리는 동안 많게 나온다(9/29 표시 2,684 · 실제 2,680).
    홈 · 리포트 페이지 머리 줄도 브라우저에서 같은 식(상장 종목 ∩ 색인)으로 센다."""
    reports = _data("index").get("reports") or {}
    listed = {s.get("ticker") for s in (_data("stocks").get("stocks") or []) if s.get("ticker")}
    n = len(listed.intersection(reports))
    if not n:
        raise SystemExit("stamp_counts: 리포트 수를 읽지 못했습니다.")
    return n


def sector_count() -> int:
    """업종 분석이 있는 대표 업종 수. 랜딩 새 디자인(concepts/landing.py)과 업종 페이지 상단
    (build_industry_comp.py)도 같은 규칙으로 센다 — 세 곳이 같은 수여야 한다.

    분석 글(data/sectors.js)을 그대로 세면 테마 둘('로봇' · '인공지능(AI)' — 여러 업종에 걸친
    묶음이라 대표 업종이 아니다)이 업종으로 들어간다. 그래서 종목의 대표 업종(data/stocks.js 의
    sector) 가운데 분석 글이 있는 것만 센다 — '기타' 는 분석 글이 없어 빠진다. 2026-10-02 에
    30 → 28(사장 "기타 포함하면 29개고 포함 안 하면 28개 맞아? 테마는 2개인데")."""
    sectors = _data("sectors").get("sectors") or {}
    reps = {s.get("sector") for s in (_data("stocks").get("stocks") or []) if s.get("sector")}
    n = len(reps.intersection(sectors))
    if not n:
        raise SystemExit("stamp_counts: 업종 수를 읽지 못했습니다.")
    return n


def sources_avg() -> str:
    """화면에 나오는 리포트(새 형식, 없으면 옛 형식)의 출처 수 평균 — 소수 첫째 자리까지('17.5')."""
    tot = n = 0
    for t in _data("index").get("reports") or {}:
        for d in ("reports_v2", "reports"):
            f = ROOT / "data" / d / f"{t}.json"
            if f.exists():
                tot += len(json.loads(f.read_text(encoding="utf-8")).get("sources") or [])
                n += 1
                break
    if not n:
        raise SystemExit("stamp_counts: 출처 평균을 읽지 못했습니다.")
    return f"{round(tot / n, 1):g}"


def _briefs():
    return sorted(p for p in BRIEFS.glob("*.json") if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem))


def brief_no() -> int:
    """모닝브리핑 호수 — 가장 최근에 발행한 호의 호수. 발행할 때 브리핑에 적는 meta.issueNo 다(2026-10-04 부터 · render_brief ·
    지난 호 페이지의 호수와 같다 — build_brief_comp.number_of). 적힌 호수가 없으면 발행한 브리핑 수(meta.publishedAt 이 있는 것).
    파일 수를 세면 발행하지 않은 원고(9월 13일 시험 원고 · 발행 대기 초안)까지 들어가 하나 많아진다(10/2 실측: 파일 32 · 발행 31)."""
    n, last = 0, None
    for p in _briefs():
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if (doc.get("meta") or {}).get("publishedAt"):
            n, last = n + 1, doc
    no = ((last or {}).get("meta") or {}).get("issueNo")
    return no if isinstance(no, int) and not isinstance(no, bool) and no > 0 else n


def today() -> datetime.date:
    """첫 화면의 '오늘' — 데이터 가운데 가장 늦은 날짜(시세 · 브리핑 · 리포트). concepts/data.py 의 now_date 와 같다."""
    ds = [str(_data("stocks").get("dataDate") or "")]
    bs = _briefs()
    if bs:
        ds.append(bs[-1].stem.replace("-", ""))
    ds += [str(r.get("reportDate", "")).replace("-", "") for r in (_data("index").get("reports") or {}).values() if r.get("reportDate")]
    d = max(x for x in ds if x)
    return datetime.date(int(d[:4]), int(d[4:6]), int(d[6:8]))


def gap_when(base=None) -> str:
    """바깥 통계의 해 — 집계 해 다음 해에만 '지난해'. 집계가 묵으면 '지난해'가 틀린 말이 된다."""
    base = base or today()
    return "지난해" if base.year == GAP["year"] + 1 else f"{GAP['year']}년"


def orb_json(base=None) -> str:
    """첫 화면 행성의 반짝임 몫 — 최근 14일 안에 새로 쓴 리포트(r)의 차례 번호와 전체 수(n).
    종목 순서는 고정 씨앗으로 섞어 빌드마다 같다(landing.py 의 ORB_JS 가 읽는다)."""
    base = base or today()
    index = _data("index").get("reports") or {}
    by = {s.get("ticker") for s in (_data("stocks").get("stocks") or [])}
    rnd = random.Random(ORB_SEED)
    tks = [t for t in index if t in by]
    rnd.shuffle(tks)
    recent = [i for i, t in enumerate(tks)
              if index[t].get("reportDate") and (base - datetime.date.fromisoformat(index[t]["reportDate"])).days <= 14]
    return json.dumps({"n": len(tks), "r": recent}, separators=(",", ":"))


def values() -> dict:
    """data-live 이름 → 지금 박아야 할 글."""
    base = today()
    return {"rep": f"{report_count():,}", "sec": str(sector_count()), "src": sources_avg(), "brief": str(brief_no()),
            "when": gap_when(base), "orb": orb_json(base)}


_LIVE = r'(<(span|script)\b[^>]*\sdata-live="%s"[^>]*>)(.*?)(</\2>)'


def stamp(html, vals=None):
    """(고친 글, 바뀐 것 목록, 못 찾은 표시 목록). 못 찾은 것이 있으면 그 자리는 그대로 둔다."""
    vals = vals or values()
    changes, missing = [], []
    for name, want in vals.items():
        pat = re.compile(_LIVE % re.escape(name), re.S)
        found = list(pat.finditer(html))
        if not found:
            missing.append(name)
            continue
        for m in found:
            if m.group(3) != want:
                changes.append(f"{name} {m.group(3)[:24]} → {want[:24]}")
        html = pat.sub(lambda m: m.group(1) + want + m.group(4), html)
    return html, changes, missing


def main() -> int:
    check = "--check" in sys.argv
    html = PAGE.read_text(encoding="utf-8")
    new, changes, missing = stamp(html)
    if missing:
        print(f"stamp_counts: index.html 에서 {', '.join(missing)} 자리를 찾지 못했습니다 — 고치지 않았습니다.", file=sys.stderr)
        return 1
    if not changes:
        print("stamp_counts: 그대로")
        return 0
    if check:
        for c in changes:
            print("stamp_counts: 어긋남 — " + c, file=sys.stderr)
        return 1
    PAGE.write_text(new, encoding="utf-8")
    print("stamp_counts: " + " · ".join(changes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
