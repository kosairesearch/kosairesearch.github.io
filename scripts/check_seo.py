#!/usr/bin/env python3
"""랜딩페이지가 사이트 대표로 보이는지 검사한다. 실패하면 0이 아닌 값으로 끝난다."""
import re, sys, pathlib, collections
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
ok, fail = [], []
def check(cond, msg, detail=""):
    (ok if cond else fail).append(f"{msg}{(' — ' + detail) if detail else ''}")

pages = sorted(ROOT.glob("*.html"))
sm = (ROOT / "sitemap.xml").read_text()

# 1) 사이트맵
tree = ET.fromstring(sm)
locs = [u[0].text for u in tree]
check(len([l for l in locs if "stock.html?ticker" in l]) == 0,
      "사이트맵에 stock.html?ticker= 없음")
check("https://kosai.kr/" in locs, "사이트맵에 루트(/) 있음")
check(len([l for l in locs if re.search(r"/r/[0-9A-Z]{6}\.html$", l)]) > 2000,
      "사이트맵에 종목 리포트(r/) 있음",
      f"{len([l for l in locs if re.search(r'/r/[0-9A-Z]{6}.html$', l)])}개")
check(len(locs) == len(set(locs)), "사이트맵에 중복 URL 없음")

# 2) 브랜드 로고가 루트를 가리킴
bad_logo = [p.name for p in pages
            if re.search(r'<a class="brand" href="Home\.html"', p.read_text(errors="ignore"))]
check(not bad_logo, "모든 브랜드 로고가 루트(/)를 가리킴", ",".join(bad_logo))

# 3) 루트로 향하는 내부 링크 수
cnt = collections.Counter()
for p in pages + [ROOT / "r/index.html"]:
    if not p.exists(): continue
    for h in re.findall(r'href="([^"]+)"', p.read_text(errors="ignore")):
        if h.startswith(("http", "mailto:", "#", "javascript:")): continue
        h = h.split("#")[0].split("?")[0] or "/"
        if h.endswith((".png", ".jpg", ".svg", ".ico", ".webp")): continue
        cnt[h] += 1
check(cnt["/"] >= 30, "루트로 향하는 내부 링크 30개 이상", f"{cnt['/']}개")
check(cnt["/"] > cnt.get("stock.html", 0), "루트가 stock.html 보다 많이 링크됨",
      f"루트 {cnt['/']} vs stock {cnt.get('stock.html',0)}")

# 4) index.html 직접 링크(루트 URL 분열) 없음
dup = [p.name for p in pages
       if re.search(r'href="(?!/r/)[^"]*\bindex\.html', p.read_text(errors="ignore"))]
check(not dup, "index.html 직접 링크 없음(루트 URL 분열 방지)", ",".join(dup))

# 5) 랜딩페이지 자체
s = (ROOT / "index.html").read_text()
check('<link rel="canonical" href="https://kosai.kr/"' in s, "랜딩 canonical 이 루트")
check("KOSAI" in re.search(r"<title>([^<]*)</title>", s).group(1), "랜딩 title 에 KOSAI")
check(not re.search(r'<meta name="robots"[^>]*noindex', s), "랜딩에 noindex 없음")
check('"@type":"WebSite"' in s.replace(" ", "") or '"WebSite"' in s, "랜딩에 WebSite 구조화 데이터")
check('naver-site-verification' in s, "네이버 사이트 소유확인 메타 있음")

# 6) canonical 이 서로 겹치지 않음(각 페이지가 자기 자신을 가리킴)
# noindex 페이지(옛 주소 리다이렉트 껍데기)는 뺀다. 그쪽은 목적지를
# canonical 로 가리키는 것이 정상이라, 겹쳐도 문제가 아니다.
canon = {}
for p in pages:
    t = p.read_text(errors="ignore")
    if re.search(r'<meta name="robots"[^>]*noindex', t): continue
    m = re.search(r'<link rel="canonical" href="([^"]+)"', t)
    if m: canon.setdefault(m.group(1), []).append(p.name)
clash = {k: v for k, v in canon.items() if len(v) > 1}
check(not clash, "canonical 이 겹치는 페이지 없음", str(clash))

print(f"통과 {len(ok)} · 실패 {len(fail)}\n")
for m in ok: print("  PASS", m)
for m in fail: print("  FAIL", m)
sys.exit(1 if fail else 0)
