# 05 · 3D · WebGL · 셰이더 · 고급 그래픽 — 프리미엄 웹에서 언제 격을 올리고 언제 싸 보이나 (2024–2026)

*조사일 2026-09-26. 웹 검색·원문 열람·저장소 실측(`index.html`, jsDelivr 번들 gzip 실측, 금융·테크 홈페이지 20곳 HTML 프로브)을 섞었다. "실측" 표시는 이 조사에서 직접 잰 값, "추정" 표시는 근거만 있는 짐작이다.*

---

## 1. 분류(택소노미)와 대표 사례 — 무엇이 '고급'으로 읽히고 무엇이 '장난감'으로 읽히나

### Takeaway
프리미엄으로 읽히는 3D·셰이더는 예외 없이 **한 페이지에 하나, 단색 또는 브랜드 색 하나, 물성(유리·얼음·빛)이 정확하고, 텍스트와 경쟁하지 않는다**. 싸 보이는 쪽은 3D 를 '장식'으로 여러 개 흩뿌리거나(떠다니는 동전·아이콘), 보라·청록 그라데이션 구체, 유리 카드 더미, 시선을 끄는 자동 모션이다. 2026년 현재 애플조차 상품 페이지의 스크롤 3D 를 캔버스 이미지 시퀀스가 아니라 `<video>` 로 배포한다(실측).

### Cited Findings

