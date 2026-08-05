[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^3\.(11|13)$')]
    [string]$PythonVersion
)

$ErrorActionPreference = 'Stop'

function Find-CiPython {
    param([Parameter(Mandatory = $true)][string]$Version)

    if ($env:RUNNER_TOOL_CACHE) {
        $pythonRoot = Join-Path $env:RUNNER_TOOL_CACHE 'Python'
        if (Test-Path -LiteralPath $pythonRoot) {
            $installations = Get-ChildItem -LiteralPath $pythonRoot -Directory |
                Where-Object { $_.Name -like "$Version.*" } |
                Sort-Object { [version]$_.Name } -Descending
            foreach ($installation in $installations) {
                $candidate = Join-Path $installation.FullName 'x64\python.exe'
                if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                    return $candidate
                }
            }
        }
    }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $candidate = (& $launcher.Source "-$Version" -c 'import sys; print(sys.executable)').Trim()
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }

    throw "Python $Version is not installed in RUNNER_TOOL_CACHE and is unavailable through py.exe."
}

$basePython = Find-CiPython -Version $PythonVersion
$actualVersion = (& $basePython -c 'import sys; print(sys.version_info.major, sys.version_info.minor, sep=chr(46))').Trim()
if ($LASTEXITCODE -ne 0 -or $actualVersion -ne $PythonVersion) {
    throw "Selected interpreter '$basePython' is Python $actualVersion, expected $PythonVersion."
}

$venvRoot = Join-Path $env:RUNNER_TEMP 'ci-python-venv'
& $basePython -m venv --clear $venvRoot
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create the CI virtual environment with '$basePython'."
}

$venvPython = Join-Path $venvRoot 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) {
    throw "The CI virtual environment did not create '$venvPython'."
}

$actualPrefix = (& $venvPython -c 'import os, sys; print(os.path.realpath(sys.prefix))').Trim()
$expectedPrefix = [IO.Path]::GetFullPath($venvRoot).TrimEnd('\')
if (-not [string]::Equals($actualPrefix.TrimEnd('\'), $expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Virtual environment prefix mismatch: $actualPrefix != $expectedPrefix"
}

Add-Content -LiteralPath $env:GITHUB_ENV -Value "CI_PYTHON=$venvPython"
Add-Content -LiteralPath $env:GITHUB_ENV -Value "VIRTUAL_ENV=$venvRoot"
Add-Content -LiteralPath $env:GITHUB_PATH -Value (Split-Path -Parent $venvPython)
Write-Output "isolated Python $actualVersion`: $venvPython"
