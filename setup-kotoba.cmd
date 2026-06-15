@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set PIP_PROGRESS_BAR=off

echo [1/3] Checking Python 3.12...
set "PYTHON312="
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON312=%%P"
if not defined PYTHON312 if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYTHON312=%LocalAppData%\Programs\Python\Python312\python.exe"
if not defined PYTHON312 (
  echo Python 3.12 was not found.
  echo Other Python versions are not compatible with the pinned ML packages.
  echo Install Python 3.12 from https://www.python.org/downloads/
  pause
  exit /b 1
)
echo Using "%PYTHON312%"

echo [2/3] Creating the Kotoba-Whisper environment...
"%PYTHON312%" -m venv ".venv-kotoba"
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
