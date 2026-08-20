/* ============================================================
   KOSAI — 가입 동의 (필수·선택 분리 · 기록 · 마케팅 수신 구분)
   ------------------------------------------------------------
   왜 이 파일이 따로 있나.

   동의를 받는 자리가 여럿이다. 이메일 가입, 구글 팝업, 카카오·네이버
   리다이렉트, 그리고 로그인 페이지로 들어와 처음 계정이 만들어지는 경우까지.
   자리마다 체크박스를 따로 만들면 문구가 갈라지고 한 곳을 빠뜨린다.
   실제로 그랬다 — 가입 페이지는 막고 있었는데 로그인 페이지는 아무 동의
   없이 계정이 만들어졌다.

   그래서 항목 정의·화면·저장을 여기 한 곳에 두고, 모든 자리가 이 파일을
   쓴다.

   ------------------------------------------------------------
   동의 항목을 왜 나누나

   개인정보보호법은 동의받을 항목을 구분해 각각 받도록 한다. 전에는
   "만 14세 이상이며, 이용약관 및 개인정보처리방침에 동의합니다" 하나로
   묶여 있었다. 하나만 동의할 방법이 없었고, '개인정보처리방침에 동의'는
   형식도 어긋난다 — 처리방침은 회사가 일방적으로 공개하는 문서이지
   동의를 받는 대상이 아니다. 동의는 무엇을 수집해 어디에 쓰고 얼마나
   보관하는지를 그 자리에서 보여주고 받아야 한다.

   ------------------------------------------------------------
   기록 형태 — users/{uid}

     consents: {
       version: "2026-08-20",         동의서 판 번호. 문구가 바뀌면 올린다
       agreedAt: <서버시각>,
       age14:     true,               [필수] 만 14세 이상
       terms:     true,               [필수] 이용약관
       privacy:   true,               [필수] 개인정보 수집·이용
       marketing: false               [선택] 마케팅 정보 수신
     },
     marketingAt: <서버시각> | null,   마케팅 동의를 켠 시각(끄면 null)
     signupMethod: "email"|"google"|"kakao"|"naver",
     createdAt, updatedAt

   마케팅 동의자만 뽑을 때:
     where("consents.marketing", "==", true)
   자세한 건 docs/consent.md 에 적어 뒀다.
   ============================================================ */
import { app } from "./firebase-config.js";
import {
  getFirestore, doc, getDoc, setDoc, updateDoc, serverTimestamp
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

/* 동의서 판 번호. 문구가 실질적으로 바뀌면 올린다 — 올리면 기존 회원도
   다음 로그인 때 새 동의를 한 번 받는다. 오탈자 수정 정도로는 올리지 않는다. */
export const CONSENT_VERSION = "2026-08-20";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);

if (window.KOSi18n) window.KOSi18n.register({
  "약관 동의": "Agreements",
  "전체 동의": "Agree to all",
  "[필수] 만 14세 이상입니다": "[Required] I am 14 or older",
  "[필수] 이용약관 동의": "[Required] Terms of Service",
  "[필수] 개인정보 수집·이용 동의": "[Required] Collection and use of personal data",
  "[선택] 마케팅 정보 수신 동의": "[Selective] Marketing messages",
  "보기": "View",
  "수집 항목: 이메일, 닉네임, 로그인 수단": "Collected: email, nickname, sign-in provider",
  "이용 목적: 회원 식별과 서비스 제공": "Purpose: identifying members and providing the service",
  "보유 기간: 회원 탈퇴 시까지": "Retained: until the account is deleted",
  "새 리포트·서비스 소식을 이메일로 받습니다. 동의하지 않아도 가입할 수 있습니다.":
    "Receive news about new reports and the service by email. You can sign up without agreeing.",
  "언제든 철회할 수 있습니다.": "You can withdraw at any time.",
  "필수 항목에 동의해야 가입할 수 있어요.": "You must accept the required items to continue.",
  "서비스를 이용하려면 약관 동의가 필요합니다": "Using the service requires your agreement",
  "동의하고 계속하기": "Agree and continue",
  "동의하지 않고 로그아웃": "Sign out instead",
  "동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.":
    "Could not save your agreement. Please try again in a moment.",
  "마케팅 수신 설정": "Marketing messages",
  "새 리포트와 서비스 소식을 이메일로 받습니다.": "Get news about new reports and the service by email.",
  "받지 않아도 서비스 이용에는 아무 영향이 없습니다.":
    "Turning this off does not affect your use of the service.",
  "수신 동의함": "Subscribed",
  "수신 동의 안 함": "Not subscribed",
  "저장": "Save",
  "닫기": "Close",
  "저장했습니다.": "Saved.",
  "저장에 실패했어요. 잠시 후 다시 시도해 주세요.":
    "Could not save. Please try again in a moment.",
  "불러오지 못했어요. 잠시 후 다시 시도해 주세요.":
    "Could not load. Please try again in a moment."
});

