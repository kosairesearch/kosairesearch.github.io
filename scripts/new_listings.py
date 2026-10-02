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
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
KNOWN = ROOT / "data" / "known_tickers.json"
REPORTS_JS = ROOT / "data" / "reports-index.js"   # 분할 구조: 가벼운 인덱스(티커 목록·reportDate)
MAX_NEW = int(os.getenv("MAX_NEW_REPORTS", "20") or "20")


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
    # 전에 보았지만 아직 리포트가 하나도 없는 종목 — 지난 생성이 실패한 신규 상장
    retry = []
    if len(reported) >= len(cur_set) // 2:
        retry = [t for t in cur if t not in reported and t not in new]
    else:
        print(f"⚠️ 리포트 인덱스가 비정상({len(reported)}개) — 재시도 대상은 이번에 보지 않는다")
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
