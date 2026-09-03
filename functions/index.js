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
/* 모닝 브리핑 워크플로를 깨우는 데 쓴다. 아래 wakeMorningBrief 주석 참고. */
const GH_DISPATCH_TOKEN = defineSecret("GH_DISPATCH_TOKEN");
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

/* ── 네이버가 받아 준 약관 동의 내역 ────────────────────────────────
   네이버 개발자센터의 '약관 1·2·3' 에 제목·URL·태그·필수/선택을 등록하면
   네이버 로그인 동의창이 그 약관들을 대신 보여 주고 동의를 받는다.
   카카오싱크와 같은 구조다.

   한동안 나는 '네이버는 약관 동의를 안 준다' 고 잘못 알고 있었다. 근거로
   삼은 것은 /v1/nid/me 응답에 약관 칸이 없다는 사실이었는데, 약관은 그
   응답이 아니라 별도 창구로 온다. 프로필 API 만 보고 없다고 단정한 것이
   틀렸다.

     GET https://openapi.naver.com/v1/nid/agreement
     Authorization: Bearer {access_token}

     { "result": "success",
       "agreementInfos": [ { "termCode": "privacy_20220929",
                             "clientId": "...",
                             "agreeDate": "..." }, ... ] }

   termCode 는 개발자센터에 적은 '약관 태그' 에 판 날짜가 붙은 값이다
   (태그 privacy → privacy_20220929). 그래서 아래에서 태그로 앞을 짚는다.

   실패해도 로그인을 막지 않는다 — 못 가져온 것과 동의하지 않은 것은 다른
   일이다. 못 가져오면 null 이고, 부르는 쪽이 지금까지의 방식으로 물러선다. */
async function naverAgreements(accessToken){
  try{
    const r = await asJson(await fetch("https://openapi.naver.com/v1/nid/agreement", {
      headers: { Authorization: `Bearer ${accessToken}` }
    }), "naver_agreement");
    /* 응답 모양을 눈으로 보기 전이라 두 자리를 다 본다. 겉이 바뀌어도
       목록만 찾으면 된다. */
    const list = Array.isArray(r.agreementInfos) ? r.agreementInfos
      : (r.response && Array.isArray(r.response.agreementInfos)) ? r.response.agreementInfos
      : null;
    if(!list){
      console.warn("[naver] agreement 응답에 agreementInfos 가 없다:",
        JSON.stringify(r).slice(0, 500));
      return null;
    }
    console.log("[naver] agreementInfos:",
      list.map(t => `${t.termCode}@${t.agreeDate || "?"}`).join(", ") || "(빈 목록)");
    return list;
  }catch(e){
    console.warn("[naver] agreement 조회 실패:", e && e.message);
    return null;
  }
}

/* 네이버가 준 약관 목록을 우리 항목으로 옮긴다.

   카카오와 다른 점이 하나 있다. 카카오는 항목마다 agreed 를 true/false 로
   주는데, 네이버는 '동의한 약관' 만 목록에 담아 준다. 그래서 목록에 있으면
   동의, 없으면 미동의다. 선택 약관(마케팅)을 체크하지 않으면 그 줄이 아예
   오지 않는다.

   ⚠️ 이 해석이 이 함수의 전부다. 만약 네이버가 미동의 항목까지 담아 보내는
      것으로 밝혀지면(agreed 같은 칸이 같이 온다면) 여기가 틀린다. 그래서
      항목에 그런 칸이 있으면 그 값을 우선하고, 없을 때만 '있으면 동의' 로
      읽는다. 원본은 그대로 저장하므로 나중에 고칠 수 있다. */
const NAVER_TAG_MATCH = {
  age14:     /age|14|연령|만14/i,
  terms:     /term|agree|tos|service|약관|이용/i,
  privacy:   /privacy|개인정보|수집/i,
  marketing: /market|adver|광고|수신|promo|benefit|혜택/i,
};

/* 네이버가 준 동의 시각을 밀리초로. 시간대 표시가 없으면 한국 시각으로 읽는다.

   ⚠️ 이걸 Date.parse 에 그대로 넘겼다가 동의 시각이 미래로 찍혔다. 가입은
      8/28 20:09 인데 동의는 8/29 02:48 로 남았다 — 정확히 9시간이다.

      네이버가 주는 값에는 시간대가 붙어 있지 않다("2026-08-28T17:48:33.062").
      Date.parse 는 시간대 없는 값을 그 기계의 지역 시각으로 읽는데, 우리
      함수는 UTC 로 도니 한국 시각 17:48 을 UTC 17:48(= 한국 02:48) 로
      읽어 버린다. 네이버는 한국 서비스이고 개발자센터도 한국 시각으로
      보여 주므로 KST 로 읽는 것이 맞다.

   Z 나 +09:00 같은 표시가 붙어 오면 그 값을 존중한다 — 네이버가 나중에
   형식을 바꿔도 우리가 9시간을 덧붙이지 않게. */
function parseNaverDate(v){
  const s = String(v || "").trim();
  if(!s) return NaN;
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/i.test(s);
  if(hasZone) return Date.parse(s);
  /* 'YYYY-MM-DD HH:MM:SS' 처럼 공백으로 갈라져 와도 받는다. */
  return Date.parse(s.replace(" ", "T") + "+09:00");
}

