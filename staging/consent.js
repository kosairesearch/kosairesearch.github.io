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
  "이용약관": "Terms of Service"
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

/* 동의 항목 묶음을 그린다. { el, validate(), values() } 를 돌려준다.

   opts.requiredOnly — 필수 항목만 그린다. 약관을 개정해 재동의를 받을 때
   쓴다. 마케팅 수신은 선택 항목이라 설정 화면이 관리하는데, 재동의 화면에
   빈 칸으로 다시 내밀면 켜 둔 사람이 그대로 두는 순간 꺼진 것처럼 보인다.
   묻지 않는 편이 맞다 — 서버도 재동의 때는 마케팅을 건드리지 않는다. */
export function renderConsent(opts = {}) {
  css();
  const box = document.createElement("div");
  box.className = "kc";
  const items = opts.requiredOnly ? ITEMS.filter(i => i.required) : ITEMS;

  const all = document.createElement("label");
  all.className = "kc-all";
  all.innerHTML = `<input type="checkbox"><span data-i18n>${T("전체 동의")}</span>`;
  box.appendChild(all);

  const boxes = {};
  for (const it of items) {
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
      /* 조각마다 제 노드를 준다. 이어 붙여 텍스트 노드 하나로 만들면 안 된다.
         i18n 엔진은 텍스트 노드의 내용 전체를 사전 키로 찾는데, 이어 붙인
         "수집 항목: … · 이용 목적: … · 보유 기간: …" 은 사전에 없는 문자열이다.
         그래서 라벨은 영어로 바뀌는데 이 줄만 한국어로 남아 있었다.
         (T() 로 미리 번역해 둬도 소용없다 — 언어를 토글하면 엔진이 그때
          화면에 있던 값을 원본으로 삼아 다시 찾으므로 결국 같은 자리에서 막힌다.) */
      it.detail.forEach((x, i) => {
        if (i) d.appendChild(document.createTextNode(" · "));
        const sp = document.createElement("span");
        sp.textContent = T(x);
        d.appendChild(sp);
      });
      box.appendChild(d);
    }
  }

  const err = document.createElement("div");
  err.className = "kc-err";
  err.textContent = T("필수 항목에 동의해야 가입할 수 있어요.");
  box.appendChild(err);

  const list = items.map(i => boxes[i.key]);
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
      for (const it of items) v[it.key] = !!boxes[it.key].checked;
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

/* 서버에 탈퇴를 맡긴다. users 문서·워치리스트·열람 기록·동의 이력을 지우고
   카카오 연결까지 끊은 뒤 Auth 사용자를 지운다.

   클라이언트가 deleteUser 만 부르면 Auth 사용자만 사라지고 우리 문서는
   남는다 — 규칙으로 users 쓰기를 닫아 두었으니 지울 방법도 없다. */
export async function deleteMyAccount() {
  const r = await callFn("deleteAccount", {});
  return (r && r.data) || {};
}

export async function saveConsent(uid, values, method, email) {
  /* 서버가 돌려주는 것을 그대로 넘긴다 — { first, reconsent }.
     부르는 쪽이 '가입을 마친 것' 과 '개정 때문에 다시 받은 것' 을
     갈라야 하는데, 그것을 아는 것은 서버뿐이다(기존 기록을 본다). */
  const r = await callFn("recordSignupConsent", {
    method: "checkbox",
    provider: method || "email",
    marketing: !!(values && values.marketing),
    email: email || ""
  });
  return (r && r.data) || {};
}

/* saveImpliedConsent 는 없앴다. 한 줄 고지로 받던 동의를 기록하던 함수인데,
   정작 구글 경로는 collectConsent 로 체크박스를 띄워 놓고 그 결과를 이
   함수로 저장하고 있었다 — 체크박스로 받은 동의가 'signup-notice' 로
   기록되고 있었다는 뜻이다. 이제 구글도 saveConsent 를 쓴다. */

/* 소셜 버튼 아래 한 줄 고지(SIGNUP_NOTICE / noticeEl)는 없앴다.

   왜 있었나. 카카오·네이버는 자기 동의 화면을 이미 보여 주니 우리 화면을
   한 번 더 얹지 말자고 판단했고, 대신 그 한 줄로 동의를 받았다.

   왜 없앴나. 그 판단에 구멍이 있었다. 카카오·네이버의 동의 화면은
   '그쪽이 우리에게 닉네임·이메일을 넘기는 것' 에 대한 동의이지, 우리
   이용약관에 대한 동의가 아니다. 즉 그 한 줄이 우리 약관 동의의 유일한
   근거였는데, 한 줄 고지는 개인정보 수집·이용 동의로 쓰기에 약하다
   (개인정보보호법 제22조는 항목을 구분해 각각 받도록 한다).

   그래서 네 경로 모두가 진짜 동의 절차를 갖도록 바꿨다.

     카카오 — 카카오싱크 간편가입. 콘솔에 이용약관·개인정보 수집·이용을
              필수 동의항목으로, 마케팅을 선택 동의항목으로 등록했고
              만 14세 연령 동의도 걸었다.
     네이버 — 개발자센터 콘솔에서 같은 세 가지를 받는다.
     구글   — finishGoogleSignup 이 우리 모달을 띄운다.
     이메일 — 가입 폼의 체크박스.

   그러고 나니 이 줄은 하는 일이 없어졌다. 남겨 두는 편이 오히려 나빴다.
   체크박스로 명시적 동의를 받아 놓고 그 아래에 "계속 진행하면 동의하게
   되며" 라고 써 두면, 우리가 받은 동의를 우리 손으로 묵시적 동의라고
   표시하는 셈이다. Signup.html 에서는 필수 체크박스 세 개 바로 아래에
   그 문장이 붙어 있었다.

   ⚠️ 남은 일. functions/index.js 의 socialLogin 은 아직 신규 소셜 가입자의
      동의를 age14/terms/privacy = true 로 하드코딩한다. 카카오 간편가입이
      승인되면 service_terms API 로 실제 동의 내역을 받아 그대로 기록해야
      한다. 그래야 마케팅 선택 동의도 사람마다 제대로 들어온다. */

