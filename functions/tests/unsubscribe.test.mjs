/* ============================================================
   마케팅 수신거부 링크 — 메일에 실리고, 로그인 없이 철회되는가
   ------------------------------------------------------------
   실행:  node functions/tests/unsubscribe.test.mjs
          FN_INDEX=<고치기 전 functions/index.js> node functions/tests/unsubscribe.test.mjs   # 고치기 전이면 걸리는지

   왜 있는가(2026-10-29 · 사장 "우리 웹사이트에서 보내는 모든 이메일에 수신거부링크가 들어있는지 확인해봐").
   처리방침 15항은 '설정 페이지에서 언제든 해제할 수 있으며, 발송되는 모든 메일 하단의 수신거부 링크로도 즉시 해제할
   수 있다'고 약속한다. 점검해 보니 링크도, 링크를 받아 처리할 곳도 없었다. 마케팅 수신에 관한 메일은 2년 재확인
   하나이고, 그 메일의 철회 방법은 로그인해야 열리는 설정 화면과 회신뿐이었다.

   functions/index.js 의 진짜 함수(marketingRecheck · unsubscribeMarketing · sendVerifyEmail · sendResetEmail)를
   가짜 관리자 SDK · 가짜 메일로 돌린다.
     ① 2년 재확인 메일 — 꼬리에 수신거부 링크, 본문 철회 방법에 그 링크, 메일 머리글 List-Unsubscribe
     ② 수신거부 표 — 회원마다 한 번 만들고 다시 쓴다(32자). 미리 보기(dryRun)는 아무것도 쓰지 않는다
     ③ 링크로 철회 — 로그인 없이 마케팅 동의가 꺼지고 이력에 남는다. 두 번 눌러도 성공(already)
     ④ 틀린 표 · 다른 회원의 표 · 없는 회원 · 표가 없는 회원 → 같은 거절(permission-denied) · 아무것도 바뀌지 않음
     ⑤ 모양이 틀린 값 → invalid-argument
     ⑥ 인증 · 비밀번호 재설정 메일에는 수신거부 줄을 싣지 않는다(회원이 요청한 안내)
     ⑦ 시험 발송(adminMarketingRecheck sample) — 관리자 본인에게만 한 통 · [시험] 제목 · 그 계정의 실제 링크로 철회된다 ·
        재확인 시계와 동의 이력은 그대로 · 계정 문서가 없으면 보내지 않는다 · 관리자가 아니면 거절
   ============================================================ */
import Module, { createRequire } from "node:module";

