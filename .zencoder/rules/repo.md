---
description: Repository information overview
alwaysApply: true
---

# PolyFi: Ranked Repository Information

## Summary

PolyFi: Ranked is a Poetry-managed Python application for Windows that keeps a
preferred Wi-Fi profile order, optionally runs in the system tray, and can
adjust Wi-Fi behavior when Ethernet is active.

## Structure

- `src/wifi_pref_manager/`: main package
- `src/wifi_pref_manager/ui/`: tray, settings, dialogs, splash UI
- `tests/`: unit and regression tests
- `config/`: example configuration data
- `docs/`: additional project documentation

## Language and Runtime

- Language: Python
- Python: 3.11+
- Build system: Poetry

## Build and Installation

Use Poetry for contributor and AI-helper workflows:

```powershell
poetry install --with dev --no-interaction
```

Run the app with:

```powershell
poetry run polyfi-ranked
```

Build the Windows executable and installer with:

```powershell
poetry install --with packaging --no-interaction
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
```

## Testing

Run the full suite with:

```powershell
poetry run pytest
```

Coverage-oriented verification while iterating:

```powershell
poetry run pytest --cov=src/wifi_pref_manager --cov-report=term-missing
```

Build the docs with:

```powershell
poetry install --with docs --no-interaction
poetry run sphinx-build -W -b html docs docs/_build/local-html
```

## Release Hygiene

For changes that affect shipped behavior, packaging, dependencies, Windows
integration, or release automation, update `CHANGELOG.md` and bump the version
in both `pyproject.toml` and `src/wifi_pref_manager/__init__.py` as part of the
same change. Docs-only and template-only changes may skip that bump when the PR
explicitly calls it out.

## Main Entry Points

- `polyfi-ranked`
- `polyfi-ranked-install-task`
