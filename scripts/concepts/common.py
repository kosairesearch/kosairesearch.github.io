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
    # 너무 짧은 꼬리는 앞 문단에 붙인다
    if len(out) > 1 and len(out[-1]) < 40:
        out[-2] = out[-2] + " " + out.pop()
    return out


def paras(text, budget=170, cls=""):
    c = f' class="{cls}"' if cls else ""
    return "".join(f"<p{c}>{esc(p)}</p>" for p in chunk(text, budget))


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
