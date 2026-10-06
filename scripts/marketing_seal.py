"""마케팅 숫자를 공개 실행 기록에 남기지 않고 주고받는다 — 잠그기 · 열기.

왜 있나
  이 저장소는 GitHub Pages 무료 요금제라 공개이고, Actions 실행 기록(로그 · 요약 칸)도 GitHub 에 로그인한
  누구나 본다. '마케팅 숫자 물어보기'(marketing_ask.yml)가 답을 그대로 찍어 방문자 수 · 유입 경로 · 인기 종목이
  밖에서 보였고, '주간 성과 보고'도 보고서 전문을 요약 칸에 붙였다(2026-10-06 사장 "외부에서 우리 마케팅
  데이터를 보면 안되지"). 숫자를 저장소에 두지 않는다는 원칙(2026-09-13 · Firestore)이 실행 기록에서 새고 있었다.

  그래서 묻는 쪽(클로드 세션)이 열쇠 한 쌍을 만들어 공개 열쇠만 작업에 넘기고, 작업은 그 열쇠로 답을 잠가서만
  찍는다. 잠긴 글은 밖에서 봐도 뜻이 없고, 여는 열쇠(~/.kosai/marketing-key.pem)는 묻는 세션 밖으로 나가지 않는다.
  작업 입력(key)은 실행 기록의 env 줄에 그대로 보이므로 공개 열쇠만 넘긴다 — 대칭 암호를 넘기면 같이 보인다.

쓰는 법(클로드 세션 — .claude/skills/마케팅/SKILL.md '숫자를 어떻게 가져오나')
  python3 scripts/marketing_seal.py newkey               # 공개 열쇠 한 줄(있으면 같은 열쇠를 다시 찍는다)
  → marketing_ask.yml 을 inputs {"tool": …, "args": …, "key": "<그 한 줄>"} 로 돌린다
  python3 scripts/marketing_seal.py open --job <job id>  # 실행 기록을 받아 답을 연다

작업 안
  python3 scripts/marketing_seal.py check --key "$KEY"                     # 열쇠가 쓸 만한지 먼저 본다
  python3 scripts/marketing_seal.py seal --key "$KEY" --in /tmp/answer.txt # 잠근 줄만 찍는다

방식 — 답을 gzip 으로 줄여 무작위 암호(32바이트)로 AES-256-CBC(openssl enc · pbkdf2) 잠그고, 그 암호를 공개 열쇠로
RSA-OAEP(SHA-256) 잠근다. 표준 openssl 만 쓴다(러너 · 클로드 세션 모두 깔려 있다 · 따로 설치할 것 없음).
잠긴 글은 4,000자씩 끊어 번호를 붙여 찍는다 — 긴 줄이 잘리지 않게, 순서가 섞여도 다시 붙게.
"""
import argparse
import base64
import gzip
import hashlib
import os
import re
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

KEY_FILE = Path(os.environ.get("KOSAI_MARKETING_KEY") or (Path.home() / ".kosai" / "marketing-key.pem"))
REPO = "kosairesearch/kosairesearch.github.io"
MARK = "KOSAI-SEALED"
CHUNK = 4000
ITER = "200000"
OAEP = ["-pkeyopt", "rsa_padding_mode:oaep", "-pkeyopt", "rsa_oaep_md:sha256", "-pkeyopt", "rsa_mgf1_md:sha256"]


class SealError(Exception):
    pass


def _openssl(*args, data=None):
    r = subprocess.run(["openssl", *args], input=data, capture_output=True)
    if r.returncode != 0:
        raise SealError("openssl " + args[0] + " 실패: " + r.stderr.decode("utf-8", "replace").strip()[:200])
    return r.stdout


def _der_of_key_file():
    return _openssl("pkey", "-in", str(KEY_FILE), "-pubout", "-outform", "DER")


def _fingerprint(der):
    """공개 열쇠의 지문 — 어느 열쇠로 잠갔는지 여는 쪽이 맞춰 본다(열쇠를 새로 만들었으면 옛 답은 못 연다)."""
    return hashlib.sha256(der).hexdigest()[:16]


def newkey(fresh=False):
    """열쇠 한 쌍을 만들고(있으면 그대로 쓴다) 공개 열쇠를 한 줄(DER 의 base64)로 돌려준다."""
    if fresh and KEY_FILE.exists():
        KEY_FILE.unlink()
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(KEY_FILE.parent, 0o700)
        old = os.umask(0o077)
        try:
            _openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072", "-out", str(KEY_FILE))
        finally:
            os.umask(old)
    return base64.b64encode(_der_of_key_file()).decode("ascii")