/* ── 가짜 저장소 · 관리자 SDK ─────────────────────────────── */
const S = { users: {}, docs: {}, sent: [], events: [] };
function reset() { S.users = {}; S.docs = {}; S.sent = []; S.events = []; }
const ts = (iso) => ({ toDate: () => new Date(iso) });
const authErr = (code) => Object.assign(new Error(code), { code });
function merge(a, b) {
  const out = Object.assign({}, a);
  for (const [k, v] of Object.entries(b || {})) {
    out[k] = (v && typeof v === "object" && !Array.isArray(v) && !(v instanceof Date) && !v.toDate && out[k] && typeof out[k] === "object")
      ? merge(out[k], v) : v;
  }
  return out;
}
function docRef(path) {
  return {
    path, id: path.split("/").pop(),
    async get() { const d = S.docs[path]; return { exists: d != null, data: () => d }; },
    async set(v, opt) { S.docs[path] = opt && opt.merge ? merge(S.docs[path] || {}, v) : v; },
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
      return { docs: rows, size: rows.length, empty: !rows.length, forEach: (fn) => rows.forEach(fn) };
    },
  };
}
const fs = {
  collection(name) {
    return Object.assign(query(name, [], 0), {
      doc(id) { return docRef(name + "/" + id); },
      async add(v) { if (name === "consentEvents") S.events.push(v); const id = "e" + Object.keys(S.docs).length; S.docs[name + "/" + id] = v; return docRef(name + "/" + id); },
    });
  },
  async runTransaction(fn) {
    return fn({
      get: async (ref) => ({ data: () => S.docs[ref.path] }),
      set: (ref, val) => { S.docs[ref.path] = Object.assign({}, S.docs[ref.path], val); },
    });
  },
};
const firestore = () => fs;
firestore.FieldValue = { serverTimestamp: () => "SERVER_TS", delete: () => undefined };
firestore.Timestamp = { fromDate: (d) => ({ toDate: () => d }) };
const authApi = {
  async getUser(uid) { const u = S.users[uid]; if (!u) throw authErr("auth/user-not-found"); return u; },
  async getUserByEmail(email) {
    const u = Object.values(S.users).find((x) => x.email === email);
    if (!u) throw authErr("auth/user-not-found");
    return u;
  },
  async generateEmailVerificationLink() { return "https://kosai-ae167.firebaseapp.com/__/auth/action?mode=verifyEmail&oobCode=CODE&apiKey=K"; },
  async generatePasswordResetLink() { return "https://kosai-ae167.firebaseapp.com/__/auth/action?mode=resetPassword&oobCode=CODE&apiKey=K"; },
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
const ok = (name, cond, detail = "") => {
  if (cond) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log(`FAIL  ${name}${detail ? " → " + detail : ""}`); }
};
const quiet = { log: console.log, error: console.error, warn: console.warn };
async function call(fn, data) {
  console.log = console.error = console.warn = () => {};
  try { return await fn({ data, rawRequest: { headers: {} } }); }
  catch (e) { return { error: e.code || String(e) }; }
  finally { Object.assign(console, quiet); }
}
async function silent(fn) {
  console.log = console.error = console.warn = () => {};
  try { return await fn(); } finally { Object.assign(console, quiet); }
}
const has = (f) => typeof f === "function";
const UID = "naver:1234567";
const TOKEN_RE = /^[A-Za-z0-9_-]{32}$/;
function seedMember(extra = {}) {
  S.docs["users/" + UID] = Object.assign({
    email: "me@kosai.kr",
    consents: { marketing: true, agreedAt: ts("2024-10-01T00:00:00Z") },
    marketingAt: ts("2024-10-01T00:00:00Z"),
  }, extra);
}

/* ── ① 2년 재확인 메일에 수신거부 링크 ─────────────────────── */
reset();
seedMember();
ok("① marketingRecheck · unsubscribeMarketing 함수가 있다", has(fns.marketingRecheck) && has(fns.unsubscribeMarketing));
if (has(fns.marketingRecheck)) await silent(() => fns.marketingRecheck());
const member = S.sent.filter((m) => m.to === "me@kosai.kr");
const token = (S.docs["users/" + UID] || {}).unsubToken;
ok("① 재확인 메일이 한 통 나간다", member.length === 1, String(member.length));
const m0 = member[0] || { html: "", headers: {} };
const link = `https://kosai.kr/auth-action.html?mode=unsubscribe&u=${encodeURIComponent(UID)}&t=${token}`;
ok("② 수신거부 표를 만들어 회원 문서에 둔다(32자)", TOKEN_RE.test(String(token)), String(token));
ok("① 꼬리에 수신거부 링크(계정 인증 화면 · 회원 번호 · 표)", m0.html.includes(`href="${link.replace(/&/g, "&amp;")}"`) && m0.html.includes(">수신거부</a>"),
   m0.html.slice(m0.html.indexOf("수신") - 80, m0.html.indexOf("수신") + 40));
ok("① 본문의 철회 방법이 그 링크를 가리킨다", m0.html.includes("이 메일 아래의 <b>수신거부</b>"));
ok("① 메일 머리글 List-Unsubscribe 도 같은 주소", (m0.headers || {})["List-Unsubscribe"] === `<${link}>`, JSON.stringify(m0.headers || {}));
ok("① 한 번에 철회하는 List-Unsubscribe-Post 는 싣지 않는다(단추를 눌러야 철회)", !("List-Unsubscribe-Post" in (m0.headers || {})));

/* 다음 회차(2년 뒤)에도 같은 표 */
S.docs["users/" + UID].marketingRecheckedAt = ts("2024-10-02T00:00:00Z");
S.sent = [];
if (has(fns.marketingRecheck)) await silent(() => fns.marketingRecheck());
const again = S.sent.filter((m) => m.to === "me@kosai.kr")[0] || { html: "" };
ok("② 한 번 만든 표를 다시 쓴다", (S.docs["users/" + UID] || {}).unsubToken === token && again.html.includes("t=" + token));

