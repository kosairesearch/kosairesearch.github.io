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
function customActionLink(rawLink){
  try{ const u = new URL(rawLink); const t = new URL(ACTION_PAGE); t.search = u.search; return t.toString(); }
  catch(e){ return rawLink; }
}

function esc(s){ return String(s || "").replace(/[&<>"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c])); }

function mailLayout({ heading, intro, btnText, link, outro }){
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f2f3fa;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f3fa;padding:32px 12px;">
<tr><td align="center">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px;background:#ffffff;border-radius:16px;border:1px solid #e7e9f2;">
    <tr><td style="padding:28px 32px 0;">
      <img src="${SITE_URL}/assets/kosai-wordmark-black.png" alt="KOSAI" width="150" height="24" style="display:block;border:0;outline:none;text-decoration:none;height:24px;width:150px;">
    </td></tr>
    <tr><td style="padding:18px 32px 0;">
      <h1 style="margin:0;font:700 20px/1.4 ${FONT};color:#0d0d12;letter-spacing:-.01em;">${esc(heading)}</h1>
      <p style="margin:14px 0 0;font:400 15px/1.65 ${FONT};color:#41434d;">${intro}</p>
    </td></tr>
    <tr><td style="padding:22px 32px 0;">
      <a href="${esc(link)}" style="display:inline-block;background:#0d69d4;color:#ffffff;text-decoration:none;font:600 15px/1 ${FONT};padding:14px 28px;border-radius:10px;">${esc(btnText)}</a>
    </td></tr>
    <tr><td style="padding:18px 32px 0;">
      <p style="margin:0;font:400 13px/1.6 ${FONT};color:#8a8c97;">${outro}</p>
      <p style="margin:12px 0 0;font:400 12px/1.5 ${FONT};color:#a7a9b4;">버튼이 안 눌리면 아래 주소를 복사해 브라우저에 붙여넣으세요.<br><span style="word-break:break-all;color:#7a8aa0;">${esc(link)}</span></p>
    </td></tr>
    <tr><td style="padding:22px 32px 28px;">
      <hr style="border:none;border-top:1px solid #eceef5;margin:0 0 16px;">
      <p style="margin:0;font:400 12px/1.65 ${FONT};color:#a7a9b4;">KOSAI · 한국 상장사 AI 리서치<br>문의 <a href="mailto:hello@kosai.kr" style="color:#8a8c97;text-decoration:none;">hello@kosai.kr</a> · <a href="${SITE_URL}" style="color:#8a8c97;text-decoration:none;">kosai.kr</a></p>
    </td></tr>
  </table>
  <p style="max-width:480px;margin:14px auto 0;font:400 11px/1.5 ${FONT};color:#b3b5bf;">본 메일은 KOSAI 계정 활동에 따라 자동 발송되었습니다.</p>
</td></tr>
</table></body></html>`;
}

function verifyMail(name, link){
  const hi = name ? `${esc(name)}님, ` : "";
  return mailLayout({
    heading: "이메일 주소를 인증해 주세요",
    intro: `${hi}KOSAI 가입을 환영합니다. 아래 버튼을 눌러 이메일 인증을 완료하면 모든 기능을 이용하실 수 있어요.`,
    btnText: "이메일 인증하기",
    link,
    outro: "본인이 가입하지 않았다면 이 메일을 무시하셔도 됩니다."
  });
}
function resetMail(link){
  return mailLayout({
    heading: "비밀번호를 재설정하세요",
    intro: "비밀번호 재설정 요청을 받았습니다. 아래 버튼을 눌러 새 비밀번호를 설정해 주세요.",
    btnText: "비밀번호 재설정하기",
    link,
    outro: "본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다. 비밀번호는 변경되지 않으며 계정은 안전합니다."
  });
}

function emailOk(e){ return typeof e === "string" && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e); }

// 이메일 인증 메일 — 가입 직후/재발송. 이메일 열거·스팸 방지를 위해
// 사용자가 없거나 이미 인증된 경우엔 조용히 성공 처리(메일 미발송).
exports.sendVerifyEmail = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    const email = ((req.data && req.data.email) || (req.auth && req.auth.token && req.auth.token.email) || "").trim().toLowerCase();
    if(!emailOk(email)) throw new HttpsError("invalid-argument", "유효한 이메일이 필요합니다.");
    let user;
    try{ user = await admin.auth().getUserByEmail(email); }
    catch(e){ return { ok: true }; }            // 없는 사용자 → 열거 방지
    if(user.emailVerified) return { ok: true };  // 이미 인증됨 → 미발송
    const link = customActionLink(await admin.auth().generateEmailVerificationLink(email, ACTION_SETTINGS));
    const resend = new Resend(RESEND_API_KEY.value());
    const { error } = await resend.emails.send({
      from: MAIL_FROM, to: email,
      subject: "KOSAI 이메일 주소를 인증해 주세요",
      html: verifyMail(user.displayName, link)
    });
    if(error){ console.error("[sendVerifyEmail] resend:", error); throw new HttpsError("internal", "메일 발송에 실패했습니다."); }
    return { ok: true };
  }
);

// 비밀번호 재설정 메일 — 비로그인 상태에서 호출. 없는 사용자는 조용히 성공.
exports.sendResetEmail = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    const email = ((req.data && req.data.email) || "").trim().toLowerCase();
    if(!emailOk(email)) throw new HttpsError("invalid-argument", "유효한 이메일이 필요합니다.");
    let link;
    try{ link = customActionLink(await admin.auth().generatePasswordResetLink(email, ACTION_SETTINGS)); }
    catch(e){
      if(e.code === "auth/user-not-found" || e.code === "auth/email-not-found") return { ok: true };
      console.error("[sendResetEmail] link:", e);
      throw new HttpsError("internal", "요청 처리에 실패했습니다.");
    }
    const resend = new Resend(RESEND_API_KEY.value());
    const { error } = await resend.emails.send({
      from: MAIL_FROM, to: email,
      subject: "KOSAI 비밀번호 재설정 안내",
      html: resetMail(link)
    });
    if(error){ console.error("[sendResetEmail] resend:", error); throw new HttpsError("internal", "메일 발송에 실패했습니다."); }
    return { ok: true };
  }
);
