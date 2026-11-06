param([switch]$Ocr)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .tmp | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
try {
    $env:TEMP = Join-Path (Get-Location) '.tmp'
    $env:TMP = $env:TEMP
    & .\.venv\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'pip check failed' }
    & .\.venv\Scripts\python.exe -m ruff check .
    if ($LASTEXITCODE -ne 0) { throw 'Ruff lint failed' }
    & .\.venv\Scripts\python.exe -m ruff format --check .
    if ($LASTEXITCODE -ne 0) { throw 'Ruff format failed' }
    $typeArgs = @('src')
    & .\.venv\Scripts\python.exe -c "from importlib.util import find_spec; raise SystemExit(find_spec('PySide6') is None)"
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Optional PySide6 dependency absent. GUI type checking and Qt tests require the gui extra.'
        $typeArgs += @('--exclude', 'stream_code_capture[/\\]gui\.py$')
    }
    & .\.venv\Scripts\python.exe -m mypy @typeArgs
    if ($LASTEXITCODE -ne 0) { throw 'Static type check failed' }
    if ($Ocr) { & .\.venv\Scripts\python.exe -m pytest -q --run-ocr }
    else { & .\.venv\Scripts\python.exe -m pytest -q }
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}
