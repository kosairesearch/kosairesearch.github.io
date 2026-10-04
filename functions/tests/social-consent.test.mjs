/* ============================================================
   카카오 · 네이버 가입 — 새 계정의 동의가 '이번 가입에서 받은 것' 인가
   ------------------------------------------------------------
   실행:  node functions/tests/social-consent.test.mjs

   왜 있는가(2026-10-04). 카카오 · 네이버의 동의 화면(이용약관 · 개인정보 수집 ·
   이용 · 만 14세 · 마케팅)은 그 사람과 앱이 처음 연결될 때만 뜬다. 연결이 남은 채
   KOSAI 계정만 없어진 사람(탈퇴할 때 못 끊음 · 콘솔 삭제 · 미완료 계정 정리)은
   다시 가입할 때 동의 화면 없이 계정이 만들어졌고, 우리는 예전에 받은 동의를 새
   계정에 붙였다. 제공자 약관을 못 읽은 새 계정은 아무 화면도 거치지 않은 채 필수
   세 항목을 true 로 적었다(signup-notice).

   functions/index.js 의 진짜 socialLogin · deleteAccount 를 가짜 관리자 SDK(메모리)와
   가짜 카카오 · 네이버 응답으로 돌려, 경우마다 무엇이 기록되고 무엇을 돌려주는지 본다.
   ============================================================ */
import Module, { createRequire } from "node:module";

/* ── 가짜 저장소 · 관리자 SDK ─────────────────────────────── */
const S = { users: {}, docs: {}, events: [] };
function reset() { S.users = {}; S.docs = {}; S.events = []; CALLS.length = 0; }
const TS = { __ts: true };
const stamp = (ms) => ({ toDate: () => new Date(ms) });
function materialize(v) {
  if (v === TS) return stamp(Date.now());
  if (v && typeof v === "object" && !Array.isArray(v) && !(v instanceof Date) && !v.toDate) {
    const o = {};
    for (const k of Object.keys(v)) if (v[k] !== undefined) o[k] = materialize(v[k]);
    return o;
  }
  return v;
}
function merge(a, b) {
  const o = Object.assign({}, a || {});
  for (const k of Object.keys(b)) {
    const v = b[k];
    if (v && typeof v === "object" && !Array.isArray(v) && !v.toDate && o[k] && typeof o[k] === "object" && !o[k].toDate) o[k] = merge(o[k], v);
    else o[k] = v;
  }
  return o;
}
function docRef(path) {
  return {
    path, id: path.split("/").pop(),
    async get() { const d = S.docs[path]; return { exists: d != null, data: () => d, ref: docRef(path), id: path.split("/").pop() }; },
    async set(data, opt) { const m = materialize(data); S.docs[path] = opt && opt.merge ? merge(S.docs[path], m) : m; },
    async delete() { delete S.docs[path]; },
  };
}
function query(name, filters, lim) {
  return {
    where(f, op, v) { return query(name, filters.concat([[f, v]]), lim); },
    limit(n) { return query(name, filters, n); },
    async get() {
      let rows;
      if (name === "consentEvents") rows = S.events.map((e, i) => e && ({ id: "e" + i, data: () => e, ref: { delete: async () => { S.events[i] = null; } } })).filter(Boolean);
      else rows = Object.keys(S.docs).filter((p) => p.startsWith(name + "/") && p.split("/").length === 2)
        .map((p) => ({ id: p.split("/")[1], data: () => S.docs[p], ref: docRef(p) }));
      rows = rows.filter((r) => filters.every(([f, v]) => r.data()[f] === v));
      if (lim) rows = rows.slice(0, lim);
      return { docs: rows, forEach: (fn) => rows.forEach(fn), size: rows.length, empty: !rows.length };
    },
  };
}
const fs = {
  collection(name) {
    return Object.assign(query(name, [], 0), {
      doc(id) { return docRef(name + "/" + id); },
      async add(data) { if (name !== "consentEvents") throw new Error("add " + name); S.events.push(materialize(data)); },
    });
  },
  doc(path) { return docRef(path); },
};
const firestore = () => fs;
firestore.FieldValue = { serverTimestamp: () => TS, delete: () => undefined };
const authApi = {
  async getUser(uid) { const u = S.users[uid]; if (!u) { const e = new Error("no"); e.code = "auth/user-not-found"; throw e; } return u; },
  async createUser(p) { S.users[p.uid] = Object.assign({}, p); return S.users[p.uid]; },
  async updateUser(uid, p) { S.users[uid] = Object.assign({}, S.users[uid], p); return S.users[uid]; },
  async deleteUser(uid) { delete S.users[uid]; },
  async createCustomToken(uid) { return "token:" + uid; },
  async getUserByEmail(email) { const u = Object.values(S.users).find((x) => x.email === email); if (!u) { const e = new Error("no"); e.code = "auth/user-not-found"; throw e; } return u; },
};
class HttpsError extends Error { constructor(code, message, details) { super(message); this.code = code; this.details = details; } }
const SECRETS = { KAKAO_REST_KEY: "k", NAVER_CLIENT_ID: "nid", NAVER_CLIENT_SECRET: "nsec", KAKAO_ADMIN_KEY: "미설정" };
const FAKES = {
  "firebase-admin": { initializeApp() {}, auth: () => authApi, firestore },
  "firebase-functions/v2/https": { onCall: (opts, fn) => fn || opts, HttpsError },
  "firebase-functions/v2/scheduler": { onSchedule: (opts, fn) => fn || opts },
  "firebase-functions/params": { defineSecret: (name) => ({ value: () => SECRETS[name] || "" }) },
  "resend": { Resend: class { constructor() { this.emails = { send: async () => ({}) }; } } },
};
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (Object.prototype.hasOwnProperty.call(FAKES, request)) return FAKES[request];
  return origLoad.apply(this, arguments);
};
const require = createRequire(import.meta.url);
/* FN_INDEX=옛 파일 로 돌리면 고치기 전 코드가 어디서 걸리는지 본다 */
const fns = require(process.env.FN_INDEX || "../index.js");

