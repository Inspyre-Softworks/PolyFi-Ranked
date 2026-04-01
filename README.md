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
- Optional automatic speed tests on connect and at a fixed interval
- Exit-time Wi-Fi state restoration when running on Python 3.12+

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

## Quick Start

```powershell
poetry install
poetry run polyfi-ranked
```

On first run, the default config file is created automatically in your local app-data folder.

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
- `min_db`
- `scan_interval`
- `connect_timeout`
- `interface_name`
- `sync_profile_order_on_start`
- `log_level`
- `log_file`
- `show_wifi_disabled_dialog`
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

## CLI Overrides

You can override these settings for a single run:

- `-l DEBUG`
- `--save-speed-test-history`
- `--no-save-speed-test-history`
- `--speed-test-history-file C:\path\to\speedtests.jsonl`

For compatibility, the older `--print-paths` flag still works, but `paths` and `config init` are the preferred command-style entry points going forward.

## Notes

This app uses `netsh wlan` under the hood. Your SSIDs must already exist as saved Windows Wi-Fi profiles.
If you set `min_db` on a `[[networks]]` block, PolyFi treats that network as unavailable when the best observed scan result is weaker than that approximate dBm threshold.
