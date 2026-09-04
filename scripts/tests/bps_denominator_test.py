#!/usr/bin/env python3
"""생성기의 'BPS 분모 되묻기' 블록이 실제로 도는지, 맞는 답을 내는지 본다.

왜 따로 시험하나
----------------
생성기는 DART·KRX 를 부르고 요금이 나가서 여기서 통째로 돌릴 수가 없다.
그러면 고쳐 놓고도 '문법은 맞다' 까지밖에 확인이 안 된다. 실제로 이 작업에서
검사 세 개가 문법은 멀쩡한 채로 엉뚱한 것을 재고 있었다.

그래서 generate_reports_v2.py 원문에서 그 블록만 **글자 그대로 꺼내** 돌린다.
베껴 오면 진짜 파일이 바뀌어도 시험이 통과하므로 베끼지 않는다.

무엇으로 시험하나
-----------------
고치기 전에 실제로 틀렸던 종목들의 값을 그대로 넣는다. 태영건설은 자본을
가중평균(159,368,756)으로 나눠 BPS 3,673 이 나왔는데 KRX 공식값은 2,037
이었다. 발행총수(298,240,052)로 나누면 KRX 와 맞는다.

  실행:  python3 scripts/tests/bps_denominator_test.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = (ROOT / "scripts" / "generate_reports_v2.py").read_text(encoding="utf-8")

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


# ── 원문에서 블록을 꺼낸다 ──────────────────────────────────────────────
m = re.search(r"^(    # ── 분모가 맞는지 KRX 에게 물어본다 .*?)\n(?=\n    # ── 자본 정합성)",
              SRC, re.S | re.M)
if not m:
    print("생성기에서 분모 되묻기 블록을 못 찾았다 — 이름이 바뀌었거나 지워졌다")
    sys.exit(1)
BLOCK = "\n".join(ln[4:] if ln.startswith("    ") else ln for ln in m.group(1).split("\n"))
ok(True, "생성기 원문에서 블록을 꺼냈다", f"{len(BLOCK.splitlines())}줄")


def run_block(bps_q, bps_krx_ref, price, fy_eqo, eqo_q, total_sh, wavg, sh):
    """꺼낸 블록을 그 자리의 변수들만 채워 넣고 돌린다."""
    logs = []
    env = {
        "bps_q": bps_q, "bps_krx_ref": bps_krx_ref, "price": price,
        "fy_row": {"equity_owner": fy_eqo}, "eqo_q": eqo_q,
        "total_sh": total_sh, "wavg": wavg, "sh": sh,
        "bps_denom": wavg or total_sh,
        "pbr_q": round(price / bps_q, 4) if (bps_q and price) else None,
        "log": logs.append, "abs": abs, "int": int, "min": min, "round": round,
    }
    exec(compile(BLOCK, "<block>", "exec"), env)
    return env["bps_q"], env["bps_denom"], env["pbr_q"], logs


# ── ① 고치기 전 실제로 틀렸던 값들 ──────────────────────────────────────
# (종목, 옛 BPS, KRX 공식, 주가, 결산 지배지분, 분기말 지배지분, 발행총수, 가중평균, 시장)
CASES = [
    ("태영건설", 3673, 2037.0, 1000, 608_000_000_000, 585_400_000_000,
     298_240_052, 159_368_756, 297_590_078, "발행총수"),
    ("유수홀딩스", 23118, 12843.0, 12000, 334_400_000_000, 341_400_000_000,
     26_041_812, 14_765_686, 26_041_812, "발행총수"),
    ("가온전선", 32054, 16250.0, 158200, 480_000_000_000, 530_200_000_000,
     16_543_115, 16_542_203, 29_777_607, "시장주식수"),
]
print("\n══ ① 틀렸던 종목에서 분모를 바로잡는가 ══")
for name, old, krx, price, fy_eqo, eqo_q, tot, wavg, sh, want_den in CASES:
    new, den, pbr, logs = run_block(old, krx, price, fy_eqo, eqo_q, tot, wavg, sh)
    before, after = abs(old / krx - 1), abs(new / krx - 1)
    ok(new != old and after < before,
       f"{name}: BPS {old:,} → {new:,} (KRX {krx:,.0f})",
       f"KRX 대비 {before*100:.0f}% → {after*100:.0f}%")
    ok(pbr and abs(pbr * new - price) <= max(1, new * 0.0001),
       f"{name}: PBR 도 같이 고쳐져 PBR×BPS 가 주가와 맞는다", f"PBR {pbr}")
    ok(any("분모를 바꾼다" in s for s in logs), f"{name}: 무엇을 왜 바꿨는지 기록에 남는다")

# ── ② 멀쩡한 것은 건드리지 않는가 ───────────────────────────────────────
print("\n══ ② 멀쩡한 값은 그대로 두는가 ══")
SAFE = [
    # 삼성생명 — 우리가 맞고 KRX 가 낡았다. 분모는 KRX 와 같다(가중평균).
    # 여기서 건드리면 맞는 값을 망가뜨린다.
    ("삼성생명", 806537, 349293.0, 328500, 62_724_296_000_000, 144_840_000_000_000,
     200_000_000, 179_580_993, 200_000_000),
    # 분모가 다 같은 평범한 회사
    ("평범한 제조업", 10000, 10100.0, 20000, 100_000_000_000, 100_000_000_000,
     10_000_000, 10_000_000, 10_000_000),
    # KRX 값이 없으면 손대지 않는다
    ("KRX 값 없음", 10000, None, 20000, 100_000_000_000, 100_000_000_000,
     10_000_000, 5_000_000, 10_000_000),
]
for name, old, krx, price, fy_eqo, eqo_q, tot, wavg, sh in SAFE:
    new, den, pbr, logs = run_block(old, krx, price, fy_eqo, eqo_q, tot, wavg, sh)
    ok(new == old, f"{name}: BPS {old:,} 그대로", f"→ {new:,}")

# ── ③ 고쳐도 나아지지 않으면 안 바꾼다 ──────────────────────────────────
print("\n══ ③ 바꿔서 나빠지는 경우 ══")
# 분모를 바꾸면 KRX 에서 더 멀어지는 값
new, den, pbr, logs = run_block(
    bps_q=1000, bps_krx_ref=5000.0, price=10000,
    fy_eqo=100_000_000_000, eqo_q=100_000_000_000,
    total_sh=20_000_000, wavg=100_000_000, sh=20_000_000)
ok(new == 1000 or abs(new / 5000 - 1) < abs(1000 / 5000 - 1),
   "바꿔서 KRX 에 가까워질 때만 바꾼다", f"{1000:,} → {new:,} (KRX 5,000)")

# ── ④ 블록이 지워지면 시험이 실패해야 한다 ──────────────────────────────
print("\n══ ④ 이 시험이 껍데기가 아닌가 ══")
ok("bps_krx_ref" in BLOCK and "bps_denom" in BLOCK,
   "꺼낸 블록이 실제로 KRX 값과 분모를 쓴다")
ok("_implied" in BLOCK and "0.03" in BLOCK and "0.08" in BLOCK,
   "역산·허용폭 조건이 블록 안에 있다")
broken = BLOCK.replace("bps_q = _new", "pass")
try:
    env = {"bps_q": 3673, "bps_krx_ref": 2037.0, "price": 1000,
           "fy_row": {"equity_owner": 608_000_000_000}, "eqo_q": 585_400_000_000,
           "total_sh": 298_240_052, "wavg": 159_368_756, "sh": 297_590_078,
           "bps_denom": 159_368_756, "pbr_q": None, "log": lambda *_: None}
    exec(compile(broken, "<broken>", "exec"), env)
    ok(env["bps_q"] == 3673, "고치는 줄을 지우면 값이 안 바뀐다(시험이 그걸 잡는다)")
except Exception as e:
    ok(False, "변이 시험이 터졌다", str(e)[:60])

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
