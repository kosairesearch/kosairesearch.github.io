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
  ⑪ 증권신고서     요약재무정보(연결 우선 · 단위 · 머리 두 줄 · 연도만 쓴 머리 · 감사의견 · 괄호 음수) · 자금 사용 계획 · 단위 오독은 버린다
  ⑫ 가져오기       정식명으로 회사 찾기 · 요약재무정보가 없는 서류(발행조건확정)는 앞 서류로 · 준비 단계가 리포트를 쓸 종목에만 단다 ·
                   목록 파일에 남고 다시 받지 않는다 · 키가 없거나 실패해도 리포트는 그대로 쓴다
  ⑬ 재료 · 검사    지시문의 [증권신고서 요약재무정보] · 저장한 리포트의 ipo.quant 로 본문 금액을 대조한다 · 정리가 ipo 를 건드리지 않는다
  ⑭ KIND 다시 읽기 403 · 서버 오류면 두 번 더 묻고, 끝내 막히면 실패로 넘긴다
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

sys.path.insert(0, str(HERE))
import ipo_filing as IF                # noqa: E402
import ipo_filing_fixtures as FX       # noqa: E402
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
FIN_HANA = IF.parse_summary(FX.HANA)
FIN_HANA.update({"rcept_no": "20261109000166", "report_nm": "[기재정정]투자설명서", "rcept_dt": "2026-11-09",
                 "funds": IF.parse_funds(FX.HANA_FUNDS)})
ipo["stocks"]["271160"]["filing"] = FIN_HANA
L.save(ipo)
st = L.stock_dict("271160", ipo["stocks"]["271160"])
ok(st["price"] is None and st["mcap"] is None and st["ipo"]["offer_price"] == 5700 and st["ipo"]["list_date"] == "2026-11-20",
   "생성기 종목 꼴 — 시세 칸은 비우고 공모 정보", json.dumps(st["ipo"], ensure_ascii=False)[:160])
p = G.build_prompt(st, "2026-11-19 06:45", "")
ok("상장일(매매개시일): 2026년 11월 20일" in p and "확정 공모가 5,700원[KRW 5,700]" in p and "공모금액 251억원[KRW 25.1 billion]" in p
   and "상장주식수 17,729,964주 · 공모가 기준 시가총액 1,011억원[KRW 101.1 billion]" in p and "대표 주관사 IBK투자증권(주)" in p,
   "공모 판 재료 — 상장일 · 공모가 · 공모금액 · 상장주식수 · 공모가 기준 시가총액 · 주관사")
ok("[신규 상장 종목 — 아래 작성 지침에 더한다]" in p and "현재가" not in p and "거래대금:" not in p and "Hana Aero Dynamics" in p,
   "공모주 지침 · 시세 줄 없음 · 영문명 블록")
ok("[증권신고서 요약재무정보 — 회사가 공모 때 낸 투자설명서(2026년 11월 9일 접수)" in p
   and "- 2025년(K-IFRS · 삼덕회계법인 적정): 매출 333억원[KRW 33.3 billion](전년 대비 3.0% 증가) · 영업이익 49.9억원" in p
   and "- 2026년 상반기(1~6월)(K-IFRS · 현대회계법인 검토): 매출 206억원" in p and "당기순손실 1.2억원[KRW 118 million]" in p
   and "- 2023년(K-GAAP · 현대회계법인 적정)" in p and "회계처리기준이 해마다 다르다" in p and "감사받지 않은 재무제표" in p
   and "공모 자금 사용 계획(확정 공모가 기준): 순수입금 248억원[KRW 24.8 billion] — 시설자금 248억원[KRW 24.8 billion]" in p
   and p.index("[증권신고서 요약재무정보") < p.index("[신규 상장 종목 — 아래 작성 지침에 더한다]"),
   "증권신고서 재무 블록 — 연도별 실적 · 전년 대비 · 회계처리기준 · 감사의견 · 상반기 누적 · 자금 사용 계획 · 지침보다 앞")
