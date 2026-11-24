/* ============================================================
   결제 함수를 켠 진짜 functions/index.js 를 돌리는 가짜 환경
   ------------------------------------------------------------
   functions/tests 의 시험 파일들이 불러 쓴다. 이 파일은 lib/ 에 있어 시험 묶음
   (check_all.sh 의 functions/tests/*.mjs)이 따로 돌리지 않는다.

   왜 있는가. 돈이 오가는 계산을 시험 파일에 옮겨 적고 그 사본을 시험하면, 원본이
   바뀌어도 시험은 통과한다 — 옮겨 적은 사본이 원본과 같은지 따로 견주는 장치를
   붙여 왔지만 견주는 함수가 하나 빠지면 그만이다. 결제 함수는 스위치
   (KOSAI_PAYMENTS=on)를 켜야 만들어지므로, 여기서 켜고 진짜 함수를 부른다.

   바꿔 끼우는 것
     · 파이어베이스 관리자 SDK — 문서 · 질의 · 트랜잭션 · getAll · 시각 · 지우기 표시
     · 토스 — fetch 를 가로채 카드 등록 · 결제 · 취소를 기록하고 성공으로 답한다
       (failToss 로 거절도 낸다)
     · 메일(Resend) — 보낸 것을 기록만 한다
     · 시계 — Date.now() 와 new Date() 가 clock.set 으로 정한 시각을 낸다.
       함수는 클라우드 함수처럼 UTC 에서 돈다(addMonth 가 지역 시각을 쓴다).

   복합 색인. 파이어스토어는 한 질의에 '같다(==)' 와 '범위(<= · >=)' 를 서로 다른
   칸에 걸면 복합 색인이 있어야 돈다. 저장소에는 색인 설정(firestore.indexes.json)이
   없다. 그런 질의를 쓰면 indexNeeds 에 적는다 — 시험이 그 목록을 볼 수 있다.

   FN_INDEX=<다른 index.js> 로 고치기 전 파일을 돌려 볼 수 있다.
   ============================================================ */
import Module, { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve as resolvePath } from "node:path";

process.env.TZ = "UTC";
process.env.KOSAI_PAYMENTS = "on";

export const MIN = 60 * 1000, HOUR = 60 * MIN, DAY = 24 * HOUR;
export const UID = "u1";

/* ── 시계 ──────────────────────────────────────────────────── */
const RealDate = globalThis.Date;
let NOW = RealDate.parse("2026-11-02T03:00:00Z");
class FakeDate extends RealDate {
  constructor(...a) { if (a.length === 0) super(NOW); else super(...a); }
  static now() { return NOW; }
}
globalThis.Date = FakeDate;
export const clock = {
  now: () => NOW,
  set(t) { NOW = typeof t === "number" ? t : RealDate.parse(t); return NOW; },
  add(ms) { NOW += ms; return NOW; },
};

/* 한국 시간 도우미 — 함수 파일과 같은 정의 */
export const kstDayNo = (ms) => Math.floor((ms + 9 * HOUR) / DAY);
export const kstDay = (ms) => new RealDate(ms + 9 * HOUR).toISOString().slice(0, 10);
export const kstMidnightAfter = (ms) => (kstDayNo(ms) + 1) * DAY - 9 * HOUR;
/* addMonth 와 같은 달력 계산(UTC 에서 돈다) */
export function addMonthMs(ms) {
  const d = new RealDate(ms);
  const day = d.getUTCDate();
  d.setUTCMonth(d.getUTCMonth() + 1);
  if (d.getUTCDate() !== day) d.setUTCDate(0);
  return d.getTime();
}

/* ── 가짜 파이어스토어 ─────────────────────────────────────── */
export class Ts {
  constructor(ms) { this._ms = ms; }
  toMillis() { return this._ms; }
  toDate() { return new RealDate(this._ms); }
}
export const ts = (ms) => new Ts(ms);
const DEL = Object.freeze({ __kos: "delete" });
const SRV = Object.freeze({ __kos: "serverTimestamp" });
const isSpecial = (v) => v === DEL || v === SRV || (v && typeof v === "object" && (v.__union || v.__inc !== undefined));
const isPlain = (v) => v && typeof v === "object" && !Array.isArray(v) && !(v instanceof Ts) &&
  !(v instanceof RealDate) && !isSpecial(v);

export const store = new Map();          // 문서 경로 → 값
export const indexNeeds = [];            // 복합 색인이 있어야 도는 질의
export const hooks = { beforeTx: null }; // 다음 트랜잭션 직전에 한 번 부른다
let seq = 0;

