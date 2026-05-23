[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [switch]$SkipPyInstaller,
    [switch]$SkipInstaller,
    [switch]$NoClean,
    [string]$Iscc
)

$ErrorActionPreference = 'Stop'

function Invoke-RepoCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Command
    )

    $commandLine = ($Command | ForEach-Object {
            if ($_ -match '\s') {
                '"' + $_.Replace('"', '\"') + '"'
            }
            else {
                $_
            }
        }) -join ' '
    Write-Host ">> $commandLine"

    $commandName = $Command[0]
    $arguments = @($Command | Select-Object -Skip 1)
    & $commandName @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $commandLine"
    }
}

Push-Location $RepoRoot
try {
    $command = @('poetry', 'run', 'python', 'scripts/build_windows_artifacts.py')
    if ($SkipPyInstaller) {
        $command += '--skip-pyinstaller'
    }
    if ($SkipInstaller) {
        $command += '--skip-installer'
    }
    if ($NoClean) {
        $command += '--no-clean'
    }
    if ($Iscc) {
        $command += @('--iscc', $Iscc)
    }

    Invoke-RepoCommand -Command $command
}
finally {
    Pop-Location
}
