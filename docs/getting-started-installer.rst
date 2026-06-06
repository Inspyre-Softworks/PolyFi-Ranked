Getting Started: Windows Installer
===================================

This guide walks end users through downloading and installing PolyFi: Ranked on
Windows using the official ``.exe`` installer and getting it running for the
first time.

Prerequisites
-------------

- Windows 10 or Windows 11 (64-bit)
- No additional software required — the installer bundles everything it needs

Downloading the Installer
-------------------------

1. Open the `Releases page <https://github.com/Inspyre-Softworks/PolyFi-Ranked/releases>`_
   on GitHub.
2. Find the latest release (or the specific version you want).
3. Under **Assets**, download the file named
   ``polyfi-ranked-setup-<version>.exe``.

Running the Installer Wizard
----------------------------

Double-click the downloaded ``.exe`` to launch the setup wizard.  Windows
Defender SmartScreen may show a prompt because the executable is not yet
code-signed; click **More info → Run anyway** to proceed.

The wizard steps are:

1. **License agreement** — read and accept the license.
2. **Destination folder** — the default is
   ``%ProgramFiles%\PolyFi-Ranked``.  Change it only if you
   have a specific reason.
3. **Components** — choose which optional pieces to install:

   - *Start Menu shortcuts* — adds a PolyFi: Ranked entry to the Windows
     Start Menu.
   - *Desktop shortcut* — adds a shortcut to your desktop.
   - *Add to PATH* — makes ``polyfi-ranked`` and
     ``polyfi-ranked-console`` available in any terminal window (recommended).
   - *Startup Programs shortcut* — launches PolyFi automatically in tray mode
     when you log in.
   - *Scheduled logon task* — launches PolyFi in tray mode through Task
     Scheduler, which can start earlier after sign-in than the Startup Programs
     shortcut.
   - *Wi-Fi helper scheduled tasks* — installs the ``PolyFi-DisableWiFi`` and
     ``PolyFi-EnableWiFi`` elevated tasks that power the ``disable_adapter``
     Ethernet mode.  Windows will show a User Account Control (UAC) prompt to
     approve creating these tasks.

4. **Ready to install** — review the summary and click **Install**.
5. **Finish** — optionally tick **Launch PolyFi: Ranked** to start the app
   immediately after the wizard closes.

.. note::

   The installer records your selected components and install directory in
   ``%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\install-record.json``.
   The command-line uninstall and purge scripts read this file to undo the
   right integrations without re-prompting you.

First Launch
------------

On first launch PolyFi creates a default configuration file at:

.. code-block:: text

   %LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.toml

An example file documenting every supported setting is also written to:

.. code-block:: text

   %LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.example.toml

PolyFi starts minimized to the system tray by default.  Click the tray icon to
open the settings window or right-click for the context menu.

Configuring Your Wi-Fi Networks
--------------------------------

Open the configuration file in any text editor (Notepad works fine) and add a
``[[networks]]`` block for each Wi-Fi network you want PolyFi to manage, in
priority order from highest to lowest:

.. code-block:: toml

   [general]
   scan_interval = 10

   [[networks]]
   ssid = 'HomeWiFi_5GHz'
   auto_switch = true
   min_db = -72

   [[networks]]
   ssid = 'HomeWiFi_2GHz'
   auto_switch = true

Save the file.  PolyFi reloads the configuration on the next scan cycle
without requiring a restart.

.. note::

   The SSIDs you list must already exist as saved Windows Wi-Fi profiles.
   PolyFi uses ``netsh wlan`` to switch between them.

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

You can also move PolyFi's data to a different location by setting the
``POLYFI_APPDATA_ROOT`` user environment variable to your preferred directory.
When that variable is set, PolyFi uses it instead of the default
``%LOCALAPPDATA%`` path.

Running in Tray Mode
--------------------

PolyFi's tray icon lets you monitor connection status and adjust settings
without opening a terminal.  If it is not already running in tray mode, launch
it from the Start Menu shortcut or by running:

.. code-block:: text

   polyfi-ranked --tray

The installed ``polyfi-ranked.exe`` app launcher is windowless so shortcuts do
not flash a terminal window.  Use ``polyfi-ranked-console.exe`` when you need
interactive command output from the installed bundle.

Windows Startup Integration
----------------------------

To have PolyFi launch automatically at logon you can:

- Enable the **Startup Programs shortcut** option in the installer wizard, or
- Enable the **Scheduled logon task** option in the installer wizard, or
- Open the settings window from the tray icon and turn on
  *Run at Windows startup* or *Start earlier with Task Scheduler*, or
- Register a Windows Task Scheduler logon task with:

  .. code-block:: text

     polyfi-ranked windows logon-task install

  Remove it again with:

  .. code-block:: text

     polyfi-ranked windows logon-task remove

  The standalone helper remains available for console-script installs:

  .. code-block:: text

     polyfi-ranked-install-task

  Remove the helper-installed task with:

  .. code-block:: text

     polyfi-ranked-install-task --uninstall

Update Checks
-------------

The tray menu includes **Check for Updates** and **About PolyFi: Ranked**.  If
automatic update checks are enabled in Settings, PolyFi checks GitHub Releases
after the tray icon starts.  When a newer release includes a Windows installer
asset, PolyFi can download the installer under local app-data and launch it.

Uninstalling
------------

Use the standard Windows **Apps & features** (or **Programs and Features**)
control panel entry to run the bundled uninstaller.  It removes the installed
files, the ``PATH`` entry, Startup Programs shortcut, and Wi-Fi helper
scheduled tasks automatically.

To also remove all PolyFi data (config, logs, state files) in one pass, run
the following from a terminal:

.. code-block:: text

   polyfi-ranked windows uninstall --purge-data

Or from the repository root (if you have the source available):

.. code-block:: powershell

   powershell -ExecutionPolicy Bypass -File .\scripts\purge_polyfi.ps1
