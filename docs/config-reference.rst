Config Reference
================

``[global]`` Settings
---------------------

These application-wide values are edited from **Global Configuration…** in
the tray menu. Legacy ``[general]`` tables are still accepted and migrate to
``[global]`` on the next save.

``scan_interval``
   Seconds between evaluation cycles. Lower values react faster but scan more
   often.

``connect_timeout``
   Seconds PolyFi waits after a connect request before checking whether the new
   Wi-Fi connection actually succeeded.

``sync_profile_order_on_start``
   If true, PolyFi updates the Windows Wi-Fi profile order to match your
   configured priority list when the app starts.

``log_level``
   The runtime logging level, such as ``INFO`` or ``DEBUG``.

``log_file``
   Optional custom log file path. Leave it blank to use the default local
   app-data log path.

``interface_name``
   Optional Wi-Fi adapter name. Leave it blank to let PolyFi resolve the
   managed Wi-Fi interface automatically.

``start_minimized_to_tray``
   If true, the app starts in tray mode.

``show_startup_splash``
   Controls **Show splash on app start**. The existing default remains
   ``true``.

``auto_disable_wifi_on_ethernet``
   If true, PolyFi applies the selected Ethernet Wi-Fi action when it detects
   an active wired connection. Default: ``false``.

``connect_preferred_after_ethernet_disconnect``
   If true, PolyFi reconnects to the best available preferred Wi-Fi network
   after Ethernet disconnects. Default: ``true``.

``ethernet_wifi_mode``
   ``disconnect_and_disable_autoconnect`` disconnects Wi-Fi and temporarily
   disables profile auto-connect (the default and recommended mode).
   ``disable_adapter`` disables the Wi-Fi adapter.

``show_wifi_disabled_dialog``
   If true, PolyFi shows a dialog after it disables the Wi-Fi adapter because
   Ethernet became active.

``add_to_startup_programs``
   If true, PolyFi keeps a tray-launch shortcut in the user's Windows Startup
   Programs folder so it can start automatically at logon.
   Default: ``false``.

``add_scheduled_logon_task``
   If true, PolyFi keeps a Windows Task Scheduler logon task registered so it
   can start earlier after sign-in than the Startup Programs shortcut path.
   This is subordinate to ``add_to_startup_programs`` in Global Configuration.
   Default: ``false``.

``auto_check_for_updates``
   If true, the tray app checks GitHub Releases for a newer PolyFi installer
   after startup.
   Default: ``false``.

``allow_prerelease_updates``
   If true, update checks may offer development, beta, or release-candidate
   versions. Default: ``false``.

``enable_speed_tests``
   Enables or disables automatic speed tests entirely.

``speed_test_on_new_connection``
   If true, PolyFi runs a speed test after connecting to a new Wi-Fi network.

``speed_test_interval``
   Seconds between repeated speed tests while remaining connected to the same
   Wi-Fi network. Set to ``0`` to stop periodic retests.

Global Configuration Window
---------------------------

The window groups the settings as follows:

- **General:** ``scan_interval``, ``show_startup_splash``,
  ``add_to_startup_programs``, and ``add_scheduled_logon_task``.
- **Speed Tests:** ``enable_speed_tests``, ``speed_test_interval``, and
  ``speed_test_on_new_connection``.
- **Ethernet Handling:** ``auto_disable_wifi_on_ethernet``,
  ``connect_preferred_after_ethernet_disconnect``, and
  ``ethernet_wifi_mode``.
- **Updates:** ``auto_check_for_updates`` and
  ``allow_prerelease_updates``.

The Task Scheduler control is hidden unless Start with Windows is enabled.
Speed-test details are hidden unless speed tests are enabled. The prerelease
control is hidden unless automatic update checking is enabled. These changes
take effect immediately while the window is open.

``[[networks]]`` Entries
------------------------

These per-network values are edited from **Manage Networks…** / Network
Settings. No application-wide controls are duplicated in that window.

Each network entry represents one saved Windows Wi-Fi profile:

``ssid``
   The Wi-Fi profile name / SSID PolyFi should look for.

``auto_switch``
   If true, PolyFi may switch to this network automatically when it becomes the
   highest-priority visible choice.

``min_db``
   Optional minimum signal threshold for that network. When set, PolyFi treats
   the network as unavailable if the strongest observed scan result is weaker
   than this approximate dBm value.

Example Network List
--------------------

.. code-block:: toml

   [[networks]]
   ssid = 'OfficeWiFi'
   auto_switch = true
   min_db = -72

   [[networks]]
   ssid = 'PhoneHotspot'
   auto_switch = false

In that example, ``OfficeWiFi`` can be selected automatically, while
``PhoneHotspot`` stays in the ordered list for reference but will not be chosen
unless you connect to it manually. Because ``OfficeWiFi`` has a minimum signal
threshold, PolyFi ignores it when the scan result is weaker than ``-72 dBm``.
