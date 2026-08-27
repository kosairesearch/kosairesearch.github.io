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

      <section class="adm-card card glass">
        <h2>회원 조회</h2>
        <div class="adm-search">
          <input id="q" type="text" placeholder="이메일 또는 uid" autocomplete="off" />
          <button type="button" class="btn btn-primary" id="findBtn">조회</button>
        </div>
        <div id="result"></div>
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
.adm{max-width:760px;margin:0 auto}
.adm-card{padding:22px 24px;margin-bottom:16px}
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
  "불러오지 못했습니다.":"Could not load."
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
function when(iso){
  if(!iso) return '—';
  try{
    const d = new Date(iso);
    const p = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  }catch(_){ return iso; }
}
function yn(v){
  const s = document.createElement('span');
  s.className = v ? 'adm-yes' : 'adm-no';
  s.textContent = v ? '동의' : '미동의';
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
  }catch(e){
    /* 권한이 없으면 서버가 permission-denied 를 준다. 그 문장을 그대로
       보여 준다 — '관리자만 볼 수 있습니다.' 로 충분하다. */
    fail((e && e.message) || T('불러오지 못했습니다.'));
  }
});

function drawStats(s){
  const box = $('#stats');
  box.textContent = '';
  const items = [
    ['전체 회원', s.total, false],
    ['동의 완료', s.consented, false],
    ['마케팅 동의', s.marketing, false],
    ['2년 재확인 대상', s.dueRecheck, s.dueRecheck > 0],
  ];
  for(const [label, n, warn] of items){
    const d = document.createElement('div');
    d.className = 'adm-stat' + (warn ? ' warn' : '');
    const b = document.createElement('b'); b.textContent = String(n ?? 0);
    const sp = document.createElement('span'); sp.textContent = T(label);
    d.appendChild(b); d.appendChild(sp); box.appendChild(d);
  }
  if(s.dueRecheck > 0){
    const p = $('#dueNote');
    p.textContent = '정보통신망법 시행령 제62조의3 — 광고성 정보 수신동의는 동의일부터 2년마다 유지 여부를 확인해야 합니다. 안내할 때 전송자 명칭·수신동의 날짜·철회 방법을 함께 알려야 합니다.';
    p.hidden = false;
  }
}

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
  row('가입 방법', esc(r.signupMethod));
  row('가입 시각', when(r.createdAt));
  row('동의서 판', esc(r.consents.version));
  row('받은 방식', esc(r.consents.method));
  row('만 14세 이상', yn(r.consents.age14));
  row('이용약관', yn(r.consents.terms));
  row('개인정보 수집·이용', yn(r.consents.privacy));
  row('마케팅 수신', yn(r.consents.marketing));
  row('동의 시각', when(r.consents.agreedAt));
  row('마케팅 켠 시각', when(r.marketingAt));
  row('마케팅 끈 시각', when(r.marketingOffAt));
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
}

$('#csvBtn').addEventListener('click', async () => {
  const note = $('#csvNote');
  note.textContent = ' ' + T('확인하는 중…');
  try{
    const r = await call('adminMarketingList');
    const head = ['uid', 'email', 'provider', 'agreedAt', 'marketingAt'];
    const cell = v => '"' + String(v == null ? '' : v).replace(/"/g, '""') + '"';
    const csv = [head.join(',')]
      .concat(r.rows.map(x => head.map(k => cell(x[k])).join(',')))
      .join('\\r\\n');
    /* 엑셀이 UTF-8 을 알아보게 BOM 을 붙인다. 없으면 한글이 깨져 보인다. */
    const blob = new Blob(['\\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'kosai-marketing-' + new Date().toISOString().slice(0, 10) + '.csv';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
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
