Development
===========

.. contents:: On this page
   :local:
   :depth: 2

Setting Up the Contributor Environment
---------------------------------------

PolyFi: Ranked uses `Poetry <https://python-poetry.org/>`_ for dependency and
environment management.  Install the full development environment with:

.. code-block:: powershell

   poetry install --with dev --no-interaction

Running Tests
-------------

.. code-block:: powershell

   poetry run pytest

.. note::

   The full test suite requires Windows because several modules depend on
   ``ctypes.WinDLL`` and the GUI components require a display.  On Linux or
   macOS, run targeted tests that do not touch Windows-only or GUI code.

GUI Development Notes
---------------------

When changing the tray or Tkinter GUI:

- Keep all Tk work on the shared UI thread.
- Prefer targeted regression tests for splash, launcher, and tray-fallback
  behavior.

Building Sphinx Documentation
------------------------------

Sphinx and Read the Docs dependencies live in the Poetry ``docs`` group:

.. code-block:: powershell

   poetry install --with docs --no-interaction
   poetry run sphinx-build -W -b html docs docs/_build/local-html

Windows Packaging
-----------------

Install the packaging toolchain with:

.. code-block:: powershell

   poetry install --with packaging --no-interaction

Build the PyInstaller app folder and, when Inno Setup 6 is installed, the
installer ``.exe``:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1

The underlying Python driver is also available directly:

.. code-block:: powershell

   poetry run python scripts/build_windows_artifacts.py

Default build outputs:

- ``dist\pyinstaller\polyfi-ranked\polyfi-ranked.exe``
- ``dist\installer\polyfi-ranked-setup-<version>.exe``

See :doc:`building-windows-installer` for full build documentation.

GitHub Releases
---------------

**Automatic (push to** ``main`` **):** ``auto-release.yml`` fires on every push
to ``main``.  When it detects a version increment in ``pyproject.toml`` with no
matching tag yet:

- Builds the wheel and source distribution.
- Publishes prerelease versions to TestPyPI; non-prerelease versions to PyPI.
- Creates the ``v<version>`` git tag and a GitHub Release with the built
  distributions attached.

The workflow is idempotent — repeated pushes with the same version are no-ops.

**Manual (tag push):** Pushing a tag matching ``v<version>`` runs
``release.yml``.  That workflow additionally builds the Windows installer and
zipped PyInstaller bundle and attaches them to the GitHub Release.

``ci.yml`` uploads the Python wheel and source distribution as workflow
artifacts on every push so builds are retained without a full release.

PyPI and TestPyPI publishing use trusted publishing, so both ``auto-release.yml``
and ``release.yml`` must be trusted by the registries.

Release Hygiene
---------------

PRs that change non-exempt source files must also update:

- ``CHANGELOG.md``
- ``pyproject.toml`` (version)
- ``src/wifi_pref_manager/__init__.py`` (version)

This is enforced by ``scripts/check_release_hygiene.py`` and the
``release-hygiene.yml`` workflow.  Files under ``docs/``, ``README.md``,
``AGENTS.md``, ``CONTRIBUTING.md``, and a few others are exempt from this
requirement.
