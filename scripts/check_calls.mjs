/* ============================================================
   호출부가 선언과 맞는가  (functions/ · staging/)

   왜 있는가. doRefund 에 인자를 하나 더 받게 고치면서 부르는 곳 두 군데 중
   하나(deleteAccount)를 빠뜨린 적이 있다. 인자가 한 칸씩 밀려 첫 줄에서
   터졌고, 그 결과 유료 회원은 탈퇴 자체가 막혔다.

   문법 검사로는 안 걸린다. 그 길을 실제로 지나가야만 드러나는데, 파이어베이스가
   없어 여기서는 지나가 볼 수가 없다. 그래서 세어 본다.

   두 가지를 본다.

     ① functions/index.js 안에서 함수를 부를 때 인자 수가 맞는가
     ② 화면(staging/)이 부르는 서버 함수 이름이 실제로 있는가
        — 이름을 잘못 적으면 눌러 봐야만 안다

   실행
     node scripts/check_calls.mjs
   ============================================================ */
import { readFileSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SERVER = join(ROOT, "functions", "index.js");
const STAGING = join(ROOT, "staging");

let fail = 0;
const bad = (msg) => { fail++; console.log("  FAIL " + msg); };

/* 주석을 지운다. 주석 안의 괄호·따옴표에 속지 않으려는 것이다. */
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/[^\n]*$/gm, "");

/* 괄호·중괄호·따옴표 안의 쉼표는 세지 않는다. */
function splitArgs(s) {
  if (!s.trim()) return [];
  const out = [];
  let depth = 0, cur = "", q = null;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (q) {
      if (c === "\\") { cur += s.slice(i, i + 2); i++; continue; }
      if (c === q) q = null;
      cur += c;
    } else if (c === '"' || c === "'" || c === "`") { q = c; cur += c; }
    else if ("([{".includes(c)) { depth++; cur += c; }
    else if (")]}".includes(c)) { depth--; cur += c; }
    else if (c === "," && depth === 0) { out.push(cur); cur = ""; }
    else cur += c;
  }
  out.push(cur);
  return out.map((a) => a.trim()).filter(Boolean);
}

/** s[i] 가 '(' 일 때 짝이 되는 ')' 위치. */
function matchParen(s, i) {
  let d = 0, q = null;
  for (; i < s.length; i++) {
    const c = s[i];
    if (q) { if (c === "\\") { i++; continue; } if (c === q) q = null; continue; }
    if (c === '"' || c === "'" || c === "`") q = c;
    else if (c === "(") d++;
    else if (c === ")") { d--; if (d === 0) return i; }
  }
  return -1;
}

