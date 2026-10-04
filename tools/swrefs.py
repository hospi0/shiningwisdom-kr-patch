"""리터럴 풀의 u32 값 → 그 리터럴을 읽는 MOV.L @(disp,PC) 명령 위치 찾기
python tools/swrefs.py 파일 적재주소 값(16진)"""
import struct, sys
def users(b, load, val):
    out = []
    for lit in range(0, len(b) - 3, 4):
        if struct.unpack_from('>I', b, lit)[0] != val: continue
        for pc in range(max(0, lit - 1024), lit, 2):
            w = struct.unpack_from('>H', b, pc)[0]
            if w >> 12 == 0xD and ((load + pc + 4) & ~3) + (w & 0xFF) * 4 == load + lit:
                out.append((load + pc, (w >> 8) & 15, load + lit))
    return out
if __name__ == '__main__':
    f, load, val = sys.argv[1], int(sys.argv[2], 16), int(sys.argv[3], 16)
    b = open('work/disc/' + f, 'rb').read()
    for pc, r, lit in users(b, load, val): print('%08X  MOV.L @%08X, R%d' % (pc, lit, r))
