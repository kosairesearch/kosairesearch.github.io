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

/* 동의서 판 번호. consent.js 의 CONSENT_VERSION 과 같아야 한다.
   한쪽만 올리면 같은 날 가입한 사람이 서로 다른 판으로 기록된다. */
const CONSENT_VERSION = "2026-08-20";

const KAKAO_REST_KEY = defineSecret("KAKAO_REST_KEY");
const KAKAO_CLIENT_SECRET = defineSecret("KAKAO_CLIENT_SECRET"); // 카카오에서 사용 안 하면 빈 값
const NAVER_CLIENT_ID = defineSecret("NAVER_CLIENT_ID");
const NAVER_CLIENT_SECRET = defineSecret("NAVER_CLIENT_SECRET");
const RESEND_API_KEY = defineSecret("RESEND_API_KEY"); // 이메일 발송(Resend)
/* 탈퇴할 때 카카오 연결을 끊는 데 쓴다(어드민 키). 탈퇴 시점에는 사용자
   토큰이 없어서 이 키가 아니면 끊을 방법이 없다.

   값이 없어도 배포는 되어야 한다. 선언된 시크릿에 값이 없으면 배포가
   통째로 막히기 때문이다(TOSS_SECRET_KEY 로 겪었다). 그래서 배포
   워크플로가 값이 없으면 자리만 채워 두고, 아래 kakaoUnlink 가 그 값을
   '미설정' 으로 알아보고 건너뛴다. */
const KAKAO_ADMIN_KEY = defineSecret("KAKAO_ADMIN_KEY");
const SECRET_UNSET = "미설정";
/* ── 결제 스위치 ─────────────────────────────────────────────
   실사이트에는 아직 결제를 올리지 않는다. 배포 목록에서 빼는 것만으로는
   부족했다. 파이어베이스 CLI 는 --only 로 고른 함수만 올리더라도 코드
   전체를 훑어 '누군가 쓰는 시크릿' 을 먼저 확인한다. 그래서 결제 함수가
   TOSS_SECRET_KEY 를 달고 있는 한, 등록된 적 없는 그 키 하나 때문에
   로그인·탈퇴 같은 결제와 무관한 함수까지 전부 배포가 막혔다.

   그래서 스위치가 꺼져 있으면 결제 함수를 아예 만들지 않는다. 시크릿을
   선언하지도 않으니 확인할 것도 없다. renewSubscriptions 가 onSchedule 인
   것도 있다 — 한 번 올라가면 부르는 화면이 없어도 매일 새벽에 혼자 돌면서
   카드에 결제를 건다. 목록에서 빼는 것보다 만들지 않는 쪽이 확실하다.

   켜는 법 (결제를 실제로 시작하는 날):
     1) firebase functions:secrets:set TOSS_SECRET_KEY
     2) 배포 워크플로 env 에 KOSAI_PAYMENTS=on
     3) --only 목록에 결제 함수 추가                                 */
const PAYMENTS_LIVE = process.env.KOSAI_PAYMENTS === "on";
const TOSS_SECRET_KEY = PAYMENTS_LIVE ? defineSecret("TOSS_SECRET_KEY") : null;

/* ── 되돌아올 주소는 서버가 검사한다 ──────────────────────────────
   전에는 클라이언트가 보낸 redirectUri 를 그대로 카카오·네이버 토큰 교환에
   넘겼다. 두 곳 모두 콘솔에 등록된 주소만 받아 주므로 당장 뚫리지는
   않았지만, 서버가 클라이언트 말을 검사 없이 믿는 자리는 남겨 둘 이유가
   없다. 우리 도메인이 아니면 여기서 끊는다. */
const ALLOWED_REDIRECT_HOSTS = [
  "kosai.kr", "www.kosai.kr", "kosairesearch.github.io", "localhost", "127.0.0.1"
];

function checkRedirectUri(uri){
  let u;
  try{ u = new URL(String(uri)); }
  catch(_){ throw new HttpsError("invalid-argument", "redirect_uri_invalid"); }
  const local = u.hostname === "localhost" || u.hostname === "127.0.0.1";
  if(u.protocol !== "https:" && !local)
    throw new HttpsError("invalid-argument", "redirect_uri_not_https");
  if(!ALLOWED_REDIRECT_HOSTS.includes(u.hostname))
    throw new HttpsError("invalid-argument", "redirect_uri_host_not_allowed");
  return u.origin + u.pathname;   // 쿼리·해시는 떼고 쓴다
}

async function asJson(res, label){
  const text = await res.text();
  let json;
  try{ json = JSON.parse(text); }catch(e){ json = { raw: text }; }
  if(!res.ok){ console.error(`[${label}] HTTP ${res.status}:`, text.slice(0, 500)); throw new HttpsError("unauthenticated", `${label}_http_${res.status}: ${text.slice(0, 300)}`); }
  return json;
}

/* 카카오싱크 간편가입에서 받은 약관 동의 내역.

   카카오 동의 화면이 곧 우리 동의 화면이다 — 개발자센터에 등록한 우리
   이용약관·개인정보 수집·이용·만 14세·마케팅 수신을 카카오가 대신 받아
   준다. 그런데 우리는 그 결과를 읽지 않고 age14/terms/privacy 를 true 로,
   marketing 을 false 로 박아 두고 있었다. 그래서 마케팅에 동의한 사람이
   우리 기록에는 전부 미동의로 남았다.

   읽어 온다. 실패해도 로그인을 막지 않는다 — 동의 내역을 못 가져온 것과
   사용자가 동의하지 않은 것은 다른 일이고, 여기서 던지면 멀쩡한 로그인이
   끊긴다. 못 가져오면 null 이고, 부르는 쪽이 기존 기록을 건드리지 않는다. */
async function kakaoServiceTerms(accessToken){
  try{
    const r = await asJson(await fetch("https://kapi.kakao.com/v2/user/service_terms", {
      headers: { Authorization: `Bearer ${accessToken}` }
    }), "kakao_service_terms");
    const list = Array.isArray(r.service_terms) ? r.service_terms : null;
    if(!list) return null;
    /* 어떤 tag 가 오는지 로그에 남긴다. tag 는 개발자센터에서 우리가 정한
       값이라 코드가 미리 알 수 없다 — 아래 매핑이 틀리면 이 줄로 안다. */
    console.log("[kakao] service_terms:",
      list.map(t => `${t.tag}${t.required ? "(필수)" : "(선택)"}=${t.agreed}`).join(", "));
    return list;
  }catch(e){
    console.warn("[kakao] service_terms 조회 실패:", e && e.message);
    return null;
  }
}

/* 카카오가 준 약관 목록을 우리 항목으로 옮긴다.

   tag 는 개발자센터에서 우리가 정한 문자열이라 코드가 미리 알 수 없다.
   그래서 두 겹으로 짚는다.

     ① tag 이름으로 짚는다 (아래 표. 실제 tag 를 알면 여기에 그대로 적으면
        된다 — 로그의 '[kakao] service_terms:' 줄에 찍힌다)
     ② 못 짚으면 required 플래그로 물러선다. 필수 약관은 동의해야 가입이
        진행되므로, 필수가 전부 동의됐으면 필수 세 항목은 true 다

   마케팅은 물러설 곳이 없다. 선택 항목이라 '동의했겠거니' 할 수 없다 —
   짚지 못하면 false 로 두고 경고를 남긴다. 없는 동의를 만들어 내는 것보다
   못 읽었다고 말하는 편이 낫다.

   원본은 그대로 저장한다. 매핑이 틀려도 자료는 남아 나중에 고칠 수 있다. */
const KAKAO_TAG_MATCH = {
  age14:     /(^|[^a-z])age|14|연령|만14/i,
  terms:     /^service$|term|약관|이용/i,
  privacy:   /privacy|개인정보|수집/i,
  marketing: /market|adver|광고|수신|promo|benefit|혜택/i,
};

function mapKakaoTerms(list){
  if(!Array.isArray(list) || !list.length) return null;

  const hit = (key) => list.find(t => KAKAO_TAG_MATCH[key].test(String(t.tag || "")));
  const req = list.filter(t => t.required);
  const allRequiredAgreed = req.length > 0 && req.every(t => t.agreed === true);

  const pick = (key) => {
    const t = hit(key);
    if(t) return t.agreed === true;
    return allRequiredAgreed;          // 못 짚으면 필수 동의 여부로 물러선다
  };

  const mk = hit("marketing");
  if(!mk){
    console.warn("[kakao] 마케팅 약관 tag 를 찾지 못했다. 받은 tag:",
      list.map(t => t.tag).join(", "), "— KAKAO_TAG_MATCH 를 확인할 것.");
  }

  /* 실제 동의 시각. 우리 서버 시각보다 이쪽이 맞다 — 사용자가 누른 시각이다.
     여럿이면 가장 늦은 것을 쓴다(마지막으로 동의를 마친 순간). */
  let agreedAt = null;
  for(const t of list){
    if(t.agreed !== true || !t.agreed_at) continue;
    const ms = Date.parse(t.agreed_at);
    if(ms && (!agreedAt || ms > agreedAt)) agreedAt = ms;
  }

  return {
    age14: pick("age14"),
    terms: pick("terms"),
    privacy: pick("privacy"),
    marketing: mk ? mk.agreed === true : false,
    marketingKnown: !!mk,
    agreedAt: agreedAt ? new Date(agreedAt) : null,
    raw: list.map(t => ({
      tag: String(t.tag || ""),
      required: t.required === true,
      agreed: t.agreed === true,
      agreedAt: t.agreed_at || null,
    })),
  };
}

/* 제공자가 알려 준 동의를 그대로 믿어도 되는가.

     withdrawnAt  마지막 탈퇴 시각(ms). 0 이면 탈퇴한 적 없음,
                  -1 이면 조회에 실패해 모름
     agreedAt     제공자가 알려 준 동의 시각(ms). 0 이면 모름

   탈퇴한 적이 없으면 그냥 믿는다. 탈퇴한 적이 있으면 그 뒤에 다시 받은
   동의여야 한다. 둘 중 하나라도 모르면 다시 받는다 — 동의를 한 번 더
   받는 것은 번거로울 뿐이지만, 받지 않은 동의를 받았다고 적는 것은
   되돌릴 수 없다. */
function isStaleProviderConsent(withdrawnAt, agreedAt){
  if(withdrawnAt === 0) return false;            // 탈퇴한 적 없음
  if(withdrawnAt < 0) return true;               // 이력을 못 읽음
  if(!agreedAt) return true;                     // 동의 시각을 모름
  return agreedAt <= withdrawnAt;                // 탈퇴 이전 동의면 옛것
}

