#!/usr/bin/env python3
"""신규 상장 종목의 리포트를 상장 전에 쓰고 게시한다(2026-11-18 사장 "상장 당일에 리포트를 뿌려야 유입이 많이 되는데, 당일에 일찍
리포트를 만들 수 없어?").

왜 있나
  신규 상장 리포트는 상장일 시세가 시세 자료(data/stocks.js)에 들어온 뒤에야 종목을 알아(new_listings.py), 상장 다음 날 새벽 ~ 아침에
  올라갔다(2026-11 래블업 · 이에스티 · 동원파츠 · 바로팜 · 넥스아이). 신규 상장 작업의 23:30 예약도 실제로는 이튿날 새벽 ~ 아침에 돌았다.

  한국거래소는 상장 이틀(영업일) 전 오후에 KIND 오늘의 공시에 '신규상장' 안내를 올린다(코스닥시장본부 · 유가증권시장본부). 그 문서에
  종목코드 · 표준코드 · 정식 회사명(한글 · 영문) · 상장주식수 · 액면가 · 소속부 · 업종 · 상장일(매매개시일) · 주요주주 · 대표이사 ·
  상장주선인 · 주요 제품이 있다(2026-11-18 러너 진단 — 하나에어로 11/18 17:03 안내 → 11/20 상장 · 에이엘로봇 11/16 18:06 → 11/18).
  KIND 공모진행 현황은 확정 공모가 · 공모금액 · 수요예측 · 청약 · 납입 일정 · 주관사를 준다. 한국거래소 전종목 기본정보 · 종목 검색 ·
  KIND 상장법인목록 · DART 회사 개황의 종목코드는 상장일 전에는 비어 있다(같은 진단).

  그래서 안내가 나오면 바로(늦어도 상장 전날 아침 브리핑 작업이 깨울 때) 리포트를 옛 형식 생성기(generate_reports_batch · 배치 ·
  하이쿠)로 쓰고, 종목 페이지(/stock/{종목코드}.html · 영어 /en/stock/)를 만들어 게시한다. 상장 전이라 시세가 없으므로 페이지 머리에는
  공모가 · 상장일을 쓰고(build_stock_staging.heroH), 시세 자료에 오르기 전까지 색인 · 사이트맵 · 리포트 정리에서 상장 종목으로
  다룬다(data/ipo.json · ipo_listings.active). 상장일 장 마감 뒤 시세 갱신이 종목을 시세 자료에 올리면 원래 상장 종목과 같다 —
  신규 상장 작업은 리포트가 있으니 다시 주문하지 않는다.

  python3 scripts/ipo_reports.py scan       # 찍기만 — 안내가 나온 상장 예정 종목 · 공모 정보 · 할 일(돈 안 듦 · 쓰지 않음)
  python3 scripts/ipo_reports.py prepare    # data/ipo.json 에 적고 리포트를 쓸 종목을 작업 출력(tickers · has_new)으로 넘긴다(돈 안 듦)
  python3 scripts/ipo_reports.py ping       # 게시한 페이지(한국어 · 영어)가 열리면 네이버에 한 번 알린다(IndexNow · 종목마다 한 번)

실행 기록은 공개다 — 공개 정보(공시 · 공모 일정)만 찍는다.
"""
import datetime
import html as H
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ipo_listings as L  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STOCKS_JS = ROOT / "data" / "stocks.js"
KIND = "https://kind.krx.co.kr"
UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0; +https://kosai.kr)"}
LOOKBACK_DAYS = 8          # 오늘의 공시를 며칠 거슬러 보나 — 안내는 상장 이틀(영업일) 전에 나온다 · 연휴를 넉넉히
MAX_NEW = int(os.getenv("IPO_MAX_NEW", "6") or "6")   # 한 번에 쓸 최대 종목 수(하루 상장은 많아야 서넛이다)
FILERS = {"코스닥시장본부": "코스닥", "유가증권시장본부": "코스피", "코넥스시장": "코넥스", "코넥스시장본부": "코넥스"}
SKIP_NAME = re.compile(r"스팩|기업인수목적")   # 스팩은 시세 자료에서도 뺀다(collect_data._is_pref_or_spac)


