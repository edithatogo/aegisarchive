$ErrorActionPreference = 'Stop'
$out = Join-Path $env:RUNNER_TEMP 'aegisarchive-acceptance\mirroring.json'
$parent = Split-Path $out -Parent
New-Item -ItemType Directory -Force -Path $parent | Out-Null
if (Get-Command docker -ErrorAction SilentlyContinue) { Write-Host 'Docker detected but intentionally not used.' }
python scripts/mirroring_acceptance.py --output $out
python scripts/mirroring_acceptance.py --check --output $out
$receipt = Get-Content -Raw $out | ConvertFrom-Json
if ($receipt.offline.source_requests -ne 0) { throw 'Offline acceptance reported source requests.' }
if (-not $receipt.capabilities.static_html.Equals('supported')) { throw 'Static HTML capability was not supported.' }
Write-Host "Windows portable acceptance passed: $out"
