#!/usr/bin/env python3
"""사업자 표시가 사이트 꼬리와 결제 메일에서 같은가 — 통신판매를 시작하면 더하는 표시까지.

왜 있나 (2026-11-25 · 유료화 2027-01-01 시행 준비)
  사업자 정보는 두 곳에서 나간다 — 사이트 꼬리(scripts/patch_biz_footer.py 의 BIZ · SELL)와 결제 · 약관 안내 메일의 꼬리
  (functions/index.js 의 BIZ_INFO · MAIL_ORDER_NO · BIZ_PHONE). 한쪽만 고치면 회원이 받은 계약 내용 안내 메일과 사이트의
  사업자 정보가 달라진다. 카카오 비즈니스 심사에서 가장 많은 반려 사유도 이 불일치다(patch_biz_footer 머리 주석).

  그리고 통신판매업 신고번호 · 대표전화는 아직 없다. 유료 시행일(comp_common.PAID_LIVE)에 값이 빈 채로 실사이트를 만들면
  전자상거래법 제10조 · 제13조가 요구하는 표시 없이 결제를 여는 것이 된다 — 그때는 생성기가 멈춰야 한다.

  ① 메일의 상호 · 대표 · 사업자등록번호 · 주소 · 이메일 = 꼬리의 BIZ (글자 하나까지)
  ② 메일의 통신판매업 신고번호 · 유사투자자문업 신고 · 대표전화 = 꼬리의 SELL
  ③ 실사이트: PAID_LIVE 가 꺼져 있으면 통신판매 표시가 없다 · 켰는데 값이 비면 멈춘다 · 값이 있으면 싣는다
  ④ 스테이징 꼬리(새 디자인 · 첫 화면)에 세 줄이 있고, 영어 사전에 그 줄이 있다

  python3 scripts/tests/biz_sell_test.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import patch_biz_footer as B  # noqa: E402
import comp_common as C  # noqa: E402

fails = []
passes = 0


def ok(cond, name, extra=""):
    global passes
    if cond:
        passes += 1
    else:
        fails.append(name + (f"\n      {extra}" if extra else ""))


FN = (ROOT / "functions/index.js").read_text(encoding="utf-8")


def js_const(name):
    m = re.search(rf'^const {name} = "([^"]*)";', FN, re.M)
    return m.group(1) if m else None


def js_info(key):
    """BIZ_INFO 의 한 칸 — 글자 하나 또는 [한국어, 영어] 의 한국어."""
    m = re.search(r"const BIZ_INFO = \{(.*?)\n\};", FN, re.S)
    if not m:
        return None
    k = re.search(rf'\b{key}:\s*(\[\s*"([^"]*)"|"([^"]*)")', m.group(1))
    if not k:
        return None
    return k.group(2) if k.group(2) is not None else k.group(3)


biz = {label: ko for label, ko, _ in B.BIZ}
sell = {label: v for label, v, _ in B.SELL}

# ① 메일의 사업자 정보 = 꼬리의 BIZ
ok(js_info("name") is not None, "functions/index.js 에 BIZ_INFO 가 있다")
for key, label in (("name", "상호"), ("ceo", "대표"), ("regNo", "사업자등록번호"), ("address", "주소"), ("email", "이메일")):
    got = js_info(key)
    ok(got == biz[label], f"메일 꼬리의 {label}가 사이트 꼬리와 같다",
       f'사이트 "{biz[label]}" · 메일 "{got}" — scripts/patch_biz_footer.py 의 BIZ 가 원본이다. functions/index.js 의 BIZ_INFO 를 같게 고쳐라')

# ② 통신판매업 신고번호 · 대표전화 = SELL
for const, label in (("MAIL_ORDER_NO", "통신판매업 신고"), ("ADVISORY_NO", "유사투자자문업 신고"), ("BIZ_PHONE", "대표전화")):
    got = js_const(const)
    ok(got is not None, f"functions/index.js 에 {const} 가 있다")
    ok(got == sell.get(label), f"메일 꼬리의 {label}가 사이트 꼬리(SELL)와 같다",
       f'사이트 "{sell.get(label)}" · 메일 "{got}" — 두 곳을 같은 값으로 채워라')
ok(sell.get("호스팅서비스"), "호스팅서비스 값이 있다(전자상거래법 시행령 제11조의4)")

# ③ 실사이트 스위치
saved = (C.PAID_LIVE, [list(x) for x in B.SELL])
try:
    C.PAID_LIVE = False
    ok(C.sell_spans("live") == "", "PAID_LIVE 가 꺼져 있으면 실사이트 꼬리에 통신판매 표시가 없다")
    C.PAID_LIVE = True
    B.SELL[:] = [(k, "", en) if k != "호스팅서비스" else (k, v, en) for k, v, en in B.SELL]
    try:
        C.sell_spans("live")
        ok(False, "PAID_LIVE 를 켰는데 신고번호 · 전화번호가 비어 있으면 실사이트 생성기가 멈춘다")
    except SystemExit as e:
        ok("통신판매업 신고" in str(e), "멈출 때 무엇을 채워야 하는지 알려 준다", str(e))
    B.SELL[:] = [(k, v or "시험값-1234", en) for k, v, en in B.SELL]
    spans = C.sell_spans("live")
    ok(spans.count("<span>") == len(B.SELL) and "시험값-1234" in spans and "기재)" not in spans,
       "값을 채우고 PAID_LIVE 를 켜면 실사이트 꼬리에 통신판매 표시를 모두 싣는다", spans)
finally:
    C.PAID_LIVE = saved[0]
    B.SELL[:] = [tuple(x) for x in saved[1]]

# ④ 스테이징 꼬리 · 첫 화면 · 영어 사전
for page in ("staging/Home.html", "staging/stock.html", "staging/checkout.html", "staging/index.html"):
    html = (ROOT / page).read_text(encoding="utf-8")
    for label, v, en in B.SELL:
        text = f"{label} {v or C._sell_tbd(label)[0]}"
        ok(f"<span>{text}</span>" in html, f"{page} 꼬리에 '{text}' 가 있다")
        ok(f'"{text}":"{en} {v or C._sell_tbd(label)[1]}"' in html, f"{page} 영어 사전에 '{text}' 가 있다")
live_home = (ROOT / "Home.html").read_text(encoding="utf-8")
if not C.PAID_LIVE:
    ok("호스팅서비스" not in live_home, "PAID_LIVE 전에는 실사이트 꼬리에 통신판매 표시가 없다")

print(f"통과 {passes} · 실패 {len(fails)}")
for f in fails:
    print("  FAIL " + f)
sys.exit(1 if fails else 0)
