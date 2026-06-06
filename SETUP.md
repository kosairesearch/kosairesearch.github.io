# KOS ai — 로그인 설정 가이드

이 사이트는 정적 호스팅(GitHub Pages)이고, 로그인은 **Firebase Authentication**으로 동작합니다.
구글·이메일은 Firebase만으로 무료로 작동하고, 카카오·네이버는 무료 한도 안에서 동작하도록
**Cloud Functions 백엔드(`functions/`)** 가 커스텀 토큰을 발급합니다.

채워야 할 자리는 모두 `[대괄호]` 플레이스홀더입니다.

---

## A. 구글 + 이메일/비밀번호 (필수, 무료)

1. **프로젝트 생성** — https://console.firebase.google.com → "프로젝트 만들기"
2. **로그인 방법 켜기** — Authentication → 시작하기 → Sign-in method
   - **이메일/비밀번호** 사용 설정
   - **Google** 사용 설정 (지원 이메일 선택)
3. **승인된 도메인** — Authentication → 설정 → 승인된 도메인에 추가
   - `kosairesearch.github.io`
   - (로컬 테스트 시) `localhost`
4. **웹앱 등록 & 설정값 복사** — 프로젝트 설정(⚙️) → 일반 → 내 앱 → 웹앱(`</>`) 추가
   → 표시되는 값으로 **`firebase-config.js`** 의 `firebaseConfig` 교체:
   ```js
   apiKey, authDomain, projectId, appId
   ```
5. 커밋·푸시 → 구글·이메일 로그인 작동 ✅

> 여기까지만 해도 로그인은 완전히 동작합니다. 카카오·네이버가 필요 없으면 B는 건너뛰세요.

---

## B. 카카오 · 네이버 (선택, Cloud Functions)

### B-1. 카카오 앱 만들기 — https://developers.kakao.com
- 내 애플리케이션 → 애플리케이션 추가
- **앱 키 → REST API 키** 복사 → `firebase-config.js` 의 `SOCIAL.kakaoRestKey`
- 카카오 로그인 → 활성화 ON
- **Redirect URI** 등록(두 개 모두):
  - `https://kosairesearch.github.io/Login.html`
  - `https://kosairesearch.github.io/Signup.html`
- 동의 항목: 닉네임(필수), 이메일(선택) 설정
- (보안 → Client Secret을 켰다면 그 값을 아래 `KAKAO_CLIENT_SECRET` 시크릿에 저장)

### B-2. 네이버 앱 만들기 — https://developers.naver.com/apps
- 애플리케이션 등록 → 사용 API: **네이버 로그인**
- **Client ID** 복사 → `firebase-config.js` 의 `SOCIAL.naverClientId`
- **Client Secret** 복사 → 아래 `NAVER_CLIENT_SECRET` 시크릿에 저장
- 서비스 URL: `https://kosairesearch.github.io`
- **Callback URL** 등록(두 개 모두):
  - `https://kosairesearch.github.io/Login.html`
  - `https://kosairesearch.github.io/Signup.html`

### B-3. Firebase CLI & 배포
```bash
# 1) CLI 설치 & 로그인
npm install -g firebase-tools
firebase login

# 2) 이 저장소에서 프로젝트 연결 (.firebaserc 의 [FIREBASE_PROJECT_ID] 자동 설정)
firebase use --add        # 위에서 만든 프로젝트 선택

# 3) Blaze(종량제) 플랜으로 업그레이드 필요 (Functions 사용 조건)
#    콘솔 → 요금제 → Blaze. 무료 한도 내에서는 청구 0원, 예산 알림 설정 권장.

# 4) 비밀키 등록 (서버에만 저장됨)
firebase functions:secrets:set KAKAO_REST_KEY        # 카카오 REST API 키
firebase functions:secrets:set KAKAO_CLIENT_SECRET   # 안 쓰면 빈 값으로 그냥 Enter
firebase functions:secrets:set NAVER_CLIENT_ID       # 네이버 Client ID
firebase functions:secrets:set NAVER_CLIENT_SECRET   # 네이버 Client Secret

# 5) 의존성 설치 & 배포
cd functions && npm install && cd ..
firebase deploy --only functions
```

> 배포 리전은 `asia-northeast3`(서울)이며 `firebase-config.js` 의 `SOCIAL.functionsRegion`,
> `functions/index.js` 의 `REGION` 과 일치해야 합니다(기본값 동일).

배포가 끝나면 `firebase-config.js` 의 `SOCIAL.kakaoRestKey` / `naverClientId` 를 커밋·푸시하세요.
한국어 모드에서 카카오·네이버 버튼이 실제로 동작합니다 ✅

---

## 동작 원리 (요약)
```
[브라우저] 카카오/네이버 버튼 클릭
   → 카카오/네이버 동의화면으로 이동
   → ?code= 로 Login.html(또는 Signup.html) 복귀
   → Cloud Functions(socialLogin) 호출 (code 전달)
[서버]  code → 카카오/네이버 액세스토큰 → 프로필
   → Firebase 커스텀 토큰 발급
[브라우저] signInWithCustomToken → 로그인 완료
```
카카오·네이버 사용자는 **일반 Firebase 사용자**로 집계되어 월 5만 MAU 무료 한도에 포함됩니다.

---

## 비용 요약
| 항목 | 비용 |
| --- | --- |
| GitHub Pages 호스팅 | 무료 |
| 구글·이메일 로그인 | 월 50,000 MAU까지 무료 |
| 카카오·네이버(이 방식) | Functions 무료 한도(월 200만 호출) 내 사실상 0원 |
| SMS/문자 인증 | 사용 안 함 |

Blaze 플랜은 카드 등록이 필요하지만, 무료 한도를 넘기 전에는 청구되지 않습니다.

---

## 채워야 할 플레이스홀더 한눈에
| 위치 | 값 |
| --- | --- |
| `firebase-config.js` → `firebaseConfig` | apiKey / authDomain / projectId / appId |
| `firebase-config.js` → `SOCIAL.kakaoRestKey` | 카카오 REST API 키 |
| `firebase-config.js` → `SOCIAL.naverClientId` | 네이버 Client ID |
| `.firebaserc` → `[FIREBASE_PROJECT_ID]` | `firebase use --add` 시 자동 |
| Functions 시크릿 | KAKAO_REST_KEY / KAKAO_CLIENT_SECRET / NAVER_CLIENT_ID / NAVER_CLIENT_SECRET |
| `Privacy.html` / `Terms.html` | `[운영자명]` · `[연락처 이메일]` |
