#!/usr/bin/env python3
"""한국거래소 로그인 아이디가 저장소에 남지 않는가.

pykrx(1.2.x)는 한국거래소에 로그인할 때 '로그인 ID: …' 를 찍는다. 로그인 정보(KRX_ID · KRX_PW)를
쓰는 작업이 그 출력을 data/ 의 기록 파일로 남기고 커밋해, 10/3~10/8 사이 아이디가 공개 저장소에
올라갔다(비밀번호는 찍지 않는다). Actions 화면은 비밀 값을 *** 로 가리지만 파일로 남긴 기록은
가리지 않는다.

  ① 로그인 정보를 쓰는 단계에서 data/ 로 기록을 남기는 줄은 모두 가림 필터를 거친다
  ② 그 필터가 아이디 줄만 바꾸고 다른 줄은 그대로 둔다
  ③ 지금 저장소의 data/ 에 가리지 않은 아이디 줄이 없다

  실행:  python3 scripts/tests/krx_id_test.py
"""
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
SED = "sed -u 's/\\(로그인 ID: \\).*/\\1(가림)/'"
PASS = FAIL = 0


def ok(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✔ {name}")
    else:
        FAIL += 1
        print(f"  ✘ {name}" + (f"\n      {detail}" if detail else ""))


print("── ① 로그인 정보를 쓰는 단계의 기록은 가림 필터를 거친다 ──")
steps, bad = 0, []
for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
    for job in (doc.get("jobs") or {}).values():
        for st in job.get("steps") or []:
            env = st.get("env") or {}
            run = st.get("run") or ""
            if "KRX_ID" not in env:
                continue
            for line in run.splitlines():
                # data/ 로 남기는 기록 — tee 또는 > 로 쓰는 줄
                if re.search(r"(\btee\b[^|]*|>>?\s*)data/", line) and "python" in line:
                    steps += 1
                    if SED not in line:
                        bad.append(f"{wf.name}: {line.strip()[:120]}")
ok(f"로그인 정보를 쓰며 기록을 남기는 줄 {steps}곳 모두 가림", steps > 0 and not bad, "\n      ".join(bad))

print("\n── ② 필터는 아이디 줄만 바꾼다 ──")
sample = "KRX 로그인 시도...\n  로그인 ID: someone123\nKRX 로그인 완료.\n  로그인 시간: 2026-10-08 07:02:32\n"
out = subprocess.run(["bash", "-c", SED], input=sample, capture_output=True, text=True).stdout
ok("아이디를 가린다", "  로그인 ID: (가림)\n" in out and "someone123" not in out, repr(out))
ok("다른 줄은 그대로", out.replace("  로그인 ID: (가림)\n", "") == sample.replace("  로그인 ID: someone123\n", ""), repr(out))

print("\n── ③ 저장소의 data/ 에 가리지 않은 아이디가 없다 ──")
files = subprocess.run(["git", "ls-files", "data"], cwd=ROOT, capture_output=True, text=True).stdout.split()
left = []
for f in files:
    p = ROOT / f
    if p.suffix not in (".log", ".txt") or not p.is_file():
        continue
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if re.search(r"로그인 ID: (?!\(가림\))\S", line):
            left.append(f"{f}:{i}")
ok(f"기록 파일 {sum(1 for f in files if f.endswith(('.log', '.txt')))}개에 남은 아이디 0", not left, ", ".join(left[:5]))

print(f"\nPASS {PASS}  FAIL {FAIL}")
sys.exit(1 if FAIL else 0)