def log(*a):
    print(*a, flush=True)


def kst_now():
    return datetime.datetime.now(L.KST)


# ── 글 다듬기 ─────────────────────────────────────────────────────────────────
def squeeze(html, n=None):
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "", flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>", " ", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = H.unescape(re.sub(r"&nbsp;?", " ", t))
    t = re.sub(r"\s+", " ", t).strip()
    return t[:n] if n else t


def _decode(content):
    t = content.decode("utf-8", "replace")
    if t.count("�") > 20:
        t = content.decode("euc-kr", "replace")
    return t


def _int(x):
    d = re.sub(r"[^\d]", "", str(x or ""))
    return int(d) if d else None


def _date(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d)).isoformat()
    except (TypeError, ValueError):
        return ""


# ── KIND: 오늘의 공시의 '신규상장' 안내 ───────────────────────────────────────
def parse_today_rows(html):
    """오늘의 공시 목록 HTML → [{acpt, isur, name, title, filer}] — 제목이 '신규상장' 인 줄만."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S):
        acpt = re.search(r"openDisclsViewer\('(\d{14})'", tr)
        if not acpt:
            continue
        titles = re.findall(r"title='([^']*)'", tr) + re.findall(r'title="([^"]*)"', tr)
        cells = [squeeze(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        title = next((t for t in titles if t.strip() == "신규상장"), None)
        if not title:
            continue
        isur = re.search(r"companysummary_open\('([0-9A-Z]+)'\)", tr)
        filer = next((c for c in cells if c in FILERS), "")
        name = titles[0].strip() if titles and titles[0].strip() != "신규상장" else (cells[1] if len(cells) > 1 else "")
        out.append({"acpt": acpt.group(1), "isur": isur.group(1) if isur else "", "name": name, "title": title, "filer": filer})
    return out


def parse_notice(text):
    """'신규상장' 안내 본문(글만) → dict. 종목코드 · 약명 · 상장일이 없으면 None."""
    t = squeeze(text)
    m_code = re.search(r"보통주\s+([A-Z]{2}[0-9A-Z]{10})\s+A?([0-9][0-9A-Z]{5})\s+([\d,]+)", t)
    m_name = re.search(r"정식명\s+한글\s+(.+?)\s+영문\s+(.+?)\s+약명\s+한글\s+(.+?)\s+영문\s+(.+?)\s+2\.", t)
    m_date = re.search(r"상장일\s*\(매매개시일\)\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일", t)
    if not (m_code and m_name and m_date):
        return None

    def grab(pat):
        m = re.search(pat, t)
        return m.group(1).strip(" -") if m else ""

    ind = re.search(r"\d+\.업종\s+(.+?)\s+(\d\d)-(\d\d)-(\d\d)\s", t)
    ksic = ""
    if ind:
        # 한국거래소 업종 번호 'AA-BB-CC' 의 BB · CC 끝자리가 표준산업분류 세 자리다('03-31-03' → 313 항공기 · '03-29-02' → 292)
        ksic = f"{ind.group(3)}{int(ind.group(4)) % 10}"
    return {
        "code": m_code.group(2), "isin": m_code.group(1), "shares": _int(m_code.group(3)),
        "full_name": m_name.group(1).strip(), "name_en": m_name.group(2).strip(),
        "name": m_name.group(3).strip(), "abbr_en": m_name.group(4).strip(),
        "list_date": _date(*m_date.groups()),
        "par": _int(grab(r"액면가\(원\)\s+([\d,]+)")),
        "fiscal_month": _int(grab(r"결산기\s+(\d{1,2})월")),
        "division": grab(r"소속부\s+(.+?)\s+\d+\.업종"),
        "industry": ind.group(1).strip() if ind else "",
        "ksic": ksic,
        "holders": grab(r"주요주주\s+(.+?)\s+\d+\.기타"),
        "ceo": grab(r"대표이사\s+(.+?)\s+명의개서대행기관"),
        "underwriter": grab(r"상장주선인\s+(.+?)\s+주요사업\(제품\)"),
        "products": grab(r"주요사업\(제품\)\s+(.+?)\s+\d+\.비고"),
    }


# ── KIND: 공모진행 현황(확정 공모가 · 공모금액 · 일정 · 주관사) ─────────────────
def parse_offers(html):
    """공모진행 현황 목록 HTML → [{name, market, filed, bookbuild, subscribe, pay, offer_price, offer_amount_mil, list_date, underwriter}]."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html or "", re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if len(tds) < 9:
            continue
        mk = re.search(r"alt='([^']+)'", tds[0]) or re.search(r'alt="([^"]+)"', tds[0])
        cells = [squeeze(c) for c in tds]
        market = {"코스닥": "코스닥", "유가증권": "코스피", "코넥스": "코넥스"}.get(mk.group(1) if mk else "", "")
        out.append({"name": cells[0], "market": market, "filed": cells[1], "bookbuild": cells[2], "subscribe": cells[3],
                    "pay": cells[4], "offer_price": _int(cells[5]), "offer_amount_mil": _int(cells[6]),
                    "list_date": cells[7], "underwriter": cells[8]})
    return out


