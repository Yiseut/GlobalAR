# notify_toast.ps1
# -----------------------------------------------------------------------------
# Unified desktop toast notification for nightly schtasks. Uses BurntToast
# (native Win10/11 toast) — appears bottom-right, auto-dismisses, does not
# steal focus or block the foreground.
#
# Usage from another script:
#   & "$PSScriptRoot\notify_toast.ps1" `
#       -TaskName "v3 仪表盘刷新" `
#       -Status   "ok" `
#       -Summary  "5/5 步 OK · 50s" `
#       -Changes  @("briefing 新增 12 条", "推微信 8 条已标 user_curated", "975 产品 / 359 公司") `
#       -LogPath  "E:\...\refresh_dashboard_latest.log"
#
# If BurntToast is missing, falls back to a balloon-tip via WinForms NotifyIcon
# (still non-intrusive) so the chain never silently dies.
# -----------------------------------------------------------------------------
param(
    [Parameter(Mandatory=$true)][string]$TaskName,
    [Parameter(Mandatory=$true)][ValidateSet('ok','warn','fail')][string]$Status,
    [string]$Summary = "",
    [string[]]$Changes = @(),
    [string]$LogPath = ""
)

$ErrorActionPreference = 'Continue'

# Title prefix + emoji per status
$prefix = switch ($Status) {
    'ok'   { '✅' }
    'warn' { '⚠️' }
    'fail' { '❌' }
}

$title = "$prefix  $TaskName"

# Build body: summary line + up to 3 change lines.
$bodyLines = @()
if ($Summary) { $bodyLines += $Summary }
if ($Changes -and $Changes.Count -gt 0) {
    $shown = $Changes | Select-Object -First 4
    foreach ($c in $shown) { $bodyLines += "· $c" }
    if ($Changes.Count -gt 4) {
        $bodyLines += "· (+ $($Changes.Count - 4) more — see log)"
    }
}
$body = ($bodyLines -join "`n")
if (-not $body) { $body = "(no summary supplied)" }

# Try BurntToast first
$burnt = Get-Module -ListAvailable BurntToast | Select-Object -First 1
if ($burnt) {
    try {
        Import-Module BurntToast -ErrorAction Stop
        $logoPath = 'E:\shared\code\briefing_v6\output\aestrat_logo.png'
        $args = @{
            Text = @($title, $body)
        }
        if (Test-Path $logoPath) { $args['AppLogo'] = $logoPath }
        # Add a "查看日志" button that opens the log when clicked.
        if ($LogPath -and (Test-Path $LogPath)) {
            $btn = New-BTButton -Content "查看日志" -Arguments $LogPath
            $args['Button'] = $btn
        }
        # Long-form toast for fail; default for ok/warn.
        if ($Status -eq 'fail') {
            $args['Sound'] = 'Alarm2'
        }
        New-BurntToastNotification @args | Out-Null
        return
    }
    catch {
        Write-Host "BurntToast failed: $($_.Exception.Message). Falling back to balloon."
    }
}

# Fallback — Windows balloon tip (System.Windows.Forms NotifyIcon)
try {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $icon = New-Object System.Windows.Forms.NotifyIcon
    $icon.Icon = [System.Drawing.SystemIcons]::Information
    if ($Status -eq 'fail') { $icon.Icon = [System.Drawing.SystemIcons]::Error }
    elseif ($Status -eq 'warn') { $icon.Icon = [System.Drawing.SystemIcons]::Warning }
    $icon.BalloonTipTitle = $title
    $icon.BalloonTipText = $body
    $icon.Visible = $true
    $icon.ShowBalloonTip(8000)
    Start-Sleep -Seconds 9
    $icon.Dispose()
}
catch {
    Write-Host "Notification fallback failed: $($_.Exception.Message)"
}
