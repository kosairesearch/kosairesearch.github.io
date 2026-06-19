#!/usr/bin/env python3
"""테마(카테고리) 랜딩 페이지 생성 — SEO용 정적 프리렌더.

data/stocks.js + data/valuation.js + data/reports-index.js 를 읽어 테마별
종목 랭킹을 HTML 소스에 직접 구워넣는다. 종목 목록과 구조화데이터
(ItemList / FAQPage / BreadcrumbList)가 초기 HTML에 포함되므로
JS 렌더에 의존하지 않아 검색엔진 색인에 유리하다(특히 네이버).

데이터 갱신 워크플로에서 collect_data → generate_sitemap 이후 실행한다.
"""
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://kosai.kr"
TOPN = 50                 # 페이지에 노출할 종목 수
SIZE_FLOOR = 0.3          # 투자가능 규모 하한(조원) — 초소형주 노이즈 제거


# ── 데이터 로드 ──────────────────────────────────────────────────────────
def load_js_global(path, var):
    raw = (ROOT / path).read_text(encoding="utf-8")
    m = re.search(re.escape(var) + r"\s*=\s*(\{.*)", raw, re.S)
    return json.loads(m.group(1).rstrip().rstrip(";"))


def build_universe():
    live = load_js_global("data/stocks.js", "window.KOS_LIVE_DATA")
    val = load_js_global("data/valuation.js", "window.KOS_VALUATION")["stocks"]
    stocks = []
    for s in live["stocks"]:
        v = val.get(s["ticker"], {})
        price = s.get("price") or 0
        eps, bps, dps = v.get("eps"), v.get("bps"), v.get("dps")
        rec = {
            "ticker": s["ticker"],
            "name": s["name"],
            "market": s.get("market", ""),
            "sector": s.get("sector", ""),
            "price": price,
            "change": s.get("change"),
            "mcap": s.get("mcap") or 0,
            "per": round(price / eps, 1) if eps and eps > 0 and price else None,
            "pbr": round(price / bps, 2) if bps and bps > 0 and price else None,
            "div": round(dps / price * 100, 2) if dps is not None and price else None,
            "roe": v.get("roe"),
            "rev_g": v.get("rev_g"),
        }
        stocks.append(rec)
    return stocks, live.get("dataDate", "")


# ── 포맷 헬퍼 (사이트 표기와 동일) ────────────────────────────────────────
def f_won(p):
    return f"{int(round(p)):,}원" if p else "—"


def f_mcap(jo):
    if not jo:
        return "—"
    return f"{jo:,.1f}조" if jo >= 1 else f"{int(round(jo * 10000)):,}억"


def f_pct(c):
    if c is None:
        return '<span class="chg flat">—</span>'
    cls = "up" if c > 0 else "down" if c < 0 else "flat"
    arw = "▲" if c > 0 else "▼" if c < 0 else "—"
    return f'<span class="chg {cls}"><span class="a">{arw}</span> {abs(c):.2f}%</span>'


def f_mult(x):
    return f"{x:.1f}배" if x is not None else "—"


def f_pbr(x):
    return f"{x:.2f}배" if x is not None else "—"


def f_pctval(x):
    return f"{x:.2f}%" if x is not None else "—"


def f_roe(x):
    return f"{x:.1f}%" if x is not None else "—"


