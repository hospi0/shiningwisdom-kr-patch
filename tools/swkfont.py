"""전역 한글 글꼴 — LowRAM 0x002CF800 에 게임 형식 글꼴([u16 폭][u16 × 15줄], 코드 c → 0x002CF800 + (c−0x20)×32)
  싣는 법: A.BIN 메인 루프가 매번 X09.BIN 을 0x06076000 에 읽고 바로 실행(0x06010F04) → 이어서 X04 가 같은 자리를 덮는다.
          ⇒ X09 끝에 [펼치기 코드][압축 글꼴] 을 붙이고 X09 진입 리터럴(파일 +8, 원래 0x0607600C)만 펼치기 코드로.
          펼치기 코드는 LowRAM 에 글꼴을 펼친 뒤 원래 진입점으로 JMP(PR 그대로 → 원래처럼 적재 함수로 돌아감).
          X09 는 X04 끝(0x0607CCA0)까지만 — 그 위는 살아 있는 데이터(스테이트 s1‥s4).
  코드: 0x20‥0x7F ASCII(게임 글꼴, 공백 폭 4, 그림 없는 ~`^{}|\\ 은 갈무리) · 0x80‥0xFF 가나(게임 글꼴 그대로 — 주인공 이름이 가나)
        · 0x100‥ 한글·부호(번역에 쓰인 것, 유니코드 순)
  압축(MSB 먼저 비트열): 글자마다 [폭 4][y0 4][h 4][cols 4] + h줄 × cols 비트(왼쪽부터). h=0 이면 빈 칸.
python tools/swkfont.py   → work/build/X09.BIN · work/build/kfont.bin(펼친 글꼴) + 시뮬레이터 검증"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swtext, swocr, swfont
from sh2asm import Asm
import sh2sim

FONT_BASE = 0x002CF800                  # ⛔0x290000 은 큰 맵의 CHR(LowRAM 0x200000‥, 최대 M013 → 0x2CF200)이 덮는다(실기 크래시 2026-10-04 s7). 0x2E0000‥ = 사운드
LOWRAM_END = 0x002E0000
X09_LOAD = 0x06076000
X09_ENTRY = 0x0607600C
X09_LIMIT = 0x0607CCA0 - X09_LOAD          # X04 끝 — 27,808 B
MISSING = '~`^{}|\\'
import swname                                        # 이름판: 가나 코드 자리의 한글 음절(대사 글꼴에도 같은 코드로)
NAMEMAP = swname.namemap()


def ko_texts():
    return [l.split('\t')[3] for l in open(os.path.join(ROOT, 'work/trans/sw_ko.tsv'), encoding='utf-8').read().splitlines()[1:]]


def extra_chars(texts=None):
    A = swfont.game_ascii()
    chars = set()
    for t in texts if texts is not None else ko_texts():
        for ch in re.sub(r'\{[0-9A-F]{4}\}|\\n', '', t):
            if ch not in A or ch in MISSING:
                chars.add(ch)
    return sorted(c for c in chars if not (0x20 <= ord(c) < 0x80))


def codemap(extras=None):
    """글자 → 코드(ASCII 는 그대로, 나머지 0x100‥)"""
    extras = extra_chars() if extras is None else extras
    m = {chr(c): c for c in range(0x20, 0x80)}
    for i, ch in enumerate(extras):
        m[ch] = 0x100 + i
    return m


def glyphs(extras=None):
    """코드 0x20 부터 [(폭, 15줄)]"""
    extras = extra_chars() if extras is None else extras
    d = open(os.path.join(swtext.DISC, 'M001.ETC'), 'rb').read(); load, hdr = swtext.header(d)
    font = swocr.struct_u(d, hdr) - load
    G = []
    for c in range(0x20, 0x100):
        o = font + (c - 0x20) * 32
        w, rows = struct.unpack_from('>H', d, o)[0], list(struct.unpack_from('>15H', d, o + 2))
        ch = chr(c)
        if ch == ' ':
            w, rows = swfont.SPACE, [0] * 15
        elif ch in MISSING:
            w, rows = swfont.glyph_bdf(ch)
        if c in NAMEMAP:                                     # 이름판 한글(가나 코드 자리, tools/swname.py)
            w, rows = swfont.glyph(NAMEMAP[c], {})
        G.append((w, rows))
    for ch in extras:
        G.append(swfont.glyph(ch, {}))
    return G


class BitW:
    def __init__(s): s.out = bytearray(); s.acc = 0; s.n = 0
    def put(s, v, n):
        for i in range(n - 1, -1, -1):
            s.acc = s.acc << 1 | (v >> i & 1); s.n += 1
            if s.n == 8: s.out.append(s.acc); s.acc = 0; s.n = 0
    def bytes(s):
        return bytes(s.out) + (bytes([s.acc << (8 - s.n)]) if s.n else b'')


def pack(G):
    bw = BitW()
    for w, rows in G:
        assert w < 16, w
        ys = [i for i, r in enumerate(rows) if r]
        if not ys:
            bw.put(w, 4); bw.put(0, 12); continue
        y0, y1 = ys[0], ys[-1]; h = y1 - y0 + 1
        cols = max(16 - ((r & -r).bit_length() - 1) for r in rows if r)
        assert cols < 16 and h < 16, (cols, h)
        bw.put(w, 4); bw.put(y0, 4); bw.put(h, 4); bw.put(cols, 4)
        for r in rows[y0:y1 + 1]:
            bw.put(r >> (16 - cols), cols)
    return bw.bytes()


def expand_py(G):
    out = bytearray()
    for w, rows in G:
        out += struct.pack('>H15H', w, *rows)
    return bytes(out)


def stub(base, count, data_addr):
    """펼치기 코드 — r0‥r7 + r8‥r11(쌓아 두고 복원). getbit = r11 이 가리키는 서브루틴(T = 비트)."""
    def build(getbit_addr):
        a = Asm(base); n = [0]
        def lab():
            n[0] += 1; return 'L%d' % n[0]
        def getbits(k):                      # → r0 (r2 씀)
            a.movi(k, 'r2'); a.movi(0, 'r0'); L = lab(); a.label(L)
            a.jsr('r11'); a.nop(); a.rotcl('r0'); a.dt('r2'); a.bf(L)
        a.stspr_predec('r15')
        for r in ('r8', 'r9', 'r10', 'r11'):
            a.movl_predec(r, 'r15')
        a.movl_pc('dst', 'r4'); a.movl_pc('cnt', 'r5'); a.movl_pc('src', 'r6'); a.movl_pc('getbit', 'r11')
        a.movi(0, 'r1')
        a.label('glyph')
        a.movi(0, 'r0'); a.mov('r4', 'r3')
        for _ in range(8):
            a.movl_store('r0', 'r3'); a.addi(4, 'r3')
        getbits(4); a.movw_store('r0', 'r4')
        getbits(4); a.mov('r0', 'r8')
        getbits(4); a.mov('r0', 'r9')
        getbits(4); a.mov('r0', 'r10')
        a.tst('r9', 'r9'); a.bt('next')
        a.mov('r8', 'r3'); a.shll('r3'); a.add('r4', 'r3'); a.addi(2, 'r3')
        a.label('row')
        a.movi(0, 'r0'); a.movi(16, 'r2'); a.mov('r10', 'r8')
        a.label('bit')
        a.tst('r8', 'r8'); a.bt('zero')
        a.dt('r8'); a.jsr('r11'); a.nop(); a.rotcl('r0'); a.bra('cont'); a.nop()
        a.label('zero')
        a.clrt(); a.rotcl('r0')
        a.label('cont')
        a.dt('r2'); a.bf('bit')
        a.movw_store('r0', 'r3'); a.addi(2, 'r3'); a.dt('r9'); a.bf('row')
        a.label('next')
        a.addi(32, 'r4'); a.dt('r5'); a.bf('glyph')
        for r in ('r11', 'r10', 'r9', 'r8'):
            a.movl_postinc('r15', r)
        a.ldspr_postinc('r15')
        a.movl_pc('entry', 'r0'); a.jmp('r0'); a.nop()
        # getbit: r1 = 남은 비트, r7 = 비트 버퍼(왼쪽 정렬), r6 = 읽을 곳 → T
        a.label('getbit')
        a.tst('r1', 'r1'); a.bf('have')
        a.movb_postinc('r6', 'r7'); a.shll16('r7'); a.shll8('r7'); a.movi(8, 'r1')
        a.label('have')
        a.dt('r1'); a.shll('r7'); a.rts(); a.nop()
        a.defl('dst', FONT_BASE); a.defl('cnt', count); a.defl('src', data_addr)
        a.defl('getbit', getbit_addr); a.defl('entry', X09_ENTRY)
        code, _ = a.assemble()
        return code, a.labels['getbit']
    code, gb = build(0)
    code2, gb2 = build(gb)
    assert gb2 == gb and len(code2) == len(code)
    return code2


def build_x09(G):
    import swmenu
    assert FONT_BASE + len(G) * 32 <= swmenu.BLOB, ('대사 글꼴이 블롭과 겹침', hex(FONT_BASE + len(G) * 32))
    x9 = bytearray(open(os.path.join(swtext.DISC, 'X09.BIN'), 'rb').read())
    assert struct.unpack_from('>I', x9, 8)[0] == X09_ENTRY
    data = pack(G)
    base_off = (len(x9) + 3) & ~3
    code = stub(X09_LOAD + base_off, len(G), 0)                # 크기만 먼저
    data_off = (base_off + len(code) + 3) & ~3
    code = stub(X09_LOAD + base_off, len(G), X09_LOAD + data_off)
    out = x9 + bytes(base_off - len(x9)) + code
    out += bytes(data_off - len(out)) + data
    struct.pack_into('>I', out, 8, X09_LOAD + base_off)
    assert len(out) <= X09_LIMIT, ('X09 자리 초과', len(out), X09_LIMIT)
    return bytes(out), len(data)


def simulate(x9new, n):
    mem = sh2sim.Mem()
    mem.map(X09_LOAD, x9new + bytes(0x10000))
    mem.map(0x00200000, bytes(0x100000))
    mem.map(0x06090000, bytes(0x10000))                         # 쌓개
    cpu = sh2sim.CPU(mem, X09_LOAD, stack_top=0x060A0000)
    cpu.pr = 0x12345678
    steps = cpu.run(X09_ENTRY, max_steps=50_000_000)
    assert cpu.pr == 0x12345678 and cpu.r[15] == 0x060A0000, '복귀 상태 다름'
    buf, o = mem._find(FONT_BASE)
    return bytes(buf[o:o + n * 32]), steps


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ex = extra_chars(); G = glyphs(ex)
    x9new, nd = build_x09(G)
    want = expand_py(G)
    got, steps = simulate(x9new, len(G))
    ok = got == want
    os.makedirs(os.path.join(ROOT, 'work/build'), exist_ok=True)
    open(os.path.join(ROOT, 'work/build/X09.BIN'), 'wb').write(x9new)
    open(os.path.join(ROOT, 'work/build/kfont.bin'), 'wb').write(want)
    print('글자 %d (한글·부호 %d, 코드 0x100‥0x%X) · 압축 %d B · X09 %d → %d B (한도 %d, 남음 %d) · 시뮬레이터 %s (%d 단계)' % (
        len(G), len(ex), 0xFF + len(ex), nd, 7198, len(x9new), X09_LIMIT, X09_LIMIT - len(x9new), '일치' if ok else '⚠다름', steps))
    if not ok:
        i = next(i for i in range(len(want)) if got[i] != want[i])
        print('첫 차이 글자', i // 32, got[i // 32 * 32:i // 32 * 32 + 32].hex(), want[i // 32 * 32:i // 32 * 32 + 32].hex())
        sys.exit(1)


if __name__ == '__main__':
    main()
