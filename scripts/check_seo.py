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

#    업종 수도 같은 자리에 있는데 이건 손으로 적혀 있어 실제와 어긋나 있었다
#    (적힌 29 · 실제 30). 이제 stamp_counts.py 가 박아 넣는다.
try:
    import json
    sj = (ROOT / "data" / "sectors.js").read_text(encoding="utf-8")
    want = str(len(json.loads(sj[sj.index("{"):].rstrip().rstrip(";"))["sectors"]))
    m = re.search(r'<b id="lpSecN"[^>]*>([^<]*)</b>', s)
    have = m.group(1).strip() if m else "(없음)"
    check(have == want, "랜딩의 업종 수가 실제와 같음", f"페이지 {have} · 실제 {want}")
except Exception as e:
    check(True, f"랜딩 업종 수 확인 건너뜀 ({e.__class__.__name__})")

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

# 9) 사업자등록번호가 전화번호로 둔갑하지 않는가
#
#    380-25-02019 는 전화번호와 모양이 같아서, 아이폰 사파리가 알아서
#    파란 글씨 링크로 바꾸고 누르면 전화를 건다. 글자를 어떻게 쓰든 막을 수
#    없고 <meta format-detection> 으로만 끈다. 페이지를 새로 만들 때 이
#    한 줄을 빠뜨리면 그 페이지만 다시 그렇게 된다 — 만든 사람은 아이폰으로
#    푸터까지 내려가 보기 전에는 모른다.
need_fd = []
for p_ in list(ROOT.glob("*.html")) + list((ROOT / "staging").glob("*.html")):
    t = p_.read_text(errors="ignore")
    if 'name="viewport"' not in t:      # 넘김용 껍데기 페이지는 푸터가 없다
        continue
    if 'name="format-detection"' not in t:
        need_fd.append(p_.relative_to(ROOT).as_posix())
check(not need_fd, "모든 페이지가 전화번호 자동인식을 꺼 둠", ",".join(need_fd))

# 10) 링크를 걷어낸 자리에 빈 껍데기가 남지 않았는가
#
#     스크리너를 걷어낼 때 <a> 만 지우고 <li> 를 남겼다. 33개 페이지 전부에
#     <li></li> 가 남았고, 푸터의 '업종별' 과 '워치리스트' 사이만 간격이
#     한 칸 더 벌어져 보였다. 눈에는 "여기만 좀 뜨네" 로만 보이는 종류다.
empty = []
for p_ in list(ROOT.glob("*.html")) + list((ROOT / "staging").glob("*.html")):
    t = p_.read_text(errors="ignore")
    for tag in ("li", "ul", "nav"):
        if f"<{tag}></{tag}>" in t:
            empty.append(f"{p_.relative_to(ROOT).as_posix()}:<{tag}>")
check(not empty, "링크를 걷어낸 자리에 빈 껍데기가 없음", ",".join(empty[:6]))

# 11) 화면 문구의 말끝이 한 가지로 통일돼 있는가
#
#     회사가 손님에게 하는 말은 "…하여 주시기 바랍니다" 로 쓴다. 그런데
#     페이지를 새로 만들 때마다 "…해 주세요", "…하시겠어요?" 가 섞여
#     들어왔다. 한 화면 안에서 두 말투가 부딪히면 급하게 만든 티가 난다.
#     실제로 워치리스트 화면 하나에서만 그게 눈에 띄어 205곳을 고쳤다.
#
#     주석은 사람끼리 읽는 글이라 검사에서 뺀다.
#     '…나요?' '…인가요?' 는 일부러 뺀다. 이건 손님이 우리에게 묻는 모양의
#     글이다 — 로그인 화면의 '비밀번호를 잊으셨나요?', 요금 안내의 자주 묻는
#     질문. 손님의 말을 우리가 대신 적어 둔 자리라 격식체로 바꾸면 오히려
#     취조하듯 읽힌다. 우리가 손님에게 묻는 '…할까요?' 는 그대로 잡는다.
CASUAL = re.compile(r"(세요|어요|아요|해요|예요|에요|워요|져요|까요\?)")
# '안녕하세요' 는 격식체 편지의 첫 인사로 쓰는 굳은 말이라 예외로 둔다.
ALLOW = ("안녕하세요",)
def strip_notes(t):
    # 여러 줄 주석은 줄바꿈만 남겨 지운다. 통째로 지우면 아래에서 세는
    # 줄 번호가 밀려서, 엉뚱한 줄을 가리키는 검사 결과가 나온다.
    blank = lambda m: "\n" * m.group(0).count("\n")
    t = re.sub(r"<!--.*?-->", blank, t, flags=re.S)   # HTML 주석
    t = re.sub(r"/\*.*?\*/", blank, t, flags=re.S)    # /* … */
    t = re.sub(r"(?<![:/])//[^\n]*", "", t)           # // …  (https:// 는 남긴다)
    return t

