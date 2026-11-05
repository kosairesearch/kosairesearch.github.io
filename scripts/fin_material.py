"""작성 모델에 주는 공시 실적 재료 — 금액은 본문 표기로 미리 바꾸고, 증감 · 전환 · 연속은 코드가 센다(2026-10-10).

사장: "지금 만든 리포트를 고치는 것보다 앞으로 만들어질 리포트에 오류가 안 생기는 게 더 중요하다."

10/9 전수 점검에서 리포트 숫자 오류의 원인이 재료에 있었다. 작성 모델은 원 단위 원자료(JSON · 342737745051)를 받아
'억 · 만'으로 직접 옮겨 적었고, 그러다 자리를 틀렸다 — '3,427억 7,375만원'(실제 3,427억 3,774만원), '영업이익 7.4억원'
(실제 7,373만원 · 열 배), '2022년 매출 1조 1,148억원'(실제 1조 115억원). 연수도 직접 셌다 — 정점 연도를 넣어 센 '3년 연속
감소'. 지배주주 순이익과 당기순이익, 자본총계와 지배주주 자본도 칸 이름(np · np_owner)만 보고 섞었다. 지시문도
'제공한 확정 데이터' · '분기 창' · 'ttm_window' 라고 불러, 그 말이 본문에 그대로 옮겨졌다(받은 자료 언급 125편).

그래서 사람이 읽는 표기와 계산 결과를 그대로 준다 — 옮겨 쓰기만 하면 맞는다. 본문에 쓰면 안 되는 값(ROE · EPS · BPS ·
주당배당금)은 싣지 않는다. 금액은 화면 표(stock_page.fwon)와 같은 절반 올림이다. 돈이 들지 않는다.
"""
import functools
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _hu(x, f=0):
    """절반 올림(x ≥ 0) — stock_page._half_up 과 같다(화면 표와 같은 반올림)."""
    return Decimal(x).quantize(Decimal(1).scaleb(-f), rounding=ROUND_HALF_UP)


def _dec(d):
    """Decimal → '9.9' · '12'(끝의 .0 은 뗀다) · 천 단위 쉼표."""
    i, dot, frac = format(d, "f").partition(".")
    frac = frac.rstrip("0")
    return f"{int(i):,}" + (f".{frac}" if frac else "")


def won(v):
    """원 → 한국어 본문 표기. 부호는 떼고 크기만 — 손익은 '영업손실' 처럼 말로 가른다.
    1조 이상 '333조 6,059억원' · 100억 이상 '4,676억원' · 1억 이상 '9.9억원'(소수 한 자리) · 그 아래 '8,532만원'."""
    a = abs(float(v))
    eok = _hu(a / 1e8)
    if eok >= 10000:
        jo, rest = divmod(int(eok), 10000)
        return f"{jo:,}조 {rest:,}억원" if rest else f"{jo:,}조원"
    if a >= 1e10:
        return f"{int(eok):,}억원"
    if a >= 1e8:
        return f"{_dec(_hu(a / 1e8, 1))}억원"
    man = _hu(a / 1e4)
    if man >= 10000:
        return "1억원"
    return f"{int(man):,}만원"


def won_en(v):
    """원 → 영어 본문 표기. 1억 = 100 million, 1조 = 1 trillion — 억을 billion 으로 옮기다 열 배가 틀리는 자리라 미리 바꿔 준다.
    한국어 표기와 같은 자릿수까지: 'KRW 333.6 trillion' · 'KRW 1.04 trillion' · 'KRW 467.6 billion' · 'KRW 2.46 billion' ·
    'KRW 990 million' · 'KRW 85.32 million'."""
    a = abs(float(v))
    if _hu(a / 1e8) >= 10000:
        t = a / 1e12
        return f"KRW {_dec(_hu(t, 2 if t < 10 else 1))} trillion"
    if a >= 1e10:
        return f"KRW {_dec(_hu(a / 1e9, 1))} billion"
    if a >= 1e9:
        return f"KRW {_dec(_hu(a / 1e9, 2))} billion"
    if a >= 1e8:
        return f"KRW {_dec(_hu(a / 1e6))} million"
    return f"KRW {_dec(_hu(a / 1e6, 2))} million"


