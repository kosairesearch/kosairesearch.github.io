# KOSAI X 멘션 자동응답 봇

누군가 X에서 **`@kosai_x 삼성전자`** 처럼 멘션하면, 해당 한국 주식 설명을 **답글로 자동
게시**한다. 한글 멘션이면 한국어, 아니면 영어로 답한다.

## 어떻게 도는가 (아키텍처)

```
멘션 발생 ──X 웹훅──▶ /api/webhook (CRC 검증·즉시 200) ──▶ 중복체크 → Redis 큐 적재
                                                              │ (kick, 안 기다림)
                                                              ▼
                                  /api/work ── 큐에서 1건 pop → 종목매칭 → (캐시/생성) → X 답글
                                      └ 남으면 자기연쇄로 다음 건
```

- **감지 = X Activity API 웹훅** (pay-per-use 티어, 실시간). `/api/webhook`이
  CRC(GET, HMAC-SHA256)와 이벤트(POST)를 받고, 무조건 즉시 200을 반환한 뒤
  실제 처리는 `/api/work`(maxDuration 300초)에 넘긴다.
- **답글 게시 = X API POST /2/tweets** (OAuth1.0a, 표준 라이브러리 서명).
- **서술 생성 = Claude + web search** — 회사 정의/사업/최근/리스크만 문장으로. **숫자 지표는
  코드가** 채운다(모델이 숫자를 못 지어내게). 영어 답글은 가격·시총에 달러 환산 병기(환율 1일 캐시).
- **캐시 = Upstash Redis** — 종목_언어별 서술은 첫 멘션 때 생성·저장 후 재사용
  (`CACHE_STALE_MONTHS` 지나면 재생성). 지표는 매번 실시간. 처리한 멘션ID 저장으로 **중복 답글 방지**.
- 예비 경로: 웹훅이 막히는 상황이 오면 `/api/poll`(Apify 폴링 + 외부 크론)로 전환 가능
  — 코드가 남아 있고 `APIFY_TOKEN`만 넣으면 된다.

## 파일 구조
```
x-bot/
  api/webhook.js   X 웹훅 수신 — CRC 검증 + 멘션 큐 적재 (Node)
  api/work.py      큐 1건 처리 — 매칭·생성·게시 (maxDuration 300s)
  api/preview.py   게시 없이 답글 미리보기 (품질확인용)
  api/health.py    상태/환경변수 점검
  api/poll.py      (예비) Apify 폴링 감지 — 웹훅 불가 시에만
  lib/             tickers·quotes·dart·narrative·compose·xclient·store·pipeline·kick
  data/tickers.json   전 상장종목 매칭표(build_tickers.py 생성)
  scripts/build_tickers.py     종목표 재생성(신규상장 반영)
  scripts/build_corpmap.py     종목코드→DART corp_code (선택)
  scripts/register_webhook.py  X 웹훅 등록 + 계정 구독 (배포 후 1회)
  vercel.json      함수 설정(work 300s, lib/data 포함)
```

## 배포 온보딩 (계정 없는 상태에서 순서대로)

### 1) X 개발자 계정 + 앱 (pay-per-use 콘솔)
1. https://developer.x.com → 봇 계정(@kosai_x)으로 로그인 → 개발자 프로그램 가입
   (사용 사례 서술 + 약관 동의). ※ 계정에 **인증된 전화번호** 필수.
2. 콘솔 → **앱** → 새 클라이언트 애플리케이션 생성 (Environment: **Production**).
3. 앱 권한을 **Read and Write**로 설정.
4. 키 4개 발급 (뜨는 즉시 복사):
   **API Key / API Key Secret** + **Access Token / Access Token Secret**(Read and Write)
   → `X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET`
5. 크레딧: 답글 게시가 시작되기 전까지는 $0으로 진행 가능. 실전 테스트 직전에
   **$10 충전, 자동충전 OFF** (콘솔 결제 메뉴).

### 2) Upstash Redis (무료)
1. https://upstash.com → **GitHub으로 로그인**.
2. **Create Database** → Redis → Free.
3. 상세 → **REST API** 섹션의 `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` 복사.

