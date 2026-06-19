$ErrorActionPreference = "Stop"
$workerPath = Join-Path $PSScriptRoot "transcribe_worker.py"
$appPath = Join-Path $PSScriptRoot "app.py"
$uninstallerPath = Join-Path $PSScriptRoot "uninstall.py"
$releaseName = "AutoVoiceClipper"

python -m pip install -r requirements-ui.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $releaseName `
    --distpath "release" `
    --workpath ".pyinstaller-cache\work" `
    --specpath ".pyinstaller-cache" `
    $appPath

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --uac-admin `
    --name "UninstallAutoVoiceClipper" `
    --distpath "release\$releaseName" `
    --workpath ".pyinstaller-cache\uninstall-work" `
    --specpath ".pyinstaller-cache" `
    $uninstallerPath

Copy-Item $workerPath "release\$releaseName\transcribe_worker.py" -Force
Copy-Item "clip_export.py" "release\$releaseName\clip_export.py" -Force
Copy-Item "requirements-kotoba.txt" "release\$releaseName\requirements-kotoba.txt" -Force
Copy-Item "patch-diarizers.py" "release\$releaseName\patch-diarizers.py" -Force
Copy-Item "setup-kotoba.cmd" "release\$releaseName\setup-kotoba.cmd" -Force
Copy-Item "setup-huggingface-login.cmd" "release\$releaseName\setup-huggingface-login.cmd" -Force
Copy-Item "setup-gpu.cmd" "release\$releaseName\setup-gpu.cmd" -Force

Compress-Archive `
    -Path "release\$releaseName" `
    -DestinationPath "release\$releaseName-Windows.zip" `
    -Force

Write-Host ""
Write-Host "Build complete: release\$releaseName\$releaseName.exe"
Write-Host "Distribution ZIP: release\$releaseName-Windows.zip"