def public_key(key_b64):
    """작업에 넘어온 key(한 줄) → (PEM, DER). newkey 가 찍는 DER 꼴과 PEM 꼴 둘 다 받는다.
    RSA 2048비트 이상 공개 열쇠가 아니면 SealError — 그때 작업은 아무것도 찍지 않는다."""
    try:
        raw = base64.b64decode("".join((key_b64 or "").split()), validate=True)
    except Exception:
        raise SealError("key 를 읽지 못했다(base64 한 줄이어야 한다)")
    if not raw:
        raise SealError("key 가 비어 있다")
    bad = SealError("key 가 공개 열쇠가 아니다 — marketing_seal.py newkey 가 찍은 한 줄을 그대로 넣어라")
    if raw.startswith(b"-----BEGIN PUBLIC KEY-----"):
        pem = raw
    elif raw.startswith(b"-----"):
        raise bad                                   # 비밀 열쇠 등 — 공개 열쇠만 받는다
    else:
        try:
            pem = _openssl("pkey", "-pubin", "-inform", "DER", "-outform", "PEM", data=raw)
        except SealError:
            raise bad
    try:
        text = _openssl("pkey", "-pubin", "-noout", "-text", data=pem).decode("utf-8", "replace")
        der = _openssl("pkey", "-pubin", "-outform", "DER", data=pem)
    except SealError:
        raise bad
    m = re.search(r"Public-Key: \((\d+) bit\)", text)
    if "Modulus" not in text or not m or int(m.group(1)) < 2048:
        raise SealError("RSA 2048비트 이상 공개 열쇠만 받는다")
    return pem, der


def seal(key_b64, plaintext):
    """평문 바이트 → 실행 기록에 찍을 줄들. 실패하면 SealError — 평문은 어디에도 찍지 않는다."""
    pem, der = public_key(key_b64)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "pub.pem").write_bytes(pem)
        (td / "data.gz").write_bytes(gzip.compress(plaintext))
        pw = td / "pass"
        old = os.umask(0o077)
        try:
            pw.write_text(secrets.token_hex(32))
        finally:
            os.umask(old)
        _openssl("enc", "-aes-256-cbc", "-pbkdf2", "-iter", ITER, "-salt",
                 "-in", str(td / "data.gz"), "-out", str(td / "data.enc"), "-pass", f"file:{pw}")
        _openssl("pkeyutl", "-encrypt", "-pubin", "-inkey", str(td / "pub.pem"), *OAEP,
                 "-in", str(pw), "-out", str(td / "pass.enc"))
        k = base64.b64encode((td / "pass.enc").read_bytes()).decode("ascii")
        d = base64.b64encode((td / "data.enc").read_bytes()).decode("ascii")
    bid = secrets.token_hex(4)                      # 한 기록에 잠긴 덩어리가 둘 이상이어도 섞이지 않게
    parts = [d[i:i + CHUNK] for i in range(0, len(d), CHUNK)]
    lines = [f"{MARK} {bid} FOR {_fingerprint(der)}", f"{MARK} {bid} KEY {k}", f"{MARK} {bid} PARTS {len(parts)}"]
    lines += [f"{MARK} {bid} DATA {i} {p}" for i, p in enumerate(parts)]
    return lines


def _fetch_job_log(job):
    url = f"https://api.github.com/repos/{REPO}/actions/jobs/{int(job)}/logs"
    r = subprocess.run(["curl", "-sSL", "--fail", url], capture_output=True)
    if r.returncode != 0:
        raise SealError(f"실행 기록을 받지 못했다(job {job}): " + r.stderr.decode("utf-8", "replace").strip()[:200]
                        + " — mcp__github__get_job_logs 로 받아 파일에 두고 --file 로 열어도 된다")
    return r.stdout.decode("utf-8", "replace")


def _blocks(log_text):
    """기록 글(줄 앞의 시각 꼬리표가 붙어 있어도 된다)에서 잠긴 덩어리를 나온 순서대로 모은다."""
    blocks = {}
    for line in log_text.splitlines():
        i = line.find(MARK + " ")
        if i < 0:
            continue
        f = line[i:].split()
        if len(f) < 4:
            continue
        b = blocks.setdefault(f[1], {"data": {}})
        if f[2] == "DATA" and len(f) >= 5 and f[3].isdigit():
            b["data"][int(f[3])] = f[4]
        elif f[2] in ("FOR", "KEY", "PARTS"):
            b[f[2]] = f[3]
    return list(blocks.values())