class Kind:
    """KIND 조회 — 실패하면 빈 값(그날은 아무것도 주문하지 않을 뿐이다)."""

    def __init__(self, session=None):
        import requests
        self.s = session or requests.Session()
        self.s.headers.update(UA)

    # KIND 가 러너에 따라 403 을 돌려줄 때가 있다(2026-11-18 — 같은 주소가 네 번 받고 다섯 번째 실행에서 첫 요청부터 403). 잠시 쉬었다
    # 두 번 더 묻고, 그래도 막히면 그 실행은 아무것도 주문하지 않는다 — 이 작업은 하루 여러 번 불리므로(브리핑 · 예약) 다음 실행이 다시 본다.
    RETRY_WAITS = (0, 15, 45)

    def _req(self, meth, url, **kw):
        last = None
        for wait in self.RETRY_WAITS:
            if wait:
                time.sleep(wait)
            try:
                r = self.s.request(meth, url, timeout=30, **kw)
                if r.status_code in (403, 429) or r.status_code >= 500:
                    last = RuntimeError(f"HTTP {r.status_code}")
                    continue
                r.raise_for_status()
                return _decode(r.content)
            except Exception as e:                           # noqa: BLE001 — 통신 오류도 같은 방식으로 다시 묻는다
                last = e
        raise last

    def _get(self, path, **params):
        return self._req("GET", KIND + path, params=params)

    def _post(self, path, data):
        url = KIND + path
        return self._req("POST", url, data=data, headers={"Referer": url, "X-Requested-With": "XMLHttpRequest"})

    def notices(self, days=LOOKBACK_DAYS, today=None):
        today = today or kst_now().date()
        self._get("/disclosure/todaydisclosure.do", method="searchTodayDisclosureMain")
        out = []
        for back in range(days):
            d = today - datetime.timedelta(days=back)
            if d.weekday() >= 5:
                continue
            html = self._post("/disclosure/todaydisclosure.do", {
                "method": "searchTodayDisclosureSub", "currentPageSize": "3000", "pageIndex": "1", "orderMode": "0",
                "orderStat": "D", "forward": "todaydisclosure_sub", "chose": "S", "todayFlag": "N", "selDate": d.isoformat(),
                "marketType": ""})
            for row in parse_today_rows(html):
                row["date"] = d.isoformat()
                out.append(row)
        return out

    def notice_text(self, acpt):
        page = self._get("/common/disclsviewer.do", method="search", acptno=acpt, docno="", viewerhost="", viewerport="")
        docs = re.findall(r"<option[^>]*value=['\"](\d{14})\|[^'\"]*['\"]", page)
        for doc in docs[:2]:
            body = self._get("/common/disclsviewer.do", method="searchContents", docNo=doc)
            for p in re.findall(r"(/external/[^'\"\s]+?\.htm)", body)[:1]:
                return squeeze(self._get(p))
        return ""

    def offers(self):
        self._get("/listinvstg/pubofrprogcom.do", method="searchPubofrProgComMain")
        return parse_offers(self._post("/listinvstg/pubofrprogcom.do", {
            "method": "searchPubofrProgComSub", "currentPageSize": "50", "pageIndex": "1", "orderMode": "1", "orderStat": "D",
            "searchMode": "", "marketType": "", "searchCorpName": "", "repIsuSrtCd": ""}))


