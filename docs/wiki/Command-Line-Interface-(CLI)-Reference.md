(polyfi-ranked-cli-reference)=

# CLI Reference

PolyFi: Ranked provides command-line tools for launching the app, inspecting resolved paths, generating configuration files, and managing Windows integration.

> [!NOTE]
> These examples assume `polyfi-ranked` is available on your `PATH`.  
> When working from a Poetry checkout, prefix commands with `poetry run`.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Top-Level Flags](#top-level-flags)
- [`paths`](#paths)
- [`config`](#config)
  - [`config init`](#config-init)
- [`windows`](#windows)
  - [`windows start-menu install`](#windows-start-menu-install)
  - [`windows startup install`](#windows-startup-install)
  - [`windows logon-task install`](#windows-logon-task-install)
  - [`windows uninstall`](#windows-uninstall)
- [Task Scheduler Entry Points](#task-scheduler-entry-points)
  - [`polyfi-ranked-install-task`](#polyfi-ranked-install-task)
- [Reference Links](#reference-links)

---

(quick-start)=

## Quick Start

Install the package with either `pip` or Poetry:

```powershell
pip install .
```

```powershell
poetry install
```

Run the main command:

```powershell
polyfi-ranked
```

Or, from a Poetry development environment:

```powershell
poetry run polyfi-ranked
```

### Common Commands

| Task | Command |
|---|---|
| Show installed version | `polyfi-ranked --version` |
| Start in tray mode | `polyfi-ranked --tray` |
| Print resolved paths | `polyfi-ranked paths` |
| Generate a config file | `polyfi-ranked config init` |
| Install Start Menu shortcut | `polyfi-ranked windows start-menu install` |
| Install Startup shortcut | `polyfi-ranked windows startup install` |
| Remove Windows integrations | `polyfi-ranked windows uninstall` |
| Fully remove integrations and app data | `polyfi-ranked windows uninstall --purge-data` |

---

(top-level-flags)=

## Top-Level Flags

Top-level flags are passed directly to `polyfi-ranked`.

| Flag | Description | Example |
|---|---|---|
| `--version`, `-V` | Print the installed PolyFi: Ranked version and exit. | `polyfi-ranked --version` |
| `--tray` | Start PolyFi: Ranked minimized to the system tray. | `polyfi-ranked --tray` |
| `-l <LEVEL>` | Override the log level for the current run. | `polyfi-ranked -l DEBUG` |
| `--show-splash` | Force the startup splash screen to show for this run. | `polyfi-ranked --show-splash` |
| `--no-splash` | Disable the startup splash screen for this run. | `polyfi-ranked --no-splash` |
| `--save-speed-test-history` | Enable speed-test history saving for this run. | `polyfi-ranked --save-speed-test-history` |
| `--no-save-speed-test-history` | Disable speed-test history saving for this run. | `polyfi-ranked --no-save-speed-test-history` |
| `--speed-test-history-file <PATH>` | Override the speed-test history file path for this run. | `polyfi-ranked --speed-test-history-file C:\path\to\history.json` |

Supported log levels include:

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

> [!NOTE]
> The older `--print-paths` flag is still accepted for compatibility, but [`polyfi-ranked paths`](#paths) is the preferred command.

---

(paths)=

## `paths`

Print all resolved PolyFi: Ranked file paths, including config, log, state, and runtime paths.

### Usage

```powershell
polyfi-ranked paths
```

### When to use it

Use this when you need to confirm where PolyFi: Ranked is reading or writing files.

Examples include checking:

| File Type | Why It Matters |
|---|---|
| Config path | Confirms which config file is active. |
| Log path | Helps when debugging or collecting issue reports. |
| State path | Shows where runtime state is stored. |
| Speed-test history path | Confirms where speed-test history is saved. |

---

(config)=

## `config`

The `config` command group manages PolyFi: Ranked configuration files.

---

(config-init)=

## `config init`

Generate a complete config file containing every supported setting and its default value.

### Basic Usage

```powershell
polyfi-ranked config init
```

### Write to a Custom Location

```powershell
polyfi-ranked config init --config C:\path\to\config.toml
```

### Overwrite an Existing Config

```powershell
polyfi-ranked config init --config C:\path\to\config.toml --force
```

> [!TIP]
> Use `--force` only when you intentionally want to replace an existing config file.  
> Tiny flag, big consequences. Classic.

---

(windows)=

## `windows`

The `windows` command group manages Windows-specific integrations.

This includes:

| Integration | Purpose |
|---|---|
| Start Menu shortcut | Adds an easy launcher for PolyFi: Ranked. |
| Startup Programs shortcut | Starts PolyFi: Ranked when the user logs in. |
| Scheduled task cleanup | Removes task-based startup integration. |
| Optional data purge | Removes config, logs, and state files. |

---

(windows-start-menu-install)=

## `windows start-menu install`

Install a Start Menu shortcut that launches PolyFi: Ranked in tray mode.

### Usage

```powershell
polyfi-ranked windows start-menu install
```

### Result

After installation, PolyFi: Ranked should appear in the Windows Start Menu.

---

(windows-startup-install)=

## `windows startup install`

Install a Startup Programs shortcut that launches PolyFi: Ranked in tray mode when the user logs in.

### Usage

```powershell
polyfi-ranked windows startup install
```

### Result

PolyFi: Ranked will start automatically on user login.

---

(windows-logon-task-install)=

## `windows logon-task install`

Install a Windows Task Scheduler logon task that launches PolyFi: Ranked in tray mode when the user logs in.

### Install the Task

```powershell
polyfi-ranked windows logon-task install
```

### Remove the Task

```powershell
polyfi-ranked windows logon-task remove
```

### Result

PolyFi: Ranked can start earlier after sign-in than the Startup Programs shortcut path.

---

(windows-uninstall)=

## `windows uninstall`

Remove PolyFi: Ranked shortcuts and scheduled tasks.

### Remove Windows Integrations

```powershell
polyfi-ranked windows uninstall
```

### Remove Windows Integrations and App Data

```powershell
polyfi-ranked windows uninstall --purge-data
```

> [!WARNING]
> `--purge-data` removes PolyFi: Ranked config, log, and state files.  
> Use it for a full cleanup, not a casual uninstall.

---

(task-scheduler-entry-points)=

## Task Scheduler Entry Points

PolyFi: Ranked also provides a dedicated Task Scheduler helper command.

This is mainly useful when you want to manage the scheduled logon task directly.

---

(polyfi-ranked-install-task)=

## `polyfi-ranked-install-task`

Register or remove a Windows Task Scheduler logon task that starts PolyFi: Ranked in tray mode.

### Install the Task

```powershell
polyfi-ranked-install-task
```

### Remove the Task

```powershell
polyfi-ranked-install-task --uninstall
```

---

(reference-links)=

## Reference Links

Use these links to jump to sections on this page.

| Target | Link |
|---|---|
| CLI Reference | [CLI Reference](#polyfi-ranked-cli-reference) |
| Quick Start | [Quick Start](#quick-start) |
| Top-Level Flags | [Top-Level Flags](#top-level-flags) |
| `paths` | [`paths`](#paths) |
| `config` | [`config`](#config) |
| `config init` | [`config init`](#config-init) |
| `windows` | [`windows`](#windows) |
| `windows start-menu install` | [`windows start-menu install`](#windows-start-menu-install) |
| `windows startup install` | [`windows startup install`](#windows-startup-install) |
| `windows logon-task install` | [`windows logon-task install`](#windows-logon-task-install) |
| `windows uninstall` | [`windows uninstall`](#windows-uninstall) |
| Task Scheduler Entry Points | [Task Scheduler Entry Points](#task-scheduler-entry-points) |
| `polyfi-ranked-install-task` | [`polyfi-ranked-install-task`](#polyfi-ranked-install-task) |
