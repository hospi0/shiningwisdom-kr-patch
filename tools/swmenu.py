"""메뉴(X10 1바이트 문구) 한글 — 8×8 셀 (사용자 결정 2026-10-04: A안)
  그리는 길(X02): 문자열 그리기 0x0604F92A / 0x0604F98C(가타카나→히라가나 변환판) → 글자 하나 0x0604F782
                 → 셀 쓰기 0x0604F52C: 창 버퍼[y×폭+x] = (코드<<1)|0x1000. 창 표 0x0605C2DC(16 B: 버퍼·…·+4 폭).
                 대사 끼워 넣기({000A} 이름·{000E} 아이템) = 0x0605A870: 바이트 → u16 → 대사 버퍼 0x0605E53A(번호 0x0605E93A).
  2바이트: 문자열 안 [앞 1‥7][뒤 b](b = 08‥FD, DE·DF 제외) = 메뉴 코드 m(0x100‥). 표 두 개(m−0x100 → 셀 값 / 대사 코드).
  셀: 갈무리7(7×7) + 오른쪽 아래 그림자(색 0x3F 잉크 · 0x3E 그림자, 원래 메뉴 글꼴과 같은 양식), VDP2 VRAM 빈 곳(스테이트 4장 모두 0):
      0x26800‥0x28000 · 0x29000‥0x2B800 · 0x2EC00‥0x30000. 셀 값 = 0x1000 | (주소/0x20 & 0xFFF).
  싣기: X01(매 루프 X02 보다 먼저 읽고 실행, BSS 0x06033B04‥0x06044C84 는 시작 때 지움 → 덧붙여도 안전) 끝에
        [설치 코드][블롭] → 진입 리터럴(+8)을 설치 코드로 → 블롭을 LowRAM 0x002D8800(BLOB) 에 복사 → 원래 진입 0x0603000C.
  후킹(전부 LowRAM): X02 진입(원래 초기화 뒤 셀 VRAM 업로드) · 붙이기 · 문자열 그리기 2개(함수 머리 = 점프, 2바이트 → v=셀/2).
  ⛔셀 쓰기 0x0604F52C 는 후킹 금지 — 대화창이 0x100 이상 코드로 글자 그림 셀을 쓴다.
  X02 덧패치: ⛔글자 하나(0x0604F782)는 손대지 않음(다른 호출자가 부호 확장 바이트를 넘김 → EXTU.W 면 깨짐) · 글자 수 세기 0x060544C4 CMP/EQ #DF → TST #F8(앞 바이트는 안 셈).
  X10: 목록 포인터 4개(몬스터·아이템·지명·설명, 표 0x060B0BA4+4k) → LowRAM 문자열.
python tools/swmenu.py   → work/build/X01.BIN · X02.BIN · X10.BIN + 시뮬레이터 검증"""
import os, re, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swkfont
from sh2asm import Asm
import sh2sim

