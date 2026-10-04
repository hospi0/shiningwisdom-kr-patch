"""받은 번역(my files/번역/sw_*.tsv) 검사·병합
  검사: 번호·원문 일치, 제어 코드 순서, 줄 수(\\n), 빈 번역, 남은 가나·한자·「。」
  병합(--merge) → work/trans/sw_ko.tsv 한 파일
    ① 손질표 work/trans/fix.tsv (번호 → 고친 번역) 우선
    ①' 용어 통일표 work/trans/terms.tsv (원문 조건·정규식·바꿈)
    ② norm: 우리식 말줄임(가운뎃점 2개 이상 → … 한 칸, 바로 뒤 마침표 흡수) · 「。」→「.」
            · 문장부호 뒤 공백 «한 칸»만 삭제(두 칸 이상은 칸 맞춤이라 둠)
python tools/trcheck.py [--merge]"""
import glob, os, re, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
TOK = re.compile(r'\{[0-9A-F]{4}\}')
KANA = re.compile(r'[ぁ-ヺー一-鿿。]')          # 가나·장음·한자·「。」(・ 30FB 는 따로)
PUNCT_SP = re.compile(r'''([,.!?:;)\]}'"~、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥]) (?! )''')


def src():
    out = {}
    for f in ('work/text/sw_etc.tsv', 'work/text/sw_sys.tsv'):
        for ln in open(f, encoding='utf-8').read().splitlines()[1:]:
            c = ln.split('\t'); out[c[0]] = c[3] if f.endswith('etc.tsv') else c[5]
    return out


def recv():
    rows = collections.OrderedDict(); dup = []
    for f in sorted(glob.glob('my files/번역/sw_*.tsv')):
        for ln in open(f, encoding='utf-8-sig').read().splitlines()[1:]:
            if not ln.strip():
                continue
            c = ln.split('\t')
            if c[0] in rows:
                dup.append(c[0])
            rows[c[0]] = (os.path.basename(f), c[3], c[4] if len(c) > 4 else '')
    return rows, dup


def norm(t):
    t = re.sub(r'・{2,}[。.]?', '…', t)
    t = re.sub(r'\.{3,}', '…', t)                         # 마침표 셋 이상도 우리식 … (실기 2026-10-04 «분명...감이»)
    t = re.sub(r'…[。.]', '…', t)
    t = t.replace('。', '.')
    return punct_sp(t)


def punct_sp(t):
    """부호 뒤 공백 1칸 삭제 — ⛔제어 코드 {XXXX} 의 «}» 는 부호가 아니다(«하지만{0006} 그» 가 붙었다). 코드 사이 글 조각마다만."""
    parts = re.split(r'(\{[0-9A-F]{4}\}|\\n)', t)
    return ''.join(p if i % 2 else PUNCT_SP.sub(r'\1', p) for i, p in enumerate(parts))


def check(S, R, label):
    prob = collections.defaultdict(list)
    for k in S:
        if k not in R:
            prob['빠진 번호'].append(k)
    for k, (f, o, t) in R.items():
        if k not in S:
            prob['없는 번호'].append(k); continue
        if o != S[k]:
            prob['원문 다름'].append(k)
        if not t.strip():
            prob['빈 번역'].append(k); continue
        if TOK.findall(o) != TOK.findall(t):
            prob['제어 코드 다름'].append(k)
        if o.count('\\n') != t.count('\\n'):
            prob['줄 수 다름(경고)'].append(k)
        if KANA.search(t):
            prob['가나·한자·。 남음'].append(k)
        if re.search(r'・{2,}', t):
            prob['・・ 말줄임 남음'].append(k)
        if punct_sp(t) != t:
            prob['부호 뒤 공백'].append(k)
    print('[%s] 원문 %d · 번역 %d' % (label, len(S), len(R)))
    for k, v in prob.items():
        if v:
            print('  %-16s %4d  %s' % (k, len(v), ' '.join(v[:12])))
    return prob


def main():
    S = src(); R, dup = recv()
    if dup:
        print('중복 번호', dup)
    check(S, R, '받은 번역')
    if '--merge' not in sys.argv:
        return
    fix = {}
    for ln in open('work/trans/fix.tsv', encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t'); fix[c[0]] = c[1]
    terms = []                                                         # 용어 통일표: (원문 조건, 정규식, 바꿈)
    for ln in open('work/trans/terms.tsv', encoding='utf-8').read().splitlines()[1:]:
        c = ln.split('\t'); terms.append((c[0], re.compile(c[1]), c[2]))
    hit = collections.Counter()

    def unify(o, t):
        for cond, rx, rep in terms:
            if cond and cond not in o:
                continue
            if rep == '왕녀' and ('姫' in o or 'プリンセス' in o):
                continue
            t, n = rx.subn(rep, t); hit[rep] += n
        return t
    os.makedirs('work/trans', exist_ok=True)
    M = collections.OrderedDict()
    with open('work/trans/sw_ko.tsv', 'w', encoding='utf-8', newline='') as w:
        w.write('#번호\t받은 파일\t원문\t번역\n')
        for k in S:
            if k in R:
                f, o, t = R[k]; t = norm(unify(S[k], fix.get(k, t))); M[k] = (f, S[k], t)
                w.write('%s\t%s\t%s\t%s\n' % (k, f, S[k], t))
    print('→ work/trans/sw_ko.tsv (손질 %d줄) · 용어 통일 %s' % (len(fix), dict(hit)))
    check(S, M, '병합본')


if __name__ == '__main__':
    main()
