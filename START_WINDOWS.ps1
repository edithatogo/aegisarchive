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
    & "runtime\python\python.exe" -B cli\launch.py @args
} elseif (Test-Path "tools\python\python.exe") {
    Write-Host "[Info] Using bundled portable Python: tools\python\python.exe" -ForegroundColor Green
    & "tools\python\python.exe" -B cli\launch.py @args
} elseif (Test-Path "..\runtime\python\python.exe") {
    Write-Host "[Info] Using parent portable Python runtime" -ForegroundColor Green
    & "..\runtime\python\python.exe" -B cli\launch.py @args
} elseif (Test-Path "..\tools\python\python.exe") {
    Write-Host "[Info] Using parent portable Python runtime" -ForegroundColor Green
    & "..\tools\python\python.exe" -B cli\launch.py @args
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 cli\launch.py @args
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python cli\launch.py @args
} else {
    Write-Host "[Error] USB runtime missing. Prepare it on a setup computer using scripts/prepare_windows_runtime.py. No target installation is required." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "[Error] The launcher exited with an error. See the messages above." -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