DISC = os.path.join(ROOT, 'work', 'disc')
BDF7 = r'C:\claude\utils\font\Galmuri-v2.40.3\Galmuri7.bdf'
BLOB = 0x002D8800                       # 대사 글꼴(0x2CF800‥) 뒤 — 끝은 0x2E0000(사운드) 전
X01_LOAD, X01_ENTRY, X01_LIMIT = 0x06030000, 0x0603000C, 0x06044C84 - 0x06030000
X02_LOAD, X02_ENTRY = 0x0604F000, 0x0604F00C
X10_LOAD = 0x060A0000
VRAM = 0x25E00000
REGIONS = [(0x26800, 0x27A00), (0x32000, 0x34000), (0x36000, 0x38000)]
# ⛔0x27A00‥0x29200 = 저장 화면 큰 글씨 창(「始める」「本体RAM」) 그림 — X02 0x06054C8E 가 0x1800 B 복사(실기 2026-10-04 s12·s13: «마» 깨짐·창에 한글 뒤섞임)
# ⛔0x29000‥0x2B800·0x2EC00‥ 은 장비 메뉴 L/R 전환 때 다른 페이지가 쓰거나 지운다(실기 2026-10-04 s6). 맵(64×64 1워드 = 8 KB) 뒤 반쪽은 아무도 안 씀(6 스테이트 모두 같은 설정).
LISTS = {3: 0x10BB0, 4: 0x10BB4, 9: 0x10BC8, 10: 0x10BCC}            # X10 파일 오프셋의 목록 포인터
LOWB = [b for b in range(8, 0xFE) if b not in (0xDE, 0xDF)]
# ⛔둘째 바이트 01‥07 금지 — 글자 수 세기(0x060544C4 TST #F8)가 앞 바이트로 보고 안 셈 → 지명 팝업 창(글자 수+4, X02 0x06059E38)이 좁아짐(실기 2026-10-04 s14 «간»=01 03)
PUTCHAR = 0x0604F782
# X02 메뉴·저장 화면 문자열(가타카나, draw2 로 히라가나 표시) → LowRAM 으로 옮기고 포인터(각 1‥2곳) 고침. «… =» 줄은 원래 9칸에 맞춤(숫자 칸 정렬)
X02_STR = {0x0605B584: '컬러 폰트를 만들 수 없음', 0x0605B598: '예! ', 0x0605B59C: '아니오',   # 같은 칸에 번갈아 그림 → «예!» 뒤 공백으로 길이 맞춤(안 하면 아니오의 «오» 남음, 사용자 2026-10-04)
           0x0605B628: '도구', 0x0605B630: '오브', 0x0605B638: '장비', 0x0605BF9C: '도구',
           0x0605BA54: '카트리지RAM', 0x0605BA60: '본체RAM', 0x0605BA70: '처음', 0x0605BA78: '부터', 0x0605BA7C: '시작',
           0x0605BA84: '신규', 0x0605BA88: '처음부터', 0x0605BA90: '저장 데이터', 0x0605BA9C: '의 수',
           0x0605BAC4: '전체 용량   =', 0x0605BAD0: '블록 수    =', 0x0605BADC: '1B 크기   =',
           0x0605BAE8: '남은 용량   =', 0x0605BAF4: '남은 블록 수 =', 0x0605BB00: '기록 가능   ='}


def galmuri7():
    g = {}
    txt = open(BDF7, encoding='utf-8').read()
    for m in re.finditer(r'ENCODING (-?\d+)\n(.*?)ENDCHAR', txt, re.S):
        b = re.search(r'BBX (-?\d+) (-?\d+) (-?\d+) (-?\d+)', m.group(2)); bm = re.search(r'BITMAP\n(.*)', m.group(2), re.S)
        if b and bm:
            g[int(m.group(1))] = tuple(int(x) for x in b.groups()) + ([r for r in bm.group(1).split() if r],)
    return g


def cell8(ch, G):
    """→ 64 B (8bpp): 잉크 0x3F, 그림자(+1,+1) 0x3E. 밑선 = 6행(7×7 한글이 0‥6행)"""
    w, h, ox, oy, rows = G[ord(ch)]
    ink = [[0] * 8 for _ in range(8)]
    for i, r in enumerate(rows):
        y = 6 - (oy + h - 1) + i
        v = int(r, 16) >> (len(r) * 4 - w)
        for x in range(w):
            if v >> (w - 1 - x) & 1 and 0 <= y < 8 and 0 <= ox + x < 8:
                ink[y][ox + x] = 1
    out = bytearray(64)
    for y in range(8):
        for x in range(8):
            if ink[y][x]:
                out[y * 8 + x] = 0x3F
            elif x > 0 and y > 0 and ink[y - 1][x - 1]:
                out[y * 8 + x] = 0x3E
    return bytes(out)


def sys_rows():
    """[(번호, 목록, 순번, 번역)] — 번역 = work/trans/sw_ko.tsv 의 S 줄"""
    src = {l.split('\t')[0]: l.split('\t') for l in open(os.path.join(ROOT, 'work/text/sw_sys.tsv'), encoding='utf-8').read().splitlines()[1:]}
    ko = {l.split('\t')[0]: l.split('\t')[3] for l in open(os.path.join(ROOT, 'work/trans/sw_ko.tsv'), encoding='utf-8').read().splitlines()[1:] if l.startswith('S')}
    names = {'몬스터': 3, '아이템·오브·장비': 4, '지명': 9, '설명': 10}
    return [(k, names[src[k][2]], int(src[k][3]), ko[k]) for k in sorted(src)]