/* 미리 보기는 아무것도 쓰지 않는다 */
reset();
seedMember();
const adminReq = { auth: { token: { email: "hello@kosai.kr", email_verified: true } } };
const dry = has(fns.adminMarketingRecheck)
  ? await silent(() => fns.adminMarketingRecheck(Object.assign({ data: { dryRun: true }, rawRequest: { headers: {} } }, adminReq)).catch((e) => ({ error: e.code })))
  : {};
ok("② 미리 보기(dryRun)는 대상을 세되 표를 만들지 않고 메일도 보내지 않는다",
   dry.dryRun === true && dry.due === 1 && !(S.docs["users/" + UID] || {}).unsubToken && S.sent.length === 0, JSON.stringify(dry));

/* ── ③ 링크로 철회 ─────────────────────────────────────────── */
reset();
const T1 = "abcdefghijklmnopqrstuvwxyz012345";
seedMember({ unsubToken: T1 });
let r = has(fns.unsubscribeMarketing) ? await call(fns.unsubscribeMarketing, { u: UID, t: T1 }) : { error: "없음" };
let doc = S.docs["users/" + UID];
ok("③ 로그인 없이 철회된다", r.ok === true && r.already === false, JSON.stringify(r));
ok("③ 마케팅 동의가 꺼지고(설정 화면과 같은 칸) 다른 동의 기록은 그대로", doc.consents.marketing === false && doc.marketingAt === null
   && doc.marketingOffAt === "SERVER_TS" && !!doc.consents.agreedAt, JSON.stringify(doc.consents));
ok("③ 이력에 marketing_off · 경로 email_link 로 남는다", S.events.length === 1 && S.events[0].kind === "marketing_off"
   && S.events[0].via === "email_link" && S.events[0].uid === UID && S.events[0].email === "me@kosai.kr", JSON.stringify(S.events));
r = has(fns.unsubscribeMarketing) ? await call(fns.unsubscribeMarketing, { u: UID, t: T1 }) : {};
ok("③ 두 번 눌러도 성공(already) · 이력은 늘지 않는다", r.ok === true && r.already === true && S.events.length === 1, JSON.stringify(r));

/* ── ④ 거절은 모두 같은 모양 ─────────────────────────────── */
reset();
seedMember({ unsubToken: T1 });
S.docs["users/other"] = { email: "o@kosai.kr", consents: { marketing: true }, unsubToken: "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ" };
S.docs["users/notoken"] = { email: "n@kosai.kr", consents: { marketing: true } };
const before = JSON.stringify(S.docs);
const cases = [
  ["틀린 표", { u: UID, t: "abcdefghijklmnopqrstuvwxyz01234X" }],
  ["다른 회원의 표", { u: UID, t: "ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ" }],
  ["없는 회원", { u: "nobody", t: T1 }],
  ["표가 없는 회원", { u: "notoken", t: T1 }],
];
for (const [name, data] of cases) {
  r = has(fns.unsubscribeMarketing) ? await call(fns.unsubscribeMarketing, data) : {};
  ok(`④ ${name} → permission-denied`, r.error === "permission-denied", JSON.stringify(r));
}
ok("④ 거절된 요청은 아무것도 바꾸지 않는다", JSON.stringify(S.docs) === before && S.events.length === 0);

/* ── ⑤ 모양이 틀린 값 ─────────────────────────────────────── */
for (const [name, data] of [["표가 짧다", { u: UID, t: "short" }], ["표에 쓸 수 없는 글자", { u: UID, t: "abcdefghijklmnopqrstuvwxyz0123+/" }],
  ["회원 번호 없음", { t: T1 }], ["회원 번호에 '/'", { u: "users/x", t: T1 }], ["값 없음", {}]]) {
  r = has(fns.unsubscribeMarketing) ? await call(fns.unsubscribeMarketing, data) : {};
  ok(`⑤ ${name} → invalid-argument`, r.error === "invalid-argument", JSON.stringify(r));
}

