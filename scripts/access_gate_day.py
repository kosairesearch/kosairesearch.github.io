#!/usr/bin/env python3
"""리포트 열람 방법 변경 시행일(2026-12-03) 정리 — 시행일에 한 번 돌린다(CLAUDE.md '리포트 열람 방법 변경').

    python3 scripts/access_gate_day.py      # 고친다 — 이미 고쳤으면 아무것도 하지 않고 알린다
    python3 scripts/build_live.py && bash scripts/check_all.sh

잠금 자체는 시행 시각(comp_common.ACCESS_GATE_AT)에 브라우저 · 미리 그리기가 스스로 켠다. 이 도구는 저절로 되지 않는 것을 고친다.
  ① 개인정보 처리방침(현행판 privacy.src.html) — 공고일 · 시행일 줄, 머리말(이번 개정), '2. 처리하는 개인정보의 항목' 첫 문장
     (공지 Notice-access.html 4항의 '변경 후' 그대로)과 그 영어(legal.json · live.json)
  ② 유료판 처리방침 머리 주석의 기준 판 값 — 유료판(2027-01-01 시행)의 2항 첫 문장은 그대로 둔다: 유료판은 그 구간을 멤버십 회원에게
     주므로 '로그인한 회원' 괄호가 맞지 않고, 원래 문장('대부분의 기능을 회원가입 없이')은 그때도 맞다
  ③ comp_common.ACCESS_GATE = True — 시행 전 안내 한 줄과 시각 판단 코드를 걷고, 실사이트 가입 화면 소개 · 회사 소개 문장이 리포트
     열람을 앞세운다(comp_common.SIGNUP_SUB_GATE · build_about_comp.ACCESS_GATED)
쓴 뒤에는 이 파일을 지우고 CLAUDE.md 의 '시행일에 할 일'을 '했다'로 고친다. 지키는 검사: same-legal.test(유료판 기준 판 · 화면 = 원문) ·
english.test · access-gate.test(정리 뒤에는 시계와 관계없이 잠근다).
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'scripts' / 'content'

UPD_OLD = '공고일 2026년 10월 4일 · 시행일 2026년 10월 11일 · 최초 시행일 2026년 6월 6일'
UPD_NEW = '공고일 2026년 11월 26일 · 시행일 2026년 12월 3일 · 최초 시행일 2026년 6월 6일'
INTRO_OLD_HEAD = '이번 개정은 소셜 로그인 시 처리하는 회원 식별번호와'
INTRO_NEW = ("이번 개정은 2026년 12월 3일부터 리포트의 실적 분석부터 종합 의견까지를 로그인한 회원에게 제공함에 따라 "
             "'2. 처리하는 개인정보의 항목'의 첫 문장을 고치는 내용입니다. 새로 수집하는 개인정보는 없으며, 이용자에게 불리한 변경 사항은 포함되어 있지 않습니다.")
SENT_OLD = '서비스는 회원가입 없이도 대부분의 기능을 이용할 수 있으며, 다음의 경우에 한해 개인정보를 처리합니다.'
SENT_NEW = '서비스는 회원가입 없이도 대부분의 기능을 이용할 수 있으며(리포트의 실적 분석부터 종합 의견까지는 로그인한 회원에게 제공합니다), 다음의 경우에 한해 개인정보를 처리합니다.'
EN = {
    UPD_NEW: 'Announced November 26, 2026 · Effective December 3, 2026 · Originally effective June 6, 2026',
    INTRO_NEW: ("This revision amends the first sentence of Section 2, 'Items of Personal Information Processed', as the sections of each report "
                "from Earnings analysis through Overall view become available to signed-in members from December 3, 2026. No new personal "
                "information is collected, and the revision contains no changes unfavorable to users."),
    SENT_NEW: ('Most features are available without an account (the sections of each report from Earnings analysis through Overall view are '
               'available to signed-in members); personal information is processed only in the following cases.'),
}


def sha16(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main():
    cc = ROOT / 'scripts' / 'comp_common.py'
    ccs = cc.read_text(encoding='utf-8')
    if re.search(r'^ACCESS_GATE = True$', ccs, re.M):
        print('이미 정리했다(ACCESS_GATE = True) — 아무것도 하지 않는다')
        return 0
    # ① 현행 처리방침
    pv = CONTENT / 'privacy.src.html'
    s = pv.read_text(encoding='utf-8')
    for old in (UPD_OLD, INTRO_OLD_HEAD, SENT_OLD):
        if s.count(old) != 1:
            raise SystemExit(f'❌ 처리방침에서 바꿀 글을 찾지 못했다(이미 고쳤거나 원문이 바뀌었다): {old[:40]}')
    s = s.replace(UPD_OLD, UPD_NEW).replace(SENT_OLD, SENT_NEW)
    s = re.sub(r'<p>이번 개정은 소셜 로그인 시 처리하는 회원 식별번호와[^<]*</p>', '<p>' + INTRO_NEW + '</p>', s, count=1)
    pv.write_text(s, encoding='utf-8')
    # 영어 — 공고일 줄 · 머리말은 legal.json(옛 값을 바꾼다), 2항 첫 문장은 live.json 에 더한다(유료판이 옛 문장을 그대로 쓴다)
    lg = ROOT / 'scripts' / 'i18n' / 'legal.json'
    d = json.loads(lg.read_text(encoding='utf-8'))
    old_intro = [k for k in d if k.startswith(INTRO_OLD_HEAD)]
    for k in [UPD_OLD] + old_intro:
        d.pop(k, None)
    d[UPD_NEW] = EN[UPD_NEW]
    d[INTRO_NEW] = EN[INTRO_NEW]
    lg.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    lv = ROOT / 'scripts' / 'i18n' / 'live.json'
    d = json.loads(lv.read_text(encoding='utf-8'))
    d[SENT_NEW] = EN[SENT_NEW]
    lv.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    # ② 유료판 처리방침 머리 주석의 기준 판
    pp = CONTENT / 'privacy.paid.src.html'
    ps = pp.read_text(encoding='utf-8')
    ps, n = re.subn(r'(sha256 앞 16자리 )[0-9a-f]{16}', lambda m: m.group(1) + sha16(pv), ps, count=1)
    tail = '이 판도 함께 고쳤는지 묻는다. -->'
    if n != 1 or ps.count(tail) != 1:
        raise SystemExit('❌ 유료판 처리방침에서 기준 판 주석을 찾지 못했다')
    ps = ps.replace(tail, "이 판도 함께 고쳤는지 묻는다. 2026-12-03 현행판 개정(2항 첫 문장의 괄호 '로그인한 회원')은 유료판에 옮기지 않았다 —\n"
                          "     유료판은 그 구간을 멤버십 회원에게 주고, 원래 문장('대부분의 기능을 회원가입 없이')은 그때도 맞다. -->", 1)
    pp.write_text(ps, encoding='utf-8')
    # ③ 스위치
    ccs, n = re.subn(r'^ACCESS_GATE = False$', 'ACCESS_GATE = True', ccs, count=1, flags=re.M)
    if n != 1:
        raise SystemExit('❌ comp_common.ACCESS_GATE 를 찾지 못했다')
    cc.write_text(ccs, encoding='utf-8')
    print('✅ 처리방침(현행판 · 영어 · 유료판 기준 판) · ACCESS_GATE = True — 이제 python3 scripts/build_live.py 와 전체 검사')
    return 0


if __name__ == '__main__':
    sys.exit(main())
