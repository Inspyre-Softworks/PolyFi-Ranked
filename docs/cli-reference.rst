CLI Reference
=============

All commands assume the package is installed (``pip install .`` or
``poetry install``) and that ``polyfi-ranked`` is on your ``PATH``, or that
you prefix each command with ``poetry run``.

Top-Level Flags
---------------

``--version`` / ``-V``
   Print the installed PolyFi: Ranked version and exit.

``--tray``
   Start PolyFi minimized to the system tray.

``-l <LEVEL>``
   Override the log level for this run (e.g. ``-l DEBUG``).

``--show-splash`` / ``--no-splash``
   Override the ``show_startup_splash`` config setting for a single run.

``--save-speed-test-history`` / ``--no-save-speed-test-history``
   Override the ``save_speed_test_history`` config setting for a single run.

``--speed-test-history-file <PATH>``
   Override the speed-test history file path for a single run.

Global Configuration Overrides
------------------------------

Every option shown in the Global Configuration window has a CLI equivalent:

``--scan-interval <SECONDS>``
   Override the network scan/evaluation interval.

``--show-splash`` / ``--no-splash``
   Show or hide the splash on app start.

``--start-with-windows`` / ``--no-start-with-windows``
   Enable or disable the Startup Programs shortcut.

``--schedule-with-task-scheduler`` / ``--no-schedule-with-task-scheduler``
   Enable or disable the earlier Task Scheduler start. Scheduling cannot be
   enabled together with ``--no-start-with-windows``.

``--enable-speed-tests`` / ``--disable-speed-tests``
   Enable or disable automatic speed tests. ``--no-speed-tests`` is an alias
   for the disable form.

``--speed-test-interval <SECONDS>``
   Set the repeated test interval; ``0`` disables periodic retests.

``--speed-test-on-connect`` / ``--no-speed-test-on-connect``
   Enable or disable a speed test after a Wi-Fi connection.

``--wifi-off-on-ethernet`` / ``--no-wifi-off-on-ethernet``
   Enable or disable automatic Wi-Fi handling while Ethernet is active.

``--connect-preferred-after-ethernet-disconnect`` / ``--no-connect-preferred-after-ethernet-disconnect``
   Enable or disable PolyFi-initiated preferred-network connection after
   Ethernet disconnects.

``--ethernet-action disconnect-and-disable-autoconnect`` / ``--ethernet-action disable-adapter``
   Select the Ethernet Wi-Fi action.

``--check-for-updates-automatically`` / ``--no-check-for-updates-automatically``
   Enable or disable the automatic update check. The shorter
   ``--auto-check-for-updates`` and ``--no-auto-check-for-updates`` aliases are
   also accepted.

``--allow-prerelease`` / ``--no-allow-prerelease``
   Include or exclude prerelease versions from update checks.

By default these options apply only to the current process. Add
``--save-config-overrides`` to write all supplied configuration overrides to
the active TOML file. For example:

.. code-block:: powershell

   polyfi-ranked --enable-speed-tests --speed-test-interval 900 `
     --check-for-updates-automatically --save-config-overrides

.. note::

   The older ``--print-paths`` flag is still accepted for compatibility but
   the ``paths`` sub-command is the preferred entry point.

``paths`` Command
-----------------

Print all resolved file paths (config, log, state files, and so on):

.. code-block:: powershell

   polyfi-ranked paths

``config`` Commands
-------------------

``config init``
   Generate a full config file with every supported setting and its defaults:

   .. code-block:: powershell

      polyfi-ranked config init

   Write to a custom location or overwrite an existing file:

   .. code-block:: powershell

      polyfi-ranked config init --config C:\path\to\config.toml --force

``windows`` Commands
--------------------

``windows start-menu install``
   Install a Start Menu shortcut that launches PolyFi in tray mode:

   .. code-block:: powershell

      polyfi-ranked windows start-menu install

``windows startup install``
   Install a Startup Programs shortcut that launches PolyFi in tray mode at
   logon:

   .. code-block:: powershell

      polyfi-ranked windows startup install

``windows logon-task install``
   Install a Windows Task Scheduler logon task that launches PolyFi in tray
   mode at logon:

   .. code-block:: powershell

      polyfi-ranked windows logon-task install

   Remove the task:

   .. code-block:: powershell

      polyfi-ranked windows logon-task remove

``windows uninstall``
   Remove PolyFi shortcuts and scheduled tasks.  Add ``--purge-data`` to also
   remove all config, log, and state files:

   .. code-block:: powershell

      polyfi-ranked windows uninstall
      polyfi-ranked windows uninstall --purge-data

Task Scheduler Entry Points
----------------------------

``polyfi-ranked-install-task``
   Register a Windows Task Scheduler logon task that starts PolyFi in tray mode:

   .. code-block:: powershell

      polyfi-ranked-install-task

   Remove the task:

   .. code-block:: powershell

      polyfi-ranked-install-task --uninstall
