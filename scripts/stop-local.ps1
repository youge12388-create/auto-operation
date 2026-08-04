$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $projectRoot ".runtime"
$statePath = Join-Path $runtimeRoot "local-processes.json"

function Show-Message([string]$message, [int]$seconds = 6) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $null = $shell.Popup($message, $seconds, "AI Content Operations", 64)
    } catch {
        Write-Output $message
    }
}

if (-not (Test-Path -LiteralPath $statePath)) {
    Show-Message "No service state created by the start shortcut was found."
    exit 0
}

try {
    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Show-Message "The service state could not be read. No process was stopped."
    exit 1
}

$stopped = [System.Collections.Generic.List[string]]::new()
$skipped = [System.Collections.Generic.List[string]]::new()

foreach ($name in @("frontend", "worker", "api")) {
    $entry = $state.services.$name
    if ($null -eq $entry -or $null -eq $entry.pid) {
        continue
    }

    $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        continue
    }

    if ($process.StartTime.ToUniversalTime().Ticks -ne [long]$entry.start_time_ticks) {
        $skipped.Add("$name (PID was reused by another process)")
        continue
    }

    Stop-Process -Id $process.Id -Force
    $stopped.Add($name)
}

Remove-Item -LiteralPath $statePath -Force

if ($skipped.Count -gt 0) {
    Show-Message ("Stopped: " + ($stopped -join ", ") + "`nSkipped: " + ($skipped -join ", "))
} elseif ($stopped.Count -gt 0) {
    Show-Message ("Platform stopped: " + ($stopped -join ", "))
} else {
    Show-Message "Services are already stopped."
}
