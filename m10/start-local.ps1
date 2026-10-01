param([string]$Python="", [int]$Port=8050)
$ErrorActionPreference="Stop"
$projectRoot=Split-Path $PSScriptRoot -Parent
if (-not $Python) {
  $runtimeFile=Join-Path $PSScriptRoot "private\runtime.json"
  if (Test-Path -LiteralPath $runtimeFile) { $Python=(Get-Content -LiteralPath $runtimeFile -Raw | ConvertFrom-Json).python }
  else { $Python=Join-Path $projectRoot ".venv\Scripts\python.exe" }
}
if (-not (Test-Path -LiteralPath $Python)) { throw "Pass -Python with an installed scientific Python runtime. See m10/README.md." }
$env:PYTHONPATH=(Join-Path $projectRoot "m10")+";"+(Join-Path $projectRoot "src")
if (-not $env:M10_SOURCE_DIR) { $env:M10_SOURCE_DIR=Split-Path $projectRoot -Parent }
if (-not $env:M10_DATA_DIR) { $env:M10_DATA_DIR=Join-Path $PSScriptRoot "private" }
$env:OMP_NUM_THREADS="1"
$env:OPENBLAS_NUM_THREADS="1"
Set-Location -LiteralPath $projectRoot
& $Python -m uvicorn metabocore.api:app --host 127.0.0.1 --port $Port --no-access-log
