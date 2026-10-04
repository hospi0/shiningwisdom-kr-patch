# -*- coding: utf-8 -*-
r"""샤이닝 위즈덤 맵 대사 추출 (2026-10-04, 해독 루틴 X02 0x0605A54C 로 확정)
  ETC 머리말 = 초기화 코드의 리터럴 [머리말 주소][0x0602FFF8] 쌍. 머리말 +00 글꼴 · +04 트리쌍 표 · +08 묶음 표(u32 절대, 0 끝)
  문장 번호 id → 묶음 = 표[id>>8], 묶음 안 [길이 바이트][비트열] 을 id&0xFF 번 건너뜀. 비트열 = 직전 바이트 0 · MSB 먼저 · u16 0x0000 끝.
  python tools/swtext.py   → 요약 + work/text/etc_raw.tsv (파일·묶음·번호·위치·u16 코드열)
"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swhuff as H

DISC = os.path.join(ROOT, 'work', 'disc')
GLOBAL_HDR = 0x0602FFF8


def header(d):
    load = struct.unpack_from('>I', d, 8)[0] & ~0xFFF          # 진입 0x060xx00C → 적재 0x060xx000
    pat = struct.pack('>I', GLOBAL_HDR); q = d.find(pat)
    while q >= 0:
        h = struct.unpack_from('>I', d, q - 4)[0]
        if load <= h < load + len(d):
            return load, h - load
        q = d.find(pat, q + 1)
    raise ValueError('머리말 못 찾음')


def messages(d, load, hdr):
    u = lambda o: struct.unpack_from('>I', d, o)[0]
    T = H.trees(d, u(hdr + 4) - load, load)
    banks = []; o = u(hdr + 8) - load
    while u(o) and load <= u(o) < load + len(d):
        banks.append(u(o) - load); o += 4
    out = []
    for bi, b in enumerate(banks):
        p = b
        for n in range(256):
            if p >= len(d): break
            L = d[p]; bs = H.Bits(d, p + 1, 0); prev = 0; sym = []
            try:
                while True:
                    t = T[prev]
                    while isinstance(t, tuple): t = t[bs.get()]
                    sym.append(t); prev = t
                    if len(sym) % 2 == 0 and sym[-2:] == [0, 0]: break
                    if len(sym) > 4000: raise ValueError
            except Exception:
                break
            used = bs.o - (p + 1) + (1 if bs.b else 0)
            if used != L: break
            codes = [(sym[i] << 8) | sym[i + 1] for i in range(0, len(sym), 2)]
            out.append((bi, n, p, L, codes)); p += L + 1
    return banks, out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = []; tot = 0; totc = 0
    for f in sorted(x for x in os.listdir(DISC) if x.endswith('.ETC')):
        d = open(os.path.join(DISC, f), 'rb').read()
        load, hdr = header(d); banks, ms = messages(d, load, hdr)
        nc = sum(len(c) - 1 for *_, c in ms); tot += len(ms); totc += nc
        print('%-9s 적재 %08X 머리말 %05X 묶음 %d 문장 %4d 코드 %6d' % (f, load, hdr, len(banks), len(ms), nc))
        for bi, n, p, L, codes in ms:
            rows.append('%s\t%d\t%d\t%05X\t%s' % (f, bi, n, p, ' '.join('%04X' % c for c in codes)))
    os.makedirs(os.path.join(ROOT, 'work', 'text'), exist_ok=True)
    open(os.path.join(ROOT, 'work', 'text', 'etc_raw.tsv'), 'w', encoding='utf-8').write('\n'.join(rows) + '\n')
    print('합계 문장', tot, '코드', totc)



def kanji_by_hash():
    """kanji_glyph.tsv + kanji_fix.tsv(우선) → {그림 해시: 글자}"""
    k = {}
    for l in open(os.path.join(ROOT, 'work', 'map', 'kanji_glyph.tsv'), encoding='utf-8'):
        a = l.rstrip('\n').split('\t'); k[a[0]] = a[1]
    p = os.path.join(ROOT, 'work', 'map', 'kanji_fix.tsv')
    for l in open(p, encoding='utf-8'):
        a = l.rstrip('\n').split('\t'); k[a[0]] = a[1]
    return k


def map_charmap(d, load, hdr, KH):
    import swocr
    font = swocr.struct_u(d, hdr) - load
    m = H.charmap('')
    c = 0x100
    while True:
        o = font + (c - 0x20) * 32
        if o + 32 > len(d) or not 1 <= struct.unpack_from('>H', d, o)[0] <= 16: break
        m[c] = KH[swocr.ghash(d, font, c)]; c += 1
    return m


def render(codes, m):
    s = []
    for c in codes[:-1]:                     # 끝 0000 제외
        if c == 3: s.append('\\n')
        elif c in m and c >= 0x20: s.append(m[c])
        else: s.append('{%04X}' % c)
    t = ''.join(s)
    t = t.replace('゛', '゙').replace('゜', '゚')
    import unicodedata
    return unicodedata.normalize('NFC', t).replace('゙', '゛').replace('゚', '゜')


def dump_tsv():
    """→ work/text/sw_etc.tsv : 번호 · 파일 · 문장 · 원문 · 같은 원문 개수(첫 줄에만) · 번역"""
    KH = kanji_by_hash(); rows = []; first = {}
    for f in sorted(x for x in os.listdir(DISC) if x.endswith('.ETC')):
        d = open(os.path.join(DISC, f), 'rb').read(); load, hdr = header(d)
        m = map_charmap(d, load, hdr, KH); _, ms = messages(d, load, hdr)
        for bi, n, p, L, codes in ms:
            t = render(codes, m); rows.append([f, '%d.%d' % (bi, n), t]); first.setdefault(t, 0); first[t] += 1
    out = ['#번호\t파일\t문장\t원문\t개수\t번역']; seen = set(); k = 0
    for f, n, t in rows:
        if t in seen: continue
        seen.add(t); k += 1
        out.append('%05d\t%s\t%s\t%s\t%d\t' % (k, f, n, t, first[t]))
    open(os.path.join(ROOT, 'work', 'text', 'sw_etc.tsv'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('고유 문장', k, '/ 전체', len(rows), '· 글자', sum(len(t) for t in seen))


if __name__ == '__main__':
    dump_tsv() if sys.argv[1:] == ['tsv'] else main()
