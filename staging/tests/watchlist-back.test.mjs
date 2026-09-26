/* 관심종목 단추 — 뒤로·앞으로 가기로 되살아난 페이지가 지금 목록을 보이는가 (2026-09-26 사장)

   사장: "리포트 상세에서 관심종목 추가하고 뒤로가기로 목록에 돌아오면 + 가 그대로다. 새로고침해야 ✓.
   그 반대도 마찬가지." 되살아난 페이지(bfcache)는 떠날 때의 목록을 들고 있어서였다. 페이지마다 pageshow 에서
   다시 그리기는 했지만 읽는 곳이 그 옛 목록이었다. 이제 watchlist.js 가 되살아날 때(pageshow · persisted)
   기억(kos-wl-cache)으로 맞춘다. 실사이트와 스테이징이 같은 모듈을 쓰므로 둘 다 본다.

   파이어베이스는 가짜로 바꿔 끼운다 — 로그인은 된 것으로, 파이어스토어는 브라우저 저장소에 둔 '서버'로.
   가짜 구독은 붙는 순간 한 번, 그리고 같은 페이지에서 쓸 때만 답한다. 되살아난 페이지에 서버가 새 답을
   늦게 주거나 안 주는 경우와 같다. 고치기 전 모듈로 돌리면(WL_MODULE=옛 파일) 되살아난 페이지 넷이 모두
   걸린다 — 그렇게 재현을 확인했다.

   플레이라이트는 크로미움의 bfcache 를 끄고 띄운다(--disable-back-forward-cache). 그 옵션을 빼고 띄우고,
   정말 되살아났는지(persisted)도 본다. 새로 불러온 것이면 이 검사는 아무것도 안 본 것이다.

     node staging/tests/watchlist-back.test.mjs
*/
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { dirname, extname, join, normalize } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..", "..");

let chromium;
try { ({ chromium } = await import("playwright-core")); }
catch {
  console.error("playwright-core 가 없습니다.  npm install --no-save playwright-core  후 다시 실행하세요.");
  process.exit(2);
}
/* 깔려 있는 크로미움 — same-units.test.mjs 와 같은 방법 */
const CHROME = (() => {
  const base = process.env.PLAYWRIGHT_BROWSERS_PATH || "/opt/pw-browsers";
  if (!existsSync(base)) return null;
  const dirs = readdirSync(base).filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  for (const d of dirs) for (const sub of ["chrome-linux64", "chrome-linux"]) {
    const p = `${base}/${d}/${sub}/chrome`;
    if (existsSync(p)) return p;
  }
  return null;
})();
if (!CHROME) { console.error("크로미움을 찾지 못했습니다(PLAYWRIGHT_BROWSERS_PATH 확인)."); process.exit(2); }

/* 동의 기록 — 없으면 auth-state 가 동의 페이지로 보낸다. 판은 모듈에서 읽는다. */
const CONSENT_VERSION = readFileSync(join(ROOT, "staging/consent.js"), "utf8").match(/CONSENT_VERSION\s*=\s*"([^"]+)"/)[1];
const UID = "u-wl-test";

