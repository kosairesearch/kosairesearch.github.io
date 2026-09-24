#!/usr/bin/env python3
"""푸터의 '면책 조항' 상자를 뺀다 — 실사이트·스테이징 모두. 리포트 본문의 한 줄과 약관 제15조는 그대로.

    python3 scripts/strip_footer_disclaimer.py [--check]

왜 뺐나(2026-09-24, 사장 결정). 무료로 주는 지금은 어떤 법도 푸터의 면책 문구를 요구하지 않는다.
  · 자본시장법 제101조 유사투자자문업은 '대가'를 받아야 신고 대상이라 무료 서비스는 해당 없다.
  · 인공지능기본법 제31조 투명성 의무는 AI 를 도구로 써서 자기 콘텐츠를 만드는 쪽에는 없고(과기정통부
    투명성 확보 가이드라인 2026-01), 있다고 보더라도 이용약관 고지(약관 제15조)와 화면 안 표시로 충분하다.
  · 약관 제15조는 회원에게만 효력이 있으므로, 회원 아닌 방문자에게 '참고 자료이지 권유가 아니다'를 알리는
    자리는 리포트 본문 끝의 한 줄(stock.html #disclaimer)이다. 그래서 그 줄만 남겼다.

⚠️ 유료화하면 다시 넣어야 한다. 유사투자자문업 신고 뒤에는 "금융투자업자가 아닌 유사투자자문업자 · 개별
   상담 불가 · 원금 손실 가능" 문구를 광고·화면에 표시해야 한다(2024-08-14 개정 자본시장법). CLAUDE.md 의
   '유료화를 시작할 때' 절에 적어 두었다.

무엇을 하나. 표준 푸터의 <div class="disclaimer"><b>면책 조항</b> …</div>(한 줄형·여러 줄형)와, 그 문장의
번역 사전 항목을 지운다. <div class="disclaimer" id="disclaimer"> 는 리포트 본문이라 건드리지 않는다.
--check 는 바꾸지 않고 상자가 남은 페이지가 있는지만 본다(check_all.sh 가 돌린다).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONE_RE = re.compile(r'^[ \t]*<div class="disclaimer"><b>면책 조항</b>[^\n]*</div>\n', re.M)
MULTI_RE = re.compile(r'^[ \t]*<div class="disclaimer">\n[ \t]*<b>면책 조항</b>[^\n]*\n[ \t]*</div>\n', re.M)
KEY_RE = re.compile(r'^[ \t]*"· 본 사이트의 모든 AI 분석·리포트는 투자 참고용 정보이며[^\n]*":\n[ \t]*"[^\n]*",\n', re.M)
LABEL_RE = re.compile(r'^[ \t]*"면책 조항":"Disclaimer",\n', re.M)


def strip(s):
    out = ONE_RE.sub('', s)
    out = MULTI_RE.sub('', out)
    out = KEY_RE.sub('', out)
    if '면책 조항' not in LABEL_RE.sub('', out):      # 다른 데서 안 쓰면 라벨 번역도 지운다
        out = LABEL_RE.sub('', out)
    return out


def main():
    check = '--check' in sys.argv
    pages = sorted(ROOT.glob('*.html')) + sorted((ROOT / 'staging').glob('*.html'))
    changed = []
    for p in pages:
        s = p.read_text(encoding='utf-8')
        out = strip(s)
        if out != s:
            changed.append(p.relative_to(ROOT).as_posix())
            if not check:
                p.write_text(out, encoding='utf-8')
    if check:
        if changed:
            print(f"❌ 푸터 면책 상자가 남은 페이지 {len(changed)}장: {' '.join(changed)}")
            print("   python3 scripts/strip_footer_disclaimer.py")
            return 1
        print(f"✅ 푸터 면책 상자 없음 · {len(pages)}장 확인")
        return 0
    print(f"✅ 푸터 면책 상자 뺌 {len(changed)}장 / {len(pages)}장")
    if changed:
        print('   ' + ' '.join(changed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