def plan():
    rows = sys_rows()
    src = {l.split('	')[0]: l.split('	')[5] for l in open(os.path.join(ROOT, 'work/text/sw_sys.tsv'), encoding='utf-8').read().splitlines()[1:]}
    for k in LISTS:                                                   # ⛔목록별 원문 최대 칸 수(탁점 빼고)를 넘으면 막음
        jm = max(len([c for c in src[i] if c not in '゛゜']) for i, kk, _, t in rows if kk == k)
        bad = [(i, t) for i, kk, _, t in rows if kk == k and len(t) > jm]
        assert not bad, ('메뉴 칸 초과(목록 %d, 원문 최대 %d)' % (k, jm), bad)
    chars = sorted({ch for t in [r[3] for r in rows] + list(X02_STR.values()) for ch in t if not (0x20 <= ord(ch) < 0x7F)})
    G = galmuri7()
    miss = [c for c in chars if ord(c) not in G]
    assert not miss, ('갈무리7 에 없는 글자', miss)
    cap = sum((b - a) // 64 for a, b in REGIONS)
    assert len(chars) <= cap, ('VRAM 셀 부족', len(chars), cap)
    mcode = {}; cells = {}; slots = []
    for a, b in REGIONS:
        slots += list(range(a, b, 64))
    for i, ch in enumerate(chars):
        mcode[ch] = (1 + i // len(LOWB)) << 8 | LOWB[i % len(LOWB)]
        cells[ch] = slots[i]
    dlg = swkfont.codemap()
    return rows, chars, mcode, cells, dlg, G


def encode(t, mcode):
    out = bytearray()
    for ch in t:
        if 0x20 <= ord(ch) < 0x7F:
            out.append(ord(ch))
        else:
            out += struct.pack('>H', mcode[ch])
    assert 0 not in out and 0xFF not in out
    return bytes(out)


def hooks(base, tabs):
    """후킹 코드 — tabs: cellmap·dlgmap·업로드 [(src, dst, longs)]"""
    def build(lab):
        a = Asm(base)
        L = lambda name: lab.get(name, 0)
        def const(name, r):                                           # 워드 리터럴 대신(풀 거리 초과 방지)
            v = {'w100': 0x100, 'wDE': 0xDE, 'wDF': 0xDF, 'wA6': 0xA6, 'wBF': 0xBF, 'wDD': 0xDD}[name]
            if v == 0x100:
                a.movi(1, r); a.shll8(r)
            else:
                a.movi(v, r); a.extub(r, r)
        # ── 붙이기 append(r4 바이트열) → 대사 버퍼 ──
        a.label('append')
        a.movl_pc('dbuf', 'r6'); a.movl_pc('didx', 'r5'); a.movw_load('r5', 'r1')
        a.label('ap_loop')
        a.movb_postinc('r4', 'r2'); a.extub('r2', 'r2'); a.tst('r2', 'r2'); a.bt('ap_end')
        a.movi(8, 'r3'); a.cmphs('r3', 'r2'); a.bt('ap_st')
        a.shll8('r2'); a.movb_postinc('r4', 'r3'); a.extub('r3', 'r3'); a.orr('r3', 'r2')
        const('w100', 'r3'); a.sub('r3', 'r2'); a.shll('r2'); a.movl_pc('dlgmap', 'r3'); a.add('r3', 'r2'); a.movw_load('r2', 'r2'); a.extuw('r2', 'r2')
        a.label('ap_st')
        a.mov('r1', 'r0'); a.shll('r0'); a.movw_r0n_store('r2', 'r6'); a.addi(1, 'r1'); a.bra('ap_loop'); a.nop()
        a.label('ap_end')
        a.movw_store('r1', 'r5'); a.rts(); a.nop()
        # ── 문자열 그리기 2개 (원래 0x0604F92A / 0x0604F98C 를 옮겨 쓰고 앞 바이트 처리만 더함) ──
        def readch(nxt):
            a.movb_postinc('r13', 'r14'); a.extub('r14', 'r14'); a.movi(8, 'r3'); a.cmphs('r3', 'r14'); a.bt(nxt)
            a.shll8('r14'); a.movb_postinc('r13', 'r3'); a.extub('r3', 'r3'); a.orr('r3', 'r14')
            # ⛔셀 쓰기(0x0604F52C)는 후킹하지 않는다 — 대화창이 0x100 이상 코드로 글자 그림 셀을 쓴다(실기 2026-10-04 오프닝 대화창 깨짐).
            #   대신 여기서 m → v(= 셀 번호 하위 12비트 / 2) 로 바꿔 넘기면 원래 공식 (v<<1)|0x1000 이 한글 셀이 된다.
            const('w100', 'r3'); a.sub('r3', 'r14'); a.shll('r14'); a.movl_pc('cellmap', 'r3'); a.add('r3', 'r14')
            a.movw_load('r14', 'r14'); a.extuw('r14', 'r14')
        # draw1: 저장 r14 r13 r12 r11 pr, 지역 8 B → 색 = @(R15+0x1F)
        a.label('draw1')
        for r in ('r14', 'r13', 'r12', 'r11'):
            a.movl_predec(r, 'r15')
        a.stspr_predec('r15'); a.addi(-8, 'r15')
        const('wDE', 'r12'); a.mov('r4', 'r0'); a.movw_r15disp_store(4); a.mov('r5', 'r11'); a.movb_store_r15('r6')
        a.movl_pc('a_chk', 'r2'); a.jsr('r2'); a.nop()                                     # 한글 셀이 덮였으면 다시 올림(r7 은 보존)
        a.bra('d1_test'); a.mov('r7', 'r13')
        a.label('d1_loop')
        readch('d1_one')
        a.mov('r11', 'r5'); a.addi(1, 'r5'); a.movb_load_r15('r6'); a.addi(1, 'r6'); a.movw_r15disp_load(4); a.mov('r0', 'r4')   # 2바이트: 셀 쓰기 직접(x+1, y+1 = 글자 하나의 기본색 경로와 같음)
        a.mov('r14', 'r7'); a.movl_pc('putcell0', 'r2'); a.jsr('r2'); a.nop(); a.addi(1, 'r11'); a.bra('d1_test'); a.nop()
        a.label('d1_one')
        a.mov('r11', 'r5'); a.mov('r14', 'r7'); a.movi(0x1F, 'r0'); a.w(0x03FC)                 # mov.b @(R0,R15),R3
        a.movl_predec('r3', 'r15'); a.movb_r15disp_load(4); a.mov('r0', 'r6'); a.movw_r15disp_load(8)
        a.movl_pc('putchar', 'r2'); a.jsr('r2'); a.mov('r0', 'r4')
        a.addi(4, 'r15'); a.extuw('r14', 'r4'); a.cmpeq('r12', 'r4'); a.bt('d1_test')
        const('wDF', 'r3'); a.cmpeq('r3', 'r4'); a.bt('d1_test'); a.addi(1, 'r11')
        a.label('d1_test')
        a.movb_load('r13', 'r3'); a.tst('r3', 'r3'); a.bf('d1_loop')
        a.addi(8, 'r15'); a.ldspr_postinc('r15')
        for r in ('r11', 'r12', 'r13', 'r14'):
            a.movl_postinc('r15', r)
        a.rts(); a.nop()
        # draw2: 저장 r14 r13 r12 r11 r10 r9 pr, 지역 8 B → 색 = @(R15+0x27). 1바이트 가타카나 A6‥BF −0x20, C0‥DD +0x20
        a.label('draw2')
        for r in ('r14', 'r13', 'r12', 'r11', 'r10', 'r9'):
            a.movl_predec(r, 'r15')
        a.stspr_predec('r15'); a.addi(-8, 'r15')
        a.mov('r4', 'r0'); a.movw_r15disp_store(4); a.mov('r5', 'r10'); a.movb_store_r15('r6')
        a.movl_pc('a_chk', 'r2'); a.jsr('r2'); a.nop()
        a.bra('d2_test'); a.mov('r7', 'r13')
        a.label('d2_loop')
        readch('d2_conv')
        a.mov('r10', 'r5'); a.addi(1, 'r5'); a.movb_load_r15('r6'); a.addi(1, 'r6'); a.movw_r15disp_load(4); a.mov('r0', 'r4')   # 2바이트: 셀 쓰기 직접(x+1, y+1 = 글자 하나의 기본색 경로와 같음)
        a.mov('r14', 'r7'); a.movl_pc('putcell0', 'r2'); a.jsr('r2'); a.nop(); a.addi(1, 'r10'); a.bra('d2_test'); a.nop()
        a.label('d2_conv')
        const('wA6', 'r3'); a.cmphs('r3', 'r14'); a.bf('d2_draw')                        # 1바이트만 변환(2바이트 m ≥ 0x100 은 아래 범위 밖)
        const('wBF', 'r3'); a.cmphi('r3', 'r14'); a.bt('d2_hi')
        a.addi(-0x20, 'r14'); a.bra('d2_draw'); a.nop()
        a.label('d2_hi')
        const('wDD', 'r3'); a.cmphi('r3', 'r14'); a.bt('d2_draw')
        a.addi(0x20, 'r14')
        a.label('d2_draw')
        a.mov('r10', 'r5'); a.mov('r14', 'r7'); a.movi(0x27, 'r0'); a.w(0x03FC)
        a.movl_predec('r3', 'r15'); a.movb_r15disp_load(4); a.mov('r0', 'r6'); a.movw_r15disp_load(8)
        a.movl_pc('putchar', 'r2'); a.jsr('r2'); a.mov('r0', 'r4')
        a.addi(4, 'r15'); a.extuw('r14', 'r4'); const('wDE', 'r3'); a.cmpeq('r3', 'r4'); a.bt('d2_test')
        const('wDF', 'r3'); a.cmpeq('r3', 'r4'); a.bt('d2_test'); a.addi(1, 'r10')
        a.label('d2_test')
        a.movb_load('r13', 'r3'); a.tst('r3', 'r3'); a.bf('d2_loop')
        a.addi(8, 'r15'); a.ldspr_postinc('r15')
        for r in ('r9', 'r10', 'r11', 'r12', 'r13', 'r14'):
            a.movl_postinc('r15', r)
        a.rts(); a.nop()
        # ── X02 진입: 원래 초기화 → 한글 셀 VRAM 업로드 ──
        a.label('x02entry')
        a.stspr_predec('r15'); a.movl_pc('x02orig', 'r0'); a.jsr('r0'); a.nop()
        a.movl_pc('a_upload', 'r0'); a.jsr('r0'); a.nop()
        a.ldspr_postinc('r15'); a.rts(); a.nop()
        # 업로드(잎 함수, r1‥r4)
        a.label('upload')
        for i, (src, dst, n, chk_off, chk_val) in enumerate(tabs['upload']):
            a.movl_pc('us%d' % i, 'r1'); a.movl_pc('ud%d' % i, 'r3'); a.movl_pc('un%d' % i, 'r4')
            a.label('ul%d' % i)
            a.movl_postinc('r1', 'r2'); a.movl_store('r2', 'r3'); a.addi(4, 'r3'); a.dt('r4'); a.bf('ul%d' % i)
            a.defl('us%d' % i, src); a.defl('ud%d' % i, dst); a.defl('un%d' % i, n)
        a.rts(); a.nop()
        # 확인(잎 함수, r1‥r3 + 업로드 r4): 구역마다 표시 워드 하나가 다르면 다시 업로드 — 다른 화면이 덮어썼을 때
        a.label('chk')
        for i, (src, dst, n, chk_off, chk_val) in enumerate(tabs['upload']):
            a.movl_pc('cv%d' % i, 'r1'); a.movl_load('r1', 'r2'); a.movl_pc('cw%d' % i, 'r3'); a.cmpeq('r2', 'r3'); a.bf('chk_up')
            a.defl('cv%d' % i, dst + chk_off); a.defl('cw%d' % i, chk_val)
        a.rts(); a.nop()
        a.label('chk_up')
        a.bra('upload'); a.nop()
        for k, v in (('wintab', 0x0605C2DC), ('cellmap', L('cellmap')), ('dlgmap', L('dlgmap')), ('dbuf', 0x0605E53A), ('didx', 0x0605E93A),
                     ('putchar', PUTCHAR), ('putcell0', 0x0604F52C), ('x02orig', X02_ENTRY), ('a_upload', L('upload')), ('a_chk', L('chk'))):
            a.defl(k, v)
        code, _ = a.assemble()
        return code, dict(a.labels)
    return build


def make_blob(rows, chars, mcode, cells, dlg, G):
    """→ (블롭 바이트, 라벨 주소, 목록 주소 {k: addr})"""
    maxp = max(m >> 8 for m in mcode.values())
    n = maxp * 256 - 0x100 + 256
    cellmap = [0] * n; dlgmap = [0] * n
    for ch, m in mcode.items():
        cellmap[m - 0x100] = (cells[ch] // 0x20 & 0xFFF) >> 1          # v: 글자 하나 → 셀 쓰기 공식 (v<<1)|0x1000
        dlgmap[m - 0x100] = dlg[ch]
    lists = {}
    for k in LISTS:
        lists[k] = b''.join(encode(t, mcode) + b'\x00' for _, kk, i, t in sorted(rows, key=lambda r: (r[1], r[2])) if kk == k) + b'\xFF'
    # 업로드할 셀 데이터: 영역마다 이어진 덩어리
    upl = []
    for a, b in REGIONS:
        data = bytearray(b - a)
        for ch in chars:
            if a <= cells[ch] < b:
                data[cells[ch] - a:cells[ch] - a + 64] = cell8(ch, G)
        used = max([cells[ch] - a + 64 for ch in chars if a <= cells[ch] < b] or [0])
        if used:
            upl.append((a, bytes(data[:used])))
    build = hooks(BLOB, None)
    # 1패스: 코드 길이 → 뒤에 표·목록·셀 배치
    def layout(code_len, labels0):
        off = (code_len + 3) & ~3; lab = {}; parts = []
        def put(name, data, align=4):
            nonlocal off
            off = (off + align - 1) & ~(align - 1); lab[name] = BLOB + off; parts.append((off, data)); off += len(data)
        put('cellmap', struct.pack('>%dH' % n, *cellmap)); put('dlgmap', struct.pack('>%dH' % n, *dlgmap))
        for k, s in lists.items():
            put('list%d' % k, s, 1)
        for a, t in X02_STR.items():
            put('x02s_%X' % a, encode(t, mcode) + bytes(1), 1)
        for i, (a, data) in enumerate(upl):
            put('cells%d' % i, data)
        return lab, parts, off
    def chkpos(data):
        o = next(i for i in range(len(data) - 4, -1, -4) if struct.unpack_from('>I', data, i)[0])
        return o, struct.unpack_from('>I', data, o)[0]
    tabs = {'upload': [(0, 0, 1, 0, 0)] * len(upl)}
    b0 = hooks(BLOB, tabs)
    code, lab0 = b0({})
    lab, parts, total = layout(len(code), lab0)
    tabs = {'upload': [(lab['cells%d' % i], VRAM + a, len(data) // 4) + chkpos(data) for i, (a, data) in enumerate(upl)]}
    code2, lab2 = hooks(BLOB, tabs)({**lab0, **lab})
    assert len(code2) == len(code)
    blob = bytearray(total)
    assert BLOB + total <= swkfont.LOWRAM_END, ('LowRAM 블롭 자리 초과', hex(BLOB + total))
    blob[:len(code2)] = code2
    for off, data in parts:
        blob[off:off + len(data)] = data
    lab.update({k: v for k, v in lab2.items()})
    return bytes(blob), lab, {k: lab['list%d' % k] for k in LISTS}, upl


def jump_stub(at, target):
    """at(2 B 정렬) 에 MOV.L @(lit),R0 ; JMP @R0 ; NOP ; [맞춤] lit — 12 B 이하"""
    out = bytearray()
    lit = (at + 6 + 3) & ~3
    disp = (lit - ((at + 4) & ~3)) // 4
    out += struct.pack('>HHH', 0xD000 | disp, 0x402B, 0x0009)
    out += bytes(lit - (at + 6))
    out += struct.pack('>I', target)
    return bytes(out)


def build():
    rows, chars, mcode, cells, dlg, G = plan()
    blob, lab, laddr, upl = make_blob(rows, chars, mcode, cells, dlg, G)
    # X01 = 원본 + 설치 코드 + 블롭
    x1 = bytearray(open(os.path.join(DISC, 'X01.BIN'), 'rb').read())
    assert struct.unpack_from('>I', x1, 8)[0] == X01_ENTRY
    inst_off = (len(x1) + 3) & ~3
    def installer(blob_src):
        a = Asm(X01_LOAD + inst_off)
        a.movl_pc('src', 'r1'); a.movl_pc('dst', 'r3'); a.movl_pc('n', 'r4')
        a.label('cp'); a.movl_postinc('r1', 'r2'); a.movl_store('r2', 'r3'); a.addi(4, 'r3'); a.dt('r4'); a.bf('cp')
        a.movl_pc('entry', 'r0'); a.jmp('r0'); a.nop()
        a.defl('src', blob_src); a.defl('dst', BLOB); a.defl('n', (len(blob) + 3) // 4); a.defl('entry', X01_ENTRY)
        return a.assemble()[0]
    ins = installer(0)
    blob_off = (inst_off + len(ins) + 3) & ~3
    ins = installer(X01_LOAD + blob_off)
    out1 = x1 + bytes(inst_off - len(x1)) + ins
    out1 += bytes(blob_off - len(out1)) + blob + bytes((-len(blob)) % 4)
    struct.pack_into('>I', out1, 8, X01_LOAD + inst_off)
    assert len(out1) <= X01_LIMIT, ('X01 자리 초과', len(out1))
    # X02 패치
    x2 = bytearray(open(os.path.join(DISC, 'X02.BIN'), 'rb').read())
    def put(addr, data, expect=None):
        o = addr - X02_LOAD
        if expect is not None:
            assert x2[o:o + len(expect)] == expect, (hex(addr), x2[o:o + len(expect)].hex())
        x2[o:o + len(data)] = data
    assert struct.unpack_from('>I', x2, 8)[0] == X02_ENTRY
    struct.pack_into('>I', x2, 8, lab['x02entry'])
    put(0x0605A870, jump_stub(0x0605A870, lab['append']), bytes.fromhex('d613d514'))
    put(0x0604F92A, jump_stub(0x0604F92A, lab['draw1']), bytes.fromhex('2fe62fd6'))
    put(0x0604F98C, jump_stub(0x0604F98C, lab['draw2']), bytes.fromhex('2fe62fd6'))
    put(0x060544C4, bytes.fromhex('c8f8'), bytes.fromhex('88df'))
    for a in X02_STR:                                                  # 문자열 포인터 → LowRAM
        refs = [i for i in range(0, len(x2) - 3, 2) if struct.unpack_from('>I', x2, i)[0] == a]
        assert 1 <= len(refs) <= 2, (hex(a), refs)
        for i in refs:
            struct.pack_into('>I', x2, i, lab['x02s_%X' % a])
    # X10 목록 포인터
    x10 = bytearray(open(os.path.join(DISC, 'X10.BIN'), 'rb').read())
    for k, off in LISTS.items():
        struct.pack_into('>I', x10, off, laddr[k])
    return dict(X01=bytes(out1), X02=bytes(x2), X10=bytes(x10), blob=blob, lab=lab, mcode=mcode, cells=cells, chars=chars, rows=rows, upl=upl, G=G)


def simulate(B):
    """s4 메모리 + 고친 X01·X02 로: ①X01 설치 → LowRAM 블롭 ②draw1 로 한글 문자열 → 창 버퍼 셀 ③append → 대사 버퍼 코드"""
    H = bytearray(open(os.path.join(ROOT, 'work/mem/s4/WorkRAMH.bin'), 'rb').read())
    for f, load in (('X01', X01_LOAD), ('X02', X02_LOAD)):
        d = B[f]; H[load - 0x06000000:load - 0x06000000 + len(d)] = d
    mem = sh2sim.Mem(); mem.map(0x06000000, H); mem.map(0x00200000, bytes(0x100000))
    mem.map(VRAM, open(os.path.join(ROOT, 'work/mem/s4/VDP2_VRAM.bin'), 'rb').read())   # 확인 → 재업로드도 시험
    cpu = sh2sim.CPU(mem, X01_LOAD, stack_top=0x0609F000); cpu.pr = 0xDEAD0000
    cpu.run(X01_ENTRY, 5_000_000)
    buf, o = mem._find(BLOB)
    assert bytes(buf[o:o + len(B['blob'])]) == B['blob'], '블롭 복사 다름'
    # ② 창 0 에 「설명」 첫 문자열을 draw1 로
    rows = [r for r in B['rows'] if r[1] == 10]
    t = rows[0][3]; s = encode(t, B['mcode']) + b'\x00'
    sa = 0x0609E000; [mem.w8(sa + i, c) for i, c in enumerate(s)]
    win = 0
    wrec = 0x0605C2DC + win * 16; wbuf = mem.r32(wrec); ww = mem.r8(wrec + 4)
    cpu = sh2sim.CPU(mem, B['lab']['draw1'], regs={4: win, 5: 1, 6: 1, 7: sa}, stack_top=0x0609F000)
    cpu.m.w32(0x0609F000 - 4, 0x3F); cpu.r[15] = 0x0609F000 - 4; cpu.pr = 0xDEAD0000
    steps = cpu.run(0xDEAD0000, 2_000_000)
    got = [mem.r16(wbuf + (2 * ww + 2 + i) * 2) for i in range(len(t))]          # 글자 하나(0x0604F782)가 창 테두리만큼 +1
    want = [0x1000 | (ord(c) << 1) if 0x20 <= ord(c) < 0x7F else 0x1000 | (B['cells'][c] // 0x20 & 0xFFF) for c in t]
    ok1 = got == want
    vb, vo = mem._find(VRAM)
    ok1 = ok1 and all(bytes(vb[a:a + len(d)]) == d for a, d in B['upl'])      # draw1 의 확인 코드가 비어 있던 VRAM 에 셀을 올렸는가
    # ③ append — 아이템 첫 이름
    it = [r for r in B['rows'] if r[1] == 4][1][3]; s = encode(it, B['mcode']) + b'\x00'
    [mem.w8(sa + i, c) for i, c in enumerate(s)]
    mem.w16(0x0605E93A, 0)
    cpu = sh2sim.CPU(mem, B['lab']['append'], regs={4: sa}, stack_top=0x0609F000); cpu.pr = 0xDEAD0000
    cpu.run(0xDEAD0000, 1_000_000)
    dlg = swkfont.codemap(); n = mem.r16(0x0605E93A)
    got2 = [mem.r16(0x0605E53A + 2 * i) for i in range(n)]
    ok2 = got2 == [dlg[c] for c in it]
    return ok1, ok2, t, it, steps


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    B = build()
    ok1, ok2, t, it, steps = simulate(B)
    os.makedirs(os.path.join(ROOT, 'work/build'), exist_ok=True)
    for f in ('X01', 'X02', 'X10'):
        open(os.path.join(ROOT, 'work/build', f + '.BIN'), 'wb').write(B[f])
    print('메뉴 글자 %d · 블롭 %d B · X01 %d B(한도 %d) · 셀 업로드 %s' % (len(B['chars']), len(B['blob']), len(B['X01']), X01_LIMIT,
          ', '.join('0x%X+%d' % (a, len(d)) for a, d in B['upl'])))
    print('시뮬: draw1 「%s」 %s · append 「%s」 %s' % (t, '일치' if ok1 else '⚠다름', it, '일치' if ok2 else '⚠다름'))
    if not (ok1 and ok2):
        sys.exit(1)


if __name__ == '__main__':
    main()
