# 종목 페이지를 종목마다 미리 만든다 — 큰 회사 방식 *(2026-09-25 사장 결정 · 2026-10-03 '1안'으로 실사이트 적용)*

사장: "대기업처럼 해줘." r/ 로봇용 사본이 왜 있냐는 물음에서 나온 결정이다. 2026-10-03 사장이 '1안'(주소를
`/stock/{종목코드}.html` 로 옮기고 r/ 은 새 주소로 보내는 껍데기로)을 골라 실사이트에 적용했다.

## 왜

옛 `stock.html` 은 2,685종목이 함께 쓰는 빈 틀 하나였다. 리포트 글은 화면이 열린 뒤 자바스크립트가
`data/reports_v2/{ticker}.json` 을 받아 그렸다. 검색·AI 수집 로봇(네이버 · ChatGPT · Perplexity · Claude)은
그 자바스크립트를 대개 돌리지 않아 종목 페이지가 전부 똑같은 빈 틀로 보였고, canonical 도 `stock.html`
하나라 종목별로 색인이 나뉘지 않았다. 그래서 로봇에게 글을 보여 주려고 `r/{ticker}.html` 2,681장을 따로
만들어 왔다(옛 `scripts/generate_geo_pages.py`, 매일). 사람용과 로봇용이 갈라져 있으니 검색 결과를 누른 사람이
머리·발도 없는 로봇용 페이지로 떨어졌다. 구글은 이 구조("동적 렌더링")를 임시 우회책이라고 문서에 적어 두었다.

큰 회사들은 HTML 을 받는 순간 글이 다 들어 있다(서버 렌더링 또는 정적 생성). GitHub Pages 는 서버가 없으니
정적 생성이다: **종목마다 완성된 페이지를 미리 만들어 올린다.** 사람과 로봇이 같은 페이지를 본다.

## 무엇이 있나

| | 파일 | 하는 일 |
|---|---|---|
| 생성기 | `scripts/build_stock_static.py` | `stock/{종목코드}.html` 2,702장 · 영어 `en/stock/{종목코드}.html` 2,702장 + `stock/assets/`(옷 · 스크립트 · 영어 사전 한 벌) + 목록으로 보내는 `stock/index.html` · `en/stock/index.html` · `en/index.html` |
| 미리 그리기 | `scripts/prerender_stock.mjs` · `scripts/mini_dom.mjs` | 리포트 상세 화면의 스크립트(`build_stock_staging.PAGE_JS` 실사이트 판)를 노드에서 가짜 문서로 돌려 글 · 머리 값을 받는다. 영어는 번역 엔진(i18n.js)의 walk 로 남은 한국어 라벨 · 머리 · 꼬리를 바꾼다 |
| 옛 주소 껍데기 | `stock.html`(build_live) · `scripts/retire_r_pages.py` | `stock.html?ticker=` · `r/{코드}.html` 을 새 주소로 넘긴다 |
| 검사 | `build_stock_static.py --check` · `staging/tests/stock-static.test.mjs` · `retire_r_pages.py --check` | 틀 · 공용 파일 · 종목 수 / 브라우저에서 다시 그리지 않음 · 주소 · 영어 / r/ 껍데기 |

    python3 scripts/build_stock_static.py           # stock/ 를 다시 만든다(바뀐 페이지만 쓴다 · 20초 안팎)
    python3 scripts/build_stock_static.py --check   # check_all '종목 페이지'
    python3 scripts/build_live.py                   # 루트 페이지와 함께 stock/ 까지

### 왜 노드로 미리 그리나

파이썬 판(`scripts/stock_page.py` 의 `render`)은 문단 자르기(`chunk`)가 화면 스크립트(`chunkPara` · 170자 예산)와 달라,
그것으로 만든 페이지는 화면이 열리자마자 다른 문단으로 한 번 더 그려진다. 화면 스크립트를 그대로 돌리면 미리 그린 글과
브라우저가 그리는 글이 글자 하나까지 같다(문단 · 돈 표기 · 차트 좌표가 한 벌). 브라우저는 자료를 받아 다시 그린 글의
지문(FNV-1a · `kosHash`)을 미리 그린 글의 지문(`data-pre`)과 견주어 같으면 그대로 둔다 — 그사이 자료가 바뀌었거나 영어
화면이면 새로 그린다. 파이썬 판과 `scripts/build_stock_pages.py` 는 시안(preview/stock/)과 랜딩 그림용으로 남아 있다.

### 페이지 한 장

- 머리: `<title>` · description · canonical(`https://kosai.kr/stock/{코드}.html`) · OG · Twitter · schema.org JSON-LD(Article · Corporation).
  값은 화면 스크립트의 `setSEO()` 가 내는 것과 같다(미리 그리기가 그 값을 받는다).
