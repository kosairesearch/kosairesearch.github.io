# KOSAI X 멘션 자동응답 봇

누군가 X에서 **`@kosai_x 삼성전자`** 처럼 멘션하면, 해당 한국 주식 설명을 **답글로 자동
게시**한다. 한글 멘션이면 한국어, 아니면 영어로 답한다.

## 어떻게 도는가 (아키텍처)

```
외부 크론(1분) ──GET──▶ /api/poll ──(Apify로 @kosai_x 멘션 감지)──▶ 새 멘션을 Redis 큐에 적재
                                                                        │ (자기연쇄 kick)
                                                                        ▼
                            /api/work ◀──크론 백스톱──  큐에서 1건 pop → 종목매칭 → (캐시/생성) → X 답글
```

- **감지 = Apify 스크래핑** (X 웹훅/Activity API는 Enterprise 전용·초고가라 회피). 1~2분 지연.
- **답글 게시 = X API Free 티어** (POST /2/tweets, 월 1,500건까지 무료).
- **서술 생성 = Claude + web search** — 회사 정의/사업/최근/리스크만 문장으로. **숫자 지표는
  코드가** kosai.kr 일일 데이터에서 계산해 채운다(모델이 숫자를 못 지어내게).
- **캐시 = Upstash Redis** — 종목_언어별 서술은 첫 멘션 때 생성·저장 후 재사용(N개월 후 재생성).
  지표는 매번 실시간. 처리한 멘션ID 저장으로 **중복 답글 방지**.

## 파일 구조
```
x-bot/
  api/poll.py      크론이 부름 — 멘션 감지 + 큐 적재
  api/work.py      큐 1건 처리 — 매칭·생성·게시 (maxDuration 60s)
  api/preview.py   게시 없이 답글 미리보기 (X 승인 전 품질확인용)
  api/health.py    상태/환경변수 점검
  lib/             tickers·quotes·dart·narrative·compose·xclient·store·pipeline·kick
  data/tickers.json   전 상장종목 매칭표(build_tickers.py 생성)
  data/corpmap.json   종목코드→DART corp_code (build_corpmap.py 생성, 선택)
  scripts/         build_tickers.py, build_corpmap.py (오프라인 빌드)
  vercel.json      함수 설정(maxDuration 60, lib/data 포함)
```

## 배포 온보딩 (계정 없는 상태에서 순서대로)

### 1) X 개발자 계정 + 앱
1. https://developer.x.com → 로그인(봇으로 쓸 계정 @kosai_x) → **Sign up for Free**.
2. Free 티어로 가입(글쓰기 월 1,500건 무료 — 답글 게시엔 충분, 결제 불필요).
3. Developer Portal → **Projects & Apps** → 앱 생성.
4. 앱 **Settings → User authentication settings → Set up**:
   - App permissions: **Read and Write**
   - Type: **Web App / Automated App or Bot**
   - Callback URL/Website: 아무 값(예: `https://kosai.kr`) — 지금은 안 씀.
5. **Keys and tokens** 탭에서 4개 발급:
   - **API Key / API Key Secret** (= Consumer Keys)
   - **Access Token / Access Token Secret** — 반드시 **Read and Write** 권한으로 생성
   → `X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_SECRET`

### 2) Upstash Redis (무료)
1. https://upstash.com → **GitHub으로 로그인**.
2. **Create Database** → Redis → Region은 아무거나(글로벌) → Free.
3. 데이터베이스 상세 → **REST API** 섹션의 `UPSTASH_REDIS_REST_URL`,
   `UPSTASH_REDIS_REST_TOKEN` 복사.

### 3) Vercel (무료)
1. https://vercel.com → **Continue with GitHub**.
2. **Add New → Project** → `kosairesearch/kosairesearch.github.io` import.
3. **Root Directory = `x-bot`** 로 설정(중요 — 이 하위폴더만 배포).
4. **Environment Variables**에 `.env.example`의 값들을 입력(아래 표 참고). 값은 여기에만.
5. Deploy. 배포되면 URL(예: `https://kosai-x-bot.vercel.app`)이 나온다.
   → 그 URL을 `APP_URL` 환경변수에 넣고 **재배포**(자기연쇄에 필요).

