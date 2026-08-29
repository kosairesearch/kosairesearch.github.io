/* ============================================================
   KOSAI — 설정 패널 (스테이징)
   ------------------------------------------------------------
   실사이트의 settings-panel.js 를 가져와 항목을 왼쪽 목록으로 나누고
   '구독' 을 더한 판이다.

   왜 페이지가 아니라 창인가. 구독 관리는 리포트를 보다가 잠깐 들르는
   곳이지 찾아가는 곳이 아니다. billing.html 로 페이지를 옮기면 보던
   화면을 잃고, 돌아오려면 뒤로가기를 눌러야 한다. 테마·언어·마케팅
   수신과 같은 성격의 설정인데 그것만 페이지로 떨어져 있을 이유도 없다.

   왜 왼쪽 목록인가. 실사이트 창은 한 줄로 죽 이어진 형태다. 거기에
   구독을 더하면 스크롤이 길어지고, 테마를 바꾸러 온 사람이 결제 정보를
   지나쳐야 한다. 성격이 다른 것은 갈라 놓는 편이 낫다.

     일반    테마 · 언어
     알림    마케팅 정보 수신
     구독    플랜 · 결제 수단 · 사용량 · 해지/재개/환불
     계정    닉네임 · 이메일 · 로그아웃 · 회원 탈퇴

   구독 자료는 window.KOSPaywall(paywall.js)에서 받고, 바꾸는 일은
   subscription-api.js 의 call() 로 보낸다. 스테이징에서는 그 call 이
   모의 백엔드로 돌아가므로 실제로 돈이 오가지 않는다.

     openSettings(tab)   지금 화면 위에 창으로 띄운다
     window.KOSSettings.open("subscription")   구독 칸을 펴서 연다
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged, signOut }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getMarketing, setMarketing, accountInfo } from "./consent.js";
import { call } from "./subscription-api.js";
import { PLANS, planOf, won, fmtDay, payReady } from "./payment-config.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
const EN = () => (window.KOSi18n ? window.KOSi18n.lang : "ko") === "en";

if (window.KOSi18n) window.KOSi18n.register({
  "설정": "Settings",
  "일반": "General",
  "알림": "Notifications",
  "구독": "Subscription",
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
  "저장에 실패했어요. 잠시 후 다시 시도해 주세요.": "Could not save. Please try again in a moment.",
  "불러오지 못했어요. 잠시 후 다시 시도해 주세요.": "Could not load. Please try again in a moment.",
  "계정 설정을 보려면 로그인이 필요합니다.": "Sign in to view your account settings.",
  "로그인": "Sign in",
  "닫기": "Close",
  "약관과 개인정보 처리에 관한 내용은": "You can review our",
  "이용약관": "Terms of Service",
  "개인정보처리방침": "Privacy Policy",
  "에서 확인할 수 있습니다.": ".",
  /* 구독 */
  "불러오는 중…": "Loading…",
  "이용 중인 플랜": "Current plan",
  "무료": "Free",
  "무료로 이용 중입니다. 하루 열람 한도 안에서 리포트를 보실 수 있습니다.":
    "You are on the free plan, with a daily report limit.",
  "플랜 보기": "See plans",
  "상태": "Status",
  "이용 중": "Active",
  "해지 예약됨": "Cancels at period end",
  "결제 실패": "Payment failed",
  "다음 결제일": "Next billing date",
  "이용 종료일": "Access ends",
  "결제 금액": "Amount",
  "결제 수단": "Payment method",
  "등록된 카드가 없습니다.": "No card registered.",
  "등록하신 카드": "Card on file",
  "오늘 열람": "Read today",
  "건": "",
  "플랜 변경": "Change plan",
  "결제 수단 변경": "Change card",
  "구독 해지": "Cancel subscription",
  "해지 취소": "Keep subscription",
  "환불 신청": "Request a refund",
  "다음 결제일에 해지됩니다. 그때까지는 그대로 이용하실 수 있습니다.":
    "Your subscription will end on the next billing date. You keep access until then.",
  "해지를 취소했습니다. 구독이 그대로 이어집니다.":
    "Cancellation withdrawn. Your subscription continues.",
  "환불을 신청했습니다.": "Refund requested.",
  "처리하지 못했어요. 잠시 후 다시 시도해 주세요.": "Could not complete. Please try again in a moment.",
  "다음 결제일에 {p} 로 바뀝니다.": "Changes to {p} on the next billing date.",
  "미리보기입니다. 실제로 돈이 오가지 않습니다.": "Preview only — no real payment is made.",
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
/* 실사이트 창(420px)보다 넓다. 왼쪽에 목록이 서고 오른쪽에 내용이 오므로
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
.ks-main{flex:1;display:flex;min-height:0}
.ks-nav{flex:none;width:196px;padding:12px 10px;overflow:auto;
  border-right:1px solid var(--hair,rgba(0,0,0,.07))}
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
.ks-seg{display:inline-flex;flex:none;width:184px;border:1px solid var(--border-2,rgba(0,0,0,.1));
  border-radius:9999px;overflow:hidden}
.ks-seg button{flex:1 1 50%;border:0;background:transparent;cursor:pointer;padding:7px 0;
  font:600 12.5px var(--font-sans,system-ui);color:var(--fg-3);white-space:nowrap}
.ks-seg button[aria-pressed="true"]{background:var(--brand-blue,#2f6df6);color:#fff}
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
.ks-btn:disabled{opacity:.55;cursor:default}
.ks-badge{display:inline-block;padding:3px 9px;border-radius:9999px;
  font:700 11.5px var(--font-sans,system-ui)}
.ks-badge.on{background:rgba(10,125,50,.12);color:#0a7d32}
.ks-badge.warn{background:rgba(192,40,43,.12);color:#c0282b}
:root[data-theme="dark"] .ks-badge.on{background:rgba(61,220,132,.14);color:#3ddc84}
:root[data-theme="dark"] .ks-badge.warn{background:rgba(255,138,140,.14);color:#ff8a8c}
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
    border-right:0;border-bottom:1px solid var(--hair,rgba(0,0,0,.07))}
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
    .catch(() => say("불러오지 못했어요. 잠시 후 다시 시도해 주세요.", "err"));

  /* 누르는 순간 저장한다. '저장' 버튼을 따로 두면 눌렀다고 생각하고 나가는
     사람이 반드시 생긴다. 실패하면 스위치를 되돌리고 이유를 말한다. */
  sw.addEventListener("click", async () => {
    const was = sw.getAttribute("aria-checked") === "true";
    sw.setAttribute("aria-checked", String(!was));
    sw.disabled = true;
    msg.className = "ks-msg";
    try { await setMarketing(user.uid, !was); }
    catch (_) {
      sw.setAttribute("aria-checked", String(was));
      say("저장에 실패했어요. 잠시 후 다시 시도해 주세요.", "err");
    }
    sw.disabled = false;
  });
  return box;
}

