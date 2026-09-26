#!/usr/bin/env python3
"""Pretendard 분할판(dynamic subset)을 fonts/ 에 푼다 — 새 디자인 페이지(시안·스테이징·정적 종목 페이지)가 쓴다.

    python3 scripts/build_font_subset.py            # npm 에서 pretendard@1.3.9 를 받아 푼다
    python3 scripts/build_font_subset.py --tgz 파일  # 이미 받은 꾸러미로

만드는 것
  · fonts/pretendard-subset/Pretendard-{Regular,Medium,SemiBold,Bold}.subset.N.woff2 — 굵기마다 92조각
  · fonts/pretendard-subset.css — 공식 pretendard-dynamic-subset.css 에서 400·500·600·700 만 남기고 woff 대체 주소를 뺀 것

왜. 전에는 굵기 넷의 통파일(각 790~820KB, 합 3.2MB)을 모든 페이지가 preload 로 받았다. 분할판은 글자 묶음(unicode-range)
마다 파일이 나뉘어 있어 그 페이지에 나온 글자의 묶음만 받는다. 판(1.3.9)은 저장소 통파일(Version 1.309)과 같게 맞췄다 —
판을 올리면 글자 모양이 실사이트와 달라질 수 있으니 같이 올린다. 실사이트(루트) 페이지는 아직 통파일을 쓴다.
"""
import argparse, io, re, sys, tarfile, urllib.request
from pathlib import Path

VERSION = '1.3.9'
WEIGHTS = {'400': 'Regular', '500': 'Medium', '600': 'SemiBold', '700': 'Bold'}
ROOT = Path(__file__).resolve().parent.parent
BASE = 'package/dist/web/static/'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tgz')
    a = ap.parse_args()
    data = Path(a.tgz).read_bytes() if a.tgz else urllib.request.urlopen(
        f'https://registry.npmjs.org/pretendard/-/pretendard-{VERSION}.tgz', timeout=120).read()
    tar = tarfile.open(fileobj=io.BytesIO(data), mode='r:gz')
    css = tar.extractfile(BASE + 'pretendard-dynamic-subset.css').read().decode('utf-8')
    header = css[:css.index('*/') + 2]
    lines = [header, f'/* KOSAI — 공식 pretendard-dynamic-subset.css({VERSION})에서 400·500·600·700 만 남기고 woff 대체 주소를 뺐다.\n'
             '   글자 묶음(unicode-range)마다 파일이 나뉘어 있어 페이지에 나온 글자의 묶음만 받는다. scripts/build_font_subset.py 로 만든다. */']
    out = ROOT / 'fonts/pretendard-subset'
    out.mkdir(parents=True, exist_ok=True)
    used = []
    for body in re.findall(r'@font-face\s*\{(.*?)\}', css, re.S):
        w = re.search(r'font-weight:\s*(\d+)', body).group(1)
        if w not in WEIGHTS:
            continue
        fn = re.search(r'url\(\./woff2-dynamic-subset/(Pretendard-[A-Za-z]+\.subset\.\d+\.woff2)\)', body).group(1)
        ur = re.search(r'unicode-range:\s*([^;]+);', body).group(1).strip()
        lines.append(f'@font-face{{font-family:"Pretendard";font-style:normal;font-weight:{w};font-display:swap;'
                     f'src:url(pretendard-subset/{fn}) format("woff2");unicode-range:{ur}}}')
        used.append(fn)
    for fn in used:
        (out / fn).write_bytes(tar.extractfile(BASE + 'woff2-dynamic-subset/' + fn).read())
    (ROOT / 'fonts/pretendard-subset.css').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'✅ Pretendard {VERSION} 분할판 — 규칙 {len(used)}개 · 파일 {len(used)}개')


if __name__ == '__main__':
    sys.exit(main())
