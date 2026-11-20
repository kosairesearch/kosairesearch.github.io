#!/usr/bin/env python3
"""상장 예정 종목의 증권신고서 · 투자설명서에서 요약재무정보와 공모 자금의 사용 목적을 읽는다(2026-11-18).

사장: "재무제표라든지 리포트에 필요한 다른 데이터들은 없어??"

상장 전 회사는 종목코드가 DART 회사 목록에 아직 없고 정기보고서도 없어, 리포트 생성기의 재무 조회(get_dart_financials ·
collect_quant)가 아무것도 받지 못한다. 그래서 상장 전 리포트는 검색에 걸린 기사로만 실적을 썼다. 회사가 공모 때 낸
증권신고서 · 투자설명서 원문(DART document.xml)의 '요약재무정보'에는 최근 3개 사업연도(감사의견 · 회계처리기준 포함)와
최근 반기 · 분기 실적이, '자금의 사용목적'에는 공모 자금의 쓰임이 있다. 2026-11-18 러너 진단(하나에어로다이내믹스 ·
에이엘로봇 · 유캐스트 · 엠비디 · 옵토닉스 등)으로 확인했다.

  · 회사는 정식 회사명으로 찾는다 — 안내의 '(주)하나에어로다이내믹스'에서 '(주)'를 뗀 이름이 DART 회사 목록의 이름과 같다.
    같은 이름이 여럿이면 공모 서류가 있는 회사를 고른다.
  · 서류는 가장 최근 것부터 읽는다 — 발행조건확정 뒤의 정정 투자설명서가 확정 공모가 기준이다. 요약재무정보를 읽지 못하면
    그 앞 서류로 간다(최대 MAX_DOCS 개).
  · 금액은 원 단위 정수로 바꿔 둔다(표의 단위 줄 '(단위 : 원 · 천원 · 백만원)'). 단위를 못 찾으면 원으로 보되, 자산총계가
    10억원보다 작으면 단위를 잘못 읽은 것으로 보고 버린다 — 열 배 · 천 배 틀린 숫자를 재료로 주지 않는다.
  · 연결 재무정보가 있으면 연결을 쓴다(사이트의 다른 리포트와 같은 기준).

DART 키(DART_API_KEY)는 러너에만 있다. 이 모듈은 받은 값을 data/ipo.json 의 종목 항목('filing')에 남기고, 지시문 ·
검사는 그 값을 쓴다(generate_reports.ipo_material · ipo_quant). 돈이 들지 않는다.
"""
import datetime
import io
import re
import zipfile
from collections import Counter

API = "https://opendart.fss.or.kr/api"
LOOKBACK_DAYS = 240
MAX_DOCS = 3
MIN_ASSETS = 1e9                    # 자산총계가 이보다 작으면 단위를 잘못 읽은 것으로 본다
CELL = re.compile(r"<(TD|TH|TE|TU)\b[^>]*>(.*?)</\1>", re.S | re.I)
ROW = re.compile(r"<TR\b.*?</TR>", re.S | re.I)
TABLE = re.compile(r"<TABLE\b.*?</TABLE>", re.S | re.I)
TITLE = re.compile(r"<TITLE\b[^>]*>(.*?)</TITLE>", re.S | re.I)
UNIT = re.compile(r"단위\s*[:：]?\s*(백만원|천원|원)")
UNIT_MUL = {"원": 1, "천원": 1_000, "백만원": 1_000_000}


def text_of(x):
    t = re.sub(r"<[^>]+>", " ", x or "")
    t = re.sub(r"&nbsp;|&#160;", " ", t).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", t).strip()


def norm_name(s):
    """'(주)하나에어로다이내믹스' · '주식회사 하나에어로다이내믹스' · '㈜ 하나에어로' → 공백 없는 회사 이름."""
    s = re.sub(r"\(\s*주\s*\)|㈜|주식회사", "", str(s or ""))
    return re.sub(r"\s+", "", s)


# ── 표 읽기 ───────────────────────────────────────────────────────────────────────────────────────
_FOOT = re.compile(r"\(\s*주\s*\d+\s*\)|주\s*\d+\)$")


