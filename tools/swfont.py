"""한글 글꼴 칸 만들기 — 게임 글꼴 형식 [u16 폭][u16 × 15줄](MSB=왼쪽), 진행 = 폭+1px
  한글·… = 갈무리11 BDF(잉크 그대로, ⛔TTF 래스터 금지), 폭 11 고정(진행 12) · 세로 3‥13행(가나 밑선 13행에 맞춤)
  ASCII·부호 = 게임 원래 글꼴(M001 0x20‥0x7E) · 공백 폭 SPACE
python tools/swfont.py preview  → work/view/font_preview.png (대사창 3배 확대 미리보기)"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
BDF = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri11.bdf'
HANGUL_W = 11; TOP = 3; SPACE = 4
_g = None


def galmuri():
    global _g
    if _g is None:
        _g = {}
        txt = open(BDF, encoding='utf-8').read()
        for m in re.finditer(r'ENCODING (-?\d+)\n(.*?)ENDCHAR', txt, re.S):
            b = re.search(r'BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)', m.group(2))
            bm = re.search(r'BITMAP\n(.*)', m.group(2), re.S)
            if b and bm:
                _g[int(m.group(1))] = tuple(int(x) for x in b.groups()) + ([r for r in bm.group(1).split() if r],)
    return _g


def glyph_bdf(ch, width=None):
    """→ (폭, 15줄 u16). 밑선(BDF y=0) = TOP+10 행"""
    w, h, ox, oy, rows = galmuri()[ord(ch)]
    out = [0] * 15; base = TOP + 10
    for i, r in enumerate(rows):
        y = base - (oy + h - 1) + i
        v = int(r, 16) >> (len(r) * 4 - w) if r else 0
        if 0 <= y < 15:
            out[y] = (v << (16 - w - ox)) & 0xFFFF
    return (width if width is not None else ox + w), out


def game_ascii():
    import swtext, swocr
    d = open(os.path.join(swtext.DISC, 'M001.ETC'), 'rb').read(); load, hdr = swtext.header(d)
    font = swocr.struct_u(d, hdr) - load
    g = {}
    for c in range(0x20, 0x7F):
        o = font + (c - 0x20) * 32
        g[chr(c)] = (struct.unpack_from('>H', d, o)[0], list(struct.unpack_from('>15H', d, o + 2)))
    g[' '] = (SPACE, [0] * 15)
    for c in '~`^{}|\\':                       # 게임 글꼴에 그림이 없는 칸(네모) → 갈무리
        g.pop(c, None)
    return g


def glyph(ch, A):
    if '\uac00' <= ch <= '\ud7a3':
        return glyph_bdf(ch, HANGUL_W)
    if ch in A:
        return A[ch]
    return glyph_bdf(ch)


def preview(texts, out):
    from PIL import Image, ImageDraw
    A = game_ascii(); TOK = re.compile(r'\{[0-9A-F]{4}\}')
    W, LH = 288, 16; pages = []
    for t in texts:
        t = TOK.sub(lambda m: '하스피' if m.group() == '{000A}' else '', t)
        pages.append(t.split('\\n'))
    im = Image.new('RGB', (W + 8, (LH * 3 + 10) * len(pages)), (16, 24, 96)); px = im.load()
    for pi, lines in enumerate(pages):
        y0 = pi * (LH * 3 + 10) + 4
        for x in range(W + 8):
            px[x, y0 - 3] = (200, 160, 60)
        for li, s in enumerate(lines):
            x = 4
            for ch in s:
                w, rows = glyph(ch, A)
                for yy, r in enumerate(rows):
                    for xx in range(16):
                        if r >> (15 - xx) & 1 and x + xx < W + 8:
                            px[x + xx, y0 + li * LH + yy] = (255, 255, 255)
                x += w + 1
            if x - 5 > W:
                for yy in range(LH):
                    px[min(W + 4, im.width - 1), y0 + li * LH + yy] = (255, 0, 0)
    im = im.resize((im.width * 3, im.height * 3), Image.NEAREST); im.save(out)


if __name__ == '__main__':
    if sys.argv[1:2] == ['preview']:
        T = {l.split('\t')[0]: l.split('\t')[3] for l in open(os.path.join(ROOT, 'work/trans/sw_ko.tsv'), encoding='utf-8').read().splitlines()[1:]}
        ids = sys.argv[2:] or ['00196', '01055', '00608', '00141', '01395', '00098']
        os.makedirs(os.path.join(ROOT, 'work/view'), exist_ok=True)
        preview([T[k] for k in ids], os.path.join(ROOT, 'work/view/font_preview.png'))
