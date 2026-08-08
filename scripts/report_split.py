#!/usr/bin/env python3
"""리포트 무료/유료 구간 분리 — 유료화의 단일 기준(single source of truth).

이 모듈이 "무엇이 무료고 무엇이 유료인가"를 정하는 유일한 곳이다.
아래 셋이 모두 이 모듈을 import 해서 같은 기준을 쓴다.
  · 파이프라인   : 무료분은 정적 커밋, 유료분은 서버(Firestore)로 업로드
  · GEO 페이지   : r/{ticker}.html 을 무료 구간까지만 생성
  · Cloud Function: 결제 확인 후 유료분 전달

화면 섹션 ↔ 데이터 대응(stock.html 렌더 순서 기준):
  [무료] 제목 · 리포트 개요(lead·keypoints) · 사업 구조(business)
         · 실적 추이(quant: 연간/분기 표·차트) · 참고 출처(sources)
  [유료] 실적 분석(earnings) · 산업 분석(industry) · 전망(outlook)
         · 밸류에이션 해설(valuation_comment) · 강세(bull) · 약세(bear)
         · 리스크(risks) · 체크포인트(checkpoints) · 종합 의견(verdict)

주의: quant(재무 수치)는 무료다. 상단 지표표·실적 차트가 이 값을 쓰고,
      숫자 자체는 DART·KRX에서 누구나 얻을 수 있어 상품성이 없다.
      파는 것은 '숫자'가 아니라 '해석'이다.

구버전(v1) 리포트는 전부 무료다. DART에 재무가 공시되지 않아 v2 생성이
불가능한 종목들(2026-08 기준 122개, 대부분 코넥스)이 여기 해당한다.
v1 에는 quant·earnings·industry·valuation_comment·checkpoints 가 없어
요금제에서 약속한 구성을 채우지 못한다. 못 채우는 걸 파는 대신 전부 연다.
"""
import re

# 유료 구간 — 이 키들만 서버가 결제 확인 후 내려준다.
PAID_KEYS = (
    "earnings",           # 실적 분석
    "industry",           # 산업 분석
    "outlook",            # 전망
    "valuation_comment",  # 밸류에이션 해설
    "bull",               # 강세 요인
    "bear",               # 약세 요인
    "risks",              # 리스크 요인
    "checkpoints",        # 다음 체크포인트
    "verdict",            # 종합 의견
    # v1 리포트 폴백에만 있는 서술 섹션
    "recent",             # 최근 실적·주가 (v1)
    "desc",               # 리포트 개요 상세 (v1)
)

# 무료 구간 — 정적 파일로 공개된다(검색 유입·신뢰 확보용).
FREE_KEYS = (
    "title", "lead", "keypoints", "business", "quant", "sources",
    "hasPaid", "teaser",          # split() 이 만들어 붙이는 값
    # 메타데이터(화면 표시·정렬에 필요)
    "ticker", "name", "name_en", "sector", "categories", "market",
    "reportDate", "reportTs", "dataDate", "model", "v",
)


def is_v2(report):
    """전체 구성을 갖춘 v2 리포트인가. v1 에는 'v' 키 자체가 없다."""
    return report.get("v") == 2


def pick_report(ticker, root=None):
    """그 종목에 대해 사이트가 실제로 서빙하는 리포트를 읽는다. 없으면 None.

    ⚠️ 유료화 판단은 반드시 이 함수가 고른 리포트로 해야 한다.
    대부분의 종목은 data/reports(v1)와 data/reports_v2 양쪽에 파일이 있고,
    화면은 v2 를 쓴다(stock.html 931~939행의 v2 → v1 폴백). 그런데 split()
    은 v1 을 받으면 전문을 무료로 연다. 그러니 v2 가 있는 종목의 v1 파일을
    그대로 split() 에 넘기면 그 종목의 유료 구간이 통째로 열린다.
    """
    from pathlib import Path
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    import json as _json
    for sub in ("reports_v2", "reports"):          # stock.html 과 같은 우선순위
        f = root / "data" / sub / f"{ticker}.json"
        if f.exists():
            rp = _json.loads(f.read_text(encoding="utf-8"))
            if isinstance(rp, dict):
                return rp
    return None


def split(report):
    """리포트 dict → (무료분, 유료분). 원본은 건드리지 않는다.

    FREE/PAID 어디에도 없는 키가 새로 생기면 '무료'로 흘러가 유료 콘텐츠가
    새는 사고가 난다. 그래서 미지의 키는 안전한 쪽(유료)으로 보낸다.

    ⚠️ 넘기는 리포트는 pick_report() 로 고른 것이어야 한다. 사유는 그 함수 설명 참고.
    """
    # v1 은 유료 구간이 없다 — 전문을 무료로 공개한다(모듈 설명 참고).
    if not is_v2(report):
        free = dict(report)
        free["hasPaid"] = False
        return free, {}

    free, paid = {}, {}
    for k, v in report.items():
        if k in PAID_KEYS:
            paid[k] = v
        elif k in FREE_KEYS:
            free[k] = v
        else:
            paid[k] = v          # 미지의 키 → 보수적으로 유료 처리
    # 프런트가 "유료 구간이 존재하는지" 알아야 잠금 UI를 그린다.
    free["hasPaid"] = bool(paid)
    # 잠긴 구간의 첫 문장과 분량. 본문이 아니라 '겉모습'이라 무료분에 둔다.
    if paid:
        free["teaser"] = teaser(report)
    return free, paid


