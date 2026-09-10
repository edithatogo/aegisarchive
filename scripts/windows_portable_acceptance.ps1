$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$python = Join-Path (Get-Location) 'runtime/python/python.exe'
if (-not (Test-Path $python)) { throw 'USB runtime missing' }
# Remove runner-installed Python and development tools from discovery.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
$env:PYTHONHOME = ''
$env:PYTHONPATH = ''
& $python -c 'import ssl, sqlite3, http.server, cli.capture_bridge; print("Bundled imports passed")'
if ($LASTEXITCODE -ne 0) { throw 'Bundled imports failed' }
& $python -m unittest discover -s tests -p test_windows_runtime.py -v
if ($LASTEXITCODE -ne 0) { throw 'USB launcher regression failed' }
& $python -m unittest discover -s tests -p test_cli.py -v
if ($LASTEXITCODE -ne 0) { throw 'Actual synthetic capture regression failed' }
Write-Host 'Bundled Windows runtime and capture acceptance passed without system Python.'
