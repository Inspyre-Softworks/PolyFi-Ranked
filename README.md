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
- Optional Windows Task Scheduler startup registration
- Default config and logs stored in platform app-data directories
- Live config reload while the service is running

## Default paths on Windows

- Config: `%APPDATA%\polyfi_ranked\wifi_preferences.toml`
- Example config: `%APPDATA%\polyfi_ranked\wifi_preferences.example.toml`
- Log: `%LOCALAPPDATA%\polyfi_ranked\logs\polyfi_ranked.log`

You can print the resolved paths with:

```powershell
poetry run polyfi-ranked --print-paths
```

## Quick Start

```powershell
poetry install
poetry run polyfi-ranked
```

On first run, the default config file is created automatically in your roaming app-data folder.

## Tray Mode

```powershell
poetry run polyfi-ranked --tray
```

## Task Scheduler Autostart

```powershell
poetry run polyfi-ranked-install-task
```

## Live config reload

Edit the config file while PolyFi: Ranked is running. On the next scan cycle, it will reload the file and apply changes such as:

- SSID order
- `auto_switch`
- `scan_interval`
- `connect_timeout`
- `interface_name`
- `sync_profile_order_on_start`
- `log_level`
- `log_file`

## Notes

This app uses `netsh wlan` under the hood. Your SSIDs must already exist as saved Windows Wi-Fi profiles.
