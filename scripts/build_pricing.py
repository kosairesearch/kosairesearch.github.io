#!/usr/bin/env python3
"""멤버십(요금제) — staging/pricing.html. 새 디자인(comp_common · staging 모드).

    python3 scripts/build_pricing.py [출력 경로]

요금제는 멤버십 하나다(2026-11-24 사장 "요금제는 1개 14900원. 열람은 무제한") — 무료 · 멤버십 두 단을 상자 없이
가는 선으로 가른다. 결제 진입 논리는 인라인 모듈(scripts/pricing_module.js) — .plan [data-plan] 단추 · .plan-badge.js 가
그 모듈의 계약이다. 요금제 변경이 없어져 확인 창(#dlg)도 없앴다.

가격과 환불 안내는 staging/payment-config.js 의 PLANS · REFUND_NOTICE('@json' 표시 사이)를 읽어 그린다 —
결제 화면 · 설정의 환불 확인 창과 같은 글이다. 환불 답은 두 말을 미리 그려 두고(data-lang) 번역 엔진이 지금 말 쪽만
보이게 한다. staging/tests/membership.test.mjs 가 요금제 수 · 표 · 자주 묻는 질문을 본다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

def payment_config():
    """staging/payment-config.js 의 '@json' 표시 사이(PLANS · REFUND_NOTICE)를 읽는다 — 결제 화면 · 설정과 같은 값.
    리포트 화면 생성기(build_stock_staging.py)도 이것으로 잠금 카드의 가격을 적는다."""
    src = (ROOT / 'staging/payment-config.js').read_text(encoding='utf-8')
    blocks = dict(re.findall(r'export const (\w+) = /\*@json\*/(.*?)/\*@/json\*/', src, re.S))
    assert {'PLANS', 'REFUND_NOTICE'} <= set(blocks), sorted(blocks)
    return {k: json.loads(v) for k, v in blocks.items()}


def member():
    return payment_config()['PLANS']['member']


def plans():
    m = member()
    return [
        dict(id='free', name='무료', price='0', unit='원', sub='가입 없이', feats=['현재가·시가총액·PER·PBR 등 핵심 지표', '리포트 개요와 핵심 요약', '사업 구조', '최근 4개 연도·5개 분기 실적 추이', '조건 검색과 업종 분석', '관심종목(무료 회원가입 후)'],
             cta='<a class="btn btn-soft" href="/Reports.html">전체 리포트 보기</a>'),
        # 종목 수는 적지 않는다(예전 '국내 상장 2,500여 개 종목' — 새 상장 종목은 리포트가 늦고, '-여'는 넘는다는 뜻이다 · 명세 4절).
        # '국내 상장 종목 리포트' 는 쓰지 않는다 — 실사이트 리포트 목록의 눈썹 글과 같아 영어 사전에 넣으면 실사이트 페이지가 바뀐다.
        dict(id='member', name=m['name'], price=f"{m['price']:,}", per='월', unit='원', sub='언제든지 해지 가능',
             feats=['무료 플랜의 모든 항목', '잠금 없이 리포트 전체 열람', '열람 종목 수 제한 없음'],
             cta=f'<button type="button" class="btn btn-ink" data-plan="{m["id"]}">구독하기</button>'),
    ]

# (항목, 설명, 무료, 멤버십) — True 포함 · False 미포함 · 문자열은 그대로. 하루 한도 줄은 없앴다(2026-11-24 — 한도 없음).
CMP = [
    ('핵심 지표', '현재가·시가총액·PER·PBR·EPS·배당수익률', True, True),
    ('리포트 개요', '한 줄 요약과 핵심 포인트', True, True),
    ('사업 구조', '부문별 매출 비중·주요 제품·고객', True, True),
    ('실적 추이', '최근 4개 연도·5개 분기 실적 표와 차트', True, True),
    ('실적 분석', '증감 원인·마진 추이·일회성 요인', False, True),
    ('산업 분석', '전방시장 수급·사이클 위치·경쟁사 비교', False, True),
    ('전망', '회사 가이던스·수주·증설·신제품 일정', False, True),
    ('밸류에이션 해설', '과거 밴드·업종 평균과 비교한 현재 수준', False, True),
    ('강세 요인 · 약세 요인', '긍정 논거 3가지 · 부정 논거 3가지', False, True),
    ('리스크 요인', '유형별 위험 요인 3가지', False, True),
    ('다음 체크포인트', '앞으로 확인할 일정과 지표', False, True),
    ('종합 의견', '앞선 분석의 종합', False, True),
    ('참고 출처', '작성에 참고한 자료 링크', True, True),
]


def notice_html(n):
    """환불 안내 한 말(ko | en) — 첫 문단 · 번호 두 항목 · 점 항목. 결제 화면(checkout.js) · 설정 확인 창(settings-panel.js)과 같은 틀."""
    import html as _h
    e = _h.escape
    return (f'<p>{e(n["lead"])}</p><ol>' + ''.join(f'<li>{e(x)}</li>' for x in n['steps']) + '</ol>'
            '<ul>' + ''.join(f'<li>{e(x)}</li>' for x in n['notes']) + '</ul>')


def refund_answer():
    """자주 묻는 질문의 환불 답 — 명세의 환불 안내 그대로(두 말을 미리 그려 둔다) + 신청하는 곳."""
    rn = payment_config()['REFUND_NOTICE']
    return (f'<div class="refund-notice" data-lang="ko">{notice_html(rn["ko"])}</div>'
            f'<div class="refund-notice" data-lang="en" lang="en">{notice_html(rn["en"])}</div>'
            '<p>환불 신청은 설정의 구독 항목에서 직접 하실 수 있습니다. 개별 확인이 필요한 경우 <a href="/Contact.html">문의하기</a>로 접수하여 주시기 바랍니다.</p>')


def faq():
    return [
    ('열람할 수 있는 리포트 수에 제한이 있나요?', '<p>멤버십은 열람하실 수 있는 리포트의 종목 수에 제한이 없습니다. 같은 종목을 새로고침하거나 다른 기기에서 다시 열람하시는 경우에도 제한 없이 이용하실 수 있습니다.</p><p>다만 리포트의 자동 수집을 막기 위해, 짧은 시간에 비정상적으로 많은 리포트를 열람한 계정은 열람이 일시적으로 제한될 수 있습니다. 이 제한은 일정 시간이 지나면 자동으로 해제됩니다.</p>'),
    ('구독은 언제든지 해지할 수 있나요?', '<p>설정의 구독 항목에서 직접 해지하실 수 있으며, 별도의 전화나 문의 접수 절차는 필요하지 않습니다. 해지 이후에도 이미 결제된 이용 기간이 종료될 때까지는 그대로 이용하실 수 있습니다.</p>'),
    ('결제가 승인되지 않으면 어떻게 되나요?', '<p>등록하신 카드로 정기결제가 승인되지 않으면 유료 구간의 이용이 일시 중지되며, 최초 승인 거절일부터 1일·3일·5일·7일이 되는 날에 자동으로 다시 시도합니다. 결제가 완료되면 그 시점부터 새로운 한 달의 이용 기간이 시작되므로, 이용하지 못하신 기간은 요금에 포함되지 않습니다.</p><p>기다리지 않고 바로 재개하시려면 설정의 구독 항목에서 결제 수단을 다시 등록해 주시기 바랍니다. 재시도를 원하지 않으시는 경우에는 같은 곳에서 해지하실 수 있으며, 해지하시면 재시도가 즉시 중지됩니다. 4회의 재시도가 모두 승인되지 않으면 구독은 자동으로 종료되고, 별도로 청구되는 금액은 없습니다.</p>'),
    ('환불 기준은 어떻게 되나요?', refund_answer()),
    ('리포트는 어떤 주기로 갱신되나요?', '<p>주가·시가총액·PER 등 시장 데이터는 매 거래일 저녁에 갱신됩니다.</p><p>리포트 본문은 해당 기업이 DART에 사업보고서와 반기보고서, 분기보고서를 제출하면 최신 실적을 반영해 자동으로 다시 작성됩니다. 새로 상장된 종목은 상장 직후 리포트가 작성됩니다.</p>'),
    ('이용 가능한 결제 수단은 무엇인가요?', '<p>국내에서 발급된 신용카드와 체크카드로 결제하실 수 있습니다. 매달 결제일에 자동으로 결제되며, 결제 내역과 영수증은 설정의 구독 항목에서 확인하실 수 있습니다.</p>'),
    ('구독하면 종목 추천을 받을 수 있나요?', '<p>KOSAI는 자체 투자의견과 목표주가를 제시하지 않습니다. 멤버십에서 추가로 제공되는 것은 공시와 실적을 근거로 한 분석·전망·리스크 정리이며, 투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있습니다.</p><p>리포트 작성 기준은 <a href="/About.html">회사 소개</a>에서 확인하실 수 있습니다.</p>'),
    ]

# 첫 줄은 유사투자자문업자 법정 표시(자본시장법 제101조의3 · comp_common.LEGAL_NOTE_KO — 요금 안내 화면에 반드시 둔다).
# 요금 인상은 회원 동의를 받는다(약관 제9조⑤ · 전자상거래법 제13조제6항 · 2025-02-14 시행).
NOTES = [C.LEGAL_NOTE_KO,
         'KOSAI의 모든 분석·리포트는 투자 참고용 정보이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있습니다.',
         '표시 금액은 부가가치세가 포함된 가격입니다. 요금을 올리는 경우 인상된 요금을 처음 결제하기 전 30일 이내에 구독 회원께 개별 안내하고 동의를 받으며, 동의하지 않으시면 인상된 요금을 결제하지 않습니다.',
         'DART에 재무 정보가 공시되지 않는 일부 종목은 실적 표와 일부 분석 항목을 제공하지 못합니다. 해당 종목의 리포트는 구독 여부와 관계없이 전체를 무료로 공개합니다.',
         '유료 콘텐츠의 복제·재배포·판매는 허용되지 않습니다.']

CSS = '''
/* 무료 · 멤버십 두 단 — 상자 없이 가는 선으로 가른다 */
.plans{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 40px;margin-top:44px;border-top:1px solid var(--line)}
.plan{position:relative;padding:28px 0 36px;border-bottom:1px solid var(--hair)} .plan+.plan{border-left:1px solid var(--hair);padding-left:32px;margin-left:-8px}
.plan-name{margin:0;font:600 12px/16px var(--font);letter-spacing:.06em;color:var(--ink-62)}
.plan-price{margin:12px 0 0;font:700 36px/44px var(--font);letter-spacing:-.02em} .plan-price span{font:500 14px/20px var(--font);letter-spacing:0;color:var(--ink-62);margin-left:6px} .plan-price .pre{margin:0 2px 0 0}   /* '월 14,900원' — 작은 '월'을 앞에(가이드 4-5, 2026-10-03) */
.plan-sub{margin:4px 0 0;font:400 13px/20px var(--font);color:var(--ink-62);min-height:20px}
.plan-feats{list-style:none;margin:22px 0 0;padding:0} .plan-feats li{padding:9px 0;border-top:1px solid var(--hair);font:400 14px/20px var(--font)}
.plan .btn{margin-top:24px;width:100%;justify-content:center;height:44px;font-size:14px}
/* 두 칸의 단추를 한 줄에 — 무료 칸의 항목이 더 많아 단추가 아래로 처졌다(2026-09-26 사장). 칸을 세로 flex 로 두고 단추를 바닥에 붙인다. */
.plan{display:flex;flex-direction:column} .plan .btn{margin-top:auto} .plan-feats{margin-bottom:24px} .plan .btn.is-current{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)}
.plan-badge.js{position:absolute;top:28px;right:0;font:600 12px/16px var(--font);color:var(--ink)}
/* 제공 범위 표 */
.cmp{padding-top:88px} .cmp-t th:first-child,.cmp-t td:first-child{width:auto;white-space:normal} .cmp-t .d{display:block;margin-top:2px;font:400 12px/16px var(--font);color:var(--ink-62)}
.cmp-t th,.cmp-t td{text-align:center;vertical-align:top} .cmp-t th:first-child,.cmp-t td:first-child{text-align:left}
.mk{font:500 14px/20px var(--font)} .mk-y{color:var(--ink)} .mk-n{color:var(--ink-62)}
/* 자주 묻는 질문 */
.faq{padding-top:88px;max-width:760px} .qa{border-top:1px solid var(--hair)} .qa:last-of-type{border-bottom:1px solid var(--hair)}
.qa summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:18px 0;font:600 16px/24px var(--font)} .qa summary::-webkit-details-marker{display:none}
.qa summary::after{content:"+";flex:none;font:400 20px/24px var(--font);color:var(--ink-30)} .qa[open] summary::after{content:"–"}
.qa .a{padding:0 0 22px;max-width:680px}
/* 유의사항 */
.notes{margin-top:88px;padding-top:24px;border-top:1px solid var(--line);max-width:720px} .notes h3{margin:0;font:600 14px/20px var(--font)}
.notes ul{margin:12px 0 0;padding-left:18px;font:400 14px/22px var(--font);color:var(--ink-72)} .notes li{margin:0 0 6px}
@media (max-width:820px){.plans{grid-template-columns:1fr;gap:0;margin-top:28px} .plan+.plan{border-left:0;padding-left:0;margin-left:0} .plan-badge.js{top:28px}
  .cmp,.faq{padding-top:56px} .notes{margin-top:56px}}'''


def plan_html(p):
    feats = ''.join(f'<li>{f}</li>' for f in p['feats'])
    pre = f'<span class="pre">{p["per"]} </span>' if p.get('per') else ''   # '월 14,900원' — 작은 '월'이 숫자 앞(가이드 4-5)
    return (f'<section class="plan" data-id="{p["id"]}"><p class="plan-name">{p["name"]}</p>'
            f'<p class="plan-price">{pre}<b>{p["price"]}</b><span>{p["unit"]}</span></p><p class="plan-sub">{p["sub"]}</p>'
            f'<ul class="plan-feats">{feats}</ul>{p["cta"]}</section>')


def mark(v):
    if v is True:
        return '<span class="mk mk-y" aria-label="포함">✓</span>'
    if v is False:
        return '<span class="mk mk-n" aria-label="미포함">—</span>'
    return f'<span class="mk">{v}</span>'


def build(out_path=None):
    C.set_mode('staging')
    def row(n, d, a, b):
        return f'<tr><td>{n}<span class="d">{d}</span></td><td>{mark(a)}</td><td>{mark(b)}</td></tr>'
    rows = ''.join(row(*r) for r in CMP)
    qa = ''.join(f'<details class="qa"><summary>{q}</summary><div class="a prose">{a}</div></details>' for q, a in faq())
    notes = ''.join(f'<li>{n}</li>' for n in NOTES)
    module = (ROOT / 'scripts/pricing_module.js').read_text(encoding='utf-8')
    body = f'''<main class="wrap">
  <header class="page-hero">
    <p class="crumb">멤버십</p>
    <h1>데이터는 무료로, 해석은 구독으로</h1>
    <p class="sub">주가와 실적 등 사실 데이터는 모든 이용자에게 무료로 공개합니다. 이를 바탕으로 작성한 분석과 전망, 리스크 진단은 멤버십에서 제공합니다.</p>
  </header>
  <div class="plans" id="plans">{''.join(plan_html(p) for p in plans())}</div>
  <section class="cmp" id="cmp"><div class="sec-h"><h2>리포트 구성과 제공 범위</h2></div>
    <div class="tbl-wrap"><table class="tbl cmp-t"><thead><tr><th>리포트 섹션</th><th>무료</th><th>{member()["name"]}</th></tr></thead><tbody>{rows}</tbody></table></div></section>
  <section class="faq" id="faq"><div class="sec-h"><h2>자주 묻는 질문</h2></div>{qa}</section>
  <section class="notes"><h3>유의사항</h3><ul>{notes}</ul></section>
</main>'''
    html = (C.head('멤버십 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.PROSE_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('멤버십') + '\n' + body + '\n' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n<script type="module">\n' + module + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'staging/pricing.html'
    C.emit(out, html)
    print(f'✅ {out} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
