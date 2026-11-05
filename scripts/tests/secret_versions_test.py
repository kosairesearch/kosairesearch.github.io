#!/usr/bin/env python3
"""비밀값 옛 버전 정리(scripts/secret_versions.py)와 함수 배포 작업이 버전을 쌓지 않는지.

  python3 scripts/tests/secret_versions_test.py

  ① 계획 — 함수가 가리키는 버전과 가장 새 켜짐 버전만 남기고, 켜짐 · 꺼짐(돈을 받는 상태) 옛 버전을 지운다.
     지운 버전은 세지 않고, 켜짐 버전이 없는 비밀값은 건드리지 않는다.
  ② 함수(2세대 · 1세대) · 실행 서비스 설정에서 가리키는 버전을 읽는다('latest' · 번호 · 'projects/…/secrets/이름' ·
     실행 서비스의 별칭 secret-<uuid> 는 주석 'run.googleapis.com/secrets' 로 푼다).
  ③ 실제로 지우는 길 — 함수 목록이 비거나 못 받으면 하나도 지우지 않는다. 가리키는 버전이 이미 켜짐이 아니면 멈춘다.
     계획만 찍을 때는 지우지 않는다. 지운 뒤 다시 보고 가리키는 버전이 모두 켜짐인지 확인한다. 값은 읽지 않는다.
  ④ 함수 배포 작업 — 비밀값 셋 모두 지금 값과 같으면 새 버전을 만들지 않고, 응답 확인 뒤 정리 단계를 돌린다.
     수동 정리 작업은 수동 실행 · 읽기 권한 · 배포와 같은 동시 실행 묶음이다.
"""
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import secret_versions as V  # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


print("① 계획")
d, k = V.plan({"RESEND_API_KEY": [(n, "ENABLED") for n in range(1, 67)]}, {"RESEND_API_KEY": {66}})
ok(k["RESEND_API_KEY"] == [66] and d["RESEND_API_KEY"] == list(range(1, 66)), "66개 중 함수가 쓰는 가장 새 버전만 남긴다")
d, k = V.plan({"A": [(n, "ENABLED") for n in range(1, 6)]}, {"A": {3}})
ok(k["A"] == [3, 5] and d["A"] == [1, 2, 4], "함수가 옛 버전(3)을 가리키면 그것과 가장 새 버전(5)을 남긴다")
d, k = V.plan({"A": [(1, "DISABLED"), (2, "ENABLED")]}, {})
ok(d["A"] == [1] and k["A"] == [2], "꺼짐 버전도 돈을 받으니 지운다")
d, k = V.plan({"A": [(1, "DESTROYED"), (2, "ENABLED")]}, {})
ok(d["A"] == [] and k["A"] == [2], "이미 지운 버전은 세지 않는다")
d, k = V.plan({"A": [(1, "ENABLED"), (2, "ENABLED")]}, {"A": {"latest"}})
ok(k["A"] == [2] and d["A"] == [1], "'latest' 를 가리키면 가장 새 켜짐 버전을 남긴다")
d, k = V.plan({"A": [(1, "DISABLED"), (2, "DISABLED")]}, {})
ok(d["A"] == [] and k["A"] == [1, 2], "켜짐 버전이 없는 비밀값은 건드리지 않는다")
d, k = V.plan({"A": [(1, "ENABLED"), (7, "DISABLED"), (5, "ENABLED")]}, {})
ok(k["A"] == [5] and d["A"] == [1, 7], "가장 새 '켜짐' 버전을 남긴다(꺼진 7번이 아니라 5번)")

print("② 가리키는 버전 읽기")
fns = [
    {"name": "projects/p/locations/r/functions/socialLogin", "environment": "GEN_2",
     "serviceConfig": {"secretEnvironmentVariables": [
         {"key": "NAVER_CLIENT_ID", "secret": "NAVER_CLIENT_ID", "version": "2"},
         {"key": "KAKAO_REST_KEY", "secret": "KAKAO_REST_KEY", "version": "latest"}]}},
    {"name": "projects/p/locations/r/functions/sendResetEmail", "environment": "GEN_2",
     "serviceConfig": {"secretVolumes": [{"secret": "RESEND_API_KEY", "versions": [{"version": "66", "path": "/k"}]}]}},
    {"name": "projects/p/locations/r/functions/old", "secretEnvironmentVariables": [{"key": "X", "secret": "X", "version": "4"}]},
]
r = V.refs_from_functions(fns)
ok(r == {"NAVER_CLIENT_ID": {2}, "KAKAO_REST_KEY": {"latest"}, "RESEND_API_KEY": {66}, "X": {4}},
   "함수 설정의 환경 변수 · 볼륨 · 1세대 칸", str(r))