def qtext(label):
    """'2026Q2' → '2026년 2분기'"""
    m = re.fullmatch(r"(\d{4})Q([1-4])", str(label or ""))
    return f"{m.group(1)}년 {m.group(2)}분기" if m else str(label or "")


def chg(cur, prev, profit=False):
    """앞 기간과 견준 말 — '10.9% 증가' · '3.2% 감소' · '흑자 전환' · '적자 전환' · '적자 지속(손실 축소)'. 견줄 수 없으면 ''.
    증감률은 둘 다 흑자(양수)일 때만 쓴다 — 적자가 끼면 비율이 뜻을 잃는다. 매출(profit=False)은 전환 말을 쓰지 않는다."""
    if cur is None or prev is None:
        return ""
    if cur > 0 and prev > 0:
        p = (cur / prev - 1) * 100
        r = _hu(abs(p), 1)
        if r == 0:
            return "변동 없음"
        return f"{r:,.1f}% {'증가' if p > 0 else '감소'}"
    if not profit or prev == 0 or cur == 0:
        return ""
    if prev < 0 < cur:
        return "흑자 전환"
    if cur < 0 < prev:
        return "적자 전환"
    if cur < 0 and prev < 0:
        if abs(cur) < abs(prev):
            return "적자 지속(손실 축소)"
        if abs(cur) > abs(prev):
            return "적자 지속(손실 확대)"
        return "적자 지속"
    return ""


def _val(row, key):
    """칸 값. 매출 0 은 값이 아니라 빈 칸이다(보험수익이 없던 해 등) — 0 으로 옮기면 '매출 0원'이 된다."""
    x = row.get(key)
    if x is None or (key == "rev" and x == 0):
        return None
    return x


def _pct(x):
    """'13.1%' · '1,143.7%'(천 단위 쉼표 — 본문 표기와 같게)."""
    try:
        return f"{float(x):,.1f}%"
    except (TypeError, ValueError):
        return f"{x}%"


# 지표 — (칸, 한국어 이름, 손실일 때 이름, 손익인가)
_METRICS = (
    ("rev", "매출", None, False),
    ("op", "영업이익", "영업손실", True),
    ("np_owner", "지배주주 순이익", "지배주주 순손실", True),
)


def _amt(v, name, loss_name):
    """'영업이익 4,676억원[KRW 467.6 billion]' · '영업손실 747억원[KRW 74.7 billion]' — 손익은 값마다 이름을 붙인다(흑자 · 적자가
    바뀌는 자리에서 이름을 틀리지 않게). 매출은 줄 머리에만 이름이 있어 값만 쓴다."""
    if not loss_name:
        return f"{won(v)}[{won_en(v)}]"
    label = loss_name if v < 0 else name
    return f"{label} {won(v)}[{won_en(v)}]"


def _eun(word):
    """받침이 있으면 '은', 없으면 '는' — '2023년은' · '4분기는'."""
    c = word[-1:]
    return "은" if c and "가" <= c <= "힣" and (ord(c) - 0xAC00) % 28 else "는"


def _run(vals, up):
    """끝에서부터 같은 방향으로 이어진 변화 수(모두 흑자일 때만). vals 는 시간순."""
    k = 0
    for i in range(len(vals) - 1, 0, -1):
        a, b = vals[i - 1], vals[i]
        if a is None or b is None or a <= 0 or b <= 0:
            break
        if (b > a) if up else (b < a):
            k += 1
        else:
            break
    return k


def _loss_run(vals):
    """끝에서부터 이어진 적자(음수) 기간 수."""
    k = 0
    for v in reversed(vals):
        if v is not None and v < 0:
            k += 1
        else:
            break
    return k