**① 추상 셰이더 배경 (Stripe 식 메시 그라데이션)**
- Stripe 랜딩의 흐르는 그라데이션은 자체 경량 WebGL 구현 `minigl` 과 `Gradient` 클래스로 그리며, 색은 캔버스의 CSS 변수(`--gradientcolorzero` … `--gradientcolorthree`)로 넣고, **화면 밖이면 ScrollObserver 로 렌더를 끈다** — [Kevin Hufnagl](https://kevinhufnagl.com/how-to-stripe-website-gradient-effect/); [Bram.us 2021-10-13](https://www.bram.us/2021/10/13/how-to-create-the-stripe-website-gradient-effect/)
- 셰이더는 심플렉스 노이즈를 옥타브별로 쌓는 FBM(프랙탈 브라운 운동)에 UV 를 sin/cos 로 흔들어 '사선 날' 을 만든다 — [exzenter/gradient-stripe README](https://github.com/exzenter/gradient-stripe)
- 같은 계열 패키지는 "약 10KB·800줄" 로 소개된다(2차 출처, 블로그) — [Medium · Caden Chen](https://medium.com/design-bootcamp/moving-mesh-gradient-background-with-stripe-mesh-gradient-webgl-package-6dc1c69c4fa2)
- 실측(2026-09-26): stripe.com 초기 HTML 에 `<canvas>` 가 정확히 1개 — 셰이더 배경 하나뿐이다(이 조사의 curl 프로브).

**② 스크롤 구동 3D 스토리텔링 (Apple 상품 페이지)**
- 2020년 AirPods Pro 페이지는 **148장** 이미지를 스크롤 위치에 맞춰 캔버스에 그리는 방식이었고, 데스크톱 전송량이 **약 55.8MB · 1,609 요청**. 애플은 3G 모바일에 단순화 버전을 내려보냈다 — [CSS-Tricks · Jurn van Wissen 2020-05-22](https://css-tricks.com/lets-make-one-of-those-fancy-scrolling-animations-used-on-apple-product-pages/)
- 실측(2026-09-26): apple.com/airpods-pro/ 초기 HTML 에는 `<video>` 15개, HLS `.m3u8` 1개, `*_startframe`/`*_endframe` 포스터 이미지가 있고 캔버스 시퀀스 흔적은 없다 — 애플은 이 기법을 **비디오 + 시작/끝 프레임 정지 이미지** 로 바꿨다(이 조사의 curl 프로브).
- 프레임을 실물 3D 모델에서 렌더팜으로 뽑는다는 설명은 2차 출처 — [scrollsequence.com](https://scrollsequence.com/how-to-make-scroll-image-animation/)

**③ 히어로 3D 오브젝트 · 풀 WebGL 사이트 (Igloo Inc · Messenger · Lusion · Vercel)**
- Igloo Inc(abeto, Awwwards 2024 올해의 사이트 + 개발자 부문 올해의 사이트)는 Three.js + Svelte + GSAP, 자산은 Houdini·Blender. **UI 텍스트까지 WebGL 로** 그리고("SDF 텍스처 오프셋을 바꿔 DOM 리레이아웃을 피한다"), 파티클용 VDB 볼륨 데이터를 "보통 웹 이미지 한 장보다 작게" 압축하는 자체 익스포터를 썼다 — [webgpu.com 쇼케이스](https://www.webgpu.com/showcase/igloo-inc-procedural-crystals/); [abeto 공지](https://x.com/abeto_co/status/1900152588768579701)
- Messenger(abeto, 2025 올해의 사이트): "작은 행성, 누군가는 배달을 해야 한다" — WebGL·Three.js·WebSockets, 실시간 물리·조명 — [Awwwards SOTD 2025-11-10](https://www.awwwards.com/sites/messenger); [Awwwards 올해의 사이트 목록](https://www.awwwards.com/websites/sites_of_the_year/); [SPINX 설명](https://www.spinxdigital.com/blog/best-website-design/)
- Vercel 은 자사 사이트 셰이더용 WebGPU 라이브러리 **vgpu 0.3.1** 을 2026-08-27 공개했다 — [webgpu.com 뉴스](https://www.webgpu.com/news/vercel-vgpu-webgpu-browser-node-ci/). 프리즘 히어로는 처음 16샘플 레이트레이싱이 "비싸고 선명하지 않아" 메시 기반으로 바꿨고, 저자는 "이런 히어로는 전부 연막과 거울(smoke and mirrors)… 성능과 지각의 균형"이라 했다. 품질 저하 신호 셋: **GPU 티어, 배터리 30% 미만, 프레임 안정성** — [Codrops 2026-09-03](https://tympanus.net/codrops/2026/09/03/from-rays-to-meshes-building-vercels-prism-with-vgpu/)
- Active Theory 는 '반응형' 이 아닌 '적응형' — 기기 정보를 런타임에 읽어 실행할 코드를 고른다. Adult Swim 프로젝트에서 저사양 기기가 버티지 못해 **텍스트까지 WebGL 안에서** 그렸다 — [Active Theory · Adult Swim 케이스](https://medium.com/active-theory/adult-swim-singles-2018-case-study-e19349ecbfb3); [기술 스토리](https://medium.com/active-theory/the-story-of-technology-built-at-active-theory-5d17ae0e3fb4)
- 심사위원 경험자의 정리: 이기는 사이트는 "모션에 감독이 있다(라이브러리만 있는 게 아니라)", "**60fps 의 아름다움이 이 분야의 전부**"(중급 폰에서 ~60fps, DevTools CPU 4× + Fast 3G 로 검사), "WebGL 은 **구경거리가 아니라 분위기** 를 위해 쓴다" — [Hon Tran · 심사위원 관점](https://www.hontran.dev/blog/best-award-winning-websites-2026)

**④ 3D 아이콘·일러스트 (토스페이스)**
- 토스페이스는 약 **3,600 글리프** 이모지 폰트. 3D 버전은 마케팅(예: 토스뱅크 모임통장)에 쓰고, 2D 설계가 끝나 있어 3D 는 조명·카메라만 손보면 됐다. 원칙: 좌→우 방향 통일, 원근 45°, 흰/검 바탕 모두 되는 팔레트 하나 — [Toss Tech · 토스페이스 제작기](https://toss.tech/article/22205); [토스페이스](https://toss.im/tossface)
- 토스뱅크 카드 발급 화면의 "직접 만지고, 돌리고, 뒤집어보는" 카드는 Spline·C4D·Framer 로 설계하고 **Three.js 로 배포**, 2주 만에 완성. 성능 수치·저사양 폴백은 글에 없다 — [Toss Tech](https://toss.tech/article/21013)

**⑤ 리퀴드 글래스 / 글래스모피즘 재유행 (iOS 26)**
- 애플 자신의 규칙: 리퀴드 글래스는 "콘텐츠 위에 떠 있는 **내비게이션 층**" 용. "테이블뷰를 글래스로 만들면 다른 요소와 경쟁해 위계가 흐려진다 — 콘텐츠 층에 두라", "**유리 위에 유리는 항상 피하라**", "콘텐츠와 글래스의 교차를 피하라". 시스템 '투명도 줄이기·대비 높이기·동작 줄이기' 가 켜지면 자동으로 서리·흑백·탄성 제거 — [WWDC25 · Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
- NN/g(Raluca Budiu, 2025-10-10): "무언가 위에 놓인 모든 것이 보기 어려워진다", "**모션을 위한 모션은 사용성이 아니다. 메스꺼움을 곁들인 산만함이다**", "애플은 사용성보다 구경거리를 우선했다", 인터페이스가 "안절부절, 관심을 구걸하고, 덜 예측 가능하고, 덜 읽힌다" — [NN/g · Liquid Glass Is Cracked](https://www.nngroup.com/articles/liquid-glass/)
- 출시 뒤 가독성·지연 불만이 칭찬보다 많았고 애플은 가독성을 손봤다 — [MacRumors 2025-09-17](https://www.macrumors.com/2025/09/17/ios-26-liquid-glass-critiques/); [PhoneArena](https://www.phonearena.com/news/liquid-glass-returns-to-ios-26-toned-down-but-with-original-vision_id172532)

**⑥ 3D 데이터 시각화**
- 3D 차트는 "장식용 3D" 가 데이터를 왜곡하고, 진짜 3D 위치 척도는 3D→2D 투영이 **비가역**이라 한 점이 한 직선에 대응해 값을 못 읽는다. 예외는 회전 가능한 인터랙티브, 느린 회전 애니메이션, 데이터 자체가 3D(지형·단백질)인 경우뿐 — [Claus Wilke · Fundamentals of Data Visualization, "Don't go 3D"](https://clauswilke.com/dataviz/no-3d.html)

### Inferences
- 고급으로 읽힌 사례의 공통분모는 (a) 요소 하나, (b) 물성의 정확도(굴절·서리·빛 분산이 '진짜' 같음), (c) 텍스트가 3D 와 겹치지 않거나 아예 3D 안에서 통제됨, (d) 성능 예산을 처음부터 설계(적응형·화면 밖 정지·품질 단계). 이 넷 중 하나라도 빠지면 같은 기술이 '템플릿 효과' 로 떨어진다.
- 토스의 3D 는 **소비자 금융 앱의 친근함**을 위한 언어(이모지 볼륨화)다. 리서치·분석 매체가 같은 언어를 쓰면 '가벼움' 으로 읽힐 가능성이 높다(추정 — 직접 비교 연구는 없음).
- 애플이 이미지 시퀀스→비디오로 옮겼다는 실측은 "스크롤 3D = 캔버스 프레임" 이라는 2020년 튜토리얼 상식이 낡았음을 뜻한다. 정적 사이트에서 같은 연출을 원하면 비디오 + 포스터가 지금의 정답이다.

### Gaps
- Linear 의 '음영 렌더 UI' 는 실측에서 초기 HTML 에 `.webm` 2개만 있고 WebGL 흔적이 없어(런타임 3D 가 아니라 영상/이미지로 추정) 기술 문서를 찾지 못했다. Bloomberg 터미널 아트, globe.gl·deck.gl 금융 데모는 검색 예산 소진으로 조사하지 못했다(Wilke 의 3D 차트 논거가 대신 답한다).
- 애플 HIG 'Motion'·'Materials' 페이지는 JS 렌더라 본문을 읽지 못했다. WWDC25 세션 스크립트로 대체했다.

---

## 2. 수상 근거 — Awwwards·FWA·CSSDA 2024–2026 과 3D

### Takeaway
Awwwards 올해의 사이트는 **2023·2024·2025 세 해 연속 풀 WebGL 사이트**(Lusion v3 · Igloo Inc · Messenger)다. 그러나 셋 다 에이전시 포트폴리오·크립토 지주사·게임형 데모이고, 금융·B2B 는 없다. 같은 수상작의 개발 점수에서 **접근성·시맨틱은 6점대**로 가장 낮다 — WebGL 로 UI 를 그린 대가다. 심사 배점은 디자인 40 · 사용성 30 · 창의 20 · 콘텐츠 10.

### Cited Findings
- Awwwards 배점: **Design 40% · Usability 30% · Creativity 20% · Content 10%**, SOTD 수상작은 별도 개발자 심사에서 7점 이상이면 Developer Award — [Awwwards · 평가 기준](https://www.awwwards.com/about-evaluation/)
- 올해의 사이트 2020–2025: 2025 Messenger(abeto) · Lando Norris(OFF+BRAND); 2024 Igloo Inc(abeto) · Don't Board Me · Opal Tadpole; 2023 Lusion v3 · Noomo · Mana Yerba Mate; 2022 KPR(Resn) · The Other Side of Truth · Persepolis Reimagined; 2021 Pangram Pangram(Locomotive) · Star Atlas · Prometheus Fuels(Active Theory) 등 — [Awwwards · Sites of the Year](https://www.awwwards.com/websites/sites_of_the_year/)
- Igloo Inc(SOTD 2024-07-23) 점수: 종합 7.92, 디자인 8.05 · 사용성 7.50 · 창의 8.31 · 콘텐츠 7.91; 개발 7.66 — 애니메이션 **9.60**, 반응형 8.40, WPO 8.00, **시맨틱/SEO 6.60, 접근성 6.60, 마크업 6.40** — [Awwwards · Igloo Inc](https://www.awwwards.com/sites/igloo-inc)
- Lusion v3(SOTD 2023-10-02): 종합 8.25, 개발 8.41 — 애니메이션 **10.00**, WPO 9.00, 접근성 7.40, 시맨틱 7.60 — [Awwwards · Lusion v3](https://www.awwwards.com/sites/lusion-v3)
- Messenger(SOTD 2025-11-10): 종합 7.92, 디자인 8.04, 개발 8.21, 태그 WebGL·Three.js·WebSockets·3D·Storytelling — [Awwwards · Messenger](https://www.awwwards.com/sites/messenger)
- 2025 후보 중 3D·WebGL: Lando Norris(WebGL + Rive), Bruno Simon 포트폴리오(2026-01, Three.js). 금융 계열 후보는 Jeton(결제, 2025)·ABTC(비트코인 채굴, 2026) 정도 — [SPINX · Best Website Designs](https://www.spinxdigital.com/blog/best-website-design/)
- 심사위원 관점의 판정 기준: "수상작은 장식한 템플릿이 아니다. 서체·색·그리드 선택 하나하나가 한 아이디어를 섬긴다", 중급 폰 ~60fps 를 못 지키면 탈락 — [Hon Tran](https://www.hontran.dev/blog/best-award-winning-websites-2026)
- 2026년 상반기 회고: "WebGL 은 **브랜드 자체가 경험인 크리에이티브 에이전시·패션 포트폴리오** 에만 출하됐다" — [Studio Meyer · 2026 트렌드 현실 점검](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)

### Inferences
- 비율(추정): 올해의 사이트 대상 기준 최근 3년 100%(3/3) 가 WebGL. 후보 전체로 넓히면 훨씬 낮다(SPINX 목록에서 3D 로 설명된 것은 소수). '수상 = 3D' 가 아니라 '**대상 = 기술 시연이 곧 상품인 사이트**' 다.
- 개발 점수 분해가 말해 주는 것: 배심원은 애니메이션·WPO 를 높이 주고 접근성·시맨틱을 낮게 준다. 즉 WebGL 사이트는 '**감탄을 사고 접근성을 판다**'. 금융·리서치 매체는 그 거래를 할 수 없다.
- 디자인 40 + 사용성 30 = 70% 가 기술과 무관한 항목이다. KOSAI 가 '수상작처럼' 보이고 싶다면 3D 가 아니라 서체·그리드·여백·사용성이 점수의 대부분이다.

### Gaps
- FWA(thefwa.com)·CSSDA 의 연간 수상 목록은 페이지가 JS 렌더/500 오류라 확보하지 못했다. CSSDA 는 Iventions(Three.js 스포트라이트 스토리텔링)가 '올해의 웹사이트 최종 후보' 였다는 2차 언급만 있다 — [Hon Tran](https://www.hontran.dev/blog/best-award-winning-websites-2026)
- 2022 KPR·2021 Prometheus Fuels 가 WebGL 인지는 이 조사에서 원문으로 확인하지 않았다(두 스튜디오가 WebGL 전문이라는 정황만).
- 배심원의 '비판' 문장(무엇이 감점됐는지)은 공개 코멘트가 없어 점수 분해로만 추정했다.

---

## 3. 도구와 비용 — Three.js/R3F · Spline · Rive · Lottie · WebGPU · CWV · 배터리 · 접근성

### Takeaway
숫자로 보면 격차가 크다: **셰이더 전용 배경 ≈ 10KB, OGL 29KB, Three.js 최소 장면 118–125KB(gz), Spline 런타임 544KB(gz, 스튜디오 회고는 '0.8–2MB'), Rive 런타임 ≈ 28KB JS + 250KB WASM, Lottie ≈ 52KB.** KOSAI 랜딩은 지금 **무압축 three.module.js 265KB(gz) + 인라인 67KB** 를 프리즘 하나에 쓰고, 동작 줄이기 설정에서도 렌더 루프가 계속 돈다(실측). 캔버스는 LCP 후보가 아니고, WebGPU 는 2025년 하반기에야 3대 브라우저에 들어갔으며, 배터리 API 는 사파리에 없다.

### Cited Findings

**번들 크기**
- Three.js 최소 장면(Scene·Camera·Renderer·Box·MeshBasic) gzip: **0.180.0 117.77kB → 0.181.0 125.03kB**(+8kB, DFG LUT 텍스처 17KB 추가) — [three.js 포럼 2025-11-03](https://discourse.threejs.org/t/8kb-gzipped-size-increase-in-0-181-0-recommendation-on-tooling-to-analyze-package-size/87880)
- 실측(jsDelivr, 2026-09-26): `three@0.170.0/build/three.module.js` **1,314,681B raw / 264,941B gz**, `three.module.min.js` **691,648B raw / 170,759B gz**. KOSAI `index.html` 은 앞의 **무압축 모듈**을 import map 으로 받는다(`index.html` 719행).
- OGL: "미니멀 WebGL 라이브러리", **29kb minzipped**(코어 8 · 수학 6 · 엑스트라 15), 의존성 0, 트리셰이킹 시 더 작음, "Three.js 와 API 는 닮았지만 기능이 훨씬 적다" — [oframe/ogl](https://github.com/oframe/ogl)
- Spline 런타임 `runtime.js` **1.9MB raw → 544KB gz** — [Envato Tuts+](https://webdesign.tutsplus.com/how-to-optimize-spline-3d-scenes-for-speed-and-core-web-vitals--cms-108749a); "히어로에 Spline 장면 하나면 사용자가 무언가 보기 전에 **0.8–2MB JS 런타임**" — [Studio Meyer](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)
- Spline 자체 권고: 지오메트리 품질 'Performance', 텍스처 압축으로 "최대 4배 작게", 서브디비전 ≤3(1–2 권장), **조명 ≤3개**, 페이지당 임베드 **1–2개(최대 3)**, iframe 대신 `spline-viewer`(지연 로드) — [Spline Docs](https://docs.spline.design/exporting-your-scene/how-to-optimize-your-scene)
- Rive vs Lottie(2026-03-20, 벤더 블로그·독립 검증 없음): lottie-react ≈ **52KB gz**; rive-react ≈ **28KB gz JS + 250KB WASM**(1회 로드·캐시); 아이콘급 파일은 Rive 가 3–5배 작음(Lottie 15–80KB JSON, Rive 5–20KB); Lottie 는 인스턴스마다 rAF 티커가 돌아 **5개 이상 동시 재생 시 모바일 CPU 급증**, Rive 는 상태기계가 유휴 시 CPU 0 — [Unicorn Icons](https://unicornicons.com/blog/lottie-vs-rive-performance)
- detect-gpu(GPU 티어 판별): fps 기준 티어 0(미지원/<15fps)·1(≥15)·2(≥30)·3(≥60), **약 1.2kB gz**, 단 벤치 데이터원(gfxbench)이 **2025-12 갱신 중단** — [pmndrs/detect-gpu](https://github.com/pmndrs/detect-gpu)

**브라우저 지원**
- WebGPU: Chrome 113+(Android 121+, Android 12 이상·Qualcomm/ARM GPU), Firefox 141(Windows)·145(macOS ARM), **Safari 26**(macOS/iOS/iPadOS/visionOS 26); Linux 는 진행 중 — [web.dev 2025-11-25](https://web.dev/blog/webgpu-supported-major-browsers)
- CSS 스크롤 구동 애니메이션(`animation-timeline`): Chrome/Edge 115+, Firefox 159+, **Safari 26+**, 전역 **87.22%** — [caniuse](https://caniuse.com/mdn-css_properties_animation-timeline)
- Battery Status API: **Safari 전 버전 미지원**, Firefox 52+ 제거(프라이버시), Chrome 38+·Samsung 지원, 전역 78.47% — [caniuse](https://caniuse.com/battery-status)

**Core Web Vitals**
- LCP 후보는 `<img>`, `<svg>` 안 `<image>`, `<video>`, `url()` 배경, 텍스트 블록 — **`<canvas>` 는 포함되지 않는다.** 기준 2.5s/4.0s, p75 — [web.dev · LCP](https://web.dev/articles/lcp)
- INP 기준 **200ms 양호 / 500ms 초과 불량**; 클릭·탭·키만 세고 스크롤은 안 셈; "메인 스레드의 긴 작업" 이 입력 지연을 만든다 — [web.dev · INP](https://web.dev/articles/inp)
- Vodafone A/B(50/50, 일 ~34K 방문): LCP **31%** 개선 → 매출 **+8%**, 리드 전환 +15%, 장바구니 전환 +11%. 바꾼 것은 렌더 차단 JS 제거·SSR·이미지 최적화 — [web.dev 케이스](https://web.dev/case-studies/vodafone)
- 2024 성능 예산(P75 기기 Galaxy A51/Nokia G100, 7.2Mbps·94ms RTT): **마크업 중심 사이트 5초 목표 = 총 2.5MiB, JS 100KiB; 3초 목표 = 1.4MiB, JS 75KiB**; JS 중심 사이트는 JS 650/365KiB — [Alex Russell · Performance Inequality Gap 2024](https://infrequently.org/2024/01/performance-inequality-gap-2024/)

**전력·발열**
- WebKit: "가능하면 선언적(CSS) 애니메이션 — 보이지 않을 때 브라우저가 최적화한다", IntersectionObserver 로 보일 때만 돌려라, 백그라운드에서 rAF 는 자동 정지, "**캔버스 내용이 안 바뀌면 캔버스 API 를 부르지 마라**", 타이머는 몇 개로 합쳐라 — [WebKit · How Web Content Can Affect Power Usage](https://webkit.org/blog/8970/how-web-content-can-affect-power-usage/)
- 단일 저자 벤치(Galaxy A54, 10분, 스프라이트 800개): 배터리 Canvas2D 4.8% / Phaser 3.9% / PixiJS 2.1% / Construct 1.8%; 41°C 도달 3.5 / 5.2 / 9.8분 / 없음; 8분 시점 fps 22 / 46 / 58 / 59 — [HackMD](https://hackmd.io/@dashichen1/Hkdt29DFMe) (독립 검증 없음)
- 2026 회고: `backdrop-filter: blur()` 는 여전히 비싸 중급 안드로이드에서 **15–30% fps 하락**, 글래스는 내비·모달로 후퇴 — [Studio Meyer](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)

**접근성**
- `prefers-reduced-motion` 은 JS 에서 `matchMedia('(prefers-reduced-motion: reduce)')` 로 읽고 변경 이벤트를 듣는다. 전정기관 장애는 "어지럼·구역·편두통, 때로 침상 안정이 필요"; 장식 모션만 빼고 기능 모션은 남긴다 — [web.dev](https://web.dev/articles/prefers-reduced-motion)
- WCAG 2.3.3(AAA): 상호작용으로 생기는 모션은 끌 수 있어야 한다 — [Deque](https://dequeuniversity.com/resources/wcag2.1/2.3.3-animations-from-interactions); 기법 C39 — [W3C](https://www.w3.org/WAI/WCAG21/Techniques/css/C39)
- GSAP 은 `gsap.matchMedia()` 에 `reduceMotion: "(prefers-reduced-motion: reduce)"` 조건을 넣고 조건이 풀리면 자동 `revert()` — [GSAP Docs](https://gsap.com/docs/v3/GSAP/gsap.matchMedia()/)
- Three.js Journey 성능 강의: 최소 60fps, 안전하게 더 높게; 드로우콜 최소화, stats.js·Spector.js 로 측정 — [Three.js Journey · Performance tips](https://threejs-journey.com/lessons/performance-tips)

**KOSAI 랜딩 실측(저장소 `index.html`, 2026-09-26)**
- 721–1780행 인라인 모듈(**67,395B**; 블렌더에서 구운 프리즘 삼각형 배열 5,157B 포함)이 `three@0.170.0` 무압축 모듈을 받아 유리 프리즘(굴절·분산·이리데선스, 무중력 텀블 + 드래그 관성 + 마우스 패럴랙스, PMREM 스튜디오 환경)을 그린다.
- 완화 장치: `reduced`(730행)·`mobile`(731행) 판별, 모바일 픽셀비 ≤1.6/데스크톱 ≤2(1725행), 모바일은 드래그 없음·그레인 평면 숨김(1595·1745행). **그러나 `reduced` 여도 `setAnimationLoop`(1758행)는 계속 돌고 시간만 `t=14` 로 고정** — 정지 화면을 매 프레임 다시 그린다. IntersectionObserver·visibilitychange·정지 단추는 없다.
- 랜딩 전송량(gz): index.html 38.9KB + three.module.js 264.9KB + lenis 5.7KB + smooth-scroll 2.5KB + analytics 5.7KB + 워드마크 PNG 27–30KB + **Pretendard woff2 4벌 3.2MB(preload)**. 헌장 목표 '랜딩 총 ≤1MB' 를 폰트만으로 넘긴다(3D 와 별개 문제이나 같은 예산표에 있다).
- 헌장(`docs/design/KOSAI-design-charter.md` 2.4)은 이미 **A안 = three.js·Lenis·gsap 제거, 프리즘은 2D 마크로**(추천), **B안 = 무채색 3D + 예산**(대안)을 적어 두었고, 검사 #16(reduced-motion 에서 `setAnimationLoop(null)`) 은 B안일 때만 신설한다고 돼 있다.

### Inferences
- 과제가 제시한 예산 "≤150KB JS" 는 **Three.js 로는 못 맞춘다**(최소 장면 118–125KB + 장면 코드 + 라이브러리 성장분; 현재 KOSAI 는 265KB). OGL(29KB) 이나 프레임워크 없는 프래그먼트 셰이더(추정 5–15KB) 로만 가능하다.
- 캔버스가 LCP 후보가 아니므로 히어로가 3D 라도 LCP 는 텍스트·워드마크로 잡힌다 — 좋은 점수가 '빠르다' 를 뜻하지 않는다. 반대로 INP 는 스크롤을 안 세므로 렌더 루프의 부담이 CWV 에 '보이지 않는다'. 즉 **CWV 만 보면 3D 의 비용이 숨는다** — 배터리·발열·중급 폰 fps 는 따로 재야 한다.
- 사파리에 배터리 API 가 없으니 '저전력이면 끈다' 는 iOS 에서 구현 불가. Vercel 처럼 **fps 워치독 + GPU 티어 + reduced-motion** 세 신호로 대체해야 한다. detect-gpu 는 데이터원이 멈춰 신뢰가 줄고 있다.
- Rive·Lottie 는 3D 대체가 아니라 **아이콘·마이크로 인터랙션** 도구다. 리서치 매체 본문에 움직이는 아이콘 자체가 불필요하므로 둘 다 KOSAI 에는 해당이 없다.

### Gaps
- iOS 사파리 저전력 모드가 rAF 를 30fps 로 낮춘다는 통설은 이 조사에서 1차 출처를 확인하지 못했다(추정 · 미검증).
- React Three Fiber 자체 크기·오버헤드는 별도 확인 안 함(정적 사이트에 React 가 없어 무관).
- "이미지 90장 56MB vs 3초 30fps 비디오 1.92MB" 라는 비교는 출처 페이지(geyer.dev)가 403 이라 확인 못 했다. CSS-Tricks 의 148장·55.8MB 만 인용한다.

---

## 4. 3D 없이 깊이를 주는 대안 — 종이 결·선·빛·전환

### Takeaway
2026년의 방향은 "**무거운 3D 대신 질감**" 이다: 정적 SVG `feTurbulence` 그레인(수 KB, GPU 0), 1px 실선 위계, 그림자 0, 스크롤 위치에 반응하는 타이포. 패럴랙스는 NN/g 가 2019년에 이미 "평균 사용자는 신경 쓰지 않는다" 고 정리했고, 애플 iOS 7 이후 '동작 줄이기' 가 생긴 계기이기도 하다. KOSAI 는 이미 `@view-transition` 과 그레인 층(`.lp-grain`, 다만 노이즈가 아닌 평면 색)을 갖고 있다.

### Cited Findings
- `feTurbulence` 는 펄린 난류로 노이즈를 만들며 `type`·`baseFrequency`·`numOctaves` 세 속성이 핵심, `fractalNoise` 는 부드럽고 `turbulence` 는 거칠다; 조명 필터와 합치면 거친 종이 질감 — [Codrops 2019-02-19](https://tympanus.net/codrops/2019/02/19/svg-filter-effects-creating-texture-with-feturbulence/)
- 그레인 그라데이션 레시피: `feTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'` + `filter: contrast(170%) brightness(1000%)`; Blink 와 WebKit 의 `mix-blend-mode` 구현이 달라 교차 확인 필요 — [CSS-Tricks · Grainy Gradients](https://css-tricks.com/grainy-gradients/)
- 2026 트렌드(Fireart, 2026-04-21/08-27 갱신): "무거운 이미지 대신 수학으로 감각을 만든다", "단색 바탕에 미세한 CSS 그레인이나 애니메이션 SVG 노이즈를 얹으면 디지털의 완벽함이 깨진다", "**WebGL 3D 는 무거운 JS 처리로 모바일 배터리를 빨리 비우고 구형 기기에서 버벅인다**", 컨테이너는 **1px 실선**, "**그림자 0 — 깊이를 블러로 속이지 않는다**", 스크롤 위치에 글자 굵기·폭을 매핑하는 키네틱 타이포 — [Fireart Studio](https://fireart.studio/blog/the-best-web-design-trends/)
- NN/g(Katie Sherwin, 2019-01-20): "대부분의 사용자는 패럴랙스가 로드되길 기다리지 않는다 — 빠르게 스크롤하며 키워드를 훑는다", "특히 텍스트의 과한 움직임은 어지럽다"(iOS 7 '동작 줄이기' 의 계기), 사용자는 움직임을 광고로 여겨 무시하기도, "**평균 사용자는 신경 쓰지 않는다**". 권고: 목적 없는 여가 탐색에만, 배경·주변 이미지에만, 위로 스크롤할 때 재생하지 말 것 — [NN/g · What Parallax Lacks](https://www.nngroup.com/articles/parallax-usability/)
- 2024 HCI 국제학회 패럴랙스 사용성 연구가 있다(초록만 확인) — [Springer](https://link.springer.com/chapter/10.1007/978-3-031-76821-7_9)
- Stanford 웹 신뢰성 지침(4,500명, 2002): "**전문적으로 보이게 디자인하라**(레이아웃·타이포·이미지·일관성)", 운영자가 "회사의 자존심이나 **기술 시연**을 사용자 필요보다 앞세우면 신뢰가 깎인다", "오탈자·깨진 링크는 생각보다 신뢰를 크게 해친다" — [Stanford Web Credibility](https://credibility.stanford.edu/guidelines/index.html)
- 글래스모피즘은 2026년 "살아남았지만 크게 절제돼" 내비게이션 바·모달로 후퇴 — [Studio Meyer](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)
- 3D 틸트 카드는 생성기·복붙 컬렉션이 널려 있다("15 CSS 3D Tilt Hover Cards", 틸트 생성기) — [CodeFronts](https://codefronts.com/components/css-3d-tilt-hover-cards/); [fullPage 틸트 생성기](https://alvarotrigo.com/fullPage/tilt-effect/)
- KOSAI 현황(저장소): 페이지 전환은 `@view-transition{navigation:auto}` 로 본문만 크로스페이드(CLAUDE.md), 랜딩 `.lp-grain::before` 는 `rgba(187,187,187,.024)` 평면 오버레이(490–491행) — 노이즈가 아니다.

### Inferences
- 3D 틸트 카드가 '낡아 보이는' 이유는 비판 기사가 아니라 **공급 과잉**으로 설명된다: 무료 생성기와 복붙 컬렉션이 수십 개라 템플릿 냄새가 난다(추정). 종이 은유와도 충돌한다 — 종이는 마우스를 따라 기울지 않는다.
- '깊이' 의 정의를 바꾸면 된다: Z 축이 아니라 **잉크 농도(--fg-1/2/3), 선 굵기(1px/0.5px), 여백 리듬, 종이 결** 이 인쇄물의 깊이다. 이는 헌장 1.2(옷만 바꾼다)와 원칙 '그라데이션 0' 과 정합한다.
- 그레인은 **정적**이어야 한다. 애니메이션 노이즈는 매 프레임 리페인트를 부르고(WebKit 권고 위반) 영상 압축 노이즈처럼 보인다. 정적 SVG data-URI 한 장(추정 1–3KB)을 `background-image` 로 깔고 불투명도 3–5% 면 충분하다.

### Gaps
- "3D 틸트가 낡았다" 는 명시적 비평 기사는 찾지 못했다(위는 추정).
- 그레인 오버레이가 저사양 기기에서 스크롤 성능에 주는 비용(합성 레이어 크기)은 수치를 찾지 못했다 — 넣는다면 실기기에서 재야 한다.

---

## 5. 금융 브랜드는 3D 를 쓰나 — 20개 홈페이지 실측과 사례

### Takeaway
실측(2026-09-26, 초기 HTML): **Goldman Sachs · Morgan Stanley · Fidelity · Vanguard · FT · Bloomberg 에는 3D·WebGL·Spline·Lottie·Rive 흔적이 전혀 없다.** 핀테크는 **영상**(Mercury mp4 3개, Wise webm/mp4 6개, Linear webm 2개)과 GSAP 스크롤(카카오뱅크)·Lottie(토스뱅크)를 쓰고, 런타임 3D 는 Stripe 의 캔버스 1개(그라데이션)뿐이다. 토스 홈 개편(2026-08)의 '3D' 도 카메라 경로용 사전 렌더 영상이다. 3D 가 신뢰·전환을 올린다는 증거는 찾지 못했고, 속도가 전환을 올린다는 증거(Vodafone)만 있다.

### Cited Findings
- 실측 프로브(curl, 초기 HTML 만 — 번들 안 라이브러리는 못 본다):
  - stripe.com — `<canvas>` 1개(셰이더 그라데이션). mercury.com — `.mp4` 3, `backdrop-filter` 1. ramp.com — 14KB 앱 셸, 표지 없음. wise.com — `<video>` 2, `.webm` 3, `.mp4` 3. revolut.com — HTTP 403(본문 873KB) `backdrop-filter` 4, WebGL 표지 없음(봇 차단 페이지일 가능성).
  - toss.im — 53KB Next 셸, `requestAnimationFrame` 3, `.mp4` 2, three/spline 없음. tossbank.com — `lottie.min` 1, `backdrop-filter` 8. kakaobank.com — `gsap.min.js` + `ScrollTrigger.min.js` + `CustomEase.min.js`, `<video>` 1.
  - goldmansachs.com(839KB) · morganstanley.com(263KB) · fidelity.com(513KB) · investor.vanguard.com(179KB) · ft.com(403, 270KB) · bloomberg.com(403) — three/spline/lottie/rive/canvas 표지 0.
  - linear.app(HTML 1.29MB) — `.webm` 2, three 없음. vercel.com — rAF 10, `.webm` 2(셰이더는 번들 안). lusion.co — `<canvas>` 3. apple.com/airpods-pro — `<video>` 15 + HLS.
- Mercury: "첫 화면의 떠 있는 카드에 은은한 반짝임이 지나가 금속 프리미엄 카드임을 알린다", 모핑 애니메이션으로 카드 기능 설명 — [siiimple](https://siiimple.com/mercury-bank/); "차분한 팔레트, 넉넉한 여백, **럭셔리·패션 브랜드에서 빌려온 에디토리얼 사진**", 샌드박스를 가입 없이 공개 — [Striped Horse](https://www.stripedhorse.com/blog/best-financial-website-designs)
- Revolut(2차 목록): 80–136px Aeonik 헤드라인, 사진 주도 히어로, 근검정 섹션 안의 제품 목업 — [Azuro Digital](https://azurodigital.com/fintech-website-examples/). 같은 목록류가 "기울어진 WebGL 그라데이션 메시, 3D WebGL 지구본, 3D 기기 목업" 을 트렌드로 언급하나 특정 은행에 귀속하지 않는다 — [Webstacks](https://www.webstacks.com/blog/fintech-websites)
- 핀테크 25곳 목록(Stripe·Robinhood·Binance·Coinbase 등)에서 **3D·WebGL·지구본 언급 0**, 강조는 다크 모드·미니멀·마이크로 인터랙션·"명확한 메시지·투명한 정책·신뢰 배지" — [Ballistic Media](https://www.ballistic.media/blog/fintech-website-designs)
- 토스 홈페이지 전면 개편(2026-08-18 발표, 70여 페이지): 인트로 영상은 생성형 AI, "카메라 이동 경로를 세밀하게 구현해야 하는 구간" 에 3D, 스크롤을 시간 흐름으로 써 10년의 서비스가 앱 화면 형태로 차례로 등장 — [디지털 인사이트](https://ditoday.com/%ED%86%A0%EC%8A%A4-%ED%99%88%ED%8E%98%EC%9D%B4%EC%A7%80-%EC%A0%84%EB%A9%B4-%EA%B0%9C%ED%8E%B8-%EB%B0%9C%ED%91%9C-10%EB%85%84-%EB%B9%84%EC%A6%88%EB%8B%88%EC%8A%A4-%ED%99%95%EC%9E%A5-%EA%B3%BC/)
- 토스뱅크 카드 3D(Three.js) 는 **앱 안 발급 화면**의 인터랙션이지 웹 랜딩이 아니다 — [Toss Tech](https://toss.tech/article/21013)
- 전환 증거: Vodafone LCP 31% → 매출 +8%(A/B) — [web.dev](https://web.dev/case-studies/vodafone). 벤더 조사(2,000 페이지, 미검증): LCP <1s 전환 4.4% → 4s+ 1.7%, 히어로 자산 +100KB 마다 이탈 +1.8%, 히어로 비디오가 LCP 를 평균 +1.2s — [Digital Applied](https://www.digitalapplied.com/blog/landing-page-conversion-study-2000-pages-tested-2026)
- 신뢰: "전문적으로 보이는 디자인" 이 지침이고 "기술 시연" 우선은 감점 — [Stanford](https://credibility.stanford.edu/guidelines/index.html)

### Inferences
- **신뢰 자본이 큰 금융사일수록 3D 가 없다**(골드만·모건스탠리·뱅가드·피델리티·FT·블룸버그 = 0). 3D 는 '신규 진입자가 세련됨을 증명하는 도구' 이고, 그것도 지구본·동전이 아니라 **금속 카드 하나(Mercury)** 처럼 실물 제품의 물성이다. 리서치 매체의 '실물 제품' 은 리포트 화면 그 자체다(헌장 2.4 A 와 같은 결론).
- 한국 금융(토스·카카오뱅크·토스뱅크)의 문법은 **영상 + 스크롤 트리거 + Lottie** 다. 런타임 3D 는 웹 랜딩에서 확인되지 않았다. KOSAI 가 '한국 금융처럼' 보이려면 3D 가 아니라 정갈한 스크롤 리듬과 실제 화면이면 된다.
- 3D 가 전환·신뢰를 올린다는 통제 실험은 없다. 있는 것은 반대 방향(무게→LCP→전환 하락) 증거뿐이다. 따라서 3D 는 '측정 가능한 이익 없이 측정 가능한 비용' 을 갖는다.

### Gaps
- 프로브는 초기 HTML 만 본 것이라 번들에 묻힌 three.js(예: Vercel 의 vgpu)는 놓친다. Revolut·Bloomberg·FT 는 403 응답이라 실제 페이지가 아닐 수 있다.
- 카카오뱅크·토스의 디자인 의도를 밝힌 1차 글은 찾지 못했다(검색 예산 소진). Kakao 의 3D 아이콘 체계도 미조사.
- Wise·Revolut·Ramp 에 대한 설명은 에이전시 목록(2차)뿐이다.

---

## 6. 2025–2026 흐름 — 무엇이 이미 낡았고 무엇이 '유행이되 오래가나'

### Takeaway
낡은 것의 목록은 이제 이름이 있다: **"AI 슬롭"** — 보라·인디고 그라데이션, 빛나는 구, 유리 카드, 다크 남색 히어로 위 3D 오브젝트. 원인까지 밝혀졌다(Tailwind 의 `bg-indigo-500` 기본값 → 학습 데이터의 중앙값). 반대편 움직임은 **질감·1px 선·그림자 0·타이포 주도·(반)브루탈리즘** 이고, 3D 는 "브랜드가 곧 경험인 에이전시" 로 물러났다. 리퀴드 글래스는 애플 안에서도 후퇴했다.

### Cited Findings
- 2025-08 Tailwind 창시자 Adam Wathan 이 "5년 전 Tailwind UI 의 모든 단추를 `bg-indigo-500` 으로 만든 것" 을 반농담으로 사과(조회 100만+) — 모든 AI 생성 UI 가 보라색이 된 원인 — [prg.sh](https://prg.sh/ramblings/Why-Your-AI-Keeps-Building-the-Same-Purple-Gradient-Website); "보라 그라데이션 피로" — [YouWare](https://www.youware.com/blog/how-we-escaped-the-purple-prison-of-ai-frontends); [DEV](https://dev.to/james_anderson_h/the-purple-gradient-problem-why-ai-ui-all-looks-alike-and-how-to-fix-it-3j65)
- "빛나는 구(glowing orb)" 는 2023년경 프리미엄 제품·AI 런칭 히어로로 퍼져 2025년엔 하나의 관용구(에너지·기술·행성) — [gradients.design](https://gradients.design/orb-gradient)
- AI 슬롭의 단서 목록(서체·그라데이션) — [925 Studios](https://www.925studios.co/blog/ai-slop-design-tells)
- 2026 상반기 회고: 3D/WebGL "표준이 되는 데 실패"(Lighthouse·CWV 붕괴), 글래스모피즘은 내비·모달로 후퇴, **반(反)그리드 브루탈리즘**(깨진 레이아웃·날것의 HTML·모노스페이스)이 벤토 포화의 반작용으로 등장 — [Studio Meyer](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)
- "생성형 AI 통합이 **동질화의 바다**를 만들었다"; 촉각적 브루탈리즘은 "표준 AI 사이트 빌더의 동질적 산출물에 대한 거대한 시각적 대비" — [Fireart](https://fireart.studio/blog/the-best-web-design-trends/)
- 기타 트렌드 목록(참고, 마케팅 성격): [Wix](https://www.wix.com/blog/web-design-trends); [Figma](https://www.figma.com/resource-library/web-design-trends/); [Bubble](https://bubble.io/blog/web-design-trends/)
- 리퀴드 글래스: NN/g "구경거리 우선" 비판, 사용자 불만 다수, 애플 톤다운 — [NN/g](https://www.nngroup.com/articles/liquid-glass/); [MacRumors](https://www.macrumors.com/2025/09/17/ios-26-liquid-glass-critiques/)
- KOSAI 헌장 표 569행: "다크 남색 기본 + 3D 오브젝트가 첫 화면 = Linear·Vercel 룩(대표 비추천)"; 511행: 빈 상태에 "그라데이션 원·3D 일러스트·'Oops' 금지"(저장소 `docs/design/KOSAI-design-charter.md`).

### Inferences
- '유행이되 오래가는 것' 의 조건은 **재료가 물리적으로 설명되는가** 다. 종이·잉크·활자·1px 괘선은 500년 된 재료라 유행을 타지 않고, 유리·네온·구체는 2023–2025 의 재료라 연도가 찍힌다. 3D 를 쓰더라도 재료를 **무채색·무광**으로 고르면(스펙트럼·이리데선스 없음) 수명이 길어진다(추정).
- 타이포그래피 3D(글자 자체가 입체)나 스크롤에 반응하는 활자 굵기는 종이 은유와 충돌하지 않는 유일한 '움직임' 이지만, 리서치 매체 본문에는 여전히 불필요하다 — 랜딩 제목 한 곳이 상한.
- KOSAI 의 현재 랜딩(강제 다크 · 남색 그라데이션 · 유리 프리즘 · 스펙트럼)은 이 조사가 '낡음' 으로 분류한 항목 네 개를 동시에 갖는다. 헌장이 같은 판단을 이미 내렸다.

### Gaps
- 트렌드 회고 글들은 에이전시 블로그라 수치의 출처가 약하다(예: "15–30% fps 하락" 은 자체 관찰). 독립 연구는 없다.
- "AI 룩" 을 사용자가 실제로 덜 신뢰한다는 실험 증거는 찾지 못했다(디자이너 커뮤니티의 합의 수준).

---

## KOSAI 적용 제안

### Takeaway
**판정: 본문 페이지(리포트·업종·브리핑·관심종목·설정·법률·인증 등 34장 + 종목 상세 2,682장)에서 3D·WebGL·셰이더·글래스 카드·3D 아이콘·패럴랙스·이미지 시퀀스는 금지. 랜딩 한 곳만 예외를 둘 수 있으나, 근거는 헌장 2.4 A(3D 제거 · 프리즘은 2D 마크) 를 가리킨다.** 대표가 B(무채색 3D)를 고른다면 아래 예산을 전부 지키는 조건이며, 현재 프리즘 구현은 그 예산의 네 항목(크기·reduced-motion 루프·화면 밖 정지·정지 단추)을 지키지 못한다.

### Cited Findings
(근거는 1–6절에 있다. 판정에 직접 쓰인 것만 다시 적는다.)
- 신뢰 자본이 큰 금융·리서치 매체(골드만·모건스탠리·뱅가드·피델리티·FT·블룸버그)는 홈에 3D·WebGL 이 없다(5절 실측). 핀테크는 영상·GSAP·Lottie(5절).
- 수상 WebGL 사이트는 접근성·시맨틱 점수가 6점대(2절 · [Awwwards Igloo](https://www.awwwards.com/sites/igloo-inc)); "기술 시연 우선은 신뢰를 깎는다"([Stanford](https://credibility.stanford.edu/guidelines/index.html)); 3D 차트는 값을 못 읽게 한다([Wilke](https://clauswilke.com/dataviz/no-3d.html)).
- Three.js 최소 118–125KB gz, KOSAI 현재 265KB gz 무압축 + 67KB 인라인(3절 실측); 마크업 중심 사이트 JS 예산 75–100KiB([Russell](https://infrequently.org/2024/01/performance-inequality-gap-2024/)); `<canvas>` 는 LCP 후보가 아님([web.dev](https://web.dev/articles/lcp)); 캔버스가 안 바뀌면 그리지 말 것([WebKit](https://webkit.org/blog/8970/how-web-content-can-affect-power-usage/)); 사파리에 배터리 API 없음([caniuse](https://caniuse.com/battery-status)).
- 글래스는 내비게이션 층에만, 유리 위 유리 금지([WWDC25](https://developer.apple.com/videos/play/wwdc2025/219/)); 모션을 위한 모션은 산만함([NN/g](https://www.nngroup.com/articles/liquid-glass/)); 패럴랙스는 사용자가 신경 쓰지 않음([NN/g](https://www.nngroup.com/articles/parallax-usability/)).
- 2026 방향은 그레인·1px 선·그림자 0([Fireart](https://fireart.studio/blog/the-best-web-design-trends/)); WebGL 은 에이전시 포트폴리오로 후퇴([Studio Meyer](https://studiomeyer.io/en/blog/webdesign-trends-2026-reality-check)).

### Inferences — 권고 9개 (예산 포함)

1. **본문 34장 + 종목 상세: 3D 0 · 캔버스는 2D 차트에만.** 깊이는 잉크 농도(`--fg-1/2/3`)·1px/0.5px 괘선·여백 리듬으로만 낸다. 차트는 SVG 또는 Canvas 2D 의 2D 선·막대만(3D 차트·도넛 원근 금지). 이는 헌장 1.2 '옷만 바꾼다' 와 그라데이션 0 원칙의 자연스러운 귀결이다.
2. **랜딩: 헌장 2.4 A 채택 권고.** three.js(265KB gz)·인라인 67KB·프리즘을 빼고, 히어로 시각물은 실제 리포트 화면 라이트 캡처(정적 `<img>`, LCP 후보가 되므로 `fetchpriority=high`), 프리즘은 정지된 2D SVG 마크(추정 ≤4KB)로 파비콘·OG·About·푸터에 옮긴다. 이 조사의 금융 실측·수상 분석·트렌드 회고가 모두 같은 쪽을 가리킨다. 예상 효과(추정): 랜딩 JS 전송 ~280KB→~15KB, 모바일 GPU 상시 부하 0, reduced-motion 검사 불필요.
3. **B(무채색 3D)를 고른다면 예산표를 검사로 못 박는다** (헌장 검사 #16 확장):
   - JS 총량 **≤150KB gz** — Three.js 는 min 빌드로도 171KB 라 탈락. 선택지는 (a) OGL 29KB + 장면 코드, (b) 프레임워크 없는 프래그먼트 셰이더 두 삼각형(추정 5–15KB, Stripe minigl 방식). 헌장이 권한 jsDelivr 는 **npm 버전 고정 + min 빌드**로만.
   - 재료 **무채색 무광 또는 무색 유리 굴절만** — 스펙트럼·이리데선스·남색 배경 제거(그라데이션 0). 바탕은 종이색 `#f9f8f6`, 다크는 먹색 토큰.
   - **첫 그림(LCP) = 제목 텍스트**, 3D 는 제목 페인트 뒤 `modulepreload` 지연 로드, 캔버스 높이 ≤40vh, 모바일은 제목 아래.
   - 정지 조건 — `prefers-reduced-motion` → **루프 없음(`setAnimationLoop(null)`) + 정지 WebP 한 장**; 화면 밖(IntersectionObserver)·탭 숨김(visibilitychange) → 정지; **8초 뒤 자동 감속·정지 단추**(WCAG 2.2.2); 카카오톡 인앱·`deviceMemory ≤4`·detect-gpu 티어 ≤1 → 정지 프레임; 1초 평균 fps <45 가 두 번이면 정지(fps 워치독 — 사파리에 배터리 API 가 없어 이것이 대체 신호).
   - 픽셀비 모바일 ≤1.5 · 데스크톱 ≤2, 드로우콜 ≤5, 조명 ≤3, 포스트프로세싱 0.
   - Playwright `reducedMotion:'reduce'` 로 rAF 호출 수 0 검사, 실기기(대표 휴대폰)에서 발열·프레임 확인. 현재 구현은 (크기 265KB · reduced 에도 루프 · 화면 밖 미정지 · 정지 단추 없음) 네 항목이 미달.
4. **종이 결은 넣되 정적으로.** `feTurbulence`(fractalNoise, baseFrequency 0.6–0.9, numOctaves 2–3) 를 SVG data-URI 한 장(추정 1–3KB)으로 `body::after` 에 깔고 불투명도 3–5%, 애니메이션 없음, `mix-blend-mode` 는 Blink/WebKit 차이 때문에 실기기 확인. 랜딩의 `.lp-grain`(평면 색)을 이것으로 바꾸면 '인쇄된 종이' 은유가 실제 질감을 얻는다. 모든 페이지 공통이면 `comp_common.CSS` 한 곳.
5. **글래스는 헤더·모바일 메뉴 한 곳만.** 이미 `.glass` 가 있으니 유지하되 본문 카드·툴팁·표에 `backdrop-filter` 금지(중급 안드로이드 fps 15–30% 하락 보고). 다크에서 텍스트 대비를 재고, 애플 규칙대로 유리 위 유리 없음.
6. **스크롤 연출 상한: 등장 페이드 하나.** 패럴랙스·핀 고정 스크롤텔링·이미지 시퀀스·비디오 스크럽 금지. 등장 애니메이션은 `prefers-reduced-motion` 에서 제거(장식이므로). gsap(73KB raw)은 랜딩 밖에서 불필요 — 필요하면 CSS `animation-timeline`(전역 87%, Safari 26+)로 대체 가능하되 폴백은 '그냥 보임'.
7. **3D 아이콘·일러스트·Lottie 아이콘 금지.** 토스페이스식 볼륨 이모지는 소비자 앱의 친근함 언어다. 빈 상태·안내는 헌장 511행대로 단색 선 아이콘 40px. Rive/Lottie 런타임(52–280KB)을 아이콘 때문에 들이지 않는다.
8. **페이지 전환·미세 상호작용은 현행 유지.** `@view-transition` 크로스페이드, 휠 스크롤(lenis, 휴대폰에서 자동 꺼짐), 200ms 이하 상태 전환 — 이것들이 '고급' 을 만드는 움직임이고 3D 가 아니다. INP 200ms 예산 안에서만.
9. **예산 외 발견 — 폰트 3.2MB.** 랜딩이 Pretendard woff2 4벌(각 ~800KB)을 preload 한다. 3D 를 빼도 헌장 '랜딩 ≤1MB' 를 못 맞춘다. 이 노트의 범위 밖이나 같은 예산표에 있으므로 서체 노트(글꼴 CDN·서브셋 결정)에서 처리해야 한다.

**하지 말 것(Do-not) 목록** — 하나라도 있으면 'AI 룩' 또는 '2023년' 으로 읽힌다
- 보라·인디고·청록 그라데이션, 빛나는 구, 크롬·액체 금속 블롭, 파티클 배경, 남색 다크 히어로 위 유리 3D 오브젝트 + 빛 스펙트럼
- 떠다니는 동전·차트·촛대 아이콘, 3D 지구본, 3D 기기 목업 더미, 3D 차트·원근 도넛
- 유리 카드 그리드, 마우스 따라 기우는 3D 틸트 카드, 홀로그램 카드
- 자동 재생 히어로 비디오(LCP +1.2s 보고), 캔버스 이미지 시퀀스(148장·55.8MB 급), 핀 고정 스크롤텔링
- Spline 임베드(런타임 544KB gz), 아이콘용 Lottie 다발(rAF 티커 다중), 페이지마다 다른 모션 라이브러리
- reduced-motion 을 '느리게' 로 해석하기 — 장식 모션은 0 이어야 한다
- 캔버스를 첫 화면 유일한 시각물로 두기(LCP 후보가 아니라 지표가 속는다)

### 구현 스케치 — B 를 고를 때의 '절제된 WebGL 요소 하나' (추정치 표시)
- **무엇**: 프레임워크 없는 전체 화면 프래그먼트 셰이더 하나(삼각형 2개, 드로우콜 1). 종이색 위에 아주 느리게 흐르는 **무채색 빛 결**(FBM 노이즈 2–3 옥타브, 밝기 ±2–3%)이나 종목 수·업종 수 같은 **실제 데이터로 자리를 정한 점·선의 단색 면**. 색은 `--bg-1`/`--fg-3` 토큰만 읽어 라이트·다크가 같은 코드.
- **크기(추정)**: GLSL 1–2KB + WebGL 부트 2–3KB + 제어 2KB ≈ **5–8KB gz**, 외부 의존 0, 정적 파일 하나(`landing-field.js`)를 `comp_common.finish()` 가 랜딩에만 붙임. jsDelivr 불필요.
- **동작**: 제목 페인트 뒤 `requestIdleCallback` 로 시작; `matchMedia` reduced → 아예 초기화하지 않고 정적 SVG/WebP 포스터; `IntersectionObserver` 밖·`document.hidden` 이면 `cancelAnimationFrame`; 30fps 로 제한(빛 결에 60fps 는 불필요, WebKit '안 바뀌면 그리지 마라' 준수); DPR 1 고정; 8초 뒤 감속·정지, 정지 단추 `aria-pressed`; fps 워치독(<45 두 번 → 정지 포스터). 카카오톡 인앱 UA·`deviceMemory ≤4` 는 포스터.
- **성능(추정)**: 통합 GPU 에서 프레임당 <2ms, 모바일 <4ms; INP 영향 0(스크롤 무관, 입력 핸들러 없음); LCP 는 제목 텍스트.
- **검사**: `check_all.sh` 에 (a) 랜딩 JS 총 gz ≤150KB, (b) Playwright reducedMotion 에서 `getContext('webgl')` 미호출, (c) 캔버스 높이 ≤40vh, (d) 그라데이션 0 유지.
- 그래도 이 스케치의 결론은 A 다: 위 예산을 다 지켜도 얻는 것은 '은은한 결' 이고, 그것은 정적 `feTurbulence` 한 장(권고 4)으로 GPU 0 에 거의 같은 효과를 낸다.

### Gaps
- 3D 유무를 직접 비교한 금융 사이트 A/B 나 신뢰 실험은 없다. 판정은 (비용 실측 + 속도→전환 증거 + 수상작 점수 분해 + 대형 금융사 실측 부재) 의 합이다.
- '무채색 3D 가 유색 3D 보다 오래 간다' 는 추정이다.
- 카카오톡 인앱 브라우저의 WebGL 성능 수치는 찾지 못했다(정지 프레임 처리는 보수적 선택).