casual = []
targets = (list(ROOT.glob("*.html")) + list(ROOT.glob("*.js"))
           + list((ROOT / "staging").glob("*.html"))
           + list((ROOT / "staging").glob("*.js"))
           + [ROOT / "functions" / "index.js"])
for p_ in targets:
    if not p_.exists():
        continue
    body = strip_notes(p_.read_text(errors="ignore"))
    for ln_no, ln in enumerate(body.split("\n"), 1):
        for a in ALLOW:
            ln = ln.replace(a, "")
        m = CASUAL.search(ln)
        if m:
            casual.append(f"{p_.relative_to(ROOT).as_posix()}:{ln_no}:{m.group(0)}")
check(not casual, "화면 문구가 모두 격식체(…하여 주시기 바랍니다)",
      ", ".join(casual[:6]) + (f" 외 {len(casual)-6}곳" if len(casual) > 6 else ""))

# 12) 없는 창구로 안내하고 있지 않은가
#
#     "환불을 끝까지 처리하지 못했습니다. 고객센터로 문의해 주시기 바랍니다"
#     라고 써 있었다. 우리에게 고객센터는 없다 — 창구는 문의하기 페이지와
#     hello@kosai.kr 둘뿐이다. 돈이 걸린 자리에서 없는 곳을 찾아가라고 하면
#     손님은 갈 데가 없다. 그 화면에서 가장 화가 난 사람이 보는 문장이다.
GHOST = ("고객센터", "콜센터", "상담센터", "상담원", "고객상담실", "ARS")
ghost = []
for p_ in targets:
    if not p_.exists():
        continue
    body = strip_notes(p_.read_text(errors="ignore"))
    for ln_no, ln in enumerate(body.split("\n"), 1):
        for g in GHOST:
            if g in ln:
                ghost.append(f"{p_.relative_to(ROOT).as_posix()}:{ln_no}:{g}")
check(not ghost, "없는 창구(고객센터 등)로 안내하지 않음", ", ".join(ghost[:6]))

# 13) 메뉴 이름이 페이지마다 같은가
#
#     서비스 메뉴는 한 페이지에 세 번 나온다 — 헤더, 햄버거 메뉴, 푸터.
#     그게 33개 페이지에 복사돼 있으니 한 이름을 바꾸면 99자리를 고쳐야 한다.
#     한 자리라도 빠지면 페이지를 옮길 때마다 메뉴 이름이 달라지는데, 만든
#     사람은 자기가 고친 페이지만 보므로 끝까지 모른다.
#
#     실제로 '업종별' → '업종 분석' 로 바꿀 때 겪은 자리다. 이름 자체를
#     박아 두지는 않는다 — 다음에 또 바꿀 테니까. '전부 같은가' 만 본다.
#     메뉴가 있는 세 자리만 본다. 본문에도 같은 곳으로 가는 링크가 있는데
#     ('홈으로 돌아가기', '리포트 둘러보기') 그건 메뉴가 아니라 문장이다.
BLOCKS = (re.compile(r'<div class="nav-links">(.*?)</div>', re.S),
          re.compile(r'<div class="mobile-menu[^"]*"[^>]*>(.*?)</div>', re.S),
          re.compile(r'<h4>서비스</h4>\s*<ul>(.*?)</ul>', re.S))
MENU = re.compile(
    r'<a[^>]+href="(Home\.html|Reports\.html|industry\.html|Watchlist\.html|brief\.html)"[^>]*>([^<]+)</a>')
