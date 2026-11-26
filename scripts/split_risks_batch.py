#!/usr/bin/env python3
"""리스크 요인이 약세 요인과 같은 사안을 다시 쓴 리포트를 고친다(2026-11-26 사장 "약세 요인 3가지 내용이랑 리스크 요인 3가지 내용이
… 글자가 완전히 똑같다는 게 아니라 내용이 같은 내용이야. 다른 리포트도 다 이렇게 되어 있어?").

무작위 30편을 읽으니 28편에서 리스크 요인 한 항목 이상이 약세 요인의 사안을 같은 수치와 함께 다시 썼다(13편은 두 항목 이상).
지시문이 두 절을 '각 3개'로만 적고 차이를 정하지 않아서다 — 지시문(리포트 v2 5-3 · 옛 형식 4-1)과 작성 판(textRules 4)을 고쳤고,
그 전에 쓴 리포트는 이 도구가 고친다. 글 전체를 다시 쓰지 않는다 — 하이쿠 5.5(배치 · 리포트 작성과 같은 모델)가 리포트 전체를 읽고
리스크 항목마다 약세 요인과 같은 사안인지 판단해, 같은 사안인 항목만 리포트의 다른 절에 적힌 사실로 다른 위험을 쓴다. 같은 사안이
아닌 항목은 손대지 않는다.

  python3 scripts/split_risks_batch.py plan  [--limit N] [--only 종목,…]              # 대상만 센다(돈 안 듦 · 어디서나)
  python3 scripts/split_risks_batch.py order [--limit N] [--only 종목,…]              # 배치를 주문하고 끝날 때까지 기다린다(러너 · 키)
  python3 scripts/split_risks_batch.py apply [--show] [--dry]                        # 받은 답을 지금 저장소의 글에 끼운다

대상: 화면에 나오는 리포트(새 형식 전부 · 새 형식이 없는 종목의 옛 형식) 가운데 고친 지시문으로 쓰지 않았고(textRules < 4) 이 도구가
아직 보지 않은(riskSplit 없음) 글. 저장 문턱(하나라도 어기면 그 글은 그대로 두고 다음 실행이 다시 묻는다):
  · 답의 모양 — 리스크 항목마다 판단이 있고, 바꾼 항목 = 같은 사안으로 판단한 항목, 바꾼 항목은 분류(cat) · 본문(body)의 한국어 ·
    영어가 모두 차 있다(분류 2~20자 · 본문 100~300자)
  · 숫자 — 바꾼 항목의 수치는 리포트의 다른 절(약세 요인과 바꾸기 전 항목 제외)에 이미 있는 것만(연도 · 연도에 붙은 분기 · 월 번호는
    된다), 약세 요인에 쓴 수치는 쓰지 않는다 — 새 사실을 만들거나 같은 사안을 다른 말로 되풀이하지 못하게
  · 검사 — 바꾼 항목은 지금 판의 규칙(check · 독자 호칭)을 모두 지나고, 다른 칸의 문장을 글자 그대로 옮기지 않았다
  · 리스크 분류가 서로 겹치지 않는다
같은 사안이 없다고 판단한 글도 riskSplit 을 달아 다시 묻지 않는다. 배치를 기다리는 동안 그 글이 다시 쓰였으면(약세 · 리스크 지문이
다르면) 건너뛴다. 파일은 원래 꼴(들여쓰기)대로 쓴다. 돈은 하이쿠 배치 단가로 편당 약 0.002달러(전 종목 약 5달러).
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_report_text as C  # noqa: E402
import repair_rules_batch as R  # noqa: E402 — 리포트 목록 · 파일 꼴 · 지문 · 숫자 세기를 같이 쓴다

MODEL = os.getenv("SPLIT_RISKS_MODEL", "claude-haiku-5-5")
STATE = Path(os.getenv("SPLIT_RISKS_STATE", "/tmp/split_risks_state.json"))
WAIT_SEC = int(os.getenv("SPLIT_RISKS_WAIT_SEC", str(4 * 3600)))
CHUNK = int(os.getenv("SPLIT_RISKS_CHUNK", "800"))   # 배치 하나에 담는 글 수 — 요청 하나가 수십 KB 라 배치 한도(256MB)에 넉넉히 들게
PRICE = {"in": 0.05, "out": 0.25, "cache_w": 0.0625, "cache_r": 0.005}   # 하이쿠 5.5 배치 · 100만 토큰당 달러(기록용 · 콘솔이 기준)
SPLIT_RULES = 4        # 이 판(textRules) 부터는 지시문이 두 절을 가른다 — 고칠 대상이 아니다
MARK = "riskSplit"     # 이 도구가 본 글의 표시(값 1) — check_report_text._NOT_TEXT

PROMPT = """아래는 한 회사의 기업 분석 리포트(JSON)입니다. 약세 요인(bear)과 리스크 요인(risks)은 화면에 나란히 놓이는데, 리스크 항목
가운데 약세 요인과 같은 사안을 다시 쓴 것이 있으면 리포트의 정보가 줄어듭니다. 그런 리스크 항목만 다른 위험으로 바꿉니다.