### 4) DART corp_code 맵 (선택 — 최근 공시용)
로컬에서 한 번:
```
DART_API_KEY=<키> python x-bot/scripts/build_corpmap.py
git add x-bot/data/corpmap.json && git commit -m "corpmap" && git push
```
없어도 최근 사건은 web search가 커버한다.

### 5) 외부 크론 (1분 주기, 무료)
https://cron-job.org → 가입 → **Create cronjob** 2개:
- `https://<APP_URL>/api/poll?key=<POLL_SECRET>` — 매 1분
- `https://<APP_URL>/api/work?key=<POLL_SECRET>` — 매 1분 (백스톱)

### 6) 확인
- `https://<APP_URL>/api/health` → 모든 키 `set` 인지.
- `https://<APP_URL>/api/preview?q=삼성전자&key=<POLL_SECRET>` → 답글 문구가 나오면 생성 OK.
- 다른 계정에서 **`@kosai_x 삼성전자`** 멘션 → 1~2분 내 답글 확인.

## 환경변수
| 변수 | 출처 | 필수 |
|---|---|---|
| ANTHROPIC_API_KEY | 기존 KOSAI 키 | ✅ |
| APIFY_TOKEN | 기존 Apify | ✅ |
| BOT_HANDLE | 봇 핸들(예: kosai_x) | ✅ |
| X_API_KEY / X_API_SECRET | X 앱 Consumer Keys | ✅ |
| X_ACCESS_TOKEN / X_ACCESS_SECRET | X 앱 Access Token(R&W) | ✅ |
| UPSTASH_REDIS_REST_URL / _TOKEN | Upstash | ✅ |
| APP_URL | 배포 URL | ✅ |
| POLL_SECRET | 임의 랜덤 문자열 | ✅ |
| DART_API_KEY | 기존 DART | 선택 |
| NEWS_MODEL / DATA_BASE / CACHE_STALE_MONTHS / WEB_SEARCH_MAX | 기본값 있음 | 선택 |

## 월 예상 비용
- **X API**: Free 티어 = **$0** (답글 월 1,500건 이내).
- **Vercel**: Hobby = **$0**.
- **Upstash Redis**: Free 티어 = **$0** (일 1만 커맨드 이내).
- **cron-job.org**: **$0**.
- **Apify**: 1분마다 멘션 검색(pay-per-result). 결과 없는 조회는 거의 무료 → 보통 **월 몇 달러 이내**.
- **Claude**: 종목당 최초 1회 web search 생성분만. 캐시되므로 인기 종목이 반복돼도 추가비용 거의 없음.
→ 합계 **대략 월 $0~5** 수준.

## 이후 관리
- **Apify 잔액**: apify.com 대시보드 Usage 확인. 자동충전 끄고 필요 시 소액 충전.
- **X 사용량**: developer.x.com Usage에서 월 게시 건수(1,500 한도) 확인.
- **캐시 갱신**: 서술은 `CACHE_STALE_MONTHS`(기본 3개월) 지나면 자동 재생성.
- **종목표 갱신**: 신규 상장 반영하려면 가끔 `python x-bot/scripts/build_tickers.py` 후 커밋.
- **별칭 추가**: `scripts/build_tickers.py`의 `ALIAS_TO_TICKER`에 추가 후 재빌드·커밋.
- **한도 관리**: 답글이 폭주하면 X Free 1,500건/월을 넘을 수 있음 — 그때 Basic 고려.

## 참고: '실시간'의 한계
초 단위 즉시 응답은 웹훅/스트리밍(Enterprise/Pro, 월 수천~수만 달러)에서만 가능하다.
무료 예산에서의 최선은 **1분 주기 감지 → 1~2분 내 답글**이다. 더 빠르게 하려면 크론 주기를
줄이거나(더 잦은 Apify 조회 = 비용↑) 유료 티어로 올린다.
