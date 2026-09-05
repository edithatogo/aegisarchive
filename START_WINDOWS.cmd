@echo off
REM ---------------------------------------------------------
REM AegisArchive 1-Click Launcher for Windows
REM ---------------------------------------------------------
cd /d "%~dp0"
echo ==========================================================
echo   Starting AegisArchive Web Console (Windows)...
echo ==========================================================

py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    py -3 cli\launch.py
    goto :end
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    python cli\launch.py
    goto :end
)

echo [Error] Python 3 was not found on your Windows PC.
echo Please install Python 3 from https://python.org
pause

:end