def clean(cell):
    """칸 글에서 각주 표시('(주1)' · '주1)')를 걷는다."""
    return re.sub(r"\s+", " ", _FOOT.sub("", str(cell or ""))).strip()


def num(cell):
    """'19,938,875,952' → 19938875952 · '(3,947,731,721)' · '△1,234' · '-1,234' → 음수 · '-' · '' → None."""
    t = re.sub(r"\s+", "", clean(cell))
    if not t or t in {"-", "–", "—"}:
        return None
    neg = t.startswith(("(", "△", "▲", "-", "−"))
    t = t.strip("()△▲-−")
    if not re.fullmatch(r"[0-9][0-9,]*(?:\.[0-9]+)?", t):
        return None
    v = float(t.replace(",", ""))
    return -v if neg else v


_TAGS = (("반기", 6), ("1분기", 3), ("3분기", 9))


def period(label):
    """열 머리 → {'y': 끝 해, 'm': 끝 달 | None, 'months': 기간 개월 | None, 'tag': '반기' · '1분기' · '3분기' · ''}.
    '제20기(2026년6월말)' · '제 10 기 반기말(2026년 06월말)' · '(2025.01.01~2025.12.31)' · '2026년 1월 1일~2026년 6월 30일' ·
    '제12기 반기(2026.01.01~06.30)' · '2026년도 반기(제8기 반기)' · '2025년(제29기)'. 연도가 없으면 None."""
    t = re.sub(r"\s+", "", clean(label))
    tag = next((k for k, _ in _TAGS if k in t), "")
    rg = re.search(r"(\d{4})[.년](\d{1,2})[.월](\d{1,2})일?\.?~(?:(\d{4})[.년])?(\d{1,2})[.월](\d{1,2})", t)
    if rg:
        y1, m1 = int(rg.group(1)), int(rg.group(2))
        y2, m2 = int(rg.group(4) or y1), int(rg.group(5))
        months = (y2 - y1) * 12 + m2 - m1 + 1
        if 1 <= m1 <= 12 and 1 <= m2 <= 12 and 1 <= months <= 12:
            return {"y": y2, "m": m2, "months": months, "tag": tag}
    pt = re.search(r"((?:19|20)\d{2})(?:년|\.)(\d{1,2})(?:월|\.\d{1,2}|$|\))", t)
    if pt and 1 <= int(pt.group(2)) <= 12:
        return {"y": int(pt.group(1)), "m": int(pt.group(2)), "months": None, "tag": tag}
    yr = re.search(r"((?:19|20)\d{2})년", t)
    if yr:
        return {"y": int(yr.group(1)), "m": None, "months": None, "tag": tag}
    return None


_LABELS = (
    # (칸, 행 이름 무늬) — 공백 · 번호 · 머리 기호 · 끝의 괄호를 걷은 이름에 대고 본다. 앞에 있는 것이 먼저다.
    ("std", r"^회계처리기준$"),
    ("audit", r"^감사인\(감사의견\)$|^감사인및감사의견$"),
    ("auditor", r"^감사인$"),
    ("opinion", r"^감사의견$"),
    ("assets", r"^(?:자산총계|자산합계|총자산)$"),
    ("liab", r"^(?:부채총계|부채합계|총부채)$"),
    ("equity", r"^(?:자본총계|자본합계|총자본)$"),
    ("rev", r"^(?:매출액|매출|영업수익|수익)$"),
    ("op", r"^(?:영업이익|영업손실|영업손익)$"),
    ("np", r"^(?:연결)?(?:당기|분기|반기|분\(반\)기|반\(분\)기)?(?:순이익|순손실|순손익)$"),
    ("np_owner", r"^지배(?:기업|회사)?(?:의)?(?:소유주|주주)?(?:지분)?(?:에게)?(?:귀속(?:되는)?)?(?:당기|분기|반기)?(?:순이익|순손실|순손익)"),
    ("owner", r"^지배(?:기업|회사)?(?:의)?(?:소유주|주주)?(?:지분|몫)$"),
)


