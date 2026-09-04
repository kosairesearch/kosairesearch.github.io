/* ============================================================
   메일 발송 횟수 제한 — 세는 법이 맞는가

   왜 있는가. 이 기능에서 제일 나쁜 결과는 막는 데 실패하는 것이 아니라
   비밀번호를 잊은 사람을 가두는 것이다. 계정을 되찾을 길이 그것뿐이다.

   그래서 '몇 통에서 막히나' 만 보지 않는다. 창이 지나면 풀리는가, 인증
   메일과 재설정 메일이 서로를 잡아먹지 않는가, 셈에 실패했을 때 막지
   않고 보내는가 — 갇히는 쪽 길을 전부 눌러 본다.

   실행
     node functions/tests/mail-quota.test.mjs
   ============================================================ */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createHash } from "node:crypto";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");
const SRC = readFileSync(join(ROOT, "functions", "index.js"), "utf8");

let pass = 0, fail = 0;
const ok = (c, m, d = "") => { c ? (pass++, console.log("  ✔", m, d)) : (fail++, console.log("  ✘", m, d)); };
const eq = (g, w, m) => ok(g === w, m, g === w ? "" : `← ${JSON.stringify(g)} (기대 ${JSON.stringify(w)})`);

/* index.js 에서 제한 값과 함수 본문을 그대로 꺼내 온다.
   베끼면 진짜 파일이 바뀌어도 검사가 통과한다. */
const limitsSrc = SRC.match(/const MAIL_LIMITS = \[([\s\S]*?)\];/);
if (!limitsSrc) { console.error("MAIL_LIMITS 를 못 찾음"); process.exit(1); }
const MAIL_LIMITS = eval("[" + limitsSrc[1] + "]");

const bodySrc = SRC.match(/async function mailQuotaTake\(db, kind, email\) \{[\s\S]*?\n\}/);
const msgSrc = SRC.match(/function mailQuotaMessage\(waitMs, lang\) \{[\s\S]*?\n\}/);
if (!bodySrc || !msgSrc) { console.error("함수를 못 찾음"); process.exit(1); }

/* 가짜 파이어스토어 — 트랜잭션과 문서 하나만 흉내 낸다. */
function fakeDb(store = new Map(), opts = {}) {
  return {
    _store: store,
    collection: () => ({ doc: (id) => ({ _id: id }) }),
    runTransaction: async (fn) => {
      if (opts.throwOnRead) throw new Error("파이어스토어 장애");
      return fn({
        get: async (ref) => ({ data: () => store.get(ref._id) }),
        set: (ref, val, o) => {
          const cur = (o && o.merge) ? (store.get(ref._id) || {}) : {};
          store.set(ref._id, { ...cur, ...val });
        },
      });
    },
  };
}

const mailQuotaTake = new Function("crypto", "MAIL_LIMITS", "console",
  `return ${bodySrc[0]}`)({ createHash }, MAIL_LIMITS, console);
const mailQuotaMessage = new Function(`return ${msgSrc[0]}`)();

const HOUR = MAIL_LIMITS.find(l => l.key === "h");
const DAY = MAIL_LIMITS.find(l => l.key === "d");

console.log("\n── 제한 값 ──");
ok(!!HOUR && !!DAY, "짧은 창과 긴 창이 둘 다 있다", `시간당 ${HOUR?.max} · 하루 ${DAY?.max}`);
ok(HOUR.max >= 3, "짧은 창이 넉넉하다(안 와서 다시 눌러 보는 것은 두세 번)", `${HOUR.max}통`);
ok(HOUR.ms <= 3 * 60 * 60 * 1000, "짧은 창이 오래 가두지 않는다", `${HOUR.ms / 3600000}시간`);
ok(DAY.max > HOUR.max, "하루 총량이 시간당보다 크다(둘이 서로 어긋나지 않게)");
ok(DAY.max < HOUR.max * 24, "하루 총량이 시간당 × 24 보다 작다(안 그러면 긴 창이 하는 일이 없다)",
   `${DAY.max} < ${HOUR.max * 24}`);

console.log("\n── 짧은 창 ──");
{
  const db = fakeDb();
  for (let i = 1; i <= HOUR.max; i++)
    ok((await mailQuotaTake(db, "reset", "a@x.com")).ok, `${i}통째는 나간다`);
  const over = await mailQuotaTake(db, "reset", "a@x.com");
  eq(over.ok, false, `${HOUR.max + 1}통째는 막힌다`);
  ok(over.waitMs > 0 && over.waitMs <= HOUR.ms, "언제 다시 되는지 알려 준다",
     `${Math.ceil(over.waitMs / 60000)}분`);
}

console.log("\n── 창이 지나면 풀리는가 (가두지 않는다) ──");
{
  const store = new Map();
  const db = fakeDb(store);
  for (let i = 0; i < HOUR.max; i++) await mailQuotaTake(db, "reset", "b@x.com");
  eq((await mailQuotaTake(db, "reset", "b@x.com")).ok, false, "먼저 막히는 것을 확인");
  // 시간을 되돌린다 — 한 시간 전에 시작한 창으로 바꾼다
  const id = [...store.keys()][0];
  const rec = store.get(id);
  rec.h = { n: rec.h.n, at: Date.now() - HOUR.ms - 1000 };
  eq((await mailQuotaTake(db, "reset", "b@x.com")).ok, true, "한 시간이 지나면 다시 나간다");
  eq(store.get(id).h.n, 1, "그때 셈이 1부터 다시 시작한다");
}

