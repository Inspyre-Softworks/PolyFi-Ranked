[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$AppDataRoot,
    [string]$TaskName = 'PolyFi Ranked',
    [switch]$Dev,
    [switch]$NoInteraction,
    [switch]$SkipPackageUninstall,
    [switch]$UninstallAll,
    [switch]$RemoveWifiTasks,
    [switch]$RemoveStartMenu,
    [switch]$RemoveStartup,
    [switch]$RemoveLogonTask,
    [switch]$PurgeData,
    [switch]$ClearAppDataOverride
)

$ErrorActionPreference = 'Stop'

function Get-NormalizedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $trimmed = $PathValue.Trim()
    if ([string]::IsNullOrWhiteSpace($trimmed)) {
        throw 'Path cannot be blank.'
    }

    if ([System.IO.Path]::IsPathRooted($trimmed)) {
        $fullPath = [System.IO.Path]::GetFullPath($trimmed)
    }
    else {
        $fullPath = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $trimmed))
    }

    return $fullPath.TrimEnd('\')
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

function Invoke-PolyFiPythonCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    $repoSrc = Join-Path $RepoRoot 'src'

    try {
        if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
            $env:PYTHONPATH = $repoSrc
        }
        else {
            $env:PYTHONPATH = "$repoSrc$([System.IO.Path]::PathSeparator)$previousPythonPath"
        }

        if ($Dev) {
            Invoke-RepoCommand -Command (@('poetry', 'run', 'python') + $Arguments)
        }
        else {
            Invoke-RepoCommand -Command (@('python') + $Arguments)
        }
    }
    finally {
        if ($null -eq $previousPythonPath) {
            Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        }
        else {
            $env:PYTHONPATH = $previousPythonPath
        }
    }
}

function Invoke-PolyFiCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Invoke-PolyFiPythonCommand -Arguments (@('-m', 'wifi_pref_manager.app') + $Arguments)
}

function Invoke-PolyFiPurgeData {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ConfigPath
    )

    $scriptContent = @'
from __future__ import annotations

import sys

sys.path.insert(0, sys.argv[1])

from wifi_pref_manager.app import Application

config_path = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
app = Application()
for message in app.purge_application_data(config_path):
    print(message)
'@

    $tempScript = New-TemporaryFile
    try {
        Set-Content -LiteralPath $tempScript.FullName -Value $scriptContent -Encoding UTF8
        Invoke-PolyFiPythonCommand -Arguments @(
            $tempScript.FullName,
            (Join-Path $RepoRoot 'src'),
            $ConfigPath
        )
    }
    finally {
        Remove-Item -LiteralPath $tempScript.FullName -Force -ErrorAction SilentlyContinue
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

        switch -Regex ($response.Trim()) {
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
        [AllowEmptyString()]
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

function Set-PolyFiProcessAppDataRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SelectedRoot,
        [Parameter(Mandatory = $true)]
        [string]$PlatformDefaultRoot
    )

    if ($SelectedRoot -ieq $PlatformDefaultRoot) {
        Remove-Item Env:POLYFI_APPDATA_ROOT -ErrorAction SilentlyContinue
    }
    else {
        $env:POLYFI_APPDATA_ROOT = $SelectedRoot
    }
}

function Remove-ScheduledTaskIfPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskNameValue
    )

    $command = @('schtasks', '/Delete', '/F', '/TN', $TaskNameValue)
    $commandLine = ($command | ForEach-Object {
            if ($_ -match '\s') {
                '"' + $_.Replace('"', '\"') + '"'
            }
            else {
                $_
            }
        }) -join ' '
    Write-Host ">> $commandLine"

    $output = & schtasks /Delete /F /TN $TaskNameValue 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
        $output | ForEach-Object { Write-Host $_ }
    }

    if ($exitCode -eq 0) {
        return
    }

    $details = (($output | Out-String).Trim())
    $normalized = $details.ToLowerInvariant()
    if ($normalized.Contains('cannot find') -or $normalized.Contains('does not exist')) {
        Write-Host "No scheduled task found: $TaskNameValue"
        return
    }

    throw "Could not remove scheduled task ${TaskNameValue}: $details"
}

