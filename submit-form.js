/* ============================================================
   KOSAI — 문의·피드백 폼 전송 (Cloud Functions → Resend → hello@kosai.kr)
   window.KOSsubmitForm(payload) 로 호출. payload:
     { kind:'contact'|'feedback', name, email, category, rating, message, page, hp }
   ============================================================ */
import { app, SOCIAL } from "./firebase-config.js";
import { getFunctions, httpsCallable } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const fns = getFunctions(app, SOCIAL.functionsRegion);
window.KOSsubmitForm = (payload) =>
  httpsCallable(fns, "submitForm")(payload || {}).then(r => r.data);