def row_key(label):
    """행 이름 → 칸. 'Ⅰ.유동자산' · '(1)매출채권' · 'ㆍ당좌자산' · '[자본금]' · '- 지배회사지분순이익' · '영업이익(영업손실)' ·
    '(감사의견)' 같은 머리 · 꼬리를 걷고 본다."""
    t = re.sub(r"\s+", "", clean(label))
    if re.fullmatch(r"\((.+)\)", t):
        t = t[1:-1]
    t = re.sub(r"^(?:[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\.?|[IVX]+\.|\d+\.|\(\d+\)|[①-⑳]|[가-하]\.|[ㆍ·•\-–])+", "", t)
    t = t.strip("[]【】<>")
    if not t.startswith("감사인("):
        t = re.sub(r"(?:\([^()]*\))+$", "", t)          # '영업이익(손실)' · '당기순이익(당기순손실)' · '매출액(영업수익)'
    for key, pat in _LABELS:
        if re.search(pat, t):
            return key
    return None


def _cells(seg):
    """구간 안의 표를 차례대로 — (표 앞 글, [행: [칸 글]])."""
    out, pos = [], 0
    for m in TABLE.finditer(seg):
        pre = text_of(seg[pos:m.start()])
        rows = [[text_of(c[1]) for c in CELL.findall(tr)] for tr in ROW.findall(m.group(0))]
        out.append((pre, [r for r in rows if any(x for x in r)]))
        pos = m.end()
    return out


def _sections(doc, pat):
    titles = [(m.start(), text_of(m.group(1))) for m in TITLE.finditer(doc)]
    out = []
    for i, (pos, t) in enumerate(titles):
        if re.search(pat, t):
            out.append(doc[pos:(titles[i + 1][0] if i + 1 < len(titles) else len(doc))])
    return out


_BASIS = re.compile(r"(연결|별도|개별)\s*(?:요약)?\s*재무|요약\s*(연결|별도|개별)")


def _unit_row(cells):
    """단위만 적은 줄('(단위 : 천원)' · '(기준일 : | 2026년 09월 21일 | ) | (단위 : 백만원)') → 배수. 아니면 None."""
    u = UNIT.findall(" ".join(cells))
    if u and not any(num(c) is not None for c in cells) and len(cells) <= 4:
        return UNIT_MUL[u[-1]]
    return None


