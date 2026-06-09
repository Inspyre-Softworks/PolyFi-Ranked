# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog, and this project tracks prerelease
versions so packaging, docs, and support paths stay aligned.

## [Unreleased]

## [1.0.0-dev.22] - 2026-06-09

### Fixed

- Fixed failing `docs` CI job caused by Sphinx Napoleon converting `Methods:`
  sections in class docstrings into `.. method::` RST directives.  Those
  directives conflicted with the same methods already documented by autodoc
  `:members:`, producing 31 "duplicate object description" warnings that were
  treated as errors by the `-W` flag.  Removed the redundant `Methods:` summary
  sections from the `ConfigLoader`, `NetshWiFiApi`, `AppPaths`,
  `TaskSchedulerInstaller`, `WiFiPreferenceService`, and `WifiAdapterTaskManager`
  class docstrings.

### Changed

- Restored the `docs` CI job to `ci.yml` (Linux, runs
  `poetry run sphinx-build -W -b html docs docs/_build/local-html`) so
  Sphinx warnings-as-errors are caught before Read the Docs.
- Added `permissions: contents: read` to `ci.yml` in line with the `main`
  branch baseline.

## [1.0.0-dev.20] - 2026-06-06

### Fixed

- Fixed installer crash (`'NoneType' object has no attribute 'isatty'`) that
  occurred when the windowed PyInstaller bundle (`console=False`) set
  `sys.stdin`, `sys.stdout`, and `sys.stderr` to `None`.  Added a `NullStream`
  class and a `redirect_none_streams()` helper to `console_output.py` that
  replaces any `None` standard stream with a safe no-op object at module-import
  time, before third-party libraries such as `inspy-logger` call `isatty()` at
  their own module level.

## [1.0.0-dev.19] - 2026-06-06

### Fixed

- Built the Windows app launcher as a windowless executable and kept a separate
  `polyfi-ranked-console.exe` launcher for command-line sessions, preventing
  Start Menu, Startup Programs, and scheduled logon launches from opening a
  terminal window before the tray app starts.
- Updated `scheduler.py` and `windows_shell.py` to prefer the windowless launcher
  for scheduled logon tasks and shell shortcuts so no terminal window appears on
  Windows-initiated starts.

## [1.0.0-dev.18] - 2026-06-05

### Added

- Added config-backed scheduled logon task management so PolyFi can start earlier after sign-in through
  Windows Task Scheduler, including a new Settings checkbox and `polyfi-ranked windows logon-task`
  install/remove commands.
- Added an optional Inno Setup component for the scheduled logon task and a Start Menu shortcut that
  uninstalls the Wi-Fi helper scheduled tasks.
- Added tray update support: automatic update checks, manual "Check for Updates", GitHub Release
  installer download/launch, and an About dialog with documentation, GitHub, PolyFi, and Python details.

### Fixed

- Downgraded Windows-shutdown `netsh` process creation failures during exit-time Wi-Fi restoration so
  shutdown does not surface a noisy error when Windows is already refusing new processes.

## [1.0.0-dev.17] - 2026-06-04

### Added

- `src/wifi_pref_manager/subprocess_utils.py`: new shared helper `hidden_subprocess_kwargs()` that
  returns Windows-specific subprocess flags to suppress console windows.
- `src/wifi_pref_manager/startup_trace.py`: new shared helper `append_startup_trace_line(trace_path, message)`
  that appends one ISO-timestamped line to a startup trace file, creating parent directories as needed.
- `tests/test_subprocess_utils.py`: tests covering all major branches of `hidden_subprocess_kwargs`.
- `tests/test_startup_trace.py`: tests verifying parent-directory creation, line format/content,
  successive appends, UTF-8 encoding, and error propagation.

### Changed

- `scheduler.py` (`TaskSchedulerInstaller._hidden_subprocess_kwargs`): delegates to the new
  shared `hidden_subprocess_kwargs()` helper; public interface preserved for backward compatibility.
- `netsh_wifi.py` (`NetshWiFiApi._hidden_subprocess_kwargs`): same delegation refactor.
- `wifi_adapter_tasks.py` (`WifiAdapterTaskManager._hidden_subprocess_kwargs`): same delegation refactor.
- `app.py` (`Application.append_startup_trace`): delegates to `append_startup_trace_line()`; existing
  OSError suppression and logging semantics are preserved.
- `ui/tray.py` (`TrayApplication._append_startup_trace`): delegates to `append_startup_trace_line()`;
  existing guard on `None` trace path and OSError suppression are preserved.

### Fixed

- `service.py` (`WiFiPreferenceService.restore_startup_network_state`): wrapped the entire method body
  in a broad `except Exception` guard so this atexit handler never propagates an exception...

## [1.0.0-dev.16] - 2026-05-28

### Changed

- Reduced steady-state tray overhead by using the lighter `netsh interface`
  path for routine Ethernet checks, skipping visible-network scans while the
  current Wi-Fi network is already the highest actionable preference, and
  slowing idle Tk dialog queue polling.

