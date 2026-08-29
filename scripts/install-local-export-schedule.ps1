<#
.SYNOPSIS
  Install or remove a Windows Scheduled Task for scripts/local-export.ps1.

.DESCRIPTION
  Registers a daily user task that runs local-only export (no git). See docs/AUTOMATION.md.
#>
param(
    [int]$Hour = 7,
    [int]$Minute = 30,
    [switch]$Pdf,
    [string]$LogDir = "",
    [string]$TaskName = "Agent Sessions Local Export",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Hour -lt 0 -or $Hour -gt 23) { throw "Hour must be 0-23" }
if ($Minute -lt 0 -or $Minute -gt 59) { throw "Minute must be 0-59" }

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ExportScript = Join-Path $RepoRoot "scripts\local-export.ps1"
if (-not (Test-Path $ExportScript)) {
    throw "missing $ExportScript"
}

if ($Uninstall) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName' (if present)."
    return
}

if (-not $LogDir) {
    if ($env:AGENT_SESSIONS_LOG_DIR) {
        $LogDir = $env:AGENT_SESSIONS_LOG_DIR
    } else {
        $LogDir = Join-Path $env:LOCALAPPDATA "agent-sessions\logs"
    }
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$argList = @(
    "-NoProfile"
    "-ExecutionPolicy", "Bypass"
    "-File", "`"$ExportScript`""
    "-LogDir", "`"$LogDir`""
    "-WritePrimaryMarker"
)
if ($Pdf) {
    $argList += "-Pdf"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($argList -join " ")
$trigger = New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $Hour -Minute $Minute -Second 0)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Description "Agent Sessions managed local-export routine schema v1" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Force | Out-Null

Write-Host "Installed daily local-export task '$TaskName' at ${Hour}:$('{0:D2}' -f $Minute)."
Write-Host "  script: $ExportScript"
Write-Host "  logs:   $LogDir"
Write-Host "  mode:   local-only (no git commit/push)"
Write-Host ""
Write-Host "Run once now:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$ExportScript`" -LogDir `"$LogDir`" -WritePrimaryMarker$(if ($Pdf) { ' -Pdf' })"