function mapNaverTerms(list){
  if(!Array.isArray(list)) return null;

  const agreedOf = (t) => {
    /* 네이버가 명시적인 동의 여부를 같이 준다면 그 값이 우선이다. */
    for(const k of ["agreed", "agree", "isAgree", "agreeYn"]){
      const v = t[k];
      if(v === true || v === false) return v;
      if(v === "Y" || v === "N") return v === "Y";
    }
    return true;                      // 목록에 있다 = 동의했다
  };

  const hit = (key) => list.find(t =>
    NAVER_TAG_MATCH[key].test(String(t.termCode || "")) && agreedOf(t));

  /* 필수 항목인데 그 태그가 목록에 없을 때 물러설 자리.

     ⚠️ 이게 없어서 로그인할 때마다 우리 동의 화면이 떴다. 개발자센터에
        등록된 약관이 terms·privacy·marketing 셋뿐이라 age14 태그가 오지
        않았고, 그러면 hit("age14") 가 undefined 라 age14:false 로 적혔다.
        consentStage 는 필수 세 항목을 모두 보므로 '동의 없음' 이고,
        guardConsent 가 매번 동의 화면으로 보냈다.

        false 는 '동의하지 않았다' 라는 뜻인데 실제로는 '묻지 않았다' 였다.
        모르는 것을 아니라고 적은 것이 틀렸다.

     물러설 근거는 이렇다. 네이버 동의 화면은 필수 약관에 모두 동의해야
     통과되므로, 목록이 하나라도 돌아왔다는 것은 등록된 필수 약관을 전부
     받았다는 뜻이다.

     age14 는 그중에서도 근거가 더 단단하다. 개발자센터의 '서비스 약관 정보'
     에 '만 14세 이상만 가입 가능' 이라는 설정이 있고, 우리 앱은 그것이 켜져
     있다. 네이버 안내를 그대로 옮기면 이렇다.

       '만 14세 이상만 가입 가능' 으로 체크한 경우 네이버 사용자의 연령
       정보를 체크하여 만 14세 미만 사용자는 서비스에 가입되지 않도록
       처리되며, 연령 정보가 없는 사용자는 동의 과정에서 [만 14세
       이상입니다] 항목을 체크하고 가입할 수 있도록 동의 항목을 노출합니다.

     즉 네이버 로그인을 통과했다는 것 자체가 만 14세 이상이라는 뜻이다.
     약관으로 받는 것이 아니라 네이버가 문에서 거른다.

     ⚠️ 그래서 agreementInfos 에 age14 는 오지 않는 것이 정상이다. 태그를
        age14 로 약관을 하나 더 만들 필요가 없다 — 한동안 그렇게 하시라고
        잘못 안내했다. 대신 개발자센터에서 저 체크를 끄면 이 근거가 무너지니
        건드리지 말 것.

     마케팅은 물러서지 않는다. 선택 항목이라 '통과했으니 동의했겠거니' 가
     성립하지 않는다. 없으면 미동의다. */
  const gotAny = list.some(agreedOf);
  const pick = (key) => {
    if(hit(key)) return true;
    if(gotAny) console.log(`[naver] ${key} 약관이 없어 동의 화면 통과로 물러선다.`);
    return gotAny;
  };

  const mk = hit("marketing");
  if(!list.length){
    console.warn("[naver] agreementInfos 가 비어 있다 — 약관 등록 상태를 확인할 것.");
  }else if(!mk){
    console.log("[naver] 마케팅 약관이 목록에 없다(= 미동의). 받은 termCode:",
      list.map(t => t.termCode).join(", "));
  }

  /* 실제 동의 시각. 여럿이면 가장 늦은 것 — 마지막으로 동의를 마친 순간. */
  let agreedAt = null;
  for(const t of list){
    if(!agreedOf(t) || !t.agreeDate) continue;
    const ms = parseNaverDate(t.agreeDate);
    if(!ms || Number.isNaN(ms)) continue;
    /* 앞선 시각은 버린다. 형식을 잘못 읽으면 미래로 튀는데, 미래에 받은
       동의라는 것은 있을 수 없다. 그런 값을 적느니 없는 편이 낫다 —
       부르는 쪽이 서버 시각으로 물러선다. */
    if(ms > Date.now() + 60000){
      console.warn("[naver] agreeDate 가 미래다. 버린다:", t.termCode, t.agreeDate);
      continue;
    }
    if(!agreedAt || ms > agreedAt) agreedAt = ms;
  }

  /* 마케팅에 동의한 시각. 다른 항목과 따로 들고 나간다 — 재가입 때 '이
     동의가 언제 것인가' 를 마케팅만 따로 따져야 하기 때문이다. */
  const mkMs = mk && mk.agreeDate ? parseNaverDate(mk.agreeDate) : NaN;

  return {
    age14: pick("age14"),
    terms: pick("terms"),
    privacy: pick("privacy"),
    marketing: !!mk,
    marketingAt: (mkMs && !Number.isNaN(mkMs)) ? new Date(mkMs) : null,
    marketingKnown: true,             // 목록을 받았다는 것 자체가 답이다
    agreedAt: agreedAt ? new Date(agreedAt) : null,
    raw: list.map(t => ({
      termCode: String(t.termCode || ""),
      agreeDate: t.agreeDate || null,
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
/* ── 네이버 연결 끊기 ────────────────────────────────────────────
   카카오에는 탈퇴할 때 unlink 를 걸어 두고 네이버에는 걸지 않았다. 그
   하나가 오늘 겪은 네이버 문제 대부분의 뿌리다.

   연결이 남아 있으면 네이버는 그 사람의 동의 기록을 계속 들고 있다.
   그래서 다시 가입할 때

     · 동의 화면이 안 뜨거나(그래서 auth_type=reprompt 를 붙였고)
     · agreeDate 가 처음 동의한 날 그대로 오고(그래서 시각 판정이 어긋났고)
     · 마케팅을 껐는데 예전에 켠 기록이 그대로 실려 왔다

   전부 '연결이 안 끊긴다' 는 한 가지에서 나왔다. 증상마다 따로 막다가
   서로 부딪혀 더 큰 문제를 만들었다. 끊는 것이 뿌리를 없애는 길이다.

   카카오와 다른 점은 어드민 키가 없다는 것이다. 네이버는 그 사람의 접근
   토큰이 있어야 끊어 준다.

     GET https://nid.naver.com/oauth2.0/token
         ?grant_type=delete&client_id=…&client_secret=…
         &access_token=…&service_provider=NAVER

   접근 토큰은 한 시간이면 만료되므로 로그인할 때 갱신 토큰을 받아 두었다가
   탈퇴하는 순간 새 접근 토큰으로 바꿔서 쓴다. 갱신 토큰은 서버만 읽는
   자리(providerTokens)에 둔다 — users 문서는 본인이 읽을 수 있어서 거기에
   두면 브라우저로 새어 나간다.

   실패해도 탈퇴는 계속한다. 네이버 쪽이 안 끊겼다고 우리 쪽 탈퇴를 막으면
   사용자는 계정을 못 지운다 — 그게 더 나쁘다. 대신 결과를 기록에 남기고,
   못 끊은 사람은 아래 마케팅 문턱이 계속 지켜 준다. */
async function naverUnlink(uid){
  const db = admin.firestore();
  const ref = db.doc(`providerTokens/${uid}`);
  let refreshToken = "";
  try{
    refreshToken = ((await ref.get()).data() || {}).refreshToken || "";
  }catch(e){
    console.warn("[naver] 갱신 토큰 조회 실패", uid, e && e.message);
  }
  if(!refreshToken){
    console.warn("[naver] 갱신 토큰이 없어 연결 끊기를 건너뛴다:", uid);
    return false;
  }

  const id = (NAVER_CLIENT_ID.value() || "").trim();
  const secret = (NAVER_CLIENT_SECRET.value() || "").trim();
  let ok = false;
  try{
    /* 접근 토큰을 새로 받는다. 로그인 때 받은 것은 이미 만료됐다. */
    const r = await asJson(await fetch("https://nid.naver.com/oauth2.0/token?" +
      new URLSearchParams({
        grant_type: "refresh_token",
        client_id: id, client_secret: secret, refresh_token: refreshToken
      })), "naver_refresh");
    const at = r.access_token;
    if(!at) throw new Error("no_access_token");

    const d = await asJson(await fetch("https://nid.naver.com/oauth2.0/token?" +
      new URLSearchParams({
        grant_type: "delete",
        client_id: id, client_secret: secret,
        access_token: at, service_provider: "NAVER"
      })), "naver_delete");
    ok = d.result === "success";
    console.log("[naver] 연결 끊기", uid, JSON.stringify(d).slice(0, 200));
  }catch(e){
    console.warn("[naver] 연결 끊기 실패", uid, e && e.message);
  }
  /* 성공이든 실패든 토큰은 들고 있지 않는다. 탈퇴한 사람의 자격증명을
     남겨 둘 이유가 없다. */
  try{ await ref.delete(); }catch(e){}
  return ok;
}

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

  /* 네이버가 약관 동의를 무슨 이름으로 주는지 코드가 미리 알 수 없다.
     카카오는 service_terms 라는 정해진 자리가 있었는데 네이버는 그렇지
     않다 — 개발자센터에 등록한 동의항목이 응답 어디에 어떤 이름으로
     실리는지 실제 응답을 봐야 안다.

     짐작으로 매핑을 짜면 카카오 태그 때처럼 어긋난다. 그래서 받은 것을
     그대로 들고 온다. 다만 프로필 정보는 값까지 나를 이유가 없으므로
     이름만 남긴다 — 우리가 찾는 것은 '약관' 쪽 칸이다. */
  const PROFILE_FIELDS = new Set([
    "id", "email", "name", "nickname", "profile_image", "gender", "age",
    "birthday", "birthyear", "mobile", "mobile_e164",
  ]);
  const raw = {};
  for (const k of Object.keys(r)) {
    raw[k] = PROFILE_FIELDS.has(k) ? "(프로필 값 생략)" : r[k];
  }
  console.log("[naver] /v1/nid/me 응답 칸:", Object.keys(r).join(", "));
  console.log("[naver] 프로필 밖 칸:", JSON.stringify(
    Object.fromEntries(Object.entries(raw).filter(([k]) => !PROFILE_FIELDS.has(k)))).slice(0, 800));

  return {
    id: String(r.id),
    email: r.email || null,
    name: r.name || r.nickname || "",
    photo: r.profile_image || null,
    raw,
    /* 약관 동의 내역은 프로필과 다른 창구에서 온다. 카카오와 같은 자리에
       담아 아래 처리를 하나로 쓴다. */
    terms: await naverAgreements(tok.access_token),
    /* 탈퇴할 때 연결을 끊는 데 쓴다. 그때는 접근 토큰이 이미 만료돼 있으므로
       갱신 토큰을 들고 있어야 한다. naverUnlink 참고. */
    refreshToken: tok.refresh_token || null
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
    /* 이 인가가 동의 화면을 거쳐 왔는가(네이버). 아래 두 곳에서 쓴다. */
    const reprompted = (req.data || {}).reprompt === true;

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

    /* 여기 있던 needsConsent 되돌리기를 없앴다.

       네이버 계정을 만들어야 하는데 동의 화면을 거치지 않았으면 클라이언트를
       한 번 되돌려 보내, auth_type=reprompt 를 붙여 다시 오게 했다. 탈퇴해도
       네이버 연결이 남아 동의 화면이 안 뜨던 시절의 대응이다.

       이제 탈퇴할 때 연결을 끊으므로(naverUnlink) 다음 로그인은 첫 연결이고,
       네이버가 알아서 동의 화면을 띄운다. 그 상태에서 이 되돌리기를 남겨
       두면 동의 화면을 두 번 보게 된다 — 1차에서 이미 동의했는데 '기록이
       없다' 며 2차를 요구하기 때문이다. 실제로 그렇게 됐다.

       뿌리를 고치면 그 위에 얹었던 땜질은 걷어내야 한다. 남겨 두면 그 땜질이
       새 증상이 된다. */
    /* 새 소셜 계정을 만들기 전에, 같은 이메일을 쓰는 계정이 이미 있는지 본다.
       있으면 만들지 않는다 — 만들었다 지우는 것보다 애초에 안 만드는 쪽이
       확실하다. 기존 사용자(exists)는 검사하지 않는다. 이미 쓰고 있는
       사람을 뒤늦게 막으면 로그인이 통째로 끊긴다. */
    if(!exists && p.email){
      const other = await findOtherAccountByEmail(admin.firestore(), p.email, uid);
      if(other){
        throw new HttpsError("already-exists",
          `이 주소는 이미 ${other.label}으로 등록되어 있습니다. 그 방법으로 로그인하여 주시기 바랍니다.`, { method: other.method });
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

       네이버도 같다. 개발자센터 '약관 1·2·3' 에 제목·URL·태그·필수/선택을
       등록해 두면 네이버 로그인 동의창이 그 약관들을 대신 보여 주고, 동의
       내역은 /v1/nid/agreement 로 읽어 온다. 창구 이름과 응답 모양만 다를
       뿐 카카오싱크와 하는 일이 같다. */
    const db = admin.firestore();
    const now = admin.firestore.FieldValue.serverTimestamp();
    /* 제공자가 대신 받아 준 동의 내역. 카카오는 service_terms, 네이버는
       agreement 창구에서 온다. 못 읽었으면 null 이고, 그때는 아래에서 기존
       기록을 건드리지 않는다.

       두 곳의 응답 모양은 다르지만(카카오는 항목마다 agreed, 네이버는 동의한
       것만 목록) map* 함수가 같은 모양으로 맞춰 주므로 여기서부터는 하나로
       다룬다. */
    const kt = provider === "kakao" ? mapKakaoTerms(p.terms)
      : provider === "naver" ? mapNaverTerms(p.terms)
      : null;
    /* 어느 화면에서 받은 동의인지. 기록에 남는 이름이다. */
    const ktMethod = provider === "kakao" ? "kakao-sync" : "naver-consent";

    /* 네이버 동의 내역을 못 읽었을 때의 물러선 자리.

       전에는 이 자리가 유일한 길이었다 — '네이버는 약관을 안 준다' 고 잘못
       알았기 때문이다. 이제는 agreement 창구가 먼저고, 그것이 실패했을 때만
       여기로 온다.

       근거는 '동의 화면을 거친 인가' 다. reprompted 는 옛 클라이언트가 아직
       보내는 값이고(그 왕복은 없앴다), 참이면 방금 그 화면을 보고 눌렀다는
       뜻이라 그대로 인정한다. 새 클라이언트에서는 늘 거짓이므로 이 자리는
       사실상 쓰이지 않는다 — agreement 를 못 읽었을 때 우리 동의 화면으로
       보내는 쪽(staleConsent)이 맡는다.

       ⚠️ 필수 세 항목을 true 로 적는 것은, 네이버 개발자센터에 우리 이용약관·
          개인정보 수집·이용이 '필수' 동의항목으로 등록돼 있고 '만 14세
          이상만 가입 가능' 이 켜져 있다는 전제 위에 선다. 내리면 거짓이 된다.

       마케팅은 다르다. 선택 항목이라 사람마다 다른데, 목록을 못 읽었으면
       알 길이 없다. 모르는 것을 true 로 적으면 동의하지 않은 사람에게 광고를
       보내게 된다. false 로 두고 설정 화면에서 본인이 켜게 한다. */
    const naverConsent = provider === "naver" && reprompted && !kt;
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
    /* 제공자가 알려 준 동의 시각이 탈퇴보다 앞서 그대로 적을 수 없을 때 참.
       기록에 '계정 생성일보다 앞선 동의일' 을 남기지 않으려고 본다. */
    let providerAgreedAtStale = false;

    /* 마지막으로 탈퇴한 시각. 제공자가 준 동의가 그보다 앞서면 옛 계약의
       동의라 새 계정에 붙일 수 없다.

       ⚠️ 이 조회를 !exists 안에 두었던 것이 문제였다. 가입할 때는 제대로
          걸러 놓고, 그 뒤 그냥 로그인할 때는 걸러 주지 않아서 아래 '기존
          회원 맞추기' 가 다시 옛 값으로 덮었다. 마케팅을 끄고 가입했는데
          다음 로그인에 저절로 켜지던 것이 이것이다.

          탈퇴 여부는 가입이든 로그인이든 똑같이 물어야 한다. 조회 한 번이
          더 드는 것보다, 동의하지 않은 사람에게 광고가 나가는 쪽이 훨씬
          비싸다. */
    let withdrawnAt = 0;
    /* 그 탈퇴에서 제공자 연결을 실제로 끊었는가. deleteAccount 가
       providerUnlinked 로 남긴다. 끊었다면 다음 로그인은 첫 연결이므로
       제공자가 동의 화면을 다시 띄웠다는 뜻이다. */
    let unlinkedAtWithdraw = false;
    try{
      const w = await db.collection("consentEvents")
        .where("uid", "==", uid).where("kind", "==", "withdraw").limit(10).get();
      w.forEach(d => {
        const data = d.data() || {};
        const t = data.at;
        const ms = t && t.toDate ? t.toDate().getTime() : 0;
        if(ms > withdrawnAt){
          withdrawnAt = ms;
          unlinkedAtWithdraw = data.providerUnlinked === true;
        }
      });
    }catch(e){
      console.warn("[social] 탈퇴 이력 조회 실패", uid, e && e.message);
      withdrawnAt = -1;                         // 모르면 아래에서 안전한 쪽으로
    }

    /* 마케팅은 따로 따진다 — 탈퇴 전에 받은 동의를 새 계정에 붙이면 안 된다.

       네이버는 탈퇴해도 자기 쪽 동의 기록을 지우지 않는다. 그래서
       agreementInfos 에 예전에 켰던 marketing 줄이 그대로 실려 오고, 그것을
       '이번에 동의했다' 로 읽으면 끄고 가입한 사람이 동의자로 기록된다.

       필수 항목은 이렇게 따지지 않는다. 그쪽은 reprompt 로 방금 동의 화면을
       거쳤다는 것이 근거이고, 필수라 통과 자체가 동의를 뜻한다. 마케팅은
       선택이라 그 논리가 서지 않는다 — 화면을 봤다는 사실이 무엇을 눌렀는지는
       알려 주지 않는다.

       그래서 탈퇴 뒤에 찍힌 동의만 인정한다. 시각을 모르면 인정하지 않는다.
       동의하지 않은 사람에게 광고를 보내는 것은 되돌릴 수 없고(정보통신망법
       제50조), 본인은 설정 화면에서 언제든 켤 수 있다.

       가입·로그인 양쪽에서 같이 돈다. 아래 '기존 회원 맞추기' 가 이 값을
       그대로 쓰므로, 여기서 한 번 거르면 두 경로가 같은 답을 본다. */
    /* ⚠️ unlinkedAtWithdraw 를 여기에도 봐야 한다. 바로 아래 재동의 판정에는
          넣고 이 문턱에는 넣지 않아서, 마케팅을 켜고 가입했는데 꺼진 채로
          기록됐다. 같은 근거를 쓰는 자리가 둘인데 한쪽만 고쳤다.

          연결을 실제로 끊었으면 이번 연결은 첫 연결이다. 첫 연결에는 '이전'
          이라는 것이 없으므로, 제공자가 지금 주는 목록이 곧 방금 받은 답이다.
          날짜를 견줄 이유가 없다.

          끊기가 실패했을 때만 날짜를 본다 — 그때는 옛 기록이 그대로 실려
          오므로 지금 답인지 알 수 없고, 모르면 켜지 않는다. */
    if(kt && kt.marketing && withdrawnAt !== 0 && !unlinkedAtWithdraw){
      const mAt = kt.marketingAt ? kt.marketingAt.getTime() : 0;
      if(withdrawnAt < 0 || !mAt || mAt <= withdrawnAt){
        console.log(`[naver] ${uid} — 마케팅 동의가 탈퇴 이전 것이라 쓰지 않는다`,
          `(동의 ${kt.marketingAt ? kt.marketingAt.toISOString() : "시각 모름"},`,
          `탈퇴 ${withdrawnAt})`);
        kt.marketing = false;
        kt.marketingAt = null;
      }
    }
    if(kt){
      console.log(`[naver] ${uid} 마케팅 판정 —`,
        `제공자 ${kt.marketing}`,
        `(시각 ${kt.marketingAt ? kt.marketingAt.toISOString() : "없음"})`,
        `탈퇴 ${withdrawnAt}`, `연결끊김 ${unlinkedAtWithdraw}`);
    }

    if(!exists){
      if(kt && kt.agreedAt && withdrawnAt > 0 && kt.agreedAt.getTime() <= withdrawnAt){
        providerAgreedAtStale = true;
      }

      /* 제공자가 '언제 동의했는지' 를 알려 준 시각.

         reprompt 를 맨 앞에 둔다. 그 값이 참이면 방금 제공자의 동의 화면을
         보고 눌렀다는 뜻이고, 그건 어떤 날짜보다도 확실한 근거다.

         이 줄이 없어서 재가입이 통째로 막혔다. 네이버는 탈퇴해도 자기 쪽
         동의 기록을 지우지 않는다 — 동의 화면을 다시 띄워 눌러도 agreeDate
         는 처음 동의한 날 그대로 온다. 그 날짜를 탈퇴 시각과 견주니 늘
         '옛 동의' 로 판정됐고, consents 를 안 써서 우리 동의 화면이 또
         떴다. 제공자 화면과 우리 화면을 둘 다 보게 되는 그 증상이다.

         날짜가 오지 않거나(파싱 실패 포함) 탈퇴 이전이어도 마찬가지다.
         reprompt 를 거쳤으면 방금 받은 동의다.

         unlinkedAtWithdraw 도 같은 자리에 둔다. 탈퇴할 때 제공자 연결을
         실제로 끊었다면 다음 로그인은 첫 연결이고, 그러면 제공자가 동의
         화면을 반드시 띄운다 — 여기 도달했다는 것은 그 화면을 보고 눌렀다는
         뜻이다. 제공자가 알려 주는 날짜가 무엇이든 상관없다.

         ⚠️ 이 줄이 없어서 우리 동의 화면이 떴다. reprompt 왕복을 걷어내면서
            '방금 동의 화면을 봤다' 는 근거가 통째로 사라졌는데, 그 자리를
            대신할 근거(연결을 끊었다)를 넣지 않았다. 그래서 판정이 늘
            제공자 날짜로 떨어졌고, 그 날짜는 옛 것이라 '옛 동의' 가 됐다.

            땜질을 걷어낼 때는 그 땜질이 대신하던 일을 무엇이 맡을지까지
            같이 정해야 한다. */
      const providerConsentAt =
        reprompted ? Date.now()               // 방금 동의 화면을 보고 눌렀다
        : unlinkedAtWithdraw ? Date.now()     // 연결을 끊었으니 이번이 첫 연결이다
        : kt && kt.agreedAt ? kt.agreedAt.getTime()
        : naverConsent ? Date.now()
        : 0;
      staleConsent = isStaleProviderConsent(withdrawnAt, providerConsentAt);
      console.log(`[social] 재가입 판정 ${uid} — 탈퇴 ${withdrawnAt}`,
        `제공자동의 ${kt && kt.agreedAt ? kt.agreedAt.toISOString() : "없음"}`,
        `reprompt ${reprompted}`, `→ ${staleConsent ? "다시 받는다" : "그대로 쓴다"}`);
    }

    const patch = { signupMethod: provider, updatedAt: now };
    if(p.email) patch.email = String(p.email).trim().toLowerCase();
    if(!exists){
      if(!p.email) patch.email = null;
      patch.createdAt = now;
      /* 네이버 프로필 응답에 어떤 칸이 왔는지 남긴다. 값은 빼고 칸 이름만
         남으므로 개인정보가 아니다. 약관은 여기 오지 않는다 — 그건 위의
         agreement 창구에서 따로 받아 consents.kakaoTerms 에 담긴다. */
      if(provider === "naver" && p.raw) patch.providerRaw = p.raw;
      if(staleConsent){
        /* consents 를 쓰지 않는다. 그러면 auth-state.js 의 guardConsent 가
           다음 화면에서 동의 페이지로 보낸다 — 구글과 같은 길이다. */
      } else {
        /* 적을 동의 시각. 사용자가 실제로 누른 시각이 우리 서버 시각보다
           맞다 — 다만 그 값이 탈퇴보다 앞서면 쓸 수 없다. 네이버는 탈퇴해도
           자기 쪽 동의 기록을 지우지 않아서 처음 동의한 날이 그대로 온다.
           그걸 그대로 적으면 계정 생성일보다 앞선 동의일이 남는다. */
        const ktAt = (kt && kt.agreedAt && !providerAgreedAtStale) ? kt.agreedAt : now;
        patch.consents = kt ? {
          version: CONSENT_VERSION,
          method: ktMethod,             // 제공자 동의 화면에서 받은 동의
          age14: kt.age14, terms: kt.terms, privacy: kt.privacy,
          marketing: kt.marketing,
          kakaoTerms: kt.raw,           // 받은 그대로. 매핑이 틀려도 자료는 남는다
          agreedAt: ktAt
        } : naverConsent ? {
          version: CONSENT_VERSION,
          method: "naver-consent",      // 네이버 동의 화면에서 받은 동의
          age14: true, terms: true, privacy: true,
          marketing: false,             // 목록을 못 읽었다. 설정에서 켠다
          agreedAt: now
        } : {
          version: CONSENT_VERSION,
          method: "signup-notice",
          age14: true, terms: true, privacy: true,
          marketing: false,             // 선택 — 설정 페이지에서 켠다
          agreedAt: now
        };
        patch.marketingAt = (kt && kt.marketing) ? ktAt : null;
      }
    } else if(kt){
      /* 이미 있는 회원. 마케팅만 맞춰 준다. 그리고 우리 쪽에서 한 번도
         만진 적이 없을 때만이다.

         켜고 끈 기록(marketingAt·marketingOffAt)이 있으면 그 사람은 우리
         설정 화면에서 자기 뜻을 밝힌 것이다. 제공자 값으로 덮으면 철회를
         무시하는 셈이 된다 — 로그인할 때마다 다시 켜진다.

         반대로 만진 적이 없는 회원은 우리가 marketing:false 를 박아 둔
         탓에 미동의로 남아 있다. 그 사람들이 여기서 제자리를 찾는다. */
      const cur = (snapBefore && snapBefore.consents) || {};
      const touched = !!(snapBefore && (snapBefore.marketingAt || snapBefore.marketingOffAt));
      const needsFix = !touched && cur.marketing !== kt.marketing;

      /* 필수 항목이 false 로 굳어 버린 기록을 되살린다.

         ⚠️ 이걸 안 해서, 한 번 잘못 적힌 계정이 로그인할 때마다 동의 화면을
            봤다. age14 태그가 개발자센터에 없던 탓에 age14:false 로 적혔고,
            그 뒤로는 제공자 값이 맞게 와도 여기서 고쳐 주지 않았다.

         올리기만 한다(false → true). 내리지는 않는다 — 태그를 잘못 짚었을 때
         멀쩡한 동의 기록을 false 로 덮는 쪽이 훨씬 나쁘다. */
      const raise = {};
      for(const k of ["age14", "terms", "privacy"]){
        if(kt[k] === true && cur[k] !== true) raise[k] = true;
      }
      const needsRaise = Object.keys(raise).length > 0;
      if(needsRaise){
        console.log(`[social] ${uid} — 필수 항목을 되살린다:`, Object.keys(raise).join(", "));
      }
      /* 고칠 기록이 실제로 있을 때만 손댄다.

         ⚠️ 이 조건이 없어서 무한 루프가 났다. 계정은 있는데 동의 기록이
            없는 상태(위에서 staleConsent 로 consents 를 안 쓴 계정)에서
            여기 들어오면 cur 가 {} 인데, 아래 Object.assign 이 그 위에
            kakaoTerms 와 method 만 얹어 반쪽짜리 기록을 만든다.

              consents: { kakaoTerms: [...], method: "naver-consent" }

            age14·terms·privacy·version·agreedAt 이 없다. consentStage 는
            필수 세 항목을 보므로 'none' 이고, guardConsent 가 동의 화면으로
            보낸다. 동의를 눌러 제대로 채워 넣어도 다음 로그인에서 이 줄이
            또 반쪽을 얹는다 — 나가지지 않는다.

         기록이 없는 계정은 여기서 건드릴 것이 없다. recordSignupConsent 가
         동의 화면에서 통째로 쓴다. */
      if(!cur.agreedAt){
        console.log(`[social] ${uid} — 동의 기록이 없어 제공자 약관 맞추기를 건너뛴다`);
      } else if(needsFix || needsRaise || !cur.kakaoTerms){
        /* 받은 방식도 실제에 맞춘다. 여태 'signup-notice' 로 적혀 있었는데
           그 고지 문구는 화면에서 지운 지 오래다 — 이 사람들이 실제로 본
           것은 제공자의 동의 화면이다. 처음 기록은 consentEvents 의
           'signup' 사건에 그대로 남아 있으므로 잃는 것은 없다.

           필수 세 항목은 올리기만 한다(raise). 내리지 않는다 — 태그를 잘못
           짚었을 때 멀쩡한 동의 기록을 false 로 덮는 쪽이 훨씬 나쁘다.
           근거는 아래 원본으로 붙는다.

           kakaoTerms 라는 이름은 카카오만 있던 시절에 지었다. 지금은 네이버
           원본([{termCode, agreeDate}])도 여기 들어간다 — 이름을 바꾸려면
           이미 쌓인 문서를 옮겨야 해서 두었다. 화면에는 '제공자 약관' 으로
           보인다. */
        patch.consents = Object.assign({}, cur, raise, {
          kakaoTerms: kt.raw,
          method: ktMethod,
        });
        if(needsFix){
          patch.consents.marketing = kt.marketing;
          patch.marketingAt = kt.marketing ? (kt.agreedAt || now) : null;
        }
        syncedTerms = needsFix ? "marketing" : needsRaise ? "required" : "terms";
      }
    }
    try{
      await db.collection("users").doc(uid).set(patch, { merge: true });
    }catch(e){
      // 새 가입인데 기록을 못 남겼으면 계정도 남기지 않는다. 반쪽짜리 가입을 두지 않는다.
      if(!exists){ try{ await admin.auth().deleteUser(uid); }catch(_){} }
      throw new HttpsError("internal", `user_doc_save_failed: ${e.code || e.message}`);
    }

    /* 갱신 토큰은 따로 둔다 — 탈퇴할 때 네이버 연결을 끊는 데만 쓴다.

       users 문서에 두지 않는 이유는 그 문서를 본인이 읽을 수 있기 때문이다
       (설정 화면이 마케팅 수신 여부를 읽어야 해서 열어 두었다). 자격증명을
       거기 두면 브라우저로 새어 나간다. providerTokens 는 규칙으로 읽기·
       쓰기를 다 막아 두어 서버만 닿는다.

       실패해도 로그인을 막지 않는다. 못 저장하면 탈퇴할 때 연결을 못 끊을
       뿐이고, 그때는 마케팅 문턱이 대신 지켜 준다. */
    if(provider === "naver" && p.refreshToken){
      try{
        await db.doc(`providerTokens/${uid}`).set({
          provider: "naver",
          refreshToken: p.refreshToken,
          updatedAt: now
        }, { merge: true });
      }catch(e){
        console.warn("[naver] 갱신 토큰 저장 실패", uid, e && e.message);
      }
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
    subject: "KOSAI 이메일 주소 인증 안내",
    html: mailLayout({ lang, heading: "이메일 주소 인증",
      intro: `${hi}KOSAI 가입을 환영합니다. 아래 버튼을 눌러 이메일 인증을 완료하면 모든 기능을 이용하실 수 있습니다.`,
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
    html: mailLayout({ lang, heading: "비밀번호 재설정",
      intro: "비밀번호 재설정 요청을 받았습니다. 아래 버튼을 눌러 새 비밀번호를 설정하여 주시기 바랍니다.",
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
      subject: "[KOSAI] Consent to our Terms of Service and privacy notice",
      html: mailLayout({ lang, heading: "Consent to our Terms of Service and privacy notice",
        intro: "Dear Member,<br><br>" +
               "Thank you for your continued use of our service.<br><br>" +
               "Our records indicate that you registered with us before our consent process was introduced, " +
               "and that we do not hold your agreement to our Terms of Service or to the collection and use " +
               "of your personal data. We are therefore writing to request your consent, in accordance with " +
               "Articles 15 and 22 of the Personal Information Protection Act.<br><br>" +
               "Signing in through the button below will display the consent screen. Once you have accepted " +
               "the required items, you may continue to use the service exactly as before. The process takes " +
               "around ten seconds, and your account, watchlist and settings remain entirely unchanged. " +
               "Marketing messages are optional, and declining them places no restriction whatsoever on your " +
               "use of the service.<br><br>" +
               "We appreciate your kind cooperation.",
        btnText: "Go to the consent screen", link,
        outro: "This message is a service notice concerning your account and is not a commercial advertisement under the Act on Promotion of Information and Communications Network Utilization and Information Protection. For enquiries, please contact hello@kosai.kr." })
    };
  }
  return {
    subject: "[KOSAI] 이용약관 및 개인정보 수집·이용 동의 안내",
    html: mailLayout({ lang, heading: "이용약관 및 개인정보 수집·이용 동의 안내",
      intro: "안녕하십니까. KOSAI입니다.<br><br>" +
             "평소 저희 서비스를 이용해 주시어 깊이 감사드립니다.<br><br>" +
             "확인 결과 회원님께서는 당사가 동의 절차를 도입하기 이전에 가입하신 회원으로, " +
             "이용약관 및 개인정보 수집·이용에 대한 동의 내역이 확인되지 않고 있습니다. " +
             "이에 「개인정보 보호법」 제15조 및 제22조에 근거하여 회원님의 동의를 요청드리고자 안내 말씀드립니다.<br><br>" +
             "아래 버튼을 통해 로그인하시면 동의 화면이 표시되며, 필수 항목에 동의하신 후에는 " +
             "기존과 동일하게 서비스를 이용하실 수 있습니다. 소요 시간은 10초 내외이며, " +
             "회원님의 계정 정보와 워치리스트, 각종 설정은 변경 없이 그대로 유지됩니다. " +
             "마케팅 정보 수신은 선택 사항으로, 동의하지 않으시더라도 서비스 이용에는 어떠한 제한도 없습니다.<br><br>" +
             "번거로우시더라도 협조하여 주시면 감사하겠습니다.",
      btnText: "동의 화면으로 이동", link,
      outro: "본 메일은 「정보통신망 이용촉진 및 정보보호 등에 관한 법률」상 광고성 정보가 아닌, 서비스 이용에 관한 안내입니다. 문의사항은 hello@kosai.kr로 연락 주시기 바랍니다." })
  };
}

/* ── 마케팅 수신 동의 2년 재확인 메일 ────────────────────────────
   개인정보처리방침에 "동의를 받은 날부터 2년마다 수신 동의 여부를 확인
   합니다" 라고 적어 두었다. 적어 놓기만 하고 확인할 수단이 없으면 그건
   지키지 않는 약속이다.

   근거는 정보통신망법 시행령 제62조의3 이고, 알려야 하는 것이 정해져 있다.

     ① 전송자의 명칭
     ② 수신동의 날짜와 그 사실
     ③ 수신동의에 대한 유지 또는 철회 의사표시 방법

   셋을 본문에 그대로 담는다. 특히 ②는 사람마다 다르므로 인자로 받는다 —
   "언제 동의하셨습니다" 를 못 적으면 이 메일은 요건을 못 채운다.

   ⚠️ 답이 없으면 동의가 유지된 것으로 본다(같은 조). 그러니 이 메일은
      다시 받아 내려는 것이 아니라 알리고 철회할 길을 열어 두는 것이다.
      무응답을 미동의로 바꾸면 오히려 법이 정한 것과 달라진다. */
/* 기한보다 며칠 앞서 보낼 것인가.

   조문이 정한 것은 '같은 날 전까지' 이므로 늦으면 안 되고 앞당기는 것은
   막지 않는다. 하루만 두면 그날 함수가 한 번 실패했을 때 곧장 기한을
   넘긴다. 이레를 두면 여섯 번 더 기회가 있다. */
const RECHECK_LEAD_DAYS = 7;

/* 동의일로부터 2년이 되는 날(한국 시각 자정, ms).

   ⚠️ 730일을 더하면 안 된다. 조문이 '매 2년이 되는 해의 수신동의를 받은
      날과 같은 날' 이라고 달력으로 정해 두었는데, 그 사이에 윤년이 끼면
      730일과 하루가 어긋난다.

   2월 29일에 동의한 경우 2년 뒤에는 그 날짜가 없다. 3월 1일로 밀면 기한을
   하루 넘기므로 2월 28일로 당긴다 — 애매하면 앞당기는 쪽이다. */
function recheckDueAt(ms){
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit"
  }).formatToParts(new Date(ms));
  const get = (t) => Number(parts.find(p => p.type === t).value);
  const y = get("year") + 2, m = get("month"), d = get("day");
  /* 그 달의 마지막 날을 넘지 않게 자른다(2/29 → 2/28). */
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const day = Math.min(d, last);
  /* 한국 시각 자정 = UTC 로 전날 15:00. */
  return Date.UTC(y, m - 1, day) - 9 * 3600 * 1000;
}

function marketingRecheckMail(lang, agreedAtText){
  const link = SITE_URL + "/Settings.html";
  const en = lang === "en";
  if(en){
    return {
      subject: "[KOSAI] Biennial confirmation of your marketing consent",
      html: mailLayout({ lang, heading: "Confirming your marketing consent",
        intro: "Hello,<br><br>" +
               "KOSAI is required to reconfirm marketing consent every two years " +
               "under Article 62-3 of the Enforcement Decree of the Network Act. " +
               "We are writing to confirm the following.<br><br>" +
               "&middot; Sender: KOSAI<br>" +
               `&middot; You consented to receive marketing messages on <b>${esc(agreedAtText)}</b>, and that consent remains in effect.<br>` +
               "&middot; To withdraw, open Settings and switch off <b>Marketing messages</b>. You may also reply to this email.<br><br>" +
               "If you wish to continue receiving them, no action is needed. " +
               "Withdrawing places no restriction on your use of the service.",
        btnText: "Open settings", link,
        outro: "This message is a statutory confirmation notice concerning your consent, not a commercial advertisement. For enquiries, please contact hello@kosai.kr." })
    };
  }
  return {
    subject: "[KOSAI] 마케팅 정보 수신 동의 확인 안내",
    html: mailLayout({ lang, heading: "마케팅 정보 수신 동의 확인",
      intro: "안녕하세요, KOSAI입니다.<br><br>" +
             "「정보통신망 이용촉진 및 정보보호 등에 관한 법률 시행령」 제62조의3에 따라 " +
             "수신 동의 여부를 2년마다 확인해 드리고 있습니다. 아래 내용을 안내드립니다.<br><br>" +
             "&middot; 전송자: KOSAI<br>" +
             `&middot; 회원님은 <b>${esc(agreedAtText)}</b>에 마케팅 정보 수신에 동의하셨으며, 현재 동의가 유지되고 있습니다.<br>` +
             "&middot; 철회 방법: 설정 화면에서 <b>마케팅 정보 수신</b>을 끄시면 즉시 철회됩니다. 본 메일에 회신하셔도 됩니다.<br><br>" +
             "계속 받아 보길 원하시면 따로 하실 일은 없습니다. " +
             "철회하셔도 서비스 이용에는 아무런 제한이 없습니다.",
      btnText: "설정 화면 열기", link,
      outro: "본 메일은 수신 동의 확인을 위한 법정 안내이며 광고성 정보가 아닙니다. 문의사항은 hello@kosai.kr로 연락 주시기 바랍니다." })
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
    if (message.length < 2) throw new HttpsError("invalid-argument", "내용을 입력하여 주시기 바랍니다.");
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

/* 환불이 끝난 구독인가.

   오늘 값을 받은 환불은 자정까지 subActive 가 참이다. 그 사이에 해지·플랜
   변경·환불을 또 누를 수 있는데, 두 번째 환불은 이미 취소한 결제 건을 다시
   취소하려 들고 업그레이드는 방금 환불한 카드에 차액을 긁는다.
   끝난 구독에는 아무것도 하지 않는다. */
function refundedAlready(sub) { return !!(sub && sub.refundedAt); }

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
    const used = seen.length;
    if (seen.includes(ticker)) return { ok: true, used };   // 오늘 이미 본 종목 — 추가 차감 없음
    if (used >= limit) return { ok: false, used };
    tx.set(ref, {
      tickers: admin.firestore.FieldValue.arrayUnion(ticker),
      count: seen.length + 1,
      day,
      uid,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true, used: used + 1 };
  });
}

/* 오늘 몇 개를 썼는지. 화면이 '남은 개수'를 보여 주려면 필요하다.
   report_reads 는 클라이언트가 읽지 못하게 막아 뒀으므로(firestore.rules) 서버가 준다.

   그냥 오늘 본 종목 수다. 구독별로 따로 세지 않는다 — 구독 기간이 겹치지
   않게(confirmBilling 이 이전 구독이 끝나는 시점부터 시작한다) 만들어 두었기
   때문에, 어느 하루의 열람은 언제나 한 구독에만 속한다. */
async function usageOf(db, uid) {
  const snap = await db.doc(`report_reads/${uid}_${kstDay()}`).get();
  return ((snap.exists && snap.data().tickers) || []).length;
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
        `이 주소는 이미 ${other.label}으로 등록되어 있습니다. 그 방법으로 로그인하여 주시기 바랍니다.`, { method: other.method });
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
  /* 네이버 연결을 끊으려면 앱 키가 있어야 한다 — 카카오는 어드민 키 하나로
     되지만 네이버는 client_id·client_secret 으로 토큰을 갱신해야 한다.

     토스 비밀키는 결제를 켰을 때만 붙인다. 이 함수는 유료 구독이 있으면 환불을
     먼저 하므로 그때는 반드시 있어야 하는데, 결제가 꺼져 있을 때 선언해 두면
     값이 없어 배포 자체가 막힌다("no value for the secret"). 그 하나 때문에
     탈퇴·로그인처럼 결제와 무관한 함수까지 전부 못 올라간 적이 있다.

     TOSS_SECRET_KEY 는 결제가 꺼져 있으면 null 이다(파일 위쪽). 그래서 스위치
     하나로 두 경우가 다 맞는다 — 결제를 켜는 날 여기를 손대야 하는 일이 없다.
     사람이 기억해야 하는 단계로 두면 언젠가 잊고, 그러면 유료 회원이 탈퇴를
     못 하게 된다. */
  { region: REGION, cors: true,
    secrets: [KAKAO_ADMIN_KEY, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET,
              ...(TOSS_SECRET_KEY ? [TOSS_SECRET_KEY] : [])] },
  async (req) => {
  const uid = req.auth && req.auth.uid;
  if (!uid) throw new HttpsError("unauthenticated", "로그인이 필요합니다.");
  const db = admin.firestore();
  const subRef = db.doc(`subscriptions/${uid}`);

  /* 탈퇴한다고 환불받을 권리가 사라지지는 않는다. 결제 후 7일 이내에 리포트를
     한 번도 열지 않았다면 전액 환불은 전자상거래법 제17조가 준 권리이고,
     요금제 페이지에도 그렇게 적어 뒀다. '환불 신청' 버튼을 먼저 누르지 않았다는
     이유로 돈을 가질 수는 없다. 그래서 여기서 같은 기준으로 계산해 먼저 돌려준다.

     환불이 실패하면 탈퇴를 진행하지 않는다. 계정을 지운 뒤에 실패하면 당사자는
     로그인도 못 하는데 돈은 우리가 들고 있는 상태가 된다 — 되돌릴 방법이 없다.

     돈을 만지는 다른 함수들과 같은 자물쇠를 잡는다. 안 잡으면 이런 일이 난다 —
     갱신 배치가 카드를 긁는 그 순간에 탈퇴를 누르면, 환불은 긁기 전의 문서를
     보고 계산해 "돌려줄 것이 없다" 로 끝나고, 그 뒤에 배치가 한 달치를 청구한
     다음 여기서 billingKey 를 지운다. 결과는 한 달치를 받아 놓고 계정을 지운
     것이 된다 — 당사자는 로그인도 못 하니 항의할 창구조차 없다.

     문서가 없는 무료 회원에게는 자물쇠를 걸지 않는다. withLock 은 자물쇠를
     잡으면서 문서를 먼저 만들기 때문에, 구독한 적 없는 사람 앞으로 빈 구독
     문서가 하나 생겨 남는다. */
  let refunded = 0;
  const first = await subRef.get();
  let sub = first.exists ? first.data() : null;

  if (sub) {
    await withLock(db, subRef, "delete", async () => {
      // 자물쇠를 잡는 사이에 갱신·재시도가 끝났을 수 있다. 그 결과를 보고 센다.
      sub = (await subRef.get()).data() || null;
      if (subActive(sub) && sub.lastPaymentKey) {
        const q = await refundQuote(db, uid, sub);
        if (q.amount > 0) {
          try {
            await doRefund(db, uid, subRef, sub, q);
            refunded = q.amount;
          } catch (e) {
            console.error(`[delete] 환불 실패 uid=${uid}`, e && e.message);
            throw new HttpsError("failed-precondition",
              "환불 처리에 실패해 탈퇴를 진행하지 않았습니다. 구독 관리에서 환불을 먼저 신청해 주시기 바랍니다.");
          }
        }
      }
      await subRef.set({
        status: "deleted",
        cancelAtPeriodEnd: true, pendingPlan: null,
        billingKey: admin.firestore.FieldValue.delete(),
        customerKey: admin.firestore.FieldValue.delete(),
        card: admin.firestore.FieldValue.delete(),
        deletedAt: admin.firestore.FieldValue.serverTimestamp(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });
    });
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
  } else if (String(uid).startsWith("naver:")) {
    unlinked = await naverUnlink(uid);
  }
  await logConsent(db, uid, "withdraw",
    unlinked === null ? {} : { providerUnlinked: unlinked }, req);

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
      /* 시계는 '마지막으로 확인한 때' 부터 잰다.

         ⚠️ 처음에는 marketingAt(최초 동의일) 만 봤다. 그러면 재확인 메일을
            보내도 그 사람은 영원히 대상으로 남는다 — 숫자가 줄지 않으니
            보냈는지 안 보냈는지 화면으로는 알 수가 없다.

         marketingRecheck 가 보낸 뒤 marketingRecheckedAt 을 찍는다. 여기서
         같은 기준으로 세야 두 곳이 어긋나지 않는다. */
      const ms = (t) => (t && t.toDate ? t.toDate().getTime() : 0);
      const base = Math.max(ms(u.marketingAt), ms(u.marketingRecheckedAt), ms(c.agreedAt));
      /* 기한과 앞당김 폭을 발송 쪽과 똑같이 쓴다. 여기서 730일 같은 다른
         잣대를 쓰면 화면 숫자와 실제로 나가는 메일이 어긋난다. */
      if (base && now >= recheckDueAt(base) - RECHECK_LEAD_DAYS * 86400000) dueRecheck++;
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
    /* 네이버가 보낸 원본. 아직 매핑 전이라 눈으로 보려고 싣는다. */
    providerRaw: u.providerRaw || null,
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

/* 유령 문서 정리 — 손으로 누르는 자리.

   Firebase 콘솔에서 Auth 사용자를 지우면 users 문서는 그대로 남는다.
   콘솔은 우리 함수를 거치지 않으니 어쩔 수 없다. purgeUnconsented 가
   매일 12:30 에 치우지만, 개발 중에는 그때까지 기다릴 이유가 없다.

   Auth 에 없는 문서만 지운다. 조회가 실패하면 아무것도 지우지 않는다 —
   '못 읽었다' 를 '없다' 로 읽으면 멀쩡한 회원 문서를 지우게 된다. */
exports.adminPurgeOrphans = onCall({ region: REGION, cors: true }, async (req) => {
  assertAdmin(req);
  const db = admin.firestore();
  const MAX = 200;
  const docs = (await db.collection("users").limit(2000).get()).docs;
  const removed = [];
  for (let i = 0; i < docs.length && removed.length < MAX; i += 100) {
    const part = docs.slice(i, i + 100);
    const res = await admin.auth().getUsers(part.map((d) => ({ uid: d.id })));
    const live = new Set((res.users || []).map((u) => u.uid));
    for (const d of part) {
      if (live.has(d.id) || removed.length >= MAX) continue;
      const email = (d.data() || {}).email || null;
      await d.ref.delete();
      removed.push({ uid: d.id, email });
      console.log(`[orphan] 삭제 ${d.id}`);
    }
  }
  return { count: removed.length, rows: removed };
});

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
/* 카드로 이 금액 미만은 결제할 수 없다(토스 제한). staging/payment-config.js
   의 MIN_CHARGE 와 같아야 한다 — 다르면 미리보기에서 되던 게 실제에서 막힌다. */
const MIN_CHARGE = 100;
const FREE_WITHDRAW_DAYS = 7;                     // 미열람 시 전액 환불 기간

/* 카드가 거절된 뒤 며칠째에 다시 시도하는가(첫 실패로부터).

   일시적인 한도 초과나 통신 오류로 구독이 끊기는 것을 막는다 — 업계에서
   dunning 이라 부르는 것이고, 간격도 관행을 따랐다. 매일 긁으면 카드사에
   불필요한 거절 기록만 쌓이고, 너무 띄우면 그 사이 사용자는 못 본다.

   네 번 다 실패하면 이용을 종료한다. 무한정 붙잡고 있으면 카드가 이미 해지된
   사람의 결제를 몇 달씩 시도하게 된다. */
const RETRY_DAYS = [1, 3, 5, 7];

const tossAuth = () =>
  "Basic " + Buffer.from(((TOSS_SECRET_KEY && TOSS_SECRET_KEY.value()) || "") + ":").toString("base64");

/* 같은 요청이 두 번 가도 돈은 한 번만 나가게 한다.

   idem 을 주면 토스가 그 이름으로 결과를 기억한다. 같은 이름이 다시 오면
   새로 긁지 않고 처음 결과를 그대로 돌려준다. 우리 쪽 자물쇠(withLock)가
   먼저 막지만 자물쇠는 함수가 중간에 죽으면 풀린다 — 그때 사용자가 다시
   누르면 돈이 두 번 나갈 수 있다. 이건 그 마지막 방어선이다.

   이름은 '무엇을 하려던 요청인가' 로 짓는다. 시각을 넣으면 두 번째 요청이
   다른 이름이 되어 아무것도 막지 못한다. */
async function toss(path, body, idem = null) {
  /* 스위치가 꺼져 있으면 비밀키가 없다. 빈 키로 토스를 부르면 401 을 받고
     엉뚱한 카드사 오류 메시지가 나간다 — 여기서 먼저 막는다. */
  if (!PAYMENTS_LIVE) throw new HttpsError("failed-precondition", "결제 기능이 아직 준비되지 않았습니다.");
  const headers = { Authorization: tossAuth(), "Content-Type": "application/json" };
  if (idem) headers["Idempotency-Key"] = String(idem).slice(0, 300);
  const res = await fetch("https://api.tosspayments.com/v1" + path, {
    method: "POST",
    headers,
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

/* ── 돈 나가는 문의 자물쇠 ───────────────────────────────────
   여태 "이미 환불했나?" 를 확인하고 → 환불했다. 그 사이에 두 번째 요청이
   들어오면 둘 다 확인을 통과한다. 사용자가 느린 화면에서 두 번 누르면 실제로
   일어나고, 그때 나가는 건 돈이다.

   확인과 자물쇠 잠그기가 한 동작이어야 한다. 트랜잭션 안에서 '비어 있으면
   내가 잡는다' 를 한 번에 한다 — 둘이 동시에 와도 하나만 잡는다.

   자물쇠를 오래 두지는 않는다. 함수가 중간에 죽으면 풀어 줄 사람이 없어서,
   그대로 두면 그 사람은 영영 결제도 환불도 못 한다. BUSY_TTL 이 지난
   자물쇠는 없는 것으로 본다.
   ─────────────────────────────────────────────────────────── */
const BUSY_TTL = 2 * 60 * 1000;          // 2분

async function withLock(db, ref, op, fn) {
  await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref);
    const busy = snap.exists && snap.data().busy;
    const at = busy && busy.at && typeof busy.at.toMillis === "function" ? busy.at.toMillis() : 0;
    if (busy && Date.now() - at < BUSY_TTL) {
      /* '자물쇠가 잡혀 있다' 를 부르는 쪽이 구별할 수 있어야 한다. 갱신 배치는
         이걸 실패로 적으면 안 되고 건너뛰어야 한다.

         HttpsError 의 code 로 구별하지 않는다 — 그 속성 이름은 라이브러리 사정이고,
         바뀌면 조용히 '결제 실패' 로 적히기 시작한다. 우리가 붙인 표시를 본다. */
      const e = new HttpsError("aborted",
        "앞서 요청하신 건을 처리하는 중입니다. 잠시 후 다시 시도하여 주시기 바랍니다.");
      e.kosLocked = true;
      throw e;
    }
    tx.set(ref, { busy: { op, at: admin.firestore.Timestamp.now() } }, { merge: true });
  });
  try {
    return await fn();
  } finally {
    /* 자물쇠는 반드시 푼다. 푸는 데 실패해도 본 작업 결과를 덮지 않도록 조용히
       넘긴다 — TTL 이 지나면 어차피 풀린다. */
    try {
      await ref.set({ busy: admin.firestore.FieldValue.delete() }, { merge: true });
    } catch (e) {
      console.error("[lock] 자물쇠 해제 실패", ref.path, e && e.message);
    }
  }
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

/* 화면에 보여 줄 결제 내역 줄 수. 월 구독이라 24줄이면 2년이다.
   전부 내려보내면 오래 쓴 사람일수록 창을 열 때마다 느려지는데, 그 아래는
   아무도 안 내려 본다. */
const PAYMENT_PAGE = 24;

/* Firestore 시각을 화면이 읽을 수 있는 글자로 바꾼다.
   함수 응답에 Timestamp 를 그대로 실으면 브라우저에는 {_seconds:…} 라는
   객체로 도착해서 날짜로 못 읽는다 — 내역 표의 '일자' 칸이 비어 버린다. */
const isoOf = (v) =>
  v == null ? null
  : typeof v.toDate === "function" ? v.toDate().toISOString()
  : typeof v === "number" ? new Date(v).toISOString()
  : String(v);

/* 결제 내역 — 본인 것만.

   payments/{uid}/items 는 규칙으로 아무에게도 열지 않았다(서버만 쓴다).
   그래서 본인이 자기 결제 내역을 보는 길이 여기 하나뿐이다.

   토스 식별자(paymentKey·orderId)는 내려보내지 않는다. 화면이 쓸 일이
   없고, 결제 건을 취소할 수 있는 열쇠라 브라우저에 둘 이유가 없다. */
if (PAYMENTS_LIVE) exports.listPayments = onCall(
  { region: REGION, cors: true },
  async (req) => {
    const uid = uidOrThrow(req);
    const snap = await admin.firestore()
      .collection(`payments/${uid}/items`)
      .orderBy("createdAt", "desc")
      .limit(PAYMENT_PAGE)
      .get();
    return {
      items: snap.docs.map((d) => {
        const p = d.data();
        return {
          amount: p.amount || 0,
          /* kind 로 화면이 문구를 만든다. description 은 한국어로 굳어 있어
             영어 화면에서 번역할 수가 없다 — 관리자·로그용으로만 둔다. */
          kind: p.kind || null,
          why: p.why || null,
          status: p.status || "paid",
          plan: p.plan || null,
          paidAt: isoOf(p.paidAt),
          createdAt: isoOf(p.createdAt),
        };
      }),
    };
  }
);

/** 빌링키로 즉시 결제. 성공하면 결제 내역을 남기고 payment 객체를 돌려준다. */
/* 결제 한 건을 기록할 때는 '무엇에 대한 결제인가'를 종류(kind)로 남긴다.
   ⚠️ 설명 문장을 한국어로 굳혀 저장하면 영어 화면에서 번역할 방법이 없다.
      화면이 언어에 맞춰 문구를 만들 수 있도록 kind 를 준다. description 은
      관리자 화면·로그에서 사람이 읽기 위한 값으로만 남겨 둔다. */
/* 이번 결제 주기에 실제로 받은 돈. 환불은 이 합계를 기준으로 계산하고, 이
   건들을 취소해 돌려준다 — 요금제의 정가가 아니다.

   업그레이드하면 한 주기에 결제가 둘이 된다(월 구독 + 차액). 정가를 기준으로
   삼으면 받지도 않은 돈을 기준으로 환불액을 내고, 취소할 때는 그중 한 건만
   가리키게 되어 카드사가 거절한다. */
const paidThisPeriod = (sub) =>
  ((sub && sub.periodPayments) || []).reduce((a, e) => a + (e.amount || 0), 0);

/* 환불에 쓸 결제 건들. 최근 것부터 — 마지막에 받은 돈을 먼저 되돌린다. */
function refundSources(sub) {
  const list = ((sub && sub.periodPayments) || [])
    .filter((e) => e && e.key && e.amount > 0);
  if (list.length) return list.slice().reverse();
  // periodPayments 가 붙기 전에 만들어진 구독. 있는 것으로 최선을 다한다.
  return sub && sub.lastPaymentKey
    ? [{ key: sub.lastPaymentKey, amount: PRICE[sub.plan] || 0 }] : [];
}

/* 아직 안 쓴 돈. 결제 건마다 그 돈이 사는 기간이 다르므로 따로 센다.

   월 구독은 주기 전체를 산다. 업그레이드 차액은 '그날부터 주기 끝까지' 만
   산다 — 청구할 때 남은 일수로 나눠 받았으니 돌려줄 때도 같은 기간으로
   나눠야 한다.

     BASIC 9,900원(31일) → 7일 쓰고 PRO 로 올림(차액 3,870원) → 바로 환불

       한 덩어리로 세면   13,770 × 24/31        = 10,661 → 수수료 빼고 9,594
       건마다 세면        9,900 × 24/31 = 7,665
                          3,870 × 24/24 = 3,870  = 11,535 → 수수료 빼고 10,381

   한 덩어리로 세면 차액에서도 7일을 뺀다. 그런데 그 7일 동안 이 사람은
   BASIC 을 썼지 PRO 를 쓴 적이 없다. 쓰지 않은 날의 값을 받는 셈이라 787원을
   덜 돌려주게 된다. */
function unusedOf(sub, startMs, endMs, usedUntilDay) {
  const endDay = kstDayNo(endMs);
  const list = ((sub && sub.periodPayments) || []).length
    ? sub.periodPayments
    // 옛 구독. 월 구독 한 건이 주기 전체를 산 것으로 본다.
    : [{ amount: PRICE[sub.plan] || 0, from: startMs }];
  return list.reduce((sum, p) => {
    const fromDay = kstDayNo(p.from || startMs);
    const win = Math.max(1, endDay - fromDay);                 // 그 돈이 사는 날 수
    const left = Math.max(0, endDay - Math.max(fromDay, usedUntilDay));
    return sum + (p.amount || 0) * Math.min(1, left / win);
  }, 0);
}

async function charge(db, uid, sub, amount, description, tag, kind, idem) {
  /* 숫자가 아니면 부르지 않는다.

     'amount < MIN_CHARGE' 만으로는 못 막는다 — undefined 와 NaN 은 어떤 수와
     비교해도 false 라 그 관문을 그냥 지나가고, 그대로 카드사로 나간다.
     PRICE[plan] 이 undefined 가 되는 경우(구독 문서의 plan 이 우리가 아는 값이
     아닐 때)가 그렇게 새는 길이다. 조용히 넘기지 않고 소리 내어 멈춘다. */
  if (!Number.isFinite(amount)) {
    console.error("[charge] 금액이 숫자가 아니다", uid, tag, amount);
    throw new HttpsError("internal", "결제 금액을 계산하지 못했습니다.");
  }
  /* 100원 미만은 청구를 건너뛰고 넘어간다. 업그레이드 차액은 남은 기간에
     비례하므로 주기 마지막 날에는 몇십 원이 된다. 그대로 토스에 보내면
     거절당해 플랜 변경 자체가 실패한다 — 몇십 원 받자고 기능을 막는 셈이다. */
  if (amount < MIN_CHARGE) return null;
  /* orderId 에는 시각이 들어가 매번 달라진다. 두 번째 요청을 막는 이름은
     따로 받는다 — idem 이 없으면 토스는 재시도도 새 결제로 받는다. */
  const pay = await toss(`/billing/${sub.billingKey}`, {
    customerKey: sub.customerKey,
    amount,
    orderId: orderId(uid, tag),
    orderName: description,
  }, idem);
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

    return withLock(db, ref, "billing", async () => {
      const cur = (await ref.get()).data() || null;

      /* 카드만 바꾸는 경우. 이용 중인 사람도 여기로 온다 — 아래 '이미 구독 중'에서
         막아 버리면 카드가 만료됐을 때 바꿀 길이 없어진다. 결제는 하지 않는다.
         여기서 또 받으면 이중 청구다. */
      if (req.data && req.data.updateMethod) {
        /* 카드를 바꿀 수 있는 상태는 둘뿐이다 — 이용 중이거나, 결제가 밀려
           멈춰 있거나. 그 밖에는 바꿔 봐야 아무 일도 일어나지 않는다.

           '문서가 있는가'로 물으면 안 된다. 위 withLock 이 자물쇠를 걸면서
           문서를 먼저 만들기 때문에, 구독이 없는 사람도 {busy} 하나만 든
           문서를 갖게 되어 그 검사를 통과한다. 그러면 plan 도 status 도 없는
           채로 카드만 등록되고, 반쪽짜리 구독 문서가 남는다.

           이미 끝난 구독(expired)도 막는다. 갱신 배치는 status 가 active 인
           것만 집으므로 카드를 새로 걸어도 다시 결제되지 않는다 — 되는 것처럼
           보여 주고 아무 일도 안 하는 쪽이 더 나쁘다. 다시 시작하려면 결제
           화면으로 가야 한다. */
        if (!subActive(cur) && !(cur && cur.status === "past_due")) {
          throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
        }
        /* 환불이 끝난 구독에는 카드도 새로 걸지 않는다. 오늘 값을 받은 환불은
           자정까지 살아 있어서 그 사이에 여기까지 올 수 있는데, 곧 끝날 구독에
           카드를 등록시키면 다음 달에 긁힐 것처럼 읽힌다. 미리보기는 이미 막고
           있었다 — 서버만 뚫려 있었다. */
        if (refundedAlready(cur)) throw new HttpsError("failed-precondition", "환불이 완료된 구독입니다.");
        const re = await toss("/billing/authorizations/issue", { authKey, customerKey });
        const card = { company: (re.card && re.card.issuerCode) || "", number: (re.card && re.card.number) || "" };
        const patch = { billingKey: re.billingKey, customerKey, card,
                        updatedAt: admin.firestore.FieldValue.serverTimestamp() };
        // 갱신 결제가 실패해 멈춰 있던 구독이라면, 새 카드로 바로 받아 되살린다.
        // 카드만 갈아 끼우고 끝내면 다음 배치가 돌 때까지 하루를 잠긴 채로 둔다.
        if (cur.status === "past_due") {
          const at = new Date();
          /* 예약해 둔 플랜 변경을 여기서 적용한다.

             다운그레이드는 '다음 결제일부터' 다. 그 다음 결제일이 바로 결제가
             거절된 그날이므로, 되살릴 때 적용해야 할 플랜은 예약해 둔 쪽이다.
             옛 플랜으로 청구하면 BASIC 으로 내리겠다고 예약한 사람에게 PRO
             값을 받고 PRO 를 그대로 물려 놓는 셈이 된다. 갱신 배치와 재시도
             배치는 이미 pendingPlan 을 보고 있었는데, 카드 재등록으로 되살리는
             이 길만 옛 플랜을 보고 있었다. */
          const nextPlan = PRICE[cur.pendingPlan] ? cur.pendingPlan : cur.plan;
          /* 멱등 이름에 카드(빌링키)를 섞는다.

             날짜만으로 지으면 같은 날 카드 A 로 실패한 뒤 카드 B 로 다시 걸 때
             이름이 똑같아진다. 카드사가 실패한 응답도 그 이름으로 기억한다면
             두 번째 카드는 긁어 보지도 못하고 첫 실패를 돌려받는다 — 카드를
             바꿔도 안 되는, 사용자가 손쓸 수 없는 상태가 된다.

             카드사가 실패 응답을 어떻게 다루는지는 여기서 확인할 수 없다.
             확인할 수 없으면 안전한 쪽으로 짓는다. 빌링키는 카드를 등록할 때마다
             새로 나오므로, 같은 카드로 두 번 누르는 것은 여전히 한 번만 나간다. */
          const pay = await charge(db, uid, { ...cur, ...patch, plan: nextPlan },
            PRICE[nextPlan], `${PLAN_NAME[nextPlan]} 월 구독`, "retry", null,
            `retry_${uid}_${kstDay()}_${String(re.billingKey).slice(-12)}`);
          patch.status = "active";
          patch.plan = nextPlan;
          patch.pendingPlan = null;
          patch.currentPeriodStart = admin.firestore.Timestamp.fromDate(at);
          patch.currentPeriodEnd = admin.firestore.Timestamp.fromDate(addMonth(at));
          patch.lastPaymentKey = pay ? pay.paymentKey : null;
          /* 새 주기다 — 지난 주기의 결제 건은 여기서 끊는다. 안 끊으면 환불이
             이미 다 쓴 지난달 결제까지 기준에 넣고, 그 건을 취소하려 든다. */
          patch.periodPayments = pay
            ? [{ key: pay.paymentKey, amount: PRICE[nextPlan], from: at.getTime() }] : [];
          patch.refundDone = admin.firestore.FieldValue.delete();
          /* 밀렸던 흔적도 같이 지운다. 남겨 두면 다음 달에 카드가 거절될 때
             재시도 횟수가 지난달 것에서 이어져, 네 번 줘야 할 기회를 한두 번만
             주고 구독을 끊어 버린다. failedAt 도 마찬가지로 지난 실패 날짜를
             가리키고 있어, 재시도 일정이 엉뚱한 날로 잡힌다. */
          patch.failedAt = admin.firestore.FieldValue.delete();
          patch.retryCount = admin.firestore.FieldValue.delete();
        }
        await ref.set(patch, { merge: true });
        // 되살렸으면 실제로 적용된 플랜을 돌려준다 — 예약해 둔 변경이 여기서 반영된다.
        return { ok: true, plan: patch.plan || cur.plan, updated: true };
      }

      /* 이용 중인 구독 위에 또 결제하지 않는다. 돈을 두 번 받는 자리다.

         예외는 '환불이 끝난 구독' 하나뿐이다. 오늘 값을 받은 환불은 그 구독을
         자정까지 살려 두므로 subActive 가 여전히 참인데, 돈은 이미 돌려줬으니
         다시 시작하려면 새로 결제하는 수밖에 없다. 겹치는 하루는 아래에서
         기간 끝에 붙여 돌려준다.

         해지 예약(cancelAtPeriodEnd)은 예외가 아니다. 한때 열어 뒀는데,
         그러면 이런 일이 난다 —

           1일  BASIC 결제(1일~31일)
           5일  해지 예약. 31일까지는 그대로 이용한다.
           7일  결제 화면으로 들어와 다시 결제

         새 기간은 '지금부터 addMonth(이전 기간 끝)' 이라 7일~61일, 54일이
         된다. 돈은 두 달치를 받았으니 날 수는 맞지만, periodPayments 가 방금
         받은 한 건으로 갈아엎어져 첫 달 결제는 환불 대상에서 사라진다. 그날
         환불하면 54일 기간에 한 달치만 얹힌 셈으로 계산돼, 사용자는 남은
         첫 달 값을 영영 돌려받지 못한다.

         해지 예약을 되돌리는 길은 이미 있다 — 구독 관리의 '해지 취소'
         (resumeSubscription)다. 공짜이고 즉시 반영된다. 플랜을 바꾸려는
         것이라면 changePlan 이 해지 예약도 함께 푼다. 결제가 필요한 길은
         하나도 없으므로, 여기서는 막고 그쪽으로 안내한다. */
      if (subActive(cur) && !cur.refundedAt) {
        throw new HttpsError("already-exists", cur.cancelAtPeriodEnd
          ? "해지가 예약된 구독이 있습니다. 구독 관리에서 해지를 취소해 주시기 바랍니다."
          : "이미 이용 중인 구독이 있습니다.");
      }

      const issued = await toss("/billing/authorizations/issue", { authKey, customerKey });
      const now = new Date();

      /* 이용은 지금부터. 이전 구독과 겹치는 하루는 기간 끝에 붙여 돌려준다.

         환불한 날 다시 시작하는 사람이 여기로 온다. 오늘 리포트를 봤다면 오늘
         요금은 이미 환불에서 차감했고, 그 구독은 오늘 자정까지 살아 있다.
         거기에 새 구독까지 오늘부터 시작하니 같은 하루를 두 번 내는 셈이다.

         그 하루를 앞에서 빼지 않고 뒤에 붙인다.

           start  지금
           end    addMonth(이전 구독이 끝나는 시점)   ← 겹친 만큼 뒤로 밀린다

           BASIC 2건 보고 환불 → PRO 재결제
             오늘    PRO 한도로 13건 더. 오늘 총 15건 — 한도 그대로.
             기간    오늘부터 다음 달 그날 + 하루

           PRO 15건 다 보고 환불 → PRO 재결제
             오늘    이미 다 썼으므로 0건.
             기간    31일. 오늘 하루를 못 쓴 만큼 뒤에서 하루를 더 받는다.
                     실제로 쓸 수 있는 날 수는 30일로 같다.

         앞에서 빼는 방식(새 구독을 내일부터 시작)도 계산은 맞지만, 구독 문서가
         '오늘까지는 옛 플랜, 내일부터 새 플랜' 두 겹을 들고 있어야 한다. 한도를
         판정하는 자리가 세 곳(서버·미리보기·화면)이라 한 곳만 놓쳐도 화면 숫자와
         실제로 열리는 개수가 어긋난다 — 실제로 그렇게 어긋난 적이 있다.
         뒤에 붙이면 판정할 것이 하나도 늘지 않는다.

         이전 구독이 이미 끝났으면(오늘 한 건도 안 봐서 환불과 동시에 닫힌
         경우, 또는 처음 가입) 겹치는 하루가 없으므로 그냥 한 달이다 — max 가
         그 두 갈래를 한 줄로 처리한다. */
      const prevEnd = cur && cur.currentPeriodEnd ? cur.currentPeriodEnd.toMillis() : 0;
      const start = now;
      const end = addMonth(new Date(Math.max(now.getTime(), prevEnd)));
      const sub = {
        billingKey: issued.billingKey, customerKey, plan,
        card: { company: (issued.card && issued.card.issuerCode) || "", number: (issued.card && issued.card.number) || "" },
      };
      const pay = await charge(db, uid, sub, PRICE[plan], `${PLAN_NAME[plan]} 월 구독`, "new", null,
        `new_${uid}_${plan}_${kstDay()}`);

      await ref.set({
        ...sub,
        status: "active",
        currentPeriodStart: admin.firestore.Timestamp.fromDate(start),
        currentPeriodEnd: admin.firestore.Timestamp.fromDate(end),
        cancelAtPeriodEnd: false,
        pendingPlan: null,
        /* 환불하고 다시 시작한 경우엔 시작일도 새로 본다. 지난 구독은 돈까지
           돌려주고 끝냈는데 '구독 시작일' 만 그때로 남으면 이어진 것처럼 읽힌다. */
        startedAt: (cur && !cur.refundedAt && cur.startedAt) || admin.firestore.Timestamp.fromDate(start),
        lastPaymentKey: pay ? pay.paymentKey : null,
        /* 이번 주기에 받은 돈. 환불이 이 목록을 보고 계산하고 취소한다.
           from 은 그 돈이 사는 기간의 시작이다 — 월 구독은 주기 전체를 산다. */
        periodPayments: pay
          ? [{ key: pay.paymentKey, amount: PRICE[plan], from: start.getTime() }] : [],
        /* 지난 구독이 남긴 표시를 전부 지운다. merge 로 쓰기 때문에 안 지우면
           그대로 붙어 있는다 — 특히 refundedAt 이 남으면 방금 결제한 구독이
           '환불 완료' 로 보이고, 해지·플랜 변경·환불이 전부 막힌다.
           환불한 날 다시 시작하는 사람이 바로 여기로 온다. */
        refundedAt: admin.firestore.FieldValue.delete(),
        canceledAt: admin.firestore.FieldValue.delete(),
        failedAt: admin.firestore.FieldValue.delete(),
        /* 결제가 밀려 멈춰 있던 사람이 카드를 바꾸는 대신 결제 화면에서 새로
           결제하면 여기로 온다. 재시도 횟수를 안 지우면 다음 달 거절 때
           남은 기회가 그만큼 줄어든 채로 시작한다. */
        retryCount: admin.firestore.FieldValue.delete(),
        /* 지난 환불에서 '어디까지 취소했는지' 적어 둔 기록. 새 구독에 그대로
           남으면 다음 환불이 이미 취소한 것으로 알고 건너뛴다 — 돈을 안 돌려주고
           끝난다. 주기가 새로 시작하는 자리마다 반드시 지운다. */
        refundDone: admin.firestore.FieldValue.delete(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });

      return { ok: true, plan };
    });
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

    return withLock(db, ref, "plan", async () => {
      const sub = (await ref.get()).data();
      if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
      if (refundedAlready(sub)) throw new HttpsError("failed-precondition", "환불이 완료된 구독입니다.");
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
        /* 결제 기록에 적히는 플랜은 charge 안에서 sub.plan 으로 정해진다. 여기에
           올리기 전 구독을 그대로 넘기면 'PRO 업그레이드 차액' 이라는 설명 옆에
           plan 은 BASIC 으로 남는다 — 내역을 보면 앞뒤가 안 맞는다.
           미리보기는 올린 뒤 플랜으로 적고 있었다(서버만 달랐다). */
        const pay = await charge(db, uid, { ...sub, plan: next }, diff,
          `${PLAN_NAME[next]} 업그레이드 차액`, "up", null,
          `up_${uid}_${next}_${kstDay()}`);
        await ref.set({
          plan: next, pendingPlan: null,
          // 해지 예약과 함께 둘 수 없다 — 아래 설명 참고.
          cancelAtPeriodEnd: false, canceledAt: null,
          /* 차액도 이번 주기에 받은 돈이다. 안 적으면 환불이 월 구독 한 건만
             보고 계산하고, 차액은 돌려주지 않은 채로 끝난다. */
          periodPayments: pay
            ? [...((sub.periodPayments) || []),
               // 차액은 '지금부터 주기 끝까지' 를 산다. 그 값으로 청구했으니
               // 환불도 그 기간으로 나눠야 한다.
               { key: pay.paymentKey, amount: diff, from: Date.now() }]
            : (sub.periodPayments || []),
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        }, { merge: true });
        /* 실제로 청구한 금액을 돌려준다. 100원 미만이면 청구를 건너뛰었으므로
           0원이다 — diff 를 그대로 주면 화면이 받지도 않은 돈을 안내한다. */
        return { ok: true, plan: next, charged: pay ? diff : 0 };
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
    });
  }
);

/* ── 3) 해지 / 해지 취소 ─────────────────────────────────────
   해지는 '지금 끊기'가 아니라 '갱신 안 함'이다. 이미 결제한 기간은 그대로 쓴다.
   ─────────────────────────────────────────────────────────── */
/* 돈이 나가지는 않지만 자물쇠를 잡는다.

   해지와 플랜 변경은 함께 둘 수 없는 예약이다(위 changePlan 설명). 그런데
   두 요청이 겹치면 '해지 예약 + 플랜 변경 예약' 이라는, 있어서는 안 되는
   상태가 만들어진다 — 갱신 배치는 해지를 먼저 보고 끝내므로 예약해 둔 변경은
   조용히 사라지고, 화면에는 둘 다 예약된 것처럼 보인다.

   결제와도 겹친다. 새 구독을 만드는 사이에 해지가 들어오면 방금 결제한 구독이
   해지 예약된 채로 시작한다. */
if (PAYMENTS_LIVE) exports.cancelSubscription = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const db = admin.firestore();
  const ref = db.doc(`subscriptions/${uid}`);
  return withLock(db, ref, "cancel", async () => {
    const sub = (await ref.get()).data();
    /* 결제가 밀려 멈춘 구독도 여기서 끊는다.

       재시도를 넣기 전에는 past_due 가 그냥 방치되다 기간이 지나 닫혔으므로
       해지할 것도 없었다. 지금은 다르다 — 1·3·5·7일째에 카드를 다시 긁는다.
       그만두겠다는 사람에게 멈출 방법을 주지 않으면, 원치 않는 달의 요금이
       일주일 안에 청구될 수 있다. 약관에 적어 둔 '언제든지 해지' 와도 어긋난다.

       이 경우는 예약이 아니라 즉시 종료다. 이미 낸 달은 다 썼고 다음 달 값은
       받지 못했으므로, 남겨서 지킬 이용 기간이 없다. */
    if (sub && sub.status === "past_due") {
      await ref.set({
        status: "expired", cancelAtPeriodEnd: true, pendingPlan: null,
        canceledAt: admin.firestore.FieldValue.serverTimestamp(),
        // 재시도 일정을 지운다. 남으면 배치가 이 문서를 다시 집을 근거가 된다.
        failedAt: admin.firestore.FieldValue.delete(),
        retryCount: admin.firestore.FieldValue.delete(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });
      return { ok: true, droppedPlan: null, stopped: true };
    }
    if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
    if (refundedAlready(sub)) throw new HttpsError("failed-precondition", "환불이 완료된 구독입니다.");
    await ref.set({
      cancelAtPeriodEnd: true, canceledAt: admin.firestore.FieldValue.serverTimestamp(),
      // 해지하면 다음 결제 자체가 없다 — 예약해 둔 플랜 변경은 의미가 없다.
      pendingPlan: null,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true, droppedPlan: sub.pendingPlan || null };
  });
});

// 해지 취소도 같은 자물쇠를 잡는다 — 위 cancelSubscription 설명 참고.
if (PAYMENTS_LIVE) exports.resumeSubscription = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const db = admin.firestore();
  const ref = db.doc(`subscriptions/${uid}`);
  return withLock(db, ref, "resume", async () => {
    const sub = (await ref.get()).data();
    if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
    if (refundedAlready(sub)) throw new HttpsError("failed-precondition", "환불이 완료된 구독입니다.");
    await ref.set({
      cancelAtPeriodEnd: false, canceledAt: null,
      updatedAt: admin.firestore.FieldValue.serverTimestamp(),
    }, { merge: true });
    return { ok: true };
  });
});

/* ── 4) 환불 ─────────────────────────────────────────────────
   요금제 페이지에 고지한 기준 그대로 계산한다. 문구와 계산이 어긋나면
   그건 그냥 거짓말이 된다.
     · 리포트 미열람 + 7일 이내  → 전액
     · 리포트 미열람 + 7일 경과  → 잔여 기간분 − 수수료 10%
     · 리포트 열람              → 이용 일수 차감 후 − 수수료 10%

   오늘 하루를 셀지 말지는 '오늘 리포트를 열었는가' 가 정한다.

     오늘 0건    오늘 값을 받지 않는다 → 이용은 지금 끝난다
     오늘 1건+   오늘 값을 받는다     → 이용은 오늘 자정까지

   여태 경과 시간을 초 단위로 나눠 썼다(9.375일). 그런데 우리가 파는 단위는
   하루다 — 하루 5건, 한국 시간 자정 리셋. 쪼갤 수 없는 것을 소수로 차감하니
   양쪽 다 어긋났다.

     오전 9시에 한 건도 안 보고 환불   오늘 값 0.375일을 내고 5건은 못 봄
     오전 9시에 5건 다 보고 환불       하루치를 다 쓰고 0.375일만 냄

   밤 11시 50분에 한 건도 안 보고 환불하면 오늘 값을 거의 다 내고 아무것도
   못 보는데, 그게 가장 이상했다.

   요금제 페이지에는 처음부터 '이용하신 일수를 차감' 이라고 적어 두었다.
   고지는 일수인데 계산이 초였다 — 이제 적어 둔 대로 센다.
   ─────────────────────────────────────────────────────────── */
const KST_OFFSET = 9 * 3600 * 1000;
/* 한국 시간 기준으로 며칠째인가(1970-01-01 = 0). 날짜끼리 빼면 날 수가 된다. */
const kstDayNo = (ms) => Math.floor((ms + KST_OFFSET) / 86400000);
/* 오늘이 끝나는 순간 = 내일 0시(KST). 오늘 값을 받았을 때 여기까지 열어 준다. */
const kstEndOfToday = (ms = Date.now()) =>
  new Date((kstDayNo(ms) + 1) * 86400000 - KST_OFFSET);

/* 환불 금액 계산 — 요금제 페이지에 고지한 기준 그대로.
   환불 신청과 회원 탈퇴가 같은 계산을 써야 한다. 두 곳에 따로 적으면 언젠가
   한쪽만 고치고 지나가고, 그러면 고지한 기준과 실제가 어긋난다. */
async function refundQuote(db, uid, sub) {
  if (!sub || !sub.lastPaymentKey) return { amount: 0, reason: "" };
  const startMs = sub.currentPeriodStart.toMillis();
  const endMs = sub.currentPeriodEnd.toMillis();
  /* 주기는 addMonth 로 잡으므로 시각이 같아 원래 정수일이다. 반올림은 만약을
     대비한 것 — 소수가 섞이면 아래 날짜 뺄셈과 단위가 어긋난다. */
  const total = Math.max(1, Math.round(days(endMs - startMs)));
  /* 기준은 요금제의 정가가 아니라 이번 주기에 실제로 받은 돈이다.

     BASIC 을 쓰다 PRO 로 올리면 9,900원 + 차액을 받는데, 정가(14,900원)를
     기준으로 삼으면 받은 적 없는 돈까지 계산에 들어간다. 게다가 취소할 때는
     결제 건 하나만 가리키므로, 그 건보다 큰 금액을 취소하려 들어 카드사가
     통째로 거절한다 — 업그레이드한 사람은 환불이 아예 안 됐다. */
  const price = paidThisPeriod(sub) || PRICE[sub.plan] || 0;

  // 이번 결제 기간에 리포트를 한 건이라도 열었는가
  const reads = await db.collection("report_reads")
    .where("uid", "==", uid)
    .where("updatedAt", ">=", sub.currentPeriodStart)
    .limit(1).get();
  const opened = !reads.empty;

  /* 오늘 한 건이라도 열었는가. 하루 한도를 세는 문서를 그대로 본다 —
     같은 자료를 두 곳에서 다르게 세면 화면의 '오늘 남은 열람' 과 환불 계산이
     어긋난다. */
  const openedToday = (await usageOf(db, uid)) > 0;

  // 지난 날은 전부 차감하고, 오늘은 열었을 때만 더한다.
  const elapsed = Math.max(0, kstDayNo(Date.now()) - kstDayNo(startMs));
  const used = Math.min(total, elapsed + (openedToday ? 1 : 0));

  if (!opened && used <= FREE_WITHDRAW_DAYS) {
    return { amount: price, reason: "청약철회(7일 이내·미열람)", why: "withdraw",
             chargedToday: false };
  }
  // 이 날짜까지는 쓴 것으로 본다. 그 뒤에 남은 돈만 돌려준다.
  const unused = unusedOf(sub, startMs, endMs, kstDayNo(startMs) + used);
  return {
    amount: Math.floor(unused * (1 - REFUND_FEE_RATE)),
    reason: opened ? "이용분 차감 환불" : "잔여 기간 환불",
    why: opened ? "used" : "left",
    chargedToday: openedToday,
  };
}

/* 한 주기에 결제가 여러 건일 수 있다(월 구독 + 업그레이드 차액). 카드사는
   결제 건 하나를 그 건의 금액 안에서만 취소해 준다. 그래서 최근 건부터 차례로,
   각 건의 금액만큼만 취소해 합계를 맞춘다.

   건마다 내역을 따로 남긴다. 취소가 둘로 나가면 카드 명세서에도 둘로 찍히므로,
   한 줄로 뭉뚱그리면 명세서와 우리 내역이 안 맞는다.

   중간에 실패하면 거기서 멈추고 던진다. 이미 나간 취소는 내역에 남아 있으므로
   얼마가 돌아갔는지는 확인할 수 있다 — 실패했다고 기록을 지우면 돈은 나갔는데
   흔적이 없어진다. */
async function doRefund(db, uid, ref, sub, q) {
  /* 취소가 여러 건으로 나가는데 중간에 실패할 수 있다. 첫 건은 이미 카드사에서
     취소됐는데 둘째에서 끊기면, 다시 눌렀을 때 첫 건을 또 취소하려 든다.

     그래서 나간 취소를 그때그때 구독 문서에 적는다(refundDone). 다시 오면 적힌
     만큼 건너뛰고 남은 것만 낸다. 토스에도 같은 이름으로 보내므로, 우리 기록이
     날아간 최악의 경우에도 카드사가 두 번 취소하지는 않는다. */
  const done = ((sub && sub.refundDone) || []).slice();
  const takenOf = (key) => done.reduce((a, d) => a + (d.key === key ? d.amount : 0), 0);
  let rest = q.amount - done.reduce((a, d) => a + d.amount, 0);

  for (const src of refundSources(sub)) {
    if (rest <= 0) break;
    const room = src.amount - takenOf(src.key);     // 이 건에서 아직 취소 안 한 몫
    const take = Math.min(rest, room);
    if (take <= 0) continue;
    await toss(`/payments/${src.key}/cancel`, {
      cancelReason: q.reason, cancelAmount: take,
    }, `refund_${uid}_${src.key}_${take}`);
    /* 나가자마자 적는다. 이 줄과 취소 사이에서 죽으면 기록에는 안 남지만,
       토스가 같은 이름을 기억하고 있어 다시 취소되지는 않는다. */
    done.push({ key: src.key, amount: take });
    await ref.set({ refundDone: done }, { merge: true });
    await writePayment(db, uid, {
      amount: -take, description: `환불 · ${q.reason}`,
      kind: "refund", why: q.why || null, status: "refunded",
      plan: sub.plan, paymentKey: src.key, paidAt: new Date().toISOString(),
    });
    rest -= take;
  }
  if (rest > 0) {
    // 여기 오면 계산이 받은 돈보다 큰 금액을 냈다는 뜻이다. 조용히 넘기면
    // 사용자는 덜 받은 줄 모른다.
    console.error("[refund] 취소하지 못한 잔액", uid, "계산", q.amount, "남음", rest);
    throw new HttpsError("internal", "환불을 끝까지 처리하지 못했습니다. 고객센터로 문의해 주시기 바랍니다.");
  }
}

if (PAYMENTS_LIVE) exports.requestRefund = onCall(
  { region: REGION, cors: true, secrets: [TOSS_SECRET_KEY] },
  async (req) => {
    const uid = uidOrThrow(req);
    const db = admin.firestore();
    const ref = db.doc(`subscriptions/${uid}`);
    /* 사용자가 확인 창에서 본 금액. 화면이 미리 물어본 값을 그대로 되돌려준다.
       없으면(옛 화면) 그냥 진행하고, 있는데 다르면 실행하지 않는다. */
    const expect = Number((req.data && req.data.expectAmount) ?? NaN);

    return withLock(db, ref, "refund", async () => {
      const sub = (await ref.get()).data();
      if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
      if (!sub.lastPaymentKey) throw new HttpsError("failed-precondition", "환불할 결제 건이 없습니다.");
      if (refundedAlready(sub)) throw new HttpsError("failed-precondition", "이미 환불이 완료되었습니다.");

      const q = await refundQuote(db, uid, sub);
      const amount = q.amount;
      if (amount <= 0) throw new HttpsError("failed-precondition", "환불 가능한 금액이 없습니다.");

      /* 보여준 금액으로만 실행한다. 확인 창을 띄운 뒤 리포트를 한 건 열면 오늘이
         이용일로 잡혀 금액이 달라진다. 그대로 진행하면 사용자는 본 적 없는
         금액을 받는다 — 새 금액을 알려 주고 다시 묻게 한다. */
      if (Number.isFinite(expect) && expect !== amount) {
        throw new HttpsError("failed-precondition",
          `환불 금액이 ${amount.toLocaleString("ko-KR")}원으로 변경되었습니다. 다시 확인해 주시기 바랍니다.`,
          { amount });
      }
      await doRefund(db, uid, ref, sub, q);

      /* 오늘 값을 받았으면 오늘은 끝까지 쓰게 둔다. 안 받았으면 지금 끝낸다.
         돈과 이용 기간이 같은 하루를 가리켜야 한다 — 오늘 값을 받아 놓고
         이용을 끊으면 대가는 받고 물건은 회수하는 셈이고, 값을 안 받고 열어
         주면 하루를 공짜로 주는 셈이다.

         q.chargedToday 를 다시 계산하지 않고 그대로 쓴다. 위에서 이미 그 값으로
         돈을 계산했으므로, 여기서 다시 세면 그 사이에 한 건 연 사람에게 값을
         안 받고 하루를 열어 주게 된다. */
      const endAt = q.chargedToday ? kstEndOfToday() : new Date();

      /* status 는 "refunded" 가 아니라 "active" 로 둔다.

         subActive 가 status === "active" 를 요구하므로, 여기서 "refunded" 로
         적으면 currentPeriodEnd 를 자정으로 미뤄 놔도 이용은 그 자리에서
         끊긴다 — 오늘 값을 받아 놓고 못 쓰게 하는 셈이다.

         대신 cancelAtPeriodEnd 를 세워 둔다. 다음 날 갱신 배치가 기간이 지난
         이 문서를 집어 cancelAtPeriodEnd 를 보고 카드를 긁지 않고 "expired"
         로 닫는다(해지 예약과 같은 길이다).

         '환불이 끝났다' 는 refundedAt 이 말한다. 그 값이 있으면 해지·플랜
         변경·재환불이 전부 막힌다(refundedAlready).
         오늘 값을 안 받은 환불은 endAt 이 지금이라 곧바로 닫힌다. */
      await ref.set({
        status: "active", cancelAtPeriodEnd: true, pendingPlan: null,
        currentPeriodEnd: admin.firestore.Timestamp.fromDate(endAt),
        refundedAt: admin.firestore.FieldValue.serverTimestamp(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
      }, { merge: true });

      return { ok: true, amount, endsAt: endAt.toISOString() };
    });
  }
);

/* ── 4-1) 환불 견적 ──────────────────────────────────────────
   확인 창에 금액을 적어 주려고 있다. 돈을 건드리지 않고 계산만 한다.

   여태 확인 창에는 "이용하신 일수를 차감해 산정됩니다" 만 있고 금액이 없었다.
   누른 다음에야 얼마인지 알았고, 그 사이 리포트를 한 건 열면 확인할 때와 다른
   금액이 나갔다. 여기서 받은 값을 requestRefund 에 그대로 되돌려주면, 달라진
   경우 실행하지 않고 다시 묻는다.
   ─────────────────────────────────────────────────────────── */
if (PAYMENTS_LIVE) exports.refundPreview = onCall({ region: REGION, cors: true }, async (req) => {
  const uid = uidOrThrow(req);
  const db = admin.firestore();
  const sub = (await db.doc(`subscriptions/${uid}`).get()).data();
  if (!subActive(sub)) throw new HttpsError("failed-precondition", "이용 중인 구독이 없습니다.");
  if (refundedAlready(sub)) throw new HttpsError("failed-precondition", "이미 환불이 완료되었습니다.");
  const q = await refundQuote(db, uid, sub);
  const endAt = q.chargedToday ? kstEndOfToday() : new Date();
  return {
    amount: q.amount, why: q.why || null, reason: q.reason || "",
    chargedToday: !!q.chargedToday, endsAt: endAt.toISOString(),
  };
});

/* ── 5) 정기결제 갱신 ────────────────────────────────────────
   매일 한 번 돌며 기간이 끝난 구독을 갱신한다. 크론은 UTC 로만 해석되므로
   02:00 UTC(= 같은 날 11:00 KST)로 적는다. 15시 이후로 잡으면 한국 날짜가 밀린다.
   ─────────────────────────────────────────────────────────── */
if (PAYMENTS_LIVE) exports.renewSubscriptions = onSchedule(
  // 카드를 긁으려면 토스 키, 실패를 알리려면 메일 키가 필요하다. 부르는 함수가
  // 쓰는 열쇠를 여기서 선언하지 않으면 그 자리에서 터진다.
  { region: REGION, schedule: "0 2 * * *", timeZone: "Etc/UTC",
    secrets: [TOSS_SECRET_KEY, RESEND_API_KEY] },
  async () => {
    const db = admin.firestore();
    const now = new Date();
    const due = await db.collection("subscriptions")
      .where("status", "==", "active")
      .where("currentPeriodEnd", "<=", admin.firestore.Timestamp.fromDate(now))
      .limit(400).get();
    console.log(`[renew] 대상 ${due.size}건`);

    const failed = [];                       // 이번에 처음 거절된 사람들
    const revived = [];                      // 재시도로 되살아난 사람들
    const gaveUp = [];                       // 끝까지 안 돼 종료한 사람들

    if (due.size >= 400) {
      // 한 번에 400건까지만 본다. 꽉 찼다는 건 못 본 사람이 남았다는 뜻이고,
      // 그 사람들은 하루 늦게 갱신된다. 조용히 밀리면 안 되니 알린다.
      console.error("[renew] 대상이 상한(400)까지 찼다 — 남은 건은 내일로 밀린다");
    }

    for (const d of due.docs) {
      const uid = d.id;
      let sub = d.data();
      // 실패 기록에 쓸 플랜. try 안에서 정하면 catch 가 못 본다.
      let plan = sub.pendingPlan || sub.plan;
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
        /* 사용자가 만지는 함수들과 같은 자물쇠를 잡는다.

           안 잡으면 이런 일이 난다. 갱신 대상은 '기간이 이미 끝난' 문서라
           subActive 가 false 다. 그래서 해지·환불·플랜 변경은 저절로 막히지만,
           '새 결제' 만은 막히지 않는다("이미 이용 중" 검사를 안 타므로). 배치가
           카드를 긁는 사이에 그 사람이 결제 화면에서 결제하면 같은 사람에게 두
           번 청구되고, periodPayments 는 나중에 쓴 쪽만 남아 다른 한 건은 환불도
           되지 않는다.

           자물쇠를 못 잡으면 건너뛴다. 실패로 적으면 방금 정상적으로 결제한
           사람에게 '결제 실패' 가 뜬다. */
        await withLock(db, d.ref, "renew", async () => {
          /* 자물쇠를 잡는 사이에 상태가 바뀌었을 수 있다. 목록을 만든 시점의
             값을 그대로 믿으면 이미 갱신된 구독을 또 긁는다. */
          const fresh = (await d.ref.get()).data();
          if (!fresh || fresh.status !== "active") return;
          const endMs = fresh.currentPeriodEnd && fresh.currentPeriodEnd.toMillis
            ? fresh.currentPeriodEnd.toMillis() : 0;
          if (endMs > now.getTime()) return;      // 그 사이 새 기간이 시작됐다
          sub = fresh;
          plan = sub.pendingPlan || sub.plan;     // 예약된 다운그레이드를 여기서 적용

          if (sub.cancelAtPeriodEnd) {
            await d.ref.set({ status: "expired", updatedAt: admin.firestore.FieldValue.serverTimestamp() }, { merge: true });
            return;
          }
          const pay = await charge(db, uid, { ...sub, plan }, PRICE[plan],
            `${PLAN_NAME[plan]} 월 구독`, "renew", null,
            `renew_${uid}_${kstDayNo(endMs)}`);
          await d.ref.set({
            plan, pendingPlan: null, status: "active",
            currentPeriodStart: admin.firestore.Timestamp.fromDate(now),
            currentPeriodEnd: admin.firestore.Timestamp.fromDate(addMonth(now)),
            lastPaymentKey: pay ? pay.paymentKey : sub.lastPaymentKey,
            // 새 주기다 — 지난 주기의 결제 건은 여기서 끊는다. 이어 붙이면
            // 환불이 이미 지나간 달의 돈까지 기준에 넣는다.
            periodPayments: pay
              ? [{ key: pay.paymentKey, amount: PRICE[plan], from: now.getTime() }] : [],
            refundDone: admin.firestore.FieldValue.delete(),
            failedAt: admin.firestore.FieldValue.delete(),
            retryCount: admin.firestore.FieldValue.delete(),
            updatedAt: admin.firestore.FieldValue.serverTimestamp(),
          }, { merge: true });
        });
      } catch (e) {
        /* 자물쇠를 못 잡은 것은 실패가 아니다. 그 사람이 지금 결제·환불을 하는
           중이라는 뜻이므로 건드리지 않고 넘어간다 — 다음 날 배치가 다시 본다. */
        if (e && e.kosLocked) {
          console.warn(`[renew] 사용자가 처리 중 — 건너뜀 uid=${uid}`);
          continue;
        }
        // 한도 초과·정지 카드 등. 바로 끊지 않고 상태만 남긴다 — 사용자가 카드를
        // 바꿀 시간을 줘야 한다. 이용 권한은 currentPeriodEnd 가 지나 자연히 닫힌다.
        console.error(`[renew] 실패 uid=${uid}`, e && e.message);
        failed.push(`${uid} · ${plan} · ${(e && e.message) || e}`);
        /* 이번 달 첫 거절이다. 재시도 횟수를 0 으로 다시 놓는다 — 지난달에
           재시도로 되살아난 사람은 그때 쓴 횟수가 남아 있을 수 있고, 그대로
           두면 이번 달에 받을 기회가 그만큼 줄어든다. failedAt 도 오늘로
           새로 적어 재시도 일정을 여기서부터 센다. */
        await d.ref.set({
          status: "past_due", retryCount: 0,
          failedAt: admin.firestore.FieldValue.serverTimestamp(),
          updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        }, { merge: true });
        /* 청구하려던 플랜으로 적는다. 다운그레이드가 예약돼 있었으면 옛 플랜의
           금액을 적게 되는데, 내역에 실제와 다른 금액이 남는다. */
        await writePayment(db, uid, {
          amount: PRICE[plan] || 0, description: "정기결제 실패",
          kind: "failed", status: "failed", plan, paidAt: null,
        });
      }
    }

    /* ── 거절된 카드를 정해진 날에 다시 시도한다 ─────────────
       한 번 거절됐다고 바로 끊지 않는다. 한도 초과·통신 오류처럼 하루 지나면
       되는 경우가 많고, 그걸로 구독이 끊기면 양쪽 다 손해다.

       성공하면 그 순간부터 새 한 달이 시작된다. 실패한 기간은 이미 지나갔고
       그동안 이용도 못 했으므로, 못 쓴 날을 시작점으로 삼을 이유가 없다.

       재시도 중에는 리포트를 볼 수 없다(status 가 active 가 아니다). 이미 낸
       한 달은 다 썼고 다음 달 값은 아직 안 받았기 때문이다. */
    const stuck = await db.collection("subscriptions")
      .where("status", "==", "past_due")
      .limit(400).get();
    if (stuck.size >= 400) {
      console.error("[renew] 재시도 대상이 상한(400)까지 찼다 — 남은 건은 내일로 밀린다");
    }
    console.log(`[renew] 재시도 대상 ${stuck.size}건`);

    for (const d of stuck.docs) {
      const uid = d.id;
      const sub = d.data();
      // 실패 기록에 쓸 플랜. 자물쇠를 잡은 뒤 다시 읽은 값으로 덮어쓴다.
      let plan = sub.pendingPlan || sub.plan;
      try {
        /* 위 갱신 고리와 같은 이유로 계정부터 확인한다. 여기도 카드를 긁는
           자리다 — 탈퇴한 사람의 카드를 긁는 사고는 되돌릴 수가 없다.
           탈퇴하면 status 가 "deleted" 로 바뀌어 이 목록에 들어오지 않지만,
           그 쓰기가 실패했거나 콘솔에서 계정만 지운 경우가 남는다. */
        try {
          await admin.auth().getUser(uid);
        } catch (e) {
          if (e && e.code === "auth/user-not-found") {
            console.warn(`[renew] 재시도 — 계정 없음, 건너뜀 uid=${uid}`);
            await d.ref.set({
              status: "deleted", billingKey: admin.firestore.FieldValue.delete(),
              updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            }, { merge: true });
            continue;
          }
          throw e;
        }

        const failedMs = sub.failedAt && sub.failedAt.toMillis ? sub.failedAt.toMillis() : 0;
        if (!failedMs) {
          /* 언제 실패했는지 모르면 재시도 날짜를 셀 수가 없다. 그냥 넘기면 이
             문서는 영영 past_due 에 머물러 결제도 종료도 되지 않는다 — 조용히
             묶여 있는 것이 가장 나쁘다. 소리를 내고 오늘을 기준일로 잡는다. */
          console.error(`[renew] 재시도 — failedAt 이 없다, 오늘을 기준으로 잡는다 uid=${uid}`);
          await d.ref.set({
            failedAt: admin.firestore.FieldValue.serverTimestamp(),
            retryCount: 0,
            updatedAt: admin.firestore.FieldValue.serverTimestamp(),
          }, { merge: true });
          continue;
        }
        const dayN = kstDayNo(now.getTime()) - kstDayNo(failedMs);
        const tried = sub.retryCount || 0;
        if (tried >= RETRY_DAYS.length) {
          /* 마지막 시도까지 실패하면 그 자리에서 expired 로 닫는다. 여기까지
             왔다는 건 그 쓰기가 실패했다는 뜻이므로 지금 마무리한다. 안 그러면
             매일 이 목록에 올라오면서 아무 일도 일어나지 않는다. */
          console.warn(`[renew] 재시도를 모두 마친 문서를 닫는다 uid=${uid}`);
          await d.ref.set({
            status: "expired", updatedAt: admin.firestore.FieldValue.serverTimestamp(),
          }, { merge: true });
          continue;
        }
        if (dayN < RETRY_DAYS[tried]) continue;        // 아직 그날이 아니다

        await withLock(db, d.ref, "dunning", async () => {
          const fresh = (await d.ref.get()).data();
          // 자물쇠를 잡는 사이에 카드를 바꿔 되살아났을 수 있다
          if (!fresh || fresh.status !== "past_due") return;
          if ((fresh.retryCount || 0) !== tried) return;
          // 목록을 만든 시점의 값을 그대로 믿지 않는다(갱신 고리와 같다).
          plan = fresh.pendingPlan || fresh.plan;

          try {
            const pay = await charge(db, uid, { ...fresh, plan }, PRICE[plan],
              `${PLAN_NAME[plan]} 월 구독`, "retry", null,
              `dun_${uid}_${kstDay()}`);
            /* 성공 — 그 순간부터 새 한 달이다. */
            await d.ref.set({
              plan, pendingPlan: null, status: "active",
              currentPeriodStart: admin.firestore.Timestamp.fromDate(now),
              currentPeriodEnd: admin.firestore.Timestamp.fromDate(addMonth(now)),
              lastPaymentKey: pay ? pay.paymentKey : fresh.lastPaymentKey,
              periodPayments: pay
                ? [{ key: pay.paymentKey, amount: PRICE[plan], from: now.getTime() }] : [],
              refundDone: admin.firestore.FieldValue.delete(),
              failedAt: admin.firestore.FieldValue.delete(),
              retryCount: admin.firestore.FieldValue.delete(),
              updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            }, { merge: true });
            revived.push(`${uid} · ${plan} · ${tried + 1}번째 시도에서 성공`);
          } catch (e) {
            const next = tried + 1;
            const done = next >= RETRY_DAYS.length;
            await d.ref.set({
              retryCount: next,
              // 마지막까지 안 되면 종료한다. 무한정 붙잡고 있을 수는 없다.
              ...(done ? { status: "expired" } : {}),
              updatedAt: admin.firestore.FieldValue.serverTimestamp(),
            }, { merge: true });
            await writePayment(db, uid, {
              amount: PRICE[plan] || 0,
              description: done ? "정기결제 실패(최종)" : `정기결제 재시도 실패(${next}회)`,
              kind: "failed", status: "failed", plan, paidAt: null,
            });
            if (done) gaveUp.push(`${uid} · ${plan} · ${(e && e.message) || e}`);
            console.warn(`[renew] 재시도 ${next}회 실패 uid=${uid}`, e && e.message);
          }
        });
      } catch (e) {
        if (e && e.kosLocked) { console.warn(`[renew] 재시도 건너뜀(처리 중) uid=${uid}`); continue; }
        console.error(`[renew] 재시도 처리 오류 uid=${uid}`, e && e.message);
      }
    }

    /* 카드가 거절된 사람이 있으면 운영자에게 알린다.

       여태 아무 데도 안 알렸다. 사용자는 설정 창을 직접 열기 전에는 자기 카드가
       막힌 줄 모르고, 우리는 몇 명이 그렇게 멈춰 있는지 알 방법이 없었다.
       카드사 쪽 문제로 여러 건이 한꺼번에 막히는 날도 이 메일이 없으면 조용히
       지나간다.

       없는 날은 알리지 않는다 — 매일 '0건' 이 오면 그 알림은 아무도 안 읽는다. */
    if (failed.length || gaveUp.length || revived.length) {
      const sum = [
        failed.length ? `새로 거절 ${failed.length}건` : "",
        revived.length ? `재시도 성공 ${revived.length}건` : "",
        gaveUp.length ? `최종 실패 ${gaveUp.length}건` : "",
      ].filter(Boolean).join(" · ");
      const lines = [];
      if (failed.length) {
        lines.push(`[새로 거절 ${failed.length}건] ${RETRY_DAYS.join("·")}일 뒤에 다시 시도합니다.`,
                   ...failed.slice(0, 20), "");
      }
      if (revived.length) {
        lines.push(`[재시도 성공 ${revived.length}건] 성공한 시점부터 새 이용 기간이 시작됩니다.`,
                   ...revived.slice(0, 20), "");
      }
      if (gaveUp.length) {
        lines.push(`[최종 실패 ${gaveUp.length}건] ${RETRY_DAYS.length}회를 모두 시도했고 이용을 종료했습니다.`,
                   ...gaveUp.slice(0, 20), "");
      }
      await alertOps(`정기결제 — ${sum}`, lines.filter(Boolean));
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
/* ============================================================
   모닝 브리핑을 제시각에 깨운다
   ------------------------------------------------------------
   왜 여기에 있나. 브리핑은 GitHub Actions 가 만드는데, GitHub 의 schedule
   은 "이 시각쯤" 이지 "이 시각" 이 아니다. 밀리는 폭이 예측되지 않는다.

     2026-08-27  06:00 슬롯이 09:23 에 발화 (+3시간 23분)
     2026-08-28  슬롯 여섯 개가 전부 건너뛰거나 밀려, 11:24 에 한 번만 깨어남

   그래서 슬롯을 여섯 개로 늘리고 릴레이 워크플로까지 두었는데, 8월 28일에
   둘 다 못 막았다. 당연하다 — 릴레이도 schedule 로 깨어난다. 같은 줄에
   매달린 두 겹은 두 겹이 아니다. 릴레이는 13:30Z 에 깨어났어야 하는데
   23:01Z 에 깨어났고(+9시간 31분), 그때는 이미 손쓸 시각이 지나 있었다.

   Cloud Scheduler 는 다르다. 이미 이 파일의 purgeUnconsented 가 매일
   12:30 에 정확히 돌고 있다. 그래서 '언제 깨울지' 를 GitHub 밖으로 뺀다.
   workflow_dispatch 는 큐를 거치지 않아 몇 초 안에 뜬다.

   두 번 깨운다. 06:40 은 만들고 기다렸다 07:28 에 올리기 위한 것이고,
   07:15 는 그 사이에 죽었을 때를 위한 예비다. 생성은 그날 브리핑이 이미
   있으면 건너뛰므로(멱등) 두 번 깨워도 과금은 하루 한 번이다.

   토큰이 없으면 아무것도 하지 않는다. 그래도 배포는 되어야 하므로 배포
   워크플로가 자리를 '미설정' 으로 채워 둔다.

   ⚠️ GH_DISPATCH_TOKEN 은 이 저장소의 Actions 에만 쓰기 권한이 있는
      fine-grained 토큰이어야 한다. 넓은 권한을 주면 안 된다.
   ============================================================ */
async function dispatchBrief(reason){
  const token = (GH_DISPATCH_TOKEN.value() || "").trim();
  if(!token || token === SECRET_UNSET){
    console.warn(`[brief] 토큰이 없어 깨우지 못했다 (${reason})`);
    return false;
  }
  try{
    const res = await fetch(
      "https://api.github.com/repos/kosairesearch/kosairesearch.github.io" +
      "/actions/workflows/morning_brief.yml/dispatches", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ ref: "main" }),
      });
    if(res.status !== 204){
      const t = await res.text();
      console.error(`[brief] 깨우기 실패 HTTP ${res.status} (${reason}):`, t.slice(0, 300));
      return false;
    }
    console.log(`[brief] 깨웠다 (${reason})`);
    return true;
  }catch(e){
    console.error(`[brief] 깨우기 오류 (${reason}):`, e && e.message);
    return false;
  }
}

/* 실패를 소리나게 만든다.

   여태 브리핑이 안 나가도 아무 데도 알리지 않았다. 8월 28일에도 사람이
   오후에야 알아챘다. 조용히 실패하는 장치는 없는 장치와 같다 — 예비를
   몇 겹으로 쌓아도 그것들이 다 죽은 것을 모르면 소용이 없다.

   메일이 안 가도 던지지 않는다. 알림이 실패했다고 브리핑까지 막을 이유가
   없다. */
async function alertOps(subject, lines){
  const key = (RESEND_API_KEY.value() || "").trim();
  if(!key) { console.warn("[alert] RESEND 키 없음:", subject); return; }
  try{
    const html = mailLayout({
      lang: "ko", heading: subject,
      intro: lines.map(esc).join("<br>"),
      btnText: "실행 기록 보기",
      link: "https://github.com/kosairesearch/kosairesearch.github.io/actions/workflows/morning_brief.yml",
      outro: "이 메일은 KOSAI 운영 알림입니다.",
    });
    const resend = new Resend(key);
    await resend.emails.send({
      from: MAIL_FROM, to: "hello@kosai.kr", subject: `[KOSAI] ${subject}`, html });
  }catch(e){
    console.error("[alert] 발송 실패:", e && e.message);
  }
}

/* 만들고 기다렸다 07:28 에 올린다. 워크플로가 그 대기를 스스로 한다. */
exports.wakeMorningBrief = onSchedule(
  { region: REGION, schedule: "40 6 * * 1-5", timeZone: "Asia/Seoul",
    secrets: [GH_DISPATCH_TOKEN, RESEND_API_KEY] },
  async () => {
    if(!(await dispatchBrief("06:40 본 발화"))){
      await alertOps("모닝 브리핑을 깨우지 못했습니다", [
        "06:40 발화가 GitHub 워크플로를 깨우지 못했습니다.",
        "토큰이 만료됐거나 권한이 부족할 수 있습니다.",
        "07:15 예비가 한 번 더 시도합니다.",
      ]);
    }
  }
);

/* 예비. 앞엣것이 죽었으면 여기서 다시 깨운다. 이미 올라갔으면 워크플로가
   스스로 건너뛴다. */
exports.wakeMorningBriefBackup = onSchedule(
  { region: REGION, schedule: "15 7 * * 1-5", timeZone: "Asia/Seoul",
    secrets: [GH_DISPATCH_TOKEN, RESEND_API_KEY] },
  async () => { await dispatchBrief("07:15 예비"); }
);

/* 파수꾼. 08:00 에 오늘 브리핑 워크플로가 돌았는지 확인한다.

   '깨우기가 실패했나' 만 보면 부족하다. 깨우는 데 성공하고 그 뒤에
   죽는 경우가 실제로 더 많았다(생성 실패·정지 조건). 결과를 본다.

   휴장일에는 워크플로가 스스로 아무것도 하지 않고 성공으로 끝난다.
   그래서 '실행이 있었고 실패하지 않았다' 를 기준으로 삼는다 — 한국
   공휴일 목록을 여기서 다시 관리하지 않아도 된다. */
exports.watchMorningBrief = onSchedule(
  { region: REGION, schedule: "0 8 * * 1-5", timeZone: "Asia/Seoul",
    secrets: [GH_DISPATCH_TOKEN, RESEND_API_KEY] },
  async () => {
    const token = (GH_DISPATCH_TOKEN.value() || "").trim();
    if(!token || token === SECRET_UNSET) return;

    /* 오늘(KST) 0시 이후에 만들어진 실행만 본다. */
    const kst = new Date(Date.now() + 9 * 3600 * 1000);
    const today = kst.toISOString().slice(0, 10);
    const since = new Date(Date.parse(today + "T00:00:00+09:00")).toISOString();

    let runs = null;
    try{
      const res = await fetch(
        "https://api.github.com/repos/kosairesearch/kosairesearch.github.io" +
        `/actions/workflows/morning_brief.yml/runs?per_page=20&created=%3E${since}`, {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
          }});
      if(res.ok) runs = (await res.json()).workflow_runs || [];
    }catch(e){
      console.error("[watch] 실행 조회 실패:", e && e.message);
    }

    if(runs === null){
      await alertOps("브리핑 상태를 확인하지 못했습니다", [
        "08:00 점검이 GitHub 실행 기록을 읽지 못했습니다.",
        "브리핑이 나갔는지는 직접 확인하여 주시기 바랍니다.",
      ]);
      return;
    }
    if(runs.length === 0){
      await alertOps("모닝 브리핑이 오늘 한 번도 돌지 않았습니다", [
        `${today} 08:00 기준으로 브리핑 워크플로 실행이 하나도 없습니다.`,
        "깨우는 장치가 전부 실패했다는 뜻입니다.",
      ]);
      return;
    }
    const good = runs.some(r => r.conclusion === "success" || r.status !== "completed");
    if(!good){
      await alertOps("모닝 브리핑이 실패했습니다", [
        `${today} 실행 ${runs.length}건이 모두 실패했습니다.`,
        "생성이나 발행 단계에서 멈춘 것입니다. 실행 기록을 확인하여 주시기 바랍니다.",
      ]);
    }
  }
);

/* 시험용. 월요일 아침까지 기다렸다가 안 나가는 것을 확인하는 것은 너무 늦다.

   관리자 화면의 버튼이 이걸 부른다. 토큰이 제대로 등록됐는지, dispatch 가
   실제로 워크플로를 깨우는지를 오늘 확인할 수 있다.

   장중에 부르면 워크플로는 정지 조건(stale_data)에 걸려 멈춘다. 그건
   정상이고, 우리가 보려는 것은 '실행이 만들어지는가' 까지다. 그 지점은
   생성 API 를 부르기 전이라 과금도 없다. */
exports.adminWakeBrief = onCall(
  { region: REGION, cors: true, secrets: [GH_DISPATCH_TOKEN] },
  async (req) => {
    assertAdmin(req);
    const ok = await dispatchBrief("관리자 수동 시험");
    return { ok };
  }
);

/* ── 마케팅 수신 동의 2년 재확인 ─────────────────────────────────
   개인정보처리방침에 "동의를 받은 날부터 2년마다 수신 동의 여부를 확인
   합니다" 라고 적어 두었다(정보통신망법 시행령 제62조의3). 그런데 여태
   관리자 화면에 '2년 재확인 대상' 숫자를 세는 것까지만 해 두었다. 세기만
   하고 보내지 않으면 지키지 않는 약속이다.

   시계를 어디서 재는가. marketingAt(최초 동의일) 하나만 보면, 한 번 대상이
   된 사람은 재확인 메일을 보내도 영원히 대상으로 남는다 — 시계가 돌지
   않는다. 그래서 marketingRecheckedAt 을 따로 두고 둘 중 나중 것을 기준
   으로 삼는다. 최초 동의일은 증거라 절대 덮지 않는다.

   무응답은 동의 유지로 본다(같은 조). 그러니 이 함수는 동의를 다시 받아
   내는 것이 아니라, 알리고 철회할 길을 열어 두고 그 사실을 남기는 것이다.

   한 번에 보내는 상한을 둔다. 이 함수는 사람 확인 없이 매달 돌면서 실제
   메일을 내보낸다 — 조건을 잘못 쓰면 전 회원에게 한꺼번에 나간다. 상한에
   걸리면 남은 사람은 다음 달에 처리되고 로그에 그 사실이 남는다.

   dryRun 으로 부르면 대상만 세고 아무것도 보내지 않는다. 첫 대상이 나오는
   것은 2028년이라, 그때까지 한 번도 못 돌려 보고 두면 그날 처음 터진다.
   관리자 화면 버튼이 이 길로 들어온다. */
async function runMarketingRecheck({ dryRun = true, limit = 100 } = {}){
  const db = admin.firestore();
  const now = Date.now();
  const ms = (t) => (t && t.toDate ? t.toDate().getTime() : 0);

  const out = { dryRun, due: 0, sent: 0, failed: 0, noEmail: 0, capped: false, targets: [] };

  let snap;
  try{
    snap = await db.collection("users").limit(5000).get();
  }catch(e){
    console.error("[recheck] 회원 조회 실패:", e && e.message);
    return Object.assign(out, { error: "user_query_failed" });
  }

  for(const d of snap.docs){
    const u = d.data() || {};
    const c = u.consents || {};
    if(c.marketing !== true) continue;

    /* 최초 동의일과 마지막 재확인일 중 나중 것. 둘 다 없으면 판단할 수
       없으므로 건드리지 않는다 — 모르는 것을 '2년 지났다' 로 볼 수 없다. */
    const base = Math.max(ms(u.marketingAt), ms(u.marketingRecheckedAt), ms(c.agreedAt));
    if(!base) continue;
    if(now < recheckDueAt(base) - RECHECK_LEAD_DAYS * 86400000) continue;
    out.due++;

    const email = String(u.email || "").trim().toLowerCase();
    if(!emailOk(email)){ out.noEmail++; continue; }   // 카카오처럼 주소가 없는 계정
    if(out.sent >= limit){ out.capped = true; continue; }

    const agreedAtText = new Intl.DateTimeFormat("sv-SE",
      { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" })
      .format(new Date(ms(u.marketingAt) || base));

    if(dryRun){
      out.targets.push({ uid: d.id, email, agreedAt: agreedAtText });
      out.sent++;                                     // 미리 보기에서는 '보낼 수' 다
      continue;
    }

    const mail = marketingRecheckMail("ko", agreedAtText);
    try{
      const resend = new Resend(RESEND_API_KEY.value());
      const { error } = await resend.emails.send({
        from: MAIL_FROM, to: email, subject: mail.subject, html: mail.html });
      if(error) throw new Error(error.message || "resend_failed");
    }catch(e){
      /* 한 사람 실패가 나머지를 막지 않는다. 시계도 돌리지 않는다 —
         못 보냈으면 다음 달에 다시 대상이 되어야 한다. */
      console.error("[recheck] 발송 실패", d.id, e && e.message);
      out.failed++;
      continue;
    }

    /* 보낸 뒤에만 시계를 돌린다. 순서를 뒤집으면 발송이 실패했는데 2년을
       더 기다리게 된다. */
    try{
      await d.ref.set({
        marketingRecheckedAt: admin.firestore.FieldValue.serverTimestamp(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });
    }catch(e){
      console.error("[recheck] 시각 기록 실패", d.id, e && e.message);
    }
    await logConsent(db, d.id, "marketing_recheck",
      { email, agreedAt: agreedAtText }, null);
    out.sent++;
  }

  console.log(`[recheck] ${dryRun ? "미리 보기" : "발송"} — 대상 ${out.due}`,
    `보냄 ${out.sent} 실패 ${out.failed} 주소없음 ${out.noEmail}`,
    out.capped ? "(상한에 걸림)" : "");
  return out;
}

/* 매일 12:40 KST.

   ⚠️ 처음에는 매달 1일로 두었다. 틀렸다. 조문이 기한을 이렇게 정한다.

       수신동의를 받은 날부터 2년마다(매 2년이 되는 해의 수신동의를 받은
       날과 같은 날 전까지를 말한다) … 확인하여야 한다

   기한이 계정마다 다르고, '그 날 전까지' 다. 달마다 돌면 15일에 기한이
   오는 사람은 다음 달 1일에야 확인하게 되어 보름 늦는다. 늦으면 그 사이에
   나간 광고는 확인하지 않은 동의로 보낸 것이 된다.

   그래서 매일 돌고, 기한보다 앞서 보낸다(RECHECK_LEAD_DAYS). 앞당겨 보내는
   것은 조문이 막지 않는다 — 막는 것은 늦는 것이다. */
exports.marketingRecheck = onSchedule(
  { region: REGION, schedule: "40 3 * * *", timeZone: "Etc/UTC", secrets: [RESEND_API_KEY] },
  async () => {
    const r = await runMarketingRecheck({ dryRun: false, limit: 100 });
    /* 나간 날에만 알린다.

       사람 확인 없이 회원에게 실제 메일을 내보내는 함수다. 그런데 아무
       말도 없이 나가면 운영자는 무엇이 언제 나갔는지 알 길이 없고,
       잘못 나가도 알아챌 자리가 없다. 자동으로 하는 것과 조용히 하는 것은
       다르다.

       대상이 없는 날은 알리지 않는다 — 2년 가까이 매일 '0건' 메일이
       오면 그 알림은 아무도 안 읽게 된다. */
    if(r && (r.sent || r.failed)){
      await alertOps("마케팅 수신 동의 2년 재확인 발송", [
        `보냄 ${r.sent}건 · 실패 ${r.failed}건 · 주소 없음 ${r.noEmail}건`,
        `대상 ${r.due}건${r.capped ? " (상한에 걸려 나머지는 내일 이어서 보냅니다)" : ""}`,
        "정보통신망법 시행령 제62조의3에 따른 법정 확인 안내입니다.",
      ]);
    }
  }
);

/* 관리자 화면에서 지금 돌려 보는 길. 기본은 미리 보기다 — 실제 발송은
   dryRun:false 를 명시해야 한다. 동의 안내 메일과 같은 방식이다. */
exports.adminMarketingRecheck = onCall(
  { region: REGION, cors: true, secrets: [RESEND_API_KEY] },
  async (req) => {
    assertAdmin(req);
    const dryRun = (req.data || {}).dryRun !== false;
    return await runMarketingRecheck({ dryRun, limit: 100 });
  }
);

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

    /* 유령 문서 — Auth 에는 없는데 users 문서만 남은 것.

       위 훑기는 Auth 목록을 돌기 때문에 이런 문서를 아예 보지 못한다.
       그래서 영영 남는다. 관리자 화면에는 '계정 없음' 인 회원으로 보이고,
       중복 검사가 그 이메일을 살아 있는 계정으로 믿어 멀쩡한 가입을 막은
       적도 있다.

       실제로 어떻게 생기나. 동의 화면의 취소가 브라우저에서 Auth 사용자만
       지우고 있었다 — 규칙으로 users 쓰기를 닫아 두었으니 문서는 지울
       수가 없었다. 그쪽은 이제 서버 deleteAccount 를 거치게 고쳤고, 여기는
       그렇게 이미 생긴 것들과 앞으로 다른 경로로 생길 것을 치운다.

       조회가 실패하면 아무것도 지우지 않는다. '못 읽었다' 를 '없다' 로
       읽으면 멀쩡한 회원 문서를 지우게 된다. */
    let orphan = 0;
    try {
      const docs = (await db.collection("users").limit(2000).get()).docs;
      for (let i = 0; i < docs.length && orphan < MAX_DELETE; i += 100) {
        const part = docs.slice(i, i + 100);
        const res = await admin.auth().getUsers(part.map((d) => ({ uid: d.id })));
        const live = new Set((res.users || []).map((u) => u.uid));
        for (const d of part) {
          if (live.has(d.id)) continue;
          if (orphan >= MAX_DELETE) break;
          try {
            await d.ref.delete();
            orphan++;
            console.log(`[purge] 유령 문서 삭제 ${d.id}`);
          } catch (e) {
            console.warn(`[purge] 유령 문서 삭제 실패 ${d.id}: ${e.code || e.message}`);
          }
        }
      }
    } catch (e) {
      console.warn("[purge] 유령 문서 훑기 실패(아무것도 지우지 않음):", e && e.message);
    }
    if (orphan) console.log(`[purge] 유령 문서 ${orphan}건 정리`);

    if (capped) {
      console.warn(`[purge] ⚠️ 한 번 상한(${MAX_DELETE})에 걸렸다. 하루 대상이 이렇게 많은 것은 ` +
                   `정상이 아니다 — 조건이 틀렸는지 사람이 확인할 것.`);
    }
  }
);
