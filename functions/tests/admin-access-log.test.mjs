/* ============================================================
   관리자 접속기록 — 법이 요구하는 것을 실제로 남기는가

   왜 있는가. 개인정보처리방침 8번에 "개인정보처리시스템에 대한 접속기록을
   1년 이상 보관하고 월 1회 이상 점검한다" 고 적었다. 적어 놓고 안 하면
   안 적은 것보다 나쁘다 — 스스로 어긴 증거를 공개해 둔 셈이 된다.

   근거는 「개인정보의 안전성 확보조치 기준」 제8조다. 기록 항목이 정해져
   있다: 계정 · 접속일시 · 접속지 정보 · 처리한 정보주체 정보 · 수행업무.
   다섯 중 하나라도 빠지면 요건 미달이다.

   그리고 '어디에 붙이는가' 가 절반이다. 관리자 함수가 하나 늘었는데 거기만
   기록을 안 붙이면, 바로 그 함수로 조회한 것은 영원히 남지 않는다. 새 admin*
   함수가 생기면 여기서 걸리게 해 둔다.

   실행
     node functions/tests/admin-access-log.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const SRC = readFileSync(join(ROOT, "functions", "index.js"), "utf8");
const RULES = readFileSync(join(ROOT, "firestore.rules"), "utf8");

let pass = 0, fail = 0;
const ok = (c, m, d = "") => { c ? (pass++, console.log("  ✔", m, d)) : (fail++, console.log("  ✘", m, d)); };

/* ── ① 고시가 정한 다섯 항목을 다 남기는가 ─────────────────────── */
console.log("① 접속기록 항목 — 고시 제8조가 정한 다섯 가지");
const helper = (SRC.match(/async function logAdminAccess[\s\S]*?\n}/) || [""])[0];
ok(!!helper, "logAdminAccess 헬퍼가 있다");
for (const [field, name] of [
  ["account", "계정"], ["at:", "접속일시"], ["ip:", "접속지 정보"],
  ["subjects:", "처리한 정보주체 정보"], ["work:", "수행업무"],
]) ok(helper.includes(field), `${name}(${field.replace(":", "")})를 남긴다`);
ok(/serverTimestamp\(\)/.test(helper), "접속일시는 서버 시각으로 박는다(단말 시계를 믿지 않는다)");
ok(/x-forwarded-for/.test(helper), "프록시 뒤에서도 진짜 접속지를 집는다");
ok(/expireAt/.test(helper) && /ADMIN_LOG_DAYS/.test(helper), "보관 만료 시각을 함께 적는다");
ok(/const ADMIN_LOG_DAYS = 366/.test(SRC), "보관 366일 — 법정 최소 1년을 넘긴다");

/* ── ② 기록을 못 남겨도 조회를 막지 않는가 ────────────────────── */
console.log("\n② 기록이 실패해도 일을 막지 않는다");
ok(/try \{[\s\S]*?\} catch \(e\) \{[\s\S]*?adminAccessLog/.test(helper),
   "던지지 않고 콘솔에 남긴다 — 기록 실패로 사장님이 일을 못 하면 안 된다");

/* ── ③ 개인정보를 만지는 admin 함수에 빠짐없이 붙었는가 ────────── */
console.log("\n③ 붙일 자리에 다 붙었는가");
const NEEDS = ["adminConsentStats", "adminConsentLookup", "adminMarketingList",
               "adminUserList", "adminPurgeOrphans", "adminNotifyUnconsented",
               "adminMarketingRecheck"];
// 개인정보를 건드리지 않는 함수. 여기 있는 것만 기록이 없어도 된다.
const EXEMPT = ["adminWakeBrief"];

const bodies = {};
for (const m of SRC.matchAll(/exports\.(admin\w+)\s*=\s*onCall\(/g)) {
  const start = m.index;
  const next = SRC.indexOf("\nexports.", start + 1);
  bodies[m[1]] = SRC.slice(start, next === -1 ? SRC.length : next);
}
ok(Object.keys(bodies).length >= NEEDS.length + EXEMPT.length,
   `admin* 함수를 ${Object.keys(bodies).length}개 찾았다`);
for (const n of NEEDS) {
  ok(bodies[n] && /await logAdminAccess\(/.test(bodies[n]), `${n} 에 접속기록이 붙어 있다`);
  ok(bodies[n] && /const who = assertAdmin\(req\)/.test(bodies[n]), `${n} 이 계정을 받아 쓴다`);
}
// 새로 생긴 admin 함수가 목록 밖에 있으면 여기서 걸린다.
const unknown = Object.keys(bodies).filter((n) => !NEEDS.includes(n) && !EXEMPT.includes(n));
ok(unknown.length === 0,
   "목록에 없는 admin 함수가 없다 — 생겼다면 기록을 붙이고 이 검사에 더할 것",
   unknown.join(", "));
ok(!/await logAdminAccess\(/.test(bodies.adminWakeBrief || ""),
   "개인정보를 안 만지는 adminWakeBrief 에는 붙이지 않는다");

/* ── ④ 월 1회 점검이 실제로 도는가 ────────────────────────────── */
console.log("\n④ 월간 점검");
const rev = (SRC.match(/exports\.reviewAdminAccessLogs[\s\S]*?\n\);/) || [""])[0];
ok(!!rev, "reviewAdminAccessLogs 가 있다");
ok(/onSchedule\(/.test(rev), "사람이 아니라 기계가 돌린다");
ok(/schedule: "0 9 1 \* \*"/.test(rev), "매월 1일에 돈다(월 1회 이상)");
ok(/timeZone: "Asia\/Seoul"/.test(rev), "한국 시간 기준");
ok(/adminAccessReviews/.test(rev), "점검했다는 사실을 기록으로 남긴다(메일은 지워질 수 있다)");
ok(/alertOps\(/.test(rev), "점검 결과를 메일로 보낸다");
ok(/expireAt", "<"/.test(rev), "보관 기간이 지난 기록을 같은 자리에서 파기한다");
ok(/byAccount/.test(rev) && /byWork/.test(rev), "계정별·업무별로 세어 이상한 것이 눈에 띄게 한다");
ok(/조회 실패/.test(rev) && /alertOps\(/.test(rev),
   "점검을 못 했으면 조용히 넘어가지 않고 알린다");

/* ── ⑤ 기록이 위·변조되지 않는가 ──────────────────────────────── */
console.log("\n⑤ 기록을 아무도 못 고친다");
for (const c of ["adminAccessLogs", "adminAccessReviews"]) {
  const m = RULES.match(new RegExp(`match /${c}/\\{id\\} \\{([\\s\\S]*?)\\}`));
  ok(!!m, `${c} 규칙이 있다`);
  ok(m && /allow read, write: if false;/.test(m[1]),
     `${c} 는 읽기·쓰기 모두 닫혀 있다 — 관리자 본인도 못 고쳐야 증거가 된다`);
}

/* ── ⑥ 방침이 약속한 숫자와 코드가 같은가 ──────────────────────── */
console.log("\n⑥ 방침에 적은 것과 코드가 어긋나지 않는가");
const PRIV = readFileSync(join(ROOT, "Privacy.html"), "utf8");
ok(/접속기록을 1년 이상 보관/.test(PRIV), "방침이 1년 이상 보관을 약속하고 있다");
ok(/월 1회 이상 점검/.test(PRIV), "방침이 월 1회 이상 점검을 약속하고 있다");
ok(366 >= 365, "코드의 보관 일수가 방침의 약속(1년)을 만족한다");

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