# ── 테마 정의 ────────────────────────────────────────────────────────────
def cats():
    return [
        {
            "slug": "high-dividend-stocks",
            "kw": "고배당주",
            "h1": "고배당주 순위 TOP 50",
            "title": "고배당주 추천 TOP 50 — 배당수익률 높은 종목 순위 | KOSAI",
            "desc": "배당수익률 4% 이상 코스피·코스닥 고배당주를 배당수익률 순으로 정리했습니다. 시가총액·PER·배당수익률을 한눈에 비교하세요. 매일 자동 갱신.",
            "intro": "예금 금리 이상의 현금흐름을 노리는 투자자를 위한 <b>고배당주</b> 목록입니다. 배당수익률(연 배당금 ÷ 현재가)이 높은 순으로 정렬했으며, 배당의 지속성을 가늠할 수 있도록 PER·ROE도 함께 표기했습니다.",
            "crit": "배당수익률 <b>4% 이상</b> · 시가총액 3,000억원 이상",
            "ok": lambda s: s["div"] is not None and s["div"] >= 4,
            "key": "div",
            "rev": True,
            "faq": [
                ("배당수익률은 어떻게 계산하나요?",
                 "배당수익률은 ‘주당 배당금 ÷ 현재 주가 × 100’으로 계산합니다. 본 페이지는 가장 최근 확정 배당금과 당일 종가를 기준으로 매일 다시 계산해 갱신합니다."),
                ("배당수익률이 높으면 무조건 좋은가요?",
                 "그렇지 않습니다. 주가가 급락하면 배당수익률이 일시적으로 높아 보일 수 있고, 실적 악화로 배당이 줄거나 끊길 위험도 있습니다. 배당성향·ROE·이익 추세를 함께 확인하는 것이 중요합니다."),
                ("고배당주는 언제 사야 유리한가요?",
                 "배당 기준일(배당락 전) 보유 여부가 그 해 배당 수령을 좌우합니다. 다만 장기 보유 관점에서는 진입 시점보다 기업의 배당 지속 능력이 더 중요합니다."),
            ],
        },
        {
            "slug": "low-per-stocks",
            "kw": "저PER 가치주",
            "h1": "저PER 가치주 TOP 50",
            "title": "저PER 주식 추천 TOP 50 — PER 낮은 저평가 가치주 | KOSAI",
            "desc": "PER 10배 이하 코스피·코스닥 저평가 가치주를 PER 낮은 순으로 정리했습니다. 이익 대비 저렴한 종목을 PER·PBR·ROE와 함께 비교하세요. 매일 갱신.",
            "intro": "기업이 버는 이익에 비해 주가가 싼 <b>저PER 가치주</b> 목록입니다. PER(주가 ÷ 주당순이익)이 낮은 순으로 정렬했으며, 자산 대비 저평가 여부(PBR)와 수익성(ROE)을 함께 확인할 수 있습니다.",
            "crit": "PER <b>10배 이하</b>(흑자 기업) · 시가총액 3,000억원 이상",
            "ok": lambda s: s["per"] is not None and 0 < s["per"] <= 10,
            "key": "per",
            "rev": False,
            "faq": [
                ("PER이 낮으면 저평가된 주식인가요?",
                 "PER이 낮으면 이익 대비 주가가 싸다는 신호일 수 있지만, 업황 둔화나 일회성 이익 등으로 ‘싸 보이는’ 경우도 많습니다. 동종 업종 평균 PER, 이익의 질, 성장성을 함께 살펴야 합니다."),
                ("PER은 몇 배가 적정한가요?",
                 "업종마다 다릅니다. 성장이 빠른 업종은 높은 PER이, 성숙·경기민감 업종은 낮은 PER이 일반적입니다. 따라서 같은 업종 내 비교가 가장 의미 있습니다."),
                ("적자 기업도 포함되나요?",
                 "아니요. 본 목록은 흑자(주당순이익이 양수)인 기업만 대상으로 하며, 시가총액 3,000억원 이상으로 한정해 초소형주의 왜곡을 줄였습니다."),
            ],
        },
        {
            "slug": "high-growth-stocks",
            "kw": "고성장주",
            "h1": "고성장주 TOP 50",
            "title": "고성장주 추천 TOP 50 — 매출 성장률 높은 성장주 순위 | KOSAI",
            "desc": "매출 성장률 25% 이상 코스피·코스닥 고성장주를 성장률 순으로 정리했습니다. 빠르게 커지는 기업을 매출성장률·ROE와 함께 비교하세요. 매일 갱신.",
            "intro": "매출이 빠르게 늘고 있는 <b>고성장주</b> 목록입니다. 매출 성장률이 높은 순으로 정렬했으며, 성장의 질을 가늠할 수 있도록 수익성(ROE)과 밸류에이션(PER)도 함께 표기했습니다.",
            "crit": "매출 성장률 <b>25% 이상</b> · 시가총액 3,000억원 이상",
            "ok": lambda s: s["rev_g"] is not None and s["rev_g"] >= 25,
            "key": "rev_g",
            "rev": True,
            "faq": [
                ("매출 성장률은 어느 기간 기준인가요?",
                 "가장 최근 발표된 연간(또는 연환산) 매출을 직전 기간과 비교한 증가율입니다. 데이터가 갱신되면 자동으로 반영됩니다."),
                ("성장주는 PER이 높아도 괜찮나요?",
                 "성장주는 미래 이익 기대가 주가에 선반영되어 PER이 높은 경우가 많습니다. 다만 성장세가 꺾이면 조정 폭이 클 수 있으므로, 성장의 지속성과 수익성(ROE)을 함께 확인해야 합니다."),
                ("매출은 느는데 적자인 기업도 있나요?",
                 "네, 성장 단계 기업은 매출이 빠르게 늘면서도 적자일 수 있습니다. ROE와 이익 추세를 함께 보면 성장의 질을 판단하는 데 도움이 됩니다."),
            ],
        },
        {
            "slug": "blue-chip-stocks",
            "kw": "대형 우량주",
            "h1": "대형 우량 저평가주 TOP 50",
            "title": "대형 우량주 추천 TOP 50 — 시총 10조+ 저평가 대형주 | KOSAI",
            "desc": "시가총액 10조원 이상이면서 PER 15배 이하인 코스피·코스닥 대형 우량주를 시총 순으로 정리했습니다. 안정성과 밸류를 함께 갖춘 종목을 비교하세요.",
            "intro": "규모가 크면서 이익 대비 밸류에이션이 부담스럽지 않은 <b>대형 우량주</b> 목록입니다. 시가총액이 큰 순으로 정렬했으며, PER·PBR·ROE로 저평가 여부와 수익성을 함께 확인할 수 있습니다.",
            "crit": "시가총액 <b>10조원 이상</b> · PER 15배 이하(흑자)",
            "ok": lambda s: s["mcap"] >= 10 and s["per"] is not None and 0 < s["per"] <= 15,
            "key": "mcap",
            "rev": True,
            "faq": [
                ("대형 우량주에 투자하는 장점은 무엇인가요?",
                 "시가총액이 큰 기업은 일반적으로 사업 안정성과 유동성이 높아 변동성이 상대적으로 낮은 편입니다. 본 목록은 여기에 ‘PER 15배 이하’ 조건을 더해 밸류 부담이 과도하지 않은 종목으로 좁혔습니다."),
                ("‘우량주’의 기준은 무엇인가요?",
                 "통용되는 절대 기준은 없습니다. 본 페이지는 시가총액(규모)과 밸류에이션(PER)을 기계적 기준으로 사용하며, 실제 우량 여부는 재무 건전성·경쟁력·배당 등을 종합해 판단해야 합니다."),
                ("이 목록만 보고 투자해도 되나요?",
                 "아니요. 본 목록은 정량 조건으로 추린 참고 자료이며 투자 권유가 아닙니다. 개별 종목의 사업 내용과 리스크를 직접 확인하시기 바랍니다."),
            ],
        },
        {
            "slug": "high-roe-stocks",
            "kw": "고ROE 우량주",
            "h1": "고ROE 우량주 TOP 50",
            "title": "고ROE 주식 추천 TOP 50 — 자기자본이익률 높은 우량주 | KOSAI",
            "desc": "ROE(자기자본이익률) 15% 이상 코스피·코스닥 우량주를 ROE 순으로 정리했습니다. 자본을 효율적으로 굴리는 기업을 PER·PBR과 함께 비교하세요.",
            "intro": "투입한 자기자본 대비 이익을 잘 내는 <b>고ROE 우량주</b> 목록입니다. ROE가 높은 순으로 정렬했으며, 그 수익성이 주가에 얼마나 반영됐는지 PER·PBR로 함께 확인할 수 있습니다.",
            "crit": "ROE <b>15% 이상</b> · 시가총액 3,000억원 이상",
            "ok": lambda s: s["roe"] is not None and s["roe"] >= 15,
            "key": "roe",
            "rev": True,
            "faq": [
                ("ROE는 무엇을 의미하나요?",
                 "ROE(자기자본이익률)는 ‘순이익 ÷ 자기자본’으로, 주주가 맡긴 자본으로 얼마나 이익을 냈는지를 보여줍니다. 일반적으로 높을수록 자본 효율이 좋다고 해석합니다."),
                ("ROE가 높으면 좋은 주식인가요?",
                 "효율적인 기업일 가능성이 높지만, 부채를 많이 써서 ROE가 부풀려질 수도 있습니다. 부채비율과 이익의 지속성을 함께 봐야 합니다."),
                ("ROE와 PER을 같이 봐야 하는 이유는?",
                 "수익성이 좋아도(높은 ROE) 주가가 이미 비싸면(높은 PER) 투자 매력이 줄어듭니다. 두 지표를 함께 보면 ‘좋은 기업을 적정 가격에’ 골라내는 데 도움이 됩니다."),
            ],
        },
        {
            "slug": "low-pbr-stocks",
            "kw": "저PBR 자산주",
            "h1": "저PBR 자산주 TOP 50",
            "title": "저PBR 주식 추천 TOP 50 — PBR 1배 이하 저평가 자산주 | KOSAI",
            "desc": "PBR 1배 이하 코스피·코스닥 저평가 자산주를 PBR 낮은 순으로 정리했습니다. 순자산 대비 싼 종목을 ROE·배당과 함께 비교하세요. 매일 자동 갱신.",
            "intro": "보유 순자산에 비해 주가가 싼 <b>저PBR 자산주</b> 목록입니다. PBR(주가 ÷ 주당순자산)이 낮은 순으로 정렬했으며, 자산이 실제 수익으로 이어지는지 ROE·배당과 함께 확인할 수 있습니다.",
            "crit": "PBR <b>1배 이하</b> · 시가총액 3,000억원 이상",
            "ok": lambda s: s["pbr"] is not None and 0 < s["pbr"] <= 1,
            "key": "pbr",
            "rev": False,
            "faq": [
                ("PBR 1배 이하는 무슨 뜻인가요?",
                 "PBR이 1배 미만이라는 것은 주가가 회계상 순자산(청산가치 개념)보다 낮게 거래된다는 의미입니다. 저평가 신호일 수 있으나, 자산의 질과 수익성이 낮아 시장이 낮게 평가하는 경우도 있습니다."),
                ("저PBR 주식은 안전한가요?",
                 "순자산이 받쳐 준다는 점에서 하방이 상대적으로 견고할 수 있으나, ROE가 낮으면 오랫동안 저평가가 해소되지 않는 ‘밸류 트랩’이 될 수 있습니다. ROE를 함께 확인하세요."),
                ("정부의 기업 밸류업 정책과 관련이 있나요?",
                 "저PBR 종목은 주주환원 확대·자본 효율 개선을 유도하는 ‘밸류업’ 논의에서 자주 거론됩니다. 다만 정책 기대만으로 투자하기보다 기업의 실제 환원·실적 개선을 확인하는 것이 바람직합니다."),
            ],
        },
    ]


