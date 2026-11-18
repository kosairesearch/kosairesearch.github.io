#!/usr/bin/env python3
"""상장 전 신규 상장 리포트 회귀 검사 — KIND · DART · Anthropic 없이 가짜로 돌린다(2026-11-18).

  python3 scripts/tests/ipo_reports_test.py

왜 있나 — 2026-11-18 사장 "상장 당일에 리포트를 뿌려야 유입이 많이 되는데, 당일에 일찍 리포트를 만들 수 없어?". 신규 상장 리포트는
상장일 시세가 시세 자료에 들어온 뒤에야 종목을 알아 상장 다음 날 새벽 ~ 아침에 올라갔다. 한국거래소가 상장 이틀 전 오후에 KIND 에
올리는 '신규상장' 안내로 종목코드를 미리 알아 상장 전에 쓰고 게시한다(scripts/ipo_reports.py · .github/workflows/ipo_reports.yml).

  ① 안내 읽기      종목코드 · 표준코드 · 약명 · 정식명 · 영문명 · 상장일 · 상장주식수 · 업종(표준산업분류 세 자리) · 영문 섞인 코드
  ② 목록 읽기      오늘의 공시에서 제목이 '신규상장'인 줄만(기준가격 안내 · 다른 공시는 뺀다) · 공모진행 현황(공모가 · 공모금액 · 일정)
  ③ 모으기         스팩 · 지난 상장일 · 이미 시세 자료에 있는 종목은 뺀다 · 공모 정보를 이름과 상장일로 잇는다 · 시장은 공시 제출인으로
  ④ 목록 파일      게시 · 알림 기록을 지킨다 · 창(상장일 7일 전 ~ 14일 뒤) · 창이 지난 줄 정리 · 바뀐 것이 없으면 쓰지 않는다
  ⑤ 할 일          리포트가 있는 종목 · 시세 자료에 오른 종목 · 지난 상장일은 다시 쓰지 않는다
  ⑥ 지시문         공모 판 재료(상장일 · 공모가 · 공모금액 · 상장주식수)와 지침 · 시세 줄 없음 · 일반 종목 지시문은 그대로
  ⑦ 생성기         시세 자료에 없는 상장 예정 종목을 주문하고(REPORT_EXTRA_STOCKS=ipo), 저장한 리포트에 ipo 를 단다 · 상태 파일을 나눈다
  ⑧ 정리 · 색인    리포트 정리 · 목록 색인(write_reports · _reindex) · 사이트맵 · 종목 페이지 색인(listed)이 상장 예정 종목을 지키고,
                   창이 지나면 원래대로 정리한다
  ⑨ 작업 파일      브리핑이 개장일에 깨운다 · 공용 실행 순서(kos-data) 밖 · 자기 상태 파일 · 하이쿠 · 배치 · push_main.sh · 워치독
  ⑩ 네이버 알림    열린 페이지만, 종목마다 한 번
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import ipo_listings as L               # noqa: E402
import ipo_reports as R                # noqa: E402
import generate_reports as G           # noqa: E402
import generate_reports_batch as GB    # noqa: E402

passed = failed = 0


def ok(cond, what, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ✔ {what}{(' — ' + detail) if detail else ''}")
    else:
        failed += 1
        print(f"  ✘ {what}{(' — ' + detail) if detail else ''}")


TMP = Path(tempfile.mkdtemp(prefix="kosai_ipo_"))
(TMP / "data" / "reports").mkdir(parents=True)
(TMP / "data" / "reports_v2").mkdir()
L.IPO_JSON = TMP / "data" / "ipo.json"
R.ROOT = TMP
R.STOCKS_JS = TMP / "data" / "stocks.js"
TODAY = datetime.date(2026, 11, 19)
R.kst_now = lambda: datetime.datetime(2026, 11, 19, 6, 45, tzinfo=L.KST)
L.today_kst = lambda: TODAY


def stocks_js(tickers):
    R.STOCKS_JS.write_text("window.KOS_LIVE_DATA = " + json.dumps(
        {"dataDate": "20261118", "stocks": [{"ticker": t, "name": f"상장{t}", "market": "코스닥", "price": 1000} for t in tickers]},
        ensure_ascii=False) + ";\n", encoding="utf-8")


# 2026-11-18 러너 진단에서 받은 실제 안내 본문(글만) — 하나에어로 · 에이엘로봇
NOTICE_HANA = ("신규상장 1.회사명 정식명 한글 (주)하나에어로다이내믹스 영문 Hana Aero Dynamics Co.,Ltd 약명 한글 하나에어로 영문 HAD "
               "2.주식의 종류와 수 주권 종류 표준코드 단축코드 주식수(주) 보통주 KR7271160004 A271160 17,729,964 3.액면가(원) 100 "
               "4.자본금(원) 1,772,996,400 5.배당기산일 주권종류 배당기산일 보통주 2026년 01월 01일 6.결산기 12월 7.소속부 벤처기업부 "
               "8.업종 항공기,우주선 및 부품 제조업 03-31-03 9.승인일 2026년 11월 18일 10.상장일(매매개시일) 2026년 11월 20일 "
               "11.주요주주 유일성장기업구조혁신신기술투자조합(46.3%) 외 2인(50.2%) 12.기타 우편번호 52512 주소 경상남도 사천시 축동면 "
               "두량로 260 &nbsp 전화번호 055-830-3800 대표이사 손창환 명의개서대행기관 하나은행 주거래은행 농협은행(주) 사천시지부 "
               "상장주선인 IBK투자증권(주) &nbsp 주요사업(제품) 항공기 치공구 및 부품, 항공기 조립 13.비고 투자설명서는 상장공시시스템(KIND) "
               "IPO 현황의 공모기업란(하나에어로다이내믹스)을 참고하시기 바랍니다. -")
NOTICE_AL = ("신규상장 1.회사명 정식명 한글 (주)에이엘로봇 영문 AL Robot Co.,Ltd 약명 한글 에이엘로봇 영문 AL Robot 2.주식의 종류와 수 "
             "주권 종류 표준코드 단축코드 주식수(주) 보통주 KR7471800003 A471800 12,065,688 3.액면가(원) 500 4.자본금(원) 6,032,844,000 "
             "5.배당기산일 주권종류 배당기산일 보통주 2026년 01월 01일 6.결산기 12월 7.소속부 기술성장기업부 8.업종 특수 목적용 기계 제조업 "
             "03-29-02 9.승인일 2026년 11월 16일 10.상장일(매매개시일) 2026년 11월 18일 11.주요주주 강대희(38.07%) 외 4인(41.93%) "
             "12.기타 대표이사 강대희 명의개서대행기관 하나은행 상장주선인 대신증권(주) &nbsp 주요사업(제품) 로봇용 힘/토크센서, 융합 제어장치 "
             "13.비고 -")

print("① '신규상장' 안내 읽기")
d = R.parse_notice(NOTICE_HANA)
ok(d and d["code"] == "271160" and d["isin"] == "KR7271160004" and d["shares"] == 17729964, "종목코드 · 표준코드 · 상장주식수",
   str(d and {k: d[k] for k in ("code", "isin", "shares")}))
ok(d and d["name"] == "하나에어로" and d["full_name"] == "(주)하나에어로다이내믹스" and d["name_en"] == "Hana Aero Dynamics Co.,Ltd",
   "약명 · 정식명 · 영문명", str(d and (d["name"], d["full_name"], d["name_en"])))
ok(d and d["list_date"] == "2026-11-20" and d["ksic"] == "313" and d["industry"] == "항공기,우주선 및 부품 제조업",
   "상장일 · 업종 · 표준산업분류 세 자리('03-31-03' → 313)", str(d and (d["list_date"], d["ksic"])))
ok(d and d["underwriter"] == "IBK투자증권(주)" and d["products"] == "항공기 치공구 및 부품, 항공기 조립" and d["ceo"] == "손창환"
   and d["division"] == "벤처기업부" and d["holders"].startswith("유일성장"), "상장주선인 · 주요 제품 · 대표이사 · 소속부 · 주요주주",
   str(d and (d["underwriter"], d["products"], d["ceo"], d["division"])))
d2 = R.parse_notice(NOTICE_AL.replace("A471800", "A0162D0"))
ok(d2 and d2["code"] == "0162D0", "영문이 섞인 종목코드(A0162D0 → 0162D0)", str(d2 and d2["code"]))
ok(R.parse_notice("신규상장 1.회사명 … 상장일(매매개시일) 2026년 11월 20일") is None, "종목코드가 없으면 None")
ok(R.sector_of("313", "271160", "하나에어로")[0] == "항공·방산", "대표 업종은 시세 수집과 같은 규칙", str(R.sector_of("313", "271160", "하나에어로")))

print("② 오늘의 공시 · 공모진행 현황 읽기")
ROWS = """<tr><td class="first txc">17:03</td> <td> <a id="companysum" href="#companysum" onclick="companysummary_open('27116'); return false;" title='하나에어로'> 하나에어로</a> </td> <td><a href="#viewer" onclick="openDisclsViewer('20261118000506','')" title='신규상장'>신규상장</a></td> <td>코스닥시장본부</td> <td class="txc"> <a href="#" title="공시차트" onclick="openDisclsChart('27116');return false;"><span>공시차트</span></a></td></tr>
<tr><td class="first txc">16:32</td> <td> <a id="companysum" href="#companysum" onclick="companysummary_open('47180'); return false;" title='에이엘로봇'> 에이엘로봇</a> </td> <td><a href="#viewer" onclick="openDisclsViewer('20261117000504','')" title='주권 등 신규상장 시 기준가격 안내'>주권 등 신규상장 시 기준가격 안내</a></td> <td>코스닥시장본부</td></tr>
<tr><td class="first txc">17:37</td> <td><img src='/images/common/icn_t_yu.gif' alt='유가증권'> <a id="companysum" href="#companysum" onclick="companysummary_open('00353'); return false;" title='한화투자증권'> 한화투자증권</a></td> <td><a href="#viewer" onclick="openDisclsViewer('20261118000588','')" title='투자설명서[일괄신고-사채]'>투자설명서[일괄신고-사채]</a></td> <td>한화투자증권</td></tr>"""
rows = R.parse_today_rows(ROWS)
ok(rows == [{"acpt": "20261118000506", "isur": "27116", "name": "하나에어로", "title": "신규상장", "filer": "코스닥시장본부"}],
   "제목이 '신규상장'인 줄만 — 기준가격 안내 · 다른 공시는 뺀다", str(rows))
OFFERS = """<tr> <td class="first" title="하나에어로"> <img src='../images/common/icn_t_ko.gif' class='vmiddle' alt='코스닥' /> 하나에어로 </td> <td class="txc">2026-09-21</td> <td class="txc">&nbsp;&nbsp;&nbsp;2026-11-02<br/> ~ 2026-11-06</td> <td class="txc">&nbsp;&nbsp;&nbsp;2026-11-10<br/> ~ 2026-11-11</td> <td class="txc">2026-11-13</td> <td class="txr">5,700</td> <td class="txr">25,080</td> <td class="txc">2026-11-20</td> <td class="txl">IBK투자증권(주)</td> </tr>
<tr> <td class="first" title="씨아이에스케미칼"> <img src='../images/common/icn_t_ko.gif' class='vmiddle' alt='코스닥' /> 씨아이에스케미칼 </td> <td class="txc">2026-10-19</td> <td class="txc">&nbsp;&nbsp;&nbsp;2026-11-30<br/> ~ 2026-12-04</td> <td class="txc">&nbsp;&nbsp;&nbsp;2026-12-10<br/> ~ 2026-12-11</td> <td class="txc">2026-12-15</td> <td class="txr">-</td> <td class="txr">-</td> <td class="txc">2026-12-22</td> <td class="txl">KB증권(주)</td> </tr>"""
of = R.parse_offers(OFFERS)
ok(len(of) == 2 and of[0]["offer_price"] == 5700 and of[0]["offer_amount_mil"] == 25080 and of[0]["list_date"] == "2026-11-20"
   and of[0]["subscribe"] == "2026-11-10 ~ 2026-11-11" and of[0]["market"] == "코스닥" and of[1]["offer_price"] is None,
   "공모가 · 공모금액(백만원) · 상장예정일 · 청약 일정 · 시장 · 미확정 공모가는 None", json.dumps(of[0], ensure_ascii=False))


class FakeKind:
    def __init__(self, notices, texts, offers):
        self._n, self._t, self._o = notices, texts, offers

    def notices(self, today=None):
        return list(self._n)

    def notice_text(self, acpt):
        return self._t[acpt]

    def offers(self):
        return list(self._o)


print("③ 모으기")
SPAC = NOTICE_AL.replace("에이엘로봇", "하나39호스팩").replace("A471800", "A499990").replace("2026년 11월 18일", "2026년 11월 21일")
OLD = NOTICE_AL                                                # 상장일 11/18 — 지난 상장(신규 상장 작업의 몫)
LISTED = NOTICE_AL.replace("A471800", "A477770").replace("2026년 11월 18일", "2026년 11월 20일")   # 이미 시세 자료에 있다고 친다
kind = FakeKind(
    [{"acpt": "A1", "isur": "27116", "name": "하나에어로", "title": "신규상장", "filer": "코스닥시장본부", "date": "2026-11-18"},
     {"acpt": "A2", "isur": "1", "name": "하나39호스팩", "title": "신규상장", "filer": "코스닥시장본부", "date": "2026-11-18"},
     {"acpt": "A3", "isur": "47180", "name": "에이엘로봇", "title": "신규상장", "filer": "코스닥시장본부", "date": "2026-11-16"},
     {"acpt": "A4", "isur": "2", "name": "에이엘로봇", "title": "신규상장", "filer": "유가증권시장본부", "date": "2026-11-17"},
     {"acpt": "A1", "isur": "27116", "name": "하나에어로", "title": "신규상장", "filer": "코스닥시장본부", "date": "2026-11-18"}],
    {"A1": NOTICE_HANA, "A2": SPAC, "A3": OLD, "A4": LISTED}, of)
found = R.collect(kind, today=TODAY, listed={"477770"}, log_fn=lambda *a: None)
ok(sorted(found) == ["271160"], "스팩 · 지난 상장일 · 시세 자료에 있는 종목은 빼고, 같은 안내는 한 번만", str(sorted(found)))
h = found.get("271160") or {}
ok(h.get("market") == "코스닥" and h.get("sector") == "항공·방산" and (h.get("offer") or {}).get("offer_price") == 5700
   and (h.get("offer") or {}).get("underwriter") == "IBK투자증권(주)" and h.get("notice") == "A1",
   "시장(제출인) · 대표 업종 · 공모 정보(이름 · 상장일로 이음) · 안내 번호", json.dumps({k: h.get(k) for k in ("market", "sector", "offer")}, ensure_ascii=False))

print("④ 목록 파일(data/ipo.json)")
ipo = {"updated": "", "stocks": {"271160": {"name": "하나에어로", "list_date": "2026-11-20", "published": "2026-11-18 21:00",
                                            "pinged": "2026-11-18 21:05", "seen": "2026-11-18 18:20"},
                                 "111110": {"name": "옛상장", "list_date": "2026-10-01"}}}
R.merge(ipo, found, "2026-11-19 06:45")
e = ipo["stocks"]["271160"]
ok(e.get("published") == "2026-11-18 21:00" and e.get("pinged") == "2026-11-18 21:05" and e.get("seen") == "2026-11-18 18:20"
   and e.get("shares") == 17729964, "게시 · 알림 · 처음 본 시각을 지키고 안내 내용을 채운다", str({k: e.get(k) for k in ("published", "pinged", "seen")}))
before = json.dumps(ipo, ensure_ascii=False, sort_keys=True)
R.merge(ipo, found, "2026-11-19 07:15")
ok(json.dumps(ipo, ensure_ascii=False, sort_keys=True) == before, "같은 안내를 다시 합쳐도 바뀌지 않는다(updated 그대로 — 커밋이 생기지 않는다)")
ok(L.prune(ipo, TODAY) == 1 and "111110" not in ipo["stocks"] and "271160" in ipo["stocks"], "창이 지난 줄을 걷는다")
win = {"list_date": "2026-11-20"}
ok(L.in_window(win, datetime.date(2026, 11, 13)) and L.in_window(win, datetime.date(2026, 12, 4))
   and not L.in_window(win, datetime.date(2026, 11, 12)) and not L.in_window(win, datetime.date(2026, 12, 5))
   and not L.in_window({"list_date": "?"}, TODAY), "창 — 상장일 7일 전 ~ 14일 뒤 · 날짜가 없으면 밖")
L.save(ipo)
ok(L.active(TODAY) == {"271160"} and L.load()["stocks"]["271160"]["name"] == "하나에어로", "저장 · 다시 읽기 · 창 안 종목", str(L.active(TODAY)))
L.IPO_JSON.write_text("{깨진", encoding="utf-8")
ok(L.active(TODAY) == set() and L.load() == {"updated": "", "stocks": {}}, "깨진 파일은 빈 목록(정리에서 빼는 종목이 없을 뿐)")
L.save(ipo)

print("⑤ 할 일")
stocks_js(["005930"])
ipo["stocks"]["222220"] = {"name": "내일상장", "list_date": "2026-11-21"}
ipo["stocks"]["333330"] = {"name": "어제상장", "list_date": "2026-11-18"}
ipo["stocks"]["444440"] = {"name": "벌써시세", "list_date": "2026-11-20"}
L.save(ipo)
stocks_js(["005930", "444440"])
(TMP / "data" / "reports" / "222220.json").write_text("{}", encoding="utf-8")
NOW = datetime.datetime(2026, 11, 19, 6, 45, tzinfo=L.KST)
ok(R.todo(ipo, NOW) == ["271160"], "리포트가 있는 종목 · 시세 자료에 오른 종목 · 지난 상장일은 빼고 상장일 순", str(R.todo(ipo, NOW)))
(TMP / "data" / "reports" / "222220.json").unlink()
ok(R.todo(ipo, NOW) == ["271160", "222220"], "상장일 순", str(R.todo(ipo, NOW)))
ipo["stocks"]["555550"] = {"name": "오늘상장", "list_date": "2026-11-19"}
ok("555550" in R.todo(ipo, NOW) and "555550" not in R.todo(ipo, NOW.replace(hour=9, minute=0)),
   "상장일 당일은 장 시작(09:00) 전까지만 — 거래가 시작되면 신규 상장 작업(평소 지시문)에 맡긴다")
ipo["stocks"].pop("555550")

print("⑥ 지시문")
st = L.stock_dict("271160", ipo["stocks"]["271160"])
ok(st["price"] is None and st["mcap"] is None and st["ipo"]["offer_price"] == 5700 and st["ipo"]["list_date"] == "2026-11-20",
   "생성기 종목 꼴 — 시세 칸은 비우고 공모 정보", json.dumps(st["ipo"], ensure_ascii=False)[:160])
p = G.build_prompt(st, "2026-11-19 06:45", "")
ok("상장일(매매개시일): 2026년 11월 20일" in p and "확정 공모가 5,700원[KRW 5,700]" in p and "공모금액 251억원[KRW 25.1 billion]" in p
   and "상장주식수 17,729,964주 · 공모가 기준 시가총액 1,011억원[KRW 101.1 billion]" in p and "대표 주관사 IBK투자증권(주)" in p,
   "공모 판 재료 — 상장일 · 공모가 · 공모금액 · 상장주식수 · 공모가 기준 시가총액 · 주관사")
ok("[신규 상장 종목 — 아래 작성 지침에 더한다]" in p and "현재가" not in p and "거래대금:" not in p and "Hana Aero Dynamics" in p,
   "공모주 지침 · 시세 줄 없음 · 영문명 블록")
p0 = G.build_prompt({"ticker": "005930", "name": "삼성전자", "market": "코스피", "sector": "반도체", "price": 100000, "change": 1.5,
                     "mcap": 600.0, "trading_value": 2e12}, "2026-11-19 06:45", "")
ok("- 현재가: 100,000원 (전일대비 +1.50%)\n- 시가총액: 600조원\n- 거래대금:" in p0 and "신규 상장 종목" not in p0,
   "일반 종목 지시문은 그대로(현재가 · 시가총액 · 거래대금 줄)")

print("⑦ 생성기 — 시세 자료에 없는 상장 예정 종목")
GB.STATE_JS = TMP / "data" / "ipo_batch_state.json"
GB.FAIL_JS = TMP / "data" / "new_listing_fail.json"
GB.load_existing = lambda: ({}, set())
GB.log = lambda *a, **k: None
G.get_dart_financials = lambda tk: ""
G.load_stocks = lambda: {"stocks": [{"ticker": "005930", "name": "삼성전자"}], "dataDate": "20261118"}
written = {}
G.write_reports = lambda reports, model, as_of: written.update(reports)
GOOD = {"title": {"ko": "제목", "en": "t"}, "verdict": "종합 의견", "business": "사업",
        "keypoints": ["a", "b", "c"], "risks": [{"x": 1}, {"y": 2}]}


def msg(text):
    return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text, citations=None)],
                                 usage=None, stop_reason="end_turn")


class FakeBatches:
    def __init__(self):
        self.created = []

    def create(self, requests):
        self.created.append(requests)
        return types.SimpleNamespace(id="msgbatch_IPO1")

    def retrieve(self, bid):
        return types.SimpleNamespace(processing_status="ended", request_counts=types.SimpleNamespace(processing=0, succeeded=1, errored=0))

    def results(self, bid):
        return [types.SimpleNamespace(custom_id="271160", result=types.SimpleNamespace(
            type="succeeded", message=msg("===JSON_START===" + json.dumps(GOOD, ensure_ascii=False) + "===JSON_END===")))]


cl = types.SimpleNamespace(messages=types.SimpleNamespace(batches=FakeBatches()))
os.environ["REPORT_TICKERS"] = "271160"
os.environ.pop("REPORT_EXTRA_STOCKS", None)
ok(GB.submit(cl, "2026-11-19 06:45") is None and not cl.messages.batches.created,
   "REPORT_EXTRA_STOCKS 가 없으면 시세 자료에 없는 종목은 주문하지 않는다(다른 작업은 그대로)")
os.environ["REPORT_EXTRA_STOCKS"] = "ipo"
bid = GB.submit(cl, "2026-11-19 06:45")
reqs = cl.messages.batches.created[-1] if cl.messages.batches.created else []
ok(bid == "msgbatch_IPO1" and [r["custom_id"] for r in reqs] == ["271160"]
   and "상장일(매매개시일): 2026년 11월 20일" in reqs[0]["params"]["messages"][0]["content"],
   "상장 예정 종목을 공모 판 지시문으로 주문한다", str([r["custom_id"] for r in reqs]))
stt = json.loads(GB.STATE_JS.read_text(encoding="utf-8"))
ok(stt.get("pending") and stt.get("batch_id") == "msgbatch_IPO1", "자기 상태 파일(BATCH_STATE_FILE)에 주문을 적는다", GB.STATE_JS.name)
GB.collect(cl, "2026-11-19 07:05")
w = written.get("271160") or {}
ok(w.get("name") == "하나에어로" and w.get("market") == "코스닥" and w.get("sector") == "항공·방산"
   and w.get("ipo") == {"list_date": "2026-11-20", "offer_price": 5700, "shares": 17729964},
   "저장한 리포트에 이름 · 시장 · 업종과 공모 정보(ipo)를 단다", json.dumps({k: w.get(k) for k in ("name", "market", "ipo")}, ensure_ascii=False))
os.environ.pop("REPORT_TICKERS", None)
os.environ.pop("REPORT_EXTRA_STOCKS", None)
src = (SCRIPTS / "generate_reports_batch.py").read_text(encoding="utf-8")
ok('os.getenv("BATCH_STATE_FILE"' in src and '"data/batch_state.json"' in src, "상태 파일 기본값은 그대로(data/batch_state.json)")

print("⑧ 정리 · 색인 · 사이트맵 · 종목 페이지 색인")
import importlib                                   # noqa: E402
G2 = importlib.reload(importlib.import_module("generate_reports"))   # 위에서 바꾼 write_reports 를 되돌린 진짜
WR = TMP / "wr"
(WR / "data" / "reports").mkdir(parents=True)
(WR / "data" / "reports_v2").mkdir()
G2.REPORTS_DIR = WR / "data" / "reports"
G2.REPORTS_INDEX_JS = WR / "data" / "reports-index.js"
G2.REPORTS_JS = WR / "data" / "reports.js"
G2.log = lambda *a, **k: None
universe = [f"{100000 + i:06d}" for i in range(2000)]
G2.load_stocks = lambda: {"stocks": [{"ticker": t} for t in universe], "dataDate": "20261118"}
reps = {universe[0]: {"title": {"ko": "상장"}, "reportDate": "2026-11-18"},
        "271160": {"title": {"ko": "공모주"}, "reportDate": "2026-11-19"},
        "999990": {"title": {"ko": "상장 폐지"}, "reportDate": "2026-09-01"}}
cwd = os.getcwd()
os.chdir(WR)                                       # write_reports 는 data/reports_v2 를 지금 폴더에서 읽는다
try:
    G2.write_reports(dict(reps), "claude-haiku-5-5", "2026-11-19 07:05")
finally:
    os.chdir(cwd)
files = sorted(p.stem for p in (WR / "data" / "reports").glob("*.json"))
idx = json.loads(G2.REPORTS_INDEX_JS.read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
ok(files == sorted([universe[0], "271160"]), "리포트 정리가 상장 예정 종목 파일은 지키고 상장 폐지 종목은 지운다", str(files))
ok(sorted(idx["reports"]) == sorted([universe[0], "271160"]) and idx["stockCount"] == 2000,
   "목록 색인에 상장 예정 종목을 남긴다(종목 수 stockCount 는 시세 자료 그대로)", str(sorted(idx["reports"])))

# _reindex.py — 표준 라이브러리만 쓰는 독립 스크립트라 임시 저장소에 옮겨 돌린다
RX = TMP / "rx"
(RX / "scripts").mkdir(parents=True)
(RX / "data" / "reports_v2").mkdir(parents=True)
for f in ("_reindex.py", "ipo_listings.py"):
    shutil.copy(SCRIPTS / f, RX / "scripts" / f)
(RX / "data" / "stocks.js").write_text("window.KOS_LIVE_DATA = " + json.dumps({"stocks": [{"ticker": "005930"}]}) + ";\n", encoding="utf-8")
(RX / "data" / "reports-index.js").write_text("window.KOS_REPORTS = " + json.dumps(
    {"reports": {"005930": {"title": "a"}, "271160": {"title": "b"}, "999990": {"title": "c"}}}) + ";\n", encoding="utf-8")
lst = {"updated": "", "stocks": {"271160": {"name": "하나에어로", "list_date": (datetime.date.today() + datetime.timedelta(days=1)).isoformat()}}}
(RX / "data" / "ipo.json").write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
subprocess.run([sys.executable, str(RX / "scripts" / "_reindex.py")], capture_output=True, text=True, check=False)
rx = json.loads((RX / "data" / "reports-index.js").read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
ok(sorted(rx["reports"]) == ["005930", "271160"], "워치독 색인 동기화(_reindex)도 상장 예정 종목을 남긴다", str(sorted(rx["reports"])))
lst["stocks"]["271160"]["list_date"] = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
(RX / "data" / "ipo.json").write_text(json.dumps(lst, ensure_ascii=False), encoding="utf-8")
subprocess.run([sys.executable, str(RX / "scripts" / "_reindex.py")], capture_output=True, text=True, check=False)
rx = json.loads((RX / "data" / "reports-index.js").read_text(encoding="utf-8").split("=", 1)[1].strip().rstrip(";"))
ok(sorted(rx["reports"]) == ["005930"], "창이 지나도 시세 자료에 없으면 원래대로 정리한다(상장이 미뤄진 경우)", str(sorted(rx["reports"])))

# 사이트맵 · 종목 페이지 색인
import generate_sitemap as GS                      # noqa: E402
SM = TMP / "sm"
for sub in ("data", "stock", "en/stock"):
    (SM / sub).mkdir(parents=True, exist_ok=True)
(SM / "data" / "stocks.js").write_text("window.KOS_LIVE_DATA = " + json.dumps({"dataDate": "20261118", "stocks": [{"ticker": "005930"}]}) + ";\n",
                                       encoding="utf-8")
for t in ("005930", "271160", "999990"):
    (SM / "stock" / f"{t}.html").write_text("x", encoding="utf-8")
    (SM / "en" / "stock" / f"{t}.html").write_text("x", encoding="utf-8")
GS.ROOT = SM
L.IPO_JSON.write_text(json.dumps({"updated": "", "stocks": {"271160": {"name": "하나에어로", "list_date": (
    datetime.date.today() + datetime.timedelta(days=1)).isoformat()}}}, ensure_ascii=False), encoding="utf-8")
L.today_kst = lambda: datetime.date.today()
GS.main()
sm = (SM / "sitemap.xml").read_text(encoding="utf-8")
ok("/stock/271160.html" in sm and "/en/stock/271160.html" in sm and "/stock/999990.html" not in sm,
   "사이트맵에 상장 예정 종목 페이지(한국어 · 영어)를 올린다 · 상장 폐지 종목은 그대로 뺀다")
import build_stock_static as BS                    # noqa: E402
BS.S.load_data = lambda: {"stocks": {"005930": {}}, "v1": set(), "v2": set(), "dataDate": "20261118", "val": {}}
ok(BS.listed() == {"005930", "271160"}, "종목 페이지 색인(listed) — 상장 예정 종목은 noindex 를 붙이지 않는다", str(sorted(BS.listed())))

print("⑨ 작업 파일")
import yaml                                         # noqa: E402
WF = REPO / ".github" / "workflows"
wf = yaml.safe_load((WF / "ipo_reports.yml").read_text(encoding="utf-8"))
on = wf.get(True) or wf.get("on")
steps = wf["jobs"]["ipo"]["steps"]
gen = next((s for s in steps if "generate_reports_batch.py" in (s.get("run") or "")), {})
genv = gen.get("env") or {}
ok(wf["concurrency"]["group"] != "kos-data", "공용 실행 순서(kos-data) 밖 — 실적 철 공시 트리거에 밀려 취소되지 않게", wf["concurrency"]["group"])
ok("workflow_dispatch" in on and "schedule" in on, "손 · 브리핑 · 예약으로 돈다")
ok(genv.get("REPORT_EXTRA_STOCKS") == "ipo" and genv.get("BATCH_STATE_FILE") == "data/ipo_batch_state.json"
   and genv.get("REPORT_MODEL") == "claude-haiku-5-5" and "generate_reports_batch.py auto" in gen.get("run", ""),
   "상장 예정 종목 · 자기 상태 파일 · 하이쿠 · 배치(옛 형식 생성기)", str({k: genv.get(k) for k in ("REPORT_EXTRA_STOCKS", "BATCH_STATE_FILE")}))
runs = "\n".join(s.get("run") or "" for s in steps)
ok("bash scripts/push_main.sh" in runs and "git push" not in runs, "올리기는 공용 단계(push_main.sh)")
ok("reports_watchdog.yml -f sync_only=true" in runs and any("github-actions[bot]" in str(s.get("if", "")) for s in steps),
   "브리핑이 GITHUB_TOKEN 으로 부른 실행은 워치독(정리만)을 직접 부른다")
ok("git add -A" not in runs and "data/ipo.json" in runs, "이 작업이 쓴 파일만 골라 올린다(같이 도는 작업과 겹치지 않게)")
mb = yaml.safe_load((WF / "morning_brief.yml").read_text(encoding="utf-8"))
mbs = mb["jobs"]["brief"]["steps"]
wake = next((i for i, s in enumerate(mbs) if "ipo_reports.yml" in (s.get("run") or "")), None)
gate = next((i for i, s in enumerate(mbs) if s.get("id") == "gate"), None)
ok(wake is not None and gate is not None and wake == gate + 1 and mbs[wake].get("continue-on-error") is True
   and "open == 'true'" in str(mbs[wake].get("if")) and (mb.get("permissions") or {}).get("actions") == "write",
   "모닝 브리핑이 개장일에 맨 앞에서 깨운다(실패해도 브리핑은 그대로 · actions 쓰기 권한)")
wd = yaml.safe_load((WF / "reports_watchdog.yml").read_text(encoding="utf-8"))
ok(wf["name"] in ((wd.get(True) or wd.get("on"))["workflow_run"]["workflows"]), "워치독이 예약 실행 뒤에 따라 돈다(이름으로 잇는다)", wf["name"])

print("⑩ 네이버 알림")
import naver_indexnow as N                          # noqa: E402
sent = []
N.send = lambda urls, endpoint=None, timeout=60: (sent.append(list(urls)) or [(len(urls), 200)])
N.key_ok = lambda root=None: True
L.IPO_JSON.write_text(json.dumps({"updated": "", "stocks": {
    "271160": {"name": "하나에어로", "list_date": (datetime.date.today() + datetime.timedelta(days=1)).isoformat()},
    "222220": {"name": "내일상장", "list_date": (datetime.date.today() + datetime.timedelta(days=2)).isoformat()}}}, ensure_ascii=False),
    encoding="utf-8")
(TMP / "data" / "reports" / "271160.json").write_text("{}", encoding="utf-8")
R.page_live = lambda url, timeout=20: "271160" in url
R.time.sleep = lambda *_: None
rc = R.cmd_ping(wait_sec=0)
lst = L.load()["stocks"]
ok(rc == 0 and sent == [["https://kosai.kr/stock/271160.html", "https://kosai.kr/en/stock/271160.html"]]
   and lst["271160"].get("pinged") and not lst["222220"].get("pinged"),
   "리포트가 있고 페이지가 열린 종목만 한국어 · 영어 주소를 알린다", str(sent))
sent.clear()
R.cmd_ping(wait_sec=0)
ok(sent == [], "이미 알린 종목은 다시 보내지 않는다")

shutil.rmtree(TMP, ignore_errors=True)
print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
