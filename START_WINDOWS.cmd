@echo off
REM ---------------------------------------------------------
REM AegisArchive 1-Click Launcher for Windows
REM Auto-detects embedded portable Python or system Python.
REM ---------------------------------------------------------
cd /d "%~dp0"
echo [Info] AegisArchive root: %CD%
echo [Info] Launcher: %~f0
echo ==========================================================
echo   Starting AegisArchive Web Console (Windows)...
echo ==========================================================

REM 1. Check for local portable embedded Python
if exist "runtime\python\python.exe" (
    echo [Info] Using bundled portable Python: runtime\python\python.exe
    "runtime\python\python.exe" -B cli\launch.py %*
    goto :result
)

if exist "tools\python\python.exe" (
    echo [Info] Using bundled portable Python: tools\python\python.exe
    "tools\python\python.exe" -B cli\launch.py %*
    goto :result
)

if exist "..\runtime\python\python.exe" (
    echo [Info] Using parent portable Python runtime
    "..\runtime\python\python.exe" -B cli\launch.py %*
    goto :result
)

if exist "..\tools\python\python.exe" (
    echo [Info] Using parent portable Python runtime
    "..\tools\python\python.exe" -B cli\launch.py %*
    goto :result
)

REM 2. Check for system Python 3 via py launcher
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 cli\launch.py %*
    goto :result
)

REM 3. Check for system Python in PATH
python --version >nul 2>&1
if %errorlevel% equ 0 (
    python cli\launch.py %*
    goto :result
)

echo [Error] This USB package is incomplete: bundled Python is missing.
echo Prepare the USB on a setup computer using scripts\prepare_windows_runtime.py.
echo No installation or administrator rights are needed on this computer.
pause
goto :end

:result
if errorlevel 1 (
    echo.
    echo [Error] The launcher exited with an error. See the messages above.
    pause
)

:end