# ── 공통 조각 ────────────────────────────────────────────────────────────
HEAD_STATIC = """  <link rel="icon" type="image/svg+xml" href="assets/kosai-icon-dark.svg?v=k2">
  <link rel="icon" type="image/png" sizes="512x512" href="assets/favicon.png?v=k2">
  <link rel="icon" type="image/png" sizes="32x32" href="assets/favicon.png?v=k2">
  <link rel="apple-touch-icon" sizes="180x180" href="assets/apple-touch-icon.png?v=k2">
  <script src="analytics.js"></script>"""


def nav_html(active):
    items = [
        ("Home.html", "홈"), ("Reports.html", "리포트"),
        ("industry.html", "업종별"), ("themes.html", "테마"),
        ("Screener.html", "스크리너"), ("Watchlist.html", "워치리스트"),
    ]
    def a(h, t):
        cls = ' class="active"' if h == active else ""
        return f'<a href="{h}"{cls}>{t}</a>'

    links = "\n    ".join(a(h, t) for h, t in items)
    menu = "\n  ".join(a(h, t) for h, t in items)
    nav = f"""<nav class="nav glass" data-screen-label="Themes · Nav">
  <a class="brand" href="Home.html"><img class="brand-logo brand-logo--light" src="assets/kosai-wordmark-black.png" alt="KOSAI" width="148" height="24"><img class="brand-logo brand-logo--dark" src="assets/kosai-wordmark-white.png" alt="KOSAI" width="148" height="24"></a>
  <div class="nav-links">
    {links}
  </div>
  <div class="nav-spacer"></div>
  <button class="icon-btn" id="themeBtn" aria-label="테마 전환" title="라이트/다크 전환">
    <svg id="themeIcon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  </button>
  <button class="icon-btn menu-btn" id="menuBtn" aria-label="메뉴">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
  </button>
</nav>
<div class="mobile-menu glass" id="mobileMenu">
  {menu}
</div>"""
    return nav