/* 필수 항목의 키. validate() 가 이 목록만 본다 — 항목을 늘릴 때
   여기 추가하지 않으면 화면에는 보이는데 검사에서 빠진다. */
const REQUIRED = ["age14", "terms", "privacy"];

const ITEMS = [
  { key: "age14", required: true, label: "[필수] 만 14세 이상입니다" },
  { key: "terms", required: true, label: "[필수] 이용약관 동의", href: "Terms.html" },
  {
    key: "privacy", required: true, label: "[필수] 개인정보 수집·이용 동의",
    href: "Privacy.html",
    detail: [
      "수집 항목: 이메일, 닉네임, 로그인 수단",
      "이용 목적: 회원 식별과 서비스 제공",
      "보유 기간: 회원 탈퇴 시까지"
    ]
  },
  {
    key: "marketing", required: false, label: "[선택] 마케팅 정보 수신 동의",
    detail: [
      "새 리포트·서비스 소식을 이메일로 받습니다. 동의하지 않아도 가입할 수 있습니다.",
      "언제든 철회할 수 있습니다."
    ]
  }
];

/* ────────────────────────────── 화면 ────────────────────────────── */

function css() {
  if (document.getElementById("kos-consent-css")) return;
  const s = document.createElement("style");
  s.id = "kos-consent-css";
  s.textContent = `
.kc{border:1px solid var(--border-2);border-radius:var(--radius-md);padding:12px 14px;margin:4px 0 6px}
.kc.invalid{border-color:#c0282b}
.kc-all{display:flex;gap:9px;align-items:center;font:600 13.5px/1.5 var(--font-sans);color:var(--fg-1);
  padding-bottom:10px;margin-bottom:8px;border-bottom:1px solid var(--hair);cursor:pointer}
.kc-row{display:flex;gap:9px;align-items:flex-start;font:400 12.5px/1.5 var(--font-sans);
  color:var(--fg-2);padding:5px 0;cursor:pointer}
.kc-row input,.kc-all input{margin:1px 0 0;width:15px;height:15px;flex:none;accent-color:var(--brand-blue)}
.kc-row span{flex:1}
.kc-row a{color:var(--brand-blue);text-decoration:none;font-size:12px;white-space:nowrap;margin-left:6px}
.kc-row a:hover{text-decoration:underline}
:root[data-theme="dark"] .kc-row a{color:var(--brand-cyan)}
.kc-detail{margin:2px 0 6px 24px;font:400 11.5px/1.6 var(--font-sans);color:var(--fg-3)}
.kc-err{display:none;margin:6px 0 0;font:600 12px/1.45 var(--font-sans);color:#c0282b}
:root[data-theme="dark"] .kc-err{color:#ff8a8c}
.kc-err.on{display:block}
/* 로그인 뒤에 뜨는 동의 화면 — 닫을 수 없다. 동의하거나 로그아웃뿐이다. */
.kc-ov{position:fixed;inset:0;z-index:1000;background:rgba(10,11,19,.55);
  display:flex;align-items:center;justify-content:center;padding:20px;
  -webkit-backdrop-filter:blur(4px);backdrop-filter:blur(4px)}
.kc-card{width:100%;max-width:440px;background:var(--bg-1);border-radius:var(--radius-lg);
  padding:22px;box-shadow:var(--shadow-2);max-height:90vh;overflow:auto}
:root[data-theme="dark"] .kc-card{background:#1a1b26}
.kc-h{margin:0 0 4px;font:700 17px/1.35 var(--font-sans);color:var(--fg-1)}
.kc-sub{margin:0 0 14px;font:400 13px/1.6 var(--font-sans);color:var(--fg-2)}
.kc-act{display:flex;flex-direction:column;gap:8px;margin-top:14px}
.kc-no{background:none;border:0;font:500 12.5px var(--font-sans);color:var(--fg-3);
  cursor:pointer;padding:6px;text-decoration:underline}`;
  document.head.appendChild(s);
}

