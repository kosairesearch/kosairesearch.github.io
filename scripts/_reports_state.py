#!/usr/bin/env python3
"""리포트 v2 파이프라인의 '상태' 를 한 곳에서 읽고 쓴다 — 표준 라이브러리만.

왜 따로 두나
------------
같은 판단("이 종목은 리포트가 있는가 · 다시 만들어야 하는가 · 지금 주문이
들어가 있는가")을 생성기(generate_reports_v2.py)와 워치독 보조 스크립트
(_fill_remaining.py · _missing_tickers.py)가 각자 따로 하고 있었다. 한쪽만
고치면 워치독은 '남았다' 고 하고 생성기는 '할 게 없다' 고 하는 식으로 어긋난다.
워치독은 pip 없이 돌므로 여기는 anthropic·pandas 를 들여오지 않는다.

상태의 종류 — 전부 종목별 마커 파일이다(병렬 run 이 서로 다른 파일만 건드려
git 충돌이 없다).

  data/reports_v2/<tk>.json        리포트 본체
  data/reports_v2_skip/<tk>        생성 불가(DART 에 재무제표가 없다). 내용은 기록한 날짜.
  data/reports_v2_hold/<tk>        숫자가 항등식에 걸려 글을 쓰지 않았다. 내용은 사유.
  data/reports_v2_fail/<tk>        배치 결과가 깨진 횟수. FAIL_LIMIT 이상이면 자동 백필에서 뺀다.
  data/batches_v2/<batch_id>.json  주문 하나의 상태. collected/abandoned 가 없으면 '진행 중'.
  data/reports_v2_refresh          갱신 기준일(YYYY-MM-DD). 이 날짜 이전 리포트는 '없는 것' 으로 본다.
  data/reports_paused              있으면 돈이 드는 모드를 전부 멈춘다.
  data/dart_quota_exhausted        DART 하루 한도를 넘긴 날(KST). 그날은 재가동하지 않는다.
"""
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_DIR = DATA / "reports_v2"
SKIP_DIR = DATA / "reports_v2_skip"
SKIP_LEGACY = DATA / "reports_v2_skip.txt"
HOLD_DIR = DATA / "reports_v2_hold"
FAIL_DIR = DATA / "reports_v2_fail"
BATCH_DIR = DATA / "batches_v2"
LEGACY_STATE = DATA / "batch_state_v2.json"
REFRESH_FILE = DATA / "reports_v2_refresh"
PAUSE_FILE = DATA / "reports_paused"
QUOTA_FILE = DATA / "dart_quota_exhausted"
STOCKS_JS = DATA / "stocks.js"

FAIL_LIMIT = 3          # 이만큼 연속으로 깨지면 자동 백필에서 뺀다(사람이 본다)
FAIL_RESET_DAYS = 14    # 마지막 실패가 이보다 오래됐으면 횟수를 0 으로 본다 — 일시 장애로 영영 묻히지 않게
SKIP_RETRY_DAYS = 30    # skip 마커가 이보다 오래됐으면 백필이 한 번 더 시도한다

TICKER = re.compile(r"[0-9][0-9A-Za-z]{5}")
KST = datetime.timezone(datetime.timedelta(hours=9))


def today_kst():
    return datetime.datetime.now(KST).date()


# ── 마커 디렉터리 공통 ─────────────────────────────────────────────────
def _names(d):
    if not d.exists():
        return set()
    return {p.name for p in d.iterdir() if p.is_file() and not p.name.startswith(".")}


def _read(d, tk):
    p = d / tk
    try:
        return p.read_text(encoding="utf-8").strip() if p.exists() else None
    except Exception:
        return None


def _write(d, tk, text):
    d.mkdir(parents=True, exist_ok=True)
    (d / tk).write_text(text, encoding="utf-8")


def _remove(d, tk):
    p = d / tk
    if p.exists():
        p.unlink()


# ── skip: DART 에 재무제표가 없어 만들 수 없는 종목 ─────────────────────
def load_skip():
    out = _names(SKIP_DIR)
    if SKIP_LEGACY.exists():
        out |= {ln.strip() for ln in SKIP_LEGACY.read_text(encoding="utf-8").splitlines() if ln.strip()}
    return out


def skip_date(tk):
    """마커에 적힌 날짜. 옛 마커(빈 파일)와 구버전 목록은 None — 언제 적었는지 모른다."""
    s = _read(SKIP_DIR, tk)
    try:
        return datetime.date.fromisoformat(s) if s else None
    except ValueError:
        return None


def add_skip(tickers, day=None):
    day = (day or today_kst()).isoformat()
    for t in tickers or ():
        _write(SKIP_DIR, t, day)


def remove_skip(tk):
    _remove(SKIP_DIR, tk)


def skip_retryable(tk, day=None):
    """skip 된 지 SKIP_RETRY_DAYS 가 지났거나 언제 적었는지 모르면 다시 시도해 볼 만하다.
    신규 상장·DART 지연으로 잠시 없던 재무제표는 나중에 생긴다."""
    d = skip_date(tk)
    if d is None:
        return True
    return ((day or today_kst()) - d).days >= SKIP_RETRY_DAYS


# ── hold: 숫자가 항등식에 걸려 글을 쓰지 않은 종목 ──────────────────────
def load_hold():
    return {tk: (_read(HOLD_DIR, tk) or "") for tk in _names(HOLD_DIR)}


def add_hold(tk, reason):
    _write(HOLD_DIR, tk, f"{today_kst().isoformat()} {reason}".strip())


def clear_hold(tk):
    _remove(HOLD_DIR, tk)


