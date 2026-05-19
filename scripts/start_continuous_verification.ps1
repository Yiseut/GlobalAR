param(
    [int]$MaxBatches = 400,
    [int]$StopAfterStalledBatches = 10
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$OutLog = Join-Path $ProjectDir "data\continuous_verification_$Stamp.log"
$ErrLog = Join-Path $ProjectDir "data\continuous_verification_$Stamp.err.log"
$CmdFile = Join-Path $ProjectDir "data\continuous_verification_$Stamp.cmd"
$RunInfo = Join-Path $ProjectDir "data\current_verification_run.json"
$Python = "C:\Users\gisel\miniconda3\python.exe"

$PythonArgs = @(
    "scripts\run_continuous_verification_batch.py",
    "--continuous",
    "--max-batches", "$MaxBatches",
    "--stop-after-stalled-batches", "$StopAfterStalledBatches",
    "--pause-seconds", "30",
    "--official-limit", "8",
    "--mdr-limit", "4",
    "--fda-companies", "4",
    "--mdr-plan-companies", "120",
    "--mdr-families-per-company", "8",
    "--media-websites", "0",
    "--media-page-fetches", "0",
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
    "--skip-media-assets",
    "--product-gap-audit",
    "--build-timeout", "480",
    "--excel-timeout", "480"
)

function Quote-CmdArg {
    param([string]$Value)
    return '"' + ($Value -replace '"', '\"') + '"'
}

$ComSpec = $env:ComSpec
if (-not $ComSpec) {
    $ComSpec = "C:\Windows\System32\cmd.exe"
}

$ArgLine = ($PythonArgs | ForEach-Object { Quote-CmdArg $_ }) -join " "
$CommandBody = "$(Quote-CmdArg $Python) $ArgLine > $(Quote-CmdArg $OutLog) 2> $(Quote-CmdArg $ErrLog)"
@(
    "@echo off",
    "cd /d $(Quote-CmdArg $ProjectDir)",
    $CommandBody,
    "exit /b %ERRORLEVEL%"
) | Set-Content -Path $CmdFile -Encoding ASCII

$StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
$StartInfo.FileName = $CmdFile
$StartInfo.WorkingDirectory = $ProjectDir
$StartInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$StartInfo.UseShellExecute = $true
$Process = [System.Diagnostics.Process]::Start($StartInfo)

$Info = [ordered]@{
    started_at = (Get-Date -Format o)
    pid = $Process.Id
    process_name = $Process.ProcessName
    project_dir = $ProjectDir
    stdout_log = $OutLog
    stderr_log = $ErrLog
    cmd_file = $CmdFile
    max_batches = $MaxBatches
    stop_after_stalled_batches = $StopAfterStalledBatches
    command = "$Python $($PythonArgs -join ' ')"
}

$Info | ConvertTo-Json -Depth 4 | Set-Content -Path $RunInfo -Encoding UTF8
$Info | ConvertTo-Json -Depth 4