def parse_summary(doc):
    """요약재무정보 → {'basis': '연결'|'', 'fy_end_month': 12, 'periods': [...]} · 읽지 못하면 None.

    periods 는 끝 시점 순 — {'end': '2025-12', 'months': 12, 'std', 'audit', 'rev', 'op', 'np', 'np_owner', 'assets', 'liab',
    'equity', 'equity_owner'}(없는 칸은 뺀다 · 금액은 원 단위 정수). 같은 표 안에서 재무상태표 머리('제20기(2026년6월말)')와
    손익 머리('(2026.1.1.~2026.06.30.)')가 따로 있으면 끝 시점으로 잇는다."""
    sets = []                                       # 열 묶음 — {'basis', 'unit', 'heads': [period], 'vals': {칸: [값]}}
    for seg in _sections(doc, r"요약.*재무|재무.*요약"):
        basis, unit = "", None
        for pre, rows in _cells(seg):
            b = _BASIS.findall(pre)
            if b:
                w = [x for pair in b for x in pair if x][-1]
                basis = "연결" if w == "연결" else "별도"
            u = UNIT.findall(pre)
            if u:
                unit = UNIT_MUL[u[-1]]
            cur, anchor = None, None
            for cells in rows:
                um = _unit_row(cells)
                if um:
                    unit = um
                    continue
                heads = [period(c) for c in cells]
                if sum(1 for h in heads if h) >= 2 and not any(num(c) is not None for c in cells):
                    hs = heads if heads[0] else heads[1:]
                    cur = {"basis": basis, "unit": unit, "heads": hs, "vals": {}}
                    sets.append(cur)
                    anchor = None
                    continue
                if cur is None or len(cells) < 2:
                    continue
                key = row_key(cells[0])
                if key in ("np", "equity"):
                    anchor = key
                if key == "owner":
                    key = "np_owner" if anchor == "np" else "equity_owner"
                if not key or key in cur["vals"]:
                    continue
                cur["vals"][key] = [clean(c) for c in cells[1:1 + len(cur["heads"])]]
    if not sets:
        return None
    # 결산월 — 반기 · 분기 표시가 없고 12개월(또는 기간 모름)인 열의 끝 달 가운데 가장 많은 것
    fy = Counter(h["m"] for s in sets for h in s["heads"] if h and h["m"] and not h["tag"]
                 and (h["months"] in (None, 12))).most_common(1)
    fy_m = fy[0][0] if fy else 12
    groups = {}
    for s in sets:
        g = groups.setdefault(s["basis"], {})
        for i, h in enumerate(s["heads"]):
            if not h:
                continue
            months = h["months"] or dict(_TAGS).get(h["tag"]) or (12 if not h["m"] or h["m"] == fy_m else (h["m"] - fy_m) % 12)
            m = h["m"] or ((fy_m + months - 1) % 12 + 1)
            p = g.setdefault((h["y"], m), {})
            if h["months"] or "months" not in p:
                p["months"] = months
            for key, vals in s["vals"].items():
                if i >= len(vals) or not vals[i] or vals[i] in {"-", "–"}:
                    continue
                if key in ("std", "audit", "auditor", "opinion"):
                    p.setdefault(key, vals[i][:40])
                    continue
                v = num(vals[i])
                if v is None:
                    continue
                if s["unit"] is None:
                    p.setdefault("_nounit", True)
                p.setdefault(key, v * (s["unit"] or 1))
    # 손익이 있는 기준을 고른다 — 연결이 있으면 연결
    def has_pl(g):
        return any(any(k in p for k in ("rev", "op", "np")) for p in g.values())
    pick = next((b for b in ("연결", "별도", "") if b in groups and has_pl(groups[b])), None)
    if pick is None:
        return None
    periods = []
    for (y, m), p in sorted(groups[pick].items()):
        if p.get("assets") is not None and abs(p["assets"]) < MIN_ASSETS:
            return None                             # 단위를 잘못 읽었다(천원 · 백만원을 원으로)
        if all(p.get(k) is not None for k in ("assets", "liab", "equity")) \
                and abs(p["assets"] - p["liab"] - p["equity"]) > abs(p["assets"]) * 0.01:
            return None                             # 자산 = 부채 + 자본이 맞지 않으면 열이 어긋난 것이다
        row = {"end": f"{y}-{m:02d}", "months": p["months"]}
        if p.get("std"):
            row["std"] = p["std"]
        who = p.get("auditor") if p.get("auditor") not in (None, "-") else ""
        what = p.get("opinion") if p.get("opinion") not in (None, "-") else ""
        audit = p.get("audit") or (f"{who}({what})" if who and what else who or what)
        if audit:
            row["audit"] = audit
        for k in ("rev", "op", "np", "np_owner", "assets", "liab", "equity", "equity_owner"):
            if p.get(k) is not None:
                row[k] = int(round(p[k]))
        if any(k in row for k in ("rev", "op", "np", "assets")):
            periods.append(row)
    if not any(r["months"] == 12 and any(k in r for k in ("rev", "op", "np")) for r in periods):
        return None
    return {"basis": "연결" if pick == "연결" else "", "fy_end_month": fy_m, "periods": periods}


_USES = ("시설자금", "영업양수자금", "운영자금", "채무상환자금", "타법인증권취득자금", "기타")


