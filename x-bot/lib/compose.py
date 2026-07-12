"""최종 답글 조립 — 서술(캐시) + 지표(코드가 매번 실시간) + 면책문구.

구조: 종목명(코드) → 정의 → 사업 → 최근 → ■핵심지표 → 리스크 → 면책.
영어 답글은 가격/시총에 달러 환산 병기. 숫자는 전부 코드가 채운다.
"""


def _fmt_won(n):
    try:
        return f"{int(round(n)):,}원"
    except Exception:
        return "-"


def _fmt_krw(n):
    try:
        return f"{int(round(n)):,} KRW"
    except Exception:
        return "-"


def _usd(n):
    if n >= 1e12:
        return f"${n/1e12:.1f}T"
    if n >= 1e9:
        return f"${n/1e9:.1f}B"
    if n >= 1e6:
        return f"${n/1e6:.0f}M"
    return f"${n:,.0f}"


def _mcap_ko(trill):
    if trill is None:
        return None
    if trill >= 1:
        return f"{int(round(trill)):,}조원"
    return f"{int(round(trill*10000)):,}억원"


def _mcap_en(trill, fx):
    if trill is None:
        return None
    usd = trill * 1e12 / fx
    return f"{trill:,.1f}T KRW (~{_usd(usd)})"


def _metrics_block(m, lang, fx):
    lines = []
    price = m.get("price")
    chg = m.get("change")
    if lang == "ko":
        lines.append("■ 핵심 지표" + (f" ({m['data_date']} 기준)" if m.get("data_date") else ""))
        if price:
            c = f" ({'+' if (chg or 0) >= 0 else ''}{chg}%)" if chg is not None else ""
            lines.append(f"현재가 {_fmt_won(price)}{c}")
        mc = _mcap_ko(m.get("mcap_trillion"))
        if mc:
            lines.append(f"시가총액 {mc}")
        ratio = []
        if m.get("per") is not None:
            ratio.append(f"PER {m['per']}")
        if m.get("pbr") is not None:
            ratio.append(f"PBR {m['pbr']}")
        if m.get("div_yield") is not None:
            ratio.append(f"배당수익률 {m['div_yield']}%")
        if ratio:
            lines.append(" · ".join(ratio))
        if m.get("roe") is not None:
            lines.append(f"ROE {m['roe']}%")
    else:
        lines.append("■ Key metrics" + (f" (as of {m['data_date']})" if m.get("data_date") else ""))
        if price:
            c = f" ({'+' if (chg or 0) >= 0 else ''}{chg}%)" if chg is not None else ""
            lines.append(f"Price {_fmt_krw(price)} (~{_usd(price/fx)}){c}")
        mc = _mcap_en(m.get("mcap_trillion"), fx)
        if mc:
            lines.append(f"Market cap {mc}")
        ratio = []
        if m.get("per") is not None:
            ratio.append(f"P/E {m['per']}")
        if m.get("pbr") is not None:
            ratio.append(f"P/B {m['pbr']}")
        if m.get("div_yield") is not None:
            ratio.append(f"Div yield {m['div_yield']}%")
        if ratio:
            lines.append(" · ".join(ratio))
        if m.get("roe") is not None:
            lines.append(f"ROE {m['roe']}%")
    return "\n".join(lines)


_DISCLAIMER_KO = "본 답변은 공시·공개 데이터 기반 정보이며 투자 권유가 아닙니다."
_DISCLAIMER_EN = "Based on public disclosures and data. Not investment advice."


def build(stock, metrics, narrative, lang, fx):
    """최종 답글 문자열."""
    name = stock.get("name") if lang == "ko" else (stock.get("name_en") or stock.get("name"))
    header = f"{name} ({stock.get('ticker')})"
    parts = [header]
    for key in ("definition", "business", "recent"):
        seg = (narrative.get(key) or "").strip()
        if seg:
            parts.append(seg)
    parts.append(_metrics_block(metrics, lang, fx))
    risks = (narrative.get("risks") or "").strip()
    if risks:
        parts.append((("참고 리스크: " if lang == "ko" else "Risk notes: ") + risks))
    parts.append(_DISCLAIMER_KO if lang == "ko" else _DISCLAIMER_EN)
    return "\n\n".join(parts)
