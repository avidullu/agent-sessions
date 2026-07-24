param(
    [switch]$Pdf,
    [switch]$NoPush,
    [string[]]$Source = @(),
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

git pull --ff-only

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

& $Python @exportArgs

$archiveStatus = git status --porcelain -- archive/
if ([string]::IsNullOrWhiteSpace($archiveStatus)) {
    Write-Host "No archive changes to commit."
    exit 0
}

git add -- archive/

$date = Get-Date -Format "yyyy-MM-dd"
git commit -m "archive: daily export $date"

if (-not $NoPush) {
    git push
}
