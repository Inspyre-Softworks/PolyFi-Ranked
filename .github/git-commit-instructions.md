# Git Commit Instructions for PolyFi: Ranked

## Format

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short summary>

[optional body]

[optional footer(s)]
```

- Subject line: 72 characters max, imperative mood ("add", "fix", "remove" — not "added" or "fixes")
- Body: wrap at 80 characters; explain *why*, not just *what*

## Types

| Type | When to use |
|------|-------------|
| `feat` | New user-visible feature |
| `fix` | Bug fix |
| `refactor` | Code change with no behavior change |
| `test` | Adding or updating tests only |
| `docs` | Documentation only |
| `chore` | Build, packaging, CI, or dependency changes |
| `perf` | Performance improvement |
| `revert` | Reverts a prior commit |

## Scopes

Use the module or subsystem most affected:

| Scope | Covers |
|-------|--------|
| `app` | `app.py` — CLI entry point, startup flow, tray handoff |
| `service` | `service.py` — Wi-Fi preference evaluation and switching |
| `config` | `config.py` — TOML config loading and live reload |
| `models` | `models.py` — `AppConfig`, `WiFiProfilePreference`, `SpeedTestResult` |
| `paths` | `paths.py` — `AppPaths`, `POLYFI_APPDATA_ROOT`, legacy migration |
| `ui` | `ui/` — tray, dialogs, splash, settings window |
| `scheduler` | `scheduler.py` — Task Scheduler logon-task integration |
| `wifi-adapter` | `wifi_adapter_tasks.py` — elevated schtasks adapter helpers |
| `installer` | `scripts/`, `packaging/` — install/uninstall/purge scripts and Inno Setup |
| `packaging` | PyInstaller spec, CI artifact build |
| `install-record` | `install_record.py` — `install-record.json` persistence |
| `single-instance` | `single_instance.py` — named Windows mutex guard |
| `speedtest` | `speedtest_runner.py`, `speedtest_history.py` |
| `windows-shell` | `windows_shell.py` — launcher, Start Menu, Startup Programs |
| `ci` | `.github/workflows/` — CI and release workflows |
| `tests` | `tests/` — regression suite |
| `docs` | `docs/` — Sphinx documentation |

Omit the scope when a commit touches many unrelated files.

## Version and Changelog Rules

When a commit affects **shipped behavior, packaging, dependencies, Windows integration, or release automation**, the same commit must also:

1. Update `CHANGELOG.md` (add an entry under `[Unreleased]`)
2. Bump the version consistently in **both** `pyproject.toml` and `src/wifi_pref_manager/__init__.py`

Include a footer referencing the version bump when applicable:

```
chore(packaging): update Inno Setup wizard art

Bumps version to 1.0.0.
```

## Examples

```
feat(service): switch back to highest-priority network on signal recovery
```

```
fix(ui): prevent splash window from blocking tray icon on slow start

The splash Tk root was being created before the tray thread was ready,
causing a freeze on machines with slow GPU drivers.

Fixes: #42
```

```
test(scheduler): add regression for task uninstall when task is missing
```

```
chore(ci): pin pyinstaller to <7 for Python 3.14 compat
```

```
docs(config): document ethernet_wifi_mode disable_adapter UAC requirement
```

## Windows-Specific Notes

- Commits touching `wifi_adapter_tasks.py` or the `disable_adapter` Ethernet mode
  should note whether elevated privileges or the schtasks helper workflow is required.
- Commits that change the `POLYFI_APPDATA_ROOT` contract or `AppPaths` field names
  are breaking changes for anyone with an existing install; flag with `!` if so
  (e.g., `feat(paths)!: rename shortcut_icon_file to tray_icon_file`).
- Commits that change `install-record.json` schema must bump `schema_version` in
  `install_record.py` and note it in the commit body.

