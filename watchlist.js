/* ============================================================
   KOS ai — 워치리스트 (Firestore 계정별 클라우드 저장)
   ------------------------------------------------------------
   로그인한 사용자별로 watchlists/{uid} 문서에 관심종목을 저장합니다.
     문서 구조:  { items: { "005930": 1717650000000, ... } }  (ticker → 추가시각)
   - 로그인 안 한 상태에서 add() 호출 시 로그인 팝업(KOSGate)을 띄웁니다.
   - 변경/로딩 시 window 에 'koswatch:change' 이벤트를 발생시켜 각 페이지가 갱신합니다.
   - 별표(.wl-btn[data-wl]) 같은 공용 토글은 자동으로 on/off 동기화합니다.
   전역 API: window.KOSWatch
   ============================================================ */
import { app, auth, isConfigured } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFirestore, doc, onSnapshot, setDoc, updateDoc, deleteField }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const db = getFirestore(app);

function pwOnly(u){ return !!(u && u.providerData && u.providerData.length && u.providerData.every(function(p){ return p.providerId === 'password'; })); }

let user  = null;
let items = {};     // { ticker: addedTs }
let ready = false;
let unsub = null;

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
  if(!user){ items = {}; ready = true; fire(); return; }
  try{
    unsub = onSnapshot(ref(),
      function(snap){
        items = (snap.exists() && snap.data().items) ? snap.data().items : {};
        ready = true; fire();
      },
      function(err){ console.warn("[watchlist] 동기화 오류:", err && err.code); ready = true; fire(); }
    );
  }catch(e){ console.warn("[watchlist] 연결 실패:", e); ready = true; fire(); }
}

const KOSWatch = {
  get ready(){ return ready; },
  loggedIn(){ return !!user; },
  has(tk){ return !!items[tk]; },
  addedAt(tk){ return items[tk] || 0; },
  tickers(){ return Object.keys(items); },

  add(tk){
    if(!user){ if(window.KOSGate) window.KOSGate.showLoginPopup("워치리스트에 추가하려면 로그인이 필요해요."); return false; }
    if(pwOnly(user) && !user.emailVerified){ if(window.KOSGate) window.KOSGate.showLoginPopup("이메일 인증 후 워치리스트를 사용할 수 있어요."); return false; }
    var ts = Date.now();
    var cp = Object.assign({}, items); cp[tk] = ts; items = cp; fire();
    setDoc(ref(), { items: { [tk]: ts } }, { merge: true })
      .catch(function(e){ console.warn("[watchlist] 추가 실패:", e && e.code); });
    return true;
  },

  remove(tk){
    if(!user) return false;
    var cp = Object.assign({}, items); delete cp[tk]; items = cp; fire();
    updateDoc(ref(), { ["items." + tk]: deleteField() })
      .catch(function(){ setDoc(ref(), { items: items }).catch(function(e){ console.warn("[watchlist] 삭제 실패:", e && e.code); }); });
    return true;
  },

  clear(){
    if(!user) return false;
    items = {}; fire();
    setDoc(ref(), { items: {} }).catch(function(e){ console.warn("[watchlist] 전체삭제 실패:", e && e.code); });
    return true;
  }
};

window.KOSWatch = KOSWatch;

if(isConfigured){
  onAuthStateChanged(auth, function(u){ user = u || null; ready = false; listen(); });
}else{
  ready = true; fire();
}
