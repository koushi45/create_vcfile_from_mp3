@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PIP_PROGRESS_BAR=off

if not exist ".venv-kotoba\Scripts\python.exe" (
  echo Run setup-kotoba.cmd first.
  pause
  exit /b 1
)

echo Ensuring compatible package versions...
".venv-kotoba\Scripts\python.exe" -m pip install -r "requirements-kotoba.txt"
if errorlevel 1 goto :failed
".venv-kotoba\Scripts\python.exe" -m pip install --no-deps "git+https://github.com/huggingface/diarizers.git"
if errorlevel 1 goto :failed
".venv-kotoba\Scripts\python.exe" "patch-diarizers.py"
if errorlevel 1 goto :failed

echo Before continuing, accept the terms for all models in your browser:
echo https://huggingface.co/pyannote/segmentation-3.0
echo https://huggingface.co/pyannote/speaker-diarization-3.1
echo https://huggingface.co/pyannote/speaker-diarization-community-1
echo.
echo Your token needs read access to public gated repositories.
echo Press any key after accepting all terms.
pause >nul

echo Logging in to Hugging Face with the latest token...
".venv-kotoba\Scripts\hf.exe" auth logout >nul 2>&1
".venv-kotoba\Scripts\hf.exe" auth login
if errorlevel 1 goto :failed

echo Downloading Kotoba-Whisper and PyAnnote models...
set PYTHONWARNINGS=ignore
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
".venv-kotoba\Scripts\python.exe" -c "from transformers import pipeline; pipeline(model='kotoba-tech/kotoba-whisper-v2.2', trust_remote_code=True)"
if errorlevel 1 goto :failed

echo.
echo Hugging Face setup completed successfully.
pause
exit /b 0

:failed
echo.
echo Hugging Face setup failed. Review the error shown above.
pause
exit /b 1
