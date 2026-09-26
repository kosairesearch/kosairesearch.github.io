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
('<sup index=…>')·모델이 받은 자료를 가리키는 말('제공된 데이터셋'). 표현이 아니라
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
    ("solicit", "위험", re.compile(
        r"매수\s*(추천|권[유고])|매도\s*(추천|권[유고])|지금이\s*기회"
        r"|(?<![가-힣])담을\s*만하|사\s*모을\s*만하"),
     "투자 권유로 읽히는 표현"),
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


def en_texts(rep):
    """(섹션명, 영문) 목록 — 영문에 한글이 남았는지 볼 때 쓴다."""
    out = []
    for k in PROSE_KEYS + ("title",):
        out.append((k, _en(rep.get(k))))
    out.append(("verdict", _en((rep.get("verdict") or {}).get("body"))))
    for k in LIST_KEYS:
        for x in (rep.get(k) or []):
            if isinstance(x, dict):
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

    for k in PROSE_KEYS:
        add(k, _ko(rep.get(k)))
    add("verdict", _ko((rep.get("verdict") or {}).get("body")))
    for k in LIST_KEYS:
        for x in (rep.get(k) or []):
            if isinstance(x, dict):
                for f in ("title", "what", "when", "body"):
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
_MARKUP = (
    (re.compile(r"<sup\b[^<>]*>.*?</sup>", re.S | re.I), ""),        # 인용 번호 — 뜻이 없다
    (re.compile(r"<sup\b[^<>]*/?>|</sup>", re.I), ""),
    (re.compile(r"</?(?:citation|cite)\b[^<>]*>", re.I), ""),        # 인용이 감싼 글은 남긴다
    (re.compile(r"<a\s[^<>]*href\s*=[^<>]*>|</a>", re.I), ""),       # 링크가 감싼 글은 남긴다
    (re.compile(r"<br\s*/?>|</br>", re.I), " "),
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"\1"),              # 마크다운 굵게
    (re.compile(r"&(?:amp|#38);"), "&"), (re.compile(r"&(?:quot|#34);"), '"'),
    (re.compile(r"&(?:#39|apos);"), "'"), (re.compile(r"&nbsp;"), " "),
    (re.compile("[\u00ad\u200b\u200c\u200d\u2060\ufeff]"), ""),        # 보이지 않는 글자
)


def clean_markup(s):
    """태그·인용 표시·마크다운·HTML 이름표를 지운다. 감싼 글은 남긴다. 결정적이라 저장 전에 늘 돌린다."""
    if not isinstance(s, str) or not s:
        return s
    t = s
    for pat, rep in _MARKUP:
        t = pat.sub(rep, t)
    if t != s:
        t = re.sub(r"[ \t]{2,}", " ", t)
        t = re.sub(r"[ \t]*\n[ \t]*", "\n", t).strip()
    return t


_NOT_TEXT = {"sources", "quant", "ticker", "name", "name_en", "market", "sector", "categories",
             "reportDate", "reportTs", "dataDate", "v", "hasPaid", "model", "usage", "meta", "asOf"}
_KS_OK = set("웻몐퀜")          # 2,350자 밖이지만 맞는 말 — 웻 스테이션 · 쓰촨성 몐양 · 초전도 코일 퀜치
_TAG = re.compile(r"<\s*/?\s*(?:sup|sub|citation|cite|br|span|div|p|b|i|em|strong|u|small|mark|ref|source|li|ul|ol|table|tr|td|h[1-6])"
                  r"\b[^<>]{0,160}>|<a\s[^<>]*href|\b(?:index|href|src|class)\s*=\s*\"|\*\*|&(?:amp|lt|gt|quot|nbsp|#\d+);", re.I)
_ODD = re.compile("[\ufffd\u0400-\u04ff\u0590-\u08ff\u0900-\u0dff\u0e00-\u0eff]")   # 깨진 글자 · 키릴·히브리·아랍·인도계·타이 문자
_KO_GLITCH = re.compile("경[쁌쳥쟰쁁쨍쟃쁏숁섄쪆쥉쁀쭁쟐쁙쥰쁩쁭쁠쁨쟟쁄쁴쁜쇄]")        # '경쟁' 이 깨진 꼴(2,350자 안에 드는 것까지)
_HAN_IN_EN = re.compile(r"[一-鿿]")
_HAN_IN_KO = re.compile(r"(?<=[가-힣])[一-鿿]+|[一-鿿]+(?=[가-힣])")   # 괄호 병기 '상저하고(上低下高)' 는 안 걸린다
_META_KO = re.compile(r"제공된\s*(?:데이터|자료|재무)|이번\s*데이터셋|(?:자료|데이터)\s*창|데이터\s*구간\s*내|\(null\)")
_META_EN = re.compile(r"data window|disclosed window|provided (?:data|dataset|financial data)|this dataset|dataset provided|\(null\)", re.I)


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
        if m:
            add("markup", "위험", sec, s, m.start(), m.end(), "태그·인용 표시·마크다운이 글자 그대로 찍힌다 — 지우고 글만 남길 것")
        m = _ODD.search(s) or (_KO_GLITCH.search(s) if lang != "en" else None) or (_HAN_IN_EN.search(s) if lang == "en" else None)
        if not m and lang != "en":
            i = next((i for i, ch in enumerate(s) if "가" <= ch <= "힣" and _ks_bad(ch)), -1)
            if i >= 0:
                add("broken_char", "위험", sec, s, i, i + 1, "깨지거나 엉뚱한 글자 — 문맥에 맞는 올바른 단어로 고칠 것")
        elif m:
            add("broken_char", "위험", sec, s, m.start(), m.end(), "깨지거나 엉뚱한 글자 — 문맥에 맞는 올바른 단어로 고칠 것")
        if lang != "en":
            m = _HAN_IN_KO.search(s)
            if m:
                add("hanja", "품질", sec, s, m.start(), m.end(), "한국어 문장에 섞인 한자 — 한글로")
        m = (_META_EN if lang == "en" else _META_KO).search(s)
        if m:
            add("meta", "품질", sec, s, m.start(), m.end(), "모델이 받은 자료를 가리키는 말 — 독자는 그 자료를 모른다")
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
            if m and key in ("valuejudge", "pershare") and cited:
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
    return hits + defects(rep)


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
    "\n  · markup: 태그·링크·인용 표시(<sup …>, <a href>, [1])와 마크다운(**)을 지우고 글만 남길 것."
    "\n  · hanja: 한국어 문장에 한자를 섞지 말 것('88億원' → '88억원', '오너家' → '오너 일가')."
    "\n  · meta: '제공된 데이터(셋)'·'자료 창'·'data window'·'provided data' 처럼 받은 자료를 가리키는 말을 쓰지 말 것"
    " — '공시 기준'·'확인되지 않는다'·'the period shown' 처럼.")


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
        "1. 위반된 문장만 규칙에 맞게 고쳐 쓰세요. 사실(숫자·고유명사·인과)은 바꾸지 말고 표현만 바꾸세요. "
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
        why = next((r[3] for r in RULES if r[0] == k), "목표주가 인용 조건 미충족")
        print(f"  {v:5d}  {k:12} {why}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