/* ── ① 인자 수 ─────────────────────────────────────────────── */
{
  const code = strip(readFileSync(SERVER, "utf8"));
  const decls = new Map();

  const take = (name, open) => {
    if (decls.has(name)) return;
    const close = matchParen(code, open);
    if (close < 0) return;
    const params = splitArgs(code.slice(open + 1, close));
    let min = 0, rest = false;
    for (const p of params) {
      if (p.startsWith("...")) { rest = true; break; }
      if (p.includes("=")) break;
      min++;
    }
    decls.set(name, { min, max: rest ? Infinity : params.length });
  };

  for (const m of code.matchAll(/\b(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/g)) {
    take(m[1], m.index + m[0].length - 1);
  }
  // const f = (a, b) => …
  for (const m of code.matchAll(/\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(/g)) {
    const open = m.index + m[0].length - 1;
    const close = matchParen(code, open);
    if (close < 0 || !code.slice(close + 1, close + 6).includes("=>")) continue;
    take(m[1], open);
  }

  let checked = 0;
  for (const [name, d] of decls) {
    for (const m of code.matchAll(new RegExp(`(?<![\\w$.])${name}\\s*\\(`, "g"))) {
      const before = code.slice(Math.max(0, m.index - 30), m.index);
      if (/function\s+$|const\s+$/.test(before)) continue;   // 선언 자체
      const close = matchParen(code, m.index + m[0].length - 1);
      if (close < 0) continue;
      const n = splitArgs(code.slice(m.index + m[0].length, close)).length;
      checked++;
      if (n < d.min || n > d.max) {
        const line = code.slice(0, m.index).split("\n").length;
        bad(`${name}() 인자 수 — ${line}행에서 ${n}개, 선언은 ${d.min}~${d.max === Infinity ? "여러" : d.max}개`);
      }
    }
  }
  if (!fail) console.log(`  PASS 인자 수가 맞다 (선언 ${decls.size}개 · 호출 ${checked}곳)`);
}

/* ── ② 화면이 부르는 이름이 서버에 있는가 ──────────────────── */
{
  const server = new Set(
    [...readFileSync(SERVER, "utf8").matchAll(/exports\.([A-Za-z]\w*)\s*=/g)].map((m) => m[1]));

  const names = new Set();
  for (const f of readdirSync(STAGING).filter((f) => f.endsWith(".js"))) {
    const t = readFileSync(join(STAGING, f), "utf8");
    for (const re of [/\bcall\(\s*"([A-Za-z]\w*)"/g, /\bfn:\s*"([A-Za-z]\w*)"/g,
                      /httpsCallable\([^,]+,\s*"([A-Za-z]\w*)"/g]) {
      for (const m of t.matchAll(re)) names.add(m[1]);
    }
  }

  const missing = [...names].filter((n) => !server.has(n));
  if (missing.length) missing.forEach((n) => bad(`화면이 부르는 "${n}" 가 서버에 없다`));
  else console.log(`  PASS 화면이 부르는 이름이 서버에 다 있다 (${names.size}개)`);

  /* 미리보기(모의 백엔드)도 같은 이름을 알아야 한다. 다만 아래 다섯은
     미리보기에서 아예 다른 길로 가므로 없는 것이 맞다.
       confirmBilling  checkout.js 가 KOSDemo.subscribe 로 빠진다
       getReport       paywall.js 가 미리보기면 자리를 안 잡는다
       나머지 셋       로그인 계열이라 미리보기에서도 진짜 서버를 쓴다 */
  const SKIP = new Set(["confirmBilling", "getReport", "sendResetEmail", "sendVerifyEmail", "socialLogin"]);
  const demoSrc = readFileSync(join(STAGING, "demo-backend.js"), "utf8");
  const demo = new Set([...demoSrc.matchAll(/name === "([A-Za-z]\w*)"/g)].map((m) => m[1]));
  const gaps = [...names].filter((n) => !SKIP.has(n) && !demo.has(n));
  if (gaps.length) gaps.forEach((n) => bad(`미리보기가 "${n}" 를 모른다 — 켜 보면 그 버튼만 죽는다`));
  else console.log(`  PASS 미리보기도 같은 이름을 안다`);
}

/* ── ③ 돈 쓰는 함수가 카드사 열쇠를 들고 있는가 ─────────────
   deleteAccount 가 환불을 하면서 TOSS_SECRET_KEY 를 선언하지 않고 있었다.
   결제를 켜는 순간 유료 회원은 탈퇴가 막힌다 — 환불에서 실패하고, 그러면
   탈퇴를 진행하지 않기 때문이다.

   토스를 부르는 길은 toss()·charge()·doRefund() 셋뿐이다. 그중 하나라도
   지나가는 onCall/onSchedule 은 열쇠를 선언해야 한다.
   ─────────────────────────────────────────────────────────── */
{
  const raw = readFileSync(SERVER, "utf8");
  const code = strip(raw);
  // 각 export 의 본문을 정확히 자른다 — 다음 export 선언 직전까지
  /* 본문은 onCall( 의 짝이 되는 ) 까지다. 다음 export 까지로 자르면 그 사이에
     있는 최상위 헬퍼(charge·doRefund 등)까지 딸려 들어와 엉뚱한 함수가 걸린다. */
  const heads = [...code.matchAll(/(?:if \(PAYMENTS_LIVE\) )?exports\.(\w+)\s*=\s*on(?:Call|Schedule)\(/g)];
  let checked = 0;
  for (let i = 0; i < heads.length; i++) {
    const name = heads[i][1];
    const from = heads[i].index;
    const open = heads[i].index + heads[i][0].length - 1;
    const close = matchParen(code, open);
    if (close < 0) { bad(`${name}() 본문 경계를 못 찾았다 — 검사기가 고장났다`); continue; }
    const body = code.slice(from, close + 1);
    // 선언 블록은 본문 첫 '{ region' 부터 콜백 시작 전까지
    const opts = body.slice(0, body.search(/async\s*\(|\basync\s*function|\(\s*\)\s*=>/) + 1);
    let touched = false;
    /* 어떤 일을 하려면 어떤 열쇠가 있어야 하는가. 부르는 함수가 쓰는 열쇠를
       선언하지 않으면 그 자리에서 터진다 — deleteAccount 가 그래서 유료 회원
       탈퇴를 막고 있었고, 갱신 배치에 실패 알림을 붙이면서 또 그럴 뻔했다. */
    for (const [what, need, why] of [
      [/\bawait (?:toss|charge|doRefund)\s*\(/, "TOSS_SECRET_KEY", "토스를 부른다"],
      [/\bawait (?:alertOps|sendMail)\s*\(/, "RESEND_API_KEY", "메일을 보낸다"],
    ]) {
      if (!what.test(body)) continue;
      touched = true;
      if (!new RegExp(need).test(opts)) bad(`${name}() 가 ${why}는데 ${need} 를 선언하지 않았다`);
    }
    if (touched) checked++;
  }
  if (checked === 0) bad("열쇠가 필요한 함수를 하나도 못 찾았다 — 검사기가 고장났다");
  else if (!fail) console.log(`  PASS 열쇠가 필요한 함수가 그 열쇠를 들고 있다 (${checked}개)`);
}

/* ── ④ 화면이 읽는 컬렉션에 규칙이 있는가 ───────────────────
   파이어스토어는 규칙이 없으면 막는다. 그런데 막히는 것이 화면에서는 조용하다 —
   paywall 은 읽기 실패를 삼키고 '구독 없음' 으로 넘어간다. 그래서 subscriptions
   규칙이 통째로 빠져 있었는데도 아무 데서도 티가 나지 않았다. 결제를 켜는 날
   돈을 낸 사람이 '무료로 이용 중' 을 보게 되는 자리였다.
   ─────────────────────────────────────────────────────────── */
{
  const rules = readFileSync(join(ROOT, "firestore.rules"), "utf8");
  const noComment = rules.replace(/\/\/[^\n]*/g, "");

  const want = new Set();
  for (const dir of [STAGING, ROOT]) {
    for (const f of readdirSync(dir).filter((f) => f.endsWith(".js"))) {
      const t = readFileSync(join(dir, f), "utf8");
      for (const m of t.matchAll(/\b(?:doc|collection)\(db,\s*"([A-Za-z_]+)"/g)) want.add(m[1]);
    }
  }

  for (const col of [...want].sort()) {
    // 그 컬렉션을 여는 match 블록에 allow read 가 있는가
    const re = new RegExp(`match\\s+/${col}/[^{]*\\{([\\s\\S]*?)\\n    \\}`, "m");
    const m = noComment.match(re);
    if (!m) bad(`화면이 "${col}" 를 읽는데 firestore.rules 에 규칙이 없다 — 조용히 막힌다`);
    else if (!/allow\s+read/.test(m[1])) bad(`"${col}" 규칙에 allow read 가 없다 — 화면이 못 읽는다`);
  }
  if (!fail) console.log(`  PASS 화면이 읽는 컬렉션에 규칙이 있다 (${want.size}개: ${[...want].sort().join(", ")})`);

  // 돈·한도와 얽힌 컬렉션은 클라이언트 쓰기가 절대 열려 있으면 안 된다
  for (const col of ["subscriptions", "payments", "report_reads", "reports_paid"]) {
    const re = new RegExp(`match\\s+/${col}/[^{]*\\{([\\s\\S]*?)\\n    \\}`, "m");
    const m = noComment.match(re);
    if (!m) { bad(`"${col}" 규칙이 없다`); continue; }
    if (!/allow\s+write:\s*if\s+false|allow\s+read,\s*write:\s*if\s+false/.test(m[1])) {
      bad(`"${col}" 에 클라이언트 쓰기가 열려 있다 — 콘솔에서 plan 을 고칠 수 있다`);
    }
  }
}

console.log(fail ? `\nFAIL ${fail}건` : "\nPASS 호출부가 전부 맞다");
process.exit(fail ? 1 : 0);
