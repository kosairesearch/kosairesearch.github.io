#!/usr/bin/env python3
"""생성된 브리핑을 brief.html 에 박는다.

generate_brief.py 가 만든 data/briefs/YYYY-MM-DD.json 을 읽어
brief.html 의 두 구역을 갈아끼운다.

  <!-- BRIEF:BODY:START -->  …  <!-- BRIEF:BODY:END -->   기사 본문
  /* BRIEF:I18N:START */     …  /* BRIEF:I18N:END */      영문 사전

왜 클라이언트에서 JSON 을 읽지 않고 HTML 에 굽나. 브리핑은 검색에서 들어오는
글이고, 자바스크립트로 본문을 채우면 크롤러가 빈 페이지를 본다. 그리고 이
사이트의 i18n 은 화면에 있는 한국어 텍스트를 키로 쓰는 방식이라, 본문이
나중에 생기면 사전을 등록할 시점을 맞추기 어렵다.

사전 키의 규칙이 하나 있다. 엔진(brief.html 의 norm)이 키를 만들 때
node.textContent 를 쓰므로, 키에는 태그가 없고 &amp; 같은 엔티티는 풀린
상태여야 한다. 그래서 문단마다 두 가지를 만든다 — 화면에 넣을 HTML 과
사전 키로 쓸 평문. 이 둘이 어긋나면 영어 모드에서 한국어가 그대로 남는다.

    python3 scripts/render_brief.py                      # 가장 최근 것
    python3 scripts/render_brief.py --date 2026-08-17
    python3 scripts/render_brief.py --check              # 쓰지 않고 검사만
"""
import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIEFS = ROOT / "data" / "briefs"
PAGE = ROOT / "brief.html"

BODY_START = "<!-- BRIEF:BODY:START"
BODY_END = "<!-- BRIEF:BODY:END -->"
I18N_START = "/* BRIEF:I18N:START"
I18N_END = "/* BRIEF:I18N:END */"

KST = datetime.timezone(datetime.timedelta(hours=9))

WEEK_KO = ["월", "화", "수", "목", "금", "토", "일"]
WEEK_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MON_EN = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

DISC_KO = ("본 자료는 공시(DART)·국내 시장 데이터와 공개된 해외 시장·일정 자료를 "
           "바탕으로 작성한 정보 제공 자료이며 투자 권유가 아닙니다. "
           "국내 수치는 {d} 종가 기준입니다.")
DISC_EN = ("This material is compiled from regulatory filings (DART), Korean market "
           "data and publicly available overseas market and calendar sources, for "
           "information purposes only. It is not investment advice. "
           "Korean figures are as of the {d} close.")

FIXED = {"모닝 브리핑": "Morning Brief"}

# coverage 섹션 위에 붙는 출처 표시. 글에서도 밝히지만(프롬프트 6-1항) 화면에서
# 한 번 더 보여 준다 — 이 섹션이 다른 섹션과 성격이 다르다는 걸 눈으로 알려야 한다.
COV_LABEL = ("KOSAI 리포트 확인 지점", "From KOSAI report checkpoints")
SUM_LABEL = ("요약", "In brief")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ────────────────────────────── 마크업 ──────────────────────────────

LINK = re.compile(r"\[([^\[\]]{1,80})\]\((\d{6})\)")
BOLD = re.compile(r"\*\*([^*]{1,200})\*\*")


def to_html(s):
    """생성기가 쓴 제한 마크업을 HTML 로. 먼저 escape 하므로 본문이 태그를
    끼워 넣을 수는 없다 — 링크와 굵게만 우리가 되살린다."""
    out = html.escape(s or "", quote=False)
    out = LINK.sub(lambda m: f'<a href="stock.html?ticker={m.group(2)}">{m.group(1)}</a>', out)
    out = BOLD.sub(r"<b>\1</b>", out)
    return out


def to_key(s):
    """사전 키 — 화면의 textContent 와 같아야 한다. 태그는 없고 엔티티는 풀린 상태."""
    out = LINK.sub(r"\1", s or "")
    out = BOLD.sub(r"\1", out)
    return re.sub(r"\s+", " ", out).strip()


