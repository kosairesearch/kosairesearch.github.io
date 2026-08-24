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
import { app, auth, SOCIAL } from "./firebase-config.js";
import { deleteUser } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import {
  getFirestore, doc, getDoc
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

/* 동의 기록을 쓰는 함수가 있는 리전. 읽기는 클라이언트가 직접 하지만
   쓰기는 전부 서버를 거친다(아래 callFn 주석 참고). */
const FN_REGION = (SOCIAL && SOCIAL.functionsRegion) || "asia-northeast3";

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
  "동의하고 가입 완료": "Agree and finish signing up",
  "동의하지 않고 취소": "Cancel",
  "가입을 마치려면 아래 항목에 동의해 주세요": "To finish signing up, please accept the items below",
  "동의하지 않으면 가입이 취소됩니다.": "If you do not agree, your sign-up is cancelled.",
  "동의하지 않으면 가입이 진행되지 않습니다. 계정은 아직 만들어지지 않았어요.":
    "Without your consent we will not create the account — nothing has been created yet.",
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
    "Could not load. Please try again in a moment.",
  "계속 진행하면 ": "By continuing you agree to the ",
  "이용약관": "Terms of Service",
  " 및 ": " and to the ",
  "개인정보 수집·이용": "collection and use of your personal data",
  "에 동의하게 되며, 만 14세 이상만 가입할 수 있습니다.":
    ". Sign-up is limited to those aged 14 and over."
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
  cursor:pointer;padding:6px;text-decoration:underline}
