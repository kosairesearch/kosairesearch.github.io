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

console.log(fail ? `\nFAIL ${fail}건` : "\nPASS 호출부가 전부 맞다");
process.exit(fail ? 1 : 0);
