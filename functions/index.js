/* ============================================================
   KOS ai — 소셜 로그인 백엔드 (카카오 / 네이버 → Firebase 커스텀 토큰)
   ------------------------------------------------------------
   클라이언트(social-login.js)가 보낸 인가코드(code)를 받아
   카카오/네이버에서 액세스 토큰·프로필을 받은 뒤, 그 사용자에 대한
   Firebase 커스텀 토큰을 발급해 돌려줍니다.

   비밀키는 코드에 두지 않고 Secret Manager 로 주입합니다(SETUP.md 참고):
     firebase functions:secrets:set KAKAO_REST_KEY
     firebase functions:secrets:set KAKAO_CLIENT_SECRET   (선택)
     firebase functions:secrets:set NAVER_CLIENT_ID
     firebase functions:secrets:set NAVER_CLIENT_SECRET
   ============================================================ */
const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const admin = require("firebase-admin");
const { Resend } = require("resend");

admin.initializeApp();

const REGION = "asia-northeast3"; // 서울

const KAKAO_REST_KEY = defineSecret("KAKAO_REST_KEY");
const KAKAO_CLIENT_SECRET = defineSecret("KAKAO_CLIENT_SECRET"); // 카카오에서 사용 안 하면 빈 값
const NAVER_CLIENT_ID = defineSecret("NAVER_CLIENT_ID");
const NAVER_CLIENT_SECRET = defineSecret("NAVER_CLIENT_SECRET");
const RESEND_API_KEY = defineSecret("RESEND_API_KEY"); // 이메일 발송(Resend)

async function asJson(res, label){
  const text = await res.text();
  let json;
  try{ json = JSON.parse(text); }catch(e){ json = { raw: text }; }
  if(!res.ok){ console.error(`[${label}] HTTP ${res.status}:`, text.slice(0, 500)); throw new HttpsError("unauthenticated", `${label}_http_${res.status}: ${text.slice(0, 300)}`); }
  return json;
}

async function kakaoProfile(code, redirectUri){
  const clientId = (KAKAO_REST_KEY.value() || "").trim();
  const secret = (KAKAO_CLIENT_SECRET.value() || "").trim();
  console.log("[kakao] client_id len:", clientId.length,
    "preview:", clientId.slice(0, 4) + "…" + clientId.slice(-4),
    "| client_secret len:", secret.length,
    "| redirect_uri:", redirectUri);
  const body = new URLSearchParams({
    grant_type: "authorization_code",
    client_id: clientId,
    redirect_uri: redirectUri,
    code
  });
  if(secret) body.set("client_secret", secret);

  const tok = await asJson(await fetch("https://kauth.kakao.com/oauth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded;charset=utf-8" },
    body
  }), "kakao_token");
  if(!tok.access_token) throw new HttpsError("unauthenticated", "kakao_no_access_token");

  const me = await asJson(await fetch("https://kapi.kakao.com/v2/user/me", {
    headers: { Authorization: `Bearer ${tok.access_token}` }
  }), "kakao_me");

  const acc = me.kakao_account || {};
  const prof = acc.profile || {};
  return {
    id: String(me.id),
    email: acc.email || null,
    name: prof.nickname || (me.properties && me.properties.nickname) || "",
    photo: prof.profile_image_url || (me.properties && me.properties.profile_image) || null
  };
}

async function naverProfile(code, redirectUri, state){
  const url = "https://nid.naver.com/oauth2.0/token?" + new URLSearchParams({
    grant_type: "authorization_code",
    client_id: NAVER_CLIENT_ID.value(),
    client_secret: NAVER_CLIENT_SECRET.value(),
    code,
    state: state || ""
  });
  const tok = await asJson(await fetch(url), "naver_token");
  if(!tok.access_token) throw new HttpsError("unauthenticated", "naver_no_access_token");

  const me = await asJson(await fetch("https://openapi.naver.com/v1/nid/me", {
    headers: { Authorization: `Bearer ${tok.access_token}` }
  }), "naver_me");

  const r = me.response || {};
  return {
    id: String(r.id),
    email: r.email || null,
    name: r.name || r.nickname || "",
    photo: r.profile_image || null
  };
}