/* ── 가짜 카카오 · 네이버 ─────────────────────────────────── */
const CALLS = [];
let SC = {};
function res(status, body) { const t = typeof body === "string" ? body : JSON.stringify(body); return { ok: status >= 200 && status < 300, status, text: async () => t }; }
globalThis.fetch = async (url, opt = {}) => {
  const u = String(url);
  const call = { url: u, method: opt.method || "GET", headers: opt.headers || {}, body: opt.body ? String(opt.body) : "" };
  CALLS.push(call);
  if (u.startsWith("https://kauth.kakao.com/oauth/token")) return res(200, { access_token: "KAT" });
  if (u.startsWith("https://kapi.kakao.com/v2/user/me")) return res(200, { id: 1, kakao_account: { profile: { nickname: "시험" } } });
  if (u.startsWith("https://kapi.kakao.com/v2/user/service_terms")) return SC.kakaoTerms();
  if (u.startsWith("https://kapi.kakao.com/v1/user/unlink")) return SC.kakaoUnlink ? SC.kakaoUnlink(call) : res(200, { id: 1 });
  if (u.includes("nid.naver.com/oauth2.0/token") && u.includes("grant_type=authorization_code")) return res(200, { access_token: "NAT", refresh_token: "NRT" });
  if (u.includes("nid.naver.com/oauth2.0/token") && u.includes("grant_type=refresh_token")) return res(200, { access_token: "NAT2" });
  if (u.includes("nid.naver.com/oauth2.0/token") && u.includes("grant_type=delete")) return res(200, { result: "success" });
  if (u.startsWith("https://nid.naver.com/oauth2.0/revoke")) return SC.naverRevoke ? SC.naverRevoke(call) : res(200, "");
  if (u.startsWith("https://openapi.naver.com/v1/nid/me")) return res(200, { response: { id: "2", email: "t@naver.com", name: "시험" } });
  if (u.startsWith("https://openapi.naver.com/v1/nid/agreement")) return SC.naverAgree();
  throw new Error("예상 못 한 주소 " + u);
};

