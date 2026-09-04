#!/usr/bin/env python3
"""
KOS ai — 업종(섹터) AI 분석 생성기 (Batch API 전용 · Sonnet)

각 업종에 대해 개요·구조(가치사슬)·최근동향·전망·리스크를 한/영으로 생성해
data/sectors.js (window.KOS_SECTORS) 를 만든다. 업종별 상위 종목·집계 통계를
프롬프트에 제공한다. 종목 리포트 배치 로직을 일부 재사용.

■ Batch API 만 쓴다 (예외 없음)

  같은 모델·같은 프롬프트라도 Batch 로 보내면 요금이 절반이다. 30개 업종을
  한 번에 내는 일은 급할 이유가 없으므로 즉시 응답에 두 배를 낼 까닭이 없다.

  '그렇게 하기로 한다' 는 약속은 언젠가 새어 나간다. 그래서 client() 에서
  즉시 호출 창구(messages.create)를 막아 둔다. 실수로 부르면 그 자리에서
  멈추고, 조용히 두 배를 물지 않는다.

■ 언제 도는가

  분기 1회, 정기보고서 마감 한 주 뒤.

    사업보고서   3월 31일  →   4월  7일
    1분기        5월 15일  →   5월 21일
    반기         8월 14일  →   8월 21일
    3분기       11월 14일  →  11월 21일

  마감 당일로 붙이지 않는다. 그날은 제출이 몰려 데이터가 다음 날에야
  정리되고, 업황 해설도 아직 안 나와 검색할 것이 없다.

모드: submit / collect / auto(기본)
환경변수: ANTHROPIC_API_KEY(필수), REPORT_MODEL(기본 claude-sonnet-5), SECTOR_FORCE, BATCH_MAX_WAIT_SEC
"""
import os
import re
import sys
import json
import time
import hashlib
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
- 한자를 섞지 말 것(예: '고객사向' → '고객사 대상', '美' → '미국').
- ★ 위 [집계]에 준 수치(업종 시가총액 합계·전체 시장 비중·상장 종목 수)와
  [시총 상위 종목]의 시총 금액은 문장에 그대로 쓰지 말 것. 이 값들은 매
  거래일 바뀌고, 화면이 본문 위에서 최신 값을 따로 보여 준다. 문장에 박으면
  그날부터 화면의 숫자와 본문의 숫자가 서로 다른 말을 하게 된다.
  준 수치는 업종의 규모·성격을 파악하는 참고용이며, 크기는 '관계'로 서술한다.
    (X) 업종 시가총액은 약 2786.3조원으로 전체 시장의 48.8%를 차지한다
    (O) 전체 시장 시가총액의 절반에 가까운 비중을 차지하는 최대 업종이다
    (X) 상장 종목은 119개로 시가총액 합계는 약 47.5조원이다
    (O) 종목 수는 많지만 개별 규모는 작아 시장 비중은 1%를 밑도는 업종이다
  다만 개별 기업의 점유율·실적·수주 같은 값은 공시나 검색으로 확인했다면
  수치로 써도 된다(예: "TC 본더 세계 점유율 약 71%"). 금지하는 것은 화면이
  실시간으로 다시 계산해 보여 주는 집계 수치뿐이다."""


class BatchOnly(RuntimeError):
    """즉시 호출 창구를 부르려 했다. Batch 로만 보내기로 한 규칙을 어긴 것이다."""


def client():
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log("❌ ANTHROPIC_API_KEY 없음"); sys.exit(1)
    cl = anthropic.Anthropic(api_key=key)

    # 즉시 호출 창구를 실제로 막는다. 주석으로 "Batch 만 쓴다" 고 적어 두는
    # 것과 부를 수 없게 만드는 것은 다르다 — 앞의 것은 다음에 고치는 사람이
    # 안 읽으면 그대로 새고, 새더라도 요금이 두 배가 될 뿐 화면은 멀쩡해서
    # 아무도 모른다. 여기서 막으면 그 자리에서 멈춘다.
    def _blocked(*_a, **_kw):
        raise BatchOnly(
            "업종 분석은 Batch API 로만 보낸다(요금 절반). "
            "messages.create 가 아니라 messages.batches.create 를 쓸 것.")

    cl.messages.create = _blocked
    cl.messages.stream = _blocked
    return cl


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
        f"[집계 · 참고용, 본문에 수치로 옮기지 말 것] 상장 종목 {info['count']}개 · "
        f"업종 시가총액 합계 약 {info['mcap']}조원 (전체 시장의 약 {info['weight']}%)\n"
        f"[시총 상위 종목 · 종목명은 쓰되 금액은 본문에 옮기지 말 것]\n{tops}\n\n"
        f"위 업종에 대해 한국 증시 관점의 업종 분석을 작성하세요. 위 상위 종목들을 적절히 언급하고, "
        f"필요하면 웹 검색으로 최근 업황을 확인하세요.\n\n" + SCHEMA
    )


# 지난 실행에서 걸러진 업종을 적어 두는 파일.
RETRY = ROOT / "data" / "sector_retry.json"


def load_retry():
    """지난 실행에서 걸러진 업종. 파일이 없거나 깨졌으면 빈 목록."""
    try:
        return set(json.loads(RETRY.read_text(encoding="utf-8")).get("failed") or [])
    except Exception:
        return set()


def save_retry(failed, as_of):
    """이번에 걸러진 업종을 적어 둔다. 없으면 파일을 치운다."""
    if failed:
        RETRY.write_text(json.dumps({"at": as_of, "failed": sorted(failed)},
                                    ensure_ascii=False, indent=2), encoding="utf-8")
    elif RETRY.exists():
        RETRY.unlink()


def submit(cl, as_of):
    sectors = load_sectors()
    existing = load_existing()
    # 걸러진 업종을 다시 대상에 넣는다.
    #
    # defects() 가 잡아낸 업종은 저장되지 않으므로 옛 글이 그대로 남는다.
    # 그런데 대상을 고르는 조건이 's not in existing'(없는 업종) 뿐이라,
    # 옛 글이 남아 있는 그 업종은 다음 실행에서도 건너뛰어졌다 — 영영 낡은
    # 채로 갇힌다. FORCE 로 전부 다시 만드는 길밖에 없었고, 그건 멀쩡한
    # 스물몇 개까지 다시 만드는 것이라 돈이 그만큼 더 든다.
    #
    # 2026-09-04 실행에서 30개 중 11개가 걸러졌다(영문이 비거나 글자가 깨진
    # 출력). 그때 이 목록이 없어서 11개가 8월 글 그대로 남았다.
    retry = load_retry()
    targets = [s for s in sectors if FORCE or s not in existing or s in retry]
    if retry and not FORCE:
        log(f"- 지난번에 걸러진 {len(retry)}개를 다시 만든다: {', '.join(sorted(retry))}")
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
    if len(cid_map) != len(targets):                 # sha1 이 겹칠 일은 없지만, 겹치면 업종이 조용히 사라진다
        log("❌ custom_id 가 겹쳤다 — 중단"); sys.exit(1)
    # 프롬프트에 넣어 준 집계를 그대로 적어 둔다. 회수할 때 '이 숫자가 본문에
    # 박혔는지' 를 보는데, 그때 시세를 다시 읽으면 값이 이미 움직여 있어서
    # 정작 박힌 숫자를 놓친다(실제로 8월 생성분 4개가 그렇게 새 나갔다).
    agg = {s: sectors[s] for s in targets}
    STATE.write_text(json.dumps({"batch_id": batch.id, "created": as_of, "model": MODEL,
                                 "cid_map": cid_map, "agg": agg},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"- ✅ 배치 제출: {batch.id} ({len(reqs)}건)")
    return batch.id


def _cid(sec):
    """custom_id 는 영숫자·언더스코어만 쓴다. 업종 이름은 한글이라 못 쓴다.

    파이썬의 hash() 를 쓰고 있었는데 그건 실행마다 값이 바뀐다(해시 무작위화).
    제출·회수를 따로 돌리면 cid_map 을 파일에 적어 두므로 동작은 했지만,
    같은 업종이 실행마다 다른 번호를 받아 로그를 맞대 볼 수 없었다.
    sha1 은 언제 돌려도 같은 값이 나온다.
    """
    return "sec_" + hashlib.sha1(sec.encode("utf-8")).hexdigest()[:16]


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


def _num_variants(v):
    """모델이 같은 수를 적을 수 있는 여러 모양. 2786.3 → 2786.3 · 2,786.3 · 2786 …"""
    out = {f"{v:g}"}
    s = f"{v:g}"
    if "." in s:                                   # 소수를 떼고 적기도 한다
        out.add(s.split(".")[0])
    for x in list(out):
        if len(x) > 3 and x.isdigit():             # 천 단위 쉼표를 넣기도 한다
            out.add(f"{int(x):,}")
    return {x for x in out if x and x != "0"}


# 화면이 본문 위에서 실시간으로 다시 계산해 보여 주는 집계 수치.
# 문장에 그대로 박히면 그날부터 위아래가 서로 다른 숫자를 말한다.
_LIVE = (
    ("업종 시가총액 합계", "mcap", r"\s*조", r"(시가총액|시총|시장\s*규모)"),
    ("전체 시장 비중", "weight", r"\s*%", r"(비중|차지|전체\s*시장|시장의|시장\s*전체)"),
    ("상장 종목 수", "count", r"\s*개", r"(종목|상장사|기업)"),
)


def live_number_hits(rep, info):
    """프롬프트에 넣어 준 집계 수치가 본문에 그대로 옮겨졌는지 본다.

    우리가 준 값이 무엇인지 아니까 그 값만 찾는다 — '숫자가 있으면 잡는다' 가
    아니다. 개별 기업의 점유율·실적 수치는 확인된 정보라 그대로 둬야 한다.

    숫자 옆(앞뒤 30자)에 '시가총액'·'비중'·'종목' 같은 말이 있을 때만 잡는다.
    같은 숫자가 우연히 다른 뜻으로 나올 수 있기 때문이다(영업이익률 0.8% 등).
    """
    if not info:
        return []
    body = " ".join(
        (rep.get(k) or {}).get(lang, "")
        for k in BODY_KEYS for lang in ("ko", "en")
    ) + " " + " ".join(
        ((r or {}).get("body") or {}).get(lang, "")
        for r in (rep.get("risks") or []) for lang in ("ko", "en")
    )
    hits = []
    for label, key, unit, near in _LIVE:
        val = info.get(key)
        if not val:
            continue
        for var in _num_variants(val):
            for m in re.finditer(re.escape(var) + unit, body):
                a, b = max(0, m.start() - 30), m.end() + 30
                if re.search(near, body[a:b]):
                    hits.append(f"{label}({var}) 본문에 박힘")
                    break
            else:
                continue
            break
    return hits


def defects(rep, message=None, info=None):
    """저장하면 안 되는 결함 목록. 비어 있으면 정상.

    2026-08 생성분에서 실제로 나온 것들이다. 한 번 저장되면 다음 분기까지 그대로
    사이트에 걸리므로 여기서 거른다. 걸러진 업종은 save_retry 가 적어 두고
    다음 실행이 그것만 다시 만든다 — 그 목록이 없던 동안에는 옛 글이 남아
    있다는 이유로 '이미 있는 업종' 으로 분류돼 영영 건너뛰어졌다.
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
    out += live_number_hits(rep, info)
    return out