/* 탈퇴할 때 카카오 앱 연결을 끊는다.

   이걸 하지 않으면 탈퇴해도 카카오 '연결된 서비스' 목록에 KOSAI 가 남는다.
   사용자가 보면 탈퇴가 안 된 것처럼 보이고, 실제로 다시 로그인하면 카카오가
   이미 동의한 앱으로 보고 동의 화면을 건너뛴다 — 그러면 우리는 탈퇴 전에
   받은 옛 동의를 새 계정의 동의로 적게 된다. 카카오 문서도 회원 탈퇴 시
   연결 끊기를 요청하도록 안내한다.

   탈퇴 시점에는 사용자 토큰이 없다(로그인할 때만 받고 버린다). 그래서
   어드민 키로 끊는다.

   실패해도 탈퇴는 계속한다. 카카오 쪽이 안 끊겼다고 우리 쪽 탈퇴를 막으면
   사용자는 계정을 못 지운다 — 그게 더 나쁘다. 대신 실패를 기록에 남기고,
   그 사람이 다시 가입하면 isStaleProviderConsent 가 옛 동의를 걸러 낸다. */
async function kakaoUnlink(uid){
  const key = (KAKAO_ADMIN_KEY.value() || "").trim();
  if(!key || key === SECRET_UNSET){
    console.warn("[kakao] 어드민 키가 없어 연결 끊기를 건너뛴다:", uid);
    return false;
  }
  const id = String(uid).split(":")[1] || "";
  if(!id) return false;
  try{
    const res = await fetch("https://kapi.kakao.com/v1/user/unlink", {
      method: "POST",
      headers: {
        Authorization: `KakaoAK ${key}`,
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
      },
      body: new URLSearchParams({ target_id_type: "user_id", target_id: id })
    });
    const text = await res.text();
    if(!res.ok){
      console.error(`[kakao] 연결 끊기 실패 HTTP ${res.status}:`, text.slice(0, 300));
      return false;
    }
    console.log("[kakao] 연결 끊음:", uid);
    return true;
  }catch(e){
    console.error("[kakao] 연결 끊기 오류:", uid, e && e.message);
    return false;
  }
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
    photo: prof.profile_image_url || (me.properties && me.properties.profile_image) || null,
    terms: await kakaoServiceTerms(tok.access_token)
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

/* ── 같은 이메일을 이미 쓰는 다른 계정 찾기 ────────────────────────
   왜 필요한가. 카카오·네이버는 커스텀 토큰으로 로그인시키는데, 그때
   Firebase 사용자에는 이메일을 심지 않는다(계정 충돌을 피하려고 그렇게 했다).
   그 대가로 Firebase 의 '이메일당 계정 하나' 보호가 소셜 계정을 아예 보지
   못한다. 그래서 네이버로 가입한 사람이 같은 네이버 주소로 이메일 가입을
   또 할 수 있었다 — 같은 사람에게 계정이 둘 생긴다.

   계정이 둘이면 관심 종목이 갈리고, 같은 주소로 마케팅 메일이 두 번 가고,
   한쪽을 탈퇴해도 다른 쪽이 남는다.

   이메일은 users/{uid}.email 에만 있으므로 여기서 찾는다. 단일 필드 조회라
   색인을 따로 만들 필요가 없다. */
/* 어느 방법으로 가입했는지를 사람 말로. '이메일(으)로 가입된 이메일입니다'
   처럼 말이 겹치지 않도록 '가입'·'로그인' 을 붙여 둔다. 넷 다 받침이 있거나
   'ㄹ' 로 끝나 조사는 '으로' 하나로 통일된다. */
const METHOD_KO = {
  email: "이메일 가입", google: "구글 로그인",
  kakao: "카카오 로그인", naver: "네이버 로그인",
};

async function findOtherAccountByEmail(db, email, selfUid) {
  const mail = String(email || "").trim().toLowerCase();
  if (!mail) return null;
  const q = await db.collection("users").where("email", "==", mail).limit(5).get();
  for (const doc of q.docs) {
    if (doc.id === selfUid) continue;

    /* 문서가 있다고 계정이 있는 것은 아니다. 콘솔에서 Auth 사용자만 지우면
       users 문서는 그대로 남는다. 그 유령 기록을 그대로 믿으면 그 이메일
       주소가 영구히 막힌다 — 실제로 그렇게 걸렸다. 계정이 살아 있는지
       확인하고, 없으면 남은 문서를 치우고 넘어간다. */
    try {
      await admin.auth().getUser(doc.id);
    } catch (e) {
      if (e && e.code === "auth/user-not-found") {
        try { await doc.ref.delete(); } catch (_) {}
        console.log(`[dup] 유령 문서 정리 ${doc.id} (${mail})`);
        continue;
      }
      throw e;                       // 조회 자체가 실패하면 막지도 통과시키지도 않는다
    }

    const m = (doc.data() || {}).signupMethod || "";
    return { uid: doc.id, method: m, label: METHOD_KO[m] || m || "다른 방법" };
  }
  return null;
}


/* 로그인 화면이 "왜 안 되는지" 를 알려 주기 위한 조회.

   비밀번호가 틀린 것과, 애초에 비밀번호로 가입한 적이 없는 것은 다른
   일이다. 네이버로 가입한 사람에게 '이메일 또는 비밀번호가 올바르지
   않습니다' 만 보여 주면 영영 못 들어온다.

   계정 열거를 걱정할 자리이긴 하다. 다만 가입 폼이 이미 같은 사실을
   알려 준다(email-already-in-use). 여기서 새로 새는 것은 '어느 방법으로
   가입했는가' 뿐이고, 그것을 감추는 대가로 사용자를 가두는 편이 더 나쁘다.
   가입한 적이 없는 주소에는 아무것도 알려 주지 않는다. */
exports.signinHint = onCall({ region: REGION, cors: true }, async (req) => {
  const email = String(((req.data || {}).email) || "").trim().toLowerCase();
  if (!emailOk(email)) return { method: null };

  /* ① Firebase 사용자에 이메일이 심긴 계정.
        이메일 가입·구글은 항상 여기서 잡힌다. 카카오·네이버도 이제 심으므로
        새로 만들어지는 것은 여기서 잡힌다. */
  try {
    const user = await admin.auth().getUserByEmail(email);
    const uid = String(user.uid || "");
    if (uid.startsWith("kakao:")) return { method: "kakao" };
    if (uid.startsWith("naver:")) return { method: "naver" };
    const ids = (user.providerData || []).map(x => x.providerId);
    if (ids.includes("google.com")) return { method: "google" };
    if (ids.includes("password")) return { method: "email" };
    return { method: null };
  } catch (e) {
    if (!e || e.code !== "auth/user-not-found") return { method: null };
  }

  /* ② 이메일을 심기 전에 만들어진 옛 소셜 계정.
        Auth 에는 이메일이 없고 users/{uid}.email 에만 있다. 여기를 보지
        않으면 그런 계정은 영영 못 찾는다 — 실제로 그래서 안내가 안 나가고
        가입이 그대로 통과했다. findOtherAccountByEmail 이 계정이 살아
        있는지까지 확인하고 유령 문서는 치운다. */
  try {
    const other = await findOtherAccountByEmail(admin.firestore(), email, null);
    return { method: (other && other.method) || null };
  } catch (e) { return { method: null }; }
});

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

    const safeRedirect = checkRedirectUri(redirectUri);

    let p;
    if(provider === "kakao") p = await kakaoProfile(code, safeRedirect);
    else if(provider === "naver") p = await naverProfile(code, safeRedirect, state);
    else throw new HttpsError("invalid-argument", "알 수 없는 provider 입니다.");

    if(!p.id) throw new HttpsError("internal", "프로필 ID를 가져오지 못했습니다.");

    const uid = `${provider}:${p.id}`;
    const userProps = {};
    if(p.name) userProps.displayName = p.name;
    if(p.photo) userProps.photoURL = p.photo;

    /* 이메일을 Firebase 사용자에도 심는다.

       전에는 일부러 심지 않았다("계정 충돌이 무섭다"). 그 대가가 컸다 —
       Firebase 의 '이메일당 계정 하나' 보호가 소셜 계정을 아예 보지 못해,
       네이버로 가입한 사람이 같은 주소로 이메일 가입을 또 할 수 있었다.
       우리가 서버에서 뒤늦게 막으려니 동의 화면까지 간 다음에야 걸렸다.

       심어 두면 Firebase 가 가입 폼에서 바로 막아 준다(email-already-in-use).
       충돌이 나는 경우는 실제로 계정이 둘이어야 하는 상황이 아니라 막아야
       하는 상황이므로, 그 오류가 곧 우리가 원하는 동작이다.

       카카오·네이버는 본인확인을 거친 주소라 emailVerified 로 둔다. 이걸
       false 로 두면 로그인할 때마다 인증 메일을 요구하게 된다. */
    if(p.email) {
      userProps.email = String(p.email).trim().toLowerCase();
      userProps.emailVerified = true;
    }

    let exists = true;
    try{
      await admin.auth().getUser(uid);
    }catch(e){
      if(e.code === "auth/user-not-found") exists = false;
      else throw new HttpsError("internal", `user_lookup_failed: ${e.code || e.message}`);
    }

    /* 새 소셜 계정을 만들기 전에, 같은 이메일을 쓰는 계정이 이미 있는지 본다.
       있으면 만들지 않는다 — 만들었다 지우는 것보다 애초에 안 만드는 쪽이
       확실하다. 기존 사용자(exists)는 검사하지 않는다. 이미 쓰고 있는
       사람을 뒤늦게 막으면 로그인이 통째로 끊긴다. */
    if(!exists && p.email){
      const other = await findOtherAccountByEmail(admin.firestore(), p.email, uid);
      if(other){
        throw new HttpsError("already-exists",
          `이 주소는 이미 ${other.label}으로 등록되어 있습니다. 그 방법으로 로그인해 주세요.`, { method: other.method });
      }
    }

    try{
      if(exists) await admin.auth().updateUser(uid, userProps);
      else await admin.auth().createUser({ uid, ...userProps });
    }catch(e){
      /* 이메일이 다른 계정에 이미 물려 있는 경우. 새 계정이면 위 검사에서
         이미 걸러졌어야 하지만, 이메일을 심기 시작하기 전에 만들어진 계정을
         갱신할 때 여기서 만날 수 있다. 그때는 이메일 없이 진행한다 —
         로그인을 끊는 것보다 낫고, 중복 자체는 위 검사가 막는다. */
      if(e && e.code === "auth/email-already-exists" && exists){
        console.warn(`[social] 이메일 심기 건너뜀 ${uid}: 다른 계정이 쓰는 중`);
        delete userProps.email; delete userProps.emailVerified;
        try{ await admin.auth().updateUser(uid, userProps); }catch(_){}
      } else {
        throw new HttpsError("internal", `user_upsert_failed: ${e.code || e.message}`);
      }
    }

    /* ── users/{uid} — 이메일과 동의 기록 ─────────────────────────────
       이메일을 여기 남긴다. 전에는 커스텀 토큰 클레임으로만 넘기고 버렸다.
       "계정 충돌이 무섭다" 는 이유였는데, 충돌은 Firebase 사용자에 이메일을
       심을 때 나는 것이지 우리 문서에 적어 두는 것과는 상관이 없었다.
       그 결과 카카오·네이버로 가입한 사람은 이메일이 어디에도 남지 않아
       마케팅 수신에 동의해도 보낼 주소가 없었다.

       카카오는 지금 닉네임만 준다(개발자센터 동의항목에 이메일이 없다).
       그래서 없으면 null 로 둔다. 나중에 항목을 켜면 그 다음 로그인 때
       채워진다 — 그래서 기존 사용자도 이메일이 오면 갱신한다. 다만 없다고
       해서 이미 있는 값을 지우지는 않는다.

       동의는 카카오·네이버의 동의 화면에서 받는다. 카카오싱크 간편가입은
       개발자센터에 등록한 우리 이용약관·개인정보 수집·이용·만 14세·마케팅
       수신을 그쪽 화면에서 대신 받아 준다. 그러니 우리 화면을 한 번 더
       띄우면 같은 것을 두 번 묻는 셈이다.

       대신 그 결과를 읽어 와야 한다. 여태 안 읽고 age14/terms/privacy 를
       true 로, marketing 을 false 로 박아 두고 있었다 — 마케팅에 동의한
       사람이 우리 기록에는 전부 미동의로 남았다.

       네이버는 검수 승인 뒤 같은 방식이 된다. 그때까지는 아래 물러선 값이
       그대로 쓰인다. */
    const db = admin.firestore();
    const now = admin.firestore.FieldValue.serverTimestamp();
    /* 카카오싱크가 대신 받아 준 동의 내역. 못 읽었으면 null 이고, 그때는
       아래에서 기존 기록을 건드리지 않는다. */
    const kt = provider === "kakao" ? mapKakaoTerms(p.terms) : null;
    /* 기존 회원의 기록. 마케팅을 맞춰 줄지 판단하는 데 쓴다. */
    let snapBefore = null;
    if(exists){
      try{ snapBefore = (await db.collection("users").doc(uid).get()).data() || null; }
      catch(e){ console.warn("[social] 기존 기록 조회 실패", uid, e && e.message); }
    }
    let syncedTerms = null;

    /* 탈퇴했다가 다시 가입하는 경우.

       탈퇴해도 카카오·네이버 쪽 앱 연결은 남는다. 그래서 다시 로그인하면
       그쪽이 동의를 다시 묻지 않고 곧장 통과시킨다. 그 상태로 우리가
       service_terms 를 읽으면 '동의함' 이 오는데, 그건 탈퇴 전에 받은
       동의다. 새 계약에 옛 동의를 붙이는 셈이고, 계정 생성일보다 동의일이
       앞서는 기록이 남는다.

       탈퇴 기록으로 가려낸다. deleteAccount 가 개인정보를 지우면서도
       'withdraw' 한 줄은 남겨 두므로(uid 와 시각뿐이라 개인정보가 아니다)
       그 시각과 제공자가 알려 준 동의 시각을 견준다.

         동의 시각이 탈퇴 뒤   → 다시 받은 동의다. 그대로 쓴다
         동의 시각이 탈퇴 전   → 옛 동의다. 우리 동의 화면에서 다시 받는다
         동의 시각을 모른다    → 옛 동의로 본다. 애매하면 다시 묻는다

       조회에 실패하면 다시 묻는 쪽으로 기운다. 동의를 한 번 더 받는 것은
       번거로울 뿐이지만, 받지 않은 동의를 받았다고 적는 것은 되돌릴 수
       없다. */
    let staleConsent = false;
    if(!exists){
      let withdrawnAt = 0;
      try{
        const w = await db.collection("consentEvents")
          .where("uid", "==", uid).where("kind", "==", "withdraw").limit(10).get();
        w.forEach(d => {
          const t = (d.data() || {}).at;
          const ms = t && t.toDate ? t.toDate().getTime() : 0;
          if(ms > withdrawnAt) withdrawnAt = ms;
        });
      }catch(e){
        console.warn("[social] 탈퇴 이력 조회 실패", uid, e && e.message);
        withdrawnAt = -1;                       // 모르면 아래에서 다시 묻는다
      }
      staleConsent = isStaleProviderConsent(
        withdrawnAt, kt && kt.agreedAt ? kt.agreedAt.getTime() : 0);
      if(staleConsent){
        console.log(`[social] 재가입 ${uid} — 제공자 동의가 탈퇴 이전이라 다시 받는다`);
      }
    }

    const patch = { signupMethod: provider, updatedAt: now };
    if(p.email) patch.email = String(p.email).trim().toLowerCase();
    if(!exists){
      if(!p.email) patch.email = null;
      patch.createdAt = now;
      if(staleConsent){
        /* consents 를 쓰지 않는다. 그러면 auth-state.js 의 guardConsent 가
           다음 화면에서 동의 페이지로 보낸다 — 구글과 같은 길이다. */
      } else {
        patch.consents = kt ? {
          version: CONSENT_VERSION,
          method: "kakao-sync",         // 카카오 동의 화면에서 받은 동의
          age14: kt.age14, terms: kt.terms, privacy: kt.privacy,
          marketing: kt.marketing,
          kakaoTerms: kt.raw,           // 받은 그대로. 매핑이 틀려도 자료는 남는다
          agreedAt: kt.agreedAt || now  // 사용자가 실제로 누른 시각
        } : {
          version: CONSENT_VERSION,
          method: "signup-notice",
          age14: true, terms: true, privacy: true,
          marketing: false,             // 선택 — 설정 페이지에서 켠다
          agreedAt: now
        };
        patch.marketingAt = (kt && kt.marketing) ? (kt.agreedAt || now) : null;
      }
    } else if(kt){
      /* 이미 있는 회원. 마케팅만 맞춰 준다. 그리고 우리 쪽에서 한 번도
         만진 적이 없을 때만이다.

         켜고 끈 기록(marketingAt·marketingOffAt)이 있으면 그 사람은 우리
         설정 화면에서 자기 뜻을 밝힌 것이다. 카카오 값으로 덮으면 철회를
         무시하는 셈이 된다 — 로그인할 때마다 다시 켜진다.

         반대로 만진 적이 없는 회원은 우리가 marketing:false 를 박아 둔
         탓에 미동의로 남아 있다. 그 사람들이 여기서 제자리를 찾는다. */
      const cur = (snapBefore && snapBefore.consents) || {};
      const touched = !!(snapBefore && (snapBefore.marketingAt || snapBefore.marketingOffAt));
      const needsFix = !touched && cur.marketing !== kt.marketing;
      if(needsFix || !cur.kakaoTerms){
        /* 받은 방식도 실제에 맞춘다. 여태 'signup-notice' 로 적혀 있었는데
           그 고지 문구는 화면에서 지운 지 오래다 — 이 사람들이 실제로 본
           것은 카카오의 동의 화면이다. 처음 기록은 consentEvents 의
           'signup' 사건에 그대로 남아 있으므로 잃는 것은 없다.

           필수 세 항목은 건드리지 않는다. 카카오싱크는 필수 약관에 동의해야
           가입이 되므로 기존 값(true)이 맞고, 태그를 잘못 짚었을 때 멀쩡한
           동의 기록을 false 로 덮는 쪽이 훨씬 나쁘다. 근거는 아래 원본으로
           붙는다. */
        patch.consents = Object.assign({}, cur, {
          kakaoTerms: kt.raw,
          method: "kakao-sync",
        });
        if(needsFix){
          patch.consents.marketing = kt.marketing;
          patch.marketingAt = kt.marketing ? (kt.agreedAt || now) : null;
        }
        syncedTerms = needsFix ? "marketing" : "terms";
      }
    }
    try{
      await db.collection("users").doc(uid).set(patch, { merge: true });
    }catch(e){
      // 새 가입인데 기록을 못 남겼으면 계정도 남기지 않는다. 반쪽짜리 가입을 두지 않는다.
      if(!exists){ try{ await admin.auth().deleteUser(uid); }catch(_){} }
      throw new HttpsError("internal", `user_doc_save_failed: ${e.code || e.message}`);
    }

    /* 이력. 가입은 가입대로, 나중에 맞춘 것은 맞춘 대로 남긴다.
       마케팅이 켜지고 꺼진 것은 분쟁에서 답해야 하는 사건이라 users 문서의
       마지막 상태만으로는 부족하다. */
    if(!exists && patch.consents){
      await logConsent(db, uid, "signup", {
        email: patch.email || null, version: CONSENT_VERSION,
        method: patch.consents.method || null, provider,
        marketing: patch.consents.marketing === true,
        kakaoTerms: kt ? kt.raw : null,
      }, req);
    } else if(!exists && staleConsent){
      /* 아직 동의를 받지 않았다. 가입으로 적으면 안 된다 — 동의 화면을
         마쳐야 recordSignupConsent 가 'signup' 을 남긴다. 다만 재가입
         시도가 있었다는 사실은 남겨 둔다. */
      await logConsent(db, uid, "rejoin_pending", { provider }, req);
    } else if(syncedTerms){
      await logConsent(db, uid, "provider_sync", {
        email: (patch.email || (snapBefore && snapBefore.email)) || null,
        version: CONSENT_VERSION, provider, what: syncedTerms,
        marketing: (patch.consents || {}).marketing === true,
        kakaoTerms: kt ? kt.raw : null,
      }, req);
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
  /* '계정 활동에 따라' 라고 적었는데, 동의 안내처럼 회원이 아무것도 하지
     않았는데 나가는 메일도 있다. 세 메일 모두에 맞는 말로 바꾼다. */
  const autoNote = en
    ? "This email was sent in connection with your KOSAI account."
    : "본 메일은 KOSAI 계정에 관한 안내로 발송되었습니다.";
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

/* 동의 절차가 생기기 전에 가입한 회원에게 보내는 안내.

   광고가 아니다. 정보통신망법 제50조는 영리목적 광고성 정보에만 사전
   수신동의를 요구하므로 마케팅 수신에 동의하지 않은 회원에게도 보낼 수
   있다. 다만 받는 사람은 그 구분을 모르니 본문에 광고가 아니라고 적는다 —
   광고로 읽히면 신고당하고, 그러면 도메인 평판이 상한다.

   겁주지 않는다. 지금 계정을 지울 계획이 없고(처리방침의 보유 기간이
   '회원 탈퇴 시까지' 다), 없는 기한을 만들어 압박하면 그것대로 거짓말이다.
   무엇이 필요하고 어떻게 하면 되는지만 적는다. */
function consentNoticeMail(lang){
  const link = SITE_URL + "/Login.html";
  const en = lang === "en";
  if(en){
    return {
      subject: "[KOSAI] Request for your consent to our Terms and privacy notice",
      html: mailLayout({ lang, heading: "Request for your consent",
        intro: "Hello,<br><br>" +
               "Our records indicate that you registered before we introduced our consent screen, and that we do not hold your agreement to our Terms of Service or to the collection and use of your personal data. In accordance with Articles 15 and 22 of the Personal Information Protection Act, we are writing to request your consent.<br><br>" +
               "Signing in using the button below will display the consent screen. Once you have accepted the required items, you may continue to use the service without interruption.<br><br>" +
               "&middot; The process takes approximately ten seconds.<br>" +
               "&middot; Your account, watchlist and settings remain unchanged.<br>" +
               "&middot; Marketing messages are optional; declining them places no restriction on your use of the service.",
        btnText: "Go to the consent screen", link,
        outro: "This message is a service notice concerning your account and is not a commercial advertisement under the Act on Promotion of Information and Communications Network Utilization and Information Protection. For enquiries, please contact hello@kosai.kr." })
    };
  }
  return {
    subject: "[KOSAI] 개인정보 수집·이용 동의 안내",
    html: mailLayout({ lang, heading: "개인정보 수집·이용 동의 안내",
      intro: "안녕하세요, KOSAI입니다.<br><br>" +
             "회원님께서는 당사가 동의 절차를 도입하기 이전에 가입하신 회원으로, 이용약관 및 개인정보 수집·이용에 대한 동의 내역이 확인되지 않습니다. 「개인정보 보호법」 제15조 및 제22조에 따라 회원님의 동의를 요청드립니다.<br><br>" +
             "아래 버튼을 눌러 로그인하시면 동의 화면이 표시됩니다. 필수 항목에 동의하신 후 서비스를 계속 이용하실 수 있습니다.<br><br>" +
             "&middot; 소요 시간은 약 10초입니다.<br>" +
             "&middot; 계정 정보와 워치리스트·설정은 변경 없이 그대로 유지됩니다.<br>" +
             "&middot; 마케팅 정보 수신은 선택 사항이며, 동의하지 않으셔도 서비스 이용에 제한이 없습니다.",
      btnText: "동의 화면으로 이동", link,
      outro: "본 메일은 「정보통신망 이용촉진 및 정보보호 등에 관한 법률」상 광고성 정보가 아닌, 서비스 이용에 관한 안내 메일입니다. 문의사항은 hello@kosai.kr로 연락 주시기 바랍니다." })
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
    if (seen.includes(ticker)) return { ok: true, used: seen.length };   // 오늘 이미 본 종목 — 추가 차감 없음
    if (seen.length >= limit) return { ok: false, used: seen.length };
    tx.set(ref, {
      tickers: admin.firestore.FieldValue.arrayUnion(ticker),
      count: seen.length + 1,
      day,
      uid,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true, used: seen.length + 1 };
  });
}

/* 오늘 몇 개를 썼는지. 화면이 '남은 개수'를 보여 주려면 필요하다.
   report_reads 는 클라이언트가 읽지 못하게 막아 뒀으므로(firestore.rules) 서버가 준다. */
async function usageOf(db, uid) {
  const snap = await db.doc(`report_reads/${uid}_${kstDay()}`).get();
  const seen = (snap.exists && snap.data().tickers) || [];
  return seen.length;
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

    const use = await consumeDailyRead(db, uid, ticker, limit);
    if (!use.ok) {
      console.warn(`[getReport] 일일 한도(${plan}=${limit}) 초과 uid=${uid}`);
      throw new HttpsError("resource-exhausted", "오늘 열람 한도를 모두 사용했습니다.");
    }

    return { ticker, paid: snap.data(), plan, limit, used: use.used };
  }
);

/* ── 회원 탈퇴 ────────────────────────────────────────────────
   ⚠️ 이 함수 없이 클라이언트에서 deleteUser() 만 부르면, 계정은 사라지는데
      subscriptions/{uid} 는 status:active·billingKey 그대로 남는다. 매일 도는
      renewSubscriptions 가 그 문서를 집어 다음 달에도, 그 다음 달에도 카드를
      긁는다. 당사자는 로그인할 수도, 해지할 수도 없다. 돈만 빠져나간다.
      그래서 탈퇴는 반드시 서버가 처리한다 — 구독을 먼저 닫고 계정을 지운다.

   탈퇴 시 환불도 여기서 처리한다. 자세한 건 아래 주석 참고.

   남기는 것과 지우는 것
     · payments/{uid}/items  남긴다. 전자상거래법상 대금결제 기록은 5년 보존
       의무가 있다(개인정보 파기 원칙의 법정 예외).
     · subscriptions/{uid}   문서는 남기되 결제에 쓰이는 값(billingKey·
       customerKey·카드)을 지우고 status 를 'deleted' 로 바꾼다. 다시 긁힐
       여지를 없애는 게 목적이다.
     · watchlists/{uid}, report_reads  지운다. 보관할 이유가 없다.
   ─────────────────────────────────────────────────────────── */
/* secrets: [TOSS_SECRET_KEY] 를 일부러 뺐다.
   선언해 두면 값이 없는 상태에서는 배포 자체가 막힌다("non-interactive mode but
   have no value for the secret"). 실사이트에는 아직 결제를 올리지 않았으므로
   토스 비밀키가 등록된 적이 없고, 그 하나 때문에 탈퇴·로그인 같은 결제와
   무관한 함수까지 전부 배포가 멈췄다.
   구독이 하나도 없으니 아래 환불 분기는 실행되지 않는다. 결제를 켜는 날
   firebase functions:secrets:set TOSS_SECRET_KEY 를 먼저 하고 이 줄을 되살린다. */
/* ── 가입 동의 기록 ──────────────────────────────────────────────
   동의는 나중에 "언제 무엇에 동의했는가" 를 답해야 하는 기록이다. 그런데
   지금까지는 클라이언트가 users/{uid} 에 직접 썼다. 브라우저 콘솔을 열 수
   있는 사람은 누구나 age14 나 agreedAt 을 고칠 수 있었다는 뜻이다. 본인이
   고칠 수 있는 기록은 증거가 아니다.

   그래서 값을 서버가 정한다. 클라이언트가 보내는 것은 선택 항목인 마케팅
   수신 여부 하나뿐이고, 판 번호·필수 항목·시각은 여기서 박는다. 필수
   항목은 거부하면 가입 자체가 성립하지 않으므로 언제나 true 다.

   이미 동의 기록이 있으면 건드리지 않는다. 로그인할 때마다 덮어쓰면 처음
   동의한 시각이 사라진다 — 그 시각이 이 기록의 핵심이다. */
const SIGNUP_METHODS = ["email", "google", "kakao", "naver"];



/* ── 동의 이력 (consentEvents) ────────────────────────────────────
   users/{uid}.consents 는 '지금 상태' 다. 그것만으로는 답하지 못하는
   질문이 있다 — "언제 동의했고 언제 철회했는가".

   실제로 setMarketingConsent 가 marketingAt / marketingOffAt 을 덮어쓰고
   있었다. 켰다 껐다를 반복하면 마지막 한 번만 남는다. 분쟁이 나면 우리가
   입증해야 하는 자료인데 스스로 지우고 있던 셈이다.

   그래서 추가만 되는 이력을 따로 둔다. 고치지 않고 지우지 않는다.

   남기는 것
     uid·email   누구인지
     at          언제
     kind        무슨 일 (signup · marketing_on · marketing_off · withdraw)
     version     그때의 동의서 판 번호
     method      어떻게 받았나 (checkbox · signup-notice)
     provider    어느 경로로 가입했나
     ip·ua       증빙력을 위해. 분쟁에서 '그 시각 그 단말에서' 를 답한다.

   쓰기는 서버만 한다(firestore.rules 에서 클라이언트를 막는다). 본인이
   고칠 수 있는 기록은 아무것도 증명하지 못한다 — users 문서를 닫은 것과
   같은 이유다.

   실패해도 던지지 않는다. 이력을 못 남겼다고 가입이나 설정 변경을 막으면
   사용자만 손해다. 대신 로그에 남겨 사람이 알아챌 수 있게 한다. */
async function logConsent(db, uid, kind, extra, req) {
  try {
    const r = (req && req.rawRequest) || {};
    const h = r.headers || {};
    const ip = String(h["x-forwarded-for"] || r.ip || "").split(",")[0].trim().slice(0, 45);
    const ua = String(h["user-agent"] || "").slice(0, 300);
    await db.collection("consentEvents").add(Object.assign({
      uid, kind,
      at: admin.firestore.FieldValue.serverTimestamp(),
      ip: ip || null, ua: ua || null,
    }, extra || {}));
  } catch (e) {
    console.error(`[consentLog] 실패 uid=${uid} kind=${kind}: ${e && e.message}`);
  }
}

exports.recordSignupConsent = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  const d = req.data || {};
  const method = d.method === "checkbox" ? "checkbox" : "signup-notice";
  const marketing = d.marketing === true;
  const provider = SIGNUP_METHODS.includes(d.provider) ? d.provider : "unknown";
  const email = typeof d.email === "string" ? d.email.trim().toLowerCase().slice(0, 320) : "";

  const db = admin.firestore();
  const ref = db.collection("users").doc(uid);
  const now = admin.firestore.FieldValue.serverTimestamp();
  const snap = await ref.get();

  /* 세 가지 경우를 갈라야 한다. 전에는 '동의한 적 있나' 하나로만 보고
     있어서, 약관을 개정하고 판 번호를 올리면 재동의가 저장되지 않았다.
     저장이 안 되니 판 번호가 그대로고, 그러면 동의 화면이 다시 뜬다 —
     전 회원이 동의 화면에 갇힌다. 아무도 아직 판을 올리지 않아 터지지
     않았을 뿐이다.

       처음      동의 기록이 없다            → 다 쓴다
       재동의    있는데 판이 다르다          → 필수 항목만 새로 쓴다
       최신      있고 판도 같다              → 건드리지 않는다 */
  const prev = (snap.exists && snap.data().consents) || null;
  const hadConsent = !!(prev && prev.agreedAt);
  if (hadConsent && prev.version === CONSENT_VERSION) {
    return { ok: true, first: false, reconsent: false };
  }

  /* 아직 동의를 남기지 않은 계정만 본다. 이미 쓰는 회원을 나중에 막아
     내쫓으면 안 된다 — 여기서 걸러야 할 것은 '지금 막 만들어진 두 번째
     계정' 이다. 부르는 쪽이 이 계정을 지우고 원래 방법으로 안내한다. */
  if (!hadConsent && email) {
    const other = await findOtherAccountByEmail(db, email, uid);
    if (other) {
      throw new HttpsError("already-exists",
        `이 주소는 이미 ${other.label}으로 등록되어 있습니다. 그 방법으로 로그인해 주세요.`, { method: other.method });
    }
  }

  const patch = { updatedAt: now };
  if (email) patch.email = email;

  const c = {
    version: CONSENT_VERSION,
    method,
    age14: true, terms: true, privacy: true,
    agreedAt: now
  };

  if (hadConsent) {
    /* 재동의. 마케팅 수신은 건드리지 않는다 — 선택 항목이고 설정 화면이
       관리한다. 여기서 폼 값으로 덮으면 켜 둔 사람이 약관 개정 한 번에
       조용히 꺼진다. 재동의 화면도 그래서 마케팅 칸을 보여 주지 않는다.

       가입 시각(createdAt)과 가입 방법(signupMethod)도 그대로 둔다.
       개정 때문에 다시 받은 것이지 다시 가입한 것이 아니다. */
    c.marketing = !!prev.marketing;
  } else {
    c.marketing = marketing;
    patch.marketingAt = marketing ? now : null;
    patch.signupMethod = provider;
    patch.createdAt = now;
  }
  patch.consents = c;
  await ref.set(patch, { merge: true });

  /* 처음 동의한 시각은 consents.agreedAt 에서 밀려나지만 이력에는 남는다 —
     'signup' 사건이 그 시각을 들고 있다. 그래서 덮어써도 잃는 것이 없다. */
  await logConsent(db, uid, hadConsent ? "reconsent" : "signup", Object.assign({
    email: email || null, version: CONSENT_VERSION, method, provider,
    marketing: c.marketing
  }, hadConsent ? { prevVersion: prev.version || null } : {}), req);

  return { ok: true, first: !hadConsent, reconsent: hadConsent };
});