# ── 상장 예정 종목 모으기 ─────────────────────────────────────────────────────
def listed_tickers():
    try:
        raw = STOCKS_JS.read_text(encoding="utf-8")
        return {s["ticker"] for s in json.loads(raw[raw.find("{"): raw.rfind("}") + 1])["stocks"]}
    except Exception:                                        # noqa: BLE001
        return set()


def has_report(tk):
    return (ROOT / "data" / "reports" / f"{tk}.json").exists() or (ROOT / "data" / "reports_v2" / f"{tk}.json").exists()


def sector_of(ksic, tk, name):
    """대표 업종 · 태그 — 시세 수집과 같은 규칙(collect_data.primary_category · categories_for). 업종을 못 정하면 '기타'."""
    try:
        import collect_data as CD
        prim = CD.primary_category(ksic or "", tk, "기타", name)
        return prim, CD.categories_for(tk, prim, ksic or "", name)
    except Exception:                                        # noqa: BLE001
        return "기타", ["기타"]


def collect(kind, today=None, listed=None, log_fn=log):
    """안내가 나온 상장 예정 종목 {종목코드: 항목}. 상장일이 오늘 이전이거나 이미 시세 자료에 있는 종목은 뺀다(신규 상장 작업의 몫)."""
    today = today or kst_now().date()
    listed = listed_tickers() if listed is None else listed
    try:
        offers = kind.offers()
    except Exception as e:                                   # noqa: BLE001
        log_fn(f"  · KIND 공모진행 현황을 받지 못했다({type(e).__name__}) — 공모가 없이 쓴다")
        offers = []
    found, seen = {}, set()
    for nt in kind.notices(today=today):
        if nt["acpt"] in seen:
            continue
        seen.add(nt["acpt"])
        if SKIP_NAME.search(nt["name"] or ""):
            continue
        try:
            doc = parse_notice(kind.notice_text(nt["acpt"]))
        except Exception as e:                               # noqa: BLE001
            log_fn(f"  · {nt['name']} 안내({nt['acpt']})를 읽지 못했다({type(e).__name__})")
            continue
        if not doc:
            log_fn(f"  · {nt['name']} 안내({nt['acpt']})에서 종목코드 · 상장일을 찾지 못했다")
            continue
        if SKIP_NAME.search(doc["name"]) or doc["list_date"] < today.isoformat() or doc["code"] in listed:
            continue
        of = next((o for o in offers if o["name"] == doc["name"] and o["list_date"] == doc["list_date"]), None)
        sector, cats = sector_of(doc["ksic"], doc["code"], doc["name"])
        found[doc["code"]] = dict(doc, market=FILERS.get(nt["filer"]) or (of or {}).get("market") or "", sector=sector,
                                  categories=cats, notice=nt["acpt"], notice_date=nt["date"],
                                  offer=({k: of[k] for k in ("offer_price", "offer_amount_mil", "bookbuild", "subscribe", "pay",
                                                             "underwriter")} if of else None))
    return found


def merge(ipo, found, now):
    """data/ipo.json 에 반영 — 게시 · 알림 기록(published · pinged)과 증권신고서 재무(filing)는 그대로 둔다."""
    st = ipo.setdefault("stocks", {})
    changed = False
    for tk, e in found.items():
        old = st.get(tk) or {}
        keep = {k: old[k] for k in ("published", "pinged", "filing") if k in old}
        new = dict({k: v for k, v in e.items() if v not in (None, "")}, **keep, seen=old.get("seen") or now)
        if new != old:
            st[tk], changed = new, True
    if changed:
        ipo["updated"] = now
    return ipo