def _open_block(b, mine):
    if "KEY" not in b or "PARTS" not in b or not b["PARTS"].isdigit():
        raise SealError("잠긴 답이 끝까지 찍히지 않았다 — 실행이 도중에 멈췄다")
    n = int(b["PARTS"])
    missing = [i for i in range(n) if i not in b["data"]]
    if missing:
        raise SealError(f"잠긴 답의 조각 {len(missing)}개가 기록에 없다 — 기록을 다시 받아라")
    if b.get("FOR") and b["FOR"] != mine:
        raise SealError("다른 열쇠로 잠긴 답이다 — 지금 열쇠(newkey 가 찍는 줄)로 다시 물어라")
    body = "".join(b["data"][i] for i in range(n))
    if "***" in b["KEY"] or "***" in body:
        raise SealError("기록에서 잠긴 글 일부가 *** 로 가려졌다(시크릿 가리기와 우연히 겹침) — 다시 물어라")
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        try:
            (td / "pass.enc").write_bytes(base64.b64decode(b["KEY"], validate=True))
            (td / "data.enc").write_bytes(base64.b64decode(body, validate=True))
        except Exception:
            raise SealError("잠긴 글이 깨졌다(base64 아님) — 기록을 다시 받아라")
        _openssl("pkeyutl", "-decrypt", "-inkey", str(KEY_FILE), *OAEP,
                 "-in", str(td / "pass.enc"), "-out", str(td / "pass"))
        _openssl("enc", "-d", "-aes-256-cbc", "-pbkdf2", "-iter", ITER,
                 "-in", str(td / "data.enc"), "-out", str(td / "data.gz"), "-pass", f"file:{td / 'pass'}")
        try:
            return gzip.decompress((td / "data.gz").read_bytes())
        except Exception:
            raise SealError("잠긴 글을 풀었지만 내용이 깨졌다 — 기록을 다시 받아라")


def open_sealed(log_text):
    """실행 기록 글 → 평문 바이트. 잠긴 덩어리가 여럿이면 나온 순서대로 잇는다."""
    if not KEY_FILE.exists():
        raise SealError(f"여는 열쇠가 없다({KEY_FILE}) — 이 세션에서 newkey 로 만든 열쇠로 잠근 답만 열 수 있다")
    blocks = _blocks(log_text)
    if not blocks:
        raise SealError("잠긴 답을 찾지 못했다 — 실행이 아직 안 끝났거나(1분쯤 걸린다) key 없이 돌린 실행이다")
    mine = _fingerprint(_der_of_key_file())
    return b"\n".join(_open_block(b, mine) for b in blocks)


def main(argv=None):
    ap = argparse.ArgumentParser(description="마케팅 숫자 잠그기 · 열기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    nk = sub.add_parser("newkey", help="열쇠 한 쌍을 만들고(있으면 그대로 쓴다) 공개 열쇠를 한 줄로 찍는다")
    nk.add_argument("--fresh", action="store_true", help="있던 열쇠를 버리고 새로 만든다")
    ck = sub.add_parser("check", help="key 가 쓸 만한 공개 열쇠인지 본다(작업 안에서 묻기 전에)")
    ck.add_argument("--key", default=os.environ.get("KEY", ""))
    se = sub.add_parser("seal", help="답을 잠가 실행 기록에 찍을 줄을 낸다(작업 안에서)")
    se.add_argument("--key", default=os.environ.get("KEY", ""))
    se.add_argument("--in", dest="infile", required=True)
    op = sub.add_parser("open", help="실행 기록에서 잠긴 답을 연다")
    op.add_argument("--job", help="Actions job 번호 — 기록을 직접 받는다")
    op.add_argument("--file", help="받아 둔 기록 파일(없으면 표준 입력)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "newkey":
            print(newkey(fresh=a.fresh))
        elif a.cmd == "check":
            _, der = public_key(a.key)
            print(f"열쇠 확인 · 지문 {_fingerprint(der)}")
        elif a.cmd == "seal":
            lines = seal(a.key, Path(a.infile).read_bytes())
            print("\n".join(lines))
        else:
            if a.job:
                text = _fetch_job_log(a.job)
            elif a.file:
                text = Path(a.file).read_text(encoding="utf-8", errors="replace")
            else:
                text = sys.stdin.read()
            out = open_sealed(text).decode("utf-8", "replace")
            sys.stdout.write(out if out.endswith("\n") else out + "\n")
    except SealError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