def _streak_line(labels, vals, unit, profit, is_year):
    """연속 · 전환을 말로 — 센 값을 그대로 옮겨 쓰게 한다.
    'N년 연속 증가 · 감소'는 변화가 일어난 해의 수다(2022년 정점 → 2023 · 2024 · 2025년 감소 = 3년 연속 감소).
    'N년 연속 적자'는 손실을 낸 해의 수다(2023 · 2024 · 2025년 손실 = 3년 연속 적자)."""
    out = []
    if not vals or vals[-1] is None:
        return out
    word = "년" if is_year else "개 분기"
    edge = f"{labels[0]}보다 앞은 확인되지 않았다 — 그 앞까지 이어졌다고 쓰려면 출처가 있어야 한다"
    for up, verb in ((True, "증가"), (False, "감소")):
        k = _run(vals, up)
        if k >= 2:
            start = labels[-1 - k]
            if k == len(vals) - 1:
                out.append(f"{labels[-k]}부터 {labels[-1]}까지 {k}{word} 연속 {verb}({start}에서 시작 · {edge})")
            else:
                out.append(f"{start}({'저점' if up else '정점'}) 다음 {labels[-k]}부터 {labels[-1]}까지 {k}{word} 연속 {verb}"
                           f"({start}{_eun(start)} 세지 않는다)")
    if profit:
        k = _loss_run(vals)
        if k >= 2:
            out.append(f"{labels[-k]}부터 {labels[-1]}까지 {k}{word} 연속 적자(손실을 낸 {unit}의 수"
                       + (f" · {edge}" if k == len(vals) else "") + ")")
    return out


def _peak(labels, vals, is_year):
    """기간 안에서 가장 큰 · 작은 해 — '사상 최대'로 옮기지 않게 기간('2022~2025년 중')을 밝힌다.
    '표의 4개 연도 중' 처럼 재료를 가리키는 말은 쓰지 않는다 — 본문에 옮겨지면 읽는 사람은 무슨 표인지 모른다."""
    pts = [(v, lb) for v, lb in zip(vals, labels) if v is not None]
    if len(pts) < 3:
        return ""
    hi, lo = max(pts), min(pts)
    span = f"{pts[0][1].rstrip('년')}~{pts[-1][1]}" if is_year else f"{pts[0][1]}~{pts[-1][1]}"
    unit = "해" if is_year else "분기"
    return f"{span} 중 가장 큰 {unit} {hi[1]} · 가장 작은 {unit} {lo[1]}('사상 최대'는 출처가 있을 때만)"