ok("실적은 위 [증권신고서 요약재무정보]가 있으면 그 금액 · 증감을 그대로 쓴다" in G.IPO_RULES
   and "경쟁률 · 확약 비율 · 유통 물량은 검색으로 확인된 값만 쓴다" in G.IPO_RULES, "공모주 지침 — 실적은 증권신고서 값 그대로")
p_nf = G.build_prompt(L.stock_dict("271160", {k: v for k, v in ipo["stocks"]["271160"].items() if k != "filing"}), "2026-11-19 06:45", "")
ok("[증권신고서 요약재무정보 —" not in p_nf and "확정 공모가 5,700원" in p_nf, "증권신고서 재무가 없으면 블록 없이 전처럼")
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
wi = dict(w.get("ipo") or {})
wq = wi.pop("quant", None)
ok(w.get("name") == "하나에어로" and w.get("market") == "코스닥" and w.get("sector") == "항공·방산"
   and wi == {"list_date": "2026-11-20", "offer_price": 5700, "shares": 17729964},
   "저장한 리포트에 이름 · 시장 · 업종과 공모 정보(ipo)를 단다", json.dumps({k: w.get(k) for k in ("name", "market")}, ensure_ascii=False))
ok(isinstance(wq, dict) and [a["year"] for a in wq["annual"]] == [2023, 2024, 2025] and wq["annual"][2]["rev"] == 33286338798
   and wq["annual"][2]["np"] == 2420372481 and "fy_end_month" not in wq,
   "증권신고서 연간 실적을 금액 검사의 공시 값(ipo.quant)으로 남긴다", json.dumps(wq, ensure_ascii=False)[:160])
ok("[증권신고서 요약재무정보" in reqs[0]["params"]["messages"][0]["content"], "주문한 지시문에 증권신고서 재무 블록이 들어간다")
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
print("⑪ 증권신고서 · 투자설명서 읽기")


def per(fin, end):
    return next((x for x in (fin or {}).get("periods", []) if x["end"] == end), {})


f = IF.parse_summary(FX.HANA)
ok(f and [x["end"] for x in f["periods"]] == ["2023-12", "2024-12", "2025-12", "2026-06"] and f["fy_end_month"] == 12
   and f["basis"] == "", "하나에어로 — 네 기간 · 결산월 · 연결 표시가 없는 표", str(f and [x["end"] for x in f["periods"]]))
ok(per(f, "2025-12") == {"end": "2025-12", "months": 12, "std": "K-IFRS", "audit": "삼덕회계법인(적정)", "rev": 33286338798,
                         "op": 4988489314, "np": 2420372481, "assets": 61427175401, "liab": 46269336195, "equity": 15157839206},
   "재무상태 머리('제19기(2025년12월말)')와 손익 머리('(2025.1.1.~2025.12.31.)')를 끝 시점으로 잇는다", json.dumps(per(f, "2025-12"), ensure_ascii=False))
ok(per(f, "2026-06").get("months") == 6 and per(f, "2026-06").get("np") == -117833618 and per(f, "2025-12").get("np") > 0,
   "'당기순손실' 줄도 부호는 괄호로 — 손실은 음수, 이익(괄호 없음)은 양수 · 반기는 6개월 누적")
ok(per(f, "2024-12").get("audit") == "감사받지 아니한재무제표" and per(f, "2023-12").get("std") == "K-GAAP"
   and "rev" not in {k for k, v in per(f, "2023-12").items() if v == 1}, "감사의견 · 회계처리기준을 해마다 남긴다 · 다음 제목의 표는 읽지 않는다")
u = IF.parse_summary(FX.UCAST)
ok(u and u["basis"] == "연결" and per(u, "2025-12").get("op") == -1826074490 and per(u, "2025-12").get("audit") == "도원회계법인(적정)"
   and per(u, "2023-12").get("audit") == "감사받지 아니함" and "rev" not in per(u, "2023-12") and per(u, "2025-12").get("equity") == -4950236136,
   "유캐스트 — 연결 · 별도가 따로면 연결 · 감사인과 감사의견이 다른 줄 · '-'는 빈 칸 · 법인세차감전순이익은 순이익이 아니다",
   json.dumps(per(u, "2025-12"), ensure_ascii=False)[:200])
