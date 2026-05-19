param(
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

$DataDir = Join-Path $ProjectDir "data"
New-Item -ItemType Directory -Path $DataDir -Force | Out-Null

$BuildLog = Join-Path $DataDir "dashboard_hidden_build.log"
$BuildErr = Join-Path $DataDir "dashboard_hidden_build.err.log"
$ServerLog = Join-Path $DataDir "dashboard_hidden_server.log"
$ServerErr = Join-Path $DataDir "dashboard_hidden_server.err.log"
$RunInfo = Join-Path $DataDir "dashboard_server_run.json"

function Get-PythonPath {
    $Bundled = "C:\Users\gisel\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $Bundled) {
        return $Bundled
    }
    $Python = (Get-Command python -ErrorAction SilentlyContinue)
    if ($Python) {
        return $Python.Source
    }
    $Py = (Get-Command py -ErrorAction SilentlyContinue)
    if ($Py) {
        return $Py.Source
    }
    throw "Python executable not found."
}

function Test-DashboardServer {
    try {
        $Response = Invoke-WebRequest -Uri "http://127.0.0.1:8790/" -UseBasicParsing -TimeoutSec 2
        return $Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500
    }
    catch {
        return $false
    }
}

$Python = Get-PythonPath

if (-not (Test-DashboardServer)) {
    $Build = Start-Process -FilePath $Python `
        -ArgumentList @("scripts\build_data.py") `
        -WorkingDirectory $ProjectDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $BuildLog `
        -RedirectStandardError $BuildErr `
        -Wait `
        -PassThru
    if ($Build.ExitCode -ne 0) {
        throw "Dashboard data build failed. See $BuildLog and $BuildErr"
    }

    $Server = Start-Process -FilePath $Python `
        -ArgumentList @("server.py", "--port", "8790") `
        -WorkingDirectory $ProjectDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $ServerLog `
        -RedirectStandardError $ServerErr `
        -PassThru

    [ordered]@{
        started_at = (Get-Date -Format o)
        pid = $Server.Id
        project_dir = $ProjectDir
        url = "http://127.0.0.1:8790/"
        stdout_log = $ServerLog
        stderr_log = $ServerErr
    } | ConvertTo-Json -Depth 4 | Set-Content -Path $RunInfo -Encoding UTF8

    Start-Sleep -Seconds 2
}

if (-not $NoOpen) {
    Start-Process "http://127.0.0.1:8790/"
}
