#!/usr/bin/env python3
"""공시 조회(OpenDartReader)가 영문이 섞인 종목코드도 찾게 한다.

OpenDartReader 0.2.x 의 find_corp_code 는 숫자 6자리만 종목코드로 보고, 그 밖의 글은 회사 이름으로 찾는다.
한국거래소가 새로 상장하는 종목에 영문이 섞인 코드('0011A0' · '0126Z0')를 매기면서, 그 종목들의 공시
조회(재무제표 · 회사 개황 · 주식 수)는 전부 '회사를 찾을 수 없음'이 됐다. 리포트 생성기는 그것을 '재무 자료
없음'으로 읽어 새 형식 리포트 대상에서 '생성 불가'로 빼 왔다 — 2026-10-27 확인 때 상장 36개 종목 전부
(액스비스 · 삼성에피스홀딩스 · 에임드바이오 …)가 6월 옛 형식 리포트에 머물러 있었다.

공시 객체는 reader() 로 만든다. 종목코드 꼴(숫자로 시작하는 영숫자 6자리, 영문이 하나라도 섞인 것)이면
회사 목록의 종목코드 칸에서 찾고, 그 밖(숫자 6자리 · 회사 이름 · 고유번호)은 라이브러리의 원래 방식 그대로다.
지키는 검사 scripts/tests/dart_reader_test.py.
"""
import re

CODE = re.compile(r"^[0-9][0-9A-Z]{5}$")


def patch(dart):
    """만들어 둔 OpenDartReader 객체의 find_corp_code 를 바꾼다. 그 객체의 조회(finstate_all · company ·
    report …)는 모두 self.find_corp_code 를 거치므로 한 곳만 바꾸면 된다. 두 번 불러도 한 번 바꾼다."""
    orig = getattr(dart, "find_corp_code", None)
    codes = getattr(dart, "corp_codes", None)
    if getattr(dart, "_kos_alnum", False) or orig is None or codes is None:
        return dart                      # 이미 바꿨거나, 회사 목록이 없는 객체(시험의 가짜 등)
    stock = codes["stock_code"].astype(str).str.strip()

    def find_corp_code(corp):
        c = str(corp or "").strip()
        if CODE.match(c) and not c.isdigit():
            hit = codes[stock == c]
            return None if hit.empty else hit.iloc[0]["corp_code"]
        return orig(corp)

    dart.find_corp_code = find_corp_code
    dart._kos_alnum = True
    return dart


def reader(api_key):
    """OpenDartReader(api_key) 와 같되, 영문이 섞인 종목코드도 찾는다."""
    import OpenDartReader
    return patch(OpenDartReader(api_key))
