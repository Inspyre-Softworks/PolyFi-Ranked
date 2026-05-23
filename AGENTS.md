---
description: PolyFi Ranked repository instructions for coding agents
alwaysApply: true
---

# PolyFi: Ranked Agent Instructions

## Overview

PolyFi: Ranked is a Windows-first Python application for managing Wi-Fi profile
priority, tray startup, and Ethernet-aware Wi-Fi behavior. The main package
lives in `src/wifi_pref_manager`, and the test suite lives in `tests/`.

## Required Workflow

- Use Poetry for dependency management, installs, and test execution.
- In a fresh checkout, install contributor dependencies with:

```powershell
poetry install --with dev --no-interaction
```

- Run the full test suite with:

```powershell
poetry run pytest
```

- For changes headed to `main` or `master` that affect shipped behavior,
  packaging, dependencies, Windows integration, or release automation, update
  `CHANGELOG.md` and bump the version in both `pyproject.toml` and
  `src/wifi_pref_manager/__init__.py` in the same change.

- Build the Sphinx docs with:

```powershell
poetry install --with docs --no-interaction
poetry run sphinx-build -W -b html docs docs/_build/local-html
```

- Build the Windows PyInstaller bundle and Inno Setup installer with:

```powershell
poetry install --with packaging --no-interaction
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
```

- For runtime smoke checks, prefer:

```powershell
poetry run polyfi-ranked --tray
```

## Repo-Specific Guidance

- Keep Tkinter work on the shared UI thread in `wifi_pref_manager.ui.dialogs`.
- Do not create ad hoc `tk.Tk()` roots on background threads.
- When changing startup or packaging behavior, add regression coverage for:
  - runtime launcher selection in `windows_shell.py`
  - tray fallback paths in `app.py`
  - splash path resolution in `ui/splash.py`
- Prefer adapting instructions and templates to this repo's real structure
  instead of copying wording from other projects verbatim.

## Important Modules

- `src/wifi_pref_manager/app.py`: CLI/bootstrap, tray handoff, startup flow
- `src/wifi_pref_manager/service.py`: Wi-Fi preference evaluation and switching
- `src/wifi_pref_manager/windows_shell.py`: launcher and Start Menu integration
- `src/wifi_pref_manager/ui/`: tray, dialogs, settings, and splash UI helpers
- `tests/`: regression coverage for config, tray, splash, service, and task setup
