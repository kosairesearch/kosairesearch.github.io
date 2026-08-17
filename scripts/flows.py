#!/usr/bin/env python3
"""투자자별 순매수 — '외국인이 3조 순매수했다'.

왜 네이버인가. 원래 pykrx 로 받았는데 KRX 가 GitHub Actions 아이피를
403 으로 막는다(판정 3차에서 확인). data.krx.co.kr 직접 호출도 같은 403.

여기까지 알아낸 것
  · finance.naver.com/sise/investorDealTrendDay 는 200 을 주지만 응답이
    1,669바이트뿐이다. 표의 <th> 헤더(날짜·개인·외국인)만 있고 <td> 데이터
    행이 없다 — 껍데기만 주고 숫자는 따로 불러오는 구조다.
  · sise_index_investor 는 404. 내가 주소를 잘못 짚었다.
  · sise_index 는 58KB 를 주지만 그 표는 '주요시세'다.

그래서 이 파일은 HTML 표와 JSON API 를 함께 시도한다. 어느 게 살아 있을지
모르므로 후보를 늘려 두고, 실패하면 응답의 모양을 로그에 남긴다. 추측으로
고치면 왕복만 늘어난다 — 실제로 그래서 한 번 헛돌았다.

지키는 것
  · 파싱 결과를 스스로 채점한다. 개인·외국인·기관 순매수의 합은 0 에
    가까워야 한다(누가 사면 누가 팔았으므로). 벗어나면 컬럼을 잘못 읽은
    것이므로 값을 버린다. 틀린 숫자를 브리핑에 내보내는 것보다 낫다.
  · 단위를 못 정하면 버린다. '3조'와 '3,038억'을 헷갈리면 브리핑이 우습다.

    python3 scripts/flows.py            # 사람이 읽는 표
    python3 scripts/flows.py --json
    FLOWS_DUMP=1 python3 scripts/flows.py   # 실패 시 응답 구조까지
"""
import argparse
import datetime
import json
import os
import re
import sys

import requests

TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))

WEB_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Referer": "https://finance.naver.com/sise/",
    "Accept-Language": "ko-KR,ko;q=0.9",
}
MOB_UA = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile Safari/604.1"),
    "Referer": "https://m.stock.naver.com/",
    "Accept": "application/json",
}

DUMP = os.getenv("FLOWS_DUMP", "1") == "1"
# 순매수 합이 최댓값의 이 비율을 넘으면 오독으로 본다. 기타법인까지 넣으면
# 합은 거의 정확히 0 이 되므로(3차 실측 0.004) 여유를 조여도 된다.
SUM_TOLERANCE = 0.05
ACTORS = ("개인", "외국인", "기관", "기관계", "기타법인", "국가", "기타외국인")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ────────────────────────────── 후보 목록 ──────────────────────────────
# (이름, 종류, URL 틀). 종류가 json 이면 JSON 으로 읽는다.
def candidates(sosok, code, bizdate):
    return [
        ("모바일 API · investorTrend", "json", MOB_UA,
         f"https://m.stock.naver.com/api/index/{code}/investorTrend"),
        ("모바일 API · investors", "json", MOB_UA,
         f"https://m.stock.naver.com/api/index/{code}/investors?pageSize=10"),
        ("모바일 API · price(수급 포함)", "json", MOB_UA,
         f"https://m.stock.naver.com/api/index/{code}/price?pageSize=5"),
        # bizdate 를 붙이면 데이터 행이 채워질 수 있다 — 껍데기만 온 게
        # 파라미터 때문일 가능성이 남아 있다.
        ("investorDealTrendDay(bizdate)", "html", WEB_UA,
         f"https://finance.naver.com/sise/investorDealTrendDay.naver"
         f"?bizdate={bizdate}&sosok={sosok}&page=1"),
        ("investorDealTrend(bizdate)", "html", WEB_UA,
         f"https://finance.naver.com/sise/investorDealTrend.naver"
         f"?bizdate={bizdate}&sosok={sosok}"),
        ("investorDealTrendDay(page)", "html", WEB_UA,
         f"https://finance.naver.com/sise/investorDealTrendDay.naver?sosok={sosok}&page=1"),
        # 이 페이지는 58KB 를 준다. 그 안의 투자자별 매매동향은 하루치 한 줄이라
        # 날짜 칸이 없어서 표 파서로는 안 잡힌다 — 라벨 파서가 노리는 대상이다.
        ("sise_index(라벨)", "html", WEB_UA,
         f"https://finance.naver.com/sise/sise_index.naver?code={code}"),
        ("국내증시 메인(라벨)", "html", WEB_UA,
         "https://finance.naver.com/sise/"),
    ]


