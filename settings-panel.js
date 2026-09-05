/* ============================================================
   KOSAI — 설정 패널
   ------------------------------------------------------------
   계정 메뉴의 '설정' 을 누르면 지금 보던 화면 위에 작은 창으로 뜬다.
   리포트를 보다가 테마 한 번 바꾸려고 페이지를 떠날 이유가 없다.

   Settings.html 도 같은 함수를 쓴다. 화면이 둘인데 코드가 둘이면 한쪽만
   고치게 되고, 그러면 모달에는 있는 항목이 페이지에는 없는 상태가 된다.
   실제로 로그인·가입 화면에서 그 일이 있었다.

   왜 왼쪽 목록인가. 전에는 항목이 한 줄로 죽 이어져 있었다. 성격이 다른
   것(그 기기의 취향 · 메일 수신 · 계정)이 한 덩어리로 붙어 있으면, 테마를
   바꾸러 온 사람이 탈퇴 버튼을 지나쳐야 한다. 스테이징 창이 먼저 목록으로
   갈랐고, 두 사이트의 설정이 서로 다르게 생길 이유가 없어 여기도 맞춘다.

     일반    테마 · 언어
     알림    마케팅 정보 수신
     계정    닉네임 · 이메일 · 로그아웃 · 회원 탈퇴

   스테이징에 있는 '구독' 칸은 여기 없다. 실사이트에는 아직 구독 기능이
   없으므로 목록에 이름만 걸어 두면 눌러도 아무 일이 없는 칸이 된다.

     openSettings()          지금 화면 위에 창으로 띄운다
     renderSettings(box)     주어진 자리에 그린다 (Settings.html 이 쓴다)
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js?v=7b8f27a5";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getMarketing, setMarketing, accountInfo } from "./consent.js?v=206cdd28";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

if (window.KOSi18n) window.KOSi18n.register({
  "설정": "Settings",
  "일반": "General",
  "알림": "Notifications",
  "계정": "Account",
  "닉네임": "Nickname",
  "이메일": "Email",
  "등록된 주소 없음": "No address on file",
  "테마": "Theme",
  "라이트": "Light",
  "다크": "Dark",
  "언어": "Language",
  "한국어": "Korean",
  "English": "English",
  "마케팅 정보 수신": "Marketing messages",
  "새 리포트와 서비스 소식을 이메일로 받습니다. 받지 않아도 서비스 이용에는 아무 영향이 없습니다.":
    "Get news about new reports and the service by email. Turning this off does not affect your use of the service.",
  "로그아웃": "Sign out",
  "회원 탈퇴": "Delete account",
  "저장하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.": "Could not save. Please try again in a moment.",
  "불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.": "Could not load. Please try again in a moment.",
  "계정 설정을 보려면 로그인이 필요합니다.": "Sign in to view your account settings.",
  "로그인": "Sign in",
  "닫기": "Close",
  "약관과 개인정보 처리에 관한 내용은": "You can review our",
  "이용약관": "Terms of Service",
  "개인정보처리방침": "Privacy Policy",
  "에서 확인할 수 있습니다.": "."
});

/* ────────────────────────────── 모양 ────────────────────────────── */