/* ── 구독 ────────────────────────────────────────────────────────
   billing.html 이 하던 일을 이 칸으로 옮긴다. 페이지 쪽 코드를 그대로
   가져오지 않고 다시 쓴 이유는, 그 화면이 결제 이력 표까지 담은 전체
   페이지 레이아웃이라 창 안에서는 읽히지 않기 때문이다. 여기서는 '지금
   어떤 상태이고 무엇을 할 수 있는가' 만 남긴다. */
function paneSubscription() {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("구독")));
  const body = el("div");
  s.appendChild(body);
  const msg = el("p", "ks-msg");
  s.appendChild(msg);
  box.appendChild(s);

  const say = (t, k) => { msg.textContent = T(t); msg.className = "ks-msg on " + k; };

  /* 결제 수단을 바꾸고 돌아온 길이면 한 번만 알린다. auth-state 가 주소에서
     ?card=1 을 지우기 전에 여기로 넘겨 준다. 읽고 나면 지운다 — 칸을 옮겼다
     돌아올 때마다 같은 안내가 뜨면 무슨 일이 또 일어난 줄 안다. */
  if (window.__KOS_CARD_NOTICE) {
    delete window.__KOS_CARD_NOTICE;
    say("결제 수단이 변경되었습니다. 다음 결제일부터 새 카드로 청구됩니다.", "ok");
  }

  body.appendChild(el("p", "ks-note", T("불러오는 중…")));

  const kv = (dl, k, v) => {
    dl.appendChild(el("dt", null, T(k)));
    const dd = el("dd");
    if (v instanceof Node) dd.appendChild(v); else dd.textContent = v;
    dl.appendChild(dd);
  };

  /* 상태가 바뀌면(해지·재개·플랜 변경) 다시 그린다. 눌러 놓고 창을 닫았다
     여는 것으로만 확인되면 제대로 됐는지 알 수가 없다. */
  function draw(st, usage) {
    body.textContent = "";
    const en = EN();
    const sub = (st && st.sub) || null;
    const plan = planOf(st && st.plan);

    if (!st || !st.active || !plan) {
      body.appendChild(el("p", "ks-note",
        T("무료로 이용 중입니다. 하루 열람 한도 안에서 리포트를 보실 수 있습니다.")));
      const btns = el("div", "ks-btns");
      const a = el("a", "ks-btn primary", T("플랜 보기"));
      a.href = "pricing.html";
      btns.appendChild(a);
      body.appendChild(btns);
      return;
    }

    const dl = el("dl", "ks-kv");
    kv(dl, "이용 중인 플랜", plan.name);

    const badge = el("span", "ks-badge " +
      (sub && sub.status === "past_due" ? "warn" : sub && sub.cancelAtPeriodEnd ? "warn" : "on"),
      T(sub && sub.status === "past_due" ? "결제 실패"
        : sub && sub.cancelAtPeriodEnd ? "해지 예약됨" : "이용 중"));
    kv(dl, "상태", badge);

    if (sub && sub.currentPeriodEnd) {
      kv(dl, sub.cancelAtPeriodEnd ? "이용 종료일" : "다음 결제일",
         fmtDay(sub.currentPeriodEnd, en));
    }
    kv(dl, "결제 금액", won(plan.price, en));

    const card = sub && sub.card;
    kv(dl, "결제 수단", card && (card.company || card.number)
      ? ((card.company || T("등록하신 카드")) + " " + (card.number || "")).trim()
      : T("등록된 카드가 없습니다."));

    if (usage && typeof usage.used === "number") {
      kv(dl, "오늘 열람", `${usage.used} / ${usage.limit ?? plan.limit}${T("건")}`);
    }
    body.appendChild(dl);

    /* 플랜 변경 예약이 걸려 있으면 알려 준다. 예약해 놓고 화면에 아무
       흔적이 없으면 다음 달에 왜 금액이 바뀌었는지 알 수 없다. */
    if (sub && sub.pendingPlan) {
      const np = planOf(sub.pendingPlan);
      if (np) body.appendChild(el("p", "ks-note",
        T("다음 결제일에 {p} 로 바뀝니다.").replace("{p}", np.name)));
    }

    const btns = el("div", "ks-btns");

    const chg = el("a", "ks-btn", T("플랜 변경"));
    chg.href = "pricing.html";
    btns.appendChild(chg);

    /* 결제창 키가 아직 안 꽂혔으면 이 버튼은 누르나 마나다 — 눌러 놓고
       빈 화면을 보느니 아예 내보내지 않는다. 다만 미리보기(__KOSDEMO)는
       토스 없이 checkout.js 안에서 카드 변경을 흉내내므로 키가 없어도 된다.
       스테이징이 그쪽이다 — 여기서 payReady 만 보면 확인할 것을 못 본다.
       주소 모양은 billing.js·pricing.html 과 같아야 한다(plan + method=1).
       method 를 빼면 결제창이 '카드 변경' 이 아니라 새 결제로 뜬다. */
    if (payReady || window.__KOSDEMO) {
      const cardBtn = el("a", "ks-btn", T("결제 수단 변경"));
      cardBtn.href = "checkout.html?plan=" +
        encodeURIComponent((sub && sub.plan) || plan.id || "basic") + "&method=1";
      btns.appendChild(cardBtn);
    }

    /* 해지와 재개는 한 자리에서 뒤집힌다. 버튼을 둘 다 두면 지금 어느
       상태인지가 흐려진다. */
    const toggle = el("button", "ks-btn" + (sub && sub.cancelAtPeriodEnd ? " primary" : " danger"),
      T(sub && sub.cancelAtPeriodEnd ? "해지 취소" : "구독 해지"));
    toggle.type = "button";
    toggle.addEventListener("click", async () => {
      toggle.disabled = true;
      msg.className = "ks-msg";
      const resume = !!(sub && sub.cancelAtPeriodEnd);
      try {
        await call(resume ? "resumeSubscription" : "cancelSubscription", {});
        say(resume ? "해지를 취소했습니다. 구독이 그대로 이어집니다."
                   : "다음 결제일에 해지됩니다. 그때까지는 그대로 이용하실 수 있습니다.", "ok");
      } catch (_) {
        say("처리하지 못했어요. 잠시 후 다시 시도해 주세요.", "err");
      }
      toggle.disabled = false;
    });
    btns.appendChild(toggle);

    const rf = el("button", "ks-btn danger", T("환불 신청"));
    rf.type = "button";
    rf.addEventListener("click", async () => {
      rf.disabled = true;
      msg.className = "ks-msg";
      try { await call("requestRefund", {}); say("환불을 신청했습니다.", "ok"); }
      catch (_) { say("처리하지 못했어요. 잠시 후 다시 시도해 주세요.", "err"); }
      rf.disabled = false;
    });
    btns.appendChild(rf);

    body.appendChild(btns);
    body.appendChild(el("p", "ks-note", T("미리보기입니다. 실제로 돈이 오가지 않습니다.")));
    if (window.KOSi18n) window.KOSi18n.apply();
  }

  /* paywall 이 아직 안 실렸을 수도 있다(스크립트 순서). 없으면 구독을
     '없음' 으로 그리는 대신 그렇게 말한다 — 유료 회원에게 무료라고
     보여 주는 쪽이 훨씬 나쁘다. */
  const pw = window.KOSPaywall;
  if (!pw) {
    body.textContent = "";
    body.appendChild(el("p", "ks-note", T("불러오지 못했어요. 잠시 후 다시 시도해 주세요.")));
    return box;
  }

  const load = async (st) => {
    let usage = null;
    try { const r = await call("getUsage", {}); usage = (r && r.data) || null; } catch (_) {}
    draw(st, usage);
  };

  /* 먼저 ready 를 기다리고, 그 다음에 변화를 듣는다. 순서를 바꾸면 인증이
     끝나기 전의 빈 스냅샷(user:null)이 먼저 도착해 유료 회원에게 '무료로
     이용 중' 이 한 번 스쳐 지나간다. onChange 는 붙는 즉시 한 번 부르므로
     그 첫 회는 버린다 — ready 로 이미 같은 값을 그렸다. */
  let off = null;
  pw.ready.then(st => {
    load(st);
    if (pw.onChange) {
      let first = true;
      off = pw.onChange(s => { if (first) { first = false; return; } load(s); });
    }
  }).catch(() => {
    body.textContent = "";
    body.appendChild(el("p", "ks-note", T("불러오지 못했어요. 잠시 후 다시 시도해 주세요.")));
  });

  /* 칸을 옮기거나 창을 닫으면 이 자리는 사라진다. 듣던 것을 놓지 않으면
     없어진 자리에 계속 그리려 든다. renderSettings 가 이걸 부른다. */
  box._kosOff = () => { if (off) { off(); off = null; } };

  return box;
}

