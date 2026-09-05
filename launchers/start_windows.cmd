@echo off
REM ---------------------------------------------------------
REM AegisArchive 1-Click Launcher for Windows
REM Auto-detects embedded portable Python or system Python.
REM ---------------------------------------------------------
cd /d "%~dp0"
echo ==========================================================
echo   Starting AegisArchive Web Console (Windows)...
echo ==========================================================

REM 1. Check for local portable embedded Python
if exist "runtime\python\python.exe" (
    echo [Info] Using bundled portable Python: runtime\python\python.exe
    "runtime\python\python.exe" cli\launch.py
    goto :end
)

if exist "tools\python\python.exe" (
    echo [Info] Using bundled portable Python: tools\python\python.exe
    "tools\python\python.exe" cli\launch.py
    goto :end
)

if exist "..\runtime\python\python.exe" (
    echo [Info] Using parent portable Python runtime
    "..\runtime\python\python.exe" cli\launch.py
    goto :end
)

if exist "..\tools\python\python.exe" (
    echo [Info] Using parent portable Python runtime
    "..\tools\python\python.exe" cli\launch.py
    goto :end
)

REM 2. Check for system Python 3 via py launcher
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 cli\launch.py
    goto :end
)

REM 3. Check for system Python in PATH
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python cli\launch.py
    goto :end
)

echo [Error] Python 3 was not found on your Windows PC.
echo Please install Python 3 from https://python.org or copy Python Embeddable into runtime\python\
pause

:end