/* 마케팅 수신 동의 켜고 끄기 — 설정 페이지가 부른다.
   동의 기록과 같은 문서에 들어가므로 여기도 서버가 쓴다. 켠 시각과 끈
   시각을 따로 남긴다. 한 칸을 켰다 껐다 하면 "언제 동의했고 언제
   철회했나" 를 답할 수 없다. */
exports.setMarketingConsent = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  const on = (req.data || {}).on === true;
  const db = admin.firestore();
  const now = admin.firestore.FieldValue.serverTimestamp();
  await db.collection("users").doc(uid).set({
    consents: { marketing: on },
    marketingAt: on ? now : null,
    marketingOffAt: on ? null : now,
    updatedAt: now
  }, { merge: true });
  /* 위 문서는 마지막 상태만 들고 있다. 켰다 껐다 한 이력은 여기 남는다. */
  const mine = (await db.collection("users").doc(uid).get()).data() || {};
  await logConsent(db, uid, on ? "marketing_on" : "marketing_off",
    { email: mine.email || null, version: CONSENT_VERSION }, req);
  return { ok: true, marketing: on };
});

exports.deleteAccount = onCall(
  { region: REGION, cors: true, secrets: [KAKAO_ADMIN_KEY] },
  async (req) => {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  const db = admin.firestore();
  const subRef = db.doc(`subscriptions/${uid}`);
  const sub = (await subRef.get()).data() || null;

  /* 탈퇴한다고 환불받을 권리가 사라지지는 않는다. 결제 후 7일 이내에 리포트를
     한 번도 열지 않았다면 전액 환불은 전자상거래법 제17조가 준 권리이고,
     요금제 페이지에도 그렇게 적어 뒀다. '환불 신청' 버튼을 먼저 누르지 않았다는
     이유로 돈을 가질 수는 없다. 그래서 여기서 같은 기준으로 계산해 먼저 돌려준다.

     환불이 실패하면 탈퇴를 진행하지 않는다. 계정을 지운 뒤에 실패하면 당사자는
     로그인도 못 하는데 돈은 우리가 들고 있는 상태가 된다 — 되돌릴 방법이 없다. */
  let refunded = 0;
  if (subActive(sub) && sub.lastPaymentKey) {
    const q = await refundQuote(db, uid, sub);
    if (q.amount > 0) {
      try {
        await doRefund(db, uid, sub, q);
        refunded = q.amount;
      } catch (e) {
        console.error(`[delete] 환불 실패 uid=${uid}`, e && e.message);
        throw new HttpsError("failed-precondition",
          "환불 처리에 실패해 탈퇴를 진행하지 않았습니다. 구독 관리에서 환불을 먼저 신청해 주세요.");
      }
    }
  }

  if (sub) {
    await subRef.set({
      status: "deleted",
      cancelAtPeriodEnd: true, pendingPlan: null,
      billingKey: admin.firestore.FieldValue.delete(),
      customerKey: admin.firestore.FieldValue.delete(),
      card: admin.firestore.FieldValue.delete(),
      deletedAt: admin.firestore.FieldValue.serverTimestamp(),
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
  }

  try { await db.doc(`watchlists/${uid}`).delete(); } catch (e) { console.warn("[delete] watchlist", e && e.message); }
  /* 동의 기록. 동의 화면에서 "보유 기간: 회원 탈퇴 시까지"라고 알리고 받았으니
     탈퇴하면 지워야 한다. 클라이언트도 지우지만 창을 닫아 버리면 남는다. */
  try { await db.doc(`users/${uid}`).delete(); } catch (e) { console.warn("[delete] user doc", e && e.message); }
  try {
    const reads = await db.collection("report_reads").where("uid", "==", uid).limit(200).get();
    await Promise.all(reads.docs.map((d) => d.ref.delete()));
  } catch (e) { console.warn("[delete] reads", e && e.message); }

  /* 동의 이력. "보유 기간: 회원 탈퇴 시까지" 라고 알리고 받았으므로 이력에
     담긴 개인정보(이메일·IP·단말)도 같이 지운다. 다만 '이 계정이 있었고
     언제 지웠는가' 한 줄은 남긴다 — 지웠다는 사실 자체가 증빙이고, uid 와
     시각만으로는 누구인지 알 수 없어 개인정보가 아니다. */
  try {
    const evs = await db.collection("consentEvents").where("uid", "==", uid).limit(500).get();
    await Promise.all(evs.docs.map((d) => d.ref.delete()));
  } catch (e) { console.warn("[delete] consentEvents", e && e.message); }
  /* 카카오 연결을 먼저 끊는다. 우리 계정을 지우고 나서 하면, 중간에
     실패했을 때 어느 쪽이 남았는지 알기 어려워진다.

     결과를 탈퇴 기록에 남긴다. 끊지 못한 사람이 다시 가입하면 카카오가
     동의를 다시 묻지 않으므로, 나중에 '왜 이 사람만 우리 동의 화면을
     봤나' 를 이 한 칸으로 답할 수 있다. */
  let unlinked = null;
  if (String(uid).startsWith("kakao:")) {
    unlinked = await kakaoUnlink(uid);
  }
  await logConsent(db, uid, "withdraw",
    unlinked === null ? {} : { kakaoUnlinked: unlinked }, req);

  await admin.auth().deleteUser(uid);
  return { ok: true, hadSubscription: !!(sub && sub.plan), refunded };
});

/* 오늘 남은 열람 수. 구독 관리 화면이 이걸로 '3 / 5개'를 보여 준다.
   한도에 부딪히기 전에는 알 길이 없었다 — 다 쓰고 나서야 알려 주는 건 늦다. */

/* ── 관리자 조회 ──────────────────────────────────────────────────
   동의를 받아 두기만 하고 볼 방법이 없으면 받지 않은 것과 크게 다르지 않다.
   문의가 들어오거나 분쟁이 생겼을 때 "이 사람이 언제 무엇에 동의했는가" 를
   그 자리에서 답할 수 있어야 한다.

   누가 관리자인가. 이메일로 정한다. 아래 목록은 공개 저장소에 들어가므로
   이미 사이트 푸터에 적혀 있는 업무용 주소만 쓴다 — 개인 주소를 넣으면
   저장소를 통해 새어 나간다. 늘리려면 여기에 더한다.

   인증된 메일만 인정한다. 인증 안 된 주소는 그 사람 것이라는 근거가 없다. */
const ADMIN_EMAILS = ["hello@kosai.kr"];

function assertAdmin(req) {
  const t = (req.auth && req.auth.token) || {};
  const email = String(t.email || "").trim().toLowerCase();
  if (!email || !t.email_verified || !ADMIN_EMAILS.includes(email)) {
    throw new HttpsError("permission-denied", "관리자만 볼 수 있습니다.");
  }
  return email;
}

function tsIso(v) {
  try { return v && v.toDate ? v.toDate().toISOString() : null; } catch (e) { return null; }
}

/* 가입 방법 표기를 하나로 맞춘다.

   8월 20일 전에는 파이어베이스가 주는 값을 그대로 적었다 — 이메일 가입이
   'password', 구글이 'google.com' 이다. 서버로 옮기면서 'email' · 'google'
   로 바뀌었고, 그래서 같은 이메일 가입이 목록에 두 가지 말로 나온다.
   읽을 때 맞춘다. 문서를 고치지는 않는다 — 받은 그대로 두는 편이 낫고,
   고치다 잘못 건드리면 되돌릴 수 없다.

   모르는 값은 null 이다. 'email' 로 뭉뚱그리면 없는 사실을 지어내는 셈이다. */
const PROVIDER_ALIAS = {
  password: "email", email: "email",
  "google.com": "google", google: "google",
  kakao: "kakao", naver: "naver",
};
const PROVIDER_LABEL = { email: "이메일", google: "구글", kakao: "카카오", naver: "네이버" };

function normProvider(v) {
  return PROVIDER_ALIAS[String(v || "").trim().toLowerCase()] || null;
}
function providerLabel(v) {
  const p = normProvider(v);
  return p ? PROVIDER_LABEL[p] : null;
}

/* 요약 — 화면 맨 위에 걸어 두는 숫자들.
   재확인 대상은 정보통신망법 시행령 제62조의3 이 근거다. 광고성 정보
   수신동의를 받은 날부터 2년마다 수신동의 여부를 확인해야 한다. 안내할 때
   전송자 명칭·수신동의 날짜·유지 또는 철회 방법을 함께 알려야 한다. */
exports.adminConsentStats = onCall({ region: REGION, cors: true }, async (req) => {
  assertAdmin(req);
  const db = admin.firestore();
  const users = await db.collection("users").limit(5000).get();
  const now = Date.now();
  const TWO_YEARS = 2 * 365 * 24 * 60 * 60 * 1000;

  let total = 0, consented = 0, marketing = 0, dueRecheck = 0, stale = 0;
  const byProvider = {};
  const byVersion = {};
  users.forEach((d) => {
    const u = d.data() || {};
    const c = u.consents || {};
    total++;
    if (c.agreedAt) consented++;
    /* 어느 판에 동의했는지 세어 둔다. 약관을 개정하면 여기서 재동의
       진행률이 보인다 — 안 보이면 다 받았는지 알 길이 없다. */
    if (c.agreedAt) {
      const v = c.version || "(판 없음)";
      byVersion[v] = (byVersion[v] || 0) + 1;
      if (c.version !== CONSENT_VERSION) stale++;
    }
    const p = normProvider(u.signupMethod) || "unknown";
    byProvider[p] = (byProvider[p] || 0) + 1;
    if (c.marketing) {
      marketing++;
      const at = u.marketingAt || c.agreedAt;
      const ms = at && at.toDate ? at.toDate().getTime() : 0;
      if (ms && now - ms >= TWO_YEARS) dueRecheck++;
    }
  });
  /* 동의 없는 계정 — 이 화면이 여태 못 보던 것.

     여기까지의 숫자는 전부 users 문서를 센 것이다. 그런데 Auth 에는
     계정이 있는데 users 문서가 없거나 그 안에 consents 가 없는 계정이
     생길 수 있다. 가입하다 동의 화면에서 나가 버린 경우다. 그런 계정은
     users 를 아무리 세어도 안 나온다 — 없는 것처럼 보인다.

     purgeUnconsented 가 24시간 뒤 지우지만, 그 사이의 계정과 상한(50)에
     걸려 남은 계정은 여기 잡힌다. 세어서 보여 준다. */
  let noConsent = 0, authTotal = 0;
  const noConsentRows = [];
  try {
    const have = new Set();
    users.forEach((d) => { if ((d.data() || {}).consents) have.add(d.id); });
    let pageToken;
    do {
      const page = await admin.auth().listUsers(1000, pageToken);
      pageToken = page.pageToken;
      for (const au of page.users) {
        authTotal++;
        if (have.has(au.uid)) continue;
        noConsent++;
        if (noConsentRows.length < 200) {
          noConsentRows.push({
            uid: au.uid,
            email: au.email ? au.email.toLowerCase() : null,
            createdAt: au.metadata && au.metadata.creationTime
              ? new Date(au.metadata.creationTime).toISOString() : null,
          });
        }
      }
    } while (pageToken);
    noConsentRows.sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
  } catch (e) {
    /* 실패하면 세지 못했다는 사실을 그대로 알린다. 0 으로 내보내면
       '없다' 로 읽혀서, 못 본 것과 없는 것이 뒤섞인다. */
    console.warn("[adminConsentStats] Auth 훑기 실패:", e && e.message);
    return { total, consented, marketing, dueRecheck, stale, byProvider, byVersion,
             version: CONSENT_VERSION, noConsent: null, authTotal: null, noConsentRows: [] };
  }

  return { total, consented, marketing, dueRecheck, stale, byProvider, byVersion,
           version: CONSENT_VERSION, noConsent, authTotal, noConsentRows };
});

/* 한 사람의 현재 동의 상태와 이력. 이메일 또는 uid 로 찾는다. */
exports.adminConsentLookup = onCall({ region: REGION, cors: true }, async (req) => {
  assertAdmin(req);
  const db = admin.firestore();
  const q = String(((req.data || {}).q) || "").trim().toLowerCase();
  if (!q) throw new HttpsError("invalid-argument", "이메일 또는 uid 가 필요합니다.");

  /* 이메일로 찾을 때 users 문서만 보면 안 된다.

     목록(adminUserList)은 users 문서에 이메일이 없으면 Auth 에서 가져와
     보여 준다. 그래서 화면에는 주소가 멀쩡히 떠 있는데 여기서는 '찾지
     못했습니다' 가 나왔다 — 8월 20일 전에 만들어진 계정은 users 문서에
     email 칸이 없다(그때는 Auth 에만 있었다).

     두 곳을 다 본다. 목록이 보여 주는 것과 조회가 찾는 것이 어긋나면
     그 화면은 못 믿는 화면이 된다. */
  let uid = q;
  if (q.includes("@")) {
    const found = await db.collection("users").where("email", "==", q).limit(1).get();
    if (!found.empty) {
      uid = found.docs[0].id;
    } else {
      try {
        uid = (await admin.auth().getUserByEmail(q)).uid;
      } catch (e) {
        return { found: false };
      }
    }
  }
  /* Auth 기록도 같이 본다. 둘 중 하나만 있는 경우가 실제로 생긴다
     (콘솔에서 한쪽만 지웠거나, 옛 계정이라 아직 안 맞춰졌거나).
     하나라도 있으면 있는 대로 보여 준다 — '찾지 못했습니다' 는 정말로
     아무 데도 없을 때만 할 말이다. */
  let au = null;
  try { au = await admin.auth().getUser(uid); } catch (e) { /* 없으면 없는 대로 */ }

  const snap = await db.collection("users").doc(uid).get();
  if (!snap.exists && !au) return { found: false };
  const u = (snap.exists && snap.data()) || {};
  const c = u.consents || {};

  const evs = await db.collection("consentEvents").where("uid", "==", uid).limit(200).get();
  const events = evs.docs.map((d) => {
    const e = d.data() || {};
    return { kind: e.kind, at: tsIso(e.at), version: e.version || null,
             method: e.method || null, provider: e.provider || null,
             marketing: typeof e.marketing === "boolean" ? e.marketing : null,
             ip: e.ip || null };
  }).sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));

  return {
    found: true, uid,
    email: u.email || (au && au.email ? au.email.toLowerCase() : null),
    signupMethod: normProvider(u.signupMethod),
    signupLabel: providerLabel(u.signupMethod),
    createdAt: tsIso(u.createdAt),
    hasDoc: snap.exists,
    live: !!au,
    emailVerified: au ? !!au.emailVerified : null,
    consents: {
      version: c.version || null, method: c.method || null,
      age14: !!c.age14, terms: !!c.terms, privacy: !!c.privacy,
      marketing: !!c.marketing, agreedAt: tsIso(c.agreedAt),
      /* 카카오가 보낸 원본. 매핑이 맞는지는 이걸 봐야 안다. */
      kakaoTerms: Array.isArray(c.kakaoTerms) ? c.kakaoTerms : null,
    },
    marketingAt: tsIso(u.marketingAt),
    marketingOffAt: tsIso(u.marketingOffAt),
    events,
  };
});