m = IF.parse_summary(FX.MBD)
ok(m and m["basis"] == "" and [x["end"] for x in m["periods"]] == ["2023-12", "2024-12", "2025-12", "2026-06"]
   and per(m, "2026-06").get("assets") == 17857104132 and per(m, "2026-06").get("np") == 11197798264
   and per(m, "2025-12").get("audit") == "삼일회계법인(적정)",
   "엠비디 — 연결 '해당사항 없음' · 연도만 쓴 머리('제11기(2025년)' · '제12기(2026년 반기)')도 손익 머리와 잇는다",
   str(m and [x["end"] for x in m["periods"]]))
e_ = IF.parse_summary(FX.EST)
ok(e_ and e_["basis"] == "연결" and per(e_, "2025-12").get("rev") == 35418086000 and per(e_, "2025-12").get("np_owner") == 1952923000
   and per(e_, "2026-06").get("assets") == 70981255000,
   "이에스티 — 천원 단위 · 이름 칸 없는 둘째 머리 줄 · '- 지배회사지분순이익'", json.dumps(per(e_, "2025-12"), ensure_ascii=False)[:200])
o_ = IF.parse_summary(FX.OPTO)
ok(o_ and o_["basis"] == "연결" and per(o_, "2025-12").get("rev") == 25602568905 and per(o_, "2026-06").get("months") == 6
   and "equity_owner" not in per(o_, "2025-12"), "옵토닉스 — '2026년도 반기' · 둘째 줄 '(제23기 반기)' · 비지배지분은 지배 지분이 아니다")
lb = IF.parse_summary(FX.LABLUP)
ok(lb and per(lb, "2025-12").get("rev") == 6718495122 and per(lb, "2025-12").get("equity_owner") == -2269211587
   and per(lb, "2024-12").get("std") == "K-IFRS", "래블업 — 영업수익 · 자본총계 앞의 [지배회사지분] · 각주 '(주1)'을 걷는다")
dw = IF.parse_summary(FX.DONGWON)
ok(dw and per(dw, "2025-12").get("rev") == 92254987000 and per(dw, "2024-12").get("audit") == "신한회계법인(적정)"
   and per(dw, "2026-06").get("months") == 6, "동원파츠 — 천원 · '2026년 반기(제30기)' · '사업연도' 머리")
ok(IF.parse_summary(FX.SHORT) is None, "요약재무정보가 없는 서류(발행조건확정)는 None")
ok(IF.parse_summary(FX.EST.replace("(단위 : 천원)", "")) is None, "단위를 못 찾아 천원 표를 원으로 읽으면(자산총계 10억원 미만) 버린다")
bad = FX.HANA.replace("<TD ALIGN=\"RIGHT\">46,269,336,195</TD>", "<TD ALIGN=\"RIGHT\">6,269,336,195</TD>")
ok(bad != FX.HANA and IF.parse_summary(bad) is None, "자산 = 부채 + 자본이 맞지 않으면(열 어긋남) 버린다")
ok(IF.parse_funds(FX.HANA_FUNDS) == {"uses": [{"use": "시설자금", "amt": 24814000000}], "net": 24814218640},
   "자금 사용 계획 — 따로 된 단위 표(백만원) · 순수입금(원) · 계는 뺀다", str(IF.parse_funds(FX.HANA_FUNDS)))
ok(IF.parse_funds(FX.NEXI_FUNDS) == {"uses": [{"use": "운영자금", "amt": 39427580000}], "net": 39427580000}
   and IF.parse_funds(FX.BARO_FUNDS)["uses"] == [{"use": "운영자금", "amt": 14889000000}, {"use": "타법인증권취득자금", "amt": 14000000000}],
   "원 단위 사용 계획 · 두 항목")
