"""저장 화면 큰 글씨 창 그림 한글 — X10 +0xA954 128×48 8bpp(셀 96개, 16셀 가로) 구운 그림
  X02 0x06054C2A 가 통째(0x1800 B)로 VDP2 VRAM 0x27A00 에 복사 → 창이 그 셀을 가리킨다(⛔메뉴 한글 셀 구역은 0x27A00 전까지).
  원본: 띠(16행) 0 「始める」 x1‥35 · 「本体RAM」 x41‥96 · 화살표 x112‥127(색 18·21·0x3F — 그대로)
        띠 1 「写す」 · 「カートリッジRAM」 x40‥127 / 띠 2 「消す」. 글자 잉크 = 0x3F 한 색, 그림자 없음.
  한글 = 갈무리11(swfont.glyph_bdf, 대사와 같은 모양) 띠 안 1행 아래(원래 한자 잉크 2‥14행) · «RAM» = 원본 그림 띠 0 x65‥96 그대로 옮김
python tools/swsave.py  → 미리보기 work/view/save_window.png"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swfont

OFF, W, H = 0xA954, 128, 48
INK = 0x3F
LEFT = ['시작', '복사', '삭제']               # 始める・写す・消す
RIGHT = ['본체', '카트리지']                  # 本体RAM・カートリッジRAM (+ RAM 원본 그림)
X_LEFT, X_RIGHT, X_LIMIT0 = 1, 41, 112        # 띠 0 은 화살표(x112‥) 전까지
RAM_SRC = (65, 97)                            # 원본 띠 0 «RAM» 열 범위


def unpack(img):
    px = [[0] * W for _ in range(H)]
    for c in range(96):
        cx, cy = c % 16, c // 16
        for y in range(8):
            for x in range(8):
                px[cy * 8 + y][cx * 8 + x] = img[c * 64 + y * 8 + x]
    return px


def pack(px):
    out = bytearray(0x1800)
    for c in range(96):
        cx, cy = c % 16, c // 16
        for y in range(8):
            for x in range(8):
                out[c * 64 + y * 8 + x] = px[cy * 8 + y][cx * 8 + x]
    return bytes(out)


def text(px, band, x, s):
    for ch in s:
        w, rows = swfont.glyph_bdf(ch, swfont.HANGUL_W)
        for r, v in enumerate(rows):
            for i in range(16):
                if v >> (15 - i) & 1:
                    px[band * 16 + 1 + r][x + i] = INK
        x += w + 1                                                     # 대사와 같은 진행(폭 + 1)
    return x


def render(x10):
    src = unpack(x10[OFF:OFF + 0x1800])
    ram = [[src[y][x] for x in range(*RAM_SRC)] for y in range(16)]
    px = [[0 if v == INK and not (y < 16 and x >= X_LIMIT0) else v for x, v in enumerate(row)] for y, row in enumerate(src)]   # 글자 잉크만 지움(띠 0 x112‥ 화살표는 잉크 포함 그대로)
    for b, s in enumerate(LEFT):
        e = text(px, b, X_LEFT, s)
        assert e <= X_RIGHT - 2, ('왼쪽 칸 넘침', s, e)
    for b, s in enumerate(RIGHT):
        x = text(px, b, X_RIGHT, s) + 3
        lim = X_LIMIT0 if b == 0 else W
        assert x + len(ram[0]) <= lim, ('오른쪽 칸 넘침', s, x)
        for y in range(16):
            for i, v in enumerate(ram[y]):
                if v:
                    px[b * 16 + y][x + i] = v
    for y in range(H):                                                 # 범위 검사: 화살표 자리 x112‥ 띠 0 은 원본과 같아야
        for x in range(112, W):
            if y < 16:
                assert px[y][x] == src[y][x], '화살표 덮음'
    return pack(px)


def apply(x10):
    x = bytearray(x10)
    x[OFF:OFF + 0x1800] = render(bytes(x10))
    return bytes(x)


def preview(img, out):
    from PIL import Image
    px = unpack(img)
    im = Image.new('RGB', (W, H), (0, 0, 64))
    for y in range(H):
        for x in range(W):
            v = px[y][x]
            if v:
                im.putpixel((x, y), (255, 255, 255) if v == INK else (0, 160, 255))
    im.resize((W * 5, H * 5), Image.NEAREST).save(out)


if __name__ == '__main__':
    x10 = open(os.path.join(ROOT, 'work', 'disc', 'X10.BIN'), 'rb').read()
    new = render(x10)
    preview(new, os.path.join(ROOT, 'work', 'view', 'save_window.png'))
    preview(x10[OFF:OFF + 0x1800], os.path.join(ROOT, 'work', 'view', 'save_window_orig.png'))
    print('OK', len(new))
