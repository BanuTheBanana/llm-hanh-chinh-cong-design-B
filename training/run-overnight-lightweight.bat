@echo off
setlocal
cd /d "%~dp0.."

set "PYTHON_EXE=training\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] Khong tim thay training\.venv.
  exit /b 2
)

set "MODE_ARG="
if /I "%~1"=="smoke" set "MODE_ARG=--smoke --cooldown-seconds 0"

echo Khong tat cua so nay va khong de may sleep trong luc chay.
echo TEST kin khong duoc truyen vao batch.
echo Log: training\output\overnight-lightweight\full\logs
"%PYTHON_EXE%" training\overnight_runner.py %MODE_ARG%
set "RUN_EXIT=%ERRORLEVEL%"

if not "%RUN_EXIT%"=="0" (
  echo [FAIL] Xem log trong training\output\overnight-lightweight.
  exit /b %RUN_EXIT%
)

echo [PASS] Batch hoan tat. Xem summary trong training\output\overnight-lightweight.
exit /b 0