exports.socialLogin = onCall(
  {
    region: REGION,
    cors: true,
    secrets: [KAKAO_REST_KEY, KAKAO_CLIENT_SECRET, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET]
  },
  async (req) => {
    const { provider, code, redirectUri, state } = req.data || {};
    if(!provider || !code || !redirectUri){
      throw new HttpsError("invalid-argument", "provider, code, redirectUri 가 필요합니다.");
    }

    let p;
    if(provider === "kakao") p = await kakaoProfile(code, redirectUri);
    else if(provider === "naver") p = await naverProfile(code, redirectUri, state);
    else throw new HttpsError("invalid-argument", "알 수 없는 provider 입니다.");

    if(!p.id) throw new HttpsError("internal", "프로필 ID를 가져오지 못했습니다.");

    const uid = `${provider}:${p.id}`;
    // 이메일은 다른 로그인 방식과의 계정 충돌을 피하기 위해 Firebase 사용자에 직접
    // 저장하지 않고 커스텀 클레임으로만 전달합니다.
    const userProps = {};
    if(p.name) userProps.displayName = p.name;
    if(p.photo) userProps.photoURL = p.photo;

    try{
      await admin.auth().updateUser(uid, userProps);
    }catch(e){
      if(e.code === "auth/user-not-found"){
        await admin.auth().createUser({ uid, ...userProps });
      }else{
        throw new HttpsError("internal", `user_upsert_failed: ${e.code || e.message}`);
      }
    }

    const token = await admin.auth().createCustomToken(uid, {
      provider,
      email: p.email || ""
    });
    return { token };
  }
);

/* ============================================================
   이메일 인증 / 비밀번호 재설정 — 커스텀 디자인 메일 발송
   ------------------------------------------------------------
   Firebase 기본 메일은 본문을 못 바꾸므로(스팸 방지 잠금),
   Admin SDK 로 액션 링크만 생성하고 Resend 로 우리 HTML 메일을 발송합니다.
     firebase functions:secrets:set RESEND_API_KEY
   발신 도메인(kosai.kr)은 Resend 콘솔에서 인증되어 있어야 합니다.
   ============================================================ */
const SITE_URL = "https://kosai.kr";
const ACTION_PAGE = SITE_URL + "/auth-action.html";  // 우리 디자인의 처리 페이지
const MAIL_FROM = "KOSAI <hello@kosai.kr>";
const FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Apple SD Gothic Neo','Malgun Gothic',sans-serif";
const ACTION_SETTINGS = { url: SITE_URL + "/Login.html", handleCodeInApp: false };

// Firebase 기본 액션 링크(firebaseapp.com/__/auth/action?...)의 쿼리는 유지하고
// 도착지만 우리 페이지로 바꿔, 메일 버튼이 우리 디자인 화면으로 가게 한다.
function customActionLink(rawLink, lang){
  try{
    const u = new URL(rawLink); const t = new URL(ACTION_PAGE); t.search = u.search;
    if(lang) t.searchParams.set("lang", lang);   // 처리 페이지도 같은 언어로
    return t.toString();
  }catch(e){ return rawLink; }
}

function esc(s){ return String(s || "").replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c])); }

function mailLayout({ lang, heading, intro, btnText, link, outro }){
  const en = lang === "en";
  const footBrand = en ? "KOSAI · AI research on Korean listed companies" : "KOSAI · 한국 상장사 AI 리서치";
  const footContact = en ? "Contact" : "문의";
  const autoNote = en
    ? "This email was sent automatically based on your KOSAI account activity."
    : "본 메일은 KOSAI 계정 활동에 따라 자동 발송되었습니다.";
  return `<!doctype html><html lang="${en ? "en" : "ko"}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f3fa;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f3fa;padding:32px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;border:1px solid #e7e9f2;">
    <tr><td style="padding:28px 32px 0 34px;">
      <img src="${SITE_URL}/assets/kosai-wordmark-black.png" alt="KOSAI" width="123" height="20" style="display:block;border:0;outline:none;text-decoration:none;height:20px;width:123px;">
    </td></tr>
    <tr><td style="padding:18px 32px 0;">
      <h1 style="margin:0;font:700 20px/1.4 ${FONT};color:#0d0d12;letter-spacing:-.01em;">${esc(heading)}</h1>
      <p style="margin:14px 0 0;font:400 15px/1.65 ${FONT};color:#41434d;">${intro}</p>
    </td></tr>
    <tr><td style="padding:22px 32px 0;">
      <a href="${esc(link)}" style="display:inline-block;background:#0d69d4;color:#ffffff;text-decoration:none;font:600 15px/1 ${FONT};padding:14px 28px;border-radius:10px;">${esc(btnText)}</a>
    </td></tr>
    <tr><td style="padding:18px 32px 0;">
      <p style="margin:0;font:400 13px/1.6 ${FONT};color:#8a8c97;">${esc(outro)}</p>
    </td></tr>
    <tr><td style="padding:22px 32px 28px;">
      <hr style="border:none;border-top:1px solid #eceef5;margin:0 0 16px;">
      <p style="margin:0;font:400 12px/1.65 ${FONT};color:#a7a9b4;">${footBrand}<br>${footContact} <a href="mailto:hello@kosai.kr" style="color:#8a8c97;text-decoration:none;">hello@kosai.kr</a> · <a href="${SITE_URL}" style="color:#8a8c97;text-decoration:none;">kosai.kr</a></p>
    </td></tr>
  </table>
  <p style="max-width:480px;margin:14px auto 0;font:400 11px/1.5 ${FONT};color:#b3b5bf;">${autoNote}</p>
</td></tr>
</table></body></html>`;
}

