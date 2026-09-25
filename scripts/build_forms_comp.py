#!/usr/bin/env python3
"""문의하기(Contact.html) · 피드백(Feedback.html) — 새 디자인 시안(comp).

    python3 scripts/build_forms_comp.py            # preview/contact.html · preview/feedback.html

글·항목·검사 규칙은 실사이트 그대로: 문의 유형/피드백 종류(구분 탭), 만족도(세 얼굴 · 고르기 전엔 보내기 잠김),
이메일 형식·내용 5자 검사, 벌집(hp) 칸, 접수 완료 화면. 유리 카드를 없애고 720px 한 단의 밑줄 입력으로 바꿨다.
실사이트는 KOSsubmitForm(Firebase 함수)으로 보낸다. 시안은 보내지 않고 접수 화면만 보여 준다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
.page-hero,.page-body{max-width:640px}
.page-body{padding-top:36px}
form .fld:last-of-type{margin-bottom:30px}
/* 만족도 — 세 얼굴. 고른 것만 먹색 */
.rating{display:flex;gap:28px;padding:6px 0 2px}
.rate{display:flex;flex-direction:column;align-items:center;gap:8px;border:0;background:none;padding:0;cursor:pointer;color:var(--ink-30);transition:color .12s} .rate:hover{color:var(--ink-72)} .rate.on{color:var(--ink)}
.rate svg{width:36px;height:36px;fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round} .rate .lab{font:500 12px/16px var(--font)}
.rate.on .lab{font-weight:600}
.direct{margin-top:40px;padding-top:24px;border-top:1px solid var(--hair);display:flex;justify-content:space-between;align-items:baseline;gap:16px;text-decoration:none;color:inherit}
.direct .k{font:400 13px/20px var(--font);color:var(--ink-55)} .direct .v{font:500 15px/20px var(--font);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)} .direct:hover .v{text-decoration-color:var(--ink)}
.sent .tbtn{font-size:14px;text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
@media (max-width:820px){.rating{gap:22px} .page-body{padding-top:28px}}
'''

CONTACT = '''<main class="wrap">
  <header class="page-hero">
    <p class="crumb">도움말</p>
    <h1>문의하기</h1>
    <p class="sub">서비스 의견·협업 제안·데이터 오류 제보를 보내 주시기 바랍니다. 영업일 기준 2~3일 내에 답변드립니다.</p>
  </header>
  <div class="page-body">
    <form id="form" novalidate>
      <div class="fld"><span class="lbl">문의 유형</span>
        <div class="seg" id="catSeg"><button type="button" class="on" data-cat="일반 문의">일반 문의</button><button type="button" data-cat="데이터 오류 제보">데이터 오류 제보</button><button type="button" data-cat="협업·제휴">협업·제휴</button></div>
      </div>
      <div class="fld"><label for="f-name">이름 <span class="opt">(선택)</span></label><input id="f-name" type="text" placeholder="성함을 입력하십시오" autocomplete="name"></div>
      <div class="fld"><label for="f-email">이메일</label><input id="f-email" type="email" placeholder="답변받으실 이메일 주소" autocomplete="email" required><div class="msg"></div></div>
      <div class="fld"><label for="f-msg">문의 내용</label><textarea id="f-msg" placeholder="문의하실 내용을 자세히 적어 주십시오. 데이터 오류 제보의 경우 해당 페이지 주소를 함께 남겨주시면 빠르게 확인할 수 있습니다." required></textarea><div class="msg"></div></div>
      <input type="text" id="hp" name="hp" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0">
      <div class="alert" id="formErr" role="alert"></div>
      <div class="submit"><button type="submit" class="btn btn-ink">문의 보내기</button><p class="form-note">보내주신 정보는 문의 응대 목적으로만 사용되며, 답변 후 안전하게 폐기됩니다.</p></div>
    </form>
    <div class="sent" id="sent" hidden>
      <h2>문의가 접수되었습니다</h2>
      <p>소중한 의견 감사합니다. 입력해 주신 이메일로 영업일 기준 2~3일 내에 답변드리겠습니다.</p>
    </div>
    <a class="direct" href="mailto:hello@kosai.kr"><span class="k">직접 메일 보내기</span><span class="v">hello@kosai.kr</span></a>
  </div>
</main>'''

FEEDBACK = '''<main class="wrap">
  <header class="page-hero">
    <p class="crumb">도움말</p>
    <h1>피드백 보내기</h1>
    <p class="sub">KOSAI를 이용하시면서 느끼신 점을 들려주시기 바랍니다. 좋았던 점도, 아쉬웠던 점도 모두 환영합니다.</p>
  </header>
  <div class="page-body">
    <form id="form" novalidate>
      <div class="fld"><span class="lbl">전반적인 만족도</span>
        <div class="rating" id="rating" role="radiogroup" aria-label="전반적인 만족도">
          <button type="button" class="rate" data-v="1" role="radio" aria-checked="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 15.5s1.3-1.5 3.5-1.5 3.5 1.5 3.5 1.5"/><path d="M9 9.5h.01M15 9.5h.01"/></svg><span class="lab">아쉬움</span></button>
          <button type="button" class="rate" data-v="2" role="radio" aria-checked="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 14.5h7"/><path d="M9 9.5h.01M15 9.5h.01"/></svg><span class="lab">보통</span></button>
          <button type="button" class="rate" data-v="3" role="radio" aria-checked="false"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 14s1.3 1.8 3.5 1.8 3.5-1.8 3.5-1.8"/><path d="M9 9.5h.01M15 9.5h.01"/></svg><span class="lab">만족</span></button>
        </div>
      </div>
      <div class="fld"><span class="lbl">어떤 피드백인가요?</span>
        <div class="seg" id="catSeg"><button type="button" class="on" data-cat="개선 제안">개선 제안</button><button type="button" data-cat="버그 신고">버그 신고</button><button type="button" data-cat="칭찬·응원">칭찬·응원</button><button type="button" data-cat="기타">기타</button></div>
      </div>
      <div class="fld"><label for="f-msg">내용</label><textarea id="f-msg" placeholder="어떤 점이 좋았는지, 무엇이 불편했는지, 어떤 기능이 있으면 좋겠는지 자유롭게 적어 주십시오." required></textarea><div class="msg"></div></div>
      <div class="fld"><label for="f-email">이메일 <span class="opt">(선택 · 답변이 필요한 경우)</span></label><input id="f-email" type="email" placeholder="답변받으실 이메일 주소" autocomplete="email"><div class="msg"></div></div>
      <input type="text" id="hp" name="hp" tabindex="-1" autocomplete="off" aria-hidden="true" style="position:absolute;left:-9999px;width:1px;height:1px;opacity:0">
      <div class="alert" id="formErr" role="alert"></div>
      <div class="submit"><button type="submit" class="btn btn-ink" id="submitBtn" disabled>피드백 보내기</button><p class="form-note" id="note">만족도를 선택하시면 전송하실 수 있습니다. 익명으로 보내셔도 괜찮습니다.</p></div>
    </form>
    <div class="sent" id="sent" hidden>
      <h2>소중한 피드백 감사합니다</h2>
      <p>보내주신 의견은 빠짐없이 읽고, 서비스를 개선하는 데 활용하겠습니다.</p>
      <a class="tbtn" href="/Home.html">홈으로 돌아가기</a>
    </div>
  </div>
</main>'''

JS_COMMON = r'''
  function fldErr(el,msg){var f=el.closest('.fld');f.classList.add('err');f.querySelector('.msg').textContent=msg}
  function fldClear(el){var f=el.closest('.fld');f.classList.remove('err')}
  var catSeg=document.getElementById('catSeg');
  catSeg.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;[].slice.call(catSeg.children).forEach(function(c){c.classList.toggle('on',c===b)});window.kosInd(catSeg,'x')()});
  window.kosInd(catSeg,'x');
  var EMAIL=/^[^@\s]+@[^@\s]+\.[^@\s]+$/;
  function sent(){document.getElementById('form').hidden=true;document.getElementById('sent').hidden=false;window.scrollTo({top:0,behavior:'smooth'})}
  /* 보내기 — 스테이징·실사이트는 KOSsubmitForm(submit-form.js → Firebase 함수)으로 실제로 보낸다. 시안(모듈 없음)은 접수 화면만. */
  var formErr=document.getElementById('formErr'),btn=document.querySelector('#form .submit .btn');
  function send(payload){formErr.classList.remove('show');
    if(!window.KOSsubmitForm){sent();return}
    payload.hp=(document.getElementById('hp')||{}).value||'';payload.page=location.pathname.split('/').pop();
    btn.disabled=true;var was=btn.textContent;btn.textContent='보내는 중…';
    window.KOSsubmitForm(payload).then(function(){sent()}).catch(function(err){formErr.textContent='보내지 못했습니다. 잠시 후 다시 시도하여 주시기 바랍니다.'+(err&&err.message?' ('+err.message+')':'');formErr.classList.add('show')})
      .then(function(){btn.disabled=false;btn.textContent=was})}
  function cat(){var b=catSeg.querySelector('.on');return b?b.dataset.cat:''}
'''

CONTACT_JS = r'''(function(){''' + JS_COMMON + r'''
  ['f-name','f-email','f-msg'].forEach(function(id){var el=document.getElementById(id);if(el)el.addEventListener('input',function(){fldClear(el)})});
  document.getElementById('form').addEventListener('submit',function(e){e.preventDefault();
    var email=document.getElementById('f-email'),msg=document.getElementById('f-msg'),bad=null,ev=email.value.trim();
    if(!ev){fldErr(email,'이메일을 입력하여 주시기 바랍니다.');bad=bad||email}else if(!EMAIL.test(ev)){fldErr(email,'올바른 이메일 형식이 아닙니다.');bad=bad||email}else fldClear(email);
    var mv=msg.value.trim();if(!mv){fldErr(msg,'문의 내용을 입력하여 주시기 바랍니다.');bad=bad||msg}else if(mv.length<5){fldErr(msg,'내용을 조금 더 자세히 입력하여 주시기 바랍니다.');bad=bad||msg}else fldClear(msg);
    if(bad){bad.focus();return}
    send({kind:'contact',name:document.getElementById('f-name').value.trim(),email:ev,category:cat(),message:mv})});
})();'''

FEEDBACK_JS = r'''(function(){''' + JS_COMMON + r'''
  var rating=document.getElementById('rating'),submitBtn=document.getElementById('submitBtn'),note=document.getElementById('note'),rated=false;
  rating.addEventListener('click',function(e){var r=e.target.closest('.rate');if(!r)return;[].slice.call(rating.children).forEach(function(c){var on=c===r;c.classList.toggle('on',on);c.setAttribute('aria-checked',on?'true':'false')});rated=true;submitBtn.disabled=false;note.textContent='익명으로 보내셔도 괜찮습니다.'});
  ['f-msg','f-email'].forEach(function(id){var el=document.getElementById(id);if(el)el.addEventListener('input',function(){fldClear(el)})});
  document.getElementById('form').addEventListener('submit',function(e){e.preventDefault();if(!rated)return;
    var msg=document.getElementById('f-msg'),email=document.getElementById('f-email'),bad=null,mv=msg.value.trim();
    if(!mv){fldErr(msg,'내용을 입력하여 주시기 바랍니다.');bad=bad||msg}else if(mv.length<5){fldErr(msg,'내용을 조금 더 자세히 입력하여 주시기 바랍니다.');bad=bad||msg}else fldClear(msg);
    var ev=email.value.trim();if(ev&&!EMAIL.test(ev)){fldErr(email,'올바른 이메일 형식이 아닙니다.');bad=bad||email}else fldClear(email);
    if(bad){bad.focus();return}
    var rv=rating.querySelector('.rate.on');send({kind:'feedback',email:ev,rating:rv?+rv.dataset.v:null,category:cat(),message:mv})});
})();'''


def page(title, body, js):
    return (C.head(title) + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.PROSE_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + '\n' + body + '\n' + C.FOOTER + '\n<script>\n' + js + '\n' + C.JS + '\n</script>\n</body>\n</html>')


def build(outs=None):
    outs = outs or {'contact': 'preview/contact.html', 'feedback': 'preview/feedback.html'}
    for out, title, body, js in [(outs['contact'], '문의하기 — 디자인 시안 | KOSAI', CONTACT, CONTACT_JS),
                                 (outs['feedback'], '피드백 — 디자인 시안 | KOSAI', FEEDBACK, FEEDBACK_JS)]:
        html = page(title, body, js)
        C.emit(ROOT / out, html)
        print(f'✅ {ROOT / out} · {len(html):,}자')


if __name__ == '__main__':
    build()
