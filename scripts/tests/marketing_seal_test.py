#!/usr/bin/env python3
"""marketing_seal.py 와 두 마케팅 작업 — 숫자가 공개 실행 기록에 남지 않는지.

2026-10-06 사장 "외부에서 우리 마케팅 데이터를 보면 안되지". '마케팅 숫자 물어보기'가 답을, '주간 성과 보고'가
보고서 전문 · 주마다의 이용자 수 · 실험 대장을 공개 실행 기록(로그 · 요약 칸)에 그대로 찍고 있었다.

여기서 보는 것
  ① 잠근 답이 이 세션의 열쇠로만 열리는지(조각 순서 · 빠진 조각 · *** 가리기 · 다른 열쇠 · 잘못된 열쇠)
  ② 작업 파일의 단계를 가짜 스크립트로 실제로 돌려, 기록(표준 출력 · 요약 칸)에 숫자가 한 글자도 나오지
     않고 잠긴 글에는 다 들어 있는지. 고치기 전 작업 파일이면 여기서 걸린다.
진짜 열쇠(~/.kosai)는 건드리지 않는다 — 임시 폴더에 따로 만든다.
"""
import base64
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
TMP = Path(tempfile.mkdtemp(prefix="seal-test-"))
os.environ["KOSAI_MARKETING_KEY"] = str(TMP / "a" / "key.pem")
import marketing_seal as M  # noqa: E402

ASK = (ROOT / ".github/workflows/marketing_ask.yml").read_text(encoding="utf-8")
WEEKLY = (ROOT / ".github/workflows/marketing_weekly.yml").read_text(encoding="utf-8")
SECRET = "이용자 1,234명 · 네이버 567회"     # 기록에 나오면 안 되는 글(가짜 숫자 · 쉼표는 base64 에 없다)

P = F = 0