svcs = [{"spec": {"template": {"spec": {
    "containers": [{"env": [{"name": "GH_DISPATCH_TOKEN", "valueFrom": {"secretKeyRef": {"name": "GH_DISPATCH_TOKEN", "key": "33"}}},
                            {"name": "PLAIN", "value": "1"}]}],
    "volumes": [{"name": "v", "secret": {"secretName": "projects/1/secrets/KAKAO_ADMIN_KEY", "items": [{"key": "33", "path": "k"}]}}]}}}}]
r = V.refs_from_run(svcs)
ok(r == {"GH_DISPATCH_TOKEN": {33}, "KAKAO_ADMIN_KEY": {33}}, "실행 서비스의 secretKeyRef · 비밀값 볼륨('projects/…/secrets/이름')", str(r))
aliased = [{"spec": {"template": {
    "metadata": {"annotations": {"run.googleapis.com/secrets":
        "secret-3bc98a67-5a3a-3f3f-9b4b-f40e8525e9f4:projects/476371644387/secrets/RESEND_API_KEY,"
        "secret-a14b5144:projects/476371644387/secrets/NAVER_CLIENT_ID"}},
    "spec": {"containers": [{"env": [
        {"name": "RESEND_API_KEY", "valueFrom": {"secretKeyRef": {"name": "secret-3bc98a67-5a3a-3f3f-9b4b-f40e8525e9f4", "key": "66"}}}]}],
             "volumes": [{"name": "v", "secret": {"secretName": "secret-a14b5144", "items": [{"key": "2", "path": "k"}]}}]}}}}]
r = V.refs_from_run(aliased)
ok(r == {"RESEND_API_KEY": {66}, "NAVER_CLIENT_ID": {2}},
   "실행 서비스가 비밀값을 별칭(secret-<uuid>)으로 부르면 주석의 별칭 표로 이름을 찾는다", str(r))
ok(V.check({"A": {3}}, {"A": [(3, "DESTROYED"), (4, "ENABLED")]}) == [("A", 3)], "가리키는 버전이 지워졌으면 잡는다")
ok(V.check({"A": {"latest"}}, {"A": [(1, "DISABLED")]}) == [("A", "latest")], "'latest' 인데 켜짐이 없으면 잡는다")
ok(V.check({"A": {3, "latest"}}, {"A": [(3, "ENABLED")]}) == [], "가리키는 버전이 켜짐이면 통과")


class Cloud:
    """gcloud 를 흉내 낸다 — 지운 버전은 DESTROYED 로 바뀐다."""

    def __init__(self, fns, versions, refs_from_run=None):
        self.fns, self.versions, self.run = fns, {k: dict(v) for k, v in versions.items()}, refs_from_run or []
        self.destroyed, self.calls = [], []

    def gjson(self, args):
        self.calls.append(args)
        if args[:2] == ["functions", "list"]:
            if self.fns is None:
                raise RuntimeError("gcloud functions list 실패: 권한 없음")
            return self.fns
        if args[:3] == ["run", "services", "list"]:
            return self.run
        if args[:2] == ["secrets", "list"]:
            return [{"name": f"projects/p/secrets/{n}"} for n in self.versions]
        if args[:3] == ["secrets", "versions", "list"]:
            return [{"name": f"projects/p/secrets/{args[3]}/versions/{n}", "state": st} for n, st in self.versions[args[3]].items()]
        raise AssertionError(args)

    def destroy(self, name, num):
        self.destroyed.append((name, num))
        self.versions[name][num] = "DESTROYED"
        return True


def run_main(cloud, argv):
    V.gjson, V.destroy_version = cloud.gjson, cloud.destroy
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = V.main(argv)
    return code, buf.getvalue()


orig = (V.gjson, V.destroy_version)
print("③ 지우는 길")
base_versions = {"RESEND_API_KEY": {n: "ENABLED" for n in range(1, 67)},
                 "KAKAO_ADMIN_KEY": {n: "ENABLED" for n in range(1, 34)},
                 "NAVER_CLIENT_ID": {1: "ENABLED", 2: "ENABLED"}}
fns_now = [{"serviceConfig": {"secretEnvironmentVariables": [
    {"secret": "RESEND_API_KEY", "version": "66"}, {"secret": "KAKAO_ADMIN_KEY", "version": "33"},
    {"secret": "NAVER_CLIENT_ID", "version": "2"}]}}]
