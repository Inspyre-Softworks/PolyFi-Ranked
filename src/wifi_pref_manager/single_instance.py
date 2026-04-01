"""
Windows single-instance guard helpers for PolyFi.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
KERNEL32 = ctypes.WinDLL('kernel32', use_last_error=True)
KERNEL32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
KERNEL32.CreateMutexW.restype = wintypes.HANDLE
KERNEL32.CloseHandle.argtypes = [wintypes.HANDLE]
KERNEL32.CloseHandle.restype = wintypes.BOOL


class SingleInstanceGuard:
    """
    Hold a named Windows mutex so only one PolyFi process runs at a time.
    """

    def __init__(self, mutex_name: str) -> None:
        self.mutex_name = mutex_name
        self._handle: int | None = None

    def acquire(self) -> bool:
        """
        Acquire the named mutex.

        Returns:
            True when this process became the active instance, otherwise False.
        """
        if self._handle is not None:
            return True

        ctypes.set_last_error(0)
        handle = KERNEL32.CreateMutexW(None, False, self.mutex_name)
        if not handle:
            raise OSError('CreateMutexW failed while creating the single-instance guard.')

        self._handle = handle
        if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
            self.release()
            return False
        return True

    def release(self) -> None:
        """
        Release the mutex handle held by this process.
        """
        if self._handle is None:
            return
        KERNEL32.CloseHandle(self._handle)
        self._handle = None
