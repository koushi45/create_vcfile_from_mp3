$ErrorActionPreference = "Stop"
$workerPath = Join-Path $PSScriptRoot "transcribe_worker.py"
$appPath = Join-Path $PSScriptRoot "app.py"

python -m pip install -r requirements-ui.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "AutoVoiceClipper" `
    --distpath "release" `
    --workpath ".pyinstaller-cache\work" `
    --specpath ".pyinstaller-cache" `
    --add-data "$workerPath;." `
    $appPath

Compress-Archive `
    -Path "release\AutoVoiceClipper" `
    -DestinationPath "release\AutoVoiceClipper-Windows.zip" `
    -Force

Write-Host ""
Write-Host "Build complete: release\AutoVoiceClipper\AutoVoiceClipper.exe"
Write-Host "Distribution ZIP: release\AutoVoiceClipper-Windows.zip"
