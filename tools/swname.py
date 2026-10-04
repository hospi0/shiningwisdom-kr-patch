"""이름 입력판 한글 — 판의 코드 배치는 그대로, 그 코드가 그리는 글자만 한글로(고르는 방식을 몰라도 같은 코드가 이름에 들어간다)
  판·옵션 창 템플릿 = X10 +0xFD54‥0x10481(X10 표 +0x4C 항목). 히라가나 판 = 묶음 1(あ‥ほ 30칸)·묶음 2(ま‥っ 25칸)·묶음 3(탁점 중복 → 비움).
  ⛔템플릿은 01‥04·11‥14 를 창 틀 제어로 써서 2바이트 한글 불가 → 1바이트 코드에 음절 고정 배정.
  라벨: かな(96 E5) → 한글 · もとる(F3 E4+゛ F9) → 지우기 · おわる(95 FC F9) → 끝내기 (판의 그 코드 칸도 같은 음절)
  옵션 창: あか/みどり/あお → 적/녹/청 · おそい/はやい → 느림/빠름 · メッセージスピード → 메시지 속도 · フレームのしゅるい → 창 종류
  가타카나 판(A6‥DD)은 그대로(draw2 가 그 범위를 바꿔 그림).
  글꼴: 메뉴 8×8(X10 +0xA4 워드 LZ 재압축, 원래 자리 6,032 B 안) · 대사(swkfont 0x80‥0xFF 칸)
python tools/swname.py  → 검사·미리보기 work/view/name_board.png"""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swlz, swmenu

T0, T1 = 0xFD54, 0x10481
FONT_OFF, FONT_END = 0xA4, 0x1834
FIXED = {0x96: '한', 0xE5: '글', 0xF3: '지', 0xE4: '우', 0xF9: '기', 0x95: '끝', 0xFC: '내'}
GRID1 = [0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
         0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE]
GRID2 = [0xEF, 0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0x86, 0xFD,
         0x87, 0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F]
EXTRA = [0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x90]
FILL = list('가나다라마바사아자차카타파하고노도로모보소오조초코토포호스피리미비이시수주민진영르류') + list('메속창종니디')  # 강 → 르(기본 이름 «마르스», 사용자 2026-10-04 · 류는 옵션 «창 종류»가 씀)
EXTRA_SYL = list('적녹청느림빠름')


def namemap():
    m = dict(FIXED); it = iter(FILL)
    for c in GRID1 + GRID2:
        if c not in m:
            m[c] = next(it)
    for c, s in zip(EXTRA, EXTRA_SYL):
        m[c] = s
    assert len(set(m.values())) == len(m), '음절 중복'
    return m


DEFAULT_NAME_OFF = 0x6314                                 # X04 0x0607C314 「マルス」 — 새 게임 때 0x06079722 가 이름 칸으로 복사(입력 안 하면 그대로)
DEFAULT_NAME = '마르스'


def default_name(x04, M):
    """X04 기본 이름 제자리(원문 3바이트 + NUL 그대로)"""
    x = bytearray(x04); inv = {v: k for k, v in M.items()}
    assert x[DEFAULT_NAME_OFF:DEFAULT_NAME_OFF + 4] == bytes([0xCF, 0xD9, 0xBD, 0]), '기본 이름 자리 다름'
    new = enc(DEFAULT_NAME, inv)
    assert len(new) == 3, new
    x[DEFAULT_NAME_OFF:DEFAULT_NAME_OFF + 3] = new
    return bytes(x)


def enc(t, inv):
    return bytes(ord(ch) if 0x20 <= ord(ch) < 0x7F else inv[ch] for ch in t)