def material(q, name=""):
    """[공시 실적] 블록 — 작성 지시문에 그대로 넣는다. 자료가 없으면 ''.

    연간은 지표마다 한 줄(값 → 전년 대비 → 연속 · 전환), 분기도 지표마다 한 줄(전 분기 대비 · 마지막 분기는 전년 동기 대비).
    금액 뒤 [ ] 안은 영어 본문에 쓸 표기다. 영업이익률 · 부채비율 · 자본은 따로 한 줄씩."""
    if not isinstance(q, dict):
        return ""
    annual = sorted((a for a in (q.get("annual") or []) if isinstance(a, dict) and a.get("year")),
                    key=lambda a: a["year"])
    quarterly = [r for r in (q.get("quarterly") or []) if isinstance(r, dict)
                 and re.fullmatch(r"\d{4}Q[1-4]", str(r.get("q") or ""))]
    quarterly.sort(key=lambda r: r["q"])
    if not annual and not quarterly:
        return ""
    rev_label = ((q.get("rev_label") or {}).get("ko") if isinstance(q.get("rev_label"), dict) else None) or "매출"
    v = q.get("valuation") or {}
    ccy = str(v.get("ccy") or "KRW").upper()
    lines = []
    head = "[공시 실적 — DART 정기보고서 · 금액은 이 표기 그대로 본문에 옮긴다 · [ ] 안은 영어 본문 표기]"
    if ccy != "KRW":
        head += f"\n(이 회사는 {ccy}로 공시한다 — 아래 금액은 원화로 환산한 값이다. 본문에 원화 금액을 쓸 때는 '원화 환산'이라고 밝힌다)"
    lines.append(head)

    if q.get("rev_label"):
        lines.append(f"('{rev_label}' 칸은 이 이름의 계정만 담는다 — 회사 전체의 매출이나 영업수익으로 쓰지 말 것)")
    if annual:
        years = [f"{a['year']}년" for a in annual]
        lines.append(f"연간({years[0]}~{years[-1]})")
        for key, nm, loss_nm, profit in _METRICS:
            nm = rev_label if key == "rev" else nm
            vals = [_val(a, key) for a in annual]
            if all(x is None for x in vals):
                continue
            parts = []
            for i, (lb, x) in enumerate(zip(years, vals)):
                if x is None:
                    parts.append(f"{lb} 자료 없음")
                    continue
                c = chg(x, vals[i - 1], profit) if i else ""
                parts.append(f"{lb} {_amt(x, nm, loss_nm)}" + (f"(전년 대비 {c})" if c else ""))
            lines.append(f"- {nm}: " + " → ".join(parts))
            extra = _streak_line(years, vals, "해", profit, True)
            pk = _peak(years, vals, True) if all(x is not None and x > 0 for x in vals) else ""
            if extra or pk:
                lines.append("  · " + " · ".join(extra + ([pk] if pk else [])))
        # 순이익 두 가지 — 지배주주 몫과 비지배 포함 전체를 섞지 않게 둘 다 이름을 붙여 준다
        nps = [(f"{a['year']}년", a.get("np")) for a in annual if a.get("np") is not None]
        if nps:
            lines.append("- 당기순이익(비지배지분 포함 · '지배주주 순이익'과 다른 값): " + " → ".join(
                f"{lb} {'당기순손실' if x < 0 else '당기순이익'} {won(x)}[{won_en(x)}]" for lb, x in nps))
        opm = [(f"{a['year']}년", a.get("opm")) for a in annual if a.get("opm") is not None]
        if opm:
            lines.append("- 영업이익률: " + " → ".join(f"{lb} {_pct(x)}" for lb, x in opm))
        dr = [(f"{a['year']}년", a.get("debt_ratio")) for a in annual if a.get("debt_ratio") is not None]
        if dr:
            lines.append("- 부채비율(부채총계 ÷ 자본총계): " + " → ".join(f"{lb} {_pct(x)}" for lb, x in dr))
        last = annual[-1]
        if last.get("equity") is not None:
            eq = f"- {last['year']}년 말 자본총계 {won(last['equity'])}[{won_en(last['equity'])}]"
            if last.get("equity_owner") is not None:
                eq += f" · 그중 지배주주 지분 {won(last['equity_owner'])}[{won_en(last['equity_owner'])}]"
            if last.get("liab") is not None:
                eq += f" · 부채총계 {won(last['liab'])}[{won_en(last['liab'])}]"
            lines.append(eq)
        cfo = [(f"{a['year']}년", a.get("cfo")) for a in annual if a.get("cfo") is not None]
        if cfo:
            lines.append("- 영업활동 현금흐름: " + " → ".join(
                f"{lb} {'-' if x < 0 else ''}{won(x)}[{'-' if x < 0 else ''}{won_en(x)}]" for lb, x in cfo))

    if quarterly:
        qs = [qtext(r["q"]) for r in quarterly]
        lines.append(f"분기(3개월 · {qs[0]}~{qs[-1]})")
        by_q = {r["q"]: r for r in quarterly}
        for key, nm, loss_nm, profit in _METRICS:
            nm = rev_label if key == "rev" else nm
            vals = [_val(r, key) for r in quarterly]
            if all(x is None for x in vals):
                continue
            parts = []
            for i, (r, lb, x) in enumerate(zip(quarterly, qs, vals)):
                if x is None:
                    parts.append(f"{lb} 자료 없음")
                    continue
                notes = []
                c = chg(x, vals[i - 1], profit) if i else ""
                if c:
                    notes.append(f"전 분기 대비 {c}")
                y, n = r["q"].split("Q")
                prev = _val(by_q.get(f"{int(y) - 1}Q{n}") or {}, key)
                c2 = chg(x, prev, profit)
                if c2:
                    notes.append(f"전년 동기 대비 {c2}")
                parts.append(f"{lb} {_amt(x, nm, loss_nm)}" + (f"({' · '.join(notes)})" if notes else ""))
            lines.append(f"- {nm}: " + " → ".join(parts))
            extra = _streak_line(qs, vals, "분기", profit, False)
            if extra:
                lines.append("  · " + " · ".join(extra))

    win, ttm = v.get("ttm_window"), v.get("ttm_np_owner")
    if win and ttm is not None:
        a, _, b = str(win).partition("~")
        lines.append(f"- 최근 4개 분기({qtext(a)}~{qtext(b)}) 지배주주 {'순손실' if ttm < 0 else '순이익'} 합계 "
                     f"{won(ttm)}[{won_en(ttm)}]")
    mult = []
    if v.get("per") is not None:
        mult.append(f"PER {v['per']:.1f}배")
    elif ttm is not None and ttm <= 0:
        mult.append("PER 산출 안 됨(최근 4개 분기 순손실)")
    if v.get("pbr") is not None:
        mult.append(f"PBR {v['pbr']:.2f}배")
    if v.get("div") is not None:
        mult.append(f"배당수익률 {v['div']}%")
    if mult:
        lines.append("- 현재 배수(주가에 따라 날마다 바뀌어 화면 카드가 표시한다 — 수치를 본문에 쓰지 말고 수준 비교에만 쓴다): "
                     + " · ".join(mult))
    return "\n".join(lines)


