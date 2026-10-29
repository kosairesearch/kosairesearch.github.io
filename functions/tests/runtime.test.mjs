/* ============================================================
   함수 실행 환경 — 세 자리가 같은 판을 가리키고, 끝난 판을 쓰지 않는가
   (③ 배포 작업의 함수 목록이 함수 파일의 내보내기와 같은가 — 2026-10-29)

   왜 있는가. 함수의 노드 판은 세 자리에 적혀 있다 — 배포 설정(firebase.json
   의 runtime), 함수 패키지(functions/package.json 의 engines), 배포 작업
   (deploy_functions.yml 의 setup-node). 배포되는 판은 firebase.json 이 정하고,
   배포 도구가 함수 파일을 읽어 들이는 판은 setup-node 가 정한다. 한 자리만
   고치면 시험한 판과 올라가는 판이 달라진다.

   노드 20 은 2026-10-30 에 지원이 끝났다(Firebase 배포 도구 경고 — 그 뒤에는
   실행 환경을 올리지 않으면 배포할 수 없고, 끝난 판의 함수는 멈출 수 있다).
   2026-10-25 에 노드 22 로 올렸다. 다음 판으로 올릴 때는 세 자리를 함께 고치고,
   ENDED 에 끝난 판을 더한다.

   실행
     node functions/tests/runtime.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const read = (p) => readFileSync(join(ROOT, p), "utf8");

let pass = 0, fail = 0;
const ok = (c, m, d = "") => { c ? (pass++, console.log("  ✔", m, d)) : (fail++, console.log("  ✘", m, d)); };

// 지원이 끝난 판 — 배포 도구 경고에 적힌 날짜(끝난 날)
const ENDED = { 20: "2026-10-30" };   // 그 아래 판은 이미 끝났다

const fb = JSON.parse(read("firebase.json"));
const runtimes = (fb.functions || []).map((f) => f.runtime);
const pkg = JSON.parse(read("functions/package.json"));
const yml = read(".github/workflows/deploy_functions.yml");
const setup = [...yml.matchAll(/node-version:\s*'?(\d+)'?/g)].map((m) => m[1]);

console.log("① 세 자리가 같은 판을 가리키는가");
const fromFb = runtimes.map((r) => (/^nodejs(\d+)$/.exec(r || "") || [])[1]);
ok(runtimes.length > 0 && fromFb.every(Boolean), "firebase.json 에 nodejsNN 꼴의 runtime 이 있다", JSON.stringify(runtimes));
const want = fromFb[0];
ok(fromFb.every((v) => v === want), "firebase.json 의 함수 묶음이 모두 같은 판이다", JSON.stringify(fromFb));
ok(String(pkg.engines && pkg.engines.node) === want, "functions/package.json engines.node 가 같은 판이다",
   `${pkg.engines && pkg.engines.node} / ${want}`);
ok(setup.length > 0 && setup.every((v) => v === want), "deploy_functions.yml 의 setup-node 가 같은 판이다",
   `${setup.join(",")} / ${want}`);

console.log("\n② 지원이 끝난 판을 쓰지 않는가");
ok(!(want in ENDED) && Number(want) > Math.max(...Object.keys(ENDED).map(Number)),
   `노드 ${want} — 끝난 판(노드 ${Object.keys(ENDED).join(" · ")} 이하)보다 새 판이다`);

/* ③ 배포 작업은 올릴 함수를 이름으로 적는다(결제 함수를 빼려고 — deploy_functions.yml 주석). 목록에 없는 함수는 올라가지
   않고 아무 경고도 없다 — reviewAdminAccessLogs(9월 6일 · 아흐레)와 unsubscribeMarketing(10월 29일 · 메일 수신거부 처리,
   첫 배포에서 빠졌다)이 그렇게 빠졌다. 그래서 함수 파일의 내보내기와 목록을 견준다. 결제 함수(if (PAYMENTS_LIVE) exports.…)는
   배포 작업이 KOSAI_PAYMENTS=on 을 줄 때만 목록에 있어야 한다. */
console.log("\n③ 배포 목록이 함수 파일의 내보내기와 같은가");
const src = read("functions/index.js");
const always = [...src.matchAll(/^exports\.([A-Za-z0-9_]+)\s*=/gm)].map((m) => m[1]);
const paid = [...src.matchAll(/^if \(PAYMENTS_LIVE\) exports\.([A-Za-z0-9_]+)\s*=/gm)].map((m) => m[1]);
const other = [...src.matchAll(/^.*\bexports\.([A-Za-z0-9_]+)\s*=.*$/gm)]
  .filter((m) => !/^(if \(PAYMENTS_LIVE\) )?exports\./.test(m[0])).map((m) => m[1]);
const only = (/--only\s+(functions:[^\s\\]+)/.exec(yml) || [])[1] || "";
const listed = only.split(",").map((s) => s.replace(/^functions:/, "")).filter(Boolean);
const payOn = /KOSAI_PAYMENTS:\s*['"]?on\b/.test(yml);
ok(always.length > 0 && other.length === 0, "함수 파일의 내보내기를 모두 읽었다(그 밖의 꼴 없음)",
   `늘 ${always.length} · 결제 ${paid.length}${other.length ? " · 모르는 꼴 " + other.join(", ") : ""}`);
const missing = always.filter((f) => !listed.includes(f));
ok(listed.length > 0 && missing.length === 0, "늘 내보내는 함수는 모두 배포 목록에 있다", missing.length ? `빠짐: ${missing.join(", ")}` : `${listed.length}개`);
const stray = listed.filter((f) => !always.includes(f) && !paid.includes(f));
ok(stray.length === 0, "배포 목록에 함수 파일에 없는 이름이 없다", stray.join(", "));
const paidListed = paid.filter((f) => listed.includes(f));
ok(payOn ? paidListed.length === paid.length : paidListed.length === 0,
   payOn ? "결제를 켰다(KOSAI_PAYMENTS=on) — 결제 함수가 모두 목록에 있다" : "결제를 켜지 않았다 — 결제 함수는 목록에 없다",
   paidListed.join(", "));

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
