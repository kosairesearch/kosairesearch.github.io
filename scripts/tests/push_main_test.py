#!/usr/bin/env python3
"""scripts/push_main.sh — 작업이 커밋한 결과를 main 에 올리는 공용 단계(2026-11-13).

11/12 공시 트리거 실행이 리포트 106편을 쓰고도 올리지 못했다 — 실패 기록 두 파일(내용이 거의 같다)을 rebase 가
'이름 바꿈'으로 읽어 rename/delete 충돌이 났고, 재시도는 멈춘 rebase 를 거두지 않았고, 다섯 번 모두 실패해도
단계는 성공으로 끝났다. 진짜 git 저장소(원격 하나 · 작업 사본 둘)로 그 장면과 비슷한 장면들을 다시 만들어 본다.
같은 날 실패한 종목의 기록은 '1 2026-11-12' 로 글자까지 같아, git 은 하나를 지우고 하나를 만든 것을 이름 바꿈으로 본다.

  ① 그날의 장면 — 옛 반복문은 올리지 못하고도 성공(0)으로 끝난다 · push_main.sh 는 올린다
  ② 이 실행이 고친 파일을 main 이 지웠다 → 이 실행의 판
  ③ 이 실행이 지운 파일을 main 이 고쳤다 → 지운다
  ④ 같은 줄을 둘 다 고쳤다 → 이 실행의 판(-X theirs)
  ⑤ main 에 같은 변경이 이미 있다 → 빈 커밋을 건너뛰고 성공
  ⑥ 커밋 둘이 차례로 충돌한다 → 둘 다 풀어 올린다
  ⑦ 끝내 못 올리면 실패(1)로 끝나고 rebase 를 남기지 않는다
  ⑧ main 에만 새로 생긴 파일은 건드리지 않는다
  ⑨ 작업 파일 — 같은 단계를 쓰는지 · 옛 반복문이 남지 않았는지

  python3 scripts/tests/push_main_test.py
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "push_main.sh"
WF = ROOT / ".github" / "workflows"

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✔ {name}")
    else:
        fail += 1
        print(f"  ✘ {name}" + (f" — {detail}" if detail else ""))


ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
           GIT_COMMITTER_EMAIL="t@t", GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
           PUSH_SLEEP="0", LC_ALL="C.UTF-8")


def sh(cwd, *cmd, check_rc=True, env=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env or ENV)
    if check_rc and r.returncode:
        raise RuntimeError(f"{cmd} 실패: {r.stderr or r.stdout}")
    return r


def write(repo, rel, text):
    p = Path(repo) / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def setup(tmp, files):
    """원격(main) 하나와 작업 사본 둘(main 쪽 다른 실행 · 이 실행)을 만든다."""
    origin = Path(tmp) / "origin.git"
    sh(tmp, "git", "init", "-q", "--bare", "--initial-branch=main", str(origin))
    seed = Path(tmp) / "seed"
    sh(tmp, "git", "clone", "-q", str(origin), str(seed))
    sh(seed, "git", "checkout", "-q", "-b", "main")
    for rel, text in files.items():
        write(seed, rel, text)
    sh(seed, "git", "add", "-A")
    sh(seed, "git", "commit", "-q", "-m", "처음")
    sh(seed, "git", "push", "-q", "origin", "main")
    other = Path(tmp) / "other"
    run = Path(tmp) / "run"
    for d in (other, run):
        sh(tmp, "git", "clone", "-q", str(origin), str(d))
    return origin, other, run


def commit(repo, msg, changes):
    for rel, text in changes.items():
        if text is None:
            sh(repo, "git", "rm", "-q", rel)
        else:
            write(repo, rel, text)
    sh(repo, "git", "add", "-A")
    sh(repo, "git", "commit", "-q", "--allow-empty", "-m", msg)


def push_main(repo, **env):
    e = dict(ENV, **env)
    return sh(repo, "bash", str(HELPER), check_rc=False, env=e)


def main_files(origin):
    r = sh(origin, "git", "ls-tree", "-r", "--name-only", "main")
    return set(r.stdout.split())


def main_text(origin, rel):
    r = sh(origin, "git", "show", f"main:{rel}", check_rc=False)
    return r.stdout if r.returncode == 0 else None


def in_rebase(repo):
    g = Path(repo) / ".git"
    return (g / "rebase-merge").exists() or (g / "rebase-apply").exists()


OLD_LOOP = """
for i in 1 2 3 4 5; do
  git fetch origin main && git rebase -X theirs origin/main && git push origin main && break
  echo "push 재시도 $i..."
