"""랜딩 그림 — 실제 리포트 화면(리포트 절)과 실제 업종 분석 화면(업종 절)을 사용자가 보는 그대로 찍는다.

    python3 scripts/concepts/landing_art.py           # 둘 다
    python3 scripts/concepts/landing_art.py report    # → preview/concepts/landing/img/report-{desk,m1,m2}-{light,dark}.webp
    python3 scripts/concepts/landing_art.py sector    # → preview/concepts/landing/img/sector-{desk,m1,m2}-{light,dark}.webp

  · 사장 2026-10-01: 편집 디자인으로 다시 짠 지면은 "실제 리포트 내용이랑 다르고 내용이 적어 부실해 보인다", 이어서 "이미지 박스를
    없애고 리포트만". 그래서 제품이 그리는 화면(stock_page.render)을 그대로 찍고, 랜딩에서는 회색 그림 자리 없이 화면만 둔다
    (landing.py 의 shot()).
  · 기기마다 그 기기의 화면 — 넓은 화면은 데스크톱 화면 한 장(왼쪽 목차의 13개 절이 '차례로 정리합니다'를 그대로 보여 준다),
    820px 이하(리포트도 한 열로 보이는 폭)는 휴대폰 화면 두 장(01 리포트 개요 · 03 실적 추이).
  · 절이 머리 바로 아래 오게 내린 상태를 찍고 머리 줄(60px)은 덜어 낸다 — 랜딩의 머리와 겹쳐 보이지 않게, 리포트부터.
    종목 머리(이름 · 주가 · 관심종목 단추)는 그보다 위라 찍히지 않는다 — 종목이 주인공이 되지 않게(CLAUDE.md).
  · 종목은 하츠(066130) — 제목이 긍정과 부정을 함께 담고(매출 둔화 속 이익률 개선), 강세 3 · 약세 3, 본문 검사 0건, 증권사 목표주가
    인용 없음. 리포트가 새로 쓰이면 다시 찍는다. 찍기 전에 검사 둘(defects · check)을 돌리고 걸리면 찍지 않는다.
  · 업종 절(사장 2026-10-01 "업종 분석해준다는 걸 이야기 못하는 것 같아 … 히트맵으로 정리해놓는다는 식으로밖에 안 들려" → 실제 업종
    분석 화면, "화학 말고 바이오로")은 미리보기 업종 화면(preview/industry.html?sector=바이오·제약)을 찍는다 — 넓은 화면은 머리(업종
    분석 > 바이오·제약 · 업종 요약)와 목차 · 01 업종 개요가 보이는 데스크톱 화면 한 장, 한 열은 휴대폰 화면 두 장(01 업종 개요 ·
    05 리스크 요인). 머리 아래 수치 줄(시가총액 합계 · 시장 비중 · 종목 수 · 평균 등락률)과 기준 줄은 매일 바뀌는 값이라 가리고
    찍는다 — 리포트 절이 종목 머리를 덜어 낸 것과 같은 이치. 업종 분석 글(data/sectors.js)이 새로 쓰이면 다시 찍는다.
  · Playwright(크로미움)가 있어야 돈다. 랜딩 빌드(landing.py)는 그림 파일만 쓴다.
"""
import functools
import io
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_report_text as CR  # noqa: E402
import stock_page as SP  # noqa: E402