# ── fail: 배치 결과·정량 수집이 깨진 횟수 ────────────────────────────────
def fail_count(tk, day=None):
    """마커 내용은 '횟수 날짜'. 마지막 실패가 FAIL_RESET_DAYS 보다 오래됐으면 0 —
    네트워크 같은 일시 장애 세 번으로 종목이 영영 묻히면 안 된다. 2주 뒤 다시 본다."""
    s = _read(FAIL_DIR, tk)
    if not s:
        return 0
    parts = s.split()
    try:
        n = int(parts[0])
    except ValueError:
        return 0
    if len(parts) > 1:
        try:
            if ((day or today_kst()) - datetime.date.fromisoformat(parts[1][:10])).days > FAIL_RESET_DAYS:
                return 0
        except ValueError:
            pass
    return n


def bump_fail(tk):
    n = fail_count(tk) + 1
    _write(FAIL_DIR, tk, f"{n} {today_kst().isoformat()}")
    return n


def clear_fail(tk):
    _remove(FAIL_DIR, tk)


def load_failed_out():
    """FAIL_LIMIT 이상 깨진 종목 — 자동 백필이 더 돈을 쓰지 않는다."""
    return {tk for tk in _names(FAIL_DIR) if fail_count(tk) >= FAIL_LIMIT}


# ── universe · 리포트 보유 · 갱신 기준일 ────────────────────────────────
def load_universe():
    """data/stocks.js → {ticker: stock}. 못 읽으면 빈 dict(호출자가 안전하게 건너뛴다)."""
    try:
        raw = STOCKS_JS.read_text(encoding="utf-8")
        obj = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        return {s["ticker"]: s for s in obj.get("stocks", [])}
    except Exception:
        return {}


def refresh_date():
    """data/reports_v2_refresh 에 적힌 기준일. 없거나 못 읽으면 None.
    '#' 로 시작하는 줄은 설명이다."""
    if not REFRESH_FILE.exists():
        return None
    for ln in REFRESH_FILE.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            return datetime.date.fromisoformat(ln[:10]).isoformat()
        except ValueError:
            return None
    return None


def report_date(tk):
    p = OUT_DIR / f"{tk}.json"
    if not p.exists():
        return None
    try:
        return str(json.loads(p.read_text(encoding="utf-8")).get("reportDate") or "")[:10] or None
    except Exception:
        return None


def has_current_report(tk, refresh=None):
    """리포트가 있고, 갱신 기준일이 있으면 그 날 이후에 만든 것인가."""
    p = OUT_DIR / f"{tk}.json"
    if not p.exists():
        return False
    if not refresh:
        return True
    d = report_date(tk)
    return bool(d and d >= refresh)


# ── 배치(주문) 상태 ──────────────────────────────────────────────────────
def batch_path(batch_id):
    return BATCH_DIR / f"{batch_id}.json"


def load_batches():
    """모든 배치 상태 [(path, state)]. 구버전 단일 파일도 함께 읽는다."""
    out = []
    if BATCH_DIR.exists():
        for p in sorted(BATCH_DIR.glob("*.json")):
            try:
                st = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(st, dict) and st.get("batch_id"):
                out.append((p, st))
    if LEGACY_STATE.exists():
        try:
            st = json.loads(LEGACY_STATE.read_text(encoding="utf-8"))
            if isinstance(st, dict) and st.get("batch_id") and not any(
                    s.get("batch_id") == st["batch_id"] for _, s in out):
                out.append((LEGACY_STATE, st))
        except Exception:
            pass
    return out


def is_pending(state):
    return bool(state.get("batch_id")) and not state.get("collected") and not state.get("abandoned")


def pending_batches():
    return [(p, st) for p, st in load_batches() if is_pending(st)]


def batch_tickers(state):
    t = state.get("tickers")
    if isinstance(t, list):
        return set(t)
    return set((state.get("models") or {}).keys())


def inflight_tickers():
    """주문은 들어갔는데 아직 결과를 받지 않은 종목. 다시 주문하면 돈만 두 번 나간다."""
    out = set()
    for _, st in pending_batches():
        out |= batch_tickers(st)
    return out


# ── 자동 백필 대상 판정 ─────────────────────────────────────────────────
def wanted(tk, refresh, skip, hold, failed_out, inflight):
    """자동 백필(fill)이 이 종목을 지금 만들어야 하는가."""
    if tk in skip or tk in hold or tk in failed_out or tk in inflight:
        return False
    return not has_current_report(tk, refresh)


def fill_context(allow_inflight=False):
    return {
        "refresh": refresh_date(),
        "skip": load_skip(),
        "hold": set(load_hold()),
        "failed_out": load_failed_out(),
        "inflight": set() if allow_inflight else inflight_tickers(),
    }


def remaining_tickers(stocks_sorted, fill_to, ctx=None):
    """시총 순위 상위 fill_to 중 아직 만들어야 할 종목 티커(순위 순)."""
    ctx = ctx or fill_context()
    return [s["ticker"] for s in stocks_sorted[:fill_to]
            if wanted(s["ticker"], ctx["refresh"], ctx["skip"], ctx["hold"],
                      ctx["failed_out"], ctx["inflight"])]


# ── DART 하루 한도 ───────────────────────────────────────────────────────
def mark_quota_exhausted(day=None):
    QUOTA_FILE.write_text((day or today_kst()).isoformat() + "\n", encoding="utf-8")


def quota_exhausted_today(day=None):
    if not QUOTA_FILE.exists():
        return False
    try:
        return QUOTA_FILE.read_text(encoding="utf-8").strip()[:10] == (day or today_kst()).isoformat()
    except Exception:
        return False