function clone(v) {
  if (v instanceof Ts) return v;
  if (Array.isArray(v)) return v.map(clone);
  if (v && typeof v === "object") { const o = {}; for (const k of Object.keys(v)) o[k] = clone(v[k]); return o; }
  return v;
}
function resolveVal(v, cur) {
  if (v === SRV) return new Ts(NOW);
  if (v && v.__union) {
    const base = Array.isArray(cur) ? cur.slice() : [];
    for (const x of v.__union) if (!base.includes(x)) base.push(x);
    return base;
  }
  if (v && v.__inc !== undefined) return (typeof cur === "number" ? cur : 0) + v.__inc;
  if (v instanceof RealDate) return new Ts(v.getTime());
  if (Array.isArray(v)) return v.map((x) => resolveVal(x));
  if (isPlain(v)) {
    const o = {};
    for (const [k, x] of Object.entries(v)) if (x !== DEL) o[k] = resolveVal(x, undefined);
    return o;
  }
  return v;
}
function mergeInto(cur, patch) {
  const out = { ...(cur || {}) };
  for (const [k, v] of Object.entries(patch)) {
    if (v === DEL) { delete out[k]; continue; }
    if (isPlain(v) && isPlain(out[k])) { out[k] = mergeInto(out[k], v); continue; }
    out[k] = resolveVal(v, out[k]);
  }
  return out;
}
function write(path, val, opt) {
  store.set(path, opt && opt.merge ? mergeInto(store.get(path), val) : resolveVal(val));
}
function snapOf(path) {
  const d = store.get(path);
  return { id: path.split("/").pop(), ref: docRef(path), exists: d !== undefined,
           data: () => (d === undefined ? undefined : clone(d)) };
}
function docRef(path) {
  return {
    path, id: path.split("/").pop(),
    async get() { return snapOf(path); },
    async set(v, opt) { write(path, v, opt); },
    async update(v) { if (!store.has(path)) throw new Error("없는 문서 " + path); write(path, v, { merge: true }); },
    async delete() { store.delete(path); },
    collection(name) { return coll(path + "/" + name); },
  };
}
const valOf = (x) => (x instanceof Ts ? x.toMillis() : x);
function test(a, op, b) {
  const x = valOf(a), y = valOf(b);
  if (op === "==") return x === y;
  if (x === undefined || x === null) return false;
  if (op === "<=") return x <= y;
  if (op === ">=") return x >= y;
  if (op === "<") return x < y;
  if (op === ">") return x > y;
  throw new Error("가짜 파이어스토어가 모르는 비교 " + op);
}
function coll(name) {
  const depth = name.split("/").length + 1;
  const q = (filters, order, lim) => ({
    where(f, op, v) { return q([...filters, [f, op, v]], order, lim); },
    orderBy(f, dir = "asc") { return q(filters, [f, dir], lim); },
    limit(n) { return q(filters, order, n); },
    async get() {
      const eq = new Set(filters.filter(([, op]) => op === "==").map(([f]) => f));
      const range = new Set(filters.filter(([, op]) => op !== "==").map(([f]) => f));
      if ([...eq].some((f) => !range.has(f)) && range.size) {
        indexNeeds.push(`${name}: ${[...eq].join("·")} 같다 + ${[...range].join("·")} 범위`);
      }
      let rows = [...store.keys()]
        .filter((p) => p.startsWith(name + "/") && p.split("/").length === depth)
        .map(snapOf)
        .filter((s) => filters.every(([f, op, v]) => test((s.data() || {})[f], op, v)));
      if (order) {
        const [f, dir] = order;
        rows.sort((a, b) => {
          const x = valOf(a.data()[f]), y = valOf(b.data()[f]);
          return (x < y ? -1 : x > y ? 1 : 0) * (dir === "desc" ? -1 : 1);
        });
      }
      if (lim) rows = rows.slice(0, lim);
      return { docs: rows, size: rows.length, empty: rows.length === 0, forEach: (fn) => rows.forEach(fn) };
    },
  });
  return Object.assign(q([], null, 0), {
    doc(id) { return docRef(name + "/" + id); },
    async add(v) { const id = "auto" + (++seq); write(name + "/" + id, v); return docRef(name + "/" + id); },
  });
}
let chain = Promise.resolve();
const db = {
  doc: (path) => docRef(path),
  collection: (name) => coll(name),
  async getAll(...refs) { return refs.map((r) => snapOf(r.path)); },
  /* 트랜잭션끼리는 줄을 선다. 쓰기는 끝날 때 한꺼번에 들어간다(진짜와 같다). */
  runTransaction(fn) {
    const run = chain.then(async () => {
      if (hooks.beforeTx) { const h = hooks.beforeTx; hooks.beforeTx = null; await h(); }
      const writes = [];
      const out = await fn({
        get: async (ref) => snapOf(ref.path),
        set: (ref, v, opt) => { writes.push([ref.path, v, opt]); },
        update: (ref, v) => { writes.push([ref.path, v, { merge: true }]); },
      });
      for (const [p, v, o] of writes) write(p, v, o);
      return out;
    });
    chain = run.catch(() => {});
    return run;
  },
};
const firestore = () => db;
firestore.FieldValue = {
  serverTimestamp: () => SRV, delete: () => DEL,
  arrayUnion: (...v) => ({ __union: v }), increment: (n) => ({ __inc: n }),
};
firestore.Timestamp = { fromDate: (d) => new Ts(d.getTime()), fromMillis: (ms) => new Ts(ms), now: () => new Ts(NOW) };

