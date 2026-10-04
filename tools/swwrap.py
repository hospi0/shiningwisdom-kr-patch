"""대화창 넘침 되접기 — 288px 를 넘는 대사만 낱말 단위로 다시 배치(내용은 그대로)
  쪽({0005}) 마다: 줄 수를 원래대로 유지하며 DP(가장 긴 줄 최소 → 여백 제곱합 최소, 부호 뒤에서 끊기 우대).
  3줄로 안 되면 3줄씩 쪽을 나누고 {0005} 를 넣는다.
  {0015} 든 문장(다른 창)·01379(원문도 한 줄 561px) 는 건드리지 않는다.
  결과 = work/trans/wrap.tsv (번호 · 고치기 전 · 고친 뒤) — tools/trcheck.py --merge 가 마지막에 적용(고치기 전이 지금과 다르면 경고).
python tools/swwrap.py"""
import io, os, re, sys, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import swfit
SKIP = {'01379'}
PUNCT_END = tuple(',.!?…~')


def best_lines(words, n):
    """words 를 정확히 n 줄로 — (넘침 여부, 최대폭, 비용) 최소"""
    W = len(words)
    width = lambda i, j: swfit.width(' '.join(words[i:j]))
    INF = (9, 10 ** 9, 10 ** 9)
    memo = {}

    def go(i, k):
        if (i, k) in memo:
            return memo[(i, k)]
        if k == 1:
            w = width(i, W)
            r = ((w > swfit.LIMIT, w, (swfit.LIMIT - w) ** 2 if w <= swfit.LIMIT else 0), [W])
            memo[(i, k)] = r; return r
        best = (INF, None)
        for j in range(i + 1, W - k + 2):
            w = width(i, j)
            if w > swfit.LIMIT:
                break
            sub, cuts = go(j, k - 1)
            if cuts is None:
                continue
            bonus = 0 if words[j - 1].endswith(PUNCT_END) else 60
            c = (sub[0], max(w, sub[1]), sub[2] + (swfit.LIMIT - w) ** 2 + bonus)
            if c < best[0]:
                best = (c, [j] + cuts)
        memo[(i, k)] = best
        return best


    cost, cuts = go(0, n)
    if cuts is None or cost[0]:
        return None
    out = []; i = 0
    for j in cuts:
        out.append(' '.join(words[i:j])); i = j
    return out


def wrap_page(pg):
    lines = pg.split('\\n')
    if all(swfit.width(l) <= swfit.LIMIT for l in lines):
        return [lines]
    words = ' '.join(lines).split(' ')
    for n in range(len(lines), 4):
        r = best_lines(words, n)
        if r:
            return [r]
    # 3줄로 안 됨 → 앞에서부터 3줄씩 채워 쪽 나눔
    pages = []; rest = words
    while rest:
        for cut in range(len(rest), 0, -1):
            r = best_lines(rest[:cut], min(3, cut))
            if r:
                pages.append(r); rest = rest[cut:]; break
        else:
            raise SystemExit('낱말 하나가 288px 를 넘음: %r' % rest[0])
    return pages


def wrap(t):
    pages = []
    for pg in t.split('{0005}'):
        pages += [ '\\n'.join(p) for p in wrap_page(pg)]
    return '{0005}'.join(pages)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    with open(os.devnull, 'w', encoding='utf-8') as f, contextlib.redirect_stdout(f):
        over = swfit.main()
    ids = sorted({k for w, k, i, other, s in over if not other and k not in SKIP})
    T = {l.split('\t')[0]: l.split('\t')[3] for l in open('work/trans/sw_ko.tsv', encoding='utf-8').read().splitlines()[1:]}
    rows = []
    for k in ids:
        new = wrap(T[k])
        assert new.replace('\\n', ' ').replace('{0005}', ' ').split() == T[k].replace('\\n', ' ').replace('{0005}', ' ').split(), k
        rows.append((k, T[k], new))
        print(k, '\n   전:', T[k].replace('\\n', ' / '), '\n   후:', new.replace('\\n', ' / ').replace('{0005}', ' ‖ '))
    with open('work/trans/wrap.tsv', 'w', encoding='utf-8', newline='') as w:
        w.write('#번호\t고치기 전\t고친 뒤\n')
        for r in rows:
            w.write('\t'.join(r) + '\n')
    print('→ work/trans/wrap.tsv %d문장 (쪽 나눔 %d)' % (len(rows), sum(n.count('{0005}') > o.count('{0005}') for _, o, n in rows)))


if __name__ == '__main__':
    main()