def ok(name, cond, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  ✅ {name}")
    else:
        F += 1
        print(f"  ❌ {name}  {extra}")


def raises(name, fn, want):
    try:
        fn()
    except M.SealError as e:
        ok(name, want in str(e), f"오류={e}")
        return
    except Exception as e:  # noqa: BLE001
        ok(name, False, f"SealError 가 아니라 {type(e).__name__}: {e}")
        return
    ok(name, False, "오류가 나지 않았다")


def gh_log(lines):
    """GitHub 실행 기록처럼 — 줄마다 시각 꼬리표, 앞에 명령 · env 줄."""
    ts = "2026-10-06T01:02:03.4567890Z "
    head = ['##[group]Run python3 scripts/marketing_seal.py seal --key "$KEY" --in /tmp/answer.txt',
            "env:", "  KEY: " + "QUJD" * 120, "##[endgroup]"]
    return "\n".join(ts + x for x in head + list(lines) + ["Post job cleanup."])


def openssl(*args, data=None):
    return subprocess.run(["openssl", *args], input=data, capture_output=True, check=True).stdout


# ─────────────────────────────── ① 잠그기 · 열기 ───────────────────────────────

print("■ 열쇠")
k1 = M.newkey()
A = M.KEY_FILE
ok("열쇠 파일은 나만 읽는다(600)", (A.stat().st_mode & 0o777) == 0o600, oct(A.stat().st_mode))
ok("다시 불러도 같은 열쇠", M.newkey() == k1)
ok("공개 열쇠는 한 줄", "\n" not in k1 and len(k1) < 700, f"len={len(k1)}")
ok("공개 열쇠로 읽힌다(DER)",
   b"BEGIN PUBLIC KEY" in openssl("pkey", "-pubin", "-inform", "DER", data=base64.b64decode(k1)))

print("■ 잠그고 열기")
small = (SECRET + "\n").encode()
lines = M.seal(k1, small)
joined = "\n".join(lines)
ok("잠근 줄에 평문이 없다", "1,234" not in joined and "이용자" not in joined)
ok("첫 줄은 표시 · 열쇠 지문", lines[0].startswith(M.MARK + " ") and " FOR " in lines[0], lines[0])
ok("열린다", M.open_sealed(gh_log(lines)) == small)
ok("같은 답도 잠글 때마다 다르다", M.seal(k1, small)[1:] != lines[1:])

big = os.urandom(12000).hex().encode() + ("\n" + SECRET).encode()
bl = M.seal(k1, big)
data = [x for x in bl if " DATA " in x]
ok("긴 답은 여러 줄로 나뉜다", len(data) >= 3, f"{len(data)}줄")
ok("줄마다 4,000자를 넘지 않는다", all(len(x.split()[-1]) <= M.CHUNK for x in data))
mixed = [x for x in bl if " DATA " not in x] + random.Random(7).sample(data, len(data))
ok("순서가 섞여도 열린다", M.open_sealed(gh_log(mixed)) == big)
ok("한 기록에 둘이면 차례로 잇는다", M.open_sealed(gh_log(M.seal(k1, b"A") + M.seal(k1, b"B"))) == b"A\nB")

print("■ 열지 못할 때")
raises("조각이 빠지면", lambda: M.open_sealed(gh_log([x for x in bl if x != data[1]])), "조각")
masked = [x if x != data[0] else x[:200] + "***" + x[210:] for x in bl]
raises("*** 로 가려지면", lambda: M.open_sealed(gh_log(masked)), "가려졌다")
raises("끝까지 안 찍혔으면", lambda: M.open_sealed(gh_log([x for x in bl if " PARTS " not in x])), "끝까지")
raises("잠긴 답이 없으면", lambda: M.open_sealed(gh_log(["그냥 줄"])), "찾지 못했다")

M.KEY_FILE = TMP / "b" / "key.pem"
k2 = M.newkey()
other = M.seal(k2, small)
M.KEY_FILE = A
ok("다른 세션은 다른 열쇠", k2 != k1)
raises("다른 열쇠로 잠긴 답", lambda: M.open_sealed(gh_log(other)), "다른 열쇠")
raises("지문 줄을 지워도 다른 열쇠로는 못 연다",
       lambda: M.open_sealed(gh_log([x for x in other if " FOR " not in x])), "pkeyutl")
M.KEY_FILE = TMP / "없음" / "key.pem"
raises("여는 열쇠가 없으면", lambda: M.open_sealed(gh_log(lines)), "여는 열쇠가 없다")
M.KEY_FILE = A

print("■ 받는 열쇠")
pem_b64 = base64.b64encode(openssl("pkey", "-in", str(A), "-pubout")).decode()
ok("PEM 꼴 공개 열쇠도 받는다", M.open_sealed(gh_log(M.seal(pem_b64, small))) == small)
raises("빈 열쇠", lambda: M.seal("", small), "비어 있다")
raises("base64 가 아닌 열쇠", lambda: M.seal("열쇠!!", small), "base64")
raises("열쇠가 아닌 글", lambda: M.seal(base64.b64encode(b"hello world").decode(), small), "공개 열쇠가 아니다")
raises("비밀 열쇠를 넣으면", lambda: M.seal(base64.b64encode(A.read_bytes()).decode(), small), "공개 열쇠가 아니다")
weak = openssl("pkey", "-pubout", "-outform", "DER",
               data=openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:1024"))
raises("1024비트 열쇠", lambda: M.seal(base64.b64encode(weak).decode(), small), "2048")
ec = openssl("pkey", "-pubout", "-outform", "DER",
             data=openssl("genpkey", "-algorithm", "EC", "-pkeyopt", "ec_paramgen_curve:P-256"))
raises("RSA 가 아닌 열쇠", lambda: M.seal(base64.b64encode(ec).decode(), small), "RSA")

print("■ 명령줄")
env = dict(os.environ, KOSAI_MARKETING_KEY=str(A), PYTHONIOENCODING="utf-8")
SEAL = [sys.executable, str(ROOT / "scripts/marketing_seal.py")]
ans = TMP / "answer.txt"
ans.write_text(SECRET + "\n", encoding="utf-8")
r = subprocess.run(SEAL + ["seal", "--key", "잘못된 열쇠", "--in", str(ans)], capture_output=True, env=env)
ok("잘못된 열쇠면 2 로 끝나고 아무것도 찍지 않는다", r.returncode == 2 and r.stdout == b"",
   f"rc={r.returncode} out={r.stdout[:80]!r}")
ok("오류 글에도 평문이 없다", "1,234".encode() not in r.stderr)
r = subprocess.run(SEAL + ["check", "--key", k1], capture_output=True, env=env, encoding="utf-8")
ok("check — 쓸 만한 열쇠", r.returncode == 0 and "지문" in r.stdout, r.stdout + r.stderr)
r = subprocess.run(SEAL + ["seal", "--key", k1, "--in", str(ans)], capture_output=True, env=env, encoding="utf-8")
logf = TMP / "job.log"
logf.write_text(gh_log(r.stdout.splitlines()), encoding="utf-8")
r2 = subprocess.run(SEAL + ["open", "--file", str(logf)], capture_output=True, env=env, encoding="utf-8")
ok("seal → 기록 → open --file", r.returncode == 0 and r2.returncode == 0 and r2.stdout == SECRET + "\n",
   r.stderr + r2.stderr)
r3 = subprocess.run(SEAL + ["open"], input=logf.read_text(encoding="utf-8"), capture_output=True, env=env,
                    encoding="utf-8")
ok("open — 표준 입력", r3.stdout == SECRET + "\n", r3.stderr)


# ──────────────────────── ② 작업 파일의 단계를 실제로 돌려 본다 ────────────────────────

def block(text, needle):
    """작업 파일에서 needle(그 단계가 돌리는 명령)이 든 단계의 run 본문을 꺼낸다. 없으면 None.
    단계 이름이 아니라 명령으로 찾는다 — 고치기 전 작업 파일에도 같은 검사를 대어 걸리는지 보려고."""
    rows = text.splitlines()
    hit = next((k for k, x in enumerate(rows) if needle in x and not x.strip().startswith("#")), None)
    if hit is None:
        return None
    j = next((k for k in range(hit, -1, -1) if rows[k].strip().startswith("run:")), None)
    if j is None:
        return None
    first = rows[j].strip()[4:].strip()
    if first and first != "|":
        return first + "\n"
    ind = len(rows[j]) - len(rows[j].lstrip())
    body = []
    for x in rows[j + 1:]:
        if x.strip() and len(x) - len(x.lstrip()) <= ind:
            break
        body.append(x)
    pad = min(len(x) - len(x.lstrip()) for x in body if x.strip())
    return "\n".join(x[pad:] for x in body) + "\n"


def stub(stdout, stderr="", rc=0):
    return f"import sys\nsys.stdout.write({stdout!r})\nsys.stderr.write({stderr!r})\nsys.exit({rc})\n"


def workspace(stubs):
    w = Path(tempfile.mkdtemp(prefix="wf-", dir=TMP))
    (w / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/marketing_seal.py", w / "scripts/marketing_seal.py")
    for name, body in stubs.items():
        (w / "scripts" / name).write_text(body, encoding="utf-8")
    (w / "out").mkdir()
    return w


def fill(script, w):
    """단계 본문의 /tmp 자리와 ${{ }} 를 시험용 값으로."""
    for name in ("out", "all.txt", "answer.txt", "report.md", "probe.txt"):
        script = script.replace(f"/tmp/{name}", str(w / name))
    return (script.replace("${{ inputs.weeks || '12' }}", "12")
            .replace("${{ inputs.deep == true && '--deep' || '' }}", "")
            .replace("${{ inputs.send }}", "false"))


def run_step(w, script, extra):
    if script is None:                      # 그 단계가 없다 — 부르는 쪽이 '없음'으로 센다
        return None, "", ""
    f = w / "step.sh"
    f.write_text(fill(script, w), encoding="utf-8")
    summary = w / "summary.md"
    summary.write_text("", encoding="utf-8")
    e = dict(os.environ, GITHUB_STEP_SUMMARY=str(summary), PYTHONIOENCODING="utf-8")
    e.update(extra)
    r = subprocess.run(["bash", "-e", str(f)], cwd=w, capture_output=True, env=e, encoding="utf-8")
    return r.returncode, r.stdout + r.stderr, summary.read_text(encoding="utf-8")


print("■ 마케팅 숫자 물어보기 — 실제 단계를 가짜 답으로")
key_run = block(ASK, "marketing_seal.py check")
ok("열쇠 확인 단계가 있다", key_run is not None)
w = workspace({})
rc, out, _ = run_step(w, key_run, {"KEY": ""})
ok("열쇠가 없으면 묻지 않고 실패", rc == 1 and "::error" in out, f"rc={rc} {out[-200:]}")
rc, out, _ = run_step(w, key_run, {"KEY": "잘못된"})
ok("잘못된 열쇠면 실패", rc == 2, f"rc={rc} {out[-200:]}")
rc, out, _ = run_step(w, key_run, {"KEY": k1})
ok("맞는 열쇠면 통과", rc == 0, f"rc={rc} {out[-200:]}")
ok("열쇠부터 보고 묻는다",
   0 <= ASK.find("marketing_seal.py check") < ASK.find("scripts/marketing_mcp.py --ask"))

ask_run = block(ASK, "scripts/marketing_mcp.py --ask")
ok("묻는 단계가 있다", ask_run is not None)
for want in (0, 3):
    w = workspace({"marketing_mcp.py": stub(SECRET + "\n", "경고 줄 8,9\n", want)})
    rc, out, summ = run_step(w, ask_run, {"TOOL": "weekly", "ARGS": "weeks=8", "KEY": k1})
    ok(f"끝 코드 {want} 를 그대로 낸다", rc == want, f"rc={rc} {out[-300:]}")
    ok(f"기록 · 요약 칸에 답이 없다(끝 코드 {want})",
       not any(s in out + summ for s in ("1,234", "이용자", "8,9", "경고 줄")), (out + summ)[-300:])
    opened = M.open_sealed(out).decode() if M.MARK in out else ""
    ok(f"잠긴 답에는 다 있다(끝 코드 {want})", SECRET in opened and "경고 줄 8,9" in opened, opened[:200])

print("■ 주간 성과 보고 — 실제 단계를 가짜 숫자로")
w = workspace({
    "ga4_data.py": stub("::warning title=GA4 수집::가장 최근 주의 이용자가 0명이다\n",
                        "  2026-09-28~10-04  이용자 1,234 (신규 1,000)\n", 1),
    "experiments.py": stub("", "  [진행중] exp_3   첫 화면 검색창 · 기준 가입 전환율=1,5\n"),
    "marketing_report.py": stub("# 지난주 보고\n" + SECRET + "\n", "· 실험 1건 판정: 첫 화면 검색창=효과 있음\n"),
})
E = {"STARTED": "exp_3", "DROPPED": "", "WHY": "", "PROPOSE": ""}
rc1, out1, s1 = run_step(w, block(WEEKLY, "scripts/ga4_data.py --weeks"), E)
ok("① 끝 코드를 그대로 낸다", rc1 == 1, f"rc={rc1} {out1[-300:]}")
ok("① 막힌 이유(::warning)는 보인다", "::warning title=GA4 수집::" in out1, out1[-300:])
rc2, out2, s2 = run_step(w, block(WEEKLY, "scripts/experiments.py --list"), E)
ok("실험 표시는 끝 코드 0", rc2 == 0, f"rc={rc2} {out2[-300:]}")
rc3, out3, s3 = run_step(w, block(WEEKLY, "scripts/marketing_report.py"), E)
ok("② 는 끝 코드 0", rc3 == 0, f"rc={rc3} {out3[-300:]}")
seen = out1 + out2 + out3 + s1 + s2 + s3
for word in ("1,234", "1,5", "이용자 1", "첫 화면 검색창", "지난주 보고", "네이버"):
    ok(f"기록 · 요약 칸에 '{word}' 가 없다", word not in seen)

fin = block(WEEKLY, "marketing_seal.py seal")
ok("주간 보고 — 모은 출력을 잠그는 단계가 있다", fin is not None)
rc, out, _ = run_step(w, fin, {"KEY": ""})
ok("key 가 없으면 상태만", rc == 0 and "찍지 않았다" in out and "1,234" not in out, f"rc={rc} {out[-200:]}")
rc, out, _ = run_step(w, fin, {"KEY": k1})
ok("key 가 있어도 기록에는 평문이 없다", rc == 0 and "1,234" not in out and "이용자" not in out, f"rc={rc} {out[-200:]}")
opened = M.open_sealed(out).decode() if M.MARK in out else ""
ok("key 가 있으면 잠긴 글에 다 있다",
   all(s in opened for s in ("1,234", SECRET, "첫 화면 검색창", "1,5")), opened[:300])

w = workspace({"ga4_data.py": stub("", "■ 지표\n  ✅ totalUsers   3행 4,321\n  ❌ cohortActiveUsers  InvalidArgument\n")})
rc, out, summ = run_step(w, block(WEEKLY, "scripts/ga4_data.py --probe"), {})
ok("probe — 개수만 찍는다", rc == 0 and "가능 1개 · 불가 1개" in out and "4,321" not in out + summ, out[-200:])

rc, out, _ = run_step(w, block(WEEKLY, "marketing_seal.py check"), {"KEY": "잘못된"})
ok("주간 보고 — 잘못된 열쇠면 먼저 멈춘다", rc == 2, f"rc={rc}")
ok("주간 보고 — 열쇠 확인이 실패하면 ② · ③ · 출력이 서지 않는다",
   WEEKLY.count("steps.keycheck.outcome != 'failure'") >= 4)

print("■ 작업 파일 규칙")
SENS = ("marketing_mcp.py", "ga4_data.py", "marketing_report.py", "experiments.py")
for fname, text in (("marketing_ask.yml", ASK), ("marketing_weekly.yml", WEEKLY)):
    ok(f"{fname} — 잠긴 줄 표시를 작업 파일에 쓰지 않는다", M.MARK not in text)
    ok(f"{fname} — key 칸이 있다", re.search(r"^ {6}key:\s*$", text, re.M) is not None)
    code = [x for x in text.splitlines() if not x.strip().startswith("#")]
    tees = [x.strip() for x in code if re.search(r"\btee\b", x) and "--whoami" not in x]
    ok(f"{fname} — tee 로 기록에 흘리지 않는다", not tees, tees)
    summ_bad = [x.strip() for x in code if "GITHUB_STEP_SUMMARY" in x and ("cat " in x or "$ARGS" in x)]
    ok(f"{fname} — 요약 칸에 출력을 붙이지 않는다", not summ_bad, summ_bad)
    joined, buf = [], ""
    for x in code:
        s = x.rstrip()
        if s.endswith("\\"):
            buf += s[:-1] + " "
            continue
        joined.append(buf + s)
        buf = ""
    loose, group = [], None
    for x in joined:
        s = x.strip()
        if s == "{":
            group = []
            continue
        if group is not None and s.startswith("}"):
            if "> /tmp/" not in s:
                loose += group
            group = None
            continue
        if any(f"scripts/{n}" in s for n in SENS) and "--whoami" not in s:
            if group is not None:
                group.append(s)
            elif "> /tmp/" not in s:
                loose.append(s)
    ok(f"{fname} — 숫자가 나오는 스크립트는 모두 파일로만 쓴다", not loose, loose)

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n통과 {P} · 실패 {F}")
sys.exit(1 if F else 0)