def parse_funds(doc):
    """'자금의 사용목적' → {'net': 순수입금, 'uses': [{'use': '시설자금', 'amt': 원}]}(0 · 빈 칸 · 합계는 뺀다). 못 읽으면 {}.
    사용 계획 표의 단위('(단위 : 백만원)')를 못 찾으면 순수입금(원)과 합계를 견주어 정한다."""
    for seg in _sections(doc, r"자금의\s*사용\s*목적"):
        unit, net, uses = None, None, None
        for pre, rows in _cells(seg):
            u = UNIT.findall(pre)
            if u:
                unit = UNIT_MUL[u[-1]]
            for i, cells in enumerate(rows):
                um = _unit_row(cells)
                if um:
                    unit = um
                    continue
                lab = re.sub(r"\s+", "", cells[0]) if cells else ""
                if net is None and lab.startswith("순수입금") and len(cells) >= 2:
                    v = num(cells[1])
                    if v and v > 0:
                        net = v * (unit or 1)
                names = [re.sub(r"\s+", "", c) for c in cells]
                if uses is None and sum(1 for n in names if n in _USES) >= 3 and i + 1 < len(rows):
                    vals = [num(c) for c in rows[i + 1]]
                    if len(vals) == len(names) and any(v for v in vals):
                        uses = ([(n, v) for n, v in zip(names, vals) if n in _USES and v and v > 0], unit,
                                next((v for n, v in zip(names, vals) if n in ("계", "합계")), None))
        if not uses or not uses[0]:
            continue
        items, mul, total = uses
        tot = total or sum(v for _, v in items)
        # 단위는 순수입금(원)과 합계가 1% 안에서 맞는 것으로 정한다 — 사용 계획 표의 단위 줄이 없으면 앞 표(자금조달금액 · 원)의
        # 단위를 이어 읽게 되므로, 적힌 단위보다 이 대조를 믿는다. 순수입금이 없으면 적힌 단위로 읽되 합계가 1억원 미만이면 버린다.
        fit = [k for k in (1, 1_000, 1_000_000) if net and tot and abs(tot * k - net) <= net * 0.01]
        if fit:
            mul = fit[0]
        elif not mul or tot * mul < 1e8 or (net and abs(tot * mul - net) > net * 0.5):
            return {}
        out = {"uses": [{"use": n, "amt": int(round(v * mul))} for n, v in items]}
        if net:
            out["net"] = int(round(net))
        return out
    return {}


# ── 작성 재료 · 검사 값 ───────────────────────────────────────────────────────────────────────────
def _label(p, fm):
    """기간 이름 — 연간 '2025년'(결산월이 12월이 아니면 '2025년 3월 결산') · 누적 '2026년 상반기(1~6월)'."""
    y, m = (int(x) for x in p["end"].split("-"))
    n = p.get("months") or 12
    if n == 12:
        return f"{y}년" if fm == 12 else f"{y}년 {fm}월 결산"
    if fm == 12:
        return {3: f"{y}년 1분기(1~3월)", 6: f"{y}년 상반기(1~6월)", 9: f"{y}년 1~9월(3분기 누적)"}.get(n, f"{y}년 1~{m}월")
    sy, sm = (y, m - n + 1) if m - n + 1 >= 1 else (y - 1, m - n + 13)
    return f"{sy}년 {sm}월~{y}년 {m}월({n}개월 누적)"


def _amt(v, name, loss_name=None):
    """'영업손실 10.1억원[KRW 1.01 billion]'(손익은 이름으로 가른다) · '자본총계 -49.5억원[KRW -4.95 billion]'(그 밖은 부호)."""
    import fin_material as F
    if loss_name and v < 0:
        name = loss_name
    sign = "-" if v < 0 and not loss_name else ""
    return f"{name} {sign}{F.won(v)}[{F.won_en(v).replace('KRW ', 'KRW ' + sign)}]"


