Quick Start (from Source)
=========================

This guide covers installing PolyFi: Ranked from source using Poetry or the
bundled PowerShell scripts.  For end-user Windows installer instructions see
:doc:`getting-started-installer`.

Prerequisites
-------------

- Windows 10 or Windows 11 (64-bit)
- Python 3.11 or later — `python.org <https://www.python.org/downloads/>`_
  (the exit-state restoration feature requires Python 3.12 or later)
- `Poetry <https://python-poetry.org/docs/#installation>`_

Basic Install and Run
---------------------

.. code-block:: powershell

   poetry install
   poetry run polyfi-ranked

On first run, PolyFi creates a default configuration file at:

.. code-block:: text

   %LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.toml

An example file documenting every setting is also written to:

.. code-block:: text

   %LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.example.toml

Print the installed version with:

.. code-block:: powershell

   poetry run polyfi-ranked --version
   poetry run polyfi-ranked -V

Print all resolved file paths with:

.. code-block:: powershell

   poetry run polyfi-ranked paths

One-Shot Setup Script
---------------------

For a guided workflow that installs the package, optionally sets the PolyFi
app-data root, and adds Wi-Fi helper tasks plus Start Menu and Startup Programs
entries:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 -InstallAll

That script uses ``python -m pip install .`` by default.  Use ``-Dev`` only
when you want a Poetry editable install that includes development dependencies
(the contributor workflow):

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 -Dev -InstallAll

When you do not pass a flag for an installer choice, the script prompts
interactively and uses the shown default when you press Enter.  Pass
``-NoInteraction`` to skip prompts and accept the defaults.  In non-interactive
mode, the Start Menu entry defaults to installed; ``-InstallStartup`` and
``-InstallWifiTasks`` default to off; ``-InstallAll`` enables everything.

The setup script writes an ``install-record.json`` file under the selected
app-data root so later teardown scripts can reuse the recorded directories and
feature choices.

Pointing PolyFi at a Custom App-Data Root
------------------------------------------

You can place all PolyFi data (config, logs, state files, generated icons) in a
custom directory:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\install_polyfi.ps1 `
     -AppDataRoot D:\Apps\PolyFi-Ranked `
     -InstallStartMenu `
     -InstallStartup

You can also set the ``POLYFI_APPDATA_ROOT`` user environment variable directly.
When it is set, PolyFi uses that directory as its app-data root instead of the
default ``%LOCALAPPDATA%`` path.  The install script above can set or clear that
override for you.

Teardown
--------

For a matching teardown workflow that removes the package, prompts through the
installed integrations, optionally purges PolyFi-owned data, and optionally
clears ``POLYFI_APPDATA_ROOT``:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1

Non-interactive uninstall (removes package, shortcuts, tasks; keeps data):

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1 `
     -NoInteraction `
     -UninstallAll

To target a Poetry contributor environment instead of the normal install:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\uninstall_polyfi.ps1 `
     -Dev `
     -SkipPackageUninstall `
     -RemoveStartup `
     -ClearAppDataOverride

Purge All PolyFi Traces
-----------------------

To remove all known traces of PolyFi in one pass — Windows integrations,
scheduled tasks, install record, and optionally the install directory:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\purge_polyfi.ps1

The purge script reads ``install-record.json`` first when it exists.  For
unattended teardown:

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\purge_polyfi.ps1 `
     -NoInteraction

Default File Paths
------------------

All PolyFi data lives under:

.. code-block:: text

   %LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\

Specific paths:

- **Config:** ``config.toml``
- **Example config:** ``config.example.toml``
- **Log:** ``Logs\polyfi_ranked.log``
- **Managed interface state:** ``managed_wifi_interface.json``
- **Speed test history:** ``speedtest_history.jsonl``
- **Install record:** ``install-record.json``