ok(IF.parse_funds(FX.BARO_FUNDS.replace("(단위 : 백만원)", "(단위 : 원)")).get("uses", [{}])[0].get("amt") == 14889000000,
   "적힌 단위가 순수입금과 맞지 않으면 순수입금과 합계로 정한다(앞 표의 단위를 이어 읽은 경우)")
NO_NET = FX.BARO_FUNDS.replace("순수입금 [(1) + (2) - (3)]", "기타 항목").replace("(단위 : 백만원)", "")
ok(IF.parse_funds(NO_NET) == {}, "순수입금도 없고 단위로 읽은 합계가 1억원 미만이면 버린다", str(IF.parse_funds(NO_NET)))
ok(IF.parse_funds(FX.BARO_FUNDS.replace("(단위 : 백만원)", "")).get("uses", [{}])[0].get("amt") == 14889000000,
   "단위를 못 찾으면 순수입금과 합계로 정한다")

print("⑫ 가져오기 · 준비 단계")
import io                              # noqa: E402
import zipfile                         # noqa: E402
CODES = [{"corp_code": "99999999", "corp_name": "하나에어로", "stock_code": ""},
         {"corp_code": "01025617", "corp_name": "하나에어로다이내믹스", "stock_code": " "}]
ok(IF.find_corp(CODES, "(주)하나에어로다이내믹스", "하나에어로") == ["01025617"]
   and IF.find_corp(CODES, "주식회사 없는회사", "하나에어로") == ["99999999"] and IF.find_corp(CODES, "", "") == [],
   "정식명('(주)' · '주식회사'를 뗀 이름)부터, 없으면 약명으로")
LIST = [{"rcept_no": "20261109000163", "report_nm": "[발행조건확정]증권신고서(지분증권)", "rcept_dt": "20261109"},
        {"rcept_no": "20261109000166", "report_nm": "[기재정정]투자설명서 ", "rcept_dt": "20261109"},
        {"rcept_no": "20261116001887", "report_nm": "분기보고서 (2026.09)", "rcept_dt": "20261116"},
        {"rcept_no": "20260921000405", "report_nm": "증권신고서(지분증권)", "rcept_dt": "20260921"}]
DOCS = {"20261109000166": FX.SHORT, "20261109000163": FX.HANA + FX.HANA_FUNDS, "20260921000405": FX.HANA}
asked = []


def fake_get(url, params=None, timeout=None):
    asked.append((url.rsplit("/", 1)[-1], (params or {}).get("rcept_no") or (params or {}).get("corp_code")))
    if url.endswith("/list.json"):
        return types.SimpleNamespace(json=lambda: {"status": "000", "list": LIST if params["corp_code"] == "01025617" else []})
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{params['rcept_no']}.xml", DOCS[params["rcept_no"]].encode("utf-8"))
        z.writestr(f"{params['rcept_no']}_00760.xml", ("<P>첨부</P>" * 99999).encode("utf-8"))
    return types.SimpleNamespace(content=buf.getvalue())


notes = []
fin = IF.collect("KEY", CODES, "(주)하나에어로다이내믹스", "하나에어로", today=datetime.date(2026, 11, 18), get=fake_get, log=notes.append)
ok(fin and fin["rcept_no"] == "20261109000163" and fin["rcept_dt"] == "2026-11-09" and fin["report_nm"] == "[발행조건확정]증권신고서(지분증권)"
   and per(fin, "2025-12").get("rev") == 33286338798 and fin["funds"]["net"] == 24814218640,
   "가장 최근 서류부터 — 요약재무정보가 없는 서류(정정 대비표뿐)는 건너뛰고 앞 서류로 · 본문 파일(접수번호.xml)을 읽는다",
   str(fin and fin.get("rcept_no")))
ok([a for a in asked if a[0] == "document.xml"] == [("document.xml", "20261109000166"), ("document.xml", "20261109000163")]
   and any("요약재무정보를 읽지 못함" in n for n in notes), "정기보고서는 받지 않는다 · 건너뛴 사유를 남긴다", str(asked))
