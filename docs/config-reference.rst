Config Reference
================

``[general]`` Settings
----------------------

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

``auto_disable_wifi_on_ethernet``
   If true, PolyFi disables the Wi-Fi adapter when it detects an active wired
   Ethernet connection and re-enables Wi-Fi when Ethernet disconnects.

``show_wifi_disabled_dialog``
   If true, PolyFi shows a dialog after it disables the Wi-Fi adapter because
   Ethernet became active.

``enable_speed_tests``
   Enables or disables automatic speed tests entirely.

``speed_test_on_new_connection``
   If true, PolyFi runs a speed test after connecting to a new Wi-Fi network.

``speed_test_interval``
   Seconds between repeated speed tests while remaining connected to the same
   Wi-Fi network. Set to ``0`` to stop periodic retests.

``[[networks]]`` Entries
------------------------

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
