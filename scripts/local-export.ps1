<#
.SYNOPSIS
  Local-only session export for a primary archive host (no git operations).

.DESCRIPTION
  Unlike daily-export.ps1, this never runs git pull/commit/push. Use when this
  clone is your on-disk source of truth, or when remotes are a public product
  repo and personal catalogs must stay local.

  See docs/AUTOMATION.md.
#>
param(
    [switch]$Pdf,
    [switch]$NoStatus,
    [switch]$WritePrimaryMarker,
    [string[]]$Source = @(),
    [string]$Python = "",
    [string]$LogDir = ""
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

if (-not $Python) {
    if ($env:PYTHON) {
        $Python = $env:PYTHON
    } else {
        $Python = "python"
    }
}

if (-not $LogDir -and $env:AGENT_SESSIONS_LOG_DIR) {
    $LogDir = $env:AGENT_SESSIONS_LOG_DIR
}

$lockFile = Join-Path $RepoRoot ".local-export.lock"
$lockTimeoutSec = 300
if (Test-Path $lockFile) {
    $age = [int]((Get-Date) - (Get-Item $lockFile).LastWriteTime).TotalSeconds
    if ($age -lt $lockTimeoutSec) {
        throw "local-export: lock file exists (age=${age}s) — another export may be running"
    }
    Write-Host "local-export: stale lock file (age=${age}s), removing"
    Remove-Item -Force $lockFile
}
Set-Content -Path $lockFile -Value $PID
try {
    $exportArgs = @(".\tools\agent_archive.py", "export")
    if ($Source.Count -gt 0) {
        foreach ($item in $Source) {
            $exportArgs += @("--source", $item)
        }
    } else {
        $exportArgs += "--all"
    }
    if ($Pdf) {
        $exportArgs += "--pdf"
    }

    $run = {
        param($Python, $exportArgs, $NoStatus, $WritePrimaryMarker, $RepoRoot)
        Write-Host "local-export: $(Get-Date -Format o) starting in $RepoRoot"
        & $Python @exportArgs
        if (-not $NoStatus) {
            & $Python ".\tools\agent_archive.py" "status"
        }
        if ($WritePrimaryMarker) {
            $archiveDir = Join-Path $RepoRoot "archive"
            New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null
            $marker = Join-Path $archiveDir ".primary-host"
            @(
                "primary-host=local"
                "repo=$RepoRoot"
                "updated=$(Get-Date -Format o)"
            ) | Set-Content -Path $marker -Encoding utf8
            Write-Host "local-export: wrote archive/.primary-host"
        }
        Write-Host "local-export: done $(Get-Date -Format o)"
    }

    if ($LogDir) {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        $logFile = Join-Path $LogDir ("export-{0:yyyy-MM-dd}.log" -f (Get-Date))
        & $run $Python $exportArgs $NoStatus $WritePrimaryMarker $RepoRoot *>> $logFile
        Write-Host "local-export: wrote $logFile"
    } else {
        & $run $Python $exportArgs $NoStatus $WritePrimaryMarker $RepoRoot
    }
}
finally {
    Remove-Item -Force $lockFile -ErrorAction SilentlyContinue
}