notes.clear()
ok(IF.collect("KEY", CODES, "(주)없는회사", "없는회사", get=fake_get, log=notes.append) is None
   and any("회사 목록에" in n for n in notes), "회사를 못 찾으면 None(사유를 남긴다)")
ok(IF.collect("KEY", [{"corp_code": "77777777", "corp_name": "새회사"}], "새회사", "", get=fake_get, log=notes.append) is None
   and any("공모 서류 없음" in n for n in notes), "공모 서류가 없으면 None")

ipo2 = {"stocks": {"271160": {"name": "하나에어로", "full_name": "(주)하나에어로다이내믹스", "list_date": "2026-11-20"},
                   "222220": {"name": "내일상장", "full_name": "(주)내일상장", "list_date": "2026-11-21", "filing": {"periods": [1]}}}}
got = []
real_collect = IF.collect
IF.collect = lambda key, codes, full, name, **k: (got.append((key, full)) or dict(FIN_HANA))
logs = []
R_log = R.log
R.log = lambda *a: logs.append(" ".join(str(x) for x in a))
ok(R.attach_filing(ipo2, ["271160", "222220"], key="KEY", codes=CODES) == 1 and got == [("KEY", "(주)하나에어로다이내믹스")]
   and ipo2["stocks"]["271160"]["filing"]["rcept_no"] == "20261109000166" and ipo2["stocks"]["222220"]["filing"] == {"periods": [1]},
   "준비 단계 — 리포트를 쓸 종목 가운데 재무가 없는 종목만 받아 목록 파일 항목에 단다", str(got))
got.clear()
ok(R.attach_filing(ipo2, ["271160"], key="KEY", codes=CODES) == 0 and not got, "이미 단 종목은 다시 받지 않는다")
ok(R.attach_filing({"stocks": {"333330": {"name": "x"}}}, ["333330"], key="", codes=CODES) == 0 and any("DART 키" in x for x in logs),
   "키가 없으면 받지 않고 알린다(리포트는 재무 없이 쓴다)")
IF.collect = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
ok(R.attach_filing({"stocks": {"333330": {"name": "x"}}}, ["333330"], key="KEY", codes=CODES) == 0, "읽다 멈춰도 준비 단계는 계속한다")
IF.collect = real_collect
R.log = R_log
merged = {"stocks": {"271160": dict(ipo2["stocks"]["271160"], published="2026-11-19 03:11")}}
R.merge(merged, {"271160": {"name": "하나에어로", "list_date": "2026-11-20", "shares": 17729964}}, "2026-11-19 06:45")
ok(merged["stocks"]["271160"].get("filing", {}).get("rcept_no") == "20261109000166" and merged["stocks"]["271160"].get("published"),
   "안내를 다시 합쳐도 증권신고서 재무(filing)를 지킨다")
ok(L.stock_dict("271160", merged["stocks"]["271160"])["ipo"]["filing"]["rcept_no"] == "20261109000166"
   and "filing" not in L.stock_dict("271160", {"name": "x", "filing": {}})["ipo"], "종목 꼴에 재무를 넘긴다(빈 값은 뺀다)")
wf = (REPO / ".github" / "workflows" / "ipo_reports.yml").read_text(encoding="utf-8")
prep = wf.split("- name: 1)")[1].split("- name: 2)")[0]
ok("DART_API_KEY: ${{ secrets.DART_API_KEY }}" in prep, "준비 단계에 DART 키를 준다")

print("⑬ 재료 · 검사")
import check_report_text as C        # noqa: E402
q = IF.quant(FIN_HANA)
rep = {"ticker": "271160", "name": "하나에어로", "ipo": {"list_date": "2026-11-20", "offer_price": 5700, "quant": q},
       "recent": {"ko": "2025년 매출은 330억원이다.", "en": "2025 revenue was KRW 33.3 billion."}}
hits = C.amount_hits(rep)
ok(len(hits) == 1 and hits[0]["rule"] == "amount" and "333억원" in hits[0]["why"],
   "본문 금액을 증권신고서 연간 실적과 대조한다(공시 값 333억원)", str([h["why"] for h in hits]))
