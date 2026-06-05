#!/usr/bin/env python3
"""
KOS ai — 업종(섹터) AI 분석 생성기 (Batch API · Sonnet)

각 업종에 대해 개요·구조(가치사슬)·최근동향·전망·리스크를 한/영으로 생성해
data/sectors.js (window.KOS_SECTORS) 를 만든다. 업종별 상위 종목·집계 통계를
프롬프트에 제공한다. 종목 리포트 배치 로직을 일부 재사용.

모드: submit / collect / auto(기본)
환경변수: ANTHROPIC_API_KEY(필수), REPORT_MODEL(기본 sonnet), SECTOR_FORCE, BATCH_MAX_WAIT_SEC
"""
import os
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

MODEL = os.getenv("REPORT_MODEL", "claude-sonnet-4-6")
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

SCHEMA = """다음 JSON 스키마로만 출력하세요. 각 텍스트는 {"ko","en} 형식(한국어/영어 병기).
===JSON_START===
{
  "lead":     {"ko":"업종 한 줄 요약(매수/매도 표현 금지)","en":""},
  "overview": {"ko":"업종 개요: 어떤 산업이고 한국 증시에서의 위치·특성 (4~6문장)","en":""},
  "structure":{"ko":"산업 구조·가치사슬: 밸류체인 단계와 대표 종목 배치, 집중도 (4~6문장)","en":""},
  "trends":   {"ko":"최근 업황·동향: 실적/수요/사이클 흐름 (4~6문장)","en":""},
  "outlook":  {"ko":"향후 전망: 성장 동인과 관전 포인트 (4~6문장)","en":""},
  "risks":    [ {"title":{"ko":"","en":""}, "body":{"ko":"2~3문장","en":""}}, ... 3개 ]
}
===JSON_END===
규칙: 마커 사이에 JSON만. 한국어는 자연스럽게, 영어는 전문 번역체로."""


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
                model=MODEL, max_tokens=16000,
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
            if not (rep.get("overview") and rep.get("risks")):
                fail += 1; log(f"  · ⚠️ {sec} 불완전 — 건너뜀"); continue
            srcs = g.collect_sources(result.result.message)
            if srcs:
                rep["sources"] = srcs[:10]
            rep["sector"] = sec
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
