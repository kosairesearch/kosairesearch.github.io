#!/usr/bin/env python3
"""계정 페이지 다섯 — 로그인(Login.html) · 회원가입(Signup.html) · 약관 동의(Consent.html) · 계정 인증(auth-action.html) · 설정(Settings.html)
새 디자인 시안(comp).

    python3 scripts/build_auth_comp.py            # preview/login.html · signup.html · consent.html · auth-action.html · settings.html

글·항목·검사 규칙은 실사이트 그대로(소셜 셋 · 이메일 · 비밀번호 규칙 · 동의 항목 넷 · 인증 상태 넷 · 설정 세 칸 · 탈퇴 절차).
유리 카드를 없애고 400px 한 단. 실사이트는 Firebase 로 로그인·가입·인증을 처리한다. 시안은 뒤가 없으니
  · 로그인/소셜 → 홈으로 가며 ?user=이메일 을 붙여 로그인 상태 헤더를 보여 준다
  · 회원가입 → 약관 동의 → 홈(?user=)         · 설정은 ?user= 가 있어야 열린다(없으면 '로그인이 필요합니다')
  · 계정 인증은 ?state=processing|verified|reset|error 로 네 상태를 본다
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

G_SVG = '<svg viewBox="0 0 48 48"><path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/><path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/><path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/><path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>'
K_SVG = '<svg viewBox="0 0 24 24"><path fill="#191600" d="M12 3C6.99 3 3 6.2 3 10.13c0 2.52 1.68 4.73 4.2 5.99-.18.65-.67 2.42-.77 2.8-.12.47.17.46.36.34.15-.1 2.39-1.62 3.36-2.28.6.09 1.22.13 1.85.13 5.01 0 9-3.2 9-7.18S17.01 3 12 3z"/></svg>'
N_SVG = '<svg viewBox="0 0 24 24"><path fill="#fff" d="M14.7 12.55 9.05 4.5H4.5v15h4.8v-8.05l5.65 8.05h4.55v-15h-4.8z"/></svg>'
CHECK = '<svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10"/></svg>'


def social(next_page):
    return (f'<div class="social"><button type="button" class="sbtn google" id="googleBtn" data-user="you@gmail.com">{G_SVG}Google로 계속하기</button>'
            f'<button type="button" class="sbtn kakao" id="kakaoBtn" data-user="you@kakao.com">{K_SVG}카카오로 계속하기</button>'
            f'<button type="button" class="sbtn naver" id="naverBtn" data-user="you@naver.com">{N_SVG}네이버로 계속하기</button></div>')


CSS = '''
/* 로그인·회원가입·약관 동의·계정 인증은 400px 단을 가운데에 — 제목도 가운데, 입력 칸 이름표는 왼쪽(읽는 방향) */
.auth:not(.wide){margin-left:auto;margin-right:auto} .auth:not(.wide) .crumb,.auth:not(.wide) h1,.auth:not(.wide) .sub{text-align:center}
.ac-body{text-align:center}
.alert.info{color:var(--ink-72)}
.consent+.alert{margin:14px 0 0}
.ac-body form{text-align:left}
/* 약관 동의 */
.consent{margin-top:28px;border-top:1px solid var(--line)} .consent .check{padding:13px 0} .consent .check.all{font-weight:600;border-bottom:1px solid var(--line)}
.consent .doc{margin-left:auto;font:400 12px/16px var(--font);color:var(--ink-62);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .consent .doc:hover{color:var(--ink)}
.acts{display:flex;flex-direction:column;align-items:center;gap:16px;margin-top:28px} .acts .btn{width:100%}
/* 계정 인증 */
.ac-body{margin-top:28px} .ac-body .btn{margin-top:8px}
/* 설정 */
.auth.wide{max-width:560px}
.tabs-s{margin-top:28px} .pane{padding:8px 0 0} .pane[hidden]{display:none}
.srow{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:18px 0;border-bottom:1px solid var(--hair)} .srow .k{font:500 15px/22px var(--font)} .srow .k small{display:block;margin-top:4px;font:400 13px/20px var(--font);color:var(--ink-62);max-width:360px}
.opts{position:relative;display:flex;gap:18px;flex:none} .opts button{border:0;background:none;padding:0;font:500 13px/32px var(--font);color:var(--ink-62);cursor:pointer;transition:color .12s} .opts button.on{color:var(--ink);font-weight:600} .opts>.ind{margin-top:-4px}
.sw{position:relative;width:40px;height:22px;border-radius:999px;border:1px solid var(--line);background:transparent;cursor:pointer;padding:0;flex:none;transition:background-color .15s,border-color .15s} .sw::after{content:"";position:absolute;top:3px;left:3px;width:14px;height:14px;border-radius:50%;background:var(--ink-62);transition:transform .15s,background-color .15s}
.sw[aria-checked="true"]{background:var(--ink);border-color:var(--ink)} .sw[aria-checked="true"]::after{background:var(--bg);transform:translateX(18px)}
.smsg{margin:10px 0 0;font:400 12px/16px var(--font);color:var(--ink-62);min-height:16px}
.kv{margin:0;display:grid;grid-template-columns:96px 1fr;gap:12px 16px;padding:18px 0;border-bottom:1px solid var(--hair);font:400 15px/22px var(--font)} .kv dt{color:var(--ink-62)} .kv dd{margin:0;word-break:break-all}
.sbtns{display:flex;gap:24px;padding:22px 0 0} .sbtns .tbtn{font-size:14px}
.need{margin-top:32px;padding-top:24px;border-top:1px solid var(--line)} .need p{margin:0 0 20px;font:400 15px/24px var(--font);color:var(--ink-72)}
/* 탈퇴 창 — 떠 있는 면 */
.ov{display:none;position:fixed;inset:0;z-index:80;background:rgba(20,20,20,.32);align-items:center;justify-content:center;padding:24px} .ov.open{display:flex}
.dlg{width:100%;max-width:480px;max-height:90vh;overflow:auto;background:var(--surface);border:1px solid var(--hair);border-radius:16px;box-shadow:0 24px 60px rgba(20,20,20,.18);padding:28px 28px 24px;box-sizing:border-box}
.dlg h2{margin:0;font:700 22px/30px var(--font);letter-spacing:-.02em} .dlg .em{margin:6px 0 0;font:400 13px/20px var(--font);color:var(--ink-62);word-break:break-all} .dlg .warn{margin:16px 0 0;font:400 14px/22px var(--font);color:var(--up)}
.dlg .q{margin:26px 0 4px;font:500 13px/20px var(--font);color:var(--ink-72)} .dlg .check{padding:10px 0;font-size:14px}
.dlg textarea{display:block;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid var(--line);background:transparent;font:400 15px/24px var(--font);color:var(--ink);padding:8px 0;outline:0;resize:vertical;min-height:56px;margin-top:8px} .dlg textarea:focus{border-bottom-color:var(--ink)}
.dlg .ack{margin-top:22px;border-bottom:0;font-size:13px;align-items:flex-start} .dlg .ack .box{margin-top:1px}
.dlg input.type{display:block;width:100%;box-sizing:border-box;border:0;border-bottom:1px solid var(--line);background:transparent;font:500 15px/24px var(--font);color:var(--ink);padding:8px 0;outline:0;margin-top:10px} .dlg input.type:focus{border-bottom-color:var(--ink)}
.dlg .dacts{display:flex;justify-content:flex-end;align-items:center;gap:20px;margin-top:26px} .dlg .btn.danger{background:var(--up);color:#fff}
.done{text-align:center;padding:8px 0} .done h2{font-size:22px} .done p{margin:10px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}
@media (max-width:820px){.kv{grid-template-columns:80px 1fr} .srow{align-items:flex-start;flex-direction:column;gap:10px}}
'''

LOGIN = f'''<main class="wrap"><div class="auth">
  <p class="crumb">계정</p><h1>로그인</h1>
  <p class="sub">KOSAI 계정으로 로그인하시면 관심 종목과 리포트를 이어서 보실 수 있습니다.</p>
  {social('home')}
  <div class="divider">또는 이메일로 로그인</div>
  <form id="emailForm" novalidate>
    <div class="fld"><label for="email">이메일</label><input id="email" type="email" autocomplete="email" placeholder="you@example.com" required><div class="msg"></div></div>
    <div class="fld"><label for="password">비밀번호</label><input id="password" type="password" autocomplete="current-password" placeholder="비밀번호를 입력하십시오" required><div class="msg"></div></div>
    <div class="row-r"><a href="#" id="forgotLink">비밀번호를 잊으셨나요?</a></div>
    <div class="alert" id="authErr" role="alert"></div>
    <button type="submit" class="btn btn-ink" id="emailSubmit">로그인</button>
  </form>
  <p class="auth-foot">아직 계정이 없으신가요? <a href="/preview/signup.html">회원가입</a></p>
</div></main>'''

SIGNUP = f'''<main class="wrap"><div class="auth">
  <p class="crumb">계정</p><h1>회원가입</h1>
  <p class="sub">무료 계정을 만드시면 관심 종목과 AI 리포트를 저장하실 수 있습니다.</p>
  {social('consent')}
  <div class="divider">또는 이메일로 가입</div>
  <form id="emailForm" novalidate>
    <div class="fld"><label for="email">이메일</label><input id="email" type="email" autocomplete="email" placeholder="you@example.com" required><div class="msg"></div></div>
    <div class="fld"><label for="password">비밀번호</label><input id="password" type="password" autocomplete="new-password" placeholder="영문·숫자 포함 8자 이상" required><div class="msg"></div></div>
    <div class="fld"><label for="password2">비밀번호 확인</label><input id="password2" type="password" autocomplete="new-password" placeholder="비밀번호를 다시 입력하십시오" required><div class="msg"></div></div>
    <div class="alert" id="authErr" role="alert"></div>
    <button type="submit" class="btn btn-ink" id="emailSubmit">회원가입</button>
  </form>
  <p class="auth-foot">이미 계정이 있으신가요? <a href="/preview/login.html">로그인</a></p>
</div></main>'''

CONSENT = f'''<main class="wrap"><div class="auth">
  <p class="crumb">계정</p><h1 id="ttl">약관 동의</h1>
  <p class="sub" id="lede">가입을 완료하시려면 아래 항목에 동의하여 주시기 바랍니다.</p>
  <div class="consent" id="consentMount">
    <label class="check all" data-k="all"><span class="box">{CHECK}</span>전체 동의</label>
    <label class="check" data-k="age14" data-req="1"><span class="box">{CHECK}</span>[필수] 만 14세 이상입니다</label>
    <label class="check" data-k="terms" data-req="1"><span class="box">{CHECK}</span>[필수] 이용약관 동의<a class="doc" href="/preview/terms.html" target="_blank" rel="noopener">보기</a></label>
    <label class="check" data-k="privacy" data-req="1"><span class="box">{CHECK}</span>[필수] 개인정보 수집·이용 동의<a class="doc" href="/preview/privacy.html" target="_blank" rel="noopener">보기</a></label>
    <label class="check" data-k="marketing"><span class="box">{CHECK}</span>[선택] 마케팅 정보 수신 동의</label>
  </div>
  <div class="alert" id="authErr" role="alert"></div>
  <div class="acts"><button type="button" class="btn btn-ink" id="agreeBtn">동의하고 시작하기</button><button type="button" class="tbtn" id="cancelBtn">동의하지 않고 취소</button></div>
  <p class="auth-note" id="foot">동의하지 않으면 가입이 취소되고 계정은 남지 않습니다.</p>
</div></main>'''

ACTION = '''<main class="wrap"><div class="auth">
  <p class="crumb" id="crumbLabel">계정 인증</p><h1 id="acTitle">처리 중…</h1>
  <p class="sub" id="acDesc">잠시만 기다려 주시기 바랍니다.</p>
  <div class="alert" id="acErr" role="alert"></div>
  <div class="ac-body" id="acBody"><div class="spin" aria-label="로딩"></div></div>
</div></main>'''

SETTINGS = '''<main class="wrap"><div class="auth wide">
  <p class="crumb">계정</p><h1>설정</h1>
  <div id="need" class="need" hidden><p>계정 설정을 보려면 로그인이 필요합니다.</p><a class="btn btn-ink" href="/preview/login.html" style="width:auto">로그인</a></div>
  <div id="panel" hidden>
    <div class="seg tabs-s" id="tabs"><button type="button" class="on" data-t="general">일반</button><button type="button" data-t="notifications">알림</button><button type="button" data-t="account">계정</button></div>
    <div class="pane" id="p-general">
      <div class="srow"><div class="k">테마</div><div class="opts" id="themeOpts"><button type="button" data-v="light">라이트</button><button type="button" data-v="dark">다크</button></div></div>
      <div class="srow"><div class="k">언어</div><div class="opts" id="langOpts"><button type="button" class="on" data-v="ko">한국어</button><button type="button" data-v="en">English</button></div></div>
    </div>
    <div class="pane" id="p-notifications" hidden>
      <div class="srow"><div class="k">마케팅 정보 수신<small>새 리포트와 서비스 소식을 이메일로 받습니다. 받지 않아도 서비스 이용에는 아무 영향이 없습니다.</small></div><button type="button" class="sw" id="mkt" role="switch" aria-checked="false" aria-label="마케팅 정보 수신"></button></div>
      <p class="smsg" id="mktMsg"></p>
    </div>
    <div class="pane" id="p-account" hidden>
      <dl class="kv"><dt>닉네임</dt><dd id="nick">—</dd><dt>이메일</dt><dd id="mail"></dd></dl>
      <div class="sbtns"><button type="button" class="tbtn" id="signOutBtn">로그아웃</button><button type="button" class="tbtn danger" id="delBtn">회원 탈퇴</button></div>
    </div>
  </div>
</div></main>
<div class="ov" id="wd" role="dialog" aria-modal="true" aria-labelledby="wdH"><div class="dlg" id="wdCard">
  <h2 id="wdH">정말 탈퇴하시겠습니까?</h2><p class="em" id="wdEm"></p>
  <p class="warn">계정과 저장된 관심종목이 영구 삭제되며, 되돌릴 수 없습니다.</p>
  <p class="q">떠나시는 이유를 알려주시면 개선에 반영하겠습니다 (복수 선택 가능)</p>
  <div id="wdReasons"></div>
  <textarea id="wdDetail" rows="2" placeholder="자세한 의견 (선택)"></textarea>
  <label class="check ack" id="wdAck"><span class="box">''' + CHECK + '''</span>위 내용을 이해했으며 되돌릴 수 없음에 동의합니다</label>
  <input class="type" id="wdType" type="text" autocomplete="off" placeholder="확인을 위해 ‘탈퇴’ 를 입력하십시오">
  <div class="dacts"><button type="button" class="tbtn" id="wdCancel">취소</button><button type="button" class="btn danger" id="wdGo" disabled>탈퇴하기</button></div>
</div></div>'''

REASONS = ["원하는 종목·정보가 부족합니다", "정보가 정확하지 않습니다", "자주 이용하지 않습니다", "이용 방법이 불편합니다", "기타"]

JS_COMMON = r'''
  var EMAIL=/^[^@\s]+@[^@\s]+\.[^@\s]+$/,err=document.getElementById('authErr');
  /* 오류는 그 칸 밑에(.fld .msg) — 빈 칸은 한꺼번에 다 표시하고 첫 칸에 초점. 단추 위의 .alert 은 칸 하나에 매이지 않는 것만:
     실사이트에서는 서버 응답(비밀번호 틀림 · 시도 초과 · 인증 안 된 계정)이 여기 온다. 시안에서는 안내(정보색)만 쓴다. */
  function showErr(m,info){if(!err)return;err.textContent=m;err.classList.toggle('info',!!info);err.classList.add('show')}
  function hideErr(){if(err)err.classList.remove('show')}
  function fldMsg(id,m){var f=document.getElementById(id).closest('.fld');f.querySelector('.msg').textContent=m;f.classList.add('err')}
  function clearAll(){hideErr();document.querySelectorAll('.fld.err').forEach(function(f){f.classList.remove('err')})}
  function focusBad(ids){var id=ids.filter(function(i){return document.getElementById(i).closest('.fld').classList.contains('err')})[0];if(id)document.getElementById(id).focus();return !!id}
  document.querySelectorAll('.fld input').forEach(function(i){i.addEventListener('input',function(){i.closest('.fld').classList.remove('err')})});
  function go(page,email){location.href='/preview/'+page+'.html'+(email?'?user='+encodeURIComponent(email):'')}
'''

LOGIN_JS = r'''(function(){''' + JS_COMMON + r'''
  document.querySelectorAll('.sbtn').forEach(function(b){b.addEventListener('click',function(){go('home',b.dataset.user)})});
  document.getElementById('emailForm').addEventListener('submit',function(e){e.preventDefault();clearAll();var email=document.getElementById('email').value.trim(),pw=document.getElementById('password').value;
    if(!email)fldMsg('email','이메일을 입력하여 주시기 바랍니다.');else if(!EMAIL.test(email))fldMsg('email','올바른 이메일 형식이 아닙니다.');
    if(!pw)fldMsg('password','비밀번호를 입력하여 주시기 바랍니다.');
    if(focusBad(['email','password']))return;
    /* 실사이트: signInWithEmailAndPassword → 틀리면 단추 위 .alert 에 '이메일 또는 비밀번호가 올바르지 않습니다' · 인증 안 된 계정이면 안내 — 시안은 홈으로 */
    go('home',email)});
  document.getElementById('forgotLink').addEventListener('click',function(e){e.preventDefault();clearAll();var email=document.getElementById('email').value.trim();
    if(!email)fldMsg('email','이메일을 먼저 입력하여 주시기 바랍니다.');else if(!EMAIL.test(email))fldMsg('email','올바른 이메일 형식이 아닙니다.');
    if(focusBad(['email']))return;
    showErr('비밀번호 재설정 메일을 보내 드렸습니다. 메일함을 확인하여 주시기 바랍니다.',true)});
})();'''

SIGNUP_JS = r'''(function(){''' + JS_COMMON + r'''
  document.querySelectorAll('.sbtn').forEach(function(b){b.addEventListener('click',function(){go('consent',b.dataset.user)})});
  document.getElementById('emailForm').addEventListener('submit',function(e){e.preventDefault();clearAll();var email=document.getElementById('email').value.trim(),pw=document.getElementById('password').value,pw2=document.getElementById('password2').value;
    if(!email)fldMsg('email','이메일을 입력하여 주시기 바랍니다.');else if(!EMAIL.test(email))fldMsg('email','올바른 이메일 형식이 아닙니다.');
    if(!pw)fldMsg('password','비밀번호를 입력하여 주시기 바랍니다.');else if(pw.length<8||!/[A-Za-z]/.test(pw)||!/[0-9]/.test(pw))fldMsg('password','비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.');
    if(!pw2)fldMsg('password2','비밀번호를 다시 입력하여 주시기 바랍니다.');else if(pw!==pw2)fldMsg('password2','비밀번호가 일치하지 않습니다.');
    if(focusBad(['email','password','password2']))return;
    /* 실사이트: 계정을 만든 뒤 Consent.html 로 — 동의는 거기서 받는다 */
    go('consent',email)});
})();'''

CONSENT_JS = r'''(function(){''' + JS_COMMON + r'''
  var qs=new URLSearchParams(location.search),email=qs.get('user')||'you@example.com';
  var rows=[].slice.call(document.querySelectorAll('#consentMount .check')),all=rows.shift();
  function sync(){all.classList.toggle('on',rows.every(function(r){return r.classList.contains('on')}))}
  all.addEventListener('click',function(){var on=!all.classList.contains('on');rows.forEach(function(r){r.classList.toggle('on',on)});sync();hideErr()});
  rows.forEach(function(r){r.addEventListener('click',function(e){if(e.target.closest('a'))return;r.classList.toggle('on');sync();hideErr()})});
  document.getElementById('agreeBtn').addEventListener('click',function(){var ok=rows.filter(function(r){return r.dataset.req}).every(function(r){return r.classList.contains('on')});
    if(!ok){showErr('필수 항목에 모두 동의하셔야 가입하실 수 있습니다.');return}
    /* 실사이트: 동의 기록(CONSENT_VERSION · 마케팅 동의 시각)을 저장하고 홈으로 */
    go('home',email)});
  document.getElementById('cancelBtn').addEventListener('click',function(){go('home')});
})();'''

ACTION_JS = r'''(function(){
  var qs=new URLSearchParams(location.search),state=qs.get('state')||'processing',email=qs.get('user')||'you@example.com';
  var crumb=document.getElementById('crumbLabel'),title=document.getElementById('acTitle'),desc=document.getElementById('acDesc'),body=document.getElementById('acBody'),err=document.getElementById('acErr');
  function btn(label,href){return '<a class="btn btn-ink" href="'+href+'">'+label+'</a>'}
  function show(s){err.classList.remove('show');
    if(s==='verified'){crumb.textContent='이메일 인증';title.textContent='이메일 인증이 완료되었습니다';desc.textContent='KOSAI의 모든 기능을 이용하실 수 있습니다.';body.innerHTML=btn('로그인하러 가기','/preview/login.html')}
    else if(s==='error'){crumb.textContent='계정 인증';title.textContent='링크가 만료되었습니다';desc.textContent='보안을 위해 인증 링크는 일정 시간이 지나면 만료됩니다. 메일을 다시 요청하여 주시기 바랍니다.';body.innerHTML=btn('로그인 페이지로','/preview/login.html')}
    else if(s==='done'){crumb.textContent='비밀번호 재설정';title.textContent='비밀번호가 변경되었습니다';desc.textContent='새 비밀번호로 로그인하여 주시기 바랍니다.';body.innerHTML=btn('로그인하러 가기','/preview/login.html')}
    else if(s==='reset'){crumb.textContent='비밀번호 재설정';title.textContent='새 비밀번호 설정';desc.textContent=email+' 계정의 새 비밀번호를 입력하여 주시기 바랍니다.';
      body.innerHTML='<form id="rs" novalidate><div class="fld"><label for="np">새 비밀번호</label><input id="np" type="password" autocomplete="new-password" placeholder="영문·숫자 포함 8자 이상" required><div class="msg"></div></div><div class="fld"><label for="np2">새 비밀번호 확인</label><input id="np2" type="password" autocomplete="new-password" placeholder="비밀번호를 다시 입력하십시오" required><div class="msg"></div></div><button type="submit" class="btn btn-ink" id="rsSubmit">비밀번호 변경</button></form>';
      var np=document.getElementById('np'),np2=document.getElementById('np2');
      function fm(i,m){var f=i.closest('.fld');f.querySelector('.msg').textContent=m;f.classList.add('err')}
      [np,np2].forEach(function(i){i.addEventListener('input',function(){i.closest('.fld').classList.remove('err')})});
      document.getElementById('rs').addEventListener('submit',function(e){e.preventDefault();err.classList.remove('show');[np,np2].forEach(function(i){i.closest('.fld').classList.remove('err')});var pw=np.value,pw2=np2.value;
        if(!pw)fm(np,'비밀번호를 입력하여 주시기 바랍니다.');else if(pw.length<8||!/[A-Za-z]/.test(pw)||!/[0-9]/.test(pw))fm(np,'비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.');
        if(!pw2)fm(np2,'비밀번호를 다시 입력하여 주시기 바랍니다.');else if(pw!==pw2)fm(np2,'비밀번호가 일치하지 않습니다.');
        var bad=[np,np2].filter(function(i){return i.closest('.fld').classList.contains('err')})[0];if(bad){bad.focus();return}
        show('done')})}
    else{crumb.textContent='계정 인증';title.textContent='처리 중…';desc.textContent='잠시만 기다려 주시기 바랍니다.';body.innerHTML='<div class="spin" aria-label="로딩"></div>'}}
  show(state);window.__acShow=show;
})();'''

SETTINGS_JS = r'''(function(){
  var qs=new URLSearchParams(location.search),u=qs.get('user'),email=(u==='1'||u==='')?'you@example.com':u;
  if(!u){document.getElementById('need').hidden=false;return}
  document.getElementById('panel').hidden=false;document.getElementById('mail').textContent=email;
  /* 탭 */
  var tabs=document.getElementById('tabs');window.kosInd(tabs,'x');
  tabs.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;[].slice.call(tabs.children).forEach(function(c){c.classList.toggle('on',c===b)});window.kosInd(tabs,'x')();['general','notifications','account'].forEach(function(t){document.getElementById('p-'+t).hidden=t!==b.dataset.t})});
  /* 일반 — 테마는 진짜로 바뀐다 · 언어는 시안이라 표시만 */
  var root=document.documentElement,th=document.getElementById('themeOpts');
  function paintTheme(){var t=root.getAttribute('data-theme')||'light';[].slice.call(th.children).forEach(function(b){b.classList.toggle('on',b.dataset.v===t)});window.kosInd(th,'x')(true)}
  paintTheme();th.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;root.setAttribute('data-theme',b.dataset.v);try{localStorage.setItem('kos-theme',b.dataset.v)}catch(x){}paintTheme();if(window.__kosPaintTheme)window.__kosPaintTheme()});
  new MutationObserver(paintTheme).observe(root,{attributes:true,attributeFilter:['data-theme']});
  var lg=document.getElementById('langOpts');window.kosInd(lg,'x');lg.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;[].slice.call(lg.children).forEach(function(c){c.classList.toggle('on',c===b)});window.kosInd(lg,'x')()});
  /* 알림 */
  var sw=document.getElementById('mkt'),msg=document.getElementById('mktMsg');
  sw.addEventListener('click',function(){var on=sw.getAttribute('aria-checked')!=='true';sw.setAttribute('aria-checked',on?'true':'false');msg.textContent=on?'저장되었습니다. 언제든 다시 끌 수 있습니다.':'저장되었습니다. 더 이상 마케팅 메일을 보내지 않습니다.'});
  /* 계정 */
  function out(){location.href='/preview/home.html'}
  document.getElementById('signOutBtn').addEventListener('click',out);
  var wd=document.getElementById('wd'),card=document.getElementById('wdCard'),ack=document.getElementById('wdAck'),type=document.getElementById('wdType'),goBtn=document.getElementById('wdGo');
  var rs=document.getElementById('wdReasons');rs.innerHTML=''' + repr(REASONS) + r'''.map(function(r){return '<label class="check" data-r="'+r+'"><span class="box">''' + CHECK.replace("'", "\\'") + r'''</span>'+r+'</label>'}).join('');
  rs.addEventListener('click',function(e){var c=e.target.closest('.check');if(c)c.classList.toggle('on')});
  function syncGo(){goBtn.disabled=!(ack.classList.contains('on')&&type.value.trim()==='탈퇴')}
  ack.addEventListener('click',function(){ack.classList.toggle('on');syncGo()});type.addEventListener('input',syncGo);
  document.getElementById('delBtn').addEventListener('click',function(){document.getElementById('wdEm').textContent=email;wd.classList.add('open');type.focus()});
  document.getElementById('wdCancel').addEventListener('click',function(){wd.classList.remove('open')});
  wd.addEventListener('click',function(e){if(e.target===wd)wd.classList.remove('open')});
  document.addEventListener('keydown',function(e){if(e.key==='Escape')wd.classList.remove('open')});
  goBtn.addEventListener('click',function(){/* 실사이트: 사유 기록 → 서버가 계정·관심종목·동의 기록을 지운다 */
    card.innerHTML='<div class="done"><h2>탈퇴가 완료되었습니다</h2><p>그동안 KOSAI를 이용해 주셔서 감사합니다. 계정과 저장된 정보는 모두 삭제되었습니다.</p><a class="btn btn-ink" href="/preview/home.html" style="width:auto">홈으로</a></div>'});
})();'''


def page(title, body, js, extra_css='', module=None):
    """js 는 시안용 흉내(IIFE). module 이 있으면(스테이징) 그 대신 실제 Firebase 모듈(scripts/auth_staging.py)을 붙인다."""
    tail = ('\n<script>\n' + C.JS + '\n</script>\n<script type="module">\n' + module + '\n</script>') if module else ('\n<script>\n' + js + '\n' + C.JS + '\n</script>')
    return (C.head(title) + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.AUTH_CSS + '\n' + CSS + extra_css + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + '\n' + body + '\n' + C.FOOTER + tail + '\n</body>\n</html>')


def build(outs=None):
    outs = outs or {'login': 'preview/login.html', 'signup': 'preview/signup.html', 'consent': 'preview/consent.html', 'action': 'preview/auth-action.html', 'settings': 'preview/settings.html'}
    stg = C.MODE == 'staging'
    real = {}
    if stg:   # 스테이징: 실제 Firebase 인증 모듈. 설정은 build_settings_staging 이 따로 만든다.
        import auth_staging as A
        real = {'login': A.LOGIN_JS, 'signup': A.SIGNUP_JS, 'consent': A.CONSENT_JS, 'action': A.ACTION_JS}
    for key, out, title, body, js in [
        ('login', outs['login'], '로그인 | KOSAI', LOGIN, LOGIN_JS),
        ('signup', outs['signup'], '회원가입 | KOSAI', SIGNUP, SIGNUP_JS),
        ('consent', outs['consent'], '약관 동의 | KOSAI', CONSENT, CONSENT_JS),
        ('action', outs['action'], '계정 인증 | KOSAI', ACTION, ACTION_JS),
        ('settings', outs['settings'], '설정 | KOSAI', SETTINGS, SETTINGS_JS),
    ]:
        if stg and key == 'settings':
            continue
        html = page(title if stg else title.replace(' | KOSAI', ' — 디자인 시안 | KOSAI'), body, js, module=real.get(key))
        C.emit(ROOT / out, html)
        print(f'✅ {ROOT / out} · {len(html):,}자')


if __name__ == '__main__':
    build()
