#!/usr/bin/env bash
# 올리기 전에 도는 검사를 한 자리에 모은다.
#
# 왜 필요한가. 검사가 여덟 군데에 흩어져 있어서 "전부 돌린다" 는 것이 사람의
# 기억에만 있었다. 실제로 그 때문에 하나가 새어 나갔다 — stamp_assets.py 는
# 배포 전에 돌려야 하는데 아무도 안 돌려서, 자바스크립트 7개의 캐시 주소가
# 옛것에 묶여 있었다. 고쳐 올려도 다시 온 사람은 옛 파일을 계속 쓰고 있었다.
#
#   bash scripts/check_all.sh
#
# 처음 한 번은 검사용 꾸러미를 깔아야 한다(저장소에는 넣지 않는다).
#
#   npm install --no-save jsdom playwright-core firebase firebase-tools @firebase/rules-unit-testing
set -uo pipefail
cd "$(dirname "$0")/.."

bad=0
red()  { printf '\033[31m%s\033[0m\n' "$1"; }
pass() { printf '  ✔ %s\n' "$1"; }

run() {                       # run <이름> <명령…>
  local name="$1"; shift
  local out rc
  out=$("$@" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then
    pass "$name — $(echo "$out" | grep -E '통과 [0-9]+|PASS *[0-9]+ *FAIL' | tail -1)"
  else
    red "  ✘ $name"
    echo "$out" | grep -E "FAIL|❌|Error" | head -6 | sed 's/^/      /'
    bad=1
  fi
}

echo "── 결제 (서버 쪽 로직) ──"
for f in functions/tests/*.mjs; do run "$(basename "$f")" node "$f"; done

echo "── 화면 (스테이징·실사이트) ──"
# 폴더째 훑으므로 새 검사를 넣으면 여기 손대지 않아도 같이 돈다.
# auth-table 은 로그인·회원가입 — 화면 넷과 모듈 다섯에 걸쳐 있어
# 한 화면만 보고 고치면 나머지가 남는다.
for f in staging/tests/*.mjs; do run "$(basename "$f")" node "$f"; done

echo "── 사이트 전체 ──"
run "호출부"        node scripts/check_calls.mjs
run "번역"          node scripts/check_i18n.mjs
run "SEO·구조"      python3 scripts/check_seo.py
# 업종 분석은 분기에 한 번만 돈다. 무엇이 어긋나도 다음 분기까지 아무도
# 모르므로(실제로 7·8월 예정 실행이 아무것도 안 하고 성공으로 끝났다)
# 요금 창구·일정·화면 안내가 서로 맞는지 여기서 본다.
run "업종 분석"     python3 scripts/check_sectors.py
# 접근 규칙은 화면과 서버 사이의 마지막 문이다. 여기가 열려 있으면 앞의
# 검사를 아무리 통과해도 소용이 없다 — 콘솔에서 구독을 PRO 로 고쳐 쓴다.
# 에뮬레이터(자바)가 없으면 스스로 건너뛴다.
run "접근 규칙"     bash scripts/check_rules.sh
# 자바스크립트를 고쳐 놓고 캐시 주소를 안 바꾸면, 다시 온 사람은 옛 파일을
# 계속 쓴다. 코드는 고쳐졌는데 화면은 안 바뀌는, 원인을 찾기 제일 어려운
# 종류의 버그다. 올리기 전에 여기서 잡는다.
run "캐시 주소"     python3 scripts/stamp_assets.py --check

echo "── 리포트 숫자 ──"
# 항등식만 보면 틀린 값끼리 맞아떨어지는 것을 못 잡는다. 삼성생명 BPS 가
# KRX 공식값의 2.3배인데 PBR×BPS=주가 는 통과했다. 그래서 같은 값을 서로
# 다른 재료로 만들어 맞대 본다 — 업종별 173종목 표본으로 본다.
run "숫자 삼각대조" python3 scripts/verify_numbers.py --quiet --max 8
# 검사가 '0건' 을 내면 멀쩡한 것과 검사가 헛도는 것이 똑같이 생겼다.
# 값을 일부러 망가뜨려 넣고 진짜로 걸리는지 확인한다.
run "검증기 자체"   python3 scripts/tests/verify_numbers_test.py
# 생성기는 DART·KRX 를 부르고 요금이 나가서 통째로 못 돌린다. 그래서 분모를
# 되묻는 블록만 원문에서 꺼내 실제 값으로 돌려 본다 — 틀렸던 종목은 고쳐지고
# 맞았던 종목(삼성생명)은 안 건드리는지.
run "생성기 분모"   python3 scripts/tests/bps_denominator_test.py

echo
if [ $bad -eq 0 ]; then
  echo "전부 통과."
else
  red "실패가 있다 — 올리지 말 것."
fi
exit $bad