function css() {
  if (document.getElementById("kos-settings-css")) return;
  const s = document.createElement("style");
  s.id = "kos-settings-css";
  s.textContent = `
.ks-ov{position:fixed;inset:0;z-index:1100;background:rgba(10,11,19,.5);
  display:flex;align-items:center;justify-content:center;padding:20px;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
/* 한 줄짜리 창(420px)보다 넓다. 왼쪽에 목록이 서고 오른쪽에 내용이 오므로
   좁으면 둘 다 답답해진다. 높이를 고정해 칸을 옮겨도 창이 들썩이지 않게 한다. */
.ks-card{width:100%;max-width:860px;height:min(600px,86vh);display:flex;flex-direction:column;
  background:var(--bg-1);border-radius:var(--radius-lg,16px);overflow:hidden;
  box-shadow:var(--shadow-2,0 24px 64px rgba(15,23,42,.24));
  border:1px solid var(--border-2,rgba(0,0,0,.07))}
:root[data-theme="dark"] .ks-card{background:#1a1b26;border-color:rgba(255,255,255,.08)}
.ks-top{display:flex;align-items:center;justify-content:space-between;flex:none;
  padding:15px 18px;border-bottom:1px solid var(--hair,rgba(0,0,0,.07))}
.ks-title{font:700 16px/1.3 var(--font-sans,system-ui);color:var(--fg-1)}
.ks-x{border:0;background:transparent;cursor:pointer;font-size:19px;line-height:1;
  color:var(--fg-3);padding:4px 6px;border-radius:8px}
.ks-x:hover{background:rgba(0,0,0,.06)}
:root[data-theme="dark"] .ks-x:hover{background:rgba(255,255,255,.08)}
.ks-body{flex:1;display:flex;min-height:0}
.ks-main{flex:1;display:flex;min-height:0}
/* 왼쪽 목록과 오른쪽 내용을 가르는 선.
   --hair 를 쓰면 다크에서 그 값이 흰색 8% 라 #1a1b26 배경 위에서 사실상
   보이지 않는다. 이 창에서만 쓰는 전용 값을 둔다 — 이러면 창을 띄우는
   페이지가 --hair 를 정의하든 말든 선이 늘 같은 굵기로 보인다.
   .ks-main 에도 같이 걸어 둔다. Settings.html 은 창이 아니라 본문에
   펴므로 .ks-card 가 없고, 그러면 선 색이 글자색으로 떨어진다. */
.ks-card,.ks-main{--ks-line:rgba(0,0,0,.12)}
:root[data-theme="dark"] .ks-card,
:root[data-theme="dark"] .ks-main{--ks-line:rgba(255,255,255,.13)}
.ks-nav{flex:none;width:196px;padding:12px 10px;overflow:auto;
  border-right:1px solid var(--ks-line)}
.ks-nav button{display:block;width:100%;text-align:left;border:0;background:transparent;
  cursor:pointer;padding:9px 12px;border-radius:9px;color:var(--fg-2);
  font:600 13.5px var(--font-sans,system-ui)}
.ks-nav button:hover{background:rgba(0,0,0,.05)}
:root[data-theme="dark"] .ks-nav button:hover{background:rgba(255,255,255,.06)}
.ks-nav button[aria-selected="true"]{background:rgba(47,109,246,.1);color:var(--brand-blue,#2f6df6)}
.ks-panel{flex:1;min-width:0;overflow:auto;padding:18px 22px 22px}
.ks-sec{padding:0 0 16px}
.ks-h{margin:0 0 10px;font:700 12px/1.3 var(--font-sans,system-ui);color:var(--fg-3);
  letter-spacing:.04em;text-transform:uppercase}
.ks-kv{display:grid;grid-template-columns:auto 1fr;gap:8px 16px;
  font:400 13.5px/1.6 var(--font-sans,system-ui);margin:0}
.ks-kv dt{color:var(--fg-3);white-space:nowrap}
.ks-kv dd{margin:0;color:var(--fg-1);word-break:break-all}
.ks-row{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:7px 0}
.ks-row .ks-lab{font:600 13.5px/1.45 var(--font-sans,system-ui);color:var(--fg-1)}
.ks-row .ks-sub{display:block;margin-top:3px;font:400 11.5px/1.55 var(--font-sans,system-ui);color:var(--fg-3)}
/* 폭을 고정한다. 글자 수에 맡기면 '라이트/다크' 와 '한국어/English' 가
   서로 다른 자리에서 끝나 오른쪽 끝이 들쭉날쭉해진다. */
.ks-seg{display:inline-flex;flex:none;width:184px;border:1px solid var(--border-2,rgba(0,0,0,.1));
  border-radius:9999px;overflow:hidden}
.ks-seg button{flex:1 1 50%;border:0;background:transparent;cursor:pointer;padding:7px 0;
  font:600 12.5px var(--font-sans,system-ui);color:var(--fg-3);white-space:nowrap}
.ks-seg button[aria-pressed="true"]{background:var(--brand-blue,#2f6df6);color:#fff}
/* 스위치 — 켜고 끄는 것이 분명해 보여야 한다 */
.ks-sw{position:relative;flex:none;width:44px;height:25px;border-radius:9999px;border:0;cursor:pointer;
  background:var(--border-2,rgba(0,0,0,.16));transition:background .16s}
.ks-sw[aria-checked="true"]{background:var(--brand-blue,#2f6df6)}
.ks-sw::after{content:"";position:absolute;top:3px;left:3px;width:19px;height:19px;border-radius:50%;
  background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.28);transition:transform .16s}
.ks-sw[aria-checked="true"]::after{transform:translateX(19px)}
.ks-sw:disabled{opacity:.5;cursor:default}
.ks-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:14px}
.ks-btn{display:inline-block;padding:10px 14px;border-radius:10px;cursor:pointer;
  font:600 13px var(--font-sans,system-ui);text-align:center;text-decoration:none;
  border:1px solid var(--border-2,rgba(0,0,0,.1));background:transparent;color:var(--fg-1)}
.ks-btn:hover{background:rgba(0,0,0,.04)}
:root[data-theme="dark"] .ks-btn:hover{background:rgba(255,255,255,.06)}
.ks-btn.primary{background:var(--brand-blue,#2f6df6);border-color:transparent;color:#fff}
.ks-btn.primary:hover{filter:brightness(1.05)}
.ks-btn.danger{color:#c0282b;border-color:rgba(192,40,43,.3)}
:root[data-theme="dark"] .ks-btn.danger{color:#ff8a8c;border-color:rgba(255,138,140,.28)}
.ks-msg{display:none;margin:10px 0 0;font:600 12px/1.5 var(--font-sans,system-ui)}
.ks-msg.on{display:block}
.ks-msg.ok{color:var(--brand-blue,#2f6df6)}
.ks-msg.err{color:#c0282b}
:root[data-theme="dark"] .ks-msg.err{color:#ff8a8c}
.ks-note{margin:14px 0 0;font:400 11.5px/1.6 var(--font-sans,system-ui);color:var(--fg-3)}
.ks-note a{color:var(--fg-2);text-decoration:underline;text-underline-offset:2px}
/* 좁은 화면 — 왼쪽 목록을 위쪽 가로줄로 눕힌다. 196px 를 떼어 주면
   내용이 들어갈 자리가 남지 않는다. */
@media (max-width:640px){
  .ks-ov{padding:0}
  .ks-card{max-width:none;height:100%;border-radius:0}
  .ks-main{flex-direction:column}
  .ks-nav{width:auto;display:flex;gap:6px;overflow-x:auto;padding:10px 12px;
    border-right:0;border-bottom:1px solid var(--ks-line)}
  .ks-nav button{width:auto;white-space:nowrap;padding:8px 12px}
  .ks-panel{padding:16px}
}`;
  document.head.appendChild(s);
}

