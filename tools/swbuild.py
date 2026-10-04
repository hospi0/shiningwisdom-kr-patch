"""샤이닝 위즈덤 한글 빌더 — 맵 대사(ETC 42개) + 전역 글꼴(X09)
  ① 번역 work/trans/sw_ko.tsv(trcheck --merge 결과) — 원문(렌더 문자열)으로 맵 문장과 짝짓기
  ② 되채움: 쪽({0005})마다 288px(tools/swfit) 넘는 쪽만 낱말 단위 재배치(줄 수 유지 → 모자라면 3줄까지). 부호 뒤에서 끊기 우대.
     01379 = 원문도 줄바꿈 없는 한 줄(561px) → 원문처럼 둔다.
  ③ 쓰는 순간 검사(⛔빌드 금지): 제어 코드 순서 = 원문 · 글꼴에 없는 글자 · 줄 288px 초과 · 3줄 초과 쪽 · 문장 255 B 초과
  ④ ETC 덩어리 = [트리][대사](원래 글꼴 자리부터 원래 마지막 문장 끝까지), 머리말 +00 = swkfont.FONT_BASE(0x002CF800) → 되읽기 검증
  ⑤ X09 = tools/swkfont(펼치기 코드 + 압축 글꼴, 시뮬레이터 검증)
python tools/swbuild.py [--write|--install]  → 검사 + work/build/ (ETC·X09) [+ work/out 트랙 1 (+ F: 설치)]"""
import os, re, struct, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import swtext, swenc, swfit, swkfont

KEEP_LONG = {'01379'}
TOK = re.compile(r'\{[0-9A-F]{4}\}')
PUNCT_END = tuple(',.!?…~」')
OUT = os.path.join(ROOT, 'work', 'build')


def load_ko():
    by_src = {}; by_id = {}
    for l in open(os.path.join(ROOT, 'work/trans/sw_ko.tsv'), encoding='utf-8').read().splitlines()[1:]:
        k, f, o, t = l.split('\t'); by_src[o] = (k, t); by_id[k] = (o, t)
    return by_src


def fit_page(pg, k):
    """한 쪽(\\n 으로 나뉜 줄들) — 넘치면 낱말 재배치"""
    lines = pg.split('\\n')
    if all(swfit.width(l) <= swfit.LIMIT for l in lines):
        return pg, False
    words = ' '.join(lines).split(' ')
    for n in range(len(lines), 4):
        best = None

        def go(i, left, acc):
            nonlocal best
            if left == 1:
                last = ' '.join(words[i:])
                if swfit.width(last) > swfit.LIMIT:
                    return
                ls = acc + [last]
                ws = [swfit.width(x) for x in ls]
                pen = sum(0 if x.endswith(PUNCT_END) else 1 for x in ls[:-1])
                key = (pen, max(ws), sum((swfit.LIMIT - w) ** 2 for w in ws))
                if best is None or key < best[0]:
                    best = (key, ls)
                return
            for j in range(i + 1, len(words) - left + 2):
                s = ' '.join(words[i:j])
                if swfit.width(s) > swfit.LIMIT:
                    break
                go(j, left - 1, acc + [s])
        go(0, n, [])
        if best:
            return '\\n'.join(best[1]), True
    raise SystemExit('⛔%s 쪽이 3줄 288px 에 안 들어감: %s' % (k, pg))


def fit(t, k):
    if k in KEEP_LONG:
        return t, False
    pages = t.split('{0005}'); ch = False
    for i, pg in enumerate(pages):
        pages[i], c = fit_page(pg, k); ch |= c
    return '{0005}'.join(pages), ch


def to_codes(t, cmap, k):
    out = []
    for m in re.finditer(r'\{([0-9A-F]{4})\}|\\n|(.)', t, re.S):
        if m.group(1):
            out.append(int(m.group(1), 16))
        elif m.group(0) == '\\n':
            out.append(3)
        else:
            ch = m.group(2)
            if ch not in cmap:
                raise SystemExit('⛔%s 글꼴에 없는 글자 %r' % (k, ch))
            out.append(cmap[ch])
    return out + [0]


