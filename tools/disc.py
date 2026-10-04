# -*- coding: utf-8 -*-
r"""샤이닝 위즈덤 (새턴 JP) 원본 디스크 — 파일 목록·읽기, work/disc/ 에 «불변 사본» 꺼내기 (2026-10-04)
  트랙 1 = MODE1/2352 데이터 · 트랙 2 = 음악
  python tools/disc.py          → 파일 목록(LBA·크기)
  python tools/disc.py extract  → 전 파일을 work/disc/ 로
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, r'C:\claude\project\darksavior-kr-patch\tools')
sys.path.append(r'C:\claude\project\anearth-kr-patch\tools')      # cdmode1 (iso.py 가 씀)
import iso

TRACK = r'C:\claude\roms\ss\Shining Wisdom (Japan)\Shining Wisdom (Japan) (Track 1).bin'
MD5 = {'track1': '00837f5a7226d3b94eb4e77a9450a129', 'track2': 'd4048c1e705f5c576dbd3dcdda9b9c19'}
DISC = os.path.join(ROOT, 'work', 'disc')
_tree = None


def listing():
    global _tree
    if _tree is None:
        with open(TRACK, 'rb') as fh:
            _tree = iso.tree(fh)
    return _tree


def read(name):
    l, s, *_ = listing()[name]
    with open(TRACK, 'rb') as fh:
        return iso.read_user(fh, l, (s + 2047) // 2048)[:s]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    t = listing()
    for n, v in sorted(t.items(), key=lambda kv: kv[1][0]):
        print('%-28s LBA %7d  %10d B' % (n, v[0], v[1]))
    if sys.argv[1:] == ['extract']:
        for n in t:
            p = os.path.join(DISC, n.replace('/', os.sep)); os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(read(n))
        print('→', DISC, len(t))


if __name__ == '__main__':
    main()
