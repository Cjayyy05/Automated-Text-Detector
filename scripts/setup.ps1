param([string]$Python = 'py')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
New-Item -ItemType Directory -Force .tmp | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
try {
    $env:TEMP = Join-Path (Get-Location) '.tmp'
    $env:TMP = $env:TEMP
    if (-not (Test-Path .venv\Scripts\python.exe)) {
        if ($Python -eq 'py') { & $Python -3.12 -m venv .venv }
        else { & $Python -m venv .venv }
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 virtual environment creation failed' }
    }
    & .\.venv\Scripts\python.exe -c 'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required' }
    & .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -c requirements-lock.txt -e '.[dev,windows]'
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
    & .\.venv\Scripts\python.exe -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency compatibility check failed' }
} finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}