### 3) Vercel (무료)
1. https://vercel.com → **Continue with GitHub**.
2. **Add New → Project** → `kosairesearch/kosairesearch.github.io` import.
3. **Root Directory = `x-bot`** 로 설정(중요 — 이 하위폴더만 배포).
4. **Environment Variables**에 `.env.example`의 값들 입력. 값은 여기에만.
5. Deploy → URL(예: `https://kosai-x-bot.vercel.app`)을 `APP_URL`에 넣고 **재배포**.

### 4) 웹훅 등록 (배포 후 1회)
콘솔 **툴박스 → 웹훅**에서 URL `https://<APP_URL>/api/webhook` 등록 + **이벤트 구독**에서
봇 계정 구독. UI가 없거나 실패하면 스크립트:
```bash
export X_API_KEY=.. X_API_SECRET=.. X_ACCESS_TOKEN=.. X_ACCESS_SECRET=..
export WEBHOOK_URL=https://<APP_URL>/api/webhook
python x-bot/scripts/register_webhook.py
```
등록 순간 X가 CRC 검증을 보내므로 **배포가 먼저** 끝나 있어야 한다.

### 5) DART corp_code 맵 (선택 — 최근 공시용)
```bash
DART_API_KEY=<키> python x-bot/scripts/build_corpmap.py
git add x-bot/data/corpmap.json && git commit -m "corpmap" && git push
```
없어도 최근 사건은 web search가 커버한다.

### 6) 확인
- `https://<APP_URL>/api/health` → 모든 키 `set` 인지.
- `https://<APP_URL>/api/preview?q=삼성전자&key=<POLL_SECRET>` → 답글 문구 확인(게시 안 됨).
- 다른 계정에서 **`@kosai_x 삼성전자`** 멘션 → 수십 초 내 답글 확인.

## 환경변수
| 변수 | 출처 | 필수 |
|---|---|---|
| ANTHROPIC_API_KEY | 기존 KOSAI 키 | ✅ |
| X_API_KEY / X_API_SECRET | X 앱 Consumer Keys (Secret은 CRC에도 사용) | ✅ |
| X_ACCESS_TOKEN / X_ACCESS_SECRET | X 앱 Access Token(R&W) | ✅ |
| BOT_HANDLE | 봇 핸들(예: kosai_x) | ✅ |
| UPSTASH_REDIS_REST_URL / _TOKEN | Upstash | ✅ |
| APP_URL | 배포 URL | ✅ |
| POLL_SECRET | 임의 랜덤 문자열 | ✅ |
| DART_API_KEY | 기존 DART | 선택 |
| APIFY_TOKEN | 예비 폴링 경로에만 | 선택 |
| NEWS_MODEL / DATA_BASE / USE_PYKRX / CACHE_STALE_MONTHS / WEB_SEARCH_MAX | 기본값 있음 | 선택 |

## 월 예상 비용
- **X API**: pay-per-use — 웹훅 이벤트 수신 + 답글 게시 건당 과금. 소규모 봇이면 **$10
  크레딧으로 수개월**. 자동충전 OFF면 잔액 이상 절대 안 나감.
- **Vercel**: Hobby = **$0**. / **Upstash Redis**: Free = **$0**.
- **Claude**: 종목당 최초 1회 web search 생성분만(캐시 재사용) → 월 몇 달러 이내.
→ 합계 **대략 월 $0~5** 수준.

## 이후 관리
- **X 크레딧**: developer.x.com 대시보드 '남은 크레딧' 확인, 필요 시 소액 충전(자동충전 OFF 유지).
- **캐시 갱신**: 서술은 `CACHE_STALE_MONTHS`(기본 3개월) 지나면 자동 재생성.
- **종목표 갱신**: 신규 상장 반영하려면 가끔 `python x-bot/scripts/build_tickers.py` 후 커밋.
- **별칭 추가**: `scripts/build_tickers.py`의 `ALIAS_TO_TICKER`에 추가 후 재빌드·커밋.
- **웹훅 상태**: 콘솔 툴박스→웹훅에서 valid 여부 확인. X가 CRC 재검증에 실패하면
  무효화되므로, 그 경우 `register_webhook.py`를 다시 실행.