/* 동의 항목 묶음을 그린다. { el, validate(), values() } 를 돌려준다. */
export function renderConsent(opts = {}) {
  css();
  const box = document.createElement("div");
  box.className = "kc";

  const all = document.createElement("label");
  all.className = "kc-all";
  all.innerHTML = `<input type="checkbox"><span data-i18n>${T("전체 동의")}</span>`;
  box.appendChild(all);

  const boxes = {};
  for (const it of ITEMS) {
    const row = document.createElement("label");
    row.className = "kc-row";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    boxes[it.key] = cb;
    const span = document.createElement("span");
    span.textContent = T(it.label);
    row.appendChild(cb);
    row.appendChild(span);
    if (it.href) {
      const a = document.createElement("a");
      a.href = it.href; a.target = "_blank"; a.rel = "noopener";
      a.textContent = T("보기");
      // 라벨 안의 링크를 누르면 체크까지 토글된다 — 약관을 보려던 것뿐이다.
      a.addEventListener("click", e => e.stopPropagation());
      row.appendChild(a);
    }
    box.appendChild(row);
    if (it.detail) {
      const d = document.createElement("div");
      d.className = "kc-detail";
      d.textContent = it.detail.map(x => T(x)).join(" · ");
      box.appendChild(d);
    }
  }

  const err = document.createElement("div");
  err.className = "kc-err";
  err.textContent = T("필수 항목에 동의해야 가입할 수 있어요.");
  box.appendChild(err);

  const list = ITEMS.map(i => boxes[i.key]);
  const sync = () => { all.querySelector("input").checked = list.every(c => c.checked); };
  all.querySelector("input").addEventListener("change", e => {
    list.forEach(c => { c.checked = e.target.checked; });
    clear();
  });
  list.forEach(c => c.addEventListener("change", () => { sync(); clear(); }));

  function clear() { box.classList.remove("invalid"); err.classList.remove("on"); }

  return {
    el: box,
    values() {
      const v = {};
      for (const it of ITEMS) v[it.key] = !!boxes[it.key].checked;
      return v;
    },
    validate() {
      const v = this.values();
      const ok = REQUIRED.every(k => v[k]);
      if (!ok) {
        box.classList.add("invalid");
        err.classList.add("on");
        const first = REQUIRED.find(k => !v[k]);
        try { boxes[first].focus(); } catch (e) {}
      }
      return ok;
    }
  };
}

/* ────────────────────────────── 기록 ────────────────────────────── */

function db() { return getFirestore(app); }

