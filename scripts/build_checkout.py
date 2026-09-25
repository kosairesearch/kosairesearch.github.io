#!/usr/bin/env python3
"""결제 화면 — staging/checkout.html. 화면은 checkout.js 가 그린다(상태 11가지 · 폼 · 요약). 여기서는 틀과 옷만.

    python3 scripts/build_checkout.py [출력 경로]

checkout.js 의 계약: h1#coH1 · p#coH2 · div#coApp, 그 안에 .co-state / .co(.co-card + aside.sum) / .co-step / .pm / .agree / #payBtn / #coMsg / .co-note / .co-fine.
staging/tests/checkout.test.mjs 는 jsdom 에 같은 뼈대를 직접 만들어 checkout.js 만 검사한다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

CSS = '''
.glass{}  /* checkout.js 가 붙이는 옛 이름 — 상자는 없다 */
.co{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:64px;margin-top:40px;align-items:start}
.co-step{display:flex;align-items:center;gap:12px;margin:0 0 14px} .co-step .n{width:24px;height:24px;border-radius:50%;background:var(--ink);color:var(--bg);font:600 12px/24px var(--font);text-align:center;flex:none} .co-step h3{margin:0;font:600 16px/24px var(--font)}
.co-card>.co-step+*+.co-step,.co-card>.co-step~.co-step{margin-top:40px;padding-top:28px;border-top:1px solid var(--hair)}
input[type=radio],input[type=checkbox]{accent-color:var(--ink);width:16px;height:16px;margin:2px 0 0;flex:none}
.pm label{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-top:1px solid var(--hair);cursor:pointer} .pm .card{display:block} .pm .t{display:block;font:500 15px/22px var(--font)} .pm .d{display:block;margin-top:2px;font:400 13px/20px var(--font);color:var(--ink-55)}
.agree label{display:flex;align-items:flex-start;gap:12px;padding:10px 0;border-top:1px solid var(--hair);font:400 14px/22px var(--font);cursor:pointer} .agree label.all{font-weight:600;border-top:0;border-bottom:1px solid var(--line)} .agree label a{text-decoration:underline;text-underline-offset:3px;text-decoration-color:var(--line)}
#payBtn{margin-top:28px;width:100%;justify-content:center;height:46px;font-size:15px}
.co-msg{display:none;margin:12px 0 0;font:400 13px/20px var(--font);color:var(--ink-72)} .co-msg.err{display:block;color:var(--up)} .co-msg:not(:empty){display:block}
.co-note{margin:14px 0 0;font:400 13px/20px var(--font);color:var(--ink-72)} .co-fine{margin:18px 0 0;font:400 12px/18px var(--font);color:var(--ink-55)} .co-fine a{text-decoration:underline;text-underline-offset:3px}
/* 요약 — 오른쪽에 붙박이 */
.sum{position:sticky;top:calc(84px + var(--kos-bar-h,0px));border-top:1px solid var(--line);padding-top:16px}
.plan-badge{display:inline-block;font:600 12px/16px var(--font);letter-spacing:.06em;color:var(--ink-55)}
.sum .amt{margin:8px 0 0;font:700 32px/40px var(--font);letter-spacing:-.02em} .sum .amt small{font:500 14px/20px var(--font);letter-spacing:0;color:var(--ink-55);margin-left:4px}
.sum .cyc{margin:2px 0 0;font:400 13px/20px var(--font);color:var(--ink-55)}
.sum ul{list-style:none;margin:20px 0 0;padding:0} .sum li{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-top:1px solid var(--hair);font:400 14px/20px var(--font)} .sum li span{color:var(--ink-55)} .sum li b{font-weight:500;text-align:right}
.sum .total{display:flex;justify-content:space-between;margin-top:6px;padding-top:14px;border-top:1px solid var(--line);font:600 15px/22px var(--font)}
/* 상태 화면(로그인 필요 · 이미 이용 중 · 실패 …) */
.co-state{max-width:560px;padding:40px 0 16px} .co-state h2{margin:0;font:700 24px/32px var(--font);letter-spacing:-.02em} .co-state p{margin:12px 0 24px;font:400 15px/24px var(--font);color:var(--ink-72)}
.co-state .spin{display:inline-block;vertical-align:-3px;width:16px;height:16px;margin:0 8px 0 0}
@media (max-width:820px){.co{grid-template-columns:1fr;gap:36px;margin-top:24px} .sum{position:static;order:-1;border-top:0;padding-top:0;border-bottom:1px solid var(--line);padding-bottom:20px}}'''

BODY = '''<main class="wrap">
  <header class="page-hero">
    <p class="crumb">멤버십</p>
    <h1 id="coH1">구독 시작하기</h1>
    <p class="sub" id="coH2">결제 수단을 등록하시면 바로 이용하실 수 있습니다. 언제든지 해지하실 수 있습니다.</p>
  </header>
  <div id="coApp" data-i18n-skip><div class="co-state"><p><span class="spin"></span>불러오는 중…</p></div></div>
</main>'''


def build(out_path=None):
    C.set_mode('staging')
    html = (C.head('구독 시작하기 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.PROSE_CSS + '\n' + C.AUTH_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('멤버십') + '\n' + BODY + '\n' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'staging/checkout.html'
    C.emit(out, html)
    print(f'✅ {out} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
