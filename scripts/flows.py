#!/usr/bin/env python3
"""투자자별 순매수 — '외국인이 3조 순매수했다'.

왜 네이버인가. 원래 pykrx 로 받았는데 KRX 가 GitHub Actions 아이피를
403 으로 막는다(판정 3차에서 확인). data.krx.co.kr 직접 호출도 같은 403.
네이버 금융은 200 에 한글까지 정상이라 여기서 받는다.

네이버 페이지 구조는 언제든 바뀔 수 있으므로 후보 경로를 여러 개 두고
먼저 되는 것을 쓴다. 그리고 파싱 결과를 스스로 채점한다 — 세 주체
(개인·외국인·기관)의 순매수 합은 0 에 가까워야 한다. 누가 사면 누가
팔았기 때문이다. 이 합이 크게 벗어나면 컬럼을 잘못 읽은 것이므로
값을 버린다. 틀린 숫자를 브리핑에 내보내는 것보다 빠지는 게 낫다.

    python3 scripts/flows.py            # 사람이 읽는 표
    python3 scripts/flows.py --json
"""
import argparse
import datetime
import json
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0 (compatible; KOSAI/1.0)",
      "Referer": "https://finance.naver.com/"}
TIMEOUT = 20
KST = datetime.timezone(datetime.timedelta(hours=9))

# sosok: 01 코스피 · 02 코스닥
CANDIDATES = [
    ("investorDealTrendDay", "https://finance.naver.com/sise/investorDealTrendDay.naver?sosok={sosok}"),
    ("investorDealTrendDay(no ext)", "https://finance.naver.com/sise/investorDealTrendDay.nhn?sosok={sosok}"),
    ("sise_index", "https://finance.naver.com/sise/sise_index.naver?code={code}"),
]

# 합이 0 에서 이 비율 이상 벗어나면 파싱을 잘못한 것으로 본다.
# (기타법인·국가 등 소수 주체가 빠지므로 완전히 0 은 아니다)
SUM_TOLERANCE = 0.35


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def _num(s):
    """'3,038,7xx' / '-1,234' / '+12' → int. 못 읽으면 None."""
    if s is None:
        return None
    t = re.sub(r"[^\d\-+.]", "", str(s).replace("−", "-"))
    if t in ("", "-", "+", "."):
        return None
    try:
        return int(round(float(t)))
    except ValueError:
        return None


def _fetch(url):
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    # 네이버 금융은 EUC-KR. 잘못 잡으면 한글이 깨지고 '외국인'을 못 찾는다.
    r.encoding = r.apparent_encoding if "charset" in (r.headers.get("content-type") or "") else "euc-kr"
    return r.text


def _rows_from_table(html):
    """일별 투자자 매매동향 표에서 (날짜, {주체: 값}) 목록을 뽑는다.

    표 구조에 의존하지 않고, '날짜 + 숫자 여러 개' 형태의 행을 찾는다.
    헤더에서 주체 순서를 읽어 값과 짝을 맞춘다.
    """
    # 헤더에서 주체 순서 확인
    heads = re.findall(r"<th[^>]*>(.*?)</th>", html, re.S)
    labels = [re.sub(r"<[^>]+>|\s", "", h) for h in heads]
    order = [l for l in labels if l in ("개인", "외국인", "기관계", "기관", "기타법인", "국가")]
    if not order:
        # 헤더를 못 읽으면 네이버의 통상 순서를 가정하되, 아래 합 검증이 걸러 준다.
        order = ["개인", "외국인", "기관계"]

    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 2:
            continue
        m = re.match(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", cells[0])
        if not m:
            continue
        nums = [_num(c) for c in cells[1:]]
        nums = [n for n in nums if n is not None]
        if len(nums) < 3:
            continue
        d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        out.append((d, dict(zip(order, nums))))
    return out


def _score(vals):
    """세 주체 합이 0 에 가까운지. 벗어나면 컬럼을 잘못 읽었다."""
    picks = [v for k, v in vals.items() if k in ("개인", "외국인", "기관계", "기관")]
    if len(picks) < 3:
        return False, "주체 3개를 못 채웠다"
    scale = max(abs(v) for v in picks) or 1
    ratio = abs(sum(picks)) / scale
    return ratio <= SUM_TOLERANCE, f"합/최대 = {ratio:.2f}"


def market(sosok, code):
    """한 시장의 최근 순매수. 단위는 네이버가 주는 대로(백만원) 받아 억원으로 바꾼다."""
    for name, tmpl in CANDIDATES:
        url = tmpl.format(sosok=sosok, code=code)
        try:
            html = _fetch(url)
        except Exception as e:
            log(f"· {name} 요청 실패: {type(e).__name__} {e}")
            continue
        rows = _rows_from_table(html)
        if not rows:
            log(f"· {name} 표를 못 찾았다")
            continue
        rows.sort(key=lambda r: r[0])
        d, vals = rows[-1]
        ok, why = _score(vals)
        if not ok:
            log(f"· {name} 검증 실패({why}) — 버린다")
            continue
        # 백만원 → 억원
        return {
            "source": name,
            "date": d.isoformat(),
            "unit": "억원",
            "check": why,
            "values": {k: round(v / 100) for k, v in vals.items()},
        }
    return None


def collect():
    return {
        "collectedAt": datetime.datetime.now(KST).isoformat(timespec="seconds"),
        "kospi": market("01", "KOSPI"),
        "kosdaq": market("02", "KOSDAQ"),
    }


def summarize(d):
    L = [f"■ 수집 {d['collectedAt']}"]
    for k in ("kospi", "kosdaq"):
        v = d.get(k)
        if not v:
            L.append(f"  {k.upper():7} — 받지 못했다")
            continue
        body = " · ".join(f"{a} {b:+,}억" for a, b in v["values"].items())
        L.append(f"  {k.upper():7} {v['date']}  {body}")
        L.append(f"  {'':7} (출처 {v['source']} · 검증 {v['check']})")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    d = collect()
    print(json.dumps(d, ensure_ascii=False, indent=2) if a.json else summarize(d))
    return 0 if (d["kospi"] or d["kosdaq"]) else 1


if __name__ == "__main__":
    sys.exit(main())