# ────────────────────────────── 도구 ──────────────────────────────

def _num(s):
    if s is None:
        return None
    t = re.sub(r"[^\d\-+.]", "", str(s).replace("−", "-"))
    if t in ("", "-", "+", "."):
        return None
    try:
        return int(round(float(t)))
    except ValueError:
        return None


def _date(cell, today=None):
    """'2026.08.14' · '26.08.14' · '08/14' · '20260814' → 날짜. 아니면 None."""
    today = today or datetime.datetime.now(KST).date()
    t = str(cell).strip()
    for pat, conv in (
        (r"^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", lambda g: (int(g[0]), int(g[1]), int(g[2]))),
        (r"^(\d{4})(\d{2})(\d{2})$", lambda g: (int(g[0]), int(g[1]), int(g[2]))),
        (r"^(\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})", lambda g: (2000 + int(g[0]), int(g[1]), int(g[2]))),
    ):
        m = re.match(pat, t)
        if m:
            y, mo, dd = conv(m.groups())
            try:
                return datetime.date(y, mo, dd)
            except ValueError:
                return None
    m = re.match(r"^(\d{1,2})[./](\d{1,2})$", t)
    if m:
        mo, dd = int(m.group(1)), int(m.group(2))
        y = today.year + (1 if (today.month == 12 and mo == 1) else 0)
        try:
            return datetime.date(y, mo, dd)
        except ValueError:
            return None
    return None


def _fetch(url, headers):
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    ctype = (r.headers.get("content-type") or "").lower()
    if "json" in ctype:
        return r.json(), "json", len(r.content)
    # 네이버 금융 웹은 EUC-KR. 잘못 잡으면 '외국인'을 못 찾는다.
    r.encoding = "euc-kr" if "charset=euc-kr" in ctype or "charset" not in ctype else r.encoding
    return r.text, "html", len(r.content)


# ────────────────────────────── HTML 파서 ──────────────────────────────

def _from_html(html):
    """일별 순매수 표. 네이버 실제 구조는 11칸이다.

      날짜 | 개인 | 외국인 | 기관계 | 금융투자 보험 투신 은행 기타금융 연기금등 | 기타법인

    처음에는 헤더에서 아는 이름만 골라 앞에서부터 값과 짝지었다. 그런데
    '기관' 세부 여섯 개가 중간에 끼어 있어서 정렬이 어긋났다 — 3차 실행에서
    금융투자 값(-11,634)이 '기관'이라는 이름을 달고 나왔다. 그래서 이름으로
    맞추지 않고 자리로 맞춘다. 개인·외국인·기관계는 앞에서 1·2·3번째,
    기타법인은 맨 끝이다.
    """
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 4:
            continue
        d = _date(cells[0])
        if d is None:
            continue
        nums = [_num(c) for c in cells[1:]]
        if sum(1 for n in nums if n is not None) < 3:
            continue
        vals = {}
        for i, actor in enumerate(("개인", "외국인", "기관계")):
            if i < len(nums) and nums[i] is not None:
                vals[actor] = nums[i]
        # 기타법인은 맨 끝. 칸이 충분히 많을 때만(세부 항목이 있는 표) 본다.
        if len(nums) >= 8 and nums[-1] is not None:
            vals["기타법인"] = nums[-1]
        if len(vals) < 3:
            continue
        out.append((d, vals))
    return out


def _from_labeled(html, fallback_date):
    """날짜 열이 없고 '외국인 30,387' 처럼 이름 옆에 값만 있는 형태.

    sise_index 페이지는 58KB 를 주는데 그 안의 투자자별 매매동향은 하루치
    한 줄이라 날짜 칸이 없다. 앞선 파서가 '첫 칸이 날짜'를 요구해서 이걸
    통째로 놓쳤다. 여기서는 이름과 바로 뒤 숫자를 짝지어 읽고, 날짜는
    호출자가 준 기준 거래일을 쓴다.
    """
    txt = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    # 태그를 지우되 칸 경계는 남긴다 — 안 그러면 숫자가 붙어 버린다
    flat = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", txt))
    vals = {}
    for actor in ("개인", "외국인", "기관계", "기관"):
        if actor in vals:
            continue
        # 이름 뒤 40자 안에서 첫 숫자를 찾는다. 부호는 +,- 와 △▽ 를 본다.
        for m in re.finditer(re.escape(actor) + r"[^\d\-+△▽]{0,40}([+\-△▽]?[\d,]{3,})", flat):
            raw = m.group(1).replace("△", "+").replace("▽", "-")
            n = _num(raw)
            if n is not None:
                vals[actor] = n
                break
    # '기관계' 와 '기관' 이 둘 다 잡히면 하나만 남긴다
    if "기관계" in vals and "기관" in vals:
        vals.pop("기관")
    if len(vals) < 3:
        return []
    return [(fallback_date, vals)]