def material_lines(fin):
    """[증권신고서 요약재무정보] 블록 — 작성 지시문에 넣는다. 금액은 본문 표기(fin_material.won)로 미리 바꾸고, 증감은 코드가 센다.
    금액 뒤 [ ] 안은 영어(en) 본문 표기다(공시 실적 재료와 같은 관례). 없으면 ''."""
    import fin_material as F
    if not isinstance(fin, dict) or not fin.get("periods"):
        return ""
    fm = fin.get("fy_end_month") or 12
    ps = fin["periods"]
    d = str(fin.get("rcept_dt") or "")
    when = f"{int(d[:4])}년 {int(d[5:7])}월 {int(d[8:10])}일" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) else ""
    doc = re.sub(r"^\[[^\]]*\]", "", str(fin.get("report_nm") or "투자설명서")).strip() or "투자설명서"
    head = (f"[증권신고서 요약재무정보 — 회사가 공모 때 낸 {doc}{f'({when} 접수)' if when else ''}"
            f"{' · 연결 기준' if fin.get('basis') == '연결' else ''} · 금액은 이 표기 그대로 본문에 옮긴다"
            " · [ ] 안은 영어(en) 본문에만 대괄호 없이 쓰는 표기]")
    lines = [head]
    annual = [p for p in ps if (p.get("months") or 12) == 12]
    by_end = {p["end"]: p for p in ps}
    for p in ps:
        lb = _label(p, fm)
        audit = re.sub(r"\s+", " ", re.sub(r"\s*\(\s*([^()]*?)\s*\)", r" \1", p.get("audit") or "")).strip()
        meta = " · ".join(x for x in (p.get("std"), audit) if x)
        parts = []
        prev = None
        if (p.get("months") or 12) == 12:
            i = annual.index(p)
            prev = annual[i - 1] if i else None
        else:
            y, m = p["end"].split("-")
            q = by_end.get(f"{int(y) - 1}-{m}")
            prev = q if q and q.get("months") == p.get("months") else None
        for key, nm, loss in (("rev", "매출", None), ("op", "영업이익", "영업손실"), ("np", "당기순이익", "당기순손실"),
                              ("np_owner", "지배주주 순이익", "지배주주 순손실")):
            v = p.get(key)
            if v is None or (key == "np_owner" and v == p.get("np")):
                continue
            c = F.chg(v, (prev or {}).get(key), profit=bool(loss)) if prev else ""
            tag = "전년 대비" if (p.get("months") or 12) == 12 else "전년 같은 기간 대비"
            parts.append(_amt(v, nm, loss) + (f"({tag} {c})" if c else ""))
        if not parts:
            parts.append("손익 자료 없음")
        lines.append(f"- {lb}{f'({meta})' if meta else ''}: " + " · ".join(parts))
    # 끝 시점의 재무상태 — 가장 최근 연간과 그 뒤 누적 기간
    for p in ps[-2:] if len(ps) > 1 and (ps[-1].get("months") or 12) != 12 else ps[-1:]:
        y, m = (int(x) for x in p["end"].split("-"))
        bs = [_amt(p[k], nm) for k, nm in (("assets", "자산총계"), ("liab", "부채총계"), ("equity", "자본총계")) if p.get(k) is not None]
        if bs:
            note = " — 자본총계가 마이너스인 자본잠식 상태" if (p.get("equity") or 0) < 0 else ""
            lines.append(f"- {y}년 {m}월 말 " + " · ".join(bs) + note)
    labels = [_label(p, fm) for p in annual]
    for key, nm, profit in (("rev", "매출", False), ("op", "영업이익", True), ("np", "당기순이익", True)):
        vals = [p.get(key) for p in annual]
        if len(vals) >= 3 and all(v is not None for v in vals):
            extra = F._streak_line(labels, vals, "해", profit, True)
            pk = F._peak(labels, vals, True) if all(v > 0 for v in vals) else ""
            if extra or pk:
                lines.append(f"  · {nm}: " + " · ".join(extra + ([pk] if pk else [])))
    stds = {p.get("std") for p in ps if p.get("std")}
    if len(stds) > 1:
        lines.append("- 회계처리기준이 해마다 다르다(위 괄호) — 기준이 다른 해끼리 견줄 때는 그 사실을 함께 쓴다")
    if any("감사받지" in (p.get("audit") or "") or "않은" in (p.get("audit") or "") for p in ps):
        lines.append("- 감사받지 않은 재무제표의 수치를 쓸 때는 그 사실을 함께 쓴다")
    if any((p.get("months") or 12) != 12 for p in ps):
        lines.append("- 누적 기간 실적은 기간을 밝혀 쓴다. 이 서류에 없는 기간(분기 하나 · 그 뒤 기간)의 실적은 출처가 있을 때만 쓴다")
    fu = fin.get("funds") or {}
    if fu.get("uses"):
        net = f"순수입금 {F.won(fu['net'])}[{F.won_en(fu['net'])}] — " if fu.get("net") else ""
        lines.append("- 공모 자금 사용 계획(확정 공모가 기준): " + net
                     + " · ".join(f"{u['use']} {F.won(u['amt'])}[{F.won_en(u['amt'])}]" for u in fu["uses"]))
    return "\n".join(lines)


