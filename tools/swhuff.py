# -*- coding: utf-8 -*-
r"""샤이닝 위즈덤 대사 허프만(가설 검증용, 2026-10-04) — ETC 머리말 [글꼴][트리쌍 표][?][?][?]
  트리쌍 표 = u32 절대주소 × 512 = (잎 기호 목록, 트리 모양 비트) × 256 — 직전 바이트별 트리(가설)
"""
import struct, sys

def load(path, base=0x060BC000, hdr=0x8a3c):
    d = open(path, 'rb').read(); u = lambda o: struct.unpack_from('>I', d, o)[0] - base
    return d, [u(hdr + 4 * i) for i in range(5)]

class Bits:
    def __init__(s, d, o, bit=0): s.d, s.o, s.b = d, o, bit
    def get(s):
        v = (s.d[s.o] >> (7 - s.b)) & 1; s.b += 1
        if s.b == 8: s.b = 0; s.o += 1
        return v

def tree(d, leaves, shape, order):
    """shape 비트로 트리(전위). order: 'leaf1' = 1 이면 잎"""
    bs = Bits(d, shape); syms = iter(leaves); used = [0]
    def node(depth=0):
        if depth > 40: raise ValueError('깊이')
        b = bs.get()
        if (b == 1) == (order == 'leaf1'):
            used[0] += 1; return next(syms)
        return (node(depth + 1), node(depth + 1))
    t = node(); return t, used[0], (bs.o - shape) * 8 + bs.b


def trees(d, tab, base=0x060BC000):
    ptr = [struct.unpack_from('>I', d, tab + 4 * i)[0] - base for i in range(512)]
    T = {}
    for k in range(256):
        L, S = ptr[2 * k], ptr[2 * k + 1]
        if 0 <= L < S <= len(d):
            T[k] = tree(d, d[L:S], S, 'leaf1')[0]
    return T


def decode(d, T, o, bit=0, prev=0, n=80, stop=None):
    bs = Bits(d, o, bit); out = []
    for _ in range(n):
        if prev not in T: out.append(('X', prev)); break
        t = T[prev]
        while isinstance(t, tuple): t = t[bs.get()]
        out.append(t); prev = t
        if stop is not None and t == stop: break
    return out, (bs.o, bs.b)


def glyph(d, font, code):
    """[u16 폭][15줄 × u16] — 1bpp 16px 폭, 맨 윗비트 = 왼쪽"""
    import numpy as np
    o = font + code * 32 - 0x20 * 32 if False else font + (code - 0x20) * 32
    w = struct.unpack_from('>H', d, o)[0]
    rows = np.frombuffer(d[o + 2:o + 32], '>u2').astype(np.uint16)
    return w, ((rows[:, None] >> (15 - np.arange(16))) & 1).astype(np.uint8)


HIRA_LO = 'をぁぃぅぇぉゃゅょっ　あいうえおかきくけこさしすせそ'          # 0x86‥0x9F (0x90 = 빈칸)
KATA = '　。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン゛゜'  # 0xA0‥0xDF
HIRA_HI = 'たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん'       # 0xE0‥0xFD


def charmap(kanji):
    m = {c: chr(c) for c in range(0x20, 0x7F)}
    for i, ch in enumerate(HIRA_LO): m[0x86 + i] = ch
    for i, ch in enumerate(KATA): m[0xA0 + i] = ch
    for i, ch in enumerate(HIRA_HI): m[0xE0 + i] = ch
    for i, ch in enumerate(kanji): m[0x100 + i] = ch
    return m
