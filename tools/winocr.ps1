# Windows.Media.Ocr (ja) 로 폴더 안 PNG 를 읽어 같은 이름 .txt 에 «단어\tX\tY\tW\tH» 줄로 쓴다.
#   powershell -ExecutionPolicy Bypass -File tools\winocr.ps1 -Dir work\ocr
param([string]$Dir)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType = WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($op, [Type]$t) {
    $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage((New-Object Windows.Globalization.Language 'ja'))
if ($null -eq $engine) { throw 'ja OCR 엔진을 만들 수 없다' }
Write-Output ("최대 그림 크기 {0}" -f [Windows.Media.Ocr.OcrEngine]::MaxImageDimension)
$files = Get-ChildItem -LiteralPath $Dir -Filter 'img_*.png' | Sort-Object Name
$n = 0
foreach ($f in $files) {
    $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f.FullName)) ([Windows.Storage.StorageFile])
    $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
    $dec = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bmp = Await ($dec.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $res = Await ($engine.RecognizeAsync($bmp)) ([Windows.Media.Ocr.OcrResult])
    $out = New-Object System.Collections.Generic.List[string]
    foreach ($l in $res.Lines) {
        foreach ($w in $l.Words) {
            $r = $w.BoundingRect
            $out.Add(("{0}`t{1}`t{2}`t{3}`t{4}" -f $w.Text, $r.X, $r.Y, $r.Width, $r.Height))
        }
    }
    [IO.File]::WriteAllLines(($f.FullName -replace '\.png$', '.txt'), $out.ToArray(), (New-Object System.Text.UTF8Encoding $false))
    $stream.Dispose()
    $n++
}
Write-Output ("OCR {0}장 완료" -f $n)
