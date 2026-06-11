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

echo Installing CUDA 12.1 compatible PyTorch...
echo This requires an NVIDIA CUDA-compatible GPU and a recent NVIDIA driver.
".venv-kotoba\Scripts\python.exe" -m pip install --force-reinstall --no-deps torch==2.4.1 torchaudio==2.4.1 --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 goto :failed

echo Checking CUDA availability...
".venv-kotoba\Scripts\python.exe" -c "import torch; print('PyTorch:', torch.__version__); print('CUDA runtime:', torch.version.cuda); print('CUDA available:', torch.cuda.is_available()); print('GPU count:', torch.cuda.device_count())"
if errorlevel 1 goto :failed

echo.
echo GPU environment setup completed.
echo If CUDA available is False, update the NVIDIA driver or use CPU mode.
pause
exit /b 0

:failed
echo.
echo GPU environment setup failed. Review the error shown above.
pause
exit /b 1