FOOTER_HTML = """<footer class="foot">
  <div class="wrap">
    <div class="foot-inner glass">
      <div class="foot-grid">
        <div class="foot-brand"><a class="brand" href="Home.html"><img class="brand-logo brand-logo--light" src="assets/kosai-wordmark-black.png" alt="KOSAI" width="148" height="24"><img class="brand-logo brand-logo--dark" src="assets/kosai-wordmark-white.png" alt="KOSAI" width="148" height="24"></a><p>한국 상장사를 위한 AI 투자 리서치. 데이터와 분석을 한 페이지에.</p></div>
        <div class="foot-col"><h4>서비스</h4><ul><li><a href="Home.html">홈</a></li><li><a href="Reports.html">리포트</a></li><li><a href="industry.html">업종별</a></li><li><a href="themes.html">테마</a></li><li><a href="Screener.html">스크리너</a></li></ul></div>
        <div class="foot-col"><h4>회사</h4><ul><li><a href="About.html">About</a></li><li><a href="Contact.html">문의하기</a></li><li><a href="Feedback.html">피드백</a></li></ul></div>
        <div class="foot-col"><h4>정책</h4><ul><li><a href="Terms.html">이용약관</a></li><li><a href="Privacy.html">개인정보처리방침</a></li></ul></div>
      </div>
      <div class="disclaimer"><b>면책 조항</b> · 본 사이트의 모든 AI 분석·리포트는 투자 참고용 정보이며, 투자 권유나 추천이 아닙니다. 투자 판단과 그 결과에 대한 책임은 전적으로 이용자 본인에게 있습니다. 데이터는 지연될 수 있으며 오류가 포함될 수 있습니다.</div>
      <div class="foot-bottom"><span>© 2026 KOSAI — All rights reserved.</span></div>
    </div>
  </div>
</footer>"""