/* ────────────────────────────── 조각 ────────────────────────────── */

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

/* 두 갈래 중 하나를 고르는 줄. 테마와 언어가 같은 모양을 쓴다. */
function segRow(label, options, current, onPick) {
  const row = el("div", "ks-row");
  row.appendChild(el("div", "ks-lab", T(label)));
  const seg = el("div", "ks-seg");
  const btns = options.map(o => {
    const b = el("button", null, T(o.label));
    b.type = "button";
    b.setAttribute("aria-pressed", String(o.value === current));
    b.addEventListener("click", () => {
      btns.forEach(x => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      onPick(o.value);
    });
    seg.appendChild(b);
    return b;
  });
  row.appendChild(seg);
  return row;
}

/* 테마는 페이지마다 인라인 스크립트가 갖고 있어서 부를 함수가 없다.
   하는 일이 세 가지뿐이라 여기서 직접 한다 — 속성·저장·헤더 아이콘.
   아이콘까지 바꿔 줘야 헤더와 설정이 서로 다른 상태를 가리키지 않는다. */
const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const MOON = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';

function currentTheme() {
  const a = document.documentElement.getAttribute("data-theme");
  if (a) return a;
  try { return localStorage.getItem("kos-theme") || "dark"; } catch (_) { return "dark"; }
}

function applyTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  try { localStorage.setItem("kos-theme", t); } catch (_) {}
  const i = document.getElementById("themeIcon");
  if (i) i.innerHTML = t === "dark" ? SUN : MOON;
}

function currentLang() { return (window.KOSi18n ? window.KOSi18n.lang : "ko") || "ko"; }

/* ────────────────────────── 칸별로 그리기 ────────────────────────── */

/* 테마와 언어. 계정이 아니라 그 기기의 취향이고 localStorage 에 저장된다.
   그래서 로그인하지 않은 사람에게도 이 칸은 보인다 — 헤더의 KO/EN 토글을
   걷어낸 뒤라, 이것마저 막으면 비회원이 영어로 바꿀 방법이 아예 없다. */
function paneGeneral() {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("일반")));
  s.appendChild(segRow("테마",
    [{ label: "라이트", value: "light" }, { label: "다크", value: "dark" }],
    currentTheme(), applyTheme));
  if (window.KOSi18n) {
    s.appendChild(segRow("언어",
      [{ label: "한국어", value: "ko" }, { label: "English", value: "en" }],
      currentLang(), v => { try { window.KOSi18n.setLang(v); } catch (_) {} }));
  }
  box.appendChild(s);
  return box;
}

