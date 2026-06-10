param(
    [int]$MaxBatches = 400,
    [int]$StopAfterStalledBatches = 10,
    [int]$MaxWaitMinutes = 360  # hard cap so a stuck batch can't pin the task forever
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
$StartScript = Join-Path $PSScriptRoot "start_continuous_verification.ps1"
$Notifier = Join-Path $PSScriptRoot "notify_toast.ps1"
$DbPath = Join-Path $ProjectDir "data\global_aesthetics.db"
$RunInfo = Join-Path $ProjectDir "data\current_verification_run.json"

function Get-Counts {
    if (-not (Test-Path $DbPath)) { return $null }
    $sqlite = "C:\Users\gisel\miniconda3\python.exe"
    if (-not (Test-Path $sqlite)) { $sqlite = (Get-Command python).Source }
    $py = @"
import sqlite3, json
c = sqlite3.connect(r'$DbPath', timeout=60)
def n(tbl):
    try: return c.execute('SELECT COUNT(*) FROM ' + tbl).fetchone()[0]
    except: return None
print(json.dumps({
    'briefing_candidates'    : n('briefing_update_candidates'),
    'briefing_verified'      : n('briefing_verified_update_events'),
    'verification_queue'     : n('verification_queue'),
    'evidence_staging'       : n('evidence_staging'),
    'registration_evidence'  : n('registration_evidence'),
    'official_indication'    : n('official_indication_evidence'),
    'product_master'         : n('product_master'),
    'company_master'         : n('company_master'),
}))
"@
    $out = & $sqlite -c $py 2>$null
    if ($LASTEXITCODE -eq 0 -and $out) { return ($out | ConvertFrom-Json) }
    return $null
}

# 1. Snapshot before
$before = Get-Counts
$startTime = Get-Date

try {
    # 2. Spawn the actual batch (writes data/current_verification_run.json with PID)
    & $StartScript -MaxBatches $MaxBatches -StopAfterStalledBatches $StopAfterStalledBatches | Out-Null

    # 3. Pick up the PID and wait for it to exit (or hit MaxWaitMinutes)
    Start-Sleep -Seconds 3
    if (-not (Test-Path $RunInfo)) {
        throw "current_verification_run.json missing — start script may have failed."
    }
    $info = Get-Content $RunInfo -Raw | ConvertFrom-Json
    $pid_ = [int]$info.pid

    $deadline = $startTime.AddMinutes($MaxWaitMinutes)
    $exited = $false
    while ((Get-Date) -lt $deadline) {
        $proc = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if (-not $proc) { $exited = $true; break }
        Start-Sleep -Seconds 30
    }

    $elapsed = [int]((Get-Date) - $startTime).TotalMinutes
    $status = if ($exited) { 'ok' } else { 'warn' }

    # 4. Snapshot after and diff
    $after = Get-Counts
    $changes = New-Object System.Collections.ArrayList
    if ($before -and $after) {
        foreach ($k in @('briefing_verified','registration_evidence','official_indication','verification_queue','evidence_staging','product_master')) {
            $b = [int]$before.$k
            $a = [int]$after.$k
            $delta = $a - $b
            if ($delta -ne 0) {
                $sign = if ($delta -gt 0) { '+' } else { '' }
                [void]$changes.Add("$k : $b → $a ($sign$delta)")
            }
        }
        if ($changes.Count -eq 0) {
            [void]$changes.Add("无字段计数变化（核查未带来新条目）")
        }
    }

    $summary = if ($exited) { "完成 · ${elapsed} 分钟" } else { "超过 ${MaxWaitMinutes} 分钟仍在跑，提前通知" }

    & $Notifier `
        -TaskName "晚间深度核查 (continuous_verification)" `
        -Status   $status `
        -Summary  $summary `
        -Changes  $changes.ToArray() `
        -LogPath  ($info.stdout_log)

    exit 0
}
catch {
    & $Notifier `
        -TaskName "晚间深度核查 (continuous_verification)" `
        -Status   "fail" `
        -Summary  "中止：$($_.Exception.Message)" `
        -Changes  @("查看 stderr 日志") `
        -LogPath  ((Test-Path $RunInfo) ? ((Get-Content $RunInfo -Raw | ConvertFrom-Json).stderr_log) : "")
    throw
}
