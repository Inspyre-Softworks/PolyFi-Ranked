# Contributing to PolyFi: Ranked

Thanks for helping improve PolyFi: Ranked. This document describes the
recommended setup and the project conventions we follow.

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally.
3. Create a branch for your work.

## Development Setup

This project uses [Poetry](https://python-poetry.org/) for dependency
management and test execution.

```powershell
poetry install --with dev --no-interaction
```

Run the application locally with:

```powershell
poetry run polyfi-ranked
```

Run the tray entry point with:

```powershell
poetry run polyfi-ranked --tray
```

## Running Tests

Run the full test suite with:

```powershell
poetry run pytest
```

For coverage while working on a change:

```powershell
poetry run pytest --cov=src/wifi_pref_manager --cov-report=term-missing
```

When fixing a regression, add or update targeted tests in `tests/` so the
exact issue stays covered.

## Building Documentation

Install the docs toolchain with:

```powershell
poetry install --with docs --no-interaction
```

Build the Sphinx site locally with:

```powershell
poetry run sphinx-build -W -b html docs docs/_build/local-html
```

Read the Docs is configured to install the Poetry `docs` group and build from
`docs/conf.py`, so local Sphinx changes should be verified before pushing.

## Building Windows Packages

Install the packaging dependencies with:

```powershell
poetry install --with packaging --no-interaction
```

Build the PyInstaller app bundle and, when Inno Setup 6 is installed, the
Windows installer executable with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1
```

If you only want the onedir app bundle, skip the installer stage:

```powershell
poetry run python scripts/build_windows_artifacts.py --skip-installer
```

GitHub Actions keeps built Python packages as CI artifacts and uses
`.github/workflows/release.yml` for tag-driven publishing. Push tags in the
format `v<version>` so they match `pyproject.toml`.

- Prerelease tags publish to TestPyPI.
- Non-prerelease tags publish to PyPI.
- The GitHub Release attaches the wheel, source distribution, Windows installer,
  and zipped PyInstaller app bundle.

Trusted publishing should be configured in both PyPI and TestPyPI for this
repository before relying on the automated release workflow.

## GUI and Windows Notes

- Keep Tkinter UI work on the shared UI thread in
  `src/wifi_pref_manager/ui/dialogs.py`.
- Avoid spawning background threads that create their own `tk.Tk()` roots.
- Launcher, splash, and tray-startup changes should include regression tests,
  especially when the behavior depends on Windows shell or startup state.

## Submitting Changes

1. Ensure `poetry run pytest` passes before opening a PR.
2. Update documentation when user-visible behavior changes.
3. If the change affects shipped behavior, packaging, dependencies, Windows
   integration, or automation that supports releases, update `CHANGELOG.md`
   and bump the version in `pyproject.toml` and
   `src/wifi_pref_manager/__init__.py` in the same PR.
4. Docs-only and template-only changes may skip the release bump, but note that
   clearly in the PR checklist.
5. Fill in the pull request template with your testing notes.
6. Keep changes focused and include regression coverage for bug fixes.