const FAKE = {
  "firebase-app": `export function initializeApp(c){ return { options: c || {} }; }`,
  "firebase-auth": `
    const U = { uid: ${JSON.stringify(UID)}, email: "t@example.com", displayName: "시험", emailVerified: true,
      providerData: [{ providerId: "google.com" }], getIdToken: async () => "t", reload: async () => {} };
    const A = { currentUser: U };
    export function getAuth(){ return A; }
    export function onAuthStateChanged(a, cb){ setTimeout(() => cb(U), 0); return () => {}; }
    export class GoogleAuthProvider { setCustomParameters(){} addScope(){} }
    const no = async () => ({});
    export const applyActionCode = no, confirmPasswordReset = no, createUserWithEmailAndPassword = no,
      deleteUser = no, signInWithCustomToken = no, signInWithEmailAndPassword = no, signInWithPopup = no,
      signOut = no, verifyPasswordResetCode = no;
    export function getAdditionalUserInfo(){ return null; }`,
  "firebase-firestore": `
    const K = (p) => "__fakefs:" + p, subs = {}, DEL = { del: 1 };
    function read(p){ try { return JSON.parse(localStorage.getItem(K(p)) || "null"); } catch (e) { return null; } }
    function snap(p){ const d = read(p); return { exists: () => d != null, data: () => d, metadata: { fromCache: false, hasPendingWrites: false } }; }
    function tell(p){ (subs[p] || []).forEach((f) => setTimeout(() => f(snap(p)), 0)); }
    function write(p, v){ localStorage.setItem(K(p), JSON.stringify(v)); tell(p); }
    function merge(a, b){ const o = Object.assign({}, a);
      for (const k of Object.keys(b)) { const v = b[k];
        if (v === DEL) delete o[k];
        else if (v && typeof v === "object" && !Array.isArray(v) && o[k] && typeof o[k] === "object") o[k] = merge(o[k], v);
        else o[k] = v; }
      return o; }
    export function getFirestore(){ return {}; }
    export function doc(db, ...parts){ return { path: parts.join("/") }; }
    export function deleteField(){ return DEL; }
    /* 붙는 순간 한 번 — 다른 페이지가 바꾼 것은 알려 주지 않는다 */
    export function onSnapshot(ref, next){
      const f = (s) => next(s);
      (subs[ref.path] = subs[ref.path] || []).push(f);
      setTimeout(() => f(snap(ref.path)), 20);
      return () => { subs[ref.path] = (subs[ref.path] || []).filter((g) => g !== f); };
    }
    export async function getDoc(ref){ return snap(ref.path); }
    export async function setDoc(ref, data, opt){ write(ref.path, opt && opt.merge ? merge(read(ref.path) || {}, data) : data); }
    export async function updateDoc(ref, data){ const d = read(ref.path) || {};
      for (const k of Object.keys(data)) { const ps = k.split("."); let o = d;
        for (let i = 0; i < ps.length - 1; i++) { o[ps[i]] = Object.assign({}, o[ps[i]] || {}); o = o[ps[i]]; }
        if (data[k] === DEL) delete o[ps[ps.length - 1]]; else o[ps[ps.length - 1]] = data[k]; }
      write(ref.path, d); }
    export async function deleteDoc(ref){ localStorage.removeItem(K(ref.path)); tell(ref.path); }`,
  "firebase-functions": `export function getFunctions(){ return {}; } export function httpsCallable(){ return async () => ({ data: {} }); }`,
};

const MIME = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".json": "application/json",
               ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2" };
const server = createServer(async (req, res) => {
  try {
    const rel = normalize(decodeURIComponent(req.url.split("?")[0])).replace(/^(\.\.[/\\])+/, "");
    if (rel === "/__blank") { res.writeHead(200, { "content-type": "text/html" }); res.end("<!doctype html><title>.</title>"); return; }
    const body = process.env.WL_MODULE && /(^|\/)watchlist\.js$/.test(rel)
      ? readFileSync(process.env.WL_MODULE) : await readFile(join(ROOT, rel));
    res.writeHead(200, { "content-type": MIME[extname(rel)] || "application/octet-stream" });
    res.end(body);
  } catch (e) { res.writeHead(404); res.end("no"); }
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: CHROME, ignoreDefaultArgs: ["--disable-back-forward-cache"] });

let pass = 0, fail = 0;
function ok(cond, msg, extra) {
  if (cond) { pass++; console.log("  ✅ " + msg); }
  else { fail++; console.log("  ❌ " + msg + (extra ? " — " + extra : "")); }
}