THEME_JS = """<script>
const menuBtn=document.getElementById('menuBtn'),mobileMenu=document.getElementById('mobileMenu');
menuBtn.addEventListener('click',()=>mobileMenu.classList.toggle('open'));
mobileMenu.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>mobileMenu.classList.remove('open')));
const root=document.documentElement,themeBtn=document.getElementById('themeBtn');
const sunSVG='<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';
const moonSVG='<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
function applyTheme(t){root.setAttribute('data-theme',t);document.getElementById('themeIcon').innerHTML=t==='dark'?sunSVG:moonSVG;try{localStorage.setItem('kos-theme',t)}catch(e){}}
let saved='dark';try{saved=localStorage.getItem('kos-theme')||'dark'}catch(e){}
applyTheme(saved);
themeBtn.addEventListener('click',()=>applyTheme(root.getAttribute('data-theme')==='dark'?'light':'dark'));
</script>"""

EXTRA_CSS = """<style>
.lead{max-width:760px;margin:6px 0 0;font:400 16px/1.7 var(--font-sans);color:var(--fg-2);text-wrap:pretty}
.crit-card{display:flex;flex-wrap:wrap;gap:8px 22px;align-items:center;margin:20px 0 6px;padding:14px 18px}
.crit-card .lab{font:600 12.5px var(--font-sans);color:var(--fg-3)}
.crit-card .val{font:500 14px var(--font-sans);color:var(--fg-1)}
.crit-card .dot{color:var(--fg-3)}
.sec{margin:36px 0 0}
.sec h2{font:700 22px var(--font-sans);letter-spacing:-.02em;margin:0 0 14px}
.prose{max-width:760px;font:400 15px/1.75 var(--font-sans);color:var(--fg-2)}
.prose p{margin:0 0 12px}
td .nm a{color:var(--fg-1);text-decoration:none}
td .nm a:hover{text-decoration:underline}
.rk{font:700 13px var(--font-sans);color:var(--fg-3);width:34px}
.hl{color:var(--brand-blue);font-weight:700}
:root[data-theme="dark"] .hl{color:var(--brand-cyan)}
.faq-item{padding:16px 18px;margin-bottom:10px}
.faq-item h3{font:600 15.5px var(--font-sans);margin:0 0 7px;color:var(--fg-1)}
.faq-item p{font:400 14.5px/1.7 var(--font-sans);color:var(--fg-2);margin:0}
.rel-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px}
.rel-card{display:block;padding:16px 18px;text-decoration:none;color:var(--fg-1);transition:transform .12s}
.rel-card:hover{transform:translateY(-2px)}
.rel-card .t{font:700 15px var(--font-sans);margin-bottom:4px}
.rel-card .d{font:400 13px/1.5 var(--font-sans);color:var(--fg-3)}
.cta{display:inline-flex;align-items:center;gap:7px;margin-top:8px;font:600 14px var(--font-sans);color:var(--brand-blue);text-decoration:none}
:root[data-theme="dark"] .cta{color:var(--brand-cyan)}
.cta:hover{text-decoration:underline}
.asof{font:500 12.5px var(--font-sans);color:var(--fg-3);margin-top:10px}
.hub-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-top:8px}
.hub-card{display:block;padding:22px;text-decoration:none;color:var(--fg-1);transition:transform .12s}
.hub-card:hover{transform:translateY(-3px)}
.hub-card .ht{font:700 19px var(--font-sans);letter-spacing:-.02em;margin-bottom:6px}
.hub-card .hc{font:600 13px var(--font-sans);color:var(--brand-blue);margin-bottom:10px}
:root[data-theme="dark"] .hub-card .hc{color:var(--brand-cyan)}
.hub-card .hd{font:400 14px/1.6 var(--font-sans);color:var(--fg-2)}
</style>"""


