/* 스크롤을 부드럽게 — 마우스 휠 한 칸이 툭 떨어지지 않고 미끄러지듯 멈춘다.

   왜. 윈도우에서 휠을 굴리면 운영체제가 100px 씩 뚝뚝 끊어 옮긴다. 맥
   트랙패드는 원래 부드러워서 이 차이를 못 느낀다. 사장이 쓰는 화면은
   윈도우라 "딱딱 떨어진다" 고 했다.

   CSS 의 scroll-behavior:smooth 로는 안 된다. 그건 #앵커로 뛸 때만 듣고
   휠에는 아무 상관이 없다.

   방식. lenis.js 가 휠을 가로채서 목표 위치까지 감속 곡선으로 창을 옮긴다.
   창을 진짜로 옮기는 것이라 position:sticky·스크롤 이벤트·주소창의 #앵커가
   그대로 산다(변형(transform)으로 밀어 올리는 옛 방식은 이게 다 깨진다).

   안 켜는 경우 — 셋 다 켜면 오히려 불편해지는 자리다.
     1. 손가락으로 넘기는 화면(휴대폰·태블릿). 원래 부드럽고, 여기서
        가로채면 손가락을 뗀 뒤에도 화면이 따라와 멀미가 난다.
     2. 움직임을 줄여 달라고 설정한 사람(prefers-reduced-motion).
        전정기관이 예민하면 이런 감속이 어지럼증을 만든다.
     3. lenis.js 가 못 떴을 때. 그냥 원래 스크롤로 둔다 — 화면이 안
        움직이는 것보다 낫다.

   되돌리기. 이 파일과 lenis.js 를 부르는 <script> 두 줄만 빼면 원래대로
   돌아온다. 화면 코드는 이 파일을 모른다.
*/
(function () {
  if (typeof window === "undefined" || !window.matchMedia) return;

  var coarse = window.matchMedia("(pointer: coarse)").matches;          // 손가락 화면
  var calm   = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (coarse || calm || typeof window.Lenis !== "function") return;

  /* 안에서 따로 굴러가는 상자 — 설정 창의 목록·칸, 대화상자, 가로로 넘기는
     표. 여기서는 가로채면 안 된다. 상자 안에서 휠을 굴렸는데 뒤쪽 본문이
     움직여 버리기 때문이다. lenis 가 휠이 지나온 길을 위로 훑으면서
     이 함수를 부른다 — 하나라도 참이면 그 휠은 브라우저에 그냥 넘긴다. */
  var overflowOf = new WeakMap();
  function scrollsItself(node) {
    if (!node || node.nodeType !== 1) return false;
    if (node.hasAttribute("data-lenis-prevent")) return true;
    var oy = overflowOf.get(node);
    if (oy === undefined) {
      try { oy = getComputedStyle(node).overflowY; } catch (e) { oy = ""; }
      overflowOf.set(node, oy);
    }
    if (oy !== "auto" && oy !== "scroll") return false;
    // 상자가 실제로 넘칠 때만. 넘치지 않으면 굴릴 것이 없다.
    return node.scrollHeight > node.clientHeight + 1;
  }

  var lenis;
  try {
    lenis = new window.Lenis({
      // 휠을 굴린 뒤 멈추기까지(초). 짧으면 원래와 구분이 안 가고, 길면
      // 손을 뗐는데 화면이 계속 흘러 답답하다.
      //
      // 0.9 로 시작했는데 사장이 "좀 늦게 멈춘다" 고 해서 0.7 로 줄였다.
      // 휠 한 번(600px)이 완전히 멎기까지 864ms → 694ms 다. 0.6 도 재 봤지만
      // (614ms) "너무 짧게는 하지 말라" 고 해서 그 앞에서 멈췄다.
      duration: 0.7,
      // 빠르게 시작해 부드럽게 선다.
      easing: function (t) { return 1 - Math.pow(1 - t, 3); },
      wheelMultiplier: 1,          // 한 번 굴리는 거리는 운영체제 기본과 같게
      smoothWheel: true,
      syncTouch: false,            // 손가락은 원래 스크롤 그대로
      orientation: "vertical",
      gestureOrientation: "vertical",
      prevent: scrollsItself
    });
  } catch (e) { return; }

  /* CSS 의 scroll-behavior:smooth 는 여기서 끈다. 브라우저도 부드럽게
     옮기려 하고 lenis 도 옮기려 해서 두 번 움직인다. 파일 16개의 CSS 를
     고치는 대신 켜질 때만 끄면, 이 파일을 빼는 순간 원래대로 돌아온다. */
  try { document.documentElement.style.scrollBehavior = "auto"; } catch (e) {}

  function frame(t) { lenis.raf(t); requestAnimationFrame(frame); }
  requestAnimationFrame(frame);

  /* #앵커로 뛰는 링크. 그냥 두면 브라우저가 순간이동시키고 lenis 가 뒤늦게
     따라와 두 번 움직인다. 여기서 받아 한 번에 미끄러지게 한다. */
  document.addEventListener("click", function (e) {
    var a = e.target && e.target.closest && e.target.closest('a[href^="#"]');
    if (!a || a.hasAttribute("data-lenis-prevent")) return;
    var id = a.getAttribute("href");
    if (!id || id === "#") return;
    var el;
    try { el = document.querySelector(id); } catch (err) { return; }
    if (!el) return;
    e.preventDefault();
    lenis.scrollTo(el, { offset: -90 });   // 떠 있는 머리띠에 안 가리도록
  });

  window.KOSSmoothScroll = lenis;   // 필요하면 바깥에서 멈추고 다시 켤 수 있게
})();
