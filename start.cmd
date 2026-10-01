@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Follow Quick Start in README.md first.
    pause
    exit /b 1
)
set "PYW=.venv\Scripts\pythonw.exe"
if exist "%PYW%" (
    start "" "%PYW%" -m nightwatch_midi
) else (
    start "" ".venv\Scripts\python.exe" -m nightwatch_midi
)
exit /b 0
