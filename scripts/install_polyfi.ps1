[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$AppDataRoot = (Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Inspyre-Softworks\PolyFi-Ranked'),
    [string]$InterfaceName,
    [switch]$Dev,
    [switch]$NoInteraction,
    [switch]$SkipPackageInstall,
    [switch]$InstallAll,
    [switch]$InstallWifiTasks,
    [switch]$InstallStartMenu,
    [switch]$InstallStartup
)

$ErrorActionPreference = 'Stop'

function Get-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $item = New-Item -ItemType Directory -Path $PathValue -Force
    return $item.FullName.TrimEnd('\')
}

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

function Invoke-PolyFiCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    if ($Dev) {
        Invoke-RepoCommand -Command (@('poetry', 'run', 'python', '-m', 'wifi_pref_manager.app') + $Arguments)
    }
    else {
        Invoke-RepoCommand -Command (@('python', '-m', 'wifi_pref_manager.app') + $Arguments)
    }
}

function Resolve-YesNoChoice {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt,
        [Parameter(Mandatory = $true)]
        [bool]$Default,
        [Parameter(Mandatory = $true)]
        [bool]$WasSpecified,
        [Parameter(Mandatory = $true)]
        [bool]$SpecifiedValue
    )

    if ($WasSpecified) {
        return $SpecifiedValue
    }

    if ($NoInteraction) {
        return $Default
    }

    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $response = Read-Host "$Prompt $suffix"
        if ([string]::IsNullOrWhiteSpace($response)) {
            return $Default
        }
        $response = $response.Trim()

        switch -Regex ($response) {
            '^(y|yes)$' { return $true }
            '^(n|no)$' { return $false }
            default { Write-Host 'Please answer yes or no.' }
        }
    }
}

function Resolve-PathChoice {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt,
        [Parameter(Mandatory = $true)]
        [string]$Default,
        [Parameter(Mandatory = $true)]
        [bool]$WasSpecified,
        [Parameter(Mandatory = $true)]
        [string]$SpecifiedValue
    )

    if ($WasSpecified) {
        return $SpecifiedValue
    }

    if ($NoInteraction) {
        return $Default
    }

    $response = Read-Host "$Prompt [$Default]"
    if ([string]::IsNullOrWhiteSpace($response)) {
        return $Default
    }

    return $response.Trim()
}

