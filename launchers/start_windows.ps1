# ---------------------------------------------------------
# AegisArchive PowerShell Launcher for Windows
# Auto-detects embedded portable Python or system Python.
# ---------------------------------------------------------
Set-Location -Path $PSScriptRoot
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AegisArchive Web Console (PowerShell)..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Test-Path "runtime\python\python.exe") {
    Write-Host "[Info] Using bundled portable Python: runtime\python\python.exe" -ForegroundColor Green
    & "runtime\python\python.exe" cli\launch.py
} elseif (Test-Path "tools\python\python.exe") {
    Write-Host "[Info] Using bundled portable Python: tools\python\python.exe" -ForegroundColor Green
    & "tools\python\python.exe" cli\launch.py
} elseif (Test-Path "..\runtime\python\python.exe") {
    Write-Host "[Info] Using parent portable Python runtime" -ForegroundColor Green
    & "..\runtime\python\python.exe" cli\launch.py
} elseif (Test-Path "..\tools\python\python.exe") {
    Write-Host "[Info] Using parent portable Python runtime" -ForegroundColor Green
    & "..\tools\python\python.exe" cli\launch.py
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 cli\launch.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python cli\launch.py
} else {
    Write-Host "[Error] Python 3 was not found. Please install from https://python.org or place Python Embeddable into runtime\python\" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
