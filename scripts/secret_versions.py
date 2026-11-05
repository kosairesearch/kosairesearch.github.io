#!/usr/bin/env python3
"""파이어베이스 비밀값(Secret Manager)의 옛 버전 정리 — 함수가 쓰는 버전과 가장 새 버전만 남긴다.

    python3 scripts/secret_versions.py            # 계획만 찍는다(지우지 않는다)
    python3 scripts/secret_versions.py --apply    # 지운다(되돌릴 수 없다 — 같은 값은 GitHub 시크릿에 그대로 있다)

왜 있나 (2026-11-05 사장 "firebase에서 과금되기 시작했는데 얼마 나왔는지, 왜 그 요금이 나왔는지 알아보고")
  Secret Manager 는 켜짐(ENABLED) · 꺼짐(DISABLED) 버전마다 한 달에 0.06달러(단가표 80.6원)를 받는다. 결제 계정마다 6개까지
  무료이고, 지운(DESTROYED) 버전은 받지 않는다. 함수 배포 작업(deploy_functions.yml)이 배포할 때마다 같은 값으로 비밀값 셋
  (RESEND_API_KEY · KAKAO_ADMIN_KEY · GH_DISPATCH_TOKEN)에 새 버전을 만들고 옛 버전을 지우지 않아, 2026-10-29 에 돈을 받는
  버전이 139개였다(RESEND 66 · 두 키 33씩 · 나머지 7). 8월 28 ~ 31일 배포 22번에 66개가 늘어 9월부터 달마다 8,500 ~ 10,700원이
  이 항목에서 나갔다(버전 수 × 단가표 계산). 배포 작업은 이제 값이 바뀐 비밀값만 새 버전을 만들고, 배포 뒤 이 스크립트로
  옛 버전을 지운다. 손으로는 Actions → 🔐 비밀값 옛 버전 정리(secret_prune.yml).

남기는 것 — 비밀값마다 (1) 배포된 함수 · 실행 서비스가 가리키는 버전 전부, (2) 가장 새 켜짐 버전. 나머지 켜짐 · 꺼짐 버전을 지운다.
  · 함수 목록을 못 받거나 비어 있으면 아무것도 지우지 않는다 — 쓰는 버전을 모르고 지우면 로그인 · 메일 함수가 새로 뜰 때 멈춘다.
  · 함수가 가리키는 버전이 이미 켜짐이 아니면 지우지 않고 멈춘다(사람이 볼 일이다).
  · 켜짐 버전이 하나도 없는 비밀값은 건드리지 않는다.
  · 지운 뒤 함수가 가리키는 버전이 모두 켜짐인지 다시 보고, 아니면 실패로 끝낸다.
  · 비밀값의 값은 읽지도 찍지도 않는다 — 이름 · 버전 번호 · 개수만 찍는다(실행 기록은 공개다).
지키는 검사 scripts/tests/secret_versions_test.py(check_all '비밀값 버전 정리').
"""
import argparse
import json
import subprocess
import sys

PROJECT = "kosai-ae167"
REGION = "asia-northeast3"
ALIVE = ("ENABLED", "DISABLED")      # 돈을 받는 상태


def _num(v):
    """버전 표기 → 번호(int) 또는 'latest'"""
    s = str(v if v is not None else "latest").strip()
    return int(s) if s.isdigit() else "latest"


def _secret_name(name):
    """'projects/…/secrets/이름' · '이름' → 이름"""
    return str(name or "").split("/secrets/")[-1].split("/")[0]


def plan(versions, refs):
    """versions: {이름: [(번호, 상태)]} · refs: {이름: {번호 | 'latest'}} → (지울 {이름: [번호]}, 남길 {이름: [번호]})"""
    destroy, keep = {}, {}
    for name, vs in versions.items():
        enabled = [n for n, st in vs if st == "ENABLED"]
        alive = sorted(n for n, st in vs if st in ALIVE)
        if not enabled:                 # 켜짐이 없으면 손대지 않는다
            keep[name], destroy[name] = alive, []
            continue
        k = {max(enabled)} | {n for n in refs.get(name, ()) if isinstance(n, int)}
        keep[name] = [n for n in alive if n in k]
        destroy[name] = [n for n in alive if n not in k]
    return destroy, keep


def refs_from_functions(fns):
    """gcloud functions list JSON → {비밀값: {번호 | 'latest'}} (2세대 serviceConfig · 1세대 칸 모두)"""
    out = {}
    for f in fns or []:
        sc = f.get("serviceConfig") or {}
        for e in (sc.get("secretEnvironmentVariables") or []) + (f.get("secretEnvironmentVariables") or []):
            out.setdefault(_secret_name(e.get("secret")), set()).add(_num(e.get("version")))
        for v in (sc.get("secretVolumes") or []) + (f.get("secretVolumes") or []):
            for vv in v.get("versions") or [{"version": "latest"}]:
                out.setdefault(_secret_name(v.get("secret")), set()).add(_num(vv.get("version")))
    return out


