@echo off
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 (
  echo Python 3 is required. Install it from https://www.python.org/downloads/ then retry.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe optimizer_gui.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo Setup or launch failed. See the error above.
pause
exit /b 1
