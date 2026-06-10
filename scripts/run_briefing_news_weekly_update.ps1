param(
  [int]$Days = 8
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Invoke-Step {
  param(
    [string]$Name,
    [string[]]$PythonArgs,
    [switch]$AllowFailure
  )

  Write-Host ""
  Write-Host "== $Name =="
  & python @PythonArgs
  if ($LASTEXITCODE -ne 0) {
    if ($AllowFailure) {
      Write-Host "$Name failed with exit code $LASTEXITCODE"
      return $false
    }
    throw "$Name failed with exit code $LASTEXITCODE"
  }
  return $true
}

$null = Invoke-Step "Sync briefing daily reports" -PythonArgs @("-X", "utf8", "scripts\sync_briefing_news_events.py", "--days", "$Days")
$null = Invoke-Step "Rescue full text and verify official sources" -PythonArgs @("-X", "utf8", "scripts\run_briefing_update_pipeline.py")
$null = Invoke-Step "Rebuild dashboard data" -PythonArgs @("-X", "utf8", "scripts\build_data.py")
$null = Invoke-Step "Refresh company profile bridge" -PythonArgs @("-X", "utf8", "scripts\sync_company_column_profiles.py")
if (-not (Invoke-Step "Run dashboard smoke test" -PythonArgs @("-X", "utf8", "scripts\smoke_test.py") -AllowFailure)) {
  Write-Host ""
  Write-Host "Smoke test failed once; rebuilding and retrying to clear concurrent build drift."
  $null = Invoke-Step "Rebuild dashboard data retry" -PythonArgs @("-X", "utf8", "scripts\build_data.py")
  $null = Invoke-Step "Refresh company profile bridge retry" -PythonArgs @("-X", "utf8", "scripts\sync_company_column_profiles.py")
  $null = Invoke-Step "Run dashboard smoke test retry" -PythonArgs @("-X", "utf8", "scripts\smoke_test.py")
}

Write-Host ""
Write-Host "Briefing weekly update complete."
Write-Host "Summary: $RepoRoot\data\audits\briefing_update_pipeline_summary_latest.md"
