"""ETC 대사 허프만 재인코더 + 덩어리 다시 쓰기
  대사 = 문장마다 [길이 1 B][비트열] — u16 BE 코드를 바이트로 풀어, 직전 바이트별 트리로 압축(직전 0 에서 시작, MSB 먼저, 0000 으로 끝).
  트리 = 트리쌍 표(머리말 +04, u32 × 512 = (잎 목록, 모양 비트) × 직전 바이트 256) — 잎 목록 바로 뒤가 모양(S − L = 잎 수),
         모양 = 전위 순회 1 = 잎 · 0 = 안쪽(왼쪽 = 0). 안 쓰는 직전 바이트 = (0, 0).
  묶음 표(머리말 +08, u32 묶음 주소 … 0 끝) — 문장 번호 id = 묶음 id>>8 · 안에서 id&0xFF.
  덩어리 [시작, 원래 마지막 문장 끝) 을 [트리][묶음 0][묶음 1]… 로 다시 채운다(남는 곳 0).
python tools/swenc.py roundtrip   → 원문 일본어를 다시 압축해 42개 ETC 왕복(코드열 동일) 검사"""
import heapq, os, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swtext, swhuff

LOAD_MASK = ~0xFFF


def huff_tree(freq):
    """→ 중첩 튜플(왼쪽 0, 오른쪽 1) 또는 잎 하나"""
    if len(freq) == 1:
        return next(iter(freq))
    h = [(n, i, s) for i, (s, n) in enumerate(sorted(freq.items()))]
    heapq.heapify(h); i = len(h)
    while len(h) > 1:
        a = heapq.heappop(h); b = heapq.heappop(h)
        heapq.heappush(h, (a[0] + b[0], i, (a[2], b[2]))); i += 1
    return h[0][2]


def tree_bytes(t):
    leaves = []; bits = []; codes = {}
    def walk(n, path):
        if isinstance(n, tuple):
            bits.append(0); walk(n[0], path + [0]); walk(n[1], path + [1])
        else:
            bits.append(1); leaves.append(n); codes[n] = path
    walk(t, [])
    shape = bytearray((len(bits) + 7) // 8)
    for i, b in enumerate(bits):
        if b:
            shape[i // 8] |= 0x80 >> (i % 8)
    return bytes(leaves), bytes(shape), codes


def encode(messages):
    """messages: [[u16 …(끝 0 포함)]] → (트리 {직전: (잎, 모양)}, [문장 바이트(길이 B 포함)])"""
    streams = [b''.join(struct.pack('>H', c) for c in m) for m in messages]
    ctx = collections.defaultdict(collections.Counter)
    for b in streams:
        prev = 0
        for x in b:
            ctx[prev][x] += 1; prev = x
    trees = {}; codes = {}
    for p, f in ctx.items():
        lv, sh, cd = tree_bytes(huff_tree(f)); trees[p] = (lv, sh); codes[p] = cd
    out = []
    for b in streams:
        bits = []; prev = 0
        for x in b:
            bits += codes[prev][x]; prev = x
        n = (len(bits) + 7) // 8
        assert n <= 255, ('문장 255 B 초과', n)
        body = bytearray(n)
        for i, v in enumerate(bits):
            if v:
                body[i // 8] |= 0x80 >> (i % 8)
        out.append(bytes([n]) + bytes(body))
    return trees, out


def text_end(d):
    """원래 마지막 문장 끝(그 뒤 ‥ 머리말 사이엔 다른 데이터가 있을 수 있다 — M011 «MAPNO Def», M232 «SHINING W…»)"""
    load, hdr = swtext.header(d); _, ms = swtext.messages(d, load, hdr)
    return ms[-1][2] + ms[-1][3] + 1


def rebuild(d, messages, start=None, font_ptr=None):
    """ETC 바이트 d 의 덩어리를 다시 쓴다. messages = 묶음 순서대로 문장 코드열 목록. start = 덩어리 시작(기본 원래 글꼴 자리)."""
    limit = text_end(bytes(d))
    d = bytearray(d); load, hdr = swtext.header(bytes(d))
    u = lambda o: struct.unpack_from('>I', d, o)[0]
    font = u(hdr) - load
    start = font if start is None else start
    tab = u(hdr + 4) - load; btab = u(hdr + 8) - load
    nb = 0
    while u(btab + 4 * nb) and load <= u(btab + 4 * nb) < load + len(d):
        nb += 1
    assert len(messages) <= 256 * nb, ('묶음 수 부족', len(messages), nb)
    trees, msgs = encode(messages)
    blk = bytearray(); ptr = [0] * 512
    for p in sorted(trees):
        lv, sh = trees[p]
        L = start + len(blk); blk += lv; S = start + len(blk); blk += sh
        ptr[2 * p] = load + L; ptr[2 * p + 1] = load + S
    banks = []
    for bi in range(nb):
        banks.append(load + start + len(blk))
        for m in msgs[bi * 256:(bi + 1) * 256]:
            blk += m
    end = start + len(blk)
    assert end <= limit, ('덩어리 넘침', end - limit)
    d[start:limit] = bytes(blk) + bytes(limit - end)
    for i in range(512):
        struct.pack_into('>I', d, tab + 4 * i, ptr[i])
    for bi in range(nb):
        struct.pack_into('>I', d, btab + 4 * bi, banks[bi])
    if font_ptr is not None:
        struct.pack_into('>I', d, hdr, font_ptr)
    return bytes(d), limit - end


def foreign_refs(d):
    """덩어리 [글꼴, 머리말) 안을 가리키는 u32 — 트리쌍 표·묶음 표·머리말 +00 말고"""
    load, hdr = swtext.header(d); u = lambda o: struct.unpack_from('>I', d, o)[0]
    font = u(hdr) - load; tab = u(hdr + 4) - load; btab = u(hdr + 8) - load
    skip = set(range(tab, tab + 2048)) | {btab + 4 * i for i in range(8)} | {hdr}
    out = []
    for o in range(0, len(d) - 3, 2):
        if o in skip:
            continue
        v = u(o)
        if load + font <= v < load + hdr:
            out.append((o, v - load))
    return out


def roundtrip():
    sys.stdout.reconfigure(encoding='utf-8')
    bad = 0
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
        _, ms = swtext.messages(d, load, hdr)
        codes = [c for *_, c in ms]
        font = struct.unpack_from('>I', d, hdr)[0] - load
        tree_start = min(p - load for p in struct.unpack_from('>512I', d, struct.unpack_from('>I', d, hdr + 4)[0] - load) if p)
        new, spare = rebuild(d, codes, start=tree_start)
        _, ms2 = swtext.messages(new, load, hdr)
        same = [c for *_, c in ms2] == codes
        fr = foreign_refs(d)
        bad += (not same) or bool(fr)
        print('%-9s 문장 %3d  왕복 %s  덩어리 남음 %5d B(원래 트리+대사 자리 기준)  다른 포인터 %s' % (f, len(codes), '일치' if same else '⚠다름', spare, fr[:3] if fr else '없음'))
    print('문제', bad)


if __name__ == '__main__':
    if sys.argv[1:] == ['roundtrip']:
        roundtrip()
