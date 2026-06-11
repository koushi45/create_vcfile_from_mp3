@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PIP_PROGRESS_BAR=off

echo [1/3] Checking Python 3.12...
py -3.12 -c "import sys; print(sys.version)" >nul 2>&1
if errorlevel 1 (
  echo Python 3.12 was not found.
  echo Install Python 3.12 from https://www.python.org/downloads/
  pause
  exit /b 1
)

echo [2/3] Creating the Kotoba-Whisper environment...
py -3.12 -m venv ".venv-kotoba"
if errorlevel 1 goto :failed

echo [3/3] Installing required packages...
".venv-kotoba\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv-kotoba\Scripts\python.exe" -m pip install -r "requirements-kotoba.txt"
if errorlevel 1 goto :failed
".venv-kotoba\Scripts\python.exe" -m pip install --no-deps "git+https://github.com/huggingface/diarizers.git"
if errorlevel 1 goto :failed
".venv-kotoba\Scripts\python.exe" "patch-diarizers.py"
if errorlevel 1 goto :failed

echo.
echo Package setup completed successfully.
echo Next, run setup-huggingface-login.cmd.
pause
exit /b 0

:failed
echo.
echo Setup failed. Review the error shown above.
pause
exit /b 1
