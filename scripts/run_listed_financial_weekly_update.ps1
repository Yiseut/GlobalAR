param(
  [int]$MarketLimit = 80,
  [double]$MarketSleep = 0.02,
  [double]$SecSleep = 0.05
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Run-Step {
  param(
    [string]$Name,
    [scriptblock]$Command
  )
  Write-Host "== $Name =="
  & $Command
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

Run-Step "Collect market snapshot" {
  python scripts\collect_market_snapshot.py --limit $MarketLimit --sleep $MarketSleep
}

Run-Step "Collect SEC financial metrics" {
  python scripts\collect_sec_financial_metrics.py --sleep $SecSleep
}

Run-Step "Merge non-US financial metrics" {
  python scripts\merge_non_us_financial_metrics.py
}

Run-Step "Run deterministic Xueqiu market cross-check" {
  python scripts\collect_xueqiu_market_check.py --scope listed --limit $MarketLimit
}

Run-Step "Promote financial fields to source workbook" {
  python scripts\promote_company_financials_to_companies.py
}

Run-Step "Rebuild dashboard data" {
  python scripts\build_data.py
}

Run-Step "Smoke test" {
  python scripts\smoke_test.py
}