/* ── 검사 도구 ─────────────────────────────────────────────── */
let pass = 0, fail = 0;
const eq = (name, got, want) => {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  if (g === w) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log(`FAIL  ${name} → ${g}  (기대 ${w})`); }
};
const quiet = { log: console.log, warn: console.warn, error: console.error };
async function mute(fn) {
  console.log = console.warn = console.error = () => {};
  try { return await fn(); } finally { Object.assign(console, quiet); }
}
async function login(provider, extra = {}) {
  return mute(async () => {
    try { return await fns.socialLogin({ data: Object.assign({ provider, code: "c", redirectUri: "https://kosai.kr/Login.html", state: "s", flow: 2 }, extra), rawRequest: { headers: {} } }); }
    catch (e) { return { error: e.code }; }
  });
}
const UID = { kakao: "kakao:1", naver: "naver:2" };
const consentsOf = (uid) => { const d = S.docs["users/" + uid]; return d ? (d.consents || null) : null; };
const kinds = (uid) => S.events.filter(Boolean).filter((e) => e.uid === uid).map((e) => e.kind);
const unlinkCalls = () => CALLS.filter((c) => c.url.startsWith("https://kapi.kakao.com/v1/user/unlink") || c.url.startsWith("https://nid.naver.com/oauth2.0/revoke"));
const iso = (ms) => new Date(ms).toISOString();
/* 네이버는 시간대 없는 한국 시각으로 준다 */
const kst = (ms) => new Date(ms + 9 * 3600e3).toISOString().replace("Z", "");
const DAY = 86400e3;
const kakaoTerms = (agreedMs, marketing = false) => () => res(200, { id: 1, service_terms: [
  { tag: "tos_20260820", required: true, agreed: true, agreed_at: iso(agreedMs) },
  { tag: "privacy_20260820", required: true, agreed: true, agreed_at: iso(agreedMs) },
  { tag: "age_14_over", required: true, agreed: true, agreed_at: iso(agreedMs) },
  ...(marketing ? [{ tag: "marketing_20260820", required: false, agreed: true, agreed_at: iso(agreedMs) }] : []),
] });
const naverTerms = (agreedMs, marketing = false) => () => res(200, { result: "success", agreementInfos: [
  { termCode: "terms_20260828", agreeDate: kst(agreedMs) },
  { termCode: "privacy_20260828", agreeDate: kst(agreedMs) },
  ...(marketing ? [{ termCode: "marketing_20260828", agreeDate: kst(agreedMs) }] : []),
] });
const ev = (uid, kind, ms, extra = {}) => S.events.push(Object.assign({ uid, kind, at: stamp(ms) }, extra));

/* ① 처음 가입 · 동의 화면을 방금 거침 → 제공자 동의로 계정을 만든다 */
for (const pv of ["kakao", "naver"]) {
  reset(); SC = { kakaoTerms: kakaoTerms(Date.now() - 20e3, true), naverAgree: naverTerms(Date.now() - 20e3, true) };
  const r = await login(pv);
  const c = consentsOf(UID[pv]) || {};
  eq(`① ${pv} 첫 가입 — 토큰 · 동의 화면으로 보내지 않음`, [!!r.token, r.needConsent, !!r.reauth], [true, false, false]);
  eq(`① ${pv} 첫 가입 — 제공자 동의 기록(필수 셋 · 마케팅)`, [c.method, c.age14, c.terms, c.privacy, c.marketing], [pv === "kakao" ? "kakao-sync" : "naver-consent", true, true, true, true]);
  eq(`① ${pv} 첫 가입 — 연결을 끊지 않음 · 가입 이력`, [unlinkCalls().length, kinds(UID[pv])], [0, ["signup"]]);
}

/* ② 처음 가입 · 제공자 약관을 못 읽음 → 동의 없이 만들고 우리 동의 화면으로(전에는 signup-notice 로 필수 셋을 true) */
reset(); SC = { kakaoTerms: () => res(403, { msg: "not allowed" }) };
{
  const r = await login("kakao");
  eq("② 카카오 약관 조회 실패 — 동의를 적지 않음", consentsOf("kakao:1"), null);
  eq("② 카카오 약관 조회 실패 — 토큰 · 우리 동의 화면으로", [!!r.token, r.needConsent], [true, true]);
  eq("② 카카오 약관 조회 실패 — 가입 대기 이력 · 연결 끊지 않음", [kinds("kakao:1"), unlinkCalls().length], [["signup_pending"], 0]);
}
reset(); SC = { naverAgree: () => res(200, { result: "success", agreementInfos: [] }) };
{
  const r = await login("naver");
  eq("② 네이버 약관 목록이 빔 — 반쪽 동의(필수 false)를 적지 않고 우리 동의 화면으로", [consentsOf("naver:2"), r.needConsent, unlinkCalls().length], [null, true, 0]);
}

