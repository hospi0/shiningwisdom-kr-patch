"""원문 대사 줄의 픽셀 폭 분포(맵 글꼴의 글자별 폭 u16 + 글자 사이 1px — my files/할일/1·3.png 잉크 폭으로 확인) — 상자 폭 «벼랑» 읽기
python tools/swwidth.py"""
import os, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import swtext, swocr
sys.stdout.reconfigure(encoding='utf-8')
KH = swtext.kanji_by_hash(); W = collections.Counter(); ex = {}; nl = collections.Counter()
for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
    d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
    font = swocr.struct_u(d, hdr) - load; m = swtext.map_charmap(d, load, hdr, KH)
    wid = lambda c: struct.unpack_from('>H', d, font + (c - 0x20) * 32)[0]
    for bi, n, p, L, codes in swtext.messages(d, load, hdr)[1]:
        line = []; lines = [line]
        for c in codes[:-1]:
            if c in (3, 5): line = []; lines.append(line)          # 03 줄바꿈 · 05 쪽 넘김
            else: line.append(c)
        nl[len(lines)] += 1
        for ln in lines:
            if any(c < 0x20 and c not in (3,) for c in ln) and 0x0A in ln: continue     # 이름 칸 든 줄은 뺀다
            g = [c for c in ln if c >= 0x20]; w = sum(wid(c) + 1 for c in g) - (1 if g else 0)   # 글자 사이 1px(스샷 실측)
            W[w] += 1; ex.setdefault(w, (f, swtext.render(ln + [0], m)))
print('줄 수 분포', sorted(nl.items()))
acc = 0; tot = sum(W.values())
for w in sorted(W):
    acc += W[w]
    if w >= 180: print('%4d px %4d 줄  누적 %5.1f%%  %s' % (w, W[w], 100 * acc / tot, ex[w][1][:30]))
