"""시안 셋이 같이 쓰는 그리기 도구 — 문단 자르기 · 막대 차트 · 업종 지도."""
import re

from data import esc, money, sign, squarify, MINUS


def chunk(text, budget=170):
    """글자 수 예산으로 문단을 자른다 — 문장 중간에서는 자르지 않는다(실사이트 방식)."""
    if not text:
        return []
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    out, cur = [], ""
    for s in sents:
        if cur and len(cur) + 1 + len(s) > budget:
            out.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    # 너무 짧은 꼬리는 앞 문단에 붙인다. (out[-2] = … + out.pop() 로 쓰면 pop 이 먼저 돌아 엉뚱한 문단을 덮는다 — 한 번 그랬다)
    if len(out) > 1 and len(out[-1]) < 40:
        tail = out.pop()
        out[-1] = out[-1] + " " + tail
    # 자른 문단을 이으면 원문과 같아야 한다 — 문장이 빠지거나 겹치면 여기서 멈춘다
    if re.sub(r"\s+", " ", " ".join(out)).strip() != re.sub(r"\s+", " ", text).strip():
        raise ValueError("chunk: 문단을 이은 글이 원문과 다르다")
    return out


NBSP = "\u00a0"
_NUMUNIT = re.compile(r"(\d[\d,.]*\s?[조억만천])\s(?=\d)")          # 171조 4995억원 → 한 덩어리
_RANGE = re.compile(r"[\d][\d,.]*[^\s~<>]*~[\d][^\s<>]*")            # 90조~110조원 · 2027~2028년
_PCT = re.compile(r"[+\u2212-]?\d[\d,.]*%p?[가-힣]{0,4}")               # 52.2%에서
_DOT = re.compile(r"[가-힣A-Za-z0-9]+(?:·[가-힣A-Za-z0-9]+)+")           # 매출·영업이익
_PREFIX = re.compile(r"(?<![가-힣])(미|약|총|전|연|월|주|각)\s(?=\d)")   # 미 10년물 · 약 90조
_MONO = re.compile(r"(?<![가-힣A-Za-z0-9])([가-힣])\s(?=[가-힣])")        # 한 유가 · 두 배 · 첫 분기


def glue(html_text, *, headline=False):
    """이미 esc 한 글에 줄바꿈 접착을 입힌다. 숫자와 단위, 범위, %와 조사, 가운뎃점 묶음이 줄 끝에서 갈라지지 않게."""
    t = _NUMUNIT.sub(lambda m: m.group(1) + NBSP, html_text)
    t = _PREFIX.sub(lambda m: m.group(1) + NBSP, t)
    t = _MONO.sub(lambda m: m.group(1) + NBSP, t)
    def nw(m):
        w = m.group(0)
        return f'<span class="nw">{w}</span>' if len(w) <= 16 else w
    t = _RANGE.sub(nw, t)
    t = re.sub(r'(?<!class="nw">)' + _PCT.pattern, nw, t)
    t = _DOT.sub(lambda m: f'<span class="nw">{m.group(0)}</span>' if len(m.group(0)) <= 12 else m.group(0), t)
    return t


def g(text, **kw):
    """글 → 안전한 HTML(esc) + 줄바꿈 접착."""
    return glue(esc(text), **kw)


def paras(text, budget=170, cls=""):
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{g(p)}</p>" for p in chunk(text, budget))


