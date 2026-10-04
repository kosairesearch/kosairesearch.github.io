/* ============================================================
   비밀번호 재설정 메일(sendResetEmail) — 가입 여부에 맞는 결과를 돌려주는가
   ------------------------------------------------------------
   실행:  node functions/tests/reset-email.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/reset-email.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가(2026-10-04). 가입되지 않은 이메일로 '비밀번호를 잊으셨나요?'를 누르면 '처리 중 오류가
   발생했습니다. (functions/internal)' 가 떴다(사장 실사이트). 이 프로젝트는 파이어베이스의 '이메일 열거
   방지'가 켜져 있어, 없는 주소로 재설정 링크를 만들면 email-not-found 가 아니라 링크 없는 성공이 돌아오고
   관리자 SDK 가 그것을 internal-error 로 던진다(firebase-admin auth-api-request 의 응답 검사 —
   'INTERNAL ASSERT FAILED: Unable to create the email action link'). 형식이 틀린 주소는 invalid-email 이다.
   실사이트 함수에 없는 주소 · 틀린 주소를 넣어 보면 둘 다 INTERNAL 이었다(메일은 나가지 않는다).

   functions/index.js 의 진짜 sendResetEmail 을 가짜 관리자 SDK(그 동작을 흉내) · 가짜 메일로 돌려,
   경우마다 무엇을 돌려주는지 · 메일이 나가는지 · 횟수를 세는지 본다.
   ============================================================ */
import Module, { createRequire } from "node:module";

/* ── 가짜 저장소 · 관리자 SDK ─────────────────────────────── */
const S = { users: {}, docs: {}, sent: [], lookupFail: null, invalidLookup: "invalid" };
function reset() { S.users = {}; S.docs = {}; S.sent = []; S.lookupFail = null; S.invalidLookup = "invalid"; }
const BAD = /@[^@]*[^A-Za-z0-9.\-][^@]*$|\.\.|@\.|\.$/;   // 도메인에 쓸 수 없는 글자 · 빈 칸(..) — 파이어베이스가 INVALID_EMAIL 로 거절하는 꼴
const authErr = (code, msg = code) => Object.assign(new Error(msg), { code });
function docRef(path) {
  return {
    path, id: path.split("/").pop(),
    async get() { const d = S.docs[path]; return { exists: d != null, data: () => d }; },
    async set(v) { S.docs[path] = v; },
    async delete() { delete S.docs[path]; },
  };
}
function query(name, filters, lim) {
  return {
    where(f, op, v) { return query(name, filters.concat([[f, v]]), lim); },
    limit(n) { return query(name, filters, n); },
    async get() {
      let rows = Object.keys(S.docs).filter((p) => p.startsWith(name + "/") && p.split("/").length === 2)
        .map((p) => ({ id: p.split("/")[1], data: () => S.docs[p], ref: docRef(p) }));
      rows = rows.filter((r) => filters.every(([f, v]) => (r.data() || {})[f] === v));
      if (lim) rows = rows.slice(0, lim);
      return { docs: rows, size: rows.length, empty: !rows.length };
    },
  };
}
const fs = {
  collection(name) { return Object.assign(query(name, [], 0), { doc(id) { return docRef(name + "/" + id); } }); },
  async runTransaction(fn) {
    return fn({
      get: async (ref) => ({ data: () => S.docs[ref.path] }),
      set: (ref, val) => { S.docs[ref.path] = Object.assign({}, S.docs[ref.path], val); },
    });
  },
};
const firestore = () => fs;
firestore.FieldValue = { serverTimestamp: () => new Date(), delete: () => undefined };
const authApi = {
  async getUser(uid) { const u = S.users[uid]; if (!u) throw authErr("auth/user-not-found"); return u; },
  async getUserByEmail(email) {
    if (S.lookupFail) throw authErr(S.lookupFail);
    if (BAD.test(email)) {
      // 조회 창구가 틀린 주소를 어떻게 다루는지는 확인하지 못했다 — 두 경우를 다 본다
      if (S.invalidLookup === "invalid") throw authErr("auth/invalid-email");
      throw authErr("auth/user-not-found");
    }
    const u = Object.values(S.users).find((x) => x.email === email);
    if (!u) throw authErr("auth/user-not-found");
    return u;
  },
  /* 이메일 열거 방지가 켜진 프로젝트의 동작 — 없는 주소는 링크 없는 성공 → 관리자 SDK 가 internal-error 로 던진다 */
  async generatePasswordResetLink(email) {
    if (BAD.test(email)) throw authErr("auth/invalid-email");
    const u = Object.values(S.users).find((x) => x.email === email);
    if (!u) throw authErr("auth/internal-error", "INTERNAL ASSERT FAILED: Unable to create the email action link");
    return "https://kosai-ae167.firebaseapp.com/__/auth/action?mode=resetPassword&oobCode=CODE&apiKey=K&lang=ko";
  },
};
class HttpsError extends Error { constructor(code, message, details) { super(message); this.code = code; this.details = details; } }
const FAKES = {
  "firebase-admin": { initializeApp() {}, auth: () => authApi, firestore },
  "firebase-functions/v2/https": { onCall: (opts, fn) => fn || opts, HttpsError },
  "firebase-functions/v2/scheduler": { onSchedule: (opts, fn) => fn || opts },
  "firebase-functions/params": { defineSecret: () => ({ value: () => "x" }) },
  "resend": { Resend: class { constructor() { this.emails = { send: async (m) => { S.sent.push(m); return {}; } }; } } },
};
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (Object.prototype.hasOwnProperty.call(FAKES, request)) return FAKES[request];
  return origLoad.apply(this, arguments);
};
const require = createRequire(import.meta.url);
const fns = require(process.env.FN_INDEX || "../index.js");
globalThis.fetch = async (url) => { throw new Error("예상 못 한 주소 " + url); };