/* 이 계정이 현재 판(version)의 동의를 갖고 있나.
   읽기에 실패하면 null 을 돌려준다 — '없다'와 구분해야 한다. 통신이 잠깐
   끊겼다고 로그인을 막으면 안 된다. */
export async function consentState(uid) {
  const s = await consentStage(uid);
  return s === null ? null : s === "ok";
}

/* 왜 아닌지까지 알려 주는 판. 동의 화면이 이걸 보고 문구를 고른다.

     "ok"     최신 판에 동의했다
     "none"   동의 기록이 아예 없다 — 가입을 마치지 못한 계정
     "stale"  동의는 했는데 그 뒤 약관이 개정됐다 — 재동의
     null     못 읽었다(통신·규칙). '없다'와 구분해야 한다 — 통신이 잠깐
              끊겼다고 로그인을 막으면 안 된다.

   둘을 갈라야 하는 이유는 화면에 쓸 말이 다르기 때문이다. 3년 쓴 회원에게
   "가입을 마치려면" 이라고 하면 무슨 소린지 알 수 없고, 취소 버튼이
   "동의하지 않고 취소" 인 것도 맞지 않는다. */
export async function consentStage(uid) {
  try {
    const snap = await getDoc(doc(db(), "users", uid));
    const c = snap.exists() ? (snap.data().consents || null) : null;
    if (!c || !REQUIRED.every(k => c[k] === true)) return "none";
    return c.version === CONSENT_VERSION ? "ok" : "stale";
  } catch (e) {
    console.warn("[consent] 조회 실패:", e && e.code);
    return null;
  }
}

/* ──────── 로그인 뒤 동의 받기 — 페이지로 옮겼다 ────────

   ensureConsent(모달) 와 collectConsent(모달) 가 여기 있었다. 둘 다 지웠다.

   동의는 이제 Consent.html 한 곳에서 받는다. 모달은 좁아 글자를 키울 수
   없었고, '가입이 아직 안 끝났다' 는 것이 화면에 드러나지 않았다.

   가입을 마치지 못한 계정(구글 팝업이 닫힌 뒤 동의 페이지에서 탭을 닫은
   경우)은 auth-state.js 의 guardConsent 가 다음 접속 때 이 페이지로 보낸다.
   ensureConsent 는 만들어만 놓고 아무도 부르지 않아 그 구멍을 못 막고
   있었다 — 화면을 하나로 모으면서 부르는 자리도 하나로 정했다.

   화면 조각(renderConsent)과 기록(saveConsent)은 그대로 남아 있다.
   Consent.html 이 그 둘을 쓴다.                                    */

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
export function finishGoogleSignup(cred, isNewUser) {
  if (!isNewUser) return Promise.resolve(true);
  /* 신규 가입이면 동의 페이지로 보낸다.
     저장도 계정 삭제도 저쪽에서 한다 — 동의를 다루는 자리가 둘로 갈리면
     한쪽만 고치는 일이 생긴다.

     false 를 돌려주는 이유: 부르는 쪽이 `if(!await finishGoogleSignup(...)) return;`
     로 쓰고 있다. 여기서 true 를 주면 리다이렉트가 뜨기 전에 goNext() 가
     먼저 돌아 원래 가려던 페이지로 가 버린다. */
  const nx = new URLSearchParams(location.search).get("next") || "Home.html";
  location.replace("Consent.html?next=" + encodeURIComponent(nx));
  return Promise.resolve(false);
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
  if (!user) return { name: "", email: "", method: "", methodLabel: "알 수 없음" };

  /* 문서 읽기를 무한정 기다리지 않는다.

     닉네임과 이메일은 Auth 에 이미 들어 있다. users 문서는 그 값이 없을 때
     쓰는 예비일 뿐인데, 그 읽기가 안 돌아오면 화면이 '—' 로 굳는다.
     모바일에서 실제로 그랬다 — 계정에 이메일이 멀쩡히 있는데도 두 칸이
     빈 채로 남았다.

     예비 자료를 기다리다 본 자료까지 못 보여 주는 것은 순서가 뒤집힌 것이다.
     4초 안에 안 오면 없는 것으로 치고 넘어간다. */
  let doc0 = null;
  try {
    doc0 = await Promise.race([
      getDoc(doc(db(), "users", user.uid)).then(s => (s.exists() ? s.data() : null)),
      new Promise(r => setTimeout(() => r(null), 4000)),
    ]);
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
