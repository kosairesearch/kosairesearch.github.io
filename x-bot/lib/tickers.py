"""종목 매칭 — 멘션 텍스트에서 종목을 찾아낸다.

정규화(소문자·부호제거·영문 접미어제거) + 별칭 사전 + 정확일치 → 부분일치 순.
build_tickers.py가 만든 data/tickers.json을 읽는다(런타임 pykrx 불필요).
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_TICKERS_PATH = os.path.join(_HERE, "..", "data", "tickers.json")

_EN_STOP = {"co", "ltd", "inc", "corp", "corporation", "company", "limited",
            "holdings", "holding", "group", "co.", "ltd.", "inc.", "the"}

_DATA = None


def norm_ko(s):
    s = (s or "").lower()
    return re.sub(r"[\s\.\,\/\(\)·\-&']", "", s)


def norm_en(s):
    s = (s or "").lower()
    s = re.sub(r"[\.\,\/\(\)·\-&']", " ", s)
    toks = [t for t in s.split() if t and t not in _EN_STOP]
    return "".join(toks)


def _load():
    global _DATA
    if _DATA is not None:
        return _DATA
    with open(_TICKERS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    stocks = raw["stocks"]
    by_ticker = {s["t"]: s for s in stocks}
    ko_exact, en_exact = {}, {}
    for s in stocks:
        kn, en = norm_ko(s["ko"]), norm_en(s["en"])
        if kn:
            ko_exact.setdefault(kn, s["t"])
        if en:
            en_exact.setdefault(en, s["t"])
    _DATA = {
        "stocks": stocks,
        "by_ticker": by_ticker,
        "ko_exact": ko_exact,
        "en_exact": en_exact,
        "aliases": raw.get("aliases", {}),
    }
    return _DATA


def has_hangul(text):
    return bool(re.search(r"[가-힣]", text or ""))


def _mcap(t, d):
    return d["by_ticker"].get(t, {}).get("mcap", 0) or 0


def _candidates(text):
    """멘션에서 @핸들 제거 후 매칭 후보 문자열들을 생성(전체·토큰·인접 2-gram)."""
    cleaned = re.sub(r"@\w+", " ", text or "")
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    # 6자리 코드 직접 언급도 후보
    codes = re.findall(r"\b\d{6}\b", cleaned)
    toks = [w for w in re.split(r"[\s,]+", cleaned) if w]
    cands = []
    cands += codes
    cands.append(cleaned.strip())
    cands += toks
    for i in range(len(toks) - 1):
        cands.append(toks[i] + toks[i + 1])       # 붙여쓴 2-gram (예: 삼성 전자)
    # 중복 제거(순서 유지)
    seen, out = set(), []
    for c in cands:
        if c and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def match(text):
    """멘션 텍스트 → (ticker, stock_dict) 또는 (None, None).

    우선순위: 6자리코드 → 별칭 → 한/영 정확일치 → 부분일치(가장 시총 큰 것)."""
    d = _load()
    for cand in _candidates(text):
        # 1) 6자리 코드
        if re.fullmatch(r"\d{6}", cand) and cand in d["by_ticker"]:
            return cand, d["by_ticker"][cand]
        kn = norm_ko(cand)
        # 2) 별칭
        if kn in d["aliases"]:
            t = d["aliases"][kn]
            return t, d["by_ticker"].get(t)
        # 3) 정확일치(한글/영문)
        if len(kn) >= 2 and kn in d["ko_exact"]:
            t = d["ko_exact"][kn]
            return t, d["by_ticker"][t]
        en = norm_en(cand)
        if len(en) >= 3 and en in d["en_exact"]:
            t = d["en_exact"][en]
            return t, d["by_ticker"][t]
    # 4) 부분일치 — 후보가 종목명의 접두/부분과 겹치면. 오탐 줄이려 최소 길이 제한.
    best = None
    for cand in _candidates(text):
        kn = norm_ko(cand)
        if len(kn) >= 2:
            for name_norm, t in d["ko_exact"].items():
                if kn == name_norm:
                    continue
                if name_norm.startswith(kn) or kn.startswith(name_norm) or kn in name_norm:
                    if best is None or _mcap(t, d) > _mcap(best, d):
                        best = t
        en = norm_en(cand)
        if len(en) >= 4:
            for name_norm, t in d["en_exact"].items():
                if en == name_norm:
                    continue
                if name_norm.startswith(en) or en in name_norm:
                    if best is None or _mcap(t, d) > _mcap(best, d):
                        best = t
    if best:
        return best, d["by_ticker"][best]
    return None, None