# ────────────────────────────── JSON 파서 ──────────────────────────────

# JSON 응답의 키 이름을 우리 주체 이름으로 맞춘다. 네이버는 카멜케이스
# 영문 키를 쓴다(individual/foreigner/institution 계열).
JSON_KEYS = {
    "개인": ("individual", "individualPureBuyQuant", "individualPureBuyAmount",
             "individualNetPurchase", "personal"),
    "외국인": ("foreigner", "foreign", "foreignerPureBuyQuant",
              "foreignerPureBuyAmount", "foreignerNetPurchase"),
    "기관": ("institution", "organization", "institutionPureBuyQuant",
            "institutionPureBuyAmount", "institutionNetPurchase"),
}
JSON_DATE_KEYS = ("localTradedAt", "tradeDate", "bizdate", "date", "dt", "localDate")


def _walk(o, depth=0):
    """중첩된 JSON 에서 딕셔너리를 전부 훑는다. 응답 모양을 모르니 넓게 본다."""
    if depth > 6:
        return
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from _walk(v, depth + 1)
    elif isinstance(o, list):
        for v in o[:60]:
            yield from _walk(v, depth + 1)


def _from_json(obj):
    out = []
    for d in _walk(obj):
        picked, keys_used = {}, []
        for actor, keys in JSON_KEYS.items():
            for k in keys:
                if k in d and _num(d[k]) is not None:
                    picked[actor] = _num(d[k])
                    keys_used.append(k)
                    break
        if len(picked) < 3:
            continue
        when = None
        for dk in JSON_DATE_KEYS:
            if dk in d:
                when = _date(d[dk])
                if when:
                    break
        if when is None:
            continue
        out.append((when, picked, keys_used))
    # (날짜, 값) 형태로 맞춘다
    return [(w, v) for w, v, _ in out], [k for _, _, k in out[:1]]


# ────────────────────────────── 검증 ──────────────────────────────

def _score(vals):
    """순매수 합이 0 에 가까운지. 벗어나면 컬럼을 잘못 읽었다.

    3차 실행에서 이 검증기가 정상 데이터를 죽였다. '기관계'와 '기관'을
    같이 더했기 때문이다 — 기관계는 기관 세부의 합계라서 이중계산이 된다.
    실제 값(개인 -19,820 · 외국인 +30,387 · 기관계 -10,298 · 기타법인 -142)은
    합이 +127 로 거의 0 인데, 이중계산하면 -11,365 가 되어 거부됐다.

    그래서 기관계가 있으면 기관은 쓰지 않고, 기타법인까지 합에 넣는다.
    기타법인을 빼면 그것 자체가 오차로 남아 애먼 값이 걸린다.
    """
    v = dict(vals)
    if "기관계" in v:
        v.pop("기관", None)          # 이중계산 방지
    picks = [x for k, x in v.items()
             if k in ("개인", "외국인", "기관계", "기관", "기타법인", "국가", "기타외국인")]
    if len([k for k in v if k in ("개인", "외국인", "기관계", "기관")]) < 3:
        return False, "주체 3개를 못 채웠다"
    scale = max(abs(x) for x in picks) or 1
    ratio = abs(sum(picks)) / scale
    return ratio <= SUM_TOLERANCE, f"합/최대 {ratio:.3f}"


def _unit(vals):
    """값의 자릿수로 단위를 추정해 억원으로 맞춘다.

    코스피 하루 순매수는 보통 수천억~수조원이다. 억원이면 4~5자리,
    백만원이면 6~7자리, 원이면 12~13자리. 어디에도 안 맞으면 버린다 —
    '3조'와 '3,038억'을 헷갈리면 브리핑이 우스워진다.
    """
    mx = max(abs(v) for v in vals.values()) or 0
    if mx == 0:
        return None, None
    if 1e2 <= mx < 1e6:                 # 이미 억원
        return 1.0, "억원(그대로)"
    if 1e6 <= mx < 1e9:                 # 백만원 → 억원
        return 1 / 100, "백만원→억원"
    if 1e10 <= mx < 1e15:               # 원 → 억원
        return 1 / 1e8, "원→억원"
    return None, f"자릿수 이상(최대 {mx:,})"


