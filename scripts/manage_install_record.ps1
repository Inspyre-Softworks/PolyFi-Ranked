[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Write', 'Read', 'Remove')]
    [string]$Mode,

    [string]$RecordPath,
    [string]$InstallMode,
    [string]$InstallRoot,
    [string]$AppDataRoot,
    [string]$ConfigPath,
    [string]$AppExecutable,
    [string]$CommandPath,

    [bool]$AddToPath = $false,
    [bool]$DesktopShortcut = $false,
    [bool]$ScheduledLogonTask = $false,
    [bool]$StartMenu = $false,
    [bool]$StartupShortcut = $false,
    [bool]$WifiTasks = $false
)

$ErrorActionPreference = 'Stop'

function Get-DefaultAppDataRoot {
    return Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'Inspyre-Softworks\PolyFi-Ranked'
}

function Resolve-RecordPath {
    if ($RecordPath) {
        return $RecordPath
    }
    if ($AppDataRoot) {
        return Join-Path $AppDataRoot 'install-record.json'
    }
    return Join-Path (Get-DefaultAppDataRoot) 'install-record.json'
}

function Get-TimestampUtc {
    return [DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssK')
}

function Normalize-PathValue {
    param(
        [AllowNull()]
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return $null
    }

    return [System.IO.Path]::GetFullPath($Value)
}

$resolvedRecordPath = Resolve-RecordPath
$resolvedAppDataRoot = if ($AppDataRoot) {
    Normalize-PathValue $AppDataRoot
}
else {
    Normalize-PathValue (Get-DefaultAppDataRoot)
}

switch ($Mode) {
    'Read' {
        if (Test-Path -LiteralPath $resolvedRecordPath) {
            Get-Content -LiteralPath $resolvedRecordPath -Raw
        }
        break
    }

    'Remove' {
        if (Test-Path -LiteralPath $resolvedRecordPath) {
            Remove-Item -LiteralPath $resolvedRecordPath -Force
        }
        break
    }

    'Write' {
        $record = if (Test-Path -LiteralPath $resolvedRecordPath) {
            Get-Content -LiteralPath $resolvedRecordPath -Raw | ConvertFrom-Json
        }
        else {
            [pscustomobject]@{
                schema_version = 1
                created_at_utc = Get-TimestampUtc
                paths = [pscustomobject]@{}
                features = [pscustomobject]@{}
            }
        }

        $record | Add-Member -NotePropertyName schema_version -NotePropertyValue 1 -Force
        $record | Add-Member -NotePropertyName updated_at_utc -NotePropertyValue (Get-TimestampUtc) -Force

        if ($PSBoundParameters.ContainsKey('InstallMode')) {
            $record | Add-Member -NotePropertyName install_mode -NotePropertyValue $InstallMode -Force
        }

        if (-not $record.paths) {
            $record | Add-Member -NotePropertyName paths -NotePropertyValue ([pscustomobject]@{}) -Force
        }
        if (-not $record.features) {
            $record | Add-Member -NotePropertyName features -NotePropertyValue ([pscustomobject]@{}) -Force
        }

        if ($PSBoundParameters.ContainsKey('AppDataRoot')) {
            $record.paths | Add-Member -NotePropertyName app_data_root -NotePropertyValue (Normalize-PathValue $AppDataRoot) -Force
        }
        elseif (-not $record.paths.PSObject.Properties['app_data_root']) {
            $record.paths | Add-Member -NotePropertyName app_data_root -NotePropertyValue $resolvedAppDataRoot -Force
        }
        if ($PSBoundParameters.ContainsKey('AppExecutable')) {
            $record.paths | Add-Member -NotePropertyName app_executable -NotePropertyValue (Normalize-PathValue $AppExecutable) -Force
        }
        if ($PSBoundParameters.ContainsKey('CommandPath')) {
            $record.paths | Add-Member -NotePropertyName command_path -NotePropertyValue (Normalize-PathValue $CommandPath) -Force
        }
        if ($PSBoundParameters.ContainsKey('ConfigPath')) {
            $record.paths | Add-Member -NotePropertyName config_path -NotePropertyValue (Normalize-PathValue $ConfigPath) -Force
        }
        elseif (-not $record.paths.PSObject.Properties['config_path']) {
            $record.paths | Add-Member -NotePropertyName config_path -NotePropertyValue (Join-Path $resolvedAppDataRoot 'config.toml') -Force
        }
        if ($PSBoundParameters.ContainsKey('InstallRoot')) {
            $record.paths | Add-Member -NotePropertyName install_root -NotePropertyValue (Normalize-PathValue $InstallRoot) -Force
        }

        foreach ($featureName in 'AddToPath', 'DesktopShortcut', 'ScheduledLogonTask', 'StartMenu', 'StartupShortcut', 'WifiTasks') {
            if ($PSBoundParameters.ContainsKey($featureName)) {
                $jsonName = ($featureName -creplace '([a-z])([A-Z])', '$1_$2').ToLowerInvariant()
                $record.features | Add-Member -NotePropertyName $jsonName -NotePropertyValue ([bool](Get-Variable -Name $featureName -ValueOnly)) -Force
            }
        }

        $recordDirectory = Split-Path -Parent $resolvedRecordPath
        if (-not [string]::IsNullOrWhiteSpace($recordDirectory)) {
            New-Item -ItemType Directory -Path $recordDirectory -Force | Out-Null
        }

        $record | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resolvedRecordPath -Encoding UTF8
        break
    }
}
