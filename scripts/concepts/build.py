"""디자인 시안을 preview/concepts/ 에 만든다 — 스테이징·실사이트는 건드리지 않는다.

    python3 scripts/concepts/build.py            # 전부
    python3 scripts/concepts/build.py a          # 하나만
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from data import ROOT  # noqa: E402

OUT = os.path.join(ROOT, "preview", "concepts")


def write(rel, text):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"  · preview/concepts/{rel}  {len(text):,}자")


def build(which):
    mod = __import__(which)
    write(f"{which}/{which}.css", mod.CSS.strip() + "\n")
    write(f"{which}/index.html", mod.home())
    write(f"{which}/stock.html", mod.stock())


CONCEPTS = [
    ("c", "C", "쇼케이스", "한 장면에 한 메시지. 큰 제목과 큰 숫자, 리포트를 제품 사진처럼. 밝고 또렷한 고급.", "#f5f5f7", "#1d1d1f"),
]


def gallery():
    """시안 목록 — 사장이 휴대폰으로 처음 여는 페이지."""
    rows = ""
    for key, tag, name, desc, bg, fg in CONCEPTS:
        rows += (f'<article class="c"><div class="meta"><p class="tag">시안 {tag}</p><h2>{name}</h2><p class="d">{desc}</p>'
                 f'<p class="links"><a href="{key}/index.html">홈 보기 →</a><a href="{key}/stock.html">삼성전자 리포트 보기 →</a></p></div>'
                 f'<a class="shot" href="{key}/index.html" style="background:{bg}"><img src="img/{key}-home.webp" alt="시안 {tag} 홈 첫 화면" loading="lazy"></a>'
                 f'<a class="shot m" href="{key}/stock.html" style="background:{bg}"><img src="img/{key}-stock-m.webp" alt="시안 {tag} 리포트 휴대폰 화면" loading="lazy"></a></article>')
    css = """*{box-sizing:border-box}body{margin:0;background:#fff;color:#111;font:400 16px/1.6 'Pretendard Variable',Pretendard,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased;word-break:keep-all;letter-spacing:-.01em}a{color:inherit;text-decoration:none}h1,h2,p{margin:0}
.w{max-width:1180px;margin:0 auto;padding:72px 32px 96px}.top{border-bottom:1px solid #e6e6e6;padding-bottom:36px;margin-bottom:12px}
.top small{font:600 13px/1 inherit;letter-spacing:.24em;color:#111}.top h1{font:680 44px/1.15 inherit;letter-spacing:-.04em;margin-top:18px}
.top p{margin-top:14px;color:#555;max-width:640px;font-size:17px}
.c{display:grid;grid-template-columns:minmax(0,.9fr) minmax(0,1.5fr) minmax(0,.45fr);gap:28px;align-items:center;padding:44px 0;border-bottom:1px solid #eee}
.tag{font:650 13px/1 inherit;color:#888}.c h2{font:680 30px/1.2 inherit;letter-spacing:-.035em;margin-top:10px}.d{margin-top:12px;color:#555;font-size:15.5px}
.links{margin-top:20px;display:flex;flex-direction:column;gap:10px;font:600 15px/1.2 inherit}.links a:hover{text-decoration:underline;text-underline-offset:.2em}
.shot{display:block;border-radius:14px;overflow:hidden;box-shadow:0 0 0 1px rgba(0,0,0,.08),0 20px 50px -24px rgba(0,0,0,.35);transition:transform .3s}
.shot:hover{transform:translateY(-3px)}.shot img{display:block;width:100%;height:auto}.shot.m{border-radius:18px}
.foot{margin-top:40px;color:#888;font-size:13.5px}
@media (max-width:820px){.w{padding:44px 20px 72px}.top h1{font-size:32px}.c{grid-template-columns:1fr 1fr;gap:16px}.c .meta{grid-column:1/-1}
.shot{grid-column:1/2}.shot.m{grid-column:2/3}}"""
    html = ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta name="robots" content="noindex,nofollow"><title>KOSAI 디자인 시안</title>'
            '<link href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css" rel="stylesheet">'
            f'<style>{css}</style></head><body><main class="w"><header class="top"><small>KOSAI</small><h1>디자인 시안</h1>'
            '<p>9월 23일 브리핑·시세와 삼성전자 리포트로 그린 시안입니다. 홈과 리포트 페이지를 휴대폰과 PC에서 각각 보실 수 있습니다. '
            '스테이징·실사이트와는 별개의 미리보기입니다.</p></header>'
            f'{rows}<p class="foot">검색에 나오지 않는 미리보기 페이지입니다(noindex). 링크·단추는 모양만 있습니다.</p></main></body></html>')
    write("index.html", html)


def thumbs(review_dir):
    """채점용 촬영본에서 목록 페이지 썸네일(webp)을 만든다."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    out = os.path.join(OUT, "img")
    os.makedirs(out, exist_ok=True)
    for key, *_ in CONCEPTS:
        im = Image.open(os.path.join(review_dir, f"{key}-home-dtop.png")).convert("RGB")
        im.resize((960, int(im.height * 960 / im.width)), Image.LANCZOS).save(os.path.join(out, f"{key}-home.webp"), quality=82, method=6)
        im = Image.open(os.path.join(review_dir, f"{key}-stock-m.png")).convert("RGB")
        im = im.crop((0, 0, im.width, min(im.height, int(im.width * 2.05))))
        im.resize((360, int(im.height * 360 / im.width)), Image.LANCZOS).save(os.path.join(out, f"{key}-stock-m.webp"), quality=82, method=6)
    print("  · preview/concepts/img/*.webp")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["thumbs"]:
        thumbs(args[1])
        sys.exit(0)
    for w in (args or [k for k, *_ in CONCEPTS]):
        if os.path.exists(os.path.join(os.path.dirname(__file__), f"{w}.py")):
            build(w)
    if not args:
        gallery()
