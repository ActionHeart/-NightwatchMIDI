@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -I tools\bootstrap.py
    exit /b
)
py -3.11 -c "import struct; assert struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
    py -3.11 -I tools\bootstrap.py
    exit /b
)
python -c "import sys,struct; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8" >nul 2>&1
if not errorlevel 1 (
    python -I tools\bootstrap.py
    exit /b
)
echo Python 3.11 [64-bit] was not found.
echo Install Python 3.11 with the Python Launcher or Add Python to PATH enabled.
echo Then double-click start.cmd again. First launch needs internet access.
echo Ready-to-run Windows EXE: https://github.com/ActionHeart/-NightwatchMIDI/releases/latest
exit /b 1