/* 마케팅 수신 동의자 목록 — 발송 전에 뽑는다. 내보내기(CSV)에도 쓴다. */
exports.adminMarketingList = onCall({ region: REGION, cors: true }, async (req) => {
  assertAdmin(req);
  const db = admin.firestore();
  const snap = await db.collection("users")
    .where("consents.marketing", "==", true).limit(5000).get();
  const rows = snap.docs.map((d) => {
    const u = d.data() || {};
    return { uid: d.id, email: u.email || null,
             provider: normProvider(u.signupMethod),
             providerLabel: providerLabel(u.signupMethod),
             agreedAt: tsIso((u.consents || {}).agreedAt),
             marketingAt: tsIso(u.marketingAt) };
  });
  return { count: rows.length, rows };
});

/* 전체 회원 목록.

   마케팅 동의자만 뽑을 수 있으면 "그 사람 가입은 했나" 를 답할 수 없다.
   조회는 이메일이나 uid 를 이미 알고 있어야 쓸 수 있고, 모르는 것을
   물어볼 수는 없다. 목록이 있어야 한다.

   정렬은 메모리에서 한다. orderBy("createdAt") 을 쓰면 그 칸이 없는 옛
   문서가 결과에서 통째로 빠진다 — 파이어스토어는 정렬 기준이 없는 문서를
   건너뛴다. 없는 사람을 빼놓는 목록은 목록이 아니다.

   상한은 2000 이다. 회원이 그보다 많아지면 잘린 사실을 화면에 알리고,
   그때 가서 페이지를 나눈다. 조용히 일부만 보여 주는 것이 제일 나쁘다. */