def to_value(s):
    """영문 사전의 값.

    엔진은 값에 '<' 가 있으면 innerHTML 로, 없으면 textContent 로 넣는다
    (brief.html 의 data-i18n-block 처리). 그래서 태그가 없는 값을 이스케이프하면
    화면에 'S&amp;P 500' 이 글자 그대로 보인다. 태그가 생기는 값만 HTML 로 만들고,
    나머지는 평문 그대로 넘긴다.
    """
    out = to_html(s)
    if "<" in out:
        return out
    return re.sub(r"\s+", " ", s or "").strip()


# ────────────────────────────── 조립 ──────────────────────────────

def _dates(doc):
    d = datetime.date.fromisoformat(doc["date"])
    td = doc.get("tradeDate") or ""
    t = (datetime.date(int(td[:4]), int(td[4:6]), int(td[6:])) if len(td) == 8 else None)
    return d, t


def head_lines(doc, at=None):
    """머리의 날짜 줄과 기준일 줄. 사실에서 그대로 나오므로 모델을 거치지 않는다.

    브리핑에서 제일 틀리면 안 되는 게 '언제 기준이냐'다. 모델에게 맡길 자리가
    아니어서 여기서 만든다.

    날짜 옆에 발행 시각을 분까지 적는다(at). 아침 글은 몇 시에 나왔는지가
    정보다 — 07:27 과 09:10 은 읽는 사람에게 다른 글이다. 값은 이 함수를
    부르는 시점, 즉 페이지에 실제로 쓰는 순간이다.
    """
    d, t = _dates(doc)
    at = at or datetime.datetime.now(KST)
    hm = f"{at.hour:02d}:{at.minute:02d}"
    date_ko = f"{d.year}년 {d.month}월 {d.day}일 ({WEEK_KO[d.weekday()]}) {hm}"
    date_en = f"{WEEK_EN[d.weekday()]}, {MON_EN[d.month - 1]} {d.day}, {d.year} · {hm} KST"

    open_today = doc.get("marketOpen")
    if t:
        t_ko = f"{t.month}월 {t.day}일({WEEK_KO[t.weekday()]})"
        t_en = f"{WEEK_EN[t.weekday()]}, {MON_EN[t.month - 1]} {t.day}"
    else:
        t_ko = t_en = "—"

    if open_today:
        meta_ko = f"국내 증시 개장 · 직전 거래일 {t_ko} 종가 기준"
        meta_en = f"Korean markets open · Figures as of the {t_en} close"
    else:
        meta_ko = f"국내 증시 휴장 · 마지막 거래일 {t_ko} 종가 기준"
        meta_en = f"Korean markets closed · Figures as of the {t_en} close"

    disc_ko = DISC_KO.format(d=f"{t.year}년 {t.month}월 {t.day}일" if t else "직전 거래일")
    disc_en = DISC_EN.format(d=f"{MON_EN[t.month - 1]} {t.day}, {t.year}" if t else "prior session")
    return (date_ko, date_en), (meta_ko, meta_en), (disc_ko, disc_en)


