#!/usr/bin/env python3
"""랜딩(스테이징) 그레인 타일을 만든다 — 파이썬 표준 라이브러리만.

    python3 scripts/gengrain.py OUT.png [size=192] [sigma=12] [step=2] [hp=2] [seed=7]

staging/index.html 의 .lp-grain::after 에 박힌 타일은 이 설정으로 만든 것이다(바이트까지 같다):

    python3 scripts/gengrain.py grain.png 128 11.5 12 2 7

  1. 가우시안 백색 잡음에서 흐린 사본(둘레를 이어 붙인 가우시안, sigma=hp px)을 빼 얼룩과
     타일 크기의 무늬를 걷어 낸다 — 이음새가 없고, 타일이 되풀이되는 것이 안 보인다.
  2. 128 을 중심으로 표준편차 sigma 단계로 맞추고 step 단위로 끊는다(파일이 작아지고 눈으로는 같다).
  3. 회색이 아니라 흰/검은 점의 투명도(= 2×|회색-128|)로 담는다. soft-light·overlay 에서는 회색
     타일과 수학적으로 같고, 블렌드를 못 하는 브라우저에서는 페이지 전체를 50% 회색으로 덮는
     대신 옅은 점으로만 남는다.
"""
import math, random, struct, sys, zlib

def gauss_kernel(s):
    r = max(1, int(math.ceil(3 * s)))
    k = [math.exp(-(i * i) / (2 * s * s)) for i in range(-r, r + 1)]
    t = sum(k)
    return [v / t for v in k], r

def blur_wrap(img, n, s):
    k, r = gauss_kernel(s)
    tmp = [[sum(k[j] * row[(x + j - r) % n] for j in range(2 * r + 1)) for x in range(n)] for row in img]
    return [[sum(k[j] * tmp[(y + j - r) % n][x] for j in range(2 * r + 1)) for x in range(n)] for y in range(n)]

def grain(n, sigma, step, hp, seed):
    rnd = random.Random(seed)
    w = [[rnd.gauss(0, 1) for _ in range(n)] for _ in range(n)]
    if hp > 0:
        b = blur_wrap(w, n, hp)
        w = [[w[y][x] - b[y][x] for x in range(n)] for y in range(n)]
    flat = [v for row in w for v in row]
    m = sum(flat) / len(flat)
    sd = math.sqrt(sum((v - m) ** 2 for v in flat) / len(flat))
    return [max(-127, min(127, step * round((v - m) / sd * sigma / step))) for v in flat]  # grey offset from 128

def chunk(t, d):
    return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)

def deflate(raw):  # noise has no repeats to find: Huffman-only packs ~9% smaller than the default strategy
    c = zlib.compressobj(9, zlib.DEFLATED, 15, 9, zlib.Z_HUFFMAN_ONLY)
    return c.compress(raw) + c.flush()

def png_indexed(q, n):
    levels = sorted(set(q))
    idx = {v: i for i, v in enumerate(levels)}
    plte = b''.join(b'\xff\xff\xff' if v > 0 else b'\x00\x00\x00' for v in levels)
    trns = bytes(min(255, 2 * abs(v)) for v in levels)
    bits = 8 if len(levels) > 16 else 4 if len(levels) > 4 else 2
    per, rows = 8 // bits, []
    for y in range(n):
        row, out = [idx[v] for v in q[y * n:(y + 1) * n]], bytearray()
        for x in range(0, n, per):
            b = 0
            for k in range(per):
                b = (b << bits) | (row[x + k] if x + k < n else 0)
            out.append(b)
        rows.append(b'\x00' + bytes(out))
    raw = b''.join(rows)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', n, n, bits, 3, 0, 0, 0))
            + chunk(b'PLTE', plte) + chunk(b'tRNS', trns) + chunk(b'IDAT', deflate(raw)) + chunk(b'IEND', b''))

if __name__ == '__main__':
    a = sys.argv[1:] + [None] * 6
    out = a[0]
    n = int(a[1] or 192); sigma = float(a[2] or 12); step = int(a[3] or 2); hp = float(a[4] or 2); seed = int(a[5] or 7)
    q = grain(n, sigma, step, hp, seed)
    data = png_indexed(q, n)
    open(out, 'wb').write(data)
    mean = sum(q) / len(q); sd = math.sqrt(sum((v - mean) ** 2 for v in q) / len(q))
    print('%s %dx%d grey-equiv sigma=%.2f mean=%+.3f range=[%d,%d] levels=%d png=%dB base64=%dB'
          % (out, n, n, sd, mean, min(q), max(q), len(set(q)), len(data), (len(data) + 2) // 3 * 4))
