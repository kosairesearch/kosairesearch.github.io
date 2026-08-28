#!/usr/bin/env python3
"""Admin.html 을 만든다 — 껍데기는 Login.html 에서 그대로 떠 온다.

Consent.html 과 같은 방식이다. 이 사이트는 페이지마다 헤더·푸터·테마 토글·
i18n 엔진을 통째로 복사해 갖고 있어서, 손으로 베끼면 새 페이지만 어긋난다.

  python3 scripts/build_admin_page.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Login.html"
OUT = ROOT / "Admin.html"

MAIN = '''<main>
  <div class="wrap">
    <div class="head">
      <div class="kick">ADMIN</div>
      <h1>동의 관리</h1>
      <p>회원이 언제 무엇에 동의했는지 확인합니다.</p>
    </div>

    <div class="adm" id="admGate">
      <div class="auth-err" id="authErr"></div>
      <p class="adm-note" id="admLoading">확인하는 중…</p>
    </div>

    <div class="adm" id="admBody" hidden>
      <section class="adm-card card glass">
        <h2>요약</h2>
        <div class="adm-stats" id="stats"></div>
        <p class="adm-note" id="dueNote" hidden></p>
      </section>

      <section class="adm-card card glass" id="ncSec" hidden>
        <h2>동의 없는 계정</h2>
        <p class="adm-note">회원 목록에는 나오지 않습니다 — 동의 기록이 없어 회원으로 세지 않기 때문입니다. 동의 제도가 생기기 전에 가입한 분은 로그인하면 동의 화면이 뜹니다.</p>
        <div class="adm-wrap"><table class="adm-tbl adm-tbl-nc" id="nc"></table></div>
        <div class="adm-act">
          <button type="button" class="btn btn-primary" id="noticeBtn">안내 메일 대상 확인</button>
          <button type="button" class="btn" id="orphanBtn">유령 문서 지금 정리</button>
          <span class="adm-note" id="noticeNote"></span>
        </div>
        <div id="noticeBox"></div>
      </section>

      <section class="adm-card card glass">
        <h2>회원 목록</h2>
        <p class="adm-note">모든 시각은 한국 시간(KST)입니다. 줄을 누르면 아래 조회에 채워집니다.</p>
        <div class="adm-search">
          <input id="filter" type="text" placeholder="이메일 · 가입 방법으로 거르기" autocomplete="off" />
          <button type="button" class="btn btn-primary" id="usersCsvBtn">CSV</button>
        </div>
        <div class="adm-wrap"><table class="adm-tbl" id="users"></table></div>
        <p class="adm-note" id="usersNote"></p>
      </section>

      <section class="adm-card card glass">
        <h2>회원 조회</h2>
        <div class="adm-search">
          <input id="q" type="text" placeholder="이메일 또는 uid" autocomplete="off" />
          <button type="button" class="btn btn-primary" id="findBtn">조회</button>
        </div>
        <div id="result"></div>
      </section>

      <section class="adm-card card glass">
        <h2>모닝 브리핑 기상 시험</h2>
        <p class="adm-note">브리핑을 깨우는 장치가 살아 있는지 확인합니다. 눌러도 브리핑이 발행되지는 않습니다 — 워크플로 실행이 만들어지는 데까지만 봅니다. 장중에는 실행이 정지 조건에 걸려 멈추는 것이 정상입니다.</p>
        <button type="button" class="btn btn-primary" id="wakeBtn">깨워 보기</button>
        <span class="adm-note" id="wakeNote"></span>
      </section>

      <section class="adm-card card glass">
        <h2>마케팅 수신 동의자</h2>
        <p class="adm-note">발송 전에 여기서 뽑습니다. 내려받은 파일에는 개인정보가 들어 있으니 다루는 데 주의해 주세요.</p>
        <button type="button" class="btn btn-primary" id="csvBtn">목록 내려받기 (CSV)</button>
        <span class="adm-note" id="csvNote"></span>
      </section>
    </div>
  </div>
</main>'''

CSS = '''<style id="admin-css">
/* 760px 은 로그인 폼 폭이다. 표 일곱 칸을 그 안에 밀어 넣으니 이메일이
   글자마다 줄바꿈되고 마지막 칸이 잘렸다. 관리 화면은 읽는 화면이라
   넓어도 된다. */
.adm{max-width:1000px;margin:0 auto}
/* 로그인 폼에서 떠 온 .card 가 560px 로 묶고 있다. 표가 그 안에 갇히면
   칸이 잘려 보인다 — 풀어 준다. */
.adm-card{max-width:none;padding:22px 24px;margin-bottom:16px}
.adm-card h2{margin:0 0 14px;font:800 17px/1.3 var(--font-sans);letter-spacing:-.02em}
.adm-note{margin:8px 0 0;font:400 12.5px/1.7 var(--font-sans);color:var(--fg-3)}
.adm-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.adm-stat{padding:14px;border:1px solid var(--border-2);border-radius:var(--radius-md)}
.adm-stat b{display:block;font:800 22px/1.2 var(--font-sans);letter-spacing:-.02em}
.adm-stat span{display:block;margin-top:4px;font:500 12px var(--font-sans);color:var(--fg-3)}
.adm-stat.warn b{color:#c0282b}
:root[data-theme="dark"] .adm-stat.warn b{color:#ff8a8c}
.adm-search{display:flex;gap:8px}
.adm-search input{flex:1;padding:12px 14px;border-radius:var(--radius-sm);
  border:1px solid var(--border-2);background:transparent;color:var(--fg-1);
  font:400 14px var(--font-sans)}
.adm-search input:focus{outline:none;border-color:var(--fg-1)}
.adm-kv{margin:14px 0 0;display:grid;grid-template-columns:auto 1fr;gap:6px 14px;
  font:400 13.5px/1.6 var(--font-sans)}
.adm-kv dt{color:var(--fg-3);white-space:nowrap}
.adm-kv dd{margin:0;color:var(--fg-1);word-break:break-all}
.adm-yes{color:#0a7d32;font-weight:600}
.adm-no{color:var(--fg-3)}
:root[data-theme="dark"] .adm-yes{color:#3ddc84}
.adm-ev{margin:16px 0 0;border-top:1px solid var(--hair);padding-top:12px}
.adm-ev table{width:100%;border-collapse:collapse;font:400 12.5px var(--font-sans)}
.adm-ev th{text-align:left;color:var(--fg-3);font-weight:600;padding:5px 8px 5px 0;white-space:nowrap}
.adm-ev td{padding:5px 8px 5px 0;color:var(--fg-2);border-top:1px solid var(--hair);word-break:break-all}
.adm-wrap{overflow-x:auto}
.adm-tbl{width:100%;min-width:780px;border-collapse:collapse;
  font:400 13px var(--font-sans);margin-top:14px}
.adm-tbl th{text-align:left;color:var(--fg-3);font-weight:600;padding:6px 12px 6px 0;white-space:nowrap}
.adm-tbl td{padding:8px 12px 8px 0;color:var(--fg-2);border-top:1px solid var(--hair);white-space:nowrap}
.adm-tbl tbody tr{cursor:pointer}
.adm-tbl tbody tr:hover td{color:var(--fg-1);background:var(--bg-2)}
.adm-tbl td.mail{color:var(--fg-1);font-weight:600;max-width:260px;
  overflow:hidden;text-overflow:ellipsis}
.adm-tbl th:last-child,.adm-tbl td:last-child{padding-right:0}
.adm-tbl-nc{min-width:420px}
.adm-tbl-nc tbody tr{cursor:default}
.adm-tbl-nc td.uid{color:var(--fg-3);font:400 11.5px var(--font-mono,ui-monospace,monospace)}
.adm-act{margin-top:18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.adm-warn{margin-top:14px;padding:14px 16px;border-radius:var(--radius-md);
  border:1px solid #c0282b;font:400 13px/1.7 var(--font-sans);color:var(--fg-1)}
:root[data-theme="dark"] .adm-warn{border-color:#ff8a8c}
.adm-warn b{display:block;margin-bottom:6px;font-weight:700}
.adm-warn ul{margin:8px 0 0;padding-left:18px;color:var(--fg-2)}
.adm-dead{color:#c0282b;font-weight:600}
:root[data-theme="dark"] .adm-dead{color:#ff8a8c}
@media (max-width:640px){
  .adm-card{padding:18px 16px}
  .adm-search{flex-direction:column}
}
</style>'''

DICT = '''if(window.KOSi18n) KOSi18n.register({
  "동의 관리":"Consent records",
  "회원이 언제 무엇에 동의했는지 확인합니다.":"See when each member agreed to what.",
  "확인하는 중…":"Checking…",
  "관리자만 볼 수 있습니다.":"Administrators only.",
  "요약":"Summary",
  "회원 조회":"Look up a member",
  "조회":"Search",
  "마케팅 수신 동의자":"Marketing opt-ins",
  "목록 내려받기 (CSV)":"Download list (CSV)",
  "발송 전에 여기서 뽑습니다. 내려받은 파일에는 개인정보가 들어 있으니 다루는 데 주의해 주세요.":
    "Export before sending. The file contains personal data — handle it carefully.",
  "전체 회원":"Members",
  "동의 완료":"With consent",
  "마케팅 동의":"Marketing opt-in",
  "2년 재확인 대상":"Due for re-confirmation",
  "찾지 못했습니다.":"Not found.",
  "불러오지 못했습니다.":"Could not load.",
  "회원 목록":"Members",
  "모든 시각은 한국 시간(KST)입니다. 줄을 누르면 아래 조회에 채워집니다.":
    "All times are Korea time (KST). Click a row to load it into the lookup below.",
  "이메일 · 가입 방법으로 거르기":"Filter by email or sign-up method",
  "아직 회원이 없습니다.":"No members yet.",
  "이메일":"Email",
  "구글":"Google",
  "카카오":"Kakao",
  "네이버":"Naver",
  "가입 방법":"Sign-up",
  "가입 시각":"Joined",
  "동의 시각":"Agreed",
  "마케팅":"Marketing",
  "메일 인증":"Email verified",
  "동의함":"Yes",
  "동의 안 함":"No",
  "없음":"None",
  "계정 없음":"No account",
  "미인증":"Unverified",
  "가입한 곳에서 확인한 주소입니다.":"Verified by the sign-in provider.",
  "재동의 대상":"Needs re-consent",
  "동의 없는 계정":"Without consent",
  "동의 없는 계정은 가입하다 동의 화면에서 나간 계정입니다. 만든 지 24시간이 지나면 매일 12:30에 자동으로 지워집니다(동의 제도 시행 전 계정은 지우지 않습니다).":
    "Accounts without consent were abandoned at the consent screen. They are deleted automatically at 12:30 daily once 24 hours old (accounts predating the consent system are never deleted).",
  "동의 없는 계정을 세지 못했습니다. 숫자가 0이라는 뜻이 아닙니다.":
    "Could not count accounts without consent — the number is not zero, it is unknown.",
  "동의서 판":"Consent version",
  "모닝 브리핑 기상 시험":"Morning brief wake-up test",
  "브리핑을 깨우는 장치가 살아 있는지 확인합니다. 눌러도 브리핑이 발행되지는 않습니다 — 워크플로 실행이 만들어지는 데까지만 봅니다. 장중에는 실행이 정지 조건에 걸려 멈추는 것이 정상입니다.":
    "Checks that the wake-up path is alive. Pressing it does not publish a brief — it only confirms a workflow run is created. During market hours the run stopping at the data guard is expected.",
  "깨워 보기":"Send wake-up",
  "깨웠습니다. GitHub Actions 에 새 실행이 떴는지 확인해 주세요.":
    "Sent. Check GitHub Actions for a new run.",
  "깨우지 못했습니다. 토큰이 등록되지 않았거나 권한이 부족합니다.":
    "Could not send — the token is missing or lacks permission.",
  "카카오 약관":"Kakao terms",
  "제공자 원본":"Provider response",
  "유령 문서 지금 정리":"Clean up orphan records",
  " 정리했습니다. 새로고침하면 사라집니다.":" cleaned up.",
  "정리할 유령 문서가 없습니다.":"No orphan records to clean up.",
  "안내 메일 대상 확인":"Preview notice recipients",
  "에게 안내 메일이 갑니다.":" will receive the notice email.",
  "보낼 대상이 없습니다.":"No one to notify.",
  " 가입":" joined",
  "제외":"Excluded",
  "동의 제도 시행 후 가입(가입하다 만 계정)":"joined after the consent screen existed (abandoned sign-ups)",
  "이메일 주소 없음":"no email address",
  "이미 안내함":"already notified",
  "위 주소로 지금 보내기":"Send to the addresses above",
  "보내는 중…":"Sending…",
  "보냈습니다.":"Sent.",
  "실패":"failed",
  "남음":"remaining",
  "회원 목록에는 나오지 않습니다 — 동의 기록이 없어 회원으로 세지 않기 때문입니다. 동의 제도가 생기기 전에 가입한 분은 로그인하면 동의 화면이 뜹니다.":
    "They do not appear in the member list because there is no consent record to count. Anyone who joined before the consent screen existed will see it the next time they sign in.",
  "(현재 판)":"(current)",
  "체크박스":"Checkbox",
  "가입 버튼 아래 고지 문구":"Notice under the sign-up button",
  "카카오 동의 화면":"Kakao consent screen",
  "네이버 동의 화면":"Naver consent screen",
  "완료":"Verified",
  "정보통신망법 시행령 제62조의3 — 광고성 정보 수신동의는 동의일부터 2년마다 유지 여부를 확인해야 합니다. 안내할 때 전송자 명칭·수신동의 날짜·철회 방법을 함께 알려야 합니다.":
    "Network Act Enforcement Decree art. 62-3 — marketing consent must be re-confirmed every two years from the date it was given, and the notice must state the sender's name, the consent date, and how to withdraw.",
  "상한(2000명)에 걸려 일부만 보입니다.":"Capped at 2,000 — some members are not shown."
});'''

SCRIPT = '''<script type="module">
/* 동의 관리 화면.
 *
 * 동의를 받아 두기만 하고 볼 방법이 없으면 받지 않은 것과 크게 다르지 않다.
 * 문의가 들어오거나 분쟁이 생겼을 때 "이 사람이 언제 무엇에 동의했는가" 를
 * 그 자리에서 답할 수 있어야 한다.
 *
 * 권한은 서버가 판단한다. 화면에서 숨기는 것은 잠그는 것이 아니다 —
 * 세 함수 모두 관리자 이메일인지 먼저 확인하고, 아니면 아무것도 돌려주지
 * 않는다. 여기 코드는 그 결과를 보여 줄 뿐이다.
 */
import { app, auth, SOCIAL } from "./firebase-config.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
import { getFunctions, httpsCallable }
  from "https://www.gstatic.com/firebasejs/10.12.2/firebase-functions.js";

const T = m => (window.KOSi18n ? window.KOSi18n.t(m) : m);
const $ = s => document.querySelector(s);
const fns = getFunctions(app, (SOCIAL && SOCIAL.functionsRegion) || "asia-northeast3");
const call = (n, d) => httpsCallable(fns, n)(d || {}).then(r => r.data);

function fail(msg){
  $('#admLoading').hidden = true;
  const e = $('#authErr');
  e.textContent = msg; e.style.display = 'block';
}
function esc(v){ return v == null || v === '' ? '—' : String(v); }

/* 사전 엔진은 페이지가 뜰 때 한 번 훑는다. 우리가 나중에 서버에서 받아
   그려 넣는 글자는 그 뒤에 생기므로 훑힌 적이 없다 — 영어 모드인데 표에만
   '네이버' 가 남아 있던 이유다. 그려 넣을 때마다 다시 훑게 한다. */
function relabel(){ try{ if(window.KOSi18n) KOSi18n.apply(); }catch(_){} }

/* 서버는 UTC(...Z)로 준다. 그대로 내보내면 '2026-08-20T13:37:39.911Z' 가
   찍히는데, 이건 한국 시간 22:37 이다 — 아홉 시간 어긋난 숫자를 읽으라고
   내미는 셈이다. 브라우저 시간대에 맡기지도 않는다. 관리자가 어디서 열든
   같은 시각이 나와야 기록으로 쓸 수 있다. 'sv-SE' 를 쓰면 2026-08-20 22:37
   모양이 나오고, 엑셀도 이 모양은 날짜로 알아본다. */
const KST = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hour12: false
});
function kst(iso){
  if(!iso) return '';
  try{ return KST.format(new Date(iso)).replace('T', ' '); }catch(_){ return String(iso); }
}
function when(iso){ return kst(iso) || '—'; }

/* 동의를 어느 화면에서 받았는지. 'checkbox' 같은 코드값을 그대로 내보내면
   읽는 사람이 무슨 화면인지 알 수 없다. */
function methodLabel(m){
  if(m === 'checkbox') return T('체크박스');
  if(m === 'signup-notice') return T('가입 버튼 아래 고지 문구');
  if(m === 'kakao-sync') return T('카카오 동의 화면');
  if(m === 'naver-consent') return T('네이버 동의 화면');
  return m || '';
}

/* 표를 내려받는다. head 는 [키, 보이는 이름, 다듬는 함수] 세 쪽이다. */
function download(name, head, rows){
  const cell = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
  const line = r => head.map(([k, , f]) => cell(f ? f(r[k], r) : r[k])).join(',');
  const csv = [head.map(h => cell(h[1])).join(',')].concat(rows.map(line)).join('\\r\\n');
  /* 엑셀이 UTF-8 을 알아보게 BOM 을 붙인다. 없으면 한글이 깨져 보인다. */
  const blob = new Blob(['\\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name + '-' + kst(new Date().toISOString()).slice(0, 10) + '.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
function yn(v){
  const s = document.createElement('span');
  s.className = v ? 'adm-yes' : 'adm-no';
  s.textContent = T(v ? '동의함' : '동의 안 함');
  return s;
}

onAuthStateChanged(auth, async user => {
  if(!user){
    location.replace('Login.html?next=' + encodeURIComponent('Admin.html'));
    return;
  }
  try{
    const s = await call('adminConsentStats');
    $('#admLoading').hidden = true;
    $('#admGate').hidden = true;
    $('#admBody').hidden = false;
    drawStats(s);
    loadUsers();
  }catch(e){
    /* 권한이 없으면 서버가 permission-denied 를 준다. 그 문장을 그대로
       보여 준다 — '관리자만 볼 수 있습니다.' 로 충분하다. */
    fail((e && e.message) || T('불러오지 못했습니다.'));
  }
});

/* 마지막으로 받은 요약. 언어가 바뀌면 이걸로 다시 그린다. */
let STATS = null;

function drawStats(s){
  STATS = s;
  const box = $('#stats');
  box.textContent = '';
  /* '동의 없는 계정' 은 못 셌을 때 null 로 온다. 0 으로 갈음하면 '없다'로
     읽혀서, 못 본 것과 없는 것이 뒤섞인다. 물음표로 둔다. */
  const items = [
    ['전체 회원', s.total, false],
    ['동의 완료', s.consented, false],
    ['마케팅 동의', s.marketing, false],
    ['2년 재확인 대상', s.dueRecheck, s.dueRecheck > 0],
    ['재동의 대상', s.stale, s.stale > 0],
    ['동의 없는 계정', s.noConsent == null ? '?' : s.noConsent, s.noConsent > 0],
  ];
  for(const [label, n, warn] of items){
    const d = document.createElement('div');
    d.className = 'adm-stat' + (warn ? ' warn' : '');
    const b = document.createElement('b'); b.textContent = String(n ?? 0);
    const sp = document.createElement('span'); sp.textContent = T(label);
    d.appendChild(b); d.appendChild(sp); box.appendChild(d);
  }

  const notes = [];
  if(s.dueRecheck > 0){
    notes.push('정보통신망법 시행령 제62조의3 — 광고성 정보 수신동의는 동의일부터 2년마다 유지 여부를 확인해야 합니다. 안내할 때 전송자 명칭·수신동의 날짜·철회 방법을 함께 알려야 합니다.');
  }
  /* 판 번호별 인원. 약관을 개정하면 여기서 재동의 진행률이 보인다. */
  if(s.byVersion && Object.keys(s.byVersion).length){
    const parts = Object.keys(s.byVersion).sort().reverse()
      .map(v => v + ' ' + countText(s.byVersion[v]) + (v === s.version ? ' ' + T('(현재 판)') : ''));
    notes.push(T('동의서 판') + ' — ' + parts.join(' · '));
  }
  if(s.noConsent > 0){
    notes.push(T('동의 없는 계정은 가입하다 동의 화면에서 나간 계정입니다. 만든 지 24시간이 지나면 매일 12:30에 자동으로 지워집니다(동의 제도 시행 전 계정은 지우지 않습니다).'));
  }
  if(s.noConsent == null){
    notes.push(T('동의 없는 계정을 세지 못했습니다. 숫자가 0이라는 뜻이 아닙니다.'));
  }

  const p = $('#dueNote');
  p.textContent = '';
  if(notes.length){
    notes.forEach((t, i) => {
      if(i) p.appendChild(document.createElement('br'));
      const sp = document.createElement('span');
      sp.textContent = t;
      p.appendChild(sp);
    });
    p.hidden = false;
  } else {
    p.hidden = true;
  }

  drawNoConsent(s.noConsentRows || []);
  relabel();
}

/* 동의 없는 계정 목록. 없으면 칸 자체를 숨긴다 — 늘 비어 있는 게 정상이고,
   빈 표가 늘 떠 있으면 진짜 뭔가 생겼을 때 눈에 안 들어온다. */
function drawNoConsent(rows){
  const sec = $('#ncSec');
  if(!rows.length){ sec.hidden = true; return; }
  sec.hidden = false;
  const t = $('#nc');
  t.textContent = '';
  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  ['이메일', '가입 시각', 'uid'].forEach(h => {
    const th = document.createElement('th'); th.textContent = T(h); hr.appendChild(th);
  });
  thead.appendChild(hr); t.appendChild(thead);
  const tb = document.createElement('tbody');
  for(const r of rows){
    const tr = document.createElement('tr');
    [[esc(r.email), 'mail'], [when(r.createdAt), ''], [r.uid, 'uid']].forEach(([v, cls]) => {
      const td = document.createElement('td');
      if(cls) td.className = cls;
      td.textContent = v;
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  }
  t.appendChild(tb);
}

/* ── 회원 목록 ───────────────────────────────────────────────── */
let USERS = [];
let TRUNCATED = false;

async function loadUsers(){
  const note = $('#usersNote');
  note.textContent = T('확인하는 중…');
  try{
    const r = await call('adminUserList');
    USERS = r.rows || [];
    TRUNCATED = !!r.truncated;
    drawUsers();
  }catch(e){
    note.textContent = (e && e.message) || T('불러오지 못했습니다.');
  }
}

/* '5명' 은 사전에 담을 수 없다 — 숫자가 매번 다르다. 언어를 보고 만든다. */
function countText(n){
  const en = window.KOSi18n && KOSi18n.lang === 'en';
  return en ? (n + (n === 1 ? ' member' : ' members')) : (n + '명');
}

function drawUsers(){
  const q = $('#filter').value.trim().toLowerCase();
  const rows = q
    ? USERS.filter(u => (String(u.email || '') + ' ' + String(u.providerLabel || '') + ' '
                         + String(u.provider || '') + ' ' + u.uid).toLowerCase().includes(q))
    : USERS;

  const t = $('#users');
  t.textContent = '';
  $('#usersNote').textContent = countText(USERS.length)
    + (TRUNCATED ? ' — ' + T('상한(2000명)에 걸려 일부만 보입니다.') : '');
  if(!USERS.length){ $('#usersNote').textContent = T('아직 회원이 없습니다.'); return; }

  const thead = document.createElement('thead');
  const hr = document.createElement('tr');
  ['이메일', '가입 방법', '가입 시각', '동의 시각', '마케팅', '메일 인증'].forEach(h => {
    const th = document.createElement('th'); th.textContent = T(h); hr.appendChild(th);
  });
  thead.appendChild(hr); t.appendChild(thead);

  const tb = document.createElement('tbody');
  for(const u of rows){
    const tr = document.createElement('tr');
    const put = (v, cls) => {
      const td = document.createElement('td');
      if(cls) td.className = cls;
      if(v instanceof Node) td.appendChild(v); else td.textContent = v;
      tr.appendChild(td);
    };
    put(esc(u.email), 'mail');
    put(esc(u.providerLabel));
    put(when(u.createdAt));
    put(u.agreedAt ? when(u.agreedAt) : mark('없음'));
    put(u.marketing ? (u.marketingAt ? when(u.marketingAt) : T('동의함')) : '—');
    /* 계정이 Auth 에 없으면 유령 문서다. 사람이 치워야 한다. */
    put(verifyCell(u));
    /* uid 는 표에 두지 않는다. 한 칸을 통째로 잡아먹는데 눈으로 훑을 일이
       없다 — 줄을 누르면 아래 조회에 uid 까지 다 나오고, CSV 에도 들어간다. */
    tr.title = u.uid + (u.email ? ' · ' + u.email : '');
    tr.addEventListener('click', () => {
      $('#q').value = u.email || u.uid;
      $('#findBtn').click();
      $('#result').scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    tb.appendChild(tr);
  }
  t.appendChild(tb);
  relabel();
}

/* 메일 인증 칸이 답해야 하는 것은 하나다 — 이 주소가 본인 것으로
   확인됐는가.

   처음에는 Firebase 의 emailVerified 를 그대로 내보냈다. 그건 '우리가
   보낸 인증 메일을 눌렀는가' 라는 뜻이다. 소셜 계정에는 인증 메일을
   보낸 적이 없으니 영원히 false 다 — 네이버로 가입한 사람이 빨간
   '미인증' 으로 뜬 이유고, 고치겠다고 '주소 미등록' 이라 써 붙인 것은
   내부 사정을 화면에 그대로 내민 것이라 더 나빴다.

   구글·카카오·네이버는 자기네가 확인한 주소만 넘겨준다. 확인된 것으로
   본다. 우리 인증 메일을 잣대로 삼는 것은 이메일 가입뿐이다. */
function verifyCell(u){
  if(u.live === false) return mark('계정 없음');
  if(!u.email) return '\u2014';
  if(u.provider && u.provider !== 'email'){
    const s = document.createElement('span');
    s.textContent = T('완료');
    s.title = T('가입한 곳에서 확인한 주소입니다.');
    return s;
  }
  if(u.emailVerified == null) return '\u2014';
  return u.emailVerified ? T('완료') : mark('미인증');
}

function mark(text){
  const s = document.createElement('span');
  s.className = 'adm-dead';
  s.textContent = T(text);
  return s;
}

/* ── 동의 안내 메일 ───────────────────────────────────────────────
   되돌릴 수 없는 일이라 한 번에 보내지 않는다. 누구에게 갈지 먼저
   보여 주고, 사람이 그 목록을 본 다음에야 보내는 버튼이 생긴다.
   서버도 같은 순서로 막고 있다(dryRun 이 기본값이다). */
$('#noticeBtn').addEventListener('click', async () => {
  const note = $('#noticeNote'), box = $('#noticeBox');
  $('#noticeBtn').disabled = true;
  note.textContent = ' ' + T('확인하는 중…');
  box.textContent = '';
  try{
    const r = await call('adminNotifyUnconsented', { dryRun: true });
    note.textContent = '';
    $('#noticeBtn').disabled = false;
    drawNoticePlan(box, r);
  }catch(e){
    $('#noticeBtn').disabled = false;
    note.textContent = ' ' + ((e && e.message) || T('불러오지 못했습니다.'));
  }
});

function drawNoticePlan(box, r){
  box.textContent = '';
  const w = document.createElement('div');
  w.className = 'adm-warn';

  const b = document.createElement('b');
  b.textContent = r.count > 0
    ? countText(r.count) + T('에게 안내 메일이 갑니다.')
    : T('보낼 대상이 없습니다.');
  w.appendChild(b);

  if(r.count > 0){
    const ul = document.createElement('ul');
    r.rows.forEach(x => {
      const li = document.createElement('li');
      li.textContent = x.email + '  ·  ' + when(x.createdAt) + T(' 가입');
      ul.appendChild(li);
    });
    w.appendChild(ul);
  }

  /* 왜 빠졌는지 적는다. 숫자가 예상과 다를 때 그 자리에서 답이 되게 한다. */
  const sk = r.skipped || {};
  const parts = [];
  if(sk.recent) parts.push(T('동의 제도 시행 후 가입(가입하다 만 계정)') + ' ' + sk.recent);
  if(sk.noEmail) parts.push(T('이메일 주소 없음') + ' ' + sk.noEmail);
  if(sk.alreadySent) parts.push(T('이미 안내함') + ' ' + sk.alreadySent);
  if(parts.length){
    const p = document.createElement('p');
    p.style.cssText = 'margin:10px 0 0;font:400 12.5px/1.7 var(--font-sans);color:var(--fg-3)';
    p.textContent = T('제외') + ' — ' + parts.join(' · ');
    w.appendChild(p);
  }

  if(r.count > 0){
    const go = document.createElement('button');
    go.type = 'button';
    go.className = 'btn btn-primary';
    go.style.marginTop = '14px';
    go.textContent = T('위 주소로 지금 보내기');
    go.addEventListener('click', async () => {
      go.disabled = true;
      go.textContent = T('보내는 중…');
      try{
        const s = await call('adminNotifyUnconsented', { dryRun: false });
        go.remove();
        const done = document.createElement('p');
        done.style.cssText = 'margin:12px 0 0;font:600 13px var(--font-sans)';
        done.textContent = T('보냈습니다.') + ' ' + countText(s.sent)
          + (s.failed && s.failed.length ? ' · ' + T('실패') + ' ' + s.failed.length : '')
          + (s.remaining ? ' · ' + T('남음') + ' ' + s.remaining : '');
        w.appendChild(done);
        if(s.failed && s.failed.length){
          const ul = document.createElement('ul');
          s.failed.forEach(f => {
            const li = document.createElement('li');
            li.textContent = f.email + ' — ' + f.reason;
            ul.appendChild(li);
          });
          w.appendChild(ul);
        }
        relabel();
      }catch(e){
        go.disabled = false;
        go.textContent = T('위 주소로 지금 보내기');
        const p = document.createElement('p');
        p.style.cssText = 'margin:10px 0 0;font:600 12.5px var(--font-sans);color:#c0282b';
        p.textContent = (e && e.message) || T('불러오지 못했습니다.');
        w.appendChild(p);
      }
    });
    w.appendChild(go);
  }

  box.appendChild(w);
  relabel();
}

/* 브리핑 기상 시험. 결과는 GitHub 의 실행 목록에서 확인한다. */
$('#wakeBtn').addEventListener('click', async () => {
  const note = $('#wakeNote');
  $('#wakeBtn').disabled = true;
  note.textContent = ' ' + T('확인하는 중…');
  try{
    const r = await call('adminWakeBrief');
    note.textContent = ' ' + T(r && r.ok
      ? '깨웠습니다. GitHub Actions 에 새 실행이 떴는지 확인해 주세요.'
      : '깨우지 못했습니다. 토큰이 등록되지 않았거나 권한이 부족합니다.');
  }catch(e){
    note.textContent = ' ' + ((e && e.message) || T('불러오지 못했습니다.'));
  }
  $('#wakeBtn').disabled = false;
});

/* 콘솔에서 Auth 사용자만 지우면 users 문서가 남는다. 매일 12:30 정리가
   치우지만 개발 중에는 그때까지 기다릴 이유가 없다. */
$('#orphanBtn').addEventListener('click', async () => {
  const note = $('#noticeNote');
  $('#orphanBtn').disabled = true;
  note.textContent = ' ' + T('확인하는 중…');
  try{
    const r = await call('adminPurgeOrphans');
    note.textContent = ' ' + (r.count
      ? countText(r.count) + T(' 정리했습니다. 새로고침하면 사라집니다.')
      : T('정리할 유령 문서가 없습니다.'));
    if(r.count){ loadUsers(); }
  }catch(e){
    note.textContent = ' ' + ((e && e.message) || T('불러오지 못했습니다.'));
  }
  $('#orphanBtn').disabled = false;
});

$('#filter').addEventListener('input', drawUsers);

/* 언어가 정해지거나 바뀌면 우리가 그린 것을 다시 그린다.

   두 가지를 처리한다.

   하나, 언어 전환. 표는 우리가 만든 것이라 사전 엔진이 훑기 전에 우리가
   먼저 손봐야 한다 — 엔진도 그 순서로 부른다.

   둘, 첫 화면의 경합. 엔진의 lang 은 DOMContentLoaded 에서 init() 이
   돌기 전까지 'ko' 다. 그 전에 그린 글자는 한국어로 굳는데, 사전에 있는
   말은 apply() 가 고쳐 줘도 '2026-09-01 3명' 처럼 우리가 이어 붙인
   문장은 사전 키가 아니라 그대로 남는다. 실제로 영어 모드에서 그 줄만
   한국어였다. init() 이 이 리스너를 불러 주므로 여기서 다시 그리면 된다. */
if(window.KOSi18n) KOSi18n.register(null, () => {
  if(STATS) drawStats(STATS);
  if(USERS.length) drawUsers();
});

$('#usersCsvBtn').addEventListener('click', () => {
  if(!USERS.length) return;
  /* 동의 항목을 하나씩 적는다. 요약 한 칸('동의 시각')만 있으면 분쟁이
     생겼을 때 이 파일로는 "개인정보 수집·이용에 동의했다" 를 못 보여 준다.
     내보낸 파일이 곧 제출할 자료다. 판 번호와 받은 방식도 같이 적는다 —
     '언제' 못지않게 '무엇을 보고' 눌렀는지가 증빙이다. */
  const yn = v => (v ? '동의' : '미동의');
  download('kosai-members', [
    ['email', '이메일'],
    ['providerLabel', '가입 방법'],
    ['createdAt', '가입 시각(KST)', kst],
    ['agreedAt', '동의 시각(KST)', kst],
    ['age14', '만 14세 이상', v => (v ? '확인' : '미확인')],
    ['terms', '이용약관', yn],
    ['privacy', '개인정보 수집·이용', yn],
    ['marketing', '마케팅 수신', yn],
    ['marketingAt', '마케팅 동의 시각(KST)', kst],
    ['version', '동의서 판'],
    ['method', '받은 방식', methodLabel],
    ['emailVerified', '메일 인증', (v, r) => (
       r.live === false ? '계정 없음'
       : !r.email ? ''
       : (r.provider && r.provider !== 'email') ? '완료'
       : v == null ? '' : v ? '완료' : '미인증')],
    ['uid', 'uid'],
  ], USERS);
});

$('#findBtn').addEventListener('click', async () => {
  const q = $('#q').value.trim();
  if(!q) return;
  const out = $('#result');
  out.textContent = T('확인하는 중…');
  try{
    const r = await call('adminConsentLookup', { q });
    out.textContent = '';
    if(!r.found){ out.textContent = T('찾지 못했습니다.'); return; }
    drawMember(out, r);
  }catch(e){ out.textContent = (e && e.message) || T('불러오지 못했습니다.'); }
});
$('#q').addEventListener('keydown', e => { if(e.key === 'Enter') $('#findBtn').click(); });

function drawMember(out, r){
  const dl = document.createElement('dl');
  dl.className = 'adm-kv';
  const row = (k, v) => {
    const dt = document.createElement('dt'); dt.textContent = k;
    const dd = document.createElement('dd');
    if(v instanceof Node) dd.appendChild(v); else dd.textContent = v;
    dl.appendChild(dt); dl.appendChild(dd);
  };
  row('uid', esc(r.uid));
  row('이메일', esc(r.email));
  row('가입 방법', esc(r.signupLabel));
  row('가입 시각', when(r.createdAt));
  row('동의서 판', esc(r.consents.version));
  row('받은 방식', esc(methodLabel(r.consents.method)));
  row('만 14세 이상', yn(r.consents.age14));
  row('이용약관', yn(r.consents.terms));
  row('개인정보 수집·이용', yn(r.consents.privacy));
  row('마케팅 수신', yn(r.consents.marketing));
  row('동의 시각', when(r.consents.agreedAt));
  row('마케팅 켠 시각', when(r.marketingAt));
  row('마케팅 끈 시각', when(r.marketingOffAt));
  /* 제공자가 보낸 약관 목록 그대로. 우리 항목이 맞게 옮겨졌는지는 이걸
     봐야 안다 — 태그는 개발자센터에서 정한 값이라 코드가 미리 모른다.

     두 곳의 모양이 다르다. 카카오는 항목마다 동의 여부를 주고(tag·required·
     agreed), 네이버는 동의한 것만 목록에 담아 준다(termCode·agreeDate).
     담기는 자리는 같아서(consents.kakaoTerms — 카카오만 있던 시절 이름이다)
     여기서 갈라 읽는다. */
  if(r.consents.kakaoTerms && r.consents.kakaoTerms.length){
    row('제공자 약관', r.consents.kakaoTerms
      .map(t => t.termCode
        ? t.termCode + '(동의' + (t.agreeDate ? ' ' + t.agreeDate : '') + ')'
        : t.tag + (t.required ? '(필수) ' : '(선택) ') + (t.agreed ? '동의' : '미동의'))
      .join('  ·  '));
  }
  /* 네이버 프로필 응답에 어떤 칸이 왔는지. 약관은 여기 오지 않는다 —
     위의 '제공자 약관' 줄이 그것이다. */
  if(r.providerRaw){
    row('제공자 원본', JSON.stringify(r.providerRaw));
  }
  out.appendChild(dl);

  if(r.events && r.events.length){
    const wrap = document.createElement('div');
    wrap.className = 'adm-ev';
    const h = document.createElement('div');
    h.style.cssText = 'font:600 13px var(--font-sans);margin-bottom:6px';
    h.textContent = '이력 (' + r.events.length + '건)';
    wrap.appendChild(h);
    const sc = document.createElement('div'); sc.className = 'adm-wrap';
    const t = document.createElement('table');
    t.innerHTML = '<tr><th>시각</th><th>구분</th><th>판</th><th>경로</th><th>IP</th></tr>';
    for(const e of r.events){
      const tr = document.createElement('tr');
      [when(e.at), esc(e.kind), esc(e.version), esc(e.provider || e.method), esc(e.ip)]
        .forEach(v => { const td = document.createElement('td'); td.textContent = v; tr.appendChild(td); });
      t.appendChild(tr);
    }
    sc.appendChild(t); wrap.appendChild(sc); out.appendChild(wrap);
  }
  relabel();
}

$('#csvBtn').addEventListener('click', async () => {
  const note = $('#csvNote');
  note.textContent = ' ' + T('확인하는 중…');
  try{
    const r = await call('adminMarketingList');
    /* 이메일이 맨 앞이다 — 발송 목록에서 제일 먼저 봐야 하는 칸이고, uid 를
       앞에 두면 엑셀에서 그 긴 문자열에 가려 정작 주소가 안 보인다.
       시각은 KST 로 바꿔 적는다(원본은 UTC 라 아홉 시간이 어긋난다). */
    download('kosai-marketing', [
      ['email', '이메일'],
      ['providerLabel', '가입 방법'],
      ['agreedAt', '가입 동의 시각(KST)', kst],
      ['marketingAt', '마케팅 동의 시각(KST)', kst],
      ['uid', 'uid'],
    ], r.rows || []);
    note.textContent = ' ' + r.count + '건';
  }catch(e){ note.textContent = ' ' + ((e && e.message) || T('불러오지 못했습니다.')); }
});
</script>'''


def build():
    src = SRC.read_text(encoding="utf-8")
    out, n = re.subn(r"<main>.*?</main>", lambda _: MAIN, src, count=1, flags=re.S)
    if n != 1:
        return None, "<main> 을 찾지 못함"
    out, n = re.subn(r"if\(window\.KOSi18n\) KOSi18n\.register\(\{.*?\n\}\);",
                     lambda _: DICT, out, count=1, flags=re.S)
    if n != 1:
        return None, f"페이지 사전을 찾지 못함(매칭 {n})"
    out, n = re.subn(r'<script type="module">.*?</script>',
                     lambda _: SCRIPT, out, count=1, flags=re.S)
    if n != 1:
        return None, f"페이지 스크립트를 찾지 못함(매칭 {n})"
    out = out.replace("<body>", CSS + "\n<body>", 1)
    if "admin-css" not in out:
        return None, "CSS 를 넣을 자리를 찾지 못함"
    out, n = re.subn(r'(<div class="crumb"><a href="Home\.html">홈</a> / <b>)[^<]*(</b></div>)',
                     r"\g<1>동의 관리\g<2>", out, count=1)
    if n != 1:
        return None, "빵부스러기를 찾지 못함"
    out = re.sub(r"<title>[^<]*</title>", "<title>동의 관리 — KOSAI</title>", out, count=1)
    out = re.sub(r'(<meta (?:name|property)="(?:description|og:description|twitter:description)" content=")[^"]*"',
                 r'\1KOSAI 동의 관리."', out)
    out = re.sub(r'(<meta (?:name|property)="(?:og:title|twitter:title)" content=")[^"]*"',
                 r'\1동의 관리 — KOSAI"', out)
    out = out.replace("https://kosai.kr/Login.html", "https://kosai.kr/Admin.html")
    out = out.replace("<head>", '<head>\n<meta name="robots" content="noindex,nofollow" />', 1)
    OUT.write_text(out, encoding="utf-8")
    return True, f"{OUT.name} 생성 ({len(out.splitlines())}줄)"


def main():
    ok, note = build()
    print(f"  {'✅' if ok else '❌'} {note}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
