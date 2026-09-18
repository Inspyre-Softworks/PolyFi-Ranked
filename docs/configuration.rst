Configuration Guide
===================

PolyFi stores its main configuration in a TOML file. On Windows, the default
path is:

``%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.toml``

If the file does not exist yet, PolyFi creates it automatically on first run.
The app also keeps an example file at:

``%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\config.example.toml``

If the ``POLYFI_APPDATA_ROOT`` user environment variable is set, PolyFi uses
that directory as its app-data root instead. The main config file becomes
``<POLYFI_APPDATA_ROOT>\config.toml`` and the default log directory becomes
``<POLYFI_APPDATA_ROOT>\Logs\``.

Configuration Layout
--------------------

The file has two main sections:

``[global]``
   App-wide behavior such as scan timing, logging, Ethernet handling, and
   automatic speed tests.

``[[networks]]``
   Your ordered Wi-Fi preference list. The first matching visible network wins.

Example
-------

.. code-block:: toml

   [global]
   scan_interval = 10
   connect_timeout = 8
   sync_profile_order_on_start = true
   log_level = 'INFO'
   log_file = ''
   interface_name = ''
   start_minimized_to_tray = false
   auto_disable_wifi_on_ethernet = false
   connect_preferred_after_ethernet_disconnect = true
   ethernet_wifi_mode = 'disconnect_and_disable_autoconnect'
   add_to_startup_programs = false
   add_scheduled_logon_task = false
   auto_check_for_updates = false
   allow_prerelease_updates = false
   show_wifi_disabled_dialog = true
   enable_speed_tests = false
   speed_test_on_new_connection = true
   speed_test_interval = 1800

   [[networks]]
   ssid = 'MyBestWiFi'
   auto_switch = true
   min_db = -72

   [[networks]]
   ssid = 'MySecondChoice'
   auto_switch = true

How PolyFi Uses It
------------------

PolyFi reads the file at startup and watches it for changes while running.
Most settings can be updated live without restarting the app.

The tray menu exposes two distinct editors:

- **Global Configuration…** controls the ``[global]`` values that affect the
  whole application: scan timing, splash/startup integration, speed tests,
  Ethernet handling, and update checks.
- **Manage Networks…** opens Network Settings and controls only
  ``[[networks]]`` entries: priority, automatic switching, and minimum signal.

Older files that use ``[general]`` remain readable. The first save through
either settings window rewrites those values under ``[global]``; existing
values are preserved, and ``[global]`` takes precedence if both tables exist.

The service uses the ``[[networks]]`` list from top to bottom:

1. Scan for visible SSIDs.
2. Find the highest-priority configured SSID that is currently visible.
3. Switch to it if it is more preferred than the current Wi-Fi connection.

Practical Notes
---------------

- ``interface_name = ''`` means "auto-detect the Wi-Fi adapter."
- ``log_file = ''`` means "use the default log path."
- ``add_to_startup_programs = true`` means "keep a tray-launch shortcut in the
  Windows Startup Programs folder."
- ``add_scheduled_logon_task = true`` means "keep a Windows Task Scheduler
  logon task registered for earlier startup after sign-in."
- ``auto_check_for_updates = true`` means "check GitHub Releases for a newer
  installer after the tray icon starts."
- ``allow_prerelease_updates = true`` allows update checks to offer development,
  beta, or release-candidate versions.
- ``speed_test_interval`` is measured in seconds.
- Every ``[[networks]]`` entry must have a non-empty ``ssid``.
- If a network has ``auto_switch = false``, it stays in the list but will not
  be selected automatically.
- If ``min_db`` is set on a network, PolyFi treats that network as
  unavailable when the observed signal is weaker than the configured threshold.