def before_trading(entry, now=None):
    """첫 거래 전인가 — 상장일이 내일 이후이거나, 오늘이고 장 시작(09:00) 전. 거래가 시작된 종목은 '첫 거래 전' 판으로 쓰지 않고
    신규 상장 작업(new_listings · 상장일 시세가 들어온 뒤 · 평소 지시문)에 맡긴다."""
    now = now or kst_now()
    d = str((entry or {}).get("list_date", ""))
    return d > now.date().isoformat() or (d == now.date().isoformat() and now.hour < 9)


def todo(ipo, now=None):
    """리포트를 쓸 종목 — 창 안 · 첫 거래 전 · 시세 자료에 없음 · 리포트 없음. 상장일 순."""
    now = now or kst_now()
    listed = listed_tickers()
    out = [tk for tk, e in (ipo.get("stocks") or {}).items()
           if L.in_window(e, now.date()) and before_trading(e, now) and tk not in listed and not has_report(tk)]
    return sorted(out, key=lambda t: (ipo["stocks"][t].get("list_date", ""), t))[:MAX_NEW]


def attach_filing(ipo, tks, key=None, codes=None):
    """리포트를 쓸 종목에 증권신고서 · 투자설명서의 요약재무정보와 공모 자금 사용 계획을 단다(scripts/ipo_filing.py · 2026-11-18
    사장 "재무제표라든지 리포트에 필요한 다른 데이터들은 없어??"). 이미 단 종목은 다시 받지 않는다. 받지 못하면 그 종목은 재무 없이
    전처럼 검색으로 쓴다 — 리포트를 막지 않는다. 단 종목 수를 돌려준다."""
    key = key if key is not None else os.getenv("DART_API_KEY", "").strip()
    need = [tk for tk in tks if not ((ipo.get("stocks") or {}).get(tk) or {}).get("filing")]
    if not need:
        return 0
    if not key:
        log("  · DART 키가 없어 증권신고서 재무를 싣지 않는다")
        return 0
    import ipo_filing
    try:
        if codes is None:
            import dart_reader
            codes = dart_reader.reader(key).corp_codes
    except Exception as e:                                   # noqa: BLE001
        log(f"  · DART 회사 목록을 받지 못했다 — {type(e).__name__} · 증권신고서 재무 없이 쓴다")
        return 0
    n = 0
    for tk in need:
        e = ipo["stocks"][tk]
        try:
            fin = ipo_filing.collect(key, codes, e.get("full_name"), e.get("name"), log=log)
        except Exception as ex:                              # noqa: BLE001
            log(f"  · {tk} 증권신고서 읽기 실패 — {type(ex).__name__}")
            fin = None
        if fin:
            e["filing"] = fin
            n += 1
            yrs = [p["end"] for p in fin["periods"]]
            log(f"  · {tk} {e.get('name')} 증권신고서 재무: {fin.get('report_nm')}({fin.get('rcept_dt')})"
                f" · {'연결' if fin.get('basis') == '연결' else '별도'} · {yrs[0]}~{yrs[-1]} {len(yrs)}개 기간"
                f" · 자금 사용 계획 {len((fin.get('funds') or {}).get('uses') or [])}항목")
    return n


def describe(tk, e):
    of = e.get("offer") or {}
    price = f"공모가 {of['offer_price']:,}원" if of.get("offer_price") else "공모가 미확인"
    return (f"{tk} {e.get('name')} · {e.get('market') or '?'} · 상장일 {e.get('list_date')} · {price} · 업종 {e.get('sector')}"
            f" · 리포트 {'있음' if has_report(tk) else '없음'}")


