$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$TaskName = "\GlobalAestheticsContinuousVerification"
$RunInfoPath = Join-Path $ProjectDir "data\current_verification_run.json"
$WatchdogLog = Join-Path $ProjectDir "data\verification_watchdog.log"
$StartScript = Join-Path $PSScriptRoot "start_continuous_verification.ps1"

function Write-WatchdogLog {
    param([string]$Message)
    Add-Content -Path $WatchdogLog -Value "$(Get-Date -Format o) $Message" -Encoding UTF8
}

function Test-TrackedProcess {
    if (-not (Test-Path $RunInfoPath)) {
        return $false
    }
    try {
        $RunInfo = Get-Content -Path $RunInfoPath -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-WatchdogLog "Could not parse current run info: $($_.Exception.Message)"
        return $false
    }
    if (-not $RunInfo.pid) {
        return $false
    }
    $Process = Get-Process -Id ([int]$RunInfo.pid) -ErrorAction SilentlyContinue
    return $null -ne $Process
}

if (Test-TrackedProcess) {
    Write-WatchdogLog "Main verification task is already running."
    exit 0
}

Write-WatchdogLog "Main verification task is not running; starting scheduled task."
if (Test-Path $StartScript) {
    $PowerShell = Join-Path $PSHOME "powershell.exe"
    $Args = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $StartScript
    )
    Start-Process -FilePath $PowerShell `
        -ArgumentList $Args `
        -WorkingDirectory $ProjectDir `
        -WindowStyle Hidden | Out-Null
}
else {
    schtasks /Run /TN $TaskName | Out-Null
}
Start-Sleep -Seconds 10

if (Test-TrackedProcess) {
    Write-WatchdogLog "Main verification task restarted successfully."
    exit 0
}

Write-WatchdogLog "Restart attempted, but no tracked process is visible yet."
exit 1
