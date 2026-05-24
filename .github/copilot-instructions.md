# PolyFi: Ranked Copilot Instructions

- Use Poetry for all installs and test runs.
- In a fresh checkout, run `poetry install --with dev --no-interaction` before
  assuming test tooling is missing.
- Verify changes with `poetry run pytest`.
- For Windows packaging work, install `poetry install --with packaging --no-interaction`
  and build with `powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1`.
- `ci.yml` uploads Python package artifacts, and `release.yml` publishes
  matching `v<version>` tags to GitHub Releases, TestPyPI for prereleases, and
  PyPI for non-prereleases.
- For changes that affect shipped behavior, packaging, dependencies, Windows
  integration, or release automation, update `CHANGELOG.md` and bump the
  version in both `pyproject.toml` and `src/wifi_pref_manager/__init__.py`.
- For documentation work, install `poetry install --with docs --no-interaction`
  and verify with `poetry run sphinx-build -W -b html docs docs/_build/local-html`.
- Keep Tkinter work on the shared UI thread in
  `src/wifi_pref_manager/ui/dialogs.py`.
- When changing launcher, splash, tray, or settings behavior, add regression
  tests in `tests/` for the exact scenario you fixed.
