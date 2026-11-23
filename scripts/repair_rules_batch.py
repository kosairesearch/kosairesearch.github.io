#!/usr/bin/env python3
"""화면에 나오는 리포트의 검사 위반을 걸린 문장만 교정 배치로 고친다(2026-11-23 · 자동 점검 3/3).

첫 쓰임 — 연도 상대 표현(stale_year). 11/18 에 지시문 · 검사(textRules 3)에 넣은 규칙이라, 그 전에 쓴 리포트 537편(한국어 685문장 ·
영어 571곳 · 대부분 11월 3분기 공시 리포트)이 '올해 · 지난해 · 작년 · 내년' · 'this year · last year'를 쓴다. 3분기 리포트는 이듬해
3월 사업보고서까지 걸려 있어 해가 바뀌면 '올해'가 모두 틀린다. 글 전체를 다시 쓰지 않고 걸린 문장만 check_report_text.repair
(소넷 5.5 · 배치 · 리포트 생성기의 교정과 같은 지시)로 연도 숫자로 바꾼다.

  python3 scripts/repair_rules_batch.py plan  [--rule stale_year] [--limit N]    # 대상만 센다(돈 안 듦 · 어디서나)
  python3 scripts/repair_rules_batch.py order [--rule stale_year] [--limit N]    # 배치를 주문하고 끝날 때까지 기다린다(러너 · 키)
  python3 scripts/repair_rules_batch.py apply                                     # 받은 답을 최신 저장소의 글에 끼운다

order 와 apply 사이에 작업 파일이 저장소를 main 의 최신으로 맞춘다(repair_rules.yml) — 배치를 기다리는 동안 다른 작업이 같은 리포트를
다시 썼으면 그 글은 건드리지 않는다(보낸 칸의 지문이 지금 글과 다르면 건너뜀). 저장 문턱:
  · 그 규칙의 위반이 줄었다(고친 뒤에도 남으면 다음 실행이 다시 고친다)
  · 다른 검사 위반이 늘지 않았다(check — 그 글의 textRules 그대로)
  · 칸 구조가 같고(repair 가 본다), 한국어가 있는 칸의 영어가 비지 않았다
  · 숫자를 지우지 않았고, 새로 생긴 숫자는 연도(2019~2031) · 연도에 붙은 분기 · 반기 · 월 번호('2025년 3분기' · '2025년 1~3분기' ·
    'Q3 2025') · 그 칸에 이미 있던 숫자뿐이다 — 사실은 바꾸지 않고 표현만 바꾸게(11/23 두 번째 실행에서 '2025년 3분기' ·
    '5월 24일'(같은 칸의 날짜)을 쓴 맞는 답 13편이 '연도가 아닌 새 숫자'로 버려졌다)
textRules 는 바꾸지 않는다(그 글을 쓴 지시문의 판이다). 파일은 원래 꼴(들여쓰기)대로 쓴다. 돈은 배치 단가로 편당 약 0.01~0.02달러.
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_report_text as C  # noqa: E402

STATE = Path(os.getenv("REPAIR_STATE", "/tmp/repair_rules_state.json"))
WAIT_SEC = int(os.getenv("REPAIR_WAIT_SEC", str(4 * 3600)))
PRICE = {"in": 1.0, "out": 5.0, "cache_w": 1.25, "cache_r": 0.10}   # 소넷 5.5 배치 · 100만 토큰당 달러(기록용 · 콘솔이 기준)


def _year_hits(rep):
    return C.year_hits(dict(rep, textRules=max(rep.get("textRules") or 0, C.YEAR_RULES)))


RULES = {"stale_year": _year_hits}


def log(*a):
    print(*a, flush=True)


def report_files(root=None):
    """화면에 나오는 리포트 — 새 형식 전부와, 새 형식이 없는 종목의 옛 형식(check_report_text_test 전수와 같은 범위)."""
    root = root or ROOT
    v2 = {f.stem for f in (root / "data" / "reports_v2").glob("*.json")}
    return sorted((root / "data" / "reports_v2").glob("*.json")) + \
        [f for f in sorted((root / "data" / "reports").glob("*.json")) if f.stem not in v2]


def load(f):
    text = f.read_text(encoding="utf-8")
    return json.loads(text), text


def dump_like(obj, text):
    """원래 파일과 같은 꼴(들여쓰기 · 끝 줄바꿈)로 — 고친 칸 밖의 줄이 바뀌지 않게."""
    tail = "\n" if text.endswith("\n") else ""
    try:
        orig = json.loads(text)
    except Exception:                                        # noqa: BLE001
        orig = None
    for ind in (1, 2, None, 4):
        if orig is not None and json.dumps(orig, ensure_ascii=False, indent=ind) + tail == text:
            return json.dumps(obj, ensure_ascii=False, indent=ind) + tail
    return json.dumps(obj, ensure_ascii=False, indent=1) + tail


def fingerprint(rep, sections):
    return hashlib.sha1(json.dumps({k: rep.get(k) for k in sections}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def cid_of(f):
    return f"{'v2' if f.parent.name == 'reports_v2' else 'v1'}_{f.stem}"


def targets(rule, limit=0, root=None):
    fn = RULES[rule]
    out = []
    for f in report_files(root):
        try:
            rep, _ = load(f)
        except Exception:                                    # noqa: BLE001
            continue
        if not isinstance(rep, dict):
            continue
        hits = fn(rep)
        if hits:
            out.append((f, rep, hits))
            if limit and len(out) >= limit:
                break
    return out


class _Ask(BaseException):
    """repair 가 보내려던 요청 — 모델을 부르지 않고 받아 둔다(generate_reports_batch 와 같은 방식)."""

    def __init__(self, params):
        super().__init__()
        self.params = params


class _OneShot:
    def __init__(self, answer=None):
        outer = self
        self.answer = answer

        class _Msgs:
            def create(self, **kw):
                if outer.answer is None:
                    raise _Ask(kw)
                return outer.answer

        self.messages = _Msgs()


def request_of(rep, hits):
    try:
        C.repair(_OneShot(), rep, hits)
    except _Ask as a:
        return a.params
    return None


# ── 저장 문턱 ───────────────────────────────────────────────────────────────────────────────────────
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers(obj):
    from collections import Counter
    c = Counter()
    for path, f in C._flat_fields(obj).items():
        for side in ("ko", "en"):
            for m in _NUM.findall(f.get(side) or ""):
                c[m.replace(",", "")] += 1
    return c


# 연도에 붙은 분기 · 반기 · 월 번호 — '2025년 3분기' · '2025년 1~3분기' · '2026년 5월' · 'Q3 2025' · '3Q 2025' · 'H1 2025' · '2025 Q3'.
_TIME_NUM = (re.compile(r"(?:19|20)\d\d년\s*(\d{1,2})(?:\s*~\s*(\d{1,2}))?\s*(?:분기|월)"),
             re.compile(r"\b[QH]([1-4])\s*(?:FY\s*)?(?:19|20)\d\d\b"),
             re.compile(r"\b([1-4])[QH]\s*(?:FY\s*)?(?:19|20)\d\d\b"),
             re.compile(r"\b(?:19|20)\d\d\s*[QH]([1-4])\b"))


def time_numbers(obj):
    """글 안에서 연도에 붙어 쓰인 분기 · 반기 · 월 번호."""
    out = set()
    for f in C._flat_fields(obj).values():
        for side in ("ko", "en"):
            t = f.get(side) or ""
            for pat in _TIME_NUM:
                for m in pat.finditer(t):
                    out.update(g for g in m.groups() if g)
    return out


def number_guard(before, after):
    """지운 숫자가 없고, 새 숫자는 연도 · 연도에 붙은 분기 · 월 번호 · 그 칸에 이미 있던 숫자뿐인가 — (통과, 사유)."""
    a, b = numbers(before), numbers(after)
    lost = a - b
    new = b - a
    if lost:
        return False, "숫자가 빠짐 " + ", ".join(sorted(lost)[:5])
    timed = time_numbers(after)
    odd = [n for n in new if not ((n.isdigit() and 2019 <= int(n) <= 2031) or n in timed or a[n])]
    if odd:
        return False, "연도가 아닌 새 숫자 " + ", ".join(sorted(odd)[:5])
    return True, ""


def en_gap_count(rep):
    return sum(1 for f in C._flat_fields({k: v for k, v in rep.items() if k not in C._NOT_TEXT}).values()
               if (f.get("ko") or "").strip() and not (f.get("en") or "").strip())


def judge(rule, rep_now, msg):
    """답을 지금 글에 끼워 본다 — (고친 글 또는 None, 사유)."""
    fn = RULES[rule]
    hits = fn(rep_now)
    if not hits:
        return None, "이미 위반 없음"
    try:
        fixed = C.repair(_OneShot(msg), rep_now, hits)
    except Exception as e:                                   # noqa: BLE001
        return None, f"답을 읽지 못함 {type(e).__name__}"
    if not fixed:
        return None, "답의 칸 구조가 다르거나 위반이 줄지 않음"
    rep2 = C.prepare(fixed[0])
    left = fn(rep2)
    if len(left) >= len(hits):
        return None, "규칙 위반이 줄지 않음"
    before = {(h["rule"], h["section"]) for h in C.check(rep_now)}
    after = C.check(rep2)
    new = [h for h in after if (h["rule"], h["section"]) not in before]
    if new:
        return None, "다른 검사 위반이 생김 " + ", ".join(f"{h['rule']}@{h['section']}" for h in new[:3])
    if en_gap_count(rep2) > en_gap_count(rep_now):
        return None, "영어 칸이 비었음"
    secs = sorted({h["section"] for h in hits})
    ok, why = number_guard({k: rep_now.get(k) for k in secs}, {k: rep2.get(k) for k in secs})
    if not ok:
        return None, why
    return rep2, f"{len(hits)} → {len(left)}"


# ── 단계 ────────────────────────────────────────────────────────────────────────────────────────────
def cmd_plan(rule, limit):
    ts = targets(rule, limit)
    n = sum(len(h) for _, _, h in ts)
    by = {}
    for f, rep, _ in ts:
        by[str(rep.get("reportDate", ""))[:7]] = by.get(str(rep.get("reportDate", ""))[:7], 0) + 1
    log(f"## {rule} — 고칠 리포트 {len(ts)}편 · 걸린 곳 {n}곳 · 작성 달별 {dict(sorted(by.items()))}")
    return ts


def cmd_order(cl, rule, limit, sleep=time.sleep):
    ts = targets(rule, limit)
    if not ts:
        log(f"## {rule} — 고칠 리포트 없음")
        STATE.write_text(json.dumps({"rule": rule, "batch_id": None, "items": {}}, ensure_ascii=False), encoding="utf-8")
        return None
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    reqs, items = [], {}
    for f, rep, hits in ts:
        p = request_of(rep, hits)
        if not p:
            continue
        cid = cid_of(f)
        secs = sorted({h["section"] for h in hits if h["section"] in rep})
        items[cid] = {"file": str(f.relative_to(ROOT)), "sections": secs, "fp": fingerprint(rep, secs), "hits": len(hits)}
        reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**p)))
    b = cl.messages.batches.create(requests=reqs)
    log(f"## {rule} — 교정 배치 제출 {b.id} · {len(reqs)}편 · 걸린 곳 {sum(i['hits'] for i in items.values())}곳")
    STATE.write_text(json.dumps({"rule": rule, "batch_id": b.id, "items": items}, ensure_ascii=False), encoding="utf-8")
    waited = 0
    while True:
        st = cl.messages.batches.retrieve(b.id)
        if st.processing_status == "ended":
            break
        if waited >= WAIT_SEC:
            raise TimeoutError(f"교정 배치가 {WAIT_SEC // 60}분 안에 끝나지 않았다({b.id}) — 같은 배치를 apply 로 다시 받는다")
        sleep(60)
        waited += 60
    log(f"- 배치 끝 ({waited // 60}분)")
    return b.id


def cmd_apply(cl, state=None):
    st = state or json.loads(STATE.read_text(encoding="utf-8"))
    rule, bid, items = st["rule"], st.get("batch_id"), st.get("items") or {}
    if not bid:
        log("받을 배치 없음")
        return {}
    use = {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0}
    got = {}
    for r in cl.messages.batches.results(bid):
        if r.custom_id in items and r.result.type == "succeeded":
            got[r.custom_id] = r.result.message
            u = getattr(r.result.message, "usage", None)
            if u is not None:
                use["in"] += getattr(u, "input_tokens", 0) or 0
                use["out"] += getattr(u, "output_tokens", 0) or 0
                use["cache_w"] += getattr(u, "cache_creation_input_tokens", 0) or 0
                use["cache_r"] += getattr(u, "cache_read_input_tokens", 0) or 0
    saved, why_skip, left = [], {}, 0
    for cid, it in sorted(items.items()):
        f = ROOT / it["file"]
        msg = got.get(cid)
        if msg is None:
            why_skip["답 없음(배치 실패)"] = why_skip.get("답 없음(배치 실패)", 0) + 1
            continue
        if not f.exists():
            why_skip["파일 없음"] = why_skip.get("파일 없음", 0) + 1
            continue
        rep_now, text = load(f)
        if fingerprint(rep_now, it["sections"]) != it["fp"]:
            why_skip["그 사이 다시 쓰임"] = why_skip.get("그 사이 다시 쓰임", 0) + 1
            continue
        rep2, why = judge(rule, rep_now, msg)
        if rep2 is None:
            key = why.split(" ")[0] if why.startswith(("숫자가", "연도가", "다른")) else why
            why_skip[key] = why_skip.get(key, 0) + 1
            log(f"  · 건너뜀 {cid} — {why}")
            continue
        f.write_text(dump_like(rep2, text), encoding="utf-8")
        saved.append(f.stem)
        left += len(RULES[rule](rep2))
    usd = sum(use[k] * PRICE[k] for k in use) / 1e6
    log(f"## {rule} — 저장 {len(saved)}편 · 건너뜀 {sum(why_skip.values())}편 {why_skip} · 저장한 글에 남은 곳 {left}곳")
    log(f"- 사용량 입력 {use['in']:,} · 캐시 쓰기 {use['cache_w']:,} · 캐시 읽기 {use['cache_r']:,} · 출력 {use['out']:,}"
        f" · 배치 단가 약 {usd:.2f}달러(콘솔이 기준)")
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fo:
            fo.write(f"saved={len(saved)}\n")
    return {"saved": saved, "skip": why_skip, "left": left, "usd": round(usd, 4)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["plan", "order", "apply"])
    ap.add_argument("--rule", default="stale_year", choices=sorted(RULES))
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)
    if a.mode == "plan":
        cmd_plan(a.rule, a.limit)
        return 0
    import anthropic
    cl = anthropic.Anthropic()
    if a.mode == "order":
        cmd_order(cl, a.rule, a.limit)
    else:
        cmd_apply(cl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
