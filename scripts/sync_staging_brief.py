#!/usr/bin/env python3
"""실사이트 모닝브리핑(brief.html)을 스테이징(staging/brief.html)으로 옮긴다.

왜 있나. 아침 워크플로(render_brief.py)는 brief.html 하나만 새로 쓴다. 스테이징
쪽은 아무도 갈아 주지 않아 8월 17일 글과 그때 디자인으로 한 달 넘게 멈춰
있었다 — 그 사이 실사이트에 들어간 요약 상자·소제목 막대·커버리지 표시가
하나도 없었다(2026-09-23 사장이 "디자인이 다르다"고 알아챔). 손으로 한 줄씩
맞추면 또 빠뜨린다. 그래서 실사이트 페이지를 통째로 가져오고, 스테이징에만
있어야 하는 것만 다시 얹는다.

  · <head> 맨 앞 두 줄 — demo-backend.js(모의 결제) · robots noindex
  · 글꼴·아이콘·로고 주소 — fonts/ · assets/ → ../ (스테이징은 한 단계 아래)
  · 로고 링크 — "/" 가 아니라 "./"(스테이징 첫 화면으로)
  · 맨 위 빨간 STAGING 띠와 그 스크립트
  · 메뉴·모바일 메뉴·푸터의 '멤버십'(pricing.html)
  · 자바스크립트 ?v= 해시 — 스테이징 파일 기준으로 다시 찍는다(stamp_assets 규칙)

얹을 것 중 head 두 줄과 띠는 지금의 staging/brief.html 에서 떼어 온다. 자리를
하나라도 못 찾으면 아무것도 쓰지 않고 멈춘다 — 반쯤 바뀐 페이지를 남기지 않는다.

    python3 scripts/sync_staging_brief.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stamp_assets  # noqa: E402  같은 규칙으로 ?v= 를 찍는다

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "brief.html"
STAGING = ROOT / "staging" / "brief.html"


def cut(text, start, end, label):
    """start 부터 end 까지(end 포함)를 떼어 온다. 없으면 멈춘다."""
    i = text.find(start)
    j = text.find(end, i) if i >= 0 else -1
    if i < 0 or j < 0:
        raise SystemExit(f"❌ 지금의 스테이징에서 {label} 을(를) 찾지 못했습니다")
    return text[i:j + len(end)]


def swap(text, old, new, count, label):
    """정확히 count 번 나와야 바꾼다 — 더 많거나 적으면 모양이 바뀐 것이다."""
    n = text.count(old)
    if n != count:
        raise SystemExit(f"❌ 실사이트에서 {label} 이(가) {count}번이 아니라 {n}번 나옵니다")
    return text.replace(old, new)


def build(live, staging):
    head_extra = cut(staging, '<script type="module" src="demo-backend.js',
                     '<meta name="robots" content="noindex,nofollow" />\n', "head 두 줄")
    bar = cut(staging, '<div class="kos-staging-bar">', "});\n</script>\n", "STAGING 띠")

    out = live
    out = swap(out, "<head>\n", "<head>\n" + head_extra, 1, "<head>")
    out = swap(out, 'url("fonts/', 'url("../fonts/', 10, "글꼴 주소")
    out = swap(out, 'href="assets/', 'href="../assets/', 4, "아이콘 주소")
    out = swap(out, 'src="assets/', 'src="../assets/', 4, "로고 주소")
    out = swap(out, '<a class="brand" href="/">', '<a class="brand" href="./">', 2, "로고 링크")
    out = swap(out, "<body>\n", "<body>\n" + bar + "\n", 1, "<body>")
    # 줄바꿈부터 맞춘다 — 앞 공백 두 칸짜리 모양은 여섯 칸짜리 메뉴 줄 안에도 들어 있다.
    out = swap(out, '\n      <a href="Watchlist.html">관심종목</a>\n',
               '\n      <a href="Watchlist.html">관심종목</a>\n    <a href="pricing.html">멤버십</a>\n',
               1, "메뉴의 관심종목")
    out = swap(out, '\n  <a href="Watchlist.html">관심종목</a>\n',
               '\n  <a href="Watchlist.html">관심종목</a>\n  <a href="pricing.html">멤버십</a>\n',
               1, "모바일 메뉴의 관심종목")
    out = swap(out, '<li><a href="Watchlist.html">관심종목</a></li>',
               '<li><a href="Watchlist.html">관심종목</a></li><li><a href="pricing.html">멤버십</a></li>',
               1, "푸터의 관심종목")

    js = sorted((ROOT / "staging").glob("*.js"))
    hashes = {p.name: stamp_assets.digest(p.read_text(encoding="utf-8")) for p in js}
    out, _ = stamp_assets.stamp(out, hashes)
    return out


def main():
    live = LIVE.read_text(encoding="utf-8")
    staging = STAGING.read_text(encoding="utf-8")
    out = build(live, staging)
    if out == staging:
        print("스테이징 브리핑이 이미 실사이트와 같습니다")
        return 0
    STAGING.write_text(out, encoding="utf-8")
    print(f"✅ staging/brief.html 을 실사이트 기준으로 새로 썼습니다 ({len(out):,}자)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
