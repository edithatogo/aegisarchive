# ---------------------------------------------------------
# AegisArchive PowerShell Launcher for Windows
# ---------------------------------------------------------
Set-Location -Path $PSScriptRoot
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting AegisArchive Web Console (PowerShell)..." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 cli\launch.py
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python cli\launch.py
} else {
    Write-Host "[Error] Python 3 was not found. Please install from https://python.org" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
}
