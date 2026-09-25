# 종목 페이지를 종목마다 미리 만든다 — 큰 회사 방식 *(2026-09-25 사장 결정)*

사장: "대기업처럼 해줘." r/ 로봇용 사본이 왜 있냐는 물음에서 나온 결정이다.

## 왜

`stock.html` 은 2,682종목이 함께 쓰는 빈 틀 하나다. 리포트 글은 화면이 열린 뒤 자바스크립트가
`data/reports_v2/{ticker}.json` 을 받아 그린다. 검색·AI 수집 로봇(네이버 · ChatGPT · Perplexity · Claude)은
그 자바스크립트를 대개 돌리지 않아 종목 페이지가 전부 똑같은 빈 틀로 보이고, canonical 도 `stock.html`
하나라 종목별로 색인이 나뉘지 않는다. 그래서 로봇에게 글을 보여 주려고 `r/{ticker}.html` 2,681장을 따로
만들어 왔다(`scripts/generate_geo_pages.py`, 매일). 사람용과 로봇용이 갈라져 있으니 검색 결과를 누른 사람이
머리·발도 없는 로봇용 페이지로 떨어진다. 구글은 이 구조("동적 렌더링")를 임시 우회책이라고 문서에 적어 두었다.

큰 회사들은 HTML 을 받는 순간 글이 다 들어 있다(서버 렌더링 또는 정적 생성). GitHub Pages 는 서버가 없으니
정적 생성이다: **종목마다 완성된 페이지를 미리 만들어 올린다.** 사람과 로봇이 같은 페이지를 본다.

## 무엇이 있나

| | 파일 | 하는 일 |
|---|---|---|
| 그리는 모듈 | `scripts/stock_page.py` | 데이터(시세 · valuation · 리포트 v2/v1)에서 한 장을 그린다. 등급 셋: 전체(v2) · 옛 형식(v1) · 리포트 준비 중 |
| 시안 한 장 | `scripts/build_stock_comp.py` | 삼성전자 → `preview/stock.html` (CSS·JS 를 안에 넣은 한 장) |
| 전 종목 생성기 | `scripts/build_stock_pages.py` | `stock/{ticker}.html` + `assets/stock.css · stock.js` 한 벌 + `index.html` |

둘 다 같은 `stock_page.render` 를 쓰므로 시안과 실제 페이지의 옷은 늘 같다.

페이지마다 붙는 것: `<title>` · description · canonical(`https://kosai.kr/stock/{ticker}.html`) · OG · schema.org
JSON-LD(Article · Corporation). CSS·JS 는 외부 한 벌이라 장당 약 37KB(글이 대부분). 전 종목이면 약 100MB —
지금 r/ 폴더(100MB)와 같고, r/ 를 없애면 저장소 크기는 그대로다.

    python3 scripts/build_stock_pages.py --sample 40            # 표본 → preview/stock/ (noindex)
    python3 scripts/build_stock_pages.py --all --out stock --index   # 전 종목 → stock/ (검색 허용)

## 실사이트로 옮기는 날 — 순서

새 디자인을 실사이트에 올리는 PR 과 같이 한다. 종목 페이지의 옷과 구조가 한꺼번에 바뀐다.

1. **생성** — `build_stock_pages.py --all --out stock --index`. `stock/assets/` 도 같이 커밋.
2. **매일 자동화** — `.github/workflows/update_data.yml` 에서 `generate_geo_pages.py` 자리에 이 생성기를 넣는다.
   시세가 바뀌면 지표 줄이 바뀌므로 매일 다시 만든다(r/ 와 같은 주기).
3. **링크** — 홈 · 리포트 목록 · 업종 · 관심종목 · 브리핑의 `stock.html?ticker=X` 를 `/stock/X.html` 로.
   (comp_common 을 쓰는 시안들은 한 곳만 고치면 된다.)
4. **옛 주소** — `stock.html?ticker=X` 는 검색·공유로 이미 퍼져 있다. `stock.html` 을 `/stock/X.html` 로
   보내는 얇은 껍데기로 남긴다(자바스크립트 리다이렉트 + canonical 은 새 주소).
5. **r/ 폐기** — `r/{ticker}.html` 은 `/stock/{ticker}.html` 로 보내는 껍데기(meta refresh + canonical 새 주소)로
   한 번 갈아 둔 뒤, 사이트맵에서 뺀다. 구글이 새 주소를 색인한 뒤(몇 주) 폴더째 지운다.
   `generate_sitemap.py` 는 `stock/*.html` 을 넣도록 고친다.
6. **기능 잇기** — 관심종목 단추는 `KOSWatch`(Firestore), 헤더 계정은 `auth-state.js`, 한/영은 `KOSi18n`.
   정적 페이지는 이미 그려져 있으니 이 스크립트들은 그 위에 얹기만 한다(다시 그리지 않는다).
7. **검사** — `check_all.sh` 에 "표본 종목 3장(전체 · 옛 형식 · 준비 중)이 만들어지고 글자가 리포트 JSON 과 같다"
   를 넣는다.

## 지킬 것

- 리포트 글은 JSON 이 원본이다. 생성기는 글을 바꾸지 않는다(170자 문단 나누기만).
- 새 상장 종목은 리포트가 없어도 페이지는 있어야 한다('리포트 준비 중' 등급). 검색에서 빈 페이지로 보이지 않게.
- 로봇도 읽는 페이지이므로 자바스크립트 없이도 글·표·지표가 다 보여야 한다. 상호작용만 JS 로.
