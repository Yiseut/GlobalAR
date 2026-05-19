param(
    [int]$MaxBatches = 400,
    [int]$StopAfterStalledBatches = 10
)

$ErrorActionPreference = "Stop"
$StartScript = Join-Path $PSScriptRoot "start_continuous_verification.ps1"

& $StartScript -MaxBatches $MaxBatches -StopAfterStalledBatches $StopAfterStalledBatches | Out-Null
exit 0