rep["recent"]["ko"] = "2025년 매출은 332억 8,600만원, 영업이익은 49억 8,800만원이다."
ok(C.amount_hits(rep) == [], "맞는 금액(더 자세한 표기 포함)은 걸지 않는다")
ok(C.amount_hits(dict(rep, ipo={"list_date": "2026-11-20"})) == [] and C._quant({"quant": {"annual": []}, "ipo": {"quant": q}}) == {"annual": []},
   "증권신고서 값이 없으면 대조하지 않는다 · 리포트 v2 의 quant 가 먼저다")
pre = C.prepare(dict(rep, ipo=json.loads(json.dumps(rep["ipo"]))))
ok(pre["ipo"] == rep["ipo"] and "ipo" in C._NOT_TEXT, "저장 전 정리는 ipo(공모 정보 · 증권신고서 값)를 건드리지 않는다")
q3 = IF.quant(dict(FIN_HANA, fy_end_month=3))
ok(q3.get("fy_end_month") == 3 and IF.quant({"periods": [{"end": "2026-06", "months": 6, "rev": 1}]}) is None and IF.quant(None) is None,
   "결산월이 12월이 아니면 표시 · 누적 기간만 있으면 None")
ok(IF.material_lines(None) == "" and IF.material_lines({"periods": []}) == "", "재무가 없으면 블록 없음")
ok("- 2026년 상반기(1~6월)(K-IFRS · 한울회계법인): 매출" in IF.material_lines(
    {"fy_end_month": 12, "periods": [{"end": "2026-06", "months": 6, "std": "K-IFRS", "audit": "한울회계법인 (-)", "rev": 3021157962}]}),
   "감사의견 칸이 '-'면 감사인 이름만(넥스아이 반기)")
mu = IF.material_lines(dict(IF.parse_summary(FX.UCAST), rcept_dt="2026-11-17", report_nm="[기재정정]투자설명서"))
ok("· 연결 기준 ·" in mu and "자본총계 -49.5억원[KRW -4.95 billion] — 자본총계가 마이너스인 자본잠식 상태" in mu
   and "- 2023년(K-IFRS · 감사받지 아니함): 손익 자료 없음" in mu and "영업손실 18.3억원[KRW 1.83 billion](전년 대비 적자 지속(손실 확대))" in mu,
   "연결 기준 표시 · 자본잠식 · 손익이 빈 해 · 손실 이름과 적자 지속", mu.split("\n")[3][:120])

print("⑭ KIND 다시 읽기")


class FakeSession:
    def __init__(self, codes):
        self.codes, self.headers, self.calls = list(codes), {}, 0

    def request(self, meth, url, timeout=None, **kw):
        self.calls += 1
        code = self.codes.pop(0)
        if isinstance(code, Exception):
            raise code
        return types.SimpleNamespace(status_code=code, content="<html>본문</html>".encode("utf-8"), raise_for_status=lambda: None)


k = R.Kind(session=FakeSession([403, 503, 200]))
k.RETRY_WAITS = (0, 0, 0)
ok(k._get("/x") == "<html>본문</html>" and k.s.calls == 3, "403 · 503 뒤 세 번째에 받는다")
k = R.Kind(session=FakeSession([403, ConnectionError("끊김"), 403]))
k.RETRY_WAITS = (0, 0, 0)
try:
    k._get("/x")
    ok(False, "세 번 모두 막히면 실패로 넘긴다")
except Exception as ex:                                        # noqa: BLE001
    ok("403" in str(ex) and k.s.calls == 3, "세 번 모두 막히면 실패로 넘긴다(준비 단계가 받아 그 실행은 주문하지 않는다)", str(ex))
ok(R.Kind.RETRY_WAITS == (0, 15, 45), "기다림 15초 · 45초")

print(f"\n통과 {passed} · 실패 {failed}")
sys.exit(1 if failed else 0)