console.log("\n── 긴 창 ──");
{
  const store = new Map();
  const db = fakeDb(store);
  let sent = 0;
  for (let round = 0; round < 30; round++) {
    for (let i = 0; i < HOUR.max + 2; i++)
      if ((await mailQuotaTake(db, "reset", "c@x.com")).ok) sent++;
    const rec = store.get([...store.keys()][0]);
    rec.h = { n: rec.h.n, at: Date.now() - HOUR.ms - 1000 };   // 매번 한 시간씩 흘려보낸다
  }
  eq(sent, DAY.max, `하루 안에서는 아무리 기다려도 ${DAY.max}통을 넘지 못한다`);
}

console.log("\n── 인증 메일과 재설정 메일은 따로 센다 ──");
{
  const db = fakeDb();
  for (let i = 0; i < HOUR.max; i++) await mailQuotaTake(db, "verify", "d@x.com");
  eq((await mailQuotaTake(db, "verify", "d@x.com")).ok, false, "인증 메일이 막힌다");
  eq((await mailQuotaTake(db, "reset", "d@x.com")).ok, true,
     "그래도 비밀번호 재설정은 나간다(계정 복구 길을 막지 않는다)");
}

console.log("\n── 주소가 다르면 서로 영향이 없다 ──");
{
  const db = fakeDb();
  for (let i = 0; i < HOUR.max; i++) await mailQuotaTake(db, "reset", "e@x.com");
  eq((await mailQuotaTake(db, "reset", "e@x.com")).ok, false, "그 주소는 막힌다");
  eq((await mailQuotaTake(db, "reset", "f@x.com")).ok, true, "다른 주소는 멀쩡하다");
}

console.log("\n── 셈을 못 했을 때 (제일 중요한 자리) ──");
{
  const db = fakeDb(new Map(), { throwOnRead: true });
  const r = await mailQuotaTake(db, "reset", "g@x.com");
  eq(r.ok, true, "파이어스토어가 죽어도 막지 않고 보낸다");
}

console.log("\n── 주소를 그대로 두지 않는가 ──");
{
  const store = new Map();
  const db = fakeDb(store);
  await mailQuotaTake(db, "reset", "secret@example.com");
  const id = [...store.keys()][0];
  ok(!id.includes("secret") && !id.includes("example"), "문서 이름에 주소가 안 들어간다", id);
  ok(id.startsWith("reset_"), "어느 메일인지는 이름에서 구분된다", id);
}

console.log("\n── 걸렸을 때 하는 말 ──");
{
  ok(mailQuotaMessage(12 * 60000, "ko").includes("12분"), "몇 분 뒤인지 말해 준다");
  ok(mailQuotaMessage(3 * 3600000, "ko").includes("3시간"), "한 시간이 넘으면 시간으로 말해 준다");
  ok(!/[가-힣]/.test(mailQuotaMessage(12 * 60000, "en")), "영어 화면에는 한국어가 안 나온다",
     mailQuotaMessage(12 * 60000, "en"));
  ok(mailQuotaMessage(1000, "ko").includes("1분"), "1분 미만도 0분이라 하지 않는다");
}

console.log("\n── 부르는 자리가 맞게 짜여 있는가 ──");
{
  // 없는 주소로는 세는 문서를 만들지 않는다 — 만들면 아무나 문서를 늘릴 수 있다
  const verify = SRC.slice(SRC.indexOf("exports.sendVerifyEmail"), SRC.indexOf("exports.sendResetEmail"));
  ok(verify.indexOf("getUserByEmail") < verify.indexOf("mailQuotaTake"),
     "인증 메일 — 사용자 조회를 먼저 하고 센다");
  ok(verify.indexOf("emailVerified) return") < verify.indexOf("mailQuotaTake"),
     "인증 메일 — 이미 인증된 사람은 세지 않는다");
  ok(verify.indexOf("mailQuotaTake") < verify.indexOf("resend.emails.send"),
     "인증 메일 — 보내기 전에 센다");

  const reset = SRC.slice(SRC.indexOf("exports.sendResetEmail"), SRC.indexOf("exports.submitForm"));
  ok(reset.indexOf("generatePasswordResetLink") < reset.indexOf("mailQuotaTake"),
     "재설정 메일 — 있는 주소인지 먼저 보고 센다");
  ok(reset.indexOf("mailQuotaTake") < reset.indexOf("resend.emails.send"),
     "재설정 메일 — 보내기 전에 센다");

  ok(/match \/mailQuota\/\{id\} \{\s*allow read, write: if false;/.test(
       readFileSync(join(ROOT, "firestore.rules"), "utf8")),
     "세는 자리는 아무에게도 열지 않는다");
  ok(/resource-exhausted/.test(readFileSync(join(ROOT, "auth-util.js"), "utf8")),
     "화면이 서버 문장을 그대로 보여 준다(언제 다시 되는지가 그 안에 있다)");
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