def cmd_scan_prepare(write):
    now = kst_now().strftime("%Y-%m-%d %H:%M")
    kind = Kind()
    try:
        found = collect(kind)
    except Exception as e:                                   # noqa: BLE001
        log(f"❌ KIND 오늘의 공시를 받지 못했다 — {type(e).__name__}: {e}")
        found = None
    ipo = L.load()
    before = json.dumps(ipo.get("stocks") or {}, ensure_ascii=False, sort_keys=True)
    n_old = L.prune(ipo)
    if found:
        merge(ipo, found, now)
    changed = json.dumps(ipo.get("stocks") or {}, ensure_ascii=False, sort_keys=True) != before
    log(f"## 상장 예정 종목(한국거래소 '신규상장' 안내) — {now} KST")
    for tk, e in sorted((found or {}).items(), key=lambda x: x[1].get("list_date", "")):
        log("  · " + describe(tk, e))
    if found == {}:
        log("  · 안내가 나온 상장 예정 종목이 없다")
    tks = todo(ipo)
    log(f"리포트를 쓸 종목: {','.join(tks) or '없음'}" + (f" · 창이 지난 줄 {n_old}개 정리" if n_old else ""))
    if tks and write and attach_filing(ipo, tks):
        changed = True
    if write:
        if changed:          # 바뀐 것이 없으면 쓰지 않는다 — 하루 여러 번 불려도 커밋이 생기지 않게
            L.save(ipo)
        gh = os.getenv("GITHUB_OUTPUT")
        if gh:
            with open(gh, "a", encoding="utf-8") as f:
                f.write(f"tickers={','.join(tks)}\nhas_new={'1' if tks else ''}\n")
    return tks


# ── 네이버에 알리기 ───────────────────────────────────────────────────────────
def page_live(url, timeout=20):
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
            return r.status == 200
    except Exception:                                        # noqa: BLE001
        return False


def cmd_ping(wait_sec=None):
    """게시한 페이지가 열리면(배포 뒤) 한국어 · 영어 주소를 네이버에 한 번 알린다. 이미 알린 종목은 보내지 않는다."""
    # 예약 실행에서도 알린다 — 새 주소를 종목마다 한 번만 보내므로 되풀이가 아니다(naver_indexnow.py 의 대량 알림은 손으로만 돌린다)
    import naver_indexnow as N
    ipo = L.load()
    st = ipo.get("stocks") or {}
    want = [tk for tk, e in st.items() if L.in_window(e) and has_report(tk) and not e.get("pinged")]
    if not want:
        log("알릴 새 페이지 없음")
        return 0
    if not N.key_ok():
        log("열쇠 파일이 없거나 내용이 다르다 — 알리지 않는다")
        return 1
    wait_sec = int(os.getenv("IPO_PING_WAIT_SEC", "900")) if wait_sec is None else wait_sec
    deadline = time.time() + wait_sec
    urls = {tk: [f"https://kosai.kr/stock/{tk}.html", f"https://kosai.kr/en/stock/{tk}.html"] for tk in want}
    ready = []
    while True:
        ready = [tk for tk in want if all(page_live(u) for u in urls[tk])]
        if len(ready) == len(want) or time.time() >= deadline:
            break
        time.sleep(30)
    if not ready:
        log(f"페이지가 아직 열리지 않았다({', '.join(want)}) — 다음 실행이 다시 본다")
        return 0
    good = True
    flat = [u for tk in ready for u in urls[tk]]
    for n, code in N.send(flat):
        log(f"  네이버에 {n}개 주소 알림 → {code} {N.MEANING.get(code, '알 수 없는 응답')}")
        good = good and code in (200, 202)
    if good:
        now = kst_now().strftime("%Y-%m-%d %H:%M")
        for tk in ready:
            st[tk]["pinged"] = now
        L.save(ipo)
    return 0 if good else 1


def mark_published(tickers):
    """리포트를 저장한 종목에 게시 시각을 적는다(작업 끝에서 부른다)."""
    ipo = L.load()
    now = kst_now().strftime("%Y-%m-%d %H:%M")
    n = 0
    for tk in tickers:
        e = (ipo.get("stocks") or {}).get(tk)
        if e is not None and has_report(tk) and not e.get("published"):
            e["published"] = now
            n += 1
    if n:
        L.save(ipo)
    return n


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scan"
    if mode == "scan":
        cmd_scan_prepare(write=False)
    elif mode == "prepare":
        cmd_scan_prepare(write=True)
    elif mode == "published":
        log(f"게시 시각 기록 {mark_published(sorted(L.active()))}건")
    elif mode == "ping":
        sys.exit(cmd_ping())
    else:
        log(f"모르는 모드: {mode}")
        sys.exit(2)
