# PolyFi: Ranked

A Windows-focused Python application that lets you define an ordered list of Wi-Fi networks and automatically connects to the highest-priority available network.

## Features

- Ordered Wi-Fi preference list
- Automatic fallback when a preferred network disappears
- Automatic switch-back when a higher-priority network returns
- Windows `netsh` integration
- TOML configuration
- Rotating log file support
- Optional system tray app
- Optional Windows Startup Programs shortcut with config-backed self-install
- Optional Windows Task Scheduler startup registration
- Default config and logs stored in platform app-data directories
- Live config reload while the service is running
- Optional automatic speed tests on connect and at a fixed interval
- Exit-time Wi-Fi state restoration when running on Python 3.12+
- Ethernet-aware Wi-Fi action mode:
  - `disconnect_and_disable_autoconnect` (default, no admin required)
  - `disable_adapter` (optional, requires admin or task helper)
- Optional startup splash screen with transparent PNG support

## Default paths on Windows

- Config: `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.toml`
- Example config: `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.example.toml`
- Log: `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\Logs\polyfi_ranked.log`
- Managed interface state: `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\managed_wifi_interface.json`
- Speed test history: `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\speedtest_history.jsonl`

You can print the resolved paths with:

```powershell
poetry run polyfi-ranked paths
```

PolyFi also honors the `POLYFI_APPDATA_ROOT` user environment variable. When it
is set, PolyFi stores its config, logs, state files, and generated icons under
that root instead of the default `%LOCALAPPDATA%` location. The installer script
below sets or clears that override for you.

## Quick Start

```powershell
poetry install
poetry run polyfi-ranked
```

To print the installed PolyFi: Ranked version:

```powershell
poetry run polyfi-ranked --version
poetry run polyfi-ranked -V
```

On first run, the default config file is created automatically in your local app-data folder.

For a one-shot Windows setup workflow that can install the package, choose the
PolyFi app-data root, and optionally add Wi-Fi helper tasks plus Start Menu and
Startup Programs entries:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 -InstallAll
```

That script uses `python -m pip install .` by default. Use `-Dev` only when you
want a contributor-style Poetry environment instead:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 -Dev -InstallAll
```

When you do not pass a flag for an installer choice, the script prompts for it
interactively and uses the shown default if you press Enter. Pass
`-NoInteraction` to skip prompts and accept the defaults instead. In
non-interactive mode, the Start Menu entry defaults to installed,
`-InstallStartup` and `-InstallWifiTasks` default to off, and `-InstallAll`
enables everything.

You can also point PolyFi at a custom app-data root:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 `
  -AppDataRoot D:\Apps\PolyFi-Ranked `
  -InstallStartMenu `
  -InstallStartup
```

For a matching Windows teardown workflow that can remove the package, prompts
through the installed integrations, optionally purge PolyFi-owned data, and
optionally clear `POLYFI_APPDATA_ROOT`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1
```

In non-interactive mode, the uninstall script defaults to removing the package,
Start Menu shortcut, Startup shortcut, Wi-Fi helper tasks, and scheduled logon
task, while leaving `-PurgeData` off. When a persistent `POLYFI_APPDATA_ROOT`
override exists, the uninstall script uses that as its default selected root
and offers to clear it:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1 `
  -NoInteraction `
  -UninstallAll `
  -PurgeData
```

To target a Poetry contributor environment instead of the normal Python install:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1 `
  -Dev `
  -SkipPackageUninstall `
  -RemoveStartup `
  -ClearAppDataOverride
```

To generate a full config file with every supported setting and its defaults:

```powershell
poetry run polyfi-ranked config init
```

You can also target a custom location or overwrite an existing file:

```powershell
poetry run polyfi-ranked config init --config C:\path\to\config.toml --force
```

To install a Start Menu shortcut that launches PolyFi directly into the tray:

```powershell
poetry run polyfi-ranked windows start-menu install
```

To install a Windows Startup Programs shortcut that launches PolyFi in tray mode at logon:

```powershell
poetry run polyfi-ranked windows startup install
```

To remove PolyFi shortcuts and scheduled tasks, with an optional full data purge:

```powershell
poetry run polyfi-ranked windows uninstall
poetry run polyfi-ranked windows uninstall --purge-data
```

## Tray Mode

```powershell
poetry run polyfi-ranked --tray
```

## Development

Use Poetry for contributor and AI-helper workflows:

```powershell
poetry install --with dev --no-interaction
poetry run pytest
```

When changing the tray or Tk GUI, keep all Tk work on the shared UI thread and prefer targeted regression tests for splash, launcher, and tray-fallback behavior.

## Windows Packaging

Install the packaging toolchain with:

```powershell
poetry install --with packaging --no-interaction
```

