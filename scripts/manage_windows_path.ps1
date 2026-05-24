[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Add', 'Remove')]
    [string]$Mode,

    [Parameter(Mandatory = $true)]
    [string]$InstallDir
)

$ErrorActionPreference = 'Stop'

function Normalize-PathEntry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    return $Value.Trim().Trim('"').TrimEnd('\').ToLowerInvariant()
}

$resolvedInstallDir = [System.IO.Path]::GetFullPath($InstallDir)
$normalizedInstallDir = Normalize-PathEntry -Value $resolvedInstallDir
$environmentSubkey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
$registry = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey($environmentSubkey, $true)

if (-not $registry) {
    throw "Could not open HKLM:\\$environmentSubkey for writing."
}

try {
    $currentPath = [string]$registry.GetValue('Path', '', 'DoNotExpandEnvironmentNames')
    $existingEntries = @()
    if ($currentPath) {
        $existingEntries = $currentPath -split ';'
    }

    $updatedEntries = [System.Collections.Generic.List[string]]::new()
    $alreadyPresent = $false

    foreach ($entry in $existingEntries) {
        $trimmedEntry = $entry.Trim()
        if (-not $trimmedEntry) {
            continue
        }

        if ((Normalize-PathEntry -Value $trimmedEntry) -eq $normalizedInstallDir) {
            $alreadyPresent = $true
            continue
        }

        $updatedEntries.Add($trimmedEntry)
    }

    if ($Mode -eq 'Add' -and -not $alreadyPresent) {
        $updatedEntries.Add($resolvedInstallDir)
    }

    $newPath = [string]::Join(';', $updatedEntries)
    $registry.SetValue('Path', $newPath, [Microsoft.Win32.RegistryValueKind]::ExpandString)
}
finally {
    $registry.Close()
}