/* ③ 연결만 남은 사람(계정 없음 · 탈퇴 기록 없음 · 옛 동의) → 연결을 끊고 제공자 동의 화면으로 다시 */
for (const pv of ["kakao", "naver"]) {
  reset(); SC = { kakaoTerms: kakaoTerms(Date.now() - 40 * DAY, true), naverAgree: naverTerms(Date.now() - 40 * DAY, true) };
  const r = await login(pv);
  eq(`③ ${pv} 연결만 남음 — reauth 를 돌려주고 계정은 만들지 않음`, [r.reauth, !!r.token, !!S.users[UID[pv]], consentsOf(UID[pv])], [true, false, false, null]);
  const u = unlinkCalls();
  eq(`③ ${pv} 연결만 남음 — 그 사람의 토큰으로 끊음`, pv === "kakao"
    ? [u.length, u[0] && u[0].method, u[0] && u[0].headers.Authorization]
    : [u.length, u[0] && u[0].method, u[0] && /(^|&)token=NAT(&|$)/.test(u[0].body) && /token_type_hint=access_token/.test(u[0].body)],
    pv === "kakao" ? [1, "POST", "Bearer KAT"] : [1, "POST", true]);
  eq(`③ ${pv} 연결만 남음 — 끊은 기록만 남김(IP · 단말 없음)`, S.events.filter(Boolean).map((e) => [e.kind, e.why, "ip" in e, "ua" in e]), [["provider_unlink", "reauth", false, false]]);

  /* ④ 다시 보낸 길 — 동의 화면을 거쳤다. 카카오는 새 동의 시각, 네이버는 옛 날짜 그대로(실측) */
  SC = { kakaoTerms: kakaoTerms(Date.now() - 5e3, false), naverAgree: naverTerms(Date.now() - 40 * DAY, false) };
  CALLS.length = 0;
  const r2 = await login(pv, { reauth: true });
  const c = consentsOf(UID[pv]) || {};
  eq(`④ ${pv} 다시 보낸 길 — 계정 · 제공자 동의(이번에 끈 마케팅은 끔)`, [!!r2.token, r2.needConsent, c.age14, c.terms, c.privacy, c.marketing], [true, false, true, true, true, false]);
  eq(`④ ${pv} 다시 보낸 길 — 더 끊지 않음 · 가입 이력`, [unlinkCalls().length, kinds(UID[pv])], [0, ["provider_unlink", "signup"]]);
  /* 제공자 시각은 Date 로, 서버 시각은 Timestamp 로 적힌다 */
  const at = c.agreedAt instanceof Date ? c.agreedAt.getTime() : c.agreedAt && c.agreedAt.toDate ? c.agreedAt.toDate().getTime() : 0;
  eq(`④ ${pv} 다시 보낸 길 — 동의 시각이 옛 날짜가 아님`, Date.now() - at < 60e3, true);
  /* 그 계정이 다음에 로그인하면 — 기존 회원이라 아무것도 묻지 않는다 */
  const r3 = await login(pv);
  eq(`④ ${pv} 다음 로그인 — 그대로 들어감`, [!!r3.token, r3.needConsent, !!r3.reauth], [true, false, false]);
}

/* ⑤ 다시 보낸 길인데 끊은 기록이 없다(기록 저장 실패 등) → 더 보내지 않고 우리 동의 화면 */
reset(); SC = { naverAgree: naverTerms(Date.now() - 40 * DAY) };
{
  const r = await login("naver", { reauth: true });
  eq("⑤ 끊은 기록 없이 돌아옴 — 두 번 보내지 않음 · 우리 동의 화면", [!!r.reauth, !!r.token, r.needConsent, consentsOf("naver:2"), unlinkCalls().length], [false, true, true, null, 0]);
}

/* ⑥ 옛 클라이언트(flow 없음) — reauth 를 모르므로 보내지 않는다. 옛 동의를 적지도 않는다 */
reset(); SC = { kakaoTerms: kakaoTerms(Date.now() - 40 * DAY) };
{
  const r = await mute(async () => fns.socialLogin({ data: { provider: "kakao", code: "c", redirectUri: "https://kosai.kr/Login.html", state: "s" }, rawRequest: { headers: {} } }));
  eq("⑥ 옛 클라이언트 — 토큰(동의 없음 → guardConsent) · 연결 끊지 않음", [!!r.token, !!r.reauth, consentsOf("kakao:1"), unlinkCalls().length], [true, false, null, 0]);
}

