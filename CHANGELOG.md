# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project tracks prerelease
versions so packaging, docs, and support paths stay aligned.

## [Unreleased]

### Added

- Placeholder for upcoming changes.

### Changed

- Placeholder for upcoming changes.

### Fixed

- Placeholder for upcoming changes.

### Removed

- Placeholder for upcoming changes.

### Security

- Placeholder for upcoming changes.

## [1.0.0-dev.3] - 2026-05-21

### Added

- A PowerShell uninstall workflow that mirrors the installer with prompts,
  non-interactive defaults, app-data root selection, optional package removal,
  optional data purging, and optional `POLYFI_APPDATA_ROOT` cleanup.

## [1.0.0-dev.2] - 2026-05-21

### Fixed

- Startup-facing Windows launchers now avoid `pythonw.exe` and use an internal
  direct-tray path so Start Menu, Startup Programs, and scheduled logon
  launches stay alive long enough to create the tray icon.

## [1.0.0-dev.1] - 2026-05-21

### Added

- Ranked Wi-Fi management that automatically prefers the highest-priority
  available saved network.
- Tray-first Windows operation with settings, config initialization, path
  reporting, `-V`/`--version`, splash support, and optional live config reload.
- Ethernet-aware Wi-Fi control modes, optional speed-test history, and managed
  interface state restoration for supported runtimes.
- Windows shell integrations for Start Menu installation, Startup Programs
  registration, scheduled Wi-Fi helper tasks, and one-shot uninstall cleanup
  with optional local data purging.
- A PowerShell installer that can install the package, create the default
  config, choose the PolyFi app-data root, and optionally wire up Start Menu,
  startup, and Wi-Fi helper integrations in one pass.

### Changed

- Release hygiene is now tracked in-repo with explicit changelog/version
  maintenance guidance, automated verification, and CI checks.