Push-Location $RepoRoot
try {
    $appDataRootWasSpecified = $PSBoundParameters.ContainsKey('AppDataRoot')
    $skipPackageUninstallWasSpecified = $PSBoundParameters.ContainsKey('SkipPackageUninstall')
    $removeWifiTasksWasSpecified = $PSBoundParameters.ContainsKey('RemoveWifiTasks')
    $removeStartMenuWasSpecified = $PSBoundParameters.ContainsKey('RemoveStartMenu')
    $removeStartupWasSpecified = $PSBoundParameters.ContainsKey('RemoveStartup')
    $removeLogonTaskWasSpecified = $PSBoundParameters.ContainsKey('RemoveLogonTask')
    $purgeDataWasSpecified = $PSBoundParameters.ContainsKey('PurgeData')
    $clearAppDataOverrideWasSpecified = $PSBoundParameters.ContainsKey('ClearAppDataOverride')

    if ($UninstallAll) {
        $RemoveWifiTasks = $true
        $RemoveStartMenu = $true
        $RemoveStartup = $true
        $RemoveLogonTask = $true
    }

    $platformDefaultAppDataRoot = Get-NormalizedPath -PathValue (
        Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Inspyre-Softworks\PolyFi-Ranked'
    )
    $currentPersistentOverride = [Environment]::GetEnvironmentVariable('POLYFI_APPDATA_ROOT', 'User')
    $currentPersistentOverride = if ([string]::IsNullOrWhiteSpace($currentPersistentOverride)) {
        $null
    }
    else {
        Get-NormalizedPath -PathValue $currentPersistentOverride
    }
    $defaultSelectedRoot = if ($currentPersistentOverride) {
        $currentPersistentOverride
    }
    else {
        $platformDefaultAppDataRoot
    }
    $selectedAppDataRoot = Get-NormalizedPath -PathValue (
        Resolve-PathChoice `
            -Prompt 'PolyFi app-data root' `
            -Default $defaultSelectedRoot `
            -WasSpecified $appDataRootWasSpecified `
            -SpecifiedValue $AppDataRoot
    )
    $configPath = Join-Path $selectedAppDataRoot 'config.toml'

    $packagePrompt = if ($Dev) {
        'Uninstall PolyFi from the Poetry environment now?'
    }
    else {
        'Uninstall the PolyFi package now?'
    }
    $shouldUninstallPackage = Resolve-YesNoChoice `
        -Prompt $packagePrompt `
        -Default $true `
        -WasSpecified $skipPackageUninstallWasSpecified `
        -SpecifiedValue (-not $SkipPackageUninstall)

    if (-not $UninstallAll) {
        $RemoveStartMenu = Resolve-YesNoChoice `
            -Prompt 'Remove the Start Menu shortcut?' `
            -Default $true `
            -WasSpecified $removeStartMenuWasSpecified `
            -SpecifiedValue $RemoveStartMenu

        $RemoveStartup = Resolve-YesNoChoice `
            -Prompt 'Remove the Startup Programs shortcut?' `
            -Default $true `
            -WasSpecified $removeStartupWasSpecified `
            -SpecifiedValue $RemoveStartup

        $RemoveWifiTasks = Resolve-YesNoChoice `
            -Prompt 'Remove the Wi-Fi helper scheduled tasks?' `
            -Default $true `
            -WasSpecified $removeWifiTasksWasSpecified `
            -SpecifiedValue $RemoveWifiTasks

        $RemoveLogonTask = Resolve-YesNoChoice `
            -Prompt 'Remove the scheduled logon task?' `
            -Default $true `
            -WasSpecified $removeLogonTaskWasSpecified `
            -SpecifiedValue $RemoveLogonTask
    }
    else {
        $RemoveStartMenu = $true
        $RemoveStartup = $true
        $RemoveWifiTasks = $true
        $RemoveLogonTask = $true
    }

    $PurgeData = Resolve-YesNoChoice `
        -Prompt 'Delete PolyFi settings, logs, and app-data directories?' `
        -Default $false `
        -WasSpecified $purgeDataWasSpecified `
        -SpecifiedValue $PurgeData

    $clearOverrideDefault = $null -ne $currentPersistentOverride
    $ClearAppDataOverride = Resolve-YesNoChoice `
        -Prompt 'Clear the persistent POLYFI_APPDATA_ROOT override?' `
        -Default $clearOverrideDefault `
        -WasSpecified $clearAppDataOverrideWasSpecified `
        -SpecifiedValue $ClearAppDataOverride

    if ($shouldUninstallPackage -or $PurgeData) {
        if (-not $RemoveStartMenu) {
            Write-Host 'Enabling Start Menu shortcut removal so PolyFi does not leave a broken launcher behind.'
            $RemoveStartMenu = $true
        }
        if (-not $RemoveStartup) {
            Write-Host 'Enabling Startup Programs shortcut removal so PolyFi does not leave a broken launcher behind.'
            $RemoveStartup = $true
        }
        if (-not $RemoveLogonTask) {
            Write-Host 'Enabling scheduled logon task removal so PolyFi does not leave a broken launcher behind.'
            $RemoveLogonTask = $true
        }
    }

    Write-Host "Repo root: $RepoRoot"
    Write-Host "Platform-default PolyFi app-data root: $platformDefaultAppDataRoot"
    Write-Host "Current persistent POLYFI_APPDATA_ROOT: $(if ($currentPersistentOverride) { $currentPersistentOverride } else { '(not set)' })"
    Write-Host "Selected PolyFi app-data root: $selectedAppDataRoot"
    Write-Host "PolyFi config path: $configPath"
    if ($Dev) {
        Write-Host 'Uninstall mode: Poetry dev environment'
    }
    else {
        Write-Host 'Uninstall mode: pip package install'
    }
    Write-Host "Uninstall package now: $shouldUninstallPackage"
    Write-Host "Remove Start Menu shortcut: $RemoveStartMenu"
    Write-Host "Remove Startup shortcut: $RemoveStartup"
    Write-Host "Remove Wi-Fi helper tasks: $RemoveWifiTasks"
    Write-Host "Remove scheduled logon task: $RemoveLogonTask"
    Write-Host "Purge settings/log/data files: $PurgeData"
    Write-Host "Clear POLYFI_APPDATA_ROOT override: $ClearAppDataOverride"

    Set-PolyFiProcessAppDataRoot -SelectedRoot $selectedAppDataRoot -PlatformDefaultRoot $platformDefaultAppDataRoot

    $errors = [System.Collections.Generic.List[string]]::new()

    if ($RemoveStartMenu) {
        try {
            Invoke-PolyFiCommand -Arguments @('windows', 'start-menu', 'remove')
        }
        catch {
            $errors.Add("Start Menu shortcut removal failed: $($_.Exception.Message)")
        }
    }

    if ($RemoveStartup) {
        try {
            Invoke-PolyFiCommand -Arguments @(
                'windows', 'startup', 'remove',
                '--config', $configPath
            )
        }
        catch {
            $errors.Add("Startup Programs shortcut removal failed: $($_.Exception.Message)")
        }
    }

    if ($RemoveWifiTasks) {
        try {
            Invoke-PolyFiCommand -Arguments @('windows', 'wifi-tasks', 'uninstall')
        }
        catch {
            $errors.Add("Wi-Fi helper task removal failed: $($_.Exception.Message)")
        }
    }

    if ($RemoveLogonTask) {
        try {
            Remove-ScheduledTaskIfPresent -TaskNameValue $TaskName
        }
        catch {
            $errors.Add($_.Exception.Message)
        }
    }

    if ($PurgeData) {
        try {
            Invoke-PolyFiPurgeData -ConfigPath $configPath
        }
        catch {
            $errors.Add("PolyFi data purge failed: $($_.Exception.Message)")
        }
    }

    if ($ClearAppDataOverride) {
        try {
            if ($currentPersistentOverride) {
                [Environment]::SetEnvironmentVariable('POLYFI_APPDATA_ROOT', $null, 'User')
                Remove-Item Env:POLYFI_APPDATA_ROOT -ErrorAction SilentlyContinue
                Update-PolyFiEnvironmentBroadcast
                Write-Host 'Cleared persistent POLYFI_APPDATA_ROOT override.'
            }
            else {
                Write-Host 'Persistent POLYFI_APPDATA_ROOT override was already clear.'
            }
        }
        catch {
            $errors.Add("Could not clear POLYFI_APPDATA_ROOT override: $($_.Exception.Message)")
        }
    }

    if ($shouldUninstallPackage) {
        try {
            Invoke-PolyFiPythonCommand -Arguments @('-m', 'pip', 'uninstall', '-y', 'polyfi-ranked')
        }
        catch {
            $errors.Add("Package uninstall failed: $($_.Exception.Message)")
        }
    }

    Write-Host ''
    if ($errors.Count -gt 0) {
        foreach ($errorMessage in $errors) {
            [Console]::Error.WriteLine($errorMessage)
        }
        Write-Host 'PolyFi uninstallation workflow completed with errors.'
        exit 1
    }

    Write-Host 'PolyFi uninstallation workflow completed.'
}
finally {
    Pop-Location
}
