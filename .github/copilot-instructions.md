# PolyFi: Ranked Copilot Instructions

- Use Poetry for all installs and test runs.
- In a fresh checkout, run `poetry install --with dev --no-interaction` before
  assuming test tooling is missing.
- Verify changes with `poetry run pytest`.
- For documentation work, install `poetry install --with docs --no-interaction`
  and verify with `poetry run sphinx-build -W -b html docs docs/_build/local-html`.
- Keep Tkinter work on the shared UI thread in
  `src/wifi_pref_manager/ui/dialogs.py`.
- When changing launcher, splash, tray, or settings behavior, add regression
  tests in `tests/` for the exact scenario you fixed.
