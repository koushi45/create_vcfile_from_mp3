$ErrorActionPreference = "Stop"

python -m pip install -r requirements-ui.txt
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "AutoVoiceClipper" `
    --add-data "transcribe_worker.py;." `
    app.py

Write-Host ""
Write-Host "Build complete: dist\AutoVoiceClipper\AutoVoiceClipper.exe"
