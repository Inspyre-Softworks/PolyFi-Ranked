[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,
    [string]$AppDataRoot,
    [string]$InstallRoot,
    [string]$TaskName = 'PolyFi Ranked',
    [switch]$Dev,
    [switch]$NoInteraction,
    [switch]$SkipPackageUninstall,
    [switch]$PreserveInstallDirectory,
    [switch]$PreservePathEntry,
    [switch]$PreserveInstallRecord
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

function Get-DefaultAppDataRoot {
    return Get-NormalizedPath -PathValue (
        Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Inspyre-Softworks\PolyFi-Ranked'
    )
}

function Resolve-YesNoChoice {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Prompt,
        [Parameter(Mandatory = $true)]
        [bool]$Default
    )

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

function Get-PolyFiInstallRecordPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppDataRootValue
    )

    return Join-Path $AppDataRootValue 'install-record.json'
}

function Read-PolyFiInstallRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RecordPath
    )

    if (-not (Test-Path -LiteralPath $RecordPath)) {
        return $null
    }

    return Get-Content -LiteralPath $RecordPath -Raw | ConvertFrom-Json
}

function Find-PolyFiInstallRecord {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$CandidateRoots
    )

    $seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($candidateRoot in $CandidateRoots) {
        if ([string]::IsNullOrWhiteSpace($candidateRoot)) {
            continue
        }

        $normalizedRoot = Get-NormalizedPath -PathValue $candidateRoot
        if (-not $seen.Add($normalizedRoot)) {
            continue
        }

        $recordPath = Get-PolyFiInstallRecordPath -AppDataRootValue $normalizedRoot
        $record = Read-PolyFiInstallRecord -RecordPath $recordPath
        if ($null -ne $record) {
            return [pscustomobject]@{
                AppDataRoot = $normalizedRoot
                Record = $record
                RecordPath = $recordPath
            }
        }
    }

    return $null
}

function Get-RecordFeatureValue {
    param(
        $Record,
        [Parameter(Mandatory = $true)]
        [string]$FeatureName,
        [Parameter(Mandatory = $true)]
        [bool]$Fallback
    )

    if ($null -ne $Record -and $null -ne $Record.features) {
        $property = $Record.features.PSObject.Properties[$FeatureName]
        if ($null -ne $property) {
            return [bool]$property.Value
        }
    }

    return $Fallback
}

function Resolve-InstallRoot {
    param(
        [AllowNull()]
        [string]$ExplicitInstallRoot,
        $Record
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitInstallRoot)) {
        return Get-NormalizedPath -PathValue $ExplicitInstallRoot
    }

    if ($null -ne $Record -and $null -ne $Record.paths) {
        if ($Record.paths.install_root) {
            return Get-NormalizedPath -PathValue $Record.paths.install_root
        }
        if ($Record.paths.app_executable) {
            return Split-Path -Parent (Get-NormalizedPath -PathValue $Record.paths.app_executable)
        }
        if ($Record.paths.command_path) {
            $commandPath = Get-NormalizedPath -PathValue $Record.paths.command_path
            if ((Split-Path -Leaf $commandPath) -ieq 'polyfi-ranked.exe') {
                return Split-Path -Parent $commandPath
            }
        }
    }

    return $null
}

function Test-PolyFiPackageInstalled {
    if ($SkipPackageUninstall) {
        return $false
    }

    $command = if ($Dev) {
        @('poetry', 'run', 'python', '-m', 'pip', 'show', 'polyfi-ranked')
    }
    else {
        @('python', '-m', 'pip', 'show', 'polyfi-ranked')
    }

    try {
        & $command[0] @($command | Select-Object -Skip 1) *> $null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
}

function Remove-ScheduledTaskIfPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$TaskNameValue
    )

    $output = & schtasks /Delete /F /TN $TaskNameValue 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) {
        Write-Host "Removed scheduled task: $TaskNameValue"
        return
    }

    $details = (($output | Out-String).Trim())
    $normalized = $details.ToLowerInvariant()
    if ($normalized.Contains('cannot find') -or $normalized.Contains('does not exist')) {
        return
    }

    throw "Could not remove scheduled task ${TaskNameValue}: $details"
}

function Remove-FileIfPresent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (Test-Path -LiteralPath $PathValue) {
        Remove-Item -LiteralPath $PathValue -Force
        Write-Host "Deleted file: $PathValue"
    }
}

function Remove-DirectoryIfEmpty {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        return
    }

    try {
        Remove-Item -LiteralPath $PathValue -Force
        Write-Host "Removed empty directory: $PathValue"
    }
    catch {
    }
}

