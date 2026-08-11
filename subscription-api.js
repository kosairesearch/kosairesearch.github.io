/* ============================================================
   KOSAI — 구독 서버 함수 호출 (공용)
   ------------------------------------------------------------
   구독 관리 화면과 멤버십 화면이 같은 서버 함수를 부른다. 두 곳이 각자
   httpsCallable 을 만들어 쓰면, 스테이징에서 모의 백엔드로 돌리는 우회도
   두 군데에 따로 넣어야 한다. 한쪽만 고치면 미리보기에서 한 화면은 되고
   한 화면은 안 되는 상태가 된다. 진입점을 여기 하나로 모은다.
   ============================================================ */
import { app, isConfigured, SOCIAL } from "./firebase-config.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const fns = isConfigured ? getFunctions(app, SOCIAL.functionsRegion || "asia-northeast3") : null;

export const call = (n, d) => httpsCallable(fns, n)(d || {});
