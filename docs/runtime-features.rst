Runtime Features
================

.. contents:: On this page
   :local:
   :depth: 2

Tray Mode
---------

Launch PolyFi minimized to the system tray:

.. code-block:: powershell

   polyfi-ranked --tray

The tray icon lets you monitor connection status and adjust settings without
opening a terminal.  Right-click the icon for the context menu.

Use **Global Configuration…** for application-wide behavior. Use **Manage
Networks…** for the ordered Wi-Fi list and each network's automatic-switch and
minimum-signal settings.

Live Config Reload
------------------

Edit the config file while PolyFi: Ranked is running.  On the next scan cycle
it reloads the file and applies changes to the following settings without
requiring a restart:

- ``ssid`` order (``[[networks]]`` list)
- ``auto_switch``
- ``min_db``
- ``scan_interval``
- ``connect_timeout``
- ``interface_name``
- ``sync_profile_order_on_start``
- ``log_level``
- ``log_file``
- ``show_wifi_disabled_dialog``
- ``auto_disable_wifi_on_ethernet``
- ``connect_preferred_after_ethernet_disconnect``
- ``ethernet_wifi_mode``
- ``add_to_startup_programs``
- ``show_startup_splash``
- ``splash_image_path``
- ``splash_fade_in_ms``
- ``splash_hold_ms``
- ``splash_fade_out_ms``
- ``enable_speed_tests``
- ``speed_test_on_new_connection``
- ``speed_test_interval``
- ``save_speed_test_history``
- ``speed_test_history_file``
- ``auto_check_for_updates``
- ``allow_prerelease_updates``

Ethernet-Aware Wi-Fi Mode
--------------------------

PolyFi can manage the Wi-Fi adapter automatically when a wired Ethernet
connection is detected. These ``[global]`` settings, also available in the
**Ethernet Handling** section of Global Configuration, control the behavior:

.. code-block:: toml

   auto_disable_wifi_on_ethernet = false
   connect_preferred_after_ethernet_disconnect = true
   ethernet_wifi_mode = 'disconnect_and_disable_autoconnect'

**Mode options:**

``disconnect_and_disable_autoconnect`` *(default, no admin required)*
   - Captures the current Wi-Fi SSID and profile auto-connect states.
   - Disconnects Wi-Fi and sets saved Wi-Fi profiles to manual-connect while
     Ethernet is active.
   - Restores the captured Wi-Fi state when Ethernet disconnects and again on
     app exit.

``disable_adapter`` *(requires administrator rights or the PolyFi Wi-Fi task helper)*
   - Disables the Wi-Fi adapter entirely while Ethernet is active.
   - Re-enables it when Ethernet disconnects.

When ``connect_preferred_after_ethernet_disconnect`` is false, PolyFi restores
Wi-Fi availability and profile auto-connect state but does not initiate its own
preferred-network connection after the Ethernet transition.

Speed Tests
-----------

PolyFi can run automatic speed tests when a new connection is established or at
a fixed interval. These ``[global]`` settings are exposed under **Speed Tests**
in Global Configuration:

.. code-block:: toml

   enable_speed_tests = false
   speed_test_on_new_connection = true
   speed_test_interval = 1800
   save_speed_test_history = false
   speed_test_history_file = ''

- ``speed_test_interval`` is measured in seconds.
- When ``speed_test_history_file`` is blank, PolyFi uses the default local
  app-data history path (``speedtest_history.jsonl``).

Windows Startup Integration
-----------------------------

These ``[global]`` settings control whether PolyFi keeps itself registered for
automatic startup:

.. code-block:: toml

   add_to_startup_programs = false
   add_scheduled_logon_task = false

When enabled, PolyFi refreshes the Startup Programs shortcut on launch and
whenever the config reloads.  When disabled, PolyFi removes the shortcut if it
exists.

The scheduled logon task uses Windows Task Scheduler and can start earlier
after sign-in than the Startup Programs shortcut. In Global Configuration it
is shown only while **Start with Windows** is enabled. Manage it there or from
the CLI:

.. code-block:: powershell

   polyfi-ranked windows logon-task install
   polyfi-ranked windows logon-task remove

The standalone helper remains available for environments that install console
scripts:

.. code-block:: powershell

   polyfi-ranked-install-task
   polyfi-ranked-install-task --uninstall

Update Checks
-------------

When ``auto_check_for_updates`` is true, the tray app checks GitHub Releases
after startup.  The tray menu also includes **Check for Updates** for manual
checks and **About PolyFi: Ranked** for version, documentation, and GitHub
links.  When a newer release includes a Windows installer asset, PolyFi can
download the installer to local app-data and launch it for the user.
``allow_prerelease_updates`` controls whether those checks can offer a
prerelease and is shown in Global Configuration only while automatic checking
is enabled. Both settings default to false.

Startup Splash Screen
---------------------

PolyFi can show an InspyreSplash-powered splash screen on startup.  These
``[global]`` settings control it:

.. code-block:: toml

   show_startup_splash = true
   splash_image_path = ''
   splash_fade_in_ms = 280
   splash_hold_ms = 1100
   splash_fade_out_ms = 280

- ``splash_hold_ms`` controls how long the splash stays visible.
- The fade timing fields (``splash_fade_in_ms``, ``splash_fade_out_ms``) are
  accepted so existing configs keep working, but the packaged InspyreSplash
  animation controls its own layer effects.
- When ``splash_image_path`` is blank, PolyFi first looks for the legacy
  ``polyfi_ranked_splash.png`` override in:

  - ``%LOCALAPPDATA%\Inspyre-Softworks\PolyFi-Ranked\``
  - ``%USERPROFILE%\OneDrive\Pictures\``
  - ``%USERPROFILE%\Pictures\``

  If no image override exists, PolyFi uses the packaged
  ``wifi_pref_manager/assets/splashes/intro/splash.json`` InspyreSplash bundle.

Notes
-----

- PolyFi uses ``netsh wlan`` under the hood.  Your SSIDs must already exist as
  saved Windows Wi-Fi profiles.
- If ``min_db`` is set on a ``[[networks]]`` block, PolyFi treats that network
  as unavailable when the best observed scan result is weaker than that
  approximate dBm threshold.  If the currently connected preferred network drops
  below its own threshold, PolyFi moves to the next preferred network whose
  signal also meets its configured threshold.
- On Python 3.12+ PolyFi restores the Wi-Fi state that was active before it
  started when it exits.
