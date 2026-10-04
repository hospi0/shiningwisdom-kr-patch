"""워드 LZ (A.BIN 0x06011E94 해제 루틴) — 메뉴 8×8 글꼴(X10.BIN +0xA4 → VDP2 VRAM 0x20000, 0x6800 B = 8bpp 셀 416개)
  [플래그 u16](MSB 먼저) 비트 0 = 리터럴 u16 · 1 = 토큰 u16: 길이 = (t & 0x1F) + 2, 거리 = t >> 5 (1‥2047), t = 0 끝
  원형 버퍼 0x820 워드(처음 0), 쓰는 자리는 0 부터. 거리 = 지금 자리 − 원본 자리.
python tools/swlz.py   → X10 글꼴 해제 = 스테이트 VRAM 대조 + 압축기 왕복"""
import os, struct, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = 0x820


def decompress(d, o=0):
    ring = [0] * N; pos = 0; out = []; mask = 0; flag = 0; p = o
    while True:
        mask >>= 1
        if not mask:
            flag = struct.unpack_from('>H', d, p)[0]; p += 2; mask = 0x8000
        w = struct.unpack_from('>H', d, p)[0]; p += 2
        if not flag & mask:
            ring[pos] = w; out.append(w); pos = (pos + 1) % N
            continue
        if w == 0:
            break
        n = (w & 0x1F) + 2; dist = w >> 5
        for _ in range(n):
            v = ring[(pos - dist) % N]; ring[pos] = v; out.append(v); pos = (pos + 1) % N
    return b''.join(struct.pack('>H', v) for v in out), p - o


def compress(data):
    assert len(data) % 2 == 0
    W = list(struct.unpack('>%dH' % (len(data) // 2), data))
    out = []; i = 0; group = []; flag = 0; nbit = 0
    def flush():
        nonlocal group, flag, nbit
        out.append(flag << (16 - nbit) if nbit < 16 else flag); out.extend(group); group = []; flag = 0; nbit = 0
    # 원형 버퍼 초기값 0 도 참조 가능하지만, 단순하게 이미 낸 출력만 참조(거리 ≤ 2047)
    while i < len(W):
        best_n = 0; best_d = 0
        lo = max(0, i - 2047)
        for j in range(i - 1, lo - 1, -1):
            n = 0
            while n < 33 and i + n < len(W) and W[j + n] == W[i + n]:
                n += 1
            if n > best_n:
                best_n, best_d = n, i - j
                if n == 33:
                    break
        if best_n >= 2:
            group.append(best_d << 5 | (best_n - 2)); flag = flag << 1 | 1; i += best_n
        else:
            group.append(W[i]); flag = flag << 1; i += 1
        nbit += 1
        if nbit == 16:
            flush()
    group.append(0); flag = flag << 1 | 1; nbit += 1
    flush()
    return b''.join(struct.pack('>H', v) for v in out)


def main():
    x10 = open(os.path.join(ROOT, 'work/disc/X10.BIN'), 'rb').read()
    font, used = decompress(x10, 0xA4)
    V = open(os.path.join(ROOT, 'work/mem/s4/VDP2_VRAM.bin'), 'rb').read()
    print('해제 %d B (압축 %d B, X10 0xA4‥0x%X) · VRAM 0x20000 과 %s' % (len(font), used, 0xA4 + used,
          '일치' if V[0x20000:0x20000 + len(font)] == font else '다름(첫 차이 %d)' % next((i for i in range(len(font)) if V[0x20000 + i] != font[i]), -1)))
    c = compress(font); back, _ = decompress(c)
    print('재압축 %d B · 왕복 %s' % (len(c), '일치' if back == font else '다름'))


if __name__ == '__main__':
    main()
