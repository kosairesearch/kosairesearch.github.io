#!/usr/bin/env python3
"""리포트 본문 금지 표현 검사 — 프롬프트가 못 막은 것을 잡는다.

프롬프트는 부탁이지 강제가 아니다. 2,563개를 점검했더니 금지해 둔 표현이
26건 새어 나와 있었다(ROE 8 · TTM 용어 11 · '저평가/고평가' 단정 7).
비율로는 1% 미만이지만, 통제 수단이 프롬프트뿐이면 만들 때마다 그만큼 샌다.

  · 생성 파이프라인(generate_reports_v2.collect)이 리포트마다 호출해 로그에 남긴다
  · 단독 실행하면 이미 쌓인 리포트를 전수 검사한다

      python3 scripts/check_report_text.py                 # data/reports_v2 전체
      python3 scripts/check_report_text.py 005930 000660   # 특정 종목만

검사는 '틀린 것'이 아니라 '우리가 안 쓰기로 한 것'을 본다. 법적 위험(가치
판단 단정)과 품질 문제(화면에 없는 지표·전문 용어)가 섞여 있고, 심각도는
level 로 구분한다.

글자 결함(defects)도 여기서 본다 — 깨진 글자(�)·엉뚱한 글자('경쁴력')·태그
('<sup index=…>')와 그 조각·모델이 받은 자료를 가리키는 말('제공된 데이터셋'). 표현이 아니라
글자 자체가 망가진 것이라 읽는 사람이 바로 본다(2026-09-26, 사장이 먼저 봤다).
태그는 clean_markup 이 저장 전에 지우고, 나머지는 교정(repair)이 그 섹션만 고친다.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "reports_v2"

# 본문을 이루는 필드들 — 새 섹션이 생기면 여기에 더한다.
PROSE_KEYS = ("lead", "business", "earnings", "industry", "outlook",
              "valuation_comment")
LIST_KEYS = ("keypoints", "risks", "bull", "bear", "checkpoints")
# 제목과 옛 형식(신규 상장 리포트)의 칸 — 2026-10-09 까지 표현 규칙이 이 칸을 보지 않았다(제목의 '저평가' · 옛 형식 '최근 동향'의
# 가치 단정이 그대로 저장됐다). 글자 결함(defects)은 원래 모든 칸을 본다.
EXTRA_KEYS = ("title", "desc", "recent")

# 면책 문구는 금지어를 포함할 수밖에 없다 — 검사 대상에서 뺀다.
DISCLAIMER = re.compile(r"(투자\s*권유|정보\s*제공\s*목적|투자\s*판단(의|에)?\s*책임)")

# 증권사명 / 시점 — 목표주가 인용의 조건을 확인할 때 쓴다.
BROKER = re.compile(r"[가-힣A-Za-z]{2,10}(증권|투자증권|자산운용|리서치)")
WHEN = re.compile(r"(20\d{2}\s*년|\d{1,2}\s*월|분기|상반기|하반기|최근)")
# 목표주가 '숫자'를 옮길 때만 인용 조건을 따진다. 숫자 없이 "목표주가를 하향했다"는
# 시장 사실 전달이라 조건을 걸 대상이 아니다.
PRICE_NUM = re.compile(r"\d[\d,]*\s*(원|만원)")
# 증권사 + 전달 동사가 같은 문장에 있으면 '우리 판단'이 아니라 인용이다.
SAY = re.compile(r"(평가|분석|제시|전망|판단|진단|추정|설명)(했|하)")

RULES = (
    # (키, 심각도, 정규식, 설명)
    ("roe", "품질", re.compile(r"\bROE\b|자기자본이익률"),
     "서비스 화면에서 뺀 지표 — 글에만 나오면 독자가 찾을 곳이 없다"),
    ("term", "품질", re.compile(r"\bTTM\b|선행\s*PER|후행\s*PER"),
     "일반 독자가 모르는 용어 — '최근 네 개 분기 기준'처럼 풀어 쓸 것"),
    ("valuejudge", "위험", re.compile(
        r"(저평가|고평가)\s*(된|되어|다|이다|구간|상태|영역)|제값을\s*못\s*받"),
     "가치 판단 단정 — 손실 분쟁 시 근거가 된다. 사실 비교로 대체할 것"),
    # 리포트 본문은 '…이다/…한다' 로 쓴다. 독자에게 말을 거는 순간
    # 리서치가 아니라 권유문이 된다. 2,563개 중 한 건(001520)의
    # 체크포인트가 통째로 "…확인하세요" 로 새어 나와 있었다.
    #
    # 문장 끝(.!?)이 뒤따를 때만 잡는다. 그냥 글자만 보면 작품 제목
    # ('사랑이라 말해요')이나 '식품위해요소' 같은 말이 걸린다.
    ("tone", "품질", re.compile(r"(하세요|해요|주세요|보세요|인가요|나요)(?=\s*[.!?])"),
     "독자에게 말을 거는 말투 — 본문은 '…이다/…한다' 로 쓸 것"),
    # 주당지표의 '수치' — 공시가 갱신되면 값이 바뀌는데 본문은 그대로 남는다.
    # 프롬프트가 금지하는데도 2,563개 중 38개(1.5%)가 새어 나왔고, 그중 42군데는
    # 지금 값과 크게 어긋나 있었다. 최악은 부호까지 뒤집힌 것이다 — 본문은
    # "EPS 785원"인데 실제는 -155원(적자)이라 흑자로 읽힌다.
    #
    # 배당금(DPS·주당배당금)은 일부러 뺐다. "삼성물산 주당배당금에서 2,500원을
    # 초과하는 부분" 처럼 계약 조건을 옮긴 사실 서술이 섞여 있어, 고쳐 쓰면
    # 없던 오류가 생긴다.
    ("pershare", "품질", re.compile(
        r"(\bEPS\b|\bBPS\b|주당\s*(순이익|순자산))[^.\n]{0,10}?\d[\d,]*\s*원"),
     "주당지표 수치 — 공시가 갱신되면 본문만 낡은 숫자로 남는다. 수준을 관계로 서술할 것"),
    # 우리 목소리의 투자 판단 — '보수적 접근이 타당하다는 판단이다' · '현 밸류에이션이 실행 위험을 충분히 반영하지 않은 상태로
    # 판단된다' · '업사이드 기대가 아직 주가에 충분히 반영되지 않았을 가능성' (2026-10-09 신규 상장 리포트 6편 · 증권사 인용은 허용).
    ("stance", "위험", re.compile(
        r"(?:보수적|신중한|선별적)(?:인)?\s*(?:접근|대응|관점)(?:이|을)?\s*(?:타당|합리적|바람직)"
        r"|(?:아직\s*|충분히\s*|온전히\s*)+반영(?:되지|하지)\s*(?:않은|못한)\s*(?:업사이드|상태로\s*(?:판단|볼\s*수))"
        r"|업사이드\s*기대가\s*(?:아직\s*)?(?:주가에\s*)?(?:충분히\s*)?반영되지"),
     "우리 목소리의 투자 판단 — 판단은 독자에게 맡기고 사실과 확인할 지점으로 쓸 것"),
    ("solicit", "위험", re.compile(
        r"매수\s*(추천|권[유고])|매도\s*(추천|권[유고])|지금이\s*기회"
        r"|(?<![가-힣])담을\s*만하|사\s*모을\s*만하"),
     "투자 권유로 읽히는 표현"),
    # 보고서 문체가 아닌 문장 끝(2026-10-09) — 합쇼체 · 해요체 8편 78문장(더존비즈온은 본문 전체), 기업 개요를 그대로 옮긴 명사형
    # 종결('…영위하고 있음.' · '…변경하였음.') 49문장. 문장 끝에서 마침표가 있을 때만 본다(핵심 포인트의 명사구는 보지 않는다).
    ("style", "품질", re.compile(
        r"(?:(?:습|입|합|됩|십|옵|큽|갑|봅|줍|냅|납|집|칩)니다|(?:해|에|예|어|아)요"
        r"|있음|없음|했음|됐음|되었음|하였음|이었음|였음|(?<=[가-힣\s])(?:함|됨|임))[.!?]$"),
     "보고서 문체가 아니다('…있습니다' · '…있음.') — '…이다 · …했다'로 끝낼 것"),
)


def _ko(v):
    if isinstance(v, dict):
        return (v.get("ko") or "").strip()
    return v.strip() if isinstance(v, str) else ""


def _en(v):
    if isinstance(v, dict):
        return (v.get("en") or "").strip()
    return ""


HANGUL = re.compile(r"[가-힣]")
HANJA = re.compile(r"[一-鿿]")


def _verdict_body(rep):
    """종합 의견 본문 — {"body": {ko, en}} 이 보통이고, 옛 형식에는 글 하나({ko, en} 또는 문자열)도 있다."""
    v = rep.get("verdict")
    if isinstance(v, dict) and "body" in v:
        return v.get("body")
    return v


def en_texts(rep):
    """(섹션명, 영문) 목록 — 영문에 한글이 남았는지 볼 때 쓴다."""
    out = []
    for k in PROSE_KEYS + EXTRA_KEYS:
        out.append((k, _en(rep.get(k))))
    out.append(("verdict", _en(_verdict_body(rep))))
    for k in LIST_KEYS:
        for x in (rep.get(k) or []):
            if isinstance(x, dict) and ("ko" in x or "en" in x):
                out.append((k, _en(x)))              # 핵심 포인트 {ko, en}
            elif isinstance(x, dict):
                for f in ("title", "what", "when", "body", "cat"):
                    out.append((k, _en(x.get(f))))
            else:
                out.append((k, _en(x)))
    return [(k, t) for k, t in out if t]


def sentences(rep):
    """(섹션명, 문장) 목록. 문장 단위로 봐야 어디가 문제인지 짚어 줄 수 있다."""
    out = []

    def add(sec, text):
        for s in re.split(r"(?<=[.。!?])\s+|\n+", text or ""):
            s = s.strip()
            if s:
                out.append((sec, s))

    for k in PROSE_KEYS + EXTRA_KEYS:
        add(k, _ko(rep.get(k)))
    add("verdict", _ko(_verdict_body(rep)))
    for k in LIST_KEYS:
        for x in (rep.get(k) or []):
            if isinstance(x, dict) and ("ko" in x or "en" in x):
                add(k, _ko(x))                       # 핵심 포인트 {ko, en} — 2026-10-09 까지 이 꼴을 보지 않았다
            elif isinstance(x, dict):
                for f in ("title", "what", "when", "body", "cat"):
                    add(k, _ko(x.get(f)))
            else:
                add(k, _ko(x))
    return out


# ── 글자 결함 — 사람이 읽을 수 없는 자리 ─────────────────────────────────────
# 2026-09-26 사장이 HLB 리포트 본문에서 '<sup index="36-2,36-3"></sup>' 를 먼저 봤다. 전수로 훑으니
#   · 태그 — 2026-09-05 배치 5개 리포트(<sup index>·<citation index>·<a href>·<br>). 웹 검색 인용을 흉내 냈다
#   · 깨진 글자(�) — 186개 리포트 221곳('경�쟁력' · '용인캠�스' · '두드러�게')
#   · 엉뚱한 글자 — 150여 곳('경쁴력' · '경쟟하는' · '플랕폼' · '꾽힌다' · '흑자전환 딖'). 대부분 '경쟁'
#   · 받은 자료를 가리키는 말 — '제공된 데이터셋에 포함되지 않아' · '자료 창 안에서 …(null)'
# 금지 표현 검사는 표현만 봤지 글자는 보지 않았다. 엉뚱한 글자는 자주 쓰는 한글 2,350자(KS X 1001)
# 밖이라는 점으로 잡는다 — 2,564개 리포트에서 그 밖의 글자 123곳 중 맞는 말은 셋(아래 _KS_OK)뿐이었다.
# 2,350자 안에서 바뀐 것('경쨍')은 못 잡는다 — 가장 흔한 '경쟁' 은 _KO_GLITCH 로 따로 본다.
# 2026-10-03 — 같은 배치에 태그가 반쯤 지워진 조각이 더 있었다. 위 규칙은 온전한 태그만 봐서 놓쳤다.
#   · 모델 자신의 인용 태그 조각 — 조흥 5곳('제한\antml:cite>될' · '생산\antml:cite>하는')
#   · 속성 끝만 남은 조각 — 한스바이오메드 4곳('제출">하며' · '부연">했다')
#   · 따옴표 앞 역슬래시 — 스튜디오미르 1곳('X-Men \'97')
# 조각도 태그와 같은 등급(markup · 위험)이다. 역슬래시는 본문에 쓸 일이 없어 어디에 있든 결함으로 본다.
_MARKUP = (
    (re.compile(r"<sup\b[^<>]*>.*?</sup>", re.S | re.I), ""),        # 인용 번호 — 뜻이 없다
    (re.compile(r"<sup\b[^<>]*/?>|</sup>", re.I), ""),
    (re.compile(r"</?(?:citation|cite)\b[^<>]*>", re.I), ""),        # 인용이 감싼 글은 남긴다
    (re.compile(r"<?\\?/?\\?antml:[a-z_]+\b[^<>\n]{0,80}>", re.I), ""),  # 모델의 인용 태그와 그 조각 — 감싼 글은 남긴다
    (re.compile(r"\\(?=[\"'])"), ""),                                 # 따옴표 앞 역슬래시
    (re.compile(r"<a\s[^<>]*href\s*=[^<>]*>|</a>", re.I), ""),       # 링크가 감싼 글은 남긴다
    (re.compile(r"<br\s*/?>|</br>", re.I), " "),
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"\1"),              # 마크다운 굵게
    (re.compile(r"&(?:amp|#38);"), "&"), (re.compile(r"&(?:quot|#34);"), '"'),
    (re.compile(r"&(?:#39|apos);"), "'"), (re.compile(r"&nbsp;"), " "),
    (re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]"), ""),        # 보이지 않는 글자
)


_QGT = re.compile(r"[\"']>")


def _stray_qgt(t):
    """속성 끝만 남은 조각('제출">하며')의 자리들. 열린 꺾쇠 안(제목 <'오징어 게임'> · 온전한 태그)은 빼고 본다."""
    return [m.span() for m in _QGT.finditer(t) if t.rfind("<", 0, m.start()) <= t.rfind(">", 0, m.start())]


def clean_markup(s):
    """태그·인용 표시·마크다운·HTML 이름표를 지운다. 감싼 글은 남긴다. 결정적이라 저장 전에 늘 돌린다."""
    if not isinstance(s, str) or not s:
        return s
    t = s
    for pat, rep in _MARKUP:
        t = pat.sub(rep, t)
    for a, b in reversed(_stray_qgt(t)):
        t = t[:a] + t[b:]
    if t != s:
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = re.sub(r"[ \t]*\n[ \t]*", "\n", t).strip()
    return t


_NOT_TEXT = {"sources", "quant", "ticker", "name", "name_en", "market", "sector", "categories",
             "reportDate", "reportTs", "dataDate", "v", "hasPaid", "model", "usage", "meta", "asOf"}
_KS_OK = set("웻몐퀜")          # 2,350자 밖이지만 맞는 말 — 웻 스테이션 · 쓰촨성 몐양 · 초전도 코일 퀜치
_TAG = re.compile(r"<\s*/?\s*(?:sup|sub|citation|cite|br|span|div|p|b|i|em|strong|u|small|mark|ref|source|li|ul|ol|table|tr|td|h[1-6])"
                  r"\b[^<>]{0,160}>|<a\s[^<>]*href|\b(?:index|href|src|class)\s*=\s*\"|\*\*|&(?:amp|lt|gt|quot|nbsp|#\d+);"
                  r"|antml:|\\", re.I)
_ODD = re.compile("[\ufffd\u0400-\u04ff\u0590-\u08ff\u0900-\u0dff\u0e00-\u0eff]")   # 깨진 글자 · 키릴·히브리·아랍·인도계·타이 문자
_KO_GLITCH = re.compile("경[쁌쳥쟰쁁쨍쟃쁏숁섄쪆쥉쁀쭁쟐쁙쥰쁩쁭쁠쁨쟟쁄쁴쁜쇄]")        # '경쟁' 이 깨진 꼴(2,350자 안에 드는 것까지)
_HAN_IN_EN = re.compile(r"[一-鿿]")
_HAN_IN_KO = re.compile(r"(?<=[가-힣])[一-鿿]+|[一-鿿]+(?=[가-힣])")   # 괄호 병기 '상저하고(上低下高)' 는 안 걸린다
# 2026-10-09 넓혔다 — '제공된 분기 구간 중 최대' · '제공된 다섯 개 분기 가운데' · '제시된 분기 구간' · '최근 4개 분기 창' ·
# '이 리포트의 확정 데이터 범위 밖' · 'the five quarters provided' · 'the disclosed quarterly window' · 'in the dataset' 이 리포트
# 125편에 260곳 있었다(앞의 규칙은 '제공된 데이터' 처럼 붙어 있는 꼴만 봤다). 바깥 자료의 이름('IMS 데이터 기준' · '한국경제 시장
# 데이터 기준'), 임상 '확정 데이터 공개', '확정 재무 데이터'(공시 확정치라는 뜻이라 읽는 사람도 안다), '창사', 화면의 표를 가리키는
# 'the four years shown', 'data provided by subsidiaries' 는 그대로 둔다.
_META_KO = re.compile(
    r"제공(?:된|받은)\s*(?:기준\s*|참고\s*|입력\s*)?(?:\[?확정\s*재무\]?\s*|확정\s*|최근\s*)?(?:데이터|자료|재무|분기|구간|기간|수치|연도|범위|실적"
    r"|\d+\s*개\s*(?:분기|연도|년)|[가-힣]{1,2}\s*개\s*(?:분기|연도|년))"
    r"|제시된\s*(?:\d+\s*개\s*|[가-힣]{1,2}\s*개\s*)?(?:분기|구간)|제공\s*데이터|이번\s*데이터셋|(?:자료|데이터)\s*창|분기\s*창(?!사|업|립|출|고|구|작|조)|데이터\s*구간\s*내|\[확정\s*재무\]"
    r"|(?:이|본)\s*리포트(?:가|의)\s*(?:사용하는\s*|다루는\s*)?(?:확정\s*)?(?:재무\s*)?(?:데이터|자료)|우리\s*(?:확정\s*)?(?:재무\s*)?데이터"
    r"|\(null\)")
_META_EN = re.compile(
    r"data window|disclosed window|quarterly window|provided (?:confirmed )?(?:data|dataset|financial data|financials|figures|quarters|periods|results|reference data)"
    r"|(?:quarters|periods|figures|financials|data) provided(?! by)|this dataset|dataset provided|(?:in|within|across|from) the data ?set\b"
    r"|\bour (?:confirmed )?(?:financial )?data(?:set)?\b|this report's (?:confirmed )?(?:financial )?data(?:set)?"
    r"|data (?:covered|used) (?:by|in) this report|\(null\)", re.I)


# ── 상대 시점 · 한자 · 영어 낱말(2026-10-09) ────────────────────────────────────────────────────────────────
# 업종 분석 30편을 전수로 읽으니 사람이 먼저 볼 결함이 셋 더 있었다(사장이 크게 질책했다).
#   · 상대 시점 — 글은 저장된 뒤 몇 주에서 몇 달 동안 그대로 걸린다. '효성중공업은 지난달에만 …' 의 '지난달' 은 그새 다른
#     달을 가리킨다. 리포트 37편에도 '지난달' · '이달 초' · '다음 달' · '오늘 기준' 이 있었다. 날짜로 써야 한다. '올해' ·
#     '지난해' 는 해가 바뀌기 전까지 맞으므로 보지 않는다. 회사 · 브랜드 이름('오늘이엔엠' · '모레모' · '오늘의집' · '미디어오늘'),
#     따옴표 안의 작품명('내일도 출근!'), 앞 문장에 기댄 '그 다음 달' 은 뺀다(조사 뒤에 한글이 이어지면 이름이다).
#   · 한자 — 한글 옆에 붙은 것만 보던 규칙이 'ESS向 공급'(영문 옆)을 놓쳤다. 괄호 병기 '상저하고(上低下高)' 와 읽기를 붙인
#     이름 '楽一(라쿠이치)' 은 뺀다.
#   · 영어 낱말 — 'Phase에 진입' · 'niche 영역' · 'valuation의 핵심 변수' · '실적 risk'. 우리말이 있는 일반 낱말만 본다(목록) —
#     괄호 병기 '니치(niche)', 영문 이름의 일부('Point-of-Care' · 'Phase2' · 'Phase 3 임상'), 업계에서 그대로 쓰는 약어
#     (CAPEX · Tier 1 · HBM)는 뺀다.
_TAIL = r"(?=(?:에는|에도|에서|에만|부터|까지|보다|처럼|으로|로|에|의|은|는|도|만|이|가|와|과|초|말|중순|중)?(?![가-힣]))"
_STALE = re.compile(
    r"(?<![가-힣'‘\"“])(?<!그 )(?<!그)(?:"
    r"(?:지난|이번|다음)\s?달" + _TAIL +
    r"|이달" + _TAIL +
    r"|(?:지난|이번|다음)\s?주(?=(?:말|초|에는|에도|에|부터|까지|중)?(?![가-힣]))"
    r"|(?:어제|그제|그저께|엊그제|오늘|내일|모레)" + _TAIL +
    r"|(?:며칠|이틀|사흘)\s?전|최근\s?며칠)")
_HANJA_RUN = re.compile(r"[一-鿿]+")
_EN_WORDS = ("valuation discount premium upside downside momentum niche phase uplift risk issue trend peak guidance "
             "consensus tailwind headwind catalyst rerating re-rating decoupling bottleneck turnaround spread margin cycle "
             "stage level mix capacity utilization backlog pipeline upcycle downcycle outlook growth demand supply "
             "sentiment shortage").split()
_EN_WORD = re.compile(r"(?<![A-Za-z0-9\-])(?:" + "|".join(sorted(map(re.escape, _EN_WORDS), key=len, reverse=True))
                      + r")(?![A-Za-z0-9\-])", re.I)


def stale_time(s):
    """상대 시점 표현의 자리(match) 또는 None."""
    return _STALE.search(s or "")


def hanja_in_ko(s):
    """한국어 문장 속 한자의 자리 또는 None — 괄호 병기 '(上低下高)' · 읽기를 붙인 이름 '楽一(라쿠이치)' 은 뺀다."""
    for m in _HANJA_RUN.finditer(s or ""):
        a, b = m.span()
        if s[a - 1:a] == "(" and s[b:b + 1] == ")":
            continue
        if re.match(r"\([가-힣\s·]+\)", s[b:]):
            continue
        return m
    return None


def en_word_in_ko(s):
    """한국어 문장에 섞인 영어 일반 낱말의 자리 또는 None."""
    for m in _EN_WORD.finditer(s or ""):
        a, b = m.span()
        if s[a - 1:a] == "(" or re.match(r"\s*\)", s[b:]) and "(" in s[max(0, a - 3):a]:
            continue                                   # 괄호 병기 '니치(niche)'
        if re.search(r"[A-Za-z][A-Za-z0-9&.'’\-]*\s*$", s[:a]) or re.match(r"\s*[A-Za-z]", s[b:]):
            continue                                   # 영문 이름 · 구의 일부
        if re.match(r"\s*(?:\d|[IVX]+\b)", s[b:]):
            continue                                   # 'Phase 3' · 'Phase II'
        if any(c.isupper() for c in s[a + 1:b]):
            continue                                   # 대소문자가 섞인 이름 — 임상 'upLIFT' · 'RISK'
        if re.search(r"[A-Za-z]\s*·\s*$", s[:a]) or re.match(r"\s*·\s*[A-Za-z]", s[b:]) or re.match(r"\([가-힣]", s[b:]):
            continue                                   # 영문 이름 목록 'Core·Growth·Seed' · 우리말 병기 'Growth(성장)'
        return m
    return None


def _ks_bad(ch):
    if ch in _KS_OK:
        return False
    try:
        return len(ch.encode("euc_kr")) != 2
    except UnicodeEncodeError:
        return True


def _texts(rep):
    """(섹션, 'ko'|'en'|'', 글) — 본문이 아닌 칸(출처·숫자·메타)은 뺀다. 제목·라벨까지 다 본다."""
    def rec(o, sec, lang):
        if isinstance(o, str):
            yield sec, lang, o
        elif isinstance(o, dict):
            for k, v in o.items():
                yield from rec(v, sec, k if k in ("ko", "en") else lang)
        elif isinstance(o, list):
            for v in o:
                yield from rec(v, sec, lang)
    for k, v in rep.items():
        if k not in _NOT_TEXT:
            yield from rec(v, k, "")


def defects(rep):
    """글자 결함 목록 — check() 가 함께 돌려준다. rule: markup·broken_char(위험) · hanja·meta(품질)."""
    hits = []

    def add(rule, level, sec, s, a, b, why):
        hits.append({"rule": rule, "level": level, "section": sec, "match": s[a:b][:24], "why": why,
                     "sentence": s[max(0, a - 60):b + 60]})

    for sec, lang, s in _texts(rep):
        m = _TAG.search(s)
        q = m.span() if m else next(iter(_stray_qgt(s)), None)
        if q:
            add("markup", "위험", sec, s, q[0], q[1], "태그·인용 표시·마크다운이 글자 그대로 찍힌다 — 지우고 글만 남길 것")
        m = _ODD.search(s) or (_KO_GLITCH.search(s) if lang != "en" else None) or (_HAN_IN_EN.search(s) if lang == "en" else None)
        if not m and lang != "en":
            i = next((i for i, ch in enumerate(s) if "가" <= ch <= "힣" and _ks_bad(ch)), -1)
            if i >= 0:
                add("broken_char", "위험", sec, s, i, i + 1, "깨지거나 엉뚱한 글자 — 문맥에 맞는 올바른 단어로 고칠 것")
        elif m:
            add("broken_char", "위험", sec, s, m.start(), m.end(), "깨지거나 엉뚱한 글자 — 문맥에 맞는 올바른 단어로 고칠 것")
        if lang != "en":
            m = hanja_in_ko(s)
            if m:
                add("hanja", "품질", sec, s, m.start(), m.end(), "한국어 문장에 섞인 한자 — 한글로")
            m = stale_time(s)
            if m:
                add("stale_time", "품질", sec, s, m.start(), m.end(),
                    "상대 시점(지난달 · 이번 주 · 오늘 · 다음 달) — 글이 걸려 있는 동안 다른 날을 가리킨다. '2026년 9월'처럼 날짜로")
            m = en_word_in_ko(s)
            if m:
                add("en_word", "품질", sec, s, m.start(), m.end(), "한국어 문장에 섞인 영어 낱말 — 우리말로('단계' · '틈새' · '밸류에이션')")
        m = (_META_EN if lang == "en" else _META_KO).search(s)
        if m:
            add("meta", "품질", sec, s, m.start(), m.end(), "모델이 받은 자료를 가리키는 말 — 독자는 그 자료를 모른다")
    return hits


# 'N년 연속 감소 · 증가' — 정점 · 저점 다음 해부터 센 햇수보다 크게 쓰면 실적 표와 어긋난다(2026-10-09 검토 시험에서 본느
# '2023년 729억원을 정점으로 2024년 687억원, 2025년 460억원으로 3년 연속 감소'. 전수로 8건 · 6종목 — 모두 정점이 든 해까지 센 오류).
# 글만 보고 판정하되 확실할 때만: 정점 연도가 '정점으로 · 정점을 찍은 뒤 · 정점 이후' 꼴로 있고, 회사 실적(매출 · 이익)을 말하고, 실적 표보다
# 늦은 해(전망)가 없을 때. 끝 연도는 문장에 적힌 더 늦은 해, 없으면 실적 표의 마지막 해. '정점 대비' · 시장 규모 · 전망은 보지 않는다.
_STREAK_PEAK = re.compile(r"(20\d\d)년[^.]{0,25}?(정점|고점|저점|바닥)(?:으로|을 찍은 뒤|을 찍고|을 지나| ?이후|에서)")
_STREAK_N = re.compile(r"(?<![\d,])(\d|두|세|네|다섯)\s*년\s*연속\s*(?:[가-힣]{0,6}\s*)?"
                       r"(감소|줄|축소|하락|역성장|증가|늘|확대|성장|상승|개선)")
_STREAK_KO_N = {"두": 2, "세": 3, "네": 4, "다섯": 5}
_STREAK_METRIC = re.compile(r"매출|영업이익|순이익|영업손실|순손실|이익률")


def streak_hits(rep):
    """정점 · 저점 다음 해부터 센 햇수보다 큰 'N년 연속'. 실적 표(quant.annual)가 없으면 판정하지 않는다."""
    q = rep.get("quant") if isinstance(rep.get("quant"), dict) else {}
    last_data = max((a.get("year") for a in (q.get("annual") or []) if isinstance(a, dict) and isinstance(a.get("year"), int)),
                    default=None)
    if not last_data:
        return []
    hits = []
    for sec, s in sentences(rep):
        pk = _STREAK_PEAK.search(s)
        if not pk or not _STREAK_METRIC.search(s):
            continue
        yrs = [int(y) for y in re.findall(r"20\d\d", s)]
        if any(y > last_data for y in yrs):
            continue
        peak = int(pk.group(1))
        later = [y for y in yrs if y > peak]
        span = (max(later) if later else last_data) - peak
        for st in _STREAK_N.finditer(s, pk.end()):
            n = _STREAK_KO_N.get(st.group(1)) or int(st.group(1))
            if (pk.group(2) in ("정점", "고점")) != (st.group(2) in ("감소", "줄", "축소", "하락", "역성장")):
                continue
            if n > span:
                hits.append({"rule": "streak", "level": "위험", "section": sec, "match": st.group(0),
                             "why": f"{peak}년 {pk.group(2)} 뒤로는 {span}년인데 '{n}년 연속' — 정점 · 저점 다음 해부터 센다",
                             "sentence": s[:160]})
    return hits


# ── 금액: 본문의 이 회사 실적 금액이 공시 값과 같은가(2026-10-10) ─────────────────────────────────────────────────
# 작성 모델이 원 단위 원자료를 '억 · 만'으로 옮기다 자리를 틀렸다 — 2,563편을 대조하니 23편에서 실제로 틀린 금액이 나왔다.
# '2025년 4분기 영업이익은 8.6억원'(실제 8,600만원 · 열 배) · '2025년 연결 매출액은 3,427억 7,375만원'(실제 3,427억 3,774만원) ·
# '2022년 매출 1조 1,148억원'(실제 1조 115억원). 재료를 본문 표기로 주는 것(fin_material)이 예방이고, 이 검사가 마지막 빗장이다.
# 오탐을 막으려고 꼴이 분명한 문장만 본다 — '2025년 (연결) 매출(은) X원' · '2026년 2분기 영업이익 X원' 과 그 뒤에 이어지는 같은
# 기간의 나열('· 영업이익 Y원'). 연도 앞에 다른 회사 · 부문 이름이 오거나, 잠정 · 전망 · 부문 · 누적 · 반기 같은 말이 있거나,
# 어림 표현('… 대' · '을 넘' · '에서')이 붙으면 보지 않는다. 표기의 자릿수만큼(마지막 자리 1.5칸) 차이는 반올림으로 본다.
# 측정(2026-10-10 · 한국어 7,024곳 · 영어 2,024곳): 걸린 29곳 중 오탐은 주어를 앞 문장에 둔 자회사 문장 1곳이었다.
_AN = r"\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?"
_AMT_KO = rf"(?:(?:{_AN})조(?: (?:{_AN})억)?(?: (?:{_AN})만)?|(?:{_AN})억(?: (?:{_AN})만)?|(?:{_AN})만)원"
_AMT_MET = r"매출액|매출|영업이익|영업손실|지배주주 ?순이익|지배주주 ?순손실|당기순이익|당기순손실|순이익|순손실"
_AMT_APPROX = (r"\s*(?:대|가량|안팎|수준|내외|이상|이하|미만|초과|남짓|규모|선|정도|에서|에 육박|에 못 미|에 달|에 이르|에 가까|가까이"
               r"|[을를] (?:\S+ )?(?:넘|웃|밑|돌파|상회|하회))")
_AMT_HEAD = re.compile(rf"(?<![\d~·∼\-])(?P<y>20\d\d)년(?: (?P<n>[1-4])분기)?(?: 연간)?(?: 연결)? (?P<m>{_AMT_MET})(?:은|는|이|가)? "
                       rf"(?P<a>{_AMT_KO})(?!{_AMT_APPROX})")
_AMT_NEXT = re.compile(rf"(?:\([^()]*\))?(?:으로|로|이고|이며|였고|이었고|를 기록했고|을 기록했고)?\s*(?:,|·|및|과|와|그리고)?\s*"
                       rf"(?P<m>{_AMT_MET})(?:은|는|이|가|도)? (?P<a>{_AMT_KO})(?!{_AMT_APPROX})")
_AMT_SKIP = re.compile(r"잠정|전망|예상|추정|컨센서스|목표|가이던스|계획|부문|사업부|자회사|종속|별도|누적|상반기|하반기|반기|합산|평균")
_AMT_LEAD = (r"(?:(?:실제로|다만|한편|반면|또한|특히|이후|그러나|하지만|결국|그 결과|이에 따라|공시 기준으로|공시 기준|연결 기준으로|연결 기준"
             r"|회사 공시 기준|확정 실적에서|확정 실적 기준)\s*,?\s*)*")
_AMT_LOSS_AFTER = re.compile(r"\s*(?:의\s*)?(?:적자|손실)")
_EN_MET = (r"revenue|sales|operating profit|operating income|operating loss"
           r"|net profit attributable to (?:owners|controlling shareholders)(?: of the parent)?"
           r"|net income attributable to (?:owners|controlling shareholders)(?: of the parent)?"
           r"|controlling(?: interest)? net (?:profit|income)|attributable net (?:profit|income)|owner net (?:profit|income)"
           r"|net profit|net income|net loss")
_EN_AMT = r"(?:KRW|₩)\s?(?P<x>\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<u>trillion|billion|million|tn|bn|mn)\b"
_EN_VERB = (r"(?:\s(?:was|were|of|came in at|came to|reached|totaled|totalled|stood at|amounted to|hit|rose|fell|grew|declined|dropped"
            r"|increased|decreased|climbed|slipped|recovered|expanded|shrank|shrinking|narrowed|narrowing|widened|widening|swung|turned"
            r"|improved|jumped|surged|plunged|tumbled|at)"
            r"(?:\s(?:sharply|slightly|further|significantly|modestly|steeply|substantially|marginally|again))?(?:\s(?:to|at))?)?"
            r"(?:\s(?:a|an))?(?:\s(?:record|new))?")
_EN_HEAD = re.compile(rf"(?:(?:In|in|For|for|The|the)\s)?(?:(?P<qq>Q[1-4])\s(?P<qy>20\d\d)|(?P<y2>20\d\d)\s(?P<q2>Q[1-4])"
                      rf"|(?:the\s)?(?P<o>first|second|third|fourth)[- ]quarter(?: of)?\s(?P<oy>20\d\d)|(?P<y>20\d\d))"
                      rf"(?:\s(?:full-year|annual|consolidated))*,?\s(?P<m>{_EN_MET}){_EN_VERB}\s{_EN_AMT}"
                      rf"(?!\s*(?:-plus|\+|range|level|mark))")
_EN_SKIP = re.compile(r"(?i)preliminary|forecast|expect|estimate|consensus|target|guidance|segment|division|subsidiar|affiliate"
                      r"|cumulative|first half|second half|half-year|\bH1\b|\bH2\b|year-to-date|average|plan")
_EN_LEAD = re.compile(r"(?:(?:The company|It|The firm)(?:'s)?\s*)?(?:(?:However|Meanwhile|In addition|Moreover|Also|Indeed|Specifically"
                      r"|By contrast|In contrast|As a result|Since then|Subsequently),?\s*)?")
_EN_UNIT = {"trillion": 1e12, "tn": 1e12, "billion": 1e9, "bn": 1e9, "million": 1e6, "mn": 1e6}
_EN_ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4}


def _amt_value(a):
    """'1,137억 8,253만원' → (값, 마지막 자리 한 칸). '8,700만' 처럼 끝이 0 이면 그만큼 반올림한 표기로 본다."""
    m = re.fullmatch(rf"(?:(?P<jo>{_AN})조)? ?(?:(?P<eok>{_AN})억)? ?(?:(?P<man>{_AN})만)?", a[:-1])
    v, unit = 0.0, None
    for g, mul in (("jo", 1e12), ("eok", 1e8), ("man", 1e4)):
        x = m.group(g) if m else None
        if x:
            raw = x.replace(",", "")
            v += float(raw) * mul
            dec = len(raw.split(".")[1]) if "." in raw else 0
            unit = mul / 10 ** dec
            if g == "man" and dec == 0:
                unit = mul * 10 ** min(len(raw) - len(raw.rstrip("0")), 3)
    return v, unit


def _amt_keys(met, quarterly):
    """본문 지표 → 공시 칸. 분기의 '순이익'(지배주주 아님)은 공시 칸이 없어(분기는 지배주주 순이익만) 보지 않는다(None)."""
    if met.startswith("매출") or met == "revenue" or met == "sales":
        return ["rev"]
    if met.startswith("영업") or met.startswith("operating"):
        return ["op"]
    owner = "지배" in met or "attributable" in met or "controlling" in met or "owner" in met
    if owner:
        return ["np_owner"]
    return None if quarterly else ["np", "np_owner"]


def amount_hits(rep):
    """본문의 이 회사 실적 금액 ↔ 공시 값(quant). 다르면 '위험'. 공시 값이 없거나 외화 공시 회사면 보지 않는다."""
    import fin_material as F                                  # noqa: E402 — 표준 라이브러리만 쓴다(돌림 의존 없음)
    q = rep.get("quant") if isinstance(rep, dict) else None
    if not isinstance(q, dict):
        return []
    if str((q.get("valuation") or {}).get("ccy") or "KRW").upper() != "KRW":
        return []
    an = {a.get("year"): a for a in (q.get("annual") or []) if isinstance(a, dict)}
    qs = {r.get("q"): r for r in (q.get("quarterly") or []) if isinstance(r, dict)}
    if not an and not qs:
        return []
    no_rev = bool(q.get("rev_label"))
    me = re.escape(str(rep.get("name") or "")) or "(?!)"
    lead_ko = re.compile(rf"(?:(?:{me}|회사|동사|당사|이 회사)(?:의|는|은|도|가|이)?\s*)?{_AMT_LEAD}")
    hits = []

    def judge(sec, s, label, row, met, val, unit, loss, en):
        keys = _amt_keys(met.lower() if en else met, quarterly=label[1])
        if keys is None or (no_rev and keys == ["rev"]):
            return
        vals = [row.get(k) for k in keys if row.get(k) is not None and not (k == "rev" and row.get(k) == 0)]
        if not vals:
            return
        good = [x for x in vals if (x < 0) == loss or x == 0]
        if any(abs(abs(x) - val) <= unit * 1.5 for x in good):
            return
        x = vals[0]
        name = {"rev": "매출", "op": "영업이익" if x >= 0 else "영업손실"}.get(keys[0]) or ("순이익" if x >= 0 else "순손실")
        shown = F.won_en(x) if en else F.won(x)
        when = (F.qtext(label[0]) if label[1] else f"{label[0]}년")
        hits.append({"rule": "amount", "level": "위험", "section": sec, "match": s[:0] + met,
                     "why": f"금액이 공시 값과 다르다 — {when} {name} 공시 값은 {shown}"
                            + (" (지배주주 기준)" if keys == ["np_owner"] else "")
                            + " · 이 회사의 값이 아니면 문장 앞에 그 회사 · 부문 이름을 쓸 것",
                     "sentence": s[:160]})

    for path, f in _flat_fields({k: v for k, v in rep.items() if k not in _NOT_TEXT}).items():
        sec = path.split(".")[0]
        for s in re.split(r"(?<=[.!?])\s+", f.get("ko") or ""):
            if _AMT_SKIP.search(s):
                continue
            for m in _AMT_HEAD.finditer(s):
                if not lead_ko.fullmatch(s[:m.start()].strip()):
                    continue
                label = (f"{m.group('y')}Q{m.group('n')}", True) if m.group("n") else (int(m.group("y")), False)
                row = qs.get(label[0]) if label[1] else an.get(label[0])
                if not row:
                    continue
                pairs, pos = [(m.group("m"), m.group("a"), m.end())], m.end()
                while True:
                    nx = _AMT_NEXT.match(s, pos)
                    if not nx:
                        break
                    pairs.append((nx.group("m"), nx.group("a"), nx.end()))
                    pos = nx.end()
                for met, a, end in pairs:
                    val, unit = _amt_value(a)
                    if unit is None:
                        continue
                    loss = "손실" in met or bool(_AMT_LOSS_AFTER.match(s, end))
                    judge(sec, s, label, row, met, val, unit, loss, en=False)
        for s in re.split(r"(?<=[.!?])\s+", f.get("en") or ""):
            if _EN_SKIP.search(s):
                continue
            for m in _EN_HEAD.finditer(s):
                if not _EN_LEAD.fullmatch(s[:m.start()].strip()):
                    continue
                if m.group("qq"):
                    label = (f"{m.group('qy')}Q{m.group('qq')[1]}", True)
                elif m.group("q2"):
                    label = (f"{m.group('y2')}Q{m.group('q2')[1]}", True)
                elif m.group("o"):
                    label = (f"{m.group('oy')}Q{_EN_ORD[m.group('o')]}", True)
                else:
                    label = (int(m.group("y")), False)
                row = qs.get(label[0]) if label[1] else an.get(label[0])
                if not row:
                    continue
                x = m.group("x").replace(",", "")
                u = _EN_UNIT[m.group("u")]
                unit = u / 10 ** (len(x.split(".")[1]) if "." in x else 0)
                loss = "loss" in m.group("m").lower() or bool(re.match(r"\s*(?:loss|deficit)", s[m.end():]))
                judge(sec, s, label, row, m.group("m"), float(x) * u, unit, loss, en=True)
    return hits


def check(rep):
    """위반 목록을 돌려준다. [] 면 통과."""
    hits = []
    for sec, s in sentences(rep):
        if DISCLAIMER.search(s):
            continue
        cited = bool(BROKER.search(s) and SAY.search(s))
        for key, level, pat, why in RULES:
            m = pat.search(s)
            # 출처를 밝힌 인용이면 허용한다(규칙 5-1). 가치 판단도, 증권사가
            # 제시한 주당지표 전망치도 '우리 숫자'가 아니라 '누가 말했다'이다.
            if m and key in ("valuejudge", "pershare", "stance") and cited:
                continue
            if m:
                hits.append({"rule": key, "level": level, "section": sec,
                             "match": m.group(0), "why": why,
                             "sentence": s[:160]})
        # 목표주가는 허용하되 조건부 — 출처(증권사)와 시점이 같은 문장에 있어야 한다.
        if re.search(r"목표\s*주가", s) and PRICE_NUM.search(s):
            miss = []
            if not BROKER.search(s):
                miss.append("증권사명 없음")
            if not WHEN.search(s):
                miss.append("시점 없음")
            if miss:
                hits.append({"rule": "target_price", "level": "위험",
                             "section": sec, "match": "목표주가",
                             "why": "인용 조건 미충족(" + " · ".join(miss) + ")",
                             "sentence": s[:160]})
    # 영문에 한글이 남으면 영어 화면에서 그 자리만 읽을 수 없다. 118개 리포트가 그랬다
    # ("continued착공 declines", "GC녹십자 (approx. 50.1% owned)"). 고유명사라도 로마자로.
    for sec, t in en_texts(rep):
        m = HANGUL.search(t)
        if m:
            i = m.start()
            hits.append({"rule": "hangul_en", "level": "품질", "section": sec,
                         "match": t[i:i + 12], "why": "영문에 한글이 남았다 — 로마자/영문 명칭으로",
                         "sentence": t[max(0, i - 60):i + 60]})
    return hits + streak_hits(rep) + amount_hits(rep) + defects(rep)


# ── 교정: 걸린 문장만 다시 쓴다 ──────────────────────────────────────────
# 프롬프트는 부탁이라 3.9% 가 샌다. 검사에서 걸린 섹션만 작은 모델에 넘겨 위반
# 문장을 규칙에 맞게 고쳐 쓰게 한다. 사실은 바꾸지 않고 표현만 바꾼다. 고친 결과가
# 검사를 더 적게 걸려야만 채택하고, 아니면 원문을 그대로 둔다(로그에 남는다).
REPAIR_MODEL = os.getenv("REPORT_REPAIR_MODEL", "claude-sonnet-5")
_RULE_TEXT = "\n".join(f"  · {key}: {why}" for key, _lv, _pat, why in RULES) + (
    "\n  · target_price: 목표주가 숫자는 증권사명과 시점이 같은 문장에 있을 때만. 둘 중 하나라도 없으면"
    " 그 수치를 지우고 정성 서술로(예: '증권사 목표주가는 큰 폭으로 갈린다')."
    "\n  · hangul_en: 영어(en) 문장에 한글을 쓰지 말 것 — 고유명사는 로마자/영문 명칭으로."
    "\n  · broken_char: 깨진 글자(�)나 엉뚱한 글자가 섞인 단어('경쁴력' · '플랕폼' · '꾽힌다' · '용인캠�스')를 문맥과"
    " 짝 언어(ko↔en)에 맞는 올바른 단어로 고칠 것('경쟁력' · '플랫폼' · '꼽힌다' · '용인캠퍼스'). 영어에 섞인 한자·다른 문자도 영어로."
    "\n  · markup: 태그·링크·인용 표시(<sup …>, <a href>, [1])와 그 조각('\">' · 역슬래시), 마크다운(**)을 지우고 글만 남길 것."
    "\n  · hanja: 한국어 문장에 한자를 섞지 말 것('88億원' → '88억원', '오너家' → '오너 일가')."
    "\n  · meta: '제공된 데이터(셋)'·'자료 창'·'data window'·'provided data' 처럼 받은 자료를 가리키는 말을 쓰지 말 것"
    " — '공시 기준'·'확인되지 않는다'·'the period shown' 처럼."
    "\n  · stale_time: '지난달'·'이번 주'·'오늘'·'다음 달' 같은 상대 시점을 쓰지 말 것 — 날짜를 알면 '2026년 9월'처럼, 모르면"
    " 시점 표현을 뺀다."
    "\n  · en_word: 한국어 문장에 영어 일반 낱말을 섞지 말 것('Phase에 진입' → '단계에 진입', 'niche 영역' → '틈새 영역',"
    " 'valuation' → '밸류에이션')."
    "\n  · streak: 'N년 연속 감소 · 증가'는 실적 표에서 다시 센다 — 정점 · 저점 다음 해부터 센 햇수다('2023년 정점 → 2024 · 2025년 감소'는"
    " 2년 연속). 햇수만 고치고, 같은 칸의 영어(three consecutive years 등)도 같이 고칠 것."
    "\n  · amount: 이 회사의 실적 금액이 공시 값과 다르다 — 위반 설명에 적힌 공시 값으로 그 금액만 고친다(같은 문장의 '전 분기 · 전년'"
    " 금액이 같은 자리에서 틀렸으면 그것도, 같은 칸의 영어 금액도 같은 값으로). 그 문장이 이 회사가 아니라 자회사 · 부문 · 다른 회사의"
    " 수치라면 금액은 두고 문장 앞에 그 이름을 밝힌다.")


def _parse_json(text):
    m = re.search(r"===JSON_START===(.*?)===JSON_END===", text, re.S)
    chunk = (m.group(1) if m else text).strip()
    chunk = re.sub(r"^```(?:json)?", "", chunk).strip()
    chunk = re.sub(r"```$", "", chunk).strip()
    a, b = chunk.find("{"), chunk.rfind("}")
    if a >= 0 and b > a:
        chunk = chunk[a:b + 1]
    try:
        return json.loads(chunk)
    except Exception:
        from json_repair import repair_json
        return repair_json(chunk, return_objects=True)


def _same_shape(a, b):
    """고친 값이 원래 값과 같은 모양인가 — 키 집합·리스트 길이·타입."""
    if isinstance(a, dict):
        return isinstance(b, dict) and set(a) == set(b) and all(_same_shape(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return isinstance(b, list) and len(a) == len(b) and all(_same_shape(x, y) for x, y in zip(a, b))
    return isinstance(b, type(a)) or (isinstance(a, str) and isinstance(b, str))


def repair(cl, rep, hits, model=None):
    """(고친 리포트, 남은 위반) 또는 None(고치지 못함). 위반이 있는 섹션만 넘긴다."""
    secs = [k for k in dict.fromkeys(h["section"] for h in hits) if k in rep]
    if not secs:
        return None
    part = {k: rep[k] for k in secs}
    listing = "\n".join(f"  - [{h['section']}] {h['rule']} — {h['why']}\n    문장: {h['sentence']}" for h in hits[:30])
    prompt = (
        "아래는 기업 리서치 리포트의 일부 섹션(JSON)입니다. 표현 규칙 검사에서 다음 위반이 나왔습니다.\n"
        f"{listing}\n\n규칙:\n{_RULE_TEXT}\n\n"
        "지시:\n"
        "1. 위반된 문장만 규칙에 맞게 고쳐 쓰세요. 사실(숫자·고유명사·인과)은 바꾸지 말고 표현만 바꾸세요 — "
        "다만 amount · streak 위반은 위반 설명에 적힌 공시 값 · 햇수로 그 숫자만 고치세요. "
        "목표주가는 증권사명·시점을 알 수 없으면 수치를 지우고 정성 서술로 바꾸세요.\n"
        "2. 위반이 없는 문장은 글자 하나도 바꾸지 마세요. 키 구조·배열 길이·ko/en 짝을 그대로 유지하세요.\n"
        "3. 영어(en)에 한글이 있으면 로마자 또는 영문 명칭으로 바꾸세요. 한국어(ko)에 한자를 쓰지 마세요.\n"
        "4. 같은 구조의 JSON 하나만 ===JSON_START=== 와 ===JSON_END=== 사이에 출력하세요. 다른 말은 쓰지 마세요.\n\n"
        "===INPUT===\n" + json.dumps(part, ensure_ascii=False) + "\n===INPUT_END===")
    resp = cl.messages.create(
        model=model or REPAIR_MODEL, max_tokens=16000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}])
    text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
    new = _parse_json(text)
    if not isinstance(new, dict) or not _same_shape(part, new):
        return None
    merged = dict(rep)
    merged.update(new)
    remaining = check(merged)
    if len(remaining) < len(hits):
        return merged, remaining
    return None


# ── 검토: 저장 전에 글 전체를 한 번 읽고 틀린 곳만 고친다(2026-10-09) ───────────────────────────────────────────
# 위의 검사는 글자와 정해 둔 표현만 본다. 업종 분석 30편을 사람이 읽으니 그 검사를 다 통과한 글에 이런 것이 있었다
# (사장이 크게 질책했다 — "앞으로 업종 분석이든 리포트 생성이든 할 때, 절대 문제 없도록").
#   · 깨진 문장 — 검색 결과 조각이 문장 안에 끼어 주어가 둘이 됐다('… 가격은 17만 4000m3급 LNG선의 신조선가는 …')
#   · 재료와 다른 서술 — '영업이익이 60~90%대로 급증'(실제 37~113%) · 'HD현대 영업이익 70% 넘게'(실제 262%,
#     72.5%는 다른 회사) · 적자를 '이익 규모가 확대'로
#   · 앞뒤 모순 — 요약은 '음반 판매 부진', 본문은 '반기 판매량 신기록'
#   · 낡은 기사 — 2022년 기사의 '4공장이 가동되면' · 이미 지난 '3분기에는 …할 전망'
#   · 회사 설명 오류 — 콘크리트 펌프카 회사를 로봇 제조사로, 핀테크 회사를 케이블TV 계열로, 영문명 오기
# 이런 것은 글을 읽어야 잡힌다. 그래서 저장 전에 값싼 모델이 재료와 함께 글을 읽고, 고칠 곳만 '고침 목록'으로 돌려준다.
# 글 전체를 다시 쓰게 하지 않는다 — 고칠 곳만 바꾸므로 멀쩡한 문장은 그대로고, 출력도 짧아 값이 싸다.
# 받은 고침은 그대로 믿지 않는다: 옛 글이 그 칸에 정확히 한 번 있어야 하고, 새 글에 본문 · 재료에 없던 수치가 들어
# 있으면 버린다(새 사실을 만들지 못하게). 고친 뒤 글자 결함이 늘면 검토 전체를 버린다. 배치로만 보낸다.
REVIEW_MODEL = os.getenv("REPORT_REVIEW_MODEL", "claude-sonnet-5")
REVIEW_MAX_PATCHES = 60

_REVIEW_ITEMS = (
    "1. 깨진 문장 — 다른 문장(검색 결과 · 기사 제목)이 끼어들어 주어와 서술어가 맞지 않는 문장, 같은 말을 한 문장 안에서 되풀이한"
    " 문장, 문장 성분이 빠져 뜻이 통하지 않는 문장.\n"
    "2. 재료와 다른 서술 — [재료]에 있는 회사의 금액 · 증감률 · 흑자/적자 · 늘었다/줄었다를 다르게 쓴 문장. 여러 회사를 묶은 말"
    "('대부분' · '60~90%대' · '두 자릿수' · '70% 넘게' · '모두')이 실제 값을 다 담지 못하면 회사별 실제 값이나 실제 범위로 고친다."
    " 다른 회사의 값을 붙인 문장, 적자를 이익 증가처럼 쓴 문장도 고친다.\n"
    "3. 앞뒤 모순 — 요약(lead) · 본문 · 위험 요인 사이에서 같은 대상을 반대로 말한 곳(판매 부진 ↔ 판매 신기록, 가격 강세 ↔ 가격 하락)."
    " 기간이 달라 둘 다 맞으면 기간을 밝혀 모순으로 읽히지 않게 한다.\n"
    "4. 시점 — [작성 기준일]보다 앞서 끝난 기간이나 이미 지난 일정을 '…할 전망' · '…할 예정' · '…되면'처럼 앞으로의 일로 쓴 문장,"
    " 오래된 기사의 내용(이미 가동 중인 공장을 '가동되면')을 지금 일처럼 쓴 문장, 상대 시점(지난달 · 이번 주 · 오늘 · 다음 달)."
    " 날짜를 확실히 모르면 시점 표현을 빼고 쓴다.\n"
    "5. 회사 설명 — [회사 설명]과 다르게 회사의 사업을 쓰거나 다른 사업군에 묶은 문장(예: 콘크리트 펌프카 회사를 로봇 제조사로)."
    " 영어 문장의 회사명이 [회사 설명]의 영문명과 다르면 고친다.\n"
    "6. 표기 — 오탈자, 한국어 문장에 섞인 영어 낱말(→ 우리말), 한자, 과장 표현('폭증' · '폭발적' · '역대급'), 독자에게 말을 거는 말투,"
    " 쉼표가 빠진 1,000 이상의 수.\n"
    "7. 영어(en) — 같은 칸의 한국어와 뜻이나 수치가 다른 영어 문장, 한국어에 있는 수치가 빠진 영어 문장.")
_REVIEW_SECTOR = ("\n8. 상장 종목 수 · 업종 시가총액 합계 · 전체 시장 비중을 수치로 쓴 문장(어림수 '170여 개' · '200개를 웃돌' 포함)"
                  " — 수치를 빼고 관계로 쓴다.")


def _flat_fields(o, path=""):
    """{칸 경로: {ko, en}} — 글 칸만. 목록은 번호로('risks.0.body' · 'keypoints.2')."""
    out = {}
    if isinstance(o, dict):
        if ("ko" in o or "en" in o) and all(isinstance(o.get(k, ""), str) for k in ("ko", "en")):
            out[path] = o
            return out
        for k, v in o.items():
            out.update(_flat_fields(v, f"{path}.{k}" if path else k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(_flat_fields(v, f"{path}.{i}" if path else str(i)))
    return out


def review_params(part, *, kind="report", as_of="", material="", names="", hits=(), hints=(), model=None,
                  max_tokens=16000):
    """검토 요청 한 건(배치 params). part 는 글 칸만 담은 dict. kind 는 'report' · 'sector'.
    hits 는 기계 검사에서 걸린 것(반드시 고칠 것), hints 는 기계가 의심한 자리(틀렸을 때만 고칠 것)."""
    label = "업종 분석" if kind == "sector" else "기업 리서치 리포트"
    items = _REVIEW_ITEMS + (_REVIEW_SECTOR if kind == "sector" else "")
    head = f"아래는 {label}의 본문(JSON)입니다. 발행 전에 마지막으로 읽고, 틀린 곳만 최소한으로 고칩니다.\n\n"
    if as_of:
        head += f"[작성 기준일] {as_of}\n\n"
    if material:
        head += "[재료 — 공시 확정치. 이 수치가 맞다]\n" + material.strip() + "\n\n"
    if names:
        head += "[회사 설명 — 각 회사의 사업(기업 리포트 첫 문장) · 영문명]\n" + names.strip() + "\n\n"
    if hits:
        head += "[기계 검사에서 걸린 곳 — 반드시 고칠 것]\n" + "\n".join(
            f"  - [{h['section']}] {h['rule']} — {h['why']}\n    문장: {h['sentence']}" for h in list(hits)[:30]) + "\n\n"
    if hints:
        head += "[확인할 곳 — 기계가 의심한 자리. 실제로 틀렸을 때만 고칠 것]\n" + "\n".join(
            f"  - {x}" for x in list(hints)[:30]) + "\n\n"
    prompt = (
        head + "검토 항목 — 아래에 해당하는 문장만 고친다.\n" + items + "\n\n"
        "고치는 원칙\n"
        "- 문제가 있는 문장만 고친다. 문제가 없는 문장은 한 글자도 바꾸지 않는다. 문장 전체를 다시 쓰기보다 틀린 부분을 바꾼다.\n"
        "- 새 사실 · 새 수치를 만들지 않는다. 수치는 [재료]나 본문에 이미 있는 것만 쓴다. 확인할 수 없는 서술이 틀린 것으로 보이면"
        " 그 서술을 뺀다.\n"
        "- 한국어를 고치면 같은 칸의 영어도 같은 뜻으로 고친다(영어를 고칠 때도 같다).\n"
        "- 문체는 그대로 — 한국어는 '…이다 · …했다'로 끝나는 보고서 문체. 투자 권유 · 가치 단정('저평가' 등)은 쓰지 않는다.\n\n"
        "출력 — 고칠 것이 없으면 {\"patches\": []}. 마커 사이에 JSON 하나만 쓴다.\n"
        "===JSON_START===\n"
        "{\"patches\": [{\"path\": \"칸 경로\", \"lang\": \"ko 또는 en\", \"old\": \"그 칸에 있는 그대로의 글\","
        " \"new\": \"고친 글\", \"why\": \"검토 항목 번호와 짧은 이유\"}]}\n"
        "===JSON_END===\n"
        "- old 는 그 칸의 지금 글에 정확히 한 번 나오는 글이어야 한다(띄어쓰기 · 문장부호까지 같게). 고칠 부분을 담은 한 문장 이내로"
        " 잡는다. 문장을 통째로 빼려면 new 를 \"\" 로.\n"
        "- path 는 아래 JSON 의 칸 경로 그대로 쓴다.\n\n"
        "===INPUT===\n" + json.dumps(_flat_fields(part), ensure_ascii=False) + "\n===INPUT_END===")
    return {"model": model or REVIEW_MODEL, "max_tokens": max_tokens, "thinking": {"type": "adaptive"},
            "messages": [{"role": "user", "content": prompt}]}


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_KO_AMT = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*조(?:\s*(\d[\d,]*)\s*억)?|(\d[\d,]*(?:\.\d+)?)\s*억(?:\s*(\d[\d,]*)\s*만)?"
                     r"|(\d[\d,]*(?:\.\d+)?)\s*만")


def _nums(text):
    """글 속 수치 — 쉼표를 뗀 꼴로."""
    return {m.group(0).replace(",", "") for m in _NUM.finditer(text or "")}


def _amount_forms(text):
    """한국어 금액('4조 1,246억원' · '3,865억원' · '1억 3,341만달러')을 영어 꼴(4.1246 · 386.5 · 133.41)로도 적어 둔다 —
    영어 문장을 고칠 때 같은 금액을 trillion · billion · million 으로 옮겨 쓰는 것은 새 수치가 아니다."""
    out = set()
    for m in _KO_AMT.finditer(text or ""):
        f = lambda x: float(x.replace(",", "")) if x else 0.0      # noqa: E731
        if m.group(1):
            v = f(m.group(1)) * 1e12 + f(m.group(2)) * 1e8
        elif m.group(3):
            v = f(m.group(3)) * 1e8 + f(m.group(4)) * 1e4
        else:
            v = f(m.group(5)) * 1e4
        for div in (1e12, 1e9, 1e6, 1e3):
            x = v / div
            if 0.01 <= x < 1e6:
                for nd in (4, 3, 2, 1, 0):
                    out.add(f"{x:.{nd}f}".rstrip("0").rstrip(".") if nd else str(round(x)))
    return out


def apply_review(rep, text, *, extra="", as_of=""):
    """검토 답(text)의 고침을 rep 의 사본에 적용한다. (고친 rep, 적용한 수, 버린 고침의 사유 목록).
    답을 읽을 수 없으면 (None, 0, [사유])."""
    try:
        got = _parse_json(text or "")
    except Exception as e:                                   # noqa: BLE001
        return None, 0, [f"답을 읽지 못함: {type(e).__name__}"]
    patches = (got or {}).get("patches") if isinstance(got, dict) else None
    if not isinstance(patches, list):
        return None, 0, ["답에 patches 가 없다"]
    new = json.loads(json.dumps(rep, ensure_ascii=False))
    fields = _flat_fields(new)
    every = " ".join(f"{v.get('ko', '')} {v.get('en', '')}" for v in fields.values()) + " " + (extra or "")
    allowed = _nums(every) | _amount_forms(every)
    y = re.match(r"(\d{4})", as_of or "")
    if y:
        allowed |= {str(int(y.group(1)) + d) for d in (-2, -1, 0, 1, 2)}
    applied, dropped = 0, []
    for p in patches[:REVIEW_MAX_PATCHES]:
        if not isinstance(p, dict):
            continue
        path, lang = str(p.get("path") or ""), p.get("lang")
        old, rep_new = p.get("old"), p.get("new")
        f = fields.get(path)
        if f is None or lang not in ("ko", "en") or not isinstance(old, str) or not isinstance(rep_new, str) or not old:
            dropped.append(f"{path}.{lang}: 칸을 찾지 못함")
            continue
        cur = f.get(lang) or ""
        if cur.count(old) != 1:
            dropped.append(f"{path}.{lang}: 옛 글이 {cur.count(old)}번 — {old[:30]!r}")
            continue
        if len(rep_new) > len(old) * 2 + 160:
            dropped.append(f"{path}.{lang}: 새 글이 너무 길다")
            continue
        fresh = {n for n in _nums(rep_new) if not (n.isdigit() and int(n) <= 31)} - allowed
        if fresh:
            dropped.append(f"{path}.{lang}: 본문 · 재료에 없는 수치 {sorted(fresh)[:3]}")
            continue
        val = cur.replace(old, rep_new)
        val = re.sub(r"[ \t]{2,}", " ", val).replace(" .", ".").strip()
        if not val:
            dropped.append(f"{path}.{lang}: 칸이 비게 된다")
            continue
        f[lang] = val
        applied += 1
    return new, applied, dropped


def review(cl, rep, hits=(), *, kind="report", as_of="", material="", names="", hints=(), keys=None, model=None):
    """검토 한 번(cl.messages.create — 회수 단계에서는 배치 대기열이 받는다). (고친 rep, 남은 위반, 기록 한 줄) 또는 None.
    keys 를 주면 그 칸만 보낸다(기본은 글 칸 전부 — 숫자 · 출처 · 메타는 보내지 않는다)."""
    keys = keys or [k for k in rep if k not in _NOT_TEXT]
    part = {k: rep[k] for k in keys if k in rep}
    if not part:
        return None
    params = review_params(part, kind=kind, as_of=as_of, material=material, names=names, hits=hits, hints=hints,
                           model=model)
    resp = cl.messages.create(**params)
    text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
    new_part, applied, dropped = apply_review(part, text, extra=f"{material}\n{names}", as_of=as_of)
    if new_part is None:
        return None
    merged = dict(rep)
    merged.update(new_part)
    before = [h for h in check(rep) if h["rule"] in ("markup", "broken_char")]
    after = check(merged)
    if len([h for h in after if h["rule"] in ("markup", "broken_char")]) > len(before):
        return None                                          # 고친 글에 글자 결함이 늘었다 — 검토를 버린다
    note = f"검토 고침 {applied}곳" + (f" · 버림 {len(dropped)}곳({'; '.join(dropped[:3])})" if dropped else "")
    return merged, after, note


_WHY_EXTRA = {
    "target_price": "목표주가 인용 조건 미충족", "hangul_en": "영문에 한글이 남았다",
    "markup": "태그 · 인용 표시 · 마크다운", "broken_char": "깨지거나 엉뚱한 글자", "hanja": "한국어 문장 속 한자",
    "meta": "받은 자료를 가리키는 말", "stale_time": "상대 시점(지난달 · 이번 주 · 오늘)", "en_word": "한국어 문장 속 영어 낱말",
    "streak": "연속 연수가 실적 표와 다름(정점 다음 해부터 센다)",
    "amount": "본문 금액이 공시 값과 다름",
}


_EN_ACR = {"LG", "SK", "KB", "KT", "HD", "CJ", "GS", "LS", "DB", "NH", "SC", "POSCO", "NAVER", "HMM", "OCI", "DL", "BGF", "JYP",
           "YG", "SM", "HLB", "KCC", "DGB", "BNK", "JB", "NHN", "SDI", "BM", "IPS", "NC", "LX", "KG", "DN"}


def clean_en(s):
    """영문명을 화면과 같은 꼴로 — 'SAMSUNG ELECTRONICS CO,.LTD' → 'Samsung Electronics'(staging/i18n.js 의 cleanEn 과 같다).
    시세 자료의 영문명은 공시 그대로라 대문자 · 'Co., Ltd.' 꼬리가 붙어 있다 — 그대로 주면 영어 문장에 그 꼴이 옮겨진다."""
    s = (s or "").strip()
    while s:
        prev = s
        s = re.sub(r"[\s,.]*\b(CO|LTD|INC|CORP|CORPORATION|LIMITED|PLC|LLC)\b\.?\s*,?\s*\.?$", "", s, flags=re.I).strip()
        if s == prev:
            break
    s = re.sub(r"[,.\s]+$", "", s).strip()
    letters, upper = re.sub(r"[^A-Za-z]", "", s), re.sub(r"[^A-Z]", "", s)
    if letters and len(upper) / len(letters) > 0.8:
        words = []
        for w in s.split():
            wu = re.sub(r"[.,]", "", w.upper())
            words.append(wu if wu in _EN_ACR else w if ("&" in w and w == w.upper()) else w[:1].upper() + w[1:].lower())
        s = " ".join(words)
    return s


def prepare(rep):
    """저장 전 결정적 정리 — 태그 · 마크다운(clean_markup), 한자(fix_hanja), 금액 띄어쓰기 · 천 단위 쉼표(number_spacing).
    돈이 들지 않고 몇 번 돌려도 결과가 같다. 출처 · 숫자 · 메타 칸은 건드리지 않는다. 고친 사본을 돌려준다.
    리포트 생성기 셋(v2 · 신규 상장 배치 · 옛 생성기)과 업종 분석 생성기가 같이 쓴다(2026-10-09)."""
    import fix_hanja                 # noqa: E402 — 둘 다 표준 라이브러리만 쓴다(돌림 의존 없음)
    import number_spacing            # noqa: E402

    def rec(o, k=None):
        if k in _NOT_TEXT:
            return o
        if isinstance(o, str):
            return clean_markup(o)
        if isinstance(o, list):
            return [rec(x) for x in o]
        if isinstance(o, dict):
            return {kk: rec(v, kk) for kk, v in o.items()}
        return o

    out = {k: rec(v, k) for k, v in rep.items()} if isinstance(rep, dict) else rep
    text = {k: v for k, v in out.items() if k not in _NOT_TEXT}
    try:
        text, _ = fix_hanja.walk(text)
    except Exception:                                        # noqa: BLE001 — 정리 실패는 검사가 잡는다
        pass
    _n, text = number_spacing.normalize_report(text, commas=True)
    out.update(text)
    return out


_PCT_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*%")


def en_gap_hints(rep, limit=25):
    """검토에 넘길 '확인할 곳' — 같은 칸의 한국어에 있는 비율(%)이 영어에 없는 자리(영어가 다른 수치를 쓰거나 빠뜨렸을 수 있다)."""
    out = []
    for path, v in _flat_fields({k: x for k, x in (rep or {}).items() if k not in _NOT_TEXT}).items():
        ko = {x.replace(",", "") for x in _PCT_RE.findall(v.get("ko") or "")}
        en = {x.replace(",", "") for x in _PCT_RE.findall(v.get("en") or "")}
        miss = sorted(ko - en)
        if miss and (v.get("en") or "").strip():
            out.append(f"[{path}] 한국어의 비율 {miss[:6]} 이 영어에 없다")
    return out[:limit]


def send_batch(cl, jobs, *, wait_sec=4800, log=print, sleep=None):
    """요청 묶음 {이름: params} 를 배치 하나로 보내고 끝날 때까지 기다린다 — {이름: 답(message) 또는 None(실패)}.
    시간을 넘기면 TimeoutError. 회수 단계 안에서 검토를 끝내야 하는 생성기(업종 분석 · 신규 상장 리포트)가 쓴다."""
    import time
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    sleep = sleep or time.sleep
    reqs = [Request(custom_id=k, params=MessageCreateParamsNonStreaming(**p)) for k, p in jobs.items()]
    b = cl.messages.batches.create(requests=reqs)
    log(f"- 🔎 검토 배치 제출: {b.id} ({len(reqs)}건)")
    waited = 0
    while True:
        st = cl.messages.batches.retrieve(b.id)
        if st.processing_status == "ended":
            break
        if waited >= wait_sec:
            raise TimeoutError(f"검토 배치가 {wait_sec // 60}분 안에 끝나지 않았다({b.id})")
        sleep(60)
        waited += 60
    out = {k: None for k in jobs}
    for r in cl.messages.batches.results(b.id):
        if r.custom_id in out and r.result.type == "succeeded":
            out[r.custom_id] = r.result.message
    return out


def message_text(msg):
    return "".join(getattr(b, "text", "") for b in (getattr(msg, "content", None) or []) if getattr(b, "type", "") == "text")


def summary_line(ticker, hits):
    if not hits:
        return None
    by = {}
    for h in hits:
        by[h["rule"]] = by.get(h["rule"], 0) + 1
    worst = "위험" if any(h["level"] == "위험" for h in hits) else "품질"
    return f"  [{worst}] {ticker} — " + ", ".join(f"{k}×{v}" for k, v in by.items())


def main():
    only = set(sys.argv[1:])
    files = sorted(OUT_DIR.glob("*.json"))
    n = bad = 0
    per_rule = {}
    for f in files:
        if f.stem == "index" or (only and f.stem not in only):
            continue
        try:
            rep = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rep, dict):
            continue
        n += 1
        hits = check(rep)
        if not hits:
            continue
        bad += 1
        for h in hits:
            per_rule[h["rule"]] = per_rule.get(h["rule"], 0) + 1
        print(summary_line(f.stem, hits))
        if only:                       # 특정 종목을 지정했을 땐 문장까지 보여 준다
            for h in hits:
                print(f"      · {h['section']}: {h['match']} — {h['why']}")
                print(f"        {h['sentence']}")
    print(f"\n검사 {n:,}개 · 위반 {bad:,}개 ({bad/n*100:.1f}%)" if n else "대상 없음")
    for k, v in sorted(per_rule.items(), key=lambda kv: -kv[1]):
        why = next((r[3] for r in RULES if r[0] == k), _WHY_EXTRA.get(k, k))
        print(f"  {v:5d}  {k:12} {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
