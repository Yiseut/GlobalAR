# refresh_dashboard.ps1
# -----------------------------------------------------------------------------
# Nightly lightweight chain that keeps the v3 dashboard fresh:
#   1. Consume new briefing HTML files into briefing_update_candidates.csv
#      (scripts/sync_briefing_news_events.py)
#   2. Mark items the user pushed to WeChat as user_curated
#      (scripts/consume_wechat_curated_news.py)
#   3. Rebuild the db from xlsx/csv  (scripts/build_data.py)
#   4. Rebuild all 11 v3 derived JS files (scripts/_v3_build_*.py)
#   5. Stamp web/v3/data-as-of.json so the topbar shows the right time
#
# Runs via the \GlobalAestheticsDailyDashboardRefresh scheduled task at 04:00.
# Idempotent — safe to run multiple times in a day.
#
# Logs: data/refresh_dashboard_YYYYMMDD_HHMMSS.{log,err}
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$DataDir = Join-Path $ProjectDir "data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

$LogPath = Join-Path $DataDir "refresh_dashboard_$Stamp.log"
$ErrPath = Join-Path $DataDir "refresh_dashboard_$Stamp.err"
$LatestLog = Join-Path $DataDir "refresh_dashboard_latest.log"

function Get-PythonPath {
    $Candidates = @(
        "C:\Users\gisel\miniconda3\python.exe",
        "C:\Users\gisel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    )
    foreach ($p in $Candidates) {
        if (Test-Path $p) { return $p }
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    throw "Python interpreter not found"
}

$Python = Get-PythonPath
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Run-Step {
    param([string]$Label, [string]$ScriptRelative, [string[]]$ExtraArgs = @())
    $start = Get-Date
    Add-Content -Path $LogPath -Value "[$($start.ToString('s'))] === $Label ==="
    $args = @($ScriptRelative) + $ExtraArgs
    & $Python @args 2>>$ErrPath | Tee-Object -FilePath $LogPath -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Add-Content -Path $LogPath -Value "[$($start.ToString('s'))] FAILED — exit $LASTEXITCODE"
        throw "$Label failed (exit $LASTEXITCODE) — see $ErrPath"
    }
    $end = Get-Date
    $secs = [int]($end - $start).TotalSeconds
    Add-Content -Path $LogPath -Value "[$($end.ToString('s'))] OK (${secs}s)"
}

$RunStart = Get-Date
try {
    Add-Content -Path $LogPath -Value "Refresh start  ProjectDir=$ProjectDir  Python=$Python"

    # 1. Pull in new briefing HTML rows
    Run-Step "Step 1/5  sync_briefing_news_events" "scripts\sync_briefing_news_events.py" @("--days", "8")

    # 2. Promote rows whose URL was pushed to WeChat → status user_curated
    Run-Step "Step 2/5  consume_wechat_curated_news" "scripts\consume_wechat_curated_news.py"

    # 3. Rebuild SQLite db from xlsx + csv
    Run-Step "Step 3/5  build_data" "scripts\build_data.py"

    # 4. Regenerate the 11 v3 derived JS feeds
    $v3Builds = @(
        "companies", "tracks", "indications", "technology", "evidence",
        "product_tree", "products", "topic_deep", "cross_analysis",
        "mdr_ce_triage", "deep_dive", "l2_detail", "indication_detail",
        "company_matrix", "material_landscape"
    )
    $i = 0
    $total = $v3Builds.Count
    foreach ($s in $v3Builds) {
        $i++
        Run-Step "Step 4/5  v3 build ($i/$total) $s" "scripts\_v3_build_$s.py"
    }

    # 5. Stamp data-as-of.json so topbar reflects this refresh
    $manifestPath = Join-Path $ProjectDir "data\import_manifest.json"
    $asOfPath = Join-Path $ProjectDir "web\v3\data-as-of.json"
    $summary = @{
        as_of        = (Get-Date -Format "o")
        generated_by = "refresh_dashboard.ps1"
    }
    if (Test-Path $manifestPath) {
        try {
            $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
            if ($manifest.summary) {
                $summary.products      = $manifest.summary.products
                $summary.companies     = $manifest.summary.companies
                $summary.brands        = $manifest.summary.brands
                $summary.registrations = $manifest.summary.registration_evidence
            }
        }
        catch {
            Add-Content -Path $LogPath -Value "Warning: could not parse import_manifest.json — as-of will lack scope numbers."
        }
    }
    $summary | ConvertTo-Json -Depth 4 | Set-Content -Path $asOfPath -Encoding UTF8

    Add-Content -Path $LogPath -Value "[$(Get-Date -Format s)] === All steps OK ==="
    Add-Content -Path $LogPath -Value "data-as-of: $asOfPath"

    # ---- Build the toast summary --------------------------------------------
    $changes = New-Object System.Collections.ArrayList

    # Briefing sync — scanned files
    $syncStatePath = Join-Path $DataDir "briefing_news_sync_state.json"
    if (Test-Path $syncStatePath) {
        try {
            $ss = Get-Content $syncStatePath -Raw | ConvertFrom-Json
            $n = ($ss.scanned_files | Measure-Object).Count
            [void]$changes.Add("Briefing 扫描 $n 个 HTML")
        } catch {}
    }

    # WeChat curation
    $curJson = Join-Path $DataDir "audits\wechat_curation_apply_latest.json"
    if (Test-Path $curJson) {
        try {
            $cj = Get-Content $curJson -Raw | ConvertFrom-Json
            if ($cj.rows_promoted_to_user_curated -ne $null) {
                [void]$changes.Add("微信已审 $($cj.rows_promoted_to_user_curated) 条 → user_curated")
            }
        } catch {}
    }

    # Data scope from import_manifest
    if (Test-Path $manifestPath) {
        try {
            $mf = Get-Content $manifestPath -Raw | ConvertFrom-Json
            if ($mf.summary) {
                [void]$changes.Add("$($mf.summary.products) 产品 / $($mf.summary.companies) 公司 / $($mf.summary.registration_evidence) 注册证")
            }
        } catch {}
    }

    $totalSecs = [int]((Get-Date) - $RunStart).TotalSeconds
    $summary = "5/5 步 OK · ${totalSecs}s"

    & "$PSScriptRoot\notify_toast.ps1" `
        -TaskName "v3 仪表盘刷新" `
        -Status   "ok" `
        -Summary  $summary `
        -Changes  $changes.ToArray() `
        -LogPath  $LatestLog
}
catch {
    Add-Content -Path $LogPath -Value "[$(Get-Date -Format s)] ABORT: $($_.Exception.Message)"
    Copy-Item -Path $LogPath -Destination $LatestLog -Force -ErrorAction SilentlyContinue
    & "$PSScriptRoot\notify_toast.ps1" `
        -TaskName "v3 仪表盘刷新" `
        -Status   "fail" `
        -Summary  "中止：$($_.Exception.Message)" `
        -Changes  @("查看日志定位失败步骤") `
        -LogPath  $LatestLog
    throw
}
finally {
    Copy-Item -Path $LogPath -Destination $LatestLog -Force -ErrorAction SilentlyContinue
}