/* ── 검사 도구 ─────────────────────────────────────────────── */
let pass = 0, fail = 0;
const eq = (name, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log(`FAIL  ${name} → ${g}  (기대 ${w})`); }
};
const quiet = { log: console.log, error: console.error };
async function ask(email, lang = "ko") {
  console.log = console.error = () => {};
  try { return await fns.sendResetEmail({ data: { email, lang }, rawRequest: { headers: {} } }); }
  catch (e) { return { error: e.code }; }
  finally { Object.assign(console, quiet); }
}
const quotaDocs = () => Object.keys(S.docs).filter((p) => p.startsWith("mailQuota/")).length;
const pw = [{ providerId: "password" }];

/* ── ① 가입되지 않은 이메일 — 오류가 아니라 '가입되지 않음' ─────────────── */
reset();
{
  const r = await ask("kosai-check-20261004-zq7@example.com");
  eq("① 가입되지 않은 주소 → sent:false · unregistered(전에는 functions/internal)", r, { ok: true, sent: false, reason: "unregistered" });
  eq("① 메일을 보내지 않는다", S.sent.length, 0);
  eq("① 없는 주소로는 세는 문서를 만들지 않는다", quotaDocs(), 0);
}

/* ── ② 형식이 틀린 주소(사장이 넣은 'dlae@!kdjae.com') ─────────────── */
reset();
{
  eq("② 조회 창구가 invalid-email 을 주면 → invalid-argument(화면이 '올바른 이메일 형식이 아닙니다')",
     await ask("dlae@!kdjae.com"), { error: "invalid-argument" });
  S.invalidLookup = "notfound";
  eq("② 조회 창구가 '없음'으로 주면 → 가입되지 않은 이메일", await ask("dlae@!kdjae.com"), { ok: true, sent: false, reason: "unregistered" });
  eq("② 어느 쪽이든 메일 · 세는 문서 없음", [S.sent.length, quotaDocs()], [0, 0]);
  eq("② 우리 형식 검사(emailOk)에 걸리는 주소는 전처럼 invalid-argument", await ask("no-at-sign"), { error: "invalid-argument" });
}

/* ── ③ 이메일로 가입한 회원 — 전처럼 보낸다 ─────────────── */
reset();
{
  S.users["u1"] = { uid: "u1", email: "me@kosai.kr", providerData: pw };
  const r = await ask("ME@kosai.kr ");
  eq("③ 이메일 가입 회원 → sent:true", r, { ok: true, sent: true });
  eq("③ 메일 한 통 · 받는 사람 · 제목", [S.sent.length, S.sent[0] && S.sent[0].to, S.sent[0] && /비밀번호/.test(S.sent[0].subject)], [1, "me@kosai.kr", true]);
  eq("③ 메일의 버튼은 우리 계정 인증 화면(언어 표시 포함)으로 간다", /kosai\.kr\/auth-action\.html\?mode=resetPassword(&|&amp;)oobCode=CODE.*lang=ko/.test(S.sent[0].html), true);
  eq("③ 보낸 사람만 센다", quotaDocs(), 1);
  const en = await ask("me@kosai.kr", "en");
  eq("③ 영어 화면에서 부르면 영어 메일", [en.sent, /password/i.test(S.sent[1].subject) && !/[가-힣]/.test(S.sent[1].subject)], [true, true]);
}

