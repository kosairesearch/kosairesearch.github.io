/* ============================================================
   KOSAI — 워치리스트 (Firestore 계정별 클라우드 저장)
   ------------------------------------------------------------
   로그인한 사용자별로 watchlists/{uid} 문서에 관심종목을 저장합니다.
     문서 구조:  { items: { "005930": 1717650000000, ... } }  (ticker → 추가시각)
   - 로그인 안 한 상태에서 add() 호출 시 로그인 팝업(KOSGate)을 띄웁니다.
   - 변경/로딩 시 window 에 'koswatch:change' 이벤트를 발생시켜 각 페이지가 갱신합니다.
   - 별표(.wl-btn[data-wl]) 같은 공용 토글은 자동으로 on/off 동기화합니다.
   전역 API: window.KOSWatch
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js?v=7b8f27a5";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, onSnapshot, setDoc, updateDoc, deleteField }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const db = getFirestore(app);

function pwOnly(u){ return !!(u && u.providerData && u.providerData.length && u.providerData.every(function(p){ return p.providerId === 'password'; })); }

let user  = null;
let items = {};     // { ticker: addedTs }
let ready = false;
let unsub = null;

/* 첫 그림 — 지난번 목록을 기억해 둔다(kos-wl-cache). 이 브라우저가 로그인 상태였다고 기억하면
   (kos-signed=1, auth-state.js 가 적는다) 파이어스토어 답이 오기 전에 그 목록으로 먼저 그린다 —
   관심종목 페이지가 첫 그림에 '비어 있습니다'를 보였다가 목록으로 바뀌던 것을 없앤다
   (2026-09-24 사장). 답이 오면 그것으로 갈아 끼운다(대개 같다). 로그아웃하면 지운다. */
const CACHE_KEY = "kos-wl-cache";
let provisional = false;
try{
  if(localStorage.getItem('kos-signed') === '1'){
    var cached = JSON.parse(localStorage.getItem(CACHE_KEY) || 'null');
    if(cached && cached.items && typeof cached.items === 'object'){ items = cached.items; provisional = true; }
  }
}catch(e){}
function remember(){
  try{ if(user) localStorage.setItem(CACHE_KEY, JSON.stringify({ uid: user.uid, items: items })); else localStorage.removeItem(CACHE_KEY); }catch(e){}
}

function fire(){
  // 공용 별표 버튼 자동 동기화
  try{
    document.querySelectorAll('[data-wl]').forEach(function(el){
      el.classList.toggle('on', !!items[el.dataset.wl]);
    });
  }catch(e){}
  try{ window.dispatchEvent(new CustomEvent('koswatch:change')); }catch(e){}
}

function ref(){ return doc(db, "watchlists", user.uid); }

function listen(){
  if(unsub){ try{ unsub(); }catch(e){} unsub = null; }
  if(!user){ items = {}; ready = true; provisional = false; remember(); fire(); return; }
  try{
    unsub = onSnapshot(ref(),
      function(snap){
        items = (snap.exists() && snap.data().items) ? snap.data().items : {};
        ready = true; provisional = false; remember(); fire();
      },
      function(err){ console.warn("[watchlist] 동기화 오류:", err && err.code); ready = true; fire(); }
    );
  }catch(e){ console.warn("[watchlist] 연결 실패:", e); ready = true; fire(); }
}

const KOSWatch = {
  get ready(){ return ready; },
  get provisional(){ return provisional && !ready; },   /* 기억으로 그린 상태(답 오기 전) */
  loggedIn(){ return !!user; },
  has(tk){ return !!items[tk]; },
  addedAt(tk){ return items[tk] || 0; },
  tickers(){ return Object.keys(items); },

  add(tk){
    if(!user){ if(window.KOSGate) window.KOSGate.showLoginPopup("관심종목에 추가하시려면 로그인이 필요합니다."); return false; }
    if(pwOnly(user) && !user.emailVerified){ if(window.KOSGate) window.KOSGate.showLoginPopup("이메일 인증 후 관심종목을 이용하실 수 있습니다."); return false; }
    var ts = Date.now();
    var cp = Object.assign({}, items); cp[tk] = ts; items = cp; remember(); fire();
    if (window.KOSA) KOSA.track("watchlist_add", { ticker: tk });
    setDoc(ref(), { items: { [tk]: ts } }, { merge: true })
      .catch(function(e){ console.warn("[watchlist] 추가 실패:", e && e.code); });
    return true;
  },

  remove(tk){
    if(!user) return false;
    var cp = Object.assign({}, items); delete cp[tk]; items = cp; remember(); fire();
    updateDoc(ref(), { ["items." + tk]: deleteField() })
      .catch(function(){ setDoc(ref(), { items: items }).catch(function(e){ console.warn("[watchlist] 삭제 실패:", e && e.code); }); });
    return true;
  },

  clear(){
    if(!user) return false;
    items = {}; remember(); fire();
    setDoc(ref(), { items: {} }).catch(function(e){ console.warn("[watchlist] 전체삭제 실패:", e && e.code); });
    return true;
  }
};

window.KOSWatch = KOSWatch;

if(isConfigured){
  if(provisional) fire();          // 기억한 목록으로 먼저 그린다
  onAuthStateChanged(auth, function(u){ user = u || null; ready = false; listen(); });
}else{
  ready = true; fire();
}