function paneNotifications(user) {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("알림")));

  const row = el("div", "ks-row");
  const lab = el("div", "ks-lab", T("마케팅 정보 수신"));
  lab.appendChild(el("span", "ks-sub",
    T("새 리포트와 서비스 소식을 이메일로 받습니다. 받지 않아도 서비스 이용에는 아무 영향이 없습니다.")));
  const sw = el("button", "ks-sw");
  sw.type = "button";
  sw.setAttribute("role", "switch");
  sw.setAttribute("aria-checked", "false");
  sw.disabled = true;
  row.appendChild(lab); row.appendChild(sw);
  s.appendChild(row);

  const msg = el("p", "ks-msg");
  s.appendChild(msg);
  box.appendChild(s);

  const say = (t, k) => { msg.textContent = T(t); msg.className = "ks-msg on " + k; };

  getMarketing(user.uid)
    .then(on => { sw.setAttribute("aria-checked", String(!!on)); sw.disabled = false; })
    .catch(() => say("불러오지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.", "err"));

  /* 누르는 순간 저장한다. '저장' 버튼을 따로 두면 눌렀다고 생각하고 나가는
     사람이 반드시 생긴다. 잘 됐다는 말은 하지 않는다 — 스위치가 옮겨 간 것이
     곧 확인이다. 실패하면 스위치를 되돌리고 그때만 이유를 말한다. */
  sw.addEventListener("click", async () => {
    const was = sw.getAttribute("aria-checked") === "true";
    sw.setAttribute("aria-checked", String(!was));
    sw.disabled = true;
    msg.className = "ks-msg";
    try { await setMarketing(user.uid, !was); }
    catch (_) {
      sw.setAttribute("aria-checked", String(was));
      say("저장하지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.", "err");
    }
    sw.disabled = false;
  });
  return box;
}

/* 내 계정에 뭐가 저장돼 있는지 본인이 볼 수 있어야 한다. 소셜로 가입하면
   화면 어디에도 이메일이 안 보여서, 어떤 주소로 메일이 오는지 알 방법이
   없었다.

   가입 방법은 뺐다. 옛 계정은 signupMethod 가 안 남아 있어서 '알 수 없음'
   만 뜬다. 틀린 값을 보여 주느니 안 보여 주는 편이 낫다. */
function paneAccount(user, opts) {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("계정")));

  const dl = el("dl", "ks-kv");
  /* Auth 에 있는 값을 먼저 그린다. 아래 accountInfo 는 users 문서까지 보고
     더 나은 값이 있으면 갈아 끼운다 — 그걸 기다리느라 빈 화면을 보여 줄
     이유가 없다. */
  const nameDd = el("dd", null, user.displayName || "—");
  const mailDd = el("dd", null, user.email || "—");
  dl.appendChild(el("dt", null, T("닉네임"))); dl.appendChild(nameDd);
  dl.appendChild(el("dt", null, T("이메일"))); dl.appendChild(mailDd);
  s.appendChild(dl);

  accountInfo(user).then(info => {
    nameDd.textContent = info.name || "—";
    mailDd.textContent = info.email || T("등록된 주소 없음");
  }).catch(() => { /* 표시용 — 실패해도 나머지는 쓸 수 있게 둔다 */ });

  const btns = el("div", "ks-btns");
  const out = el("button", "ks-btn", T("로그아웃"));
  out.type = "button";
  out.addEventListener("click", async () => {
    try { await signOut(auth); } catch (_) {}
    location.href = "Home.html";
  });
  const del = el("button", "ks-btn danger", T("회원 탈퇴"));
  del.type = "button";
  del.addEventListener("click", () => {
    if (opts.onClose) opts.onClose();
    /* 탈퇴 화면은 auth-state.js 가 갖고 있다. 여기서 다시 만들면 확인
       절차가 두 벌이 되고, 한쪽만 고치게 된다. */
    if (window.KOSAccount && window.KOSAccount.withdraw) window.KOSAccount.withdraw();
  });
  btns.appendChild(out); btns.appendChild(del);
  s.appendChild(btns);

  const note = el("p", "ks-note");
  note.appendChild(document.createTextNode(T("약관과 개인정보 처리에 관한 내용은") + " "));
  const t1 = el("a", null, T("이용약관")); t1.href = "Terms.html"; note.appendChild(t1);
  note.appendChild(document.createTextNode(" · "));
  const t2 = el("a", null, T("개인정보처리방침")); t2.href = "Privacy.html"; note.appendChild(t2);
  note.appendChild(document.createTextNode(T("에서 확인할 수 있습니다.")));
  s.appendChild(note);

  box.appendChild(s);
  return box;
}

