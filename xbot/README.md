# kosai-mention-bot

X(트위터)에서 `@kosai_x 삼성전자` 처럼 멘션하면 해당 한국 주식 종목의 상세 설명을
답글로 자동 게시하는 봇. Vercel 서버리스로 배포한다.

## 구조

```
멘션 발생 → X 웹훅 → api/webhook.js (CRC 검증 + 즉시 200 응답)
                          └→ waitUntil로 api/process.py 호출 (백그라운드)
                                ├ Upstash Redis: 멘션 중복 체크 / 설명 캐시
                                ├ 종목 매칭: data/name_map.json (한글명=pykrx, 영문명=DART)
                                ├ 지표: pykrx 실시간 (가격·시총·PER·PBR·배당)
                                ├ 공시: DART OpenAPI 최근 공시
                                ├ 설명 생성: Claude API + web search (캐시 없을 때만)
                                └ 답글 게시: X API v2 POST /2/tweets (OAuth 1.0a)
```

- 웹훅 핸들러(Node)는 무조건 즉시 200을 반환하고, 실제 처리는 별도 Python 함수가
  최대 300초까지 수행한다 (Vercel 타임아웃 회피).
- 설명은 100% lazy 생성: 첫 멘션 때 만들어 Redis에 저장(`desc:{코드}_{ko|en}`),
  이후 재사용. 지표 숫자는 매번 실시간으로 채운다.
  캐시가 `CACHE_TTL_DAYS`(기본 90일)보다 오래되면 재생성.
- 언어: 멘션 텍스트에 한글이 있으면 한국어, 없으면 영어 답글.

## Vercel 프로젝트 설정

- Root Directory: `xbot`
- 환경변수: `.env.example` 참고 (전부 Vercel 대시보드에 등록, 커밋 금지)

## 배포 후 1회 실행

```bash
python scripts/build_name_map.py      # 종목명 매핑 생성 (커밋)
python scripts/register_webhook.py    # X에 웹훅 URL 등록 + 계정 구독
```

## 환경변수 목록

| 변수 | 용도 |
|------|------|
| `X_API_KEY` / `X_API_SECRET` | X 앱 Consumer Keys (CRC 검증에도 사용) |
| `X_ACCESS_TOKEN` / `X_ACCESS_SECRET` | 봇 계정 Access Token (답글 게시) |
| `X_BOT_HANDLE` | 봇 핸들 (기본 kosai_x) — 자기 트윗 무시용 |
| `INTERNAL_SECRET` | webhook→process 내부 호출 인증용 랜덤 문자열 |
| `UPSTASH_REDIS_REST_URL` / `UPSTASH_REDIS_REST_TOKEN` | 캐시·중복방지 저장소 |
| `ANTHROPIC_API_KEY` | 설명 생성 |
| `DART_API_KEY` | 최근 공시 조회 |
| `CACHE_TTL_DAYS` | 설명 캐시 유효기간(일), 기본 90 |