function Update-PolyFiEnvironmentBroadcast {
    if (-not ([System.Management.Automation.PSTypeName]'PolyFiEnvironmentNotifier').Type) {
        Add-Type @'
using System;
using System.Runtime.InteropServices;

public static class PolyFiEnvironmentNotifier
{
    private const int HWND_BROADCAST = 0xffff;
    private const int WM_SETTINGCHANGE = 0x001A;
    private const int SMTO_ABORTIFHUNG = 0x0002;

    [DllImport("user32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageTimeout(
        IntPtr hWnd,
        uint Msg,
        IntPtr wParam,
        string lParam,
        uint fuFlags,
        uint uTimeout,
        out IntPtr lpdwResult);

    public static void NotifyEnvironmentChanged()
    {
        IntPtr result;
        SendMessageTimeout(
            new IntPtr(HWND_BROADCAST),
            WM_SETTINGCHANGE,
            IntPtr.Zero,
            "Environment",
            SMTO_ABORTIFHUNG,
            5000,
            out result);
    }
}
'@
    }

    [PolyFiEnvironmentNotifier]::NotifyEnvironmentChanged()
}

Push-Location $RepoRoot
try {
    $appDataRootWasSpecified = $PSBoundParameters.ContainsKey('AppDataRoot')
    $skipPackageInstallWasSpecified = $PSBoundParameters.ContainsKey('SkipPackageInstall')
    $installWifiTasksWasSpecified = $PSBoundParameters.ContainsKey('InstallWifiTasks')
    $installStartMenuWasSpecified = $PSBoundParameters.ContainsKey('InstallStartMenu')
    $installStartupWasSpecified = $PSBoundParameters.ContainsKey('InstallStartup')

    if ($InstallAll) {
        $InstallWifiTasks = $true
        $InstallStartMenu = $true
        $InstallStartup = $true
    }

    $defaultAppDataRoot = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Inspyre-Softworks\PolyFi-Ranked'
    $selectedAppDataRoot = Get-NormalizedPath -PathValue (
        Resolve-PathChoice `
            -Prompt 'PolyFi app-data root' `
            -Default $defaultAppDataRoot `
            -WasSpecified $appDataRootWasSpecified `
            -SpecifiedValue $AppDataRoot
    )
    $configPath = Join-Path $selectedAppDataRoot 'config.toml'

    $shouldInstallPackage = Resolve-YesNoChoice `
        -Prompt 'Install the PolyFi package now?' `
        -Default $true `
        -WasSpecified $skipPackageInstallWasSpecified `
        -SpecifiedValue (-not $SkipPackageInstall)

    if (-not $InstallAll) {
        $InstallStartMenu = Resolve-YesNoChoice `
            -Prompt 'Install the Start Menu shortcut?' `
            -Default $true `
            -WasSpecified $installStartMenuWasSpecified `
            -SpecifiedValue $InstallStartMenu

        $InstallStartup = Resolve-YesNoChoice `
            -Prompt 'Install the Startup Programs shortcut?' `
            -Default $false `
            -WasSpecified $installStartupWasSpecified `
            -SpecifiedValue $InstallStartup

        $InstallWifiTasks = Resolve-YesNoChoice `
            -Prompt 'Install the Wi-Fi helper scheduled tasks?' `
            -Default $false `
            -WasSpecified $installWifiTasksWasSpecified `
            -SpecifiedValue $InstallWifiTasks
    }
    else {
        $InstallStartMenu = $true
        $InstallStartup = $true
        $InstallWifiTasks = $true
    }

    Write-Host "Repo root: $RepoRoot"
    Write-Host "Default PolyFi app-data root: $(Get-NormalizedPath -PathValue $defaultAppDataRoot)"
    Write-Host "Selected PolyFi app-data root: $selectedAppDataRoot"
    Write-Host "PolyFi config path: $configPath"
    if ($Dev) {
        Write-Host 'Install mode: Poetry dev environment'
    }
    else {
        Write-Host 'Install mode: pip package install'
    }
    Write-Host "Install package now: $shouldInstallPackage"
    Write-Host "Install Start Menu shortcut: $InstallStartMenu"
    Write-Host "Install Startup shortcut: $InstallStartup"
    Write-Host "Install Wi-Fi helper tasks: $InstallWifiTasks"

    if ($selectedAppDataRoot -ieq $defaultAppDataRoot) {
        [Environment]::SetEnvironmentVariable('POLYFI_APPDATA_ROOT', $null, 'User')
        Remove-Item Env:POLYFI_APPDATA_ROOT -ErrorAction SilentlyContinue
        Write-Host 'Cleared persistent POLYFI_APPDATA_ROOT override; PolyFi will use the default platform app-data path.'
    }
    else {
        [Environment]::SetEnvironmentVariable('POLYFI_APPDATA_ROOT', $selectedAppDataRoot, 'User')
        $env:POLYFI_APPDATA_ROOT = $selectedAppDataRoot
        Write-Host "Set persistent POLYFI_APPDATA_ROOT override to: $selectedAppDataRoot"
    }
    Update-PolyFiEnvironmentBroadcast

    if ($shouldInstallPackage) {
        if ($Dev) {
            Invoke-RepoCommand -Command @('poetry', 'install', '--with', 'dev', '--no-interaction')
        }
        else {
            Invoke-RepoCommand -Command @('python', '-m', 'pip', 'install', '.')
        }
    }

    if (-not (Test-Path -LiteralPath $configPath)) {
        Invoke-PolyFiCommand -Arguments @(
            'config', 'init',
            '--config', $configPath
        )
    }
    else {
        Write-Host "Using existing config file: $configPath"
    }

    if ($InstallWifiTasks) {
        $wifiTaskCommand = @('windows', 'wifi-tasks', 'install')
        if ($InterfaceName) {
            $wifiTaskCommand += @('--interface', $InterfaceName)
        }
        Invoke-PolyFiCommand -Arguments $wifiTaskCommand
    }

    if ($InstallStartMenu) {
        Invoke-PolyFiCommand -Arguments @(
            'windows', 'start-menu', 'install',
            '--config', $configPath,
            '--force'
        )
    }

    if ($InstallStartup) {
        Invoke-PolyFiCommand -Arguments @(
            'windows', 'startup', 'install',
            '--config', $configPath,
            '--force'
        )
    }

    Write-Host ''
    Write-Host 'PolyFi installation workflow completed.'
}
finally {
    Pop-Location
}