def esc(s):
    return html.escape(str(s), quote=True)


def meta_block(title, desc, canon):
    t_og = title.split(" | ")[0].split(" — ")[0] + " — KOSAI"
    return f"""<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}" />
<link rel="canonical" href="{canon}" />
<meta name="robots" content="index,follow,max-image-preview:large" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="KOSAI" />
<meta property="og:locale" content="ko_KR" />
<meta property="og:title" content="{esc(t_og)}" />
<meta property="og:description" content="{esc(desc)}" />
<meta property="og:url" content="{canon}" />
<meta property="og:image" content="https://kosai.kr/assets/og-image.png?v=3" />
<meta property="og:image:width" content="1200" />
<meta property="og:image:height" content="630" />
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{esc(t_og)}" />
<meta name="twitter:description" content="{esc(desc)}" />
<meta name="twitter:image" content="https://kosai.kr/assets/og-image.png?v=3" />"""


def table_html(rows):
    head = (
        "<thead><tr><th class='nosort'>#</th><th class='nosort'>종목명</th>"
        "<th class='nosort c-center'>시장</th><th class='nosort'>현재가</th>"
        "<th class='nosort'>등락률</th><th class='nosort'>시가총액</th>"
        "<th class='nosort'>PER</th><th class='nosort'>PBR</th>"
        "<th class='nosort'>배당</th><th class='nosort'>ROE</th></tr></thead>"
    )
    body = []
    for i, s in enumerate(rows, 1):
        cell = {
            "per": (f_mult(s["per"]), "per"),
            "pbr": (f_pbr(s["pbr"]), "pbr"),
            "div": (f_pctval(s["div"]), "div"),
            "roe": (f_roe(s["roe"]), "roe"),
        }
        return_key = s["_key"]

        def c(metric):
            txt, name = cell[metric]
            cls = " class='hl'" if name == return_key else ""
            return f"<td{cls}>{txt}</td>"

        url = f"stock.html?ticker={s['ticker']}"
        body.append(
            f"<tr onclick=\"location.href='{url}'\">"
            f"<td class='rk'>{i}</td>"
            f"<td><span class='nm'><span class='n'><a href='{url}'>{esc(s['name'])}</a></span>"
            f"<span class='s'>{esc(s['sector'] or s['ticker'])}</span></span></td>"
            f"<td class='c-center'><span class='mkt-tag'>{esc(s['market'])}</span></td>"
            f"<td>{f_won(s['price'])}</td>"
            f"<td>{f_pct(s['change'])}</td>"
            f"<td>{f_mcap(s['mcap'])}</td>"
            f"{c('per')}{c('pbr')}{c('div')}{c('roe')}</tr>"
        )
    return (
        "<div class='table-card glass'><div class='table-scroll'><table>"
        + head + "<tbody>" + "".join(body) + "</tbody></table></div></div>"
    )