def check(k, src, t):
    if TOK.findall(src) != TOK.findall(t):
        raise SystemExit('⛔%s 제어 코드가 원문과 다름\n  원문 %s\n  번역 %s' % (k, src, t))
    bad = re.search(r'\{000[AE]\}(?:은|을|과|으로|이\(|을\(|은\(|나 )', t)              # 이름(가나 = 모음 끝) 뒤 받침 조사·병기
    if bad:
        raise SystemExit('⛔%s 이름 뒤 조사 %r: %s' % (k, bad.group(), t))
    src_max = max(len(p.split('\\n')) for p in src.split('{0005}'))
    for pg in t.split('{0005}'):
        ls = pg.split('\\n')
        if len(ls) > max(3, src_max) and k not in KEEP_LONG:
            raise SystemExit('⛔%s 쪽 3줄 초과: %s' % (k, pg))
        for l in ls:
            if swfit.width(l) > swfit.LIMIT and k not in KEEP_LONG:
                raise SystemExit('⛔%s 줄 %dpx: %s' % (k, swfit.width(l), l))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    KO = load_ko(); cmap = swkfont.codemap()
    KH = swtext.kanji_by_hash(); os.makedirs(OUT, exist_ok=True)
    refit = {}; tot = 0
    for f in sorted(x for x in os.listdir(swtext.DISC) if x.endswith('.ETC')):
        d = open(os.path.join(swtext.DISC, f), 'rb').read(); load, hdr = swtext.header(d)
        m = swtext.map_charmap(d, load, hdr, KH)
        ms = swtext.messages(d, load, hdr)[1]
        codes = []
        for *_, c in ms:
            src = swtext.render(c, m)
            if src not in KO:
                raise SystemExit('⛔%s 번역 없음: %s' % (f, src))
            k, t = KO[src]
            t2, ch = fit(t, k)
            if ch:
                refit[k] = (t, t2)
            check(k, src, t2)
            codes.append(to_codes(t2, cmap, k))
        font_off = struct.unpack_from('>I', d, hdr)[0] - load
        new, spare = swenc.rebuild(d, codes, start=font_off, font_ptr=swkfont.FONT_BASE)
        _, ms2 = swtext.messages(new, load, hdr)
        assert [c for *_, c in ms2] == codes, f + ' 되읽기 다름'
        assert len(new) == len(d)
        open(os.path.join(OUT, f), 'wb').write(new); tot += 1
        print('%-9s 문장 %3d · 덩어리 남음 %6d B' % (f, len(codes), spare))
    x9, nd = swkfont.build_x09(swkfont.glyphs())
    got, _ = swkfont.simulate(x9, len(swkfont.glyphs()))
    assert got == swkfont.expand_py(swkfont.glyphs()), 'X09 시뮬레이터 불일치'
    open(os.path.join(OUT, 'X09.BIN'), 'wb').write(x9)
    import swmenu                                                        # ⑥ 메뉴(X10 문구·X02 문자열) 8×8 한글 — X01 운반·X02 후킹·X10 포인터
    MB = swmenu.build(); ok1, ok2, *_ = swmenu.simulate(MB)
    assert ok1 and ok2, '메뉴 시뮬레이터 불일치'
    import swname                                                        # ⑦ 이름판 한글(X10 템플릿·메뉴 글꼴) — 대사 글꼴은 swkfont 가 NAMEMAP 로
    MB['X10'], NM, zlen = swname.apply(MB['X10'])
    import swsave                                                        # ⑨ 저장 화면 큰 글씨 창 그림(X10 +0xA954 128×48) 한글
    MB['X10'] = swsave.apply(MB['X10'])
    for f in ('X01', 'X02', 'X10'):
        open(os.path.join(OUT, f + '.BIN'), 'wb').write(MB[f])
    x04 = swname.default_name(open(os.path.join(swtext.DISC, 'X04.BIN'), 'rb').read(), NM)    # ⑧ 기본 이름 マルス → 마르스
    open(os.path.join(OUT, 'X04.BIN'), 'wb').write(x04)
    print('이름판 음절 %d · 메뉴 글꼴 재압축 %d B · 기본 이름 %s' % (len(NM), zlen, x04[swname.DEFAULT_NAME_OFF:swname.DEFAULT_NAME_OFF + 3].hex()))
    print('메뉴 글자 %d · X01 %d B · 블롭 %d B' % (len(MB['chars']), len(MB['X01']), len(MB['blob'])))
    with open(os.path.join(OUT, 'refit.tsv'), 'w', encoding='utf-8', newline='') as w:
        w.write('#번호\t번역\t되채움\n')
        for k, (a, b) in sorted(refit.items()):
            w.write('%s\t%s\t%s\n' % (k, a, b))
    print('ETC %d개 · X09 %d B · 되채움 %d문장(work/build/refit.tsv) → work/build/' % (tot, len(x9), len(refit)))
    if '--write' in sys.argv or '--install' in sys.argv:
        import disc, hashlib, shutil
        files = {n: open(os.path.join(OUT, n), 'rb').read() for n in sorted(os.listdir(OUT)) if n.endswith(('.ETC', '.BIN'))}
        dst_dir = os.path.join(ROOT, 'work', 'out'); os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(disc.TRACK))
        disc.patch_track(dst, files)
        print('트랙 1', dst, hashlib.md5(open(dst, 'rb').read()).hexdigest())
        if '--install' in sys.argv:
            F = r'F:\hospi\roms\ss roms\Shining Wisdom (Japan)'
            shutil.copyfile(dst, os.path.join(F, os.path.basename(dst))); print('F: 설치', F)


if __name__ == '__main__':
    main()
