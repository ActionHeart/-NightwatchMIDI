@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Python environment not found. Follow Quick Start in README.md first.
    pause
    exit /b 1
)
echo Starting NightwatchMIDI with console output for troubleshooting...
".venv\Scripts\python.exe" -m nightwatch_midi
pause