function verifyMail(name, link, lang){
  const en = lang === "en";
  if(en){
    return {
      subject: "Verify your KOSAI email address",
      html: mailLayout({ lang, heading: "Verify your email address",
        intro: name
          ? `Hi ${esc(name)}, welcome to KOSAI. Tap the button below to verify your email and unlock all features.`
          : "Welcome to KOSAI. Tap the button below to verify your email and unlock all features.",
        btnText: "Verify email", link,
        outro: "If you didn't sign up, you can safely ignore this email." })
    };
  }
  const hi = name ? `${esc(name)}님, ` : "";
  return {
    subject: "KOSAI 이메일 주소를 인증해 주세요",
    html: mailLayout({ lang, heading: "이메일 주소를 인증해 주세요",
      intro: `${hi}KOSAI 가입을 환영합니다. 아래 버튼을 눌러 이메일 인증을 완료하면 모든 기능을 이용하실 수 있어요.`,
      btnText: "이메일 인증하기", link,
      outro: "본인이 가입하지 않았다면 이 메일을 무시하셔도 됩니다." })
  };
}
function resetMail(link, lang){
  const en = lang === "en";
  if(en){
    return {
      subject: "Reset your KOSAI password",
      html: mailLayout({ lang, heading: "Reset your password",
        intro: "We received a request to reset your password. Tap the button below to set a new one.",
        btnText: "Reset password", link,
        outro: "If you didn't request this, you can ignore this email — your password won't change and your account stays safe." })
    };
  }
  return {
    subject: "KOSAI 비밀번호 재설정 안내",
    html: mailLayout({ lang, heading: "비밀번호를 재설정하세요",
      intro: "비밀번호 재설정 요청을 받았습니다. 아래 버튼을 눌러 새 비밀번호를 설정해 주세요.",
      btnText: "비밀번호 재설정하기", link,
      outro: "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다. 비밀번호는 변경되지 않으며 계정은 안전합니다." })
  };
}

function emailOk(e){ return typeof e === "string" && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e); }

// 이메일 인증 메일 — 가입 직후/재발송. 이메일 열거·스팸 방지를 위해
// 사용자가 없거나 이미 인증된 경우엔 조용히 성공 처리(메일 미발송).
exports.sendVerifyEmail = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    const email = ((req.data && req.data.email) || (req.auth && req.auth.token && req.auth.token.email) || "").trim().toLowerCase();
    const lang = (req.data && req.data.lang) === "en" ? "en" : "ko";
    if(!emailOk(email)) throw new HttpsError("invalid-argument", "유효한 이메일이 필요합니다.");
    let user;
    try{ user = await admin.auth().getUserByEmail(email); }
    catch(e){ return { ok: true }; }            // 없는 사용자 → 열거 방지
    if(user.emailVerified) return { ok: true };  // 이미 인증됨 → 미발송
    const link = customActionLink(await admin.auth().generateEmailVerificationLink(email, ACTION_SETTINGS), lang);
    const mail = verifyMail(user.displayName, link, lang);
    const resend = new Resend(RESEND_API_KEY.value());
    const { error } = await resend.emails.send({ from: MAIL_FROM, to: email, subject: mail.subject, html: mail.html });
    if(error){ console.error("[sendVerifyEmail] resend:", error); throw new HttpsError("internal", "메일 발송에 실패했습니다."); }
    return { ok: true };
  }
);