def _aliases(meta):
    """실행 서비스 설정의 별칭 표 — 'run.googleapis.com/secrets' 주석('secret-…:projects/번호/secrets/이름,…') → {별칭: 이름}.
    함수가 만든 실행 서비스는 비밀값을 이름 대신 별칭(secret-<uuid>)으로 부른다(2026-11-05 첫 실행에서 이 별칭을 이름으로
    읽어 '가리키는 버전이 없다'며 멈췄다 — 지우기 전에 멈추는 안전장치가 잡았다)."""
    out = {}
    raw = ((meta or {}).get("annotations") or {}).get("run.googleapis.com/secrets") or ""
    for part in raw.split(","):
        if ":" in part:
            alias, full = part.split(":", 1)
            out[alias.strip()] = _secret_name(full.strip())
    return out


def refs_from_run(services):
    """gcloud run services list JSON → {비밀값: {번호 | 'latest'}} (환경 변수의 secretKeyRef · 비밀값 볼륨 · 별칭 풀기)"""
    out = {}
    for s in services or []:
        tmpl = (s.get("spec") or {}).get("template") or {}
        spec = tmpl.get("spec") or {}
        names = {**_aliases(s.get("metadata")), **_aliases(tmpl.get("metadata"))}

        def real(n):
            return names.get(str(n or ""), _secret_name(n))
        for c in spec.get("containers") or []:
            for e in c.get("env") or []:
                ref = (e.get("valueFrom") or {}).get("secretKeyRef")
                if ref:
                    out.setdefault(real(ref.get("name")), set()).add(_num(ref.get("key")))
        for v in spec.get("volumes") or []:
            sec = v.get("secret")
            if sec:
                for it in sec.get("items") or [{"key": "latest"}]:
                    out.setdefault(real(sec.get("secretName")), set()).add(_num(it.get("key")))
    return out


def check(refs, versions):
    """함수가 가리키는 버전이 켜짐인지 — 아니면 [(비밀값, 번호)]"""
    bad = []
    for name, rs in sorted(refs.items()):
        states = dict(versions.get(name, []))
        enabled = [n for n, st in versions.get(name, []) if st == "ENABLED"]
        for r in sorted(rs, key=str):
            if (r == "latest" and not enabled) or (r != "latest" and states.get(r) != "ENABLED"):
                bad.append((name, r))
    return bad


def alive_count(versions):
    return sum(1 for vs in versions.values() for _, st in vs if st in ALIVE)


def gjson(args):
    r = subprocess.run(["gcloud", *args, "--project", PROJECT, "--format=json"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError("gcloud " + " ".join(args[:3]) + " 실패: " + (r.stderr or "").strip()[-300:])
    return json.loads(r.stdout or "[]")


def load_versions():
    out = {}
    for s in gjson(["secrets", "list"]):
        name = s["name"].split("/")[-1]
        out[name] = [(int(v["name"].split("/")[-1]), v.get("state")) for v in gjson(["secrets", "versions", "list", name])]
    return out


def load_refs():
    fns = gjson(["functions", "list"])
    if not fns:
        raise RuntimeError("함수 목록이 비었다 — 쓰는 버전을 알 수 없어 지우지 않는다")
    refs = refs_from_functions(fns)
    for k, v in refs_from_run(gjson(["run", "services", "list", "--platform", "managed", "--region", REGION])).items():
        refs.setdefault(k, set()).update(v)
    return refs, len(fns)


def destroy_version(name, num):
    r = subprocess.run(["gcloud", "secrets", "versions", "destroy", str(num), "--secret", name,
                        "--project", PROJECT, "--quiet"], capture_output=True, text=True, timeout=120)
    return r.returncode == 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="비밀값 옛 버전 정리(함수가 쓰는 버전 · 가장 새 버전만 남긴다)")
    ap.add_argument("--apply", action="store_true", help="지운다(없으면 계획만 찍는다)")
    a = ap.parse_args(argv)
    try:
        refs, nf = load_refs()
        versions = load_versions()
    except Exception as e:
        print(f"⛔ {e}")
        return 2
    destroy, keep = plan(versions, refs)
    print(f"함수 {nf}개 · 비밀값 {len(versions)}개 · 돈을 받는 버전 {alive_count(versions)}개 → 남길 버전 "
          f"{sum(len(v) for v in keep.values())}개")
    for name in sorted(versions):
        print(f"  {name}: 남김 {keep[name]} · 지울 버전 {len(destroy[name])}개 · 함수가 가리키는 버전 "
              f"{sorted(str(x) for x in refs.get(name, ()))}")
    bad = check(refs, versions)
    if bad:
        print(f"⛔ 함수가 가리키는 버전이 켜짐이 아니다 — 지우지 않고 멈춘다: {bad}")
        return 3
    if not a.apply:
        print("(계획만 찍었다 — --apply 로 지운다)")
        return 0
    done = failed = 0
    for name in sorted(destroy):
        for num in destroy[name]:
            if destroy_version(name, num):
                done += 1
            else:
                failed += 1
    print(f"지운 버전 {done}개 · 실패 {failed}개")
    try:
        after = load_versions()
    except Exception as e:
        print(f"⛔ 지운 뒤 다시 보지 못했다: {e}")
        return 4
    bad = check(refs, after)
    if bad:
        print(f"⛔ 지운 뒤 함수가 가리키는 버전이 켜짐이 아니다: {bad}")
        return 4
    print(f"확인 — 함수가 가리키는 버전은 모두 켜짐 · 돈을 받는 버전 {alive_count(after)}개")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
