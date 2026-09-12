#!/usr/bin/env python3
"""rebase 가 valuation.js 에서 충돌했을 때 종목 단위로 합친다.

왜 필요한가
-----------
data/valuation.js 는 종목 2,700개가 든 JSON 을 매번 통째로 다시 쓰는
파일이다. 수집 잡이 둘 연달아 생기면(예약 실행이 줄 서 있는 동안 다른
실행이 먼저 push, 또는 self-chain) 뒤 실행은 낡은 기준에서 같은 파일을
다시 쓴 상태가 된다. 텍스트 단위 rebase 는 "통째로 다시 쓴 것" 두 개를
합치지 못한다. 결정적 충돌이라 25번 재시도해도 25번 다 똑같이 실패한다.
실제로 2026-09-12 12:11 실행이 그렇게 죽었다.

    CONFLICT (content): Merge conflict in data/valuation.js

그런데 내용은 종목별로 독립된 사전이다. 텍스트로는 못 합쳐도 JSON
으로는 합쳐진다. 그래서 충돌한 두 쪽을 읽어 종목 단위로 포갠다.

어느 쪽이 이기나
----------------
이번 실행이 방금 수집한 값이 이긴다. 상대가 넣은 종목은 그대로 둔다.
종목끼리는 서로 영향을 주지 않으므로 이렇게 포개도 어긋나지 않는다.

rebase 중의 :2 와 :3
--------------------
rebase 는 merge 와 반대다. 기준(origin/main)이 :2 이고, 지금 얹으려는
우리 커밋이 :3 이다. 헷갈리기 쉬워 이름을 그대로 적어 둔다.

안전장치
--------
조금이라도 이상하면 아무것도 쓰지 않고 1 을 돌려준다. 부르는 쪽
(워크플로)은 그때 예전처럼 rebase --abort 로 물러난다. 즉 이 스크립트가
실패해도 고치기 전과 똑같이 동작할 뿐, 더 나빠지지 않는다.

    python3 scripts/merge_valuation.py            # rebase 충돌 상태에서
    python3 scripts/merge_valuation.py A.js B.js  # 파일 둘을 직접 (시험용)
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "data" / "valuation.js"
HEAD = "// KOS ai — 전 종목 밸류에이션(자동 생성). PER·PBR·배당은 화면에서 주가로 즉석 계산.\n"
BODY = re.compile(r"window\.KOS_VALUATION\s*=\s*(\{.*)", re.S)


def parse(text):
    """valuation.js 한 쪽을 읽는다. 모양이 예상과 다르면 None."""
    m = BODY.search(text or "")
    if not m:
        return None
    try:
        obj = json.loads(m.group(1).rstrip().rstrip(";"))
    except Exception:
        return None
    if not isinstance(obj, dict) or not isinstance(obj.get("stocks"), dict):
        return None
    return obj


def merge(onto, ours):
    """기준(onto) 위에 이번 실행이 수집한 것(ours)을 종목 단위로 포갠다."""
    stocks = dict(onto["stocks"])
    stocks.update(ours["stocks"])
    # asOf·dataDate 는 늦은 쪽을 쓴다. count 는 합친 뒤 다시 센다.
    out = dict(onto)
    out["stocks"] = stocks
    for k in ("asOf", "dataDate"):
        a, b = onto.get(k) or "", ours.get(k) or ""
        out[k] = b if b > a else a
    out["count"] = len(stocks)
    return out


def render(obj):
    return HEAD + "window.KOS_VALUATION = " + json.dumps(obj, ensure_ascii=False) + ";\n"


def stage(n):
    """rebase 가 남겨 둔 충돌 단계를 읽는다. :2=기준, :3=우리 커밋."""
    r = subprocess.run(["git", "show", f":{n}:data/valuation.js"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def main(argv):
    if len(argv) == 2:                      # 시험용 — 파일 둘을 직접
        onto_txt = Path(argv[0]).read_text(encoding="utf-8")
        ours_txt = Path(argv[1]).read_text(encoding="utf-8")
    elif not argv:                          # 실제 — rebase 충돌 상태에서
        onto_txt, ours_txt = stage(2), stage(3)
    else:
        print("인자는 없거나 두 개여야 한다", file=sys.stderr)
        return 1

    onto, ours = parse(onto_txt), parse(ours_txt)
    if onto is None or ours is None:
        print("합칠 수 없다 — 두 쪽 중 하나를 못 읽었다", file=sys.stderr)
        return 1

    out = merge(onto, ours)
    # 합친 결과가 어느 한쪽보다 적으면 뭔가 잘못된 것이다. 쓰지 않는다.
    if len(out["stocks"]) < max(len(onto["stocks"]), len(ours["stocks"])):
        print("합친 결과가 원본보다 적다 — 쓰지 않는다", file=sys.stderr)
        return 1

    text = render(out)
    # 쓰기 전에 되읽어 본다. 여기서 안 읽히면 화면이 깨지므로 쓰지 않는다.
    back = parse(text)
    if back is None or len(back["stocks"]) != len(out["stocks"]):
        print("합친 결과를 다시 못 읽었다 — 쓰지 않는다", file=sys.stderr)
        return 1
    TARGET.write_text(text, encoding="utf-8")
    print(f"valuation.js 합침 — 기준 {len(onto['stocks']):,} + 이번 "
          f"{len(ours['stocks']):,} → {len(out['stocks']):,}종목")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
