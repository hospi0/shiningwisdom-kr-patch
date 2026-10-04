# -*- coding: utf-8 -*-
r"""한자 판독 눈 검토표 — work/review/kanji_NN.png (게임 글자 | OCR 글자, 번호 = kanji_glyph.tsv 줄 번호)
  python tools/swreview.py   · 고친 것은 work/map/kanji_fix.tsv (해시\t글자) 에 — 늘 우선"""
import hashlib, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swhuff as H, swtext, swocr


def glyphs():
    G = {}
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
        font = swocr.struct_u(d, hdr) - load; c = 0x100
        while True:
            o = font + (c - 0x20) * 32
            if o + 32 > len(d): break
            w = int.from_bytes(d[o:o + 2], 'big')
            if not 1 <= w <= 16: break
            h = swocr.ghash(d, font, c)
            if h not in G: G[h] = H.glyph(d, font, c)[1]
            c += 1
    return G


def main():
    G = glyphs()
    rows = [l.rstrip('\n').split('\t') for l in open(os.path.join(ROOT, 'work', 'map', 'kanji_glyph.tsv'), encoding='utf-8')]
    fix = {}
    p = os.path.join(ROOT, 'work', 'map', 'kanji_fix.tsv')
    if os.path.exists(p):
        for l in open(p, encoding='utf-8'):
            a = l.rstrip('\n').split('\t')
            if len(a) >= 2: fix[a[0]] = a[1]
    jf = ImageFont.truetype(r'C:\Windows\Fonts\msgothic.ttc', 28); nf = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 11)
    od = os.path.join(ROOT, 'work', 'review'); os.makedirs(od, exist_ok=True)
    per = 200; cols = 10
    for s in range(0, len(rows), per):
        chunk = rows[s:s + per]; R = (len(chunk) + cols - 1) // cols
        im = Image.new('L', (cols * 100, R * 44), 255); dr = ImageDraw.Draw(im)
        for i, r in enumerate(chunk):
            y, x = divmod(i, cols); X, Y = x * 100, y * 44
            g = G.get(r[0])
            if g is not None:
                im.paste(Image.fromarray(((1 - g) * 255).astype(np.uint8)).resize((32, 30), Image.NEAREST), (X + 20, Y + 6))
            ch = fix.get(r[0], r[1]); dr.text((X + 58, Y + 6), ch, font=jf, fill=0)
            dr.text((X + 1, Y + 2), str(s + i), font=nf, fill=0)
            if r[0] in fix: dr.rectangle((X + 55, Y + 4, X + 90, Y + 38), outline=0)
        im.save(os.path.join(od, 'kanji_%02d.png' % (s // per)))
    print('검토표', (len(rows) + per - 1) // per, '장')


if __name__ == '__main__':
    main()