def build(doc, at=None):
    """(본문 HTML, 영문 사전) 을 만든다."""
    (date_ko, date_en), (meta_ko, meta_en), (disc_ko, disc_en) = head_lines(doc, at)
    dic = dict(FIXED)
    dic[date_ko] = to_value(date_en)
    dic[meta_ko] = to_value(meta_en)
    dic[disc_ko] = to_value(disc_en)

    def pair(node, cls=None, tag="p"):
        """한 문단을 화면용 HTML 로 만들고 사전에 등록한다."""
        ko, en = (node.get("ko") or "").strip(), (node.get("en") or "").strip()
        if not ko:
            return None
        key = to_key(ko)
        if en:
            dic[key] = to_value(en)
        attr = f' class="{cls}"' if cls else ""
        return f'<{tag}{attr} data-i18n-block>{to_html(ko)}</{tag}>'

    L = ['    <header class="mb-head">',
         f'      <div class="mb-date">{html.escape(date_ko)}</div>']
    title_ko = (doc["title"].get("ko") or "").strip()
    if doc["title"].get("en"):
        dic[to_key(title_ko)] = to_value(doc["title"]["en"])
    L.append(f'      <h1>{to_html(title_ko)}</h1>')
    # 리드와 요약은 둘 다 '맨 위에서 오늘을 압축하는 자리'라 같이 두면 첫 문장이
    # 겹친다. 실제로 나란히 놓아 보니 두 블록이 거의 같은 말을 반복했다.
    # 그래서 요약이 있는 날은 리드를 화면에서 빼고 요약 하나만 보여 준다.
    # (리드는 JSON 에 그대로 남는다 — 워크플로 실행 요약이 그걸 쓴다.)
    sm = doc.get("summary") or {}
    has_sum = isinstance(sm.get("ko"), str) and bool(sm["ko"].strip())
    if not has_sum:
        lead = pair(doc["lead"], cls="mb-lead")
        if lead:
            L.append("      " + lead)
    L.append(f'      <div class="mb-meta">{html.escape(meta_ko)}</div>')
    L.append("    </header>")

    # 요약 — 제목 바로 아래, 본문 앞에. 훑고 나가는 사람을 위한 자리다.
    # 목록이 아니라 이어지는 문단 하나다(생성 규칙 9-1). 항목으로 쪼개 놓으면
    # 사람이 쓴 글로 읽히지 않는다.
    # summary 는 나중에 생긴 항목이라 옛 브리핑에는 없다. 없으면 통째로 건너뛴다.
    if has_sum:
        dic[SUM_LABEL[0]] = SUM_LABEL[1]
        row = pair(sm, cls="mb-sum-p")
        L.append("")
        L.append('    <aside class="mb-sum">')
        L.append(f'      <div class="mb-sum-h">{html.escape(SUM_LABEL[0])}</div>')
        L.append("      " + row)
        L.append("    </aside>")

    for sec in doc.get("sections") or []:
        h = sec.get("heading") or {}
        h_ko = (h.get("ko") or "").strip()
        if h.get("en"):
            dic[to_key(h_ko)] = to_value(h["en"])
        L.append("")
        if sec.get("id") == "coverage":
            dic[COV_LABEL[0]] = COV_LABEL[1]
            L.append('    <section class="mb-sec mb-sec--cov">')
            L.append(f'      <div class="mb-src">{html.escape(COV_LABEL[0])}</div>')
        else:
            L.append('    <section class="mb-sec">')
        L.append(f'      <h2>{to_html(h_ko)}</h2>')
        for p in sec.get("paragraphs") or []:
            row = pair(p)
            if row:
                L.append("      " + row)
        L.append("    </section>")

    L.append("")
    L.append(f'    <p class="mb-disc" data-i18n-block>{html.escape(disc_ko)}</p>')
    return "\n".join(L), dic


def dict_js(dic):
    """KOSi18n.register 블록. 키·값 모두 JSON 으로 이스케이프한다 —
    본문에 따옴표나 역슬래시가 있어도 스크립트가 깨지지 않게."""
    lines = ["/* BRIEF:I18N:START · scripts/render_brief.py 가 만든다 */",
             "if(window.KOSi18n) KOSi18n.register({"]
    items = list(dic.items())
    def js(x):
        # JSON 문자열 안의 '</' 는 </script> 로 읽혀 스크립트 태그를 닫을 수 있다.
        return json.dumps(x, ensure_ascii=False).replace("</", "<\\/")

    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append(f"  {js(k)}:{js(v)}{comma}")
    lines.append("});")
    lines.append(I18N_END)
    return "\n".join(lines)


