"""스테이트 VDP2 NBG0‥3 그리기 — 이 게임 설정: 셀 1×1 · 8bpp · 패턴 이름 1워드(CNSM=1: 0‥11 = 문자 번호, 12‥14 = 팔레트) · 면 1×1
  맵 주소 = MPABNn 하위 6비트 × 0x2000. 문자 주소 = 번호 × 0x20.
python tools/swvdp2.py s4  → work/view/<s>_nbgN.png (512×512, 스크롤 무시) · work/view/<s>_nbgN_map.txt"""
import os, struct, sys
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def render(s):
    M = os.path.join(ROOT, 'work', 'mem', s)
    V = open(os.path.join(M, 'VDP2_VRAM.bin'), 'rb').read(); C = open(os.path.join(M, 'CRAM.bin'), 'rb').read()
    R = struct.unpack('>256H', open(os.path.join(M, 'VDP2_REGS.bin'), 'rb').read())
    col = lambda i: (lambda c: ((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3))(C[i * 2 & 0xFFF] << 8 | C[(i * 2 + 1) & 0xFFF])
    for n in range(4):
        base = (R[(0x40 + 4 * n) // 2] & 0x3F) * 0x2000
        im = Image.new('RGB', (512, 512)); px = im.load(); lines = []
        for ty in range(64):
            row = []
            for tx in range(64):
                w = struct.unpack_from('>H', V, base + (ty * 64 + tx) * 2)[0]
                ch = (w & 0xFFF) | ((R[(0x30 + 2 * n) // 2] >> 2 & 7) << 12); pal = (w >> 12) & 7   # PNCNn 보조 문자 번호 2‥4 → 12‥14비트
                row.append('%04X' % ch)
                a = ch * 0x20
                for y in range(8):
                    for x in range(8):
                        v = V[(a + y * 8 + x) & 0x7FFFF]
                        if v:
                            px[tx * 8 + x, ty * 8 + y] = col(pal * 256 + v)
            lines.append(' '.join(row))
        im.save(os.path.join(ROOT, 'work', 'view', '%s_nbg%d.png' % (s, n)))
        open(os.path.join(ROOT, 'work', 'view', '%s_nbg%d_map.txt' % (s, n)), 'w').write('\n'.join(lines))


if __name__ == '__main__':
    render(sys.argv[1])
