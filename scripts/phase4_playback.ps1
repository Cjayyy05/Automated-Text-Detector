param(
    [switch]$ShowPlayback,
    [string]$OutputDirectory = 'artifacts/phase4-short',
    [ValidateRange(1, 50)][int]$Count = 4,
    [int]$Seed = 20261103,
    [switch]$WithActivityGate,
    [ValidateRange(0, 2000)][int]$DrainMs = 0,
    [switch]$PreciseStimulus
)
$ErrorActionPreference = 'Stop'
if (-not $ShowPlayback) { throw 'Explicit -ShowPlayback is required to open test windows. Clipboard is memory-only.' }
Set-Location (Split-Path $PSScriptRoot -Parent)
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a new output directory; reports are never overwritten.' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$runs = @()
foreach ($profile in @('discount', 'game')) {
    foreach ($mode in @('baseline', 'cpu')) {
        $runs += @{ Profile = $profile; Mode = $mode; Gate = 0 }
    }
}
if ($WithActivityGate) { $runs += @{ Profile = 'game'; Mode = 'cpu-gate'; Gate = 100 } }
$failed = 0
foreach ($run in $runs) {
    $name = "$($run.Profile)-$($run.Mode)"
    $report = Join-Path $OutputDirectory "$name.jsonl"
    $arguments = @('scripts/game_playback.py', '--synthetic-count', "$Count", '--seed', "$Seed", '--profile', $run.Profile, '--profile-inference', '--drain-ms', "$DrainMs", '--report', $report)
    if ($run.Mode -ne 'baseline') {
        $arguments += @('--scale', '1', '--threads', '4', '--cpu-arena', '--no-spinning', '--det-limit', '640')
    }
    if ($run.Gate) { $arguments += @('--activity-gate-ms', "$($run.Gate)") }
    if ($PreciseStimulus) { $arguments += '--precise-stimulus' }
    Write-Output ('.\.venv\Scripts\python.exe ' + ($arguments -join ' '))
    & .\.venv\Scripts\python.exe @arguments > (Join-Path $OutputDirectory "$name-console.txt")
    $code = $LASTEXITCODE
    Write-Output "$name exit=$code"
    if ($code -ne 0) { $failed += 1 }
}
Write-Output "$failed runs did not achieve full recall; inspect each report, including expected O/0 abstentions."
if ($failed) { exit 1 }
