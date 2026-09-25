#!/usr/bin/env python3
"""설정 — staging/Settings.html. 내용은 settings-panel.js 의 renderSettings() 가 그린다(일반 · 알림 · 구독 · 계정, 구독 관리 포함).
여기서는 페이지 틀과 옷(.ks-* 를 새 디자인으로) 만. ?tab=general|notifications|subscription|account · &card=1(결제 수단 변경 알림).

    python3 scripts/build_settings_staging.py [출력 경로]

staging/tests/subscription.test.mjs · spec-table.test.mjs 는 renderSettings 를 jsdom 에서 직접 부른다 — 이 페이지와 무관하다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

# settings-panel.js 가 스스로 끼우는 #kos-settings-css 보다 뒤에 오지 않으므로 선택자를 #mount 로 무겁게 해서 이긴다.
CSS = '''
.auth.wide{max-width:560px}
#mount .ks-main{display:block} #mount .ks-nav{position:relative;display:flex;gap:22px;width:auto;padding:0;margin-top:28px;border:0;border-bottom:1px solid var(--hair);overflow-x:auto;scrollbar-width:none} #mount .ks-nav::-webkit-scrollbar{display:none}
#mount .ks-nav button{width:auto;flex:none;border:0;border-radius:0;background:none;padding:0;font:500 13px/40px var(--font);color:var(--ink-55);white-space:nowrap;transition:color .12s} #mount .ks-nav button:hover{background:none;color:var(--ink)}
#mount .ks-nav button[aria-selected="true"]{background:none;color:var(--ink);font-weight:600}
#mount .ks-panel{padding:8px 0 0;overflow:visible} #mount .ks-sec{padding:0 0 8px} #mount .ks-sec.sep{margin-top:32px;padding-top:24px;border-top:1px solid var(--line)}
#mount .ks-h{margin:26px 0 12px;font:600 12px/16px var(--font);color:var(--ink-55);letter-spacing:.06em;text-transform:none}
#mount .ks-row{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:18px 0;border-bottom:1px solid var(--hair)} #mount .ks-row .ks-lab{font:500 15px/22px var(--font);color:var(--ink)} #mount .ks-row .ks-sub{margin-top:4px;font:400 13px/20px var(--font);color:var(--ink-55);max-width:360px}
#mount .ks-seg{width:auto;border:0;border-radius:0;background:none;display:flex;gap:18px;flex:none} #mount .ks-seg button{flex:none;padding:0;font:500 13px/32px var(--font);color:var(--ink-55);background:none;border-radius:0;box-shadow:none} #mount .ks-seg button[aria-pressed="true"]{background:none;color:var(--ink);font-weight:600;box-shadow:inset 0 -2px 0 var(--ink)}
#mount .ks-sw{width:40px;height:22px;border-radius:999px;border:1px solid var(--line);background:transparent} #mount .ks-sw::after{top:3px;left:3px;width:14px;height:14px;background:var(--ink-55);box-shadow:none} #mount .ks-sw[aria-checked="true"]{background:var(--ink);border-color:var(--ink)} #mount .ks-sw[aria-checked="true"]::after{background:var(--bg);transform:translateX(18px)}
#mount .ks-kv{grid-template-columns:120px 1fr;gap:12px 16px;padding:0;font:400 15px/22px var(--font)} #mount .ks-kv dt{color:var(--ink-55)} #mount .ks-kv dd{color:var(--ink)}
#mount .ks-badge{padding:0;border-radius:0;background:none;font:600 13px/20px var(--font);color:var(--ink)} #mount .ks-badge.on{background:none;color:var(--ink)} #mount .ks-badge.warn{background:none;color:var(--up)}
#mount .ks-btns{display:flex;flex-wrap:wrap;gap:10px 12px;margin-top:18px}
#mount .ks-btn{display:inline-flex;align-items:center;height:36px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--ink);font:600 13px/1 var(--font);cursor:pointer;text-decoration:none;transition:border-color .12s}
#mount .ks-btn:hover{background:transparent;border-color:var(--ink)} #mount .ks-btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)} #mount .ks-btn.primary:hover{opacity:.9;filter:none} #mount .ks-btn.danger{color:var(--up);border-color:var(--line)} #mount .ks-btn.danger:hover{border-color:var(--up)}
#mount .ks-note{margin:12px 0 0;font:400 14px/22px var(--font);color:var(--ink-72)} #mount .ks-note a{color:var(--ink);text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
#mount .ks-msg{margin:14px 0 0;font:400 13px/20px var(--font);color:var(--ink-72)} #mount .ks-msg.ok{color:var(--ink)} #mount .ks-msg.err{color:var(--up)}
#mount .ks-hist{margin-top:4px} #mount .ks-hist table{font:400 14px/20px var(--font)} #mount .ks-hist th{padding:0 12px 10px 0;font:500 12px/16px var(--font);color:var(--ink-55);border-bottom:1px solid var(--line)} #mount .ks-hist td{padding:11px 12px 11px 0;border-top:1px solid var(--hair)}
/* 확인 창 — body 에 붙는다 */
body .ks-dlg{background:rgba(20,20,20,.32);-webkit-backdrop-filter:none;backdrop-filter:none} body .ks-dlg-card{max-width:480px;background:var(--surface);border:1px solid var(--hair);border-radius:16px;box-shadow:0 24px 60px rgba(20,20,20,.18);padding:28px}
body .ks-dlg-t{margin:0;font:700 20px/28px var(--font);letter-spacing:-.02em;color:var(--ink)} body .ks-dlg-b{margin:12px 0 0;font:400 15px/24px var(--font);color:var(--ink-72)}
body .ks-dlg-q{margin:22px 0 4px;font:500 13px/20px var(--font);color:var(--ink-72)} body .ks-dlg-r{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--hair);font:400 14px/20px var(--font);color:var(--ink)}
body .ks-dlg-d{display:block;width:100%;box-sizing:border-box;margin-top:10px;border:0;border-bottom:1px solid var(--line);border-radius:0;background:transparent;font:400 14px/22px var(--font);color:var(--ink);padding:8px 0;outline:0;resize:vertical} body .ks-dlg-d:focus{border-bottom-color:var(--ink)}
body .ks-dlg .ks-btns{display:flex;justify-content:flex-end;gap:12px;margin-top:24px} body .ks-dlg .ks-btn{display:inline-flex;align-items:center;height:38px;padding:0 18px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--ink);font:600 13px/1 var(--font);cursor:pointer} body .ks-dlg .ks-btn.primary{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.need{margin-top:32px;padding-top:24px;border-top:1px solid var(--line)} .need p{margin:0 0 20px;font:400 15px/24px var(--font);color:var(--ink-72)}
@media (max-width:820px){#mount .ks-kv{grid-template-columns:96px 1fr} #mount .ks-row{align-items:flex-start;flex-direction:column;gap:10px}}'''

BODY = '''<main class="wrap"><div class="auth wide">
  <p class="crumb">계정</p><h1>설정</h1>
  <div id="mount" aria-live="polite"><p class="ks-note">불러오는 중…</p></div>
</div></main>'''

JS = '''import { auth, isConfigured } from "./firebase-config.js";
import { renderSettings } from "./settings-panel.js";
import { onAuthStateChanged } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";
/* 페이지로 온 설정. 로그인 확인이 끝난 뒤 그려야 '로그인이 필요합니다' 가 잠깐 비치지 않는다. 로그인·로그아웃이 바뀌면 다시 그린다. */
const q = new URLSearchParams(location.search);
if (q.get("card") === "1") window.__KOS_CARD_NOTICE = true;
const TABS = ["general", "notifications", "subscription", "account"];
const tab = TABS.includes(q.get("tab")) ? q.get("tab") : "general";
const mount = document.getElementById("mount");
function paint() {
  renderSettings(mount, { tab });
  const nav = mount.querySelector(".ks-nav");
  if (nav && window.kosInd) { const mv = window.kosInd(nav, "x", '[aria-selected="true"]'); mv(true); nav.addEventListener("click", () => setTimeout(() => mv(), 0)); }
}
/* 테마 단추는 settings-panel 이 옛 아이콘을 그려 넣는다 — 헤더의 아이콘은 우리 것으로 다시 그린다 */
new MutationObserver(() => { if (window.__kosPaintTheme) window.__kosPaintTheme(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
if (isConfigured && auth) onAuthStateChanged(auth, paint); else paint();'''


def build(out_path=None):
    C.set_mode('staging')
    html = (C.head('설정 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.AUTH_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('') + '\n' + BODY + '\n' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n<script type="module">\n' + JS + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'staging/Settings.html'
    C.emit(out, html)
    print(f'✅ {out} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
