# -*- coding: utf-8 -*-
r"""시스템 문구(1바이트 가나, 00 끝 · FF 목록 끝) — X10.BIN(적재 0x060A0000) 목록 표 0x10BA4 + X02 저장 메뉴
  python tools/swsys.py → work/text/sw_sys.tsv (번호 · 파일 · 목록 · 순번 · 위치 · 원문 · 번역)"""
import os, struct, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swhuff as H

X10_BASE = 0x060A0000
X10_LISTS = {3: '몬스터', 4: '아이템·오브·장비', 9: '지명', 10: '설명'}        # 표 0x10BA4 + 4*k


def txt(b, m):
    s = ''.join(m.get(c, '{%02X}' % c) for c in b)
    s = s.replace('゛', '゙').replace('゜', '゚')
    return unicodedata.normalize('NFC', s).replace('゙', '゛').replace('゚', '゜')


def x10():
    d = open(os.path.join(ROOT, 'work', 'disc', 'X10.BIN'), 'rb').read(); m = H.charmap('')
    out = []
    for k, name in X10_LISTS.items():
        p = struct.unpack_from('>I', d, 0x10BA4 + 4 * k)[0] - X10_BASE; i = 0
        while d[p] != 0xFF:
            e = d.index(0, p); out.append(('X10.BIN', name, i, p, txt(d[p:e], m))); p = e + 1; i += 1
    return out


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    rows = x10()
    L = ['#번호\t파일\t목록\t순번\t위치\t원문\t번역'] + ['S%04d\t%s\t%s\t%d\t%05X\t%s\t' % (n + 1, *r) for n, r in enumerate(rows)]
    open(os.path.join(ROOT, 'work', 'text', 'sw_sys.tsv'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('시스템 문구', len(rows), '글자', sum(len(r[4]) for r in rows))


if __name__ == '__main__':
    main()