/* 동의 안내 메일 보내기.

   되돌릴 수 없는 일이다. 한 번 나간 메일은 회수할 수 없고, 같은 사람에게
   두 번 가면 그것대로 신뢰를 깎는다. 그래서 세 겹으로 조인다.

   ① 대상을 좁게 잡는다
      동의 제도 시행일 이전에 만들어진 계정만. 그 뒤에 만들어진 동의 없는
      계정은 '가입하다 나간 것' 이라 안내할 일이 아니다 — purgeUnconsented
      가 치운다. 그런 사람에게 메일을 보내면 그건 스팸이다.

   ② 이미 보낸 사람은 건너뛴다
      consentEvents 에 notice_sent 로 남기고, 보내기 전에 확인한다.
      버튼을 두 번 눌러도 두 번 가지 않는다.

   ③ 미리 보기를 먼저 준다
      dryRun 이면 누구에게 갈지만 돌려주고 아무것도 보내지 않는다.
      화면이 먼저 이걸 부르고, 사람이 확인한 다음에 실제로 보낸다. */
exports.adminNotifyUnconsented = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    assertAdmin(req);
    const db = admin.firestore();
    const dryRun = (req.data || {}).dryRun !== false;   // 기본은 미리 보기
    const CONSENT_EPOCH = Date.parse("2026-08-20T00:00:00Z");
    const MAX_SEND = 200;

    /* 동의 기록이 있는 uid 를 모은다. 이 집합에 없는 Auth 계정이 대상이다. */
    const have = new Set();
    const users = await db.collection("users").limit(5000).get();
    users.forEach((d) => { if ((d.data() || {}).consents) have.add(d.id); });

    const targets = [];
    const skipped = { recent: 0, noEmail: 0, alreadySent: 0 };
    let pageToken;
    do {
      const page = await admin.auth().listUsers(1000, pageToken);
      pageToken = page.pageToken;
      for (const au of page.users) {
        if (have.has(au.uid)) continue;
        const created = Date.parse((au.metadata && au.metadata.creationTime) || "");
        if (!created || created >= CONSENT_EPOCH) { skipped.recent++; continue; }
        if (!emailOk(au.email)) { skipped.noEmail++; continue; }
        targets.push({ uid: au.uid, email: au.email.toLowerCase(),
                       createdAt: new Date(created).toISOString() });
      }
    } while (pageToken);

    /* 이미 안내한 사람 거르기. 사건 기록을 그대로 근거로 쓴다 — 따로
       표시를 만들면 두 곳이 어긋난다. */
    const fresh = [];
    for (const t of targets) {
      let sentBefore = false;
      try {
        const q = await db.collection("consentEvents")
          .where("uid", "==", t.uid).where("kind", "==", "notice_sent").limit(1).get();
        sentBefore = !q.empty;
      } catch (e) {
        /* 확인하지 못했으면 보내지 않는다. 두 번 보내는 것보다 안 보내는
           쪽이 낫다 — 다음에 다시 누르면 된다. */
        console.warn("[notify] 이력 확인 실패, 건너뜀", t.uid, e && e.message);
        skipped.alreadySent++;
        continue;
      }
      if (sentBefore) { skipped.alreadySent++; continue; }
      fresh.push(t);
    }
    fresh.sort((a, b) => String(a.createdAt).localeCompare(String(b.createdAt)));

    if (dryRun) {
      return { dryRun: true, count: fresh.length, rows: fresh.slice(0, 200), skipped };
    }

    const mail = consentNoticeMail("ko");
    const resend = new Resend(RESEND_API_KEY.value());
    let sent = 0;
    const failed = [];
    for (const t of fresh.slice(0, MAX_SEND)) {
      try {
        const { error } = await resend.emails.send({
          from: MAIL_FROM, to: t.email, subject: mail.subject, html: mail.html
        });
        if (error) throw new Error(error.message || "send_failed");
        sent++;
        /* 보낸 뒤에 남긴다. 먼저 남기고 발송에 실패하면 그 사람은 영영
           안내를 못 받는다 — 기록만 있고 메일은 안 간 상태가 된다. */
        await logConsent(db, t.uid, "notice_sent", { email: t.email }, req);
      } catch (e) {
        failed.push({ email: t.email, reason: (e && e.message) || "unknown" });
        console.error("[notify] 발송 실패", t.email, e && e.message);
      }
    }
    return { dryRun: false, sent, failed, remaining: Math.max(0, fresh.length - MAX_SEND) };
  }
);

