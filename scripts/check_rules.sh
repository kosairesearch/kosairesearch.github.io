#!/usr/bin/env bash
# 파이어스토어 접근 규칙을 에뮬레이터에 대고 실제로 눌러 본다.
#
# 규칙은 눈으로 봐서는 맞는지 알기 어렵다. delete 는 allow write 에 들어가는데
# 그때 request.resource 가 null 이라, 쓰기에 모양 검사를 붙이면 삭제가 같이
# 막힌다 — 읽어서는 안 보이고 돌려 봐야 보인다.
#
# 에뮬레이터는 자바가 있어야 돌고 꾸러미도 크다. 없으면 건너뛴다 —
# 나머지 검사까지 못 돌게 만들 이유는 없다.
#
#   npm install --no-save firebase firebase-tools @firebase/rules-unit-testing
#   bash scripts/check_rules.sh
set -uo pipefail
cd "$(dirname "$0")/.."

FB="node_modules/firebase-tools/lib/bin/firebase.js"

if ! command -v java >/dev/null 2>&1; then
  echo "건너뜀 — 자바가 없다(에뮬레이터가 자바로 돈다)"; exit 0
fi
if [ ! -f "$FB" ]; then
  echo "건너뜀 — firebase-tools 없음.  npm install --no-save firebase firebase-tools @firebase/rules-unit-testing"; exit 0
fi
if ! node -e "require.resolve('@firebase/rules-unit-testing/package.json')" 2>/dev/null; then
  echo "건너뜀 — @firebase/rules-unit-testing 없음"; exit 0
fi

node "$FB" emulators:exec --only firestore --project kosai-rules-test \
  "node scripts/tests/rules.test.mjs" 2>&1 \
  | grep -vE '@firebase/firestore:|GrpcConnection|^false for|^i  |^\+  |Downloading|^$|^⚠'
exit "${PIPESTATUS[0]}"