def quant(fin):
    """금액 검사(check_report_text.amount_hits)에 쓸 값 — 리포트 v2 의 quant 와 같은 꼴(연간만). 없으면 None."""
    if not isinstance(fin, dict):
        return None
    annual = []
    for p in fin.get("periods") or []:
        if (p.get("months") or 12) != 12:
            continue
        row = {"year": int(p["end"][:4])}
        for k in ("rev", "op", "np", "np_owner", "equity", "equity_owner", "liab"):
            if p.get(k) is not None:
                row[k] = p[k]
        if len(row) > 1:
            annual.append(row)
    if not annual:
        return None
    q = {"annual": annual, "source": "증권신고서"}
    if (fin.get("fy_end_month") or 12) != 12:
        q["fy_end_month"] = fin["fy_end_month"]
    return q


# ── DART 조회(러너에서만) ──────────────────────────────────────────────────────────────────────────
def find_corp(codes, *names):
    """DART 회사 목록(corp_codes — DataFrame 또는 {corp_code, corp_name} 목록)에서 이름이 같은 회사들의 고유번호.
    정식명 · 약명 순으로 찾는다('(주)' · '주식회사' · 띄어쓰기는 견주지 않는다)."""
    want = [norm_name(n) for n in names if norm_name(n)]
    if not want:
        return []
    rows = codes.to_dict("records") if hasattr(codes, "to_dict") else list(codes or [])
    for w in want:
        hit = [str(r.get("corp_code")) for r in rows if norm_name(r.get("corp_name")) == w]
        if hit:
            return hit
    return []


def prospectuses(key, code, today=None, get=None):
    """최근 LOOKBACK_DAYS 일의 지분증권 증권신고서 · 투자설명서 — 최근 접수부터."""
    import requests
    get = get or requests.get
    today = today or datetime.date.today()
    j = get(f"{API}/list.json", params={
        "crtfc_key": key, "corp_code": code, "page_count": 100,
        "bgn_de": (today - datetime.timedelta(days=LOOKBACK_DAYS)).strftime("%Y%m%d"),
        "end_de": today.strftime("%Y%m%d")}, timeout=30).json()
    rows = [r for r in (j.get("list") or []) if "투자설명서" in r.get("report_nm", "")
            or "증권신고서(지분증권)" in r.get("report_nm", "")]
    return sorted(rows, key=lambda r: r["rcept_no"], reverse=True)


def fetch_doc(key, rcept_no, get=None):
    """서류 원문(document.xml 묶음의 본문 파일) — 글."""
    import requests
    get = get or requests.get
    z = get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcept_no}, timeout=90)
    zf = zipfile.ZipFile(io.BytesIO(z.content))
    names = [i.filename for i in zf.infolist()]
    main = f"{rcept_no}.xml" if f"{rcept_no}.xml" in names else max(zf.infolist(), key=lambda i: i.file_size).filename
    raw = zf.read(main)
    doc = raw.decode("utf-8", "replace")
    if doc.count("�") > 50:
        doc = raw.decode("euc-kr", "replace")
    return doc


def collect(key, codes, full_name, name, today=None, get=None, log=print):
    """회사 하나의 증권신고서 재무 · 자금 쓰임. 못 읽으면 None(사유는 log 로)."""
    cands = find_corp(codes, full_name, name)
    if not cands:
        log(f"    · 증권신고서: DART 회사 목록에 '{norm_name(full_name) or name}' 없음")
        return None
    rows = []
    for code in cands:
        rows = prospectuses(key, code, today, get)
        if rows:
            break
    if not rows:
        log("    · 증권신고서: 최근 공모 서류 없음")
        return None
    for r in rows[:MAX_DOCS]:
        try:
            doc = fetch_doc(key, r["rcept_no"], get)
        except Exception as e:                                   # noqa: BLE001
            log(f"    · 증권신고서 {r['rcept_no']} 받기 실패: {type(e).__name__}")
            continue
        fin = parse_summary(doc)
        if not fin:
            log(f"    · 증권신고서 {r['rcept_no']} {r.get('report_nm', '')}: 요약재무정보를 읽지 못함 — 앞 서류로")
            continue
        d = str(r.get("rcept_dt") or "")
        fin.update({"rcept_no": r["rcept_no"], "report_nm": re.sub(r"\s+", " ", r.get("report_nm", "")).strip(),
                    "rcept_dt": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d,
                    "funds": parse_funds(doc)})
        return fin
    return None
