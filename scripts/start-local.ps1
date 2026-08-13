$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backendRoot = Join-Path $projectRoot "backend"
$frontendRoot = Join-Path $projectRoot "frontend"
$runtimeRoot = Join-Path $projectRoot ".runtime"
$logRoot = Join-Path $runtimeRoot "logs"
$statePath = Join-Path $runtimeRoot "local-processes.json"
$pythonPath = Join-Path $backendRoot ".venv\Scripts\python.exe"
$vitePath = Join-Path $frontendRoot "node_modules\vite\bin\vite.js"

# Some hosts inject both Path and PATH into this process. Windows treats them as
# one variable, but Start-Process rejects the duplicate dictionary keys.
$processPath = [System.Environment]::GetEnvironmentVariable("Path", "Process")
if (-not $processPath) {
    $processPath = [System.Environment]::GetEnvironmentVariable("PATH", "Process")
}
[System.Environment]::SetEnvironmentVariable("PATH", $null, "Process")
if ($processPath) {
    [System.Environment]::SetEnvironmentVariable("Path", $processPath, "Process")
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null

function Show-Message([string]$message, [int]$seconds = 8) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $null = $shell.Popup($message, $seconds, "AI Content Operations", 64)
    } catch {
        Write-Output $message
    }
}

function Test-Port([int]$port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    return $null -ne $listener
}

function Start-ServiceProcess(
    [string]$name,
    [string]$filePath,
    [string[]]$arguments,
    [string]$workingDirectory
) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutPath = Join-Path $logRoot "$name-$timestamp.log"
    $stderrPath = Join-Path $logRoot "$name-$timestamp.error.log"
    $process = Start-Process `
        -FilePath $filePath `
        -ArgumentList $arguments `
        -WorkingDirectory $workingDirectory `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
    return [ordered]@{
        pid = $process.Id
        start_time_ticks = $process.StartTime.ToUniversalTime().Ticks
    }
}

if (-not (Test-Path -LiteralPath $pythonPath)) {
    Show-Message "Backend virtual environment is missing: $pythonPath"
    exit 1
}
if (-not (Test-Path -LiteralPath $vitePath)) {
    Show-Message "Frontend dependencies are missing. Run pnpm install in the frontend directory."
    exit 1
}

$nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
if ($null -eq $nodeCommand) {
    Show-Message "Node.js was not found. Install Node.js 20 or later."
    exit 1
}

$previousState = $null
if (Test-Path -LiteralPath $statePath) {
    try {
        $previousState = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    } catch {
        $previousState = $null
    }
}

function Get-LiveState($entry) {
    if ($null -eq $entry -or $null -eq $entry.pid) {
        return $null
    }
    $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        return $null
    }
    if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$entry.start_time_ticks) {
        return $null
    }
    return [ordered]@{
        pid = $process.Id
        start_time_ticks = $process.StartTime.ToUniversalTime().Ticks
    }
}

$state = [ordered]@{
    project_root = $projectRoot
    started_at = (Get-Date).ToUniversalTime().ToString("O")
    services = [ordered]@{
        api = Get-LiveState $previousState.services.api
        worker = Get-LiveState $previousState.services.worker
        frontend = Get-LiveState $previousState.services.frontend
    }
}

$notes = [System.Collections.Generic.List[string]]::new()

if ($null -eq $state.services.api) {
    if (Test-Port 8000) {
        $notes.Add("Port 8000 is already in use. API was not started again.")
    } else {
        $state.services.api = Start-ServiceProcess "api" $pythonPath @("-m", "content_ops.main") $backendRoot
    }
}

if ($null -eq $state.services.worker) {
    $state.services.worker = Start-ServiceProcess "worker" $pythonPath @("-m", "content_ops.worker") $backendRoot
}

if ($null -eq $state.services.frontend) {
    if (Test-Port 5173) {
        $notes.Add("Port 5173 is already in use. Frontend was not started again.")
    } else {
        $state.services.frontend = Start-ServiceProcess "frontend" $nodeCommand.Source @($vitePath, "--host", "127.0.0.1", "--port", "5173") $frontendRoot
    }
}

$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding UTF8

$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline -and -not (Test-Port 5173)) {
    Start-Sleep -Milliseconds 300
}

if (Test-Port 5173) {
    Start-Process "http://127.0.0.1:5173"
    if ($notes.Count -gt 0) {
        Show-Message ("The platform is open.`n" + ($notes -join "`n"))
    }
} else {
    Show-Message "Frontend did not start on port 5173. Check logs: $logRoot"
    exit 1
}
