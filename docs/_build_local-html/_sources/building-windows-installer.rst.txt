Building the Windows Installer
==============================

This guide explains how to build the PolyFi: Ranked Windows installer
(``polyfi-ranked-setup-<version>.exe``) and the portable PyInstaller app bundle
from source.

Prerequisites
-------------

- **Windows 10 or Windows 11** (the build must run on Windows because
  PyInstaller bundles the Windows runtime)
- **Python 3.12 or later** — `python.org <https://www.python.org/downloads/>`_
- **Poetry** — install with:

  .. code-block:: powershell

     python -m pip install poetry

- **Inno Setup 6** — `jrsoftware.org <https://jrsoftware.org/isinfo.php>`_.
  Required only if you want to produce the ``.exe`` installer; the PyInstaller
  app bundle can be built without it.

Installing Packaging Dependencies
-----------------------------------

The packaging tools (PyInstaller and the icon-generation helpers) live in the
Poetry ``packaging`` dependency group.  Install them with:

.. code-block:: powershell

   poetry install --with packaging --no-interaction

Building with the PowerShell Script
--------------------------------------

The recommended way to build is via the wrapper script, which handles both the
PyInstaller step and the Inno Setup step in one command:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1

When the script finishes successfully, two artifacts are produced:

- **PyInstaller app folder:**
  ``dist\pyinstaller\polyfi-ranked\polyfi-ranked.exe`` and
  ``dist\pyinstaller\polyfi-ranked\polyfi-ranked-console.exe``
- **Windows installer:**
  ``dist\installer\polyfi-ranked-setup-<version>.exe``

Script Parameters
^^^^^^^^^^^^^^^^^

The wrapper script accepts the following optional parameters:

``-SkipPyInstaller``
    Pass through ``--skip-pyinstaller`` to the Python driver.  Skips the
    PyInstaller step and assumes ``dist\pyinstaller\polyfi-ranked\`` already
    exists.

``-SkipInstaller``
    Pass through ``--skip-installer`` to the Python driver.  Skips the Inno
    Setup compilation step and stops after producing the PyInstaller app folder.

``-NoClean``
    Pass through ``--no-clean`` to the Python driver.  Reuses the existing
    PyInstaller work directory rather than deleting it first.  Useful for
    faster incremental rebuilds during development.

``-Iscc <path>``
    Explicit path to ``ISCC.exe`` when Inno Setup is installed outside the
    default ``%ProgramFiles(x86)%\Inno Setup 6`` location:

    .. code-block:: powershell

       powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_installer.ps1 `
         -Iscc 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'

Building with the Python Driver Directly
-----------------------------------------

The underlying Python script can also be called directly for finer control:

.. code-block:: powershell

   poetry run python scripts/build_windows_artifacts.py

Available flags:

``--skip-pyinstaller``
    Skip the PyInstaller step.

``--skip-installer``
    Skip the Inno Setup compilation step (produces only the app folder).

``--no-clean``
    Reuse the existing PyInstaller work directory.

``--iscc <path>``
    Full path to ``ISCC.exe``.

Examples
^^^^^^^^

Build only the PyInstaller app folder (no installer):

.. code-block:: powershell

   poetry run python scripts/build_windows_artifacts.py --skip-installer

Build the installer using a custom Inno Setup path:

.. code-block:: powershell

   poetry run python scripts/build_windows_artifacts.py `
     --iscc 'C:\Tools\InnoSetup6\ISCC.exe'

Rebuild quickly without cleaning the work directory:

.. code-block:: powershell

   poetry run python scripts/build_windows_artifacts.py --no-clean

Output Locations
----------------

After a full build the following files are present under the repository root:

.. code-block:: text

   dist\
     pyinstaller\
       polyfi-ranked\
         polyfi-ranked.exe          <- windowless app executable
         polyfi-ranked-console.exe  <- console launcher for CLI output
         (supporting DLLs and data files)
     installer\
       polyfi-ranked-setup-<version>.exe   <- Inno Setup installer
       polyfi-ranked-app-<version>-windows-x64.zip  <- bundle archive (CI only)

.. note::

   The ``.zip`` archive is created by the GitHub Actions release workflows,
   not by the local build scripts.  See :ref:`ci-release-builds` below.

How Inno Setup Is Located
--------------------------

The Python driver searches for ``ISCC.exe`` in this order:

1. The ``ISCC_EXE`` environment variable (if set)
2. ``ISCC.exe`` or ``iscc`` on the system ``PATH``
3. ``%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe``
4. ``%ProgramFiles%\Inno Setup 6\ISCC.exe``
5. Inno Setup 5 equivalents in the same directories

If ``ISCC.exe`` cannot be found, the script prints the checked locations and
exits with a non-zero status.  Pass ``--iscc`` (or ``-Iscc`` for the
PowerShell wrapper) to override.

.. _ci-release-builds:

CI and Release Builds
---------------------

The repository contains two release workflows that run the same build on a
GitHub-hosted Windows runner:

``auto-release.yml``
    Fires automatically on every push to ``main``.  When a version increment
    is detected and no matching tag exists, it builds the Python distributions
    **and** the Windows installer, then publishes a GitHub Release containing:

    - The Python wheel (``.whl``)
    - The source distribution (``.tar.gz``)
    - The Windows installer (``.exe``)
    - The Windows app bundle archive (``.zip``)

``release.yml``
    Fires when a ``v<version>`` tag is pushed manually.  Performs the same
    artifact set and additionally validates that the pushed tag matches the
    version in ``pyproject.toml``.

Both workflows install the Poetry ``packaging`` group, run
``scripts\build_windows_installer.ps1``, archive the PyInstaller bundle as a
zip, and upload the artifacts before creating the GitHub Release.

Troubleshooting
---------------

**PyInstaller cannot find the application module**
    Make sure ``poetry install --with packaging --no-interaction`` completed
    successfully and that you are running the build inside the Poetry
    environment (``poetry run ...``).

**ISCC not found**
    Install Inno Setup 6 from `jrsoftware.org <https://jrsoftware.org/isinfo.php>`_
    or pass the full path to ``ISCC.exe`` via ``-Iscc`` / ``--iscc``.

**Build fails with an icon-generation error**
    The ``packaging`` group installs Pillow for icon creation.  If the error
    mentions a missing import, re-run ``poetry install --with packaging`` to
    ensure the group is present.

**Windows Defender blocks the output executable**
    The bundled ``.exe`` is not code-signed, so Defender SmartScreen may warn
    end users.  This is expected.  Code-signing requires a purchased certificate
    and is not part of the current build workflow.