/* 소셜 버튼 아래 한 줄 고지 */
.kc-notice{margin:10px 2px 0;font:400 11.5px/1.6 var(--font-sans);color:var(--fg-3);text-align:center}
.kc-notice a{color:var(--fg-2);text-decoration:underline;text-underline-offset:2px}
.kc-notice a:hover{color:var(--brand-blue)}
:root[data-theme="dark"] .kc-notice a:hover{color:var(--brand-cyan)}`;
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
        /* 누른 자리에서 한참 떨어진 곳에 빨간 줄만 켜 두면 버튼이 죽은 것처럼
           보인다. 실제로 가입 페이지에서 그랬다 — 소셜 버튼은 위에 있고 동의
           상자는 768px 아래라 화면 밖이었다. 안내를 눈앞으로 데려온다. */
        try { box.scrollIntoView({ block: "center", behavior: "smooth" }); } catch (e) {}
        try { boxes[first].focus({ preventScroll: true }); } catch (e) { try { boxes[first].focus(); } catch (_) {} }
      }
      return ok;
    }
  };
}

/* ────────────────────────────── 기록 ────────────────────────────── */

function db() { return getFirestore(app); }

/* 동의 기록은 서버가 쓴다.

   전에는 여기서 users/{uid} 에 직접 썼다. 그러면 브라우저 콘솔을 열 수 있는
   사람은 누구나 age14 나 agreedAt 을 고칠 수 있다 — 본인이 고칠 수 있는
   기록은 나중에 아무것도 증명하지 못한다.

   그래서 값은 서버(recordSignupConsent)가 정한다. 여기서 보내는 것은
   선택 항목인 마케팅 수신 여부와, 어느 화면에서 받았는지뿐이다.

   실패하면 던진다. 부르는 쪽이 방금 만든 계정을 지운다 — 동의 기록 없는
   계정을 남기지 않는 것이 이 함수의 목적이다. */
function callFn(name, payload) {
  return httpsCallable(getFunctions(app, FN_REGION), name)(payload || {});
}

export async function saveConsent(uid, values, method, email) {
  await callFn("recordSignupConsent", {
    method: "checkbox",
    provider: method || "email",
    marketing: !!(values && values.marketing),
    email: email || ""
  });
}

/* 가입 버튼 아래 고지 문구로 받은 동의. 구글 경로가 쓴다.
   카카오·네이버는 서버가 socialLogin 안에서 같은 모양으로 남긴다. */
export async function saveImpliedConsent(uid, method, email, marketing) {
  await callFn("recordSignupConsent", {
    method: "signup-notice",
    provider: method || "google",
    marketing: !!marketing,
    email: email || ""
  });
}

/* 가입 버튼 아래에 붙는 한 줄. 소셜 버튼 밑에 이 문구가 있어야 위의
   saveImpliedConsent 가 성립한다 — 보여 준 적 없는 것에 동의시킬 수는 없다.
   문구가 한 곳에만 있어야 페이지마다 달라지지 않는다.

   문구를 고른 이유.

   '가입하면' 이 아니라 '계속 진행하면' 이다. 이 줄은 Signup.html 뿐 아니라
   Login.html 의 소셜 버튼 밑에도 붙는다 — 로그인하러 온 기존 회원에게
   '가입하면' 이라고 말하고 있었다. 조건절 구어체라 약관 고지의 무게도
   실리지 않는다.

   '개인정보처리방침에 동의' 가 아니라 '개인정보 수집·이용에 동의' 다.
   처리방침은 회사가 일방적으로 공개하는 문서라 동의를 받는 대상이 아니다
   (위 '동의 항목을 왜 나누나' 참고). 체크박스 라벨은 이미 '개인정보
   수집·이용 동의' 인데 이 줄만 옛 표현으로 남아 있었다.

   '만 14세 이상임을 확인합니다' 가 아니라 '만 14세 이상만 가입할 수
   있습니다' 다. 사용자가 자기 나이를 우리에게 확인해 주는 형태가 아니라,
   서비스의 가입 요건을 알리는 형태가 맞다. */
export const SIGNUP_NOTICE =
  "계속 진행하면 이용약관 및 개인정보 수집·이용에 동의하게 되며, " +
  "만 14세 이상만 가입할 수 있습니다.";

export function noticeEl() {
  const p = document.createElement("p");
  p.className = "kc-notice";
  const mk = (label, href) => {
    const a = document.createElement("a");
    a.href = href; a.target = "_blank"; a.rel = "noopener"; a.textContent = T(label);
    return a;
  };
  p.appendChild(document.createTextNode(T("계속 진행하면 ")));
  p.appendChild(mk("이용약관", "Terms.html"));
  p.appendChild(document.createTextNode(T(" 및 ")));
  p.appendChild(mk("개인정보 수집·이용", "Privacy.html"));
  p.appendChild(document.createTextNode(
    T("에 동의하게 되며, 만 14세 이상만 가입할 수 있습니다.")));
  css();
  return p;
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
    h.className = "kc-h"; h.textContent = T("가입을 마치려면 아래 항목에 동의해 주세요");
    const sub = document.createElement("p");
    sub.className = "kc-sub";
    sub.textContent = T("동의하지 않으면 가입이 취소됩니다.");
    const set = renderConsent();
    const act = document.createElement("div");
    act.className = "kc-act";
    const ok = document.createElement("button");
    ok.type = "button"; ok.className = "btn btn-primary";
    ok.textContent = T("동의하고 가입 완료");
    const no = document.createElement("button");
    no.type = "button"; no.className = "kc-no";
    no.textContent = T("동의하지 않고 취소");
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
      no.disabled = true;
      /* 거부하면 계정을 지운다. 로그아웃만 하면 동의하지 않은 계정이 그대로
         남는다 — 카카오·네이버는 인증이 끝나는 순간 계정이 먼저 만들어지기
         때문이다. 동의하지 않았으면 가입이 성립하지 않아야 한다.

         막 만들어진 계정이라 대개 지워지지만, 실패하면(재인증 요구 등)
         로그아웃이라도 한다. 남은 계정은 다음 로그인 때 다시 이 화면을
         만나므로 동의 없이 서비스가 쓰이지는 않는다. */
      try { await deleteUser(auth.currentUser || user); }
      catch (e) {
        console.warn("[consent] 계정 삭제 실패:", e && e.code);
        try { await onSignOut(); } catch (_) {}
      }
      ov.remove();
      resolve(false);
    });
  });
}

/* ────────────────── 마케팅 수신 (조회 · 변경) ────────────────── */

/* 동의는 언제든 철회할 수 있어야 한다. 켜는 길만 있고 끄는 길이 없으면
   그건 동의가 아니다.

   화면은 Settings.html 이 갖고 여기는 값만 다룬다. 처음에는 계정 메뉴에서
   바로 여는 모달로 만들었는데, 마케팅 설정이 로그아웃·탈퇴와 나란히 있는
   게 어색하다는 지적을 받았다. 보통 설정 페이지 안에 있다. */

export async function getMarketing(uid) {
  const snap = await getDoc(doc(db(), "users", uid));
  return !!(snap.exists() && (snap.data().consents || {}).marketing);
}

/* 켤 때와 끌 때의 시각을 따로 남긴다. 한 칸을 켰다 껐다 하면 "언제 동의했고
   언제 철회했나" 를 답할 수 없다.

   문서가 아직 없을 수도 있다 — 이 기능이 생기기 전에 가입한 사람이다.
   그래서 update 가 아니라 merge 로 쓴다. */
export async function setMarketing(uid, on) {
  await callFn("setMarketingConsent", { on: !!on });
}


/* ────────────── 가입 전 동의 받기 (계정 없이) ────────────── */

/* 로그인한 사용자가 없는 상태에서 동의만 받는다. 동의하면 값, 취소하면 null.

   ensureConsent 와 다른 점: 저장도, 계정 삭제도 하지 않는다. 카카오·네이버는
   서버가 신규 사용자면 계정을 만들지 않고 돌아오므로, 이 시점에는 지울 계정
   자체가 없다. 받은 값을 서버로 보내면 서버가 계정과 동의를 함께 만든다.

   이것이 올바른 순서다 — 동의가 먼저, 계정이 나중. */
export function collectConsent(opts = {}) {
  css();
  return new Promise(resolve => {
    const ov = document.createElement("div");
    ov.className = "kc-ov";
    const card = document.createElement("div");
    card.className = "kc-card";
    const h = document.createElement("div");
    h.className = "kc-h";
    h.textContent = T("가입을 마치려면 아래 항목에 동의해 주세요");
    const sub = document.createElement("p");
    sub.className = "kc-sub";
    /* 여기는 계정을 만들기 전이다. '취소됩니다' 라고 쓰면 이미 가입이 끝난
       것처럼 읽힌다 — 동의를 먼저 받으려고 순서를 고쳐 놓고 문구가 옛 순서를
       말하고 있으면 안 된다. (구글 경로는 계정이 이미 생긴 뒤라 저쪽 문구가
       맞다.) */
    sub.textContent = opts.accountCreated
      ? T("동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.")
      : T("동의하지 않으면 가입이 진행되지 않습니다. 계정은 아직 만들어지지 않았어요.");
    const set = renderConsent();
    const act = document.createElement("div");
    act.className = "kc-act";
    const ok = document.createElement("button");
    ok.type = "button"; ok.className = "btn btn-primary";
    ok.textContent = T("동의하고 가입 완료");
    const no = document.createElement("button");
    no.type = "button"; no.className = "kc-no";
    no.textContent = T("동의하지 않고 취소");
    act.appendChild(ok); act.appendChild(no);
    card.appendChild(h); card.appendChild(sub); card.appendChild(set.el); card.appendChild(act);
    ov.appendChild(card);
    document.body.appendChild(ov);

    ok.addEventListener("click", () => {
      if (!set.validate()) return;
      const v = set.values();
      v.version = CONSENT_VERSION;
      ov.remove();
      resolve(v);
    });
    no.addEventListener("click", () => { ov.remove(); resolve(null); });
  });
}


/* ────────────── 구글 가입 마무리 ────────────── */

/* 구글은 팝업이 닫히는 순간 파이어베이스가 계정을 만든다. 서버를 거치지
   않으므로 카카오·네이버처럼 '동의 먼저, 계정 나중' 순서를 쓸 수 없다.

   그래서 새 계정일 때만 그 자리에서 받고, 거부하거나 기록에 실패하면 방금
   만든 계정을 지운다. 만들었다가 지우는 것과 애초에 안 만드는 것은 다르지만,
   구글 경로에서 할 수 있는 최선이 이것이다. 동의 기록 없는 계정을 남기는
   것보다는 낫다.

   기존 사용자는 그냥 지나간다 — 로그인할 때마다 물으면 안 된다.

   로그인 화면과 가입 화면이 이 함수를 같이 쓴다. 전에는 같은 로직이 두
   군데 복사돼 있었고, 한쪽만 고쳐서 가입 화면에서는 동의를 받고 로그인
   화면에서는 안 받는 상태가 됐던 적이 있다.

   돌려주는 값: true 면 계속 진행, false 면 사용자가 취소한 것. */
export async function finishGoogleSignup(cred, isNewUser) {
  if (!isNewUser) return true;
  const v = await collectConsent({ accountCreated: true });
  if (!v) {
    try { await deleteUser(cred.user); } catch (_) {}
    try { await auth.signOut(); } catch (_) {}
    return false;
  }
  try {
    await saveImpliedConsent(cred.user.uid, "google", cred.user.email || "", v.marketing);
  } catch (e) {
    try { await deleteUser(cred.user); } catch (_) {}
    try { await auth.signOut(); } catch (_) {}
    throw e;
  }
  return true;
}


/* ────────────── 내 계정 정보 ────────────── */

/* 설정 페이지가 "내 계정에 뭐가 저장돼 있나" 를 보여 줄 때 쓴다.

   이메일이 두 군데에 있다. 이메일·구글 가입자는 Firebase 사용자에 있고,
   카카오·네이버 가입자는 커스텀 토큰이라 거기엔 없고 users/{uid} 에만
   있다. 화면에서는 그 차이가 보일 이유가 없으므로 여기서 합친다.

   users 문서를 못 읽어도(규칙·통신) 나머지는 보여 준다 — 표시용이다. */
const METHOD_LABEL = {
  email: "이메일", google: "구글", kakao: "카카오", naver: "네이버"
};

export async function accountInfo(user) {
  let doc0 = null;
  try {
    const snap = await getDoc(doc(db(), "users", user.uid));
    doc0 = snap.exists() ? snap.data() : null;
  } catch (e) { /* 표시용 — 없으면 없는 대로 */ }
  const method = (doc0 && doc0.signupMethod)
    || (String(user.uid).split(":")[0] === "kakao" ? "kakao"
      : String(user.uid).split(":")[0] === "naver" ? "naver"
      : ((user.providerData || [])[0] || {}).providerId === "google.com" ? "google"
      : ((user.providerData || [])[0] || {}).providerId === "password" ? "email" : "");
  return {
    name: user.displayName || "",
    email: user.email || (doc0 && doc0.email) || "",
    method,
    methodLabel: METHOD_LABEL[method] || "알 수 없음"
  };
}