done
"""

BASE = {
    "data/reports_v2_fail/067900": "1 2026-11-12",   # 같은 날 실패한 기록은 내용이 같다
    "data/reports_v2/067900.json": '{"t": "067900", "v": 1}\n',
    "data/reports_v2/011500.json": '{"t": "011500", "v": 1}\n',
    "data/batches_v2/b1.json": '{"id": "b1", "repair": "r1"}\n',
}


def scene_rename_delete():
    print("① 그날의 장면 — 실패 기록 하나를 지우고 하나를 새로 만들었는데, main 이 먼저 지웠다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        # 다른 실행(회수)이 먼저 같은 보정을 받아 067900 을 저장하고 실패 기록을 지웠다.
        commit(other, "회수", {"data/reports_v2_fail/067900": None,
                               "data/reports_v2/067900.json": '{"t": "067900", "v": 2}\n',
                               "data/batches_v2/b1.json": '{"id": "b1", "collected": "x"}\n'})
        sh(other, "git", "push", "-q", "origin", "main")
        # 이 실행 — 같은 일을 늦게 하고, 새 종목 003530 을 실패로 적고, 새 리포트를 저장했다.
        commit(run, "공시 트리거", {"data/reports_v2_fail/067900": None,
                                     "data/reports_v2_fail/003530": "1 2026-11-12",
                                     "data/reports_v2/067900.json": '{"t": "067900", "v": 2}\n',
                                     "data/reports_v2/011500.json": '{"t": "011500", "v": 2}\n',
                                     "data/batches_v2/b1.json": '{"id": "b1", "collected": "y"}\n',
                                     "data/batches_v2/b2.json": '{"id": "b2", "repair": "r2"}\n'})
        head = sh(run, "git", "rev-parse", "HEAD").stdout.strip()
        r = sh(run, "bash", "-c", OLD_LOOP, check_rc=False)
        files = main_files(origin)
        check("옛 반복문은 올리지 못했다", "data/reports_v2_fail/003530" not in files)
        check("옛 반복문은 그래도 성공(0)으로 끝났다 — 고치기 전 모습", r.returncode == 0, f"rc={r.returncode}")
        check("옛 반복문은 멈춘 rebase 를 남겼다", in_rebase(run))
        # 같은 커밋으로 고친 단계를 돌린다.
        sh(run, "git", "rebase", "--abort", check_rc=False)
        sh(run, "git", "reset", "-q", "--hard", head)
        r = push_main(run)
        files = main_files(origin)
        check("push_main.sh 는 올렸다(0)", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        check("새 실패 기록 003530 이 main 에 있다", "data/reports_v2_fail/003530" in files)
        check("지운 실패 기록 067900 은 없다", "data/reports_v2_fail/067900" not in files)
        check("이 실행의 새 상태 파일 b2 가 있다", "data/batches_v2/b2.json" in files)
        check("이 실행의 리포트 011500 v2", '"v": 2' in (main_text(origin, "data/reports_v2/011500.json") or ""))
        check("rebase 를 남기지 않았다", not in_rebase(run))


def scene_modify_delete():
    print("② 이 실행이 고친 파일을 main 이 지웠다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        commit(other, "main 이 지움", {"data/reports_v2_fail/067900": None})
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "이 실행이 고침", {"data/reports_v2_fail/067900": "2 2026-11-12"})
        r = push_main(run)
        check("올렸다(0)", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        check("이 실행의 판(2번째 실패)이 남았다", main_text(origin, "data/reports_v2_fail/067900") == "2 2026-11-12",
              repr(main_text(origin, "data/reports_v2_fail/067900")))


def scene_delete_modify():
    print("③ 이 실행이 지운 파일을 main 이 고쳤다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        commit(other, "main 이 고침", {"data/reports_v2_fail/067900": "2 2026-11-12"})
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "이 실행이 저장하고 지움", {"data/reports_v2_fail/067900": None,
                                               "data/reports_v2/067900.json": '{"t": "067900", "v": 3}\n'})
        r = push_main(run)
        check("올렸다(0)", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        files = main_files(origin)
        check("실패 기록은 지워졌다(이 실행의 판)", "data/reports_v2_fail/067900" not in files)
        check("이 실행의 리포트가 있다", '"v": 3' in (main_text(origin, "data/reports_v2/067900.json") or ""))


def scene_same_line():
    print("④ 같은 줄을 둘 다 고쳤다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        commit(other, "main", {"data/batches_v2/b1.json": '{"id": "b1", "repair": "rX"}\n'})
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "이 실행", {"data/batches_v2/b1.json": '{"id": "b1", "repair": "rY"}\n'})
        r = push_main(run)
        check("올렸다(0)", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        check("이 실행의 판", '"rY"' in (main_text(origin, "data/batches_v2/b1.json") or ""))


def scene_already_there():
    print("⑤ main 에 같은 변경이 이미 있다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        same = {"data/reports_v2/067900.json": '{"t": "067900", "v": 9}\n', "data/reports_v2_fail/067900": None}
        commit(other, "main", same)
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "이 실행(같은 일)", same)
        r = push_main(run)
        check("성공(0)으로 끝났다", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        check("rebase 를 남기지 않았다", not in_rebase(run))
        check("main 내용 그대로", '"v": 9' in (main_text(origin, "data/reports_v2/067900.json") or ""))


def scene_two_commits():
    print("⑥ 커밋 둘이 차례로 충돌한다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        commit(other, "main", {"data/reports_v2_fail/067900": None, "data/reports_v2/011500.json": None})
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "첫째", {"data/reports_v2_fail/067900": "2 2026-11-12"})
        commit(run, "둘째", {"data/reports_v2/011500.json": '{"t": "011500", "v": 5}\n'})
        r = push_main(run)
        check("올렸다(0)", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        check("첫째 커밋의 판", main_text(origin, "data/reports_v2_fail/067900") == "2 2026-11-12")
        check("둘째 커밋의 판", '"v": 5' in (main_text(origin, "data/reports_v2/011500.json") or ""))


def scene_never():
    print("⑦ 끝내 못 올린다")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        hook = origin / "hooks" / "pre-receive"
        hook.write_text("#!/bin/sh\necho 거절 >&2\nexit 1\n", encoding="utf-8")
        hook.chmod(0o755)
        commit(run, "이 실행", {"data/reports_v2/011500.json": '{"t": "011500", "v": 7}\n'})
        r = push_main(run, PUSH_TRIES="2")
        check("실패(1)로 끝났다", r.returncode == 1, f"rc={r.returncode}")
        check("오류 줄을 남겼다", "::error::" in r.stdout)
        check("rebase 를 남기지 않았다", not in_rebase(run))


def scene_new_on_main():
    print("⑧ main 에만 새로 생긴 파일")
    with tempfile.TemporaryDirectory() as tmp:
        origin, other, run = setup(tmp, BASE)
        commit(other, "main", {"data/reports_v2/005930.json": '{"t": "005930"}\n'})
        sh(other, "git", "push", "-q", "origin", "main")
        commit(run, "이 실행", {"data/reports_v2/011500.json": '{"t": "011500", "v": 4}\n'})
        r = push_main(run)
        check("올렸다(0)", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        files = main_files(origin)
        check("main 의 새 파일이 그대로 있다", "data/reports_v2/005930.json" in files)
        check("이 실행의 판", '"v": 4' in (main_text(origin, "data/reports_v2/011500.json") or ""))


# 결과를 커밋해 올리는 작업 파일 — 공용 단계를 쓴다.
USERS = ["filing_reports.yml", "new_listings.yml", "classify_sectors.yml", "generate_sectors.yml",
         "sectors_watchdog.yml", "update_data.yml", "generate_reports_batch.yml",
         "collect_batch.yml", "generate_reports_v2.yml"]


def workflows():
    print("⑨ 작업 파일")
    for name in USERS:
        t = (WF / name).read_text(encoding="utf-8")
        check(f"{name} 가 push_main.sh 를 쓴다", "bash scripts/push_main.sh" in t)
        check(f"{name} 에 옛 반복문이 없다", "git rebase -X theirs origin/main" not in t and "git rebase origin/main" not in t
              and "git rebase -X no-renames origin/main" not in t)
    # 멈춘 rebase 를 거두지 않고 다시 도는 반복문이 어디에도 없어야 한다.
    bad = []
    for p in sorted(WF.glob("*.yml")):
        t = p.read_text(encoding="utf-8")
        for m in re.finditer(r"for i in [^\n]*; do\n((?:[^\n]*\n){1,4}?)\s*done", t):
            body = m.group(1)
            if "git rebase" in body and "rebase --abort" not in body and "push_main.sh" not in body:
                bad.append(p.name)
    check("멈춘 rebase 를 거두지 않는 반복문 0", not bad, ", ".join(bad))


if __name__ == "__main__":
    scene_rename_delete()
    scene_modify_delete()
    scene_delete_modify()
    scene_same_line()
    scene_already_there()
    scene_two_commits()
    scene_never()
    scene_new_on_main()
    workflows()
    print(f"\n통과 {ok} · 실패 {fail}")
    sys.exit(1 if fail else 0)