/* ⑦ 탈퇴하면서 연결을 끊은 사람 — 다음 연결은 동의 화면을 거친다. 네이버가 옛 날짜를 줘도 다시 묻지 않는다 */
reset(); ev("naver:2", "withdraw", Date.now() - 3 * DAY, { providerUnlinked: true }); SC = { naverAgree: naverTerms(Date.now() - 40 * DAY) };
{
  const r = await login("naver");
  eq("⑦ 끊고 탈퇴한 네이버 재가입 — 바로 가입(동의 화면 두 번 없음)", [!!r.token, !!r.reauth, r.needConsent, (consentsOf("naver:2") || {}).terms, unlinkCalls().length], [true, false, false, true, 0]);
}

/* ⑧ 탈퇴할 때 못 끊은 사람(카카오 어드민 키 미설정) — 이번에 끊고 다시 보낸다 */
reset(); ev("kakao:1", "withdraw", Date.now() - 3 * DAY, { providerUnlinked: false }); SC = { kakaoTerms: kakaoTerms(Date.now() - 40 * DAY) };
{
  const r = await login("kakao");
  eq("⑧ 못 끊고 탈퇴한 카카오 재가입 — reauth", [r.reauth, unlinkCalls().length, !!S.users["kakao:1"]], [true, 1, false]);
}

/* ⑨ 끊은 뒤 다시 연결된 적이 있다(끊은 기록보다 늦은 가입 이력) → 끊긴 상태로 보지 않는다 */
reset(); ev("kakao:1", "withdraw", Date.now() - 30 * DAY, { providerUnlinked: true }); ev("kakao:1", "signup", Date.now() - 20 * DAY);
SC = { kakaoTerms: kakaoTerms(Date.now() - 20 * DAY) };
{
  const r = await login("kakao");
  eq("⑨ 끊은 뒤 다시 연결(콘솔 삭제 등) — reauth", [r.reauth, unlinkCalls().length], [true, 1]);
}

/* ⑩ 이번에 끊기를 실패 → 우리 동의 화면에서 받는다(끝없이 오가지 않음) */
reset(); SC = { kakaoTerms: kakaoTerms(Date.now() - 40 * DAY), kakaoUnlink: () => res(401, { msg: "this access token does not exist" }) };
{
  const r = await login("kakao");
  eq("⑩ 끊기 실패 — 동의 없이 계정 · 우리 동의 화면", [!!r.reauth, !!r.token, r.needConsent, consentsOf("kakao:1"), kinds("kakao:1")], [false, true, true, null, ["signup_pending"]]);
}

/* ⑪ 기존 회원 — 동의가 다 있으면 그대로, 없으면 동의 화면으로. 연결은 절대 끊지 않는다 */
const OK = { version: "2026-08-20", method: "kakao-sync", age14: true, terms: true, privacy: true, marketing: false, agreedAt: stamp(Date.now() - 50 * DAY), kakaoTerms: [] };
reset(); S.users["kakao:1"] = { uid: "kakao:1" }; S.docs["users/kakao:1"] = { consents: OK }; SC = { kakaoTerms: kakaoTerms(Date.now() - 60 * DAY) };
{
  const r = await login("kakao");
  eq("⑪ 기존 회원 · 동의 있음 — 그대로 · 끊지 않음", [!!r.token, r.needConsent, !!r.reauth, unlinkCalls().length], [true, false, false, 0]);
}
reset(); S.users["kakao:1"] = { uid: "kakao:1" }; S.docs["users/kakao:1"] = { email: null }; SC = { kakaoTerms: kakaoTerms(Date.now() - 60 * DAY) };
{
  const r = await login("kakao");
  eq("⑪ 기존 회원 · 동의 없음 — 우리 동의 화면으로 · 끊지 않음", [!!r.token, r.needConsent, unlinkCalls().length], [true, true, 0]);
}
reset(); S.users["kakao:1"] = { uid: "kakao:1" }; S.docs["users/kakao:1"] = { consents: Object.assign({}, OK, { version: "2026-01-01" }) }; SC = { kakaoTerms: kakaoTerms(Date.now() - 60 * DAY) };
{
  const r = await login("kakao");
  eq("⑪ 기존 회원 · 옛 판 동의 — 재동의 화면으로", r.needConsent, true);
}

