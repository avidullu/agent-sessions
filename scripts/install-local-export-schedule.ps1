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
    [string]$Python = "",
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

if (-not $Python) {
    $launcher = Get-Command "py.exe" -ErrorAction SilentlyContinue
    if ($launcher) {
        foreach ($version in @("3.13", "3.12", "3.11")) {
            $candidate = (& $launcher.Source "-$version" -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                $Python = $candidate.Trim()
                break
            }
        }
    }
}
if (-not $Python) {
    $candidateCommand = Get-Command "python.exe" -ErrorAction SilentlyContinue
    if ($candidateCommand) {
        $candidateVersion = (& $candidateCommand.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if ($LASTEXITCODE -eq 0 -and ([Version]$candidateVersion -ge [Version]"3.11")) {
            $Python = $candidateCommand.Source
        }
    }
}
if (-not $Python) {
    throw "Python 3.11 or newer is required for the scheduled local export"
}
$selectedVersion = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if ($LASTEXITCODE -ne 0 -or ([Version]$selectedVersion -lt [Version]"3.11")) {
    throw "Python 3.11 or newer is required; selected interpreter is '$Python'"
}

$argList = @(
    "-NoProfile"
    "-ExecutionPolicy", "Bypass"
    "-File", "`"$ExportScript`""
    "-Python", "`"$Python`""
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
Write-Host "  python: $Python ($selectedVersion)"
Write-Host "  mode:   local-only (no git commit/push)"
Write-Host ""
Write-Host "Run once now:"
Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$ExportScript`" -LogDir `"$LogDir`" -WritePrimaryMarker$(if ($Pdf) { ' -Pdf' })"
