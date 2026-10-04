"""번역 줄 폭 검사 — 대화창 글자 영역 288px (my files/할일/1·3.png 실측: 글자 시작 115 → 안쪽 테두리 1633, 화소 5.27배)
  폭 = Σ(글자 폭 + 1) − 1. 글자 폭 = tools/swfont.py(한글 11 · 공백 4 · ASCII 원래 글꼴 · 그 밖 갈무리11) · 이름 {000A} = 78px(원문이 남긴 최대, 가나 6자)
  줄 = \n(03) 또는 {0005}(쪽 넘김)로 끊음. {0015} 든 문장(저장 화면 등 다른 창)은 따로 표시.
python tools/swfit.py [번역 tsv=work/trans/sw_ko.tsv]"""
import os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import swtext, swocr
LIMIT = 288; NAME = 78
d = open(os.path.join(swtext.DISC, 'M001.ETC'), 'rb').read(); load, hdr = swtext.header(d)
font = swocr.struct_u(d, hdr) - load
ASCII = {chr(c): struct.unpack_from('>H', d, font + (c - 0x20) * 32)[0] for c in range(0x20, 0x7F)}
EXTRA = {'…': 12, '·': 7, '・': 7, '~': 10, '「': 7, '」': 7, '『': 8, '』': 8, '♪': 12, '♥': 12}
TOK = re.compile(r'(\{[0-9A-F]{4}\})')


def width(line):
    import swfont
    global _A
    if '_A' not in globals():
        _A = swfont.game_ascii()
    w = []
    for part in TOK.split(line):
        if TOK.fullmatch(part):
            if part == '{000A}': w.append(NAME)
            continue
        for ch in part:
            w.append(swfont.glyph(ch, _A)[0])
    return sum(x + 1 for x in w) - (1 if w else 0)


def lines(t):
    return re.split(r'\\n|\{0005\}', t)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p = sys.argv[1] if len(sys.argv) > 1 else 'work/trans/sw_ko.tsv'
    over = []; dist = collections.Counter()
    for ln in open(p, encoding='utf-8').read().splitlines()[1:]:
        k, f, o, t = ln.split('\t')
        if k.startswith('S'): continue
        for i, s in enumerate(lines(t)):
            w = width(s); dist[w // 20 * 20] += 1
            if w > LIMIT: over.append((w, k, i + 1, '{0015}' in o, s))
    print('줄 폭 분포(20px 단위)', sorted(dist.items()))
    print('넘침 %d줄 (그중 다른 창 {0015} %d)' % (len(over), sum(x[3] for x in over)))
    return over


if __name__ == '__main__':
    for w, k, i, other, s in sorted(main(), reverse=True)[:40]:
        print('%4d %s 줄%d %s %s' % (w, k, i, '[창]' if other else '', s))