# ── 회사 영문명 ─────────────────────────────────────────────────────────────
# 영어 본문의 회사명을 모델이 한국어 이름에서 지어냈다 — '이랜텍'을 'E-Lantec'(공시 영문명 Elentec), '엠로'를 'Ellomay',
# '진원생명과학'을 'Genexine Life Science'(제넥신은 다른 회사다), 화천기공과 화천기계의 영문명을 뒤바꿔 썼다. 공시 영문명을 준다.
_GLUED_SUFFIX = re.compile(r"(?<=[a-z])(?:CompanyLimited|Corporation|Company|Limited|Corp|Inc|Co|Ltd)$")


def en_name(raw):
    """공시 영문명 → 본문에 쓸 꼴. clean_en(화면과 같은 정리)을 바탕으로 세 가지만 더 한다.
      · 대문자 공시 이름의 짧은 약어는 대문자로 둔다 — 'HS HWASUNG' → 'HS Hwasung'(clean_en 은 'Hs')
      · 대문자 공시 이름의 하이픈 뒤도 대문자로 — 'ELECTRO-MECHANICS' → 'Electro-Mechanics'
      · 단어를 붙여 쓴 공시 이름은 붙은 꼬리('…Co' · '…Inc')를 떼고 띄운다 — 'KohYoungTechnologyInc.' → 'Koh Young Technology'.
        대문자뿐인 붙은 이름('HYUNDAIMARINE&FIREINSURANCECO')은 띄울 자리를 알 수 없어 그대로 두고 표시만 붙인다."""
    import check_report_text as C       # noqa: E402 — 표준 라이브러리만 쓴다
    s = (raw or "").strip()
    if not s:
        return ""
    c = C.clean_en(s)
    caps = {t for t in re.findall(r"[A-Za-z&]+", s) if t.isupper() and len(t) <= 3}
    if caps:
        c = " ".join(w.upper() if w.upper() in caps and w.isalpha() else w for w in c.split())
    if re.sub(r"[^A-Za-z]", "", s).isupper():
        c = re.sub(r"-([a-z])", lambda m: "-" + m.group(1).upper(), c)
    core = re.sub(r"(?i)[\s,.]*\b(?:co|ltd|inc|corp|corporation|limited|company)\b\.?\s*$", "", s.split(",")[0].strip()).strip()
    if " " not in c and len(c) > 8:
        m = _GLUED_SUFFIX.search(c)
        if m and re.search(r"[a-z][A-Z]", c):
            c = c[:m.start()]
            if len(c) >= 12:
                c = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", c)
        elif (" " not in core and re.fullmatch(r"[A-Z&.]+", core)
              and len(re.sub(r"[^A-Za-z]", "", core)) > 12):
            return f"{core.rstrip('.')}(공시 영문명이 붙어 있다 — 같은 철자로 단어를 띄어 쓸 것)"
    return c


