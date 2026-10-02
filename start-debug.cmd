@echo off
setlocal
cd /d "%~dp0"
call "%~dp0setup.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)
echo Starting NightwatchMIDI with console output for troubleshooting...
".venv\Scripts\python.exe" -I -m nightwatch_midi
pause