function paneAccount(user, opts) {
  const box = el("div");
  const s = el("div", "ks-sec");
  s.appendChild(el("div", "ks-h", T("계정")));

  const dl = el("dl", "ks-kv");
  const nameDd = el("dd", null, user.displayName || "—");
  const mailDd = el("dd", null, user.email || "—");
  dl.appendChild(el("dt", null, T("닉네임"))); dl.appendChild(nameDd);
  dl.appendChild(el("dt", null, T("이메일"))); dl.appendChild(mailDd);
  s.appendChild(dl);

  accountInfo(user).then(info => {
    nameDd.textContent = info.name || "—";
    mailDd.textContent = info.email || T("등록된 주소 없음");
  }).catch(() => {});

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

/* 주어진 자리에 설정을 그린다. tab 으로 처음 펼 칸을 정한다. */
export function renderSettings(box, opts = {}) {
  css();
  box.textContent = "";

  const user = auth.currentUser;
  const signedIn = !!(isConfigured && user);

  /* 화면(테마·언어)은 로그인과 상관없다. 그 기기의 취향이고 계정에
     저장되지 않는다. 그래서 비회원에게도 '일반' 은 보인다. */
  const tabs = [{ id: "general", label: "일반", make: () => paneGeneral() }];
  if (signedIn) {
    tabs.push({ id: "notifications", label: "알림", make: () => paneNotifications(user) });
    tabs.push({ id: "subscription", label: "구독", make: () => paneSubscription() });
    tabs.push({ id: "account", label: "계정", make: () => paneAccount(user, opts) });
  }

  const main = el("div", "ks-main");
  const nav = el("div", "ks-nav");
  nav.setAttribute("role", "tablist");
  const panel = el("div", "ks-panel");
  main.appendChild(nav); main.appendChild(panel);
  box.appendChild(main);

  const btns = [];
  function drop() {
    const cur = panel.firstChild;
    if (cur && typeof cur._kosOff === "function") { try { cur._kosOff(); } catch (_) {} }
  }
  function show(id) {
    const t = tabs.find(x => x.id === id) || tabs[0];
    btns.forEach(b => b.setAttribute("aria-selected", String(b.dataset.id === t.id)));
    drop();
    panel.textContent = "";
    panel.appendChild(t.make());
    panel.scrollTop = 0;
    if (window.KOSi18n) window.KOSi18n.apply();
  }
  box._kosOff = drop;

  tabs.forEach(t => {
    const b = el("button", null, T(t.label));
    b.type = "button";
    b.dataset.id = t.id;
    b.setAttribute("role", "tab");
    b.addEventListener("click", () => show(t.id));
    nav.appendChild(b);
    btns.push(b);
  });

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

/* 지금 보던 화면 위에 창으로 띄운다. tab 을 주면 그 칸을 펴서 연다 —
   '구독 관리' 를 누른 사람에게 일반 설정부터 보여 줄 이유가 없다. */
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

  const body = el("div");
  body.style.cssText = "flex:1;display:flex;min-height:0";
  card.appendChild(top); card.appendChild(body);
  ov.appendChild(card);
  document.body.appendChild(ov);

  const close = () => {
    if (typeof body._kosOff === "function") { try { body._kosOff(); } catch (_) {} }
    ov.remove();
    document.removeEventListener("keydown", onKey);
  };
  function onKey(e) { if (e.key === "Escape") close(); }
  x.addEventListener("click", close);
  ov.addEventListener("click", e => { if (e.target === ov) close(); });
  document.addEventListener("keydown", onKey);

  renderSettings(body, { onClose: close, tab });

  const stop = onAuthStateChanged(auth, u => { if (!u) { close(); stop(); } });
  return close;
}

window.KOSSettings = { open: openSettings, render: renderSettings };