c = Cloud(fns_now, base_versions)
code, out = run_main(c, [])
ok(code == 0 and c.destroyed == [] and "계획만" in out, "--apply 가 없으면 지우지 않는다", out.splitlines()[0])
c = Cloud(fns_now, base_versions)
code, out = run_main(c, ["--apply"])
ok(code == 0 and len(c.destroyed) == 65 + 32 + 1, "--apply 면 쓰지 않는 98개를 지운다", f"{len(c.destroyed)}개")
ok(("RESEND_API_KEY", 66) not in c.destroyed and ("NAVER_CLIENT_ID", 2) not in c.destroyed, "가리키는 버전은 지우지 않는다")
ok("돈을 받는 버전 3개" in out and "확인" in out, "지운 뒤 다시 보고 남은 수를 찍는다", out.strip().splitlines()[-1])
c = Cloud([], base_versions)
code, out = run_main(c, ["--apply"])
ok(code == 2 and c.destroyed == [], "함수 목록이 비면 하나도 지우지 않는다")
c = Cloud(None, base_versions)
code, out = run_main(c, ["--apply"])
ok(code == 2 and c.destroyed == [], "함수 목록을 못 받으면 하나도 지우지 않는다")
broken = {**base_versions, "NAVER_CLIENT_ID": {1: "ENABLED", 2: "DESTROYED"}}
c = Cloud(fns_now, broken)
code, out = run_main(c, ["--apply"])
ok(code == 3 and c.destroyed == [], "가리키는 버전이 이미 켜짐이 아니면 멈춘다")
run_only = [{"spec": {"template": {"spec": {"containers": [{"env": [
    {"name": "K", "valueFrom": {"secretKeyRef": {"name": "KAKAO_ADMIN_KEY", "key": "10"}}}]}]}}}}]
c = Cloud(fns_now, base_versions, run_only)
code, out = run_main(c, ["--apply"])
ok(code == 0 and ("KAKAO_ADMIN_KEY", 10) not in c.destroyed, "실행 서비스만 가리키는 옛 버전(10)도 남긴다")
c = Cloud(fns_now, base_versions, [{"spec": {"template": {
    "metadata": {"annotations": {"run.googleapis.com/secrets": "secret-1:projects/1/secrets/RESEND_API_KEY"}},
    "spec": {"containers": [{"env": [{"name": "R", "valueFrom": {"secretKeyRef": {"name": "secret-1", "key": "66"}}}]}]}}}}])
code, out = run_main(c, ["--apply"])
ok(code == 0 and len(c.destroyed) == 98, "별칭으로 부르는 실행 서비스가 있어도 멈추지 않고 정리한다", f"종료 {code} · {len(c.destroyed)}개")
V.gjson, V.destroy_version = orig
src = (ROOT / "scripts" / "secret_versions.py").read_text(encoding="utf-8")
ok("versions access" not in src and "access_secret" not in src.lower(), "정리 스크립트는 비밀값의 값을 읽지 않는다")

print("④ 작업 파일")
wf = (ROOT / ".github" / "workflows" / "deploy_functions.yml").read_text(encoding="utf-8")
sets = [l for l in wf.splitlines() if "functions:secrets:set" in l]
ok(len(sets) == 3, "비밀값 셋을 등록하는 자리", f"{len(sets)}곳")
for name in ("RESEND_API_KEY", "KAKAO_ADMIN_KEY", "GH_DISPATCH_TOKEN"):
    step = (wf.split(f"- name: {name} 시크릿 등록") + [""])[1].split("- name:")[0]
    ok(f"gcloud secrets versions access latest --secret={name}" in step and "값이 같아 새 버전을 만들지 않습니다" in step
       and -1 < step.find("versions access") < step.find("functions:secrets:set"), f"{name} — 지금 값과 같으면 새 버전을 만들지 않는다")
    ok("echo \"$cur\"" not in step and "echo $cur" not in step, f"{name} — 지금 값을 찍지 않는다")
ok("gcloud auth activate-service-account" in wf, "gcloud 도 배포 계정으로 인증한다")
i_deploy = wf.find("- name: 함수 배포 (결제 제외)")
i_check = wf.find("- name: 수신거부 함수 응답 확인")
i_prune = wf.find("- name: 비밀값 옛 버전 정리")
i_log = wf.find("- name: 배포 로그 저장(디버그)")
ok(-1 < i_deploy < i_check < i_prune < i_log and "python3 scripts/secret_versions.py --apply" in wf[i_prune:i_log],
   "배포 · 응답 확인 뒤, 로그 저장 전에 옛 버전을 지운다")
ok(i_prune > -1 and "pipefail" in wf[i_prune:i_log], "정리가 실패하면 작업이 실패로 끝난다(tee 가 가리지 않게)")
pr = (ROOT / ".github" / "workflows" / "secret_prune.yml").read_text(encoding="utf-8")
ok("workflow_dispatch" in pr and "schedule" not in pr and "contents: read" in pr and "git push" not in pr,
   "수동 정리 작업 — 수동 실행 · 읽기 권한 · 커밋 없음")
ok("group: firebase-deploy" in pr and "group: firebase-deploy" in wf, "배포와 정리가 겹쳐 돌지 않는다")
ok("--apply" in pr and "APPLY" in pr, "정리 작업은 켜야만 지운다(기본은 계획만)")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