def template(x10, M):
    """X10 바이트 → 고친 X10 (템플릿 제자리, 길이 그대로)"""
    x = bytearray(x10); inv = {v: k for k, v in M.items()}
    blk = bytearray(x[T0:T1])
    def rows():
        out = []; start = None
        for i, c in enumerate(blk):
            if c == 0x11:
                start = i + 1
            elif c == 0x04 and start is not None:
                out.append((start, i)); start = None
        return out
    R = rows()
    def setrow(k, text):
        a, b = R[k]
        new = enc(text, inv)
        assert len(new) <= b - a, (k, text)
        blk[a:b] = new + b' ' * (b - a - len(new))
    # 히라가나 판: 글자 줄 6개(짝수) 사이에 탁점 줄 5개(홀수). 열: 묶음1 0‥8 · 묶음2 11‥19 · 묶음3 22‥30 · 라벨 33‥35
    hira = next(k for k, (a, b) in enumerate(R) if blk[a:a + 3] == bytes([0x91, 0x20, 0x92]))
    for j in range(11):
        a, b = R[hira + j]
        if j % 2:                                                # 탁점 줄 → 비움(히라가나 판만)
            blk[a:b] = bytes(0x20 if c in (0xDE, 0xDF) else c for c in blk[a:b])
        elif j:                                                  # 묶음 3(탁점 중복) → 비움. 첫 줄은 부호(! ? 、 。 -)라 남김
            blk[a + 22:a + 31] = b' ' * 9
    # 「지우기」(F3 E4 F9) 바로 위 칸의 ゛ 지움 — 모든 판
    for k, (a, b) in enumerate(R):
        i = bytes(blk[a:b]).find(bytes([0xF3, 0xE4, 0xF9]))
        if i >= 0 and k:
            pa, pb = R[k - 1]
            if blk[pa + i + 1] == 0xDE:
                blk[pa + i + 1] = 0x20
    # 옵션 창
    for k, (a, b) in enumerate(R):
        row = bytes(blk[a:b])
        if row.startswith(b' \x91\x96 \xb0'):          # あか ーー…
            blk[a + 1:a + 3] = enc(' 적', inv)
        elif row.startswith(b' \xf0\xe4\xf8\xb0'):      # みどり ー…  (ど = と + 위 줄 ゛)
            blk[a + 1:a + 4] = enc('녹  ', inv)[:3]
            pa, pb = R[k - 1]                                    # 바로 윗줄(옵션 전용)의 ゛ 전부 — 원래 한 칸 오른쪽(3열)
            blk[pa:pb] = bytes(0x20 if c == 0xDE else c for c in blk[pa:pb])
        elif row.startswith(b' \x91\x95 \xb0'):         # あお ー…
            blk[a + 1:a + 3] = enc(' 청', inv)
        elif row.startswith(b'\x95\x9f\x92 1 2 3 4 \xea\xf4\x92'):
            blk[a:a + 15] = enc('느림  1 2 3 4 빠름', inv) + b' '          # 숫자 칸(4·6·8·10열) 그대로
        elif b'\xd2\xaf\xbe\xb0\xbc\xbd\xcb\xb0\xc4' in row:   # メッセージスピード
            i = row.index(b'\xd2\xaf\xbe')
            blk[a + i:a + i + 9] = enc('메시지 속도', inv).ljust(9, b' ')[:9]
        elif b'\xcc\xda\xb0\xc4\xe9\x9c\x8d\xf9\x92' in row:   # フレームのしゅるい
            i = row.index(b'\xcc\xda\xb0')
            blk[a + i:a + i + 9] = enc('창 종류', inv).ljust(9, b' ')
    assert len(blk) == T1 - T0, '템플릿 길이 바뀜'
    x[T0:T1] = blk
    return x


def menu_font(x10, M):
    """X10 의 메뉴 글꼴(LZ) 에서 M 의 코드 칸을 갈무리7 한글로 → 다시 압축(원래 자리 안)"""
    font, used = swlz.decompress(x10, FONT_OFF)
    assert FONT_OFF + used == FONT_END
    f = bytearray(font); G = swmenu.galmuri7()
    for c, s in M.items():
        f[c * 64:c * 64 + 64] = swmenu.cell8(s, G)
    z = swlz.compress(bytes(f))
    assert len(z) <= FONT_END - FONT_OFF, ('메뉴 글꼴 압축 자리 초과', len(z), FONT_END - FONT_OFF)
    back, _ = swlz.decompress(z)
    assert back == bytes(f)
    x = bytearray(x10)
    x[FONT_OFF:FONT_END] = z + bytes(FONT_END - FONT_OFF - len(z))
    return x, len(z)


def apply(x10):
    M = namemap()
    x = template(x10, M)
    x, zlen = menu_font(bytes(x), M)
    return bytes(x), M, zlen


def preview(x10, M):
    from PIL import Image
    font, _ = swlz.decompress(x10, FONT_OFF)
    blk = x10[T0:T1]
    rows = []; start = None
    for i, c in enumerate(blk):
        if c == 0x11: start = i + 1
        elif c == 0x04 and start is not None: rows.append(blk[start:i]); start = None
    im = Image.new('RGB', (8 * 40, 8 * len(rows)), (20, 20, 80)); px = im.load()
    for y, r in enumerate(rows):
        for x, c in enumerate(r[:40]):
            g = font[c * 64:c * 64 + 64]
            for yy in range(8):
                for xx in range(8):
                    v = g[yy * 8 + xx]
                    if v: px[x * 8 + xx, y * 8 + yy] = (255, 255, 255) if v == 0x3F else (110, 110, 160)
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(ROOT, 'work/view/name_board.png'))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    x10 = open(os.path.join(ROOT, 'work/disc/X10.BIN'), 'rb').read()
    x, M, z = apply(x10)
    preview(x, M)
    print('음절 %d · 메뉴 글꼴 재압축 %d B / %d · 판: %s' % (len(M), z, FONT_END - FONT_OFF, ''.join(M[c] for c in GRID1 + GRID2)))
