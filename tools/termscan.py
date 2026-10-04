"""용어 통일 검사 — 원문 가타카나 낱말(2자 이상)마다 번역 쪽 대응 낱말을 모아, 갈리는 것을 보인다.
python tools/termscan.py [최소 등장 수=2]"""
import re, sys, collections
sys.stdout.reconfigure(encoding='utf-8')
T = [l.split('\t') for l in open('work/trans/sw_ko.tsv', encoding='utf-8').read().splitlines()[1:]]
KATA = re.compile(r'[ァ-ヺ][ァ-ヺー・]+')
JOSA = re.compile(r'(으로부터|에게서|에게|한테|으로|로|에서|에|의|은|는|이|가|을|를|과|와|도|만|님|이여|여|야|아|이다|이야|이군|이란|라는|이라는|라고|이라고|께서|까지|부터|처럼|보다|들)$')
HAN = re.compile(r'[가-힣]+')
MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 2
occ = collections.defaultdict(list)
for k, f, o, t in T:
    for w in set(KATA.findall(TOKS := re.sub(r'\{[0-9A-F]{4}\}', ' ', o))):
        occ[w].append((k, o, t))
rows = []
for w, L in occ.items():
    if len(L) < MIN:
        continue
    cnt = collections.Counter()
    for k, o, t in L:
        cnt.update(set(JOSA.sub('', x) for x in HAN.findall(t)))
    top, n = cnt.most_common(1)[0]
    miss = [(k, t) for k, o, t in L if top not in [JOSA.sub('', x) for x in HAN.findall(t)]]
    rows.append((w, len(L), top, n, miss))
rows.sort(key=lambda r: -r[1])
for w, c, top, n, miss in rows:
    flag = '' if not miss else '  ⚠%d' % len(miss)
    print('%s ×%d → %s (%d)%s' % (w, c, top, n, flag))
    for k, t in miss[:4]:
        print('      %s %s' % (k, t[:70]))