exports.adminUserList = onCall({ region: REGION, cors: true }, async (req) => {
  assertAdmin(req);
  const db = admin.firestore();
  const CAP = 2000;
  const snap = await db.collection("users").limit(CAP + 1).get();
  const truncated = snap.size > CAP;
  const rows = snap.docs.slice(0, CAP).map((d) => {
    const u = d.data() || {};
    const c = u.consents || {};
    return {
      uid: d.id,
      email: u.email || null,
      provider: normProvider(u.signupMethod),
      providerLabel: providerLabel(u.signupMethod),
      createdAt: tsIso(u.createdAt),
      agreedAt: tsIso(c.agreedAt),
      /* 항목별로 내보낸다. 요약 한 칸만 있으면 분쟁이 생겼을 때 "이 사람이
         개인정보 수집·이용에 동의했다" 를 그 파일만으로는 못 보여 준다.
         내보낸 파일이 곧 제출할 자료다. */
      version: c.version || null,
      method: c.method || null,
      age14: !!c.age14,
      terms: !!c.terms,
      privacy: !!c.privacy,
      marketing: !!c.marketing,
      marketingAt: tsIso(u.marketingAt),
      live: null,          // Auth 에 계정이 실제로 있는가
      authEmail: null,     // Auth 쪽에 이메일이 심겨 있는가
      emailVerified: null,
    };
  });

  /* 계정이 살아 있는지 같이 본다. 콘솔에서 Auth 사용자만 지우면 users
     문서가 남는데, 그 유령 문서는 목록에서 멀쩡한 회원처럼 보이고 실제로
     멀쩡한 가입까지 막은 적이 있다. 보이면 사람이 치울 수 있다.
     실패해도 목록은 그대로 내보낸다 — 부가 정보 때문에 목록을 잃을 이유가
     없다. 그때는 두 칸이 빈 채로 나간다. */
  try {
    for (let i = 0; i < rows.length; i += 100) {
      const part = rows.slice(i, i + 100);
      const res = await admin.auth().getUsers(part.map((r) => ({ uid: r.uid })));
      const byUid = new Map((res.users || []).map((u) => [u.uid, u]));
      part.forEach((r) => {
        const au = byUid.get(r.uid);
        r.live = !!au;
        if (au) {
          /* 이메일 칸은 users 문서에서 가져오는데 인증 여부는 Auth 에서
             온다. 8월 27일 전에 만들어진 카카오·네이버 계정은 Auth 에
             이메일이 아예 없어서(그때는 일부러 안 심었다) 표에는 주소가
             보이는데 인증은 false 로 나온다 — 없는 문제를 있는 것처럼
             보이게 한다. 두 가지를 구분해서 내보낸다. */
          r.authEmail = au.email ? au.email.toLowerCase() : null;
          r.emailVerified = !!au.emailVerified;
          if (!r.email && au.email) r.email = au.email.toLowerCase();
        }
      });
    }
  } catch (e) {
    console.warn("[adminUserList] Auth 조회 실패:", e && e.message);
  }

  /* 최근 가입이 위로. 가입 시각이 없는 옛 문서는 맨 아래로 내린다. */
  rows.sort((a, b) => String(b.createdAt || "").localeCompare(String(a.createdAt || "")));
  return { count: rows.length, truncated, rows };
});