function Remove-InstallDirectorySafely {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $normalized = Get-NormalizedPath -PathValue $PathValue
    $root = [System.IO.Path]::GetPathRoot($normalized).TrimEnd('\')
    if ($normalized -ieq $root) {
        throw "Refusing to remove drive root: $normalized"
    }

    if (-not (Test-Path -LiteralPath $normalized)) {
        return
    }

    Remove-Item -LiteralPath $normalized -Recurse -Force
    Write-Host "Removed install directory: $normalized"
}

function Remove-PolyFiAppDataTraces {
    param(
        [Parameter(Mandatory = $true)]
        [string]$AppDataRootValue
    )

    $normalizedRoot = Get-NormalizedPath -PathValue $AppDataRootValue
    $fileTargets = @(
        'config.toml',
        'config.example.toml',
        'managed_wifi_interface.json',
        'speedtest_history.jsonl',
        'polyfi_ranked.ico',
        'startup_trace.log',
        'tray_started.flag',
        'polyfi_ranked_output_console.log',
        'install-record.json'
    )

    foreach ($fileName in $fileTargets) {
        Remove-FileIfPresent -PathValue (Join-Path $normalizedRoot $fileName)
    }

    $logDir = Join-Path $normalizedRoot 'Logs'
    if (Test-Path -LiteralPath $logDir) {
        Remove-Item -LiteralPath $logDir -Recurse -Force
        Write-Host "Removed log directory: $logDir"
    }

    Remove-DirectoryIfEmpty -PathValue $normalizedRoot

    $legacyRoots = @(
        Join-Path $HOME 'AppData\Roaming\polyfi_ranked',
        Join-Path $HOME 'AppData\Local\polyfi_ranked'
    )
    foreach ($legacyRoot in $legacyRoots) {
        if (Test-Path -LiteralPath $legacyRoot) {
            Remove-Item -LiteralPath $legacyRoot -Recurse -Force
            Write-Host "Removed legacy application directory: $legacyRoot"
        }
    }
}

Push-Location $RepoRoot
try {
    $platformDefaultAppDataRoot = Get-DefaultAppDataRoot
    $currentPersistentOverride = [Environment]::GetEnvironmentVariable('POLYFI_APPDATA_ROOT', 'User')
    $currentPersistentOverride = if ([string]::IsNullOrWhiteSpace($currentPersistentOverride)) {
        $null
    }
    else {
        Get-NormalizedPath -PathValue $currentPersistentOverride
    }

    $existingInstallRecord = Find-PolyFiInstallRecord -CandidateRoots @(
        if ($AppDataRoot) { $AppDataRoot }
        if ($currentPersistentOverride) { $currentPersistentOverride }
        $platformDefaultAppDataRoot
    )

    $selectedAppDataRoot = if (-not [string]::IsNullOrWhiteSpace($AppDataRoot)) {
        Get-NormalizedPath -PathValue $AppDataRoot
    }
    elseif (
        $existingInstallRecord -and
        $existingInstallRecord.Record.paths -and
        $existingInstallRecord.Record.paths.app_data_root
    ) {
        Get-NormalizedPath -PathValue $existingInstallRecord.Record.paths.app_data_root
    }
    elseif ($currentPersistentOverride) {
        $currentPersistentOverride
    }
    else {
        $platformDefaultAppDataRoot
    }

    $selectedInstallRecordPath = Get-PolyFiInstallRecordPath -AppDataRootValue $selectedAppDataRoot
    $selectedInstallRecord = if (
        $existingInstallRecord -and
        $existingInstallRecord.RecordPath -ieq $selectedInstallRecordPath
    ) {
        $existingInstallRecord.Record
    }
    else {
        Read-PolyFiInstallRecord -RecordPath $selectedInstallRecordPath
    }

    $resolvedInstallRoot = Resolve-InstallRoot -ExplicitInstallRoot $InstallRoot -Record $selectedInstallRecord
    $recordedAddToPath = Get-RecordFeatureValue -Record $selectedInstallRecord -FeatureName 'add_to_path' -Fallback $false
    $shouldRemovePathEntry = (-not $PreservePathEntry) -and $recordedAddToPath -and (-not [string]::IsNullOrWhiteSpace($resolvedInstallRoot))
    $shouldUninstallPackage = Test-PolyFiPackageInstalled

    Write-Host "Repo root: $RepoRoot"
    Write-Host "Platform-default app-data root: $platformDefaultAppDataRoot"
    Write-Host "Current persistent POLYFI_APPDATA_ROOT: $(if ($currentPersistentOverride) { $currentPersistentOverride } else { '(not set)' })"
    Write-Host "Selected app-data root: $selectedAppDataRoot"
    Write-Host "Install record: $selectedInstallRecordPath"
    Write-Host "Recorded install mode: $(if ($selectedInstallRecord -and $selectedInstallRecord.install_mode) { $selectedInstallRecord.install_mode } else { '(unknown)' })"
    Write-Host "Recorded install root: $(if ($resolvedInstallRoot) { $resolvedInstallRoot } else { '(unknown)' })"
    Write-Host "Remove package via pip: $shouldUninstallPackage"
    Write-Host "Remove PATH entry: $shouldRemovePathEntry"
    Write-Host "Remove install directory: $(-not $PreserveInstallDirectory)"
    Write-Host "Remove install record: $(-not $PreserveInstallRecord)"

    $confirmed = Resolve-YesNoChoice -Prompt 'Purge all PolyFi traces from this machine?' -Default $false
    if (-not $confirmed) {
        Write-Host 'Purge cancelled.'
        exit 1
    }

    $errors = [System.Collections.Generic.List[string]]::new()

    $uninstallScript = Join-Path $RepoRoot 'scripts\uninstall_polyfi.ps1'
    if (Test-Path -LiteralPath $uninstallScript) {
        try {
            $uninstallParameters = @{
                RepoRoot = $RepoRoot
                AppDataRoot = $selectedAppDataRoot
                TaskName = $TaskName
                NoInteraction = $true
                UninstallAll = $true
                PurgeData = $true
                ClearAppDataOverride = $true
            }
            if ($Dev) {
                $uninstallParameters.Dev = $true
            }
            if (-not $shouldUninstallPackage) {
                $uninstallParameters.SkipPackageUninstall = $true
            }

            & $uninstallScript @uninstallParameters
            if ($LASTEXITCODE -ne 0) {
                throw "uninstall_polyfi.ps1 exited with code $LASTEXITCODE"
            }
        }
        catch {
            $errors.Add("Uninstall workflow reported an error: $($_.Exception.Message)")
        }
    }
    else {
        $errors.Add("Uninstall workflow script not found: $uninstallScript")
    }

    try {
        if ($shouldRemovePathEntry) {
            $pathScript = Join-Path $RepoRoot 'scripts\manage_windows_path.ps1'
            & $pathScript -Mode Remove -InstallDir $resolvedInstallRoot
            if ($LASTEXITCODE -ne 0) {
                throw "manage_windows_path.ps1 exited with code $LASTEXITCODE"
            }
            Update-PolyFiEnvironmentBroadcast
            Write-Host "Removed PATH entry for: $resolvedInstallRoot"
        }
    }
    catch {
        $errors.Add("PATH cleanup failed: $($_.Exception.Message)")
    }

    try {
        foreach ($task in @($TaskName, 'PolyFi-DisableWiFi', 'PolyFi-EnableWiFi')) {
            Remove-ScheduledTaskIfPresent -TaskNameValue $task
        }
    }
    catch {
        $errors.Add($_.Exception.Message)
    }

    try {
        $roamingPrograms = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
        $startMenuFolder = Join-Path $roamingPrograms 'PolyFi-Ranked'
        $legacyStartMenuFolder = Join-Path $roamingPrograms 'Inspyre-Softworks'
        $startupShortcut = Join-Path (Join-Path $roamingPrograms 'Startup') 'PolyFi-Ranked.lnk'
        $desktopShortcut = Join-Path ([Environment]::GetFolderPath('Desktop')) 'PolyFi Ranked.lnk'

        foreach ($filePath in @(
                (Join-Path $startMenuFolder 'PolyFi-Ranked.lnk'),
                (Join-Path $legacyStartMenuFolder 'PolyFi-Ranked.lnk'),
                $startupShortcut,
                $desktopShortcut
            )) {
            Remove-FileIfPresent -PathValue $filePath
        }

        Remove-DirectoryIfEmpty -PathValue $startMenuFolder
        Remove-DirectoryIfEmpty -PathValue $legacyStartMenuFolder
    }
    catch {
        $errors.Add("Shortcut cleanup failed: $($_.Exception.Message)")
    }

    try {
        Remove-PolyFiAppDataTraces -AppDataRootValue $selectedAppDataRoot
    }
    catch {
        $errors.Add("Application data cleanup failed: $($_.Exception.Message)")
    }

    try {
        if (-not $PreserveInstallRecord) {
            $recordScript = Join-Path $RepoRoot 'scripts\manage_install_record.ps1'
            if (Test-Path -LiteralPath $recordScript) {
                & $recordScript -Mode Remove -RecordPath $selectedInstallRecordPath
                if ($LASTEXITCODE -ne 0) {
                    throw "manage_install_record.ps1 exited with code $LASTEXITCODE"
                }
            }
            elseif (Test-Path -LiteralPath $selectedInstallRecordPath) {
                Remove-Item -LiteralPath $selectedInstallRecordPath -Force
            }
        }
    }
    catch {
        $errors.Add("Install record cleanup failed: $($_.Exception.Message)")
    }

    try {
        if ($currentPersistentOverride) {
            [Environment]::SetEnvironmentVariable('POLYFI_APPDATA_ROOT', $null, 'User')
            Remove-Item Env:POLYFI_APPDATA_ROOT -ErrorAction SilentlyContinue
            Update-PolyFiEnvironmentBroadcast
            Write-Host 'Cleared persistent POLYFI_APPDATA_ROOT override.'
        }
    }
    catch {
        $errors.Add("Environment cleanup failed: $($_.Exception.Message)")
    }

    try {
        if (-not $PreserveInstallDirectory -and $resolvedInstallRoot) {
            Remove-InstallDirectorySafely -PathValue $resolvedInstallRoot
        }
    }
    catch {
        $errors.Add("Install directory cleanup failed: $($_.Exception.Message)")
    }

    Write-Host ''
    if ($errors.Count -gt 0) {
        foreach ($errorMessage in $errors) {
            [Console]::Error.WriteLine($errorMessage)
        }
        Write-Host 'PolyFi purge completed with errors.'
        exit 1
    }

    Write-Host 'PolyFi purge completed.'
}
finally {
    Pop-Location
}
