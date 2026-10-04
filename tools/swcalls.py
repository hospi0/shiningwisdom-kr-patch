"""X02 안에서 함수 호출자 찾기(BSR 직접 + MOV.L 리터럴 → JSR) — python tools/swcalls.py 주소…"""
import struct, sys
FILES = {'X02.BIN': 0x0604F000, 'X03.BIN': 0x0605F000, 'X04.BIN': 0x06076000, 'A.BIN': 0x06010000, 'X01.BIN': 0x06030000}
def callers(t):
    out = []
    for f, L in FILES.items():
        b = open('work/disc/' + f, 'rb').read()
        for pc in range(0, len(b) - 1, 2):
            w = struct.unpack_from('>H', b, pc)[0]
            if w >> 12 == 0xB:
                d = w & 0xFFF; d = d - 4096 if d & 0x800 else d
                if L + pc + 4 + d * 2 == t: out.append((f, L + pc, 'BSR'))
            if w >> 12 == 0xD:
                a = ((L + pc + 4) & ~3) + (w & 0xFF) * 4 - L
                if 0 <= a < len(b) - 3 and struct.unpack_from('>I', b, a)[0] == t: out.append((f, L + pc, 'LIT R%d' % (w >> 8 & 15)))
    return out
if __name__ == '__main__':
    for t in sys.argv[1:]:
        print(t, [(f, '%08X' % a, k) for f, a, k in callers(int(t, 16))])