# 잠긴 구간의 '겉모습' — 무엇이 몇 개, 얼마나 긴가. 글자는 주지 않는다.
# 화면 순서와 종류는 stock.html renderV2 와 같아야 한다.
TEASER_ORDER = (
    ("earnings", "prose"), ("industry", "prose"), ("outlook", "prose"),
    ("valuation_comment", "prose"),
    ("bull", "factors"), ("bear", "factors"), ("risks", "pairs"),
    ("checkpoints", "pairs"), ("verdict", "wrapup"),
)

# 문장 경계 — stock.html splitSentences 와 같은 기준이어야 문단 수가 맞는다.
_SENT = re.compile(r"(?:[다요죠음함됨임]\.)\s+|(?:[.!?])\s+(?=[A-Z가-힣\"'(])")


def _one_line(v):
    return " ".join(str(v or "").split())


def _lang(v, lang):
    if isinstance(v, dict):
        return v.get(lang) or v.get("ko") or v.get("en") or ""
    return v or ""


def _sentences(t):
    out, last = [], 0
    for m in _SENT.finditer(t):
        out.append(t[last:m.end()].strip())
        last = m.end()
    tail = t[last:].strip()
    if tail:
        out.append(tail)
    return [x for x in out if x]


def _para_lens(t, per=3):
    """화면이 그릴 문단 하나하나의 길이. stock.html prose()/chunkPara() 와 같은 규칙.

    문단 수와 길이가 맞아야 흐린 판의 덩어리 모양이 실제와 겹친다.
    """
    out = []
    for block in str(t or "").split("\n\n"):
        block = " ".join(block.split())
        if not block:
            continue
        ss = _sentences(block)
        if len(ss) <= per + 1:
            out.append(len(block))
            continue
        for i in range(0, len(ss), per):
            out.append(len(" ".join(ss[i:i + per])))
    return out


def _shape(v, kind, lang):
    """섹션 하나의 뼈대. 글자는 없고 개수와 길이만 있다."""
    if kind == "prose":
        return {"paras": _para_lens(_lang(v, lang))}
    if kind == "wrapup":
        return {"paras": _para_lens(_lang((v or {}).get("body"), lang))}
    if kind == "factors":
        return {"items": [[len(_one_line(_lang(f.get("title"), lang))),
                           len(_one_line(_lang(f.get("body"), lang)))] for f in (v or [])]}
    if kind == "pairs":
        # 리스크(cat/body)와 체크포인트(when/what) 는 모양이 같다 — 짧은 앞머리 + 본문.
        out = []
        for it in (v or []):
            a = it.get("cat", it.get("when"))
            b = it.get("body", it.get("what"))
            out.append([len(_one_line(_lang(a, lang))), len(_one_line(_lang(b, lang)))])
        return {"items": out}
    return {}


def teaser(report):
    """비구독자에게 보여 줄 뼈대를 만든다 — 글자는 빼고 모양만.

    본문을 내려보내 놓고 CSS 로 흐리게 덮으면, 개발자 도구에서 filter 한 줄만
    지우면 그대로 읽힌다. 안 판 것과 같다. 그래서 여기서 나가는 건 '무엇이 몇
    개 있고 각각 몇 글자인가'뿐이다. 화면은 그 수만큼 아무 뜻 없는 글자를 깔고
    크게 흐린다 — 벗겨도 나올 게 없다.

    대신 문단 수·항목 수·각 길이를 실제와 똑같이 맞춘다. 그래야 흐린 판의
    덩어리 모양과 위치가 진짜 리포트와 겹친다.

    [{"k": 키, "t": 종류, "paras"|"items": [...]}]
    """
    if not is_v2(report):
        return []
    out = []
    for key, kind in TEASER_ORDER:
        v = report.get(key)
        if not v:
            continue
        sh = _shape(v, kind, "ko")
        if not (sh.get("paras") or sh.get("items")):
            continue
        out.append(dict(k=key, t=kind, **sh))
    return out


def unknown_keys(report):
    """FREE/PAID 어디에도 정의되지 않은 키 목록(스키마 변경 감지용)."""
    return sorted(k for k in report if k not in PAID_KEYS and k not in FREE_KEYS)


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    tk = sys.argv[1] if len(sys.argv) > 1 else "005930"
    root = Path(__file__).resolve().parent.parent
    src = root / "data" / "reports_v2" / f"{tk}.json"
    if not src.exists():
        src = root / "data" / "reports" / f"{tk}.json"
    rp = json.loads(src.read_text(encoding="utf-8"))

    free, paid = split(rp)
    unk = unknown_keys(rp)

    def size(d):
        return len(json.dumps(d, ensure_ascii=False))

    print(f"[{tk}] {rp.get('name','')} — {src.relative_to(root)}")
    print(f"  무료: {len(free):2}개 키 · {size(free):>7,}자  {sorted(free)}")
    print(f"  유료: {len(paid):2}개 키 · {size(paid):>7,}자  {sorted(paid)}")
    if unk:
        print(f"  ⚠️ 미정의 키(유료로 처리됨): {unk}")
