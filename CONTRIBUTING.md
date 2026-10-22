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
`docs/conf.py`, and CI now runs the same `sphinx-build -W` command on Linux, so
local Sphinx changes should be verified before pushing.

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

GitHub Actions keeps built Python packages as CI artifacts and supports two
release paths:

- **Automatic:** `.github/workflows/auto-release.yml` fires on every push to
  `main`. When it detects a version increment, it
  publishes to TestPyPI (prerelease) or PyPI (stable) and opens a GitHub Release
  with the built distributions attached.
- **Manual:** Push a tag in the format `v<version>` to trigger
  `.github/workflows/release.yml`. Both workflows build the Windows
  installer and zipped PyInstaller bundle and attaches them to the GitHub Release.

Prerelease tags/versions publish to TestPyPI; non-prerelease versions publish to
PyPI. Both workflows validate matching package metadata and dated changelog
notes, run the Windows regression suite, and finish all builds before publishing
packages. The GitHub Release uses the current version's changelog notes and
attaches the wheel, source distribution, Windows installer, and zipped app bundle.
Publishing is serialized across both entry points. Automatic tags target the
exact tested commit. A failed tagged release can be retried from its Actions run.
Automatic release retries also resume an existing tag when it points to that
same commit, and reject versions whose tags already point elsewhere.

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
   `src/wifi_pref_manager/__init__.py` in the same PR.  If the PR already
   contains a version bump (i.e. `pyproject.toml` and
   `src/wifi_pref_manager/__init__.py` reflect a new version relative to the
   base branch), do not bump the version again.
4. Test-only, docs-only, and template-only changes may skip the release bump, but note that
   clearly in the PR checklist.
5. Fill in the pull request template with your testing notes.
6. Keep changes focused and include regression coverage for bug fixes.

Keep `[Unreleased]` at the top of `CHANGELOG.md`, followed by a dated
`## [<version>] - YYYY-MM-DD` release section with real entries matching both
version files. Versions must increase under PEP 440 ordering; retouching the
files or changing only the spelling of a version does not satisfy the rule.
Validate the complete PR locally with fetched refs:

```powershell
poetry run python scripts/check_release_hygiene.py --base origin/main --head HEAD
```

Use the actual target branch in place of `origin/main`. A follow-up PR targeting
`dev` compares against `origin/dev`. Invalid or unavailable refs fail the check.
For release preparation, use `--metadata-only --tag v<version>` to validate the
tag and metadata without a PR comparison.

