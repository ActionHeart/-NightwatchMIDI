@echo off
setlocal
cd /d "%~dp0"
call "%~dp0setup.cmd"
if errorlevel 1 (
    pause
    exit /b 1
)
set "PYW=.venv\Scripts\pythonw.exe"
if exist "%PYW%" (
    start "" "%PYW%" -I -m nightwatch_midi
) else (
    start "" ".venv\Scripts\python.exe" -I -m nightwatch_midi
)
exit /b 0
