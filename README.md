# PolyFi: Ranked

[![CI](https://github.com/Inspyre-Softworks/PolyFi-Ranked/actions/workflows/ci.yml/badge.svg)](https://github.com/Inspyre-Softworks/PolyFi-Ranked/actions/workflows/ci.yml)
[![Release Hygiene](https://github.com/Inspyre-Softworks/PolyFi-Ranked/actions/workflows/release-hygiene.yml/badge.svg)](https://github.com/Inspyre-Softworks/PolyFi-Ranked/actions/workflows/release-hygiene.yml)
[![Documentation Status](https://readthedocs.org/projects/polyfi-ranked/badge/?version=latest)](https://polyfi-ranked.readthedocs.io/en/latest/)
[![PyPI version](https://img.shields.io/pypi/v/polyfi-ranked.svg)](https://pypi.org/project/polyfi-ranked/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D4.svg?logo=windows)](https://www.microsoft.com/windows)

A Windows-focused Python application that lets you define an ordered list of Wi-Fi networks and automatically connects to the highest-priority available network.

## Features

- Ordered Wi-Fi preference list
- Automatic fallback when a preferred network disappears
- Automatic switch-back when a higher-priority network returns
- Windows `netsh` integration
- TOML configuration with live reload
- Rotating log file support
- Optional system tray app
- Optional Windows Startup Programs shortcut with config-backed self-install
- Optional Windows Task Scheduler startup registration
- Default config and logs stored in platform app-data directories
- Optional automatic speed tests on connect and at a fixed interval
- Exit-time Wi-Fi state restoration when running on Python 3.12+
- Ethernet-aware Wi-Fi action mode (`disconnect_and_disable_autoconnect` or `disable_adapter`)
- Optional startup splash screen with transparent PNG support

## Quick Start

```powershell
poetry install
poetry run polyfi-ranked
```

On first run the default config file is created automatically in your local app-data folder:

```
%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.toml
```

## Documentation

Full documentation is hosted on [Read the Docs](https://polyfi-ranked.readthedocs.io/).

| Topic | Description |
|---|---|
| [Quick Start (source)](docs/quick-start.rst) | From-source install, setup scripts, teardown |
| [Getting Started: Installer](docs/getting-started-installer.rst) | Windows `.exe` installer walkthrough |
| [CLI Reference](docs/cli-reference.rst) | All commands, flags, and entry points |
| [Runtime Features](docs/runtime-features.rst) | Tray, live reload, Ethernet mode, speed tests, splash |
| [Configuration Guide](docs/configuration.rst) | Config file layout and examples |
| [Config Reference](docs/config-reference.rst) | Every `[general]` and `[[networks]]` setting |
| [Development](docs/development.rst) | Dev setup, tests, packaging, releases |
| [Building the Installer](docs/building-windows-installer.rst) | PyInstaller + Inno Setup build guide |

## Notes

- PolyFi uses `netsh wlan` under the hood — your SSIDs must already exist as saved Windows Wi-Fi profiles.
- Set the `POLYFI_APPDATA_ROOT` environment variable to store config, logs, and state files in a custom directory instead of the default `%LOCALAPPDATA%` path.

## Maintenance and Cleanup

If you need to fully remove PolyFi artifacts created by install/setup scripts, use:

- `scripts/purge_polyfi.ps1`

This cleanup flow references the installation record file:

- `install-record.json`

Use this when you want to remove installed files, PATH/task-scheduler/startup artifacts, and related app-data created during setup/testing.

## Release Automation

This repository includes automated publishing that verifies and publishes packages to:

- TestPyPI
- PyPI

The release pipeline also creates a GitHub Release with built artifacts.