TK = "066130"
SECTOR = "바이오·제약"
OUT = os.path.join(ROOT, "preview", "concepts", "landing", "img")
NAV = 60   # 머리 줄 높이 — 찍은 뒤 덜어 낸다
# 이름: (화면 폭, 높이, 배율, 머리 아래 올 절(None 이면 맨 위 그대로), 그 절의 화면 위 거리, 자를 범위(화면 좌표 x0 · y0 · x1 · y1),
#        저장 폭, 켜져 있어야 할 목차)
SHOTS = {
    "desk": (1280, 1000, 2, "#s01", 92, (56, NAV, 1280, 1000), 1840, "01"),
    "m1": (390, 844, 3, "#s01", 112, (0, NAV, 390, 700), 900, "01"),
    "m2": (390, 844, 3, "#s03", 112, (0, NAV, 390, 700), 900, "03"),
}
# 업종 화면 — 데스크톱은 본문 폭(1056px)에 16px 씩 여유를 둔 범위를 2112px(2배)로 담는다
SECTOR_SHOTS = {
    "desk": (1280, 900, 2, None, 0, (96, 84, 1184, 760), 2112, "01"),
    "m1": (390, 844, 3, None, 0, (0, NAV, 390, 700), 900, "01"),
    "m2": (390, 844, 3, "#s05", 112, (0, NAV, 390, 700), 900, "05"),
}
HIDE = ".stats,.stats-note{display:none!important}"   # 업종 화면의 매일 바뀌는 수치 줄


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def take(br, url, shots, prefix, route=None, css=None):
    """shots 대로 라이트 · 다크를 찍어 prefix-{이름}-{테마}.webp 로 저장한다. 목차 표시가 맞지 않으면 멈춘다"""
    from PIL import Image
    for name, (w, h, dpr, sel, off, box, out_w, want) in shots.items():
        for theme in ("light", "dark"):
            phone = w < 500
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=dpr, reduced_motion="reduce",
                                 is_mobile=phone, has_touch=phone)
            ctx.add_init_script(f"try{{localStorage.setItem('kos-theme','{theme}')}}catch(e){{}}")
            if route:
                ctx.route(*route)
            pg = ctx.new_page()
            pg.goto(url, wait_until="load")
            if css:
                pg.add_style_tag(content=css)
            pg.evaluate("document.fonts.ready.then(()=>1)")
            if sel:
                pg.evaluate("([s,o])=>{const e=document.querySelector(s);scrollTo({top:e.getBoundingClientRect().top+scrollY-o,behavior:'instant'})}",
                            [sel, off])
            pg.wait_for_timeout(700)   # 스크롤에 따라 목차 표시 · 휴대폰 절 단추 줄(머리 안으로 옮겨 붙는다)이 자리를 잡는다
            on = pg.evaluate("[...document.querySelectorAll('.toc a.on,.chips a.on')].map(a=>a.textContent.trim())")
            if not any(t.startswith(want) for t in on):
                sys.exit(f"{prefix} {name} {theme}: 목차 표시가 {want} 가 아니다 — {on}")
            im = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
            ctx.close()
            x0, y0, x1, y1 = box
            im = im.crop((x0 * dpr, y0 * dpr, x1 * dpr, y1 * dpr))
            im = im.resize((out_w, round(im.height * out_w / im.width)), Image.LANCZOS)
            path = os.path.join(OUT, f"{prefix}-{name}-{theme}.webp")
            im.save(path, "WEBP", quality=84, method=6)
            print(f"{os.path.relpath(path, ROOT)} {im.size[0]}×{im.size[1]} {os.path.getsize(path) // 1024}KB")


def report(br, base):
    d = json.load(open(os.path.join(ROOT, "data", "reports_v2", f"{TK}.json"), encoding="utf-8"))
    bad = CR.defects(d) or CR.check(d)
    if bad:
        sys.exit(f"{TK} 리포트가 검사에 걸려 찍지 않는다: {bad}")
    page, tier = SP.render(TK, SP.load_data(), inline=True, preview=True)
    if tier != "v2":
        sys.exit(f"{TK} 리포트가 새 형식이 아니다: {tier}")
    take(br, f"{base}/__stock.html", SHOTS, "report",
         route=(f"{base}/__stock.html", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=page)))


def sector(br, base):
    js = open(os.path.join(ROOT, "data", "sectors.js"), encoding="utf-8").read()
    sec = (json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", js, re.S).group(1)).get("sectors") or {}).get(SECTOR)
    if not sec:
        sys.exit(f"{SECTOR} 업종 분석이 없다")
    bad = CR.defects(sec) or CR.check(sec)
    if bad:
        sys.exit(f"{SECTOR} 업종 분석이 검사에 걸려 찍지 않는다: {bad}")
    take(br, f"{base}/preview/industry.html?sector={urllib.parse.quote(SECTOR)}", SECTOR_SHOTS, "sector", css=HIDE)


def main():
    which = sys.argv[1:] or ["report", "sector"]
    os.makedirs(OUT, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=ROOT))   # 글꼴 · 로고 · 업종 화면은 저장소에서
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        br = pw.chromium.launch(args=["--no-proxy-server"])
        for w in which:
            {"report": report, "sector": sector}[w](br, base)
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    main()