/* ── 가짜 인증 · 메일 · 토스 ───────────────────────────────── */
export const S = { users: new Set(), deletedUsers: [], mails: [], toss: [], tossFail: [] };
const authApi = {
  async getUser(uid) {
    if (!S.users.has(uid)) throw Object.assign(new Error("없는 회원"), { code: "auth/user-not-found" });
    return { uid };
  },
  async deleteUser(uid) { S.users.delete(uid); S.deletedUsers.push(uid); },
};
class HttpsError extends Error {
  constructor(code, message, details) { super(message); this.code = code; this.details = details; }
}
const FAKES = {
  "firebase-admin": { initializeApp() {}, auth: () => authApi, firestore },
  "firebase-functions/v2/https": { onCall: (opts, fn) => fn || opts, HttpsError },
  "firebase-functions/v2/scheduler": { onSchedule: (opts, fn) => fn || opts },
  "firebase-functions/params": { defineSecret: (name) => ({ value: () => "test-" + name }) },
  "resend": { Resend: class { constructor() { this.emails = { send: async (m) => { S.mails.push(m); return {}; } }; } } },
};
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
  if (Object.prototype.hasOwnProperty.call(FAKES, request)) return FAKES[request];
  return origLoad.apply(this, arguments);
};

const TOSS = "https://api.tosspayments.com/v1";
const reply = (status, json) => ({ ok: status < 400, status, text: async () => JSON.stringify(json) });
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (!u.startsWith(TOSS)) throw new Error("예상 못 한 주소 " + u);
  const path = u.slice(TOSS.length);
  const body = JSON.parse(init.body || "{}");
  const idem = (init.headers || {})["Idempotency-Key"] || null;
  const f = S.tossFail.find((x) => x.re.test(path));
  S.toss.push({ path, body, idem, failed: !!f });
  if (f) {
    if (f.once) S.tossFail.splice(S.tossFail.indexOf(f), 1);
    return reply(400, { code: "REJECT", message: f.message || "카드사에서 거절했습니다." });
  }
  if (path === "/billing/authorizations/issue") {
    return reply(200, { billingKey: "bk_" + (++seq), card: { issuerCode: "11", number: "4330****1234" } });
  }
  let m;
  if ((m = /^\/billing\/([^/]+)$/.exec(path))) {
    return reply(200, { paymentKey: "pay_" + (++seq), orderId: body.orderId,
                        approvedAt: new RealDate(NOW).toISOString() });
  }
  if ((m = /^\/payments\/([^/]+)\/cancel$/.exec(path))) return reply(200, { paymentKey: m[1], status: "CANCELED" });
  return reply(404, { message: "모르는 길 " + path });
};
/* 토스가 path 에 맞는 요청을 거절하게 한다. once 면 한 번만. */
export function failToss(re, { once = false, message } = {}) { S.tossFail.push({ re, once, message }); }
/* 카드로 나간 결제 금액들(카드 등록 제외 · 거절 제외) */
export const charges = () => S.toss
  .filter((c) => /^\/billing\/(?!authorizations\/)/.test(c.path) && !c.failed).map((c) => c.body.amount);
/* 카드로 보낸 결제 요청 전부(거절 포함) — 금액이 숫자였는지 본다 */
export const chargeTries = () => S.toss.filter((c) => /^\/billing\/(?!authorizations\/)/.test(c.path));
/* 나간 취소들 */
export const cancels = () => S.toss.filter((c) => /\/cancel$/.test(c.path) && !c.failed)
  .map((c) => ({ key: c.path.split("/")[2], amount: c.body.cancelAmount }));

/* ── 진짜 함수 파일 ────────────────────────────────────────── */
const HERE = dirname(fileURLToPath(import.meta.url));
export const INDEX = process.env.FN_INDEX ? resolvePath(process.env.FN_INDEX) : join(HERE, "..", "..", "index.js");
export const SRC = readFileSync(INDEX, "utf8");
const require = createRequire(import.meta.url);
export const fns = require(INDEX);

