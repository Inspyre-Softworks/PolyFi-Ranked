# PolyFi: Ranked Copilot Instructions

- Use Poetry for all installs and test runs.
- In a fresh checkout, run `poetry install --with dev --no-interaction` before
  assuming test tooling is missing.
- Verify changes with `poetry run pytest`.
- For Windows packaging work, install `poetry install --with packaging --no-interaction`
  and build with `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1`.
- `ci.yml` uploads Python package artifacts. `auto-release.yml` fires on every
  push to `main` and, when it detects a version increment with no existing tag,
  publishes to TestPyPI (prerelease) or PyPI (stable) and creates the matching
  GitHub Release. `release.yml` handles the same publishing and GitHub Release
  creation for manually pushed `v<version>` tags and additionally builds the
  Windows installer and zipped app bundle.
- For changes that affect shipped behavior, packaging, dependencies, Windows
  integration, or release automation, update `CHANGELOG.md` and bump the
  version in both `pyproject.toml` and `src/wifi_pref_manager/__init__.py`.
  If the PR already contains a version bump (i.e. `pyproject.toml` and
  `src/wifi_pref_manager/__init__.py` reflect a new version relative to the
  base branch), do not bump the version again.
- For documentation work, install `poetry install --with docs --no-interaction`
  and verify with `poetry run sphinx-build -W -b html docs docs/_build/local-html`.
- Keep Tkinter work on the shared UI thread in
  `src/wifi_pref_manager/ui/dialogs.py`.
- When changing launcher, splash, tray, or settings behavior, add regression
  tests in `tests/` for the exact scenario you fixed.
