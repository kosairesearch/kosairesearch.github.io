#!/usr/bin/env python3
"""
KOS ai — 업종(섹터) AI 분석 생성기 (Batch API · Sonnet)

각 업종에 대해 개요·구조(가치사슬)·최근동향·전망·리스크를 한/영으로 생성해
data/sectors.js (window.KOS_SECTORS) 를 만든다. 업종별 상위 종목·집계 통계를
프롬프트에 제공한다. 종목 리포트 배치 로직을 일부 재사용.

모드: submit / collect / auto(기본)
환경변수: ANTHROPIC_API_KEY(필수), REPORT_MODEL(기본 claude-sonnet-5), SECTOR_FORCE, BATCH_MAX_WAIT_SEC
"""
import os
import re
import sys
import json
import time
import datetime
from collections import defaultdict
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

import generate_reports as g  # extract_text / parse_report / collect_sources 재사용

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
OUT_JS = ROOT / "data" / "sectors.js"
STATE = ROOT / "data" / "sector_batch_state.json"

MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-5")
FORCE = os.getenv("SECTOR_FORCE", "") == "1"
MAX_WAIT = int(os.getenv("BATCH_MAX_WAIT_SEC", "4800"))

TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3,
          "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]

log = g.log

SYSTEM = (
    "너는 한국 증시 섹터(업종) 애널리스트다. 주어진 업종의 한국 상장사들을 바탕으로 "
    "투자 참고용 업종 분석을 작성한다. 매수/매도·목표주가 등 투자권유 표현은 쓰지 않는다. "
    "수치는 확인된 것만 쓰고 과장·날조하지 않는다. 전문 애널리스트 톤."
)

# en 자리를 ""로 비워 보였더니 모델이 템플릿 그대로 빈 문자열을 내놓는 일이 있었다
# (2026-08 생성분에서 조선·2차전지의 본문 영어가 통째로 비었다). 그래서 en 에도
# 무엇을 쓸지 명시하고, 비우지 말라는 규칙을 따로 둔다.
SCHEMA = """다음 JSON 스키마로만 출력하세요. 모든 텍스트는 {"ko":"한국어","en":"영어"} 형식입니다.
===JSON_START===
{
  "lead":     {"ko":"업종 한 줄 요약(매수/매도 표현 금지)","en":"same, in English"},
  "overview": {"ko":"업종 개요: 어떤 산업이고 한국 증시에서의 위치·특성 (4~6문장)","en":"same, in English"},
  "structure":{"ko":"산업 구조·가치사슬: 밸류체인 단계와 대표 종목 배치, 집중도 (4~6문장)","en":"same, in English"},
  "trends":   {"ko":"최근 업황·동향: 실적/수요/사이클 흐름 (4~6문장)","en":"same, in English"},
  "outlook":  {"ko":"향후 전망: 성장 동인과 관전 포인트 (4~6문장)","en":"same, in English"},
  "risks":    [ {"title":{"ko":"제목","en":"title in English"},
                 "body":{"ko":"2~3문장","en":"same, in English"}}, ... 3개 ]
}
===JSON_END===
규칙
- 마커 사이에 JSON만. 한국어는 자연스럽게, 영어는 전문 번역체로.
- ko·en 어느 쪽도 빈 문자열로 두지 말 것. 모든 항목을 양쪽 언어로 채운다.
- 문장은 반드시 끝맺을 것. 분량이 부담되면 문장 수를 줄이되 중간에 끊지 않는다.
- 한자를 섞지 말 것(예: '고객사向' → '고객사 대상', '美' → '미국')."""


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음"); sys.exit(1)
    return anthropic.Anthropic(api_key=key)


