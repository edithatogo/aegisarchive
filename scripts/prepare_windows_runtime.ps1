$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$lock = Get-Content -Raw (Join-Path $root 'portable/windows-python.json') | ConvertFrom-Json
$temp = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
New-Item -ItemType Directory $temp | Out-Null
try {
    $zip = Join-Path $temp 'python.zip'
    Invoke-WebRequest $lock.url -OutFile $zip
    if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $lock.sha256) {
        throw 'Windows Python archive checksum mismatch'
    }
    Expand-Archive $zip (Join-Path $temp 'bootstrap')
    & (Join-Path $temp 'bootstrap/python.exe') (Join-Path $root 'scripts/prepare_windows_runtime.py') --archive $zip
    if ($LASTEXITCODE -ne 0) { throw 'Runtime preparation failed' }
} finally { Remove-Item -Recurse -Force $temp }
