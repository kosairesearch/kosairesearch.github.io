#!/usr/bin/env python3
"""
KOS ai — 신규 상장(또는 universe 신규 진입) 종목 감지.

data/known_tickers.json(이전에 본 종목)과 현재 data/stocks.js를 비교해
새로 생긴 종목을 찾아 GITHUB_OUTPUT(new_tickers, has_new)으로 내보낸다.
known 목록은 항상 현재 전체로 갱신한다. 첫 실행(known 없음)이면 초기화만 하고 신규 0.

리포트가 하나도 없는 종목도 다시 대상에 넣는다(재시도). known 은 리포트가 써졌는지와
상관없이 갱신되므로, 한 번 실패한 신규 상장은 다시 '신규' 로 잡히지 않는다. 2026년
8~9월 상장 2개사가 그렇게 몇 주씩 리포트 없이 남았다 — 0220W0 은 배치 결과가 불완전
(잘림 의심)해 버려졌고, 0010S0 은 배치가 80분 안에 끝나지 않았다.

리포트 폭주 방지: 리포트 없는 종목만, 최대 MAX_NEW_REPORTS(기본 20)개. 인덱스를 못
읽었거나 비정상으로 작으면(종목 수의 절반 미만) 재시도는 하지 않는다 — 그대로 두면
리포트가 있는 종목까지 '없음' 으로 보고 다시 쓴다. 같은 종목이 계속 실패하면 평일마다
배치 한 건 값으로 다시 쓴다 — 로그의 '재시도' 줄이 며칠째 같으면 사람이 본다.
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _reports_state as S  # noqa: E402  — 리포트 파일의 날짜(색인 동기화 전에도 '있음'으로 친다)

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
KNOWN = ROOT / "data" / "known_tickers.json"
REPORTS_JS = ROOT / "data" / "reports-index.js"   # 분할 구조: 가벼운 인덱스(티커 목록·reportDate)
MAX_NEW = int(os.getenv("MAX_NEW_REPORTS", "20") or "20")
# 생성기가 저장하지 못한 연속 횟수(generate_reports_batch.FAIL_JS) — FAIL_MAX 번째부터 재시도하지 않는다(2026-10-09 · 같은 이유로
# 계속 걸리는 종목을 평일 밤마다 다시 주문하지 않게). 다시 시도하려면 그 파일에서 종목을 지운다.
FAIL_JS = ROOT / "data" / "new_listing_fail.json"
FAIL_MAX = 3


def _load_obj(path):
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def main():
    stocks = _load_obj(STOCKS_JS)["stocks"]
    cur = [s["ticker"] for s in stocks]
    cur_set = set(cur)

    if not KNOWN.exists():
        KNOWN.write_text(json.dumps(sorted(cur_set), ensure_ascii=False), encoding="utf-8")
        print(f"known_tickers 초기화 ({len(cur_set)}개) — 신규 없음")
        new = []
    else:
        known = set(json.loads(KNOWN.read_text(encoding="utf-8")))
        new = [t for t in cur if t not in known]
        KNOWN.write_text(json.dumps(sorted(cur_set), ensure_ascii=False), encoding="utf-8")
        print(f"신규 진입 종목 {len(new)}개")

    # 종목명 매핑(로그용)
    nm = {s["ticker"]: s.get("name", "") for s in stocks}
    for t in new[:40]:
        print(f"  · {t} {nm.get(t,'')}")

    # 리포트 이미 있는 건 제외
    reported = set()
    if REPORTS_JS.exists():
        try:
            reported = set(_load_obj(REPORTS_JS).get("reports", {}).keys())
        except Exception:
            pass
    # 색인에 아직 오르지 않은 리포트 파일도 '있음'으로 친다. 배치 회수 · 백필은 파일만 커밋하고 색인은
    # 워치독 동기화 때 고쳐지므로, 색인만 보면 그 사이 같은 종목을 또 만든다(2026-10-03 공시 트리거가
    # 같은 원인으로 9개 종목을 두 번 주문했다).
    # 폭주 방지는 색인만으로 판단한다(파일로 채운 수를 넣으면 색인이 깨진 날에도 재시도가 열린다).
    idx_n = len(reported)
    on_file = {t for t in cur if t not in reported and S.file_report_date(t)}
    if on_file:
        print(f"색인 동기화 전 리포트 파일이 있는 종목 {len(on_file)}개 — 있는 것으로 친다: {','.join(sorted(on_file)[:20])}")
    reported |= on_file
    # 전에 보았지만 아직 리포트가 하나도 없는 종목 — 지난 생성이 실패한 신규 상장
    retry = []
    try:
        fails = json.loads(FAIL_JS.read_text(encoding="utf-8")) if FAIL_JS.exists() else {}
    except Exception:
        fails = {}
    stuck = {t for t, e in fails.items() if isinstance(e, dict) and int(e.get("n", 0)) >= FAIL_MAX}
    if idx_n >= len(cur_set) // 2:
        retry = [t for t in cur if t not in reported and t not in new and t not in stuck]
        held = [t for t in cur if t not in reported and t in stuck]
        if held:
            print(f"⛔ 저장하지 못한 횟수가 {FAIL_MAX}번인 종목 {len(held)}개는 다시 주문하지 않는다"
                  f"(data/new_listing_fail.json 에서 지우면 다시 시도): "
                  + ", ".join(f"{t} {nm.get(t, '')}({fails[t].get('why', '')})" for t in held[:20]))
    else:
        print(f"⚠️ 리포트 인덱스가 비정상({idx_n}개) — 재시도 대상은 이번에 보지 않는다")
    for t in retry[:40]:
        print(f"  · 재시도 {t} {nm.get(t,'')} (리포트 없음)")
    todo = ([t for t in new if t not in reported] + retry)[:MAX_NEW]

    out = ",".join(todo)
    gh = os.getenv("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a", encoding="utf-8") as f:
            f.write(f"new_tickers={out}\n")
            f.write(f"has_new={'1' if todo else ''}\n")
    print(f"\n리포트 생성 대상(신규·재시도, 최대 {MAX_NEW}): {len(todo)}개")
    print(f"new_tickers={out}")


if __name__ == "__main__":
    main()