menus = {}
for p_ in sorted(list(ROOT.glob("*.html")) + list((ROOT / "staging").glob("*.html"))):
    t = p_.read_text(errors="ignore")
    if 'name="viewport"' not in t:          # 넘김용 껍데기 페이지엔 메뉴가 없다
        continue
    # 같은 주소의 링크 글자를 모은다. 값이 둘 이상이면 그 페이지 안에서 이미 갈렸다.
    m = {}
    for blk in BLOCKS:
        for chunk in blk.findall(t):
            for href, text in MENU.findall(chunk):
                m.setdefault(href, set()).add(text.strip())
    if m:
        menus[p_.relative_to(ROOT).as_posix()] = {k: sorted(v) for k, v in m.items()}

split = [f"{p}:{h}={'/'.join(v)}" for p, mm in menus.items() for h, v in mm.items() if len(v) > 1]
check(not split, "한 페이지 안에서 메뉴 이름이 갈리지 않음", ", ".join(split[:4]))

base = next(iter(menus.values()), {})
diff = []
for p, mm in menus.items():
    for h, v in mm.items():
        if h in base and v != base[h]:
            diff.append(f"{p}:{h}={'/'.join(v)}(≠{'/'.join(base[h])})")
check(not diff, f"메뉴 이름이 {len(menus)}개 페이지에서 모두 같음", ", ".join(diff[:4]))


# 12) 랜딩페이지가 자기 이야기를 하고 있는가
#
#     '코사이' 로 네이버를 찾으면 사이트 대표로 About 페이지가 나왔다. 제목·
#     설명·canonical·구조화 데이터·내부 링크는 위 검사들이 이미 다 보고 있었고
#     전부 통과였다. 남은 것은 아무도 안 세던 것 하나였다 — 크롤러가 읽는 글자.
#
#       /            132낱말   ← 큰 제목 한 줄, 소개 한 문장, 숫자 셋이 전부
#       About.html  1457낱말
#
#     검색 엔진에게 '코사이' 를 설명하는 페이지가 About 뿐이었으니 그쪽이
#     대표가 된 것이다. 메타 태그로는 이걸 못 이긴다.
#
#     낱말 수는 대리 지표일 뿐이고 이 숫자를 채우는 것이 목적이 아니다. 다만
#     랜딩이 다시 껍데기로 돌아가면(섹션을 걷어내거나 자바스크립트로 옮기면)
#     여기서 걸린다. 자바스크립트가 그린 글은 세지 않는다 — 네이버 크롤러도
#     그것을 못 읽는 것이 이 문제의 뿌리였다.
def visible(t):
    t = re.sub(r"(?is)<script.*?</script>", " ", t)
    t = re.sub(r"(?is)<style.*?</style>", " ", t)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = t[t.index("<body"):] if "<body" in t else t
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", t)).strip()

#     <main> 안만 센다. 머리 메뉴와 푸터는 어느 페이지나 똑같아서, 그것까지
#     세면 껍데기 페이지도 90낱말쯤은 그냥 나온다.
def main_of(t):
    m = re.search(r"(?is)<main\b.*?</main>", t)
    return visible("<body>" + (m.group(0) if m else t) + "</body>")

lp = (ROOT / "index.html").read_text(errors="ignore")
words = len(main_of(lp).split())
check(words >= 350, "랜딩에 크롤러가 읽을 본문이 있음", f"{words}낱말(350 이상이어야 한다)")
h2 = len(re.findall(r"<h2\b", lp))
check(h2 >= 3, "랜딩 본문이 제목으로 나뉘어 있음", f"h2 {h2}개")
check('"FAQPage"' in lp.replace(" ", ""), "랜딩에 자주 묻는 질문 구조화 데이터")

#     그리고 About 의 글을 그대로 옮겨 오지 않았는지 본다. 같은 글이 두 주소에
#     있으면 둘이 서로의 순위를 갉아먹어, 고치기 전보다 나빠질 수 있다.
ab = main_of((ROOT / "About.html").read_text(errors="ignore"))
lpv = main_of(lp)
def shingles(t, n=8):
    w = t.split()
    return {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
a, b_ = shingles(lpv), shingles(ab)
dup = len(a & b_) / max(1, len(a))
check(dup < 0.10, "랜딩이 About 의 글을 베끼지 않음", f"겹치는 대목 {dup:.1%}")

print(f"통과 {len(ok)} · 실패 {len(fail)}\n")
for m in ok: print("  PASS", m)
for m in fail: print("  FAIL", m)
sys.exit(1 if fail else 0)