def jsonld(cat, rows, canon, asof):
    items = [
        {
            "@type": "ListItem",
            "position": i,
            "url": f"{SITE}/stock.html?ticker={s['ticker']}",
            "name": s["name"],
        }
        for i, s in enumerate(rows, 1)
    ]
    blocks = [
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": cat["h1"],
            "description": cat["desc"],
            "url": canon,
            "inLanguage": "ko",
            "isPartOf": {"@type": "WebSite", "name": "KOSAI", "url": SITE + "/"},
            "dateModified": asof,
            "mainEntity": {
                "@type": "ItemList",
                "itemListOrder": "https://schema.org/ItemListOrderDescending",
                "numberOfItems": len(rows),
                "itemListElement": items,
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": SITE + "/Home.html"},
                {"@type": "ListItem", "position": 2, "name": "테마", "item": SITE + "/themes.html"},
                {"@type": "ListItem", "position": 3, "name": cat["kw"], "item": canon},
            ],
        },
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q,
                    "acceptedAnswer": {"@type": "Answer", "text": a},
                }
                for q, a in cat["faq"]
            ],
        },
    ]
    return "\n".join(
        '<script type="application/ld+json">' + json.dumps(b, ensure_ascii=False) + "</script>"
        for b in blocks
    )


def related_html(current, allcats):
    cards = []
    for c in allcats:
        if c["slug"] == current:
            continue
        cards.append(
            f"<a class='rel-card glass' href='{c['slug']}.html'>"
            f"<div class='t'>{esc(c['kw'])}</div>"
            f"<div class='d'>{esc(c['crit'].replace('<b>', '').replace('</b>', ''))}</div></a>"
        )
    return "<div class='rel-grid'>" + "".join(cards) + "</div>"


def page_html(cat, rows, total, style, allcats, asof):
    canon = f"{SITE}/{cat['slug']}.html"
    faq = "".join(
        f"<div class='faq-item glass'><h3>{esc(q)}</h3><p>{esc(a)}</p></div>"
        for q, a in cat["faq"]
    )
    return f"""<!doctype html>
<html lang="ko">
<head>
{meta_block(cat['title'], cat['desc'], canon)}
{style}
{EXTRA_CSS}
{HEAD_STATIC}
{jsonld(cat, rows, canon, asof)}
</head>
<body>
{nav_html('themes.html')}
<div class="wrap">
  <div class="page-head">
    <div class="crumb"><a href="Home.html">홈</a> / <a href="themes.html">테마</a> / <b>{esc(cat['kw'])}</b></div>
    <h1>{cat['h1']}</h1>
    <p class="lead">{cat['intro']}</p>
    <div class="crit-card glass">
      <span class="lab">선정 기준</span><span class="val">{cat['crit']}</span>
      <span class="dot">·</span><span class="val">조건 충족 {total:,}개 중 상위 {len(rows)}개</span>
    </div>
    <div class="asof">데이터 기준일 {asof} · 매일 자동 갱신 · 정렬·표기는 참고용이며 투자 권유가 아닙니다.</div>
  </div>

  {table_html(rows)}
  <a class="cta" href="Screener.html">더 많은 조건으로 직접 걸러보기 — 스크리너 →</a>

  <div class="sec">
    <h2>{esc(cat['kw'])} 자주 묻는 질문</h2>
    {faq}
  </div>

  <div class="sec">
    <h2>다른 테마로 종목 찾기</h2>
    {related_html(cat['slug'], allcats)}
  </div>
</div>
{FOOTER_HTML}
{THEME_JS}
</body>
</html>"""