### Fixed

- Automatic speed tests configured for new connections no longer run just
  because PolyFi starts while Windows is already connected; they now wait for
  an actual observed connection change, an app-initiated connection change, or
  the configured periodic interval.

## [1.0.0-dev.15] - 2026-05-28

### Fixed

- Resolved `Join-Path` failure in `scripts/build_windows_installer.ps1` when
  `$PSScriptRoot` is empty under GitHub Actions by adding a CI-safe fallback
  that tries `$MyInvocation.MyCommand.Path` then `Get-Location` before
  computing `$RepoRoot` (fixes workflow run 26550598265, job 78211816902).

## [1.0.0-dev.14] - 2026-05-27

### Added

- A local `docs/wiki/` source-of-truth workflow can now sync Markdown pages to
  the adjacent `PolyFi-Ranked.wiki` checkout with dry-run, dirty-repo, link
  rewrite, and prune safety checks.

## [1.0.0-dev.13] - 2026-05-26

### Fixed

- The auto-release workflow now validates `POLYFI_VERSION` before constructing
  the Windows PyInstaller app bundle archive path, and reuses the validated
  value for archive naming to avoid empty-value `Join-Path` failures.

## [1.0.0-dev.12] - 2026-05-26

### Fixed

- Release hygiene now treats a PR-wide version bump as satisfying the policy for
  later release-sensitive changes in the same PR, so follow-up commits do not
  fail unless the PR never updated the changelog and version metadata at all.

## [1.0.0-dev.11] - 2026-05-24

### Added

- A push-to-main auto-release workflow (`auto-release.yml`) that detects version
  increments, creates the matching `v<version>` git tag, publishes prerelease
  versions to TestPyPI and stable versions to PyPI via OIDC trusted publishing,
  and opens a GitHub Release with the built distributions attached. The workflow
  is idempotent — it skips silently when the version is unchanged or the tag
  already exists.

## [1.0.0-dev.10] - 2026-05-23

### Added

- A dedicated `scripts/purge_polyfi.ps1` workflow now removes recorded PolyFi
  app-data traces, Windows shell integrations, scheduled tasks, PATH entries,
  install records, and the recorded install directory in one pass.

## [1.0.0-dev.9] - 2026-05-23

### Added

- A tag-driven GitHub release workflow now validates `v<version>` tags, builds
  Python distributions plus Windows release assets, publishes prereleases to
  TestPyPI, publishes stable releases to PyPI, and attaches the build outputs
  to the matching GitHub Release.
- The Windows installer now offers a checked-by-default option to add the
  installed PolyFi directory to `PATH`, with matching uninstall cleanup for the
  PATH entry.
- PolyFi's setup and Windows integration commands now keep an
  `install-record.json` file in sync so the teardown workflow can reuse the
  recorded directories and installed features before removing them.

### Changed

- The main CI workflow now uploads the built wheel and source distribution as
  GitHub Actions artifacts so package outputs are retained for each run.

## [1.0.0-dev.8] - 2026-05-22

### Fixed

- The Windows installer now creates the `PolyFi Ranked` Start Menu folder and
  launcher entries as part of the normal install instead of treating them as an
  optional task hidden under the Programs root.
- The installer no longer auto-launches PolyFi after setup, which avoids the
  immediate post-install tray launch that Windows Defender was blocking for
  unsigned local builds.

## [1.0.0-dev.7] - 2026-05-21

### Fixed

- Start Menu, Startup Programs, and scheduled tray launchers now start PolyFi
  with the detached `--tray` path instead of forcing `--direct-tray`, so
  Windows shell launches can hand off cleanly to the background tray runtime.
- Windows shortcut generation now prefers the installed `Scripts\polyfi-ranked.exe`
  launcher when the active Python runtime lives above a `Scripts` directory,
  keeping Start Menu and Startup shortcuts anchored to the correct installed app.

## [1.0.0-dev.6] - 2026-05-21

### Added

- The Windows installer now offers Start Menu shortcuts, Startup Programs
  registration, and Wi-Fi helper task setup directly on the installer task
  page, with uninstall cleanup for the Startup and Wi-Fi helper integrations.
- The installer wizard now uses PolyFi-branded artwork generated from the
  project's icon art instead of the default Inno Setup visuals.

## [1.0.0-dev.5] - 2026-05-21

### Fixed

- The Windows packaging helper now performs its own retrying cleanup for
  PyInstaller work folders instead of relying on PyInstaller's `--clean`
  removal path, which could fail on Windows with `WinError 5` against
  `localpycs`.

## [1.0.0-dev.4] - 2026-05-21

### Added

- A Windows packaging workflow that builds a PyInstaller onedir executable and,
  when Inno Setup 6 is available, a native installer `.exe`.
- Checked-in PyInstaller and Inno Setup packaging definitions plus helper
  scripts so the Windows installer build stays reproducible in-repo.

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