def _tally(use, message):
    """이번 회수분이 실제로 쓴 양을 더한다.

    여태 로그에는 배치 제출·회수 기록만 있고 얼마를 썼는지가 없었다. 그래서
    "업종 분석을 월 1회로 늘리면 얼마 더 드나" 를 기록으로 답할 수 없었다.
    """
    u = getattr(message, "usage", None)
    if not u:
        return
    for k in ("input_tokens", "output_tokens",
              "cache_read_input_tokens", "cache_creation_input_tokens"):
        use[k] += getattr(u, k, 0) or 0
    stu = getattr(u, "server_tool_use", None)
    use["web_search"] += getattr(stu, "web_search_requests", 0) or 0 if stu else 0


# Batch API 요금(1M 토큰당, 즉시 호출의 절반). 2026-09 기준이며 요금표가
# 바뀌면 아래 추정액만 어긋난다 — 토큰 수 자체는 그대로 남으므로 나중에
# 다시 계산할 수 있다.
_RATE = {"claude-sonnet-5": (1.50, 7.50), "claude-opus-5": (2.50, 12.50)}
_WEB_SEARCH_PER_1K = 10.0                       # 웹 검색 1,000회당(배치 할인 없음)


def _log_usage(use, model):
    if not use:
        log("- 사용량 정보 없음(회수 결과에 usage 가 없다)")
        return
    ins = use["input_tokens"] + use["cache_read_input_tokens"] + use["cache_creation_input_tokens"]
    outs = use["output_tokens"]
    log(f"\n■ 사용량 — 입력 {ins:,} 토큰 · 출력 {outs:,} 토큰 · 웹 검색 {use['web_search']}회")
    rate = _RATE.get(model)
    if rate:
        cost = ins / 1e6 * rate[0] + outs / 1e6 * rate[1] \
             + use["web_search"] / 1000 * _WEB_SEARCH_PER_1K
        log(f"  대략 ${cost:,.2f} (Batch 요금 · {model} · 2026-09 요금표 기준 추정)")
    else:
        log(f"  요금표에 없는 모델({model}) — 토큰 수로 직접 계산할 것")