def bars_svg(values, labels, *, w=360, h=200, fill="#141414", fill_neg=None, label_fill="#141414",
             axis="#141414", tick_fill="rgba(20,20,20,.62)", font="inherit", fsize=12, tsize=12, weight=500,
             radius=0, gap=0.42, fmt=money, highlight_last=False, fill_last=None, top_pad=26, bottom_pad=26,
             grad=None, glow=None, label_weight=None, klass=""):
    """단순 막대. 0선 아래는 음수. 값 라벨은 막대 위(음수는 아래)."""
    n = len(values)
    vmax = max([v for v in values if v is not None] + [0])
    vmin = min([v for v in values if v is not None] + [0])
    span = (vmax - vmin) or 1
    ih = h - top_pad - bottom_pad
    y0 = top_pad + ih * (vmax / span)
    step = w / n
    bw = step * (1 - gap)
    defs = ""
    if grad:
        defs += (f'<linearGradient id="{grad[0]}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0" stop-color="{grad[1]}"/><stop offset="1" stop-color="{grad[2]}"/></linearGradient>')
    if glow:
        defs += (f'<filter id="{glow}" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" result="b"/>'
                 f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    parts = [f'<svg class="{klass}" viewBox="0 0 {w} {h}" width="100%" preserveAspectRatio="xMidYMid meet" role="img" '
             f'style="font-family:{font}">' + (f"<defs>{defs}</defs>" if defs else "")]
    for i, v in enumerate(values):
        x = step * i + (step - bw) / 2
        if v is None:
            continue
        bh = abs(v) / span * ih
        y = y0 - bh if v >= 0 else y0
        f = fill_neg if (v < 0 and fill_neg) else fill
        if highlight_last and i == n - 1 and fill_last:
            f = fill_last
        if grad and v >= 0:
            f = f"url(#{grad[0]})"
        r = min(radius, bw / 2, bh / 2) if radius else 0
        flt = f' filter="url(#{glow})"' if (glow and i == n - 1) else ""
        parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{max(bh, 0.8):.1f}" rx="{r:.1f}" fill="{f}"{flt}/>')
        ly = y - 7 if v >= 0 else y + bh + fsize + 3
        lw = label_weight or weight
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="{fsize}" font-weight="{lw}" '
                     f'fill="{label_fill}" style="font-variant-numeric:tabular-nums">{esc(fmt(v))}</text>')
        parts.append(f'<text x="{x + bw / 2:.1f}" y="{h - 6:.1f}" text-anchor="middle" font-size="{tsize}" fill="{tick_fill}">{esc(labels[i])}</text>')
    parts.append(f'<line x1="0" x2="{w}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{axis}" stroke-width="1"/>')
    parts.append("</svg>")
    return "".join(parts)


