# -*- coding: utf-8 -*-
r"""샤이닝 위즈덤 배포 묶음 — dist/ShiningWisdom_KR_<VER>/ : 트랙 1 xdelta + xdelta.exe + readme.txt(CP949) + 한글패치_적용.bat + zip
  (다크 세이비어 tools/make_dist.py 를 옮김) 검증: 원본 트랙 1 → xdelta 적용 → md5 = 빌드 결과(work/out) md5.
  python tools/make_dist.py   (먼저 python tools/swbuild.py --write 또는 --install)
"""
import hashlib, os, shutil, subprocess, sys, zipfile
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import disc

VER = 'v0.9'
XDELTA = r'C:\claude\utils\xdelta.exe'
NAME = 'ShiningWisdom_KR_' + VER
TITLE = '샤이닝 위즈덤 (세가 새턴 일본판) 한글 패치 ' + VER
ROMNAME = 'Shining Wisdom (Japan)'
TRACKS = 2


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest().upper()


HEAD = """{tracks}개의 트랙으로 이루어진 {rom} 의
트랙 1번에 패치하시면 됩니다.

원본md5 : {o}
패치md5 : {d}

입니다.
"""

BODY = """

[ 적용 방법 ]

  1) 원본 트랙 1 파일을 이 폴더에 복사
       "{bin}"
  2) 한글패치_적용.bat 실행 → 이름 끝에 [KR] 이 붙은 파일이 만들어집니다
  3) 만든 파일 이름을 원본 트랙 1 이름으로 바꿔 넣고, 트랙 2 와 cue 는 그대로 쓰세요
     (트랙 1 크기는 그대로라 cue 는 고칠 필요 없습니다)

  직접 적용:
    xdelta.exe -d -s "원본 트랙 1" "{patch}" "결과 파일"
  (Delta Patcher 같은 xdelta3 GUI 도구로 적용해도 됩니다. 원본이 다르면 xdelta 가 적용을 거부합니다.)


[ 바뀌는 것 ]

  - 맵 대사 전부
  - 메뉴: 아이템·장비·몬스터·지명·설명, 메뉴 제목, 예/아니오, 저장 화면
  - 저장 화면 큰 글씨 창: 시작 · 복사 · 삭제 / 본체 RAM · 카트리지 RAM
  - 이름 입력판: 히라가나 판을 한글 음절로 - 기본 이름 "마르스"


[ 알려진 점 ]

  - 이름 입력판은 정해진 한글 62음절만 고를 수 있습니다. 가타카나 판은 원본 그대로입니다.
  - 아직 끝까지 실기로 통독하지 못했습니다. 이상한 곳이 있으면 알려 주세요.
"""

BAT = r"""@echo off
chcp 949 >nul
set "XD=%~dp0xdelta.exe"
if not exist "%~dp0{bin}" (
  echo   [오류] 원본 트랙 1 파일을 이 폴더에 넣어 주세요 - readme 참고.
  pause & exit /b 1
)
"%XD%" -d -f -s "%~dp0{bin}" "%~dp0{patch}" "%~dp0{kbin}"
if errorlevel 1 (
  echo   [오류] 패치 실패 - 원본이 다를 수 있습니다 - readme 의 원본md5 확인.
  pause & exit /b 1
)
echo   완료: "{kbin}"
pause
"""


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    d = os.path.join(ROOT, 'dist', NAME)
    if os.path.isdir(d):
        shutil.rmtree(d)                                  # 옛 묶음(옛 xdelta) 남기지 않음
    os.makedirs(d)
    b = ROMNAME + ' (Track 1).bin'
    src = disc.TRACK; out = os.path.join(ROOT, 'work', 'out', b)
    assert md5(src).lower() == disc.MD5['track1'], '원본 트랙 1 md5 다름'
    patch = NAME + '.xdelta'; pp = os.path.join(d, patch)
    subprocess.run([XDELTA, '-e', '-9', '-f', '-B', str(1 << 29), '-s', src, out, pp], check=True)
    chk = os.path.join(d, '_check.bin')
    subprocess.run([XDELTA, '-d', '-f', '-B', str(1 << 29), '-s', src, pp, chk], check=True)
    o, want, got = md5(src), md5(out), md5(chk)
    os.remove(chk)
    assert got == want, ('패치 적용 결과가 빌드와 다름', got, want)
    kbin = ROMNAME + ' (Track 1) [KR].bin'
    shutil.copy2(XDELTA, os.path.join(d, 'xdelta.exe'))
    readme = (TITLE + '\n' + '=' * 60 + '\n\n' + HEAD.format(tracks=TRACKS, rom=ROMNAME, o=o, d=want)
              + BODY.format(bin=b, patch=patch))
    open(os.path.join(d, 'readme.txt'), 'wb').write(readme.replace('\n', '\r\n').encode('cp949'))
    open(os.path.join(d, '한글패치_적용.bat'), 'wb').write(
        BAT.format(bin=b, patch=patch, kbin=kbin).replace('\n', '\r\n').encode('cp949'))
    shutil.copy2(os.path.join(d, 'readme.txt'), os.path.join(ROOT, 'dist', 'readme.txt'))
    zp = os.path.join(ROOT, 'dist', NAME + '.zip')
    with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(d)):
            z.write(os.path.join(d, f), NAME + '/' + f)
    print('원본md5 %s → 패치md5 %s · %s %d B' % (o, want, patch, os.path.getsize(pp)))
    print('✅', d, '·', os.path.basename(zp), os.path.getsize(zp))
    for f in sorted(os.listdir(d)):
        print('  %-40s %12d' % (f, os.path.getsize(os.path.join(d, f))))


if __name__ == '__main__':
    main()
