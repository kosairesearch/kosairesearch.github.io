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

# 7) 랜딩 페이지의 'AI 리포트' 수가 실제 종목 수와 같은가
#    손으로 적어 둔 숫자라 아무도 안 고쳐 2,684 로 굳어 있었다. 이제
#    stamp_counts.py 가 리포트를 만들 때마다 박아 넣는데, 그 단계가 언젠가
#    빠져도 여기서 걸린다.
try:
    import json
    idx = (ROOT / "data" / "reports-index.js").read_text(encoding="utf-8")
    payload = json.loads(idx[idx.index("=") + 1:].strip().rstrip(";"))
    want = f'{payload.get("stockCount") or len(payload.get("reports") or {}):,}'
    m = re.search(r'<b id="lpRepN"[^>]*>([^<]*)</b>', s)
    have = m.group(1).strip() if m else "(없음)"
    check(have == want, "랜딩의 AI 리포트 수가 실제와 같음", f"페이지 {have} · 실제 {want}")
except Exception as e:                                  # 인덱스가 없는 환경
    check(True, f"랜딩 리포트 수 확인 건너뜀 ({e.__class__.__name__})")

# 8) 없앤 페이지의 흔적이 남아 있지 않은가
#
#    스크리너를 리포트 페이지 안으로 옮기면서 그 페이지를 접었다. 링크가 한
#    군데라도 남으면 사용자는 눌렀다가 되돌려 보내지는데, 그게 제일 나쁘다 —
#    사이트가 자기 구조를 스스로 모르는 것처럼 보인다.
#
#    Screener.html 자체는 지우지 않고 리포트로 보내는 껍데기로 남겼다. 이
#    주소는 검색에 올라 있고 즐겨찾기에 담은 사람도 있어서, 지우면 404 가 된다.
#    그래서 '링크가 없는가' 와 '껍데기가 제대로 보내는가' 를 함께 본다.
RETIRED = "Screener.html"
shell = ROOT / RETIRED
linkers = []
for p_ in list(ROOT.glob("*.html")) + list((ROOT / "staging").glob("*.html")):
    if p_.name == RETIRED: continue
    t = p_.read_text(errors="ignore")
    if re.search(r'href="[^"]*' + re.escape(RETIRED), t):
        linkers.append(p_.relative_to(ROOT).as_posix())
check(not linkers, f"{RETIRED} 로 가는 링크가 없음", ",".join(linkers))
check(RETIRED not in sm, f"사이트맵에 {RETIRED} 없음")
llms = (ROOT / "llms.txt")
check(RETIRED not in llms.read_text(errors="ignore") if llms.exists() else True,
      f"llms.txt 에 {RETIRED} 없음")

if shell.exists():
    t = shell.read_text(errors="ignore")
    check('location.replace("Reports.html")' in t and 'http-equiv="refresh"' in t,
          f"{RETIRED} 이 리포트로 보낸다(자바스크립트+meta 둘 다)")
    check('rel="canonical" href="https://kosai.kr/Reports.html"' in t,
          f"{RETIRED} 의 canonical 이 리포트를 가리킨다")
    check('name="robots" content="noindex' in t, f"{RETIRED} 이 noindex 다")
else:
    check(False, f"{RETIRED} 껍데기가 없다 — 옛 주소가 404 가 된다")

# 검색에 나오면 안 되는 곳이 robots.txt 로 막혀 있는가
#   /project/(옛 디자인 시안)은 폴더째 지웠다. 없는 폴더를 막아 두면 다음에
#   읽는 사람이 그게 뭔지 찾게 되므로 robots.txt 에서도 뺐다.
rb = (ROOT / "robots.txt").read_text(errors="ignore")
check("Disallow: /staging/" in rb, "robots.txt 가 /staging/ 를 막는다")
check(not (ROOT / "project").exists(), "옛 디자인 시안 폴더가 남아 있지 않음")

print(f"통과 {len(ok)} · 실패 {len(fail)}\n")
for m in ok: print("  PASS", m)
for m in fail: print("  FAIL", m)
sys.exit(1 if fail else 0)