- 본문: `<main id="page" data-tk="{코드}" data-pre="{지문}">` 안에 히어로 · 지표 · 목차 · 13개 절(옛 형식은 있는 절만).
- 꼬리: 시세 · valuation 자료, `stock/assets/stock.js`(목차 · 공통 · 차트 라벨 · 페이지 스크립트), 영어 사전, 로그인 상태 · 관심종목 · 안내창 모듈, 휠 스크롤.
- 크기: 장당 33~44KB, 전 종목 약 107MB(옛 r/ 101MB 와 비슷 · r/ 은 껍데기가 되어 약 1MB).
- 시세 자료에 없는 종목(상장 폐지 · 합병 · 거래 정지 등으로 리포트만 남은 17개)은 noindex · 사이트맵 제외.
- 영어 페이지(`en/stock/{코드}.html` · 2026-10-03 사장 승인) — 옛 r/ 에 있던 영어 본문을 대신한다. 자바스크립트 없이도 머리 · 본문 · 꼬리가
  영어이고(html lang=en), 한국어 페이지와 hreflang 으로 서로를 가리킨다(x-default 한국어). 머리에서 `KOS_PAGE_LANG='en'` 을 달아 저장된 말과
  관계없이 영어로 보인다(저장된 말은 바꾸지 않는다 — 그 페이지만 영어). 한국어 페이지를 영어로 정한 사람에게는 화면이 자료(`en`)로 영어를 그린다(대표 주소는 한국어 페이지 그대로).
- 자료(리포트 파일 · 시세)를 못 받으면 미리 그린 글 · 제목 · 대표 주소를 그대로 둔다(`data-pre-tier` · `data-pre-known`). 자료가 늘어난
  경우(준비 중 → 리포트)만 새로 그린다.

## 옮긴 순서(2026-10-03)

1. **생성** — `build_stock_static.py`. `stock/assets/` 도 같이 커밋. 영어 페이지(`en/stock/`)는 같은 날 뒤이어 추가했다(자동 작업의 `git add` 에 `en/`).
2. **매일 자동화** — `update_data.yml` 이 `generate_geo_pages.py` 자리에서 이 생성기를 돌린다(시세 · 매일). 리포트 워치독(30분 · 리포트 · valuation)과
   신규 상장 작업(new_listings · 새 종목의 링크가 빈 주소가 되지 않게)도 돈다. 종목 하나가 그리다 멈추면 그 종목만 옛 페이지로 둔다.
3. **링크** — 홈 · 리포트 목록 · 업종 · 관심종목 · 브리핑(본문 · 영어 사전) · 첫 화면 검색. 생성기는 시안 · 스테이징과 같은
   `/stock.html?ticker=` 를 쓰고 실사이트 `comp_common.finish()` 가 `live_stock_links` 로 바꾼다(스테이징은 유료 구간 잠금 때문에 껍데기 한 장).
4. **모듈 주소** — 폴더가 한 단 아래라 로그인 · 가입 · 설정 · 동의 · 홈으로 가는 주소를 맨 위부터 쓴다(`siteBase()`) · 돌아올 곳은 `stock/005930.html`.
5. **옛 주소** — `stock.html?ticker=X` 는 머리 맨 앞의 스크립트가 `/stock/X.html` 로 넘긴다(꼬리표 · #절 그대로). 페이지가 없는
   종목코드(`stock/assets/pages.js` 에 없음)는 넘기지 않고 '종목을 찾을 수 없습니다'. 넘기기 전에 원래 출처를 남겨 통계가 검색 유입을 잃지 않게 한다. `r/{코드}.html` 은 0초 메타 리프레시 + canonical 껍데기(네이버 서치어드바이저가 서버 이동이
   안 될 때 권하는 방식). 사이트맵에서 r/ · stock.html 을 빼고 stock/ 을 넣었다. llms.txt 도 새 주소로.
6. **통계** — GA4 에는 옛 주소 모양(`/stock.html?ticker=`)으로 싣는다(`analytics.js` 의 `page_location`). 주간 보고서가 '/stock.html'
   한 덩어리로 리포트 연 사람을 세기 때문이다.
7. **검사** — `check_all.sh` 에 '종목 페이지' · '옛 주소 r/' 를 넣었고, 화면 검사(`stock-static.test.mjs`)는 폴더째 돈다.

## 남은 일

- **r/ 폐기** — 구글 서치 콘솔 · 네이버 서치어드바이저에서 r/ 주소가 색인에서 빠지고 stock/ 이 올라온 것을 확인한 뒤(몇 주) 폴더째 지운다.
  그때 `retire_r_pages.py` 와 check_all 의 '옛 주소 r/' 줄, check_seo 의 r/ 언급도 같이 뺀다.
- **유료화** — 미리 만든 페이지에 유료 구간 글이 들어 있으면 누구나 읽는다. 유료화하는 날 이 생성기에 무료 구간만 그리는 잠금을 넣는다.

## 지킬 것

- 리포트 글은 JSON 이 원본이다. 생성기는 글을 바꾸지 않는다(문단 나누기는 화면 스크립트가 한다).
- 새 상장 종목은 리포트가 없어도 페이지는 있어야 한다('리포트 준비 중' 등급). 검색에서 빈 페이지로 보이지 않게.
- 로봇도 읽는 페이지이므로 자바스크립트 없이도 글·표·지표가 다 보여야 한다. 상호작용만 JS 로.