def line_svg(values, labels, *, w=360, h=200, stroke="#141414", dot="#141414", label_fill="#141414",
             tick_fill="rgba(20,20,20,.62)", font="inherit", fsize=12, tsize=12, weight=500, fmt=None,
             top_pad=28, bottom_pad=26, area=None, width=1.6, glow=None, klass="", zero=None):
    n = len(values)
    vals = [v for v in values if v is not None]
    vmax, vmin = max(vals), min(vals + [0] if zero else vals)
    span = (vmax - vmin) or 1
    ih = h - top_pad - bottom_pad
    step = w / n
    pts = []
    for i, v in enumerate(values):
        x = step * i + step / 2
        y = top_pad + ih * (1 - (v - vmin) / span)
        pts.append((x, y, v))
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
    defs = ""
    if glow:
        defs += (f'<filter id="{glow}" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/>'
                 f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    if area:
        defs += (f'<linearGradient id="{area[0]}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{area[1]}"/>'
                 f'<stop offset="1" stop-color="{area[2]}"/></linearGradient>')
    parts = [f'<svg class="{klass}" viewBox="0 0 {w} {h}" width="100%" role="img" style="font-family:{font}">'
             + (f"<defs>{defs}</defs>" if defs else "")]
    if area:
        base = top_pad + ih
        parts.append(f'<path d="{d} L{pts[-1][0]:.1f},{base:.1f} L{pts[0][0]:.1f},{base:.1f} Z" fill="url(#{area[0]})"/>')
    flt = f' filter="url(#{glow})"' if glow else ""
    parts.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{flt}/>')
    for i, (x, y, v) in enumerate(pts):
        last = i == n - 1
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{3.2 if last else 2.2}" fill="{dot}"/>')
        parts.append(f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" font-size="{fsize}" font-weight="{weight}" fill="{label_fill}" '
                     f'style="font-variant-numeric:tabular-nums">{esc(fmt(v) if fmt else v)}</text>')
        parts.append(f'<text x="{x:.1f}" y="{h - 6:.1f}" text-anchor="middle" font-size="{tsize}" fill="{tick_fill}">{esc(labels[i])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def treemap(secs, *, W=1000, H=520, tile, px=1.144):
    """업종 지도 — 면적은 시가총액. tile(sec, x, y, w, h, size) → HTML. 좌표는 % 로 준다.
    px 는 좌표 1 이 화면에서 몇 px 인지(데스크톱 1144px 폭이면 1.144). 라벨은 화면 크기로 판정한다."""
    rects = squarify([(s["mcap"], s) for s in secs], 0, 0, W, H)
    out = []
    for i, (x, y, w, h, s) in enumerate(rects):
        sw, sh = w * px, h * px
        if i == 0 and sw * sh > 90000:
            size = "l3"
        elif sw >= 110 and sh >= 58:
            size = "l2"
        elif sw >= 72 and sh >= 30:
            size = "l1"
        else:
            size = "l0"
        out.append(tile(s, x / W * 100, y / H * 100, w / W * 100, h / H * 100, size))
    return "".join(out)


def q_label(q):
    """'2026Q2' → '26.2Q'"""
    return f"{q[2:4]}.{q[-1]}Q"


def spark(values, *, w=120, h=34, fill="rgba(20,20,20,.22)", last="#141414", neg="rgba(20,20,20,.22)", zero="rgba(20,20,20,.35)", gap=0.34, radius=0):
    """글자 크기의 막대 — 라벨 없이 모양만. 0선 아래는 적자."""
    vals = [v for v in values if v is not None]
    if not vals:
        return ""
    vmax, vmin = max(vals + [0]), min(vals + [0])
    span = (vmax - vmin) or 1
    y0 = h * vmax / span
    n = len(values)
    step = w / n
    bw = step * (1 - gap)
    out = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true" style="display:block;overflow:visible">']
    for i, v in enumerate(values):
        if v is None:
            continue
        bh = max(abs(v) / span * h, 1)
        y = y0 - bh if v >= 0 else y0
        f = last if i == n - 1 else (neg if v < 0 else fill)
        out.append(f'<rect x="{step * i + (step - bw) / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="{radius}" fill="{f}"/>')
    out.append(f'<line x1="0" x2="{w}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{zero}" stroke-width="1"/></svg>')
    return "".join(out)


# ── 이름 · 출처 ─────────────────────────────────────────

_ACR = {"SK", "LG", "KB", "HD", "GS", "CJ", "LS", "KT", "SKC", "OCI", "DB", "BNK", "JB", "DGB", "HMM", "KCC", "KG", "POSCO", "NH", "IBK",
        "KT&G", "S-OIL", "AI", "IT", "NAVER", "BGF", "SPC", "HL", "DL", "KCTC", "ISC", "SNT", "SGC", "HK", "TKG", "NHN", "NCSOFT"}


def clean_en(name_en):
    """'SAMSUNG ELECTRONICS CO,.LTD' → 'Samsung Electronics'. 모양이 이상하면 None(줄을 뺀다)."""
    if not name_en:
        return None
    n = name_en.strip()
    for _ in range(3):
        n = re.sub(r"[\s,.]*(co\s*[,.]*\s*,?\s*ltd|company\s+limited|corporation|corp|inc|limited|ltd|co)\.?\s*$", "", n, flags=re.I).strip(" ,.")
    if not n or re.search(r"[^A-Za-z0-9&\-\s'.]", n) or len(n) > 34:
        return None
    words = []
    for w in n.split():
        if w.upper() in _ACR or re.search(r"\d", w) or (w.isupper() and len(w) <= 3):
            words.append(w.upper() if w.upper() in _ACR else w)
        elif w.isupper():                      # 대문자만인 낱말만 고친다 — 'hynix'·'e-future' 같은 공식 표기는 그대로
            words.append("-".join(p[:1] + p[1:].lower() for p in w.split("-")))
        else:
            words.append(w)
    return " ".join(words)


OUTLETS = {
    "thelec.kr": "더일렉", "mt.co.kr": "머니투데이", "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "yna.co.kr": "연합뉴스",
    "chosun.com": "조선일보", "biz.chosun.com": "조선비즈", "joongang.co.kr": "중앙일보", "donga.com": "동아일보", "hani.co.kr": "한겨레",
    "edaily.co.kr": "이데일리", "etnews.com": "전자신문", "zdnet.co.kr": "지디넷코리아", "sedaily.com": "서울경제", "fnnews.com": "파이낸셜뉴스",
    "newspim.com": "뉴스핌", "thebell.co.kr": "더벨", "businesspost.co.kr": "비즈니스포스트", "bizwatch.co.kr": "비즈워치", "asiae.co.kr": "아시아경제",
    "heraldcorp.com": "헤럴드경제", "news1.kr": "뉴스1", "newsis.com": "뉴시스", "dailian.co.kr": "데일리안", "ajunews.com": "아주경제",
    "g-enews.com": "글로벌이코노믹", "koreatimes.co.kr": "코리아타임스", "koreaherald.com": "코리아헤럴드", "reuters.com": "로이터",
    "bloomberg.com": "블룸버그", "ft.com": "파이낸셜타임스", "wsj.com": "월스트리트저널", "cnbc.com": "CNBC", "news.samsung.com": "삼성전자 뉴스룸",
    "news.samsungsemiconductor.com": "삼성반도체 뉴스룸", "dart.fss.or.kr": "금융감독원 DART", "kind.krx.co.kr": "한국거래소 KIND",
    "krx.co.kr": "한국거래소", "trendforce.com": "트렌드포스", "digitimes.com": "디지타임스", "news.nate.com": "네이트뉴스", "naver.com": "네이버뉴스",
    "daum.net": "다음뉴스", "investing.com": "인베스팅닷컴", "ceoscoredaily.com": "CEO스코어데일리", "newsdaily.co.kr": "뉴스데일리",
    "ebc.com": "EBC", "newdaily.co.kr": "뉴데일리", "koreatimes.com": "코리아타임스", "biz.newdaily.co.kr": "뉴데일리경제", "tradersunion.com": "트레이더스유니온", "thecommoditiesnews.com": "커머디티뉴스", "studio24.kr": "스튜디오24",
    "tradingkey.com": "트레이딩키", "inews24.com": "아이뉴스24", "ddaily.co.kr": "디지털데일리", "etoday.co.kr": "이투데이",
    "seoul.co.kr": "서울신문", "khan.co.kr": "경향신문", "kmib.co.kr": "국민일보", "hankookilbo.com": "한국일보", "nocutnews.co.kr": "노컷뉴스",
    "yonhapnewstv.co.kr": "연합뉴스TV", "sbs.co.kr": "SBS", "kbs.co.kr": "KBS", "mbc.co.kr": "MBC", "ytn.co.kr": "YTN", "jtbc.co.kr": "JTBC",
    "pharmnews.com": "팜뉴스", "dailypharm.com": "데일리팜", "biospectator.com": "바이오스펙테이터", "hitnews.co.kr": "히트뉴스",
    "theguru.co.kr": "더구루", "bloter.net": "블로터", "irgo.co.kr": "IRGO", "moneys.co.kr": "머니S", "news.einfomax.co.kr": "연합인포맥스",
    "einfomax.co.kr": "연합인포맥스", "wowtv.co.kr": "한국경제TV", "mtn.co.kr": "머니투데이방송", "sisajournal-e.com": "시사저널이코노미",
}


def sources_grouped(urls):
    """매체별로 묶는다 → [(매체, [url, …])] — 같은 매체의 다른 기사는 번호로."""
    groups = {}
    for name, host, u in sources(urls):
        groups.setdefault(name, []).append(u)
    return list(groups.items())


def sources(urls):
    """출처 URL → [(매체, 호스트, url)] · 같은 주소는 하나로."""
    seen, out = set(), []
    for u in urls or []:
        key = re.sub(r"^https?://(www\.|m\.)?", "", u).rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        host = re.sub(r"^(www\.|m\.)", "", u.split("//")[-1].split("/")[0])
        name = OUTLETS.get(host)
        if not name:
            for k, v in OUTLETS.items():
                if host.endswith("." + k) or host == k:
                    name = v
                    break
        out.append((name or host, host, u))
    return out


# ── 업종 지도 보조 ─────────────────────────────────────

def merge_small(secs, min_share=1.0):
    """시가총액 1% 미만 업종은 '기타 N개 업종' 하나로 묶는다."""
    big = [s for s in secs if s["share"] >= min_share and s["name"] != "기타"]
    small = [s for s in secs if s not in big]
    if small:
        m = sum(s["mcap"] for s in small)
        w = sum(s["mcap"] * s["chg"] for s in small)
        big.append({"name": f"기타 {len(small)}개 업종", "mcap": m, "chg": w / m if m else 0, "share": sum(s["share"] for s in small),
                    "n": sum(s["n"] for s in small), "tops": [], "top": [], "lead": "", "other": True})
    return big


def yoy(vals):
    """분기 5개(같은 분기 1년 전 포함) → 전년 동기 대비 배수·증감률"""
    if len(vals) >= 5 and vals[0] and vals[-1] is not None and vals[0] > 0:
        return vals[-1] / vals[0]
    return None


def rbar_path(x, y, w, h, r, up=True):
    """위(또는 아래) 모서리만 둥근 막대"""
    r = max(0, min(r, w / 2, h))
    if h <= 0.01:
        return f"M{x:.1f},{y:.1f}h{w:.1f}"
    if up:
        return (f"M{x:.1f},{y + h:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{y + h:.1f}Z")
    return (f"M{x:.1f},{y:.1f}V{y + h - r:.1f}Q{x:.1f},{y + h:.1f} {x + r:.1f},{y + h:.1f}H{x + w - r:.1f}Q{x + w:.1f},{y + h:.1f} {x + w:.1f},{y + h - r:.1f}V{y:.1f}Z")


def chart_bars(values, labels, *, w=360, h=200, uid="c", bg="#f9f8f6", fill="rgba(20,20,20,.2)", last="#141414", text="#141414",
               tick="rgba(20,20,20,.62)", axis="rgba(20,20,20,.5)", font="inherit", fsize=13, tsize=12, weight=500, radius=3,
               fmt=None, label_last=True, gap=0.42, top_pad=26, bottom_pad=26, last_grad=None):
    """막대 — 위 모서리만 둥글게, 값 라벨에 바탕색 테두리(할로), 0선 아래는 음수."""
    from data import money as _money
    fmt = fmt or _money
    n = len(values)
    vs = [v for v in values if v is not None]
    vmax, vmin = max(vs + [0]), min(vs + [0])
    span = (vmax - vmin) or 1
    ih = h - top_pad - bottom_pad
    y0 = top_pad + ih * vmax / span
    step = w / n
    bw = step * (1 - gap)
    halo = f'paint-order="stroke" stroke="{bg}" stroke-width="4" stroke-linejoin="round"'
    defs = ""
    if last_grad:
        defs = (f'<defs><linearGradient id="{uid}g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{last_grad[0]}"/>'
                f'<stop offset="1" stop-color="{last_grad[1]}"/></linearGradient></defs>')
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" style="font-family:{font};display:block">{defs}']
    for i, v in enumerate(values):
        x = step * i + (step - bw) / 2
        if v is None:
            out.append(f'<line x1="{x:.1f}" x2="{x + bw:.1f}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{tick}" stroke-width="2"/>')
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 7:.1f}" text-anchor="middle" font-size="{tsize}" fill="{tick}">{esc(labels[i])}</text>')
            continue
        bh = max(abs(v) / span * ih, 1)
        islast = i == n - 1
        f = (f"url(#{uid}g)" if last_grad else last) if islast else fill
        out.append(f'<path d="{rbar_path(x, y0 - bh if v >= 0 else y0, bw, bh, radius, v >= 0)}" fill="{f}"/>')
        if label_last or not islast:
            ly = (y0 - bh - 8) if v >= 0 else (y0 + bh + fsize + 4)
            out.append(f'<text x="{x + bw / 2:.1f}" y="{ly:.1f}" text-anchor="middle" font-size="{fsize}" font-weight="{weight if not islast else weight + 100}" '
                       f'fill="{text}" {halo} style="font-variant-numeric:tabular-nums">{esc(fmt(v))}</text>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 7:.1f}" text-anchor="middle" font-size="{tsize}" fill="{tick}">{esc(labels[i])}</text>')
    out.append(f'<line x1="0" x2="{w}" y1="{y0:.1f}" y2="{y0:.1f}" stroke="{axis}" stroke-width="1"/></svg>')
    return "".join(out)


def chart_line(values, labels, *, w=360, h=200, uid="l", bg="#f9f8f6", stroke="#141414", dot=None, text="#141414", tick="rgba(20,20,20,.62)",
               font="inherit", fsize=13, tsize=12, weight=500, fmt=None, width=1.6, area=None, top_pad=30, bottom_pad=30, zero=True, last_dot=None):
    """선 — 라벨은 선과 부딪치지 않는 쪽(나가는 선이 더 가파르면 아래)에, 바탕색 할로."""
    n = len(values)
    vs = [v for v in values if v is not None]
    vmax, vmin = max(vs), (min(vs + [0]) if zero else min(vs))
    span = (vmax - vmin) or 1
    ih = h - top_pad - bottom_pad
    step = w / n
    pts = [(step * i + step / 2, top_pad + ih * (1 - (v - vmin) / span), v) for i, v in enumerate(values)]
    d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y, _ in pts)
    halo = f'paint-order="stroke" stroke="{bg}" stroke-width="4" stroke-linejoin="round"'
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" style="font-family:{font};display:block">']
    if area:
        out.append(f'<defs><linearGradient id="{uid}a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{area[0]}"/><stop offset="1" stop-color="{area[1]}"/></linearGradient></defs>')
        out.append(f'<path d="{d} L{pts[-1][0]:.1f},{top_pad + ih:.1f} L{pts[0][0]:.1f},{top_pad + ih:.1f} Z" fill="url(#{uid}a)"/>')
    out.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')
    for i, (x, y, v) in enumerate(pts):
        sin = (pts[i - 1][1] - y) if i > 0 else 0          # 들어오는 선의 오름(px)
        sout = (y - pts[i + 1][1]) if i < n - 1 else -1    # 나가는 선의 오름
        below = i < n - 1 and sout > sin and sout > 8
        islast = i == n - 1
        r = 3.6 if islast else 2.4
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{(last_dot or dot or stroke) if islast else (dot or stroke)}"/>')
        ly = y + fsize + 9 if below else y - 11
        lx = x + (8 if below else 0)
        anchor = "start" if below else "middle"
        out.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" font-size="{fsize}" font-weight="{weight + (100 if islast else 0)}" fill="{text}" {halo} '
                   f'style="font-variant-numeric:tabular-nums">{esc(fmt(v) if fmt else v)}</text>')
        out.append(f'<text x="{x:.1f}" y="{h - 7:.1f}" text-anchor="middle" font-size="{tsize}" fill="{tick}">{esc(labels[i])}</text>')
    out.append("</svg>")
    return "".join(out)


def first_sentence(text, maxlen=44):
    """첫 문장 — 마침표는 떼고, 길면 잘라 말줄임."""
    s = re.split(r"(?<=[.!?])\s+", (text or "").strip())[0].rstrip(".")
    return s if len(s) <= maxlen else s[:maxlen - 1].rstrip(" ,·") + "…"


def read_minutes(r):
    """리포트 전체 글자 수 ÷ 분당 500자"""
    ko = lambda d: (d or {}).get("ko", "")
    n = sum(len(ko(r.get(k))) for k in ("lead", "business", "earnings", "industry", "outlook", "valuation_comment"))
    n += sum(len(ko(x["title"])) + len(ko(x["body"])) for x in r["bull"] + r["bear"])
    n += sum(len(ko(x["body"])) for x in r["risks"]) + sum(len(ko(x["what"])) for x in r["checkpoints"])
    n += len(ko(r["verdict"]["body"])) + sum(len(ko(k)) for k in r["keypoints"])
    return max(1, round(n / 500))