exports.getUsage = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  const db = admin.firestore();
  const sub = (await db.doc(`subscriptions/${uid}`).get()).data() || null;
  if (!subActive(sub)) return { active: false, used: 0, limit: 0 };
  const plan = String(sub.plan || "").toLowerCase();
  return { active: true, plan, limit: DAILY_LIMIT[plan] || 0, used: await usageOf(db, uid) };
});

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

const PRICE = { basic: 9900, pro: 14900 };        // pricing.html·payment-config.js 와 같아야 한다
const PLAN_NAME = { basic: "BASIC", pro: "PRO" };
const REFUND_FEE_RATE = 0.10;                     // 서비스 수수료 10% (요금제 페이지 고지)
const FREE_WITHDRAW_DAYS = 7;                     // 미열람 시 전액 환불 기간

const tossAuth = () =>
  "Basic " + Buffer.from(((TOSS_SECRET_KEY && TOSS_SECRET_KEY.value()) || "") + ":").toString("base64");

async function toss(path, body) {
  /* 스위치가 꺼져 있으면 비밀키가 없다. 빈 키로 토스를 부르면 401 을 받고
     엉뚱한 카드사 오류 메시지가 나간다 — 여기서 먼저 막는다. */
  if (!PAYMENTS_LIVE) throw new HttpsError("failed-precondition", "결제 기능이 아직 준비되지 않았습니다.");
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
/* 결제 한 건을 기록할 때는 '무엇에 대한 결제인가'를 종류(kind)로 남긴다.
   ⚠️ 설명 문장을 한국어로 굳혀 저장하면 영어 화면에서 번역할 방법이 없다.
      화면이 언어에 맞춰 문구를 만들 수 있도록 kind 를 준다. description 은
      관리자 화면·로그에서 사람이 읽기 위한 값으로만 남겨 둔다. */
async function charge(db, uid, sub, amount, description, tag, kind) {
  if (amount <= 0) return null;
  const pay = await toss(`/billing/${sub.billingKey}`, {
    customerKey: sub.customerKey,
    amount,
    orderId: orderId(uid, tag),
    orderName: description,
  });
  await writePayment(db, uid, {
    amount, description, kind: kind || (tag === "up" ? "upgrade" : "subscription"),
    status: "paid", plan: sub.plan,
    paymentKey: pay.paymentKey, orderId: pay.orderId,
    paidAt: pay.approvedAt || new Date().toISOString(),
  });
  return pay;
}

/* ── 1) 카드 등록 + 첫 결제 ───────────────────────────────── */
if (PAYMENTS_LIVE) exports.confirmBilling = onCall(
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

    /* 카드만 바꾸는 경우. 이용 중인 사람도 여기로 온다 — 아래 '이미 구독 중'에서
       막아 버리면 카드가 만료됐을 때 바꿀 길이 없어진다. 결제는 하지 않는다.
       여기서 또 받으면 이중 청구다. */
    if (req.data && req.data.updateMethod) {
      if (!cur) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
      const re = await toss("/billing/authorizations/issue", { authKey, customerKey });
      const card = { company: (re.card && re.card.issuerCode) || "", number: (re.card && re.card.number) || "" };
      const patch = { billingKey: re.billingKey, customerKey, card,
                      updatedAt: admin.firestore.FieldValue.serverTimestamp() };
      // 갱신 결제가 실패해 멈춰 있던 구독이라면, 새 카드로 바로 받아 되살린다.
      // 카드만 갈아 끼우고 끝내면 다음 배치가 돌 때까지 하루를 잠긴 채로 둔다.
      if (cur.status === "past_due") {
        const at = new Date();
        const pay = await charge(db, uid, { ...cur, ...patch, plan: cur.plan },
          PRICE[cur.plan], `${PLAN_NAME[cur.plan]} 월 구독`, "retry");
        patch.status = "active";
        patch.currentPeriodStart = admin.firestore.Timestamp.fromDate(at);
        patch.currentPeriodEnd = admin.firestore.Timestamp.fromDate(addMonth(at));
        patch.lastPaymentKey = pay ? pay.paymentKey : null;
      }
      await ref.set(patch, { merge: true });
      return { ok: true, plan: cur.plan, updated: true };
    }

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

   ⚠️ 해지 예약과 플랜 변경 예약은 함께 둘 수 없다. renewSubscriptions 는
      cancelAtPeriodEnd 를 먼저 보고 끝내므로, 둘 다 걸려 있으면 해지가 이기고
      예약해 둔 변경은 조용히 사라진다. 화면에는 둘 다 예약된 것처럼 보이니
      그건 거짓말이 된다. 게다가 업그레이드는 그 자리에서 차액을 받는데 며칠
      뒤 구독이 닫히면 돈만 받고 닫는 꼴이다.
      다음 달 쓸 플랜을 고르는 건 계속 쓰겠다는 뜻이므로, 여기서 해지 예약을 푼다
      (반대로 해지를 누르면 cancelSubscription 이 변경 예약을 지운다).
   ─────────────────────────────────────────────────────────── */
if (PAYMENTS_LIVE) exports.changePlan = onCall(
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
        // 해지 예약과 함께 둘 수 없다 — 아래 설명 참고.
        cancelAtPeriodEnd: false, canceledAt: null,
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });
      return { ok: true, plan: next, charged: diff };
    }

    // 지금 쓰는 플랜을 다시 고르는 건 '예약 취소'다. 그대로 넣으면 예약이
    // 남아 화면에 '9월 8일부터 PRO' 같은 말이 계속 붙는다.
    const pending = next === sub.plan ? null : next;
    await ref.set({
      pendingPlan: pending,
      cancelAtPeriodEnd: false, canceledAt: null,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true, pendingPlan: pending, resumed: !!sub.cancelAtPeriodEnd };
  }
);

