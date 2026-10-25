/* ============================================================
   함수 실행 환경 — 세 자리가 같은 판을 가리키고, 끝난 판을 쓰지 않는가

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

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