export async function saveConsent(uid, values, method) {
  const consents = { version: CONSENT_VERSION, agreedAt: serverTimestamp() };
  for (const it of ITEMS) consents[it.key] = !!values[it.key];
  await setDoc(doc(db(), "users", uid), {
    consents,
    // 마케팅 동의를 켠 시각. 끄면 null 로 지운다 — 언제 받았는지가 남아야
    // 나중에 "이 사람 언제 동의했나" 를 답할 수 있다.
    marketingAt: values.marketing ? serverTimestamp() : null,
    signupMethod: method || "unknown",
    createdAt: serverTimestamp(),
    updatedAt: serverTimestamp()
  }, { merge: true });
}

/* 이 계정이 현재 판(version)의 동의를 갖고 있나.
   읽기에 실패하면 null 을 돌려준다 — '없다'와 구분해야 한다. 통신이 잠깐
   끊겼다고 로그인을 막으면 안 된다. */
export async function consentState(uid) {
  try {
    const snap = await getDoc(doc(db(), "users", uid));
    const c = snap.exists() ? (snap.data().consents || null) : null;
    if (!c) return false;
    return c.version === CONSENT_VERSION && REQUIRED.every(k => c[k] === true);
  } catch (e) {
    console.warn("[consent] 조회 실패:", e && e.code);
    return null;
  }
}

/* 카카오·네이버는 페이지를 떠났다 돌아온다. 그 사이 체크 상태가 사라지므로
   떠나기 전에 담아 두고 돌아와서 꺼낸다. */
const STASH = "kos_consent_pending";
export function stashConsent(values, method) {
  try { sessionStorage.setItem(STASH, JSON.stringify({ values, method })); } catch (e) {}
}
export function takeStashed() {
  try {
    const raw = sessionStorage.getItem(STASH);
    sessionStorage.removeItem(STASH);
    return raw ? JSON.parse(raw) : null;
  } catch (e) { return null; }
}

/* ────────────────────── 로그인 뒤 동의 받기 ────────────────────── */

/* 동의 기록이 없으면 화면을 띄우고 받는다. 동의하면 true, 로그아웃하면 false.
   기록이 이미 있거나 조회에 실패하면 아무것도 하지 않고 true. */
export async function ensureConsent(user, onSignOut) {
  const state = await consentState(user.uid);
  if (state === true || state === null) return true;

  // 리다이렉트 직전에 담아 둔 게 있으면 그대로 저장하고 화면을 띄우지 않는다.
  const stashed = takeStashed();
  if (stashed && REQUIRED.every(k => stashed.values[k])) {
    try {
      await saveConsent(user.uid, stashed.values, stashed.method);
      return true;
    } catch (e) { console.warn("[consent] 저장 실패:", e && e.code); }
  }

  css();
  return new Promise(resolve => {
    const ov = document.createElement("div");
    ov.className = "kc-ov";
    const card = document.createElement("div");
    card.className = "kc-card";
    const h = document.createElement("div");
    h.className = "kc-h"; h.textContent = T("서비스를 이용하려면 약관 동의가 필요합니다");
    const sub = document.createElement("p");
    sub.className = "kc-sub";
    sub.textContent = T("수집 항목: 이메일, 닉네임, 로그인 수단");
    const set = renderConsent();
    const act = document.createElement("div");
    act.className = "kc-act";
    const ok = document.createElement("button");
    ok.type = "button"; ok.className = "btn btn-primary";
    ok.textContent = T("동의하고 계속하기");
    const no = document.createElement("button");
    no.type = "button"; no.className = "kc-no";
    no.textContent = T("동의하지 않고 로그아웃");
    act.appendChild(ok); act.appendChild(no);
    card.appendChild(h); card.appendChild(sub); card.appendChild(set.el); card.appendChild(act);
    ov.appendChild(card);
    document.body.appendChild(ov);

    ok.addEventListener("click", async () => {
      if (!set.validate()) return;
      ok.disabled = true;
      try {
        await saveConsent(user.uid, set.values(), (user.providerData[0] || {}).providerId || "unknown");
        ov.remove();
        resolve(true);
      } catch (e) {
        ok.disabled = false;
        const err = card.querySelector(".kc-err");
        err.textContent = T("동의 저장에 실패했어요. 잠시 후 다시 시도해 주세요.");
        err.classList.add("on");
      }
    });
    no.addEventListener("click", async () => {
      ov.remove();
      try { await onSignOut(); } catch (e) {}
      resolve(false);
    });
  });
}

