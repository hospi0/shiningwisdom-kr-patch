# -*- coding: utf-8 -*-
r"""맵 한자 받아쓰기(2026-10-04) — 한자는 맵마다 코드가 달라 «글자 그림 해시»로 묶는다.
  python tools/swocr.py prep   → work/ocr/img_NNNN.png + layout.json (대사 줄을 게임 글꼴로 4배 흰 바탕)
  powershell -ExecutionPolicy Bypass -File tools\winocr.ps1 -Dir work\ocr
  python tools/swocr.py vote   → work/map/kanji_glyph.tsv (해시 · 글자 · 득표/전체 · 쓰인 맵 수)
                                 work/map/kanji_<맵>.txt 는 만들지 않음 — 코드표는 swtext 가 해시로 찾는다
"""
import collections, glob, hashlib, json, os, sys, unicodedata
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swhuff as H, swtext

OCR = os.path.join(ROOT, 'work', 'ocr'); SC = 4


def fonts():
    """{맵: (d, font_base)}"""
    out = {}
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
        out[f] = (d, H.load.__defaults__ and (struct_u(d, hdr) - load), load, hdr)
    return out


def struct_u(d, o):
    import struct
    return struct.unpack_from('>I', d, o)[0]


def ghash(d, font, c):
    w, g = H.glyph(d, font, c)
    return hashlib.md5(bytes([w]) + g.tobytes()).hexdigest()[:10]


def lines():
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
        font = struct_u(d, hdr) - load
        _, ms = swtext.messages(d, load, hdr)
        for bi, n, p, L, codes in ms:
            cur = []
            for c in codes + [3]:
                if c < 0x20:
                    if any(x >= 0x100 for x in cur): yield f, d, font, cur
                    cur = []
                else:
                    cur.append(c)


def prep():
    os.makedirs(OCR, exist_ok=True)
    for p in glob.glob(os.path.join(OCR, 'img_*')): os.remove(p)
    seen = set(); lay = {}; k = 0
    for f, d, font, cur in lines():
        key = (f, tuple(cur))
        if key in seen: continue
        seen.add(key)
        W = sum(H.glyph(d, font, c)[0] + 1 for c in cur) + 8
        img = np.full((16 + 8, W), 255, np.uint8); x = 4; cells = []
        for c in cur:
            w, g = H.glyph(d, font, c)
            img[4:19, x:x + 16][g[:, :min(16, W - x)] == 1] = 0
            cells.append([x, x + w, ghash(d, font, c) if c >= 0x100 else None, c]); x += w + 1
        Image.fromarray(img).resize((W * SC, img.shape[0] * SC), Image.NEAREST).save(os.path.join(OCR, 'img_%05d.png' % k))
        lay['%05d' % k] = {'map': f, 'cells': cells}; k += 1
    json.dump(lay, open(os.path.join(OCR, 'layout.json'), 'w'))
    print('줄', k)


def nk(c):
    return unicodedata.normalize('NFKC', c)


def vote():
    lay = json.load(open(os.path.join(OCR, 'layout.json')))
    V = collections.defaultdict(collections.Counter); maps = collections.defaultdict(set); tot = collections.Counter()
    for k, L in lay.items():
        t = os.path.join(OCR, 'img_%s.txt' % k)
        for c in L['cells']:
            if c[2]: tot[c[2]] += 1; maps[c[2]].add(L['map'])
        if not os.path.exists(t): continue
        for ln in open(t, encoding='utf-8'):
            p = ln.rstrip('\n').split('\t')
            if len(p) < 5: continue
            word = p[0]; x, w = float(p[1]) / SC, float(p[3]) / SC
            n = len(word)
            for i, ch in enumerate(word):
                cx = x + (i + 0.5) * w / n
                for c in L['cells']:
                    if c[2] and c[0] - 1 <= cx < c[1] + 1:
                        ch = nk(ch)
                        if '一' <= ch <= '鿿' or ch in '々〆ヶ': V[c[2]][ch] += 1
    out = []
    for h in sorted(tot, key=lambda h: -tot[h]):
        best = V[h].most_common(2)
        out.append('%s\t%s\t%d/%d\t%d\t%s' % (h, best[0][0] if best else '?', best[0][1] if best else 0, tot[h], len(maps[h]),
                                             ' '.join('%s%d' % kv for kv in best)))
    p = os.path.join(ROOT, 'work', 'map', 'kanji_glyph.tsv'); os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('한자 그림', len(tot), '판독', sum(1 for h in tot if V[h]))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    {'prep': prep, 'vote': vote}[sys.argv[1]]()
