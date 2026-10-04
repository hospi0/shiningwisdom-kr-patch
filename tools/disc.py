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


def patch_track(dst, files, log=print):
    """원본 트랙 1 → dst, files {이름: 바이트}. 원래 섹터 안이면 제자리, 넘치면 마지막 실제 파일 뒤 빈 곳(LBA 39370‥)으로.
    ⛔트랙 크기는 안 바꾼다 — CDDA2 항목(LBA 39820)은 트랙 2(음악)를 가리키는 가짜라 «파일 영역 끝» 계산에서 뺀다. 뒷간격 150섹터는 비워 둔다."""
    import shutil, struct
    shutil.copyfile(TRACK, dst)
    total = os.path.getsize(TRACK) // 2352
    with open(dst, 'r+b') as fh:
        dl, dirdata, ents = iso.entries(fh)
        E = {nm: (l, s, off) for nm, l, s, off in ents}
        cur = max(l + (s + 2047) // 2048 for nm, l, s, _ in ents if l < total)
        for nm, data in files.items():
            l, s, off = E[nm]
            have = (s + 2047) // 2048; need = max(1, (len(data) + 2047) // 2048)
            if need <= have:
                lba, n = l, have
            else:
                lba, n = cur, need; cur += need
                assert cur <= total - 150, ('트랙 1 빈 곳 부족', cur, total)
            pad = data + bytes(n * 2048 - len(data))
            for k in range(n):
                fh.seek((lba + k) * 2352); fh.write(iso.sector(lba + k, pad[k * 2048:(k + 1) * 2048]))
            struct.pack_into('<I', dirdata, off + 2, lba); struct.pack_into('>I', dirdata, off + 6, lba)
            struct.pack_into('<I', dirdata, off + 10, len(data)); struct.pack_into('>I', dirdata, off + 14, len(data))
            log('  %-10s %7d → %7d B  LBA %5d%s' % (nm, s, len(data), lba, ' (옮김, 옛 %d)' % l if lba != l else ''))
        for k in range(len(dirdata) // 2048):
            fh.seek((dl + k) * 2352); fh.write(iso.sector(dl + k, dirdata[k * 2048:(k + 1) * 2048]))
    assert os.path.getsize(dst) == total * 2352
    with open(dst, 'rb') as fh:                                    # 되읽기
        _, _, ents = iso.entries(fh)
        for nm, l, s, _ in ents:
            if nm in files:
                assert iso.read_user(fh, l, (s + 2047) // 2048)[:s] == files[nm], nm + ' 되읽기 다름'


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