Build the PyInstaller app folder and, when Inno Setup 6 is installed, the
installer `.exe` with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
```

The underlying build driver is also available directly:

```powershell
poetry run python scripts/build_windows_artifacts.py
```

By default this produces:

- `dist\pyinstaller\polyfi-ranked\polyfi-ranked.exe`
- `dist\installer\polyfi-ranked-setup-<version>.exe`

The installer uses PolyFi-branded wizard art and can optionally add Start Menu
shortcuts, a desktop shortcut, a Startup Programs shortcut, and Wi-Fi helper
scheduled tasks during setup. The Wi-Fi helper task option may trigger a
Windows approval prompt because it installs elevated scheduled tasks. The
finish-page launch option is preserved; when Start Menu shortcuts were selected,
the launcher now goes through the installed Start Menu entry instead of spawning
the EXE directly from Setup.

If Inno Setup is not on `PATH`, point the build at `ISCC.exe` explicitly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1 `
  -Iscc 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

## Documentation

Sphinx and Read the Docs dependencies live in the Poetry `docs` group:

```powershell
poetry install --with docs --no-interaction
poetry run sphinx-build -W -b html docs docs/_build/local-html
```

## Task Scheduler Autostart

```powershell
poetry run polyfi-ranked-install-task
poetry run polyfi-ranked-install-task --uninstall
```

## Live config reload

Edit the config file while PolyFi: Ranked is running. On the next scan cycle, it will reload the file and apply changes such as:

- SSID order
- `auto_switch`
- `min_db`
- `scan_interval`
- `connect_timeout`
- `interface_name`
- `sync_profile_order_on_start`
- `log_level`
- `log_file`
- `show_wifi_disabled_dialog`
- `auto_disable_wifi_on_ethernet`
- `ethernet_wifi_mode`
- `add_to_startup_programs`
- `show_startup_splash`
- `splash_image_path`
- `splash_fade_in_ms`
- `splash_hold_ms`
- `splash_fade_out_ms`
- `enable_speed_tests`
- `speed_test_on_new_connection`
- `speed_test_interval`
- `save_speed_test_history`
- `speed_test_history_file`

## Speed Test Config

These `general` settings control automatic speed tests:

- `enable_speed_tests = false`
- `speed_test_on_new_connection = true`
- `speed_test_interval = 1800`
- `save_speed_test_history = false`
- `speed_test_history_file = ''`

`speed_test_interval` is measured in seconds.
When `speed_test_history_file` is blank, PolyFi uses the default local app-data history path.

## Ethernet Wi-Fi Mode

These `general` settings control Ethernet-aware Wi-Fi behavior:

- `auto_disable_wifi_on_ethernet = true`
- `ethernet_wifi_mode = 'disconnect_and_disable_autoconnect'`

Mode behavior:

- `disconnect_and_disable_autoconnect`:
  - Captures the current Wi-Fi SSID and profile auto-connect states.
  - Disconnects Wi-Fi and sets saved Wi-Fi profiles to manual connect while Ethernet is active.
  - Restores the captured Wi-Fi state when Ethernet disconnects and again on app exit.
  - Designed to work without administrator privileges.
- `disable_adapter`:
  - Disables the Wi-Fi adapter while Ethernet is active.
  - Requires administrator rights, or the PolyFi Wi-Fi task helper workflow.

## Windows Startup

These `general` settings control whether PolyFi keeps itself registered in the
user's Windows Startup Programs folder:

- `add_to_startup_programs = false`

When enabled, PolyFi refreshes the Startup Programs shortcut on launch and when
the config reloads. When disabled, PolyFi removes that shortcut if it exists.

## Startup Splash

These `general` settings control the startup splash:

- `show_startup_splash = true`
- `splash_image_path = ''`
- `splash_fade_in_ms = 280`
- `splash_hold_ms = 1100`
- `splash_fade_out_ms = 280`

PolyFi now shows the splash briefly and closes it without fade effects. `splash_hold_ms`
controls how long it stays visible. The fade timing fields are still accepted so existing
configs keep working, but they are currently ignored.

When `splash_image_path` is blank, PolyFi looks for `polyfi_ranked_splash.png` in:

- `%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\`
- `%USERPROFILE%\OneDrive\Pictures\`
- `%USERPROFILE%\Pictures\`

## CLI Overrides

You can override these settings for a single run:

- `-l DEBUG`
- `--save-speed-test-history`
- `--no-save-speed-test-history`
- `--speed-test-history-file C:\path\to\speedtests.jsonl`
- `--show-splash`
- `--no-splash`

For compatibility, the older `--print-paths` flag still works, but `paths` and `config init` are the preferred command-style entry points going forward.

## Notes

This app uses `netsh wlan` under the hood. Your SSIDs must already exist as saved Windows Wi-Fi profiles.
If you set `min_db` on a `[[networks]]` block, PolyFi treats that network as unavailable when the best observed scan result is weaker than that approximate dBm threshold. If the currently connected preferred network drops below its own threshold, PolyFi will move to the next preferred network whose signal also meets its configured threshold.