@functools.lru_cache(maxsize=1)
def _stocks():
    s = (ROOT / "data" / "stocks.js").read_text(encoding="utf-8")
    return json.loads(s[s.index("["):s.rindex("]") + 1])


def name_block(st, stocks=None, n_sector=20, n_similar=8, n_top=15):
    """[회사 영문명] 블록 — 이 회사 · 같은 업종 상위 · 이름이 비슷한 회사 · 시가총액 상위. 돈이 들지 않는다."""
    try:
        stocks = stocks if stocks is not None else _stocks()
    except Exception:
        stocks = []
    me_tk, me_nm = st.get("ticker"), st.get("name") or ""
    me_en = en_name(st.get("name_en"))
    rows = [x for x in stocks if isinstance(x, dict) and x.get("ticker") != me_tk and x.get("name") and x.get("name_en")]
    rows.sort(key=lambda x: x.get("mcap") or 0, reverse=True)
    seen = set()

    def pick(cands, k):
        out = []
        for x in cands:
            if x["ticker"] in seen:
                continue
            seen.add(x["ticker"])
            out.append(f"{x['name']}({en_name(x['name_en'])})")
            if len(out) >= k:
                break
        return out

    # 이름이 비슷한 회사를 먼저 고른다 — 같은 업종이어도 '서로 다른 회사'라는 표시가 붙게(화천기공 · 화천기계는 둘 다 기계 · 장비)
    sec = st.get("sector") or ""
    stem = re.sub(r"[^가-힣]", "", me_nm)[:2]
    similar = pick([x for x in rows if len(stem) == 2 and re.sub(r"[^가-힣]", "", x["name"]).startswith(stem)], n_similar)
    same = pick([x for x in rows if sec and x.get("sector") == sec], n_sector)
    top = pick(rows, n_top)
    lines = ["[회사 영문명 — 영어(en) 본문은 이 이름을 쓴다]",
             f"- 이 회사: {me_nm}({me_en or '공시 영문명 없음 — 회사가 쓰는 영문명을 검색으로 확인할 것'})"]
    if same:
        lines.append(f"- 같은 업종({sec}) 상장사: " + " · ".join(same))
    if similar:
        lines.append("- 이름이 비슷한 상장사(서로 다른 회사다 — 섞지 말 것): " + " · ".join(similar))
    if top:
        lines.append("- 시가총액 상위 상장사: " + " · ".join(top))
    lines.append("- 목록에 없는 회사는 그 회사가 쓰는 공식 영문명을 검색으로 확인해 쓴다. 한국어 이름을 소리 나는 대로 옮겨 새 이름을"
                 " 짓지 않는다. 회사가 IR · 홈페이지에서 다른 영문명을 쓰는 것이 확인되면 그 이름을 쓴다.")
    return "\n".join(lines)