def load_sectors():
    raw = STOCKS_JS.read_text(encoding="utf-8")
    stocks = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]
    total = sum(s.get("mcap", 0) or 0 for s in stocks)
    by = defaultdict(list)
    for s in stocks:
        cats = s.get("categories") or [s.get("sector", "기타")]
        for c in cats:
            by[c].append(s)
    out = {}
    for sec, lst in by.items():
        mc = sum(s.get("mcap", 0) or 0 for s in lst)
        top = sorted(lst, key=lambda x: x.get("mcap", 0) or 0, reverse=True)[:12]
        out[sec] = {
            "count": len(lst), "mcap": round(mc, 1),
            "weight": round(mc / total * 100, 1) if total else 0,
            "top": [(t["name"], round(t.get("mcap", 0) or 0, 2)) for t in top],
        }
    return out


def build_prompt(sec, info):
    tops = "\n".join(f"  - {nm} (시총 {mc}조)" for nm, mc in info["top"])
    return (
        f"[업종] {sec}\n"
        f"[집계] 상장 종목 {info['count']}개 · 업종 시가총액 합계 약 {info['mcap']}조원 "
        f"(전체 시장의 약 {info['weight']}%)\n"
        f"[시총 상위 종목]\n{tops}\n\n"
        f"위 업종에 대해 한국 증시 관점의 업종 분석을 작성하세요. 위 상위 종목들을 적절히 언급하고, "
        f"필요하면 웹 검색으로 최근 업황을 확인하세요.\n\n" + SCHEMA
    )