두 절의 뜻
· bear(약세 요인) — 지금 이미 드러난 약점이다. 공시 실적 · 재무 · 사업 현황에서 확인되는 사실과 그 원인.
· risks(리스크 요인) — 아직 일어나지 않았거나 결과가 정해지지 않은 일 가운데, 일어나면 이 회사의 실적 · 사업에 영향을 줄 사건 ·
  조건이다. 규제 · 인허가, 소송 · 분쟁, 환율 · 금리 · 원자재 가격, 고객 · 공급망, 임상 · 기술 개발, 증설 · 신사업 실행, 지배구조 ·
  자금 조달, 정책 · 지정학 등.

할 일
1. 리스크 항목(1~{n})을 하나씩 읽고, 약세 요인 가운데 같은 사안을 다룬 항목이 있는지 판단한다. 같은 사안이란 같은 원인 · 사건 ·
   수치를 다루는 것이다 — 같은 일을 '지금의 약점'과 '앞으로의 위험'으로 나눠 쓴 것도 같은 사안이다. 같은 회사라서 낱말이 겹치는
   것만으로는 같은 사안이 아니다.
2. 같은 사안인 리스크 항목만 새로 쓴다. 새 항목은
   · 약세 요인의 어느 항목과도, 다른 리스크 항목과도 다른 사안이다.
   · 이 리포트의 다른 절(business · earnings · industry · outlook · valuation_comment · checkpoints · verdict · lead · keypoints)에
     적힌 계획 · 사건 · 조건에 근거한 앞으로의 위험이다. 리포트에 없는 사실이나 근거 없는 가정(유상증자 · 지분 희석 등)을 만들지
     않는다.
   · 주가 · 수급 · 주가 변동성 · 밸류에이션 배수는 리스크로 쓰지 않는다 — 회사의 실적 · 사업에 닿는 사안만 쓴다.
   · 작성일({date})보다 앞선 날짜의 일정(예정 · 계획 · 목표)은 이미 지난 일이므로 앞으로의 위험으로 쓰지 않는다.
   · 수치는 리포트의 다른 절에 이미 있는 것만 그 뜻 그대로 쓴다. 약세 요인에 쓴 수치는 쓰지 않는다. 수치가 없어도 된다.
   · cat 은 위험의 분류를 짧게(한국어 4~12자), body 는 한국어 150~200자 · 3~4문장이다.
   · 이 회사에 닿는 구체적 사안을 쓴다. 업계 일반론('경기 둔화' · '경쟁 심화')만으로 채우지 않는다.
   · 문장은 '…이다 · …했다 · …수 있다'로 끝나는 보고서 문체로 쓴다. 투자 권유 · 가치 단정 · 독자나 투자자를 부르는 말 · 글을 쓴
     과정('이번 조사에서' · '이 리포트에서는') · 과장을 쓰지 않는다. 연도는 숫자로 쓴다('올해' · '지난해' 금지).
   · 새 항목은 리포트 본문의 한 절로 읽혀야 한다. 이 글이나 그 절을 가리키지 않고('리포트에는 … 제시되지 않아' · '산업 분석은
     … 설명했다' 금지), 리포트에 무엇이 없다고 쓰지 않는다.
   · en 은 같은 뜻의 영어다. 한글을 한 글자도 쓰지 않는다. 회사 · 제품 · 기관 이름은 리포트 영어 본문의 표기를 따른다.
3. 같은 사안이 아닌 리스크 항목은 바꾸지 않는다(출력에 넣지 않는다).

출력 — 마커 사이에 JSON 하나만 쓴다. 다른 말은 쓰지 않는다. 아래는 모양을 보이는 예다.
===JSON_START===
{{"judge": [{{"risk": 1, "same_as": 2, "why": "판단 근거"}}, {{"risk": 2, "same_as": 0, "why": "판단 근거"}}, {{"risk": 3, "same_as": 0, "why": "판단 근거"}}],
 "replace": [{{"risk": 1, "cat": {{"ko": "분류", "en": "Category"}}, "body": {{"ko": "본문", "en": "Body"}}}}]}}
===JSON_END===
· judge 는 리스크 항목마다 하나씩(1~{n}). same_as 는 같은 사안인 약세 요인 번호(1~{b}) 또는 0(같은 사안 없음). why 는 판단 근거를
  한국어 40자 안으로 쓴다.
· replace 에는 same_as 가 0 이 아닌 항목만 넣는다. 같은 사안이 없으면 "replace": [] 로 쓴다.

===REPORT===
{report}
===REPORT_END==="""


def log(*a):
    print(*a, flush=True)


def _items_ok(lst, head):
    return isinstance(lst, list) and lst and all(
        isinstance(it, dict) and all(isinstance(it.get(k), dict) for k in (head, "body")) for it in lst)


def eligible(rep):
    """이 도구가 볼 글인가 — 약세 · 리스크가 제 모양이고, 고친 지시문 전에 썼고, 아직 보지 않았다."""
    return (isinstance(rep, dict) and _items_ok(rep.get("bear"), "title") and _items_ok(rep.get("risks"), "cat")
            and (rep.get("textRules") or 0) < SPLIT_RULES and not rep.get(MARK))


def targets(limit=0, only=None, root=None):
    out = []
    for f in R.report_files(root):
        if only and f.stem not in only:
            continue
        try:
            rep, _ = R.load(f)
        except Exception:                                    # noqa: BLE001
            continue
        if eligible(rep):
            out.append((f, rep))
            if limit and len(out) >= limit:
                break
    return out


def params_of(rep):
    part = {k: v for k, v in rep.items() if k not in C._NOT_TEXT and k != MARK}
    text = PROMPT.format(n=len(rep["risks"]), b=len(rep["bear"]), date=str(rep.get("reportDate") or "")[:10] or "작성일",
                         report=json.dumps(part, ensure_ascii=False, indent=1))
    return {"model": MODEL, "max_tokens": 16000, "thinking": {"type": "adaptive"},
            "messages": [{"role": "user", "content": text}]}


# ── 저장 문턱 ───────────────────────────────────────────────────────────────────────────────────────
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_ATTACHED = re.compile(r"(\d{1,2})\s*(?:분기|월)|\b[QH]([1-4])\b|\b([1-4])[QH]\b")


def _nums(text):
    """글의 수치 — 연도(2019~2031)와 분기 · 월 번호('3분기' · '12월' · 'Q3')는 뺀다."""
    t = text or ""
    skip = {g for m in _ATTACHED.finditer(t) for g in m.groups() if g}
    out = set()
    for m in _NUM.findall(t):
        n = m.replace(",", "").rstrip(".")
        if n.isdigit() and 2019 <= int(n) <= 2031:
            continue
        if n in skip:
            continue
        out.add(n)
    return out


def _side_nums(obj, side, fn=None):
    fn = fn or _nums
    return set().union(*[fn(f.get(side) or "") for f in C._flat_fields(obj).values()] or [set()])


# 약세 요인과 견줄 수치 — 금액 · 비율 · 배수 같은 '같은 사안'을 알리는 수치만. 한 자리 개수('2개 공장' · '3곳' · '1위')와
# 날짜 · 기간('11월 30일' · '3년' · '6개월')은 견주지 않는다 — 첫 전체 실행(2026-11-27)에서 '약세 요인의 수치' 307편 가운데
# 약 220편이 한 자리 수만 겹쳐 걸렸다(약세 '2년 연속 적자' ↔ 새 리스크 '2개 공장'). 두 번째 실행 뒤에는 단위까지 견준다 —
# '200%' ↔ '200억원', '1조 2,345억원' ↔ '1조 5,000억원'('1조'만 겹침)은 같은 수치가 아니다.
_UNIT = (("%", re.compile(r"\s*(?:%p?|％|퍼센트|percent(?:age points?)?|bp\b|pp\b)", re.I)),
         ("배", re.compile(r"\s*(?:배|x\b|times\b)", re.I)),
         ("", re.compile(r"\s*(조|천\s*억|억|만\s*원|천\s*원|원|달러|trillion|billion|million)", re.I)))
_JO = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*조\s*(\d[\d,]*)\s*(천\s*)?억")
_TIME = re.compile(r"\s*(?:분기|월|일|년|개월|주|시간|days?\b|months?\b|years?\b|weeks?\b)", re.I)
_MON_EN = re.compile(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+$")


def _unit(after):
    for name, rx in _UNIT:
        m = rx.match(after)
        if m:
            return name or re.sub(r"\s+", "", m.group(1)).lower()
    return ""


def _figures(text):
    """견줄 수치 — 수와 단위를 함께 본다('200%' ≠ '200억원' · '1조 2,345억원' ≠ '1조 5,000억원'). 자리마다 본다
    (같은 수가 '3분기'와 '3%'로 함께 나와도 '3%'는 센다)."""
    t = text or ""
    out, taken = set(), []
    for m in _JO.finditer(t):
        out.add(f"{m.group(1).replace(',', '')}조{m.group(2).replace(',', '')}{'천' if m.group(3) else ''}억")
        taken.append(m.span())
    for m in _NUM.finditer(t):
        if any(a <= m.start() < b for a, b in taken):
            continue
        n = m.group().replace(",", "").rstrip(".")
        if n.isdigit() and 2019 <= int(n) <= 2031:
            continue
        before, after = t[max(0, m.start() - 12):m.start()], t[m.end():]
        # 날짜 · 기간, 영문자에 붙은 수('Q3' · '3Q25' · 'BAL0891' · 'MP010' · 'SAL200' · '5G' — 분기 · 제품 이름)는 견주지 않는다
        if (_TIME.match(after) or _MON_EN.search(before) or re.search(r"[A-Za-z]$", before)
                or (re.match(r"[A-Za-z]", after) and not re.match(r"(?:bp|pp|x)\b", after))):
            continue
        unit = _unit(after)
        if n.isdigit() and int(n) < 10 and not unit:
            continue
        out.add(n + unit)
    return out


def _sentences_ko(obj):
    out = set()
    for f in C._flat_fields(obj).values():
        for s in re.split(r"(?<=[.다])\s+", f.get("ko") or ""):
            k = re.sub(r"\s+", " ", s).strip()
            if len(k) >= 25:
                out.add(k)
    return out


# 리포트 자체나 그 절을 가리키는 말 — 2026-11-26 시험 27항목 중 3항목('리포트에는 발급 규모와 거래 단가가 제시되지 않아' ·
# '거래처별 매출 비중은 리포트에 제시되지 않아' · '산업 분석은 … 설명했으나'). 증권사 리포트를 가리키는 말('KB증권은 5월 리포트에서')은 뺀다.
_SELF_KO = re.compile(r"리포트(?:에는|에|에서는|에서도|에서)\s*[^.]{0,40}?(?:제시|나와|나오|담기|담겨|포함|언급|드러나|확인|나타나)"
                      r"(?:되|하|돼)?(?:지|진)?\s*않"
                      r"|(?<![가-힣])(?:산업|실적|사업|전망|밸류에이션)\s*분석(?:은|에서는|에서|이|에 따르면)\s"
                      r"|(?<![가-힣])(?:본문|이 절|앞 절|위 절)(?:에|에서|에는|은|의)?\s")
_SELF_EN = re.compile(r"\b(?:the|this) report (?:does not|doesn't|did not|gives no|provides no|shows no|lacks)\b"
                      r"|\bnot (?:given|shown|provided|disclosed|stated) in (?:the|this) report\b"
                      r"|\bthe (?:industry|earnings|business|valuation|outlook) (?:analysis|section) (?:explains|says|notes|states|shows|describes)\b"
                      r"|\b(?:this|the above|the previous) section\b", re.I)
_BROKER = re.compile(r"(?:증권|투자|리서치|애널리스트|자산운용|은행)[^.]{0,12}$")


def self_ref(item):
    """새 항목이 리포트 자체나 그 절을 가리키는가 — 걸린 말 또는 ''."""
    ko = " ".join(((item.get(k) or {}).get("ko") or "") for k in ("cat", "body"))
    en = " ".join(((item.get(k) or {}).get("en") or "") for k in ("cat", "body"))
    for m in _SELF_KO.finditer(ko):
        if m.group(0).startswith("리포트") and _BROKER.search(ko[:m.start()]):
            continue                                   # 'KB증권은 5월 리포트에서 …' — 증권사 리포트
        return m.group(0)[:30]
    m = _SELF_EN.search(en)
    return m.group(0)[:30] if m else ""


_YM = re.compile(r"(20\d\d)년\s*(\d{1,2})월")
_PLAN = re.compile(r"예정(?:이다|되어|돼|이며|이고|이라|인|대로)|계획(?:이다|이며|이고)|목표(?:다|이다|로 하)|앞두고")


def stale_plan(item, report_date):
    """작성일보다 앞선 달의 일정을 앞으로의 일('…예정되어')로 쓴 문장 — 걸린 문장 또는 ''."""
    m = re.match(r"(\d{4})-(\d{2})", str(report_date or ""))
    if not m:
        return ""
    now = (int(m.group(1)), int(m.group(2)))
    for s in re.split(r"(?<=[.다])\s+", (item.get("body") or {}).get("ko") or ""):
        if _PLAN.search(s) and any((int(y), int(mo)) < now for y, mo in _YM.findall(s)):
            return s[:40]
    return ""


def parse(msg):
    text = "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")
    try:
        return C._parse_json(text)
    except Exception:                                        # noqa: BLE001
        return None


def judge(rep_now, ans):
    """답을 지금 글에 끼워 본다 — (고친 글 또는 None, 사유, 바꾼 항목 번호들)."""
    if not eligible(rep_now):
        return None, "대상 아님(이미 봤거나 새 지시문)", []
    if not isinstance(ans, dict) or not isinstance(ans.get("judge"), list) or not isinstance(ans.get("replace"), list):
        return None, "답의 모양이 다름", []
    risks, bear = rep_now["risks"], rep_now["bear"]
    n = len(risks)
    same = {}
    for j in ans["judge"]:
        if not isinstance(j, dict):
            return None, "답의 모양이 다름", []
        try:
            i, s = int(j.get("risk")), int(j.get("same_as") or 0)
        except (TypeError, ValueError):
            return None, "답의 모양이 다름", []
        if not 1 <= i <= n or not 0 <= s <= len(bear) or i in same:
            return None, "판단 번호가 맞지 않음", []
        same[i] = s
    if set(same) != set(range(1, n + 1)):
        return None, "판단이 빠진 항목이 있음", []
    want = {i for i, s in same.items() if s}
    rep = {}
    for r in ans["replace"]:
        try:
            i = int(r.get("risk"))
        except (TypeError, ValueError, AttributeError):
            return None, "답의 모양이 다름", []
        if i in rep:
            return None, "같은 항목을 두 번 바꿈", []
        rep[i] = r
    if set(rep) != want:
        return None, "바꾼 항목이 판단과 다름", []
    if not want:
        out = dict(rep_now)
        out[MARK] = 1
        return out, "같은 사안 없음", []
    new = [dict(x) for x in risks]
    for i, r in rep.items():
        item = {}
        for k, lo, hi in (("cat", 2, 20), ("body", 100, 300)):
            v = r.get(k)
            if not isinstance(v, dict) or not all(isinstance(v.get(s), str) and v.get(s).strip() for s in ("ko", "en")):
                return None, "새 항목의 칸이 비었음", []
            ko = v["ko"].strip()
            if not lo <= len(ko) <= hi:
                return None, f"새 항목 {k} 길이 {len(ko)}자", []
            if len(v["en"].strip()) < (3 if k == "cat" else 60):
                return None, "새 항목의 영어가 짧음", []
            item[k] = {"ko": ko, "en": v["en"].strip()}
        new[i - 1] = dict(risks[i - 1], **item)
    new = C.prepare({"risks": new})["risks"]
    changed = [new[i - 1] for i in sorted(want)]
    cats = [re.sub(r"\s+", "", (x.get("cat") or {}).get("ko") or "") for x in new]
    if len(set(cats)) < len(cats):
        return None, "리스크 분류가 겹침", []
    # 수치 — 다른 절에 있는 것만 · 약세 요인의 수치는 쓰지 않는다
    rest = {k: v for k, v in rep_now.items() if k not in C._NOT_TEXT and k not in (MARK, "bear", "risks")}
    rest["risks"] = [x for i, x in enumerate(risks, 1) if i not in want]
    for side in ("ko", "en"):
        mine = _side_nums(changed, side)
        echo = _side_nums(changed, side, _figures) & _side_nums(bear, side, _figures)
        if echo:
            return None, f"약세 요인의 수치를 다시 씀({side}) " + ", ".join(sorted(echo)[:4]), []
        odd = mine - _side_nums(rest, side)
        if odd:
            return None, f"리포트에 없는 수치({side}) " + ", ".join(sorted(odd)[:4]), []
    # 리포트 자체를 가리키는 말 · 이미 지난 일정을 앞으로의 일로
    for x in changed:
        hit = self_ref(x)
        if hit:
            return None, f"리포트 자체를 가리킴 — {hit}", []
        hit = stale_plan(x, rep_now.get("reportDate"))
        if hit:
            return None, f"지난 일정을 앞으로의 일로 — {hit}", []
    # 다른 칸의 문장을 글자 그대로 옮기지 않았다
    if _sentences_ko(changed) & _sentences_ko({k: v for k, v in rep_now.items() if k not in C._NOT_TEXT and k != "risks"}):
        return None, "다른 칸의 문장을 그대로 옮김", []
    # 지금 판의 규칙 — 바꾼 항목만 담은 글로 잰다(모든 규칙이 걸리게: 지금 판 · 새 규칙 적용 날짜)
    mini = {k: rep_now.get(k) for k in ("ticker", "name", "name_en", "market", "sector", "quant", "ipo") if k in rep_now}
    mini.update({"reportDate": "2099-12-31", "reportTs": "2099-12-31 00:00", "model": MODEL, "textRules": C.TEXT_RULES,
                 "risks": changed})
    hits = C.check(mini) + C.new_rule_hits(mini)
    if hits:
        h = hits[0]
        return None, f"검사 위반 {h['rule']} — {str(h.get('sentence', ''))[:40]}", []
    out = dict(rep_now)
    out["risks"] = new
    out[MARK] = 1
    return out, f"{len(want)}항목 바꿈", sorted(want)


def fingerprint(rep):
    return R.fingerprint(rep, ["bear", "risks"])


# ── 단계 ────────────────────────────────────────────────────────────────────────────────────────────
def cmd_plan(limit, only=None):
    ts = targets(limit, only)
    by = Counter(str(rep.get("reportDate", ""))[:7] for _, rep in ts)
    v1 = sum(1 for f, _ in ts if f.parent.name == "reports")
    log(f"## 리스크 나누기 — 볼 리포트 {len(ts)}편(옛 형식 {v1}) · 작성 달별 {dict(sorted(by.items()))}")
    return ts


def cmd_order(cl, limit, only=None, sleep=time.sleep):
    ts = targets(limit, only)
    if not ts:
        log("## 리스크 나누기 — 볼 리포트 없음")
        STATE.write_text(json.dumps({"batch_ids": [], "items": {}}, ensure_ascii=False), encoding="utf-8")
        return []
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    bids, items = [], {}
    for i in range(0, len(ts), CHUNK):
        reqs = []
        for f, rep in ts[i:i + CHUNK]:
            cid = R.cid_of(f)
            items[cid] = {"file": str(f.relative_to(ROOT)), "fp": fingerprint(rep)}
            reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params_of(rep))))
        b = cl.messages.batches.create(requests=reqs)
        bids.append(b.id)
        log(f"## 리스크 나누기 — 배치 제출 {b.id} · {len(reqs)}편")
        STATE.write_text(json.dumps({"batch_ids": bids, "items": items}, ensure_ascii=False), encoding="utf-8")
    waited = 0
    left = list(bids)
    while left:
        left = [b for b in left if cl.messages.batches.retrieve(b).processing_status != "ended"]
        if not left:
            break
        if waited >= WAIT_SEC:
            raise TimeoutError(f"배치가 {WAIT_SEC // 60}분 안에 끝나지 않았다({', '.join(left)}) — 같은 배치를 apply 로 다시 받는다")
        sleep(60)
        waited += 60
    log(f"- 배치 {len(bids)}개 끝 ({waited // 60}분)")
    return bids


def _show(cid, rep_now, rep2, ans, want):
    log(f"\n### {cid} {rep_now.get('name', '')}")
    for j in ans.get("judge") or []:
        log(f"- 리스크 {j.get('risk')} → 약세 {j.get('same_as')} · {j.get('why', '')}")
    for i in want:
        o, nw = rep_now["risks"][i - 1], rep2["risks"][i - 1]
        log(f"- 리스크 {i} 전: [{o['cat'].get('ko')}] {o['body'].get('ko')}")
        log(f"  리스크 {i} 후: [{nw['cat'].get('ko')}] {nw['body'].get('ko')}")
        log(f"  영어: [{nw['cat'].get('en')}] {nw['body'].get('en')}")


def cmd_apply(cl, state=None, show=False, dry=False):
    st = state or json.loads(STATE.read_text(encoding="utf-8"))
    bids = st.get("batch_ids") or ([st["batch_id"]] if st.get("batch_id") else [])
    items = st.get("items") or {}
    if not bids:
        log("받을 배치 없음")
        return {}
    use = Counter()
    got = {}
    for bid in bids:
        for r in cl.messages.batches.results(bid):
            if r.custom_id in items and r.result.type == "succeeded":
                got[r.custom_id] = r.result.message
                u = getattr(r.result.message, "usage", None)
                if u is not None:
                    use["in"] += getattr(u, "input_tokens", 0) or 0
                    use["out"] += getattr(u, "output_tokens", 0) or 0
                    use["cache_w"] += getattr(u, "cache_creation_input_tokens", 0) or 0
                    use["cache_r"] += getattr(u, "cache_read_input_tokens", 0) or 0
    saved, changed, items_changed, skip = [], 0, 0, Counter()
    judged = Counter()
    for cid, it in sorted(items.items()):
        f = ROOT / it["file"]
        msg = got.get(cid)
        if msg is None:
            skip["답 없음(배치 실패)"] += 1
            continue
        if not f.exists():
            skip["파일 없음"] += 1
            continue
        rep_now, text = R.load(f)
        if fingerprint(rep_now) != it["fp"]:
            skip["그 사이 다시 쓰임"] += 1
            continue
        ans = parse(msg)
        rep2, why, want = judge(rep_now, ans)
        if isinstance(ans, dict):
            for j in ans.get("judge") or []:
                if isinstance(j, dict):
                    judged["같은 사안" if j.get("same_as") else "다른 사안"] += 1
        if rep2 is None:
            key = re.sub(r"[\s(].*$", "", why) if why.startswith(("리포트에", "약세", "검사", "새 항목", "리포트 자체", "지난 일정")) else why
            skip[key] += 1
            log(f"  · 건너뜀 {cid} — {why}")
            continue
        if show:
            _show(cid, rep_now, rep2, ans, want)
        if not dry:
            f.write_text(R.dump_like(rep2, text), encoding="utf-8")
        saved.append(f.stem)
        if want:
            changed += 1
            items_changed += len(want)
    usd = sum(use[k] * PRICE[k] for k in PRICE) / 1e6
    log(f"\n## 리스크 나누기 — {'저장하지 않음(시험) · ' if dry else ''}통과 {len(saved)}편(리스크를 바꾼 글 {changed}편 · "
        f"{items_changed}항목) · 건너뜀 {sum(skip.values())}편 {dict(skip)}")
    log(f"- 판단 — 리스크 항목 {sum(judged.values())}개 중 약세 요인과 같은 사안 {judged['같은 사안']}개")
    log(f"- 사용량 입력 {use['in']:,} · 캐시 쓰기 {use['cache_w']:,} · 캐시 읽기 {use['cache_r']:,} · 출력 {use['out']:,}"
        f" · 배치 단가 약 {usd:.2f}달러(콘솔이 기준)")
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fo:
            fo.write(f"saved={0 if dry else changed}\n")
    return {"saved": saved, "changed": changed, "items": items_changed, "skip": dict(skip), "usd": round(usd, 4)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "order", "apply"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    only = {x.strip() for x in a.only.replace(" ", ",").split(",") if x.strip()} or None
    if a.mode == "plan":
        cmd_plan(a.limit, only)
        return 0
    import anthropic
    cl = anthropic.Anthropic()
    if a.mode == "order":
        cmd_order(cl, a.limit, only)
    else:
        cmd_apply(cl, show=a.show, dry=a.dry)
    return 0


if __name__ == "__main__":
    sys.exit(main())