// 비밀번호 재설정 메일 — 비로그인 상태에서 호출. 없는 사용자는 조용히 성공.
exports.sendResetEmail = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    const email = ((req.data && req.data.email) || "").trim().toLowerCase();
    const lang = (req.data && req.data.lang) === "en" ? "en" : "ko";
    if(!emailOk(email)) throw new HttpsError("invalid-argument", "유효한 이메일이 필요합니다.");
    let link;
    try{ link = customActionLink(await admin.auth().generatePasswordResetLink(email, ACTION_SETTINGS), lang); }
    catch(e){
      if(e.code === "auth/user-not-found" || e.code === "auth/email-not-found") return { ok: true };
      console.error("[sendResetEmail] link:", e);
      throw new HttpsError("internal", "요청 처리에 실패했습니다.");
    }
    const mail = resetMail(link, lang);
    const resend = new Resend(RESEND_API_KEY.value());
    const { error } = await resend.emails.send({ from: MAIL_FROM, to: email, subject: mail.subject, html: mail.html });
    if(error){ console.error("[sendResetEmail] resend:", error); throw new HttpsError("internal", "메일 발송에 실패했습니다."); }
    return { ok: true };
  }
);

/* ============================================================
   문의·피드백 폼 → hello@kosai.kr 로 이메일 전송
   ------------------------------------------------------------
   공개(비로그인) 호출. 봇 방지: 허니팟(hp) + 길이 제한.
   답장하면 보낸 사람에게 회신되도록 replyTo 설정.
   ============================================================ */
const FORM_TO = "hello@kosai.kr";

exports.submitForm = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    const d = req.data || {};
    if (d.hp) return { ok: true };                       // 허니팟에 값 → 봇, 조용히 성공
    const kind = d.kind === "feedback" ? "feedback" : "contact";
    const message = String(d.message || "").trim().slice(0, 5000);
    if (message.length < 2) throw new HttpsError("invalid-argument", "내용을 입력해 주세요.");
    const name = String(d.name || "").trim().slice(0, 80);
    const email = String(d.email || "").trim().slice(0, 120);
    const category = String(d.category || "").trim().slice(0, 40);
    const rating = String(d.rating || "").trim().slice(0, 24);
    const page = String(d.page || "").trim().slice(0, 200);

    const isFb = kind === "feedback";
    const label = isFb ? "피드백" : "문의";
    const who = name || (emailOk(email) ? email : "익명");
    const subject = `[${label}]${category ? " " + category : ""}${isFb && rating ? " · " + rating : ""} — ${who}`;

    const rows = [];
    if (!isFb && name) rows.push(["이름", name]);
    if (email) rows.push(["이메일", email]);
    if (category) rows.push([isFb ? "유형" : "문의 유형", category]);
    if (isFb && rating) rows.push(["만족도", rating]);
    if (page) rows.push(["페이지", page]);
    const rowsHtml = rows.map(([k, v]) =>
      `<tr><td style="padding:5px 14px 5px 0;color:#8a8c97;font:600 13px ${FONT};white-space:nowrap;vertical-align:top">${esc(k)}</td><td style="padding:5px 0;color:#1c1e26;font:400 14px ${FONT}">${esc(v)}</td></tr>`
    ).join("");

    const html = `<!doctype html><html lang="ko"><body style="margin:0;background:#f2f3fa;padding:28px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fff;border-radius:14px;border:1px solid #e7e9f2">
    <tr><td style="padding:24px 28px 0"><div style="font:700 12px ${FONT};letter-spacing:.08em;color:#0d69d4">KOSAI · 새 ${esc(label)}</div></td></tr>
    <tr><td style="padding:14px 28px 0"><table role="presentation" cellpadding="0" cellspacing="0">${rowsHtml}</table></td></tr>
    <tr><td style="padding:16px 28px 0"><div style="border-top:1px solid #eceef5;padding-top:14px;color:#1c1e26;font:400 15px/1.65 ${FONT};white-space:pre-wrap">${esc(message)}</div></td></tr>
    <tr><td style="padding:18px 28px 24px"><div style="color:#a7a9b4;font:400 12px ${FONT}">${emailOk(email) ? "이 메일에 그대로 답장하면 보낸 사람에게 회신됩니다." : "보낸 사람이 이메일을 남기지 않았습니다."}</div></td></tr>
  </table>
</td></tr></table></body></html>`;

    const resend = new Resend(RESEND_API_KEY.value());
    const opts = { from: MAIL_FROM, to: FORM_TO, subject, html };
    if (emailOk(email)) opts.replyTo = email;
    const { error } = await resend.emails.send(opts);
    if (error) { console.error("[submitForm] resend:", error); throw new HttpsError("internal", "전송에 실패했습니다."); }
    return { ok: true };
  }
);