/* ────────────────────────────── 본체 ────────────────────────────── */

/* 주어진 자리에 설정을 그린다. opts.tab 으로 처음 펼 칸을 정하고,
   opts.onClose 를 주면 '회원 탈퇴' 로 넘어갈 때 부른다(창이 자기를 닫는다). */
export function renderSettings(box, opts = {}) {
  css();
  box.textContent = "";

  const user = auth.currentUser;
  const signedIn = !!(isConfigured && user);

  const tabs = [{ id: "general", label: "일반", make: () => paneGeneral() }];
  if (signedIn) {
    tabs.push({ id: "notifications", label: "알림", make: () => paneNotifications(user) });
    tabs.push({ id: "account", label: "계정", make: () => paneAccount(user, opts) });
  }

  const main = el("div", "ks-main");
  const nav = el("div", "ks-nav");
  nav.setAttribute("role", "tablist");
  const panel = el("div", "ks-panel");
  main.appendChild(nav); main.appendChild(panel);
  box.appendChild(main);

  const btns = [];
  function show(id) {
    const t = tabs.find(x => x.id === id) || tabs[0];
    btns.forEach(b => b.setAttribute("aria-selected", String(b.dataset.id === t.id)));
    panel.textContent = "";
    panel.appendChild(t.make());
    panel.scrollTop = 0;
    if (window.KOSi18n) window.KOSi18n.apply();
  }

  tabs.forEach(t => {
    const b = el("button", null, T(t.label));
    b.type = "button";
    b.dataset.id = t.id;
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(t.id));
    nav.appendChild(b);
    btns.push(b);
  });

  /* 로그인하지 않았으면 목록은 '일반' 하나뿐이다. 계정 칸을 눌러도 아무
     일이 없는 이름만 걸어 두느니, 그 자리에 로그인으로 가는 길을 둔다. */
  if (!signedIn) {
    const s = el("div", "ks-sec");
    s.appendChild(el("p", "ks-note", T("계정 설정을 보려면 로그인이 필요합니다.")));
    const a = el("a", "ks-btn primary", T("로그인"));
    a.href = "Login.html?next=" + encodeURIComponent(
      (location.pathname.split("/").pop() || "Home.html") + (location.search || ""));
    s.appendChild(a);
    panel.appendChild(paneGeneral());
    panel.appendChild(s);
    btns[0].setAttribute("aria-selected", "true");
    if (window.KOSi18n) window.KOSi18n.apply();
    return;
  }

  show(opts.tab && tabs.some(t => t.id === opts.tab) ? opts.tab : "general");
}

/* 지금 보던 화면 위에 창으로 띄운다. tab 을 주면 그 칸을 펴서 연다. */
export function openSettings(tab) {
  css();
  const old = document.getElementById("ksModal");
  if (old) old.remove();

  const ov = el("div", "ks-ov");
  ov.id = "ksModal";
  const card = el("div", "ks-card");
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");

  const top = el("div", "ks-top");
  top.appendChild(el("div", "ks-title", T("설정")));
  const x = el("button", "ks-x", "✕");
  x.type = "button";
  x.setAttribute("aria-label", T("닫기"));
  top.appendChild(x);

  const body = el("div", "ks-body");
  card.appendChild(top); card.appendChild(body);
  ov.appendChild(card);
  document.body.appendChild(ov);

  const close = () => { ov.remove(); document.removeEventListener("keydown", onKey); };
  function onKey(e) { if (e.key === "Escape") close(); }
  x.addEventListener("click", close);
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  document.addEventListener("keydown", onKey);

  renderSettings(body, { onClose: close, tab });

  /* 로그아웃되면(다른 탭에서 나갔거나 탈퇴했거나) 창을 닫는다. */
  const stop = onAuthStateChanged(auth, u => { if (!u) { close(); stop(); } });
  return close;
}

/* 계정 메뉴가 부를 수 있게 열어 둔다. auth-state.js 는 이 모듈을 import
   하지 않는다 — 모든 페이지에 실리는 파일이라 무겁게 만들지 않으려고
   필요할 때만 동적으로 불러온다. */
window.KOSSettings = { open: openSettings, render: renderSettings };
