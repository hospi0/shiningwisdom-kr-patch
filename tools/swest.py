"""맵(ETC)별 한글 수요·자리 추정 — 덩어리 [글꼴][트리 데이터][대사 묶음] 을 한글로 다시 만들면 원래 자리에 드는가
  덩어리 = 머리말 +00(글꼴) ‥ 머리말 시작. 글꼴 = 0x20‥끝 연속 32 B 칸, 한글은 0x80(가나 자리)부터 맵별 빈도순.
  대사 = 문장마다 [길이 1 B][허프만 비트](직전 바이트별 트리, 직전 0 에서 시작, u16 0000 끝). 길이 ≤ 255.
  트리 = 쓰인 직전 바이트마다 (잎 목록 n B, 모양 비트 2n−1). 트리쌍 표(2 KB)는 머리말 뒤 따로 있어 그대로.
python tools/swest.py"""
import heapq, math, os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swtext, swfont
TOK = re.compile(r'\{([0-9A-F]{4})\}')
ETC_END = 0x14000                     # 적재 0x060BC000 ‥ 0x060D0000(MAP 버퍼)


def ko_table():
    T = {}
    for l in open(os.path.join(ROOT, 'work/trans/sw_ko.tsv'), encoding='utf-8').read().splitlines()[1:]:
        k, f, o, t = l.split('\t'); T[o] = t
    return T


def huff_lengths(freq):
    if len(freq) == 1:
        return {next(iter(freq)): 1}
    h = [(n, i, (s,)) for i, (s, n) in enumerate(freq.items())]; heapq.heapify(h); L = collections.Counter(); i = len(h)
    while len(h) > 1:
        a = heapq.heappop(h); b = heapq.heappop(h)
        for s in a[2] + b[2]:
            L[s] += 1
        heapq.heappush(h, (a[0] + b[0], i, a[2] + b[2])); i += 1
    return L


def to_codes(t, cmap):
    out = []
    for part in TOK.split(t)[0::1]:
        pass
    i = 0
    for m in re.finditer(r'\{([0-9A-F]{4})\}|\\n|(.)', t, re.S):
        if m.group(1):
            out.append(int(m.group(1), 16))
        elif m.group(0) == '\\n':
            out.append(3)
        else:
            out.append(cmap[m.group(2)])
    return out + [0]


def estimate(f, KO):
    d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
    u = lambda o: struct.unpack_from('>I', d, o)[0]
    font = u(hdr) - load; span = hdr - font
    KH = swtext.kanji_by_hash(); m = swtext.map_charmap(d, load, hdr, KH)
    msgs = [swtext.render(c, m) for *_, c in swtext.messages(d, load, hdr)[1]]
    kts = [KO[t] for t in msgs]
    A = swfont.game_ascii()
    chars = collections.Counter(ch for t in kts for ch in re.sub(r'\{[0-9A-F]{4}\}|\\n', '', t))
    extra = [ch for ch, n in chars.most_common() if ch not in A]          # 한글 + 게임 글꼴에 없는 부호
    cmap = {ch: ord(ch) for ch in A}
    for i, ch in enumerate(extra):
        cmap[ch] = 0x80 + i if i < 0x80 else 0x100 + (i - 0x80)
    top = max(cmap[ch] for ch in extra) if extra else 0x7F
    font_b = (top + 1 - 0x20) * 32
    streams = []
    for t in kts:
        b = b''.join(struct.pack('>H', c) for c in to_codes(t, cmap)); streams.append(b)
    ctx = collections.defaultdict(collections.Counter)
    for b in streams:
        prev = 0
        for x in b:
            ctx[prev][x] += 1; prev = x
    L = {p: huff_lengths(c) for p, c in ctx.items()}
    tree_b = sum(len(c) + math.ceil((2 * len(c) - 1) / 8) for c in ctx.values())
    msg_b = [];
    for b in streams:
        prev = 0; bits = 0
        for x in b:
            bits += L[prev][x]; prev = x
        msg_b.append(math.ceil(bits / 8))
    text_b = sum(1 + n for n in msg_b)
    new = font_b + tree_b + text_b
    return dict(f=f, size=len(d), span=span, syl=len(extra), font=font_b, tree=tree_b, text=text_b, new=new,
                spare=span - new, tail=ETC_END - len(d), maxmsg=max(msg_b), nmsg=len(msgs))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    KO = ko_table(); R = []
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        r = estimate(f, KO); R.append(r)
        print('%-9s 문장%4d 음절·기호%4d  글꼴%6d 트리%5d 대사%6d = %6d / 원래 덩어리 %6d → 남음 %6d · 파일 뒤 여유 %6d · 최장 %3d B%s' % (
            r['f'], r['nmsg'], r['syl'], r['font'], r['tree'], r['text'], r['new'], r['span'], r['spare'], r['tail'], r['maxmsg'],
            '  ⚠넘침' if r['spare'] + r['tail'] < 0 else ('  (뒤 여유 필요)' if r['spare'] < 0 else '')))
    print('최대 음절', max(r['syl'] for r in R), '· 덩어리 안 부족', sum(r['spare'] < 0 for r in R), '· 뒤까지 합쳐도 부족', sum(r['spare'] + r['tail'] < 0 for r in R))


if __name__ == '__main__':
    main()