/* ── ④ 비밀번호 없이 소셜로 가입한 계정 — 메일 대신 가입 방법 ─────────────── */
reset();
{
  S.users["kakao:1"] = { uid: "kakao:1", email: "k@kakao.com", providerData: [] };
  S.users["naver:2"] = { uid: "naver:2", email: "n@naver.com", providerData: [] };
  S.users["g1"] = { uid: "g1", email: "g@gmail.com", providerData: [{ providerId: "google.com" }] };
  eq("④ 카카오 가입 → no-password · kakao", await ask("k@kakao.com"), { ok: true, sent: false, reason: "no-password", method: "kakao" });
  eq("④ 네이버 가입 → no-password · naver", await ask("n@naver.com"), { ok: true, sent: false, reason: "no-password", method: "naver" });
  eq("④ 구글만 → no-password · google", await ask("g@gmail.com"), { ok: true, sent: false, reason: "no-password", method: "google" });
  eq("④ 메일 · 세는 문서 없음", [S.sent.length, quotaDocs()], [0, 0]);
}

/* ── ⑤ 비밀번호가 있으면 소셜 가입이어도 전처럼 보낸다(그 비밀번호로 로그인하는 사람을 막지 않는다) ── */
reset();
{
  S.users["kakao:3"] = { uid: "kakao:3", email: "k3@kakao.com", providerData: pw };
  S.users["g2"] = { uid: "g2", email: "g2@gmail.com", providerData: [{ providerId: "google.com" }, { providerId: "password" }] };
  eq("⑤ 비밀번호가 있는 카카오 계정 → sent:true", await ask("k3@kakao.com"), { ok: true, sent: true });
  eq("⑤ 비밀번호가 있는 구글 계정 → sent:true", await ask("g2@gmail.com"), { ok: true, sent: true });
  eq("⑤ 두 통", S.sent.length, 2);
}

/* ── ⑥ 이메일을 심기 전의 옛 소셜 계정(Auth 에 주소 없음 · users 문서에만) ─────────────── */
reset();
{
  S.users["naver:9"] = { uid: "naver:9", providerData: [] };
  S.docs["users/naver:9"] = { email: "old@naver.com", signupMethod: "naver" };
  eq("⑥ 옛 네이버 계정 → '가입되지 않은'이 아니라 naver", await ask("old@naver.com"), { ok: true, sent: false, reason: "no-password", method: "naver" });
  S.docs["users/ghost"] = { email: "ghost@kakao.com", signupMethod: "kakao" };   // Auth 사용자는 지워지고 문서만 남은 것
  eq("⑥ 유령 문서(계정은 없음) → 가입되지 않은 이메일", await ask("ghost@kakao.com"), { ok: true, sent: false, reason: "unregistered" });
  eq("⑥ 유령 문서는 치운다(signinHint 와 같다)", S.docs["users/ghost"], undefined);
  S.docs["users/e1"] = { email: "moved@kosai.kr", signupMethod: "email" };
  S.users["e1"] = { uid: "e1", email: "new@kosai.kr", providerData: pw };       // 로그인 주소를 바꾼 이메일 회원의 옛 주소
  eq("⑥ 옛 주소(문서에만 남은 이메일 가입) → 가입되지 않은 이메일(그 주소로는 로그인할 수 없다)", await ask("moved@kosai.kr"), { ok: true, sent: false, reason: "unregistered" });
  eq("⑥ 메일 없음", S.sent.length, 0);
}

/* ── ⑦ 조회 자체가 실패하면 — 모르는 것이므로 '가입되지 않은'이라고 하지 않는다 ─────────────── */
reset();
{
  S.lookupFail = "auth/internal-error";
  eq("⑦ Auth 조회 실패 → internal", await ask("me@kosai.kr"), { error: "internal" });
  S.lookupFail = null;
  const orig = fs.collection;
  fs.collection = (name) => { if (name === "users") throw new Error("파이어스토어 장애"); return orig(name); };
  eq("⑦ 옛 계정 조회 실패 → internal", await ask("nobody@kosai.kr"), { error: "internal" });
  fs.collection = orig;
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