def collect(cl, as_of):
    if not STATE.exists():
        log("❌ state 없음"); sys.exit(1)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    b = cl.messages.batches.retrieve(st["batch_id"])
    if b.processing_status != "ended":
        log(f"- 아직 처리 중({b.processing_status})."); return False
    cid_map = st["cid_map"]
    sectors = load_existing()
    # 제출할 때 적어 둔 집계를 쓴다. 옛 state 에는 없으므로 그때만 다시 읽는다.
    agg = st.get("agg") or load_sectors()
    use = defaultdict(int)
    dropped = []                       # 결함으로 저장하지 않은 업종
    ok = fail = 0
    for result in cl.messages.batches.results(st["batch_id"]):
        sec = cid_map.get(result.custom_id)
        if not sec:
            continue
        if result.result.type != "succeeded":
            fail += 1; dropped.append(sec)
            log(f"  · ⚠️ {sec} {result.result.type}"); continue
        _tally(use, result.result.message)
        try:
            text = g.extract_text(result.result.message)
            rep = g.parse_report(text)
            why = defects(rep, result.result.message, agg.get(sec))
            if why:
                fail += 1; dropped.append(sec)
                log(f"  · ⚠️ {sec} 불완전 — 건너뜀 ({'; '.join(why)})"); continue
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
            fail += 1; dropped.append(sec)
            log(f"  · ⚠️ {sec} 파싱 실패: {e}")
    # 걸러진 업종을 적어 둔다. 다음 실행이 이 목록만 다시 만든다.
    save_retry(dropped, as_of)
    _log_usage(use, st.get("model", MODEL))
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