/* ============================================================
   유료 리포트 전달 — getReport
   ------------------------------------------------------------
   무료 구간은 정적 파일(data/reports_v2/{ticker}.json)로 공개되고,
   유료 구간은 Firestore(reports_paid/{ticker})에만 두어 이 함수를 통해서만
   나간다. 구독이 확인된 사용자에게만 응답한다.

   전제(파이프라인이 만들어 줌):
     reports_paid/{ticker}   — 유료 섹션(earnings·bull·bear·verdict 등)
     subscriptions/{uid}     — { status, plan, currentPeriodEnd }
                               status: active | canceled | expired
                               plan  : basic | pro

   열람 한도는 요금제로 갈린다. pricing.html에 고지한 수치와 반드시 같아야 한다.
   ============================================================ */
const DAILY_LIMIT = { basic: 5, pro: 15 };   // 1일 '서로 다른 종목' 열람 수

function subActive(sub) {
  if (!sub || sub.status !== "active") return false;
  const end = sub.currentPeriodEnd;
  if (!end) return false;
  const ms = typeof end.toMillis === "function" ? end.toMillis()
           : typeof end === "number" ? end : Date.parse(end);
  return Number.isFinite(ms) && ms > Date.now();
}

// 한국 시간 기준 날짜. UTC로 끊으면 한도가 오전 9시(장 시작)에 초기화된다.
function kstDay() {
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

/* 하루 열람 한도 차감. 한도 안이면 true.

   같은 종목을 다시 열 때는 차감하지 않는다. 새로고침·뒤로가기·다른 기기에서
   다시 보기가 전부 한 건씩 깎으면, 사용자는 서로 다른 두 종목만 보고도
   '한도 초과'를 만나게 된다. 그래서 횟수가 아니라 '오늘 본 종목'을 센다. */
async function consumeDailyRead(db, uid, ticker, limit) {
  const day = kstDay();
  const ref = db.doc(`report_reads/${uid}_${day}`);
  return db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const seen = (snap.exists && snap.data().tickers) || [];
    if (seen.includes(ticker)) return true;        // 오늘 이미 본 종목 — 추가 차감 없음
    if (seen.length >= limit) return false;
    tx.set(ref, {
      tickers: admin.firestore.FieldValue.arrayUnion(ticker),
      count: seen.length + 1,
      day,
      uid,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return true;
  });
}

exports.getReport = onCall(
  { region: REGION, cors: true },
  async (req) => {
    const ticker = String((req.data && req.data.ticker) || "").trim().toUpperCase();
    if (!/^[0-9A-Z]{6}$/.test(ticker)) {
      throw new HttpsError("invalid-argument", "종목코드가 올바르지 않습니다.");
    }
    const uid = req.auth && req.auth.uid;
    if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");

    const db = admin.firestore();

    const subSnap = await db.doc(`subscriptions/${uid}`).get();
    const sub = subSnap.exists ? subSnap.data() : null;
    if (!subActive(sub)) {
      // 결제/체험이 없거나 만료 — 프런트는 이 코드를 받아 잠금 UI를 띄운다.
      throw new HttpsError("permission-denied", "멤버십이 필요합니다.");
    }

    const plan = String(sub.plan || "").toLowerCase();
    const limit = DAILY_LIMIT[plan];
    if (!limit) {
      console.error(`[getReport] 알 수 없는 요금제 plan=${sub.plan} uid=${uid}`);
      throw new HttpsError("failed-precondition", "요금제 정보를 확인할 수 없습니다.");
    }

    // 리포트가 없으면 한도를 깎지 않는다 — 없는 종목을 눌러 한도를 잃으면 안 된다.
    const snap = await db.doc(`reports_paid/${ticker}`).get();
    if (!snap.exists) throw new HttpsError("not-found", "리포트를 찾을 수 없습니다.");

    if (!(await consumeDailyRead(db, uid, ticker, limit))) {
      console.warn(`[getReport] 일일 한도(${plan}=${limit}) 초과 uid=${uid}`);
      throw new HttpsError("resource-exhausted", "오늘 열람 한도를 모두 사용했습니다.");
    }

    return { ticker, paid: snap.data(), plan, limit };
  }
);

/* ============================================================
   구독 결제 — 토스페이먼츠 정기결제(빌링)
   ------------------------------------------------------------
   비밀키는 Secret Manager 로만 넣는다:
     firebase functions:secrets:set TOSS_SECRET_KEY

   Firestore
     subscriptions/{uid}      { status, plan, currentPeriodStart, currentPeriodEnd,
                                cancelAtPeriodEnd, pendingPlan, billingKey, customerKey,
                                card:{company,number}, startedAt, updatedAt }
     payments/{uid}/items/{id}{ amount, description, status, paymentKey, orderId,
                                plan, paidAt, createdAt }

   ⚠️ 금액은 서버 표(PRICE)에서만 읽는다. 클라이언트가 보낸 금액은 쓰지 않는다.
   ⚠️ 구독 문서는 서버만 쓴다(firestore.rules 에서 클라이언트 쓰기 금지).
   ============================================================ */
const { onSchedule } = require("firebase-functions/v2/scheduler");
const TOSS_SECRET_KEY = defineSecret("TOSS_SECRET_KEY");

const PRICE = { basic: 9900, pro: 14900 };        // pricing.html·payment-config.js 와 같아야 한다
const PLAN_NAME = { basic: "BASIC", pro: "PRO" };
const REFUND_FEE_RATE = 0.10;                     // 서비스 수수료 10% (요금제 페이지 고지)
const FREE_WITHDRAW_DAYS = 7;                     // 미열람 시 전액 환불 기간

const tossAuth = () =>
  "Basic " + Buffer.from((TOSS_SECRET_KEY.value() || "") + ":").toString("base64");

async function toss(path, body) {
  const res = await fetch("https://api.tosspayments.com/v1" + path, {
    method: "POST",
    headers: { Authorization: tossAuth(), "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const text = await res.text();
  let json; try { json = JSON.parse(text); } catch (e) { json = { raw: text }; }
  if (!res.ok) {
    console.error(`[toss] ${path} HTTP ${res.status}:`, text.slice(0, 500));
    // 카드사 거절 메시지는 사용자에게 그대로 보여주는 편이 낫다(한도 초과·정지 등).
    throw new HttpsError("failed-precondition", json.message || "결제에 실패했습니다.");
  }
  return json;
}

/** 한 달 뒤. 31일처럼 다음 달에 없는 날짜는 그 달의 마지막 날로 맞춘다. */
function addMonth(from) {
  const d = new Date(from);
  const day = d.getDate();
  d.setMonth(d.getMonth() + 1);
  if (d.getDate() !== day) d.setDate(0);
  return d;
}
const days = (ms) => ms / 86400000;
function planOrThrow(p) {
  const id = String(p || "").toLowerCase();
  if (!PRICE[id]) throw new HttpsError("invalid-argument", "요금제를 확인할 수 없습니다.");
  return id;
}
function uidOrThrow(req) {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  return uid;
}
const orderId = (uid, tag) =>
  `kosai_${tag}_${uid.slice(0, 12)}_${Date.now().toString(36)}`;

async function writePayment(db, uid, data) {
  await db.collection(`payments/${uid}/items`).add({
    ...data,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
  });
}

/** 빌링키로 즉시 결제. 성공하면 결제 내역을 남기고 payment 객체를 돌려준다. */
async function charge(db, uid, sub, amount, description, tag) {
  if (amount <= 0) return null;
  const pay = await toss(`/billing/${sub.billingKey}`, {
    customerKey: sub.customerKey,
    amount,
    orderId: orderId(uid, tag),
    orderName: description,
  });
  await writePayment(db, uid, {
    amount, description, status: "paid", plan: sub.plan,
    paymentKey: pay.paymentKey, orderId: pay.orderId,
    paidAt: pay.approvedAt || new Date().toISOString(),
  });
  return pay;
}

/* ── 1) 카드 등록 + 첫 결제 ───────────────────────────────── */
exports.confirmBilling = onCall(
  { region: REGION, cors: true, secrets: [TOSS_SECRET_KEY] },
  async (req) => {
    const uid = uidOrThrow(req);
    const plan = planOrThrow(req.data && req.data.plan);
    const authKey = String((req.data && req.data.authKey) || "").trim();
    const customerKey = String((req.data && req.data.customerKey) || "").trim();
    if (!authKey || customerKey !== uid) {
      // customerKey 는 uid 여야 한다 — 남의 카드로 내 구독을 만들 수 없게.
      throw new HttpsError("invalid-argument", "결제 정보가 올바르지 않습니다.");
    }

    const db = admin.firestore();
    const ref = db.doc(`subscriptions/${uid}`);
    const cur = (await ref.get()).data() || null;
    if (subActive(cur) && !cur.cancelAtPeriodEnd) {
      throw new HttpsError("already-exists", "이미 이용 중인 구독이 있습니다.");
    }

    const issued = await toss("/billing/authorizations/issue", { authKey, customerKey });
    const now = new Date();
    const sub = {
      billingKey: issued.billingKey, customerKey, plan,
      card: { company: (issued.card && issued.card.issuerCode) || "", number: (issued.card && issued.card.number) || "" },
    };
    const pay = await charge(db, uid, sub, PRICE[plan], `${PLAN_NAME[plan]} 월 구독`, "new");

    await ref.set({
      ...sub,
      status: "active",
      currentPeriodStart: admin.firestore.Timestamp.fromDate(now),
      currentPeriodEnd: admin.firestore.Timestamp.fromDate(addMonth(now)),
      cancelAtPeriodEnd: false,
      pendingPlan: null,
      readsAtStart: 0,
      startedAt: (cur && cur.startedAt) || admin.firestore.Timestamp.fromDate(now),
      lastPaymentKey: pay ? pay.paymentKey : null,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });

    return { ok: true, plan };
  }
);

/* ── 2) 플랜 변경 ─────────────────────────────────────────────
   업그레이드는 즉시 적용하고 남은 기간만큼 차감해 차액만 받는다(결제일 유지).
   다운그레이드는 다음 결제일부터 — 즉시 내리면 환불이 생기고, 남은 기간
   PRO 를 이미 쓴 사람에게 돈을 돌려주는 구조가 된다.
   ─────────────────────────────────────────────────────────── */
exports.changePlan = onCall(
  { region: REGION, cors: true, secrets: [TOSS_SECRET_KEY] },
  async (req) => {
    const uid = uidOrThrow(req);
    const next = planOrThrow(req.data && req.data.plan);
    const db = admin.firestore();
    const ref = db.doc(`subscriptions/${uid}`);
    const sub = (await ref.get()).data();
    if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
    if (sub.plan === next && !sub.pendingPlan) {
      throw new HttpsError("already-exists", "이미 해당 플랜을 이용 중입니다.");
    }

    if (PRICE[next] > PRICE[sub.plan]) {
      const endMs = sub.currentPeriodEnd.toMillis();
      const startMs = sub.currentPeriodStart ? sub.currentPeriodStart.toMillis() : endMs - 30 * 86400000;
      const total = Math.max(1, days(endMs - startMs));
      const left = Math.max(0, days(endMs - Date.now()));
      // 남은 기간에 해당하는 두 요금의 차액. 원 단위 절사(사용자에게 유리하게).
      const diff = Math.floor((PRICE[next] - PRICE[sub.plan]) * (left / total));
      await charge(db, uid, sub, diff, `${PLAN_NAME[next]} 업그레이드 차액`, "up");
      await ref.set({
        plan: next, pendingPlan: null,
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });
      return { ok: true, plan: next, charged: diff };
    }

    await ref.set({
      pendingPlan: next,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true, pendingPlan: next };
  }
);

/* ── 3) 해지 / 해지 취소 ─────────────────────────────────────
   해지는 '지금 끊기'가 아니라 '갱신 안 함'이다. 이미 결제한 기간은 그대로 쓴다.
   ─────────────────────────────────────────────────────────── */
exports.cancelSubscription = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const ref = admin.firestore().doc(`subscriptions/${uid}`);
  const sub = (await ref.get()).data();
  if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
  await ref.set({
    cancelAtPeriodEnd: true, canceledAt: admin.firestore.FieldValue.serverTimestamp(),
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });
  return { ok: true };
});

exports.resumeSubscription = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const ref = admin.firestore().doc(`subscriptions/${uid}`);
  const sub = (await ref.get()).data();
  if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
  await ref.set({
    cancelAtPeriodEnd: false, canceledAt: null,
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });
  return { ok: true };
});

/* ── 4) 환불 ─────────────────────────────────────────────────
   요금제 페이지에 고지한 기준 그대로 계산한다. 문구와 계산이 어긋나면
   그건 그냥 거짓말이 된다.
     · 리포트 미열람 + 7일 이내  → 전액
     · 리포트 미열람 + 7일 경과  → 잔여 기간분 − 수수료 10%
     · 리포트 열람              → 이용 일수 차감 후 − 수수료 10%
   ─────────────────────────────────────────────────────────── */
exports.requestRefund = onCall(
  { region: REGION, cors: true, secrets: [TOSS_SECRET_KEY] },
  async (req) => {
    const uid = uidOrThrow(req);
    const db = admin.firestore();
    const ref = db.doc(`subscriptions/${uid}`);
    const sub = (await ref.get()).data();
    if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
    if (!sub.lastPaymentKey) throw new HttpsError("failed-precondition", "환불할 결제 건이 없습니다.");

    const startMs = sub.currentPeriodStart.toMillis();
    const endMs = sub.currentPeriodEnd.toMillis();
    const total = Math.max(1, days(endMs - startMs));
    const used = Math.min(total, Math.max(0, days(Date.now() - startMs)));
    const price = PRICE[sub.plan] || 0;

    // 이번 결제 기간에 리포트를 한 건이라도 열었는가
    const reads = await db.collection("report_reads")
      .where("uid", "==", uid)
      .where("updatedAt", ">=", sub.currentPeriodStart)
      .limit(1).get();
    const opened = !reads.empty;

    let amount, reason;
    if (!opened && used <= FREE_WITHDRAW_DAYS) {
      amount = price;
      reason = "청약철회(7일 이내·미열람)";
    } else {
      const leftRatio = Math.max(0, (total - used) / total);
      amount = Math.floor(price * leftRatio * (1 - REFUND_FEE_RATE));
      reason = opened ? "이용분 차감 환불" : "잔여 기간 환불";
    }
    if (amount <= 0) throw new HttpsError("failed-precondition", "환불 가능한 금액이 없습니다.");

    await toss(`/payments/${sub.lastPaymentKey}/cancel`, {
      cancelReason: reason, cancelAmount: amount,
    });
    await writePayment(db, uid, {
      amount: -amount, description: `환불 · ${reason}`, status: "refunded",
      plan: sub.plan, paymentKey: sub.lastPaymentKey, paidAt: new Date().toISOString(),
    });
    // 환불이 끝나면 이용 권한은 즉시 종료된다(요금제 페이지 고지와 동일).
    await ref.set({
      status: "refunded", cancelAtPeriodEnd: true,
      currentPeriodEnd: admin.firestore.Timestamp.fromDate(new Date()),
      refundedAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });

    return { ok: true, amount };
  }
);

/* ── 5) 정기결제 갱신 ────────────────────────────────────────
   매일 한 번 돌며 기간이 끝난 구독을 갱신한다. 크론은 UTC 로만 해석되므로
   02:00 UTC(= 같은 날 11:00 KST)로 적는다. 15시 이후로 잡으면 한국 날짜가 밀린다.
   ─────────────────────────────────────────────────────────── */
exports.renewSubscriptions = onSchedule(
  { region: REGION, schedule: "0 2 * * *", timeZone: "Etc/UTC", secrets: [TOSS_SECRET_KEY] },
  async () => {
    const db = admin.firestore();
    const now = new Date();
    const due = await db.collection("subscriptions")
      .where("status", "==", "active")
      .where("currentPeriodEnd", "<=", admin.firestore.Timestamp.fromDate(now))
      .limit(400).get();
    console.log(`[renew] 대상 ${due.size}건`);

    for (const d of due.docs) {
      const uid = d.id, sub = d.data();
      try {
        if (sub.cancelAtPeriodEnd) {
          await d.ref.set({ status: "expired", updatedAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
          continue;
        }
        const plan = sub.pendingPlan || sub.plan;   // 예약된 다운그레이드를 여기서 적용
        const pay = await charge(db, uid, { ...sub, plan }, PRICE[plan],
          `${PLAN_NAME[plan]} 월 구독`, "renew");
        await d.ref.set({
          plan, pendingPlan: null, status: "active",
          currentPeriodStart: admin.firestore.Timestamp.fromDate(now),
          currentPeriodEnd: admin.firestore.Timestamp.fromDate(addMonth(now)),
          lastPaymentKey: pay ? pay.paymentKey : sub.lastPaymentKey,
          failedAt: null,
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        }, { merge: true });
      } catch (e) {
        // 한도 초과·정지 카드 등. 바로 끊지 않고 상태만 남긴다 — 사용자가 카드를
        // 바꿀 시간을 줘야 한다. 이용 권한은 currentPeriodEnd 가 지나 자연히 닫힌다.
        console.error(`[renew] 실패 uid=${uid}`, e && e.message);
        await d.ref.set({
          status: "past_due", failedAt: admin.firestore.FieldValue.serverTimestamp(),
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        }, { merge: true });
        await writePayment(db, uid, {
          amount: PRICE[sub.plan] || 0, description: "정기결제 실패",
          status: "failed", plan: sub.plan, paidAt: null,
        });
      }
    }
  }
);
