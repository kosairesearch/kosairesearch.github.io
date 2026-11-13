#!/usr/bin/env bash
# 작업이 커밋한 결과를 main 에 올린다 — 작업 파일 여럿이 같이 쓴다.
#
#   git commit … && bash scripts/push_main.sh
#
# 왜 있나(2026-11-13). 11/12 07:58(세계 표준시) 공시 트리거 실행이 하이쿠 리포트 106편(약 3.36달러 · 기록 기준)을
# 쓰고도 main 에 올리지 못했고, 다음 실행이 같은 114종목을 다시 주문했다. 세 가지가 겹쳤다.
#   · 실패 기록 파일은 '1 2026-11-12' 처럼 내용이 거의 같다. 이 실행은 한 종목의 기록을 지우고 다른 종목의 기록을
#     새로 만들었는데, rebase 가 둘을 '이름 바꿈'으로 읽었다. 그사이 다른 실행이 지운 기록이라 rename/delete 충돌이
#     났다. -X theirs 는 글 내용의 충돌만 푼다.
#   · 재시도가 멈춘 rebase 를 거두지 않아 남은 네 번은 'rebase-merge 폴더가 이미 있다'로 곧바로 실패했다.
#   · 다섯 번 모두 실패해도 단계는 성공으로 끝났다(반복문의 마지막 명령이 sleep).
# 그래서 — 남은 충돌(이름 바꿈 · 수정과 삭제가 엇갈린 것)은 이 실행의 판을 따르고(-X theirs 와 같은 원칙 — rebase 에서
# 'theirs' 는 다시 얹는 이 실행의 커밋이다), 풀지 못한 rebase 는 거두고 다시 하며, 끝내 못 올리면 실패로 끝낸다.
# -X no-renames 는 보조다 — git 의 기본 합치기(ort)는 내용이 같은 파일의 이름 바꿈을 이 선택과 관계없이 찾는다(2.43 에서
# 확인 · 그날의 충돌도 이 꼴). 그래서 충돌 풀기를 빼면 안 된다. 지키는 검사 scripts/tests/push_main_test.py.
#
#   PUSH_TRIES   재시도 횟수(기본 8)
#   PUSH_SLEEP   기다리는 시간의 배수(기본 1 · 시험은 0)
set -u

tries="${PUSH_TRIES:-8}"
nap() { sleep $(( ($1 * 3 + RANDOM % 5) * ${PUSH_SLEEP:-1} )); }

in_rebase() {
  [ -d "$(git rev-parse --git-path rebase-merge)" ] || [ -d "$(git rev-parse --git-path rebase-apply)" ]
}

# 멈춘 rebase 의 남은 충돌을 이 실행의 판으로 푼다(rebase 에서 2번 칸은 main, 3번 칸은 이 실행의 커밋이다).
#   이 실행의 판이 있다            → 그 판
#   없고 원래 있던 파일이다         → 이 실행이 지운 파일 — 지운다
#   없고 main 에만 새로 생긴 파일이다 → 그대로 둔다
take_this_run() {
  local f
  while IFS= read -r -d '' f; do
    if git cat-file -e ":3:$f" 2>/dev/null; then
      git checkout --theirs -- "$f" && git add -- "$f" || return 1
    elif git cat-file -e ":1:$f" 2>/dev/null; then
      git rm -q -- "$f" >/dev/null 2>&1 || return 1
    else
      git checkout --ours -- "$f" && git add -- "$f" || return 1
    fi
    echo "    · 충돌 $f → 이 실행의 판"
  done < <(git diff --name-only --diff-filter=U -z | sort -zu)
}

# 멈춘 rebase 를 끝까지 민다. 커밋마다 멈출 수 있어 되풀이한다. 끝내지 못하면 1.
finish_rebase() {
  local guard=0
  while in_rebase; do
    guard=$((guard + 1))
    [ "$guard" -le 30 ] || return 1
    take_this_run || return 1
    if [ -n "$(git diff --name-only --diff-filter=U)" ]; then
      return 1
    fi
    if git diff --cached --quiet; then
      # 풀고 나니 바뀐 것이 없다 — 같은 변경이 이미 main 에 있다. 이 커밋은 건너뛴다.
      GIT_EDITOR=true git rebase --skip >/dev/null 2>&1 || true
    else
      GIT_EDITOR=true git rebase --continue >/dev/null 2>&1 || true
    fi
  done
  return 0
}

for i in $(seq 1 "$tries"); do
  git fetch -q origin main || true
  if ! git rebase -X theirs -X no-renames origin/main; then
    if ! finish_rebase; then
      echo "  · ${i}번째: rebase 를 끝내지 못했다 — 거두고 다시"
      git rebase --abort 2>/dev/null || true
      nap "$i"
      continue
    fi
  fi
  if git push origin HEAD:main; then
    exit 0
  fi
  echo "push 재시도 $i..."
  nap "$i"
done
in_rebase && git rebase --abort 2>/dev/null
echo "::error::main 에 올리지 못했다(${tries}번 모두 실패) — 결과가 사라진 것을 모르고 지나가지 않게 실패로 끝낸다."
exit 1
