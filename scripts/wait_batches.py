#!/usr/bin/env python3
"""회수 전에 진행 중인 배치가 끝나기를 기다린다(2026-11-18).

배치 회수(collect_batch.yml)는 30분 예약이지만 실제로는 몇 시간에 한 번만 돈다 — 11/17 마지막 예약 실행이 19:56(한국 시간)이었고,
01:50 에 공시 트리거가 맡긴 교정 배치(53편)는 그 뒤 몇 시간 동안 저장되지 않았다. 그래서 배치를 맡기고 끝나는 작업(공시 트리거 ·
리포트 v2 · 다음 교정 회차를 주문한 회수)이 회수를 곧바로 부르고(wait_min), 회수는 여기서 배치가 끝날 때까지 기다렸다 받는다.

기다리는 배치 — 보정을 기다리는 주문은 보정 배치, 아니면 본 배치. 끝나지 않은 채 한도가 다 되면 그대로 넘어간다(회수는 끝난
것만 받고, 남은 것은 다음 회수가 받는다). 상태를 받지 못한 배치는 기다리지 않는다(찾을 수 없는 배치는 회수가 판단한다).
조회만 하므로 돈이 들지 않는다.

  python scripts/wait_batches.py 2700     # 최대 45분(초)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _reports_state as S  # noqa: E402

STEP = 60   # 조회 간격(초)


def targets(pending=None):
    """기다릴 배치 ID(주문 순서 그대로 · 겹침 없이)."""
    out = []
    for _, st in (S.pending_batches() if pending is None else pending):
        rq = st.get("repair")
        bid = rq.get("batch_id") if isinstance(rq, dict) and rq.get("batch_id") else st.get("batch_id")
        if bid and bid not in out:
            out.append(bid)
    return out


def wait(cl, ids, limit_sec, step=STEP, now=time.monotonic, sleep=time.sleep, say=print):
    """ids 가 모두 끝나거나 limit_sec 가 지날 때까지 기다린다. 끝나지 않은 ID 를 돌려준다."""
    left, t0 = list(dict.fromkeys(ids)), now()
    while left:
        still = []
        for bid in left:
            try:
                status = cl.messages.batches.retrieve(bid).processing_status
            except Exception as e:      # 찾을 수 없음 · 일시 오류 — 기다리지 않는다
                say(f"- {bid} 상태를 받지 못함({type(e).__name__}) — 기다리지 않는다")
                continue
            if status != "ended":
                still.append(bid)
        left = still
        if not left or now() - t0 + step > limit_sec:
            break
        sleep(step)
    return left


def main(argv):
    try:
        limit = int(argv[1]) if len(argv) > 1 else 0
    except ValueError:
        limit = 0
    ids = targets()
    if not ids or limit <= 0:
        print(f"기다릴 배치 {len(ids)}개 · 한도 {limit}초 — 기다리지 않는다")
        return 0
    import anthropic
    t0 = time.monotonic()
    left = wait(anthropic.Anthropic(), ids, limit)
    print(f"기다린 배치 {len(ids)}개 · {int(time.monotonic() - t0)}초 · 끝나지 않은 배치 {len(left)}개"
          + (f"({', '.join(left)}) — 끝난 것만 받는다" if left else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