/* ── 3) 해지 / 해지 취소 ─────────────────────────────────────
   해지는 '지금 끊기'가 아니라 '갱신 안 함'이다. 이미 결제한 기간은 그대로 쓴다.
   ─────────────────────────────────────────────────────────── */
if (PAYMENTS_LIVE) exports.cancelSubscription = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const ref = admin.firestore().doc(`subscriptions/${uid}`);
  const sub = (await ref.get()).data();
  if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
  await ref.set({
    cancelAtPeriodEnd: true, canceledAt: admin.firestore.FieldValue.serverTimestamp(),
    // 해지하면 다음 결제 자체가 없다 — 예약해 둔 플랜 변경은 의미가 없다.
    pendingPlan: null,
    updatedAt: admin.firestore.FieldValue.serverTimestamp(),
  }, { merge: true });
  return { ok: true, droppedPlan: sub.pendingPlan || null };
});

if (PAYMENTS_LIVE) exports.resumeSubscription = onCall({ region: REGION, cors: true }, async (req) => {
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
/* 환불 금액 계산 — 요금제 페이지에 고지한 기준 그대로.
   환불 신청과 회원 탈퇴가 같은 계산을 써야 한다. 두 곳에 따로 적으면 언젠가
   한쪽만 고치고 지나가고, 그러면 고지한 기준과 실제가 어긋난다. */
async function refundQuote(db, uid, sub) {
  if (!sub || !sub.lastPaymentKey) return { amount: 0, reason: "" };
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

  if (!opened && used <= FREE_WITHDRAW_DAYS) {
    return { amount: price, reason: "청약철회(7일 이내·미열람)", why: "withdraw" };
  }
  const leftRatio = Math.max(0, (total - used) / total);
  return {
    amount: Math.floor(price * leftRatio * (1 - REFUND_FEE_RATE)),
    reason: opened ? "이용분 차감 환불" : "잔여 기간 환불",
    why: opened ? "used" : "left",
  };
}

async function doRefund(db, uid, sub, q) {
  await toss(`/payments/${sub.lastPaymentKey}/cancel`, {
    cancelReason: q.reason, cancelAmount: q.amount,
  });
  await writePayment(db, uid, {
    amount: -q.amount, description: `환불 · ${q.reason}`,
    kind: "refund", why: q.why || null, status: "refunded",
    plan: sub.plan, paymentKey: sub.lastPaymentKey, paidAt: new Date().toISOString(),
  });
}

if (PAYMENTS_LIVE) exports.requestRefund = onCall(
  { region: REGION, cors: true, secrets: [TOSS_SECRET_KEY] },
  async (req) => {
    const uid = uidOrThrow(req);
    const db = admin.firestore();
    const ref = db.doc(`subscriptions/${uid}`);
    const sub = (await ref.get()).data();
    if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
    if (!sub.lastPaymentKey) throw new HttpsError("failed-precondition", "환불할 결제 건이 없습니다.");

    const q = await refundQuote(db, uid, sub);
    const amount = q.amount;
    if (amount <= 0) throw new HttpsError("failed-precondition", "환불 가능한 금액이 없습니다.");
    await doRefund(db, uid, sub, q);
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
if (PAYMENTS_LIVE) exports.renewSubscriptions = onSchedule(
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
        // 탈퇴로 계정이 사라진 문서가 남아 있으면 긁지 않는다. deleteAccount 가
        // status 를 바꿔 두므로 여기까지 오지 않지만, 한 번 더 확인한다 —
        // 없는 사람 카드를 긁는 사고는 되돌릴 수가 없다.
        try {
          await admin.auth().getUser(uid);
        } catch (e) {
          if (e && e.code === "auth/user-not-found") {
            console.warn(`[renew] 계정 없음 — 건너뜀 uid=${uid}`);
            await d.ref.set({
              status: "deleted", billingKey: admin.firestore.FieldValue.delete(),
              updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            }, { merge: true });
            continue;
          }
          throw e;
        }
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
          kind: "failed", status: "failed", plan: sub.plan, paidAt: null,
        });
      }
    }
  }
);

/* ── 6) 동의를 마치지 못한 계정 정리 ──────────────────────────────
   구글 가입은 팝업이 닫히는 순간 파이어베이스가 계정을 먼저 만든다. 동의는
   그 뒤 Consent.html 에서 받는다. 그 사이에 창을 닫으면 동의 기록 없는
   계정이 남는다.

   화면 쪽은 auth-state.js 의 guardConsent 가 막고 있다 — 어느 페이지로
   들어와도 동의 페이지로 되돌린다. 그래서 서비스를 쓰지는 못한다.

   그런데 '못 쓰게 막는 것' 과 '가지고 있지 않는 것' 은 다르다. 그 계정에는
   이메일과 이름이 들어 있고, 우리는 그걸 보관할 근거(동의)를 받지 못했다.
   동의 없이 받은 개인정보를 무기한 들고 있을 수는 없다.

   그래서 매일 한 번 훑어 지운다. 지우는 조건이 좁아야 한다 — 잘못 지우면
   멀쩡한 회원 계정이 사라지는, 되돌릴 수 없는 자리다.

     · 만든 지 24시간이 안 됐으면 건드리지 않는다. 가입하다 잠깐 자리를
       비운 사람을 지우면 안 된다.
     · users/{uid} 에 consents 가 있으면 건드리지 않는다.
     · 문서를 읽지 못하면(권한·통신) 건드리지 않는다. '없다' 와 '못 읽었다'
       를 구분하지 않으면 장애가 곧 계정 삭제가 된다.

   이메일·카카오·네이버 가입은 계정이 만들어지는 그 자리에서 동의가 기록되므로
   여기 걸리지 않는다. 실제 대상은 중간에 그만둔 구글 가입뿐이다.
   ─────────────────────────────────────────────────────────── */
exports.purgeUnconsented = onSchedule(
  { region: REGION, schedule: "30 3 * * *", timeZone: "Etc/UTC" },   // 12:30 KST
  async () => {
    const db = admin.firestore();
    const GRACE_MS = 24 * 60 * 60 * 1000;
    const cutoff = Date.now() - GRACE_MS;

    /* 한 번에 지울 수 있는 상한. 이 함수는 되돌릴 수 없는 일을 사람 확인 없이
       매일 한다 — 조건을 잘못 쓰면 전 회원이 하루아침에 사라진다. 상한에
       걸리면 남은 것은 다음 날 처리되고, 로그에 그 사실이 남아 사람이
       알아챌 수 있다. 정상 상황에서 하루 대상은 많아야 몇 건이다. */
    const MAX_DELETE = 50;

    /* 동의 제도가 생기기 전에 가입한 계정은 지우지 않는다.

       이 함수가 잡아야 하는 것은 '가입하다 동의 화면에서 나가 버린 계정'
       이다. 그런데 조건이 '24시간 지났고 동의 기록이 없다' 뿐이라, 6월에
       가입해 그동안 안 들어온 멀쩡한 회원도 똑같이 걸린다. 그 사람은
       동의를 거부한 것이 아니라 물어본 적이 없는 것이다. 물어보지도 않고
       지우는 것은 안 된다.

       그런 계정은 다음에 들어올 때 auth-state.js 의 guardConsent 가 동의
       화면으로 보낸다. 그때 받으면 된다. */
    const CONSENT_EPOCH = Date.parse("2026-08-20T00:00:00Z");

    let scanned = 0, deleted = 0, kept = 0, skipped = 0, capped = false, oldAccount = 0;

    let pageToken;
    do {
      const page = await admin.auth().listUsers(1000, pageToken);
      pageToken = page.pageToken;

      for (const u of page.users) {
        scanned++;
        const created = Date.parse(u.metadata.creationTime || "");
        if (!created || created > cutoff) { kept++; continue; }   // 유예 기간 안
        if (created < CONSENT_EPOCH) { oldAccount++; kept++; continue; }

        let snap;
        try {
          snap = await db.collection("users").doc(u.uid).get();
        } catch (e) {
          // 못 읽었으면 아무것도 하지 않는다. 다음 실행에서 다시 본다.
          skipped++;
          continue;
        }
        /* consents 가 있기만 하면 남긴다. 처음에는 agreedAt 까지 있어야
           남기게 썼는데, 그러면 기록이 반만 저장된 계정이 삭제 대상이 된다.
           애매할 때는 지우지 않는 쪽으로 기운다 — 잘못 남긴 계정은 나중에
           고칠 수 있지만 잘못 지운 계정은 못 돌린다. */
        const c = snap.exists ? (snap.data() || {}).consents : null;
        if (c) { kept++; continue; }

        if (deleted >= MAX_DELETE) { capped = true; skipped++; continue; }
        try {
          await admin.auth().deleteUser(u.uid);
          if (snap.exists) await snap.ref.delete();
          deleted++;
          console.log(`[purge] 삭제 ${u.uid} (생성 ${u.metadata.creationTime})`);
        } catch (e) {
          skipped++;
          console.warn(`[purge] 삭제 실패 ${u.uid}: ${e.code || e.message}`);
        }
      }
    } while (pageToken);

    console.log(`[purge] 훑음 ${scanned} · 삭제 ${deleted} · 유지 ${kept} ` +
                `(그중 제도 시행 전 계정 ${oldAccount}) · 건너뜀 ${skipped}`);
    if (capped) {
      console.warn(`[purge] ⚠️ 한 번 상한(${MAX_DELETE})에 걸렸다. 하루 대상이 이렇게 많은 것은 ` +
                   `정상이 아니다 — 조건이 틀렸는지 사람이 확인할 것.`);
    }
  }
);
