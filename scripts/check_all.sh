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
#   npm install --no-save jsdom playwright-core
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
for f in staging/tests/*.mjs; do run "$(basename "$f")" node "$f"; done

echo "── 사이트 전체 ──"
run "호출부"        node scripts/check_calls.mjs
run "번역"          node scripts/check_i18n.mjs
run "SEO·구조"      python3 scripts/check_seo.py
# 자바스크립트를 고쳐 놓고 캐시 주소를 안 바꾸면, 다시 온 사람은 옛 파일을
# 계속 쓴다. 코드는 고쳐졌는데 화면은 안 바뀌는, 원인을 찾기 제일 어려운
# 종류의 버그다. 올리기 전에 여기서 잡는다.
run "캐시 주소"     python3 scripts/stamp_assets.py --check

echo
if [ $bad -eq 0 ]; then
  echo "전부 통과."
else
  red "실패가 있다 — 올리지 말 것."
fi
exit $bad