/* ⑫ 우리 동의 화면(체크박스)에서 마케팅을 고르지 않은 회원 — 제공자의 옛 마케팅 동의로 덮지 않는다 */
reset(); S.users["kakao:1"] = { uid: "kakao:1" };
S.docs["users/kakao:1"] = { consents: { version: "2026-08-20", method: "checkbox", age14: true, terms: true, privacy: true, marketing: false, agreedAt: stamp(Date.now() - DAY) }, marketingAt: null };
SC = { kakaoTerms: kakaoTerms(Date.now() - 60 * DAY, true) };
{
  await login("kakao");
  const c = consentsOf("kakao:1");
  eq("⑫ 체크박스 회원 — 마케팅 그대로(끔) · 방식 그대로(checkbox)", [c.marketing, c.method, S.docs["users/kakao:1"].marketingAt], [false, "checkbox", null]);
}
/* 제공자 동의 회원(한 번도 우리 설정에서 만지지 않음)은 전처럼 제공자 값에 맞춘다 */
reset(); S.users["kakao:1"] = { uid: "kakao:1" }; S.docs["users/kakao:1"] = { consents: OK };
SC = { kakaoTerms: kakaoTerms(Date.now() - 60 * DAY, true) };
{
  await login("kakao");
  eq("⑫ 제공자 동의 회원 — 마케팅을 제공자 값에 맞춤(전과 같음)", consentsOf("kakao:1").marketing, true);
}

/* ⑬ 같은 이메일의 다른 계정 — 막고, 연결은 끊지 않는다(끊어도 가입할 수 없으므로) */
reset(); S.users["google:x"] = { uid: "google:x", email: "t@naver.com" }; S.docs["users/google:x"] = { email: "t@naver.com", signupMethod: "google" };
SC = { naverAgree: naverTerms(Date.now() - 40 * DAY) };
{
  const r = await login("naver");
  eq("⑬ 이메일 중복 — already-exists · 끊지 않음 · 계정 없음", [r.error, unlinkCalls().length, !!S.users["naver:2"]], ["already-exists", 0, false]);
}

/* ⑭ 미리 깨우기 — 아무것도 읽거나 쓰지 않는다 */
reset();
{
  const r = await mute(() => fns.socialLogin({ data: { warm: true }, rawRequest: { headers: {} } }));
  eq("⑭ 미리 깨우기 — 바로 돌려줌", [r, CALLS.length, S.events.length], [{ warm: true }, 0, 0]);
}

/* ⑮ 접근 토큰은 어디에도 저장하지 않는다 */
reset(); SC = { naverAgree: naverTerms(Date.now() - 10e3) };
await login("naver");
eq("⑮ 접근 토큰 미저장", JSON.stringify([S.docs, S.events, S.users]).includes("NAT"), false);

/* ⑯ 탈퇴 — 네이버 연결은 새 창구(토큰 폐기)로 끊는다. 새 창구가 실패하면 옛 창구로 */
async function withdrawNaver() {
  S.users["naver:2"] = { uid: "naver:2" }; S.docs["users/naver:2"] = { consents: OK }; S.docs["providerTokens/naver:2"] = { refreshToken: "NRT" };
  return mute(() => fns.deleteAccount({ auth: { uid: "naver:2" }, data: {}, rawRequest: { headers: {} } }));
}
reset(); SC = {};
{
  await withdrawNaver();
  const rv = CALLS.filter((c) => c.url.startsWith("https://nid.naver.com/oauth2.0/revoke"));
  eq("⑯ 네이버 탈퇴 — 갱신 뒤 새 접근 토큰을 폐기", [rv.length, rv[0] && /(^|&)token=NAT2(&|$)/.test(rv[0].body), CALLS.some((c) => c.url.includes("grant_type=delete"))], [1, true, false]);
  eq("⑯ 네이버 탈퇴 — 끊었다고 기록 · 토큰 지움 · 계정 지움", [S.events.filter(Boolean).map((e) => [e.kind, e.providerUnlinked]), !!S.docs["providerTokens/naver:2"], !!S.users["naver:2"]], [[["withdraw", true]], false, false]);
}
reset(); SC = { naverRevoke: () => res(404, "not found") };
{
  await withdrawNaver();
  eq("⑯ 새 창구 실패 — 옛 창구로 끊음", [CALLS.some((c) => c.url.includes("grant_type=delete")), S.events.filter(Boolean).map((e) => e.providerUnlinked)], [true, [true]]);
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
