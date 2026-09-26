#!/usr/bin/env python3
"""멤버십(요금제) — staging/pricing.html. 새 디자인(comp_common · staging 모드).

    python3 scripts/build_pricing.py [출력 경로]

플랜 셋은 상자 없이 세 단(가는 선으로 가른다). 결제 진입 논리는 옛 페이지의 인라인 모듈(scripts/pricing_module.js)을
그대로 쓴다 — .plan [data-plan] 단추 · .plan-msg · .plan-badge.js · #dlg(#dlgT #dlgB #dlgYes #dlgNo) 가 그 모듈의 계약이다.
staging/tests/layout.test.mjs 가 .dlg 의 z-index(띠 60 보다 위)를 잰다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import comp_common as C  # noqa: E402

PLANS = [
    dict(id='free', name='무료', price='0', unit='원', sub='가입 없이', feats=['현재가·시가총액·PER·PBR 등 핵심 지표', '리포트 개요와 핵심 요약', '사업 구조', '최근 4개 연도·5개 분기 실적 추이', '조건 검색 · 업종 분석 · 관심종목'],
         cta='<a class="btn btn-soft" href="/Reports.html">리포트 둘러보기</a>'),
    dict(id='basic', name='BASIC', price='9,900', unit='원 / 월', sub='언제든지 해지 가능', feats=['무료 플랜의 모든 항목', '잠금 없이 리포트 전문 열람', '국내 상장 2,500여 개 종목', '하루 5개 리포트 열람'],
         cta='<button type="button" class="btn btn-ink" data-plan="basic" data-i18n-skip>업그레이드</button>'),
    dict(id='pro', name='PRO', price='14,900', unit='원 / 월', sub='언제든지 해지 가능', feats=['무료 플랜의 모든 항목', '잠금 없이 리포트 전문 열람', '국내 상장 2,500여 개 종목', '하루 15개 리포트 열람'],
         cta='<button type="button" class="btn btn-ink" data-plan="pro" data-i18n-skip>업그레이드</button>'),
]

# (항목, 설명, 무료, BASIC, PRO) — True 포함 · False 미포함 · 문자열은 그대로
CMP = [
    ('핵심 지표', '현재가·시가총액·PER·PBR·EPS·배당수익률', True, True, True),
    ('리포트 개요', '한 줄 요약과 핵심 포인트', True, True, True),
    ('사업 구조', '부문별 매출 비중·주요 제품·고객', True, True, True),
    ('실적 추이', '최근 4개 연도·5개 분기 실적 표와 차트', True, True, True),
    ('실적 분석', '증감 원인·마진 추이·일회성 요인', False, True, True),
    ('산업 분석', '전방시장 수급·사이클 위치·경쟁사 비교', False, True, True),
    ('전망', '회사 가이던스·수주·증설·신제품 일정', False, True, True),
    ('밸류에이션 해설', '과거 밴드·업종 평균과 비교한 현재 수준', False, True, True),
    ('강세 요인 · 약세 요인', '긍정 논거 3가지 · 부정 논거 3가지', False, True, True),
    ('리스크 요인', '유형별 위험 요인 3가지', False, True, True),
    ('다음 체크포인트', '앞으로 확인할 일정과 지표', False, True, True),
    ('종합 의견', '앞선 분석의 종합', False, True, True),
    ('참고 출처', '작성에 참고한 자료 링크', True, True, True),
    ('하루 열람 한도', '같은 종목을 다시 열 때는 차감되지 않습니다', '—', '5개', '15개'),
]

FAQ = [
    ('BASIC과 PRO의 차이는 무엇인가요?', '<p>두 플랜의 제공 내용은 동일합니다. 국내 상장 2,500여 개 종목의 리포트를 전문 그대로 열람하실 수 있습니다.</p><p>차이는 하루에 열람할 수 있는 종목 수입니다. BASIC은 5개, PRO는 15개입니다. 보유 종목을 중심으로 확인하신다면 BASIC이, 여러 종목을 비교하며 검토하신다면 PRO가 적합합니다.</p><p>플랜은 언제든지 변경하실 수 있습니다.</p>'),
    ('구독은 언제든지 해지할 수 있나요?', '<p>설정의 구독 항목에서 직접 해지하실 수 있으며, 별도의 전화나 문의 접수 절차는 필요하지 않습니다. 해지 이후에도 이미 결제된 이용 기간이 종료될 때까지는 그대로 이용하실 수 있습니다.</p>'),
    ('결제가 승인되지 않으면 어떻게 되나요?', '<p>등록하신 카드로 정기결제가 승인되지 않으면 유료 구간의 이용이 일시 중지되며, 최초 승인 거절일부터 1일·3일·5일·7일이 되는 날에 자동으로 다시 시도합니다. 결제가 완료되면 그 시점부터 새로운 한 달의 이용 기간이 시작되므로, 이용하지 못하신 기간은 요금에 포함되지 않습니다.</p><p>기다리지 않고 바로 재개하시려면 설정의 구독 항목에서 결제 수단을 다시 등록해 주시기 바랍니다. 재시도를 원하지 않으시는 경우에는 같은 곳에서 해지하실 수 있으며, 해지하시면 재시도가 즉시 중지됩니다. 4회의 재시도가 모두 승인되지 않으면 구독은 자동으로 종료되고, 별도로 청구되는 금액은 없습니다.</p>'),
    ('플랜을 중간에 바꾸면 어떻게 되나요?', '<p>BASIC에서 PRO로 변경하시면 신청 즉시 PRO가 적용됩니다. 이미 결제하신 BASIC 이용 기간 중 남은 몫은 PRO 요금에서 차감되므로, 차액만 결제하시면 됩니다. 매달 결제되는 날짜는 기존 주기 그대로 유지됩니다.</p><p>변경 당일 이미 열람하신 리포트는 그대로 유지되며, 하루 열람 한도만 15개로 늘어납니다.</p><p>PRO에서 BASIC으로 변경하시는 경우에는 다음 결제일부터 적용됩니다. 그때까지는 PRO를 그대로 이용하실 수 있습니다.</p>'),
    ('환불 기준은 어떻게 되나요?', '<p>결제 이후 리포트 열람 여부에 따라 적용 기준이 달라집니다.</p><h4>리포트를 열람하지 않으신 경우</h4><ul><li>결제 후 7일 이내 — 전액 환불</li><li>결제 후 7일 경과 — 잔여 이용 기간에 해당하는 금액에서 서비스 수수료 10%를 제외하고 환불</li></ul><h4>리포트를 열람하신 경우</h4><p>이용하신 일수를 차감한 뒤, 서비스 수수료 10%를 제외한 금액이 환불됩니다.</p><h4>신청하신 날은 어떻게 계산되나요?</h4><p>열람 한도는 하루 단위로 드리므로 차감도 하루 단위로 합니다. 신청하신 날 리포트를 한 건이라도 열람하셨다면 그날은 이용하신 날로 보아 차감하고, 그날 자정까지 남은 열람 한도를 그대로 사용하실 수 있습니다. 한 건도 열람하지 않으셨다면 그날은 차감하지 않으며, 이용 권한은 신청 즉시 종료됩니다.</p><p>환불 신청은 설정의 구독 항목에서 직접 하실 수 있습니다. 개별 확인이 필요한 경우 <a href="/Contact.html">문의하기</a>로 접수하여 주시기 바랍니다.</p>'),
    ('하루 열람 한도는 어떻게 산정되나요?', '<p>하루 동안 열람하신 종목의 수를 기준으로 산정합니다. 동일한 종목을 새로고침하거나 다른 기기에서 다시 열람하시는 경우에는 추가로 차감되지 않습니다.</p><p>한도는 매일 자정(한국 시간)에 초기화됩니다. 무료로 공개되는 영역은 한도와 무관하게 언제든지 이용하실 수 있습니다.</p>'),
    ('리포트는 어떤 주기로 갱신되나요?', '<p>주가·시가총액·PER 등 시장 데이터는 매 거래일 저녁에 갱신됩니다.</p><p>리포트 본문은 해당 기업이 DART에 사업보고서·반기보고서·분기보고서를 제출하면 최신 실적을 반영해 자동으로 재작성됩니다. 신규 상장 종목은 상장 직후 리포트가 생성됩니다.</p>'),
    ('이용 가능한 결제 수단은 무엇인가요?', '<p>국내에서 발급된 신용카드와 체크카드로 결제하실 수 있습니다. 매달 결제일에 자동으로 결제되며, 결제 내역과 영수증은 설정의 구독 항목에서 확인하실 수 있습니다.</p>'),
    ('구독하면 종목 추천을 받을 수 있나요?', '<p>KOSAI는 매수·매도 의견이나 목표주가를 제시하지 않습니다. 구독 플랜에서 추가로 제공되는 것은 공시와 실적을 근거로 한 분석·전망·리스크 정리이며, 투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있습니다.</p><p>리포트 작성 기준은 <a href="/About.html">About</a>에서 확인하실 수 있습니다.</p>'),
]

NOTES = ['KOSAI의 모든 분석·리포트는 투자 참고용 정보이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 결과에 대한 책임은 이용자 본인에게 있습니다.',
         '표시 금액은 부가가치세가 포함된 가격입니다. 요금 변경 시 기존 구독자에게는 사전에 안내하며, 사전 고지 없이 인상하지 않습니다.',
         'DART에 재무 정보가 공시되지 않는 일부 종목은 실적 표와 일부 분석 항목을 제공하지 못합니다. 해당 종목의 리포트는 구독 여부와 관계없이 전문을 무료로 공개합니다.',
         '유료 콘텐츠의 복제·재배포·판매는 허용되지 않습니다.']

CSS = '''
/* 플랜 세 단 — 상자 없이 가는 선으로 가른다 */
.plans{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 40px;margin-top:44px;border-top:1px solid var(--line)}
.plan{position:relative;padding:28px 0 36px;border-bottom:1px solid var(--hair)} .plan+.plan{border-left:1px solid var(--hair);padding-left:32px;margin-left:-8px}
.plan-name{margin:0;font:600 12px/16px var(--font);letter-spacing:.06em;color:var(--ink-55)}
.plan-price{margin:12px 0 0;font:700 36px/44px var(--font);letter-spacing:-.02em} .plan-price span{font:500 14px/20px var(--font);letter-spacing:0;color:var(--ink-55);margin-left:6px}
.plan-sub{margin:4px 0 0;font:400 13px/20px var(--font);color:var(--ink-55);min-height:20px}
.plan-feats{list-style:none;margin:22px 0 0;padding:0} .plan-feats li{padding:9px 0;border-top:1px solid var(--hair);font:400 14px/20px var(--font)}
.plan .btn{margin-top:24px;width:100%;justify-content:center;height:44px;font-size:14px}
/* 세 칸의 단추를 한 줄에 — 무료 칸의 항목이 하나 더 많아 단추가 아래로 처졌다(2026-09-26 사장). 칸을 세로 flex 로 두고 단추를 바닥에 붙인다. */
.plan{display:flex;flex-direction:column} .plan .btn{margin-top:auto} .plan-feats{margin-bottom:24px} .plan .btn.is-current{background:transparent;color:var(--ink);box-shadow:inset 0 0 0 1px var(--line)}
.plan-msg{display:none;margin:12px 0 0;font:400 13px/20px var(--font);color:var(--ink-72)} .plan-msg.show{display:block} .plan-msg.err{color:var(--up)}
.plan-badge.js{position:absolute;top:28px;right:0;font:600 12px/16px var(--font);color:var(--ink)}
/* 제공 범위 표 */
.cmp{padding-top:88px} .cmp-t th:first-child,.cmp-t td:first-child{width:auto;white-space:normal} .cmp-t .d{display:block;margin-top:2px;font:400 12px/16px var(--font);color:var(--ink-55)}
.cmp-t th,.cmp-t td{text-align:center;vertical-align:top} .cmp-t th:first-child,.cmp-t td:first-child{text-align:left}
.mk{font:500 14px/20px var(--font)} .mk-y{color:var(--ink)} .mk-n{color:var(--ink-30)} .cmp-t tr.lim td{font-weight:500}
/* 자주 묻는 질문 */
.faq{padding-top:88px;max-width:760px} .qa{border-top:1px solid var(--hair)} .qa:last-of-type{border-bottom:1px solid var(--hair)}
.qa summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:baseline;gap:20px;padding:18px 0;font:600 16px/24px var(--font)} .qa summary::-webkit-details-marker{display:none}
.qa summary::after{content:"+";flex:none;font:400 20px/24px var(--font);color:var(--ink-30)} .qa[open] summary::after{content:"–"}
.qa .a{padding:0 0 22px;max-width:680px}
/* 유의사항 */
.notes{margin-top:88px;padding-top:24px;border-top:1px solid var(--line);max-width:720px} .notes h3{margin:0;font:600 14px/20px var(--font)}
.notes ul{margin:12px 0 0;padding-left:18px;font:400 14px/22px var(--font);color:var(--ink-72)} .notes li{margin:0 0 6px}
/* 확인 창 — 떠 있는 면. 띠(60) 위 */
.dlg{display:none;position:fixed;inset:0;z-index:80;background:rgba(20,20,20,.32);align-items:center;justify-content:center;padding:24px} .dlg.open{display:flex}
.dlg-box{width:100%;max-width:440px;background:var(--surface);border:1px solid var(--hair);border-radius:16px;box-shadow:0 24px 60px rgba(20,20,20,.18);padding:28px;box-sizing:border-box}
.dlg h3{margin:0;font:700 20px/28px var(--font);letter-spacing:-.02em} #dlgB p{margin:12px 0 0;font:400 15px/24px var(--font);color:var(--ink-72)}
.dlg-acts{display:flex;justify-content:flex-end;align-items:center;gap:20px;margin-top:26px}
@media (max-width:820px){.plans{grid-template-columns:1fr;gap:0;margin-top:28px} .plan+.plan{border-left:0;padding-left:0;margin-left:0} .plan-badge.js{top:28px}
  .cmp,.faq{padding-top:56px} .notes{margin-top:56px}}'''


def plan_html(p):
    feats = ''.join(f'<li>{f}</li>' for f in p['feats'])
    return (f'<section class="plan{" plan-pro" if p["id"] == "pro" else ""}" data-id="{p["id"]}"><p class="plan-name">{p["name"]}</p>'
            f'<p class="plan-price"><b>{p["price"]}</b><span>{p["unit"]}</span></p><p class="plan-sub">{p["sub"]}</p>'
            f'<ul class="plan-feats">{feats}</ul>{p["cta"]}<div class="plan-msg"></div></section>')


def mark(v):
    if v is True:
        return '<span class="mk mk-y" aria-label="포함">✓</span>'
    if v is False:
        return '<span class="mk mk-n" aria-label="미포함">—</span>'
    return f'<span class="mk">{v}</span>'


def build(out_path=None):
    C.set_mode('staging')
    def row(n, d, a, b, c):
        cls = ' class="lim"' if a == '—' else ''
        return f'<tr{cls}><td>{n}<span class="d">{d}</span></td><td>{mark(a)}</td><td>{mark(b)}</td><td>{mark(c)}</td></tr>'
    rows = ''.join(row(*r) for r in CMP)
    faq = ''.join(f'<details class="qa"><summary>{q}</summary><div class="a prose">{a}</div></details>' for q, a in FAQ)
    notes = ''.join(f'<li>{n}</li>' for n in NOTES)
    module = (ROOT / 'scripts/pricing_module.js').read_text(encoding='utf-8')
    body = f'''<main class="wrap">
  <header class="page-hero">
    <p class="crumb">멤버십</p>
    <h1>데이터는 무료로, 해석은 구독으로</h1>
    <p class="sub">주가와 실적 등 사실 데이터는 모든 이용자에게 무료로 공개합니다. 이를 바탕으로 작성한 분석과 전망, 리스크 진단은 구독 플랜에서 제공합니다.</p>
  </header>
  <div class="plans" id="plans">{''.join(plan_html(p) for p in PLANS)}</div>
  <section class="cmp" id="cmp"><div class="sec-h"><h2>리포트 구성과 제공 범위</h2></div>
    <div class="tbl-wrap"><table class="tbl cmp-t"><thead><tr><th>리포트 섹션</th><th>무료</th><th>BASIC</th><th>PRO</th></tr></thead><tbody>{rows}</tbody></table></div></section>
  <section class="faq" id="faq"><div class="sec-h"><h2>자주 묻는 질문</h2></div>{faq}</section>
  <section class="notes"><h3>유의사항</h3><ul>{notes}</ul></section>
</main>
<div class="dlg" id="dlg" role="dialog" aria-modal="true" aria-labelledby="dlgT" data-i18n-skip><div class="dlg-box"><h3 id="dlgT"></h3><div id="dlgB"></div>
  <div class="dlg-acts"><button type="button" class="tbtn" id="dlgNo">취소</button><button type="button" class="btn btn-ink" id="dlgYes">확인</button></div></div></div>'''
    html = (C.head('멤버십 | KOSAI') + '\n<style>\n' + C.CSS + '\n' + C.FORM_CSS + '\n' + C.PROSE_CSS + '\n' + CSS + '\n' + C.MOBILE_CSS + '\n</style>\n</head>\n<body>\n'
            + C.nav('멤버십') + '\n' + body + '\n' + C.FOOTER + '\n<script>\n' + C.JS + '\n</script>\n<script type="module">\n' + module + '\n</script>\n</body>\n</html>')
    out = Path(out_path) if out_path else ROOT / 'staging/pricing.html'
    C.emit(out, html)
    print(f'✅ {out} · {len(html):,}자')


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else None)
