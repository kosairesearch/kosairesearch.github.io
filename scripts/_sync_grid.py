#!/usr/bin/env python3
"""상단 그리드(data/valuation.js)의 숫자를 reports_v2/*.json 과 맞춘다.

그리드는 리포트의 quant 를 그대로 옮겨 쓴다 — 두 벌로 계산하면 언젠가 갈라진다.
그 동기화는 원래 collect_valuation 이 하는데, 두 시간에 한 번 돌고 DART 키가
있어야 시작한다. 전 종목을 다시 만드는 동안에는 몇 분마다 수백 개가 새로 쌓이므로
그 두 시간 동안 화면 그리드와 리포트 본문의 EPS·BPS 가 서로 다르게 보인다
(갱신 직후 실제로 20종목이 그랬다 — 한화리츠 리포트 81 vs 그리드 80).

파일만 읽는 일이라 값이 들지 않으므로, 워치독이 인덱스를 재생성할 때 같이 맞춘다.
표준 라이브러리만 사용(워치독에서 pip 없이 실행).

숫자가 그대로인 항목은 손대지 않는다 — 날짜만 바뀐 2,500줄짜리 커밋을 30분마다
남기지 않기 위해서다."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

import _reports_state as S

OUT = ROOT / "data" / "valuation.js"
HEAD = ("// KOS ai — 전 종목 밸류에이션(자동 생성). "
        "PER·PBR·배당은 화면에서 주가로 즉석 계산.\n")


def load():
    """(payload, stocks) 또는 (None, None) — 못 읽으면 아무것도 하지 않는다."""
    if not OUT.exists():
        return None, None
    try:
        m = re.search(r"window\.KOS_VALUATION\s*=\s*(\{.*)", OUT.read_text(encoding="utf-8"), re.S)
        payload = json.loads(m.group(1).rstrip().rstrip(";"))
        stocks = payload.get("stocks")
        return (payload, stocks) if isinstance(stocks, dict) else (None, None)
    except Exception as e:
        print(f"- valuation.js 를 읽지 못했다({type(e).__name__}: {e}) — 건너뜀")
        return None, None


def main():
    payload, stocks = load()
    if stocks is None:
        return
    today = S.today_kst().isoformat()
    changed = []
    for p in sorted(S.OUT_DIR.glob("*.json")):
        tk = p.stem
        try:
            q = json.loads(p.read_text(encoding="utf-8")).get("quant") or {}
        except Exception:
            continue
        v = S.grid_summary(q.get("valuation") or {}, q.get("annual") or [])
        old = stocks.get(tk) or {}
        if {k: x for k, x in old.items() if k not in ("_v", "_d")} == v:
            continue                      # 숫자가 같다 — 날짜만 바꾸지 않는다
        v["_v"], v["_d"] = S.GRID_VERSION, today
        stocks[tk] = v
        changed.append(tk)
    if not changed:
        print("- 그리드 동기화: 바뀐 값 없음")
        return
    payload["asOf"] = S.now_kst().strftime("%Y-%m-%d %H:%M")
    payload["count"] = len(stocks)
    OUT.write_text(HEAD + "window.KOS_VALUATION = " + json.dumps(payload, ensure_ascii=False) + ";\n",
                   encoding="utf-8")
    print(f"- 그리드 동기화 {len(changed)}건 — 그리드=리포트 (예: {', '.join(changed[:5])})")


if __name__ == "__main__":
    main()