# ────────────────────────────── 수집 ──────────────────────────────

def market(sosok, code, bizdate):
    for name, kind, headers, url in candidates(sosok, code, bizdate):
        try:
            body, got, nbytes = _fetch(url, headers)
        except Exception as e:
            log(f"· {name} 요청 실패: {type(e).__name__} {str(e)[:70]}")
            continue

        keys_used = []
        if got == "json" or kind == "json":
            rows, keys_used = _from_json(body if got == "json" else json.loads(body))
        else:
            rows = _from_html(body)
            if not rows:
                # 날짜 열이 없는 형태를 다시 시도한다
                rows = _from_labeled(body, _date(bizdate) or datetime.date.today())
                if rows:
                    keys_used = ["라벨 인접값"]

        if not rows:
            log(f"· {name} 데이터 행 없음 ({nbytes:,}바이트)")
            if DUMP:
                if got == "json":
                    log(f"    JSON 뼈대: {_shape(body)}")
                else:
                    txt = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>", "", body, flags=re.S))
                    j = txt.find("외국인")
                    log(f"    <td> 개수 {txt.count('<td')}")
                    if j >= 0:
                        log(f"    '외국인' 부근: {txt[max(0,j-160):j+260]!r}")
                    else:
                        log(f"    '외국인' 없음 · 앞부분: {txt[:260]!r}")
            continue

        rows.sort(key=lambda r: r[0])
        d, vals = rows[-1]
        ok, why = _score(vals)
        if not ok:
            log(f"· {name} 검증 실패({why}) — 버린다 · 값 {vals}")
            continue
        mul, unit_note = _unit(vals)
        if mul is None:
            log(f"· {name} 단위 판정 실패({unit_note}) — 버린다")
            continue
        return {
            "source": name,
            "date": d.isoformat(),
            "unit": "억원",
            "check": f"{why} · {unit_note}" + (f" · 키 {keys_used[0]}" if keys_used else ""),
            "values": {k: round(v * mul) for k, v in vals.items()},
        }
    return None


def _shape(o, depth=0):
    """JSON 의 뼈대만 보여 준다 — 값이 아니라 키 구조를 알아야 한다."""
    if depth > 3:
        return "…"
    if isinstance(o, dict):
        return "{" + ", ".join(f"{k}:{_shape(v, depth+1)}" for k, v in list(o.items())[:12]) + "}"
    if isinstance(o, list):
        return f"[{len(o)}×{_shape(o[0], depth+1) if o else ''}]"
    return type(o).__name__


def collect(bizdate=None):
    if not bizdate:
        # 직전 거래일. market_data 가 휴장까지 보고 판정해 준다.
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from market_data import open_today
            _, around = open_today()
            bizdate = (around or {}).get("prev", "").replace("-", "")
        except Exception as e:
            log(f"· 직전 거래일 판정 실패: {e}")
        if not bizdate:
            d = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)
            while d.weekday() >= 5:
                d -= datetime.timedelta(days=1)
            bizdate = d.strftime("%Y%m%d")
    return {
        "collectedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "bizdate": bizdate,
        "kospi": market("01", "KOSPI", bizdate),
        "kosdaq": market("02", "KOSDAQ", bizdate),
    }


def summarize(d):
    L = [f"■ 수집 {d['collectedAt']} · 기준 거래일 {d['bizdate']}"]
    for k in ("kospi", "kosdaq"):
        v = d.get(k)
        if not v:
            L.append(f"  {k.upper():7} — 받지 못했다")
            continue
        body = " · ".join(f"{a} {b:+,}억" for a, b in v["values"].items())
        L.append(f"  {k.upper():7} {v['date']}  {body}")
        L.append(f"  {'':7} (출처 {v['source']} · {v['check']})")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--date", help="기준 거래일 YYYYMMDD")
    a = ap.parse_args()
    d = collect(a.date)
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    return 0 if (d["kospi"] or d["kosdaq"]) else 1


if __name__ == "__main__":
    sys.exit(main())
