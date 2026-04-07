"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    wifi_adapter_tasks.py

Description:
    Windows Task Scheduler helpers that let a non-elevated process control
    the Wi-Fi adapter.  When an administrator policy prevents Python from
    running elevated (e.g. an AppLocker rule targeting ``python.exe``),
    PolyFi registers two SYSTEM-level scheduled tasks that execute
    ``netsh.exe`` on its behalf.

    Tasks are created by elevating ``powershell.exe`` — a Microsoft-signed
    system binary not typically covered by AppLocker rules for Python — so
    the one-time setup prompt shows "Windows PowerShell" in the UAC dialog
    rather than the blocked ``python.exe``.

    At runtime, triggering the tasks via ``schtasks /run`` requires no UAC
    because members of the local Administrators group may always invoke
    scheduled tasks regardless of the process elevation level.
"""

from __future__ import annotations

import base64
import ctypes
import subprocess
import time


TASK_NAME_DISABLE = 'PolyFi-DisableWiFi'
TASK_NAME_ENABLE = 'PolyFi-EnableWiFi'

_INSTALL_POLL_INTERVAL = 0.5
_INSTALL_TIMEOUT = 12.0


class WifiAdapterTaskError(RuntimeError):
    """Raised when a scheduled-task trigger operation fails."""


class WifiAdapterTaskManager:
    """
    Manage Windows scheduled tasks for privileged Wi-Fi adapter control.

    Two SYSTEM-level scheduled tasks are registered — one to disable and
    one to enable a specific Wi-Fi interface.  They can be triggered from
    an unprivileged (non-elevated) admin process via ``schtasks /run``.

    Methods:
        are_installed:
            Return True when both tasks exist and target the given interface.
        install:
            Launch an elevated PowerShell to create both SYSTEM tasks.
        install_and_wait:
            Install and poll until tasks appear or the timeout expires.
        uninstall:
            Delete both tasks.
        disable_wifi:
            Trigger the disable task and wait briefly for execution.
        enable_wifi:
            Trigger the enable task and wait briefly for execution.
    """

    @staticmethod
    def _hidden_subprocess_kwargs() -> dict[str, object]:
        """Return subprocess kwargs that suppress console windows."""
        kwargs: dict[str, object] = {}
        create_no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        if create_no_window:
            kwargs['creationflags'] = create_no_window
        startupinfo_type = getattr(subprocess, 'STARTUPINFO', None)
        startf_use_showwindow = getattr(subprocess, 'STARTF_USESHOWWINDOW', 0)
        if startupinfo_type is not None and startf_use_showwindow:
            si = startupinfo_type()
            si.dwFlags |= startf_use_showwindow
            si.wShowWindow = 0
            kwargs['startupinfo'] = si
        return kwargs

    def _run_schtasks(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ['schtasks', *args],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            **self._hidden_subprocess_kwargs(),
        )

    def _task_exists(self, task_name: str) -> bool:
        """Quick existence check via schtasks (avoids PowerShell overhead)."""
        return self._run_schtasks('/query', '/tn', task_name).returncode == 0

    def _get_task_action_arguments(self, task_name: str) -> str | None:
        """
        Return the action-arguments string for the task's first action.

        Uses ``Get-ScheduledTask`` so the full argument string (including the
        embedded interface name) is reliably returned regardless of locale.

        Returns ``None`` when the task does not exist, has no actions, or
        cannot be queried.
        """
        ps = (
            f"$t = Get-ScheduledTask -TaskName '{task_name}' "
            f"-ErrorAction SilentlyContinue; "
            f"if ($t -and $t.Actions -and $t.Actions.Count -gt 0) "
            f"{{ $t.Actions[0].Arguments }} else {{ '' }}"
        )
        result = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', ps],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
            **self._hidden_subprocess_kwargs(),
        )
        if result.returncode != 0:
            return None
        output = result.stdout.strip()
        return output if output else None

    def are_installed(self, interface_name: str) -> bool:
        """
        Return True when both tasks exist and embed the given interface name.

        Parameters:
            interface_name:
                Wi-Fi interface name to verify (case-insensitive).
        """
        esc = interface_name.lower()
        for name in (TASK_NAME_DISABLE, TASK_NAME_ENABLE):
            args = self._get_task_action_arguments(name)
            if args is None:
                return False
            if esc not in args.lower():
                return False
        return True

    @staticmethod
    def _encode_ps_command(script: str) -> str:
        """Base64-encode a PowerShell script for use with ``-EncodedCommand``."""
        return base64.b64encode(script.encode('utf-16-le')).decode('ascii')

    @staticmethod
    def _escape_for_ps_double_quoted_string(value: str) -> str:
        """
        Escape a string for safe embedding inside a PowerShell double-quoted string.

        PowerShell uses the backtick as its escape character inside ``"..."``
        strings.  The three characters that require escaping are:

        * `` ` `` (backtick — the escape character itself, must be doubled)
        * ``"`` (double-quote — would close the surrounding string)
        * ``$`` (dollar-sign — would trigger variable expansion)

        Backtick escaping is applied first to avoid double-processing.
        """
        return value.replace('`', '``').replace('"', '`"').replace('$', '`$')

    def _build_install_script(self, interface_name: str) -> str:
        """
        Build and encode a PowerShell script that creates both SYSTEM tasks.

        The interface name is embedded directly in the task action arguments
        after being escaped for PowerShell double-quoted string context, so
        no variable interpolation risks exist at task execution time.
        """
        esc = self._escape_for_ps_double_quoted_string(interface_name)
        disable_arg = f'interface set interface `"{esc}`" admin=disabled'
        enable_arg = f'interface set interface `"{esc}`" admin=enabled'
        script = (
            '$principal = New-ScheduledTaskPrincipal '
            "-UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest\n"
            f"Register-ScheduledTask -Force -TaskName '{TASK_NAME_DISABLE}' "
            "-Action (New-ScheduledTaskAction -Execute 'netsh.exe' "
            f'-Argument "{disable_arg}") '
            "-Principal $principal\n"
            f"Register-ScheduledTask -Force -TaskName '{TASK_NAME_ENABLE}' "
            "-Action (New-ScheduledTaskAction -Execute 'netsh.exe' "
            f'-Argument "{enable_arg}") '
            "-Principal $principal"
        )
        return self._encode_ps_command(script)

    def install(self, interface_name: str) -> bool:
        """
        Launch an elevated PowerShell to create both SYSTEM tasks.

        ``powershell.exe`` is a Microsoft-signed system binary.  AppLocker
        rules that block ``python.exe`` from elevation do not apply to it,
        so a standard UAC prompt for PowerShell will appear instead.

        Parameters:
            interface_name:
                Wi-Fi interface name to embed in the task commands.

        Returns:
            ``True`` when the elevation request was accepted
            (``ShellExecuteW`` > 32), ``False`` when the user cancelled the
            UAC prompt (code 1223).

        Raises:
            OSError:
                When ``ShellExecuteW`` returns a hard-error code.
        """
        encoded = self._build_install_script(interface_name)
        try:
            result = ctypes.windll.shell32.ShellExecuteW(
                None,
                'runas',
                'powershell.exe',
                f'-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand {encoded}',
                None,
                0,  # SW_HIDE
            )
        except (AttributeError, OSError) as exc:
            raise OSError(f'ShellExecuteW is unavailable on this platform: {exc}') from exc
        if result > 32:
            return True
        if result == 1223:
            return False
        raise OSError(
            f'ShellExecuteW for scheduled-task installation returned code {result}.'
        )

    def install_and_wait(
        self,
        interface_name: str,
        timeout: float = _INSTALL_TIMEOUT,
    ) -> bool:
        """
        Install tasks and poll until both appear or the timeout expires.

        Parameters:
            interface_name:
                Wi-Fi interface name passed to :meth:`install`.
            timeout:
                Maximum seconds to wait for tasks to become queryable.

        Returns:
            ``True`` when both tasks were confirmed created within
            ``timeout``, ``False`` otherwise.
        """
        if not self.install(interface_name):
            return False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(_INSTALL_POLL_INTERVAL)
            if self._task_exists(TASK_NAME_DISABLE) and self._task_exists(TASK_NAME_ENABLE):
                return self.are_installed(interface_name)
        return False

    def uninstall(self) -> None:
        """Delete both PolyFi Wi-Fi control tasks if they exist."""
        for name in (TASK_NAME_DISABLE, TASK_NAME_ENABLE):
            self._run_schtasks('/delete', '/tn', name, '/f')

    def _trigger_task(self, task_name: str, post_wait: float) -> None:
        result = self._run_schtasks('/run', '/tn', task_name)
        if result.returncode != 0:
            raise WifiAdapterTaskError(
                f'Failed to trigger scheduled task {task_name!r}: '
                f'{(result.stderr or result.stdout).strip()}'
            )
        time.sleep(post_wait)

    def disable_wifi(self, *, post_wait: float = 2.0) -> None:
        """
        Trigger the disable-WiFi task and wait briefly for execution.

        Parameters:
            post_wait:
                Seconds to sleep after triggering so ``netsh.exe`` finishes.

        Raises:
            WifiAdapterTaskError:
                When ``schtasks /run`` exits with a non-zero code.
        """
        self._trigger_task(TASK_NAME_DISABLE, post_wait)

    def enable_wifi(self, *, post_wait: float = 2.0) -> None:
        """
        Trigger the enable-WiFi task and wait briefly for execution.

        Parameters:
            post_wait:
                Seconds to sleep after triggering so ``netsh.exe`` finishes.

        Raises:
            WifiAdapterTaskError:
                When ``schtasks /run`` exits with a non-zero code.
        """
        self._trigger_task(TASK_NAME_ENABLE, post_wait)