/* ────────────────── 마케팅 수신 설정 (철회 포함) ────────────────── */

/* 동의는 언제든 철회할 수 있어야 한다. 켜는 것만 있고 끄는 길이 없으면
   그건 동의가 아니다. 계정 메뉴에서 이 화면을 연다.

   끌 때 marketingAt 을 지우고 marketingOffAt 을 남긴다. "언제 동의했고
   언제 철회했나" 를 나중에 답할 수 있어야 하기 때문이다. */
export async function openMarketingSettings(user) {
  css();
  const ov = document.createElement("div");
  ov.className = "kc-ov";
  const card = document.createElement("div");
  card.className = "kc-card";
  card.innerHTML =
    `<div class="kc-h">${T("마케팅 수신 설정")}</div>
     <p class="kc-sub">${T("새 리포트와 서비스 소식을 이메일로 받습니다.")}<br>${T("받지 않아도 서비스 이용에는 아무 영향이 없습니다.")}</p>`;

  const box = document.createElement("div");
  box.className = "kc";
  const row = document.createElement("label");
  row.className = "kc-row";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.disabled = true;                    // 현재 값을 읽어오기 전에는 못 만진다
  const span = document.createElement("span");
  span.textContent = T("수신 동의 안 함");
  row.appendChild(cb); row.appendChild(span);
  box.appendChild(row);
  const err = document.createElement("div");
  err.className = "kc-err";
  box.appendChild(err);
  card.appendChild(box);

  const act = document.createElement("div");
  act.className = "kc-act";
  const save = document.createElement("button");
  save.type = "button"; save.className = "btn btn-primary";
  save.textContent = T("저장"); save.disabled = true;
  const close = document.createElement("button");
  close.type = "button"; close.className = "kc-no";
  close.textContent = T("닫기");
  act.appendChild(save); act.appendChild(close);
  card.appendChild(act);
  ov.appendChild(card);
  document.body.appendChild(ov);

  const label = () => { span.textContent = T(cb.checked ? "수신 동의함" : "수신 동의 안 함"); };
  cb.addEventListener("change", () => { label(); err.classList.remove("on"); });
  close.addEventListener("click", () => ov.remove());
  // 이 화면은 닫아도 된다 — 동의 화면과 달리 막아설 이유가 없다.
  ov.addEventListener("click", e => { if (e.target === ov) ov.remove(); });

  try {
    const snap = await getDoc(doc(db(), "users", user.uid));
    cb.checked = !!(snap.exists() && (snap.data().consents || {}).marketing);
    label();
    cb.disabled = false; save.disabled = false;
  } catch (e) {
    err.textContent = T("불러오지 못했어요. 잠시 후 다시 시도해 주세요.");
    err.classList.add("on");
    return;
  }

  save.addEventListener("click", async () => {
    save.disabled = true; cb.disabled = true;
    try {
      const on = cb.checked;
      await updateDoc(doc(db(), "users", user.uid), {
        "consents.marketing": on,
        marketingAt: on ? serverTimestamp() : null,
        marketingOffAt: on ? null : serverTimestamp(),
        updatedAt: serverTimestamp()
      });
      err.style.color = "var(--fg-2)";
      err.textContent = T("저장했습니다.");
      err.classList.add("on");
      setTimeout(() => ov.remove(), 900);
    } catch (e) {
      save.disabled = false; cb.disabled = false;
      err.style.color = "";
      err.textContent = T("저장에 실패했어요. 잠시 후 다시 시도해 주세요.");
      err.classList.add("on");
    }
  });
}
