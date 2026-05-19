param(
    [int]$CurrentPid = 0
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$RunLog = Join-Path $ProjectDir "data\quality_continuation_$Stamp.runner.log"
$OutLog = Join-Path $ProjectDir "data\quality_continuation_$Stamp.log"
$ErrLog = Join-Path $ProjectDir "data\quality_continuation_$Stamp.err.log"

function Write-RunLog {
    param([string]$Message)
    Add-Content -Path $RunLog -Value "$(Get-Date -Format o) $Message" -Encoding UTF8
}

Write-RunLog "Quality continuation wrapper started."

if ($CurrentPid -gt 0) {
    try {
        $existing = Get-Process -Id $CurrentPid -ErrorAction Stop
        Write-RunLog "Waiting for current process PID $CurrentPid ($($existing.ProcessName)) to finish."
        Wait-Process -Id $CurrentPid
    }
    catch {
        Write-RunLog "Current process PID $CurrentPid is not running; continuing."
    }
}

Start-Sleep -Seconds 20
Write-RunLog "Starting slow comprehensive verification run."

$PythonArgs = @(
    "scripts\run_continuous_verification_batch.py",
    "--continuous",
    "--max-batches", "400",
    "--stop-after-stalled-batches", "10",
    "--pause-seconds", "30",
    "--official-limit", "8",
    "--mdr-limit", "4",
    "--fda-companies", "4",
    "--mdr-plan-companies", "120",
    "--mdr-families-per-company", "8",
    "--media-websites", "8",
    "--media-page-fetches", "8",
    "--media-images-per-site", "2",
    "--media-pages-per-site", "2",
    "--search-results", "6",
    "--search-timeout", "35",
    "--search-sleep", "0.5",
    "--official-timeout", "1800",
    "--mdr-timeout", "1800",
    "--fda-stage-timeout", "600",
    "--fda-timeout", "35",
    "--fda-sleep", "0.5",
    "--media-stage-timeout", "900",
    "--media-timeout", "10",
    "--media-sleep", "0.2",
    "--download-logos-only",
    "--build-timeout", "480",
    "--excel-timeout", "480"
)

$process = Start-Process -FilePath "python" `
    -ArgumentList $PythonArgs `
    -WorkingDirectory $ProjectDir `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden `
    -PassThru `
    -Wait

Write-RunLog "Slow comprehensive verification run finished with exit code $($process.ExitCode)."
Write-RunLog "stdout: $OutLog"
Write-RunLog "stderr: $ErrLog"
exit $process.ExitCode