/* ── 부르기 ────────────────────────────────────────────────── */
const quiet = { log: console.log, warn: console.warn, error: console.error };
/* 함수가 남기는 기록 줄은 시험 출력에서 뺀다. 성공하면 {data}, 실패하면 {error}. */
export async function call(name, data = {}, { uid = UID } = {}) {
  const fn = fns[name];
  if (typeof fn !== "function") return { error: { code: "no-function", message: `${name} 함수가 없다` } };
  console.log = console.warn = console.error = () => {};
  try {
    return { data: await fn({ data, auth: uid ? { uid, token: {} } : null, rawRequest: { headers: {} } }) };
  } catch (e) {
    return { error: { code: e.code || "?", message: e.message, details: e.details } };
  } finally { Object.assign(console, quiet); }
}
/* 예약 작업(onSchedule) */
export async function runJob(name) {
  const fn = fns[name];
  if (typeof fn !== "function") return { error: { code: "no-function", message: `${name} 함수가 없다` } };
  console.log = console.warn = console.error = () => {};
  try { return { data: await fn() }; }
  catch (e) { return { error: { code: e.code || "?", message: e.message } }; }
  finally { Object.assign(console, quiet); }
}

/* ── 심기 · 읽기 ───────────────────────────────────────────── */
export function reset() {
  store.clear();
  indexNeeds.length = 0;
  hooks.beforeTx = null;
  S.users.clear(); S.deletedUsers.length = 0; S.mails.length = 0; S.toss.length = 0; S.tossFail.length = 0;
  chain = Promise.resolve();
}
/* 이용 중인 구독 하나. 기본은 지금 결제한 member 14,900원 · 한 달. */
export function seedSub({ uid = UID, startMs = NOW, endMs, plan = "member", amount = 14900,
                          payKey = "pay_seed", ...rest } = {}) {
  S.users.add(uid);
  const doc = {
    status: "active", plan, billingKey: "bk_seed", customerKey: uid,
    card: { company: "11", number: "4330****1234" },
    currentPeriodStart: ts(startMs), currentPeriodEnd: ts(endMs ?? addMonthMs(startMs)),
    cancelAtPeriodEnd: false, startedAt: ts(startMs),
    lastPaymentKey: payKey,
    periodPayments: [{ key: payKey, amount, from: startMs }],
  };
  for (const [k, v] of Object.entries(rest)) { if (v === undefined) delete doc[k]; else doc[k] = v; }
  store.set(`subscriptions/${uid}`, doc);
  return doc;
}
export const sub = (uid = UID) => store.get(`subscriptions/${uid}`);
export function seedReports(tickers) {
  for (const t of tickers) store.set(`reports_paid/${t}`, { ticker: t, earnings: "실적 분석", verdict: "종합 의견" });
}
export const tickers = (n, from = 0) => Array.from({ length: n }, (_, i) => String(from + i).padStart(6, "0"));
/* 그날(한국 시간)의 열람 기록 문서 */
export const readsDoc = (ms = NOW, uid = UID) => store.get(`report_reads/${uid}_${kstDay(ms)}`);
/* 열람 기록을 직접 심는다(그날 문서 하나) */
export function seedReads(ms, list, { uid = UID, lastAt = ms } = {}) {
  store.set(`report_reads/${uid}_${kstDay(ms)}`, {
    uid, day: kstDay(ms), tickers: list.slice(), openedAt: list.map(() => ms),
    count: list.length, lastAt, updatedAt: ts(lastAt),
  });
}
export const payments = (uid = UID) => [...store.entries()]
  .filter(([p]) => p.startsWith(`payments/${uid}/items/`)).map(([, v]) => v);

/* ── 검사 도구 ─────────────────────────────────────────────── */
let pass = 0, fail = 0;
export function ok(name, cond, detail = "") {
  if (cond) { pass++; console.log("PASS  " + name); }
  else { fail++; console.log("FAIL  " + name + (detail ? "  ← " + detail : "")); }
}
export function eq(name, got, want) {
  const g = JSON.stringify(got), w = JSON.stringify(want);
  ok(name, g === w, `${g} (기대 ${w})`);
}
export const section = (t) => console.log("\n── " + t + " ──");
export function done() {
  console.log(`\n통과 ${pass} · 실패 ${fail}`);
  process.exit(fail ? 1 : 0);
}
export const won = (n) => (typeof n === "number" ? n.toLocaleString("ko-KR") + "원" : String(n));