def submit(cl, as_of):
    sectors = load_sectors()
    existing = load_existing()
    targets = [s for s in sectors if FORCE or s not in existing]
    # '기타'는 업종 분석 의미가 적어 제외
    targets = [s for s in targets if s != "기타"]
    log(f"## 업종 분석 batch 제출 — 대상 {len(targets)}개 / 전체 {len(sectors)}개 · 모델 {MODEL}")
    if not targets:
        log("- 생성할 업종 없음(모두 보유). 종료."); return None
    reqs = []
    for sec in targets:
        reqs.append(Request(
            custom_id=_cid(sec),
            params=MessageCreateParamsNonStreaming(
                model=MODEL, max_tokens=24000,
                system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
                thinking={"type": "adaptive"}, tools=TOOLS,
                messages=[{"role": "user", "content": build_prompt(sec, sectors[sec])}],
            )))
        log(f"  · 준비 {sec} ({sectors[sec]['count']}종목)")
    batch = cl.messages.batches.create(requests=reqs)
    cid_map = {_cid(s): s for s in targets}
    STATE.write_text(json.dumps({"batch_id": batch.id, "created": as_of, "model": MODEL,
                                 "cid_map": cid_map}, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건)")
    return batch.id


def _cid(sec):
    # custom_id는 영숫자/언더스코어 권장 → 인덱스 기반 안전 id
    return "sec_" + str(abs(hash(sec)) % (10**10))


def poll(cl, bid):
    waited = 0
    while waited < MAX_WAIT:
        b = cl.messages.batches.retrieve(bid)
        rc = b.request_counts
        log(f"  · {b.processing_status} · 처리 {rc.processing}/성공 {rc.succeeded}/오류 {rc.errored}")
        if b.processing_status == "ended":
            return True
        time.sleep(60); waited += 60
    return False


def load_existing():
    if OUT_JS.exists():
        try:
            raw = OUT_JS.read_text(encoding="utf-8")
            return json.loads(raw[raw.find("{"): raw.rfind("}") + 1]).get("sectors", {}) or {}
        except Exception:
            return {}
    return {}


BODY_KEYS = ("lead", "overview", "structure", "trends", "outlook")
_ENDS = re.compile(r'[.!?…"”\')\]]\s*$')


def defects(rep, message=None):
    """저장하면 안 되는 결함 목록. 비어 있으면 정상.

    2026-08 생성분에서 실제로 나온 것들이다. 한 번 저장되면 다음 분기까지 그대로
    사이트에 걸리므로, 여기서 걸러 다음 실행 때 다시 만들게 한다(대상은 '없는 업종').
      · 영어 본문이 통째로 빈 채로 저장 → 영어 모드에서 한국어가 그대로 노출
      · max_tokens 로 잘려 json_repair 가 문장 중간을 닫아버림
      · 인코딩이 깨진 자리(U+FFFD)가 본문에 박힘
    """
    out = []
    if getattr(message, "stop_reason", None) == "max_tokens":
        out.append("max_tokens 로 잘림")
    if not rep.get("risks") or len(rep["risks"]) < 3:
        out.append("리스크 3개 미만")

    def check(label, o):
        for lang in ("ko", "en"):
            s = (o or {}).get(lang, "")
            if not (s or "").strip():
                out.append(f"{label}.{lang} 빔")
            elif not _ENDS.search(s):
                out.append(f"{label}.{lang} 문장 안 끝남")

    for k in BODY_KEYS:
        check(k, rep.get(k))
    for i, r in enumerate(rep.get("risks") or []):
        check(f"risks[{i}].body", (r or {}).get("body"))
        for lang in ("ko", "en"):
            if not ((r or {}).get("title") or {}).get(lang, "").strip():
                out.append(f"risks[{i}].title.{lang} 빔")
    if "�" in json.dumps(rep, ensure_ascii=False):
        out.append("깨진 문자(U+FFFD)")
    return out


def collect(cl, as_of):
    if not STATE.exists():
        log("❌ state 없음"); sys.exit(1)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    b = cl.messages.batches.retrieve(st["batch_id"])
    if b.processing_status != "ended":
        log(f"- 아직 처리 중({b.processing_status})."); return False
    cid_map = st["cid_map"]
    sectors = load_existing()
    ok = fail = 0
    for result in cl.messages.batches.results(st["batch_id"]):
        sec = cid_map.get(result.custom_id)
        if not sec:
            continue
        if result.result.type != "succeeded":
            fail += 1; log(f"  · ⚠️ {sec} {result.result.type}"); continue
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            why = defects(rep, result.result.message)
            if why:
                fail += 1; log(f"  · ⚠️ {sec} 불완전 — 건너뜀 ({'; '.join(why)})"); continue
            srcs = g.collect_sources(result.result.message)
            if srcs:
                rep["sources"] = srcs[:10]
            rep["sector"] = sec
            # 업종별 작성 시점. FORCE 없이 돌리면 새로 만든 업종과 예전 것이 섞이므로
            # 전체 lastUpdated 만으로는 화면에 정확한 날짜를 못 쓴다.
            rep["generatedAt"] = as_of
            sectors[sec] = rep
            ok += 1
        except Exception as e:
            fail += 1; log(f"  · ⚠️ {sec} 파싱 실패: {e}")
    payload = {"lastUpdated": as_of, "model": st.get("model", MODEL), "sectors": sectors}
    OUT_JS.write_text("// KOS ai — 업종 AI 분석 (자동 생성). 직접 수정 금지.\n"
                      "window.KOS_SECTORS = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
                      encoding="utf-8")
    log(f"\n✅ 회수 완료 · 성공 {ok}/실패 {fail} · 총 {len(sectors)}개 → data/sectors.js")
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
    log(f"## generate_sectors 시작 — mode={mode!r} · MODEL={MODEL} · FORCE={FORCE}")
    sys.stdout.flush()
    cl = client()
    as_of = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    if mode == "submit":
        submit(cl, as_of)
    elif mode == "collect":
        collect(cl, as_of)
    else:
        bid = submit(cl, as_of)
        if bid and poll(cl, bid):
            collect(cl, as_of)


def _entry():
    try:
        main()
    except Exception as e:
        import traceback
        msg = "❌ generate_sectors 예외: " + "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(msg, flush=True)
        try:
            (ROOT / "data" / "sectors_run.log").open("a", encoding="utf-8").write(msg + "\n")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    _entry()