def hub_html(allcats, counts, style, asof):
    canon = f"{SITE}/themes.html"
    title = "테마별 종목 — 고배당·저PER·고성장·우량주 순위 | KOSAI"
    desc = "고배당주·저PER 가치주·고성장주·대형 우량주·고ROE·저PBR 등 테마별 한국 주식 순위를 한 곳에서. 매일 자동 갱신되는 종목 리스트."
    cards = []
    for c in allcats:
        cards.append(
            f"<a class='hub-card glass' href='{c['slug']}.html'>"
            f"<div class='ht'>{esc(c['kw'])}</div>"
            f"<div class='hc'>{counts[c['slug']]:,}개 종목</div>"
            f"<div class='hd'>{esc(c['crit'].replace('<b>', '').replace('</b>', ''))}</div></a>"
        )
    ld = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "테마별 종목",
        "description": desc,
        "url": canon,
        "inLanguage": "ko",
        "hasPart": [
            {"@type": "WebPage", "name": c["kw"], "url": f"{SITE}/{c['slug']}.html"}
            for c in allcats
        ],
    }
    return f"""<!doctype html>
<html lang="ko">
<head>
{meta_block(title, desc, canon)}
{style}
{EXTRA_CSS}
{HEAD_STATIC}
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
</head>
<body>
{nav_html('themes.html')}
<div class="wrap">
  <div class="page-head">
    <div class="crumb"><a href="Home.html">홈</a> / <b>테마</b></div>
    <h1>테마별 종목</h1>
    <p class="lead">관심 있는 투자 스타일에 맞춰 한국 상장사를 골라보세요. 각 테마는 객관적 재무 기준으로 종목을 추리며, 시세·밸류에이션 데이터에 맞춰 매일 자동 갱신됩니다.</p>
    <div class="asof">데이터 기준일 {asof} · 본 페이지는 투자 참고용 정보이며 투자 권유가 아닙니다.</div>
  </div>
  <div class="hub-grid">
    {''.join(cards)}
  </div>
</div>
{FOOTER_HTML}
{THEME_JS}
</body>
</html>"""


def main():
    stocks, dd = build_universe()
    asof = f"{dd[:4]}-{dd[4:6]}-{dd[6:8]}" if len(dd) == 8 else date.today().isoformat()
    scr = (ROOT / "Screener.html").read_text(encoding="utf-8")
    style = re.search(r"<style>\s*@font-face.*?</style>", scr, re.S).group(0)

    allcats = cats()
    counts = {}
    for cat in allcats:
        pool = [s for s in stocks if s["mcap"] >= SIZE_FLOOR and cat["ok"](s)]
        pool.sort(key=lambda s: s[cat["key"]], reverse=cat["rev"])
        counts[cat["slug"]] = len(pool)
        rows = pool[:TOPN]
        for r in rows:
            r["_key"] = cat["key"] if cat["key"] in ("per", "pbr", "div", "roe") else None
        out = page_html(cat, rows, len(pool), style, allcats, asof)
        (ROOT / f"{cat['slug']}.html").write_text(out, encoding="utf-8")
        print(f"  {cat['slug']}.html — {len(pool)}개 중 {len(rows)}개 노출")

    (ROOT / "themes.html").write_text(hub_html(allcats, counts, style, asof), encoding="utf-8")
    print("  themes.html (허브)")
    print(f"테마 랜딩 {len(allcats)} + 허브 1 페이지 생성 완료 (기준 {asof})")


if __name__ == "__main__":
    main()