async function site(label, dir, rowsSel, wlRowSel) {
  console.log(`\n${label}`);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await ctx.route(/^https?:\/\/(?!127\.0\.0\.1)/, (route) => {
    const m = route.request().url().match(/gstatic\.com\/firebasejs\/[\d.]+\/(firebase-[a-z-]+)\.js/);
    if (m && FAKE[m[1]]) return route.fulfill({ status: 200, contentType: "text/javascript", body: FAKE[m[1]] });
    return route.abort();
  });
  await ctx.addInitScript(() => {
    window.addEventListener("pageshow", (e) => { window.__shows = (window.__shows || []).concat(e.persisted); });
  });
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  const notUsed = [];
  await cdp.send("Page.enable");
  cdp.on("Page.backForwardCacheNotUsed", (e) => notUsed.push((e.notRestoredExplanations || []).map((x) => x.reason).join(",")));

  await page.goto(`${BASE}/__blank`);
  await page.evaluate(([uid, v]) => {
    localStorage.clear();
    localStorage.setItem("__fakefs:users/" + uid, JSON.stringify({ consents: { age14: true, terms: true, privacy: true, version: v } }));
  }, [UID, CONSENT_VERSION]);

  const ready = () => page.waitForFunction(() => window.KOSWatch && window.KOSWatch.ready, null, { timeout: 15000 });
  const restored = async (what) => {
    await page.waitForTimeout(300);
    const shows = await page.evaluate(() => window.__shows || []);
    ok(shows[shows.length - 1] === true, `${what} — 되살아난 페이지다(bfcache)`, `pageshow ${JSON.stringify(shows)} · 못 쓴 까닭 ${notUsed.slice(-1)[0] || "?"}`);
  };
  const isOn = (sel) => page.$eval(sel, (b) => b.classList.contains("on")).catch(() => null);

  /* ① 목록 → 상세에서 추가 → 뒤로 → 목록 단추가 ✓ */
  await page.goto(`${BASE}/${dir}Reports.html`);
  await ready();
  await page.waitForSelector(`${rowsSel} [data-wl]`, { timeout: 15000 });
  const tk = await page.$eval(`${rowsSel} [data-wl]`, (b) => b.dataset.wl);
  const btn = `${rowsSel} [data-wl="${tk}"]`;
  ok(await isOn(btn) === false, `목록 ${tk} 단추가 처음엔 +`);
  await page.goto(`${BASE}/${dir}stock.html?ticker=${tk}`);
  await ready();
  await page.waitForSelector("#watchBtn", { timeout: 15000 });
  await page.click("#watchBtn");
  ok(await isOn("#watchBtn") === true, "상세에서 추가하면 ✓");
  await page.goBack({ waitUntil: "commit" });
  await restored("뒤로 가기");
  ok(await isOn(btn) === true, "뒤로 가기로 돌아온 목록의 단추가 ✓", "옛 목록 그대로(+)");

  /* ② 반대 — 목록에서 빼기 → 앞으로 → 상세 단추가 + */
  await page.click(btn);
  ok(await isOn(btn) === false, "목록에서 빼면 +");
  await page.goForward({ waitUntil: "commit" });
  await restored("앞으로 가기");
  ok(await isOn("#watchBtn") === false, "앞으로 가기로 돌아온 상세의 단추가 +", "옛 목록 그대로(✓)");

  /* ③ 관심종목 페이지 → 상세에서 빼기 → 뒤로 → 목록에서 사라진다 */
  await page.click("#watchBtn");
  ok(await isOn("#watchBtn") === true, "상세에서 다시 추가하면 ✓");
  await page.goto(`${BASE}/${dir}Watchlist.html`);
  await ready();
  /* 보이는지로 본다 — 실사이트 관심종목 페이지는 목록이 비면 줄을 지우지 않고 목록째 숨긴다 */
  const wlRow = page.locator(`${wlRowSel}[data-tk="${tk}"]`);
  await wlRow.waitFor({ state: "visible", timeout: 15000 }).catch(() => {});
  ok(await wlRow.isVisible(), `관심종목 페이지에 ${tk} 가 보인다`);
  await page.goto(`${BASE}/${dir}stock.html?ticker=${tk}`);
  await ready();
  await page.waitForSelector("#watchBtn", { timeout: 15000 });
  await page.click("#watchBtn");
  ok(await isOn("#watchBtn") === false, "상세에서 빼면 +");
  await page.goBack({ waitUntil: "commit" });
  await restored("뒤로 가기(관심종목)");
  ok(!(await wlRow.isVisible()), `돌아온 관심종목 페이지에서 ${tk} 가 사라진다`, "옛 목록 그대로");

  await ctx.close();
}

try {
  await site("스테이징", "staging/", "a.rl-row", "a.row");
  await site("실사이트", "", "a.rl-row", "a.wl-row");
} finally {
  await browser.close();
  server.close();
}

console.log(`\n통과 ${pass} · 실패 ${fail}`);
process.exit(fail ? 1 : 0);
