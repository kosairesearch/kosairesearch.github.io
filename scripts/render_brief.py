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

# ── 문단 자르기 ──────────────────────────────────────────────────────────
# 모델이 내주는 한 '문단' 이 500~650자다. 휴대폰에서 25줄쯤 이어져 벽처럼
# 보인다. 여기서 읽기 좋은 길이로 잘라 여러 <p> 로 내보낸다.
#
# 주의: 이 사이트의 i18n 은 화면의 한국어 텍스트를 키로 쓴다. 그래서 한국어만
# 자르면 잘린 조각들이 사전에 없어 영어 모드에서 한국어가 그대로 남는다.
# 한국어를 N 조각으로 자르면 영어도 반드시 같은 N 조각으로 맞춰 자른다.
PARA_KO = 170      # 한 문단 목표 글자 수(한글) — 휴대폰에서 대략 5~7줄
PARA_EN = 320

_SENT_RE = re.compile(r'(?<=[다요죠음함됨임]\.)\s+|(?<=[.!?])\s+(?=[A-Z가-힣"\'(])')


def split_sentences(t):
    return [x.strip() for x in _SENT_RE.split(t or "") if x and x.strip()]


def chunk_text(t, budget):
    """문장 경계에서만 자른다. 문장 중간은 절대 건드리지 않는다."""
    sents = split_sentences(t)
    if len(sents) < 2:
        return [t.strip()] if (t or "").strip() else []
    out, cur = [], ""
    for x in sents:
        nx = (cur + " " + x) if cur else x
        if cur and len(nx) > budget:
            out.append(cur)
            cur = x
        else:
            cur = nx
    if cur:
        out.append(cur)
    # 마지막 조각이 한 줄짜리 외톨이면 앞에 붙인다.
    #
    # 꺼내고 나서 붙인다. 한 줄로 쓰면 안 된다 —
    #     out[-2] = out[-2] + " " + out.pop()
    # 파이썬은 오른쪽을 먼저 계산하고 왼쪽 첨자를 그 뒤에 본다. pop 이 리스트를
    # 줄여 놓은 상태에서 out[-2] 를 평가하므로, 조각이 둘이면 IndexError 로
    # 죽고 셋 이상이면 한 칸 앞 문단에 갖다 붙인다. 실제로 2026-08-25 브리핑이
    # 이걸로 발행되지 못했다.
    #
    # stock.html 의 같은 로직(out[out.length-2] += ' '+out.pop())은 멀쩡하다.
    # 자바스크립트는 += 의 왼쪽 참조를 먼저 잡는다. 옮겨 적을 때 평가 순서가
    # 반대라는 걸 놓쳤다.
    if len(out) > 1 and len(out[-1]) < budget * 0.35:
        tail = out.pop()
        out[-1] = out[-1] + " " + tail
    return out


def group_evenly(sents, n):
    """문장 목록을 n 덩어리로 고르게 나눈다. 문장이 모자라면 None."""
    if n <= 1:
        return [" ".join(sents)]
    if len(sents) < n:
        return None
    return [" ".join(sents[len(sents) * i // n:len(sents) * (i + 1) // n])
            for i in range(n)]


def chunk_pair(ko, en):
    """(ko, en) 한 쌍을 같은 개수의 조각들로 자른다 → [(ko_i, en_i), ...]"""
    ko = (ko or "").strip()
    en = (en or "").strip()
    ko_parts = chunk_text(ko, PARA_KO)
    if len(ko_parts) <= 1:
        return [(ko, en)] if ko else []
    if not en:
        return [(k, "") for k in ko_parts]
    en_sents = split_sentences(en)
    n = len(ko_parts)
    en_parts = group_evenly(en_sents, n)
    if en_parts is None:
        # 영어 문장이 조각 수보다 적다 → 맞출 수 있는 만큼만 자른다.
        n = max(1, len(en_sents))
        ko_parts = group_evenly(split_sentences(ko), n) or [ko]
        en_parts = group_evenly(en_sents, n) or [en]
        if len(ko_parts) != len(en_parts):
            return [(ko, en)]          # 그래도 안 맞으면 자르지 않는다
    return list(zip(ko_parts, en_parts))


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
        L.append("")
        L.append('    <aside class="mb-sum">')
        L.append(f'      <div class="mb-sum-h">{html.escape(SUM_LABEL[0])}</div>')
        # 목록이 아니라 이어지는 문단이라는 규칙은 그대로다 — 항목으로 쪼개지
        # 않고, 읽기 좋은 길이에서 문단만 나눈다.
        for ko_c, en_c in chunk_pair(sm.get("ko"), sm.get("en")):
            row = pair({"ko": ko_c, "en": en_c}, cls="mb-sum-p")
            if row:
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
            for ko_c, en_c in chunk_pair(p.get("ko"), p.get("en")):
                row = pair({"ko": ko_c, "en": en_c})
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
    # 이미 발행된 브리핑이면 그때 시각을 그대로 쓴다. 표시만 손봐서 다시 그릴
    # 때 머리글의 시각이 지금으로 밀리면, 아침에 나간 글이 낮에 나온 것처럼
    # 보인다. --at 을 직접 주면 그쪽이 이긴다.
    _prev = (doc.get("meta") or {}).get("publishedAt") or ""
    if len(_prev) >= 16 and not a.at:
        try:
            at = at.replace(hour=int(_prev[11:13]), minute=int(_prev[14:16]))
        except ValueError:
            pass
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
    #
    # 한 번 찍힌 시각은 덮어쓰지 않는다. 문단 나누기처럼 표시만 손봐서 다시
    # 그릴 일이 있는데, 그때마다 시각이 밀리면 '아침 7시 브리핑' 이 오전
    # 11시에 나온 것처럼 보인다. 다시 그린 것과 다시 낸 것은 다르다.
    meta = doc.setdefault("meta", {})
    first_publish = not meta.get("publishedAt")
    if first_publish:
        meta["publishedAt"] = at.isoformat(timespec="minutes")
        src.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    # "2026-08-24T07:28+09:00" 에서 07:28 만. 뒤에서 다섯 글자를 집으면
    # 시간대(+09:00)를 집는다.
    _pa = meta.get("publishedAt", "")
    shown = _pa[11:16] if len(_pa) >= 16 else f"{at:%H:%M}"
    log(f"✅ {page_path.name} ← {src.name}  "
        f"({'발행' if first_publish else '다시 그림 · 발행'} {shown} KST)")
    log(f"   제목 {doc['title']['ko']}")
    log(f"   문단 {n_para}개 · 영문 사전 {len(dic)}항목 · "
        f"{'개장' if doc.get('marketOpen') else '휴장'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