/* ── ⑥ 회원이 요청한 안내에는 수신거부 줄이 없다 ─────────────── */
reset();
S.users.u1 = { uid: "u1", email: "me@kosai.kr", emailVerified: false, providerData: [{ providerId: "password" }] };
await call(fns.sendVerifyEmail, { email: "me@kosai.kr" });
await call(fns.sendResetEmail, { email: "me@kosai.kr" });
await call(fns.sendVerifyEmail, { email: "me@kosai.kr", lang: "en" });
ok("⑥ 인증 · 비밀번호 재설정 메일(한국어 · 영어)이 나간다", S.sent.length === 3, String(S.sent.length));
ok("⑥ 그 메일들에는 수신거부 줄 · 머리글이 없다", S.sent.every((m) => !/수신거부|unsubscribe/i.test(m.html) && !m.headers));

/* ── ⑦ 시험 발송(sample) — 관리자 본인에게 한 통 · 실제 링크 · 시계와 이력은 그대로 ─────────────── */
const ADMIN_UID = "google:admin1";
const asAdmin = (data, uid = ADMIN_UID, email = "hello@kosai.kr") => has(fns.adminMarketingRecheck)
  ? silent(() => fns.adminMarketingRecheck({ data, auth: { uid, token: { email, email_verified: true } }, rawRequest: { headers: {} } })
      .catch((e) => ({ error: e.code })))
  : Promise.resolve({ error: "없음" });
reset();
seedMember();
S.docs["users/" + ADMIN_UID] = { email: "hello@kosai.kr", consents: { marketing: true, agreedAt: ts("2026-08-20T00:00:00Z") },
  marketingAt: ts("2026-08-21T00:00:00Z") };
r = await asAdmin({ sample: true });
const sm = S.sent[0] || { html: "", headers: {}, subject: "" };
const at = (S.docs["users/" + ADMIN_UID] || {}).unsubToken;
const slink = `https://kosai.kr/auth-action.html?mode=unsubscribe&u=${encodeURIComponent(ADMIN_UID)}&t=${at}`;
ok("⑦ 시험 발송은 관리자 본인에게 한 통만 간다", r.sent === true && S.sent.length === 1 && sm.to === "hello@kosai.kr",
   JSON.stringify({ r, to: S.sent.map((m) => m.to) }));
ok("⑦ 제목 앞에 [시험] · 실제와 같은 재확인 메일", sm.subject.startsWith("[시험] ") && sm.html.includes("2026-08-21") && sm.html.includes("이 메일 아래의 <b>수신거부</b>"),
   sm.subject);
ok("⑦ 링크 · 머리글은 관리자 계정의 실제 표", TOKEN_RE.test(String(at)) && sm.html.includes(`href="${slink.replace(/&/g, "&amp;")}"`)
   && (sm.headers || {})["List-Unsubscribe"] === `<${slink}>`);
ok("⑦ 재확인 시계 · 동의 이력은 건드리지 않는다", !("marketingRecheckedAt" in S.docs["users/" + ADMIN_UID]) && S.events.length === 0
   && !(S.docs["users/" + UID] || {}).unsubToken);
r = has(fns.unsubscribeMarketing) ? await call(fns.unsubscribeMarketing, { u: ADMIN_UID, t: at }) : {};
ok("⑦ 그 링크로 실제로 철회된다", r.ok === true && r.already === false && S.docs["users/" + ADMIN_UID].consents.marketing === false, JSON.stringify(r));
S.sent = [];
r = await asAdmin({ sample: true });
ok("⑦ 동의가 꺼진 계정에도 보내고(동의일 자리에 '시험 발송'), 같은 표를 다시 쓴다",
   r.sent === true && r.marketing === false && (S.sent[0] || { html: "" }).html.includes("<b>시험 발송</b>")
   && S.docs["users/" + ADMIN_UID].unsubToken === at, JSON.stringify(r));
reset();
r = await asAdmin({ sample: true });
ok("⑦ 계정 문서가 없으면 보내지 않고 문서도 만들지 않는다", r.sent === false && r.reason === "no-user-doc" && S.sent.length === 0
   && !S.docs["users/" + ADMIN_UID], JSON.stringify(r));
reset();
seedMember();
r = await asAdmin({ sample: true }, UID, "me@kosai.kr");
ok("⑦ 관리자가 아니면 거절(permission-denied) · 보내지 않는다", r.error === "permission-denied" && S.sent.length === 0, JSON.stringify(r));

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