def splice(page, body, dj):
    """두 구역만 갈아끼운다. 나머지(헤더·푸터·스타일)는 손대지 않는다."""
    for name, start, end in (("본문", BODY_START, BODY_END), ("사전", I18N_START, I18N_END)):
        if start not in page or end not in page:
            raise SystemExit(f"❌ brief.html 에서 {name} 표식을 찾지 못했습니다 ({start})")

    i = page.index(BODY_START)
    j = page.index(BODY_END) + len(BODY_END)
    marker = ("<!-- BRIEF:BODY:START · 여기부터 END 까지는 scripts/render_brief.py 가 만든다.\n"
              "         손으로 고치면 다음 생성에서 덮인다. -->")
    page = page[:i] + marker + "\n" + body + "\n    " + BODY_END + page[j:]

    i = page.index(I18N_START)
    j = page.index(I18N_END) + len(I18N_END)
    return page[:i] + dj + page[j:]


def verify(page, dic):
    """영어 모드에서 한국어가 남는 경로를 미리 잡는다.

    data-i18n-block 문단의 키가 사전에 없으면 그 문단은 영어 모드에서
    한국어로 남는다. 화면을 열어 보지 않으면 눈치채기 어려운 종류라서
    렌더링 직후에 확인한다.
    """
    body = page[page.index(BODY_START):page.index(BODY_END)]
    bad = []
    for m in re.finditer(r"<(p|h1|h2)[^>]*>(.*?)</\1>", body, re.S):
        text = re.sub(r"<[^>]+>", "", m.group(2))
        key = re.sub(r"\s+", " ", html.unescape(text)).strip()
        if key and key not in dic:
            bad.append(key[:60])
    return bad


def latest():
    files = sorted(p for p in BRIEFS.glob("*.json") if re.fullmatch(r"\d{4}-\d\d-\d\d", p.stem))
    return files[-1] if files else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD (기본: 가장 최근)")
    ap.add_argument("--check", action="store_true", help="쓰지 않고 검사만")
    ap.add_argument("--page", help="대상 HTML (기본 brief.html)")
    ap.add_argument("--at", help="발행 시각 HH:MM (기본: 지금. 테스트용)")
    a = ap.parse_args()

    src = (BRIEFS / f"{a.date}.json") if a.date else latest()
    if not src or not src.exists():
        log(f"❌ 브리핑 JSON 이 없습니다: {src or BRIEFS}")
        return 2
    doc = json.loads(src.read_text(encoding="utf-8"))

    at = datetime.datetime.now(KST)
    if a.at:
        h, m = a.at.split(":")
        at = at.replace(hour=int(h), minute=int(m))
    body, dic = build(doc, at)
    page_path = Path(a.page) if a.page else PAGE
    page = splice(page_path.read_text(encoding="utf-8"), body, dict_js(dic))

    missing = verify(page, dic)
    if missing:
        # 발행을 막지는 않는다 — 영어에서 한국어가 남는 것과 글이 아예 안
        # 나가는 것은 무게가 다르다. 대신 반드시 눈에 띄게 남긴다.
        log(f"⚠️ 영문 사전에 없는 문단 {len(missing)}건 — 영어 모드에서 한국어로 남는다")
        for k in missing[:5]:
            log(f"   · {k}…")

    n_para = body.count("data-i18n-block")
    if a.check:
        log(f"■ {src.name} · 문단 {n_para}개 · 사전 {len(dic)}항목 · 쓰지 않음(--check)")
        return 1 if missing else 0

    page_path.write_text(page, encoding="utf-8")
    # 발행 시각을 브리핑 파일에도 남긴다. 나중에 "그날 몇 시에 나갔나"를
    # 페이지가 아니라 기록에서 확인할 수 있어야 한다.
    doc.setdefault("meta", {})["publishedAt"] = at.isoformat(timespec="minutes")
    src.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"✅ {page_path.name} ← {src.name}  (발행 {at:%H:%M} KST)")
    log(f"   제목 {doc['title']['ko']}")
    log(f"   문단 {n_para}개 · 영문 사전 {len(dic)}항목 · "
        f"{'개장' if doc.get('marketOpen') else '휴장'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
